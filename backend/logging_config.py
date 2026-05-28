"""
ロギング設定
アプリ全体でログフォーマットとレベルを統一する
main.py と celery_app.py から setup_logging() を呼び出す
"""

import logging
import os


def setup_logging() -> None:
    """ルートロガーを設定する。LOG_LEVEL 環境変数でレベルを切り替えられる（既定 INFO）"""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # uvicorn / celery が事前にハンドラを登録している場合があるので force=True で上書きする
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
