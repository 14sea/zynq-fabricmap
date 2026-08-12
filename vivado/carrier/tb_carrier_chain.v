`timescale 1ns/1ps
`default_nettype none
//
// The whole chain, replaying what the board actually did.
// =======================================================
//
// On 2026-08-12 the no-op calibration reached its first pass-1 envelope and the BOARD
// REBOOTED inside the command: `mw.l <CTRL> 0x4 1; cp.l <dram> <stream> 0x218`. The reply
// carried a U-Boot banner. Everything before it worked -- staging, the staged readback, the
// PCAP_PR handover, begin_txn, and two STATUS reads of 0x00000080.
//
// A reboot is what an AXI error response looks like on this board: SLVERR reaches the A9 as
// a data abort, `panic()` runs, and with CONFIG_PANIC_HANG unset it resets the CPU. So the
// question is whether the stream window refused a write, and where.
//
// Two possibilities are open, and this bench is built to tell them apart:
//   1. the FIRST stream beat is refused -- a handshake race between `start_pass1` reaching
//      `carrier_stream` and `stream_open` being visible to `carrier_axil`;
//   2. some later beat is refused -- a validator, CRC, timeout or byte-count fault returns
//      the phase to idle, and every remaining beat of the `cp.l` then meets `stream_open` low.
//
// What this bench is not
// ----------------------
//
// It is not allowed to make the DUT pass. The RTL is replayed as published; if the failure
// does not reproduce, that is the result and it is recorded as such.
//
// The AXI3 master below is written independently: it drives AW, W, B, AR and R with its own
// explicit handshakes and its own burst arithmetic, and it does not borrow a single timing
// assumption from `carrier_axi3_lite`. A bench that models the DUT's assumptions cannot test
// them -- three separate defects in this project have now hidden behind exactly that.
//
// The envelope is REAL: `tb_envelope0.hex` is envelope 0 of the sealed no-op payload whose
// sha256 is 07fbca9e93f0066a7873607b9a79ad89521e37a8853ef92ec88256dac4fdb9c6, the same bytes
// the board was given.
//
// Per beat it records BRESP, the engine's phase, its fault and fault code, and the stream
// word index, so the first deviation names itself instead of being inferred.
//

