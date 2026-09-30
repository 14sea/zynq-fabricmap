/* p3_derive — see p3_derive.h. Pure arithmetic; no board, no I/O, no allocation. */

#include "p3_derive.h"
#include "p3_data.h"

#include <string.h>

/* ------------------------------------------------------------------ sha256 */

static const uint32_t K256[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u,
    0x923f82a4u, 0xab1c5ed5u, 0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u, 0xe49b69c1u, 0xefbe4786u,
    0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u,
    0x06ca6351u, 0x14292967u, 0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u, 0xa2bfe8a1u, 0xa81a664bu,
    0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au,
    0x5b9cca4fu, 0x682e6ff3u, 0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u};

static uint32_t ror32(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

static void sha256_block(uint32_t h[8], const uint8_t p[64])
{
    uint32_t w[64], a, b, c, d, e, f, g, hh, t1, t2;
    int i;
    for (i = 0; i < 16; i++)
        w[i] = ((uint32_t)p[4 * i] << 24) | ((uint32_t)p[4 * i + 1] << 16) |
               ((uint32_t)p[4 * i + 2] << 8) | (uint32_t)p[4 * i + 3];
    for (i = 16; i < 64; i++) {
        uint32_t s0 = ror32(w[i - 15], 7) ^ ror32(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = ror32(w[i - 2], 17) ^ ror32(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    a = h[0]; b = h[1]; c = h[2]; d = h[3];
    e = h[4]; f = h[5]; g = h[6]; hh = h[7];
    for (i = 0; i < 64; i++) {
        t1 = hh + (ror32(e, 6) ^ ror32(e, 11) ^ ror32(e, 25)) + ((e & f) ^ (~e & g)) + K256[i] + w[i];
        t2 = (ror32(a, 2) ^ ror32(a, 13) ^ ror32(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
        hh = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d;
    h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
}

void p3_sha256_init(p3_sha256 *c)
{
    static const uint32_t iv[8] = {0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
                                   0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u};
    memcpy(c->h, iv, sizeof(iv));
    c->len = 0;
    c->n = 0;
}

void p3_sha256_update(p3_sha256 *c, const uint8_t *data, size_t n)
{
    c->len += (uint64_t)n;
    while (n) {
        size_t take = 64 - c->n;
        if (take > n)
            take = n;
        memcpy(c->buf + c->n, data, take);
        c->n += take;
        data += take;
        n -= take;
        if (c->n == 64) {
            sha256_block(c->h, c->buf);
            c->n = 0;
        }
    }
}

void p3_sha256_final(p3_sha256 *c, uint8_t out[32])
{
    uint64_t bits = c->len * 8u;
    uint8_t pad = 0x80;
    uint8_t lenbe[8];
    int i;
    p3_sha256_update(c, &pad, 1);
    pad = 0;
    while (c->n != 56)
        p3_sha256_update(c, &pad, 1);
    for (i = 0; i < 8; i++)
        lenbe[i] = (uint8_t)(bits >> (56 - 8 * i));
    p3_sha256_update(c, lenbe, 8);
    for (i = 0; i < 8; i++) {
        out[4 * i] = (uint8_t)(c->h[i] >> 24);
        out[4 * i + 1] = (uint8_t)(c->h[i] >> 16);
        out[4 * i + 2] = (uint8_t)(c->h[i] >> 8);
        out[4 * i + 3] = (uint8_t)c->h[i];
    }
}

void p3_sha256_words(p3_sha256 *c, const uint32_t *words, size_t n)
{
    size_t i;
    for (i = 0; i < n; i++) {
        uint8_t be[4];
        be[0] = (uint8_t)(words[i] >> 24);
        be[1] = (uint8_t)(words[i] >> 16);
        be[2] = (uint8_t)(words[i] >> 8);
        be[3] = (uint8_t)words[i];
        p3_sha256_update(c, be, 4);
    }
}

void p3_hex(const uint8_t *in, size_t n, char *out)
{
    static const char digits[] = "0123456789abcdef";
    size_t i;
    for (i = 0; i < n; i++) {
        out[2 * i] = digits[in[i] >> 4];
        out[2 * i + 1] = digits[in[i] & 15];
    }
    out[2 * n] = 0;
}

/* -------------------------------------------------------------------- CRC-32 */

uint32_t p3_crc32(const uint8_t *data, size_t n)
{
    uint32_t crc = 0xFFFFFFFFu;
    size_t i;
    int k;
    for (i = 0; i < n; i++) {
        crc ^= data[i];
        for (k = 0; k < 8; k++)
            crc = (crc >> 1) ^ (0xEDB88320u & (uint32_t)(-(int32_t)(crc & 1)));
    }
    return crc ^ 0xFFFFFFFFu;
}

/* ----------------------------------------------------------------- frame ECC
 * Port of the imported frame_ecc.py, itself a port of prjxray's icap_ecc /
 * calculateECC / updateECC. The three `val` bases skip the Hamming positions that are
 * powers of two, which is why the offsets jump at index 0x6 and 0x25.
 */
#define P3_ECC_WORD 0x32u  /* 50 */
#define P3_ECC_MASK 0x1FFFu
#define P3_ECC_KEEP 0xFFFFE000u
#define P3_ECC_LAST 0x64u  /* 100 */

static uint32_t icap_ecc(uint32_t idx, uint32_t data, uint32_t ecc)
{
    uint32_t val = idx * 32u;
    int i;
    if (idx > 0x25u)
        val += 0x1360u;
    else if (idx > 0x6u)
        val += 0x1340u;
    else
        val += 0x1320u;
    if (idx == P3_ECC_WORD)
        data &= P3_ECC_KEEP;
    for (i = 0; i < 32; i++) {
        if (data & 1u)
            ecc ^= val + (uint32_t)i;
        data >>= 1;
    }
    if (idx == P3_ECC_LAST) {
        uint32_t v = ecc & 0xFFFu;
        v ^= v >> 8;
        v ^= v >> 4;
        v ^= v >> 2;
        v ^= v >> 1;
        ecc ^= (v & 1u) << 12;
    }
    return ecc;
}

uint32_t p3_frame_ecc(const uint32_t frame[P3_FRAME_WORDS])
{
    uint32_t ecc = 0;
    uint32_t i;
    for (i = 0; i < P3_FRAME_WORDS; i++)
        ecc = icap_ecc(i, frame[i], ecc);
    return ecc;
}

void p3_frame_update_ecc(uint32_t frame[P3_FRAME_WORDS])
{
    frame[P3_ECC_WORD] = (frame[P3_ECC_WORD] & P3_ECC_KEEP) | (p3_frame_ecc(frame) & P3_ECC_MASK);
}

/* --------------------------------------------------------------- genome codec */

static int hexval(char c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    return -1;
}

int p3_genome_from_hex(const char *hex, uint32_t words[P3_GENOME_WORDS])
{
    int i, j;
    for (i = 0; i < P3_GENOME_WORDS * 8; i++)
        if (hexval(hex[i]) < 0)
            return -1;
    if (hex[P3_GENOME_WORDS * 8] != 0)
        return -1;
    for (i = 0; i < P3_GENOME_WORDS; i++) {
        uint32_t w = 0;
        for (j = 0; j < 8; j++)
            w = (w << 4) | (uint32_t)hexval(hex[8 * i + j]);
        words[i] = w;
    }
    /* bits 292..319 must be zero: word 9 keeps only its low four bits */
    if (words[P3_GENOME_WORDS - 1] & ~0xFu)
        return -1;
    return 0;
}

void p3_genome_to_hex(const uint32_t words[P3_GENOME_WORDS], char out[P3_GENOME_WORDS * 8 + 1])
{
    static const char digits[] = "0123456789abcdef";
    int i, j;
    for (i = 0; i < P3_GENOME_WORDS; i++)
        for (j = 0; j < 8; j++)
            out[8 * i + j] = digits[(words[i] >> (28 - 4 * j)) & 0xFu];
    out[P3_GENOME_WORDS * 8] = 0;
}

int p3_genome_bit(const uint32_t words[P3_GENOME_WORDS], int i)
{
    return (int)((words[i / 32] >> (i % 32)) & 1u);
}

/* --------------------------------------------------- derive / build / parse / hash */

void p3_derive_frames(const uint32_t genome[P3_GENOME_WORDS],
                      uint32_t frames[P3_TARGET_FRAMES][P3_FRAME_WORDS])
{
    int i;
    memcpy(frames, P3_BASE_TARGET, sizeof(P3_BASE_TARGET));
    for (i = 0; i < P3_GENOME_BITS; i++) {
        const p3_address *a = &P3_WHITELIST[i];
        uint32_t mask = 1u << a->bit;
        if (p3_genome_bit(genome, i))
            frames[a->frame][a->word] |= mask;
        else
            frames[a->frame][a->word] &= ~mask;
    }
    for (i = 0; i < P3_TARGET_FRAMES; i++)
        p3_frame_update_ecc(frames[i]);
}

/* type-1/type-2 packet headers, as zynq-psmap's write plan builds them */
#define P3_DUMMY 0xFFFFFFFFu
#define P3_SYNC 0xAA995566u
#define P3_NOOP 0x20000000u
#define P3_REG_CMD 4u
#define P3_REG_FAR 1u
#define P3_REG_FDRI 2u
#define P3_REG_IDCODE 12u
#define P3_CMD_RCRC 7u
#define P3_CMD_WCFG 1u
#define P3_CMD_DESYNC 13u

static uint32_t t1w(uint32_t reg, uint32_t count)
{
    return (1u << 29) | (2u << 27) | (reg << 13) | count;
}

static uint32_t t2w(uint32_t count) { return (2u << 29) | (2u << 27) | count; }

void p3_build_stream(int envelope, const uint32_t frames[P3_TARGET_FRAMES][P3_FRAME_WORDS],
                     uint32_t out[P3_STREAM_WORDS])
{
    const p3_envelope *e = &P3_ENVELOPE[envelope];
    int i, k, n = 0;
    for (i = 0; i < 8; i++)
        out[n++] = P3_DUMMY;
    out[n++] = P3_SYNC;
    out[n++] = P3_NOOP;
    out[n++] = t1w(P3_REG_CMD, 1);
    out[n++] = P3_CMD_RCRC;
    out[n++] = P3_NOOP;
    out[n++] = P3_NOOP;
    out[n++] = t1w(P3_REG_IDCODE, 1);
    out[n++] = P3_IDCODE;
    out[n++] = t1w(P3_REG_CMD, 1);
    out[n++] = P3_CMD_WCFG;
    out[n++] = P3_NOOP;
    out[n++] = t1w(P3_REG_FAR, 1);
    out[n++] = e->far_set;
    out[n++] = t1w(P3_REG_FDRI, 0);
    out[n++] = t2w(P3_FDRI_WORDS);
    for (k = 0; k < 4; k++)
        for (i = 0; i < P3_FRAME_WORDS; i++)
            out[n++] = frames[e->target[k]][i];
    for (i = 0; i < P3_FRAME_WORDS; i++)
        out[n++] = P3_BASE_FLUSH[e->flush][i]; /* flush frames are written verbatim */
    out[n++] = t1w(P3_REG_CMD, 1);
    out[n++] = P3_CMD_DESYNC;
    out[n++] = P3_NOOP;
    out[n++] = P3_NOOP;
    out[n++] = P3_NOOP;
    out[n++] = P3_NOOP;
    /* n == P3_STREAM_WORDS by construction; the parser re-checks on the way back */
}

int p3_parse_stream(const uint32_t in[P3_STREAM_WORDS], uint32_t *far_set_out,
                    uint32_t frames5[P3_ENVELOPE_FRAMES][P3_FRAME_WORDS])
{
    int i = 9, k, cmds = 0;
    int have_far = 0, have_fdri = 0;
    uint32_t far_set = 0;
    uint32_t seen[3];
    for (k = 0; k < 8; k++)
        if (in[k] != P3_DUMMY)
            return -1;
    if (in[8] != P3_SYNC)
        return -1;
    while (i < P3_STREAM_WORDS) {
        uint32_t w = in[i], reg, count;
        if (w == P3_NOOP) {
            i++;
            continue;
        }
        if ((w >> 29) != 1u || ((w >> 27) & 3u) != 2u)
            return -1; /* only type-1 writes are permitted */
        reg = (w >> 13) & 0x3FFFu;
        count = w & 0x7FFu;
        if (reg == P3_REG_CMD) {
            uint32_t cmd = in[i + 1];
            if (cmd != P3_CMD_RCRC && cmd != P3_CMD_WCFG && cmd != P3_CMD_DESYNC)
                return -1;
            if (cmds >= 3)
                return -1;
            seen[cmds++] = cmd;
            i += 2;
        } else if (reg == P3_REG_IDCODE) {
            if (in[i + 1] != P3_IDCODE)
                return -1;
            i += 2;
        } else if (reg == P3_REG_FAR) {
            int e;
            int known = 0;
            for (e = 0; e < P3_ENVELOPE_COUNT; e++)
                if (in[i + 1] == P3_ENVELOPE[e].far_set)
                    known = 1;
            if (!known)
                return -1;
            far_set = in[i + 1];
            have_far = 1;
            i += 2;
        } else if (reg == P3_REG_FDRI) {
            if (count != 0 || (in[i + 1] >> 29) != 2u ||
                (in[i + 1] & 0x07FFFFFFu) != P3_FDRI_WORDS)
                return -1;
            if (!have_far || have_fdri)
                return -1;
            for (k = 0; k < P3_ENVELOPE_FRAMES; k++)
                memcpy(frames5[k], &in[i + 2 + k * P3_FRAME_WORDS],
                       P3_FRAME_WORDS * sizeof(uint32_t));
            have_fdri = 1;
            i += 2 + P3_FDRI_WORDS;
        } else {
            return -1; /* any other register, CRC included, is refused */
        }
    }
    if (!have_fdri || cmds != 3)
        return -1;
    if (seen[0] != P3_CMD_RCRC || seen[1] != P3_CMD_WCFG || seen[2] != P3_CMD_DESYNC)
        return -1;
    *far_set_out = far_set;
    return 0;
}

void p3_frames_hash(const uint32_t frames[P3_TARGET_FRAMES][P3_FRAME_WORDS], uint8_t out[32])
{
    p3_sha256 c;
    int i;
    p3_sha256_init(&c);
    /* P3_TARGET_FARS is ascending, so this walk is the FAR-ordered domain */
    for (i = 0; i < P3_TARGET_FRAMES; i++) {
        p3_sha256_words(&c, &P3_TARGET_FARS[i], 1);
        p3_sha256_words(&c, frames[i], P3_FRAME_WORDS);
    }
    p3_sha256_final(&c, out);
}

/* ------------------------------------------------- the pinned readback command stream */

#define P3_OP_READ 1u
#define P3_OP_WRITE 2u
#define P3_R_FDRO 3u
#define P3_CMD_RCFG 4u
#define P3_FLUSH_NOOPS 32

static uint32_t t1op(uint32_t op, uint32_t reg, uint32_t count)
{
    return (1u << 29) | (op << 27) | (reg << 13) | count;
}

static uint32_t t2op(uint32_t op, uint32_t count)
{
    return (2u << 29) | (op << 27) | count;
}

void p3_build_readback_command(uint32_t far, uint32_t out[P3_READBACK_CMD_WORDS])
{
    int i, n = 0;
    out[n++] = P3_DUMMY;
    out[n++] = P3_SYNC;
    out[n++] = P3_NOOP;
    out[n++] = P3_NOOP;
    out[n++] = t1op(P3_OP_WRITE, P3_REG_CMD, 1); /* UG470 step 6: RCFG first … */
    out[n++] = P3_CMD_RCFG;
    out[n++] = P3_NOOP;                          /* … then one NOOP … */
    out[n++] = t1op(P3_OP_WRITE, P3_REG_FAR, 1); /* … then the FAR (step 7) */
    out[n++] = far;
    out[n++] = t1op(P3_OP_READ, P3_R_FDRO, 0); /* step 8 */
    out[n++] = t2op(P3_OP_READ, P3_READBACK_WORDS);
    for (i = 0; i < P3_FLUSH_NOOPS; i++)
        out[n++] = P3_NOOP;
}

void p3_build_cleanup_command(uint32_t out[P3_CLEANUP_WORDS])
{
    out[0] = P3_NOOP;
    out[1] = t1op(P3_OP_WRITE, P3_REG_CMD, 1);
    out[2] = P3_CMD_DESYNC;
    out[3] = P3_NOOP;
    out[4] = P3_NOOP;
}

/* --------------------------------------------------------- nonce, base64url, page */

uint64_t p3_nonce_step(uint64_t x)
{
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    return x;
}

size_t p3_base64url(const uint8_t *in, size_t n, char *out)
{
    static const char abc[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    size_t i = 0, o = 0;
    while (i + 3 <= n) {
        uint32_t v = ((uint32_t)in[i] << 16) | ((uint32_t)in[i + 1] << 8) | in[i + 2];
        out[o++] = abc[(v >> 18) & 63];
        out[o++] = abc[(v >> 12) & 63];
        out[o++] = abc[(v >> 6) & 63];
        out[o++] = abc[v & 63];
        i += 3;
    }
    if (n - i == 1) {
        uint32_t v = (uint32_t)in[i] << 16;
        out[o++] = abc[(v >> 18) & 63];
        out[o++] = abc[(v >> 12) & 63];
        out[o++] = '=';
        out[o++] = '=';
    } else if (n - i == 2) {
        uint32_t v = ((uint32_t)in[i] << 16) | ((uint32_t)in[i + 1] << 8);
        out[o++] = abc[(v >> 18) & 63];
        out[o++] = abc[(v >> 12) & 63];
        out[o++] = abc[(v >> 6) & 63];
        out[o++] = '=';
    }
    out[o] = 0;
    return o;
}

static int b64val(char c)
{
    if (c >= 'A' && c <= 'Z')
        return c - 'A';
    if (c >= 'a' && c <= 'z')
        return c - 'a' + 26;
    if (c >= '0' && c <= '9')
        return c - '0' + 52;
    if (c == '-')
        return 62;
    if (c == '_')
        return 63;
    return -1;
}

size_t p3_base64url_decode(const char *in, uint8_t *out, size_t max)
{
    size_t n = strlen(in), i = 0, o = 0;
    if (n % 4u != 0u)
        return 0;
    while (i < n) {
        int v[4];
        int k, pad = 0;
        for (k = 0; k < 4; k++) {
            char c = in[i + (size_t)k];
            if (c == '=') {
                if (k < 2)
                    return 0;
                pad++;
                v[k] = 0;
            } else {
                if (pad)
                    return 0; /* padding is only ever a suffix */
                v[k] = b64val(c);
                if (v[k] < 0)
                    return 0;
            }
        }
        if (pad && i + 4u != n)
            return 0;
        if (o + (size_t)(3 - pad) > max)
            return 0;
        out[o++] = (uint8_t)((v[0] << 2) | (v[1] >> 4));
        if (pad < 2)
            out[o++] = (uint8_t)((v[1] << 4) | (v[2] >> 2));
        if (pad < 1)
            out[o++] = (uint8_t)((v[2] << 6) | v[3]);
        i += 4;
    }
    return o;
}

int p3_parse_identity_page(const uint32_t words[P3_PAGE_WORDS], p3_identity_page *out)
{
    uint32_t checksum = 0;
    int i;
    uint8_t be[32];
    for (i = 0; i < P3_PAGE_WORDS - 1; i++)
        checksum ^= words[i];
    if (words[0] != P3_PAGE_MAGIC || words[1] != P3_PAGE_LAYOUT ||
        words[P3_PAGE_WORDS - 1] != checksum)
        return -1;
    for (i = 0; i < 4; i++) {
        be[4 * i] = (uint8_t)(words[2 + i] >> 24);
        be[4 * i + 1] = (uint8_t)(words[2 + i] >> 16);
        be[4 * i + 2] = (uint8_t)(words[2 + i] >> 8);
        be[4 * i + 3] = (uint8_t)words[2 + i];
    }
    p3_hex(be, 16, out->token);
    out->uboot_epoch = words[6];
    out->app_image_sha_lo32 = words[7];
    for (i = 0; i < 8; i++) {
        be[4 * i] = (uint8_t)(words[8 + i] >> 24);
        be[4 * i + 1] = (uint8_t)(words[8 + i] >> 16);
        be[4 * i + 2] = (uint8_t)(words[8 + i] >> 8);
        be[4 * i + 3] = (uint8_t)words[8 + i];
    }
    p3_hex(be, 32, out->carrier_sha256);
    out->nonce_seen = (uint64_t)words[16] | ((uint64_t)words[17] << 32);
    out->status_seen = words[18];
    out->seed = words[19];
    out->budget = words[20];
    out->flags = words[21];
    out->fclk0_hz = words[22];
    return 0;
}
