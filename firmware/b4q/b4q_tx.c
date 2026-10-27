/* b4q_tx — see b4q_tx.h. Every register access goes through the four accessors below with the allowlist checked BEFORE the
 * access (the B1 application's rule); every wait is a bounded poll of STATUS / FAULT; every stop names its reason. */
#include "b4q_tx.h"
#include "b4q_hal.h"
#include "b4q_regmap.h"
#include "b4q_data.h"

#include <stdio.h>
#include <string.h>

/* ─────────────────────────────── the PS address map (firmware/b1's, kept) ─────────────────────────────── */
#define B4Q_AXI_BASE 0x43C00000u
#define DEVCFG_BASE 0xF8007000u
#define DEVCFG_CTRL (DEVCFG_BASE + 0x000u)
#define DEVCFG_INT_STS (DEVCFG_BASE + 0x00Cu)
#define DEVCFG_DMA_SRC_ADDR (DEVCFG_BASE + 0x018u)
#define DEVCFG_DMA_DEST_ADDR (DEVCFG_BASE + 0x01Cu)
#define DEVCFG_DMA_SRC_LEN (DEVCFG_BASE + 0x020u)
#define DEVCFG_DMA_DEST_LEN (DEVCFG_BASE + 0x024u)
#define SLCR_PSS_IDCODE 0xF8000530u
#define B4Q_IDCODE_MASK 0x0FFFFFFFu
#define PCAP_ENDPOINT 0xFFFFFFFFu
#define DMA_HOLD_TAG 0x1u
#define INT_STS_D_P_DONE (1u << 12)
#define INT_STS_ERROR_MASK 0x00F4C840u
#define INT_STS_CLEAR_MASK (INT_STS_ERROR_MASK | INT_STS_D_P_DONE | (1u << 13))
#define CTRL_PCAP_MASK 0x0C000000u
#define DMA_SPIN_LIMIT 100000
#define P3_CMD_BUF 0x10200000u
#define P3_DST_BUF 0x10300000u
#define P3_WR_BUF 0x10400000u
#define P3_SENTINEL 0xA5A5A5A5u

typedef struct { uint32_t src, dst, src_len, dst_len; } b4q_dma;
static const b4q_dma DMA_WRITE_ENVELOPE = {P3_WR_BUF | DMA_HOLD_TAG, PCAP_ENDPOINT, P3_STREAM_WORDS, 0};
static const b4q_dma DMA_READ_COMMAND = {P3_CMD_BUF | DMA_HOLD_TAG, PCAP_ENDPOINT, P3_READBACK_CMD_WORDS, 0};
static const b4q_dma DMA_READ_FRAME = {PCAP_ENDPOINT, P3_DST_BUF | DMA_HOLD_TAG, 0, P3_READBACK_WORDS};
static const b4q_dma DMA_READ_CLEANUP = {P3_CMD_BUF | DMA_HOLD_TAG, PCAP_ENDPOINT, P3_CLEANUP_WORDS, 0};

/* ─────────────────────────────── the carrier window: the allowlist, checked at the accessor ─────────────────────────────── */
static int axi_readable(uint32_t off)
{
    switch (off) {
    case B4Q_STATUS: case B4Q_FAULT: case B4Q_Q_LIVE: case B4Q_IN_LIVE: case B4Q_SLOT_READ: case B4Q_SLOT_ADDR: case B4Q_WITNESS:
    case B4Q_TIMING: case B4Q_HEARTBEAT: case B4Q_NONCE_LO: case B4Q_NONCE_HI: case B4Q_VARIANT: case B4Q_STEP_IN:
    case B4Q_BASE_STATE: case B4Q_SLOT_IN_READ:
        return 1;
    default:
        return off >= B4Q_HW_COMMIT0 && off < B4Q_HW_COMMIT0 + 4u * B4Q_HW_COMMIT_WORDS && (off & 3u) == 0u;
    }
}

