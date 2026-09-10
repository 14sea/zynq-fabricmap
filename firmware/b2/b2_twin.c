/* b2_twin — the host driver that proves b2_search.c equals the Python reference
 * (host/b2_search.py + host/b2_landscape.py) evaluation by evaluation.
 *
 * Host-only: compiled with the host gcc, never for the board. Modes:
 *
 *   rng        < "seed n" lines        -> "<next32 hex> <uniform(n)>" after init
 *   seeds      < "master count"        -> "<landscape> <operator>" per pair
 *   landscape  < "seed"                -> "MASK <6x16hex>" then "TARGET <6x16hex>"
 *   fitness    < "seed <6x16hex>"      -> "F1 <train> <holdout>" for that readout
 *   run        < "arm lseed oseed budget" then, per proposal, the twin prints
 *                 "EVAL <n> <parent_born> <kind> <bits...> | <genome hex>"
 *               and reads one line: six 16-hex tables (the MEASURED readout) or "UNSCORED";
 *               after each observation it prints
 *                 "FIT <fit> <best> <selected> | <pop fit:born ...>"
 *               and at the end
 *                 "CHAMPION <genome hex> <fit> <column_moves>"
 *               then, if a further readout line is given, "HOLDOUT <fit>".
 */
#include "b2_search.h"
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
    unsigned long arm, lseed, oseed, budget;
    int kind, i;
    uint32_t n = 0;

    if (!fgets(line, sizeof(line), stdin) || sscanf(line, "%lu %lu %lu %lu", &arm, &lseed, &oseed, &budget) != 4)
        return 2;
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
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: b2_twin rng|seeds|landscape|fitness|run\n");
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
    fprintf(stderr, "unknown mode %s\n", argv[1]);
    return 2;
}
