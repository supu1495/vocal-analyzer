"""
歌唱技法検出モジュール
ピッチデータから各種歌唱技法を検出・評価する
"""

import numpy as np  # フレームの配列処理・標準偏差計算に使用
import librosa  # hz_to_midi による周波数→半音変換に使用


_LONG_TONE_MIN_SECONDS = 1.0      # ロングトーン判定の最短持続時間（秒）。DAM・ジョイサウンドは0.5秒だが本プロダクトは厳格な判定を採用
_LONG_TONE_PITCH_THRESHOLD = 0.5  # ロングトーン中の最大ピッチ変動（半音単位）

_SHAKURI_MIN_CENTS = 50.0         # しゃくり判定の最小上昇幅（セント）。これ未満は通常の発声として無視する
_SHAKURI_MAX_CENTS = 200.0        # しゃくり判定の最大上昇幅（セント）。これを超える変化は体力不足・感情表現として除外
_SHAKURI_SETTLE_FRAMES = 5        # 安定音程を推定するフレーム数（発声開始の次フレームから最大この数だけ見る）


class TechniqueDetector:
    """
    歌唱技法検出クラス
    ビブラート・こぶし・フォール・しゃくり・ロングトーンを検出する
    """

    def detect_all(self, pitch_data: dict) -> dict:
        """
        すべての歌唱技法を検出する

        Args:
            pitch_data: PitchDetectorが返すピッチデータ

        Returns:
            各技法の検出結果
        """
        return {
            "vibrato": self.detect_vibrato(pitch_data),
            "kobushi": self.detect_kobushi(pitch_data),
            "fall": self.detect_fall(pitch_data),
            "shakuri": self.detect_shakuri(pitch_data),
            "long_tone": self.detect_long_tone(pitch_data),
        }

    def detect_vibrato(self, pitch_data: dict) -> dict:
        """
        ビブラートを検出する（ピッチの周期的な変動）

        Returns:
            {
                "count": 検出回数,
                "avg_frequency": 平均周波数（Hz）,
                "avg_depth": 平均深さ（cent）,
                "gratuitous_count": 加点目的と判定されたビブラートの回数
            }
        """
        # TODO: ピッチの周期的変動をFFTで検出する
        # TODO: gratuitous_count — 間奏など旋律のない区間（ピッチ変化がほぼゼロの無声区間）で発生したビブラートをカウントする
        #       歌唱中のビブラートはアレンジとして加点。旋律のない区間でのビブラートのみ減点対象とする
        return {"count": 0, "avg_frequency": 0.0, "avg_depth": 0.0, "gratuitous_count": 0}

    def detect_kobushi(self, pitch_data: dict) -> dict:
        """
        こぶしを検出する（短時間の急激なピッチ変化）

        Returns:
            {
                "count": 検出回数,
                "timestamps": 発生タイミングのリスト
            }
        """
        # TODO: 短時間での急激なピッチ変化を検出する
        return {"count": 0, "timestamps": []}

    def detect_fall(self, pitch_data: dict) -> dict:
        """
        フォールを検出する（音の終わりの下降）

        Returns:
            {
                "count": 検出回数,
                "avg_depth": 平均下降幅（cent）
            }
        """
        # TODO: 音の終わりの下降パターンを検出する
        return {"count": 0, "avg_depth": 0.0}

    def detect_shakuri(self, pitch_data: dict) -> dict:
        """
        しゃくりを検出する（音の始まりの上昇）

        Returns:
            {
                "count": 検出回数,
                "avg_height": 平均上昇幅（cent）
            }
        """
        times = np.array(pitch_data["times"])
        frequencies = np.array(pitch_data["frequencies"])
        confidence = np.array(pitch_data["confidence"])

        if len(times) < 2:
            return {"count": 0, "avg_height": 0.0}

        reliable = (confidence > 0.5) & (frequencies > 0)
        midi_notes = np.where(reliable, librosa.hz_to_midi(np.maximum(frequencies, 1e-6)), np.nan)

        shakuris = []

        for i in range(1, len(midi_notes)):
            # NaN → 有効MIDI の切り替わり（発声開始）を探す
            if not np.isnan(midi_notes[i - 1]) or np.isnan(midi_notes[i]):
                continue

            start_pitch = midi_notes[i]

            # 発声開始の次フレームから最大 _SHAKURI_SETTLE_FRAMES 個の有効フレームで安定音程を推定する
            settle_end = min(i + 1 + _SHAKURI_SETTLE_FRAMES, len(midi_notes))
            settle_frames = [
                midi_notes[j]
                for j in range(i + 1, settle_end)
                if not np.isnan(midi_notes[j])
            ]

            if len(settle_frames) < 2:
                continue

            settled_pitch = float(np.mean(settle_frames))
            rise_cents = (settled_pitch - start_pitch) * 100.0

            if _SHAKURI_MIN_CENTS <= rise_cents <= _SHAKURI_MAX_CENTS:
                shakuris.append(rise_cents)

        if not shakuris:
            return {"count": 0, "avg_height": 0.0}

        return {
            "count": len(shakuris),
            "avg_height": float(np.mean(shakuris)),
        }

    def detect_long_tone(self, pitch_data: dict) -> dict:
        """
        ロングトーンを検出する（長い音の安定性）

        Returns:
            {
                "count": 検出回数,
                "avg_tone_seconds": 平均持続時間（秒）,
                "avg_stability": 平均安定性（0-100）
            }
        """
        times = np.array(pitch_data["times"])
        frequencies = np.array(pitch_data["frequencies"])
        confidence = np.array(pitch_data["confidence"])

        if len(times) < 2:
            return {"count": 0, "avg_tone_seconds": 0.0, "avg_stability": 0.0}

        seconds_per_frame = float(times[1] - times[0])

        # 信頼度が高く有声のフレームだけMIDIノート番号に変換し、それ以外はNaNにする
        reliable = (confidence > 0.5) & (frequencies > 0)
        midi_notes = np.where(reliable, librosa.hz_to_midi(np.maximum(frequencies, 1e-6)), np.nan)

        long_tones = []
        i = 0
        while i < len(midi_notes):
            if np.isnan(midi_notes[i]):
                i += 1
                continue

            # 現在のフレームから音程が安定して続く区間を探す
            j = i
            segment = [midi_notes[i]]
            while j + 1 < len(midi_notes) and not np.isnan(midi_notes[j + 1]):
                if abs(midi_notes[j + 1] - np.mean(segment)) <= _LONG_TONE_PITCH_THRESHOLD:
                    j += 1
                    segment.append(midi_notes[j])
                else:
                    break

            segment_seconds = (j - i + 1) * seconds_per_frame
            if segment_seconds >= _LONG_TONE_MIN_SECONDS:
                stability = float(max(0.0, 100.0 - np.std(segment) * 200.0))
                long_tones.append({"seconds": segment_seconds, "stability": stability})

            i = j + 1

        if not long_tones:
            return {"count": 0, "avg_tone_seconds": 0.0, "avg_stability": 0.0}

        return {
            "count": len(long_tones),
            "avg_tone_seconds": float(np.mean([lt["seconds"] for lt in long_tones])),
            "avg_stability": float(np.mean([lt["stability"] for lt in long_tones])),
        }