/* b3_online_view — the O arm's engine initializer and its online map view, on B2's engine.
 * B3 lifecycle 2, image stage 2 (docs/b3_architecture.md v0.3 §7, Decision E1).
 *
 * The O arm runs B2's (mu + lambda) engine and B2's map-guided operator UNCHANGED (b2_search.c is a
 * byte-for-byte copy of firmware/b2/b2_search.c); what differs is the map the operator reads. B2's
 * `col_keys` / `col_bits` / `col_n` are, for the O arm, the ONLINE view: the relations the specimen
 * cartographer (b3_carto) has decoded so far, restricted to the train columns — the C twin of the
 * Python `SpecimenCarto.map_view(train)` that b3/host/b3_online_arm.run_online hands to
 * `b2_search.map_guided_move`.
 *
 * E1 (no frozen-map leakage): the O arm must never see the compiled B1 self-map. B2's own initializer,
 * b2_search_init, unconditionally builds the view from p3_data.h `B2_MAP_INIT`; clearing it afterwards
 * would still have read it. So the O arm has its OWN initializer, b3_online_init, which builds the same
 * engine state from B2's public functions (the universe mask, the public target rule, the RNG, F1) and
 * starts with an EMPTY view; this unit never names B2_MAP_INIT and never calls b2_search_init. The R and
 * F arms keep b2_search_init.
 *
 * Freestanding C99: no allocation, no stdio; every frame is small (held by the tests with -fstack-usage
 * on the host and on the pinned ARM toolchain).
 */
#ifndef B3_ONLINE_VIEW_H
#define B3_ONLINE_VIEW_H

#include <stdint.h>

#include "b2_search.h"
#include "b3_carto.h"

#define B3_ARM_ONLINE 2                      /* the arm code in the search commitment text (b3_online_arm.ARM_CODE) */

/* The O arm of one pair: B2's engine state for (landscape seed, operator seed, budget) from the
 * MEASURED opening-baseline readout `base`, with the arm code B3_ARM_ONLINE and an empty map view
 * (col_keys_n == 0, every col_n == 0): at evaluation 0 the operator knows nothing, so every move is
 * random-safe until the cartographer decodes a train relation. */
void b3_online_init(b2_search *s, uint32_t landscape_seed, uint32_t operator_seed, uint32_t budget,
                    const uint64_t base[B2_LUTS]);

/* Rebuild the operator's view from the cartographer's decoded state: for every decoded address, in
 * address order, whose position's vector is a TRAIN column, the address is placed in that column;
 * the column keys are the non-empty train columns in ascending order and each column's bits are
 * ascending — Python's map_view(). Returns 0, or -1 (the view is then left EMPTY) if a column would
 * hold more than B2_LUTS addresses, which a consistent cartographer cannot produce. */
int b3_online_view_rebuild(b2_search *s, const b3_carto *c);

#endif
