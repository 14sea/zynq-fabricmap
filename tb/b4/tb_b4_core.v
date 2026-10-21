`timescale 1ns/1ps
// B4 carrier v2 bench: AXI-Lite master -> b4_core (register file + gate + engine) with the bench's fabric
// (tb/b4/b4_target_slice_model.v = the behaviour hypothesis under a genome only the bench knows) and the
// engine's GSR drive fed back as the model's init event. One scenario per run (+SCENARIO=<name>); a fault is
// persistent in v2 (only a reconfiguration = a fresh simulation clears it), which is itself one of the checks.
// Every AXI access and every mark is logged as JSON lines (sim/b4/out/<scenario>.jsonl) for the host-side
// record builder (host/b4carrier_records.py). The owner's five reproductions of 2026-10-21 (P9, open close, AXI
// backpressure, STEP snapshot, busy CLOSE) are scenarios here, with the REPAIRED expectations.
module tb_b4_core;
    `include "b4_fixture.vh"
    localparam integer ASSERT_DELAY = 8, PULSE = 2, RELEASE = 16, SAMPLE_OFFSET = 4, SETTLE = 4, HOLD = 4;
    localparam integer QUIET = ASSERT_DELAY + PULSE + RELEASE + SAMPLE_OFFSET + 16;   // the host's quiet window after INIT_REQ
    reg clk = 0; always #10 clk = ~clk;
    reg rst_n = 0;
    reg [15:0] awaddr = 0, araddr = 0; reg awvalid = 0, wvalid = 0, bready = 1, arvalid = 0, rready = 1;
    reg [31:0] wdata = 0; wire awready, wready, bvalid, arready, rvalid; wire [1:0] bresp, rresp; wire [31:0] rdata;
    wire slice_clk, slice_ce, slice_sr; wire [7:0] slice_d, slice_q; wire gsr_drive;

    reg ext_quiet = 1; wire stall;
    b4_core #(.NONCE_SEED(SEED), .ASSERT_DELAY(ASSERT_DELAY), .PULSE(PULSE), .RELEASE(RELEASE), .SAMPLE_OFFSET(SAMPLE_OFFSET), .SETTLE(SETTLE), .HOLD(HOLD)) dut (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(awaddr), .s_awvalid(awvalid), .s_awready(awready),
        .s_wdata(wdata), .s_wstrb(4'hF), .s_wvalid(wvalid), .s_wready(wready),
        .s_bresp(bresp), .s_bvalid(bvalid), .s_bready(bready),
        .s_araddr(araddr), .s_arvalid(arvalid), .s_arready(arready),
        .s_rdata(rdata), .s_rresp(rresp), .s_rvalid(rvalid), .s_rready(rready),
        .slice_clk(slice_clk), .slice_ce(slice_ce), .slice_sr(slice_sr), .slice_d(slice_d), .slice_q(slice_q), .gsr_drive(gsr_drive),
        .ext_quiet(ext_quiet), .stall(stall));
    b4_target_slice target (.slice_clk(slice_clk), .ce(slice_ce), .sr(slice_sr), .d(slice_d), .q(slice_q), .gsr(gsr_drive));

    integer fails = 0, log_fd;
    initial begin #20000000; $display("WATCHDOG: scenario %0s did not finish (fails so far %0d)", scenario, fails); $display("TB_FAIL %0s (watchdog)", scenario); $finish; end
    reg [1:0] last_bresp, last_rresp; reg [31:0] last_rdata; reg aw_done = 0, w_done = 0;
    reg [255:0] scenario;
    // the event's entry context (contract 5.1 step 0 / 5.6 J3): at every GSR assertion the inputs and the slice clock are 0
    always @(posedge gsr_drive) if ({slice_clk, slice_sr, slice_ce, slice_d} != 11'd0) begin fails = fails + 1; $display("FAIL: GSR asserted with inputs held: clk=%0d ce=%0d sr=%0d d=%h [t=%0t]", slice_clk, slice_ce, slice_sr, slice_d, $time); end
    task check(input cond, input [255:0] what); begin
        if (!cond) begin fails = fails + 1; $display("FAIL: %0s   [rdata=%h rresp=%b bresp=%b t=%0t]", what, last_rdata, last_rresp, last_bresp, $time); end
    end endtask
    task mark(input [255:0] what); begin $fdisplay(log_fd, "{\"t\": %0d, \"mark\": \"%0s\"}", $time, what); end endtask
    // AW and W are independent channels: each is held until its own ready (the gate masks AW while an event is pending
    // and lets W through, so the two handshakes may complete in different cycles)
    task wr(input [15:0] a, input [31:0] d); begin
        @(negedge clk); awaddr = a; wdata = d; awvalid = 1; wvalid = 1; aw_done = 0; w_done = 0;
        while (!(aw_done && w_done)) begin
            #1;                                                   // the readies are combinational: sampled before the posedge
            if (awvalid && awready) aw_done = 1;
            if (wvalid && wready) w_done = 1;
            @(negedge clk); if (aw_done) awvalid = 0; if (w_done) wvalid = 0;
        end
        while (!bvalid) @(negedge clk);
        last_bresp = bresp; @(negedge clk);
        $fdisplay(log_fd, "{\"t\": %0d, \"op\": \"wr\", \"addr\": %0d, \"data\": %0d, \"resp\": %0d}", $time, a, d, last_bresp);
    end endtask
    task rd(input [15:0] a); begin
        @(negedge clk); araddr = a; arvalid = 1;
        while (!arready) @(negedge clk);
        @(negedge clk); arvalid = 0;
        while (!rvalid) @(negedge clk);
        last_rdata = rdata; last_rresp = rresp; @(negedge clk);
        if (^last_rdata === 1'bx) $fdisplay(log_fd, "{\"t\": %0d, \"op\": \"rd\", \"addr\": %0d, \"data\": null, \"x\": \"%b\", \"resp\": %0d}", $time, a, last_rdata, last_rresp);
        else $fdisplay(log_fd, "{\"t\": %0d, \"op\": \"rd\", \"addr\": %0d, \"data\": %0d, \"resp\": %0d}", $time, a, last_rdata, last_rresp);
    end endtask
    task stage(input [767:0] p); integer i; begin
        for (i = 0; i < 24; i = i + 1) wr(16'h2100 + 4*i, p[(23-i)*32 +: 32]);
    end endtask
    task arm; begin wr(16'h2000, 32'h40); end endtask
    task provision(input [127:0] k); integer j; begin
        for (j = 0; j < 4; j = j + 1) wr(16'h2160 + 4*j, k[(3-j)*32 +: 32]);
        wr(16'h2000, 32'h100);
    end endtask
    task wait_gate; begin repeat (5) @(negedge clk); rd(16'h2004); while (last_rdata[0]) rd(16'h2004); end endtask
    task wait_engine; begin rd(16'h2004); while (last_rdata[3]) rd(16'h2004); end endtask
    task reset; begin
        @(negedge clk); awvalid = 0; wvalid = 0; arvalid = 0;
        rst_n = 0; repeat (3) @(negedge clk); rst_n = 1; repeat (2) @(negedge clk);
    end endtask
    task expect_nonce(input [63:0] n, input [255:0] what); begin
        rd(16'h202C); check(last_rdata == n[31:0], what); rd(16'h2030); check(last_rdata == n[63:32], what);
    end endtask
    task expect_fault(input [3:0] fcode, input [255:0] what); begin
        rd(16'h2004); check(last_rdata[1] == 1 && last_rdata[7] == 1, what);
        rd(16'h2008); check(last_rdata[3:0] == fcode, what);
    end endtask
    task slot(input [4:0] a); begin wr(16'h201C, {27'd0, a}); rd(16'h2018); end endtask
    // the masked comparison of a sample with the model's expectation (the model's null cells are not compared)
    task expect_slot(input [4:0] a, input [7:0] q, input [7:0] m, input [255:0] what); begin
        slot(a);
        if (((last_rdata[7:0] ^ q) & m) != 8'd0) begin fails = fails + 1; $display("FAIL: %0s slot %0d = %b expected %b mask %b [t=%0t]", what, a, last_rdata[7:0], q, m, $time); end
    end endtask
    task pre_sample; begin wr(16'h2000, 32'h200); wait_engine; end endtask
    // the events: the gate stalls every access from the request's acceptance until the sample is taken, so a poll
    // issued right away simply waits at the bus; the host may also keep quiet for QUIET cycles (both are exercised)
    task init_event; begin wr(16'h2000, 32'h400); repeat (QUIET) @(negedge clk); wait_engine; end endtask
    task init_event_poll; begin wr(16'h2000, 32'h400); wait_engine; end endtask
    task restore_event; begin wr(16'h2000, 32'h4000); repeat (QUIET) @(negedge clk); wait_engine; end endtask
    task step(input [24:0] s); begin wr(16'h2038, {7'd0, s}); wr(16'h2000, 32'h800); wait_engine; end endtask
    task cleanup; begin wr(16'h2000, 32'h1000); wait_engine; end endtask
    task close; begin wr(16'h2000, 32'h2000); wait_engine; end endtask
    task close_injection; begin wr(16'h2000, 32'h8000); wait_engine; end endtask
    task arm_a5; begin wr(16'h2000, 32'hC0); end endtask
    task slot_in(input [4:0] a); begin wr(16'h201C, {27'd0, a}); rd(16'h2040); end endtask

    // ------------------------------------------------------------------ one complete transaction on fixture k
    task fixture_inputs(input integer k, input integer j, output [24:0] s); begin
        case (k)
        0: case (j) 0: s = FIX0_IN0; 1: s = FIX0_IN1; 2: s = FIX0_IN2; 3: s = FIX0_IN3; 4: s = FIX0_IN4; 5: s = FIX0_IN5; default: s = FIX0_IN6; endcase
        1: case (j) 0: s = FIX1_IN0; 1: s = FIX1_IN1; 2: s = FIX1_IN2; 3: s = FIX1_IN3; 4: s = FIX1_IN4; 5: s = FIX1_IN5; default: s = FIX1_IN6; endcase
        2: case (j) 0: s = FIX2_IN0; 1: s = FIX2_IN1; 2: s = FIX2_IN2; 3: s = FIX2_IN3; 4: s = FIX2_IN4; 5: s = FIX2_IN5; default: s = FIX2_IN6; endcase
        3: case (j) 0: s = FIX3_IN0; 1: s = FIX3_IN1; 2: s = FIX3_IN2; 3: s = FIX3_IN3; 4: s = FIX3_IN4; 5: s = FIX3_IN5; default: s = FIX3_IN6; endcase
        4: case (j) 0: s = FIX4_IN0; 1: s = FIX4_IN1; 2: s = FIX4_IN2; 3: s = FIX4_IN3; 4: s = FIX4_IN4; 5: s = FIX4_IN5; default: s = FIX4_IN6; endcase
        default: case (j) 0: s = FIX5_IN0; 1: s = FIX5_IN1; 2: s = FIX5_IN2; 3: s = FIX5_IN3; 4: s = FIX5_IN4; 5: s = FIX5_IN5; default: s = FIX5_IN6; endcase
        endcase
    end endtask
    task fixture_expect(input integer k, input integer j, output [7:0] q, output [7:0] m); begin
        case (k)
        0: case (j) 0: begin q = FIX0_Q0; m = FIX0_M0; end 1: begin q = FIX0_Q1; m = FIX0_M1; end 2: begin q = FIX0_Q2; m = FIX0_M2; end 3: begin q = FIX0_Q3; m = FIX0_M3; end 4: begin q = FIX0_Q4; m = FIX0_M4; end 5: begin q = FIX0_Q5; m = FIX0_M5; end 6: begin q = FIX0_Q6; m = FIX0_M6; end default: begin q = FIX0_Q7; m = FIX0_M7; end endcase
        1: case (j) 0: begin q = FIX1_Q0; m = FIX1_M0; end 1: begin q = FIX1_Q1; m = FIX1_M1; end 2: begin q = FIX1_Q2; m = FIX1_M2; end 3: begin q = FIX1_Q3; m = FIX1_M3; end 4: begin q = FIX1_Q4; m = FIX1_M4; end 5: begin q = FIX1_Q5; m = FIX1_M5; end 6: begin q = FIX1_Q6; m = FIX1_M6; end default: begin q = FIX1_Q7; m = FIX1_M7; end endcase
        2: case (j) 0: begin q = FIX2_Q0; m = FIX2_M0; end 1: begin q = FIX2_Q1; m = FIX2_M1; end 2: begin q = FIX2_Q2; m = FIX2_M2; end 3: begin q = FIX2_Q3; m = FIX2_M3; end 4: begin q = FIX2_Q4; m = FIX2_M4; end 5: begin q = FIX2_Q5; m = FIX2_M5; end 6: begin q = FIX2_Q6; m = FIX2_M6; end default: begin q = FIX2_Q7; m = FIX2_M7; end endcase
        3: case (j) 0: begin q = FIX3_Q0; m = FIX3_M0; end 1: begin q = FIX3_Q1; m = FIX3_M1; end 2: begin q = FIX3_Q2; m = FIX3_M2; end 3: begin q = FIX3_Q3; m = FIX3_M3; end 4: begin q = FIX3_Q4; m = FIX3_M4; end 5: begin q = FIX3_Q5; m = FIX3_M5; end 6: begin q = FIX3_Q6; m = FIX3_M6; end default: begin q = FIX3_Q7; m = FIX3_M7; end endcase
        4: case (j) 0: begin q = FIX4_Q0; m = FIX4_M0; end 1: begin q = FIX4_Q1; m = FIX4_M1; end 2: begin q = FIX4_Q2; m = FIX4_M2; end 3: begin q = FIX4_Q3; m = FIX4_M3; end 4: begin q = FIX4_Q4; m = FIX4_M4; end 5: begin q = FIX4_Q5; m = FIX4_M5; end 6: begin q = FIX4_Q6; m = FIX4_M6; end default: begin q = FIX4_Q7; m = FIX4_M7; end endcase
        default: case (j) 0: begin q = FIX5_Q0; m = FIX5_M0; end 1: begin q = FIX5_Q1; m = FIX5_M1; end 2: begin q = FIX5_Q2; m = FIX5_M2; end 3: begin q = FIX5_Q3; m = FIX5_M3; end 4: begin q = FIX5_Q4; m = FIX5_M4; end 5: begin q = FIX5_Q5; m = FIX5_M5; end 6: begin q = FIX5_Q6; m = FIX5_M6; end default: begin q = FIX5_Q7; m = FIX5_M7; end endcase
        endcase
    end endtask
    task fixture_genome(input integer k, output [20:0] g); begin
        case (k) 0: g = FIX0_GENOME; 1: g = FIX1_GENOME; 2: g = FIX2_GENOME; 3: g = FIX3_GENOME; 4: g = FIX4_GENOME; default: g = FIX5_GENOME; endcase
    end endtask
    task payload_of(input integer k, output [767:0] p); begin
        case (k) 0: p = VALID1; 1: p = VALID2; 2: p = VALID3; 3: p = VALID4; 4: p = VALID5; default: p = VALID6; endcase
    end endtask

    reg [24:0] s; reg [7:0] q, m, q_base_expected; reg [20:0] g; reg [767:0] p; reg [31:0] hb_before, gsr_before; integer j, k;
    task transaction(input integer k, input do_cleanup, input [255:0] what); begin
        fixture_genome(k, g); target.genome = g; payload_of(k, p);
        fixture_expect(k, 0, q_base_expected, m);                                      // on the bench the base is this fixture's own genome; its event value is the init sample's (masked below)
        mark("transaction_begin");
        stage(p); arm; wait_gate;
        rd(16'h2004); check(last_rdata[2] == 1 && last_rdata[6] == 1 && last_rdata[1] == 0, what);   // armed, tag_ok, no fault
        rd(16'h2200); check(last_rdata == p[767:736], "hw_commit = the signed commit");
        rd(16'h2028); hb_before = last_rdata; rd(16'h2020); gsr_before = last_rdata;
        pre_sample; rd(16'h2004); check(last_rdata[5] == 1, "pre_sampled");
        slot(5'd0);                                                                     // the pre-init sample: recorded, not compared (x before the first event)
        init_event;
        rd(16'h2004); check(last_rdata[9] == 1 && last_rdata[10] == 0, "init_done, not pending");
        rd(16'h2028); check(last_rdata < hb_before, "heartbeat restarted by the init event (GSR witness)");
        rd(16'h2020); check(last_rdata[7:0] == gsr_before[7:0] + 8'd1 && last_rdata[15:8] == 8'd2 && last_rdata[23:16] == PULSE, "gsr_count + 1, mechanism 2, PULSE clocks");
        rd(16'h2004); check(last_rdata[11] == 1 && last_rdata[2] == 1, "key_loaded and armed persist across the init event");
        rd(16'h2014); check(last_rdata[10:0] == 11'd0, "inputs and slice clock are 0 after the init event");
        rd(16'h2020); check(last_rdata[27] == 0, "no pre-init cleanup in an idle context");
        fixture_expect(k, 0, q, m); expect_slot(5'd1, q, m, what);                     // the init sample (step 0)
        slot_in(5'd0); slot_in(5'd1); check(last_rdata == 32'd0, "the init sample's applied inputs are 0");
        for (j = 0; j < FIX_STEPS; j = j + 1) begin
            fixture_inputs(k, j, s); step(s);
            rd(16'h2004); check(last_rdata[4] == 1 && last_rdata[1] == 0, "step_done, no fault");
            fixture_expect(k, j + 1, q, m); expect_slot(5'd2 + j, q, m, what);
            slot_in(5'd2 + j); check(last_rdata[24:0] == s, "the applied inputs are the accepted step");
        end
        rd(16'h2004); check(last_rdata[25:21] == FIX_STEPS && last_rdata[20:16] == FIX_STEPS + 2, "step_index and slot_count");
        if (do_cleanup) begin
            cleanup; rd(16'h2004); check(last_rdata[13] == 1, "cleanup_done");
            rd(16'h2014); check(last_rdata[10:0] == 11'd0, "cleanup leaves inputs and clock at 0");
            slot(5'd2 + FIX_STEPS); slot_in(5'd2 + FIX_STEPS);                           // the cleanup sample: recorded, not compared
            // P8 is the host's (the base written and read back over PCAP); P9 is the carrier's: the event on the base
            rd(16'h2020); gsr_before = last_rdata;
            restore_event; rd(16'h2004); check(last_rdata[26] == 1, "restore_done");
            rd(16'h2020); check(last_rdata[7:0] == gsr_before[7:0] + 8'd1, "the restore event counted");
            rd(16'h203C); fixture_expect(k, 0, q, m); check(((last_rdata[7:0] ^ q) & m) == 0, "the base-state sample after the restore event");
            close; rd(16'h2004); check(last_rdata[2] == 0 && last_rdata[12] == 1 && last_rdata[14] == 0, "closed: not armed, idle, no injection open");
        end else begin
            close_injection; rd(16'h2004); check(last_rdata[2] == 0 && last_rdata[12] == 0 && last_rdata[14] == 1, "injection closed: not armed, NOT idle, injection open");
        end
        mark("transaction_end");
    end endtask

    initial begin
        if (!$value$plusargs("SCENARIO=%s", scenario)) scenario = "flow";
        log_fd = $fopen($sformatf("sim/b4/out/%0s.jsonl", scenario), "w");
        $fdisplay(log_fd, "{\"scenario\": \"%0s\", \"timing\": [%0d, %0d, %0d, %0d, %0d, %0d]}", scenario, ASSERT_DELAY, PULSE, RELEASE, SAMPLE_OFFSET, SETTLE, HOLD);
        reset;
        case (scenario)
        "regs": begin
            rd(16'h2004); check(last_rdata != 0 && last_rdata[8] == 1 && last_rdata[31:27] == 0, "alive bit, reserved zero");
            rd(16'h2028); hb_before = last_rdata; rd(16'h2028); check(last_rdata > hb_before, "heartbeat advances");
            rd(16'h200C); check(last_rresp == 2'b10, "undecoded read is SLVERR");
            rd(16'h2100); check(last_rresp == 2'b10, "staging is write-only");
            rd(16'h2240); check(last_rresp == 2'b10, "the B1 sweep readout window is gone");
            wr(16'h2010, 32'h1); check(last_bresp == 2'b10, "Q_LIVE not writable");
            rd(16'h2034); check(last_rresp == 2'b00 && last_rdata == 32'h42340001, "VARIANT reads the B4 v2 word");
            wr(16'h2034, 32'h1); check(last_bresp == 2'b10, "VARIANT is not writable");
            rd(16'h2024); check(last_rdata == {HOLD[3:0], SETTLE[3:0], SAMPLE_OFFSET[7:0], RELEASE[7:0], ASSERT_DELAY[7:0]}, "TIMING word");
            rd(16'h2020); check(last_rdata[15:8] == 8'd2 && last_rdata[7:0] == 0 && last_rdata[23:16] == PULSE, "mechanism 2, PULSE, gsr_count 0 at configuration");
            wr(16'h2000, 32'h600); check(last_bresp == 2'b10, "a combined CTRL command is SLVERR");
            wr(16'h2000, 32'h80); check(last_bresp == 2'b10, "the A5 flag alone is SLVERR");
            wr(16'h2000, 32'h10200); check(last_bresp == 2'b10, "an unknown CTRL bit is SLVERR");
            wr(16'h2000, 32'h0); check(last_bresp == 2'b10, "an empty CTRL command is SLVERR");
            expect_nonce(N0, "nonce = seed after configuration");
            rd(16'h2004); check(last_rdata[11] == 0 && last_rdata[12] == 1, "key_loaded = 0, idle after configuration");
            provision(KEY_A);
            rd(16'h2004); check(last_rdata[11] == 1, "key_loaded after commit");
            wr(16'h2160, 32'hDEADBEEF); check(last_bresp == 2'b10, "key is write-once");
            rd(16'h2160); check(last_rresp == 2'b10, "key words not readable");
            reset; rd(16'h2004); check(last_rdata[11] == 1, "key_loaded SURVIVES a reset (persistent; only a reconfiguration clears it)");
            wr(16'h2038, 32'h01FF00A5); rd(16'h2038); check(last_rdata == 32'h01FF00A5, "STEP_IN stages and reads back");
            wr(16'h201C, 32'd7); rd(16'h201C); check(last_rdata == 7, "SLOT_ADDR");
        end
        "flow": begin
            provision(KEY_A);
            for (k = 0; k < FIX_N; k = k + 1) begin
                transaction(k, 1, "flow transaction");
                case (k) 0: expect_nonce(N1, "nonce after T1"); 1: expect_nonce(N2, "nonce after T2"); 2: expect_nonce(N3, "nonce after T3"); 3: expect_nonce(N4, "nonce after T4"); 4: expect_nonce(N5, "nonce after T5"); default: expect_nonce(N6, "nonce after T6"); endcase
            end
            rd(16'h2020); check(last_rdata[7:0] == 2 * FIX_N, "gsr_count = two events per transaction (init, restore)");
            // a replay of VALID1 on the advanced (persistent) nonce: AUTH fault, sticky, and a reset does not clear it
            stage(VALID1); arm; wait_gate; expect_fault(13, "replay -> F_ARM_AUTH");
            reset; expect_fault(13, "the fault SURVIVES a reset (persistent); only a reconfiguration clears it");
            stage(VALID7); arm; wait_gate; rd(16'h2004); check(last_rdata[2] == 0, "ARM under recovery is refused");
        end
        "fault_not_armed": begin provision(KEY_A); wr(16'h2000, 32'h200); wait_engine; expect_fault(5, "an engine op without ARM -> F_NOT_ARMED"); end
        "fault_nokey": begin stage(VALID1); arm; wait_gate; expect_fault(12, "unprovisioned -> F_ARM_NOKEY"); expect_nonce(N1, "nonce consumed"); end
        "fault_unsigned": begin provision(KEY_A); stage(UNSIGNED); arm; wait_gate; expect_fault(13, "unsigned -> F_ARM_AUTH"); end
        "fault_wrong_commit": begin provision(KEY_A); stage(WRONG_COMMIT); arm; wait_gate; expect_fault(13, "wrong commit -> F_ARM_AUTH"); end
        "fault_wrong_key": begin provision(KEY_B); stage(VALID1); arm; wait_gate; expect_fault(13, "wrong key -> F_ARM_AUTH"); end
        "fault_sequence": begin
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate;
            wr(16'h2038, {7'd0, FIX0_IN0}); wr(16'h2000, 32'h800); wait_engine; expect_fault(7, "STEP before the init event -> F_SEQUENCE");
        end
        "fault_double_arm": begin
            provision(KEY_A); stage(VALID1); arm; wait_gate; rd(16'h2004); check(last_rdata[2] == 1, "armed");
            stage(VALID2); arm; wait_gate; expect_fault(7, "ARM while armed -> F_SEQUENCE"); expect_nonce(N1, "the refused ARM does not consume the nonce");
        end
        "fault_realisable": begin
            // a non-uniform ce at the third step: F_NOT_REALISABLE, the acquired prefix retained (slots 0..3), step_index 2
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event;
            step(FIX0_IN0); step(FIX0_IN1);
            wr(16'h2038, 32'h0100_A5_00 | (32'h3C << 8)); wr(16'h2000, 32'h800); wait_engine;
            expect_fault(6, "a per-element ce vector that is not uniform -> F_NOT_REALISABLE");
            rd(16'h2004); check(last_rdata[25:21] == 2 && last_rdata[20:16] == 4, "the prefix retained: step_index 2, slot_count 4");
            slot(5'd0); slot(5'd1); slot(5'd2); slot_in(5'd0); slot_in(5'd1); slot_in(5'd2); slot_in(5'd3);
            fixture_expect(0, 2, q, m); expect_slot(5'd3, q, m, "the last acquired step is intact");
            slot_in(5'd3); check(last_rdata[24:0] == FIX0_IN1, "the applied inputs of the last acquired step are the accepted ones");
            mark("invalid_prefix_retained");
        end
        "a5": begin
            // J1: c observed and closed normally; J2: c-prime leaves every element opposite, inputs held, CLOSE_INJECTION;
            // J3: c again, ARM with the A5 context flag; the held inputs and the injected state recorded; cleared by the event
            provision(KEY_A); transaction(0, 1, "J1 c");
            mark("J2_begin"); target.genome = FIX0_GENOME; stage(VALID2); arm; wait_gate; pre_sample; slot(5'd0); slot_in(5'd0); init_event; slot(5'd1);
            step(25'h100FF00);               // clock 1, ce all (bits 15:8), sr 0, d 0x00: every element captures 0 (opposite of INIT 1)
            slot(5'd2); slot_in(5'd2);
            rd(16'h2010); check(last_rdata[7:0] == 8'h00, "c-prime left every element at 0");
            close_injection; rd(16'h2004); check(last_rdata[14] == 1 && last_rdata[12] == 0, "injection_open, not idle"); mark("J2_end");
            mark("J3_begin"); stage(VALID3); arm_a5; wait_gate;
            rd(16'h2004); check(last_rdata[2] == 1 && last_rdata[1] == 0 && last_rdata[14] == 1, "the A5-context ARM accepted; the witness still readable");
            pre_sample; rd(16'h2014); check(last_rdata[10] == 1 && last_rdata[8] == 1 && last_rdata[7:0] == 8'h00, "held inputs recorded: clock 1, ce 1, d 0");
            rd(16'h2020); check(last_rdata[25] == 1, "pre_context_a5 witness");
            slot(5'd0); check(last_rdata[7:0] == 8'h00, "the pre-init sample shows the injected state (the injection arrived)");
            slot_in(5'd0); check(last_rdata[24] == 1 && last_rdata[15:8] == 8'hFF && last_rdata[7:0] == 8'h00, "the applied-input record of the pre-init sample = the held inputs");
            init_event; slot(5'd1); check(last_rdata[7:0] == 8'hFF, "the init sample is INIT again: the injected state was cleared (A5 pass on this fabric)");
            rd(16'h2014); check(last_rdata[10:0] == 11'd0, "inputs 0 after the event");
            rd(16'h2020); check(last_rdata[27] == 1 && last_rdata[25] == 1, "pre_init_cleanup and pre_context_a5 witnesses");
            cleanup; slot(5'd2); slot_in(5'd2); restore_event; rd(16'h203C); check(last_rdata[7:0] == 8'hFF, "J3 base-state sample");
            close; rd(16'h2004); check(last_rdata[14] == 0 && last_rdata[12] == 1, "J3 closed normally: injection cleared, idle"); mark("J3_end");
        end
        "a5_wrong_context": begin
            // an ordinary ARM after an injection close, and an A5-context ARM with no injection open: both F_SEQUENCE
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event; step(25'h100FF00); close_injection;
            stage(VALID2); arm; wait_gate; expect_fault(7, "an ordinary ARM while an injection is open -> F_SEQUENCE");
        end
        "a5_flag_without_injection": begin
            provision(KEY_A); stage(VALID1); arm_a5; wait_gate; expect_fault(7, "the A5 flag with no injection open -> F_SEQUENCE");
        end
        "open_close_refused": begin
            // the owner's open-close reproduction, repaired: CLOSE before the restore event is F_SEQUENCE; idle stays 0 with held inputs
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event; step(25'h100FF00);
            rd(16'h2004); check(last_rdata[12] == 0, "not idle while armed with held inputs");
            close; expect_fault(7, "CLOSE without cleanup and restore -> F_SEQUENCE");
            rd(16'h2004); check(last_rdata[12] == 0 && last_rdata[14] == 0 && last_rdata[7] == 1, "not idle, no injection open, recovery required: nothing was closed");
            rd(16'h2014); check(last_rdata[10:0] != 11'd0, "the inputs are still held");
            stage(VALID2); arm; wait_gate; rd(16'h2004); check(last_rdata[2] == 0, "no further ARM under recovery");
        end
        "p9": begin
            // the owner's P9 reproduction, repaired: the current transaction raises its event on the restored base and samples it
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event;
            step(25'h100FF00); rd(16'h2010); check(last_rdata[7:0] == 8'h00, "captured zero"); cleanup;
            rd(16'h2010); check(last_rdata[7:0] == 8'h00, "the base configuration (the host rewrote it) still holds the captured zero before P9");
            close; expect_fault(7, "CLOSE before the restore event is refused");
        end
        "p9_ok": begin
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event;
            step(25'h100FF00); cleanup; rd(16'h2020); gsr_before = last_rdata;
            restore_event; rd(16'h2020); check(last_rdata[7:0] == gsr_before[7:0] + 8'd1, "a second event, in this transaction");
            rd(16'h203C); check(last_rdata[7:0] == 8'hFF, "the base-state sample = INIT: Q restored by the event on the base");
            rd(16'h2014); check(last_rdata[10:0] == 0, "inputs 0");
            wr(16'h2000, 32'h4000); wait_engine; expect_fault(7, "a third event in the same transaction is refused");
        end
        "busy_refused": begin
            // the owner's busy-CLOSE reproduction, repaired: a CTRL command while the engine is busy is SLVERR and changes nothing
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event;
            wr(16'h2038, 32'h0000FF5A); wr(16'h2000, 32'h800);          // a step: clock 0, ce all, d 0x5A — runs for SETTLE + HOLD + 3 cycles
            wr(16'h2000, 32'h2000); check(last_bresp == 2'b10, "CLOSE during an in-flight step is SLVERR");
            wr(16'h2000, 32'h800); check(last_bresp == 2'b10, "a second STEP during the step is SLVERR");
            wait_engine; rd(16'h2004); check(last_rdata[2] == 1 && last_rdata[1] == 0 && last_rdata[25:21] == 1, "still armed, no fault, exactly one step applied");
            rd(16'h2014); check(last_rdata[7:0] == 8'h5A && last_rdata[8] == 1 && last_rdata[10] == 0, "the step's inputs are what was accepted");
        end
        "step_atomic": begin
            // the owner's STEP snapshot reproduction, repaired: staging the next word during a step changes nothing of the step
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event;
            wr(16'h2038, 32'h0000FFA5); wr(16'h2000, 32'h800);          // clock 0, ce all, d 0xA5
            wr(16'h2038, 32'h01FF005A);                                  // the NEXT word staged while the step runs: clock 1, d 0x5A
            wait_engine;
            rd(16'h2014); check(last_rdata[7:0] == 8'hA5 && last_rdata[10] == 0, "applied: clock 0, d 0xA5 — the accepted command, not the staged word");
            rd(16'h2010); check(last_rdata[7:0] == 8'hFF, "no edge: Q holds INIT");
            slot_in(5'd2); check(last_rdata[24:0] == 25'h000FFA5, "the applied-input record = the accepted command");
            rd(16'h2038); check(last_rdata == 32'h01FF005A, "the staged word is intact for the next STEP");
        end
        "backpressure": begin
            // the owner's AXI backpressure reproduction, repaired: BREADY held low after INIT_REQ — the response is delivered
            // first, the event fires only after the bus is quiet, each exactly once
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample;
            @(negedge clk); bready = 0; awaddr = 16'h2000; wdata = 32'h400; awvalid = 1; wvalid = 1;
            while (!(awready && wready)) @(negedge clk);
            @(negedge clk); awvalid = 0; wvalid = 0;
            while (!bvalid) @(negedge clk);
            repeat (QUIET) @(negedge clk);
            check(bvalid == 1 && bready == 0, "the write response is still held for the master after the quiet window");
            check(gsr_drive == 0 && dut.engine.gsr_count == 0, "no event while the response is outstanding");
            bready = 1; @(negedge clk); @(negedge clk); bready = 1;
            repeat (QUIET) @(negedge clk); wait_engine;
            rd(16'h2020); check(last_rdata[7:0] == 1, "exactly one event, after the response was taken");
            rd(16'h2004); check(last_rdata[9] == 1, "init_done");
            mark("backpressure_done");
        end
        "read_at_launch": begin
            // a poll presented at every offset around the launch cycle: with the gate's masking it is held and served
            // after the event; an unmasked register file would accept it just before the GSR and lose it (the watchdog)
            provision(KEY_A); target.genome = FIX0_GENOME;
            for (k = 0; k < 6; k = k + 1) begin
                case (k) 0: p = VALID1; 1: p = VALID2; 2: p = VALID3; 3: p = VALID4; 4: p = VALID5; default: p = VALID6; endcase
                stage(p); arm; wait_gate; pre_sample;
                wr(16'h2000, 32'h400);
                repeat (ASSERT_DELAY - 2 + k) @(negedge clk);
                araddr = 16'h2004; arvalid = 1; while (!arready) @(negedge clk);
                @(negedge clk); arvalid = 0; while (!rvalid) @(negedge clk); last_rdata = rdata; @(negedge clk);
                wait_engine; rd(16'h2020); check(last_rdata[7:0] == 2 * k + 1, "one init event, the poll served");
                rd(16'h2004); check(last_rdata[9] == 1, "init_done");
                cleanup; restore_event; close;
            end
        end
        "session": begin
            // the zero-finding chain for the host: session open -> the init-only ROOT on genome 0 -> one candidate -> close.
            // The bench's fabric has no value before its first event (the model's null); here, as the vendor FDPEs do after
            // the configuration GSR, the fabric starts at its INIT values — the power-up state of a configured device, set
            // once on the fabric, never on a record.
            target.genome = FIX0_GENOME; target.q = 8'hFF;
            provision(KEY_A);
            mark("transaction_begin"); stage(VALID1); arm; wait_gate; rd(16'h2004); check(last_rdata[2] == 1, "root armed");
            rd(16'h2200); rd(16'h2028); rd(16'h2020);
            pre_sample; slot(5'd0); slot_in(5'd0); init_event;
            rd(16'h2004); rd(16'h2020); rd(16'h2014); slot(5'd1); slot_in(5'd1); rd(16'h2004);
            cleanup; rd(16'h2004); rd(16'h2014); slot(5'd2); slot_in(5'd2); rd(16'h2020);
            restore_event; rd(16'h2004); rd(16'h2020); rd(16'h203C); close; rd(16'h2004); check(last_rdata[12] == 1, "root closed, idle");
            mark("transaction_end");
            transaction(1, 1, "the candidate after the root");
        end
        "post_fault": begin
            // a complete observation, then CLOSE before cleanup / restore: the engine latches F_SEQUENCE after P6 — the host's O
            // is sealed at P6 unchanged and X is faulted, never a rewritten O
            provision(KEY_A); target.genome = FIX0_GENOME; target.q = 8'hFF;
            transaction(0, 1, "warm transaction");
            mark("transaction_begin"); fixture_genome(1, g); target.genome = g; stage(VALID2); arm; wait_gate;
            rd(16'h2200); rd(16'h2028); rd(16'h2020); pre_sample; slot(5'd0); slot_in(5'd0); init_event;
            rd(16'h2004); rd(16'h2020); rd(16'h2014); slot(5'd1); slot_in(5'd1);
            for (j = 0; j < FIX_STEPS; j = j + 1) begin fixture_inputs(1, j, s); step(s); slot(5'd2 + j); slot_in(5'd2 + j); end
            rd(16'h2004); mark("P6_sealed");
            close; expect_fault(7, "post-P6 CLOSE before restore is a sequence fault");
            rd(16'h2004); check(last_rdata[2] == 0 && last_rdata[12] == 0, "unclosed: recovery, not idle");
            mark("transaction_end");
        end
        "read_during_window": begin
            // a read presented while the window is open is stalled by the gate and served afterwards; nothing is lost
            provision(KEY_A); target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample;
            wr(16'h2000, 32'h400);
            @(negedge clk); araddr = 16'h2004; arvalid = 1;              // the poll, presented immediately
            while (!arready) @(negedge clk);
            @(negedge clk); arvalid = 0; while (!rvalid) @(negedge clk); last_rdata = rdata; @(negedge clk);
            check(last_rdata[9] == 1 || last_rdata[10] == 1, "the stalled read was served after the window with a coherent status");
            wait_engine; rd(16'h2020); check(last_rdata[7:0] == 1, "one event");
            rd(16'h2004); check(last_rdata[9] == 1 && last_rdata[11] == 1 && last_rdata[2] == 1, "init_done; key and armed persisted");
        end
        "a5_persist": begin
            // the same protocol on a fabric whose init event has no effect (the hypothesis swap init_no_effect): the data of an A5 FAIL
            provision(KEY_A); target.gsr_init_effect = 1'b0;
            target.genome = FIX0_GENOME; stage(VALID1); arm; wait_gate; pre_sample; init_event;
            step(25'h100FF00); rd(16'h2010); check(last_rdata[7:0] == 8'h00, "elements at 0"); close_injection;
            stage(VALID2); arm_a5; wait_gate; pre_sample; slot(5'd0); check(last_rdata[7:0] == 8'h00, "injected state at the boundary");
            init_event; slot(5'd1); check(last_rdata[7:0] == 8'h00, "the init sample still shows the injected state: persistence (A5 fail data)");
            rd(16'h2020); check(last_rdata[7:0] == 2, "the carrier DID raise the event twice: the persistence is the fabric's, not a missing event");
            cleanup; restore_event; close;
        end
        default: begin $display("FAIL: unknown scenario %0s", scenario); fails = fails + 1; end
        endcase
        $fdisplay(log_fd, "{\"fails\": %0d}", fails); $fclose(log_fd);
        if (fails == 0) $display("TB_PASS %0s", scenario); else $display("TB_FAIL %0s (%0d)", scenario, fails);
        $finish;
    end
endmodule
