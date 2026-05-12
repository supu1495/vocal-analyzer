"""
音声分析司令塔モジュール
separator・pitch・techniquesを組み合わせて分析結果を生成する
"""

import numpy as np  # 周波数配列のフィルタリングと最小・最大値計算に使用
import librosa  # hz_to_midi・midi_to_note による周波数→ノート名変換に使用
from librosa.onset import onset_detect  # 発声タイミング検出（librosa.onset.onset_detectの重複を避けるため個別import）

from audio.separator import VocalSeparator
from audio.pitch import PitchDetector
from audio.techniques import TechniqueDetector


class AudioAnalyzer:
    """
    音声分析の司令塔クラス
    各モジュールを呼び出して総合的な分析結果を生成する
    """

    def __init__(self):
        self.separator = VocalSeparator()
        self.pitch_detector = PitchDetector()
        self.technique_detector = TechniqueDetector()

    def analyze(self, audio_path: str) -> dict:
        """
        音声ファイルを分析して総合結果を返す

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            {
                "pitch_accuracy": ピッチ正確性スコア（0-100）,
                "rhythm_score": リズムスコア（0-100）,
                "techniques": 歌唱技法の詳細,
                "vocal_range": 声域データ,
                "feedback": 改善アドバイス
            }
        """
        # 音源分離：ボーカル・ドラム・ベース・その他に分離
        separated_tracks = self.separator.separate(audio_path)

        # ボーカルトラックからピッチを検出
        pitch_data = self.pitch_detector.detect(separated_tracks["vocals"])

        # ピッチデータから歌唱技法を検出
        detected_techniques = self.technique_detector.detect_all(pitch_data)

        # 声域（最低音〜最高音）を計算
        vocal_range = self._calculate_vocal_range(pitch_data)

        # ピッチ正確性とリズム感のスコアを計算
        pitch_accuracy = self.pitch_detector.calculate_accuracy(pitch_data, {})
        rhythm_score = self._calculate_rhythm_score(
            separated_tracks["vocals"], separated_tracks["sample_rate"]
        )

        # 分析結果をもとに改善アドバイスを生成
        feedback = self._generate_feedback(pitch_accuracy, detected_techniques)

        return {
            "pitch_accuracy": pitch_accuracy,
            "rhythm_score": rhythm_score,
            "techniques": detected_techniques,
            "vocal_range": vocal_range,
            "feedback": feedback,
        }

    def _calculate_vocal_range(self, pitch_data: dict) -> dict:
        """声域（最低音〜最高音）を計算する"""
        frequencies = np.array(pitch_data["frequencies"])
        confidence = np.array(pitch_data["confidence"])

        confident_frequencies = frequencies[confidence > 0.5]
        if len(confident_frequencies) == 0:
            return {"lowest": None, "highest": None, "range_semitones": 0}

        lowest_midi = int(round(librosa.hz_to_midi(float(confident_frequencies.min()))))
        highest_midi = int(round(librosa.hz_to_midi(float(confident_frequencies.max()))))

        return {
            "lowest": librosa.midi_to_note(lowest_midi),
            "highest": librosa.midi_to_note(highest_midi),
            "range_semitones": highest_midi - lowest_midi,
        }

    def _calculate_rhythm_score(self, vocals: np.ndarray, sample_rate: int) -> float:
        """リズム感・グルーヴ感のスコアを計算する

        発声タイミング（onset）とビートのズレの一貫性を測定する。
        一貫したズレ（グルーヴ）を高評価し、バラバラなズレを低評価する。
        """
        # ステレオの場合はモノラルに変換（beat_track・onset_detectはモノラルのみ対応）
        mono = vocals.mean(axis=0) if vocals.ndim == 2 else vocals

        # ビート位置を検出してフレーム番号→秒に変換
        _, beat_frames = librosa.beat.beat_track(y=mono, sr=sample_rate)
        beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate)

        # 発声タイミング（onset）を検出してフレーム番号→秒に変換
        onset_frames = onset_detect(y=mono, sr=sample_rate)
        onset_times = librosa.frames_to_time(onset_frames, sr=sample_rate)

        if len(onset_times) < 2 or len(beat_times) < 2:
            return 0.0

        # 各onsetから最も近いビートとのズレ（オフセット）を計算
        offsets = []
        for onset in onset_times:
            nearest_beat = beat_times[np.argmin(np.abs(beat_times - onset))]
            offsets.append(onset - nearest_beat)

        # オフセットの標準偏差が小さい = 一貫したズレ = グルーヴがある = 高スコア
        # 標準偏差 0ms → 100点、100ms以上 → 0点
        offset_std = np.std(offsets)
        return float(max(0.0, 100.0 - offset_std * 1000.0))

    def _generate_feedback(self, pitch_accuracy: float, detected_techniques: dict) -> str:
        """分析結果をもとに改善アドバイスを生成する"""
        # TODO: スコアと技法データをもとに具体的なアドバイスを生成する
        return "分析完了。詳細なフィードバックは今後実装予定です。"