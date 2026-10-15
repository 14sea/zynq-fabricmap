/* b2_search — the on-board search of stage B2, a pure unit. See b2_search.h. */
#include "b2_search.h"
#include "p3_data.h"
#include "p3_derive.h"

#include <stdio.h>
#include <string.h>

#define B2_GOLDEN 0x9E3779B97F4A7C15ull
#define B2_WARMUP 4

/* ------------------------------------------------------------------ RNG (l6_operators.Rng) */
static uint64_t xorshift(uint64_t x)
{
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    return x;
}

void b2_rng_init(b2_rng *r, uint32_t seed32)
{
    uint64_t x = (((uint64_t)seed32 << 32) | seed32) ^ B2_GOLDEN;
    int i;
    if (x == 0ull)
        x = B2_GOLDEN;
    for (i = 0; i < B2_WARMUP; i++)
        x = xorshift(x);
    r->x = x;
}

uint32_t b2_rng_next32(b2_rng *r)
{
    r->x = xorshift(r->x);
    return (uint32_t)(r->x >> 32);
}

uint32_t b2_rng_uniform(b2_rng *r, uint32_t n)
{
    uint64_t limit = ((1ull << 32) / n) * n;
    for (;;) {
        uint32_t v = b2_rng_next32(r);
        if ((uint64_t)v < limit)
            return v % n;
    }
}

/* partial Fisher–Yates over a copy, draw order = output order (l6_operators.Rng.sample) */
static void rng_sample(b2_rng *r, uint16_t *pool, uint32_t n, uint32_t k, uint16_t *out)
{
    uint32_t i;
    for (i = 0; i < k; i++) {
        uint32_t j = i + b2_rng_uniform(r, n - i);
        uint16_t t = pool[i];
        pool[i] = pool[j];
        pool[j] = t;
        out[i] = pool[i];
    }
}

static void sort_u16(uint16_t *a, int n)
{
    int i, j;
    for (i = 1; i < n; i++) {
        uint16_t v = a[i];
        for (j = i - 1; j >= 0 && a[j] > v; j--)
            a[j + 1] = a[j];
        a[j + 1] = v;
    }
}

/* ------------------------------------------------------------------ the frozen seed rule */
static int seed_excluded(uint32_t v)
{
    int lo = 0, hi = B2_EXCLUDED_SEEDS_N - 1;
    while (lo <= hi) {                       /* the table is generated sorted */
        int mid = lo + (hi - lo) / 2;
        uint32_t m = (uint32_t)B2_EXCLUDED_SEEDS[mid];
        if (m == v)
            return 1;
        if (m < v)
            lo = mid + 1;
        else
            hi = mid - 1;
    }
    return 0;
}

void b2_pair_seeds(uint32_t master, int count, uint32_t *out)
{
    b2_rng r;
    int n = 0;
    b2_rng_init(&r, master);
    while (n < count) {
        uint32_t l = b2_rng_next32(&r);
        uint32_t o = b2_rng_next32(&r);
        int i, clash = 0;
        if (seed_excluded(l) || seed_excluded(o) || l == o)
            continue;
        for (i = 0; i < 2 * n; i++)          /* `seen`: every seed drawn so far is distinct */
            if (out[i] == l || out[i] == o)
                clash = 1;
        if (clash)
            continue;
        out[2 * n] = l;
        out[2 * n + 1] = o;
        n++;
    }
}

/* ------------------------------------------------------------------ the landscape */
void b2_universe_mask(uint64_t masks[B2_LUTS])
{
    int i;
    for (i = 0; i < B2_LUTS; i++)
        masks[i] = 0ull;
    for (i = 0; i < B2_MAP_N; i++)
        masks[B2_MAP_LUT[i]] |= 1ull << B2_MAP_INIT[i];
}

void b2_target(uint32_t landscape_seed, const uint64_t masks[B2_LUTS], uint64_t target[B2_LUTS])
{
    b2_rng r;
    int k, v;
    b2_rng_init(&r, landscape_seed);
    for (k = 0; k < B2_LUTS; k++)
        target[k] = 0ull;
    for (k = 0; k < B2_LUTS; k++)
        for (v = 0; v < B2_VECTORS; v++) {
            uint32_t bit = b2_rng_next32(&r) & 1u;
            if (bit && ((masks[k] >> v) & 1ull))
                target[k] |= 1ull << v;
        }
}

/* ------------------------------------------------------------------ F1 */
static uint32_t column_word(const uint64_t t[B2_LUTS], int v)
{
    uint32_t w = 0u;
    int k;
    for (k = 0; k < B2_LUTS; k++)
        w |= (uint32_t)((t[k] >> v) & 1ull) << k;
    return w;
}

