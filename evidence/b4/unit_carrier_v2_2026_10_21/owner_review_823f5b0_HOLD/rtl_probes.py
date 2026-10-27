"""AXI/engine counterexamples in the isolated snapshot. Product sources are never edited."""
from pathlib import Path
import json
import subprocess

D = Path(__file__).resolve().parent
root = Path(json.loads((D / 'snapshot.json').read_text())['temporary_root'])
base = (root / 'tb/b4/tb_b4_core.v').read_text()
cases = r'''
        "owner_p9": begin
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event;
            step(25'h100FF00); cleanup;
            target.genome = FIX0_GENOME; // fixture's base configuration; no additional init event
            rd(16'h2010); check(last_rdata[7:0] == 8'h00, "base Q still held at captured zero");
            $display("OWNER P9 base_Q=%h (base INIT was FF at step 0)", last_rdata[7:0]);
            rd(16'h2020); $display("OWNER P9 init_count_before_close=%0d", last_rdata[7:0]);
            wr(16'h2000, 32'h400); wait_engine; expect_fault(7, "P9 cannot raise second event while init_done");
        end
        "owner_open_close": begin
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event;
            step(25'h100FF00); close;
            rd(16'h2004); check(last_rdata[12] && last_rdata[14], "idle bit set on injection_open");
            $display("OWNER premature_close status=%h", last_rdata);
            rd(16'h2014); check(last_rdata[10:0] != 0, "held inputs are not idle");
            $display("OWNER premature_close held_inputs=%h", last_rdata);
            stage(VALID2); arm; wait_gate; rd(16'h2004);
            check(last_rdata[2] && !last_rdata[1], "normal ARM accepted without base restore");
            $display("OWNER premature_close next_arm_status=%h", last_rdata);
        end
        "owner_axi_backpressure": begin
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample;
            @(negedge clk); bready = 0; awaddr = 16'h2000; wdata = 32'h400; awvalid = 1; wvalid = 1;
            while (!(awready && wready)) @(negedge clk);
            @(negedge clk); awvalid = 0; wvalid = 0;
            while (!bvalid) @(negedge clk);
            $display("OWNER held_response before_GSR bvalid=%b bready=%b", bvalid, bready);
            repeat (QUIET) @(negedge clk);
            $display("OWNER held_response after_GSR bvalid=%b bready=%b", bvalid, bready);
            check(bvalid == 0 && bready == 0, "outstanding write response lost before handshake");
            bready = 1; repeat (5) @(negedge clk);
            rd(16'h2020); $display("OWNER held_response init_count=%0d", last_rdata[7:0]);
        end
        "owner_step_snapshot": begin
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event;
            wr(16'h2038, 32'h0000FFA5); wr(16'h2000, 32'h800);
            // Stage a NEXT word without issuing a second STEP. Applied command should retain clock=0,d=A5.
            wr(16'h2038, 32'h0100FF5A); wait_engine;
            rd(16'h2014); $display("OWNER step_snapshot actual_inputs=%h expected_clock=0", last_rdata);
            rd(16'h2010); $display("OWNER step_snapshot actual_Q=%h expected_held_INIT=FF", last_rdata[7:0]);
            check(last_rdata[7:0] == 8'hA5, "next staged clock changed the in-flight step");
        end
        "owner_busy_close": begin
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event;
            wr(16'h2038, 32'h0100FFA5); wr(16'h2000, 32'h800);
            wr(16'h2000, 32'h2000); repeat (10) @(negedge clk); wait_engine;
            rd(16'h2004); $display("OWNER busy_close status=%h", last_rdata);
            check(last_rdata[2] && !last_rdata[1], "CLOSE during busy silently dropped: still armed, no fault");
        end
'''
assert '"fault_not_armed": begin' in base
probe = base.replace('"fault_not_armed": begin', cases + '\n        "fault_not_armed": begin', 1)
probe = probe.replace('endmodule', 'initial begin #2000000; $display("OWNER_TIMEOUT"); $finish; end\nendmodule')
(D / 'tb_owner_probes.v').write_text(probe)
rtl = ['rtl/b1/p3_siphash.v', 'rtl/b4/b4_gsr_reg.v', 'rtl/b4/b4_slot_ram.v', 'rtl/b4/b4_axil.v',
       'rtl/b4/b4_gate.v', 'rtl/b4/b4_engine.v', 'rtl/b4/b4_core.v']
uni = '/home/test/Xilinx/2025.2/data/verilog/src'
binary = root / 'sim/b4/out/owner_probes.vvp'
cmd = ['iverilog', '-g2012', '-I', str(root / 'tb/b4'), '-o', str(binary), '-y', uni + '/unisims',
       *[str(root / p) for p in rtl], str(root / 'tb/b4/b4_target_slice_model.v'), str(D / 'tb_owner_probes.v')]
p = subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=30)
(D / 'rtl_compile.txt').write_text(p.stdout + p.stderr)
assert p.returncode == 0, p.stderr
out = {}
for scenario in ('owner_p9', 'owner_open_close', 'owner_axi_backpressure', 'owner_step_snapshot', 'owner_busy_close'):
    p = subprocess.run(['vvp', '-N', str(binary), '+SCENARIO=' + scenario], cwd=root, text=True, capture_output=True, timeout=15)
    (D / (scenario + '.txt')).write_text(p.stdout + p.stderr)
    out[scenario] = {'exit': p.returncode, 'output': p.stdout, 'stderr': p.stderr,
                     'finding_reproduced': 'TB_PASS ' + scenario in p.stdout and 'OWNER_TIMEOUT' not in p.stdout}
assert all(v['finding_reproduced'] for v in out.values()), out
(D / 'rtl_findings.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
