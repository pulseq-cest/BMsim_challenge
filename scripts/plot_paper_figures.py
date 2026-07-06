#!/usr/bin/env python3
"""Generate figures for the BMsim manuscript from spreadsheet data."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from bmsim.download import download_spreadsheet
from bmsim.parser import load_all_cases
from bmsim.plotting import generate_paper_figures
from config import CACHE_XLSX, FIGURES_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xlsx",
        type=Path,
        default=CACHE_XLSX,
        help="Path to spreadsheet XLSX (downloaded if missing)",
    )
    parser.add_argument(
        "--figures-dir",
        type=Path,
        default=FIGURES_DIR,
        help="Output directory for PNG/PDF figures",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download spreadsheet before plotting",
    )
    parser.add_argument(
        "--include-zmt",
        action="store_true",
        help="Include z-only MT submissions in panel plots",
    )
    args = parser.parse_args()

    if args.force_download or not args.xlsx.exists():
        download_spreadsheet(args.xlsx, force=args.force_download)

    cases = load_all_cases(args.xlsx, download=False)
    paths = generate_paper_figures(
        cases,
        args.figures_dir,
        exclude_zmt=not args.include_zmt,
    )
    for p in paths:
        print(f"Wrote {p}")


if __name__ == "__main__":
    main()
