/* b1_carto — the on-board cartographer (stage B1), a pure unit. See b1_carto.h. */
#include "b1_carto.h"
#include "p3_derive.h"

#include <string.h>

#define B1_GOLDEN 0x9E3779B97F4A7C15ull
#define B1_WARMUP 4

/* ------------------------------------------------------------------ RNG (l6_operators.Rng) */
static uint64_t xorshift(uint64_t x)
{
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    return x;
}

void b1_rng_init(b1_rng *r, uint32_t seed32)
{
    uint64_t x = (((uint64_t)seed32 << 32) | seed32) ^ B1_GOLDEN;
    int i;
    if (x == 0ull)
        x = B1_GOLDEN;
    for (i = 0; i < B1_WARMUP; i++)
        x = xorshift(x);
    r->x = x;
}

uint32_t b1_rng_next32(b1_rng *r)
{
    r->x = xorshift(r->x);
    return (uint32_t)(r->x >> 32);
}

uint32_t b1_rng_uniform(b1_rng *r, uint32_t n)
{
    uint64_t limit = ((1ull << 32) / n) * n;
    for (;;) {
        uint32_t v = b1_rng_next32(r);
        if ((uint64_t)v < limit)
            return v % n;
    }
}

/* partial Fisher–Yates over a copy, draw order = output order (l6_operators.Rng.sample) */
static void rng_sample(b1_rng *r, uint16_t *pool, uint32_t n, uint32_t k, uint16_t *out)
{
    uint32_t i;
    for (i = 0; i < k; i++) {
        uint32_t j = i + b1_rng_uniform(r, n - i);
        uint16_t t = pool[i];
        pool[i] = pool[j];
        pool[j] = t;
        out[i] = pool[i];
    }
}

/* ------------------------------------------------------------------ helpers */
static void genome_clear(uint32_t g[B1_GENOME_WORDS]) { memset(g, 0, sizeof(uint32_t) * B1_GENOME_WORDS); }
static void genome_set(uint32_t g[B1_GENOME_WORDS], uint32_t bit) { g[bit >> 5] |= 1u << (bit & 31u); }

static int lit_position(const uint64_t t[B1_LUTS], int lut, int v) { return (int)((t[lut] >> v) & 1ull); }

static void entry_evidence(b1_entry *e, uint32_t seq)
{
    if (e->evidence_n < B1_EVIDENCE_MAX)
        e->evidence[e->evidence_n++] = (uint16_t)seq;
}

/* the set of changed entries of the last observation */
static uint16_t g_changed[B1_N + 4];
static int g_changed_n;
static void changed_add(uint16_t i)
{
    int k;
    for (k = 0; k < g_changed_n; k++)
        if (g_changed[k] == i)
            return;
    if (g_changed_n < (int)(sizeof(g_changed) / sizeof(g_changed[0])))
        g_changed[g_changed_n++] = i;
}

int b1_carto_changed(const b1_carto *c, uint16_t *out, int max)
{
    int k, n = g_changed_n < max ? g_changed_n : max;
    (void)c;
    for (k = 0; k < n; k++)
        out[k] = g_changed[k];
    return n;
}

/* ------------------------------------------------------------------ init */
void b1_carto_init(b1_carto *c, uint32_t seed, uint32_t budget)
{
    int i;
    memset(c, 0, sizeof(*c));
    c->seed = seed;
    c->budget = budget;
    b1_rng_init(&c->rng, seed);
    c->phase = B1_PH_CODE;
    c->pending = -1;
    c->pending_pair = -1;
    for (i = 0; i < B1_N; i++) {
        c->e[i].lut = -1;
        c->e[i].init = -1;
        c->e[i].state = B1_ST_UNKNOWN;
    }
    g_changed_n = 0;
}

