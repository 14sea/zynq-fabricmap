/* b1_orch — the session orchestrator (stage B1), a pure unit. See b1_orch.h. */
#include "b1_orch.h"

#include <string.h>

void b1_orch_init(b1_orch *o, uint32_t seed, uint32_t budget, const char *token, const char *universe, uint32_t image_lo32)
{
    memset(o, 0, sizeof(*o));
    b1_carto_init(&o->carto, seed, budget);   /* BEFORE the opening baseline: its block commits to this state */
    b1_carto_bind(&o->carto, token, universe, image_lo32);
    o->step = B1_STEP_OPENING;
    o->last_is_baseline = 0;
    o->last_kind = B1_PH_DONE;
}

int b1_orch_next(b1_orch *o, uint32_t genome[B1_GENOME_WORDS], int *is_baseline, int *kind)
{
    memset(genome, 0, sizeof(uint32_t) * B1_GENOME_WORDS);
    if (o->step == B1_STEP_OPENING) {
        o->step = B1_STEP_PROBES;
        o->last_is_baseline = 1;
        o->last_kind = B1_PH_DONE;
        o->candidates++;
        *is_baseline = 1;
        *kind = B1_PH_DONE;
        return 1;                                   /* the blank genome IS the pinned base */
    }
    if (o->step == B1_STEP_PROBES) {
        int k;
        if (b1_carto_next(&o->carto, genome, &k)) {
            o->last_is_baseline = 0;
            o->last_kind = k;
            o->candidates++;
            *is_baseline = 0;
            *kind = k;
            return 1;
        }
        o->step = B1_STEP_CLOSING;
        memset(genome, 0, sizeof(uint32_t) * B1_GENOME_WORDS);
    }
    if (o->step == B1_STEP_CLOSING) {
        o->step = B1_STEP_DONE;
        o->last_is_baseline = 1;
        o->last_kind = B1_PH_DONE;
        o->candidates++;
        *is_baseline = 1;
        *kind = B1_PH_DONE;
        return 1;                                   /* closing baseline = restore + score */
    }
    return 0;
}

void b1_orch_observe(b1_orch *o, uint32_t seq, const uint64_t tables[B1_LUTS])
{
    if (!o->last_is_baseline)
        b1_carto_observe(&o->carto, seq, tables);
}

void b1_orch_unobserved(b1_orch *o)
{
    if (!o->last_is_baseline)
        b1_carto_unobserved(&o->carto);
}

size_t b1_orch_record_block(b1_orch *o, uint32_t seq, char *render, size_t render_max, char *out, size_t max)
{
    uint16_t changed[B1_N + 4];
    int n = o->last_is_baseline ? 0 : b1_carto_changed(&o->carto, changed, (int)(sizeof(changed) / sizeof(changed[0])));
    if (n > 8)
        n = 8;                                      /* the record carries a sample; the hash carries the map */
    if (b1_carto_render(&o->carto, render, render_max) == 0u)
        return 0u;
    return b1_carto_record_json(&o->carto, o->last_is_baseline ? B1_PH_DONE : o->last_kind, seq, changed, n, out, max);
}
