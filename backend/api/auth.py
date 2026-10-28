"""
認証APIエンドポイント
ユーザー登録・ログイン・プロフィール取得を担当する
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from auth_utils import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    DUMMY_HASH,
    check_lockout,
    clear_lockout,
    create_access_token,
    get_current_user,
    hash_password,
    record_login_failure,
    verify_password,
)
from database import get_db
from models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_AUTH_COOKIE_NAME = "access_token"

# SameSite=Lax: フロント（vocal-analyzer.supu361.dev）と API（vocal-api.supu361.dev）は
# 同じサイト（supu361.dev）なので fetch に Cookie が付く。他サイトからのフォーム送信には付かない（CSRF 対策）
_AUTH_COOKIE_ATTRIBUTES = {
    "httponly": True,
    "secure": True,
    "samesite": "lax",
}


# ── スキーマ ──────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: int
    email: str


class UserResponse(BaseModel):
    user_id: int
    email: str
    disclaimer_accepted: bool


# ── エンドポイント ────────────────────────────────────────────────────────────


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    """
    新規ユーザー登録

    - email: メールアドレス（一意）
    - password: パスワード（8文字以上推奨）
    """
    if len(body.password) < 8:
        logger.info("Register rejected (weak password): email=%s", body.email)
        raise HTTPException(status_code=400, detail="パスワードは8文字以上で設定してください。")

    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        logger.info("Register rejected (duplicate email): email=%s", body.email)
        raise HTTPException(status_code=409, detail="このメールアドレスはすでに登録されています。")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        disclaimer_accepted=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("User registered: user_id=%d email=%s", user.id, user.email)

    _set_auth_cookie(response, create_access_token(user.id))
    return AuthResponse(user_id=user.id, email=user.email)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    ログイン

    - email / password が一致すればhttpOnly CookieにJWTを発行する
    """
    check_lockout(body.email)

    user = db.query(User).filter(User.email == body.email).first()
    # タイミング攻撃対策: ユーザーが存在しない場合もダミーハッシュで verify を実行し、
    # レスポンス時間の差からメールアドレスの存在を推測されないようにする
    hash_to_check = user.hashed_password if user is not None else DUMMY_HASH
    password_valid = verify_password(body.password, hash_to_check)

    if not password_valid or user is None:
        record_login_failure(body.email)
        logger.warning("Login failed: email=%s", body.email)
        raise HTTPException(status_code=401, detail="メールアドレスまたはパスワードが正しくありません。")

    clear_lockout(body.email)
    logger.info("Login success: user_id=%d email=%s", user.id, user.email)
    _set_auth_cookie(response, create_access_token(user.id))
    return AuthResponse(user_id=user.id, email=user.email)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    """ログイン中のユーザー情報を返す"""
    return UserResponse(
        user_id=current_user.id,
        email=current_user.email,
        disclaimer_accepted=current_user.disclaimer_accepted,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    """ログアウト — httpOnly CookieのJWTを削除する"""
    # 発行時と属性を揃えて、ブラウザに同じ Cookie の削除だと確実に扱わせる
    response.delete_cookie(key=_AUTH_COOKIE_NAME, **_AUTH_COOKIE_ATTRIBUTES)


# ── プライベート関数 ──────────────────────────────────────────────────────────


def _set_auth_cookie(response: Response, token: str) -> None:
    """JWT を httpOnly Cookie にセットする（register / login 共通）"""
    response.set_cookie(
        key=_AUTH_COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **_AUTH_COOKIE_ATTRIBUTES,
    )
