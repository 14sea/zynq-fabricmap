// Integration bench: the stream engine and the scorer wired together exactly as
// carrier_top wires them, for one question the unit benches structurally cannot answer.
//
//   fault  ->  a later COMPLETE, fully verified 15-frame transaction  ->  arm
//
// Design §4 item 6 says what was written before a fault is not a candidate and may NEVER
// be scored. The complete transaction legitimately raises `configuration_valid` again — it
// really did write and verify all fifteen frames — so a scorer gated on
// `configuration_valid && arm` alone would score afterwards, and did. `recovery_required`
// is the flag that stays raised, and only wiring it into the scorer's own start condition
// makes the document's rule a property of the hardware rather than of a host script.

`timescale 1ns/1ps
`default_nettype none

module tb_carrier_integration;
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
    // The host's real envelope, so the control skeleton is never re-typed from the RTL.
    reg [31:0] real_env [0:ENV_WORDS-1];
    initial $readmemh("tb_envelope0.hex", real_env);

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
            // From the host's real envelope, not re-typed from the RTL: 0x13722093 is
            // the JTAG identity and is NOT what a configuration stream carries.
            env_words[14] = 32'h30018001; env_words[15] = real_env[15];
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


    // ---- the scorer, wired as carrier_top wires it
    wire [5:0]      vector;
    wire [5:0]      lut_q;
    wire            scorer_busy, scorer_done, scorer_armed;
    wire [6*8-1:0]  score_flat;
    reg             arm = 1'b0;

    // six trivial "LUTs": the fixture only needs the scorer to run, not to score well
    assign lut_q = {6{vector[0]}};

    carrier_scorer #(.LUTS(6)) scorer (
        .clk(clk), .rst_n(rst_n),
        .configuration_valid(configuration_valid),
        .recovery_required(recovery_required),
        .arm(arm), .mode_holdout(1'b0),
        .vector(vector), .lut_q(lut_q),
        .busy(scorer_busy), .done(scorer_done), .armed_o(scorer_armed),
        .score_flat(score_flat)
    );

    task do_arm;
        begin
            @(negedge clk); arm = 1'b1; @(negedge clk); arm = 1'b0;
        end
    endtask

    task full_transaction;
        begin
            start_txn();
            build(FAR0, 32'd0); run_pass1(2'd0);
            build(FAR1, 32'd0); run_pass1(2'd1);
            build(FAR2, 32'd0); run_pass1(2'd2);
            build(FAR0, 32'd0); run_pass2(2'd0);
            build(FAR1, 32'd0); run_pass2(2'd1);
            build(FAR2, 32'd0); run_pass2(2'd2);
        end
    endtask

    integer busy_seen;
    initial begin
        repeat (3) @(negedge clk); rst_n = 1'b1;

        // ---- 1. a clean run from reset scores: the refusal below must not be vacuous
        full_transaction();
        check("clean run confirms", configuration_valid, 1);
        check("clean run clears recovery", recovery_required, 0);
        busy_seen = 0;
        do_arm();
        repeat (400) begin @(negedge clk); if (scorer_busy) busy_seen = 1; end
        check("a clean run CAN be scored", busy_seen, 1);

        // ---- 2. fault -> complete transaction -> arm must not score
        // The fault: a corrupted readback word anywhere refuses the transaction.
        start_txn();
        build(FAR0, 32'd0); run_pass1(2'd0);
        build(FAR1, 32'd0); run_pass1(2'd1);
        build(FAR2, 32'd0); run_pass1(2'd2);
        corrupt_env = 0; corrupt_frame = 2; corrupt_word = 7;
        build(FAR0, 32'd0); run_pass2(2'd0);
        corrupt_env = -1; corrupt_frame = -1; corrupt_word = -1;
        check("the partial write faulted", fault, 1);
        check("and recovery is required", recovery_required, 1);

        full_transaction();
        check("the later transaction really did verify all fifteen", rb_frames_ok, 15);
        check("and it legitimately re-confirms", configuration_valid, 1);
        check("but recovery is still required", recovery_required, 1);

        busy_seen = 0;
        do_arm();
        repeat (400) begin @(negedge clk); if (scorer_busy) busy_seen = 1; end
        check("SCORING IS REFUSED after a fault", busy_seen, 0);
        check("armed stays 0", scorer_armed, 0);
        check("busy stays 0", scorer_busy, 0);
        check("done stays 0", scorer_done, 0);

        if (errors == 0) $display("INTEGRATION TB: OK");
        else             $display("INTEGRATION TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule

`default_nettype wire
