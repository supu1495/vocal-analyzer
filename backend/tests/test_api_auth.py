"""
認証APIエンドポイントのテスト（api/auth.py）

- client fixture: SQLiteDB + fakeredis + TestClient が揃った状態で提供される
- TestClient は base_url="https://testserver" を使用（secure Cookie の送受信に必要）
"""


# ── ヘルパー ────────────────────────────────────────────────────────────────

def _register(client, email="test@example.com", password="password123"):
    return client.post("/api/v1/auth/register", json={"email": email, "password": password})


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
