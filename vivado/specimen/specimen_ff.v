// Specimen for the clb_ff_config class.
//
// The class splits into two scopes and the specimen has to respect the split:
//
//   per-FF     ZINI, ZRST      — one bit per flip-flop, 8 per slice
//   per-SLICE  CEUSEDMUX, SRUSEDMUX, FFSYNC, LATCH, CLKINV/NOCLKINV
//              — one bit per slice, SHARED by all eight of its flip-flops
//
// So a control-set change is never local to one FF: it moves bits that belong to the
// whole slice. That is a degree of freedom this specimen pins by instantiating exactly
// one storage element per slice under test.
`timescale 1ns / 1ps

module specimen_ff #(
    parameter INIT_VAL = 1'b0,      // -> the FF's own ZINI bit
    parameter USE_CE   = 1,         // -> slice-wide CEUSEDMUX
    parameter USE_R    = 1          // -> slice-wide SRUSEDMUX
) (
    input  wire [5:0] i,
    input  wire       clk,
    input  wire       ce,
    input  wire       rst,
    output wire       o,
    output wire       q
);
    wire lo, clk_g;

    BUFG bufg_inst (.I(clk), .O(clk_g));

    (* DONT_TOUCH = "TRUE" *)
    LUT6 #(.INIT(64'hA5A5A5A5A5A5A5A5)) target (
        .I0(i[0]), .I1(i[1]), .I2(i[2]), .I3(i[3]), .I4(i[4]), .I5(i[5]), .O(lo)
    );

    (* DONT_TOUCH = "TRUE" *)
    FDRE #(.INIT(INIT_VAL)) ff (
        .C(clk_g),
        .CE(USE_CE ? ce  : 1'b1),
        .R (USE_R  ? rst : 1'b0),
        .D (lo), .Q(q)
    );

    assign o = lo;
endmodule
