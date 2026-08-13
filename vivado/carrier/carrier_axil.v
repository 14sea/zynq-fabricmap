// Claim B round 1 carrier — AXI4-Lite slave: the word stream, the readback window and the
// register file.
//
// THERE IS NO CANDIDATE BUFFER ANY MORE. The frame-staged engine consumes the envelope as
// it arrives and stages exactly one frame, so the AXI write channel IS the word stream:
// one write to the STREAM window is one word, and `word_ready` is the backpressure. The
// 536-word buffer it replaces cost 288 LUTs of SLICEM in a region that must also hold two
// of the evolvable LUTs. (The region is SLICE_X0Y0:X1Y99 plus SLICE_X6Y0:X7Y99 — about
// 1,600 LUTs, not the single 800-LUT block an earlier note assumed; the erratum-003 build
// used 816. The budget argument for removing the buffer stands either way.)
//
// Three windows off one GP0 slave:
//   0x0000            STREAM   W: one word of the envelope, in order
//   0x1000 .. 0x1193  RDBACK   R: the 101 words of the frame the engine has verified
//                                  (first word 0x1000, LAST WORD 0x1190; 0x118F would be
//                                   100 words and stop one short — the decode below is
//                                   right, this line was not, corrected 2026-08-13)
//   0x2000 ..         registers
//
//   0x2000  CTRL      W: bit1 begin_txn    bit2 start_pass1   bit3 start_pass2
//                        bits5:4 env_index bit6 arm           bit7 mode_holdout
//                        bit8 rb_ack
//   0x2004  STATUS    R: bit0 busy, bit1 fault, bit2 configuration_valid,
//                        bit3 scorer_busy, bit4 scorer_done, bit5 scorer_armed,
//                        bit6 pass1_complete, bit7 recovery_required,
//                        bits9:8 expect_env, bit10 rb_frame_ready,
//                        bits13:11 env_committed, bits17:14 rb_frames_ok,
//                        bits25:18 rb_latency_words, bit26 rb_latency_valid,
//                        bits31:27 RESERVED and read zero
//   0x2008  FAULT     R: bits3:0 fault code
//   0x2010  SCORE0..  R: six per-LUT match counts, one per register
//
// `configuration_valid` is READ-ONLY BY CONSTRUCTION: it is an input to this module and
// appears only in the STATUS read multiplexer. There is no address that writes it, which is
// the first of the four properties ruled for the guard — a register file that offered one
// would make the whole interlock a formality. The same holds for `recovery_required`,
// `env_committed` and `rb_frames_ok`.

