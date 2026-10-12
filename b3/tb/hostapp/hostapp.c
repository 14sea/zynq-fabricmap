/* b3/tb/hostapp — the REAL b3/firmware/b3_app.c executed off-board (B3 lifecycle 2, image stage 6; the discipline
 * of tb/b2/hostapp). The application is #included verbatim and compiled with the image's own compile branch
 * (-DB3_EMIT_SHA); what surrounds it is a fake memory map, a scripted host on the console and a MINIMAL fake of
 * the PL and of the DevC DMA (the owner's ruling of 2026-10-12 on the stage-6 scope):
 *
 *   - the fabric: the additive truth model (b1_model.Fabric over the truth mapping, which the test writes to a
 *     file) applied to the genome the host signed — so an O-arm ledger can be held to the prediction;
 *   - the ARM: payload / tag words latched; a zero tag is refused (fault, cfg_valid 0), any other accepted
 *     (scorer_done, cfg_valid); the nonce steps on every ARM (p3_nonce_step); the readout is the fabric's, the
 *     hardware commit the payload's;
 *   - the PCAP: the configuration frames a WRITE_ENVELOPE DMA carries are kept by target frame; a READ_COMMAND
 *     names a target (its words are matched against p3_build_readback_command); a READ_FRAME writes the pad
 *     frame (zeros) and that target frame to its destination. Nothing of the carrier is re-done.
 *   - the DevC: every DMA_DEST_LEN write is a SUBMISSION whose four registers are recorded (a "DMA" line). Its
 *     status, its data write and its completion are separate, controllable events: by default D_P_DONE and
 *     DMA_DONE appear on the first status poll and the data is written then; a fault rule can make the status
 *     never complete, show an error bit, complete on a given poll, show DMA_DONE only, or defer the data. A
 *     submission that has not completed stays PENDING whatever the application does — a function returning,
 *     the epoch stopping, the TERM — and its late events can still be fired (`late=` below).
 *
 * NOTHING IS PRIMED: every candidate before the one a scenario is about runs the application's whole path
 * (sign, stage, link 2, the DMAs, link 3, the ARM, observe, the block, the record) — a pair's 3 005 candidates take
 * about two seconds here.
 *
 * The phase of a submission is the application's own state when it is made: CANDIDATE while the epoch runs,
 * AFTER_STOP once it has stopped (the restore-only cleanup of b3_session_finish). They are counted apart.
 *
 *   hostapp <mode> <fabric file> [key=value ...]
 *   mode  session — init / run / finish driven here (b3_session_*), the page set directly
 *         startup — the application's REAL main(): the identity page is written to the fake memory
 *   keys  master budget total first count reserved   the page (defaults: the B3 profile, slice 0,1)
 *         refuse=S       the host answers SIGNREF at seq S (0: never)
 *         ackrec ackterm ackident strict   the host's acknowledgements (1 by default; strict: ACK only an identity
 *                        whose slice is the page's)
 *         fault=K@N:M[:P]  the N-th CANDIDATE submission of kind K (env | cmd | frame | clean) behaves as M:
 *                        never | error | poll (completes on status poll P) | dmadone (DMA_DONE only, never
 *                        D_P_DONE) | defer (completes, its data deferred)
 *         sticky=1       every submission after the faulted one never completes either
 *         late=W         fire every pending submission's deferred data (and, for one that never completed, its
 *                        completion) at W: stop (the first submission after the stop), term (when the TERM is
 *                        sent), cleanpoll (on the first status poll of the first after-stop submission, the
 *                        pending submission's D_P_DONE appears in INT_STS)
 *   prints one JSON line per frame the application sent ("frame"), one per submission ("dma"), and RESULT.
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
static int npages, last_page = -1;
static uint8_t *page_for(uint32_t addr)
{
    uint32_t base = addr & ~((1u << PAGE_BITS) - 1u);
    if (last_page >= 0 && pages[last_page].base == base) return pages[last_page].mem;
    for (int i = 0; i < npages; i++) if (pages[i].base == base) { last_page = i; return pages[i].mem; }
    if (npages >= NPAGES) { fprintf(stderr, "fake memory: too many pages\n"); exit(3); }
    pages[npages].base = base; pages[npages].mem = calloc(1, 1u << PAGE_BITS);
    last_page = npages;
    return pages[npages++].mem;
}
static uint32_t mem_rd(uint32_t a) { uint32_t v; memcpy(&v, page_for(a) + (a & ((1u << PAGE_BITS) - 1u)), 4); return v; }
static void mem_wr(uint32_t a, uint32_t v) { memcpy(page_for(a) + (a & ((1u << PAGE_BITS) - 1u)), &v, 4); }

/* the application, verbatim, BEFORE the fakes that need its types and state */
u32 Xil_In32(u32 addr);
void Xil_Out32(u32 addr, u32 value);
#define main b3_app_main
#include "b3_app.c"
#undef main
#include "b3_seed_data.h"      /* the two session profiles (b3_orch.c reads the same header) */

