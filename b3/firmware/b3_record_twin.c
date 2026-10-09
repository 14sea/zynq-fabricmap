/* b3_record_twin — the host driver that proves the O arm's C side equals the Python reference
 * (b3/host/b3_online_arm.run_online, record_block, ledger_entry, state_sha256). B3 lifecycle 2,
 * image stage 2.
 *
 * Host-only: compiled with the host compiler, never for the board. The harness plays the FABRIC: the
 * twin proposes, the harness computes the readout of the proposed genome and sends it back, and the
 * twin does what the image will do with it — B2's engine observes, the cartographer observes the
 * specimen (moved bits, toggled positions), the online view is rebuilt on a decode, and the commitment,
 * the ledger entry and the record block are rendered. Every command is the whole line; anything else is
 * "ERR ..." and changes nothing.
 *
 *   I <pair> <lseed> <oseed> <budget> <t0> .. <t5>
 *          the O arm of absolute pair <pair> (b3_online_init) from the baseline readout (six
 *          16-hex-digit words), a fresh cartographer -> OK
 *   S      SEARCH <the search text> of the current state (at evaluation 0: the O initializer's state)
 *   V      VIEW <col_keys_n> <sum of all col_n> <v:b,b;v:b...>   the operator's view, in col_keys order
 *   P      PROP <kind> <parent_born> <genomehex> <n> <b1> ... <bn>, or DONE (the budget is spent)
 *   M <t0> .. <t5>   the measured readout of the proposal in flight -> the lines
 *            TEXT <the bytes the commitment hashes>   SEARCH <the search text>   COMMIT <hex>
 *            LEDGER <json>   BLOCK <json>
 *   C      CHAMP <genomehex> (the champion's holdout candidate), or ERR
 *   H <t0> .. <t5>   the champion's measured readout -> BLOCK <holdout json>, COMMIT <hex>
 *   K      probes of b3_record_json's refusals on the current state:
 *            K <search without ledger> <holdout with ledger> <exact buffer> <buffer + 1> <length>
 *              <an eval index that is not the entry's seq>
 *   T <L|B> [<field> <args>] ...
 *          a TAMPERED copy of the last observation's ledger entry, rendered by b3_ledger_json (L) or embedded in
 *          b3_record_json's search block (B) -> T <length> (0 = refused). Fields, applied left to right:
 *            seq | map_version | map_version_after | anomalies | parent_born <u32>;  fitness | kind <i32>;
 *            bits <n> <b1..bn> (n <= 4)   delta <n> <p1..pn> (positions 64k+v, n <= 384)
 *            newly <n> <a1..an> (n <= 292)   carto other (the LEDGER cartographer instead of the O arm's)
 *            nbits | ndelta | nnewly <count>  (the count alone, over an array of EXACTLY its capacity holding
 *                                              0, 1, 2 ... — a count past the capacity must be refused before
 *                                              any element is read; the ASan build holds that)
 *   U <eval_n> <holdout>   b3_record_json's holdout block for these values on the current state -> U <length>
 *   W <eval_n> <holdout>   the same, but handed the last observation's ledger entry -> W <length> (must be 0)
 *   X      a fresh LEDGER cartographer (independent of the O arm's) -> OK
 *   E <seq> <parent_born> <kind> <fitness> <n> <b1..bn> | <m> <k.v ...>
 *          the ledger cartographer observes the specimen -> LEDGER <json> (the entry, map_version before)
 *   Z <arm> <lseed> <oseed> <budget> <evals> <gen> <best> <fit:born:hex> x4
 *          a SYNTHETIC search state beside the ledger cartographer -> TEXT <bytes>, COMMIT <hex>
 *   R <O|Z>   the byte ranges the commitment of the O arm's state (O) or of the last synthetic state (Z) is hashed
 *          in, call for call -> EMIT <n>:<hex> ... (the owner's B-2 ruling of 2026-10-09: the image's compile branch,
 *          `make record-twin-image`, against this emitter branch, range for range)
 *   Q      exit 0
 */
#include "b2_search.h"
#include "b3_carto.h"
#include "b3_online_view.h"
#include "b3_record.h"
#include "p3_derive.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LINE_MAX_BYTES 65536
#define JSON_MAX 65536

