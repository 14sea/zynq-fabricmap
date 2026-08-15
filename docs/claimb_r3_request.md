# Request: R3, and the control it needs before it can be read

Offline implementation only. No board run is authorised by this document.

## R3 as ruled

Baseline is R2. Remove `JSHUTDOWN` and its dedicated 1024-TCK dwell; keep everything else.
The resulting session:

```
IDCODE
CFG_IN [dummy, sync, NOOP, read STAT, NOOP, NOOP] → CFG_OUT → CFG_IN [CMD DESYNC]
CFG_IN [dummy, sync, NOOP, CMD RCRC, NOOP, NOOP]  → CFG_IN [CMD DESYNC]
CFG_IN [dummy, sync, NOOP, CMD DESYNC, NOOP, NOOP]          ← the self-contained pre-read envelope
per FAR: CFG_IN [sync, RCFG, FAR, FDRO, type-2 count, 32×NOOP] → CFG_OUT → CFG_IN [DESYNC]
```

* **IR narrows to `0x09` (IDCODE), `0x05` (CFG_IN), `0x04` (CFG_OUT).** `0x0d` (`JSHUTDOWN`)
  moves from the allowed set to the forbidden set and must be unreachable — asserted the same
  way `JPROGRAM` and `JSTART` already are.
* Configuration commands are unchanged: `RCRC`, `RCFG`, `FAR`, `FDRO`, `DESYNC`. `WCFG`,
  `FDRI`, `IPROG` stay refused before a bit is shifted.
* A machine check must refuse a script that contains `JSHUTDOWN` anywhere, that lacks the
  RCRC envelope, that lacks the pre-read envelope, or that puts either after the first FDRO.
* **A mutant that quietly restores `JSHUTDOWN` must be killed**, by the emitted script rather
  than by a string search of the source.
* probe → 2.3.0, parent → 2.6.0, so R2 captures cannot enter an R3 index. Verify the refusal
  for **2.0.0, 2.1.0 and 2.2.0**, not only the newest.

## R3-control is part of R3, not a diagnostic beside it

R3 ships as **two acquisitions with one instrument**. The rule that makes the pair meaningful
is that nothing about the instrument differs between them:

* the same probe, the same probe and parent versions, the **same sixteen pinned controls**;
* the **same `instrument_digest`** — the two `index.json` files must record byte-identical
  values, and if they do not, the pair is void and neither result may be read;
* **no new mode flag, and nothing that changes the child Tcl.** The two runs differ by the
  state of the board when they start, and by nothing a script can see. A flag that reached the
  emitted sequence would mean the control tested a different instrument from the one under
  test, which is the whole thing this pair exists to avoid.

The pre-state is recorded where it belongs — the output directory and a field of the run
record — and a test should pin that **the child Tcl is byte-identical between the two runs**.

### The sequence on the board

```
R3-control:  physical power cycle → precheck PCFG_DONE=0 → canonical load
             → no transaction of any kind → one --control-only
             → 16/16 bit-exact, or stop
R3:          physical power cycle again → precheck → canonical load
             → one no-op passing every hard condition → same boot → one --control-only
```

Each acquisition runs **once**. No retries, no reloads, no second attempt at either. **The
state R3-control leaves behind is not reused for R3** — R3-control has itself read the device
sixteen times, and R0 showed a state that has been probed is not the state that was probed.

Stop conditions for R3-control are the same as everywhere else and are not softened by its
being "only" a control: anything other than 16/16 bit-exact, any reboot, any marker mismatch,
any bookkeeping anomaly, and the pair stops there with the evidence kept.

## The flaw this specification has, and the rung that fixes it

As written, **a failing R3 is uninterpretable**, and it is worth saying so before the board
time is spent rather than after.

Every exact read this project has ever obtained — rung 1's 16/16, and Phase 1's A20 and A21 —
was taken **with** `JSHUTDOWN`. Reading configuration without shutting the design down has
never been tried here, in any state. So if R3 returns 0/16 there are two explanations and this
experiment cannot separate them:

1. the shutdown was not what spoiled the readback; or
2. a readback without a shutdown does not work on this device at all, spoiled state or not.

The fix is one extra acquisition and it is cheap:

> **R3-control — the same no-shutdown sequence on a freshly loaded carrier that has run no
> transaction.** Exactly rung 1's conditions, with R3's script.

Read together:

| R3-control | R3 | reading |
|---|---|---|
| 16/16 | 16/16 | the shutdown was the obstacle; a recovery exists |
| 16/16 | 0/16 | no-shutdown reading works, and the shutdown was **not** the obstacle |
| 0/16 | anything | the no-shutdown sequence cannot read this device; R3 says nothing about the spoiled state |

Only the middle row is a clean negative for R3, and only the first is a positive. Without
R3-control, the last row is indistinguishable from the middle one, which is the ambiguity that
made the Phase 2 sweep worthless.

The order is the one given above, and only the first row of that table licenses anything
further. Two loads, no transaction in the first, about twelve minutes in total.

## What R3 does and does not test

The variable between R2 and R3 is the shutdown action, and that is the whole point. It is not
a test of whether some other timing helps, nor of whether `JSTART` would; R4 remains where it
was, behind the allowlist procedure.

## Standing rules for the verdict

Unchanged, and worth restating because three rungs have now been judged by them:

* the verdict is the sixteen pinned controls, bit-exact at the same FAR, and nothing else;
* `CONFIG_STATUS` is **not** a validity proxy in either direction — R1 reported the values
  associated with valid reads while reading 0/16;
* no comparison of captured **content** between rungs is admissible — R0 showed two runs of
  one rung already disagree on nine of sixteen frames. The all-zero observation of R1 and R2
  is reported as a correlation with the RCRC position, not as a measurement of anything.
