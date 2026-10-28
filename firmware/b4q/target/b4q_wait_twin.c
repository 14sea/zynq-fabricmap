/* b4q_wait_twin — the application's receive budget under injected console fixtures (tests/test_b4q_app.py::Bounds; after the
 * owner's wait_probe.c of 2026-10-28): the ORIGINAL b4q_app.c is included unchanged; only the console, the platform and the
 * MMIO are fixtures, and every readiness poll is counted. Modes (argv[1]):
 *   0  a silent peer                       3  a flood of malformed lines (bad CRC)
 *   1  a flood of stale SIGNREPLYs          4  the command wait of the main loop under a flood of well-formed non-command frames
 *   2  one endless overlong line             5  the idle wait under a silent host
 *   6  a flood of well-formed fresh TX frames during a sign wait (another type: charged, never a reply)
 * Prints "ret=<r> polls=<n> requests=<k> frames=<f> hb=<h>"; the budget is the build's (B4Q_APP_REPLY_POLLS / IDLE_POLLS). The
 * fixture itself caps at 50 x the budget so that a missing bound ends as OVER_BUDGET (exit 77), never as a hang. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "b4q_app.c"

static unsigned polls_seen, requests, frames;
static int mode, enabled;
static char rx[2048], tx[16384];
static size_t rn, rp, tn;
static const unsigned CAP = 50u * (B4Q_APP_REPLY_POLLS > B4Q_APP_IDLE_POLLS ? B4Q_APP_REPLY_POLLS : B4Q_APP_IDLE_POLLS);

void b4q_con_putc(char c)
{
    if (tn + 1 < sizeof tx) tx[tn++] = c;
    if (c == '\n') { tx[tn] = 0; if (strstr(tx, "B4Q1 SIGNREQ ") == tx) { requests++; enabled = 1; } tn = 0; }
}

int b4q_con_rx_ready(void)
{
    if (++polls_seen > CAP) { printf("OVER_BUDGET mode=%d polls=%u requests=%u frames=%u\n", mode, polls_seen, requests, frames); exit(77); }
    return mode != 0 && mode != 5 && (mode == 4 || enabled);
}

char b4q_con_getc(void)
{
    static uint32_t hseq;
    if (mode == 2) return 'X';
    if (rp == rn) {
        if (mode == 3) { rn = (size_t)snprintf(rx, sizeof rx, "B4Q1 SIGNREPLY %lu %s T0s= 00000000\n", (unsigned long)++hseq, S.token); }
        else if (mode == 6) { const char *p = "TX root 00000000 0"; frames++; rn = b4q_wire_frame("TX", ++hseq, S.token, (const uint8_t *)p, strlen(p), rx, sizeof rx); }
        else {
            const char *p = "OK 999999 00000000";       /* another request's reply (mode 1) / a stale frame for the idle wait (mode 4) */
            frames++;
            rn = b4q_wire_frame("SIGNREPLY", ++hseq, S.token, (const uint8_t *)p, strlen(p), rx, sizeof rx);
        }
        rp = 0;
    }
    return rx[rp++];
}

int b4q_con_rx_flush(void) { enabled = 0; rp = rn = 0; return 0; }
int b4q_plat_watchdog_start(void) { return 0; }
void b4q_plat_kick(void) { }
void b4q_plat_halt(void) { exit(99); }
uint32_t b4q_rd32(uint32_t a, uint32_t *resp) { (void)a; *resp = B4Q_RESP_SLVERR; return 0; }
uint32_t b4q_wr32(uint32_t a, uint32_t v) { (void)a; (void)v; return B4Q_RESP_SLVERR; }

int main(int argc, char **argv)
{
    uint32_t words[24];
    int ret;
    mode = argc > 1 ? atoi(argv[1]) : 0;
    memset(&S, 0, sizeof S);
    strcpy(S.token, B4Q_WIRE_ZERO_TOKEN);
    if (mode == 4 || mode == 5) {
        b4q_wire_frame_t f;
        b4q_budget b = {B4Q_APP_IDLE_POLLS, 0};
        ret = wait_command(&b, &f);
        printf("ret=%d polls=%u requests=%u frames=%u hb=%lu spent=%lu\n", ret, polls_seen, requests, frames, (unsigned long)S.sum.hb, (unsigned long)b.spent);
        return 0;
    }
    ret = b4q_sign("00000000", "0000000000000000", words);
    printf("ret=%d polls=%u requests=%u frames=%u hb=%lu\n", ret, polls_seen, requests, frames, (unsigned long)S.sum.hb);
    return 0;
}
