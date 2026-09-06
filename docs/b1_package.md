# B1 — the package: v2.3.1 pushed, compatibility PASS, preregistration FROZEN (2026-09-06); next the B1Q ruling pair

> **FROZEN / NO BOARD RULING.** The preregistration was frozen on 2026-09-06 after the
> compatibility review of image `300b12b1…` passed; the image is `board_ready`.
> The carrier is not `qualified`, and no B1Q ruling pair exists. Work is stopped before
> board contact: no power cycle, image load or serial access has occurred. The instrument
> (`zynq-psoracle` `689dde1`) is unchanged, bit for bit. The v2.3.1 image and its review
> are pushed; the freeze and its clean-tree report are committed locally pending push
> approval. Next: the owner's B1Q ruling pair (§5).

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

**v2 → v2.1 (the owner's review of v2, 2026-09-05):** v2 was judged to have solved the
circular measurement and the init order, but not yet to freeze. Four blockers, closed here:

| blocker (v2) | v2.1 |
|---|---|
| 1 — schema findings were computed and then dropped by the entry point (`findings = …` overwrote them); the runner called `adjudicate()` and so bypassed the CLI's pin check | one local findings list written once; the plan, prediction and pin table are re-verified **inside** `adjudicate()` (a drift after preflight is REFUSED); every negative test now drives `adjudicate()` itself (`tests/test_b1_adjudicate.py`) |
| 2 — the gates were not the preregistration's exact numbers (full confirmation "not null" instead of 301; calibration not computed per snapshot; pending not required) | `EXPECTED` constants; exact equality on every §4 row; the probe-9 snapshot's confidence-1 accuracy 292/292 and the final snapshot's confidence-2 accuracy 292/292 with no confidence-1 cohort; pending = 0; the prediction file must carry the same constants; one entry-point negative per gate |
| 3 — `qualified` was a bare boolean; no B1Q runner, adjudicator, seed, or evidence pin; ruling count wrong | `host/b1q_runner.py` (the QUALIFICATION profile of the runner), `host/b1q_adjudicate.py`, the qualification plan/prediction (`evidence/b1q/`, seed 176 359 248 excluded from B1's set), the record format and `verify()` in `host/b1_qualification.py` — files hash, binding, PASS, **re-adjudication** — from which `carrier.qualified` is derived; two ruling pairs, four rulings; no host-attested reply control on the board (the nine code probes' `tables_match` = 0 with `configuration_valid_hw` = 1 are the evidence) — `docs/b1_carrier_qualification.md` |
| 4 — drift: manifest version / `evidence_max` / `holdout_luts`, the firmware header, the report schema and its round-1′ dependency, the legacy `validate_run_log`, unpinned normative docs, no semantic map validation | manifest sections derived from the tree (`b1_manifest.py`: prereg version from the document, cartographer from the constants, `reporting_strata`); firmware header rewritten for B1; `b1_test_report.py` standalone (schema `b1_test_report`); `validate_run_log` is a refusal; the contract, qualification and architecture documents are in the runtime pin table; `b1_verify.semantic_findings` (292 addresses once each, legal state combinations, code-probe seqs, 32 legal edges, none pending) |

**v2.1 → v2.2 (the owner's short review of v2.1, 2026-09-05):** the design and the four
fixes stand; four host-side blockers in the evidence chain and the manifest lifecycle:

| blocker (v2.1) | v2.2 |
|---|---|
| 1 — the manifest lifecycle dead-locked: the committed `carrier.qualification` was a legacy string, and `refresh()` reset `board_ready` to false, so "freeze → B1Q → pin → mapping" would refuse at `board_ready` | `refresh()` migrates any non-record value to null and keeps the owner's `board_ready` while the image, ELF and build-evidence pins have not drifted (any drift resets it); `Lifecycle` test: freeze → refresh (idempotent) → B1Q → `--qualification` → `qualified` derived, `board_ready` kept → the mapping preflight passes every pin |
| 2 — a B1Q run log carried the mapping plan/prediction hashes as its inputs | `l6.inputs` per profile (plan, prediction **and the pin table**); both adjudicators refuse a log whose inputs are not the session's pinned ones; the qualification record and `verify()` cross-check them against `manifest_at_run` |
| 3 — the qualification chain was open: the token came from the caller, the rulings' binding was not kept, the bound manifest's bytes were not kept, the provisioning ruling was not evidence | the runner copies `manifest_at_run.json` (bytes = the bound sha256) and both rulings verbatim into the evidence before the port; the record (2.0.0) takes its token from the run log, keeps both rulings' hash and content and the input pins; `verify()` re-binds tokens (app_identity / notary / summary / summary.json), both rulings, the inputs, re-adjudicates against `manifest_at_run`, and allows the current manifest to differ from it only in the qualification state (`docs/b1_carrier_qualification.md` §4) |
| 4 — the mapping adjudicator accepted `qualified: false` with standing evidence | `qualification_stands()` requires the derived flag to agree with the evidence (as the runner does); tested from `adjudicate()` |

**v2.2 → v2.2.1 (the owner's final short review, 2026-09-05):** the four v2.1 blockers are
closed; one execution-order / evidence-identity blocker remained: the session artifacts
were archived by the session function, i.e. after the ruling was claimed and the serial
port opened, against what the documents said. v2.2.1: `b1_runner.execute` archives and
verifies the three artifacts (each ruling copy equal to what the preflight parsed) in a
guarded try **before** the claim and **before** the port — a failure consumes nothing and
opens nothing — and the order is asserted by a test (`tests/test_b1_runner.py::Order`:
archive → claim → open → session); the session function refuses to start without the
artifacts; `verify()` requires `summary.ruling` to equal the archived whole-of-run ruling
and `summary.provisioning_ruling_sha256` (the digest of the bytes the signer was handed,
taken before and after the call) to equal the archived provisioning copy's. Firmware,
image, carrier, plans and predictions unchanged.

**v2.2.1 → v2.2.2 (the owner's review of v2.2.1, 2026-09-05):** the five fixes stand; one
one-shot-ruling blocker remained — the archive copied each ruling verbatim, and a verbatim
copy with no `.consumed` marker beside it is a fresh, valid ruling to every parser (the
instrument's `check_ruling`, the signer's provisioning path, this runner's preflight): an
owner's authorisation duplicated into another usable one. v2.2.2 archives rulings as
**inert envelopes** (`archived_ruling_bytes`: the bytes base64 + their sha256, no ruling
fields), decoded and hash-checked by `verify()` and re-bound as before; tests assert that
every parser refuses the envelopes, that a failed archive leaves nothing behind, and that
no file in the evidence directory ever parses as a ruling. Firmware, image, carrier, plans
and predictions unchanged.

**v2.2.2 → v2.2.3 (the owner's review of v2.2.2, 2026-09-05):** the envelope's top-level
schema was not locked: with the decoded ruling fields re-added at the envelope's top level
(bytes, bytes hash and content unchanged) and the evidence / record hashes updated, a
parser accepted the file as a ruling and `verify()` still passed. v2.2.3: the envelope's
key set is exact (`additionalProperties: false` — `schema`, `schema_version`, `sha256`,
`content_base64`, `note`), any ruling field on an envelope is refused explicitly, types are
checked; the owner's counter-example is a test through `verify()`, for both rulings. The
qualification document's example now says record 2.1.0. Firmware, image, carrier, plans
and predictions unchanged. **v2.2.4** (the owner's last read): `note` is mandatory in the
envelope, as the documents say; with that the owner approved the push of every local
commit, with the sequence after it fixed: compatibility review → freeze → B1Q ruling pair;
no board contact before that.

**v2.2.4 → v2.2.5 (the owner's post-push check, 2026-09-05):** two evidence gaps, closed
before the freeze. (1) The offline adjudications compared only the preregistration's
digest in the manifest and the log, never the document's bytes: a document edited after
the freeze still passed B1, B1Q and the qualification verifier (the runner did check it).
Now `check_prereg_document` runs inside both adjudicators' binding and in `verify()`; the
owner's reproduction is a test in each. (2) The build evidence listed the application
units and the headers they include, not the BSP / syscall / watchdog C and assembly units
`build.sh` compiles, `b1_orch.c/h`, nor the toolchain's runtime objects and libraries.
`b1_build_evidence.py` 1.1.0 reads the unit lists from `build.sh` itself and records every
translation unit, every header any unit includes, and crti/crtbegin/crtend/crtn +
libgcc/libc/libm as the link resolves them, all by hash. Also the README / package
headers that still read "awaiting push". Firmware, image (`54b00663…`, rebuilt
byte-identically), carrier, plans and predictions unchanged.

**FREEZE (owner, 2026-09-06), executed on the owner's instruction to perform the freeze:**
`docs/b1_preregistration.md` pinned by its bytes (`prereg.sha256` =
`f995245cca13d5ac8cba8475c609a6e9f01d269cddc2d87e6a9b980f983652f2`, `frozen: true`),
`image.board_ready: true` for `300b12b1…`, the manifest refreshed (the derived sections
unchanged; `carrier.qualified` false — no B1Q session yet), the manifest's status FROZEN. Any
change to the preregistration document is now refused by the runner and both adjudicators.
The next station is the B1Q ruling pair bound to THIS committed manifest's sha256 (§5).

**Compatibility review of the v2.3.1 image `300b12b1…` (owner, 2026-09-05): PASS** —
`docs/b1_compatibility_review_2026_09_05_v231.md`, evidence
`evidence/b1/compatibility_review_2026_09_05_v231/`: every §7 item checked (wire, settle,
audit, MMIO, DMA, watchdog, memory, RTL diff), 55 tests incl. the RTL benches, the ARM
`run_candidate` frame 9 960 B, the REC stress case 2 306 / 4 096 B, image / ELF / carrier /
build inputs / pins matching. Recorded limits: the SCORED candidates before a refused one
are primed by the harness (no PL path executed); no on-board verification, no stack
high-water measurement, no Vivado re-run. At that review, the next station was the owner's
freeze (§8 of the preregistration), completed on 2026-09-06 as recorded above; the B1Q
ruling pair remains pending.

**v2.3 → v2.3.1 (the owner's recheck of v2.3, 2026-09-05; P2):** `run_candidate` set
`S.closing_baseline` at ANY scored baseline, so after a scored opening baseline a refused
probe's TERM claimed `closing.baseline: done` for a closing baseline that never happened —
and the harness's priming, which updated only the orchestrator, the seq and the scored
count, omitted that side effect and so hid it. v2.3.1 (firmware): the bookkeeping a SCORED
candidate leaves is one function, `note_scored`, and the closing-baseline mark is set only
when the orchestrator's step is DONE (the closing baseline); the harness primes through
`note_scored` itself, never a hand-written subset; tests assert the mark both ways (after
the opening: not set; after the closing: set) and, through the real loop, that a refusal
after the opening baseline leaves the TERM's closing baseline `not_reached`. NEW image
`300b12b1…` (§1); `31663e2d…` recorded WITHDRAWN / DEFECTIVE / NO-RUN.

**v2.2.6 → v2.3 (the owner's compatibility review, 2026-09-05: HOLD —
`docs/b1_compatibility_review_2026_09_05.md`):** every §7 item passed except the unscored
stop condition: `run_candidate`'s SIGNREF branch recorded `REFUSED_BY_GATE` and returned 0,
so `main` proposed the next candidate — the instrument's "a gate refusal is data, the
session continues", against B1's "any candidate that is not SCORED ends the epoch"; the
twin's UNSCORED model breaks out of its own loop and could never see it. v2.3 (firmware):
the branch stops the epoch after the record (restore-only cleanup, STOPPED TERM); the
STOP_AXI branch's stop is explicit; the session is three named steps
(`b1_session_init/run/finish`). Coverage of the ACTUAL application branches: the host
application harness `tb/b1/hostapp` compiles `b1_app.c` itself against stub BSP headers, a
fake memory map and a scripted host and runs the real session loop — the opening baseline,
a probe after a scored baseline and the closing baseline each refused, and a refusal
record never acknowledged: every one ends the epoch with one SIGNREQ, no CTRL write, the
restore-only cleanup and a STOPPED TERM whose REC / TERM payloads validate under the
instrument's schemas; a source audit requires the stop after every non-SCORED emission
(`tests/test_b1_hostapp.py`). The image is NEW (§1); `54b00663…` is recorded WITHDRAWN /
DEFECTIVE / NO-RUN; the compatibility review must be redone on the new image, then freeze.

**v2.2.5 → v2.2.6 (the owner's review of v2.2.5, 2026-09-05):** the
prereg gap is closed; the build-evidence gap was not — the header set kept only the
embeddedsw / repository dependencies and dropped the toolchain's own (newlib's
`stdint.h`, `stdio.h`, `string.h` …, 23 files for `b1_app.c` alone), on the wrong premise
that the compiler executable's hash covers the headers beside it. `b1_build_evidence.py`
1.2.0 records every dependency `gcc -M` names for every unit, wherever it lives, and a
completeness test recomputes the dependency set of every unit and requires it to be a
subset of the evidence's header set with matching hashes. The qualification module's
docstring no longer calls the ruling archives verbatim files. Image unchanged.

## 1. Hashes and data flow

| artifact | sha256 / value | role |
|---|---|---|
| `manifests/b1_manifest.json` | (committed; **FROZEN 2026-09-06**: `prereg.sha256` `f995245c…`, `board_ready` true; `carrier.qualification` **null** → `qualified` false, derived) | the stage's pins |
| B1 carrier `builds/b1/b1.bit` | `d85daef4e3aa1ff925c327e1c1f98465a83d96e79955aca432d664d98aa4f38f`, 2 083 858 B | committed (as the instrument commits its carrier); build record `5da31443…`, carrier manifest `2e9de7c7…`, isolation `ada2594e…`; WNS +7.993 ns, ICAPE2 0, isolation passed |
| B1 image `firmware/b1/bsp/out/b1_app.bin` | `300b12b1104b70d1612f4c6236a9280a0556443757b2ddf9dbadd9ef993d5abb`, 114 708 B | rebuilt byte-identically by `firmware/b1/bsp/build.sh`; not committed; hash-checked by the runner |
| `evidence/b1/build_evidence.json` | pinned in the manifest | two clean builds equal; the sources, the embeddedsw inputs, the compiler, all by hash; `worktree_dirty` and `head` recorded |
| B1 signer `host/b1_sign_arm.py` | pinned in the manifest | zero tables; `probe` / `sign_genome` / `provision` only — no host-attested `sign` |
| `firmware/b1/p3_data.h` | generated (`host/gen_b1_data.py`), no operator tables | the cartographer's only knowledge of the fabric: 292 addresses + base frames |
| `firmware/b1/IMPORT.json` | 14 instrument files at `689dde1` by hash; 3 derived | the verbatim imports; `b1_app.c`, `b1_wire.c/h` derived from `p3_app.c`, `p3_wire.c/h` |
| `manifests/claimb_round1prime_instrument_pins.json` | 128 files | the read-only instrument binding, reused |
| `manifests/b1_instrument_pins.json` | 92 files | every adjudication-critical fabricmap file, the contract / qualification / architecture documents included; re-verified inside the adjudicator |
| `evidence/b1/plan.json` | `470e18f8fe3443be1ee9f9f27ffc28f73113b2231cdbff5b62348bfb58fda8e9` | seed 1 123 460 948, budget 333, 335 records, every seq audited, 9 048 frames, budget 37, deadline 1 048 s, strata A/B |
| `evidence/b1/prediction.json` | `7d197a498a5ca894fbc1287b37d19cd7d288c2f26d6dbcd21fefa8679e8fd35a` | the 333 probes (`f351475c…`), every record's content-level block, the map content (`7e1e7702…`), the expected score with both snapshots' calibration |
| `evidence/b1q/plan.json` / `prediction.json` | `dead8853…` / `d2c9293a…` | the qualification session: seed 176 359 248, budget 9, 11 records, 300 frames, budget 2, deadline 615 s; the nine probes, the provisional content (`ce2c89f9…`), the base counters, the STATUS observations |
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
| **the carrier is qualified only through evidence** | the modelled B1Q session (11 records) through the real stack → `b1q_adjudicate` PASS with every silicon observation (baselines: zero readout, base counters, `tables_match` 1; code probes: non-zero readout, `tables_match` 0, `configuration_valid_hw` 1, fault 0) → the record → `verify()` re-adjudicates → the mapping adjudicator and runner accept the carrier; a bare flag, a missing record, a tampered evidence file (caught by the hash, and — re-pinned — by the re-adjudication), a binding to another carrier / image / prereg / seed, a HOLD record, a code probe with `tables_match` = 1 or `cfg_valid` = 0, a baseline with a non-zero readout or other counters: each refused | `tests/test_b1_qualification.py` |
| every gate fires from the entry point | each exact metric of the preregistration §4 altered by one unit on its way out of the verifier → `adjudicate()` returns HOLD naming it; a forced schema finding, a missing JSON-schema validator, a broken schema or semantics → HOLD; a plan / prediction / pin table that drifted after preflight → REFUSED | `tests/test_b1_adjudicate.py` |
| fail-closed everywhere | runner refusals in order (§8); adjudicator refusals (binding, pins, qualification chain); pin table drift | `tests/test_b1_runner.py`, `test_b1_adjudicate.py`, `test_b1_pins.py` |

## 3. Rebuildable image and carrier

```bash
python3 host/gen_b1_data.py --check          # the header is fresh from its generator
IMAGE=b1_app bash firmware/b1/bsp/build.sh   # → firmware/b1/bsp/out/b1_app.bin, sha256 300b12b1…
python3 host/b1_build_evidence.py --build    # two clean builds, evidence/b1/build_evidence.json
bash sim/b1/run.sh                           # iverilog: tb_p3_siphash (verbatim) + tb_b1_core
vivado -mode batch -source vivado/b1/build_b1.tcl   # → builds/b1/b1.bit (d85daef4…), b1_build.json, isolation.txt
python3 host/b1_manifest.py                  # refresh the manifest's derived sections from the tree
python3 host/b1_plan.py --write-manifest     # plan + prediction, pinned into the manifest
python3 host/b1_plan.py --qualification --write-manifest   # the B1Q plan + prediction (evidence/b1q/)
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

## 5. Rulings — DRAFT texts (not issued): two sessions, two pairs, FOUR rulings

A provisioning ruling is consumed once and is bound to its session name, so each session
needs its own. The manifest sha256 in the qualification pair is the one **after** the owner
writes the frozen prereg hash and `board_ready` and commits; the one in the mapping pair is
the manifest **after** the qualification record is pinned and committed. Both unknown today.

**Qualification pair (session `B1Q`)**
```json
{"ruling": "whole-of-run B1 carrier qualification", "boardid": "17A6", "granted_by": "14sea",
 "date": "<YYYY-MM-DD-NN>", "session": "B1Q", "master_seed": 176359248,
 "prereg_sha256": "<sha256 of docs/b1_preregistration.md as frozen>",
 "image_sha256": "300b12b1104b70d1612f4c6236a9280a0556443757b2ddf9dbadd9ef993d5abb",
 "b1_manifest_sha256": "<manifest sha256 at freeze>"}
```
```json
{"ruling": "provisioning P3-K", "boardid": "17A6", "granted_by": "14sea",
 "date": "<YYYY-MM-DD-NN>", "session": "B1Q",
 "prereg_sha256": "<sha256 of docs/b1_preregistration.md as frozen>",
 "image_sha256": "300b12b1104b70d1612f4c6236a9280a0556443757b2ddf9dbadd9ef993d5abb",
 "b1_manifest_sha256": "<manifest sha256 at freeze>"}
```

**Mapping pair (session `B1`)**
```json
{"ruling": "whole-of-run B1 cartography", "boardid": "17A6", "granted_by": "14sea",
 "date": "<YYYY-MM-DD-NN>", "session": "B1", "master_seed": 1123460948,
 "prereg_sha256": "<sha256 of docs/b1_preregistration.md as frozen>",
 "image_sha256": "300b12b1104b70d1612f4c6236a9280a0556443757b2ddf9dbadd9ef993d5abb",
 "b1_manifest_sha256": "<manifest sha256 after the qualification record is pinned>"}
```
```json
{"ruling": "provisioning P3-K", "boardid": "17A6", "granted_by": "14sea",
 "date": "<YYYY-MM-DD-NN>", "session": "B1",
 "prereg_sha256": "<sha256 of docs/b1_preregistration.md as frozen>",
 "image_sha256": "300b12b1104b70d1612f4c6236a9280a0556443757b2ddf9dbadd9ef993d5abb",
 "b1_manifest_sha256": "<manifest sha256 after the qualification record is pinned>"}
```

## 6. What a board session needs (when ruled)

A fresh power cycle; the D4 boundary produced as the runner < 6 h before `go`
(`zynq-psoracle/host/verify_principal_boundary.py --out …`); the rulings in `rulings/`
(gitignored); the image rebuilt (§3); the D4 sudoers line extended to
`host/b1_sign_arm.py` (a provisioning step recorded here, never done by a runner) — then:

```bash
cd /home/test/zynq_fabricmap
# session (a): the carrier qualification, then pin its PASS record and commit
python3 host/b1q_runner.py --ruling rulings/b1q_<date>.json --provision-ruling rulings/p3_k_b1q_<date>.json \
  --boundary <boundary json> --out evidence/b1q/b1q_17A6_<date> --image firmware/b1/bsp/out/b1_app.bin
python3 host/b1_manifest.py --qualification evidence/b1q/b1q_17A6_<date>     # verifies, pins, derives qualified
# session (b): the mapping session, under the pair bound to THAT committed manifest
python3 host/b1_runner.py --ruling rulings/b1_<date>.json --provision-ruling rulings/p3_k_b1_<date>.json \
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

The committed manifest is **FROZEN**, its preregistration hashes to the frozen pin, and
the reviewed image is `board_ready`. With fixture rulings that pass the initial ruling
checks, `host/b1_runner.py` in the MAPPING profile passes the preceding pins and refuses
because the carrier is **not qualified: no carrier.qualification record**. The committed
manifest also makes `host/b1_adjudicate.py` refuse at the missing qualification record.
These checks run before any port access or ruling consumption. No real B1Q ruling pair
has been issued.

The DRAFT refusal remains covered by fixtures with `prereg.sha256` null; it is no longer
the committed manifest's state. Other fixture tests reach each refusal in order
(`tests/test_b1_runner.py`): plan pin, pin table, image bytes, `board_ready`, build evidence,
carrier manifest / build record / bitstream pin, VARIANT, the qualification chain (no
record; a bare flag; tampered evidence; a binding to another carrier; a flag disagreeing
with the evidence), rulings bound to another seed, manifest or session, and a stale
boundary. The QUALIFICATION profile requires no prior qualification, but does require
its own plan pin and ruling pair (session `B1Q`; mapping rulings do not open it). The
adjudicator re-verifies the plan, prediction and pin table itself.

## 9. Tests and the clean-tree proof

B1 tests: `test_b1_adjudicate` (26), `test_b1_build_evidence` (3), `test_b1_carrier` (7), `test_b1_e2e` (5), `test_b1_hostapp` (8), `test_b1_leakage` (7), `test_b1_pins` (3), `test_b1_plan` (10), `test_b1_qualification` (18), `test_b1_records` (5), `test_b1_runner` (20), `test_b1_session` (5), `test_b1_signer` (4), `test_b1_twin` (8), `test_b1_wire` (3). Whole suite on the clean tree — **see the report cited below**; a
dirty tree skips 27 carrier-authority tests, so only `clean_tree_proof: true` counts.

Report: `evidence/b1/tests/test_report_2026-09-06T071310Z.json` (schema `b1_test_report`, package `B1 v2.3.1`) — ran **1427**, skipped **0**, `OK`; `head_at_run` `e1f2839778c3` (the freeze commit), `worktree_dirty` False; instrument `689dde1dad37` = pinned, dirty False; **`clean_tree_proof: True`**. Earlier reports are kept as the records of the earlier packages (the last before the freeze: `…T191204Z`, 1425 at `9d7a720`).

## 10. What is asked, and what is not

Asked (the owner's words after the final short review): once green — push, then the
compatibility review (§7), the freeze (prereg hash + `board_ready`), the qualification pair and session
(a), the record pinned and committed, then the mapping pair and one session (b) on `17A6`. Not asked, and not done: any board contact,
any change to `zynq-psoracle`, any probe of unattested bits, any routing, any provisioning
of `08EB`, any B2/B3 ruling (their interfaces are fixed by the roadmap; their packages are
separate).
