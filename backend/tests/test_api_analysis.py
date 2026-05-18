"""
分析APIエンドポイントのテスト（api/analysis.py）

Phase 8 以降はアップロードが非同期（Celery タスク）になっているため
- POST /upload はタスク登録 → task_id 返却をテスト
- GET /analysis/status/{task_id} は AsyncResult をモックして動作確認
- GET /analysis/{id} は DB に直接レコードを作成して動作確認
"""

import io
import wave
from unittest.mock import patch, MagicMock

from models import AnalysisResult, User


# ── ヘルパー ───────────────────────────────────────────────────────────────────

def _create_minimal_wav() -> bytes:
    """Pythonの標準waveモジュールで作る最小WAVファイル（ディスクを使わずメモリ上で生成）"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(44100)
        wav_file.writeframes(b"\x00" * 200)
    return buf.getvalue()


def _register_and_login(client, email="test@example.com", password="password123"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})


def _upload(client, filename="test.wav", content_type="audio/wav", content=None):
    if content is None:
        content = _create_minimal_wav()
    return client.post(
        "/api/v1/analysis/upload",
        files={"audio_file": (filename, content, content_type)},
    )


def _create_analysis_record(db, user_id: int) -> AnalysisResult:
    """テスト用に DB にダミーの分析結果を直接作成する"""
    record = AnalysisResult(
        user_id=user_id,
        song_title="テスト曲",
        artist_name="",
        pitch_accuracy=75.0,
        rhythm_score=60.0,
        techniques={},
        vocal_range={"lowest": None, "highest": None, "range_semitones": 0},
        feedback="テストフィードバック",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ── POST /api/v1/analysis/upload ──────────────────────────────────────────────

def test_upload_unauthenticated(client):
    res = _upload(client)
    assert res.status_code == 401


def test_upload_invalid_file_type(client):
    _register_and_login(client)
    res = _upload(client, filename="test.txt", content_type="text/plain", content=b"hello")
    assert res.status_code == 400


def test_upload_file_too_large(client):
    _register_and_login(client)
    oversized = b"\x00" * (50 * 1024 * 1024 + 1)
    res = _upload(client, content=oversized)
    assert res.status_code == 400


def test_upload_success(client):
    _register_and_login(client)
    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    with patch("api.analysis.analyze_audio_task.delay", return_value=mock_task):
        res = _upload(client)
    assert res.status_code == 200
    assert res.json()["task_id"] == "test-task-id"
    assert res.json()["status"] == "processing"


# ── GET /api/v1/analysis/status/{task_id} ─────────────────────────────────────

def test_get_analysis_status_unauthenticated(client):
    res = client.get("/api/v1/analysis/status/some-task-id")
    assert res.status_code == 401


def test_get_analysis_status_success(client):
    _register_and_login(client)
    with patch("api.analysis.AsyncResult") as mock_async_result:
        mock_async_result.return_value.status = "SUCCESS"
        mock_async_result.return_value.result = 42
        res = client.get("/api/v1/analysis/status/some-task-id")
    assert res.status_code == 200
    assert res.json() == {"status": "SUCCESS", "analysis_id": 42}


def test_get_analysis_status_pending(client):
    _register_and_login(client)
    with patch("api.analysis.AsyncResult") as mock_async_result:
        mock_async_result.return_value.status = "PENDING"
        res = client.get("/api/v1/analysis/status/some-task-id")
    assert res.status_code == 200
    assert res.json()["status"] == "PENDING"


# ── GET /api/v1/analysis/{analysis_id} ────────────────────────────────────────

def test_get_analysis_success(client, db):
    _register_and_login(client)
    user = db.query(User).first()
    record = _create_analysis_record(db, user.id)

    res = client.get(f"/api/v1/analysis/{record.id}")
    assert res.status_code == 200
    assert res.json()["analysis_id"] == record.id


def test_get_analysis_unauthenticated(client, db):
    _register_and_login(client)
    user = db.query(User).first()
    record = _create_analysis_record(db, user.id)

    client.post("/api/v1/auth/logout")
    res = client.get(f"/api/v1/analysis/{record.id}")
    assert res.status_code == 401


def test_get_analysis_not_found(client):
    _register_and_login(client)
    res = client.get("/api/v1/analysis/99999")
    assert res.status_code == 404


def test_get_analysis_other_user_returns_403(client, db):
    # User A: 登録してレコードを作成
    _register_and_login(client, email="user_a@example.com")
    user_a = db.query(User).filter(User.email == "user_a@example.com").first()
    record = _create_analysis_record(db, user_a.id)

    # User B: 登録して User A のレコードにアクセスする
    client.post("/api/v1/auth/logout")
    _register_and_login(client, email="user_b@example.com")
    res = client.get(f"/api/v1/analysis/{record.id}")
    assert res.status_code == 403


# ── GET /api/v1/analysis/user/statistics ──────────────────────────────────────

def test_get_statistics_authenticated(client):
    _register_and_login(client)
    res = client.get("/api/v1/analysis/user/statistics")
    assert res.status_code == 200
    assert "history" in res.json()
    assert "total_count" in res.json()


def test_get_statistics_unauthenticated(client):
    res = client.get("/api/v1/analysis/user/statistics")
    assert res.status_code == 401
