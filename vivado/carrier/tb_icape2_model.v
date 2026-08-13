// The device model's own bench: a literal known-answer trace, then the seven ways a
// readback can be got wrong.
//
// WHY THIS BENCH EXISTS SEPARATELY FROM THE DUT'S
// ----------------------------------------------
// A model is only an oracle if it can tell right from wrong WITHOUT the DUT in the room.
// So every stimulus here is written out word by word by the bench, and every expected
// answer is either a literal or a value the bench itself put into the model's configuration
// memory. Nothing is read from `carrier_stream`, and `carrier_stream` is not instantiated.
//
// If this bench passes, the following are established about the model:
//   * it syncs ONLY on the ICAPE2 wire order, so a SelectMAP-order stream is dead on arrival;
//   * it answers a register read with the device's own value after the flush, and with idle
//     words before it;
//   * a five-frame FDRI burst commits FOUR frames — the fifth stays in the frame buffer;
//   * its FAR successor reproduces the manifest's non-consecutive flush FAR (A23 -> A80);
//   * a readback returns the frame buffer FIRST and configuration memory afterwards;
//   * and it distinguishes all seven defects in the erratum-004 ruling.
//
// Then, and only then, is it worth pointing at the DUT.

`timescale 1ns/1ps
`default_nettype none

