// Specimen family for the clb_lutram class.
//
// The class is SLICEM-only: all 42 entries live in CLBLM_L / CLBLM_R, on SLICEM_X0,
// and CLBLL tiles carry none of them (`docs/lutram_inventory.md`).  Its 21 features
// per tile type split into three scopes:
//
//   per-LUT     [A-D]LUT.{RAM,SMALL,SRL}      12 features
//   per-LUT     [A-C]LUT.DI1MUX.{direct,cascade}  6 features, 3 complementary pairs
//   per-SLICE   WA7USED, WA8USED, WEMUX.CE     3 features
//
// Unlike clb_ff_config's INIT, none of these is a cell property: every mode is a
// different primitive, so every variant is its own synthesis + place + route and the
// diff carries real routing change.  That is expected and is kept in the evidence
// rather than filtered out.
//
// MODE selects the primitive placed in the target site.  Nothing here asserts what a
// mode *means* in silicon — the modes exist to move bits, and which bits moved is
// measured, not assumed.
`timescale 1ns / 1ps

// ANCHOR=1 adds a fixed consumer of every input port and of the buffered clock,
// placed in a different tile. Without it each mode uses a different subset of the
// ports -- MODE 0 touches a[5:0] and never clk -- so Vivado trims a different set of
// IBUFs and may drop the BUFG, and the IO ring and clock tree differ between the two
// endpoints of a pair. Those tiles are not in the freeze, so the resulting changes
// land in `ownership_unknown`, which certificate 1.4 counts as FP.
//
// ANCHOR=0 means "no anchor cells". It is NOT a compatibility mode: this module now
// declares anchor_o/anchor_o2 unconditionally and build_lutram.tcl pins them
// unconditionally, so even at ANCHOR=0 the design has two extra output ports and their
// OBUFs. `evidence/lutram_isolation_2026_08_03/` is reproduced by commit 044b204, not
// by this file. Making ANCHOR=0 a real compatibility mode would need a wrapper without
// those ports plus a measurement that all seven bitstream hashes match.
module specimen_lutram #(
    parameter MODE   = 0,
    parameter ANCHOR = 0
) (
    input  wire [7:0] a,
    input  wire       clk,
    input  wire       we,
    input  wire       d,
    output wire       o,
    output wire       anchor_o,
    output wire       anchor_o2
);
    wire clk_g;
    BUFG bufg_inst (.I(clk), .O(clk_g));

    generate
        if (ANCHOR) begin : g_anchor
            // Two LUT6s and one FF, all LOC'd and BEL'd by the Tcl to a fixed site in
            // another tile, consuming a[7:0], d, we and clk_g. Identical in every
            // mode, so it contributes no changed bit to any pair -- its only job is to
            // stop the IO/clock structure from varying.
            wire w1, w2;
            (* DONT_TOUCH = "TRUE" *)
            LUT6 #(.INIT(64'h6996966996696996)) anchor_lut1 (
                .I0(a[0]), .I1(a[1]), .I2(a[2]), .I3(a[3]), .I4(a[4]), .I5(a[5]),
                .O(w1)
            );
            (* DONT_TOUCH = "TRUE" *)
            LUT6 #(.INIT(64'h6996966996696996)) anchor_lut2 (
                .I0(a[6]), .I1(a[7]), .I2(d), .I3(we), .I4(w1), .I5(w1),
                .O(w2)
            );
            (* DONT_TOUCH = "TRUE" *)
            FDRE #(.INIT(1'b0)) anchor_ff (
                .C(clk_g), .CE(1'b1), .R(1'b0), .D(w2), .Q(anchor_o)
            );
            // Second clocked keeper, placed by the Tcl in the SAME CLB COLUMN as the
            // site under test. Without it, MODE 0 is the only mode whose target does
            // not clock anything, so that column's clock branch is enabled in every
            // other mode and three HCLK_L bits move in every pair based on mode 0.
            // HCLK_L is not in the freeze, so those land in ownership_unknown.
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
        if (MODE == 0) begin : g_lut6
            // Baseline: a plain LUT6 in a SLICEM LUT. No RAM/SRL feature should be set.
            (* DONT_TOUCH = "TRUE" *)
            LUT6 #(.INIT(64'hA5A5A5A5A5A5A5A5)) target (
                .I0(a[0]), .I1(a[1]), .I2(a[2]), .I3(a[3]), .I4(a[4]), .I5(a[5]),
                .O(o)
            );
        end else if (MODE == 1) begin : g_ram64
            (* DONT_TOUCH = "TRUE" *)
            RAM64X1S #(.INIT(64'h0000000000000000)) target (
                .O(o), .A0(a[0]), .A1(a[1]), .A2(a[2]), .A3(a[3]), .A4(a[4]), .A5(a[5]),
                .D(d), .WCLK(clk_g), .WE(we)
            );
        end else if (MODE == 2) begin : g_ram32
            (* DONT_TOUCH = "TRUE" *)
            RAM32X1S #(.INIT(32'h00000000)) target (
                .O(o), .A0(a[0]), .A1(a[1]), .A2(a[2]), .A3(a[3]), .A4(a[4]),
                .D(d), .WCLK(clk_g), .WE(we)
            );
        end else if (MODE == 3) begin : g_srl32
            (* DONT_TOUCH = "TRUE" *)
            SRLC32E #(.INIT(32'h00000000)) target (
                .Q(o), .Q31(), .A(a[4:0]), .CE(we), .CLK(clk_g), .D(d)
            );
        end else if (MODE == 4) begin : g_ram128
            // Spans two LUTs of the slice; which two is Vivado's choice and is read back.
            (* DONT_TOUCH = "TRUE" *)
            RAM128X1S #(.INIT(128'h0)) target (
                .O(o), .A0(a[0]), .A1(a[1]), .A2(a[2]), .A3(a[3]),
                .A4(a[4]), .A5(a[5]), .A6(a[6]),
                .D(d), .WCLK(clk_g), .WE(we)
            );
        end else if (MODE == 5) begin : g_ram256
            (* DONT_TOUCH = "TRUE" *)
            RAM256X1S #(.INIT(256'h0)) target (
                .O(o), .A(a[7:0]), .D(d), .WCLK(clk_g), .WE(we)
            );
        end else if (MODE == 6) begin : g_srl_cascade
            // Two SRLC32E with Q31 -> D, the shape that exercises a DI1MUX cascade
            // member. Whether it actually selects the cascade input is measured.
            wire q31;
            (* DONT_TOUCH = "TRUE" *)
            SRLC32E #(.INIT(32'h00000000)) target (
                .Q(), .Q31(q31), .A(a[4:0]), .CE(we), .CLK(clk_g), .D(d)
            );
            (* DONT_TOUCH = "TRUE" *)
            SRLC32E #(.INIT(32'h00000000)) target2 (
                .Q(o), .Q31(), .A(a[4:0]), .CE(we), .CLK(clk_g), .D(q31)
            );
        end
    endgenerate
endmodule
