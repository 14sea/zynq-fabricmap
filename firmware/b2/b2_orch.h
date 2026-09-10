/* b2_orch — the B2 session orchestrator, a pure unit (B1's b1_orch, re-aimed at stage B2).
 *
 * It owns the ORDER the application drives, and nothing else: the search itself is
 * b2_search.c, and the HAL, the transactions and the audit are b2_app.c.
 *
 * The order, fixed by docs/b2_preregistration.md §2:
 *
 *   opening baseline                       (the blank genome; its MEASURED readout is the
 *                                           base every arm of this session starts from)
 *   for each pair r of this session's slice:
 *       arm order = (A, B) when r is even, (B, A) when r is odd
 *       for arm in order:  `budget` evaluations                    -- the search
 *       for arm in order:  one champion evaluation                 -- the holdout known answer
 *   closing baseline
 *
 * The champion's holdout evaluation is a REAL candidate: the champion genome is written,
 * armed and read back again, and F1 is taken over the HOLDOUT columns of that fresh
 * readout. No `mode_holdout` flag is used and none is needed — the arm gate sweeps all 64
 * input vectors either way, so the readout already carries both column sets, and a fresh
 * write is stronger evidence than re-reading a stored one.
 *
 * The session's pair SLICE (`pair_first`, `pair_count`) comes from the identity page: a
 * session holds whole pairs, and the split across sessions is the preregistration's frozen
 * rule applied to the B2Q-measured rate. The pair SEEDS are not on the page: the board
 * derives all `pairs_total` of them from the master seed with the compiled exclusion table
 * (`b2_pair_seeds`), so the frozen rule is reproduced on the board.
 *
 * Any candidate that is not SCORED ends the epoch: the application stops, no further
 * candidate is proposed, and no closing baseline follows (B1's rule, and the defect its
 * first image had).
 */
#ifndef B2_ORCH_H
#define B2_ORCH_H

#include "b2_search.h"

#define B2_MAX_PAIRS 16                 /* the preregistered N is 9; a session's slice is at most this */
#define B2_ARMS 2

enum {
    B2_PH_OPEN = 0,                     /* the opening baseline */
    B2_PH_SEARCH_0 = 1,                 /* the first arm of the pair, in this pair's order */
    B2_PH_SEARCH_1 = 2,
    B2_PH_HOLDOUT_0 = 3,
    B2_PH_HOLDOUT_1 = 4,
    B2_PH_CLOSE = 5,                    /* the closing baseline */
    B2_PH_DONE = 6
};

typedef struct {
    /* the page */
    uint32_t master_seed, budget;
    int pairs_total, pair_first, pair_count;
    /* the derived pair seeds, all `pairs_total` of them */
    uint32_t seeds[2 * B2_MAX_PAIRS];
    /* the binding the records commit to */
    char token[33];
    char universe[65];
    uint32_t image_lo32;
    /* where we are */
    int phase;
    int pair_i;                         /* 0..pair_count-1 within the slice */
    int arm_at[B2_ARMS];                /* this pair's arm order: B2_ARM_* per position */
    uint64_t base[B2_LUTS];             /* the measured opening baseline */
    int have_base;
    b2_search s[B2_ARMS];               /* indexed by B2_ARM_*, not by position */
    int started[B2_ARMS];
    /* the proposal in flight */
    int pending_is_baseline;
    int pending_arm;                    /* B2_ARM_* of the arm in flight, or -1 on a baseline */
    int pending_holdout;
    uint32_t pending_eval;
    uint32_t seq_last;
} b2_orch;

/* the page's fields; `pair_first + pair_count <= pairs_total` and `pairs_total <= B2_MAX_PAIRS` */
int b2_orch_init(b2_orch *o, uint32_t master_seed, uint32_t budget, int pairs_total,
                 int pair_first, int pair_count, const char *token, const char *universe,
                 uint32_t image_lo32);
/* the next candidate (0 = the session is complete). `*is_baseline` marks the two brackets. */
int b2_orch_next(b2_orch *o, uint32_t genome[B2_GENOME_WORDS], int *is_baseline);
/* the application assigned `seq` to the last proposal and measured these tables */
void b2_orch_observe(b2_orch *o, uint32_t seq, const uint64_t tables[B2_LUTS]);
/* the last proposal was not SCORED: the epoch ends */
void b2_orch_unobserved(b2_orch *o);
/* the `search` block for the record just observed, or 0 for a baseline (which carries none) */
size_t b2_orch_record_block(const b2_orch *o, char *out, size_t max);
/* the arm of the record just observed, as the wire names it, or NULL on a baseline */
const char *b2_orch_arm_name(const b2_orch *o);
/* the absolute pair index (0..pairs_total-1) of the record just observed, or -1 */
int b2_orch_pair(const b2_orch *o);

#endif /* B2_ORCH_H */
