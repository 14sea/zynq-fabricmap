// Claim B round 1 carrier — AXI4-Lite slave: the candidate buffer and the register file.
//
// Two windows off one GP0 slave:
//   0x0000 .. 0x191F   candidate buffer, 1608 words (three 536-word envelopes)
//   0x2000 ..          registers
//
// Register map. Every bit software can write is listed; everything else is read-only, and
// `STATUS` in particular has no write path at all — `configuration_valid` reaches software
// only as something to read.
//
//   0x2000  CTRL      W: bit0 load_done (latch loaded_words), bit1 go (validate+write+
//                        readback), bit2 arm (one evaluation), bit3 mode_holdout
//   0x2004  STATUS    R: bit0 guard_busy, bit1 guard_fault, bit2 configuration_valid,
//                        bit3 scorer_busy, bit4 scorer_done, bit5 scorer_armed
//   0x2008  FAULT     R: bits3:0 guard fault code, bits27:16 fault word index
//   0x200C  LOADED    R: words the host has written into the buffer since reset
//   0x2010  SCORE0..  R: six per-LUT match counts, one per register
//
// `configuration_valid` is READ-ONLY BY CONSTRUCTION: it is an input to this module and
// appears only in the STATUS read multiplexer. There is no address that writes it, which
// is the first of the four properties ruled for the guard — a register file that offered
// one would make the whole interlock a formality.

