// Two-pass transaction bench. It wires the REAL validator and the REAL CRC engine, not
// mocks of them: the contract is about those three agreeing, and a bench that stubbed two
// of them would be testing the FSM's opinion of itself.
//
// The cases that carry the contract:
//
//   * pass 2 loaded with different bytes that are still a VALID envelope — the payload may
//     differ freely, so only the CRC separates "the envelope pass 1 judged" from "an
//     envelope". This is the whole reason for two passes.
//   * envelopes out of order, in each pass.
//   * a write before pass 1 finished.
//   * configuration_valid low from the first write of pass 2 onwards.
//   * a readback mismatch anywhere, including in the flush frame.
//   * the readback words reaching the buffer, because the host must compute the payload
//     authority itself and cannot be handed a boolean.

`timescale 1ns/1ps
`default_nettype none

module tb_carrier_txn;
    localparam integer ENV_WORDS     = 536;
    localparam integer PAYLOAD_START = 23;
    localparam integer PAYLOAD_WORDS = 505;
    localparam integer TIMEOUT       = 8000;

    reg         clk = 1'b0;
    reg         rst_n = 1'b0;
    reg         begin_txn = 1'b0, validate_env = 1'b0, write_env = 1'b0;
    reg  [1:0]  env_index = 2'd0;

    wire        busy, fault, pass1_complete, configuration_valid;
    wire [3:0]  fault_code;
    wire [1:0]  expect_env;
    wire [11:0] txn_addr, buf_waddr;
    wire        buf_we;
    wire [31:0] buf_wdata;
    wire        val_start, val_busy, val_ok, val_fault;
    wire [11:0] val_addr;
    wire [3:0]  val_fault_code;
    wire [11:0] val_fault_word;
    wire        crc_clear, crc_valid;
    wire [31:0] crc_value;
    wire        icap_csib, icap_rdwrb;
    wire [31:0] icap_din;
    reg  [31:0] icap_dout;

    integer errors = 0, i;
    integer corrupt_at = -1;
    reg     valid_while_writing = 1'b0;

    reg [31:0] buffer [0:ENV_WORDS-1];
    reg [31:0] device [0:2][0:PAYLOAD_WORDS-1];
    reg [31:0] buf_data;

    always #5 clk = ~clk;

    // one shared read port, muxed exactly as the top level does it
    wire [11:0] buf_raddr = val_busy ? val_addr : txn_addr;
    always @(posedge clk) buf_data <= buffer[buf_raddr];
    always @(posedge clk) if (buf_we) buffer[buf_waddr] <= buf_wdata;

    carrier_envelope validator (
        .clk(clk), .rst_n(rst_n), .start(val_start), .env_index(env_index),
        .loaded_words(12'd536),
        .buf_addr(val_addr), .buf_data(buf_data),
        .busy(val_busy), .ok(val_ok), .fault(val_fault),
        .fault_code(val_fault_code), .fault_word(val_fault_word)
    );

    carrier_crc32 crc (
        .clk(clk), .rst_n(rst_n), .clear(crc_clear), .valid(crc_valid),
        .data(buf_data), .crc(crc_value)
    );

    carrier_txn #(.TIMEOUT(TIMEOUT)) dut (
        .clk(clk), .rst_n(rst_n),
        .begin_txn(begin_txn), .validate_env(validate_env), .write_env(write_env),
        .env_index(env_index),
        .busy(busy), .fault(fault), .fault_code(fault_code),
        .expect_env(expect_env), .pass1_complete(pass1_complete),
        .configuration_valid(configuration_valid),
        .buf_addr(txn_addr), .buf_data(buf_data),
        .buf_we(buf_we), .buf_waddr(buf_waddr), .buf_wdata(buf_wdata),
        .val_start(val_start), .val_busy(val_busy), .val_ok(val_ok), .val_fault(val_fault),
        .crc_clear(crc_clear), .crc_valid(crc_valid), .crc_value(crc_value),
        .icap_csib(icap_csib), .icap_rdwrb(icap_rdwrb),
        .icap_din(icap_din), .icap_dout(icap_dout)
    );

    // mock device: one payload store per envelope
    reg [1:0] dev_env = 2'd0;
    always @(posedge clk) begin
        if (!icap_csib && !icap_rdwrb && dut.pos_d >= PAYLOAD_START)
            device[dev_env][dut.pos_d - PAYLOAD_START] <= icap_din;
    end
    always @* begin
        icap_dout = device[dev_env][dut.pos_d];
        if (corrupt_at >= 0 && dut.pos_d == corrupt_at) icap_dout = ~device[dev_env][dut.pos_d];
    end

    always @(posedge clk)
        if (dut.state == 5 && configuration_valid) valid_while_writing <= 1'b1;

    task check(input [255:0] what, input integer got, input integer want);
        begin
            if (got !== want) begin
                $display("FAIL %0s: got %0d want %0d", what, got, want);
                errors = errors + 1;
            end
        end
    endtask

    localparam [31:0] FAR0 = 32'h00400A20, FAR1 = 32'h00400C1A, FAR2 = 32'h00400C20;

    task build(input [31:0] far, input [31:0] salt);
        begin
            for (i = 0; i < 8; i = i + 1) buffer[i] = 32'hFFFFFFFF;
            buffer[8]  = 32'hAA995566; buffer[9]  = 32'h20000000;
            buffer[10] = 32'h30008001; buffer[11] = 32'h00000007;
            buffer[12] = 32'h20000000; buffer[13] = 32'h20000000;
            buffer[14] = 32'h30018001; buffer[15] = 32'h13722093;
            buffer[16] = 32'h30008001; buffer[17] = 32'h00000001;
            buffer[18] = 32'h20000000; buffer[19] = 32'h30002001;
            buffer[20] = far;          buffer[21] = 32'h30004000;
            buffer[22] = 32'h400001F9;
            for (i = 0; i < PAYLOAD_WORDS; i = i + 1)
                buffer[PAYLOAD_START+i] = 32'hC0DE0000 + salt + i;
            buffer[528] = 32'h30000001; buffer[529] = 32'h00000000;
            buffer[530] = 32'h30008001; buffer[531] = 32'h0000000D;
            for (i = 0; i < 4; i = i + 1) buffer[532+i] = 32'h20000000;
        end
    endtask

    task pulse_validate(input [1:0] e);
        begin
            @(negedge clk); env_index = e; validate_env = 1'b1;
            @(negedge clk); validate_env = 1'b0;
            wait (!busy); @(negedge clk);
        end
    endtask

    task pulse_write(input [1:0] e);
        begin
            dev_env = e;
            @(negedge clk); env_index = e; write_env = 1'b1;
            @(negedge clk); write_env = 1'b0;
            wait (!busy); @(negedge clk);
        end
    endtask

    task start_txn;
        begin
            @(negedge clk); begin_txn = 1'b1;
            @(negedge clk); begin_txn = 1'b0;
            @(negedge clk);
        end
    endtask

    task full_pass1(input [31:0] salt);
        begin
            build(FAR0, salt); pulse_validate(2'd0);
            build(FAR1, salt); pulse_validate(2'd1);
            build(FAR2, salt); pulse_validate(2'd2);
        end
    endtask

    initial begin
        repeat (3) @(negedge clk); rst_n = 1'b1;
        check("clear out of reset", configuration_valid, 0);

        // ---------------------------------------------------------- 1. the happy path
        start_txn();
        full_pass1(32'd0);
        check("pass 1 complete", pass1_complete, 1);
        check("no fault in pass 1", fault, 0);
        check("still not confirmed after pass 1", configuration_valid, 0);

        build(FAR0, 32'd0); pulse_write(2'd0);
        check("no fault writing envelope 0", fault, 0);
        check("not confirmed part way", configuration_valid, 0);
        build(FAR1, 32'd0); pulse_write(2'd1);
        build(FAR2, 32'd0); pulse_write(2'd2);
        check("confirmed after the third envelope", configuration_valid, 1);
        check("never confirmed while writing", valid_while_writing, 0);

        // the readback words reached the buffer: the host must be able to hash them
        check("readback word 0 in the buffer", buffer[0], 32'hC0DE0000 + 0);
        check("readback last word in the buffer",
              buffer[PAYLOAD_WORDS-1], 32'hC0DE0000 + PAYLOAD_WORDS - 1);

        // ---- 1b. a write issued while a confirmation stands must drop it AT ONCE.
        // In the happy path configuration_valid was already 0 when pass 2 began, because
        // begin_txn cleared it — so nothing there can tell "cleared at the first write"
        // from "never set yet". After a completed transaction it can: expect_env is still
        // 2 and pass1_complete still 1, so re-issuing envelope 2's write is accepted, and
        // the confirmation must be gone before a single ICAP word goes out.
        check("confirmed before the repeat write", configuration_valid, 1);
        @(negedge clk); env_index = 2'd2; write_env = 1'b1;
        @(negedge clk); write_env = 1'b0;
        check("confirmation dropped the moment the write was accepted",
              configuration_valid, 0);
        wait (!busy); @(negedge clk);

        // ------------------------------------------- 2. pass 2 with DIFFERENT valid bytes
        // The payload may differ freely and the envelope is still structurally valid, so
        // only the CRC separates "the envelope pass 1 judged" from "an envelope".
        start_txn();
        full_pass1(32'd0);
        build(FAR0, 32'd7);            // a different, perfectly valid envelope 0
        pulse_write(2'd0);
        check("different bytes in pass 2 are refused", fault, 1);
        check("and it is a CRC fault", fault_code, 4'd3);
        check("not confirmed", configuration_valid, 0);

        // --------------------------------------------------------- 3. order violations
        start_txn();
        build(FAR1, 32'd0); pulse_validate(2'd1);     // pass 1 must start at 0
        check("pass 1 out of order refused", fault, 1);
        check("order fault", fault_code, 4'd1);

        start_txn();
        full_pass1(32'd0);
        build(FAR1, 32'd0); pulse_write(2'd1);        // pass 2 must start at 0
        check("pass 2 out of order refused", fault, 1);
        check("order fault", fault_code, 4'd1);

        // ------------------------------------------------ 4. a write before pass 1 ends
        start_txn();
        build(FAR0, 32'd0); pulse_validate(2'd0);
        build(FAR0, 32'd0); pulse_write(2'd0);
        check("write before pass 1 completed is refused", fault, 1);
        check("phase fault", fault_code, 4'd6);

        // ------------------------------------------------------ 5. a readback mismatch
        start_txn();
        full_pass1(32'd0);
        build(FAR0, 32'd0);
        corrupt_at = PAYLOAD_START + 40;
        pulse_write(2'd0);
        corrupt_at = -1;
        check("readback mismatch refused", fault, 1);
        check("readback fault", fault_code, 4'd4);
        check("not confirmed", configuration_valid, 0);

        // a mismatch in the FLUSH frame (the last of the five) is equally a refusal
        start_txn();
        full_pass1(32'd0);
        build(FAR0, 32'd0);
        corrupt_at = PAYLOAD_START + 4*101 + 7;
        pulse_write(2'd0);
        corrupt_at = -1;
        check("flush-frame readback mismatch refused", fault, 1);

        // --------------------------------------------------------------- 6. fail-closed
        start_txn();
        full_pass1(32'd0);
        build(FAR0, 32'd0); pulse_write(2'd0);
        build(FAR1, 32'd0); pulse_write(2'd1);
        // ... and now abandon it: no third envelope
        check("an unfinished pass 2 leaves it unconfirmed", configuration_valid, 0);

        @(negedge clk); rst_n = 1'b0; @(negedge clk); rst_n = 1'b1;
        repeat (5) @(negedge clk);
        check("reset clears confirmation", configuration_valid, 0);
        check("reset clears pass1_complete", pass1_complete, 0);

        if (errors == 0) $display("TXN TB: OK");
        else             $display("TXN TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule

`default_nettype wire
