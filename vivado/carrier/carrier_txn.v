// Claim B round 1 carrier — the two-pass transaction.
//
// Replaces the single-shot guard FSM. It owns ICAPE2, it is the only driver of
// `configuration_valid`, and it enforces the two-pass contract of the carrier design.
//
// THE GUARANTEE, and it is weaker than the one it replaces — say the new one, not the old
// ----------------------------------------------------------------------------------------
// NOT "the entire candidate was validated before any write". The buffer holds 536 words,
// one envelope, because the left-of-flush region has no BRAM column. What holds is:
//
//     each envelope, before it is written, is word-for-word identical to
//     the same envelope validated in pass 1
//
// Pass 1 validates all three with ICAPE2 untouched and records a CRC-32 per envelope.
// Pass 2 reloads each envelope, re-runs the control-trace and FAR rules, requires the CRC
// to equal pass 1's for THAT envelope, and only then writes it.
//
// WHAT THE CRC CAN AND CANNOT AUTHORISE
// -------------------------------------
// The CRC and the immediate readback compare are a TRANSMISSION AND HARDWARE INTERLOCK.
// The word-by-word control and FAR rules guarantee only that a CRC collision cannot
// silently change the control skeleton or the write addresses; they cannot authorise
// payload CONTENT. The payload's authority is
//
//     host-gated candidate SHA-256 == streamed readback SHA-256
//
// computed BY THE HOST from readback bytes it actually received, in this same transaction.
// That is why the readback words are placed back into the buffer for the host to read:
// a design where the host only ever learns a boolean would make `configuration_valid` the
// authority over payload content, and it is not.
//
// FAIL-CLOSED, EVERYWHERE
// -----------------------
// An interrupted pass 2, an out-of-order envelope, a CRC mismatch, a readback mismatch, a
// timeout or a reset all leave `configuration_valid` low. Whatever was already written is
// NOT a candidate and can never be scored — the scorer gates on `configuration_valid`, so
// a partial write cannot reach it. Recovery is restoring the pinned base or reloading the
// carrier, and neither is this module's business.

