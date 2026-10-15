/* p3_rectx — see p3_rectx.h. Pure: no MMIO, no console, no global state. */

#include "p3_rectx.h"

#include <string.h>

int p3_rectx_recv_line_timed(const p3_rectx_rx *rx, char *out, size_t max, uint32_t idle_polls,
                             uint64_t idle_ticks)
{
    size_t n = 0;
    uint32_t idle = 0u, total = 0u;
    const uint32_t line_polls = idle_polls * P3_RECTX_LINE_POLL_FACTOR;
    const int timed = (rx->now_ticks != NULL && idle_ticks != 0u);
    /* review 2026-09-03, blocker 2: the whole-line wall-time bound is the SAME idle_ticks —
     * a line trickled in below the idle gap can hold the receiver no longer than one bound
     * in all (the ×4 factor applies to the poll count only, the termination backstop) */
    const uint64_t line_ticks = idle_ticks;
    uint64_t t_start = 0u, t_last = 0u;

    if (max == 0u)
        return -1;
    out[0] = 0;
    if (timed) {
        t_start = rx->now_ticks(rx->ctx);
        t_last = t_start;
    }
    for (;;) {
        int c;
        if (!rx->rx_ready(rx->ctx)) {
            if (++idle > idle_polls) {
                out[n] = 0;
                return n == 0u ? -2 : -3; /* silence: nothing at all, or a line cut short */
            }
            if (++total > line_polls) {
                out[n] = 0;
                return n == 0u ? -2 : -3;
            }
            if (timed) {
                uint64_t now = rx->now_ticks(rx->ctx);
                /* the clock bound: the same two questions, on the wall-time authority */
                if (now - t_last > idle_ticks || now - t_start > line_ticks) {
                    out[n] = 0;
                    return n == 0u ? -2 : -3;
                }
            }
            continue;
        }
        idle = 0u;
        if (++total > line_polls) {
            out[n] = 0;
            return -3; /* a line that never ends within the overall bound */
        }
        if (timed) {
            t_last = rx->now_ticks(rx->ctx);
            if (t_last - t_start > line_ticks) {
                out[n] = 0;
                return -3;
            }
        }
        c = rx->rx_byte(rx->ctx);
        if (c == '\n')
            break;
        if (c == '\r')
            continue;
        if (n + 1u >= max) {
            out[n] = 0;
            return -1; /* over-long: the caller discards it and keeps waiting */
        }
        out[n++] = (char)c;
    }
    out[n] = 0;
    return (int)n;
}

int p3_rectx_recv_line(const p3_rectx_rx *rx, char *out, size_t max, uint32_t idle_polls)
{
    return p3_rectx_recv_line_timed(rx, out, max, idle_polls, 0u);
}

void p3_rectx_corrupt_crc(char *line, size_t n)
{
    size_t i;

    if (n < 2u)
        return;
    i = (line[n - 1] == '\n') ? n - 2u : n - 1u;
    line[i] = (line[i] == '0') ? '1' : '0';
}

static int tx_send(const char *line, size_t n, uint32_t attempt, int corrupt_first,
                   const p3_rectx_io *io, char *scratch, size_t scratch_max,
                   p3_rectx_result *r)
{
    r->attempts++;
    if (attempt == 1u && corrupt_first) {
        if (scratch == NULL || scratch_max < n)
            return -1;
        memcpy(scratch, line, n);
        p3_rectx_corrupt_crc(scratch, n);
        r->corrupted_first = 1;
        return io->send(scratch, n, io->ctx);
    }
    return io->send(line, n, io->ctx); /* the real bytes, identical on every transmission */
}

static int is_type(const char *type, const char *want)
{
    return want != NULL && strcmp(type, want) == 0;
}

int p3_tx_run(const char *line, size_t n, uint32_t seq, const p3_tx_kinds *kinds, int corrupt_first,
              const p3_rectx_io *io, char *scratch, size_t scratch_max, p3_rectx_result *r)
{
    uint32_t attempt;
    uint32_t prev_acks = 0u;

    memset(r, 0, sizeof(*r));
    for (attempt = 1u; attempt <= P3_RECTX_ATTEMPTS; attempt++) {
        uint32_t stale = 0u;

        if (tx_send(line, n, attempt, corrupt_first, io, scratch, scratch_max, r) != 0) {
            r->why = "PROTOCOL: the channel failed while sending";
            return -2;
        }
        /* wait for THIS seq's acknowledgement or re-request; anything else is ignored,
         * within bounds — except, under the strict rule, an acknowledgement that names
         * neither this seq nor the previous record's */
        for (;;) {
            char type[16];
            uint32_t fseq = 0u, pseq = 0u;
            const char *payload;
            int got = io->recv_bounded(io->rx, io->rx_max, io->ctx);

            if (got == -2) {
                r->idle_expiries++;
                break; /* the bound ran out: resend, or exhaust */
            }
            if (got < 0) {
                r->stale++; /* over-long (-1) or partial (-3): not a line of ours */
                if (got == -3)
                    r->partial++;
            } else {
                payload = io->parse(io->rx, type, sizeof(type), &fseq, io->ctx);
                if (payload == NULL) {
                    r->stale++; /* broken or foreign: not ours */
                } else if (kinds->prev_strict &&
                           (strcmp(type, "RECACK") == 0 || strcmp(type, "RECGET") == 0)) {
                    /* the previous record's acknowledgement, arriving late: skipped, bounded;
                     * one that names any other seq is channel misbehaviour (blocker 4b) */
                    if (kinds->prev_seq == 0u || fseq != kinds->prev_seq || payload[0] == 0 ||
                        io->payload_seq(payload, &pseq, io->ctx) != 0 || pseq != kinds->prev_seq) {
                        r->why = "PROTOCOL: an acknowledgement that is not the previous transaction's";
                        return -3;
                    }
                    if (++prev_acks > P3_RECTX_PREV_ACK_LIMIT) {
                        r->why = "PROTOCOL: too many stale acknowledgements before the reply";
                        return -3;
                    }
                    r->prev_acks = prev_acks;
                    r->stale++;
                } else if (fseq != seq || payload[0] == 0 ||
                           io->payload_seq(payload, &pseq, io->ctx) != 0 || pseq != seq) {
                    r->stale++; /* another seq's line: not ours */
                } else if (is_type(type, kinds->ack_a) || is_type(type, kinds->ack_b)) {
                    r->acked = 1;
                    strncpy(r->ack_type, type, sizeof(r->ack_type) - 1u);
                    r->ack_type[sizeof(r->ack_type) - 1u] = 0;
                    r->ack_payload = payload;
                    return 0;
                } else if (is_type(type, kinds->get)) {
                    r->gets++;
                    break; /* the host asked: send the same bytes again */
                } else {
                    r->stale++;
                }
            }
            if (++stale >= P3_RECTX_STALE_LIMIT) {
                r->idle_expiries++;
                break; /* the P3_RECTX_STALE_LIMIT-th ignored line ends the wait like the bound */
            }
        }
    }
    r->why = kinds->stop_why;
    return -1;
}

int p3_rectx_run(const char *line, size_t n, uint32_t seq, int corrupt_first,
                 const p3_rectx_io *io, char *scratch, size_t scratch_max,
                 p3_rectx_result *r)
{
    p3_tx_kinds k;

    k.ack_a = "RECACK";
    k.ack_b = NULL;
    k.get = "RECGET";
    k.stop_why = "STOP_REC: the record was not acknowledged after 3 attempts";
    k.prev_seq = 0u;
    k.prev_strict = 0;
    return p3_tx_run(line, n, seq, &k, corrupt_first, io, scratch, scratch_max, r);
}
