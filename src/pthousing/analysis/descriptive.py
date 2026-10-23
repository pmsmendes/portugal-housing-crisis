"""Descriptive statistics, growth rates and group comparisons (coastal/inland, urban/rural, tourist)."""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from pthousing.config import MUNI_KEY, YEAR_KEY
from pthousing.features import affordability as aff


def yearly_quantiles(
    df: pd.DataFrame, column: str, quantiles: tuple[float, ...] = (0.1, 0.5, 0.9)
) -> pd.DataFrame:
    """Quantiles of ``column`` across municipalities for each year, with the number of municipalities.

    Columns are ``q10``, ``q50``, ``q90`` (percent of the quantile) and ``n``; missing values are ignored.
    """
    grouped = df.groupby(YEAR_KEY)[column]
    out = pd.concat({f"q{round(q * 100)}": grouped.quantile(q) for q in quantiles}, axis=1)
    out["n"] = grouped.count()
    return out[out["n"] > 0]


def share_above(df: pd.DataFrame, column: str, threshold: float) -> pd.DataFrame:
    """Share of municipalities with ``column`` above ``threshold`` per year (among those with a value)."""
    valid = df.dropna(subset=[column])
    above = valid[column].gt(threshold).groupby(valid[YEAR_KEY])
    return pd.DataFrame({"share": above.mean(), "n": above.size()})


def balanced_sample(df: pd.DataFrame, columns: list[str], years: list[int]) -> pd.DataFrame:
    """Rows of the municipalities that have every ``column`` in every one of ``years`` (a fixed sample).

    Comparing years on a changing set of municipalities mixes real change with a changing sample.
    """
    window = df[df[YEAR_KEY].isin(years)]
    complete = window.dropna(subset=columns).groupby(MUNI_KEY).size() == len(years)
    return window[window[MUNI_KEY].isin(complete[complete].index)]


def rebase(table: pd.DataFrame, base_year: int) -> pd.DataFrame:
    """Index columns of a year-indexed table to 100 in ``base_year``."""
    return table / table.loc[base_year] * 100


def median_index(df: pd.DataFrame, columns: list[str], base_year: int) -> pd.DataFrame:
    """Median across municipalities of each municipality's own index (``base_year`` = 100) per year.

    Indexing each municipality first and taking the median after avoids mixing levels of very different
    markets; use it on a balanced sample so the municipalities do not change between years.
    """
    out = {}
    for column in columns:
        wide = df.pivot(index=MUNI_KEY, columns=YEAR_KEY, values=column)
        out[column] = (wide.div(wide[base_year], axis=0) * 100).median()
    return pd.DataFrame(out)


def change(df: pd.DataFrame, column: str, start: int, end: int, kind: str = "diff") -> pd.Series:
    """Change of ``column`` per municipality between two years: ``diff`` (end - start) or ``pct`` (%).

    Municipalities missing either year stay NaN.
    """
    wide = df.pivot(index=MUNI_KEY, columns=YEAR_KEY, values=column)
    if kind == "diff":
        return (wide[end] - wide[start]).rename(f"{column}_change_{start}_{end}")
    if kind == "pct":
        return (100 * (wide[end] / wide[start] - 1)).rename(f"{column}_change_pct_{start}_{end}")
    raise ValueError(f"kind must be 'diff' or 'pct', got {kind!r}")


def burden_at_fixed_rate(panel: pd.DataFrame, rate_year: int) -> pd.Series:
    """Mortgage burden (%) if the mortgage rate had stayed at its ``rate_year`` level (prices, incomes,
    dwelling size and loan terms as observed): separates the effect of rates from prices and incomes."""
    rate = panel.loc[panel[YEAR_KEY] == rate_year, "mortgage_rate_new_lt1y_pct"].iloc[0]
    return aff.mortgage_burden_pct(
        panel["price_sqm_eur"], panel["dwelling_area_sqm"], panel["income_median_eur"], rate
    )


def ranking(
    df: pd.DataFrame, year: int, columns: list[str], by: str, n: int = 15, ascending: bool = False
):
    """The ``n`` municipalities with the highest (or lowest) ``by`` in ``year`` with selected columns."""
    cols = ["muni_name", "district", *columns]
    sel = df[df[YEAR_KEY] == year].dropna(subset=[by]).sort_values(by, ascending=ascending)
    return sel.head(n)[[MUNI_KEY, *cols]].reset_index(drop=True)


def group_median(df: pd.DataFrame, column: str, by: str) -> pd.DataFrame:
    """Median of ``column`` across municipalities for each value of ``by`` and year."""
    return df.groupby([by, YEAR_KEY])[column].median().unstack(by)


