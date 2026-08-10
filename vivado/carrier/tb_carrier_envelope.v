// Envelope validator bench. Built from the SAME literal envelope the host emits, then
// corrupted one word at a time — the host's review v1 and v2 findings replayed against
// the fabric-side validator, because the point of having two is that neither is trusted
// to agree with itself.

`timescale 1ns/1ps
`default_nettype none

module tb_carrier_envelope;
    localparam integer ENVELOPES = 3;
    localparam integer ENV_WORDS = 536;
    localparam integer TOTAL     = ENVELOPES * ENV_WORDS;

    reg         clk = 1'b0;
    reg         rst_n = 1'b0;
    reg         start = 1'b0;
    reg  [11:0] loaded_words = TOTAL;
    wire [11:0] buf_addr;
    reg  [31:0] buf_data;
    wire        busy, ok, fault;
    wire [3:0]  fault_code;
    wire [11:0] fault_word;

    integer errors = 0;
    integer i, e;

    reg [31:0] buffer [0:TOTAL-1];
    reg [31:0] golden [0:TOTAL-1];

    always #5 clk = ~clk;

    carrier_envelope dut (
        .clk(clk), .rst_n(rst_n), .start(start), .loaded_words(loaded_words),
        .buf_addr(buf_addr), .buf_data(buf_data),
        .busy(busy), .ok(ok), .fault(fault),
        .fault_code(fault_code), .fault_word(fault_word)
    );

    // SYNCHRONOUS, matching the AXI slave's BRAM read: the datum belongs to the address
    // presented on the previous cycle. A combinational model here would let a validator
    // with the off-by-one bug pass the bench and fail on hardware.
    always @(posedge clk) buf_data <= buffer[buf_addr];

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

    // one corrupted word, run, expect a refusal with the given code, then restore
    task expect_refusal(input [255:0] what, input integer at, input [31:0] value,
                        input [3:0] code);
        reg [31:0] saved;
        begin
            saved = buffer[at];
            buffer[at] = value;
            run();
            check(what, ok, 0);
            check({what, " code"}, fault_code, code);
            check({what, " position"}, fault_word, at);
            buffer[at] = saved;
        end
    endtask

    localparam [31:0] FAR0 = 32'h00400A20, FAR1 = 32'h00400C1A, FAR2 = 32'h00400C20;

    task build_envelope(input integer base, input [31:0] far);
        begin
            for (i = 0; i < 8; i = i + 1) buffer[base+i] = 32'hFFFFFFFF;
            buffer[base+8]  = 32'hAA995566;
            buffer[base+9]  = 32'h20000000;
            buffer[base+10] = 32'h30008001;
            buffer[base+11] = 32'h00000007;   // RCRC
            buffer[base+12] = 32'h20000000;
            buffer[base+13] = 32'h20000000;
            buffer[base+14] = 32'h30018001;
            buffer[base+15] = 32'h13722093;   // IDCODE
            buffer[base+16] = 32'h30008001;
            buffer[base+17] = 32'h00000001;   // WCFG
            buffer[base+18] = 32'h20000000;
            buffer[base+19] = 32'h30002001;
            buffer[base+20] = far;
            buffer[base+21] = 32'h30004000;
            buffer[base+22] = 32'h400001F9;   // type 2, 505 words
            for (i = 0; i < 505; i = i + 1) buffer[base+23+i] = 32'hC0DE0000 + base + i;
            buffer[base+528] = 32'h30000001;
            buffer[base+529] = 32'h00000000;  // CRC = 0
            buffer[base+530] = 32'h30008001;
            buffer[base+531] = 32'h0000000D;  // DESYNC
            for (i = 0; i < 4; i = i + 1) buffer[base+532+i] = 32'h20000000;
        end
    endtask

    initial begin
        build_envelope(0*ENV_WORDS, FAR0);
        build_envelope(1*ENV_WORDS, FAR1);
        build_envelope(2*ENV_WORDS, FAR2);
        for (i = 0; i < TOTAL; i = i + 1) golden[i] = buffer[i];

        repeat (3) @(negedge clk);
        rst_n = 1'b1;

        // 0. the untouched stream validates — without this every case below could pass
        //    for the wrong reason
        run();
        check("clean stream validates", ok, 1);
        check("no fault", fault, 0);

        // 1. RULE 1 — an OMISSION. Review v1's finding: removing WCFG left the host gate
        //    with zero findings, because membership cannot see what is not there. Here
        //    the word at WCFG's position is simply not WCFG.
        expect_refusal("WCFG removed",    16 + 1, 32'h20000000, 4'd1);
        expect_refusal("RCRC removed",    10 + 1, 32'h20000000, 4'd1);
        expect_refusal("DESYNC removed", 530 + 1, 32'h20000000, 4'd1);

        // 2. a WRONG VALUE that is still a plausible packet: review v1's non-zero CRC
        expect_refusal("CRC write non-zero", 529, 32'h12345678, 4'd1);

        // 3. an EXTRA write where a noop belongs, and a reorder
        expect_refusal("extra write in the tail", 533, 32'h30000001, 4'd1);
        expect_refusal("sync missing",              8, 32'h20000000, 4'd1);
        expect_refusal("IDCODE wrong",             15, 32'h0362D093, 4'd1);

        // 4. RULE 2 — the declared length. A type-2 count that is not the pinned payload
        //    length is a fault of its own kind, before any payload word is read.
        expect_refusal("declared length too short", 22, 32'h400001F8, 4'd3);
        expect_refusal("declared length too long",  22, 32'h400001FA, 4'd3);

        // 5. RULE 3 — the FAR comes from the STREAM. Every one of these is a real frame
        //    address that the compiled-in list does not permit for this envelope.
        expect_refusal("envelope 0 addressing a flush frame",  20, 32'h00400A80, 4'd2);
        expect_refusal("envelope 0 addressing envelope 1",     20, 32'h00400C1A, 4'd2);
        expect_refusal("envelope 0 addressing a neighbour",    20, 32'h00400A1F, 4'd2);
        expect_refusal("envelope 1 addressing envelope 0",
                       ENV_WORDS + 20, 32'h00400A20, 4'd2);
        expect_refusal("envelope 2 addressing envelope 1",
                       2*ENV_WORDS + 20, 32'h00400C1A, 4'd2);
        // a routing-class frame, the case the guard exists for
        expect_refusal("a frame outside the class entirely",
                       2*ENV_WORDS + 20, 32'h00000000, 4'd2);

        // 6. RULE 2 — a short load. The buffer does not hold what the envelopes declare.
        loaded_words = TOTAL - 1;
        run();
        check("short load refuses", ok, 0);
        check("short load code", fault_code, 4'd4);
        loaded_words = TOTAL;
        run();
        check("recovers on a full load", ok, 1);

        // 7. the LAST word of the LAST envelope: a walk that stops early accepts here
        expect_refusal("last word of the last envelope",
                       TOTAL - 1, 32'h30000001, 4'd1);

        // 8. and a corrupted PAYLOAD word is NOT a control fault — the payload is the
        //    candidate, and judging its content is the readback compare's job, not this
        //    module's. Without this the validator could be over-tight in a way that
        //    rejects legitimate candidates.
        buffer[100] = 32'hDEADBEEF;
        run();
        check("payload content is not a control fault", ok, 1);
        buffer[100] = golden[100];

        // 8b. the permitted-FAR table asked directly, including the index the FSM never
        //     reaches. Mutation testing showed the default arm is dead code from inside
        //     the walk — an extra case could be added there and nothing would notice.
        check("envelope 0 permits A20", dut.permitted_far(2'd0), 32'h00400A20);
        check("envelope 1 permits C1A", dut.permitted_far(2'd1), 32'h00400C1A);
        check("envelope 2 permits C20", dut.permitted_far(2'd2), 32'h00400C20);
        check("index 3 is the never-permitted sentinel",
              dut.permitted_far(2'd3), 32'hFFFFFFFF);
        // and the three permitted FARs are distinct, so no two envelopes share one
        check("permitted FARs are distinct 0/1",
              dut.permitted_far(2'd0) != dut.permitted_far(2'd1), 1);
        check("permitted FARs are distinct 1/2",
              dut.permitted_far(2'd1) != dut.permitted_far(2'd2), 1);
        check("permitted FARs are distinct 0/2",
              dut.permitted_far(2'd0) != dut.permitted_far(2'd2), 1);

        // 9. reset leaves it not-ok
        @(negedge clk); rst_n = 1'b0;
        @(negedge clk);
        check("reset clears ok", ok, 0);
        @(negedge clk); rst_n = 1'b1;

        if (errors == 0) $display("ENVELOPE TB: OK");
        else             $display("ENVELOPE TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule

`default_nettype wire
