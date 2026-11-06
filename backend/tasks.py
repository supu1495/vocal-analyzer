"""
Celery タスク定義
音声分析の重い処理をバックグラウンドで実行する
"""

import logging
import os
import time

from celery.exceptions import SoftTimeLimitExceeded  # 時間切れ（soft time limit）を失敗理由 timeout に分けるため

from celery_app import celery_app
from audio.errors import INTERNAL, TIMEOUT, AnalysisError
from database import SessionLocal
from audio.analyzer import AudioAnalyzer
from models import AnalysisResult
from task_failures import save_failure_reason
from upload_limits import release_analysis_slot

logger = logging.getLogger(__name__)

# fork 後の各 worker プロセスで初回タスク実行時に遅延初期化する
# モジュールレベルで初期化すると PyTorch が fork 前に読み込まれデッドロックする
_audio_analyzer: AudioAnalyzer | None = None


def _get_analyzer() -> AudioAnalyzer:
    global _audio_analyzer
    if _audio_analyzer is None:
        _audio_analyzer = AudioAnalyzer()
    return _audio_analyzer


# bind=True: 1つ目の引数（self）からこのタスク自身の task_id を取れるようにする（失敗理由の記録に使う）
@celery_app.task(bind=True)
def analyze_audio_task(
    self,
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
    logger.info("Task started: user_id=%d song=%s", user_id, song_title)
    start = time.time()
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
        elapsed = time.time() - start
        logger.info(
            "Task completed: user_id=%d analysis_id=%d elapsed=%.2fs",
            user_id, record.id, elapsed,
        )
        return record.id
    except Exception as e:
        # commit 前後で例外が出てもセッションを安全な状態に戻す
        db.rollback()
        elapsed = time.time() - start
        reason = _classify_failure(e)
        logger.exception(
            "Task failed: user_id=%d reason=%s elapsed=%.2fs", user_id, reason, elapsed,
        )
        # タスクを直接呼んだとき（テストなど）は task_id が無いので記録しない
        if self.request.id is not None:
            save_failure_reason(self.request.id, reason)
        raise
    finally:
        # 著作権保護のため分析完了後に即時削除する
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        db.close()
        # 次のアップロードを受け付けられるようにする
        release_analysis_slot(user_id)


def _classify_failure(error: Exception) -> str:
    """例外から失敗理由（audio/errors.py の値）を決める

    hard time limit（task_time_limit）で強制終了されたときはここまで来ないため、理由は記録されない
    （status API では internal として返す）
    """
    if isinstance(error, AnalysisError):
        return error.reason
    if isinstance(error, SoftTimeLimitExceeded):
        return TIMEOUT
    return INTERNAL
