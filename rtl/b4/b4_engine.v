// B4 carrier v2 — the observation engine: the pre-init sample, the init event (GSR through STARTUPE2,
// hardware-timed), the `set` steps of the stimulus, the cleanup, the RESTORE event on the restored base (P9) and
// the close, as docs/b4_observation_contract.md sections 2.3, 5.1, 5.3, 5.4, 5.6, 6.3 require. Nothing here
// compares a sample with anything: the samples go to GSR-immune slots raw, with the inputs that were APPLIED.
//
// THE EVENTS (mechanism (b)). INIT_REQ / RESTORE_INIT -> the pending flag is persisted -> the bus gates stall new
// accesses (b4_axi_gate) -> after ASSERT_DELAY consecutive quiet cycles (nothing outstanding anywhere on the PS path)
// the engine loads the PULSE counter -> the counter, built of LUTRAM (GSR-immune), drives STARTUPE2.GSR for exactly
// PULSE clocks and clears itself -> every flip-flop of the PL returns to INIT: the target elements and this engine's
// own state. The engine WAKES from its reset state, finds the pending flag without its done flag, counts RELEASE then
// SAMPLE_OFFSET cycles, samples the eight Q outputs (slot 1 for the init event; `base_state` for the restore event),
// records the done flag and `gsr_count + 1`. The slice inputs and clock are 0 after the event by the same reset.
// The pulse is hardware-timed by construction (no flip-flop of the generator holds it), so a GSR-aware netlist bench
// sees the same width as the RTL bench; what the width DOES on this die (release skew, the Q effect) stays A8's.
//
// ONE RULE FOR OPERATIONS. The register file accepts a CTRL operation only when the engine and the gate are idle,
// exactly one operation is named and no other bit is set (anything else is SLVERR and changes nothing). An accepted
// STEP is LATCHED here (`cmd`): the live STEP_IN word may change while the step runs; the applied step does not.
// Out-of-phase operations are refused with F_SEQUENCE (sticky). Realisability: one CE and one SR pin per slice, so a
// `set` step whose ce or sr vector is not uniform is refused with F_NOT_REALISABLE.
//
// THE CLOSE. A normal CLOSE is accepted only after the restore event (restore_done): it clears the transaction's
// flags and the armed latch. CLOSE_INJECTION is the explicit A5 exception (contract 5.6, J2): accepted after the init
// event with no cleanup, it persists `injection_open` and leaves the inputs as they are; the next ARM must carry the
// A5 context flag (b4_gate), and that transaction's PRE_SAMPLE records `pre_context_a5` with the held inputs; its INIT_REQ
// then performs the RECORDED pre-init cleanup of contract 5.6 J3 (inputs and clock to 0 inside step 0, witness
// `pre_init_cleanup`) before the launch, so the event always enters the required context.
`default_nettype none
module b4_engine #(
    parameter integer ASSERT_DELAY  = 8,
    parameter integer PULSE         = 2,
    parameter integer RELEASE       = 16,
    parameter integer SAMPLE_OFFSET = 4,
    parameter integer SETTLE        = 4,
    parameter integer HOLD          = 4
) (
    input  wire        clk,
    input  wire        rst_n,        // the configuration reset AND the GSR (b4_core): the engine's flip-flop state
    input  wire        armed,
    input  wire        recovery_required,
    input  wire        bus_quiet,    // every gated bus path has nothing outstanding and nothing presented
    input  wire        op_pre_sample, op_init_req, op_step, op_cleanup, op_restore_init, op_close, op_close_injection,
    input  wire [24:0] step_in,
    input  wire [7:0]  q_in,
    output reg         slice_clk,
    output reg         slice_ce,
    output reg         slice_sr,
    output reg  [7:0]  slice_d,
    output wire        gsr_drive,
    output wire        stall,        // the bus gates hold new accesses from the request until the event's sample
    output reg  [7:0]  q_live,
    // persistent witnesses
    output wire        pre_sampled, init_pending, init_done, cleanup_done, cleanup_edge, restore_pending, restore_done,
    output wire        injection_open, pre_context_a5, pre_init_cleanup,
    output wire [7:0]  gsr_count, base_state,
    output wire [4:0]  step_index, slot_count,
    output wire        busy,
    output reg         step_done,
    output wire        idle,
    // the slots (the samples and the applied inputs)
    input  wire [4:0]  slot_addr_host,
    output wire [7:0]  slot_q,
    output wire [31:0] slot_in_q,
    // to the gate
    output reg         fault_strobe,
    output reg  [3:0]  fault_code_o,
    output reg         close_strobe
);
    localparam [3:0] F_NOT_ARMED = 4'd5, F_NOT_REALISABLE = 4'd6, F_SEQUENCE = 4'd7, F_SLOT_OVERFLOW = 4'd8;

    // ---------------------------------------------------------------- the persistent witnesses (LUTRAM)
    //  flags: 0 pre_sampled 1 init_pending 2 init_done 3 cleanup_done 4 cleanup_edge 5 restore_pending 6 restore_done
    //         7 injection_open 8 pre_context_a5 9 pre_init_cleanup
    reg flags_we; reg [9:0] flags_d; wire [9:0] flags;
    b4_gsr_reg #(.W(10)) flags_store (.wclk(clk), .we(flags_we), .d(flags_d), .q(flags));
    assign {pre_init_cleanup, pre_context_a5, injection_open, restore_done, restore_pending, cleanup_edge, cleanup_done, init_done, init_pending, pre_sampled} = flags;
    reg gsr_we; reg [7:0] gsr_d;
    b4_gsr_reg #(.W(8)) gsr_store (.wclk(clk), .we(gsr_we), .d(gsr_d), .q(gsr_count));
    reg idx_we; reg [9:0] idx_d; wire [9:0] idx;
    b4_gsr_reg #(.W(10)) idx_store (.wclk(clk), .we(idx_we), .d(idx_d), .q(idx));
    assign step_index = idx[4:0]; assign slot_count = idx[9:5];
    reg base_we; reg [7:0] base_d;
    b4_gsr_reg #(.W(8)) base_store (.wclk(clk), .we(base_we), .d(base_d), .q(base_state));
    reg slot_we; reg [4:0] slot_a_eng; reg [7:0] slot_d; reg [31:0] slot_in_d;
    wire [4:0] slot_a = slot_we ? slot_a_eng : slot_addr_host;
    b4_slot_ram slots (.wclk(clk), .we(slot_we), .a(slot_a), .d(slot_d), .q(slot_q));
    b4_gsr_ram32 slots_in (.wclk(clk), .we(slot_we), .a(slot_a), .d(slot_in_d), .q(slot_in_q));

    always @(posedge clk) q_live <= q_in;        // registered every cycle; no reset: it is what the pins show
    wire [31:0] in_live = {7'd0, slice_clk, {8{slice_sr}}, {8{slice_ce}}, slice_d};

    // ---------------------------------------------------------------- the GSR pulse: a LUTRAM thermometer shift
    // Loaded by `fire` with PULSE ones, it then runs itself: WE while non-zero, D = the word shifted right by one
    // (11 -> 01 -> 00). No flip-flop holds the pulse, so the GSR it raises cannot shorten it — PULSE clocks,
    // hardware-timed, the same in the RTL and in a GSR-aware netlist. A THERMOMETER, not a binary count: exactly one
    // bit changes per cycle, so the OR that drives STARTUPE2.GSR never glitches (a binary 2 -> 1 is a two-bit change
    // and the resolved global net showed a delta-cycle 1 -> 0 -> 1 inside the pulse — a hazard on an asynchronous
    // reset net, found by the vendor-model bench and removed here).
    reg fire; wire [3:0] pulse_cnt;
    wire pulse_we = fire || (pulse_cnt != 4'd0);
    wire [3:0] pulse_d = fire ? ((4'd1 << PULSE) - 4'd1) : (pulse_cnt >> 1);
    b4_gsr_reg #(.W(4)) pulse_store (.wclk(clk), .we(pulse_we), .d(pulse_d), .q(pulse_cnt));
    assign gsr_drive = (pulse_cnt != 4'd0);
    assign stall = (init_pending && !init_done) || (restore_pending && !restore_done);

    // ---------------------------------------------------------------- the sequencer
    localparam [3:0] S_IDLE = 4'd0, S_LAUNCH = 4'd1, S_RELEASE = 4'd2, S_OFFSET = 4'd3, S_STEP_CTRL = 4'd4, S_STEP_DATA = 4'd5,
                     S_STEP_SETTLE = 4'd6, S_STEP_HOLD = 4'd7, S_CLEAN_SETTLE = 4'd8, S_CLEAN_HOLD = 4'd9, S_WRITE = 4'd10, S_POST = 4'd11,
                     S_PRECLEAN_SETTLE = 4'd12, S_PRECLEAN_HOLD = 4'd13;
    reg [3:0] state; reg [7:0] cnt; reg [24:0] cmd; reg restoring;
    assign busy = (state != S_IDLE);
    assign idle = (state == S_IDLE) && !armed && !injection_open && (in_live[24:0] == 25'd0);
    wire ce_uniform = (step_in[15:8] == 8'h00) || (step_in[15:8] == 8'hFF);
    wire sr_uniform = (step_in[23:16] == 8'h00) || (step_in[23:16] == 8'hFF);
    wire op_any = op_pre_sample || op_init_req || op_step || op_cleanup || op_restore_init || op_close || op_close_injection;
    wire wake_init = init_pending && !init_done && !gsr_drive;
    wire wake_restore = restore_pending && !restore_done && !gsr_drive;

    task refuse(input [3:0] code); begin fault_strobe <= 1'b1; fault_code_o <= code; end endtask
    task write_sample(input [4:0] a, input [31:0] inputs); begin
        slot_we <= 1'b1; slot_a_eng <= a; slot_d <= q_live; slot_in_d <= inputs;
    end endtask

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE; cnt <= 8'd0; fire <= 1'b0; cmd <= 25'd0; restoring <= 1'b0;
            slice_clk <= 1'b0; slice_ce <= 1'b0; slice_sr <= 1'b0; slice_d <= 8'd0;
            step_done <= 1'b0; flags_we <= 0; flags_d <= 10'd0; gsr_we <= 0; gsr_d <= 8'd0; idx_we <= 0; idx_d <= 10'd0;
            base_we <= 0; base_d <= 8'd0; slot_we <= 0; slot_a_eng <= 5'd0; slot_d <= 8'd0; slot_in_d <= 32'd0;
            fault_strobe <= 0; fault_code_o <= 4'd0; close_strobe <= 0;
        end else begin
            fire <= 1'b0; flags_we <= 0; gsr_we <= 0; idx_we <= 0; base_we <= 0; slot_we <= 0; fault_strobe <= 0; close_strobe <= 0;
            case (state)
            S_IDLE: begin
                if (wake_init || wake_restore) begin
                    // WAKE after an event: the slice inputs and clock are at their reset values
                    restoring <= wake_restore && !wake_init; cnt <= 8'd0; state <= S_RELEASE;
                end else if (op_any && (!armed || recovery_required)) begin
                    if (!recovery_required) refuse(F_NOT_ARMED);   // under recovery: refused silently, as the gate does
                end else if (op_pre_sample) begin
                    if (pre_sampled || init_done) refuse(F_SEQUENCE);
                    else begin
                        write_sample(5'd0, in_live);
                        flags_we <= 1'b1; flags_d <= (flags & 10'b0010000000) | 10'b0000000001 | (injection_open ? 10'b0100000000 : 10'd0);
                        idx_we <= 1'b1; idx_d <= {5'd1, 5'd0};
                        state <= S_POST;
                    end
                end else if (op_init_req) begin
                    if (!pre_sampled || init_pending || init_done) refuse(F_SEQUENCE);
                    else if (in_live[24:0] != 25'd0) begin
                        // the inputs are held (an A5 injection, contract 5.6 J3): the pre-init sample is already in slot 0,
                        // so a RECORDED cleanup-like operation inside step 0's context brings the inputs and the clock to
                        // 0 (control first, then a falling edge if the clock is 1) BEFORE the event is launched; the
                        // witness `pre_init_cleanup` is persisted with init_pending
                        flags_we <= 1'b1; flags_d <= flags | 10'b1000000010;
                        slice_d <= 8'd0; slice_ce <= 1'b0; slice_sr <= 1'b0;
                        cnt <= 8'd0; state <= S_PRECLEAN_SETTLE;
                    end else begin
                        flags_we <= 1'b1; flags_d <= flags | 10'b0000000010;    // init_pending: persisted, the stall begins
                        cnt <= 8'd0; state <= S_LAUNCH;
                    end
                end else if (op_step) begin
                    if (!init_done || cleanup_done) refuse(F_SEQUENCE);
                    else if (!ce_uniform || !sr_uniform) refuse(F_NOT_REALISABLE);
                    else if (slot_count >= 5'd30) refuse(F_SLOT_OVERFLOW);
                    else begin
                        cmd <= step_in; step_done <= 1'b0; state <= S_STEP_CTRL;   // the accepted command, latched
                    end
                end else if (op_cleanup) begin
                    if (!init_done || cleanup_done) refuse(F_SEQUENCE);
                    else begin
                        slice_d <= 8'd0; slice_ce <= 1'b0; slice_sr <= 1'b0;
                        cnt <= 8'd0; state <= S_CLEAN_SETTLE;
                    end
                end else if (op_restore_init) begin
                    if (!cleanup_done || restore_pending || restore_done) refuse(F_SEQUENCE);
                    else begin
                        flags_we <= 1'b1; flags_d <= flags | 10'b0000100000;    // restore_pending
                        cnt <= 8'd0; state <= S_LAUNCH;
                    end
                end else if (op_close) begin
                    if (!restore_done) refuse(F_SEQUENCE);
                    else begin
                        close_strobe <= 1'b1;
                        flags_we <= 1'b1; flags_d <= 10'd0;
                        idx_we <= 1'b1; idx_d <= 10'd0;
                        step_done <= 1'b0; state <= S_POST;
                    end
                end else if (op_close_injection) begin
                    if (!init_done || cleanup_done) refuse(F_SEQUENCE);
                    else begin
                        close_strobe <= 1'b1;
                        flags_we <= 1'b1; flags_d <= 10'b0010000000;             // injection_open; the inputs stay as they are
                        idx_we <= 1'b1; idx_d <= 10'd0;
                        step_done <= 1'b0; state <= S_POST;
                    end
                end
            end
            S_PRECLEAN_SETTLE: begin
                if (cnt == SETTLE[7:0] - 8'd1) begin slice_clk <= 1'b0; cnt <= 8'd0; state <= S_PRECLEAN_HOLD; end
                else cnt <= cnt + 8'd1;
            end
            S_PRECLEAN_HOLD: begin
                if (cnt == HOLD[7:0] - 8'd1) begin cnt <= 8'd0; state <= S_LAUNCH; end   // the event context: inputs 0, clock low
                else cnt <= cnt + 8'd1;
            end
            S_LAUNCH: begin
                // ASSERT_DELAY consecutive quiet cycles on every gated path, then the pulse is loaded
                if (!bus_quiet) cnt <= 8'd0;
                else if (cnt == ASSERT_DELAY[7:0] - 8'd1) begin fire <= 1'b1; state <= S_IDLE; end
                else cnt <= cnt + 8'd1;
                // the GSR that follows resets this state machine; the sequence continues at the wake above
            end
            S_RELEASE: begin
                if (cnt == RELEASE[7:0] - 8'd1) begin cnt <= 8'd0; state <= S_OFFSET; end
                else cnt <= cnt + 8'd1;
            end
            S_OFFSET: begin
                if (cnt == SAMPLE_OFFSET[7:0] - 8'd1) begin
                    if (restoring) begin
                        base_we <= 1'b1; base_d <= q_live;
                        flags_we <= 1'b1; flags_d <= (flags & ~10'b0000100000) | 10'b0001000000;   // restore_done, not pending
                    end else begin
                        write_sample(5'd1, 32'd0);
                        flags_we <= 1'b1; flags_d <= (flags & ~10'b0000000010) | 10'b0000000100;   // init_done, not pending
                        idx_we <= 1'b1; idx_d <= {5'd2, 5'd0};
                    end
                    gsr_we <= 1'b1; gsr_d <= gsr_count + 8'd1;
                    state <= S_POST;
                end else cnt <= cnt + 8'd1;
            end
            S_STEP_CTRL: begin
                // control first, data one cycle later: with a transparent latch the order in which ce / sr and d move
                // is observable; applying the controls first gives the final state of the model's atomic step
                slice_ce <= cmd[8]; slice_sr <= cmd[16]; state <= S_STEP_DATA;
            end
            S_STEP_DATA: begin
                slice_d <= cmd[7:0]; cnt <= 8'd0; state <= S_STEP_SETTLE;
            end
            S_STEP_SETTLE: begin
                if (cnt == SETTLE[7:0] - 8'd1) begin slice_clk <= cmd[24]; cnt <= 8'd0; state <= S_STEP_HOLD; end
                else cnt <= cnt + 8'd1;
            end
            S_STEP_HOLD: begin
                if (cnt == HOLD[7:0] - 8'd1) begin
                    write_sample(5'd2 + step_index, {7'd0, cmd[24], {8{cmd[16]}}, {8{cmd[8]}}, cmd[7:0]});
                    idx_we <= 1'b1; idx_d <= {slot_count + 5'd1, step_index + 5'd1};
                    step_done <= 1'b1; state <= S_POST;
                end else cnt <= cnt + 8'd1;
            end
            S_CLEAN_SETTLE: begin
                if (cnt == SETTLE[7:0] - 8'd1) begin
                    if (slice_clk) begin flags_we <= 1'b1; flags_d <= flags | 10'b0000010000; end   // cleanup_edge: a falling edge
                    slice_clk <= 1'b0; cnt <= 8'd0; state <= S_CLEAN_HOLD;
                end else cnt <= cnt + 8'd1;
            end
            S_CLEAN_HOLD: begin
                if (cnt == HOLD[7:0] - 8'd1) begin
                    write_sample(5'd2 + step_index, 32'd0);
                    idx_we <= 1'b1; idx_d <= {slot_count + 5'd1, step_index};
                    state <= S_WRITE;
                end else cnt <= cnt + 8'd1;
            end
            S_WRITE: begin
                flags_we <= 1'b1; flags_d <= flags | 10'b0000001000;    // cleanup_done (after the slot: one `we` per store per cycle)
                state <= S_POST;
            end
            S_POST: state <= S_IDLE;        // one cycle: every store has taken its write before IDLE re-reads it
            default: state <= S_IDLE;
            endcase
        end
    end
endmodule
`default_nettype wire
