%% APTw_3T_003_2uT_8block_DC95_834ms_braintumor.seq
% Creates a sequence file for an APTw protocol with block pulses, ~95% DC and t_sat of 833 ms:
%
% Kai Herz 2020
% kai.herz@tuebingen.mpg.de

% author name for sequence file
author = 'Kai Herz';

%% get id of generation file
if contains(mfilename, 'LiveEditorEvaluationHelperESectionEval')
    [~, seqid] = fileparts(matlab.desktop.editor.getActiveFilename);
else
    [~, seqid] = fileparts(which(mfilename));
end

%% sequence definitions
% everything in seq_defs gets written as definition in .seq-file
seq_defs.n_pulses      = 8               ; % number of pulses
seq_defs.tp            = 100e-3          ; % pulse duration [s]
seq_defs.td            = [1e-3 10e-3]    ; % interpulse delay [s]
seq_defs.Trec          = 3.5             ; % recovery time [s]
seq_defs.Trec_M0       = 3.5             ; % recovery time before M0 [s]
seq_defs.M0_offset     = -1560           ; % m0 offset [ppm]
seq_defs.DCsat         = (2*seq_defs.tp)/(2*seq_defs.tp+sum(seq_defs.td)); % duty cycle
seq_defs.offsets_ppm   = [seq_defs.M0_offset -4:0.25:4]; % offset vector [ppm]
seq_defs.num_meas      = numel(seq_defs.offsets_ppm)   ; % number of repetition
seq_defs.Tsat          = seq_defs.n_pulses/2*(seq_defs.tp+seq_defs.td(1)) + ...
                         seq_defs.n_pulses/2*(seq_defs.tp+seq_defs.td(2)) - seq_defs.td(2);  % saturation time [s]
seq_defs.B0            = 3               ; % B0 [T]
seq_defs.seq_id_string = seqid           ; % unique seq id


%% get info from struct
offsets_ppm = seq_defs.offsets_ppm; % [ppm]
Trec        = seq_defs.Trec;        % recovery time between scans [s]
Trec_M0     = seq_defs.Trec_M0;     % recovery time before m0 scan [s]
tp          = seq_defs.tp;          % sat pulse duration [s]
td          = seq_defs.td;          % delay between pulses [s]
n_pulses    = seq_defs.n_pulses;    % number of sat pulses per measurement. if DC changes use: n_pulses = round(2/(t_p+t_d))
B0          = seq_defs.B0;          % B0 [T]
B1pa        = 2;  % mean sat pulse b1 [uT]
spoiling    = 1;     % 0=no spoiling, 1=before readout, Gradient in x,y,z

seq_filename = strcat(seq_defs.seq_id_string,'.seq'); % filename

%% scanner limits
% see pulseq doc for more ino
seq = SequenceSBB(getScannerLimits());

%% create scanner events
% satpulse
gyroRatio_hz  = 42.5764;                  % for H [Hz/uT]
gyroRatio_rad = gyroRatio_hz*2*pi;        % [rad/uT]
fa_sat        = B1pa*gyroRatio_rad*tp; % flip angle of sat pulse
% create pulseq saturation pulse object
satPulse      = mr.makeBlockPulse(fa_sat, 'Duration', tp, 'system', seq.sys);

[B1cwpe,B1cwae,B1cwae_pure,alpha]= calculatePowerEquivalents(satPulse,tp,sum(td)/2,1,gyroRatio_hz);
seq_defs.B1cwpe = B1cwpe;


%% loop through zspec offsets
offsets_Hz = offsets_ppm*gyroRatio_hz*B0;

% loop through offsets and set pulses and delays
for currentOffset = offsets_Hz
    if currentOffset == seq_defs.M0_offset*gyroRatio_hz*B0
        if Trec_M0 > 0
            seq.addBlock(mr.makeDelay(Trec_M0));
        end
    else
        if Trec > 0
            seq.addBlock(mr.makeDelay(Trec)); % recovery time
        end
    end
    satPulse.freqOffset = currentOffset; % set freuqncy offset of the pulse
    accumPhase=0;
    for np = 1:n_pulses
        satPulse.phaseOffset = mod(accumPhase,2*pi); % set accumulated pahse from previous rf pulse
        seq.addBlock(satPulse) % add sat pulse
        % calc phase for next rf pulse
        accumPhase = mod(accumPhase + currentOffset*2*pi*(numel(find(abs(satPulse.signal)>0))*1e-6),2*pi);
        
        if np < n_pulses % delay between pulses
            if mod(np,2) == 0
                seq.addBlock(mr.makeDelay(td(2)));
            else
                seq.addBlock(mr.makeDelay(td(1))); % add delay
            end
        end
    end
    if spoiling % spoiling before readout
        seq.addSpoilerGradients();
    end
    seq.addPseudoADCBlock(); % readout trigger event
end


%% write definitions
def_fields = fieldnames(seq_defs);
for n_id = 1:numel(def_fields)
    seq.setDefinition(def_fields{n_id}, seq_defs.(def_fields{n_id}));
end
seq.write(seq_filename, author);

%% write sequence
seq.write(seq_filename);

%% plot
saveSaturationPhasePlot(seq_filename);

%% call standard sim
M_z = simulate_pulseqcest(seq_filename,'../../sim-library/WM_3T_default_7pool_bmsim.yaml');

%% plot
plotSimulationResults(M_z,offsets_ppm, seq_defs.M0_offset);


