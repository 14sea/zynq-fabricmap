#!/usr/bin/env python3
"""Mutants of the B4 carrier v2 RTL and of its host modules, run HERMETICALLY: the files the benches and tests read are
copied to a temporary directory, one mutation applied there, the relevant bench scenarios / test modules run from
that copy, and a mutant counts as KILLED only when the run REPORTS a failure (TB_FAIL / FAILED with Ran N > 0 — an
EDIT-MISS, a compile error or a run that did not happen is not a kill: feedback-failure-looks-like-success).
Nothing under the repository is modified. Output: mutants.json / mutants.txt beside this script."""
import json, pathlib, re, shutil, subprocess, sys, tempfile
R = pathlib.Path('/home/test/zynq_fabricmap'); HERE = pathlib.Path(__file__).resolve().parent
SUBTREE = ['rtl/b4', 'rtl/b1/p3_siphash.v', 'tb/b4', 'sim/b4/run.sh', 'vivado/carrier/carrier_axi3_lite.v', 'host/b4carrier_regmap.py', 'host/b4carrier_manifest.py',
           'host/b4carrier_records.py', 'host/claimb_r1p_instrument.py', 'tests/test_b4carrier_regmap.py', 'tests/test_b4carrier_records.py',
           'b4/host/b4_ff_model.py', 'b4/host/b4_ff_hypothesis.py', 'b4/host/b4_ff_mapping.py', 'b4/hypothesis', 'gate_runs/run_2026_08_05_ff/certificate.json',
           'evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/probe_report.json', 'docs/ff_latch_probe.md',
           'manifests/claimb_round1prime_manifest.json', 'manifests/claimb_round1prime_instrument_pins.json']