module chain_dut #(
    parameter integer ENV_WORDS   = 536,
    parameter integer FRAME_WORDS = 101,
    parameter integer LUTS        = 8
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [11:0] s_awid,
    input  wire [31:0] s_awaddr,
    input  wire [3:0]  s_awlen,
    input  wire [2:0]  s_awsize,
    input  wire [1:0]  s_awburst,
    input  wire        s_awvalid,
    output wire        s_awready,
    input  wire [11:0] s_wid,
    input  wire [31:0] s_wdata,
    input  wire [3:0]  s_wstrb,
    input  wire        s_wlast,
    input  wire        s_wvalid,
    output wire        s_wready,
    output wire [11:0] s_bid,
    output wire [1:0]  s_bresp,
    output wire        s_bvalid,
    input  wire        s_bready,
    input  wire [11:0] s_arid,
    input  wire [31:0] s_araddr,
    input  wire [3:0]  s_arlen,
    input  wire [2:0]  s_arsize,
    input  wire [1:0]  s_arburst,
    input  wire        s_arvalid,
    output wire        s_arready,
    output wire [11:0] s_rid,
    output wire [31:0] s_rdata,
    output wire [1:0]  s_rresp,
    output wire        s_rlast,
    output wire        s_rvalid,
    input  wire        s_rready
);
    wire [15:0] m_awaddr, m_araddr;
    wire        m_awvalid, m_awready, m_wvalid, m_wready, m_bvalid, m_bready;
    wire        m_arvalid, m_arready, m_rvalid, m_rready;
    wire [31:0] m_wdata, m_rdata;
    wire [3:0]  m_wstrb;
    wire [1:0]  m_bresp, m_rresp;

    carrier_axi3_lite #(.ID_W(12), .ADDR_W(16)) axi3 (
        .clk(clk), .rst_n(rst_n),
        .s_awid(s_awid), .s_awaddr(s_awaddr), .s_awlen(s_awlen), .s_awsize(s_awsize),
        .s_awburst(s_awburst), .s_awvalid(s_awvalid), .s_awready(s_awready),
        .s_wid(s_wid), .s_wdata(s_wdata), .s_wstrb(s_wstrb), .s_wlast(s_wlast),
        .s_wvalid(s_wvalid), .s_wready(s_wready),
        .s_bid(s_bid), .s_bresp(s_bresp), .s_bvalid(s_bvalid), .s_bready(s_bready),
        .s_arid(s_arid), .s_araddr(s_araddr), .s_arlen(s_arlen), .s_arsize(s_arsize),
        .s_arburst(s_arburst), .s_arvalid(s_arvalid), .s_arready(s_arready),
        .s_rid(s_rid), .s_rdata(s_rdata), .s_rresp(s_rresp), .s_rlast(s_rlast),
        .s_rvalid(s_rvalid), .s_rready(s_rready),
        .m_awaddr(m_awaddr), .m_awvalid(m_awvalid), .m_awready(m_awready),
        .m_wdata(m_wdata), .m_wstrb(m_wstrb), .m_wvalid(m_wvalid), .m_wready(m_wready),
        .m_bresp(m_bresp), .m_bvalid(m_bvalid), .m_bready(m_bready),
        .m_araddr(m_araddr), .m_arvalid(m_arvalid), .m_arready(m_arready),
        .m_rdata(m_rdata), .m_rresp(m_rresp), .m_rvalid(m_rvalid), .m_rready(m_rready)
    );

    wire        ctrl_begin_txn, ctrl_pass1, ctrl_pass2, ctrl_arm, ctrl_mode_holdout,
                ctrl_rb_ack;
    wire [1:0]  ctrl_env_index;
    wire        txn_busy, txn_fault, configuration_valid, pass1_complete,
                recovery_required, rb_frame_ready, stream_open;
    wire [3:0]  txn_fault_code, rb_frames_ok;
    wire [1:0]  expect_env;
    wire [2:0]  env_committed;
    wire        word_valid, word_ready;
    wire [31:0] word_data, rb_rdata;
    wire [6:0]  rb_raddr;

    carrier_axil #(.FRAME_WORDS(FRAME_WORDS), .LUTS(LUTS)) axil (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(m_awaddr), .s_awvalid(m_awvalid), .s_awready(m_awready),
        .s_wdata(m_wdata), .s_wstrb(m_wstrb), .s_wvalid(m_wvalid), .s_wready(m_wready),
        .s_bresp(m_bresp), .s_bvalid(m_bvalid), .s_bready(m_bready),
        .s_araddr(m_araddr), .s_arvalid(m_arvalid), .s_arready(m_arready),
        .s_rdata(m_rdata), .s_rresp(m_rresp), .s_rvalid(m_rvalid), .s_rready(m_rready),
        .word_valid(word_valid), .word_data(word_data), .word_ready(word_ready),
        .stream_open(stream_open),
        .rb_raddr(rb_raddr), .rb_rdata(rb_rdata),
        .ctrl_begin_txn(ctrl_begin_txn),
        .ctrl_pass1(ctrl_pass1), .ctrl_pass2(ctrl_pass2),
        .ctrl_env_index(ctrl_env_index),
        .ctrl_arm(ctrl_arm), .ctrl_mode_holdout(ctrl_mode_holdout),
        .ctrl_rb_ack(ctrl_rb_ack),
        .txn_busy(txn_busy), .txn_fault(txn_fault), .txn_fault_code(txn_fault_code),
        .pass1_complete(pass1_complete), .recovery_required(recovery_required),
        .expect_env(expect_env), .env_committed(env_committed),
        .rb_frame_ready(rb_frame_ready), .rb_frames_ok(rb_frames_ok),
        .configuration_valid(configuration_valid),
        .scorer_busy(1'b0), .scorer_done(1'b0), .scorer_armed(1'b0),
        .score_flat({LUTS*8{1'b0}})
    );

    // No ICAPE2 here: it is a device primitive and pass 1 never asserts CSIB anyway, so the
    // whole of what this bench replays runs with the ICAP idle.
    wire        icap_csib, icap_rdwrb;
    wire [31:0] icap_din;

    carrier_stream #(.ENV_WORDS(ENV_WORDS), .FRAME_WORDS(FRAME_WORDS)) stream (
        .clk(clk), .rst_n(rst_n),
        .begin_txn(ctrl_begin_txn),
        .start_pass1(ctrl_pass1), .start_pass2(ctrl_pass2),
        .env_index(ctrl_env_index),
        .word_valid(word_valid), .word_data(word_data), .word_ready(word_ready),
        .stream_open(stream_open),
        .busy(txn_busy), .fault(txn_fault), .fault_code(txn_fault_code),
        .expect_env(expect_env), .pass1_complete(pass1_complete),
        .configuration_valid(configuration_valid),
        .recovery_required(recovery_required), .env_committed(env_committed),
        .host_raddr(rb_raddr), .host_rdata(rb_rdata),
        .rb_frame_ready(rb_frame_ready), .rb_ack(ctrl_rb_ack),
        .rb_frames_ok(rb_frames_ok),
        .icap_csib(icap_csib), .icap_rdwrb(icap_rdwrb),
        .icap_din(icap_din), .icap_dout(32'd0)
    );
endmodule


module tb_carrier_chain;

    localparam integer ENV_WORDS = 536;
    localparam [15:0]  A_STREAM  = 16'h0000;
    localparam [15:0]  A_CTRL    = 16'h2000;
    localparam [15:0]  A_STATUS  = 16'h2004;
    localparam [1:0]   BURST_INCR = 2'b01;
    localparam [2:0]   SIZE_4B    = 3'b010;
    localparam [1:0]   RESP_OKAY  = 2'b00;

    reg clk = 1'b0, rst_n = 1'b0;
    always #5 clk = ~clk;

    reg  [11:0] awid = 12'd0;   reg [31:0] awaddr = 32'd0;  reg [3:0] awlen = 4'd0;
    reg  [2:0]  awsize = SIZE_4B; reg [1:0] awburst = BURST_INCR; reg awvalid = 1'b0;
    wire        awready;
    reg  [11:0] wid = 12'd0;    reg [31:0] wdata = 32'd0;   reg [3:0] wstrb = 4'hF;
    reg         wlast = 1'b0,   wvalid = 1'b0;              wire wready;
    wire [11:0] bid;            wire [1:0] bresp;           wire bvalid;  reg bready = 1'b0;
    reg  [11:0] arid = 12'd0;   reg [31:0] araddr = 32'd0;  reg [3:0] arlen = 4'd0;
    reg  [2:0]  arsize = SIZE_4B; reg [1:0] arburst = BURST_INCR; reg arvalid = 1'b0;
    wire        arready;
    wire [11:0] rid;            wire [31:0] rdata;          wire [1:0] rresp;
    wire        rlast, rvalid;  reg rready = 1'b0;

    chain_dut dut (
        .clk(clk), .rst_n(rst_n),
        .s_awid(awid), .s_awaddr(awaddr), .s_awlen(awlen), .s_awsize(awsize),
        .s_awburst(awburst), .s_awvalid(awvalid), .s_awready(awready),
        .s_wid(wid), .s_wdata(wdata), .s_wstrb(wstrb), .s_wlast(wlast),
        .s_wvalid(wvalid), .s_wready(wready),
        .s_bid(bid), .s_bresp(bresp), .s_bvalid(bvalid), .s_bready(bready),
        .s_arid(arid), .s_araddr(araddr), .s_arlen(arlen), .s_arsize(arsize),
        .s_arburst(arburst), .s_arvalid(arvalid), .s_arready(arready),
        .s_rid(rid), .s_rdata(rdata), .s_rresp(rresp), .s_rlast(rlast),
        .s_rvalid(rvalid), .s_rready(rready)
    );

    // The real envelope the board was given.
    reg [31:0] envelope [0:ENV_WORDS-1];

    integer beats_sent, first_bad_beat, errors, scenario_faults;
    reg [1:0] first_bad_resp;
    reg [3:0] first_bad_phase, first_bad_fault_code;
    reg       first_bad_fault;
    reg [9:0] first_bad_pos;

    // ---------------------------------------------------------------- the AXI3 master
    //
    // Written from the AXI3 spec, not from the DUT: AW and W are independent channels, W
    // beats carry WID and the last one carries WLAST, and B is a separate handshake that
    // this master accepts only when it chooses to. `#1` at every sample point, because a
    // combinational READY cannot be sampled in the same delta as the drive that produces it
    // -- a trap this project has paid for twice.

    task automatic aw_beat(input [31:0] addr, input [3:0] len);
        begin
            @(posedge clk); #1;
            awaddr = addr; awlen = len; awvalid = 1'b1;
            awsize = SIZE_4B; awburst = BURST_INCR;
            while (!awready) @(posedge clk);
            @(posedge clk); #1;
            awvalid = 1'b0;
        end
    endtask

    task automatic w_beat(input [31:0] data, input last, input integer stall);
        integer s;
        begin
            for (s = 0; s < stall; s = s + 1) @(posedge clk);
            @(posedge clk); #1;
            wdata = data; wlast = last; wvalid = 1'b1; wstrb = 4'hF;
            while (!wready) @(posedge clk);
            @(posedge clk); #1;
            wvalid = 1'b0; wlast = 1'b0;
        end
    endtask

    task automatic b_beat(input integer stall, output [1:0] resp);
        integer s;
        begin
            for (s = 0; s < stall; s = s + 1) @(posedge clk);
            @(posedge clk); #1;
            bready = 1'b1;
            while (!bvalid) @(posedge clk);
            resp = bresp;
            @(posedge clk); #1;
            bready = 1'b0;
        end
    endtask

    task automatic read_word(input [31:0] addr, output [31:0] data, output [1:0] resp);
        begin
            @(posedge clk); #1;
            araddr = addr; arlen = 4'd0; arvalid = 1'b1;
            arsize = SIZE_4B; arburst = BURST_INCR;
            while (!arready) @(posedge clk);
            @(posedge clk); #1;
            arvalid = 1'b0; rready = 1'b1;
            while (!rvalid) @(posedge clk);
            data = rdata; resp = rresp;
            @(posedge clk); #1;
            rready = 1'b0;
        end
    endtask

    task automatic write_word(input [31:0] addr, input [31:0] data, output [1:0] resp);
        begin
            aw_beat(addr, 4'd0);
            w_beat(data, 1'b1, 0);
            b_beat(0, resp);
        end
    endtask

    // ------------------------------------------------------- per-beat observation
    task automatic note_beat(input integer index, input [1:0] resp);
        begin
            if (resp !== RESP_OKAY && first_bad_beat < 0) begin
                first_bad_beat       = index;
                first_bad_resp       = resp;
                first_bad_phase      = dut.stream.phase;
                first_bad_fault      = dut.stream.fault;
                first_bad_fault_code = dut.stream.fault_code;
                first_bad_pos        = dut.stream.pos;
                $display("    FIRST DEVIATION at stream word %0d: BRESP=%b phase=%0d fault=%b code=%0d pos=%0d stream_open=%b",
                         index, resp, dut.stream.phase, dut.stream.fault,
                         dut.stream.fault_code, dut.stream.pos, dut.stream.stream_open);
            end
            if (dut.stream.fault && scenario_faults == 0) begin
                scenario_faults = 1;
                $display("    engine FAULT first seen at stream word %0d: code=%0d pos=%0d",
                         index, dut.stream.fault_code, dut.stream.pos);
            end
        end
    endtask

    task automatic reset_dut;
        begin
            rst_n = 1'b0;
            repeat (8) @(posedge clk);
            rst_n = 1'b1;
            repeat (4) @(posedge clk);
        end
    endtask

    // begin_txn, then STATUS, then pass1 -- exactly the order the calibration used.
    task automatic begin_and_arm_pass1(output [31:0] status_before);
        reg [1:0] resp;
        begin
            write_word({16'd0, A_CTRL}, 32'h0000_0002, resp);   // CTRL_BEGIN_TXN
            if (resp !== RESP_OKAY) begin
                $display("    begin_txn answered BRESP=%b", resp); errors = errors + 1;
            end
            read_word({16'd0, A_STATUS}, status_before, resp);
            write_word({16'd0, A_CTRL}, 32'h0000_0004, resp);   // CTRL_PASS1, env 0
            if (resp !== RESP_OKAY) begin
                $display("    start_pass1 answered BRESP=%b", resp); errors = errors + 1;
            end
        end
    endtask

    // ------------------------------------------------------------------- scenarios
    task automatic scenario_single_beats(input integer stall_w, input integer stall_b,
                                         input [511:0] name);
        reg [31:0] status_before;
        reg [1:0]  resp;
        integer    i;
        begin
            $display("\n--- %0s", name);
            reset_dut;
            first_bad_beat = -1; scenario_faults = 0;
            begin_and_arm_pass1(status_before);
            $display("    STATUS after begin_txn = 0x%08x", status_before);
            for (i = 0; i < ENV_WORDS; i = i + 1) begin
                aw_beat({16'd0, A_STREAM}, 4'd0);
                w_beat(envelope[i], 1'b1, stall_w);
                b_beat(stall_b, resp);
                note_beat(i, resp);
                beats_sent = beats_sent + 1;
            end
            report(name);
        end
    endtask

    task automatic scenario_bursts(input integer beats_per_burst, input [511:0] name);
        reg [31:0] status_before;
        reg [1:0]  resp;
        integer    i, j;
        begin
            $display("\n--- %0s", name);
            reset_dut;
            first_bad_beat = -1; scenario_faults = 0;
            begin_and_arm_pass1(status_before);
            $display("    STATUS after begin_txn = 0x%08x", status_before);
            i = 0;
            while (i < ENV_WORDS) begin
                aw_beat({16'd0, A_STREAM}, beats_per_burst[3:0] - 4'd1);
                for (j = 0; j < beats_per_burst; j = j + 1)
                    w_beat(envelope[i + j], (j == beats_per_burst - 1), 0);
                b_beat(0, resp);
                // AXI3 gives ONE BRESP per burst, not per beat, so this attributes the
                // burst's response to its first beat and says so rather than pretending to
                // a resolution the protocol does not offer.
                note_beat(i, resp);
                i = i + beats_per_burst;
            end
            report(name);
        end
    endtask

    task automatic report(input [511:0] name);
        begin
            if (first_bad_beat < 0)
                $display("    NO DEVIATION: every beat answered OKAY, phase=%0d fault=%b pos=%0d env_committed=%0d",
                         dut.stream.phase, dut.stream.fault, dut.stream.pos,
                         dut.stream.env_committed);
            else begin
                $display("    DEVIATION SUMMARY: first bad beat %0d, BRESP=%b, phase=%0d, fault=%b code=%0d, pos=%0d",
                         first_bad_beat, first_bad_resp, first_bad_phase,
                         first_bad_fault, first_bad_fault_code, first_bad_pos);
                if (first_bad_beat == 0)
                    $display("    READING 1: the FIRST beat was refused -- look at start_pass1 -> stream_open timing across the modules.");
                else
                    $display("    READING 2: %0d beats were accepted first -- look for the engine's first fault (validator, CRC, timeout, byte count).",
                             first_bad_beat);
            end
        end
    endtask

    initial begin
        $readmemh("tb_envelope0.hex", envelope);
        beats_sent = 0; errors = 0;

        scenario_single_beats(0, 0, "A: single beats, no gap");
        scenario_single_beats(2, 0, "B: single beats, W stalled 2 cycles");
        scenario_single_beats(0, 3, "C: single beats, B accepted late (backpressure)");
        scenario_bursts(16, "D: 16-beat INCR bursts");

        $display("\n=== chain replay complete: %0d beats driven, %0d control errors",
                 beats_sent, errors);
        if (errors == 0)
            $display("READING 3 applies only if every scenario said NO DEVIATION: the simulation did not reproduce the board's refusal, and the next step is to compare the AXI transaction shape U-Boot's cp.l actually emits.");
        $finish;
    end

    initial begin
        #20_000_000;
        $display("TIMEOUT: the bench itself hung");
        $finish;
    end
endmodule

`default_nettype wire
