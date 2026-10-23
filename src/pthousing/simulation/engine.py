"""Combine scenarios and levers into affordability, cost and uncertainty outputs.

An annual, national stock-flow model from ``start_year`` (last year with observed prices) over ``horizon_years``:

* **Demand.** Population grows by natural change plus net migration; household size follows the census trend;
  households follow (``supply.households``).
* **Supply.** Completions (scenario) plus policy levers add dwellings that can house households
  (``supply.usable_additions``). The year's *balance pressure* is the households formed beyond them.
* **Prices.** Real price growth = ``price_flexibility_balance`` x pressure + ``income_elasticity_of_price`` x
  income growth - ``mortgage_rate_semi_elasticity`` x the change in the mortgage rate (spread over two years)
  + a fading *other demand* drift (tourism, foreign buyers, credit, expectations) + the capitalisation of tax
  reforms. The drift starts at a value chosen so that the baseline reproduces the validated ETS forecast of
  ``p4_01`` for ``near_term_year`` (with its 80% interval as the spread of that anchor); how fast it fades is a
  scenario input. So the first years are the forecast, and the later years are scenarios.
* **Affordability.** Price-to-income and the mortgage burden of the start year (median municipality, 2024
  panel, rolled to the start year) move with the national price, income and mortgage-rate paths.
* **Cost.** Direct fiscal effects of every lever (``fiscal``), kept apart from the behavioural price effects.

Every function works on arrays with a leading draw axis, so a deterministic run (the ``mid`` values) and an
uncertainty run (triangular draws over each parameter's range, common random numbers across scenarios and
policies) share one code path.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from pthousing.config import BENCHMARK_AREA_SQM, MUNI_KEY, TABLES, YEAR_KEY
from pthousing.data import build_panel
from pthousing.features import affordability as aff
from pthousing.simulation import fiscal, supply
from pthousing.simulation import scenarios as scn
from pthousing.simulation.scenarios import LEVER_KEYS, Assumptions

Z80 = (
    1.2815515655446004  # the 90th percentile of the standard normal: half-width of an 80% interval
)
CENSUS_YEARS = (2011, 2021)
FORECAST_SERIES = "Real house price index"
QUANTILES = (0.1, 0.5, 0.9)


@dataclass(frozen=True)
class Anchors:
    """Observed starting point, all from the project's data (no hand-typed numbers)."""

    start_year: int
    population: float
    persons_per_household: float
    household_size_trend: float  # persons per household per year, census 2011 to 2021
    households: float
    completions: float  # last observed year
    pti_years: float  # median municipality
    burden_pct: float  # median municipality
    mortgage_rate_pct: float
    imi_average_rate_pct: float
    transaction_value_eur: float
    near_term_log_growth: float  # log of the forecast price index over the start-year mean
    near_term_sigma: float  # sd of that log growth, from the 80% interval
    near_term_steps: int


@dataclass(frozen=True)
class Policy:
    """Size of each lever, per year from the policy start year (rate changes in pp, negative is a cut)."""

    construction_boost_units: float = 0.0
    vacant_renovation_units: float = 0.0
    public_housing_units: float = 0.0
    imi_rate_change_pp: float = 0.0
    imt_rate_change_pp: float = 0.0

    @classmethod
    def package(cls, a: Assumptions, name: str) -> Policy:
        return cls(**a.packages[name])

    def scaled(self, factor: float) -> Policy:
        return Policy(**{k: getattr(self, k) * factor for k in LEVER_KEYS})

    @property
    def is_empty(self) -> bool:
        return all(getattr(self, k) == 0 for k in LEVER_KEYS)


@dataclass
class Run:
    """Result of one simulation: arrays of shape (draws, years) unless stated."""

    years: np.ndarray  # start year first
    series: dict[str, np.ndarray] = field(default_factory=dict)

    def summary(self, metric: str, quantiles=QUANTILES) -> pd.DataFrame:
        """One row per year with the quantiles of ``metric`` over the draws."""
        values = self.series[metric]
        years = self.years[-values.shape[1] :]
        q = np.quantile(values, quantiles, axis=0)
        return pd.DataFrame(
            {"year": years, **{f"p{round(100 * p)}": q[i] for i, p in enumerate(quantiles)}}
        )

    def end(self, metric: str) -> np.ndarray:
        """The metric in the last year, one value per draw."""
        return self.series[metric][:, -1]


