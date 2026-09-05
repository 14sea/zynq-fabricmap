/* p3_wire — the standalone application's wire serialisation, as a pure unit.
 *
 * WHY THIS FILE EXISTS. The first L5 board attempt was blocked because the C
 * application's framed output had never been checked against the host validator that
 * consumes it: records were emitted flat (no `seq`, no `verified`, no nested `evidence`),
 * no `IDENT` was ever sent although `validate_standalone_run_log` requires `app_identity`,
 * and no heartbeat was sent although the collector calls 30 s of silence a CRASH. The
 * host-only rehearsal had validated `host/l5_refloop.py` -- the *Python* reference -- so
 * every test was green while the C wire format was incompatible.
 *
 * The fix is structural, and it is the same move `p3_derive.c` already makes for the
 * hashes: everything provable on the host lives in a unit with no MMIO and no board
 * dependency, so a host test can compile THIS source, drive it, and feed the bytes it
 * produces to the real Python validator (`tests/test_firmware_wire_contract.py`). What
 * stays in `p3_app.c` is the HAL and the state machine. A green test here is therefore
 * evidence about the bytes the board will actually emit, not about a model of them.
 *
 * Every builder writes compact JSON with sorted keys into a caller buffer and returns the
 * length, or 0 if it would not fit (callers treat 0 as a PROTOCOL-class failure and never
 * emit a truncated line).
 */
#ifndef P3_WIRE_H
#define P3_WIRE_H

#include <stddef.h>
#include <stdint.h>

#define P3_WIRE_SCORES 6
#define P3_WIRE_TOKEN_HEX 32
#define P3_WIRE_SHA_HEX 64
#define P3_WIRE_GENOME_HEX 80
#define P3_WIRE_TABLE_HEX 16
#define P3_WIRE_TAG_HEX 32

/* ------------------------------------------------------------------ framed line ----- */

/* "P3L5 <type> <seq> <token> <payload> <crc32>\n" (spec 5b: the FULL 128-bit token).
 * `payload` is already base64url, or "-" for a payload-less type such as HB. */
size_t p3_wire_line(const char *type, uint32_t seq, const char *token,
                    const char *payload_b64, char *out, size_t max);

/* ------------------------------------------------------------------ app_identity ---- */

typedef struct {
    uint32_t pss_idcode;
    const char *token;          /* 32 hex */
    uint32_t uboot_epoch;
    const char *carrier_sha256; /* 64 hex */
    uint64_t nonce_at_start;
    uint32_t status_at_start;
    uint32_t fclk0_hz_decoded;
    uint32_t app_epoch;
    const char *const *findings; /* may be NULL when n == 0 */
    int findings_n;
    /* app_identity 1.1.0 (L6 prereg §2.4): the master seed the schedule derives from, the
     * schedule mode the identity page asked for, and the hash of the map data compiled
     * into this image — the host regenerates it from local_map.json and compares. */
    uint32_t master_seed;
    const char *schedule_mode;        /* abba | random_safe_forced | map_guided_forced */
    const char *operator_data_sha256; /* 64 hex, P3_OPERATOR_DATA_SHA256 */
    /* app_identity 1.2.0 (rec-v3, L6 prereg v0.4): the wire protocol this image speaks —
     * the host refuses an image that does not declare the one its runner implements —
     * and the identity page's forced REC-retry control flag as the application decoded it */
    const char *protocol;             /* "rec-v3" | "rel-v4" */
    int rec_retry_control;
    /* app_identity 1.3.0 (rel-v4, prereg v0.6 draft §2.6d): the page's flags.bit5 — the
     * forced SIGNREQ-retry control — as the application decoded it */
    int sign_retry_control;
    /* app_identity 1.4.0 (B1): the cartographer's version, the universe digest it was
     * compiled with, and the probe budget the identity page handed it */
    const char *carto_version;
    const char *universe_sha256;      /* 64 hex, B1_UNIVERSE_SHA256 */
    uint32_t probe_budget;
} p3_wire_identity_in;

size_t p3_wire_identity(const p3_wire_identity_in *in, char *out, size_t max);

/* ------------------------------------------------------------------ sign_request ---- */

size_t p3_wire_sign_request(const char *token, uint32_t app_epoch, uint32_t seq,
                            const char *genome_hex, uint64_t nonce, char *out, size_t max);

/* ------------------------------------------------------------------ loop_record ----- */