def top_with_baseline(
    df: pd.DataFrame, column: str, start: int, end: int, n: int = 15
) -> pd.DataFrame:
    """The ``n`` municipalities with the highest ``column`` in ``end`` that also have a value in ``start``."""
    wide = df.pivot(index=MUNI_KEY, columns=YEAR_KEY, values=column)[[start, end]].dropna()
    names = df.drop_duplicates(MUNI_KEY).set_index(MUNI_KEY)[["muni_name", "district"]]
    out = names.join(wide.rename(columns={start: "start", end: "end"}), how="inner")
    return out.sort_values("end", ascending=False).head(n).reset_index()


def district_summary(df: pd.DataFrame, column: str, start: int, end: int) -> pd.DataFrame:
    """Median of ``column`` across the municipalities of each district in two years, with the change.

    Only municipalities with a value in both years are used, so the two medians describe the same set.
    """
    wide = df.pivot(index=MUNI_KEY, columns=YEAR_KEY, values=column)[[start, end]].dropna()
    district = df.drop_duplicates(MUNI_KEY).set_index(MUNI_KEY)["district"]
    grouped = wide.join(district).groupby("district")
    out = pd.DataFrame(
        {
            f"median_{start}": grouped[start].median(),
            f"median_{end}": grouped[end].median(),
            "municipalities_n": grouped.size(),
        }
    )
    out["change"] = out[f"median_{end}"] - out[f"median_{start}"]
    return out.sort_values(f"median_{end}", ascending=False).reset_index()


def segment_summary(
    panel: pd.DataFrame, typology: pd.DataFrame, groups: dict[str, list[str]], start: int, end: int
) -> pd.DataFrame:
    """Price-to-income, real price and real income by group of a typology column, ``start`` to ``end``.

    ``groups`` maps a typology column to the group values to report. Only municipalities with all three
    values in both years are used, so each group's two medians describe the same municipalities. Changes are
    the median of each municipality's own log change, shown as a percentage.
    """
    columns = ["pti_years", "price_sqm_eur_real", "income_median_eur_real"]
    wide = panel[panel[YEAR_KEY].isin([start, end])].pivot(
        index=MUNI_KEY, columns=YEAR_KEY, values=columns
    )
    wide = wide.dropna()
    own = pd.DataFrame(
        {
            f"pti_{start}": wide[("pti_years", start)],
            f"pti_{end}": wide[("pti_years", end)],
            "pti_change_pct": 100
            * np.expm1(np.log(wide["pti_years"][end] / wide["pti_years"][start])),
            "price_real_change_pct": 100
            * np.expm1(np.log(wide["price_sqm_eur_real"][end] / wide["price_sqm_eur_real"][start])),
            "income_real_change_pct": 100
            * np.expm1(
                np.log(wide["income_median_eur_real"][end] / wide["income_median_eur_real"][start])
            ),
        }
    )
    typology = typology.set_index(MUNI_KEY)
    rows = []
    for dimension, values in groups.items():
        joined = own.join(typology[dimension])
        for value in values:
            sub = joined[joined[dimension] == value].drop(columns=dimension)
            rows.append(
                {"dimension": dimension, "group": value, "municipalities_n": len(sub)}
                | sub.median().to_dict()
            )
    return pd.DataFrame(rows)


def group_regression(
    df: pd.DataFrame,
    y: str,
    groups: dict[str, str],
    controls: list[str] | None = None,
    fixed_effects: str | None = None,
) -> pd.DataFrame:
    """OLS of ``y`` on group dummies (HC3 robust errors): the difference of each group from its reference.

    ``groups`` maps a column to its reference value; ``controls`` are numeric columns; ``fixed_effects`` a
    column whose values get their own intercept (absorbed, not reported). Returns ``term``, ``coef``, ``se``,
    ``ci_low``, ``ci_high``, ``p`` and the sample size.
    """
    terms = [f"C({col}, Treatment(reference='{ref}'))" for col, ref in groups.items()]
    formula = f"{y} ~ " + " + ".join([*terms, *(controls or [])])
    if fixed_effects:
        formula += f" + C({fixed_effects})"
    data = df.dropna(subset=[y, *groups, *(controls or [])])
    res = smf.ols(formula, data=data).fit(cov_type="HC3")
    ci = res.conf_int()
    keep = [
        name
        for name in res.params.index
        if any(name.startswith(f"C({col}, ") for col in groups) or name in (controls or [])
    ]
    labels = {}
    for name in keep:
        if name.startswith("C("):
            col = name[2:].split(",")[0]
            level = name.split("[T.")[1].rstrip("]")
            labels[name] = f"{col}: {level} (vs {groups[col]})"
        else:
            labels[name] = name
    return pd.DataFrame(
        {
            "term": [labels[n] for n in keep],
            "coef": res.params[keep].to_numpy(),
            "se": res.bse[keep].to_numpy(),
            "ci_low": ci.loc[keep, 0].to_numpy(),
            "ci_high": ci.loc[keep, 1].to_numpy(),
            "p": res.pvalues[keep].to_numpy(),
            "n_obs": int(res.nobs),
        }
    )


