"""
フィードバック文（AudioAnalyzer._generate_feedback）のテスト（issue #11）

形（フロントは pre-line で \n をそのまま改行として表示する）:
    【歌唱特性】
    <1文>
    【改善点】            ← 項目があるときだけ
    ・<項目>
    【伸ばすべきポイント】  ← 項目があるときだけ
    ・<項目>
文の最後に「。」は付けない
"""

import pytest

from audio.analyzer import AudioAnalyzer  # _generate_feedback を呼ぶため

CHARACTERISTIC = "【歌唱特性】"
IMPROVEMENTS = "【改善点】"
STRENGTHS = "【伸ばすべきポイント】"


def _analyzer() -> AudioAnalyzer:
    """Demucs のモデルを読み込まずに AudioAnalyzer を作る（_generate_feedback はモデルを使わない）"""
    return object.__new__(AudioAnalyzer)


def _techniques(count: int) -> dict:
    """全技法を同じ回数にした検出結果。ロングトーンは安定度 80（伸ばすべきポイントに出る値）にする"""
    return {
        "vibrato": {"count": count},
        "kobushi": {"count": count},
        "fall": {"count": count},
        "shakuri": {"count": count},
        "long_tone": {"count": count, "avg_stability": 80.0},
    }


def _score_matrix(penalty: float) -> dict:
    return {"faithfulness_score": 50.0, "technique_score": 50.0, "naturalness_penalty": penalty}


def _items_under(lines: list[str], heading: str) -> list[str]:
    """見出しの次の行から、次の見出し（【 で始まる行）の手前までを返す"""
    start = lines.index(heading) + 1
    items = []
    for line in lines[start:]:
        if line.startswith("【"):
            break
        items.append(line)
    return items


# 改善点と伸ばすべきポイントは、同時には全部出せない（例：音程 < 60 と音程 >= 80）。
# そのため、どちらかの項目がなるべく多く出る組み合わせに分けて確かめる
@pytest.mark.parametrize(
    "pitch, rhythm, technique_count, penalty, improvement_count, strength_count",
    [
        # 改善点：音程・リズム・使いすぎ ／ 伸ばすべきポイント：ビブラート・こぶし・ロングトーン
        (50.0, 50.0, 1, 10.0, 3, 3),
        # 改善点：使いすぎ ／ 伸ばすべきポイント：5つ全部
        (90.0, 90.0, 1, 10.0, 1, 5),
        # 改善点：技法を取り入れる ／ 伸ばすべきポイント：音程・リズム
        (90.0, 90.0, 0, 20.0, 1, 2),
    ],
    ids=["improvements_many", "strengths_all", "no_techniques"],
)
def test_feedback_headings_and_bullet_items(
    pitch, rhythm, technique_count, penalty, improvement_count, strength_count,
):
    feedback = _analyzer()._generate_feedback(
        pitch, rhythm, _techniques(technique_count), _score_matrix(penalty),
    )
    lines = feedback.split("\n")

    # 見出しはそれぞれ1行で、この順に並ぶ
    headings = [line for line in lines if line.startswith("【")]
    assert headings == [CHARACTERISTIC, IMPROVEMENTS, STRENGTHS]

    # 歌唱特性は見出しの下に1文（「・」は付けない）
    characteristic = _items_under(lines, CHARACTERISTIC)
    assert len(characteristic) == 1
    assert not characteristic[0].startswith("・")

    # 改善点・伸ばすべきポイントは、1項目ずつ「・」で始まる行になる
    improvements = _items_under(lines, IMPROVEMENTS)
    strengths = _items_under(lines, STRENGTHS)
    assert len(improvements) == improvement_count
    assert len(strengths) == strength_count
    assert all(item.startswith("・") for item in improvements + strengths)

    # 文の最後に「。」を付けない（歌唱特性も含む）
    assert not any(line.endswith("。") for line in lines)


def test_feedback_omits_empty_sections():
    """項目が1つもないまとまりは、見出しごと出さない（音程・リズムが 60〜80 で技法が少し使えていない場合など）"""
    techniques = _techniques(0)
    techniques["fall"]["count"] = 1  # 伸ばすべきポイントに出ない技法だけを1回にする
    feedback = _analyzer()._generate_feedback(70.0, 70.0, techniques, _score_matrix(0.0))

    lines = feedback.split("\n")
    assert lines[0] == CHARACTERISTIC
    assert len(lines) == 2
