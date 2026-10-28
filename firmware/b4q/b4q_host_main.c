/* b4q_host_main — the HOST driver of the B4Q executing side: the injected transport (b4q_hal.h) as a line protocol on
 * stdin / stdout to host/b4q_session.py (which answers every MMIO access from host/b4q_backend.py and every SIGN from the
 * bench notary), and a tiny command loop the session drives:
 *
 *   -> "OPEN"                                              the session opening (identity, startup readback)
 *   -> "TX <kind> <genome_hex8> <n> <step_hex ...> [TASK <digest> <m> <step elem target weight> ...]"
 *                                                          one transaction; kind: normal | root | inject | a5
 *   -> "QUIT"
 *   <- "R <addr_hex8>"            / -> "<data_hex8> <resp>"           an MMIO read
 *   <- "W <addr_hex8> <data_hex8>" / -> "<resp>"                       an MMIO write
 *   <- "SIGN <genome_hex8> <nonce_hex16>" / -> "OK <24 words hex8>" | "REFUSED <why>"
 *   <- "EV ..." / "MARK ..."                                          events (informational)
 *   <- "RESULT {...}"                                                  the outcome of OPEN / TX, one JSON line
 * The command parser and the RESULT writers are the shared pure unit b4q_cmd.c (the board application uses the same).
 * Nothing here is a board image. */
#include "b4q_tx.h"
#include "b4q_hal.h"
#include "b4q_cmd.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char g_line[4096];

static const char *reply(void)
{
    if (!fgets(g_line, sizeof g_line, stdin)) { fprintf(stderr, "transport closed\n"); exit(3); }
    g_line[strcspn(g_line, "\r\n")] = 0;
    return g_line;
}

uint32_t b4q_rd32(uint32_t addr, uint32_t *resp)
{
    unsigned long long d = 0, r = 0;
    printf("R %08x\n", (unsigned)addr); fflush(stdout);
    if (sscanf(reply(), "%llx %llu", &d, &r) != 2) { fprintf(stderr, "bad read reply: %s\n", g_line); exit(3); }
    *resp = (uint32_t)r;
    return (uint32_t)d;
}

uint32_t b4q_wr32(uint32_t addr, uint32_t value)
{
    unsigned long long r = 0;
    printf("W %08x %08x\n", (unsigned)addr, (unsigned)value); fflush(stdout);
    if (sscanf(reply(), "%llu", &r) != 1) { fprintf(stderr, "bad write reply: %s\n", g_line); exit(3); }
    return (uint32_t)r;
}

int b4q_sign(const char *genome_hex, const char *nonce_hex, uint32_t words[24])
{
    const char *p;
    int i;
    printf("SIGN %s %s\n", genome_hex, nonce_hex); fflush(stdout);
    p = reply();
    if (strncmp(p, "OK ", 3) != 0) return -1;
    p += 3;
    for (i = 0; i < 24; i++) {
        unsigned long long w;
        int n = 0;
        if (sscanf(p, "%llx%n", &w, &n) != 1) return -1;
        words[i] = (uint32_t)w; p += n;
    }
    return 0;
}

void b4q_emit(const char *line) { printf("%s\n", line); fflush(stdout); }

static char g_json[8192];

static void print_json(const char *tag, size_t n)
{
    if (n == 0) { printf("RESULT {\"status\": 3, \"reason\": \"result too long\"}\n"); fflush(stdout); return; }
    printf("%s %s\n", tag, g_json); fflush(stdout);
}

int main(void)
{
    static char cmd[8192];
    static b4q_tx_command c;
    while (fgets(cmd, sizeof cmd, stdin)) {
        cmd[strcspn(cmd, "\r\n")] = 0;
        if (strcmp(cmd, "QUIT") == 0) break;
        if (strcmp(cmd, "OPEN") == 0) {
            b4q_open_result o;
            b4q_session_open(&o);
            print_json("RESULT", b4q_open_json(&o, g_json, sizeof g_json));
        } else if (strncmp(cmd, "TX ", 3) == 0) {
            b4q_tx_result r;
            if (b4q_parse_tx(cmd, &c) != 0) { printf("RESULT {\"status\": 3, \"reason\": \"malformed TX\"}\n"); fflush(stdout); continue; }
            b4q_transaction(c.genome, c.steps, c.n_steps, c.kind, c.task.n ? &c.task : NULL, &r);
            print_json("RESULT", b4q_tx_json(&r, g_json, sizeof g_json));
        } else {
            printf("RESULT {\"status\": 3, \"reason\": \"unknown command\"}\n"); fflush(stdout);
        }
    }
    return 0;
}
