/* b4q_cmd — see b4q_cmd.h. The parser is the host driver's (b4q_host_main.c at a41f573), moved here unchanged in meaning; the
 * JSON writers produce the byte-identical lines that driver printed, so the records built from them do not change. */
#include "b4q_cmd.h"

#include <stdio.h>
#include <string.h>

int b4q_parse_tx(const char *cmd, b4q_tx_command *out)
{
    char kindname[16];
    unsigned long long g;
    int n = 0, i, pos = 0, k;
    const char *t;
    memset(out, 0, sizeof *out);
    if (strncmp(cmd, "TX ", 3) != 0) return -1;
    if (sscanf(cmd + 3, "%15s %llx %d%n", kindname, &g, &n, &pos) != 3) return -1;
    if (n < 0 || n > B4Q_MAX_STEPS) return -1;
    out->genome = (uint32_t)g;
    out->kind = strcmp(kindname, "root") == 0 ? B4Q_KIND_ROOT : strcmp(kindname, "inject") == 0 ? B4Q_KIND_INJECT : strcmp(kindname, "a5") == 0 ? B4Q_KIND_A5 : B4Q_KIND_NORMAL;
    k = 3 + pos;
    for (i = 0; i < n; i++) {
        unsigned long long w; int q = 0;
        if (sscanf(cmd + k, "%llx%n", &w, &q) != 1) return -1;
        out->steps[i] = (uint32_t)w; k += q;
    }
    out->n_steps = n;
    t = strstr(cmd, " TASK ");
    if (t) {
        int m = 0, q = 0, j;
        if (sscanf(t + 6, "%64s %d%n", out->task.digest, &m, &q) == 2 && m >= 0 && m <= B4Q_MAX_MASK) {
            const char *p = t + 6 + q;
            for (j = 0; j < m; j++) {
                int s, e, tv, w, qq = 0;
                if (sscanf(p, "%d %d %d %d%n", &s, &e, &tv, &w, &qq) != 4) break;
                out->task.step[j] = (uint8_t)s; out->task.elem[j] = (uint8_t)e; out->task.target[j] = (uint8_t)tv; out->task.weight[j] = (uint16_t)w; p += qq;
            }
            out->task.n = j;
        }
    }
    return 0;
}

static size_t put(char *out, size_t max, size_t at, const char *s)
{
    size_t n = strlen(s);
    if (at + n + 1 > max) return max;        /* saturate: the caller sees `max` and treats it as overflow */
    memcpy(out + at, s, n + 1);
    return at + n;
}

size_t b4q_open_json(const b4q_open_result *o, char *out, size_t max)
{
    char buf[512];
    int n = snprintf(buf, sizeof buf,
                     "{\"status\": %d, \"reason\": \"%s\", \"idcode\": %u, \"variant\": %u, \"timing\": %u, \"witness\": %u, \"status_word\": %u, "
                     "\"heartbeat\": %u, \"nonce\": \"%016llx\", \"startup_readback\": \"%s\"}",
                     o->status, o->reason ? o->reason : "", (unsigned)o->idcode, (unsigned)o->variant, (unsigned)o->timing, (unsigned)o->witness, (unsigned)o->status_word,
                     (unsigned)o->heartbeat, (unsigned long long)o->nonce, o->startup_readback_hex);
    if (n < 0 || (size_t)n >= sizeof buf || (size_t)n + 1 > max) return 0;
    memcpy(out, buf, (size_t)n + 1);
    return (size_t)n;
}

size_t b4q_tx_json(const b4q_tx_result *r, char *out, size_t max)
{
    char buf[1024];
    size_t at = 0;
    int i, n;
    n = snprintf(buf, sizeof buf,
                 "{\"status\": %d, \"phase\": \"%s\", \"reason\": \"%s\", \"fault_code\": %u, \"commit\": \"%s\", \"staged\": \"%s\", \"stream\": \"%s\", "
                 "\"pre_event\": \"%s\", \"post_event\": \"%s\", \"base_staged\": \"%s\", \"base_readback\": \"%s\", \"n_slots\": %d, \"slot_q\": [",
                 r->status, r->phase, r->reason ? r->reason : "", (unsigned)r->fault_code, r->commit_hex, r->staged_hex, r->stream_hex, r->pre_event_hex, r->post_event_hex,
                 r->base_staged_hex, r->base_readback_hex, r->n_slots);
    if (n < 0 || (size_t)n >= sizeof buf) return 0;
    at = put(out, max, at, buf);
    for (i = 0; i < r->n_slots; i++) { snprintf(buf, sizeof buf, "%s%u", i ? ", " : "", (unsigned)r->slot_q[i]); at = put(out, max, at, buf); }
    at = put(out, max, at, "], \"slot_in\": [");
    for (i = 0; i < r->n_slots; i++) { snprintf(buf, sizeof buf, "%s%u", i ? ", " : "", (unsigned)r->slot_in[i]); at = put(out, max, at, buf); }
    n = snprintf(buf, sizeof buf,
                 "], \"in_live_pre\": %u, \"witness_after_init\": %u, \"witness_after_restore\": %u, \"heartbeat_before\": %u, \"heartbeat_after\": %u, "
                 "\"base_state\": %u, \"status_final\": %u, \"steps_applied\": %d, \"has_fitness\": %d, \"fitness\": %d, \"task_digest\": \"%s\", "
                 "\"nonce_before\": \"%016llx\", \"nonce_after\": \"%016llx\"}",
                 (unsigned)r->in_live_pre, (unsigned)r->witness_after_init, (unsigned)r->witness_after_restore, (unsigned)r->heartbeat_before, (unsigned)r->heartbeat_after,
                 (unsigned)r->base_state, (unsigned)r->status_final, r->steps_applied, r->has_fitness, r->fitness, r->task_digest,
                 (unsigned long long)r->nonce_before, (unsigned long long)r->nonce_after);
    if (n < 0 || (size_t)n >= sizeof buf) return 0;
    at = put(out, max, at, buf);
    return at >= max ? 0 : at;
}
