"""Expose the GSR pulse-counter simulation distinction with vendor FDCE primitives in a temporary model.
This is a simulation-model comparison, not a measured physical pulse width or post-route timing proof.
"""
from pathlib import Path
import json
import subprocess

D = Path(__file__).resolve().parent
root = Path(json.loads((D / 'snapshot.json').read_text())['temporary_root'])
engine = (root / 'rtl/b4/b4_engine.v').read_text()
old = '''    always @(posedge clk or negedge rst_n_raw) begin
        if (!rst_n_raw) pulse_cnt <= 8'd0;
        else if (fire) pulse_cnt <= PULSE[7:0];
        else if (pulse_cnt != 8'd0) pulse_cnt <= pulse_cnt - 8'd1;
    end'''
assert old in engine
mapped = engine.replace('reg fire; reg [7:0] pulse_cnt;', 'reg fire; wire [7:0] pulse_cnt;')
new = '''    wire [7:0] pulse_d = fire ? PULSE[7:0] : (pulse_cnt != 0 ? pulse_cnt - 8'd1 : 8'd0);
    genvar owner_bit;
    generate for (owner_bit = 0; owner_bit < 8; owner_bit = owner_bit + 1) begin : owner_vendor_counter
        FDCE #(.INIT(1'b0)) r (.Q(pulse_cnt[owner_bit]), .C(clk), .CE(1'b1), .CLR(~rst_n_raw), .D(pulse_d[owner_bit]));
    end endgenerate'''
mapped = mapped.replace(old, new)
(D / 'b4_engine_vendor_counter.v').write_text(mapped)
tb = (root / 'tb/b4/tb_b4_unisim.v').read_text()
monitor = '''
    realtime owner_on;
    reg owner_seen = 0;
    always @(posedge gsr_drive) begin owner_on = $realtime; owner_seen = 1; end
    always @(negedge gsr_drive) if (owner_seen) $display("OWNER_GSR_WIDTH_NS %0.3f", $realtime - owner_on);
    initial begin #2000000; $display("OWNER_TIMEOUT"); $finish; end
'''
tb = tb.replace('endmodule', monitor + '\nendmodule')
(D / 'tb_vendor_counter_probe.v').write_text(tb)
uni = Path('/home/test/Xilinx/2025.2/data/verilog/src')
rtl = ['rtl/b1/p3_siphash.v', 'rtl/b4/b4_gsr_reg.v', 'rtl/b4/b4_slot_ram.v', 'rtl/b4/b4_axil.v',
       'rtl/b4/b4_gate.v', 'rtl/b4/b4_core.v', 'rtl/b4/b4_target_slice.v']
out = {}
for variant, engine_file in [('behavioral_counter', root / 'rtl/b4/b4_engine.v'), ('vendor_FDCE_counter', D / 'b4_engine_vendor_counter.v')]:
    binary = root / ('sim/b4/out/' + variant + '.vvp')
    cmd = ['iverilog', '-g2012', '-I', str(root / 'tb/b4'), '-o', str(binary), '-y', str(uni / 'unisims'),
           str(uni / 'glbl.v'), *[str(root / s) for s in rtl], str(engine_file), str(D / 'tb_vendor_counter_probe.v')]
    p = subprocess.run(cmd, cwd=root, text=True, capture_output=True, timeout=30)
    (D / (variant + '_compile.txt')).write_text(p.stdout + p.stderr)
    assert p.returncode == 0, p.stderr
    p = subprocess.run(['vvp', '-N', str(binary)], cwd=root, text=True, capture_output=True, timeout=15)
    (D / (variant + '.txt')).write_text(p.stdout + p.stderr)
    widths = [float(l.split()[1]) for l in p.stdout.splitlines() if l.startswith('OWNER_GSR_WIDTH_NS ')]
    out[variant] = {'exit': p.returncode, 'pulse_width_ns_in_this_functional_simulation': widths,
                    'TB_PASS': 'TB_PASS unisim' in p.stdout, 'output': p.stdout}
assert out['behavioral_counter']['pulse_width_ns_in_this_functional_simulation']
assert out['behavioral_counter']['pulse_width_ns_in_this_functional_simulation'] != out['vendor_FDCE_counter']['pulse_width_ns_in_this_functional_simulation']
out['limit'] = 'The vendor-mapped counter models global GSR on pulse flops, which RTL reg simulation omits. Widths are model results, not silicon timing measurements. The committed timing report identifies pulse_cnt registers as FDCE.'
(D / 'gsr_model_comparison.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
