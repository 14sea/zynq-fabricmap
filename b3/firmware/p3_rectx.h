/* p3_rectx — the bounded resend TRANSACTION and the bounded line receiver, as pure units
 * with injected I/O. rec-v3 introduced it for the loop record (REC → RECACK | RECGET);
 * rel-v4 (docs/l6_frame_reliability_design.md rev. 4, prereg v0.6 draft §2.6i–6p) runs
 * the SAME state machine for IDENT (→ IDENTACK), SIGNREQ (→ SIGNOK | SIGNREF, SIGNGET) and
 * TERM (→ TERMACK, TERMGET): send the line, wait — with a bound — for the acknowledging
 * type (or a re-request), resend the SAME bytes on the re-request or when the bound runs
 * out, at most P3_RECTX_ATTEMPTS transmissions in all. Without an acknowledgement the
 * caller stops the epoch (STOP_REC / STOP_IDENT / STOP_SIGN; a TERM simply halts).
 *
 * WHY THIS FILE EXISTS. S #1 (2026-09-01-11) lost ~536 bytes inside `REC 465` on the
 * console — the one frame the pull protocol could not re-request. C1 #5 and the reliability
 * review that followed showed every other board→host frame was in the same position: a
 * lost SIGNREQ blocked the board until the watchdog, a lost TERM was `missing TERM`, a lost
 * IDENT could never be acknowledged. From rel-v4 on every one of them is a transaction.
 *
 * The state machine lives here, with no MMIO and no console dependency, so the SAME source
 * the board image links is compiled on the host (firmware/p3_wire_twin.c `rectx`,
 * `identtx`, `signtx`, `termtx`) and driven by tests/test_firmware_wire_contract.py over a
 * pipe: the host test plays the runner and judges the bytes and the attempt counts this
 * code actually produces. `p3_app.c` supplies the I/O (put_str + watchdog kick, the bounded
 * RX-FIFO poll with the global-timer clock, its frame parser and JSON scan) and nothing of
 * the logic.
 *
 * THE BOUND (review 2026-09-02, the board-bound contract): a wait is bounded by BOTH a
 * count of RX polls and a number of global-timer ticks; whichever runs out first ends the
 * wait. The tick bound is the wall-time authority — P3_BOUND_TICKS in p3_app.c is
 * P3_BOUND_S × COUNTS_PER_SECOND on the pinned clock (CPU 666.67 MHz, timer = CPU/2,
 * 6:2:1 verified per session from CPU_CLK_CTRL), so every rel-v4 bound is ≤ P3_BOUND_S
 * seconds of wall time on that clock, which is what the host's TERM linger relies on
 * (host/l6_rel.py BOARD_BOUND_WALL_MAX_S). The poll count is a termination backstop for a
 * timer that does not advance; it is not the wall-time proof.
 *
 * The preregistered controls (identity page flags.bit4 = P3_RECTX_CONTROL_FLAG for the REC,
 * flags.bit5 = P3_SIGNTX_CONTROL_FLAG for the SIGNREQ): when the caller asks for it, the
 * FIRST transmission is sent with the last hex digit of its CRC field flipped — a
 * deliberate, recorded CRC failure on the wire — so that every session proves the real
 * retry on its opening baseline within seconds. Only attempt 1; the resend is the true line.
 */
#ifndef P3_RECTX_H
#define P3_RECTX_H

#include <stddef.h>
#include <stdint.h>

#define P3_RECTX_ATTEMPTS 3u        /* the first transmission + two retries (D-p1) */
#define P3_RECTX_CONTROL_FLAG 16u   /* identity page flags.bit4: forced REC-retry control */
#define P3_SIGNTX_CONTROL_FLAG 32u  /* identity page flags.bit5: forced SIGNREQ-retry control (rel-v4) */
/* Per wait: this many lines that are not this transaction's acknowledgement/re-request
 * (foreign, stale, broken, partial) are ignored; the one that makes the count reach the
 * limit ends the wait as if the bound had run out (resend, or exhaustion). */
#define P3_RECTX_STALE_LIMIT 64u
/* SIGNREQ transaction (review 2026-09-02, blocker 4b, kept under rel-v4): a RECACK/RECGET
 * arriving in the sign wait is tolerated only when it names the PREVIOUS record's seq, at
 * most this many times; any other acknowledgement there is channel misbehaviour. */
#define P3_RECTX_PREV_ACK_LIMIT 8u
/* p3_rectx_recv_line: a line is abandoned as PARTIAL when no byte arrives for `idle_polls`
 * polls (or `idle_ticks` of the clock) after at least one did, and in any case after
 * P3_RECTX_LINE_POLL_FACTOR × idle_polls polls OR `idle_ticks` of the clock in all — the
 * whole-line WALL-TIME bound equals the idle bound (review 2026-09-03: a ×4 factor on the
 * ticks made a trickled line worth 32 s), so no host line, however it is cut or paced,
 * can hold the application past one bound. */
#define P3_RECTX_LINE_POLL_FACTOR 4u

/* ------------------------------------------------------------ bounded line receive ----- */

