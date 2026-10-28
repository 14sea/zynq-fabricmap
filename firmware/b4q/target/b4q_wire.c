/* b4q_wire — see b4q_wire.h. */
#include "b4q_wire.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- the instrument's functions, VERBATIM from firmware/b1/p3_derive.c (held by digest: tests/test_b4q_wire.py) ---- */
#define p3_crc32 b4q_crc32
#define p3_base64url b4q_base64url
#define p3_base64url_decode b4q_base64url_decode
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
#undef p3_crc32
#undef p3_base64url
#undef p3_base64url_decode

/* ---- the frame ---- */
size_t b4q_wire_line(const char *type, uint32_t seq, const char *token, const char *payload_b64, char *out, size_t max)
{
    int n = snprintf(out, max, "%s %s %lu %s %s", B4Q_WIRE_MAGIC, type, (unsigned long)seq, token, payload_b64);
    if (n < 0 || (size_t)n + 10 >= max) { if (max) out[0] = 0; return 0; }
    {
        uint32_t crc = b4q_crc32((const uint8_t *)out, (size_t)n);
        int m = snprintf(out + n, max - (size_t)n, " %08lx\n", (unsigned long)crc);
        if (m < 0 || (size_t)n + (size_t)m >= max) { out[0] = 0; return 0; }
        return (size_t)n + (size_t)m;
    }
}

size_t b4q_wire_frame(const char *type, uint32_t seq, const char *token, const uint8_t *plain, size_t n, char *out, size_t max)
{
    static char b64[12288];
    if (n == 0) return b4q_wire_line(type, seq, token, "-", out, max);
    if (((n + 2) / 3) * 4 + 1 > sizeof b64) { if (max) out[0] = 0; return 0; }
    b4q_base64url(plain, n, b64);
    return b4q_wire_line(type, seq, token, b64, out, max);
}

int b4q_wire_parse(char *line, const char *want_token, b4q_wire_frame_t *out)
{
    char *last, *f[6];
    size_t i, k = 0, n;
    char expect[9];
    memset(out, 0, sizeof *out);
    n = strlen(line);
    while (n && (line[n - 1] == '\n' || line[n - 1] == '\r')) line[--n] = 0;
    last = strrchr(line, ' ');
    if (!last) return -2;
    *last = 0;                                        /* the CRC covers everything before the final field */
    snprintf(expect, sizeof expect, "%08lx", (unsigned long)b4q_crc32((const uint8_t *)line, strlen(line)));
    if (strcmp(expect, last + 1) != 0) return -1;
    f[k++] = line;
    for (i = 0; line[i] && k < 5; i++)
        if (line[i] == ' ') { line[i] = 0; f[k++] = line + i + 1; }
    if (k != 5 || strcmp(f[0], B4Q_WIRE_MAGIC) != 0) return -2;
    if (strlen(f[1]) >= sizeof out->type || strlen(f[3]) != B4Q_WIRE_TOKEN_HEX) return -2;
    for (i = 0; f[2][i]; i++) if (f[2][i] < '0' || f[2][i] > '9') return -2;
    if (!f[2][0] || i > 10) return -2;                /* a 32-bit sequence number: at most ten decimal digits ... */
    {
        unsigned long long v = strtoull(f[2], NULL, 10);
        if (v > 0xFFFFFFFFull) return -2;             /* ... and within range */
        out->seq = (uint32_t)v;
    }
    if (want_token && strcmp(f[3], want_token) != 0) return -3;
    strcpy(out->type, f[1]);
    strcpy(out->token, f[3]);
    out->payload_b64 = f[4];
    return 0;
}

size_t b4q_wire_payload(const b4q_wire_frame_t *f, char *out, size_t max)
{
    size_t n;
    if (max == 0) return (size_t)-1;
    if (strcmp(f->payload_b64, "-") == 0) { out[0] = 0; return 0; }
    n = b4q_base64url_decode(f->payload_b64, (uint8_t *)out, max - 1);
    if (n == 0) return (size_t)-1;
    out[n] = 0;
    if (strlen(out) != n) return (size_t)-1;          /* a NUL inside a text payload is not a line */
    return n;
}

/* ---- the identity page ---- */
static void hex_of_words_be(const uint32_t *w, int nw, char *out)
{
    static const char hx[] = "0123456789abcdef";
    int i, o = 0;
    for (i = 0; i < nw; i++) {
        int s;
        for (s = 28; s >= 0; s -= 4) out[o++] = hx[(w[i] >> s) & 15u];
    }
    out[o] = 0;
}

int b4q_parse_page(const uint32_t words[B4Q_PAGE_WORDS], b4q_page *out)
{
    uint32_t checksum = 0;
    int i;
    memset(out, 0, sizeof *out);
    for (i = 0; i < B4Q_PAGE_WORDS - 1; i++) checksum ^= words[i];
    if (words[0] != B4Q_PAGE_MAGIC || words[1] != B4Q_PAGE_LAYOUT || words[B4Q_PAGE_WORDS - 1] != checksum) return -1;
    hex_of_words_be(words + 2, 4, out->token);
    out->uboot_epoch = words[6];
    out->app_image_sha_lo32 = words[7];
    hex_of_words_be(words + 8, 8, out->carrier_sha256);
    out->nonce_seen = (uint64_t)words[16] | ((uint64_t)words[17] << 32);
    out->status_seen = words[18];
    out->flags = words[19];
    for (i = 20; i < 23; i++) if (words[i] != 0u) return -1;      /* the reserved words are zero in layout 1 */
    return 0;
}
