`timescale 1ns/1ps

// The frozen known-answer phenotype against the REAL scorer RTL.  Python independently
// recomputes the same vectors, but this bench proves the register-visible counts are what
// carrier_scorer itself produces for candidate and restore in both modes.
module tb_claimb_known_answer;
    localparam integer LUTS = 6;
    reg clk = 0;
    always #10 clk = ~clk;

    reg rst_n = 0;
    reg configuration_valid = 1;
    reg recovery_required = 0;
    reg arm = 0;
    reg mode_holdout = 0;
    wire [5:0] vector;
    reg [63:0] phenotype [0:LUTS-1];
    reg [LUTS-1:0] lut_q;
    wire busy, done, armed_o;
    wire [LUTS*8-1:0] score_flat;
    integer i;
    integer failures = 0;

    always @* begin
        for (i = 0; i < LUTS; i = i + 1)
            lut_q[i] = phenotype[i][vector];
    end

    carrier_scorer #(.LUTS(LUTS), .VECTORS(64), .TRAIN_COUNT(40)) dut (
        .clk(clk), .rst_n(rst_n), .configuration_valid(configuration_valid),
        .recovery_required(recovery_required), .arm(arm),
        .mode_holdout(mode_holdout), .vector(vector), .lut_q(lut_q),
        .busy(busy), .done(done), .armed_o(armed_o), .score_flat(score_flat)
    );

    task check_scores;
        input [8*16-1:0] label;
        input integer s0, s1, s2, s3, s4, s5;
        integer want [0:LUTS-1];
        begin
            want[0]=s0; want[1]=s1; want[2]=s2;
            want[3]=s3; want[4]=s4; want[5]=s5;
            for (i = 0; i < LUTS; i = i + 1) begin
                if (score_flat[i*8 +: 8] !== want[i][7:0]) begin
                    $display("FAIL %0s LUT%0d got %0d expected %0d",
                             label, i, score_flat[i*8 +: 8], want[i]);
                    failures = failures + 1;
                end
            end
        end
    endtask

    task run_mode;
        input holdout;
        integer cycles;
        begin
            @(negedge clk); mode_holdout = holdout; arm = 1;
            @(negedge clk); arm = 0;
            cycles = 0;
            while (!done && cycles < 100) begin
                @(negedge clk); cycles = cycles + 1;
            end
            if (!done || busy || armed_o) begin
                $display("FAIL mode %0d did not finish one-shot", holdout);
                failures = failures + 1;
            end
        end
    endtask

    initial begin
        for (i = 0; i < LUTS; i = i + 1) phenotype[i] = 64'd0;
        phenotype[0] = 64'h50785CE844305DC4;
        repeat (3) @(negedge clk);
        rst_n = 1;

        run_mode(0);
        check_scores("candidate train", 35,22,20,20,20,18);
        run_mode(1);
        check_scores("candidate hold", 23,10,12,12,12,14);

        for (i = 0; i < LUTS; i = i + 1) phenotype[i] = 64'd0;
        run_mode(0);
        check_scores("restore train", 18,22,20,20,20,18);
        run_mode(1);
        check_scores("restore hold", 14,10,12,12,12,14);

        if (failures == 0)
            $display("KNOWN-ANSWER SCORER TB: OK");
        else
            $display("KNOWN-ANSWER SCORER TB: FAILURE (%0d)", failures);
        $finish;
    end
endmodule
