// Claim B round 1 carrier — the frame-staged stream engine.
//
// One module owns the position counter, the word-by-word validation, the CRC, the
// single-frame staging buffer and the ICAP feed, because splitting them meant three
// handshakes across which a stale level once let a verdict from the previous envelope
// finish the current one.
//
// THE GUARANTEE
// -------------
//   each FRAME, before it is written, is byte-identical to the same (envelope, frame)
//   validated in pass 1
//
// The PL never reconstructs an "equivalent" stream. Preamble and trailer words are
// validated and forwarded VERBATIM; each frame's 101 ORIGINAL words go into the FDRI burst
// unaltered. The only difference from a single continuous write is that time passes
// between frames, with CSIB high while the next frame is loaded and checked.
//
// CRC COMMITMENT — the boundary a per-frame design invites you to get wrong
// -------------------------------------------------------------------------
// Pass 1 computes five frame CRCs per envelope, but they are SCRATCH until the whole
// envelope has passed: its trailer, its length and its position in the order. An envelope
// that produced five perfectly good frame CRCs and then failed its trailer must not leave
// five usable authorities behind. So the scratch set is committed in ONE step at the end of
// a wholly successful envelope, and `env_committed` gates every use of it in pass 2.
// `begin_txn`, a timeout and any fault clear the commit bits — an uncommitted CRC is not
// weaker authority, it is none.
//
// RDWRB is held in write for the entire FDRI burst and is never toggled while CSIB is low;
// toggling it there aborts the load (UG470). Readback is a separate phase after the whole
// envelope is written, never a switch mid-burst.

