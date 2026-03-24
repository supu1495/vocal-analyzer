"""
認証APIエンドポイント
ユーザー登録・ログイン・プロフィール取得を担当する
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth_utils import (
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
        raise HTTPException(status_code=400, detail="パスワードは8文字以上で設定してください。")

    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="このメールアドレスはすでに登録されています。")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        disclaimer_accepted=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24,
    )
    return AuthResponse(user_id=user.id, email=user.email)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    ログイン

    - email / password が一致すればhttpOnly CookieにJWTを発行する
    """
    check_lockout(body.email)

    user = db.query(User).filter(User.email == body.email).first()
    if user is None or not verify_password(body.password, user.hashed_password):
        record_login_failure(body.email)
        raise HTTPException(status_code=401, detail="メールアドレスまたはパスワードが正しくありません。")

    clear_lockout(body.email)
    token = create_access_token(user.id)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24,
    )
    return AuthResponse(user_id=user.id, email=user.email)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    """ログイン中のユーザー情報を返す"""
    return UserResponse(
        user_id=current_user.id,
        email=current_user.email,
        disclaimer_accepted=current_user.disclaimer_accepted,
    )
