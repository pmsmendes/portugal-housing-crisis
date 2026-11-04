"""The committed notebooks must render on GitHub (outputs saved) and must not leak machine paths."""

import json
import re
from pathlib import Path

import pytest

NOTEBOOKS = sorted((Path(__file__).resolve().parents[1] / "notebooks").glob("*/*.ipynb"))
MACHINE_PATH = re.compile(r"[A-Za-z]:[\/]{1,4}(Users|Projects)|AppData|\.venv|pmigu", re.IGNORECASE)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_notebooks_are_found():
    assert len(NOTEBOOKS) > 40


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_has_saved_outputs_and_no_machine_paths(path):
    nb = _load(path)
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert any(c.get("outputs") for c in code), (
        "no saved outputs: GitHub would show an empty notebook"
    )
    assert not MACHINE_PATH.search(path.read_text(encoding="utf-8")), "machine path in the notebook"
    errors = [o for c in code for o in c.get("outputs", []) if o.get("output_type") == "error"]
    assert not errors, "a cell saved an error"
