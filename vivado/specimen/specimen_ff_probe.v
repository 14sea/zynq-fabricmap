// Probe family for the `clb_ff_config` LATCH question. NOT a certification specimen.
//
// `docs/ff_preregistration_plan.md` §5 risk 3: the LATCH pair is the one place the
// 176-key plan is not yet known to be safe. `LDCE` is a different primitive from the
// plan's baseline `FDRE`, and it does not have `CE`/`R` in the same shape, so the pair
// was expected to move more of the slice-wide control set than the single `LATCH` bit.
// Those extra movers would be `db_attributed` AND claimed by this class AND outside the
// pair's one preregistered scope — false positives under the fixed 1.4 rule, with FP=0
// required.
//
// The author ruled: keep LATCH, do not guess a wider scope, and try a CONTROL-MATCHED
// baseline first. That is what MODE 0 is. Reading the three modes against each other:
//
//   MODE 0  FDCE  asynchronous clear, CE driven, CLR driven   <- control-matched baseline
//   MODE 1  LDCE  the latch under test, GE driven, CLR driven <- variant
//   MODE 2  FDRE  synchronous reset — the plan's default baseline B
//
// The claim being probed is that (0 -> 1) isolates to one bit while (2 -> 1) does not,
// because FDRE differs from LDCE in the set/reset KIND as well as in the storage kind.
// Whether that is true is measured, not assumed: `scripts/gate_build_ff.py` builds all
// three and reports every same-class mover with its direction.
//
// Every mode instantiates the same LUT6 feeding the same cell name `storage`, so the
// LOC/BEL constraints and the data source are identical and cannot themselves be what
// moved.
`timescale 1ns / 1ps

// ANCHOR=1 adds fixed consumers of every input port and of the buffered clock in
// another tile, plus a clocked keeper in the SAME CLB COLUMN as the site under test.
// Both exist for reasons measured in the lutram round (`docs/lutram_anchored.md`):
// without the port consumers, different modes trim different IBUFs and the IO ring
// itself changes; without the column keeper, a mode whose target does not clock
// anything leaves that column's clock branch disabled and HCLK bits move. Neither tile
// is in the freeze, so both would land in `ownership_unknown` — FP under 1.4.
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
    wire lo, clk_g;

    BUFG bufg_inst (.I(clk), .O(clk_g));

    (* DONT_TOUCH = "TRUE" *)
    LUT6 #(.INIT(64'hA5A5A5A5A5A5A5A5)) target_lut (
        .I0(i[0]), .I1(i[1]), .I2(i[2]), .I3(i[3]), .I4(i[4]), .I5(i[5]), .O(lo)
    );

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
            // whether that alone keeps the branch enabled is exactly the sort of thing
            // this keeper stops the diff from depending on.
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
        if (MODE == 0) begin : g_fdce
            // Control-matched baseline: asynchronous clear, like LDCE's CLR, with both
            // control inputs really driven.
            (* DONT_TOUCH = "TRUE" *)
            FDCE #(.INIT(1'b0)) storage (
                .C(clk_g), .CE(ce), .CLR(rst), .D(lo), .Q(q)
            );
        end else if (MODE == 1) begin : g_ldce
            (* DONT_TOUCH = "TRUE" *)
            LDCE #(.INIT(1'b0)) storage (
                .G(clk_g), .GE(ce), .CLR(rst), .D(lo), .Q(q)
            );
        end else if (MODE == 2) begin : g_fdre
            // The plan's default baseline B: synchronous reset.
            (* DONT_TOUCH = "TRUE" *)
            FDRE #(.INIT(1'b0)) storage (
                .C(clk_g), .CE(ce), .R(rst), .D(lo), .Q(q)
            );
        end else if (MODE == 3) begin : g_fdce_inv
            // Second control match, added after MODE 0 measured: FDCE->LDCE still moved
            // the CLKINV bit, so the baseline's clock polarity is matched to whatever
            // the latch ends up with. If the remaining mover really is clock inversion
            // and nothing else, this pair reduces to the single LATCH bit.
            (* DONT_TOUCH = "TRUE" *)
            FDCE #(.INIT(1'b0), .IS_C_INVERTED(1'b1)) storage (
                .C(clk_g), .CE(ce), .CLR(rst), .D(lo), .Q(q)
            );
        end
    endgenerate
endmodule
