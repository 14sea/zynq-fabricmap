/* b3_record — the O arm's commitment, ledger entry and record block. See b3_record.h. */
#include "b3_record.h"
#include "p3_derive.h"
#include "p3_data.h"

#include <string.h>

/* ------------------------------------------------------------------ integers, without stdio */
/* Decimal digits of v into buf (at least 11 bytes), no NUL; returns the length. */
static size_t fmt_u32(uint32_t v, char *buf)
{
    char rev[10];
    size_t n = 0, i;
    do {
        rev[n++] = (char)('0' + (int)(v % 10u));
        v /= 10u;
    } while (v != 0u);
    for (i = 0; i < n; i++)
        buf[i] = rev[n - 1 - i];
    return n;
}

static size_t fmt_i32(int32_t v, char *buf)
{
    if (v < 0) {
        buf[0] = '-';
        return 1u + fmt_u32((uint32_t)0u - (uint32_t)v, buf + 1);
    }
    return fmt_u32((uint32_t)v, buf);
}

/* ------------------------------------------------------------------ the commitment text */
typedef struct {
#ifndef B3_EMIT_SHA
    b3_emit emit;
#endif
    void *ctx;
    size_t n;
} emitter;

static void em_bytes(emitter *e, const char *b, size_t n)
{
#ifdef B3_EMIT_SHA
    b3_sha_sink(e->ctx, b, n);                   /* the image: a direct call, no emitter pointer (b3_carto.h) */
#else
    e->emit(e->ctx, b, n);
#endif
    e->n += n;
}

static void em_str(emitter *e, const char *s) { em_bytes(e, s, strlen(s)); }

static void em_u32(emitter *e, uint32_t v)
{
    char buf[12];
    em_bytes(e, buf, fmt_u32(v, buf));
}

static void em_i32(emitter *e, int32_t v)
{
    char buf[12];
    em_bytes(e, buf, fmt_i32(v, buf));
}

static void search_render(const b2_search *s, emitter *e)
{
    char ghex[B2_GENOME_WORDS * 8 + 1];
    int i;
    em_str(e, B2_SEARCH_VERSION);                /* "%s|%d|%lu|%lu|%lu|%lu|%lu|%ld|" — b2_search_state_hex */
    em_str(e, "|");
    em_i32(e, (int32_t)s->arm);
    em_str(e, "|");
    em_u32(e, s->landscape_seed);
    em_str(e, "|");
    em_u32(e, s->operator_seed);
    em_str(e, "|");
    em_u32(e, s->budget);
    em_str(e, "|");
    em_u32(e, s->evals);
    em_str(e, "|");
    em_u32(e, s->generation);
    em_str(e, "|");
    em_i32(e, s->best);
    em_str(e, "|");
    for (i = 0; i < B2_MU; i++) {                /* "%ld:%lu:%s;" per member */
        p3_genome_to_hex(s->pop[i].genome, ghex);
        em_i32(e, s->pop[i].fit);
        em_str(e, ":");
        em_u32(e, s->pop[i].born);
        em_str(e, ":");
        em_bytes(e, ghex, B2_GENOME_WORDS * 8);
        em_str(e, ";");
    }
}

#ifdef B3_EMIT_SHA
size_t b3_search_state_render(const b2_search *s, void *ctx)
#else
size_t b3_search_state_render(const b2_search *s, b3_emit emit, void *ctx)
#endif
{
    emitter e;
#ifndef B3_EMIT_SHA
    e.emit = emit;
#endif
    e.ctx = ctx;
    e.n = 0u;
    search_render(s, &e);
    return e.n;
}

#ifdef B3_EMIT_SHA
size_t b3_commitment_render(const b2_search *s, const b3_carto *c, void *ctx)
#else
size_t b3_commitment_render(const b2_search *s, const b3_carto *c, b3_emit emit, void *ctx)
#endif
{
    emitter e;
#ifndef B3_EMIT_SHA
    e.emit = emit;
#endif
    e.ctx = ctx;
    e.n = 0u;
    search_render(s, &e);
    em_str(&e, "|");
#ifdef B3_EMIT_SHA
    e.n += b3_carto_state_render(c, ctx);
#else
    e.n += b3_carto_state_render(c, emit, ctx);
#endif
    return e.n;
}

