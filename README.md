# zynq-fabricmap

Device-local fabric cartography on a Zynq-7000 (XC7Z010): can a board map enough
of its own fabric to guide its own evolution — and is map-guided evolution
measurably safer or better than raw mutation?

**Status (2026-08-14): three bit classes are address-certified; Claim B round 1's
reachability result is complete; the erratum-006 carrier is published, accepted by the
host-side gates, and its no-op calibration now passes on silicon — the first complete
write-and-readback transaction this line has achieved on a board.**

- `data/` is frozen and self-verifying; the approach is ratified (see below).
- **`clb_lut_init`** and **`clb_mux`** are certified host-side (address prediction).
- **`clb_ff_config` is certified**: the 184-specimen staging was published and accepted,
  then measured and certified — **154 of 154 holdout address predictions correct, FP=0,
  FN=0**, coverage 176/176, semantic identity 154/154 reported independently. Certificate
  1.6.0 at `gate_runs/run_2026_08_05_ff/certificate.json`.
  **Those 154 predictions are now spent**: a new holdout claim needs a fresh preregistered
  commitment.
- **Claim B round 1 remains a DRAFT** (`docs/claimb_preregistration.md`) — map-guided vs
  random-safe mutation over the certified `clb_lut_init` universe. Its production
  reachability report is complete at 6/6 LUTs, but the evaluation loop and budget are not
  frozen: they still depend on a successful measured calibration.
- **Board engineering has happened.** Carrier builds through erratum 005 were loaded on
  the verification board and engineering no-op transactions exercised the ICAP path. Every
  run through erratum 005 stopped fail-closed at `F_READBACK` inside envelope 0; the
  erratum-005 dump contained real configuration data, but from the wrong location.
  **Erratum 006's no-op then passed** (`evidence/calibration_noop_2026_08_14_erratum006/`):
  all three envelopes committed, 15/15 frames read back equal to the pinned base, `fault=0`,
  `rb_latency_valid=1`. ⚠ **This does not by itself prove the readback now addresses the
  requested frame**: all 15 pinned frames are all-zero, so a read of some other all-zero
  frame is byte-indistinguishable from a correct one. The discriminator is the
  known-answer mutation, which has not been run.

**Scope, stated plainly.** The bit-class certificates are **address prediction** — where a
feature's bits live in the bitstream. The board records are engineering validation of the
carrier, transport, guard and ICAP path; they are not a silicon-semantics certificate or a
Claim B evolutionary result. No known-answer mutation, scorer arm or A/B evolution run has
occurred.

## Claim B round 1 — where it stands

| piece | state |
|---|---|
| preregistration | **DRAFT** — `docs/claimb_preregistration.md`; §6 budget unfrozen |
| `local_map` 1.0.0 | built from the `clb_lut_init` certificate — 292 addresses, 12 frames, 6 LUTs |
| reachability | **complete** — production report selected 6/6 LUTs, discarded 20 draws, attainable ceiling 353, not exhausted; report committed under `gate_runs/claimb_round1_reachability_2026_08_10/` |
| carrier authority | erratum-006 `carrier.bit`, `post_route.dcp`, `phenotype_manifest` and bundle committed under `gate_runs/claimb_round1_carrier_2026_08_13_erratum006/`; publication, base and ECO gates accepted |
| ICAP write/readback path | 3 envelopes × 536 words = 6,432 bytes; **hardware-proven end to end on erratum 006** — all three envelopes commit in pass 1 and read back in pass 2, 15/15 frames equal to the pinned base, latency 1 word and valid on every envelope, `fault=0`, `recovery_required=0`, scorer never armed. Runs through erratum 005 never left envelope 0 |
| candidate gate | judges the **serialized** sequence, under two frame semantics |
| board identity gate | boardid/role/IDCODE/50 MHz, session- and epoch-scoped, no override |
| run log | `claimb_run_log` 1.0.0 |
| engineering device work | carrier loads and guarded no-op ICAP attempts were authorised and executed through erratum 005; every failed attempt stopped without mutation or scoring |
| **Claim B result** | **none yet** — preregistration remains draft; no known-answer mutation, scorer arm or paired A/B run has occurred |

### Carrier errata, in one place

The records are additive: an erratum does not rewrite the failure evidence that exposed it.

1. [Erratum 001](docs/claimb_erratum_001_static_routes.md) moved carrier safety from a
   zero-route-crossing rule that the device geometry cannot satisfy to final-bitstream
   invariance, while retaining cell isolation and making a no-op the first board test.
