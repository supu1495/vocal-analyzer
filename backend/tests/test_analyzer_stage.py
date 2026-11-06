"""
audio/analyzer.py の stage（段階ごとの所要時間・失敗した段階のログ）のテスト
"""

import logging

import pytest

from audio.analyzer import stage


def test_stage_logs_finished_on_success(caplog):
    with caplog.at_level(logging.INFO, logger="audio.analyzer"):
        with stage("pitch"):
            pass

    assert "Stage finished: stage=pitch" in caplog.text
    assert "Stage failed" not in caplog.text


def test_stage_logs_failed_and_reraises(caplog):
    with caplog.at_level(logging.INFO, logger="audio.analyzer"):
        with pytest.raises(ValueError):
            with stage("separate"):
                raise ValueError("boom")

    assert "Stage failed: stage=separate" in caplog.text
    assert "Stage finished" not in caplog.text
