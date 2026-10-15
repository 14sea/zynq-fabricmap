/* b3_record — the O arm's record commitment, its specimen-ledger entry and its `search` record block.
 * B3 lifecycle 2, image stage 2 (docs/b3_architecture.md v0.3 §7–§8, Decision E1).
 *
 * The C twin of three functions of b3/host/b3_online_arm.py:
 *
 *   the combined commitment   state_sha256(search_state_text(...), carto.state_text())
 *       = sha256( <B2 search state text> "|" <cartographer state text> ). The search text is byte for
 *       byte what B2's b2_search_state_hex hashes — "b2-es-v1|arm|lseed|oseed|budget|evals|gen|best|"
 *       then "fit:born:genomehex;" per member of the population — rendered here from the PUBLIC b2_search
 *       struct (b2_search.c is an unchanged copy and does not expose the text); the cartographer's text
 *       is b3_carto_state_render. Both stream through an emitter, so the image hashes them without a
 *       buffer, and the twin prints the very bytes the hash consumed.
 *
 *   the ledger entry          ledger_entry(...) — specimen_ledger 1.1.0, eleven fields — as compact JSON
 *       with sorted keys (json.dumps(entry, sort_keys=True, separators=(",", ":"))).
 *
 *   the record block          record_block(...) — B2's `search` block with arm "O", state_sha256 = the
 *       combined commitment and, on a search record, the `ledger` sub-block (its sorted position is
 *       between landscape_seed and move); the champion's holdout block has no ledger key at all.
 *
 * Freestanding C99: no allocation, no stdio (integers are formatted here). Every output buffer is the
 * CALLER's; every frame is small (held by the tests with -fstack-usage on the host and on the pinned ARM
 * toolchain). A render that would not fit returns 0 (the caller treats it as a PROTOCOL-class failure).
 */
#ifndef B3_RECORD_H
#define B3_RECORD_H

#include <stddef.h>
#include <stdint.h>

#include "b2_search.h"
#include "b3_carto.h"

#ifdef B3_EMIT_SHA
/* The image's compile branch (b3_carto.h): both renderers feed the hash `ctx` through b3_sha_sink, called directly. */
size_t b3_search_state_render(const b2_search *s, void *ctx);
size_t b3_commitment_render(const b2_search *s, const b3_carto *c, void *ctx);
#else
/* The emitter the renderers write through (the same shape as b3_carto_emit). */
typedef b3_carto_emit b3_emit;

/* The B2 search state text of `s`, through `emit`; returns the bytes rendered. */
size_t b3_search_state_render(const b2_search *s, b3_emit emit, void *ctx);

/* The whole commitment input: search text, "|", cartographer text; returns the bytes rendered. */
size_t b3_commitment_render(const b2_search *s, const b3_carto *c, b3_emit emit, void *ctx);
#endif

/* sha256 of b3_commitment_render (through b3_sha_sink), as 64 lower-case hex digits and a NUL. */
void b3_state_hex(const b2_search *s, const b3_carto *c, char out[65]);

/* The toggled positions between two readouts, as 64 * LUT + vector in (LUT, vector) order — Python's
 * positions_of([child[k] ^ parent[k] ...]). `out` holds B3_CARTO_POSITIONS entries; returns the count. */
int b3_delta_positions(const uint64_t parent[B2_LUTS], const uint64_t child[B2_LUTS], uint16_t *out);

/* One specimen_ledger 1.1.0 entry. The arrays are the caller's; `carto` supplies the decoded positions of
 * the `newly` addresses (a decoded address never moves, so any later state gives the same values). */
typedef struct {
    uint32_t seq, map_version, map_version_after, anomalies, parent_born;
    int32_t fitness;
    int kind;                                   /* B2_MOVE_RANDOM | B2_MOVE_COLUMN */
    const uint16_t *bits;                       /* the intervention, as the move produced it */
    int n_bits;
    const uint16_t *delta;                      /* the behaviour delta, 64 * LUT + vector, in positions_of order */
    int n_delta;
    const uint16_t *newly;                      /* the addresses the specimen decoded, in the cartographer's order */
    int n_newly;
    const b3_carto *carto;
} b3_ledger_entry;

/* The entry as compact sorted-key JSON into out[max] (NUL-terminated); returns the length, 0 if it would
 * not fit or the entry is malformed — outside the specimen_ledger 1.1.0 schema or the cartographer's version
 * rule (every count is checked against its bound before any array is read; see b3_record.c ledger_valid). */
size_t b3_ledger_json(const b3_ledger_entry *e, char *out, size_t max);

/* The O arm's record block for the observation just made (`ledger` = its entry, `holdout` < 0) or for the
 * champion's holdout evaluation (`holdout` >= 0, `ledger` NULL), into out[max] (NUL-terminated). Refused (0):
 * a search block without a ledger entry, or a holdout block with one; a search block whose entry is not the
 * observation just made — seq, eval_n and s->evals, parent_born, move kind, fitness and bits must equal the
 * search's last observation, and `carto` must be `c` with the same version and anomaly count — or made when
 * no observation is fresh (a proposal or the holdout in flight, the holdout done); a holdout block unless the
 * champion's evaluation is done, eval_n == s->evals and holdout == s->champion_holdout. Returns the length
 * or 0. */
size_t b3_record_json(const b2_search *s, const b3_carto *c, int pair, uint32_t eval_n, int32_t holdout,
                      const b3_ledger_entry *ledger, char *out, size_t max);

#endif
