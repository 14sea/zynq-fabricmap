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
//   0x2000  CTRL      W: bit0 load_done (latch loaded_words)
//                        bit1 begin_txn      bit2 validate_env    bit3 write_env
//                        bits5:4 env_index   bit6 arm             bit7 mode_holdout
//   0x2004  STATUS    R: bit0 txn_busy, bit1 txn_fault, bit2 configuration_valid,
//                        bit3 scorer_busy, bit4 scorer_done, bit5 scorer_armed,
//                        bit6 pass1_complete, bit7 recovery_required,
//                        bits9:8 expect_env
//   0x2008  FAULT     R: bits3:0 txn fault code
//   0x200C  LOADED    R: words the host has written into the buffer since the last latch
//   0x2010  SCORE0..  R: six per-LUT match counts, one per register
//
// `configuration_valid` is READ-ONLY BY CONSTRUCTION: it is an input to this module and
// appears only in the STATUS read multiplexer. There is no address that writes it, which
// is the first of the four properties ruled for the guard — a register file that offered
// one would make the whole interlock a formality.

`default_nettype none

module carrier_axil #(
    parameter integer BUF_WORDS = 536,   // ONE envelope: the two-pass contract
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

    // candidate buffer, read side. ONE port, shared: the transaction and the validator
    // drive it while a transaction runs, and an AXI read of the buffer drives it when one
    // does not. Two read ports made Vivado replicate the array — 792 RAMD64E against the
    // 400 SLICEM sites that exist left of the flush column — and the host only ever reads
    // the buffer between transactions anyway, to collect the readback it must hash itself.
    input  wire [11:0] buf_raddr,
    input  wire        buf_read_busy,   // a transaction owns the port this cycle
    output wire [11:0] buf_raddr_out,   // the address actually presented
    output reg  [31:0] buf_rdata,   // SYNCHRONOUS: valid one cycle after buf_raddr
    output reg  [11:0] loaded_words,

    // the transaction's readback write-back port; muxed with the AXI write below so the
    // array keeps ONE write port. Two write sources on one array is what dissolved a
    // 2048x32 memory into 65,536 flip-flops in the autoehw campaign.
    input  wire        txn_we,
    input  wire [11:0] txn_waddr,
    input  wire [31:0] txn_wdata,

    // control pulses
    output reg         ctrl_begin_txn,
    output reg         ctrl_validate,
    output reg         ctrl_write,
    output reg  [1:0]  ctrl_env_index,
    output reg         ctrl_arm,
    output reg         ctrl_mode_holdout,

    // status in
    input  wire        txn_busy,
    input  wire        txn_fault,
    input  wire [3:0]  txn_fault_code,
    input  wire        pass1_complete,
    input  wire        recovery_required,
    input  wire [1:0]  expect_env,
    input  wire        configuration_valid,
    input  wire        scorer_busy,
    input  wire        scorer_done,
    input  wire        scorer_armed,
    input  wire [LUTS*8-1:0] score_flat
);
    localparam [15:0] REG_BASE = 16'h2000;

    // BLOCK RAM, and the reads are SYNCHRONOUS. 1608 x 32 = 51,456 bits is about two
    // RAMB36 and costs no SLICEM at all — which matters because CLBLM_L_X6 is a SLICEM
    // column and two of the evolvable LUTs live in it, so a LUTRAM buffer competes for
    // exactly the resources the isolation checks must keep clear.
    //
    // The one-cycle latency is affordable because validation completes before any
    // streaming, so there is exactly one sequential reader at a time: address out, datum
    // and its expectation compared on the next cycle. An earlier note claiming BRAM was
    // impossible here confused a property of the then-current RTL with an architectural
    // fact.
    // DISTRIBUTED. With the two-pass contract the buffer is 536 words, which is
    // 32 x ceil(536/64) = 288 LUTs of SLICEM — small enough to sit with the logic on the
    // LEFT of the first flush column, where PS7 also is. That is the whole reason the
    // one-envelope buffer was taken: BRAM columns all lie to the RIGHT of that column, so
    // a BRAM buffer forces either the AXI bus or the buffer read path to cross it.
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
            ctrl_begin_txn    <= 1'b0;
            ctrl_validate     <= 1'b0;
            ctrl_write        <= 1'b0;
            ctrl_env_index    <= 2'd0;
            ctrl_arm          <= 1'b0;
            ctrl_mode_holdout <= 1'b0;
            loaded_words      <= 12'd0;
            write_count       <= 12'd0;
        end else begin
            ctrl_begin_txn <= 1'b0;   // one-cycle pulses
            ctrl_validate  <= 1'b0;
            ctrl_write     <= 1'b0;
            ctrl_arm       <= 1'b0;

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
                            ctrl_begin_txn    <= s_wdata[1];
                            ctrl_validate     <= s_wdata[2];
                            ctrl_write        <= s_wdata[3];
                            ctrl_env_index    <= s_wdata[5:4];
                            ctrl_arm          <= s_wdata[6];
                            ctrl_mode_holdout <= s_wdata[7];
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
                        s_rdata <= {22'd0, expect_env, recovery_required, pass1_complete,
                                    scorer_armed, scorer_done, scorer_busy,
                                    configuration_valid, txn_fault, txn_busy};
                    REG_BASE + 16'h0008:
                        s_rdata <= {28'd0, txn_fault_code};
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
                // the shared port already presented this address, so the datum is here
                s_rdata <= buf_rdata;
            end else begin
                s_rdata <= 32'd0;
                s_rresp <= 2'b10;
            end
        end else if (s_rvalid && s_rready) begin
            s_rvalid <= 1'b0;
        end
    end

    // The memory itself lives in its own purely synchronous block with NO reset, and its
    // reads are SYNCHRONOUS (this note said "purely combinational" while the buffer was
    // LUTRAM; it is BRAM now). Both matter: an array written inside an
    // asynchronous-reset process is not inferrable as RAM at all, and the first attempt —
    // which only added `ram_style = "distributed"` while leaving the write in the
    // reset block — produced byte-identical over-utilisation (FDRE 51,456 = 1608 x 32).
    // The attribute was being ignored, not disobeyed.
    // ONE write port, muxed. The host loads the buffer and the transaction writes the
    // readback into it, and they never overlap: the host is not writing while the
    // transaction runs, and the transaction is not running while the host loads.
    wire        axi_we    = wr_fire && !wr_is_reg && (wr_word < BUF_WORDS);
    wire        buf_we    = axi_we || txn_we;
    wire [11:0] buf_waddr = txn_we ? txn_waddr : wr_word;
    wire [31:0] buf_wdata = txn_we ? txn_wdata : s_wdata;
    always @(posedge clk) if (buf_we) buffer[buf_waddr] <= buf_wdata;



    // ------------------------------------------------------ the single read port
    //
    // SYNCHRONOUS: `buf_rdata` is the word at the address presented on the PREVIOUS cycle.
    // Both consumers pipeline their expectation to match.
    assign buf_raddr_out = buf_read_busy ? buf_raddr : s_araddr[13:2];
    always @(posedge clk) buf_rdata <= buffer[buf_raddr_out];
endmodule

`default_nettype wire
