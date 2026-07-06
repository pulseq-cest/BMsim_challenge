"""Paths and IDs for BMsim challenge analysis."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
FIGURES_DIR = REPO_ROOT / "text" / "figures"
CACHE_XLSX = DATA_DIR / "bmsim_results.xlsx"

SPREADSHEET_ID = "1JN7VN-f1ktDrJgokb0FlUFwkH0MWYlPA_jSfnQoFOVc"
XLSX_EXPORT_URL = (
    f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=xlsx"
)

CASE_SHEETS = [f"case {n}" for n in range(1, 9)]

# Substrings in column headers that mark z-only MT implementations (excluded by default).
ZMT_NAME_MARKERS = ("zmt", "z-mt", "z mt", "_z", " only z")

# Default reference: first non-empty submission column (usually M. Zaiss).
DEFAULT_REFERENCE_INDEX = 0
