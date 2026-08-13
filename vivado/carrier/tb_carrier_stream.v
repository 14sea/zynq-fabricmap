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
    wire [31:0] icap_din, icap_dout;
    reg         rb_ack = 1'b0;
    wire [3:0]  rb_frames_ok;
    wire [3:0]  m_err;
    wire [15:0] m_committed;

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

    // ERRATUM 004. What used to be here was a "device" that handed back the words the DUT
    // had just staged, indexed by the DUT's own `frame_word` and `rb_frame`. It agreed with
    // any read protocol, including the none the RTL implemented, and it hid a consumer that
    // discarded three words in four. The device is now `icape2_model`, which parses the
    // wire and answers out of its own configuration memory (see that file's header).
    //
    // This bench's subject is unchanged: WHEN five frame CRCs may be used as authority.
    icape2_model #(.FRAME_WORDS(FRAME_WORDS))
      dev (.clk(clk), .csib(icap_csib), .rdwrb(icap_rdwrb), .i(icap_din), .o(icap_dout),
           .synced(), .err(m_err), .far(), .wcfg(), .rcfg(),
           .n_written(), .n_read(), .n_idle(), .n_frames_committed(m_committed),
           .buf_far());

    // The fabric before a candidate. The flush FAR must already hold what the envelope's
    // fifth frame carries — that is the invariant the manifest's pinned flush frame exists
    // to satisfy, and a readback that verifies proves it held.
    task preload_fabric;
        begin
            dev.preload_frame(FAR0, 32'hBA5E0000);
            dev.preload_frame(FAR1, 32'hBA5E1000);
            dev.preload_frame(FAR2, 32'hBA5E2000);
            dev.preload_frame(32'h00400A80, 32'hC0DE0000 + 4*FRAME_WORDS);
            dev.preload_frame(32'h00400C1E, 32'hC0DE0000 + 4*FRAME_WORDS);
            dev.preload_frame(32'h00400C80, 32'hC0DE0000 + 4*FRAME_WORDS);
        end
    endtask

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

    // The control skeleton is taken from the HOST's real envelope, never re-typed from the
    // RTL's own constants. This bench used to assert `env_words[15] = 32'h13722093` -- a copy
    // of the parameter it was testing -- so it agreed with the RTL while every real envelope
    // was rejected at that word. An oracle built from the DUT cannot test the DUT.
    //
    // `tb_envelope0.hex` is envelope 0 of the sealed no-op payload (sha256 07fbca9e...), the
    // bytes the host actually emits, derived from the published bitstream via the manifest.
    reg [31:0] real_env [0:ENV_WORDS-1];
    initial $readmemh("tb_envelope0.hex", real_env);

    task build(input [31:0] far, input [31:0] salt);
        begin
            for (i = 0; i < PREAMBLE; i = i + 1) env_words[i] = real_env[i];
            env_words[20] = far;                       // the FAR is this bench's variable
            for (i = 0; i < 505; i = i + 1)
                env_words[PREAMBLE+i] = 32'hC0DE0000 + salt + i;
            for (i = 528; i < ENV_WORDS; i = i + 1) env_words[i] = real_env[i];
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

    // `poke_widx < 0` leaves the fabric alone. Otherwise one word of configuration memory
    // is changed after the envelope is written and before it is read back: the only window
    // in which the staging copy and the fabric can be made to disagree, and therefore the
    // only way to tell a real read from an echo.
    task run_pass2_poke(input [1:0] e, input [31:0] poke_far, input integer poke_widx);
        begin
            @(negedge clk); env_index = e; start_pass2 = 1'b1;
            @(negedge clk); start_pass2 = 1'b0;
            stream(0, ENV_WORDS);
            if (poke_widx >= 0) dev.poke_frame_word(poke_far, poke_widx, 32'hDEADBEEF);
            wait (!busy); @(negedge clk);
        end
    endtask

    task run_pass2(input [1:0] e);
        begin
            run_pass2_poke(e, 32'd0, -1);
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
        preload_fabric();
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
        //         fifteenth frame has been verified locally.
        //
        // RESET FIRST, and that is the point rather than bench hygiene: tests 1-4 provoked
        // faults, `fault_since_reset` is sticky, and under design §4 item 6 the only way
        // back to a state where a clean run may clear `recovery_required` is reloading the
        // carrier — which on this board IS this reset. A bench that skipped it would be
        // asserting the rule the RTL was just corrected away from.
        @(negedge clk); rst_n = 1'b0;
        repeat (3) @(negedge clk); rst_n = 1'b1;
        @(negedge clk);
        check("the reload leaves recovery required", recovery_required, 1);
        check("and the fault latch clear", dut.fault_since_reset, 0);

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
        check("recovery cleared by a complete transaction with no fault", recovery_required, 0);

        // ---- 6. a readback mismatch anywhere refuses, including the flush frame
        start_txn();
        build(FAR0, 32'd0); run_pass1(2'd0);
        build(FAR1, 32'd0); run_pass1(2'd1);
        build(FAR2, 32'd0); run_pass1(2'd2);
        // the FLUSH frame's address, changed in the fabric behind the DUT's back
        build(FAR0, 32'd0); run_pass2_poke(2'd0, 32'h00400A80, 17);
        check("a flush-frame readback mismatch refuses", fault, 1);
        check("readback fault", fault_code, 4'd8);
        check("not confirmed", configuration_valid, 0);
        check("and recovery is required after a partial write", recovery_required, 1);

        // ---- 7. after a fault, a LATER COMPLETE transaction must NOT clear recovery.
        // Design §4 item 6 allows only a pinned-base restore or a carrier reload, and this
        // engine cannot tell a restore from any other candidate — nor certify its own
        // repair, since erratum 001 puts its own routing inside the rewritten frames. The
        // clearing rule and the document have to be the same contract.
        // The word test 6 changed is at the FLUSH FAR, and the flush frame is the one frame
        // an FDRI burst never commits — so on the fabric that difference is permanent until
        // something else writes it. Repairing it here is what "the carrier was reloaded"
        // means; without it this test would be asserting that a damaged fabric confirms.
        dev.preload_frame(32'h00400A80, 32'hC0DE0000 + 4*FRAME_WORDS);
        start_txn();
        build(FAR0, 32'd0); run_pass1(2'd0);
        build(FAR1, 32'd0); run_pass1(2'd1);
        build(FAR2, 32'd0); run_pass1(2'd2);
        build(FAR0, 32'd0); run_pass2(2'd0);
        build(FAR1, 32'd0); run_pass2(2'd1);
        build(FAR2, 32'd0); run_pass2(2'd2);
        check("a clean transaction after a fault still confirms", configuration_valid, 1);
        check("fifteen frames verified again", rb_frames_ok, 15);
        check("but recovery is NOT cleared after a fault", recovery_required, 1);
        check("and begin_txn did not launder the fault latch", dut.fault_since_reset, 1);

        check("the device never errored", m_err, 0);
        if (errors == 0) $display("STREAM TB: OK");
        else             $display("STREAM TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule

`default_nettype wire
