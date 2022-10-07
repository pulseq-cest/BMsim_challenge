"""
Script requires "BMCTool" package
can be installed from PyPi using "pip install bmctool"

My environment was:
Python 3.10
  - numpy 1.22.4
  - pandas 1.4.3
  - bmctool 0.4.0
  - pypulseq 1.4.0

Author: Patrick Schuenke
e-mail: patrick.schuenke@ptb.de
date: 2022-10-07
"""
from pathlib import Path

import pandas as pd

from bmctool.bmc_tool import BMCTool
from bmctool.set_params import load_params
from bmctool.utils.eval import plot_z

seq_file = Path(r'\BMsim_challenge\case_4\case_4_create_seq.seq')
config_file = Path(r'\BMsim_challenge\case_4\case_4_5pool_model.yaml')

# load config file
sim_params = load_params(config_file)
sim_params.update_options(par_calc=True)

# create BMCTool object and run simulation
sim = BMCTool(sim_params, seq_file)
sim.run()

# get x,y data for Z-spectrum
offsets, mz = sim.get_zspec()

# create panda DataFrame and copy it to clipboard to be able to paste it in excel
pd_data = pd.DataFrame(mz)
pd_data.to_clipboard(excel=True)

# plot data
plot_z(mz=mz,
       offsets=offsets,
       normalize=True)
