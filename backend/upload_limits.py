"""
アップロードの使いすぎ防止
自宅PCで重い分析（Demucs）を回すため、1人が分析を大量に流せないようにする

API（受け付け時）と Celery worker（分析終了時）の両方から使うため、
認証まわり（auth_utils.py）とは分けている。worker に JWT や FastAPI の処理を読み込ませないため
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import redis

# 分析中の印を自動で消すまでの時間
# worker が強制終了されると tasks.py の finally が動かず印が残るため、期限で消えるようにする
# タスクの時間制限（celery_app.py の task_time_limit = 10分）＋順番待ちの余裕
_ACTIVE_TASK_TTL_SECONDS = 60 * 20

# 1日のアップロード回数は日本時間の0時で区切る（コンテナのタイムゾーンは UTC のため明示する）
_JST = ZoneInfo("Asia/Tokyo")
_DEFAULT_DAILY_UPLOAD_LIMIT = 10
# 回数のキーには日付が入っており、日付が変われば別のキーになる。期限は古いキーの掃除のためだけに付ける
_DAILY_COUNT_TTL_SECONDS = 60 * 60 * 24 * 2

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


def daily_upload_limit() -> int:
    """1日に受け付けるアップロードの回数（環境変数 DAILY_UPLOAD_LIMIT。未設定なら10）"""
    return int(os.environ.get("DAILY_UPLOAD_LIMIT", _DEFAULT_DAILY_UPLOAD_LIMIT))


def _now_jst() -> datetime:
    """今の日本時間（テストで時刻を固定するために関数にしている）"""
    return datetime.now(_JST)


def _daily_count_key(user_id: int, now: datetime) -> str:
    return f"upload_count:{user_id}:{now.date().isoformat()}"


def _seconds_until_next_midnight(now: datetime) -> int:
    """次の0時までの秒数。端数は切り上げる（切り捨てると解除前の時刻を指してしまうため）"""
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    remaining = next_midnight - now
    return remaining.days * 86400 + remaining.seconds + (1 if remaining.microseconds else 0)


def daily_limit_retry_after(user_id: int) -> int | None:
    """今日の回数が上限に達していれば、次の日本時間0時までの秒数を返す。まだ受け付けられるなら None"""
    now = _now_jst()
    count = _redis.get(_daily_count_key(user_id, now))
    if count is None or int(count) < daily_upload_limit():
        return None
    return _seconds_until_next_midnight(now)


def count_daily_upload(user_id: int) -> None:
    """今日のアップロード回数を1増やす（タスクに登録できたときに呼ぶ）

    pipeline(transaction=True) で INCR と EXPIRE をまとめて実行し、期限なしのキーが残らないようにする
    """
    key = _daily_count_key(user_id, _now_jst())
    with _redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, _DAILY_COUNT_TTL_SECONDS)
        pipe.execute()
