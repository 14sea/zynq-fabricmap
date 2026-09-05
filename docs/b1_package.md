# B1 — the pre-board package, v2, delivered for the whole-package review (2026-09-05)

> **HOST-ONLY. DRAFT / NO BOARD RULING.** Delivered at "B1 ready for the board" under the
> owner's ruling of 2026-09-05 (`docs/autonomous_cartography_roadmap.md`; the
> authorisation of the same day) and STOPPED here. Nothing is frozen; the image is not
> `board_ready`; the carrier is not `qualified`; no ruling exists; no board contact, power
> cycle, image load or serial port has been touched. The instrument (`zynq-psoracle`
> `689dde1`) is unchanged, bit for bit. Local commits only; nothing pushed until this review.

## 0. History: the first package and why it failed

The first B1 package (`4c49b25` + `fbcdf97`, local, never pushed; image `7bc86a3f…`) was
reviewed by the owner on 2026-09-05 and **FAILED — do not push / freeze / sign / board**.
The image is recorded as **WITHDRAWN / DEFECTIVE / NO-RUN** (`manifests/b1_manifest.json`
`history`); it was never loaded on any board. The five blockers and what replaced them:

| blocker | v2 |
|---|---|
| 1 — circular "blind" mapping: the P3 carrier's gate requires the readout to equal the host-signed expected tables, so every observation the cartographer learned from was pre-certified by the ground truth | the **B1 carrier** (`rtl/b1/`, `SEMANTIC_GATE = 0`, read-only `VARIANT`), the **B1 signer** (zero tables, semantic oracle disarmed), the **B1 validator** (rule iii-B1 refuses non-zero tables) — `docs/b1_carrier_contract.md`; host-verified RTL diff, benches, Vivado build, MMIO check — `docs/b1_carrier_qualification.md`; a qualification session under its own ruling before any mapping |
| 2 — the opening baseline was recorded before the cartographer was initialised (its block hashed a zero struct) | the orchestrator (`firmware/b1/b1_orch.c`, reference `b1_carto.session_run`): init + bind → opening → probes → closing; an unscored candidate ends the epoch; C = Python (`tests/test_b1_session.py`); the adjudicator names the defect at seq 1 if it ever recurs |
| 3 — the adjudicator was not fail-closed | binding to the manifest's own hash, the instrument commit, the carrier hash and VARIANT, a qualified carrier; the probe sequence a finding per record; per-record prediction comparison; one `b1_findings()` per preregistration condition, each with a negative test (`tests/test_b1_adjudicate.py`) |
| 4 — map v2 semantics (derived polarity; no confidence snapshots; no separate confirmation evidence; board map and verifier judgement merged; no real schema validation; "holdout" misnamed) | `schemas/self_map_v2.schema.json` revised: no polarity, observed transition, code mask + confirm seq evidence, binding; confidence snapshots provisional / confirmed; board-authored map and verifier report are two documents; JSON-schema validated (draft 2020-12) with "no validator" a finding; "holdout" → reporting strata A / B |
| 5 — pins (IMPORT.json targets missing; build evidence from a dirty tree; no B1 test report; no fabricmap pin table) | `IMPORT.json` derived entries; `manifests/b1_instrument_pins.json` (`host/b1_pins.py`, 85 files, not self-referential, verified by runner and adjudicator); build evidence and test report from the clean tree (§9) |

Plus, ordered by the owner: a real **end-to-end modelled 335-record session** through the
instrument's host stack and validators (§2).

## 1. Hashes and data flow