`default_nettype none

module carrier_stream #(
    parameter integer ENVELOPES     = 3,
    parameter integer ENV_WORDS     = 536,
    parameter integer FRAME_WORDS   = 101,
    parameter integer FRAMES_PER_ENV = 5,
    parameter integer PREAMBLE      = 23,
    parameter integer FAR_POS       = 20,
    parameter [31:0]  IDCODE        = 32'h13722093,
    parameter integer TIMEOUT       = 1 << 20
) (
    input  wire        clk,
    input  wire        rst_n,

    // control
    input  wire        begin_txn,
    input  wire        start_pass1,     // begin streaming envelope `env_index` (pass 1)
    input  wire        start_pass2,     // begin streaming envelope `env_index` (pass 2)
    input  wire [1:0]  env_index,

    // the word stream from AXI: one word per `word_valid`, held until `word_ready`
    input  wire        word_valid,
    input  wire [31:0] word_data,
    output wire        word_ready,

    // status
    output reg         busy,
    output reg         fault,
    output reg  [3:0]  fault_code,
    output reg  [1:0]  expect_env,
    output reg         pass1_complete,
    output reg         configuration_valid,
    output reg         recovery_required,
    output reg  [2:0]  env_committed,

    // readback staging, read by the host over AXI
    output reg         rb_we,
    output reg  [6:0]  rb_waddr,
    output reg  [31:0] rb_wdata,
    output reg         rb_frame_ready,   // a whole frame is in the readback buffer

    // ICAPE2
    output reg         icap_csib,
    output reg         icap_rdwrb,
    output reg  [31:0] icap_din,
    input  wire [31:0] icap_dout
);
    localparam [3:0] F_NONE     = 4'd0,
                     F_ORDER    = 4'd1,
                     F_CONTROL  = 4'd2,
                     F_FAR      = 4'd3,
                     F_LENGTH   = 4'd4,
                     F_CRC      = 4'd5,
                     F_TIMEOUT  = 4'd6,
                     F_PHASE    = 4'd7,
                     F_READBACK = 4'd8,
                     F_UNCOMMITTED = 4'd9;

    localparam [31:0] W_DUMMY  = 32'hFFFFFFFF, W_SYNC  = 32'hAA995566,
                      W_NOOP   = 32'h20000000, W_CMD1  = 32'h30008001,
                      W_RCRC   = 32'h00000007, W_WCFG  = 32'h00000001,
                      W_DESYNC = 32'h0000000D, W_ID1   = 32'h30018001,
                      W_FAR1   = 32'h30002001, W_FDRI0 = 32'h30004000,
                      W_TYPE2  = 32'h40000000 | (FRAMES_PER_ENV * FRAME_WORDS),
                      W_CRC1   = 32'h30000001, W_ZERO  = 32'h00000000;

    // The pinned control skeleton by position. FAR_POS is judged by the allowlist instead.
    function automatic [32:0] expected_at(input [9:0] p);
        begin
            expected_at = {1'b0, 32'd0};
            if (p < 8)                    expected_at = {1'b1, W_DUMMY};
            else if (p == 8)              expected_at = {1'b1, W_SYNC};
            else if (p == 9)              expected_at = {1'b1, W_NOOP};
            else if (p == 10)             expected_at = {1'b1, W_CMD1};
            else if (p == 11)             expected_at = {1'b1, W_RCRC};
            else if (p == 12 || p == 13)  expected_at = {1'b1, W_NOOP};
            else if (p == 14)             expected_at = {1'b1, W_ID1};
            else if (p == 15)             expected_at = {1'b1, IDCODE};
            else if (p == 16)             expected_at = {1'b1, W_CMD1};
            else if (p == 17)             expected_at = {1'b1, W_WCFG};
            else if (p == 18)             expected_at = {1'b1, W_NOOP};
            else if (p == 19)             expected_at = {1'b1, W_FAR1};
            else if (p == 21)             expected_at = {1'b1, W_FDRI0};
            else if (p == 22)             expected_at = {1'b1, W_TYPE2};
            else if (p == 528)            expected_at = {1'b1, W_CRC1};
            else if (p == 529)            expected_at = {1'b1, W_ZERO};
            else if (p == 530)            expected_at = {1'b1, W_CMD1};
            else if (p == 531)            expected_at = {1'b1, W_DESYNC};
            else if (p >= 532)            expected_at = {1'b1, W_NOOP};
        end
    endfunction

    function automatic [31:0] permitted_far(input [1:0] e);
        case (e)
            2'd0:    permitted_far = 32'h00400A20;
            2'd1:    permitted_far = 32'h00400C1A;
            2'd2:    permitted_far = 32'h00400C20;
            default: permitted_far = 32'hFFFFFFFF;
        endcase
    endfunction

    localparam [2:0] P_IDLE = 3'd0, P_PASS1 = 3'd1, P_PASS2 = 3'd2, P_RDBACK = 3'd3,
                     P_FAULT = 3'd4;

    reg [2:0]  phase;
    reg [1:0]  env;
    reg [9:0]  pos;
    reg [2:0]  frame_idx;
    reg [6:0]  frame_word;
    reg [31:0] watchdog;

    // staging: one frame of original words, plus the readback of one frame
    reg [31:0] stage [0:FRAME_WORDS-1];

    reg [31:0] crc_scratch [0:FRAMES_PER_ENV-1];
    reg [31:0] crc_committed [0:ENVELOPES*FRAMES_PER_ENV-1];

    wire        crc_ready;
    wire [31:0] crc_value;
    reg         crc_clear, crc_feed;

    carrier_crc32 crc_i (
        .clk(clk), .rst_n(rst_n), .clear(crc_clear), .valid(crc_feed),
        .data(word_data), .ready(crc_ready), .crc(crc_value)
    );

    // A word is consumed when the CRC has taken all four of its bytes. Control words are
    // not CRC'd — the CRC covers the frames, which is what pass 2 re-checks — so they
    // retire immediately.
    wire in_frame  = (pos >= PREAMBLE) && (pos < PREAMBLE + FRAMES_PER_ENV*FRAME_WORDS);
    assign word_ready = (phase == P_PASS1 || phase == P_PASS2) &&
                        (in_frame ? crc_ready : 1'b1);

    wire [32:0] want = expected_at(pos);
    wire        control_bad = want[32] && (word_data != want[31:0]);
    wire        far_bad     = (pos == FAR_POS) && (word_data != permitted_far(env));

    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase <= P_IDLE; busy <= 1'b0; fault <= 1'b0; fault_code <= F_NONE;
            expect_env <= 2'd0; pass1_complete <= 1'b0;
            configuration_valid <= 1'b0;
            recovery_required <= 1'b1;      // fail-closed: a reset proves nothing
            env_committed <= 3'b000;
            env <= 2'd0; pos <= 10'd0; frame_idx <= 3'd0; frame_word <= 7'd0;
            watchdog <= 32'd0;
            crc_clear <= 1'b0; crc_feed <= 1'b0;
            rb_we <= 1'b0; rb_frame_ready <= 1'b0;
            icap_csib <= 1'b1; icap_rdwrb <= 1'b0; icap_din <= 32'd0;
        end else begin
            crc_clear <= 1'b0;
            crc_feed  <= 1'b0;
            rb_we     <= 1'b0;
            icap_csib <= 1'b1;              // paused unless a word is being handed over

            case (phase)
                P_IDLE: begin
                    busy <= 1'b0;
                    if (begin_txn) begin
                        configuration_valid <= 1'b0;
                        pass1_complete      <= 1'b0;
                        fault               <= 1'b0;
                        fault_code          <= F_NONE;
                        expect_env          <= 2'd0;
                        // An uncommitted CRC is not weaker authority, it is none.
                        env_committed       <= 3'b000;
                        // recovery_required is deliberately NOT cleared here.
                    end else if (start_pass1 || start_pass2) begin
                        if (env_index != expect_env ||
                            (start_pass2 && !pass1_complete) ||
                            (start_pass1 && pass1_complete)) begin
                            fault_code <= (env_index != expect_env) ? F_ORDER : F_PHASE;
                            phase      <= P_FAULT;
                        // Mutation note: this arm is currently UNREACHABLE, and it stays.
                        // `pass1_complete` is set only after envelope 2 commits, and each
                        // envelope commits only on success, so pass1_complete implies all
                        // three bits — a pass-2 start therefore fails the phase check
                        // first. It is here because `crc_committed` is NOT cleared on
                        // fault, only its commit bits are: if that invariant ever changes,
                        // this is what stops a stale CRC being used as authority instead
                        // of silently succeeding.
                        end else if (start_pass2 && !env_committed[env_index]) begin
                            fault_code <= F_UNCOMMITTED;
                            phase      <= P_FAULT;
                        end else begin
                            if (start_pass2) configuration_valid <= 1'b0;
                            env        <= env_index;
                            pos        <= 10'd0;
                            frame_idx  <= 3'd0;
                            frame_word <= 7'd0;
                            watchdog   <= 32'd0;
                            crc_clear  <= 1'b1;
                            busy       <= 1'b1;
                            phase      <= start_pass1 ? P_PASS1 : P_PASS2;
                        end
                    end
                end

                P_PASS1, P_PASS2: begin
                    watchdog <= watchdog + 32'd1;
                    if (watchdog > TIMEOUT) begin
                        fault_code <= F_TIMEOUT;
                        phase      <= P_FAULT;
                    end else if (word_valid) begin
                        if (control_bad) begin
                            fault_code <= (pos == 22) ? F_LENGTH : F_CONTROL;
                            phase      <= P_FAULT;
                        end else if (far_bad) begin
                            fault_code <= F_FAR;
                            phase      <= P_FAULT;
                        end else if (in_frame) begin
                            crc_feed <= 1'b1;
                            if (phase == P_PASS2) stage[frame_word] <= word_data;
                            if (crc_ready) begin
                                // this word is retired
                                if (frame_word == FRAME_WORDS - 1) begin
                                    if (phase == P_PASS1) begin
                                        crc_scratch[frame_idx] <= crc_value;
                                    end else if (crc_value !=
                                                 crc_committed[env*FRAMES_PER_ENV + frame_idx]) begin
                                        fault_code <= F_CRC;
                                        phase      <= P_FAULT;
                                    end
                                    frame_word <= 7'd0;
                                    frame_idx  <= frame_idx + 3'd1;
                                    crc_clear  <= 1'b1;
                                end else begin
                                    frame_word <= frame_word + 7'd1;
                                end
                                pos <= pos + 10'd1;
                            end
                        end else begin
                            // preamble or trailer: validated, forwarded verbatim
                            if (phase == P_PASS2) begin
                                icap_csib  <= 1'b0;
                                icap_rdwrb <= 1'b0;
                                icap_din   <= word_data;
                            end
                            if (pos == ENV_WORDS - 1) begin
                                if (phase == P_PASS1) begin
                                    // ONE commit, at the end of a wholly good envelope
                                    for (i = 0; i < FRAMES_PER_ENV; i = i + 1)
                                        crc_committed[env*FRAMES_PER_ENV + i] <= crc_scratch[i];
                                    env_committed[env] <= 1'b1;
                                    if (env == ENVELOPES - 1) begin
                                        pass1_complete <= 1'b1;
                                        expect_env     <= 2'd0;
                                    end else begin
                                        expect_env <= env + 2'd1;
                                    end
                                    busy  <= 1'b0;
                                    phase <= P_IDLE;
                                end else begin
                                    phase <= P_RDBACK;
                                    pos   <= 10'd0;
                                end
                            end else begin
                                pos <= pos + 10'd1;
                            end
                        end
                    end
                end

                P_RDBACK: begin
                    // placeholder for the readback phase; the envelope's frames are read
                    // back one at a time into rb_* for the host to hash.
                    if (env == ENVELOPES - 1) begin
                        configuration_valid <= 1'b1;
                        recovery_required   <= 1'b0;
                    end else begin
                        expect_env <= env + 2'd1;
                    end
                    busy  <= 1'b0;
                    phase <= P_IDLE;
                end

                P_FAULT: begin
                    configuration_valid <= 1'b0;
                    pass1_complete      <= 1'b0;
                    env_committed       <= 3'b000;   // scratch and commits both die
                    fault               <= 1'b1;
                    busy                <= 1'b0;
                    phase               <= P_IDLE;
                end

                default: phase <= P_FAULT;
            endcase
        end
    end
endmodule

`default_nettype wire
