"""
分析タスクの失敗理由の受け渡し
Celery worker（失敗時に書く）と API（status 確認で読む）の両方から使う

worker に JWT や FastAPI の処理を読み込ませないため、auth_utils.py とは分けている（upload_limits.py と同じ理由）
"""

import os

import redis

# タスクの持ち主の記録（auth_utils.py の _TASK_OWNER_TTL_SECONDS）と同じ期間だけ残す
_FAILURE_REASON_TTL_SECONDS = 60 * 60 * 24

_redis = redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379"))


def _failure_reason_key(task_id: str) -> str:
    return f"task_failure:{task_id}"


def save_failure_reason(task_id: str, reason: str) -> None:
    """失敗理由を記録する（audio/errors.py の INVALID_FORMAT などの値）"""
    _redis.set(_failure_reason_key(task_id), reason, ex=_FAILURE_REASON_TTL_SECONDS)


def get_failure_reason(task_id: str) -> str | None:
    """失敗理由を返す。記録が無い（worker が強制終了された・期限切れ）なら None"""
    reason = _redis.get(_failure_reason_key(task_id))
    return reason.decode() if reason is not None else None
