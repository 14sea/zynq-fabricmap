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
 * Nothing here is a board image. */
#include "b4q_tx.h"
#include "b4q_hal.h"

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

static void print_tx(const b4q_tx_result *r)
{
    int i;
    printf("RESULT {\"status\": %d, \"phase\": \"%s\", \"reason\": \"%s\", \"fault_code\": %u, \"commit\": \"%s\", \"staged\": \"%s\", \"stream\": \"%s\", "
           "\"pre_event\": \"%s\", \"post_event\": \"%s\", \"base_staged\": \"%s\", \"base_readback\": \"%s\", \"n_slots\": %d, \"slot_q\": [",
           r->status, r->phase, r->reason ? r->reason : "", (unsigned)r->fault_code, r->commit_hex, r->staged_hex, r->stream_hex, r->pre_event_hex, r->post_event_hex,
           r->base_staged_hex, r->base_readback_hex, r->n_slots);
    for (i = 0; i < r->n_slots; i++) printf("%s%u", i ? ", " : "", (unsigned)r->slot_q[i]);
    printf("], \"slot_in\": [");
    for (i = 0; i < r->n_slots; i++) printf("%s%u", i ? ", " : "", (unsigned)r->slot_in[i]);
    printf("], \"in_live_pre\": %u, \"witness_after_init\": %u, \"witness_after_restore\": %u, \"heartbeat_before\": %u, \"heartbeat_after\": %u, "
           "\"base_state\": %u, \"status_final\": %u, \"steps_applied\": %d, \"has_fitness\": %d, \"fitness\": %d, \"task_digest\": \"%s\", "
           "\"nonce_before\": \"%016llx\", \"nonce_after\": \"%016llx\"}\n",
           (unsigned)r->in_live_pre, (unsigned)r->witness_after_init, (unsigned)r->witness_after_restore, (unsigned)r->heartbeat_before, (unsigned)r->heartbeat_after,
           (unsigned)r->base_state, (unsigned)r->status_final, r->steps_applied, r->has_fitness, r->fitness, r->task_digest,
           (unsigned long long)r->nonce_before, (unsigned long long)r->nonce_after);
    fflush(stdout);
}

int main(void)
{
    static char cmd[8192];
    while (fgets(cmd, sizeof cmd, stdin)) {
        cmd[strcspn(cmd, "\r\n")] = 0;
        if (strcmp(cmd, "QUIT") == 0) break;
        if (strcmp(cmd, "OPEN") == 0) {
            b4q_open_result o;
            b4q_session_open(&o);
            printf("RESULT {\"status\": %d, \"reason\": \"%s\", \"idcode\": %u, \"variant\": %u, \"timing\": %u, \"witness\": %u, \"status_word\": %u, "
                   "\"heartbeat\": %u, \"nonce\": \"%016llx\", \"startup_readback\": \"%s\"}\n",
                   o.status, o.reason ? o.reason : "", (unsigned)o.idcode, (unsigned)o.variant, (unsigned)o.timing, (unsigned)o.witness, (unsigned)o.status_word,
                   (unsigned)o.heartbeat, (unsigned long long)o.nonce, o.startup_readback_hex);
            fflush(stdout);
        } else if (strncmp(cmd, "TX ", 3) == 0) {
            static uint32_t steps[B4Q_MAX_STEPS];
            static b4q_task task;
            b4q_tx_result r;
            char kindname[16];
            unsigned long long g;
            int n = 0, i, pos = 0, k;
            b4q_kind kind;
            memset(&task, 0, sizeof task);
            if (sscanf(cmd + 3, "%15s %llx %d%n", kindname, &g, &n, &pos) != 3) { printf("RESULT {\"status\": 3, \"reason\": \"malformed TX\"}\n"); fflush(stdout); continue; }
            kind = strcmp(kindname, "root") == 0 ? B4Q_KIND_ROOT : strcmp(kindname, "inject") == 0 ? B4Q_KIND_INJECT : strcmp(kindname, "a5") == 0 ? B4Q_KIND_A5 : B4Q_KIND_NORMAL;
            k = 3 + pos;
            for (i = 0; i < n && i < B4Q_MAX_STEPS; i++) {
                unsigned long long w; int q = 0;
                if (sscanf(cmd + k, "%llx%n", &w, &q) != 1) break;
                steps[i] = (uint32_t)w; k += q;
            }
            {
                const char *t = strstr(cmd, " TASK ");
                if (t) {
                    int m = 0, q = 0, j;
                    if (sscanf(t + 6, "%64s %d%n", task.digest, &m, &q) == 2 && m <= B4Q_MAX_MASK) {
                        const char *p = t + 6 + q;
                        for (j = 0; j < m; j++) {
                            int s, e, tv, w, qq = 0;
                            if (sscanf(p, "%d %d %d %d%n", &s, &e, &tv, &w, &qq) != 4) break;
                            task.step[j] = (uint8_t)s; task.elem[j] = (uint8_t)e; task.target[j] = (uint8_t)tv; task.weight[j] = (uint16_t)w; p += qq;
                        }
                        task.n = j;
                    }
                }
            }
            b4q_transaction((uint32_t)g, steps, n, kind, task.n ? &task : NULL, &r);
            print_tx(&r);
        } else {
            printf("RESULT {\"status\": 3, \"reason\": \"unknown command\"}\n"); fflush(stdout);
        }
    }
    return 0;
}