static int axi_writable(uint32_t off)
{
    if (off == B4Q_CTRL || off == B4Q_SLOT_ADDR || off == B4Q_STEP_IN)
        return 1;
    if (off >= B4Q_PAYLOAD0 && off < B4Q_PAYLOAD0 + 4u * B4Q_PAYLOAD_WORDS && (off & 3u) == 0u)
        return 1;
    if (off >= B4Q_TAG0 && off < B4Q_TAG0 + 4u * B4Q_TAG_WORDS && (off & 3u) == 0u)
        return 1;
    return 0;   /* the key window among the rest: the signer principal's, never this program's */
}

static const char *g_stop;      /* the first named stop of the current call */
static char g_phase[5];

static void stop(const char *why) { if (!g_stop) g_stop = why; }
static void phase(const char *p) { strncpy(g_phase, p, sizeof g_phase - 1); g_phase[sizeof g_phase - 1] = 0; }

static uint32_t axi_rd(uint32_t off)
{
    uint32_t resp = B4Q_RESP_OKAY, v;
    if (!axi_readable(off)) { stop("STOP_AXI: read outside the pinned map"); return 0; }
    v = b4q_rd32(B4Q_AXI_BASE + off, &resp);
    if (resp != B4Q_RESP_OKAY) stop("STOP_AXI: a read of the pinned map answered SLVERR");
    return v;
}

static uint32_t axi_wr(uint32_t off, uint32_t v)
{
    uint32_t resp;
    if (!axi_writable(off)) { stop("STOP_AXI: write outside the pinned map"); return B4Q_RESP_SLVERR; }
    resp = b4q_wr32(B4Q_AXI_BASE + off, v);
    if (resp != B4Q_RESP_OKAY && off != B4Q_CTRL) stop("STOP_AXI: a write of the pinned map answered SLVERR (the register is not what this side meant to stage)");
    return resp;                                   /* a CTRL SLVERR is the register file's refusal: the caller names it */
}

static uint32_t mem_rd(uint32_t a) { uint32_t resp; return b4q_rd32(a, &resp); }
static void mem_wr(uint32_t a, uint32_t v) { (void)b4q_wr32(a, v); }

static uint64_t pl_nonce(void)
{
    uint32_t lo = axi_rd(B4Q_NONCE_LO), hi = axi_rd(B4Q_NONCE_HI);
    return (uint64_t)lo | ((uint64_t)hi << 32);
}

static int bit(uint32_t w, unsigned b) { return (int)((w >> b) & 1u); }

static void emitf(const char *fmt, const char *a, const char *b)
{
    char line[256];
    snprintf(line, sizeof line, fmt, a, b);
    b4q_emit(line);
}

/* ─────────────────────────────── the waits: witnesses in STATUS / FAULT, never a bus acknowledgement ─────────────────────────────── */
/* poll STATUS until `done_bit` is set or the engine / gate is idle with a fault latched; 0 ok, -1 fault, -2 ran out */
static int wait_status(unsigned busy_bit, unsigned done_bit, uint32_t *last)
{
    uint32_t i, st = 0;
    for (i = 0; i < B4Q_POLL_LIMIT; i++) {
        st = axi_rd(B4Q_STATUS);
        if (g_stop) { *last = st; return -1; }
        if (bit(st, B4Q_ST_FAULT)) { *last = st; return -1; }
        if (!bit(st, busy_bit) && (done_bit == 32u || bit(st, done_bit))) { *last = st; return 0; }
    }
    *last = st;
    return -2;
}

/* ─────────────────────────────── the DMA (the four tuples) ─────────────────────────────── */
static int devcfg_wait_done(void)
{
    int spins;
    for (spins = 0; spins < DMA_SPIN_LIMIT; spins++) {
        uint32_t sts = mem_rd(DEVCFG_INT_STS);
        if (sts & INT_STS_ERROR_MASK) { stop("STOP_DMA: DEVCFG error bit after a DMA"); return -1; }
        if (sts & INT_STS_D_P_DONE) return 0;     /* D_P_DONE: the DMA and the PCAP; DMA_DONE alone is not */
    }
    stop("STOP_DMA: DEVCFG D_P_DONE never asserted");
    return -1;
}

