`timescale 1ns/1ps
// B1 carrier bench: AXI-Lite master -> b1_core (register file + the B1 gate + scorer) with six
// LUT6 models whose INITs only the bench knows. The instrument's tb_p3_core scenarios that
// still apply are re-run (alive, SLVERR on undecoded, write-once key, no-key fault, replay,
// unsigned, wrong commit, wrong key, reset clears the key), and the B1 contract's own:
//   * a correctly signed payload with ZERO tables ARMs, and the readout equals the bench's
//     fabric — tables that nothing in the payload named;
//   * the scorer still runs on the latch (counters are observations);
//   * tables_match is an observation only: a signed payload with non-zero (attested) tables
//     ARMs as well (the fabric is indifferent; the host validator refuses such a reply);
//   * VARIANT reads the B1 word; the instrument's eight stable words keep their offsets.
module tb_b1_core;
    `include "b1_fixture.vh"
    reg clk = 0; always #10 clk = ~clk;
    reg rst_n = 0;
    reg [15:0] awaddr = 0, araddr = 0; reg awvalid = 0, wvalid = 0, bready = 1, arvalid = 0, rready = 1;
    reg [31:0] wdata = 0; wire awready, wready, bvalid, arready, rvalid; wire [1:0] bresp, rresp; wire [31:0] rdata;
    wire [5:0] vector; wire [5:0] lut_q;
    reg [63:0] init0, init1, init2, init3, init4, init5;
    assign lut_q = {init5[vector], init4[vector], init3[vector], init2[vector], init1[vector], init0[vector]};

    b1_core #(.NONCE_SEED(SEED), .SEMANTIC_GATE(0)) dut (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(awaddr), .s_awvalid(awvalid), .s_awready(awready),
        .s_wdata(wdata), .s_wstrb(4'hF), .s_wvalid(wvalid), .s_wready(wready),
        .s_bresp(bresp), .s_bvalid(bvalid), .s_bready(bready),
        .s_araddr(araddr), .s_arvalid(arvalid), .s_arready(arready),
        .s_rdata(rdata), .s_rresp(rresp), .s_rvalid(rvalid), .s_rready(rready),
        .vector(vector), .lut_q(lut_q));

    integer fails = 0;
    reg [1:0] last_bresp, last_rresp; reg [31:0] last_rdata;
    task check(input cond, input [255:0] what); begin
        if (!cond) begin fails = fails + 1; $display("FAIL: %0s   [rdata=%h rresp=%b bresp=%b t=%0t]", what, last_rdata, last_rresp, last_bresp, $time); end
    end endtask
    task wr(input [15:0] a, input [31:0] d); begin
        @(negedge clk); awaddr = a; wdata = d; awvalid = 1; wvalid = 1;
        while (!(awready && wready)) @(negedge clk);
        @(negedge clk); awvalid = 0; wvalid = 0;
        while (!bvalid) @(negedge clk);
        last_bresp = bresp; @(negedge clk);
    end endtask
    task rd(input [15:0] a); begin
        @(negedge clk); araddr = a; arvalid = 1;
        while (!arready) @(negedge clk);
        @(negedge clk); arvalid = 0;
        while (!rvalid) @(negedge clk);
        last_rdata = rdata; last_rresp = rresp; @(negedge clk);
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
    task wait_scorer; begin rd(16'h2004); while (last_rdata[3]) rd(16'h2004); end endtask
    task reset; begin
        @(negedge clk); awvalid = 0; wvalid = 0; arvalid = 0;
        rst_n = 0; repeat (3) @(negedge clk); rst_n = 1; repeat (2) @(negedge clk);
    end endtask
    task expect_nonce(input [63:0] n, input [255:0] what); begin
        rd(16'h202C); check(last_rdata == n[31:0], what); rd(16'h2030); check(last_rdata == n[63:32], what);
    end endtask
    task expect_status(input v, input f, input tagok, input rec, input [3:0] fcode, input [255:0] what); begin
        rd(16'h2004);
        check(last_rdata[2] == v && last_rdata[1] == f && last_rdata[6] == tagok && last_rdata[7] == rec
              && last_rdata[8] == 1'b1 && last_rdata[31:27] == 0, what);
        rd(16'h2008); check(last_rdata[3:0] == fcode, what);
    end endtask
    // the readout must equal the bench's fabric, table t at words 2t (hi) / 2t+1 (lo)
    task expect_readout(input [63:0] t0, input [63:0] t1, input [63:0] t2, input [63:0] t3, input [63:0] t4, input [63:0] t5, input [255:0] what); begin
        rd(16'h2240); check(last_rdata == t0[63:32], what); rd(16'h2244); check(last_rdata == t0[31:0], what);
        rd(16'h2248); check(last_rdata == t1[63:32], what); rd(16'h224C); check(last_rdata == t1[31:0], what);
        rd(16'h2250); check(last_rdata == t2[63:32], what); rd(16'h2254); check(last_rdata == t2[31:0], what);
        rd(16'h2258); check(last_rdata == t3[63:32], what); rd(16'h225C); check(last_rdata == t3[31:0], what);
        rd(16'h2260); check(last_rdata == t4[63:32], what); rd(16'h2264); check(last_rdata == t4[31:0], what);
        rd(16'h2268); check(last_rdata == t5[63:32], what); rd(16'h226C); check(last_rdata == t5[31:0], what);
    end endtask
    integer i; reg [31:0] hb0;
    initial begin
        init0 = INIT0; init1 = INIT1; init2 = INIT2; init3 = INIT3; init4 = INIT4; init5 = INIT5;
        reset;
        rd(16'h2004); check(last_rdata != 0 && last_rdata[8] == 1, "alive bit");
        rd(16'h2028); hb0 = last_rdata; rd(16'h2028); check(last_rdata > hb0, "heartbeat advances");
        rd(16'h200C); check(last_rresp == 2'b10, "undecoded read is SLVERR");
        rd(16'h2100); check(last_rresp == 2'b10, "staging is write-only");
        wr(16'h2010, 32'h1); check(last_bresp == 2'b10, "score regs not writable");
        rd(16'h2034); check(last_rresp == 2'b00 && last_rdata == 32'h42310001, "VARIANT reads the B1 word");
        wr(16'h2034, 32'h1); check(last_bresp == 2'b10, "VARIANT is not writable");
        expect_nonce(N0, "nonce = seed after reset");
        // 0. unprovisioned ARM -> F_ARM_NOKEY
        rd(16'h2004); check(last_rdata[11] == 0, "key_loaded = 0 after reset");
        stage(VALID1); arm; wait_gate; expect_status(0, 1, 0, 1, 12, "unprovisioned -> F_ARM_NOKEY");
        expect_nonce(N1, "nonce consumed by the unprovisioned attempt");
        reset; provision(KEY_A);
        rd(16'h2004); check(last_rdata[11] == 1, "key_loaded after commit");
        wr(16'h2160, 32'hDEADBEEF); check(last_bresp == 2'b10, "key is write-once");
        rd(16'h2160); check(last_rresp == 2'b10, "key words not readable");
        // 1. B1 contract: VALID1 (zero tables) ARMs; the readout is the FABRIC, which no payload named
        stage(VALID1); arm; wait_gate; expect_status(1, 0, 1, 0, 0, "VALID1 (zero tables) armed under B1");
        rd(16'h2004); check(last_rdata[10] == 0, "tables_match = 0 is an observation, not a fault");
        rd(16'h2200); check(last_rdata == C1[255:224], "hw_commit = C1");
        expect_readout(INIT0, INIT1, INIT2, INIT3, INIT4, INIT5, "readout = the bench's fabric");
        wait_scorer; rd(16'h2004); check(last_rdata[4] == 1, "scorer done (counters are observations)");
        expect_nonce(N1, "nonce stepped after VALID1");
        // 2. replay -> F_ARM_AUTH; 3. ARM after fault refused
        stage(VALID1); arm; wait_gate; expect_status(0, 1, 0, 1, 13, "replay -> F_ARM_AUTH");
        stage(VALID2); arm; wait_gate; expect_status(0, 1, 0, 1, 13, "ARM after fault refused");
        expect_nonce(N2, "nonce not consumed by a refused ARM");
        // 4. VALID1 then VALID2 on the stepped nonce; a changed fabric shows in the readout, never a fault
        reset; provision(KEY_A); stage(VALID1); arm; wait_gate; wait_scorer; expect_status(1, 0, 1, 0, 0, "VALID1 again");
        init0 = INIT0 ^ 64'h4;
        stage(VALID2); arm; wait_gate; expect_status(1, 0, 1, 0, 0, "VALID2 armed with a changed fabric (no F_ARM_TABLE under B1)");
        rd(16'h2200); check(last_rdata == C2[255:224], "hw_commit = C2");
        expect_readout(INIT0 ^ 64'h4, INIT1, INIT2, INIT3, INIT4, INIT5, "readout follows the fabric change");
        wait_scorer; init0 = INIT0;
        // 5. UNSIGNED / 6. WRONG_COMMIT -> AUTH
        reset; provision(KEY_A); stage(UNSIGNED); arm; wait_gate; expect_status(0, 1, 0, 1, 13, "unsigned -> F_ARM_AUTH");
        reset; provision(KEY_A); stage(WRONG_COMMIT); arm; wait_gate; expect_status(0, 1, 0, 1, 13, "wrong commit -> F_ARM_AUTH");
        // 7. ATTESTED: signed with non-zero tables — the fabric is indifferent (tables_match observed 1), the HOST refuses
        reset; provision(KEY_A); stage(ATTESTED); arm; wait_gate; expect_status(1, 0, 1, 0, 0, "attested tables still ARM (the contract is enforced at the host)");
        rd(16'h2004); check(last_rdata[10] == 1, "tables_match observed = 1 when the attested tables happen to equal the fabric");
        wait_scorer;
        // 8. wrong key -> AUTH; 9. reset clears key_loaded
        reset; provision(KEY_B); stage(VALID1); arm; wait_gate; expect_status(0, 1, 0, 1, 13, "wrong key -> F_ARM_AUTH");
        reset; rd(16'h2004); check(last_rdata[11] == 0, "key_loaded cleared by reset");
        if (fails == 0) $display("TB_PASS"); else $display("TB_FAIL (%0d)", fails);
        $finish;
    end
endmodule
