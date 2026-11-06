"""
分析の失敗理由の分類のテスト（issue #33）

- audio/separator.py：読み込めないファイル → invalid_format
- audio/analyzer.py：声が無い → no_voice
- tasks.py：例外から理由を決めて Redis に記録する
"""

import subprocess
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from celery.exceptions import SoftTimeLimitExceeded

from audio.analyzer import AudioAnalyzer
from audio.errors import INTERNAL, INVALID_FORMAT, NO_VOICE, TIMEOUT, AnalysisError
from audio.separator import _to_wav
from task_failures import get_failure_reason


# ── audio/separator.py ────────────────────────────────────────────────────────

def test_to_wav_raises_invalid_format_when_ffmpeg_fails(tmp_path):
    audio_path = tmp_path / "broken.m4a"
    audio_path.write_bytes(b"not audio")

    with patch(
        "audio.separator.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "ffmpeg"),
    ):
        with pytest.raises(AnalysisError) as exc_info:
            _to_wav(str(audio_path))

    assert exc_info.value.reason == INVALID_FORMAT


# ── audio/analyzer.py ─────────────────────────────────────────────────────────

def _analyzer_with_pitch(confidence: list[float]) -> AudioAnalyzer:
    """Demucs のモデルを読み込まずに AudioAnalyzer を作り、ピッチ検出の結果だけ差し替える"""
    analyzer = object.__new__(AudioAnalyzer)
    analyzer.separator = MagicMock()
    analyzer.separator.separate.return_value = {
        "vocals": np.zeros((2, 100)),
        "sample_rate": 44100,
    }
    analyzer.pitch_detector = MagicMock()
    analyzer.pitch_detector.detect.return_value = {
        "times": [i * 0.01 for i in range(len(confidence))],
        "frequencies": [440.0] * len(confidence),
        "confidence": confidence,
    }
    analyzer.technique_detector = MagicMock()
    return analyzer


def test_analyze_raises_no_voice_when_no_confident_frames():
    analyzer = _analyzer_with_pitch([0.1, 0.2, 0.5])  # 0.5 ちょうどは「声がある」に入れない

    with pytest.raises(AnalysisError) as exc_info:
        analyzer.analyze("dummy.wav")

    assert exc_info.value.reason == NO_VOICE
    analyzer.technique_detector.detect_all.assert_not_called()  # 技法検出まで進まない


def test_analyze_raises_no_voice_when_pitch_is_empty():
    analyzer = _analyzer_with_pitch([])

    with pytest.raises(AnalysisError) as exc_info:
        analyzer.analyze("dummy.wav")

    assert exc_info.value.reason == NO_VOICE


# ── tasks.py ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "error, expected_reason",
    [
        (AnalysisError(NO_VOICE, "no voiced frames"), NO_VOICE),
        (AnalysisError(INVALID_FORMAT, "ffmpeg failed"), INVALID_FORMAT),
        (SoftTimeLimitExceeded(), TIMEOUT),
        (RuntimeError("unexpected"), INTERNAL),
    ],
)
def test_task_saves_failure_reason(fake_redis, tmp_path, error, expected_reason):
    from tasks import analyze_audio_task

    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(b"dummy")

    with patch("tasks._get_analyzer") as mock_get_analyzer, patch("tasks.SessionLocal"):
        mock_get_analyzer.return_value.analyze.side_effect = error
        # apply: worker を使わずにその場で実行する。task_id を渡すと self.request.id に入る
        result = analyze_audio_task.apply(
            args=(str(audio_path), "", "", 1), task_id="failed-task-id",
        )

    assert result.failed()
    assert get_failure_reason("failed-task-id") == expected_reason
