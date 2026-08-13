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
    // The CONFIGURATION-STREAM IDCODE, which is NOT the PSS/JTAG identity. UG470 makes
    // IDCODE[31:28] a revision field, so a bitstream's IDCODE register write carries the
    // revision masked off: this device streams 0x03722093 while its JTAG identity reads
    // 0x13722093. The two were confused here, and the engine rejected every real envelope at
    // word 15 with F_CONTROL -- which on the board became SLVERR, a data abort and a reboot.
    // Renamed so the two identities cannot be mistaken for each other again. It is compared
    // EXACTLY: no masking, and the JTAG value is not also accepted.
    parameter [31:0]  CONFIG_IDCODE = 32'h03722093,
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
    // One cycle per stream write that arrived with no pass open. `carrier_axil` completes
    // those on the bus with OKAY so the host can drain a `cp.l`; the refusal is reported
    // here instead, because an AXI error response reboots this board's U-Boot.
    input  wire        protocol_fault,
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

    // ---- TELEMETRY, and nothing but telemetry.
    //
    // The read pipeline's depth, measured against a known answer at the start of every
    // envelope's readback, and a validity bit that says whether this envelope measured it.
    // The board has never been able to report HOW FAR the pipeline is, which is why erratum
    // 004's failure was mute; these two say it out loud.
    //
    // They are a SEPARATE latch from `rb_lat`, which is what the sequencer actually skips
    // on. Sharing one register would put a reporting field inside a control path, and the
    // ruling is explicit: telemetry takes no part in acceptance, in a fault, or in
    // `configuration_valid`. Grep for `rb_latency` — it appears in this file only where it
    // is assigned, and in the register file where it is read.
    output reg  [7:0]  rb_latency,       // words of latency the probe measured
    output reg         rb_latency_valid, // ...and whether THIS envelope measured it

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
                     F_BYTECOUNT = 4'd10,
                     F_PROTOCOL  = 4'd11,   // a stream write with no pass open
                     // The readback's sync probe never got the device to name itself. This
                     // is deliberately NOT F_READBACK: "the read path never came up" and
                     // "it came up and the content disagreed" are different findings, and
                     // erratum 004 cost a board round precisely because one code covered
                     // both. Word ordering, a lost sync and a dead ICAP land here.
                     F_RBSYNC    = 4'd12;

    localparam [31:0] W_DUMMY  = 32'hFFFFFFFF, W_SYNC  = 32'hAA995566,
                      W_NOOP   = 32'h20000000, W_CMD1  = 32'h30008001,
                      W_RCRC   = 32'h00000007, W_WCFG  = 32'h00000001,
                      W_DESYNC = 32'h0000000D, W_ID1   = 32'h30018001,
                      W_FAR1   = 32'h30002001, W_FDRI0 = 32'h30004000,
                      W_TYPE2  = 32'h40000000 | (FRAMES_PER_ENV * FRAME_WORDS),
                      W_CRC1   = 32'h30000001, W_ZERO  = 32'h00000000;

    // ---- the READ side of the configuration protocol (erratum 004).
    // `W_RDID`  Type-1 read of IDCODE (reg 12), 1 word — the known answer the probe hunts.
    // `W_RCFG`  CMD = RCFG, which is what establishes a read transaction at all.
    // `W_FDRO0` Type-1 read of FDRO (reg 3), 0 words, followed by the Type-2 that carries
    //           the real length: one dummy frame plus this envelope's five.
    localparam [31:0] W_RDID   = 32'h28018001, W_RCFG  = 32'h00000004,
                      W_FDRO0  = 32'h28006000;
    // ERRATUM 005: one FDRO transaction PER FRAME, so the burst is a dummy frame plus one
    // real frame. The whole burst is absorbed contiguously into the staging RAM at one word
    // per clock and the CRC runs afterwards, out of the RAM — see the P_RDBACK comment.
    localparam integer RB_WORDS = 2 * FRAME_WORDS;                      // 202
    localparam [31:0] W_RDLEN  = 32'h48000000 | RB_WORDS;

    // The device IDCODE with the revision nibble masked off. UG470 makes IDCODE[31:28] a
    // revision field: this die answers a register read with 0x13722093 while a bitstream
    // WRITES 0x03722093 (erratum 003, and CONFIG_IDCODE above). Matching on [27:0] accepts
    // either and keeps the two identities from being confused for a second time.
    localparam [27:0] DEVICE_ID_LOW = 28'h3722093;

    // 32 NOOPs of pipeline flush after a read command — UG470's figure — and a probe that
    // gives up after 64 words. 32 clocks is 0.64 us of a 20.97 ms watchdog phase.
    localparam integer FLUSH_NOOPS = 32;
    // widths pinned once; part-selecting an integer parameter inline is a portability trap
    localparam [8:0]  SKIP_FRAME   = FRAME_WORDS;
    localparam [5:0]  FLUSH_LAST   = FLUSH_NOOPS - 1;
    localparam [7:0]  PROBE_LAST   = 8'd63;

    // ---- ICAPE2 WIRE ORDER (erratum 004 §2).
    //
    // ICAPE2's I/O bus is bit-reversed within each byte relative to SelectMAP order — the
    // order every bitstream, this repo's manifest, the committed CRCs and the host's
    // SHA-256 are all written in. The carrier used to hand `word_data` straight to `I`, so
    // the sync word arrived as 0xAA995566 where the primitive wanted 0x5599AA66 and the
    // configuration engine never synced at all. The swap is a permutation of 32 wires: it
    // costs no logic, and it belongs HERE, at the pins, so that everything above it keeps
    // speaking SelectMAP order.
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
            5'd15:                  expected_at_idx = {1'b1, CONFIG_IDCODE};
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

    // Every frame's own address. A per-frame FDRO addresses the frame it is reading, so the
    // three envelope heads are no longer enough. Same order as
    // scripts/board_carrier_guard.py's PERMITTED_TARGET_FARS + PERMITTED_FLUSH_FARS, and
    // tests/test_config_idcode_agreement.py compares the two rather than trusting either.
    function automatic [31:0] frame_far(input [1:0] e, input [2:0] f);
        case ({e, f})
            5'b00_000: frame_far = 32'h00400A20;
            5'b00_001: frame_far = 32'h00400A21;
            5'b00_010: frame_far = 32'h00400A22;
            5'b00_011: frame_far = 32'h00400A23;
            5'b00_100: frame_far = 32'h00400A80;   // envelope 0's flush FAR
            5'b01_000: frame_far = 32'h00400C1A;
            5'b01_001: frame_far = 32'h00400C1B;
            5'b01_010: frame_far = 32'h00400C1C;
            5'b01_011: frame_far = 32'h00400C1D;
            5'b01_100: frame_far = 32'h00400C1E;
            5'b10_000: frame_far = 32'h00400C20;
            5'b10_001: frame_far = 32'h00400C21;
            5'b10_010: frame_far = 32'h00400C22;
            5'b10_011: frame_far = 32'h00400C23;
            5'b10_100: frame_far = 32'h00400C80;
            default:   frame_far = 32'hFFFFFFFF;
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

    // ---- the readback sequencer's own states. `phase` keeps its encoding: the host and
    // the transport decode STATUS, not this, and P_RDBACK is still one phase to them.
    localparam [3:0] RB_PCMD   = 4'd0,   // dummy, sync, NOOPs, Type-1 read IDCODE
                     RB_PFLUSH = 4'd1,   // 32 NOOPs of pipeline flush
                     RB_TRN    = 4'd2,   // CSIB High, then RDWRB moves — never the reverse
                     RB_PROBE  = 4'd3,   // read until the device names itself: the latency
                     RB_SETUP  = 4'd4,   // FAR, RCFG, FDRO, Type-2 length
                     RB_SFLUSH = 4'd5,   // 32 NOOPs again
                     RB_SKIP   = 4'd6,   // the measured latency, then the dummy FRAME
                     RB_DATA   = 4'd7,   // the five frames
                     RB_DESYNC = 4'd8,   // leave the engine desynced before the next frame
                     RB_CRC    = 4'd9,   // CRC the staged frame OUT OF THE RAM, ICAP idle
                     RB_WAIT   = 4'd10,  // the host has the frame; wait for its ack
                     RB_FIN    = 4'd11;

    reg [3:0]  phase;
    reg [3:0]  rb_st;
    reg [3:0]  rb_next;      // where RB_TRN returns to
    reg        rb_dir;       // the direction RB_TRN is turning towards
    reg [5:0]  rb_k;         // position within a command sequence / the flush count
    reg [7:0]  rb_lat;       // MEASURED: idle words before the device answered
    reg [7:0]  rb_lat_cnt;
    reg [8:0]  rb_skip;      // words still to discard: the latency, then a whole frame
    reg        icap_rd_valid;
    reg [2:0]  rb_frame;
    reg [6:0]  emit_word;
    reg [1:0]  env;
    reg [9:0]  pos;
    reg [2:0]  frame_idx;
    reg [6:0]  frame_word;
    reg        awaiting_crc;   // last word of a frame accepted; feeder still draining

    // STICKY TO RESET. Design §4 item 6: after a partial write the only permitted next
    // actions are restoring the pinned base or reloading the whole carrier — so a later
    // candidate, however complete, must NOT be able to clear `recovery_required`. The RTL
    // used to clear it on any fully verified transaction, which is the opposite rule, and
    // the bench pinned that as correct.
    //
    // The reason is erratum 001. The carrier's own static routing now lives inside the
    // frames a candidate rewrites, so a partial write may have damaged the very logic that
    // would go on to report "the next write verified". A machine cannot certify its own
    // repair. `begin_txn` deliberately does not clear this: a host-issued pulse must not be
    // able to launder a fault. Only a reset — which on this board means the carrier was
    // reloaded — clears it.
    reg        fault_since_reset;
    reg [TIMEOUT_BITS-1:0] watchdog;
    wire       expired = watchdog[TIMEOUT_BITS-1];

    // staging: ONE frame-sized memory, used by pass 2 for the candidate frame and by the
    // readback for the words the device returns. They are never live at the same time —
    // readback begins only after the whole envelope has been written, so no emit follows it
    // within an envelope — and sharing removes a second 101-word array (88 LUTs of SLICEM
    // in a floorplan of about 1,600). It also makes an assurance structural rather than
    // incidental: the words the host reads back ARE the words the CRC saw, because they are
    // the same array written by the same transfer.
    //
    // DISTRIBUTED RAM, written from its OWN purely synchronous block. Left inside the
    // asynchronous-reset FSM it inferred 3,232 flip-flops AND a 101-entry 32-bit read
    // multiplexer for the emit path — 4,272 FDRE and 2,415 LUTs against the ~1,600 LUTs the
    // whole pblock has, so the placer refused before it started. It
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

    // The device speaks in ICAPE2 wire order; everything above this line speaks SelectMAP
    // order. One unswap, at the pin, for the CRC, the staging RAM and the host alike.
    wire [31:0] icap_word = br8(icap_dout);

    // In pass 1/2 the CRC covers the words the HOST sent; during readback it covers the
    // words the DEVICE returned, and comparing the second against the first is the local
    // interlock. One engine, two sources, selected by phase.
    //
    // ERRATUM 005: in readback the source is the STAGING RAM, not the ICAP pins. The
    // byte-serial CRC takes one word every four cycles and an FDRO burst delivers one per
    // clock, so a CRC fed from the pins can only keep up by pausing the interface — which
    // is what aborted the configuration on silicon. The burst is absorbed first; the CRC
    // runs afterwards, out of the RAM, with the ICAP idle.
    wire [31:0] crc_source = (phase == P_RDBACK) ? stage_rdata : word_data;

    // ONE feeder for all three phases; only the source changes. Three phases keeping
    // three sets of counters against one byte stream is exactly how the readback CRC came
    // out as though almost nothing had been consumed.
    //
    // The readback term is `icap_rd_valid`, not "the phase is open": a read word EXISTS for
    // exactly one cycle, in the cycle after CSIB was Low. The old term fed the CRC whenever
    // the phase was running, which against a real device would have CRC'd whatever `O`
    // happened to be holding — invisible against a bench that re-presented the same word
    // until the DUT moved on.
    wire crc_feed = !awaiting_crc &&
                    (((phase == P_PASS1 || phase == P_PASS2) && word_valid && in_frame)
                     || (phase == P_RDBACK && rb_st == RB_CRC));

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
    // one write port, two sources, mutually exclusive by phase. The readback write takes a
    // word EVERY CLOCK of the burst: a distributed-RAM write port keeps up with ICAP, which
    // is the whole reason the burst can be contiguous.
    wire        stage_rb_we = (phase == P_RDBACK) && (rb_st == RB_DATA) && icap_rd_valid
                              && !expired;
    wire        stage_any_we = stage_we || stage_rb_we;
    wire [31:0] stage_wdata  = stage_rb_we ? icap_word : word_data;

    // ---- ERRATUM 005: the read is CONTIGUOUS. There is no per-word request any more.
    //
    // `icap_rd_valid` is the cycle in which a word the device served is present on `O`:
    // CSIB was Low the cycle before, in read mode. During a burst CSIB is Low on every
    // clock, so this is high on every clock of it.
    //
    // What was here before was a one-word-in-flight handshake that pulled CSIB Low for one
    // clock and High for three while the byte-serial CRC drained. UG470's way to run the
    // interface non-contiguously is to stop CCLK, not to toggle CSIB; on silicon those gaps
    // aborted the configuration and the device returned 101 abort status words. The
    // consumer is now the staging RAM, which never needs a gap.
    wire rb_reading = (rb_st == RB_PROBE) || (rb_st == RB_SKIP) || (rb_st == RB_DATA);
    always @(posedge clk) if (stage_any_we) stage[frame_word] <= stage_wdata;

    // one read port: the emit path while a frame is being handed to ICAP, the host at any
    // other time. The host reads only between `rb_frame_ready` and its ack, so they never
    // want the array in the same cycle.
    // one read port, three readers, none of them live at the same time: the emit path while
    // a verified frame is handed to ICAP, the CRC while it re-checks a frame the burst has
    // already finished delivering, and the host between `rb_frame_ready` and its ack.
    wire [6:0]  stage_raddr = (phase == P_EMIT)                        ? emit_word :
                              (phase == P_RDBACK && rb_st == RB_CRC)   ? frame_word :
                                                                         host_raddr;
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
            awaiting_crc <= 1'b0; fault_since_reset <= 1'b0;
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
            rb_st <= RB_PCMD; rb_next <= RB_PCMD; rb_dir <= 1'b0; rb_k <= 6'd0;
            rb_lat <= 8'd0; rb_lat_cnt <= 8'd0; rb_skip <= 9'd0;
            rb_latency <= 8'd0; rb_latency_valid <= 1'b0;
            icap_rd_valid <= 1'b0;
            icap_csib <= 1'b1; icap_rdwrb <= 1'b0; icap_din <= 32'd0;
        end else begin
            crc_clear <= 1'b0;
            cc_we     <= 1'b0;
            icap_csib <= 1'b1;              // paused unless a word is being handed over
            // A word the device served is present for exactly ONE cycle: the one after
            // CSIB was Low in read mode. Everything on the read path is paced by this.
            icap_rd_valid <= !icap_csib && icap_rdwrb;

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
                                icap_din   <= br8(word_data);
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
                                    rb_st      <= RB_PCMD;
                                    rb_k       <= 6'd0;
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
                        icap_din   <= br8(stage_rdata);
                        if (emit_word == FRAME_WORDS - 1) begin
                            emit_word <= 7'd0;
                            phase     <= P_PASS2;
                        end else begin
                            emit_word <= emit_word + 7'd1;
                        end
                    end
                end

                // ---- readback: FIVE independent, CONTIGUOUS FDRO transactions
                //
                // ERRATUM 005. The erratum-004 engine read one envelope in a single
                // 606-word FDRO burst and paced it by pulling CSIB Low for one clock per
                // word and High for three while the byte-serial CRC drained. On silicon
                // that aborted the configuration: the staging window came back holding 101
                // identical words, `0xFFFFFFDA`, which is `br8` of `0xFFFFFF5B` — an abort
                // status word, driven raw because an abort status is not configuration data
                // and is not bit-swapped. UG470 runs the interface non-contiguously by
                // stopping CCLK, not by toggling CSIB, and AMD's own AXI HWICAP does not
                // stop the ICAP stream when its read FIFO fills, which is exactly why that
                // core can overflow.
                //
                // So each frame is now its own sync..DESYNC transaction reading a dummy
                // frame plus itself, 202 words, with CSIB Low and RDWRB High on every clock
                // of the burst. The words go into the staging RAM at one word per clock —
                // a RAM write port keeps up with ICAP where a byte-serial CRC cannot — and
                // the CRC runs afterwards, out of that RAM, with the ICAP idle and
                // desynced. Nothing back-pressures the configuration engine.
                //
                // One FAR set per sync..DESYNC is also the shape this project already knows
                // is safe: `scripts/icap_sequence.py` records that several FAR sets inside
                // ONE envelope mis-commit the buffered frame and corrupt the array.
                //
                // The pipeline latency is measured per frame, immediately before the burst
                // that uses it, by a Type-1 IDCODE read that is itself absorbed
                // contiguously. That does not remove the assumption that a register read's
                // latency equals an FDRO read's — it makes the measurement as close to its
                // use as it can be, and the erratum-004 measurement of 1 word is void
                // because it was taken through a gapped read.
                P_RDBACK: begin
                    if (!expired) watchdog <= watchdog + 1'b1;
                    if (expired) begin
                        fault_code <= F_TIMEOUT;
                        phase      <= P_FAULT;
                    end else begin
                        case (rb_st)
                            // ---- sync, then ask the device to name itself
                            RB_PCMD: begin
                                if (rb_k == 6'd0) rb_latency_valid <= 1'b0;
                                icap_csib  <= 1'b0;
                                icap_rdwrb <= 1'b0;
                                case (rb_k)
                                    6'd0:    icap_din <= br8(W_DUMMY);
                                    6'd1:    icap_din <= br8(W_SYNC);
                                    6'd4:    icap_din <= br8(W_RDID);
                                    default: icap_din <= br8(W_NOOP);
                                endcase
                                if (rb_k == 6'd4) begin
                                    rb_k  <= 6'd0;
                                    rb_st <= RB_PFLUSH;
                                end else rb_k <= rb_k + 6'd1;
                            end

                            RB_PFLUSH: begin
                                icap_csib  <= 1'b0;
                                icap_rdwrb <= 1'b0;
                                icap_din   <= br8(W_NOOP);
                                if (rb_k == FLUSH_LAST) begin
                                    rb_k    <= 6'd0;
                                    rb_dir  <= 1'b1;
                                    rb_next <= RB_PROBE;
                                    rb_st   <= RB_TRN;
                                end else rb_k <= rb_k + 6'd1;
                            end

                            // ---- THE turnaround, and the only place RDWRB ever moves:
                            // CSIB High first, and the direction changes while it is High.
                            // Moving RDWRB with CSIB Low aborts the configuration (UG470).
                            RB_TRN: begin
                                icap_csib <= 1'b1;
                                if (rb_k == 6'd1) begin
                                    icap_rdwrb <= rb_dir;
                                    rb_k       <= 6'd0;
                                    rb_lat_cnt <= 8'd0;
                                    rb_st      <= rb_next;
                                end else rb_k <= rb_k + 6'd1;
                            end

                            // ---- read CONTIGUOUSLY until the known answer arrives. The
                            // count is in clocks of an uninterrupted read, which is the
                            // only kind the FDRO burst will perform.
                            RB_PROBE: begin
                                icap_csib <= 1'b0;
                                if (icap_rd_valid) begin
                                    if (icap_word[27:0] == DEVICE_ID_LOW) begin
                                        rb_lat           <= rb_lat_cnt;
                                        rb_latency       <= rb_lat_cnt;
                                        rb_latency_valid <= 1'b1;
                                        rb_k    <= 6'd0;
                                        rb_dir  <= 1'b0;
                                        rb_next <= RB_SETUP;
                                        rb_st   <= RB_TRN;
                                    end else if (rb_lat_cnt == PROBE_LAST) begin
                                        rb_latency_valid <= 1'b0;
                                        fault_code <= F_RBSYNC;
                                        phase      <= P_FAULT;
                                    end else begin
                                        rb_lat_cnt <= rb_lat_cnt + 8'd1;
                                    end
                                end
                            end

                            // ---- RCFG, NOOP, FAR, FDRO for THIS FRAME. `frame_far`
                            // addresses the frame being read, not the envelope's head: one
                            // FAR set, one frame, one transaction.
                            //
                            // ERRATUM 006: the command comes FIRST and the address SECOND.
                            // UG470 executes the command CMD is holding at the moment FAR
                            // is loaded, so the previous order — FAR, then RCFG — loaded
                            // the address with no read established and left RCFG holding a
                            // command that nothing ever ran. Same seven words, same length,
                            // only the order differs. The 2026-08-13 board dump is what
                            // sent us looking: the staging window held a bit-exact 101-word
                            // slice of the device stream from 0x00400A81/0x00400A82 — the
                            // address FAR had auto-incremented to after pass 2 — and not
                            // the requested 0x00400A20. See
                            // evidence/calibration_noop_2026_08_13_erratum005/reading.md.
                            RB_SETUP: begin
                                icap_csib  <= 1'b0;
                                icap_rdwrb <= 1'b0;
                                case (rb_k)
                                    6'd0:    icap_din <= br8(W_CMD1);
                                    6'd1:    icap_din <= br8(W_RCFG);
                                    6'd2:    icap_din <= br8(W_NOOP);
                                    6'd3:    icap_din <= br8(W_FAR1);
                                    6'd4:    icap_din <= br8(frame_far(env, rb_frame));
                                    6'd5:    icap_din <= br8(W_FDRO0);
                                    6'd6:    icap_din <= br8(W_RDLEN);
                                    default: icap_din <= br8(W_NOOP);
                                endcase
                                if (rb_k == 6'd6) begin
                                    rb_k  <= 6'd0;
                                    rb_st <= RB_SFLUSH;
                                end else rb_k <= rb_k + 6'd1;
                            end

                            RB_SFLUSH: begin
                                icap_csib  <= 1'b0;
                                icap_rdwrb <= 1'b0;
                                icap_din   <= br8(W_NOOP);
                                if (rb_k == FLUSH_LAST) begin
                                    rb_k    <= 6'd0;
                                    rb_dir  <= 1'b1;
                                    rb_next <= RB_SKIP;
                                    rb_skip <= {1'b0, rb_lat} + SKIP_FRAME;
                                    rb_st   <= RB_TRN;
                                end else rb_k <= rb_k + 6'd1;
                            end

                            // ---- the measured latency, then ONE WHOLE DUMMY FRAME, without
                            // a gap. From here to the last word of RB_DATA the interface is
                            // never paused.
                            RB_SKIP: begin
                                icap_csib <= 1'b0;
                                if (icap_rd_valid) begin
                                    if (rb_skip == 9'd1) begin
                                        frame_word <= 7'd0;
                                        rb_st      <= RB_DATA;
                                    end else rb_skip <= rb_skip - 9'd1;
                                end
                            end

                            // ---- the frame, one word per clock, straight into the RAM
                            RB_DATA: begin
                                icap_csib <= 1'b0;
                                if (icap_rd_valid) begin
                                    if (frame_word == FRAME_WORDS - 1) begin
                                        rb_k    <= 6'd0;
                                        rb_dir  <= 1'b0;
                                        rb_next <= RB_DESYNC;
                                        rb_st   <= RB_TRN;
                                    end else frame_word <= frame_word + 7'd1;
                                end
                            end

                            // ---- put the engine down before the CRC runs, so nothing is
                            // in flight while the ICAP is left alone.
                            RB_DESYNC: begin
                                icap_csib  <= 1'b0;
                                icap_rdwrb <= 1'b0;
                                case (rb_k)
                                    6'd0:    icap_din <= br8(W_CMD1);
                                    6'd1:    icap_din <= br8(W_DESYNC);
                                    default: icap_din <= br8(W_NOOP);
                                endcase
                                if (rb_k == 6'd5) begin
                                    rb_k       <= 6'd0;
                                    frame_word <= 7'd0;
                                    crc_clear  <= 1'b1;
                                    rb_st      <= RB_CRC;
                                end else rb_k <= rb_k + 6'd1;
                            end

                            // ---- the local interlock: CRC the frame out of the RAM and
                            // compare it against the SAME committed CRC pass 1 produced.
                            // ICAP is idle and desynced throughout, so taking four cycles
                            // per word costs nothing but time.
                            RB_CRC: begin
                                if (awaiting_crc) begin
                                    if (crc_taken) begin
                                        awaiting_crc <= 1'b0;
                                        if (crc_byte_count != BYTES_PER_FRAME) begin
                                            fault_code <= F_BYTECOUNT;
                                            phase      <= P_FAULT;
                                        end else if (crc_value == cc_rdata) begin
                                            rb_frames_ok   <= rb_frames_ok + 4'd1;
                                            rb_frame_ready <= 1'b1;
                                            rb_st          <= RB_WAIT;
                                        end else begin
                                            fault_code <= F_READBACK;
                                            phase      <= P_FAULT;
                                        end
                                    end
                                end else if (crc_ready) begin
                                    if (frame_word == FRAME_WORDS - 1) awaiting_crc <= 1'b1;
                                    else frame_word <= frame_word + 7'd1;
                                end
                            end

                            // ---- the host takes the frame out of the same RAM
                            RB_WAIT: begin
                                if (rb_ack) begin
                                    rb_frame_ready <= 1'b0;
                                    rb_k           <= 6'd0;
                                    if (rb_frame == FRAMES_PER_ENV - 1) begin
                                        rb_st <= RB_FIN;
                                    end else begin
                                        rb_frame <= rb_frame + 3'd1;
                                        rb_st    <= RB_PCMD;
                                    end
                                end
                            end

                            // ---- envelope done. configuration_valid is reachable ONLY from
                            // here, and only with every one of the fifteen frames verified —
                            // the counter, not the envelope index, is what makes it
                            // structurally unreachable early.
                            RB_FIN: begin
                                busy  <= 1'b0;
                                rb_st <= RB_PCMD;
                                if (env == ENVELOPES - 1 &&
                                    rb_frames_ok != TOTAL_FRAMES[3:0]) begin
                                    fault_code <= F_READBACK;
                                    phase      <= P_FAULT;
                                end else begin
                                    if (env == ENVELOPES - 1) begin
                                        configuration_valid <= 1'b1;
                                        if (!fault_since_reset) recovery_required <= 1'b0;
                                    end else begin
                                        expect_env <= env + 2'd1;
                                    end
                                    phase <= P_IDLE;
                                end
                            end

                            default: begin
                                fault_code <= F_PHASE;
                                phase      <= P_FAULT;
                            end
                        endcase
                    end
                end

                P_FAULT: begin
                    // `rb_latency` and `rb_latency_valid` are deliberately NOT cleared here:
                    // after F_READBACK the measurement is the most useful thing the engine
                    // has to say. F_RBSYNC clears the validity at its own site instead.
                    awaiting_crc        <= 1'b0;
                    fault_since_reset   <= 1'b1;   // sticky: only a reset clears it
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

            // A refused stream write, reported rather than answered with a bus error.
            //
            // Placed after the phase machine so it cannot be lost to a same-cycle
            // assignment, and guarded by `!fault` so the FIRST fault always survives: when
            // word 15 has already raised F_CONTROL, the rest of the host's `cp.l` drains
            // through here and must not rewrite that verdict.
            if (protocol_fault && !fault) begin
                fault_code <= F_PROTOCOL;
                phase      <= P_FAULT;
            end
        end
    end
endmodule

`default_nettype wire
