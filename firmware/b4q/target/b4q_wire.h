/* b4q_wire — the board application's console framing as a PURE unit (no MMIO, no board dependency), so that the host tests
 * compile this source, drive it, and hold the bytes the board will emit to the Python twin (host/b4q_wire.py) — the B1 rule
 * (firmware/b1/b1_wire.h): everything provable on the host lives outside the HAL.
 *
 *   "B4Q1 <TYPE> <seq> <token32hex> <payload> <crc32hex8>\n"
 * the CRC (IEEE 802.3, zlib's) covers everything before the final space; `payload` is base64url (padded, p3's alphabet) of
 * the plain bytes, or "-" when the line carries none; `token` is the session token of the identity page, 32 zeros before the
 * page is read. Board -> host types: IDENT, HB, SIGNREQ, EV, RESULT, NACK, END. Host -> board: TX, QUIT, SIGNREPLY.
 * The CRC and base64url functions are the instrument's p3_derive.c functions byte for byte (firmware/b4q/IMPORT.json). */
#ifndef B4Q_WIRE_H
#define B4Q_WIRE_H

#include <stddef.h>
#include <stdint.h>

#define B4Q_WIRE_MAGIC "B4Q1"
#define B4Q_WIRE_TOKEN_HEX 32
#define B4Q_WIRE_ZERO_TOKEN "00000000000000000000000000000000"

uint32_t b4q_crc32(const uint8_t *data, size_t n);                 /* verbatim p3_crc32 */
size_t b4q_base64url(const uint8_t *in, size_t n, char *out);       /* verbatim p3_base64url */
size_t b4q_base64url_decode(const char *in, uint8_t *out, size_t max);   /* verbatim p3_base64url_decode */

/* the framed line (with its '\n'); `payload_b64` already encoded or "-"; the length, or 0 when it would not fit */
size_t b4q_wire_line(const char *type, uint32_t seq, const char *token, const char *payload_b64, char *out, size_t max);
/* encode `plain` (n bytes) and frame it in one call; 0 on overflow */
size_t b4q_wire_frame(const char *type, uint32_t seq, const char *token, const uint8_t *plain, size_t n, char *out, size_t max);

typedef struct {
    char type[16];
    uint32_t seq;
    char token[B4Q_WIRE_TOKEN_HEX + 1];
    const char *payload_b64;    /* points into the caller's line ("-" for none) */
} b4q_wire_frame_t;

/* parse one line IN PLACE (the line is modified); 0 ok; -1 bad CRC; -2 not a B4Q1 line / wrong field count; -3 the token is
 * not `want_token` (when want_token is non-NULL) */
int b4q_wire_parse(char *line, const char *want_token, b4q_wire_frame_t *out);
/* decode the parsed payload into `out` as a NUL-terminated string; the length, 0 for "-" (out[0] = 0), (size_t)-1 when invalid */
size_t b4q_wire_payload(const b4q_wire_frame_t *f, char *out, size_t max);

/* ---------------------------------------------------------------- the identity page (24 words at B4Q_PAGE_ADDR) ----- */
#define B4Q_PAGE_WORDS 24
#define B4Q_PAGE_MAGIC 0x42345149u   /* "B4QI" */
#define B4Q_PAGE_LAYOUT 1u
#define B4Q_PAGE_FLAG_WATCHDOG 0x2u  /* flags.bit1: the application arms the private watchdog (B1's D-s1 bit) */

typedef struct {
    char token[B4Q_WIRE_TOKEN_HEX + 1];
    uint32_t uboot_epoch;
    uint32_t app_image_sha_lo32;
    char carrier_sha256[65];
    uint64_t nonce_seen;
    uint32_t status_seen;
    uint32_t flags;
} b4q_page;

/* DERIVED from p3_parse_identity_page: the same magic / layout / xor-checksum discipline on the B4Q layout; 0 ok, -1 refused */
int b4q_parse_page(const uint32_t words[B4Q_PAGE_WORDS], b4q_page *out);

#endif /* B4Q_WIRE_H */
