/* b2_orch — the B2 session orchestrator, a pure unit. See b2_orch.h. */
#include "b2_orch.h"

#include <string.h>

static void genome_clear(uint32_t g[B2_GENOME_WORDS]) { memset(g, 0, sizeof(uint32_t) * B2_GENOME_WORDS); }

int b2_page_slice(uint32_t flags, int *pairs_total, int *pair_first, int *pair_count)
{
    int total, first, count;
    if ((flags >> 28) != 0u)                       /* reserved bits: fail closed */
        return -1;
    total = (int)((flags >> 16) & 0xfu) + 1;
    first = (int)((flags >> 20) & 0xfu);
    count = (int)((flags >> 24) & 0xfu) + 1;
    if (total > B2_MAX_PAIRS || first + count > total)
        return -1;
    if (pairs_total)
        *pairs_total = total;
    if (pair_first)
        *pair_first = first;
    if (pair_count)
        *pair_count = count;
    return 0;
}

static int abs_pair(const b2_orch *o) { return o->pair_first + o->pair_i; }

static void set_arm_order(b2_orch *o)
{
    /* pair r runs A then B when r is even, B then A when r is odd (preregistration §2):
     * drift in the instrument is then not confounded with the arm */
    if ((abs_pair(o) % 2) == 0) {
        o->arm_at[0] = B2_ARM_RANDOM_SAFE;
        o->arm_at[1] = B2_ARM_MAP_GUIDED;
    } else {
        o->arm_at[0] = B2_ARM_MAP_GUIDED;
        o->arm_at[1] = B2_ARM_RANDOM_SAFE;
    }
}

static void start_pair(b2_orch *o)
{
    int i;
    set_arm_order(o);
    for (i = 0; i < B2_ARMS; i++)
        o->started[i] = 0;
}

/* the arm whose search or holdout the current phase drives */
static int phase_arm(const b2_orch *o)
{
    switch (o->phase) {
    case B2_PH_SEARCH_0:
    case B2_PH_HOLDOUT_0:
        return o->arm_at[0];
    case B2_PH_SEARCH_1:
    case B2_PH_HOLDOUT_1:
        return o->arm_at[1];
    default:
        return -1;
    }
}

static void ensure_started(b2_orch *o, int arm)
{
    int r = abs_pair(o);
    if (o->started[arm])
        return;
    b2_search_init(&o->s[arm], arm, o->seeds[2 * r], o->seeds[2 * r + 1], o->budget, o->base);
    o->started[arm] = 1;
}

int b2_orch_init(b2_orch *o, uint32_t master_seed, uint32_t budget, int pairs_total,
                 int pair_first, int pair_count, const char *token, const char *universe,
                 uint32_t image_lo32)
{
    size_t n;
    memset(o, 0, sizeof(*o));
    if (pairs_total <= 0 || pairs_total > B2_MAX_PAIRS)
        return -1;
    if (pair_first < 0 || pair_count <= 0 || pair_first + pair_count > pairs_total)
        return -1;
    if (budget == 0u)
        return -1;
    o->master_seed = master_seed;
    o->budget = budget;
    o->pairs_total = pairs_total;
    o->pair_first = pair_first;
    o->pair_count = pair_count;
    b2_pair_seeds(master_seed, pairs_total, o->seeds);
    n = strlen(token);
    memcpy(o->token, token, n < 32u ? n : 32u);
    n = strlen(universe);
    memcpy(o->universe, universe, n < 64u ? n : 64u);
    o->image_lo32 = image_lo32;
    o->phase = B2_PH_OPEN;
    o->pending_arm = -1;
    o->pending_holdout = 0;
    return 0;
}

