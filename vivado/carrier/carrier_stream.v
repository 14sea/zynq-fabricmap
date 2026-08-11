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
    output wire        stream_open,     // a pass is open: a stream write may stall, not err

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
    input  wire        rb_ack,           // the host has taken it
    output reg  [3:0]  rb_frames_ok,     // frames verified so far in this transaction

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
                     F_UNCOMMITTED = 4'd9,
                     F_BYTECOUNT = 4'd10;

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
                     P_FAULT = 3'd4, P_EMIT = 3'd5;

    localparam integer TOTAL_FRAMES = ENVELOPES * FRAMES_PER_ENV;   // 15

    reg [2:0]  phase;
    reg [2:0]  rb_frame;
    reg [6:0]  emit_word;
    reg [1:0]  env;
    reg [9:0]  pos;
    reg [2:0]  frame_idx;
    reg [6:0]  frame_word;
    reg        awaiting_crc;   // last word of a frame accepted; feeder still draining
    reg [31:0] watchdog;

    // staging: one frame of original words, plus the readback of one frame
    reg [31:0] stage [0:FRAME_WORDS-1];

    reg [31:0] crc_scratch [0:FRAMES_PER_ENV-1];
    reg [31:0] crc_committed [0:ENVELOPES*FRAMES_PER_ENV-1];

    wire        crc_ready, crc_taken, crc_idle;
    wire [15:0] crc_byte_count;
    wire [31:0] crc_value;
    reg         crc_clear;

    // In pass 1/2 the CRC covers the words the HOST sent; during readback it covers the
    // words the DEVICE returned, and comparing the second against the first is the local
    // interlock. One engine, two sources, selected by phase.
    wire [31:0] crc_source = (phase == P_RDBACK) ? icap_dout : word_data;

    // ONE feeder for all three phases; only the source changes. Three phases keeping
    // three sets of counters against one byte stream is exactly how the readback CRC came
    // out as though almost nothing had been consumed.
    wire crc_feed = !awaiting_crc &&
                    (((phase == P_PASS1 || phase == P_PASS2) && word_valid && in_frame)
                     || (phase == P_RDBACK && !rb_frame_ready));

    carrier_crc32 crc_i (
        .clk(clk), .rst_n(rst_n), .clear(crc_clear), .valid(crc_feed),
        .data(crc_source), .ready(crc_ready), .taken(crc_taken), .idle(crc_idle),
        .byte_count(crc_byte_count), .crc(crc_value)
    );

    // A 101-word frame is exactly 404 byte handshakes. Checking the count turns any
    // drift between the feeder and a consumer's index into an observable violation
    // instead of a wrong CRC that looks like a readback failure.
    localparam [15:0] BYTES_PER_FRAME = FRAME_WORDS * 4;

    // A word is consumed when the CRC has taken all four of its bytes. Control words are
    // not CRC'd — the CRC covers the frames, which is what pass 2 re-checks — so they
    // retire immediately.
    wire in_frame  = (pos >= PREAMBLE) && (pos < PREAMBLE + FRAMES_PER_ENV*FRAME_WORDS);
    // A frame word retires on the feeder's ONE advance condition — word_valid && crc_ready
    // — and every index in every phase advances on that same event and nothing else. A
    // control word is not CRC'd and retires at once.
    assign word_ready = (phase == P_PASS1 || phase == P_PASS2) && !awaiting_crc &&
                        (in_frame ? crc_ready : 1'b1);

    // A stream write is stalled while a pass is open and errored when none is: an AXI-Lite
    // write that never completes wedges the PS, so "no pass is open" must be an answer, not
    // a hang. P_EMIT counts as open — the stall there is at most one frame.
    assign stream_open = (phase == P_PASS1) || (phase == P_PASS2) || (phase == P_EMIT);

    wire [32:0] want = expected_at(pos);
    wire        control_bad = want[32] && (word_data != want[31:0]);
    wire        far_bad     = (pos == FAR_POS) && (word_data != permitted_far(env));

    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase <= P_IDLE; busy <= 1'b0; fault <= 1'b0; fault_code <= F_NONE;
            awaiting_crc <= 1'b0;
            expect_env <= 2'd0; pass1_complete <= 1'b0;
            configuration_valid <= 1'b0;
            recovery_required <= 1'b1;      // fail-closed: a reset proves nothing
            env_committed <= 3'b000;
            env <= 2'd0; pos <= 10'd0; frame_idx <= 3'd0; frame_word <= 7'd0;
            watchdog <= 32'd0;
            crc_clear <= 1'b0;
            rb_we <= 1'b0; rb_frame_ready <= 1'b0; rb_frames_ok <= 4'd0;
            rb_frame <= 3'd0;
            icap_csib <= 1'b1; icap_rdwrb <= 1'b0; icap_din <= 32'd0;
        end else begin
            crc_clear <= 1'b0;
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
                        rb_frames_ok        <= 4'd0;
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
                            // Pass 2 is the only phase that writes the fabric, so from
                            // its first word the configuration is partial again: drop the
                            // confirmation AND re-arm recovery. Without the re-arm a
                            // transaction that faulted after a previous one had succeeded
                            // reported "no recovery needed" over a half-written fabric.
                            if (start_pass2) begin
                                configuration_valid <= 1'b0;
                                recovery_required   <= 1'b1;
                            end
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
                    end else if (awaiting_crc) begin
                        // The frame's 101st word was accepted; the feeder is still clocking
                        // out its last bytes. Nothing advances and no word is accepted until
                        // the CRC has settled, so `crc_value` is never read one word early.
                        if (crc_taken) begin
                            awaiting_crc <= 1'b0;
                            frame_word   <= 7'd0;
                            frame_idx    <= frame_idx + 3'd1;
                            crc_clear    <= 1'b1;
                            // A 101-word frame is 404 byte handshakes, no more and no less.
                            // Any drift between the feeder and an index shows up here as a
                            // fault instead of as a CRC that merely looks wrong.
                            if (crc_byte_count != BYTES_PER_FRAME) begin
                                fault_code <= F_BYTECOUNT;
                                phase      <= P_FAULT;
                            end else if (phase == P_PASS1) begin
                                crc_scratch[frame_idx] <= crc_value;
                            end else if (crc_value !=
                                         crc_committed[env*FRAMES_PER_ENV + frame_idx]) begin
                                fault_code <= F_CRC;
                                phase      <= P_FAULT;
                            end else begin
                                // CRC matched: only NOW do the frame's 101 ORIGINAL words
                                // go into the FDRI burst. ICAP has been paused with CSIB
                                // high while they were loaded and checked.
                                emit_word <= 7'd0;
                                phase     <= P_EMIT;
                            end
                        end
                    end else if (word_valid) begin
                        if (control_bad) begin
                            fault_code <= (pos == 22) ? F_LENGTH : F_CONTROL;
                            phase      <= P_FAULT;
                        end else if (far_bad) begin
                            fault_code <= F_FAR;
                            phase      <= P_FAULT;
                        end else if (in_frame) begin
                            if (crc_ready) begin      // the transfer: word_valid && crc_ready
                                if (phase == P_PASS2) stage[frame_word] <= word_data;
                                pos <= pos + 10'd1;
                                if (frame_word == FRAME_WORDS - 1) awaiting_crc <= 1'b1;
                                else frame_word <= frame_word + 7'd1;
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
                                    phase      <= P_RDBACK;
                                    pos        <= 10'd0;
                                    rb_frame   <= 3'd0;
                                    frame_word <= 7'd0;
                                    watchdog   <= 32'd0;
                                    crc_clear  <= 1'b1;
                                end
                            end else begin
                                pos <= pos + 10'd1;
                            end
                        end
                    end
                end

                // ---- emit: hand one verified frame to the FDRI burst already in
                // progress. RDWRB stays in write throughout and is never toggled while
                // CSIB is low, which would abort the load.
                P_EMIT: begin
                    watchdog <= watchdog + 32'd1;
                    if (watchdog > TIMEOUT) begin
                        fault_code <= F_TIMEOUT;
                        phase      <= P_FAULT;
                    end else begin
                        icap_csib  <= 1'b0;
                        icap_rdwrb <= 1'b0;
                        icap_din   <= stage[emit_word];
                        if (emit_word == FRAME_WORDS - 1) begin
                            emit_word <= 7'd0;
                            phase     <= P_PASS2;
                        end else begin
                            emit_word <= emit_word + 7'd1;
                        end
                    end
                end

                // ---- readback: the envelope's five frames, one at a time
                //
                // The local compare is CRC per frame against the SAME committed CRC pass 1
                // produced, so no copy of the candidate has to be kept. It is a hardware
                // interlock and nothing more: the host reads every frame out of `rb_*` and
                // computes the SHA-256 that actually authorises the payload.
                //
                // NOTE, and the calibration must settle it: the ICAP readback command
                // sequence is modelled abstractly here. The bench's device is a model of
                // the assumption, so simulation cannot establish that a real ICAPE2 will
                // return these words this way.
                P_RDBACK: begin
                    watchdog <= watchdog + 32'd1;
                    if (watchdog > TIMEOUT) begin
                        fault_code <= F_TIMEOUT;
                        phase      <= P_FAULT;
                    end else if (rb_frame_ready) begin
                        if (rb_ack) begin
                            rb_frame_ready <= 1'b0;
                            if (rb_frame == FRAMES_PER_ENV - 1) begin
                                // envelope done. configuration_valid is reachable ONLY
                                // from here, and only with every one of the fifteen frames
                                // verified — the counter, not the envelope index, is what
                                // makes it structurally unreachable early.
                                if (env == ENVELOPES - 1) begin
                                    if (rb_frames_ok == TOTAL_FRAMES[3:0]) begin
                                        configuration_valid <= 1'b1;
                                        recovery_required   <= 1'b0;
                                    end else begin
                                        fault_code <= F_READBACK;
                                        phase      <= P_FAULT;
                                    end
                                end else begin
                                    expect_env <= env + 2'd1;
                                end
                                busy  <= 1'b0;
                                phase <= (phase == P_FAULT) ? P_FAULT : P_IDLE;
                            end else begin
                                rb_frame   <= rb_frame + 3'd1;
                                frame_word <= 7'd0;
                                crc_clear  <= 1'b1;
                            end
                        end
                    end else if (awaiting_crc) begin
                        // CSIB high pauses the readback while the feeder drains the last
                        // word — the same pause the write path uses between frames.
                        icap_csib <= 1'b1;
                        rb_we     <= 1'b0;
                        if (crc_taken) begin
                            awaiting_crc <= 1'b0;
                            if (crc_byte_count != BYTES_PER_FRAME) begin
                                fault_code <= F_BYTECOUNT;
                                phase      <= P_FAULT;
                            end else if (crc_value ==
                                crc_committed[env*FRAMES_PER_ENV + rb_frame]) begin
                                rb_frames_ok   <= rb_frames_ok + 4'd1;
                                rb_frame_ready <= 1'b1;
                            end else begin
                                fault_code <= F_READBACK;
                                phase      <= P_FAULT;
                            end
                        end
                    end else begin
                        // stream one frame back, paced by the SAME advance condition: the
                        // buffer write and the CRC see the identical word, so a readback
                        // word can never reach `rb_*` without having been CRC'd.
                        icap_csib  <= 1'b0;
                        icap_rdwrb <= 1'b1;
                        rb_we      <= crc_ready;
                        rb_waddr   <= frame_word;
                        rb_wdata   <= icap_dout;
                        if (crc_ready) begin
                            if (frame_word == FRAME_WORDS - 1) awaiting_crc <= 1'b1;
                            else frame_word <= frame_word + 7'd1;
                        end
                    end
                end

                P_FAULT: begin
                    awaiting_crc        <= 1'b0;
                    configuration_valid <= 1'b0;
                    pass1_complete      <= 1'b0;
                    env_committed       <= 3'b000;   // scratch and commits both die
                    rb_frames_ok        <= 4'd0;
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
