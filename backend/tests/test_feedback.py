"""
フィードバック文（AudioAnalyzer._generate_feedback）と、使いすぎの上限（OVERUSE_LIMITS）のテスト（issue #11）

形（フロントは pre-line で \n をそのまま改行として表示する）:
    【歌唱特性】
    <1文>
    【改善点】          ← 項目があるときだけ
    ・<項目>
    【できていること】  ← 項目があるときだけ
    ・<項目>
文の最後に「。」は付けない
"""

import pytest

# AudioAnalyzer: _generate_feedback・_calculate_score_matrix を呼ぶため
# OVERUSE_LIMITS: 採点と同じ上限の値からテストの回数を作るため（数字をテストに直書きしない）
from audio.analyzer import OVERUSE_LIMITS, AudioAnalyzer

CHARACTERISTIC = "【歌唱特性】"
IMPROVEMENTS = "【改善点】"
ACHIEVEMENTS = "【できていること】"
OVERUSE_ADVICE = "場面を選んで使うとメリハリが生まれます"


def _analyzer() -> AudioAnalyzer:
    """Demucs のモデルを読み込まずに AudioAnalyzer を作る（どちらのメソッドもモデルを使わない）"""
    return object.__new__(AudioAnalyzer)


def _techniques(count: int, **overrides: int) -> dict:
    """全技法を同じ回数にした検出結果。overrides で技法ごとに回数を変える
    ロングトーンは安定度 80（できていることに出る値）にする
    """
    counts = {"vibrato": count, "shakuri": count, "kobushi": count, "fall": count, "long_tone": count}
    counts.update(overrides)
    techniques = {name: {"count": n} for name, n in counts.items()}
    techniques["long_tone"]["avg_stability"] = 80.0
    return techniques


def _score_matrix(penalty: float) -> dict:
    return {"faithfulness_score": 50.0, "technique_score": 50.0, "naturalness_penalty": penalty}


def _feedback(pitch: float, rhythm: float, techniques: dict, penalty: float = 0.0) -> list[str]:
    return _analyzer()._generate_feedback(pitch, rhythm, techniques, _score_matrix(penalty)).split("\n")


def _items_under(lines: list[str], heading: str) -> list[str]:
    """見出しの次の行から、次の見出し（【 で始まる行）の手前までを返す。見出しがなければ空"""
    if heading not in lines:
        return []
    items = []
    for line in lines[lines.index(heading) + 1:]:
        if line.startswith("【"):
            break
        items.append(line)
    return items


# ── 形 ────────────────────────────────────────────────────────────────────────


# 改善点とできていることは、同時には全部出せない（例：音程 < 60 と音程 >= 80）。
# そのため、どちらかの項目がなるべく多く出る組み合わせに分けて確かめる
@pytest.mark.parametrize(
    "pitch, rhythm, techniques, improvement_count, achievement_count",
    [
        # 改善点：音程・リズム・技法の使いすぎ（4技法を1行にまとめる） ／ できていること：ロングトーン
        (50.0, 50.0, _techniques(1, **{n: limit + 1 for n, limit in OVERUSE_LIMITS.items()}), 3, 1),
        # 改善点：なし ／ できていること：音程・リズム・5技法の全部
        (90.0, 90.0, _techniques(1), 0, 7),
        # 改善点：技法を取り入れる ／ できていること：音程・リズム
        (90.0, 90.0, _techniques(0), 1, 2),
    ],
    ids=["improvements_many", "achievements_all", "no_techniques"],
)
def test_feedback_headings_and_bullet_items(pitch, rhythm, techniques, improvement_count, achievement_count):
    lines = _feedback(pitch, rhythm, techniques)

    # 見出しはそれぞれ1行で、この順に並ぶ（項目がないまとまりは見出しごと出さない）
    expected_headings = [CHARACTERISTIC]
    if improvement_count:
        expected_headings.append(IMPROVEMENTS)
    if achievement_count:
        expected_headings.append(ACHIEVEMENTS)
    assert [line for line in lines if line.startswith("【")] == expected_headings

    # 歌唱特性は見出しの下に1文（「・」は付けない）
    characteristic = _items_under(lines, CHARACTERISTIC)
    assert len(characteristic) == 1
    assert not characteristic[0].startswith("・")

    # 改善点・できていることは、1項目ずつ「・」で始まる行になる
    improvements = _items_under(lines, IMPROVEMENTS)
    achievements = _items_under(lines, ACHIEVEMENTS)
    assert len(improvements) == improvement_count
    assert len(achievements) == achievement_count
    assert all(item.startswith("・") for item in improvements + achievements)

    # 文の最後に「。」を付けない（歌唱特性も含む）
    assert not any(line.endswith("。") for line in lines)


