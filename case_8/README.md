# BMsim challenge - CASE 8

## Pool model

The pool model of case 8 (and case 7) is similar to the [WM_3T_default_7pool_bmsim](https://github.com/kherz/pulseq-cest-library/blob/6ffca73282badd2828b86ace383969e9b4276e80/sim-library/WM_3T_default_7pool_bmsim.yaml) model published in the [pulseq-cest-library](https://github.com/kherz/pulseq-cest-library). It consists of:

- 1 water pool
- 2 CEST pools
- 1 NOE pool
- 1 MT pool

### The exact settings are

- water_pool:
  - f: 1.0
  - T1: 1.0
  - T2: 0.040

- mt_pool
  - f:  0.1351
  - T1: 1.0
  - T2: 4.0e-05
  - k:  30
  - dw: -3.0

- cest pool 1: "amide"
  - f: 0.0009009
  - T1: 1.0
  - T2: 0.1
  - k: 50
  - dw: 3.5

- cest pool 2: "guanidine"
  - f: 0.0009009
  - T1: 1.0
  - T2: 0.1
  - k: 1000
  - dw: 2

- NOE pool:
  - f: 0.0045
  - T1: 1.3
  - T2: 0.005
  - k: 20
  - dw: -3

More details and references are given in [case_8_5pool_model.yaml](/case_8/case_8_5pool_model.yaml)

## Preparation scheme

The preparation scheme for case 8 is inspired by [WASABI_3T_001_3p7uT_1block_5ms](https://github.com/kherz/pulseq-cest-library/tree/master/seq-library/WASABI_3T_001_3p7uT_1block_5ms)
published in the [pulseq-cest-library](https://github.com/kherz/pulseq-cest-library).

The preparation settings are:

- pulse shape: block
- pulse duration: 5 ms
- number of pulses: 2
- interpulse delay: 100 µs
- number of interpulse delays: 1
- total saturation time: 0.0101 s
- pulse power: 3.7 µT
- offset list: -2:0.05:2 ppm

A MATLAB and a Python script to create a [Pulseq](https://github.com/pulseq/pulseq) seq-file is given in the [subfolder of case 8](/case_8)
  