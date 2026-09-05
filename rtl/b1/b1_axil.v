// P3 register file — AXI4-Lite slave, 16-bit address window, word-addressed.
//
//   0x2000  CTRL      W: bit6 arm_strobe, bit7 mode_holdout      (anything else: SLVERR)
//   0x2004  STATUS    R: bit0 gate_busy  bit1 fault  bit2 configuration_valid_hw
//                        bit3 scorer_busy bit4 scorer_done bit5 scorer_armed bit6 tag_ok
//                        bit7 recovery_required bit8 alive(=1) bit9 sweep_done
//                        bit10 tables_match bit11 key_loaded ; bits 31:27 RESERVED read zero
//   0x2008  FAULT     R: bits3:0 fault code (13 ARM_AUTH, 15 ARM_TABLE)
//   0x2010..0x2024  SCORE0..5  R          ─┐ zynq-psmap P2's eight stable-state words keep
//   (STATUS, FAULT, SCORE0..5 = the eight) ─┘ their offsets
//   0x2028  HEARTBEAT R  (free-running counter, +1 per clk)
//   0x202C  NONCE_LO  R   0x2030 NONCE_HI R
//   0x2034  VARIANT   R   (B1: the constant VARIANT_WORD — the gate contract this carrier implements)
//   0x2100..0x214C  ARM payload staging, 20 words W (commit[8] then tables[12])
//   0x2150..0x215C  ARM tag, 4 words W
//   0x2160..0x216C  KEY, 4 words W-ONLY, WRITE-ONCE: accepted only while key_loaded == 0;
//                   CTRL bit 8 (key_commit) sets key_loaded; afterwards a key-word write is
//                   SLVERR and key_commit is ignored. Reads are SLVERR (undecoded). Only a
//                   reconfiguration clears key_loaded. STATUS bit 11 = key_loaded.
//   0x2200..0x221C  HW_COMMIT R (8)      0x2240..0x226C FUNCTIONAL_READOUT R (12)
//   any other address: SLVERR on read and on write (the P2 allowlist rule stands: an
//   undecoded read is a data abort on this board's U-Boot).
//
// `configuration_valid_hw` and `hw_commit` are READ-ONLY BY CONSTRUCTION: no address
// writes them. The staging registers are write-only: reading them back is refused, so the
// host's evidence of what it staged is its own copy, and the PL's evidence of what it
// verified is HW_COMMIT.
`default_nettype none
module b1_axil #(
    parameter integer LUTS = 6,
    parameter [31:0]  VARIANT_WORD = 32'h42310001   // "B1", contract v1 (SEMANTIC_GATE = 0)
) (
    input  wire        clk,
    input  wire        rst_n,
    // AXI4-Lite
    input  wire [15:0] s_awaddr, input wire s_awvalid, output wire s_awready,
    input  wire [31:0] s_wdata,  input wire [3:0] s_wstrb, input wire s_wvalid, output wire s_wready,
    output reg  [1:0]  s_bresp,  output reg s_bvalid, input wire s_bready,
    input  wire [15:0] s_araddr, input wire s_arvalid, output wire s_arready,
    output reg  [31:0] s_rdata,  output reg [1:0] s_rresp, output reg s_rvalid, input wire s_rready,
    // to the gate
    output reg  [639:0] payload,
    output reg  [127:0] tag,
    output reg          arm_strobe,
    output reg          mode_holdout,
    output reg  [127:0] key,
    output reg          key_loaded,
    // from the gate / scorer
    input  wire         gate_busy, tag_ok, sweep_done, tables_match, recovery_required,
    input  wire         configuration_valid_hw,
    input  wire [3:0]   fault_code,
    input  wire [63:0]  nonce,
    input  wire [255:0] hw_commit,
    input  wire [383:0] functional_readout,
    input  wire         scorer_busy, scorer_done, scorer_armed,
    input  wire [LUTS*8-1:0] score_flat,
    input  wire [31:0]  heartbeat
);
    // ---------------------------------------------------------------- write channel
    reg aw_seen, w_seen; reg [15:0] aw_addr; reg [31:0] w_data;
    assign s_awready = !aw_seen && !s_bvalid;
    assign s_wready  = !w_seen && !s_bvalid;
    wire wr_go = aw_seen && w_seen && !s_bvalid;
    wire [15:0] wa = aw_addr;
    wire wr_ctrl    = (wa == 16'h2000);
    wire wr_payload = (wa >= 16'h2100) && (wa < 16'h2150) && (wa[1:0] == 2'b00);
    wire wr_tag     = (wa >= 16'h2150) && (wa < 16'h2160) && (wa[1:0] == 2'b00);
    wire wr_key     = (wa >= 16'h2160) && (wa < 16'h2170) && (wa[1:0] == 2'b00);
    integer k;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            aw_seen <= 0; w_seen <= 0; aw_addr <= 0; w_data <= 0; s_bvalid <= 0; s_bresp <= 0;
            payload <= 640'd0; tag <= 128'd0; arm_strobe <= 0; mode_holdout <= 0;
            key <= 128'd0; key_loaded <= 1'b0;
        end else begin
            arm_strobe <= 1'b0;
            if (s_awvalid && s_awready) begin aw_seen <= 1; aw_addr <= s_awaddr; end
            if (s_wvalid && s_wready)   begin w_seen <= 1; w_data <= s_wdata; end
            if (wr_go) begin
                aw_seen <= 0; w_seen <= 0; s_bvalid <= 1;
                s_bresp <= 2'b00;
                if (wr_ctrl) begin
                    arm_strobe   <= w_data[6];
                    mode_holdout <= w_data[7];
                    if (w_data[8] && !key_loaded) key_loaded <= 1'b1;   // write-once commit
                end else if (wr_key) begin
                    k = (wa - 16'h2160) >> 2;              // 0..3, word 0 at the top
                    if (key_loaded) s_bresp <= 2'b10;      // SLVERR: the key is write-once
                    else key[(3 - k)*32 +: 32] <= w_data;
                end else if (wr_payload) begin
                    k = (wa - 16'h2100) >> 2;              // 0..19
                    payload[(19 - k)*32 +: 32] <= w_data;  // word 0 at the top
                end else if (wr_tag) begin
                    k = (wa - 16'h2150) >> 2;              // 0..3
                    tag[(3 - k)*32 +: 32] <= w_data;
                end else begin
                    s_bresp <= 2'b10;                      // SLVERR: nothing else is writable
                end
            end else if (s_bvalid && s_bready) begin
                s_bvalid <= 0;
            end
        end
    end

    // ---------------------------------------------------------------- read channel
    assign s_arready = !s_rvalid;
    wire [15:0] ra = s_araddr;
    wire [31:0] status = {5'd0, 15'd0, key_loaded, tables_match, sweep_done, 1'b1, recovery_required,
                          tag_ok, scorer_armed, scorer_done, scorer_busy,
                          configuration_valid_hw, (fault_code != 4'd0), gate_busy};
    integer j;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_rvalid <= 0; s_rresp <= 0; s_rdata <= 0;
        end else if (s_arvalid && s_arready) begin
            s_rvalid <= 1; s_rresp <= 2'b00; s_rdata <= 32'd0;
            if (ra == 16'h2004)      s_rdata <= status;
            else if (ra == 16'h2008) s_rdata <= {28'd0, fault_code};
            else if (ra >= 16'h2010 && ra < 16'h2028 && ra[1:0] == 2'b00)
                s_rdata <= {24'd0, score_flat[((ra - 16'h2010) >> 2) * 8 +: 8]};
            else if (ra == 16'h2028) s_rdata <= heartbeat;
            else if (ra == 16'h202C) s_rdata <= nonce[31:0];
            else if (ra == 16'h2030) s_rdata <= nonce[63:32];
            else if (ra == 16'h2034) s_rdata <= VARIANT_WORD;
            else if (ra >= 16'h2200 && ra < 16'h2220 && ra[1:0] == 2'b00) begin
                j = (ra - 16'h2200) >> 2;
                s_rdata <= hw_commit[(7 - j)*32 +: 32];
            end else if (ra >= 16'h2240 && ra < 16'h2270 && ra[1:0] == 2'b00) begin
                j = (ra - 16'h2240) >> 2;                  // 0..11: table t = j>>1, high word then low
                s_rdata <= functional_readout[(LUTS - 1 - (j >> 1)) * 64 + (j[0] ? 0 : 32) +: 32];
            end else s_rresp <= 2'b10;                     // SLVERR
        end else if (s_rvalid && s_rready) begin
            s_rvalid <= 0;
        end
    end
endmodule
`default_nettype wire
