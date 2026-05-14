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

_VIBRATO_MIN_FREQ_HZ  = 4.5   # ビブラート判定の最低周波数（Hz）
_VIBRATO_MAX_FREQ_HZ  = 8.0   # ビブラート判定の最高周波数（Hz）
_VIBRATO_MIN_DEPTH    = 40.0  # ビブラート判定の最小深さ（セント）
_VIBRATO_MAX_DEPTH    = 80.0  # ビブラート判定の最大深さ（セント）
_VIBRATO_MIN_SECONDS  = 0.4   # ビブラート判定の最短持続時間（秒）。最低2サイクル確保するため

_KOBUSHI_MIN_CENTS       = 60.0  # こぶし判定の最小逸脱幅（セント）。これ未満はビブラートのブレ・ノイズとして除外
_KOBUSHI_MAX_CENTS       = 400.0 # こぶし判定の最大逸脱幅（セント）。これを超えると音程ミスや感情表現として扱う
_KOBUSHI_MIN_SECONDS     = 0.05  # 逸脱の最短時間（秒）。50ms未満は音切れ・ノイズとして除外
_KOBUSHI_MAX_SECONDS     = 0.12  # 逸脱の最長時間（秒）。120ms超はビブラートや別技法とみなす
_KOBUSHI_RETURN_CENTS    = 60.0  # 「ベースラインに戻った」と判定する最大逸脱幅（セント）
_KOBUSHI_BASELINE_FRAMES = 20    # 局所ベースライン推定に使う前後のフレーム数

