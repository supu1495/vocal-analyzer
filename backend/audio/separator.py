"""
音源分離モジュール
Demucs v4を使用してカラオケ録音からボーカルを抽出する
"""

import numpy as np
import torch
import soundfile as sf
import librosa
from demucs.pretrained import get_model
from demucs.apply import apply_model


class VocalSeparator:
    """
    音源分離クラス
    録音データをボーカル・ドラム・ベース・その他に分離する
    """

    def __init__(self):
        # Demucsモデルをロード（htdemucsが最高精度モデル）
        # 初回起動時にモデルをダウンロードするため数分かかる場合がある
        print("Demucsモデルをロード中...")
        self.model = get_model("htdemucs")
        self.model.eval()

        # GPUが使える場合はGPUを使用、なければCPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        print(f"Demucsモデルのロード完了（使用デバイス: {self.device}）")

    def separate(self, audio_path: str) -> dict:
        """
        音声ファイルをトラックに分離する

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            {
                "vocals": ボーカルのnumpy配列,
                "drums": ドラムのnumpy配列,
                "bass": ベースのnumpy配列,
                "other": その他のnumpy配列,
                "sample_rate": サンプリングレート
            }
        """
        # 音声ファイルを読み込む
        audio, sample_rate = librosa.load(audio_path, sr=None, mono=False)
        if audio.ndim == 1:
            audio = audio[np.newaxis, :]  # モノラルの場合は次元を追加

        # Demucsが期待する形式に変換（チャンネル × サンプル数）
        audio = audio.T
        audio_tensor = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
        audio_tensor = audio_tensor.to(self.device)

        # 音源分離を実行
        with torch.no_grad():
            sources = apply_model(self.model, audio_tensor)
            
        # numpy配列に変換してバッチ次元を削除
        sources = sources.squeeze(0).cpu().numpy()

        # モデルが持つトラック名のリストを取得（例: ["drums", "bass", "other", "vocals"]）
        track_names = self.model.sources

        result = {}
        for i, name in enumerate(track_names):
            result[name] = sources[i]

        result["sample_rate"] = sample_rate
        return result