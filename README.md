# zynq-fabricmap

Device-local fabric cartography on a Zynq-7000 (XC7Z010): can a board map enough
of its own fabric to guide its own evolution — and is map-guided evolution
measurably safer or better than raw mutation?

> **▶ 2026-09-05, compatibility review PASS on image `300b12b1…` (v2.3.1, pushed at `3955b17`) — [`docs/b1_compatibility_review_2026_09_05_v231.md`](docs/b1_compatibility_review_2026_09_05_v231.md). Next: the owner's freeze (prereg sha256 into the manifest, `board_ready`), then the B1Q ruling pair. Still nothing frozen, no ruling, no board contact.**
>
> **▶ 2026-09-05, v2.3.1 (local): the owner's recheck of v2.3 found the TERM's closing-baseline mark set by any scored baseline (hidden by the harness's incomplete priming); fixed in firmware (`note_scored`, the mark only at the closing baseline), the harness primes through the application's own bookkeeping, tests assert the mark both ways. New image `300b12b1…`; `31663e2d…` withdrawn. Compatibility review still to be redone on the new image. Nothing frozen, no ruling, no board contact.**
>
> **▶ 2026-09-05, compatibility review HOLD → v2.3 (local): the application's SIGNREF branch continued the session after a gate refusal (the instrument's behaviour), against B1's "unscored ends the epoch" — fixed in firmware, and now exercised on the REAL `b1_app.c` off-board by the host application harness (`tb/b1/hostapp`: stub BSP, fake memory map, scripted host; four refusal scenarios, all end the epoch). New image; `54b00663…` withdrawn; the compatibility review is to be redone on the new image — [`docs/b1_package.md`](docs/b1_package.md) §0, [`docs/b1_compatibility_review_2026_09_05.md`](docs/b1_compatibility_review_2026_09_05.md). Nothing frozen, no ruling, no board contact.**
>
> **▶ 2026-09-05, PUSHED: the B1 v2.2.4 package is on `origin/main` with the owner's approval; v2.2.5 closes two evidence gaps found in the owner's post-push check (the offline adjudicators now check the preregistration document's bytes, not only its digest; the build evidence now records every translation unit `build.sh` compiles, every header, and the toolchain's runtime objects and libraries) — [`docs/b1_package.md`](docs/b1_package.md) §0. The sequence the owner fixed: compatibility review → freeze → B1Q ruling pair; no board contact before that. Nothing frozen, no ruling, `board_ready` false, not qualified; `zynq-psoracle` unchanged.**
>
> **▶ 2026-09-05, v2.2.3: the ruling envelope's key set is exact — an envelope re-armed with ruling fields is refused by `verify()` even with every hash updated (the owner's counter-example is a test). Green on the clean tree; awaiting the owner's go for push.**
>
> **▶ 2026-09-05, v2.2.2: archived rulings are inert envelopes (bytes + sha256, no ruling fields) that every parser refuses — an archive is never a second authorisation; a failed archive leaves nothing behind. Green on the clean tree; awaiting the owner's go for push.**
>
> **▶ 2026-09-05, final: v2.2.1 — the session artifacts (manifest bytes, both rulings) are archived and verified BEFORE the ruling is claimed and the port is opened, the order is a test, and the qualification chain also binds `summary.ruling` and the provisioning ruling's digest — [`docs/b1_package.md`](docs/b1_package.md) §0. Green on the clean tree; awaiting the owner's go for push / compatibility review / freeze. Still no ruling, no board contact.**
>
> **▶ 2026-09-05, latest: the owner's short review of v2.1 found four host-side blockers in the evidence chain and the manifest lifecycle; v2.2 closes them and STOPS for the final short re-review — [`docs/b1_package.md`](docs/b1_package.md) §0.** The manifest lifecycle no longer dead-locks (`board_ready` survives a refresh while the image pins hold; a legacy `carrier.qualification` value migrates to null; one `Lifecycle` test runs freeze → B1Q → pin → mapping preflight); a B1Q log must name the qualification plan / prediction / pin table as its inputs; the qualification chain is closed (the bound manifest's bytes and both rulings are copied into the evidence and re-bound, the token comes from the run log, the current manifest may differ from the bound one only in the qualification state); the mapping adjudicator requires the derived flag to agree with the evidence. **Still nothing frozen, no ruling, no push, no board contact; `zynq-psoracle` unchanged.**
>
> **▶ 2026-09-05, late night: the owner's review of v2 — noninterference and the init order stand, four blockers remain — is closed in v2.1; STOPPED for the short re-review — [`docs/b1_package.md`](docs/b1_package.md) §0.** The adjudicator no longer drops schema findings and re-verifies the plan / prediction / pin table inside `adjudicate()`; every preregistration gate is an exact constant with an entry-point negative test (probe-9 confidence-1 accuracy 292/292, final confidence-2 292/292 with no confidence-1 cohort, full confirmation at 301, 32/0/0 pairs); the carrier's qualification is an **evidence chain** (a B1Q session under its own ruling pair — runner, adjudicator, seed 176 359 248, record, re-adjudication on every use — [`docs/b1_carrier_qualification.md`](docs/b1_carrier_qualification.md)) from which `qualified` is derived; two sessions, four rulings; no host-attested reply control on the board. Drift cleaned (manifest sections derived from the tree, strata not "holdout", firmware header, standalone B1 test report, the legacy validator a refusal, normative docs in the pin table, semantic map validation). **Still nothing frozen, no ruling, no push, no board contact; `zynq-psoracle` unchanged.**
>
> **▶ 2026-09-05, night: the first B1 package FAILED review; the v2 package is delivered and STOPPED for the whole-package review — [`docs/b1_package.md`](docs/b1_package.md) §0.** The owner's five blockers: the P3 carrier pre-certifies every readout against the host-signed tables (circular), the opening baseline preceded the cartographer's init, the adjudicator was not fail-closed, the map v2 carried derived semantics, pins were incomplete. v2: a **B1 carrier** (`d85daef4…`, `SEMANTIC_GATE=0`, read-only VARIANT — [`docs/b1_carrier_contract.md`](docs/b1_carrier_contract.md), host-verified and awaiting its own qualification session [`docs/b1_carrier_qualification.md`](docs/b1_carrier_qualification.md)), a zero-table signer, a validator that refuses attested tables, an orchestrator with the session order fixed, a fail-closed adjudicator bound to the manifest / instrument / carrier, map v2 without polarity and with confidence snapshots, a fabricmap pin table, and an **end-to-end modelled 335-record session through the instrument's real host stack and validators** (truth PASS 335/335 audited; permuted HOLD; tampered words KILL). Image `54b00663…`; `7bc86a3f…` is WITHDRAWN / DEFECTIVE / NO-RUN. **Nothing frozen, no ruling, no board contact; `zynq-psoracle` unchanged.**
>
> **▶ 2026-09-05, evening: the B1 pre-board package is delivered and STOPPED for the whole-package review — [`docs/b1_package.md`](docs/b1_package.md)** (architecture [`docs/b1_architecture.md`](docs/b1_architecture.md), preregistration DRAFT [`docs/b1_preregistration.md`](docs/b1_preregistration.md)). The board maps the 292 certified bits from its own probes (9 code probes to a complete provisional map, 333 to a confirmed one), commits to its map hash in every record, and the host recomputes and scores it against the certificate the executable never saw. Image `7bc86a3f…` rebuilt byte-identically; every B1 test green on a clean tree. **Nothing frozen, no ruling, no board contact; `zynq-psoracle` unchanged.**
>
> **▶ 2026-09-05, latest: round 1′ is WITHDRAWN BEFORE FREEZE / NO-RUN, and the line is re-shaped — [`docs/autonomous_cartography_roadmap.md`](docs/autonomous_cartography_roadmap.md).** Four stages that can fail independently: B1 autonomous (blind) mapping on the known 292 bits with the certificate as hidden ground truth; B2 map utility on a carrier that passes a host-side discriminability gate (Claim B lives here now); B3 the closed loop; B4 expansion to FF and routing. Host = notary/auditor/endpoint/collector only. Everything without physical risk on `17A6` first; routing only later, on a provisioned sacrificial EBAZ4203 (`08EB`), never on the K7 pair. Nothing here is a ruling for board time.
>
> **▶ 2026-09-05, later: the round 1′ package is delivered at "ready for the board" and STOPPED there for the whole-package review — [`docs/claimb_round1prime_package.md`](docs/claimb_round1prime_package.md).** Preregistration DRAFT (not frozen), plan and prediction pinned, runner fail-closed, 57 tests. **Read its §0 first:** the host model shows the carrier's fitness is additive over the 292 bits; under this additive scorer the same-LUT structure has no interaction advantage, and the fixed round 1′ seed, budget and primary are predicted to saturate into a tie (every block +4 vs +4, falsifier 1 fires). That is a statement about this scorer and this round's primary, not about every operator or selection scheme; the board run would have measured that tie and 11 754 predicted known answers through the oracle. Still no board contact.
>
> **▶ 2026-09-05 ruling: Claim B is RESUMED — PREREGISTRATION PENDING (HOST-ONLY).** The owner ruled on the L6 package (`docs/claimb_l6_package.md` §0): both preconditions are met and the readback leg leaves PAUSED; what is authorised is host-only — the round 1′ preregistration, runner/validators/guards, model and replay tests, evidence index and candidate execution package, pushed as drafts but never marked FROZEN or given a board ruling before the whole-package review. **No board contact, power cycle, image load or Claim B execution until the next explicit ruling.** The budget must sit inside the evidenced 6763.9 s window; S #3's candidates are not Claim B data; every L6 seed is excluded; `zynq-psoracle` stays archived and read-only.
>
> **▶ 2026-09-05 update: the L6 package is delivered and the resumption ruling is requested — still PAUSED.** Both conditions of the 2026-09-01 ruling were met in `zynq-psoracle` on 2026-09-04 (prereg v0.7 `95d177a1…` passed: Q1 by the pinned calibrations C1 #6 / C2 #2, Q2 by the S #3 soak, 12 570 records in 6763.9 s meeting the registered 2-hour criterion, owner PASS scoped; the two-operator image `5deee74c…` passed P3 compatibility review and ran the four rel-v4 sessions C1 #6, C2 #2, S #2 and S #3); that repository is archived (adjudication `32d1460`, archive head `689dde1` after a doc-only narrative correction). The package and the request are [`docs/claimb_l6_package.md`](docs/claimb_l6_package.md). Until the owner rules there: PAUSED, zero data points, no board contact.
>
> **▶ 2026-09-01 update: RESUMPTION-ELIGIBLE, still PAUSED.** The stop-loss's "new mechanism" condition is met within scope by the PS/PCAP + P3 evidence (`docs/claimb_resumption_memo.md` §0); execution stays PAUSED until a calibration/soak preregistration and the two-operator image pass review.
>
> **▶ PAUSED, 2026-08-20 — Claim B's board programme is stopped under a stop-loss committed to
> in the prior session ruling.** A host-side review found no way to build a write-verification
> gate on the JTAG path without changing the measurement architecture, so the work is published
> as a negative result rather than continued. **The findings are
> [`docs/claimb_findings.md`](docs/claimb_findings.md)**; the review that triggered the stop-loss
> is [`docs/claimb_jtag_gate_review.md`](docs/claimb_jtag_gate_review.md). In one line: the
> candidate write lands at the intended FAR, the carrier's internal readback interlock faults on
> it, and the interlock's successes cover only degenerate all-zero content. **Claim B still has
> zero data points, and no board contact is authorised.** The status paragraph below is kept as
> written; its single-observation caveat was closed on 2026-08-20 by a second fault instance
> measured by the same JTAG method — replication, not an independent method.

**Status (2026-08-20): three bit classes are address-certified and Claim B still has zero data
points — but the question that blocked §9 step 6 for weeks is answered. The location sweep ran
on silicon, and in the post-fault state the intended frame `0x00400A20` **held the candidate
bit-for-bit**, with sixteen of sixteen positive controls exact in the same acquisition
(`evidence/location_sweep_2026_08_20/`). So for that transaction the write reached the frame it
asked for, and its `F_READBACK` stop is a **read-side disagreement**, not a lost write. ⚠ That
is **one direct observation** and is not yet closed by independent reproduction, and **§9 step 6
still does not pass**: the carrier's own readback interlock still faults, so `restore` and the
baseline re-run never execute. See [Where the line actually is](#where-the-line-actually-is).**

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
  reachability report is complete at 6/6 LUTs, but §6's evaluation loop and budget are not
  frozen and §10's freeze has not happened: they still depend on a successful measured
  calibration. **Anything produced against a draft is a pilot, by the document's own rule.**
- **Board engineering has happened.** Carrier builds through erratum 005 were loaded on
  the verification board and engineering no-op transactions exercised the ICAP path. Every
  run through erratum 005 stopped fail-closed at `F_READBACK` inside envelope 0; the
  erratum-005 dump contained real configuration data, but from the wrong location.
  **Erratum 006's no-op then passed** (`evidence/calibration_noop_2026_08_14_erratum006/`):
  all three envelopes committed, 15/15 frames read back equal to the pinned base, `fault=0`,
  `rb_latency_valid=1`. ⚠ **This does not by itself prove the readback now addresses the
  requested frame**: all 15 pinned frames are all-zero, so a read of some other all-zero
  frame is byte-indistinguishable from a correct one. The discriminator is the known-answer
  mutation — see below.
- **The known-answer mutation has been run, and it stops.** §9 step 6 — apply *one*
  precomputed LUT-INIT mutation — has been attempted on silicon and has never got past the
  same point. Four committed records, across separate builds, boots and power cycles, all
  read the same:

  > `known_answer stopped: the engine faulted during pass 2 of envelope 0: fault_code 8 (readback)`

  (`evidence/known_answer_2026_08_14_erratum006/`, `evidence/phase2_2026_08_15/known_answer_record.json`,
  `evidence/postfault_r4_step2_capture_2026_08_16/`, `evidence/postfault_r4_replication_2026_08_16/fault_capture/`.)
  Two things about that stop matter and are easy to misread. **The stop is raised by the
  fabric engine's own FAULT register, not by a content comparison** — the host-side
  readback-SHA-mismatch stop in `scripts/board_claimb_known_answer.py` has never once fired,
  so what is observed is "the engine says the readback went wrong", not "the bytes came back
  different". And **the restore payload, which travels the identical write path with only
  its content differing, completes both passes every time** — so this is content-dependent,
  not a dead readback path.
- **The scorer has never been armed**, and in the latest capture that is a reading off the
  wire rather than an inference: `CTRL_ARM` and `CTRL_MODE_HOLDOUT` are clear in all twelve
  `CTRL` writes of `evidence/postfault_r4_step2_capture_2026_08_16/`.

**Scope, stated plainly.** The bit-class certificates are **address prediction** — where a
feature's bits live in the bitstream. The board records are engineering validation of the
carrier, transport, guard and ICAP path; they are not a silicon-semantics certificate or a
Claim B evolutionary result. **No known-answer mutation has ever completed, no scorer arm
and no paired A/B evolution run has occurred, and Claim B's result count is zero.**

## Where the line actually is

Measured against the preregistration's own yardstick — §9's fixed seven-step first-contact
order — steps 1–5 pass, step 6 fails every time it runs, and step 7 has never started and
could not (the document is still a draft). Diagnosing step 6 has put the line four levels
below its goal:

```
L0  Claim B A/B run                      the goal — never started
L1  §9 step 6, known-answer mutation     STILL FAILS — but no longer for an unknown reason:
                                         the write is proven to land, the engine's readback
                                         interlock still faults, so restore and the baseline
                                         re-run never happen
L1' why does the engine's readback         <- the live question, no mechanism yet
    disagree while JTAG reproduces
    the frame exactly?
L2  locate the write                     ANSWERED ONCE, not closed: WRITE_LANDED_AT_THE_
                                         INTENDED_FAR, 16/16 controls (2026-08-20). Needs
                                         independent reproduction under the same identity.
                                         Phase 2's earlier attempt stays VOID
L3  fix post-fault JTAG readback (R4)    SOLVED and reproduced on 16 controls. Separately,
                                         the R4 instrument scaled on a fresh load to 5,144
                                         frames with 0 missing; post-fault step ④ stopped
                                         legally after 17 reads
L4  the sweep tool's control semantics   DONE (2.8.0)
```

**What the 2026-08-20 run did and did not settle.** Step ① loaded the canonical carrier on a
freshly powered board and swept all 5,144 frames with 16/16 controls: the candidate signature
was **absent** before any transaction, as a negative control requires. Step ③ built the
specified fault — `STATUS 0x04040082`, `FAULT 0x8`, pass 2 of envelope 0, matching the two
accepted 2026-08-16 records in recorded fault shape and decoded transaction trace. Step ④,
in that same boot, read `0x00400A20`
and found the candidate: the frame differs from the base at exactly words 50 and 51
(`0x0000100e`, `0x00005213`) and both were reproduced, all 101 words equal. A forensic read of
the fault's own staging copy in PS DDR (`fault/ddr_slot0_shutdown_read.json`) came back **all
zero** — undiscriminating on its own, but read against step ④ it says the readback path handed
over a zero frame while the addressed frame held the candidate. `RB_SKIP`, readback latency and
FDRO framing are the untested suspects. **Nothing here is a Claim B data point**, and the
location claim is one observation until it is independently reproduced.

**Phase 2's earlier location attempt (the original L2) is void, and its own artifact does not
say so — additively marked as of 2026-08-20 in
`evidence/phase2_2026_08_15/sweep/superseded.md`, which recomputes its controls at 0/16 and
leaves `verdict.json` byte-for-byte as the tool wrote it.** `evidence/phase2_2026_08_15/sweep/verdict.json`
searched all 5,144 frames and records `NOT_FOUND_COMPLETE`. That verdict may not be relied
on: in that same post-fault state the instrument reproduced **0 of 16** frames whose
contents were already known, so whole-frame equality was answering nothing there. The
committed controls (`evidence/phase2_2026_08_15/sweep/`, 16 captures with their child logs
and Tcl) are what makes this checkable without unpacking the archive. Whether that
`verdict.json`'s wording should be amended in place is an open question, deliberately left
to the repository owner, and **ruled 2026-08-20: the verdict file is never rewritten; the
correction lives beside it.**

**L3 is the one solid new result.** The startup-cycle recovery
`JSHUTDOWN -> 12 TCK -> JSTART -> 2000 TCK -> RCRC -> JSHUTDOWN -> 12 TCK`, derived from
UG470 v1.17 Table 6-6 and Table 10-4 (`docs/claimb_r4_protocol.md`), restores JTAG readback
of all sixteen known non-zero control frames from the specified `F_READBACK` fault state —
16/16 twice, on two separately built faults, across two power cycles, under one instrument
digest with byte-identical child Tcl (`evidence/postfault_r4_replication_2026_08_16/`).
⚠ Two limits stand: the control is **historical, not paired** (no non-R4 prefix was ever run
on either fault state), and it says **nothing about where the write landed**.

**L4 is done, off the board (2026-08-17).** `docs/claimb_location_sweep_spec.md` specified the
location sweep that later answered the write-location half of L1 once, and it recorded two defects in
`scripts/board_signature_search.py` that would have made that sweep meaningless: an intended hit
skipped the control block entirely and emitted a location verdict with **zero** controls read,
and `judge_positive_controls()` returned `INSTRUMENT_VALID` on a single matching frame without
ever looking at the unread ones — one right and fifteen never read passed. Both are closed in
`2.8.0`: all sixteen controls are read in every case, 16/16 exact is required before **any**
location verdict including the intended hit, the sweep does not start until they pass, and the
offline `--judge-only` path enforces the same rule so it cannot re-license what an acquisition
refused. Four new behavioural mutants hold it (25/25 in the harness). As predicted, this
changed `instrument_digest`, which hashes the script's own bytes. The 2026-08-20 procedure
therefore established its own fresh-load control under the new signature-search identity
`a20e56aa…`; the four older R4 acquisitions (`2.7.1` / `8d28dcf3…`) were not borrowed as its
control. The separate control-only identity remains `49c8dbce…`, with both identities pinned
in the tests.

**Agreed order from here** (ruled 2026-08-16, and now largely spent): ~~this README~~, ~~the
16/16 control semantics with their mutants offline~~, ~~the location sweep~~ — all three are
done, the sweep having run on 2026-08-20 under its own authorisation after an audit of 2.8.0.
The sparse-diagnosis panel was conditional on the sweep returning `NOT_FOUND_COMPLETE` with
valid controls; **it did not**, so that branch is not taken. What is next instead: an
independent reproduction of the A20 hit under the same frozen identity, and only then the
read-side mechanism — two experiments, not one. Sparse diagnosis is a branch after the sweep, not a shortcut past it: a passing
sparse candidate would prove write and readback consistent with *each other* and could not
exclude both landing consistently in the wrong place, which is the thing only a location
sweep answers. No board action is authorised at the time of writing; nothing perishable is
still needed from the powered post-fault state, so it may be powered down.

## Claim B round 1 — where it stands

| piece | state |
|---|---|
| preregistration | **DRAFT** — `docs/claimb_preregistration.md`; §6 budget unfrozen, §10 freeze never performed |
| `local_map` 1.0.0 | built from the `clb_lut_init` certificate — 292 addresses, 12 frames, 6 LUTs |
| reachability | **complete** — production report selected 6/6 LUTs, discarded 20 draws, attainable ceiling 353, not exhausted; report committed under `gate_runs/claimb_round1_reachability_2026_08_10/` |
| carrier authority | erratum-006 `carrier.bit`, `post_route.dcp`, `phenotype_manifest` and bundle committed under `gate_runs/claimb_round1_carrier_2026_08_13_erratum006/`; publication, base and ECO gates accepted |
| ICAP write/readback path | 3 envelopes × 536 words = 6,432 bytes; the **no-op** is hardware-proven end to end on erratum 006 — all three envelopes commit in pass 1 and read back in pass 2, 15/15 frames equal to the pinned base, latency 1 word and valid on every envelope, `fault=0`, `recovery_required=0`, scorer never armed. Runs through erratum 005 never left envelope 0. All 15 pinned frames are all-zero, so this establishes that the sequence is legal to the device, **not** that it addresses the requested frame |
| known-answer mutation (§9 step 6) | **still stops** — pass 2 of envelope 0, `fault_code 8` (readback), raised by the engine's FAULT register; 5 committed records now. The restore payload, same path and different content, completes both passes every time. **New as of 2026-08-20: this transaction's write is no longer in question.** In its post-fault state the intended frame holds the candidate bit-for-bit (16/16 controls, `evidence/location_sweep_2026_08_20/step4_sweep/`), and the fault's own DDR staging copy of that frame is all zero — so this is a read-side disagreement for that transaction. Step 6 nevertheless does not pass: `restore` and the baseline re-run are downstream of the interlock and never execute |
| post-fault JTAG readback | **recoverable**: the R4 startup-cycle prefix restores 16/16 known non-zero control frames from the specified fault state, reproduced on a second fault and a second power cycle. Historical control, not paired; says nothing about write location |
| location sweep | **executed once under its own authorisation** — fresh-load step ① read 5,144/5,144 frames with 16/16 controls and found no pre-existing candidate signature; post-fault step ④ read A20 plus all 16 controls, found `WRITE_LANDED_AT_THE_INTENDED_FAR`, and stopped legally after 17 reads. This is one direct location observation, pending independent reproduction under the same frozen identity |
| candidate gate | judges the **serialized** sequence, under two frame semantics |
| board identity gate | boardid/role/IDCODE/50 MHz, session- and epoch-scoped, no override |
| run log | `claimb_run_log` 1.0.0 |
| engineering device work | carrier loads and guarded ICAP attempts were authorised and executed through erratum 006; every failed attempt stopped without mutation or scoring |
| **Claim B result** | **none yet, zero data points** — preregistration remains draft and unfrozen; no known-answer mutation has completed, and no scorer arm or paired A/B run has occurred |

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
   means it does not yet establish the address. The discriminator — one known-answer
   mutation — was then run on the same carrier and **still stops at pass 2 of envelope 0**,
   which is the open problem described in
   [Where the line actually is](#where-the-line-actually-is). No erratum 007 has been
   written: the cause is not yet identified, and guessing one into a carrier build would be
   the wrong move.

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
