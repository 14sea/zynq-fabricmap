// Minimal specimen: one explicitly instantiated LUT6 at a pinned site.
//
// The design exists only so that a bitstream can be written; what matters is that
// exactly one configurable element is under our control and that its placement is
// fixed, so that two bitstreams differing only in the LUT's INIT differ only in the
// bits that encode that INIT.  Everything else (IOBs, the routing to them) is
// identical across variants by construction, because the variants are written from
// the same placed-and-routed design.
`timescale 1ns / 1ps

module specimen_lut (
    input  wire [5:0] i,
    output wire       o
);
    (* DONT_TOUCH = "TRUE" *)
    LUT6 #(.INIT(64'h0000000000000000)) target (
        .I0(i[0]), .I1(i[1]), .I2(i[2]), .I3(i[3]), .I4(i[4]), .I5(i[5]), .O(o)
    );
endmodule
