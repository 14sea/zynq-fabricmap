from pathlib import Path
import json,subprocess
D=Path(__file__).resolve().parent;P=Path(json.loads((D/'snapshot.json').read_text())['temporary_root'])
s=(P/'tb/b4/tb_b4_core.v').read_text()
s=s.replace('    integer fails = 0, log_fd;','''    integer fails = 0, log_fd;
    always @(posedge gsr_drive) $display("OWNER_EVENT_PRE_RESET clk=%0d ce=%0d sr=%0d d=%0h gsr_count=%0d",slice_clk,slice_ce,slice_sr,slice_d,dut.engine.gsr_count);
''',1)
(P/'tb/b4/owner_a5_context.v').write_text(s)
rtl=['rtl/b1/p3_siphash.v']+[f'rtl/b4/{n}.v' for n in ('b4_gsr_reg','b4_slot_ram','b4_gsr_ram32','b4_axi_gate','b4_axil','b4_gate','b4_engine','b4_core')]
p=subprocess.run(['iverilog','-g2012','-I','tb/b4','-o','owner_a5_context.vvp','-y','/home/test/Xilinx/2025.2/data/verilog/src/unisims',*rtl,'tb/b4/b4_target_slice_model.v','tb/b4/owner_a5_context.v'],cwd=P,text=True,capture_output=True);assert p.returncode==0,p.stderr
p=subprocess.run(['vvp','-N','owner_a5_context.vvp','+SCENARIO=a5'],cwd=P,text=True,capture_output=True,timeout=30)
(D/'a5_context_probe.txt').write_text(p.stdout+p.stderr); print(p.stdout)
