#!/usr/bin/env python3
"""Download fresh data and regenerate all manuscript figures."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PYTHON = SCRIPTS_DIR.parent / ".venv" / "bin" / "python"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Reuse the cached XLSX instead of downloading a fresh spreadsheet export.",
    )
    args = parser.parse_args()

    commands = [
        [str(PYTHON), str(SCRIPTS_DIR / "fetch_spreadsheet.py")],
        [str(PYTHON), str(SCRIPTS_DIR / "plot_paper_figures.py")],
    ]
    if not args.use_cache:
        commands[0].append("--force")
        commands[1].append("--force-download")

    for cmd in commands:
        print(">>", " ".join(cmd))
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
