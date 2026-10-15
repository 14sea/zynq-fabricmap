/* b3_orch — the B3 session orchestrator, a pure unit. See b3_orch.h (derived from firmware/b2/b2_orch.c). */
#include "b3_orch.h"
#include "b3_seed_data.h"
#include "b3_wire.h"

#include <string.h>

static void genome_clear(uint32_t g[B2_GENOME_WORDS]) { memset(g, 0, sizeof(uint32_t) * B2_GENOME_WORDS); }

int b3_page_slice(uint32_t flags, int *pairs_total, int *pair_first, int *pair_count)
{
    int total, first, count;
    if ((flags >> 28) != 0u)                       /* reserved bits: fail closed */
        return -1;
    total = (int)((flags >> 16) & 0xfu) + 1;
    first = (int)((flags >> 20) & 0xfu);
    count = (int)((flags >> 24) & 0xfu) + 1;
    if (total > B3_MAX_PAIRS || first + count > total)
        return -1;
    if (pairs_total)
        *pairs_total = total;
    if (pair_first)
        *pair_first = first;
    if (pair_count)
        *pair_count = count;
    return 0;
}

/* ------------------------------------------------------------------ the seed rule */
static int seed_excluded(uint32_t v)
{
    int lo = 0, hi = B3_SEED_EXCLUDED_N - 1;
    while (lo <= hi) {                             /* the generated table is ascending */
        int mid = lo + (hi - lo) / 2;
        uint32_t m = B3_SEED_EXCLUDED[mid];
        if (m == v)
            return 1;
        if (m < v)
            lo = mid + 1;
        else
            hi = mid - 1;
    }
    return 0;
}

static int in_list(const uint32_t *a, int n, uint32_t v)
{
    int i;
    for (i = 0; i < n; i++)
        if (a[i] == v)
            return 1;
    return 0;
}

int b3_pair_seeds(uint32_t master, int count, const uint32_t *extra, int n_extra, uint32_t *out)
{
    b2_rng r;
    int n = 0;
    if (count < 1 || count > B3_MAX_PAIRS || n_extra < 0 || (n_extra > 0 && extra == NULL) || out == NULL)
        return -1;
    b2_rng_init(&r, master);
    while (n < count) {
        uint32_t l = b2_rng_next32(&r);
        uint32_t o = b2_rng_next32(&r);
        if (seed_excluded(l) || seed_excluded(o) || l == o)
            continue;                              /* the whole pair, as b2_search.pair_seeds */
        if (in_list(extra, n_extra, l) || in_list(extra, n_extra, o))
            continue;
        if (in_list(out, 2 * n, l) || in_list(out, 2 * n, o))
            continue;                              /* every seed drawn so far is distinct */
        out[2 * n] = l;
        out[2 * n + 1] = o;
        n++;
    }
    return 0;
}

int b3_profile(uint32_t master, uint32_t budget, int pairs_total)
{
    if (master == B3_PROFILE_B3_MASTER && budget == B3_PROFILE_B3_BUDGET && pairs_total == B3_PROFILE_B3_PAIRS)
        return B3_PROFILE_B3;
    if (master == B3_PROFILE_B3Q_MASTER && budget == B3_PROFILE_B3Q_BUDGET && pairs_total == B3_PROFILE_B3Q_PAIRS)
        return B3_PROFILE_B3Q;
    return B3_PROFILE_NONE;
}

int b3_profile_seeds(uint32_t master, uint32_t budget, int pairs_total, uint32_t *out)
{
    uint32_t b3[2 * B3_PROFILE_B3_PAIRS];
    int p = b3_profile(master, budget, pairs_total);
    if (p == B3_PROFILE_B3) {
        if (b3_pair_seeds(master, pairs_total, NULL, 0, out) != 0)
            return B3_PROFILE_NONE;
    } else if (p == B3_PROFILE_B3Q) {          /* B3Q also excludes every seed of B3's pairs */
        if (b3_pair_seeds(B3_PROFILE_B3_MASTER, B3_PROFILE_B3_PAIRS, NULL, 0, b3) != 0 ||
            b3_pair_seeds(master, pairs_total, b3, 2 * B3_PROFILE_B3_PAIRS, out) != 0)
            return B3_PROFILE_NONE;
    }
    return p;
}

/* ------------------------------------------------------------------ the order */
static int abs_pair(const b3_orch *o) { return o->pair_first + o->pair_i; }

static int arm_code(char letter)
{
    return letter == 'R' ? B2_ARM_RANDOM_SAFE : letter == 'F' ? B2_ARM_MAP_GUIDED : B3_ARM_ONLINE;
}

