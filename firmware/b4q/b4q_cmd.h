/* b4q_cmd — the textual command and result forms the executing side exchanges with its host, as ONE pure unit shared by the
 * host driver (b4q_host_main.c: on stdin / stdout) and the board application (target/b4q_app.c: as the payload of a framed
 * console line), so that the board parses exactly what the host-only path parsed and reports exactly what it reported:
 *
 *   "TX <kind> <genome_hex8> <n> <step_hex ...> [TASK <digest> <m> <step elem target weight> ...]"   kind: normal | root | inject | a5
 *   the RESULT JSON of an opening and of a transaction (the field names host/b4q_session.py reads)
 * No MMIO, no console, no board dependency: compiled on the host by the tests and for cortex-a9 by the image build. */
#ifndef B4Q_CMD_H
#define B4Q_CMD_H

#include <stddef.h>
#include <stdint.h>
#include "b4q_tx.h"

typedef struct {
    uint32_t genome;
    uint32_t steps[B4Q_MAX_STEPS];
    int n_steps;
    b4q_kind kind;
    b4q_task task;              /* task.n == 0: no task */
} b4q_tx_command;

/* 0 parsed; -1 malformed (nothing is run on a malformed command) */
int b4q_parse_tx(const char *cmd, b4q_tx_command *out);
/* the JSON objects (compact, the host-only driver's exact field order); the length written, or 0 when `max` is too small */
size_t b4q_open_json(const b4q_open_result *o, char *out, size_t max);
size_t b4q_tx_json(const b4q_tx_result *r, char *out, size_t max);

#endif /* B4Q_CMD_H */
