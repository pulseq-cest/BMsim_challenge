#!/usr/bin/env python3
"""Download Google Sheet revisions and make per-case submission-progress GIFs."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import warnings
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from PIL import Image

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import openpyxl

from bmsim.filters import filter_submissions
from bmsim.parser import parse_case_sheet
from bmsim.plotting import (
    PLOT_FONT_SIZE,
    PLOT_LEGEND_FONT_SIZE,
    PLOT_LINE_WIDTH,
    PLOT_SUBPLOT_TITLE_FONT_SIZE,
    REFERENCE_SUBMISSION_LABEL,
    _cluster_z_envelope,
    _display_offset_mask,
    _labeled_submission_names,
    _plot_main_cluster_envelope,
    _plot_style,
    _reference_submission_name,
    _submission_color,
    _submission_linestyle,
    identify_main_cluster,
)
from bmsim.submissions import display_submission_label
from config import CASE_SHEETS, REPO_ROOT, SPREADSHEET_ID

PROGRESS_DIR = REPO_ROOT / "progress"
SNAPSHOT_DIR = PROGRESS_DIR / "snapshots"

FIGSIZE = (9.2, 5.4)
DZ_FIGSIZE = (9.2, 8.2)
DPI = 120
FRAME_SIZE = (int(FIGSIZE[0] * DPI), int(FIGSIZE[1] * DPI))
DZ_FRAME_SIZE = (int(DZ_FIGSIZE[0] * DPI), int(DZ_FIGSIZE[1] * DPI))
# Leave a fixed right margin so the axes box never moves when traces appear.
AXES_RECT = (0.09, 0.12, 0.62, 0.76)
AXES_Z_RECT = (0.10, 0.545, 0.60, 0.375)
AXES_DZ_RECT = (0.10, 0.10, 0.60, 0.375)
MIN_SIDE_FRACTION = 0.20
MIN_SIDE_POINTS = 5


def revision_export_url(revision: int) -> str:
    return (
        "https://docs.google.com/spreadsheets/export"
        f"?id={SPREADSHEET_ID}&revision={revision}&exportFormat=xlsx"
    )


def _tiles_url(end: int) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/revisions/tiles"
        f"?id={SPREADSHEET_ID}&start=1&end={end}"
    )


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "bmsim-progress/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        text = response.read().decode()
    return json.loads(text.lstrip(")]}'\n"))


def _latest_revision(seed: int = 6584) -> int:
    """Highest revision id the tiles endpoint currently accepts.

    Asking for an older end returns only that prefix, so the walk has to
    probe upward until the endpoint rejects the request.
    """
    last_ok = seed
    step = 32
    failed: int | None = None
    while failed is None:
        trial = last_ok + step
        try:
            payload = _fetch_json(_tiles_url(trial))
        except urllib.error.HTTPError as exc:
            if exc.code != 400:
                raise
            failed = trial
            break
        tiles = payload.get("tileInfo") or []
        if not tiles:
            failed = trial
            break
        last_ok = max(int(tile["end"]) for tile in tiles)
        step *= 2

    lo, hi = last_ok, failed - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        try:
            payload = _fetch_json(_tiles_url(mid))
        except urllib.error.HTTPError as exc:
            if exc.code != 400:
                raise
            hi = mid - 1
            continue
        tiles = payload.get("tileInfo") or []
        if not tiles:
            hi = mid - 1
            continue
        last_ok = max(last_ok, max(int(tile["end"]) for tile in tiles))
        lo = mid
    return last_ok


def list_daily_revisions(end_revision: int | None = None) -> list[tuple[str, int]]:
    """Return (UTC date, last revision that day) from the Sheet version history."""
    if end_revision is None:
        end_revision = _latest_revision()
        print(f"  latest revision {end_revision}")
    all_tiles: list[dict] = []
    end = end_revision
    for _ in range(40):
        payload = _fetch_json(_tiles_url(end))
        tiles = payload.get("tileInfo") or []
        if not tiles:
            break
        all_tiles.extend(tiles)
        first = min(int(tile["start"]) for tile in tiles)
        print(f"  tiles …{end} ({len(tiles)} groups, first {first})")
        if first <= 2:
            break
        end = first - 1

    by_day: dict[str, int] = {}
    for tile in all_tiles:
        day = datetime.fromtimestamp(
            tile["endMillis"] / 1000, timezone.utc
        ).date().isoformat()
        by_day[day] = int(tile["end"])
    items = sorted(by_day.items())
    print(f"  {len(items)} edit days from {items[0][0]} to {items[-1][0]}")
    return items


def load_cases_lenient(path: Path) -> dict:
    """Parse whatever case sheets exist; skip empty or legacy layouts."""
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    cases = {}
    for sheet_name in CASE_SHEETS:
        if sheet_name not in workbook.sheetnames:
            continue
        try:
            case = parse_case_sheet(workbook[sheet_name])
        except (ValueError, KeyError, IndexError):
            continue
        cases[case.case_number] = case
    return cases


def download_revision(date: str, revision: int) -> Path | None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    dest = SNAPSHOT_DIR / f"rev{revision}_{date}.xlsx"
    if dest.exists() and dest.stat().st_size > 1024 and dest.read_bytes()[:2] == b"PK":
        return dest
    req = urllib.request.Request(
        revision_export_url(revision),
        headers={"User-Agent": "bmsim-progress/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            data = response.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  skip rev {revision} ({date}): {exc}")
        return None
    if data[:2] != b"PK":
        print(f"  skip rev {revision} ({date}): not xlsx ({data[:40]!r})")
        return None
    dest.write_bytes(data)
    print(f"  wrote {dest.name} ({len(data)} bytes)")
    return dest


def iter_cached_snapshots() -> list[tuple[str, int, Path]]:
    """End-of-day snapshots already saved under progress/snapshots."""
    by_date: dict[str, tuple[int, Path]] = {}
    for path in SNAPSHOT_DIR.glob("rev*.xlsx"):
        stem = path.stem
        if not stem.startswith("rev") or "_" not in stem:
            continue
        rev_text, date = stem[3:].split("_", 1)
        try:
            revision = int(rev_text)
        except ValueError:
            continue
        previous = by_date.get(date)
        if previous is None or revision > previous[0]:
            by_date[date] = (revision, path)
    return [(date, by_date[date][0], by_date[date][1]) for date in sorted(by_date)]


def _offset_grid_is_bipolar(offsets: np.ndarray) -> bool:
    display = _display_offset_mask(offsets)
    return bool(np.any(display & (offsets > 0))) and bool(
        np.any(display & (offsets < 0))
    )


def _spectrum_is_bipolar(offsets: np.ndarray, z: np.ndarray) -> bool:
    """Drop half-filled spectra that only occupy one side of 0 ppm."""
    if not _offset_grid_is_bipolar(offsets):
        return False
    display = _display_offset_mask(offsets)
    finite = display & np.isfinite(z)
    n_pos_grid = int(np.count_nonzero(display & (offsets > 0)))
    n_neg_grid = int(np.count_nonzero(display & (offsets < 0)))
    n_pos = int(np.count_nonzero(finite & (offsets > 0)))
    n_neg = int(np.count_nonzero(finite & (offsets < 0)))
    need_pos = max(MIN_SIDE_POINTS, int(MIN_SIDE_FRACTION * n_pos_grid))
    need_neg = max(MIN_SIDE_POINTS, int(MIN_SIDE_FRACTION * n_neg_grid))
    return n_pos >= need_pos and n_neg >= need_neg


def _masked_spectrum(offsets: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Keep NaNs so matplotlib does not draw across missing offsets."""
    plotted = np.asarray(z, dtype=float).copy()
    plotted[~_display_offset_mask(offsets)] = np.nan
    return plotted


