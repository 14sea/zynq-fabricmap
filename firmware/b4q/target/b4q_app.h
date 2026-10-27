/* b4q_app — the board application's session as a PURE unit over the console (b4q_console.h), the platform (b4q_platform.h)
 * and the injected transport (b4q_hal.h): the identity page, the IDENT line, the host's commands (TX / QUIT) answered with the
 * executing side's RESULT, the console notary (SIGNREQ / SIGNREPLY) behind b4q_sign, the events behind b4q_emit, the bounded
 * waits with heartbeats, the named END. The same source runs on the host (target/b4q_app_host.c) against the emulated
 * backend and the Python console host (host/b4q_console_session.py), where its bytes and its sequence are tested; on the
 * board it is linked under target/b4q_board_main.c. It performs no MMIO itself: every access is b4q_tx.c's through the HAL.
 *
 * Fail-closed: a page that does not parse, a watchdog that cannot be armed, a refused opening, a framing failure the bound
 * exhausts, a host that falls silent — each ends the session by name (END STOPPED / PROTOCOL) and nothing further is
 * attempted; a stop inside a transaction is the executing side's (its admission invariant) and is reported in the RESULT.
 * The bounds are COUNTS of console polls (never a clock the application measures): B4Q_APP_IDLE_POLLS for the next host
 * command, B4Q_APP_REPLY_POLLS for a SIGNREPLY (B4Q_APP_SIGN_ATTEMPTS re-requests), a heartbeat every B4Q_APP_HB_EVERY polls. */
#ifndef B4Q_APP_H
#define B4Q_APP_H

#include <stddef.h>
#include <stdint.h>

#ifndef B4Q_APP_IDLE_POLLS
#define B4Q_APP_IDLE_POLLS 50000000u      /* ~ tens of seconds of UART status polls on the board (a count, not a measured time) */
#endif
#ifndef B4Q_APP_REPLY_POLLS
#define B4Q_APP_REPLY_POLLS 50000000u
#endif
#ifndef B4Q_APP_HB_EVERY
#define B4Q_APP_HB_EVERY 5000000u
#endif
#define B4Q_APP_SIGN_ATTEMPTS 3
#define B4Q_APP_PROTOCOL "b4q-v1"
#define B4Q_APP_MAX_NACKS 8                /* malformed host lines tolerated per wait before the session ends PROTOCOL */

typedef enum { B4Q_END_NONE = 0, B4Q_END_COMPLETED, B4Q_END_STOPPED, B4Q_END_PROTOCOL, B4Q_END_ABORT } b4q_end_kind;

typedef struct {
    b4q_end_kind end;
    const char *reason;
    uint32_t lines, hb, nacks, sign_requests, sign_replies, kicks_requested, transactions;
    int page_ok, watchdog_armed, opened;
} b4q_app_summary;

/* the whole session: returns when the END line has been emitted (the caller halts) */
void b4q_app_run(void);
/* from an exception handler (the board): emit END ABORT with the fault's name, address and status, then return (the caller spins) */
void b4q_app_abort(const char *kind, uint32_t addr, uint32_t status);
const b4q_app_summary *b4q_app_summary_get(void);

#endif /* B4Q_APP_H */