/* ---- the fabric: the additive truth model --------------------------------------------- */
#define FAB_N 292
static int fab_k[FAB_N], fab_v[FAB_N];         /* -1: the bit maps to nothing */
static uint32_t cur_genome[P3_GENOME_WORDS];  /* the genome the host last signed */
static void load_fabric(const char *path)
{
    FILE *f = fopen(path, "r");
    int i, k, v, n = 0;
    char dash[8];
    if (!f) { fprintf(stderr, "fabric: cannot open %s\n", path); exit(3); }
    for (i = 0; i < FAB_N; i++) fab_k[i] = fab_v[i] = -1;
    while (fscanf(f, "%d", &i) == 1) {
        if (i < 0 || i >= FAB_N) { fprintf(stderr, "fabric: bit %d\n", i); exit(3); }
        if (fscanf(f, "%d %d", &k, &v) == 2) { fab_k[i] = k; fab_v[i] = v; }
        else if (fscanf(f, "%7s", dash) != 1 || strcmp(dash, "-")) { fprintf(stderr, "fabric: line %d\n", i); exit(3); }
        n++;
    }
    fclose(f);
    if (n != FAB_N) { fprintf(stderr, "fabric: %d lines, not %d\n", n, FAB_N); exit(3); }
}
static void fabric(const uint32_t g[P3_GENOME_WORDS], uint64_t t[B2_LUTS])
{
    int i;
    for (i = 0; i < B2_LUTS; i++) t[i] = 0;
    for (i = 0; i < FAB_N; i++)
        if (((g[i / 32] >> (i % 32)) & 1u) && fab_k[i] >= 0)
            t[fab_k[i]] |= (uint64_t)1 << fab_v[i];
}

/* ---- the PL's AXI window ---------------------------------------------------------------- */
static uint64_t fake_nonce = 0x9e3779b97f4a7c15ull;
static uint32_t payload_w[20], tag_w[4], status_now = (1u << 8) | (1u << 11), fault_now, hb_count = 1000;
static uint32_t hw_commit[8], readout_w[12];
static unsigned ctrl_writes, arms_candidate, arms_after_stop, arms_refused, axi_reads;

static void pl_arm(void)
{
    uint64_t t[B2_LUTS];
    int i, zero = 1;
    if (S.kind == P3_RUNNING) arms_candidate++; else arms_after_stop++;
    for (i = 0; i < 4; i++) if (tag_w[i]) zero = 0;
    fake_nonce = p3_nonce_step(fake_nonce);           /* the attempt is consumed either way */
    for (i = 0; i < 8; i++) hw_commit[i] = payload_w[i];
    fabric(cur_genome, t);
    for (i = 0; i < 6; i++) { readout_w[2 * i] = (uint32_t)(t[i] >> 32); readout_w[2 * i + 1] = (uint32_t)t[i]; }
    if (zero) { status_now = (1u << 8) | (1u << 11) | (1u << 1); fault_now = 1; arms_refused++; }
    else status_now = (1u << 8) | (1u << 11) | (1u << 2) | (1u << 4);
}

/* ---- the DevC DMA ------------------------------------------------------------------------- */
enum { K_ENV, K_CMD, K_FRAME, K_CLEAN, K_OTHER };
static const char *const KIND_NAME[] = {"env", "cmd", "frame", "clean", "other"};
enum { M_OK, M_NEVER, M_ERROR, M_POLL, M_DMADONE, M_DEFER };
typedef struct {
    uint32_t src, dst, slen, dlen;
    int kind, after_stop, ordinal;      /* ordinal: among CANDIDATE submissions of its kind, 1-based */
    uint32_t seq;                       /* the application's S.seq when it was submitted */
    int mode, poll_at;                  /* how it behaves */
    unsigned polls;
    int done, data_done, target;
} dma_t;
#define MAXQ 200000
static dma_t q[MAXQ];
static int nq, cur = -1;
static uint32_t devc_src, devc_dst, devc_slen, devc_sts;
static int n_kind_candidate[5], n_kind_after_stop[5], fault_kind = -1, fault_n, fault_mode = M_OK, fault_p, sticky,
           stuck, late_when; /* 0 none, 1 stop, 2 term, 3 cleanpoll */
