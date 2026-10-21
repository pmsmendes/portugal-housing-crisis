import pytest

from pthousing.viz import style


def test_color_conversion_roundtrips_exactly():
    for color in ("#e34948", "#2a78d6", "#86b6ef", "#0d366b", "#f0efec"):
        assert style.oklch_to_hex(*style.hex_to_oklch(color)) == color


def test_sequential_ramp_gets_darker_at_every_step():
    lightness = [style.hex_to_oklch(c)[0] for c in style.SEQUENTIAL_6]
    assert all(a > b + 0.05 for a, b in zip(lightness, lightness[1:], strict=False))


def test_diverging_ramp_arms_have_equal_lightness():
    ramp = style.diverging_ramp(3)
    cool = [style.hex_to_oklch(c)[0] for c in ramp[:3]]
    warm = [style.hex_to_oklch(c)[0] for c in ramp[3:]][::-1]
    assert cool == pytest.approx(warm, abs=0.01)
    assert len(ramp) == 6 and len(style.diverging_ramp(2)) == 4


def test_save_fig_and_table_write_under_reports_and_reject_unknown_phase(tmp_path, monkeypatch):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    monkeypatch.setattr(style, "FIGURES", tmp_path / "figures")
    monkeypatch.setattr(style, "TABLES", tmp_path / "tables")
    fig, _ = plt.subplots()
    assert style.save_fig(fig, "p1", "demo") == tmp_path / "figures" / "p1" / "demo.png"
    assert (tmp_path / "figures" / "p1" / "demo.png").exists()
    path = style.save_table(pd.DataFrame({"a": [1]}), "p1", "demo")
    assert path == tmp_path / "tables" / "p1" / "demo.csv" and path.read_text().startswith("a\n1")
    with pytest.raises(ValueError):
        style.save_fig(fig, "p9", "x")
    with pytest.raises(ValueError):
        style.save_table(pd.DataFrame(), "p9", "x")
