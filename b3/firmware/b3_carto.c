/* b3_carto — the specimen cartographer (see b3_carto.h). Freestanding C99. */
#include "b3_carto.h"

#include <string.h>

/* ------------------------------------------------------------------ position sets (384 bits) */

static void set_clear(uint64_t s[B3_CARTO_WORDS])
{
    memset(s, 0, sizeof(uint64_t) * B3_CARTO_WORDS);
}

static int set_has(const uint64_t s[B3_CARTO_WORDS], int pos)
{
    return (int)((s[pos / 64] >> (pos % 64)) & 1u);
}

static void set_add(uint64_t s[B3_CARTO_WORDS], int pos)
{
    s[pos / 64] |= (uint64_t)1 << (pos % 64);
}

static void set_remove(uint64_t s[B3_CARTO_WORDS], int pos)
{
    s[pos / 64] &= ~((uint64_t)1 << (pos % 64));
}

static int set_intersects(const uint64_t a[B3_CARTO_WORDS], const uint64_t b[B3_CARTO_WORDS])
{
    int w;
    for (w = 0; w < B3_CARTO_WORDS; w++)
        if (a[w] & b[w])
            return 1;
    return 0;
}

static void set_and(uint64_t out[B3_CARTO_WORDS], const uint64_t a[B3_CARTO_WORDS], const uint64_t b[B3_CARTO_WORDS])
{
    int w;
    for (w = 0; w < B3_CARTO_WORDS; w++)
        out[w] = a[w] & b[w];
}

static void set_andnot(uint64_t out[B3_CARTO_WORDS], const uint64_t a[B3_CARTO_WORDS], const uint64_t b[B3_CARTO_WORDS])
{
    int w;
    for (w = 0; w < B3_CARTO_WORDS; w++)
        out[w] = a[w] & ~b[w];
}

static int set_empty(const uint64_t s[B3_CARTO_WORDS])
{
    int w;
    for (w = 0; w < B3_CARTO_WORDS; w++)
        if (s[w])
            return 0;
    return 1;
}

static int set_count(const uint64_t s[B3_CARTO_WORDS])
{
    int w, n = 0;
    for (w = 0; w < B3_CARTO_WORDS; w++) {
        uint64_t x = s[w];
        while (x) {
            x &= x - 1;
            n++;
        }
    }
    return n;
}

/* The lowest position of a set with exactly one member (or the lowest member of any non-empty set). */
static int set_first(const uint64_t s[B3_CARTO_WORDS])
{
    int w;
    for (w = 0; w < B3_CARTO_WORDS; w++) {
        if (s[w]) {
            uint64_t x = s[w];
            int b = 0;
            while (!(x & 1u)) {
                x >>= 1;
                b++;
            }
            return w * 64 + b;
        }
    }
    return B3_CARTO_NO_POSITION;
}

/* ------------------------------------------------------------------ the state */

void b3_carto_init(b3_carto *c)
{
    int i;
    memset(c, 0, sizeof(*c));
    for (i = 0; i < B3_CARTO_N; i++)
        c->decoded[i] = B3_CARTO_NO_POSITION;
}

int b3_carto_decoded_position(const b3_carto *c, int address)
{
    if (address < 0 || address >= B3_CARTO_N)
        return B3_CARTO_NO_POSITION;
    return c->decoded[address];
}

int b3_carto_decoded_count(const b3_carto *c)
{
    int i, n = 0;
    for (i = 0; i < B3_CARTO_N; i++)
        if (c->decoded[i] != B3_CARTO_NO_POSITION)
            n++;
    return n;
}

/* The whole check, on the copy `w` of the state; returns the newly-decoded count, or -1 on any
 * inconsistency (the copy is then discarded by the caller — nothing was committed). */
