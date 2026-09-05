# B1 — the pre-board package, delivered for the whole-package review (2026-09-05)

> **HOST-ONLY. DRAFT / NO BOARD RULING.** Delivered at "B1 ready for the board" under the
> owner's ruling of 2026-09-05 (`docs/autonomous_cartography_roadmap.md`; the
> authorisation of the same day) and STOPPED here. Nothing is frozen; the image is not
> `board_ready`; no ruling exists; no board contact, power cycle, image load or serial
> port has been touched. The instrument (`zynq-psoracle` `689dde1`) is unchanged, bit for
> bit. Local commits only; nothing pushed until this review.

## 0. What B1 is, in three sentences

The board, given only the 292 certified addresses and their safety class, chooses its
own probes, reads the PL's functional readout after each, and builds a map — LUT, INIT
position, polarity, confidence, evidence — committing to its hash in every record. The
host signs, audits every record, collects, and afterwards **recomputes** the map from the
readouts: the board's probes and hashes must be exactly what the algorithm produces from
those observations, and the map is then scored against the certificate the executable
never saw. The prediction says the board will map all 292 in **9 probes** (provisional) and
confirm all of them by probe 301, with 0 anomalies, in about six minutes.

## 1. Hashes and data flow

| artifact | sha256 / value | role |
|---|---|---|
| `manifests/b1_manifest.json` | (committed; `prereg.sha256` null, `board_ready` false) | the stage's pins |
| B1 image `firmware/b1/bsp/out/b1_app.bin` | `7bc86a3f2b9548a4a9cb8eb794ed7ee3ea864a814dabe848149e6c228903178d`, 114 708 B | rebuilt byte-identically by `firmware/b1/bsp/build.sh`; not committed; hash-checked by the runner |
| `evidence/b1/build_evidence.json` | pinned in the manifest | two clean builds equal; 18 sources, 13 embeddedsw inputs, the compiler, all by hash |
| `firmware/b1/p3_data.h` | generated (`host/gen_b1_data.py`), no operator tables | the cartographer's only knowledge of the fabric: 292 addresses + base frames |
| `firmware/b1/IMPORT.json` | 14 instrument files at `689dde1` by hash | the verbatim imports; `b1_app.c`, `b1_wire.c/h` derived from `p3_app.c`, `p3_wire.c/h` |
| `manifests/claimb_round1prime_instrument_pins.json` | 128 files | the read-only instrument binding, reused |
| `evidence/b1/plan.json` | `59fbd8040b4238bb22924980e6357fad19056cbb8c38cd2bc705044ee301b9cc` | seed 1 123 460 948, budget 333, 335 records, every seq audited, 9 048 frames, budget 37, deadline 1 048 s |
| `evidence/b1/prediction.json` | `d993a528dd994b40f73726981235620cd4b99c4d9c90b0c40df29f120402b317` | the 333 probes, every record's carto block, the map (`38337072…`), the expected score |
| universe digest | `895baf85…` | in the header, the image and the IDENT |
| ground truth `local_map.json` | `56f2b9e8…` | held back from the executable; the verifier's only input beyond the records |
| `schemas/self_map_v2.schema.json` | (committed) | the expanded map the adjudicator writes |

Data flow, one session: identity page (seed, budget, flags) → IDENT 1.4.0 (carto-v1,
universe, budget; verified before IDENTACK) → per probe: SIGNREQ (genome) → host gate +
signature → stage / DMA / readback → signed ARM → sweep → readout + counters → REC 1.2.0
with `carto` (phase, changed sample, `map_sha256`) → audit pull (every record) → … →
closing baseline (its carto block = the final commitment) → closing unsigned control →
TERM. Afterwards, from the files as written: the instrument's validators → the autonomy
replay → the verifier → `self_map_v2.json`.

## 2. Autonomy and leakage — the proofs

| claim | proof | where |
|---|---|---|
| the board chooses; the host only audits | the replay: the reference, fed the records' readouts, reproduces every probe genome and every running `map_sha256`; a foreign probe or a lying hash is a HOLD | `host/b1_adjudicate.py`; `tests/test_b1_adjudicate.py` |
| no table reaches the executable | header generator + token scan; source include scan; binary scan (no LUT key, no `P3_LUT`, no arm name; `carto-v1` and the universe digest present); verbatim imports by hash | `tests/test_b1_leakage.py` |
| it measures, it does not recall | permuted fixture → 292/292 vs the permutation, < 10 vs the truth; address-only baseline precision < 0.2 vs 1.0 | `tests/test_b1_leakage.py`, `host/b1_model.py` |
| the image runs the same algorithm as the reference | C twin = Python over four fixtures, six budgets, unscored probes; the RNG = the instrument's `l6_operators.Rng` | `tests/test_b1_twin.py` |
| the board's bytes pass the host | the image's identity (1.4.0) and record (1.2.0 + carto) bytes accepted by the instrument's validator; sorted keys; payload headroom | `tests/test_b1_wire.py` |

## 3. Rebuildable image

```bash
python3 host/gen_b1_data.py --check          # the header is fresh from its generator
IMAGE=b1_app bash firmware/b1/bsp/build.sh   # → firmware/b1/bsp/out/b1_app.bin, sha256 7bc86a3f…
python3 host/b1_build_evidence.py --build    # two clean builds, evidence/b1/build_evidence.json
```

