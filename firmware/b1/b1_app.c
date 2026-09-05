/* b1_app — the B1 standalone application: the board half of the autonomous-cartography
 * session (docs/b1_architecture.md), a versioned SUCCESSOR of the instrument's p3_app.c
 * (zynq-psoracle 689dde1; firmware/b1/IMPORT.json names it as `derived_to` this file).
 *
 * ─── STANDING OF THIS FILE ────────────────────────────────────────────────────────────
 * COMPILED, NOT BOARD-RUN (B1 v2 package, 2026-09-05; DRAFT / NO BOARD RULING). Cross-compiled
 * for cortex-a9 into firmware/b1/bsp/out/b1_app.bin with the pinned xPack arm-none-eabi-gcc
 * 14.2.1 against the instrument's standalone BSP; two clean builds are byte-identical
 * (evidence/b1/build_evidence.json). It has NEVER been run on a board; the first board
 * contact is the carrier qualification session under its own ruling
 * (docs/b1_carrier_qualification.md §3), then the mapping session under its own.
 * What IS proven host-side: p3_derive.c (verbatim: every hash, the stream builder and
 * parser, the readback stream, base64url, the nonce model, the identity page) against the
 * instrument's Python reference; b1_carto.c + b1_orch.c (C == Python twin over the fixtures
 * and the session order, tests/test_b1_twin.py, test_b1_session.py); the wire bytes this file
 * emits through b1_wire.c against the instrument's validator (tests/test_b1_wire.py). This
 * file is deliberately thin for that reason: HAL plus state machine, checked by source audit
 * and by the MMIO allowlist against the B1 RTL decode (tests/test_b1_carrier.py).
 * ──────────────────────────────────────────────────────────────────────────────────────
 *
 * The diff to p3_app.c is the search → orchestrator/cartographer replacement, the `carto`
 * block in every record, and the VARIANT read into the IDENT; where this file and the Python
 * reference (host/b1_carto.session_run) disagree, the Python is the specification. The
 * session:
 *
 *   identity → cartographer init + bind → opening baseline → [ propose → notary (ZERO
 *   tables) → stage → link 2 → DMA → link 3 → ARM → raw readout → observe ]* → closing
 *   baseline (= restore) → closing unsigned ARM
 *
 * ending in exactly one of COMPLETED / STOPPED / PROTOCOL. CRASHED is the watchdog's and by
 * definition leaves nothing behind but what the collector already received. An unscored
 * candidate ends the epoch: nothing is re-issued and no closing baseline follows.
 */

#include "p3_data.h"
#include "p3_derive.h"
/* The wire serialisation lives in its own pure unit so the host contract test can compile
 * it and feed the bytes this application emits to the real validator
 * (tests/test_firmware_wire_contract.py). Nothing below builds a payload by hand. */
#include "b1_wire.h"
/* The REC transaction (rec-v3) is a pure unit too: the same source is compiled on the host
 * and driven over a pipe by tests/test_firmware_wire_contract.py::RecWireContract. */
#include "p3_rectx.h"
#include "p3_pull.h"
#include "b1_orch.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* BSP: standalone_v9_4 with the console UART as stdout. `outbyte`/`inbyte` are the only
 * console primitives used, so no UART register appears in this file. */
#include "xil_io.h"
#include "xil_mmu.h"
#include "xparameters.h"
#include "xscuwdt.h"
#include "xtime_l.h"

extern void outbyte(char c);
extern char inbyte(void);
extern int console_rx_ready(void); /* BSP glue (firmware/bsp/src/console.c): RX FIFO non-empty? */
extern int console_rx_flush(void); /* BSP glue: discard stale RX bytes before a SIGNREQ (rec-v3) */

/* ───────────────────────────────── memory map (docs/l5_design.md §2) ───────────────── */

#define P3_CMD_BUF 0x10200000u   /* readback command buffer, 43 words       */
#define P3_DST_BUF 0x10300000u   /* readback destination buffer, 202 words  */
#define P3_WR_BUF 0x10400000u    /* staging, 3 x 534 words (psmap's WR_BUF) */
#define P3_PAGE_ADDR 0x10440000u /* identity page, 24 words                 */
#define P3_RING_ADDR 0x10800000u /* evidence ring, W entries                */
#define P3_RING_W 512
#define P3_DROP_BUDGET 16 /* manifests/l5_manifest.json protocol.crc_drop_budget_per_session */

#define P3_MB (1024u * 1024u)
#define P3_NONCACHEABLE 0x14de2u /* Xil_SetTlbAttributes: strongly-ordered, non-cacheable */
#define P3_SENTINEL 0xA5A5A5A5u
/* D-s1 (L6 prereg §3, owner 2026-09-01): the A9 private watchdog ON, 30.0 s, flag-gated.
 * PINNED IN manifests/l6_manifest.json pinned_at_build: prescaler 7 → the timer counts at
 * PERIPHCLK / 8 = 333 333 343 / 8 Hz (PERIPHCLK board-confirmed 2026-09-01-05), and
 * 30.0 s × 41 666 667.9 Hz − 1 = 1 250 000 035. The ACTUAL value written is what the
 * manifest and tests/test_firmware_audit.py pin, not the derivation. Watchdog (reset)
 * mode, not timer mode: a timeout resets the PS and the collector sees the banner. */
#define P3_WDT_LOAD 1250000035u
#define P3_WDT_PRESCALER 7u

/* ───────────────────────────── the PL's AXI window (L1 map) ───────────────────────── */

#define P3_AXI_BASE 0x43C00000u
#define P3_CTRL 0x2000u
#define P3_STATUS 0x2004u
#define P3_FAULT 0x2008u
#define P3_SCORE0 0x2010u
#define P3_HEARTBEAT 0x2028u
#define P3_NONCE_LO 0x202Cu
#define P3_NONCE_HI 0x2030u
#define P3_PAYLOAD0 0x2100u /* 20 write-only staging words */
#define P3_TAG0 0x2150u     /* 4 write-only tag words      */
#define P3_HW_COMMIT0 0x2200u
#define P3_READOUT0 0x2240u

/* The MAC key register is provisioned by the gate signer over the JTAG DAP mem-AP and is
 * absent from this map BY CONSTRUCTION: no constant here names it, and `axi_write()`
 * refuses any offset it does not recognise. `tests/test_firmware_audit.py` asserts that no
 * line of this file names those offsets. */

#define P3_ST_GATE_BUSY 0u   /* docs/l1_design.md register map; rtl/p3_axil.v status[0] */
#define P3_ST_FAULT 1u
#define P3_ST_CFG_VALID_HW 2u
#define P3_ST_SCORER_BUSY 3u
#define P3_ST_SCORER_DONE 4u
#define P3_ST_RECOVERY 7u
#define P3_ST_ALIVE 8u
#define P3_ST_KEY_LOADED 11u
#define P3_ST_RESERVED 0xF8000000u
#define P3_ARM_STROBE (1u << 6)
#define P3_VARIANT 0x2034u          /* B1 carrier: the gate-contract word (read-only) */
#define B1_VARIANT_WORD 0x42310001u /* "B1", contract v1: SEMANTIC_GATE = 0 */
/* The bound on the post-strobe STATUS poll. The gate is done in < 200 cycles at 50 MHz
 * (host/l3_runner.py, board-observed at L3); one Strongly-Ordered AXI read from the A9
 * takes on the order of 100 ns, so this bound is ~0.1-0.3 s of polling — four to five
 * orders of magnitude above the gate's own time, and far below the collector's 30 s
 * silence threshold. It is a count, not a clock: the global timer's rate follows
 * CPU_6x4x, and liveness must not depend on that constant (see heartbeat()). */
#define P3_SETTLE_POLLS_MAX 1000000u
/* The bound on waiting for the host's next AUDITGET/AUDITDONE/AUDITABORT during an audit
 * pull (L6, docs/l6_audit_pull_design.md): polls of the RX FIFO, a COUNT not a clock, as
 * the settle poll is. One strongly-ordered UART status read is ~100–200 ns, so this is a
 * few seconds — below the collector's 30 s silence rule and the 30 s watchdog (which
 * remain the last resort for a stall inside a line). A lost host frame therefore never
 * leaves the application waiting forever: the pull aborts and no ARM is attempted. */
#define P3_PULL_IDLE_POLLS 50000000u
/* The bound on waiting for the host's RECACK/RECGET after a record (rec-v3): the same count
 * as the pull's. When it runs out the SAME bytes are sent again, at most P3_RECTX_ATTEMPTS
 * times in all; without an acknowledgement the epoch stops (STOP_REC) — the next candidate
 * is never proposed on an unconfirmed record. */
#define P3_REC_IDLE_POLLS 50000000u
/* rel-v4 (prereg v0.6 draft §2.6p, the board-bound contract): every transaction wait —
 * IDENT, SIGNREQ, the audit pull, REC, TERM — is bounded by the GLOBAL TIMER as well as by
 * its poll count; whichever runs out first ends the wait. The tick bound is the wall-time
 * authority: P3_BOUND_S seconds × COUNTS_PER_SECOND (the global timer runs at CPU/2 =
 * 333,333,343 Hz on the pinned 6:2:1 clock, which the runner verifies from CPU_CLK_CTRL
 * before every session), so every bound is ≤ P3_BOUND_S s of wall time on that clock —
 * below the host's BOARD_BOUND_WALL_MAX_S (10 s) that its 22 s TERM linger derives from.
 * The poll counts stay as a termination backstop for a timer that does not advance; they
 * are NOT the wall-time proof (one UART status read is ~100–200 ns, never pinned). */
#define P3_BOUND_S 8u
#define P3_BOUND_TICKS ((uint64_t)P3_BOUND_S * (uint64_t)COUNTS_PER_SECOND)
#define P3_IDENT_IDLE_POLLS 100000000u
#define P3_SIGN_IDLE_POLLS 100000000u
#define P3_TERM_IDLE_POLLS 100000000u
/* (rel-v4: the stale-acknowledgement rule of the sign wait is p3_rectx.h P3_RECTX_PREV_ACK_LIMIT) */