`default_nettype none

module carrier_axil #(
    parameter integer BUF_WORDS = 1608,
    parameter integer LUTS      = 6
) (
    input  wire        clk,
    input  wire        rst_n,

    // AXI4-Lite (32-bit)
    input  wire [15:0] s_awaddr,
    input  wire        s_awvalid,
    output wire        s_awready,
    input  wire [31:0] s_wdata,
    input  wire [3:0]  s_wstrb,
    input  wire        s_wvalid,
    output wire        s_wready,
    output reg  [1:0]  s_bresp,
    output reg         s_bvalid,
    input  wire        s_bready,
    input  wire [15:0] s_araddr,
    input  wire        s_arvalid,
    output wire        s_arready,
    output reg  [31:0] s_rdata,
    output reg  [1:0]  s_rresp,
    output reg         s_rvalid,
    input  wire        s_rready,

    // candidate buffer, read side (to the validator and the guard)
    input  wire [11:0] buf_raddr,
    output reg  [31:0] buf_rdata,   // combinational; see the note at the read port
    output reg  [11:0] loaded_words,

    // control pulses
    output reg         ctrl_go,
    output reg         ctrl_arm,
    output reg         ctrl_mode_holdout,

    // status in
    input  wire        guard_busy,
    input  wire        guard_fault,
    input  wire [3:0]  guard_fault_code,
    input  wire [11:0] guard_fault_word,
    input  wire        configuration_valid,
    input  wire        scorer_busy,
    input  wire        scorer_done,
    input  wire        scorer_armed,
    input  wire [LUTS*8-1:0] score_flat
);
    localparam [15:0] REG_BASE = 16'h2000;

    // DISTRIBUTED, explicitly. The validator and the guard both read combinationally —
    // address and datum have to be in the same cycle or every comparison is off by one —
    // and an asynchronous read cannot be BRAM. Left to infer, Vivado dissolved 1608x32
    // into 51,456 flip-flops (FDRE required 51,456 against 35,200 available, and LUTs
    // 29,641 against 17,600): the same failure recorded in the autoehw campaign, where a
    // 2048x32 array became 65,536 FFs. LUTRAM gives 64x1 per SLICEM LUT, so this is
    // 32 x ceil(1608/64) = 832 LUTs.
    (* ram_style = "distributed" *) reg [31:0] buffer [0:BUF_WORDS-1];

    // ------------------------------------------------------------------ write channel
    wire        wr_fire = s_awvalid && s_wvalid && !s_bvalid;
    assign      s_awready = wr_fire;
    assign      s_wready  = wr_fire;

    wire        wr_is_reg = (s_awaddr >= REG_BASE);
    wire [11:0] wr_word   = s_awaddr[13:2];

    // How many words the host has written since the last load. COUNTED, not declared: a
    // host that stops early leaves a smaller number and the validator refuses on it,
    // rather than the guard reading whatever a previous candidate left behind. A word
    // written twice makes the count exceed the expected 1608, which is also refused — the
    // check is equality, not a lower bound.
    reg [11:0] write_count;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_bvalid          <= 1'b0;
            s_bresp           <= 2'b00;
            ctrl_go           <= 1'b0;
            ctrl_arm          <= 1'b0;
            ctrl_mode_holdout <= 1'b0;
            loaded_words      <= 12'd0;
            write_count       <= 12'd0;
        end else begin
            ctrl_go  <= 1'b0;    // one-cycle pulses
            ctrl_arm <= 1'b0;

            if (wr_fire) begin
                s_bvalid <= 1'b1;
                s_bresp  <= 2'b00;
                if (wr_is_reg) begin
                    case (s_awaddr)
                        REG_BASE: begin
                            if (s_wdata[0]) begin
                                // latch what was actually written, then reset the counter
                                // so the next candidate starts from zero rather than
                                // inheriting this one's total.
                                loaded_words <= write_count;
                                write_count  <= 12'd0;
                            end
                            ctrl_go           <= s_wdata[1];
                            ctrl_arm          <= s_wdata[2];
                            ctrl_mode_holdout <= s_wdata[3];
                        end
                        default: s_bresp <= 2'b10;   // SLVERR: nothing else is writable
                    endcase
                end else if (wr_word < BUF_WORDS) begin
                    if (write_count != 12'hFFF) write_count <= write_count + 12'd1;
                end else begin
                    s_bresp <= 2'b10;
                end
            end else if (s_bvalid && s_bready) begin
                s_bvalid <= 1'b0;
            end
        end
    end

    // ------------------------------------------------------------------- read channel
    assign s_arready = s_arvalid && !s_rvalid;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_rvalid <= 1'b0;
            s_rresp  <= 2'b00;
            s_rdata  <= 32'd0;
        end else if (s_arvalid && !s_rvalid) begin
            s_rvalid <= 1'b1;
            s_rresp  <= 2'b00;
            if (s_araddr >= REG_BASE) begin
                case (s_araddr)
                    REG_BASE + 16'h0004:
                        s_rdata <= {26'd0, scorer_armed, scorer_done, scorer_busy,
                                    configuration_valid, guard_fault, guard_busy};
                    REG_BASE + 16'h0008:
                        s_rdata <= {4'd0, guard_fault_word, 12'd0, guard_fault_code};
                    REG_BASE + 16'h000C:
                        s_rdata <= {20'd0, loaded_words};
                    default: begin
                        if (s_araddr >= REG_BASE + 16'h0010 &&
                            s_araddr <  REG_BASE + 16'h0010 + LUTS*4) begin
                            s_rdata <= {24'd0,
                                        score_flat[(s_araddr[7:2] - 4) * 8 +: 8]};
                        end else begin
                            s_rdata <= 32'd0;
                            s_rresp <= 2'b10;
                        end
                    end
                endcase
            end else if (s_araddr[13:2] < BUF_WORDS) begin
                s_rdata <= axi_buf_rdata;
            end else begin
                s_rdata <= 32'd0;
                s_rresp <= 2'b10;
            end
        end else if (s_rvalid && s_rready) begin
            s_rvalid <= 1'b0;
        end
    end

    // The memory itself lives in its own purely synchronous block with NO reset, and its
    // reads are purely combinational. Both matter: an array written inside an
    // asynchronous-reset process is not inferrable as RAM at all, and the first attempt —
    // which only added `ram_style = "distributed"` while leaving the write in the
    // reset block — produced byte-identical over-utilisation (FDRE 51,456 = 1608 x 32).
    // The attribute was being ignored, not disobeyed.
    wire buf_we = wr_fire && !wr_is_reg && (wr_word < BUF_WORDS);
    always @(posedge clk) if (buf_we) buffer[wr_word] <= s_wdata;

    wire [31:0] axi_buf_rdata = buffer[s_araddr[13:2]];

    // ------------------------------------- buffer read port for the validator and guard
    //
    // COMBINATIONAL, not registered. The validator and the guard both drive an address and
    // compare the datum in the same cycle; a registered read port returns the previous
    // address's word and every comparison is off by one. That exact bug already cost a
    // debugging round in `carrier_guard`, where the address, the datum and the ICAP strobe
    // had to be brought into one cycle for any clean run to confirm.
    always @* buf_rdata = buffer[buf_raddr];
endmodule

`default_nettype wire
