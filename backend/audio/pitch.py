"""
ピッチ検出モジュール
Crepeを使用してボーカルトラックからピッチを検出する
"""

import numpy as np
import crepe
import librosa


class PitchDetector:
    """
    ピッチ検出クラス
    ボーカルトラックから時系列のピッチデータを抽出する
    """

    def __init__(self):
        # Crepeはインポート時に自動でモデルをロードする
        pass

    def detect(self, vocals: np.ndarray, sample_rate: int = 44100) -> dict:
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
        # 音源分離が失敗してボーカルデータがない場合は空を返す
        if vocals is None:
            return {"times": [], "frequencies": [], "confidence": []}

        # Crepeはモノラルのみ対応のため、ステレオの場合は左右の平均を取って変換
        if vocals.ndim == 2:
            vocals_as_mono = vocals.mean(axis=0)
        else:
            vocals_as_mono = vocals

        # Crepeでピッチ検出を実行
        # viterbi=True: 前後フレームを考慮してより滑らかなピッチを推定
        # verbose=0: 処理中のログを非表示
        times, frequencies, confidence, _ = crepe.predict(
            vocals_as_mono,
            sample_rate,
            viterbi=True,
            verbose=0,
        )

        # numpy配列はJSONに変換できないためリストに変換して返す
        return {
            "times": times.tolist(),
            "frequencies": frequencies.tolist(),
            "confidence": confidence.tolist(),
        }

    def calculate_accuracy(self, detected: dict, reference: dict) -> float:
        """
        検出したピッチの安定性からスコアを計算する

        Args:
            detected: 検出したピッチデータ
            reference: 原曲のピッチデータ（将来的に使用予定）

        Returns:
            ピッチ正確性スコア（0-100）
        """
        # ピッチデータが空の場合はスコア0を返す
        if not detected["frequencies"]:
            return 0.0

        # リストをnumpy配列に変換（数値計算のため）
        frequencies = np.array(detected["frequencies"])
        confidence = np.array(detected["confidence"])

        # 信頼度0.5未満のフレームは「自信がない音程」として除外
        is_confident = confidence > 0.5
        if not is_confident.any():
            return 0.0

        # 信頼度が高いフレームの周波数だけを抽出
        reliable_frequencies = frequencies[is_confident]

        # 周波数（Hz）をMIDIノート番号に変換（例: 440Hz → 69）
        midi_notes = librosa.hz_to_midi(reliable_frequencies)

        # 半音内でのズレ（小数部分）を取り出してピッチの安定性を計算
        # 標準偏差が小さい = ばらつきが少ない = ピッチが安定している
        deviation_within_semitone = midi_notes % 1
        pitch_instability = np.std(deviation_within_semitone)

        # 不安定さをスコアに変換（不安定なほどスコアが下がる、最低0）
        stability_score = max(0, 100 - pitch_instability * 100)

        return float(stability_score)