/* b2_twin — the host driver that proves b2_search.c equals the Python reference
 * (host/b2_search.py + host/b2_landscape.py) evaluation by evaluation.
 *
 * Host-only: compiled with the host gcc, never for the board. Modes:
 *
 *   rng        < "seed n" lines        -> "<next32 hex> <uniform(n)>" after init
 *   seeds      < "master count"        -> "<landscape> <operator>" per pair
 *   landscape  < "seed"                -> "MASK <6x16hex>" then "TARGET <6x16hex>"
 *   fitness    < "seed <6x16hex>"      -> "F1 <train> <holdout>" for that readout
 *   wire                               -> "IDENT <json>" and "REC <json>": the app_identity
 *                                         1.5.0 and loop_record 1.3.0 bytes the image emits,
 *                                         for fixed inputs, so tests/test_b2_wire.py can feed
 *                                         them to the real host validator
 *   run        < "arm lseed oseed budget pair" then, per proposal, the twin prints
 *                 "EVAL <n> <parent_born> <kind> <bits...> | <genome hex>"
 *               and reads one line: six 16-hex tables (the MEASURED readout) or "UNSCORED";
 *               after each observation it prints
 *                 "FIT <fit> <best> <selected> | <pop fit:born ...>"
 *                 "BLOCK <the `search` record block the image writes>"
 *               and at the end
 *                 "CHAMPION <genome hex> <fit> <column_moves>"
 *               then, if a further readout line is given, "HOLDOUT <fit>".
 */
#include "b2_search.h"
#include "b2_wire.h"
#include "p3_data.h"
#include "p3_derive.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int parse_tables(const char *line, uint64_t t[B2_LUTS])
{
    int k;
    const char *p = line;
    for (k = 0; k < B2_LUTS; k++) {
        char *end;
        while (*p == ' ')
            p++;
        t[k] = strtoull(p, &end, 16);
        if (end == p)
            return -1;
        p = end;
    }
    return 0;
}

static void print_tables(const char *tag, const uint64_t t[B2_LUTS])
{
    int k;
    printf("%s", tag);
    for (k = 0; k < B2_LUTS; k++)
        printf(" %016llx", (unsigned long long)t[k]);
    printf("\n");
}

static int mode_rng(void)
{
    char line[256];
    while (fgets(line, sizeof(line), stdin)) {
        unsigned long seed, n;
        b2_rng r;
        if (sscanf(line, "%lu %lu", &seed, &n) != 2)
            continue;
        b2_rng_init(&r, (uint32_t)seed);
        {
            uint32_t a = b2_rng_next32(&r);
            uint32_t u = b2_rng_uniform(&r, (uint32_t)n);
            printf("%08lx %lu\n", (unsigned long)a, (unsigned long)u);
        }
    }
    return 0;
}

static int mode_seeds(void)
{
    char line[256];
    unsigned long master, count;
    static uint32_t out[2 * 64];
    unsigned long i;
    if (!fgets(line, sizeof(line), stdin) || sscanf(line, "%lu %lu", &master, &count) != 2)
        return 2;
    if (count > 64u)
        return 3;
    b2_pair_seeds((uint32_t)master, (int)count, out);
    for (i = 0; i < count; i++)
        printf("%lu %lu\n", (unsigned long)out[2 * i], (unsigned long)out[2 * i + 1]);
    return 0;
}

static int mode_landscape(void)
{
    char line[256];
    unsigned long seed;
    uint64_t masks[B2_LUTS], target[B2_LUTS];
    if (!fgets(line, sizeof(line), stdin) || sscanf(line, "%lu", &seed) != 1)
        return 2;
    b2_universe_mask(masks);
    b2_target((uint32_t)seed, masks, target);
    print_tables("MASK", masks);
    print_tables("TARGET", target);
    return 0;
}