#define SLCR_PSS_IDCODE 0xF8000530u /* READ ONLY — this application writes no SLCR word */
#define P3_IDCODE_MASK 0x0FFFFFFFu

/* ───────────────────────────── DEVCFG (zynq-psmap §8a, verbatim) ──────────────────── */

#define DEVCFG_BASE 0xF8007000u
#define DEVCFG_CTRL (DEVCFG_BASE + 0x000u)
#define DEVCFG_INT_STS (DEVCFG_BASE + 0x00Cu)
#define DEVCFG_DMA_SRC_ADDR (DEVCFG_BASE + 0x018u)
#define DEVCFG_DMA_DEST_ADDR (DEVCFG_BASE + 0x01Cu)
#define DEVCFG_DMA_SRC_LEN (DEVCFG_BASE + 0x020u)
#define DEVCFG_DMA_DEST_LEN (DEVCFG_BASE + 0x024u)

#define PCAP_ENDPOINT 0xFFFFFFFFu
#define DMA_HOLD_TAG 0x1u
#define INT_STS_D_P_DONE (1u << 12)
#define INT_STS_DMA_DONE (1u << 13)
#define INT_STS_ERROR_MASK 0x00F4C840u
#define INT_STS_CLEAR_MASK (INT_STS_ERROR_MASK | INT_STS_D_P_DONE | INT_STS_DMA_DONE)
#define CTRL_PCAP_MASK 0x0C000000u /* PCAP_PR | PCAP_MODE */
#define DMA_SPIN_LIMIT 1000000

/* The FOUR legal DMA transactions (psmap §6a: the unit of adjudication is the whole
 * transaction, never a field). This application issues nothing else. */
typedef struct {
    uint32_t src, dst, src_len, dst_len;
} p3_dma;

static const p3_dma DMA_WRITE_ENVELOPE = {P3_WR_BUF | DMA_HOLD_TAG, PCAP_ENDPOINT,
                                          P3_STREAM_WORDS, 0};
static const p3_dma DMA_READ_COMMAND = {P3_CMD_BUF | DMA_HOLD_TAG, PCAP_ENDPOINT,
                                        P3_READBACK_CMD_WORDS, 0};
static const p3_dma DMA_READ_FRAME = {PCAP_ENDPOINT, P3_DST_BUF | DMA_HOLD_TAG, 0,
                                      P3_READBACK_WORDS};
static const p3_dma DMA_READ_CLEANUP = {P3_CMD_BUF | DMA_HOLD_TAG, PCAP_ENDPOINT,
                                        P3_CLEANUP_WORDS, 0};

/* ───────────────────────────────── epoch taxonomy (§3c) ───────────────────────────── */

typedef enum { P3_RUNNING = 0, P3_COMPLETED, P3_STOPPED, P3_PROTOCOL } p3_end_kind;

static const char *const END_NAME[] = {"RUNNING", "COMPLETED", "STOPPED", "PROTOCOL"};

static struct {
    p3_end_kind kind;
    const char *reason;
    uint32_t seq;
    p3_identity_page page;
    uint32_t frames[P3_TARGET_FRAMES][P3_FRAME_WORDS];
    uint32_t readback[P3_TARGET_FRAMES][P3_FRAME_WORDS];
    uint32_t scored, refused;  /* the TERM's audit block comes from p3_wire_tally(), not here */
    int audit_requested;       /* an AUDITREQ arrived in this candidate's exchange */
    int audit_served;          /* the host pulled every chunk and sent AUDITDONE for … */
    uint32_t audit_served_seq; /* … this candidate (rule ix: the mark means served AND done) */
    uint32_t audit_chunks_served; /* chunk replies sent in this candidate's pull (retries included) */
    const char *audit_stop_why;   /* why the pull ended without AUDITDONE, for the STOP_AUDIT record */
    int rec_control;              /* identity page flags.bit4: the forced REC-retry control (rec-v3) */
    int sign_control;             /* identity page flags.bit5: the forced SIGNREQ-retry control (rel-v4) */
    uint32_t hb_i;                /* rel-v4: the heartbeat index within the current record, 0..15 */
    uint32_t sign_attempts, sign_gets; /* SIGNREQ transmissions and SIGNGETs answered, whole session */
    int have_closing_control;     /* rel-v4: the closing control's fields, repeated in the TERM */
    uint64_t close_nb, close_na;
    uint32_t close_fault, close_status;
    const char *rec_stop_why;     /* set when a record's transaction was not acknowledged */
    uint32_t rec_attempts, rec_gets; /* transmissions and RECGETs answered, whole session */
    uint32_t crc_dropped;
    uint32_t envelope_int_sts[P3_ENVELOPE_COUNT];
    int closing_restore, closing_baseline, closing_unsigned;
    int have_last_reply;
    char last_commit[65];
    char last_tables[6][17];
    XScuWdt wdt;
    int wdt_started; /* set ONLY after CfgInitialize → SetControlReg → LoadWdt → Start; the
                      * kick looks at this, never at the flag: the IDENT frame (and its
                      * kick) goes out BEFORE the watchdog is initialised, and restarting an
                      * uninitialised instance (BaseAddr 0, IsReady unset) asserts forever
                      * (review 2026-09-01: the first L6 image hung after IDENT) */
} S;

static int tx_run_line(size_t n, uint32_t seq, const p3_tx_kinds *kinds, int corrupt_first,
                       uint32_t idle_polls, p3_rectx_result *r);

static void p3_stop(p3_end_kind kind, const char *reason)
{
    if (S.kind == P3_RUNNING) { /* the first cause is the one recorded */
        S.kind = kind;
        S.reason = reason;
    }
}

/* ───────────────────────────────── register access ────────────────────────────────── */

static int axi_readable(uint32_t off)
{
    if (off == P3_STATUS || off == P3_FAULT || off == P3_HEARTBEAT || off == P3_NONCE_LO ||
        off == P3_NONCE_HI || off == P3_VARIANT)   /* B1: VARIANT (0x2034) is decoded read-only by rtl/b1/b1_axil.v */
        return 1;
    /* CTRL (0x2000) is deliberately ABSENT: rtl/p3_axil.v decodes it write-only, so a read
     * is SLVERR and on this board a data abort. Session 2 died on exactly that after this
     * allowlist was widened for instrumentation. The RTL contract is not expanded to suit
     * an instrument; the instrument records the value as unavailable instead. */
    if ((off & 3u) != 0u)
        return 0;
    if (off >= P3_SCORE0 && off < P3_SCORE0 + 6u * 4u)
        return 1;
    if (off >= P3_HW_COMMIT0 && off < P3_HW_COMMIT0 + 8u * 4u)
        return 1;
    if (off >= P3_READOUT0 && off < P3_READOUT0 + 12u * 4u)
        return 1;
    return 0;
}

static int axi_writable(uint32_t off)
{
    if (off == P3_CTRL)
        return 1;
    if ((off & 3u) != 0u)
        return 0;
    if (off >= P3_PAYLOAD0 && off < P3_PAYLOAD0 + 20u * 4u)
        return 1;
    if (off >= P3_TAG0 && off < P3_TAG0 + 4u * 4u)
        return 1;
    return 0;
}

/* An undecoded access is SLVERR and, on this board, a data abort (zynq-psmap P2), so the
 * allowlist is checked at the accessor rather than trusted from the call sites. */
static uint32_t axi_read(uint32_t off)
{
    if (!axi_readable(off)) {
        p3_stop(P3_STOPPED, "STOP_AXI: read outside the pinned map");
        return 0;
    }
    return Xil_In32(P3_AXI_BASE + off);
}

static void axi_write(uint32_t off, uint32_t value)
{
    if (!axi_writable(off)) {
        p3_stop(P3_STOPPED, "STOP_AXI: write outside the pinned map");
        return;
    }
    Xil_Out32(P3_AXI_BASE + off, value);
}

static uint64_t pl_nonce(void)
{
    uint32_t lo = axi_read(P3_NONCE_LO);
    uint32_t hi = axi_read(P3_NONCE_HI);
    return (uint64_t)lo | ((uint64_t)hi << 32);
}

/* ─────────────────────────────────── console framing (§5b) ────────────────────────── */

static char g_line[8192];   /* one inbound line            */
static char g_json[4096];   /* one decoded payload         */
static char g_payload[4096];/* one outbound payload, plain */
static char g_encoded[6144];/* one outbound payload, b64   */
static char g_body[7168];   /* one outbound line body      */
static char g_rec_line[7168];    /* the record's framed line: built ONCE, resent verbatim (rec-v3) */
static char g_rec_scratch[7168]; /* the control's corrupted copy of attempt 1 */
static char g_tx_line[7168];     /* rel-v4: the IDENT / SIGNREQ / TERM line of the transaction in flight, built once */
static char g_ready_line[7168];  /* rel-v4: the AUDIT_READY line, built once, resent verbatim on the bound */
static uint32_t g_tx_idle_polls; /* the poll cap of the transaction in flight (its clock bound is P3_BOUND_TICKS) */

static void put_str(const char *s)
{
    while (*s)
        outbyte(*s++);
}

static void kick_watchdog(void)
{
    if (S.wdt_started)
        XScuWdt_RestartWdt(&S.wdt); /* after a framed line (§6a); only once initialised */
}

/* `P3L5 <type> <seq> <token(32 hex)> <payload> <crc32>` — the FULL token in every line.
 * The framing itself is p3_wire's, so the host contract test judges these exact bytes. */
static size_t build_frame(const char *type, uint32_t seq, const char *payload, char *out, size_t max)
{
    size_t n = p3_wire_line(type, seq, S.page.token, payload, out, max);

    if (n == 0u)
        p3_stop(P3_PROTOCOL, "PROTOCOL_FRAME: outbound line too long");
    return n;
}


/* Encodes `plain_len` bytes of g_payload into a framed line in `out`. A builder that
 * overflowed returns 0 and we refuse to emit a truncated line rather than call it evidence. */
static size_t build_payload_frame(const char *type, uint32_t seq, size_t plain_len, char *out, size_t max)
{
    if (plain_len == 0u) {
        p3_stop(P3_PROTOCOL, "PROTOCOL_FRAME: payload builder overflowed");
        return 0u;
    }
    p3_base64url((const uint8_t *)g_payload, plain_len, g_encoded);
    return build_frame(type, seq, g_encoded, out, max);
}

