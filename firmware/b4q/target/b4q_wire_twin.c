/* b4q_wire_twin — a stdin / stdout driver of the wire unit for tests/test_b4q_wire.py: each input line is one command,
 *   "FRAME <type> <seq> <token> <hex-of-plain>"  -> the framed line, or "OVERFLOW"
 *   "PARSE <token|-> <line...>"                  -> "OK <type> <seq> <token> <hex-of-plain>" | "BAD <code>"
 *   "PAGE <24 words hex8>"                       -> "OK <token> <epoch> <sha_lo32> <carrier> <nonce> <status> <flags>" | "REFUSED"
 *   "CRC <hex-of-bytes>"                         -> the crc32
 *   "PSMAP <addr hex>"                           -> "r=<0|1> w=<0|1>" (the pure allowlist) */
#include "b4q_wire.h"
#include "b4q_psmap.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int unhex(const char *h, uint8_t *out, size_t max)
{
    size_t n = strlen(h), i;
    if (n % 2 || n / 2 > max) return -1;
    for (i = 0; i < n; i += 2) { unsigned v; if (sscanf(h + i, "%2x", &v) != 1) return -1; out[i / 2] = (uint8_t)v; }
    return (int)(n / 2);
}

static void hexout(const uint8_t *b, size_t n) { size_t i; for (i = 0; i < n; i++) printf("%02x", b[i]); }

int main(void)
{
    static char line[131072], out[16384], plain[16384];
    static uint8_t bytes[65536];
    setvbuf(stdout, NULL, _IOLBF, 0);               /* every reply line leaves at once: the driver reads one per command */
    while (fgets(line, sizeof line, stdin)) {
        line[strcspn(line, "\r\n")] = 0;
        if (strncmp(line, "FRAME ", 6) == 0) {
            static char type[32], token[64], hex[131072];
            unsigned long seq;
            int n;
            if (sscanf(line + 6, "%31s %lu %63s %131071s", type, &seq, token, hex) != 4) { puts("BAD args"); continue; }
            n = strcmp(hex, "-") == 0 ? 0 : unhex(hex, bytes, sizeof bytes);
            if (n < 0) { puts("BAD hex"); continue; }
            if (b4q_wire_frame(type, (uint32_t)seq, token, bytes, (size_t)n, out, sizeof out) == 0) puts("OVERFLOW");
            else { fputs(out, stdout); }
        } else if (strncmp(line, "PARSE ", 6) == 0) {
            char token[64];
            int pos = 0;
            b4q_wire_frame_t f;
            int r;
            if (sscanf(line + 6, "%63s%n", token, &pos) != 1) { puts("BAD args"); continue; }
            r = b4q_wire_parse(line + 6 + pos + 1, strcmp(token, "-") == 0 ? NULL : token, &f);
            if (r != 0) { printf("BAD %d\n", r); continue; }
            {
                size_t n = b4q_wire_payload(&f, plain, sizeof plain);
                if (n == (size_t)-1) { puts("BAD payload"); continue; }
                printf("OK %s %lu %s ", f.type, (unsigned long)f.seq, f.token); hexout((const uint8_t *)plain, n); puts("");
            }
        } else if (strncmp(line, "PAGE ", 5) == 0) {
            uint32_t w[B4Q_PAGE_WORDS];
            b4q_page p;
            const char *s = line + 5;
            int i;
            for (i = 0; i < B4Q_PAGE_WORDS; i++) { unsigned long v; int n = 0; if (sscanf(s, " %lx%n", &v, &n) != 1) break; w[i] = (uint32_t)v; s += n; }
            if (i < B4Q_PAGE_WORDS) { puts("BAD args"); continue; }
            if (b4q_parse_page(w, &p) != 0) puts("REFUSED");
            else printf("OK %s %lu %lu %s %016llx %lu %lu\n", p.token, (unsigned long)p.uboot_epoch, (unsigned long)p.app_image_sha_lo32, p.carrier_sha256,
                        (unsigned long long)p.nonce_seen, (unsigned long)p.status_seen, (unsigned long)p.flags);
        } else if (strncmp(line, "CRC ", 4) == 0) {
            int n = unhex(line + 4, bytes, sizeof bytes);
            if (n < 0) { puts("BAD hex"); continue; }
            printf("%08lx\n", (unsigned long)b4q_crc32(bytes, (size_t)n));
        } else if (strncmp(line, "PSMAP ", 6) == 0) {
            unsigned long a = strtoul(line + 6, NULL, 16);
            printf("r=%d w=%d\n", b4q_psmap_readable((uint32_t)a), b4q_psmap_writable((uint32_t)a));
        } else puts("BAD command");
        fflush(stdout);
    }
    return 0;
}
