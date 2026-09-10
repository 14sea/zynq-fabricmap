/* host stub of the global timer: a counter the harness advances */
#ifndef XTIME_L_H
#define XTIME_L_H
#include "xil_types.h"
typedef u64 XTime;
#define COUNTS_PER_SECOND 333333343u
void XTime_GetTime(XTime *t);
void XTime_SetTime(XTime t);
#endif
