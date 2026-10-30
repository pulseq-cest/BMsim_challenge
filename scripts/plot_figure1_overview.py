#!/usr/bin/env python3
"""Figure 1: saturation scheme, Z-spectrum, and MTR_asym for all eight cases.

One row per case. The RF saturation column is built from the challenge
definitions in BMsim_challenge/case_*/ (block amplitudes and timings from the
sequence scripts, the sampled Gaussian from rf_pulse.csv); the spectra are the
Pulseq-CEST MATLAB submission (S01).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from bmsim.parser import load_all_cases
from bmsim.plotting import _display_offset_mask, _spectra_for_participant
from bmsim.submissions import display_submission_label
from config import FIGURES_DIR, REPO_ROOT

GAMMA_HZ_PER_UT = 42.5764
SPOILER_S = 6.5e-3  # 1 ms ramp + 4.5 ms flat + 1 ms ramp
LINE_COLOR = "#1f5fa8"
SPOILER_COLOR = "0.88"
SPECTRUM_SUBMISSION = "S01"

CASES = {
    1: {"label": "CW 15 s, 2-pool", "pulse": ("block", 2.0, 15.0), "n": 1, "td": 0.0, "unit": "s"},
    2: {"label": "CW 2 s, 2-pool", "pulse": ("block", 2.0, 2.0), "n": 1, "td": 0.0, "unit": "s"},
    3: {"label": "CW 2 s, 5-pool", "pulse": ("block", 2.0, 2.0), "n": 1, "td": 0.0, "unit": "s"},
    4: {"label": "WASABI block, 5-pool", "pulse": ("block", 3.7, 5e-3), "n": 1, "td": 0.0, "unit": "ms"},
    5: {"label": "Gaussian, 2-pool", "pulse": ("gauss",), "n": 1, "td": 0.0, "unit": "ms"},
    6: {"label": "Gaussian train, 2-pool", "pulse": ("gauss",), "n": 36, "td": 5e-3, "unit": "s"},
    7: {"label": "Gaussian train, 5-pool", "pulse": ("gauss",), "n": 36, "td": 5e-3, "unit": "s"},
    8: {"label": "WASABI train, 5-pool", "pulse": ("block", 3.7, 5e-3), "n": 2, "td": 100e-6, "unit": "ms"},
}


def _gaussian_samples() -> tuple[np.ndarray, np.ndarray]:
    path = REPO_ROOT / "BMsim_challenge" / "case_5" / "rf_pulse.csv"
    with path.open() as handle:
        rows = np.array([[float(v) for v in row] for row in csv.reader(handle)])
    dt = rows[1, 0] - rows[0, 0]
    return dt, rows[:, 1] / GAMMA_HZ_PER_UT


def saturation_waveform(case_number: int) -> tuple[np.ndarray, np.ndarray, float]:
    """Return (time [s], B1 [uT], end of saturation [s]) as a step waveform."""
    spec = CASES[case_number]
    times, amps = [0.0], [0.0]
    t = 0.0
    for index in range(spec["n"]):
        if spec["pulse"][0] == "block":
            _, b1, tp = spec["pulse"]
            times += [t, t + tp]
            amps += [b1, b1]
            t += tp
        else:
            dt, b1 = _gaussian_samples()
            edges = t + dt * np.arange(len(b1) + 1)
            times += list(np.repeat(edges, 2)[1:-1])
            amps += list(np.repeat(b1, 2))
            t = float(edges[-1])
        times.append(t)
        amps.append(0.0)
        if index < spec["n"] - 1:
            t += spec["td"]
            times.append(t)
            amps.append(0.0)
    sat_end = t
    times.append(t + SPOILER_S)
    amps.append(0.0)
    return np.array(times), np.array(amps), sat_end


def _submission_name(case, label: str) -> str:
    for name in case.participant_names:
        if display_submission_label(name) == label:
            return name
    return case.participant_names[0]


def plot_figure1(output_path: Path) -> Path:
    cases = load_all_cases(download=False)
    plt.rcParams.update(
        {
            "font.size": 7.5,
            "axes.titlesize": 7.5,
            "axes.labelsize": 7.5,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "axes.linewidth": 0.6,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "xtick.major.size": 2.5,
            "ytick.major.size": 2.5,
        }
    )
    fig, axes = plt.subplots(
        len(CASES), 3, figsize=(6.3, 8.0),
        gridspec_kw={"width_ratios": [1.15, 1.0, 1.0]},
    )
    fig.subplots_adjust(left=0.115, right=0.985, top=0.94, bottom=0.05,
                        wspace=0.42, hspace=1.12)

    for row, case_number in enumerate(sorted(CASES)):
        spec = CASES[case_number]
        ax_rf, ax_z, ax_asym = axes[row]

        times, amps, sat_end = saturation_waveform(case_number)
        scale = 1e3 if spec["unit"] == "ms" else 1.0
        ax_rf.axvspan(sat_end * scale, (sat_end + SPOILER_S) * scale,
                      color=SPOILER_COLOR, lw=0, zorder=0)
        ax_rf.plot(times * scale, amps, color=LINE_COLOR, lw=0.9)
        ax_rf.set_xlim(0, times[-1] * scale)
        ax_rf.set_ylim(-0.2, 4.2)
        ax_rf.set_yticks([0, 2, 4])
        ax_rf.set_ylabel(r"$B_1$ ($\mu$T)")
        ax_rf.set_xlabel(f"Time ({spec['unit']})", labelpad=1)

        case = cases[case_number]
        name = _submission_name(case, SPECTRUM_SUBMISSION)
        offsets, z, asym_ppm, mtrasym = _spectra_for_participant(case, name)
        mask = _display_offset_mask(offsets) & np.isfinite(z)
        ax_z.plot(offsets[mask], z[mask], color=LINE_COLOR, lw=1.0)
        span = float(np.nanmax(np.abs(offsets[mask])))
        ax_z.set_xlim(span, -span)
        ax_z.set_ylabel(r"$Z$")
        ax_z.set_xlabel(r"$\Delta\omega$ (ppm)", labelpad=1)

        amask = np.isfinite(asym_ppm) & np.isfinite(mtrasym) & (asym_ppm > 0) & (asym_ppm <= span)
        ax_asym.axhline(0, color="0.6", lw=0.5, zorder=0)
        ax_asym.plot(asym_ppm[amask], mtrasym[amask] * 100, color=LINE_COLOR, lw=1.0)
        ax_asym.set_xlim(span, 0)
        ax_asym.set_ylabel(r"$MTR_{\mathrm{asym}}$ (%)")
        ax_asym.set_xlabel(r"$\Delta\omega$ (ppm)", labelpad=1)

        for ax in (ax_rf, ax_z, ax_asym):
            ax.grid(True, alpha=0.25, lw=0.4)
            ax.tick_params(pad=1.5)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)

        ax_rf.text(0.0, 1.10, f"Case {case_number}: {spec['label']}",
                   transform=ax_rf.transAxes, fontweight="bold", ha="left", va="bottom")

    for ax, title in zip(axes[0], ("RF saturation", r"$Z$-spectrum", r"$MTR_{\mathrm{asym}}$")):
        ax.annotate(title, xy=(0.5, 1.0), xycoords="axes fraction", xytext=(0, 17),
                    textcoords="offset points", ha="center", va="bottom", fontweight="bold")
    fig.align_ylabels(axes[:, 0])
    fig.align_ylabels(axes[:, 1])
    fig.align_ylabels(axes[:, 2])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    fig.savefig(output_path.with_suffix(".png"), dpi=300)
    plt.close(fig)
    return output_path


if __name__ == "__main__":
    out = plot_figure1(FIGURES_DIR / "Figure_1_cases_overview.pdf")
    print(f"Wrote {out} and {out.with_suffix('.png')}")