static b2_search search, synth;
static b3_carto carto, lcarto, scratch;
static int have_search, have_synth, pair;
static uint16_t delta[B3_CARTO_POSITIONS], newly[B3_CARTO_N];                        /* the O arm's: last_entry points here */
static uint16_t moved[B3_CARTO_N], e_delta[B3_CARTO_POSITIONS], e_newly[B3_CARTO_N];  /* the E command's own */
static char json[JSON_MAX];
static b3_ledger_entry last_entry;
static int have_entry;
static uint16_t t_bits[B2_KMAX], t_delta[B3_CARTO_POSITIONS], t_newly[B3_CARTO_N];   /* exactly their capacities */

static void emit_stdout(void *ctx, const char *bytes, size_t n)
{
    (void)ctx;
    fwrite(bytes, 1, n, stdout);
}

/* One emitted byte range, as the R command lists it: " <n>:<the bytes in hex>". */
static void emit_range(void *ctx, const char *bytes, size_t n)
{
    size_t i;
    (void)ctx;
    printf(" %lu:", (unsigned long)n);
    for (i = 0; i < n; i++)
        printf("%02x", (unsigned)(unsigned char)bytes[i]);
}

#ifdef B3_EMIT_SHA
/* The image's compile branch (`make record-twin-image`: -DB3_EMIT_SHA, linked with --wrap=p3_sha256_update). The
 * renderers call b3_sha_sink directly and it hands each byte range to p3_sha256_update; the wrap sees every range in
 * the order it is hashed and, while `tap` is set, shows it before hashing it. The driver prints the texts this way:
 * what it prints IS what the image's sink hashed. */
static void (*tap)(void *ctx, const char *bytes, size_t n);

void __real_p3_sha256_update(p3_sha256 *c, const uint8_t *data, size_t n);
void __wrap_p3_sha256_update(p3_sha256 *c, const uint8_t *data, size_t n);

void __wrap_p3_sha256_update(p3_sha256 *c, const uint8_t *data, size_t n)
{
    if (tap)
        tap(NULL, (const char *)data, n);
    __real_p3_sha256_update(c, data, n);
}

static void render_commitment(const b2_search *s, const b3_carto *c, void (*to)(void *, const char *, size_t))
{
    p3_sha256 h;
    p3_sha256_init(&h);
    tap = to;
    (void)b3_commitment_render(s, c, &h);
    tap = NULL;
}

static void render_search(const b2_search *s, void (*to)(void *, const char *, size_t))
{
    p3_sha256 h;
    p3_sha256_init(&h);
    tap = to;
    (void)b3_search_state_render(s, &h);
    tap = NULL;
}

/* R: every byte range b3_state_hex itself hashes, call for call. */
static void emitted_ranges(const b2_search *s, const b3_carto *c)
{
    char hex[65];
    tap = emit_range;
    b3_state_hex(s, c, hex);
    tap = NULL;
}
#else
static void render_commitment(const b2_search *s, const b3_carto *c, void (*to)(void *, const char *, size_t))
{
    (void)b3_commitment_render(s, c, to, NULL);
}

static void render_search(const b2_search *s, void (*to)(void *, const char *, size_t))
{
    (void)b3_search_state_render(s, to, NULL);
}

/* R: every byte range the renderers emit, call for call. */
static void emitted_ranges(const b2_search *s, const b3_carto *c)
{
    render_commitment(s, c, emit_range);
}
#endif

static void done(void) { fflush(stdout); }

/* ------------------------------------------------------------------ tokens */
static int skip(const char **p)
{
    if (**p != ' ')
        return -1;
    while (**p == ' ')
        (*p)++;
    return 0;
}

static int parse_u32(const char **p, uint32_t *out)
{
    const char *s = *p;
    unsigned long v;
    char *end;
    if (*s < '0' || *s > '9')
        return -1;
    errno = 0;
    v = strtoul(s, &end, 10);
    if (end == s || errno || v > 0xFFFFFFFFUL)
        return -1;
    *out = (uint32_t)v;
    *p = end;
    return 0;
}