static int devcfg_dma(const b4q_dma *t, uint32_t src_override)
{
    if ((mem_rd(DEVCFG_CTRL) & CTRL_PCAP_MASK) != CTRL_PCAP_MASK) { stop("STOP_DMA: DEVCFG CTRL is not in PCAP mode"); return -1; }
    mem_wr(DEVCFG_INT_STS, INT_STS_CLEAR_MASK);
    if (mem_rd(DEVCFG_INT_STS) & INT_STS_D_P_DONE) { stop("STOP_DMA: INT_STS would not clear"); return -1; }
    mem_wr(DEVCFG_DMA_SRC_ADDR, src_override ? src_override : t->src);
    mem_wr(DEVCFG_DMA_DEST_ADDR, t->dst);
    mem_wr(DEVCFG_DMA_SRC_LEN, t->src_len);
    mem_wr(DEVCFG_DMA_DEST_LEN, t->dst_len);    /* queues the command */
    return devcfg_wait_done();
}

/* ─────────────────────────────── the candidate: derive, stage, link 2, write, link 3 ─────────────────────────────── */
static uint32_t g_frames[P3_TARGET_FRAMES][P3_FRAME_WORDS];
static uint32_t g_readback[P3_TARGET_FRAMES][P3_FRAME_WORDS];

static void hex_of(const uint8_t *d, char out[65]) { p3_hex(d, 32, out); }

static void derive(uint32_t genome, char commit_hex[65])
{
    uint32_t g[P3_GENOME_WORDS];
    uint8_t d[32];
    g[0] = genome;
    p3_derive_frames(g, g_frames);
    p3_frames_hash(P3_CFRAMES(g_frames), d);
    hex_of(d, commit_hex);
}

static void stage_streams(void)
{
    uint32_t words[P3_STREAM_WORDS];
    int e, i;
    for (e = 0; e < P3_ENVELOPE_COUNT; e++) {
        p3_build_stream(e, P3_CFRAMES(g_frames), words);
        for (i = 0; i < P3_STREAM_WORDS; i++)
            mem_wr(P3_WR_BUF + (uint32_t)e * 4u * P3_STREAM_WORDS + 4u * (uint32_t)i, words[i]);
    }
}

/* link 2: re-read the staged streams FROM DDR, parse them literally, hash what is actually there */
static int link2(char staged_hex[65], char stream_hex[65])
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
            words[i] = mem_rd(P3_WR_BUF + (uint32_t)e * 4u * P3_STREAM_WORDS + 4u * (uint32_t)i);
        p3_sha256_words(&c, words, P3_STREAM_WORDS);
        if (p3_parse_stream(words, &far_set, frames5) != 0 || far_set != P3_ENVELOPE[e].far_set) { stop("STOP_LINK2: the staged stream does not parse"); return -1; }
        for (k = 0; k < 4; k++)
            memcpy(reread[P3_ENVELOPE[e].target[k]], frames5[k], sizeof(frames5[k]));
    }
    p3_sha256_final(&c, digest);
    hex_of(digest, stream_hex);
    p3_frames_hash(P3_CFRAMES(reread), digest);
    hex_of(digest, staged_hex);
    return 0;
}

static int write_envelopes(void)
{
    int e;
    for (e = 0; e < P3_ENVELOPE_COUNT; e++)
        if (devcfg_dma(&DMA_WRITE_ENVELOPE, (P3_WR_BUF + (uint32_t)e * 4u * P3_STREAM_WORDS) | DMA_HOLD_TAG) != 0)
            return -1;
    return 0;
}

