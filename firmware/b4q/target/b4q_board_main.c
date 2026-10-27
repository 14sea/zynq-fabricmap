/* b4q_board_main — the B4Q standalone application's platform layer: the MMU attributes of the DDR buffers, the exception
 * handlers (error-to-stop), the private watchdog, the halt. Everything else is the pure units (b4q_app.c and what it calls).
 *
 * STANDING: COMPILED, NOT BOARD-RUN. Cross-compiled for cortex-a9 by firmware/b4q/bsp/build.sh with the instrument's pinned
 * xPack toolchain against the same hand-assembled standalone BSP as B1's image (firmware/b1/bsp, read-only precedent); its
 * build evidence is host/b4q_build_evidence.py's. It has never been loaded on a board: the first board contact is the F8B3
 * bring-up under its own execution plan and ruling (docs/b4q_plan.md §7 / §8). Nothing here is on-target evidence.
 *
 * Memory discipline (B1's, docs/l3_findings.md): the DDR the DMA and the readback use — the three buffers and the identity
 * page — is mapped strongly-ordered and NON-CACHEABLE before it is touched, so no per-operation cache maintenance exists to be
 * missed; the image's own code / data stay cacheable. The console is UART1 as U-Boot left it (bsp/src/console.c: status polls
 * and the FIFO only). The watchdog: the A9 private SCU watchdog in reset mode, B1's pinned load / prescaler (30.0 s at the
 * PERIPHCLK board-confirmed on 17A6, 2026-09-01; F8B3's PERIPHCLK is NOT confirmed — a bring-up measurement), armed only when
 * the identity page asks, kicked only after a framed line went out (b4q_app.c). A timeout resets the PS: the host sees the
 * U-Boot banner — after an END line that is the expected epilogue, before one it is the CRASH the collector names. */
#include "b4q_app.h"
#include "b4q_platform.h"
#include "b4q_psmap.h"

#include "xil_exception.h"
#include "xil_io.h"
#include "xil_mmu.h"
#include "xparameters.h"
#include "xpseudo_asm.h"
#include "xreg_cortexa9.h"
#include "xscuwdt.h"
#include "xtime_l.h"

#define B4Q_NONCACHEABLE 0x14de2u    /* Xil_SetTlbAttributes: strongly-ordered, non-cacheable (B1's P3_NONCACHEABLE) */
#define B4Q_WDT_LOAD 1250000035u     /* B1's D-s1 pin: 30.0 s at PERIPHCLK / 8 = 333 333 343 / 8 Hz (17A6-confirmed) */
#define B4Q_WDT_PRESCALER 7u

static XScuWdt g_wdt;
static int g_wdt_started;

int b4q_plat_watchdog_start(void)
{
    XScuWdt_Config *cfg = XScuWdt_LookupConfig(XPAR_PS7_SCUWDT_0_DEVICE_ID);
    if (cfg == NULL || XScuWdt_CfgInitialize(&g_wdt, cfg, cfg->BaseAddr) != XST_SUCCESS) return -1;
    XScuWdt_SetControlReg(&g_wdt, (B4Q_WDT_PRESCALER << XSCUWDT_CONTROL_PRESCALER_SHIFT) | XSCUWDT_CONTROL_WD_MODE_MASK);
    XScuWdt_LoadWdt(&g_wdt, B4Q_WDT_LOAD);
    XScuWdt_Start(&g_wdt);
    g_wdt_started = 1;               /* the kick is live from here and only from here (B1's review of 2026-09-01) */
    return 0;
}

void b4q_plat_kick(void)
{
    if (g_wdt_started) XScuWdt_RestartWdt(&g_wdt);
}

void b4q_plat_halt(void)
{
    for (;;) { }                     /* the session ended by name; an armed watchdog resets the PS within its period */
}

static void on_data_abort(void *data)
{
    uint32_t dfsr = mfcp(XREG_CP15_DATA_FAULT_STATUS), dfar = mfcp(XREG_CP15_DATA_FAULT_ADDRESS);
    (void)data;
    b4q_app_abort("data_abort", dfar, dfsr);
    b4q_plat_halt();
}

static void on_prefetch_abort(void *data)
{
    uint32_t ifsr = mfcp(XREG_CP15_INST_FAULT_STATUS), ifar = mfcp(XREG_CP15_INST_FAULT_ADDRESS);
    (void)data;
    b4q_app_abort("prefetch_abort", ifar, ifsr);
    b4q_plat_halt();
}

static void on_undefined(void *data)
{
    (void)data;
    b4q_app_abort("undefined_instruction", 0u, 0u);
    b4q_plat_halt();
}

int main(void)
{
    Xil_SetTlbAttributes(B4Q_PSMAP_CMD_BUF, B4Q_NONCACHEABLE);
    Xil_SetTlbAttributes(B4Q_PSMAP_DST_BUF, B4Q_NONCACHEABLE);
    Xil_SetTlbAttributes(B4Q_PSMAP_WR_BUF, B4Q_NONCACHEABLE);
    Xil_SetTlbAttributes(B4Q_PSMAP_PAGE_ADDR, B4Q_NONCACHEABLE);
    XTime_SetTime(0u);
    Xil_ExceptionInit();
    Xil_ExceptionRegisterHandler(XIL_EXCEPTION_ID_DATA_ABORT_INT, on_data_abort, NULL);
    Xil_ExceptionRegisterHandler(XIL_EXCEPTION_ID_PREFETCH_ABORT_INT, on_prefetch_abort, NULL);
    Xil_ExceptionRegisterHandler(XIL_EXCEPTION_ID_UNDEFINED_INT, on_undefined, NULL);
    b4q_app_run();
    b4q_plat_halt();
    return 0;
}
