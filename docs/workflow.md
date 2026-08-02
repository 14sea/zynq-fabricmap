# zynq-fabricmap — division of labour & workflow

Two AIs with a human relay, same as the sibling repos. This file is the contract for
**this** repo and overrides the default split where it says so. Base contract:
`zynq-autoehw/docs/workflow.md` (its §"Division of labour is not fixed" is what
authorises the inversion below).

## Roles for this repo

| Who | Owns (writes, and is accountable for) | Does not write |
|---|---|---|
| **Claude** | the Vivado-facing infrastructure: `data/subset_spec.json` + `scripts/extract_prjxray_subset.py` (freeze), the specimen generator and bitstream differ, the prediction gate and its TP/FP accounting, emitted certificates, `docs/freeze_format.md`, board work when it starts, git commits | the `local_map` schema, the verifiers that judge its output, the known-answer fixtures |
| **Author (ChatGPT)** | the consumer side: the certificate schema, the `local_map` instantiation, host verifiers that run over Claude's emitted artifacts, and known-answer fixtures the gate must reproduce | `data/**` (never hand-edited), the extractor, the specimen harness, the gate |
| **Human** | the relay; scope and priority calls; approves every push | — |

**Why inverted here.** The default (author writes code, Claude gates and boards)
assumes host-side logic. Extraction + per-bit-class certification is a Vivado
specimen-diff activity end to end; in the M1 engineering addendum five of six
blockers over six rounds were invisible on the authoring side. Keeping the default
split for this drop would make that ratio worse.

## The rule that makes the inversion safe

Inverting the split moves Claude from gatekeeper to author, so the writer/verifier
separation has to be re-established on the other side, deliberately:

1. **The author's verifiers must be able to fail Claude's artifacts, and Claude runs
   them.** A gate written by the same party that wrote the thing under test is not a
   gate.
2. **Verifiers and fixtures are written against `docs/freeze_format.md` and the
   certificate schema — not against Claude's source.** Reading the implementation to
   make a fixture pass destroys the independence that justifies the round trip.
3. **Claude never edits a fixture to make the gate pass.** A disagreement between
   fixture and gate is a review round (`review.vN.txt`), and the losing side is
   whichever one the frozen data contradicts — decided by a command, not by seniority.
4. **Neither side's "done" is trusted** (base contract rule 3), and every claim in a
   commit message is backed by a command actually run that session.

## What crosses the boundary

| artifact | direction | status |
|---|---|---|
| `docs/freeze_format.md` — spec/manifest contract, incl. the `certification` slot and its staleness rule | Claude → author | **shipped** (`28363a4`) |
| `data/MANIFEST.json` + `data/prjxray/**` — the frozen subset, self-verifying via `--verify` | Claude → author | **shipped** (46 files, 10,896 classified features) |
| **claims inventory** — what evidence the gate can physically produce (below) | Claude → author | in this document |
| **certificate schema** — versioned, per the `zynq-autoehw/docs/schema.md` policy | author → Claude | **not started** |
| **known-answer fixtures** — what the gate must reproduce | author → Claude | **not started** |
| **verifiers** — run over emitted certificates + manifest | author → Claude | **not started** |
| `local_map` instantiation consuming certified classes | author → Claude | after the first certificate |

The schema is written by the **consumer**, not the producer: the party that will read
certificates decides what a certificate must contain. To keep that from deadlocking
(the author cannot design a record for evidence they have not seen), Claude ships the
inventory below first — a menu of obtainable evidence, not a format.

## Claims inventory — what the gate can attest

Per specimen run: design source hash, Vivado version and part, the LOC-pinned site,
the tile and its `tilegrid` frame base, build seed, and the resulting bitstream hash.

Per feature under test: the **predicted** bit set (from the frozen segbits + tilegrid
address arithmetic, expressed both as `frame_offset_bitoffset` segbit coordinates and
absolute `FAR`/word/bit), the **observed** diff bit set from the specimen pair, the
verdict, and — for `ppip_bitless` — the negative assertion that the observed diff is
empty.

Per class run: TP / FP / FN counts, the mine/holdout split, coverage (features
attested ÷ class entries in the manifest), every unattributed bit seen (with whether
the frozen mask lists it — see the artix7 4-bit mask delta in `data/README.md`), and
the pass/fail decision against the TP=1 / FP=0 criterion.

Pinned in every certificate: `spec.sha256`, the sha256 of each frozen file consumed,
the manifest's `freeze_stamp`, and the tool versions. A certificate whose pinned
hashes do not match the current manifest is stale by construction.

## Round 1 ask (what the author writes next)

1. **`certificate` schema, `schema_version` 1.0.0**, drawn from the claims inventory,
   following the MAJOR/MINOR policy of `zynq-autoehw/docs/schema.md`. It must make
   the falsifier explicit: what a *failed* certification looks like as a record, not
   only a passing one.
2. **A verifier over `data/`** that reproduces, independently of Claude's extractor:
   the manifest's per-file hashes, the per-class entry counts from the frozen `.db`
   files and the spec's regexes, and the `unclassified == 0` invariant. If it agrees
   with `--verify` it costs nothing; if it disagrees, one of the two is wrong and
   that is exactly the finding worth having.
3. **Known-answer fixtures for the address arithmetic** — the highest-value item.
   Pick a small set of features (a `CLBLL_L` LUT INIT bit, a `SLICEM` LUTRAM bit, an
   `INT_L` PIP, a `ppip_bitless` entry) and compute, from the frozen `segbits_*.db` +
   `tilegrid.json` alone, the expected absolute bit address for a named tile
   instance. That is an independent reimplementation of the arithmetic the harness
   depends on, and it is where a silent error would otherwise survive all the way to
   a wrong certificate. Include the negative cases: a bit-less ppip, and a bit that
   the frozen mask lists.

Fixtures do **not** require Vivado: everything above is derivable from the frozen
data. If the author does have Vivado available, a gold bitstream pair for one of the
fixtures is welcome as a bonus, but the assignment is deliberately written not to
depend on it — Claude runs Vivado 2025.2 locally
(`~/Xilinx/2025.2/Vivado/settings64.sh`) and owns every specimen build.

## Gate order on receiving a drop — cheapest disqualifier first

1. `scripts/extract_prjxray_subset.py --verify` — seconds; if the freeze drifted,
   nothing downstream means anything.
2. Run the author's verifier and fixtures against the current artifacts.
3. Read the diff.
4. Vivado specimen build (minutes) — only for changes that reach the harness.
5. Board — nothing in this drop reaches a board; routing-class silicon work waits for
   sacrificial hardware.

## Standing rules inherited unchanged

- **Isolation is absolute.** Sibling repos (`zynq-autoehw`, `zynq-xpart`, `zynq-ehw`,
  `Cyclone_CRAM_Mapper`, `prjxray-db`) are read-only sources; files are copied in,
  never referenced across trees and never modified in place.
- **`data/prjxray/**` is verbatim.** It is regenerated by the extractor or not at
  all. Any transformation lives in a derived artifact.
- **Git:** branch `main`, commit locally without asking, **always ask the human
  before pushing**. No remote exists yet — creating one is a human decision.
- **Handoff files:** author → Claude ships code + a `docs/*_handoff.md`; Claude →
  author ships `review.vN.txt` with file:line + evidence + a decisive test, kept
  untracked and deleted once resolved.
