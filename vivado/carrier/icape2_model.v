// An ICAPE2 device model that does NOT know what the DUT intends.
//
// WHY THIS FILE EXISTS
// --------------------
// Errata 002, 003 and 004 were one defect wearing three costumes: the bench modelled the
// readback the way the RTL implemented it. `tb_carrier_stream`'s device handed back the
// words the DUT had just staged, indexed by the DUT's own `frame_word` — so it agreed with
// any read protocol at all, including none, and with a consumer that dropped three words
// out of four. Erratum 004 is what that costs when the board finally rules.
//
// So this model is built to a written specification (docs/claimb_icape2_readback_sequence.md)
// and obeys exactly ONE rule above all others:
//
//     it never reads a signal, an array or a parameter belonging to the DUT.
//
// It sees five wires — CLK, CSIB, RDWRB, I, O — and nothing else. Everything it returns is
// computed from words it parsed off those wires and from its own configuration memory. If
// the DUT sends a wrong command, a wrong address or a wrong length, this model does not
// know that it was wrong; it simply behaves as the silicon would, and the DUT's own CRC
// fails. That is what makes it an oracle rather than a mirror.
//
// WHAT IT MODELS, AND WHERE THE AUTHORITY COMES FROM (see the doc for the full derivation)
//   * wire order: ICAPE2's I/O are bit-reversed within each byte relative to SelectMAP
//     order, so a stream carrying a raw 0xAA995566 NEVER syncs here;
//   * pausing with CSIB is legal and lossless; toggling RDWRB while CSIB is Low ABORTS;
//   * a write of N frames leaves the LAST frame in the frame buffer, uncommitted — which is
//     why a bitstream appends a pad frame, and why this carrier's flush frame is the pinned
//     content of the successor FAR;
//   * a readback must be established (sync -> FAR -> RCFG -> FDRO), and the first frame it
//     returns is the frame buffer's content, not the addressed frame;
//   * FAR successors are computed from the address format, never from a table — which is
//     also how the model reproduces the manifest's two non-consecutive flush FARs.
//
// WHAT IT DELIBERATELY DOES NOT MODEL
//   * the configuration CRC register (a CRC write is accepted and ignored). The carrier
//     writes CRC=0 and never enables a CRC check, so modelling it would add a second CRC
//     with no observable consequence;
//   * ECC, per-frame parity, GHIGH/GTS/GRESTORE state, and everything about the running
//     design's flip-flops. A candidate write is a content-bit edit; none of that is reached.
//
// The read pipeline is EXPOSED AS TWO KNOBS, not pinned: `MIN_FLUSH` clocks must pass after
// a read command before any data can flow, and `READ_LATENCY` idle words precede the data
// once it does. A DUT that hardcodes either number is supposed to fail when the bench sweeps
// them. That is the whole point: the number no simulation can establish must not be a number
// the design believes.