/* Encodes `plain_len` bytes of g_payload and sends them as one frame. */
static void send_payload(const char *type, uint32_t seq, size_t plain_len)
{
    if (build_payload_frame(type, seq, plain_len, g_body, sizeof(g_body)) == 0u)
        return;
    put_str(g_body);
    kick_watchdog();
}

/* A liveness beat at every progress point of a candidate. The collector calls three
 * heartbeat intervals of silence a CRASH (§3c), and a candidate is otherwise silent from
 * the sign reply until its record. This is deliberately driven by PROGRESS, not by a
 * clock: the global timer's rate follows CPU_6x4x, which is still an assumption until the
 * pre-board CPU_CLK_CTRL read, and liveness must not depend on an unverified constant. */
static void heartbeat(void)
{
    /* rel-v4: every heartbeat carries its index within the record, so a lost one is
     * identified and budgeted and a duplicated one is harmless (prereg v0.6 draft §2.6n) */
    if (S.kind == P3_RUNNING)
        send_payload("HB", S.seq, p3_wire_hb(S.hb_i++, g_payload, sizeof(g_payload)));
}

/* (rel-v4: the L5 blocking recv_line is gone — every wait for a host line is the bounded,
 * timed receiver below; the watchdog is no longer what ends a stalled wait) */

/* Verifies magic, CRC and token; writes the frame's type into `type_out` and its seq into
 * `seq_out`, and returns the payload field (still base64url). Mutates `line`. */
static const char *parse_frame_any(char *line, char *type_out, size_t type_max, uint32_t *seq_out)
{
    char *last = strrchr(line, ' ');
    char expect[16];
    char *f[5];
    size_t i, k = 0;
    if (!last)
        return NULL;
    *last = 0; /* the CRC covers everything before the final field */
    snprintf(expect, sizeof(expect), "%08lx",
             (unsigned long)p3_crc32((const uint8_t *)line, strlen(line)));
    if (strcmp(expect, last + 1) != 0)
        return NULL;
    f[k++] = line;
    for (i = 0; line[i] && k < 5; i++)
        if (line[i] == ' ') {
            line[i] = 0;
            f[k++] = line + i + 1;
        }
    if (k != 5 || strcmp(f[0], "P3L5") != 0)
        return NULL;
    if (strcmp(f[3], S.page.token) != 0)
        return NULL;
    *seq_out = (uint32_t)strtoul(f[2], NULL, 10);
    snprintf(type_out, type_max, "%s", f[1]);
    return f[4];
}


/* ─────────────────────────── minimal JSON field extraction ────────────────────────── */
/* The relay emits canonical compact JSON (sorted keys, no spaces) whose schema is pinned
 * in docs/contracts.md, so a key scan suffices — and every field is length- and
 * alphabet-checked rather than trusted. */

static int is_lower_hex(char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }

static int json_hex(const char *json, const char *key, char *out, size_t len)
{
    const char *p = strstr(json, key);
    size_t i;
    if (!p)
        return -1;
    p += strlen(key);
    for (i = 0; i < len; i++) {
        if (!is_lower_hex(p[i]))
            return -1;
        out[i] = p[i];
    }
    out[len] = 0;
    return p[len] == '"' ? 0 : -1;
}

/* an unsigned integer field: digits after the key, terminated by , or } */
static int json_uint(const char *json, const char *key, uint32_t *out)
{
    const char *p = strstr(json, key);
    uint32_t v = 0;
    int n = 0;
    if (!p)
        return -1;
    p += strlen(key);
    while (*p >= '0' && *p <= '9' && n < 10) {
        v = v * 10u + (uint32_t)(*p - '0');
        p++;
        n++;
    }
    if (n == 0 || (*p != ',' && *p != '}'))
        return -1;
    *out = v;
    return 0;
}

/* the six tables are one JSON array; they must be walked in order, not searched for */
static int json_tables(const char *json, char tables[6][17])
{
    static const char key[] = "\"expected_tables\":[";
    const char *p = strstr(json, key);
    int i, k;
    if (!p)
        return -1;
    p += sizeof(key) - 1;
    for (i = 0; i < 6; i++) {
        if (*p++ != '"')
            return -1;
        for (k = 0; k < 16; k++) {
            if (!is_lower_hex(p[k]))
                return -1;
            tables[i][k] = p[k];
        }
        tables[i][16] = 0;
        p += 16;
        if (*p++ != '"')
            return -1;
        if (i < 5 && *p++ != ',')
            return -1;
    }
    return *p == ']' ? 0 : -1;
}

/* ───────────────────────────────── DMA (the four tuples) ──────────────────────────── */

static int devcfg_wait_done(void)
{
    int spins;
    for (spins = 0; spins < DMA_SPIN_LIMIT; spins++) {
        uint32_t sts = Xil_In32(DEVCFG_INT_STS);
        if (sts & INT_STS_ERROR_MASK) {
            p3_stop(P3_STOPPED, "DEVCFG error bit after a DMA");
            return -1;
        }
        if (sts & INT_STS_D_P_DONE) /* D_P_DONE: the DMA *and* PCAP; DMA_DONE alone is not */
            return 0;
    }
    p3_stop(P3_STOPPED, "DEVCFG D_P_DONE never asserted");
    return -1;
}

static int devcfg_dma(const p3_dma *t, uint32_t src_override)
{
    if ((Xil_In32(DEVCFG_CTRL) & CTRL_PCAP_MASK) != CTRL_PCAP_MASK) {
        p3_stop(P3_STOPPED, "DEVCFG CTRL is not in the required PCAP mode");
        return -1;
    }
    Xil_Out32(DEVCFG_INT_STS, INT_STS_CLEAR_MASK);
    if (Xil_In32(DEVCFG_INT_STS) & INT_STS_D_P_DONE) {
        p3_stop(P3_STOPPED, "DEVCFG INT_STS would not clear");
        return -1;
    }
    /* the four registers in the pinned order; the DEST_LEN write queues the command */
    Xil_Out32(DEVCFG_DMA_SRC_ADDR, src_override ? src_override : t->src);
    Xil_Out32(DEVCFG_DMA_DEST_ADDR, t->dst);
    Xil_Out32(DEVCFG_DMA_SRC_LEN, t->src_len);
    Xil_Out32(DEVCFG_DMA_DEST_LEN, t->dst_len);
    return devcfg_wait_done();
}

/* ───────────────────────────────── identity (§3b) ─────────────────────────────────── */

/* B1: the on-board cartographer replaces the two-operator search (b1_carto.c); the
 * identity page's seed and budget are its inputs; flags bits 2-3 (L6's schedule mode) are
 * ignored. The record's `arm` field is never emitted; the `carto` block carries the phase. */
static b1_orch O;                          /* the session orchestrator: cartographer + the sequence */
static char g_carto_json[2048];
static char g_map_render[20480];
static uint64_t g_tables_u64[B1_LUTS];
static uint32_t g_carrier_variant;         /* VARIANT as read at identity */
static const char *carto_block(void)
{
    if (b1_orch_record_block(&O, S.seq, g_map_render, sizeof(g_map_render), g_carto_json, sizeof(g_carto_json)) == 0u)
        return NULL;
    return g_carto_json;
}

static int establish_identity(void)
{
    uint32_t page[P3_PAGE_WORDS];
    uint32_t st;
    int i;
    for (i = 0; i < P3_PAGE_WORDS; i++)
        page[i] = Xil_In32(P3_PAGE_ADDR + 4u * (uint32_t)i);
    if (p3_parse_identity_page(page, &S.page) != 0) {
        p3_stop(P3_STOPPED, "identity page magic/layout/checksum refused");
        return -1;
    }
    S.rec_control = (S.page.flags & P3_RECTX_CONTROL_FLAG) ? 1 : 0; /* rec-v3: the forced REC-retry control */
    S.sign_control = (S.page.flags & P3_SIGNTX_CONTROL_FLAG) ? 1 : 0; /* rel-v4: the forced SIGNREQ-retry control */
    /* Every check is evaluated and reported, then the epoch stops if any of them fired.
     * The refused identity is still evidence, so IDENT is emitted either way — and it is
     * emitted at all, which the first L5 attempt could not do: validate_standalone_run_log
     * requires app_identity and this application never sent one. */
    {
        p3_wire_identity_in in;
        const char *findings[8];
        uint64_t nonce = pl_nonce();
        int nf = 0;
        uint32_t idcode = Xil_In32(SLCR_PSS_IDCODE);

        st = axi_read(P3_STATUS);
        if ((idcode & P3_IDCODE_MASK) != (P3_IDCODE & P3_IDCODE_MASK))
            findings[nf++] = "PSS_IDCODE is not this part";
        if ((st & P3_ST_RESERVED) || !((st >> P3_ST_ALIVE) & 1u))
            findings[nf++] = "STATUS is not the P3 carrier answering";
        if (!((st >> P3_ST_KEY_LOADED) & 1u))
            findings[nf++] = "key_loaded is 0: not the provisioned carrier instance";
        g_carrier_variant = axi_read(P3_VARIANT);
        if (g_carrier_variant != B1_VARIANT_WORD)
            findings[nf++] = "VARIANT is not the B1 gate contract: this is not the B1 carrier";
        if (((st >> P3_ST_FAULT) & 1u) || ((st >> P3_ST_RECOVERY) & 1u))
            findings[nf++] = "fault/recovery before start";
        /* the nonce echo: a reconfiguration since the host's last look would have reset it */
        if (nonce != S.page.nonce_seen)
            findings[nf++] = "the nonce is not the host's last observation";

        memset(&in, 0, sizeof(in));
        in.pss_idcode = idcode;
        in.token = S.page.token;
        in.uboot_epoch = S.page.uboot_epoch;
        in.carrier_sha256 = S.page.carrier_sha256;
        in.nonce_at_start = nonce;
        in.status_at_start = st;
        in.fclk0_hz_decoded = S.page.fclk0_hz;   /* host-supplied, echoed (p3_derive.h) */
        in.app_epoch = 0;
        in.findings = nf ? findings : NULL;
        in.findings_n = nf;
        /* app_identity 1.1.0 (L6 §2.4): the master seed, the mode, and the hash of the map
         * data compiled into THIS image (p3_data.h), which the host regenerates */
        /* B1: the seed drives the cartographer's own choices; there is no schedule mode and no
         * operator data — the universe digest stands where the L6 map-data hash stood */
        in.master_seed = S.page.seed;
        in.schedule_mode = "carto-v1";
        in.operator_data_sha256 = B1_UNIVERSE_SHA256;
        in.carto_version = B1_CARTO_VERSION;
        in.universe_sha256 = B1_UNIVERSE_SHA256;
        in.probe_budget = S.page.budget;
        in.carrier_variant = g_carrier_variant;
        /* app_identity 1.2.0 (rec-v3): the wire protocol this image speaks, and the control;
         * 1.3.0 (rel-v4): the SIGNREQ control echoed as well */
        in.protocol = "rel-v4";
        in.rec_retry_control = S.rec_control;
        in.sign_retry_control = S.sign_control;
        /* rel-v4 §2.6j: the IDENT is a handshake — sent, then the host's IDENTACK waited for
         * with the bound, the same bytes resent on the bound, at most P3_RECTX_ATTEMPTS
         * transmissions; without an acknowledgement the epoch stops (STOP_IDENT) and no
         * SIGNREQ is ever sent. A refused identity (the host verifies before it acks) is
         * exactly the case that exhausts. */
        {
            p3_tx_kinds k;
            p3_rectx_result r;
            size_t n = build_payload_frame("IDENT", 0, p3_wire_identity(&in, g_payload, sizeof(g_payload)),
                                           g_tx_line, sizeof(g_tx_line));
            if (n == 0u)
                return -1;
            k.ack_a = "IDENTACK";
            k.ack_b = NULL;
            k.get = NULL;
            k.stop_why = "STOP_IDENT: the identity was not acknowledged after 3 attempts";
            k.prev_seq = 0u;
            k.prev_strict = 0;
            if (tx_run_line(n, 0u, &k, 0, P3_IDENT_IDLE_POLLS, &r) != 0) {
                if (S.kind == P3_RUNNING)
                    p3_stop(P3_STOPPED, r.why ? r.why : "STOP_IDENT: the identity was not acknowledged");
            }
        }
        if (nf)
            p3_stop(P3_STOPPED, "identity refused");
    }
    return S.kind == P3_RUNNING ? 0 : -1;
}

