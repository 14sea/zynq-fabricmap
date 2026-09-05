// The B1 ARM gate — the instrument's p3_arm_gate with ONE parameter, SEMANTIC_GATE.
//
// SEMANTIC_GATE = 1 reproduces the instrument's gate exactly (readout must equal the signed
// expected tables, else F_ARM_TABLE). SEMANTIC_GATE = 0 is the B1 noninterference contract
// (docs/b1_carrier_contract.md): the signature still binds commit ‖ tables-slot ‖ nonce and
// the sweep still runs, but the readout is NOT compared with anything the host supplied —
// the host must not attest semantics before the measurement, so `tables_match` becomes an
// observation only and configuration_valid_hw = tag_ok ∧ sweep_done ∧ ¬recovery ∧ fault==0.
// The instrument's original header follows.
//
// The ARM gate — the trusted enforcement point of docs/p3_architecture.md §3.
//
//   staging (24 words, write-only)  ──┐
//   nonce (xorshift, steps per ARM) ──┼─► SipHash-2-4-128 verify ─► tag_ok
//                                     │            │ ok
//                                     │   64-vector sweep of the six LUTs ─► readout
//                                     │            │
//                                     │   readout == expected_tables ─► tables_match
//                                     └─► configuration_valid_hw = tag_ok ∧ tables_match
//                                                      ∧ ¬recovery_required ∧ fault==0
//   scorer.arm pulses ONLY from configuration_valid_hw rising. No other ARM path exists.
//
// Every failure is a sticky fault (recovery_required) that only a reset clears, and the
// nonce steps after EVERY attempt, so a replayed payload can never verify twice.
// The key is NOT a constant: it arrives from the write-once key register (p3_axil) that the
// signer principal provisions after configuration; an ARM before that is F_ARM_NOKEY.
`default_nettype none
module b1_arm_gate #(
    parameter [63:0]  NONCE_SEED = 64'h9E3779B97F4A7C15,
    parameter integer LUTS       = 6,
    parameter integer SEMANTIC_GATE = 0   // 0 = B1 contract (no semantic compare); 1 = the instrument's gate
) (
    input  wire         clk,
    input  wire         rst_n,
    // staging registers, written by the host through the register file
    input  wire [639:0] payload,          // 20 words: commit[8] ‖ tables[12], word 0 at the top
    input  wire [127:0] tag_in,           // 4 words
    input  wire         arm_strobe,       // CTRL bit 6 write
    input  wire [127:0] key,              // from the write-once key register
    input  wire         key_loaded,       // ARM is refused (F_ARM_NOKEY) until the signer provisioned the key
    input  wire         mode_holdout,
    // the LUTs
    output reg  [5:0]   sweep_vector,
    output reg          sweep_active,     // when 1 the mux hands `sweep_vector` to the LUTs
    input  wire [LUTS-1:0] lut_q,
    // the scorer
    output reg          scorer_arm,       // one-cycle pulse
    output wire         configuration_valid_hw,
    input  wire         scorer_busy,
    // observations (read-only registers)
    output reg  [63:0]  nonce,
    output reg  [255:0] hw_commit,        // the commit the gate verified (latched on tag_ok)
    output reg  [383:0] functional_readout,
    output reg          busy,
    output reg          tag_ok,
    output reg          sweep_done,
    output reg          tables_match,
    output reg          recovery_required,
    output reg  [3:0]   fault_code
);
    localparam [3:0] F_NONE = 4'd0, F_ARM_NOKEY = 4'd12, F_ARM_AUTH = 4'd13, F_ARM_TABLE = 4'd15;

    // ------------------------------------------------------------------ SipHash
    reg          sh_start;
    wire         sh_busy, sh_done;
    wire [127:0] sh_tag;
    p3_siphash #(.MSG_WORDS(20)) siphash (
        .clk(clk), .rst_n(rst_n), .key(key), .start(sh_start), .msg(payload), .nonce(nonce),
        .busy(sh_busy), .done(sh_done), .tag(sh_tag));

    function [63:0] xorshift;
        input [63:0] x;
        reg [63:0] y;
        begin
            y = x ^ (x << 13);
            y = y ^ (y >> 7);
            y = y ^ (y << 17);
            xorshift = y;
        end
    endfunction

    // words 8..19 = six 64-bit tables, table 0 at the TOP ([383:320]); the readout is laid
    // out identically so the comparator compares LUT i with table i.
    wire [383:0] expected_tables = payload[383:0];

    reg [2:0] state;   // 0 idle, 1 verifying, 2 sweeping, 3 compare, 4 armed
    reg [6:0] vec;
    reg       valid_latch;
    assign configuration_valid_hw = valid_latch;

    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= 3'd0; busy <= 1'b0; sh_start <= 1'b0; scorer_arm <= 1'b0;
            nonce <= NONCE_SEED; hw_commit <= 256'd0; functional_readout <= 384'd0;
            tag_ok <= 1'b0; sweep_done <= 1'b0; tables_match <= 1'b0;
            recovery_required <= 1'b0; fault_code <= F_NONE;     // fail-closed: nothing armed
            sweep_vector <= 6'd0; sweep_active <= 1'b0; vec <= 7'd0; valid_latch <= 1'b0;
        end else begin
            sh_start   <= 1'b0;
            scorer_arm <= 1'b0;
            case (state)
            3'd0: begin
                if (arm_strobe && !busy && !recovery_required && !scorer_busy && !key_loaded) begin
                    // no key: the attempt is refused, consumes the nonce, and is a sticky fault
                    nonce <= xorshift(nonce);
                    fault_code <= F_ARM_NOKEY; recovery_required <= 1'b1; valid_latch <= 1'b0;
                end else if (arm_strobe && !busy && !recovery_required && !scorer_busy) begin
                    busy <= 1'b1; tag_ok <= 1'b0; sweep_done <= 1'b0; tables_match <= 1'b0;
                    valid_latch <= 1'b0;
                    sh_start <= 1'b1;
                    state <= 3'd1;
                end
                // an ARM while recovery is required is refused silently: the fault is
                // already latched and only a reset clears it
            end
            3'd1: if (sh_done) begin
                // the nonce is consumed by THIS attempt whatever the outcome
                nonce <= xorshift(nonce);
                if (sh_tag == tag_in) begin
                    tag_ok <= 1'b1;
                    hw_commit <= payload[639:384];
                    sweep_active <= 1'b1; sweep_vector <= 6'd0; vec <= 7'd0;
                    state <= 3'd2;
                end else begin
                    fault_code <= F_ARM_AUTH; recovery_required <= 1'b1;
                    busy <= 1'b0; state <= 3'd0;
                end
            end
            3'd2: begin
                // at this edge `sweep_vector` has been presented for a full cycle and
                // `lut_q` is its combinational output: record bit `sweep_vector` of each LUT
                for (i = 0; i < LUTS; i = i + 1)
                    functional_readout[(LUTS-1-i)*64 + sweep_vector] <= lut_q[i];   // table i at the top
                if (sweep_vector == 6'd63) begin
                    sweep_active <= 1'b0; sweep_done <= 1'b1; state <= 3'd3;
                end else begin
                    sweep_vector <= sweep_vector + 6'd1;
                end
            end
            3'd3: begin
                // tables_match is always computed (an observation the host may read); under
                // the B1 contract it does NOT gate: the readout is handed over raw
                tables_match <= (functional_readout == expected_tables);
                if (SEMANTIC_GATE == 0 || functional_readout == expected_tables) begin
                    valid_latch <= 1'b1;
                    scorer_arm <= 1'b1;                 // the ONLY source of scorer.arm
                    state <= 3'd4;
                end else begin
                    fault_code <= F_ARM_TABLE; recovery_required <= 1'b1;
                    busy <= 1'b0; state <= 3'd0;
                end
            end
            3'd4: begin
                busy <= 1'b0; state <= 3'd0;           // armed; the scorer runs on the latch
            end
            default: state <= 3'd0;
            endcase
        end
    end
endmodule
`default_nettype wire
