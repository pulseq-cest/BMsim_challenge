lib_path='D:\root\LABLOG\FAU\MRIlab\SIM\pulseq-cest-library';
seq_path=[lib_path '/seq-library/'];
sim_path=[lib_path '/sim-library/'];


%% 1
figure('Name','APTw_SS Cr');
seq_filename=fullfile(pwd,'../case_1/.seq')
seq = mr.Sequence;  seq.read(seq_filename);
offsets_ppm = seq.definitions('offsets_ppm'); % offsets
m0_offset = seq.definitions('M0_offset');     % m0 offset frequency
M_z = simulate_pulseqcest(seq_filename,[sim_path 'WM_3T_default_7pool_bmsim.yaml']);
plotSimulationResults(M_z,offsets_ppm,m0_offset);

legend(shortID, 'Interpreter', 'none');

%% 2
figure('Name','APTw_000 Cr');
seq_filename=fullfile(seq_path,'/APTw_3T_000_2uT_1block_2s_braintumor/APTw_3T_000_2uT_1block_2s_braintumor.seq')
seq = mr.Sequence;  seq.read(seq_filename);
offsets_ppm = seq.definitions('offsets_ppm'); % offsets
m0_offset = seq.definitions('M0_offset');     % m0 offset frequency
M_z = simulate_pulseqcest(seq_filename,[sim_path 'z_phantom_creatine_3T_pH6.4_T22C_bmsim.yaml']);
plotSimulationResults(M_z,offsets_ppm,m0_offset);

legend(shortID, 'Interpreter', 'none');

%% 3
figure('Name','WASABI WM');
seq_filename=fullfile(lib_path,'/sandbox/002_BMsim_challenge/WASABI_3T_001_3p7uT_1block_5ms.seq')
seq = mr.Sequence;  seq.read(seq_filename);
offsets_ppm = seq.definitions('offsets_ppm'); % offsets
m0_offset = seq.definitions('M0_offset');     % m0 offset frequency
M_z = simulate_pulseqcest(seq_filename,[sim_path 'WM_3T_default_7pool_bmsim.yaml']);
plotSimulationResults(M_z,offsets_ppm,m0_offset);

legend(shortID, 'Interpreter', 'none');


