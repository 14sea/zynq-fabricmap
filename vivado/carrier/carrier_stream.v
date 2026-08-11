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
    // The watchdog's TOP BIT is the expiry, so there is no comparator: `watchdog > TIMEOUT`
    // on a 32-bit counter cost ~40 LUTs of the 800 the whole design may use.
    parameter integer TIMEOUT_BITS  = 21
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

    // the staging memory, read by the host over AXI between frames
    input  wire [6:0]  host_raddr,
    output wire [31:0] host_rdata,
    output reg         rb_frame_ready,   // a whole frame is in the staging memory
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
    // The control-word expectations, as a 31-entry ROM indexed by a 5-bit position, NOT as
    // a priority chain of 10-bit comparisons: as a chain each of the 33 output bits was a
    // function of the whole position and the block cost roughly 165 LUTs.
    //
    //   index 0..22  -> envelope positions 0..22   (the preamble)
    //   index 23..30 -> envelope positions 528..535 (the trailer)
    //
    // Position 20 is the FAR and carries NO control expectation — it is checked against
    // `permitted_far(env)` instead — so its entry has the valid bit clear.
    function automatic [32:0] expected_at_idx(input [4:0] k);
        case (k)
            5'd0, 5'd1, 5'd2, 5'd3,
            5'd4, 5'd5, 5'd6, 5'd7: expected_at_idx = {1'b1, W_DUMMY};
            5'd8:                   expected_at_idx = {1'b1, W_SYNC};
            5'd9:                   expected_at_idx = {1'b1, W_NOOP};
            5'd10:                  expected_at_idx = {1'b1, W_CMD1};
            5'd11:                  expected_at_idx = {1'b1, W_RCRC};
            5'd12, 5'd13:           expected_at_idx = {1'b1, W_NOOP};
            5'd14:                  expected_at_idx = {1'b1, W_ID1};
            5'd15:                  expected_at_idx = {1'b1, IDCODE};
            5'd16:                  expected_at_idx = {1'b1, W_CMD1};
            5'd17:                  expected_at_idx = {1'b1, W_WCFG};
            5'd18:                  expected_at_idx = {1'b1, W_NOOP};
            5'd19:                  expected_at_idx = {1'b1, W_FAR1};
            5'd21:                  expected_at_idx = {1'b1, W_FDRI0};
            5'd22:                  expected_at_idx = {1'b1, W_TYPE2};
            5'd23:                  expected_at_idx = {1'b1, W_CRC1};
            5'd24:                  expected_at_idx = {1'b1, W_ZERO};
            5'd25:                  expected_at_idx = {1'b1, W_CMD1};
            5'd26:                  expected_at_idx = {1'b1, W_DESYNC};
            5'd27, 5'd28, 5'd29,
            5'd30:                  expected_at_idx = {1'b1, W_NOOP};
            default:                expected_at_idx = {1'b0, 32'd0};   // incl. 20, the FAR
        endcase
    endfunction

    function automatic [31:0] permitted_far(input [1:0] e);
        case (e)
            2'd0:    permitted_far = 32'h00400A20;
            2'd1:    permitted_far = 32'h00400C1A;
            2'd2:    permitted_far = 32'h00400C20;
            default: permitted_far = 32'hFFFFFFFF;
        endcase
    endfunction

    localparam [3:0] P_IDLE = 4'd0, P_PASS1 = 4'd1, P_PASS2 = 4'd2, P_RDBACK = 4'd3,
                     P_FAULT = 4'd4, P_EMIT = 4'd5, P_COMMIT = 4'd6;

    localparam integer TOTAL_FRAMES = ENVELOPES * FRAMES_PER_ENV;   // 15

    reg [3:0]  phase;
    reg [2:0]  rb_frame;
    reg [6:0]  emit_word;
    reg [1:0]  env;
    reg [9:0]  pos;
    reg [2:0]  frame_idx;
    reg [6:0]  frame_word;
    reg        awaiting_crc;   // last word of a frame accepted; feeder still draining
    reg [TIMEOUT_BITS-1:0] watchdog;
    wire       expired = watchdog[TIMEOUT_BITS-1];

    // staging: ONE frame-sized memory, used by pass 2 for the candidate frame and by the
    // readback for the words the device returns. They are never live at the same time —
    // readback begins only after the whole envelope has been written, so no emit follows it
    // within an envelope — and sharing removes a second 101-word array (88 LUTs of SLICEM
    // in a region with 800 LUTs total). It also makes an assurance structural rather than
    // incidental: the words the host reads back ARE the words the CRC saw, because they are
    // the same array written by the same transfer.
    //
    // DISTRIBUTED RAM, written from its OWN purely synchronous block. Left inside the
    // asynchronous-reset FSM it inferred 3,232 flip-flops AND a 101-entry 32-bit read
    // multiplexer for the emit path — 4,272 FDRE and 2,415 LUTs against the 1,600 and 800
    // the left-of-flush region actually has, so the placer refused before it started. It
    // is the same trap the candidate buffer fell into: an array written inside an
    // asynchronous-reset process is not inferrable as RAM at all, and the `ram_style`
    // attribute is then ignored rather than disobeyed.
    (* ram_style = "distributed" *) reg [31:0] stage [0:FRAME_WORDS-1];

    reg [31:0] crc_scratch [0:FRAMES_PER_ENV-1];

    // The fifteen committed CRCs are a DISTRIBUTED RAM with ONE write port, and the commit
    // is sequenced over five cycles in P_COMMIT. As fifteen registers copied in a single
    // step they cost ~900 LUTs — each of the fifteen needed a 5:1 mux of the scratch set,
    // and the two read sites (the pass-2 compare and the readback compare) each built a
    // 15:1 mux of their own. That is more than the entire left-of-flush region has.
    //
    // Atomicity is NOT weakened by sequencing: `env_committed[env]` is what every use of
    // the set is gated on, and it is set only after all five writes have happened. A
    // half-written RAM with the bit clear is not weaker authority, it is none.
    (* ram_style = "distributed" *) reg [31:0] crc_committed [0:ENVELOPES*FRAMES_PER_ENV-1];
    reg  [3:0]  cc_waddr;
    reg  [31:0] cc_wdata;
    reg         cc_we;
    reg  [2:0]  commit_i;
    always @(posedge clk) if (cc_we) crc_committed[cc_waddr] <= cc_wdata;

    // ONE read port: the two compare sites are in different phases and never overlap.
    wire [3:0]  cc_raddr = (phase == P_RDBACK)
                           ? (env*FRAMES_PER_ENV + rb_frame)
                           : (env*FRAMES_PER_ENV + frame_idx);
    wire [31:0] cc_rdata = crc_committed[cc_raddr];

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

    // The staging write is exactly the pass-2 transfer, spelled out here because the RAM
    // must not share the FSM's reset.
    wire stage_we = (phase == P_PASS2) && !awaiting_crc && word_valid && in_frame
                    && !control_bad && !far_bad && crc_ready && !expired;
    // one write port, two sources, mutually exclusive by phase
    wire        stage_rb_we = (phase == P_RDBACK) && !rb_frame_ready && !awaiting_crc
                              && crc_ready && !expired;
    wire        stage_any_we = stage_we || stage_rb_we;
    wire [31:0] stage_wdata  = stage_rb_we ? icap_dout : word_data;
    always @(posedge clk) if (stage_any_we) stage[frame_word] <= stage_wdata;

    // one read port: the emit path while a frame is being handed to ICAP, the host at any
    // other time. The host reads only between `rb_frame_ready` and its ack, so they never
    // want the array in the same cycle.
    wire [6:0]  stage_raddr = (phase == P_EMIT) ? emit_word : host_raddr;
    wire [31:0] stage_rdata = stage[stage_raddr];
    assign      host_rdata  = stage_rdata;

    wire        pos_is_ctrl = (pos < PREAMBLE) || (pos >= ENV_WORDS - 8);
    wire [4:0]  ctrl_idx    = (pos < PREAMBLE) ? pos[4:0] : (5'd23 + pos[2:0]);
    wire [32:0] want        = pos_is_ctrl ? expected_at_idx(ctrl_idx) : {1'b0, 32'd0};
    wire        control_bad = want[32] && (word_data != want[31:0]);
    wire        far_bad     = (pos == FAR_POS) && (word_data != permitted_far(env));


    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase <= P_IDLE; busy <= 1'b0; fault <= 1'b0; fault_code <= F_NONE;
            awaiting_crc <= 1'b0;
            cc_we <= 1'b0; cc_waddr <= 4'd0; cc_wdata <= 32'd0; commit_i <= 3'd0;
            expect_env <= 2'd0; pass1_complete <= 1'b0;
            configuration_valid <= 1'b0;
            recovery_required <= 1'b1;      // fail-closed: a reset proves nothing
            env_committed <= 3'b000;
            env <= 2'd0; pos <= 10'd0; frame_idx <= 3'd0; frame_word <= 7'd0;
            watchdog <= {TIMEOUT_BITS{1'b0}};
            crc_clear <= 1'b0;
            rb_frame_ready <= 1'b0; rb_frames_ok <= 4'd0;
            rb_frame <= 3'd0;
            icap_csib <= 1'b1; icap_rdwrb <= 1'b0; icap_din <= 32'd0;
        end else begin
            crc_clear <= 1'b0;
            cc_we     <= 1'b0;
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
                            watchdog   <= {TIMEOUT_BITS{1'b0}};
                            crc_clear  <= 1'b1;
                            busy       <= 1'b1;
                            phase      <= start_pass1 ? P_PASS1 : P_PASS2;
                        end
                    end
                end

                P_PASS1, P_PASS2: begin
                    if (!expired) watchdog <= watchdog + 1'b1;
                    if (expired) begin
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
                            end else if (crc_value != cc_rdata) begin
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
                                    // ONE commit, at the end of a wholly good envelope,
                                    // sequenced through the RAM's single write port.
                                    commit_i <= 3'd0;
                                    phase    <= P_COMMIT;
                                end else begin
                                    phase      <= P_RDBACK;
                                    pos        <= 10'd0;
                                    rb_frame   <= 3'd0;
                                    frame_word <= 7'd0;
                                    watchdog   <= {TIMEOUT_BITS{1'b0}};
                                    crc_clear  <= 1'b1;
                                end
                            end else begin
                                pos <= pos + 10'd1;
                            end
                        end
                    end
                end

                // ---- commit: copy the envelope's five scratch CRCs into the committed
                // set, one per cycle, and only then raise the authority bit.
                P_COMMIT: begin
                    if (!expired) watchdog <= watchdog + 1'b1;
                    if (expired) begin
                        fault_code <= F_TIMEOUT;
                        phase      <= P_FAULT;
                    end else begin
                        cc_we    <= 1'b1;
                        cc_waddr <= env*FRAMES_PER_ENV + commit_i;
                        cc_wdata <= crc_scratch[commit_i];
                        if (commit_i == FRAMES_PER_ENV - 1) begin
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
                            commit_i <= commit_i + 3'd1;
                        end
                    end
                end

                // ---- emit: hand one verified frame to the FDRI burst already in
                // progress. RDWRB stays in write throughout and is never toggled while
                // CSIB is low, which would abort the load.
                P_EMIT: begin
                    if (!expired) watchdog <= watchdog + 1'b1;
                    if (expired) begin
                        fault_code <= F_TIMEOUT;
                        phase      <= P_FAULT;
                    end else begin
                        icap_csib  <= 1'b0;
                        icap_rdwrb <= 1'b0;
                        icap_din   <= stage_rdata;
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
                    if (!expired) watchdog <= watchdog + 1'b1;
                    if (expired) begin
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
                        if (crc_taken) begin
                            awaiting_crc <= 1'b0;
                            if (crc_byte_count != BYTES_PER_FRAME) begin
                                fault_code <= F_BYTECOUNT;
                                phase      <= P_FAULT;
                            end else if (crc_value == cc_rdata) begin
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
