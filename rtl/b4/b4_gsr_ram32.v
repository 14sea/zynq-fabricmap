// B4 carrier v2 — 32 slots of 32 bits, GSR-immune (RAM32X1S), sharing the address with the sample slots: the
// inputs the engine APPLIED when it took each sample (d bits 7:0, ce bits 15:8 as the uniform vector, sr bits 23:16
// likewise, the slice clock bit 24). The record describes applied operations, not attempted MMIO writes.
`default_nettype none
module b4_gsr_ram32 (
    input  wire        wclk,
    input  wire        we,
    input  wire [4:0]  a,
    input  wire [31:0] d,
    output wire [31:0] q
);
    genvar i;
    generate
        for (i = 0; i < 32; i = i + 1) begin : g
            (* DONT_TOUCH = "TRUE" *) RAM32X1S #(.INIT(32'd0)) r (
                .O(q[i]), .A0(a[0]), .A1(a[1]), .A2(a[2]), .A3(a[3]), .A4(a[4]),
                .D(d[i]), .WCLK(wclk), .WE(we));
        end
    endgenerate
endmodule
`default_nettype wire
