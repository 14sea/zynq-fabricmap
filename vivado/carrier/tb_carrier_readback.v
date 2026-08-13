// `carrier_stream` against a device that does NOT echo its staging buffer.
//
// This is the bench erratum 004 says should have existed. `tb_carrier_stream`'s device
// model returns the words the DUT staged, indexed by the DUT's own `frame_word`; it agrees
// with any read protocol, with none at all, and with a consumer that drops three words in
// four. Here the only thing between the DUT and its answers is `icape2_model`, which parses
// the wire and serves out of its own configuration memory.
//
// WHAT IS CHECKED, AND WHY EACH ONE IS A SEPARATE FACT
//   1. the write is accepted at all — a stream in the wrong word order never syncs, so the
//      model's own counters say whether the fabric was ever written;
//   2. the readback verifies fifteen frames and confirms the configuration;
//   3. the device saw NO protocol error: no abort from a direction change under CSIB, no
//      FDRO without RCFG, no IDCODE disagreement;
//   4. the fifteen frames the HOST reads out of the staging window are byte-identical to the
//      fifteen it sent — this is the SHA-256's raw material, and it is checked here as bytes
//      rather than trusted because a CRC agreed;
//   5. PROVENANCE: with one word of the model's configuration memory changed behind the
//      DUT's back — the staging copy still holding the written value — the readback must
//      FAIL. A DUT reading its own staging cannot fail this test, so passing it is what
//      distinguishes a real read from an echo.
//
// The read pipeline is swept, not assumed: `RB_LATENCY` is a bench parameter handed to the
// model, and the same run must pass at 0, 3 and 7 idle words. A design that hardcodes the
// skip passes exactly one of them.

`timescale 1ns/1ps
`default_nettype none

