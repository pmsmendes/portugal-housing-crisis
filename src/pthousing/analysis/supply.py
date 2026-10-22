"""Supply against demand: did the dwelling stock keep pace with households, and where did it not?

Two periods, because the observed quantities differ:
* census 2011 to 2021: dwellings and private households are both counted, so the balance is observed;
* 2021 to 2023: only population (annual estimates) and completions are observed. The households added are
  *implied* (new residents / persons per household in 2021) and completions are new family dwellings only
  (no demolitions, conversions or renovation), so this period is a proxy for the pressure, not a count.

All balances use the sign convention of ``affordability.supply_gap_per_1000``: positive means dwellings grew
faster than households. Results are accounting ratios; the regression helper returns adjusted associations.
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from pthousing.config import MUNI_KEY, YEAR_KEY
from pthousing.data import interim
from pthousing.features import affordability as aff

CENSUS = (2011, 2021)
POST_CENSUS = (2021, 2023)  # population estimates end in 2023
COMPLETION_YEARS = (2022, 2023)  # completions after the 2021 census year
ISLANDS = {"azores": "Açores", "madeira": "Madeira"}


def read_stock() -> pd.DataFrame:
    """Census dwellings (usual, secondary, vacant) and households per municipality and census year."""
    return interim.read("ine_census_stock")


def area_of(panel: pd.DataFrame) -> pd.Series:
    """Reporting area of each municipality: its district on the mainland, Açores or Madeira otherwise."""
    one = panel.drop_duplicates(MUNI_KEY).set_index(MUNI_KEY)
    return one["district"].where(one["territory"] == "continente", one["territory"].map(ISLANDS))


def national_flows(panel: pd.DataFrame) -> pd.DataFrame:
    """New family dwellings licensed and completed per year, summed over municipalities (RQ2.1, RQ2.2)."""
    return panel.groupby(YEAR_KEY)[["licensed_n", "completed_n"]].sum(min_count=1)


def balance(panel: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    """Dwellings, households and population per municipality over the two periods, with the balances.

    Counts are kept (not only ratios) so that groups can be summed and the ratios recomputed
    (``aggregate``). Population is the annual estimate; ``persons_per_household_2021`` divides the 2021
    estimate by the census households, so the implied households of 2021-2023 are on the estimate's scale.
    """
    wide = stock.pivot(index=MUNI_KEY, columns="census_year")
    pop = panel.pivot(index=MUNI_KEY, columns=YEAR_KEY, values="population_n")
    completed = panel.pivot(index=MUNI_KEY, columns=YEAR_KEY, values="completed_n")
    a, b = CENSUS
    out = pd.DataFrame(index=wide.index)
    for year in CENSUS:
        out[f"dwellings_{year}_n"] = wide[("dwellings_n", year)]
        out[f"households_{year}_n"] = wide[("households_n", year)]
        out[f"population_{year}_n"] = pop[year]
    out["completions_2012_2021_n"] = completed.loc[:, a + 1 : b].sum(axis=1)
    out["supply_gap_2011_2021_per_1000"] = aff.supply_gap_per_1000(
        out[f"dwellings_{a}_n"],
        out[f"dwellings_{b}_n"],
        out[f"households_{a}_n"],
        out[f"households_{b}_n"],
    )
    out["population_2023_n"] = pop[POST_CENSUS[1]]
    out["persons_per_household_2021"] = out["population_2021_n"] / out["households_2021_n"]
    out["implied_new_households_2021_2023_n"] = (
        out["population_2023_n"] - out["population_2021_n"]
    ) / out["persons_per_household_2021"]
    out["completions_2022_2023_n"] = completed.loc[
        :, COMPLETION_YEARS[0] : COMPLETION_YEARS[1]
    ].sum(axis=1)
    out["implied_gap_2021_2023_per_1000"] = aff.implied_gap_per_1000(
        out["completions_2022_2023_n"],
        out["implied_new_households_2021_2023_n"],
        out["households_2021_n"],
    )
    return add_rates(out)


def add_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Growth rates (%) of dwellings, households and population, computed from the count columns.

    Used both per municipality and per group of summed counts, so a group's rate is never an average of
    its municipalities' rates.
    """
    a, b = CENSUS
    out = df.copy()
    out["dwellings_change_pct"] = 100 * (out[f"dwellings_{b}_n"] / out[f"dwellings_{a}_n"] - 1)
    out["households_change_pct"] = 100 * (out[f"households_{b}_n"] / out[f"households_{a}_n"] - 1)
    out["population_change_2011_2021_pct"] = 100 * (
        out[f"population_{b}_n"] / out[f"population_{a}_n"] - 1
    )
    out["population_change_2021_2023_pct"] = 100 * (
        out["population_2023_n"] / out["population_2021_n"] - 1
    )
    out["persons_per_household_2011"] = out["population_2011_n"] / out["households_2011_n"]
    out["completions_2022_2023_per_1000"] = (
        1000 * out["completions_2022_2023_n"] / out["dwellings_2021_n"]
    )
    return out


