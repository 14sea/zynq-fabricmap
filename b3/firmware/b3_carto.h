/* b3_carto — the specimen cartographer, the C twin of b3/host/b3_carto.py (SpecimenCarto v1.1;
 * docs/b3_architecture.md v0.3 §7, Decision E1). B3 lifecycle 2, image stage 1.
 *
 * A specimen is (moved addresses M, toggled positions D). |M| = 1 decodes directly; |M| > 1 narrows
 * each pending address's candidate set by intersection, then a global closure decodes every address
 * whose candidates minus the taken positions are exactly one. EVERY check runs on a COPY of the
 * state and the copy is committed only if the whole specimen is consistent; otherwise the anomaly
 * count is incremented and NOTHING else changes. The map version bumps once per specimen that decodes
 * at least one address.
 *
 * The state commitment text — the projection the board commits to on every O-arm search record —
 * is rendered by b3_carto_state_render, byte for byte the Python `state_text()`:
 *   <carto_version>|<version>|<anomalies>|<decoded i:k:v; sorted by i>|<candidates i:k.v,k.v; sorted>
 * rendered through an emitter so that the image can hash it without a buffer (in the image's compile branch,
 * B3_EMIT_SHA, the emitter is the SHA-256 sink called directly: see b3_carto_state_render).
 *
 * Freestanding C99: no allocation, no stdio, no libc but memcpy / memset / strlen (the board BSP has
 * them). The state is ~15 KB; b3_carto_observe runs every check on a COPY of it, and that copy is a
 * CALLER-OWNED scratch (a static / BSS object in the image, never a stack frame: the BSP stack is
 * 0x4000 bytes, firmware/b2/bsp/lscript.ld, and a 15 KB frame would leave nothing for the callers —
 * the owner's P1 on 4817662). Every function here keeps its frame under 1 KB (held by the tests with
 * -fstack-usage on the host and on the pinned ARM toolchain).
 * Positions are encoded as 64 * LUT + vector (0 .. 383), as the Python (k, v) order sorts.
 * The closure iterates the candidate addresses in the order they FIRST became pending, exactly as
 * the Python dict does, so the newly-decoded list comes out in the same order and the image's
 * ledger `decoded` field reproduces the prediction's entry for entry.
 */
#ifndef B3_CARTO_H
#define B3_CARTO_H

#include <stddef.h>
#include <stdint.h>

#define B3_CARTO_VERSION "specimen-carto-v1.1"
#define B3_CARTO_N 292                       /* genome addresses (b1_carto.N) */
#define B3_CARTO_LUTS 6
#define B3_CARTO_VECTORS 64
#define B3_CARTO_POSITIONS (B3_CARTO_LUTS * B3_CARTO_VECTORS)   /* 384 */
#define B3_CARTO_WORDS B3_CARTO_LUTS         /* a position set: one uint64_t per LUT, bit = vector */
#define B3_CARTO_NO_POSITION (-1)
#define B3_CARTO_REFUSED (-1)                /* b3_carto_observe: the specimen was refused (counted) */
#define B3_CARTO_BAD_CALL (-2)               /* b3_carto_observe: scratch is NULL or aliases the state; nothing done */

typedef struct {
    uint64_t cand[B3_CARTO_N][B3_CARTO_WORDS];  /* candidate position set per address (valid when has_cand) */
    uint8_t has_cand[B3_CARTO_N];               /* address i has ever been pending (the Python dict key) */
    uint16_t order[B3_CARTO_N];                 /* candidate addresses in FIRST-pending order (the dict's order) */
    uint16_t n_order;
    int16_t decoded[B3_CARTO_N];                /* position of a decoded address, else B3_CARTO_NO_POSITION */
    uint64_t taken[B3_CARTO_WORDS];             /* positions owned by decoded addresses */
    uint32_t version;
    uint32_t anomalies;
} b3_carto;

/* The SHA-256 sink (defined in b3_record.c): hands each byte range to p3_sha256_update((p3_sha256 *)ctx, ...);
 * `ctx` is a p3_sha256 set up by p3_sha256_init. */
void b3_sha_sink(void *ctx, const char *bytes, size_t n);

#ifndef B3_EMIT_SHA
/* The emitter a renderer writes through: called with successive byte ranges of the text. */
typedef void (*b3_carto_emit)(void *ctx, const char *bytes, size_t n);
#endif

void b3_carto_init(b3_carto *c);

/* Observe one specimen. `scratch`: a caller-owned b3_carto the checks run on (its contents are
 * overwritten; it must not be NULL and must not be `c` itself — otherwise B3_CARTO_BAD_CALL is
 * returned and nothing is done or counted). `moved`: the moved addresses (any order, as the move
 * produced them); `delta`: the toggled positions as 64 * LUT + vector (any order). On a CONSISTENT
 * specimen the state is committed, the addresses newly decoded by it are written to `newly` (at most
 * `newly_cap`, in the Python's order) and their count is returned (0 .. B3_CARTO_N). On a refusal — a
 * malformed intervention (empty, a duplicate, an address out of range), a malformed delta (a
 * duplicate, a position out of range), |delta| != |moved|, a decoded moved address whose position did
 * not toggle, a toggled position owned by a decoded address that was not moved, an empty
 * intersection, or a closure conflict — the anomaly count is incremented, nothing else changes, and
 * B3_CARTO_REFUSED is returned. `newly` may be NULL with newly_cap 0 (the count is still returned). */
int b3_carto_observe(b3_carto *c, b3_carto *scratch, const uint16_t *moved, int n_moved, const uint16_t *delta, int n_delta,
                     uint16_t *newly, int newly_cap);

/* The position a decoded address holds, or B3_CARTO_NO_POSITION. */
int b3_carto_decoded_position(const b3_carto *c, int address);

/* The number of decoded addresses. */
int b3_carto_decoded_count(const b3_carto *c);

#ifdef B3_EMIT_SHA
/* The image's compile branch (bsp/build.sh compiles every unit with -DB3_EMIT_SHA; the owner's B-2 ruling of
 * 2026-10-09): the renderers call b3_sha_sink DIRECTLY — no emitter function pointer is stored or passed — with the
 * same byte ranges, call for call, as the emitter branch below (b3/tests/test_b3_record_twin.py runs both).
 * Render the commitment text into the hash `ctx`. Returns the number of bytes rendered. */
size_t b3_carto_state_render(const b3_carto *c, void *ctx);
#else
/* Render the commitment text through `emit`. Returns the number of bytes rendered. */
size_t b3_carto_state_render(const b3_carto *c, b3_carto_emit emit, void *ctx);
#endif

#endif
