"""
音声分析APIエンドポイント
音声ファイルのアップロード・分析結果の取得・統計情報の取得を担当する
"""

import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from audio.analyzer import AudioAnalyzer
from auth_utils import get_current_user
from database import get_db
from models import AnalysisResult, User

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

# アプリ起動時に1回だけインスタンス化（Demucsモデルのロードが重いため）
audio_analyzer = AudioAnalyzer()


@router.post("/upload")
async def upload_audio(
    audio_file: UploadFile = File(...),
    song_title: str = "",
    artist_name: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    音声ファイルをアップロードして分析し、結果をDBに保存する

    - audio_file: 音声ファイル（WAV/MP3/M4A）
    - song_title: 楽曲名（任意）
    - artist_name: アーティスト名（任意）
    """
    _validate_audio_file(audio_file)

    content = await audio_file.read()
    _validate_file_size(content)

    analysis_data = _run_analysis(audio_file.filename, content, song_title, artist_name)

    saved = _save_to_db(db, song_title, artist_name, analysis_data, current_user.id)

    return {
        "analysis_id": saved.id,
        "status": "completed",
        "result": analysis_data,
    }


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

    - analysis_id: アップロード時に返されたID
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
            "feedback": result.feedback,
        },
    }


# ── プライベート関数 ──────────────────────────────────────────────────────────


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


def _save_to_db(
    db: Session, song_title: str, artist_name: str, analysis_data: dict, user_id: int
) -> AnalysisResult:
    """分析結果をPostgreSQLに保存してcommitする"""
    record = AnalysisResult(
        user_id=user_id,
        song_title=song_title,
        artist_name=artist_name,
        pitch_accuracy=analysis_data.get("pitch_accuracy"),
        rhythm_score=analysis_data.get("rhythm_score"),
        techniques=analysis_data.get("techniques"),
        vocal_range=analysis_data.get("vocal_range"),
        feedback=analysis_data.get("feedback"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _calculate_growth_rate(pitch_values: list[float]) -> int:
    """
    最初と最後のピッチスコアから成長率（%）を計算する
    データが2件未満の場合は0を返す
    """
    if len(pitch_values) < 2 or pitch_values[0] == 0:
        return 0
    growth = ((pitch_values[-1] - pitch_values[0]) / pitch_values[0]) * 100
    return round(growth)
