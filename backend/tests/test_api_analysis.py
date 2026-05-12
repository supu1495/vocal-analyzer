"""
分析APIエンドポイントのテスト（api/analysis.py）

audio_analyzer.analyze() は Crepe + librosa を使うため、
テストでは unittest.mock.patch で差し替えてモックデータを返す。
"""

import io
import wave
from unittest.mock import patch


# ── 定数・ヘルパー ─────────────────────────────────────────────────────────────

# analyze() が返す形と同じ構造のダミーデータ
_MOCK_ANALYSIS = {
    "pitch_accuracy": 75.0,
    "rhythm_score": 0.0,
    "techniques": {},
    "vocal_range": {"lowest": None, "highest": None, "range_semitones": 0},
    "feedback": "テストフィードバック",
}


def _create_minimal_wav() -> bytes:
    """Pythonの標準waveモジュールで作る最小WAVファイル（ディスクを使わずメモリ上で生成）"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)      # モノラル
        wav_file.setsampwidth(2)      # 16bit
        wav_file.setframerate(44100)  # 44100Hz
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
    with patch("api.analysis.audio_analyzer.analyze", return_value=dict(_MOCK_ANALYSIS)):
        res = _upload(client)
    assert res.status_code == 200
    assert "analysis_id" in res.json()


# ── GET /api/v1/analysis/{analysis_id} ────────────────────────────────────────

def test_get_analysis_success(client):
    _register_and_login(client)
    with patch("api.analysis.audio_analyzer.analyze", return_value=dict(_MOCK_ANALYSIS)):
        analysis_id = _upload(client).json()["analysis_id"]

    res = client.get(f"/api/v1/analysis/{analysis_id}")
    assert res.status_code == 200
    assert res.json()["analysis_id"] == analysis_id


def test_get_analysis_unauthenticated(client):
    _register_and_login(client)
    with patch("api.analysis.audio_analyzer.analyze", return_value=dict(_MOCK_ANALYSIS)):
        analysis_id = _upload(client).json()["analysis_id"]

    client.post("/api/v1/auth/logout")
    res = client.get(f"/api/v1/analysis/{analysis_id}")
    assert res.status_code == 401


def test_get_analysis_not_found(client):
    _register_and_login(client)
    res = client.get("/api/v1/analysis/99999")
    assert res.status_code == 404


def test_get_analysis_other_user_returns_403(client):
    # User A: 登録してアップロード
    _register_and_login(client, email="user_a@example.com")
    with patch("api.analysis.audio_analyzer.analyze", return_value=dict(_MOCK_ANALYSIS)):
        analysis_id = _upload(client).json()["analysis_id"]

    # User B: 登録して User A の分析結果 ID でアクセスする
    client.post("/api/v1/auth/logout")
    _register_and_login(client, email="user_b@example.com")
    res = client.get(f"/api/v1/analysis/{analysis_id}")
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
