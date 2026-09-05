/* b1_carto — the on-board cartographer (stage B1), a pure unit.
 *
 * Compiled BOTH into the board application (b1_app.c) and into the host twin (b1_twin.c),
 * and the twin is checked against the Python reference (host/b1_carto.py) probe by probe
 * over simulated fabrics — the same discipline the instrument's search unit and its twin used.
 *
 * What it knows: the universe is N = B1_N addresses, indexed 0..N-1 in the canonical genome
 * bit order (P3_WHITELIST), all of one coarse safety class (content bits). It does NOT
 * know, and this unit must never be linked with, any LUT key, INIT index, polarity or
 * group table: b1_data.h carries the whitelist and the base frames only, and
 * tests/test_b1_leakage.py scans the sources and the built image for the tables that
 * p3_data.h used to carry.
 *
 * What it observes: after every SCORED probe, the PL's functional readout — six 64-bit
 * truth tables, table k bit v = the output of LUT k for input vector v — as the application
 * read it from the READOUT registers. A position (k, v) is "lit" when that bit is 1; the
 * base (no bits set) reads all-zero.
 *
 * What it does, deterministically from (seed, budget, the observations):
 *   phase A  CODE probes. Address i carries the code c(i) = i + 1 (1..N, never zero);
 *            probe p (p = 0..B1_CODE_BITS-1) sets every address whose code has bit p set.
 *            A position lit in exactly the probes of a code decodes to that address — one
 *            fabric sweep per code bit instead of one per address (group testing). The
 *            decode is provisional (confidence 1). A probe whose lit count differs from
 *            its set count, or a position whose code is out of range, is recorded as an
 *            anomaly and lowers nothing silently.
 *   phase B  CONFIRM probes. Single-address probes, in an order the RNG draws (the board's
 *            own choice), for every address whose decode is provisional — first the
 *            addresses that decoded to NOTHING (they are probed alone before being called
 *            "no observable effect"). A single probe that lights exactly the decoded
 *            position raises the entry to confidence 2; anything else is a contradiction
 *            (confidence 0, kept with its evidence).
 *   phase C  INTERACTION probes. Pairs of confirmed addresses drawn by the RNG, half within
 *            one decoded LUT and half across two: the readout must be the union of the two
 *            singles. A deviation is an interaction edge, recorded with the observed
 *            tables; agreement is a "none" edge with its evidence.
 * The budget bounds the total; phase B and C are cut where it runs out, and every entry
 * says what evidence it rests on. The map hash is sha256 over the canonical rendering
 * (host/b1_carto.py renders the same bytes) and is carried in every record's `carto`
 * block so the host can check the board's commitment against its own reconstruction.
 */
#ifndef B1_CARTO_H
#define B1_CARTO_H

#include <stddef.h>
#include <stdint.h>

#define B1_CARTO_VERSION "carto-v1"
#define B1_N 292
#define B1_LUTS 6
#define B1_CODE_BITS 9                 /* 2^9 = 512 > N + 1 */
#define B1_GENOME_WORDS 10
#define B1_PAIRS_MAX 32                /* phase C pairs, half same-LUT, half cross-LUT */

typedef struct { uint64_t x; } b1_rng;

/* one address's belief */
typedef struct {
    int8_t lut;                        /* 0..5, or -1 = none decoded */
    int8_t init;                       /* 0..63, or -1 */
    uint8_t confidence;                /* 0 contradiction, 1 code-decoded, 2 confirmed by a single */
    uint8_t state;                     /* B1_ST_* */
    uint8_t observed;                  /* 1 = the transition base 0 -> set 1 was seen lit at (lut, init) */
    uint16_t code_mask;                /* which code probes (bit p) lit the decoded position; the record seqs are code_seq[] */
    uint16_t confirm_seq;              /* the single-address probe's record seq, 0 = none */
} b1_entry;

enum { B1_ST_UNKNOWN = 0, B1_ST_DECODED = 1, B1_ST_CONFIRMED = 2, B1_ST_NO_EFFECT = 3, B1_ST_CONTRADICTION = 4 };
enum { B1_PH_CODE = 0, B1_PH_CONFIRM = 1, B1_PH_PAIR = 2, B1_PH_DONE = 3 };

typedef struct {
    uint16_t a, b;                     /* addresses */
    uint8_t kind;                      /* 0 same-LUT, 1 cross-LUT */
    uint8_t result;                    /* 0 pending, 1 union (no interaction), 2 deviation */
    uint16_t seq;
} b1_pair;

typedef struct {
    uint32_t seed, budget;
    b1_rng rng;
    int phase;
    uint32_t probes_issued;            /* proposals made */
    uint32_t seq_last;                 /* the seq the application assigned to the last proposal */
    /* phase A */
    int code_p;                        /* next code bit to probe */
    uint64_t lit[B1_CODE_BITS][B1_LUTS];   /* readout per code probe */
    uint32_t set_count[B1_CODE_BITS];
    uint32_t lit_count[B1_CODE_BITS];
    uint16_t code_seq[B1_CODE_BITS];
    uint8_t decoded;                   /* phase A decode done */
    /* the map */
    b1_entry e[B1_N];
    /* phase B */
    uint16_t order[B1_N];              /* RNG-drawn confirmation order */
    int order_n, order_i;
    int16_t pending;                   /* address under single probe, or -1 */
    /* phase C */
    b1_pair pairs[B1_PAIRS_MAX];
    int pairs_n, pairs_i;
    int16_t pending_pair;
    /* anomalies */
    uint32_t anomalies;
    /* binding (b1_carto_bind): the map names the session it was built in */
    char token[33];
    char universe[65];
    uint32_t image_lo32;
    uint8_t content_sha256[32];        /* over the "content" object: the predictable part */
    char content_sha256_hex[65];
    uint8_t map_sha256[32];            /* over the whole rendering (binding + content) */
    char map_sha256_hex[65];
} b1_carto;

/* the RNG: l6_operators.Rng exactly (xorshift64, warm-up 4, rejection sampling) */
void b1_rng_init(b1_rng *r, uint32_t seed32);
uint32_t b1_rng_next32(b1_rng *r);
uint32_t b1_rng_uniform(b1_rng *r, uint32_t n);

void b1_carto_init(b1_carto *c, uint32_t seed, uint32_t budget);
/* the session the map is built in: token (32 hex), universe digest (64 hex), image sha low 32 bits */
void b1_carto_bind(b1_carto *c, const char *token, const char *universe, uint32_t image_lo32);
/* propose the next probe as a genome (0 = none: done, or budget exhausted); *kind_out is the phase */
int b1_carto_next(b1_carto *c, uint32_t genome[B1_GENOME_WORDS], int *kind_out);
/* the application assigned `seq` to the last proposal and observed these tables */
void b1_carto_observe(b1_carto *c, uint32_t seq, const uint64_t tables[B1_LUTS]);
/* the last proposal was not scored (a stop): nothing is learned, the phase does not advance */
void b1_carto_unobserved(b1_carto *c);
/* canonical map rendering, returns bytes written (0 on overflow); also refreshes the hash */
size_t b1_carto_render(b1_carto *c, char *out, size_t max);
/* the `carto` evidence block for the record `seq` (the entries changed by this observation) */
size_t b1_carto_record_json(const b1_carto *c, int kind, uint32_t seq, const uint16_t *changed, int changed_n,
                            char *out, size_t max);
/* the entries changed by the last observation (filled by observe) */
int b1_carto_changed(const b1_carto *c, uint16_t *out, int max);

#endif
