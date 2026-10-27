/* b4q_app — see b4q_app.h. */
#include "b4q_app.h"
#include "b4q_console.h"
#include "b4q_platform.h"
#include "b4q_wire.h"
#include "b4q_psmap.h"
#include "b4q_hal.h"
#include "b4q_tx.h"
#include "b4q_cmd.h"

#include <stdio.h>
#include <string.h>

static struct {
    b4q_app_summary sum;
    char token[B4Q_WIRE_TOKEN_HEX + 1];
    b4q_page page;
    uint32_t seq;                    /* this side's line sequence */
    uint32_t last_host_seq;
    const char *sign_why;            /* why the last b4q_sign returned -1 (reported on the EV line) */
} S;

static char g_out[12288];            /* one outbound framed line */
static char g_in[8192];              /* one inbound line */
static char g_plain[6144];           /* one decoded payload */
static char g_json[8192];            /* one result */

/* ---------------------------------------------------------------- emitting ----- */
static void emit_raw(const char *type, const uint8_t *plain, size_t n)
{
    size_t len = b4q_wire_frame(type, S.seq, S.token, plain, n, g_out, sizeof g_out), i;
    if (len == 0) {                  /* a line that does not fit is never truncated: a minimal NACK names it instead */
        len = b4q_wire_frame("NACK", S.seq, S.token, (const uint8_t *)"line too long", 13, g_out, sizeof g_out);
        S.sum.nacks++;
    }
    for (i = 0; i < len; i++) b4q_con_putc(g_out[i]);
    S.seq++; S.sum.lines++;
    b4q_plat_kick(); S.sum.kicks_requested++;      /* the one place the watchdog is kicked: after a framed line went out */
}

static void emit_text(const char *type, const char *text) { emit_raw(type, (const uint8_t *)text, strlen(text)); }

static void emit_end(b4q_end_kind kind, const char *reason)
{
    static const char *const NAME[] = {"NONE", "COMPLETED", "STOPPED", "PROTOCOL", "ABORT"};
    char buf[512];
    if (S.sum.end == B4Q_END_NONE) { S.sum.end = kind; S.sum.reason = reason; }   /* the first cause is the one recorded */
    snprintf(buf, sizeof buf, "{\"kind\": \"%s\", \"reason\": \"%s\", \"lines\": %lu, \"hb\": %lu, \"nacks\": %lu, \"sign_requests\": %lu, \"sign_replies\": %lu, "
             "\"transactions\": %lu, \"kicks\": %lu, \"watchdog_armed\": %d, \"opened\": %d}",
             NAME[S.sum.end], S.sum.reason ? S.sum.reason : "", (unsigned long)S.sum.lines, (unsigned long)S.sum.hb, (unsigned long)S.sum.nacks,
             (unsigned long)S.sum.sign_requests, (unsigned long)S.sum.sign_replies, (unsigned long)S.sum.transactions, (unsigned long)S.sum.kicks_requested,
             S.sum.watchdog_armed, S.sum.opened);
    emit_text("END", buf);
}

/* ---------------------------------------------------------------- receiving (bounded) ----- */
/* one line into g_in within `polls` console polls, a heartbeat every B4Q_APP_HB_EVERY; 1 a line, 0 the bound ran out, -1 a line too long (discarded) */
static int read_line(uint32_t polls)
{
    size_t n = 0;
    uint32_t i, since_hb = 0;
    for (i = 0; i < polls; i++) {
        if (!b4q_con_rx_ready()) {
            if (++since_hb >= B4Q_APP_HB_EVERY) { since_hb = 0; S.sum.hb++; emit_text("HB", ""); }
            continue;
        }
        {
            char c = b4q_con_getc();
            if (c == '\n') {
                if (n == 0) continue;                    /* an empty line: nothing */
                g_in[n] = 0; return 1;
            }
            if (n + 1 >= sizeof g_in) { n = 0; while (b4q_con_rx_ready() && b4q_con_getc() != '\n') { } return -1; }
            g_in[n++] = c;
        }
    }
    return 0;
}

/* the next well-formed host frame within `polls`; 1 with the frame and its payload decoded into g_plain; 0 the bound ran out;
 * -1 the session must end PROTOCOL (too many malformed lines) */
