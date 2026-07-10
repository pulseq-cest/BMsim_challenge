#!/usr/bin/env python3
"""Plot S03 Case 7 spectra simulated with different timesteps."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from bmsim.plotting import plot_case_timestep_comparison
from config import FIGURES_DIR

DEFAULT_MAT = SCRIPTS_DIR / "Case7_timestep.mat"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mat",
        type=Path,
        default=DEFAULT_MAT,
        help="Path to Case7_timestep.mat",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=FIGURES_DIR / "Case_7_timestep.png",
        help="Output figure path",
    )
    args = parser.parse_args()

    path = plot_case_timestep_comparison(
        args.output,
        args.mat,
        case_number=7,
        pool_model="WM 5 pool",
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
