# B3 lifecycle 1 — stop decision at the prediction preflight (2026-09-17)

**Decision (the owner, 2026-09-17): B3 lifecycle 1 is stopped at the prediction preflight.** No 2c-ii,
no canonical plan / prediction, no pin table, no manifest, no image, no ruling, no board. The
predicted primary 1 passing on its own does not become a B3 claim. **This is a design-stage stop,
not a B3 FAIL on the board** — no board session was run under this lifecycle.

## 1. What triggered it

Preregistration DRAFT v0.2 §1 (`docs/b3_preregistration.md`, sha256 `03cb3914…` before the STOPPED
banner): both predicted primaries on the fixed board seeds must reach p ≤ 0.05, else the line stops —
the seeds are not redrawn and N is not raised. The prediction preflight (`b3/host/b3_plan.py` at
`b1b82d0`, run once, rate-less, kept as it came out in `evidence/b3/plan_trial_2026_09_17/`):

| | Δ per pair (0..8) | pos / neg / ties | p (one-sided exact sign test) | exact | verdict |
|---|---|---|---|---|---|
| primary 1, Δ1 = O − R | 9, 5, 4, 5, 8, 4, 2, 6, 4 | 9 / 0 / 0 | 0.001953125 | 1/512 | SUPPORTED |
| primary 2, Δ2 = O − end-to-end F | 4, 0, −1, 3, 3, 2, −1, 3, −2 | 5 / 3 / 1 | 0.36328125 | 93/256 | **NOT SUPPORTED** |

Seeds: label `b3-session` ‖ instrument commit `689dde1…`, master 1 273 858 430, nine pairs, 1 646
excluded values (every archived set including the gate's own 200 pairs). F1 / 1 000 / the
prefix-balanced arm order. Every O-arm run decoded ≥ 286 / 292 with 0 wrong decodes and 0 anomalies.

## 2. Independent confirmation (the owner's, and reproduced here)

`evidence/b3/lifecycle1_stop_2026_09_17/regeneration_and_sizing.json`:

- the committed code regenerates the trial `prediction.json` **byte-identically** (sha256
  `6e45a752bd3db536db0cbea7dcb0e531bb40889fff91f7dc6c28250f44f729b2`); the plan is equal outside
  `generated_utc` / `prediction_sha256` (trial `plan.json` `8b6142b0…`);
- the CLI exits **3** and names primary 2;
- the two exact p-values are 1/512 and 93/256;
- canonical `evidence/b3/plan.json` / `prediction.json`, `manifests/b3_instrument_pins.json` and
  `manifests/b3_manifest.json` do not exist;
- the B2 verify stays S3 / true / null / `aec84514…` (`verify_closing.json`).

**Why nine pairs did not provide the planned power for primary 2.** The gate sized N on Δ1 alone
(H5, N(B*) = 9). The same bootstrap rule applied to Δ2 at B* = 1 000 over the 200 gate seeds
(125 / 49 / 26) gives **power 0.213 at N = 9** and requires **N = 53 to reach 0.9** (power 0.909,
search cost 159 000 — more than five times the 30 000 cap). Lifecycle 1 therefore sized Δ1 but left
the required primary 2 underpowered. The fixed nine-pair prediction did not support primary 2; it
cannot distinguish sampling variation from effect heterogeneity. H9 met the preregistered S = 200
gate condition but did not guarantee significance at N = 9.

## 3. Identity chain of lifecycle 1 (history; no authority is carried forward)

| what | identity |
|---|---|
| base | `73b68d7` (B2 complete, S3 `aec84514…`) |
| unit 1, the pinned-surface audit (PASS) | `c648d6e` → `c5f5346` → `3a2063d`; B2 completion inputs `evidence/b2/b2_completion_inputs_2026-09-17/` (archive `20300d5f…`, manifest `ca5fedd7…`) |
| unit 2, architecture v0.2.3 + preregistration DRAFT v0.1.2 (PASS) | `4fbb305` → `b729c39` → `faa7421` → `1aa06f1`; `docs/b3_architecture.md` sha256 `0713dee9e6954bb9db20a3a8be0b52512de762ebe2c4674f18902646bd8dbac8` (unchanged since) |
| 2a, cartographer / online arm / control X / online map (PASS) | `fd3e47f` → `b3c5d29` → `2b7495e` → `25c7ede` |
| 2b, the gate (PASS) | code `61fe638` → `f159dee`; run 1 `b7db6c7` (`evidence/b3/gate/gate_report.json` `477225f54bb40866abb08df69e6e34341c7516cd7e398e8bb6d0c06c8ae2aa68`, F1 PASS, B* = 1 000, N = 9, H9 holds, control X π `9cc0b64e…`); preregistration v0.2 `989ab4f` → `8b43205` |
| 2c-i, the plan tool and the trial | `b1b82d0`; trial `evidence/b3/plan_trial_2026_09_17/` |
| this containment | the commit that adds this document, the evidence directory and the banner |

## 4. Kept as they are — the defects the owner found on `b1b82d0` (not repaired under this lifecycle)

- **P2** `b3/host/b3_plan.py` stores only `ledger_sha256` and counts for the O arm; preregistration
  §3 / §8 require every ledger entry in the prediction; the tests check counts only.
- **P2** `main()` writes the plan and prediction before checking the stop rule; with the default
  `--out` it would have written `evidence/b3/plan.json` and then exited 3 (the trial used a scratch
  directory, so the canonical path was not touched). The stop must act before any canonical write.
- **P3** the commit message said 48 tests / 10 in `test_b3_plan`; the count is **47 / 9**
  (`b3_tests_at_b1b82d0.log`).
- **P3** preregistration §3 calls the rendered map `self_map` 2.0.0 in the same sentence that says
  it is an `online_map` 1.0.0 and not a `self_map`.

These are recorded, not fixed: a lifecycle that has stopped does not keep editing its instruments.

## 5. What was not done

No S0, no pin table, no manifest, no image build, no ruling, no board session; no push; no seed
redraw, no change of N, no narrowing of the claim to primary 1; `docs/b3_architecture.md`,
`docs/b3_preregistration.md` §1–§10, the gate evidence and the trial untouched (the preregistration
carries only a STOPPED banner).

## 6. If a lifecycle 2 is opened (the owner's conditions)

- the nine lifecycle-1 pairs are an **observed pilot**: they enter the exclusion set and never a
  new draw;
- the new claim, the search-evaluation cap, the sizing of **both** primaries by the same rule, and
  the seed label are fixed **before** any new prediction is generated;
- everything else of unit 1 and 2 (the namespace, the pins discipline, the verifier contract, the
  authority boundary) stands as reviewed; the gate run 1 stays historical evidence under its own
  architecture hash and is not an input to a new sizing without a new gate ruling.