static int32_t f1_over(const uint64_t tables[B2_LUTS], const uint64_t target[B2_LUTS],
                      const unsigned char *vectors, int n)
{
    int32_t f = 0;
    int i;
    for (i = 0; i < n; i++) {
        int v = (int)vectors[i];
        if (column_word(tables, v) == column_word(target, v))
            f++;
    }
    return f;
}

int32_t b2_f1_train(const uint64_t tables[B2_LUTS], const uint64_t target[B2_LUTS])
{
    return f1_over(tables, target, B2_TRAIN_VECTORS, B2_TRAIN_COUNT);
}

int32_t b2_f1_holdout(const uint64_t tables[B2_LUTS], const uint64_t target[B2_LUTS])
{
    return f1_over(tables, target, B2_HOLDOUT_VECTORS, B2_HOLDOUT_COUNT);
}

/* ------------------------------------------------------------------ genome helpers */
static void genome_clear(uint32_t g[B2_GENOME_WORDS]) { memset(g, 0, sizeof(uint32_t) * B2_GENOME_WORDS); }
static void genome_flip(uint32_t g[B2_GENOME_WORDS], uint32_t bit) { g[bit >> 5] ^= 1u << (bit & 31u); }

/* ------------------------------------------------------------------ the map view */
static void build_view(b2_search *s)
{
    int i, v;
    unsigned char is_train[B2_VECTORS];
    memset(is_train, 0, sizeof(is_train));
    for (i = 0; i < B2_TRAIN_COUNT; i++)
        is_train[B2_TRAIN_VECTORS[i]] = 1u;
    memset(s->col_n, 0, sizeof(s->col_n));
    for (i = 0; i < B2_MAP_N; i++) {
        int col = (int)B2_MAP_INIT[i];
        if (!is_train[col])
            continue;
        if (s->col_n[col] < B2_LUTS)
            s->col_bits[col][s->col_n[col]++] = (uint16_t)i;
    }
    s->col_keys_n = 0;
    for (v = 0; v < B2_VECTORS; v++) {           /* the operator's draw list, in a fixed order */
        if (s->col_n[v] == 0u)
            continue;
        sort_u16(s->col_bits[v], (int)s->col_n[v]);
        s->col_keys[s->col_keys_n++] = (uint8_t)v;
    }
}

/* ------------------------------------------------------------------ the operators */
static int random_safe_move(b2_search *s, uint16_t *bits)
{
    uint16_t pool[B2_N];
    uint32_t k, i;
    k = 1u + b2_rng_uniform(&s->rng, (uint32_t)B2_KMAX);
    for (i = 0; i < (uint32_t)B2_N; i++)
        pool[i] = (uint16_t)i;
    rng_sample(&s->rng, pool, (uint32_t)B2_N, k, bits);
    sort_u16(bits, (int)k);
    return (int)k;
}

static int column_move(b2_search *s, uint16_t *bits)
{
    uint16_t pool[B2_LUTS];
    int col = (int)s->col_keys[b2_rng_uniform(&s->rng, (uint32_t)s->col_keys_n)];
    uint32_t n = (uint32_t)s->col_n[col];
    uint32_t cap = n < (uint32_t)B2_KMAX ? n : (uint32_t)B2_KMAX;
    uint32_t k = 1u + b2_rng_uniform(&s->rng, cap);
    uint32_t i;
    for (i = 0; i < n; i++)
        pool[i] = s->col_bits[col][i];
    rng_sample(&s->rng, pool, n, k, bits);
    sort_u16(bits, (int)k);
    return (int)k;
}

static int draw_move(b2_search *s, uint16_t *bits, int *kind)
{
    if (s->arm == B2_ARM_RANDOM_SAFE || s->col_keys_n == 0) {
        *kind = B2_MOVE_RANDOM;
        return random_safe_move(s, bits);
    }
    if (b2_rng_uniform(&s->rng, 2u) == 0u) {
        *kind = B2_MOVE_RANDOM;
        return random_safe_move(s, bits);
    }
    *kind = B2_MOVE_COLUMN;
    return column_move(s, bits);
}

/* ------------------------------------------------------------------ selection */
/* truncation over pop + children by (-fit, born): the mu best, ties to the older */
static void select_generation(b2_search *s)
{
    b2_indiv pool[B2_MU + B2_LAMBDA];
    int n = 0, i, j;
    for (i = 0; i < B2_MU; i++)
        pool[n++] = s->pop[i];
    for (i = 0; i < s->nchild; i++)
        pool[n++] = s->child[i];
    for (i = 1; i < n; i++) {                   /* insertion sort: n <= 12 */
        b2_indiv v = pool[i];
        for (j = i - 1; j >= 0 && (pool[j].fit < v.fit || (pool[j].fit == v.fit && pool[j].born > v.born)); j--)
            pool[j + 1] = pool[j];
        pool[j + 1] = v;
    }
    for (i = 0; i < B2_MU; i++)
        s->pop[i] = pool[i];
    s->nchild = 0;
    s->generation++;
}