static void set_arm_order(b3_orch *o)
{
    /* pair r runs the (r mod 6)-th of the prefix-balanced sequence (preregistration §2): over any N an arm's
     * position counts differ by at most 1 between arms, equal exactly when N is a multiple of 3 */
    static const char *const sequence[6] = {"RFO", "FOR", "ORF", "ROF", "OFR", "FRO"};
    const char *s = sequence[abs_pair(o) % 6];
    int i;
    for (i = 0; i < B3_ARMS; i++)
        o->arm_at[i] = arm_code(s[i]);
}

static void start_pair(b3_orch *o)
{
    int i;
    set_arm_order(o);
    for (i = 0; i < B3_ARMS; i++)
        o->started[i] = 0;
    o->have_entry = 0;                             /* no ledger entry crosses a pair */
}

/* the arm whose search or holdout the current phase drives */
static int phase_arm(const b3_orch *o)
{
    if (o->phase >= B3_PH_SEARCH_0 && o->phase <= B3_PH_SEARCH_2)
        return o->arm_at[o->phase - B3_PH_SEARCH_0];
    if (o->phase >= B3_PH_HOLDOUT_0 && o->phase <= B3_PH_HOLDOUT_2)
        return o->arm_at[o->phase - B3_PH_HOLDOUT_0];
    return -1;
}

static void ensure_started(b3_orch *o, int arm)
{
    int r = abs_pair(o);
    if (o->started[arm])
        return;
    if (arm == B3_ARM_ONLINE) {                    /* its own initializer, an empty view, a fresh cartographer */
        b3_online_init(&o->s[arm], o->seeds[2 * r], o->seeds[2 * r + 1], o->budget, o->base);
        b3_carto_init(&o->carto);
        o->have_entry = 0;
    } else {
        b2_search_init(&o->s[arm], arm, o->seeds[2 * r], o->seeds[2 * r + 1], o->budget, o->base);
    }
    o->started[arm] = 1;
}

int b3_orch_init(b3_orch *o, uint32_t master_seed, uint32_t budget, int pairs_total, int pair_first, int pair_count,
                 const char *token, const char *universe, uint32_t image_lo32)
{
    size_t n;
    memset(o, 0, sizeof(*o));
    b3_carto_init(&o->carto);                      /* a valid empty map even before the O arm starts (0 is a position) */
    o->phase = B3_PH_DONE;                         /* a refused init proposes nothing */
    if (pairs_total <= 0 || pairs_total > B3_MAX_PAIRS)
        return -1;
    /* the slice, without an addition that can overflow (the owner's P2 on 0fe24b0: pair_first + pair_count with
     * pair_first = INT_MAX or pair_count = INT_MAX is signed overflow, and once accepted a candidate was proposed) */
    if (pair_first < 0 || pair_first >= pairs_total || pair_count <= 0 || pair_count > pairs_total - pair_first)
        return -1;
    if (budget == 0u || token == NULL || universe == NULL)
        return -1;
    o->profile = b3_profile_seeds(master_seed, budget, pairs_total, o->seeds);
    if (o->profile == B3_PROFILE_NONE)
        return -1;
    o->master_seed = master_seed;
    o->budget = budget;
    o->pairs_total = pairs_total;
    o->pair_first = pair_first;
    o->pair_count = pair_count;
    n = strlen(token);
    memcpy(o->token, token, n < 32u ? n : 32u);
    n = strlen(universe);
    memcpy(o->universe, universe, n < 64u ? n : 64u);
    o->image_lo32 = image_lo32;
    o->phase = B3_PH_OPEN;
    o->pending_arm = -1;
    o->pending_holdout = 0;
    return 0;
}

int b3_orch_next(b3_orch *o, uint32_t genome[B2_GENOME_WORDS], int *is_baseline)
{
    int arm;
    for (;;) {
        switch (o->phase) {
        case B3_PH_OPEN:
        case B3_PH_CLOSE:
            genome_clear(genome);                  /* the blank genome IS the pinned base */
            *is_baseline = 1;
            o->pending_is_baseline = 1;
            o->pending_arm = -1;
            o->pending_holdout = 0;
            return 1;
        case B3_PH_SEARCH_0:
        case B3_PH_SEARCH_1:
        case B3_PH_SEARCH_2:
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
            o->phase++;                            /* the next arm's search, or the first holdout */
            continue;
        case B3_PH_HOLDOUT_0:
        case B3_PH_HOLDOUT_1:
        case B3_PH_HOLDOUT_2:
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
            if (o->phase != B3_PH_HOLDOUT_2) {
                o->phase++;
                continue;
            }
            o->pair_i++;
            if (o->pair_i < o->pair_count) {
                start_pair(o);
                o->phase = B3_PH_SEARCH_0;
                continue;
            }
            o->phase = B3_PH_CLOSE;
            continue;
        default:
            return 0;
        }
    }
}

