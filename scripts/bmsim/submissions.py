"""Submission-number labels for spreadsheet columns."""
from __future__ import annotations

from collections import Counter, defaultdict


def normalize_submission_name(name: str) -> str:
    """Normalize spreadsheet labels for heuristic matching."""
    return (
        name.lower()
        .replace(" ", "")
        .replace(".", "")
        .replace("_", "")
        .replace("-", "")
    )


def submission_number(name: str) -> int | None:
    """Map spreadsheet column labels to manuscript submission numbers."""
    key = normalize_submission_name(name)
    if "stollberger2" in key:
        return 4
    if "stollberger" in key:
        return 3
    if "zaiss" in key:
        return 1
    if "schuenke" in key or "bmctool" in key:
        return 2
    if "zeng" in key or "yadav" in key:
        return 5
    if "vladimirov" in key or "perlman" in key:
        return 6
    if "zu" in key or "viswanathan" in key:
        return 7
    if "wang" in key and "xu" in key:
        return 8
    if "longo" in key or "ramdhane" in key:
        return 9
    if "fabian" in key:
        return 10
    if "kang" in key or "singh" in key or "heo" in key:
        return 11
    if "zhang" in key or "huang" in key:
        return 12
    if "wu" in key or "zhou" in key:
        return 18
    if "hou" in key:
        return 13
    if "bart" in key or "juschitz" in key or "scholand" in key:
        return 14
    if "quach" in key:
        return 15
    if "zimmer" in key or "mrpro" in key:
        return 16
    if "cohen" in key:
        return 17
    if "parnianpour" in key or "pioro" in key:
        return 19
    if "pan" in key or "tee" in key:
        return 20
    return None


def base_submission_label(name: str) -> str:
    """Return the manuscript submission label, e.g. S01."""
    number = submission_number(name)
    if number is None:
        return "S??"
    return f"S{number:02d}"


def unique_submission_labels(names: list[str]) -> list[str]:
    """Return stable unique labels for raw spreadsheet columns.

    The base label is the manuscript submission number. If a case contains
    multiple columns from the same submission, suffixes are appended to keep
    DataFrame columns unique while preserving the base submission number.
    """
    base_to_indices: dict[str, list[int]] = defaultdict(list)
    for index, name in enumerate(names):
        base_to_indices[base_submission_label(name)].append(index)

    labels = [""] * len(names)
    for base, indices in base_to_indices.items():
        if len(indices) == 1:
            labels[indices[0]] = base
            continue

        non_zmt_indices = [
            index for index in indices if "zmt" not in normalize_submission_name(names[index])
        ]
        single_non_zmt = len(non_zmt_indices) == 1
        variant_index = 0
        for index in indices:
            name = names[index]
            if "zmt" in normalize_submission_name(name):
                labels[index] = f"{base}_zMT"
                continue
            if single_non_zmt:
                labels[index] = base
                continue
            variant_index += 1
            labels[index] = f"{base}_{variant_index}"

    seen: Counter[str] = Counter()
    for index, label in enumerate(labels):
        seen[label] += 1
        if seen[label] > 1:
            labels[index] = f"{label}_{seen[label]}"
    return labels


def display_submission_label(label: str) -> str:
    """Return the plot legend label for a parsed submission column."""
    base, separator, suffix = label.partition("_")
    if not separator:
        return base
    if suffix.lower() == "zmt":
        return base
    first_suffix = suffix.split("_", 1)[0]
    if first_suffix.isdigit():
        letter_index = int(first_suffix) - 1
        # S15_1 is the default 5th-order CESTSim.jl submission used in all other cases.
        if base in {"S14", "S15"} and first_suffix == "1":
            return base
        if 0 <= letter_index < 26:
            return f"{base}{chr(ord('a') + letter_index)}"
    return label
