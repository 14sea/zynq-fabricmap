// Specimen for the clb_mux class: the slice's FF-input mux, driven structurally.
//
// Unlike LUT INIT, a mux selection is not a property that can be set on a routed
// design — it is a consequence of what the netlist connects.  So variants here differ
// by a parameter that changes the FF's data source, and each variant is a separate
// implementation run.  That is what makes the isolation problem real: routing may
// legitimately change too, and the harness has to distinguish "the mux bits we are
// testing" from "the routing that had to move".
//
//   FFSRC = 0   FF.D <- LUT6 output          (expected: the O6 member of the group)
//   FFSRC = 1   FF.D <- a package pin        (expected: the bypass member)
//
// Both variants keep the same cells, the same LOC/BEL and the same pins, so the
// netlist difference is exactly one edge.
`timescale 1ns / 1ps

module specimen_mux #(
    parameter integer FFSRC = 0
) (
    input  wire [5:0] i,
    input  wire       clk,
    input  wire       ce,
    input  wire       rst,
    output wire       o,
    output wire       q
);
    wire lo;
    wire clk_g;

    // Explicit BUFG: a FF clocked straight off an IOB is not a legal dedicated route,
    // and letting the tool improvise one would be one more degree of freedom the
    // specimen has not pinned.
    BUFG bufg_inst (.I(clk), .O(clk_g));

    (* DONT_TOUCH = "TRUE" *)
    LUT6 #(.INIT(64'hA5A5A5A5A5A5A5A5)) target (
        .I0(i[0]), .I1(i[1]), .I2(i[2]), .I3(i[3]), .I4(i[4]), .I5(i[5]), .O(lo)
    );

    (* DONT_TOUCH = "TRUE" *)
    FDRE #(.INIT(1'b0)) ff (
        .C(clk_g), .CE(ce), .R(rst), .D(FFSRC ? i[0] : lo), .Q(q)
    );

    assign o = lo;
endmodule