MUTANTS = [
 # id, file, old, new, kind, what must fail
 ('M01', 'rtl/b4/b4_engine.v', 'else if (op_any && (!armed || recovery_required)) begin', 'else if (op_any && (1\'b0)) begin', 'bench', ['fault_not_armed']),
 ('M02', 'rtl/b4/b4_gate.v', 'nonce_we <= 1\'b1; nonce_d <= xorshift(nonce);      // consumed by THIS attempt whatever the outcome', '// MUTANT: the nonce does not step', 'bench', ['flow']),
 ('M03', 'rtl/b4/b4_engine.v', 'else if (!ce_uniform || !sr_uniform) refuse(F_NOT_REALISABLE);', '// MUTANT: no realisability check', 'bench', ['fault_realisable']),
 ('M04', 'rtl/b4/b4_engine.v', "else if (cnt == ASSERT_DELAY[7:0] - 8'd1) begin fire <= 1'b1; state <= S_IDLE; end", "else if (cnt == ASSERT_DELAY[7:0] - 8'd1) begin fire <= 1'b0; state <= S_IDLE; end", 'bench', ['flow', 'a5']),
 ('M05', 'rtl/b4/b4_engine.v', "slice_ce <= cmd[8]; slice_sr <= cmd[16]; state <= S_STEP_DATA;", "slice_d <= cmd[7:0]; slice_ce <= cmd[8]; slice_sr <= cmd[16]; cnt <= 8'd0; state <= S_STEP_SETTLE;", 'bench', ['flow']),
 ('M06', 'rtl/b4/b4_core.v', "parameter [31:0]  VARIANT_WORD  = 32'h42340001,", "parameter [31:0]  VARIANT_WORD  = 32'h42310001,", 'bench', ['regs']),
 ('M07', 'rtl/b4/b4_gate.v', "if (arm_strobe && !busy && !recovery_required && (armed || (arm_a5 != injection_open))) begin", "if (1'b0) begin", 'bench', ['fault_double_arm', 'a5_wrong_context']),
 ('M08', 'rtl/b4/b4_engine.v', "if (!init_done || cleanup_done) refuse(F_SEQUENCE);\n                    else if (!ce_uniform", "if (1'b0) refuse(F_SEQUENCE);\n                    else if (!ce_uniform", 'bench', ['fault_sequence']),
 ('M09', 'rtl/b4/b4_engine.v', "flags_we <= 1'b1; flags_d <= 10'b0010000000;             // injection_open; the inputs stay as they are", "flags_we <= 1'b1; flags_d <= 10'd0;", 'bench', ['a5']),
 ('M10', 'rtl/b4/b4_engine.v', "write_sample(5'd1, 32'd0);", "slot_we <= 1'b1; slot_a_eng <= 5'd1; slot_d <= ~q_live; slot_in_d <= 32'd0;", 'bench', ['flow']),
 ('M11', 'rtl/b4/b4_gate.v', 'if (sh_tag == tag_in) begin', "if (1'b1) begin", 'bench', ['fault_unsigned']),
 ('M12', 'rtl/b4/b4_engine.v', "if (slice_clk) begin flags_we <= 1'b1; flags_d <= flags | 10'b0000010000; end   // cleanup_edge: a falling edge\n                    slice_clk <= 1'b0;", "if (slice_clk) begin flags_we <= 1'b1; flags_d <= flags | 10'b0000010000; end\n                    slice_clk <= slice_clk;", 'bench', ['flow']),
 # the repair's own mutants
 ('M13', 'rtl/b4/b4_engine.v', "if (!restore_done) refuse(F_SEQUENCE);", "if (1'b0) refuse(F_SEQUENCE);", 'bench', ['open_close_refused', 'p9']),
 ('M14', 'rtl/b4/b4_engine.v', "cmd <= step_in; step_done <= 1'b0; state <= S_STEP_CTRL;   // the accepted command, latched", "step_done <= 1'b0; state <= S_STEP_CTRL;", 'bench', ['step_atomic']),
 ('M15', 'rtl/b4/b4_axil.v', "wire ctrl_accept = ctrl_one && ctrl_known && ctrl_a5_ok && !engine_busy && !gate_busy;", "wire ctrl_accept = ctrl_one && ctrl_known && ctrl_a5_ok;", 'bench', ['busy_refused']),
 ('M16', 'rtl/b4/b4_axil.v', "wire ctrl_one = (ctrl_ops != 9'd0) && ((ctrl_ops & (ctrl_ops - 9'd1)) == 9'd0);", "wire ctrl_one = (ctrl_ops != 9'd0);", 'bench', ['regs']),
 ('M17', 'rtl/b4/b4_engine.v', "if (!bus_quiet) cnt <= 8'd0;\n                else if", "if (1'b0) cnt <= 8'd0;\n                else if", 'bench', ['backpressure']),
 ('M18', 'rtl/b4/b4_axi_gate.v', "assign s_arvalid = m_arvalid && !mask;     assign m_arready = s_arready && !mask;", "assign s_arvalid = m_arvalid;  assign m_arready = s_arready;", 'bench', ['read_at_launch']),   # a first version removed the AW masking and survived backpressure / read_during_window: those pass without the stall; read_at_launch is the scenario the stall exists for
 ('M19', 'rtl/b4/b4_engine.v', "if (restoring) begin\n                        base_we <= 1'b1; base_d <= q_live;", "if (restoring) begin\n                        base_we <= 1'b1; base_d <= ~q_live;", 'bench', ['p9_ok', 'flow']),
 ('M20', 'rtl/b4/b4_engine.v', "assign idle = (state == S_IDLE) && !armed && !injection_open && (in_live[24:0] == 25'd0);", "assign idle = (state == S_IDLE) && !armed;", 'bench', ['a5', 'open_close_refused']),
 ('M21', 'rtl/b4/b4_engine.v', "wire [3:0] pulse_d = fire ? ((4'd1 << PULSE) - 4'd1) : (pulse_cnt >> 1);", "wire [3:0] pulse_d = fire ? 4'd1 : (pulse_cnt >> 1);", 'unisim', ['unisim']),
 ('H01', 'host/b4carrier_records.py', "    extra = set(obj) - set(schema)\n", "    extra = set()\n", 'test', ['tests.test_b4carrier_records']),
 ('H02', 'host/b4carrier_records.py', "        for ph in PHASES[: PHASES.index(phase)]:\n            schema.update(O_PHASE[ph])                      # completed phases: required", "        for ph in PHASES[: PHASES.index(phase)]:\n            pass", 'test', ['tests.test_b4carrier_records']),
 ('H03', 'host/b4carrier_regmap.py', 'APP_READABLE = frozenset({STATUS,', 'APP_READABLE = frozenset({0x2240, STATUS,', 'test', ['tests.test_b4carrier_regmap']),
 ('H04', 'host/b4carrier_records.py', "def _t_cells(v) -> bool:\n    return isinstance(v, list) and len(v) == 8 and all(_is_int(c) and c in (0, 1) for c in v)", "def _t_cells(v) -> bool:\n    return isinstance(v, list) and len(v) == 8 and all(c in (0, 1, None) for c in v)", 'test', ['tests.test_b4carrier_records']),
 ('H05', 'host/b4carrier_regmap.py', 'return ce in (0x00, 0xFF) and sr in (0x00, 0xFF)', 'return True', 'test', ['tests.test_b4carrier_regmap']),
 ('H06', 'host/b4carrier_records.py', "    hit = _keys_at_all_levels(o) & DENY\n", "    hit = set()\n", 'test', ['tests.test_b4carrier_records']),
 ('H07', 'host/b4carrier_records.py', "    if status == \"closed\" and x[\"idle_status\"] != 1:", "    if False:", 'test', ['tests.test_b4carrier_records']),
 ('H08', 'host/b4carrier_records.py', "    tf = validate_task(task, len(o[\"steps\"]))\n    if tf:\n        raise RecordRefusal(\"; \".join(tf))", "    tf = []", 'test', ['tests.test_b4carrier_records']),
 ('H09', 'host/b4carrier_records.py', "        if len(set(rb)) > 1:", "        if False:", 'test', ['tests.test_b4carrier_records']),
 # round 3 (the owner's HOLD on aaf15ba): the burst drain, the P6 seal, the completion witnesses, the trusted binding, the schema rules, the pre-init cleanup
 ('M22', 'rtl/b4/b4_axi_gate.v', "wire mask_w  = mask && !wr_out;           // the beats of an accepted write address drain", "wire mask_w  = mask;", 'axi3', ['axi3']),
 ('M23', 'rtl/b4/b4_core.v', ".enable(LITE_STALL[0]),", ".enable(1'b1),", 'axi3', ['axi3']),
 ('M24', 'rtl/b4/b4_engine.v', "else if (in_live[24:0] != 25'd0) begin\n                        // the inputs are held", "else if (1'b0) begin\n                        // the inputs are held", 'bench', ['a5']),
 ('M25', 'rtl/b4/b4_axil.v', "s_rdata <= {4'd0, pre_init_cleanup, stall,", "s_rdata <= {4'd0, 1'b0, stall,", 'bench', ['a5']),
 ('H11', 'host/b4carrier_records.py', "    evs = evs[:boundary]                                  # the terminal boundary: nothing after it enters O\n", "    evs = list(evs)\n", 'test', ['tests.test_b4carrier_records']),
 ('H12', 'host/b4carrier_records.py', "    after = evs[i + 1:]\n    faults = [e for e in after", "    return True\n    after = evs[i + 1:]\n    faults = [e for e in after", 'test', ['tests.test_b4carrier_records']),
 ('H13', 'host/b4carrier_records.py', "        if x[\"seq\"] != o[\"seq\"]:", "        if False:", 'test', ['tests.test_b4carrier_records']),
 ('H14', 'host/b4carrier_records.py', "            if c[\"clock_before\"] != last_clock:", "            if False:", 'test', ['tests.test_b4carrier_records']),
 ('H15', 'host/b4carrier_records.py', "\"clock_after\": _t_int(0, 0), \"edge\": _t_enum(\"falling\", None), \"ce\": _t_int(0, 0), \"sr\": _t_int(0, 0), \"d\": _t_int(0, 0)", "\"clock_after\": _t_enum(0), \"edge\": _t_enum(\"falling\", None), \"ce\": _t_enum(0), \"sr\": _t_enum(0), \"d\": _t_enum(0)", 'test', ['tests.test_b4carrier_records']),
 ('H16', 'host/b4carrier_records.py', "        if so[\"instrument\"] != ctx.get(\"instrument\"):", "        if False:", 'test', ['tests.test_b4carrier_records']),
 ('H17', 'host/b4carrier_records.py', "                    if fitness(o, task)[\"fitness\"] != fr[\"fitness\"]:", "                    if False:", 'test', ['tests.test_b4carrier_records']),
 ('H18', 'host/b4carrier_records.py', "        if not isinstance(r, dict) or not isinstance(r.get(\"o\"), dict) or not isinstance(r.get(\"ctx\"), dict):", "        if False:", 'test', ['tests.test_b4carrier_records']),
 ('H19', 'host/b4carrier_records.py', "        if ph in (\"P1\", \"P2\") and (steps or \"initial\" in o or sr is not None):", "        if False:", 'test', ['tests.test_b4carrier_records']),
 ('H20', 'host/b4carrier_records.py', "        if held != pic:", "        if False:", 'test', ['tests.test_b4carrier_records']),
 ('H21', 'host/b4carrier_records.py', "        if ctx.get(\"predecessor_seq\") is not None and o[\"predecessor\"][\"seq\"] != ctx[\"predecessor_seq\"]:", "        if False:", 'test', ['tests.test_b4carrier_records']),
 # round 4 (the owner's HOLD on ce3ca6d): the W-first admission, the acquisition boundary, the two references, the shape-first chain
 ('M26', 'rtl/b4/b4_axi_gate.v', "wire mask_w  = mask && !wr_out;           // the beats of an accepted write address drain", "wire mask_w  = 1'b0;", 'bench', ['w_first']),
 ('M27', 'rtl/b4/b4_axi_gate.v', "assign quiet = !wr_out && !w_early && !rd_out && !bvalid && !rvalid;", "assign quiet = !wr_out && !rd_out && !bvalid && !rvalid;", 'bench', ['w_first_early']),
 ('M28', 'rtl/b4/b4_axi_gate.v', "wire mask_aw = mask && !w_early;          // the AW of a W already accepted is admitted", "wire mask_aw = mask;", 'bench', ['w_first_early']),
 ('H22', 'host/b4carrier_records.py', "            if init_done and step_idx >= n_declared - 1:\n                return i, \"sealed\"", "            if True:\n                return i, \"sealed\"", 'test', ['tests.test_b4carrier_records']),
 ('H23', 'host/b4carrier_records.py', "                    return j + 1, \"premature_refused\"", "                    return i, \"premature_refused\"", 'test', ['tests.test_b4carrier_records']),
 ('H24', 'host/b4carrier_records.py', "    if how != \"sealed\":\n        raise RecordRefusal(f\"no transaction close", "    if False:\n        raise RecordRefusal(f\"no transaction close", 'test', ['tests.test_b4carrier_records']),
 ('H25', 'host/b4carrier_records.py', "        elif so[\"base_frames_reference_sha256\"] != ctx[\"loaded_frames_reference_sha256\"]:", "        elif so[\"base_frames_reference_sha256\"] != ctx.get(\"base_readback_sha256\"):", 'test', ['tests.test_b4carrier_records']),
 ('H26', 'host/b4carrier_records.py', "        if shape:\n            f += [f\"chain[{i}]: {m}\" for m in shape]", "        if False:\n            f += [f\"chain[{i}]: {m}\" for m in shape]", 'test', ['tests.test_b4carrier_records']),
 ('H27', 'host/b4carrier_records.py', "    if f:\n        return f + [\"chain: the session-opening record is malformed; no transaction can be bound to it\"]", "    if False:\n        return f", 'test', ['tests.test_b4carrier_records']),
 ('H28', 'host/b4carrier_records.py', "            if not _hex(ctx.get(\"base_readback_sha256\"), 64):", "            if False:", 'test', ['tests.test_b4carrier_records']),
 ('H10', 'host/b4carrier_records.py', "    raise RecordRefusal(\"the transaction is not closed: no completed CLOSE / CLOSE_INJECTION and no fault after the observation\")", "    return {\"schema\": SCHEMA_X, \"schema_version\": VERSION, \"observation_sha256\": osha, \"seq\": seq, \"idle_status\": 0, \"status\": \"injection_open\"}", 'test', ['tests.test_b4carrier_records']),
]
# optional: `run_mutants.py <tag> <id,id,...>` runs only those mutants and writes mutants_<tag>.json / .txt (a repair round's
# affected subset); without arguments the whole battery runs and writes mutants.json / mutants.txt
TAG = sys.argv[1] if len(sys.argv) > 2 else None
if TAG:
    ONLY = set(sys.argv[2].split(','))
    unknown = ONLY - {m[0] for m in MUTANTS}
    if unknown: sys.exit(f'unknown mutant ids: {sorted(unknown)}')
    MUTANTS = [m for m in MUTANTS if m[0] in ONLY]
