/* b2_search — the on-board search of stage B2, a pure unit.
 *
 * Compiled BOTH into the board application (b2_app.c) and into the host twin (b2_twin.c),
 * and the twin is checked against the Python reference (host/b2_search.py and
 * host/b2_landscape.py) evaluation by evaluation — the discipline B1's cartographer used.
 *
 * The question (docs/b2_architecture.md): does a frozen, board-built map make the SAME
 * selection engine beat random-safe on a fitness with real interaction between bits? So this
 * unit holds ONE engine and TWO operators, and the arm is a parameter:
 *
 *   arm A  random-safe : k ~ U{1..B2_KMAX}; k distinct universe bits, uniform, without
 *                        replacement. The map is never read.
 *   arm B  map-guided  : with probability 1/2 the random-safe move; otherwise a COLUMN move
 *                        — a train column the map names, drawn uniformly, and a non-empty
 *                        subset (1..min(KMAX, |column|)) of the genome bits the map places
 *                        there. Only `relation.init_index` is read; the LUT index is not
 *                        part of the operator.
 *
 * The engine is (mu + lambda) = (4 + 8) with truncation selection, ties by age (every
 * individual has a unique birth index), and the initial population is mu copies of the base.
 * One child is one BOARD EVALUATION: the application writes the candidate, arms the gate and
 * reads the PL's functional readout, and this unit's `observe` computes the fitness FROM THAT
 * MEASURED READOUT — never from a model of it. The parent an individual passes on carries the
 * measured tables it was scored from.
 *
 * The landscape is a public rule: the target is the instrument's xorshift stream taken per
 * (LUT, INIT) in k-major order and masked to the universe, where the universe mask is derived
 * from the compiled B1 self-map (p3_data.h `B2_MAP_LUT` / `B2_MAP_INIT`). Fitness F1 is the
 * number of TRAIN columns whose six-bit readout word equals the target's. Holdout is scored
 * once per arm, on the champion, and is a neutrality / known-answer control — not
 * generalisation (docs/b2_architecture.md §8).
 *
 * Everything is integer and deterministic from (arm, landscape seed, operator seed, budget,
 * the observations), so the C image and its Python reference produce the same bytes.
 */
#ifndef B2_SEARCH_H
#define B2_SEARCH_H

#include <stddef.h>
#include <stdint.h>

#define B2_SEARCH_VERSION "b2-es-v1"
#define B2_N 292
#define B2_LUTS 6
#define B2_VECTORS 64
#define B2_MU 4
#define B2_LAMBDA 8
#define B2_KMAX 4
#define B2_GENOME_WORDS 10
#define B2_ARM_RANDOM_SAFE 0
#define B2_ARM_MAP_GUIDED 1
#define B2_MOVE_RANDOM 0
#define B2_MOVE_COLUMN 1

typedef struct { uint64_t x; } b2_rng;

typedef struct {
    uint32_t genome[B2_GENOME_WORDS];
    uint64_t tables[B2_LUTS];          /* the MEASURED readout this individual was scored from */
    int32_t fit;                       /* train fitness F1 */
    uint32_t born;                     /* unique birth index: the tie-break */
} b2_indiv;

typedef struct {
    /* the landscape (public rule, masked to the universe) */
    uint32_t landscape_seed;
    uint64_t masks[B2_LUTS];
    uint64_t target[B2_LUTS];
    /* the map as the operator sees it: train columns -> genome bits (init index only) */
    uint8_t col_keys[B2_VECTORS];
    int col_keys_n;
    uint16_t col_bits[B2_VECTORS][B2_LUTS];
    uint8_t col_n[B2_VECTORS];
    /* the engine */
    int arm;
    uint32_t operator_seed, budget;
    b2_rng rng;
    b2_indiv pop[B2_MU];
    b2_indiv child[B2_LAMBDA];
    int nchild;
    uint32_t born, evals, generation, column_moves;
    int32_t base_fit, best;
    /* the proposal in flight */
    int pending;
    int pending_parent;                /* index into pop */
    uint32_t pending_parent_born;
    uint16_t pending_bits[B2_KMAX];
    int pending_nbits, pending_kind;
    uint32_t pending_genome[B2_GENOME_WORDS];
    /* the last observation, for the record block */
    int32_t last_fit;
    int last_selected;                 /* 1 = this observation closed a generation */
    /* the champion's holdout evaluation */
    int champion_pending, champion_done;
    int32_t champion_holdout;
} b2_search;

/* the RNG: l6_operators.Rng exactly (xorshift64, warm-up 4, rejection sampling) */
void b2_rng_init(b2_rng *r, uint32_t seed32);
uint32_t b2_rng_next32(b2_rng *r);
uint32_t b2_rng_uniform(b2_rng *r, uint32_t n);

/* the frozen session seed rule: pairs of (landscape, operator) seeds off the master seed,
 * skipping every value of B2_EXCLUDED_SEEDS. Fills `out` with 2*count 32-bit seeds. */
void b2_pair_seeds(uint32_t master, int count, uint32_t *out);

/* the universe mask and the public target rule (both derived, neither compiled in) */
void b2_universe_mask(uint64_t masks[B2_LUTS]);
void b2_target(uint32_t landscape_seed, const uint64_t masks[B2_LUTS], uint64_t target[B2_LUTS]);

/* F1 over the train columns / the holdout columns */
int32_t b2_f1_train(const uint64_t tables[B2_LUTS], const uint64_t target[B2_LUTS]);
int32_t b2_f1_holdout(const uint64_t tables[B2_LUTS], const uint64_t target[B2_LUTS]);

/* one arm of one pair. `base` is the MEASURED opening-baseline readout. */
void b2_search_init(b2_search *s, int arm, uint32_t landscape_seed, uint32_t operator_seed,
                    uint32_t budget, const uint64_t base[B2_LUTS]);
/* propose the next candidate (0 = the budget is spent); *kind_out is B2_MOVE_* */
int b2_search_next(b2_search *s, uint32_t genome[B2_GENOME_WORDS], int *kind_out);
/* the application measured this readout for the proposal in flight */
void b2_search_observe(b2_search *s, const uint64_t tables[B2_LUTS]);
/* the proposal was not scored: nothing is learned and the generation does not advance */
void b2_search_unobserved(b2_search *s);
/* the champion after the budget (pop[0]); 0 if a proposal is still in flight */
int b2_search_champion(const b2_search *s, uint32_t genome[B2_GENOME_WORDS], int32_t *fit_out);
/* the champion's holdout evaluation: propose, then observe its measured readout */
int b2_search_champion_next(b2_search *s, uint32_t genome[B2_GENOME_WORDS]);
void b2_search_champion_observe(b2_search *s, const uint64_t tables[B2_LUTS]);

#endif