`default_nettype none

module icape2_model #(
    parameter integer FRAME_WORDS    = 101,
    parameter integer SLOTS          = 24,     // configuration-memory frames held
    parameter integer MIN_FLUSH      = 32,     // clocks after a read command before data
    parameter integer READ_LATENCY   = 0,      // idle words at the head of a read burst
    parameter integer MINORS_PER_COL = 36,     // 7-series CLB column: 36 frames
    parameter [31:0]  DEVICE_IDCODE  = 32'h13722093,   // the IDCODE *register*
    parameter [31:0]  STREAM_IDCODE  = 32'h03722093,   // what a bitstream WRITES (erratum 003)
    parameter [31:0]  STAT_VALUE     = 32'h46107FFC,   // measured on this silicon
    parameter integer BIT_ORDER      = 1,      // 1 = ICAPE2 wire order (byte-bit-reversed)
    // Does a DESYNC make the frame still sitting in the buffer ineligible to commit?
    // UNPROVEN — see docs/claimb_icape2_readback_sequence.md §9. Default 1 (it does).
    // With 0 the leftover lands when the NEXT envelope pushes a frame, and the bench shows
    // what that costs this envelope shape: nothing, because the only frame that can be left
    // over is the flush frame and its address already holds its content.
    parameter integer DESYNC_FLUSHES_BUFFER = 1,
    parameter [31:0]  IDLE_WORD      = 32'hFFFFFFFF,
    // The ABORT status word the device drives once a configuration has been aborted.
    // MEASURED on board 17A6, 2026-08-13: after the erratum-004 readback faulted, the
    // staging window held 101 identical words and the value on the ICAPE2 O pins was
    // 0xFFFFFF5B. Its shape is UG470's abort status: the upper 24 bits all 1, and in the
    // low byte CFGERR_B=0, DALIGN=1, RIP=0, IN_ABORT_B=1 with the fixed low bits.
    //
    // It is driven RAW. An abort status word is not part of the configuration data stream
    // and is NOT bit-swapped, which is why the engine's unconditional un-swap turned it
    // into 0xFFFFFFDA in the staging window — br8(0x5B) == 0xDA, exactly.
    parameter [31:0]  ABORT_STATUS   = 32'hFFFFFF5B
) (
    input  wire        clk,
    input  wire        csib,
    input  wire        rdwrb,
    input  wire [31:0] i,
    output reg  [31:0] o,

    // ---- observation ports. FOR THE BENCH ONLY; nothing in the DUT may be wired to these.
    output reg         synced,
    output reg  [3:0]  err,          // first error, sticky
    output reg  [31:0] far,
    output reg         wcfg,
    output reg         rcfg,
    output reg  [15:0] n_written,    // words accepted in write mode
    output reg  [15:0] n_read,       // words served in read mode
    output reg  [15:0] n_idle,       // of those, words that were not real data
    output reg  [15:0] n_frames_committed,
    // The address the frame now sitting in the frame buffer was written to. Silicon has no
    // such port; a bench needs it to see the one-frame pipeline and the FAR successor rule
    // as separate facts instead of inferring both from one readback.
    output reg  [31:0] buf_far
);
    // ---- error codes (observation only; the model keeps behaving like silicon)
    localparam [3:0] E_NONE       = 4'd0,
                     E_ABORT      = 4'd1,   // RDWRB toggled while CSIB Low
                     E_NO_RCFG    = 4'd2,   // FDRO read with no RCFG since sync
                     E_IDCODE     = 4'd3,   // IDCODE write disagreed with the device
                     E_NO_WCFG    = 4'd4,   // FDRI data with no WCFG since sync
                     E_UNKNOWN_FAR= 4'd5,   // a read addressed a frame never written
                     E_STRAY_TYPE2= 4'd6,   // a Type-2 packet with no Type-1 to own it
                     E_UNSYNCED   = 4'd7,   // a read command arrived while desynced
                     E_FDRO_GAP   = 4'd8;   // CSIB rose during an ACTIVE FDRO read

    localparam [31:0] SYNC = 32'hAA995566;

    // Widths pinned once. Part-selecting an integer parameter inline is a portability trap
    // that costs an afternoon under a different simulator.
    localparam [6:0]  LAST_W     = FRAME_WORDS - 1;
    localparam [6:0]  LAST_MINOR = MINORS_PER_COL - 1;

    localparam [13:0] REG_CRC = 14'd0, REG_FAR = 14'd1, REG_FDRI = 14'd2, REG_FDRO = 14'd3,
                      REG_CMD = 14'd4, REG_STAT = 14'd7, REG_IDCODE = 14'd12;

    localparam [31:0] CMD_WCFG = 32'h00000001, CMD_RCFG = 32'h00000004,
                      CMD_RCRC = 32'h00000007, CMD_DESYNC = 32'h0000000D;

    // ---------------------------------------------------------------- wire bit ordering
    //
    // Per-byte bit reversal. `br8(br8(x)) == x`, so the same function serves both
    // directions; it is written once and applied at the pins, exactly where the silicon
    // applies it.
    function automatic [31:0] br8(input [31:0] d);
        integer b;
        begin
            for (b = 0; b < 8; b = b + 1) begin
                br8[b]      = d[7  - b];
                br8[8  + b] = d[15 - b];
                br8[16 + b] = d[23 - b];
                br8[24 + b] = d[31 - b];
            end
        end
    endfunction

    // The ordering is held in a register, not read straight from the parameter, so a bench
    // can change it MID-RUN. That is what makes "the second envelope must not inherit the
    // first envelope's measurement" testable: envelope 0 measures a good device, the device
    // then stops speaking the DUT's order, and envelope 1 must report nothing rather than
    // the number that is still sitting in the register.
    reg wire_order;
    initial wire_order = (BIT_ORDER != 0);

    task set_wire_order(input value);
        begin
            wire_order = value;
        end
    endtask

    function automatic [31:0] from_wire(input [31:0] d);
        from_wire = wire_order ? br8(d) : d;
    endfunction

    function automatic [31:0] to_wire(input [31:0] d);
        to_wire = wire_order ? br8(d) : d;
    endfunction

    // ------------------------------------------------------------------- FAR successor
    //
    // Derived from the address format, NOT from the manifest's list: [6:0] minor,
    // [16:7] column, [21:17] row, [22] top/bottom. The successor of the last minor of a
    // column is minor 0 of the next column. Applied to the pinned targets this reproduces
    // all three pinned flush FARs, including the two that are not FAR+1.
    function automatic [31:0] far_succ(input [31:0] a);
        begin
            if (a[6:0] == LAST_MINOR)
                far_succ = {a[31:7] + 25'd1, 7'd0};
            else
                far_succ = {a[31:7], a[6:0] + 7'd1};
        end
    endfunction

    // ------------------------------------------------------------ configuration memory
    reg [31:0] mem      [0:SLOTS*FRAME_WORDS-1];
    reg [31:0] mem_far  [0:SLOTS-1];
    reg        mem_used [0:SLOTS-1];

    integer    s_i, w_i;

    function automatic integer slot_of(input [31:0] a);
        integer k;
        begin
            slot_of = -1;
            for (k = 0; k < SLOTS; k = k + 1)
                if (mem_used[k] && mem_far[k] == a && slot_of < 0) slot_of = k;
        end
    endfunction

    function automatic integer free_slot;
        input dummy;                      // iverilog wants at least one port
        integer k;
        begin
            free_slot = -1;
            for (k = 0; k < SLOTS; k = k + 1)
                if (!mem_used[k] && free_slot < 0) free_slot = k;
        end
    endfunction

    // ---- bench-side setup. The bench owns the fabric's prior contents; the DUT cannot
    // reach any of this.
    task preload_frame(input [31:0] a, input [31:0] seed);
        integer k, sl;
        begin
            sl = slot_of(a);
            if (sl < 0) sl = free_slot(1'b0);
            if (sl < 0) begin
                $display("MODEL: out of configuration-memory slots for FAR %08x", a);
                $finish;
            end
            mem_used[sl] = 1'b1;
            mem_far[sl]  = a;
            for (k = 0; k < FRAME_WORDS; k = k + 1)
                mem[sl*FRAME_WORDS + k] = seed + k[31:0];
        end
    endtask

    // Overwrite one word of the fabric BEHIND the DUT's back. This is how a bench proves
    // the frames the DUT reports came out of configuration memory and not out of its own
    // staging buffer: the staging copy still holds the word that was written, the fabric
    // does not, and only a real read can tell the difference.
    task poke_frame_word(input [31:0] a, input integer widx, input [31:0] value);
        integer sl;
        begin
            sl = slot_of(a);
            if (sl < 0) begin
                $display("MODEL: poke of unknown FAR %08x", a);
                $finish;
            end
            mem[sl*FRAME_WORDS + widx] = value;
        end
    endtask

    // Observation counters and the sticky error belong to the CASE a bench is running, not
    // to the device: silicon has no such registers. A bench clears them between cases so
    // that "sticky" means "sticky within one case" — which is what makes a later case's
    // clean run readable at all.
    task clear_obs;
        begin
            err = E_NONE;
            n_written = 16'd0; n_read = 16'd0; n_idle = 16'd0; n_frames_committed = 16'd0;
        end
    endtask

    function automatic [31:0] peek_frame_word(input [31:0] a, input integer widx);
        integer sl;
        begin
            sl = slot_of(a);
            peek_frame_word = (sl < 0) ? {16'hDEAD, a[15:0]} : mem[sl*FRAME_WORDS + widx];
        end
    endfunction

    // ------------------------------------------------------------------ the frame buffer
    //
    // One frame deep. A burst of N frames commits N-1 of them; the last stays here. This is
    // also what a readback returns as its first (pad) frame.
    reg [31:0] fbuf [0:FRAME_WORDS-1];
    reg        fbuf_valid;
    reg        fbuf_commit_ok;

    reg [31:0] cur  [0:FRAME_WORDS-1];
    reg [31:0] cur_far;
    reg [6:0]  cur_w;

    // ---------------------------------------------------------------------- packet state
    reg [13:0] pay_reg;
    reg [10:0] pay_cnt;
    reg [26:0] fdri_cnt;
    reg        fdri_pending, fdro_pending;
    reg        id_bad;

    // ------------------------------------------------------------------------ read state
    reg        rd_active;
    reg        rd_kind;          // 0 = register, 1 = frame stream
    reg [31:0] rd_val;
    reg [26:0] rd_cnt;
    reg [31:0] rd_far;
    reg [6:0]  rd_word;
    reg [11:0] rd_frame;
    reg [15:0] rd_wait;          // clocks still owed before data may flow
    reg [15:0] rd_lead;          // idle words still owed at the head of the burst

    reg        csib_q, rdwrb_q;

    // ---- ERRATUM 005: an FDRO read must be absorbed CONTIGUOUSLY.
    //
    // The erratum-004 engine pulled CSIB Low for one clock per word and High for three
    // while its byte-serial CRC drained, and this model let it: pausing was modelled as
    // free in both directions, because that is what the WRITE path needs between frames and
    // the read path was never thought about separately. On silicon the read came back as
    // 101 identical abort status words.
    //
    // THIS RULE IS AN ADVERSARIAL CONTRACT, NOT A REPRODUCTION OF SILICON.
    //
    // What is actually supported: UG470 documents non-contiguous configuration as available
    // EITHER by de-asserting CSI_B OR by stopping CCLK — a gap is a documented pause, not a
    // documented break. AMD defines the abort condition as RDWRB changing while CSIB is
    // asserted (PG134, Abort Status Register); nothing says a plain FDRO gap must abort.
    // What IS documented is that AMD's own AXI HWICAP does not stop the ICAP stream when its
    // read FIFO fills, which is why that core can overflow: a reader must be able to absorb
    // the stream.
    //
    // So the model refuses a gap for the same reason it refuses a missing RCFG — because the
    // DESIGN must not depend on a device tolerating one — and not because the device is known
    // to punish it. On the board the erratum-004 engine gapped the read and the staging
    // window came back holding 101 abort status words; that is a correlation this rule makes
    // impossible to ignore, not a causation it establishes.
    // See docs/claimb_erratum_005_correction_2026_08_13.md.
    //
    // Deliberately asymmetric: a gap during an FDRI WRITE is still modelled as a legal
    // pause. That is what the frame-staged write depends on, the ruling scopes this to
    // FDRO, and nothing measured says otherwise about the write path.
    reg        aborted;
    // "Active" starts when the first data word is SERVED, not when the FDRO header is
    // parsed. The turnaround from write to read must raise CSIB — that is the rule two
    // paragraphs up — so a window that opened at the header would make the legal
    // turnaround an abort and the model would refuse every correct sequence.
    reg        fdro_started;
    wire       fdro_streaming = fdro_started && rd_cnt != 27'd0;

    // ERRATUM 006: a command written to CMD does not take effect when it is written. UG470
    // has it execute when FAR is loaded, which is why the documented sequences put the
    // command FIRST and the address SECOND:
    //
    //     write:     CMD=WCFG -> FAR -> FDRI
    //     readback:  CMD=RCFG -> NOOP -> FAR -> FDRO
    //
    // Modelling it as "set on the CMD payload" made the ORDER unobservable: a stream that
    // wrote FAR and only then RCFG established a read anyway, so the model called a
    // sequence legal that UG470 does not describe. That is exactly the shape of defect a
    // model exists to catch, and it did not catch it — every bench passed while the RTL's
    // readback path had FAR before RCFG.
    //
    // CMD holds ONE command, so a second write before the FAR load replaces the first.
    // DESYNC and RCRC stay immediate: DESYNC ends the transaction and no FAR follows it,
    // and RCRC is accepted-but-unmodelled here. Scoping the rule to WCFG/RCFG keeps the
    // change to what the two documented sequences actually pin.
    reg        pend_wcfg;
    reg        pend_rcfg;

    task set_err(input [3:0] code);
        begin
            if (err == E_NONE) err = code;
        end
    endtask

    task abort_config;
        begin
            set_err(E_FDRO_GAP);
            aborted <= 1'b1;
            desync;
        end
    endtask

    task desync;
        begin
            synced <= 1'b0; wcfg <= 1'b0; rcfg <= 1'b0;
            pend_wcfg <= 1'b0; pend_rcfg <= 1'b0;
            pay_cnt <= 11'd0; fdri_cnt <= 27'd0;
            fdri_pending <= 1'b0; fdro_pending <= 1'b0;
            rd_active <= 1'b0; rd_cnt <= 27'd0; fdro_started <= 1'b0;
            cur_w <= 7'd0; id_bad <= 1'b0;
            if (DESYNC_FLUSHES_BUFFER != 0) fbuf_commit_ok <= 1'b0;
        end
    endtask

    task start_read(input reg kind, input [31:0] value, input [26:0] count);
        begin
            rd_active <= 1'b1;
            rd_kind   <= kind;
            rd_val    <= value;
            rd_cnt    <= count;
            rd_word   <= 7'd0;
            rd_frame  <= 12'd0;
            rd_far    <= far;
            rd_wait   <= MIN_FLUSH;
            rd_lead   <= READ_LATENCY;
            fdro_started <= 1'b0;
        end
    endtask

    function automatic [31:0] reg_value(input [13:0] r);
        begin
            case (r)
                REG_IDCODE: reg_value = DEVICE_IDCODE;
                REG_STAT:   reg_value = STAT_VALUE;
                REG_FAR:    reg_value = far;
                default:    reg_value = 32'h00000000;
            endcase
        end
    endfunction

    integer k;

    initial begin
        o = IDLE_WORD; synced = 1'b0; err = E_NONE; far = 32'd0;
        wcfg = 1'b0; rcfg = 1'b0; pend_wcfg = 1'b0; pend_rcfg = 1'b0;
        n_written = 16'd0; n_read = 16'd0; n_idle = 16'd0; n_frames_committed = 16'd0;
        pay_reg = 14'd0; pay_cnt = 11'd0; fdri_cnt = 27'd0;
        fdri_pending = 1'b0; fdro_pending = 1'b0; id_bad = 1'b0;
        rd_active = 1'b0; rd_kind = 1'b0; rd_val = 32'd0; rd_cnt = 27'd0;
        rd_far = 32'd0; rd_word = 7'd0; rd_frame = 12'd0; rd_wait = 16'd0; rd_lead = 16'd0;
        buf_far = 32'd0; fbuf_valid = 1'b0; fbuf_commit_ok = 1'b0;
        cur_far = 32'd0; cur_w = 7'd0;
        csib_q = 1'b1; rdwrb_q = 1'b1; aborted = 1'b0; fdro_started = 1'b0;
        for (s_i = 0; s_i < SLOTS; s_i = s_i + 1) begin
            mem_used[s_i] = 1'b0;
            mem_far[s_i]  = 32'hFFFFFFFF;
        end
        for (w_i = 0; w_i < SLOTS*FRAME_WORDS; w_i = w_i + 1) mem[w_i] = 32'h00000000;
        for (w_i = 0; w_i < FRAME_WORDS; w_i = w_i + 1) begin
            fbuf[w_i] = 32'h00000000;
            cur[w_i]  = 32'h00000000;
        end
    end

    reg [31:0] word;
    reg [2:0]  htype;
    reg [1:0]  op;
    reg [13:0] rg;
    reg [10:0] cnt1;
    reg [26:0] cnt2;
    integer    sl;

    always @(posedge clk) begin
        csib_q  <= csib;
        rdwrb_q <= rdwrb;

        // A gap in an active FDRO read. Checked BEFORE the `!csib` body, because the whole
        // point is what happens on the clocks where CSIB is High.
        if (csib && fdro_streaming && !aborted) abort_config;

        if (!csib) begin
            // A direction change is only legal with CSIB High. Doing it here aborts the
            // configuration — UG470 — and that is a hard stop, not a warning.
            if (!csib_q && (rdwrb != rdwrb_q)) begin
                set_err(E_ABORT);
                desync;
            end else begin
                // The read pipeline drains on every clock the interface takes, whichever
                // direction it is pointing: this is what the flush NOOPs are for.
                if (rd_active && rd_wait != 16'd0) rd_wait <= rd_wait - 16'd1;

                if (!rdwrb) begin
                    // ------------------------------------------------------------ WRITE
                    word      = from_wire(i);
                    n_written <= n_written + 16'd1;

                    if (!synced) begin
                        if (word == SYNC) begin
                            synced  <= 1'b1;
                            wcfg    <= 1'b0;
                            rcfg    <= 1'b0;
                            pend_wcfg <= 1'b0;
                            pend_rcfg <= 1'b0;
                            id_bad  <= 1'b0;
                            aborted <= 1'b0;   // a fresh sync clears an abort
                        end
                    end else if (pay_cnt != 11'd0) begin
                        case (pay_reg)
                            // ERRATUM 006: loading FAR is what executes the command that
                            // CMD is holding. A FAR load with nothing pending is legal and
                            // simply establishes no transaction — which is precisely the
                            // case the old model could not tell apart from a good one.
                            REG_FAR: begin
                                far <= word;
                                if (pend_wcfg) wcfg <= 1'b1;
                                if (pend_rcfg) rcfg <= 1'b1;
                                pend_wcfg <= 1'b0;
                                pend_rcfg <= 1'b0;
                            end
                            REG_CMD: begin
                                case (word)
                                    // CMD holds one command until a FAR load executes it
                                    CMD_WCFG:   begin pend_wcfg <= 1'b1;
                                                      pend_rcfg <= 1'b0; end
                                    CMD_RCFG:   begin pend_rcfg <= 1'b1;
                                                      pend_wcfg <= 1'b0; end
                                    CMD_RCRC:   ;                 // accepted, not modelled
                                    CMD_DESYNC: desync;
                                    default:    ;
                                endcase
                            end
                            REG_IDCODE: begin
                                if (word != STREAM_IDCODE) begin
                                    set_err(E_IDCODE);
                                    id_bad <= 1'b1;
                                end
                            end
                            default: ;                            // CRC and friends
                        endcase
                        pay_cnt <= pay_cnt - 11'd1;
                    end else if (fdri_cnt != 27'd0) begin
                        // ---- frame data
                        if (!wcfg || id_bad) begin
                            set_err(E_NO_WCFG);                   // silently discarded
                        end else begin
                            cur[cur_w] <= word;
                            if (cur_w == 7'd0) cur_far <= far;
                            if (cur_w == LAST_W) begin
                                // the buffer holds the PREVIOUS frame; it lands now
                                if (fbuf_valid && fbuf_commit_ok) begin
                                    sl = slot_of(buf_far);
                                    if (sl < 0) sl = free_slot(1'b0);
                                    if (sl >= 0) begin
                                        mem_used[sl] = 1'b1;
                                        mem_far[sl]  = buf_far;
                                        for (k = 0; k < FRAME_WORDS; k = k + 1)
                                            mem[sl*FRAME_WORDS + k] = fbuf[k];
                                        n_frames_committed <= n_frames_committed + 16'd1;
                                    end
                                end
                                for (k = 0; k < FRAME_WORDS - 1; k = k + 1) fbuf[k] = cur[k];
                                fbuf[FRAME_WORDS-1] = word;
                                buf_far        <= (cur_w == 7'd0) ? far : cur_far;
                                fbuf_valid     <= 1'b1;
                                fbuf_commit_ok <= 1'b1;
                                far        <= far_succ(far);
                                cur_w      <= 7'd0;
                            end else begin
                                cur_w <= cur_w + 7'd1;
                            end
                        end
                        fdri_cnt <= fdri_cnt - 27'd1;
                    end else begin
                        // ---- a packet header
                        htype = word[31:29];
                        if (htype == 3'b001) begin
                            op   = word[28:27];
                            rg   = word[26:13];
                            cnt1 = word[10:0];
                            if (op == 2'd2) begin                 // write
                                if (rg == REG_FDRI) begin
                                    if (cnt1 == 11'd0) fdri_pending <= 1'b1;
                                    else               fdri_cnt <= {16'd0, cnt1};
                                end else begin
                                    pay_reg <= rg;
                                    pay_cnt <= cnt1;
                                end
                            end else if (op == 2'd1) begin        // read
                                if (rg == REG_FDRO) begin
                                    if (cnt1 == 11'd0) fdro_pending <= 1'b1;
                                    else if (!rcfg)    set_err(E_NO_RCFG);
                                    else               start_read(1'b1, 32'd0, {16'd0, cnt1});
                                end else begin
                                    start_read(1'b0, reg_value(rg), {16'd0, cnt1});
                                end
                            end
                            // op == 0 is a NOP
                        end else if (htype == 3'b010) begin
                            cnt2 = word[26:0];
                            if (fdri_pending) begin
                                fdri_cnt     <= cnt2;
                                fdri_pending <= 1'b0;
                            end else if (fdro_pending) begin
                                fdro_pending <= 1'b0;
                                if (!rcfg) set_err(E_NO_RCFG);
                                else       start_read(1'b1, 32'd0, cnt2);
                            end else begin
                                set_err(E_STRAY_TYPE2);
                            end
                        end
                    end
                end else begin
                    // ------------------------------------------------------------- READ
                    n_read <= n_read + 16'd1;
                    // Reading with nothing established and no sync ever seen is the
                    // signature of a stream in the wrong word order: it is worth its own
                    // code, because on the board it is the difference between "the read
                    // path never came up" and "it came up and disagreed".
                    if (!synced && !rd_active) set_err(E_UNSYNCED);
                    if (aborted) begin
                        // RAW: an abort status word is not configuration data and is not
                        // bit-swapped. This is the value the board actually returned.
                        o      <= ABORT_STATUS;
                        n_idle <= n_idle + 16'd1;
                    end else if (!rd_active || rd_wait != 16'd0 || rd_lead != 16'd0 ||
                        rd_cnt == 27'd0) begin
                        o      <= to_wire(IDLE_WORD);
                        n_idle <= n_idle + 16'd1;
                        if (rd_active && rd_wait == 16'd0 && rd_lead != 16'd0)
                            rd_lead <= rd_lead - 16'd1;
                    end else if (!rd_kind) begin
                        o      <= to_wire(rd_val);
                        rd_cnt <= rd_cnt - 27'd1;
                    end else begin
                        // frame 0 of a readback is the FRAME BUFFER, not the addressed
                        // frame. Frames 1..n come out of configuration memory.
                        if (rd_frame == 12'd0) begin
                            o <= to_wire(fbuf_valid ? fbuf[rd_word] : IDLE_WORD);
                        end else begin
                            sl = slot_of(rd_far);
                            if (sl < 0) begin
                                set_err(E_UNKNOWN_FAR);
                                o <= to_wire({16'hDEAD, rd_far[15:0]});
                            end else begin
                                o <= to_wire(mem[sl*FRAME_WORDS + rd_word]);
                            end
                        end
                        if (rd_word == LAST_W) begin
                            rd_word  <= 7'd0;
                            rd_frame <= rd_frame + 12'd1;
                            if (rd_frame != 12'd0) rd_far <= far_succ(rd_far);
                        end else begin
                            rd_word <= rd_word + 7'd1;
                        end
                        rd_cnt       <= rd_cnt - 27'd1;
                        fdro_started <= 1'b1;
                    end
                end
            end
        end
    end
endmodule

`default_nettype wire
