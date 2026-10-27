/* b4q_console — the board application's console primitives (the HAL of the wire): on the board firmware/b4q/bsp/src/console.c
 * (UART1 as U-Boot left it: status-register polls and the FIFO, nothing configured); on the host target/b4q_app_host.c (a pipe).
 * Reads are bounded by the CALLER's poll counts (b4q_app.c), never by these primitives. */
#ifndef B4Q_CONSOLE_H
#define B4Q_CONSOLE_H

void b4q_con_putc(char c);
int b4q_con_rx_ready(void);     /* non-blocking: a byte is waiting */
char b4q_con_getc(void);        /* called only after rx_ready said so */
int b4q_con_rx_flush(void);     /* discard what is waiting (bounded); the count discarded */

#endif /* B4Q_CONSOLE_H */
