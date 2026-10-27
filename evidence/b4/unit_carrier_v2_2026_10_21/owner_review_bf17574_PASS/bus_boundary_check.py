from pathlib import Path
import json,subprocess
D=Path(__file__).resolve().parent;P=Path(json.loads((D/'snapshot.json').read_text())['temporary_root']);(P/'sim/b4/owner_monitor').mkdir(parents=True,exist_ok=True)
s=(P/'tb/b4/tb_b4_core.v').read_text().replace('sim/b4/out/%0s.jsonl','sim/b4/owner_monitor/%0s.jsonl')
s=s.replace('    integer fails = 0, log_fd;', '''    integer fails = 0, log_fd;
    integer owner_b=0, owner_start=0, owner_wait=0, owner_events=0;
    always @(posedge clk) if (bvalid && bready) owner_b=owner_b+1;
    always @(posedge gsr_drive) begin
        owner_events=owner_events+1;
        if (dut.axil.aw_seen || dut.axil.w_seen || bvalid || rvalid)
            begin fails=fails+1; $display("FAIL: OWNER_GSR with uncompleted bus transfer aw=%b w=%b b=%b r=%b",dut.axil.aw_seen,dut.axil.w_seen,bvalid,rvalid); end
    end
''',1)
new='''        "owner_split_W", "owner_split_AW": begin
            provision(KEY_A);target.genome=FIX0_GENOME;stage(VALID1);arm;wait_gate;pre_sample;
            wr(16'h2000,32'h400);owner_start=owner_b;
            @(negedge clk);awaddr=16'h2038;wdata=32'h0000FF5A;
            if(scenario=="owner_split_W")begin
                wvalid=1;owner_wait=0;#1;
                check(!wready && stall,"W-first is held during the event");
                while(!wready && owner_wait<400)begin @(negedge clk);#1;owner_wait=owner_wait+1;end
                check(owner_wait<400,"W is eventually admitted");
                @(negedge clk);wvalid=0;repeat(3)@(negedge clk);awvalid=1;#1;
                owner_wait=0;while(!awready && owner_wait<100)begin @(negedge clk);#1;owner_wait=owner_wait+1;end
                check(owner_wait<100,"matching AW admitted");@(negedge clk);awvalid=0;
            end else begin
                awvalid=1;owner_wait=0;#1;
                check(!awready && stall,"AW-first is held during the event");
                while(!awready && owner_wait<400)begin @(negedge clk);#1;owner_wait=owner_wait+1;end
                check(owner_wait<400,"AW is eventually admitted");
                @(negedge clk);awvalid=0;repeat(3)@(negedge clk);wvalid=1;#1;
                owner_wait=0;while(!wready && owner_wait<100)begin @(negedge clk);#1;owner_wait=owner_wait+1;end
                check(owner_wait<100,"matching W admitted");@(negedge clk);wvalid=0;
            end
            owner_wait=0;while(owner_b==owner_start && owner_wait<100)begin @(negedge clk);owner_wait=owner_wait+1;end
            check(owner_b==owner_start+1,"split write answered exactly once");
            rd(16'h2038);check(last_rdata==32'h0000FF5A,"the acknowledged write value was applied");
            check(owner_events==1 && dut.engine.gsr_count==1,"exactly one init event");
        end
'''
s=s.replace('        "regs": begin',new+'        "regs": begin',1)
(P/'tb/b4/owner_bus_check.v').write_text(s)
rtl=['rtl/b1/p3_siphash.v']+[f'rtl/b4/{n}.v' for n in ('b4_gsr_reg','b4_slot_ram','b4_gsr_ram32','b4_axi_gate','b4_axil','b4_gate','b4_engine','b4_core')]
p=subprocess.run(['iverilog','-g2012','-I','tb/b4','-o','owner_bus_check.vvp','-y','/home/test/Xilinx/2025.2/data/verilog/src/unisims',*rtl,'tb/b4/b4_target_slice_model.v','tb/b4/owner_bus_check.v'],cwd=P,text=True,capture_output=True);assert p.returncode==0,p.stderr
# All core mechanics scenarios, with the independent GSR/bus-state monitor, plus independent legal split transfers.
import re
sc=re.search(r'SCENARIOS="([^"]+)"',(P/'sim/b4/run.sh').read_text()).group(1).split()+['owner_split_W','owner_split_AW']
logs=[]
for mode in sc:
    p=subprocess.run(['vvp','-N','owner_bus_check.vvp','+SCENARIO='+mode],cwd=P,text=True,capture_output=True,timeout=30)
    logs.append(p.stdout+p.stderr)
    assert f'TB_PASS {mode}' in p.stdout and 'FAIL:' not in p.stdout and 'TB_FAIL' not in p.stdout,p.stdout+p.stderr
(D/'bus_boundary_check.txt').write_text('\n'.join(logs));print('owner bus-state monitor:',len(sc),'core scenarios PASS; W-first and AW-first each complete exactly once')
