import numpy as np
import pandas as pd
import pytest

from pthousing.analysis import panel as pn


def _panel(n_munis: int = 60, years: range = range(2014, 2024), seed: int = 0) -> pd.DataFrame:
    """Synthetic municipality-year panel: log_pti = 0.5 * x1 - 0.2 * x2 + muni effect + year effect + noise."""
    rng = np.random.default_rng(seed)
    rows = []
    muni_fx = rng.normal(0, 1, n_munis)
    year_fx = rng.normal(0, 0.3, len(years))
    for i in range(n_munis):
        for j, y in enumerate(years):
            x1, x2 = rng.normal(0, 1) + 0.5 * muni_fx[i], rng.normal(0, 1)
            rows.append(
                {
                    "muni_code": f"{i:04d}",
                    "year": y,
                    "x1": x1,
                    "x2": x2,
                    "log_pti": 0.5 * x1 - 0.2 * x2 + muni_fx[i] + year_fx[j] + rng.normal(0, 0.05),
                    "nuts3_name_2024": f"R{i % 6}",
                    "district": f"D{i % 3}",
                    "territory": "azores" if i < 6 else "continente",
                }
            )
    df = pd.DataFrame(rows)
    df["region_year"] = df["nuts3_name_2024"] + "_" + df["year"].astype(str)
    return df.set_index(["muni_code", "year"])


def test_fit_recovers_coefficients_despite_municipality_effects():
    res = pn.fit(_panel(), pn.Spec("log_pti", ["x1", "x2"]), years=(2014, 2023))
    table = pn.coef_table(res).set_index("term")
    assert table.loc["x1", "coef"] == pytest.approx(0.5, abs=0.02)
    assert table.loc["x2", "coef"] == pytest.approx(-0.2, abs=0.02)
    assert table.loc["x1", "p"] < 0.001
    assert table.loc["x1", "n_munis"] == 60 and table.loc["x1", "n_obs"] == 600


def test_coefficient_per_sd_uses_within_variation():
    res = pn.fit(_panel(), pn.Spec("log_pti", ["x1", "x2"]), years=(2014, 2023))
    table = pn.coef_table(res).set_index("term")
    assert table.loc["x2", "coef_per_sd"] == pytest.approx(table.loc["x2", "coef"] * 1.0, abs=0.05)
    assert table.loc["x1", "sd_within"] < _panel()["x1"].std()  # muni means removed


def test_region_year_effects_and_region_clustering_run_and_agree():
    frame = _panel()
    base = pn.coef_table(pn.fit(frame, pn.Spec("log_pti", ["x1"])))
    rey = pn.coef_table(pn.fit(frame, pn.Spec("log_pti", ["x1"], effects="region_year")))
    clu = pn.coef_table(pn.fit(frame, pn.Spec("log_pti", ["x1"], cluster="region")))
    assert rey["coef"].iloc[0] == pytest.approx(base["coef"].iloc[0], abs=0.03)
    assert clu["coef"].iloc[0] == pytest.approx(base["coef"].iloc[0])
    assert clu["se"].iloc[0] != pytest.approx(base["se"].iloc[0])


def test_sample_filters_and_year_window():
    frame = _panel()
    mainland = pn.fit(frame, pn.Spec("log_pti", ["x1"], sample={"territory": ["continente"]}))
    assert pn.coef_table(mainland)["n_munis"].iloc[0] == 54
    no_d0 = pn.fit(frame, pn.Spec("log_pti", ["x1"], sample={"exclude_district": ["D0"]}))
    assert pn.coef_table(no_d0)["n_munis"].iloc[0] == 40
    short = pn.fit(frame, pn.Spec("log_pti", ["x1"]), years=(2020, 2023))
    assert pn.coef_table(short)["n_obs"].iloc[0] == 60 * 4


def test_spec_years_override_the_window():
    res = pn.fit(_panel(), pn.Spec("log_pti", ["x1"], years=(2014, 2017)), years=(2014, 2023))
    assert pn.coef_table(res)["n_obs"].iloc[0] == 60 * 4


def test_lagged_drivers_drop_the_first_year():
    res = pn.fit(_panel(), pn.Spec("log_pti", ["x1"], lag=1), years=(2014, 2023))
    assert pn.coef_table(res)["n_obs"].iloc[0] == 60 * 9
    assert abs(pn.coef_table(res)["coef"].iloc[0]) < 0.15  # a lagged random driver explains little