static int recv_frame(uint32_t polls, b4q_wire_frame_t *f)
{
    uint32_t nacks = 0;
    for (;;) {
        int r = read_line(polls);
        if (r == 0) return 0;
        if (r < 0) { emit_text("NACK", "line too long"); S.sum.nacks++; if (++nacks > B4Q_APP_MAX_NACKS) return -1; continue; }
        r = b4q_wire_parse(g_in, S.token, f);
        if (r != 0) {
            emit_text("NACK", r == -1 ? "bad crc" : r == -3 ? "wrong token" : "not a B4Q1 frame"); S.sum.nacks++;
            if (++nacks > B4Q_APP_MAX_NACKS) return -1;
            continue;
        }
        if (b4q_wire_payload(f, g_plain, sizeof g_plain) == (size_t)-1) {
            emit_text("NACK", "bad payload"); S.sum.nacks++;
            if (++nacks > B4Q_APP_MAX_NACKS) return -1;
            continue;
        }
        S.last_host_seq = f->seq;
        return 1;
    }
}

/* ---------------------------------------------------------------- the HAL's notary and events ----- */
int b4q_sign(const char *genome_hex, const char *nonce_hex, uint32_t words[24])
{
    char req[128];
    uint32_t req_seq = S.seq;
    int attempt;
    snprintf(req, sizeof req, "{\"genome\": \"%s\", \"nonce\": \"%s\", \"req\": %lu}", genome_hex, nonce_hex, (unsigned long)req_seq);
    S.sign_why = NULL;
    for (attempt = 0; attempt < B4Q_APP_SIGN_ATTEMPTS; attempt++) {
        b4q_wire_frame_t f;
        uint32_t polls = B4Q_APP_REPLY_POLLS;
        b4q_con_rx_flush();                              /* whatever waits is stale by construction (B1's rec-v3 rule) */
        emit_text("SIGNREQ", req); S.sum.sign_requests++;
        for (;;) {
            int r = recv_frame(polls, &f);
            unsigned long got_req = 0;
            if (r == 0) { S.sign_why = "no SIGNREPLY within the bound"; break; }
            if (r < 0) { S.sign_why = "the console produced only malformed lines"; emit_text("EV", "EV sign: the console produced only malformed lines"); return -1; }
            if (strcmp(f.type, "SIGNREPLY") != 0) { continue; }      /* another frame during the wait: not this reply */
            if (strncmp(g_plain, "OK ", 3) == 0 && sscanf(g_plain + 3, "%lu", &got_req) == 1 && got_req == req_seq) {
                const char *p = strchr(g_plain + 3, ' ');
                int i;
                if (!p) { S.sign_why = "a SIGNREPLY without words"; break; }
                for (i = 0; i < 24; i++) {
                    unsigned long w; int n = 0;
                    if (sscanf(p, " %lx%n", &w, &n) != 1) { S.sign_why = "a SIGNREPLY with too few words"; break; }
                    words[i] = (uint32_t)w; p += n;
                }
                if (i < 24) break;
                S.sum.sign_replies++;
                return 0;
            }
            if (strncmp(g_plain, "REFUSED ", 8) == 0 && sscanf(g_plain + 8, "%lu", &got_req) == 1 && got_req == req_seq) {
                S.sum.sign_replies++;
                S.sign_why = "the notary refused";
                snprintf(g_json, sizeof g_json, "EV sign: refused: %s", g_plain + 8);
                emit_text("EV", g_json);
                return -1;                                /* a refusal is final: no re-request */
            }
            /* a reply to another request (stale) or an unparsable one: keep waiting on the same bound */
        }
    }
    snprintf(g_json, sizeof g_json, "EV sign: no valid SIGNREPLY after %d attempts: %s", B4Q_APP_SIGN_ATTEMPTS, S.sign_why ? S.sign_why : "");
    emit_text("EV", g_json);
    return -1;
}

void b4q_emit(const char *line) { emit_text("EV", line); }

/* ---------------------------------------------------------------- the session ----- */
static int read_page(void)
{
    uint32_t words[B4Q_PAGE_WORDS], resp;
    int i;
    for (i = 0; i < B4Q_PAGE_WORDS; i++) {
        words[i] = b4q_rd32(B4Q_PSMAP_PAGE_ADDR + 4u * (uint32_t)i, &resp);
        if (resp != B4Q_RESP_OKAY) return -1;
    }
    return b4q_parse_page(words, &S.page);
}