results = []
with tempfile.TemporaryDirectory(prefix='b4carrier_mutants_') as td:
    T = pathlib.Path(td)
    for rel in SUBTREE:
        src = R / rel; dst = T / rel; dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir(): shutil.copytree(src, dst, dirs_exist_ok=True)
        else: shutil.copy2(src, dst)
    (T / 'sim/b4/out').mkdir(parents=True, exist_ok=True)
    # the host tests read the bench TRACES (sim/b4/out/*.jsonl), produced by the unmutated benches: copied once from the
    # repository's fresh full run (sim/b4/run.sh) so a host mutant does not re-run the whole suite; the traces are inputs,
    # never judged, and no host mutant can change them (the RTL mutants run the benches themselves)
    for j in (R / 'sim/b4/out').glob('*.jsonl'):
        shutil.copy2(j, T / 'sim/b4/out' / j.name)
    # the runner must run from the copy: it cds to its own ../..
    for mid, rel, old, new, kind, targets in MUTANTS:
        f = T / rel; text = f.read_text(); n = text.count(old)
        if n != 1:
            results.append({'id': mid, 'file': rel, 'status': 'EDIT-MISS', 'occurrences': n}); continue
        f.write_text(text.replace(old, new))
        try:
            if kind == 'unisim':   # the vendor bench with the RTL core and glbl (the LUTRAM pulse)
                p = subprocess.run(['bash', '-c', f'cd {T} && python3 -B tb/b4/gen_b4_fixture.py >/dev/null && iverilog -g2012 -I tb/b4 -o sim/b4/out/mu.vvp -y /home/test/Xilinx/2025.2/data/verilog/src/unisims /home/test/Xilinx/2025.2/data/verilog/src/glbl.v rtl/b1/p3_siphash.v rtl/b4/b4_gsr_reg.v rtl/b4/b4_slot_ram.v rtl/b4/b4_gsr_ram32.v rtl/b4/b4_axi_gate.v rtl/b4/b4_axil.v rtl/b4/b4_gate.v rtl/b4/b4_engine.v rtl/b4/b4_core.v rtl/b4/b4_target_slice.v tb/b4/tb_b4_unisim.v && vvp -N sim/b4/out/mu.vvp 2>&1 | grep -E "^TB_" | tail -1'], capture_output=True, text=True, timeout=600)
                outs = [('unisim', p.stdout.strip(), p.returncode)]
                ran = outs[0][1].startswith('TB_'); killed = ran and outs[0][1].startswith('TB_FAIL')
                results.append({'id': mid, 'file': rel, 'status': 'KILLED' if killed else ('SURVIVED' if ran else 'NOT-RUN'), 'runs': outs})
            elif kind == 'axi3':   # the PS path through the pinned shim (the burst cases)
                p = subprocess.run(['bash', '-c', f'cd {T} && python3 -B tb/b4/gen_b4_fixture.py >/dev/null && iverilog -g2012 -I tb/b4 -o sim/b4/out/ma.vvp -y /home/test/Xilinx/2025.2/data/verilog/src/unisims rtl/b1/p3_siphash.v rtl/b4/b4_gsr_reg.v rtl/b4/b4_slot_ram.v rtl/b4/b4_gsr_ram32.v rtl/b4/b4_axi_gate.v rtl/b4/b4_axil.v rtl/b4/b4_gate.v rtl/b4/b4_engine.v rtl/b4/b4_core.v vivado/carrier/carrier_axi3_lite.v tb/b4/b4_target_slice_model.v tb/b4/tb_b4_axi3.v && timeout 600 vvp -N sim/b4/out/ma.vvp 2>&1 | grep -E "^TB_" | tail -1'], capture_output=True, text=True, timeout=900)
                outs = [('axi3', p.stdout.strip(), p.returncode)]
                ran = outs[0][1].startswith('TB_'); killed = ran and outs[0][1].startswith('TB_FAIL')
                results.append({'id': mid, 'file': rel, 'status': 'KILLED' if killed else ('SURVIVED' if ran else 'NOT-RUN'), 'runs': outs})
            elif kind == 'bench':
                outs = []
                for s in targets:
                    p = subprocess.run(['bash', '-c', f'cd {T} && python3 -B tb/b4/gen_b4_fixture.py >/dev/null && iverilog -g2012 -I tb/b4 -o sim/b4/out/m.vvp -y /home/test/Xilinx/2025.2/data/verilog/src/unisims rtl/b1/p3_siphash.v rtl/b4/b4_gsr_reg.v rtl/b4/b4_slot_ram.v rtl/b4/b4_gsr_ram32.v rtl/b4/b4_axi_gate.v rtl/b4/b4_axil.v rtl/b4/b4_gate.v rtl/b4/b4_engine.v rtl/b4/b4_core.v tb/b4/b4_target_slice_model.v tb/b4/tb_b4_core.v && vvp -N sim/b4/out/m.vvp +SCENARIO={s} 2>&1 | grep -E "^TB_" | tail -1'], capture_output=True, text=True, timeout=600)
                    outs.append((s, p.stdout.strip(), p.returncode))
                ran = all(o[1].startswith('TB_') for o in outs)
                killed = ran and any(o[1].startswith('TB_FAIL') for o in outs)
                results.append({'id': mid, 'file': rel, 'status': 'KILLED' if killed else ('SURVIVED' if ran else 'NOT-RUN'), 'runs': outs})
            else:
                outs = []
                for mod in targets:
                    p = subprocess.run(['python3', '-B', '-m', 'unittest', mod], cwd=T, capture_output=True, text=True, timeout=600)
                    tail = p.stderr.strip().splitlines()[-3:]
                    m = re.search(r'Ran (\d+) tests', p.stderr); ran_n = int(m.group(1)) if m else 0
                    outs.append((mod, ran_n, 'FAILED' in p.stderr, p.returncode, tail))
                ran = all(o[1] > 0 for o in outs)
                killed = ran and any(o[2] for o in outs)
                results.append({'id': mid, 'file': rel, 'status': 'KILLED' if killed else ('SURVIVED' if ran else 'NOT-RUN'), 'runs': outs})
        finally:
            f.write_text(text)
summary = {s: sum(1 for r in results if r['status'] == s) for s in ('KILLED', 'SURVIVED', 'EDIT-MISS', 'NOT-RUN')}
OUTN = f'mutants_{TAG}' if TAG else 'mutants'
(HERE / f'{OUTN}.json').write_text(json.dumps({'results': results, 'summary': summary}, indent=1) + '\n')
lines = [f"{r['id']:4} {r['status']:9} {r['file']}" + ('' if r['status'] == 'EDIT-MISS' else '  ' + '; '.join(str(x[:2]) for x in r.get('runs', []))) for r in results]
(HERE / f'{OUTN}.txt').write_text('\n'.join(lines) + f"\nsummary {summary}\n")
print('\n'.join(lines)); print('summary', summary)