# ---- anchors -------------------------------------------------------------------------------------


def _year_sum(panel: pd.DataFrame, column: str, year: int) -> float:
    return float(panel.loc[panel[YEAR_KEY] == year, column].sum(min_count=1))


def anchors(
    panel: pd.DataFrame, nat: pd.DataFrame, forecast: pd.DataFrame, a: Assumptions
) -> Anchors:
    """Starting point from the municipal panel, the national quarterly table and the p4_01 forecast table.

    ``nat`` has a ``period_start`` column; ``forecast`` is ``reports/tables/p4/national_forecast.csv``.
    """
    s, base = a.start_year, a.start_year - 1
    census = panel[panel[YEAR_KEY] == CENSUS_YEARS[1]].set_index(MUNI_KEY)
    pop = {y: _year_sum(panel, "population_n", y) for y in (CENSUS_YEARS[0], CENSUS_YEARS[1], 2023)}
    hh = {
        2011: float(census["households_2011_n"].sum()),
        2021: float(census["households_2021_n"].sum()),
    }
    size = {y: pop[y] / hh[y] for y in hh}
    trend = (size[2021] - size[2011]) / (2021 - 2011)
    size_start = size[2021] + trend * (s - 2021)
    population = pop[2023] + (s - 2023) * a.common["population_change_2024"]

    year = nat.assign(year=pd.to_datetime(nat["period_start"]).dt.year).groupby("year")
    hpi = year["hpi_total_real_b2025"].mean()
    rate = year["mortgage_rate_new_lt1y_pct"].mean()
    income_growth = a.common["income_growth_2025_pct"] / 100
    price_ratio = hpi[s] / hpi[base]  # panel indicators are of the year before the start
    d = panel[panel[YEAR_KEY] == base]
    pti = float(d["pti_years"].median()) * price_ratio / (1 + income_growth)
    burden = (
        float(d["mortgage_burden_pct"].median())
        * price_ratio
        / (1 + income_growth)
        * aff.mortgage_payment_monthly(1.0, rate[s])
        / aff.mortgage_payment_monthly(1.0, rate[base])
    )

    target = forecast[
        (forecast["series"] == FORECAST_SERIES) & (forecast["period"] == f"{a.near_term_year}Q2")
    ]
    if len(target) != 1:
        raise ValueError(f"no {FORECAST_SERIES} forecast for {a.near_term_year}Q2")
    row = target.iloc[0]
    sigma = (np.log(row["hi80"]) - np.log(row["lo80"])) / (2 * Z80)

    sales_year = base  # 2025 transactions are not complete in the panel
    sold = panel[panel[YEAR_KEY] == sales_year]
    value = float((sold["sales_12m_n"] * sold["price_sqm_eur_real"]).sum() * BENCHMARK_AREA_SQM)
    rates = panel.loc[panel[YEAR_KEY] == s, "imi_urban_pct"].dropna()
    if rates.empty:
        rates = panel.loc[panel[YEAR_KEY] == base, "imi_urban_pct"].dropna()
    return Anchors(
        start_year=s,
        population=population,
        persons_per_household=size_start,
        household_size_trend=trend,
        households=population / size_start,
        completions=_year_sum(panel, "completed_n", s),
        pti_years=pti,
        burden_pct=burden,
        mortgage_rate_pct=float(rate[s]),
        imi_average_rate_pct=float(rates.mean()),
        transaction_value_eur=value,
        near_term_log_growth=float(np.log(row["mean"] / hpi[s])),
        near_term_sigma=float(sigma),
        near_term_steps=a.near_term_year - s,
    )


def load_inputs() -> tuple[Assumptions, Anchors]:
    """Assumptions from ``config/scenarios.yaml`` and the anchors from the committed panels and the p4_01 forecast."""
    a = scn.load()
    forecast = pd.read_csv(TABLES / "p4" / "national_forecast.csv")
    anc = anchors(
        build_panel.read("panel_municipality_year"),
        build_panel.read("national_quarterly"),
        forecast,
        a,
    )
    return a, anc


# ---- parameters ----------------------------------------------------------------------------------


def central(a: Assumptions, **override: float) -> dict[str, np.ndarray]:
    """One draw at every parameter's mid value; ``override`` sets named parameters (or ``near_term_z``)."""
    p = {name: np.array([r.mid]) for name, r in a.ranges.items()}
    p["near_term_z"] = np.zeros(1)
    for name, value in override.items():
        p[name.replace("__", ".")] = np.array([float(value)])
    return p


