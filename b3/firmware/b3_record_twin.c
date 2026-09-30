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
 *   X      a fresh LEDGER cartographer (independent of the O arm's) -> OK
 *   E <seq> <parent_born> <kind> <fitness> <n> <b1..bn> | <m> <k.v ...>
 *          the ledger cartographer observes the specimen -> LEDGER <json> (the entry, map_version before)
 *   Z <arm> <lseed> <oseed> <budget> <evals> <gen> <best> <fit:born:hex> x4
 *          a SYNTHETIC search state beside the ledger cartographer -> TEXT <bytes>, COMMIT <hex>
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
static int have_search, pair;
static uint16_t delta[B3_CARTO_POSITIONS], newly[B3_CARTO_N], moved[B3_CARTO_N];
static char json[JSON_MAX];
static b3_ledger_entry last_entry;
static int have_entry;

static void emit_stdout(void *ctx, const char *bytes, size_t n)
{
    (void)ctx;
    fwrite(bytes, 1, n, stdout);
}

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
    b3_commitment_render(s, c, emit_stdout, NULL);
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
    b3_search_state_render(&search, emit_stdout, NULL);
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
    have_entry = 0;
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
        delta[j] = (uint16_t)(k * B3_CARTO_VECTORS + v);
    }
    if (!at_end(p)) {
        puts("ERR cannot parse E trailing");
        return;
    }
    e.seq = seq;
    e.map_version = lcarto.version;
    n = b3_carto_observe(&lcarto, &scratch, moved, (int)nb, delta, (int)nd, newly, B3_CARTO_N);
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
    e.delta = delta;
    e.n_delta = (int)nd;
    e.newly = newly;
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
    print_text(&synth, &lcarto);
    print_commit(&synth, &lcarto);
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
                b3_search_state_render(&search, emit_stdout, NULL);
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
        else if (line[0] == 'E' && line[1] == ' ')
            cmd_ledger(line + 1);
        else if (line[0] == 'Z' && line[1] == ' ')
            cmd_synthetic(line + 1);
        else
            puts("ERR unknown command");
        done();
    }
    return 0;
}