int b2_orch_next(b2_orch *o, uint32_t genome[B2_GENOME_WORDS], int *is_baseline)
{
    int arm;
    for (;;) {
        switch (o->phase) {
        case B2_PH_OPEN:
            genome_clear(genome);                       /* the blank genome IS the pinned base */
            *is_baseline = 1;
            o->pending_is_baseline = 1;
            o->pending_arm = -1;
            o->pending_holdout = 0;
            return 1;
        case B2_PH_SEARCH_0:
        case B2_PH_SEARCH_1:
            arm = phase_arm(o);
            ensure_started(o, arm);
            if (b2_search_next(&o->s[arm], genome, NULL)) {
                *is_baseline = 0;
                o->pending_is_baseline = 0;
                o->pending_arm = arm;
                o->pending_holdout = 0;
                o->pending_eval = o->s[arm].evals + 1u;
                return 1;
            }
            o->phase = (o->phase == B2_PH_SEARCH_0) ? B2_PH_SEARCH_1 : B2_PH_HOLDOUT_0;
            continue;
        case B2_PH_HOLDOUT_0:
        case B2_PH_HOLDOUT_1:
            arm = phase_arm(o);
            ensure_started(o, arm);
            if (b2_search_champion_next(&o->s[arm], genome)) {
                *is_baseline = 0;
                o->pending_is_baseline = 0;
                o->pending_arm = arm;
                o->pending_holdout = 1;
                o->pending_eval = o->s[arm].evals;
                return 1;
            }
            if (o->phase == B2_PH_HOLDOUT_0) {
                o->phase = B2_PH_HOLDOUT_1;
                continue;
            }
            o->pair_i++;
            if (o->pair_i < o->pair_count) {
                start_pair(o);
                o->phase = B2_PH_SEARCH_0;
                continue;
            }
            o->phase = B2_PH_CLOSE;
            continue;
        case B2_PH_CLOSE:
            genome_clear(genome);
            *is_baseline = 1;
            o->pending_is_baseline = 1;
            o->pending_arm = -1;
            o->pending_holdout = 0;
            return 1;
        default:
            return 0;
        }
    }
}

void b2_orch_observe(b2_orch *o, uint32_t seq, const uint64_t tables[B2_LUTS])
{
    int k;
    o->seq_last = seq;
    if (o->pending_is_baseline) {
        if (o->phase == B2_PH_OPEN) {
            for (k = 0; k < B2_LUTS; k++)
                o->base[k] = tables[k];
            o->have_base = 1;
            start_pair(o);
            o->phase = B2_PH_SEARCH_0;
        } else {
            o->phase = B2_PH_DONE;
        }
        return;
    }
    if (o->pending_holdout)
        b2_search_champion_observe(&o->s[o->pending_arm], tables);
    else
        b2_search_observe(&o->s[o->pending_arm], tables);
}

void b2_orch_unobserved(b2_orch *o)
{
    if (!o->pending_is_baseline && o->pending_arm >= 0) {
        if (o->pending_holdout)
            o->s[o->pending_arm].champion_pending = 0;
        else
            b2_search_unobserved(&o->s[o->pending_arm]);
    }
    o->phase = B2_PH_DONE;                              /* an unscored candidate ends the epoch */
}

const char *b2_orch_arm_name(const b2_orch *o)
{
    if (o->pending_is_baseline || o->pending_arm < 0)
        return NULL;                                    /* a baseline carries no arm */
    return (o->pending_arm == B2_ARM_RANDOM_SAFE) ? "random_safe" : "map_guided";
}

int b2_orch_pair(const b2_orch *o)
{
    if (o->pending_is_baseline)
        return -1;
    return abs_pair(o);
}

size_t b2_orch_record_block(const b2_orch *o, char *out, size_t max)
{
    const b2_search *s;
    if (o->pending_is_baseline || o->pending_arm < 0)
        return 0u;
    s = &o->s[o->pending_arm];
    return b2_search_record_json(s, abs_pair(o), (o->pending_arm == B2_ARM_RANDOM_SAFE) ? "A" : "B",
                                 o->pending_eval, o->pending_holdout ? s->champion_holdout : -1,
                                 out, max);
}
