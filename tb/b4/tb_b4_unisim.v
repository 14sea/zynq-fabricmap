`timescale 1ns/1ps
// The init mechanism on the VENDOR models: b4_core + the real rtl/b4/b4_target_slice.v (FDPE / LUT6 UNISIM) +
// a STARTUPE2 whose GSR input is the engine's drive, exactly as b4_top wires it. The vendor model drives
// glbl.GSR from that input, so the FDPEs return to INIT (1) when the carrier raises the event, and the
// RAM32X1S store does not. Compiled TWICE by sim/b4/run.sh: with the RTL core (every engine flip-flop reset
// through rst_n_eff) and with the post-route FUNCSIM NETLIST of the core (every flip-flop a vendor FDxE that sees
// glbl.GSR itself — the owner's model-fidelity point of 2026-10-21). The GSR pulse width is measured and must be
// PULSE clocks in both: the generator is LUTRAM. This witnesses the mechanism's CONDITIONS (contract 6.2 (b),
// 9.1) on the base configuration only; it is not an A8 demonstration.
module tb_b4_unisim;
    `include "b4_fixture.vh"
    localparam integer ASSERT_DELAY = 8, PULSE = 2, RELEASE = 16, SAMPLE_OFFSET = 4, SETTLE = 4, HOLD = 4;
    localparam integer QUIET = ASSERT_DELAY + PULSE + RELEASE + SAMPLE_OFFSET + 16;
    reg clk = 0; always #10 clk = ~clk;
    reg rst_n = 0;
    reg [15:0] awaddr = 0, araddr = 0; reg awvalid = 0, wvalid = 0, bready = 1, arvalid = 0, rready = 1;
    reg [31:0] wdata = 0; wire awready, wready, bvalid, arready, rvalid; wire [1:0] bresp, rresp; wire [31:0] rdata;
    wire slice_clk, slice_ce, slice_sr; wire [7:0] slice_d, slice_q; wire gsr_drive;
    // no parameter overrides: the netlist build has none; the defaults equal the fixture's SEED and the timing above
    b4_core dut (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(awaddr), .s_awvalid(awvalid), .s_awready(awready),
        .s_wdata(wdata), .s_wstrb(4'hF), .s_wvalid(wvalid), .s_wready(wready),
        .s_bresp(bresp), .s_bvalid(bvalid), .s_bready(bready),
        .s_araddr(araddr), .s_arvalid(arvalid), .s_arready(arready),
        .s_rdata(rdata), .s_rresp(rresp), .s_rvalid(rvalid), .s_rready(rready),
        .slice_clk(slice_clk), .slice_ce(slice_ce), .slice_sr(slice_sr), .slice_d(slice_d), .slice_q(slice_q), .gsr_drive(gsr_drive),
        .ext_quiet(1'b1), .stall());
    b4_target_slice target (.slice_clk(slice_clk), .ce(slice_ce), .sr(slice_sr), .d(slice_d), .q(slice_q), .gsr(gsr_drive));
    STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(0.0)) startup (
        .CFGCLK(), .CFGMCLK(), .EOS(), .PREQ(), .CLK(1'b0), .GSR(gsr_drive), .GTS(1'b0), .KEYCLEARB(1'b1), .PACK(1'b0),
        .USRCCLKO(1'b0), .USRCCLKTS(1'b1), .USRDONEO(1'b1), .USRDONETS(1'b1));

    integer fails = 0; reg [1:0] last_bresp, last_rresp; reg [31:0] last_rdata;
    realtime gsr_on; integer pulses = 0; realtime widths [0:7];
    always @(posedge glbl.GSR) gsr_on = $realtime;
    always @(negedge glbl.GSR) if ($realtime > 150) begin widths[pulses] = $realtime - gsr_on; pulses = pulses + 1; end
    task check(input cond, input [255:0] what); begin if (!cond) begin fails = fails + 1; $display("FAIL: %0s [rdata=%h t=%0t]", what, last_rdata, $time); end end endtask
    task wr(input [15:0] a, input [31:0] d); begin
        @(negedge clk); awaddr = a; wdata = d; awvalid = 1; wvalid = 1; while (!(awready && wready)) @(negedge clk);
        @(negedge clk); awvalid = 0; wvalid = 0; while (!bvalid) @(negedge clk); last_bresp = bresp; @(negedge clk);
    end endtask
    task rd(input [15:0] a); begin
        @(negedge clk); araddr = a; arvalid = 1; while (!arready) @(negedge clk);
        @(negedge clk); arvalid = 0; while (!rvalid) @(negedge clk); last_rdata = rdata; last_rresp = rresp; @(negedge clk);
    end endtask
    task stage(input [767:0] p); integer i; begin for (i = 0; i < 24; i = i + 1) wr(16'h2100 + 4*i, p[(23-i)*32 +: 32]); end endtask
    task provision(input [127:0] k); integer j; begin for (j = 0; j < 4; j = j + 1) wr(16'h2160 + 4*j, k[(3-j)*32 +: 32]); wr(16'h2000, 32'h100); end endtask
    task wait_gate; begin repeat (5) @(negedge clk); rd(16'h2004); while (last_rdata[0]) rd(16'h2004); end endtask
    task wait_engine; begin rd(16'h2004); while (last_rdata[3]) rd(16'h2004); end endtask
    task slot(input [4:0] a); begin wr(16'h201C, {27'd0, a}); rd(16'h2018); end endtask
    initial begin
        #150; @(negedge clk); rst_n = 0; repeat (3) @(negedge clk); rst_n = 1; repeat (2) @(negedge clk);   // after glbl's power-on GSR
        rd(16'h2010); check(last_rdata[7:0] == 8'hFF, "the vendor FDPEs read INIT = 1 after configuration");
        provision(KEY_A);
        // T1: capture zeros, no cleanup (inputs held), close
        stage(VALID1); wr(16'h2000, 32'h40); wait_gate; rd(16'h2004); check(last_rdata[2] == 1, "armed");
        wr(16'h2000, 32'h200); wait_engine;
        wr(16'h2000, 32'h400); repeat (QUIET) @(negedge clk); wait_engine;
        slot(5'd1); check(last_rdata[7:0] == 8'hFF, "T1 init sample = INIT (vendor FDPE under the carrier's GSR)");
        wr(16'h2038, 32'h0100FF00); wr(16'h2000, 32'h800); wait_engine;        // clock 1, ce all, d 0x00
        rd(16'h2010); check(last_rdata[7:0] == 8'h00, "the vendor FDPEs captured 0 on the engine's slice clock");
        wr(16'h2000, 32'h8000); wait_engine;                                     // CLOSE_INJECTION: the inputs stay held (c-prime)
        // T2: the event restores INIT on the vendor models; the LUTRAM store (key, nonce, armed) survives
        
        stage(VALID2); wr(16'h2000, 32'hC0); wait_gate; rd(16'h2004); check(last_rdata[2] == 1 && last_rdata[11] == 1, "armed again (A5 context); key persisted");
        wr(16'h2000, 32'h200); wait_engine; slot(5'd0); check(last_rdata[7:0] == 8'h00, "pre-init sample = the held zeros");
        wr(16'h2000, 32'h400); repeat (QUIET) @(negedge clk); wait_engine;
        slot(5'd1); check(last_rdata[7:0] == 8'hFF, "T2 init sample = INIT: the carrier's GSR restored the vendor FDPEs");
        rd(16'h2020); check(last_rdata[7:0] == 2, "two events");
        rd(16'h202C); check(last_rdata == N2[31:0], "nonce chain survived both events");
        wr(16'h2000, 32'h1000); wait_engine;                                     // cleanup
        wr(16'h2000, 32'h4000); repeat (QUIET) @(negedge clk); wait_engine;      // the restore event (P9)
        rd(16'h203C); check(last_rdata[7:0] == 8'hFF, "the base-state sample after the restore event = INIT on the vendor FDPEs");
        wr(16'h2000, 32'h2000); wait_engine; rd(16'h2004); check(last_rdata[12] == 1, "idle after the normal close");
        rd(16'h2020); check(last_rdata[7:0] == 3, "three events");
        check(pulses == 3, "three GSR pulses seen on glbl.GSR");
        check(widths[0] == PULSE * 20.0 && widths[1] == PULSE * 20.0 && widths[2] == PULSE * 20.0, "every GSR pulse is PULSE clocks wide (LUTRAM-timed; the same on the netlist)");
        $display("GSR_PULSE_WIDTHS_NS %0.1f %0.1f %0.1f", widths[0], widths[1], widths[2]);
        if (fails == 0) $display("TB_PASS unisim"); else $display("TB_FAIL unisim (%0d)", fails);
        $finish;
    end
endmodule
