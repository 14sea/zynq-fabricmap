/* b4q_cmd — see b4q_cmd.h. The parser checks the whole grammar before accepting anything (the owner's R5 of 2026-10-28: the
 * former host-driver parser normalised, truncated and defaulted); the JSON writers produce the byte-identical lines the host driver
 * printed at a41f573, so the records built from them do not change. */
#include "b4q_cmd.h"

#include <stdio.h>
#include <string.h>

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;                                           /* lower-case hex only: the host's own form */
}

int b4q_cmd_u32(const char **p, int base, unsigned long long max, unsigned long long *out)
{
    const char *s = *p;
    unsigned long long v = 0;
    int n = 0;
    for (;; s++, n++) {
        int d = (base == 16) ? hexval(*s) : ((*s >= '0' && *s <= '9') ? *s - '0' : -1);
        if (d < 0) break;
        if (n >= (base == 16 ? 8 : 10)) return -1;       /* more digits than the width allows: never truncated */
        v = v * (unsigned long long)base + (unsigned long long)d;
    }
    if (n == 0 || v > max) return -1;
    if (*s != 0 && *s != ' ') return -1;                 /* a field ends at a space or the end, nothing else */
    *out = v; *p = s;
    return 0;
}

static int spaces(const char **p)                        /* one or more spaces; 0 when none */
{
    const char *s = *p;
    if (*s != ' ') return 0;
    while (*s == ' ') s++;
    *p = s;
    return 1;
}

static int word(const char **p, const char *w)
{
    size_t n = strlen(w);
    if (strncmp(*p, w, n) != 0 || ((*p)[n] != ' ' && (*p)[n] != 0)) return 0;
    *p += n;
    return 1;
}

int b4q_parse_tx(const char *cmd, b4q_tx_command *out)
{
    const char *p = cmd;
    unsigned long long v;
    int i;
    memset(out, 0, sizeof *out);
    if (!word(&p, "TX") || !spaces(&p)) return -1;
    if (word(&p, "normal")) out->kind = B4Q_KIND_NORMAL;
    else if (word(&p, "root")) out->kind = B4Q_KIND_ROOT;
    else if (word(&p, "inject")) out->kind = B4Q_KIND_INJECT;
    else if (word(&p, "a5")) out->kind = B4Q_KIND_A5;
    else return -1;                                      /* an unknown kind is refused, never defaulted */
    if (!spaces(&p) || b4q_cmd_u32(&p, 16, 0xFFFFFFFFull, &v) != 0) return -1;
    if (v & ~(unsigned long long)B4Q_GENOME_MASK) return -1;   /* only the 21 configuration bits may be set */
    out->genome = (uint32_t)v;
    if (!spaces(&p) || b4q_cmd_u32(&p, 10, B4Q_MAX_STEPS, &v) != 0) return -1;
    out->n_steps = (int)v;
    if (out->kind == B4Q_KIND_ROOT && out->n_steps != 0) return -1;
    for (i = 0; i < out->n_steps; i++) {
        if (!spaces(&p) || b4q_cmd_u32(&p, 16, B4Q_STEP_MASK, &v) != 0) return -1;
        out->steps[i] = (uint32_t)v;
    }
    {
        const char *q = p;
        if (spaces(&q) && word(&q, "TASK")) {
            unsigned long long m;
            int j;
            p = q;
            if (!spaces(&p)) return -1;
            for (j = 0; j < 64; j++) if (hexval(p[j]) < 0) return -1;
            if (p[64] != ' ') return -1;
            memcpy(out->task.digest, p, 64); out->task.digest[64] = 0; p += 64;
            if (!spaces(&p) || b4q_cmd_u32(&p, 10, B4Q_MAX_MASK, &m) != 0) return -1;
            for (j = 0; j < (int)m; j++) {
                unsigned long long s, e, tv, w;
                if (!spaces(&p) || b4q_cmd_u32(&p, 10, (unsigned long long)out->n_steps, &s) != 0 || s == 0) return -1;   /* 1 .. n */
                if (!spaces(&p) || b4q_cmd_u32(&p, 10, 7, &e) != 0) return -1;
                if (!spaces(&p) || b4q_cmd_u32(&p, 10, 1, &tv) != 0) return -1;
                if (!spaces(&p) || b4q_cmd_u32(&p, 10, 65535, &w) != 0) return -1;
                out->task.step[j] = (uint8_t)s; out->task.elem[j] = (uint8_t)e; out->task.target[j] = (uint8_t)tv; out->task.weight[j] = (uint16_t)w;
            }
            out->task.n = (int)m;
        }
    }
    while (*p == ' ') p++;
    return *p == 0 ? 0 : -1;                             /* nothing but trailing spaces after the grammar */
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
