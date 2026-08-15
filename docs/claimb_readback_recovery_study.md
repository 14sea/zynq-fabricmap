# Offline study: why a clean no-op spoils the JTAG readback, and what to try

Originally written after control-gradient rung 2; updated through the R3-control result and
the offline R4 implementation. No board action is authorised by this document, and none was
taken to write it. The board holds nothing irreplaceable and may be powered off.

## What is established, narrowly

A successful ICAP no-op — 15/15 frames, digests matching, `fault=0` — is **sufficient** to
turn a 16/16 bit-exact JTAG control read into 0/16. A fault is not necessary. It is **not**
established that every ICAP transaction does this, only that this one did.

No `CONFIG_STATUS` value is a validity proxy. R1 produced values previously associated with
valid reads while all sixteen controls were wrong. The verdict remains bit-exact positive
controls, and post-transaction JTAG location search stays suspended. Phase 2's
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
| R1, child #1 | `0x46106ffd` | 0/16 overall |
| R1, child #2 | `0x46107ffc` | 0/16 overall |
| R1, children #3–16 | `0x46101f8c` | 0/16 overall |
| R2, child #1 | `0x46106ffd` | 0/16 overall |
| R2, child #2 | `0x46107ffc` | 0/16 overall |
| R2, children #3–16 | `0x46101f8c` | 0/16 overall |

Bit differences, which are the part that is evidence:

* valid-first-read vs invalid: **exactly two bits** — bit 0 goes `0 → 1`, bit 12 goes
  `1 → 0`.
* valid-first-read vs valid-later-reads: bits 4, 5, 6, 13, 14 all `1 → 0`, which tracks
  position in the session rather than validity and is not the interesting difference.

Annotation, and only that: under the documented 7-series `STAT` layout bit 0 is `CRC_ERROR`
and bit 12 is `GTS_CFG_B`. **No file in this repository pins that layout**, so it is a reading
aid to be confirmed against UG470 before anything rests on it. R1 shows why no decision may
rest on these names or values: moving RCRC changed later status words to the values previously
seen during exact reads, while the controls remained 0/16. The status transition is evidence
that the reordered command affected engine state, not that it restored readback.

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
| R2 | fix the post-`JSHUTDOWN` dwell at **1024 TCK**, and add one self-contained SYNC…DESYNC envelope before the first read envelope | none — timing and an existing command | tests the fixed combination “1024 TCK + extra DESYNC”; it does not establish a general settling bound |
| R3 | omit `JSHUTDOWN` entirely and read the controls directly | none — removing one | `JSHUTDOWN` after a transaction may itself be what leaves the engine unreadable |
| R4 | complete `JSHUTDOWN → JSTART`, then use UG470 Table 6-6's documented shutdown-readback prefix | **new instruction** — allowlist, test, mutant first | exercises the startup state machine before returning to the only prefix that has produced exact reads |

R0 through R3 need no new instruction and are therefore cheap and safe to rule on. R4 is the
first that touches the allowlist and should not be reached for until R0–R3 have failed.

### Implementation status

R0 subsequently reproduced `INSTRUMENT_INVALID` twice on the same boot (0/16 both times,
`CONFIG_STATUS=0x46106ffd` for all 32 children).  The incorrect frame contents themselves
were not repeatable, so later rungs are judged only by the bit-exact control verdict.

R1 (`probe_jtag_config_read.py/2.1.0`, parent `board_signature_search.py/2.4.0`) was then run
on a freshly rebuilt spoiled state. All sixteen emitted Tcl files had
`JSHUTDOWN < RCRC < FDRO`, but the result was `INSTRUMENT_INVALID`, 0/16. R1 therefore failed.
Its first child reported `0x46106ffd`; later children reported `0x46107ffc` and
`0x46101f8c`, the same values previously seen alongside valid reads. That is direct evidence
that `CONFIG_STATUS` is not a validity proxy in either direction. The changed status does
show that the relocated RCRC reached and affected configuration-engine state; it does not
show that readback recovered.

R2 (`probe_jtag_config_read.py/2.2.0`, parent `board_signature_search.py/2.5.0`) then waited
1024 TCK after JSHUTDOWN and inserted a self-contained SYNC…DESYNC before the first FDRO.
All sixteen emitted scripts contained that exact sequence, but the result remained
`INSTRUMENT_INVALID`, 0/16. Its per-child status values and sixteen all-zero control frames
were byte-identical to R1. The narrow result is that **this fixed combination** — 1024 TCK
plus the additional envelope — had no observed effect. It says nothing about a longer delay,
a delay between RCRC and FDRO, or a slower TCK.

R3 was implemented as `probe_jtag_config_read.py/2.3.0`, but R3-control stopped the pair:
on a fresh load with no transaction, the no-`JSHUTDOWN` instrument returned 0/16 all-zero
controls where rung 1's shutdown instrument had returned 16/16 exact. R3 therefore could not
measure the spoiled state and the post-no-op acquisition was formally withdrawn. Narrowly,
`JSHUTDOWN` is necessary for this fixed readback path on this device; that observation is not
a general rule for JTAG readback.

R4 is implemented offline as `probe_jtag_config_read.py/2.4.0`, with parent
`board_signature_search.py/2.7.0`, following `claimb_r4_protocol.md`. It emits this exact
prefix before every child's first FDRO:

```
JSHUTDOWN → RTI 12 → JSTART → RTI 2000 → RCRC envelope → JSHUTDOWN → RTI 12
```

The two 12-TCK dwells cite UG470 v1.17 Chapter 6 Table 6-6 and the 2000-TCK dwell cites
Chapter 10 Table 10-4. The emitted-Tcl checker rejects missing or late `JSTART`, missing
leading shutdown, any change in any dwell, R2's extra pre-read envelope, and `RCRC` after the
final `JSHUTDOWN`—the ordering error made by the superseded first R4 draft. `JSTART` is now
allowlisted; `JPROGRAM`, IPROG, WCFG and FDRI writes remain unreachable. The R4-control and R4
acquisitions use byte-identical Tcl and instrument digests. This is an implementation record
only: neither board acquisition is authorised here.

The subsequent board pair and its independent replication both returned 16/16 controls on
fresh-load control acquisitions and again after one clean ICAP no-op. All four acquisitions
used the same parent/child versions, control FARs, byte-identical child Tcl and instrument
digest. R4 is therefore an independently reproduced recovery method for the state left by
that clean no-op. It remains untested after the known-answer `F_READBACK` fault and does not
explain why the startup cycle restores readback.

After those pairs closed, parent 2.7.1 removed an inaccurate state-specific phrase from the
human-readable `INSTRUMENT_VALID` message. The verdict had said “in this post-fault state”
even for fresh-load controls. It now says “in this acquisition”. This wording-only source
change deliberately creates a new instrument digest; future paired acquisitions must validate
that identity rather than borrowing the four completed 2.7.0 observations.

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
