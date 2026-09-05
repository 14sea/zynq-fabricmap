/* b1_twin — the host driver that proves b1_carto.c equals the Python reference
 * (host/b1_carto.py) probe by probe over simulated fabrics.
 *
 * Host-only: compiled with the host gcc, never for the board. Modes:
 *
 *   rng    < "seed n" lines            -> "<next32 hex> <uniform(n)>" after init (RNG twin)
 *   carto  < "seed budget" then, per proposal the twin prints
 *              "PROBE <kind> <seq> <genome hex>"
 *            and reads one line: six 16-hex tables separated by spaces (the fabric's
 *            readout for that probe), or "UNSCORED" (the probe was not scored);
 *            when the cartographer is done it prints
 *              "MAP <sha256> <rendered json>"
 *            and, for every observation, "REC <seq> <carto record json>" before the next
 *            PROBE — the same block the board puts into the loop record.
 */
#include "b1_carto.h"
#include "b1_orch.h"
#include "b1_wire.h"
#include "p3_derive.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char g_render[20480];
static char g_rec[4096];

static void genome_hex(const uint32_t g[B1_GENOME_WORDS], char out[B1_GENOME_WORDS * 8 + 1])
{
    p3_genome_to_hex(g, out);
}

static int parse_tables(const char *line, uint64_t t[B1_LUTS])
{
    int k;
    const char *p = line;
    for (k = 0; k < B1_LUTS; k++) {
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

static int mode_rng(void)
{
    char line[256];
    while (fgets(line, sizeof(line), stdin)) {
        unsigned long seed, n;
        b1_rng r;
        if (sscanf(line, "%lu %lu", &seed, &n) != 2)
            continue;
        b1_rng_init(&r, (uint32_t)seed);
        {
            uint32_t a = b1_rng_next32(&r);
            uint32_t u = b1_rng_uniform(&r, (uint32_t)n);
            printf("%08lx %lu\n", (unsigned long)a, (unsigned long)u);
        }
    }
    return 0;
}

static int mode_carto(void)
{
    static b1_carto c;
    char line[1024];
    char ghex[B1_GENOME_WORDS * 8 + 1];
    uint32_t genome[B1_GENOME_WORDS];
    unsigned long seed, budget;
    uint32_t seq = 1; /* seq 1 is the opening baseline on the board; probes start at 2 */
    int kind;

    if (!fgets(line, sizeof(line), stdin) || sscanf(line, "%lu %lu", &seed, &budget) != 2)
        return 2;
    b1_carto_init(&c, (uint32_t)seed, (uint32_t)budget);
    b1_carto_bind(&c, "00000000000000000000000000000000", "0000000000000000000000000000000000000000000000000000000000000000", 0u);
    while (b1_carto_next(&c, genome, &kind)) {
        seq++;
        genome_hex(genome, ghex);
        printf("PROBE %d %lu %s\n", kind, (unsigned long)seq, ghex);
        fflush(stdout);
        if (!fgets(line, sizeof(line), stdin))
            return 3;
        if (strncmp(line, "UNSCORED", 8) == 0) {
            b1_carto_unobserved(&c);
            seq--;
            continue;
        }
        {
            uint64_t t[B1_LUTS];
            uint16_t changed[B1_N + 4];
            int n;
            if (parse_tables(line, t) != 0)
                return 4;
            b1_carto_observe(&c, seq, t);
            n = b1_carto_changed(&c, changed, (int)(sizeof(changed) / sizeof(changed[0])));
            if (n > 8)
                n = 8;
            if (b1_carto_render(&c, g_render, sizeof(g_render)) == 0u)
                return 5;
            if (b1_carto_record_json(&c, kind, seq, changed, n, g_rec, sizeof(g_rec)) == 0u)
                return 6;
            printf("REC %lu %s\n", (unsigned long)seq, g_rec);
            fflush(stdout);
        }
    }
    if (b1_carto_render(&c, g_render, sizeof(g_render)) == 0u)
        return 5;
    printf("MAP %s %s\n", c.map_sha256_hex, g_render);
    return 0;
}

/* wire: the B1 image's ACTUAL serialisation of an app_identity 1.4.0 and a loop_record 1.2.0
 * with a carto block, for fixed inputs, so tests/test_b1_wire.py can feed the bytes the
 * board would emit to the instrument's validator. Prints two lines: IDENT <json>, REC <json>. */
static int mode_wire(void)
{
    static char out[8192];
    static char rec_out[8192];
    static b1_carto c;
    static char carto_json[2048];
    static char render[20480];
    p3_wire_identity_in in;
    p3_wire_record_in rec;
    static const char *tables[6] = {"0000000000000000", "0000000000000030", "0000000000000000",
                                    "0000000008000000", "0000000000001000", "0000000000000000"};
    uint16_t changed[2] = {0, 1};
    int i;

    memset(&in, 0, sizeof(in));
    in.pss_idcode = 0x13722093u;
    in.token = "a13f38b53355fd4c1cac3145244727f8";
    in.uboot_epoch = 0;
    in.carrier_sha256 = "956379fa8d23f8a6f1e0c80fe18b8c4aee68e76cc650499911a4bdb7807e610a";
    in.nonce_at_start = 0x9e3779b97f4a7c15ull;
    in.status_at_start = 0x900u;
    in.fclk0_hz_decoded = 50000000u;
    in.app_epoch = 0;
    in.master_seed = 1123460948u;
    in.schedule_mode = "carto-v1";
    in.operator_data_sha256 = "895baf85ed31df9beae28a533646182ffb8d0e0735c9849ede9641af81ee7458";
    in.protocol = "rel-v4";
    in.rec_retry_control = 1;
    in.sign_retry_control = 1;
    in.carto_version = B1_CARTO_VERSION;
    in.universe_sha256 = "895baf85ed31df9beae28a533646182ffb8d0e0735c9849ede9641af81ee7458";
    in.probe_budget = 333u;
    in.carrier_variant = 0x42310001u;
    if (p3_wire_identity(&in, out, sizeof(out)) == 0u)
        return 7;
    printf("IDENT %s\n", out);

    b1_carto_init(&c, 1123460948u, 333u);
    b1_carto_bind(&c, "a13f38b53355fd4c1cac3145244727f8", "895baf85ed31df9beae28a533646182ffb8d0e0735c9849ede9641af81ee7458", 0x12345678u);
    if (b1_carto_render(&c, render, sizeof(render)) == 0u)
        return 8;
    if (b1_carto_record_json(&c, B1_PH_CODE, 2, changed, 2, carto_json, sizeof(carto_json)) == 0u)
        return 9;
    memset(&rec, 0, sizeof(rec));
    rec.seq = 2;
    rec.genome = "00000000000000000000000000000000000000000000000000000000000000000000000000000000";
    rec.outcome = "SCORED";
    rec.audited = 1;
    rec.arm = NULL;
    rec.carto = carto_json;
    rec.have_sign_reply = 1;
    rec.commit = "39fa5c49fb904701ea96159b7220ad83e017dd0cfc4897b7ca4f9b8f7ddbda5e";
    for (i = 0; i < 6; i++) rec.tables[i] = tables[i];
    rec.tag = "88c45cf12e6857e7af54751d700e0f71";
    rec.have_oracle = 1;
    rec.staged_sha256 = "39fa5c49fb904701ea96159b7220ad83e017dd0cfc4897b7ca4f9b8f7ddbda5e";
    rec.staged_stream_sha256 = "3ec0c49aed63997df3346caf51e92843d08df351b1dc15e215a8f1d82f2d02b9";
    rec.readback_sha256 = "39fa5c49fb904701ea96159b7220ad83e017dd0cfc4897b7ca4f9b8f7ddbda5e";
    rec.envelopes_n = 3;
    rec.audit_available = 1;
    rec.have_arm = 1;
    rec.nonce_before = 0x9e3779b97f4a7c15ull; rec.nonce_after = 0xdc1b77ae0bf34dadull;   /* one xorshift64 step */
    rec.status_after = 0xf54u; rec.fault_after = 0; rec.key_loaded_observed = 1;
    rec.writes_issued = 25; rec.settle_polls = 16; rec.settle_polls_max = 1000000u; rec.settled = 1; rec.status_first = 0x901u;
    rec.have_score = 1;
    rec.hw_candidate_commit = "39fa5c49fb904701ea96159b7220ad83e017dd0cfc4897b7ca4f9b8f7ddbda5e";
    for (i = 0; i < 6; i++) { rec.readout[i] = tables[i]; rec.scores[i] = 18u; }
    rec.hb_before = 1; rec.hb_after = 2;
    if (p3_wire_loop_record(&rec, rec_out, sizeof(rec_out)) == 0u)
        return 10;
    printf("REC %s\n", rec_out);
    return 0;
}

/* session: the orchestrator exactly as b1_app.c main drives it — opening baseline, probes,
 * closing baseline — printing "CAND <is_baseline> <kind> <seq> <genome hex>" per candidate,
 * reading the fabric's readout (six 16-hex tables) or "UNSCORED", and "REC <seq> <carto>" per
 * scored record; then "MAP <sha256> <rendered json>". The twin's output is what the board's
 * records must equal (tests/test_b1_session.py). */
static int mode_session(void)
{
    static b1_orch o;
    char line[1024];
    char ghex[B1_GENOME_WORDS * 8 + 1];
    uint32_t genome[B1_GENOME_WORDS];
    unsigned long seed, budget, image_lo32;
    char token[64], universe[128];
    uint32_t seq = 0;
    int is_baseline, kind;

    /* "seed budget token universe image_lo32(hex)" */
    if (!fgets(line, sizeof(line), stdin) || sscanf(line, "%lu %lu %63s %127s %lx", &seed, &budget, token, universe, &image_lo32) != 5)
        return 2;
    b1_orch_init(&o, (uint32_t)seed, (uint32_t)budget, token, universe, (uint32_t)image_lo32);
    while (b1_orch_next(&o, genome, &is_baseline, &kind)) {
        seq++;
        genome_hex(genome, ghex);
        printf("CAND %d %d %lu %s\n", is_baseline, kind, (unsigned long)seq, ghex);
        fflush(stdout);
        if (!fgets(line, sizeof(line), stdin))
            return 3;
        if (strncmp(line, "UNSCORED", 8) == 0) {
            /* as b1_app.c main: a candidate that was not SCORED ends the epoch — no re-issue,
             * no closing baseline; the map is whatever was learned before it */
            b1_orch_unobserved(&o);
            break;
        }
        {
            uint64_t t[B1_LUTS];
            if (parse_tables(line, t) != 0)
                return 4;
            b1_orch_observe(&o, seq, t);
            if (b1_orch_record_block(&o, seq, g_render, sizeof(g_render), g_rec, sizeof(g_rec)) == 0u)
                return 6;
            printf("REC %lu %s\n", (unsigned long)seq, g_rec);
            fflush(stdout);
        }
    }
    if (b1_carto_render(&o.carto, g_render, sizeof(g_render)) == 0u)
        return 5;
    printf("MAP %s %s\n", o.carto.map_sha256_hex, g_render);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: b1_twin rng|carto\n");
        return 2;
    }
    if (strcmp(argv[1], "rng") == 0)
        return mode_rng();
    if (strcmp(argv[1], "carto") == 0)
        return mode_carto();
    if (strcmp(argv[1], "wire") == 0)
        return mode_wire();
    if (strcmp(argv[1], "session") == 0)
        return mode_session();
    fprintf(stderr, "unknown mode %s\n", argv[1]);
    return 2;
}
