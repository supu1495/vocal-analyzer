"""
音源分離モジュール
Demucs v4を使用してカラオケ録音からボーカルを抽出する
"""
import numpy as np
import librosa

class VocalSeparator:
    def __init__(self):
        print("VocalSeparator初期化完了（スタブモード）")

    def separate(self, audio_path: str) -> dict:
        """
        音声ファイルをトラックに分離する（スタブ）
        """
        # 音声ファイルを読み込む
        audio, sample_rate = librosa.load(audio_path, sr=None, mono=False)
        if audio.ndim == 1:
            audio = audio[np.newaxis, :]

        # ダミーデータとしてボーカルにそのまま音声を返す
        return {
            "vocals": audio,
            "drums": np.zeros_like(audio),
            "bass": np.zeros_like(audio),
            "other": np.zeros_like(audio),
            "sample_rate": sample_rate,
        }