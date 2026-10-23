"""Load and validate scenario assumptions from config/scenarios.yaml.

Behavioural and policy parameters are ``Range`` objects (low, mid, high). A deterministic run uses ``mid``;
an uncertainty run draws each parameter from a triangular distribution over its range. Fixed facts are floats.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from pthousing.config import SCENARIOS_YAML

SCENARIO_KEYS = (
    "net_migration_per_year",
    "household_income_growth_real_pct",
    "mortgage_rate_pct",
    "completions_per_year",
    "other_demand_half_life_years",
)
LEVER_KEYS = (
    "construction_boost_units",
    "vacant_renovation_units",
    "public_housing_units",
    "imi_rate_change_pp",
    "imt_rate_change_pp",
)


@dataclass(frozen=True)
class Range:
    """A parameter with a central value and bounds."""

    low: float
    mid: float
    high: float

    def __post_init__(self):
        if not self.low <= self.mid <= self.high:
            raise ValueError(f"need low <= mid <= high, got {self.low}, {self.mid}, {self.high}")

    def at(self, which: str) -> float:
        return getattr(self, which)

    def draw(self, rng: np.random.Generator, n: int) -> np.ndarray:
        """``n`` draws, triangular over (low, mid, high); a degenerate range returns its value."""
        if self.low == self.high:
            return np.full(n, float(self.mid))
        return rng.triangular(self.low, self.mid, self.high, n)


@dataclass(frozen=True)
class Assumptions:
    horizon_years: int
    base_year: int
    start_year: int
    near_term_year: int
    policy_start_year: int
    common: dict[str, float]
    scenarios: dict[str, dict[str, float]]
    ranges: dict[str, Range]  # flat names: "price_flexibility_balance", "public_housing.crowd_out"
    fixed: dict[str, float]
    fiscal: dict[str, float]
    packages: dict[str, dict[str, float]]
    notes: dict[str, dict] = field(
        default_factory=dict
    )  # status and source of each parameter group

    @property
    def end_year(self) -> int:
        return self.start_year + self.horizon_years


def _is_range(node) -> bool:
    return isinstance(node, dict) and {"low", "mid", "high"} <= node.keys()


def _check_filled(node, path: str) -> None:
    if node is None:
        raise ValueError(f"scenarios.yaml: {path} is empty")
    if isinstance(node, dict):
        for key, value in node.items():
            _check_filled(value, f"{path}.{key}")


def load(path: Path = SCENARIOS_YAML) -> Assumptions:
    """Read the yaml, check that no value is empty and that every scenario defines every input."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    _check_filled(raw, "scenarios.yaml")
    for name, values in raw["scenarios"].items():
        missing = set(SCENARIO_KEYS) - values.keys()
        if missing:
            raise ValueError(f"scenario {name!r} lacks {sorted(missing)}")
    ranges: dict[str, Range] = {}
    fixed: dict[str, float] = {}
    notes: dict[str, dict] = {}
    for key, node in raw["behaviour"].items():
        notes[key] = {"status": node.get("status", ""), "source": node.get("source", "")}
        if _is_range(node):
            ranges[key] = Range(node["low"], node["mid"], node["high"])
        else:
            fixed[key] = float(node["value"])
    for lever, node in raw["policies"].items():
        notes[lever] = {"status": node.get("status", ""), "source": node.get("source", "")}
        for key, value in node.items():
            if _is_range(value):
                ranges[f"{lever}.{key}"] = Range(value["low"], value["mid"], value["high"])
    fiscal = {k: v for k, v in raw["fiscal"].items() if isinstance(v, int | float)}
    packages = raw.get("packages", {})
    for name, sizes in packages.items():
        unknown = set(sizes) - set(LEVER_KEYS)
        if unknown:
            raise ValueError(f"package {name!r} has unknown levers {sorted(unknown)}")
    return Assumptions(
        horizon_years=int(raw["horizon_years"]),
        base_year=int(raw["base_year"]),
        start_year=int(raw["start_year"]),
        near_term_year=int(raw["near_term_year"]),
        policy_start_year=int(raw["policy_start_year"]),
        common=dict(raw["common"]),
        scenarios={k: dict(v) for k, v in raw["scenarios"].items()},
        ranges=ranges,
        fixed=fixed,
        fiscal=fiscal,
        packages={k: dict(v or {}) for k, v in packages.items()},
        notes=notes,
    )
