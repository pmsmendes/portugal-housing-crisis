"""Data pipeline CLI: download -> clean -> build panel.

Usage: uv run python scripts/run_pipeline.py [--sources ine bportugal ...] [--skip-download]
Thin wrapper only; all logic lives in src/pthousing/data/.
"""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="*", help="Source ids from config/sources.yaml")
    parser.add_argument("--skip-download", action="store_true")
    parser.parse_args()
    raise SystemExit("Pipeline not implemented yet (Phase 1).")


if __name__ == "__main__":
    main()
