"""
認証ユーティリティ
JWT生成・検証、パスワードハッシュ化を担当する
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import redis
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User

logger = logging.getLogger(__name__)

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24時間

# ログイン失敗ロックアウト設定
_MAX_FAILURES = 5         # この回数失敗するとロック
_LOCKOUT_SECONDS = 60 * 15  # ロック持続時間: 15分

# 分析タスクの持ち主を覚えておく期間。Celery の結果保存期間（result_expires の初期値 = 1日）に揃える
_TASK_OWNER_TTL_SECONDS = 60 * 60 * 24

_redis = redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379"))

# タイミング攻撃対策: ユーザーが存在しない場合でも verify_password を実行するためのダミーハッシュ
# モジュールロード時に1回だけ生成する
DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode()

# INCR と EXPIRE を atomic に実行する Lua スクリプト
# INCR と EXPIRE の間にクラッシュが発生しても TTL が失われない
_INCR_WITH_EXPIRE_LUA = """
local current = redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[1])
return current
"""


def check_lockout(email: str) -> None:
    """ログイン失敗が規定回数（5回）に達している場合、リクエストを拒否して429エラーを返す
    429 = Too Many Requests（リクエスト過多）を意味するHTTPステータスコード
    Retry-After ヘッダーで解除までの残り秒数を返す（フロントが再読み込み後も制限表示を復元するため）
    """
    key = f"login_fail:{email}"
    count = _redis.get(key)
    if count and int(count) >= _MAX_FAILURES:
        retry_after = _lockout_remaining_seconds(key)
        logger.warning(
            "Lockout triggered: email=%s failure_count=%d retry_after=%d",
            email, int(count), retry_after,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ログイン試行回数が上限を超えました。しばらくしてから再試行してください。",
            headers={"Retry-After": str(retry_after)},
        )


def _lockout_remaining_seconds(key: str) -> int:
    """ロック解除までの残り秒数。TTL が取れない（-1: 期限なし / -2: キーなし）ときはロック時間の上限を返す"""
    ttl = _redis.ttl(key)
    return ttl if ttl > 0 else _LOCKOUT_SECONDS


def record_login_failure(email: str) -> None:
    """失敗カウントをインクリメントし、TTLを atomic にセットする"""
    key = f"login_fail:{email}"
    _redis.eval(_INCR_WITH_EXPIRE_LUA, 1, key, _LOCKOUT_SECONDS)


def clear_lockout(email: str) -> None:
    """ログイン成功時に失敗カウントを削除する"""
    _redis.delete(f"login_fail:{email}")


def save_task_owner(task_id: str, user_id: int) -> None:
    """分析タスクの持ち主を記録する（status 確認で本人のタスクか照合するため）"""
    _redis.set(f"task_owner:{task_id}", user_id, ex=_TASK_OWNER_TTL_SECONDS)


def get_task_owner(task_id: str) -> int | None:
    """分析タスクの持ち主の user_id を返す。記録が無い（存在しない・期限切れ）なら None"""
    owner = _redis.get(f"task_owner:{task_id}")
    return int(owner) if owner is not None else None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # jti（JWT ID）: トークンごとの一意な ID。ログアウト時にこの ID で無効化する
    payload = {"sub": str(user_id), "exp": expire, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def revoke_access_token(token: str) -> None:
    """ログアウト時にトークンを無効リストへ入れる。トークンが不正・期限切れなら何もしない

    記録はトークン自体の期限が切れるまで残す（期限切れのトークンはどのみち通らないため）
    """
    try:
        payload = _decode_token(token)
    except HTTPException:
        return

    remaining_seconds = payload["exp"] - int(datetime.now(timezone.utc).timestamp())
    if remaining_seconds > 0:
        _redis.set(f"revoked_jti:{payload['jti']}", 1, ex=remaining_seconds)
        logger.info("Token revoked: user_id=%s jti=%s", payload["sub"], payload["jti"])


def _is_token_revoked(jti: str) -> bool:
    return _redis.exists(f"revoked_jti:{jti}") > 0


def _decode_token(token: str) -> dict:
    """署名・有効期限と必須項目（sub / exp / jti）を検証して payload を返す。不正なら401を raise する

    jti の無いトークン（ブラックリスト導入前に発行されたもの）は無効化できないため拒否する
    """
    try:
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            options={"require": ["sub", "exp", "jti"]},
        )
        int(payload["sub"])  # user_id として使えるかを先に確かめる
        return payload
    except (jwt.InvalidTokenError, ValueError) as e:
        logger.warning("JWT validation failed: %s", e)
        raise _invalid_credentials_error()


def _invalid_credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="認証情報が無効です。再ログインしてください。",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """ログイン必須エンドポイント用 Dependency。未認証なら 401 を返す"""
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です。",
        )
    payload = _decode_token(access_token)
    if _is_token_revoked(payload["jti"]):
        logger.warning("Revoked token used: user_id=%s jti=%s", payload["sub"], payload["jti"])
        raise _invalid_credentials_error()

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ユーザーが存在しません。")
    return user