static int parse_i32(const char **p, int32_t *out)
{
    const char *s = *p;
    long v;
    char *end;
    if (!((*s >= '0' && *s <= '9') || (*s == '-' && s[1] >= '0' && s[1] <= '9')))
        return -1;
    errno = 0;
    v = strtol(s, &end, 10);
    if (end == s || errno || v < -2147483647L - 1L || v > 2147483647L)
        return -1;
    *out = (int32_t)v;
    *p = end;
    return 0;
}

static int parse_hex64(const char **p, uint64_t *out)
{
    const char *s = *p;
    uint64_t v = 0;
    int i;
    for (i = 0; i < 16; i++) {
        char ch = s[i];
        int d = (ch >= '0' && ch <= '9') ? ch - '0' : (ch >= 'a' && ch <= 'f') ? ch - 'a' + 10 : -1;
        if (d < 0)
            return -1;
        v = (v << 4) | (uint64_t)d;
    }
    if (s[16] != '\0' && s[16] != ' ')
        return -1;
    *out = v;
    *p = s + 16;
    return 0;
}

static int parse_tables(const char **p, uint64_t t[B2_LUTS])
{
    int k;
    for (k = 0; k < B2_LUTS; k++)
        if (skip(p) < 0 || parse_hex64(p, &t[k]) < 0)
            return -1;
    return 0;
}

static int at_end(const char *p) { return *p == '\0'; }

/* ------------------------------------------------------------------ printing */
static void print_view(const b2_search *s)
{
    int i, j;
    unsigned total = 0;
    for (i = 0; i < B2_VECTORS; i++)
        total += s->col_n[i];
    printf("VIEW %d %u ", s->col_keys_n, total);
    for (i = 0; i < s->col_keys_n; i++) {
        int v = s->col_keys[i];
        printf("%s%d:", i ? ";" : "", v);
        for (j = 0; j < s->col_n[v]; j++)
            printf("%s%u", j ? "," : "", (unsigned)s->col_bits[v][j]);
    }
    fputc('\n', stdout);
}

static void print_commit(const b2_search *s, const b3_carto *c)
{
    char hex[65];
    b3_state_hex(s, c, hex);
    printf("COMMIT %s\n", hex);
}

static void print_text(const b2_search *s, const b3_carto *c)
{
    fputs("TEXT ", stdout);
    render_commitment(s, c, emit_stdout);
    fputc('\n', stdout);
}

static void print_genome(const uint32_t g[B2_GENOME_WORDS])
{
    char hex[B2_GENOME_WORDS * 8 + 1];
    p3_genome_to_hex(g, hex);
    fputs(hex, stdout);
}

/* ------------------------------------------------------------------ commands */
static void cmd_init(const char *p)
{
    uint32_t r, l, o, b;
    uint64_t base[B2_LUTS];
    if (skip(&p) < 0 || parse_u32(&p, &r) < 0 || r > 0x7FFFFFFFu || skip(&p) < 0 || parse_u32(&p, &l) < 0 || skip(&p) < 0 || parse_u32(&p, &o) < 0 || skip(&p) < 0 ||
        parse_u32(&p, &b) < 0 || parse_tables(&p, base) < 0 || !at_end(p)) {
        puts("ERR cannot parse I");
        return;
    }
    b3_online_init(&search, l, o, b, base);
    pair = (int)r;
    b3_carto_init(&carto);
    have_search = 1;
    have_entry = 0;
    puts("OK");
}

static void cmd_propose(void)
{
    uint32_t g[B2_GENOME_WORDS];
    int kind, i;
    if (!have_search) {
        puts("ERR no search");
        return;
    }
    if (!b2_search_next(&search, g, &kind)) {
        puts("DONE");
        return;
    }
    printf("PROP %s %lu ", kind == B2_MOVE_COLUMN ? "column" : "random", (unsigned long)search.pending_parent_born);
    print_genome(g);
    printf(" %d", search.pending_nbits);
    for (i = 0; i < search.pending_nbits; i++)
        printf(" %u", (unsigned)search.pending_bits[i]);
    fputc('\n', stdout);
}

