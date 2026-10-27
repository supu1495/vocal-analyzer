"""
起動時の秘密情報チェック
.env が初期値のまま・空・短すぎる場合に、理由をログに出して起動を止める
main.py と celery_app.py から validate_secrets() を呼び出す
"""

import logging
import os
import sys
from urllib.parse import urlparse

from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)

# RFC 7518 §3.2: HS256 の鍵は 256bit（32バイト）以上
_MIN_SECRET_KEY_LENGTH = 32
_MIN_PASSWORD_LENGTH = 16

# .env.example に書いてある初期値。これらのまま起動させない
_PLACEHOLDER_VALUES = {"your-secret-key-here", "changeme"}


def _check_value(name: str, value: str | None, min_length: int) -> str | None:
    """問題があれば理由の文字列を、問題なければ None を返す"""
    if not value:
        return f"{name} が空です"
    if value in _PLACEHOLDER_VALUES:
        return f"{name} が .env.example の初期値のままです"
    if len(value) < min_length:
        return f"{name} が短すぎます（{len(value)}文字。{min_length}文字以上にしてください）"
    return None


def _database_password() -> str | None:
    """DATABASE_URL からパスワード部分を取り出す（backend には POSTGRES_PASSWORD が直接渡らないため）"""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return None
    return make_url(database_url).password


def _redis_password() -> str | None:
    """REDIS_URL（redis://:<パスワード>@redis:6379）からパスワード部分を取り出す"""
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None
    return urlparse(redis_url).password


def find_secret_problems() -> list[str]:
    """すべての項目を調べ、問題の一覧を返す（1つずつ直して再起動しなくて済むよう全部集める）"""
    checks = [
        _check_value("SECRET_KEY", os.environ.get("SECRET_KEY"), _MIN_SECRET_KEY_LENGTH),
        _check_value("POSTGRES_PASSWORD", _database_password(), _MIN_PASSWORD_LENGTH),
        _check_value("REDIS_PASSWORD", _redis_password(), _MIN_PASSWORD_LENGTH),
    ]
    return [problem for problem in checks if problem is not None]


def validate_secrets() -> None:
    """問題が1つでもあれば理由をログに出してプロセスを終了する"""
    problems = find_secret_problems()
    if not problems:
        return

    for problem in problems:
        logger.error("秘密情報の設定に問題があります: %s", problem)
    logger.error("値の生成方法・変更手順は .env.example を参照してください。起動を中止します")
    sys.exit(1)
