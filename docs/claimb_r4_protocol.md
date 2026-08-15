# R4 protocol derivation: a startup/shutdown cycle before the first read

Offline derivation only. No implementation, no allowlist entry and no board run is authorised
by this document. The sequence below is fixed by UG470 v1.17 and is what an implementation must
emit; nothing here licenses writing it.

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

## 3. The sequence, from UG470 v1.17

The user obtained the document, and it settles both the dwells and an error in the first draft
of this derivation.

* **Chapter 6, Table 6-6, "Shutdown Readback Command Sequence"** — `RCRC` is sent **before**
  `JSHUTDOWN`, then **12 TCK in Run-Test/Idle**, and only then `RCFG`/`FAR`/`FDRO`.
* **Chapter 10, Table 10-4, "Single Device Configuration Sequence"** — after `JSTART`, hold
  **at least 2000 TCK in Run-Test/Idle** to advance the startup sequence.

  AMD UG470, *7 Series FPGAs Configuration User Guide*, v1.17:
  <https://docs.amd.com/v/u/en-US/ug470_7Series_Config>

### The correction this forces on §3 of the first draft

The first draft's shape B put the second `RCRC` **after** the final `JSHUTDOWN`. That is the
reverse of Table 6-6 and must not be implemented. Shape A is likewise superseded.

It also reframes R1 and R2 in a way worth recording: the 2.0.0 probe placed `RCRC` before
`JSHUTDOWN`, which is what Table 6-6 specifies, and R1 and R2 moved it *after* — that is, both
rungs tested a **deviation** from the documented sequence, and both failed. Nothing about that
was known when they were run, and it does not change their verdicts, but it does mean the
documented prefix is the one to keep rather than the one to keep experimenting on.

### R4, fixed

```
IDCODE → STAT envelope
JSHUTDOWN → RTI 12          # UG470 v1.17 ch.6 Table 6-6
JSTART    → RTI 2000        # UG470 v1.17 ch.10 Table 10-4, "at least 2000"
RCRC envelope               # UG470 v1.17 ch.6 Table 6-6, before the shutdown
JSHUTDOWN → RTI 12          # UG470 v1.17 ch.6 Table 6-6
per FAR: RCFG → FAR → FDRO → CFG_OUT → DESYNC
```

A complete shutdown/startup transition first, then the documented shutdown-readback prefix
exactly as Table 6-6 gives it — the same prefix that read 16/16 on a fresh load in rung 1.

**R2's extra pre-read DESYNC is not carried forward.** It is not part of the UG470 sequence,
and R2 measured it to add nothing.

## 4. Dwell provenance, now that there is a document

Every dwell constant carries a provenance record, and a test asserts that each one has one:

| dwell | value | provenance |
|---|---|---|
| after `JSHUTDOWN` | 12 TCK | `document_id: UG470, version: v1.17, chapter: 6, table: 6-6` |
| after `JSTART` | 2000 TCK | `document_id: UG470, version: v1.17, chapter: 10, table: 10-4` |
| R2's dwell | 1024 TCK | **`chosen, not derived`** — historical, not carried into R4 |

One distinction has to be kept straight. The original `runtest 12` entered the probe in
`850f709` written from general knowledge, and its value **turns out to agree** with Table 6-6.
That is a post-hoc confirmation of the number, **not** a citation of where it came from, and
the provenance record must say so rather than implying the constant was derived from the table
at the time. R2's 1024 remains chosen and derived from nothing.

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
* a structural test on the **emitted** Tcl that pins the whole prefix in order and by value:
  `JSHUTDOWN` → `runtest 12` → `JSTART` → `runtest 2000` → the `RCRC` envelope → `JSHUTDOWN`
  → `runtest 12` → the first `FDRO`. The dwells are checked **exactly**: 12, 2000, 12, and
  neither a longer nor a shorter one passes;
* version isolation: probe 2.4.0 and parent 2.7.0, refusing 2.0.0 through 2.3.0 captures;
* mutants killed from the emitted script rather than by a string search, covering at least:
  **a missing `JSTART`**; **`JSTART` after the first `FDRO`**; **a missing leading
  `JSHUTDOWN`**; **a wrong dwell** on any of the three; and **`RCRC` moved after the final
  `JSHUTDOWN`**, which is the mistake this derivation itself made and which Table 6-6 forbids;
* the provenance records of §4 on every dwell constant, with a test asserting each carries one,
  and the historical 1024 marked `chosen, not derived` rather than quietly inheriting a
  citation it never had.

## 7. Standing rules, unchanged

The verdict is the sixteen pinned controls, bit-exact at the same FAR, and nothing else.
`CONFIG_STATUS` is not a validity proxy in either direction — it has now been refuted twice,
in a spoiled state and in a good one. No comparison of captured content between rungs is
admissible.
