/* bspconfig.h — hand-written for the P3 standalone image (classic, non-SDT flow).
 * Equivalent of what the Vitis BSP generator's cmake would template from bspconfig.h.in
 * for a Zynq-7000 cortex-a9 target with the UARTPS console. Only the Zynq path is taken;
 * no Versal/ZynqMP/MicroBlaze machinery is enabled. */
#ifndef BSPCONFIG_H
#define BSPCONFIG_H

#include "xmem_config.h"

#define PLATFORM_ZYNQ
#define XPAR_CPU_ID 0

/* console is the PS UART (UART1); outbyte/inbyte are provided by firmware/bsp/src/console.c */
#define XPAR_STDIN_IS_UARTPS
#define STDIN_BASEADDRESS  0xE0001000U
#define STDOUT_BASEADDRESS 0xE0001000U

#endif /* BSPCONFIG_H */
