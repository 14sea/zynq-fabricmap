// Guard bench. The four ruled properties, each exercised by the wrong input rather than
// the right one — a guard that has only ever seen a clean run has not been shown to guard.
//
// The mock ICAP echoes back whatever was written, with an injectable corruption at a
// chosen (frame, word). That is enough to separate "compares the whole candidate" from
// "compares the part it happens to look at", including the flush frames, which are the
// case a design that treated them as collateral would let through.

`timescale 1ns/1ps
`default_nettype none

module tb_carrier_guard;
    localparam integer FRAME_WORDS = 101;
    localparam integer FRAMES      = 15;
    localparam integer TIMEOUT     = 4000;

    reg         clk = 1'b0;
    reg         rst_n = 1'b0;
    reg         start = 1'b0;
    wire        busy, fault, configuration_valid;
    wire [3:0]  fault_code;
    wire [11:0] buf_addr;
    reg  [31:0] buf_data;
    wire        icap_csib, icap_rdwrb;
    wire [31:0] icap_din;
    reg  [31:0] icap_dout;

    integer errors = 0;
    integer i;

    // the host-loaded candidate, and the mock device's memory
    reg [31:0] candidate [0:FRAMES*FRAME_WORDS-1];
    reg [31:0] device    [0:FRAMES*FRAME_WORDS-1];

    // injected corruption: -1 disables
    integer corrupt_at = -1;

    // sticky observation: configuration_valid must never be high while busy
    reg valid_while_busy = 1'b0;

    always #5 clk = ~clk;

    carrier_guard #(.FRAME_WORDS(FRAME_WORDS), .TIMEOUT(TIMEOUT)) dut (
        .clk(clk), .rst_n(rst_n), .start(start),
        .busy(busy), .fault(fault), .fault_code(fault_code),
        .configuration_valid(configuration_valid),
        .buf_addr(buf_addr), .buf_data(buf_data),
        .icap_csib(icap_csib), .icap_rdwrb(icap_rdwrb),
        .icap_din(icap_din), .icap_dout(icap_dout)
    );

    // the candidate buffer the guard reads
    always @* buf_data = candidate[buf_addr];

    // the mock device: writes land, reads come back (optionally corrupted)
    always @(posedge clk) begin
        if (!icap_csib && !icap_rdwrb) device[buf_addr] <= icap_din;
    end
    always @* begin
        icap_dout = device[buf_addr];
        if (corrupt_at >= 0 && buf_addr == corrupt_at) icap_dout = ~device[buf_addr];
    end

    always @(posedge clk) if (busy && configuration_valid) valid_while_busy <= 1'b1;

    task check(input [255:0] what, input integer got, input integer want);
        begin
            if (got !== want) begin
                $display("FAIL %0s: got %0d want %0d", what, got, want);
                errors = errors + 1;
            end
        end
    endtask

    task run;
        begin
            @(negedge clk); start = 1'b1;
            @(negedge clk); start = 1'b0;
            wait (!busy);
            @(negedge clk);
        end
    endtask

    initial begin
        for (i = 0; i < FRAMES*FRAME_WORDS; i = i + 1) begin
            candidate[i] = 32'hA5A50000 + i;
            device[i]    = 32'h00000000;
        end

        repeat (3) @(negedge clk);
        rst_n = 1'b1;

        // fail-closed before anything has run
        check("clear out of reset", configuration_valid, 0);

        // 1. a clean write + readback confirms
        run();
        check("confirmed after a clean run", configuration_valid, 1);
        check("no fault", fault, 0);
        check("never valid while busy", valid_while_busy, 0);

        // 2. RULE 2 — accepting a command clears it BEFORE any ICAP word goes out
        @(negedge clk); start = 1'b1;
        @(negedge clk);
        check("cleared the cycle the command is accepted", configuration_valid, 0);
        start = 1'b0;
        wait (!busy); @(negedge clk);
        check("re-confirmed after that run", configuration_valid, 1);

        // 3. a corrupted TARGET frame word leaves it clear
        corrupt_at = 2*FRAME_WORDS + 17;      // frame 2 is a target
        run();
        check("target mismatch refuses", configuration_valid, 0);
        check("fault raised", fault, 1);
        check("fault code is readback", fault_code, 2);

        // recover
        corrupt_at = -1;
        run();
        check("recovers after a clean run", configuration_valid, 1);

        // 4. a corrupted FLUSH frame word leaves it clear too. Frame 4 is envelope 0's
        //    flush (0x00400A80). A guard that treated flush frames as collateral — they
        //    are written back verbatim, after all — would confirm here.
        corrupt_at = 4*FRAME_WORDS + 3;
        run();
        check("flush mismatch refuses", configuration_valid, 0);
        corrupt_at = -1;

        // 5. the LAST word of the LAST frame: a comparison that stops early confirms here
        run();
        check("clean again", configuration_valid, 1);
        corrupt_at = (FRAMES-1)*FRAME_WORDS + (FRAME_WORDS-1);
        run();
        check("last word of last frame refuses", configuration_valid, 0);
        corrupt_at = -1;

        // 6. reset while confirmed drops it
        run();
        check("confirmed", configuration_valid, 1);
        @(negedge clk); rst_n = 1'b0;
        @(negedge clk);
        check("reset clears confirmation", configuration_valid, 0);
        @(negedge clk); rst_n = 1'b1;
        repeat (5) @(negedge clk);
        check("stays clear after reset", configuration_valid, 0);

        // 7. the allowlist: exactly the fifteen FARs, and nothing adjacent
        check("A20 permitted",  dut.is_permitted(32'h00400A20), 1);
        check("A80 permitted",  dut.is_permitted(32'h00400A80), 1);
        check("C1E permitted",  dut.is_permitted(32'h00400C1E), 1);
        check("C80 permitted",  dut.is_permitted(32'h00400C80), 1);
        check("A24 refused",    dut.is_permitted(32'h00400A24), 0);  // does not exist
        check("A1F refused",    dut.is_permitted(32'h00400A1F), 0);  // adjacent, in column
        check("C1F refused",    dut.is_permitted(32'h00400C1F), 0);  // adjacent, in column
        check("C24 refused",    dut.is_permitted(32'h00400C24), 0);
        check("zero refused",   dut.is_permitted(32'h00000000), 0);
        check("all-ones refused", dut.is_permitted(32'hFFFFFFFF), 0);

        // and the flush classification, because a target treated as flush would be
        // written from candidate content
        check("frame 4 is flush",   dut.is_flush(4'd4), 1);
        check("frame 9 is flush",   dut.is_flush(4'd9), 1);
        check("frame 14 is flush",  dut.is_flush(4'd14), 1);
        check("frame 0 is target",  dut.is_flush(4'd0), 0);
        check("frame 13 is target", dut.is_flush(4'd13), 0);

        // The table's out-of-range answer, tested directly. `is_permitted` only ever
        // indexes 0..14, so the default arm is unreachable through it — an unexercised
        // rule, which mutation testing duly showed could be changed to a REAL frame
        // address without any test noticing. Asked of `far_of` directly it has teeth.
        check("index 15 is the never-permitted sentinel", dut.far_of(4'd15), 32'hFFFFFFFF);
        check("the sentinel itself is not permitted", dut.is_permitted(32'hFFFFFFFF), 0);
        for (i = 0; i < 15; i = i + 1)
            check("every listed FAR is permitted", dut.is_permitted(dut.far_of(i[3:0])), 1);

        if (errors == 0) $display("GUARD TB: OK");
        else             $display("GUARD TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule

`default_nettype wire
