"""
音声分析APIエンドポイント
音声ファイルのアップロード・分析結果の取得・統計情報の取得を担当する
"""

import logging
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from celery_app import celery_app
from tasks import analyze_audio_task
from auth_utils import get_current_user, get_task_owner, save_task_owner
from database import get_db
from models import AnalysisResult, User
from upload_limits import (
    acquire_analysis_slot,
    count_daily_upload,
    daily_limit_retry_after,
    daily_upload_limit,
    release_analysis_slot,
)

logger = logging.getLogger(__name__)

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
    - 同時に分析できるのは1人1件。分析中なら 429
    - 1日（日本時間0時区切り）の回数に上限がある。超えたら 429（Retry-After: 次の0時までの秒数）
    """
    _validate_audio_content_type(audio_file)

    retry_after = daily_limit_retry_after(current_user.id)
    if retry_after is not None:
        logger.warning(
            "Upload rejected (daily limit reached): user_id=%d retry_after=%d",
            current_user.id, retry_after,
        )
        raise HTTPException(
            status_code=429,
            detail=f"今日のアップロード上限（{daily_upload_limit()}回）に達しました。日本時間の0時以降にお試しください。",
            headers={"Retry-After": str(retry_after)},
        )

    if not acquire_analysis_slot(current_user.id):
        logger.warning("Upload rejected (analysis in progress): user_id=%d", current_user.id)
        raise HTTPException(
            status_code=429,
            detail="分析中の音声があります。終わってから次をアップロードしてください。",
        )

    logger.info(
        "Upload received: user_id=%d filename=%s content_type=%s",
        current_user.id, audio_file.filename, audio_file.content_type,
    )

    try:
        tmp_path = await _stream_to_shared_volume(audio_file)
        task = analyze_audio_task.delay(tmp_path, song_title, artist_name, current_user.id)
    except Exception:
        # タスクに登録できなかったときは、分析中の印をここで外す（登録後は tasks.py の finally で外す）
        release_analysis_slot(current_user.id)
        raise

    # 数えるのはタスクに登録できたときだけ（弾かれたファイルは数えない）
    count_daily_upload(current_user.id)
    save_task_owner(task.id, current_user.id)
    logger.info("Task queued: task_id=%s user_id=%d", task.id, current_user.id)

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
    - 本人のタスクでなければ 404（他人のタスク・存在しないタスクを区別せず、存在を推測させない）
    """
    owner_id = get_task_owner(task_id)
    if owner_id != current_user.id:
        if owner_id is not None:
            logger.warning(
                "Forbidden task status access: requester_id=%d task_id=%s owner_id=%d",
                current_user.id, task_id, owner_id,
            )
        raise HTTPException(status_code=404, detail="分析タスクが見つかりません。")

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
        logger.warning(
            "Forbidden access attempt: requester_id=%d analysis_id=%d owner_id=%d",
            current_user.id, analysis_id, result.user_id,
        )
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
        logger.warning(
            "Upload rejected (invalid content-type): filename=%s content_type=%s",
            audio_file.filename, audio_file.content_type,
        )
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
        logger.warning("Upload rejected (file too small): bytes=%d", len(head))
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

    logger.warning("Upload rejected (magic bytes mismatch)")
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
                    logger.warning(
                        "Upload rejected (size exceeded): bytes=%d limit=%d",
                        total, _MAX_FILE_SIZE,
                    )
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