/* One candidate. The `have_*` flags select the evidence members, which the validator
 * requires to match the outcome exactly (see validators/records.py _check_loop_record):
 *   REFUSED_BY_GATE      -> sign_refusal only
 *   STOP_AXI, STOP_LINK2 -> sign_reply (no arm, no score)
 *   STOP_LINK3           -> sign_reply + app_oracle_record (no arm, no score)
 *   REFUSED_BY_PL        -> sign_reply + app_oracle_record + arm (no score)
 *   SCORED               -> sign_reply + app_oracle_record + arm + score
 */
typedef struct {
    uint32_t seq;
    const char *genome;   /* 80 hex */
    const char *outcome;  /* one of LOOP_OUTCOMES */
    int audited;          /* -> "verified": "audited" | "replayed-only" */
    const char *carto;    /* loop_record 1.2.0 (B1): the cartographer's pre-rendered JSON block, or NULL */
    const char *arm;      /* loop_record 1.1.0: random_safe | map_guided on a candidate;
                           * NULL on the two baseline brackets, which then carry no arm */

    int have_sign_refusal;
    const char *const *finding_kinds;
    int finding_kinds_n;

    int have_sign_reply;
    const char *commit;                          /* 64 hex */
    const char *tables[P3_WIRE_SCORES];          /* 16 hex each */
    const char *tag;                             /* 32 hex */

    int have_oracle;
    const char *staged_sha256;                   /* 64 hex */
    const char *staged_stream_sha256;            /* 64 hex, a different domain */
    const char *readback_sha256;                 /* 64 hex */
    int envelopes_n;
    const uint32_t *envelope_int_sts;            /* envelopes_n words, may be NULL */
    int audit_available;

    int have_arm;
    uint64_t nonce_before, nonce_after;
    uint32_t status_after, fault_after;
    int key_loaded_observed;
    /* Session 1 (2026-09-01) stopped because the nonce did not step, and STATUS/FAULT were
     * read and then thrown away on that path. These are recorded on EVERY ARM attempt,
     * whatever the outcome: the failing path gets the same evidence as the passing one.
     *
     * There is deliberately NO ctrl_before/ctrl_after. CTRL (0x2000) is write-only in
     * rtl/p3_axil.v; reading it is SLVERR and on this board a data abort, which is what
     * killed session 2. The record states the value as UNAVAILABLE rather than omitting the
     * question — a reader must be able to see that the strobe's fate in the register was not
     * observable, not be left wondering whether anyone looked. */
    int writes_issued;   /* payload + tag + strobe actually handed to Xil_Out32 */
    /* The bounded settle poll after the strobe (session 3, 2026-09-01). The RTL steps the
     * nonce only when the gate's SipHash completes (rtl/p3_arm_gate.v state 1, sh_done);
     * session 3 read `gate_busy` SET immediately after the strobe and an unchanged nonce,
     * so the "did not consume" of sessions 1 and 3 was a read issued before the gate had
     * finished. Every ARM record now says how long it waited and what it saw first and
     * last; `status_after` IS `status_last`. */
    uint32_t settle_polls;      /* STATUS reads issued after the strobe, >= 1 */
    uint32_t settle_polls_max;  /* the bound; polls == polls_max and !settled => STOP_SETTLE */
    int settled;                /* !gate_busy && !scorer_busy && (fault || scorer_done) */
    uint32_t status_first;      /* STATUS on the first read after the strobe (session 3's value) */

    /* STOP_AUDIT (L6 pull): the host-paced audit did not complete before the ARM — retries
     * exhausted, an AUDITABORT, or the board's bounded wait ran out. No ARM was attempted. */
    int have_audit_stop;
    const char *audit_stop_why;
    uint32_t audit_chunks_served;

    /* STOP_SIGN (rel-v4, prereg v0.6 draft §2.6k): the sign exchange was not acknowledged
     * after the bounded resends — a terminal record carrying this block and nothing else */
    int have_sign_stop;
    uint32_t sign_stop_attempts;
    const char *sign_stop_why;

    int have_score;
    const char *hw_candidate_commit;             /* 64 hex */
    const char *readout[P3_WIRE_SCORES];         /* 16 hex each */
    uint32_t scores[P3_WIRE_SCORES];
    uint32_t hb_before, hb_after;
} p3_wire_record_in;

size_t p3_wire_loop_record(const p3_wire_record_in *in, char *out, size_t max);

/* ------------------------------------------------------------------ audit pull (L6) -- */

