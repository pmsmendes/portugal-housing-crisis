"""Large municipalities and their surroundings: do prices rise faster at the centre or further out (RQ4.3).

A centre is a municipality with at least ``MIN_CENTRE_POPULATION`` residents (a size rule, not a functional urban
area: it picks the two metropolitan cores and also their large suburbs). Distance is the number of border steps
to the nearest centre on the queen contiguity graph (``spatial.build_weights``): 0 is a centre, 1 a municipality
that touches one, and so on. No link crosses the sea, so islands without a centre have no distance.

Functions take Series indexed by ``muni_code`` and the weights object; nothing here reads files.
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from libpysal import weights

MIN_CENTRE_POPULATION = 100_000
#: Distances above this are pooled with it (a municipality four or more steps from any centre).
MAX_STEPS = 4


def find_centres(population: pd.Series, minimum: int = MIN_CENTRE_POPULATION) -> list[str]:
    """Codes of municipalities with at least ``minimum`` residents, largest first."""
    big = population[population >= minimum].sort_values(ascending=False)
    return big.index.to_list()


def steps_from_centre(w: weights.W, centres: list[str]) -> pd.Series:
    """Border steps to the nearest centre (breadth-first search); municipalities no centre reaches are NaN."""
    steps = dict.fromkeys(centres, 0)
    frontier = list(centres)
    while frontier:
        following = []
        for code in frontier:
            for neighbour in w.neighbors[code]:
                if neighbour not in steps:
                    steps[neighbour] = steps[code] + 1
                    following.append(neighbour)
        frontier = following
    out = pd.Series(steps, dtype=float).reindex(w.id_order)
    out.index.name = "muni_code"
    return out.rename("steps_from_centre")


def gradient(
    outcomes: dict[str, pd.Series], steps: pd.Series, cap: int = MAX_STEPS
) -> pd.DataFrame:
    """Median of each outcome by steps from the nearest centre (``cap`` and above pooled), with the count.

    ``outcomes`` maps a label to a Series by municipality (for example the real price change in %). The count is
    of municipalities with a value and a distance.
    """
    group = steps.clip(upper=cap)
    rows = {}
    for label, values in outcomes.items():
        d = pd.concat([values.rename("v"), group.rename("g")], axis=1).dropna()
        by = d.groupby("g")["v"]
        rows[label] = pd.DataFrame(
            {"municipalities_n": by.size(), "median": by.median(), "mean": by.mean()}
        )
    out = pd.concat(rows, names=["outcome"])
    out.index = out.index.set_names(["outcome", "steps"])
    return out


def gradient_within_regions(
    outcome: pd.Series, steps: pd.Series, region: pd.Series, cap: int = 3
) -> pd.DataFrame:
    """Difference from a centre of the log change at each distance, with region (NUTS 3) fixed effects.

    ``outcome`` is the change in % (the regression uses its log, in percentage points); the table gives, for each
    distance class up to ``cap`` (the last pools ``cap`` and above), the percentage difference from a centre in
    the same region, with a 95% interval from standard errors clustered by region. Regions without a centre
    contribute nothing to the contrasts (their count is ``regions_with_centre_n``). Few clusters: read the interval as approximate.
    """
    d = pd.concat(
        [outcome.rename("y"), steps.clip(upper=cap).rename("steps"), region.rename("region")],
        axis=1,
    ).dropna()
    d["log_change"] = 100 * np.log1p(d["y"] / 100)
    d["steps"] = d["steps"].astype(int).astype(str)
    fit = smf.ols("log_change ~ C(steps, Treatment('0')) + C(region)", data=d).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d["region"])[0]}
    )
    rows = {}
    for name in fit.params.index:
        if name.startswith("C(steps"):
            label = name.split("[T.")[1].rstrip("]")
            lo, hi = fit.conf_int().loc[name]
            rows[int(label)] = {
                "diff_log_points": fit.params[name],
                "ci_low": lo,
                "ci_high": hi,
                "p_value": fit.pvalues[name],
                "municipalities_n": int((d["steps"] == label).sum()),
            }
    out = pd.DataFrame(rows).T.rename_axis("steps")
    out["regions_with_centre_n"] = d.loc[d["steps"] == "0", "region"].nunique()
    return out


def core_vs_rest(outcome: pd.Series, cores: list[str], area: pd.Series) -> pd.DataFrame:
    """Outcome of each core municipality against the median of the other municipalities of its area.

    ``area`` labels each municipality with its metropolitan area (NaN outside); ``cores`` are the codes of the
    cores (one per area).
    """
    rows = {}
    for core in cores:
        members = area[area == area[core]].index.difference([core])
        rest = outcome.reindex(members).dropna()
        rows[core] = {
            "area": area[core],
            "core": outcome.get(core, np.nan),
            "rest_median": rest.median(),
            "rest_n": len(rest),
            "share_of_rest_above_core_pct": 100 * (rest > outcome.get(core, np.nan)).mean(),
        }
    return pd.DataFrame(rows).T