/* ------------------------------------------------------------------ phase A decode */
static void decode_codes(b1_carto *c)
{
    int lut, v, p, i;
    /* every lit position → its code → the address; positions never lit decode nothing */
    for (lut = 0; lut < B1_LUTS; lut++) {
        for (v = 0; v < 64; v++) {
            uint32_t code = 0;
            int any = 0;
            for (p = 0; p < B1_CODE_BITS; p++) {
                if (lit_position(c->lit[p], lut, v)) {
                    code |= 1u << p;
                    any = 1;
                }
            }
            if (!any)
                continue;
            if (code < 1u || code > (uint32_t)B1_N) {
                c->anomalies++;
                continue;
            }
            i = (int)code - 1;
            if (c->e[i].state == B1_ST_DECODED) { /* two positions claim one address */
                c->e[i].state = B1_ST_CONTRADICTION;
                c->e[i].confidence = 0;
                c->anomalies++;
                changed_add((uint16_t)i);
                continue;
            }
            c->e[i].lut = (int8_t)lut;
            c->e[i].init = (int8_t)v;
            c->e[i].confidence = 1;
            c->e[i].state = B1_ST_DECODED;
            for (p = 0; p < B1_CODE_BITS; p++)
                if ((code >> p) & 1u)
                    entry_evidence(&c->e[i], c->code_seq[p]);
            changed_add((uint16_t)i);
        }
    }
    for (p = 0; p < B1_CODE_BITS; p++)
        if (c->lit_count[p] != c->set_count[p])
            c->anomalies++;
    c->decoded = 1;
}

/* phase B order: the addresses that decoded nothing first, then the decoded ones — each
 * group in an order the RNG draws (the board's own choice, replayable from the seed) */
static void draw_order(b1_carto *c)
{
    uint16_t pool[B1_N];
    uint32_t n0 = 0, n1 = 0, i;
    for (i = 0; i < B1_N; i++)
        if (c->e[i].state == B1_ST_UNKNOWN)
            pool[n0++] = (uint16_t)i;
    if (n0)
        rng_sample(&c->rng, pool, n0, n0, c->order);
    for (i = 0; i < B1_N; i++)
        if (c->e[i].state == B1_ST_DECODED)
            pool[n1++] = (uint16_t)i;
    if (n1)
        rng_sample(&c->rng, pool, n1, n1, c->order + n0);
    c->order_n = (int)(n0 + n1);
    c->order_i = 0;
}

static void draw_pairs(b1_carto *c)
{
    uint16_t conf[B1_N];
    uint32_t n = 0, i, tries = 0;
    for (i = 0; i < B1_N; i++)
        if (c->e[i].state == B1_ST_CONFIRMED)
            conf[n++] = (uint16_t)i;
    c->pairs_n = 0;
    c->pairs_i = 0;
    if (n < 2)
        return;
    /* half same-LUT, half cross-LUT, drawn by rejection from the confirmed set */
    while (c->pairs_n < B1_PAIRS_MAX && tries < 4096u) {
        uint16_t a = conf[b1_rng_uniform(&c->rng, n)];
        uint16_t b = conf[b1_rng_uniform(&c->rng, n)];
        int want_same = (c->pairs_n & 1) == 0;
        tries++;
        if (a == b)
            continue;
        if ((c->e[a].lut == c->e[b].lut) != want_same)
            continue;
        c->pairs[c->pairs_n].a = a;
        c->pairs[c->pairs_n].b = b;
        c->pairs[c->pairs_n].kind = want_same ? 0 : 1;
        c->pairs[c->pairs_n].result = 0;
        c->pairs_n++;
    }
}

/* ------------------------------------------------------------------ next */
int b1_carto_next(b1_carto *c, uint32_t genome[B1_GENOME_WORDS], int *kind_out)
{
    genome_clear(genome);
    if (c->probes_issued >= c->budget)
        return 0;
    for (;;) {
        if (c->phase == B1_PH_CODE) {
            int p = c->code_p, i;
            if (p >= B1_CODE_BITS) {           /* the decode happened in observe(); nothing pending */
                c->phase = B1_PH_CONFIRM;
                continue;
            }
            c->set_count[p] = 0;
            for (i = 0; i < B1_N; i++) {
                if ((((uint32_t)i + 1u) >> p) & 1u) {
                    genome_set(genome, (uint32_t)i);
                    c->set_count[p]++;
                }
            }
            *kind_out = B1_PH_CODE;
            c->probes_issued++;
            return 1;
        }
        if (c->phase == B1_PH_CONFIRM) {
            if (c->order_i >= c->order_n) {
                draw_pairs(c);
                c->phase = B1_PH_PAIR;
                continue;
            }
            c->pending = (int16_t)c->order[c->order_i++];
            genome_set(genome, (uint32_t)c->pending);
            *kind_out = B1_PH_CONFIRM;
            c->probes_issued++;
            return 1;
        }
        if (c->phase == B1_PH_PAIR) {
            if (c->pairs_i >= c->pairs_n) {
                c->phase = B1_PH_DONE;
                return 0;
            }
            c->pending_pair = (int16_t)c->pairs_i++;
            genome_set(genome, c->pairs[c->pending_pair].a);
            genome_set(genome, c->pairs[c->pending_pair].b);
            *kind_out = B1_PH_PAIR;
            c->probes_issued++;
            return 1;
        }
        return 0;
    }
}