static int late_fired, late_applied, read_target = -1;
static uint32_t cfg[P3_TARGET_FRAMES][P3_FRAME_WORDS];
static int cfg_has[P3_TARGET_FRAMES];

static int classify(uint32_t src, uint32_t dst, uint32_t slen)
{
    if (dst == PCAP_ENDPOINT && (src & ~3u) >= P3_WR_BUF && (src & ~3u) < P3_WR_BUF + 3u * 4u * P3_STREAM_WORDS) return K_ENV;
    if (dst == PCAP_ENDPOINT && (src & ~3u) == P3_CMD_BUF && slen == P3_READBACK_CMD_WORDS) return K_CMD;
    if (dst == PCAP_ENDPOINT && (src & ~3u) == P3_CMD_BUF && slen == P3_CLEANUP_WORDS) return K_CLEAN;
    if (src == PCAP_ENDPOINT && (dst & ~3u) == P3_DST_BUF) return K_FRAME;
    return K_OTHER;
}

/* what the transfer DOES once its data moves: the PCAP side of the minimal model */
static void dma_data(dma_t *d)
{
    uint32_t i;
    if (d->data_done) return;
    d->data_done = 1;
    if (d->kind == K_ENV) {
        static uint32_t words[P3_STREAM_WORDS], frames5[P3_ENVELOPE_FRAMES][P3_FRAME_WORDS];
        uint32_t far_set; int e, k;
        for (i = 0; i < P3_STREAM_WORDS; i++) words[i] = mem_rd((d->src & ~3u) + 4u * i);
        if (p3_parse_stream(words, &far_set, frames5) != 0) return;   /* a stream the fake cannot parse configures nothing */
        for (e = 0; e < P3_ENVELOPE_COUNT; e++)
            if (P3_ENVELOPE[e].far_set == far_set)
                for (k = 0; k < 4; k++) { memcpy(cfg[P3_ENVELOPE[e].target[k]], frames5[k], sizeof(cfg[0])); cfg_has[P3_ENVELOPE[e].target[k]] = 1; }
    } else if (d->kind == K_CMD) {
        uint32_t cmd[P3_READBACK_CMD_WORDS], want[P3_READBACK_CMD_WORDS]; int t;
        for (i = 0; i < P3_READBACK_CMD_WORDS; i++) cmd[i] = mem_rd((d->src & ~3u) + 4u * i);
        read_target = -1;
        for (t = 0; t < P3_TARGET_FRAMES; t++) {
            p3_build_readback_command(P3_TARGET_FARS[t], want);
            if (!memcmp(cmd, want, sizeof(cmd))) read_target = t;
        }
        d->target = read_target;
    } else if (d->kind == K_FRAME) {
        d->target = read_target;
        for (i = 0; i < d->dlen; i++) {
            uint32_t w = 0;
            if (i >= P3_FRAME_WORDS && i < 2u * P3_FRAME_WORDS && read_target >= 0 && cfg_has[read_target])
                w = cfg[read_target][i - P3_FRAME_WORDS];
            mem_wr((d->dst & ~3u) + 4u * i, w);
        }
    }
}

static void print_dma(const dma_t *d, int idx)
{
    printf("{\"dma\":%d,\"seq\":%u,\"kind\":\"%s\",\"phase\":\"%s\",\"ordinal\":%d,\"src\":\"%08x\",\"dst\":\"%08x\",\"src_len\":%u,"
           "\"dst_len\":%u,\"mode\":%d}\n", idx, (unsigned)d->seq, KIND_NAME[d->kind], d->after_stop ? "after_stop" : "candidate", d->ordinal,
           d->src, d->dst, d->slen, d->dlen, d->mode);
}

static void fire_late(int upto)      /* the late events of every submission before `upto` still pending, once */
{
    int i;
    if (late_fired) return;
    late_fired = 1;
    for (i = 0; i < upto; i++)
        if (!q[i].data_done && (q[i].mode == M_DEFER || q[i].mode == M_NEVER || q[i].mode == M_DMADONE)) {
            q[i].done = 1;
            dma_data(&q[i]);
            late_applied++;
        }
}

