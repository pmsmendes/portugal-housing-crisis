"""Capitalisation of municipal IMI rate cuts: event table, stacked event study, dose-response and placebos.

Treatment is a cut in the municipal urban IMI rate. Rates are chosen by councils, not assigned, so the
estimates are causal only if the pre-period coefficients are flat (``EventStudy.pretrend_p``); otherwise they
are adjusted associations. Units: rate changes in percentage points (``change_pp``) and, for doses, in
0.01 pp (``DOSE_UNIT_PP``); log outcomes in natural logs (100 x coefficient = % effect).

* ``rate_events`` lists the rate changes with an *isolated* flag (no other change in the window).
* ``build_stacks`` + ``event_study``: one stack per event year, treated municipalities against municipalities
  whose rate did not change in the window, compared within the same NUTS 3 region and year.
* ``cohort_did``: the same comparison as separate 2x2 differences per cohort, averaged with a municipality
  bootstrap; it does not mix cohorts in one regression, so it is the check on the pooled estimate.
* ``dose_response``: log price growth on the size of the cut (and its lags), all changes, not only isolated ones.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from scipy import stats

from pthousing.analysis import panel as pn
from pthousing.config import MUNI_KEY, YEAR_KEY

REGION = "nuts3_name_2024"
DOSE_UNIT_PP = 0.01  # one dose unit = a 0.01 pp change in the rate
TOLERANCE = 1e-9
PARISH_LINK_FROM = (
    2013  # the 2012 pages show the parish link for 206 municipalities: another convention
)
RATE_FLOOR_PCT = 0.30  # the legal minimum of the urban rate: municipalities there cannot cut


def build_frame(panel: pd.DataFrame) -> pd.DataFrame:
    """Long frame (one row per municipality-year) with the outcomes and the rate columns used here.

    ``log_price_real``, ``log_pti`` (price-to-income, the affordability outcome) and ``log_rent_real``;
    ``d_log_price`` (annual change of the log price); ``rate_pct`` and ``change_pp`` of the urban IMI rate.
    """
    df = panel.sort_values([MUNI_KEY, YEAR_KEY]).copy()
    by = df.groupby(MUNI_KEY)
    out = pd.DataFrame(
        {
            MUNI_KEY: df[MUNI_KEY],
            YEAR_KEY: df[YEAR_KEY],
            "region": df[REGION],
            "district": df["district"],
            "territory": df["territory"],
            "log_price_real": np.log(df["price_sqm_eur_real"]),
            "log_pti": np.log(df["pti_years"]),
            "log_rent_real": np.log(df["rent_sqm_eur_real"]),
            "rate_pct": df["imi_urban_pct"],
            "change_pp": df["imi_change_pp"],
            "parish_rates": df["imi_parish_rates"].astype("boolean"),
            "deduction_link": df["imi_deduction_link"].astype("boolean"),
        }
    )
    out["d_log_price"] = out.groupby(MUNI_KEY)["log_price_real"].diff()
    out["d_log_price"] = out["d_log_price"].where(by[YEAR_KEY].diff() == 1)
    return out.reset_index(drop=True)


# ---- events ---------------------------------------------------------------------------------------


def _wide(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return frame.pivot(index=MUNI_KEY, columns=YEAR_KEY, values=column).astype(float)


def _window_state(
    change: pd.DataFrame, offsets: range
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """For every municipality-year ``t``: all changes at ``t + offsets`` observed, how many are nonzero.

    Returns (observed, n_changes, n_changes_excluding_t) as wide frames; years whose window leaves the data
    are not observed.
    """
    years = change.columns
    observed = pd.DataFrame(True, index=change.index, columns=years)
    n_changes = pd.DataFrame(0, index=change.index, columns=years)
    for k in offsets:
        shifted = change.reindex(columns=years + k)
        shifted.columns = years
        observed &= shifted.notna()
        n_changes += (shifted.abs() > TOLERANCE).fillna(False).astype(int)
    return observed, n_changes, n_changes - (change.abs() > TOLERANCE).fillna(False).astype(int)


def rate_events(frame: pd.DataFrame, iso_before: int = 2, iso_after: int = 1) -> pd.DataFrame:
    """Every nonzero change of the urban rate, flagged for whether it is isolated.

    A change in year ``t`` is *isolated* when the changes of ``t - iso_before`` to ``t + iso_after`` are all
    observed and none other than the one in ``t`` is nonzero. Columns: ``muni_code``, ``event_year``,
    ``change_pp`` (negative = cut), ``rate_before_pct``, ``observed`` (window fully observed), ``isolated``.
    """
    change = _wide(frame, "change_pp")
    rate = _wide(frame, "rate_pct")
    observed, _, others = _window_state(change, range(-iso_before, iso_after + 1))
    events = change.stack().rename("change_pp").reset_index()
    events = events[events["change_pp"].abs() > TOLERANCE].rename(columns={YEAR_KEY: "event_year"})
    key = [events[MUNI_KEY], events["event_year"]]
    idx = pd.MultiIndex.from_arrays(key)
    events["observed"] = observed.stack().reindex(idx).to_numpy()
    events["isolated"] = events["observed"] & (others.stack().reindex(idx).to_numpy() == 0)
    events["rate_before_pct"] = (
        rate.stack().reindex(idx) - events["change_pp"].to_numpy()
    ).to_numpy()
    events["rate_before_pct"] = events["rate_before_pct"].round(4)
    return events.reset_index(drop=True)[
        [MUNI_KEY, "event_year", "change_pp", "rate_before_pct", "observed", "isolated"]
    ]


# ---- stacks ---------------------------------------------------------------------------------------


def build_stacks(
    frame: pd.DataFrame,
    outcome: str = "log_price_real",
    pre: int = 2,
    post: int = 2,
    iso_before: int = 2,
    iso_after: int = 1,
    min_cut_pp: float = 0.0,
    control_min_rate_pct: float | None = None,
    event_years: tuple[int, int] | None = None,
    exclude_events: set[int] | None = None,
    drop_munis: set[str] | None = None,
    sample: dict | None = None,
) -> pd.DataFrame:
    """Stacked event-study sample, one stack per event year.

    Treated: municipalities with an isolated cut of at least ``min_cut_pp`` in the event year. Controls: all
    municipalities with no change from ``iso_before`` years before to the end of the outcome window
    (``max(iso_after, post)`` years after); with ``control_min_rate_pct`` only those above that rate the year
    before, which drops municipalities at the floor that cannot cut.
    Units need the outcome in every year of ``event - pre`` to ``event + post``; others drop out of that stack.
    ``exclude_events`` removes event years (and their stacks), ``drop_munis`` removes municipalities.
    ``sample`` is {'territory': [...], 'parish_free': True, 'stable_deduction': True}: ``parish_free`` drops
    municipalities that show the parish-rate link in any year from ``PARISH_LINK_FROM``; ``stable_deduction``
    drops units whose family-deduction status (IMI Familiar link) changes inside their outcome window.

    Returns long rows: ``stack``, ``unit`` (municipality-stack), ``muni_code``, ``year``, ``k`` (event time),
    ``treated``, ``dose`` (size of the cut in 0.01 pp; 0 for controls), ``y``, ``region``, ``cell``
    (region-stack-year, the fixed effect that makes the comparison within region and year).
    """
    sample = sample or {}
    base = frame
    if "territory" in sample:
        base = base[base["territory"].isin(sample["territory"])]
    if sample.get("parish_free"):
        linked = base[base[YEAR_KEY] >= PARISH_LINK_FROM].groupby(MUNI_KEY)["parish_rates"]
        ever = linked.apply(lambda s: bool(s.fillna(False).any()))
        base = base[~base[MUNI_KEY].isin(ever[ever].index)]
    if drop_munis:
        base = base[~base[MUNI_KEY].isin(drop_munis)]

    change = _wide(base, "change_pp")
    rate = _wide(base, "rate_pct")
    # controls stay quiet over the whole outcome window, or a control's own cut at e + 2 would leak into k = 2
    observed, n_changes, _ = _window_state(change, range(-iso_before, max(iso_after, post) + 1))
    events = rate_events(base, iso_before, iso_after)
    treated_events = events[
        events["isolated"]
        & (events["change_pp"] < -TOLERANCE)
        & (-events["change_pp"] >= min_cut_pp - TOLERANCE)
    ]
    if event_years:
        treated_events = treated_events[treated_events["event_year"].between(*event_years)]
    if exclude_events:
        treated_events = treated_events[~treated_events["event_year"].isin(exclude_events)]

    outcomes = base.pivot(index=MUNI_KEY, columns=YEAR_KEY, values=outcome)
    deduction = base.pivot(index=MUNI_KEY, columns=YEAR_KEY, values="deduction_link").astype(float)
    regions = base.drop_duplicates(MUNI_KEY).set_index(MUNI_KEY)["region"]
    parts = []
    for year, treated in treated_events.groupby("event_year"):
        window = list(range(year - pre, year + post + 1))
        if not set(window) <= set(outcomes.columns):
            continue
        has_outcome = outcomes[window].notna().all(axis=1)
        if sample.get("stable_deduction"):
            has_outcome &= deduction[window].nunique(axis=1) <= 1
        is_control = observed[year] & (n_changes[year] == 0) & has_outcome
        if control_min_rate_pct is not None:
            is_control &= rate[year - 1] > control_min_rate_pct + TOLERANCE
        controls = is_control[is_control].index
        cuts = treated.set_index(MUNI_KEY)["change_pp"]
        cuts = cuts[cuts.index.isin(has_outcome[has_outcome].index)]
        units = pd.concat(
            [
                pd.DataFrame({MUNI_KEY: cuts.index, "treated": True, "dose": -cuts / DOSE_UNIT_PP}),
                pd.DataFrame({MUNI_KEY: controls, "treated": False, "dose": 0.0}),
            ],
            ignore_index=True,
        )
        long = units.merge(
            outcomes[window]
            .rename_axis(columns=None)
            .reset_index()
            .melt(id_vars=MUNI_KEY, var_name=YEAR_KEY, value_name="y"),
            on=MUNI_KEY,
        )
        long[YEAR_KEY] = long[YEAR_KEY].astype(int)
        long["stack"] = int(year)
        long["k"] = long[YEAR_KEY] - int(year)
        long["region"] = long[MUNI_KEY].map(regions)
        parts.append(long)
    if not parts:
        return pd.DataFrame(
            columns=[
                "stack", "unit", MUNI_KEY, YEAR_KEY, "k", "treated", "dose", "y", "region", "cell",
            ]
        )  # fmt: skip
    out = pd.concat(parts, ignore_index=True)
    out["unit"] = out[MUNI_KEY] + "_" + out["stack"].astype(str)
    out["cell"] = (
        out["region"].astype(str) + "_" + out["stack"].astype(str) + "_" + out[YEAR_KEY].astype(str)
    )
    return out[["stack", "unit", MUNI_KEY, YEAR_KEY, "k", "treated", "dose", "y", "region", "cell"]]


# ---- event study ----------------------------------------------------------------------------------


@dataclass
class EventStudy:
    """Coefficients by event time (reference k = -1) and the joint test of the pre-period coefficients."""

    table: pd.DataFrame  # k, coef, se, ci_low, ci_high, p
    pretrend_p: float  # Wald test that all k < -1 coefficients are zero (NaN if there is only one)
    n_treated: int
    n_controls: int
    n_stacks: int
    res: object = None


def _wald_p(params: pd.Series, cov: pd.DataFrame) -> float:
    if len(params) == 0:
        return np.nan
    stat = float(params.to_numpy() @ np.linalg.solve(cov.to_numpy(), params.to_numpy()))
    return float(stats.chi2.sf(stat, len(params)))


def event_study(stacks: pd.DataFrame, dose: bool = True) -> EventStudy:
    """Stacked event study: unit-stack effects + region-stack-year effects, errors clustered by municipality.

    With ``dose`` the coefficients are the effect on the outcome of a 0.01 pp cut; otherwise of a cut of
    any size. The reference period is k = -1 (the year before the event year).
    """
    data = stacks.copy()
    ks = sorted(k for k in data["k"].unique() if k != -1)
    treat = data["dose"] if dose else data["treated"].astype(float)
    exog = pd.DataFrame({f"k{k}": treat * (data["k"] == k) for k in ks}, index=data.index)
    data = data.set_index(["unit", YEAR_KEY])
    exog.index = data.index
    other = data[["cell"]].astype("category")
    clusters = data[[MUNI_KEY]].astype("category").apply(lambda c: c.cat.codes)
    model = PanelOLS(data["y"], exog, entity_effects=True, other_effects=other, drop_absorbed=True)
    res = model.fit(cov_type="clustered", clusters=clusters)
    ci = res.conf_int()
    table = pd.DataFrame(
        {
            "k": [int(t[1:]) for t in res.params.index],
            "coef": res.params.to_numpy(),
            "se": res.std_errors.to_numpy(),
            "ci_low": ci["lower"].to_numpy(),
            "ci_high": ci["upper"].to_numpy(),
            "p": res.pvalues.to_numpy(),
        }
    )
    pre_terms = [f"k{k}" for k in ks if k < -1 and f"k{k}" in res.params.index]
    pretrend = _wald_p(res.params[pre_terms], res.cov.loc[pre_terms, pre_terms])
    unit = data.reset_index().drop_duplicates("unit")
    return EventStudy(
        table=table,
        pretrend_p=pretrend,
        n_treated=int(unit["treated"].sum()),
        n_controls=int((~unit["treated"]).sum()),
        n_stacks=int(unit["stack"].nunique()),
        res=res,
    )


def cumulative(res, terms: list[str]) -> dict[str, float]:
    """Sum of the coefficients ``terms`` of a ``linearmodels`` result, with its standard error and 95% interval.

    Meaningful for coefficients on *changes* (the dose-response: this year's plus last year's effect on growth).
    The event-study coefficients are levels against k = -1, so the k = +2 coefficient already is the
    two-year effect and must not be summed.
    """
    beta = res.params[terms]
    var = float(res.cov.loc[terms, terms].to_numpy().sum())
    total, se = float(beta.sum()), float(np.sqrt(var))
    return {"coef": total, "se": se, "ci_low": total - 1.96 * se, "ci_high": total + 1.96 * se}


# ---- cohort-by-cohort 2x2 differences (check on the pooled regression) ----------------------------


def _region_demeaned_slope(
    delta: np.ndarray, x: np.ndarray, region: np.ndarray, w: np.ndarray
) -> float:
    """Weighted slope of ``delta`` on ``x`` after removing region means (OLS with region dummies)."""
    codes, inverse = np.unique(region, return_inverse=True)
    totals = np.bincount(inverse, weights=w, minlength=len(codes))
    mx = np.bincount(inverse, weights=w * x, minlength=len(codes)) / np.where(totals > 0, totals, 1)
    md = np.bincount(inverse, weights=w * delta, minlength=len(codes)) / np.where(
        totals > 0, totals, 1
    )
    xt, dt = x - mx[inverse], delta - md[inverse]
    denominator = float(np.sum(w * xt * xt))
    return float(np.sum(w * xt * dt) / denominator) if denominator > 0 else np.nan


def cohort_did(
    stacks: pd.DataFrame, dose: bool = True, n_boot: int = 300, seed: int = 0
) -> pd.DataFrame:
    """Per-cohort 2x2 differences against k = -1, averaged over cohorts weighted by their treated units.

    For each stack and k: slope of ``y(e+k) - y(e-1)`` on the treatment (dose or 0/1) with region effects,
    i.e. treated against controls of the same region. Standard errors and the interval come from a bootstrap
    of municipalities (the same municipality is resampled in every stack it appears in).
    Returns k, coef, se, ci_low, ci_high (percentile) and the number of cohorts used.
    """
    wide = stacks.pivot_table(index=["stack", MUNI_KEY], columns="k", values="y", aggfunc="first")
    meta = stacks.drop_duplicates(["stack", MUNI_KEY]).set_index(["stack", MUNI_KEY])
    x = (meta["dose"] if dose else meta["treated"].astype(float)).reindex(wide.index).to_numpy()
    treated = meta["treated"].reindex(wide.index).to_numpy()
    region = meta["region"].reindex(wide.index).astype(str).to_numpy()
    stack = wide.index.get_level_values("stack").to_numpy()
    munis = wide.index.get_level_values(MUNI_KEY)
    ks = [k for k in wide.columns if k != -1]
    deltas = {k: (wide[k] - wide[-1]).to_numpy() for k in ks}

    def estimate(weights: np.ndarray) -> dict[int, float]:
        out = {}
        for k in ks:
            num = den = 0.0
            for s in np.unique(stack):
                in_stack = stack == s
                w = weights[in_stack]
                n_t = float(np.sum(w * treated[in_stack]))
                if n_t <= 0:
                    continue
                b = _region_demeaned_slope(deltas[k][in_stack], x[in_stack], region[in_stack], w)
                if np.isfinite(b):
                    num, den = num + n_t * b, den + n_t
            out[k] = num / den if den > 0 else np.nan
        return out

    point = estimate(np.ones(len(wide)))
    codes, inverse = np.unique(munis, return_inverse=True)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        counts = rng.multinomial(len(codes), np.full(len(codes), 1 / len(codes)))
        draws.append(estimate(counts[inverse].astype(float)))
    boot = pd.DataFrame(draws)
    return pd.DataFrame(
        {
            "k": ks,
            "coef": [point[k] for k in ks],
            "se": [boot[k].std() for k in ks],
            "ci_low": [boot[k].quantile(0.025) for k in ks],
            "ci_high": [boot[k].quantile(0.975) for k in ks],
            "n_cohorts": len(np.unique(stack)),
        }
    )


# ---- dose-response --------------------------------------------------------------------------------


def dose_frame(
    frame: pd.DataFrame, lags: tuple[int, ...] = (0, 1), leads: tuple[int, ...] = ()
) -> pd.DataFrame:
    """Regression frame for ``dose_response``, indexed by (muni_code, year).

    ``cut_l<j>``: the cut of ``j`` years ago in 0.01 pp (positive = cut; increases are negative), ``cut_f<j>``:
    the cut ``j`` years ahead (a placebo). ``d_log_price_l1`` is last year's price growth (cuts may follow
    booms); ``rate_before_pct`` the rate of the previous year.
    """
    df = frame.sort_values([MUNI_KEY, YEAR_KEY]).copy()
    df["cut"] = -df["change_pp"] / DOSE_UNIT_PP
    by = df.groupby(MUNI_KEY)
    for j in lags:
        df[f"cut_l{j}"] = by["cut"].shift(j)
    for j in leads:
        df[f"cut_f{j}"] = by["cut"].shift(-j)
    df["d_log_price_l1"] = by["d_log_price"].shift(1)
    df["rate_before_pct"] = by["rate_pct"].shift(1)
    df = df.set_index([MUNI_KEY, YEAR_KEY])
    df["region_year"] = (
        df["region"].astype(str) + "_" + df.index.get_level_values(YEAR_KEY).astype(str)
    )
    return df


def dose_response(
    frame: pd.DataFrame,
    lags: tuple[int, ...] = (0, 1),
    leads: tuple[int, ...] = (),
    outcome: str = "d_log_price",
    controls: tuple[str, ...] = (),
    years: tuple[int, int] = (2016, 2025),
    sample: dict | None = None,
    effects: str = "region_year",
):
    """Annual change of the outcome on the size of the rate cut (and its lags/leads): municipality +
    region-year effects, errors clustered by municipality. Returns the ``panel.fit`` result; read it with
    ``panel.coef_table``. ``outcome`` must be an annual change (``d_log_price``) or a level to be differenced
    by the caller."""
    data = dose_frame(frame, lags, leads)
    xs = [f"cut_l{j}" for j in lags] + [f"cut_f{j}" for j in leads] + list(controls)
    spec = pn.Spec(outcome, xs, effects=effects, sample=sample or {}, years=years)
    return pn.fit(data, spec, years=years)


# ---- benchmark ------------------------------------------------------------------------------------


def full_capitalisation_pct(cut_pp: float, tax_value_ratio: float, discount_rate: float) -> float:
    """Price effect (%) if a permanent cut of ``cut_pp`` percentage points were fully capitalised.

    The yearly saving is ``cut_pp / 100 * assessed value``; as a perpetuity at ``discount_rate`` and over the
    price it is ``cut_pp / 100 * tax_value_ratio / discount_rate``. ``tax_value_ratio`` is the assessed
    value (VPT) over the market price.
    """
    if discount_rate <= 0:
        raise ValueError("discount_rate must be positive")
    return 100 * (cut_pp / 100) * tax_value_ratio / discount_rate
