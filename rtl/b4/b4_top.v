// B4 carrier v2 — top level: PS7 (GP0) -> the AXI gate -> AXI3->AXI4-Lite shim (the instrument's, by reference, unchanged)
// -> b4_core (with its own gate at the Lite port) -> the target slice at SLICE_X2Y25; STARTUPE2 for the init event
// (GSR), driven by the engine's LUTRAM pulse counter.
// No ICAPE2. No board IO. NONCE_SEED is a build-time constant; the MAC key is provisioned at runtime.
`default_nettype none
module b4_top #(
    parameter [63:0]  NONCE_SEED   = 64'h9E3779B97F4A7C15,
    parameter [31:0]  VARIANT_WORD = 32'h42340001
) ();
    wire clk, rst_n;
    wire [31:0] ps_awaddr, ps_wdata, ps_araddr, ps_rdata;
    wire        ps_awvalid, ps_awready, ps_wvalid, ps_wready, ps_bvalid, ps_bready;
    wire        ps_arvalid, ps_arready, ps_rvalid, ps_rready;
    wire [1:0]  ps_bresp, ps_rresp;
    wire [3:0]  ps_wstrb;
    wire [11:0] ps_awid, ps_wid, ps_bid, ps_arid, ps_rid;
    wire [3:0]  ps_awlen, ps_arlen;
    wire [1:0]  ps_awsize, ps_arsize, ps_awburst, ps_arburst;
    wire        ps_wlast, ps_rlast;
    wire [15:0] m_awaddr, m_araddr; wire [31:0] m_wdata, m_rdata;
    wire m_awvalid, m_awready, m_wvalid, m_wready, m_bvalid, m_bready, m_arvalid, m_arready, m_rvalid, m_rready;
    wire [1:0] m_bresp, m_rresp; wire [3:0] m_wstrb;
    wire [3:0] fclkclk, fclkresetn;
    assign clk = fclkclk[0]; assign rst_n = fclkresetn[0];

    PS7 ps7 (
        .FCLKCLK(fclkclk), .FCLKRESETN(fclkresetn), .MAXIGP0ACLK(clk), .MAXIGP0ARESETN(),
        .MAXIGP0AWID(ps_awid), .MAXIGP0AWADDR(ps_awaddr), .MAXIGP0AWLEN(ps_awlen), .MAXIGP0AWSIZE(ps_awsize),
        .MAXIGP0AWBURST(ps_awburst), .MAXIGP0AWVALID(ps_awvalid), .MAXIGP0AWREADY(ps_awready),
        .MAXIGP0WID(ps_wid), .MAXIGP0WDATA(ps_wdata), .MAXIGP0WSTRB(ps_wstrb), .MAXIGP0WLAST(ps_wlast),
        .MAXIGP0WVALID(ps_wvalid), .MAXIGP0WREADY(ps_wready), .MAXIGP0BID(ps_bid), .MAXIGP0BRESP(ps_bresp),
        .MAXIGP0BVALID(ps_bvalid), .MAXIGP0BREADY(ps_bready), .MAXIGP0ARID(ps_arid), .MAXIGP0ARADDR(ps_araddr),
        .MAXIGP0ARLEN(ps_arlen), .MAXIGP0ARSIZE(ps_arsize), .MAXIGP0ARBURST(ps_arburst), .MAXIGP0ARVALID(ps_arvalid),
        .MAXIGP0ARREADY(ps_arready), .MAXIGP0RID(ps_rid), .MAXIGP0RDATA(ps_rdata), .MAXIGP0RRESP(ps_rresp),
        .MAXIGP0RLAST(ps_rlast), .MAXIGP0RVALID(ps_rvalid), .MAXIGP0RREADY(ps_rready));

    wire gsr_drive, stall, ps_quiet;
    wire rst_n_eff = rst_n & ~gsr_drive;
    // the AXI gate in front of the shim: the shim accepts a PS transaction into its own state machine before the
    // Lite side takes it, so the stall and the quiescence check must be applied on the PS side of it
    wire g_awvalid, g_awready, g_wvalid, g_wready, g_arvalid, g_arready;
    b4_axi_gate ps_gate (
        .clk(clk), .rst_n(rst_n_eff), .stall(stall),
        .m_awvalid(ps_awvalid), .m_awready(ps_awready), .s_awvalid(g_awvalid), .s_awready(g_awready),
        .m_wvalid(ps_wvalid),   .m_wready(ps_wready),   .s_wvalid(g_wvalid),   .s_wready(g_wready),
        .m_arvalid(ps_arvalid), .m_arready(ps_arready), .s_arvalid(g_arvalid), .s_arready(g_arready),
        .bvalid(ps_bvalid), .bready(ps_bready), .rvalid(ps_rvalid), .rready(ps_rready), .rlast(ps_rlast), .quiet(ps_quiet));
    carrier_axi3_lite #(.ID_W(12), .ADDR_W(16)) axi3 (
        .clk(clk), .rst_n(rst_n_eff),
        .s_awid(ps_awid), .s_awaddr(ps_awaddr), .s_awlen(ps_awlen), .s_awsize({1'b0, ps_awsize}), .s_awburst(ps_awburst),
        .s_awvalid(g_awvalid), .s_awready(g_awready),
        .s_wid(ps_wid), .s_wdata(ps_wdata), .s_wstrb(ps_wstrb), .s_wlast(ps_wlast), .s_wvalid(g_wvalid), .s_wready(g_wready),
        .s_bid(ps_bid), .s_bresp(ps_bresp), .s_bvalid(ps_bvalid), .s_bready(ps_bready),
        .s_arid(ps_arid), .s_araddr(ps_araddr), .s_arlen(ps_arlen), .s_arsize({1'b0, ps_arsize}), .s_arburst(ps_arburst),
        .s_arvalid(g_arvalid), .s_arready(g_arready),
        .s_rid(ps_rid), .s_rdata(ps_rdata), .s_rresp(ps_rresp), .s_rlast(ps_rlast), .s_rvalid(ps_rvalid), .s_rready(ps_rready),
        .m_awaddr(m_awaddr), .m_awvalid(m_awvalid), .m_awready(m_awready),
        .m_wdata(m_wdata), .m_wstrb(m_wstrb), .m_wvalid(m_wvalid), .m_wready(m_wready),
        .m_bresp(m_bresp), .m_bvalid(m_bvalid), .m_bready(m_bready),
        .m_araddr(m_araddr), .m_arvalid(m_arvalid), .m_arready(m_arready),
        .m_rdata(m_rdata), .m_rresp(m_rresp), .m_rvalid(m_rvalid), .m_rready(m_rready));

    wire slice_clk, slice_ce, slice_sr; wire [7:0] slice_d, slice_q;
    b4_core #(.NONCE_SEED(NONCE_SEED), .VARIANT_WORD(VARIANT_WORD)) core (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(m_awaddr), .s_awvalid(m_awvalid), .s_awready(m_awready),
        .s_wdata(m_wdata), .s_wstrb(m_wstrb), .s_wvalid(m_wvalid), .s_wready(m_wready),
        .s_bresp(m_bresp), .s_bvalid(m_bvalid), .s_bready(m_bready),
        .s_araddr(m_araddr), .s_arvalid(m_arvalid), .s_arready(m_arready),
        .s_rdata(m_rdata), .s_rresp(m_rresp), .s_rvalid(m_rvalid), .s_rready(m_rready),
        .slice_clk(slice_clk), .slice_ce(slice_ce), .slice_sr(slice_sr), .slice_d(slice_d), .slice_q(slice_q),
        .gsr_drive(gsr_drive), .ext_quiet(ps_quiet), .stall(stall));

    // the target: the certified site (vivado/b4/b4.xdc pins every cell)
    b4_target_slice target (.slice_clk(slice_clk), .ce(slice_ce), .sr(slice_sr), .d(slice_d), .q(slice_q), .gsr(gsr_drive));

    // the init event: the device's global set / reset, raised by the engine (mechanism (b) of the contract)
    (* DONT_TOUCH = "TRUE" *) STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(0.0)) startup (
        .CFGCLK(), .CFGMCLK(), .EOS(), .PREQ(),
        .CLK(1'b0), .GSR(gsr_drive), .GTS(1'b0), .KEYCLEARB(1'b1), .PACK(1'b0),
        .USRCCLKO(1'b0), .USRCCLKTS(1'b1), .USRDONEO(1'b1), .USRDONETS(1'b1));
endmodule
`default_nettype wire
