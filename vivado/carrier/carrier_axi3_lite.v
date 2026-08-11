// Claim B round 1 carrier — AXI3 slave to AXI4-Lite master, for PS7's M_AXI_GP0.
//
// WHY THIS EXISTS: erratum 002. `carrier_top` used to wire `M_AXI_GP0` straight to
// `carrier_axil` with the AXI4-Lite signal set. `M_AXI_GP0` is an AXI3 master, and
// `MAXIGP0RLAST` is an INPUT to PS7 — left unconnected it is tied low, so the master
// raises a read, takes the beat, never sees the last beat, and waits forever. The A9
// stalls and the board needs a power cycle. That is exactly what board 17A6 did on the
// first read the transport ever issued. A write would have completed, which is why the
// defect could hide until the first `md`.
//
// WHAT IT GUARANTEES
// ------------------
//   * every accepted transaction COMPLETES. There is no input this module can be given
//     that leaves a channel hanging — not a burst, not a bad size, not a WLAST in the
//     wrong place, not a WID that does not match. Unsupported means "finish it and answer
//     SLVERR", never "wait for something that is not coming". Hanging is the failure mode
//     that costs a power cycle, so it is the one thing that must be structurally absent.
//   * a burst is converted BEAT BY BEAT into AXI4-Lite transfers. It is never truncated,
//     and never silently turned into a single transfer — the old wiring ignored AWLEN and
//     ARLEN entirely, which would have dropped beats without a word of complaint.
//   * `BID`/`RID` echo the request's ID and `RLAST` marks the last beat, because those
//     are what the master is waiting for.
//
// SERIALISED ON PURPOSE. One transaction is in flight at a time, so the address register,
// the incrementer and the beat counter are shared between the read and the write path.
// AXI permits it — a slave may accept AW and AR whenever it chooses — and the alternative
// costs a second copy of all three in a region that has ~68 spare LUTs. There is no
// deadlock in it: neither channel's acceptance depends on the other making progress.
//
// SIZE IS 3 BITS HERE and 2 bits on PS7. `MAXIGP0AWSIZE`/`ARSIZE` are `[1:0]` because the
// GP master never transfers more than 4 bytes. This module takes the standard 3-bit field
// so it is a general AXI3 slave that can be benched with sizes PS7 cannot produce, and
// `carrier_top` zero-extends at the boundary where the narrowing is visible.