/* ------------------------------------------------------------------ the run */
void b2_search_init(b2_search *s, int arm, uint32_t landscape_seed, uint32_t operator_seed,
                    uint32_t budget, const uint64_t base[B2_LUTS])
{
    int i, k;
    memset(s, 0, sizeof(*s));
    s->arm = arm;
    s->landscape_seed = landscape_seed;
    s->operator_seed = operator_seed;
    s->budget = budget;
    b2_universe_mask(s->masks);
    b2_target(landscape_seed, s->masks, s->target);
    build_view(s);
    b2_rng_init(&s->rng, operator_seed);
    s->base_fit = b2_f1_train(base, s->target);
    s->best = s->base_fit;
    for (i = 0; i < B2_MU; i++) {
        genome_clear(s->pop[i].genome);
        for (k = 0; k < B2_LUTS; k++)
            s->pop[i].tables[k] = base[k];
        s->pop[i].fit = s->base_fit;
        s->pop[i].born = (uint32_t)i;
    }
    s->born = (uint32_t)B2_MU;
    s->champion_holdout = -1;
}

int b2_search_next(b2_search *s, uint32_t genome[B2_GENOME_WORDS], int *kind_out)
{
    int i;
    if (s->pending || s->evals >= s->budget)
        return 0;
    s->pending_parent = (int)b2_rng_uniform(&s->rng, (uint32_t)B2_MU);
    s->pending_parent_born = s->pop[s->pending_parent].born;
    s->pending_nbits = draw_move(s, s->pending_bits, &s->pending_kind);
    if (s->pending_kind == B2_MOVE_COLUMN)
        s->column_moves++;
    memcpy(s->pending_genome, s->pop[s->pending_parent].genome, sizeof(s->pending_genome));
    for (i = 0; i < s->pending_nbits; i++)
        genome_flip(s->pending_genome, (uint32_t)s->pending_bits[i]);
    memcpy(genome, s->pending_genome, sizeof(s->pending_genome));
    if (kind_out)
        *kind_out = s->pending_kind;
    s->pending = 1;
    return 1;
}

void b2_search_observe(b2_search *s, const uint64_t tables[B2_LUTS])
{
    b2_indiv *c;
    int k;
    if (!s->pending)
        return;
    c = &s->child[s->nchild++];
    memcpy(s->last_bits, s->pending_bits, sizeof(s->last_bits));
    s->pending_nbits_last = s->pending_nbits;
    s->last_kind = s->pending_kind;
    s->last_parent_born = s->pending_parent_born;
    memcpy(c->genome, s->pending_genome, sizeof(c->genome));
    for (k = 0; k < B2_LUTS; k++)
        c->tables[k] = tables[k];
    c->fit = b2_f1_train(tables, s->target);
    c->born = s->born++;
    s->evals++;
    if (c->fit > s->best)
        s->best = c->fit;
    s->last_fit = c->fit;
    s->pending = 0;
    /* the generation closes on the lambda-th child, or where the budget cut it short */
    if (s->nchild >= B2_LAMBDA || s->evals >= s->budget) {
        select_generation(s);
        s->last_selected = 1;
    } else {
        s->last_selected = 0;
    }
}

void b2_search_unobserved(b2_search *s)
{
    s->pending = 0;
    s->last_selected = 0;
}

int b2_search_champion(const b2_search *s, uint32_t genome[B2_GENOME_WORDS], int32_t *fit_out)
{
    if (s->pending || s->nchild != 0)
        return 0;                              /* a generation is open: there is no champion yet */
    memcpy(genome, s->pop[0].genome, sizeof(s->pop[0].genome));
    if (fit_out)
        *fit_out = s->pop[0].fit;
    return 1;
}

int b2_search_champion_next(b2_search *s, uint32_t genome[B2_GENOME_WORDS])
{
    if (s->evals < s->budget || s->champion_done || s->champion_pending)
        return 0;
    if (!b2_search_champion(s, genome, NULL))
        return 0;
    s->champion_pending = 1;
    return 1;
}

void b2_search_champion_observe(b2_search *s, const uint64_t tables[B2_LUTS])
{
    if (!s->champion_pending)
        return;
    s->champion_holdout = b2_f1_holdout(tables, s->target);
    s->champion_pending = 0;
    s->champion_done = 1;
}

/* ------------------------------------------------------------------ the commitment and the record block */
static void hex32(const uint8_t d[32], char out[65])
{
    static const char *H = "0123456789abcdef";
    int i;
    for (i = 0; i < 32; i++) {
        out[2 * i] = H[(d[i] >> 4) & 0xf];
        out[2 * i + 1] = H[d[i] & 0xf];
    }
    out[64] = '\0';
}