static void cmd_measure(const char *p)
{
    uint64_t t[B2_LUTS];
    uint32_t version_before;
    int nd, n;
    size_t len;
    if (parse_tables(&p, t) < 0 || !at_end(p)) {
        puts("ERR cannot parse M");
        return;
    }
    if (!have_search || !search.pending) {
        puts("ERR no proposal in flight");
        return;
    }
    nd = b3_delta_positions(search.pop[search.pending_parent].tables, t, delta);
    version_before = carto.version;
    b2_search_observe(&search, t);
    n = b3_carto_observe(&carto, &scratch, search.last_bits, search.pending_nbits_last, delta, nd, newly, B3_CARTO_N);
    if (n == B3_CARTO_BAD_CALL) {
        puts("ERR bad call");
        return;
    }
    if (n < 0)
        n = 0;                                    /* a refused specimen: counted, nothing decoded */
    if (n > 0 && b3_online_view_rebuild(&search, &carto) < 0) {
        puts("ERR the view overflowed");
        return;
    }
    last_entry.seq = search.evals;
    last_entry.map_version = version_before;
    last_entry.map_version_after = carto.version;
    last_entry.anomalies = carto.anomalies;
    last_entry.parent_born = search.last_parent_born;
    last_entry.fitness = search.last_fit;
    last_entry.kind = search.last_kind;
    last_entry.bits = search.last_bits;
    last_entry.n_bits = search.pending_nbits_last;
    last_entry.delta = delta;
    last_entry.n_delta = nd;
    last_entry.newly = newly;
    last_entry.n_newly = n;
    last_entry.carto = &carto;
    have_entry = 1;
    print_text(&search, &carto);
    fputs("SEARCH ", stdout);
    render_search(&search, emit_stdout);
    fputc('\n', stdout);
    print_commit(&search, &carto);
    len = b3_ledger_json(&last_entry, json, sizeof(json));
    printf("LEDGER %s\n", len ? json : "");
    len = b3_record_json(&search, &carto, pair, search.evals, -1, &last_entry, json, sizeof(json));
    printf("BLOCK %s\n", len ? json : "");
}

static void cmd_champion(void)
{
    uint32_t g[B2_GENOME_WORDS];
    if (!have_search || !b2_search_champion_next(&search, g)) {
        puts("ERR no champion");
        return;
    }
    fputs("CHAMP ", stdout);
    print_genome(g);
    fputc('\n', stdout);
}

static void cmd_holdout(const char *p)
{
    uint64_t t[B2_LUTS];
    size_t len;
    if (parse_tables(&p, t) < 0 || !at_end(p)) {
        puts("ERR cannot parse H");
        return;
    }
    if (!have_search || !search.champion_pending) {
        puts("ERR no champion in flight");
        return;
    }
    b2_search_champion_observe(&search, t);
    len = b3_record_json(&search, &carto, pair, search.evals, search.champion_holdout, NULL, json, sizeof(json));
    printf("BLOCK %s\n", len ? json : "");
    print_commit(&search, &carto);
}

static void cmd_probe(void)
{
    size_t a, b, n, exact, plus, wrong_seq;
    if (!have_search || !have_entry) {
        puts("ERR no observation");
        return;
    }
    a = b3_record_json(&search, &carto, pair, search.evals, -1, NULL, json, sizeof(json));
    b = b3_record_json(&search, &carto, pair, search.evals, 0, &last_entry, json, sizeof(json));
    n = b3_record_json(&search, &carto, pair, search.evals, -1, &last_entry, json, sizeof(json));
    exact = b3_record_json(&search, &carto, pair, search.evals, -1, &last_entry, json, n);
    plus = b3_record_json(&search, &carto, pair, search.evals, -1, &last_entry, json, n + 1u);
    wrong_seq = b3_record_json(&search, &carto, pair, search.evals + 1u, -1, &last_entry, json, sizeof(json));
    printf("K %lu %lu %lu %lu %lu %lu\n", (unsigned long)a, (unsigned long)b, (unsigned long)exact, (unsigned long)plus,
           (unsigned long)n, (unsigned long)wrong_seq);
}

static int word(const char **p, const char *w)
{
    size_t n = strlen(w);
    if (strncmp(*p, w, n) != 0 || ((*p)[n] != ' ' && (*p)[n] != '\0'))
        return 0;
    *p += n;
    return 1;
}

