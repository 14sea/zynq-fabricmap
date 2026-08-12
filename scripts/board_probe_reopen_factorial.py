#!/usr/bin/env python3
"""SUPERSEDED 2026-08-12. Do not run. Kept because `evidence/reopen_factorial_2026_08_12/`
names it as the tool that produced conditions A-D.

What it did
-----------
A 2x2 over a console reopen: gap (30 s vs back-to-back) x a bare CR on open (no vs yes),
five trials each, order A, B, C, D. Twenty trials, zero events. The record is in
`evidence/reopen_factorial_2026_08_12/record.json`.

Why it is superseded rather than continued
------------------------------------------
The question it was asked to settle has been answered from source instead, and the answer
retires the experiment:

* U-Boot declares `md` repeatable (`U_BOOT_CMD(md, 3, 1, do_mem_md)`, `cmd/mem.c:1318`), so
  a bare CR RE-RUNS the last command; `do_mem_md` resumes from `dp_last_addr`, which the
  previous call advanced past the word it printed (`cmd/mem.c:79`, `:110`, `:113`).
* After an `md.l` of the carrier's FAULT register that address is FAULT + 4, which the
  carrier answers with SLVERR (`vivado/carrier/carrier_axil.v:217`), the A9 takes a data
  abort, `bad_mode()` panics, and with `CONFIG_PANIC_HANG` unset `panic_finish()` calls
  `do_reset()`. (Offsets, not absolutes: only `board_uboot_axi` may name the window.)

So the three "spontaneous restarts" were this tooling rebooting the board, and the fix is
that `Probe` transmits nothing on open at all.

**E and F were never run, and their design was insufficient anyway.** They were meant to put
the `tcflush` purge back, E as the historical path and F as its control. But the trigger is
the CR's REPEAT of a preceding `md`, and in this harness the command before every close was
`printenv plmark` — harmless to repeat. E would therefore have reproduced the historical
*flags* while omitting the historical *precondition*, and a null result would have proved
nothing. They are not a pending experiment.
"""

from __future__ import annotations

import sys

SUPERSEDED = (
    "board_probe_reopen_factorial.py is superseded and must not be run. The reopen restart "
    "is explained in source: a bare CR repeats `md` at the auto-incremented address, the "
    "carrier answers SLVERR, and U-Boot's abort path resets the CPU. Probe now transmits "
    "nothing on open. Conditions E and F were never run and their design was insufficient — "
    "the command preceding every close here was `printenv plmark`, so repeating it is "
    "harmless and the historical precondition was absent."
)


def main() -> int:
    print(SUPERSEDED, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
