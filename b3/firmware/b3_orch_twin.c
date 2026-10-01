/* b3_orch_twin — the host driver that proves b3_orch.c drives the session b3/host/b3_session.run_context
 * describes, candidate by candidate, and reproduces the formal B3 seed rule. B3 lifecycle 2, image stage 4.
 *
 * Host-only: compiled with the host compiler, never for the board, and LINKED WITH
 * -Wl,--wrap=b2_search_init -Wl,--wrap=b3_online_init: every call the orchestrator makes to either initializer
 * passes through the wrappers below, which log (initializer, arm, landscape seed) and call the real one — the
 * ACTUAL path, not a reading of the source, is what b3/tests/test_b3_orch_twin.py holds (R and F through
 * b2_search_init, O through b3_online_init, never b2_search_init). The harness plays the FABRIC. Commands, one
 * per line, the whole line:
 *
 *   SEEDS <master> <count> [<extra> ...]   -> SEEDS <l0> <o0> ... : b3_pair_seeds, ANY master (the helper entry)
 *   PROFILE <master> <budget> <total>      -> PROFILE <profile> [<l0> <o0> ...] : b3_profile_seeds
 *   SLICE <flags>                          -> SLICE <total> <first> <count>, or SLICE REFUSED
 *   SESSION <master> <budget> <total> <first> <count>
 *       -> REFUSED (b3_orch_init said no: nothing is proposed), or per candidate
 *            CAND <is_baseline> <pair> <arm|-> <holdout> <seq> <eval> <view> | <genomehex>
 *          (<view> = "<col_keys_n>,<sum of col_n>" of the O arm's view as the proposal was drawn, "-" otherwise)
 *          and reads ONE line: the measured readout (six 16-hex words) or UNSCORED; after a scored non-baseline
 *          candidate it prints BLOCK <the search block>; at the end
 *            END <records> <complete>
 *            CARTO <the O cartographer's state text>
 *            INITS <b2|online>:<arm>:<landscape seed> ...   (every initializer call, in order)
 *   SESSIONF <flags> <master> <budget>     -> the same, the slice decoded from the page's flags first
 *   Q                                       -> exit 0
 */
#include "b2_search.h"
#include "b3_carto.h"
#include "b3_online_view.h"
#include "b3_orch.h"
#include "p3_derive.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LINE_MAX_BYTES 4096
#define MAX_INITS 256

static b3_orch orch;
static char block[65536];
static char inits[MAX_INITS][32];
static int n_inits;

/* ------------------------------------------------------------------ the initializer wrappers (--wrap) */
void __real_b2_search_init(b2_search *s, int arm, uint32_t landscape_seed, uint32_t operator_seed, uint32_t budget,
                           const uint64_t base[B2_LUTS]);
void __wrap_b2_search_init(b2_search *s, int arm, uint32_t landscape_seed, uint32_t operator_seed, uint32_t budget,
                           const uint64_t base[B2_LUTS]);
void __real_b3_online_init(b2_search *s, uint32_t landscape_seed, uint32_t operator_seed, uint32_t budget,
                           const uint64_t base[B2_LUTS]);
void __wrap_b3_online_init(b2_search *s, uint32_t landscape_seed, uint32_t operator_seed, uint32_t budget,
                           const uint64_t base[B2_LUTS]);

void __wrap_b2_search_init(b2_search *s, int arm, uint32_t landscape_seed, uint32_t operator_seed, uint32_t budget,
                           const uint64_t base[B2_LUTS])
{
    if (n_inits < MAX_INITS)
        snprintf(inits[n_inits++], sizeof(inits[0]), "b2:%d:%lu", arm, (unsigned long)landscape_seed);
    __real_b2_search_init(s, arm, landscape_seed, operator_seed, budget, base);
}

void __wrap_b3_online_init(b2_search *s, uint32_t landscape_seed, uint32_t operator_seed, uint32_t budget,
                           const uint64_t base[B2_LUTS])
{
    if (n_inits < MAX_INITS)
        snprintf(inits[n_inits++], sizeof(inits[0]), "online:%d:%lu", B3_ARM_ONLINE, (unsigned long)landscape_seed);
    __real_b3_online_init(s, landscape_seed, operator_seed, budget, base);
}