module tb_icape2_model;
    localparam integer FRAME_WORDS = 101;
    localparam integer FLUSH_NOOPS = 32;

    localparam [31:0] DUMMY = 32'hFFFFFFFF, SYNC = 32'hAA995566, NOOP = 32'h20000000;
    localparam [31:0] W_CMD1 = 32'h30008001, W_WCFG = 32'h00000001, W_RCFG = 32'h00000004,
                      W_DESYNC = 32'h0000000D, W_ID1 = 32'h30018001, W_IDCODE = 32'h03722093,
                      W_FAR1 = 32'h30002001, W_FDRI0 = 32'h30004000,
                      W_RD_IDCODE = 32'h28018001, W_FDRO0 = 32'h28006000;

    // the pinned addresses, from scripts/board_carrier_guard.py. They are STIMULUS here,
    // not an oracle: the model is never told that A80 follows A23 — it is asked.
    localparam [31:0] FAR_T0 = 32'h00400A20, FAR_T1 = 32'h00400A21,
                      FAR_T2 = 32'h00400A22, FAR_T3 = 32'h00400A23,
                      FAR_FL = 32'h00400A80,   // the manifest's flush FAR for envelope 0
                      FAR_OTHER = 32'h00400C1A;

    localparam [31:0] IDLE = 32'hFFFFFFFF;
    localparam [31:0] DEV_IDCODE = 32'h13722093;

    reg         clk = 1'b0;
    reg         csib = 1'b1, rdwrb = 1'b1;
    reg  [31:0] iw = 32'd0;
    wire [31:0] ow;
    wire        m_synced, m_wcfg, m_rcfg;
    wire [3:0]  m_err;
    wire [31:0] m_far;
    wire [15:0] m_written, m_read, m_idle, m_committed;
    wire [31:0] m_buf_far;

    integer errors = 0;
    integer k, f;
    reg [31:0] got, want;
    reg [31:0] cap [0:1023];

    always #5 clk = ~clk;

    icape2_model #(.FRAME_WORDS(FRAME_WORDS), .MIN_FLUSH(FLUSH_NOOPS), .READ_LATENCY(0))
      m (.clk(clk), .csib(csib), .rdwrb(rdwrb), .i(iw), .o(ow),
         .synced(m_synced), .err(m_err), .far(m_far), .wcfg(m_wcfg), .rcfg(m_rcfg),
         .n_written(m_written), .n_read(m_read), .n_idle(m_idle),
         .n_frames_committed(m_committed), .buf_far(m_buf_far));

    // The bench's own copy of the wire ordering, written from the specification and not
    // shared with the model — if both were one function, a wrong ordering would cancel out.
    function [31:0] tb_br8(input [31:0] d);
        integer b;
        begin
            for (b = 0; b < 8; b = b + 1) begin
                tb_br8[b]      = d[7  - b];
                tb_br8[8  + b] = d[15 - b];
                tb_br8[16 + b] = d[23 - b];
                tb_br8[24 + b] = d[31 - b];
            end
        end
    endfunction

    // ---- driver. One task, one ICAP clock, so a sequence in this file reads as the
    // sequence on the wire.
    task wr(input [31:0] w);
        begin
            @(negedge clk); csib = 1'b0; rdwrb = 1'b0; iw = tb_br8(w);
            @(posedge clk); #1;
        end
    endtask

    task wr_raw(input [31:0] w);            // no ordering applied: the wrong-order stimulus
        begin
            @(negedge clk); csib = 1'b0; rdwrb = 1'b0; iw = w;
            @(posedge clk); #1;
        end
    endtask

    task noops(input integer n);
        integer j;
        begin
            for (j = 0; j < n; j = j + 1) wr(NOOP);
        end
    endtask

    task turn(input dir);               // CSIB High, change direction, one idle clock
        begin
            @(negedge clk); csib = 1'b1;
            @(posedge clk); #1;
            @(negedge clk); rdwrb = dir;
            @(posedge clk); #1;
        end
    endtask

    task turn_illegal(input dir);       // the same change WITHOUT raising CSIB
        begin
            @(negedge clk); csib = 1'b0; rdwrb = dir;
            @(posedge clk); #1;
        end
    endtask

    task rd(output [31:0] w);
        begin
            @(negedge clk); csib = 1'b0; rdwrb = 1'b1;
            @(posedge clk); #1; w = tb_br8(ow);
        end
    endtask

    task rd_raw(output [31:0] w);      // the pin value, with no un-swap applied
        begin
            @(negedge clk); csib = 1'b0; rdwrb = 1'b1;
            @(posedge clk); #1; w = ow;
        end
    endtask

    task gap_clk;                      // one clock with CSIB High, mid-burst
        begin
            @(negedge clk); csib = 1'b1;
            @(posedge clk); #1;
        end
    endtask

    task idle_clk;
        begin
            @(negedge clk); csib = 1'b1;
            @(posedge clk); #1;
        end
    endtask

    task check_w(input [255:0] what, input [31:0] g, input [31:0] e);
        begin
            if (g !== e) begin
                $display("FAIL %0s: got %08x want %08x", what, g, e);
                errors = errors + 1;
            end
        end
    endtask

    task check_ne(input [255:0] what, input [31:0] g, input [31:0] e);
        begin
            if (g === e) begin
                $display("FAIL %0s: got %08x, which is what it must NOT be", what, g);
                errors = errors + 1;
            end
        end
    endtask

    task check_i(input [255:0] what, input integer g, input integer e);
        begin
            if (g !== e) begin
                $display("FAIL %0s: got %0d want %0d", what, g, e);
                errors = errors + 1;
            end
        end
    endtask

    // ---- the two sequences under test, written once, as the specification writes them
    task seq_sync;
        begin
            wr(DUMMY); wr(SYNC); wr(NOOP); wr(NOOP);
        end
    endtask

    // one envelope's write, exactly as `icap_sequence.build_envelope` emits it
    task seq_write_envelope(input [31:0] far, input [31:0] seed);
        integer j;
        begin
            for (j = 0; j < 8; j = j + 1) wr(DUMMY);
            wr(SYNC); wr(NOOP);
            wr(W_CMD1); wr(32'h00000007);        // RCRC
            wr(NOOP); wr(NOOP);
            wr(W_ID1); wr(W_IDCODE);
            wr(W_CMD1); wr(W_WCFG); wr(NOOP);
            wr(W_FAR1); wr(far);
            wr(W_FDRI0); wr(32'h40000000 | (5*FRAME_WORDS));
            for (j = 0; j < 5*FRAME_WORDS; j = j + 1) wr(seed + j);
            wr(32'h30000001); wr(32'h00000000);  // CRC write, ignored
            wr(W_CMD1); wr(W_DESYNC);
            wr(NOOP); wr(NOOP); wr(NOOP); wr(NOOP);
        end
    endtask

    // the readback transaction, with every step individually defeatable
    task seq_readback(input [31:0] far, input integer nwords,
                      input with_rcfg, input integer flush);
        begin
            // ERRATUM 006: UG470's readback order is RCFG -> NOOP -> FAR -> FDRO. This
            // helper used to emit FAR before RCFG -- the same defect the carrier's RTL had
            // -- and the old model accepted it, so the bench could not have caught it.
            wr(DUMMY); wr(SYNC); wr(NOOP); wr(NOOP);
            if (with_rcfg) begin wr(W_CMD1); wr(W_RCFG); end
            wr(NOOP);
            wr(W_FAR1); wr(far);
            wr(W_FDRO0);
            wr(32'h48000000 | nwords);
            noops(flush);
        end
    endtask

    // The defective order, kept as a fixture so the rule that rejects it stays tested.
    task seq_readback_far_before_rcfg(input [31:0] far, input integer nwords,
                                      input integer flush);
        begin
            wr(DUMMY); wr(SYNC); wr(NOOP); wr(NOOP);
            wr(W_FAR1); wr(far);
            wr(W_CMD1); wr(W_RCFG);
            wr(NOOP);
            wr(W_FDRO0);
            wr(32'h48000000 | nwords);
            noops(flush);
        end
    endtask

    initial begin
        // ============================================================ 1. the wire order
        // A SelectMAP-order stream must be inert. This is the check that would have caught
        // the carrier feeding raw envelope words to ICAPE2.I.
        wr_raw(DUMMY); wr_raw(SYNC); wr_raw(NOOP); wr_raw(NOOP);
        check_i("raw order does not sync", m_synced, 0);
        turn(1'b1);
        rd(got);
        check_w("and a read returns idle", got, IDLE);
        check_i("with the unsynced code", m_err, 7);

        // the same words in the wire order do sync
        turn(1'b0);
        seq_sync();
        check_i("wire order syncs", m_synced, 1);

        // ================================================ 2. a register read, known answer
        wr(W_RD_IDCODE);
        noops(2);                                   // deliberately short of the flush
        turn(1'b1);
        rd(got);
        check_w("too little flush yields idle", got, IDLE);
        turn(1'b0);
        noops(FLUSH_NOOPS);                          // the rest of the pipeline flush
        turn(1'b1);
        rd(got);
        check_w("IDCODE register read", got, DEV_IDCODE);
        rd(got);
        check_w("one asked for, one served", got, IDLE);

        // ======================================= 3. the write pipeline: five in, four land
        m.clear_obs();
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);                    // start from a known desynced state
        m.preload_frame(FAR_T0, 32'h11110000);
        m.preload_frame(FAR_T1, 32'h22220000);
        m.preload_frame(FAR_T2, 32'h33330000);
        m.preload_frame(FAR_T3, 32'h44440000);
        m.preload_frame(FAR_FL, 32'h55550000);
        m.preload_frame(FAR_OTHER, 32'h66660000);

        seq_write_envelope(FAR_T0, 32'hC0DE0000);
        check_i("four of five frames commit", m_committed, 4);
        check_w("frame 0 landed", m.peek_frame_word(FAR_T0, 0), 32'hC0DE0000);
        check_w("frame 3 landed", m.peek_frame_word(FAR_T3, 0),
                32'hC0DE0000 + 3*FRAME_WORDS);
        // The fifth frame is still in the buffer, so the flush FAR keeps what it had. This
        // is exactly why the carrier sources its flush frame from the manifest's pinned
        // content: what is written there is what is already there.
        check_w("the flush frame did NOT land", m.peek_frame_word(FAR_FL, 0), 32'h55550000);
        // ...and the model worked out that address itself, from the address format.
        check_w("the successor of A23 is A80", m_buf_far, FAR_FL);

        // ================================================ 4. readback, literal known answer
        seq_readback(FAR_T0, 6*FRAME_WORDS, 1'b1, FLUSH_NOOPS);
        turn(1'b1);
        for (k = 0; k < 6*FRAME_WORDS; k = k + 1) rd(cap[k]);

        // frame 0 out is the FRAME BUFFER: the envelope's fifth frame, the one that never
        // landed. A consumer that skipped the discard would compare this against frame 0.
        for (k = 0; k < FRAME_WORDS; k = k + 1) begin
            want = 32'hC0DE0000 + 4*FRAME_WORDS + k;
            check_w("pad frame is the frame buffer", cap[k], want);
        end
        // frames 1..4 out are the four that landed, in configuration memory
        for (f = 0; f < 4; f = f + 1)
            for (k = 0; k < FRAME_WORDS; k = k + 1) begin
                want = 32'hC0DE0000 + f*FRAME_WORDS + k;
                check_w("target frame from config mem", cap[(f+1)*FRAME_WORDS + k], want);
            end
        // frame 5 out is the flush FAR — untouched, still the preloaded content
        for (k = 0; k < FRAME_WORDS; k = k + 1) begin
            want = 32'h55550000 + k;
            check_w("flush frame reads as preloaded", cap[5*FRAME_WORDS + k], want);
        end
        check_i("no error on the good path", m_err, 0);

        // ==================================================== 5. NEGATIVE: RCFG missing
        m.clear_obs();
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);
        seq_readback(FAR_T0, 6*FRAME_WORDS, 1'b0, FLUSH_NOOPS);
        turn(1'b1);
        rd(got);
        check_w("no RCFG serves no data", got, IDLE);
        check_i("and is reported", m_err, 2);

        // ==================================================== 6. NEGATIVE: the wrong FAR
        m.clear_obs();
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);
        seq_readback(FAR_OTHER, 6*FRAME_WORDS, 1'b1, FLUSH_NOOPS);
        turn(1'b1);
        for (k = 0; k < 2*FRAME_WORDS; k = k + 1) rd(cap[k]);
        check_w("a wrong FAR serves that FAR", cap[FRAME_WORDS], 32'h66660000);
        check_ne("not the intended frame", cap[FRAME_WORDS], 32'hC0DE0000);

        // ============================================== 7. NEGATIVE: the wrong FDRO length
        m.clear_obs();
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);
        seq_readback(FAR_T0, 3*FRAME_WORDS, 1'b1, FLUSH_NOOPS);
        turn(1'b1);
        for (k = 0; k < 4*FRAME_WORDS; k = k + 1) rd(cap[k]);
        check_w("the last word asked for is data", cap[3*FRAME_WORDS - 1],
                32'hC0DE0000 + 2*FRAME_WORDS - 1);
        check_w("and the next one is not", cap[3*FRAME_WORDS], IDLE);

        // ================================ 8. NEGATIVE: the dummy frame, and an off-by-one
        m.clear_obs();
        // Stated as an assertion about the stream rather than about a consumer: the word at
        // offset 0 and the word at offset FRAME_WORDS are different frames, and a reader
        // that is one frame late runs off the end of what it asked for.
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);
        seq_readback(FAR_T0, 6*FRAME_WORDS, 1'b1, FLUSH_NOOPS);
        turn(1'b1);
        for (k = 0; k < 6*FRAME_WORDS; k = k + 1) rd(cap[k]);
        check_w("offset 0 is the pad", cap[0], 32'hC0DE0000 + 4*FRAME_WORDS);
        check_w("offset 101 is frame 0", cap[FRAME_WORDS], 32'hC0DE0000);
        rd(got);
        check_w("one frame late runs off the end", got, IDLE);

        // ================================== 9. NEGATIVE: direction switched with CSIB Low
        m.clear_obs();
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);
        seq_readback(FAR_T0, 6*FRAME_WORDS, 1'b1, FLUSH_NOOPS);
        turn_illegal(1'b1);                          // no CSIB High between the directions
        rd(got);
        check_w("an abort serves no data", got, IDLE);
        check_i("abort is reported", m_err, 1);
        check_i("and the engine is desynced", m_synced, 0);

        // ============================= 10. NEGATIVE: too few flush clocks before the data
        m.clear_obs();
        // Same transaction, correct in every other respect, turned around early. The words
        // arrive late by exactly the shortfall, so a consumer holding a hardcoded skip is
        // misaligned rather than merely delayed.
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);
        seq_readback(FAR_T0, 6*FRAME_WORDS, 1'b1, 4);   // 4 flush clocks, not 32
        turn(1'b1);
        for (k = 0; k < 8; k = k + 1) rd(cap[k]);
        check_w("early turnaround reads idle", cap[0], IDLE);
        check_w("still idle four words in", cap[3], IDLE);

        // ============ 11. ERRATUM 005: an FDRO read must be absorbed CONTIGUOUSLY
        //
        // The erratum-004 engine pulled CSIB Low one clock per word and High for three
        // while its byte-serial CRC drained. This is the rule that makes that a defect
        // instead of a pause, and the value it produces is the one the board returned.
        m.clear_obs();
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);
        seq_readback(FAR_T0, 6*FRAME_WORDS, 1'b1, FLUSH_NOOPS);
        turn(1'b1);
        for (k = 0; k < 6*FRAME_WORDS; k = k + 1) rd(cap[k]);
        check_i("a contiguous burst does not abort", m_err, 0);
        check_w("and it is real data", cap[FRAME_WORDS], 32'hC0DE0000);

        // the same transaction, with ONE clock of CSIB High after the first word
        m.clear_obs();
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);
        seq_readback(FAR_T0, 6*FRAME_WORDS, 1'b1, FLUSH_NOOPS);
        turn(1'b1);
        rd(got);
        check_w("the first word is still data", got, 32'hC0DE0000 + 4*FRAME_WORDS);
        gap_clk();                                   // <-- the defect, one clock of it
        check_i("one CSIB clock mid-burst aborts", m_err, 8);
        rd_raw(got);
        check_w("and the device drives the abort word", got, 32'hFFFFFF5B);
        rd(got);
        check_w("which un-swaps to what the board stored", got, 32'hFFFFFFDA);
        rd_raw(got);
        check_w("and it keeps driving it", got, 32'hFFFFFF5B);

        // a fresh sync clears it: the engine is not bricked, it is desynced
        turn(1'b0);
        seq_sync();
        check_i("a sync clears the abort", m_synced, 1);

        // ============ 12. ERRATUM 006: a CMD command executes when FAR is LOADED
        //
        // UG470 orders readback RCFG -> NOOP -> FAR -> FDRO, and orders configuration
        // CMD=WCFG -> FAR -> FDRI, because loading FAR is what runs the command CMD holds.
        // The carrier's readback path emitted FAR before RCFG and every bench passed: the
        // model set `rcfg` on the CMD payload, so the ORDER was unobservable. These checks
        // make it observable. Without them the RTL fix has nothing holding it in place.
        //
        // Same words, same count, same flush — only the order differs.
        m.clear_obs();
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);
        seq_readback_far_before_rcfg(FAR_T0, 6*FRAME_WORDS, FLUSH_NOOPS);
        turn(1'b1);
        rd(got);
        check_w("FAR before RCFG serves no data", got, IDLE);
        check_i("and is reported as a missing RCFG", m_err, 2);

        // the documented order, unchanged in every other respect, still works
        m.clear_obs();
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);
        seq_readback(FAR_T0, 6*FRAME_WORDS, 1'b1, FLUSH_NOOPS);
        turn(1'b1);
        // drained in full: leaving a burst active would make the turnaround below an
        // E_FDRO_GAP and the next check would blame the write path for it
        for (k = 0; k < 6*FRAME_WORDS; k = k + 1) rd(cap[k]);
        check_w("RCFG before FAR serves data", cap[0], 32'hC0DE0000 + 4*FRAME_WORDS);
        check_i("with no error", m_err, 0);

        // The write path already used the documented order, and must keep working: this is
        // the check that a FAR-gated command did not break configuration.
        m.clear_obs();
        turn(1'b0);
        wr(W_CMD1); wr(W_DESYNC);
        seq_write_envelope(FAR_T0, 32'hBEEF0000);
        check_i("the write path is undisturbed", m_err, 0);
        check_w("and its first frame still lands",
                m.peek_frame_word(FAR_T0, 0), 32'hBEEF0000);

        if (errors == 0) $display("ICAPE2 MODEL TB: OK");
        else             $display("ICAPE2 MODEL TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule

`default_nettype wire
