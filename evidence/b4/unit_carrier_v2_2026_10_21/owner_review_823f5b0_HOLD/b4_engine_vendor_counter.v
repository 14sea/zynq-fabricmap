// B4 carrier v2 — the observation engine: the pre-init sample, the init event (GSR through STARTUPE2,
// hardware-timed), the `set` steps of the stimulus, the cleanup and the close, as docs/b4_observation_contract.md
// sections 2.3, 5.1, 5.3, 6.3 require. Nothing here compares a sample with anything: the samples go to the
// GSR-immune slots raw and the host reads them.
//
// THE INIT EVENT (mechanism (b)). CTRL.INIT_REQ -> `init_pending` is persisted -> ASSERT_DELAY cycles (so the
// host's write response is long complete and no AXI transaction is in flight) -> `gsr_drive` is raised for
// PULSE cycles -> STARTUPE2.GSR -> every flip-flop of the PL returns to INIT: the target elements (the thing
// observed) and this engine's own state. The engine then WAKES from its INIT state, sees `init_pending`
// without `init_done`, counts RELEASE cycles, then SAMPLE_OFFSET, samples the eight Q outputs into slot 1
// (the init sample = the stimulus's step 0) and records `init_done`, `gsr_count + 1`. The slice inputs
// and the slice clock are 0 after the event by the same reset — the permitted init context. In silicon the
// pulse generator's flip-flops are reset by the GSR they raise, so the pulse is self-timed (its width the
// GSR tree's delay); on the bench the driver holds for PULSE cycles so the vendor models see a clean
// pulse — both end with the generator cleared and the engine in its reset state (the witness is
// `gsr_count`, exactly 1 per transaction, and the heartbeat restarting).
//
// REALISABILITY. One CE and one SR pin per slice: a `set` step whose ce or sr vector is not uniform (all
// 0 or all 1) cannot be applied and is refused with F_NOT_REALISABLE (sticky). The task stimulus of
// task-v0.2 draws per-element vectors; what that means is the unit's finding, not the engine's to hide.
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
    input  wire        rst_n,        // the configuration reset AND the GSR (b4_core): the engine's state
    input  wire        rst_n_raw,    // the configuration reset only: the pulse generator
    input  wire        armed,
    input  wire        recovery_required,
    input  wire        op_pre_sample, op_init_req, op_step, op_cleanup, op_close,
    input  wire [24:0] step_in,
    input  wire [7:0]  q_in,
    output reg         slice_clk,
    output reg         slice_ce,
    output reg         slice_sr,
    output reg  [7:0]  slice_d,
    output wire        gsr_drive,
    output reg  [7:0]  q_live,
    // persistent witnesses
    output wire        pre_sampled, init_pending, init_done, cleanup_done, closed_without_cleanup, cleanup_edge,
    output wire [7:0]  gsr_count,
    output wire [4:0]  step_index, slot_count,
    output wire        busy,
    output reg         step_done,
    output wire        idle,
    // the slots
    input  wire [4:0]  slot_addr_host,
    output wire [7:0]  slot_q,
    // to the gate
    output reg         fault_strobe,
    output reg  [3:0]  fault_code_o,
    output reg         close_strobe
);
    localparam [3:0] F_NOT_ARMED = 4'd5, F_NOT_REALISABLE = 4'd6, F_SEQUENCE = 4'd7, F_SLOT_OVERFLOW = 4'd8;

    // ---------------------------------------------------------------- the persistent witnesses
    //  flags: 0 pre_sampled, 1 init_pending, 2 init_done, 3 cleanup_done, 4 closed_without_cleanup, 5 cleanup_edge
    reg flags_we; reg [5:0] flags_d; wire [5:0] flags;
    b4_gsr_reg #(.W(6)) flags_store (.wclk(clk), .we(flags_we), .d(flags_d), .q(flags));
    assign {cleanup_edge, closed_without_cleanup, cleanup_done, init_done, init_pending, pre_sampled} = flags;
    reg gsr_we; reg [7:0] gsr_d;
    b4_gsr_reg #(.W(8)) gsr_store (.wclk(clk), .we(gsr_we), .d(gsr_d), .q(gsr_count));
    reg idx_we; reg [9:0] idx_d; wire [9:0] idx;
    b4_gsr_reg #(.W(10)) idx_store (.wclk(clk), .we(idx_we), .d(idx_d), .q(idx));
    assign step_index = idx[4:0]; assign slot_count = idx[9:5];
    reg slot_we; reg [4:0] slot_a_eng; reg [7:0] slot_d;
    wire [4:0] slot_a = slot_we ? slot_a_eng : slot_addr_host;
    b4_slot_ram slots (.wclk(clk), .we(slot_we), .a(slot_a), .d(slot_d), .q(slot_q));

    always @(posedge clk) q_live <= q_in;        // registered every cycle; no reset: it is what the pins show

    // ---------------------------------------------------------------- the GSR pulse generator
    reg fire; wire [7:0] pulse_cnt;
    assign gsr_drive = (pulse_cnt != 8'd0);
    wire [7:0] pulse_d = fire ? PULSE[7:0] : (pulse_cnt != 0 ? pulse_cnt - 8'd1 : 8'd0);
    genvar owner_bit;
    generate for (owner_bit = 0; owner_bit < 8; owner_bit = owner_bit + 1) begin : owner_vendor_counter
        FDCE #(.INIT(1'b0)) r (.Q(pulse_cnt[owner_bit]), .C(clk), .CE(1'b1), .CLR(~rst_n_raw), .D(pulse_d[owner_bit]));
    end endgenerate

    // ---------------------------------------------------------------- the sequencer
    localparam [3:0] S_IDLE = 4'd0, S_INIT_DELAY = 4'd1, S_RELEASE = 4'd2, S_OFFSET = 4'd3,
                     S_STEP_SETTLE = 4'd4, S_STEP_HOLD = 4'd5, S_CLEAN_SETTLE = 4'd6, S_CLEAN_HOLD = 4'd7, S_WRITE = 4'd8,
                     S_POST = 4'd9, S_STEP_DATA = 4'd10;
    reg [3:0] state; reg [7:0] cnt; reg [7:0] pending_slot_d; reg [4:0] pending_slot_a; reg [5:0] pending_flags; reg pending_flags_we;
    reg [9:0] pending_idx; reg pending_idx_we; reg pending_gsr;
    assign busy = (state != S_IDLE);
    assign idle = (state == S_IDLE) && !armed;
    wire ce_uniform = (step_in[15:8] == 8'h00) || (step_in[15:8] == 8'hFF);
    wire sr_uniform = (step_in[23:16] == 8'h00) || (step_in[23:16] == 8'hFF);
    wire op_any = op_pre_sample || op_init_req || op_step || op_cleanup || op_close;

    task refuse(input [3:0] code); begin fault_strobe <= 1'b1; fault_code_o <= code; end endtask

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE; cnt <= 8'd0; fire <= 1'b0;
            slice_clk <= 1'b0; slice_ce <= 1'b0; slice_sr <= 1'b0; slice_d <= 8'd0;
            step_done <= 1'b0; flags_we <= 0; flags_d <= 6'd0; gsr_we <= 0; gsr_d <= 8'd0; idx_we <= 0; idx_d <= 10'd0;
            slot_we <= 0; slot_a_eng <= 5'd0; slot_d <= 8'd0; fault_strobe <= 0; fault_code_o <= 4'd0; close_strobe <= 0;
            pending_slot_d <= 8'd0; pending_slot_a <= 5'd0; pending_flags <= 6'd0; pending_flags_we <= 0;
            pending_idx <= 10'd0; pending_idx_we <= 0; pending_gsr <= 0;
        end else begin
            fire <= 1'b0; flags_we <= 0; gsr_we <= 0; idx_we <= 0; slot_we <= 0; fault_strobe <= 0; close_strobe <= 0;
            case (state)
            S_IDLE: begin
                if (init_pending && !init_done && !gsr_drive) begin
                    // WAKE after the init event: the slice inputs and clock are at their reset values
                    cnt <= 8'd0; state <= S_RELEASE;
                end else if (op_any && (!armed || recovery_required)) begin
                    if (!recovery_required) refuse(F_NOT_ARMED);   // under recovery: refused silently, as the gate does
                end else if (op_pre_sample) begin
                    if (pre_sampled || init_done) refuse(F_SEQUENCE);
                    else begin
                        slot_we <= 1'b1; slot_a_eng <= 5'd0; slot_d <= q_live;
                        flags_we <= 1'b1; flags_d <= flags | 6'b000001;
                        idx_we <= 1'b1; idx_d <= {5'd1, 5'd0};
                    end
                end else if (op_init_req) begin
                    if (!pre_sampled || init_pending || init_done) refuse(F_SEQUENCE);
                    else begin
                        flags_we <= 1'b1; flags_d <= flags | 6'b000010;    // init_pending, persisted before the pulse
                        cnt <= 8'd0; state <= S_INIT_DELAY;
                    end
                end else if (op_step) begin
                    if (!init_done || cleanup_done) refuse(F_SEQUENCE);
                    else if (!ce_uniform || !sr_uniform) refuse(F_NOT_REALISABLE);
                    else if (slot_count >= 5'd31) refuse(F_SLOT_OVERFLOW);
                    else begin
                        // control first, data one cycle later: with a transparent latch the order in which ce / sr
                        // and d move is observable (a d that moves while the gate is still enabled is captured);
                        // applying the controls first makes the final state the one the model's atomic step gives
                        slice_ce <= step_in[8]; slice_sr <= step_in[16];
                        step_done <= 1'b0; state <= S_STEP_DATA;
                    end
                end else if (op_cleanup) begin
                    if (!init_done || cleanup_done) refuse(F_SEQUENCE);
                    else begin
                        slice_d <= 8'd0; slice_ce <= 1'b0; slice_sr <= 1'b0;
                        cnt <= 8'd0; state <= S_CLEAN_SETTLE;
                    end
                end else if (op_close) begin
                    // the close: the armed latch cleared at the gate; the witnesses cleared for the next
                    // transaction, except `closed_without_cleanup` which the NEXT record reads (the A5
                    // injection path, contract 5.6) and `gsr_count` which is cumulative per session
                    close_strobe <= 1'b1;
                    flags_we <= 1'b1; flags_d <= {1'b0, !cleanup_done, 4'd0};
                    idx_we <= 1'b1; idx_d <= 10'd0;
                    step_done <= 1'b0;
                end
            end
            S_INIT_DELAY: begin
                if (cnt == ASSERT_DELAY[7:0] - 8'd1) begin fire <= 1'b1; state <= S_IDLE; end
                else cnt <= cnt + 8'd1;
                // the GSR that follows resets this state machine; the sequence continues at the wake above
            end
            S_RELEASE: begin
                if (cnt == RELEASE[7:0] - 8'd1) begin cnt <= 8'd0; state <= S_OFFSET; end
                else cnt <= cnt + 8'd1;
            end
            S_OFFSET: begin
                if (cnt == SAMPLE_OFFSET[7:0] - 8'd1) begin
                    slot_we <= 1'b1; slot_a_eng <= 5'd1; slot_d <= q_live;
                    flags_we <= 1'b1; flags_d <= (flags & ~6'b000010) | 6'b000100;   // init_done, not pending
                    gsr_we <= 1'b1; gsr_d <= gsr_count + 8'd1;
                    idx_we <= 1'b1; idx_d <= {5'd2, 5'd0};
                    state <= S_POST;        // the stores take the write at the next edge; IDLE must not re-read the old flags
                end else cnt <= cnt + 8'd1;
            end
            S_STEP_DATA: begin
                slice_d <= step_in[7:0]; cnt <= 8'd0; state <= S_STEP_SETTLE;
            end
            S_STEP_SETTLE: begin
                if (cnt == SETTLE[7:0] - 8'd1) begin slice_clk <= step_in[24]; cnt <= 8'd0; state <= S_STEP_HOLD; end
                else cnt <= cnt + 8'd1;
            end
            S_STEP_HOLD: begin
                if (cnt == HOLD[7:0] - 8'd1) begin
                    slot_we <= 1'b1; slot_a_eng <= 5'd2 + step_index; slot_d <= q_live;
                    idx_we <= 1'b1; idx_d <= {slot_count + 5'd1, step_index + 5'd1};
                    step_done <= 1'b1; state <= S_IDLE;
                end else cnt <= cnt + 8'd1;
            end
            S_CLEAN_SETTLE: begin
                if (cnt == SETTLE[7:0] - 8'd1) begin
                    if (slice_clk) begin flags_we <= 1'b1; flags_d <= flags | 6'b100000; end   // cleanup_edge: a falling edge
                    slice_clk <= 1'b0; cnt <= 8'd0; state <= S_CLEAN_HOLD;
                end else cnt <= cnt + 8'd1;
            end
            S_CLEAN_HOLD: begin
                if (cnt == HOLD[7:0] - 8'd1) begin
                    slot_we <= 1'b1; slot_a_eng <= 5'd2 + step_index; slot_d <= q_live;
                    idx_we <= 1'b1; idx_d <= {slot_count + 5'd1, step_index};
                    state <= S_WRITE;
                end else cnt <= cnt + 8'd1;
            end
            S_WRITE: begin
                // the flags word is written after the slot so that one `we` per store suffices per cycle
                flags_we <= 1'b1; flags_d <= flags | 6'b001000;    // cleanup_done
                state <= S_POST;
            end
            S_POST: state <= S_IDLE;        // one cycle: every store has taken its write
            default: state <= S_IDLE;
            endcase
        end
    end
endmodule
`default_nettype wire
