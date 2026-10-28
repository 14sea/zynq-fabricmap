/* b4q_app_host — the HOST harness of the board application: the same b4q_app.c / b4q_wire.c / b4q_psmap.c / b4q_tx.c /
 * b4q_derive.c / b4q_cmd.c sources, with the MMIO half of the HAL on stdin / stdout (the line protocol host/b4q_session.py
 * answers from the emulated backend) and the CONSOLE on file descriptors 3 (host -> application) and 4 (application -> host),
 * the platform as counters. host/b4q_console_session.py drives it: every byte the board would put on UART1 goes through fd 4
 * and is parsed by the Python twin. Not a board image; nothing here is on-target evidence. */
#include "b4q_app.h"
#include "b4q_console.h"
#include "b4q_platform.h"
#include "b4q_hal.h"
#include "b4q_psmap.h"
#include "b4q_ring.h"

#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* the console's descriptors: 3 (in) / 4 (out) unless the driver names others through B4Q_CON_IN / B4Q_CON_OUT (it keeps them
 * open across the exec with pass_fds; nothing is re-numbered inside the child) */
static int CON_IN = 3, CON_OUT = 4;

static char g_line[4096];
static char g_tx[16384];
static size_t g_tx_n;
static unsigned long g_kicks;
static int g_armed;

static const char *reply(void)
{
    if (!fgets(g_line, sizeof g_line, stdin)) { fprintf(stderr, "transport closed\n"); exit(3); }
    g_line[strcspn(g_line, "\r\n")] = 0;
    return g_line;
}

static uint8_t kind_of(uint32_t addr)
{
    if (addr >= B4Q_PSMAP_AXI_BASE && addr < B4Q_PSMAP_AXI_BASE + B4Q_PSMAP_AXI_SIZE) return B4Q_RING_KIND_WIN;
    if (addr >= B4Q_PSMAP_DEVCFG_BASE && addr < B4Q_PSMAP_DEVCFG_BASE + 0x100u) return B4Q_RING_KIND_DEVC;
    return B4Q_RING_KIND_BUF;
}

static uint32_t addr_of(uint32_t addr) { return kind_of(addr) == B4Q_RING_KIND_WIN ? addr - B4Q_PSMAP_AXI_BASE : addr; }

uint32_t b4q_rd32(uint32_t addr, uint32_t *resp)
{
    unsigned long long d = 0, r = 0;
    if (!b4q_psmap_readable(addr)) { *resp = B4Q_RESP_SLVERR; b4q_app_log_access(kind_of(addr), B4Q_RING_OP_RD, addr_of(addr), 0u, 1); return 0; }   /* the HAL's allowlist: never issued (the board's rule) */
    printf("R %08x\n", (unsigned)addr); fflush(stdout);
    if (sscanf(reply(), "%llx %llu", &d, &r) != 2) { fprintf(stderr, "bad read reply: %s\n", g_line); exit(3); }
    *resp = (uint32_t)r;
    b4q_app_log_access(kind_of(addr), B4Q_RING_OP_RD, addr_of(addr), (uint32_t)d, r != 0);
    return (uint32_t)d;
}

uint32_t b4q_wr32(uint32_t addr, uint32_t value)
{
    unsigned long long r = 0;
    if (b4q_app_terminal()) return B4Q_RESP_SLVERR;     /* the terminal END went out: no write is issued after it (R2) */
    if (!b4q_psmap_writable(addr)) { b4q_app_log_access(kind_of(addr), B4Q_RING_OP_WR, addr_of(addr), value, 1); return B4Q_RESP_SLVERR; }
    printf("W %08x %08x\n", (unsigned)addr, (unsigned)value); fflush(stdout);
    if (sscanf(reply(), "%llu", &r) != 1) { fprintf(stderr, "bad write reply: %s\n", g_line); exit(3); }
    b4q_app_log_access(kind_of(addr), B4Q_RING_OP_WR, addr_of(addr), value, r != 0);
    return (uint32_t)r;
}

static void con_flush_tx(void)
{
    size_t off = 0;
    while (off < g_tx_n) {
        ssize_t w = write(CON_OUT, g_tx + off, g_tx_n - off);
        if (w <= 0) { fprintf(stderr, "console closed\n"); exit(3); }
        off += (size_t)w;
    }
    g_tx_n = 0;
}

void b4q_con_putc(char c)
{
    g_tx[g_tx_n++] = c;
    if (c == '\n' || g_tx_n == sizeof g_tx) con_flush_tx();
}

int b4q_con_rx_ready(void)
{
    struct pollfd p; p.fd = CON_IN; p.events = POLLIN; p.revents = 0;
    return poll(&p, 1, 0) > 0 && (p.revents & (POLLIN | POLLHUP));
}

char b4q_con_getc(void)
{
    char c;
    if (read(CON_IN, &c, 1) != 1) { fprintf(stderr, "console closed\n"); exit(3); }
    return c;
}

int b4q_con_rx_flush(void)
{
    int n = 0;
    while (n < 4096 && b4q_con_rx_ready()) { (void)b4q_con_getc(); n++; }
    return n;
}

int b4q_plat_watchdog_start(void) { g_armed = 1; return getenv("B4Q_APP_HOST_WDT_FAIL") ? -1 : 0; }

static uint8_t *g_ring;
static uint32_t g_tick;
uint8_t *b4q_plat_ring_base(uint32_t *capacity)
{
    const char *e = getenv("B4Q_APP_HOST_RING_BYTES");      /* a bench knob: a small log to reach the overflow stop */
    uint32_t cap = e ? (uint32_t)strtoul(e, NULL, 10) : 16u * 1024u * 1024u;
    if (!g_ring) g_ring = (uint8_t *)malloc(cap);
    *capacity = g_ring ? cap : 0u;
    return g_ring;
}
uint32_t b4q_plat_tick(void) { return ++g_tick; }
void b4q_plat_kick(void) { if (g_armed) g_kicks++; }
void b4q_plat_halt(void)
{
    con_flush_tx();
    printf("HALT kicks=%lu\n", g_kicks); fflush(stdout);
    exit(0);
}

int main(void)
{
    const char *e;
    if ((e = getenv("B4Q_CON_IN")) != NULL) CON_IN = atoi(e);
    if ((e = getenv("B4Q_CON_OUT")) != NULL) CON_OUT = atoi(e);
    b4q_app_run();
    b4q_plat_halt();
    return 0;
}
