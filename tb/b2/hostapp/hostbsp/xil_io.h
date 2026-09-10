/* host stub: every Xil_In32/Xil_Out32 goes to the harness's fake memory map */
#ifndef XIL_IO_H
#define XIL_IO_H
#include "xil_types.h"
u32 Xil_In32(u32 addr);
void Xil_Out32(u32 addr, u32 value);
#endif
