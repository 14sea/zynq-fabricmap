/* p3_derive — the pure half of the standalone application (D1 spec §4).
 *
 * Everything here is arithmetic over words in memory: no register access, no I/O, no
 * board. It is compiled BOTH into the board application and into the host twin
 * (`p3_twin.c`), and the twin is checked against the Python reference over the whole
 * pinned corpus (N = 256, `fixtures/d1_corpus_v1.json`) — review #2's Q7 condition.
 *
 * The board-facing half (AXI, DEVCFG DMA, MMU attributes, UART framing, the loop) is
 * `p3_app.c`; keeping it thin is deliberate — this file is the part that can be proven
 * bit-exact on the host, and it carries every hash the interlock depends on.
 */
#ifndef P3_DERIVE_H
#define P3_DERIVE_H

#include <stddef.h>
#include <stdint.h>

#define P3_FRAME_WORDS 101
#define P3_TARGET_FRAMES 12
#define P3_ENVELOPE_COUNT 3
#define P3_ENVELOPE_FRAMES 5
#define P3_FDRI_WORDS (P3_ENVELOPE_FRAMES * P3_FRAME_WORDS) /* 505 */
#define P3_STREAM_WORDS 534
#define P3_GENOME_BITS 292
#define P3_GENOME_WORDS 10
#define P3_PAGE_WORDS 24
#define P3_PAGE_MAGIC 0x50334944u /* "P3ID" */
#define P3_PAGE_LAYOUT 2u

/* ---------------------------------------------------------------- sha256 (FIPS 180-4) */
typedef struct {
    uint32_t h[8];
    uint64_t len;
    uint8_t buf[64];
    size_t n;
} p3_sha256;

void p3_sha256_init(p3_sha256 *c);
void p3_sha256_update(p3_sha256 *c, const uint8_t *data, size_t n);
void p3_sha256_final(p3_sha256 *c, uint8_t out[32]);
/* words as big-endian bytes — the hash domain zynq-psmap and zynq-fabricmap share */
void p3_sha256_words(p3_sha256 *c, const uint32_t *words, size_t n);
void p3_hex(const uint8_t *in, size_t n, char *out); /* out: 2n+1 bytes */

/* --------------------------------------------------------------------------- CRC-32 */
uint32_t p3_crc32(const uint8_t *data, size_t n); /* IEEE 802.3, as zlib's */

/* ------------------------------------------------------------------------ frame ECC */
uint32_t p3_frame_ecc(const uint32_t frame[P3_FRAME_WORDS]);
void p3_frame_update_ecc(uint32_t frame[P3_FRAME_WORDS]);

/* --------------------------------------------------------------------- genome codec */
/* hex is 80 chars, word 0 first; returns 0 on success, -1 on a malformed genome */
int p3_genome_from_hex(const char *hex, uint32_t words[P3_GENOME_WORDS]);
void p3_genome_to_hex(const uint32_t words[P3_GENOME_WORDS], char out[P3_GENOME_WORDS * 8 + 1]);
int p3_genome_bit(const uint32_t words[P3_GENOME_WORDS], int i);

/* ------------------------------------------------------- derive / build / parse / hash */
/* ISO C before C2x does not implicitly convert `uint32_t (*)[N]` to `const uint32_t (*)[N]`,
 * so passing a mutable frame array to the read-only functions below needs this explicit
 * cast. The `const` in their signatures is kept: it is the statement that they do not
 * modify the candidate. */
#define P3_CFRAMES(f) ((const uint32_t(*)[P3_FRAME_WORDS])(f))

/* the single derive function the signer and the application must agree on, bit for bit */
void p3_derive_frames(const uint32_t genome[P3_GENOME_WORDS],
                      uint32_t frames[P3_TARGET_FRAMES][P3_FRAME_WORDS]);
void p3_build_stream(int envelope,
                     const uint32_t frames[P3_TARGET_FRAMES][P3_FRAME_WORDS],
                     uint32_t out[P3_STREAM_WORDS]);
/* literal grammar walk of a stream read back from DDR; 0 on success, -1 on any deviation */
int p3_parse_stream(const uint32_t in[P3_STREAM_WORDS], uint32_t *far_set_out,
                    uint32_t frames5[P3_ENVELOPE_FRAMES][P3_FRAME_WORDS]);
/* candidate_sha256 domain: FAR-ordered (far big-endian, then the frame's words) */
void p3_frames_hash(const uint32_t frames[P3_TARGET_FRAMES][P3_FRAME_WORDS], uint8_t out[32]);

/* ------------------------------------------------- the pinned readback command stream */
/* zynq-psmap §8a, verbatim: RCFG then FAR then a type-1/type-2 FDRO read, then 32 flush
 * NOOPs; the cleanup leaves the configuration engine desynchronised (no SHUTDOWN, no
 * START, no RCRC — startup transitions are forbidden by this line's rules). */
#define P3_READBACK_CMD_WORDS 43
#define P3_READBACK_WORDS 202 /* pad frame + target frame; only [101:202] is adjudicated */
#define P3_CLEANUP_WORDS 5

void p3_build_readback_command(uint32_t far, uint32_t out[P3_READBACK_CMD_WORDS]);
void p3_build_cleanup_command(uint32_t out[P3_CLEANUP_WORDS]);

/* ------------------------------------------------------------------ nonce and framing */
uint64_t p3_nonce_step(uint64_t x); /* the PL's xorshift, modelled bit-exactly */
size_t p3_base64url(const uint8_t *in, size_t n, char *out);
/* returns the decoded length, or 0 if `in` is not valid base64url */
size_t p3_base64url_decode(const char *in, uint8_t *out, size_t max);

/* ------------------------------------------------------------------- identity page */
typedef struct {
    char token[33];          /* the FULL 128-bit session token, 32 hex chars */
    uint32_t uboot_epoch;
    uint32_t app_image_sha_lo32;
    char carrier_sha256[65]; /* the FULL 256-bit carrier hash */
    uint64_t nonce_seen;
    uint32_t status_seen;
    uint32_t seed;
    uint32_t budget;
    uint32_t flags;
    /* Word 22, previously reserved. HOST-SUPPLIED and merely echoed by the application in
     * app_identity.fclk0_hz_decoded: the application cannot measure it, because the source
     * audit permits exactly one SLCR symbol (the IDCODE read) and that guard is not being
     * weakened to add a field. The host verifies FCLK0 itself before handing over, and
     * that verification — not this echo — is the evidence. The identity's real weight is
     * carried by the values the application does observe: IDCODE, STATUS, key_loaded and
     * the nonce echo. */
    uint32_t fclk0_hz;
} p3_identity_page;

/* 0 on success; -1 on magic/layout/checksum refusal */
int p3_parse_identity_page(const uint32_t words[P3_PAGE_WORDS], p3_identity_page *out);

#endif /* P3_DERIVE_H */
