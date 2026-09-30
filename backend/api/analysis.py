"""
音声分析APIエンドポイント
音声ファイルのアップロード・分析結果の取得・統計情報の取得を担当する
"""

import logging
import os
import tempfile

import redis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from audio.analyzer import AudioAnalyzer
from auth_utils import get_current_user
from database import SessionLocal, get_db
from models import AnalysisResult, User

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

logger = logging.getLogger(__name__)

# アプリ起動時に1回だけインスタンス化（Demucsモデルのロードが重いため）
audio_analyzer = AudioAnalyzer()

# 分析の進行状況はRedisに持つ（DBスキーマを変えずに状態を扱うための暫定対応）
_redis = redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379"))
_STATUS_TTL_SECONDS = 24 * 60 * 60

STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

_FAILURE_MESSAGE = "音声の分析に失敗しました。ファイルが壊れていないかご確認ください。"


@router.post("/upload", status_code=202)
async def upload_audio(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    song_title: str = "",
    artist_name: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    音声ファイルを受け取り、分析をバックグラウンドで開始する

    CPUでの分析は数分かかりリバースプロキシのタイムアウトに引っかかるため、
    ここでは結果を待たずに202を返す。
    呼び出し側は GET /api/v1/analysis/{analysis_id} をポーリングして完了を待つ。

    - audio_file: 音声ファイル（WAV/MP3/M4A）
    - song_title: 楽曲名（任意）
    - artist_name: アーティスト名（任意）
    """
    _validate_audio_file(audio_file)

    content = await audio_file.read()
    _validate_file_size(content)

    pending = _create_pending_record(db, song_title, artist_name, current_user.id)
    _write_status(pending.id, STATUS_PROCESSING)

    background_tasks.add_task(
        _analyze_and_save,
        pending.id,
        audio_file.filename,
        content,
        song_title,
        artist_name,
    )

    return {"analysis_id": pending.id, "status": STATUS_PROCESSING}


@router.get("/user/statistics")
def get_user_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ログインユーザーの分析結果統計を返す

    ダッシュボード画面のグラフ・サマリー表示に使用する
    分析中・失敗したレコードはスコアが未確定なので集計から除外する
    """
    results = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.user_id == current_user.id)
        .filter(AnalysisResult.pitch_accuracy.isnot(None))
        .order_by(AnalysisResult.created_at.asc())
        .all()
    )

    history = [
        {
            "date": r.created_at.strftime("%m/%d"),
            "pitch": round(r.pitch_accuracy) if r.pitch_accuracy is not None else 0,
            "rhythm": round(r.rhythm_score) if r.rhythm_score is not None else 0,
        }
        for r in results
    ]

    pitch_values = [h["pitch"] for h in history]
    growth_rate = _calculate_growth_rate(pitch_values)

    return {
        "history": history,
        "total_count": len(history),
        "best_pitch": max(pitch_values) if pitch_values else 0,
        "growth_rate": growth_rate,
    }