2. [Erratum 002](docs/claimb_erratum_002_ps7_axi3.md) added the missing AXI3-to-AXI4-Lite
   protocol bridge after an un-terminated GP0 read wedged the CPU.
3. [Erratum 003](docs/claimb_erratum_003_config_idcode_and_refusal.md) separated the
   configuration IDCODE from the JTAG IDCODE and made guard refusals return `OKAY` while
   latching a fault, rather than rebooting U-Boot through an AXI data abort.
4. [Erratum 004](docs/claimb_erratum_004_icap_readback.md) replaced the stage-buffer echo
   model with an independent ICAPE2 model and implemented the actual bit-swapped ICAP
   readback transaction and telemetry.
5. [Erratum 005](docs/claimb_erratum_005_fdro_contiguity.md), read together with its
   [correction](docs/claimb_erratum_005_correction_2026_08_13.md), conservatively made each
   frame a contiguous FDRO transaction. Its board run still stopped at `F_READBACK`, but
   returned bit-exact configuration data from a location `+604` words from the request.
6. [Erratum 006](docs/claimb_erratum_006_command_order.md) corrects the readback order to
   `RCFG -> NOOP -> FAR -> FDRO`. Its model, benches, mutations, Vivado build and publication
   gates pass, and on 2026-08-14 its no-op calibration **passed on silicon** where every
   earlier build faulted — the first board run to complete pass 2 at all. What that
   establishes is that the sequence is now legal to the device; the all-zero frame set
   means it does not yet establish the address.

## Cloning and Git LFS

The repository tracks staged specimen bitstreams and exact carrier `.bit`/`.dcp` authority
artifacts with Git LFS. A metadata-only review does not need to download those objects:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/14sea/zynq-fabricmap.git
cd zynq-fabricmap
```

To exercise the current production carrier gates, pull just the erratum-006 authority:

```bash
git lfs pull --include='gate_runs/claimb_round1_carrier_2026_08_13_erratum006/*'
python3 scripts/gate_carrier_base.py \
  --run-dir gate_runs/claimb_round1_carrier_2026_08_13_erratum006
python3 scripts/gate_init_eco.py \
  --run-dir gate_runs/claimb_round1_carrier_2026_08_13_erratum006
