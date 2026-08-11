// CRC-32 over a word stream — the PL's own transmission-error check for the two-pass
// contract.
//
// WHAT THIS IS AND IS NOT
// -----------------------
// It is NOT the authority that pass 2's envelope is pass 1's envelope. SHA-256 is, and it
// is held host-side: the left-of-flush region has 800 LUTs, the logic already uses 432,
// and a hardware SHA-256 does not fit in what is left. That is an arithmetic constraint,
// so the fallback the ruling allows is taken and named rather than quietly substituted.
//
// What it IS: an independent check, computed in the fabric from the words that actually
// arrived, that pass 2 received the same 536 words pass 1 did. It catches transmission
// error, which is what the second transfer introduces. The word-by-word control-trace and
// FAR rules run in BOTH passes regardless, so a stream that is wrong in a way CRC-32 could
// miss still has to be wrong in a way that leaves every control word and every FAR intact.
//
// Standard CRC-32 (IEEE 802.3): polynomial 0x04C11DB7, reflected input and output, initial
// value 0xFFFFFFFF, final XOR 0xFFFFFFFF — so a host can reproduce it with any ordinary
// implementation rather than one written to match this file.
//
// BYTE-SERIAL. A word is consumed over four cycles, one byte at a time, and `ready` is low
// until they are done. The word-parallel version unrolled 32 XOR stages and cost 162 LUTs
// in a region that has 800 in total; the transfer is AXI-paced and cannot notice three
// extra cycles per word, so the area is worth more than the throughput.

`default_nettype none

module carrier_crc32 (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        clear,       // start a new frame
    input  wire        valid,       // present `data`; held until `ready`
    input  wire [31:0] data,
    output wire        ready,       // this word has been consumed
    output wire [31:0] crc
);
    reg [31:0] state;
    reg [1:0]  byte_index;
    reg        running;

    // one byte, LSB first (reflected input)
    function automatic [31:0] crc_byte(input [31:0] acc, input [7:0] byte_in);
        integer b;
        reg [31:0] c;
        begin
            c = acc ^ {24'd0, byte_in};
            for (b = 0; b < 8; b = b + 1) begin
                if (c[0]) c = (c >> 1) ^ 32'hEDB88320;   // reflected 0x04C11DB7
                else      c = (c >> 1);
            end
            crc_byte = c;
        end
    endfunction

    // A 32-bit word is consumed LITTLE-ENDIAN — bytes [7:0], [15:8], [23:16], [31:24] —
    // matching how the host serialises the stream. Stated because "we both compute CRC-32"
    // is not a specification, and the known answers in the bench are Python's zlib over
    // exactly this order.
    wire [7:0] this_byte = (byte_index == 2'd0) ? data[7:0]   :
                           (byte_index == 2'd1) ? data[15:8]  :
                           (byte_index == 2'd2) ? data[23:16] : data[31:24];

    assign ready = running && (byte_index == 2'd3);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= 32'hFFFFFFFF;
            byte_index <= 2'd0;
            running    <= 1'b0;
        end else if (clear) begin
            state      <= 32'hFFFFFFFF;
            byte_index <= 2'd0;
            running    <= 1'b0;
        end else if (valid) begin
            state      <= crc_byte(state, this_byte);
            byte_index <= byte_index + 2'd1;
            running    <= 1'b1;
        end else begin
            running    <= 1'b0;
        end
    end

    assign crc = state ^ 32'hFFFFFFFF;
endmodule

`default_nettype wire
