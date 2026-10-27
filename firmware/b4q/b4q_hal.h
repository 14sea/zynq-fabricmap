/* b4q_hal — the INJECTED transport of the B4Q executing side: everything the transaction logic (b4q_tx.c) does to the
 * outside world goes through these five calls and nothing else, so the same logic runs on the host against an emulated
 * backend (b4q_host_main.c: a line protocol on stdin / stdout to host/b4q_backend.py) and, at a later stage, on the board
 * against Xil_In32 / Xil_Out32 and the console notary. The MMIO accesses the logic makes are therefore OBSERVABLE from
 * outside (the A7 allowlist check compares them to the RTL decode); the key window is never touched by this side. */
#ifndef B4Q_HAL_H
#define B4Q_HAL_H

#include <stddef.h>
#include <stdint.h>

#define B4Q_RESP_OKAY 0u
#define B4Q_RESP_SLVERR 2u

/* a 32-bit read of an absolute PS address; the response code (OKAY / SLVERR) is returned through *resp (on the board an
 * SLVERR read is a data abort, zynq-psmap P2: the allowlist is checked BEFORE the access, never trusted from the call site) */
uint32_t b4q_rd32(uint32_t addr, uint32_t *resp);
/* a 32-bit write; returns the response code */
uint32_t b4q_wr32(uint32_t addr, uint32_t value);
/* link 1: the notary signs the candidate `genome_hex` (8 hex chars) against the PL's current nonce (16 hex chars);
 * returns 0 and the 24 staging words (20 payload + 4 tag) in the PL's order, or -1 when the notary refused */
int b4q_sign(const char *genome_hex, const char *nonce_hex, uint32_t words[24]);
/* an event line for the host's log (a mark, a phase result, a digest); informational, never evidence by itself */
void b4q_emit(const char *line);

#endif /* B4Q_HAL_H */