static int parse_list(const char **p, uint16_t *out, uint32_t cap, int *n_out)
{
    uint32_t n, j, v;
    if (skip(p) < 0 || parse_u32(p, &n) < 0 || n > cap)
        return -1;
    for (j = 0; j < n; j++) {
        if (skip(p) < 0 || parse_u32(p, &v) < 0 || v > 0xFFFFu)
            return -1;
        out[j] = (uint16_t)v;
    }
    *n_out = (int)n;
    return 0;
}

static int parse_count(const char **p, uint16_t *arr, int cap, int *n_out)
{
    int32_t n;
    int j;
    if (skip(p) < 0 || parse_i32(p, &n) < 0)
        return -1;
    for (j = 0; j < cap; j++)
        arr[j] = (uint16_t)j;
    *n_out = (int)n;
    return 0;
}

static void cmd_tamper(const char *p)
{
    b3_ledger_entry e;
    int target;
    size_t len;
    if (!have_search || !have_entry) {
        puts("ERR no observation");
        return;
    }
    if (skip(&p) < 0 || (*p != 'L' && *p != 'B') || (p[1] != ' ' && p[1] != '\0')) {
        puts("ERR cannot parse T target");
        return;
    }
    target = *p++;
    e = last_entry;
    while (*p) {
        int32_t i;
        int bad;
        if (skip(&p) < 0)
            bad = 1;
        else if (word(&p, "seq"))
            bad = skip(&p) < 0 || parse_u32(&p, &e.seq) < 0;
        else if (word(&p, "map_version_after"))
            bad = skip(&p) < 0 || parse_u32(&p, &e.map_version_after) < 0;
        else if (word(&p, "map_version"))
            bad = skip(&p) < 0 || parse_u32(&p, &e.map_version) < 0;
        else if (word(&p, "anomalies"))
            bad = skip(&p) < 0 || parse_u32(&p, &e.anomalies) < 0;
        else if (word(&p, "parent_born"))
            bad = skip(&p) < 0 || parse_u32(&p, &e.parent_born) < 0;
        else if (word(&p, "fitness"))
            bad = skip(&p) < 0 || parse_i32(&p, &e.fitness) < 0;
        else if (word(&p, "kind")) {
            bad = skip(&p) < 0 || parse_i32(&p, &i) < 0;
            e.kind = (int)i;
        } else if (word(&p, "bits")) {
            bad = parse_list(&p, t_bits, B2_KMAX, &e.n_bits) < 0;
            e.bits = t_bits;
        } else if (word(&p, "delta")) {
            bad = parse_list(&p, t_delta, B3_CARTO_POSITIONS, &e.n_delta) < 0;
            e.delta = t_delta;
        } else if (word(&p, "newly")) {
            bad = parse_list(&p, t_newly, B3_CARTO_N, &e.n_newly) < 0;
            e.newly = t_newly;
        } else if (word(&p, "nbits")) {
            bad = parse_count(&p, t_bits, B2_KMAX, &e.n_bits) < 0;
            e.bits = t_bits;
        } else if (word(&p, "ndelta")) {
            bad = parse_count(&p, t_delta, B3_CARTO_POSITIONS, &e.n_delta) < 0;
            e.delta = t_delta;
        } else if (word(&p, "nnewly")) {
            bad = parse_count(&p, t_newly, B3_CARTO_N, &e.n_newly) < 0;
            e.newly = t_newly;
        } else if (word(&p, "carto")) {
            bad = skip(&p) < 0 || !word(&p, "other");
            e.carto = &lcarto;
        } else
            bad = 1;
        if (bad) {
            puts("ERR cannot parse T field");
            return;
        }
    }
    if (target == 'L')
        len = b3_ledger_json(&e, json, sizeof(json));
    else
        len = b3_record_json(&search, &carto, pair, e.seq, -1, &e, json, sizeof(json));
    printf("T %lu\n", (unsigned long)len);
}

static void cmd_holdout_probe(const char *p, int with_ledger)
{
    uint32_t e;
    int32_t h;
    if (skip(&p) < 0 || parse_u32(&p, &e) < 0 || skip(&p) < 0 || parse_i32(&p, &h) < 0 || !at_end(p)) {
        puts("ERR cannot parse U");
        return;
    }
    if (!have_search) {
        puts("ERR no search");
        return;
    }
    if (with_ledger && !have_entry) {
        puts("ERR no observation");
        return;
    }
    printf("%c %lu\n", with_ledger ? 'W' : 'U',
           (unsigned long)b3_record_json(&search, &carto, pair, e, h, with_ledger ? &last_entry : NULL, json, sizeof(json)));
}