def _s02_name(names: list[str]) -> str | None:
    for name in names:
        if display_submission_label(name) == REFERENCE_SUBMISSION_LABEL:
            return name
    for name in names:
        if display_submission_label(name).startswith(REFERENCE_SUBMISSION_LABEL):
            return name
    return None


def _delta_z_vs_s02(case, name: str, ref_name: str) -> np.ndarray:
    offsets = case.offsets_ppm
    z = _masked_spectrum(offsets, case.submissions[name].values)
    ref = _masked_spectrum(offsets, case.submissions[ref_name].values)
    ref_ok = np.isfinite(ref)
    if np.count_nonzero(ref_ok) < 2:
        return np.full_like(z, np.nan)
    order = np.argsort(offsets[ref_ok])
    xp = offsets[ref_ok][order]
    fp = ref[ref_ok][order]
    delta = np.full_like(z, np.nan)
    ok = np.isfinite(z)
    delta[ok] = z[ok] - np.interp(offsets[ok], xp, fp)
    return delta


def _plotted_names(case) -> list[str]:
    if not _offset_grid_is_bipolar(case.offsets_ppm):
        return []
    keep = filter_submissions(case.participant_names, exclude_zmt=True)
    names = _labeled_submission_names([case.participant_names[i] for i in keep])
    nonempty = []
    for name in names:
        values = case.submissions[name].values.astype(float)
        if _spectrum_is_bipolar(case.offsets_ppm, values):
            nonempty.append(name)
    return nonempty


