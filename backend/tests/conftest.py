"""
テスト共通設定・フィクスチャ

環境変数の設定は必ずアプリのimportより先に行う。
auth_utils.py がモジュールロード時に os.environ["SECRET_KEY"] を読むため。
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from database import Base, get_db
from main import app

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """テストごとにテーブルを作り直すインメモリDBセッション"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def fake_redis():
    """auth_utils._redis を fakeredis に差し替えるフィクスチャ"""
    fake_r = fakeredis.FakeRedis()

    # Lua スクリプト（INCR + EXPIRE）をネイティブ操作でシミュレートする
    def fake_eval(_script, _numkeys, *args):
        key = args[0]
        ttl = int(args[1])
        current = fake_r.incr(key)
        fake_r.expire(key, ttl)
        return current

    fake_r.eval = fake_eval

    with patch("auth_utils._redis", fake_r):
        yield fake_r


@pytest.fixture
def client(db, fake_redis):
    """get_db をテスト用 DB にすり替えた TestClient"""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()
