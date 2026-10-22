"""Panel regressions of affordability on its drivers: municipality + year fixed effects, clustered errors.

Coefficients are *adjusted associations*: supply responds to prices and people move to where jobs and
amenities are, so no design here identifies a cause. The functions return tidy tables; the notebook reads them.

Specifications are named by their fixed effects:
* ``year``: municipality + year effects (absorbs national shocks such as the mortgage rate);
* ``region_year``: municipality + NUTS 3 x year effects (also absorbs regional shocks, so the coefficients
  come from differences between municipalities of the same region).
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS

from pthousing.config import MUNI_KEY, YEAR_KEY

REGION = "nuts3_name_2024"
COMPLETION_WINDOW = (
    3  # years of completions summed (t-3 to t-1: lagged so they cannot respond to year t)
)
LABELS = {
    "log_income_real": "Real median income (log)",
    "pop_growth_pct": "Population growth (pp per year)",
    "completions_per_1000": "Completions, 3 years (per 1,000 dwellings)",
    "pop_65plus_pct": "Population aged 65+ (pp)",
    "al_per_1000": "Short-term rentals (per 1,000 dwellings)",
}


def build_frame(panel: pd.DataFrame) -> pd.DataFrame:
    """Regression frame indexed by (muni_code, year) with outcomes and drivers.

    Outcomes: ``log_price_real`` (price per m2) and ``log_pti`` (price-to-income). Drivers:
    ``log_income_real``; ``pop_growth_pct`` (annual log change of resident population x 100);
    ``completions_per_1000`` (dwellings completed in the three previous years per 1,000 dwellings in the 2011
    census, a fixed denominator so the stock does not move with construction); ``pop_65plus_pct``;
    ``al_per_1000`` (registered short-term rentals per 1,000 census 2011 dwellings; mainland only, and
    the stock of still-registered units, which understates the past).
    """
    df = panel.sort_values([MUNI_KEY, YEAR_KEY]).copy()
    by = df.groupby(MUNI_KEY)
    dwellings = df["dwellings_2011_n"].replace(0, np.nan)
    completions = by["completed_n"].transform(
        lambda s: s.shift(1).rolling(COMPLETION_WINDOW, min_periods=COMPLETION_WINDOW).sum()
    )
    out = pd.DataFrame(
        {
            "log_price_real": np.log(df["price_sqm_eur_real"]),
            "log_pti": np.log(df["pti_years"]),
            "log_income_real": np.log(df["income_median_eur_real"]),
            "pop_growth_pct": 100 * by["population_n"].transform(lambda s: np.log(s).diff()),
            "completions_per_1000": 1000 * completions / dwellings,
            "pop_65plus_pct": df["pop_65plus_pct"],
            "al_per_1000": 1000 * df["al_survivor_units_n"] / dwellings,
            REGION: df[REGION],
            "district": df["district"],
            "territory": df["territory"],
        }
    )
    out.index = pd.MultiIndex.from_frame(df[[MUNI_KEY, YEAR_KEY]])
    out["region_year"] = (
        out[REGION].astype(str) + "_" + out.index.get_level_values(YEAR_KEY).astype(str)
    )
    return out


@dataclass
class Spec:
    """One regression: outcome, drivers, fixed effects, sample filter and standard-error clustering."""

    y: str
    xs: list[str]
    effects: str = "year"  # 'year' or 'region_year'
    cluster: str = "muni"  # 'muni' or 'region'
    lag: int = 0  # years by which the drivers are lagged
    sample: dict = field(
        default_factory=dict
    )  # {'territory': ['continente'], 'exclude_district': [...]}


def _sample(frame: pd.DataFrame, years: tuple[int, int], sample: dict) -> pd.DataFrame:
    keep = pd.Series(frame.index.get_level_values(YEAR_KEY), index=frame.index).between(*years)
    if "territory" in sample:
        keep &= frame["territory"].isin(sample["territory"])
    if "exclude_district" in sample:
        keep &= ~frame["district"].isin(sample["exclude_district"])
    return frame[keep]


def fit(frame: pd.DataFrame, spec: Spec, years: tuple[int, int] = (2016, 2023)):
    """Fit one specification and return the linearmodels result (``spec`` is stored in ``res.spec``)."""
    xs = spec.xs
    data = frame
    if spec.lag:
        lagged = frame.groupby(level=MUNI_KEY)[xs].shift(spec.lag)
        data = frame.drop(columns=xs).join(lagged)
    data = _sample(data, years, spec.sample).dropna(subset=[spec.y, *xs])
    exog = data[xs]
    kwargs = {"entity_effects": True}
    if spec.effects == "year":
        kwargs["time_effects"] = True
    elif spec.effects == "region_year":
        kwargs["other_effects"] = data[["region_year"]]
    else:
        raise ValueError(f"effects must be 'year' or 'region_year', not {spec.effects!r}")
    model = PanelOLS(data[spec.y], exog, drop_absorbed=True, **kwargs)
    if spec.cluster == "muni":
        res = model.fit(cov_type="clustered", cluster_entity=True)
    elif spec.cluster == "region":
        clusters = data[[REGION]].astype("category").apply(lambda c: c.cat.codes)
        res = model.fit(cov_type="clustered", clusters=clusters)
    else:
        raise ValueError(f"cluster must be 'muni' or 'region', not {spec.cluster!r}")
    res.spec = spec
    res.sample_frame = data
    return res


def _period(data: pd.DataFrame, effects: str) -> pd.Series:
    """The group whose means the second fixed effect removes: the year, or the region-year."""
    if effects == "region_year":
        return data["region_year"]
    return pd.Series(data.index.get_level_values(YEAR_KEY), index=data.index)


def within_sd(data: pd.DataFrame, xs: list[str], effects: str = "year") -> pd.Series:
    """Standard deviation of each driver after removing municipality and year (or region-year) means.

    Used to express a coefficient per one standard deviation of the variation the model actually uses.
    """
    demeaned = data[xs] - data.groupby(level=MUNI_KEY)[xs].transform("mean")
    return (demeaned - demeaned.groupby(_period(data, effects)).transform("mean")).std()


def coef_table(res, label: str | None = None) -> pd.DataFrame:
    """Tidy coefficients: ``spec``, ``term``, ``coef``, ``se``, ``ci_low``, ``ci_high``, ``p``, ``coef_per_sd``
    (the coefficient times the within standard deviation of the driver), sample sizes and ``r2`` (share of the
    variation left after the fixed effects that the drivers explain)."""
    spec = res.spec
    ci = res.conf_int()
    sd = within_sd(res.sample_frame, list(res.params.index), spec.effects)
    n_munis = res.entity_info["total"]
    return pd.DataFrame(
        {
            "spec": label or spec.y,
            "term": res.params.index,
            "coef": res.params.to_numpy(),
            "se": res.std_errors.to_numpy(),
            "ci_low": ci["lower"].to_numpy(),
            "ci_high": ci["upper"].to_numpy(),
            "p": res.pvalues.to_numpy(),
            "sd_within": sd.reindex(res.params.index).to_numpy(),
            "coef_per_sd": (res.params * sd.reindex(res.params.index)).to_numpy(),
            "n_obs": int(res.nobs),
            "n_munis": int(n_munis),
            "r2": float(res.rsquared),  # of the model after both sets of effects are removed
        }
    )


def vif(data: pd.DataFrame, xs: list[str], effects: str = "year") -> pd.Series:
    """Variance inflation factor of each driver after removing the fixed effects (what the model uses).

    A value above 5 to 10 means the driver is nearly a combination of the others.
    """
    x = data[xs].dropna()
    x = x - x.groupby(level=MUNI_KEY).transform("mean")
    x = x - x.groupby(_period(data.loc[x.index], effects)).transform("mean")
    out = {}
    for col in xs:
        others = x.drop(columns=col).to_numpy()
        y = x[col].to_numpy()
        coef, *_ = np.linalg.lstsq(others, y, rcond=None)
        resid = y - others @ coef
        r2 = 1 - (resid @ resid) / (y @ y)
        out[col] = 1 / (1 - r2)
    return pd.Series(out, name="vif")


def residuals_by_year(res) -> pd.DataFrame:
    """Residuals of a fitted model as a (muni_code, year, residual) table, for spatial checks."""
    return res.resids.rename("residual").reset_index()
