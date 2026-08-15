# Offline study: why a clean no-op spoils the JTAG readback, and what to try

Written after rung 2. No board action is authorised by this document, and none was taken to
write it. The board holds nothing irreplaceable and may be powered off.

## What is established, narrowly

A successful ICAP no-op — 15/15 frames, digests matching, `fault=0` — is **sufficient** to
turn a 16/16 bit-exact JTAG control read into 0/16. A fault is not necessary. It is **not**
established that every ICAP transaction does this, only that this one did.

`0x46106ffd` stays a fail-fast indicator, not a verdict. The verdict remains bit-exact
positive controls, and post-transaction JTAG location search stays suspended. Phase 2's
`NOT_FOUND_COMPLETE` stays void.

## Review 1 — the carrier's ICAP teardown

`carrier_stream.v` releases the port cleanly, and this is worth stating because it rules out
the most convenient explanation:

* `icap_csib <= 1'b1` is a **per-cycle default** (`:476`, "paused unless a word is being
  handed over"), so the ICAP is deselected on every cycle that is not actively handing over a
  word. Nothing holds CSIB low after a transaction ends.
* Each readback envelope ends in `RB_DESYNC`, which sends `CMD` then `DESYNC` (`:835-849`).
* The frame CRC comparison then runs in `RB_CRC` with the ICAP idle and desynced.
* `RDWRB` only ever changes while CSIB is high (`:724-729`), which is the UG470 rule the
  design was corrected to obey in erratum 005.

So the carrier does not leave the ICAP selected, mid-packet, or mid-direction-change. Whatever
is spoiled is the configuration engine's state, not the port.

## Review 2 — the 2.0.0 JTAG probe's start sequence, and the thing it already did

`probe_jtag_config_read.py/2.0.0`, which produced rungs 1, 2 and R0, opened every session
with:

```
IDCODE
CFG_IN [dummy, sync, NOOP, read STAT, NOOP, NOOP] → CFG_OUT → CFG_IN [CMD DESYNC]
CFG_IN [dummy, sync, NOOP, CMD RCRC, NOOP, NOOP] → CFG_IN [CMD DESYNC]
JSHUTDOWN, RTI 12
per FAR: CFG_IN [sync, RCFG, FAR, FDRO, type-2 count, 32×NOOP] → CFG_OUT → CFG_IN [DESYNC]
```

**The 2.0.0 probe issued `RCRC` before every read, and it did not restore the readback.**
That established the pre-R1 baseline: the obvious command was already present, but in the
pre-shutdown position it was insufficient. It did not establish whether the same command
would be accepted after shutdown; that is precisely the narrower R1 question.

Note also that the STAT read happens *before* the RCRC, so the recorded `CONFIG_STATUS` is the
state as found, not as left.

## Review 3 — the CONFIG_STATUS bits

Raw, from the evidence:

| state | value | controls |
|---|---|---|
| rung 1, child #1 (fresh load) | `0x46107ffc` | 16/16 exact |
| rung 1, children #2–16 | `0x46101f8c` | 16/16 exact |
| rung 2 (after one clean no-op) | `0x46106ffd` | 0/16 |
| Phase 2 (after a faulted round) | `0x46106ffd` ×5,144 | none matched |

Bit differences, which are the part that is evidence:

* valid-first-read vs invalid: **exactly two bits** — bit 0 goes `0 → 1`, bit 12 goes
  `1 → 0`.
* valid-first-read vs valid-later-reads: bits 4, 5, 6, 13, 14 all `1 → 0`, which tracks
  position in the session rather than validity and is not the interesting difference.

Annotation, and only that: under the documented 7-series `STAT` layout bit 0 is `CRC_ERROR`
and bit 12 is `GTS_CFG_B`. **No file in this repository pins that layout**, so it is a reading
aid to be confirmed against UG470 before anything rests on it. If it is right, the invalid
state is one where the configuration engine reports a CRC error and the global tristate
control has moved — and the probe's existing `RCRC` did not clear it.

## The recovery ladder

Each rung is judged by exactly one thing: the sixteen pinned controls, bit-exact, through the
existing `--control-only` mode. Nothing else counts, and a rung that does not restore them is
a rung that failed. Every rung needs its own board ruling; none is authorised here.

`WCFG`, `FDRI`, `JPROGRAM` and `IPROG` remain forbidden throughout. Any rung that needs a JTAG
instruction the probe does not already issue must first ship the packet allowlist entry, the
structural test and the mutant that kills its removal — in that order, offline, audited.

| rung | change | instructions needed | why it might work |
|---|---|---|---|
| R0 | run `--control-only` twice on the same spoiled state, no other change | none | establishes whether the spoiling is stable or drifts; a free baseline, and it costs one power cycle to reach |
| R1 | move the `RCRC` envelope to **after** `JSHUTDOWN` rather than before | none — reordering existing ones | the engine may only accept the reset once the design is shut down |
| R2 | lengthen the RTI dwell after `JSHUTDOWN`, and add a DESYNC before the first read envelope | none — timing and an existing instruction | shutdown may need more than 12 TCK to settle after a transaction |
| R3 | omit `JSHUTDOWN` entirely and read the controls directly | none — removing one | `JSHUTDOWN` after a transaction may itself be what leaves the engine unreadable |
| R4 | `JSTART` after the reads, or a `JSTART`/`JSHUTDOWN` pair around them | **new instruction** — allowlist, test, mutant first | restores the design's run state; may also restore the engine's |

R0 through R3 need no new instruction and are therefore cheap and safe to rule on. R4 is the
first that touches the allowlist and should not be reached for until R0–R3 have failed.

### Implementation status

R0 subsequently reproduced `INSTRUMENT_INVALID` twice on the same boot (0/16 both times,
`CONFIG_STATUS=0x46106ffd` for all 32 children).  The incorrect frame contents themselves
were not repeatable, so later rungs are judged only by the bit-exact control verdict.

R1 is implemented offline in `probe_jtag_config_read.py/2.1.0`: its single RCRC envelope is
after JSHUTDOWN and before the first FDRO.  The parent acquisition tool is correspondingly
`board_signature_search.py/2.4.0`, so old and R1 captures cannot share an index.  This is an
implementation record, not a board result; R1 remains unverified until separately authorised.

## If no JTAG state recovers

Then post-transaction JTAG readback is not the instrument for this line, and the diagnosis
moves inside the carrier: an ICAP positive control, where the carrier itself reads a **known
non-zero frame that it does not write** and reports it, so the question stops depending on
JTAG at all.

Two things that would have to be true for that to be worth building. It is production RTL, so
it needs its own design, audit and gate ladder rather than an incremental patch. And it puts
the carrier's own readback path — the thing under suspicion since erratum 004 — in the
position of witness, so the control frame must be one the carrier never writes, and a failure
would be ambiguous between "the fabric does not hold it" and "the carrier cannot read it".
That ambiguity is exactly what the JTAG path was brought in to avoid, and it should be named
before the work starts rather than discovered afterwards.
