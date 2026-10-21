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
 ('M09', 'rtl/b4/b4_engine.v', "flags_we <= 1'b1; flags_d <= 9'b010000000;             // injection_open; the inputs stay as they are", "flags_we <= 1'b1; flags_d <= 9'd0;", 'bench', ['a5']),
 ('M10', 'rtl/b4/b4_engine.v', "write_sample(5'd1, 32'd0);", "slot_we <= 1'b1; slot_a_eng <= 5'd1; slot_d <= ~q_live; slot_in_d <= 32'd0;", 'bench', ['flow']),
 ('M11', 'rtl/b4/b4_gate.v', 'if (sh_tag == tag_in) begin', "if (1'b1) begin", 'bench', ['fault_unsigned']),
 ('M12', 'rtl/b4/b4_engine.v', "if (slice_clk) begin flags_we <= 1'b1; flags_d <= flags | 9'b000010000; end   // cleanup_edge: a falling edge\n                    slice_clk <= 1'b0;", "if (slice_clk) begin flags_we <= 1'b1; flags_d <= flags | 9'b000010000; end\n                    slice_clk <= slice_clk;", 'bench', ['flow']),
 # the repair's own mutants
 ('M13', 'rtl/b4/b4_engine.v', "if (!restore_done) refuse(F_SEQUENCE);", "if (1'b0) refuse(F_SEQUENCE);", 'bench', ['open_close_refused', 'p9']),
 ('M14', 'rtl/b4/b4_engine.v', "cmd <= step_in; step_done <= 1'b0; state <= S_STEP_CTRL;   // the accepted command, latched", "step_done <= 1'b0; state <= S_STEP_CTRL;", 'bench', ['step_atomic']),
 ('M15', 'rtl/b4/b4_axil.v', "wire ctrl_accept = ctrl_one && ctrl_known && ctrl_a5_ok && !engine_busy && !gate_busy;", "wire ctrl_accept = ctrl_one && ctrl_known && ctrl_a5_ok;", 'bench', ['busy_refused']),
 ('M16', 'rtl/b4/b4_axil.v', "wire ctrl_one = (ctrl_ops != 9'd0) && ((ctrl_ops & (ctrl_ops - 9'd1)) == 9'd0);", "wire ctrl_one = (ctrl_ops != 9'd0);", 'bench', ['regs']),
 ('M17', 'rtl/b4/b4_engine.v', "if (!bus_quiet) cnt <= 8'd0;\n                else if", "if (1'b0) cnt <= 8'd0;\n                else if", 'bench', ['backpressure']),
 ('M18', 'rtl/b4/b4_axi_gate.v', "assign s_awvalid = m_awvalid && !stall;  assign m_awready = s_awready && !stall;", "assign s_awvalid = m_awvalid;  assign m_awready = s_awready;", 'bench', ['backpressure', 'read_during_window']),
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
 ('H10', 'host/b4carrier_records.py', "    raise RecordRefusal(\"the transaction is not closed: no accepted CLOSE / CLOSE_INJECTION and no fault after the observation\")", "    return {\"schema\": SCHEMA_X, \"schema_version\": VERSION, \"observation_sha256\": osha, \"seq\": seq, \"idle_status\": 0, \"status\": \"injection_open\"}", 'test', ['tests.test_b4carrier_records']),
]
results = []
with tempfile.TemporaryDirectory(prefix='b4carrier_mutants_') as td:
    T = pathlib.Path(td)
    for rel in SUBTREE:
        src = R / rel; dst = T / rel; dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir(): shutil.copytree(src, dst, dirs_exist_ok=True)
        else: shutil.copy2(src, dst)
    (T / 'sim/b4/out').mkdir(parents=True, exist_ok=True)
    # the runner must run from the copy: it cds to its own ../..
    for mid, rel, old, new, kind, targets in MUTANTS:
        f = T / rel; text = f.read_text(); n = text.count(old)
        if n != 1:
            results.append({'id': mid, 'file': rel, 'status': 'EDIT-MISS', 'occurrences': n}); continue
        f.write_text(text.replace(old, new))
        try:
            if kind == 'unisim':
                p = subprocess.run(['bash', '-c', f'cd {T} && python3 -B tb/b4/gen_b4_fixture.py >/dev/null && iverilog -g2012 -I tb/b4 -o sim/b4/out/mu.vvp -y /home/test/Xilinx/2025.2/data/verilog/src/unisims /home/test/Xilinx/2025.2/data/verilog/src/glbl.v rtl/b1/p3_siphash.v rtl/b4/b4_gsr_reg.v rtl/b4/b4_slot_ram.v rtl/b4/b4_gsr_ram32.v rtl/b4/b4_axi_gate.v rtl/b4/b4_axil.v rtl/b4/b4_gate.v rtl/b4/b4_engine.v rtl/b4/b4_core.v rtl/b4/b4_target_slice.v tb/b4/tb_b4_unisim.v && vvp -N sim/b4/out/mu.vvp 2>&1 | grep -E "^TB_" | tail -1'], capture_output=True, text=True, timeout=600)
                outs = [('unisim', p.stdout.strip(), p.returncode)]
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
(HERE / 'mutants.json').write_text(json.dumps({'results': results, 'summary': summary}, indent=1) + '\n')
lines = [f"{r['id']:4} {r['status']:9} {r['file']}" + ('' if r['status'] == 'EDIT-MISS' else '  ' + '; '.join(str(x[:2]) for x in r.get('runs', []))) for r in results]
(HERE / 'mutants.txt').write_text('\n'.join(lines) + f"\nsummary {summary}\n")
print('\n'.join(lines)); print('summary', summary)