static int check_on_copy(b3_carto *w, const uint16_t *moved, int n_moved, const uint16_t *delta, int n_delta,
                         uint16_t *newly, int newly_cap)
{
    uint8_t seen_addr[B3_CARTO_N];
    uint64_t remaining[B3_CARTO_WORDS];
    int j, n_newly = 0, changed;

    /* the intervention: non-empty, in range, no duplicate */
    if (n_moved <= 0 || n_moved > B3_CARTO_N)
        return -1;
    memset(seen_addr, 0, sizeof(seen_addr));
    for (j = 0; j < n_moved; j++) {
        if (moved[j] >= B3_CARTO_N || seen_addr[moved[j]])
            return -1;
        seen_addr[moved[j]] = 1;
    }
    /* the delta: in range, no duplicate, exactly one position per moved address */
    if (n_delta < 0 || n_delta > B3_CARTO_POSITIONS)
        return -1;
    set_clear(remaining);
    for (j = 0; j < n_delta; j++) {
        if (delta[j] >= B3_CARTO_POSITIONS || set_has(remaining, delta[j]))
            return -1;
        set_add(remaining, delta[j]);
    }
    if (n_delta != n_moved)
        return -1;
    /* every decoded moved address must have toggled at its own position; consume those */
    for (j = 0; j < n_moved; j++) {
        int pos = w->decoded[moved[j]];
        if (pos != B3_CARTO_NO_POSITION) {
            if (!set_has(remaining, pos))
                return -1;
            set_remove(remaining, pos);
        }
    }
    /* a toggled position owned by a decoded address that was not moved */
    if (set_intersects(remaining, w->taken))
        return -1;
    /* the pending addresses narrow by intersection (first entry: the remaining set itself) */
    for (j = 0; j < n_moved; j++) {
        int i = moved[j];
        if (w->decoded[i] != B3_CARTO_NO_POSITION)
            continue;
        if (!w->has_cand[i]) {
            memcpy(w->cand[i], remaining, sizeof(remaining));
            w->has_cand[i] = 1;
            w->order[w->n_order++] = (uint16_t)i;
        } else {
            set_and(w->cand[i], w->cand[i], remaining);
        }
        if (set_empty(w->cand[i]))
            return -1;
    }
    /* the global closure, in the candidates' first-pending order (the Python dict's) */
    do {
        changed = 0;
        for (j = 0; j < w->n_order; j++) {
            uint64_t free_[B3_CARTO_WORDS];
            int i = w->order[j], n;
            if (w->decoded[i] != B3_CARTO_NO_POSITION)
                continue;
            set_andnot(free_, w->cand[i], w->taken);
            n = set_count(free_);
            if (n == 1) {
                int pos = set_first(free_);
                w->decoded[i] = (int16_t)pos;
                set_add(w->taken, pos);
                if (newly && n_newly < newly_cap)
                    newly[n_newly] = (uint16_t)i;
                n_newly++;
                changed = 1;
            } else if (n == 0) {
                return -1;
            }
        }
    } while (changed);
    return n_newly;
}

int b3_carto_observe(b3_carto *c, b3_carto *scratch, const uint16_t *moved, int n_moved, const uint16_t *delta, int n_delta,
                     uint16_t *newly, int newly_cap)
{
    int n;
    if (scratch == NULL || scratch == c)
        return B3_CARTO_BAD_CALL;                        /* a programming error, not a specimen: nothing done */
    memcpy(scratch, c, sizeof(*scratch));                /* every check runs on the caller's copy, never a stack frame */
    n = check_on_copy(scratch, moved, n_moved, delta, n_delta, newly, newly_cap);
    if (n < 0) {
        c->anomalies++;                                  /* counted; nothing else changes */
        return B3_CARTO_REFUSED;
    }
    if (n > 0)
        scratch->version++;
    memcpy(c, scratch, sizeof(*c));                      /* committed whole, or not at all */
    return n;
}

/* ------------------------------------------------------------------ the commitment text */

typedef struct {
    b3_carto_emit emit;
    void *ctx;
    size_t n;
} writer;

static void put(writer *wr, const char *s, size_t n)
{
    if (n) {
        wr->emit(wr->ctx, s, n);
        wr->n += n;
    }
}

static void put_str(writer *wr, const char *s)
{
    put(wr, s, strlen(s));
}

static void put_uint(writer *wr, uint32_t v)
{
    char buf[10];
    int n = 0;
    if (v == 0) {
        put(wr, "0", 1);
        return;
    }
    while (v) {
        buf[n++] = (char)('0' + (v % 10));
        v /= 10;
    }
    while (n)
        put(wr, &buf[--n], 1);
}

size_t b3_carto_state_render(const b3_carto *c, b3_carto_emit emit, void *ctx)
{
    writer wr;
    int i, first;
    wr.emit = emit;
    wr.ctx = ctx;
    wr.n = 0;
    put_str(&wr, B3_CARTO_VERSION);
    put_str(&wr, "|");
    put_uint(&wr, c->version);
    put_str(&wr, "|");
    put_uint(&wr, c->anomalies);
    put_str(&wr, "|");
    first = 1;                                           /* decoded: i:k:v sorted by i */
    for (i = 0; i < B3_CARTO_N; i++) {
        int pos = c->decoded[i];
        if (pos == B3_CARTO_NO_POSITION)
            continue;
        if (!first)
            put_str(&wr, ";");
        first = 0;
        put_uint(&wr, (uint32_t)i);
        put_str(&wr, ":");
        put_uint(&wr, (uint32_t)(pos / 64));
        put_str(&wr, ":");
        put_uint(&wr, (uint32_t)(pos % 64));
    }
    put_str(&wr, "|");
    first = 1;                                           /* candidates: i:k.v,k.v sorted by i then position */
    for (i = 0; i < B3_CARTO_N; i++) {
        int pos, firstpos = 1;
        if (!c->has_cand[i])
            continue;
        if (!first)
            put_str(&wr, ";");
        first = 0;
        put_uint(&wr, (uint32_t)i);
        put_str(&wr, ":");
        for (pos = 0; pos < B3_CARTO_POSITIONS; pos++) {
            if (!set_has(c->cand[i], pos))
                continue;
            if (!firstpos)
                put_str(&wr, ",");
            firstpos = 0;
            put_uint(&wr, (uint32_t)(pos / 64));
            put_str(&wr, ".");
            put_uint(&wr, (uint32_t)(pos % 64));
        }
    }
    return wr.n;
}