| artifact | sha256 / value | role |
|---|---|---|
| `manifests/b1_manifest.json` | (committed; `prereg.sha256` null, `board_ready` false, `carrier.qualified` false) | the stage's pins |
| B1 carrier `builds/b1/b1.bit` | `d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f`, 2 083 858 B | committed (as the instrument commits its carrier); build record `5da31443…`, carrier manifest `2e9de7c7…`, isolation `ada2594e…`; WNS +7.993 ns, ICAPE2 0, isolation passed |
| B1 image `firmware/b1/bsp/out/b1_app.bin` | `54b006636fe07d1b52784e636452cfbd1191407a100699a7666c57b96ba4d6c8`, 114 708 B | rebuilt byte-identically by `firmware/b1/bsp/build.sh`; not committed; hash-checked by the runner |
| `evidence/b1/build_evidence.json` | pinned in the manifest | two clean builds equal; the sources, the embeddedsw inputs, the compiler, all by hash; `worktree_dirty` and `head` recorded |
| B1 signer `host/b1_sign_arm.py` | pinned in the manifest | zero tables; `probe` / `sign_genome` / `provision` only — no host-attested `sign` |
| `firmware/b1/p3_data.h` | generated (`host/gen_b1_data.py`), no operator tables | the cartographer's only knowledge of the fabric: 292 addresses + base frames |
| `firmware/b1/IMPORT.json` | 14 instrument files at `689dde1` by hash; 3 derived | the verbatim imports; `b1_app.c`, `b1_wire.c/h` derived from `p3_app.c`, `p3_wire.c/h` |
| `manifests/claimb_round1prime_instrument_pins.json` | 128 files | the read-only instrument binding, reused |
| `manifests/b1_instrument_pins.json` | 85 files | every adjudication-critical fabricmap file |
| `evidence/b1/plan.json` | `4bc2e9b91f1d822d52017f6742caca50a64a5858c0f9c36a1c8be0b74e75cfa6` | seed 1 123 460 948, budget 333, 335 records, every seq audited, 9 048 frames, budget 37, deadline 1 048 s |
| `evidence/b1/prediction.json` | `fc1d41ce6652dc95ff3ac1804be383cf55b3cd70fce4ac74b6621f64bc507419` | the 333 probes (`f351475c…`), every record's content-level block, the map content (`7e1e7702…`), the expected score |
| universe digest | `895baf85…` | in the header, the image and the IDENT |
| ground truth `local_map.json` | `56f2b9e8…` | held back from the executable; the verifier's only input beyond the records |
| `schemas/self_map_v2.schema.json` | (committed) | the board-authored map the adjudicator expands and validates |

Data flow, one session: identity page (seed, budget, flags) → IDENT 1.4.0 (carto-v1,
universe, budget, carrier hash, VARIANT; verified before IDENTACK) → cartographer init +
bind → per record: SIGNREQ (genome) → host gate + **zero-table** signature → stage / DMA /
readback → signed ARM → sweep → raw readout + counters → REC 1.2.0 with `carto` (phase,
changed sample, `content_sha256`, `map_sha256`) → audit pull (every record) → … → closing
baseline (its carto block = the final commitment) → closing unsigned control → TERM.
Afterwards, from the files as written: the B1 validator over the instrument's → the
autonomy replay → the verifier → `self_map_v2` + the verifier report.

## 2. Autonomy, noninterference and leakage — the proofs

| claim | proof | where |
|---|---|---|
| nobody attests semantics before the measurement | RTL: the gate ARMs on zero-table payloads and never faults on the readout (bench); the signer cannot compute expected tables (a call is a refusal) and answers only zero tables; the validator refuses any non-zero table; RTL diff = parameter + VARIANT | `tests/test_b1_carrier.py`, `test_b1_signer.py`, `test_b1_records.py`; `docs/b1_carrier_contract.md` |
| the board chooses; the host only audits | the replay: the reference, bound as the board was, fed the records' readouts, reproduces every probe genome and every record's content / map hash; a foreign probe, a lying hash, the init-order defect are HOLDs named by seq | `host/b1_adjudicate.py`; `tests/test_b1_adjudicate.py` |
| no table reaches the executable | header generator + token scan; source include scan; binary scan (no LUT key, no `P3_LUT`, no arm name; `carto-v1` and the universe digest present); verbatim imports by hash | `tests/test_b1_leakage.py` |
| it measures, it does not recall | permuted fixture → 292/292 vs the permutation, < 10 vs the truth; address-only baseline precision < 0.2 vs 1.0 | `tests/test_b1_leakage.py`, `host/b1_model.py` |
| the image runs the same algorithm and the same session order as the reference | C twin = Python over four fixtures, six budgets, unscored probes; session mode: init → bind → opening → probes → closing, unscored ends the epoch; the RNG = the instrument's `l6_operators.Rng` | `tests/test_b1_twin.py`, `tests/test_b1_session.py` |
| the board's bytes pass the host | the image's identity (1.4.0) and record (1.2.0 + carto) bytes accepted by the instrument's validator; sorted keys; payload headroom | `tests/test_b1_wire.py` |
| **the whole session passes the real validators** | `host/b1_modelled_session.py`: the 335-record session through the instrument's reader / console / notary relay (B1 signer in-process, throw-away key) / collector / audit pulls of each candidate's **real** 2 814 staging + readback words, written as the runner writes it, adjudicated by `b1_adjudicate` with the instrument's validators — truth: **PASS**, 335 scored / 335 audited / chain 336, precision 1.0, recall 1.0, content = prediction; permuted: HOLD (verifier + prediction); a tampered served word: **KILL falsified**; a readout the board's block contradicts: named; a faulty channel (rel-v4 recovery): still COMPLETED | `tests/test_b1_e2e.py` |
| fail-closed everywhere | runner refusals in order (§8); adjudicator refusals (binding, pins, unqualified carrier); pin table drift | `tests/test_b1_runner.py`, `test_b1_adjudicate.py`, `test_b1_pins.py` |

