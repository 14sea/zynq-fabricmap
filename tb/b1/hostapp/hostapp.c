/* tb/b1/hostapp — the REAL b1_app.c compiled for the host against stub BSP headers
 * (hostbsp/), a fake memory map (DDR buffers, the B1 AXI window, DEVCFG, the SLCR IDCODE)
 * and a SCRIPTED HOST on the console. Compatibility review 2026-09-05 (HOLD): the twin's
 * session mode models an unscored candidate by breaking out of its own loop, so the
 * application's actual SIGNREF branch and main loop were never executed off-board. This
 * harness executes them: b1_session_init / b1_session_run / b1_session_finish from
 * b1_app.c itself, with run_candidate, emit_record, the rel-v4 transactions (p3_rectx),
 * the TERM and the restore-only cleanup all the firmware's own code.
 *
 * What is primed rather than executed: for the "probe" and "closing" scenarios the
 * candidates BEFORE the one the host refuses are fed to the orchestrator as observed
 * (all-zero tables) and S.seq advanced — the staging / DMA / ARM path of a SCORED
 * candidate needs a PL and is not modelled here. Every scenario then runs the real loop.
 *
 *   hostapp <scenario>   scenario ∈ opening | probe | closing | ack_fail
 * prints one JSON line per frame the application sent (decoded) and a final RESULT line.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "xil_types.h"
#include "xscuwdt.h"
#include "xtime_l.h"

/* ---- the fake memory map ------------------------------------------------------------- */
#define PAGE_BITS 12
#define NPAGES 4096
static struct { uint32_t base; uint8_t *mem; } pages[NPAGES];
static int npages;
static uint8_t *page_for(uint32_t addr)
{
    uint32_t base = addr & ~((1u << PAGE_BITS) - 1u);
    for (int i = 0; i < npages; i++) if (pages[i].base == base) return pages[i].mem;
    if (npages >= NPAGES) { fprintf(stderr, "fake memory: too many pages\n"); exit(3); }
    pages[npages].base = base; pages[npages].mem = calloc(1, 1u << PAGE_BITS);
    return pages[npages++].mem;
}
static uint32_t mem_rd(uint32_t a) { uint32_t v; memcpy(&v, page_for(a) + (a & ((1u << PAGE_BITS) - 1u)), 4); return v; }
static void mem_wr(uint32_t a, uint32_t v) { memcpy(page_for(a) + (a & ((1u << PAGE_BITS) - 1u)), &v, 4); }

/* the peripherals the application touches */
#define AXI_BASE 0x43C00000u
#define DEVCFG_BASE_ 0xF8007000u
static uint32_t devcfg_int_sts, ctrl_writes, payload_writes, dma_count, axi_reads, axi_writes;
static uint64_t fake_nonce = 0x9e3779b97f4a7c15ull;

uint32_t Xil_In32(uint32_t addr)
{
    if ((addr & 0xFFFF0000u) == AXI_BASE) {
        uint32_t off = addr - AXI_BASE; axi_reads++;
        switch (off) {
        case 0x2004: return (1u << 8) | (1u << 11);            /* alive, key_loaded; nothing busy */
        case 0x2008: return 0;
        case 0x2028: return 1000u + axi_reads;                   /* a heartbeat that advances */
        case 0x202C: return (uint32_t)fake_nonce;
        case 0x2030: return (uint32_t)(fake_nonce >> 32);
        case 0x2034: return 0x42310001u;
        default: return 0;
        }
    }
    if (addr == DEVCFG_BASE_ + 0x000) return 0x0C000000u;       /* PCAP_PR | PCAP_MODE */
    if (addr == DEVCFG_BASE_ + 0x00C) return devcfg_int_sts;
    if (addr == 0xF8000530u) return 0x13722093u;
    return mem_rd(addr);
}

void Xil_Out32(uint32_t addr, uint32_t value)
{
    if ((addr & 0xFFFF0000u) == AXI_BASE) {
        uint32_t off = addr - AXI_BASE; axi_writes++;
        if (off == 0x2000) ctrl_writes++;
        else if (off >= 0x2100 && off < 0x2100 + 24 * 4) payload_writes++;
        return;
    }
    if (addr == DEVCFG_BASE_ + 0x00C) { devcfg_int_sts = 0; return; }
    if (addr == DEVCFG_BASE_ + 0x024) { devcfg_int_sts |= (1u << 12) | (1u << 13); dma_count++; }
    mem_wr(addr, value);
}

