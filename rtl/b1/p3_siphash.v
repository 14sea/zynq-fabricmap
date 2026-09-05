// SipHash-2-4 with 128-bit output, sequential, one SipRound per clock.
//
// The verifier for `arm_mac` 1.0.0 (docs/contracts.md). The message is fixed-length:
// MSG_WORDS 32-bit words presented big-endian (the AXI staging order) plus a 64-bit
// nonce; it is consumed as 8-byte little-endian blocks exactly as the Python reference
// (`validators/siphash.py`) consumes the same byte stream, so the two agree by
// construction and the testbench proves it against vectors the reference generated.
//
// The key is a runtime input from the write-once, write-only key register (D4, option A);
// initial state of v0..v3. There is no port that carries it.
`default_nettype none
module p3_siphash #(
    parameter integer MSG_WORDS = 20          // 8 commit + 12 table words; the tag is not part of the message
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [127:0] key,                  // provisioned at runtime (write-once register); never a constant
    input  wire         start,                // one-shot; ignored while busy
    input  wire [MSG_WORDS*32-1:0] msg,       // word 0 in the top bits (big-endian stream)
    input  wire [63:0]  nonce,                // appended after msg, as 8 LE bytes
    output reg          busy,
    output reg          done,                 // one-cycle pulse; tag valid from then on
    output reg  [127:0] tag                   // {out0, out1}: out0 in [127:64]; each half is the
                                              // 64-bit integer whose LE bytes are the tag bytes
);
    localparam integer MSG_BYTES = MSG_WORDS*4 + 8;
    localparam integer BLOCKS    = MSG_BYTES / 8;     // full blocks; the tail block is separate
    localparam integer TAIL_LEN  = MSG_BYTES % 8;     // 0 here (88 bytes) — kept general

    // ---------------------------------------------------------------- byte stream
    // byte k of the stream, k = 0 .. MSG_BYTES-1
    function [7:0] stream_byte;
        input integer k;
        begin
            if (k < MSG_WORDS*4)
                stream_byte = msg[(MSG_WORDS*4 - 1 - k)*8 +: 8];         // big-endian words
            else
                stream_byte = nonce[(k - MSG_WORDS*4)*8 +: 8];           // nonce: byte 0 first
        end
    endfunction

    // 8-byte little-endian block j
    function [63:0] block;
        input integer j;
        integer b;
        begin
            block = 64'd0;
            for (b = 0; b < 8; b = b + 1)
                block[b*8 +: 8] = stream_byte(j*8 + b);
        end
    endfunction

    // ---------------------------------------------------------------- SipRound
    function [255:0] sipround;
        input [255:0] s;
        reg [63:0] v0, v1, v2, v3;
        begin
            {v0, v1, v2, v3} = s;
            v0 = v0 + v1; v1 = {v1[50:0], v1[63:51]}; v1 = v1 ^ v0; v0 = {v0[31:0], v0[63:32]};
            v2 = v2 + v3; v3 = {v3[47:0], v3[63:48]}; v3 = v3 ^ v2;
            v0 = v0 + v3; v3 = {v3[42:0], v3[63:43]}; v3 = v3 ^ v0;
            v2 = v2 + v1; v1 = {v1[46:0], v1[63:47]}; v1 = v1 ^ v2; v2 = {v2[31:0], v2[63:32]};
            sipround = {v0, v1, v2, v3};
        end
    endfunction

    wire [63:0] K0 = key[63:0];           // key bytes 0..7 as LE = low 64 bits of the register value
    wire [63:0] K1 = key[127:64];

    reg [255:0] v;
    reg [63:0]  m;
    reg [7:0]   blk;        // current block index
    reg [2:0]   rnd;        // round counter within a phase
    reg [2:0]   phase;      // 0 idle, 1 compress, 2 final0, 3 out0, 4 final1, 5 out1

    wire [63:0] v0 = v[255:192], v1 = v[191:128], v2 = v[127:64], v3 = v[63:0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0; done <= 1'b0; tag <= 128'd0; phase <= 3'd0; blk <= 8'd0; rnd <= 3'd0;
            v <= 256'd0; m <= 64'd0;
        end else begin
            done <= 1'b0;
            case (phase)
            3'd0: if (start && !busy) begin
                busy  <= 1'b1;
                v     <= {64'h736f6d6570736575 ^ K0, (64'h646f72616e646f6d ^ K1) ^ 64'hEE,
                          64'h6c7967656e657261 ^ K0, 64'h7465646279746573 ^ K1};
                blk   <= 8'd0; rnd <= 3'd0;
                m     <= block(0);
                phase <= 3'd1;
            end
            3'd1: begin
                // compress block `blk`: v3 ^= m; 2 rounds; v0 ^= m
                if (rnd == 3'd0) begin
                    v   <= sipround({v0, v1, v2, v3 ^ m});
                    rnd <= 3'd1;
                end else if (rnd == 3'd1) begin
                    v   <= sipround(v);
                    rnd <= 3'd2;
                end else begin
                    v   <= {v0 ^ m, v1, v2, v3};
                    rnd <= 3'd0;
                    if (blk == BLOCKS - 1) begin
                        // tail block: length byte in the top, no remaining bytes (TAIL_LEN 0)
                        m     <= {MSG_BYTES[7:0], 56'd0};
                        phase <= 3'd2;
                    end else begin
                        blk <= blk + 8'd1;
                        m   <= block(blk + 1);
                    end
                end
            end
            3'd2: begin
                // the tail block compresses like any other, then v2 ^= 0xEE and 4 rounds
                if (rnd == 3'd0) begin v <= sipround({v0, v1, v2, v3 ^ m}); rnd <= 3'd1; end
                else if (rnd == 3'd1) begin v <= sipround(v); rnd <= 3'd2; end
                else if (rnd == 3'd2) begin v <= {v0 ^ m, v1, v2 ^ 64'hEE, v3}; rnd <= 3'd3; end
                else if (rnd < 3'd7) begin v <= sipround(v); rnd <= rnd + 3'd1; end
                else begin
                    tag[127:64] <= v0 ^ v1 ^ v2 ^ v3;
                    v   <= {v0, v1 ^ 64'hDD, v2, v3};
                    rnd <= 3'd0;
                    phase <= 3'd3;
                end
            end
            3'd3: begin
                if (rnd < 3'd4) begin v <= sipround(v); rnd <= rnd + 3'd1; end
                else begin
                    tag[63:0] <= v0 ^ v1 ^ v2 ^ v3;
                    busy <= 1'b0; done <= 1'b1; phase <= 3'd0; rnd <= 3'd0;
                end
            end
            default: phase <= 3'd0;
            endcase
        end
    end
endmodule
`default_nettype wire