/* link 3: the pinned three-command readback of one frame (psmap §8a) */
static int readback_frame(int index)
{
    uint32_t cmd[P3_READBACK_CMD_WORDS];
    uint32_t clean[P3_CLEANUP_WORDS];
    int i;
    for (i = 0; i < P3_READBACK_WORDS; i++)
        mem_wr(P3_DST_BUF + 4u * (uint32_t)i, P3_SENTINEL);
    for (i = 0; i < P3_READBACK_WORDS; i++)
        if (mem_rd(P3_DST_BUF + 4u * (uint32_t)i) != P3_SENTINEL) { stop("STOP_LINK3: the sentinel prefill did not verify"); return -1; }
    p3_build_readback_command(P3_TARGET_FARS[index], cmd);
    for (i = 0; i < P3_READBACK_CMD_WORDS; i++)
        mem_wr(P3_CMD_BUF + 4u * (uint32_t)i, cmd[i]);
    if (devcfg_dma(&DMA_READ_COMMAND, 0) != 0) return -1;
    if (devcfg_dma(&DMA_READ_FRAME, 0) != 0) return -1;
    p3_build_cleanup_command(clean);
    for (i = 0; i < P3_CLEANUP_WORDS; i++)
        mem_wr(P3_CMD_BUF + 4u * (uint32_t)i, clean[i]);
    if (devcfg_dma(&DMA_READ_CLEANUP, 0) != 0) return -1;
    for (i = 0; i < P3_FRAME_WORDS; i++)         /* words [0:101] are the pad frame; [101:202] the target */
        g_readback[index][i] = mem_rd(P3_DST_BUF + 4u * (uint32_t)(P3_FRAME_WORDS + i));
    return 0;
}

static int link3(char readback_hex[65])
{
    uint8_t digest[32];
    int i;
    for (i = 0; i < P3_TARGET_FRAMES; i++)        /* all eight read before judging */
        if (readback_frame(i) != 0) return -1;
    p3_frames_hash(P3_CFRAMES(g_readback), digest);
    hex_of(digest, readback_hex);
    return 0;
}

/* the whole P1 + P2 of a candidate: derive, sign, stage, ARM, link 2, write, link 3 */
static int candidate_in(uint32_t genome, int a5, b4q_tx_result *r, char pre_event_hex[65], char staged_hex[65], char stream_hex[65], char commit_hex[65])
{
    uint32_t words[24], st = 0, commit_w[8];
    char ghex[9], nhex[17];
    uint64_t nonce;
    int i;
    derive(genome, commit_hex);
    for (i = 0; i < 8; i++) {
        uint32_t w = 0; int j;
        for (j = 0; j < 8; j++) { char c = commit_hex[8 * i + j]; w = (w << 4) | (uint32_t)((c <= '9') ? c - '0' : c - 'a' + 10); }
        commit_w[i] = w;
    }
    nonce = pl_nonce();
    r->nonce_before = nonce;
    snprintf(ghex, sizeof ghex, "%08x", (unsigned)genome);
    snprintf(nhex, sizeof nhex, "%016llx", (unsigned long long)nonce);
    if (b4q_sign(ghex, nhex, words) != 0) { stop("STOP_SIGN: the notary refused the candidate"); return -1; }
    for (i = 0; i < 8; i++)
        if (words[i] != commit_w[i]) { stop("STOP_SIGN: the notary signed another commit than this side derived"); return -1; }
    for (i = 0; i < 20; i++) if (axi_wr(B4Q_PAYLOAD0 + 4u * (uint32_t)i, words[i]) != B4Q_RESP_OKAY) return -1;
    for (i = 0; i < 4; i++) if (axi_wr(B4Q_TAG0 + 4u * (uint32_t)i, words[20 + i]) != B4Q_RESP_OKAY) return -1;
    if (axi_wr(B4Q_CTRL, B4Q_CTRL_ARM | (a5 ? B4Q_CTRL_ARM_A5 : 0u)) != B4Q_RESP_OKAY) { stop("STOP_ARM: the CTRL write was SLVERR (busy or malformed)"); return -1; }
    if (wait_status(B4Q_ST_GATE_BUSY, 32u, &st) != 0) { r->fault_code = axi_rd(B4Q_FAULT); stop("STOP_ARM: the gate refused (FAULT latched)"); return -1; }
    /* the armed latch follows tag_ok by a cycle: poll once more for configuration_valid_hw */
    if (wait_status(B4Q_ST_GATE_BUSY, B4Q_ST_CONFIGURATION_VALID_HW, &st) != 0) { r->fault_code = axi_rd(B4Q_FAULT); stop("STOP_ARM: not armed after the verification"); return -1; }
    if (!bit(st, B4Q_ST_TAG_OK)) { stop("STOP_ARM: armed without tag_ok"); return -1; }
    r->nonce_after = pl_nonce();
    for (i = 0; i < 8; i++)
        if (axi_rd(B4Q_HW_COMMIT0 + 4u * (uint32_t)i) != commit_w[i]) { stop("STOP_ARM: HW_COMMIT is not the derived commit"); return -1; }
    stage_streams();
    if (link2(staged_hex, stream_hex) != 0) return -1;
    if (strcmp(staged_hex, commit_hex) != 0) { stop("STOP_LINK2: the re-read frames are not the signed candidate"); return -1; }
    phase("P2");
    if (write_envelopes() != 0) return -1;
    if (link3(pre_event_hex) != 0) return -1;
    if (strcmp(pre_event_hex, commit_hex) != 0) { stop("STOP_LINK3: the pre-event readback is not the signed candidate (no event is raised on it)"); return -1; }
    return 0;
}

