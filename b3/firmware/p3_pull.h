/* p3_pull — the host-paced audit pull's board state machine (pull-v2 + rel-v4), as a pure
 * unit with injected I/O.
 *
 * pull-v2 (docs/l6_audit_pull_design.md): the board announces AUDIT_READY, answers every
 * AUDITGET with the chunk asked for — as often as asked — until AUDITDONE or AUDITABORT or
 * its own bounded wait runs out. rel-v4 (docs/l6_frame_reliability_design.md §3.3, §3.8)
 * adds two things the C1 #5 review found missing: while NO AUDITGET has been seen yet, an
 * expired bound resends the AUDIT_READY line (same bytes, ≤ P3_PULL_READY_ATTEMPTS in all —
 * the announcement may have been lost); and once EVERY chunk has been served at least
 * once, an expired bound sends AUDITWAIT {seq, served} (≤ P3_PULL_WAIT_MAX) so the host
 * replays the DONE/ABORT the board did not see. Exhaustion of either gives the audit up
 * exactly as before (the caller: STOP_AUDIT on the SCORED path, replayed-only otherwise).
 *
 * Pure: the caller supplies the sending of the stored READY line, the serving of a chunk,
 * the AUDITWAIT frame, the bounded receiver, the parser and the JSON scan. The same source
 * the image links is driven on the host (firmware/p3_wire_twin.c `pulltx`) by
 * tests/test_firmware_wire_contract.py with the real host pull (host/l6_audit_pull.PullHost).
 */
#ifndef P3_PULL_H
#define P3_PULL_H

#include <stddef.h>
#include <stdint.h>

#define P3_PULL_READY_ATTEMPTS 3u  /* AUDIT_READY transmissions in all while no GET was seen (D-p1) */
#define P3_PULL_WAIT_MAX 3u        /* AUDITWAIT announcements before the audit is given up (D-p1) */
#define P3_PULL_STALE_LIMIT 64u    /* ignored lines per wait, then the wait ends like the bound */
#define P3_PULL_MAX_CHUNKS 32u     /* the served bitmap's width; a span needs 8 */

typedef struct {
    int (*send_ready)(void *ctx);                    /* (re)send the stored AUDIT_READY line; 0 ok */
    int (*serve_chunk)(uint32_t chunk, void *ctx);   /* send the AUDIT chunk asked for; 0 ok */
    int (*send_wait)(uint32_t served, void *ctx);    /* send AUDITWAIT {seq, served}; 0 ok */
    int (*recv_bounded)(char *out, size_t max, void *ctx);      /* p3_rectx_recv_line's contract */
    const char *(*parse)(char *line, char *type_out, size_t type_max, uint32_t *seq_out, void *ctx);
    /* the payload's "seq" (0 ok / -1) and, when present, its "chunk" (has_chunk set) */
    int (*payload_fields)(const char *payload_b64, uint32_t *seq_out, uint32_t *chunk_out,
                          int *has_chunk, void *ctx);
    int (*channel_failed)(void *ctx);                /* the caller's own send failure flag */
    char *rx;
    size_t rx_max;
    void *ctx;
} p3_pull_io;

typedef struct {
    uint32_t ready_sent;      /* AUDIT_READY transmissions (1 + resends) */
    uint32_t gets_seen;       /* AUDITGET lines answered */
    uint32_t chunks_served;   /* AUDIT chunk lines sent (retries included) */
    uint32_t waits_sent;      /* AUDITWAIT announcements */
    uint32_t idle_expiries;   /* bounded waits that ran out */
    uint32_t stale;           /* lines ignored */
    uint32_t served_mask;     /* bit c set once chunk c was served at least once */
    int done;                 /* AUDITDONE arrived */
    int aborted;              /* AUDITABORT, or the bound/resends exhausted */
    const char *why;          /* set when not done */
} p3_pull_result;

/* Runs one candidate's pull for `chunks` chunks (1..P3_PULL_MAX_CHUNKS). Returns 0 on
 * AUDITDONE, -1 when the audit was given up (result->why says why), -2 on a channel
 * failure. The READY line is sent by this function through io->send_ready (once, then on
 * an expired bound while no GET was seen). */
int p3_pull_run(uint32_t seq, uint32_t chunks, const p3_pull_io *io, p3_pull_result *result);

#endif /* P3_PULL_H */
