from pathlib import Path
import json,subprocess,sys
D=Path(__file__).resolve().parent; P=Path(json.loads((D/'snapshot.json').read_text())['temporary_root'])
s=(P/'tb/b4/tb_b4_core.v').read_text()
s=s.replace('        if (do_cleanup) begin','''        if (scenario == "owner_post_fault" && k == 1) begin
            mark("P6_sealed");
            close; expect_fault(7, "post-P6 CLOSE before restore is a sequence fault");
        end else if (do_cleanup) begin''',1)
s=s.replace('        "flow": begin','''        "owner_post_fault": begin
            provision(KEY_A);
            transaction(0, 1, "warm transaction");
            transaction(1, 1, "completed observation, faulted close");
        end
        "flow": begin''',1)
(P/'tb/b4/owner_phase.v').write_text(s)
rtl=['rtl/b1/p3_siphash.v']+[f'rtl/b4/{n}.v' for n in ('b4_gsr_reg','b4_slot_ram','b4_gsr_ram32','b4_axi_gate','b4_axil','b4_gate','b4_engine','b4_core')]
p=subprocess.run(['iverilog','-g2012','-I','tb/b4','-o','owner_phase.vvp','-y','/home/test/Xilinx/2025.2/data/verilog/src/unisims',*rtl,'tb/b4/b4_target_slice_model.v','tb/b4/owner_phase.v'],cwd=P,capture_output=True,text=True);assert p.returncode==0,p.stderr
p=subprocess.run(['vvp','-N','owner_phase.vvp','+SCENARIO=owner_post_fault'],cwd=P,text=True,capture_output=True,timeout=30)
(D/'phase_probe_rtl.txt').write_text(p.stdout+p.stderr)
sys.path[:0]=[str(P/'host'),str(P)]
import b4carrier_records as r
from tests.test_b4carrier_records import LINKS,TIMING,ROOT,fixture_stimuli
trace=r.load_trace(P/'sim/b4/out/owner_post_fault.jsonl'); ev=r.transactions(trace)[1]
cut=next(i for i,e in enumerate(ev) if e.get('mark')=='P6_sealed')
args=dict(links=LINKS,timing=TIMING,seq=2,session='bench',predecessor=ROOT,declared_stimulus=fixture_stimuli()[1])
o=r.observation(ev[:cut],**args); after=r.observation(ev,**args)
try: x=r.transaction_close(ev,o,seq=2,links=LINKS); xc={'status':x['status'],'findings':r.validate_close(x,o)}
except r.RecordRefusal as exc: xc={'raised':str(exc)}
out={'RTL':p.stdout.strip(),'P6_O_status':o['status'],'P6_O_findings':r.validate_observation(o),'after_fault_O_status':after['status'],'after_fault_O_fault':after.get('fault'),'close_result':xc}
(D/'phase_probe_results.json').write_text(json.dumps(out,indent=2)+'\n');(D/'phase_probe_mmio.jsonl').write_text((P/'sim/b4/out/owner_post_fault.jsonl').read_text()); print(json.dumps(out,indent=2))