/* ------------------------------------------------------------------ observe */
static uint32_t popcount_tables(const uint64_t t[B1_LUTS])
{
    uint32_t n = 0;
    int k, v;
    for (k = 0; k < B1_LUTS; k++)
        for (v = 0; v < 64; v++)
            n += (uint32_t)((t[k] >> v) & 1ull);
    return n;
}

void b1_carto_observe(b1_carto *c, uint32_t seq, const uint64_t tables[B1_LUTS])
{
    g_changed_n = 0;
    c->seq_last = seq;
    if (c->phase == B1_PH_CODE) {
        int p = c->code_p;
        memcpy(c->lit[p], tables, sizeof(uint64_t) * B1_LUTS);
        c->lit_count[p] = popcount_tables(tables);
        c->code_seq[p] = (uint16_t)seq;
        c->code_p++;
        if (c->code_p >= B1_CODE_BITS) {
            /* the last code probe: decode every lit position now, so that this record's
             * `changed` carries the decode (the host reconstruction sees all of it; the
             * wire sample is capped) and the confirmation order is drawn */
            decode_codes(c);
            draw_order(c);
            c->phase = B1_PH_CONFIRM;
        }
        return;
    }
    if (c->phase == B1_PH_CONFIRM && c->pending >= 0) {
        b1_entry *e = &c->e[c->pending];
        uint32_t n = popcount_tables(tables);
        entry_evidence(e, seq);
        if (e->state == B1_ST_UNKNOWN) {
            if (n == 0u) {
                e->state = B1_ST_NO_EFFECT;
                e->confidence = 2;
            } else if (n == 1u) {           /* decoded nothing in phase A but a single lights one: take it */
                int k, v;
                for (k = 0; k < B1_LUTS; k++)
                    for (v = 0; v < 64; v++)
                        if (lit_position(tables, k, v)) { e->lut = (int8_t)k; e->init = (int8_t)v; }
                e->state = B1_ST_CONFIRMED;
                e->confidence = 1;          /* one observation only */
                c->anomalies++;
            } else {
                e->state = B1_ST_CONTRADICTION;
                e->confidence = 0;
                c->anomalies++;
            }
        } else if (e->state == B1_ST_DECODED) {
            if (n == 1u && lit_position(tables, e->lut, e->init)) {
                e->state = B1_ST_CONFIRMED;
                e->confidence = 2;
            } else {
                e->state = B1_ST_CONTRADICTION;
                e->confidence = 0;
                c->anomalies++;
            }
        }
        changed_add((uint16_t)c->pending);
        c->pending = -1;
        return;
    }
    if (c->phase == B1_PH_PAIR && c->pending_pair >= 0) {
        b1_pair *pr = &c->pairs[c->pending_pair];
        uint64_t want[B1_LUTS];
        int k, same = 1;
        memset(want, 0, sizeof(want));
        want[c->e[pr->a].lut] |= 1ull << c->e[pr->a].init;
        want[c->e[pr->b].lut] |= 1ull << c->e[pr->b].init;
        for (k = 0; k < B1_LUTS; k++)
            if (want[k] != tables[k])
                same = 0;
        pr->result = same ? 1 : 2;
        pr->seq = (uint16_t)seq;
        if (!same)
            c->anomalies++;
        changed_add(pr->a);
        changed_add(pr->b);
        c->pending_pair = -1;
        return;
    }
}

void b1_carto_unobserved(b1_carto *c)
{
    g_changed_n = 0;
    /* a proposal that was not scored: the phase does not advance; the same proposal is
     * made again on the next call (phase A re-issues code bit code_p; B/C re-issue the
     * pending item) — the budget counted the attempt */
    if (c->phase == B1_PH_CONFIRM && c->pending >= 0) {
        c->order_i--;
        c->pending = -1;
    } else if (c->phase == B1_PH_PAIR && c->pending_pair >= 0) {
        c->pairs_i--;
        c->pending_pair = -1;
    }
}

/* ------------------------------------------------------------------ rendering */
typedef struct { char *out; size_t max, n; int overflow; } b1_w;

static void w_put(b1_w *w, const char *s)
{
    size_t l = strlen(s);
    if (w->n + l + 1 > w->max) { w->overflow = 1; return; }
    memcpy(w->out + w->n, s, l);
    w->n += l;
    w->out[w->n] = 0;
}