static int mode_fitness(void)
{
    char line[1024];
    while (fgets(line, sizeof(line), stdin)) {
        unsigned long seed;
        uint64_t masks[B2_LUTS], target[B2_LUTS], t[B2_LUTS];
        const char *rest = strchr(line, ' ');
        if (sscanf(line, "%lu", &seed) != 1 || !rest)
            continue;
        b2_universe_mask(masks);
        b2_target((uint32_t)seed, masks, target);
        if (parse_tables(rest, t) != 0)
            return 4;
        printf("F1 %ld %ld\n", (long)b2_f1_train(t, target), (long)b2_f1_holdout(t, target));
        fflush(stdout);
    }
    return 0;
}

static int mode_run(void)
{
    static b2_search s;
    char line[1024];
    char ghex[B2_GENOME_WORDS * 8 + 1];
    uint32_t genome[B2_GENOME_WORDS];
    uint64_t base[B2_LUTS], t[B2_LUTS];
    static char block[4096];
    unsigned long arm, lseed, oseed, budget, pair = 0;
    const char *arm_letter;
    int kind, i;
    uint32_t n = 0;

    if (!fgets(line, sizeof(line), stdin) || sscanf(line, "%lu %lu %lu %lu %lu", &arm, &lseed, &oseed, &budget, &pair) < 4)
        return 2;
    arm_letter = (arm == (unsigned long)B2_ARM_RANDOM_SAFE) ? "A" : "B";
    if (!fgets(line, sizeof(line), stdin) || parse_tables(line, base) != 0)
        return 3;                          /* the measured opening baseline */
    b2_search_init(&s, (int)arm, (uint32_t)lseed, (uint32_t)oseed, (uint32_t)budget, base);
    while (b2_search_next(&s, genome, &kind)) {
        n++;
        p3_genome_to_hex(genome, ghex);
        printf("EVAL %lu %lu %d", (unsigned long)n, (unsigned long)s.pending_parent_born, kind);
        for (i = 0; i < s.pending_nbits; i++)
            printf(" %u", (unsigned)s.pending_bits[i]);
        printf(" | %s\n", ghex);
        fflush(stdout);
        if (!fgets(line, sizeof(line), stdin))
            return 4;
        if (strncmp(line, "UNSCORED", 8) == 0) {
            b2_search_unobserved(&s);
            break;
        }
        if (parse_tables(line, t) != 0)
            return 5;
        b2_search_observe(&s, t);
        printf("FIT %ld %ld %d |", (long)s.last_fit, (long)s.best, s.last_selected);
        for (i = 0; i < B2_MU; i++)
            printf(" %ld:%lu", (long)s.pop[i].fit, (unsigned long)s.pop[i].born);
        printf("\n");
        if (b2_search_record_json(&s, (int)pair, arm_letter, n, -1, block, sizeof(block)) == 0u)
            return 8;
        printf("BLOCK %s\n", block);
        fflush(stdout);
    }
    {
        int32_t fit = -1;
        if (!b2_search_champion(&s, genome, &fit))
            return 6;
        p3_genome_to_hex(genome, ghex);
        printf("CHAMPION %s %ld %lu\n", ghex, (long)fit, (unsigned long)s.column_moves);
        fflush(stdout);
    }
    if (b2_search_champion_next(&s, genome)) {
        if (!fgets(line, sizeof(line), stdin))
            return 0;                      /* the driver may stop before the holdout evaluation */
        if (parse_tables(line, t) != 0)
            return 7;
        b2_search_champion_observe(&s, t);
        printf("HOLDOUT %ld\n", (long)s.champion_holdout);
        if (b2_search_record_json(&s, (int)pair, arm_letter, s.evals, s.champion_holdout, block, sizeof(block)) == 0u)
            return 9;
        printf("BLOCK %s\n", block);
        fflush(stdout);
    }
    return 0;
}

/* the B2 image's ACTUAL serialisation of an app_identity 1.5.0 and a loop_record 1.3.0 with a
 * search block, for fixed inputs (tests/test_b2_wire.py feeds the bytes to the host validator) */
