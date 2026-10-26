import pandas as pd
import pytest

from pthousing.analysis import evidence as ev


def _table():
    rows = [
        ("a", "x", 0.5, 0.01, 0.1),
        ("b", "x", 0.4, 0.03, 0.08),
        ("c", "x", 0.2, 0.40, 0.04),
        ("a", "y", 0.1, 0.60, 0.01),
        ("b", "y", -0.3, 0.01, -0.05),
        ("a", "z", 0.5, 0.01, 0.1),
        ("b", "z", -0.5, 0.01, -0.1),
    ]
    return pd.DataFrame(rows, columns=["spec", "term", "coef", "p", "coef_per_sd"])


def test_rungs_follow_the_given_order_and_keep_missing_as_nan():
    out = ev.rungs(_table(), "x", ["c", "a", "zz"])
    assert out["spec"].tolist() == ["c", "a", "zz"]
    assert out["coef"].iloc[1] == 0.5
    assert pd.isna(out["p"].iloc[2])


@pytest.mark.parametrize(
    ("term", "specs", "expected"),
    [
        ("x", ["a", "b"], "holds"),
        ("x", ["a", "b", "c"], "fades"),
        ("y", ["a", "b"], "emerges"),
        ("z", ["a", "b"], "flips"),
        ("y", ["a"], "never"),
    ],
)
def test_classify_reads_the_path(term, specs, expected):
    assert ev.classify(ev.rungs(_table(), term, specs)) == expected


def test_classify_without_estimates_and_mixed():
    assert ev.classify(ev.rungs(_table(), "q", ["a"])) == "not estimated"
    mixed = pd.DataFrame({"p": [0.01, 0.4, 0.01], "coef": [1.0, 1.0, 1.0]})
    assert ev.classify(mixed) == "mixed"


def test_design_verdict_and_summary():
    assert ev.design_verdict(0.024, "fails") == "assumption rejected"
    assert ev.design_verdict(0.668, "fails") == "assumption not rejected"
    with pytest.raises(ValueError):
        ev.design_verdict(0.5, "passes")
    counts = ev.summary(pd.Series(["holds", "never", "never"]))
    assert counts["never"] == 2 and counts["fades"] == 0 and counts.index[0] == "holds"