void b3_sha_sink(void *ctx, const char *bytes, size_t n)
{
    p3_sha256_update((p3_sha256 *)ctx, (const uint8_t *)bytes, n);
}

void b3_state_hex(const b2_search *s, const b3_carto *c, char out[65])
{
    p3_sha256 h;
    uint8_t digest[32];
    p3_sha256_init(&h);
#ifdef B3_EMIT_SHA
    (void)b3_commitment_render(s, c, &h);
#else
    (void)b3_commitment_render(s, c, b3_sha_sink, &h);
#endif
    p3_sha256_final(&h, digest);
    p3_hex(digest, 32u, out);
}

int b3_delta_positions(const uint64_t parent[B2_LUTS], const uint64_t child[B2_LUTS], uint16_t *out)
{
    int n = 0, k, v;
    for (k = 0; k < B2_LUTS; k++) {
        uint64_t d = parent[k] ^ child[k];
        for (v = 0; v < B2_VECTORS; v++)
            if ((d >> v) & 1ull)
                out[n++] = (uint16_t)(k * B2_VECTORS + v);
    }
    return n;
}

/* ------------------------------------------------------------------ JSON into a caller's buffer */
typedef struct {
    char *out;
    size_t max, at;
    int ok;
} jw;

static void jw_bytes(jw *w, const char *b, size_t n)
{
    if (!w->ok)
        return;
    if (n >= w->max - w->at) {                   /* keep one byte for the NUL */
        w->ok = 0;
        return;
    }
    memcpy(w->out + w->at, b, n);
    w->at += n;
}

static void jw_str(jw *w, const char *s) { jw_bytes(w, s, strlen(s)); }

static void jw_u32(jw *w, uint32_t v)
{
    char buf[12];
    jw_bytes(w, buf, fmt_u32(v, buf));
}

static void jw_i32(jw *w, int32_t v)
{
    char buf[12];
    jw_bytes(w, buf, fmt_i32(v, buf));
}

static const char *kind_name(int kind) { return kind == B2_MOVE_COLUMN ? "column" : "random"; }

/* The specimen_ledger 1.1.0 entry schema (b3/schemas/specimen_ledger.schema.json), fail-closed, every count
 * bounded BEFORE any array is read: seq >= 1; fitness in 0 .. B2_TRAIN_COUNT (F1); a known move kind; an
 * intervention of 1 .. B2_KMAX addresses, each < B3_CARTO_N, strictly ascending (unique, as the move produces
 * it); a behaviour delta of at most B3_CARTO_POSITIONS positions, each valid, strictly ascending (unique, in
 * positions_of order); at most B3_CARTO_N newly-decoded addresses, each in range, unique and decoded by
 * `carto`; and the cartographer's version rule — the version after is the version before plus one exactly
 * when the specimen decoded something, else unchanged. */
static int ledger_valid(const b3_ledger_entry *e)
{
    uint64_t seen[(B3_CARTO_N + 63) / 64];
    int i;
    if (e->n_bits < 1 || e->n_bits > B2_KMAX || e->n_delta < 0 || e->n_delta > B3_CARTO_POSITIONS ||
        e->n_newly < 0 || e->n_newly > B3_CARTO_N)
        return 0;
    if (!e->bits || (e->n_delta && !e->delta) || (e->n_newly && (!e->newly || !e->carto)))
        return 0;
    if (e->seq < 1u || e->fitness < 0 || e->fitness > B2_TRAIN_COUNT)
        return 0;
    if (e->kind != B2_MOVE_RANDOM && e->kind != B2_MOVE_COLUMN)
        return 0;
    if (e->map_version_after != e->map_version + (e->n_newly > 0 ? 1u : 0u))
        return 0;
    for (i = 0; i < e->n_bits; i++)
        if (e->bits[i] >= B3_CARTO_N || (i && e->bits[i] <= e->bits[i - 1]))
            return 0;
    for (i = 0; i < e->n_delta; i++)
        if (e->delta[i] >= B3_CARTO_POSITIONS || (i && e->delta[i] <= e->delta[i - 1]))
            return 0;
    memset(seen, 0, sizeof(seen));
    for (i = 0; i < e->n_newly; i++) {
        uint16_t a = e->newly[i];
        if (a >= B3_CARTO_N || ((seen[a / 64] >> (a % 64)) & 1ull) ||
            b3_carto_decoded_position(e->carto, a) == B3_CARTO_NO_POSITION)
            return 0;
        seen[a / 64] |= 1ull << (a % 64);
    }
    return 1;
}