static int engine_op(uint32_t op, unsigned done_bit, uint32_t *st, b4q_tx_result *r, const char *name)
{
    int rc;
    if (axi_wr(B4Q_CTRL, op) != B4Q_RESP_OKAY) { stop(name); return -1; }
    rc = wait_status(B4Q_ST_ENGINE_BUSY, done_bit, st);
    if (rc == -2) { stop("STOP_WAIT: the engine did not complete the operation within the poll limit"); return -1; }
    if (rc != 0) { r->fault_code = axi_rd(B4Q_FAULT); stop(name); return -1; }
    return 0;
}

static int read_slot(int a, b4q_tx_result *r)
{
    if (axi_wr(B4Q_SLOT_ADDR, (uint32_t)a) != B4Q_RESP_OKAY) return -1;
    r->slot_q[a] = axi_rd(B4Q_SLOT_READ) & 0xFFu;
    r->slot_in[a] = axi_rd(B4Q_SLOT_IN_READ);
    if (a + 1 > r->n_slots) r->n_slots = a + 1;
    return g_stop ? -1 : 0;
}

/* ─────────────────────────────── the session opening ─────────────────────────────── */
int b4q_session_open(b4q_open_result *o)
{
    memset(o, 0, sizeof *o);
    g_stop = NULL; phase("open");
    {
        uint32_t resp;
        o->idcode = b4q_rd32(SLCR_PSS_IDCODE, &resp);
    }
    o->status_word = axi_rd(B4Q_STATUS);
    o->variant = axi_rd(B4Q_VARIANT);
    o->timing = axi_rd(B4Q_TIMING);
    o->witness = axi_rd(B4Q_WITNESS);
    o->heartbeat = axi_rd(B4Q_HEARTBEAT);
    o->nonce = pl_nonce();
    if ((o->idcode & B4Q_IDCODE_MASK) != (P3_IDCODE & B4Q_IDCODE_MASK)) stop("IDENT: PSS_IDCODE is not this part");
    if (!bit(o->status_word, B4Q_ST_ALIVE)) stop("IDENT: STATUS is not the carrier answering");
    if (o->variant != B4Q_VARIANT_WORD) stop("IDENT: VARIANT is not the B4 v2 word");
    if (((o->witness >> B4Q_WIT_MECHANISM_SHIFT) & B4Q_WIT_MECHANISM_MASK) != B4Q_MECHANISM) stop("IDENT: the declared mechanism is not (b)");
    if (!bit(o->status_word, B4Q_ST_KEY_LOADED)) stop("IDENT: key_loaded is 0: not the provisioned carrier");
    if (bit(o->status_word, B4Q_ST_FAULT) || bit(o->status_word, B4Q_ST_RECOVERY_REQUIRED)) stop("IDENT: fault / recovery before start");
    if (!bit(o->status_word, B4Q_ST_IDLE)) stop("IDENT: the carrier is not idle");
    if (g_stop) { o->status = 1; o->reason = g_stop; return -1; }
    /* the startup readback of the loaded image's write set (link 3), before anything is signed */
    if (link3(o->startup_readback_hex) != 0) { o->status = 1; o->reason = g_stop; return -1; }
    o->status = 0; o->reason = "opened";
    emitf("EV open startup_readback=%s %s", o->startup_readback_hex, "");
    return 0;
}

