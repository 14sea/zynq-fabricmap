from pathlib import Path
import json,subprocess,sys
D=Path(__file__).resolve().parent;P=Path(json.loads((D/'snapshot.json').read_text())['temporary_root'])
(P/'sim/b4/out').mkdir(parents=True,exist_ok=True)
s=(P/'tb/b4/tb_b4_core.v').read_text()
s=s.replace('    integer fails = 0, log_fd;','''    integer fails = 0, log_fd;
    integer owner_responses = 0, owner_before = 0;
    always @(posedge clk) if (bvalid && bready) owner_responses = owner_responses + 1;
''',1)
cases='''        "owner_wfirst": begin
            provision(KEY_A); target.genome=FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample;
            wr(16'h2000,32'h400);
            owner_before=owner_responses;
            @(negedge clk); wdata=32'h0000FF5A; wvalid=1; #1;
            check(stall==1 && wready==1,"W accepted during event pending");
            @(negedge clk); wvalid=0;
            repeat(QUIET) @(negedge clk);
            check(dut.engine.gsr_count==1,"one GSR since W acceptance");
            awaddr=16'h2038; awvalid=1; #1; while(!awready) begin @(negedge clk); #1; end
            @(negedge clk); awvalid=0;
            repeat(80) @(negedge clk);
            $display("OWNER_WFIRST gsr_count=%0d responses_for_split_write=%0d aw_seen=%0d w_seen=%0d step_in=%h",dut.engine.gsr_count,owner_responses-owner_before,dut.axil.aw_seen,dut.axil.w_seen,dut.axil.step_in);
        end
        "owner_early_cleanup": begin
            provision(KEY_A); transaction(0,1,"warm transaction");
            mark("transaction_begin");target.genome=FIX1_GENOME;stage(VALID2);arm;wait_gate;
            pre_sample;slot(0);slot_in(0);rd(16'h2020);mark("P3_before_bad_cleanup");
            cleanup;expect_fault(7,"CLEANUP before init is sequence fault");mark("transaction_end");
        end
'''
s=s.replace('        "regs": begin',cases+'        "regs": begin',1)
(P/'tb/b4/owner_boundaries.v').write_text(s)
rtl=['rtl/b1/p3_siphash.v']+[f'rtl/b4/{n}.v' for n in ('b4_gsr_reg','b4_slot_ram','b4_gsr_ram32','b4_axi_gate','b4_axil','b4_gate','b4_engine','b4_core')]
p=subprocess.run(['iverilog','-g2012','-I','tb/b4','-o','owner_boundaries.vvp','-y','/home/test/Xilinx/2025.2/data/verilog/src/unisims',*rtl,'tb/b4/b4_target_slice_model.v','tb/b4/owner_boundaries.v'],cwd=P,text=True,capture_output=True);assert p.returncode==0,p.stderr
for mode in ('owner_wfirst','owner_early_cleanup'):
    p=subprocess.run(['vvp','-N','owner_boundaries.vvp','+SCENARIO='+mode],cwd=P,text=True,capture_output=True,timeout=30)
    (D/(mode+'.txt')).write_text(p.stdout+p.stderr);(D/(mode+'.jsonl')).write_bytes((P/'sim/b4/out'/f'{mode}.jsonl').read_bytes()); print(p.stdout)
sys.path[:0]=[str(P/'host'),str(P)]
import b4carrier_records as r
from tests.test_b4carrier_records import LINKS,TIMING,ROOT,fixture_stimuli
trace=r.load_trace(P/'sim/b4/out/owner_early_cleanup.jsonl');tx=r.transactions(trace)[1]
o=r.observation(tx,LINKS,TIMING,seq=2,session='bench',predecessor=ROOT,declared_stimulus=fixture_stimuli()[1]); x=r.transaction_close(tx,o,seq=2,links=LINKS)
results={'O_status':o['status'],'O_fault':o.get('fault'),'O_step_count':len(o['steps']),'O_findings':r.validate_observation(o),'X_status':x['status'],'X_fault':x.get('fault'),'X_findings':r.validate_close(x,o)}
(D/'early_cleanup_records.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