_FALL_MIN_CENTS              = 50.0    # フォール判定の最小下降幅（セント）
_FALL_MIN_SECONDS            = 0.05   # フォール判定の最短時間。これ未満は1フレーム音切れ・CREPEのオクターブエラーとして除外
_FALL_MAX_SECONDS            = 0.8    # フォール判定の最長時間。これを超えるとフレーズ末尾の自然な音程追従とみなす
_FALL_MIN_RATE_CENTS_PER_SEC = 400.0  # フォール判定の最低下降速度。これ未満は緩やかな追従として除外
_FALL_MAX_RATE_CENTS_PER_SEC = 5000.0 # フォール判定の最高下降速度。これを超えるとCREPEの誤検出として除外
_FALL_LOOK_BACK_FRAMES       = 15     # 発声終了直前を見るフレーム数の上限


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

        FFTで有声区間の周期成分を分析し、4.5〜8.0Hz の振動を検出する。
        「加点目的」と「アレンジ模倣」の区別はリファレンスデータなしでは不可能なため
        gratuitous_count は実装しない（SPEC.md 既知の問題を参照）。

        Returns:
            {
                "count": 検出回数,
                "avg_frequency": 平均周波数（Hz）,
                "avg_depth": 平均深さ（cent）
            }
        """
        times = np.array(pitch_data["times"])
        frequencies = np.array(pitch_data["frequencies"])
        confidence = np.array(pitch_data["confidence"])

        if len(times) < 2:
            return {"count": 0, "avg_frequency": 0.0, "avg_depth": 0.0}

        seconds_per_frame = float(times[1] - times[0])
        reliable = (confidence > 0.5) & (frequencies > 0)
        midi_notes = np.where(reliable, librosa.hz_to_midi(np.maximum(frequencies, 1e-6)), np.nan)

        vibratos = []

        i = 0
        while i < len(midi_notes):
            if np.isnan(midi_notes[i]):
                i += 1
                continue

            # 有声区間の終端を探す
            j = i
            while j < len(midi_notes) and not np.isnan(midi_notes[j]):
                j += 1

            segment = midi_notes[i:j]
            seg_len = len(segment)

            if seg_len * seconds_per_frame < _VIBRATO_MIN_SECONDS:
                i = j
                continue

            # 線形デトレンド: メロディのなだらかなピッチ移動を除去してビブラートの波だけを残す
            x = np.arange(seg_len, dtype=float)
            slope, intercept = np.polyfit(x, segment, 1)
            pitch_waveform = segment - (slope * x + intercept)

            # FFTで周期成分を分析する
            fft_result = np.fft.rfft(pitch_waveform)
            freqs = np.fft.rfftfreq(seg_len, d=seconds_per_frame)

            vibrato_mask = (freqs >= _VIBRATO_MIN_FREQ_HZ) & (freqs <= _VIBRATO_MAX_FREQ_HZ)
            if not np.any(vibrato_mask):
                i = j
                continue

            magnitudes = np.abs(fft_result)
            peak_idx = np.argmax(magnitudes[vibrato_mask])
            peak_freq = float(freqs[vibrato_mask][peak_idx])
            # FFTの振幅をピーク変動幅（セント）に変換する
            # 両側スペクトルの片側のみを使うため係数2を掛ける
            peak_depth_cents = (2.0 * float(magnitudes[vibrato_mask][peak_idx]) / seg_len) * 100.0

            if not (_VIBRATO_MIN_DEPTH <= peak_depth_cents <= _VIBRATO_MAX_DEPTH):
                i = j
                continue

            vibratos.append({"frequency": peak_freq, "depth": peak_depth_cents})

            i = j

        if not vibratos:
            return {"count": 0, "avg_frequency": 0.0, "avg_depth": 0.0}

        return {
            "count": len(vibratos),
            "avg_frequency": float(np.mean([v["frequency"] for v in vibratos])),
            "avg_depth": float(np.mean([v["depth"] for v in vibratos])),
        }

    def detect_kobushi(self, pitch_data: dict) -> dict:
        """
        こぶしを検出する（50〜120ms の V字・逆V字ピッチ変化）

        Returns:
            {
                "count": 検出回数,
                "timestamps": 発生タイミングのリスト
            }
        """
        times = np.array(pitch_data["times"])
        frequencies = np.array(pitch_data["frequencies"])
        confidence = np.array(pitch_data["confidence"])

        if len(times) < 2:
            return {"count": 0, "timestamps": []}

        seconds_per_frame = float(times[1] - times[0])
        reliable = (confidence > 0.5) & (frequencies > 0)
        midi_notes = np.where(reliable, librosa.hz_to_midi(np.maximum(frequencies, 1e-6)), np.nan)

        kobushis = []

        i = 0
        while i < len(midi_notes):
            if np.isnan(midi_notes[i]):
                i += 1
                continue

            # 有声区間の終端を探す
            j = i
            while j < len(midi_notes) and not np.isnan(midi_notes[j]):
                j += 1

            segment = midi_notes[i:j]
            seg_len = len(segment)

            if seg_len < 4:
                i = j
                continue

            # 移動中央値でベースラインを推定する
            # 移動中央値はビブラートや一時的な逸脱に対してロバストで、こぶし検出のベースラインに適している
            baseline = np.array([
                np.nanmedian(
                    segment[max(0, k - _KOBUSHI_BASELINE_FRAMES):min(seg_len, k + _KOBUSHI_BASELINE_FRAMES + 1)]
                )
                for k in range(seg_len)
            ])

            deviation_cents = (segment - baseline) * 100.0
            abs_deviation_cents = np.abs(deviation_cents)

            k = 0
            while k < seg_len:
                if abs_deviation_cents[k] < _KOBUSHI_MIN_CENTS:
                    k += 1
                    continue

                # 逸脱区間の開始・終端を確定する
                exc_start = k
                while k < seg_len and abs_deviation_cents[k] >= _KOBUSHI_MIN_CENTS:
                    k += 1
                exc_end = k - 1

                # 持続時間チェック（50ms〜120ms）
                exc_seconds = (exc_end - exc_start + 1) * seconds_per_frame
                if not (_KOBUSHI_MIN_SECONDS <= exc_seconds <= _KOBUSHI_MAX_SECONDS):
                    continue

                # ピーク逸脱幅チェック
                peak_deviation = float(np.max(abs_deviation_cents[exc_start:exc_end + 1]))
                if peak_deviation > _KOBUSHI_MAX_CENTS:
                    continue

                # V字・逆V字チェック: 逸脱区間内は単一方向でなければならない
                exc_deviations = deviation_cents[exc_start:exc_end + 1]
                if not (np.all(exc_deviations > 0) or np.all(exc_deviations < 0)):
                    continue

                # 戻りチェック: 逸脱後にベースライン付近へ戻るかを確認する
                # 逸脱が有声区間の末尾に達している場合は戻りを確認するフレームが存在しないためスキップする
                # 下降方向の末尾逸脱は detect_fall が担当する。上昇方向の末尾逸脱は現状未検出（既知の制限）
                return_start = exc_end + 1
                if return_start >= seg_len:
                    continue

                return_check_end = min(seg_len, return_start + _KOBUSHI_BASELINE_FRAMES)
                if return_check_end - return_start < 2:
                    continue

                if float(np.mean(abs_deviation_cents[return_start:return_check_end])) > _KOBUSHI_RETURN_CENTS:
                    continue

                kobushis.append(float(times[i + exc_start]))

            i = j

        return {
            "count": len(kobushis),
            "timestamps": kobushis,
        }

    def detect_fall(self, pitch_data: dict) -> dict:
        """
        フォールを検出する（音の終わりの下降）

        Returns:
            {
                "count": 検出回数,
                "avg_depth": 平均下降幅（cent）
            }
        """
        times = np.array(pitch_data["times"])
        frequencies = np.array(pitch_data["frequencies"])
        confidence = np.array(pitch_data["confidence"])

        if len(times) < 2:
            return {"count": 0, "avg_depth": 0.0}

        seconds_per_frame = float(times[1] - times[0])

        reliable = (confidence > 0.5) & (frequencies > 0)
        midi_notes = np.where(reliable, librosa.hz_to_midi(np.maximum(frequencies, 1e-6)), np.nan)

        falls = []

        for i in range(1, len(midi_notes)):
            # 有効 → NaN の切り替わり（発声終了）を探す
            if np.isnan(midi_notes[i - 1]) or not np.isnan(midi_notes[i]):
                continue

            last_valid_idx = i - 1
            fall_end_idx = last_valid_idx
            fall_start_idx = last_valid_idx

            # NaN直前から逆方向に単調下降（時間方向）区間をたどる
            # ビブラートの折り返しや別フレーズのピッチが混入しないよう、
            # ピッチが上昇に転じた時点で停止する
            look_back_limit = max(0, last_valid_idx - _FALL_LOOK_BACK_FRAMES)
            j = last_valid_idx - 1
            while j >= look_back_limit:
                if np.isnan(midi_notes[j]):
                    break
                if midi_notes[j] > midi_notes[j + 1]:
                    fall_start_idx = j
                    j -= 1
                else:
                    break

            fall_frames = fall_end_idx - fall_start_idx
            if fall_frames == 0:
                continue

            depth_cents = (midi_notes[fall_start_idx] - midi_notes[fall_end_idx]) * 100.0
            fall_seconds = fall_frames * seconds_per_frame
            rate = depth_cents / fall_seconds

            if (
                depth_cents >= _FALL_MIN_CENTS
                and _FALL_MIN_SECONDS <= fall_seconds <= _FALL_MAX_SECONDS
                and _FALL_MIN_RATE_CENTS_PER_SEC <= rate <= _FALL_MAX_RATE_CENTS_PER_SEC
            ):
                falls.append(depth_cents)

        if not falls:
            return {"count": 0, "avg_depth": 0.0}

        return {
            "count": len(falls),
            "avg_depth": float(np.mean(falls)),
        }

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