def case_fingerprint(case) -> str:
    digest = hashlib.sha256()
    mask = _display_offset_mask(case.offsets_ppm)
    for name in _plotted_names(case):
        z = np.asarray(case.submissions[name].values, dtype=float)[mask]
        rounded = np.round(np.nan_to_num(z, nan=1e9), 6).tobytes()
        digest.update(display_submission_label(name).encode())
        digest.update(rounded)
    return digest.hexdigest()


def unique_frames(snapshots: list[tuple[str, int, object]], case_number: int):
    frames = []
    previous = None
    for date, revision, cases in snapshots:
        case = cases.get(case_number)
        if case is None:
            continue
        names = _plotted_names(case)
        if not names:
            continue
        fingerprint = case_fingerprint(case)
        if fingerprint == previous:
            continue
        previous = fingerprint
        frames.append((date, revision, case, names))
    return frames


def _appearance_order(frames) -> list[str]:
    """Display labels in the order submissions first appear."""
    order: list[str] = []
    seen: set[str] = set()
    for _date, _revision, _case, names in frames:
        for name in names:
            label = display_submission_label(name)
            if label in seen:
                continue
            seen.add(label)
            order.append(label)
    return order


def _legend_for_names(
    names: list[str], appearance_order: list[str]
) -> tuple[list[str], dict[str, str]]:
    present = {display_submission_label(name): name for name in names}
    labels = [label for label in appearance_order if label in present]
    return labels, {label: present[label] for label in labels}


def _xlim_from_frames(frames) -> tuple[float, float]:
    _date, _revision, case, _names = frames[-1]
    mask = _display_offset_mask(case.offsets_ppm)
    values = case.offsets_ppm[mask]
    xmax = float(np.nanmax(values))
    xmin = float(np.nanmin(values))
    pad = 0.02 * max(xmax - xmin, 1e-3)
    return xmax + pad, xmin - pad


def _ylim_from_frames(frames) -> tuple[float, float]:
    _date, _revision, case, names = frames[-1]
    mask = _display_offset_mask(case.offsets_ppm)
    values: list[float] = []
    for name in names:
        z = np.asarray(case.submissions[name].values, dtype=float)[mask]
        values.extend(z[np.isfinite(z)].tolist())
    if not values:
        return -0.05, 1.08
    lo, hi = float(np.min(values)), float(np.max(values))
    lo = min(lo, 0.0)
    hi = max(hi, 1.0)
    span = max(hi - lo, 1e-3)
    return lo - 0.06 * span, hi + 0.08 * span


def _dylim_from_frames(frames) -> tuple[float, float]:
    values: list[float] = []
    for _date, _revision, case, names in frames:
        ref_name = _s02_name(names)
        if ref_name is None:
            continue
        for name in names:
            delta = _delta_z_vs_s02(case, name, ref_name)
            values.extend(delta[np.isfinite(delta)].tolist())
    if not values:
        return -0.05, 0.05
    magnitude = float(np.nanpercentile(np.abs(values), 99))
    magnitude = max(magnitude * 1.1, 1e-3)
    return -magnitude, magnitude


