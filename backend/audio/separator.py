"""
音源分離モジュール
Demucs v4を使用してカラオケ録音からボーカルを抽出する
"""


class VocalSeparator:
    """
    音源分離クラス
    録音データをボーカル・ドラム・ベース・その他に分離する
    """

    def __init__(self):
        # TODO: Phase2後半でDemucsモデルをロードする
        # from demucs import pretrained
        # self.model = pretrained.get_model('htdemucs')
        self.model = None

    def separate(self, audio_path: str) -> dict:
        """
        音声ファイルをトラックに分離する

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            {
                "vocals": numpy配列,
                "drums": numpy配列,
                "bass": numpy配列,
                "other": numpy配列
            }
        """
        # TODO: 実際のDemucs処理に置き換える
        return {
            "vocals": None,
            "drums": None,
            "bass": None,
            "other": None,
            "status": "dummy",
        }