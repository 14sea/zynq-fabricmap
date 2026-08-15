# Phase 1, second round: the envelope fix changed nothing at all

The ruled fix was applied exactly: every FAR now gets its own complete transaction —
`SYNC → RCFG → FAR → FDRO → CFG_OUT → DESYNC` — before the next FAR begins, `JSHUTDOWN` is
issued once per session between envelopes, and the STAT and RCRC blocks are closed the same
way because the first `CFG_OUT` of the script belongs to STAT. The emitted script is
4 SYNC / 4 DESYNC / 3 CFG_OUT. `envelope_violations()` reads the words that would actually
be shifted and `build_tcl()` refuses to emit an unclosed envelope; the mutation gate kills
both dropped-DESYNC mutants by that behaviour, not by a string search.

Then the board was power-cycled, `carrier_eco.bit` (`78eff0cb…`) was loaded onto an empty
PL (plmark `18cbffcbbcf79a2f`), and A20 and A21 were read in one session.

## The result

| | |
|---|---|
| `0x00400A20` | 101 of 101 words identical to `carrier_eco.bit`, ECC consistent, both expected bits at their exact positions |
| `0x00400A21` | all zero — differs from the expected frame at words 50 and 51, the ECO bit and its ECC |

Which is, to the bit, the previous run:

```
run A (shared envelope, boot 18cbfeacd7296aa9)   run B (per-FAR envelopes, boot 18cbffcbbcf79a2f)
0x00400A20  all 202 words identical between runs
0x00400A21  all 202 words identical between runs
CONFIG_STATUS 0x46107ffc                          CONFIG_STATUS 0x46107ffc
```

**The shared-envelope explanation is refuted.** It was the most economical reading of the
first miss, it matched a rule this repository had already paid for, and it is wrong: two
different script shapes on two different boots produced 404 identical words. Whatever
decides the A21 result, the envelope structure is not it.

What survives is stronger than before, because it now has a replicate: a JTAG readback of a
configured, JSHUTDOWN'd device reproduces `0x00400A20` **exactly and deterministically**,
including two bits that are set in the loaded bitstream and clear in the base. And the A21
miss is not noise either — it is the same all-zero frame twice.

## What is still open, and what would decide it

Two readings remain, and this run cannot separate them:

1. **the second read of a session is not trustworthy**, whatever the envelopes look like;
2. **this address reads back all-zero**, and would do so first in a session too.

The experiment that separates them is one read of `0x00400A21` **alone**, or A21 before A20,
on a freshly loaded board. It is cheap, read-only and disposable. It was not run: the
authorisation for this round says stop on any mismatch, and this is a mismatch.

A third possibility deserves recording rather than testing on the board: the ECO's third bit
is at A21 **according to the local map and the bitstream parser**, and both were checked
file-to-file. A20 matching exactly proves that mapping is right for A20; it proves nothing
about A21. If A21 turns out to read all-zero even when read alone, the parser's placement of
INIT[35] is the next thing to doubt — offline, against the raw bitstream, not on silicon.

Phase 1's success condition — both frames 101/101, all three bits hit — is **not met**, so
Phase 2 stays unauthorised.

## A label discrepancy in this record, stated where a reader meets it

`record.json` here says `probe_jtag_config_read.py/1.0.0`. The sequence it ran is the
per-FAR envelope shape described above; the version string had simply not been bumped when
the behaviour changed, so this run and the shared-envelope run of
`../jtag_eco_control_2026_08_15/` both claim 1.0.0 while shifting different words. The
record is not re-taken — the words it holds are what the board returned — and the tool is
now **2.0.0** for the per-FAR shape, so later evidence distinguishes the two by identity as
well as by directory. The sequence each run actually shifted is in its own `record.json`
under `sequence`, and in `record.tcl`.
