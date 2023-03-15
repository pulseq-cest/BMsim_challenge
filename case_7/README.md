# BMsim challenge - CASE 7

## Pool model

The pool model of case 7 (and case 8) is similar to the [WM_3T_default_7pool_bmsim](https://github.com/kherz/pulseq-cest-library/blob/6ffca73282badd2828b86ace383969e9b4276e80/sim-library/WM_3T_default_7pool_bmsim.yaml) model published in the [pulseq-cest-library](https://github.com/kherz/pulseq-cest-library). It consists of:

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

More details and references are given in [case_7_5pool_model.yaml](/case_7/case_7_5pool_model.yaml)

## Preparation scheme

The preparation scheme for case 7 is based on [APTw_3T_001_2uT_36SincGauss_DC90_2s_braintumor](https://github.com/kherz/pulseq-cest-library/tree/master/seq-library/APTw_3T_001_2uT_36SincGauss_DC90_2s_braintumor) published in the [pulseq-cest-library](https://github.com/kherz/pulseq-cest-library).

The preparation settings are:

- pulse shape: Gaussian
- pulse duration: 50 ms
- number of pulses: 36
- interpulse delay: 5 ms
- number of interpulse delays: 35
- total saturation time: 1.975 s
- pulse power (B1rms): 1.99620497 µT
- offset list: -15:0.1:15 ppm

A MATLAB and a Python script to create a [Pulseq](https://github.com/pulseq/pulseq) seq-file is given in the [subfolder of case 7](/case_7)
  