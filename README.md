# BMsim challenge
Repository for the Bloch-McConnell simulation (BMsim) challenge

Find the corresponding google sheet at:

https://docs.google.com/spreadsheets/d/1JN7VN-f1ktDrJgokb0FlUFwkH0MWYlPA_jSfnQoFOVc/

Find the .seq and BMsim.yaml files in seq and sim folders, respectively.


## Challenge 1: 7pWM - APTw_3T_000
Pool model WM_default:	https://github.com/kherz/pulseq-cest-library/blob/6ffca73282badd2828b86ace383969e9b4276e80/sim-library/WM_3T_default_7pool_bmsim.yaml

Prep. sequence APTw_3T_000: https://github.com/kherz/pulseq-cest-library/blob/22009a462a689e10f407374efc0d63760344519b/seq-library/APTw_3T_000_2uT_1block_2s_braintumor/	 	

We assume fully relaxed initial magnetization Zi=1, and a cw saturation period of 2s and 2µT.

Zi=1, tsat=2 s, B1= 2 µT cw;		
offset list: -15:0.25:15 ppm		
gamma	:	42.576400 MHz/T
FREQ(3T) : 	127.7292	MHz

## Challenge 2: 2p - APTw_3T_000
Pool model 2 pool creatine:	https://github.com/kherz/pulseq-cest-library/blob/22009a462a689e10f407374efc0d63760344519b/sim-library/z_phantom_creatine_3T_pH6.4_T22C_bmsim.yaml

Prep. sequence APTw_3T_000: https://github.com/kherz/pulseq-cest-library/blob/22009a462a689e10f407374efc0d63760344519b/seq-library/APTw_3T_000_2uT_1block_2s_braintumor/	 	

We assume fully relaxed initial magnetization Zi=1, and a cw saturation period of 2s and 2µT.

Zi=1, tsat=2 s, B1= 2 µT cw;		
offset list: -15:0.25:15 ppm
gamma	:	42.576400 MHz/T
FREQ(3T) : 	127.7292	MHz

## Challenge 1: 7pWM - WASABI_3T_001
Pool model WM_default:	https://github.com/kherz/pulseq-cest-library/blob/6ffca73282badd2828b86ace383969e9b4276e80/sim-library/WM_3T_default_7pool_bmsim.yaml

Prep. sequence WASABI_3T_001: https://github.com/kherz/pulseq-cest-library/tree/22009a462a689e10f407374efc0d63760344519b/seq-library/WASABI_3T_001_3p7uT_1block_5ms

We assume fully relaxed initial magnetization Zi=1, and a cw saturation period of 2s and 2µT.

Zi=1, tsat=0.05s, B1= 3.7µT cw;
offset list: -2: 1/6 :2 ppm
gamma	:	42.576400 MHz/T
FREQ(3T) : 	127.7292	MHz

## General simulation remarks

### gamma
Already a different gamma can yield deviations in simulations.
Thus we define our used value as the shielded gamma/2pi value in Hz with four digits = **42.5764 MHz/T**

Dividing the value of 
https://physics.nist.gov/cgi-bin/cuu/Value?gammapp 
by 2pi yields

42.5763 84750950949004433240733872 MHz/T 

rounded to 4 digits yields **42.5764 MHz/T**

We use this value everywhere in teh simulations directly and multiply it with 2pi if needed.

