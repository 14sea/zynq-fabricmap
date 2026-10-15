/* b3_online_view — the O arm's initializer and online view. See b3_online_view.h. */
#include "b3_online_view.h"
#include "p3_data.h"

#include <string.h>

/* b2_search_init's engine state, rebuilt from B2's public functions — with the O arm's code and
 * WITHOUT build_view (which reads the compiled self-map): the view stays empty. */
void b3_online_init(b2_search *s, uint32_t landscape_seed, uint32_t operator_seed, uint32_t budget,
                    const uint64_t base[B2_LUTS])
{
    int i, k;
    memset(s, 0, sizeof(*s));                    /* col_keys_n = 0, every col_n = 0: the empty view */
    s->arm = B3_ARM_ONLINE;
    s->landscape_seed = landscape_seed;
    s->operator_seed = operator_seed;
    s->budget = budget;
    b2_universe_mask(s->masks);
    b2_target(landscape_seed, s->masks, s->target);
    b2_rng_init(&s->rng, operator_seed);
    s->base_fit = b2_f1_train(base, s->target);
    s->best = s->base_fit;
    for (i = 0; i < B2_MU; i++) {
        for (k = 0; k < B2_LUTS; k++)
            s->pop[i].tables[k] = base[k];
        s->pop[i].fit = s->base_fit;
        s->pop[i].born = (uint32_t)i;
    }
    s->born = (uint32_t)B2_MU;
    s->champion_holdout = -1;
}

static void view_clear(b2_search *s)
{
    memset(s->col_keys, 0, sizeof(s->col_keys));
    memset(s->col_bits, 0, sizeof(s->col_bits));
    memset(s->col_n, 0, sizeof(s->col_n));
    s->col_keys_n = 0;
}

int b3_online_view_rebuild(b2_search *s, const b3_carto *c)
{
    uint8_t is_train[B2_VECTORS];
    int i, v;
    memset(is_train, 0, sizeof(is_train));
    for (i = 0; i < B2_TRAIN_COUNT; i++)
        is_train[B2_TRAIN_VECTORS[i]] = 1u;
    view_clear(s);
    for (i = 0; i < B3_CARTO_N; i++) {           /* address order: each column's bits come out ascending */
        int pos = b3_carto_decoded_position(c, i);
        if (pos == B3_CARTO_NO_POSITION)
            continue;
        v = pos % B3_CARTO_VECTORS;
        if (!is_train[v])
            continue;
        if (s->col_n[v] >= B2_LUTS) {
            view_clear(s);
            return -1;
        }
        s->col_bits[v][s->col_n[v]++] = (uint16_t)i;
    }
    for (v = 0; v < B2_VECTORS; v++)             /* the draw list: the non-empty train columns, ascending */
        if (s->col_n[v] != 0u)
            s->col_keys[s->col_keys_n++] = (uint8_t)v;
    return 0;
}
