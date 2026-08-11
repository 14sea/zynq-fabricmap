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
// BYTE-SERIAL, with an ORDINARY AXI-STREAM HANDSHAKE. The transfer happens in the one
// cycle where `valid && ready`; the word is LATCHED there and the remaining three bytes are
// clocked out of the latch, so the producer is free to change `data` immediately — which it
// does, because `ready` is what its own counters advance on. `taken` pulses four cycles
// later and means only "the CRC has settled", never "consume another word": using it as the
// advance event double-consumed every word (byte_count came out at exactly 2x).
// The word-parallel version unrolled 32 XOR stages and cost 162 LUTs in a region that has
// 800 in total; the transfer is AXI-paced and cannot notice three extra cycles per word.
//
// WHY THE HANDSHAKE IS SHAPED THIS WAY. The first version exposed `ready` as a level and
// let each consumer advance its own counters from it. Three phases then kept three sets of
// counters against one byte stream, and they drifted: the readback CRC came out as though
// almost no bytes had been consumed. There is now ONE advance event, and `byte_count`
// makes a drift observable rather than merely wrong — a 101-word frame must produce
// exactly 404 byte handshakes.
//
// `crc` is only meaningful while `idle`. Reading it in the same cycle as the last `taken`
// reads a state that has not been updated yet, which is the same off-by-one in a
// different costume.

`default_nettype none

module carrier_crc32 (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        clear,       // start a new frame; also clears byte_count
    input  wire        valid,       // a whole word is offered
    input  wire [31:0] data,
    output wire        ready,       // valid && ready == the transfer; data is latched here
    output reg         taken,       // one pulse per word, four cycles later: CRC settled
    output wire        idle,        // `crc` is settled
    output reg  [15:0] byte_count,  // bytes consumed since `clear`
    output wire [31:0] crc
);
    reg [31:0] state;
    reg [31:0] wreg;      // the accepted word; `data` may change the very next cycle
    reg [1:0]  bidx;
    reg        active;

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
    // is not a specification, and the bench's known answers are Python's zlib over exactly
    // this order.
    wire [7:0] byte_of_index = (bidx == 2'd1) ? wreg[15:8]  :
                               (bidx == 2'd2) ? wreg[23:16] : wreg[31:24];

    // `clear` wins over `accept` inside the state update, so a word offered in the same
    // cycle as a clear would be counted by the consumer and dropped by the CRC. Withdrawing
    // `ready` for that cycle makes the two mutually exclusive at the interface instead of
    // relying on every caller to keep them apart. (The 404-byte assertion is what found it:
    // the frame came out at 400.)
    wire accept = valid && !active && !clear;

    assign ready = !active && !clear;
    assign idle  = !active;
    assign crc   = state ^ 32'hFFFFFFFF;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= 32'hFFFFFFFF; bidx <= 2'd0; active <= 1'b0; wreg <= 32'd0;
            taken <= 1'b0; byte_count <= 16'd0;
        end else begin
            taken <= 1'b0;
            if (clear) begin
                state <= 32'hFFFFFFFF; bidx <= 2'd0; active <= 1'b0; byte_count <= 16'd0;
            end else if (accept) begin
                wreg       <= data;
                state      <= crc_byte(state, data[7:0]);
                byte_count <= byte_count + 16'd1;
                bidx       <= 2'd1;
                active     <= 1'b1;
            end else if (active) begin
                state      <= crc_byte(state, byte_of_index);
                byte_count <= byte_count + 16'd1;
                if (bidx == 2'd3) begin
                    active <= 1'b0;
                    taken  <= 1'b1;      // "settled" — NOT an invitation to send more
                end else begin
                    bidx <= bidx + 2'd1;
                end
            end
        end
    end
endmodule

`default_nettype wire
