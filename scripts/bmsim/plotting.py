"""Generate manuscript figures from parsed spreadsheet data."""
from __future__ import annotations

from contextlib import contextmanager
from itertools import combinations
from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from bmsim.filters import filter_submissions
from bmsim.mtrasym import compute_mtrasym
from bmsim.parser import CaseData
from bmsim.submissions import display_submission_label
from config import FIGURES_DIR, SCRIPTS_ROOT

REFERENCE_SUBMISSION_LABEL = "S02"

PLOT_FONT_SIZE = 12
PLOT_FONT_SIZE_LARGE = 17
PLOT_FONT_SIZE_OVERVIEW = 14
PLOT_LEGEND_FONT_SIZE = 11
PLOT_SUBPLOT_TITLE_FONT_SIZE = 12
PLOT_SUPTITLE_FONT_SIZE = 14
PLOT_LINE_WIDTH = 1.3
PLOT_LINE_WIDTH_STRONG = 1.5

_RC_STYLE_KEYS = (
    "font.size",
    "axes.titlesize",
    "axes.labelsize",
    "xtick.labelsize",
    "ytick.labelsize",
    "legend.fontsize",
    "lines.linewidth",
)


@contextmanager
def _plot_style(
    *,
    font_size: float | None = None,
    legend_font_size: float | None = None,
):
    """Temporarily apply manuscript plot typography."""
    old = {key: plt.rcParams[key] for key in _RC_STYLE_KEYS}
    base = font_size or PLOT_FONT_SIZE
    legend = legend_font_size or PLOT_LEGEND_FONT_SIZE
    plt.rcParams.update(
        {
            "font.size": base,
            "axes.titlesize": PLOT_SUBPLOT_TITLE_FONT_SIZE,
            "axes.labelsize": base,
            "xtick.labelsize": base - 1,
            "ytick.labelsize": base - 1,
            "legend.fontsize": legend,
            "lines.linewidth": PLOT_LINE_WIDTH,
        }
    )
    try:
        yield
    finally:
        plt.rcParams.update(old)


def _display_offset_mask(offsets: np.ndarray, m0_ppm: float = -300.0) -> np.ndarray:
    """Finite offsets excluding the M0 normalization scan."""
    offsets = np.asarray(offsets, dtype=float)
    return np.isfinite(offsets) & ~np.isclose(offsets, m0_ppm, atol=1e-6, rtol=0)


def _line_style(index: int):
    """Cycle visually distinct line styles for dense comparison plots."""
    styles = [
        "-",
        "--",
        "-.",
        ":",
        (0, (5, 1)),
        (0, (3, 1, 1, 1)),
        (0, (1, 1)),
        (0, (5, 2, 1, 2)),
    ]
    return styles[index % len(styles)]


def _submission_variant_index(label: str) -> int:
    """Return 0 for the primary trace and 1+ for solver variants (e.g. S14b)."""
    base, separator, suffix = label.partition("_")
    if not separator:
        return 0
    if suffix.lower() == "zmt":
        return 0
    first_suffix = suffix.split("_", 1)[0]
    if not first_suffix.isdigit():
        return 0
    letter_index = int(first_suffix) - 1
    if base in {"S14", "S15"} and first_suffix == "1":
        return 0
    return letter_index


def _submission_index(label: str) -> int:
    base = display_submission_label(label).split()[0]
    match = re.match(r"S(\d+)", base)
    if not match:
        return 999
    return int(match.group(1)) - 1


_VARIANT_LINESTYLES = ("--", "-.", ":", (0, (5, 1)), (0, (3, 1, 1, 1)))


def _submission_color(label: str):
    cmap = plt.get_cmap("tab20")
    base_idx = _submission_index(label)
    variant = _submission_variant_index(label)
    return cmap((base_idx + variant * 11) % 20)


def _submission_linestyle(label: str):
    variant = _submission_variant_index(label)
    if variant > 0:
        return _VARIANT_LINESTYLES[(variant - 1) % len(_VARIANT_LINESTYLES)]
    return _line_style(_submission_index(label))


def _submission_sort_key(label: str) -> tuple[int, int, str]:
    return (
        _submission_index(label),
        _submission_variant_index(label),
        display_submission_label(label),
    )


def _sort_submission_names(names: list[str]) -> list[str]:
    return sorted(names, key=_submission_sort_key)


def _is_labeled_submission(name: str) -> bool:
    return not display_submission_label(name).startswith("S??")


def _labeled_submission_names(names: list[str]) -> list[str]:
    return _sort_submission_names([name for name in names if _is_labeled_submission(name)])


def _reference_submission_name(
    names: list[str],
    *,
    reference_label: str = REFERENCE_SUBMISSION_LABEL,
) -> str:
    """Return the requested reference submission from already-filtered names."""
    for name in names:
        if display_submission_label(name) == reference_label:
            return name
    raise ValueError(f"Reference submission {reference_label} is not present in plotted names")


def _deduplicate_submission_names(
    names: list[str],
    *,
    required_names: list[str] | None = None,
) -> list[str]:
    """Keep at most one plotted trace per base submission label."""
    required_names = required_names or []
    required_bases = {
        display_submission_label(name)
        for name in required_names
        if name in names
    }
    selected = []
    seen = set()
    for name in required_names:
        if name not in names:
            continue
        base = display_submission_label(name)
        if base in seen:
            continue
        selected.append(name)
        seen.add(base)
    for name in names:
        base = display_submission_label(name)
        if base in seen:
            continue
        # Prefer required entries if another variant from the same submission was forced.
        if base in required_bases:
            continue
        selected.append(name)
        seen.add(base)
    return selected


def _sorted_legend(handles, labels):
    by_label = {}
    for label, handle in zip(labels, handles):
        by_label.setdefault(label, handle)
    pairs = sorted(by_label.items(), key=lambda item: _submission_sort_key(item[0]))
    if not pairs:
        return [], []
    sorted_labels, sorted_handles = zip(*pairs)
    return list(sorted_handles), list(sorted_labels)


def _zmt_comparison_legend_sort_key(label: str) -> tuple[int, int, int, str]:
    mt_group = 1 if " zMT" in label else 0
    subm_number, variant, display = _submission_sort_key(label)
    return mt_group, subm_number, variant, display


def _sorted_zmt_comparison_legend(handles, labels):
    pairs = sorted(zip(labels, handles), key=lambda item: _zmt_comparison_legend_sort_key(item[0]))
    if not pairs:
        return [], []
    sorted_labels, sorted_handles = zip(*pairs)
    return list(sorted_handles), list(sorted_labels)