/* A search record's entry must BE the observation just made: every field it shares with the search state
 * and with this cartographer is bound to them (the owner's P2 on 08030dd). */
static int ledger_bound(const b2_search *s, const b3_carto *c, uint32_t eval_n, const b3_ledger_entry *e)
{
    int i;
    if (!ledger_valid(e))
        return 0;
    if (s->pending || s->champion_pending || s->champion_done || s->evals < 1u)
        return 0;                                /* no observation just made (or the holdout already closed the arm) */
    if (e->seq != eval_n || eval_n != s->evals || e->parent_born != s->last_parent_born || e->kind != s->last_kind ||
        e->fitness != s->last_fit || e->n_bits != s->pending_nbits_last)
        return 0;
    for (i = 0; i < e->n_bits; i++)
        if (e->bits[i] != s->last_bits[i])
            return 0;
    if (e->carto != c || e->map_version_after != c->version || e->anomalies != c->anomalies)
        return 0;
    return 1;
}

/* sorted keys: anomalies < behaviour_delta < confidence < decoded < fitness < intervention < map_version <
 * map_version_after < move_kind < parent_born < seq */
static void ledger_write(jw *w, const b3_ledger_entry *e)
{
    int i;
    jw_str(w, "{\"anomalies\":");
    jw_u32(w, e->anomalies);
    jw_str(w, ",\"behaviour_delta\":[");
    for (i = 0; i < e->n_delta; i++) {
        jw_str(w, i ? ",[" : "[");
        jw_u32(w, (uint32_t)(e->delta[i] / B3_CARTO_VECTORS));
        jw_str(w, ",");
        jw_u32(w, (uint32_t)(e->delta[i] % B3_CARTO_VECTORS));
        jw_str(w, "]");
    }
    jw_str(w, "],\"confidence\":");
    jw_str(w, e->n_bits == 1 ? "2" : "1");
    jw_str(w, ",\"decoded\":[");
    for (i = 0; i < e->n_newly; i++) {
        int pos = b3_carto_decoded_position(e->carto, e->newly[i]);
        jw_str(w, i ? ",[" : "[");
        jw_u32(w, e->newly[i]);
        jw_str(w, ",");
        jw_u32(w, (uint32_t)(pos / B3_CARTO_VECTORS));
        jw_str(w, ",");
        jw_u32(w, (uint32_t)(pos % B3_CARTO_VECTORS));
        jw_str(w, "]");
    }
    jw_str(w, "],\"fitness\":");
    jw_i32(w, e->fitness);
    jw_str(w, ",\"intervention\":[");
    for (i = 0; i < e->n_bits; i++) {
        if (i)
            jw_str(w, ",");
        jw_u32(w, e->bits[i]);
    }
    jw_str(w, "],\"map_version\":");
    jw_u32(w, e->map_version);
    jw_str(w, ",\"map_version_after\":");
    jw_u32(w, e->map_version_after);
    jw_str(w, ",\"move_kind\":\"");
    jw_str(w, kind_name(e->kind));
    jw_str(w, "\",\"parent_born\":");
    jw_u32(w, e->parent_born);
    jw_str(w, ",\"seq\":");
    jw_u32(w, e->seq);
    jw_str(w, "}");
}

