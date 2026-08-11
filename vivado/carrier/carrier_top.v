// Claim B round 1 carrier — top level.
//
// PS7 (GP0 master) -> AXI4-Lite slave -> word stream + readback window + registers
//                                     -> frame-staged stream engine -> ICAPE2
//                                     -> scorer -> six evolvable LUT6
//
// The validator, the CRC, the transaction FSM and the guard used to be four modules with
// three handshakes between them, and a level that survived from one envelope to the next
// once let a stale verdict finish the current one. They are now ONE module,
// `carrier_stream`, which owns the position counter, the word-by-word validation, the CRC,
// the single-frame staging and the ICAP feed together.
//
// The evolvable LUTs are the ONLY cells permitted in the target column segments, they are
// `DONT_TOUCH` so nothing absorbs them, and their pin mapping is locked in the XDC. The
// certified addresses are INIT bits under `I0:A1 … I5:A6`; a permuted mapping would put
// the same truth table on different bits and silently invalidate every address in the map,
// while everything continued to look correct.

`default_nettype none

// NO PORTS. The carrier has no board IO: the PS reaches it through PS7/GP0 and the ICAP is
// internal. A tied-off `led[3:0]` existed and stopped write_bitstream on unconstrained-IO
// DRC — the right answer is not to waive the DRC or to invent pin constraints for a signal
// nothing drives, but to not have the port.
module carrier_top #(
    parameter integer LUTS        = 6,
    parameter integer FRAME_WORDS = 101   // the readback window; the engine stages one frame
) ();
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
    wire        ctrl_begin_txn, ctrl_pass1, ctrl_pass2, ctrl_arm, ctrl_mode_holdout,
                ctrl_rb_ack;
    wire [1:0]  ctrl_env_index;

    wire        txn_busy, txn_fault, configuration_valid, pass1_complete,
                recovery_required, rb_frame_ready, stream_open;
    wire [3:0]  txn_fault_code, rb_frames_ok;
    wire [1:0]  expect_env;
    wire [2:0]  env_committed;
    wire        word_valid, word_ready;
    wire [31:0] word_data, rb_rdata;
    wire [6:0]  rb_raddr;
    wire        scorer_busy, scorer_done, scorer_armed;
    wire [LUTS*8-1:0] score_flat;

    carrier_axil #(.FRAME_WORDS(FRAME_WORDS), .LUTS(LUTS)) axil (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(m_awaddr[15:0]), .s_awvalid(m_awvalid), .s_awready(m_awready),
        .s_wdata(m_wdata), .s_wstrb(m_wstrb), .s_wvalid(m_wvalid), .s_wready(m_wready),
        .s_bresp(m_bresp), .s_bvalid(m_bvalid), .s_bready(m_bready),
        .s_araddr(m_araddr[15:0]), .s_arvalid(m_arvalid), .s_arready(m_arready),
        .s_rdata(m_rdata), .s_rresp(m_rresp), .s_rvalid(m_rvalid), .s_rready(m_rready),
        .word_valid(word_valid), .word_data(word_data), .word_ready(word_ready),
        .stream_open(stream_open),
        .rb_raddr(rb_raddr), .rb_rdata(rb_rdata),
        .ctrl_begin_txn(ctrl_begin_txn),
        .ctrl_pass1(ctrl_pass1), .ctrl_pass2(ctrl_pass2),
        .ctrl_env_index(ctrl_env_index),
        .ctrl_arm(ctrl_arm), .ctrl_mode_holdout(ctrl_mode_holdout),
        .ctrl_rb_ack(ctrl_rb_ack),
        .txn_busy(txn_busy), .txn_fault(txn_fault), .txn_fault_code(txn_fault_code),
        .pass1_complete(pass1_complete), .recovery_required(recovery_required),
        .expect_env(expect_env), .env_committed(env_committed),
        .rb_frame_ready(rb_frame_ready), .rb_frames_ok(rb_frames_ok),
        .configuration_valid(configuration_valid),
        .scorer_busy(scorer_busy), .scorer_done(scorer_done), .scorer_armed(scorer_armed),
        .score_flat(score_flat)
    );

    // ------------------------------------- the frame-staged stream engine, then ICAPE2
    wire        icap_csib, icap_rdwrb;
    wire [31:0] icap_din, icap_dout;

    carrier_stream #(.ENV_WORDS(ENV_WORDS), .FRAME_WORDS(FRAME_WORDS)) stream (
        .clk(clk), .rst_n(rst_n),
        .begin_txn(ctrl_begin_txn),
        .start_pass1(ctrl_pass1), .start_pass2(ctrl_pass2),
        .env_index(ctrl_env_index),
        .word_valid(word_valid), .word_data(word_data), .word_ready(word_ready),
        .stream_open(stream_open),
        .busy(txn_busy), .fault(txn_fault), .fault_code(txn_fault_code),
        .expect_env(expect_env), .pass1_complete(pass1_complete),
        .configuration_valid(configuration_valid),
        .recovery_required(recovery_required), .env_committed(env_committed),
        .host_raddr(rb_raddr), .host_rdata(rb_rdata),
        .rb_frame_ready(rb_frame_ready), .rb_ack(ctrl_rb_ack),
        .rb_frames_ok(rb_frames_ok),
        .icap_csib(icap_csib), .icap_rdwrb(icap_rdwrb),
        .icap_din(icap_din), .icap_dout(icap_dout)
    );

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
        .recovery_required(recovery_required),
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

endmodule

`default_nettype wire
