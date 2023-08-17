# BMSim Challenge: CASE 8
# Script to create the seq-file for the BMSim Challenge CASE 8
#
# https://github.com/pulseq-cest/BMsim_challenge
#
# Tested with pypulseq version 1.4.0 and bmctool version 0.6.1
#
# Patrick Schuenke 2023
# patrick.schuenke@ptb.de

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pypulseq as pp
from bmctool.utils.pulses.calc_power_equivalents import calc_power_equivalent
from bmctool.utils.seq.write import write_seq

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
defs["b1pa"] = 3.7  # B1 peak average [µT] (b1rms calculated below)
defs["b0"] = 3  # B0 [T]
defs["freq"] = defs["b0"] * GAMMA_HZ  # Larmor frequency [Hz]
defs["n_pulses"] = 2  # number of pulses  #
defs["tp"] = 5e-3  # pulse duration [s]
defs["td"] = 100e-6  # interpulse delay [s]
defs["trec"] = 3.0  # recovery time [s]
defs["trec_m0"] = 12  # recovery time before M0 [s]
defs["m0_offset"] = -300  # m0 offset [ppm]
defs["offsets_ppm"] = np.append(
    defs["m0_offset"],
    np.linspace(-2, 2, 81),
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
    rf_raster_time=250e-6,  # rf raster time = 250 µs for PyPulseq v1.4
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
flip_angle_sat = defs["b1pa"] * GAMMA_HZ * 2 * np.pi * defs["tp"]
sat_pulse = pp.make_block_pulse(
    flip_angle=flip_angle_sat,
    duration=defs["tp"],
    system=sys,
)

# calculate b1rms
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
        accum_phase = (
            accum_phase
            + offset * 2 * np.pi * np.sum(np.abs(sat_pulse.signal) > 0) * 1e-6
        ) % (2 * np.pi)
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
print("here")