/* the O arm's search observation: the specimen first (the served parent's tables are still in the population),
 * then the search, the cartographer, the view, the ledger entry */
static int observe_online(b3_orch *o, const uint64_t tables[B2_LUTS])
{
    b2_search *s = &o->s[B3_ARM_ONLINE];
    uint32_t version_before = o->carto.version;
    int nd = b3_delta_positions(s->pop[s->pending_parent].tables, tables, o->delta);
    int n;
    b2_search_observe(s, tables);
    n = b3_carto_observe(&o->carto, &o->scratch, s->last_bits, s->pending_nbits_last, o->delta, nd, o->newly, B3_CARTO_N);
    if (n < 0)
        n = 0;                                     /* a refused specimen: counted by the cartographer, nothing decoded */
    if (n > 0 && b3_online_view_rebuild(s, &o->carto) < 0)
        return -1;
    o->entry.seq = s->evals;
    o->entry.map_version = version_before;
    o->entry.map_version_after = o->carto.version;
    o->entry.anomalies = o->carto.anomalies;
    o->entry.parent_born = s->last_parent_born;
    o->entry.fitness = s->last_fit;
    o->entry.kind = s->last_kind;
    o->entry.bits = s->last_bits;
    o->entry.n_bits = s->pending_nbits_last;
    o->entry.delta = o->delta;
    o->entry.n_delta = nd;
    o->entry.newly = o->newly;
    o->entry.n_newly = n;
    o->entry.carto = &o->carto;
    o->have_entry = 1;
    return 0;
}

int b3_orch_observe(b3_orch *o, uint32_t seq, const uint64_t tables[B2_LUTS])
{
    int k;
    o->seq_last = seq;
    if (o->pending_is_baseline) {
        if (o->phase == B3_PH_OPEN) {
            for (k = 0; k < B2_LUTS; k++)
                o->base[k] = tables[k];
            o->have_base = 1;
            start_pair(o);
            o->phase = B3_PH_SEARCH_0;
        } else {
            o->phase = B3_PH_DONE;
            o->completed = 1;                      /* the closing baseline was observed */
        }
        return 0;
    }
    if (o->pending_holdout) {
        b2_search_champion_observe(&o->s[o->pending_arm], tables);
        if (o->pending_arm == B3_ARM_ONLINE)
            o->have_entry = 0;                     /* the holdout observes no specimen and carries no ledger */
        return 0;
    }
    if (o->pending_arm == B3_ARM_ONLINE)
        return observe_online(o, tables);
    b2_search_observe(&o->s[o->pending_arm], tables);
    return 0;
}

void b3_orch_unobserved(b3_orch *o)
{
    if (!o->pending_is_baseline && o->pending_arm >= 0) {
        if (o->pending_holdout)
            o->s[o->pending_arm].champion_pending = 0;
        else
            b2_search_unobserved(&o->s[o->pending_arm]);
        if (o->pending_arm == B3_ARM_ONLINE)
            o->have_entry = 0;                     /* no specimen, no map update, no ledger */
    }
    o->phase = B3_PH_DONE;                         /* an unscored candidate ends the epoch */
}

const char *b3_orch_arm_name(const b3_orch *o)
{
    if (o->pending_is_baseline || o->pending_arm < 0)
        return NULL;                               /* a baseline carries no arm */
    return o->pending_arm == B2_ARM_RANDOM_SAFE ? B3_WIRE_ARM_RANDOM_SAFE
         : o->pending_arm == B2_ARM_MAP_GUIDED  ? B3_WIRE_ARM_MAP_GUIDED
                                                : B3_WIRE_ARM_ONLINE;
}

int b3_orch_pair(const b3_orch *o)
{
    if (o->pending_is_baseline)
        return -1;
    return abs_pair(o);
}

int b3_orch_complete(const b3_orch *o)
{
    return o->completed;
}

size_t b3_orch_record_block(const b3_orch *o, char *out, size_t max)
{
    const b2_search *s;
    if (o->pending_is_baseline || o->pending_arm < 0)
        return 0u;
    s = &o->s[o->pending_arm];
    if (o->pending_arm == B3_ARM_ONLINE) {
        if (o->pending_holdout)
            return b3_record_json(s, &o->carto, abs_pair(o), o->pending_eval, s->champion_holdout, NULL, out, max);
        if (!o->have_entry)
            return 0u;                             /* no observation was made: no block */
        return b3_record_json(s, &o->carto, abs_pair(o), o->pending_eval, -1, &o->entry, out, max);
    }
    return b2_search_record_json(s, abs_pair(o), o->pending_arm == B2_ARM_RANDOM_SAFE ? "A" : "B", o->pending_eval,
                                 o->pending_holdout ? s->champion_holdout : -1, out, max);
}