## 3. Rebuildable image and carrier

```bash
python3 host/gen_b1_data.py --check          # the header is fresh from its generator
IMAGE=b1_app bash firmware/b1/bsp/build.sh   # → firmware/b1/bsp/out/b1_app.bin, sha256 54b00663…
python3 host/b1_build_evidence.py --build    # two clean builds, evidence/b1/build_evidence.json
bash sim/b1/run.sh                           # iverilog: tb_p3_siphash (verbatim) + tb_b1_core
vivado -mode batch -source vivado/b1/build_b1.tcl   # → builds/b1/b1.bit (d85daef4…), b1_build.json, isolation.txt
python3 host/b1_manifest.py                  # refresh the manifest's derived sections from the tree
python3 host/b1_plan.py --write-manifest     # plan + prediction, pinned into the manifest
python3 host/b1_pins.py --generate && python3 host/b1_manifest.py   # the pin table, last
```

Toolchain: the instrument's xPack arm-none-eabi-gcc 14.2.1 (read-only); BSP: Xilinx
2025.2 embeddedsw standalone_v9_4 + scuwdt_v2_6, referenced in place, every input by hash;
Vivado 2025.2 for the carrier.

## 4. Plan and stop-loss (the preregistration §2, §6)

Seed 1 123 460 948 by the stated rule, every earlier seed excluded; 333 probes + 2
baselines; all-self-reporting audit; deadline 1 048 s (expected ≈ 358 s; the modelled
session's virtual span ≈ 264 s); flags `0x32`; one ruling = one session; any non-COMPLETED
end, a failed replay, a map ≠ prediction, an anomaly, or a span past the deadline is a HOLD
reported with the map still scored; a validator falsification is a KILL; the instrument's
two-strikes / three-without-COMPLETED rules in force.

## 5. Rulings — DRAFT texts (not issued)

Three rulings, two sessions. The manifest sha256 below is the one **after** the owner writes
the frozen prereg hash and `board_ready` (and, for the mapping pair, `qualified`) into it
and commits; unknown today.

```json
{"ruling": "whole-of-run B1 carrier qualification", "boardid": "17A6", "granted_by": "14sea",
 "date": "<YYYY-MM-DD-NN>", "session": "B1Q", "budget": 9,
 "prereg_sha256": "<sha256 of docs/b1_preregistration.md as frozen>",
 "image_sha256": "54b006636fe07d1b52784e636452cfbd1191407a100699a7666c57b96ba4d6c8",
 "carrier_sha256": "d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f",
 "b1_manifest_sha256": "<manifest sha256 at freeze>"}
```
```json
{"ruling": "whole-of-run B1 cartography", "boardid": "17A6", "granted_by": "14sea",
 "date": "<YYYY-MM-DD-NN>", "session": "B1", "master_seed": 1123460948,
 "prereg_sha256": "<sha256 of docs/b1_preregistration.md as frozen>",
 "image_sha256": "54b006636fe07d1b52784e636452cfbd1191407a100699a7666c57b96ba4d6c8",
 "b1_manifest_sha256": "<manifest sha256 after qualified = true>"}
```
```json
{"ruling": "provisioning P3-K", "boardid": "17A6", "granted_by": "14sea",
 "date": "<YYYY-MM-DD-NN>", "session": "B1",
 "prereg_sha256": "<sha256 of docs/b1_preregistration.md as frozen>",
 "image_sha256": "54b006636fe07d1b52784e636452cfbd1191407a100699a7666c57b96ba4d6c8",
 "b1_manifest_sha256": "<manifest sha256 at freeze>"}
```

The qualification session's runner (`--budget 9`, the qualification ruling) is a
follow-up deliverable once the owner decides whether the host-attested reply control
(`docs/b1_carrier_qualification.md` §3 item 6) belongs in it; today's `b1_runner.py` runs
the mapping session only and refuses an unqualified carrier.

## 6. What a board session needs (when ruled)

A fresh power cycle; the D4 boundary produced as the runner < 6 h before `go`
(`zynq-psoracle/host/verify_principal_boundary.py --out …`); the rulings in `rulings/`
(gitignored); the image rebuilt (§3); the D4 sudoers line extended to
`host/b1_sign_arm.py` (a provisioning step recorded here, never done by a runner) — then:

```bash
cd /home/test/zynq_fabricmap && python3 host/b1_runner.py \
  --ruling rulings/b1_<date>.json --provision-ruling rulings/p3_k_<date>.json \
  --boundary <boundary json> --out evidence/b1/b1_17A6_<date> --image firmware/b1/bsp/out/b1_app.bin
```

Evidence per session ≈ 335 records, every one audited: small (the modelled session's
three files are ≈ 4 MB).

## 7. Compatibility review — what the owner is asked to review before `board_ready`

The B1 image against the L6 preregistration §2's list, as the two-operator image was
reviewed: the wire contract (rel-v4 unchanged; loop_record 1.2.0 + `carto`; app_identity
1.4.0 + the B1 fields — `tests/test_b1_wire.py`), the settle poll, the audit service, the
MMIO allowlists against the **B1** RTL (`tests/test_b1_carrier.py::MmioAllowlist`), the DMA
order, no ICAPE2, no SLCR write, the watchdog gating (all verbatim from `p3_app.c`, the
diff being the search → orchestrator/cartographer replacement, the carto block and the
VARIANT read: `git diff --no-index zynq-psoracle/firmware/p3_app.c firmware/b1/b1_app.c`),
the bounds (unchanged), and the B1-specific points: the cartographer's memory (static,
~34 KB of state + 20 KB render buffer), the record's payload size with a carto block
(< 3.6 KB of 4 KB), and the B1 carrier's RTL diff (`rtl/b1/` vs the instrument's).

