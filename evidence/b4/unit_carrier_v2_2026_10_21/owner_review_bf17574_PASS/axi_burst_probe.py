from pathlib import Path
import json,subprocess
D=Path(__file__).resolve().parent
P=Path(json.loads((D/'snapshot.json').read_text())['temporary_root'])
s=(P/'tb/b4/tb_b4_axi3.v').read_text()
s=s[:s.index('        // the backpressure case through the shim:')]+'''
        // Legal two-beat FIXED AXI3 write: INIT_REQ in beat 1, a refused duplicate in beat 2.
        // The accepted burst must drain, even if the second operation is refused.
        @(negedge clk); awaddr=32'h40002000; awlen=1; awburst=0; awvalid=1;
        #1; while (!awready) begin @(negedge clk); #1; end
        @(negedge clk); awvalid=0; wdata=32'h400; wvalid=1; wlast=0;
        #1; while (!wready) begin @(negedge clk); #1; end
        @(negedge clk); wvalid=0;
        repeat(12) @(negedge clk);
        wdata=32'h400; wvalid=1; wlast=1;
        repeat(200) @(negedge clk);
        $display("OWNER_BURST stall=%0d ps_quiet=%0d shim_state=%0d WVALID=%0d WREADY=%0d BVALID=%0d gsr_count=%0d lite_quiet=%0d",stall,ps_quiet,axi3.state,wvalid,wready,bvalid,dut.engine.gsr_count,dut.quiet_lite);
        if (stall && !wready && !bvalid && dut.engine.gsr_count==0) $display("OWNER_REPRODUCED: accepted AXI3 burst cannot drain after its first INIT_REQ beat");
        else $display("OWNER_NOT_REPRODUCED");
        $finish;
    end
endmodule
'''
(P/'tb/b4/owner_axi_burst.v').write_text(s)
rtl=['rtl/b1/p3_siphash.v']+[f'rtl/b4/{n}.v' for n in ('b4_gsr_reg','b4_slot_ram','b4_gsr_ram32','b4_axi_gate','b4_axil','b4_gate','b4_engine','b4_core')]
cmd=['iverilog','-g2012','-I','tb/b4','-o','owner_axi_burst.vvp','-y','/home/test/Xilinx/2025.2/data/verilog/src/unisims',*rtl,'vivado/carrier/carrier_axi3_lite.v','tb/b4/b4_target_slice_model.v','tb/b4/owner_axi_burst.v']
a=subprocess.run(cmd,cwd=P,text=True,capture_output=True); assert a.returncode==0,a.stderr
b=subprocess.run(['vvp','-N','owner_axi_burst.vvp'],cwd=P,text=True,capture_output=True,timeout=30)
(D/'axi_burst_probe.txt').write_text(b.stdout+b.stderr); print(b.stdout)