static void cmd_ledger(const char *p)
{
    b3_ledger_entry e;
    uint32_t seq, pb, nb, nd, j, v, k;
    int32_t fit;
    int kind, n;
    size_t len;
    if (skip(&p) < 0 || parse_u32(&p, &seq) < 0 || skip(&p) < 0 || parse_u32(&p, &pb) < 0 || skip(&p) < 0) {
        puts("ERR cannot parse E");
        return;
    }
    if (strncmp(p, "random ", 7) == 0)
        kind = B2_MOVE_RANDOM;
    else if (strncmp(p, "column ", 7) == 0)
        kind = B2_MOVE_COLUMN;
    else {
        puts("ERR cannot parse E kind");
        return;
    }
    p += 6;
    if (skip(&p) < 0 || parse_i32(&p, &fit) < 0 || skip(&p) < 0 || parse_u32(&p, &nb) < 0 || nb > B3_CARTO_N) {
        puts("ERR cannot parse E");
        return;
    }
    for (j = 0; j < nb; j++) {
        if (skip(&p) < 0 || parse_u32(&p, &v) < 0 || v > 0xFFFFu) {
            puts("ERR cannot parse E bits");
            return;
        }
        moved[j] = (uint16_t)v;
    }
    if (skip(&p) < 0 || *p != '|') {
        puts("ERR cannot parse E separator");
        return;
    }
    p++;
    if (skip(&p) < 0 || parse_u32(&p, &nd) < 0 || nd > B3_CARTO_POSITIONS) {
        puts("ERR cannot parse E delta");
        return;
    }
    for (j = 0; j < nd; j++) {
        if (skip(&p) < 0 || parse_u32(&p, &k) < 0 || *p != '.' || (p++, parse_u32(&p, &v) < 0) ||
            k >= B3_CARTO_LUTS || v >= B3_CARTO_VECTORS) {
            puts("ERR cannot parse E position");
            return;
        }
        e_delta[j] = (uint16_t)(k * B3_CARTO_VECTORS + v);
    }
    if (!at_end(p)) {
        puts("ERR cannot parse E trailing");
        return;
    }
    e.seq = seq;
    e.map_version = lcarto.version;
    n = b3_carto_observe(&lcarto, &scratch, moved, (int)nb, e_delta, (int)nd, e_newly, B3_CARTO_N);
    if (n == B3_CARTO_BAD_CALL) {
        puts("ERR bad call");
        return;
    }
    e.map_version_after = lcarto.version;
    e.anomalies = lcarto.anomalies;
    e.parent_born = pb;
    e.fitness = fit;
    e.kind = kind;
    e.bits = moved;
    e.n_bits = (int)nb;
    e.delta = e_delta;
    e.n_delta = (int)nd;
    e.newly = e_newly;
    e.n_newly = n < 0 ? 0 : n;
    e.carto = &lcarto;
    len = b3_ledger_json(&e, json, sizeof(json));
    printf("LEDGER %s\n", len ? json : "");
}

