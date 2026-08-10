// Claim B round 1 carrier — the envelope validator, in fabric.
//
// The host-side `gate_candidate.py` judges the serialized ICAP stream before it leaves the
// host. This is its counterpart on the other side of the wire, and it exists because the
// host is not the authority: a mis-addressed write is a software defect, and a guard
// defended by the software it is defending against is not a guard.
//
// THREE RULES, all of them learned the expensive way on the host side
// -------------------------------------------------------------------
// 1. **The whole ordered control trace is compared, not just FAR membership.** Review v1
//    showed a membership check cannot see an ABSENT command or a WRONG value — removing
//    WCFG, removing RCRC and writing a non-zero CRC all passed with zero findings. Here
//    every control word of every envelope is compared against the pinned constant at its
//    pinned position, so missing, duplicated, reordered and extra words are all the same
//    single failure: a word that is not what belongs there.
// 2. **The declared length is proved to exist before any payload is read.** Review v2
//    showed a recognised but truncated packet crashed the host parser instead of refusing.
//    Here the type-2 count must equal the pinned payload length AND the buffer must
//    actually hold that many words, checked before the payload is touched.
// 3. **The allowlist eats the FAR PARSED FROM THE STREAM**, at its position in the words
//    that will physically go to ICAPE2 — never a host-declared frame index and never the
//    validator's own expectation. That is the whole point: `configuration_valid` has to
//    describe fabric written through a fixed envelope, and the only evidence of which
//    frame was addressed is the word the FAR packet carries.
//
// Validation is a SEPARATE PASS over the whole buffer, completed before a single word is
// streamed. Checking as it goes would already have written envelopes 0 and 1 by the time
// it refused envelope 2.
//
// WHAT configuration_valid DOES AND DOES NOT AUTHORISE
// ----------------------------------------------------
// A readback compare proves ONE thing: the fabric now holds what the guard actually
// received and wrote. It says nothing about whether that candidate was allowed to be
// written. Whether the payload changes only the 292 whitelisted bits, whether the flush
// frames equal the pinned base verbatim, and whether each ECC is a correct recomputation
// are judgements of the HOST gate, `scripts/gate_candidate.py`, and they are not
// re-implemented here.
//
// What has to hold before a score means anything is a three-part conjunction:
//
//     bytes the host candidate gate ACCEPTED
//       == bytes actually HANDED TO the guard
//       == bytes READ BACK from the fabric
//
// `configuration_valid` establishes the second and third links. The first is the host's,
// and scoring requires it too. Two consequences for the data path, so the chain cannot be
// broken between the links: the transport must send the SAME in-memory bytes the gate
// parsed — never re-read the file after gating — and the run log's candidate hash and
// readback hash must be equal before an arm is issued.
//
`default_nettype none

// TWO-PASS FORM. This module now validates ONE resident envelope, named by `env_index`,
// because the buffer holds 536 words rather than 1608 — the left-of-flush region has no
// BRAM column and cannot hold the whole candidate as LUTRAM. Pass 1 runs it over each of
// the three in turn with ICAPE2 untouched; pass 2 runs it again on the reloaded envelope
// before that envelope is written.
//
// `env_index` selects WHICH permitted FAR is expected. It is the host's declaration, and
// it is not trusted: if the host declares 1 while loading envelope 0's bytes, the FAR
// parsed from the stream will not equal permitted_far(1) and the envelope is refused.
// Order is enforced separately, by the transaction, which requires 0, 1, 2 in sequence.

module carrier_envelope #(
    parameter integer ENVELOPES     = 3,
    parameter integer ENV_WORDS     = 536,
    parameter integer PAYLOAD_WORDS = 505,
    parameter integer PAYLOAD_START = 23,
    parameter integer FAR_POS       = 20,
    parameter [31:0]  IDCODE        = 32'h13722093
) (
    input  wire        clk,
    input  wire        rst_n,

    input  wire        start,
    input  wire [1:0]  env_index,      // which envelope the resident words claim to be
    input  wire [11:0] loaded_words,   // how many words the host actually wrote

    output wire [11:0] buf_addr,
    input  wire [31:0] buf_data,

    output reg         busy,
    output reg         ok,
    output reg         fault,
    output reg  [3:0]  fault_code,
    output reg  [11:0] fault_word      // word position WITHIN the envelope
);
    localparam [3:0] E_NONE      = 4'd0,
                     E_CONTROL   = 4'd1,  // a control word is not the pinned constant
                     E_FAR       = 4'd2,  // the parsed FAR is not on the allowlist
                     E_LENGTH    = 4'd3,  // type-2 count is not the pinned payload length
                     E_TRUNCATED = 4'd4;  // the buffer does not hold what was declared

    localparam [31:0] W_DUMMY  = 32'hFFFFFFFF,
                      W_SYNC   = 32'hAA995566,
                      W_NOOP   = 32'h20000000,
                      W_CMD1   = 32'h30008001,
                      W_RCRC   = 32'h00000007,
                      W_WCFG   = 32'h00000001,
                      W_DESYNC = 32'h0000000D,
                      W_ID1    = 32'h30018001,
                      W_FAR1   = 32'h30002001,
                      W_FDRI0  = 32'h30004000,
                      W_TYPE2  = 32'h40000000 | PAYLOAD_WORDS,
                      W_CRC1   = 32'h30000001,
                      W_ZERO   = 32'h00000000;

    // The pinned control skeleton, by position within an envelope. Positions 23..527 are
    // payload and are not control words; FAR_POS is checked against the allowlist rather
    // than a constant, because its value is the one thing that legitimately varies.
    function automatic [32:0] expected_at(input [9:0] pos);
        // bit 32 = "this position is a pinned constant"; bits 31:0 = the constant
        begin
            expected_at = {1'b0, 32'd0};
            if (pos < 8)                       expected_at = {1'b1, W_DUMMY};
            else if (pos == 8)                 expected_at = {1'b1, W_SYNC};
            else if (pos == 9)                 expected_at = {1'b1, W_NOOP};
            else if (pos == 10)                expected_at = {1'b1, W_CMD1};
            else if (pos == 11)                expected_at = {1'b1, W_RCRC};
            else if (pos == 12 || pos == 13)   expected_at = {1'b1, W_NOOP};
            else if (pos == 14)                expected_at = {1'b1, W_ID1};
            else if (pos == 15)                expected_at = {1'b1, IDCODE};
            else if (pos == 16)                expected_at = {1'b1, W_CMD1};
            else if (pos == 17)                expected_at = {1'b1, W_WCFG};
            else if (pos == 18)                expected_at = {1'b1, W_NOOP};
            else if (pos == 19)                expected_at = {1'b1, W_FAR1};
            // pos == FAR_POS (20): the allowlist judges it, not a constant
            else if (pos == 21)                expected_at = {1'b1, W_FDRI0};
            else if (pos == 22)                expected_at = {1'b1, W_TYPE2};
            else if (pos == 528)               expected_at = {1'b1, W_CRC1};
            else if (pos == 529)               expected_at = {1'b1, W_ZERO};
            else if (pos == 530)               expected_at = {1'b1, W_CMD1};
            else if (pos == 531)               expected_at = {1'b1, W_DESYNC};
            else if (pos >= 532)               expected_at = {1'b1, W_NOOP};
        end
    endfunction

    // The permitted FAR for a given envelope: the FIRST frame of that envelope's group.
    // Compiled in; nothing indexes it from a register.
    function automatic [31:0] permitted_far(input [1:0] env);
        case (env)
            2'd0:    permitted_far = 32'h00400A20;
            2'd1:    permitted_far = 32'h00400C1A;
            2'd2:    permitted_far = 32'h00400C20;
            default: permitted_far = 32'hFFFFFFFF;   // never permitted
        endcase
    endfunction

    localparam [2:0] S_IDLE = 3'd0,
                     S_LEN  = 3'd1,
                     S_WALK = 3'd2,
                     S_OK   = 3'd3,
                     S_BAD  = 3'd4;

    reg [2:0]  state;
    reg [1:0]  env;      // address being ISSUED this cycle
    reg [9:0]  pos;
    reg [1:0]  env_d;    // the address whose datum is on buf_data NOW
    reg [9:0]  pos_d;
    reg        valid_d;  // ... and whether that datum is meaningful yet
    reg        issued_last;

    // The buffer read is SYNCHRONOUS: `buf_data` belongs to the address presented on the
    // previous cycle. So the expectation is pipelined alongside the address rather than
    // recomputed from the issuing counter — comparing `buf_data` against `expected_at(pos)`
    // would judge every word against its successor's expectation, which is the same
    // off-by-one that made the guard's first version never confirm.
    // One envelope resident: the buffer is addressed from 0 regardless of which envelope
    // these words claim to be.
    assign buf_addr = pos;

    wire [32:0] want_d = expected_at(pos_d);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= S_IDLE;
            busy       <= 1'b0;
            ok         <= 1'b0;
            fault      <= 1'b0;
            fault_code <= E_NONE;
            fault_word <= 12'd0;
            env        <= 2'd0;
            pos        <= 10'd0;
        end else begin
            case (state)
                S_IDLE: begin
                    busy <= 1'b0;
                    if (start) begin
                        ok         <= 1'b0;
                        fault      <= 1'b0;
                        fault_code <= E_NONE;
                        env        <= 2'd0;
                        pos        <= 10'd0;
                        busy       <= 1'b1;
                        state      <= S_LEN;
                    end
                end

                // RULE 2, before a single payload word is looked at: the buffer must hold
                // every word the envelopes declare. A short load is a fault, never a
                // silently truncated read.
                S_LEN: begin
                    if (loaded_words != ENV_WORDS) begin
                        fault_code <= E_TRUNCATED;
                        fault_word <= loaded_words;
                        state      <= S_BAD;
                    end else begin
                        env     <= env_index;
                        pos     <= 10'd0;
                        valid_d <= 1'b0;
                        issued_last <= 1'b0;
                        state   <= S_WALK;
                    end
                end

                S_WALK: begin
                    // 1. judge the datum that has arrived, for the address issued last
                    if (valid_d) begin
                        if (pos_d == FAR_POS) begin
                            // RULE 3: the allowlist judges the word that will physically
                            // be sent, read out of the stream at the FAR packet's position.
                            if (buf_data != permitted_far(env_d)) begin
                                fault_code <= E_FAR;
                                fault_word <= pos_d;
                                state      <= S_BAD;
                            end
                        end else if (want_d[32] && buf_data != want_d[31:0]) begin
                            // RULE 1: any control word that is not the pinned constant —
                            // missing, duplicated, reordered or extra all land here.
                            fault_code <= (pos_d == 22) ? E_LENGTH : E_CONTROL;
                            fault_word <= pos_d;
                            state      <= S_BAD;
                        end else if (issued_last && pos_d == ENV_WORDS - 1) begin
                            state <= S_OK;   // the last word has now been JUDGED, not
                                             // merely issued: the pipeline is drained
                        end
                    end

                    // 2. issue the next address, and remember what it was
                    env_d   <= env;
                    pos_d   <= pos;
                    valid_d <= 1'b1;
                    if (pos == ENV_WORDS - 1) begin
                        issued_last <= 1'b1;
                    end else if (!issued_last) begin
                        pos <= pos + 10'd1;
                    end
                end

                S_OK: begin
                    ok    <= 1'b1;
                    busy  <= 1'b0;
                    state <= S_IDLE;
                end

                S_BAD: begin
                    ok    <= 1'b0;
                    fault <= 1'b1;
                    busy  <= 1'b0;
                    state <= S_IDLE;
                end

                default: state <= S_BAD;
            endcase
        end
    end
endmodule

`default_nettype wire
