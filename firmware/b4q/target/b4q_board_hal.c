/* b4q_board_hal — the MMIO half of the HAL on the board: Xil_In32 / Xil_Out32 behind the pure allowlist (b4q_psmap.c), checked
 * BEFORE every access. A refused address is reported as SLVERR and NEVER issued: on this part an undecoded access is a data
 * abort (zynq-psmap P2), and the abort handler (b4q_board_main.c) ends the session by name. OKAY here means exactly "the
 * access completed without an abort" — the AXI response of a completed access is not observable from the A9 (an SLVERR is
 * the abort), so no other response is ever invented. The notary and event halves of the HAL are b4q_app.c's (the console). */
#include "b4q_hal.h"
#include "b4q_psmap.h"
#include "b4q_app.h"
#include "b4q_ring.h"
#include "xil_io.h"

static uint8_t kind_of(uint32_t addr)
{
    if (addr >= B4Q_PSMAP_AXI_BASE && addr < B4Q_PSMAP_AXI_BASE + B4Q_PSMAP_AXI_SIZE) return B4Q_RING_KIND_WIN;
    if (addr >= B4Q_PSMAP_DEVCFG_BASE && addr < B4Q_PSMAP_DEVCFG_BASE + 0x100u) return B4Q_RING_KIND_DEVC;
    return B4Q_RING_KIND_BUF;
}

static uint32_t addr_of(uint32_t addr) { return kind_of(addr) == B4Q_RING_KIND_WIN ? addr - B4Q_PSMAP_AXI_BASE : addr; }

uint32_t b4q_rd32(uint32_t addr, uint32_t *resp)
{
    uint32_t v;
    if (!b4q_psmap_readable(addr)) { *resp = B4Q_RESP_SLVERR; b4q_app_log_access(kind_of(addr), B4Q_RING_OP_RD, addr_of(addr), 0u, 1); return 0; }
    *resp = B4Q_RESP_OKAY;
    v = Xil_In32(addr);
    b4q_app_log_access(kind_of(addr), B4Q_RING_OP_RD, addr_of(addr), v, 0);     /* the evidence log: what this program read */
    return v;
}

uint32_t b4q_wr32(uint32_t addr, uint32_t value)
{
    if (b4q_app_terminal()) return B4Q_RESP_SLVERR;     /* the terminal END went out: no write is issued after it (R2) */
    if (!b4q_psmap_writable(addr)) { b4q_app_log_access(kind_of(addr), B4Q_RING_OP_WR, addr_of(addr), value, 1); return B4Q_RESP_SLVERR; }
    Xil_Out32(addr, value);
    b4q_app_log_access(kind_of(addr), B4Q_RING_OP_WR, addr_of(addr), value, 0);  /* completed without an abort */
    return B4Q_RESP_OKAY;
}
