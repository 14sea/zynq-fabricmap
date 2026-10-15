# zynq-fabricmap

Device-local fabric cartography on a Zynq-7000 (XC7Z010): can a board map part of its
own fabric by itself, and does that map make its own evolution measurably better?

Everything here runs on a single EBAZ4203 (`17A6`) over a UART mailbox, with a host that
acts only as notary, auditor and collector. Every board session needs an owner-signed
ruling pair, is judged fail-closed by an offline adjudicator, and is archived as observed.
Nothing is re-run to make a result look better.

## Where the line is (2026-10-14, S3)

| stage | question | state |
|---|---|---|
| **B1** autonomous mapping | can the board build a correct map of 292 certified LUT-INIT bits from its own probes? | **complete** — carrier qualified by B1Q PASS on `17A6` (2026-09-08, attempt 4); B1 mapping PASS later that day, self-map `c6a4b23e…` frozen |
| **B2** map utility | does a search that consults that map reproduce, record for record, the host-predicted outcome? | **complete — PASS / SUPPORTED, p = 0.01953125** (lifecycle 2 on `17A6`, 2026-09-16..17: B2Q PASS, two B2 sessions PASS covering the nine preregistered pairs, pooled primary 8/1/0 equal to the prediction; `docs/b2_result_2026_09_17.md`) |
| **B3** closed loop | map → evolve → re-map on the board | **complete — PASS / SUPPORTED, p = 0.00390625** (lifecycle 2 on `17A6`, 2026-10-14..15: B3Q -01 HOLD / -02 PASS; eight one-pair B3 sessions, nine attempts — session 0's first attempt LOST at the carrier configuration, then eight PASS sessions, pairs 0–7, 24 040 records; the pooled primary 8 positives / 0 negatives / 0 ties, equal to the preregistered prediction, Δ1 = [11, 9, 7, 7, 4, 6, 9, 2]; the secondary outcome reported without a threshold; result document `docs/b3_result_2026_10_15.md` — **lifecycle 2 closed on the owner's review, 2026-10-15**). Manifest S3 `258bb14c…`, no post-B3 transition. Standing: the formal S2 and S3 clean-tree proofs did NOT pass (two pinned-test defects, accepted for engineering purposes under the named exceptions, `docs/b3_s2_proof_exception_2026_10_14.md`; the S3 node serves as §8's final proof by the owner's ruling of 2026-10-14); the image is board_ready with image_ready=false / FINDINGS; sessions 3 and 7 carried heartbeat-burst byte deletions absorbed by rule v07 (not counted toward the stop-loss, which stands). The eight PASS main sessions archived in form (c) with a fresh-restore re-judge (`evidence/b3/main_preparation_2026_10_14/`). |
| **B4** expansion | FF and routing classes, on sacrificial silicon | not started |

Standing constraints that no PASS lifts on its own:

- **Transport stop-loss.** Single-byte deletions on the CH340 UART path were observed on
  WSL and on native Linux, cause unresolved. The lifecycle-2 B2Q and both B2 sessions each
  ran under its own explicitly authorised, session-scoped exception written into that
  session's ruling pair; every exception was spent by its session. The stop-loss itself is
  not lifted; any further board session needs its own transport disposition.
- **Owner rulings only.** Rulings live in `rulings/` (gitignored), are bound to the exact
  manifest, preregistration and image digests, and are consumed by the run.
- **Evidence is never rewritten.** Corrections are added beside the original.

B2's lifecycle 2 ran S0 manifest → S1 freeze → **B2Q** on silicon → S2 qualify → S3 plan →
two B2 sessions → pooled primary, and **closed at S3, manifest `aec84514…`** — the
preregistration defines no post-B2 transition and none was added (`docs/b2_preregistration.md`
§8, §8a). Lifecycle 1 stopped before its B2 sessions (`docs/b2_s3_frozen_test_decision_2026_09_16.md`).

## Verify it yourself

