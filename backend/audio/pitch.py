"""
ピッチ検出モジュール
Crepeを使用してボーカルトラックからピッチを検出する
"""


class PitchDetector:
    """
    ピッチ検出クラス
    ボーカルトラックから時系列のピッチデータを抽出する
    """

    def __init__(self):
        # TODO: Phase2後半でCrepeモデルをロードする
        # import crepe
        # self.model = crepe
        self.model = None

    def detect(self, vocals: any, sample_rate: int = 44100) -> dict:
        """
        ボーカルトラックからピッチを検出する

        Args:
            vocals: ボーカルの音声データ（numpy配列）
            sample_rate: サンプリングレート

        Returns:
            {
                "times": 時刻のリスト（秒）,
                "frequencies": 周波数のリスト（Hz）,
                "confidence": 信頼度のリスト（0-1）
            }
        """
        # TODO: 実際のCrepe処理に置き換える
        return {
            "times": [],
            "frequencies": [],
            "confidence": [],
            "status": "dummy",
        }

    def calculate_accuracy(self, detected: dict, reference: dict) -> float:
        """
        検出したピッチと原曲ピッチを比較して正確性を計算する

        Args:
            detected: 検出したピッチデータ
            reference: 原曲のピッチデータ

        Returns:
            ピッチ正確性スコア（0-100）
        """
        # TODO: cent単位での誤差計算を実装する
        return 0.0