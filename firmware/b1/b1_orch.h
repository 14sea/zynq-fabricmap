/* b1_orch — the session orchestrator (stage B1), a pure unit shared by the board application
 * (b1_app.c main) and the host twin (b1_twin.c `session` mode), so that the ORDER of the
 * session — opening baseline, the cartographer's probes, closing baseline — and the
 * initialisation of the cartographer BEFORE the opening baseline are one implementation,
 * exercised on the host end to end (tests/test_b1_session.py). The first B1 image
 * initialised the cartographer after the opening baseline, so the opening record's
 * commitment was the zero-initialised struct's hash and the host's reconstruction could
 * never match it (owner's review 2026-09-05, blocker 2); no unit test of the cartographer
 * alone can see that, only a test of the sequence can.
 */
#ifndef B1_ORCH_H
#define B1_ORCH_H

#include "b1_carto.h"

enum { B1_STEP_OPENING = 0, B1_STEP_PROBES = 1, B1_STEP_CLOSING = 2, B1_STEP_DONE = 3 };

typedef struct {
    b1_carto carto;
    int step;
    int last_is_baseline;      /* the candidate last proposed by b1_orch_next */
    int last_kind;             /* its cartographer phase (B1_PH_DONE on a baseline) */
    uint32_t candidates;       /* proposals made, baselines included */
} b1_orch;

/* initialise the cartographer FIRST, then the sequence */
void b1_orch_init(b1_orch *o, uint32_t seed, uint32_t budget, const char *token, const char *universe, uint32_t image_lo32);
/* the next candidate: 1 = run it (genome, is_baseline, kind), 0 = the sequence is complete */
int b1_orch_next(b1_orch *o, uint32_t genome[B1_GENOME_WORDS], int *is_baseline, int *kind);
/* the candidate proposed last was SCORED with these tables (a baseline learns nothing) */
void b1_orch_observe(b1_orch *o, uint32_t seq, const uint64_t tables[B1_LUTS]);
/* the candidate proposed last was not scored */
void b1_orch_unobserved(b1_orch *o);
/* the record's `carto` block for the candidate proposed last (after observe): renders the
 * map into `render` (refreshing the commitment) and the block into `out`; 0 on overflow */
size_t b1_orch_record_block(b1_orch *o, uint32_t seq, char *render, size_t render_max, char *out, size_t max);

#endif