def test_bad_options_are_rejected():
    frame = _panel()
    with pytest.raises(ValueError, match="effects"):
        pn.fit(frame, pn.Spec("log_pti", ["x1"], effects="none"))
    with pytest.raises(ValueError, match="cluster"):
        pn.fit(frame, pn.Spec("log_pti", ["x1"], cluster="country"))


def test_vif_flags_collinear_drivers():
    frame = _panel()
    rng = np.random.default_rng(1)
    frame["x3"] = frame["x1"] + rng.normal(0, 0.05, len(frame))
    flagged = pn.vif(frame, ["x1", "x2", "x3"])
    assert flagged["x1"] > 50 and flagged["x3"] > 50
    assert flagged["x2"] < 1.5
    assert pn.vif(frame, ["x1", "x2"]).max() < 2


def test_residuals_table_has_one_row_per_observation():
    res = pn.fit(_panel(), pn.Spec("log_pti", ["x1"]), years=(2014, 2023))
    resid = pn.residuals_by_year(res)
    assert len(resid) == 600 and set(resid.columns) == {"muni_code", "year", "residual"}


def test_build_frame_constructs_drivers_from_the_processed_panel():
    rows = []
    for muni, pop0 in (("0101", 1000.0), ("0102", 2000.0)):
        for k, year in enumerate(range(2012, 2018)):
            rows.append(
                {
                    "muni_code": muni,
                    "year": year,
                    "price_sqm_eur_real": 1000.0 + 10 * k,
                    "pti_years": 10.0,
                    "income_median_eur_real": 12000.0,
                    "population_n": pop0 * 1.01**k,
                    "foreign_residents_n": 100.0 + 10.0 * k,
                    "pop_65plus_pct": 20.0,
                    "completed_n": 10.0 * (k + 1),
                    "dwellings_2011_n": 500,
                    "al_survivor_units_n": 5.0,
                    "nuts3_name_2024": "A",
                    "district": "D",
                    "territory": "continente",
                }
            )
    frame = pn.build_frame(pd.DataFrame(rows))
    row = frame.loc[("0101", 2016)]
    assert row["pop_growth_pct"] == pytest.approx(100 * np.log(1.01))
    # completions of 2013, 2014 and 2015 (k = 1, 2, 3 -> 20, 30, 40) over 500 dwellings x 1,000
    assert row["completions_per_1000"] == pytest.approx(1000 * (20 + 30 + 40) / 500)
    assert np.isnan(frame.loc[("0101", 2013), "completions_per_1000"])
    assert row["al_per_1000"] == pytest.approx(10.0)
    last_pop = 1000.0 * 1.01**3  # population of 2015
    assert row["foreign_change_pct"] == pytest.approx(100 * 10.0 / last_pop)
    total_change = 100 * (1000.0 * 1.01**4 - last_pop) / last_pop
    assert row["pop_change_ex_foreign_pct"] + row["foreign_change_pct"] == pytest.approx(
        total_change
    )
    assert row["log_pti"] == pytest.approx(np.log(10.0))
    assert frame.index.names == ["muni_code", "year"]


def test_add_spatial_lags_uses_neighbours_in_the_same_or_an_earlier_year():
    import geopandas as gpd
    from shapely.geometry import box

    from pthousing.analysis import spatial
    from pthousing.config import CRS_METRIC

    codes = ["0101", "0102", "0103"]  # three squares in a row: 0102 touches both others
    geo = gpd.GeoDataFrame(
        {"muni_code": codes, "territory": "continente",
         "geometry": [box(i * 1000, 0, (i + 1) * 1000, 1000) for i in range(3)]},
        crs=CRS_METRIC,
    )  # fmt: skip
    w = spatial.build_weights(geo)
    index = pd.MultiIndex.from_product([codes, [2020, 2021]], names=["muni_code", "year"])
    frame = pd.DataFrame({"v": [1.0, 2.0, 10.0, 20.0, 100.0, 200.0]}, index=index)
    same = pn.add_spatial_lags(frame, w, ["v"])
    assert same.loc[("0102", 2020), "w_v"] == pytest.approx((1.0 + 100.0) / 2)
    assert same.loc[("0101", 2021), "w_v"] == pytest.approx(20.0)
    earlier = pn.add_spatial_lags(frame, w, ["v"], shift=1)
    assert np.isnan(earlier.loc[("0102", 2020), "w_v_l1"])
    assert earlier.loc[("0102", 2021), "w_v_l1"] == pytest.approx((1.0 + 100.0) / 2)