static void submit(uint32_t dlen)
{
    dma_t *d;
    if (nq >= MAXQ) { fprintf(stderr, "too many DMA submissions\n"); exit(3); }
    if (late_when == 1 && S.kind != P3_RUNNING) fire_late(nq);
    d = &q[nq];
    memset(d, 0, sizeof(*d));
    d->src = devc_src; d->dst = devc_dst; d->slen = devc_slen; d->dlen = dlen; d->seq = S.seq;
    d->kind = classify(d->src, d->dst, d->slen);
    d->after_stop = S.kind != P3_RUNNING;
    d->target = -1;
    if (d->after_stop) n_kind_after_stop[d->kind]++;
    else d->ordinal = ++n_kind_candidate[d->kind];
    d->mode = M_OK;
    if (stuck) d->mode = M_NEVER;
    else if (!d->after_stop && d->kind == fault_kind && d->ordinal == fault_n) {
        d->mode = fault_mode; d->poll_at = fault_p;
        if (sticky) stuck = 1;
    }
    print_dma(d, nq);
    cur = nq++;
}

static uint32_t devc_status(void)
{
    dma_t *d;
    if (cur < 0) return devc_sts;
    d = &q[cur];
    d->polls++;
    if (late_when == 3 && !late_fired && d->after_stop && d->polls == 1) {   /* a pending submission completes now, once */
        int i, any = 0;
        for (i = 0; i < cur; i++) if (!q[i].done && (q[i].mode == M_NEVER || q[i].mode == M_DMADONE)) any = 1;
        if (any) { fire_late(cur); devc_sts |= INT_STS_D_P_DONE | INT_STS_DMA_DONE; return devc_sts; }
    }
    switch (d->mode) {
    case M_NEVER: break;
    case M_ERROR: devc_sts |= (1u << 18); break;                  /* RX_FIFO_OV, inside INT_STS_ERROR_MASK */
    case M_DMADONE: devc_sts |= INT_STS_DMA_DONE; break;
    case M_POLL: if (d->polls >= (unsigned)d->poll_at && !d->done) { d->done = 1; dma_data(d); devc_sts |= INT_STS_D_P_DONE | INT_STS_DMA_DONE; } break;
    case M_DEFER: if (!d->done) { d->done = 1; devc_sts |= INT_STS_D_P_DONE | INT_STS_DMA_DONE; } break;
    default: if (!d->done) { d->done = 1; dma_data(d); } devc_sts |= INT_STS_D_P_DONE | INT_STS_DMA_DONE; break;
    }
    return devc_sts;
}

u32 Xil_In32(u32 addr)
{
    if ((addr & 0xFFFF0000u) == P3_AXI_BASE) {
        uint32_t off = addr - P3_AXI_BASE; axi_reads++;
        if (off == P3_STATUS) return status_now;
        if (off == P3_FAULT) return fault_now;
        if (off == P3_HEARTBEAT) return ++hb_count;
        if (off == P3_NONCE_LO) return (uint32_t)fake_nonce;
        if (off == P3_NONCE_HI) return (uint32_t)(fake_nonce >> 32);
        if (off == P3_VARIANT) return B2_VARIANT_WORD;
        if (off >= P3_HW_COMMIT0 && off < P3_HW_COMMIT0 + 32u) return hw_commit[(off - P3_HW_COMMIT0) / 4u];
        if (off >= P3_READOUT0 && off < P3_READOUT0 + 48u) return readout_w[(off - P3_READOUT0) / 4u];
        if (off >= P3_SCORE0 && off < P3_SCORE0 + 24u) {
            int k = (int)((off - P3_SCORE0) / 4u);
            return (uint32_t)__builtin_popcountll(((uint64_t)readout_w[2 * k] << 32) | readout_w[2 * k + 1]);
        }
        return 0;
    }
    if (addr == DEVCFG_CTRL) return CTRL_PCAP_MASK;
    if (addr == DEVCFG_INT_STS) return devc_status();
    if (addr == SLCR_PSS_IDCODE) return 0x13722093u;
    return mem_rd(addr);
}

