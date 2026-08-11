// carrier_axil bench.
//
// The register file is the surface software touches, so the properties worth asserting are
// the ones a plausible edit would break silently:
//   - no address writes `configuration_valid` (or the other verdict bits). It is an input;
//     the bench proves the OUTWARD claim by writing every writable address with all ones
//     and every other address too, and checking the status bits still mirror the inputs.
//   - a stream write outside a pass is an ERROR, not a hang. An AXI-Lite write that never
//     completes wedges the PS, which on this board means a power cycle.
//   - a stream write inside a pass is one word, once, and it does not complete until the
//     engine takes it.
//   - the readback window is readable and NOT writable.

`timescale 1ns/1ps
`default_nettype none

module tb_carrier_axil;
    localparam integer FRAME_WORDS = 101;
    localparam integer LUTS = 6;

    reg clk = 0; always #5 clk = ~clk;
    reg rst_n = 0;

    reg  [15:0] awaddr = 0, araddr = 0;
    reg         awvalid = 0, wvalid = 0, bready = 1, arvalid = 0, rready = 1;
    reg  [31:0] wdata = 0;
    wire        awready, wready, bvalid, arready, rvalid;
    wire [1:0]  bresp, rresp;
    wire [31:0] rdata;

    wire        word_valid;
    wire [31:0] word_data;
    reg         word_ready = 1, stream_open = 0;
    // stands in for the engine's staging memory: an ASYNCHRONOUS read at rb_raddr
    wire [6:0]  rb_raddr;
    reg  [31:0] stage_model [0:FRAME_WORDS-1];
    wire [31:0] rb_rdata = stage_model[rb_raddr];

    wire        ctrl_begin_txn, ctrl_pass1, ctrl_pass2, ctrl_arm, ctrl_mode_holdout,
                ctrl_rb_ack;
    wire [1:0]  ctrl_env_index;

    reg         txn_busy = 0, txn_fault = 0, pass1_complete = 0, recovery_required = 1,
                rb_frame_ready = 0, configuration_valid = 0,
                scorer_busy = 0, scorer_done = 0, scorer_armed = 0;
    reg  [3:0]  txn_fault_code = 0, rb_frames_ok = 0;
    reg  [1:0]  expect_env = 0;
    reg  [2:0]  env_committed = 0;
    reg  [LUTS*8-1:0] score_flat = 0;

    integer errors = 0;
    integer word_count = 0;
    reg [31:0] last_word = 0;
    always @(posedge clk) if (word_valid && word_ready) begin
        word_count <= word_count + 1;
        last_word  <= word_data;
    end

    carrier_axil #(.FRAME_WORDS(FRAME_WORDS), .LUTS(LUTS)) dut (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(awaddr), .s_awvalid(awvalid), .s_awready(awready),
        .s_wdata(wdata), .s_wstrb(4'hF), .s_wvalid(wvalid), .s_wready(wready),
        .s_bresp(bresp), .s_bvalid(bvalid), .s_bready(bready),
        .s_araddr(araddr), .s_arvalid(arvalid), .s_arready(arready),
        .s_rdata(rdata), .s_rresp(rresp), .s_rvalid(rvalid), .s_rready(rready),
        .word_valid(word_valid), .word_data(word_data), .word_ready(word_ready),
        .stream_open(stream_open),
        .rb_raddr(rb_raddr), .rb_rdata(rb_rdata),
        .ctrl_begin_txn(ctrl_begin_txn), .ctrl_pass1(ctrl_pass1), .ctrl_pass2(ctrl_pass2),
        .ctrl_env_index(ctrl_env_index), .ctrl_arm(ctrl_arm),
        .ctrl_mode_holdout(ctrl_mode_holdout), .ctrl_rb_ack(ctrl_rb_ack),
        .txn_busy(txn_busy), .txn_fault(txn_fault), .txn_fault_code(txn_fault_code),
        .pass1_complete(pass1_complete), .recovery_required(recovery_required),
        .expect_env(expect_env), .env_committed(env_committed),
        .rb_frame_ready(rb_frame_ready), .rb_frames_ok(rb_frames_ok),
        .configuration_valid(configuration_valid),
        .scorer_busy(scorer_busy), .scorer_done(scorer_done), .scorer_armed(scorer_armed),
        .score_flat(score_flat)
    );

    reg [1:0] wr_resp;
    task axi_write(input [15:0] a, input [31:0] d);
        begin
            @(negedge clk); awaddr = a; wdata = d; awvalid = 1; wvalid = 1;
            @(posedge clk);
            while (!(awready && wready)) @(posedge clk);
            @(negedge clk); awvalid = 0; wvalid = 0;
            while (!bvalid) @(posedge clk);
            wr_resp = bresp;
            @(negedge clk);
        end
    endtask

    reg [31:0] rd_data;
    reg [1:0]  rd_resp;
    task axi_read(input [15:0] a);
        begin
            @(negedge clk); araddr = a; arvalid = 1;
            @(posedge clk);
            while (!arready) @(posedge clk);
            @(negedge clk); arvalid = 0;
            while (!rvalid) @(posedge clk);
            rd_data = rdata; rd_resp = rresp;
            @(negedge clk);
        end
    endtask

    task check(input [255:0] what, input integer got, input integer want);
        begin
            if (got !== want) begin
                $display("FAIL %0s: got %0d want %0d", what, got, want);
                errors = errors + 1;
            end
        end
    endtask

    integer i;
    initial begin
        repeat (3) @(negedge clk); rst_n = 1;

        // ---- 1. a stream write with no pass open is an error, and consumes no word
        stream_open = 0;
        axi_write(16'h0000, 32'hDEADBEEF);
        check("stream write outside a pass: SLVERR", wr_resp, 2'b10);
        check("no word consumed outside a pass", word_count, 0);

        // ---- 2. inside a pass it is one word, once
        stream_open = 1;
        axi_write(16'h0000, 32'hC0DE0001);
        check("stream write inside a pass: OKAY", wr_resp, 2'b00);
        check("exactly one word consumed", word_count, 1);
        check("and it is the word written", last_word, 32'hC0DE0001);

        // ---- 3. backpressure: the write does not complete until the engine takes it
        word_ready = 0;
        @(negedge clk); awaddr = 16'h0000; wdata = 32'hC0DE0002; awvalid = 1; wvalid = 1;
        repeat (8) @(posedge clk);
        check("stalled: no completion", awready, 0);
        check("stalled: valid is held for the engine", word_valid, 1);
        check("stalled: still one word", word_count, 1);
        @(negedge clk); word_ready = 1;
        @(posedge clk);
        while (!(awready && wready)) @(posedge clk);
        @(negedge clk); awvalid = 0; wvalid = 0;
        while (!bvalid) @(posedge clk);
        @(negedge clk);
        check("released: two words", word_count, 2);
        check("released: the second word", last_word, 32'hC0DE0002);
        stream_open = 0;

        // ---- 4. no address writes the verdict bits
        configuration_valid = 0; recovery_required = 1; env_committed = 3'b000;
        rb_frames_ok = 4'd0; pass1_complete = 0;
        for (i = 0; i < 16; i = i + 1) axi_write(16'h2000 + i*4, 32'hFFFFFFFF);
        axi_read(16'h2004);
        check("configuration_valid unwritable", rd_data[2], 0);
        check("recovery_required unwritable", rd_data[7], 1);
        check("pass1_complete unwritable", rd_data[6], 0);
        check("env_committed unwritable", rd_data[13:11], 0);
        check("rb_frames_ok unwritable", rd_data[17:14], 0);
        // and they do mirror their inputs, so the check above is not passing vacuously
        configuration_valid = 1; env_committed = 3'b101; rb_frames_ok = 4'd9;
        axi_read(16'h2004);
        check("configuration_valid mirrors its input", rd_data[2], 1);
        check("env_committed mirrors its input", rd_data[13:11], 3'b101);
        check("rb_frames_ok mirrors its input", rd_data[17:14], 4'd9);

        // ---- 5. only CTRL is writable among the registers
        axi_write(16'h2004, 32'h1);
        check("STATUS is not writable", wr_resp, 2'b10);
        axi_write(16'h2008, 32'h1);
        check("FAULT is not writable", wr_resp, 2'b10);

        // ---- 6. CTRL pulses are one cycle and carry their fields
        fork
            axi_write(16'h2000, 32'h000001D8);   // pass2, env=1, arm, holdout, rb_ack
            begin : count_pulses
                integer n1, n2;
                n1 = 0; n2 = 0;
                repeat (12) begin
                    @(posedge clk);
                    if (ctrl_pass2) n1 = n1 + 1;
                    if (ctrl_arm)   n2 = n2 + 1;
                end
                check("start_pass2 pulses exactly once", n1, 1);
                check("arm pulses exactly once", n2, 1);
            end
        join
        check("env_index latched", ctrl_env_index, 1);
        check("mode_holdout is a level", ctrl_mode_holdout, 1);

        // ---- 7. the readback window: readable, not writable
        for (i = 0; i < FRAME_WORDS; i = i + 1) stage_model[i] = 32'hAB000000 | i;
        axi_read(16'h1000);
        check("readback word 0", rd_data, 32'hAB000000);
        axi_read(16'h1000 + 100*4);
        check("readback word 100", rd_data, 32'hAB000064);
        axi_write(16'h1000, 32'hFFFFFFFF);
        check("readback window is read-only", wr_resp, 2'b10);
        axi_read(16'h0000);
        check("the stream window is write-only", rd_resp, 2'b10);
        axi_read(16'h2100);
        check("an unmapped register reads SLVERR", rd_resp, 2'b10);

        if (errors == 0) $display("AXIL TB: OK");
        else             $display("AXIL TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule

`default_nettype wire
