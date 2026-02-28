"""
音声分析APIエンドポイント
音声ファイルのアップロードと分析結果の取得を担当する
"""

import uuid
import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException
from audio.analyzer import AudioAnalyzer

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

# 分析結果の一時保存（後でPostgreSQLに置き換える）
analysis_store: dict = {}

# アプリ起動時に1回だけインスタンス化（Demucsモデルのロードが重いため）
audio_analyzer = AudioAnalyzer()


@router.post("/upload")
async def upload_audio(
    audio_file: UploadFile = File(...),
    song_title: str = "",
    artist_name: str = "",
):
    """
    音声ファイルをアップロードして分析を開始する

    - audio_file: 音声ファイル（WAV/MP3/M4A）
    - song_title: 楽曲名（任意）
    - artist_name: アーティスト名（任意）
    """
    # ファイル形式の検証
    allowed_types = ["audio/wav", "audio/mpeg", "audio/mp4", "audio/x-m4a"]
    if audio_file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"対応していないファイル形式です。WAV/MP3/M4Aのみ対応しています。",
        )

    # ファイルサイズの検証（50MB以上は拒否）
    MAX_SIZE = 50 * 1024 * 1024  # 50MB
    content = await audio_file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="ファイルサイズが大きすぎます。50MB以下にしてください。",
        )

    # 一時ファイルに保存して分析
    analysis_id = str(uuid.uuid4())
    import os
    suffix = os.path.splitext(audio_file.filename)[1]  # .m4a / .mp3 / .wav を取得
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 音声分析を実行
        result = audio_analyzer.analyze(tmp_path)
        result["analysis_id"] = analysis_id
        result["song_title"] = song_title
        result["artist_name"] = artist_name

        # 結果を一時保存
        analysis_store[analysis_id] = result
    finally:
        # 音声ファイルは即時削除（著作権保護）
        os.unlink(tmp_path)

    return {"analysis_id": analysis_id, "status": "completed", "result": result}


@router.get("/{analysis_id}")
async def get_analysis(analysis_id: str):
    """
    分析結果を取得する

    - analysis_id: アップロード時に返されたID
    """
    if analysis_id not in analysis_store:
        raise HTTPException(status_code=404, detail="分析結果が見つかりません。")

    return analysis_store[analysis_id]