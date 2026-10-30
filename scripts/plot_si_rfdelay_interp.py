#!/usr/bin/env python3
"""SI figure: interpolation-grid placement changes how long omega_RF stays on."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.linalg import expm

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from bmsim.parser import load_all_cases
from config import CACHE_XLSX, FIGURES_DIR, REPO_ROOT

GAMMA = 267.5154109126009  # rad / s / uT
GAMMA_HZ = GAMMA / (2.0 * np.pi)
B0 = 3.0
MAG_MAX_HZ = 141.667
PULSE_LEN = 0.050
DELAY_LEN = 0.005
N_REPEAT = 36
T_POST = 6.5e-3
DT = 0.00025


def _load_pulse() -> tuple[np.ndarray, np.ndarray]:
    csv_path = REPO_ROOT / "BMsim_challenge" / "case_6" / "rf_pulse.csv"
    data = np.loadtxt(csv_path, delimiter=",")
    t = data[:, 0]
    amp = data[:, 1]
    b1_hz = amp / np.max(amp) * MAG_MAX_HZ
    return t, b1_hz


def _affine_expm(evol: np.ndarray, c: np.ndarray, t: float) -> np.ndarray:
    """7x7 homogeneous propagator for dM/dt = A M + c."""
    n = evol.shape[0]
    ah = np.zeros((n + 1, n + 1))
    ah[:n, :n] = evol
    ah[:n, n] = c
    return expm(ah * t)


def _build_matrices(offs_ppm: float):
    """Relaxation, exchange, and offset-dependent chemical-shift terms."""
    t1 = np.array([3.0, 1.05])
    t2 = np.array([2.0, 0.1])
    f = np.array([1.0, 5.0e-4])
    k_ex = 50.0
    dw_ppm = np.array([0.0, 1.9])
    r1 = 1.0 / t1
    r2 = 1.0 / t2
    k_we = f[1] * k_ex / f[0]
    k_ew = k_ex

    r_mat = -np.diag(np.concatenate([r2, r2, r1]))
    exch = np.zeros((6, 6))
    for block in range(3):
        sl = slice(block * 2, block * 2 + 2)
        exch[sl, sl] = np.array([[-k_we, k_ew], [k_we, -k_ew]])

    dw_pool = 2.0 * np.pi * B0 * GAMMA_HZ * dw_ppm
    dw_rf = 2.0 * np.pi * round(B0 * GAMMA_HZ * offs_ppm, 6)
    magn_ss = np.array([0.0, 0.0, 0.0, 0.0, f[0], f[1]]) / f[0]
    c = -r_mat @ magn_ss
    return r_mat, exch, dw_pool, dw_rf, c, magn_ss


def _cs_and_pulse_mat(dw: np.ndarray, b1_hz: float) -> np.ndarray:
    w1 = 2.0 * np.pi * b1_hz
    cs = np.zeros((6, 6))
    cs[0, 2] = dw[0]
    cs[1, 3] = dw[1]
    cs[2, 0] = -dw[0]
    cs[3, 1] = -dw[1]
    pulse = np.zeros((6, 6))
    # x-pulse: y <-> z
    pulse[2, 4] = -w1
    pulse[3, 5] = -w1
    pulse[4, 2] = w1
    pulse[5, 3] = w1
    return cs + pulse


def _step_prop(r_mat, exch, dw_pool, dw_rf, c, b1_hz, dt, wrf_on: bool) -> np.ndarray:
    dw = dw_pool - dw_rf if wrf_on else dw_pool
    evol = r_mat + exch + _cs_and_pulse_mat(dw, b1_hz)
    return _affine_expm(evol, c, dt)


def _compose(props: list[np.ndarray]) -> np.ndarray:
    out = np.eye(7)
    for p in props:
        out = p @ out
    return out


def _apply(prop: np.ndarray, m: np.ndarray) -> np.ndarray:
    v = prop @ np.append(m, 1.0)
    return v[:6]


def _waveform_aligned(t_csv: np.ndarray, b1_hz: np.ndarray):
    """Pulse samples as supplied, then a single delay with B1=0 and omega_RF off."""
    pulse = [(float(b), DT, True) for b in b1_hz]
    delay = [(0.0, DELAY_LEN, False)]
    return pulse, delay


def _waveform_misaligned(t_csv: np.ndarray, b1_hz: np.ndarray):
    """0th-order interpolation onto a grid that does not match the CSV nodes."""
    t_src = np.concatenate([t_csv, [PULSE_LEN, PULSE_LEN + DELAY_LEN]])
    b_src = np.concatenate([b1_hz, [0.0, 0.0]])
    t_grid = np.arange(0.0, PULSE_LEN + DELAY_LEN, DT)
    idx = np.clip(np.searchsorted(t_src, t_grid, side="right") - 1, 0, len(b_src) - 1)
    b_grid = b_src[idx]
    wrf = np.abs(b_grid) > 1e-9
    dts = np.diff(np.concatenate([t_grid, [PULSE_LEN + DELAY_LEN]]))
    pulse_mask = t_grid < PULSE_LEN
    # Keep extra non-zero samples that spill into the delay with the pulse block
    # so omega_RF stays on for those extra steps.
    pulse = [
        (float(b), float(dt), bool(on))
        for b, dt, on, in_pulse in zip(b_grid, dts, wrf, pulse_mask)
        if in_pulse or on
    ]
    delay_steps = [
        (float(b), float(dt), bool(on))
        for b, dt, on, in_pulse in zip(b_grid, dts, wrf, pulse_mask)
        if (not in_pulse) and (not on)
    ]
    if not delay_steps:
        delay_steps = [(0.0, DELAY_LEN, False)]
    return pulse, delay_steps


def _simulate_case6(t_csv, b1_hz, offs, misaligned: bool) -> np.ndarray:
    pulse, delay = (
        _waveform_misaligned(t_csv, b1_hz) if misaligned else _waveform_aligned(t_csv, b1_hz)
    )
    z = np.empty(len(offs))
    for i, off in enumerate(offs):
        r_mat, exch, dw_pool, dw_rf, c, magn_ss = _build_matrices(float(off))
        pulse_props = [
            _step_prop(r_mat, exch, dw_pool, dw_rf, c, b1, dt, wrf)
            for b1, dt, wrf in pulse
        ]
        delay_props = [
            _step_prop(r_mat, exch, dw_pool, dw_rf, c, b1, dt, wrf)
            for b1, dt, wrf in delay
        ]
        p_pulse = _compose(pulse_props)
        p_delay = _compose(delay_props)
        p_block = p_delay @ p_pulse
        p_train = np.linalg.matrix_power(p_block, N_REPEAT - 1)
        p_post = _step_prop(r_mat, exch, dw_pool, dw_rf, c, 0.0, T_POST, False)
        prop = p_post @ p_pulse @ p_train
        m = _apply(prop, magn_ss)
        z[i] = m[4]
    return z


def _plot_supplied_pulse(ax, t_csv, b1_uT) -> None:
    """Draw the two pulse edges without connecting them across the delay."""
    m1 = t_csv >= 0.0490
    m2 = t_csv <= 0.0014
    ax.plot(t_csv[m1], b1_uT[m1], color="tab:red", lw=1.7, zorder=2)
    ax.plot(t_csv[m1], b1_uT[m1], "o", color="tab:red", ms=4.5, zorder=3)
    ax.plot(
        t_csv[m2] + PULSE_LEN + DELAY_LEN,
        b1_uT[m2],
        color="tab:red",
        lw=1.7,
        zorder=2,
    )
    ax.plot(
        t_csv[m2] + PULSE_LEN + DELAY_LEN,
        b1_uT[m2],
        "o",
        color="tab:red",
        ms=4.5,
        label="Supplied pulse",
        zorder=3,
    )


def _zeroth_order_hold(t_nodes, b_nodes, dt=DT):
    """Return staircase samples (t, B1) for 0th-order hold of duration dt."""
    t_line, b_line, t_mark, b_mark = [], [], [], []
    for t0, b0 in zip(t_nodes, b_nodes):
        t_mark.append(t0)
        b_mark.append(b0)
        t_line.extend([t0, t0 + dt])
        b_line.extend([b0, b0])
    return (
        np.asarray(t_line),
        np.asarray(b_line),
        np.asarray(t_mark),
        np.asarray(b_mark),
    )


def _plot_delay_panel(ax, t_csv, b1_hz, misaligned: bool) -> None:
    b1_uT = b1_hz / GAMMA_HZ
    _plot_supplied_pulse(ax, t_csv, b1_uT)

    edge = t_csv >= 0.04915
    t_fall = t_csv[edge]
    b_fall = b1_uT[edge]
    t_rise = t_csv[t_csv <= 0.0014] + PULSE_LEN + DELAY_LEN
    b_rise = b1_uT[t_csv <= 0.0014]

    if misaligned:
        # Hold each sample for dt, so the last pulse sample spills past 50 ms
        # and the next pulse is entered dt early.
        t_on_f, b_on_f, t_mk_f, b_mk_f = _zeroth_order_hold(t_fall, b_fall)
        t_on_r, b_on_r, t_mk_r, b_mk_r = _zeroth_order_hold(t_rise - DT, b_rise)
        ax.plot(t_on_f, b_on_f, color="tab:blue", ls="--", lw=1.15, zorder=4)
        ax.plot(t_on_r, b_on_r, color="tab:blue", ls="--", lw=1.15, zorder=4)
        ax.plot(
            np.concatenate([t_mk_f, t_mk_r]),
            np.concatenate([b_mk_f, b_mk_r]),
            "+",
            color="tab:blue",
            ms=9,
            mew=1.4,
            label=r"$\omega_{\mathrm{rf}}\neq 0$",
            zorder=5,
        )
        t_off0 = t_fall[-1] + DT
        t_off1 = t_rise[0] - DT
        ax.plot(
            [t_on_f[-1], t_off0, t_off0],
            [b_fall[-1], b_fall[-1], 0.0],
            color="tab:blue",
            ls="--",
            lw=1.15,
            zorder=4,
        )
        ax.plot(
            [t_off0, t_off1],
            [0.0, 0.0],
            color="k",
            ls="--",
            lw=1.2,
            label=r"$\omega_{\mathrm{rf}}=0$",
            zorder=4,
        )
    else:
        ax.plot(
            t_fall,
            b_fall,
            "+",
            color="tab:blue",
            ms=9,
            mew=1.4,
            label=r"$\omega_{\mathrm{rf}}\neq 0$",
            zorder=5,
        )
        ax.plot(
            t_rise,
            b_rise,
            "+",
            color="tab:blue",
            ms=9,
            mew=1.4,
            zorder=5,
        )
        ax.plot(
            [t_fall[-1], PULSE_LEN, PULSE_LEN],
            [b_fall[-1], b_fall[-1], 0.0],
            color="tab:blue",
            ls="--",
            lw=1.0,
            zorder=4,
        )
        ax.plot(
            [PULSE_LEN, PULSE_LEN + DELAY_LEN],
            [0.0, 0.0],
            color="k",
            ls="--",
            lw=1.2,
            label=r"$\omega_{\mathrm{rf}}=0$",
            zorder=4,
        )

    ax.set_xlim(0.0493, 0.0558)
    ax.set_ylim(-0.005, 0.085)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel(r"$B_1$ [$\mu$T]")
    ax.set_title("In-between pulses")
    ax.legend(frameon=False, fontsize=8, loc="upper center")


def _plot_zspec_row(axz, axd, offs, z_zaiss, z_cestsim) -> None:
    axz.plot(offs, z_zaiss, color="tab:red", lw=1.5, label="M. Zaiss")
    axz.plot(offs, z_cestsim, color="tab:blue", ls="--", lw=1.4, label="CESTSim.jl")
    axz.set_xlim(-5, 5)
    axz.set_ylim(-0.5, 1.05)
    axz.set_xlabel(r"$\Delta\omega$ [ppm]")
    axz.set_ylabel(r"$M_z$ [au]")
    axz.set_title("Zspec")
    axz.legend(frameon=False, fontsize=8, loc="lower right")

    axd.plot(offs, z_zaiss - z_cestsim, color="tab:red", lw=1.2)
    axd.axhline(0.0, color="0.75", lw=0.8)
    axd.set_xlim(-12, 12)
    axd.set_ylim(-0.035, 0.008)
    axd.set_xlabel(r"$\Delta\omega$ [ppm]")
    axd.set_ylabel(r"$\Delta M_z$ [au]")
    axd.set_title("Difference")


def main() -> None:
    t_csv, b1_hz = _load_pulse()
    cases = load_all_cases(CACHE_XLSX, download=False)
    case = cases[6]
    mask = np.isfinite(case.offsets_ppm) & ~np.isclose(case.offsets_ppm, -300.0)
    offs = case.offsets_ppm[mask]
    z_zaiss = case.submissions["S01"].values.astype(float)[mask]
    z_cestsim = case.submissions["S15"].values.astype(float)[mask]

    fig, axes = plt.subplots(2, 3, figsize=(11.2, 6.4), constrained_layout=True)
    _plot_delay_panel(axes[0, 0], t_csv, b1_hz, misaligned=True)
    _plot_delay_panel(axes[1, 0], t_csv, b1_hz, misaligned=False)
    _plot_zspec_row(axes[0, 1], axes[0, 2], offs, z_zaiss, z_cestsim)
    _plot_zspec_row(axes[1, 1], axes[1, 2], offs, z_zaiss, z_cestsim)

    fig.savefig(FIGURES_DIR / "SI_Case6_rfinterp_grid.png", dpi=200)
    fig.savefig(FIGURES_DIR / "SI_Case6_rfinterp_grid.pdf")
    plt.close(fig)
    print(f"Wrote {FIGURES_DIR / 'SI_Case6_rfinterp_grid.png'}")
    print(
        "max|CESTSim-Zaiss|="
        f"{float(np.nanmax(np.abs(z_cestsim - z_zaiss))):.4f}"
    )


if __name__ == "__main__":
    main()
