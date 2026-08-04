// Probe family for the `clb_ff_config` LATCH question. NOT a certification specimen.
//
// `docs/ff_preregistration_plan.md` §5 risk 3: the LATCH pair is the one place the
// 176-key plan is not known to be safe. `LDCE` is a different primitive from the plan's
// baseline `FDRE` and does not have `CE`/`R` in the same shape, so the pair was expected
// to move more of the slice-wide control set than the single `LATCH` bit. Those extra
// movers would be `db_attributed` AND claimed by this class AND outside the pair's one
// preregistered scope — false positives under the fixed 1.4 rule, with FP=0 required.
//
// The author ruled: keep LATCH, do not guess a wider scope, try a CONTROL-MATCHED
// baseline first, and report every remaining same-class mover with its direction.
//
// MODES 0-3 are the single-FF sketch that answered the question in principle:
//
//   0  fdce      FDCE, asynchronous clear          <- reset kind matched
//   1  ldce      LDCE, the latch under test
//   2  fdre      FDRE, the plan's default baseline B (synchronous reset)
//   3  fdce_inv  FDCE with the clock inverted      <- reset kind AND clock polarity
//
// MODES 4-7 are the FORMAL topology, because a one-FF result does not transfer. The
// certification specimen instantiates every storage element of the slice, so that every
// per-FF bit exists and a control-set change is shared by all of them:
//
//   4  full_base   8 storage, FDCE with the clock inverted
//   5  full_latch  8 storage, LDCE
//   6  main_base   4 storage, FDCE with the clock inverted
//   7  main_latch  4 storage, LDCE
//
// The 4-element pair exists because UG474 says the "5FF" storage elements are
// unavailable while the slice is in latch mode. Whether Vivado agrees is measured, not
// assumed: MODE 5 is built and its failure, if it fails, is itself the answer.
//
// Every mode drives the same ports through the same anchors, so the IO ring and the
// clock tree cannot themselves be what moved.
`timescale 1ns / 1ps

// ANCHOR=1 adds fixed consumers of every input port and of the buffered clock in
// another tile, plus a clocked keeper in the SAME CLB COLUMN as the site under test.
// Both exist for reasons measured in the lutram round (`docs/lutram_anchored.md`):
// without the port consumers, different modes trim different IBUFs and the IO ring
// changes; without the column keeper, a mode whose target does not clock anything
// leaves that column's clock branch disabled and HCLK bits move. Neither tile is in the
// freeze, so both would land in `ownership_unknown` — FP under 1.4.
module specimen_ff_probe #(
    parameter MODE   = 0,
    parameter ANCHOR = 1
) (
    input  wire [5:0] i,
    input  wire       clk,
    input  wire       ce,
    input  wire       rst,
    output wire       o,
    output wire       q,
    output wire       anchor_o,
    output wire       anchor_o2
);
    wire clk_g;
    wire lo;
    wire q_int;

    BUFG bufg_inst (.I(clk), .O(clk_g));

    assign q = q_int;

    generate
        if (ANCHOR) begin : g_anchor
            wire w1, w2;
            (* DONT_TOUCH = "TRUE" *)
            LUT6 #(.INIT(64'h6996966996696996)) anchor_lut1 (
                .I0(i[0]), .I1(i[1]), .I2(i[2]), .I3(i[3]), .I4(i[4]), .I5(i[5]), .O(w1)
            );
            (* DONT_TOUCH = "TRUE" *)
            LUT6 #(.INIT(64'h6996966996696996)) anchor_lut2 (
                .I0(ce), .I1(rst), .I2(w1), .I3(w1), .I4(w1), .I5(w1), .O(w2)
            );
            (* DONT_TOUCH = "TRUE" *)
            FDRE #(.INIT(1'b0)) anchor_ff (
                .C(clk_g), .CE(1'b1), .R(1'b0), .D(w2), .Q(anchor_o)
            );
            // Column keeper: same CLB column as the site under test, so that column's
            // clock branch is enabled in every mode regardless of what the target does
            // with the clock. A latch gates on the same net a flip-flop clocks on, and
            // whether that alone keeps the branch enabled is exactly what this keeper
            // stops the diff from depending on.
            (* DONT_TOUCH = "TRUE" *)
            FDRE #(.INIT(1'b0)) anchor_ff2 (
                .C(clk_g), .CE(1'b1), .R(1'b0), .D(w2), .Q(anchor_o2)
            );
        end else begin : g_no_anchor
            assign anchor_o  = 1'b0;
            assign anchor_o2 = 1'b0;
        end
    endgenerate

    generate
        // ---- single-element modes ------------------------------------------------
        if (MODE <= 3) begin : g_single
            (* DONT_TOUCH = "TRUE" *)
            LUT6 #(.INIT(64'hA5A5A5A5A5A5A5A5)) target_lut (
                .I0(i[0]), .I1(i[1]), .I2(i[2]), .I3(i[3]), .I4(i[4]), .I5(i[5]), .O(lo)
            );
            assign o = lo;

            if (MODE == 0) begin : g_fdce
                (* DONT_TOUCH = "TRUE" *)
                FDCE #(.INIT(1'b0)) storage (
                    .C(clk_g), .CE(ce), .CLR(rst), .D(lo), .Q(q_int)
                );
            end else if (MODE == 1) begin : g_ldce
                (* DONT_TOUCH = "TRUE" *)
                LDCE #(.INIT(1'b0)) storage (
                    .G(clk_g), .GE(ce), .CLR(rst), .D(lo), .Q(q_int)
                );
            end else if (MODE == 2) begin : g_fdre
                (* DONT_TOUCH = "TRUE" *)
                FDRE #(.INIT(1'b0)) storage (
                    .C(clk_g), .CE(ce), .R(rst), .D(lo), .Q(q_int)
                );
            end else begin : g_fdce_inv
                (* DONT_TOUCH = "TRUE" *)
                FDCE #(.INIT(1'b0), .IS_C_INVERTED(1'b1)) storage (
                    .C(clk_g), .CE(ce), .CLR(rst), .D(lo), .Q(q_int)
                );
            end

        // ---- full-slice modes ----------------------------------------------------
        end else begin : g_full
            localparam integer NFF = (MODE < 6) ? 8 : 4;
            wire [3:0] o6;
            wire [3:0] o5;
            wire [7:0] qb;
            wire qr1;

            genvar k;
            // A pair of LUT5s per physical LUT rather than one LUT6_2: the macro's
            // children are what actually carry the BEL, and `set_property BEL` on a
            // macro is a silent no-op (`docs/lutram_inventory.md` — it cost two
            // debugging rounds there). Two LUT5s sharing the same five inputs is what a
            // 7-series LUT site holds when both O6 and O5 are used, stated explicitly so
            // every BEL is constrained by name.
            for (k = 0; k < 4; k = k + 1) begin : g_hi
                (* DONT_TOUCH = "TRUE" *)
                LUT5 #(.INIT(32'hA5A5A5A5)) l (
                    .I0(i[0]), .I1(i[1]), .I2(i[2]), .I3(i[3]), .I4(i[4]), .O(o6[k])
                );
            end
            for (k = 0; k < 4; k = k + 1) begin : g_lo
                (* DONT_TOUCH = "TRUE" *)
                LUT5 #(.INIT(32'h5A5A5A5A)) l (
                    .I0(i[0]), .I1(i[1]), .I2(i[2]), .I3(i[3]), .I4(i[4]), .O(o5[k])
                );
            end
            assign lo = o6[0];
            assign o  = lo;

            for (k = 0; k < 8; k = k + 1) begin : g_store
                if (k < NFF) begin : g_used
                    // 8-element modes alternate main element (O6) and 5FF (O5);
                    // 4-element modes use the four MAIN elements only, because the 5FF
                    // BELs are type FF_INIT and Vivado refuses to place a latch on one
                    // — measured, see docs/ff_latch_probe.md.
                    if (MODE == 4 || MODE == 6) begin : g_ff
                        (* DONT_TOUCH = "TRUE" *)
                        FDCE #(.INIT(1'b0), .IS_C_INVERTED(1'b1)) s (
                            .C(clk_g), .CE(ce), .CLR(rst),
                            .D((NFF == 8) ? ((k % 2 == 0) ? o6[k / 2] : o5[k / 2]) : o6[k]),
                            .Q(qb[k])
                        );
                    end else begin : g_latch
                        (* DONT_TOUCH = "TRUE" *)
                        LDCE #(.INIT(1'b0)) s (
                            .G(clk_g), .GE(ce), .CLR(rst),
                            .D((NFF == 8) ? ((k % 2 == 0) ? o6[k / 2] : o5[k / 2]) : o6[k]),
                            .Q(qb[k])
                        );
                    end
                end else begin : g_unused
                    assign qb[k] = 1'b0;
                end
            end

            // Eight Q bits reduced to the single `q` port by two LUT6s the Tcl pins into
            // the anchor tile. Widening `q` to a vector would change the IO ring, and
            // letting the placer put the reduction wherever it liked would put structure
            // back into the diff that the anchors exist to remove.
            (* DONT_TOUCH = "TRUE" *)
            LUT6 #(.INIT(64'h6996966996696996)) q_reduce1 (
                .I0(qb[0]), .I1(qb[1]), .I2(qb[2]), .I3(qb[3]), .I4(qb[4]), .I5(qb[5]),
                .O(qr1)
            );
            (* DONT_TOUCH = "TRUE" *)
            LUT6 #(.INIT(64'h6996966996696996)) q_reduce2 (
                .I0(qr1), .I1(qb[6]), .I2(qb[7]), .I3(qr1), .I4(qr1), .I5(qr1),
                .O(q_int)
            );
        end
    endgenerate
endmodule
