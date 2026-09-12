# B2 — the §7 image package, submitted for the owner's review (2026-09-12)

Submitted at **`619b22b`** (`origin/main`). The report that describes that tree is the commit
after it, as the reporter's own note requires.

This document is the submission, not a verdict. It says what §7 asks, what exists for each item,
and — where an item rests on reading rather than on a check — it says that instead of claiming it.
**Nothing here asks for `board_ready`, the freeze, a ruling or board time.**

---

## 1. What is submitted

| | |
|---|---|
| image | `firmware/b2/bsp/out/b2_app.bin`, **`d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5`**, 114 708 bytes; ELF `7de96ed25e01199ad4405dcc59b2ec92140c27679710e6acfbbad158e4986cdc` |
| build evidence | `evidence/b2/build_evidence.json` — 20 sources, 6 BSP inputs, the pinned toolchain by digest, and **two clean builds agreeing bit for bit** on both the binary and the ELF |
| preregistration | `docs/b2_preregistration.md` (NOT frozen; `prereg.sha256` is null until S1, which is the owner's) |
| host tools | five, §7's list, below |
| B2Q's experiment | `evidence/b2/b2q_plan.json`, `evidence/b2/b2q_prediction.json`, pinned by the manifest at S0 |
| pin table | `manifests/b2_instrument_pins.json`, 71 files, plus B1's 105 |
| clean-tree proof | `evidence/b2/tests/test_report_2026-09-12T134616Z.json` — whole suite, **1 895 tests, 0 skips, 0 failures, 0 errors**, `proof_refusals: []` at HEAD `619b22b` |
| B2/B3 focused suite | **439 tests, zero skips** |

There is **no `manifests/b2_manifest.json` in the tree**. S0 generates it from the tree
(`b2_manifest.init`); it is not committed, so nothing in this submission is bound to a manifest
the owner has not seen produced.

---

## 2. §7's first list — the compatibility review (the owner's)

§7 names these as the owner's review, preceding `board_ready`. For each: where it lives, and what
automated evidence exists. **Items marked "reading" have no automated guard** — they rest on the
derivation from B1 and on the owner reading the source.

| §7 item | where | automated evidence |
|---|---|---|
| the wire contract | `firmware/b2/b2_wire.c` (derived from B1's), the twin's `wire` mode | `tests/test_b2_wire.py` (6): the bytes the image emits validate under the instrument's own validator — **common envelope only**, which is why `b2_records` exists for the B2 fields |
| the settle poll | `firmware/b2/b2_app.c`, inherited from B1's ARM path | **reading** — the ARM/settle path is verbatim-derived, not re-tested here |
| the audit service | inherited; exercised end to end | `tests/test_b2_e2e.py` — the modelled session serves each candidate's **real** staging streams and readback frames and the instrument's audit gate recomputes every hash |
| the MMIO allowlist against the B1 RTL | unchanged RTL | §7 itself says the B1 check stands; the carrier bitstream digest is B1's, pinned through `carrier_lineage` and re-verified on every `b2_manifest.verify` |
| the DMA order | inherited | **reading** |
| no ICAPE2 | — | **reading**. No ICAPE2 symbol appears in `firmware/b2/`, but there is no guard asserting it |
| no SLCR write | `b2_app.c:152` declares `SLCR_PSS_IDCODE` READ ONLY and only reads it | **reading** — no automated guard forbids an SLCR write |
| the watchdog gating | `b2_app.c` (D-s1, 30 s, flag-gated) | `b2_runner` refuses a preflight whose L6 manifest does not carry the instrument's watchdog pins; the firmware side is **reading** |

The image's relationship to B1 is recorded in `firmware/b2/IMPORT.json`: **10 files verbatim** from
the instrument at `689dde1`, **3 derived** (`b2_app.c`, `b2_wire.c`, `p3_data.h`), each derived
file required to exist and to DIFFER from its base.

---

## 3. §7's second list — the B1 guards, re-established

These §7 requires **before the package is submitted**. Each is a test, named.

| guard | where |
|---|---|
| verbatim imports | `test_b2_leakage.test_every_verbatim_import_is_the_instrument_s_byte`; `…test_every_derived_file_exists_and_differs_from_its_base`; `…test_the_import_table_names_the_archived_instrument`; `…test_the_application_records_its_derivation` |
| header without tables | `test_b2_leakage.test_no_forbidden_token_in_the_headers_data`, `…test_the_header_is_fresh_from_its_generator` (forbidden: the LUT keys, lengths, bits, mutation bits, operator digest, the tile names, `SLICE_X`, `local_map`, `certificate`) |
| source include scan | `test_b2_leakage.test_the_search_unit_includes_nothing_else`, `…test_no_forbidden_token_in_the_b2_sources` |
| binary scan, extended to the certificate and the oracle rendering | `test_b2_leakage.test_the_image_carries_no_forbidden_token`, `…test_the_image_declares_the_engine_and_the_map` |
| C = Python twin | `test_b2_twin.py` (9): the RNG equals the instrument's, the pair seeds are the frozen rule, the universe mask and target, F1 over both vector sets, both arms over the budget grid, every session pair at the planned budget, and the session deltas ARE the prediction |
| the real application off-board | `test_b2_hostapp.py` (16): the real application compiled and executed on the host, refusals at each bracket and at a generation close, an unacknowledged record, a page outside the experiment, every emitted frame validating |
| wire contract | `test_b2_wire.py` (6) |
| fail-closed adjudication | `test_b2_records.py` (49), `test_b2_adjudicate.py` (84), `test_b2_runner.py` (52) |
| pins | `test_b2_pins.py` (6) and the table itself |
| the map is the committed B1 map; the seed exclusion covers every archived run | `test_b2_leakage.test_the_compiled_map_is_the_committed_b1_map`, `…test_the_seed_exclusion_covers_every_archived_run` |
| the operator reads only the column | `test_b2_leakage.test_the_operator_reads_only_the_column` |

---

## 4. The five host tools

| tool | what it establishes | tests |
|---|---|---|
| `host/b2_records.py` | every B2 field and cross-record binding the instrument's validator ignores by design | 49 |
| `host/b2_adjudicate.py` | per record, F1 recomputed **from the served readout** and the PL's additive known answer (a contradiction is a KILL); then the stateful replay of every parent draw, move, genome, counter, selection, champion and `state_sha256`; then the pinned prediction and, at run scope only, the pooled primary | 84 |
| `host/b2_runner.py` | the fail-closed preflight, the two profiles, the ruling and board authority, and the session verdict that COMPOSES the instrument/evidence contract with the record replay | 52 |
| `host/b2_pins.py` | the pin table of the whole decision surface — 71 files including what the pinned harness compiles and runs, plus B1's own 105 | 6 |
| `host/b2_test_report.py` | the clean-tree proof, with snapshots before and after the run and a strict log contract | 35 |

Supporting: `host/b2_modelled_session.py` drives a whole B2Q session through the instrument's real
host stack and the production exporter (`test_b2_e2e.py`, 15).

---

## 5. What the offline lifecycle establishes — and what it does not

`tests/test_b2_e2e.py` runs, offline and with **no replay double and no stored-verdict double on
the positive path**: a modelled B2Q session → the runner's own `judge_session` → **PASS** (zero
findings, zero kills, a rate measured from the session's own timing, a policy verified by the
instrument's check) → `qualify` **accepts** and derives the calibration → `pin_plan` → a
**fresh-process** `verify` returning stage S3. Eleven negatives are then applied one at a time to
that passing evidence.

**It establishes that the checks can be satisfied, not anything about silicon.** The model stands
in for a board; the rulings in it are inert documents that authorise nothing; no board was
contacted. In particular the modelled rate (4 490.86 /h) is an artefact of a virtual clock and
**must never be used as a calibration** — measuring the real one is what B2Q is for.

---

## 6. What is NOT done, not claimed, and not asked for

1. **No board session has been run and none is authorised.** Every fixture is the model standing
   in for a board.
2. **The B2 (map-utility) profile has no modelled demonstration.** B2Q has one; a B2 slice at
   budget 600 is thousands of records and belongs in a one-off demonstration. The runner's B2 path
   is covered by unit and refusal tests and by an independently reviewed non-first-slice run, not
   by an end-to-end modelled session.
3. **The compatibility items marked "reading" in §2 have no automated guard.**
4. **The preregistration is not frozen and the image is not `board_ready`** — both are the owner's.
5. **B1Q's transport stop-loss is unresolved and its root cause unattributed** (preregistration
   §6). It bears on scheduling B2Q, not on this package's contents.
6. The ruling texts in `b2_runner` (`whole-of-run B2 map utility`,
   `whole-of-run B2 image qualification and calibration`) are **proposals**. The runner refuses any
   other text, so they must agree with what the owner intends to sign before a session is possible.

---

## 7. What the owner is asked

1. To review this package under §7 — the compatibility list, the guards, the five tools, the
   clean-tree proof, and B2Q's pinned experiment.
2. To say whether the ruling texts above are the ones to be signed.
3. Nothing else. `board_ready`, the freeze, the rulings and board time are not requested here.

## 8. Where to look

- `docs/b2_package.md` — the running record, newest first, of every review round and correction.
- `docs/b2_architecture.md`, `docs/b2_preregistration.md` — the design and the frozen experiment.
- `evidence/b2/` — the gate, the plan and prediction, B2Q's pinned documents, the build evidence,
  every review's artifacts as received, every correction's acceptance, the modelled lifecycle, and
  the test reports with a README saying which is cited and which are superseded.
- `git log --oneline 619b22b` — each correction is its own commit, and each review document was
  committed as received before the code that answers it.
