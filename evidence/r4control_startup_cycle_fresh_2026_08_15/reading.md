# R4-control: the startup-cycle sequence is a working instrument

Physical power cycle, read-only precheck at the fresh reference with `PCFG_DONE=0`,
repository at `fbeb6fd` with a clean tracked tree, the canonical `carrier.bit` (`8c3369e8…`)
loaded once onto an empty PL as marker `18cc165290c02487`, **no no-op, no carrier transaction,
no AXI, no arm, no scoring**. Then one `--control-only`.

## It was the R4 sequence

```
children whose ACTUAL tcl passes the R4 order check : 16 of 16
tcl digests matching their capture                  : 16 of 16
child tool versions                                 : probe 2.4.0 ×16
```

The order check is a whole-prefix comparison, so passing it means each child really emitted
`JSHUTDOWN → RTI 12 → JSTART → RTI 2000 → RCRC → JSHUTDOWN → RTI 12 → FDRO`, with no pre-read
DESYNC.

## The result

**`INSTRUMENT_VALID` — 16 of 16 bit-exact, none unread.** Every control reproduced its known
non-zero base frame at its own FAR, whole:

```
expected 48 non-zero words / observed 48      expected 46 / observed 46
expected 66 / observed 66                     expected 84 / observed 84
expected 71 / observed 71                     expected 14 / observed 14
…all sixteen exact
```

Every entry `ok`, plmark identical at both ends.

## What it settles

**Adding `JSTART` and a 2000 TCK dwell in front of the documented shutdown-readback prefix
does not break the read.** The R4 sequence is a working instrument on a device known to be
readable, which is the precondition R4 needed and the one R3 failed to meet.

So if the second acquisition returns 0/16, that will mean the startup cycle did not repair the
spoiled state — not that the script cannot read. That distinction is the entire reason this
control exists, and it cost one load and about a second of reading.

It settles nothing about the spoiled state. R4 has not been run.

## Two observations, recorded not interpreted

`CONFIG_STATUS` here is `0x46107ffc` in child #1 and `0x46101f8c` in children #2–16, which is
rung 1's pattern exactly. R3-control, whose sequence had no `JSHUTDOWN` at all, reported
`0x46107ffc` in all sixteen. The value moving after the first child tracks the presence of a
shutdown rather than the validity of the read — consistent with everything else, and still not
a validity proxy.

The tool's `INSTRUMENT_VALID` message is hardcoded to say "in this post-fault state". On a
fresh untransacted load that phrase is wrong. It has no effect on the verdict, which is
computed from the sixteen comparisons, but a later reader of `verdict.json` could be misled by
it and it should be corrected the next time production code is opened.

Stopped as ruled: no R4, no second acquisition, no retry.