def block_r2(df: pd.DataFrame, y: str, blocks: dict[str, list[str]]) -> pd.DataFrame:
    """R2 and adjusted R2 of ``y`` as blocks of terms are added one after another, on a fixed sample.

    ``blocks`` maps a name to formula terms (numeric columns or ``C(column)``), added in the order given. The
    sample is the rows with ``y`` and every column used, so the steps are comparable. Returns one row per step
    with the cumulative ``r2``, ``r2_adj`` and the ``r2_added`` by that block (order matters when blocks overlap).
    """
    columns = {
        c
        for terms in blocks.values()
        for t in terms
        for c in ([t[2:-1]] if t.startswith("C(") else [t])
    }
    data = df.dropna(subset=[y, *columns])
    rows, used, previous = [], [], 0.0
    for name, terms in blocks.items():
        used += terms
        res = smf.ols(f"{y} ~ " + " + ".join(used), data=data).fit()
        rows.append(
            {
                "block": name,
                "r2": res.rsquared,
                "r2_adj": res.rsquared_adj,
                "r2_added": res.rsquared - previous,
                "n_obs": int(res.nobs),
            }
        )
        previous = res.rsquared
    return pd.DataFrame(rows)


def compare_definitions(
    panel: pd.DataFrame,
    base: str,
    others: dict[str, tuple[str, int, int]],
    level_year: int,
    top_n: int = 20,
) -> pd.DataFrame:
    """How far a conclusion about ``base`` survives another definition of the same indicator (M1).

    ``others`` maps a label to ``(column, start, end)``: the alternative column and the window in which its
    change is compared (windows differ because some series are shorter). For each alternative, on the
    municipalities where both columns exist: the Spearman rank correlation of the levels in ``level_year``
    and of the log changes over the window, the share of municipalities where both agree on the sign of the
    change, how many of the ``top_n`` highest values in ``level_year`` they share, and the median
    percentage change of each in the window, and the share of municipalities where it worsened
    (``worse_pct``, against ``base_worse_pct``). Rank correlations near 1 mean the ranking of places does not
    depend on the choice; the change columns say whether the story about direction does.
    """
    wide = panel.pivot(index=MUNI_KEY, columns=YEAR_KEY)
    rows = []
    for label, (column, start, end) in others.items():
        level = pd.concat([wide[(base, level_year)], wide[(column, level_year)]], axis=1).dropna()
        d = pd.concat(
            [
                np.log(wide[(base, end)] / wide[(base, start)]),
                np.log(wide[(column, end)] / wide[(column, start)]),
            ],
            axis=1,
            keys=["base", "alt"],
        ).dropna()
        shared = len(
            set(level.iloc[:, 0].nlargest(top_n).index)
            & set(level.iloc[:, 1].nlargest(top_n).index)
        )
        rows.append(
            {
                "definition": label,
                "window": f"{start}-{end}",
                "level_municipalities_n": len(level),
                "rank_corr_level": level.corr(method="spearman").iloc[0, 1]
                if len(level) > 2
                else np.nan,
                "change_municipalities_n": len(d),
                "rank_corr_change": d.corr(method="spearman").iloc[0, 1] if len(d) > 2 else np.nan,
                "same_sign_pct": 100 * ((d["base"] > 0) == (d["alt"] > 0)).mean()
                if len(d)
                else np.nan,
                f"top{top_n}_shared": shared,
                "worse_pct": 100 * (d["alt"] > 0).mean() if len(d) else np.nan,
                "base_worse_pct": 100 * (d["base"] > 0).mean() if len(d) else np.nan,
                "median_change_pct": 100 * np.expm1(d["alt"].median()) if len(d) else np.nan,
                "base_median_change_pct": 100 * np.expm1(d["base"].median()) if len(d) else np.nan,
            }
        )
    return pd.DataFrame(rows)
