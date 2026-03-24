"""
認証ユーティリティ
JWT生成・検証、パスワードハッシュ化を担当する
"""

import os
from datetime import datetime, timedelta, timezone

import redis
from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import User

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24時間

# ログイン失敗ロックアウト設定
_MAX_FAILURES = 5         # この回数失敗するとロック
_LOCKOUT_SECONDS = 60 * 15  # ロック持続時間: 15分

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_redis = redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379"))


def check_lockout(email: str) -> None:
    """ロック中なら 429 を raise する"""
    count = _redis.get(f"login_fail:{email}")
    if count and int(count) >= _MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="ログイン試行回数が上限を超えました。15分後に再試行してください。",
        )


def record_login_failure(email: str) -> None:
    """失敗カウントをインクリメントし、TTLを（再）セットする"""
    key = f"login_fail:{email}"
    _redis.incr(key)
    _redis.expire(key, _LOCKOUT_SECONDS)


def clear_lockout(email: str) -> None:
    """ログイン成功時に失敗カウントを削除する"""
    _redis.delete(f"login_fail:{email}")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> int:
    """トークンをデコードしてuser_idを返す。不正なら401を raise する"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
        return user_id
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
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
    user_id = _decode_token(access_token)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ユーザーが存在しません。")
    return user
