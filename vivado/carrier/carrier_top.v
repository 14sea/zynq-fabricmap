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
    parameter integer BUF_WORDS = 536    // one envelope; see the two-pass contract
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
    // FCLKCLK and FCLKRESETN are PS7 OUTPUTS and are 4 bits wide. Driving a
    // concatenation from them is an illegal output expression (Synth 8-315); take the
    // full bus and index it.
    wire [3:0]  fclkclk;
    wire [3:0]  fclkresetn;

    assign clk   = fclkclk[0];
    assign rst_n = fclkresetn[0];

    PS7 ps7 (
        .FCLKCLK        (fclkclk),
        .FCLKRESETN     (fclkresetn),
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
    wire        ctrl_begin_txn, ctrl_validate, ctrl_write, ctrl_arm, ctrl_mode_holdout;
    wire [1:0]  ctrl_env_index;

    wire        txn_busy, txn_fault, configuration_valid, pass1_complete,
                recovery_required;
    wire [3:0]  txn_fault_code;
    wire [1:0]  expect_env;
    wire        txn_we;
    wire [11:0] txn_waddr;
    wire [31:0] txn_wdata;
    wire        scorer_busy, scorer_done, scorer_armed;
    wire [LUTS*8-1:0] score_flat;

    carrier_axil #(.BUF_WORDS(BUF_WORDS), .LUTS(LUTS)) axil (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(m_awaddr[15:0]), .s_awvalid(m_awvalid), .s_awready(m_awready),
        .s_wdata(m_wdata), .s_wstrb(m_wstrb), .s_wvalid(m_wvalid), .s_wready(m_wready),
        .s_bresp(m_bresp), .s_bvalid(m_bvalid), .s_bready(m_bready),
        .s_araddr(m_araddr[15:0]), .s_arvalid(m_arvalid), .s_arready(m_arready),
        .s_rdata(m_rdata), .s_rresp(m_rresp), .s_rvalid(m_rvalid), .s_rready(m_rready),
        .buf_raddr(buf_raddr), .buf_read_busy(val_busy || txn_busy),
        .buf_raddr_out(), .buf_rdata(buf_rdata), .loaded_words(loaded_words),
        .txn_we(txn_we), .txn_waddr(txn_waddr), .txn_wdata(txn_wdata),
        .ctrl_begin_txn(ctrl_begin_txn), .ctrl_validate(ctrl_validate),
        .ctrl_write(ctrl_write), .ctrl_env_index(ctrl_env_index),
        .ctrl_arm(ctrl_arm), .ctrl_mode_holdout(ctrl_mode_holdout),
        .txn_busy(txn_busy), .txn_fault(txn_fault), .txn_fault_code(txn_fault_code),
        .pass1_complete(pass1_complete), .recovery_required(recovery_required),
        .expect_env(expect_env),
        .configuration_valid(configuration_valid),
        .scorer_busy(scorer_busy), .scorer_done(scorer_done), .scorer_armed(scorer_armed),
        .score_flat(score_flat)
    );

    // ------------------------------------- validator + CRC + transaction, then ICAPE2
    wire [11:0] val_addr, txn_addr;
    wire        val_busy, val_ok, val_fault;
    wire [3:0]  val_fault_code;
    wire [11:0] val_fault_word;
    wire        val_start, crc_clear, crc_valid;
    wire [31:0] crc_value;

    carrier_envelope validator (
        .clk(clk), .rst_n(rst_n),
        .start(val_start), .env_index(ctrl_env_index), .loaded_words(loaded_words),
        .buf_addr(val_addr), .buf_data(buf_rdata),
        .busy(val_busy), .ok(val_ok), .fault(val_fault),
        .fault_code(val_fault_code), .fault_word(val_fault_word)
    );

    carrier_crc32 crc (
        .clk(clk), .rst_n(rst_n),
        .clear(crc_clear), .valid(crc_valid), .data(buf_rdata), .crc(crc_value)
    );

    wire        icap_csib, icap_rdwrb;
    wire [31:0] icap_din, icap_dout;

    carrier_txn txn (
        .clk(clk), .rst_n(rst_n),
        .begin_txn(ctrl_begin_txn), .validate_env(ctrl_validate),
        .write_env(ctrl_write), .env_index(ctrl_env_index),
        .busy(txn_busy), .fault(txn_fault), .fault_code(txn_fault_code),
        .expect_env(expect_env), .pass1_complete(pass1_complete),
        .configuration_valid(configuration_valid),
        .recovery_required(recovery_required),
        .buf_addr(txn_addr), .buf_data(buf_rdata),
        .buf_we(txn_we), .buf_waddr(txn_waddr), .buf_wdata(txn_wdata),
        .val_start(val_start), .val_busy(val_busy),
        .val_ok(val_ok), .val_fault(val_fault),
        .crc_clear(crc_clear), .crc_valid(crc_valid), .crc_value(crc_value),
        .icap_csib(icap_csib), .icap_rdwrb(icap_rdwrb),
        .icap_din(icap_din), .icap_dout(icap_dout)
    );

    // one shared read port: the validator drives it while it is busy, the transaction
    // otherwise. They never contend, because the transaction waits for the validator.
    assign buf_raddr = val_busy ? val_addr : txn_addr;

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
