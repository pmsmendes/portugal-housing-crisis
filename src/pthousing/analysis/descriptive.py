"""Descriptive statistics, growth rates and group comparisons (coastal/inland, urban/rural, tourist)."""

import pandas as pd

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
