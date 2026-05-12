"""
auth_utils.py のユニットテスト

- パスワード・JWT のテスト: DB・Redis 不要（純粋関数）
- ロックアウトのテスト: fake_redis fixture を使用
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

import auth_utils
from auth_utils import (
    _decode_token,
    check_lockout,
    clear_lockout,
    create_access_token,
    hash_password,
    record_login_failure,
    verify_password,
)


# ── パスワード ──────────────────────────────────────────────────────────────

def test_hash_password_returns_different_string():
    hashed = hash_password("mysecret")
    assert hashed != "mysecret"


def test_verify_password_correct():
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("mysecret")
    assert verify_password("wrongpassword", hashed) is False


# ── JWT ─────────────────────────────────────────────────────────────────────

def test_create_access_token_returns_string():
    token = create_access_token(user_id=1)
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_token_returns_user_id():
    token = create_access_token(user_id=42)
    user_id = _decode_token(token)
    assert user_id == 42


def test_decode_token_tampered_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        _decode_token("invalid.token.string")
    assert exc_info.value.status_code == 401


def test_decode_token_expired_raises_401():
    expire = datetime.now(timezone.utc) - timedelta(minutes=5)
    expired_token = jwt.encode(
        {"sub": "1", "exp": expire},
        auth_utils.SECRET_KEY,
        algorithm=auth_utils.ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc_info:
        _decode_token(expired_token)
    assert exc_info.value.status_code == 401


# ── ロックアウト（fake_redis 使用）──────────────────────────────────────────

def test_check_lockout_not_locked(fake_redis):
    # 失敗カウントがない状態では例外が発生しない（発生したらテスト失敗）
    check_lockout("test@example.com")


def test_check_lockout_not_raised_at_four_failures(fake_redis):
    email = "test@example.com"
    for _ in range(4):
        record_login_failure(email)
    # 4回ではロックされない（5回からロック）
    check_lockout(email)


def test_check_lockout_raises_429_when_locked(fake_redis):
    email = "test@example.com"
    for _ in range(5):
        record_login_failure(email)

    with pytest.raises(HTTPException) as exc_info:
        check_lockout(email)
    assert exc_info.value.status_code == 429


def test_record_login_failure_increments_count(fake_redis):
    email = "test@example.com"
    record_login_failure(email)
    record_login_failure(email)

    count = int(fake_redis.get(f"login_fail:{email}"))
    assert count == 2


def test_clear_lockout_removes_count(fake_redis):
    email = "test@example.com"
    for _ in range(5):
        record_login_failure(email)

    clear_lockout(email)

    assert fake_redis.get(f"login_fail:{email}") is None
