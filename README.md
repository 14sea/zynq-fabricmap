# zynq-fabricmap

Device-local fabric cartography on a Zynq-7000 (XC7Z010): can a board map part of its
own fabric by itself, and does that map make its own evolution measurably better?

Everything here runs on a single EBAZ4203 (`17A6`) over a UART mailbox, with a host that
acts only as notary, auditor and collector. Every board session needs an owner-signed
ruling pair, is judged fail-closed by an offline adjudicator, and is archived as observed.
Nothing is re-run to make a result look better.

## Where the line is (2026-09-14)

| stage | question | state |
|---|---|---|
| **B1** autonomous mapping | can the board build a correct map of 292 certified LUT-INIT bits from its own probes? | **complete** — carrier qualified by B1Q PASS on `17A6` (2026-09-08, attempt 4); B1 mapping PASS later that day, self-map `c6a4b23e…` frozen |
| **B2** map utility | does a search that consults that map reproduce, record for record, the host-predicted outcome? | **S2 QUALIFIED** — first B2Q PASS on silicon (2026-09-14), calibration 2976.98 evals/h pinned; S3 plan not yet pinned; no B2 mapping session authorised |
| **B3** closed loop | map → evolve → re-map on the board | host-only architecture (`docs/b3_architecture.md`) |
| **B4** expansion | FF and routing classes, on sacrificial silicon | not started |

Standing constraints that no PASS lifts on its own:

- **Transport stop-loss.** Single-byte deletions on the CH340 UART path were observed on
  WSL and on native Linux, cause unresolved. The 2026-09-14 B2Q ran as one explicitly
  authorised exception; any further board session needs its own transport disposition.
- **Owner rulings only.** Rulings live in `rulings/` (gitignored), are bound to the exact
  manifest, preregistration and image digests, and are consumed by the run.
- **Evidence is never rewritten.** Corrections are added beside the original.

The lifecycle B2 is on: S0 manifest → S1 freeze → **B2Q** on silicon → **S2 qualify** (here)
→ S3 plan → B2 sessions. See `docs/b2_preregistration.md` §8.

## Verify it yourself

The clone below is sufficient for source review. Production verification also needs
the required LFS payloads, the pinned B1/B2 build outputs (the B2 binary and ELF are
not tracked), and the pinned `zynq-psoracle` checkout. Reproducing and checking the
builds additionally requires the recorded toolchain and Xilinx embeddedsw inputs;
see `evidence/b2/build_evidence.json` and `docs/b2_section7_submission_2026_09_12.md`.
The commands below assume those prerequisites have been restored. This is not a
claim that a pointer-only clone can pass the production gates.

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/14sea/zynq-fabricmap.git
cd zynq-fabricmap
# S2 verify needs the production re-adjudicator, which the CLI deliberately does not supply:
python3 -B -c 'import sys,json; sys.path.insert(0,"host"); import b2_manifest as bm, b2_runner as rn; \
  m=json.loads(bm.MANIFEST.read_text()); v=bm.verify(m, readjudicate=rn.readjudicator(m)); \
  print(v["stage"], v["qualified"], v["refusal"])'      # S2 True None
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
| `firmware/` | the B1 and B2 board images (bare-metal, on the P3 instrument's BSP) |
| `evidence/` | every board session and review, as observed (`evidence/b1q/`, `evidence/b2/`) |
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
- **2026-09-14** — first B2Q on silicon: PASS, S2 qualified.

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