/* ────────────────────────── one candidate (§4.2 – §4.6) ───────────────────────────── */

static uint32_t hex_nibble(char c) { return (uint32_t)((c <= '9') ? c - '0' : c - 'a' + 10); }

static void hex_to_words_be(const char *hex, uint32_t *out, int words)
{
    int i, j;
    for (i = 0; i < words; i++) {
        uint32_t w = 0;
        for (j = 0; j < 8; j++)
            w = (w << 4) | hex_nibble(hex[8 * i + j]);
        out[i] = w;
    }
}

static uint64_t hex_to_u64(const char *hex)
{
    uint64_t v = 0;
    int i;
    for (i = 0; i < 16; i++)
        v = (v << 4) | (uint64_t)hex_nibble(hex[i]);
    return v;
}

static int stage_streams(void)
{
    uint32_t words[P3_STREAM_WORDS];
    int e, i;
    for (e = 0; e < P3_ENVELOPE_COUNT; e++) {
        p3_build_stream(e, P3_CFRAMES(S.frames), words);
        for (i = 0; i < P3_STREAM_WORDS; i++)
            Xil_Out32(P3_WR_BUF + (uint32_t)e * 4u * P3_STREAM_WORDS + 4u * (uint32_t)i,
                      words[i]);
    }
    return 0;
}

/* link 2: re-read the staged streams FROM DDR and hash what is actually there */
static int link2_witness(char *staged_hex, char *stream_hex)
{
    uint32_t frames5[P3_ENVELOPE_FRAMES][P3_FRAME_WORDS];
    uint32_t reread[P3_TARGET_FRAMES][P3_FRAME_WORDS];
    uint32_t words[P3_STREAM_WORDS];
    uint8_t digest[32];
    p3_sha256 c;
    int e, k, i;
    p3_sha256_init(&c);
    for (e = 0; e < P3_ENVELOPE_COUNT; e++) {
        uint32_t far_set;
        for (i = 0; i < P3_STREAM_WORDS; i++)
            words[i] = Xil_In32(P3_WR_BUF + (uint32_t)e * 4u * P3_STREAM_WORDS +
                                4u * (uint32_t)i);
        p3_sha256_words(&c, words, P3_STREAM_WORDS);
        if (p3_parse_stream(words, &far_set, frames5) != 0 || far_set != P3_ENVELOPE[e].far_set) {
            p3_stop(P3_STOPPED, "STOP_LINK2: the staged stream does not parse");
            return -1;
        }
        for (k = 0; k < 4; k++)
            memcpy(reread[P3_ENVELOPE[e].target[k]], frames5[k], sizeof(frames5[k]));
    }
    p3_sha256_final(&c, digest);
    p3_hex(digest, 32, stream_hex);
    p3_frames_hash(P3_CFRAMES(reread), digest);
    p3_hex(digest, 32, staged_hex);
    return 0;
}

static int write_envelopes(void)
{
    int e;
    for (e = 0; e < P3_ENVELOPE_COUNT; e++) {
        if (devcfg_dma(&DMA_WRITE_ENVELOPE,
                       (P3_WR_BUF + (uint32_t)e * 4u * P3_STREAM_WORDS) | DMA_HOLD_TAG) != 0)
            return -1;
        /* per-envelope DMA status, reported in the oracle self-report (spec §7) */
        S.envelope_int_sts[e] = Xil_In32(DEVCFG_INT_STS);
        heartbeat();
    }
    return 0;
}

/* link 3: the pinned three-command readback of one frame (psmap §8a) */
static int readback_frame(int index)
{
    uint32_t cmd[P3_READBACK_CMD_WORDS];
    uint32_t clean[P3_CLEANUP_WORDS];
    int i;
    for (i = 0; i < P3_READBACK_WORDS; i++)
        Xil_Out32(P3_DST_BUF + 4u * (uint32_t)i, P3_SENTINEL);
    for (i = 0; i < P3_READBACK_WORDS; i++)
        if (Xil_In32(P3_DST_BUF + 4u * (uint32_t)i) != P3_SENTINEL) {
            /* not confirmed present ⇒ the read is not attempted (psmap §7.5) */
            p3_stop(P3_STOPPED, "STOP_LINK3: the sentinel prefill did not verify");
            return -1;
        }
    p3_build_readback_command(P3_TARGET_FARS[index], cmd);
    for (i = 0; i < P3_READBACK_CMD_WORDS; i++)
        Xil_Out32(P3_CMD_BUF + 4u * (uint32_t)i, cmd[i]);
    if (devcfg_dma(&DMA_READ_COMMAND, 0) != 0)
        return -1;
    if (devcfg_dma(&DMA_READ_FRAME, 0) != 0)
        return -1;
    p3_build_cleanup_command(clean);
    for (i = 0; i < P3_CLEANUP_WORDS; i++)
        Xil_Out32(P3_CMD_BUF + 4u * (uint32_t)i, clean[i]);
    if (devcfg_dma(&DMA_READ_CLEANUP, 0) != 0)
        return -1;
    /* words [0:101] are the pad frame and are not adjudicated; [101:202] is the target */
    for (i = 0; i < P3_FRAME_WORDS; i++)
        S.readback[index][i] = Xil_In32(P3_DST_BUF + 4u * (uint32_t)(P3_FRAME_WORDS + i));
    return 0;
}

static int link3_witness(char *readback_hex)
{
    uint8_t digest[32];
    int i;
    for (i = 0; i < P3_TARGET_FRAMES; i++) { /* all twelve read before judging: L3 #1's lesson */
        if (readback_frame(i) != 0)
            return -1;
        heartbeat(); /* twelve PCAP readbacks is the session's longest silent stretch */
    }
    p3_frames_hash(P3_CFRAMES(S.readback), digest);
    p3_hex(digest, 32, readback_hex);
    return 0;
}

/* the ARM transaction: 24 staged words then the strobe. The tag is the notary's; this
 * application cannot produce one — it holds no key and has no path to the key register. */
/* What the post-strobe poll saw: how many STATUS reads, whether the gate settled, and the
 * first and last STATUS values. Recorded on every ARM path. */
typedef struct {
    uint32_t polls;
    uint32_t polls_max;
    int settled;
    uint32_t status_first;
    uint32_t status_last;
} p3_settle;

/* The gate has settled when neither the gate nor the scorer is busy AND something has
 * latched — a fault or scorer_done. The SAME condition host/l3_runner.py polled for at L3,
 * where the nonce was seen to step five times; session 3 (2026-09-01) showed why it is
 * needed here: this function used to read the nonce immediately after the strobe, and
 * rtl/p3_arm_gate.v steps the nonce only when the SipHash completes (state 1, sh_done),
 * so the immediate read saw gate_busy SET and the old nonce. */
static int settle_condition(uint32_t st)
{
    int busy = ((st >> P3_ST_GATE_BUSY) & 1u) || ((st >> P3_ST_SCORER_BUSY) & 1u);
    int latched = ((st >> P3_ST_FAULT) & 1u) || ((st >> P3_ST_SCORER_DONE) & 1u);
    return !busy && latched;
}

/* Returns 0 when the gate settled and the PL consumed the attempt (the nonce stepped),
 * 1 when the gate settled and the nonce did NOT step, 2 when the bounded poll ran out
 * before the gate settled, and -1 only when the attempt was not made at all. Every
 * observation is written through the out-parameters on ALL paths: session 1 stopped on the
 * nonce check and threw away the STATUS and FAULT it had just read, which were the two
 * most diagnostic values it had. The caller decides what to record; this function loses
 * nothing that is READABLE — CTRL is write-only in the RTL, so the strobe's fate in the
 * register is not observable from here and the record says so rather than pretending
 * otherwise. The poll only READS STATUS: the strobe is written exactly once, whatever the
 * poll sees, and no ARM is re-issued from here. */