def at_bound(a: Assumptions, name: str, which: str) -> dict[str, np.ndarray]:
    """The central draw with one parameter at its ``low`` or ``high`` bound."""
    p = central(a)
    p[name] = np.array([a.ranges[name].at(which)])
    return p


def draw(a: Assumptions, n: int = 500, seed: int = 2026) -> dict[str, np.ndarray]:
    """``n`` draws of every range (triangular) and of the position inside the forecast's 80% interval."""
    rng = np.random.default_rng(seed)
    p = {name: r.draw(rng, n) for name, r in a.ranges.items()}
    p["near_term_z"] = rng.standard_normal(n)
    return p


def _n(p: dict[str, np.ndarray]) -> int:
    return len(p["near_term_z"])


# ---- the model -----------------------------------------------------------------------------------


def _terms(a: Assumptions, anc: Anchors, scenario: dict, policy: Policy, p: dict) -> dict:
    """Everything in a run that does not depend on the drift: balance, income, rates, policy, cost."""
    steps = a.horizon_years
    n = _n(p)
    years = anc.start_year + np.arange(1, steps + 1)
    active = (years >= a.policy_start_year).astype(float)
    c = a.common

    pop = supply.population_path(
        anc.population, c["natural_change_per_year"], scenario["net_migration_per_year"], steps
    )
    size = supply.household_size_path(anc.persons_per_household, anc.household_size_trend, steps)
    hh = np.concatenate([[anc.households], supply.households(pop, size)])
    completions = supply.ramp(
        anc.completions, scenario["completions_per_year"], int(c["completions_ramp_years"]), steps
    )
    rates = supply.ramp(
        anc.mortgage_rate_pct, scenario["mortgage_rate_pct"], int(c["rate_ramp_years"]), steps
    )

    extra, renovated, public = (
        active * policy.construction_boost_units,
        active * policy.vacant_renovation_units,
        active * policy.public_housing_units,
    )
    additions = supply.usable_additions(
        completions[None, :],
        extra[None, :],
        renovated[None, :],
        public[None, :],
        net_ratio=a.fixed["net_additions_per_completion"],
        usable_share=p["usable_share_of_additions"][:, None],
        additionality=p["construction_boost.additionality"][:, None],
        reoccupation=p["vacant_renovation.reoccupation"][:, None],
        crowd_out=p["public_housing.crowd_out"][:, None],
    )
    pressure = supply.balance_pressure(hh[:-1][None, :], hh[1:][None, :], additions)

    income_growth = np.log1p(scenario["household_income_growth_real_pct"] / 100)
    rate_steps = np.diff(np.concatenate([[anc.mortgage_rate_pct], rates]))
    rate_term = 0.5 * rate_steps + 0.5 * np.concatenate([[0.0], rate_steps[:-1]])

    first = np.argmax(years >= a.policy_start_year) if active.any() else 0
    shift = np.zeros((n, steps))
    imi = np.log1p(
        fiscal.imi_capitalisation(
            policy.imi_rate_change_pp,
            p["imi_reform.capitalisation_share"],
            p["imi_reform.tax_value_ratio"],
            p["imi_reform.discount_rate"],
        )
    )
    imt = np.log1p(
        fiscal.imt_capitalisation(policy.imt_rate_change_pp, p["imt_reform.capitalisation_share"])
    )
    if active.any():
        shift[:, first] = imi + imt

    f = a.fiscal
    cost = {
        "construction_boost": fiscal.spending(
            extra[None, :], p["construction_boost.cost_per_unit_eur"][:, None]
        ),
        "vacant_renovation": fiscal.spending(
            renovated[None, :], p["vacant_renovation.cost_per_unit_eur"][:, None]
        ),
        "public_housing": fiscal.spending(
            public[None, :], p["public_housing.cost_per_unit_eur"][:, None]
        ),
        "imi_reform": np.broadcast_to(
            active
            * fiscal.imi_revenue_loss(
                policy.imi_rate_change_pp, anc.imi_average_rate_pct, f["imi_revenue_eur"]
            ),
            (n, steps),
        ),
        "imt_reform": np.broadcast_to(
            active * fiscal.imt_revenue_loss(policy.imt_rate_change_pp, anc.transaction_value_eur),
            (n, steps),
        ),
    }
    return {
        "years": years,
        "households": hh,
        "pressure": pressure,
        "additions": additions,
        "income_growth": income_growth,
        "rates": rates,
        "rate_term": rate_term,
        "shift": shift,
        "cost": cost,
        "shortfall": np.cumsum(hh[1:] - hh[:-1] - additions, axis=1),
        "homes_added": np.cumsum(
            policy.public_housing_units * active
            + p["vacant_renovation.reoccupation"][:, None] * renovated[None, :]
            + p["construction_boost.additionality"][:, None] * extra[None, :],
            axis=1,
        ),
    }


