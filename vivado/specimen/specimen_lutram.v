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

module specimen_lutram #(
    parameter MODE = 0
) (
    input  wire [7:0] a,
    input  wire       clk,
    input  wire       we,
    input  wire       d,
    output wire       o
);
    wire clk_g;
    BUFG bufg_inst (.I(clk), .O(clk_g));

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