/* the watchdog and the timer */
static XScuWdt_Config wcfg = {0xF8F00620u};
static int wdt_kicks;
XScuWdt_Config *XScuWdt_LookupConfig(u16 id) { (void)id; return &wcfg; }
int XScuWdt_CfgInitialize(XScuWdt *w, XScuWdt_Config *cfg, u32 base) { w->IsReady = 1; w->BaseAddr = base; (void)cfg; return 0; }
void XScuWdt_SetControlReg(XScuWdt *w, u32 v) { (void)w; (void)v; }
void XScuWdt_LoadWdt(XScuWdt *w, u32 v) { (void)w; (void)v; }
void XScuWdt_Start(XScuWdt *w) { (void)w; }
void XScuWdt_RestartWdt(XScuWdt *w) { (void)w; wdt_kicks++; }
static u64 fake_ticks;
void XTime_GetTime(XTime *t) { fake_ticks += 100u; *t = fake_ticks; }
void XTime_SetTime(XTime t) { fake_ticks = t; }

/* ---- the application, verbatim ------------------------------------------------------- */
#define main b1_app_main
#include "b1_app.c"
#undef main

/* ---- the scripted host on the console ------------------------------------------------ */
static struct { int signref_at_seq; int ack_rec; int ack_term; } script;
static char tx_line[16384]; static size_t tx_n;
static char rx_q[65536]; static size_t rx_head, rx_tail;
static unsigned n_signreq, n_rec, n_term, n_hb, n_other;
static char last_rec_outcome[64];
static char frame_json[8192];

static void rx_push(const char *s) { while (*s) { rx_q[rx_tail++ % sizeof(rx_q)] = *s++; } }
int console_rx_ready(void) { return rx_head != rx_tail; }
char inbyte(void) { return rx_q[rx_head++ % sizeof(rx_q)]; }
int console_rx_flush(void) { int n = (int)(rx_tail - rx_head); rx_head = rx_tail; return n; }

static void reply(const char *type, uint32_t seq, const char *json)
{
    static char b64[4096], line[8192];
    p3_base64url((const uint8_t *)json, strlen(json), b64);
    if (p3_wire_line(type, seq, S.page.token, b64, line, sizeof(line)) == 0u) { fprintf(stderr, "reply too long\n"); exit(3); }
    rx_push(line);
}

static void on_board_line(char *line)
{
    char type[24]; uint32_t seq; static char copy[16384]; char json[192];
    snprintf(copy, sizeof(copy), "%s", line);
    const char *payload = parse_frame_any(copy, type, sizeof(type), &seq);
    if (!payload) { printf("{\"frame\":\"UNPARSED\"}\n"); n_other++; return; }
    size_t jn = strcmp(payload, "-") ? p3_base64url_decode(payload, (uint8_t *)frame_json, sizeof(frame_json) - 1u) : 0u;
    frame_json[jn] = 0;
    printf("{\"frame\":\"%s\",\"seq\":%u,\"payload\":%s}\n", type, (unsigned)seq, jn ? frame_json : "null");
    if (!strcmp(type, "SIGNREQ")) {
        n_signreq++;
        if ((int)seq == script.signref_at_seq) {
            snprintf(json, sizeof(json), "{\"schema\":\"sign_refusal\",\"schema_version\":\"1.0.0\",\"seq\":%u,\"finding_kinds\":[\"whitelist\"]}", (unsigned)seq);
            reply("SIGNREF", seq, json);
        } /* any other seq: the host stays silent (a scenario never gets there) */
    } else if (!strcmp(type, "REC")) {
        n_rec++;
        const char *o = strstr(frame_json, "\"outcome\":\"");
        if (o) { o += 11; size_t k = 0; while (o[k] && o[k] != '"' && k < 63) { last_rec_outcome[k] = o[k]; k++; } last_rec_outcome[k] = 0; }
        if (script.ack_rec) { snprintf(json, sizeof(json), "{\"seq\":%u}", (unsigned)seq); reply("RECACK", seq, json); }
    } else if (!strcmp(type, "TERM")) {
        n_term++;
        if (script.ack_term) { snprintf(json, sizeof(json), "{\"seq\":%u}", (unsigned)seq); reply("TERMACK", seq, json); }
    } else if (!strcmp(type, "HB")) {
        n_hb++;
    } else {
        n_other++;
    }
}

void outbyte(char c)
{
    if (tx_n < sizeof(tx_line) - 1) tx_line[tx_n++] = c;
    if (c == '\n') { tx_line[tx_n - 1] = 0; on_board_line(tx_line); tx_n = 0; }
}

/* ---- the scenarios ------------------------------------------------------------------- */
/* Feed the orchestrator one candidate as SCORED with an all-zero readout (the staging /
 * ARM path of a scored candidate needs a PL and is not modelled). Returns 0 when the
 * proposal was the CLOSING baseline: it is then handed back (the orchestrator's step is
 * rewound to CLOSING, the proposal count with it) so that the real session loop proposes
 * it — the scenario's refused candidate. */