`default_nettype none

module carrier_txn #(
    parameter integer ENVELOPES     = 3,
    parameter integer ENV_WORDS     = 536,
    parameter integer FRAME_WORDS   = 101,
    parameter integer FRAMES_PER_ENV = 5,       // 4 target + 1 flush
    parameter integer PAYLOAD_START = 23,
    parameter integer TIMEOUT       = 1 << 20
) (
    input  wire        clk,
    input  wire        rst_n,

    // control: one pulse each, with the envelope the host claims to have loaded
    input  wire        begin_txn,      // start a transaction: clears everything
    input  wire        validate_env,   // pass 1 step for `env_index`
    input  wire        write_env,      // pass 2 step for `env_index`
    input  wire [1:0]  env_index,

    output reg         busy,
    output reg         fault,
    output reg  [3:0]  fault_code,
    output reg  [1:0]  expect_env,     // which envelope the transaction will accept next
    output reg         pass1_complete,
    output reg         configuration_valid,

    // the resident envelope buffer
    output wire [11:0] buf_addr,
    input  wire [31:0] buf_data,
    output reg         buf_we,         // readback write-back, for the host to read
    output reg  [11:0] buf_waddr,
    output reg  [31:0] buf_wdata,

    // the validator
    output reg         val_start,
    input  wire        val_busy,
    input  wire        val_ok,
    input  wire        val_fault,

    // the CRC engine
    output reg         crc_clear,
    output reg         crc_valid,
    input  wire [31:0] crc_value,

    // ICAPE2
    output wire        icap_csib,
    output wire        icap_rdwrb,
    output wire [31:0] icap_din,
    input  wire [31:0] icap_dout
);
    localparam [3:0] F_NONE     = 4'd0,
                     F_ORDER    = 4'd1,   // envelope out of sequence
                     F_VALIDATE = 4'd2,   // the validator refused it
                     F_CRC      = 4'd3,   // pass 2 bytes are not pass 1 bytes
                     F_READBACK = 4'd4,
                     F_TIMEOUT  = 4'd5,
                     F_PHASE    = 4'd6;   // a write before pass 1 completed

    localparam [3:0] S_IDLE   = 4'd0,
                     S_P1_CRC = 4'd1,
                     S_P1_VAL = 4'd2,
                     S_P2_CRC = 4'd3,
                     S_P2_VAL = 4'd4,
                     S_WRITE  = 4'd5,
                     S_RDBACK = 4'd6,
                     S_ENVDONE= 4'd7,
                     S_DONE   = 4'd8,
                     S_FAULT  = 4'd9;

    reg [3:0]  state;
    reg [9:0]  pos;          // word within the envelope being streamed
    reg [9:0]  pos_d;
    reg        valid_d;
    reg        last_issued;
    reg [31:0] watchdog;
    reg        mismatch;
    reg [31:0] pass1_crc [0:ENVELOPES-1];
    reg [1:0]  cur_env;

    // The validator's `ok` and `fault` are LEVELS that persist until its next start, so a
    // waiter that samples them on entry accepts the PREVIOUS envelope's verdict and
    // finishes before the validator has run. That is exactly what happened: the buffer was
    // then rewritten with the next envelope mid-validation, and envelope 1 was judged
    // against envelope 2's bytes. The verdict is only read after the validator has been
    // observed busy for this request.
    reg        val_seen_busy;

    localparam integer PAYLOAD_WORDS = FRAMES_PER_ENV * FRAME_WORDS;   // 505

    // During a write the datum is the candidate word; during readback the address walks
    // the payload while the write-back trails it, which is safe because the read index
    // (PAYLOAD_START + i) is always ahead of the write index (i).
    assign buf_addr    = (state == S_RDBACK) ? (PAYLOAD_START + pos) : pos;
    assign icap_din    = buf_data;
    assign icap_csib   = !((state == S_WRITE || state == S_RDBACK) && valid_d);
    assign icap_rdwrb  = (state == S_RDBACK);

    integer k;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state               <= S_IDLE;
            busy                <= 1'b0;
            fault               <= 1'b0;
            fault_code          <= F_NONE;
            configuration_valid <= 1'b0;
            pass1_complete      <= 1'b0;
            expect_env          <= 2'd0;
            cur_env             <= 2'd0;
            pos                 <= 10'd0;
            pos_d               <= 10'd0;
            valid_d             <= 1'b0;
            last_issued         <= 1'b0;
            watchdog            <= 32'd0;
            mismatch            <= 1'b0;
            val_seen_busy       <= 1'b0;
            val_start           <= 1'b0;
            crc_clear           <= 1'b0;
            crc_valid           <= 1'b0;
            buf_we              <= 1'b0;
            for (k = 0; k < ENVELOPES; k = k + 1) pass1_crc[k] <= 32'd0;
        end else begin
            val_start <= 1'b0;
            crc_clear <= 1'b0;
            crc_valid <= 1'b0;
            buf_we    <= 1'b0;

            case (state)
                S_IDLE: begin
                    busy <= 1'b0;
                    if (begin_txn) begin
                        // A new transaction discards everything, including any standing
                        // confirmation: the fabric is about to change.
                        configuration_valid <= 1'b0;
                        pass1_complete      <= 1'b0;
                        fault               <= 1'b0;
                        fault_code          <= F_NONE;
                        mismatch            <= 1'b0;
                        expect_env          <= 2'd0;
                    end else if (validate_env) begin
                        if (env_index != expect_env || pass1_complete) begin
                            fault_code <= (pass1_complete) ? F_PHASE : F_ORDER;
                            state      <= S_FAULT;
                        end else begin
                            cur_env   <= env_index;
                            busy      <= 1'b1;
                            crc_clear <= 1'b1;
                            pos       <= 10'd0;
                            valid_d   <= 1'b0;
                            last_issued <= 1'b0;
                            watchdog  <= 32'd0;
                            val_seen_busy <= 1'b0;
                            state     <= S_P1_CRC;
                        end
                    end else if (write_env) begin
                        // RULE: configuration_valid is cleared when the FIRST write of
                        // pass 2 is accepted — before a single ICAP word goes out.
                        configuration_valid <= 1'b0;
                        if (!pass1_complete) begin
                            fault_code <= F_PHASE;
                            state      <= S_FAULT;
                        end else if (env_index != expect_env) begin
                            fault_code <= F_ORDER;
                            state      <= S_FAULT;
                        end else begin
                            cur_env   <= env_index;
                            busy      <= 1'b1;
                            crc_clear <= 1'b1;
                            pos       <= 10'd0;
                            valid_d   <= 1'b0;
                            last_issued <= 1'b0;
                            watchdog  <= 32'd0;
                            val_seen_busy <= 1'b0;
                            state     <= S_P2_CRC;
                        end
                    end
                end

                // ---- both passes: CRC the resident envelope, then validate it
                S_P1_CRC, S_P2_CRC: begin
                    watchdog <= watchdog + 32'd1;
                    if (watchdog > TIMEOUT) begin
                        fault_code <= F_TIMEOUT;
                        state      <= S_FAULT;
                    end else begin
                        if (valid_d) crc_valid <= 1'b1;
                        pos_d   <= pos;
                        valid_d <= 1'b1;
                        if (valid_d && last_issued && pos_d == ENV_WORDS - 1) begin
                            val_start <= 1'b1;
                            state     <= (state == S_P1_CRC) ? S_P1_VAL : S_P2_VAL;
                        end else if (!last_issued) begin
                            if (pos == ENV_WORDS - 1) last_issued <= 1'b1;
                            else                      pos <= pos + 10'd1;
                        end
                    end
                end

                S_P1_VAL: begin
                    watchdog <= watchdog + 32'd1;
                    if (val_busy) val_seen_busy <= 1'b1;
                    if (watchdog > TIMEOUT) begin
                        fault_code <= F_TIMEOUT;
                        state      <= S_FAULT;
                    end else if (!val_seen_busy || val_busy) begin
                        // still this request's validation; the levels below are stale
                    end else if (val_fault) begin
                        fault_code <= F_VALIDATE;
                        state      <= S_FAULT;
                    end else if (val_ok) begin
                        pass1_crc[cur_env] <= crc_value;
                        if (cur_env == ENVELOPES - 1) begin
                            pass1_complete <= 1'b1;
                            expect_env     <= 2'd0;   // pass 2 starts from 0 again
                        end else begin
                            expect_env <= cur_env + 2'd1;
                        end
                        busy  <= 1'b0;
                        state <= S_IDLE;
                    end
                end

                S_P2_VAL: begin
                    watchdog <= watchdog + 32'd1;
                    if (val_busy) val_seen_busy <= 1'b1;
                    if (watchdog > TIMEOUT) begin
                        fault_code <= F_TIMEOUT;
                        state      <= S_FAULT;
                    end else if (!val_seen_busy || val_busy) begin
                        // still this request's validation; the levels below are stale
                    end else if (val_fault) begin
                        fault_code <= F_VALIDATE;
                        state      <= S_FAULT;
                    end else if (val_ok) begin
                        // The whole point of two passes: these bytes must be the bytes
                        // pass 1 judged, for THIS envelope.
                        if (crc_value != pass1_crc[cur_env]) begin
                            fault_code <= F_CRC;
                            state      <= S_FAULT;
                        end else begin
                            pos         <= 10'd0;
                            pos_d       <= 10'd0;
                            valid_d     <= 1'b0;
                            last_issued <= 1'b0;
                            watchdog    <= 32'd0;
                            state       <= S_WRITE;
                        end
                    end
                end

                // ---- pass 2: stream the payload, then read it back and compare
                S_WRITE: begin
                    watchdog <= watchdog + 32'd1;
                    if (watchdog > TIMEOUT) begin
                        fault_code <= F_TIMEOUT;
                        state      <= S_FAULT;
                    end else begin
                        pos_d   <= pos;
                        valid_d <= 1'b1;
                        if (valid_d && last_issued && pos_d == ENV_WORDS - 1) begin
                            pos         <= 10'd0;
                            pos_d       <= 10'd0;
                            valid_d     <= 1'b0;
                            last_issued <= 1'b0;
                            watchdog    <= 32'd0;
                            state       <= S_RDBACK;
                        end else if (!last_issued) begin
                            if (pos == ENV_WORDS - 1) last_issued <= 1'b1;
                            else                      pos <= pos + 10'd1;
                        end
                    end
                end

                S_RDBACK: begin
                    watchdog <= watchdog + 32'd1;
                    if (watchdog > TIMEOUT) begin
                        fault_code <= F_TIMEOUT;
                        state      <= S_FAULT;
                    end else begin
                        if (valid_d) begin
                            // compare against the candidate payload word ...
                            if (icap_dout !== buf_data) mismatch <= 1'b1;
                            // ... and hand the readback word to the host. The write index
                            // trails the read index by PAYLOAD_START, so nothing still
                            // needed is overwritten.
                            buf_we    <= 1'b1;
                            buf_waddr <= {2'd0, pos_d};
                            buf_wdata <= icap_dout;
                        end
                        pos_d   <= pos;
                        valid_d <= 1'b1;
                        if (valid_d && last_issued && pos_d == PAYLOAD_WORDS - 1) begin
                            state <= S_ENVDONE;
                        end else if (!last_issued) begin
                            if (pos == PAYLOAD_WORDS - 1) last_issued <= 1'b1;
                            else                          pos <= pos + 10'd1;
                        end
                    end
                end

                S_ENVDONE: begin
                    if (mismatch) begin
                        fault_code <= F_READBACK;
                        state      <= S_FAULT;
                    end else if (cur_env == ENVELOPES - 1) begin
                        state <= S_DONE;
                    end else begin
                        expect_env <= cur_env + 2'd1;
                        busy       <= 1'b0;
                        state      <= S_IDLE;
                    end
                end

                S_DONE: begin
                    // The ONLY assignment of 1 in this module, reached only when all three
                    // envelopes have been written and read back with no mismatch and with
                    // every CRC equal to pass 1's.
                    configuration_valid <= 1'b1;
                    busy                <= 1'b0;
                    state               <= S_IDLE;
                end

                S_FAULT: begin
                    configuration_valid <= 1'b0;
                    pass1_complete      <= 1'b0;   // the transaction is over
                    fault               <= 1'b1;
                    busy                <= 1'b0;
                    state               <= S_IDLE;
                end

                default: state <= S_FAULT;
            endcase
        end
    end
endmodule

`default_nettype wire
