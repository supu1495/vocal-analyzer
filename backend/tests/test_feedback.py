"""
フィードバック文（AudioAnalyzer._generate_feedback）のテスト（issue #11）

- 項目の末尾の「。」と、まとまりを締める「。」が重なって「。。」にならないこと
- 【歌唱特性】【改善点】【伸ばすべきポイント】の3つのまとまりが \n で区切られていること（フロントは pre-line で改行を表示する）
"""

import pytest

from audio.analyzer import AudioAnalyzer  # _generate_feedback を呼ぶため


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


# 改善点と伸ばすべきポイントは、同時には全部出せない（例：音程 < 60 と音程 >= 80）。
# そのため、どちらかの項目がなるべく多く出る組み合わせに分けて確かめる
@pytest.mark.parametrize(
    "pitch, rhythm, technique_count, penalty",
    [
        # 改善点：音程・リズム・使いすぎの3つ ／ 伸ばすべきポイント：ビブラート・こぶし・ロングトーン
        (50.0, 50.0, 1, 10.0),
        # 改善点：使いすぎ ／ 伸ばすべきポイント：5つ全部
        (90.0, 90.0, 1, 10.0),
    ],
    ids=["improvements_many", "strengths_all"],
)
def test_feedback_has_three_sections_without_double_period(pitch, rhythm, technique_count, penalty):
    feedback = _analyzer()._generate_feedback(
        pitch, rhythm, _techniques(technique_count), _score_matrix(penalty),
    )

    assert "。。" not in feedback

    sections = feedback.split("\n")
    assert len(sections) == 3
    assert sections[0].startswith("【歌唱特性】")
    assert sections[1].startswith("【改善点】")
    assert sections[2].startswith("【伸ばすべきポイント】")


def test_feedback_without_techniques_has_no_double_period():
    """技法が0回のとき（改善点に「技法を取り入れて」が出る。伸ばすべきポイントは音程・リズムだけ）"""
    feedback = _analyzer()._generate_feedback(90.0, 90.0, _techniques(0), _score_matrix(20.0))

    assert "。。" not in feedback
    assert len(feedback.split("\n")) == 3
