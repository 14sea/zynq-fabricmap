/* b4q_tx — the B4Q executing side: the session opening and the one-candidate transaction of docs/b4_observation_contract.md
 * section 5 (P1–P10, the A5 injection protocol of 5.6 J2 / J3) on the B4 carrier v2 register map (b4q_regmap.h, generated
 * from the table of record) through the injected transport (b4q_hal.h). What it is:
 *
 *   * the executing-side PRODUCER of the raw facts the host's record layer (host/b4carrier_records.py) turns into O / F / X:
 *     every sample it reads it reads from the carrier's slots (SLOT_READ / SLOT_IN_READ), every completion it waits for it
 *     waits for in STATUS / FAULT (never in a bus acknowledgement: an accepted CTRL write the engine refuses is a FAULT read
 *     later), every digest it reports it computed from words it read back (link 2 from DDR, link 3 from the PCAP readback);
 *   * the four legal DMA transactions of the archived PCAP path (write envelope, read command, read frame, cleanup) and
 *     nothing else; the derive / stream / readback arithmetic is b4q_derive.c (DERIVED from the instrument's);
 *   * fail-closed: a refusal, a fault, a parse failure or a digest disagreement stops the transaction at the phase reached
 *     and reports it; nothing is retried, filled in or continued.
 * What it is NOT: the record writer (the host builds the records from the register trace and holds this side's digests
 * and fitness to them), the notary (b4q_sign is the host's), a board image (no BSP, no console framing here). */
#ifndef B4Q_TX_H
#define B4Q_TX_H

#include <stdint.h>
#include "b4q_derive.h"

#define B4Q_MAX_STEPS 28          /* slots 2 .. 29 (the engine refuses at slot_count >= 30) */
#define B4Q_MAX_MASK 256
#define B4Q_POLL_LIMIT 200000u    /* STATUS polls before a wait is given up (a stop, never a retry) */

typedef enum { B4Q_KIND_NORMAL = 0, B4Q_KIND_ROOT = 1, B4Q_KIND_INJECT = 2, B4Q_KIND_A5 = 3 } b4q_kind;

typedef struct {
    int n;
    uint8_t step[B4Q_MAX_MASK];     /* 1-based step index into the acquired grid (0 = the init step) */
    uint8_t elem[B4Q_MAX_MASK];     /* 0..7 */
    uint8_t target[B4Q_MAX_MASK];   /* 0 / 1 */
    uint16_t weight[B4Q_MAX_MASK];
    char digest[65];
} b4q_task;

typedef struct {
    /* the outcome */
    int status;                 /* 0 complete and closed; 1 stopped in P1..P5 (O invalid, no X); 2 faulted after P6 (O sealed, X faulted);
                                   3 refused before anything (no derivation staged); 4 a wait ran out (a stop) */
    char phase[5];              /* the phase reached when it stopped, "P10" when closed */
    const char *reason;         /* a short named reason on a stop */
    uint32_t fault_code;        /* the FAULT register as read at the stop, 0 otherwise */
    /* the digests this side computed (hex, 64) */
    char commit_hex[65];        /* the derived frames' FAR-ordered hash: what the notary signed */
    char staged_hex[65];        /* link 2: the frames re-read from DDR, hashed in the same domain */
    char stream_hex[65];        /* link 2: the two staged streams, hashed as words */
    char pre_event_hex[65];     /* link 3 after the candidate's write (P2) */
    char post_event_hex[65];    /* link 3 after the init event (P4) */
    char base_staged_hex[65];   /* P8: the base's link-2 digest */
    char base_readback_hex[65]; /* P8: link 3 of the restored base */
    /* the carrier's samples as read (the slots), the applied inputs, the witnesses */
    int n_slots;
    uint32_t slot_q[32];
    uint32_t slot_in[32];
    uint32_t in_live_pre;       /* IN_LIVE at the pre-init sample (the held inputs under A5) */
    uint32_t witness_after_init, witness_after_restore, heartbeat_before, heartbeat_after;
    uint32_t base_state;
    uint32_t status_final;
    int steps_applied;
    /* the fitness over the full mask on the sampled values (contract 3.4 (i)); only when complete and a task was given */
    int has_fitness;
    int fitness;
    char task_digest[65];
    uint64_t nonce_before, nonce_after;
} b4q_tx_result;

typedef struct {
    int status;                 /* 0 opened; 1 refused (identity); 4 a wait ran out */
    const char *reason;
    uint32_t idcode, variant, timing, witness, status_word, heartbeat;
    uint64_t nonce;
    char startup_readback_hex[65];   /* link 3 of the loaded image's write set, taken before anything is signed */
} b4q_open_result;

int b4q_session_open(b4q_open_result *o);
int b4q_transaction(uint32_t genome, const uint32_t *steps, int n_steps, b4q_kind kind, const b4q_task *task, b4q_tx_result *r);

#endif /* B4Q_TX_H */
