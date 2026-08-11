// Stream-engine bench, aimed at the boundary a per-frame design invites you to get wrong:
// pass 1 can compute five perfectly good frame CRCs for an envelope and then fail its
// trailer, its length or its order — and those five must not survive as authority.
//
// The case that matters is `envelope 0 fails its trailer, then pass 2 offers envelope 0`:
// with per-frame commitment the CRCs are already stored and pass 2 sails through; with
// commitment at the end of a wholly good envelope it is refused as uncommitted.

`timescale 1ns/1ps
`default_nettype none

module tb_carrier_stream;
    localparam integer ENV_WORDS   = 536;
    localparam integer FRAME_WORDS = 101;
    localparam integer PREAMBLE    = 23;

    reg         clk = 1'b0, rst_n = 1'b0;
    reg         begin_txn = 1'b0, start_pass1 = 1'b0, start_pass2 = 1'b0;
    reg  [1:0]  env_index = 2'd0;
    reg         word_valid = 1'b0;
    reg  [31:0] word_data = 32'd0;
    wire        word_ready;
    wire        busy, fault, pass1_complete, configuration_valid, recovery_required;
    wire [3:0]  fault_code;
    wire [1:0]  expect_env;
    wire [2:0]  env_committed;
    wire        rb_frame_ready;
    reg  [6:0]  host_raddr = 7'd0;
    wire [31:0] host_rdata;
    wire        icap_csib, icap_rdwrb;
    wire [31:0] icap_din;
    reg  [31:0] icap_dout = 32'd0;
    reg         rb_ack = 1'b0;
    wire [3:0]  rb_frames_ok;
    // device model: what the fabric returns, per (envelope, frame, word)
    reg [31:0] device [0:2][0:4][0:FRAME_WORDS-1];
    integer corrupt_env = -1, corrupt_frame = -1, corrupt_word = -1;

    integer errors = 0, i;
    reg [31:0] env_words [0:ENV_WORDS-1];

    always #5 clk = ~clk;

    carrier_stream dut (
        .clk(clk), .rst_n(rst_n),
        .begin_txn(begin_txn), .start_pass1(start_pass1), .start_pass2(start_pass2),
        .env_index(env_index),
        .word_valid(word_valid), .word_data(word_data), .word_ready(word_ready),
        .busy(busy), .fault(fault), .fault_code(fault_code), .expect_env(expect_env),
        .pass1_complete(pass1_complete), .configuration_valid(configuration_valid),
        .recovery_required(recovery_required), .env_committed(env_committed),
        .host_raddr(host_raddr), .host_rdata(host_rdata),
        .rb_frame_ready(rb_frame_ready), .rb_ack(rb_ack), .rb_frames_ok(rb_frames_ok),
        .icap_csib(icap_csib), .icap_rdwrb(icap_rdwrb), .icap_din(icap_din),
        .icap_dout(icap_dout)
    );

    // the device returns what pass 2 wrote, unless a corruption is injected
    always @* begin
        icap_dout = device[dut.env][dut.rb_frame][dut.frame_word];
        if (corrupt_env == dut.env && corrupt_frame == dut.rb_frame &&
            corrupt_word == dut.frame_word)
            icap_dout = ~device[dut.env][dut.rb_frame][dut.frame_word];
    end

    // capture what pass 2 hands to ICAP during the EMIT phase, so the readback has
    // something faithful to return. Frames reach ICAP only from there — the point of the
    // staging is that nothing is handed over until its CRC has matched.
    //
    // The capture keeps its OWN pointer. `icap_din` is a registered output, so by the time
    // a word is on the wire `emit_word` has already advanced, and indexing the device by
    // it stores every word one place late — which reads back as a CRC mismatch and looks
    // exactly like a real readback failure.
    //
    // For the same reason the window is P_EMIT delayed by one cycle, not P_EMIT itself:
    // the 101st word reaches the wire in the first cycle AFTER the engine has left P_EMIT
    // (that is also when a real ICAPE2 latches it, CSIB still low). Gating on the phase
    // directly stored only 100 words and left word 100 as x — which the CRC then reported
    // as a readback mismatch, i.e. a bench defect wearing a device failure's clothes.
    integer cap_ptr = 0;
    reg     emit_d = 1'b0;
    always @(posedge clk) emit_d <= (dut.phase == 3'd5);
    always @(posedge clk) begin
        if (emit_d && !icap_csib && !icap_rdwrb) begin
            device[dut.env][dut.frame_idx - 3'd1][cap_ptr] <= icap_din;
            cap_ptr <= (cap_ptr == FRAME_WORDS-1) ? 0 : cap_ptr + 1;
        end else if (!emit_d) begin
            cap_ptr <= 0;
        end
    end

    // the host taking each readback frame
    always @(posedge clk) rb_ack <= rb_frame_ready && !rb_ack;

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
            for (i = 0; i < 8; i = i + 1) env_words[i] = 32'hFFFFFFFF;
            env_words[8]  = 32'hAA995566; env_words[9]  = 32'h20000000;
            env_words[10] = 32'h30008001; env_words[11] = 32'h00000007;
            env_words[12] = 32'h20000000; env_words[13] = 32'h20000000;
            env_words[14] = 32'h30018001; env_words[15] = 32'h13722093;
            env_words[16] = 32'h30008001; env_words[17] = 32'h00000001;
            env_words[18] = 32'h20000000; env_words[19] = 32'h30002001;
            env_words[20] = far;          env_words[21] = 32'h30004000;
            env_words[22] = 32'h400001F9;
            for (i = 0; i < 505; i = i + 1)
                env_words[PREAMBLE+i] = 32'hC0DE0000 + salt + i;
            env_words[528] = 32'h30000001; env_words[529] = 32'h00000000;
            env_words[530] = 32'h30008001; env_words[531] = 32'h0000000D;
            for (i = 0; i < 4; i = i + 1) env_words[532+i] = 32'h20000000;
        end
    endtask

    // stream words [from, upto) of the resident envelope, stopping early on a fault.
    // The range matters: the engine has a position of its own, so a task that always
    // restarted at 0 would re-send word 0 where word 535 was expected — which is how the
    // first version of this bench manufactured a control fault of its own making.
    task stream(input integer from, input integer upto);
        integer k;
        begin
            k = from;
            while (k < upto && !fault) begin
                @(negedge clk);
                word_data  = env_words[k];
                word_valid = 1'b1;
                @(posedge clk);
                while (!word_ready && !fault) @(posedge clk);
                @(negedge clk);
                word_valid = 1'b0;
                k = k + 1;
            end
            @(negedge clk);
        end
    endtask

    task run_pass1(input [1:0] e);
        begin
            @(negedge clk); env_index = e; start_pass1 = 1'b1;
            @(negedge clk); start_pass1 = 1'b0;
            stream(0, ENV_WORDS);
            wait (!busy); @(negedge clk);
        end
    endtask

    task run_pass2(input [1:0] e);
        begin
            @(negedge clk); env_index = e; start_pass2 = 1'b1;
            @(negedge clk); start_pass2 = 1'b0;
            stream(0, ENV_WORDS);
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

    initial begin
        repeat (3) @(negedge clk); rst_n = 1'b1;
        check("recovery required out of reset", recovery_required, 1);
        check("nothing committed", env_committed, 0);

        // ---- 1. a wholly good envelope commits its five CRCs, once, at the end
        start_txn();
        build(FAR0, 32'd0);
        @(negedge clk); env_index = 2'd0; start_pass1 = 1'b1;
        @(negedge clk); start_pass1 = 1'b0;
        stream(0, ENV_WORDS - 1);              // everything but the last trailer word
        check("nothing committed part way through", env_committed, 0);
        stream(ENV_WORDS - 1, ENV_WORDS);      // and now the last word
        wait (!busy); @(negedge clk);
        check("committed after a whole good envelope", env_committed, 3'b001);
        check("no fault", fault, 0);

        // ---- 2. THE BOUNDARY: five good frame CRCs, then a bad trailer
        start_txn();
        check("commit bits cleared by begin_txn", env_committed, 0);
        build(FAR0, 32'd0);
        env_words[531] = 32'h20000000;         // DESYNC replaced by a NOOP
        @(negedge clk); env_index = 2'd0; start_pass1 = 1'b1;
        @(negedge clk); start_pass1 = 1'b0;
        stream(0, ENV_WORDS);
        wait (!busy); @(negedge clk);
        check("a bad trailer refuses the envelope", fault, 1);
        check("control fault", fault_code, 4'd2);
        check("and NOTHING is committed", env_committed, 0);

        // pass 2 for that envelope must now be refused as uncommitted, not accepted on
        // the strength of five CRCs that were computed before the trailer failed
        start_txn();
        build(FAR0, 32'd0);
        @(negedge clk); env_index = 2'd0; start_pass2 = 1'b1;
        @(negedge clk); start_pass2 = 1'b0;
        @(negedge clk);
        check("pass 2 on an uncommitted envelope is refused", fault, 1);

        // ---- 3. a bad FAR mid-envelope also commits nothing
        start_txn();
        build(32'h00400A80, 32'd0);            // envelope 0 addressing its flush frame
        @(negedge clk); env_index = 2'd0; start_pass1 = 1'b1;
        @(negedge clk); start_pass1 = 1'b0;
        stream(0, ENV_WORDS);
        wait (!busy); @(negedge clk);
        check("a bad FAR refuses", fault, 1);
        check("FAR fault", fault_code, 4'd3);
        check("nothing committed", env_committed, 0);

        // ---- 4. a fault clears commits already earned in this transaction
        start_txn();
        build(FAR0, 32'd0); run_pass1(2'd0);
        check("envelope 0 committed", env_committed, 3'b001);
        build(FAR1, 32'd0);
        env_words[22] = 32'h400001F8;          // wrong declared length
        @(negedge clk); env_index = 2'd1; start_pass1 = 1'b1;
        @(negedge clk); start_pass1 = 1'b0;
        stream(0, ENV_WORDS);
        wait (!busy); @(negedge clk);
        check("a length fault refuses", fault, 1);
        check("length fault", fault_code, 4'd4);
        check("and envelope 0's commit dies with the transaction", env_committed, 0);

        // ---- 5. a full transaction, and configuration_valid is unreachable before the
        //         fifteenth frame has been verified locally
        start_txn();
        build(FAR0, 32'd0); run_pass1(2'd0);
        build(FAR1, 32'd0); run_pass1(2'd1);
        build(FAR2, 32'd0); run_pass1(2'd2);
        check("all three committed", env_committed, 3'b111);
        check("pass 1 complete", pass1_complete, 1);
        check("still not confirmed", configuration_valid, 0);

        build(FAR0, 32'd0); run_pass2(2'd0);
        check("not confirmed after one envelope", configuration_valid, 0);
        check("five frames verified", rb_frames_ok, 5);
        build(FAR1, 32'd0); run_pass2(2'd1);
        check("not confirmed after two", configuration_valid, 0);
        check("ten frames verified", rb_frames_ok, 10);
        build(FAR2, 32'd0); run_pass2(2'd2);
        check("confirmed only after fifteen", configuration_valid, 1);
        check("fifteen frames verified", rb_frames_ok, 15);
        check("recovery cleared by a complete transaction", recovery_required, 0);

        // ---- 6. a readback mismatch anywhere refuses, including the flush frame
        start_txn();
        build(FAR0, 32'd0); run_pass1(2'd0);
        build(FAR1, 32'd0); run_pass1(2'd1);
        build(FAR2, 32'd0); run_pass1(2'd2);
        corrupt_env = 0; corrupt_frame = 4; corrupt_word = 17;   // the FLUSH frame
        build(FAR0, 32'd0); run_pass2(2'd0);
        corrupt_env = -1; corrupt_frame = -1; corrupt_word = -1;
        check("a flush-frame readback mismatch refuses", fault, 1);
        check("readback fault", fault_code, 4'd8);
        check("not confirmed", configuration_valid, 0);
        check("and recovery is required after a partial write", recovery_required, 1);

        if (errors == 0) $display("STREAM TB: OK");
        else             $display("STREAM TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule

`default_nettype wire
