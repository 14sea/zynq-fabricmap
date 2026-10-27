/* b4q_psmap — the board HAL's address allowlist as a PURE unit: every PS address the executing side may read or write —
 * the carrier window's registers (the table of record, b4q_regmap.h), the DevC's six registers, the three DDR buffers
 * (read / write) and the identity page (read only), the SLCR IDCODE (read only). Checked BEFORE every access on the board
 * (an undecoded or refused access there is a data abort — zynq-psmap P2; the allowlist is the HAL's, never trusted from a
 * call site), and held to the A7 regions of host/b4q_a7.py by tests/test_b4q_app.py. The key window is absent by construction. */
#ifndef B4Q_PSMAP_H
#define B4Q_PSMAP_H

#include <stdint.h>

#define B4Q_PSMAP_AXI_BASE 0x43C00000u
#define B4Q_PSMAP_AXI_SIZE 0x00010000u
#define B4Q_PSMAP_DEVCFG_BASE 0xF8007000u
#define B4Q_PSMAP_SLCR_PSS_IDCODE 0xF8000530u
#define B4Q_PSMAP_CMD_BUF 0x10200000u
#define B4Q_PSMAP_DST_BUF 0x10300000u
#define B4Q_PSMAP_WR_BUF 0x10400000u
#define B4Q_PSMAP_PAGE_ADDR 0x10440000u

int b4q_psmap_readable(uint32_t addr);
int b4q_psmap_writable(uint32_t addr);

#endif /* B4Q_PSMAP_H */