static void w_uint(b1_w *w, long v)
{
    char buf[16];
    int i = 15, neg = v < 0;
    unsigned long u = (unsigned long)(neg ? -v : v);
    buf[i] = 0;
    do { buf[--i] = (char)('0' + u % 10u); u /= 10u; } while (u);
    if (neg) buf[--i] = '-';
    w_put(w, buf + i);
}

static const char *state_name(int st)
{
    switch (st) {
    case B1_ST_DECODED: return "decoded";
    case B1_ST_CONFIRMED: return "confirmed";
    case B1_ST_NO_EFFECT: return "no_effect";
    case B1_ST_CONTRADICTION: return "contradiction";
    default: return "unknown";
    }
}

/* one entry: [i, lut, init, confidence, "state", [evidence...]] */
static void w_entry(b1_w *w, const b1_carto *c, int i)
{
    const b1_entry *e = &c->e[i];
    int k;
    w_put(w, "["); w_uint(w, i); w_put(w, ","); w_uint(w, e->lut); w_put(w, ","); w_uint(w, e->init);
    w_put(w, ","); w_uint(w, e->confidence); w_put(w, ",\""); w_put(w, state_name(e->state)); w_put(w, "\",[");
    for (k = 0; k < e->evidence_n; k++) {
        if (k) w_put(w, ",");
        w_uint(w, e->evidence[k]);
    }
    w_put(w, "]]");
}

size_t b1_carto_render(b1_carto *c, char *out, size_t max)
{
    b1_w w;
    int i;
    w.out = out; w.max = max; w.n = 0; w.overflow = 0;
    out[0] = 0;
    /* canonical: {"anomalies":A,"entries":[...],"pairs":[[a,b,kind,result,seq],...],"seed":S,"version":"carto-v1"} */
    w_put(&w, "{\"anomalies\":"); w_uint(&w, (long)c->anomalies); w_put(&w, ",\"entries\":[");
    for (i = 0; i < B1_N; i++) {
        if (i) w_put(&w, ",");
        w_entry(&w, c, i);
    }
    w_put(&w, "],\"pairs\":[");
    for (i = 0; i < c->pairs_n; i++) {
        const b1_pair *p = &c->pairs[i];
        if (i) w_put(&w, ",");
        w_put(&w, "["); w_uint(&w, p->a); w_put(&w, ","); w_uint(&w, p->b); w_put(&w, ","); w_uint(&w, p->kind);
        w_put(&w, ","); w_uint(&w, p->result); w_put(&w, ","); w_uint(&w, p->seq); w_put(&w, "]");
    }
    w_put(&w, "],\"seed\":"); w_uint(&w, (long)c->seed); w_put(&w, ",\"version\":\"" B1_CARTO_VERSION "\"}");
    if (w.overflow)
        return 0;
    {
        p3_sha256 h;
        p3_sha256_init(&h);
        p3_sha256_update(&h, (const uint8_t *)out, w.n);
        p3_sha256_final(&h, c->map_sha256);
        p3_hex(c->map_sha256, 32, c->map_sha256_hex);
    }
    return w.n;
}

size_t b1_carto_record_json(const b1_carto *c, int kind, uint32_t seq, const uint16_t *changed, int changed_n,
                            char *out, size_t max)
{
    b1_w w;
    int i;
    (void)seq;
    w.out = out; w.max = max; w.n = 0; w.overflow = 0;
    out[0] = 0;
    /* sorted keys: anomalies < changed < map_sha256 < phase < probes_issued < version */
    w_put(&w, "{\"anomalies\":"); w_uint(&w, (long)c->anomalies); w_put(&w, ",\"changed\":[");
    for (i = 0; i < changed_n; i++) {
        if (i) w_put(&w, ",");
        w_entry(&w, c, changed[i]);
    }
    w_put(&w, "],\"map_sha256\":\""); w_put(&w, c->map_sha256_hex); w_put(&w, "\",\"phase\":");
    w_put(&w, kind == B1_PH_CODE ? "\"code\"" : kind == B1_PH_CONFIRM ? "\"confirm\"" : kind == B1_PH_PAIR ? "\"pair\"" : "\"baseline\"");
    w_put(&w, ",\"probes_issued\":"); w_uint(&w, (long)c->probes_issued);
    w_put(&w, ",\"version\":\"" B1_CARTO_VERSION "\"}");
    return w.overflow ? 0 : w.n;
}