static void ident(const b4q_open_result *o)
{
    char open_json[512];
    if (b4q_open_json(o, open_json, sizeof open_json) == 0) strcpy(open_json, "{}");
    snprintf(g_json, sizeof g_json,
             "{\"protocol\": \"%s\", \"token\": \"%s\", \"uboot_epoch\": %lu, \"app_image_sha_lo32\": %lu, \"carrier_sha256\": \"%s\", \"flags\": %lu, "
             "\"page_nonce_seen\": \"%016llx\", \"page_status_seen\": %lu, \"nonce_echo_equal\": %d, \"watchdog\": \"%s\", \"open\": %s}",
             B4Q_APP_PROTOCOL, S.page.token, (unsigned long)S.page.uboot_epoch, (unsigned long)S.page.app_image_sha_lo32, S.page.carrier_sha256, (unsigned long)S.page.flags,
             (unsigned long long)S.page.nonce_seen, (unsigned long)S.page.status_seen, S.page.nonce_seen == o->nonce,
             S.sum.watchdog_armed ? "armed" : ((S.page.flags & B4Q_PAGE_FLAG_WATCHDOG) ? "requested" : "off"), open_json);
    emit_text("IDENT", g_json);
}

void b4q_app_run(void)
{
    static b4q_tx_command c;
    static b4q_tx_result r;
    b4q_open_result o;
    memset(&S, 0, sizeof S);
    strcpy(S.token, B4Q_WIRE_ZERO_TOKEN);
    if (read_page() != 0) { emit_end(B4Q_END_STOPPED, "the identity page does not parse (magic / layout / checksum / reserved)"); return; }
    S.sum.page_ok = 1;
    strcpy(S.token, S.page.token);
    /* the watchdog is armed only once the page asked for it, before anything is signed; failing to arm it ends the session */
    if (S.page.flags & B4Q_PAGE_FLAG_WATCHDOG) {
        if (b4q_plat_watchdog_start() != 0) { emit_end(B4Q_END_STOPPED, "the watchdog could not be armed"); return; }
        S.sum.watchdog_armed = 1;
    }
    b4q_session_open(&o);
    S.sum.opened = (o.status == 0);
    ident(&o);
    if (o.status != 0) { emit_end(B4Q_END_STOPPED, "the opening was refused: nothing is signed"); return; }
    for (;;) {
        b4q_wire_frame_t f;
        int rc = recv_frame(B4Q_APP_IDLE_POLLS, &f);
        if (rc == 0) { emit_end(B4Q_END_STOPPED, "no host command within the idle bound"); return; }
        if (rc < 0) { emit_end(B4Q_END_PROTOCOL, "the console produced only malformed lines"); return; }
        if (strcmp(f.type, "QUIT") == 0) { emit_end(B4Q_END_COMPLETED, "the host closed the session"); return; }
        if (strcmp(f.type, "TX") == 0) {
            if (b4q_parse_tx(g_plain, &c) != 0) { emit_text("NACK", "malformed TX"); S.sum.nacks++; continue; }
            S.sum.transactions++;
            b4q_transaction(c.genome, c.steps, c.n_steps, c.kind, c.task.n ? &c.task : NULL, &r);
            if (b4q_tx_json(&r, g_json, sizeof g_json) == 0) { emit_end(B4Q_END_PROTOCOL, "a RESULT did not fit its line"); return; }
            emit_text("RESULT", g_json);
            continue;
        }
        emit_text("NACK", "unknown command"); S.sum.nacks++;
    }
}

void b4q_app_abort(const char *kind, uint32_t addr, uint32_t status)
{
    char buf[256];
    snprintf(buf, sizeof buf, "%s at %08lx status %08lx", kind, (unsigned long)addr, (unsigned long)status);
    S.sum.reason = NULL; S.sum.end = B4Q_END_NONE;      /* an abort is always recorded, whatever was in flight */
    emit_end(B4Q_END_ABORT, buf);
}

const b4q_app_summary *b4q_app_summary_get(void) { return &S.sum; }
