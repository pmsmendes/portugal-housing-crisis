"""Data pipeline CLI: download -> clean (interim parquet) -> build panels -> typology -> validate.

Usage: uv run python scripts/run_pipeline.py [--sources ine bportugal ...] [--skip-download] [--refresh]
Thin wrapper only; all logic lives in src/pthousing/data/.
"""

import argparse

from pthousing.data import build_panel, interim, typology, validate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources",
        nargs="*",
        choices=interim.SOURCES,
        help="Raw sources to download (default: all)",
    )
    parser.add_argument("--skip-download", action="store_true", help="Use the files in data/raw")
    parser.add_argument("--refresh", action="store_true", help="Download again even if cached")
    args = parser.parse_args()

    if not args.skip_download:
        interim.download(args.sources, refresh=args.refresh)
    paths = interim.build_all()
    print(f"Built {len(paths)} interim tables in data/interim")
    panels = build_panel.build_all()
    print(f"Built {len(panels)} panels in data/processed")
    print(f"Built the municipality typology ({len(typology.build())} rows) in data/external")
    report = validate.validate_all(strict=False)
    failed = report[~report["ok"]]
    print(f"Validation: {int(report['ok'].sum())} of {len(report)} checks pass")
    if not failed.empty:
        print(failed.to_string(index=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
