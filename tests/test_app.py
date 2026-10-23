from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

APP = Path(__file__).resolve().parents[1] / "app" / "pages"


def _run(page):
    at = AppTest.from_file(str(APP / page), default_timeout=90)
    return at.run()


def test_simulator_page_runs_with_defaults_and_shows_no_policy_cost():
    at = _run("4_Simulator.py")
    assert not at.exception
    labels = [m.label for m in at.metric]
    assert any(label.startswith("Price-to-income") for label in labels)
    assert any("none selected" in m.value for m in at.metric)


def test_simulator_policy_slider_adds_a_cost():
    at = _run("4_Simulator.py")
    construction = next(s for s in at.sidebar.slider if s.label == "Extra completions a year")
    construction.set_value(10_000)
    at.run()
    assert not at.exception
    cost = next(m for m in at.metric if m.label.startswith("Budget cost to"))
    assert float(cost.value.split()[0]) > 0


@pytest.mark.parametrize("page", ["1_Geographic.py", "2_Trends.py", "3_Explanatory.py"])
def test_page_runs_with_defaults(page):
    at = _run(page)
    assert not at.exception


def test_home_shows_headline_numbers():
    at = AppTest.from_file(str(APP.parent / "Home.py"), default_timeout=90).run()
    assert not at.exception
    assert len(at.metric) == 3


def test_geographic_change_mode_and_islands_run():
    at = _run("1_Geographic.py")
    at.sidebar.radio[0].set_value("Change between two years")
    at.run()
    assert not at.exception
    at.sidebar.radio[1].set_value("azores")
    at.run()
    assert not at.exception


def test_geographic_every_indicator_runs():
    from pthousing.viz import dashboard as D

    at = _run("1_Geographic.py")
    for column in D.INDICATORS:
        at.sidebar.selectbox[0].set_value(column)
        at.run()
        assert not at.exception, column