Toolchain: the instrument's xPack arm-none-eabi-gcc 14.2.1 (read-only); BSP: Xilinx
2025.2 embeddedsw standalone_v9_4 + scuwdt_v2_6, referenced in place, every input by hash.

## 4. Plan and stop-loss (the preregistration §2, §6)

Seed 1 123 460 948 by the stated rule, every earlier seed excluded; 333 probes + 2
baselines; all-self-reporting audit; deadline 1 048 s (expected ≈ 358 s); flags `0x32`;
one ruling = one session; any non-COMPLETED end, a failed replay, a map ≠ prediction, an
anomaly, or a span past the deadline is a HOLD reported with the map still scored; the
instrument's two-strikes / three-without-COMPLETED rules in force.

## 5. Ruling pair — DRAFT texts (not issued)

The manifest sha256 below is the one **after** the owner writes the frozen prereg hash and
`board_ready` into it and commits; unknown today.

```json
{"ruling": "whole-of-run B1 cartography", "boardid": "17A6", "granted_by": "14sea",
 "date": "<YYYY-MM-DD-NN>", "session": "B1", "master_seed": 1123460948,
 "prereg_sha256": "<sha256 of docs/b1_preregistration.md as frozen>",
 "image_sha256": "7bc86a3f2b9548a4a9cb8eb794ed7ee3ea864a814dabe848149e6c228903178d",
 "b1_manifest_sha256": "<manifest sha256 at freeze>"}
```
```json
{"ruling": "provisioning P3-K", "boardid": "17A6", "granted_by": "14sea",
 "date": "<YYYY-MM-DD-NN>", "session": "B1",
 "prereg_sha256": "<sha256 of docs/b1_preregistration.md as frozen>",
 "image_sha256": "7bc86a3f2b9548a4a9cb8eb794ed7ee3ea864a814dabe848149e6c228903178d",
 "b1_manifest_sha256": "<manifest sha256 at freeze>"}
```

## 6. What a board session needs (when ruled)

A fresh power cycle; the D4 boundary produced as the runner < 6 h before `go`
(`zynq-psoracle/host/verify_principal_boundary.py --out …`); the rulings in `rulings/`
(gitignored); the image rebuilt (§3) — then:

```bash
cd /home/test/zynq_fabricmap && python3 host/b1_runner.py \
  --ruling rulings/b1_<date>.json --provision-ruling rulings/p3_k_<date>.json \
  --boundary <boundary json> --out evidence/b1/b1_17A6_<date> --image firmware/b1/bsp/out/b1_app.bin
```

Evidence per session ≈ 335 records, every one audited: small (the L6 C1/C2 sessions of 66
records were a few MB).

## 7. Compatibility review — what the owner is asked to review before `board_ready`

The B1 image against the L6 preregistration §2's list, as the two-operator image was
reviewed: the wire contract (rel-v4 unchanged; loop_record 1.2.0 + `carto`; app_identity
1.4.0 + three fields — `tests/test_b1_wire.py`), the settle poll, the audit service, the
MMIO allowlists against the RTL, the DMA order, no ICAPE2, no SLCR write, the watchdog
gating (all verbatim from `p3_app.c`, the diff being the search → cartographer replacement
and the carto block: `git diff --no-index zynq-psoracle/firmware/p3_app.c
firmware/b1/b1_app.c`), the bounds (unchanged), and the two B1-specific points: the
cartographer's memory (static, ~34 KB of state + 20 KB render buffer; bss 1.18 MB as the P3
image's) and the record's payload size with a carto block (< 3.6 KB of 4 KB).

## 8. Fail-closed today

`host/b1_runner.py` on the committed manifest: **REFUSED: B1's preregistration is not
frozen (manifest prereg.sha256 is null): host-only until the owner freezes it** — after the
ruling texts, before any instrument import, port or ruling consumption. With a fixture
"frozen" manifest the later refusals are reached one by one (`tests/test_b1_runner.py`):
plan pin, image bytes, `board_ready`, build evidence, ruling bound to another seed or
manifest, a stale boundary.

## 9. Tests and the clean-tree proof

New for B1: `test_b1_twin` (8), `test_b1_leakage` (7), `test_b1_wire` (3), `test_b1_plan`
(7), `test_b1_adjudicate` (8), `test_b1_runner` (10). Whole suite on the clean tree —
**see the report cited below**; a dirty tree skips 27 carrier-authority tests and hides 5,
so only `clean_tree_proof: true` counts.

Report: `evidence/b1/tests/test_report_2026-09-05T101536Z.json` — ran **1338**, skipped **0**, `OK`; `head_at_run` `4c49b259671b` (the package commit), `worktree_dirty` False; instrument `689dde1dad37` = pinned, dirty False; **`clean_tree_proof: True`**.

## 10. What is asked, and what is not

Asked: the whole-package review; if it passes — the compatibility review (§7), the freeze
(prereg hash + `board_ready`), the ruling pair (§5), one session on `17A6`. Not asked, and
not done: any board contact, any change to `zynq-psoracle`, any probe of unattested bits,
any routing, any provisioning of `08EB`, any B2/B3 ruling (their interfaces are fixed by
the roadmap; their packages are separate).
