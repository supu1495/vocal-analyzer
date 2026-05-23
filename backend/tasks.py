"""
Celery タスク定義
音声分析の重い処理をバックグラウンドで実行する
"""

import os

from celery_app import celery_app
from database import SessionLocal
from audio.analyzer import AudioAnalyzer
from models import AnalysisResult

# fork 後の各 worker プロセスで初回タスク実行時に遅延初期化する
# モジュールレベルで初期化すると PyTorch が fork 前に読み込まれデッドロックする
_audio_analyzer: AudioAnalyzer | None = None


def _get_analyzer() -> AudioAnalyzer:
    global _audio_analyzer
    if _audio_analyzer is None:
        _audio_analyzer = AudioAnalyzer()
    return _audio_analyzer


@celery_app.task
def analyze_audio_task(
    tmp_path: str,
    song_title: str,
    artist_name: str,
    user_id: int,
) -> int:
    """
    音声ファイルを分析してDBに保存する

    Args:
        tmp_path: 共有ボリューム上の一時ファイルパス
        song_title: 楽曲名
        artist_name: アーティスト名
        user_id: ログインユーザーのID

    Returns:
        保存した AnalysisResult の ID
    """
    db = SessionLocal()
    try:
        result = _get_analyzer().analyze(tmp_path)
        score_matrix = result.get("score_matrix", {})

        record = AnalysisResult(
            user_id=user_id,
            song_title=song_title,
            artist_name=artist_name,
            pitch_accuracy=result.get("pitch_accuracy"),
            rhythm_score=result.get("rhythm_score"),
            techniques=result.get("techniques"),
            vocal_range=result.get("vocal_range"),
            total_score=score_matrix.get("total_score"),
            faithfulness_score=score_matrix.get("faithfulness_score"),
            technique_score=score_matrix.get("technique_score"),
            naturalness_penalty=score_matrix.get("naturalness_penalty"),
            feedback=result.get("feedback"),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record.id
    except Exception:
        # commit 前後で例外が出てもセッションを安全な状態に戻す
        db.rollback()
        raise
    finally:
        # 著作権保護のため分析完了後に即時削除する
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        db.close()