## 8. Fail-closed today

`host/b1_runner.py` on the committed manifest: **REFUSED: B1's preregistration is not
frozen (manifest prereg.sha256 is null): host-only until the owner freezes it** — after the
ruling texts, before any instrument import, port or ruling consumption. With a fixture
"frozen" manifest the later refusals are reached one by one (`tests/test_b1_runner.py`):
plan pin, pin table, image bytes, `board_ready`, build evidence, carrier manifest / build
record / bitstream pin, VARIANT, **unqualified carrier**, ruling bound to another seed or
manifest, a stale boundary. `host/b1_adjudicate.py` on the committed manifest refuses the
same way (not frozen; unqualified carrier) before reading a record.

## 9. Tests and the clean-tree proof

B1 tests: `test_b1_adjudicate` (17), `test_b1_carrier` (7), `test_b1_e2e` (5), `test_b1_leakage` (7), `test_b1_pins` (3), `test_b1_plan` (7), `test_b1_records` (4), `test_b1_runner` (13), `test_b1_session` (5), `test_b1_signer` (4), `test_b1_twin` (8), `test_b1_wire` (3). Whole suite on the clean tree — **see the report cited below**; a
dirty tree skips 27 carrier-authority tests, so only `clean_tree_proof: true` counts.

Report: <<<REPORT>>>

## 10. What is asked, and what is not

Asked: the whole-package review; if it passes — the compatibility review (§7), the freeze
(prereg hash + `board_ready`), the carrier qualification ruling pair and session, then the
mapping ruling pair and one session on `17A6`. Not asked, and not done: any board contact,
any change to `zynq-psoracle`, any probe of unattested bits, any routing, any provisioning
of `08EB`, any B2/B3 ruling (their interfaces are fixed by the roadmap; their packages are
separate).
