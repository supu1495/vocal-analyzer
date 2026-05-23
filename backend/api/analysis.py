"""
音声分析APIエンドポイント
音声ファイルのアップロード・分析結果の取得・統計情報の取得を担当する
"""

import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from celery_app import celery_app
from tasks import analyze_audio_task
from auth_utils import get_current_user
from database import get_db
from models import AnalysisResult, User

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

# 共有ボリュームの一時ファイル置き場
_UPLOAD_DIR = "/tmp/vocal_analyzer"

# アップロード上限とストリーミング読み込みのチャンクサイズ
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
_CHUNK_SIZE = 1024 * 1024           # 1MB


@router.post("/upload")
async def upload_audio(
    audio_file: UploadFile = File(...),
    song_title: str = "",
    artist_name: str = "",
    current_user: User = Depends(get_current_user),
):
    """
    音声ファイルをアップロードして分析タスクをキューに登録する

    - audio_file: 音声ファイル（WAV/MP3/M4A）
    - song_title: 楽曲名（任意）
    - artist_name: アーティスト名（任意）
    - 戻り値: task_id（ステータス確認に使用）
    """
    _validate_audio_content_type(audio_file)

    tmp_path = await _stream_to_shared_volume(audio_file)

    task = analyze_audio_task.delay(tmp_path, song_title, artist_name, current_user.id)

    return {
        "task_id": task.id,
        "status": "processing",
    }


@router.get("/status/{task_id}")
def get_analysis_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    タスクの進捗を確認する

    - task_id: アップロード時に返された task_id
    - 戻り値: status（PENDING / SUCCESS / FAILURE）と analysis_id（完了時のみ）
    """
    # アプリを明示的に渡さないと DisabledBackend を見に行って AttributeError になる
    result = celery_app.AsyncResult(task_id)

    if result.status == "SUCCESS":
        return {"status": "SUCCESS", "analysis_id": result.result}

    if result.status == "FAILURE":
        return {"status": "FAILURE", "detail": "分析中にエラーが発生しました。"}

    return {"status": result.status}


@router.get("/user/statistics")
def get_user_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ログインユーザーの分析結果統計を返す

    ダッシュボード画面のグラフ・サマリー表示に使用する
    """
    results = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.user_id == current_user.id)
        .order_by(AnalysisResult.created_at.asc())
        .all()
    )

    history = [
        {
            "date": record.created_at.strftime("%m/%d"),
            "pitch": round(record.pitch_accuracy) if record.pitch_accuracy is not None else 0,
            "rhythm": round(record.rhythm_score) if record.rhythm_score is not None else 0,
        }
        for record in results
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
    指定IDの分析結果を取得する

    - analysis_id: ステータス確認で返された analysis_id
    - ログインユーザー自身の分析結果のみ取得可能
    """
    result = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if result is None:
        raise HTTPException(status_code=404, detail="分析結果が見つかりません。")
    if result.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="この分析結果へのアクセス権限がありません。")

    return {
        "analysis_id": result.id,
        "song_title": result.song_title,
        "artist_name": result.artist_name,
        "result": {
            "pitch_accuracy": result.pitch_accuracy,
            "rhythm_score": result.rhythm_score,
            "techniques": result.techniques,
            "vocal_range": result.vocal_range,
            "score_matrix": {
                "total_score": result.total_score,
                "faithfulness_score": result.faithfulness_score,
                "technique_score": result.technique_score,
                "naturalness_penalty": result.naturalness_penalty,
            },
            "feedback": result.feedback,
        },
    }


# ── プライベート関数 ──────────────────────────────────────────────────────────


def _validate_audio_content_type(audio_file: UploadFile) -> None:
    """ブラウザ側の Content-Type で1次フィルタする（偽装可能なため後段の magic bytes 検証と併用する）"""
    allowed_types = ["audio/wav", "audio/mpeg", "audio/mp4", "audio/x-m4a"]
    if audio_file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="対応していないファイル形式です。WAV/MP3/M4Aのみ対応しています。",
        )


def _validate_audio_magic_bytes(head: bytes) -> None:
    """ファイル先頭バイト（magic bytes）で音声形式を検証する。

    Content-Type はブラウザが付ける任意のヘッダで偽装可能なため、ファイルの実体
    から判別する。WAV/MP3/M4A 以外は拒否する。
    """
    if len(head) < 12:
        raise HTTPException(status_code=400, detail="ファイルが破損しているか小さすぎます。")

    # WAV: "RIFF" + サイズ(4byte) + "WAVE"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return
    # MP3: ID3v2 タグ付き
    if head[:3] == b"ID3":
        return
    # MP3: 裸の MPEG オーディオフレーム sync (0xFFEx〜0xFFFx)
    if head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return
    # M4A: ISO Base Media File Format。offset 4 から "ftyp"
    if head[4:8] == b"ftyp":
        return

    raise HTTPException(
        status_code=400,
        detail="ファイル内容が WAV/MP3/M4A のいずれにも一致しません。",
    )


async def _stream_to_shared_volume(audio_file: UploadFile) -> str:
    """
    アップロードファイルをチャンク単位で共有ボリュームに書き込む。

    50MB を超えた時点で書き込みを中止し、書き途中のファイルを削除して拒否する。
    最初のチャンクで magic bytes 検証を行い、Content-Type 偽装に対する追加防御とする。
    メモリ使用量を _CHUNK_SIZE 程度に抑えるためファイル全体を一括で読み込まない。

    ファイル名衝突を避けるため UUID をプレフィックスに付ける。
    """
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    suffix = os.path.splitext(audio_file.filename)[1]
    tmp_path = os.path.join(_UPLOAD_DIR, f"{uuid.uuid4()}{suffix}")

    total = 0
    first_chunk = True
    try:
        with open(tmp_path, "wb") as f:
            while chunk := await audio_file.read(_CHUNK_SIZE):
                if first_chunk:
                    _validate_audio_magic_bytes(chunk[:16])
                    first_chunk = False
                total += len(chunk)
                if total > _MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=400,
                        detail="ファイルサイズが大きすぎます。50MB以下にしてください。",
                    )
                f.write(chunk)
        return tmp_path
    except Exception:
        # 中止時は書き途中のファイルを残さない
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _calculate_growth_rate(pitch_values: list[float]) -> int:
    """
    最初と最後のピッチスコアから成長率（%）を計算する
    データが2件未満の場合は0を返す
    """
    if len(pitch_values) < 2 or pitch_values[0] == 0:
        return 0
    growth = ((pitch_values[-1] - pitch_values[0]) / pitch_values[0]) * 100
    return round(growth)
