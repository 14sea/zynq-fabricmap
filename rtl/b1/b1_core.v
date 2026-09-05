// P3 core: everything below the AXI3→AXI4-Lite shim — register file, ARM gate, heartbeat,
// the reused carrier scorer, and the six evolvable LUT6. No ICAPE2, no stream engine.
`default_nettype none
module b1_core #(
    parameter [63:0]  NONCE_SEED = 64'h9E3779B97F4A7C15,
    parameter integer LUTS       = 6,
    parameter integer SEMANTIC_GATE = 0,
    parameter [31:0]  VARIANT_WORD = 32'h42310001
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [15:0] s_awaddr, input wire s_awvalid, output wire s_awready,
    input  wire [31:0] s_wdata,  input wire [3:0] s_wstrb, input wire s_wvalid, output wire s_wready,
    output wire [1:0]  s_bresp,  output wire s_bvalid, input wire s_bready,
    input  wire [15:0] s_araddr, input wire s_arvalid, output wire s_arready,
    output wire [31:0] s_rdata,  output wire [1:0] s_rresp, output wire s_rvalid, input wire s_rready,
    // the LUTs live in the top so their LOC/LOCK_PINS constraints name top-level cells
    output wire [5:0]      vector,
    input  wire [LUTS-1:0] lut_q
);
    `include "carrier_base_init.vh"   // unused here; kept so the generated header is a build input

    wire [639:0] payload; wire [127:0] tag; wire arm_strobe, mode_holdout;
    wire [127:0] key; wire key_loaded;
    wire gate_busy, tag_ok, sweep_done, tables_match, recovery_required, cfg_valid_hw;
    wire [3:0] fault_code; wire [63:0] nonce; wire [255:0] hw_commit; wire [383:0] readout;
    wire scorer_busy, scorer_done, scorer_armed, scorer_arm;
    wire [LUTS*8-1:0] score_flat;
    wire [5:0] sweep_vector, scorer_vector; wire sweep_active;
    reg  [31:0] heartbeat;

    always @(posedge clk or negedge rst_n)
        if (!rst_n) heartbeat <= 32'd0; else heartbeat <= heartbeat + 32'd1;

    b1_axil #(.LUTS(LUTS), .VARIANT_WORD(VARIANT_WORD)) axil (
        .clk(clk), .rst_n(rst_n),
        .s_awaddr(s_awaddr), .s_awvalid(s_awvalid), .s_awready(s_awready),
        .s_wdata(s_wdata), .s_wstrb(s_wstrb), .s_wvalid(s_wvalid), .s_wready(s_wready),
        .s_bresp(s_bresp), .s_bvalid(s_bvalid), .s_bready(s_bready),
        .s_araddr(s_araddr), .s_arvalid(s_arvalid), .s_arready(s_arready),
        .s_rdata(s_rdata), .s_rresp(s_rresp), .s_rvalid(s_rvalid), .s_rready(s_rready),
        .payload(payload), .tag(tag), .arm_strobe(arm_strobe), .mode_holdout(mode_holdout),
        .key(key), .key_loaded(key_loaded),
        .gate_busy(gate_busy), .tag_ok(tag_ok), .sweep_done(sweep_done), .tables_match(tables_match),
        .recovery_required(recovery_required), .configuration_valid_hw(cfg_valid_hw),
        .fault_code(fault_code), .nonce(nonce), .hw_commit(hw_commit), .functional_readout(readout),
        .scorer_busy(scorer_busy), .scorer_done(scorer_done), .scorer_armed(scorer_armed),
        .score_flat(score_flat), .heartbeat(heartbeat));

    b1_arm_gate #(.NONCE_SEED(NONCE_SEED), .LUTS(LUTS), .SEMANTIC_GATE(SEMANTIC_GATE)) gate (
        .clk(clk), .rst_n(rst_n), .payload(payload), .tag_in(tag), .arm_strobe(arm_strobe),
        .key(key), .key_loaded(key_loaded), .mode_holdout(mode_holdout), .sweep_vector(sweep_vector), .sweep_active(sweep_active),
        .lut_q(lut_q), .scorer_arm(scorer_arm), .configuration_valid_hw(cfg_valid_hw),
        .scorer_busy(scorer_busy), .nonce(nonce), .hw_commit(hw_commit),
        .functional_readout(readout), .busy(gate_busy), .tag_ok(tag_ok), .sweep_done(sweep_done),
        .tables_match(tables_match), .recovery_required(recovery_required), .fault_code(fault_code));

    // The reused scorer: its `configuration_valid` is the gate's hardware latch and its
    // `arm` is the gate's pulse. Nothing else reaches either input.
    carrier_scorer #(.LUTS(LUTS)) scorer (
        .clk(clk), .rst_n(rst_n),
        .configuration_valid(cfg_valid_hw), .recovery_required(recovery_required),
        .arm(scorer_arm), .mode_holdout(mode_holdout),
        .vector(scorer_vector), .lut_q(lut_q),
        .busy(scorer_busy), .done(scorer_done), .armed_o(scorer_armed), .score_flat(score_flat));

    assign vector = sweep_active ? sweep_vector : scorer_vector;
endmodule
`default_nettype wire