static int arm_attempt(const char *commit_hex, const char tables_hex[6][17],
                       const char *tag_hex, uint64_t *nonce_before, uint64_t *nonce_after,
                       uint32_t *status, uint32_t *fault, int *writes_issued,
                       p3_settle *settle)
{
    uint32_t words[24];
    uint8_t tag[16];
    uint64_t t0 = 0, t1 = 0;
    int i;
    uint32_t st = axi_read(P3_STATUS);
    if (((st >> P3_ST_FAULT) & 1u) || ((st >> P3_ST_RECOVERY) & 1u)) {
        p3_stop(P3_STOPPED, "STOP_AXI: fault set before the ARM");
        return -1;
    }
    *nonce_before = pl_nonce();
    *writes_issued = 0;
    hex_to_words_be(commit_hex, words, 8);
    for (i = 0; i < 6; i++) {
        uint64_t t = hex_to_u64(tables_hex[i]);
        words[8 + 2 * i] = (uint32_t)(t >> 32);
        words[9 + 2 * i] = (uint32_t)t;
    }
    for (i = 0; i < 16; i++)
        tag[i] = (uint8_t)((hex_nibble(tag_hex[2 * i]) << 4) | hex_nibble(tag_hex[2 * i + 1]));
    for (i = 7; i >= 0; i--) { /* the tag's two 64-bit LITTLE-endian halves, high word first */
        t0 = (t0 << 8) | tag[i];
        t1 = (t1 << 8) | tag[8 + i];
    }
    words[20] = (uint32_t)(t0 >> 32);
    words[21] = (uint32_t)t0;
    words[22] = (uint32_t)(t1 >> 32);
    words[23] = (uint32_t)t1;

    for (i = 0; i < 20; i++) {
        axi_write(P3_PAYLOAD0 + 4u * (uint32_t)i, words[i]);
        (*writes_issued)++;
    }
    for (i = 0; i < 4; i++) {
        axi_write(P3_TAG0 + 4u * (uint32_t)i, words[20 + i]);
        (*writes_issued)++;
    }
    axi_write(P3_CTRL, P3_ARM_STROBE);
    (*writes_issued)++;

    /* bounded settle poll: read-only, one STATUS read per iteration, no second strobe */
    settle->polls_max = P3_SETTLE_POLLS_MAX;
    settle->polls = 0u;
    settle->settled = 0;
    st = axi_read(P3_STATUS);
    settle->status_first = st;
    settle->polls = 1u;
    while (!(settle->settled = settle_condition(st)) && settle->polls < settle->polls_max &&
           S.kind == P3_RUNNING) {
        st = axi_read(P3_STATUS);
        settle->polls++;
    }
    settle->status_last = st;

    *status = st;
    *fault = axi_read(P3_FAULT);
    *nonce_after = pl_nonce();
    /* The caller emits the record carrying everything above; it is NOT this function's
     * business to decide that the observations are uninteresting. */
    if (!settle->settled)
        return 2;
    return (*nonce_after == *nonce_before) ? 1 : 0;
}

/* ───────────────────────────────── the session ────────────────────────────────────── */

/* The search is out of D1's scope; only its interface is fixed (§4.1) — declared above
 * with the schedule mode and the arm the L6 preregistration added to it. */

/* ───────────────────────────── audit-on-request (§4.7) ────────────────────────────── */

/* The raw words behind one candidate's self-report: the three re-read staging streams
 * followed by the twelve readback frames, in that fixed order. The collector recomputes
 * both link-2 hashes and the link-3 hash from them and compares with the compact record. */
#define P3_AUDIT_STREAM_WORDS (P3_ENVELOPE_COUNT * P3_STREAM_WORDS)
#define P3_AUDIT_FRAME_WORDS (P3_TARGET_FRAMES * P3_FRAME_WORDS)
#define P3_AUDIT_WORDS (P3_AUDIT_STREAM_WORDS + P3_AUDIT_FRAME_WORDS)
static char g_words_b64[4096]; /* one chunk's sparse entries: at most 384 × 6 bytes → 3072 b64 chars */

static uint32_t audit_word(uint32_t i)
{
    if (i < (uint32_t)P3_AUDIT_STREAM_WORDS)
        return Xil_In32(P3_WR_BUF + 4u * i);
    i -= (uint32_t)P3_AUDIT_STREAM_WORDS;
    return S.readback[i / P3_FRAME_WORDS][i % P3_FRAME_WORDS];
}

/* A line from the host, waited for with a BOUND on the WHOLE line (review 2026-09-02,
 * blocker 1: the first version bounded the first byte only and then blocked for the
 * newline). The receiver is p3_rectx_recv_line — the same code the host contract test
 * drives with truncated input; this file supplies only the RX FIFO primitives. -2 when the
 * host stayed quiet for `idle_polls` polls, -3 when a line was cut short, -1 over-long. */
static int app_rx_ready(void *ctx)
{
    (void)ctx;
    return console_rx_ready();
}

static int app_rx_byte(void *ctx)
{
    (void)ctx;
    return (int)(unsigned char)inbyte();
}

static uint64_t app_now_ticks(void *ctx)
{
    XTime now;
    (void)ctx;
    XTime_GetTime(&now); /* the global timer, started once at go (main); reads only */
    return (uint64_t)now;
}

static int recv_line_bounded(char *out, size_t max, uint32_t idle_polls)
{
    p3_rectx_rx rx;
    rx.rx_ready = app_rx_ready;
    rx.rx_byte = app_rx_byte;
    rx.now_ticks = app_now_ticks;
    rx.ctx = NULL;
    /* the poll cap AND the clock bound (P3_BOUND_TICKS): the first to run out ends the wait */
    return p3_rectx_recv_line_timed(&rx, out, max, idle_polls, P3_BOUND_TICKS);
}

static void serve_sparse_chunk(uint32_t chunk, uint32_t chunks, uint32_t total, const char *span)
{
    uint32_t lo = chunk * P3_WIRE_SPARSE_WINDOW;
    uint32_t hi = lo + P3_WIRE_SPARSE_WINDOW < total ? lo + P3_WIRE_SPARSE_WINDOW : total;
    size_t n = p3_wire_sparse_entries(audit_word, lo, hi, g_words_b64, sizeof(g_words_b64));
    if (n == 0u)
        g_words_b64[0] = 0; /* an all-zero window: no entries, which is legal and exact */
    send_payload("AUDIT", S.seq,
                 p3_wire_audit_sparse(S.seq, chunk, chunks, span, total, lo, hi, g_words_b64,
                                      g_payload, sizeof(g_payload)));
}

/* The I/O p3_pull.c is given (rel-v4): the stored READY line resent verbatim, the chunk
 * service above, the AUDITWAIT frame, the bounded receiver, this file's parser and JSON
 * scan. The state machine — resends, waits, bounds — is p3_pull.c's, the same source the
 * host contract test drives with the real host pull. */
typedef struct {
    uint32_t chunks, total;
    const char *span;
} pull_ctx;

static int pull_send_ready_cb(void *ctx)
{
    (void)ctx;
    put_str(g_ready_line);
    kick_watchdog();
    return S.kind == P3_PROTOCOL ? -1 : 0;
}

static int pull_serve_chunk_cb(uint32_t chunk, void *ctx)
{
    const pull_ctx *c = (const pull_ctx *)ctx;
    serve_sparse_chunk(chunk, c->chunks, c->total, c->span);
    return S.kind == P3_PROTOCOL ? -1 : 0;
}

static int pull_send_wait_cb(uint32_t served, void *ctx)
{
    (void)ctx;
    send_payload("AUDITWAIT", S.seq, p3_wire_audit_wait(S.seq, served, g_payload, sizeof(g_payload)));
    return S.kind == P3_PROTOCOL ? -1 : 0;
}

static int pull_recv_cb(char *out, size_t max, void *ctx)
{
    (void)ctx;
    return recv_line_bounded(out, max, P3_PULL_IDLE_POLLS);
}

static const char *pull_parse_cb(char *line, char *type_out, size_t type_max, uint32_t *seq_out, void *ctx)
{
    (void)ctx;
    return parse_frame_any(line, type_out, type_max, seq_out);
}

static int pull_payload_fields_cb(const char *payload, uint32_t *seq_out, uint32_t *chunk_out, int *has_chunk, void *ctx)
{
    size_t jn = p3_base64url_decode(payload, (uint8_t *)g_json, sizeof(g_json) - 1u);
    (void)ctx;
    if (jn == 0u)
        return -1;
    g_json[jn] = 0;
    if (json_uint(g_json, "\"seq\":", seq_out) != 0)
        return -1;
    *has_chunk = (json_uint(g_json, "\"chunk\":", chunk_out) == 0);
    return 0;
}

static int pull_channel_failed_cb(void *ctx)
{
    (void)ctx;
    return S.kind == P3_PROTOCOL;
}

/* The host-paced audit pull (docs/l6_audit_pull_design.md). Announces the transaction
 * (AUDIT_READY), then answers every AUDITGET with the sparse chunk asked for — as often
 * as asked: a chunk the host lost is simply asked for again — until AUDITDONE (0: the
 * words were pulled and verified, the record may say audited) or AUDITABORT / the bounded
 * wait running out (-1: the record says replayed-only; on the SCORED path the caller
 * emits STOP_AUDIT and makes NO ARM). `with_readback` is 0 at a link-2 refusal, whose
 * readback frames do not exist. Once per candidate: a second call is a no-op success. */
