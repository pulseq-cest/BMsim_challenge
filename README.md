# BMsim challenge
Repository for the Bloch-McConnell simulation (BMsim) challenge

Find the corresponding google sheet at:

https://docs.google.com/spreadsheets/d/1JN7VN-f1ktDrJgokb0FlUFwkH0MWYlPA_jSfnQoFOVc/

Find the .seq and BMsim.yaml files in seq and sim folders, respectively.


## Challenge 1: 7pWM - APTw_3T_000

## Challenge 2: 2p - APTw_3T_000

## Challenge 1: 7pWM - WASABI_3T_001


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