def _fit_frame(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    rgb = image.convert("RGB")
    canvas = Image.new("RGB", size, (255, 255, 255))
    canvas.paste(rgb, (0, 0))
    return canvas


def _legend_handles(legend_labels: list[str], label_examples: dict[str, str]):
    return [
        Line2D(
            [0],
            [0],
            color=_submission_color(label_examples[label]),
            linestyle=_submission_linestyle(label_examples[label]),
            alpha=0.85,
            linewidth=PLOT_LINE_WIDTH,
        )
        for label in legend_labels
    ]


def _draw_z_traces(ax, case, names) -> list[str]:
    offsets = case.offsets_ppm
    cluster_names: list[str] = []
    try:
        _reference_submission_name(names, reference_label=REFERENCE_SUBMISSION_LABEL)
        cluster_names, _spread = identify_main_cluster(
            case, names, reference_label=REFERENCE_SUBMISSION_LABEL
        )
        cluster_offsets, cluster_z_min, cluster_z_max = _cluster_z_envelope(
            case, cluster_names
        )
        _plot_main_cluster_envelope(ax, cluster_offsets, cluster_z_min, cluster_z_max)
    except (ValueError, KeyError):
        pass
    for name in names:
        y = _masked_spectrum(offsets, case.submissions[name].values)
        if not np.isfinite(y).any():
            continue
        ax.plot(
            offsets,
            y,
            color=_submission_color(name),
            linestyle=_submission_linestyle(name),
            alpha=0.85,
            linewidth=PLOT_LINE_WIDTH,
        )
    return cluster_names


def _draw_dz_traces(ax, case, names) -> None:
    offsets = case.offsets_ppm
    ref_name = _s02_name(names)
    ax.axhline(0.0, color="0.55", linewidth=0.8, zorder=1)
    if ref_name is None:
        return
    for name in names:
        y = _delta_z_vs_s02(case, name, ref_name)
        if not np.isfinite(y).any():
            continue
        ax.plot(
            offsets,
            y,
            color=_submission_color(name),
            linestyle=_submission_linestyle(name),
            alpha=0.85,
            linewidth=PLOT_LINE_WIDTH,
        )


def _style_panel(ax, *, xlim, ylim, ylabel: str, xlabel: str | None) -> None:
    ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.grid(True, alpha=0.25)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xmargin(0)
    ax.set_ymargin(0)
    if not xlabel:
        ax.tick_params(labelbottom=False)


def _place_legend(target, handles, labels, *, bbox_to_anchor, bbox_transform) -> None:
    if not handles:
        return
    target.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=bbox_to_anchor,
        bbox_transform=bbox_transform,
        fontsize=max(7, PLOT_LEGEND_FONT_SIZE - 2),
        frameon=False,
        borderaxespad=0.0,
        handlelength=1.8,
        labelspacing=0.28,
    )


def render_frame(
    case,
    names,
    date: str,
    *,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    legend_labels: list[str],
    label_examples: dict[str, str],
    mode: str = "z",
    dylim: tuple[float, float] | None = None,
) -> Image.Image:
    figsize = FIGSIZE if mode == "z" else DZ_FIGSIZE
    frame_size = FRAME_SIZE if mode == "z" else DZ_FRAME_SIZE
    with _plot_style(font_size=11, legend_font_size=8):
        fig = plt.figure(figsize=figsize, dpi=DPI, facecolor="white")
        handles = _legend_handles(legend_labels, label_examples)
        if mode == "z":
            ax = fig.add_axes(AXES_RECT, facecolor="white")
            cluster_names = _draw_z_traces(ax, case, names)
            _style_panel(ax, xlim=xlim, ylim=ylim, ylabel=r"$Z$", xlabel="Offset (ppm)")
            ax.set_title(
                f"Case {case.case_number}  ·  {date}",
                fontsize=PLOT_SUBPLOT_TITLE_FONT_SIZE,
                pad=8,
            )
            extra = f"  ·  MC {len(cluster_names)}" if cluster_names else ""
            ax.text(
                0.01,
                0.02,
                f"{len(names)} submission{'s' if len(names) != 1 else ''}" + extra,
                transform=ax.transAxes,
                ha="left",
                va="bottom",
                fontsize=PLOT_FONT_SIZE - 2,
                color="0.35",
            )
            _place_legend(
                ax,
                handles,
                legend_labels,
                bbox_to_anchor=(1.04, 1.0),
                bbox_transform=ax.transAxes,
            )
        else:
            ax_z = fig.add_axes(AXES_Z_RECT, facecolor="white")
            ax_dz = fig.add_axes(AXES_DZ_RECT, facecolor="white")
            cluster_names = _draw_z_traces(ax_z, case, names)
            _draw_dz_traces(ax_dz, case, names)
            _style_panel(ax_z, xlim=xlim, ylim=ylim, ylabel=r"$Z$", xlabel=None)
            _style_panel(
                ax_dz,
                xlim=xlim,
                ylim=dylim or (-0.05, 0.05),
                ylabel=r"$\Delta Z$ vs S02",
                xlabel="Offset (ppm)",
            )
            ax_z.set_title(
                f"Case {case.case_number}  ·  {date}",
                fontsize=PLOT_SUBPLOT_TITLE_FONT_SIZE,
                pad=8,
            )
            extra = f"  ·  MC {len(cluster_names)}" if cluster_names else ""
            ax_z.text(
                0.01,
                0.02,
                f"{len(names)} submission{'s' if len(names) != 1 else ''}" + extra,
                transform=ax_z.transAxes,
                ha="left",
                va="bottom",
                fontsize=PLOT_FONT_SIZE - 2,
                color="0.35",
            )
            _place_legend(
                fig,
                handles,
                legend_labels,
                bbox_to_anchor=(0.72, 0.92),
                bbox_transform=fig.transFigure,
            )
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=DPI, facecolor="white", pad_inches=0)
        plt.close(fig)
    buf.seek(0)
    return _fit_frame(Image.open(buf), frame_size)