static size_t jw_finish(jw *w)
{
    if (!w->ok)
        return 0u;
    w->out[w->at] = '\0';
    return w->at;
}

size_t b3_ledger_json(const b3_ledger_entry *e, char *out, size_t max)
{
    jw w;
    if (!e || !out || max == 0u || !ledger_valid(e))
        return 0u;
    w.out = out;
    w.max = max;
    w.at = 0u;
    w.ok = 1;
    ledger_write(&w, e);
    return jw_finish(&w);
}

/* sorted keys: arm < best < column_moves < eval < fitness < generation < holdout < landscape_seed <
 * ledger < move < operator_seed < pair < parent_born < population < selected < state_sha256 < version */
size_t b3_record_json(const b2_search *s, const b3_carto *c, int pair, uint32_t eval_n, int32_t holdout,
                      const b3_ledger_entry *ledger, char *out, size_t max)
{
    char state[65];
    jw w;
    int i, search = holdout < 0;
    if (!s || !c || !out || max == 0u || pair < 0)
        return 0u;
    if (search ? (!ledger || !ledger_bound(s, c, eval_n, ledger)) : ledger != NULL)
        return 0u;                               /* a search record has exactly one ledger entry, bound; a holdout record none */
    if (!search && (!s->champion_done || s->champion_pending || s->pending || eval_n != s->evals ||
                    holdout != s->champion_holdout))
        return 0u;                               /* the holdout record is the champion's evaluation just made */
    b3_state_hex(s, c, state);
    w.out = out;
    w.max = max;
    w.at = 0u;
    w.ok = 1;
    jw_str(&w, "{\"arm\":\"O\",\"best\":");
    jw_i32(&w, s->best);
    jw_str(&w, ",\"column_moves\":");
    jw_u32(&w, s->column_moves);
    jw_str(&w, ",\"eval\":");
    jw_u32(&w, eval_n);
    if (search) {
        jw_str(&w, ",\"fitness\":");
        jw_i32(&w, s->last_fit);
    } else {
        jw_str(&w, ",\"fitness\":null");
    }
    jw_str(&w, ",\"generation\":");
    jw_u32(&w, s->generation);
    jw_str(&w, ",\"holdout\":");
    if (search)
        jw_str(&w, "null");
    else
        jw_i32(&w, holdout);
    jw_str(&w, ",\"landscape_seed\":");
    jw_u32(&w, s->landscape_seed);
    if (search) {
        jw_str(&w, ",\"ledger\":");
        ledger_write(&w, ledger);
        jw_str(&w, ",\"move\":{\"bits\":[");
        for (i = 0; i < s->pending_nbits_last; i++) {
            if (i)
                jw_str(&w, ",");
            jw_u32(&w, s->last_bits[i]);
        }
        jw_str(&w, "],\"kind\":\"");
        jw_str(&w, kind_name(s->last_kind));
        jw_str(&w, "\"}");
    } else {
        jw_str(&w, ",\"move\":null");
    }
    jw_str(&w, ",\"operator_seed\":");
    jw_u32(&w, s->operator_seed);
    jw_str(&w, ",\"pair\":");
    jw_u32(&w, (uint32_t)pair);
    jw_str(&w, ",\"parent_born\":");
    if (search)
        jw_u32(&w, s->last_parent_born);
    else
        jw_str(&w, "null");
    jw_str(&w, ",\"population\":[");
    for (i = 0; i < B2_MU; i++) {
        jw_str(&w, i ? ",{\"born\":" : "{\"born\":");
        jw_u32(&w, s->pop[i].born);
        jw_str(&w, ",\"fit\":");
        jw_i32(&w, s->pop[i].fit);
        jw_str(&w, "}");
    }
    jw_str(&w, "],\"selected\":");
    jw_str(&w, (search && s->last_selected) ? "true" : "false");
    jw_str(&w, ",\"state_sha256\":\"");
    jw_bytes(&w, state, 64u);
    jw_str(&w, "\",\"version\":\"" B2_SEARCH_VERSION "\"}");
    return jw_finish(&w);
}
