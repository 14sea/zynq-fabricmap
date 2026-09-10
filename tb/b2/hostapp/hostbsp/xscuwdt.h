/* host stub of the SCU watchdog driver: the harness records the calls */
#ifndef XSCUWDT_H
#define XSCUWDT_H
#include "xil_types.h"
typedef struct { u32 BaseAddr; } XScuWdt_Config;
typedef struct { u32 IsReady; u32 BaseAddr; } XScuWdt;
#define XSCUWDT_CONTROL_PRESCALER_SHIFT 8
#define XSCUWDT_CONTROL_WD_MODE_MASK 0x8u
XScuWdt_Config *XScuWdt_LookupConfig(u16 DeviceId);
int XScuWdt_CfgInitialize(XScuWdt *w, XScuWdt_Config *cfg, u32 base);
void XScuWdt_SetControlReg(XScuWdt *w, u32 v);
void XScuWdt_LoadWdt(XScuWdt *w, u32 v);
void XScuWdt_Start(XScuWdt *w);
void XScuWdt_RestartWdt(XScuWdt *w);
#endif