/* ------------------------------------------------------------------ parsing */
static int parse_u32(const char **p, uint32_t *out)
{
    const char *s = *p;
    unsigned long v;
    char *end;
    if (*s != ' ')
        return -1;
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

static int parse_tables(const char *s, uint64_t t[B2_LUTS])
{
    int k, i;
    for (k = 0; k < B2_LUTS; k++) {
        uint64_t v = 0;
        if (k > 0) {
            if (*s != ' ')
                return -1;
            s++;
        }
        for (i = 0; i < 16; i++) {
            char ch = s[i];
            int d = (ch >= '0' && ch <= '9') ? ch - '0' : (ch >= 'a' && ch <= 'f') ? ch - 'a' + 10 : -1;
            if (d < 0)
                return -1;
            v = (v << 4) | (uint64_t)d;
        }
        t[k] = v;
        s += 16;
    }
    return *s == '\0' ? 0 : -1;
}

static int read_line(char *line, size_t max)
{
    size_t len;
    if (!fgets(line, (int)max, stdin))
        return -1;
    len = strlen(line);
    if (len && line[len - 1] == '\n')
        line[--len] = '\0';
    return 0;
}

/* ------------------------------------------------------------------ commands */
static void cmd_seeds(const char *p)
{
    static uint32_t extra[512], out[2 * B3_MAX_PAIRS];
    uint32_t master, count;
    int n_extra = 0, i;
    if (parse_u32(&p, &master) < 0 || parse_u32(&p, &count) < 0 || count < 1 || count > B3_MAX_PAIRS) {
        puts("ERR cannot parse SEEDS");
        return;
    }
    while (*p) {
        if (n_extra >= 512 || parse_u32(&p, &extra[n_extra]) < 0) {
            puts("ERR cannot parse SEEDS extra");
            return;
        }
        n_extra++;
    }
    if (b3_pair_seeds(master, (int)count, n_extra ? extra : NULL, n_extra, out) != 0) {
        puts("ERR refused");
        return;
    }
    fputs("SEEDS", stdout);
    for (i = 0; i < 2 * (int)count; i++)
        printf(" %lu", (unsigned long)out[i]);
    fputc('\n', stdout);
}

static void cmd_profile(const char *p)
{
    static uint32_t out[2 * B3_MAX_PAIRS];
    uint32_t master, budget, total;
    int prof, i;
    if (parse_u32(&p, &master) < 0 || parse_u32(&p, &budget) < 0 || parse_u32(&p, &total) < 0 || *p != '\0' ||
        total > B3_MAX_PAIRS) {
        puts("ERR cannot parse PROFILE");
        return;
    }
    prof = b3_profile_seeds(master, budget, (int)total, out);
    printf("PROFILE %d", prof);
    if (prof != B3_PROFILE_NONE)
        for (i = 0; i < 2 * (int)total; i++)
            printf(" %lu", (unsigned long)out[i]);
    fputc('\n', stdout);
}

static void cmd_slice(const char *p)
{
    uint32_t flags;
    int total, first, count;
    if (parse_u32(&p, &flags) < 0 || *p != '\0') {
        puts("ERR cannot parse SLICE");
        return;
    }
    if (b3_page_slice(flags, &total, &first, &count) != 0)
        puts("SLICE REFUSED");
    else
        printf("SLICE %d %d %d\n", total, first, count);
}

static void emit_stdout(void *ctx, const char *bytes, size_t n)
{
    (void)ctx;
    fwrite(bytes, 1, n, stdout);
}

static void run_session(uint32_t master, uint32_t budget, int total, int first, int count)
{
    static char line[LINE_MAX_BYTES];
    char ghex[B2_GENOME_WORDS * 8 + 1];
    uint32_t genome[B2_GENOME_WORDS];
    uint64_t t[B2_LUTS];
    uint32_t seq = 0;
    int is_baseline, i;
    n_inits = 0;
    if (b3_orch_init(&orch, master, budget, total, first, count, "a13f38b53355fd4c1cac3145244727f8",
                     "895baf85ed31df9beae28a533646182ffb8d0e0735c9849ede9641af81ee7458", 0x5eedu) != 0) {
        puts("REFUSED");
        return;
    }
    while (b3_orch_next(&orch, genome, &is_baseline)) {
        const char *arm = b3_orch_arm_name(&orch);
        char view[32] = "-";
        seq++;
        p3_genome_to_hex(genome, ghex);
        if (!is_baseline && orch.pending_arm == B3_ARM_ONLINE && !orch.pending_holdout) {
            unsigned sum = 0;
            for (i = 0; i < B2_VECTORS; i++)
                sum += orch.s[B3_ARM_ONLINE].col_n[i];
            snprintf(view, sizeof(view), "%d,%u", orch.s[B3_ARM_ONLINE].col_keys_n, sum);
        }
        printf("CAND %d %d %s %d %lu %lu %s | %s\n", is_baseline, b3_orch_pair(&orch), arm ? arm : "-",
               orch.pending_holdout, (unsigned long)seq, (unsigned long)orch.pending_eval, view, ghex);
        fflush(stdout);
        if (read_line(line, sizeof(line)) != 0)
            exit(4);
        if (strcmp(line, "UNSCORED") == 0) {
            b3_orch_unobserved(&orch);
            continue;                              /* b3_orch_next proposes nothing more */
        }
        if (parse_tables(line, t) != 0) {
            puts("ERR cannot parse the readout");
            exit(5);
        }
        if (b3_orch_observe(&orch, seq, t) != 0) {
            puts("ERR the observation failed");
            exit(6);
        }
        if (!is_baseline) {
            if (b3_orch_record_block(&orch, block, sizeof(block)) == 0u) {
                puts("ERR the block did not render");
                exit(7);
            }
            printf("BLOCK %s\n", block);
        }
    }
    printf("END %lu %d\n", (unsigned long)seq, b3_orch_complete(&orch));
    fputs("CARTO ", stdout);
    b3_carto_state_render(&orch.carto, emit_stdout, NULL);
    fputc('\n', stdout);
    fputs("INITS", stdout);
    for (i = 0; i < n_inits; i++)
        printf(" %s", inits[i]);
    fputc('\n', stdout);
}

static void cmd_session(const char *p)
{
    uint32_t master, budget, total, first, count;
    if (parse_u32(&p, &master) < 0 || parse_u32(&p, &budget) < 0 || parse_u32(&p, &total) < 0 ||
        parse_u32(&p, &first) < 0 || parse_u32(&p, &count) < 0 || *p != '\0' || total > 0x7FFFu || first > 0x7FFFu ||
        count > 0x7FFFu) {
        puts("ERR cannot parse SESSION");
        return;
    }
    run_session(master, budget, (int)total, (int)first, (int)count);
}

static void cmd_session_flags(const char *p)
{
    uint32_t flags, master, budget;
    int total, first, count;
    if (parse_u32(&p, &flags) < 0 || parse_u32(&p, &master) < 0 || parse_u32(&p, &budget) < 0 || *p != '\0') {
        puts("ERR cannot parse SESSIONF");
        return;
    }
    if (b3_page_slice(flags, &total, &first, &count) != 0) {
        puts("REFUSED");                           /* the page is refused before any candidate */
        return;
    }
    run_session(master, budget, total, first, count);
}

int main(void)
{
    static char line[LINE_MAX_BYTES];
    while (read_line(line, sizeof(line)) == 0) {
        if (strcmp(line, "Q") == 0)
            return 0;
        if (strncmp(line, "SEEDS ", 6) == 0)
            cmd_seeds(line + 5);
        else if (strncmp(line, "PROFILE ", 8) == 0)
            cmd_profile(line + 7);
        else if (strncmp(line, "SLICE ", 6) == 0)
            cmd_slice(line + 5);
        else if (strncmp(line, "SESSION ", 8) == 0)
            cmd_session(line + 7);
        else if (strncmp(line, "SESSIONF ", 9) == 0)
            cmd_session_flags(line + 8);
        else
            puts("ERR unknown command");
        fflush(stdout);
    }
    return 0;
}
