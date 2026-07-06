#!/usr/bin/env python3
"""Calculate per-case Z-spectrum and MTRasym spread metrics.

By default, entries labeled as z-only MT simulations are excluded, matching the
main manuscript figures. The normalization offset at -300 ppm is excluded from
Z-spectrum spread calculations.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from bmsim.download import download_spreadsheet
from bmsim.filters import filter_submissions
from bmsim.mtrasym import compute_mtrasym
from bmsim.parser import load_all_cases
from config import CACHE_XLSX


def _spread_summary(stack: np.ndarray) -> dict[str, float]:
    """Return point-wise spread summaries for a participant x offset stack."""
    spread = np.nanmax(stack, axis=0) - np.nanmin(stack, axis=0)
    return {
        "max": float(np.nanmax(spread)),
        "p95": float(np.nanpercentile(spread, 95)),
        "median": float(np.nanmedian(spread)),
    }


def calculate_case_spreads(
    *,
    include_zmt: bool = False,
    force_download: bool = False,
) -> list[dict[str, object]]:
    """Calculate per-case spread metrics from the cached Google Sheet export."""
    if force_download or not CACHE_XLSX.exists():
        download_spreadsheet(CACHE_XLSX, force=force_download)

    cases = load_all_cases(CACHE_XLSX, download=False)
    rows: list[dict[str, object]] = []

    for case_number in sorted(cases):
        case = cases[case_number]
        keep = filter_submissions(case.participant_names, exclude_zmt=not include_zmt)
        names = [case.participant_names[i] for i in keep]
        if not names:
            continue

        display_mask = ~np.isclose(case.offsets_ppm, -300.0, atol=1e-6, rtol=0)
        z_stack = np.vstack(
            [case.submissions[name].values.astype(float)[display_mask] for name in names]
        )
        z_summary = _spread_summary(z_stack)

        mtrasym_values = [
            compute_mtrasym(case.offsets_ppm, case.submissions[name].values.astype(float))[1]
            for name in names
        ]
        if mtrasym_values and all(values.size for values in mtrasym_values):
            min_len = min(values.size for values in mtrasym_values)
            mtrasym_stack = np.vstack([values[:min_len] for values in mtrasym_values])
            mtrasym_summary = _spread_summary(mtrasym_stack)
        else:
            mtrasym_summary = {"max": float("nan"), "p95": float("nan"), "median": float("nan")}

        rows.append(
            {
                "case": case_number,
                "n_submitters": len(names),
                "max_dZ": z_summary["max"],
                "p95_dZ": z_summary["p95"],
                "median_dZ": z_summary["median"],
                "max_dMTRasym": mtrasym_summary["max"],
                "p95_dMTRasym": mtrasym_summary["p95"],
                "median_dMTRasym": mtrasym_summary["median"],
            }
        )

    return rows


def _format_float(value: object) -> str:
    if not isinstance(value, float):
        return str(value)
    if np.isnan(value):
        return "nan"
    return f"{value:.6g}"


def print_table(rows: list[dict[str, object]]) -> None:
    fieldnames = list(rows[0].keys()) if rows else []
    if not fieldnames:
        return
    print("\t".join(fieldnames))
    for row in rows:
        print("\t".join(_format_float(row[field]) for field in fieldnames))


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-zmt",
        action="store_true",
        help="Include entries labeled as z-only MT simulations.",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download the spreadsheet before calculating metrics.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Optional path for writing the metrics as CSV.",
    )
    args = parser.parse_args()

    rows = calculate_case_spreads(
        include_zmt=args.include_zmt,
        force_download=args.force_download,
    )
    print_table(rows)
    if args.csv:
        write_csv(rows, args.csv)


if __name__ == "__main__":
    main()