static int mode_wire(void)
{
    static char out[8192], rec[8192], block[4096];
    static b2_search s;
    uint64_t base[B2_LUTS] = {0, 0, 0, 0, 0, 0};
    uint64_t observed[B2_LUTS] = {1, 0, 0, 0, 0, 0};
    p3_wire_identity_in in;
    p3_wire_record_in r;
    static const char *zero_tables[6] = {"0000000000000000", "0000000000000000", "0000000000000000",
                                         "0000000000000000", "0000000000000000", "0000000000000000"};
    uint32_t genome[B2_GENOME_WORDS];
    int i, kind;

    memset(&in, 0, sizeof(in));
    in.pss_idcode = 0x13722093u;
    in.token = "a13f38b53355fd4c1cac3145244727f8";
    in.uboot_epoch = 0;
    in.carrier_sha256 = "d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f";
    in.nonce_at_start = 0x9e3779b97f4a7c15ull;
    in.status_at_start = 0x900u;
    in.fclk0_hz_decoded = 50000000u;
    in.app_epoch = 0;
    in.master_seed = 716169644u;
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
    in.budget_per_arm = 600u;
    in.pairs_total = 9u;
    in.pair_first = 0u;
    in.pair_count = 4u;
    if (p3_wire_identity(&in, out, sizeof(out)) == 0u)
        return 7;
    printf("IDENT %s\n", out);

    b2_search_init(&s, B2_ARM_MAP_GUIDED, 3999265929u, 2551437210u, 4u, base);
    if (!b2_search_next(&s, genome, &kind))
        return 8;
    b2_search_observe(&s, observed);
    if (b2_search_record_json(&s, 0, "B", 1, -1, block, sizeof(block)) == 0u)
        return 9;
    memset(&r, 0, sizeof(r));
    r.seq = 2;
    r.genome = "00000000000000000000000000000000000000000000000000000000000000000000000000000000";
    r.outcome = "SCORED";
    r.audited = 1;
    r.arm = "map_guided";
    r.search = block;
    r.have_sign_reply = 1;
    r.commit = "39fa5c49fb904701ea96159b7220ad83e017dd0cfc4897b7ca4f9b8f7ddbda5e";
    for (i = 0; i < 6; i++)
        r.tables[i] = zero_tables[i];
    r.tag = "88c45cf12e6857e7af54751d700e0f71";
    r.have_oracle = 1;
    r.staged_sha256 = r.commit;
    r.staged_stream_sha256 = "3ec0c49aed63997df3346caf51e92843d08df351b1dc15e215a8f1d82f2d02b9";
    r.readback_sha256 = r.commit;
    r.envelopes_n = 3;
    r.audit_available = 1;
    r.have_arm = 1;
    r.nonce_before = 0x9e3779b97f4a7c15ull;
    r.nonce_after = 0xdc1b77ae0bf34dadull;
    r.status_after = 0xf54u;
    r.key_loaded_observed = 1;
    r.writes_issued = 25;
    r.settle_polls = 16;
    r.settle_polls_max = 1000000u;
    r.settled = 1;
    r.status_first = 0x901u;
    r.have_score = 1;
    r.hw_candidate_commit = r.commit;
    for (i = 0; i < 6; i++) {
        r.readout[i] = zero_tables[i];
        r.scores[i] = 18u;
    }
    r.hb_before = 1;
    r.hb_after = 2;
    if (p3_wire_loop_record(&r, rec, sizeof(rec)) == 0u)
        return 10;
    printf("REC %s\n", rec);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: b2_twin rng|seeds|landscape|fitness|run|wire\n");
        return 2;
    }
    if (strcmp(argv[1], "rng") == 0)
        return mode_rng();
    if (strcmp(argv[1], "seeds") == 0)
        return mode_seeds();
    if (strcmp(argv[1], "landscape") == 0)
        return mode_landscape();
    if (strcmp(argv[1], "fitness") == 0)
        return mode_fitness();
    if (strcmp(argv[1], "run") == 0)
        return mode_run();
    if (strcmp(argv[1], "wire") == 0)
        return mode_wire();
    fprintf(stderr, "unknown mode %s\n", argv[1]);
    return 2;
}
