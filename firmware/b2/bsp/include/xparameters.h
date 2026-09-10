/* xparameters.h — hand-written for the P3 standalone image (classic, non-SDT flow).
 *
 * PROVENANCE OF EVERY BOARD-SPECIFIC VALUE (docs/l5_findings.md §"build constants"):
 *   - Fixed Zynq-7000 addresses (UART, SCU, DDR base) come from Xilinx's own
 *     arm/cortexa9/xparameters_ps.h, included below — architectural, not a choice.
 *   - Console UART = UART1 @ 0xE0001000: pinned by the D1 spec (docs/d1_standalone_spec.md
 *     T1 = "the console (UART1)") and matched by every board run's relay. Defined in
 *     bspconfig.h (STDIN/STDOUT_BASEADDRESS), which gates out the stock outbyte/inbyte stubs.
 *   - ARM PLL = 1333.33 MHz is board-confirmed: ARM_PLL_CTRL = 0x00028008 on 17A6
 *     (evidence/l2_17A6_2026-08-30-03/L2_0_fclk.json), FDIV = 40, x 33.333 MHz.
 *   - CPU_6x4x = 666.67 MHz assumes the standard 6:2:1 ratio: CPU_CLK_CTRL (0xF8000120)
 *     was NOT captured in the board evidence, so the divisor is assumed, not confirmed.
 *     This is the one un-confirmed constant — flagged for the reviewer. It affects only the
 *     watchdog period computation, not the interlock.
 *   - DDR high = 0x1FFFFFFF (512 MiB): the inherited U-Boot map psmap/l3_runner staged
 *     into reaches 0x1080_0000+8 MiB (docs/l5_design.md §2), so the part carries >=512 MiB.
 */
#ifndef XPARAMETERS_H
#define XPARAMETERS_H

/* CPU clock must be defined BEFORE xparameters_ps.h so its CORE_CLOCK alias resolves. */
#define XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ      666666687U   /* 6:2:1 assumed (see above) */

#include "xparameters_ps.h"   /* Xilinx: XPS_* fixed PS addresses + canonical PS defs */

/* ---- DDR (inherited from U-Boot; not re-initialised by this image) ----------------- */
#define XPAR_PS7_DDR_0_S_AXI_BASEADDR            0x00100000U
#define XPAR_PS7_DDR_0_S_AXI_HIGHADDR            0x1FFFFFFFU

/* ---- SCU private watchdog (the only driver instance this image links) --------------- */
#define XPAR_XSCUWDT_NUM_INSTANCES               1U
#define XPAR_SCUWDT_0_DEVICE_ID                  0U
#define XPAR_SCUWDT_0_BASEADDR                   (XPS_SCU_PERIPH_BASE + 0x00000620U) /* 0xF8F00620 */
#define XPAR_PS7_SCUWDT_0_DEVICE_ID              0U
#define XPAR_PS7_SCUWDT_0_BASEADDR               (XPS_SCU_PERIPH_BASE + 0x00000620U)

#endif /* XPARAMETERS_H */
