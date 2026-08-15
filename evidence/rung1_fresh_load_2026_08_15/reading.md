# Rung 1: a freshly loaded, untransacted carrier reads back exactly

The first rung of the ruled gradient. Read-only precheck first — all four devcfg registers at
their fresh power-on values, `PCFG_DONE=0`. Then the canonical erratum-006 `carrier.bit`
(`8c3369e8…`, the published one, not the ECO) loaded onto the empty PL, marker
`18cc0afcb4ebbe30`. **No transaction, no no-op, no mutation, no arm, no scoring** — the
loader loads and `--control-only` has no vocabulary for anything else.

Then one `--control-only` acquisition: exactly the sixteen pinned positive controls.

## The result

**`INSTRUMENT_VALID` — 16 of 16, all bit-exact, none unread.**

Every control reproduced its known non-zero base frame at its own FAR, whole:

```
0x00000900  expected 48 non-zero words / observed 48   exact
0x00000986  expected 66 / observed 66                  exact
0x000009a2  expected 71 / observed 71                  exact
0x00000a8e  expected 46 / observed 46                  exact
0x00000b8a  expected 84 / observed 84                  exact
0x00000c04  expected 14 / observed 14                  exact
…all sixteen exact
```

Bookkeeping: mode `control-only`, tool 2.3.0, every entry `ok`, plmark identical at both ends,
median 0.058 s per child, 1.0 s of child time for the whole acquisition.

## What it settles, and what it does not

It settles the first branch of the reading table: **the JTAG method and the control set are
sound**. A failure here would have indicted them and made everything downstream meaningless;
it did not happen. Sixteen frames chosen for being non-zero and unique in the device came
back whole, at their own addresses, on a device that had been loaded and left alone.

It settles nothing about ICAP or about the fault state. Rung 2 (a fresh boot whose no-op
passed) and rung 3 (a known-answer fault) are separate rungs and separate rulings, and this
round stops here as instructed.

## The CONFIG_STATUS observation, sharpened

Within this single acquisition the status is not constant, and it varies by position rather
than by outcome:

| child | CONFIG_STATUS | control exact |
|---|---|---|
| #1 | `0x46107ffc` | yes |
| #2 … #16 | `0x46101f8c` | yes, all of them |

That is the same pattern Phase 1 showed across separate runs — the first process of a fresh
load reports `0x46107ffc`, later processes report `0x46101f8c` — and here both values
accompany exact reads. So the two "good" values are explained by position in the session, not
by validity, and what remains distinctive about the invalid Phase 2 state is `0x46106ffd`,
uniform across all 5,144 of its captures.

Still recorded rather than interpreted: one valid state and one invalid state is not a test of
a classifier, and rungs 2 and 3 are what would give it more than one invalid state to speak
about.