def calibrate(a: Assumptions, anc: Anchors, p: dict) -> np.ndarray:
    """Starting value of the other-demand drift (log points a year), one per draw.

    Chosen so that the baseline scenario without policy reaches the forecast (mean plus ``near_term_z`` sd of
    its 80% interval) in ``near_term_year``: the first projection years are pinned to the validated forecast.
    """
    base = a.scenarios["baseline"]
    t = _terms(a, anc, base, Policy(), p)
    k = anc.near_term_steps
    explained = _explained(p, t, base)[:, :k].sum(axis=1)
    target = anc.near_term_log_growth + anc.near_term_sigma * p["near_term_z"]
    weights = 0.5 ** (np.arange(k) / base["other_demand_half_life_years"])
    return (target - explained) / weights.sum()


def _explained(p: dict, t: dict, scenario: dict) -> np.ndarray:
    """Log price growth from balance, income and mortgage rate (before drift and policy shifts)."""
    return (
        p["price_flexibility_balance"][:, None] * t["pressure"]
        + p["income_elasticity_of_price"][:, None] * t["income_growth"]
        - p["mortgage_rate_semi_elasticity"][:, None] / 100 * t["rate_term"][None, :]
    )


def run(
    a: Assumptions,
    anc: Anchors,
    scenario: str | dict,
    policy: Policy | None = None,
    p: dict | None = None,
    drift: np.ndarray | None = None,
) -> Run:
    """Simulate one scenario and policy package over the draws ``p`` (default: the central draw).

    ``drift`` is the calibrated starting drift (``calibrate``); pass it when the parameters of ``p`` are those
    the forecast was calibrated with, so a policy and its no-policy comparison share it.
    """
    policy = policy or Policy()
    p = p if p is not None else central(a)
    sc = a.scenarios[scenario] if isinstance(scenario, str) else scenario
    drift = calibrate(a, anc, p) if drift is None else drift
    t = _terms(a, anc, sc, policy, p)
    steps = a.horizon_years

    fade = 0.5 ** (np.arange(steps) / sc["other_demand_half_life_years"])
    growth = _explained(p, t, sc) + drift[:, None] * fade[None, :] + t["shift"]
    price = 100 * np.exp(np.concatenate([np.zeros((_n(p), 1)), np.cumsum(growth, axis=1)], axis=1))
    income = (
        100
        * np.exp(np.concatenate([[0.0], np.cumsum(np.full(steps, t["income_growth"]))]))[None, :]
    )
    relative = (price / 100) / (income / 100)
    pay = aff.mortgage_payment_monthly(1.0, np.concatenate([[anc.mortgage_rate_pct], t["rates"]]))
    pay = np.asarray(pay)[None, :] / pay[0]

    cost = {k: v for k, v in t["cost"].items()}
    annual_cost = sum(cost.values())
    out = {
        "price_index": price,
        "income_index": np.broadcast_to(income, price.shape),
        "pti_years": anc.pti_years * relative,
        "burden_pct": anc.burden_pct * relative * pay,
        "mortgage_rate_pct": np.broadcast_to(
            np.concatenate([[anc.mortgage_rate_pct], t["rates"]])[None, :], price.shape
        ),
        "households_n": np.broadcast_to(t["households"][None, :], price.shape),
        "pressure_pct": 100 * t["pressure"],
        "cumulative_shortfall_n": t["shortfall"],
        "homes_added_n": t["homes_added"],
        "cost_eur": annual_cost,
        "cumulative_cost_eur": np.cumsum(annual_cost, axis=1),
    }
    out.update({f"cost_{k}_eur": np.asarray(v) for k, v in cost.items()})
    return Run(years=np.concatenate([[anc.start_year], t["years"]]), series=out)


# ---- comparisons ---------------------------------------------------------------------------------


