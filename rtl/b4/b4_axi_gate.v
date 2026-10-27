// B4 carrier v2 — the AXI gate: the piece that makes the init event safe for the bus.
//
// The init event (GSR) resets every flip-flop of the PL, the AXI3->Lite shim and the register file included. A
// transaction in flight at that moment would be lost: an accepted AW whose W / B never completes, a B or R the
// master has not yet taken (the owner's reproduction: BREADY held low after INIT_REQ lost the write response).
// This gate sits in front of a slave on every path the PS can take (b4_top: in front of the shim; b4_core: at the
// Lite port) and does two things with the VALID / READY lines only (every other signal passes straight through):
//   * STALL: while `stall` is high no NEW transaction is accepted, and every half of a write that HAS been accepted
//     is let through to completion — a write is two independent channels, so the rule is per half:
//       - AR is hidden (the master holds ARVALID);
//       - AW is hidden UNLESS its W was already accepted (`w_early`: an AXI-Lite master may deliver W first; that W is
//         in the register file and the event must not clear it, so its AW is admitted and the write completes);
//       - W is hidden UNLESS a write address is outstanding (`wr_out`: the beats of an accepted write — every beat of
//         an accepted AXI3 burst, the owner's 2026-10-21 reproduction with INIT_REQ in beat 1 — always drain).
//     A W-first transfer presented during the stall is therefore held, not acknowledged (the owner's 2026-10-21
//     standalone reproduction: an acknowledged W cleared by the GSR left its later AW without a response forever);
//     a W accepted before the stall is outstanding and holds the launch until its write is answered. `enable` = 0 turns
//     the hiding off and keeps the tracking: the core's Lite gate under the shim, where every Lite transfer belongs to a
//     transaction the outer gate admitted (b4_core LITE_STALL);
//   * QUIET: `quiet` is high when nothing is outstanding on this path — no write between the acceptance of its first
//     half (AW, or a W that came first) and its B handshake, no read between its AR acceptance and its last-beat R
//     handshake, no response pending.
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
    reg wr_out, w_early, rd_out;
    wire mask    = stall && enable;
    wire mask_aw = mask && !w_early;          // the AW of a W already accepted is admitted
    wire mask_w  = mask && !wr_out;           // the beats of an accepted write address drain
    assign s_awvalid = m_awvalid && !mask_aw;  assign m_awready = s_awready && !mask_aw;
    assign s_wvalid  = m_wvalid  && !mask_w;   assign m_wready  = s_wready  && !mask_w;
    assign s_arvalid = m_arvalid && !mask;     assign m_arready = s_arready && !mask;
    wire aw_hs = s_awvalid && s_awready, w_hs = s_wvalid && s_wready;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin wr_out <= 1'b0; w_early <= 1'b0; rd_out <= 1'b0; end
        else begin
            if (aw_hs) wr_out <= 1'b1;
            else if (bvalid && bready) wr_out <= 1'b0;
            if (aw_hs) w_early <= 1'b0;                              // paired: wr_out carries it to its B
            else if (w_hs && !wr_out) w_early <= 1'b1;               // a W ahead of its AW
            if (s_arvalid && s_arready) rd_out <= 1'b1;
            else if (rvalid && rready && rlast) rd_out <= 1'b0;
        end
    end
    // outstanding = accepted and not yet answered. A VALID the master holds at a stalled gate is WAITING, not outstanding:
    // it cannot be accepted while the stall lasts, so it must not hold the launch (a first version counted it and deadlocked
    // on a read presented during the window — the scenario read_during_window). A W accepted ahead of its AW IS outstanding.
    assign quiet = !wr_out && !w_early && !rd_out && !bvalid && !rvalid;
endmodule
`default_nettype wire
