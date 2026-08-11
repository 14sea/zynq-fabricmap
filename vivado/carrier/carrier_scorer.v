// Claim B round 1 carrier — the scorer, and the interlock that gates it.
//
// It walks the frozen vector order, drives the six evolvable LUTs, compares each output
// against that LUT's frozen target bit, and accumulates a per-LUT match count. Nothing
// here is evolvable: the vectors, the targets and the split are constants from
// `specs/reachability_spec_v1.json` and the production reachability report. The only
// thing evolution changes is the six LUTs' INIT, which lives in the fabric, not here.
//
// THE SPLIT IS A FIREWALL, NOT A RANGE
// ------------------------------------
// Train is `order[0 .. TRAIN_COUNT-1]`; holdout is `order[TRAIN_COUNT .. VECTORS-1]`.
// Holdout mode walks the holdout slice ONLY. A first draft of this module set the limit
// to VECTORS in holdout mode, which scores all 64 — leaking the train vectors into the
// holdout number while still looking like a holdout evaluation. The preregistration's
// firewall is the whole reason the holdout means anything, so the base and the count are
// both derived from the mode rather than only the count.
//
// THE INTERLOCK — two conditions, and the second one is not the host's word
// -------------------------------------------------------------------------
// An evaluation starts only on `configuration_valid && !recovery_required && arm`.
//
// `armed` is a ONE-SHOT: set only by an explicit arm, cleared by reset, and self-clearing
// at `done`. That alone proves "no arm, no score" — but on its own it still leaves the
// promise resting on the host issuing things in the right order.
//
// `configuration_valid` is the other half and it is NOT a software bit. It is driven by
// the board-side guard, which clears it before any FAR/FDRI write begins, holds it clear
// through a failed or timed-out write and through reset, and sets it ONLY after its own
// fixed-range readback compare succeeds. So the state the scorer gates on is
// *readback-confirmed*, observable, and maintained by the thing performing the write.
//
// This is the reason the guard lives in the PL and drives ICAPE2 rather than being PS
// firmware over PCAP: the PL cannot observe PCAP activity, so a PS-side guard could only
// offer a register bit the host sets — which is the assumption being removed. No fictional
// "reconfiguration busy" signal is invented anywhere; the observable fact is the guard's
// own comparison result.
//
// Both conditions fail closed. Reset clears both; an unarmed loop, a lost connection, a
// mismatching readback or a write that never completed all leave the accumulator held.

`default_nettype none

module carrier_scorer #(
    parameter integer LUTS        = 6,
    parameter integer VECTORS     = 64,
    parameter integer TRAIN_COUNT = 40
) (
    input  wire                  clk,
    input  wire                  rst_n,

    input  wire                  configuration_valid, // from the guard's readback compare
    // Design §4 item 6: after a partial write, what was already written is NOT a candidate
    // and MAY NEVER BE SCORED. `configuration_valid` alone does not carry that: a fault
    // followed by a complete, fully verified transaction raises it again, so `arm` was
    // still able to score afterwards. `recovery_required` is the flag that stays raised,
    // and the scorer must be the thing that refuses — a rule enforced only in a host script
    // is a rule the hardware does not have.
    input  wire                  recovery_required,
    input  wire                  arm,           // one-shot: start one evaluation
    input  wire                  mode_holdout,  // latched at arm

    output reg  [5:0]            vector,        // drives the evolvable LUT inputs
    input  wire [LUTS-1:0]       lut_q,         // their outputs, combinational in `vector`

    output reg                   busy,
    output reg                   done,
    output wire                  armed_o,
    output reg  [LUTS*8-1:0]     score_flat     // per-LUT match counts, 8 bits each
);
    localparam integer HOLDOUT_COUNT = VECTORS - TRAIN_COUNT;

    // The 64 six-bit vectors in the frozen order, and the six target truth tables.
    // Loaded from generated hex so the constants have one source: the committed spec and
    // the committed reachability report. Hand-typing 64 + 6 values is exactly the sort of
    // transcription this line refuses everywhere else.
    reg [5:0]  order  [0:VECTORS-1];
    reg [63:0] target [0:LUTS-1];

    initial begin
        $readmemh("carrier_vector_order.hex", order);
        $readmemh("carrier_targets.hex", target);
    end

    reg        armed;
    reg [6:0]  step;    // 0 .. count-1 within the selected slice
    reg [6:0]  base;    // 0 for train, TRAIN_COUNT for holdout
    reg [6:0]  count;   // TRAIN_COUNT or HOLDOUT_COUNT

    assign armed_o = armed;

    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            armed      <= 1'b0;              // fail-closed: every reset lands frozen
            busy       <= 1'b0;
            done       <= 1'b0;
            step       <= 7'd0;
            base       <= 7'd0;
            count      <= TRAIN_COUNT[6:0];
            vector     <= 6'd0;
            score_flat <= {LUTS*8{1'b0}};
        end else if (!configuration_valid || recovery_required) begin
            // Confirmation withdrawn, or recovery became required. Freeze, disarm, and
            // WITHDRAW ANY PREVIOUS RESULT.
            //
            // Clearing `done` unconditionally, not only while busy, is the point: `done` is
            // a level the host reads out of STATUS, so a `done` left standing from the
            // previous candidate reads as a result for the current one — and after a fault
            // the current one may never be scored at all. A stale completion flag beside a
            // stale `score_flat` is exactly the shape of a wrong answer that looks right.
            busy  <= 1'b0;
            armed <= 1'b0;
            done  <= 1'b0;
        end else if (arm && !busy) begin
            armed      <= 1'b1;
            busy       <= 1'b1;
            done       <= 1'b0;
            step       <= 7'd0;
            base       <= mode_holdout ? TRAIN_COUNT[6:0] : 7'd0;
            count      <= mode_holdout ? HOLDOUT_COUNT[6:0] : TRAIN_COUNT[6:0];
            vector     <= order[mode_holdout ? TRAIN_COUNT : 0];
            score_flat <= {LUTS*8{1'b0}};
        end else if (busy && armed) begin
            // At this edge `vector` holds the vector under test and `lut_q` its
            // combinational output, so the comparison is of the pair presented during the
            // cycle just ending.
            for (i = 0; i < LUTS; i = i + 1) begin
                if (lut_q[i] == target[i][vector]) begin
                    score_flat[i*8 +: 8] <= score_flat[i*8 +: 8] + 8'd1;
                end
            end
            if (step == count - 7'd1) begin
                busy   <= 1'b0;
                done   <= 1'b1;
                armed  <= 1'b0;              // ONE-SHOT: back to frozen
            end else begin
                step   <= step + 7'd1;
                vector <= order[base + step + 7'd1];
            end
        end
    end
endmodule

`default_nettype wire
