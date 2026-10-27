/* b4q_board_hal — the MMIO half of the HAL on the board: Xil_In32 / Xil_Out32 behind the pure allowlist (b4q_psmap.c), checked
 * BEFORE every access. A refused address is reported as SLVERR and NEVER issued: on this part an undecoded access is a data
 * abort (zynq-psmap P2), and the abort handler (b4q_board_main.c) ends the session by name. OKAY here means exactly "the
 * access completed without an abort" — the AXI response of a completed access is not observable from the A9 (an SLVERR is
 * the abort), so no other response is ever invented. The notary and event halves of the HAL are b4q_app.c's (the console). */
#include "b4q_hal.h"
#include "b4q_psmap.h"
#include "xil_io.h"

uint32_t b4q_rd32(uint32_t addr, uint32_t *resp)
{
    if (!b4q_psmap_readable(addr)) { *resp = B4Q_RESP_SLVERR; return 0; }
    *resp = B4Q_RESP_OKAY;
    return Xil_In32(addr);
}

uint32_t b4q_wr32(uint32_t addr, uint32_t value)
{
    if (!b4q_psmap_writable(addr)) return B4Q_RESP_SLVERR;
    Xil_Out32(addr, value);
    return B4Q_RESP_OKAY;
}
