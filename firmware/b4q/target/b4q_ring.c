/* b4q_ring — see b4q_ring.h. */
#include "b4q_ring.h"
#include "b4q_derive.h"

#include <string.h>

static void put32(uint8_t *p, uint32_t v) { p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16); p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v; }
static void put16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v; }

void b4q_ring_init(b4q_ring *r, uint8_t *base, uint32_t capacity)
{
    memset(r, 0, sizeof *r);
    r->base = base; r->capacity = capacity - (capacity % B4Q_RING_RECORD);
}

static void append(b4q_ring *r, uint8_t kind, uint8_t op, uint16_t count, uint32_t addr, uint32_t data, uint32_t tick)
{
    uint8_t rec[B4Q_RING_RECORD];
    if (r->overflow) return;
    if (r->used + B4Q_RING_RECORD > r->capacity) { r->overflow = 1; return; }
    put32(rec, tick); rec[4] = kind; rec[5] = op; put16(rec + 6, count); put32(rec + 8, addr); put32(rec + 12, data);
    memcpy(r->base + r->used, rec, B4Q_RING_RECORD);
    r->used += B4Q_RING_RECORD; r->records++;
    r->last_kind = kind; r->last_op = op; r->last_addr = addr; r->last_data = data; r->last_count = count; r->have_last = 1;
}

void b4q_ring_access(b4q_ring *r, uint8_t kind, uint8_t op, uint32_t addr, uint32_t data, int refused, uint32_t tick)
{
    uint16_t count = (uint16_t)(1u | (refused ? B4Q_RING_RESP_BIT : 0u));
    uint16_t n;
    if (r->overflow) return;
    n = (uint16_t)(r->last_count & B4Q_RING_COUNT_MASK);
    if (r->have_last && r->last_kind == kind && r->last_op == op && r->last_data == data
        && (r->last_count & B4Q_RING_RESP_BIT) == (count & B4Q_RING_RESP_BIT) && n < B4Q_RING_COUNT_MASK) {
        /* a POLL: an identical consecutive read at the same address (STATUS / INT_STS) — counted into the previous record, amended in
         * place (the digest is computed over the final bytes, b4q_ring_digest) */
        if (op == B4Q_RING_OP_RD && !(r->last_count & B4Q_RING_RUN_BIT) && r->last_addr == addr) {
            r->last_count++;
            put16(r->base + r->used - B4Q_RING_RECORD + 6, r->last_count);
            r->compressed++;
            return;
        }
        /* a RUN: the same data at the next word address (the sentinel prefill and its verification) — a run record counts the words */
        if (kind == B4Q_RING_KIND_BUF && addr == r->last_addr + 4u * n && (n == 1u || (r->last_count & B4Q_RING_RUN_BIT))) {
            r->last_count = (uint16_t)((r->last_count | B4Q_RING_RUN_BIT) + 1u);
            put16(r->base + r->used - B4Q_RING_RECORD + 6, r->last_count);
            r->compressed++;
            return;
        }
    }
    append(r, kind, op, count, addr, data, tick);
}

void b4q_ring_mark(b4q_ring *r, uint32_t mark, uint32_t tick)
{
    append(r, B4Q_RING_KIND_MARK, 0u, 1u, mark, 0u, tick);
    r->have_last = 0;                                     /* a mark breaks poll compression */
}

void b4q_ring_digest(b4q_ring *r, uint8_t out[32])
{
    p3_sha256 c;                                          /* over the final bytes (the amended counts included) */
    p3_sha256_init(&c);
    p3_sha256_update(&c, r->base, r->used);
    p3_sha256_final(&c, out);
    memcpy(r->digest, out, 32);
}

uint32_t b4q_ring_read(const b4q_ring *r, uint32_t offset, uint32_t n, uint8_t *out)
{
    if (offset >= r->used) return 0;
    if (n > r->used - offset) n = r->used - offset;
    memcpy(out, r->base + offset, n);
    return n;
}
