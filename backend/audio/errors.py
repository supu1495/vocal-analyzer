"""
分析の失敗理由
status API で利用者に理由を返すため、失敗をいくつかに分類する（issue #33）
"""

# 失敗理由。status API の reason にそのまま入る
INVALID_FORMAT = "invalid_format"  # 音声として読み込めない（ffmpeg / torchaudio が失敗）
NO_VOICE = "no_voice"              # 歌声が検出できない（無音・伴奏だけなど）
TIMEOUT = "timeout"                # 時間制限（celery_app.py の task_soft_time_limit）を超えた
INTERNAL = "internal"              # 上のどれにも当たらない（サーバー側の不具合）


class AnalysisError(Exception):
    """理由が分かっている分析の失敗

    message はログ用。利用者に見せる文言は api/analysis.py で reason ごとに決める
    """

    def __init__(self, reason: str, message: str):
        super().__init__(f"{reason}: {message}")
        self.reason = reason
