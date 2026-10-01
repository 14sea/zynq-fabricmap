/* b3_orch — the B3 session orchestrator, a pure unit. B3 lifecycle 2, image stage 4.
 *
 * DERIVED from firmware/b2/b2_orch.{c,h} (docs/b3_architecture.md v0.3 §7, Decision E1; recorded in
 * b3/firmware/IMPORT.json). It owns the ORDER the application drives and the O arm's board observation;
 * the searches are b2_search.c (R, F) and b2_search.c + b3_online_view.c + b3_carto.c (O), the record
 * blocks b2_search_record_json (R, F) and b3_record_json (O), and the HAL, the transactions and the audit
 * are the application's. The order (preregistration v0.3.1 §2; b3/host/b3_session.py is its reference):
 *
 *   opening baseline                     the blank genome; its MEASURED readout is every arm's base
 *   for each absolute pair r of this session's slice:
 *       arm order = the (r mod 6)-th of RFO, FOR, ORF, ROF, OFR, FRO
 *       for arm in order:  `budget` evaluations                 -- the three searches
 *       for arm in order:  one champion evaluation              -- the three holdout known answers
 *   closing baseline
 *
 * The arms: R = B2's random-safe arm and F = B2's map-guided arm over the compiled B1 self-map, both
 * initialised by b2_search_init; O = the online arm, initialised by b3_online_init (B2's engine state, an
 * EMPTY view — never b2_search_init, which reads the frozen map) with a fresh cartographer every pair.
 *
 * The O arm's observation, owned here: before the search observation changes the population, the
 * positions that toggled between the served parent's measured tables and the served child's are taken;
 * the search observes; the cartographer observes the specimen (the move's bits, those positions); on a
 * decode the view is rebuilt; the ledger entry is filled — its arrays and its cartographer live in this
 * state until the record block is rendered. The O champion's holdout evaluation observes no specimen,
 * updates no view and carries no ledger. An O candidate that is not scored updates nothing.
 *
 * The SEEDS are the formal B3 rule reproduced on the board (the owner's ruling of 2026-10-01), not B2's
 * table: b3_pair_seeds draws from b2_rng (one stream off the master; per draw a (landscape, operator) pair,
 * the WHOLE pair skipped when either seed is excluded, already drawn, or the two are equal) against the
 * generated b3_seed_data.h set; B3Q's draw also excludes every seed of B3's pairs, which it derives from
 * the B3 profile. A session is B3's or B3Q's by (master, budget, pairs_total) exactly — anything else is
 * refused at init, before any candidate.
 *
 * Any candidate that is not SCORED ends the epoch: nothing further is proposed and no closing baseline
 * follows; the session is complete only when the closing baseline was observed.
 *
 * All the state — three searches, the cartographer and its scratch (each ~15 KB), the ledger arrays — is
 * the b3_orch the CALLER owns (a static in the twin, BSS in the image): no frame here holds any of it.
 */
#ifndef B3_ORCH_H
#define B3_ORCH_H

#include "b2_search.h"
#include "b3_carto.h"
#include "b3_online_view.h"
#include "b3_record.h"

#define B3_MAX_PAIRS 16                 /* B3's preregistered N is 8, B3Q's 1; a slice is at most this */
#define B3_ARMS 3                       /* indexed by arm code: B2_ARM_RANDOM_SAFE, B2_ARM_MAP_GUIDED, B3_ARM_ONLINE */
#define B3_PROFILE_NONE 0
#define B3_PROFILE_B3 1
#define B3_PROFILE_B3Q 2

enum {
    B3_PH_OPEN = 0,                     /* the opening baseline */
    B3_PH_SEARCH_0 = 1,                 /* the pair's arms in this pair's order */
    B3_PH_SEARCH_1 = 2,
    B3_PH_SEARCH_2 = 3,
    B3_PH_HOLDOUT_0 = 4,
    B3_PH_HOLDOUT_1 = 5,
    B3_PH_HOLDOUT_2 = 6,
    B3_PH_CLOSE = 7,                    /* the closing baseline */
    B3_PH_DONE = 8
};

