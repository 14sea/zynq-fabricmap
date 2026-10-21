// B4 carrier v2 — the AXI gate: the piece that makes the init event safe for the bus.
//
// The init event (GSR) resets every flip-flop of the PL, the AXI3->Lite shim and the register file included. A
// transaction in flight at that moment would be lost: an accepted AW whose W / B never completes, a B or R the
// master has not yet taken (the owner's reproduction: BREADY held low after INIT_REQ lost the write response).
// This gate sits in front of a slave on every path the PS can take (b4_top: in front of the shim; b4_core: at the
// Lite port) and does two things with the VALID / READY lines only (every other signal passes straight through):
//   * STALL: while `stall` is high no new AW / W / AR is accepted — the valid is hidden from the slave and the
//     ready is hidden from the master, so the master simply holds its VALID (AXI allows a slave to wait);
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
    // master side (valid in, ready out)          slave side (valid out, ready in)
    input  wire m_awvalid, output wire m_awready,   output wire s_awvalid, input wire s_awready,
    input  wire m_wvalid,  output wire m_wready,    output wire s_wvalid,  input wire s_wready,
    input  wire m_arvalid, output wire m_arready,   output wire s_arvalid, input wire s_arready,
    // the response channels pass through; observed only
    input  wire bvalid, input wire bready,
    input  wire rvalid, input wire rready, input wire rlast,
    output wire quiet
);
    assign s_awvalid = m_awvalid && !stall;  assign m_awready = s_awready && !stall;
    assign s_wvalid  = m_wvalid  && !stall;  assign m_wready  = s_wready  && !stall;
    assign s_arvalid = m_arvalid && !stall;  assign m_arready = s_arready && !stall;
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
