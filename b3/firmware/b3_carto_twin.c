/* b3_carto_twin — the host driver that proves b3_carto.c equals the Python reference
 * (b3/host/b3_carto.py, SpecimenCarto v1.1) specimen by specimen. B3 lifecycle 2, image stage 1.
 *
 * Host-only: compiled with the host compiler, never for the board. One cartographer per process,
 * driven over a pipe, one command per line:
 *
 * Every command is the whole line: "S", "R" and "Q" exactly (a trailing newline only), "O " followed by
 * the specimen; anything else — "S junk", "R junk", "Observe …" — is "ERR unknown command" and changes
 * nothing (the owner's P2 on 4817662).
 *
 *   O <n> <i1> ... <in> | <m> <k1.v1> ... <km.vm>
 *       observe a specimen: n moved addresses, m toggled positions (LUT.vector). Prints
 *         NEWLY <count> <i:k:v> ...      the addresses this specimen decoded, in the cartographer's order
 *       or
 *         ANOMALY                        the specimen was refused (counted; nothing else changed)
 *       then
 *         STATE <text>                   the commitment text (b3_carto_state_render), byte for byte
 *   B <the same specimen syntax as O>
 *       a PROBE of the API contract, not a cartographer operation: calls b3_carto_observe with the scratch
 *       aliasing the state (scratch == &carto). The contract says B3_CARTO_BAD_CALL, nothing done, nothing
 *       counted — printed as "ERR bad call" then STATE <text> (unchanged).
 *   S   print STATE <text>
 *   R   reset the cartographer, then print STATE <text>
 *   Q   exit 0
 *
 * A line the twin cannot parse — a token that is not a non-negative integer below 65536, a count that
 * does not match its tokens, more than B3_CARTO_N addresses or B3_CARTO_POSITIONS positions, a missing
 * "|" — is answered with "ERR <reason>" and changes NOTHING: the whole line is parsed into local
 * arrays before the cartographer is called. Values that parse but are out of the cartographer's
 * range (an address >= 292, a LUT >= 6, a vector >= 64) are handed to the cartographer, which refuses
 * them as the Python does (an anomaly): an out-of-range position is encoded as a position index
 * >= B3_CARTO_POSITIONS so that it can never alias a valid one.
 */
#include "b3_carto.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LINE_MAX_BYTES 65536
#define OUT_OF_RANGE_POSITION 0xFFFF

static void emit_stdout(void *ctx, const char *bytes, size_t n)
{
    (void)ctx;
    fwrite(bytes, 1, n, stdout);
}

static void print_state(const b3_carto *c)
{
    fputs("STATE ", stdout);
    b3_carto_state_render(c, emit_stdout, NULL);
    fputc('\n', stdout);
    fflush(stdout);
}

/* A non-negative decimal integer below 65536; advances *p past it. */
static int parse_u16(const char **p, unsigned *out)
{
    const char *s = *p;
    unsigned long v;
    char *end;
    while (*s == ' ')
        s++;
    if (*s < '0' || *s > '9')
        return -1;
    v = strtoul(s, &end, 10);
    if (end == s || v > 65535UL)
        return -1;
    *out = (unsigned)v;
    *p = end;
    return 0;
}

static int at_end(const char *p)
{
    while (*p == ' ')
        p++;
    return *p == '\0';
}

static int parse_observe(const char *line, uint16_t *moved, int *n_moved, uint16_t *delta, int *n_delta, const char **why)
{
    const char *p = line + 1;
    unsigned n, m, v, k, j;
    if (parse_u16(&p, &n) < 0) {
        *why = "the address count";
        return -1;
    }
    if (n > B3_CARTO_N) {
        *why = "too many addresses";
        return -1;
    }
    for (j = 0; j < n; j++) {
        if (parse_u16(&p, &v) < 0) {
            *why = "an address token";
            return -1;
        }
        moved[j] = (uint16_t)v;
    }
    while (*p == ' ')
        p++;
    if (*p != '|') {
        *why = "the '|' separator";
        return -1;
    }
    p++;
    if (parse_u16(&p, &m) < 0) {
        *why = "the position count";
        return -1;
    }
    if (m > B3_CARTO_POSITIONS) {
        *why = "too many positions";
        return -1;
    }
    for (j = 0; j < m; j++) {
        if (parse_u16(&p, &k) < 0) {
            *why = "a LUT token";
            return -1;
        }
        if (*p != '.') {
            *why = "the '.' of a position";
            return -1;
        }
        p++;
        if (*p < '0' || *p > '9' || parse_u16(&p, &v) < 0) {
            *why = "a vector token";
            return -1;
        }
        delta[j] = (k < B3_CARTO_LUTS && v < B3_CARTO_VECTORS) ? (uint16_t)(k * B3_CARTO_VECTORS + v) : OUT_OF_RANGE_POSITION;
    }
    if (!at_end(p)) {
        *why = "trailing tokens";
        return -1;
    }
    *n_moved = (int)n;
    *n_delta = (int)m;
    return 0;
}

int main(void)
{
    static char line[LINE_MAX_BYTES];
    static b3_carto carto, scratch;                       /* the scratch is BSS, as the image's will be — never a frame */
    static uint16_t moved[B3_CARTO_N], delta[B3_CARTO_POSITIONS], newly[B3_CARTO_N];
    b3_carto_init(&carto);
    while (fgets(line, sizeof(line), stdin)) {
        const char *why = "";
        int n_moved = 0, n_delta = 0, n, j;
        size_t len = strlen(line);
        if (len && line[len - 1] != '\n' && !feof(stdin)) {
            printf("ERR the line exceeds %d bytes\n", LINE_MAX_BYTES - 1);
            fflush(stdout);
            return 3;
        }
        if (len && line[len - 1] == '\n')
            line[--len] = '\0';                         /* the command is the whole line, without its newline */
        if (strcmp(line, "S") == 0) {
            print_state(&carto);
            continue;
        }
        if (strcmp(line, "R") == 0) {
            b3_carto_init(&carto);
            print_state(&carto);
            continue;
        }
        if (strcmp(line, "Q") == 0)
            return 0;
        if ((line[0] == 'O' || line[0] == 'B') && line[1] == ' ') {
            int probe = line[0] == 'B';
            if (parse_observe(line, moved, &n_moved, delta, &n_delta, &why) < 0) {
                printf("ERR cannot parse %s\n", why);
                fflush(stdout);
                continue;
            }
            n = b3_carto_observe(&carto, probe ? &carto : &scratch, moved, n_moved, delta, n_delta, newly, B3_CARTO_N);
            if (n == B3_CARTO_BAD_CALL) {
                fputs("ERR bad call\n", stdout);        /* the contract's answer to an aliasing scratch (the B probe) */
                print_state(&carto);
                continue;
            }
            if (n < 0) {
                fputs("ANOMALY\n", stdout);
            } else {
                printf("NEWLY %d", n);
                for (j = 0; j < n; j++) {
                    int pos = b3_carto_decoded_position(&carto, newly[j]);
                    printf(" %u:%d:%d", (unsigned)newly[j], pos / B3_CARTO_VECTORS, pos % B3_CARTO_VECTORS);
                }
                fputc('\n', stdout);
            }
            print_state(&carto);
            continue;
        }
        fputs("ERR unknown command\n", stdout);
        fflush(stdout);
    }
    return 0;
}