module tb_carrier_readback #(
    parameter integer RB_LATENCY  = 0,   // idle words at the head of a read burst
    parameter integer MODEL_FLUSH = 32   // clocks the device wants after a read command
);
    localparam integer ENV_WORDS    = 536;
    localparam integer FRAME_WORDS  = 101;
    localparam integer PREAMBLE     = 23;
    localparam integer FRAMES_PER_ENV = 5;
    localparam integer ENVELOPES    = 3;
    localparam integer TOTAL_FRAMES = ENVELOPES * FRAMES_PER_ENV;

    // What the probe SHOULD measure on this device.
    //
    // The sequence sends 32 flush clocks after each read command. A device that wants more
    // than that has not finished flushing when the turnaround happens, and the remainder is
    // served as idle words — so the probe legitimately measures the device's own read
    // latency PLUS whatever flush it still owed. That is the design working, not drifting.
    //
    // The bench computes this from ITS OWN stimulus, and the exact-value cases the ruling
    // asks for (latency 0 and 12) are run with MODEL_FLUSH = 32, where the excess is zero
    // and the expected number is simply RB_LATENCY.
    localparam integer FLUSH_EXCESS = (MODEL_FLUSH > 32) ? (MODEL_FLUSH - 32) : 0;
    localparam integer EXPECT_LAT   = RB_LATENCY + FLUSH_EXCESS;

    reg         clk = 1'b0, rst_n = 1'b0;
    reg         begin_txn = 1'b0, start_pass1 = 1'b0, start_pass2 = 1'b0;
    reg  [1:0]  env_index = 2'd0;
    reg         word_valid = 1'b0;
    reg  [31:0] word_data = 32'd0;
    wire        word_ready, stream_open;
    wire        busy, fault, pass1_complete, configuration_valid, recovery_required;
    wire [3:0]  fault_code;
    wire [1:0]  expect_env;
    wire [2:0]  env_committed;
    wire        rb_frame_ready;
    wire [7:0]  rb_latency;
    wire        rb_latency_valid;
    reg  [6:0]  host_raddr = 7'd0;
    wire [31:0] host_rdata;
    reg         rb_ack = 1'b0;
    wire [3:0]  rb_frames_ok;

    wire        icap_csib, icap_rdwrb;
    wire [31:0] icap_din, icap_dout;

    wire        m_synced, m_wcfg, m_rcfg;
    wire [3:0]  m_err;
    wire [31:0] m_far, m_buf_far;
    wire [15:0] m_written, m_read, m_idle, m_committed;

    integer errors = 0;
    integer i, k, e, f;

    // The FIRST fault code, latched. The one in STATUS at the end of a run is whatever the
    // cascade left there — after a refusal the envelope order breaks and every later start
    // reports F_ORDER — so a post-mortem that reads the final code learns nothing about
    // what actually went wrong.
    reg [3:0] first_fault = 4'd0;
    reg       fault_q = 1'b0;
    always @(posedge clk) begin
        fault_q <= fault;
        if (fault && !fault_q && first_fault == 4'd0) first_fault <= fault_code;
    end

    // the words the host SENDS, and the words the host READS BACK
    reg [31:0] env_words [0:ENV_WORDS-1];
    reg [31:0] tx [0:TOTAL_FRAMES-1][0:FRAME_WORDS-1];
    reg [31:0] rx [0:TOTAL_FRAMES-1][0:FRAME_WORDS-1];
    integer    rx_frames = 0;

    always #5 clk = ~clk;

    carrier_stream dut (
        .clk(clk), .rst_n(rst_n),
        .begin_txn(begin_txn), .start_pass1(start_pass1), .start_pass2(start_pass2),
        .env_index(env_index), .protocol_fault(1'b0),
        .word_valid(word_valid), .word_data(word_data), .word_ready(word_ready),
        .stream_open(stream_open),
        .busy(busy), .fault(fault), .fault_code(fault_code), .expect_env(expect_env),
        .pass1_complete(pass1_complete), .configuration_valid(configuration_valid),
        .recovery_required(recovery_required), .env_committed(env_committed),
        .host_raddr(host_raddr), .host_rdata(host_rdata),
        .rb_frame_ready(rb_frame_ready), .rb_ack(rb_ack), .rb_frames_ok(rb_frames_ok),
        .rb_latency(rb_latency), .rb_latency_valid(rb_latency_valid),
        .icap_csib(icap_csib), .icap_rdwrb(icap_rdwrb),
        .icap_din(icap_din), .icap_dout(icap_dout)
    );

    icape2_model #(.FRAME_WORDS(FRAME_WORDS), .READ_LATENCY(RB_LATENCY),
                   .MIN_FLUSH(MODEL_FLUSH))
      dev (.clk(clk), .csib(icap_csib), .rdwrb(icap_rdwrb), .i(icap_din), .o(icap_dout),
           .synced(m_synced), .err(m_err), .far(m_far), .wcfg(m_wcfg), .rcfg(m_rcfg),
           .n_written(m_written), .n_read(m_read), .n_idle(m_idle),
           .n_frames_committed(m_committed), .buf_far(m_buf_far));

    // ---- the pinned addresses (scripts/board_carrier_guard.py). Stimulus, not an oracle.
    function [31:0] target_far(input integer env, input integer frame);
        begin
            case (env)
                0: target_far = 32'h00400A20 + frame;
                1: target_far = 32'h00400C1A + frame;
                default: target_far = 32'h00400C20 + frame;
            endcase
        end
    endfunction

    function [31:0] flush_far(input integer env);
        begin
            case (env)
                0: flush_far = 32'h00400A80;
                1: flush_far = 32'h00400C1E;
                default: flush_far = 32'h00400C80;
            endcase
        end
    endfunction

    // The candidate's content, and the flush frame's PINNED content. The flush frame is the
    // one place where what is written must equal what is already there — that is the whole
    // reason the manifest supplies it — so the bench preloads the fabric with exactly it.
    function [31:0] tx_word(input integer env, input integer frame, input integer widx);
        begin
            if (frame == FRAMES_PER_ENV - 1)
                tx_word = 32'hF1005000 + env * 32'h100 + widx;
            else
                tx_word = 32'hC0DE0000 + env * 32'h10000 + frame * 32'h100 + widx;
        end
    endfunction

    task check_i(input [255:0] what, input integer g, input integer want);
        begin
            if (g !== want) begin
                $display("FAIL %0s: got %0d want %0d", what, g, want);
                errors = errors + 1;
            end
        end
    endtask

    task check_w(input [255:0] what, input [31:0] g, input [31:0] want);
        begin
            if (g !== want) begin
                $display("FAIL %0s: got %08x want %08x", what, g, want);
                errors = errors + 1;
            end
        end
    endtask

    // ---- the envelope, built the way `icap_sequence.build_envelope` builds it
    reg [31:0] real_env [0:ENV_WORDS-1];
    initial $readmemh("tb_envelope0.hex", real_env);

    task build(input integer env);
        integer j, fr;
        begin
            for (j = 0; j < PREAMBLE; j = j + 1) env_words[j] = real_env[j];
            env_words[20] = target_far(env, 0);
            for (fr = 0; fr < FRAMES_PER_ENV; fr = fr + 1)
                for (j = 0; j < FRAME_WORDS; j = j + 1) begin
                    env_words[PREAMBLE + fr*FRAME_WORDS + j] = tx_word(env, fr, j);
                    tx[env*FRAMES_PER_ENV + fr][j] = tx_word(env, fr, j);
                end
            for (j = ENV_WORDS - 8; j < ENV_WORDS; j = j + 1) env_words[j] = real_env[j];
        end
    endtask

    task stream_all;
        integer j;
        begin
            j = 0;
            while (j < ENV_WORDS && !fault) begin
                @(negedge clk);
                word_data  = env_words[j];
                word_valid = 1'b1;
                @(posedge clk);
                while (!word_ready && !fault) @(posedge clk);
                @(negedge clk);
                word_valid = 1'b0;
                j = j + 1;
            end
            @(negedge clk);
        end
    endtask

    task run_pass1(input integer env);
        begin
            build(env);
            @(negedge clk); env_index = env; start_pass1 = 1'b1;
            @(negedge clk); start_pass1 = 1'b0;
            stream_all();
            wait (!busy); @(negedge clk);
        end
    endtask

    // Pass 2 streams the envelope and then services the readback: five frames, each read
    // out of the staging window word by word before it is acknowledged — which is exactly
    // what the U-Boot transport does with `cp.l`.
    // `poke_widx < 0` means "do not disturb the fabric". Otherwise one word of the
    // model's configuration memory is changed AFTER the envelope has been written and
    // BEFORE it is read back — the only window in which the staging copy and the fabric
    // can be made to disagree.
    task run_pass2_poke(input integer env, input [31:0] poke_far, input integer poke_widx);
        integer guard_cycles;
        begin
            build(env);
            @(negedge clk); env_index = env; start_pass2 = 1'b1;
            @(negedge clk); start_pass2 = 1'b0;
            stream_all();
            if (poke_widx >= 0) dev.poke_frame_word(poke_far, poke_widx, 32'hDEADBEEF);
            guard_cycles = 0;
            while (busy && !fault && guard_cycles < 4000000) begin
                @(posedge clk); #1;
                guard_cycles = guard_cycles + 1;
                if (rb_frame_ready) begin
                    for (k = 0; k < FRAME_WORDS; k = k + 1) begin
                        host_raddr = k;
                        #1;
                        if (rx_frames < TOTAL_FRAMES) rx[rx_frames][k] = host_rdata;
                    end
                    rx_frames = rx_frames + 1;
                    @(negedge clk); rb_ack = 1'b1;
                    @(negedge clk); rb_ack = 1'b0;
                end
            end
            @(negedge clk);
        end
    endtask

    task run_pass2(input integer env);
        begin
            run_pass2_poke(env, 32'd0, -1);
        end
    endtask

    task start_txn;
        begin
            @(negedge clk); begin_txn = 1'b1;
            @(negedge clk); begin_txn = 1'b0;
            @(negedge clk);
        end
    endtask

    // The fabric as it stands BEFORE a candidate: the target frames hold something else
    // entirely, the flush frames hold the pinned content the envelope will rewrite with.
    task preload_fabric;
        integer env, fr, j;
        begin
            for (env = 0; env < ENVELOPES; env = env + 1) begin
                for (fr = 0; fr < FRAMES_PER_ENV - 1; fr = fr + 1)
                    dev.preload_frame(target_far(env, fr), 32'hBA5E0000 + env*256 + fr*16);
                // the flush frame's pinned content, which is also what will be written
                dev.preload_frame(flush_far(env), 32'hF1005000 + env * 256);
            end
        end
    endtask

    initial begin
        repeat (3) @(negedge clk); rst_n = 1'b1;
        preload_fabric();

        // ---------------------------------------------------------------- the good path
        start_txn();
        run_pass1(0); run_pass1(1); run_pass1(2);
        check_i("all three envelopes commit", env_committed, 7);
        check_i("pass 1 complete", pass1_complete, 1);

        run_pass2(0);
        check_i("envelope 0 verifies five frames", rb_frames_ok, 5);
        // TELEMETRY: the probe measured this device's pipeline, and says so.
        check_i("the latency is reported valid", rb_latency_valid, 1);
        check_i("and it is the device's own", rb_latency, EXPECT_LAT);
        run_pass2(1);
        check_i("envelope 1 makes it ten", rb_frames_ok, 10);
        check_i("envelope 1 measured it too", rb_latency_valid, 1);
        check_i("with the same answer", rb_latency, EXPECT_LAT);
        run_pass2(2);
        check_i("fifteen frames verified", rb_frames_ok, 15);
        check_i("no fault", fault, 0);
        check_i("configuration confirmed", configuration_valid, 1);

        // ---- what the DEVICE saw. These are the checks no echo model can make.
        check_i("the device never errored", m_err, 0);
        check_i("twelve frames reached the fabric", m_committed, 12);
        check_i("the host read fifteen frames", rx_frames, 15);

        // ---- the bytes the SHA-256 will be computed over
        for (f = 0; f < TOTAL_FRAMES; f = f + 1)
            for (k = 0; k < FRAME_WORDS; k = k + 1)
                if (rx[f][k] !== tx[f][k]) begin
                    $display("FAIL frame %0d word %0d: read %08x, sent %08x",
                             f, k, rx[f][k], tx[f][k]);
                    errors = errors + 1;
                end

        // ------------------------------------------------------- 5. PROVENANCE
        // One word of the fabric is changed behind the DUT's back, AFTER pass 1 has
        // committed the CRCs. The staging copy of that frame still holds the value that was
        // written, so a DUT reading its own buffer sees nothing wrong. Only a DUT that
        // actually reads configuration memory can fail here — and failing is the pass
        // condition.
        @(negedge clk); rst_n = 1'b0;
        repeat (3) @(negedge clk); rst_n = 1'b1;
        @(negedge clk);
        rx_frames = 0;
        start_txn();
        run_pass1(0); run_pass1(1); run_pass1(2);
        run_pass2(0);
        check_i("envelope 0 still verifies", rb_frames_ok, 5);
        run_pass2_poke(1, target_far(1, 2), 40);
        check_i("a fabric that disagrees is refused", fault, 1);
        check_i("and it is a readback fault", fault_code, 8);
        check_i("confirmation is withheld", configuration_valid, 0);
        check_i("recovery is required", recovery_required, 1);
        // The probe SUCCEEDED and the frames then disagreed. That is exactly when a host
        // wants the measurement, so the fault must not take it away.
        check_i("a readback fault keeps the latency", rb_latency_valid, 1);
        check_i("and its value", rb_latency, EXPECT_LAT);

        // -------------------------------------------- 6. the probe fails, and says nothing
        // The device stops speaking the DUT's word order between one envelope and the next.
        // Envelope 0 measured a good device a moment ago; envelope 1 must report NOTHING
        // rather than the number still sitting in the register.
        @(negedge clk); rst_n = 1'b0;
        repeat (3) @(negedge clk); rst_n = 1'b1;
        @(negedge clk);
        check_i("reset clears the validity", rb_latency_valid, 0);
        rx_frames = 0;
        start_txn();
        run_pass1(0); run_pass1(1); run_pass1(2);
        run_pass2(0);
        check_i("envelope 0 measured the device", rb_latency_valid, 1);
        check_i("envelope 0 latency", rb_latency, EXPECT_LAT);
        dev.set_wire_order(1'b0);              // the device stops answering in that order
        run_pass2(1);
        check_i("the probe fails", fault_code, 12);
        check_i("and the validity is CLEARED, not inherited", rb_latency_valid, 0);
        dev.set_wire_order(1'b1);

        $display("READBACK TB (latency %0d, flush %0d): %0d written, %0d read, %0d idle",
                 RB_LATENCY, MODEL_FLUSH, m_written, m_read, m_idle);
        // The measured latency and the two fault codes are printed unconditionally: when a
        // mutant dies, HOW it died is the evidence, and a bare failure count does not say.
        $display("READBACK TB: measured latency %0d, first fault %0d, device err %0d",
                 dut.rb_lat, first_fault, m_err);
        if (errors == 0) $display("READBACK TB: OK");
        else             $display("READBACK TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule

`default_nettype wire
