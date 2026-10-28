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
    uint32_t last_host_seq;          /* the last host sequence accepted; valid when have_host_seq */
    int have_host_seq;
    const char *sign_why;            /* why the last b4q_sign returned -1 (reported on the EV line) */
    int terminal;                    /* C4: the line sequence reached B4Q_APP_SEQ_LIMIT — the END PROTOCOL went out with that sequence; nothing is emitted or run after it */
} S;

static void end_json(char *buf, size_t max);

static char g_out[12288];            /* one outbound framed line */
static char g_in[8192];              /* one inbound line */
static char g_plain[6144];           /* one decoded payload */
static char g_json[8192];            /* one result */

/* ---------------------------------------------------------------- the receive budget (R1) ----- */
typedef struct { uint32_t left, spent; } b4q_budget;

/* one readiness poll charged to the budget; -1 when the budget is spent (or the session is terminal), else the console's answer */
static int poll_rx(b4q_budget *b)
{
    if (b->left == 0 || S.terminal) return -1;
    b->left--; b->spent++;
    return b4q_con_rx_ready();
}

/* ---------------------------------------------------------------- emitting ----- */
static void emit_raw(const char *type, const uint8_t *plain, size_t n)
{
    size_t len, i;
    if (S.terminal) return;                          /* after the terminal END nothing more is put on the console */
    if (S.seq >= B4Q_APP_SEQ_LIMIT) {                /* C4: the last usable sequence carries the terminal END, whatever this line was going to be */
        static char endbuf[640];
        S.terminal = 1;                              /* set first: the END built below is framed directly, never through this gate again */
        if (S.sum.end == B4Q_END_NONE) { S.sum.end = B4Q_END_PROTOCOL; S.sum.reason = "this side's line sequence is exhausted"; }
        end_json(endbuf, sizeof endbuf);
        len = b4q_wire_frame("END", S.seq, S.token, (const uint8_t *)endbuf, strlen(endbuf), g_out, sizeof g_out);
        for (i = 0; i < len; i++) b4q_con_putc(g_out[i]);
        S.sum.lines++; b4q_plat_kick(); S.sum.kicks_requested++;
        return;
    }
    len = b4q_wire_frame(type, S.seq, S.token, plain, n, g_out, sizeof g_out);
    if (len == 0) {                  /* a line that does not fit is never truncated: a minimal NACK names it instead */
        len = b4q_wire_frame("NACK", S.seq, S.token, (const uint8_t *)"line too long", 13, g_out, sizeof g_out);
        S.sum.nacks++;
    }
    for (i = 0; i < len; i++) b4q_con_putc(g_out[i]);
    S.seq++; S.sum.lines++;
    b4q_plat_kick(); S.sum.kicks_requested++;      /* the one place the watchdog is kicked: after a framed line went out */
}

static void emit_text(const char *type, const char *text) { emit_raw(type, (const uint8_t *)text, strlen(text)); }

static void end_json(char *buf, size_t max)
{
    static const char *const NAME[] = {"NONE", "COMPLETED", "STOPPED", "PROTOCOL", "ABORT"};
    snprintf(buf, max, "{\"kind\": \"%s\", \"reason\": \"%s\", \"lines\": %lu, \"hb\": %lu, \"nacks\": %lu, \"sign_requests\": %lu, \"sign_replies\": %lu, "
             "\"transactions\": %lu, \"kicks\": %lu, \"flushed\": %lu, \"stale_frames\": %lu, \"refused_tx\": %lu, \"watchdog_armed\": %d, \"opened\": %d, \"halted\": \"%s\"}",
             NAME[S.sum.end], S.sum.reason ? S.sum.reason : "", (unsigned long)S.sum.lines, (unsigned long)S.sum.hb, (unsigned long)S.sum.nacks,
             (unsigned long)S.sum.sign_requests, (unsigned long)S.sum.sign_replies, (unsigned long)S.sum.transactions, (unsigned long)S.sum.kicks_requested,
             (unsigned long)S.sum.flushed, (unsigned long)S.sum.stale_frames, (unsigned long)S.sum.refused_tx, S.sum.watchdog_armed, S.sum.opened, S.sum.halted ? S.sum.halted : "");
}

static void emit_end(b4q_end_kind kind, const char *reason)
{
    char buf[640];
    if (S.terminal) return;                          /* the terminal END already went out */
    if (S.sum.end == B4Q_END_NONE) { S.sum.end = kind; S.sum.reason = reason; }   /* the first cause is the one recorded */
    end_json(buf, sizeof buf);
    emit_text("END", buf);
}

