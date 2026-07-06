"""Filter participant columns (e.g. exclude z-only MT submissions)."""
from __future__ import annotations

from config import ZMT_NAME_MARKERS


def is_zmt_only_name(name: str) -> bool:
    """Heuristic: submission label indicates z-only MT pool implementation."""
    lower = name.lower()
    if "xyz" in lower:
        return False
    if lower.split("_", 1)[0] in {"s07", "s13"}:
        return True
    return any(marker in lower for marker in ZMT_NAME_MARKERS)


def filter_submissions(
    names: list[str],
    *,
    exclude_zmt: bool = True,
) -> list[int]:
    """Return column indices to keep."""
    indices = []
    for i, name in enumerate(names):
        if exclude_zmt and is_zmt_only_name(name):
            continue
        indices.append(i)
    return indices