static int audit_pull(int with_readback)
{
    uint32_t total = with_readback ? (uint32_t)P3_AUDIT_WORDS : (uint32_t)P3_AUDIT_STREAM_WORDS;
    const char *span = with_readback ? "streams+readback" : "streams";
    uint32_t chunks = (total + P3_WIRE_SPARSE_WINDOW - 1u) / P3_WIRE_SPARSE_WINDOW;
    uint32_t nonzero = 0, i;
    pull_ctx ctx;
    p3_pull_io io;
    p3_pull_result pr;
    int rc;

    if (S.audit_served && S.audit_served_seq == S.seq)
        return 0;
    for (i = 0; i < total; i++)
        if (audit_word(i))
            nonzero++;
    S.audit_chunks_served = 0;
    S.audit_stop_why = NULL;
    /* the READY line is built ONCE and resent verbatim on the bound (rel-v4 §2.6l) */
    if (build_payload_frame("AUDIT_READY", S.seq,
                            p3_wire_audit_ready(S.seq, span, total, chunks, nonzero, g_payload, sizeof(g_payload)),
                            g_ready_line, sizeof(g_ready_line)) == 0u)
        return -1;
    ctx.chunks = chunks;
    ctx.total = total;
    ctx.span = span;
    io.send_ready = pull_send_ready_cb;
    io.serve_chunk = pull_serve_chunk_cb;
    io.send_wait = pull_send_wait_cb;
    io.recv_bounded = pull_recv_cb;
    io.parse = pull_parse_cb;
    io.payload_fields = pull_payload_fields_cb;
    io.channel_failed = pull_channel_failed_cb;
    io.rx = g_line;
    io.rx_max = sizeof(g_line);
    io.ctx = &ctx;
    rc = p3_pull_run(S.seq, chunks, &io, &pr);
    S.audit_chunks_served = pr.chunks_served;
    if (rc == 0) {
        S.audit_served = 1;
        S.audit_served_seq = S.seq;
        return 0;
    }
    if (rc == -2)
        return -1; /* the channel itself failed while sending: PROTOCOL is already set */
    S.audit_stop_why = pr.why ? pr.why : "the audit pull did not complete";
    return -1;
}

/* ───────────────────────────── the REC transaction (rec-v3) ───────────────────────── */

/* The I/O p3_rectx.c is given: the console's line send with the watchdog kick, the bounded
 * RX poll, this file's frame parser and JSON scan. The state machine itself is p3_rectx.c's
 * — the same source the host test drives (RecWireContract) — so nothing about resending,
 * bounds or acknowledgement is decided here. */
static int rectx_send_cb(const char *line, size_t n, void *ctx)
{
    (void)ctx;
    (void)n; /* the line is NUL-terminated by construction (p3_wire_line) */
    put_str(line);
    kick_watchdog();
    return 0;
}

static int rectx_recv_cb(char *out, size_t max, void *ctx)
{
    (void)ctx;
    return recv_line_bounded(out, max, P3_REC_IDLE_POLLS);
}

/* rel-v4: the same I/O for the IDENT / SIGNREQ / TERM transactions, with their own poll cap */
static int tx_recv_cb(char *out, size_t max, void *ctx)
{
    (void)ctx;
    return recv_line_bounded(out, max, g_tx_idle_polls);
}

static const char *rectx_parse_cb(char *line, char *type_out, size_t type_max, uint32_t *seq_out, void *ctx)
{
    (void)ctx;
    return parse_frame_any(line, type_out, type_max, seq_out);
}

static int rectx_payload_seq_cb(const char *payload, uint32_t *seq_out, void *ctx)
{
    size_t jn = p3_base64url_decode(payload, (uint8_t *)g_json, sizeof(g_json) - 1u);
    (void)ctx;
    if (jn == 0u)
        return -1;
    g_json[jn] = 0;
    return json_uint(g_json, "\"seq\":", seq_out);
}

/* rel-v4: one transaction over the line in g_tx_line (n bytes, newline included) — the
 * IDENT, the SIGNREQ or the TERM — with this file's I/O and the given poll cap; the clock
 * bound is P3_BOUND_TICKS through recv_line_bounded. Returns p3_tx_run's code. */
static int tx_run_line(size_t n, uint32_t seq, const p3_tx_kinds *kinds, int corrupt_first,
                       uint32_t idle_polls, p3_rectx_result *r)
{
    p3_rectx_io io;

    io.send = rectx_send_cb;
    io.recv_bounded = tx_recv_cb;
    io.parse = rectx_parse_cb;
    io.payload_seq = rectx_payload_seq_cb;
    io.rx = g_line;
    io.rx_max = sizeof(g_line);
    io.ctx = NULL;
    g_tx_idle_polls = idle_polls;
    return p3_tx_run(g_tx_line, n, seq, kinds, corrupt_first, &io, g_rec_scratch, sizeof(g_rec_scratch), r);
}

/* One candidate's record, built by p3_wire so it carries `seq`, `verified` and the nested
 * `evidence` the validator requires — the shape the flat payload this replaced never had.
 * `rec` is populated as the transaction proceeds; `outcome` selects which members the
 * validator will then insist on.
 *
 * rec-v3: the record is built ONCE (the serialiser's tally counts it once) into its own
 * buffer and handed to the REC transaction, which sends it, waits — bounded — for the
 * host's RECACK, resends the SAME bytes on a RECGET or when the wait runs out, and gives up
 * after P3_RECTX_ATTEMPTS. Returns 0 when the host acknowledged, -1 otherwise: the caller
 * must then NOT propose another candidate (S.rec_stop_why names the cause; the stop paths
 * keep their own first cause). The forced REC-retry control (flags.bit4) corrupts the CRC
 * of the FIRST transmission of the opening baseline's record (seq 1) only. */
static int emit_record(p3_wire_record_in *rec, const char *outcome)
{
    p3_rectx_io io;
    p3_rectx_result r;
    size_t n;
    int rc;

    rec->outcome = outcome;
    /* `audited` means the host ASKED and this application SERVED the raw words for this
     * candidate — never merely that auditing was configured. A record that claimed the
     * mark without the words would be exactly the self-report rule (ix) exists to bound. */
    rec->audited = (S.audit_served && S.audit_served_seq == rec->seq);
    n = build_payload_frame("REC", rec->seq, p3_wire_loop_record(rec, g_payload, sizeof(g_payload)),
                            g_rec_line, sizeof(g_rec_line));
    if (n == 0u)
        return -1; /* PROTOCOL already recorded by the builder */
    memset(&io, 0, sizeof(io));
    io.send = rectx_send_cb;
    io.recv_bounded = rectx_recv_cb;
    io.parse = rectx_parse_cb;
    io.payload_seq = rectx_payload_seq_cb;
    io.rx = g_line;
    io.rx_max = sizeof(g_line);
    rc = p3_rectx_run(g_rec_line, n, rec->seq, (S.rec_control && rec->seq == 1u) ? 1 : 0, &io,
                      g_rec_scratch, sizeof(g_rec_scratch), &r);
    S.rec_attempts += r.attempts;
    S.rec_gets += r.gets;
    if (rc == -2) {
        p3_stop(P3_PROTOCOL, r.why);
        return -1;
    }
    if (rc != 0) {
        S.rec_stop_why = r.why; /* the caller stops the epoch; no next candidate */
        return -1;
    }
    return 0;
}

