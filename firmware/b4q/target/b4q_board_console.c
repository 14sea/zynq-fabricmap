/* b4q_board_console — the application's console primitives (b4q_console.h) on the board, over B1's UART1 glue
 * (bsp/src/console.c, byte for byte: outbyte / inbyte / console_rx_ready / console_rx_flush — status polls and the FIFO of
 * the port U-Boot configured; nothing is re-initialised). The one UART-touching unit stays the BSP's; this file names no
 * register. */
#include "b4q_console.h"

extern void outbyte(char c);
extern char inbyte(void);
extern int console_rx_ready(void);
extern int console_rx_flush(void);

void b4q_con_putc(char c) { outbyte(c); }
int b4q_con_rx_ready(void) { return console_rx_ready(); }
char b4q_con_getc(void) { return inbyte(); }
int b4q_con_rx_flush(void) { return console_rx_flush(); }
