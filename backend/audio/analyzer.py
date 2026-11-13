"""
音声分析司令塔モジュール
separator・pitch・techniquesを組み合わせて分析結果を生成する
"""

import contextlib  # with で囲んだ段階の所要時間を測る関数（stage）を短く書くために使用
import logging
import time

import numpy as np  # 周波数配列のフィルタリングと最小・最大値計算に使用
import librosa  # hz_to_midi・midi_to_note による周波数→ノート名変換に使用
from librosa.onset import onset_detect  # 発声タイミング検出（librosa.onset.onset_detectの重複を避けるため個別import）

from audio.errors import NO_VOICE, AnalysisError
from audio.separator import VocalSeparator
from audio.pitch import PitchDetector
from audio.techniques import TechniqueDetector

logger = logging.getLogger(__name__)

# Crepe の信頼度がこれを超えるフレームを「声がある」とみなす（声域の計算と同じ基準）
_VOICED_CONFIDENCE_THRESHOLD = 0.5

# 技法の使いすぎの上限（J-pop相場の上限）。これを超えると不自然さペナルティで減点し、フィードバックで「多すぎます」と伝える
# 採点（_calculate_score_matrix）とフィードバック（_generate_feedback）の両方がここを読む。値を変えたらスコアの版（#23）を上げる
# ロングトーンには上限がない。設定ファイルへの切り出しは #26
OVERUSE_LIMITS = {
    "vibrato": 40,
    "shakuri": 30,
    "kobushi": 15,
    "fall": 10,
}

# フィードバックに出す技法の名前。並び順は採点の配点の順
_TECHNIQUE_LABELS = {
    "vibrato": "ビブラート",
    "shakuri": "しゃくり",
    "kobushi": "こぶし",
    "fall": "フォール",
}


@contextlib.contextmanager
def stage(name: str):
    """分析の1段階を囲み、所要時間をログに出す。例外が出たらどの段階で落ちたかを出す

    スタックトレースは tasks.py の logger.exception で出すため、ここでは段階名と時間だけにする（二重に出さない）
    """
    start = time.time()
    try:
        yield
    except Exception:
        logger.error("Stage failed: stage=%s elapsed=%.2fs", name, time.time() - start)
        raise
    logger.info("Stage finished: stage=%s elapsed=%.2fs", name, time.time() - start)


def _has_voice(pitch_data: dict) -> bool:
    """信頼度が基準を超えるフレームが1つでもあれば True"""
    return any(c > _VOICED_CONFIDENCE_THRESHOLD for c in pitch_data["confidence"])


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
                "score_matrix": スコアマトリクス（total / faithfulness / technique / penalty）,
                "feedback": 改善アドバイス
            }
        """
        # 音源分離：ボーカル・ドラム・ベース・その他に分離
        with stage("separate"):
            separated_tracks = self.separator.separate(audio_path)

        # ボーカルトラックからピッチを検出
        with stage("pitch"):
            pitch_data = self.pitch_detector.detect(separated_tracks["vocals"])
            # 声が無いまま進むと、意味のないスコアを返してしまうため失敗にする
            # 要確認: 今は「1フレームも無い」ときだけ。実音声で「何秒未満なら失敗」にするか調整する
            if not _has_voice(pitch_data):
                raise AnalysisError(NO_VOICE, "no voiced frames")

        # ピッチデータから歌唱技法を検出
        with stage("techniques"):
            detected_techniques = self.technique_detector.detect_all(pitch_data)

        with stage("scoring"):
            # 声域（最低音〜最高音）を計算
            vocal_range = self._calculate_vocal_range(pitch_data)

            # ピッチ正確性とリズム感のスコアを計算
            pitch_accuracy = self.pitch_detector.calculate_accuracy(pitch_data, {})
            rhythm_score = self._calculate_rhythm_score(
                separated_tracks["vocals"], separated_tracks["sample_rate"]
            )

            # スコアマトリクス（基本忠実度・技法スコア・不自然さペナルティ・総合スコア）を計算
            score_matrix = self._calculate_score_matrix(
                pitch_data, detected_techniques, pitch_accuracy, rhythm_score
            )

            # スコアと技法データをもとにフィードバックを生成
            feedback = self._generate_feedback(
                pitch_accuracy, rhythm_score, detected_techniques, score_matrix
            )

        return {
            "pitch_accuracy": pitch_accuracy,
            "rhythm_score": rhythm_score,
            "techniques": detected_techniques,
            "vocal_range": vocal_range,
            "score_matrix": score_matrix,
            "feedback": feedback,
        }

    def _calculate_vocal_range(self, pitch_data: dict) -> dict:
        """声域（最低音〜最高音）を計算する"""
        frequencies = np.array(pitch_data["frequencies"])
        confidence = np.array(pitch_data["confidence"])

        confident_frequencies = frequencies[confidence > _VOICED_CONFIDENCE_THRESHOLD]
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
        # ステレオをモノラルに変換（beat_track・onset_detectはモノラルのみ対応）
        mono = vocals.mean(axis=0)

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

    def _calculate_score_matrix(
        self,
        pitch_data: dict,
        detected_techniques: dict,
        pitch_accuracy: float,
        rhythm_score: float,
    ) -> dict:
        """スコアマトリクスを計算する（基本忠実度・技法スコア・不自然さペナルティ・総合スコア）"""
        faithfulness_score = pitch_accuracy * 0.6 + rhythm_score * 0.4

        vibrato_count   = detected_techniques["vibrato"]["count"]
        kobushi_count   = detected_techniques["kobushi"]["count"]
        fall_count      = detected_techniques["fall"]["count"]
        shakuri_count   = detected_techniques["shakuri"]["count"]
        long_tone_count = detected_techniques["long_tone"]["count"]

        # 各技法を「J-pop相場の下限を満点ライン」として 0〜1 に正規化してから配点
        # 満点ライン（20・20・5・5・3）を変えたら、技法バーの最大値（frontend/src/types.ts の TECHNIQUE_FULL_MARKS）もそろえる
        vibrato_pts   = min(vibrato_count   / 20.0, 1.0) * 20.0
        shakuri_pts   = min(shakuri_count   / 20.0, 1.0) * 15.0
        kobushi_pts   = min(kobushi_count   /  5.0, 1.0) * 15.0
        fall_pts      = min(fall_count      /  5.0, 1.0) * 15.0
        long_tone_pts = min(long_tone_count /  3.0, 1.0) * 15.0
        raw_pts = vibrato_pts + shakuri_pts + kobushi_pts + fall_pts + long_tone_pts
        # raw_max=80（将来の追加技法用バッファ20点分を確保）を 100 点スケールに変換
        technique_score = min(raw_pts / 80.0 * 100.0, 100.0)

        # 棒読み検出: 信頼度の高いフレームのMIDIノート標準偏差を計算する
        frequencies = np.array(pitch_data["frequencies"])
        confidence  = np.array(pitch_data["confidence"])
        confident_freqs = frequencies[confidence > 0.5]
        if len(confident_freqs) > 0:
            pitch_std = float(np.std(librosa.hz_to_midi(np.maximum(confident_freqs, 1e-6))))
        else:
            pitch_std = 0.0

        naturalness_penalty = 0.0
        total_techniques = (
            vibrato_count + kobushi_count + fall_count + shakuri_count + long_tone_count
        )
        # ピッチ分散が小さく技法もゼロ → 棒読みと判定（SPEC.md: 棒読み検出 Approach A）
        if total_techniques == 0 and pitch_std < 2.0:
            naturalness_penalty += 20.0
        # J-pop相場の上限を超えた場合は過剰使用として、技法1つにつき減点
        for name, limit in OVERUSE_LIMITS.items():
            if detected_techniques[name]["count"] > limit:
                naturalness_penalty += 10.0

        total_score = max(
            0.0,
            min(100.0, faithfulness_score * 0.6 + technique_score * 0.4 - naturalness_penalty),
        )

        return {
            "total_score": total_score,
            "faithfulness_score": faithfulness_score,
            "technique_score": technique_score,
            "naturalness_penalty": naturalness_penalty,
        }

    def _generate_feedback(
        self,
        pitch_accuracy: float,
        rhythm_score: float,
        detected_techniques: dict,
        score_matrix: dict,
    ) -> str:
        """スコアと技法データをもとにルールベースのフィードバックを生成する"""
        faithfulness = score_matrix["faithfulness_score"]
        technique    = score_matrix["technique_score"]
        penalty      = score_matrix["naturalness_penalty"]

        vibrato_count   = detected_techniques["vibrato"]["count"]
        kobushi_count   = detected_techniques["kobushi"]["count"]
        fall_count      = detected_techniques["fall"]["count"]
        shakuri_count   = detected_techniques["shakuri"]["count"]
        long_tone       = detected_techniques["long_tone"]
        total_techniques = (
            vibrato_count + kobushi_count + fall_count + shakuri_count + long_tone["count"]
        )

        # 歌唱特性: スコアパターンから歌い方の傾向を1文で表現する
        if penalty >= 20.0 and total_techniques == 0:
            characteristic = "音程は安定していますが、感情表現や歌唱技法が少ない傾向があります"
        elif faithfulness >= 70 and technique >= 60:
            characteristic = "音程・リズムの安定性と豊かな表現力を兼ね備えた歌い方です"
        elif faithfulness >= 70:
            characteristic = "音程・リズムが安定した正確な歌い方です"
        elif technique >= 60:
            characteristic = "表現力豊かですが、音程・リズムの精度にまだ伸び代があります"
        else:
            characteristic = "基礎力と表現力の両方に伸び代があります"

        # 改善点: スコアが低い項目・過剰項目を列挙する
        improvements = []
        if pitch_accuracy < 60:
            improvements.append("音程の精度向上（ゆっくり音程を確認しながら歌う練習が効果的です）")
        if rhythm_score < 60:
            improvements.append("リズム感の向上（メトロノームに合わせて歌う練習が効果的です）")
        if total_techniques == 0:
            improvements.append("ビブラートやしゃくりなど歌唱技法を意識して取り入れてみましょう")

        # できていること: 事実だけを書く（アドバイスや回数は付けない。回数は技法のバーに出ている）
        achievements = []
        if pitch_accuracy >= 80:
            achievements.append("音程の正確さが優れています")
        if rhythm_score >= 80:
            achievements.append("リズム感が優れています")

        # 技法: 上限を超えたものは改善点に、0回より多く上限以内のものはできていることに入れる
        # 上限を超えた技法は、同じアドバイスが何行も続かないよう1行にまとめる（1つだけのときも同じ形）
        overused = []
        for name, label in _TECHNIQUE_LABELS.items():
            count = detected_techniques[name]["count"]
            if count > OVERUSE_LIMITS[name]:
                overused.append(label)
            elif count > 0:
                achievements.append(f"{label}が使えています")
        if overused:
            improvements.append(
                f"技法の使いすぎ：{'、'.join(overused)}（場面を選んで使うとメリハリが生まれます）"
            )
        if long_tone["count"] > 0 and long_tone.get("avg_stability", 0) >= 80:
            achievements.append("ロングトーンが安定しています")

        # 見出しを1行、その下に中身を1行ずつ置き、\n でつなぐ（フロントは pre-line で改行を表示する）
        # 文の最後に「。」は付けない
        lines = ["【歌唱特性】", characteristic]
        if improvements:
            lines.append("【改善点】")
            lines.extend(f"・{item}" for item in improvements)
        if achievements:
            lines.append("【できていること】")
            lines.extend(f"・{item}" for item in achievements)

        return "\n".join(lines)