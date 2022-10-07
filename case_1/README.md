# BMsim challenge - CASE 1

## Pool model:
The pool model of case 1 is identical to the [z_phantom_creatine_3T_pH6.4_T22C_bmsim](https://github.com/kherz/pulseq-cest-library/blob/6ffca73282badd2828b86ace383969e9b4276e80/sim-library/WM_3T_default_7pool_bmsim.yaml)
model published in the [pulseq-cest-library](https://github.com/kherz/pulseq-cest-library). It consists of:
 - 1 water pool
 - 1 CEST pool


#### The exact settings are:

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


More details and references are given in [case_1_2pool_model.yaml](/case_1/case_1_2pool_model.yaml)

## Preparation scheme:
The preparation scheme for case 1 is based on 
[APTw_3T_000_2uT_1block_2s_braintumor](https://github.com/kherz/pulseq-cest-library/blob/22009a462a689e10f407374efc0d63760344519b/seq-library/APTw_3T_000_2uT_1block_2s_braintumor/)
scheme published in the published in the [pulseq-cest-library](https://github.com/kherz/pulseq-cest-library),
but with 30 seconds of saturation to be close to steady-state (10*T1, deviation from steady state <10^-4)

The preparation settings are:
  - pulse shape: block
  - pulse duration: 15 s
  - pulse power: 2 µT
  - offset list: -15:0.1:15 ppm

A MATLAB script to create a [Pulseq](https://github.com/pulseq/pulseq) seq-file is given in the [subfolder of case 1](/case_1)
  