```

Use plain `git lfs pull` only when every staged specimen and historical carrier artifact is
needed. A pointer-only checkout is useful for source review, but it cannot verify production
artifacts: the production gates deliberately refuse LFS pointers in place of the pinned
bytes. GitHub's current LFS allowance and billing behavior are documented in
[Git Large File Storage billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs).

Three facts measured while building this, each of which constrains the experiment:

- the certified universe is **292 addresses, not the class's 2048** — the rest are named by
  the frozen DB but were never attested by a specimen pair;
- **no LUT is fully writable** (49/49/49/51/50/44 of 64), so a fitness may not assume a free
  64-bit INIT;
- **every certified bit has `expected_value = 1`** — there is no negated token in the set, so
  polarity handling is unexercised by round-1 data (see `docs/claimb_handoff.md`).

## Relationship to the other repos

This is the successor line to [zynq-autoehw](https://github.com/14sea/zynq-autoehw),
whose M1 closed at tag `m1-complete` with beats-random confirmed on silicon
(+113/1024, Set B), later reproduced bit-identically on a second die.

- It tests **Claim B** of `zynq-autoehw/docs/tech_report.md` — *a device-local
  map guides evolution better/safer than raw mutation*. Claim A (autonomous
  runtime) and the beats-random subclaim of Claim C are already settled there and
  are **not** re-litigated here.
- It is a **separate repo on purpose**: different claim, different board-risk
  envelope (bitstream/routing-level manipulation, not plumbing), different
  cadence (exploratory — it is expected to falsify its own ideas repeatedly).
  Keeping it out of zynq-autoehw leaves that repo's published M1 record frozen
  and citable.
- zynq-autoehw's own engineering debt (NV champion store, board-side replay
  bundle) is **not** here — it stays in that repo as an M1 engineering addendum,
  so the M1 record never points at remainders closed somewhere else.

Earlier lines, for provenance: [zynq-ehw](https://github.com/14sea/zynq-ehw)
(closed at v1.2.0), [zynq-xpart](https://github.com/14sea/zynq-xpart) (DFX / ICAP
/ prjxray), [zynq-agentctl](https://github.com/14sea/zynq-agentctl).

## What is already settled (read this before proposing anything)

`docs/kickoff_fuzz_and_map.md` is the audited prework, copied verbatim from
zynq-autoehw. Its load-bearing findings:

- **prjxray's zynq7 fabric rules are md5-identical to artix7** — 7-series shares
  one fabric. "Partial coverage" is a misleading label; the real gaps (GTP, PCIe,
  XADC MONITOR, cells_data/gridinfo) do not intersect what evolution needs.
- **Recommendation, not yet ratified:** do *not* try to complete prjxray. Extract
  and freeze the needed subset, then certify it per bit-class with our own
  Vivado specimen-diff prediction gate (the EP4CE6 mine → holdout → emit →
  fresh-gold TP=1/FP=0 method). Certificates become the authority; prjxray is
  demoted to an index.
- **Fuzz × evolve has three levels**: offline fuzz feeds a whitelist / on-board
  self-cartography / evolution *as* fuzzing (the map is a byproduct of search).
  The third is the unclaimed territory.
- **Safety split**: content-bit classes (worst case: logic garbage) are fine on
  the EBAZ boards; autonomous *routing*-class fuzzing goes to sacrificial
  hardware, never the working boards.

## ★ Ratified 2026-08-02 — the approach is now decided, not proposed

The prework's core recommendation is **approved by the user**. It is no longer a
recommendation; it is what this repo does:

- **Do not complete prjxray.** Its fuzzers are archived and pinned to Vivado
  2017.2, there is no ground truth in them, and nothing here consumes them.
- **Extract the needed subset and freeze it into `data/`.** The 2026-07-11 audit
  established that the zynq7 fabric rules are md5-identical to artix7 (7-series
  shares one fabric) and that the real gaps — GTP, PCIe, XADC MONITOR,
  cells_data/gridinfo — do not intersect what evolution needs. Licence is CC0, so
  vendoring is clean.
- **Certify per bit-class with our own Vivado specimen-diff prediction gate**,
  porting the EP4CE6 method (mine → holdout → emit → fresh-gold, TP=1 / FP=0).
  The certificates become the authority.
- **prjxray is demoted to an index**, and completion becomes lazy: targeted
  mini-fuzz only where a certificate actually fails.

This evidence now feeds the certificate-inherited `local_map` 1.0.0 for Claim B. The
consumer-owned authority schema is `schemas/local_map.schema.json`; the independent
`host/verify_local_map.py` re-derives the complete universe, polarity, indexes and ECC
collateral from the production certificate and frozen manifest. It does not trust the
producer's map builder.

### First drop, concretely

Pure host-side, zero board risk. Split per the inversion below:

| side | owns |
|---|---|
| Claude | the extraction + certification infrastructure: subset extractor into `data/`, Vivado specimen-diff harness, the prediction gate itself, and its TP/FP accounting |
| author | `local_map` schema instantiation, host verifiers over the emitted certificates, and known-answer fixtures the gate must reproduce |

### Landed so far

**Step 1 — extraction + freeze format (done).**

```bash
scripts/extract_prjxray_subset.py --src /path/to/prjxray-db   # (re-)freeze
scripts/extract_prjxray_subset.py --verify                    # integrity gate, no deps
```

- `data/subset_spec.json` declares the subset and the bit-class taxonomy; it is the
  only place the subset is defined.
- `data/prjxray/` holds 46 verbatim upstream files (16.6 MB) from prjxray-db
  `0a0adde`, CC0; `data/MANIFEST.json` pins every hash, count and provenance field.
- **10,896 features, 100% classified** into six classes — `clb_lut_init` (2048),
  `clb_mux` (500), `clb_ff_config` (176), `clb_lutram` (42), `int_pip` (7272),
  `ppip_bitless` (858). An unclassifiable feature aborts the extraction on purpose.
- The 2026-07-11 "7-series shares one fabric" audit is now **machine-checked at every
  extraction**: 28/34 rule files byte-identical to artix7, 2 rule-equivalent
  (provenance labels only) — and 4 CLB mask files carry a real 4-bit delta, recorded
  rather than smoothed over (`data/README.md`).
- Format contract for the other author: `docs/freeze_format.md`, including the
  `certification` slot the prediction gate writes back into and its staleness rule.

**Step 2 — host-side certification infrastructure (active).**

- Certificate schema 1.6, multi-cell specimen attestation 2.0, exact staging-set
  validation, the independent host verifier and known-answer fixtures are shipped.
  Feature records preregister both endpoints; group records retain their
  absolute-assignment model.
- `clb_lut_init` is certified at holdout 262/262 with fp=0/fn=0.
- `clb_mux` is certified at 16/16 falsifiable address passes, with 16 vacuous
  exclusivity diagnostics and semantic identity 16/16 reported separately.
- `clb_ff_config` is preregistered at full 176/176 coverage. Its formal
  184-specimen/120-P&R builder exists; the mine instance is built and independently
  diagnosed at TP=22, FP=0, FN=0 (23/184 specimens, holdout untouched). The host-side
  attestation converter and stager (`scripts/gate_stage_ff_formal.py`,
  `docs/ff_staging_producer.md`) exist and need no Vivado run.
  **The first full holdout run (2026-08-06) built 184/184 and is refused**: one
  committed holdout pair is structurally incomparable (T2, dedicated net `w1` routed
  differently at `SLICE_X25Y25`), so it may not be staged or measured, and the
  affected prediction is not dropped. Preserved in
  `evidence/ff_holdout_2026_08_06_t2fail/`. The stop condition stays a stop condition:
  T1/T2 is not relaxed after firing. The run verdict is now `ready_for_measurement`
  (`ff_formal_run/2`), the builder's exit status follows it, and the stager recomputes
  the whole structural gate itself before staging anything.
  **The specimen design now pins dedicated-net routing** (`docs/ff_builder_design.md`,
  addendum 2026-08-07): the nine are recomputed from the netlist, the six with an
  interconnect route are routed first into an empty fabric and frozen, the three pad
  nets are required to stay intrasite, and both phases of all nine are recorded in
  `readback.tsv` under `routepin.` — pinned by that artifact's hash and recomputed from
  raw fields by both the builder and the gate. That change invalidates all 184 previous
  artifacts, which are preserved under
  `build/gate_ff_formal.invalidated_t2fail_2026_08_06/`. Next: rebuild the mine
  instance and evaluate its gate; a full rebuild that comes back 168/168 is what would
  answer whether `SLICE_X25Y25` is repaired.
- `clb_lutram` has inventory, isolation and real-diff evidence, but no commitment or
  certificate. `int_pip` and `ppip_bitless` remain unstarted.

## Planning decisions carried in (2026-08-02)

**The first drop inverts the usual division of labour.** In the sibling repos the
default is: the other author writes code, Claude gates and boards it. That
assumes host-side logic. Extraction + per-bit-class certification is a Vivado
specimen-diff activity end to end, so here **Claude builds the infrastructure and
the author writes schemas, host verifiers and known-answer fixtures against it.**
Rationale is concrete: in the M1 engineering addendum, five of six blockers
across six rounds were invisible on the authoring side (no RISC-V toolchain, no
Vivado). Keeping the default split for a Vivado-centric drop would make that
ratio worse. See `zynq-autoehw/docs/workflow.md`.

**No sacrificial hardware is being bought yet.** The prework's safety split says
content-bit classes are safe on the EBAZ boards; only *routing*-class autonomous
fuzzing needs sacrificial silicon. The XC7K70T's original rationale is also
materially weaker than when it was proposed — the 2026-07-11 prjxray audit killed
the coverage argument, four spare same-part Zynqs killed the sacrificial-economics
argument, and its J7 UART header is unpopulated while this whole control plane is
UART-mailbox based, a cost the old plan never carried. **Revisit only when this
line actually hits the routing wall.**

## Hardware

Board plumbing is copied in from zynq-autoehw and is deliberately board-agnostic
(it drives both an EBAZ4205 and an EBAZ4203):

- `scripts/board_serial.py` — prompt regex matching `zynq-uboot>` (4205 vendor
  U-Boot) and `Zynq>` (4203 mainline U-Boot); `/dev/ebaz-uart` follows either
  board's CH340.
- `scripts/board_set_fclk50.py` — pins FCLK0 to the 50 MHz signoff clock by
  *decoding the PLLs*, because the divisor constant is board-specific: the 4205's
  magic `0x00200a00` written onto a 4203 (IO PLL 1600 MHz, not 1000) yields
  80 MHz, silently out of signoff.
- `scripts/board_uboot_fpga_load.py` — `loady` + ymodem + `fpga loadb`.
- `scripts/board_carousel_extract.py` — rebuilds a mailbox carousel
  **positionally** from a monitor trace, never from a first-seen set.

Copies, not shared code: the source repos are never modified from here.

## License

Original project content is licensed under the Apache License, Version 2.0; see
[`LICENSE`](LICENSE) and [`NOTICE`](NOTICE). The vendored Project X-Ray database subset in
`data/prjxray/` remains under its accompanying CC0-1.0 terms and is not relicensed by the
top-level Apache license. Vivado-generated bitstreams and checkpoints are retained as exact
reproducibility artifacts; Vivado itself and the AMD documentation cited by this repository
are not redistributed here.
