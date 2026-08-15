# Rung 2: a clean ICAP no-op is enough to spoil the JTAG readback

Fresh power cycle, read-only precheck at the reference values with `PCFG_DONE=0`, then the
canonical erratum-006 `carrier.bit` (`8c3369e8…`) loaded onto the empty PL and **one** no-op,
marker `18cc0ddd534ffc33`. No mutation, no arm, no scoring.

## The no-op passed, completely

Every condition the authorisation named:

```
verdict NO-OP CALIBRATION PASSED     15/15 frames, 0 differing
readback digest matches              fault=0   recovery_required=0
configuration_valid=1                scorer_armed=0
rb_frames_ok=15  env_committed=7     latency valid on all three envelopes (1 word each)
190 commands, 0 reboots, 0 missing prompts
```

This is the transaction the carrier is supposed to perform, performed correctly, with nothing
gone wrong anywhere in it.

## Then, in the same boot, without reloading: the controls fail

**`INSTRUMENT_INVALID` — 0 of 16, all sixteen read, none exact.**

```
0x00000900  expected 48 non-zero words / observed  0
0x00000986  expected 66 / observed 16
0x000009a2  expected 71 / observed 16
0x00000a8e  expected 46 / observed 15
0x00000b8a  expected 84 / observed 13
0x00000c04  expected 14 / observed 19
…observed non-zero words across all sixteen: 0 to 20
```

The same sixteen frames came back **bit-exact an hour earlier** on rung 1, on a carrier that
had been loaded and left alone. The only difference between the two rungs is that this one
ran a no-op.

## What this settles

**A successful ICAP transaction is sufficient to spoil subsequent JTAG readback.** No fault
is required. That is rung 2's ruled reading and it is what happened: rung 1 passed, rung 2
failed, and the difference between them is one clean transaction.

It follows that Phase 2's invalid readback was never about the fault. The sweep that produced
`NOT_FOUND_COMPLETE` was taken after a known-answer transaction, and a transaction alone is
enough — the fault it ended in was incidental to the readback being meaningless.

And it has a consequence worth stating plainly, because it closes a route rather than opening
one: **the location question cannot be answered by JTAG readback after the transaction that
writes the candidate.** Reading the fabric requires a state no transaction has touched, and
the only way back to such a state is a power cycle, which erases what would be read.

## What it does not settle

Not why. Not whether the spoiling is recoverable by anything short of a power cycle. Not
whether the candidate write ever reached the fabric — that question is exactly as open as it
was, and this rung removes the instrument that was going to answer it rather than answering
it.

Rung 3 was to ask whether the fault state spoils readback. It is now largely answered in
advance: a transaction alone does, and every fault so far arrived at the end of one. The
ruling stops this round at rung 2 regardless.

## The CONFIG_STATUS classifier now has two invalid states

| state | CONFIG_STATUS | controls exact |
|---|---|---|
| rung 1, loaded and untouched | `0x46107ffc` (child #1), `0x46101f8c` (#2–16) | **16/16** |
| rung 2, after one clean no-op | `0x46106ffd` (all 16) | **0/16** |
| Phase 2, after a faulted known-answer | `0x46106ffd` (all 5,144) | n/a — none matched |

Two independent invalid states now report `0x46106ffd` and the one valid state does not. That
is a real correlation rather than a single coincidence, and it is still a correlation: nothing
here shows the status causes or is caused by the readback failing, and a state that reports
`0x46106ffd` while reading correctly would refute it. It is worth recording as a cheap
pre-flight check — read the status, and if it is `0x46106ffd`, do not trust what follows.