`default_nettype none

module carrier_axi3_lite #(
    parameter integer ID_W   = 12,
    parameter integer ADDR_W = 16
) (
    input  wire                clk,
    input  wire                rst_n,

    // ---------------------------------------------------------------- AXI3 slave
    input  wire [ID_W-1:0]     s_awid,
    input  wire [31:0]         s_awaddr,
    input  wire [3:0]          s_awlen,
    input  wire [2:0]          s_awsize,
    input  wire [1:0]          s_awburst,
    input  wire                s_awvalid,
    output wire                s_awready,

    input  wire [ID_W-1:0]     s_wid,
    input  wire [31:0]         s_wdata,
    input  wire [3:0]          s_wstrb,
    input  wire                s_wlast,
    input  wire                s_wvalid,
    output wire                s_wready,

    output wire [ID_W-1:0]     s_bid,
    output wire [1:0]          s_bresp,
    output wire                s_bvalid,
    input  wire                s_bready,

    input  wire [ID_W-1:0]     s_arid,
    input  wire [31:0]         s_araddr,
    input  wire [3:0]          s_arlen,
    input  wire [2:0]          s_arsize,
    input  wire [1:0]          s_arburst,
    input  wire                s_arvalid,
    output wire                s_arready,

    output wire [ID_W-1:0]     s_rid,
    output wire [31:0]         s_rdata,
    output wire [1:0]          s_rresp,
    output wire                s_rlast,
    output wire                s_rvalid,
    input  wire                s_rready,

    // ----------------------------------------------------------- AXI4-Lite master
    output wire [ADDR_W-1:0]   m_awaddr,
    output wire                m_awvalid,
    input  wire                m_awready,
    output wire [31:0]         m_wdata,
    output wire [3:0]          m_wstrb,
    output wire                m_wvalid,
    input  wire                m_wready,
    input  wire [1:0]          m_bresp,
    input  wire                m_bvalid,
    output wire                m_bready,

    output wire [ADDR_W-1:0]   m_araddr,
    output wire                m_arvalid,
    input  wire                m_arready,
    input  wire [31:0]         m_rdata,
    input  wire [1:0]          m_rresp,
    input  wire                m_rvalid,
    output wire                m_rready
);
    localparam [1:0] RESP_OKAY = 2'b00, RESP_SLVERR = 2'b10;
    localparam [1:0] BURST_FIXED = 2'b00, BURST_INCR = 2'b01;
    localparam [2:0] SIZE_4B = 3'b010;

    localparam [2:0] S_IDLE    = 3'd0,
                     S_RD_REQ  = 3'd1,   // present the lite read address
                     S_RD_BEAT = 3'd3,   // pass one R beat through to the master
                     S_WR_BEAT = 3'd4,   // take one W beat, present the lite write
                     S_WR_WAIT = 3'd5,   // take the lite write response
                     S_WR_RESP = 3'd6;   // hand one B response to the master

    reg  [2:0]        state;
    // SEPARATE ID registers, not one shared one. A single `id` needs a 2:1 mux in front
    // of twelve flip-flops — twelve LUTs — while two registers each load from their own
    // channel and drive their own output, which is twelve LUTs of nothing. Flip-flops are
    // what this region has spare; LUTs are what it does not.
    reg  [ID_W-1:0]   awid_q, arid_q;
    reg  [ADDR_W-1:2] word_addr;
    reg  [3:0]        beats;             // beats REMAINING after the current one
    reg               fixed;             // FIXED burst: the address does not advance
    reg               bad;               // unsupported: complete it, answer SLVERR
    reg               err;               // any beat answered SLVERR, or a protocol fault
    reg               wr_done;           // the beat just taken ended the transaction

    // A transaction this module will not perform against the register file. It is still
    // completed, beat for beat, with SLVERR — an unsupported transaction that stalled
    // would be the very failure erratum 002 is about.
    function automatic unsupported(input [2:0] size, input [1:0] burst);
        unsupported = (size != SIZE_4B) ||
                      ((burst != BURST_INCR) && (burst != BURST_FIXED));
    endfunction

    wire is_last = (beats == 4'd0);

    // -------------------------------------------------------------- handshakes out
    assign s_awready = (state == S_IDLE) && s_awvalid;
    assign s_arready = (state == S_IDLE) && !s_awvalid && s_arvalid;

    // A WID that does not match the AW belongs to another transaction. AXI3 permits write
    // data interleaving between IDs and this module does not implement it, so the beat must
    // not be written anywhere — and that has to be decided COMBINATIONALLY, on the beat
    // itself. Setting a flag in the clocked block and answering SLVERR afterwards still
    // lets the mismatching beat through to the register file first, which is precisely
    // "writing it somewhere plausible": the response says refused while the fabric says
    // written. The comparator is the one already needed for `err`, reused here.
    wire wid_bad  = (s_wid != awid_q);
    // Once a beat is refused the whole transaction is refused: `bad` latches, so the
    // remaining beats drain without reaching the lite side however well-formed they are.
    // It is cleared only by the next AW/AR acceptance in S_IDLE.
    wire drop_beat = bad || wid_bad;

    // A write beat is consumed either by the lite side taking it, or — when the beat is
    // refused — by this module alone. Both count as one beat.
    wire wr_fire_lite = (state == S_WR_BEAT) && !drop_beat && s_wvalid
                        && m_awready && m_wready;
    wire wr_fire_drop = (state == S_WR_BEAT) && drop_beat && s_wvalid;
    assign s_wready  = (state == S_WR_BEAT) && (drop_beat || (m_awready && m_wready));

    assign s_bid   = awid_q;
    assign s_bresp = err ? RESP_SLVERR : RESP_OKAY;
    assign s_bvalid = (state == S_WR_RESP);

    // R is a PASS-THROUGH. `carrier_axil` already holds RDATA and RRESP until RREADY, so
    // a copy here is 32 flip-flops and a state to fill them, for a value that is already
    // being held one module away. Only RLAST and RID are this module's to produce.
    assign s_rid    = arid_q;
    assign s_rdata  = m_rdata;
    assign s_rresp  = bad ? RESP_SLVERR : m_rresp;
    assign s_rlast  = is_last;
    assign s_rvalid = (state == S_RD_BEAT) && (bad || m_rvalid);

    // ------------------------------------------------------------- lite side out
    assign m_araddr  = {word_addr, 2'b00};
    assign m_arvalid = (state == S_RD_REQ) && !bad;
    assign m_rready  = (state == S_RD_BEAT) && !bad && s_rready;

    assign m_awaddr  = {word_addr, 2'b00};
    assign m_awvalid = (state == S_WR_BEAT) && !drop_beat && s_wvalid;
    assign m_wdata   = s_wdata;
    assign m_wstrb   = s_wstrb;
    assign m_wvalid  = (state == S_WR_BEAT) && !drop_beat && s_wvalid;
    assign m_bready  = (state == S_WR_WAIT);

    // ------------------------------------------------------------------- the FSM
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= S_IDLE;
            awid_q    <= {ID_W{1'b0}};
            arid_q    <= {ID_W{1'b0}};
            word_addr <= {(ADDR_W-2){1'b0}};
            beats     <= 4'd0;
            fixed     <= 1'b0;
            bad       <= 1'b0;
            err       <= 1'b0;
            wr_done   <= 1'b0;
        end else begin
            case (state)
                S_IDLE: begin
                    err     <= 1'b0;
                    wr_done <= 1'b0;
                    // Writes take priority, arbitrarily and harmlessly: AXI imposes no
                    // ordering between the channels, and each transaction completes, so
                    // neither side can starve the other.
                    if (s_awvalid) begin
                        awid_q    <= s_awid;
                        word_addr <= s_awaddr[ADDR_W-1:2];
                        beats     <= s_awlen;
                        fixed     <= (s_awburst == BURST_FIXED);
                        bad       <= unsupported(s_awsize, s_awburst);
                        state     <= S_WR_BEAT;
                    end else if (s_arvalid) begin
                        arid_q    <= s_arid;
                        word_addr <= s_araddr[ADDR_W-1:2];
                        beats     <= s_arlen;
                        fixed     <= (s_arburst == BURST_FIXED);
                        bad       <= unsupported(s_arsize, s_arburst);
                        state     <= S_RD_REQ;
                    end
                end

                // ---- read ------------------------------------------------------
                // A refused read skips the lite side entirely and goes straight to the
                // beat. RDATA is whatever the lite side last drove — AXI says read data is
                // not valid when RRESP reports an error, so forcing it to zero would only
                // buy a 32-bit mux. The refusal travels on RRESP, which is where a master
                // reads it.
                S_RD_REQ: begin
                    if (bad || m_arready) state <= S_RD_BEAT;
                end

                S_RD_BEAT: begin
                    if (s_rvalid && s_rready) begin
                        if (is_last) begin
                            state <= S_IDLE;
                        end else begin
                            beats     <= beats - 4'd1;
                            if (!fixed) word_addr <= word_addr + 1'b1;
                            state     <= S_RD_REQ;
                        end
                    end
                end

                // ---- write -----------------------------------------------------
                S_WR_BEAT: begin
                    if (wr_fire_lite || wr_fire_drop) begin
                        // The beat was already withheld from the lite side by
                        // `drop_beat`; this latches the refusal so the rest of the
                        // transaction drains rather than resuming on the next good WID.
                        if (wid_bad) begin
                            err <= 1'b1;
                            bad <= 1'b1;
                        end
                        // WLAST in the wrong place is also a fault, and BOTH directions of
                        // it end the transaction here. Waiting for a beat the master has
                        // already declared finished, or waiting for more beats after its
                        // last one, are the two ways this could hang.
                        if (s_wlast != is_last) err <= 1'b1;
                        if (bad) err <= 1'b1;
                        if (s_wlast || is_last) begin
                            wr_done <= 1'b1;
                            state   <= wr_fire_drop ? S_WR_RESP : S_WR_WAIT;
                        end else begin
                            beats   <= beats - 4'd1;
                            if (!fixed) word_addr <= word_addr + 1'b1;
                            wr_done <= 1'b0;
                            state   <= wr_fire_drop ? S_WR_BEAT : S_WR_WAIT;
                        end
                    end
                end

                // `wr_done` and not `beats == 0`: on the second-to-last beat the counter
                // reaches zero here too, and reading it as "finished" would drop the last
                // beat of every burst — the silent truncation this module exists to
                // prevent, reintroduced one state later.
                S_WR_WAIT: begin
                    if (m_bvalid) begin
                        if (m_bresp != RESP_OKAY) err <= 1'b1;
                        state <= wr_done ? S_WR_RESP : S_WR_BEAT;
                    end
                end

                S_WR_RESP: begin
                    if (s_bready) state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end
endmodule

`default_nettype wire