def aggregate(table: pd.DataFrame, by: pd.Series) -> pd.DataFrame:
    """Balance of groups: counts are summed, then the gaps and rates are recomputed from the sums."""
    counts = [c for c in table.columns if c.endswith("_n")]
    sums = table[counts].groupby(by).sum()
    sums["municipalities_n"] = table.groupby(by).size()
    a, b = CENSUS
    sums["supply_gap_2011_2021_per_1000"] = aff.supply_gap_per_1000(
        sums[f"dwellings_{a}_n"],
        sums[f"dwellings_{b}_n"],
        sums[f"households_{a}_n"],
        sums[f"households_{b}_n"],
    )
    sums["persons_per_household_2021"] = sums["population_2021_n"] / sums["households_2021_n"]
    # implied households use each municipality's own household size, so they are summed, not recomputed
    sums["implied_gap_2021_2023_per_1000"] = aff.implied_gap_per_1000(
        sums["completions_2022_2023_n"],
        sums["implied_new_households_2021_2023_n"],
        sums["households_2021_n"],
    )
    return add_rates(sums)


def composition(stock: pd.DataFrame, by: pd.Series | None = None) -> pd.DataFrame:
    """Share (%) of conventional dwellings that are usual residence, secondary residence or vacant (RQ2.4).

    ``by`` maps municipalities to groups (default: all of Portugal). One row per group and census year.
    """
    kinds = {
        "dwellings_usual_n": "usual_pct",
        "dwellings_secondary_n": "secondary_pct",
        "dwellings_vacant_n": "vacant_pct",
    }
    data = stock.set_index(MUNI_KEY)
    group = by.reindex(data.index) if by is not None else pd.Series("Portugal", index=data.index)
    sums = data.groupby([group.rename("group"), data["census_year"]])[["dwellings_n", *kinds]].sum()
    shares = sums[list(kinds)].div(sums["dwellings_n"], axis=0).mul(100).rename(columns=kinds)
    return pd.concat([sums[["dwellings_n"]], shares], axis=1).reset_index()


def associations(
    df: pd.DataFrame,
    y: str,
    xs: list[str],
    fixed_effects: str | None = None,
    categorical: list[str] | None = None,
    label: str | None = None,
) -> pd.DataFrame:
    """OLS of ``y`` on numeric ``xs`` (HC3 errors), optionally with group intercepts and class dummies.

    ``fixed_effects`` is a column whose values get their own intercept (absorbed, not reported);
    ``categorical`` are class columns entered as dummies and not reported. Reports ``coef``, ``se``, ``p``,
    the interval, ``coef_per_sd`` (coefficient times the standard deviation of the driver in the sample) and
    the sample size and R2. An adjusted association between cross-sections, not an effect.
    """
    terms = [
        *xs,
        *(f"C({c})" for c in categorical or []),
        *([f"C({fixed_effects})"] if fixed_effects else []),
    ]
    data = df.dropna(
        subset=[y, *xs, *(categorical or []), *([fixed_effects] if fixed_effects else [])]
    )
    res = smf.ols(f"{y} ~ " + " + ".join(terms), data=data).fit(cov_type="HC3")
    ci = res.conf_int().loc[xs]
    return pd.DataFrame(
        {
            "spec": label or y,
            "term": xs,
            "coef": res.params[xs].to_numpy(),
            "se": res.bse[xs].to_numpy(),
            "ci_low": ci[0].to_numpy(),
            "ci_high": ci[1].to_numpy(),
            "p": res.pvalues[xs].to_numpy(),
            "sd": data[xs].std().to_numpy(),
            "coef_per_sd": (res.params[xs] * data[xs].std()).to_numpy(),
            "n_obs": int(res.nobs),
            "r2": float(res.rsquared),
        }
    )


def pti_change(panel: pd.DataFrame, start: int, end: int) -> pd.Series:
    """Log change of price-to-income per municipality between two years (NaN if either is missing)."""
    wide = panel[panel[YEAR_KEY].isin([start, end])].pivot(
        index=MUNI_KEY, columns=YEAR_KEY, values="pti_years"
    )
    return np.log(wide[end] / wide[start]).rename("dlog_pti")
