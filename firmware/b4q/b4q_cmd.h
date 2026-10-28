/* b4q_cmd — the textual command and result forms the executing side exchanges with its host, as ONE pure unit shared by the
 * host driver (b4q_host_main.c: on stdin / stdout) and the board application (target/b4q_app.c: as the payload of a framed
 * console line), so that the board parses exactly what the host-only path parsed and reports exactly what it reported.
 *
 * THE GRAMMAR (checked completely before anything is run or signed — the owner's R5 of 2026-10-28; a command that does not
 * match is refused whole, never normalised, truncated or defaulted):
 *
 *   TX <kind> <genome> <n> {<step>}n [TASK <digest> <m> {<s> <e> <t> <w>}m]
 *   kind    := normal | root | inject | a5                      (exactly one of these words)
 *   genome  := 1..8 hex digits, value <= 0xFFFFFFFF            (the lower 21 bits are the configuration; the rest must be 0)
 *   n       := decimal 0..28, and EXACTLY n step words follow   (the root has n = 0)
 *   step    := 1..8 hex digits, value <= 0x1FFFFFF             (d | ce << 8 | sr << 16 | clock << 24)
 *   digest  := exactly 64 lower-case hex digits
 *   m       := decimal 0..256, and EXACTLY 4 m decimal fields follow: s 1..n, e 0..7, t 0..1, w 0..65535
 *   fields are separated by one or more spaces; trailing spaces are allowed; anything else after the grammar is a refusal
 *   The RESULT JSON of an opening and of a transaction (the field names host/b4q_session.py reads). */
#ifndef B4Q_CMD_H
#define B4Q_CMD_H

#include <stddef.h>
#include <stdint.h>
#include "b4q_tx.h"

#define B4Q_STEP_MASK 0x1FFFFFFu
#define B4Q_GENOME_MASK 0x001FFFFFu

typedef struct {
    uint32_t genome;
    uint32_t steps[B4Q_MAX_STEPS];
    int n_steps;
    b4q_kind kind;
    b4q_task task;              /* task.n == 0: no task */
} b4q_tx_command;

/* 0 parsed; -1 refused (nothing is run on a refused command) */
int b4q_parse_tx(const char *cmd, b4q_tx_command *out);
/* a bounded unsigned number at *p (base 10 or 16, 1..`maxdigits` digits with no sign / prefix / overflow, value <= max): 0 and *p
 * advanced past it, -1 refused; shared with the SIGNREPLY parser */
int b4q_cmd_u32(const char **p, int base, unsigned long long max, unsigned long long *out);
/* the JSON objects (compact, the host-only driver's exact field order); the length written, or 0 when `max` is too small */
size_t b4q_open_json(const b4q_open_result *o, char *out, size_t max);
size_t b4q_tx_json(const b4q_tx_result *r, char *out, size_t max);

#endif /* B4Q_CMD_H */
