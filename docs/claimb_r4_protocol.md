# R4 protocol derivation: a startup/shutdown cycle before the first read

Offline derivation only. No implementation, no allowlist entry, no board run is authorised by
this document, and R4 must not be built until the open item in §4 is closed.

## 1. R3 is cancelled, and what R3-control actually showed

R3 is withdrawn and must not be executed. R3-control established, **for this fixed probe
sequence on this device**, that without `JSHUTDOWN` a fresh load with no transaction returns
0/16 where the same controls read 16/16 with it. That is a fact about this instrument and this
part. It is **not** a general law that JTAG readback requires a shutdown, and nothing in this
document treats it as one.

## 2. Why "JSTART after the reads" is not R4

Each control is read by its own OpenOCD process, one FAR per child, because a readback is
trustworthy only as a process's first read. A `JSTART` emitted after a child's `FDRO`
therefore cannot affect that child's own measurement — the only measurement it makes — and the
first control can never benefit from it at all. A trailing `JSTART` could only influence
*later* children, which is both a weaker claim and an untestable one under the standing rule
that content is not compared between runs.

**R4 must place the startup action before the first `FDRO` of every child, or it is not
testing anything the verdict can see.**

## 3. The two candidate shapes

Both keep `JSHUTDOWN`, because §1 says the read does not work without it.

**A — bare start, then shutdown**

```
IDCODE → STAT envelope → JSTART → dwell → JSHUTDOWN → dwell
       → RCRC envelope → pre-read envelope → FDRO
```

**B — shutdown, start, shutdown: a complete cycle**

```
IDCODE → STAT envelope → JSHUTDOWN → dwell → JSTART → dwell → JSHUTDOWN → dwell
       → RCRC envelope → pre-read envelope → FDRO
```

B is the better-motivated of the two. In the state R4 exists for, the design is *running* when
the probe arrives — the no-op left it running and nothing has shut it down. A bare `JSTART`
issued to an already-started device may be a no-operation, in which case shape A tests
nothing; B drives the startup state machine through a full transition regardless of where it
began. A is cheaper to emit and worth keeping only as a fallback if B is refused for a reason
this derivation has not anticipated.

**Neither shape is a recovery hypothesis with a mechanism behind it.** The honest statement is
that R1 and R2 showed the reordered `RCRC` reaches the configuration engine without restoring
the readback, and the startup state machine is the next state variable this probe can touch at
all. That is why R4 is next — not because there is a theory that it will work.

## 4. The open item: the dwell figures are not pinned, and cannot be pinned from here

The ruling asks for the required RTI clocks to be pinned to UG470. **They cannot be, from this
machine.** UG470 is not in this repository and not on this box; `ref/` is gitignored for
copyrighted references and does not exist here.

Worse, and worth saying plainly: **the existing `runtest 12` has no citation either.** It
entered the probe in `850f709`, written from general knowledge rather than derived from a
document, and every rung since has inherited it. No file in this repository pins it. The R2
dwell of 1024 was likewise a chosen number, not a derived one.

So before R4 is implemented, one of these has to happen:

* **obtain UG470 and cite it** — the table or figure number, in the source, next to each
  `runtest`, for `JSTART` and for `JSHUTDOWN` alike; or
* **declare the dwells explicitly unpinned** — a named constant carrying a `provenance` field
  that says "chosen, not derived", with the same treatment applied retroactively to the
  existing 12, so that no reader mistakes a habit for a specification.

The second is acceptable and is the smaller lie; what is not acceptable is a comment claiming
UG470 backing that nobody has checked. A test should assert that every dwell constant carries
a provenance string.

## 5. The acquisition pair, unchanged in shape

R4 ships as two acquisitions with one instrument, on the same terms R3 established: same
probe, same versions, same sixteen controls, byte-identical child Tcl, identical
`instrument_digest`, and no mode flag reaching the emitted sequence.

```
R4-control:  power cycle → precheck → canonical load → NO transaction → one --control-only
             → 16/16 bit-exact, or the pair stops and R4 is not run
R4:          power cycle again → precheck → canonical load → one no-op passing the full gate
             → same boot → one --control-only
```

`R4-control` is not optional and is not a formality: it is what distinguishes "the startup
cycle did not fix the spoiled state" from "this sequence cannot read anything", which is
exactly the distinction R3-control had to make and did.

## 6. What implementation must ship before any board talk

* the allowlist entry for `JSTART` (`0x0c`), moving it from `FORBIDDEN_IR` to `IR`, with
  `JPROGRAM` and `IPROG` staying forbidden and `WCFG`/`FDRI` untouched;
* a structural test on the **emitted** Tcl: `JSTART` appears exactly as many times as the
  shape requires, before the first `FDRO`, with `JSHUTDOWN` in its ruled position;
* version isolation: probe 2.4.0 and parent 2.7.0, refusing 2.0.0 through 2.3.0 captures;
* mutants killed from the emitted script, not by string search — **a missing `JSTART`**, and
  **`JSTART` after the first `FDRO`**, and if shape B is chosen, **a missing leading
  `JSHUTDOWN`**;
* the dwell provenance decision of §4, applied to the new constants and retroactively to the
  old one.

## 7. Standing rules, unchanged

The verdict is the sixteen pinned controls, bit-exact at the same FAR, and nothing else.
`CONFIG_STATUS` is not a validity proxy in either direction — it has now been refuted twice,
in a spoiled state and in a good one. No comparison of captured content between rungs is
admissible.
