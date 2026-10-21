// B4 carrier v2 — the sample slots: 32 slots of 8 bits (one bit per storage element), GSR-immune
// (eight RAM32X1S sharing the address). Slot 0 is the pre-init sample, slot 1 the init sample
// (step 0), slot 2 + k the k-th set step, and the cleanup sample follows the last step. The address
// is the engine's while it writes and the host's otherwise (b4_engine).
`default_nettype none
module b4_slot_ram (
    input  wire       wclk,
    input  wire       we,
    input  wire [4:0] a,
    input  wire [7:0] d,
    output wire [7:0] q
);
    genvar i;
    generate
        for (i = 0; i < 8; i = i + 1) begin : g
            (* DONT_TOUCH = "TRUE" *) RAM32X1S #(.INIT(32'd0)) r (
                .O(q[i]), .A0(a[0]), .A1(a[1]), .A2(a[2]), .A3(a[3]), .A4(a[4]),
                .D(d[i]), .WCLK(wclk), .WE(we));
        end
    endgenerate
endmodule
`default_nettype wire
