// B4 carrier v2 — the target: the eight storage elements of the certified site SLICE_X2Y25 and the
// four LUT6 that feed the main elements' D inputs (vivado/b4/b4.xdc pins every cell to its BEL).
//
// Element order, everywhere in this carrier: AFF, A5FF, BFF, B5FF, CFF, C5FF, DFF, D5FF
// (b4/host/b4_ff_model.ELEMENTS; bit i of `d` and `q` is element i).
//
// The base configuration is the all-zero genome of the 21 certified addresses (docs/ff_preregistration_plan.md
// section 2's Z convention): INIT = 1, SRVAL = 1, CE tied high, SR tied low, asynchronous, flip-flop, clock
// not inverted — eight FDPE. CE and SR ARE connected to the engine's nets here so that the slice's CE and
// SR pins are routed: the loaded bitstream therefore carries CEUSEDMUX = SRUSEDMUX = 1, and the session
// root writes genome 0 as a signed candidate (docs/b4_observation_contract.md 5.5). A 7-series slice has
// ONE CE, ONE SR and ONE CLK pin for its eight elements: `ce` and `sr` are one bit each by construction
// (the per-element vectors of the task stimulus are realisable only when uniform — b4_engine refuses the
// rest by name). The main elements take D from LUT6 O6 (a pass-through of I0, LOCK_PINS I0:A1); the
// x5FF elements take D from the AX..DX bypass pins. The slice clock is a fabric net driven by the engine.
// `gsr` is unused in silicon (the real GSR reaches these cells globally); the bench's model of this
// module uses it (tb/b4/b4_target_slice_model.v).
`default_nettype none
module b4_target_slice (
    input  wire       slice_clk,
    input  wire       ce,
    input  wire       sr,
    input  wire [7:0] d,
    output wire [7:0] q,
    input  wire       gsr
);
    wire [3:0] lut_o;
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(64'hAAAAAAAAAAAAAAAA)) target_lut_a (.O(lut_o[0]), .I0(d[0]), .I1(1'b0), .I2(1'b0), .I3(1'b0), .I4(1'b0), .I5(1'b0));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(64'hAAAAAAAAAAAAAAAA)) target_lut_b (.O(lut_o[1]), .I0(d[2]), .I1(1'b0), .I2(1'b0), .I3(1'b0), .I4(1'b0), .I5(1'b0));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(64'hAAAAAAAAAAAAAAAA)) target_lut_c (.O(lut_o[2]), .I0(d[4]), .I1(1'b0), .I2(1'b0), .I3(1'b0), .I4(1'b0), .I5(1'b0));
    (* DONT_TOUCH = "TRUE" *) LUT6 #(.INIT(64'hAAAAAAAAAAAAAAAA)) target_lut_d (.O(lut_o[3]), .I0(d[6]), .I1(1'b0), .I2(1'b0), .I3(1'b0), .I4(1'b0), .I5(1'b0));
    (* DONT_TOUCH = "TRUE" *) FDPE #(.INIT(1'b1)) target_ff_aff  (.Q(q[0]), .C(slice_clk), .CE(ce), .D(lut_o[0]), .PRE(sr));
    (* DONT_TOUCH = "TRUE" *) FDPE #(.INIT(1'b1)) target_ff_a5ff (.Q(q[1]), .C(slice_clk), .CE(ce), .D(d[1]),     .PRE(sr));
    (* DONT_TOUCH = "TRUE" *) FDPE #(.INIT(1'b1)) target_ff_bff  (.Q(q[2]), .C(slice_clk), .CE(ce), .D(lut_o[1]), .PRE(sr));
    (* DONT_TOUCH = "TRUE" *) FDPE #(.INIT(1'b1)) target_ff_b5ff (.Q(q[3]), .C(slice_clk), .CE(ce), .D(d[3]),     .PRE(sr));
    (* DONT_TOUCH = "TRUE" *) FDPE #(.INIT(1'b1)) target_ff_cff  (.Q(q[4]), .C(slice_clk), .CE(ce), .D(lut_o[2]), .PRE(sr));
    (* DONT_TOUCH = "TRUE" *) FDPE #(.INIT(1'b1)) target_ff_c5ff (.Q(q[5]), .C(slice_clk), .CE(ce), .D(d[5]),     .PRE(sr));
    (* DONT_TOUCH = "TRUE" *) FDPE #(.INIT(1'b1)) target_ff_dff  (.Q(q[6]), .C(slice_clk), .CE(ce), .D(lut_o[3]), .PRE(sr));
    (* DONT_TOUCH = "TRUE" *) FDPE #(.INIT(1'b1)) target_ff_d5ff (.Q(q[7]), .C(slice_clk), .CE(ce), .D(d[7]),     .PRE(sr));
endmodule
`default_nettype wire