static int prime_observed(uint32_t seq, int keep_closing)
{
    uint32_t genome[P3_GENOME_WORDS]; int is_baseline, kind;
    static const uint64_t zeros[B1_LUTS];
    static const char zero_tables[6][17] = {"0000000000000000", "0000000000000000", "0000000000000000",
                                            "0000000000000000", "0000000000000000", "0000000000000000"};
    static const char fake_commit[65] = "0000000000000000000000000000000000000000000000000000000000000000";
    if (!b1_orch_next(&O, genome, &is_baseline, &kind)) { fprintf(stderr, "prime: nothing to propose at seq %u\n", (unsigned)seq); exit(3); }
    if (is_baseline && O.step == B1_STEP_DONE && !keep_closing) {
        O.step = B1_STEP_CLOSING; O.candidates--;
        return 0;
    }
    /* exactly the application's own bookkeeping for a SCORED candidate (b1_app.c
     * note_scored), never a hand-written subset of it — plus the orchestrator's observation
     * and the seq, which run_candidate sets before the sign exchange */
    S.seq = seq;
    b1_orch_observe(&O, seq, zeros);
    note_scored(is_baseline, fake_commit, zero_tables);
    return 1;
}

static void print_result(const char *scenario)
{
    printf("RESULT {\"scenario\":\"%s\",\"kind\":\"%s\",\"reason\":\"%s\",\"seq\":%u,\"orch_step\":%d,\"signreq\":%u,\"rec\":%u,\"term\":%u,\"hb\":%u,\"other\":%u,"
           "\"last_rec_outcome\":\"%s\",\"ctrl_writes\":%u,\"payload_writes\":%u,\"dma\":%u,\"closing_restore\":%d,\"closing_baseline\":%d,\"closing_unsigned\":%d,"
           "\"scored\":%u,\"refused\":%u,\"rec_attempts\":%u,\"have_last_reply\":%d}\n",
           scenario, END_NAME[S.kind], S.reason ? S.reason : "", (unsigned)S.seq, O.step, n_signreq, n_rec, n_term, n_hb, n_other,
           last_rec_outcome, ctrl_writes, payload_writes, dma_count, S.closing_restore, S.closing_baseline, S.closing_unsigned,
           (unsigned)S.scored, (unsigned)S.refused, (unsigned)S.rec_attempts, S.have_last_reply);
}

int main(int argc, char **argv)
{
    const char *scenario = argc > 1 ? argv[1] : "opening";
    memset(&S, 0, sizeof(S));
    S.kind = P3_RUNNING;
    snprintf(S.page.token, sizeof(S.page.token), "%s", "a13f38b53355fd4c1cac3145244727f8");
    S.page.seed = 1123460948u; S.page.budget = 333u; S.page.flags = 0x32u; S.page.app_image_sha_lo32 = 0xba4d6c8u;
    S.rec_control = 0; S.sign_control = 0;
    script.ack_rec = 1; script.ack_term = 1;
    b1_session_init();
    if (!strcmp(scenario, "opening")) {
        script.signref_at_seq = 1;
    } else if (!strcmp(scenario, "probe")) {
        (void)prime_observed(1, 0);               /* the opening baseline, scored */
        script.signref_at_seq = 2;
    } else if (!strcmp(scenario, "closing")) {
        /* the opening baseline and every probe the orchestrator proposes, observed as all
         * zero (no decode, no confirmation, no pairs: the orchestrator reaches the closing
         * baseline after fewer than 333 probes — the harness primes until it does) */
        (void)prime_observed(1, 0);
        while (prime_observed(S.seq + 1u, 0)) { }
        script.signref_at_seq = (int)S.seq + 1;
    } else if (!strcmp(scenario, "ack_fail")) {
        script.signref_at_seq = 1; script.ack_rec = 0;
    } else if (!strcmp(scenario, "state_after_opening")) {
        /* the application's state after a SCORED opening baseline, no session run */
        (void)prime_observed(1, 0);
        print_result(scenario); return 0;
    } else if (!strcmp(scenario, "state_after_closing")) {
        /* … after every candidate INCLUDING the closing baseline scored */
        (void)prime_observed(1, 1);
        while (O.step != B1_STEP_DONE) (void)prime_observed(S.seq + 1u, 1);
        print_result(scenario); return 0;
    } else {
        fprintf(stderr, "unknown scenario %s\n", scenario); return 2;
    }
    b1_session_run();
    b1_session_finish();
    print_result(scenario);
    return 0;
}
