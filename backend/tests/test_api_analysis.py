"""
分析APIエンドポイントのテスト（api/analysis.py）

Phase 8 以降はアップロードが非同期（Celery タスク）になっているため
- POST /upload はタスク登録 → task_id 返却をテスト
- GET /analysis/status/{task_id} は AsyncResult をモックし、持ち主の記録は fakeredis に直接書いて動作確認
- GET /analysis/{id} は DB に直接レコードを作成して動作確認
"""

import io
import os
import wave
from unittest.mock import patch, MagicMock

from datetime import datetime
from zoneinfo import ZoneInfo

from auth_utils import get_task_owner, save_task_owner
from models import AnalysisResult, User
from upload_limits import release_analysis_slot


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


def _register_and_login(client, email="test@example.com", password="password123", accept_disclaimer=True):
    """登録してログイン状態にする。accept_disclaimer=True なら免責事項にも同意する（アップロードできる状態）"""
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "invite_code": os.environ["INVITE_CODE"]},
    )
    if accept_disclaimer:
        client.post("/api/v1/auth/disclaimer")


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


def test_upload_rejected_without_disclaimer(client):
    """免責事項に同意していなければ、タスクに登録せず 403"""
    _register_and_login(client, accept_disclaimer=False)
    with patch("api.analysis.analyze_audio_task.delay") as mock_delay:
        res = _upload(client)
    assert res.status_code == 403
    mock_delay.assert_not_called()


def test_upload_without_disclaimer_is_not_counted(client, fake_redis):
    """未同意で弾いた分は、1日の回数に数えず、分析中の印も付けない"""
    _register_and_login(client, accept_disclaimer=False)
    _upload(client)
    assert fake_redis.keys("upload_count:*") == []
    assert fake_redis.keys("active_task:*") == []


def test_upload_allowed_after_accepting_disclaimer(client):
    """未同意で弾かれても、同意すればアップロードできる"""
    _register_and_login(client, accept_disclaimer=False)
    assert _upload(client).status_code == 403
    client.post("/api/v1/auth/disclaimer")
    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    with patch("api.analysis.analyze_audio_task.delay", return_value=mock_task):
        assert _upload(client).status_code == 200


def test_upload_rejected_while_analysis_in_progress(client):
    """分析中に2件目を送ると 429"""
    _register_and_login(client)
    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    with patch("api.analysis.analyze_audio_task.delay", return_value=mock_task) as mock_delay:
        first = _upload(client)
        second = _upload(client)
    assert first.status_code == 200
    assert second.status_code == 429
    assert mock_delay.call_count == 1


def test_upload_slot_is_per_user(client):
    """ほかのユーザーが分析中でも、自分のアップロードは通る"""
    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    with patch("api.analysis.analyze_audio_task.delay", return_value=mock_task):
        _register_and_login(client, email="user_a@example.com")
        assert _upload(client).status_code == 200
        client.post("/api/v1/auth/logout")
        _register_and_login(client, email="user_b@example.com")
        assert _upload(client).status_code == 200


def test_upload_slot_released_when_file_rejected(client):
    """ファイルの中身で弾かれたら分析中の印を外し、次のアップロードを受け付ける"""
    _register_and_login(client)
    rejected = _upload(client, content=b"not an audio file")
    assert rejected.status_code == 400

    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    with patch("api.analysis.analyze_audio_task.delay", return_value=mock_task):
        assert _upload(client).status_code == 200


def test_upload_slot_released_when_queueing_fails(client):
    """タスクの登録に失敗したら分析中の印を外す"""
    _register_and_login(client)
    with patch("api.analysis.analyze_audio_task.delay", side_effect=ConnectionError("broker down")):
        try:
            _upload(client)
        except ConnectionError:
            pass  # TestClient はサーバー側の例外をそのまま投げ直す

    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    with patch("api.analysis.analyze_audio_task.delay", return_value=mock_task):
        assert _upload(client).status_code == 200


def test_upload_slot_has_expiry(client, db, fake_redis):
    """worker が強制終了されても印が残り続けないよう、有効期限が付いている"""
    _register_and_login(client)
    user = db.query(User).first()
    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    with patch("api.analysis.analyze_audio_task.delay", return_value=mock_task):
        _upload(client)
    ttl = fake_redis.ttl(f"active_task:{user.id}")
    assert 0 < ttl <= 20 * 60


def test_task_releases_slot_when_analysis_fails(fake_redis, tmp_path):
    """分析が失敗しても、タスクの finally で分析中の印を外す"""
    from tasks import analyze_audio_task
    from upload_limits import acquire_analysis_slot

    user_id = 1
    assert acquire_analysis_slot(user_id)
    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(_create_minimal_wav())

    with patch("tasks._get_analyzer") as mock_get_analyzer, patch("tasks.SessionLocal"):
        mock_get_analyzer.return_value.analyze.side_effect = RuntimeError("analysis failed")
        try:
            analyze_audio_task(str(audio_path), "", "", user_id)
        except RuntimeError:
            pass

    assert acquire_analysis_slot(user_id)  # 印が外れていれば、もう一度付けられる


def _upload_and_finish(client, db):
    """アップロードして、分析が終わった状態にする（分析中の印を外して次を送れるようにする）"""
    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    with patch("api.analysis.analyze_audio_task.delay", return_value=mock_task):
        res = _upload(client)
    for user in db.query(User).all():
        release_analysis_slot(user.id)
    return res


def _jst(*args) -> datetime:
    return datetime(*args, tzinfo=ZoneInfo("Asia/Tokyo"))


