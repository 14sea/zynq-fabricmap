# R2: more dwell and a pre-read DESYNC change nothing

Conditions aligned with R1 exactly: physical power cycle, precheck at the fresh reference
with `PCFG_DONE=0`, repository at `7c0351a` with a clean tracked tree, the canonical
`carrier.bit` (`8c3369e8…`) onto an empty PL, one no-op passing every hard condition —
15/15 and none differing, digest matching, `fault=0`, `recovery_required=0`, three latencies
valid, no reboots — as marker `18cc11e4644f7028`. Then one `--control-only` in that boot.

## R2 was really on the wire

From the scripts the children wrote, not from a version string:

```
children whose ACTUAL tcl is the full R2 sequence  : 16 of 16
  (JSHUTDOWN → runtest 1024 → RCRC → pre-read SYNC…DESYNC → FDRO)
tcl digests matching their capture                 : 16 of 16
child tool versions                                : probe 2.2.0 ×16
```

## The verdict: R2 failed

**`INSTRUMENT_INVALID`, 0 of 16, all sixteen read.** An 85-fold longer shutdown dwell and a
self-contained DESYNC before the first read do not restore the control readback.

## R2 is indistinguishable from R1

Not merely "also a failure" — the same fingerprint, in both things that R1 changed:

| | R1 | R2 |
|---|---|---|
| verdict | `INSTRUMENT_INVALID`, 0/16 | `INSTRUMENT_INVALID`, 0/16 |
| `CONFIG_STATUS` | `0x46106ffd` ×1, `0x46107ffc` ×1, `0x46101f8c` ×14 | identical |
| control frames | 16/16 all-zero | 16/16 all-zero |

So the timing was not the obstacle. Whatever the reordered `RCRC` does — and it does
something, since the status moves — a 1024 TCK dwell and an extra envelope add nothing to it.

## The all-zero observation, now repeated

After R1 this was flagged as an observation needing repetition before it could be a property,
because R0 had shown captured content is not reproducible between runs. It has now repeated:

* `RCRC` **before** `JSHUTDOWN` (rung 2, R0-A, R0-B): varying non-zero content, with 8, 8 and
  11 all-zero frames of sixteen.
* `RCRC` **after** `JSHUTDOWN` (R1, R2): **16 of 16 all-zero, both times.**

Two trials against three, and all-zero is a degenerate value that cannot vary downward, so
this is weaker than it looks and is still not a verdict. What it is: a reproducible difference
that tracks the `RCRC` position, in a state where nothing else has been reproducible.

## Where the ladder stands

R0 established the spoiled state is stable in verdict. R1 and R2 have both failed, and the
one thing they demonstrably do — clearing the status bits — is not enough. The remaining rung
that needs no new JTAG instruction is **R3: omit `JSHUTDOWN` entirely and read the controls
directly**, on the hypothesis that the shutdown after a transaction is itself what leaves the
engine unreadable. R4 (`JSTART`) needs the allowlist procedure first and should wait for R3.

Stopped as ruled: no R3, no sweep, no mutation, no arm, no scoring.