typedef struct {
    /* the page and the profile */
    uint32_t master_seed, budget;
    int pairs_total, pair_first, pair_count;
    int profile;                        /* B3_PROFILE_B3 | B3_PROFILE_B3Q */
    uint32_t seeds[2 * B3_MAX_PAIRS];   /* all `pairs_total` pairs, derived on the board */
    /* the binding the records commit to */
    char token[33];
    char universe[65];
    uint32_t image_lo32;
    /* where we are */
    int phase;
    int pair_i;                         /* 0..pair_count-1 within the slice */
    int arm_at[B3_ARMS];                /* this pair's arm order: arm codes per position */
    uint64_t base[B2_LUTS];             /* the measured opening baseline */
    int have_base;
    b2_search s[B3_ARMS];               /* indexed by arm code, not by position */
    int started[B3_ARMS];
    /* the O arm's cartographer, its scratch, and the ledger entry of the observation just made */
    b3_carto carto, scratch;
    uint16_t delta[B3_CARTO_POSITIONS];
    uint16_t newly[B3_CARTO_N];
    b3_ledger_entry entry;
    int have_entry;
    /* the proposal in flight */
    int pending_is_baseline;
    int pending_arm;                    /* the arm code in flight, or -1 on a baseline */
    int pending_holdout;
    uint32_t pending_eval;
    uint32_t seq_last;
    int completed;                      /* 1 only when the CLOSING baseline was observed */
} b3_orch;

/* The session's pair SLICE in the identity page's `flags` word — B2's layout (firmware/b2/b2_orch.h):
 *   bits  0..15  the instrument's flags, untouched
 *   bits 16..19  pairs_total - 1   (1..16)
 *   bits 20..23  pair_first        (0..15)
 *   bits 24..27  pair_count - 1    (1..16)
 *   bits 28..31  reserved, MUST be zero
 * Returns 0 and fills the three fields, or -1 when a reserved bit is set or the slice does not lie inside
 * the experiment — a page refusal, fail-closed, before any candidate is proposed. */
#define B3_FLAGS_SLICE_SHIFT 16
int b3_page_slice(uint32_t flags, int *pairs_total, int *pair_first, int *pair_count);

/* The seed rule: `count` (1..B3_MAX_PAIRS) pairs off `master` into out[2*count], excluding the generated set,
 * the `n_extra` values of `extra` (may be NULL when n_extra is 0) and every seed already drawn. Returns 0, or
 * -1 on a bad count. Exposed for the twin, which drives it with any master; production goes through the
 * profile (b3_profile_seeds / b3_orch_init). */
int b3_pair_seeds(uint32_t master, int count, const uint32_t *extra, int n_extra, uint32_t *out);

/* The profile (master, budget, pairs_total) names — B3_PROFILE_B3, B3_PROFILE_B3Q, or B3_PROFILE_NONE. */
int b3_profile(uint32_t master, uint32_t budget, int pairs_total);

/* A profile's seeds: B3's from its master; B3Q's from its master, excluding every seed of B3's pairs too.
 * Returns the profile, or B3_PROFILE_NONE (out untouched) when (master, budget, pairs_total) is not one. */
int b3_profile_seeds(uint32_t master, uint32_t budget, int pairs_total, uint32_t *out);

/* The page's fields: the profile must match exactly and the slice must lie inside it; else -1, nothing to
 * propose. */
int b3_orch_init(b3_orch *o, uint32_t master_seed, uint32_t budget, int pairs_total, int pair_first, int pair_count,
                 const char *token, const char *universe, uint32_t image_lo32);
/* the next candidate (0 = the session is over). `*is_baseline` marks the two brackets. */
int b3_orch_next(b3_orch *o, uint32_t genome[B2_GENOME_WORDS], int *is_baseline);
/* the application assigned `seq` to the last proposal and measured these tables. Returns 0, or -1 when the
 * O arm's view could not be rebuilt (a cartographer that cannot exist; the caller treats it as PROTOCOL) */
int b3_orch_observe(b3_orch *o, uint32_t seq, const uint64_t tables[B2_LUTS]);
/* the last proposal was not SCORED: the epoch ends, and nothing — search, map or ledger — is updated */
void b3_orch_unobserved(b3_orch *o);
/* the `search` block for the record just observed, or 0 for a baseline (which carries none) */
size_t b3_orch_record_block(const b3_orch *o, char *out, size_t max);
/* the arm of the record just observed, as the wire names it (B3_WIRE_ARM_*), or NULL on a baseline */
const char *b3_orch_arm_name(const b3_orch *o);
/* the absolute pair index (0..pairs_total-1) of the record just observed, or -1 */
int b3_orch_pair(const b3_orch *o);
/* 1 only when the session ran to its closing baseline AND that baseline was observed */
int b3_orch_complete(const b3_orch *o);

#endif /* B3_ORCH_H */