def compare(
    a: Assumptions, anc: Anchors, scenario: str | dict, policy: Policy, p: dict | None = None
) -> pd.DataFrame:
    """Effect of ``policy`` on the last year, one row per draw: change in PTI and burden, cost, effect per cost.

    Both runs share the calibrated drift, so the difference is the policy and nothing else. ``pti_gain`` is
    the fall in price-to-income (positive is better); ``gain_per_bn`` divides it by the cumulative budget
    cost in billions of base-year euros (NaN when the package costs nothing or saves money).
    """
    p = p if p is not None else central(a)
    drift = calibrate(a, anc, p)
    without, with_ = run(a, anc, scenario, None, p, drift), run(a, anc, scenario, policy, p, drift)
    cost = with_.end("cumulative_cost_eur")
    gain = without.end("pti_years") - with_.end("pti_years")
    with np.errstate(divide="ignore", invalid="ignore"):
        per_bn = np.where(cost > 0, gain / (cost / 1e9), np.nan)
    return pd.DataFrame(
        {
            "pti_gain": gain,
            "burden_gain_pp": without.end("burden_pct") - with_.end("burden_pct"),
            "price_effect_pct": 100 * (with_.end("price_index") / without.end("price_index") - 1),
            "cost_eur": cost,
            "gain_per_bn": per_bn,
            "homes_added_n": with_.end("homes_added_n"),
        }
    )


def summarise(frame: pd.DataFrame, quantiles=QUANTILES) -> pd.Series:
    """Median and 80% range of each column of ``compare`` plus the share of draws that improve."""
    q = frame.quantile(list(quantiles))
    out = {}
    for col in frame:
        for i, label in enumerate(("p10", "p50", "p90")):
            out[f"{col}_{label}"] = q[col].iloc[i]
    out["share_improving"] = float((frame["pti_gain"] > 0).mean())
    return pd.Series(out)


def scenario_table(
    a: Assumptions, anc: Anchors, p: dict, packages: list[str] | None = None
) -> pd.DataFrame:
    """Last-year affordability and cost for every scenario and package, with quantiles over the draws."""
    drift = calibrate(a, anc, p)
    rows = []
    for scenario in a.scenarios:
        for name in packages or list(a.packages):
            r = run(a, anc, scenario, Policy.package(a, name), p, drift)
            row = {"scenario": scenario, "package": name}
            for metric in ("price_index", "pti_years", "burden_pct", "cumulative_cost_eur"):
                lo, mid, hi = np.quantile(r.end(metric), QUANTILES)
                row.update({f"{metric}_p10": lo, f"{metric}_p50": mid, f"{metric}_p90": hi})
            rows.append(row)
    return pd.DataFrame(rows)


def sensitivity(
    a: Assumptions, anc: Anchors, scenario: str | dict = "baseline", policy: Policy | None = None
) -> pd.DataFrame:
    """One-at-a-time sensitivity of the last year's PTI and of the policy's gain (RQ10.6).

    Each behavioural or policy parameter is set to its ``low`` and ``high`` bound with all others at ``mid``
    (the drift is recalibrated to the forecast each time); each scenario input is moved across the range
    spanned by the three scenarios, keeping the drift. Output: parameter, kind, both bounds' values of
    ``pti_end`` and ``pti_gain``.
    """
    policy = policy or Policy.package(a, "supply_mix")
    mid = central(a)
    rows = []
    for name in a.ranges:
        vals = {}
        for which in ("low", "high"):
            p = at_bound(a, name, which)
            drift = calibrate(a, anc, p)
            base = run(a, anc, scenario, None, p, drift)
            pol = run(a, anc, scenario, policy, p, drift)
            vals[which] = (
                base.end("pti_years")[0],
                base.end("pti_years")[0] - pol.end("pti_years")[0],
            )
        rows.append(
            {"parameter": name, "kind": "behaviour", "low_pti_end": vals["low"][0],
             "high_pti_end": vals["high"][0], "low_pti_gain": vals["low"][1],
             "high_pti_gain": vals["high"][1]}
        )  # fmt: skip
    drift = calibrate(a, anc, mid)
    sc = a.scenarios[scenario] if isinstance(scenario, str) else dict(scenario)
    for key in sc:
        span = [s[key] for s in a.scenarios.values()]
        vals = {}
        for which, v in (("low", min(span)), ("high", max(span))):
            alt = {**sc, key: v}
            base = run(a, anc, alt, None, mid, drift)
            pol = run(a, anc, alt, policy, mid, drift)
            vals[which] = (
                base.end("pti_years")[0],
                base.end("pti_years")[0] - pol.end("pti_years")[0],
            )
        rows.append(
            {"parameter": key, "kind": "scenario", "low_pti_end": vals["low"][0],
             "high_pti_end": vals["high"][0], "low_pti_gain": vals["low"][1],
             "high_pti_gain": vals["high"][1]}
        )  # fmt: skip
    out = pd.DataFrame(rows)
    out["swing_pti_end"] = (out["high_pti_end"] - out["low_pti_end"]).abs()
    out["swing_pti_gain"] = (out["high_pti_gain"] - out["low_pti_gain"]).abs()
    return out.sort_values("swing_pti_end", ascending=False, ignore_index=True)


