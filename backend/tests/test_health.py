"""
/health のテスト（main.py）

フロントはここで返るコミットIDを自分のビルド元と比べ、違っていたら警告を出す
"""


def test_health_returns_commit(client, monkeypatch):
    commit = "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setenv("GIT_COMMIT", commit)

    res = client.get("/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok", "commit": commit}


def test_health_returns_unknown_without_commit(client, monkeypatch):
    # ビルド時にコミットIDを渡し忘れたときは unknown（フロントはこれも警告の対象にする）
    monkeypatch.delenv("GIT_COMMIT", raising=False)

    res = client.get("/health")

    assert res.json()["commit"] == "unknown"