def test_upload_rejected_after_daily_limit(client, db):
    """1日の上限（10回）までは通り、11回目は 429"""
    _register_and_login(client)
    with patch("upload_limits._now_jst", return_value=_jst(2026, 10, 30, 12, 0)):
        for _ in range(10):
            assert _upload_and_finish(client, db).status_code == 200
        res = _upload_and_finish(client, db)
    assert res.status_code == 429
    assert "10回" in res.json()["detail"]


def test_daily_limit_retry_after_is_seconds_until_jst_midnight(client, db, monkeypatch):
    """Retry-After は次の日本時間0時までの秒数（23:59:30 なら30秒）"""
    monkeypatch.setenv("DAILY_UPLOAD_LIMIT", "1")
    _register_and_login(client)
    with patch("upload_limits._now_jst", return_value=_jst(2026, 10, 30, 23, 59, 30)):
        _upload_and_finish(client, db)
        res = _upload_and_finish(client, db)
    assert res.status_code == 429
    assert res.headers["Retry-After"] == "30"


def test_daily_limit_retry_after_rounds_up(client, db, monkeypatch):
    """端数は切り上げる（残り29.5秒なら30秒）"""
    monkeypatch.setenv("DAILY_UPLOAD_LIMIT", "1")
    _register_and_login(client)
    with patch("upload_limits._now_jst", return_value=_jst(2026, 10, 30, 23, 59, 30, 500000)):
        _upload_and_finish(client, db)
        res = _upload_and_finish(client, db)
    assert res.headers["Retry-After"] == "30"


def test_daily_limit_resets_at_jst_midnight(client, db, monkeypatch):
    """日本時間で日付が変われば受け付ける（UTC ではまだ前の日の 15:00）"""
    monkeypatch.setenv("DAILY_UPLOAD_LIMIT", "1")
    _register_and_login(client)
    with patch("upload_limits._now_jst", return_value=_jst(2026, 10, 30, 23, 59)):
        _upload_and_finish(client, db)
        assert _upload_and_finish(client, db).status_code == 429
    with patch("upload_limits._now_jst", return_value=_jst(2026, 10, 31, 0, 0)):
        assert _upload_and_finish(client, db).status_code == 200


def test_daily_limit_does_not_count_rejected_files(client, db, monkeypatch):
    """ファイルの中身で弾かれた分は数えない"""
    monkeypatch.setenv("DAILY_UPLOAD_LIMIT", "1")
    _register_and_login(client)
    assert _upload(client, content=b"not an audio file").status_code == 400
    assert _upload_and_finish(client, db).status_code == 200


def test_daily_limit_is_per_user(client, db, monkeypatch):
    """ほかのユーザーが上限に達していても、自分は送れる"""
    monkeypatch.setenv("DAILY_UPLOAD_LIMIT", "1")
    _register_and_login(client, email="user_a@example.com")
    _upload_and_finish(client, db)
    assert _upload_and_finish(client, db).status_code == 429
    client.post("/api/v1/auth/logout")
    _register_and_login(client, email="user_b@example.com")
    assert _upload_and_finish(client, db).status_code == 200


def test_daily_count_key_has_expiry(client, db, fake_redis):
    """回数のキーに掃除用の期限が付いている"""
    _register_and_login(client)
    user = db.query(User).first()
    with patch("upload_limits._now_jst", return_value=_jst(2026, 10, 30, 12, 0)):
        _upload_and_finish(client, db)
    assert fake_redis.ttl(f"upload_count:{user.id}:2026-10-30") > 0


# ── GET /api/v1/analysis/status/{task_id} ─────────────────────────────────────

def test_get_analysis_status_unauthenticated(client):
    res = client.get("/api/v1/analysis/status/some-task-id")
    assert res.status_code == 401


def test_upload_saves_task_owner(client, db):
    _register_and_login(client)
    user = db.query(User).first()
    mock_task = MagicMock()
    mock_task.id = "test-task-id"
    with patch("api.analysis.analyze_audio_task.delay", return_value=mock_task):
        _upload(client)
    assert get_task_owner("test-task-id") == user.id


def test_get_analysis_status_success(client, db):
    _register_and_login(client)
    user = db.query(User).first()
    save_task_owner("some-task-id", user.id)
    with patch("api.analysis.celery_app.AsyncResult") as mock_async_result:
        mock_async_result.return_value.status = "SUCCESS"
        mock_async_result.return_value.result = 42
        res = client.get("/api/v1/analysis/status/some-task-id")
    assert res.status_code == 200
    assert res.json() == {"status": "SUCCESS", "analysis_id": 42}


def test_get_analysis_status_pending(client, db):
    _register_and_login(client)
    user = db.query(User).first()
    save_task_owner("some-task-id", user.id)
    with patch("api.analysis.celery_app.AsyncResult") as mock_async_result:
        mock_async_result.return_value.status = "PENDING"
        res = client.get("/api/v1/analysis/status/some-task-id")
    assert res.status_code == 200
    assert res.json()["status"] == "PENDING"


def test_get_analysis_status_unknown_task_returns_404(client):
    # Celery は存在しない task_id にも PENDING を返すため、持ち主の記録で弾けているかを見る
    _register_and_login(client)
    res = client.get("/api/v1/analysis/status/unknown-task-id")
    assert res.status_code == 404


def test_get_analysis_status_other_user_returns_404(client, db):
    # User A: 登録してタスクの持ち主として記録する
    _register_and_login(client, email="user_a@example.com")
    user_a = db.query(User).filter(User.email == "user_a@example.com").first()
    save_task_owner("user-a-task-id", user_a.id)

    # User B: 登録して User A のタスクの状態を確認しようとする
    client.post("/api/v1/auth/logout")
    _register_and_login(client, email="user_b@example.com")
    res = client.get("/api/v1/analysis/status/user-a-task-id")
    assert res.status_code == 404


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
