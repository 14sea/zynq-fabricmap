// Formal `clb_ff_config` specimen — the 15 place-and-routed variants of the committed
// 184-specimen plan (`gate_runs/run_2026_08_05_ff/predictions.json`, sha256 5440ef27…).
//
// Design of record: `docs/ff_builder_design.md`. This module is an executor of the
// committed plan, not a plan: it knows variant topologies and nothing about which bits
// any of them are predicted to move.
//
// The eight `zini_*` specimens are NOT here. `INIT` is a cell property, so they are
// produced by reopening `base`'s routed checkpoint and changing one attribute — one
// place-and-route serving nine bitstreams (design §2.1). 15 modes × 8 site instances =
// 120 implementations; 23 specimens × 8 = 184.
//
//   MODE 0  base        8x FDRE, INIT=1, CE and R driven, sync, non-inverted clock
//   MODE 1  zrst        as base, except storage element IDX is FDSE (SRVAL=1)
//   MODE 2  ce_tied     as base, CE tied to 1'b1
//   MODE 3  sr_tied     as base, R tied to 1'b0
//   MODE 4  async       8x FDCE, asynchronous clear
//   MODE 5  latch_base  4x FDCE with IS_C_INVERTED on AFF..DFF   <- the LATCH baseline
//   MODE 6  latch       4x LDCE on AFF..DFF
//   MODE 7  clkinv      as base, IS_C_INVERTED on the clock pin
//
// MODE 5/6 are four-element on purpose and it is not a shortcut: `A5FF` and its siblings
// are BEL type `FF_INIT`, and Vivado refuses `LDCE` on one outright. The four-element
// pair reproduced the single-FF LATCH result exactly (`docs/ff_latch_probe.md`), and the
// pair is `latch` against `latch_base` — never against `base`, which would also move
// `FFSYNC` and `CLKINV`.
`timescale 1ns / 1ps

// ANCHOR: fixed consumers of every input port and of the buffered clock, in a tile two
// columns from the target, plus a clocked keeper in the SAME CLB COLUMN as the target.
// Measured in the lutram round: without the port consumers, different modes trim
// different IBUFs and the IO ring changes; without the column keeper, a mode whose
// target does not clock anything leaves that column's clock branch disabled. Both would
// land in `ownership_unknown`, which the fixed 1.4 rule counts as FP with FP=0 required.
//
// An identical port set eliminates one CAUSE of IO-ring movement. It does not establish
// that the IO ring was implemented identically — that is settled by the pairwise
// readback comparison and, in the end, by the five-bucket accounting.
module specimen_ff_formal #(
    parameter MODE = 0,
    parameter IDX  = 0
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
    localparam integer NFF = (MODE == 5 || MODE == 6) ? 4 : 8;

    wire clk_g;
    wire [3:0] o6;
    wire [3:0] o5;
    wire [7:0] qb;
    wire qr1;

    BUFG bufg_inst (.I(clk), .O(clk_g));

    // ---- anchors ---------------------------------------------------------------
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
    // Column keeper. Same CLB column as the target, row 20: it shares the target's
    // frames and never its words (design §3.4). That it keeps the column's clock branch
    // enabled is a HYPOTHESIS supported by one mine-site measurement, not a proof — the
    // freeze establishes only the geometry.
    (* DONT_TOUCH = "TRUE" *)
    FDRE #(.INIT(1'b0)) anchor_ff2 (
        .C(clk_g), .CE(1'b1), .R(1'b0), .D(w2), .Q(anchor_o2)
    );

    // ---- target LUTs: eight LUT5 in every variant, both families -----------------
    // A pair of LUT5s per physical LUT rather than one LUT6_2: the macro's children are
    // what carry the BEL, and `set_property BEL` on a macro is a silent no-op. Keeping
    // all eight in the four-element family too means LUT content bits are identical
    // across the families and only the storage differs.
    genvar k;
    generate
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
    endgenerate

    assign o = o6[0];

    // ---- storage -----------------------------------------------------------------
    // Every branch carries the SAME generate label `g_s`, so the elaborated cell name is
    // `g_store[k].g_s.s` whatever the variant is. Only one branch elaborates, and a
    // uniform name means the Tcl selects cells by one glob instead of by a per-variant
    // path — the class of mistake that "matched nothing, constrained nothing, exited 0".
    generate
        for (k = 0; k < 8; k = k + 1) begin : g_store
            if (k < NFF) begin : g_used
                wire d_k = (NFF == 8) ? ((k % 2 == 0) ? o6[k / 2] : o5[k / 2]) : o6[k];

                if (MODE == 6) begin : g_s
                    (* DONT_TOUCH = "TRUE" *)
                    LDCE #(.INIT(1'b1)) s (
                        .G(clk_g), .GE(ce), .CLR(rst), .D(d_k), .Q(qb[k])
                    );
                end else if (MODE == 5) begin : g_s
                    (* DONT_TOUCH = "TRUE" *)
                    FDCE #(.INIT(1'b1), .IS_C_INVERTED(1'b1)) s (
                        .C(clk_g), .CE(ce), .CLR(rst), .D(d_k), .Q(qb[k])
                    );
                end else if (MODE == 4) begin : g_s
                    (* DONT_TOUCH = "TRUE" *)
                    FDCE #(.INIT(1'b1)) s (
                        .C(clk_g), .CE(ce), .CLR(rst), .D(d_k), .Q(qb[k])
                    );
                end else if (MODE == 1 && k == IDX) begin : g_s
                    (* DONT_TOUCH = "TRUE" *)
                    FDSE #(.INIT(1'b1)) s (
                        .C(clk_g), .CE(ce), .S(rst), .D(d_k), .Q(qb[k])
                    );
                end else if (MODE == 7) begin : g_s
                    (* DONT_TOUCH = "TRUE" *)
                    FDRE #(.INIT(1'b1), .IS_C_INVERTED(1'b1)) s (
                        .C(clk_g), .CE(ce), .R(rst), .D(d_k), .Q(qb[k])
                    );
                end else begin : g_s
                    (* DONT_TOUCH = "TRUE" *)
                    FDRE #(.INIT(1'b1)) s (
                        .C(clk_g),
                        .CE(MODE == 2 ? 1'b1 : ce),
                        .R (MODE == 3 ? 1'b0 : rst),
                        .D(d_k), .Q(qb[k])
                    );
                end
            end else begin : g_unused
                assign qb[k] = 1'b0;
            end
        end
    endgenerate

    // Eight Q bits reduced to the single `q` port by two LUT6s the Tcl pins into the
    // anchor tile. Widening `q` to a vector would change the IO ring; letting the placer
    // choose would put structure back into the diff that the anchors exist to remove.
    //
    // These two are anchor cells by placement, but their INPUTS come from the target and
    // legitimately differ between the four- and eight-element families. That is exactly
    // why the pairwise comparison is tiered: their nets to the target are diagnostic
    // (tier 3), while the nets wholly inside the anchor subgraph are hard-checked.
    (* DONT_TOUCH = "TRUE" *)
    LUT6 #(.INIT(64'h6996966996696996)) q_reduce1 (
        .I0(qb[0]), .I1(qb[1]), .I2(qb[2]), .I3(qb[3]), .I4(qb[4]), .I5(qb[5]), .O(qr1)
    );
    (* DONT_TOUCH = "TRUE" *)
    LUT6 #(.INIT(64'h6996966996696996)) q_reduce2 (
        .I0(qr1), .I1(qb[6]), .I2(qb[7]), .I3(qr1), .I4(qr1), .I5(qr1), .O(q)
    );
endmodule