def write_gif(
    frames,
    case_number: int,
    *,
    mode: str = "z",
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    dylim: tuple[float, float] | None = None,
    appearance_order: list[str],
) -> Path | None:
    if not frames:
        print(f"Case {case_number} ({mode}): no frames")
        return None
    images = []
    for date, _revision, case, names in frames:
        legend_labels, examples = _legend_for_names(names, appearance_order)
        images.append(
            render_frame(
                case,
                names,
                date,
                xlim=xlim,
                ylim=ylim,
                legend_labels=legend_labels,
                label_examples=examples,
                mode=mode,
                dylim=dylim,
            )
        )
        print(
            f"  Case {case_number} {mode} frame {date} ({len(names)} submissions)"
        )

    palette = images[-1].quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    quantized = [
        image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images
    ]
    durations = [400] * (len(quantized) - 1) + [1800]
    suffix = "progress" if mode == "z" else "progress_dZ"
    out = PROGRESS_DIR / f"Case_{case_number}_{suffix}.gif"
    quantized[0].save(
        out,
        save_all=True,
        append_images=quantized[1:],
        duration=durations,
        loop=0,
        optimize=False,
        disposal=2,
    )
    frame_size = FRAME_SIZE if mode == "z" else DZ_FRAME_SIZE
    print(f"Wrote {out} ({len(quantized)} frames, {frame_size[0]}x{frame_size[1]})")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Refresh Sheet revision snapshots before plotting",
    )
    parser.add_argument(
        "--only-dz",
        action="store_true",
        help="Rebuild only the two-panel ΔZ GIFs",
    )
    args = parser.parse_args()

    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    warnings.filterwarnings(
        "ignore",
        message="Sparkline Group extension is not supported",
    )
    if args.fetch or not any(SNAPSHOT_DIR.glob("rev*.xlsx")):
        print("Listing Sheet version-history days…")
        snapshot_days = list_daily_revisions()
        print(f"Downloading {len(snapshot_days)} sheet revisions…")
        for date, revision in snapshot_days:
            download_revision(date, revision)

    cached = iter_cached_snapshots()
    loaded: list[tuple[str, int, dict]] = []
    print(f"Parsing {len(cached)} cached snapshots…")
    for date, revision, path in cached:
        cases = load_cases_lenient(path)
        loaded.append((date, revision, cases))
        print(f"  parsed rev {revision} ({date}): cases {sorted(cases)}")

    for case_number in range(1, 9):
        frames = unique_frames(loaded, case_number)
        if not frames:
            print(f"Case {case_number}: no frames")
            continue
        xlim = _xlim_from_frames(frames)
        ylim = _ylim_from_frames(frames)
        dylim = _dylim_from_frames(frames)
        appearance_order = _appearance_order(frames)
        shared = dict(
            xlim=xlim,
            ylim=ylim,
            dylim=dylim,
            appearance_order=appearance_order,
        )
        if not args.only_dz:
            write_gif(frames, case_number, mode="z", **shared)
        write_gif(frames, case_number, mode="dz", **shared)


if __name__ == "__main__":
    main()