/* returns 0 to continue the session, -1 when the epoch has ended */
static int run_candidate(const uint32_t genome[P3_GENOME_WORDS], int is_baseline,
                         const char *arm_name)
{
    char genome_hex[P3_GENOME_WORDS * 8 + 1];
    char type[16];
    char commit[65], tag[33], staged[65], stream_h[65], readback[65];
    char tables[6][17];
    p3_wire_record_in rec;
    const char *payload;
    size_t jn;
    uint64_t nonce_before, nonce_after;
    uint32_t status, fault, hb_before;
    p3_settle settle;
    int i, armed, writes_issued;

    S.seq++;
    S.hb_i = 0u; /* rel-v4: heartbeat indices restart with every record */
    p3_genome_to_hex(genome, genome_hex);
    memset(&rec, 0, sizeof(rec));
    rec.seq = S.seq;
    rec.genome = genome_hex;
    rec.arm = arm_name; /* NULL on a baseline: the brackets carry no arm (§2.4) */
    /* rec-v3: the console is read only inside a transaction, so anything waiting in the RX
     * FIFO now (a RECACK the host repeated after this application had already moved on)
     * is stale by construction and would otherwise merge with the sign reply. */
    (void)console_rx_flush();
    /* rel-v4 §2.6k: the sign exchange is a transaction. The SIGNREQ line is built ONCE and
     * handed to p3_tx_run, which sends it, waits — bounded — for SIGNOK or SIGNREF, resends
     * the SAME bytes on a SIGNGET or when the bound runs out, and gives up after
     * P3_RECTX_ATTEMPTS: then a terminal STOP_SIGN record and the stop. A RECACK/RECGET
     * arriving here is tolerated only when it names the previous record (bounded); any
     * other acknowledgement ends the epoch PROTOCOL (review 2026-09-02, blocker 4b). The
     * forced SIGNREQ-retry control (flags.bit5) corrupts the CRC of seq 1's first
     * transmission only. AUDITREQ is no longer a frame: the host's request rides in the
     * SIGNOK payload (`audit_requested`), read below. */
    {
        p3_tx_kinds k;
        p3_rectx_result r;
        int rc;
        size_t tn = build_payload_frame("SIGNREQ", S.seq,
                                        p3_wire_sign_request(S.page.token, 0, S.seq, genome_hex, pl_nonce(),
                                                             g_payload, sizeof(g_payload)),
                                        g_tx_line, sizeof(g_tx_line));
        if (tn == 0u || S.kind != P3_RUNNING)
            return -1;
        k.ack_a = "SIGNOK";
        k.ack_b = "SIGNREF";
        k.get = "SIGNGET";
        k.stop_why = "STOP_SIGN: the sign exchange was not acknowledged after 3 attempts";
        k.prev_seq = S.seq >= 2u ? S.seq - 1u : 0u;
        k.prev_strict = 1;
        rc = tx_run_line(tn, S.seq, &k, (S.sign_control && S.seq == 1u) ? 1 : 0, P3_SIGN_IDLE_POLLS, &r);
        S.sign_attempts += r.attempts;
        S.sign_gets += r.gets;
        if (rc == -2 || rc == -3) {
            p3_stop(P3_PROTOCOL, r.why ? r.why : "PROTOCOL: the sign transaction failed");
            return -1;
        }
        if (rc != 0) {
            /* STOP_SIGN: nothing was staged, no ARM, no nonce consumed — a terminal record
             * carrying the attempt count and nothing else, then the stop (restore, TERM) */
            rec.have_sign_stop = 1;
            rec.sign_stop_attempts = r.attempts;
            rec.sign_stop_why = r.why ? r.why : "STOP_SIGN";
            (void)emit_record(&rec, "STOP_SIGN");
            p3_stop(P3_STOPPED, r.why ? r.why : "STOP_SIGN");
            return -1;
        }
        snprintf(type, sizeof(type), "%s", r.ack_type);
        payload = r.ack_payload;
    }
    S.audit_requested = 0;
    if (!strcmp(type, "SIGNREF")) {
        /* a gate refusal is DATA, not a channel failure (§3c). NOT audited, and
         * deliberately so: nothing was staged, so no raw words exist, and this record makes
         * no oracle self-report to check. Its evidence is the notary's OWN refusal, which
         * the host already holds and rule (vii) cross-checks.
         * B1 (docs/b1_architecture.md §3; compatibility review 2026-09-05, HOLD): the
         * instrument continued its session after a refusal; the B1 contract is that ANY
         * candidate that is not SCORED ENDS THE EPOCH — no next probe, no closing baseline,
         * no closing ARM; the restore-only cleanup and the TERM follow. The record is
         * emitted first (the terminal evidence), then the stop. */
        static const char *const refused_kind[] = {"gate_refusal"};
        S.refused++;
        rec.have_sign_refusal = 1;
        rec.finding_kinds = refused_kind;
        rec.finding_kinds_n = 1;
        if (emit_record(&rec, "REFUSED_BY_GATE") != 0) {
            p3_stop(P3_STOPPED, S.rec_stop_why); /* unacknowledged: no next candidate */
            return -1;
        }
        p3_stop(P3_STOPPED, "REFUSED_BY_GATE: an unscored candidate ends the B1 epoch");
        return -1;
    }
    if (strcmp(type, "SIGNOK") != 0) {
        p3_stop(P3_PROTOCOL, "PROTOCOL: unexpected reply type");
        return -1;
    }
    jn = p3_base64url_decode(payload, (uint8_t *)g_json, sizeof(g_json) - 1u);
    if (jn == 0u) {
        p3_stop(P3_PROTOCOL, "PROTOCOL: the reply payload is not base64url");
        return -1;
    }
    g_json[jn] = 0;
    if (!strstr(g_json, "\"schema\":\"sign_reply\"") ||
        json_hex(g_json, "\"commit\":\"", commit, 64) != 0 ||
        json_hex(g_json, "\"tag\":\"", tag, 32) != 0 || json_tables(g_json, tables) != 0) {
        p3_stop(P3_PROTOCOL, "PROTOCOL: the reply is not a well-formed sign_reply");
        return -1;
    }
    /* rel-v4 §2.6k: the audit request rides in the reply the transaction waited for */
    S.audit_requested = (strstr(g_json, "\"audit_requested\":true") != NULL) ? 1 : 0;

    rec.have_sign_reply = 1;
    rec.commit = commit;
    rec.tag = tag;
    for (i = 0; i < 6; i++)
        rec.tables[i] = tables[i];

    p3_derive_frames(genome, S.frames);
    stage_streams();
    heartbeat();
    if (link2_witness(staged, stream_h) != 0)
        return -1;
    if (strcmp(staged, commit) != 0) { /* the binding, BEFORE any DMA */
        /* The staging streams exist, so this refusal is auditable and IS audited — with or
         * without a request (§3a item 2): the application is asserting `staged != commit`
         * and the host would otherwise have to take that on trust. The readback frames do
         * not exist, hence a "streams" span. Words first, then the stop, then the record. */
        (void)audit_pull(0); /* §3a item 2: pulled unconditionally; the mark follows the pull */
        p3_stop(P3_STOPPED, "STOP_LINK2: staged frames are not the signed commit");
        (void)emit_record(&rec, "STOP_LINK2");
        return -1;
    }
    /* link 2 held: the oracle self-report can now be filled in. `readback` is still empty
     * and is set after link 3; the validator refuses an ARM without readback == commit. */
    rec.have_oracle = 1;
    rec.staged_sha256 = staged;
    rec.staged_stream_sha256 = stream_h;
    rec.readback_sha256 = readback;
    rec.envelopes_n = P3_ENVELOPE_COUNT;
    rec.envelope_int_sts = S.envelope_int_sts;
    rec.audit_available = 1;
    memset(readback, '0', 64); /* the schema wants 64 hex; link 3 overwrites it below */
    readback[64] = 0;
    if (write_envelopes() != 0)
        return -1;
    if (link3_witness(readback) != 0)
        return -1;
    /* the words exist now, so an audit promised in this exchange is served BEFORE the
     * record that will claim it — including on the STOP_LINK3 path, where the raw words
     * are exactly what a reviewer would want */
    if (strcmp(readback, commit) != 0) {
        (void)audit_pull(1); /* §3a item 2: a link-3 stop is audited whether or not it was asked */
        p3_stop(P3_STOPPED, "STOP_LINK3: the fabric did not read back as the candidate");
        (void)emit_record(&rec, "STOP_LINK3");
        return -1;
    }
    /* The SCORED path's audit, iff the host asked at sign time (all-self-reporting, or the
     * sampled schedule). It happens BEFORE the ARM; a pull that does not complete means
     * NO ARM: the candidate ends as STOP_AUDIT and the epoch stops (restore, TERM). */
    if (S.audit_requested && audit_pull(1) != 0) {
        rec.have_audit_stop = 1;
        rec.audit_stop_why = S.audit_stop_why ? S.audit_stop_why : "the audit pull did not complete";
        rec.audit_chunks_served = S.audit_chunks_served;
        (void)emit_record(&rec, "STOP_AUDIT");
        p3_stop(P3_STOPPED, "the audit pull did not complete: no ARM was attempted");
        return -1;
    }
    hb_before = axi_read(P3_HEARTBEAT);
    armed = arm_attempt(commit, (const char(*)[17])tables, tag, &nonce_before, &nonce_after,
                        &status, &fault, &writes_issued, &settle);
    if (armed < 0) {
        /* The attempt was never made: the pre-ARM check found a fault. The candidate HAS
         * staged and read back, so this is a post-staging STOP_AXI — a raw self-report,
         * auto-audited and recorded (§3a; validators.records.self_report_class). */
        (void)audit_pull(1); /* §3a item 2: the words persist; the mark follows the pull */
        (void)emit_record(&rec, "STOP_AXI");
        p3_stop(P3_STOPPED, "STOP_AXI: the pre-ARM check found a fault"); /* the first cause (arm_attempt's) is kept; this guarantees the stop */
        return -1;
    }
    rec.have_arm = 1;
    rec.nonce_before = nonce_before;
    rec.nonce_after = nonce_after;
    rec.status_after = status;
    rec.fault_after = fault;
    rec.writes_issued = writes_issued;
    rec.key_loaded_observed = (int)((status >> P3_ST_KEY_LOADED) & 1u);
    rec.settle_polls = settle.polls;
    rec.settle_polls_max = settle.polls_max;
    rec.settled = settle.settled;
    rec.status_first = settle.status_first;
    if (armed == 2) {
        /* The gate never settled within the bound. Neutral: the record carries the whole
         * poll and the epoch stops. Nothing is re-issued and nothing is claimed about why. */
        (void)audit_pull(1); /* §3a item 2: the words persist; the mark follows the pull */
        (void)emit_record(&rec, "STOP_SETTLE");
        p3_stop(P3_STOPPED, "the ARM did not settle within the poll bound");
        return -1;
    }
    if (armed == 1) {
        /* The gate settled and the PL did not consume the ARM. Session 1 (2026-09-01)
         * ended on the old form of this check and kept nothing; the record goes out FIRST,
         * carrying every observation, and only then does the epoch stop. This records THAT
         * it happened and asserts nothing about why. */
        (void)audit_pull(1); /* §3a item 2: the words persist; the mark follows the pull */
        (void)emit_record(&rec, "STOP_ARM");
        p3_stop(P3_STOPPED, "the gate settled and the nonce did not step: the PL did not consume this ARM");
        return -1;
    }
    if (!((status >> P3_ST_CFG_VALID_HW) & 1u)) {
        (void)audit_pull(1); /* §3a item 2: the words persist; the mark follows the pull */
        (void)emit_record(&rec, "REFUSED_BY_PL");
        /* the fault code names the check that fired, not its cause (spec §4.6) */
        p3_stop(P3_STOPPED, "the PL refused the ARM");
        return -1;
    }
    {
        /* The PL's OWN witness of what it bound. These are read back from the hardware,
         * never echoed from the signed reply: rules (ii) and (iii) compare them with the
         * signed commit and tables, and an echo would make both checks vacuous. */
        char readout[6][17];
        char hw_commit[65];
        rec.have_score = 1;
        for (i = 0; i < 8; i++)
            snprintf(hw_commit + 8 * i, 9, "%08lx",
                     (unsigned long)axi_read(P3_HW_COMMIT0 + 4u * (uint32_t)i));
        rec.hw_candidate_commit = hw_commit;
        for (i = 0; i < 6; i++) {
            uint32_t hi = axi_read(P3_READOUT0 + 4u * (uint32_t)(2 * i));
            uint32_t lo = axi_read(P3_READOUT0 + 4u * (uint32_t)(2 * i + 1));
            snprintf(readout[i], sizeof(readout[i]), "%08lx%08lx",
                     (unsigned long)hi, (unsigned long)lo);
            rec.readout[i] = readout[i];
            rec.scores[i] = axi_read(P3_SCORE0 + 4u * (uint32_t)i);
            g_tables_u64[i] = ((uint64_t)hi << 32) | (uint64_t)lo;
        }
        rec.hb_before = hb_before;
        rec.hb_after = axi_read(P3_HEARTBEAT);
        /* B1: the cartographer learns from the PL's own readout of this probe, then the
         * record carries its updated commitment (map hash) and a sample of what changed */
        b1_orch_observe(&O, S.seq, g_tables_u64);   /* a baseline learns nothing; a probe does */
        rec.carto = carto_block();
        if (emit_record(&rec, "SCORED") != 0) {
            S.scored++; /* it was scored; it is its record that the host never confirmed */
            p3_stop(P3_STOPPED, S.rec_stop_why); /* unacknowledged: no next candidate */
            return -1;
        }
    }
    S.scored++;
    memcpy(S.last_commit, commit, sizeof(commit));
    memcpy(S.last_tables, tables, sizeof(tables));
    S.have_last_reply = 1;
    if (is_baseline)
        S.closing_baseline = 1;
    return 0;
}

