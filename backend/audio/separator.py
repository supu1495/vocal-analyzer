"""
音源分離モジュール
Demucs v4 を使用してカラオケ録音からボーカル・ドラム・ベース・その他に分離する
"""

import numpy as np
import torch
import torchaudio
from demucs.pretrained import get_model
from demucs.apply import apply_model


class VocalSeparator:
    def __init__(self):
        # Demucs v4（htdemucs）モデルを読み込む
        # モデルのロードが重いため Worker 起動時に1回だけ実行する
        self._model = get_model("htdemucs")
        self._model.eval()

    def separate(self, audio_path: str) -> dict:
        """
        音声ファイルをボーカル・ドラム・ベース・その他の4トラックに分離する

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            {
                "vocals": numpy配列 (channels, time),
                "drums":  numpy配列 (channels, time),
                "bass":   numpy配列 (channels, time),
                "other":  numpy配列 (channels, time),
                "sample_rate": int
            }
        """
        wav, sr = torchaudio.load(audio_path)

        # Demucs のサンプリングレートと異なる場合はリサンプリングする
        if sr != self._model.samplerate:
            wav = torchaudio.functional.resample(wav, sr, self._model.samplerate)

        # Demucs はステレオ入力を前提とするためモノラルの場合はチャンネルを複製する
        if wav.shape[0] == 1:
            wav = wav.repeat(2, 1)

        # バッチ次元を追加して分離を実行する: (channels, time) → (1, channels, time)
        with torch.no_grad():
            sources = apply_model(self._model, wav[None], device="cpu")

        # バッチ次元を除去: (1, sources, channels, time) → (sources, channels, time)
        sources = sources[0]

        result = {
            name: sources[i].numpy()
            for i, name in enumerate(self._model.sources)
        }
        result["sample_rate"] = self._model.samplerate
        return result
