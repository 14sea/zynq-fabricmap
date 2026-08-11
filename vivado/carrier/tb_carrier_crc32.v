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
    reg clk=0, rst_n=0, clear=0, valid=0; reg [31:0] data=0; wire [31:0] crc; wire ready;
    integer errors=0, i;
    always #5 clk=~clk;
    carrier_crc32 dut(.clk(clk),.rst_n(rst_n),.clear(clear),.valid(valid),.data(data),
                      .ready(ready),.crc(crc));
    // byte-serial: hold the word until `ready`
    task feed(input [31:0] w);
        begin
            @(negedge clk); data=w; valid=1;
            while (!ready) @(negedge clk);
            @(negedge clk); valid=0;
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
        if (errors==0) $display("CRC TB: OK"); else $display("CRC TB: %0d FAILURE(S)", errors);
        $finish;
    end
endmodule