def test_achievements_are_facts_only():
    """できていることには、アドバイス（括弧の補足）を付けない"""
    achievements = _items_under(_feedback(90.0, 90.0, _techniques(1)), ACHIEVEMENTS)
    assert not any("（" in item for item in achievements)


# ── 使いすぎの上限 ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name, label",
    [("vibrato", "ビブラート"), ("shakuri", "しゃくり"), ("kobushi", "こぶし"), ("fall", "フォール")],
)
def test_technique_at_limit_is_achievement(name, label):
    """上限ちょうどは使いすぎではない。できていることに入り、改善点には出ない"""
    lines = _feedback(70.0, 70.0, _techniques(0, **{name: OVERUSE_LIMITS[name]}))
    assert f"・{label}が使えています" in _items_under(lines, ACHIEVEMENTS)
    assert not any(label in item for item in _items_under(lines, IMPROVEMENTS))


@pytest.mark.parametrize(
    "name, label",
    [("vibrato", "ビブラート"), ("shakuri", "しゃくり"), ("kobushi", "こぶし"), ("fall", "フォール")],
)
def test_technique_over_limit_is_improvement(name, label):
    """上限を超えたら、改善点に「技法の使いすぎ：〇〇」と書き、できていることには入れない（1つだけのときも同じ形）"""
    lines = _feedback(70.0, 70.0, _techniques(0, **{name: OVERUSE_LIMITS[name] + 1}))
    assert f"・技法の使いすぎ：{label}（{OVERUSE_ADVICE}）" in _items_under(lines, IMPROVEMENTS)
    assert not any(label in item for item in _items_under(lines, ACHIEVEMENTS))


def test_overused_techniques_are_listed_in_one_line():
    """上限を超えた技法が複数あっても、同じアドバイスを繰り返さず1行に並べる。並びは採点の配点の順"""
    techniques = _techniques(
        0,
        vibrato=OVERUSE_LIMITS["vibrato"],  # ちょうど上限なので使いすぎではない
        kobushi=OVERUSE_LIMITS["kobushi"] + 1,
        fall=OVERUSE_LIMITS["fall"] + 1,
        shakuri=OVERUSE_LIMITS["shakuri"] + 1,
    )
    improvements = _items_under(_feedback(70.0, 70.0, techniques), IMPROVEMENTS)

    assert improvements == [f"・技法の使いすぎ：しゃくり、こぶし、フォール（{OVERUSE_ADVICE}）"]


@pytest.mark.parametrize("name", list(OVERUSE_LIMITS))
def test_score_penalty_uses_same_limits(name):
    """採点も同じ上限を使う：上限ちょうどでは減点なし、1回超えると 10 点減点（フィードバックと境目がずれない）"""
    # ピッチは使わない（棒読みの判定は技法が0回のときだけなので、上限の回数を入れたこのテストでは起きない）
    pitch_data = {"frequencies": [440.0], "confidence": [0.0]}

    at_limit = _analyzer()._calculate_score_matrix(
        pitch_data, _techniques(0, **{name: OVERUSE_LIMITS[name]}), 50.0, 50.0,
    )
    over_limit = _analyzer()._calculate_score_matrix(
        pitch_data, _techniques(0, **{name: OVERUSE_LIMITS[name] + 1}), 50.0, 50.0,
    )

    assert at_limit["naturalness_penalty"] == 0.0
    assert over_limit["naturalness_penalty"] == 10.0