/* ---------------------------------------------------------------- receiving (one budget per wait) ----- */
/* one line into g_in: 1 a line; 0 the budget is spent (whatever was read is dropped); -1 an oversize line discarded (the budget
 * charged for every byte); a heartbeat every B4Q_APP_HB_EVERY polls of the wait */
static int read_line(b4q_budget *b)
{
    size_t n = 0;
    uint32_t since_hb = 0;
    for (;;) {
        int ready = poll_rx(b);
        if (ready < 0) return 0;
        if (!ready) {
            if (++since_hb >= B4Q_APP_HB_EVERY) { since_hb = 0; S.sum.hb++; emit_text("HB", ""); }
            continue;
        }
        {
            char c = b4q_con_getc();
            if (c == '\n') {
                if (n == 0) continue;                    /* an empty line: nothing */
                g_in[n] = 0; return 1;
            }
            if (n + 1 >= sizeof g_in) {                  /* oversize: discard to the end of the line, every byte charged */
                for (;;) {
                    ready = poll_rx(b);
                    if (ready < 0) return 0;
                    if (ready && b4q_con_getc() == '\n') break;
                }
                return -1;
            }
            g_in[n++] = c;
        }
    }
}

/* the next well-formed, FRESH host frame within the wait's budget; 1 with the frame and its payload decoded into g_plain; 0 the
 * budget is spent; -1 the session must end PROTOCOL (too many malformed lines in one wait) */
static int recv_frame(b4q_budget *b, b4q_wire_frame_t *f)
{
    uint32_t nacks = 0;
    for (;;) {
        int r = read_line(b);
        if (r == 0) return 0;
        if (r < 0) { emit_text("NACK", "line too long"); S.sum.nacks++; if (++nacks > B4Q_APP_MAX_NACKS) return -1; continue; }
        r = b4q_wire_parse(g_in, S.token, f);
        if (r != 0) {
            emit_text("NACK", r == -1 ? "bad crc" : r == -3 ? "wrong token" : "not a B4Q1 frame"); S.sum.nacks++;
            if (++nacks > B4Q_APP_MAX_NACKS) return -1;
            continue;
        }
        if (S.have_host_seq && f->seq <= S.last_host_seq) {     /* R2: a duplicate or decreasing host sequence has no effect */
            emit_text("NACK", "stale sequence"); S.sum.nacks++; S.sum.stale_frames++;
            if (++nacks > B4Q_APP_MAX_NACKS) return -1;
            continue;
        }
        if (b4q_wire_payload(f, g_plain, sizeof g_plain) == (size_t)-1) {
            emit_text("NACK", "bad payload"); S.sum.nacks++;
            if (++nacks > B4Q_APP_MAX_NACKS) return -1;
            continue;
        }
        S.last_host_seq = f->seq; S.have_host_seq = 1;
        return 1;
    }
}

/* ---------------------------------------------------------------- the HAL's notary and events ----- */
/* "OK <req> <24 words>" / "REFUSED <req> <why>" parsed exactly (R5): 1 OK with the words, 2 REFUSED, 0 another request's reply
 * (ignored), -1 malformed (NACKed) */
static int parse_signreply(const char *s, uint32_t req_seq, uint32_t words[24])
{
    const char *p;
    unsigned long long v;
    int i;
    if (strncmp(s, "OK ", 3) == 0) p = s + 3;
    else if (strncmp(s, "REFUSED ", 8) == 0) p = s + 8;
    else return -1;
    if (b4q_cmd_u32(&p, 10, 0xFFFFFFFFull, &v) != 0) return -1;
    if ((uint32_t)v != req_seq) return 0;
    if (s[0] == 'R') return 2;                           /* the refusal's reason is free text */
    for (i = 0; i < 24; i++) {
        if (*p != ' ') return -1;
        while (*p == ' ') p++;
        if (b4q_cmd_u32(&p, 16, 0xFFFFFFFFull, &v) != 0) return -1;
        words[i] = (uint32_t)v;
    }
    while (*p == ' ') p++;
    return *p == 0 ? 1 : -1;                             /* exactly 24 words, nothing after */
}

