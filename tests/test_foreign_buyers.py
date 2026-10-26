import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import foreign_buyers as fb


def _buyer(n=40, seed=0):
    """Q4 snapshots 2019-2025 for n municipalities; the first 10 have a foreign price every year."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        code = f"{i + 101:04d}"
        base = rng.uniform(800, 1500)
        for year in range(2019, 2026):
            dom = base * 1.07 ** (year - 2019)
            rows.append((code, year, "domestic", dom))
            rows.append((code, year, "total", dom * 1.01))
            if i < 10:
                rows.append((code, year, "foreign", dom * 1.25))
    df = pd.DataFrame(rows, columns=["muni_code", "year", "buyer", "price_sqm_eur"])
    df["period_start"] = pd.to_datetime(df["year"].astype(str) + "-10-01")
    df["quarter"] = 4
    return df


def _sales(n=40):
    rows = [
        (f"{i + 101:04d}", y, 4, "total", 100.0 + 10 * i)
        for i in range(n)
        for y in range(2019, 2026)
    ]
    return pd.DataFrame(rows, columns=["muni_code", "year", "quarter", "category", "sales_12m_n"])


def _info(n=40):
    codes = [f"{i + 101:04d}" for i in range(n)]
    return pd.DataFrame(
        {
            "coast_class": ["coast" if i < 20 else "inland" for i in range(n)],
            "density_class": ["urban" if i % 3 == 0 else "rural" for i in range(n)],
            "tourist": ["tourist" if i < 10 else "other" for i in range(n)],
            "area": ["A" if i % 2 else "B" for i in range(n)],
        },
        index=pd.Index(codes, name="muni_code"),
    )


def test_national_premium_is_the_foreign_median_over_the_domestic_one():
    quarters = pd.date_range("2019-10-01", periods=3, freq="QS")
    prices = (
        ("domestic", 1000.0),
        ("foreign", 1500.0),
        ("eu", 1200.0),
        ("other_foreign", 2000.0),
        ("total", 1050.0),
    )
    rows = [(t, b, v) for t in quarters for b, v in prices]
    nat = pd.DataFrame(rows, columns=["period_start", "buyer", "price_sqm_eur"])
    out = fb.national_premium(nat)
    assert np.allclose(out["premium_foreign_pct"], 50.0)
    assert np.allclose(out["premium_eu_pct"], 20.0)
    assert np.allclose(out["premium_other_foreign_pct"], 100.0)


def test_foreign_markets_counts_priced_municipalities_and_their_share_of_sales():
    out = fb.foreign_markets(_buyer(), _sales())
    assert (out["foreign_priced_n"] == 10).all() and (out["priced_n"] == 40).all()
    expected = 100 * sum(100 + 10 * i for i in range(10)) / sum(100 + 10 * i for i in range(40))
    assert out["share_of_sales_pct"].iloc[0] == pytest.approx(expected)
    assert out["median_premium_pct"].iloc[0] == pytest.approx(25.0)


def test_foreign_presence_flags_municipalities_with_enough_years():
    buyer = _buyer()
    foreign = buyer["buyer"] == "foreign"
    # four years left for 0101 (still a market), two for 0102 (not)
    buyer = buyer[~((buyer["muni_code"] == "0101") & foreign & (buyer["year"] < 2022))]
    buyer = buyer[~((buyer["muni_code"] == "0102") & foreign & (buyer["year"] < 2024))]
    out = fb.foreign_presence(buyer, min_years=4)
    assert out.loc["0101", "foreign_years_n"] == 4 and out.loc["0101", "foreign_market"]
    assert out.loc["0102", "foreign_years_n"] == 2 and not out.loc["0102", "foreign_market"]
    assert out.loc["0140", "foreign_years_n"] == 0


def test_cross_section_growth_uses_domestic_prices_and_keeps_the_flag():
    cs = fb.cross_section(_buyer(), _sales(), _info())
    assert len(cs) == 40 and int(cs["foreign_market"].sum()) == 10
    assert cs["growth_log_pts"].iloc[0] == pytest.approx(100 * 6 * np.log(1.07))


def test_association_recovers_a_planted_effect_and_not_a_null():
    cs = fb.cross_section(_buyer(), _sales(), _info())
    rng = np.random.default_rng(3)
    planted = cs.assign(growth_log_pts=rng.normal(40, 3, len(cs)) + 10 * cs["foreign_market"])
    out = fb.association(planted, "growth_log_pts")
    assert out.loc["district", "coef"] == pytest.approx(10, abs=4)
    null = fb.association(cs.assign(growth_log_pts=rng.normal(40, 3, len(cs))), "growth_log_pts")
    assert abs(null.loc["district", "coef"]) < 5
    assert list(out.index) == list(fb.SPECS)


def test_by_group_reports_share_and_growth_for_markets_and_others():
    cs = fb.cross_section(_buyer(), _sales(), _info())
    out = fb.by_group(cs, "coast_class")
    assert (
        out.loc["coast", "foreign_markets_n"] == 10 and out.loc["inland", "foreign_markets_n"] == 0
    )
    assert out.loc["coast", "foreign_market_share_pct"] == pytest.approx(50.0)