The clone below is sufficient for source review. Production verification also needs
the required LFS payloads, the pinned B1/B2 build outputs (the B2 binary and ELF are
not tracked), and the pinned `zynq-psoracle` checkout. Verification also requires the
ignored B1/B2 artefacts at their pinned hashes; preserve or restore them before verifying.
Reproducing and checking the
builds additionally requires the recorded toolchain and Xilinx embeddedsw inputs;
see `evidence/b2/build_evidence.json` and `docs/b2_section7_submission_2026_09_12.md`.
The commands below assume those prerequisites have been restored. This is not a
claim that a pointer-only clone can pass the production gates.

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/14sea/zynq-fabricmap.git
cd zynq-fabricmap
# S3 verify needs the production re-adjudicator, which the CLI deliberately does not supply:
python3 -B -c 'import sys,json; sys.path.insert(0,"host"); import b2_manifest as bm, b2_runner as rn; \
  m=json.loads(bm.MANIFEST.read_text()); v=bm.verify(m, readjudicate=rn.readjudicator(m)); \
  print(v["stage"], v["qualified"], v["refusal"])'      # S3 True None
python3 -B host/b2_test_report.py                     # whole suite; needs a clean tree
python3 -B host/verify_local_map.py                   # the B1 self-map against the certificate
scripts/extract_prjxray_subset.py --verify            # the frozen prjxray subset
```

The B2 manifest's `verify` re-hashes the image, re-verifies the B1 lineage and the pinned
instrument (`zynq-psoracle` at `689dde1`, located by `PSORACLE_ROOT`, default `/home/test/zynq_psoracle`), and re-adjudicates
the pinned B2Q evidence. `b2_test_report.py` writes `evidence/b2/tests/test_report_<UTC>.json`
and only sets `clean_tree_proof` when HEAD and both worktrees are clean before and after.

## Layout

| path | what |
|---|---|
| `docs/` | preregistrations, architecture, every owner review as received (`*_review_*.md`), the roadmap (`autonomous_cartography_roadmap.md`) |
| `manifests/` | `b1_manifest.json`, `b2_manifest.json` and their instrument pin tables — the frozen authority for each stage |
| `host/` | runners, adjudicators, lifecycle tools (`b2_runner.py`, `b2_manifest.py`, `b2_adjudicate.py`, `b1_*`) |
| `b3/` | the B3 lifecycle-2 line, self-contained: host tools (`b3/host/`), board image sources and host twins (`b3/firmware/`), tests (`b3/tests/`), schemas |
| `firmware/` | the B1 and B2 board images (bare-metal, on the P3 instrument's BSP) |
| `evidence/` | every board session and review, as observed (`evidence/b1q/`, `evidence/b2/`, `evidence/b3/b3q_*`); B3's gate, prediction, build evidence, lifecycle transitions and clean-tree proofs (`evidence/b3/`) |
| `data/` | the frozen, self-verifying prjxray subset (CC0) — 10,896 features in six classes |
| `gate_runs/` | bit-class certificates and the carrier authority (LFS) |
| `tests/` | the suite the test report runs (B1, B2, B3, transport) |
| `scripts/` | board plumbing (serial, FCLK0 pinning, U-Boot ymodem load) and the extractor |

## History, briefly

- **2026-07/08** — prjxray subset frozen; `clb_lut_init`, `clb_mux`, `clb_ff_config`
  certified host-side by specimen-diff prediction (TP=1/FP=0 method).
- **2026-08-20** — Claim B's original ICAP route stopped under a stop-loss: the write
  landed at the intended frame but the carrier's readback interlock faulted
  (`docs/claimb_findings.md`).
- **2026-09-05** — the line re-shaped into B1–B4 (`docs/autonomous_cartography_roadmap.md`).
- **2026-09-06..08** — four B1Q sessions: LOST, PASS-but-unpinnable, LOST, PASS.
  Attempt 3's adjudicator returned HOLD; its session disposition was LOST. Carrier qualified.
- **2026-09-07..14** — the transport investigation (WSL and native Linux, loopback and
  board-side controls), observations only, stop-loss kept.
- **2026-09-14** — first B2Q on silicon: PASS, S2 qualified (lifecycle 1).
- **2026-09-16** — lifecycle 1's S3 plan was legal but contradicted a test frozen in the pin
  table at S1; contained, not patched (`docs/b2_s3_frozen_test_decision_2026_09_16.md`).
  Lifecycle 2 started over on `b2-lifecycle-2`: pinned-test audit, preregistration v0.3,
  new pin table, S0 → S1 (post-freeze proof) → B2Q PASS on `17A6` (3016.40 evals/h) → S2 →
  S3 (final clean-tree proof), each step a separately authorised unit.
- **2026-09-16..17** — the two B2 sessions on `17A6`, pairs 0–4 (6012 records) and 5–8
  (4810 records), both PASS / COMPLETED; the pooled primary over the nine pairs equalled
  the preregistered prediction (8/1/0, p = 0.01953125, SUPPORTED) — **B2 PASS**
  (`docs/b2_result_2026_09_17.md`). Session evidence archived in a hybrid form with
  executable fresh-restore / re-judge scripts.
- **2026-09-17** — B3 lifecycle 1 stopped at its prediction preflight: the fixed nine-pair
  prediction did not support its second required primary, which lifecycle 1 had left
  underpowered (`docs/b3_lifecycle1_stop_decision_2026_09_17.md`). Archived on
  `b3-lifecycle-1`, not merged.
- **2026-09-17 onward** — B3 lifecycle 2 on `b3-lifecycle-2`: one confirmatory primary (Δ1),
  Δ2 reported as secondary; gate run 1 F1 PASS (B* = 1000, N = 8) and the prediction
  preflight (primary 8/0/0, p = 1/256). Then host-only units, each reviewed separately:
  records, session, adjudicator, runner, manifest, pins, test report, the §9 test audit, and
  the board image in six stages. Image stages 1–6 are closed; stage 5 passed engineering
  acceptance, with image_ready=false. B3Q documents, the pin table and the S0 manifest are
  committed.
- **2026-10-14** — S1 freeze: preregistration v0.3.1 `e89c5677…` pinned, image marked
  board_ready by the owner with the stack assessment still `FINDINGS` (`evidence/b3/s1_2026_10_14/`);
  manifest `bb917ec7…`. Post-freeze proof `test_report_2026-10-14T090238Z.json`: whole suite OK
  (2096 / 793 / 792, zero skips), clean_tree_proof true, bound to `bb917ec7…`.
- **2026-10-14** — B3Q on `17A6`, one ruling pair per attempt: -01 HOLD (`35d81c2`, a heartbeat
  lost to an 80-byte console deletion; the two other CRC drops are the forced retry controls),
  -02 PASS (`76534b7`, no transport loss). S2 qualify from -02 only: manifest `bea08769…`,
  calibration 3180.049965139327 evals/h × 0.85 → eight one-pair sessions (`evidence/b3/s2_2026_10_14/`).
  The transport stop-loss stands. S2 clean-tree proof `test_report_2026-10-14T144023Z.json`: **not passed**
  (one isolation ERROR in a pinned test, `docs/b3_s2_proof_exception_2026_10_14.md`); S2 accepted under the
  owner's named engineering-acceptance exception, with the plan module re-verified in isolation (32 / 32, tree
  and removal shadow) and a fresh S2 verify.
- **2026-10-14** — S3 plan: `b3_plan.py --rate-per-hour 3180.049965139327` regenerated the canonical
  `evidence/b3/plan.json` (stop rule: no finding, primary 8/0/0 p = 1/256; the prediction byte-identical),
  pinned as manifest `258bb14c…` — eight sessions of one pair, 24 040 records. S3 clean-tree proof
  `test_report_2026-10-14T180234Z.json`: **not passed** (the S2 isolation ERROR plus two FAILs of a second
  stage-latent defect: the pinned seed header's plan digest, `docs/b3_s2_proof_exception_2026_10_14.md`); S3
  accepted under the owner's narrowly extended engineering-acceptance exception, with the header's divergence
  verified to be exactly the digest line (negative controls refused), the plan module 32 / 32 on the tree and on
  a removal shadow, and a fresh S3 verify. No B3 ruling pair, no board session.
- **2026-10-14..15** — the B3 main experiment on `17A6`: main-experiment preparation (`evidence/b3/main_preparation_2026_10_14/`,
  the form (c) archiver and the fresh-restore re-judge); session 0 attempt 1 LOST at the carrier configuration (`7677d23`),
  attempt 2 PASS (`2e99381`); sessions 1–7 PASS (`03de515`, `50b5420`, `8cd83f1`, `0ff8bd1`, `da973b7`, `fe2f2d1`, `283aced`),
  each under its own ruling pair, boundary record and transport disposition, each re-judged from a fresh restore; the pooled
  primary PASS 8 / 0 / 0, p = 1/256, every quantity equal to the prediction (`evidence/b3/b3_primary_2026-10-15/`, `4e872c1`);
  the result document `docs/b3_result_2026_10_15.md` (owner-reviewed; lifecycle 2 closed).
- **2026-10-14** — main-experiment preparation (owner's ten rulings on the batch scope draft): form (c) archiver
  and the shared fresh-restore re-judge (`evidence/b3/main_preparation_2026_10_14/`), synthetic SEARCH and B3Q round
  trips with the named negative cases, the production path over the real B3Q -02 archive; the S3 node ruled to serve
  as §8's final proof for engineering purposes. No ruling pair, no board session, no push.
- **2026-10-04..06** — image stage 5: the application, a reproducible cross-build (two clean
  builds byte-identical) and its build evidence landed; the stack assessment of the final ELF
  (`b3/host/b3_image_stack.py`) went through three reviewed rounds. Under the strict reading
  ruled on 2026-10-06 — a write is taken to miss a callback cell only when the bytes it can
  reach are shown to, never because of the object it was meant for — the committed image's
  assessment is `FINDINGS`: each routine's unplaced writes are listed by address, no stack
  bound is published, `image_ready` is false. Which of those writes to prove next is open.
- **2026-10-07..12** — stage 5 closed on an engineering exit (the owner, 2026-10-12): the
  requirement to prove the whole image memory-safe first was withdrawn; the image's own PCAP DMA
  became a write of the inventory (b3-image-stack 1.8.0); the assessment of the final ELF is
  accepted with its established, conditional and diagnostic results and every remaining finding
  classified (`docs/b3_stage5_engineering_acceptance_2026_10_12.md`). The formal result stays
  `FINDINGS`, `image_ready` false; no board session, pin table, S0 or board_ready is authorised.

The full running log that used to be this README is preserved verbatim at
`docs/README_archive_2026_09_14.md`.

## Related repositories

Successor to [zynq-autoehw](https://github.com/14sea/zynq-autoehw) (M1 closed at
`m1-complete`). Instrument and oracle: [zynq-psoracle](https://github.com/14sea/zynq-psoracle)
(archived at `689dde1`, pinned here). Earlier lines: [zynq-ehw](https://github.com/14sea/zynq-ehw),
[zynq-xpart](https://github.com/14sea/zynq-xpart), [zynq-agentctl](https://github.com/14sea/zynq-agentctl).

## Git LFS

Specimen bitstreams and carrier `.bit`/`.dcp` artifacts are in LFS. A pointer-only clone is
fine for source review; the production gates refuse pointers in place of the pinned bytes.
Pull only what a gate needs, e.g.
`git lfs pull --include='gate_runs/claimb_round1_carrier_2026_08_13_erratum006/*'`.

## License

Apache-2.0 for original content (`LICENSE`, `NOTICE`). The vendored prjxray subset in
`data/prjxray/` stays CC0-1.0. Vivado-generated artifacts are kept for reproducibility only.
