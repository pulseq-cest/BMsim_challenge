#!/usr/bin/env python3
"""Before/after Z-spectra and all-case spread history.

Top block: Case 3 (Z + MTR_asym) and Case 5 (Z); largest observed deviation
(top row, red traces; Case 3 includes z-only MT, dotted) versus current
(bottom row, green traces; z-only MT omitted). Case 3's two panels together
match Case 5's width. Bottom: for every case, largest observed maximum and
median Z spread versus the final values.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import plot_progress_gifs as progress
from bmsim.filters import filter_submissions, is_zmt_only_name
from bmsim.mtrasym import compute_mtrasym
from bmsim.plotting import (
    PLOT_FONT_SIZE,
    PLOT_LEGEND_FONT_SIZE,
    PLOT_LINE_WIDTH,
    _cluster_z_envelope,
    _display_offset_mask,
    _labeled_submission_names,
    _plot_main_cluster_envelope,
    _plot_style,
    _submission_color,
    _submission_linestyle,
    identify_main_cluster,
)
from bmsim.submissions import display_submission_label
from config import FIGURES_DIR, REPO_ROOT

# Case 3 MTR_asym display window (ppm); left=3, right=0.
ASYM_XLIM_PPM = (3.0, 0.0)

# Day of largest max-Z spread for Cases 3 and 5 (labeled, zMT-excluded scan).
WORST_DATES = {3: "2023-01-23", 5: "2026-04-27"}
SUMMARY_CSV = REPO_ROOT / "data" / "spread_history_summary.csv"

# Trace tint (RGB); spectra are blended toward these instead of background fill.
TINT_WORST = np.array([0.72, 0.18, 0.14])
TINT_FINAL = np.array([0.10, 0.48, 0.28])
LINE_WORST = "#b03a2e"
LINE_FINAL = "#1e7a46"

CASE_LABELS = [
    "1\nCW 15 s",
    "2\nCW 2 s",
    "3\nCW 5-pool",
    "4\nWASABI",
    "5\nGauss.",
    "6\nTrain 2p",
    "7\nTrain 5p",
    "8\nWASABI tr.",
]


def included_names(case, *, exclude_zmt: bool = True) -> list[str]:
    keep = filter_submissions(case.participant_names, exclude_zmt=exclude_zmt)
    names = _labeled_submission_names([case.participant_names[i] for i in keep])
    return [
        name
        for name in names
        if progress._spectrum_is_bipolar(
            case.offsets_ppm, case.submissions[name].values.astype(float)
        )
    ]


def reference_label(names: list[str]) -> str | None:
    labels = {display_submission_label(name) for name in names}
    for candidate in ("S02", "S02a"):
        if candidate in labels:
            return candidate
    return None


def snapshot_case(date: str, case_number: int):
    snaps = {day: path for day, _rev, path in progress.iter_cached_snapshots()}
    if date not in snaps:
        raise FileNotFoundError(f"No cached snapshot for {date}")
    cases = progress.load_cases_lenient(snaps[date])
    if case_number not in cases:
        raise FileNotFoundError(f"Case {case_number} missing on {date}")
    return cases[case_number]


def load_spread_summary(path: Path = SUMMARY_CSV) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}; run the labeled spread-history scan first."
        )
    with path.open() as handle:
        rows = sorted(csv.DictReader(handle), key=lambda r: int(r["case"]))
    if len(rows) != 8:
        raise ValueError(f"Expected 8 cases in {path}, found {len(rows)}")
    return rows


def _blend_toward(base_color, tint: np.ndarray, strength: float = 0.62) -> tuple:
    """Pull a matplotlib color toward a red/green tint for before/after panels."""
    rgba = plt.matplotlib.colors.to_rgba(base_color)
    mixed = np.asarray(rgba[:3]) * (1.0 - strength) + tint * strength
    return (float(mixed[0]), float(mixed[1]), float(mixed[2]), 0.88)


def _plot_case_spectra(ax, case, names, *, tint: np.ndarray, show_cluster: bool) -> None:
    if show_cluster:
        ref = reference_label(names)
        cluster_pool = [n for n in names if not is_zmt_only_name(n)] or list(names)
        if ref is not None and ref in {display_submission_label(n) for n in cluster_pool}:
            try:
                cluster_names, _ = identify_main_cluster(
                    case, cluster_pool, reference_label=ref
                )
                offs, z_min, z_max = _cluster_z_envelope(case, cluster_names)
                _plot_main_cluster_envelope(ax, offs, z_min, z_max)
            except ValueError:
                pass

    for name in names:
        z = case.submissions[name].values.astype(float)
        finite = _display_offset_mask(case.offsets_ppm) & np.isfinite(z)
        ax.plot(
            case.offsets_ppm[finite],
            z[finite],
            color=_blend_toward(_submission_color(name), tint),
            linestyle=":" if is_zmt_only_name(name) else _submission_linestyle(name),
            alpha=0.9,
            linewidth=PLOT_LINE_WIDTH * 0.95,
            zorder=3,
        )
    ax.invert_xaxis()
    ax.grid(True, alpha=0.22)
    ax.set_facecolor("white")


def _plot_case_asym(
    ax,
    case,
    names,
    *,
    tint: np.ndarray,
    xlim_ppm: tuple[float, float] = ASYM_XLIM_PPM,
) -> None:
    """Plot MTR_asym traces; ``xlim_ppm`` is (left, right), e.g. (3, 0)."""
    x_lo, x_hi = min(xlim_ppm), max(xlim_ppm)
    y_vals: list[float] = []
    for name in names:
        z = case.submissions[name].values.astype(float)
        ppm, asym = compute_mtrasym(case.offsets_ppm, z)
        if ppm.size == 0:
            continue
        finite = np.isfinite(ppm) & np.isfinite(asym)
        ax.plot(
            ppm[finite],
            asym[finite],
            color=_blend_toward(_submission_color(name), tint),
            linestyle=":" if is_zmt_only_name(name) else _submission_linestyle(name),
            alpha=0.9,
            linewidth=PLOT_LINE_WIDTH * 0.95,
            zorder=3,
        )
        in_win = finite & (ppm >= x_lo) & (ppm <= x_hi)
        if np.any(in_win):
            y_vals.extend(asym[in_win].tolist())
    ax.set_xlim(*xlim_ppm)
    if y_vals:
        lo, hi = float(np.min(y_vals)), float(np.max(y_vals))
        pad = 0.08 * (hi - lo) if hi > lo else 0.001
        ax.set_ylim(lo - pad, hi + pad)
    ax.grid(True, alpha=0.22)
    ax.set_facecolor("white")


def _share_ylim(*axes) -> None:
    lo = min(ax.get_ylim()[0] for ax in axes)
    hi = max(ax.get_ylim()[1] for ax in axes)
    pad = 0.04 * (hi - lo) if hi > lo else 0.02
    for ax in axes:
        ax.set_ylim(lo - pad, hi + pad)


def _format_asym_yaxis(ax, *, labelsize: float) -> None:
    """Short MTR_asym tick labels in units of 1e-3 (title carries the scale)."""
    ax.yaxis.set_major_locator(plt.MaxNLocator(nbins=3))
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda value, _pos: f"{value * 1e3:g}")
    )
    ax.tick_params(axis="y", labelsize=labelsize, pad=1)


def _plot_spread_panel(
    ax,
    x: np.ndarray,
    worst: np.ndarray,
    now: np.ndarray,
    *,
    ylabel: str,
    show_xticklabels: bool,
    show_legend: bool = False,
) -> None:
    for i, (w, n) in enumerate(zip(worst, now)):
        ax.plot([i, i], [n, w], color="0.75", lw=1.1, zorder=1)
    ax.plot(
        x,
        worst,
        "s--",
        color=LINE_WORST,
        ms=6,
        lw=1.25,
        zorder=2,
        label="largest observed deviation",
    )
    ax.plot(
        x,
        now,
        "o-",
        color=LINE_FINAL,
        ms=6.5,
        lw=1.35,
        zorder=3,
        label="current",
    )
    ax.set_yscale("log")
    ax.set_ylabel(ylabel, fontsize=PLOT_FONT_SIZE - 1, labelpad=2)
    ax.yaxis.set_major_locator(plt.LogLocator(base=10, numticks=5))
    ax.set_xticks(x)
    if show_xticklabels:
        ax.set_xticklabels(CASE_LABELS, fontsize=PLOT_FONT_SIZE - 2)
    else:
        ax.tick_params(labelbottom=False)
    if show_legend:
        # Extra log headroom so a one-row legend sits above all markers.
        lo, hi = ax.get_ylim()
        ax.set_ylim(lo, hi * 15)
        decades = np.arange(np.ceil(np.log10(lo)), np.floor(np.log10(hi)) + 1)
        ax.set_yticks(10.0**decades)
        ax.legend(
            loc="upper center",
            ncol=2,
            fontsize=PLOT_LEGEND_FONT_SIZE - 1,
            frameon=True,
            fancybox=False,
            edgecolor="0.85",
            framealpha=0.92,
            borderaxespad=0.3,
        )
    ax.grid(True, axis="y", alpha=0.22, which="both")
    ax.set_xlim(-0.4, 7.4)
    ax.tick_params(labelsize=PLOT_FONT_SIZE - 2)


def plot_case5_history(output_path: Path) -> Path:
    """Kept name for callers; draws Cases 3 and 5 plus all-case spreads."""
    snaps = progress.iter_cached_snapshots()
    current_date = snaps[-1][0]
    summary = load_spread_summary()

    worst3 = snapshot_case(WORST_DATES[3], 3)
    now3 = snapshot_case(current_date, 3)
    # zMT only on the largest-observed (before) Case 3 panels.
    names3_w = included_names(worst3, exclude_zmt=False)
    names3_n = included_names(now3, exclude_zmt=True)

    worst5 = snapshot_case(WORST_DATES[5], 5)
    now5 = snapshot_case(current_date, 5)
    names5_w = included_names(worst5, exclude_zmt=True)
    names5_n = included_names(now5, exclude_zmt=True)

    with _plot_style():
        fig = plt.figure(figsize=(10.5, 7.2))
        # Nested: tight within each block, small gap between spectra and spreads.
        outer = GridSpec(
            2,
            1,
            figure=fig,
            height_ratios=[1.0, 1.15],
            hspace=0.20,
            left=0.11,
            right=0.97,
            top=0.96,
            bottom=0.09,
        )
        # Case 3 block (Z | asym) and Case 5 block get equal width.
        gs_top = outer[0].subgridspec(1, 2, wspace=0.10)
        gs_c3 = gs_top[0].subgridspec(2, 2, hspace=0.10, wspace=0.30)
        gs_c5 = gs_top[1].subgridspec(2, 1, hspace=0.10)
        gs_bot = outer[1].subgridspec(2, 1, hspace=0.22)

        ax_z3_w = fig.add_subplot(gs_c3[0, 0])
        ax_a3_w = fig.add_subplot(gs_c3[0, 1])
        ax_z5_w = fig.add_subplot(gs_c5[0, 0])
        ax_z3_n = fig.add_subplot(gs_c3[1, 0])
        ax_a3_n = fig.add_subplot(gs_c3[1, 1])
        ax_z5_n = fig.add_subplot(gs_c5[1, 0])
        ax_max = fig.add_subplot(gs_bot[0, 0])
        ax_med = fig.add_subplot(gs_bot[1, 0], sharex=ax_max)

        _plot_case_spectra(
            ax_z3_w, worst3, names3_w, tint=TINT_WORST, show_cluster=True
        )
        _plot_case_spectra(
            ax_z3_n, now3, names3_n, tint=TINT_FINAL, show_cluster=True
        )
        _plot_case_asym(ax_a3_w, worst3, names3_w, tint=TINT_WORST)
        _plot_case_asym(ax_a3_n, now3, names3_n, tint=TINT_FINAL)
        _plot_case_spectra(
            ax_z5_w, worst5, names5_w, tint=TINT_WORST, show_cluster=True
        )
        _plot_case_spectra(
            ax_z5_n, now5, names5_n, tint=TINT_FINAL, show_cluster=True
        )

        _share_ylim(ax_z3_w, ax_z3_n)
        _share_ylim(ax_a3_w, ax_a3_n)
        _share_ylim(ax_z5_w, ax_z5_n)

        for ax in (ax_a3_w, ax_a3_n):
            _format_asym_yaxis(ax, labelsize=PLOT_FONT_SIZE - 2)
        # Case 5 y-ticks on the right so they do not crowd the asym panel.
        for ax in (ax_z5_w, ax_z5_n):
            ax.yaxis.tick_right()
            ax.set_xticks([2, 1, 0, -1, -2])

        ax_z3_w.set_title("Case 3", fontsize=PLOT_FONT_SIZE, pad=2)
        ax_a3_w.set_title(
            r"Case 3 MTR$_{\mathrm{asym}}$ ($\times10^{-3}$)",
            fontsize=PLOT_FONT_SIZE,
            pad=2,
        )
        ax_z5_w.set_title("Case 5", fontsize=PLOT_FONT_SIZE, pad=2)
        for ax in (ax_z3_w, ax_a3_w, ax_z5_w):
            ax.set_xlabel("")
            ax.tick_params(labelbottom=False)
            plt.setp(ax.get_xticklabels(), visible=False)
        ax_z3_n.set_xlabel("Offset (ppm)", labelpad=0)
        ax_a3_n.set_xlabel("Offset (ppm)", labelpad=0)
        ax_z5_n.set_xlabel("Offset (ppm)", labelpad=0)
        ax_max.tick_params(labelbottom=False)
        ax_z3_w.set_ylabel("largest observed\ndeviation", labelpad=3)
        ax_z3_n.set_ylabel("current", labelpad=3)

        x = np.arange(8)
        _plot_spread_panel(
            ax_max,
            x,
            np.array([float(r["max_dZ_worst"]) for r in summary]),
            np.array([float(r["max_dZ_now"]) for r in summary]),
            ylabel=r"max $\Delta Z$",
            show_xticklabels=False,
            show_legend=True,
        )
        _plot_spread_panel(
            ax_med,
            x,
            np.array([float(r["median_dZ_worst"]) for r in summary]),
            np.array([float(r["median_dZ_now"]) for r in summary]),
            ylabel=r"median $\Delta Z$",
            show_xticklabels=True,
            show_legend=False,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight", pad_inches=0.12)
    pdf_path = output_path.with_suffix(".pdf")
    fig.savefig(pdf_path, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    print(f"Wrote {output_path}")
    print(f"Wrote {pdf_path}")
    return output_path


def main() -> None:
    plot_case5_history(FIGURES_DIR / "Figure_CASE5_spread_history.png")


if __name__ == "__main__":
    main()
