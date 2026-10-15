/* b3_wire_twin — the host driver that puts the B3 image's wire bytes in front of the production validator
 * (b3/tests/test_b3_wire_contract.py → b3/host/b3_records). B3 lifecycle 2, image stage 3.
 *
 * Host-only: compiled with the host compiler, never for the board. It links the units the image will link
 * for these bytes — b3_wire.c, b2_search.c (the R and F arms, through B2's own initializer and renderer),
 * b3_online_view.c + b3_carto.c + b3_record.c (the O arm) and p3_derive.c — and the harness plays the
 * FABRIC, as in the record twin: the twin proposes, the harness answers with the readout of the proposed
 * genome, and the twin emits the loop record the image would emit for that evaluation. The evidence
 * members are B2's twin's fixed values (they are not what this stage is about); the search block and the
 * outer arm are the real ones. Every command is the whole line; anything else is "ERR ..." and changes
 * nothing.
 *
 *   IDENT <master> <budget> <pairs_total> <pair_first> <pair_count>   -> IDENT <app_identity 1.6.0>
 *   BASE <seq>                                                         -> REC <a baseline loop record>
 *   RUN <R|F|O> <pair> <lseed> <oseed> <budget> <t0> .. <t5>           -> OK  (one arm of one pair)
 *   P                     -> PROP <genomehex>, or DONE
 *   M <seq> <t0> .. <t5>  -> REC <the search record for the proposal in flight>
 *   C                     -> CHAMP <genomehex>, or ERR
 *   H <seq> <t0> .. <t5>  -> REC <the champion's holdout record>
 *   A <name>              -> A <length>: a baseline-shaped record under the outer arm <name> (0 = refused)
 *   Q                     -> exit 0
 */
#include "b2_search.h"
#include "b3_carto.h"
#include "b3_online_view.h"
#include "b3_record.h"
#include "b3_wire.h"
#include "p3_data.h"
#include "p3_derive.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LINE_MAX_BYTES 4096

static b2_search search;
static b3_carto carto, scratch;
static uint16_t delta[B3_CARTO_POSITIONS], newly[B3_CARTO_N];
static char block[65536], rec[131072];
static int have_run, arm_letter, pair;

static const char *zero_tables[6] = {"0000000000000000", "0000000000000000", "0000000000000000",
                                     "0000000000000000", "0000000000000000", "0000000000000000"};

