/* b4q_platform — the three platform acts the application needs and does not perform itself: the watchdog (armed once the
 * identity page asked for it, kicked after every emitted line and nowhere else), and the halt after the END line. On the
 * board: target/b4q_board_main.c (XScuWdt, a spin); on the host: target/b4q_app_host.c (counters, exit). */
#ifndef B4Q_PLATFORM_H
#define B4Q_PLATFORM_H

#include <stdint.h>

int b4q_plat_watchdog_start(void);   /* 0 armed; -1 the watchdog could not be brought up (fail-closed: the session does not run) */
void b4q_plat_kick(void);            /* restart the watchdog; a no-op until armed */
void b4q_plat_halt(void);            /* never returns: the board spins (an armed watchdog then resets the PS); the host exits */
/* the evidence log's memory (the board: a strongly-ordered DDR region; the host: a buffer) and the tick stamped on its records
 * (the board: the global timer's low word, unmeasured; the host: a counter) */
uint8_t *b4q_plat_ring_base(uint32_t *capacity);
uint32_t b4q_plat_tick(void);

#endif /* B4Q_PLATFORM_H */
