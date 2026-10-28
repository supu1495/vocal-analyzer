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


def test_decode_token_returns_payload_with_jti():
    token = create_access_token(user_id=42)
    payload = _decode_token(token)
    assert payload["sub"] == "42"
    assert payload["jti"]  # ログアウト時の無効化に使う ID が入っている


def test_create_access_token_jti_is_unique():
    # 同じユーザーでもトークンごとに別の jti（片方を無効化しても、もう片方に影響しない）
    jti_1 = _decode_token(create_access_token(user_id=1))["jti"]
    jti_2 = _decode_token(create_access_token(user_id=1))["jti"]
    assert jti_1 != jti_2


def test_decode_token_without_jti_raises_401():
    # ブラックリスト導入前の形式（jti なし）は無効化できないため拒否する
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    token_without_jti = jwt.encode(
        {"sub": "1", "exp": expire},
        auth_utils.SECRET_KEY,
        algorithm=auth_utils.ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc_info:
        _decode_token(token_without_jti)
    assert exc_info.value.status_code == 401


def test_decode_token_tampered_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        _decode_token("invalid.token.string")
    assert exc_info.value.status_code == 401


def test_decode_token_expired_raises_401():
    expire = datetime.now(timezone.utc) - timedelta(minutes=5)
    # jti を入れて「期限切れ」だけが拒否の理由になるようにする
    expired_token = jwt.encode(
        {"sub": "1", "exp": expire, "jti": "expired-token-jti"},
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


def test_check_lockout_returns_retry_after(fake_redis):
    email = "test@example.com"
    for _ in range(5):
        record_login_failure(email)

    with pytest.raises(HTTPException) as exc_info:
        check_lockout(email)
    # 残り秒数は Redis の TTL。ロック直後なので 1〜900秒（15分）の範囲に入る
    retry_after = int(exc_info.value.headers["Retry-After"])
    assert 1 <= retry_after <= 15 * 60


def test_check_lockout_retry_after_falls_back_when_no_ttl(fake_redis):
    # TTL が取れない（期限なしのキー）場合はロック時間の上限（15分）を返す
    email = "test@example.com"
    fake_redis.set(f"login_fail:{email}", 5)

    with pytest.raises(HTTPException) as exc_info:
        check_lockout(email)
    assert exc_info.value.headers["Retry-After"] == str(15 * 60)


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
