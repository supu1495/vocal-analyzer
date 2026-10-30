"""
アップロードの使いすぎ防止
自宅PCで重い分析（Demucs）を回すため、1人が分析を大量に流せないようにする

API（受け付け時）と Celery worker（分析終了時）の両方から使うため、
認証まわり（auth_utils.py）とは分けている。worker に JWT や FastAPI の処理を読み込ませないため
"""

import os

import redis

# 分析中の印を自動で消すまでの時間
# worker が強制終了されると tasks.py の finally が動かず印が残るため、期限で消えるようにする
# タスクの時間制限（celery_app.py の task_time_limit = 10分）＋順番待ちの余裕
_ACTIVE_TASK_TTL_SECONDS = 60 * 20

_redis = redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379"))


def _active_task_key(user_id: int) -> str:
    return f"active_task:{user_id}"


def acquire_analysis_slot(user_id: int) -> bool:
    """分析中の印を付ける。すでに分析中なら False

    SET NX（キーが無いときだけ書く）で、確認と書き込みを1回で行う。
    2回に分けると、同時に2件送られたときに両方通ってしまうため
    """
    return bool(_redis.set(_active_task_key(user_id), 1, nx=True, ex=_ACTIVE_TASK_TTL_SECONDS))


def release_analysis_slot(user_id: int) -> None:
    """分析中の印を外す（分析が終わったとき・受け付けの途中で失敗したとき）

    要確認: 順番待ちが期限（20分）を超えると、印が先に消えて2件目を受け付け、
    その後1件目の終了時に2件目の印まで外してしまう。今の利用規模では起きにくいため受け入れている
    """
    _redis.delete(_active_task_key(user_id))