def _spectra_for_participant(
    case: CaseData,
    name: str,
    *,
    normalize: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    z = case.submissions[name].values.astype(float)
    offsets = case.offsets_ppm
    asym_ppm, mtrasym = compute_mtrasym(offsets, z)
    return offsets, z, asym_ppm, mtrasym


def _z_rms_distance(a: np.ndarray, b: np.ndarray) -> float:
    finite = np.isfinite(a) & np.isfinite(b)
    if np.count_nonzero(finite) == 0:
        return float("nan")
    return float(np.sqrt(np.nanmean((a[finite] - b[finite]) ** 2)))


def _pointwise_z_spread(spectra: list[np.ndarray]) -> float:
    if len(spectra) < 2:
        return 0.0
    stack = np.vstack(spectra)
    spread = np.nanmax(stack, axis=0) - np.nanmin(stack, axis=0)
    return float(np.nanmax(spread))


def _format_cluster_spread(value: float) -> str:
    if not np.isfinite(value):
        return "n/a"
    if value == 0.0:
        return "0"
    if value < 1e-2:
        return f"{value:.2e}"
    return f"{value:.3g}"


MAIN_CLUSTER_SPREAD_THRESHOLD = 0.01
MAIN_CLUSTER_SECOND_GAP_RATIO = 4.0


def _gap_split_index(
    ranked: list[tuple[float, str]],
    *,
    min_percentile: float,
    min_ratio: float = 0.0,
) -> int:
    """Return the last inlier index before the strongest qualifying distance gap."""
    if len(ranked) <= 1:
        return len(ranked) - 1

    distances = np.array([distance for distance, _ in ranked], dtype=float)
    percentile_cutoff = float(np.percentile(distances, min_percentile))
    split_index = len(ranked) - 1
    best_score = -1.0
    for index in range(len(ranked) - 1):
        lower_distance = ranked[index][0]
        gap = ranked[index + 1][0] - lower_distance
        if lower_distance < percentile_cutoff:
            continue
        score = gap / max(lower_distance, 1e-15)
        if score < min_ratio:
            continue
        if score > best_score:
            best_score = score
            split_index = index
    return split_index


def _tighten_cluster_by_spread(
    cluster: list[str],
    spectra: dict[str, np.ndarray],
    *,
    min_size: int = 5,
    relative_improvement: float = 0.25,
) -> list[str]:
    """Iteratively drop submissions that substantially increase peak Z spread."""
    members = list(cluster)
    while len(members) > min_size:
        spread = _pointwise_z_spread([spectra[name] for name in members])
        best_remove: str | None = None
        best_spread = spread
        for name in members:
            reduced = [member for member in members if member != name]
            candidate_spread = _pointwise_z_spread([spectra[member] for member in reduced])
            if candidate_spread < best_spread * (1.0 - relative_improvement):
                best_spread = candidate_spread
                best_remove = name
        if best_remove is None:
            break
        members.remove(best_remove)
    return members


def identify_main_cluster(
    case: CaseData,
    names: list[str],
    *,
    reference_label: str = REFERENCE_SUBMISSION_LABEL,
) -> tuple[list[str], float]:
    """Identify the visually dominant submission cluster for one case.

  Submissions are first ranked by RMS Z-spectrum distance to the reference
  (S02) and split before the strongest relative gap among distances above the
  75th percentile. If the resulting cluster still shows a large peak Z spread,
  a second gap split (25th percentile, ratio >= 4) and optional spread-based
  pruning are applied.
    """
    if len(names) < 2:
        return list(names), 0.0

    ref_name = _reference_submission_name(names, reference_label=reference_label)
    display_mask = _display_offset_mask(case.offsets_ppm)
    spectra = {
        name: case.submissions[name].values.astype(float)[display_mask] for name in names
    }
    ref = spectra[ref_name]
    ranked = sorted((_z_rms_distance(spectra[name], ref), name) for name in names)
    split_index = _gap_split_index(ranked, min_percentile=75.0)
    cluster = [name for _, name in ranked[: split_index + 1]]
    max_spread = _pointwise_z_spread([spectra[name] for name in cluster])

    if max_spread > MAIN_CLUSTER_SPREAD_THRESHOLD:
        ranked_cluster = sorted(
            (_z_rms_distance(spectra[name], ref), name) for name in cluster
        )
        second_split = _gap_split_index(
            ranked_cluster,
            min_percentile=25.0,
            min_ratio=MAIN_CLUSTER_SECOND_GAP_RATIO,
        )
        cluster = [name for _, name in ranked_cluster[: second_split + 1]]
        max_spread = _pointwise_z_spread([spectra[name] for name in cluster])

    if max_spread > MAIN_CLUSTER_SPREAD_THRESHOLD:
        cluster = _tighten_cluster_by_spread(cluster, spectra)
        max_spread = _pointwise_z_spread([spectra[name] for name in cluster])

    return cluster, max_spread


def _cluster_z_envelope(
    case: CaseData,
    cluster_names: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return offsets and point-wise Z min/max for a submission cluster."""
    display_mask = _display_offset_mask(case.offsets_ppm)
    z_stack = np.vstack(
        [
            case.submissions[name].values.astype(float)[display_mask]
            for name in cluster_names
        ]
    )
    offsets = case.offsets_ppm[display_mask]
    return offsets, np.nanmin(z_stack, axis=0), np.nanmax(z_stack, axis=0)


MAIN_CLUSTER_LABEL_XY = (0.06, 0.12)


def _main_cluster_wing_mask(
    offsets: np.ndarray,
    z_min: np.ndarray,
    z_max: np.ndarray,
) -> np.ndarray:
    finite = np.isfinite(offsets) & np.isfinite(z_min) & np.isfinite(z_max)
    abs_offsets = np.abs(offsets[finite])
    wing_threshold = float(np.percentile(abs_offsets, 55))
    wing_mask = finite & (np.abs(offsets) >= wing_threshold)
    positive_wing = wing_mask & (offsets > 0)
    if np.count_nonzero(positive_wing) >= 3:
        search_mask = positive_wing
    elif np.count_nonzero(wing_mask) >= 3:
        search_mask = wing_mask
    else:
        search_mask = finite

    search_indices = np.flatnonzero(search_mask)
    far_threshold = float(np.percentile(offsets[search_indices], 70))
    far_mask = search_mask & (offsets >= far_threshold)
    if np.count_nonzero(far_mask) < 2:
        return search_mask
    return far_mask


def _main_cluster_envelope_anchor(
    ax,
    offsets: np.ndarray,
    z_min: np.ndarray,
    z_max: np.ndarray,
) -> tuple[float, float]:
    """Return a point on the cluster envelope boundary nearest the label."""
    wing_mask = _main_cluster_wing_mask(offsets, z_min, z_max)
    wing_offsets = offsets[wing_mask]
    wing_z_min = z_min[wing_mask]
    wing_z_max = z_max[wing_mask]

    display_x, display_y = ax.transAxes.transform(MAIN_CLUSTER_LABEL_XY)
    label_x, label_y = ax.transData.inverted().transform((display_x, display_y))

    index = int(np.argmin(np.abs(wing_offsets - label_x)))
    anchor_x = float(wing_offsets[index])
    mid_y = 0.5 * (wing_z_min[index] + wing_z_max[index])
    if label_y <= mid_y:
        anchor_y = float(wing_z_min[index])
    else:
        anchor_y = float(wing_z_max[index])
    return anchor_x, anchor_y


def _main_cluster_label_layout(
    ax,
    offsets: np.ndarray,
    z_min: np.ndarray,
    z_max: np.ndarray,
) -> tuple[tuple[float, float], tuple[float, float], str, str]:
    """Pick an envelope anchor on the cluster band and a bottom-left label position."""
    finite = np.isfinite(offsets) & np.isfinite(z_min) & np.isfinite(z_max)
    if not np.any(finite):
        return (0.0, 1.0), MAIN_CLUSTER_LABEL_XY, "left", "bottom"

    anchor_xy = _main_cluster_envelope_anchor(ax, offsets, z_min, z_max)
    return anchor_xy, MAIN_CLUSTER_LABEL_XY, "left", "bottom"


def _plot_main_cluster_envelope(
    ax,
    offsets: np.ndarray,
    z_min: np.ndarray,
    z_max: np.ndarray,
) -> None:
    """Shade and outline the main-cluster Z envelope on the spectrum panel."""
    finite = np.isfinite(offsets) & np.isfinite(z_min) & np.isfinite(z_max)
    if not np.any(finite):
        return

    plot_offsets = offsets[finite]
    plot_min = z_min[finite]
    plot_max = z_max[finite]
    ax.fill_between(
        plot_offsets,
        plot_min,
        plot_max,
        color="0.55",
        alpha=0.18,
        zorder=1,
        linewidth=0,
    )
    envelope_style = {
        "color": "0.35",
        "linewidth": 1.2,
        "alpha": 0.95,
        "zorder": 2,
    }
    ax.plot(plot_offsets, plot_min, **envelope_style)
    ax.plot(plot_offsets, plot_max, **envelope_style)


def _plot_main_cluster_label(
    ax,
    *,
    cluster_count: int,
    offsets: np.ndarray,
    z_min: np.ndarray,
    z_max: np.ndarray,
) -> None:
    """Attach the MC abbreviation to the cluster envelope with a leader line."""
    finite = np.isfinite(offsets) & np.isfinite(z_min) & np.isfinite(z_max)
    if not np.any(finite):
        ax.text(
            MAIN_CLUSTER_LABEL_XY[0],
            MAIN_CLUSTER_LABEL_XY[1],
            _main_cluster_abbrev(cluster_count),
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=PLOT_FONT_SIZE - 2,
            color="0.35",
            zorder=5,
        )
        return

    anchor_xy, text_xy, ha, va = _main_cluster_label_layout(ax, offsets, z_min, z_max)
    ax.annotate(
        _main_cluster_abbrev(cluster_count),
        xy=anchor_xy,
        xytext=text_xy,
        xycoords="data",
        textcoords="axes fraction",
        ha=ha,
        va=va,
        fontsize=PLOT_FONT_SIZE - 2,
        color="0.35",
        arrowprops={
            "arrowstyle": "-",
            "color": "0.35",
            "linewidth": 0.9,
            "shrinkA": 2,
            "shrinkB": 0,
        },
        zorder=5,
    )


def _main_cluster_abbrev(count: int) -> str:
    return rf"MC ($n={count}$)"


def _main_cluster_detail(count: int, max_spread: float) -> str:
    return (
        rf"Main cluster (MC): $n={count}$ submissions; "
        rf"max $\Delta Z$ = {_format_cluster_spread(max_spread)}"
    )


def _select_close_z_cluster(
    case: CaseData,
    names: list[str],
    *,
    max_count: int = 4,
    required_names: list[str] | None = None,
) -> list[str]:
    """Select a small set of submissions that agree closely in Z-spectrum."""
    required_names = [name for name in (required_names or []) if name in names]
    required_set = set(required_names)
    if len(required_names) >= max_count:
        return required_names[:max_count]
    if len(names) <= max_count:
        return names

    display_mask = _display_offset_mask(case.offsets_ppm)
    valid_names = []
    spectra = []
    for name in names:
        z = case.submissions[name].values.astype(float)[display_mask]
        if np.count_nonzero(np.isfinite(z)) > 1:
            valid_names.append(name)
            spectra.append(z)

    required_names = [name for name in required_names if name in valid_names]
    required_set = set(required_names)
    required_indices = tuple(valid_names.index(name) for name in required_names)

    if len(valid_names) <= max_count:
        return valid_names

    stack = np.vstack(spectra)
    n_names = len(valid_names)
    distances = np.full((n_names, n_names), np.inf, dtype=float)
    for i in range(n_names):
        distances[i, i] = 0.0
        for j in range(i + 1, n_names):
            finite = np.isfinite(stack[i]) & np.isfinite(stack[j])
            if np.count_nonzero(finite) == 0:
                continue
            rms = float(np.sqrt(np.nanmean((stack[i, finite] - stack[j, finite]) ** 2)))
            distances[i, j] = rms
            distances[j, i] = rms

    best_combo: tuple[int, ...] | None = None
    best_score: tuple[float, float] | None = None
    for combo in combinations(range(n_names), max_count):
        if required_set and not required_set.issubset({valid_names[i] for i in combo}):
            continue
        pair_distances = [
            distances[i, j]
            for pos, i in enumerate(combo)
            for j in combo[pos + 1 :]
        ]
        if not pair_distances or not np.all(np.isfinite(pair_distances)):
            continue
        score = (float(np.max(pair_distances)), float(np.mean(pair_distances)))
        if best_score is None or score < best_score:
            best_score = score
            best_combo = combo

    if best_combo is None:
        return valid_names[:max_count]

    combo_indices = list(best_combo)
    if required_indices:
        required_order = [idx for idx in required_indices if idx in combo_indices]
        reference_idx = required_order[0]
        others = sorted(
            [idx for idx in combo_indices if idx not in required_order],
            key=lambda idx: distances[reference_idx, idx],
        )
        return [valid_names[idx] for idx in [*required_order, *others]]

    medoid = min(
        combo_indices,
        key=lambda idx: float(np.mean([distances[idx, other] for other in combo_indices])),
    )
    others = sorted(
        [idx for idx in combo_indices if idx != medoid],
        key=lambda idx: distances[medoid, idx],
    )
    return [valid_names[idx] for idx in [medoid, *others]]


def plot_case_panel(
    cases: list[CaseData],
    output_path: Path,
    *,
    exclude_zmt: bool = True,
    reference_label: str = REFERENCE_SUBMISSION_LABEL,
    title: str | None = None,
) -> Path:
    """
  Multi-case figure: columns = cases, rows = Z, MTR_asym, ΔZ, ΔMTR_asym.

  Matches layout of legacy ``Figure_CASE_*.png`` files.
  """
    with _plot_style():
        return _plot_case_panel_impl(
            cases,
            output_path,
            exclude_zmt=exclude_zmt,
            reference_label=reference_label,
            title=title,
        )


def _plot_case_panel_impl(
    cases: list[CaseData],
    output_path: Path,
    *,
    exclude_zmt: bool = True,
    reference_label: str = REFERENCE_SUBMISSION_LABEL,
    title: str | None = None,
) -> Path:
    n_cases = len(cases)
    fig, axes = plt.subplots(
        4,
        n_cases,
        figsize=(5.5 * n_cases, 11),
        squeeze=False,
    )

    row_titles = [
        r"$Z$-spectrum",
        r"MTR$_{\mathrm{asym}}$",
        rf"$\Delta Z$ vs {reference_label}",
        rf"$\Delta$MTR$_{{\mathrm{{asym}}}}$ vs {reference_label}",
    ]

    for col, case in enumerate(cases):
        names = case.participant_names
        keep = filter_submissions(names, exclude_zmt=exclude_zmt)
        names = _labeled_submission_names([names[i] for i in keep])
        if not names:
            raise ValueError(f"No submissions left for case {case.case_number}")

        ref_name = _reference_submission_name(names, reference_label=reference_label)
        ref_offsets, ref_z, ref_asym_ppm, ref_mtrasym = _spectra_for_participant(
            case, ref_name
        )
        cluster_names, cluster_max_spread = identify_main_cluster(
            case,
            names,
            reference_label=reference_label,
        )
        cluster_offsets, cluster_z_min, cluster_z_max = _cluster_z_envelope(
            case,
            cluster_names,
        )
        ref_z_mask = _display_offset_mask(ref_offsets) & np.isfinite(ref_z)
        ref_asym_mask = np.isfinite(ref_asym_ppm) & np.isfinite(ref_mtrasym)
        z_ax = axes[0, col]
        _plot_main_cluster_envelope(
            z_ax,
            cluster_offsets,
            cluster_z_min,
            cluster_z_max,
        )

        for name in names:
            color = _submission_color(name)
            linestyle = _submission_linestyle(name)
            offsets, z, asym_ppm, mtrasym = _spectra_for_participant(case, name)
            finite_z = _display_offset_mask(offsets) & np.isfinite(z)
            axes[0, col].plot(
                offsets[finite_z],
                z[finite_z],
                color=color,
                linestyle=linestyle,
                alpha=0.85,
                linewidth=PLOT_LINE_WIDTH,
                label=display_submission_label(name),
                zorder=3,
            )
            if asym_ppm.size:
                finite_mtr = np.isfinite(asym_ppm) & np.isfinite(mtrasym)
                axes[1, col].plot(
                    asym_ppm[finite_mtr],
                    mtrasym[finite_mtr],
                    color=color,
                    linestyle=linestyle,
                    alpha=0.85,
                    linewidth=PLOT_LINE_WIDTH,
                )

            if np.count_nonzero(ref_z_mask) > 1 and np.count_nonzero(finite_z) > 1:
                dz = z[finite_z] - np.interp(
                    offsets[finite_z],
                    ref_offsets[ref_z_mask],
                    ref_z[ref_z_mask],
                )
                axes[2, col].plot(
                    offsets[finite_z],
                    dz,
                    color=color,
                    linestyle=linestyle,
                    alpha=0.85,
                    linewidth=PLOT_LINE_WIDTH,
                )

            if asym_ppm.size and ref_asym_ppm.size and np.count_nonzero(ref_asym_mask) > 1:
                finite_mtr = np.isfinite(asym_ppm) & np.isfinite(mtrasym)
                ref_interp = np.interp(
                    asym_ppm[finite_mtr],
                    ref_asym_ppm[ref_asym_mask],
                    ref_mtrasym[ref_asym_mask],
                )
                axes[3, col].plot(
                    asym_ppm[finite_mtr],
                    mtrasym[finite_mtr] - ref_interp,
                    color=color,
                    linestyle=linestyle,
                    alpha=0.85,
                    linewidth=PLOT_LINE_WIDTH,
                )

        axes[0, col].set_title(
            f"Case {case.case_number}\n{case.pool_model}",
            fontsize=PLOT_SUBPLOT_TITLE_FONT_SIZE,
        )
        max_asym_ppm = float(np.nanmax(case.offsets_ppm[case.offsets_ppm > 0]))
        axes[0, col].invert_xaxis()
        axes[2, col].invert_xaxis()
        axes[1, col].set_xlim(max_asym_ppm, 0)
        axes[3, col].set_xlim(max_asym_ppm, 0)
        axes[3, col].set_xlabel("Offset (ppm)")
        _plot_main_cluster_label(
            z_ax,
            cluster_count=len(cluster_names),
            offsets=cluster_offsets,
            z_min=cluster_z_min,
            z_max=cluster_z_max,
        )
        z_ax.text(
            0.5,
            -0.20,
            _main_cluster_detail(len(cluster_names), cluster_max_spread),
            transform=z_ax.transAxes,
            ha="center",
            va="top",
            fontsize=PLOT_FONT_SIZE - 2,
            color="0.35",
            clip_on=False,
        )
        for row in range(4):
            axes[row, col].grid(True, alpha=0.25)
            axes[row, 0].set_ylabel(row_titles[row])

    all_handles = []
    all_labels = []
    for col in range(n_cases):
        handles, labels = axes[0, col].get_legend_handles_labels()
        all_handles.extend(handles)
        all_labels.extend(labels)
    handles, labels = _sorted_legend(all_handles, all_labels)
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=min(4, len(labels)),
        fontsize=PLOT_LEGEND_FONT_SIZE,
        bbox_to_anchor=(0.5, 0.02),
    )
    if title:
        fig.suptitle(title, y=1.06, fontsize=PLOT_SUPTITLE_FONT_SIZE)
    fig.tight_layout(rect=[0, 0.15, 1, 0.98])
    fig.subplots_adjust(hspace=0.58)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_zmt_comparison(
    case: CaseData,
    output_path: Path,
    *,
    xyz_names: list[str] | None = None,
    zmt_names: list[str] | None = None,
    max_per_group: int = 4,
    max_zmt: int = 3,
    required_xyz_names: list[str] | None = None,
) -> Path:
    """Case 3 style: overlay selected xyzMT and zMT submissions."""
    from bmsim.filters import is_zmt_only_name

    if xyz_names is None:
        xyz_candidates = _deduplicate_submission_names(
            [
                n
                for n in case.participant_names
                if not is_zmt_only_name(n) and _is_labeled_submission(n)
            ],
            required_names=required_xyz_names,
        )
        xyz_names = _select_close_z_cluster(
            case,
            xyz_candidates,
            max_count=max_per_group,
            required_names=required_xyz_names,
        )
    if zmt_names is None:
        zmt_candidates = _deduplicate_submission_names(
            [
                n
                for n in case.participant_names
                if is_zmt_only_name(n) and _is_labeled_submission(n)
            ]
        )
        zmt_names = _select_close_z_cluster(
            case,
            zmt_candidates,
            max_count=max_zmt,
        )

    xyz_names = _sort_submission_names(xyz_names)
    zmt_names = _sort_submission_names(zmt_names)
    selected_names = _sort_submission_names(xyz_names + zmt_names)
    if not selected_names:
        raise ValueError("No submissions selected for zMT comparison")

    ref_name = selected_names[0]
    ref_label = display_submission_label(ref_name)
    ref_offsets, ref_z, ref_asym_ppm, ref_mtrasym = _spectra_for_participant(
        case, ref_name
    )
    ref_z_mask = _display_offset_mask(ref_offsets) & np.isfinite(ref_z)
    ref_asym_mask = np.isfinite(ref_asym_ppm) & np.isfinite(ref_mtrasym)

    with _plot_style():
        fig, axes = plt.subplots(2, 2, figsize=(13, 8))

        for name in xyz_names:
            offsets, z, asym_ppm, mtrasym = _spectra_for_participant(case, name)
            finite_z = _display_offset_mask(offsets) & np.isfinite(z)
            label = f"{display_submission_label(name)} xyzMT"
            color = _submission_color(name)
            linestyle = _submission_linestyle(name)
            axes[0, 0].plot(
                offsets[finite_z],
                z[finite_z],
                label=label,
                color=color,
                linestyle=linestyle,
                linewidth=PLOT_LINE_WIDTH_STRONG,
            )
            if np.count_nonzero(ref_z_mask) > 1 and np.count_nonzero(finite_z) > 1:
                ref_interp = np.interp(
                    offsets[finite_z],
                    ref_offsets[ref_z_mask],
                    ref_z[ref_z_mask],
                )
                axes[1, 0].plot(
                    offsets[finite_z],
                    ref_interp - z[finite_z],
                    color=color,
                    linestyle=linestyle,
                    linewidth=PLOT_LINE_WIDTH_STRONG,
                )
            if asym_ppm.size:
                finite_mtr = np.isfinite(asym_ppm) & np.isfinite(mtrasym)
                axes[0, 1].plot(
                    asym_ppm[finite_mtr],
                    mtrasym[finite_mtr],
                    color=color,
                    linestyle=linestyle,
                    linewidth=PLOT_LINE_WIDTH_STRONG,
                )
                if np.count_nonzero(ref_asym_mask) > 1 and np.count_nonzero(finite_mtr) > 1:
                    ref_mtr_interp = np.interp(
                        asym_ppm[finite_mtr],
                        ref_asym_ppm[ref_asym_mask],
                        ref_mtrasym[ref_asym_mask],
                    )
                    axes[1, 1].plot(
                        asym_ppm[finite_mtr],
                        ref_mtr_interp - mtrasym[finite_mtr],
                        color=color,
                        linestyle=linestyle,
                        linewidth=PLOT_LINE_WIDTH_STRONG,
                    )

        for name in zmt_names:
            offsets, z, asym_ppm, mtrasym = _spectra_for_participant(case, name)
            finite_z = _display_offset_mask(offsets) & np.isfinite(z)
            label = f"{display_submission_label(name)} zMT"
            color = _submission_color(name)
            linestyle = _submission_linestyle(name)
            axes[0, 0].plot(
                offsets[finite_z],
                z[finite_z],
                label=label,
                color=color,
                linestyle=linestyle,
                linewidth=PLOT_LINE_WIDTH_STRONG,
            )
            if np.count_nonzero(ref_z_mask) > 1 and np.count_nonzero(finite_z) > 1:
                ref_interp = np.interp(
                    offsets[finite_z],
                    ref_offsets[ref_z_mask],
                    ref_z[ref_z_mask],
                )
                axes[1, 0].plot(
                    offsets[finite_z],
                    ref_interp - z[finite_z],
                    color=color,
                    linestyle=linestyle,
                    linewidth=PLOT_LINE_WIDTH_STRONG,
                )
            if asym_ppm.size:
                finite_mtr = np.isfinite(asym_ppm) & np.isfinite(mtrasym)
                axes[0, 1].plot(
                    asym_ppm[finite_mtr],
                    mtrasym[finite_mtr],
                    color=color,
                    linestyle=linestyle,
                    linewidth=PLOT_LINE_WIDTH_STRONG,
                )
                if np.count_nonzero(ref_asym_mask) > 1 and np.count_nonzero(finite_mtr) > 1:
                    ref_mtr_interp = np.interp(
                        asym_ppm[finite_mtr],
                        ref_asym_ppm[ref_asym_mask],
                        ref_mtrasym[ref_asym_mask],
                    )
                    axes[1, 1].plot(
                        asym_ppm[finite_mtr],
                        ref_mtr_interp - mtrasym[finite_mtr],
                        color=color,
                        linestyle=linestyle,
                        linewidth=PLOT_LINE_WIDTH_STRONG,
                    )

        axes[0, 0].set_ylabel(r"$Z$")
        axes[0, 1].set_ylabel(r"MTR$_{\mathrm{asym}}$")
        axes[1, 0].set_ylabel(r"$Z_{ref}$ - $Z$")
        axes[1, 1].set_ylabel(r"MTR$_{\mathrm{asym,ref}}$ - MTR$_{\mathrm{asym}}$")
        axes[1, 0].set_xlabel("Offset (ppm)")
        axes[1, 1].set_xlabel("Offset (ppm)")
        axes[0, 0].set_title(f"Case {case.case_number}: xyzMT vs z-only MT")
        axes[0, 1].set_title("MTR asymmetry")
        axes[1, 0].set_title(f"Difference to {ref_label}")
        axes[1, 1].set_title(f"Difference to {ref_label}")

        axes[0, 0].invert_xaxis()
        axes[1, 0].invert_xaxis()
        if ref_asym_ppm.size:
            max_asym = float(np.nanmax(ref_asym_ppm))
            axes[0, 1].set_xlim(max_asym, 0)
            axes[1, 1].set_xlim(max_asym, 0)

        handles, labels = _sorted_zmt_comparison_legend(
            *axes[0, 0].get_legend_handles_labels()
        )
        fig.legend(
            handles,
            labels,
            loc="lower center",
            ncol=2,
            fontsize=PLOT_LEGEND_FONT_SIZE,
            bbox_to_anchor=(0.5, 0.02),
        )
        for ax in axes.flatten():
            ax.grid(True, alpha=0.25)
        fig.tight_layout(rect=[0, 0.14, 1, 1])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
    return output_path


def plot_reference_overview(
    cases: dict[int, CaseData],
    output_path: Path,
    *,
    ref_name: str | None = None,
    asym_cutoff: float = 15.0,
) -> Path:
    """Overview figure in the style of the original Colab/Markus script.

    The layout is one row per case and two columns: Z-spectrum and MTR_asym.
    It uses the first submission in each case unless ``ref_name`` is present.
    """
    case_list = [cases[n] for n in sorted(cases)]
    with _plot_style(font_size=PLOT_FONT_SIZE_LARGE):
        fig, axes = plt.subplots(
            nrows=len(case_list),
            ncols=2,
            figsize=(9, 20),
            dpi=300,
            squeeze=False,
        )

        for row, case in enumerate(case_list):
            name = ref_name or case.participant_names[0]
            if name not in case.submissions.columns:
                name = case.participant_names[0]
            offsets, z, asym_ppm, mtrasym = _spectra_for_participant(
                case, name, normalize=False
            )

            finite_z = _display_offset_mask(offsets) & np.isfinite(z)
            axes[row, 0].plot(
                offsets[finite_z], z[finite_z], linewidth=PLOT_LINE_WIDTH_STRONG
            )
            axes[row, 0].set_title(f"Case {case.case_number}")
            axes[row, 0].invert_xaxis()
            axes[row, 0].set_ylabel(r"Z($\Delta\omega$)")

            asym_mask = (
                np.isfinite(asym_ppm)
                & np.isfinite(mtrasym)
                & (asym_ppm > 0)
                & (asym_ppm <= asym_cutoff)
            )
            axes[row, 1].plot(
                asym_ppm[asym_mask],
                mtrasym[asym_mask],
                linewidth=PLOT_LINE_WIDTH_STRONG,
            )
            axes[row, 1].set_title(f"Case {case.case_number}")
            axes[row, 1].invert_xaxis()
            axes[row, 1].set_ylabel(r"MTR$_{asym}$ ($\Delta\omega$)")

            if row == len(case_list) - 1:
                axes[row, 0].set_xlabel(r"$\Delta\omega$ [ppm]")
                axes[row, 1].set_xlabel(r"$\Delta\omega$ [ppm]")

        fig.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        if output_path.suffix.lower() != ".pdf":
            fig.savefig(output_path.with_suffix(".pdf"), dpi=300, bbox_inches="tight")
        plt.close(fig)
    return output_path


def plot_difference_overview(
    cases: dict[int, CaseData],
    output_path: Path,
    *,
    exclude_zmt: bool = True,
    reference_label: str = REFERENCE_SUBMISSION_LABEL,
    asym_cutoff: float = 15.0,
) -> Path:
    """Overview-style plot with spectra and differences to a reference.

    Columns are Z, MTR_asym, Z_ref - Z, and MTR_asym,ref - MTR_asym.
    """
    case_list = [cases[n] for n in sorted(cases)]
    with _plot_style(font_size=PLOT_FONT_SIZE_OVERVIEW):
        fig, axes = plt.subplots(
            nrows=len(case_list),
            ncols=4,
            figsize=(18, 20),
            dpi=300,
            squeeze=False,
        )

        for row, case in enumerate(case_list):
            names_all = case.participant_names
            keep = filter_submissions(names_all, exclude_zmt=exclude_zmt)
            names = _labeled_submission_names([names_all[i] for i in keep])
            if not names:
                continue

            ref_name = _reference_submission_name(names, reference_label=reference_label)
            ref_offsets, ref_z, ref_asym_ppm, ref_mtrasym = _spectra_for_participant(
                case, ref_name, normalize=False
            )
            ref_z_mask = _display_offset_mask(ref_offsets) & np.isfinite(ref_z)
            ref_asym_mask = (
                np.isfinite(ref_asym_ppm)
                & np.isfinite(ref_mtrasym)
                & (ref_asym_ppm > 0)
                & (ref_asym_ppm <= asym_cutoff)
            )

            for name in names:
                color = _submission_color(name)
                linestyle = _submission_linestyle(name)
                offsets, z, asym_ppm, mtrasym = _spectra_for_participant(
                    case, name, normalize=False
                )

                finite_z = _display_offset_mask(offsets) & np.isfinite(z)
                axes[row, 0].plot(
                    offsets[finite_z],
                    z[finite_z],
                    color=color,
                    linestyle=linestyle,
                    linewidth=PLOT_LINE_WIDTH,
                    alpha=0.8,
                )

                asym_mask = (
                    np.isfinite(asym_ppm)
                    & np.isfinite(mtrasym)
                    & (asym_ppm > 0)
                    & (asym_ppm <= asym_cutoff)
                )
                axes[row, 1].plot(
                    asym_ppm[asym_mask],
                    mtrasym[asym_mask],
                    color=color,
                    linestyle=linestyle,
                    linewidth=PLOT_LINE_WIDTH,
                    alpha=0.8,
                )

                if np.count_nonzero(ref_z_mask) > 1 and np.count_nonzero(finite_z) > 1:
                    ref_interp = np.interp(
                        offsets[finite_z],
                        ref_offsets[ref_z_mask],
                        ref_z[ref_z_mask],
                    )
                    axes[row, 2].plot(
                        offsets[finite_z],
                        ref_interp - z[finite_z],
                        color=color,
                        linestyle=linestyle,
                        linewidth=PLOT_LINE_WIDTH,
                        alpha=0.8,
                    )

                if (
                    np.count_nonzero(ref_asym_mask) > 1
                    and np.count_nonzero(asym_mask) > 1
                ):
                    ref_mtr_interp = np.interp(
                        asym_ppm[asym_mask],
                        ref_asym_ppm[ref_asym_mask],
                        ref_mtrasym[ref_asym_mask],
                    )
                    axes[row, 3].plot(
                        asym_ppm[asym_mask],
                        ref_mtr_interp - mtrasym[asym_mask],
                        color=color,
                        linestyle=linestyle,
                        linewidth=PLOT_LINE_WIDTH,
                        alpha=0.8,
                    )

            for col in (0, 2):
                axes[row, col].invert_xaxis()
            for col in (1, 3):
                axes[row, col].invert_xaxis()

            axes[row, 0].set_ylabel(r"Z($\Delta\omega$)")
            axes[row, 1].set_ylabel(r"MTR$_{asym}$")
            axes[row, 2].set_ylabel(rf"Z$_{{{reference_label}}}$ - Z")
            axes[row, 3].set_ylabel(rf"MTR$_{{asym,{reference_label}}}$ - MTR$_{{asym}}$")

            axes[row, 0].set_title(f"Case {case.case_number}")
            axes[row, 1].set_title(f"Case {case.case_number}")
            axes[row, 2].set_title(f"Case {case.case_number}")
            axes[row, 3].set_title(f"Case {case.case_number}")

            if row == len(case_list) - 1:
                for col in range(4):
                    axes[row, col].set_xlabel(r"$\Delta\omega$ [ppm]")

            for col in range(4):
                axes[row, col].grid(True, alpha=0.2)

        fig.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        if output_path.suffix.lower() != ".pdf":
            fig.savefig(output_path.with_suffix(".pdf"), dpi=300, bbox_inches="tight")
        plt.close(fig)
    return output_path


def plot_max_spread_summary(
    cases: dict[int, CaseData],
    output_path: Path,
    *,
    exclude_zmt: bool = True,
) -> Path:
    """Bar chart: max |ΔZ| between any pair of submissions per case."""
    case_nums = []
    max_spread = []

    for num in sorted(cases):
        case = cases[num]
        keep = filter_submissions(case.participant_names, exclude_zmt=exclude_zmt)
        names = _labeled_submission_names([case.participant_names[i] for i in keep])
        if len(names) < 2:
            continue

        z_values = []
        for name in names:
            offsets, z, _, _ = _spectra_for_participant(case, name)
            z_values.append(z)

        display_mask = _display_offset_mask(case.offsets_ppm)
        stack = np.vstack([z[display_mask] for z in z_values])
        spread = np.nanmax(stack, axis=0) - np.nanmin(stack, axis=0)
        case_nums.append(num)
        max_spread.append(float(np.nanmax(spread)))

    with _plot_style():
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar([f"Case {n}" for n in case_nums], max_spread, color="steelblue")
        ax.set_ylabel(r"max$_\omega$ ($Z_{\max}-Z_{\min}$)")
        ax.set_title("Peak spread between submissions (Z)")
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
    return output_path


def _submission_abs_diff_to_reference(
    case: CaseData,
    names: list[str],
    *,
    reference_label: str = REFERENCE_SUBMISSION_LABEL,
    asym_cutoff: float = 15.0,
) -> dict[str, tuple[float, float]]:
    """Per-submission mean absolute difference to the reference."""
    ref_name = _reference_submission_name(names, reference_label=reference_label)
    ref_offsets, ref_z, ref_asym_ppm, ref_mtrasym = _spectra_for_participant(
        case, ref_name
    )
    ref_z_mask = _display_offset_mask(ref_offsets) & np.isfinite(ref_z)
    ref_asym_mask = (
        np.isfinite(ref_asym_ppm)
        & np.isfinite(ref_mtrasym)
        & (ref_asym_ppm > 0)
        & (ref_asym_ppm <= asym_cutoff)
    )

    results: dict[str, tuple[float, float]] = {}
    for name in names:
        label = display_submission_label(name)
        if name == ref_name:
            results[label] = (0.0, 0.0)
            continue

        offsets, z, asym_ppm, mtrasym = _spectra_for_participant(case, name)
        finite_z = _display_offset_mask(offsets) & np.isfinite(z)
        z_mad = float("nan")
        if np.count_nonzero(ref_z_mask) > 1 and np.count_nonzero(finite_z) > 1:
            ref_interp = np.interp(
                offsets[finite_z],
                ref_offsets[ref_z_mask],
                ref_z[ref_z_mask],
            )
            z_mad = float(np.nanmean(np.abs(ref_interp - z[finite_z])))

        asym_mask = (
            np.isfinite(asym_ppm)
            & np.isfinite(mtrasym)
            & (asym_ppm > 0)
            & (asym_ppm <= asym_cutoff)
        )
        mtr_mad = float("nan")
        if np.count_nonzero(ref_asym_mask) > 1 and np.count_nonzero(asym_mask) > 1:
            ref_mtr_interp = np.interp(
                asym_ppm[asym_mask],
                ref_asym_ppm[ref_asym_mask],
                ref_mtrasym[ref_asym_mask],
            )
            mtr_mad = float(
                np.nanmean(np.abs(ref_mtr_interp - mtrasym[asym_mask]))
            )
        results[label] = (z_mad, mtr_mad)
    return results


def plot_mean_abs_diff_summary(
    cases: dict[int, CaseData],
    output_path: Path,
    *,
    exclude_zmt: bool = True,
    reference_label: str = REFERENCE_SUBMISSION_LABEL,
    asym_cutoff: float = 15.0,
) -> Path:
    """Scatter plot: one point per submission showing mean |difference| to the reference."""
    case_nums = sorted(cases)
    legend_handles: dict[str, object] = {}

    with _plot_style():
        fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharex=True)
        ylabels = (
            rf"mean |$Z_{{\mathrm{{ref}}}} - Z$|",
            rf"mean |MTR$_{{\mathrm{{asym,ref}}}}$ - MTR$_{{\mathrm{{asym}}}}$|",
        )

        for num in case_nums:
            case = cases[num]
            keep = filter_submissions(case.participant_names, exclude_zmt=exclude_zmt)
            names = _labeled_submission_names([case.participant_names[i] for i in keep])
            if len(names) < 2:
                continue

            per_submission = _submission_abs_diff_to_reference(
                case,
                names,
                reference_label=reference_label,
                asym_cutoff=asym_cutoff,
            )
            ordered = sorted(
                per_submission.items(), key=lambda item: _submission_sort_key(item[0])
            )
            for label, (z_mad, mtr_mad) in ordered:
                x = num
                color = _submission_color(label)
                for ax, value in zip(axes, (z_mad, mtr_mad)):
                    point = ax.scatter(
                        x,
                        value,
                        color=color,
                        s=50,
                        edgecolors="0.2",
                        linewidths=0.5,
                        zorder=3,
                    )
                    if label not in legend_handles:
                        legend_handles[label] = point

        for ax, ylabel in zip(axes, ylabels):
            ax.set_ylabel(ylabel)
            ax.set_xticks(case_nums)
            ax.set_xticklabels([f"Case {n}" for n in case_nums])
            ax.set_xlim(0.4, len(case_nums) + 0.6)
            ax.grid(True, axis="y", alpha=0.3)

        axes[0].set_title(rf"Differences to {reference_label} by submission")
        axes[1].set_xlabel("Case")
        legend_labels, legend_items = zip(
            *sorted(legend_handles.items(), key=lambda item: _submission_sort_key(item[0]))
        )
        fig.legend(
            legend_items,
            legend_labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.02),
            ncol=5,
            fontsize=PLOT_LEGEND_FONT_SIZE,
            frameon=False,
        )
        fig.tight_layout(rect=[0, 0.14, 1, 1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        if output_path.suffix.lower() != ".pdf":
            fig.savefig(output_path.with_suffix(".pdf"), dpi=300, bbox_inches="tight")
        plt.close(fig)
    return output_path


def _format_timestep_label(dt_s: float) -> str:
    """Return a legend-friendly timestep label in microseconds."""
    dt_us = dt_s * 1e6
    if np.isclose(dt_us, round(dt_us), rtol=0, atol=1e-6):
        return rf"$\Delta t = {int(round(dt_us))}\,\mu\mathrm{{s}}$"
    return rf"$\Delta t = {dt_us:g}\,\mu\mathrm{{s}}$"


def _padded_ylim(
    values: list[float] | np.ndarray,
    *,
    pad_fraction: float = 0.08,
) -> tuple[float, float] | None:
    """Return padded y-limits for a collection of plotted values."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    vmin, vmax = float(np.min(arr)), float(np.max(arr))
    span = vmax - vmin
    if span <= 0:
        margin = max(abs(vmin), 1e-6) * pad_fraction
        return vmin - margin, vmax + margin
    margin = span * pad_fraction
    return vmin - margin, vmax + margin


def load_timestep_mat(mat_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load S03 timestep comparison data from a MATLAB file."""
    import scipy.io as sio

    data = sio.loadmat(mat_path)
    offsets = np.asarray(data["vOffsets"], dtype=float).ravel()
    timesteps = np.asarray(data["DT"], dtype=float).ravel()
    spectra = np.asarray(data["mSpec"], dtype=float)
    if spectra.shape[0] != timesteps.size:
        spectra = spectra.T
    return offsets, timesteps, spectra


def plot_case_timestep_comparison(
    output_path: Path,
    mat_path: Path,
    *,
    case_number: int = 7,
    pool_model: str = "WM 5 pool",
    reference_index: int = -1,
) -> Path:
    """Plot Z/MTR_asym spectra for multiple S03 timesteps in case-panel style."""
    offsets, timesteps, spectra = load_timestep_mat(mat_path)
    labels = [_format_timestep_label(dt) for dt in timesteps]
    ref_label = labels[reference_index]

    row_titles = [
        r"$Z$-spectrum",
        r"MTR$_{\mathrm{asym}}$",
        rf"$\Delta Z$ vs {ref_label}",
        rf"$\Delta$MTR$_{{\mathrm{{asym}}}}$ vs {ref_label}",
    ]

    ref_z = spectra[reference_index]
    ref_asym_ppm, ref_mtrasym = compute_mtrasym(offsets, ref_z)
    ref_z_mask = _display_offset_mask(offsets) & np.isfinite(ref_z)
    ref_asym_mask = np.isfinite(ref_asym_ppm) & np.isfinite(ref_mtrasym)
    coarse_dt = 5e-4
    mtr_ylim_values: list[float] = []
    dz_ylim_values: list[float] = []
    dmtr_ylim_values: list[float] = []

    with _plot_style():
        fig, axes = plt.subplots(4, 1, figsize=(5.5, 11), squeeze=False)

        for index, (dt, z, label) in enumerate(zip(timesteps, spectra, labels)):
            color = plt.get_cmap("tab10")(index % 10)
            linestyle = _line_style(index)
            asym_ppm, mtrasym = compute_mtrasym(offsets, z)
            finite_z = _display_offset_mask(offsets) & np.isfinite(z)
            use_for_ylim = not np.isclose(dt, coarse_dt, rtol=0, atol=0)

            axes[0, 0].plot(
                offsets[finite_z],
                z[finite_z],
                color=color,
                linestyle=linestyle,
                alpha=0.85,
                linewidth=PLOT_LINE_WIDTH,
                label=label,
            )

            if asym_ppm.size:
                finite_mtr = np.isfinite(asym_ppm) & np.isfinite(mtrasym)
                axes[1, 0].plot(
                    asym_ppm[finite_mtr],
                    mtrasym[finite_mtr],
                    color=color,
                    linestyle=linestyle,
                    alpha=0.85,
                    linewidth=PLOT_LINE_WIDTH,
                )
                if use_for_ylim:
                    mtr_ylim_values.extend(mtrasym[finite_mtr].tolist())

            if np.count_nonzero(ref_z_mask) > 1 and np.count_nonzero(finite_z) > 1:
                dz = z[finite_z] - np.interp(
                    offsets[finite_z],
                    offsets[ref_z_mask],
                    ref_z[ref_z_mask],
                )
                axes[2, 0].plot(
                    offsets[finite_z],
                    dz,
                    color=color,
                    linestyle=linestyle,
                    alpha=0.85,
                    linewidth=PLOT_LINE_WIDTH,
                )
                if use_for_ylim:
                    dz_ylim_values.extend(dz.tolist())

            if asym_ppm.size and ref_asym_ppm.size and np.count_nonzero(ref_asym_mask) > 1:
                finite_mtr = np.isfinite(asym_ppm) & np.isfinite(mtrasym)
                ref_interp = np.interp(
                    asym_ppm[finite_mtr],
                    ref_asym_ppm[ref_asym_mask],
                    ref_mtrasym[ref_asym_mask],
                )
                dmtr = mtrasym[finite_mtr] - ref_interp
                axes[3, 0].plot(
                    asym_ppm[finite_mtr],
                    dmtr,
                    color=color,
                    linestyle=linestyle,
                    alpha=0.85,
                    linewidth=PLOT_LINE_WIDTH,
                )
                if use_for_ylim:
                    dmtr_ylim_values.extend(dmtr.tolist())

        for ax, values in (
            (axes[1, 0], mtr_ylim_values),
            (axes[2, 0], dz_ylim_values),
            (axes[3, 0], dmtr_ylim_values),
        ):
            limits = _padded_ylim(values)
            if limits is not None:
                ax.set_ylim(*limits)

        axes[0, 0].set_title(
            f"Case {case_number} / {pool_model}\nS03 timestep comparison",
            fontsize=PLOT_SUBPLOT_TITLE_FONT_SIZE,
        )
        max_asym_ppm = float(np.nanmax(offsets[offsets > 0]))
        axes[0, 0].invert_xaxis()
        axes[2, 0].invert_xaxis()
        axes[1, 0].set_xlim(max_asym_ppm, 0)
        axes[3, 0].set_xlim(max_asym_ppm, 0)
        axes[3, 0].set_xlabel("Offset (ppm)")
        for row in range(4):
            axes[row, 0].grid(True, alpha=0.25)
            axes[row, 0].set_ylabel(row_titles[row])

        handles, legend_labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(
            handles,
            legend_labels,
            loc="lower center",
            ncol=2,
            fontsize=PLOT_LEGEND_FONT_SIZE,
            bbox_to_anchor=(0.5, 0.02),
        )
        fig.tight_layout(rect=[0, 0.15, 1, 0.98])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        if output_path.suffix.lower() != ".pdf":
            fig.savefig(output_path.with_suffix(".pdf"), dpi=300, bbox_inches="tight")
        plt.close(fig)
    return output_path


def _resolve_submission_columns(case: CaseData, labels: list[str]) -> list[str]:
    """Map display labels such as S14b to parsed spreadsheet column names."""
    resolved: list[str] = []
    for label in labels:
        matches = [
            column
            for column in case.submissions.columns
            if display_submission_label(column) == label or column == label
        ]
        if not matches:
            raise ValueError(
                f"Submission {label} not found in case {case.case_number}"
            )
        resolved.append(matches[0])
    return resolved


def plot_submission_subset_panel(
    cases: list[CaseData],
    submission_labels: list[str],
    output_path: Path,
    *,
    reference_label: str = REFERENCE_SUBMISSION_LABEL,
    legend_display_labels: list[str] | None = None,
) -> Path:
    """Case-panel layout for a fixed set of submissions (Z, MTR, differences)."""
    n_cases = len(cases)
    plot_legend_labels = legend_display_labels or submission_labels
    row_titles = [
        r"$Z$-spectrum",
        r"MTR$_{\mathrm{asym}}$",
        rf"$\Delta Z$ vs {reference_label}",
        rf"$\Delta$MTR$_{{\mathrm{{asym}}}}$ vs {reference_label}",
    ]

    with _plot_style():
        fig, axes = plt.subplots(
            4,
            n_cases,
            figsize=(5.5 * n_cases, 11),
            squeeze=False,
        )

        for col, case in enumerate(cases):
            names = _resolve_submission_columns(case, submission_labels)
            ref_name = _reference_submission_name(names, reference_label=reference_label)
            ref_offsets, ref_z, ref_asym_ppm, ref_mtrasym = _spectra_for_participant(
                case, ref_name
            )
            ref_z_mask = _display_offset_mask(ref_offsets) & np.isfinite(ref_z)
            ref_asym_mask = np.isfinite(ref_asym_ppm) & np.isfinite(ref_mtrasym)

            for name in names:
                color = _submission_color(name)
                linestyle = _submission_linestyle(name)
                offsets, z, asym_ppm, mtrasym = _spectra_for_participant(case, name)
                finite_z = _display_offset_mask(offsets) & np.isfinite(z)
                display = display_submission_label(name)
                legend_label = plot_legend_labels[submission_labels.index(display)]
                axes[0, col].plot(
                    offsets[finite_z],
                    z[finite_z],
                    color=color,
                    linestyle=linestyle,
                    alpha=0.85,
                    linewidth=PLOT_LINE_WIDTH,
                    label=legend_label,
                )
                if asym_ppm.size:
                    finite_mtr = np.isfinite(asym_ppm) & np.isfinite(mtrasym)
                    axes[1, col].plot(
                        asym_ppm[finite_mtr],
                        mtrasym[finite_mtr],
                        color=color,
                        linestyle=linestyle,
                        alpha=0.85,
                        linewidth=PLOT_LINE_WIDTH,
                    )

                if np.count_nonzero(ref_z_mask) > 1 and np.count_nonzero(finite_z) > 1:
                    dz = z[finite_z] - np.interp(
                        offsets[finite_z],
                        ref_offsets[ref_z_mask],
                        ref_z[ref_z_mask],
                    )
                    axes[2, col].plot(
                        offsets[finite_z],
                        dz,
                        color=color,
                        linestyle=linestyle,
                        alpha=0.85,
                        linewidth=PLOT_LINE_WIDTH,
                    )

                if (
                    asym_ppm.size
                    and ref_asym_ppm.size
                    and np.count_nonzero(ref_asym_mask) > 1
                ):
                    finite_mtr = np.isfinite(asym_ppm) & np.isfinite(mtrasym)
                    ref_interp = np.interp(
                        asym_ppm[finite_mtr],
                        ref_asym_ppm[ref_asym_mask],
                        ref_mtrasym[ref_asym_mask],
                    )
                    axes[3, col].plot(
                        asym_ppm[finite_mtr],
                        mtrasym[finite_mtr] - ref_interp,
                        color=color,
                        linestyle=linestyle,
                        alpha=0.85,
                        linewidth=PLOT_LINE_WIDTH,
                    )

            axes[0, col].set_title(
                f"Case {case.case_number}\n{case.pool_model}",
                fontsize=PLOT_SUBPLOT_TITLE_FONT_SIZE,
            )
            max_asym_ppm = float(np.nanmax(case.offsets_ppm[case.offsets_ppm > 0]))
            axes[0, col].invert_xaxis()
            axes[2, col].invert_xaxis()
            axes[1, col].set_xlim(max_asym_ppm, 0)
            axes[3, col].set_xlim(max_asym_ppm, 0)
            axes[3, col].set_xlabel("Offset (ppm)")
            for row in range(4):
                axes[row, col].grid(True, alpha=0.25)
                axes[row, 0].set_ylabel(row_titles[row])

        handles, labels = axes[0, 0].get_legend_handles_labels()
        if legend_display_labels:
            label_order = {label: handle for label, handle in zip(labels, handles)}
            handles = [label_order[label] for label in plot_legend_labels if label in label_order]
            labels = [label for label in plot_legend_labels if label in label_order]
        else:
            handles, labels = _sorted_legend(handles, labels)
        fig.legend(
            handles,
            labels,
            loc="lower center",
            ncol=len(labels),
            fontsize=PLOT_LEGEND_FONT_SIZE,
            bbox_to_anchor=(0.5, 0.02),
        )
        fig.tight_layout(rect=[0, 0.12, 1, 0.98])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        if output_path.suffix.lower() != ".pdf":
            fig.savefig(output_path.with_suffix(".pdf"), dpi=300, bbox_inches="tight")
        plt.close(fig)
    return output_path


def plot_bart_precision_comparison(
    cases: dict[int, CaseData],
    output_path: Path,
    *,
    case_numbers: list[int] | None = None,
    reference_label: str = REFERENCE_SUBMISSION_LABEL,
) -> Path:
    """Compare single- and double-precision BART against the reference."""
    case_numbers = case_numbers or [5, 6]
    case_list = [cases[num] for num in case_numbers]
    return plot_submission_subset_panel(
        case_list,
        [reference_label, "S14", "S14b"],
        output_path,
        reference_label=reference_label,
        legend_display_labels=[
            reference_label,
            r"S14 (single precision)",
            r"S14b (double precision)",
        ],
    )


def generate_bart_precision_figures(
    cases: dict[int, CaseData],
    figures_dir: Path | None = None,
    *,
    reference_label: str = REFERENCE_SUBMISSION_LABEL,
) -> list[Path]:
    """Write BART single- vs double-precision panels for all case pairs."""
    out = figures_dir or FIGURES_DIR
    pairs = [
        ([1, 2], "Figure_BART_precision_12.png"),
        ([3, 4], "Figure_BART_precision_34.png"),
        ([5, 6], "Figure_BART_precision_56.png"),
        ([7, 8], "Figure_BART_precision_78.png"),
    ]
    paths: list[Path] = []
    for case_numbers, filename in pairs:
        paths.append(
            plot_bart_precision_comparison(
                cases,
                out / filename,
                case_numbers=case_numbers,
                reference_label=reference_label,
            )
        )
    return paths


def generate_paper_figures(
    cases: dict[int, CaseData],
    figures_dir: Path | None = None,
    *,
    exclude_zmt: bool = True,
) -> list[Path]:
    """Write all standard figures used by ``bmsim.tex``."""
    out = figures_dir or FIGURES_DIR
    paths = []

    pairs = [(1, 2), (3, 4), (5, 6), (7, 8)]
    filenames = [
        "Figure_CASE_12.png",
        "Figure_CASE_34.png",
        "Figure_CASE_56.png",
        "Figure_CASE_78.png",
    ]
    for (a, b), fname in zip(pairs, filenames):
        p = plot_case_panel(
            [cases[a], cases[b]],
            out / fname,
            exclude_zmt=exclude_zmt,
        )
        paths.append(p)

    if 3 in cases:
        paths.append(
            plot_zmt_comparison(
                cases[3],
                out / "Case_3_zMT_comparison.png",
                required_xyz_names=["S01"],
            )
        )

    if cases:
        paths.append(
            plot_reference_overview(
                cases,
                out / "All_Cases_Z_and_MTRasym_ref.png",
            )
        )
        paths.append(
            plot_difference_overview(
                cases,
                out / "All_Cases_Z_and_MTRasym_diff.png",
                exclude_zmt=exclude_zmt,
            )
        )
        paths.append(
            plot_max_spread_summary(
                cases,
                out / "Figure_max_Z_spread.png",
                exclude_zmt=exclude_zmt,
            )
        )
        paths.append(
            plot_mean_abs_diff_summary(
                cases,
                out / "Figure_mean_abs_diff.png",
                exclude_zmt=exclude_zmt,
            )
        )
        paths.extend(
            generate_bart_precision_figures(
                cases,
                out,
            )
        )

    mat_path = SCRIPTS_ROOT / "Case7_timestep.mat"
    if mat_path.exists():
        paths.append(
            plot_case_timestep_comparison(
                out / "Case_7_timestep.png",
                mat_path,
                case_number=7,
                pool_model="WM 5 pool",
            )
        )

    return paths
