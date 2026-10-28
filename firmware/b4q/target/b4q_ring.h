/* b4q_ring — the PS-side EVIDENCE LOG as a pure unit (docs/b4q_source_audit.md §3.1): an append-only byte log of every access the
 * executing side makes through the HAL (the carrier window, the DevC registers, the DDR buffers, the identity page), the
 * transaction marks and the executing side's events, with a running sha256 the host's pulled bytes must reproduce. Fixed 16-byte
 * records; identical consecutive reads (the polls) compressed into one record with a count; never overwritten — a full log sets
 * `overflow` and the application stops admitting transactions. The log lives in a strongly-ordered DDR region on the board and in
 * a buffer in the host harness; the same source on both. No MMIO here: the HAL calls b4q_ring_access, the application the marks. */
#ifndef B4Q_RING_H
#define B4Q_RING_H

#include <stddef.h>
#include <stdint.h>

#define B4Q_RING_RECORD 16u
#define B4Q_RING_KIND_WIN 1u     /* a carrier-window access: addr = the offset */
#define B4Q_RING_KIND_DEVC 2u    /* a DevC register access: addr = the absolute address */
#define B4Q_RING_KIND_BUF 3u     /* a DDR buffer / page / SLCR access: addr = the absolute address */
#define B4Q_RING_KIND_MARK 4u    /* a mark: addr = the mark id, data = 0 */
#define B4Q_RING_KIND_END 5u     /* the log's close: the running digest follows in the next two records' bytes */
#define B4Q_RING_OP_RD 0u
#define B4Q_RING_OP_WR 1u
#define B4Q_RING_RESP_BIT 0x8000u  /* set in `count` when the access was refused (SLVERR / never issued) */
#define B4Q_RING_RUN_BIT 0x4000u   /* set in `count` when the record is a RUN: `count` accesses at addr, addr + 4, ... with the same data (the sentinel sweeps);
                                      clear: `count` identical accesses at the one addr (the polls) */
#define B4Q_RING_COUNT_MASK 0x3FFFu
#define B4Q_RING_MARK_OPEN 1u
#define B4Q_RING_MARK_TX_BEGIN 2u
#define B4Q_RING_MARK_P6_SEALED 3u
#define B4Q_RING_MARK_TX_END 4u
#define B4Q_RING_MARK_TX_INTERRUPTED 5u

typedef struct b4q_ring b4q_ring;
struct b4q_ring {
    uint8_t *base;
    uint32_t capacity;       /* bytes */
    uint32_t used;           /* bytes appended */
    int overflow;            /* a record did not fit: nothing further is appended */
    uint32_t records, compressed;
    uint8_t digest[32];      /* sha256 of bytes[0:used], valid after b4q_ring_digest() (computed over the final bytes: the poll counts are amended in place) */
    /* the last record, for poll compression */
    uint8_t last_kind, last_op; uint32_t last_addr, last_data; uint16_t last_count; int have_last;
};

void b4q_ring_init(b4q_ring *r, uint8_t *base, uint32_t capacity);
/* append one access; identical consecutive reads (kind, addr, data, response) are counted into the previous record */
void b4q_ring_access(b4q_ring *r, uint8_t kind, uint8_t op, uint32_t addr, uint32_t data, int refused, uint32_t tick);
void b4q_ring_mark(b4q_ring *r, uint32_t mark, uint32_t tick);
/* the digest of bytes[0:used] (a snapshot; appending continues) */
void b4q_ring_digest(b4q_ring *r, uint8_t out[32]);
/* the bytes of [offset, offset + n) into out; the count copied (0 when offset >= used) */
uint32_t b4q_ring_read(const b4q_ring *r, uint32_t offset, uint32_t n, uint8_t *out);

#endif /* B4Q_RING_H */
