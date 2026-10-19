# B4 — the exposure settlement (the owner's ruling of 2026-10-19 on the prior production-seed exposure)

Host-only. Delivered for the owner's review on `b4-prework`; local commits only (not pushed, not merged; `main` stays
`d5bf815`). The ruling is copied unchanged as `owner_ruling_2026_10_19.md`. This unit derives NO new exploration set: the
label `b4-sim-3` is reserved and never evaluated here, not even for a smoke test; the S = 32 run is a separate authorisation.

## 1. What was settled

| ruling | done here |
|---|---|
| §1 retire `b4-sim-1` / `b4-sim-2`; reserve `b4-sim-3`; keep the anchor, the formulas, the thresholds, τ, the grid unchanged | `b4/host/b4_seeds.py`: `RETIRED_LABELS`, `EXPLORATION_LABEL = "b4-sim-3"`, `check_label_not_retired` (the new-production-derivation path only); `b4/host/b4_sim.py`: the pre-flight refuses a retired label before any tree is read and before any master is formed, `Batch.init` checks again; the CLI's help names the retirement; `b4/host/b4_thresholds.py`: `anchor.exploration_label = "b4-sim-3"`, `anchor.retired_exploration_labels`, pinned to §9.2's text; `docs/b4_architecture.md` v0.1.16 (§9.2's formula line, the settlement paragraph, the revision note, §13, §14). The anchor formula, the hypothesis digest, every threshold, τ, the grid and the control formulas are unchanged (the thresholds test holds every number to the document) |
| §2 originals preserved; recovery distinguished from execution; seed-only reconstruction authorised | `evidence/b4/unit_2b4a_repair_2026_10_18/exposure/` untouched (22 records, byte-identical; checked by the owner's previous reviews and by `reconstruction_comparison.json`'s digests). `reconstruct_exposure.py` derives SEEDS ONLY from the historical derivation code (`edfc93c:b4/host/b4_seeds.py` and `b4_rng.py`, extracted from git, blob ids and digests recorded) and the historical exclusion contents; it never runs the engine, the fabric, the cartographer, K9 / K10 or a statistic; every output is marked reconstructed with the reconstruction time and its historical inputs |
| §3 the finite envelope fixed before deriving; the preserved records checked against it; any mismatch stops the unit | section 2 below (the recipe inventory from historical source) and section 3 (the comparison: 22 / 22 agree). The script stops by name on a mismatch, on a changed source digest, on a different anchor, or if `evidence/b4/sim/` exists |
| §4 a versioned receipt under `evidence/b4/` outside the sim namespace; the loader reads and validates it, pins its digest, pools both positions, binds it into the manifest / checkpoints / verification; retired labels refused before derivation, still ingested from archives | `exposure_receipt.json` (schema `b4_exposure_receipt 1.0.0`); `b4_seeds.read_exposure_receipt` (missing / unreadable / re-hashed / malformed → `ExclusionSourceRefusal` by name), `receipt_findings` (total), `EXPOSURE_RECEIPT_SHA256` pinned; `load_exclusion_set` pools the receipt's values (`pair_seeds` screens both positions against the one pooled set); the receipt is a `ROOT_INPUT` of the harness (its pinned digest checked at the pre-flight, held at every checkpoint → `input_drift`); `seeds.json` 1.2.0 and the manifest name it (path, digest, count); `manifest_findings` and the verifier's linkage bind it to the pinned constants; the registry still reads a `b4-sim-1` / `b4-sim-2` archived record (1.1.0 and 1.2.0 forms) |
| §5 bounded implementation, tests with mechanics schedules and hand-made receipts, affected mutants, IMPORT, README | sections 4 and 5 below |
| §6 exploration remains separate | nothing of `b4-sim-3` exists; the receipt is committed and bound before any such derivation could be asked |

## 2. The recipe inventory (from historical source, not from re-running old suites)

Derivation code: `edfc93c:b4/host/b4_seeds.py` (git blob `daae6d5a…`) with `b4_rng.py` (blob `ec59a60d…`, unchanged since).
`master = int.from_bytes(sha256(label|anchor)[:4])` (32-bit); pairs by `Rng(master).next32()` in order, a draw skipped when either
value is pooled, seen or equal. The anchor `59948f9b…` (the ruling's; equal to `hy.HYPOTHESIS_SHA256` now). The historical
base pool P0 = B2's frozen copy ∪ `B4_EXPOSED_VALUES` (unchanged since `edfc93c`) ∪ every value of the 38 sources (digests
unchanged; the historical loader re-verifies them) — 2 093 values, with NO exploration namespace (every exposing tree
started with an empty registry). An archived set contributes its master and every pair value to the next derivation in the
same tree (`sim_registry` at `edfc93c`).

Call sites at `edfc93c` that derive a production set: `b4_sim.Batch.init` only (`b4_sim.py:252–253`). The seeds unit tests
use `b4-fake-*` labels and a fake anchor throughout (checked at `8939fb9` and `edfc93c`). Every other `master_seed` /
`pair_seeds` call in the repository is B2 / B3 code with its own labels.

Batches per fresh hermetic tree in `edfc93c:b4/tests/test_b4_sim.py` (every test class builds its own tree; `tearDown`
commits each batch, so consecutive batches pass the clean-tree check and see the previous sets in the registry):

| class | batches reaching a derivation | sets |
|---|---|---|
| `Preflight` | 0 (every call is refused before derivation) | — |
| `CompleteBatch` | `b4-sim-1` S=2 (setUpClass), then `b4-sim-2` S=2 with the first in its registry | sim-1 set 1; sim-2 set 1 |
| `InvalidStops` | 7 × `b4-sim-1` S=2 (the drift batch derives before its drift) | sim-1 sets 1–7 |
| `IncompleteStops` | 3 × `b4-sim-1` S=2 | sim-1 sets 1–3 |
| the author's smoke test (CLI, default-named directory) | 1 × `b4-sim-1` S=2 | set 1 |
| the owner's interrupted re-run (`b4sim_rvf1ws_h`) | 6 × `b4-sim-1` (t001–t005 returned, t006 interrupted after its seeds) | sets 1–6 |

Mutants of the `cdf2c53` battery that run a batch: M1, M15, M16, M18–M23, M32. Only **M1** changes a derivation (the
registry's values not pooled): its named tests run `CompleteBatch` — set 1 of `b4-sim-1` (unchanged: the registry was empty)
and `b4-sim-2` drawn against P0 alone (the variant). **M32** (a fixture hypothesis in the formal CLI path) left
`hy.HYPOTHESIS_SHA256`, the anchor the master is derived from, untouched: its batch is set 1 again. M3 / M7 / M17 touch a
seed rule but run no batch. No other historical edit or call site affects a derivation.

Set k of a label depends only on sets 1 … k-1 of that tree (the stream's next two admissible pairs), never on the order of
tests. **The envelope** is therefore V1–V7 (`b4-sim-1` sets 1–7), V8 (`b4-sim-2` set 1 against {sim-1 set 1}), V9 (`b4-sim-2`
under M1, against P0 alone) — the ruling's §3 envelope exactly; the audit found no additional seed-affecting branch.

**Not covered, and not recoverable:** the author's development runs of the tests and of the battery before `edfc93c` /
`cdf2c53` (the runs with 217 and 218 tests) used uncommitted versions whose recipes are not recoverable; the number of
historical attempts, and whether any deleted outcome was inspected, cannot be shown. The envelope covers the committed
recipes; it is not a complete execution history.

## 3. The comparison (`reconstruction_comparison.json`)

22 preserved `seeds.json` records (7 distinct digests, 6 distinct sets) against their recipes by (label, registry depth):
**22 / 22 agree** — master, both pairs, the anchor, 38 sources, and the recorded `pooled_total` (2 093 for depth 0, then
+5 for set 1's master and values, +4 per further set). The observed variants are V1–V6; V7, V8 and V9 are
`reconstructed_recipe` (no record survives). V8 and V9 draw the same pairs (the `b4-sim-2` stream's first two admissible
pairs are not in set 1 of `b4-sim-1`); both are kept with their own provenance.

The one correction the comparison forced on the reconstruction itself: set 1 is drawn against P0 alone — the master enters
the pool only through the registry of a later batch (the first run of the script assumed the master pooled from the start,
disagreed with every depth-0 record on `pooled_total` by one, and stopped by name; the script was corrected, not the
records).

## 4. The receipt (`exposure_receipt.json`, sha256 pinned in `b4_seeds.EXPOSURE_RECEIPT_SHA256`)

66 pooled integers: 2 masters, 32 pair values (9 variants × 4, V8 = V9), 32 control seeds (X and D per drawn pair), none
already in P0. Classes: 24 `observed`, 9 `reconstructed_recipe`, 1 both (the `b4-sim-1` master: observed in V1–V6, drawn
again by V7), 32 `conservative_superset` (the control seeds: derivable from every drawn pair; whether a run reached the X / D
arm is not shown — the preserved run directories hold no `controls.json`). Each value carries its origins (variant and
position); duplicates' provenance is kept although the integers are deduplicated. The receipt records the historical inputs
(commit, blobs, anchor, the base pool's count and digest, the 38 sources' digests), the envelope and its rationale, the
not-covered statement, the 22 records with their digests and verdicts, and its limits.

After the receipt the pooled exclusion set is 2 093 + 66 = 2 159 values; a `b4-mech-*` fixture batch records it in
`seeds.json` and the manifest and holds it at every checkpoint (section 5's tests).

## 5. Validation (clean committed tree, HEAD `8955647`; files beside this README)

The three runs started together on the committed tree; no tool file, document or receipt was edited during them. Each raw
file has a three-line header (HEAD, command, UTC time) and is otherwise unedited.

| file | command (from `/home/test/zynq_fabricmap`) | result |
|---|---|---|
| `tests.txt` | `python3 -m unittest -v` over the 20 `b4.tests.test_b4_*` modules | **Ran 254 tests … OK**, exit 0 (the production-derivation guards of every harness test class: 0 calls) |
| `mutants.txt` | `python3 evidence/b4/unit_2b4a_repair_2026_10_18/b4_2b4a_mutants.py evidence/b4/unit_2b4a_exposure_settlement_2026_10_19/mutants.txt` | **75 / 75 killed** in 850 s; no `SURVIVED`, `BASELINE-NOT-GREEN` or `EDIT-MISS` line |
| `import_check.txt` | `python3 evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py` | 49 entries, every digest equal; no tracked file under `b4/` without an entry |

The battery is the shared 2b-4a battery, now 75 mutants: M35 re-targeted to the moved `init` line (it would otherwise be an
`EDIT-MISS`); M68–M75 one per settlement contract — the receipt not pooled (M68), its digest not held (M69), a retired label
accepted by the pre-flight (M70), the receipt not a root input / not held at the checkpoints (M71; the hermetic trees copy
the receipt in its own right so this mutant is killed by the checkpoint tests, not by a missing file), the manifest validator
not binding it (M72), the verifier's linkage not binding it (M73), the thresholds table naming a retired label (M74), a seeds
record's receipt reference not held (M75). 9 / 9 on the dry run of the new and re-targeted mutants, 75 / 75 on the full run.

Tests use the mechanics schedules (`b4-mech-*`, exposed values only) and hand-made receipts / records; the only values of a
retired label that appear in a test are the OBSERVED ones read from the receipt (no derivation function is called — the
registry test mocks both to fail). No test creates a batch under `b4-sim-3` or a gate label.

**Status.** `b4-prework`: … `82e863e` (2b-4a accepted), the settlement `8955647` + this verification commit; local only —
not pushed, not merged (the earlier push permission does not extend to this unit); `main` is `d5bf815`. Delivered for the
owner's review. Still not authorised: the S = 32 `b4-sim-3` exploration, the formal gate tool and run, units 2c / 2d, the
full proof, push / merge, procurement and board work.

## 6. What this does not claim

The receipt makes the known and the reconstructable exposure excluded. It does not make the historical exposure record
complete, does not recover any deleted readout, manifest or verdict, and does not show that no deleted outcome was looked
at. A new label does not guarantee unseen or independent data: masters and seeds are 32-bit values in one space, which is
why the exclusion is by value and why the receipt exists. `b4-gate-1` remains reserved and unexecuted. Nothing here is an
exploration result, a gate result or a statement about silicon.