typedef struct {
    int (*rx_ready)(void *ctx);        /* a byte is waiting */
    int (*rx_byte)(void *ctx);         /* the waiting byte (0..255); only called after rx_ready */
    uint64_t (*now_ticks)(void *ctx);  /* the monotonic clock in ticks; NULL = no clock bound */
    void *ctx;
} p3_rectx_rx;

/* One line into `out` (NUL-terminated, no CR/LF): >= 0 its length; -1 over-long (the rest
 * of the line is NOT consumed — the caller treats it as a discarded line); -2 nothing at
 * all arrived within the idle bound; -3 a partial line: bytes arrived and then the newline
 * did not, within the idle bound or the overall line bound — discarded. The idle bound is
 * `idle_polls` RX polls AND, when the receiver has a clock and idle_ticks > 0, `idle_ticks`
 * ticks of it — the first to run out ends the wait. */
int p3_rectx_recv_line_timed(const p3_rectx_rx *rx, char *out, size_t max, uint32_t idle_polls,
                             uint64_t idle_ticks);
/* The count-only form (idle_ticks 0). */
int p3_rectx_recv_line(const p3_rectx_rx *rx, char *out, size_t max, uint32_t idle_polls);

/* ------------------------------------------------------------ the transaction ---------- */

typedef struct {
    /* put the whole line on the wire (framing already done); 0 ok, -1 channel failure */
    int (*send)(const char *line, size_t n, void *ctx);
    /* one host line into `out` (no newline): >= 0 length, -1 over-long (discard, keep
     * waiting), -2 the bounded wait ran out with nothing received, -3 a partial line was
     * abandoned (discard, keep waiting) — p3_rectx_recv_line's contract */
    int (*recv_bounded)(char *out, size_t max, void *ctx);
    /* magic + CRC + token; on success fills type (NUL-terminated), the frame seq and
     * returns the payload field, else NULL. May mutate `line`. */
    const char *(*parse)(char *line, char *type_out, size_t type_max, uint32_t *seq_out, void *ctx);
    /* the payload's own "seq" field; 0 ok, -1 absent/unreadable */
    int (*payload_seq)(const char *payload_b64, uint32_t *seq_out, void *ctx);
    char *rx;          /* the caller's line buffer for recv_bounded */
    size_t rx_max;
    void *ctx;
} p3_rectx_io;

/* What ends a transaction: the acknowledging type(s), the re-request type (NULL = none),
 * and — for the SIGNREQ transaction — the previous record's seq whose stale RECACK/RECGET
 * lines are tolerated (prev_strict = 1; prev_seq 0 on the first candidate). */
typedef struct {
    const char *ack_a;      /* e.g. "RECACK", "IDENTACK", "SIGNOK", "TERMACK" */
    const char *ack_b;      /* e.g. "SIGNREF"; NULL when there is one acknowledging type */
    const char *get;        /* e.g. "RECGET", "SIGNGET", "TERMGET"; NULL = no re-request */
    const char *stop_why;   /* the reason recorded on exhaustion */
    uint32_t prev_seq;
    int prev_strict;
} p3_tx_kinds;

typedef struct {
    uint32_t attempts;        /* transmissions made, including the corrupted control one */
    uint32_t gets;            /* re-requests answered */
    uint32_t idle_expiries;   /* bounded waits that ran out (nothing, or a flood of stale lines) */
    uint32_t stale;           /* lines ignored (wrong type/seq/token/broken/partial/over-long) */
    uint32_t partial;         /* of those, partial lines abandoned by the receiver (-3) */
    uint32_t prev_acks;       /* SIGNREQ: stale acknowledgements of the previous record skipped */
    int corrupted_first;      /* the control was applied to attempt 1 */
    int acked;
    char ack_type[16];        /* the acknowledging type that arrived ("SIGNOK" / "SIGNREF" / …) */
    const char *ack_payload;  /* the acknowledging line's payload field, inside io->rx */
    const char *why;          /* set when not acked */
} p3_rectx_result;

/* Runs one transaction: `line` is the framed line INCLUDING its trailing newline (n
 * bytes), `seq` its seq. Returns 0 when an acknowledging line for this seq arrived
 * (result->ack_type / ack_payload say which and what), -1 when P3_RECTX_ATTEMPTS
 * transmissions went unacknowledged (result->why = kinds->stop_why), -2 when the channel
 * itself failed while sending, -3 when a strict previous-ack rule was violated
 * (result->why names it). `scratch` (>= n bytes) holds the corrupted copy for the control.
 * The bytes of every real transmission are identical: `line` is never modified. */
int p3_tx_run(const char *line, size_t n, uint32_t seq, const p3_tx_kinds *kinds, int corrupt_first,
              const p3_rectx_io *io, char *scratch, size_t scratch_max, p3_rectx_result *result);

/* The REC transaction (rec-v3): p3_tx_run with RECACK / RECGET and STOP_REC. */
int p3_rectx_run(const char *line, size_t n, uint32_t seq, int corrupt_first,
                 const p3_rectx_io *io, char *scratch, size_t scratch_max,
                 p3_rectx_result *result);

/* The control's corruption, in one place: the last hex digit of the CRC field of a framed
 * line (the character before the newline) — '0' becomes '1', anything else '0'. */
void p3_rectx_corrupt_crc(char *line, size_t n);

#endif /* P3_RECTX_H */
