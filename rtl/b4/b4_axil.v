// B4 carrier v2 register file — AXI4-Lite slave, 16-bit address window, word-addressed.
// The instrument's eight stable-state words (STATUS, FAULT, 0x2010..0x2024) keep their offsets; HEARTBEAT, NONCE and
// VARIANT too; the staging / tag / key windows and HW_COMMIT are the B1 register file's. The sweep readout (0x2240..)
// is gone: the observation is read slot by slot (SLOT_ADDR / SLOT_READ / SLOT_IN_READ).
//
//   0x2000  CTRL      W: bit6 arm  bit7 arm_a5_context (with bit6 only)  bit8 key_commit  bit9 PRE_SAMPLE
//                        bit10 INIT_REQ  bit11 STEP  bit12 CLEANUP  bit13 CLOSE  bit14 RESTORE_INIT
//                        bit15 CLOSE_INJECTION.
//                        ONE RULE: a CTRL write is accepted only when the engine and the gate are idle, exactly ONE
//                        operation is named (bit 7 may accompany bit 6 only) and no other bit is set; otherwise the
//                        write is SLVERR and NOTHING changes. (A busy or combined command never half-applies or vanishes.)
//   0x2004  STATUS    R: bit0 gate_busy  bit1 fault  bit2 configuration_valid_hw (= armed, no recovery)
//                        bit3 engine_busy  bit4 step_done  bit5 pre_sampled  bit6 tag_ok  bit7 recovery_required
//                        bit8 alive(=1)  bit9 init_done  bit10 init_pending  bit11 key_loaded
//                        bit12 idle (engine idle, not armed, no injection open, inputs and clock 0)  bit13 cleanup_done
//                        bit14 injection_open  bit15 cleanup_edge  bits 20:16 slot_count  bits 25:21 step_index
//                        bit26 restore_done ; bits 31:27 RESERVED read zero
//   0x2008  FAULT     R: bits3:0 (5 NOT_ARMED, 6 NOT_REALISABLE, 7 SEQUENCE, 8 SLOT_OVERFLOW, 12 ARM_NOKEY, 13 ARM_AUTH)
//   0x2010  Q_LIVE    R: bits7:0 the slice outputs, registered every cycle (AFF .. D5FF = bit 0 .. 7)
//   0x2014  IN_LIVE   R: bits7:0 d as driven, bit8 ce, bit9 sr, bit10 slice clock
//   0x2018  SLOT_READ R: bits7:0 the sample at SLOT_ADDR
//   0x201C  SLOT_ADDR W/R: bits4:0
//   0x2020  WITNESS   R: bits7:0 gsr_count  bits15:8 mechanism (2 = GSR via STARTUPE2)  bits23:16 PULSE (clocks, LUTRAM-timed)
//                        bit24 restore_pending  bit25 pre_context_a5  bit26 stall (the bus gates hold new accesses)
//                        bit27 pre_init_cleanup (the recorded cleanup-like operation inside step 0, contract 5.6 J3)
//   0x2024  TIMING    R: bits7:0 ASSERT_DELAY  bits15:8 RELEASE  bits23:16 SAMPLE_OFFSET  bits27:24 SETTLE  bits31:28 HOLD
//   0x2028  HEARTBEAT R  (free-running; RESET BY EVERY EVENT — a witness that GSR occurred)
//   0x202C  NONCE_LO  R   0x2030 NONCE_HI R  (persistent across the events)
//   0x2034  VARIANT   R   (B4 v2: 0x42340001)
//   0x2038  STEP_IN   W/R: bits7:0 d  bits15:8 ce  bits23:16 sr  bit24 clock  (staged; LATCHED by the engine at CTRL.STEP)
//   0x203C  BASE_STATE R: bits7:0 the sample after the restore event on the restored base (P9)
//   0x2040  SLOT_IN_READ R: the inputs APPLIED at the sample of SLOT_ADDR (d 7:0, ce 15:8, sr 23:16, clock 24)
//   0x2100..0x214C  ARM payload staging, 20 words W    0x2150..0x215C  ARM tag, 4 words W
//   0x2160..0x216C  KEY, 4 words W-ONLY, WRITE-ONCE (persistent)      0x2200..0x221C  HW_COMMIT R (8; read before INIT_REQ)
//   any other address: SLVERR on read and on write.
`default_nettype none
module b4_axil #(
    parameter [31:0] VARIANT_WORD = 32'h42340001,
    parameter [31:0] TIMING_WORD  = 32'h0,
    parameter [7:0]  MECHANISM    = 8'd2,
    parameter [7:0]  PULSE_WORD   = 8'd2
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] s_awaddr, input wire s_awvalid, output wire s_awready,
    input  wire [31:0] s_wdata,  input wire [3:0] s_wstrb, input wire s_wvalid, output wire s_wready,
    output reg  [1:0]  s_bresp,  output reg s_bvalid, input wire s_bready,
    input  wire [15:0] s_araddr, input wire s_arvalid, output wire s_arready,
    output reg  [31:0] s_rdata,  output reg [1:0] s_rresp, output reg s_rvalid, input wire s_rready,
    // to the gate
    output reg  [639:0] payload,
    output reg  [127:0] tag,
    output reg          arm_strobe,
    output reg          arm_a5,
    output wire [127:0] key,
    output wire         key_loaded,
    // to the engine
    output reg          op_pre_sample, op_init_req, op_step, op_cleanup, op_restore_init, op_close, op_close_injection,
    output reg  [24:0]  step_in,
    output reg  [4:0]   slot_addr,
    // observations
    input  wire         gate_busy, tag_ok, recovery_required, configuration_valid_hw,
    input  wire [3:0]   fault_code,
    input  wire [63:0]  nonce,
    input  wire [255:0] hw_commit,
    input  wire         engine_busy, step_done, pre_sampled, init_done, init_pending, cleanup_done, cleanup_edge, idle,
    input  wire         injection_open, restore_pending, restore_done, pre_context_a5, pre_init_cleanup, stall,
    input  wire [4:0]   slot_count, step_index,
    input  wire [7:0]   q_live, slot_read, gsr_count, base_state,
    input  wire [31:0]  slot_in_read,
    input  wire [10:0]  in_live,
    input  wire [31:0]  heartbeat
);
    // ---------------------------------------------------------------- the persistent key
    reg         key_we; reg [127:0] key_d; reg key_loaded_we;
    b4_gsr_reg #(.W(128)) key_store (.wclk(clk), .we(key_we), .d(key_d), .q(key));
    b4_gsr_reg #(.W(1))   key_loaded_store (.wclk(clk), .we(key_loaded_we), .d(1'b1), .q(key_loaded));

    // ---------------------------------------------------------------- write channel
    reg aw_seen, w_seen; reg [15:0] aw_addr; reg [31:0] w_data;
    assign s_awready = !aw_seen && !s_bvalid;
    assign s_wready  = !w_seen && !s_bvalid;
    wire wr_go = aw_seen && w_seen && !s_bvalid;
    wire [15:0] wa = aw_addr;
    wire wr_ctrl    = (wa == 16'h2000);
    wire wr_slot    = (wa == 16'h201C);
    wire wr_stepin  = (wa == 16'h2038);
    wire wr_payload = (wa >= 16'h2100) && (wa < 16'h2150) && (wa[1:0] == 2'b00);
    wire wr_tag     = (wa >= 16'h2150) && (wa < 16'h2160) && (wa[1:0] == 2'b00);
    wire wr_key     = (wa >= 16'h2160) && (wa < 16'h2170) && (wa[1:0] == 2'b00);
    // the CTRL acceptance rule
    wire [8:0] ctrl_ops = {w_data[15], w_data[14], w_data[13], w_data[12], w_data[11], w_data[10], w_data[9], w_data[8], w_data[6]};
    wire ctrl_one = (ctrl_ops != 9'd0) && ((ctrl_ops & (ctrl_ops - 9'd1)) == 9'd0);
    wire ctrl_known = (w_data & ~32'h0000FFC0) == 32'd0;
    wire ctrl_a5_ok = !w_data[7] || w_data[6];
    wire ctrl_accept = ctrl_one && ctrl_known && ctrl_a5_ok && !engine_busy && !gate_busy;
    integer k;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            aw_seen <= 0; w_seen <= 0; aw_addr <= 0; w_data <= 0; s_bvalid <= 0; s_bresp <= 0;
            payload <= 640'd0; tag <= 128'd0; arm_strobe <= 0; arm_a5 <= 0;
            op_pre_sample <= 0; op_init_req <= 0; op_step <= 0; op_cleanup <= 0; op_restore_init <= 0; op_close <= 0; op_close_injection <= 0;
            step_in <= 25'd0; slot_addr <= 5'd0; key_we <= 0; key_d <= 128'd0; key_loaded_we <= 0;
        end else begin
            arm_strobe <= 1'b0; op_pre_sample <= 0; op_init_req <= 0; op_step <= 0; op_cleanup <= 0; op_restore_init <= 0; op_close <= 0; op_close_injection <= 0;
            key_we <= 0; key_loaded_we <= 0;
            if (s_awvalid && s_awready) begin aw_seen <= 1; aw_addr <= s_awaddr; end
            if (s_wvalid && s_wready)   begin w_seen <= 1; w_data <= s_wdata; end
            if (wr_go) begin
                aw_seen <= 0; w_seen <= 0; s_bvalid <= 1;
                s_bresp <= 2'b00;
                if (wr_ctrl) begin
                    if (!ctrl_accept) s_bresp <= 2'b10;                 // SLVERR: busy, combined, unknown or malformed — nothing changes
                    else begin
                        arm_strobe         <= w_data[6]; arm_a5 <= w_data[7];
                        if (w_data[8] && !key_loaded) key_loaded_we <= 1'b1;   // write-once commit (persistent)
                        op_pre_sample      <= w_data[9];
                        op_init_req        <= w_data[10];
                        op_step            <= w_data[11];
                        op_cleanup         <= w_data[12];
                        op_close           <= w_data[13];
                        op_restore_init    <= w_data[14];
                        op_close_injection <= w_data[15];
                    end
                end else if (wr_key) begin
                    k = (wa - 16'h2160) >> 2;
                    if (key_loaded) s_bresp <= 2'b10;      // SLVERR: the key is write-once
                    else begin key_d <= key; key_d[(3 - k)*32 +: 32] <= w_data; key_we <= 1'b1; end
                end else if (wr_payload) begin
                    k = (wa - 16'h2100) >> 2;
                    payload[(19 - k)*32 +: 32] <= w_data;
                end else if (wr_tag) begin
                    k = (wa - 16'h2150) >> 2;
                    tag[(3 - k)*32 +: 32] <= w_data;
                end else if (wr_stepin) begin
                    step_in <= w_data[24:0];
                end else if (wr_slot) begin
                    slot_addr <= w_data[4:0];
                end else begin
                    s_bresp <= 2'b10;
                end
            end else if (s_bvalid && s_bready) begin
                s_bvalid <= 0;
            end
        end
    end

    // ---------------------------------------------------------------- read channel
    assign s_arready = !s_rvalid;
    wire [15:0] ra = s_araddr;
    wire [31:0] status = {5'd0, restore_done, step_index, slot_count, cleanup_edge, injection_open, cleanup_done, idle,
                          key_loaded, init_pending, init_done, 1'b1, recovery_required, tag_ok, pre_sampled, step_done,
                          engine_busy, configuration_valid_hw, (fault_code != 4'd0), gate_busy};
    integer j;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_rvalid <= 0; s_rresp <= 0; s_rdata <= 0;
        end else if (s_arvalid && s_arready) begin
            s_rvalid <= 1; s_rresp <= 2'b00; s_rdata <= 32'd0;
            if (ra == 16'h2004)      s_rdata <= status;
            else if (ra == 16'h2008) s_rdata <= {28'd0, fault_code};
            else if (ra == 16'h2010) s_rdata <= {24'd0, q_live};
            else if (ra == 16'h2014) s_rdata <= {21'd0, in_live};
            else if (ra == 16'h2018) s_rdata <= {24'd0, slot_read};
            else if (ra == 16'h201C) s_rdata <= {27'd0, slot_addr};
            else if (ra == 16'h2020) s_rdata <= {4'd0, pre_init_cleanup, stall, pre_context_a5, restore_pending, PULSE_WORD, MECHANISM, gsr_count};
            else if (ra == 16'h2024) s_rdata <= TIMING_WORD;
            else if (ra == 16'h2028) s_rdata <= heartbeat;
            else if (ra == 16'h202C) s_rdata <= nonce[31:0];
            else if (ra == 16'h2030) s_rdata <= nonce[63:32];
            else if (ra == 16'h2034) s_rdata <= VARIANT_WORD;
            else if (ra == 16'h2038) s_rdata <= {7'd0, step_in};
            else if (ra == 16'h203C) s_rdata <= {24'd0, base_state};
            else if (ra == 16'h2040) s_rdata <= slot_in_read;
            else if (ra >= 16'h2200 && ra < 16'h2220 && ra[1:0] == 2'b00) begin
                j = (ra - 16'h2200) >> 2;
                s_rdata <= hw_commit[(7 - j)*32 +: 32];
            end else s_rresp <= 2'b10;
        end else if (s_rvalid && s_rready) begin
            s_rvalid <= 0;
        end
    end
endmodule
`default_nettype wire
