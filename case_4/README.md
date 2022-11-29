# BMsim challenge - CASE 4

## Pool model:
The pool model of case 4 (and case 3) is similar to the [WM_3T_default_7pool_bmsim](https://github.com/kherz/pulseq-cest-library/blob/6ffca73282badd2828b86ace383969e9b4276e80/sim-library/WM_3T_default_7pool_bmsim.yaml)
model published in the [pulseq-cest-library](https://github.com/kherz/pulseq-cest-library). It consists of:
 - 1 water pool
 - 2 CEST pools
 - 1 NOE pool 
 - 1 Lorentzian shaped MT pool


#### The exact settings are:

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

More details and references are given in [case_4_5pool_model.yaml](/case_4/case_4_5pool_model.yaml)

## Preparation scheme:
The preparation scheme for case 4 is identical to the 
[WASABI_3T_001_3p7uT_1block_5ms](https://github.com/kherz/pulseq-cest-library/tree/22009a462a689e10f407374efc0d63760344519b/seq-library/WASABI_3T_001_3p7uT_1block_5ms)
scheme published in the published in the [pulseq-cest-library](https://github.com/kherz/pulseq-cest-library).

The preparation settings are:
  - pulse shape: block
  - pulse duration: 5 ms
  - pulse power: 3.7 µT
  - post-pulse delay: 6.5 ms (in the seq-file this corresponds to the gradient spoiler duration)
  - offset list: -2:0.05:2 ppm
  - normalization scan at -300 ppm

A MATLAB script to create a [Pulseq](https://github.com/pulseq/pulseq) seq-file is given in the [subfolder of case 4](/case_4)
  
