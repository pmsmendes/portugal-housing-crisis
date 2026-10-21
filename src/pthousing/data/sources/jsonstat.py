"""Parser for JSON-stat 2.0 datasets (used by Eurostat and Banco de Portugal BPstat)."""

import numpy as np
import pandas as pd


def _codes(category: dict) -> list[str]:
    index = category["index"]
    if isinstance(index, dict):  # code -> position
        return [code for code, _ in sorted(index.items(), key=lambda kv: kv[1])]
    return list(index)


def parse_jsonstat(payload: dict) -> pd.DataFrame:
    """One row per present cell: a column of category codes per dimension, ``value`` and ``status``.

    Values and status may be dense lists or sparse ``{position: value}`` dicts; absent cells are omitted.
    """
    dims = payload["id"]
    sizes = payload["size"]
    codes = [_codes(payload["dimension"][d]["category"]) for d in dims]

    value = payload["value"]
    if isinstance(value, dict):
        positions = np.array(sorted(int(k) for k in value), dtype=np.int64)
        values = np.array([value[str(p)] for p in positions], dtype=float)
    else:
        positions = np.array([i for i, v in enumerate(value) if v is not None], dtype=np.int64)
        values = np.array([value[i] for i in positions], dtype=float)

    status = payload.get("status") or {}
    if isinstance(status, list):
        flags = [status[p] if p < len(status) else None for p in positions]
    else:
        flags = [status.get(str(p)) for p in positions]

    cells = (
        np.unravel_index(positions, sizes)
        if len(positions)
        else [np.array([], dtype=int)] * len(dims)
    )
    out = {d: np.array(codes[i], dtype=object)[cells[i]] for i, d in enumerate(dims)}
    out["value"] = values
    out["status"] = flags
    return pd.DataFrame(out)
