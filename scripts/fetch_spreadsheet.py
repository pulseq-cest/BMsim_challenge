#!/usr/bin/env python3
"""Download BMsim results spreadsheet and export tidy CSV."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from bmsim.download import download_spreadsheet
from bmsim.parser import cases_to_long_csv, load_all_cases
from config import CACHE_XLSX, DATA_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download XLSX even if cached",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DATA_DIR / "bmsim_results_long.csv",
        help="Output tidy CSV path",
    )
    args = parser.parse_args()

    xlsx = download_spreadsheet(force=args.force)
    print(f"Spreadsheet: {xlsx}")

    cases = load_all_cases(xlsx, download=False)
    print(f"Loaded {len(cases)} case sheets")

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    cases_to_long_csv(cases, args.csv)
    print(f"Wrote {args.csv}")


if __name__ == "__main__":
    main()
