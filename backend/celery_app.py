"""
Celery アプリケーション設定
Redis をブローカー（タスクキュー）とバックエンド（結果保存）として使用する
"""

import os
from celery import Celery

from logging_config import setup_logging
from secret_check import validate_secrets

setup_logging()
validate_secrets()

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
    # 録音の上限（api/analysis.py の _MAX_DURATION_SECONDS = 10分）に合わせている（#13）
    # 分析は録音の約1.3倍かかる（5分13秒のライブ版で約408秒、2026-11-13 実測）。10分 × 1.3 ≒ 13分に余裕を足した
    # upload_limits.py の分析中の印の期限と、フロントの結果確認の長さは、この hard の値をもとに決めている
    task_soft_time_limit=16 * 60,  # 16分
    task_time_limit=17 * 60,       # 17分
)
