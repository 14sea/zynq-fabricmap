// carrier_axi3_lite bench — an INDEPENDENT AXI3 master.
//
// Erratum 002 happened because `tb_carrier_axil.v` drives the slave with the AXI4-Lite
// signal set, which is the design's own signal set: a bench written that way has no RLAST,
// no ID and no burst length to get wrong, so it cannot see them missing. This bench is
// deliberately written from the OTHER side — it is an AXI3 master with IDs, lengths, sizes,
// burst types and WLAST, and it checks what a master actually waits for.
//
// **Every wait in here is bounded.** A hang is the failure erratum 002 is about, and a
// bench that hangs while testing for hangs reports nothing at all: each handshake wait has
// a cycle budget and blowing it is a FAIL with the state printed, never a stalled run.
//
// The lite side is a small model slave shaped like `carrier_axil` — AW and W taken
// together, one B per write, R the cycle after AR — with a programmable stall so
// backpressure is exercised rather than assumed, and one address that answers SLVERR so
// response pass-through is exercised too.

`timescale 1ns/1ps
`default_nettype none

module tb_carrier_axi3;
    localparam integer ID_W = 12;
    localparam integer ADDR_W = 16;
    localparam [1:0] OKAY = 2'b00, SLVERR = 2'b10;
    localparam [1:0] FIXED = 2'b00, INCR = 2'b01, WRAP = 2'b10;
    localparam [2:0] SZ4 = 3'b010, SZ8 = 3'b011;
    localparam integer TIMEOUT = 500;

    integer failures = 0;
    integer lite_writes = 0, lite_reads = 0;

    reg clk = 0; always #5 clk = ~clk;
    reg rst_n = 0;

    // ------------------------------------------------------------- AXI3 master side
    reg  [ID_W-1:0] awid = 0;   reg [31:0] awaddr = 0; reg [3:0] awlen = 0;
    reg  [2:0]      awsize = SZ4; reg [1:0] awburst = INCR; reg awvalid = 0;
    wire            awready;
    reg  [ID_W-1:0] wid = 0;    reg [31:0] wdata = 0; reg [3:0] wstrb = 4'hF;
    reg             wlast = 0, wvalid = 0;
    wire            wready;
    wire [ID_W-1:0] bid;        wire [1:0] bresp; wire bvalid; reg bready = 1;
    reg  [ID_W-1:0] arid = 0;   reg [31:0] araddr = 0; reg [3:0] arlen = 0;
    reg  [2:0]      arsize = SZ4; reg [1:0] arburst = INCR; reg arvalid = 0;
    wire            arready;
    wire [ID_W-1:0] rid;        wire [31:0] rdata; wire [1:0] rresp;
    wire            rlast, rvalid; reg rready = 1;

    // ------------------------------------------------------------- lite model slave
    wire [ADDR_W-1:0] m_awaddr, m_araddr;
    wire              m_awvalid, m_wvalid, m_bready, m_arvalid, m_rready;
    wire [31:0]       m_wdata;  wire [3:0] m_wstrb;
    wire              m_awready, m_wready, m_arready;
    reg               m_bvalid = 0, m_rvalid = 0;
    reg  [1:0]        m_bresp = OKAY, m_rresp = OKAY;
    reg  [31:0]       m_rdata = 0;

    reg [31:0] mem [0:1023];
    integer    stall = 0;                 // cycles of backpressure per lite transfer
    integer    stall_ctr = 0;
    localparam [ADDR_W-1:0] ERR_ADDR = 16'h0F00;   // the one address that answers SLVERR

    carrier_axi3_lite #(.ID_W(ID_W), .ADDR_W(ADDR_W)) dut (
        .clk(clk), .rst_n(rst_n),
        .s_awid(awid), .s_awaddr(awaddr), .s_awlen(awlen), .s_awsize(awsize),
        .s_awburst(awburst), .s_awvalid(awvalid), .s_awready(awready),
        .s_wid(wid), .s_wdata(wdata), .s_wstrb(wstrb), .s_wlast(wlast),
        .s_wvalid(wvalid), .s_wready(wready),
        .s_bid(bid), .s_bresp(bresp), .s_bvalid(bvalid), .s_bready(bready),
        .s_arid(arid), .s_araddr(araddr), .s_arlen(arlen), .s_arsize(arsize),
        .s_arburst(arburst), .s_arvalid(arvalid), .s_arready(arready),
        .s_rid(rid), .s_rdata(rdata), .s_rresp(rresp), .s_rlast(rlast),
        .s_rvalid(rvalid), .s_rready(rready),
        .m_awaddr(m_awaddr), .m_awvalid(m_awvalid), .m_awready(m_awready),
        .m_wdata(m_wdata), .m_wstrb(m_wstrb), .m_wvalid(m_wvalid), .m_wready(m_wready),
        .m_bresp(m_bresp), .m_bvalid(m_bvalid), .m_bready(m_bready),
        .m_araddr(m_araddr), .m_arvalid(m_arvalid), .m_arready(m_arready),
        .m_rdata(m_rdata), .m_rresp(m_rresp), .m_rvalid(m_rvalid), .m_rready(m_rready)
    );

    // The model slave. Shaped like carrier_axil: READY is combinational, AW and W are
    // taken in the same cycle, exactly one B follows, and R is driven the cycle after AR.
    // Modelling READY as a register instead would put a cycle of skew between "the slave
    // decided" and "the beat transferred", and every burst check here is about which beat
    // landed where.
    wire slave_ready = (stall_ctr >= stall);
    assign m_awready = slave_ready && m_awvalid && m_wvalid && !m_bvalid;
    assign m_wready  = m_awready;
    assign m_arready = slave_ready && m_arvalid && !m_rvalid;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            m_bvalid <= 0; m_bresp <= OKAY;
            m_rvalid <= 0; m_rresp <= OKAY; m_rdata <= 0;
            stall_ctr <= 0;
        end else begin
            if (m_bvalid && m_bready) m_bvalid <= 0;
            if (m_rvalid && m_rready) m_rvalid <= 0;

            if (m_awready) begin
                mem[m_awaddr[11:2]] <= m_wdata;
                m_bvalid <= 1;
                m_bresp  <= (m_awaddr == ERR_ADDR) ? SLVERR : OKAY;
                lite_writes = lite_writes + 1;
                stall_ctr <= 0;
            end else if (m_arready) begin
                m_rdata  <= mem[m_araddr[11:2]];
                m_rvalid <= 1;
                m_rresp  <= (m_araddr == ERR_ADDR) ? SLVERR : OKAY;
                lite_reads = lite_reads + 1;
                stall_ctr <= 0;
            end else if ((m_awvalid && m_wvalid && !m_bvalid) ||
                         (m_arvalid && !m_rvalid)) begin
                stall_ctr <= stall_ctr + 1;
            end
        end
    end

    // ------------------------------------------------------------------- helpers
    task fail(input [1023:0] why);
        begin
            $display("FAIL: %0s   (t=%0t)", why, $time);
            failures = failures + 1;
        end
    endtask

    task check(input ok, input [1023:0] why);
        begin if (!ok) fail(why); end
    endtask

    // ------------------------------------------------------- AXI3 master transactions
    //
    // `wlast_at` is the beat index on which WLAST is asserted; -1 asserts it on no beat,
    // and any value other than `len` is a protocol fault the DUT has to survive.
    task axi_write(input [ID_W-1:0] tid, input [31:0] addr, input [3:0] len,
                   input [2:0] size, input [1:0] burst, input [31:0] first,
                   input integer wlast_at, input [ID_W-1:0] use_wid);
        integer beat, n;
        begin
            @(negedge clk);
            awid = tid; awaddr = addr; awlen = len; awsize = size; awburst = burst;
            awvalid = 1;
            #1;
            n = 0;
            while (!awready) begin
                @(negedge clk); #1;
                n = n + 1;
                if (n > TIMEOUT) begin fail("HANG on AW"); awvalid = 0; disable axi_write; end
            end
            @(negedge clk); awvalid = 0;     // the posedge in between took it

            beat = 0;
            while (beat <= len) begin
                wid = (beat == wid_flip_at) ? (use_wid ^ {ID_W{1'b1}}) : use_wid;
                wdata = first + beat; wstrb = 4'hF;
                wlast = (beat == wlast_at); wvalid = 1;
                #1;
                n = 0;
                while (!wready) begin
                    @(negedge clk); #1;
                    n = n + 1;
                    if (n > TIMEOUT) begin
                        fail("HANG on W"); wvalid = 0; wlast = 0; disable axi_write;
                    end
                end
                @(negedge clk);
                // The DUT ends the transaction at an early WLAST; a real master stops
                // driving beats it has already declared finished, so this one does too.
                if (beat == wlast_at) beat = len + 1;
                else                  beat = beat + 1;
            end
            wvalid = 0; wlast = 0;
            #1;

            n = 0;
            while (!bvalid) begin
                @(negedge clk); #1;
                n = n + 1;
                if (n > TIMEOUT) begin fail("HANG on B"); disable axi_write; end
            end
            last_bid = bid; last_bresp = bresp;
            @(negedge clk);                  // bready is held high, so the posedge took it
        end
    endtask

    // The beat whose WID is deliberately wrong; -1 means none. A module-level knob rather
    // than another task argument, so the fifteen existing call sites stay readable.
    integer        wid_flip_at = -1;
    reg [31:0]     mem_before;
    reg [ID_W-1:0] last_bid;  reg [1:0] last_bresp;
    reg [ID_W-1:0] last_rid;  reg [1:0] last_rresp;
    reg [31:0]     rbeat [0:15];
    integer        rbeats, rlast_at;

    task axi_read(input [ID_W-1:0] tid, input [31:0] addr, input [3:0] len,
                  input [2:0] size, input [1:0] burst);
        integer n, done;
        begin
            rbeats = 0; rlast_at = -1; last_rresp = OKAY; last_rid = 0;
            @(negedge clk);
            arid = tid; araddr = addr; arlen = len; arsize = size; arburst = burst;
            arvalid = 1;
            #1;
            n = 0;
            while (!arready) begin
                @(negedge clk); #1;
                n = n + 1;
                if (n > TIMEOUT) begin fail("HANG on AR"); arvalid = 0; disable axi_read; end
            end
            @(negedge clk); arvalid = 0; #1;

            done = 0; n = 0;
            while (!done) begin
                if (rvalid) begin              // rready is held high
                    rbeat[rbeats] = rdata;
                    last_rid = rid;
                    if (rresp != OKAY) last_rresp = rresp;
                    if (rlast) rlast_at = rbeats;
                    rbeats = rbeats + 1;
                    n = 0;
                    if (rlast) done = 1;
                    else if (rbeats > 16) begin fail("more than 16 R beats"); done = 1; end
                end else begin
                    n = n + 1;
                    if (n > TIMEOUT) begin fail("HANG on R"); done = 1; end
                end
                if (!done) begin @(negedge clk); #1; end
            end
            @(negedge clk);
        end
    endtask

    // ------------------------------------------------------------------- the tests
    integer i, w0, r0;
    initial begin
        for (i = 0; i < 1024; i = i + 1) mem[i] = 32'hDEADBEEF;
        repeat (3) @(negedge clk);
        rst_n = 1;
        repeat (2) @(negedge clk);

        // 1. single beat, both directions, with a distinctive ID
        axi_write(12'hA5C, 32'h0000_0010, 4'd0, SZ4, INCR, 32'h1111_0000, 0, 12'hA5C);
        check(last_bresp === OKAY, "single write should be OKAY");
        check(last_bid === 12'hA5C, "BID must echo AWID");
        check(mem[4] === 32'h1111_0000, "single write reached the lite slave");

        axi_read(12'h3C5, 32'h0000_0010, 4'd0, SZ4, INCR);
        check(rbeats === 1, "single read is one beat");
        check(rlast_at === 0, "RLAST on the only beat");
        check(rbeat[0] === 32'h1111_0000, "single read data");
        check(last_rid === 12'h3C5, "RID must echo ARID");
        check(last_rresp === OKAY, "single read should be OKAY");

        // 2. the maximum AXI3 burst: 16 beats, INCR, both directions
        w0 = lite_writes;
        axi_write(12'h001, 32'h0000_0100, 4'd15, SZ4, INCR, 32'h2222_0000, 15, 12'h001);
        check(last_bresp === OKAY, "max burst write should be OKAY");
        check(lite_writes - w0 === 16, "a 16-beat burst is 16 lite writes, not 1");
        for (i = 0; i < 16; i = i + 1)
            check(mem[64 + i] === 32'h2222_0000 + i, "max burst write data/address");

        r0 = lite_reads;
        axi_read(12'h002, 32'h0000_0100, 4'd15, SZ4, INCR);
        check(rbeats === 16, "max burst read is 16 beats");
        check(rlast_at === 15, "RLAST only on the last beat");
        check(lite_reads - r0 === 16, "a 16-beat burst is 16 lite reads");
        for (i = 0; i < 16; i = i + 1)
            check(rbeat[i] === 32'h2222_0000 + i, "max burst read data");

        // 3. the same, under backpressure
        stall = 3;
        axi_write(12'h003, 32'h0000_0200, 4'd7, SZ4, INCR, 32'h3333_0000, 7, 12'h003);
        check(last_bresp === OKAY, "burst write under backpressure");
        axi_read(12'h004, 32'h0000_0200, 4'd7, SZ4, INCR);
        check(rbeats === 8, "burst read under backpressure is 8 beats");
        for (i = 0; i < 8; i = i + 1)
            check(rbeat[i] === 32'h3333_0000 + i, "burst read data under backpressure");
        stall = 0;

        // 4. FIXED burst: every beat hits the same address
        axi_write(12'h005, 32'h0000_0300, 4'd3, SZ4, FIXED, 32'h4444_0000, 3, 12'h005);
        check(last_bresp === OKAY, "FIXED write should be OKAY");
        check(mem[192] === 32'h4444_0003, "FIXED write does not advance the address");
        check(mem[193] === 32'hDEADBEEF, "FIXED write must not touch the next word");

        // 5. early WLAST — declared finished before the length says so
        w0 = lite_writes;
        axi_write(12'h006, 32'h0000_0400, 4'd3, SZ4, INCR, 32'h5555_0000, 1, 12'h006);
        check(last_bresp === SLVERR, "an early WLAST must answer SLVERR");
        check(last_bid === 12'h006, "BID echoes even on an error");
        check(lite_writes - w0 === 2, "an early WLAST stops after the beats it sent");

        // 6. late WLAST — never asserted at all
        axi_write(12'h007, 32'h0000_0500, 4'd1, SZ4, INCR, 32'h6666_0000, -1, 12'h007);
        check(last_bresp === SLVERR, "a missing WLAST must answer SLVERR, not hang");

        // 7. a WID that does not match the AWID. Answering SLVERR is not enough: the beat
        //    must never reach the register file. A refusal that arrives after the write has
        //    landed is a response that contradicts the fabric.
        w0 = lite_writes;
        mem_before = mem[384];
        axi_write(12'h101, 32'h0000_0600, 4'd0, SZ4, INCR, 32'h7777_0000, 0, 12'h102);
        check(last_bresp === SLVERR, "a mismatched WID must answer SLVERR");
        check(lite_writes - w0 === 0, "a mismatched WID must not reach the lite slave");
        check(mem[384] === mem_before, "a mismatched WID must not change memory");
        axi_write(12'h103, 32'h0000_0600, 4'd0, SZ4, INCR, 32'h7777_1111, 0, 12'h103);
        check(last_bresp === OKAY && mem[384] === 32'h7777_1111,
              "a well-formed write after a WID refusal still works");

        // 7b. a mismatch PART WAY THROUGH a burst: the beats before it stand, and the
        //     refusal latches so no later beat is written however well-formed its WID is.
        w0 = lite_writes;
        wid_flip_at = 1;
        axi_write(12'h104, 32'h0000_0900, 4'd3, SZ4, INCR, 32'hAAAA_0000, 3, 12'h104);
        wid_flip_at = -1;
        check(last_bresp === SLVERR, "a mid-burst WID mismatch answers SLVERR");
        check(lite_writes - w0 === 1, "only the beats before the mismatch reach the slave");
        check(mem[576] === 32'hAAAA_0000, "the beat before the mismatch stands");
        for (i = 1; i < 4; i = i + 1)
            check(mem[576 + i] === 32'hDEADBEEF,
                  "no beat from the mismatch onward is written");

        // 8. unsupported size — completed, refused, and the slave never sees it
        w0 = lite_writes; r0 = lite_reads;
        axi_write(12'h00A, 32'h0000_0700, 4'd1, SZ8, INCR, 32'h8888_0000, 1, 12'h00A);
        check(last_bresp === SLVERR, "an unsupported size must answer SLVERR");
        check(lite_writes - w0 === 0, "an unsupported write must not reach the slave");
        axi_read(12'h00B, 32'h0000_0700, 4'd1, SZ8, INCR);
        check(rbeats === 2, "an unsupported read still returns len+1 beats");
        check(rlast_at === 1, "an unsupported read still marks RLAST");
        check(last_rresp === SLVERR, "an unsupported read answers SLVERR");
        check(lite_reads - r0 === 0, "an unsupported read must not reach the slave");

        // 9. unsupported burst type
        axi_read(12'h00C, 32'h0000_0800, 4'd3, SZ4, WRAP);
        check(rbeats === 4, "a WRAP read still returns len+1 beats");
        check(last_rresp === SLVERR, "a WRAP read answers SLVERR");

        // 10. an error from the lite side propagates
        axi_write(12'h00D, {16'd0, ERR_ADDR}, 4'd0, SZ4, INCR, 32'h9999_0000, 0, 12'h00D);
        check(last_bresp === SLVERR, "a lite SLVERR must reach the master's B channel");
        axi_read(12'h00E, {16'd0, ERR_ADDR}, 4'd0, SZ4, INCR);
        check(last_rresp === SLVERR, "a lite SLVERR must reach the master's R channel");

        // 11. and after all of that the shim is still usable
        axi_write(12'h00F, 32'h0000_0020, 4'd0, SZ4, INCR, 32'hFEED_0001, 0, 12'h00F);
        axi_read(12'h010, 32'h0000_0020, 4'd0, SZ4, INCR);
        check(last_bresp === OKAY && rbeat[0] === 32'hFEED_0001,
              "the shim still works after every refusal");

        if (failures == 0) $display("tb_carrier_axi3: OK");
        else               $display("tb_carrier_axi3: %0d FAILURE(S)", failures);
        $finish;
    end

    // A global backstop: if a task's own budget is somehow escaped, the run still ends.
    initial begin
        #2_000_000;
        $display("FAIL: tb_carrier_axi3 global timeout");
        $finish;
    end
endmodule

`default_nettype wire
