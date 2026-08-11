// Scorer bench. The decisive case is the firewall one: a phenotype that matches the
// target on every TRAIN vector and on no holdout vector must score 40 in train mode and 0
// in holdout mode. A scorer that walked all 64 vectors in holdout mode — the first draft
// of this module did — scores 40 there too, while still looking like a holdout run.

`timescale 1ns/1ps
`default_nettype none

module tb_carrier_scorer;
    localparam integer LUTS  = 6;
    localparam integer TRAIN = 40;

    reg               clk = 1'b0;
    reg               rst_n = 1'b0;
    reg               arm = 1'b0;
    reg               configuration_valid = 1'b1;
    reg               recovery_required   = 1'b0;
    reg               done_before;
    reg               mode_holdout = 1'b0;
    wire [5:0]        vector;
    reg  [LUTS-1:0]   lut_q;
    wire              busy, done, armed;
    wire [LUTS*8-1:0] score_flat;

    integer errors = 0;
    integer i;

    // The bench's own copy of the constants, read from the same generated files.
    reg [5:0]  order  [0:63];
    reg [63:0] target [0:LUTS-1];
    reg [63:0] phenotype [0:LUTS-1];

    always #5 clk = ~clk;

    carrier_scorer #(.LUTS(LUTS), .VECTORS(64), .TRAIN_COUNT(TRAIN)) dut (
        .clk(clk), .rst_n(rst_n), .configuration_valid(configuration_valid),
        .recovery_required(recovery_required),
        .arm(arm), .mode_holdout(mode_holdout),
        .vector(vector), .lut_q(lut_q),
        .busy(busy), .done(done), .armed_o(armed), .score_flat(score_flat)
    );

    // Behavioural stand-ins for the six evolvable LUT6: a truth table indexed by vector.
    always @* for (i = 0; i < LUTS; i = i + 1) lut_q[i] = phenotype[i][vector];

    function [7:0] score_of(input integer index);
        score_of = score_flat[index*8 +: 8];
    endfunction

    task check(input [255:0] what, input integer got, input integer want);
        begin
            if (got !== want) begin
                $display("FAIL %0s: got %0d want %0d", what, got, want);
                errors = errors + 1;
            end
        end
    endtask

    task run(input holdout);
        begin
            @(negedge clk);
            cycles = 0;
            mode_holdout = holdout;
            arm = 1'b1;
            @(negedge clk);
            arm = 1'b0;
            wait (done);
            @(negedge clk);
        end
    endtask

    integer k;
    reg [LUTS*8-1:0] prev_score;
    integer cycles;            // cycles from arm to done, so the walk LENGTH is checked
    reg     busy_seen;         // sticky: catches a transient a periodic sample would miss

    always @(posedge clk) if (busy) busy_seen <= 1'b1;

    // count every cycle the scorer is busy, for the length assertion
    always @(posedge clk) if (busy) cycles <= cycles + 1;
    initial begin
        $readmemh("carrier_vector_order.hex", order);
        $readmemh("carrier_targets.hex", target);

        repeat (3) @(negedge clk);
        rst_n = 1'b1;

        // 1. a perfect phenotype scores the full slice in each mode
        for (i = 0; i < LUTS; i = i + 1) phenotype[i] = target[i];
        run(1'b0);
        for (i = 0; i < LUTS; i = i + 1) check("perfect train", score_of(i), TRAIN);
        check("train walks exactly TRAIN vectors", cycles, TRAIN);
        run(1'b1);
        for (i = 0; i < LUTS; i = i + 1) check("perfect holdout", score_of(i), 64 - TRAIN);
        // THE LENGTH is asserted, not only the score: a holdout walk that runs for 64
        // cycles is scoring a different set even when the total happens to match, because
        // an over-long walk reads past the slice and simply fails to accumulate there.
        check("holdout walks exactly the holdout slice", cycles, 64 - TRAIN);

        // 2. an inverted phenotype scores zero
        for (i = 0; i < LUTS; i = i + 1) phenotype[i] = ~target[i];
        run(1'b0);
        for (i = 0; i < LUTS; i = i + 1) check("inverted train", score_of(i), 0);

        // 3. THE FIREWALL: right on every train vector, wrong on every holdout vector.
        for (i = 0; i < LUTS; i = i + 1) phenotype[i] = ~target[i];
        for (k = 0; k < TRAIN; k = k + 1)
            for (i = 0; i < LUTS; i = i + 1)
                phenotype[i][order[k]] = target[i][order[k]];
        run(1'b0);
        for (i = 0; i < LUTS; i = i + 1) check("firewall train", score_of(i), TRAIN);
        run(1'b1);
        for (i = 0; i < LUTS; i = i + 1) check("firewall holdout", score_of(i), 0);

        // 4. and the converse, so the slices are not merely disjoint by luck
        for (i = 0; i < LUTS; i = i + 1) phenotype[i] = ~target[i];
        for (k = TRAIN; k < 64; k = k + 1)
            for (i = 0; i < LUTS; i = i + 1)
                phenotype[i][order[k]] = target[i][order[k]];
        run(1'b0);
        for (i = 0; i < LUTS; i = i + 1) check("converse train", score_of(i), 0);
        run(1'b1);
        for (i = 0; i < LUTS; i = i + 1) check("converse holdout", score_of(i), 64 - TRAIN);

        // 5. THE INTERLOCK is a one-shot: it disarms itself at `done`
        check("armed clears at done", armed, 0);
        check("busy clears at done", busy, 0);

        // running without a fresh arm must change nothing
        prev_score = score_flat;
        repeat (200) @(negedge clk);
        check("frozen without arm", score_flat === prev_score, 1);
        check("still not busy", busy, 0);

        // 6. fail-closed: reset leaves it frozen
        @(negedge clk); rst_n = 1'b0;
        @(negedge clk); rst_n = 1'b1;
        repeat (200) @(negedge clk);
        check("frozen after reset", busy, 0);
        check("disarmed after reset", armed, 0);
        for (i = 0; i < LUTS; i = i + 1) check("zeroed after reset", score_of(i), 0);

        // 7. THE SECOND CONDITION: an arm without readback confirmation does nothing.
        //    Without this the interlock only proves "no arm, no score", which still leaves
        //    the promise resting on the host calling things in the right order.
        configuration_valid = 1'b0;
        for (i = 0; i < LUTS; i = i + 1) phenotype[i] = target[i];
        busy_seen = 1'b0;
        @(negedge clk); arm = 1'b1; @(negedge clk); arm = 1'b0;
        repeat (200) @(negedge clk);
        // sticky, because an unconfirmed arm that starts and is frozen a cycle later is
        // still an arm that should never have been accepted — a periodic sample sees
        // nothing.
        check("never even started without configuration_valid", busy_seen, 0);
        check("no score without configuration_valid", busy, 0);
        check("not armed without configuration_valid", armed, 0);
        check("done stays low", done, 0);
        for (i = 0; i < LUTS; i = i + 1)
            check("score stays zero", score_of(i), 0);

        // 8. and confirmation WITHDRAWN mid-evaluation freezes without completing:
        //    a partial score must never present itself as a result.
        configuration_valid = 1'b1;
        @(negedge clk); arm = 1'b1; @(negedge clk); arm = 1'b0;
        repeat (5) @(negedge clk);
        check("running once confirmed", busy, 1);
        configuration_valid = 1'b0;
        @(negedge clk);
        check("frozen when confirmation withdrawn", busy, 0);
        check("disarmed when confirmation withdrawn", armed, 0);
        check("no done for a partial evaluation", done, 0);

        // and it recovers cleanly on the next confirmed arm
        configuration_valid = 1'b1;
        run(1'b0);
        for (i = 0; i < LUTS; i = i + 1) check("recovered train", score_of(i), TRAIN);

        // ---- recovery_required freezes the scorer, at arm and mid-evaluation.
        // Design §4 item 6: after a partial write what was already written may NEVER be
        // scored. configuration_valid does not carry that — a fault followed by a
        // complete, fully verified transaction raises it again — so the scorer has to
        // refuse on its own.
        configuration_valid = 1'b1; recovery_required = 1'b1;
        busy_seen = 0;
        // `done` is a level that survives the previous evaluation, so "did not rise" is
        // the property, not "is 0" — checking the latter would have been asserting the
        // history of the bench rather than the behaviour under test.
        done_before = done;
        @(negedge clk); arm = 1'b1; @(negedge clk); arm = 1'b0;
        repeat (200) begin @(negedge clk); if (busy) busy_seen = 1; end
        check("recovery_required: never started", busy_seen, 0);
        check("recovery_required: not armed", armed, 0);
        check("recovery_required withdraws a stale done", done, 0);

        // and it freezes an evaluation already in flight
        recovery_required = 1'b0;
        @(negedge clk); arm = 1'b1; @(negedge clk); arm = 1'b0;
        repeat (8) @(negedge clk);
        check("running before recovery is raised", busy, 1);
        @(negedge clk); recovery_required = 1'b1;
        repeat (4) @(negedge clk);
        check("recovery mid-evaluation freezes it", busy, 0);
        check("and disarms", armed, 0);
        check("and never raises done", done, 0);
        recovery_required = 1'b0;

        if (errors == 0) $display("SCORER TB: OK");
        else             $display("SCORER TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule

`default_nettype wire
