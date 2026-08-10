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
| **certificate schema** — versioned, per the `zynq-autoehw/docs/schema.md` policy | author → Claude | **shipped through 1.6** (multi-cell attestation + exact staging) |
| **known-answer fixtures** — what the gate must reproduce | author → Claude | **shipped and active** (address, feature, group, lifecycle, multi-cell and staging fixtures) |
| **verifiers** — run over emitted certificates + manifest | author → Claude | **shipped and active** (`host/verify_certificate.py`, `host/verify_data.py`) |
| `local_map` instantiation consuming certified classes | author → Claude | **active** (`local_map` 1.0.0 authority schema + independent verifier) |

The schema is written by the **consumer**, not the producer: the party that will read
certificates decides what a certificate must contain. To keep that from deadlocking
(the author cannot design a record for evidence they have not seen), Claude ships the
inventory below first — a menu of obtainable evidence, not a format.

## Claims inventory — what the gate can attest

Per specimen run: design source hash, Vivado version and part, the LOC-pinned site,
the tile and its `tilegrid` frame base, build seed, and the resulting bitstream hash.

Per feature under test: the **predicted bit assignment** — not a bit set — i.e. a
list of `(FAR, word, bit, expected_value)` where `expected_value` is 0 for a
`!`-negated segbit token and 1 otherwise, carried alongside the raw `F_B` segbit
coordinates (`docs/freeze_format.md` §5); the **observed** bit assignment from the
specimen pair; the verdict; and — for `ppip_bitless` — the negative assertion that
the observed diff is empty.

Per class run: `tp_count` / `fp_count` / `fn_count` as integers, the **explicit
membership** of the mine and holdout sets (the feature names in each, not just their
sizes), coverage (features attested ÷ class entries in the manifest), every
unattributed bit seen with whether the frozen mask lists it (see the artix7 4-bit
mask delta in `data/README.md`), and the pass/fail decision.

**Criterion, stated unambiguously:** the EP4CE6 shorthand "TP=1 / FP=0" is a *rate*
plus a *count* — recall 1.0 and zero false positives. As a record it is
`fp_count == 0 and fn_count == 0` over the holdout set, with `tp_count` equal to the
holdout size. Certificates should carry the counts and let a consumer recompute the
rate; a schema that stores only a rate cannot be audited.

Pinned in every certificate: `spec.sha256`, the sha256 of each frozen file consumed,
the manifest's `freeze_stamp`, and the tool versions. A certificate whose pinned
hashes do not match the current manifest is stale by construction.

## Historical Round 1 ask — completed

The three items below were the initial request. They are retained as the original
boundary contract, not as current work: the certificate schema is now 1.6, the data
and address verifiers are active, and the known-answer fixtures have caught real
producer and consumer defects.

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
   The arithmetic is now specified normatively in `docs/freeze_format.md` §5
   (block selection, `FAR = baseaddr + F`, `word = offset + B//32`, `bit = B%32`,
   `!` polarity, the already-applied word-50 skip, site → `SLICE[LM]_X{0,1}` prefix,
   and the constraint table with the commands to re-derive each constant). It is a
   shared **contract**; the fixture reimplements it from that text and the frozen
   data, never by reading `scripts/`. Pick a `CLBLL_L` LUT INIT bit, a `SLICEM`
   LUTRAM bit, an `INT_L` PIP **with at least one negated token**, and a
   `ppip_bitless` entry, and give the expected assignment for a named tile instance.
   Include the negative cases: the bit-less ppip, and a bit the frozen mask lists.
   This is where a silent arithmetic error would otherwise survive all the way into
   a wrong certificate.

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
- **Git:** branch `main` (the repo was created on `master` and renamed 2026-08-02
  before a remote existed, so nothing was rewritten). `origin` now exists. Commit
  locally without asking and **always ask the human before pushing**.
- **Handoff files:** author → Claude ships code + a `docs/*_handoff.md`; Claude →
  author ships `review.vN.txt` with file:line + evidence + a decisive test, kept
  untracked and deleted once resolved.
