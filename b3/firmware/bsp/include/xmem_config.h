/* xmem_config.h — minimal. In the 2025.2 cmake flow this file carries OCM/TCM/reserved
 * region defines; on Zynq-7000 the MMU table (translation_table.S) sizes DDR from
 * XPAR_PS7_DDR_0_S_AXI_* in xparameters.h, so no memory-region macro is required here.
 * It exists because bspconfig.h and translation_table.S both #include it. */
#ifndef XMEM_CONFIG_H
#define XMEM_CONFIG_H
#endif /* XMEM_CONFIG_H */
