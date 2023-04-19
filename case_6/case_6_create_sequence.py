# BMSim Challenge: CASE 6
# Script to create the seq-file for the BMSim Challenge CASE 6
#
# https://github.com/pulseq-cest/BMsim_challenge
#
# Tested with pypulseq version 1.3.1post1 and bmctool version 0.6.0
#
# Patrick Schuenke 2023
# patrick.schuenke@ptb.de

import copy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pypulseq as pp
from bmctool.utils.pulses.calc_power_equivalents import calc_power_equivalent
from bmctool.utils.seq.write import write_seq
from scipy.interpolate import interp1d


def resample_pulse(rf: SimpleNamespace, n_sample: int = 200) -> SimpleNamespace:
    """Resample rf pulse to specified number of piecewise-constant values but original number of total samples.

    Parameters
    ----------
    rf : SimpleNamespace
        PyPulseq RF pulse
    n_sample : int, optional
        Number of samples, by default 200

    Returns
    -------
    SimpleNamespace
        Resampled RF pulse
    """
    # create copy of rf pulse
    rf_resampled = copy.deepcopy(rf)

    # get new time vector
    t = np.linspace(0, rf.t[-1], n_sample)

    # calc temporary signal with 'n_sample' samples
    _signal = np.interp(t, rf.t, rf.signal)

    # calculate piecewise-constant signal with original number of samples
    interpolation = interp1d(t, _signal, kind="nearest")
    _signal = interpolation(rf.t)

    # overwrite with piecewise-constant signal
    rf_resampled.signal = _signal

    return rf_resampled


# get id of generation file
seqid = Path(__file__).stem + "_py"

# get folder of generation file
folder = Path(__file__).parent

# define gyromagnetic ratio [Hz/T]
GAMMA_HZ = 42.5764

# sequence definitions
defs: dict = {}
defs["b1pa"] = 1.78  # B1 peak amplitude [µT] (b1rms calculated below)
defs["b0"] = 3  # B0 [T]
defs["freq"] = defs["b0"] * GAMMA_HZ  # Larmor frequency [Hz]
defs["n_pulses"] = 36  # number of pulses  #
defs["tp"] = 50e-3  # pulse duration [s]
defs["td"] = 5e-3  # interpulse delay [s]
defs["trec"] = 3.5  # recovery time [s]
defs["trec_m0"] = 3.5  # recovery time before M0 [s]
defs["m0_offset"] = -300  # m0 offset [ppm]
defs["offsets_ppm"] = np.append(defs["m0_offset"], np.linspace(-15, 15, 301))  # offset vector [ppm]

defs["num_meas"] = defs["offsets_ppm"].size  # number of repetition
defs["tsat"] = defs["n_pulses"] * (defs["tp"] + defs["td"]) - defs["td"]  # saturation time [s]
defs["seq_id_string"] = seqid  # unique seq id

seq_filename = defs["seq_id_string"] + ".seq"

# scanner limits
sys = pp.Opts(
    max_grad=80,
    grad_unit="mT/m",
    max_slew=200,
    slew_unit="T/m/s",
    rf_ringdown_time=0,
    rf_dead_time=0,
    rf_raster_time=1e-6,
    gamma=GAMMA_HZ * 1e6,
)

# ===========
# PREPARATION
# ===========

# spoiler
spoil_amp = 0.8 * sys.max_grad  # Hz/m
rise_time = 1.0e-3  # spoiler rise time in seconds
spoil_dur = 6.5e-3  # complete spoiler duration in seconds

gx_spoil, gy_spoil, gz_spoil = [
    pp.make_trapezoid(channel=c, system=sys, amplitude=spoil_amp, duration=spoil_dur, rise_time=rise_time)
    for c in ["x", "y", "z"]
]

# RF pulses
flip_angle_sat = defs["b1pa"] * GAMMA_HZ * 2 * np.pi * defs["tp"]
sat_pulse = pp.make_sinc_pulse(
    flip_angle=flip_angle_sat, duration=defs["tp"], system=sys, time_bw_product=2, apodization=0.15
)

# overwrite rf pulse with piecewise-constant signal and phase
sat_pulse = resample_pulse(sat_pulse, n_sample=200)

defs["b1rms"] = calc_power_equivalent(rf_pulse=sat_pulse, tp=defs["tp"], td=defs["td"], gamma_hz=GAMMA_HZ)

# pseudo ADC event
pseudo_adc = pp.make_adc(num_samples=1, duration=1e-3)

# delays
td_delay = pp.make_delay(defs["td"])
trec_delay = pp.make_delay(defs["trec"])
m0_delay = pp.make_delay(defs["trec_m0"])

# Sequence object
seq = pp.Sequence()

# ===
# RUN
# ===

offsets_hz = defs["offsets_ppm"] * defs["freq"]  # convert from ppm to Hz

for m, offset in enumerate(offsets_hz):
    # print progress/offset
    print(f"#{m + 1} / {len(offsets_hz)} : offset {offset / defs['freq']:.2f} ppm ({offset:.3f} Hz)")

    # reset accumulated phase
    accum_phase = 0

    # add delay
    if offset == defs["m0_offset"] * defs["freq"]:
        if defs["trec_m0"] > 0:
            seq.add_block(m0_delay)
    else:
        if defs["trec"] > 0:
            seq.add_block(trec_delay)

    # set sat_pulse
    sat_pulse.freq_offset = offset
    for n in range(defs["n_pulses"]):
        sat_pulse.phase_offset = accum_phase % (2 * np.pi)
        seq.add_block(sat_pulse)
        accum_phase = (accum_phase + offset * 2 * np.pi * np.sum(np.abs(sat_pulse.signal) > 0) * 1e-6) % (2 * np.pi)
        if n < defs["n_pulses"] - 1:
            seq.add_block(td_delay)

    # add spoiler gradients
    seq.add_block(gx_spoil, gy_spoil, gz_spoil)

    # add pseudo ADC event
    seq.add_block(pseudo_adc)

write_seq(
    seq=seq,
    seq_defs=defs,
    filename=str(folder / seq_filename),
    author="https://github.com/pulseq-cest/BMsim_challenge",
    use_matlab_names=True,
)
