// CRC bench. The known answers are not this module's own output: they are Python's
// `zlib.crc32` over the same bytes, so the host can use any ordinary CRC-32 implementation
// rather than one written to agree with this file. That is the whole point of specifying
// the polynomial, reflection and byte order instead of saying "we both compute CRC-32".
//
//   zlib.crc32(pack('<I', 0))              = 2144DF1C
//   zlib.crc32(pack('<I', 0x04030201))     = B63CFBCD
//   zlib.crc32(536 words of 0xA5A50000+i)  = D23C13F5

`timescale 1ns/1ps
module tb_crc;
    reg clk=0, rst_n=0, clear=0, valid=0; reg [31:0] data=0; wire [31:0] crc;
    wire ready, taken, idle; wire [15:0] byte_count;
    integer errors=0, i;
    always #5 clk=~clk;
    carrier_crc32 dut(.clk(clk),.rst_n(rst_n),.clear(clear),.valid(valid),.data(data),
                      .ready(ready),.taken(taken),.idle(idle),.byte_count(byte_count),
                      .crc(crc));
    // The transfer is the cycle where valid && ready. A producer that then held `data`
    // steady would hide a missing latch, and one that held `valid` steady would hide
    // double-consumption, so this one drops valid AND scribbles over the data the moment
    // the word is taken — the worst case the stream engine will actually present.
    task feed(input [31:0] w);
        begin
            @(negedge clk); data=w; valid=1;
            while (!ready) @(negedge clk);
            @(negedge clk); valid=0; data=32'hDEADBEEF;
            while (!idle) @(negedge clk);
        end
    endtask
    // back-to-back: valid never drops between words, which is how a paced AXI source
    // behaves and is exactly what re-consumed each word four cycles later.
    task feed_b2b(input [31:0] w);
        begin
            @(negedge clk); data=w; valid=1;
            while (!ready) @(negedge clk);
        end
    endtask
    task chk(input [255:0] what, input [31:0] got, input [31:0] want);
        begin if (got!==want) begin $display("FAIL %0s: got %08x want %08x", what, got, want); errors=errors+1; end end
    endtask
    initial begin
        repeat(3) @(negedge clk); rst_n=1;
        @(negedge clk); clear=1; @(negedge clk); clear=0;
        feed(32'h00000000);
        chk("crc of one zero word", crc, 32'h2144DF1C);
        @(negedge clk); clear=1; @(negedge clk); clear=0;
        feed(32'h04030201);   // bytes 01 02 03 04
        chk("crc of 01 02 03 04", crc, 32'hB63CFBCD);
        @(negedge clk); clear=1; @(negedge clk); clear=0;
        for (i=0;i<536;i=i+1) feed(32'hA5A50000+i);
        chk("crc of the 536-word pattern", crc, 32'hD23C13F5);
        // 536 words must be exactly 2144 byte handshakes; a 101-word frame is 404
        chk("byte_count for 536 words", byte_count, 536*4);
        // the same stream from a source that never deasserts valid must give the same
        // answer and the same count
        @(negedge clk); clear=1; @(negedge clk); clear=0;
        for (i=0;i<536;i=i+1) feed_b2b(32'hA5A50000+i);
        @(negedge clk); valid=0;
        while (!idle) @(negedge clk);
        chk("back-to-back crc of the 536-word pattern", crc, 32'hD23C13F5);
        chk("back-to-back byte_count", byte_count, 536*4);
        if (errors==0) $display("CRC TB: OK"); else $display("CRC TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule
