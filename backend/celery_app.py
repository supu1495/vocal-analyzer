"""
Celery アプリケーション設定
Redis をブローカー（タスクキュー）とバックエンド（結果保存）として使用する
"""

import os
from celery import Celery

# auth_utils.py と同じパターンで REDIS_URL を取得する
# ブローカー（タスクの受け渡し）: DB0
# バックエンド（タスクの結果保存）: DB1 — ブローカーと混在しないよう別DBを使う
_redis_url = os.environ.get("REDIS_URL", "redis://redis:6379")

celery_app = Celery(
    "vocal_analyzer",
    broker=f"{_redis_url}/0",
    backend=f"{_redis_url}/1",
    include=["tasks"],  # tasks.py のタスクを Worker に登録する
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,  # 起動時の接続リトライを明示的に有効化
    # タスクが固まったときに永遠に走り続けないように時間制限を入れる
    # soft: SoftTimeLimitExceeded 例外を発生（tasks.py の try/finally で後片付け可能）
    # hard: プロセス強制kill（後片付けなし）
    # フロントのポーリング上限（120回 × 5秒 = 10分）に合わせている
    task_soft_time_limit=540,  # 9分
    task_time_limit=600,       # 10分
)