void Xil_Out32(u32 addr, u32 value)
{
    if ((addr & 0xFFFF0000u) == P3_AXI_BASE) {
        uint32_t off = addr - P3_AXI_BASE;
        if (off == P3_CTRL) { ctrl_writes++; if (value & P3_ARM_STROBE) pl_arm(); }
        else if (off >= P3_PAYLOAD0 && off < P3_PAYLOAD0 + 80u) payload_w[(off - P3_PAYLOAD0) / 4u] = value;
        else if (off >= P3_TAG0 && off < P3_TAG0 + 16u) tag_w[(off - P3_TAG0) / 4u] = value;
        return;
    }
    if (addr == DEVCFG_INT_STS) { devc_sts &= ~value; cur = -1; return; }   /* write-to-clear; no submission is polled now */
    if (addr == DEVCFG_DMA_SRC_ADDR) { devc_src = value; return; }
    if (addr == DEVCFG_DMA_DEST_ADDR) { devc_dst = value; return; }
    if (addr == DEVCFG_DMA_SRC_LEN) { devc_slen = value; return; }
    if (addr == DEVCFG_DMA_DEST_LEN) { submit(value); return; }
    mem_wr(addr, value);
}

/* the watchdog and the timer */
static XScuWdt_Config wcfg = {0xF8F00620u};
static int wdt_kicks;
XScuWdt_Config *XScuWdt_LookupConfig(u16 id) { (void)id; return &wcfg; }
int XScuWdt_CfgInitialize(XScuWdt *w, XScuWdt_Config *c, u32 base) { w->IsReady = 1; w->BaseAddr = base; (void)c; return 0; }
void XScuWdt_SetControlReg(XScuWdt *w, u32 v) { (void)w; (void)v; }
void XScuWdt_LoadWdt(XScuWdt *w, u32 v) { (void)w; (void)v; }
void XScuWdt_Start(XScuWdt *w) { (void)w; }
void XScuWdt_RestartWdt(XScuWdt *w) { (void)w; wdt_kicks++; }
static u64 fake_ticks;
void XTime_GetTime(XTime *t) { fake_ticks += 100u; *t = fake_ticks; }
void XTime_SetTime(XTime t) { fake_ticks = t; }

/* ---- the scripted host on the console ------------------------------------------------ */
static struct { unsigned refuse, ack_rec, ack_term, ack_ident, strict, want_total, want_first, want_count; } script;
static unsigned n_ident, n_identack, n_signreq, n_signreq_after_stop, n_rec, n_term, n_hb, n_close, n_audit_ready, n_other;
static int ident_slice[3] = {-1, -1, -1}, ident_findings_empty = 1;
static char tx_line[B3_LINE_MAX + 64]; static size_t tx_n;
static char rx_q[1 << 16]; static size_t rx_head, rx_tail;
static char frame_json[B3_PAYLOAD_MAX + 64];
static char outcomes[64][24]; static int n_outcomes;
static const char ZERO16[] = "0000000000000000";

static void rx_push(const char *s) { while (*s) rx_q[rx_tail++ % sizeof(rx_q)] = *s++; }
int console_rx_ready(void) { return rx_head != rx_tail; }
char inbyte(void) { return rx_q[rx_head++ % sizeof(rx_q)]; }
int console_rx_flush(void) { int n = (int)(rx_tail - rx_head); rx_head = rx_tail; return n; }

static void reply(const char *type, uint32_t seq, const char *json)
{
    static char b64[8192], line[12288];
    p3_base64url((const uint8_t *)json, strlen(json), b64);
    if (p3_wire_line(type, seq, S.page.token, b64, line, sizeof(line)) == 0u) { fprintf(stderr, "reply too long\n"); exit(3); }
    rx_push(line);
}

/* the notary's half: the commit is the hash of the frames the signed genome derives (what link 2 / link 3 compare),
 * the tables are zero (the B1 contract: the host attests no semantics), the tag any non-zero value */
static void sign(uint32_t seq, const char *genome_hex)
{
    static uint32_t frames[P3_TARGET_FRAMES][P3_FRAME_WORDS];
    uint8_t digest[32]; char commit[65], json[1024];
    if (p3_genome_from_hex(genome_hex, cur_genome) != 0) { fprintf(stderr, "sign: bad genome\n"); exit(3); }
    p3_derive_frames(cur_genome, frames);
    p3_frames_hash(P3_CFRAMES(frames), digest);
    p3_hex(digest, 32, commit);
    snprintf(json, sizeof(json), "{\"audit_requested\":false,\"commit\":\"%s\",\"expected_tables\":[\"%s\",\"%s\",\"%s\",\"%s\",\"%s\",\"%s\"],"
             "\"schema\":\"sign_reply\",\"schema_version\":\"1.0.0\",\"seq\":%u,\"tag\":\"0123456789abcdef0123456789abcdef\"}",
             commit, ZERO16, ZERO16, ZERO16, ZERO16, ZERO16, ZERO16, (unsigned)seq);
    reply("SIGNOK", seq, json);
}

