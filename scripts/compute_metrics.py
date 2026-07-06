#!/usr/bin/env python3
"""Print per-case spread metrics (for Results section text)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import numpy as np

from bmsim.download import download_spreadsheet
from bmsim.filters import filter_submissions
from bmsim.mtrasym import compute_mtrasym
from bmsim.parser import load_all_cases
from config import CACHE_XLSX


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-zmt", action="store_true")
    args = parser.parse_args()

    if not CACHE_XLSX.exists():
        download_spreadsheet()

    cases = load_all_cases(download=False)
    exclude_zmt = not args.include_zmt

    print("case\tn_submitters\tmax_dZ\tmax_dMTRasym\tunique_clusters(rough)")
    for num in sorted(cases):
        case = cases[num]
        keep = filter_submissions(case.participant_names, exclude_zmt=exclude_zmt)
        names = [case.participant_names[i] for i in keep]
        if not names:
            continue

        z_list = []
        mtr_list = []
        for name in names:
            offsets = case.offsets_ppm
            z = case.submissions[name].values.astype(float)
            z_list.append(z)
            _, mtr = compute_mtrasym(offsets, z)
            mtr_list.append(mtr)

        display_mask = ~np.isclose(case.offsets_ppm, -300.0, atol=1e-6, rtol=0)
        stack = np.vstack([z[display_mask] for z in z_list])
        max_dz = float(np.nanmax(np.nanmax(stack, axis=0) - np.nanmin(stack, axis=0)))

        if mtr_list and all(m.size for m in mtr_list):
            min_len = min(len(m) for m in mtr_list)
            mtr_stack = np.vstack([m[:min_len] for m in mtr_list])
            max_dmtr = float(
                np.nanmax(np.nanmax(mtr_stack, axis=0) - np.nanmin(mtr_stack, axis=0))
            )
        else:
            max_dmtr = float("nan")

        print(f"{num}\t{len(names)}\t{max_dz:.6f}\t{max_dmtr:.6f}")


if __name__ == "__main__":
    main()
