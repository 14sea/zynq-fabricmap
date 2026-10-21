// B4 carrier v2 — a GSR-immune register: W bits of RAM32X1S (distributed LUTRAM) at address 0.
//
// The initialisation mechanism of this carrier is the device's global set / reset (GSR), raised by the
// carrier itself through STARTUPE2 (b4_engine). GSR returns EVERY flip-flop of the PL to its INIT value,
// the carrier's own included; LUTRAM is configuration memory and is untouched by it (witnessed on the
// vendor models: tb/b4). So everything that must survive the init event of a transaction — the
// provisioned key, the nonce chain, the sticky fault, the armed latch, the samples and the witnesses —
// is kept here and nowhere else. Read is asynchronous (the value is always visible); write is one
// WCLK edge with `we`. INIT is the value after configuration (and after a reconfiguration, which is the
// only thing that clears it).
`default_nettype none
module b4_gsr_reg #(
    parameter integer W = 1,
    parameter [W-1:0] INIT = {W{1'b0}}
) (
    input  wire         wclk,
    input  wire         we,
    input  wire [W-1:0] d,
    output wire [W-1:0] q
);
    genvar i;
    generate
        for (i = 0; i < W; i = i + 1) begin : g
            (* DONT_TOUCH = "TRUE" *) RAM32X1S #(.INIT({31'd0, INIT[i]})) r (
                .O(q[i]), .A0(1'b0), .A1(1'b0), .A2(1'b0), .A3(1'b0), .A4(1'b0),
                .D(d[i]), .WCLK(wclk), .WE(we));
        end
    endgenerate
endmodule
`default_nettype wire