void b2_search_state_hex(const b2_search *s, char out[65])
{
    p3_sha256 c;
    uint8_t digest[32];
    char buf[256];
    char ghex[B2_GENOME_WORDS * 8 + 1];
    int i, n;
    p3_sha256_init(&c);
    n = snprintf(buf, sizeof(buf), "%s|%d|%lu|%lu|%lu|%lu|%lu|%ld|", B2_SEARCH_VERSION, s->arm,
                 (unsigned long)s->landscape_seed, (unsigned long)s->operator_seed, (unsigned long)s->budget,
                 (unsigned long)s->evals, (unsigned long)s->generation, (long)s->best);
    p3_sha256_update(&c, (const uint8_t *)buf, (size_t)n);
    for (i = 0; i < B2_MU; i++) {
        p3_genome_to_hex(s->pop[i].genome, ghex);
        n = snprintf(buf, sizeof(buf), "%ld:%lu:%s;", (long)s->pop[i].fit, (unsigned long)s->pop[i].born, ghex);
        p3_sha256_update(&c, (const uint8_t *)buf, (size_t)n);
    }
    p3_sha256_final(&c, digest);
    hex32(digest, out);
}

size_t b2_search_record_json(const b2_search *s, int pair, const char *arm, uint32_t eval_n,
                             int32_t holdout, char *out, size_t max)
{
    char state[65];
    size_t at = 0;
    int i, n;
    b2_search_state_hex(s, state);
    /* sorted keys: arm < best < column_moves < eval < fitness < generation < holdout <
     * landscape_seed < move < operator_seed < pair < parent_born < population < selected <
     * state_sha256 < version */
    n = snprintf(out, max, "{\"arm\":\"%s\",\"best\":%ld,\"column_moves\":%lu,\"eval\":%lu,",
                 arm, (long)s->best, (unsigned long)s->column_moves, (unsigned long)eval_n);
    if (n < 0 || (size_t)n >= max)
        return 0u;
    at = (size_t)n;
    if (holdout >= 0)
        n = snprintf(out + at, max - at, "\"fitness\":null,\"generation\":%lu,\"holdout\":%ld,",
                     (unsigned long)s->generation, (long)holdout);
    else
        n = snprintf(out + at, max - at, "\"fitness\":%ld,\"generation\":%lu,\"holdout\":null,",
                     (long)s->last_fit, (unsigned long)s->generation);
    if (n < 0 || (size_t)n >= max - at)
        return 0u;
    at += (size_t)n;
    n = snprintf(out + at, max - at, "\"landscape_seed\":%lu,\"move\":", (unsigned long)s->landscape_seed);
    if (n < 0 || (size_t)n >= max - at)
        return 0u;
    at += (size_t)n;
    if (holdout >= 0) {
        n = snprintf(out + at, max - at, "null,");
    } else {
        n = snprintf(out + at, max - at, "{\"bits\":[");
        if (n < 0 || (size_t)n >= max - at)
            return 0u;
        at += (size_t)n;
        for (i = 0; i < s->pending_nbits_last; i++) {
            n = snprintf(out + at, max - at, "%s%u", i ? "," : "", (unsigned)s->last_bits[i]);
            if (n < 0 || (size_t)n >= max - at)
                return 0u;
            at += (size_t)n;
        }
        n = snprintf(out + at, max - at, "],\"kind\":\"%s\"},",
                     s->last_kind == B2_MOVE_COLUMN ? "column" : "random");
    }
    if (n < 0 || (size_t)n >= max - at)
        return 0u;
    at += (size_t)n;
    n = snprintf(out + at, max - at, "\"operator_seed\":%lu,\"pair\":%d,", (unsigned long)s->operator_seed, pair);
    if (n < 0 || (size_t)n >= max - at)
        return 0u;
    at += (size_t)n;
    if (holdout >= 0)
        n = snprintf(out + at, max - at, "\"parent_born\":null,\"population\":[");
    else
        n = snprintf(out + at, max - at, "\"parent_born\":%lu,\"population\":[", (unsigned long)s->last_parent_born);
    if (n < 0 || (size_t)n >= max - at)
        return 0u;
    at += (size_t)n;
    for (i = 0; i < B2_MU; i++) {
        n = snprintf(out + at, max - at, "%s{\"born\":%lu,\"fit\":%ld}", i ? "," : "",
                     (unsigned long)s->pop[i].born, (long)s->pop[i].fit);
        if (n < 0 || (size_t)n >= max - at)
            return 0u;
        at += (size_t)n;
    }
    n = snprintf(out + at, max - at, "],\"selected\":%s,\"state_sha256\":\"%s\",\"version\":\"%s\"}",
                 (holdout < 0 && s->last_selected) ? "true" : "false", state, B2_SEARCH_VERSION);
    if (n < 0 || (size_t)n >= max - at)
        return 0u;
    return at + (size_t)n;
}
