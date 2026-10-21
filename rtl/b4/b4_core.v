// B4 carrier v2 core: everything below the AXI3→AXI4-Lite shim — the register file, the gate, the engine,
// the heartbeat — and the ports to the target slice and to STARTUPE2.GSR. `gsr` (the carrier's own drive)
// is folded into the reset of every flip-flop here: on silicon the global GSR does that implicitly; folding
// it in makes the RTL say so and the bench see it (the pulse generator keeps the raw reset, b4_engine).
`default_nettype none
module b4_core #(
    parameter [63:0]  NONCE_SEED    = 64'h9E3779B97F4A7C15,
    parameter [31:0]  VARIANT_WORD  = 32'h42340001,
    parameter integer ASSERT_DELAY  = 8,
    parameter integer PULSE         = 2,
    parameter integer RELEASE       = 16,
    parameter integer SAMPLE_OFFSET = 4,
    parameter integer SETTLE        = 4,
    parameter integer HOLD          = 4
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] s_awaddr, input wire s_awvalid, output wire s_awready,
    input  wire [31:0] s_wdata,  input wire [3:0] s_wstrb, input wire s_wvalid, output wire s_wready,
    output wire [1:0]  s_bresp,  output wire s_bvalid, input wire s_bready,
    input  wire [15:0] s_araddr, input wire s_arvalid, output wire s_arready,
    output wire [31:0] s_rdata,  output wire [1:0] s_rresp, output wire s_rvalid, input wire s_rready,
    // the target slice
    output wire        slice_clk, slice_ce, slice_sr,
    output wire [7:0]  slice_d,
    input  wire [7:0]  slice_q,
    // STARTUPE2
    output wire        gsr_drive
);
    localparam [31:0] TIMING_WORD = {HOLD[3:0], SETTLE[3:0], SAMPLE_OFFSET[7:0], RELEASE[7:0], ASSERT_DELAY[7:0]};
    wire rst_n_eff = rst_n & ~gsr_drive;

    wire [639:0] payload; wire [127:0] tag; wire arm_strobe; wire [127:0] key; wire key_loaded;
    wire op_pre_sample, op_init_req, op_step, op_cleanup, op_close; wire [24:0] step_in; wire [4:0] slot_addr;
    wire gate_busy, tag_ok, recovery_required, cfg_valid_hw, armed; wire [3:0] fault_code; wire [63:0] nonce; wire [255:0] hw_commit;
    wire engine_busy, step_done, pre_sampled, init_done, init_pending, cleanup_done, closed_without_cleanup, cleanup_edge, idle;
    wire [4:0] slot_count, step_index; wire [7:0] q_live, slot_read, gsr_count;
    wire eng_fault_strobe; wire [3:0] eng_fault_code; wire close_strobe;
    reg  [31:0] heartbeat;

    always @(posedge clk or negedge rst_n_eff)
        if (!rst_n_eff) heartbeat <= 32'd0; else heartbeat <= heartbeat + 32'd1;

    b4_axil #(.VARIANT_WORD(VARIANT_WORD), .TIMING_WORD(TIMING_WORD), .MECHANISM(8'd2)) axil (
        .clk(clk), .rst_n(rst_n_eff),
        .s_awaddr(s_awaddr), .s_awvalid(s_awvalid), .s_awready(s_awready),
        .s_wdata(s_wdata), .s_wstrb(s_wstrb), .s_wvalid(s_wvalid), .s_wready(s_wready),
        .s_bresp(s_bresp), .s_bvalid(s_bvalid), .s_bready(s_bready),
        .s_araddr(s_araddr), .s_arvalid(s_arvalid), .s_arready(s_arready),
        .s_rdata(s_rdata), .s_rresp(s_rresp), .s_rvalid(s_rvalid), .s_rready(s_rready),
        .payload(payload), .tag(tag), .arm_strobe(arm_strobe), .key(key), .key_loaded(key_loaded),
        .op_pre_sample(op_pre_sample), .op_init_req(op_init_req), .op_step(op_step), .op_cleanup(op_cleanup), .op_close(op_close),
        .step_in(step_in), .slot_addr(slot_addr),
        .gate_busy(gate_busy), .tag_ok(tag_ok), .recovery_required(recovery_required), .configuration_valid_hw(cfg_valid_hw),
        .fault_code(fault_code), .nonce(nonce), .hw_commit(hw_commit),
        .engine_busy(engine_busy), .step_done(step_done), .pre_sampled(pre_sampled), .init_done(init_done), .init_pending(init_pending),
        .cleanup_done(cleanup_done), .closed_without_cleanup(closed_without_cleanup), .cleanup_edge(cleanup_edge), .idle(idle),
        .slot_count(slot_count), .step_index(step_index), .q_live(q_live), .slot_read(slot_read), .gsr_count(gsr_count),
        .in_live({slice_clk, slice_sr, slice_ce, slice_d}), .heartbeat(heartbeat));

    b4_gate #(.NONCE_SEED(NONCE_SEED)) gate (
        .clk(clk), .rst_n(rst_n_eff), .payload(payload), .tag_in(tag), .arm_strobe(arm_strobe), .key(key), .key_loaded(key_loaded),
        .eng_fault_strobe(eng_fault_strobe), .eng_fault_code(eng_fault_code), .close_strobe(close_strobe),
        .nonce(nonce), .hw_commit(hw_commit), .busy(gate_busy), .tag_ok(tag_ok), .armed(armed),
        .recovery_required(recovery_required), .fault_code(fault_code), .configuration_valid_hw(cfg_valid_hw));

    b4_engine #(.ASSERT_DELAY(ASSERT_DELAY), .PULSE(PULSE), .RELEASE(RELEASE), .SAMPLE_OFFSET(SAMPLE_OFFSET), .SETTLE(SETTLE), .HOLD(HOLD)) engine (
        .clk(clk), .rst_n(rst_n_eff), .rst_n_raw(rst_n), .armed(armed), .recovery_required(recovery_required),
        .op_pre_sample(op_pre_sample), .op_init_req(op_init_req), .op_step(op_step), .op_cleanup(op_cleanup), .op_close(op_close),
        .step_in(step_in), .q_in(slice_q),
        .slice_clk(slice_clk), .slice_ce(slice_ce), .slice_sr(slice_sr), .slice_d(slice_d), .gsr_drive(gsr_drive), .q_live(q_live),
        .pre_sampled(pre_sampled), .init_pending(init_pending), .init_done(init_done), .cleanup_done(cleanup_done),
        .closed_without_cleanup(closed_without_cleanup), .cleanup_edge(cleanup_edge), .gsr_count(gsr_count),
        .step_index(step_index), .slot_count(slot_count), .busy(engine_busy), .step_done(step_done), .idle(idle),
        .slot_addr_host(slot_addr), .slot_q(slot_read),
        .fault_strobe(eng_fault_strobe), .fault_code_o(eng_fault_code), .close_strobe(close_strobe));
endmodule
`default_nettype wire