static int parse_u32(const char **p, uint32_t *out)
{
    const char *s = *p;
    unsigned long v;
    char *end;
    while (*s == ' ')
        s++;
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

static int parse_tables(const char **p, uint64_t t[B2_LUTS])
{
    int k, i;
    for (k = 0; k < B2_LUTS; k++) {
        const char *s = *p;
        uint64_t v = 0;
        if (*s != ' ')
            return -1;
        s++;
        for (i = 0; i < 16; i++) {
            char ch = s[i];
            int d = (ch >= '0' && ch <= '9') ? ch - '0' : (ch >= 'a' && ch <= 'f') ? ch - 'a' + 10 : -1;
            if (d < 0)
                return -1;
            v = (v << 4) | (uint64_t)d;
        }
        t[k] = v;
        *p = s + 16;
    }
    return **p == '\0' ? 0 : -1;
}

static void print_genome(const char *tag, const uint32_t g[B2_GENOME_WORDS])
{
    char hex[B2_GENOME_WORDS * 8 + 1];
    p3_genome_to_hex(g, hex);
    printf("%s %s\n", tag, hex);
}

/* B2's twin's fixed evidence members (tests/test_b2_wire.py): a SCORED, audited candidate */
static void evidence(p3_wire_record_in *r, uint32_t seq)
{
    int i;
    memset(r, 0, sizeof(*r));
    r->seq = seq;
    r->genome = "00000000000000000000000000000000000000000000000000000000000000000000000000000000";
    r->outcome = "SCORED";
    r->audited = 1;
    r->have_sign_reply = 1;
    r->commit = "39fa5c49fb904701ea96159b7220ad83e017dd0cfc4897b7ca4f9b8f7ddbda5e";
    for (i = 0; i < 6; i++)
        r->tables[i] = zero_tables[i];
    r->tag = "88c45cf12e6857e7af54751d700e0f71";
    r->have_oracle = 1;
    r->staged_sha256 = r->commit;
    r->staged_stream_sha256 = "3ec0c49aed63997df3346caf51e92843d08df351b1dc15e215a8f1d82f2d02b9";
    r->readback_sha256 = r->commit;
    r->envelopes_n = 3;
    r->audit_available = 1;
    r->have_arm = 1;
    r->nonce_before = 0x9e3779b97f4a7c15ull;
    r->nonce_after = 0xdc1b77ae0bf34dadull;
    r->status_after = 0xf54u;
    r->key_loaded_observed = 1;
    r->writes_issued = 25;
    r->settle_polls = 16;
    r->settle_polls_max = 1000000u;
    r->settled = 1;
    r->status_first = 0x901u;
    r->have_score = 1;
    r->hw_candidate_commit = r->commit;
    for (i = 0; i < 6; i++) {
        r->readout[i] = zero_tables[i];
        r->scores[i] = 18u;
    }
    r->hb_before = 1;
    r->hb_after = 2;
}

static const char *outer_arm(void)
{
    return arm_letter == 'R' ? B3_WIRE_ARM_RANDOM_SAFE : arm_letter == 'F' ? B3_WIRE_ARM_MAP_GUIDED : B3_WIRE_ARM_ONLINE;
}

static void emit_record(uint32_t seq, const char *search_block, const char *arm)
{
    p3_wire_record_in r;
    evidence(&r, seq);
    r.arm = arm;
    r.search = search_block;
    if (p3_wire_loop_record(&r, rec, sizeof(rec)) == 0u) {
        puts("ERR the record did not render");
        return;
    }
    printf("REC %s\n", rec);
}

static void cmd_ident(const char *p)
{
    static char out[8192];
    p3_wire_identity_in in;
    uint32_t master, budget, total, first, count;
    if (parse_u32(&p, &master) < 0 || parse_u32(&p, &budget) < 0 || parse_u32(&p, &total) < 0 ||
        parse_u32(&p, &first) < 0 || parse_u32(&p, &count) < 0 || *p != '\0') {
        puts("ERR cannot parse IDENT");
        return;
    }
    memset(&in, 0, sizeof(in));
    in.pss_idcode = 0x13722093u;
    in.token = "a13f38b53355fd4c1cac3145244727f8";
    in.carrier_sha256 = "d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f";
    in.nonce_at_start = 0x9e3779b97f4a7c15ull;
    in.status_at_start = 0x900u;
    in.fclk0_hz_decoded = 50000000u;
    in.master_seed = master;
    in.schedule_mode = B2_SEARCH_VERSION;
    in.operator_data_sha256 = B2_MAP_SHA256;
    in.protocol = "rel-v4";
    in.rec_retry_control = 1;
    in.sign_retry_control = 1;
    in.universe_sha256 = B2_UNIVERSE_SHA256;
    in.carrier_variant = 0x42310001u;
    in.search_version = B2_SEARCH_VERSION;
    in.map_sha256 = B2_MAP_SHA256;
    in.fitness_id = B2_FITNESS_ID;
    in.budget_per_arm = budget;
    in.pairs_total = total;
    in.pair_first = first;
    in.pair_count = count;
    in.carto_version = B3_CARTO_VERSION;
    in.arms = B3_WIRE_ARMS;
    in.b1_map_cost = B3_WIRE_B1_MAP_COST;
    if (p3_wire_identity(&in, out, sizeof(out)) == 0u) {
        puts("ERR the identity did not render");
        return;
    }
    printf("IDENT %s\n", out);
}

static void cmd_run(const char *p)
{
    uint32_t r, l, o, b;
    uint64_t base[B2_LUTS];
    char a;
    while (*p == ' ')
        p++;
    a = *p;
    if ((a != 'R' && a != 'F' && a != 'O') || p[1] != ' ') {
        puts("ERR cannot parse RUN arm");
        return;
    }
    p++;
    if (parse_u32(&p, &r) < 0 || r > 0x7FFFFFFFu || parse_u32(&p, &l) < 0 || parse_u32(&p, &o) < 0 ||
        parse_u32(&p, &b) < 0 || parse_tables(&p, base) < 0) {
        puts("ERR cannot parse RUN");
        return;
    }
    if (a == 'O') {
        b3_online_init(&search, l, o, b, base);  /* the O arm: its own initializer, an empty view */
        b3_carto_init(&carto);
    } else {
        b2_search_init(&search, a == 'R' ? B2_ARM_RANDOM_SAFE : B2_ARM_MAP_GUIDED, l, o, b, base);
    }
    arm_letter = a;
    pair = (int)r;
    have_run = 1;
    puts("OK");
}

static void cmd_propose(void)
{
    uint32_t g[B2_GENOME_WORDS];
    int kind;
    if (!have_run) {
        puts("ERR no run");
        return;
    }
    if (!b2_search_next(&search, g, &kind)) {
        puts("DONE");
        return;
    }
    print_genome("PROP", g);
}

static void cmd_measure(const char *p)
{
    uint64_t t[B2_LUTS];
    uint32_t seq, version_before;
    size_t len;
    int nd, n;
    if (parse_u32(&p, &seq) < 0 || parse_tables(&p, t) < 0) {
        puts("ERR cannot parse M");
        return;
    }
    if (!have_run || !search.pending) {
        puts("ERR no proposal in flight");
        return;
    }
    if (arm_letter != 'O') {
        b2_search_observe(&search, t);
        len = b2_search_record_json(&search, pair, arm_letter == 'R' ? "A" : "B", search.evals, -1, block, sizeof(block));
    } else {
        b3_ledger_entry e;
        nd = b3_delta_positions(search.pop[search.pending_parent].tables, t, delta);
        version_before = carto.version;
        b2_search_observe(&search, t);
        n = b3_carto_observe(&carto, &scratch, search.last_bits, search.pending_nbits_last, delta, nd, newly, B3_CARTO_N);
        if (n < 0)
            n = 0;
        if (n > 0 && b3_online_view_rebuild(&search, &carto) < 0) {
            puts("ERR the view overflowed");
            return;
        }
        e.seq = search.evals;
        e.map_version = version_before;
        e.map_version_after = carto.version;
        e.anomalies = carto.anomalies;
        e.parent_born = search.last_parent_born;
        e.fitness = search.last_fit;
        e.kind = search.last_kind;
        e.bits = search.last_bits;
        e.n_bits = search.pending_nbits_last;
        e.delta = delta;
        e.n_delta = nd;
        e.newly = newly;
        e.n_newly = n;
        e.carto = &carto;
        len = b3_record_json(&search, &carto, pair, search.evals, -1, &e, block, sizeof(block));
    }
    if (len == 0u) {
        puts("ERR the search block did not render");
        return;
    }
    emit_record(seq, block, outer_arm());
}

static void cmd_champion(void)
{
    uint32_t g[B2_GENOME_WORDS];
    if (!have_run || !b2_search_champion_next(&search, g)) {
        puts("ERR no champion");
        return;
    }
    print_genome("CHAMP", g);
}

static void cmd_holdout(const char *p)
{
    uint64_t t[B2_LUTS];
    uint32_t seq;
    size_t len;
    if (parse_u32(&p, &seq) < 0 || parse_tables(&p, t) < 0) {
        puts("ERR cannot parse H");
        return;
    }
    if (!have_run || !search.champion_pending) {
        puts("ERR no champion in flight");
        return;
    }
    b2_search_champion_observe(&search, t);
    if (arm_letter != 'O')
        len = b2_search_record_json(&search, pair, arm_letter == 'R' ? "A" : "B", search.evals, search.champion_holdout,
                                    block, sizeof(block));
    else
        len = b3_record_json(&search, &carto, pair, search.evals, search.champion_holdout, NULL, block, sizeof(block));
    if (len == 0u) {
        puts("ERR the holdout block did not render");
        return;
    }
    emit_record(seq, block, outer_arm());
}

static void cmd_arm_probe(const char *name)
{
    p3_wire_record_in r;
    evidence(&r, 1);
    r.arm = name;
    printf("A %lu\n", (unsigned long)p3_wire_loop_record(&r, rec, sizeof(rec)));
}

int main(void)
{
    static char line[LINE_MAX_BYTES];
    uint32_t seq;
    b3_carto_init(&carto);
    while (fgets(line, sizeof(line), stdin)) {
        size_t len = strlen(line);
        const char *p;
        if (len && line[len - 1] != '\n' && !feof(stdin)) {
            printf("ERR the line exceeds %d bytes\n", LINE_MAX_BYTES - 1);
            fflush(stdout);
            return 3;
        }
        if (len && line[len - 1] == '\n')
            line[--len] = '\0';
        if (strcmp(line, "Q") == 0)
            return 0;
        if (strcmp(line, "P") == 0)
            cmd_propose();
        else if (strcmp(line, "C") == 0)
            cmd_champion();
        else if (strncmp(line, "IDENT ", 6) == 0)
            cmd_ident(line + 5);
        else if (strncmp(line, "BASE ", 5) == 0) {
            p = line + 4;
            if (parse_u32(&p, &seq) < 0 || *p != '\0')
                puts("ERR cannot parse BASE");
            else
                emit_record(seq, NULL, NULL);
        } else if (strncmp(line, "RUN ", 4) == 0)
            cmd_run(line + 3);
        else if (line[0] == 'M' && line[1] == ' ')
            cmd_measure(line + 1);
        else if (line[0] == 'H' && line[1] == ' ')
            cmd_holdout(line + 1);
        else if (line[0] == 'A' && line[1] == ' ')
            cmd_arm_probe(line + 2);
        else
            puts("ERR unknown command");
        fflush(stdout);
    }
    return 0;
}
