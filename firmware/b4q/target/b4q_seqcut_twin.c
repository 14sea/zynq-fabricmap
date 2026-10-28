/* b4q_seqcut_twin — the host harness with the line sequence cut to its limit inside a transaction (after the owner's
 * terminal_app_fixture.c of 2026-10-28): the ORIGINAL b4q_app.c and b4q_app_host.c are included unchanged; only b4q_emit is
 * wrapped so that, right before the executing side's "EV P4" event of the first candidate, the sequence is set to
 * B4Q_APP_SEQ_LIMIT - 1. The event line then carries the last sequence, the next emission is the terminal END, and — the R2
 * repair — the HAL's write half refuses every write from then on, so the unchanged b4q_tx.c stops at its first refused write:
 * no register write, no staging, no DMA after the END. host/b4q_console_e2e.py's `sequence_cut` scenario drives it. */
int app_host_main(void);
#define b4q_emit b4q_emit_orig
#include "b4q_app.c"
#undef b4q_emit
#define main app_host_main
#include "b4q_app_host.c"
#undef main

static int g_cut;
void b4q_emit(const char *line);

void b4q_emit(const char *line)
{
    if (!g_cut && strncmp(line, "EV P4", 5) == 0) { g_cut = 1; S.seq = B4Q_APP_SEQ_LIMIT - 1u; }
    b4q_emit_orig(line);
}

int main(void) { return app_host_main(); }
