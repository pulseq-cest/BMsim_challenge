"""Download the public Google spreadsheet as XLSX."""
from __future__ import annotations

import urllib.request
from pathlib import Path

from config import CACHE_XLSX, DATA_DIR, XLSX_EXPORT_URL


def download_spreadsheet(
    destination: Path | None = None,
    *,
    force: bool = False,
) -> Path:
    """Download spreadsheet export; reuse cached file unless ``force``."""
    dest = destination or CACHE_XLSX
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        return dest

    req = urllib.request.Request(
        XLSX_EXPORT_URL,
        headers={"User-Agent": "bmsim-analysis/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        dest.write_bytes(response.read())

    return dest
