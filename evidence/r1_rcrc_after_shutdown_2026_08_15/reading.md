# R1: the reorder does something real, and it is not a recovery

A clean spoiled state was rebuilt rather than reusing R0's twice-probed one, so this is
directly comparable to rung 2 and R0: precheck at the fresh reference with `PCFG_DONE=0`, the
canonical `carrier.bit` (`8c3369e8…`) onto an empty PL, one no-op passing every condition —
15/15 and none differing, digest matching, `fault=0`, `recovery_required=0`, three latencies
valid, no reboots — as marker `18cc103ba298e7da`. Then one `--control-only` in that boot.

## R1 was really on the wire

A negative result is only worth having if the thing being tested actually ran. Verified from
the scripts each child wrote, not from the version string:

```
children whose ACTUAL tcl has JSHUTDOWN < RCRC < FDRO : 16 of 16
children whose tcl digest matches the capture record  : 16 of 16
child tool versions                                   : probe 2.1.0 ×16
```

## The verdict: R1 failed

**`INSTRUMENT_INVALID`, 0 of 16, all sixteen read.** Moving the `RCRC` envelope to after
`JSHUTDOWN` does not restore the control readback. By the ruling, R2 may now be prepared.

## But the state changed, in two ways worth recording

**One.** `CONFIG_STATUS` had been `0x46106ffd` in every child of every spoiled-state run so
far — rung 2, R0-A and R0-B, forty-eight children, no exceptions. Under R1:

| child | CONFIG_STATUS |
|---|---|
| #1 | `0x46106ffd` — the state as found, since the STAT read precedes the RCRC |
| #2 | `0x46107ffc` |
| #3 … #16 | `0x46101f8c` |

Those are the values the *valid* rung-1 state reported. So the RCRC, in its new position,
**does** clear the status, and the clearing persists into later processes.

**Two.** Every control frame came back all-zero — 16 of 16, no non-zero words anywhere. The
three previous spoiled-state runs returned varying non-zero content (non-zero word counts
ranging 0–20, 0–20 and 0–9, with 8, 8 and 11 all-zero frames respectively). R0 established
that this content is not reproducible between runs, so **one R1 run showing all zeros is an
observation and not yet a property**; it would need repeating before anything rests on it.

## The correction this forces

`0x46106ffd` can no longer be treated as a fail-fast indicator of readback validity. This run
reports the *good* values in fifteen of sixteen children and reads 0/16.

I wrote earlier that "a state that reports `0x46106ffd` while reading correctly would refute
it". The refutation arrived from the other side — good status, bad reads — and it refutes the
association just as thoroughly. **The status must not be used as a proxy for validity in
either direction.** The only verdict remains the sixteen controls, bit-exact.

That the status moved at all is the useful part: it shows the reorder reaches the
configuration engine and changes its reported state. Whatever prevents a readback from
returning the configuration array is not what those status bits report, and R2's timing
change is now being asked of a machine we know we can affect.

Stopped here as ruled: no R2, no location search, no mutation, no arm, no scoring.