# ---- budget-constrained mixes (RQ10.5) -----------------------------------------------------------

MIX_LEVERS = (
    "construction_boost_units",
    "vacant_renovation_units",
    "public_housing_units",
    "imi_rate_change_pp",
    "imt_rate_change_pp",
)


def policy_for_budget(a: Assumptions, anc: Anchors, shares: dict[str, float], budget_eur: float):
    """A package that spends ``budget_eur`` a year split by ``shares`` (summing to 1), at mid unit costs.

    Supply levers buy units; the tax levers are cuts sized so that the revenue lost equals their share.
    """
    mid = lambda name: a.ranges[name].mid  # noqa: E731
    unit_cost = {
        "construction_boost_units": mid("construction_boost.cost_per_unit_eur"),
        "vacant_renovation_units": mid("vacant_renovation.cost_per_unit_eur"),
        "public_housing_units": mid("public_housing.cost_per_unit_eur"),
    }
    sizes = {k: shares.get(k, 0.0) * budget_eur / c for k, c in unit_cost.items()}
    sizes["imi_rate_change_pp"] = -(
        shares.get("imi_rate_change_pp", 0.0)
        * budget_eur
        / a.fiscal["imi_revenue_eur"]
        * anc.imi_average_rate_pct
    )
    sizes["imt_rate_change_pp"] = -(
        shares.get("imt_rate_change_pp", 0.0) * budget_eur / anc.transaction_value_eur * 100
    )
    return Policy(**sizes)


def mix_search(
    a: Assumptions,
    anc: Anchors,
    scenario: str | dict,
    budget_eur: float,
    p: dict,
    step: float = 0.25,
    levers: tuple[str, ...] = MIX_LEVERS,
) -> pd.DataFrame:
    """Every split of an annual budget over ``levers`` in multiples of ``step``, ranked by median PTI gain.

    One row per mix with the shares, the median and 80% range of the gain, the share of draws in which it
    helps and the median cost. The budget is a yearly amount from the policy start year.
    """
    k = round(1 / step)
    drift = calibrate(a, anc, p)
    without = run(a, anc, scenario, None, p, drift)
    rows = []

    def splits(n_left: int, slots: int):
        if slots == 1:
            yield (n_left,)
            return
        for i in range(n_left + 1):
            for rest in splits(n_left - i, slots - 1):
                yield (i, *rest)

    for combo in splits(k, len(levers)):
        shares = {lever: c / k for lever, c in zip(levers, combo, strict=True)}
        pol = policy_for_budget(a, anc, shares, budget_eur)
        with_ = run(a, anc, scenario, pol, p, drift)
        gain = without.end("pti_years") - with_.end("pti_years")
        lo, mid, hi = np.quantile(gain, QUANTILES)
        rows.append(
            {**{f"share_{lever}": s for lever, s in shares.items()},
             "pti_gain_p10": lo, "pti_gain_p50": mid, "pti_gain_p90": hi,
             "share_improving": float((gain > 0).mean()),
             "cost_eur_p50": float(np.median(with_.end("cumulative_cost_eur")))}
        )  # fmt: skip
    return pd.DataFrame(rows).sort_values("pti_gain_p50", ascending=False, ignore_index=True)


__all__ = [
    "Anchors",
    "Policy",
    "Run",
    "anchors",
    "at_bound",
    "calibrate",
    "central",
    "compare",
    "draw",
    "load_inputs",
    "mix_search",
    "policy_for_budget",
    "run",
    "scenario_table",
    "sensitivity",
    "summarise",
]
