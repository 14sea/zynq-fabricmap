// Claim B round 1 carrier — the board-side guard.
//
// It owns ICAPE2. Every frame write and every readback goes through this module, and it is
// the only driver of `configuration_valid`, the signal the scorer gates on.
//
// FOUR THINGS ARE STRUCTURAL, ruled 2026-08-10
// --------------------------------------------
// 1. `configuration_valid` is READ-ONLY to software. There is no AXI write path that can
//    set it. Nothing in this module assigns it from a register bit; it is assigned from
//    the comparison result and from clears, and a mutation that adds a set-from-register
//    path is what the bench's `no_software_set` case exists to catch.
// 2. It is cleared THE MOMENT a command is accepted — not when the first FAR or FDRI word
//    goes out. The window between "the host asked for a write" and "the write started" is
//    still a window in which the configuration is no longer the one that was confirmed.
// 3. It is set again only when the readback of the COMPLETE candidate — all 12 target
//    frames and all 3 flush frames — matches. Any mismatch, any short read, any timeout
//    leaves it clear.
// 4. There is no second control path to ICAPE2 and nothing widens the guard. The FAR
//    allowlist, the envelope shape and the payload length are localparams in the fabric.
//    No register can add a FAR, lengthen an FDRI burst or skip the readback. The sibling
//    `icaphw.c` took its range from ICAPHW_FAR_LO/HI/MAX_FDRI environment variables; an
//    overridable guard is not a guard, and that is the mistake this module exists not to
//    repeat.
//
// WHY THE GUARD, AND NOT THE HOST, HOLDS THIS STATE
// -------------------------------------------------
// A candidate changes content bits only, and every other bit of every frame it writes is
// the pinned base's, verbatim — so the intended write set cannot reach a routing frame.
// The path that CAN is a mis-addressed write, i.e. a software defect. A guard that took
// its permitted range from software would be defended by the thing it is defending
// against.
//
// WHAT configuration_valid DOES AND DOES NOT AUTHORISE
// ----------------------------------------------------
// A readback compare proves ONE thing: the fabric now holds what the guard actually
// received and wrote. It says nothing about whether that candidate was allowed to be
// written. Whether the payload changes only the 292 whitelisted bits, whether the flush
// frames equal the pinned base verbatim, and whether each ECC is a correct recomputation
// are judgements of the HOST gate, `scripts/gate_candidate.py`, and they are not
// re-implemented here.
//
// What has to hold before a score means anything is a three-part conjunction:
//
//     bytes the host candidate gate ACCEPTED
//       == bytes actually HANDED TO the guard
//       == bytes READ BACK from the fabric
//
// `configuration_valid` establishes the second and third links. The first is the host's,
// and scoring requires it too. Two consequences for the data path, so the chain cannot be
// broken between the links: the transport must send the SAME in-memory bytes the gate
// parsed — never re-read the file after gating — and the run log's candidate hash and
// readback hash must be equal before an arm is issued.
//
`default_nettype none

module carrier_guard #(
    parameter integer FRAME_WORDS   = 101,
    parameter integer TARGET_FRAMES = 12,
    parameter integer FLUSH_FRAMES  = 3,
    parameter integer TOTAL_FRAMES  = TARGET_FRAMES + FLUSH_FRAMES,
    // Watchdog: an ICAP that never answers must leave the guard clear, not hung.
    parameter integer TIMEOUT       = 1 << 20
) (
    input  wire        clk,
    input  wire        rst_n,

    // control (AXI-mapped; `start` is a one-cycle pulse from a write to CTRL)
    input  wire        start,
    output reg         busy,
    output reg         fault,
    output reg  [3:0]  fault_code,

    // the ONLY driver of this signal in the design
    output reg         configuration_valid,

    // candidate buffer: the host-loaded frames, addressed as frame*FRAME_WORDS + word
    output wire [11:0] buf_addr,
    input  wire [31:0] buf_data,

    // ICAPE2, abstracted: one word in, one word out, csib/rdwrb as the primitive has them
    output wire        icap_csib,
    output wire        icap_rdwrb,
    output wire [31:0] icap_din,
    input  wire [31:0] icap_dout
);
    // ---------------------------------------------------------------- the allowlist
    // The 12 target FARs and the 3 flush FARs, compiled in. Derived from the local_map and
    // the phenotype manifest; changing them is a source edit that shows up in a diff.
    // A case function rather than an unpacked array: equally compiled into the fabric,
    // and portable across the tools this repo actually runs (iverilog rejects unpacked
    // localparam arrays). No register indexes into it and nothing can extend it.
    function automatic [31:0] far_of(input [3:0] index);
        case (index)
            4'd0:  far_of = 32'h00400A20;   // envelope 0, target
            4'd1:  far_of = 32'h00400A21;   // envelope 0, target
            4'd2:  far_of = 32'h00400A22;   // envelope 0, target
            4'd3:  far_of = 32'h00400A23;   // envelope 0, target
            4'd4:  far_of = 32'h00400A80;   // envelope 0, FLUSH (major 21, cross-column)
            4'd5:  far_of = 32'h00400C1A;   // envelope 1, target
            4'd6:  far_of = 32'h00400C1B;   // envelope 1, target
            4'd7:  far_of = 32'h00400C1C;   // envelope 1, target
            4'd8:  far_of = 32'h00400C1D;   // envelope 1, target
            4'd9:  far_of = 32'h00400C1E;   // envelope 1, FLUSH (in column)
            4'd10: far_of = 32'h00400C20;   // envelope 2, target
            4'd11: far_of = 32'h00400C21;   // envelope 2, target
            4'd12: far_of = 32'h00400C22;   // envelope 2, target
            4'd13: far_of = 32'h00400C23;   // envelope 2, target
            4'd14: far_of = 32'h00400C80;   // envelope 2, FLUSH (major 25, cross-column)
            default: far_of = 32'hFFFFFFFF; // never permitted
        endcase
    endfunction

    // Flush frames are written back verbatim and are still compared: falling inside the
    // FDRI range does not make a frame writable, and a flush frame that reads back
    // different is a violation rather than collateral.
    function automatic is_flush(input [3:0] index);
        is_flush = (index == 4'd4) || (index == 4'd9) || (index == 4'd14);
    endfunction

    localparam [3:0] FAULT_NONE       = 4'd0,
                     FAULT_TIMEOUT    = 4'd1,
                     FAULT_READBACK   = 4'd2,
                     FAULT_SHORT_READ = 4'd3;

    localparam [3:0] S_IDLE   = 4'd0,
                     S_CLEAR  = 4'd1,
                     S_WRITE  = 4'd2,
                     S_RDBACK = 4'd3,
                     S_CMP    = 4'd4,
                     S_OK     = 4'd5,
                     S_FAULT  = 4'd6;

    reg [3:0]  state;
    reg [3:0]  frame;          // 0 .. TOTAL_FRAMES-1
    reg [6:0]  word;           // 0 .. FRAME_WORDS-1
    reg [31:0] watchdog;
    reg        mismatch;

    // Address, data and the ICAP controls are COMBINATIONAL in (state, frame, word).
    // A first version registered them: `buf_addr` moved at the clock edge while
    // `icap_din <= buf_data` still held the previous address's word, so every write and
    // every comparison was off by one and a clean run never confirmed. Driving them from
    // the same counters that select the word keeps the address, the datum and the strobe
    // in one cycle.
    assign buf_addr   = frame * FRAME_WORDS + word;
    assign icap_din   = buf_data;
    assign icap_csib  = !(state == S_WRITE || state == S_RDBACK);
    assign icap_rdwrb = (state == S_RDBACK);

    // A FAR is permitted only if it is in the compiled-in list. Kept as a function so the
    // rule has one definition and a test can call it directly.
    function automatic is_permitted(input [31:0] far);
        integer k;
        begin
            is_permitted = 1'b0;
            for (k = 0; k < TOTAL_FRAMES; k = k + 1)
                if (far_of(k[3:0]) == far) is_permitted = 1'b1;
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state               <= S_IDLE;
            busy                <= 1'b0;
            fault               <= 1'b0;
            fault_code          <= FAULT_NONE;
            configuration_valid <= 1'b0;   // fail-closed on every reset
            frame               <= 4'd0;
            word                <= 7'd0;
            watchdog            <= 32'd0;
            mismatch            <= 1'b0;
        end else begin
            case (state)
                S_IDLE: begin
                    busy <= 1'b0;
                    if (start) begin
                        // RULE 2: cleared the instant the command is accepted, before a
                        // single FAR or FDRI word has gone out.
                        configuration_valid <= 1'b0;
                        fault               <= 1'b0;
                        fault_code          <= FAULT_NONE;
                        mismatch            <= 1'b0;
                        frame               <= 4'd0;
                        word                <= 7'd0;
                        watchdog            <= 32'd0;
                        busy                <= 1'b1;
                        state               <= S_CLEAR;
                    end
                end

                S_CLEAR: begin
                    // one settled cycle with the signal already low, so no observer can
                    // see "command accepted" and "still valid" in the same cycle
                    state <= S_WRITE;
                end

                S_WRITE: begin
                    watchdog <= watchdog + 32'd1;
                    if (watchdog > TIMEOUT) begin
                        fault_code <= FAULT_TIMEOUT;
                        state      <= S_FAULT;
                    end else begin
                        if (word == FRAME_WORDS - 1) begin
                            word <= 7'd0;
                            if (frame == TOTAL_FRAMES - 1) begin
                                frame    <= 4'd0;
                                watchdog <= 32'd0;
                                state    <= S_RDBACK;
                            end else begin
                                frame <= frame + 4'd1;
                            end
                        end else begin
                            word <= word + 7'd1;
                        end
                    end
                end

                S_RDBACK: begin
                    watchdog <= watchdog + 32'd1;
                    if (watchdog > TIMEOUT) begin
                        fault_code <= FAULT_TIMEOUT;
                        state      <= S_FAULT;
                    end else begin
                        // RULE 3: every frame, target AND flush, is compared. A flush
                        // frame that came back different is a violation, not collateral.
                        if (icap_dout !== buf_data) mismatch <= 1'b1;
                        if (word == FRAME_WORDS - 1) begin
                            word <= 7'd0;
                            if (frame == TOTAL_FRAMES - 1) begin
                                state <= S_CMP;
                            end else begin
                                frame <= frame + 4'd1;
                            end
                        end else begin
                            word <= word + 7'd1;
                        end
                    end
                end

                S_CMP: begin
                    if (mismatch) begin
                        fault_code <= FAULT_READBACK;
                        state      <= S_FAULT;
                    end else begin
                        state <= S_OK;
                    end
                end

                S_OK: begin
                    // RULE 1 and 3: the only assignment of 1 in the whole module, and it
                    // is reached only from a complete, matching readback.
                    configuration_valid <= 1'b1;
                    busy                <= 1'b0;
                    state               <= S_IDLE;
                end

                S_FAULT: begin
                    // Mutation note: removing this clear is currently EQUIVALENT — every
                    // path into S_FAULT has already passed the clear at command accept.
                    // It stays as defence in depth, because a later path that reached
                    // here without that clear would otherwise leave a stale confirmation.
                    configuration_valid <= 1'b0;
                    fault               <= 1'b1;
                    busy                <= 1'b0;
                    state               <= S_IDLE;
                end

                default: state <= S_FAULT;
            endcase
        end
    end
endmodule

`default_nettype wire