/* ─────────────────────────────── one transaction ─────────────────────────────── */
int b4q_transaction(uint32_t genome, const uint32_t *steps, int n_steps, b4q_kind kind, const b4q_task *task, b4q_tx_result *r)
{
    uint32_t st = 0;
    int k, a5 = (kind == B4Q_KIND_A5);
    memset(r, 0, sizeof *r);
    g_stop = NULL; phase("P1");
    if (n_steps < 0 || n_steps > B4Q_MAX_STEPS || (kind == B4Q_KIND_ROOT && n_steps != 0)) { r->status = 3; r->reason = "a transaction has 0..28 set steps; the root has none"; strcpy(r->phase, "P1"); return -1; }
    b4q_emit("MARK transaction_begin");
    if (candidate_in(genome, a5, r, r->pre_event_hex, r->staged_hex, r->stream_hex, r->commit_hex) != 0) goto stopped;
    emitf("EV P2 commit=%s pre_event=%s", r->commit_hex, r->pre_event_hex);
    /* P3: the pre-init sample, then the init event */
    phase("P3");
    if (engine_op(B4Q_CTRL_PRE_SAMPLE, B4Q_ST_PRE_SAMPLED, &st, r, "STOP_P3: PRE_SAMPLE refused") != 0) goto stopped;
    r->in_live_pre = axi_rd(B4Q_IN_LIVE);
    if (read_slot(0, r) != 0) goto stopped;
    r->heartbeat_before = axi_rd(B4Q_HEARTBEAT);
    if (engine_op(B4Q_CTRL_INIT_REQ, B4Q_ST_INIT_DONE, &st, r, "STOP_P3: INIT_REQ refused") != 0) goto stopped;
    r->witness_after_init = axi_rd(B4Q_WITNESS);
    r->heartbeat_after = axi_rd(B4Q_HEARTBEAT);
    if (axi_rd(B4Q_IN_LIVE) != 0u) stop("STOP_P3: the inputs are not 0 after the init event");
    if (read_slot(1, r) != 0) goto stopped;
    if (g_stop) goto stopped;
    /* P4: the post-event readback */
    phase("P4");
    if (link3(r->post_event_hex) != 0) goto stopped;
    if (strcmp(r->post_event_hex, r->pre_event_hex) != 0) { stop("STOP_LINK3: the post-event readback is not the pre-event one (the event changed a frame): no step is applied"); goto stopped; }
    emitf("EV P4 post_event=%s %s", r->post_event_hex, "");
    /* P5: the set steps, exactly */
    phase("P5");
    for (k = 0; k < n_steps; k++) {
        if (axi_wr(B4Q_STEP_IN, steps[k] & 0x1FFFFFFu) != B4Q_RESP_OKAY) { stop("STOP_P5: the STEP_IN write answered SLVERR: the staged word is not this step; no STEP is launched"); goto stopped; }
        if (axi_rd(B4Q_STEP_IN) != (steps[k] & 0x1FFFFFFu)) { stop("STOP_P5: STEP_IN does not read back the staged step; no STEP is launched"); goto stopped; }
        if (engine_op(B4Q_CTRL_STEP, B4Q_ST_STEP_DONE, &st, r, "STOP_P5: STEP refused") != 0) goto stopped;
        if (read_slot(2 + k, r) != 0) goto stopped;
        r->steps_applied = k + 1;
    }
    r->status_final = axi_rd(B4Q_STATUS);
    if (((r->status_final >> B4Q_ST_STEP_INDEX_SHIFT) & B4Q_ST_STEP_INDEX_MASK) != (uint32_t)n_steps) { stop("STOP_P5: step_index is not the number of steps applied"); goto stopped; }
    /* P6: the observation is sealed by the host from the trace; this side's fitness over the full mask on the sampled values */
    phase("P6");
    if (task && task->n > 0 && kind != B4Q_KIND_ROOT) {
        int i, f = 0;
        for (i = 0; i < task->n; i++) {
            int s = task->step[i], e = task->elem[i];
            if (s < 1 || s > n_steps || e < 0 || e > 7) { stop("STOP_P6: a task cell lies outside the observation"); goto stopped; }
            if (((r->slot_q[1 + s] >> e) & 1u) == task->target[i]) f += task->weight[i];
        }
        r->fitness = f; r->has_fitness = 1; strncpy(r->task_digest, task->digest, 64); r->task_digest[64] = 0;
    }
    b4q_emit("MARK P6_sealed");
    if (kind == B4Q_KIND_INJECT) {
        /* the A5 injecting transaction (contract 5.6 J2): P7–P9 deliberately omitted; the inputs stay as they are */
        phase("P10");
        if (engine_op(B4Q_CTRL_CLOSE_INJECTION, B4Q_ST_INJECTION_OPEN, &st, r, "STOP_P10: CLOSE_INJECTION refused") != 0) goto faulted;
        r->status_final = st; r->status = 0; r->reason = "injection_open";
        b4q_emit("MARK transaction_end");
        return 0;
    }
    /* P7: the cleanup, recorded, not scored */
    phase("P7");
    if (engine_op(B4Q_CTRL_CLEANUP, B4Q_ST_CLEANUP_DONE, &st, r, "STOP_P7: CLEANUP refused") != 0) goto faulted;
    if (axi_rd(B4Q_IN_LIVE) != 0u) { stop("STOP_P7: the cleanup left inputs held"); goto faulted; }
    if (read_slot(2 + n_steps, r) != 0) goto faulted;
    /* P8: the base restored (genome 0 signed and written) and read back — the host's PCAP path, this side's DMAs */
    phase("P8");
    {
        char commit0[65], staged0[65], stream0[65];
        uint8_t d[32];
        uint32_t g0[P3_GENOME_WORDS];
        int i;
        g0[0] = 0u;
        p3_derive_frames(g0, g_frames);
        p3_frames_hash(P3_CFRAMES(g_frames), d);
        hex_of(d, commit0);
        stage_streams();
        if (link2(staged0, stream0) != 0 || strcmp(staged0, commit0) != 0) { stop("STOP_P8: the staged base is not the base"); goto faulted; }
        strcpy(r->base_staged_hex, staged0);
        if (write_envelopes() != 0) goto faulted;
        if (link3(r->base_readback_hex) != 0) goto faulted;
        if (strcmp(r->base_readback_hex, commit0) != 0) { stop("STOP_P8: the restored base's readback is not the derived base: no restore event is raised on it"); goto faulted; }
        for (i = 0; i < 8; i++) (void)i;
    }
    emitf("EV P8 base_readback=%s %s", r->base_readback_hex, "");
    /* P9: the base-state witness: the declared event on the restored base, sampled */
    phase("P9");
    if (engine_op(B4Q_CTRL_RESTORE_INIT, B4Q_ST_RESTORE_DONE, &st, r, "STOP_P9: RESTORE_INIT refused") != 0) goto faulted;
    r->witness_after_restore = axi_rd(B4Q_WITNESS);
    r->base_state = axi_rd(B4Q_BASE_STATE) & 0xFFu;
    /* P10: the close; idle read */
    phase("P10");
    if (engine_op(B4Q_CTRL_CLOSE, 32u, &st, r, "STOP_P10: CLOSE refused") != 0) goto faulted;
    st = axi_rd(B4Q_STATUS);
    r->status_final = st;
    if (!bit(st, B4Q_ST_IDLE)) { stop("STOP_P10: not idle after CLOSE"); goto faulted; }
    r->status = 0; r->reason = "closed";
    b4q_emit("MARK transaction_end");
    return 0;
stopped:
    r->status = (strcmp(g_phase, "P1") == 0 && r->commit_hex[0] == 0) ? 3 : 1;
    r->reason = g_stop ? g_stop : "stopped";
    strcpy(r->phase, g_phase);
    b4q_emit("MARK transaction_end");
    return -1;
faulted:
    r->status = 2;
    r->reason = g_stop ? g_stop : "faulted";
    strcpy(r->phase, g_phase);
    b4q_emit("MARK transaction_end");
    return -1;
}
