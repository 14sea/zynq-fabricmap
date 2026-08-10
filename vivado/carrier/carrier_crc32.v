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

`default_nettype none

module carrier_crc32 (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        clear,       // start a new envelope
    input  wire        valid,       // consume `data` this cycle
    input  wire [31:0] data,
    output wire [31:0] crc
);
    reg [31:0] state;

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

    // A 32-bit word is consumed little-endian, matching how the host serialises the
    // stream; the envelope words themselves are big-endian on the wire, and the host's
    // reference implementation must use the same order. Stated here because "we both
    // compute CRC-32" is not a specification.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)      state <= 32'hFFFFFFFF;
        else if (clear)  state <= 32'hFFFFFFFF;
        else if (valid)  state <= crc_byte(crc_byte(crc_byte(crc_byte(
                                     state, data[7:0]), data[15:8]), data[23:16]),
                                     data[31:24]);
    end

    assign crc = state ^ 32'hFFFFFFFF;
endmodule

`default_nettype wire