static void on_board_line(char *line)
{
    char type[24]; uint32_t seq; static char copy[B3_LINE_MAX + 64]; char json[256];
    snprintf(copy, sizeof(copy), "%s", line);
    const char *payload = parse_frame_any(copy, type, sizeof(type), &seq);
    if (!payload) { printf("{\"frame\":\"UNPARSED\"}\n"); n_other++; return; }
    size_t jn = strcmp(payload, "-") ? p3_base64url_decode(payload, (uint8_t *)frame_json, sizeof(frame_json) - 1u) : 0u;
    frame_json[jn] = 0;
    if (strcmp(type, "HB"))                       /* heartbeats are counted, not printed */
        printf("{\"frame\":\"%s\",\"seq\":%u,\"payload\":%s}\n", type, (unsigned)seq, jn ? frame_json : "null");
    if (!strcmp(type, "IDENT")) {
        long v[3] = {-1, -1, -1};
        static const char *const key[3] = {"\"pairs_total\":", "\"pair_first\":", "\"pair_count\":"};
        int i;
        n_ident++;
        for (i = 0; i < 3; i++) { const char *k = strstr(frame_json, key[i]); if (k) v[i] = strtol(k + strlen(key[i]), NULL, 10); }
        for (i = 0; i < 3; i++) ident_slice[i] = (int)v[i];
        if (!strstr(frame_json, "\"findings\":[]")) ident_findings_empty = 0;
        if (script.ack_ident && (!script.strict ||
            (v[0] == (long)script.want_total && v[1] == (long)script.want_first && v[2] == (long)script.want_count))) {
            n_identack++;
            snprintf(json, sizeof(json), "{\"seq\":%u}", (unsigned)seq);
            reply("IDENTACK", seq, json);
        }
    } else if (!strcmp(type, "SIGNREQ")) {
        const char *g = strstr(frame_json, "\"genome\":\"");
        char genome_hex[P3_GENOME_WORDS * 8 + 1];
        n_signreq++;
        if (S.kind != P3_RUNNING) n_signreq_after_stop++;
        if (!g) { fprintf(stderr, "SIGNREQ without a genome\n"); exit(3); }
        memcpy(genome_hex, g + 10, P3_GENOME_WORDS * 8); genome_hex[P3_GENOME_WORDS * 8] = 0;
        if (seq == script.refuse) {
            snprintf(json, sizeof(json), "{\"finding_kinds\":[\"whitelist\"],\"schema\":\"sign_refusal\",\"schema_version\":\"1.0.0\",\"seq\":%u}", (unsigned)seq);
            reply("SIGNREF", seq, json);
        } else
            sign(seq, genome_hex);
    } else if (!strcmp(type, "REC")) {
        const char *o = strstr(frame_json, "\"outcome\":\"");
        n_rec++;
        if (o && n_outcomes < 64) { size_t k = 0; o += 11; while (o[k] && o[k] != '"' && k < 23) { outcomes[n_outcomes][k] = o[k]; k++; } outcomes[n_outcomes++][k] = 0; }
        if (script.ack_rec) { snprintf(json, sizeof(json), "{\"seq\":%u}", (unsigned)seq); reply("RECACK", seq, json); }
    } else if (!strcmp(type, "TERM")) {
        n_term++;
        if (late_when == 2) fire_late(nq);
        if (script.ack_term) { snprintf(json, sizeof(json), "{\"seq\":%u}", (unsigned)seq); reply("TERMACK", seq, json); }
    } else if (!strcmp(type, "HB")) {
        n_hb++;
    } else if (!strcmp(type, "CLOSE")) {
        n_close++;
    } else if (!strcmp(type, "AUDIT_READY")) {     /* the host does not pull: it aborts (the record then says replayed-only) */
        n_audit_ready++;
        snprintf(json, sizeof(json), "{\"seq\":%u}", (unsigned)seq);
        reply("AUDITABORT", seq, json);
    } else {
        n_other++;
    }
}

void outbyte(char c)
{
    if (tx_n < sizeof(tx_line) - 1) tx_line[tx_n++] = c;
    if (c == '\n') { tx_line[tx_n - 1] = 0; on_board_line(tx_line); tx_n = 0; }
}

