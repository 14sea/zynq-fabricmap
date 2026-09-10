/* p3_pull — see p3_pull.h. Pure: no MMIO, no console, no global state. */

#include "p3_pull.h"

#include <string.h>

static uint32_t popcount(uint32_t x)
{
    uint32_t n = 0u;
    while (x) {
        n += x & 1u;
        x >>= 1;
    }
    return n;
}

static int all_served(const p3_pull_result *r, uint32_t chunks)
{
    uint32_t want = (chunks >= 32u) ? 0xFFFFFFFFu : ((1u << chunks) - 1u);
    return (r->served_mask & want) == want;
}

int p3_pull_run(uint32_t seq, uint32_t chunks, const p3_pull_io *io, p3_pull_result *r)
{
    memset(r, 0, sizeof(*r));
    if (chunks == 0u || chunks > P3_PULL_MAX_CHUNKS) {
        r->aborted = 1;
        r->why = "the audit span has an impossible chunk count";
        return -1;
    }
    if (io->send_ready(io->ctx) != 0)
        return -2;
    r->ready_sent = 1u;
    for (;;) {
        uint32_t stale = 0u;
        int expired = 0;

        for (;;) {
            char type[16];
            uint32_t fseq = 0u, pseq = 0u, chunk = 0u;
            int has_chunk = 0;
            const char *payload;
            int got;

            if (io->channel_failed != NULL && io->channel_failed(io->ctx))
                return -2; /* the channel itself failed while sending */
            got = io->recv_bounded(io->rx, io->rx_max, io->ctx);
            if (got == -2) {
                r->idle_expiries++;
                expired = 1;
                break;
            }
            if (got < 0) {
                r->stale++; /* over-long or partial: not a host frame of ours */
            } else {
                payload = io->parse(io->rx, type, sizeof(type), &fseq, io->ctx);
                if (payload == NULL || fseq != seq || payload[0] == 0 ||
                    io->payload_fields(payload, &pseq, &chunk, &has_chunk, io->ctx) != 0 || pseq != seq) {
                    r->stale++; /* broken, foreign, or another candidate's: not answered */
                } else if (strcmp(type, "AUDITGET") == 0) {
                    if (has_chunk && chunk < chunks) {
                        if (io->serve_chunk(chunk, io->ctx) != 0)
                            return -2;
                        r->gets_seen++;
                        r->chunks_served++;
                        r->served_mask |= (1u << chunk);
                    } else {
                        r->stale++;
                    }
                    stale = 0u; /* a valid GET is the host alive: the stale count restarts */
                    continue;
                } else if (strcmp(type, "AUDITDONE") == 0) {
                    /* review 2026-09-03, blocker 1: a DONE is the host's word that it verified
                     * EVERY chunk — it cannot arrive before every chunk was served. One that
                     * does is channel misbehaviour (or a forged line) and the audit is given
                     * up, fail-closed: no `audited` mark, no ARM on the SCORED path. */
                    if (!all_served(r, chunks)) {
                        r->aborted = 1;
                        r->why = "AUDITDONE before every chunk was served: the audit is not complete";
                        return -1;
                    }
                    r->done = 1;
                    return 0;
                } else if (strcmp(type, "AUDITABORT") == 0) {
                    r->aborted = 1;
                    r->why = "the host aborted the audit pull";
                    return -1;
                } else {
                    r->stale++; /* any other type during a pull is ignored */
                }
            }
            if (++stale >= P3_PULL_STALE_LIMIT) {
                r->idle_expiries++;
                expired = 1;
                break;
            }
        }
        if (!expired)
            continue;
        /* the bound ran out: the announcement may have been lost, or our last chunk's
         * DONE may have — resend the one, or announce for the other, both bounded */
        if (r->gets_seen == 0u) {
            if (r->ready_sent >= P3_PULL_READY_ATTEMPTS) {
                r->aborted = 1;
                r->why = "the host never asked for a chunk: AUDIT_READY resent to its bound";
                return -1;
            }
            if (io->send_ready(io->ctx) != 0)
                return -2;
            r->ready_sent++;
            continue;
        }
        if (all_served(r, chunks)) {
            if (r->waits_sent >= P3_PULL_WAIT_MAX) {
                r->aborted = 1;
                r->why = "every chunk was served but no AUDITDONE arrived: AUDITWAIT announced to its bound";
                return -1;
            }
            if (io->send_wait(popcount(r->served_mask), io->ctx) != 0) /* unique chunks, not transmissions */
                return -2;
            r->waits_sent++;
            continue;
        }
        r->aborted = 1;
        r->why = "the host went quiet during the audit pull (bounded wait ran out)";
        return -1;
    }
}
