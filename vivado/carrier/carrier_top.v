// Claim B round 1 carrier — top level.
//
// PS7 (GP0 master) -> AXI4-Lite slave -> candidate buffer + registers
//                                     -> envelope validator -> guard -> ICAPE2
//                                     -> scorer -> six evolvable LUT6
//
// The evolvable LUTs are the ONLY cells permitted in the target column segments, they are
// `DONT_TOUCH` so nothing absorbs them, and their pin mapping is locked in the XDC. The
// certified addresses are INIT bits under `I0:A1 … I5:A6`; a permuted mapping would put
// the same truth table on different bits and silently invalidate every address in the map,
// while everything continued to look correct.

`default_nettype none

module carrier_top #(
    parameter integer LUTS      = 6,
    parameter integer BUF_WORDS = 1608
) (
    output wire [3:0] led    // tied off; the design has no board IO of its own
);
    localparam integer ENV_WORDS = 536;

    `include "carrier_base_init.vh"

    wire clk;
    wire rst_n;

    // ------------------------------------------------------------------------ PS7
    wire [31:0] m_awaddr, m_wdata, m_araddr, m_rdata;
    wire        m_awvalid, m_awready, m_wvalid, m_wready, m_bvalid, m_bready;
    wire        m_arvalid, m_arready, m_rvalid, m_rready;
    wire [1:0]  m_bresp, m_rresp;
    wire [3:0]  m_wstrb;
    wire        fclk0, frst0_n;

    assign clk   = fclk0;
    assign rst_n = frst0_n;

    PS7 ps7 (
        .FCLKCLK        ({3'b000, fclk0}),
        .FCLKRESETN     ({3'b000, frst0_n}),
        .MAXIGP0ACLK    (clk),
        .MAXIGP0ARESETN (),
        .MAXIGP0AWADDR  (m_awaddr),
        .MAXIGP0AWVALID (m_awvalid),
        .MAXIGP0AWREADY (m_awready),
        .MAXIGP0WDATA   (m_wdata),
        .MAXIGP0WSTRB   (m_wstrb),
        .MAXIGP0WVALID  (m_wvalid),
        .MAXIGP0WREADY  (m_wready),
        .MAXIGP0BRESP   (m_bresp),
        .MAXIGP0BVALID  (m_bvalid),
        .MAXIGP0BREADY  (m_bready),
        .MAXIGP0ARADDR  (m_araddr),
        .MAXIGP0ARVALID (m_arvalid),
        .MAXIGP0ARREADY (m_arready),
        .MAXIGP0RDATA   (m_rdata),
        .MAXIGP0RRESP   (m_rresp),
        .MAXIGP0RVALID  (m_rvalid),
        .MAXIGP0RREADY  (m_rready)
    );

    // ------------------------------------------------------------------ AXI-Lite slave
    wire [11:0] buf_raddr;
    wire [31:0] buf_rdata;
    wire [11:0] loaded_words;
    wire        ctrl_go, ctrl_arm, ctrl_mode_holdout;

    wire        guard_busy, guard_fault, configuration_valid;
    wire [3:0]  guard_fault_code;
    wire [11:0] guard_fault_word;
    wire        scorer_busy, scorer_done, scorer_armed;
    wire [LUTS*8-1:0] score_flat;

    carrier_axil #(.BUF_WORDS(BUF_WORDS), .LUTS(LUTS)) axil (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(m_awaddr[15:0]), .s_awvalid(m_awvalid), .s_awready(m_awready),
        .s_wdata(m_wdata), .s_wstrb(m_wstrb), .s_wvalid(m_wvalid), .s_wready(m_wready),
        .s_bresp(m_bresp), .s_bvalid(m_bvalid), .s_bready(m_bready),
        .s_araddr(m_araddr[15:0]), .s_arvalid(m_arvalid), .s_arready(m_arready),
        .s_rdata(m_rdata), .s_rresp(m_rresp), .s_rvalid(m_rvalid), .s_rready(m_rready),
        .buf_raddr(buf_raddr), .buf_rdata(buf_rdata), .loaded_words(loaded_words),
        .ctrl_go(ctrl_go), .ctrl_arm(ctrl_arm), .ctrl_mode_holdout(ctrl_mode_holdout),
        .guard_busy(guard_busy), .guard_fault(guard_fault),
        .guard_fault_code(guard_fault_code), .guard_fault_word(guard_fault_word),
        .configuration_valid(configuration_valid),
        .scorer_busy(scorer_busy), .scorer_done(scorer_done), .scorer_armed(scorer_armed),
        .score_flat(score_flat)
    );

    // ---------------------------------------------- validator, then guard, then ICAPE2
    wire [11:0] val_addr, guard_addr;
    wire        val_busy, val_ok, val_fault;
    wire [3:0]  val_fault_code;
    wire [11:0] val_fault_word;
    wire        guard_start;

    carrier_envelope validator (
        .clk(clk), .rst_n(rst_n),
        .start(ctrl_go), .loaded_words(loaded_words),
        .buf_addr(val_addr), .buf_data(buf_rdata),
        .busy(val_busy), .ok(val_ok), .fault(val_fault),
        .fault_code(val_fault_code), .fault_word(val_fault_word)
    );

    // The guard runs ONLY on a validated buffer: validation is a complete pass, and the
    // start pulse is its `ok`. Nothing reaches ICAPE2 before the whole stream has been
    // judged.
    assign guard_start = val_ok;

    wire        icap_csib, icap_rdwrb;
    wire [31:0] icap_din, icap_dout;

    carrier_guard guard (
        .clk(clk), .rst_n(rst_n),
        .start(guard_start),
        .busy(guard_busy), .fault(guard_fault), .fault_code(guard_fault_code),
        .configuration_valid(configuration_valid),
        .buf_addr(guard_addr), .buf_data(buf_rdata),
        .icap_csib(icap_csib), .icap_rdwrb(icap_rdwrb),
        .icap_din(icap_din), .icap_dout(icap_dout)
    );

    assign guard_fault_word = val_fault ? val_fault_word : 12'd0;
    assign buf_raddr = val_busy ? val_addr : guard_addr;

    ICAPE2 #(.ICAP_WIDTH("X32")) icap (
        .CLK(clk), .CSIB(icap_csib), .RDWRB(icap_rdwrb),
        .I(icap_din), .O(icap_dout)
    );

    // ------------------------------------------------------- scorer + evolvable LUTs
    wire [5:0]      vector;
    wire [LUTS-1:0] lut_q;

    carrier_scorer #(.LUTS(LUTS)) scorer (
        .clk(clk), .rst_n(rst_n),
        .configuration_valid(configuration_valid),
        .arm(ctrl_arm), .mode_holdout(ctrl_mode_holdout),
        .vector(vector), .lut_q(lut_q),
        .busy(scorer_busy), .done(scorer_done), .armed_o(scorer_armed),
        .score_flat(score_flat)
    );

    // The six evolvable LUT6. Their INIT is the frozen base; evolution changes it in the
    // fabric, never here. LOC/BEL and LOCK_PINS are in the XDC.
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_0)) evolvable_0 (
        .O(lut_q[0]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]),
        .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_1)) evolvable_1 (
        .O(lut_q[1]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]),
        .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_2)) evolvable_2 (
        .O(lut_q[2]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]),
        .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_3)) evolvable_3 (
        .O(lut_q[3]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]),
        .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_4)) evolvable_4 (
        .O(lut_q[4]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]),
        .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(BASE_INIT_5)) evolvable_5 (
        .O(lut_q[5]), .I0(vector[0]), .I1(vector[1]), .I2(vector[2]),
        .I3(vector[3]), .I4(vector[4]), .I5(vector[5]));

    assign led = 4'b0000;
endmodule

`default_nettype wire
