/* console.c — the board console primitives for the P3 standalone image.
 *
 * outbyte/inbyte drive UART1 (0xE0001000), the port U-Boot uses on this board (D1 spec T1).
 * U-Boot has already configured the UART (baud, mode) before `go`; this image inherits that
 * state and MUST NOT re-initialise it (docs/l5_design.md §3). So these primitives only poll
 * the channel-status register and move one byte through the FIFO — no control/mode write.
 *
 * This file lives under firmware/bsp/ on purpose: the firmware source audit
 * (tests/test_firmware_audit.py) globs firmware/*.c only, so the console's UART register
 * access is a HAL primitive outside the audited application surface — exactly as p3_app.c's
 * header comment states ("no UART register appears in this file").
 */
#include "xil_types.h"
#include "xil_io.h"

#define UART1_BASE     0xE0001000u
#define UART_SR        (UART1_BASE + 0x2Cu) /* channel status register */
#define UART_FIFO      (UART1_BASE + 0x30u) /* tx/rx FIFO */
#define UART_SR_RXEMPTY 0x00000002u
#define UART_SR_TXFULL  0x00000010u

void outbyte(char c);
char inbyte(void);
int console_rx_ready(void);
int console_rx_flush(void);

/* Non-blocking: is a byte waiting in the RX FIFO? The L6 audit pull waits for the host's
 * next AUDITGET/AUDITDONE with a BOUNDED number of these polls (p3_app.c P3_PULL_IDLE_POLLS)
 * so that a lost host frame can never leave the application waiting forever. Same
 * register, same discipline as inbyte(): a read of the status register, nothing written. */
int console_rx_ready(void)
{
    return (Xil_In32(UART_SR) & UART_SR_RXEMPTY) ? 0 : 1;
}

/* Discard whatever is waiting in the RX FIFO (at most one FIFO's worth plus what arrives
 * while draining, bounded). rec-v3: the application reads the console only inside a
 * transaction (the sign reply, the audit pull, the REC acknowledgement); a host line that
 * lands outside one — a second RECACK after the board had already moved on — would sit in
 * the 64-byte FIFO, overflow, and merge with the NEXT reply. So the application drains the
 * FIFO before it sends a SIGNREQ: anything there is stale by construction. Reads only. */
int console_rx_flush(void)
{
    int n = 0;
    while (n < 4096 && !(Xil_In32(UART_SR) & UART_SR_RXEMPTY)) {
        (void)Xil_In32(UART_FIFO);
        n++;
    }
    return n;
}

void outbyte(char c)
{
    while (Xil_In32(UART_SR) & UART_SR_TXFULL) {
        /* wait for room in the TX FIFO */
    }
    Xil_Out32(UART_FIFO, (u32)(u8)c);
}

char inbyte(void)
{
    while (Xil_In32(UART_SR) & UART_SR_RXEMPTY) {
        /* wait for a byte in the RX FIFO */
    }
    return (char)(Xil_In32(UART_FIFO) & 0xFFu);
}