`default_nettype none

module carrier_axil #(
    parameter integer FRAME_WORDS = 101,
    parameter integer LUTS        = 6
) (
    input  wire        clk,
    input  wire        rst_n,

    // AXI4-Lite (32-bit)
    input  wire [15:0] s_awaddr,
    input  wire        s_awvalid,
    output wire        s_awready,
    input  wire [31:0] s_wdata,
    input  wire [3:0]  s_wstrb,
    input  wire        s_wvalid,
    output wire        s_wready,
    output reg  [1:0]  s_bresp,
    output reg         s_bvalid,
    input  wire        s_bready,
    input  wire [15:0] s_araddr,
    input  wire        s_arvalid,
    output wire        s_arready,
    output wire [31:0] s_rdata,
    output reg  [1:0]  s_rresp,
    output reg         s_rvalid,
    input  wire        s_rready,

    // the word stream to the engine
    output wire        word_valid,
    output wire [31:0] word_data,
    input  wire        word_ready,
    input  wire        stream_open,     // the engine is in a phase that consumes words
    // Pulsed for exactly one cycle per stream write that arrives with no pass open. The AXI
    // side of such a write COMPLETES with OKAY so the host's `cp.l` can drain; the word is
    // not delivered to the engine, and this tells the engine to latch a refusal instead.
    output reg         stream_refused,

    // the engine's staging memory, read through here by the host
    output wire [6:0]  rb_raddr,
    input  wire [31:0] rb_rdata,

    // control pulses
    output reg         ctrl_begin_txn,
    output reg         ctrl_pass1,
    output reg         ctrl_pass2,
    output reg  [1:0]  ctrl_env_index,
    output reg         ctrl_arm,
    output reg         ctrl_mode_holdout,
    output reg         ctrl_rb_ack,

    // status in
    input  wire        txn_busy,
    input  wire        txn_fault,
    input  wire [3:0]  txn_fault_code,
    input  wire        pass1_complete,
    input  wire        recovery_required,
    input  wire [1:0]  expect_env,
    input  wire [2:0]  env_committed,
    input  wire        rb_frame_ready,
    input  wire [3:0]  rb_frames_ok,
    // telemetry only: reported, never acted on (carrier_stream.v)
    input  wire [7:0]  rb_latency,
    input  wire        rb_latency_valid,
    input  wire        configuration_valid,
    input  wire        scorer_busy,
    input  wire        scorer_done,
    input  wire        scorer_armed,
    input  wire [LUTS*8-1:0] score_flat
);
    localparam [15:0] RB_BASE  = 16'h1000;
    localparam [15:0] REG_BASE = 16'h2000;

    // ------------------------------------------------------------------ write channel
    //
    // A STREAM write completes when the engine takes the word, so an AXI write is the
    // handshake and no separate "loaded_words" bookkeeping exists to disagree with the
    // engine's own position counter. A stream write while the engine is NOT consuming
    // completes with **OKAY** and raises `stream_refused`, which the engine latches as a
    // sticky fault; it does not stall and it does not answer SLVERR. (This comment said
    // SLVERR until 2026-08-13 — it described the behaviour erratum 003 removed, because an
    // AXI error response on this board reaches the A9 as a data abort and resets it. The
    // code below has been right since erratum 003; only this paragraph was stale.)
    // Inside a pass the stall is bounded — four cycles for the CRC, at most one frame while
    // a verified frame is emitted.
    wire        wr_addr_ok  = s_awvalid && s_wvalid && !s_bvalid;
    wire        wr_is_reg   = (s_awaddr >= REG_BASE);
    wire        wr_is_strm  = (s_awaddr <  RB_BASE);
    wire        strm_stall  = wr_is_strm && stream_open && !word_ready;
    wire        wr_fire     = wr_addr_ok && !strm_stall;

    assign      s_awready   = wr_fire;
    assign      s_wready    = wr_fire;

    // the stream handshake: exactly the cycle the AXI write of a stream word completes
    assign      word_valid  = wr_addr_ok && wr_is_strm && stream_open;
    assign      word_data   = s_wdata;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stream_refused    <= 1'b0;
            s_bvalid          <= 1'b0;
            s_bresp           <= 2'b00;
            ctrl_begin_txn    <= 1'b0;
            ctrl_pass1        <= 1'b0;
            ctrl_pass2        <= 1'b0;
            ctrl_env_index    <= 2'd0;
            ctrl_arm          <= 1'b0;
            ctrl_mode_holdout <= 1'b0;
            ctrl_rb_ack       <= 1'b0;
        end else begin
            stream_refused <= 1'b0;   // one-cycle pulse, like the ctrl strobes
            ctrl_begin_txn <= 1'b0;   // one-cycle pulses
            ctrl_pass1     <= 1'b0;
            ctrl_pass2     <= 1'b0;
            ctrl_arm       <= 1'b0;
            ctrl_rb_ack    <= 1'b0;

            if (wr_fire) begin
                s_bvalid <= 1'b1;
                s_bresp  <= 2'b00;
                if (wr_is_reg) begin
                    case (s_awaddr)
                        REG_BASE: begin
                            ctrl_begin_txn    <= s_wdata[1];
                            ctrl_pass1        <= s_wdata[2];
                            ctrl_pass2        <= s_wdata[3];
                            ctrl_env_index    <= s_wdata[5:4];
                            ctrl_arm          <= s_wdata[6];
                            ctrl_mode_holdout <= s_wdata[7];
                            ctrl_rb_ack       <= s_wdata[8];
                        end
                        default: s_bresp <= 2'b10;   // SLVERR: nothing else is writable
                    endcase
                end else if (wr_is_strm) begin
                    // Taken by the engine this cycle, or refused because no pass is open.
                    //
                    // A refusal used to answer SLVERR. Under this board's U-Boot an AXI error
                    // response reaches the A9 as a data abort, `panic()` runs and -- with
                    // CONFIG_PANIC_HANG unset -- resets the CPU. So the one channel the guard
                    // had for saying no destroyed the host and the evidence with it: a whole
                    // no-op calibration came back as a boot banner. The refusal is now
                    // reported in STATUS/FAULT instead, and the bus is allowed to finish.
                    //
                    // "AXI OKAY" therefore means the transfer completed, NOT that the
                    // candidate was accepted. The host must read FAULT after `cp.l` returns.
                    if (!stream_open) stream_refused <= 1'b1;
                end else begin
                    s_bresp <= 2'b10;   // the readback window is read-only
                end
            end else if (s_bvalid && s_bready) begin
                s_bvalid <= 1'b0;
            end
        end
    end

    // ------------------------------------------------------------------- read channel
    //
    // There is NO array here. The readback words live in the engine's staging memory — the
    // same array, written by the same transfer that fed the CRC — and this module only
    // presents an address to it. A second 101-word copy cost 88 LUTs of SLICEM.
    assign rb_raddr = s_araddr[8:2];

    wire rd_is_rb = (s_araddr >= RB_BASE) && (s_araddr < REG_BASE) &&
                    (rb_raddr < FRAME_WORDS);

    // The engine's read is asynchronous, so `rb_rdata` is the word at the address presented
    // this cycle; R is driven the cycle after AR is accepted, and the address is still on
    // `s_araddr` only while AR is valid. It is therefore registered here.
    reg [31:0] rb_hold;
    always @(posedge clk) rb_hold <= rb_rdata;

    reg [31:0] rdata_reg;
    assign s_rdata = rd_was_rb ? rb_hold : rdata_reg;

    // SYNCHRONOUS read: the address is presented in the cycle AR is accepted and the datum
    // is available the next, which is the cycle R is driven.
    reg rd_was_rb;
    assign s_arready = s_arvalid && !s_rvalid;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_rvalid  <= 1'b0;
            s_rresp   <= 2'b00;
            rdata_reg <= 32'd0;
            rd_was_rb <= 1'b0;
        end else if (s_arvalid && !s_rvalid) begin
            s_rvalid  <= 1'b1;
            s_rresp   <= 2'b00;
            rd_was_rb <= rd_is_rb;
            if (s_araddr >= REG_BASE) begin
                case (s_araddr)
                    // 5 + 1 + 8 + 4 + 3 + 1 + 2 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 = 32.
                    // The top five bits stay reserved and read zero, and the host still
                    // refuses a STATUS word that has any of them set.
                    REG_BASE + 16'h0004:
                        rdata_reg <= {5'd0, rb_latency_valid, rb_latency,
                                    rb_frames_ok, env_committed, rb_frame_ready,
                                    expect_env, recovery_required, pass1_complete,
                                    scorer_armed, scorer_done, scorer_busy,
                                    configuration_valid, txn_fault, txn_busy};
                    REG_BASE + 16'h0008:
                        rdata_reg <= {28'd0, txn_fault_code};
                    default: begin
                        if (s_araddr >= REG_BASE + 16'h0010 &&
                            s_araddr <  REG_BASE + 16'h0010 + LUTS*4) begin
                            rdata_reg <= {24'd0,
                                        score_flat[(s_araddr[7:2] - 4) * 8 +: 8]};
                        end else begin
                            rdata_reg <= 32'd0;
                            s_rresp   <= 2'b10;
                        end
                    end
                endcase
            end else if (!rd_is_rb) begin
                // the stream window is write-only, and so is anything unmapped
                rdata_reg <= 32'd0;
                s_rresp   <= 2'b10;
            end
        end else if (s_rvalid && s_rready) begin
            s_rvalid  <= 1'b0;
            rd_was_rb <= 1'b0;
        end
    end
endmodule

`default_nettype wire
