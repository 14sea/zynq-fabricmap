/* b4q_derive — the pure half of the B4Q executing side, DERIVED from firmware/b1/p3_derive.{h,c} (the instrument's
 * D1 derive unit, zynq-psoracle 689dde1 -> firmware/b1 -> here; firmware/b4q/IMPORT.json names the base and the digests).
 *
 * What is VERBATIM (held function by function by tests/test_b4q_derive.py): sha256, hex, CRC-32, the frame ECC, the stream
 * builder and its literal parser, the FAR-ordered frames hash, the pinned readback and cleanup command streams, the nonce
 * step. What CHANGED: the data (b4q_data.h — eight target frames in two envelopes of the column 0x00400a00, the 21
 * certified addresses of SLICE_X2Y25) and the genome codec (21 bits in one word, 8 hex chars). What is REMOVED: the
 * identity page and base64url (the B1 console protocol's; B4Q's host transport carries its own lines).
 *
 * Everything here is arithmetic over words in memory: no register access, no I/O, no board. It is compiled into the
 * executing-side program (b4q_tx.c) and into the host twin (b4q_derive_twin.c), which tests/test_b4q_derive.py holds to
 * the Python twin host/b4q_frames.py over a corpus of genomes.
 */
#ifndef B4Q_DERIVE_H
#define B4Q_DERIVE_H

#include <stddef.h>
#include <stdint.h>

#define P3_FRAME_WORDS 101
#define P3_TARGET_FRAMES 8  /* B4: the write set (b4q_data.h) */
#define P3_ENVELOPE_COUNT 2
#define P3_ENVELOPE_FRAMES 5
#define P3_FDRI_WORDS (P3_ENVELOPE_FRAMES * P3_FRAME_WORDS) /* 505 */
#define P3_STREAM_WORDS 534
#define P3_GENOME_BITS 21
#define P3_GENOME_WORDS 1

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
/* hex is 8 chars (one word, bits 21..31 zero); returns 0 on success, -1 on a malformed genome */
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

/* ------------------------------------------------------------------ nonce */
uint64_t p3_nonce_step(uint64_t x); /* the PL's xorshift, modelled bit-exactly */

#endif /* B4Q_DERIVE_H */
