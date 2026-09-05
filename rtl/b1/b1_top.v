// B1 carrier — top level: the P3 carrier with the b1 gate (SEMANTIC_GATE = 0) and the VARIANT register.
// P3 carrier — top level. PS7 (GP0) -> AXI3->AXI4-Lite shim (imported, unchanged)
// -> p3_core (register file, ARM gate, heartbeat, scorer) -> six evolvable LUT6.
// No ICAPE2. No board IO. NONCE_SEED is a build-time constant; the MAC key is provisioned at runtime (D4 option A).
`default_nettype none
module b1_top #(
    parameter [63:0]  NONCE_SEED = 64'h9E3779B97F4A7C15,
    parameter integer LUTS       = 6,
    parameter integer SEMANTIC_GATE = 0,
    parameter [31:0]  VARIANT_WORD = 32'h42310001
) ();
    `include "carrier_base_init.vh"
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

    carrier_axi3_lite #(.ID_W(12), .ADDR_W(16)) axi3 (
        .clk(clk), .rst_n(rst_n),
        .s_awid(ps_awid), .s_awaddr(ps_awaddr), .s_awlen(ps_awlen), .s_awsize({1'b0, ps_awsize}), .s_awburst(ps_awburst),
        .s_awvalid(ps_awvalid), .s_awready(ps_awready),
        .s_wid(ps_wid), .s_wdata(ps_wdata), .s_wstrb(ps_wstrb), .s_wlast(ps_wlast), .s_wvalid(ps_wvalid), .s_wready(ps_wready),
        .s_bid(ps_bid), .s_bresp(ps_bresp), .s_bvalid(ps_bvalid), .s_bready(ps_bready),
        .s_arid(ps_arid), .s_araddr(ps_araddr), .s_arlen(ps_arlen), .s_arsize({1'b0, ps_arsize}), .s_arburst(ps_arburst),
        .s_arvalid(ps_arvalid), .s_arready(ps_arready),
        .s_rid(ps_rid), .s_rdata(ps_rdata), .s_rresp(ps_rresp), .s_rlast(ps_rlast), .s_rvalid(ps_rvalid), .s_rready(ps_rready),
        .m_awaddr(m_awaddr), .m_awvalid(m_awvalid), .m_awready(m_awready),
        .m_wdata(m_wdata), .m_wstrb(m_wstrb), .m_wvalid(m_wvalid), .m_wready(m_wready),
        .m_bresp(m_bresp), .m_bvalid(m_bvalid), .m_bready(m_bready),
        .m_araddr(m_araddr), .m_arvalid(m_arvalid), .m_arready(m_arready),
        .m_rdata(m_rdata), .m_rresp(m_rresp), .m_rvalid(m_rvalid), .m_rready(m_rready));

    wire [5:0] vector; wire [LUTS-1:0] lut_q;
    b1_core #(.NONCE_SEED(NONCE_SEED), .LUTS(LUTS), .SEMANTIC_GATE(SEMANTIC_GATE), .VARIANT_WORD(VARIANT_WORD)) core (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(m_awaddr), .s_awvalid(m_awvalid), .s_awready(m_awready),
        .s_wdata(m_wdata), .s_wstrb(m_wstrb), .s_wvalid(m_wvalid), .s_wready(m_wready),
        .s_bresp(m_bresp), .s_bvalid(m_bvalid), .s_bready(m_bready),
        .s_araddr(m_araddr), .s_arvalid(m_arvalid), .s_arready(m_arready),
        .s_rdata(m_rdata), .s_rresp(m_rresp), .s_rvalid(m_rvalid), .s_rready(m_rready),
        .vector(vector), .lut_q(lut_q));

    // The six evolvable LUT6 — same cells, same names, same LOC/LOCK_PINS as the carrier.
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_0)) evolvable_0 (.O(lut_q[0]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]), .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_1)) evolvable_1 (.O(lut_q[1]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]), .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_2)) evolvable_2 (.O(lut_q[2]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]), .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_3)) evolvable_3 (.O(lut_q[3]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]), .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_4)) evolvable_4 (.O(lut_q[4]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]), .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_5)) evolvable_5 (.O(lut_q[5]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]), .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));
endmodule
`default_nettype wire