/* The host-paced sparse audit (docs/l6_audit_pull_design.md). AUDIT_READY announces the
 * transaction's binding (seq, span, total_words, chunks); each AUDIT chunk repeats it and
 * carries the NON-ZERO words of one WINDOW of positions as packed (uint16 position,
 * uint32 word) pairs, ascending, base64url — an unlisted position is zero. */
#define P3_WIRE_SPARSE_WINDOW 384u
#define P3_WIRE_SPARSE_ENCODING "sparse-v1"

size_t p3_wire_audit_ready(uint32_t seq, const char *span, uint32_t total_words, uint32_t chunks,
                           uint32_t nonzero, char *out, size_t max);

/* entries for positions [lo, hi) from a word accessor; returns the base64url length, 0 on overflow */
size_t p3_wire_sparse_entries(uint32_t (*word)(uint32_t), uint32_t lo, uint32_t hi,
                              char *b64_out, size_t max);

size_t p3_wire_audit_sparse(uint32_t seq, uint32_t chunk, uint32_t chunks, const char *span,
                            uint32_t total_words, uint32_t lo, uint32_t hi, const char *entries_b64,
                            char *out, size_t max);

/* ------------------------------------------------------------------ audit ----------- */

/* One chunk of the raw words held in the evidence ring for candidate `seq`. The collector
 * reassembles `chunk`/`chunks`, recomputes both link-2 hashes and the link-3 hash, and
 * compares them with the compact record it already holds (spec 4.7). `words_b64` is
 * base64url of the chunk's words, big-endian, 4 bytes each. */
/* `span` names WHICH raw words this audit covers, because a candidate that ended at link 2
 * has staging streams but no readback frames: "streams" or "streams+readback". The host
 * must not silently treat a short audit as a full one. */
size_t p3_wire_audit(uint32_t seq, uint32_t chunk, uint32_t chunks, uint32_t word_offset,
                     uint32_t word_count, uint32_t total_words, const char *span,
                     const char *words_b64, char *out, size_t max);

/* ------------------------------------------------------------------ closing control - */

/* The closing unsigned ARM (spec 4.0) is NOT a loop_record: "CLOSING_CONTROL" is not one of
 * LOOP_OUTCOMES, and the validator reads it from the log's own `closing_negative` key. It
 * travels as its own frame type so the collector can file it there. */
size_t p3_wire_closing(uint64_t nonce_before, uint64_t nonce_after, uint32_t fault,
                       uint32_t status, char *out, size_t max);

/* ------------------------------------------------------------------ summary --------- */

typedef struct {
    const char *token;
    const char *kind;        /* COMPLETED | STOPPED | PROTOCOL */
    const char *reason;
    uint32_t last_seq;
    uint32_t scored, refused_by_gate;
    int closing_restore, closing_baseline, closing_unsigned; /* -> done | not_reached */
    uint32_t audited, total;
    uint32_t crc_dropped, drop_budget;
    /* rel-v4 (prereg v0.6 draft §2.6o): the closing unsigned control's fields repeated in
     * the TERM, so a lost CLOSE is reconstructed from the re-requestable TERM. Present
     * exactly when the control was reached (closing_unsigned == done). */
    int have_closing_control;
    uint64_t close_nonce_before, close_nonce_after;
    uint32_t close_fault, close_status;
} p3_wire_summary_in;

size_t p3_wire_summary(const p3_wire_summary_in *in, char *out, size_t max);

/* rel-v4: the heartbeat's index payload {"i":k} (0..15 per record), so a lost heartbeat is
 * identified and a duplicated one harmless (prereg v0.6 draft §2.6n). */
size_t p3_wire_hb(uint32_t i, char *out, size_t max);
/* rel-v4: AUDITWAIT {seq, served} — the board did not see AUDITDONE after the last chunk
 * (prereg v0.6 draft §2.6m). */
size_t p3_wire_audit_wait(uint32_t seq, uint32_t served, char *out, size_t max);

/* ------------------------------------------------------------------ tally ----------- */

/* The accounting the summary's `audit` block reports, kept where the records are
 * serialised so it cannot disagree with what was emitted: p3_wire_loop_record() counts
 * every record it produces and every one marked audited. Session 3 (2026-09-01) was
 * rejected by rule (ix) because the application derived `total` as scored + refused and
 * so did not count its own STOP_ARM record. The validator requires total == the number of
 * loop records; this is that number, from the only place that knows it. */
void p3_wire_tally(uint32_t *records_emitted, uint32_t *records_audited);
void p3_wire_tally_reset(void);

#endif /* P3_WIRE_H */
