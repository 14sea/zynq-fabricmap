// B4 carrier v2 ARM gate — the B1 gate (the instrument's p3_arm_gate) without the 64-vector sweep: the
// signature still binds commit ‖ tables-slot (zero under the contract) ‖ nonce, the nonce steps after
// EVERY attempt, a failure is a sticky fault, and `configuration_valid_hw` is the ONLY thing that lets the
// engine observe. What changed for v2: the gate's authority state — the nonce, the armed latch, the fault
// code and recovery — is GSR-IMMUNE (b4_gsr_reg), because the transaction's init event (GSR) comes AFTER
// the ARM and would otherwise reset the nonce to its seed (a replay would verify again) and clear the
// fault (fail-open). HW_COMMIT stays a flip-flop register: the host reads it before INIT_REQ.
// The engine's own faults (b4_engine) and its CLOSE arrive here and are persisted by the same logic.
`default_nettype none
module b4_gate #(
    parameter [63:0] NONCE_SEED = 64'h9E3779B97F4A7C15
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [639:0] payload,
    input  wire [127:0] tag_in,
    input  wire         arm_strobe,
    input  wire         arm_a5,            // the A5 context flag (CTRL bit 7): required when an injection is open, refused otherwise
    input  wire         injection_open,
    input  wire [127:0] key,
    input  wire         key_loaded,
    // from the engine
    input  wire         eng_fault_strobe,
    input  wire [3:0]   eng_fault_code,
    input  wire         close_strobe,
    // observations
    output wire [63:0]  nonce,
    output reg  [255:0] hw_commit,
    output reg          busy,
    output reg          tag_ok,
    output wire         armed,
    output wire         recovery_required,
    output wire [3:0]   fault_code,
    output wire         configuration_valid_hw
);
    localparam [3:0] F_NONE = 4'd0, F_SEQUENCE = 4'd7, F_ARM_NOKEY = 4'd12, F_ARM_AUTH = 4'd13;

    // ---------------------------------------------------------------- the persistent authority state
    reg nonce_we; reg [63:0] nonce_d;
    reg armed_we; reg armed_d;
    reg fault_we; reg [3:0] fault_d; reg recovery_d;
    b4_gsr_reg #(.W(64), .INIT(NONCE_SEED)) nonce_store (.wclk(clk), .we(nonce_we), .d(nonce_d), .q(nonce));
    b4_gsr_reg #(.W(1)) armed_store (.wclk(clk), .we(armed_we), .d(armed_d), .q(armed));
    b4_gsr_reg #(.W(4)) fault_store (.wclk(clk), .we(fault_we), .d(fault_d), .q(fault_code));
    b4_gsr_reg #(.W(1)) recovery_store (.wclk(clk), .we(fault_we), .d(recovery_d), .q(recovery_required));
    assign configuration_valid_hw = armed && !recovery_required;

    // ---------------------------------------------------------------- SipHash
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

    reg state;   // 0 idle, 1 verifying
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= 1'b0; busy <= 1'b0; sh_start <= 1'b0; hw_commit <= 256'd0; tag_ok <= 1'b0;
            nonce_we <= 0; nonce_d <= 64'd0; armed_we <= 0; armed_d <= 0; fault_we <= 0; fault_d <= F_NONE; recovery_d <= 0;
        end else begin
            sh_start <= 1'b0; nonce_we <= 0; armed_we <= 0; fault_we <= 0;
            // the engine's fault and close requests (never in the same cycle as a verification result:
            // the engine acts only while armed, and an ARM while armed is refused below)
            if (eng_fault_strobe) begin
                fault_we <= 1'b1; fault_d <= eng_fault_code; recovery_d <= 1'b1;
            end
            if (close_strobe) begin
                armed_we <= 1'b1; armed_d <= 1'b0; tag_ok <= 1'b0;
            end
            case (state)
            1'b0: begin
                if (arm_strobe && !busy && !recovery_required && (armed || (arm_a5 != injection_open))) begin
                    // an ARM while a transaction is open, or an ARM whose context does not match the carrier's state
                    // (the A5 flag without an open injection, or an open injection without the flag — contract 5.6):
                    // a sequence fault, nonce untouched
                    fault_we <= 1'b1; fault_d <= F_SEQUENCE; recovery_d <= 1'b1;
                end else if (arm_strobe && !busy && !recovery_required && !key_loaded) begin
                    // no key: the attempt is refused, consumes the nonce, and is a sticky fault
                    nonce_we <= 1'b1; nonce_d <= xorshift(nonce);
                    fault_we <= 1'b1; fault_d <= F_ARM_NOKEY; recovery_d <= 1'b1;
                end else if (arm_strobe && !busy && !recovery_required) begin
                    busy <= 1'b1; tag_ok <= 1'b0;
                    sh_start <= 1'b1;
                    state <= 1'b1;
                end
                // an ARM while recovery is required is refused silently: the fault is already latched
            end
            1'b1: if (sh_done) begin
                nonce_we <= 1'b1; nonce_d <= xorshift(nonce);      // consumed by THIS attempt whatever the outcome
                if (sh_tag == tag_in) begin
                    tag_ok <= 1'b1;
                    hw_commit <= payload[639:384];
                    armed_we <= 1'b1; armed_d <= 1'b1;             // the ONLY source of the armed latch
                end else begin
                    fault_we <= 1'b1; fault_d <= F_ARM_AUTH; recovery_d <= 1'b1;
                end
                busy <= 1'b0; state <= 1'b0;
            end
            endcase
        end
    end
endmodule
`default_nettype wire
