"""
認証APIエンドポイントのテスト（api/auth.py）

- client fixture: SQLiteDB + fakeredis + TestClient が揃った状態で提供される
- TestClient は base_url="https://testserver" を使用（secure Cookie の送受信に必要）
"""

import os

import jwt

from main import allowed_origins


# ── ヘルパー ────────────────────────────────────────────────────────────────

def _register(client, email="test@example.com", password="password123", invite_code=None):
    if invite_code is None:
        invite_code = os.environ["INVITE_CODE"]
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "invite_code": invite_code},
    )


def _login(client, email="test@example.com", password="password123"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# ── POST /register ──────────────────────────────────────────────────────────

def test_register_success(client):
    res = _register(client)
    assert res.status_code == 201
    assert res.json()["email"] == "test@example.com"
    assert "access_token" in res.cookies


def test_register_duplicate_email(client):
    _register(client)
    res = _register(client)
    assert res.status_code == 409


def test_register_wrong_invite_code(client):
    res = _register(client, invite_code="wrong-code")
    assert res.status_code == 403
    assert "access_token" not in res.cookies


def test_register_empty_invite_code(client):
    res = _register(client, invite_code="")
    assert res.status_code == 403


def test_register_fullwidth_invite_code(client):
    """全角文字でも 500（TypeError）にならず 403 を返す"""
    res = _register(client, invite_code="ｔｅｓｔ－ｉｎｖｉｔｅ－ｃｏｄｅ")
    assert res.status_code == 403


def test_register_without_invite_code_field(client):
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert res.status_code == 422


def test_register_rejected_when_invite_code_not_configured(client, monkeypatch):
    """INVITE_CODE が未設定なら、どんなコードでも登録できない"""
    monkeypatch.delenv("INVITE_CODE")
    res = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123", "invite_code": ""},
    )
    assert res.status_code == 403


def test_register_wrong_invite_code_does_not_reveal_existing_email(client):
    """招待コードが違えば、登録済みのメールアドレスでも 409 ではなく 403 を返す"""
    _register(client)
    res = _register(client, invite_code="wrong-code")
    assert res.status_code == 403


def test_register_short_password(client):
    res = _register(client, password="short")
    assert res.status_code == 400


# ── POST /login ─────────────────────────────────────────────────────────────

def test_login_success(client):
    _register(client)
    res = _login(client)
    assert res.status_code == 200
    assert res.json()["email"] == "test@example.com"
    assert "access_token" in res.cookies
    assert "httponly" in res.headers["set-cookie"].lower()


def test_login_cookie_is_samesite_lax(client):
    # 他サイトからのフォーム送信に Cookie を付けさせない（CSRF 対策）
    _register(client)
    res = _login(client)
    set_cookie = res.headers["set-cookie"].lower()
    assert "samesite=lax" in set_cookie
    assert "secure" in set_cookie


def test_login_wrong_password(client):
    _register(client)
    res = _login(client, password="wrongpassword")
    assert res.status_code == 401


def test_login_nonexistent_email(client):
    res = _login(client, email="nobody@example.com")
    assert res.status_code == 401


def test_login_same_error_message_for_wrong_password_and_nonexistent(client):
    """ユーザー列挙攻撃対策: 誤パスワードと存在しないメールのエラーメッセージが同一か確認"""
    _register(client)
    res_wrong_pw = _login(client, password="wrongpassword")
    res_no_user = _login(client, email="nobody@example.com")
    assert res_wrong_pw.json()["detail"] == res_no_user.json()["detail"]


def test_login_lockout_after_five_failures(client):
    _register(client)
    for _ in range(5):
        _login(client, password="wrong")
    res = _login(client, password="wrong")
    assert res.status_code == 429


def test_login_lockout_exposes_retry_after_to_frontend(client):
    # 本番はフロントと API が別オリジンなので、Retry-After が CORS で公開されていないと JS から読めない
    _register(client)
    for _ in range(5):
        _login(client, password="wrong")
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrong"},
        headers={"Origin": allowed_origins[0]},
    )
    assert res.status_code == 429
    assert 1 <= int(res.headers["retry-after"]) <= 15 * 60
    assert "retry-after" in res.headers["access-control-expose-headers"].lower()


def test_login_clears_lockout_on_success(client, fake_redis):
    _register(client)
    for _ in range(4):
        _login(client, password="wrong")
    _login(client)  # 正しいパスワードでログイン成功
    assert fake_redis.get("login_fail:test@example.com") is None


# ── GET /me ─────────────────────────────────────────────────────────────────

def test_me_authenticated(client):
    _register(client)
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    assert res.json()["email"] == "test@example.com"


def test_me_unauthenticated(client):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


# ── POST /logout ─────────────────────────────────────────────────────────────

def test_logout_clears_cookie(client):
    _register(client)
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 204
    # ログアウト後は /me が 401 を返す（Cookie が削除されているため）
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_cookie_attributes_match_login(client):
    # 削除用の Set-Cookie も発行時と同じ属性で返す
    _register(client)
    res = client.post("/api/v1/auth/logout")
    set_cookie = res.headers["set-cookie"].lower()
    assert "samesite=lax" in set_cookie
    assert "secure" in set_cookie
    assert "httponly" in set_cookie


def test_logout_revokes_token(client):
    # ログアウト前にコピーされたトークンは、ログアウト後に使っても通らない
    token = _register(client).cookies["access_token"]
    client.post("/api/v1/auth/logout")

    res = client.get("/api/v1/auth/me", headers={"Cookie": f"access_token={token}"})
    assert res.status_code == 401


def test_logout_stores_revoked_jti_until_token_expires(client, fake_redis):
    token = _register(client).cookies["access_token"]
    jti = jwt.decode(token, options={"verify_signature": False})["jti"]
    client.post("/api/v1/auth/logout")

    # 記録はトークンの有効期限（24時間）が切れるまで残る
    ttl = fake_redis.ttl(f"revoked_jti:{jti}")
    assert 1 <= ttl <= 60 * 60 * 24


def test_logout_does_not_revoke_other_sessions(client):
    # 別の端末（別のトークン）のログインは、こちらのログアウトでは無効にならない
    other_device_token = _register(client).cookies["access_token"]
    _login(client)  # この端末のトークン（Cookie が上書きされる）
    client.post("/api/v1/auth/logout")  # この端末のトークンだけを無効にする

    res = client.get("/api/v1/auth/me", headers={"Cookie": f"access_token={other_device_token}"})
    assert res.status_code == 200


def test_logout_without_cookie_returns_204(client):
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 204


def test_logout_with_invalid_cookie_returns_204(client):
    res = client.post("/api/v1/auth/logout", headers={"Cookie": "access_token=invalid.token.string"})
    assert res.status_code == 204
