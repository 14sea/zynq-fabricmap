# R0: the verdict is stable, the data is not

The baseline rung of the recovery ladder. The rung-2 state had been lost to a power cycle, so
it was rebuilt exactly as before — precheck at the fresh power-on reference with
`PCFG_DONE=0`, the canonical `carrier.bit` (`8c3369e8…`) onto an empty PL, and one no-op that
passed every condition: 15/15 frames and none differing, digest matching, `fault=0`,
`recovery_required=0`, `configuration_valid=1`, scorer never armed, all three latencies valid,
190 commands, no reboots. Marker `18cc0ef14374aac8`.

Then two identical `--control-only` acquisitions, same boot, nothing between them.

## The result

| | verdict | controls exact | CONFIG_STATUS |
|---|---|---|---|
| R0-A | `INSTRUMENT_INVALID` | 0 of 16 | `0x46106ffd` ×16 |
| R0-B | `INSTRUMENT_INVALID` | 0 of 16 | `0x46106ffd` ×16 |

Both closed on the same marker at both ends. This also reproduces rung 2 across a power
cycle: a clean no-op spoils the readback, repeatably.

**`invalid → invalid`, so the spoiled state is stable in verdict and R1 is qualified to be
tested.**

## What the two rounds do not share

The verdict is the only thing that repeated. The data did not:

```
frame digests identical between the rounds : 7 of 16
  of those, all-zero (the zero floor)      : 7
  of those, non-zero (a real repeat)       : 0
all-zero frames                            : A 8,  B 11
observed non-zero words                    : A 0-20, B 0-9
```

Reading the same sixteen addresses twice, in one boot, with the same tool and no change in
between, returned different content at nine of them, and not one non-zero frame came back the
same twice. The seven digests that match are zeros matching zeros, which this line has been
careful about since the first DDR capture.

## What that means for the ladder

The stability R0 was asked to establish holds at the level of the verdict, and that is the
level the ladder judges at: `INSTRUMENT_VALID` on the sixteen controls, bit-exact, or nothing.
R1 can therefore be run and a negative result from it will mean something.

It does not hold at the level of content, and that is worth carrying forward as a rule rather
than rediscovering: **no comparison of captured content between rungs is admissible.** Two
runs of the same rung disagree on nine of sixteen frames, so any story built on "the data
changed after R1" would be a story about noise. The only admissible difference between rungs
is the control verdict.

`0x46106ffd` reported in all thirty-two child reads across both rounds, unchanged. It remains
a fail-fast indicator awaiting a UG470 check on the bit names, not a verdict.

Stopped here as ruled. R1 not started; no mutation, no arm, no scoring, no known-answer.
