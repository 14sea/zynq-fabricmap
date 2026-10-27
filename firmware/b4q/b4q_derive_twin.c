/* b4q_derive_twin — the host driver of b4q_derive.c for tests/test_b4q_derive.py: one genome (8 hex chars) per stdin line,
 * one JSON line out with the digests the Python twin (host/b4q_frames.py) must reproduce — the derived frames' FAR-ordered
 * hash, each envelope's stream digest and its parse round trip, the readback command digest of every target FAR, the cleanup
 * command digest, a nonce step. Host tooling only; nothing here is a board image. */
#include "b4q_derive.h"
#include "b4q_data.h"

#include <stdio.h>
#include <string.h>

static void words_hex(const uint32_t *w, size_t n, char *out)
{
    uint8_t d[32];
    p3_sha256 c;
    p3_sha256_init(&c);
    p3_sha256_words(&c, w, n);
    p3_sha256_final(&c, d);
    p3_hex(d, 32, out);
}

int main(void)
{
    char line[64];
    while (fgets(line, sizeof line, stdin)) {
        uint32_t genome[P3_GENOME_WORDS];
        uint32_t frames[P3_TARGET_FRAMES][P3_FRAME_WORDS];
        uint32_t stream[P3_STREAM_WORDS];
        uint32_t frames5[P3_ENVELOPE_FRAMES][P3_FRAME_WORDS];
        uint32_t cmd[P3_READBACK_CMD_WORDS], clean[P3_CLEANUP_WORDS];
        uint8_t d[32];
        char hex[65], back[P3_GENOME_WORDS * 8 + 1];
        size_t n = strlen(line);
        int e, i, ok;
        while (n && (line[n - 1] == '\n' || line[n - 1] == '\r'))
            line[--n] = 0;
        if (p3_genome_from_hex(line, genome) != 0) {
            printf("{\"genome\": \"%s\", \"refused\": true}\n", line);
            continue;
        }
        p3_genome_to_hex(genome, back);
        p3_derive_frames(genome, frames);
        p3_frames_hash(P3_CFRAMES(frames), d);
        p3_hex(d, 32, hex);
        printf("{\"genome\": \"%s\", \"round_trip\": \"%s\", \"frames_hash\": \"%s\", \"streams\": [", line, back, hex);
        for (e = 0; e < P3_ENVELOPE_COUNT; e++) {
            uint32_t far_set = 0;
            p3_build_stream(e, P3_CFRAMES(frames), stream);
            words_hex(stream, P3_STREAM_WORDS, hex);
            ok = (p3_parse_stream(stream, &far_set, frames5) == 0) && (far_set == P3_ENVELOPE[e].far_set);
            for (i = 0; ok && i < 4; i++)
                ok = memcmp(frames5[i], frames[P3_ENVELOPE[e].target[i]], sizeof frames5[i]) == 0;
            if (ok)
                ok = memcmp(frames5[4], P3_BASE_FLUSH[P3_ENVELOPE[e].flush], sizeof frames5[4]) == 0;
            printf("%s{\"sha256\": \"%s\", \"parse_ok\": %s, \"far_set\": \"0x%08x\"}", e ? ", " : "", hex, ok ? "true" : "false", (unsigned)far_set);
        }
        printf("], \"readback_cmd\": [");
        for (i = 0; i < P3_TARGET_FRAMES; i++) {
            p3_build_readback_command(P3_TARGET_FARS[i], cmd);
            words_hex(cmd, P3_READBACK_CMD_WORDS, hex);
            printf("%s\"%s\"", i ? ", " : "", hex);
        }
        p3_build_cleanup_command(clean);
        words_hex(clean, P3_CLEANUP_WORDS, hex);
        printf("], \"cleanup\": \"%s\", \"ecc\": [", hex);
        for (i = 0; i < P3_TARGET_FRAMES; i++)
            printf("%s%u", i ? ", " : "", (unsigned)(frames[i][50] & 0x1FFFu));
        printf("], \"nonce_step\": \"0x%016llx\"}\n", (unsigned long long)p3_nonce_step(0x9E3779B97F4A7C15ull ^ (uint64_t)genome[0]));
        fflush(stdout);
    }
    return 0;
}