static void print_result(const char *mode)
{
    int i;
    printf("RESULT {\"mode\":\"%s\",\"kind\":\"%s\",\"reason\":\"%s\",\"seq\":%u,\"orch_phase\":%d,\"orch_complete\":%d,"
           "\"ident\":%u,\"identack\":%u,\"ident_slice\":[%d,%d,%d],\"ident_findings_empty\":%d,"
           "\"signreq\":%u,\"signreq_after_stop\":%u,\"rec\":%u,\"term\":%u,\"hb\":%u,\"close\":%u,\"audit_ready\":%u,\"other\":%u,"
           "\"ctrl_writes\":%u,\"arms_candidate\":%u,\"arms_after_stop\":%u,\"arms_refused\":%u,"
           "\"dma_candidate\":{\"env\":%d,\"cmd\":%d,\"frame\":%d,\"clean\":%d,\"other\":%d},"
           "\"dma_after_stop\":{\"env\":%d,\"cmd\":%d,\"frame\":%d,\"clean\":%d,\"other\":%d},\"late_applied\":%d,"
           "\"dst_target_word0\":\"%08x\",\"scored\":%u,\"refused\":%u,\"rec_attempts\":%u,\"closing_restore\":%d,\"closing_baseline\":%d,\"closing_unsigned\":%d,"
           "\"outcomes\":[",
           mode, END_NAME[S.kind], S.reason ? S.reason : "", (unsigned)S.seq, O.phase, b3_orch_complete(&O),
           n_ident, n_identack, ident_slice[0], ident_slice[1], ident_slice[2], ident_findings_empty,
           n_signreq, n_signreq_after_stop, n_rec, n_term, n_hb, n_close, n_audit_ready, n_other,
           ctrl_writes, arms_candidate, arms_after_stop, arms_refused,
           n_kind_candidate[0], n_kind_candidate[1], n_kind_candidate[2], n_kind_candidate[3], n_kind_candidate[4],
           n_kind_after_stop[0], n_kind_after_stop[1], n_kind_after_stop[2], n_kind_after_stop[3], n_kind_after_stop[4],
           late_applied, mem_rd(P3_DST_BUF + 4u * P3_FRAME_WORDS), (unsigned)S.scored, (unsigned)S.refused, (unsigned)S.rec_attempts,
           S.closing_restore, S.closing_baseline, S.closing_unsigned);
    for (i = 0; i < n_outcomes; i++) printf("%s\"%s\"", i ? "," : "", outcomes[i]);
    printf("]}\n");
}

/* a checksummed identity page in the fake memory, exactly as the host writes it */
static void write_page(uint32_t seed, uint32_t budget, uint32_t flags)
{
    uint32_t w[P3_PAGE_WORDS], sum = 0; int i;
    memset(w, 0, sizeof(w));
    w[0] = P3_PAGE_MAGIC; w[1] = P3_PAGE_LAYOUT;
    for (i = 0; i < 4; i++) w[2 + i] = 0xa13f38b5u + (uint32_t)i;      /* the token's 16 bytes */
    w[6] = 0;                                                          /* uboot_epoch */
    w[7] = 0xf54b0ae9u;                                                /* image sha lo32 */
    for (i = 0; i < 8; i++) w[8 + i] = 0xd85daef4u + (uint32_t)i;      /* the carrier hash */
    w[16] = (uint32_t)fake_nonce; w[17] = (uint32_t)(fake_nonce >> 32);
    w[18] = (1u << 8) | (1u << 11);                                    /* the STATUS the fake AXI returns */
    w[19] = seed; w[20] = budget; w[21] = flags; w[22] = 50000000u;
    for (i = 0; i < P3_PAGE_WORDS - 1; i++) sum ^= w[i];
    w[P3_PAGE_WORDS - 1] = sum;
    for (i = 0; i < P3_PAGE_WORDS; i++) mem_wr(P3_PAGE_ADDR + 4u * (uint32_t)i, w[i]);
}

static long opt(int argc, char **argv, const char *key, long dflt)
{
    size_t n = strlen(key); int i;
    for (i = 3; i < argc; i++) if (!strncmp(argv[i], key, n) && argv[i][n] == '=') return strtol(argv[i] + n + 1, NULL, 0);
    return dflt;
}
static const char *sopt(int argc, char **argv, const char *key)
{
    size_t n = strlen(key); int i;
    for (i = 3; i < argc; i++) if (!strncmp(argv[i], key, n) && argv[i][n] == '=') return argv[i] + n + 1;
    return NULL;
}