/* the closing control: the last signed candidate's payload with a ZERO tag must be refused
 * (§4.0). The fault it raises is sticky, which is why it is the last device operation. */
static void closing_unsigned_control(void)
{
    static const char zero_tag[] = "00000000000000000000000000000000";
    uint64_t nb, na;
    uint32_t status, fault;
    p3_settle settle;
    int writes_issued;
    if (!S.have_last_reply) {
        p3_stop(P3_STOPPED, "no signed candidate to build the closing control from");
        return;
    }
    /* A closing control the PL never consumed is a different fact from one it refused, and
     * it must be said so. It is NOT emitted as a CLOSE frame: rule (viii) rejects a closing
     * ARM control on a stopped epoch, so the observation travels as the epoch's reason
     * rather than as a record the validator would have to be loosened to accept. */
    {
        int armed = arm_attempt(S.last_commit, (const char(*)[17])S.last_tables, zero_tag,
                                &nb, &na, &status, &fault, &writes_issued, &settle);
        if (armed == 2) {
            p3_stop(P3_STOPPED,
                    "the closing unsigned ARM did not settle within the poll bound");
            return;
        }
        if (armed == 1) {
            p3_stop(P3_STOPPED,
                    "the closing unsigned ARM was not consumed: the nonce did not step");
            return;
        }
        if (armed != 0)
            return;
    }
    if ((status >> P3_ST_CFG_VALID_HW) & 1u) {
        p3_stop(P3_STOPPED, "KILL: the closing unsigned ARM validated");
        return;
    }
    /* Its own frame type, not a loop_record: "CLOSING_CONTROL" is not a LOOP_OUTCOME and
     * the validator reads this from the log's `closing_negative` key (§4.0, rule viii). */
    send_payload("CLOSE", S.seq,
                 p3_wire_closing(nb, na, fault, status, g_payload, sizeof(g_payload)));
    S.closing_unsigned = 1;
    /* rel-v4 §2.6o: the same fields ride in the TERM, so a lost CLOSE is reconstructed */
    S.have_closing_control = 1;
    S.close_nb = nb;
    S.close_na = na;
    S.close_fault = fault;
    S.close_status = status;
}

static void emit_summary(void)
{
    p3_wire_summary_in in;

    memset(&in, 0, sizeof(in));
    in.token = S.page.token;
    in.kind = END_NAME[S.kind];
    in.reason = S.reason ? S.reason : "";
    in.last_seq = S.seq;
    in.scored = S.scored;
    in.refused_by_gate = S.refused;
    in.closing_restore = S.closing_restore;
    in.closing_baseline = S.closing_baseline;
    in.closing_unsigned = S.closing_unsigned;
    /* The audit block is the record serialiser's own count of what it produced — never a
     * sum of outcome counters. Session 3 (2026-09-01): scored + refused omitted the
     * STOP_ARM record, so the TERM said audited 1 / total 0 and rule (ix) rejected the
     * whole log. The validator requires total == the number of loop records. */
    p3_wire_tally(&in.total, &in.audited);
    in.crc_dropped = S.crc_dropped;
    in.drop_budget = P3_DROP_BUDGET;
    in.have_closing_control = S.have_closing_control;
    in.close_nonce_before = S.close_nb;
    in.close_nonce_after = S.close_na;
    in.close_fault = S.close_fault;
    in.close_status = S.close_status;
    /* rel-v4 §2.6o: the TERM is a transaction — sent, TERMACK waited for with the bound,
     * the same bytes resent on a TERMGET or the bound, at most P3_RECTX_ATTEMPTS; then the
     * application halts either way (nothing follows a TERM). */
    {
        p3_tx_kinds k;
        p3_rectx_result r;
        size_t n = build_payload_frame("TERM", S.seq + 1u, p3_wire_summary(&in, g_payload, sizeof(g_payload)),
                                       g_tx_line, sizeof(g_tx_line));
        if (n == 0u)
            return;
        k.ack_a = "TERMACK";
        k.ack_b = NULL;
        k.get = "TERMGET";
        k.stop_why = "TERM_UNACKED: the summary was not acknowledged after 3 attempts";
        k.prev_seq = 0u;
        k.prev_strict = 0;
        (void)tx_run_line(n, S.seq + 1u, &k, 0, P3_TERM_IDLE_POLLS, &r);
    }
}

/* ───────────────────────────────── the B1 session, as three named steps ─────────────────
 * ONE sequence for the board and the host twin; ALSO the unit the host application harness
 * (tb/b1/hostapp) drives with the real code of this file against a scripted host:
 *   init   — the orchestrator initialises and binds the cartographer BEFORE the opening
 *            baseline (its record commits to that state);
 *   run    — every candidate the orchestrator proposes (opening baseline, the probes from
 *            the identity page's seed and budget, the closing baseline) through
 *            run_candidate; the stop condition is checked BEFORE a candidate is proposed,
 *            and ANY candidate that is not SCORED ends the epoch (run_candidate returns
 *            non-zero: the orchestrator is told, nothing more is proposed); the closing
 *            unsigned control and COMPLETED only when the budget completed;
 *   finish — the restore-only cleanup of a stopped epoch, then the TERM. */
static void b1_session_init(void)
{
    b1_orch_init(&O, S.page.seed, S.page.budget, S.page.token, B1_UNIVERSE_SHA256, S.page.app_image_sha_lo32);
}

static void b1_session_run(void)
{
    uint32_t genome[P3_GENOME_WORDS];
    int is_baseline, kind;
    while (S.kind == P3_RUNNING && b1_orch_next(&O, genome, &is_baseline, &kind)) {
        if (run_candidate(genome, is_baseline, NULL) != 0) {
            b1_orch_unobserved(&O);
            break;
        }
    }
    if (S.kind == P3_RUNNING && O.step == B1_STEP_DONE) {
        S.closing_restore = 1;                 /* the closing baseline restored the base and scored */
        closing_unsigned_control();
        if (S.kind == P3_RUNNING)
            p3_stop(P3_COMPLETED, "budget");
    }
}

static void b1_session_finish(void)
{
    uint32_t blank[P3_GENOME_WORDS];
    if (S.kind == P3_STOPPED && !S.closing_restore) {
        /* the mandatory finally: restore the base — a WRITE, never an ARM after a sticky
         * fault (§4.0). A failure here changes nothing that is already true of the epoch. */
        memset(blank, 0, sizeof(blank));
        p3_derive_frames(blank, S.frames);
        if (stage_streams() == 0 && write_envelopes() == 0)
            S.closing_restore = 1;
    }
    emit_summary();
}

int main(void)
{
    uint32_t genome[P3_GENOME_WORDS];
    uint32_t blank[P3_GENOME_WORDS];
    uint32_t i;

    /* The DDR this instrument uses is mapped strongly-ordered and NON-CACHEABLE before it
     * is touched. Staging through the D-cache is the defect the L3 diagnostic session found
     * (docs/l3_findings.md): the DMA read stale DDR while the re-read "confirmed" the
     * cached copy. Per-operation flushes are the version of that fix which is silently
     * wrong the first time one call is missed — so no cache maintenance appears below. */
    Xil_SetTlbAttributes(P3_CMD_BUF, P3_NONCACHEABLE);
    Xil_SetTlbAttributes(P3_DST_BUF, P3_NONCACHEABLE);
    Xil_SetTlbAttributes(P3_WR_BUF, P3_NONCACHEABLE);
    Xil_SetTlbAttributes(P3_PAGE_ADDR, P3_NONCACHEABLE);
    for (i = 0; i < 8u * P3_MB; i += P3_MB)
        Xil_SetTlbAttributes(P3_RING_ADDR + i, P3_NONCACHEABLE);

    memset(&S, 0, sizeof(S));
    S.kind = P3_RUNNING;
    /* rel-v4: the global timer is the wall-time authority of every bounded wait
     * (P3_BOUND_TICKS); started and zeroed once here, read-only afterwards. A private
     * (SCU) peripheral register, not the SLCR. */
    XTime_SetTime(0u);

    if (establish_identity() != 0) {
        emit_summary();
        return 0;
    }

    /* the watchdog is armed only once identity holds, and is kicked from this loop alone */
    if (S.page.flags & 2u) {
        XScuWdt_Config *cfg = XScuWdt_LookupConfig(XPAR_PS7_SCUWDT_0_DEVICE_ID);
        /* Fail-closed: a watchdog the identity page asked for and that cannot be brought
         * up is an epoch that must not run; the TERM says why and nothing else happens. */
        if (cfg == NULL || XScuWdt_CfgInitialize(&S.wdt, cfg, cfg->BaseAddr) != XST_SUCCESS) {
            p3_stop(P3_STOPPED, "the watchdog could not be initialised");
            emit_summary();
            return 0;
        }
        /* D-s1: prescaler 7 and watchdog (reset) mode in one control write, then the
         * pinned load, then enable. The mode bit can only be cleared through the disable
         * register's magic sequence, which this application never writes. */
        XScuWdt_SetControlReg(&S.wdt, (P3_WDT_PRESCALER << XSCUWDT_CONTROL_PRESCALER_SHIFT) |
                                          XSCUWDT_CONTROL_WD_MODE_MASK);
        XScuWdt_LoadWdt(&S.wdt, P3_WDT_LOAD);
        XScuWdt_Start(&S.wdt);
        S.wdt_started = 1; /* the kick is live from here, and only from here */
    }

    memset(blank, 0, sizeof(blank)); /* the blank genome IS the pinned base (b1_orch proposes it) */
    (void)blank;
    (void)genome;

    b1_session_init();
    b1_session_run();
    b1_session_finish();
    return 0;
}
