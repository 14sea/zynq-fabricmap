`timescale 1ns/1ps
// The PS path: an AXI3 master (the bench, single-beat as PS7 GP0 issues them) -> the AXI gate -> the instrument's
// AXI3->Lite shim (pinned, by reference) -> b4_core (with its own Lite gate) -> the bench's fabric. Exactly b4_top
// without PS7 and STARTUPE2. It exercises the owner's backpressure reproduction THROUGH THE SHIM: BREADY held low
// after INIT_REQ, the response is delivered first and the event fires once after the path is quiet; and a read
// presented during the window is stalled at the PS side (never accepted into the shim) and served afterwards.
module tb_b4_axi3;
    `include "b4_fixture.vh"
    localparam integer ASSERT_DELAY = 8, PULSE = 2, RELEASE = 16, SAMPLE_OFFSET = 4, SETTLE = 4, HOLD = 4;
    localparam integer QUIET = ASSERT_DELAY + PULSE + RELEASE + SAMPLE_OFFSET + 16;
    reg clk = 0; always #10 clk = ~clk;
    reg rst_n = 0;
    // the AXI3 master
    reg [11:0] awid = 0, arid = 0; reg [31:0] awaddr = 0, araddr = 0, wdata = 0; reg [3:0] awlen = 0, arlen = 0; reg [1:0] awsize = 2, arsize = 2, awburst = 1, arburst = 1;
    reg awvalid = 0, wvalid = 0, wlast = 1, bready = 1, arvalid = 0, rready = 1; reg [3:0] wstrb = 4'hF;
    wire awready, wready, bvalid, arready, rvalid, rlast; wire [1:0] bresp, rresp; wire [31:0] rdata; wire [11:0] bid, rid;
    // gate -> shim -> core
    wire g_awvalid, g_awready, g_wvalid, g_wready, g_arvalid, g_arready, ps_quiet, stall, gsr_drive;
    wire [15:0] m_awaddr, m_araddr; wire [31:0] m_wdata, m_rdata; wire [3:0] m_wstrb;
    wire m_awvalid, m_awready, m_wvalid, m_wready, m_bvalid, m_bready, m_arvalid, m_arready, m_rvalid, m_rready; wire [1:0] m_bresp, m_rresp;
    wire rst_n_eff = rst_n & ~gsr_drive;
    b4_axi_gate ps_gate (.clk(clk), .rst_n(rst_n_eff), .stall(stall),
        .m_awvalid(awvalid), .m_awready(awready), .s_awvalid(g_awvalid), .s_awready(g_awready),
        .m_wvalid(wvalid), .m_wready(wready), .s_wvalid(g_wvalid), .s_wready(g_wready),
        .m_arvalid(arvalid), .m_arready(arready), .s_arvalid(g_arvalid), .s_arready(g_arready),
        .bvalid(bvalid), .bready(bready), .rvalid(rvalid), .rready(rready), .rlast(rlast), .quiet(ps_quiet));
    carrier_axi3_lite #(.ID_W(12), .ADDR_W(16)) axi3 (.clk(clk), .rst_n(rst_n_eff),
        .s_awid(awid), .s_awaddr(awaddr), .s_awlen(awlen), .s_awsize({1'b0, awsize}), .s_awburst(awburst), .s_awvalid(g_awvalid), .s_awready(g_awready),
        .s_wid(awid), .s_wdata(wdata), .s_wstrb(wstrb), .s_wlast(wlast), .s_wvalid(g_wvalid), .s_wready(g_wready),
        .s_bid(bid), .s_bresp(bresp), .s_bvalid(bvalid), .s_bready(bready),
        .s_arid(arid), .s_araddr(araddr), .s_arlen(arlen), .s_arsize({1'b0, arsize}), .s_arburst(arburst), .s_arvalid(g_arvalid), .s_arready(g_arready),
        .s_rid(rid), .s_rdata(rdata), .s_rresp(rresp), .s_rlast(rlast), .s_rvalid(rvalid), .s_rready(rready),
        .m_awaddr(m_awaddr), .m_awvalid(m_awvalid), .m_awready(m_awready), .m_wdata(m_wdata), .m_wstrb(m_wstrb), .m_wvalid(m_wvalid), .m_wready(m_wready),
        .m_bresp(m_bresp), .m_bvalid(m_bvalid), .m_bready(m_bready), .m_araddr(m_araddr), .m_arvalid(m_arvalid), .m_arready(m_arready),
        .m_rdata(m_rdata), .m_rresp(m_rresp), .m_rvalid(m_rvalid), .m_rready(m_rready));
    wire slice_clk, slice_ce, slice_sr; wire [7:0] slice_d, slice_q;
    b4_core #(.NONCE_SEED(SEED)) dut (.clk(clk), .rst_n(rst_n),
        .s_awaddr(m_awaddr), .s_awvalid(m_awvalid), .s_awready(m_awready), .s_wdata(m_wdata), .s_wstrb(m_wstrb), .s_wvalid(m_wvalid), .s_wready(m_wready),
        .s_bresp(m_bresp), .s_bvalid(m_bvalid), .s_bready(m_bready), .s_araddr(m_araddr), .s_arvalid(m_arvalid), .s_arready(m_arready),
        .s_rdata(m_rdata), .s_rresp(m_rresp), .s_rvalid(m_rvalid), .s_rready(m_rready),
        .slice_clk(slice_clk), .slice_ce(slice_ce), .slice_sr(slice_sr), .slice_d(slice_d), .slice_q(slice_q), .gsr_drive(gsr_drive),
        .ext_quiet(ps_quiet), .stall(stall));
    b4_target_slice target (.slice_clk(slice_clk), .ce(slice_ce), .sr(slice_sr), .d(slice_d), .q(slice_q), .gsr(gsr_drive));

    integer fails = 0, responses = 0; reg [1:0] last_bresp; reg [31:0] last_rdata; reg verbose = 0;
    initial begin if ($test$plusargs("VERBOSE")) verbose = 1; #3000000; $display("WATCHDOG: the AXI3 bench did not finish (fails so far %0d)", fails); $finish; end
    always @(posedge clk) if (bvalid && bready) responses = responses + 1;
    task check(input cond, input [255:0] what); begin if (!cond) begin fails = fails + 1; $display("FAIL: %0s [rdata=%h t=%0t]", what, last_rdata, $time); end end endtask
    // the shim's AWREADY / ARREADY / WREADY are combinational in the cycle the VALID is presented: sample them after the
    // combinational settle (#1) in the same cycle, not after the edge that already completed the handshake
    task wr(input [15:0] a, input [31:0] d); begin
        @(negedge clk); awaddr = {16'h4000, a}; wdata = d; awvalid = 1; #1; while (!awready) begin @(negedge clk); #1; end
        @(negedge clk); awvalid = 0; wvalid = 1; #1; while (!wready) begin @(negedge clk); #1; end
        @(negedge clk); wvalid = 0; while (!bvalid) @(negedge clk); last_bresp = bresp; @(negedge clk);
        if (verbose) $display("  wr %h <= %h resp %0d t=%0t", a, d, last_bresp, $time);
    end endtask
    task rd(input [15:0] a); begin
        @(negedge clk); araddr = {16'h4000, a}; arvalid = 1; #1; while (!arready) begin @(negedge clk); #1; end
        @(negedge clk); arvalid = 0; while (!rvalid) @(negedge clk); last_rdata = rdata; @(negedge clk);
        if (verbose) $display("  rd %h => %h t=%0t", a, last_rdata, $time);
    end endtask
    task stage(input [767:0] p); integer i; begin for (i = 0; i < 24; i = i + 1) wr(16'h2100 + 4*i, p[(23-i)*32 +: 32]); end endtask
    task provision(input [127:0] k); integer j; begin for (j = 0; j < 4; j = j + 1) wr(16'h2160 + 4*j, k[(3-j)*32 +: 32]); wr(16'h2000, 32'h100); end endtask
    task wait_gate; begin repeat (5) @(negedge clk); rd(16'h2004); while (last_rdata[0]) rd(16'h2004); end endtask
    task wait_engine; begin rd(16'h2004); while (last_rdata[3]) rd(16'h2004); end endtask
    integer r0;
    initial begin
        @(negedge clk); rst_n = 0; repeat (3) @(negedge clk); rst_n = 1; repeat (2) @(negedge clk);
        rd(16'h2034); check(last_rdata == 32'h42340001, "VARIANT through the shim");
        provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); wr(16'h2000, 32'h40); wait_gate;
        rd(16'h2004); check(last_rdata[2] == 1, "armed through the shim");
        wr(16'h2000, 32'h200); wait_engine;
        // the backpressure case through the shim: the INIT_REQ write, BREADY held low
        r0 = responses;
        @(negedge clk); bready = 0; awaddr = 32'h40002000; wdata = 32'h400; awvalid = 1; #1; while (!awready) begin @(negedge clk); #1; end
        @(negedge clk); awvalid = 0; wvalid = 1; #1; while (!wready) begin @(negedge clk); #1; end
        @(negedge clk); wvalid = 0; while (!bvalid) @(negedge clk);
        repeat (QUIET) @(negedge clk);
        check(bvalid == 1 && bready == 0, "the shim still holds the write response for the master after the quiet window");
        check(gsr_drive == 0 && dut.engine.gsr_count == 0, "no event while the response is outstanding in the shim");
        bready = 1; repeat (2) @(negedge clk);
        check(responses == r0 + 1, "exactly one response delivered");
        // a read presented during the window: stalled at the PS side, served after
        @(negedge clk); araddr = 32'h40002004; arvalid = 1; #1; while (!arready) begin @(negedge clk); #1; end
        @(negedge clk); arvalid = 0; while (!rvalid) @(negedge clk); last_rdata = rdata; @(negedge clk);
        check(last_rdata[9] == 1 || last_rdata[10] == 1, "the read was served with a coherent status after the window");
        wait_engine; rd(16'h2020); check(last_rdata[7:0] == 1, "exactly one event");
        rd(16'h2004); check(last_rdata[9] == 1 && last_rdata[2] == 1 && last_rdata[11] == 1, "init_done; armed and key persisted through the shim's reset");
        wr(16'h2038, 32'h0000FF00); wr(16'h2000, 32'h800); wait_engine; rd(16'h2010); check(last_rdata[7:0] == 8'hFF, "a step through the shim (clock 0: hold)");
        wr(16'h2000, 32'h1000); wait_engine; wr(16'h2000, 32'h4000); repeat (QUIET) @(negedge clk); wait_engine;
        rd(16'h203C); check(last_rdata[7:0] == 8'hFF, "base-state sample"); wr(16'h2000, 32'h2000); wait_engine;
        rd(16'h2004); check(last_rdata[12] == 1, "idle after the close");
        if (fails == 0) $display("TB_PASS axi3"); else $display("TB_FAIL axi3 (%0d)", fails);
        $finish;
    end
endmodule