@router.get("/{analysis_id}")
def get_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    指定IDの分析結果と進行状況を取得する

    - analysis_id: アップロード時に返されたID
    - ログインユーザー自身の分析結果のみ取得可能
    - status が processing の間は result の各値が未確定（None）
    """
    result = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="分析結果が見つかりません。")
    if result.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="この分析結果へのアクセス権限がありません。")

    status, error_detail = _read_status(result)

    return {
        "analysis_id": result.id,
        "status": status,
        "error": error_detail,
        "song_title": result.song_title,
        "artist_name": result.artist_name,
        "result": {
            "pitch_accuracy": result.pitch_accuracy,
            "rhythm_score": result.rhythm_score,
            "techniques": result.techniques,
            "vocal_range": result.vocal_range,
            "feedback": result.feedback,
        },
    }


# ── 進行状況の管理 ────────────────────────────────────────────────────────────


def _status_key(analysis_id: int) -> str:
    return f"analysis_status:{analysis_id}"


def _write_status(analysis_id: int, status: str, detail: str = "") -> None:
    """進行状況をRedisに記録する（一定時間で自動的に消える）"""
    value = f"{status}:{detail}" if detail else status
    _redis.setex(_status_key(analysis_id), _STATUS_TTL_SECONDS, value)


def _read_status(record: AnalysisResult) -> tuple[str, str]:
    """
    進行状況とエラー内容を返す

    RedisのキーがTTLで消えている場合は、DBに結果が入っているかで完了を判定する
    """
    raw = _redis.get(_status_key(record.id))
    if raw is None:
        has_result = record.pitch_accuracy is not None
        return (STATUS_COMPLETED if has_result else STATUS_FAILED), ""

    status, _, detail = raw.decode().partition(":")
    return status, detail


# ── プライベート関数 ──────────────────────────────────────────────────────────


def _analyze_and_save(
    analysis_id: int, filename: str, content: bytes, song_title: str, artist_name: str
) -> None:
    """
    バックグラウンドで分析を実行し、作成済みのレコードに結果を書き込む

    リクエスト用のDBセッションはレスポンス返却時に閉じられるため、
    ここでは新しいセッションを作って使う
    """
    db = SessionLocal()
    try:
        analysis_data = _run_analysis(filename, content, song_title, artist_name)
        _fill_result(db, analysis_id, analysis_data)
        _write_status(analysis_id, STATUS_COMPLETED)
    except Exception:
        db.rollback()
        # 例外の詳細はログにだけ残し、利用者には内部情報を返さない
        logger.exception("分析に失敗しました: analysis_id=%s", analysis_id)
        _write_status(analysis_id, STATUS_FAILED, _FAILURE_MESSAGE)
    finally:
        db.close()


def _validate_audio_file(audio_file: UploadFile) -> None:
    """ファイル形式を検証する"""
    allowed_types = ["audio/wav", "audio/mpeg", "audio/mp4", "audio/x-m4a"]
    if audio_file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="対応していないファイル形式です。WAV/MP3/M4Aのみ対応しています。",
        )


def _validate_file_size(content: bytes) -> None:
    """ファイルサイズを検証する（50MB超は拒否）"""
    max_size = 50 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail="ファイルサイズが大きすぎます。50MB以下にしてください。",
        )


def _run_analysis(
    filename: str, content: bytes, song_title: str, artist_name: str
) -> dict:
    """
    一時ファイルに書き出して音声分析を実行する
    分析後は著作権保護のため一時ファイルを即時削除する
    """
    suffix = os.path.splitext(filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = audio_analyzer.analyze(tmp_path)
        result["song_title"] = song_title
        result["artist_name"] = artist_name
        return result
    finally:
        os.unlink(tmp_path)


def _create_pending_record(
    db: Session, song_title: str, artist_name: str, user_id: int
) -> AnalysisResult:
    """分析開始前の空レコードを作成する（スコア類は分析完了後に埋める）"""
    record = AnalysisResult(
        user_id=user_id,
        song_title=song_title,
        artist_name=artist_name,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _fill_result(db: Session, analysis_id: int, analysis_data: dict) -> None:
    """分析完了後のスコアを既存レコードに書き込んでcommitする"""
    record = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if record is None:
        logger.error("保存先のレコードが見つかりません: analysis_id=%s", analysis_id)
        return

    record.pitch_accuracy = analysis_data.get("pitch_accuracy")
    record.rhythm_score = analysis_data.get("rhythm_score")
    record.techniques = analysis_data.get("techniques")
    record.vocal_range = analysis_data.get("vocal_range")
    record.feedback = analysis_data.get("feedback")
    db.commit()


def _calculate_growth_rate(pitch_values: list[float]) -> int:
    """
    最初と最後のピッチスコアから成長率（%）を計算する
    データが2件未満の場合は0を返す
    """
    if len(pitch_values) < 2 or pitch_values[0] == 0:
        return 0
    growth = ((pitch_values[-1] - pitch_values[0]) / pitch_values[0]) * 100
    return round(growth)
