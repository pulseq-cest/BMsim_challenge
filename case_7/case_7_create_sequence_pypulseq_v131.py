# BMSim Challenge: CASE 7
# Script to create the seq-file for the BMSim Challenge CASE 7
#
# https://github.com/pulseq-cest/BMsim_challenge
#
# Tested with pypulseq version 1.3.1post1 and bmctool version 0.6.1
#
# Patrick Schuenke 2023
# patrick.schuenke@ptb.de

import copy
from pathlib import Path
from types import SimpleNamespace
from scipy.interpolate import interp1d

import numpy as np
import pypulseq as pp
from bmctool.utils.pulses.calc_power_equivalents import calc_power_equivalent
from bmctool.utils.seq.write import write_seq


def make_pulse_from_txt(fpath, system):
    """Creates a rf event using the signal from the provided txt-file.

    The txt-file contains the time steps in the first column and the signal
    in the second column. The total duration of the pulse is 50 ms and 200
    samples are given leading to a dwell time of 250 µs.

    Parameters
    ----------
    fpath
        Path to the txt-file
    system
        PyPulseq system object

    Returns
    -------
        RF event (SimpleNamespace)
    """
    _data = np.loadtxt(fpath)
    _t = np.squeeze(_data[:, 0])
    _signal = np.squeeze(_data[:, 1:])

    _rf = SimpleNamespace()
    _rf.type = "rf"
    _rf.signal = _signal
    _rf.t = _t
    _rf.shape_dur = (_t[1] - _t[0]) * _signal.size  # dwell * number of samples
    _rf.freq_offset = 0
    _rf.phase_offset = 0
    _rf.delay = 0
    _rf.dead_time = system.rf_dead_time
    _rf.ringdown_time = system.rf_ringdown_time

    return _rf


def resample_pulse(
    rf: SimpleNamespace, rf_raster_time: float = 1e-6
) -> SimpleNamespace:
    """Resample rf pulse to specified rf raster time using a nearest neighbor interpolation.

    Parameters
    ----------
    rf : SimpleNamespace
        PyPulseq RF pulse
    rf_raster_time : float, optional
        rf raster time [s], by default 1e-6

    Returns
    -------
    SimpleNamespace
        Resampled RF pulse
    """
    # create copy of rf pulse
    rf_resampled = copy.deepcopy(rf)

    # calculate new time points for resampled rf pulse
    n_sample = int(np.round(rf.shape_dur / rf_raster_time))
    t = (np.arange(1, n_sample + 1) - 0.5) * rf_raster_time

    # calculate piecewise-constant signal with new number of samples
    f = interp1d(rf.t, rf.signal, kind="nearest", fill_value="extrapolate")
    _signal = f(t)

    # assign new values to rf_resampled
    rf_resampled.t = t
    rf_resampled.signal = _signal
    rf_resampled.raster_time = rf_raster_time

    return rf_resampled


# get id of generation file
seqid = Path(__file__).stem.replace("_create_sequence", "")

# get folder of generation file
folder = Path(__file__).parent

# define file path of rf pulse
fpath = Path(R"case_5\rf_pulse.txt")

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
defs["offsets_ppm"] = np.append(
    defs["m0_offset"],
    np.linspace(-15, 15, 301),
)  # offset vector [ppm]

defs["num_meas"] = defs["offsets_ppm"].size  # number of repetition
defs["tsat"] = (
    defs["n_pulses"] * (defs["tp"] + defs["td"]) - defs["td"]
)  # saturation time [s]
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
    rf_raster_time=1e-6,  # rf raster time = 1 µs for PyPulseq v1.3.1
    gamma=GAMMA_HZ * 1e6,
)

# ===========
# PREPARATION
# ===========

# spoiler
spoil_amp = 0.8 * sys.max_grad  # Hz/m
rise_time = 1.0e-3  # spoiler rise time in seconds
flat_time = 4.5e-3  # spoiler flat time in seconds

gx_spoil, gy_spoil, gz_spoil = [
    pp.make_trapezoid(
        channel=c,
        system=sys,
        amplitude=spoil_amp,
        flat_time=flat_time,
        rise_time=rise_time,
    )
    for c in ["x", "y", "z"]
]

# RF pulses
sat_pulse = make_pulse_from_txt(fpath, sys)

# resample rf pulse to rf raster time of 1 µs
sat_pulse = resample_pulse(sat_pulse, sys.rf_raster_time)

defs["b1rms"] = calc_power_equivalent(
    rf_pulse=sat_pulse, tp=defs["tp"], td=defs["td"], gamma_hz=GAMMA_HZ
)

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
    print(
        f"#{m + 1} / {len(offsets_hz)} : offset {offset / defs['freq']:.2f} ppm ({offset:.3f} Hz)"
    )

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
        _dur = np.sum(np.abs(sat_pulse.signal) > 0) * 1e-6
        accum_phase = (accum_phase + offset * 2 * np.pi * _dur) % (2 * np.pi)
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