int b4q_sign(const char *genome_hex, const char *nonce_hex, uint32_t words[24])
{
    char req[128];
    uint32_t req_seq = S.seq;
    int attempt;
    S.sign_why = NULL;
    if (S.terminal) return -1;                           /* C4: nothing is requested after the terminal END */
    if (S.sum.halted) {                                  /* R3: a halted session requests no signature */
        snprintf(g_json, sizeof g_json, "EV sign: refused by this side: the session is halted (%s)", S.sum.halted);
        emit_text("EV", g_json);
        return -1;
    }
    snprintf(req, sizeof req, "{\"genome\": \"%s\", \"nonce\": \"%s\", \"req\": %lu}", genome_hex, nonce_hex, (unsigned long)req_seq);
    for (attempt = 0; attempt < B4Q_APP_SIGN_ATTEMPTS; attempt++) {
        b4q_wire_frame_t f;
        b4q_budget b = {B4Q_APP_REPLY_POLLS, 0};         /* one budget for the whole attempt: every poll, every line, every byte */
        S.sum.flushed += (uint32_t)b4q_con_rx_flush();   /* whatever waits is stale by construction (B1's rec-v3 rule); bounded by the primitive */
        emit_text("SIGNREQ", req); S.sum.sign_requests++;
        for (;;) {
            int r = recv_frame(&b, &f);
            if (r == 0) { S.sign_why = "no SIGNREPLY within the attempt's budget"; break; }
            if (r < 0) { S.sign_why = "the console produced only malformed lines"; emit_text("EV", "EV sign: the console produced only malformed lines"); return -1; }
            if (strcmp(f.type, "SIGNREPLY") != 0) continue;       /* another frame during the wait: charged, not this reply */
            r = parse_signreply(g_plain, req_seq, words);
            if (r == 1) { S.sum.sign_replies++; return 0; }
            if (r == 2) {
                S.sum.sign_replies++;
                S.sign_why = "the notary refused";
                snprintf(g_json, sizeof g_json, "EV sign: refused: %s", g_plain + 8);
                emit_text("EV", g_json);
                return -1;                                /* a refusal is final: no re-request */
            }
            if (r < 0) { emit_text("NACK", "bad SIGNREPLY"); S.sum.nacks++; }
            /* r == 0: a reply to another request (stale): charged, ignored, the wait continues on the same budget */
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

static b4q_tx_command g_cmd;

/* the wait for the next command on ONE budget: a frame that is not a command (another type, a malformed TX, a TX on a halted
 * session) is NACKed by name and the wait continues on the same budget; at most B4Q_APP_MAX_NACKS such refusals per wait.
 * 1 a TX parsed into g_cmd on a session that may run it; 2 QUIT; 0 the budget is spent; -1 the session must end PROTOCOL */
static int wait_command(b4q_budget *b, b4q_wire_frame_t *f)
{
    uint32_t refusals = 0;
    for (;;) {
        int rc = recv_frame(b, f);
        if (rc <= 0) return rc;
        if (strcmp(f->type, "QUIT") == 0) return 2;
        if (strcmp(f->type, "TX") == 0) {
            if (S.sum.halted) {                          /* R3: nothing further is run or signed after a transaction that did not close */
                snprintf(g_json, sizeof g_json, "halted: %s: nothing further is signed without a ruling", S.sum.halted);
                emit_text("NACK", g_json); S.sum.nacks++; S.sum.refused_tx++;
            } else if (b4q_parse_tx(g_plain, &g_cmd) != 0) {
                emit_text("NACK", "malformed TX"); S.sum.nacks++;
            } else return 1;
        } else { emit_text("NACK", "unknown command"); S.sum.nacks++; }
        if (++refusals > B4Q_APP_MAX_NACKS) return -1;
    }
}

void b4q_app_run(void)
{
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
        b4q_budget b = {B4Q_APP_IDLE_POLLS, 0};          /* one budget per wait for the next command: renewed only after a transaction ran */
        int rc;
        if (S.terminal) return;                          /* the terminal END already went out (inside a wait or a transaction) */
        rc = wait_command(&b, &f);
        if (S.terminal) return;
        if (rc == 0) { emit_end(B4Q_END_STOPPED, "no host command within the idle bound"); return; }
        if (rc < 0) { emit_end(B4Q_END_PROTOCOL, "the console produced only malformed or unknown lines"); return; }
        if (rc == 2) { emit_end(B4Q_END_COMPLETED, "the host closed the session"); return; }
        /* rc == 1: a TX that parsed, on a session that may run it */
        S.sum.transactions++;
        b4q_transaction(g_cmd.genome, g_cmd.steps, g_cmd.n_steps, g_cmd.kind, g_cmd.task.n ? &g_cmd.task : NULL, &r);
        if (r.status != 0) S.sum.halted = r.reason ? r.reason : "the transaction did not close";
        if (S.terminal) return;                          /* the sequence ran out inside the transaction: its END went out, no RESULT follows */
        if (b4q_tx_json(&r, g_json, sizeof g_json) == 0) { emit_end(B4Q_END_PROTOCOL, "a RESULT did not fit its line"); return; }
        emit_text("RESULT", g_json);
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
int b4q_app_terminal(void) { return S.terminal; }
