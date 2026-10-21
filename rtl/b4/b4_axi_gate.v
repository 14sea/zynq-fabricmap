// B4 carrier v2 — the AXI gate: the piece that makes the init event safe for the bus.
//
// The init event (GSR) resets every flip-flop of the PL, the AXI3->Lite shim and the register file included. A
// transaction in flight at that moment would be lost: an accepted AW whose W / B never completes, a B or R the
// master has not yet taken (the owner's reproduction: BREADY held low after INIT_REQ lost the write response).
// This gate sits in front of a slave on every path the PS can take (b4_top: in front of the shim; b4_core: at the
// Lite port) and does two things with the VALID / READY lines only (every other signal passes straight through):
//   * STALL: while `stall` is high no NEW transaction is accepted — AW and AR are hidden from the slave and their
//     readies from the master, so the master simply holds its VALID (AXI allows a slave to wait). W is never masked:
//     a W beat belongs to a transaction already accepted (the shim accepts AW first), and masking it would leave an
//     accepted burst unable to drain while the engine waits for exactly that burst's B (the owner's reproduction of
//     2026-10-21: a two-beat FIXED write whose first beat is INIT_REQ). `enable` = 0 turns the masking off and keeps
//     the tracking: the core's Lite gate under the shim, where every Lite transfer is a beat of a transaction the
//     outer gate has already admitted (b4_core LITE_STALL);
//   * QUIET: `quiet` is high when nothing is outstanding on this path — no write between its AW acceptance and
//     its B handshake, no read between its AR acceptance and its last-beat R handshake, no response pending.
// The engine raises `stall` from the persisted `init_pending` (it survives the reset) and launches the event only
// after ASSERT_DELAY consecutive quiet cycles on every gated path: an outstanding response is delivered first,
// whatever BREADY does, and nothing new enters until the engine is done. `rlast` is the AXI3 RLAST (tie high for Lite).
`default_nettype none
module b4_axi_gate (
    input  wire clk,
    input  wire rst_n,
    input  wire stall,
    input  wire enable,    // 1: the stall masks new AW / AR; 0: track only (an outer gate does the masking)
    // master side (valid in, ready out)          slave side (valid out, ready in)
    input  wire m_awvalid, output wire m_awready,   output wire s_awvalid, input wire s_awready,
    input  wire m_wvalid,  output wire m_wready,    output wire s_wvalid,  input wire s_wready,
    input  wire m_arvalid, output wire m_arready,   output wire s_arvalid, input wire s_arready,
    // the response channels pass through; observed only
    input  wire bvalid, input wire bready,
    input  wire rvalid, input wire rready, input wire rlast,
    output wire quiet
);
    wire mask = stall && enable;
    assign s_awvalid = m_awvalid && !mask;   assign m_awready = s_awready && !mask;
    assign s_wvalid  = m_wvalid;             assign m_wready  = s_wready;             // W drains always
    assign s_arvalid = m_arvalid && !mask;   assign m_arready = s_arready && !mask;
    reg wr_out, rd_out;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin wr_out <= 1'b0; rd_out <= 1'b0; end
        else begin
            if (s_awvalid && s_awready) wr_out <= 1'b1;
            else if (bvalid && bready) wr_out <= 1'b0;
            if (s_arvalid && s_arready) rd_out <= 1'b1;
            else if (rvalid && rready && rlast) rd_out <= 1'b0;
        end
    end
    // outstanding = accepted and not yet answered. A VALID the master holds at a stalled gate is WAITING, not outstanding:
    // it cannot be accepted while the stall lasts, so it must not hold the launch (a first version counted it and deadlocked
    // on a read presented during the window — the scenario read_during_window)
    assign quiet = !wr_out && !rd_out && !bvalid && !rvalid;
endmodule
`default_nettype wire