static void parse_fault(const char *f)
{
    char kind[8], mode[12]; int n = 0, p = 0, k;
    if (!f) return;
    if (sscanf(f, "%7[a-z]@%d:%11[a-z]:%d", kind, &n, mode, &p) < 3) { fprintf(stderr, "fault=%s\n", f); exit(2); }
    for (k = 0; k < 4; k++) if (!strcmp(kind, KIND_NAME[k])) fault_kind = k;
    if (fault_kind < 0 || n < 1) { fprintf(stderr, "fault kind %s\n", kind); exit(2); }
    fault_n = n; fault_p = p;
    if (!strcmp(mode, "never")) fault_mode = M_NEVER;
    else if (!strcmp(mode, "error")) fault_mode = M_ERROR;
    else if (!strcmp(mode, "poll")) fault_mode = M_POLL;
    else if (!strcmp(mode, "dmadone")) fault_mode = M_DMADONE;
    else if (!strcmp(mode, "defer")) fault_mode = M_DEFER;
    else { fprintf(stderr, "fault mode %s\n", mode); exit(2); }
    if (fault_mode == M_POLL && p < 1) { fprintf(stderr, "fault poll needs P >= 1\n"); exit(2); }
}

int main(int argc, char **argv)
{
    const char *mode = argc > 1 ? argv[1] : "", *late;
    uint32_t master, budget, flags; int total, first, count;
    if (argc < 3) { fprintf(stderr, "usage: hostapp session|startup <fabric file> [key=value ...]\n"); return 2; }
    load_fabric(argv[2]);
    master = (uint32_t)opt(argc, argv, "master", B3_PROFILE_B3_MASTER);
    budget = (uint32_t)opt(argc, argv, "budget", B3_PROFILE_B3_BUDGET);
    total = (int)opt(argc, argv, "total", B3_PROFILE_B3_PAIRS);
    first = (int)opt(argc, argv, "first", 0);
    count = (int)opt(argc, argv, "count", 1);
    flags = 0x32u | ((uint32_t)(total - 1) << 16) | ((uint32_t)first << 20) | ((uint32_t)(count - 1) << 24)
            | ((uint32_t)opt(argc, argv, "reserved", 0) << 28);
    script.refuse = (unsigned)opt(argc, argv, "refuse", 0);
    script.ack_rec = (unsigned)opt(argc, argv, "ackrec", 1);
    script.ack_term = (unsigned)opt(argc, argv, "ackterm", 1);
    script.ack_ident = (unsigned)opt(argc, argv, "ackident", 1);
    script.strict = (unsigned)opt(argc, argv, "strict", 0);
    script.want_total = (unsigned)total; script.want_first = (unsigned)first; script.want_count = (unsigned)count;
    parse_fault(sopt(argc, argv, "fault"));
    sticky = (int)opt(argc, argv, "sticky", 0);
    late = sopt(argc, argv, "late");
    late_when = !late ? 0 : !strcmp(late, "stop") ? 1 : !strcmp(late, "term") ? 2 : !strcmp(late, "cleanpoll") ? 3 : -1;
    if (late_when < 0) { fprintf(stderr, "late=%s\n", late); return 2; }

    if (!strcmp(mode, "startup")) {
        write_page(master, budget, flags);
        (void)b3_app_main();
        print_result(mode);
        return 0;
    }
    if (strcmp(mode, "session")) { fprintf(stderr, "mode %s\n", mode); return 2; }
    memset(&S, 0, sizeof(S));
    S.kind = P3_RUNNING;
    snprintf(S.page.token, sizeof(S.page.token), "%s", "a13f38b53355fd4c1cac3145244727f8");
    S.page.seed = master; S.page.budget = budget; S.page.flags = flags;
    S.page.app_image_sha_lo32 = 0xf54b0ae9u;
    /* these sessions drive the three steps directly and so never run establish_identity, which is where the
     * application decodes the slice: do exactly what it does (the startup mode exercises it itself) */
    g_slice_ok = (b3_page_slice(S.page.flags, &g_pairs_total, &g_pair_first, &g_pair_count) == 0);
    if (!g_slice_ok) g_pairs_total = g_pair_first = g_pair_count = 0;
    b3_session_init();
    b3_session_run();
    b3_session_finish();
    print_result(mode);
    return 0;
}
