# BMsim challenge - CASE 5

## Pool model

The pool model of case 5 is identical to the [z_phantom_creatine_3T_pH6.4_T22C_bmsim](https://github.com/kherz/pulseq-cest-library/blob/6ffca73282badd2828b86ace383969e9b4276e80/sim-library/WM_3T_default_7pool_bmsim.yaml)
model published in the [pulseq-cest-library](https://github.com/kherz/pulseq-cest-library). It consists of:

- 1 water pool
- 1 CEST pool

### The exact settings are

- water_pool:
  - f: 1.0
  - T1: 3.0
  - T2: 2.0

- cest pool:
  - f: 5.0e-04
  - T1: 1.05
  - T2: 0.1
  - k: 50
  - dw: 1.9

More details and references are given in [case_5_2pool_model.yaml](/case_5/case_5_2pool_model.yaml)

## Preparation scheme

The preparation scheme for case 5 consists of a single sinc-pulse, which has exactly the same settings as the sinc-pulses used in case 6 and case 7.

The preparation settings are:

- pulse shape: Gaussian
- pulse duration: 50 ms
- number of pulses: 1
- total saturation time: 50 ms
- pulse power (B1rms): 1.9962 µT
- offset list: -5:0.1:5 ppm

A MATLAB and a Python script to create a [Pulseq](https://github.com/pulseq/pulseq) seq-file is given in the [subfolder of case 5](/case_5)
  