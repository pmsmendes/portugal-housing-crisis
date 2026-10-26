"""How far each association survives added controls, and which designs test their own assumption (M3).

A *ladder* is one driver followed through the specifications of an earlier notebook, ordered from the least to the most
controlled (same district, then coast and density class, then region-year effects, then the foreign-resident change).
Each rung has a coefficient and a p-value; ``classify`` reads the sequence by the rule the project uses throughout: a driver
"matters" at a rung if its coefficient is below p = 0.05, and it matters overall only if it keeps its sign and stays below
0.05 at every rung. This says how robust an adjusted association is; it does not make it causal. A *design check* is a test
of the identifying assumption itself (a pre-trend, a placebo on the future); only designs that pass one can support causal
language, and ``design_verdict`` reads their p-values. Functions take the result tables of earlier notebooks.
"""

import numpy as np
import pandas as pd

ALPHA = 0.05


def rungs(table: pd.DataFrame, term: str, specs: list[str]) -> pd.DataFrame:
    """The coefficient, p-value and ``coef_per_sd`` of ``term`` in each of ``specs`` (in that order); NaN where a rung lacks it."""
    out = []
    for spec in specs:
        row = table[(table["spec"] == spec) & (table["term"] == term)]
        out.append(
            {
                "spec": spec,
                "coef": float(row["coef"].iloc[0]) if len(row) else np.nan,
                "p": float(row["p"].iloc[0]) if len(row) else np.nan,
                "coef_per_sd": float(row["coef_per_sd"].iloc[0]) if len(row) else np.nan,
            }
        )
    return pd.DataFrame(out)


def classify(r: pd.DataFrame, alpha: float = ALPHA) -> str:
    """Name the path of a ladder.

    ``holds``: below ``alpha`` with one sign at every rung; ``fades``: below at the first rung, not at the last;
    ``emerges``: the reverse; ``flips``: below at two rungs with opposite signs; ``never``: below at none;
    ``mixed``: any other pattern. Rungs without an estimate are ignored.
    """
    r = r.dropna(subset=["p"])
    if r.empty:
        return "not estimated"
    sig = r["p"] < alpha
    if not sig.any():
        return "never"
    signs = np.sign(r.loc[sig, "coef"])
    if signs.nunique() > 1:
        return "flips"
    if sig.all():
        return "holds"
    if sig.iloc[0] and not sig.iloc[-1]:
        return "fades"
    if not sig.iloc[0] and sig.iloc[-1]:
        return "emerges"
    return "mixed"


def design_verdict(p_assumption: float, direction: str, alpha: float = ALPHA) -> str:
    """Read the p-value of the test of a design's own assumption.

    ``direction`` says what a small p means: ``"fails"`` (a pre-trend or a lead in the placebo: small p means the assumption is
    rejected) is the only case used so far. Large p is "not rejected", which is not proof that it holds.
    """
    if direction != "fails":
        raise ValueError(f"unknown direction {direction!r}")
    return "assumption rejected" if p_assumption < alpha else "assumption not rejected"


def summary(classes: pd.Series) -> pd.Series:
    """Count of ladders by class, in a fixed order, zeros included."""
    order = ["holds", "fades", "emerges", "flips", "mixed", "never", "not estimated"]
    return classes.value_counts().reindex(order, fill_value=0)
