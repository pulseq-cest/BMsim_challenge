# BMsim analysis scripts

Python tooling to download challenge results from the [Google spreadsheet](https://docs.google.com/spreadsheets/d/1JN7VN-f1ktDrJgokb0FlUFwkH0MWYlPA_jSfnQoFOVc/), relabel submissions as manuscript submission numbers, export tidy tables, and regenerate manuscript figures.

## Setup

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
```

## Usage

Download data and export long-format CSV:

```bash
.venv/bin/python scripts/fetch_spreadsheet.py
```

Regenerate figures into `text/figures/`:

```bash
.venv/bin/python scripts/plot_paper_figures.py
```

Or both:

```bash
.venv/bin/python scripts/run_all.py
```

Print per-case spread metrics (helpful for writing Results):

```bash
.venv/bin/python scripts/compute_metrics.py
```

### Options

- `fetch_spreadsheet.py --force` — re-download the XLSX
- `plot_paper_figures.py --include-zmt` — keep z-only MT columns in panel plots (default: excluded by name)
- `plot_paper_figures.py --figures-dir PATH` — custom output directory

## Layout

| Path | Role |
|------|------|
| `config.py` | Spreadsheet ID, paths, constants |
| `bmsim/download.py` | Download public XLSX export |
| `bmsim/parser.py` | Parse `case 1` … `case 8` sheets |
| `bmsim/submissions.py` | Map spreadsheet names to manuscript submission numbers |
| `bmsim/mtrasym.py` | Normalized Z and MTR<sub>asym</sub> |
| `bmsim/filters.py` | Exclude z-only MT submissions |
| `bmsim/plotting.py` | Figure builders |
| `fetch_spreadsheet.py` | CLI: download + CSV |
| `plot_paper_figures.py` | CLI: all paper figures |
| `compute_metrics.py` | CLI: numeric spread table |
| `run_all.py` | CLI: fetch + plot |

Cached spreadsheet: `data/bmsim_results.xlsx`  
Tidy export: `data/bmsim_results_long.csv`  
Parsed submission columns use `S01`, `S02`, ... labels; the tidy CSV also keeps the original spreadsheet column name in `original_participant`.

## Output figures

- `Figure_CASE_12.png`, `Figure_CASE_34.png`, `Figure_CASE_56.png`, `Figure_CASE_78.png`
- `Case_3_zMT_comparison.png`
- `All_Cases_Z_and_MTRasym_ref.png`
- `All_Cases_Z_and_MTRasym_diff.png`
- `Figure_max_Z_spread.png` (summary bar chart)
- `Figure_BART_precision_12.png`, `Figure_BART_precision_34.png`, `Figure_BART_precision_56.png`, `Figure_BART_precision_78.png` (single- vs double-precision BART vs S02)
- `Case_6_timestep.png` (S03 Case 6 fixed-timestep convergence)

Reference column for Δ plots: first remaining submission after filtering (typically M. Zaiss).