static void cmd_synthetic(const char *p)
{
    uint32_t arm, u[5];
    int32_t best;
    int i, j;
    memset(&synth, 0, sizeof(synth));
    have_synth = 0;                               /* until this Z parses whole */
    if (skip(&p) < 0 || parse_u32(&p, &arm) < 0 || arm > 0x7FFFFFFFu) {
        puts("ERR cannot parse Z");
        return;
    }
    for (j = 0; j < 5; j++)
        if (skip(&p) < 0 || parse_u32(&p, &u[j]) < 0) {
            puts("ERR cannot parse Z");
            return;
        }
    if (skip(&p) < 0 || parse_i32(&p, &best) < 0) {
        puts("ERR cannot parse Z");
        return;
    }
    for (i = 0; i < B2_MU; i++) {
        uint32_t born;
        int32_t fit;
        if (skip(&p) < 0 || parse_i32(&p, &fit) < 0 || *p != ':' || (p++, parse_u32(&p, &born) < 0) || *p != ':') {
            puts("ERR cannot parse Z member");
            return;
        }
        p++;
        if (strlen(p) < B2_GENOME_WORDS * 8 || (p[B2_GENOME_WORDS * 8] != ' ' && p[B2_GENOME_WORDS * 8] != '\0')) {
            puts("ERR cannot parse Z genome");
            return;
        }
        {
            char hex[B2_GENOME_WORDS * 8 + 1];
            memcpy(hex, p, B2_GENOME_WORDS * 8);
            hex[B2_GENOME_WORDS * 8] = '\0';
            if (p3_genome_from_hex(hex, synth.pop[i].genome) < 0) {
                puts("ERR cannot parse Z genome");
                return;
            }
        }
        p += B2_GENOME_WORDS * 8;
        synth.pop[i].fit = fit;
        synth.pop[i].born = born;
    }
    if (!at_end(p)) {
        puts("ERR cannot parse Z trailing");
        return;
    }
    synth.arm = (int)arm;
    synth.landscape_seed = u[0];
    synth.operator_seed = u[1];
    synth.budget = u[2];
    synth.evals = u[3];
    synth.generation = u[4];
    synth.best = best;
    have_synth = 1;
    print_text(&synth, &lcarto);
    print_commit(&synth, &lcarto);
}

/* R O | R Z: the byte ranges the commitment of the O arm's state (O) or of the last synthetic state beside the
 * ledger cartographer (Z) is hashed in, call for call -> EMIT <n>:<hex> ... */
static void cmd_ranges(const char *p)
{
    if (strcmp(p, " O") == 0 && have_search) {
        fputs("EMIT", stdout);
        emitted_ranges(&search, &carto);
    } else if (strcmp(p, " Z") == 0 && have_synth) {
        fputs("EMIT", stdout);
        emitted_ranges(&synth, &lcarto);
    } else {
        puts("ERR cannot parse R, or no such state");
        return;
    }
    fputc('\n', stdout);
}

int main(void)
{
    static char line[LINE_MAX_BYTES];
    b3_carto_init(&carto);
    b3_carto_init(&lcarto);
    while (fgets(line, sizeof(line), stdin)) {
        size_t len = strlen(line);
        if (len && line[len - 1] != '\n' && !feof(stdin)) {
            printf("ERR the line exceeds %d bytes\n", LINE_MAX_BYTES - 1);
            done();
            return 3;
        }
        if (len && line[len - 1] == '\n')
            line[--len] = '\0';
        if (strcmp(line, "Q") == 0)
            return 0;
        if (strcmp(line, "V") == 0)
            have_search ? print_view(&search) : (void)puts("ERR no search");
        else if (strcmp(line, "S") == 0) {
            if (have_search) {
                fputs("SEARCH ", stdout);
                render_search(&search, emit_stdout);
                fputc('\n', stdout);
            } else {
                puts("ERR no search");
            }
        } else if (strcmp(line, "P") == 0)
            cmd_propose();
        else if (strcmp(line, "C") == 0)
            cmd_champion();
        else if (strcmp(line, "K") == 0)
            cmd_probe();
        else if (strcmp(line, "X") == 0) {
            b3_carto_init(&lcarto);
            puts("OK");
        } else if (line[0] == 'I' && line[1] == ' ')
            cmd_init(line + 1);
        else if (line[0] == 'M' && line[1] == ' ')
            cmd_measure(line + 1);
        else if (line[0] == 'H' && line[1] == ' ')
            cmd_holdout(line + 1);
        else if (line[0] == 'T' && line[1] == ' ')
            cmd_tamper(line + 1);
        else if (line[0] == 'U' && line[1] == ' ')
            cmd_holdout_probe(line + 1, 0);
        else if (line[0] == 'W' && line[1] == ' ')
            cmd_holdout_probe(line + 1, 1);
        else if (line[0] == 'E' && line[1] == ' ')
            cmd_ledger(line + 1);
        else if (line[0] == 'Z' && line[1] == ' ')
            cmd_synthetic(line + 1);
        else if (line[0] == 'R' && line[1] == ' ')
            cmd_ranges(line + 1);
        else
            puts("ERR unknown command");
        done();
    }
    return 0;
}
