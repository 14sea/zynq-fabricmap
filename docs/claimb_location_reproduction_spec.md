# Independent reproduction of the A20 location result

**Design only. No board action is authorised by this document.** It asks for one, after review.

On 2026-08-20 the location sweep returned `WRITE_LANDED_AT_THE_INTENDED_FAR` with sixteen of
sixteen positive controls exact (`evidence/location_sweep_2026_08_20/`). That is **one direct
observation**. This document specifies the second one, and — more importantly — fixes what
would count as a success, a failure, and an uninterpretable run **before** either can be seen.

Ruled 2026-08-20: this reproduction comes **before** any investigation of the read-side
mechanism and before any RTL change. The two are not to be mixed into one experiment; a
carrier change would change the state constructor and make a like-for-like reproduction under
the frozen identity impossible. There is no live evidence at risk: the previous board state has
already been captured and the board has been powered down.

## 1. The one claim under test

> Starting from a post-fault state built by the specified `no_op` + `known_answer` round, the
> R4 recovery/read sequence reports that the intended frame `0x00400A20` holds the
> **candidate** frame — all 101 words, including the two that differ from the base (word 50
> `0x0000100e`, word 51 `0x00005213`) — with all sixteen positive controls exact in the same
> `board_signature_search.py/2.8.0` acquisition.

Nothing else is under test. Not why the engine's readback disagrees, not whether earlier
known-answer stops behaved the same way, not Claim B.

## 2. What "independent" means here, and what it does not

**It does mean**: a new power cycle, a fresh carrier load, a newly built fault, a new `plmark`,
a new pair of acquisitions, and a result that was pre-registered rather than read off
afterwards. If the first observation was a fluke of one boot or one transaction, this catches
it.

**It does not mean an independent method.** The same host, the same JTAG cable, the same tool
bytes, the same carrier and the same board. **A systematic error in that instrument could
reproduce faithfully**, and this run cannot see it. Detecting that needs a *different readback
path* — the carrier's own `RDBACK` window, or a PCAP/devcfg readback — which is a separate
design, deliberately out of scope here, and named so the limitation is on the record rather
than discovered by a reviewer.

## 3. The frozen identity — and exactly what must not change

For this acquisition, `instrument_digest()` hashes four scalar fields (tool version, child
version, adapter speed and mode), eight files, and a hash of the complete ordered FAR list.
Everything below is pinned **now**, so drift between review and run is detectable rather than
assumed:

```
TOOL board_signature_search.py/2.8.0   CHILD probe_jtag_config_read.py/2.4.0
SPEED 2000   MODE signature-search

d25d46e9649957fe767f0469411b9d7a7c985d01aa0b8fac4e9b3078426f5b5d  scripts/board_signature_search.py
c3e79a0856ccc821ca35f6a2daa637258075f92b573cf6247d9b745dac1f1122  scripts/probe_jtag_config_read.py
06e542043996643358e5606d226d9585b1c239325b54e6afb4856d2c6a1b99fa  scripts/jtag_config_only.cfg
8c3369e8e4755da5aceeb7844690d5e132b2e65647004c0a46c0e868e34f0b8a  …erratum006/carrier.bit
e45f466d082ccd6f227e6f9be4ce75a4e98c4caa708808c09a77ed32331c10ef  …erratum006/phenotype_manifest.json
56f2b9e81e180eee2540286e4fde797e0d4820a49d10624c10844c38e99d87cb  …erratum006/local_map.json
f06bf9074bd0a017663ce9895760f817484590ab8a11afe27e438a75983b4930  …reachability_2026_08_10/reachability_report.json
b115e6be3c44b1500aaf0281bd7f480afa61654a12b1083a778fb9d9cb2f5ef1  …known_answer_2026_08_14/known_answer.json

FAR count 5144
ordered FAR-list sha256  2eaa5c2dd25f707ab8d19faaeb566e50cc6233eededb2b5f7a9819d53206e592
signature-search  a20e56aae879812d9ed2960ec55ac8b1b3f57710411cf40da0cc32b1855aa95d
```

The `control-only` identity is deliberately absent: neither acquisition uses that mode, and it
cannot substitute for the signature-search negative control.

**Instrument freeze rule: none of those fields, files or FARs may change before the run.** A
single byte or ordering change makes a new identity, and a new identity means this is not a
reproduction — it is a first observation again.

The search digest does not cover the program that constructs the fault. Pinning only
`board_claimb_postfault_capture.py` is insufficient because it imports the transaction,
transport, setup and authority code that actually touches the board. The conservative
state-construction freeze is therefore the complete tracked `scripts/` tree:

```
baseline commit       78e907e4a3263f8f6561679bfa40274bfaa16f9e
scripts Git tree      c0bb137139b937fc94302d6940cada3a9bc58b2c
canonical-run tree    98d7721ec8095ea08944f2c50c515d3a003ee879
post-fault entrypoint board_claimb_postfault_capture.py/1.0.0
```

The previous observation used for the cross-run checks is frozen too. It is not whatever a
mutable path happens to contain on execution day:

```
evidence publication commit  0cc5aa4608acf4c477ca5ab122219a458b013fb3
step4_sweep Git tree          c721277fd506f7211271d300ddee9772962adbac
step4 index sha256            4747cc11f22893d383c9095c2709f505b7fa8378fa06f8ccff394a5a5ba3a6f2
A20 capture sha256            404fa8c7a0ebbe5b7d15e1ad2f44ed0176bff8f20a22545c896911d7cf9dd580
A20 frame sha256              15cb05e68adbff6c962053bb5220c33d278c09a793ce12bc4017f37269a5bbe7
A20 child Tcl sha256          b66256c4efcc5fe839d323b9709a9dd55a29f6ccd4c4794a82f3c25dac053f5d
```

New documents, tests and evidence may change without changing the instrument. The pinned
reference subtree above may not. Before any board action, the working `scripts/` tree must be
clean and have the pinned Git tree ID; the canonical carrier-run tree and published reference
subtree must have their pinned Git tree IDs; and a host-side recomputation must return the
pinned signature-search digest.

## 4. Pre-registered outcomes — fixed here, before the run

The acquisition is judged on three things: the fault's shape, the controls, and `A20`.

| # | observation | verdict, decided in advance |
|---|---|---|
| **R1** | fault shape as specified, controls **16/16**, `A20` == candidate exactly | **REPRODUCED.** Two observations; the location result stops being a single point |
| **R2** | fault shape as specified, controls 16/16, `A20` == **base** | **NOT REPRODUCED AT THE INTENDED FAR.** The tool must finish the full sweep that this branch requires; record that result, then stop the procedure. The two recorded instances differ, but this experiment does not identify why. It is not a reason to run a third time |
| **R3** | fault shape as specified, controls 16/16, `A20` == neither | valid third-state observation: the intended-FAR result was not reproduced. Record the frame, stop, and make no causal interpretation |
| **R4** | controls **not** 16/16 | the acquisition answers nothing about location — Phase 2's failure mode. Stop. Note R4-the-recovery has now held after three separately constructed specified post-fault starting states, so this outcome would itself be new information |
| **R5** | the round does not produce exactly `[no_op: passed, known_answer: stopped]` with `STATUS 0x04040082` / `FAULT 0x8` in pass 2 of envelope 0 — **including an unexpected pass** | stop **before** step ④. The specified state was not created, so there is nothing in scope to acquire |
| **R6** | any reboot, marker mismatch, child failure, missing required capture (not a legitimate `not_attempted` entry after an early verdict), or bookkeeping anomaly | not interpretable; stop where it happened, keep everything |

**Cross-run pairing, also fixed here.** Before accepting any step-④ location or instrument
verdict, these must hold; otherwise the result is R6:

* `instrument_digest` equal, parent and child versions equal;
* the sixteen control FARs and their order equal;
* the child Tcl of the 17 FARs both runs read is byte-identical across runs;
* the two `plmark`s differ, and each is stable within its own acquisition.

The old side of every comparison is read from the pinned `0cc5aa4` publication tree, not from a
mutable worktree path. On R1, two additional whole-frame consistency checks must hold and are
reported whether they hold or not:

* `A20`'s 101-word frame is **word-for-word identical to the pinned 2026-08-20 capture** — both
  equal the candidate, so this is a consistency check on the whole chain, not a new claim.
  Its digest is independently checkable: the pinned capture's `frame_sha256`
  `15cb05e68adbff6c962053bb5220c33d278c09a793ce12bc4017f37269a5bbe7` is the same value
  `analyse_ddr_capture.py` derived as `expected_frame_sha256` from the frozen authority,
  by a different route;
* the sixteen control frames are word-for-word identical to the pinned 2026-08-20 captures.

**No retries.** Each step runs once. A failed reproduction is a result, not a reason to rebuild
the state and try again.

## 5. Run book

Same shape as `claimb_location_sweep_spec.md`, with the three corrections that procedure
already paid for. `<D>` is the run date; evidence root `evidence/location_reproduction_<D>/`.

Before the first power cycle, perform and preserve a host-only freeze preflight. It must show:

* `git status --porcelain -- scripts` is empty;
* `git rev-parse HEAD:scripts` equals `c0bb137139b937fc94302d6940cada3a9bc58b2c`;
* `git rev-parse HEAD:gate_runs/claimb_round1_carrier_2026_08_13_erratum006` equals
  `98d7721ec8095ea08944f2c50c515d3a003ee879`;
* `git rev-parse 0cc5aa4:evidence/location_sweep_2026_08_20/step4_sweep` equals
  `c721277fd506f7211271d300ddee9772962adbac`;
* recomputing `instrument_digest(frozen_far_sequence(), "signature-search")` returns
  `a20e56aae879812d9ed2960ec55ac8b1b3f57710411cf40da0cc32b1855aa95d` and the FAR count is
  5,144.

Any mismatch stops before board contact. Preserve the commands, output and return codes as
`freeze_preflight.txt` in the evidence root. Create that root before the preflight; creating a
host directory is not board contact.

```sh
CARRIER=gate_runs/claimb_round1_carrier_2026_08_13_erratum006/carrier.bit
EXPECTED_CARRIER_SHA256=8c3369e8e4755da5aceeb7844690d5e132b2e65647004c0a46c0e868e34f0b8a
```

```
⓪ host-only freeze preflight
   mkdir -p evidence/location_reproduction_<D>
   [perform the four checks above and preserve their output in the evidence root]

① fresh load, negative control
   [physical power cycle]
   python3 scripts/precheck_fresh_power.py --out evidence/location_reproduction_<D>/precheck_1.json
   printf '%s  %s\n' "$EXPECTED_CARRIER_SHA256" "$CARRIER" |
       sha256sum --check - > evidence/location_reproduction_<D>/carrier_sha256.txt 2>&1
   python3 scripts/board_set_fclk50.py --port /dev/ebaz-uart \
       > evidence/location_reproduction_<D>/fclk50.log 2>&1
   python3 scripts/board_uboot_fpga_load.py --require-unconfigured --op loadb --bit "$CARRIER" \
       > evidence/location_reproduction_<D>/carrier_load.log 2>&1
       # transcribe the marker, never retype:
       #   grep -o '\[plmark\] [0-9a-f]*' evidence/location_reproduction_<D>/carrier_load.log
   python3 scripts/board_signature_search.py \
       --out-dir evidence/location_reproduction_<D>/step1_negative --plmark <marker> \
       > evidence/location_reproduction_<D>/step1_negative.stdout.log 2>&1
   expect: 16/16 controls, A20 = base, 5,144 read, candidate signature ABSENT
           (a signature present here ends the procedure — it would not be diagnostic)

② [physical power cycle]

③ build the specified fault
   python3 scripts/precheck_fresh_power.py --out evidence/location_reproduction_<D>/precheck_2.json
   sha256sum "$CARRIER"          # optional, read-only: phase_setup compares it mechanically
   python3 scripts/board_claimb_postfault_capture.py \
       --out evidence/location_reproduction_<D>/fault/record.json \
       > evidence/location_reproduction_<D>/fault_capture.log 2>&1
       # NO hand load: phase_setup already does SHA + fclk50 + loadb, and a second load
       # meets PCFG_DONE = 1 and is refused.
       # The specified fault is a fail-closed STOP, so the expected CLI exit code is 1.
       # Do not accept it by exit code: reconstruct the exact R5 shape from record.json.

④ the acquisition, same boot
   python3 scripts/board_signature_search.py \
       --out-dir evidence/location_reproduction_<D>/step4_sweep --plmark <the fault boot's marker> \
       > evidence/location_reproduction_<D>/step4_sweep.stdout.log 2>&1
       # no --max-reads, no --control-only

⑤ host-side only: identity pairing against the pinned `0cc5aa4` blobs, then the cross-run
   comparisons of §4, then the reading
```

Step ① is repeated rather than inherited. It is the day's negative control, it re-establishes
the instrument at 5,144 frames, and a reproduction that borrowed yesterday's control would be
weaker than the thing it is reproducing.

## 6. Budget

| quantity | figure |
|---|---|
| power cycles | 2, both physical (the operator's, not the tool's) |
| step ① acquisition | 5,144 frames at the **measured** 0.1007 s/frame ≈ **8.6 min** |
| step ④ acquisition | **17 reads ≈ 2 s in R1, R3 and R4** — the tool stops there. **R2 is the expensive branch**: `A20` holding the base with 16/16 controls is exactly the condition that makes it complete all 5,144, ≈ 8.6 min |
| carrier loads | 2 × ≈3 min at 115200 |
| raw evidence | ① has 15,432 child-triplet files plus `index.json`/`verdict.json` = 15,434 in the acquisition directory, ≈121 MB; ④ has 53 files if it stops after 17 reads, all in the keep set |
| wall clock, end to end | ≈ 30 min including the two loads and the fault round; ≈ 38 min on R2 |

## 7. Evidence and archive

Committed per acquisition: `index.json`, `verdict.json`, the reading, the candidate FARs
**that were read**, and the sixteen controls, each as capture + child log + Tcl, plus an
archive manifest — including a manifest that records *no archive* when nothing needs one.
**On R2 step ④ is a full sweep and produces its own 15,434-file set**, which then takes the
same five-step archive treatment as step ①'s; on R1, R3 and R4 its 53 files are all keepers
and nothing is archived.
Console logs (`fclk50.log`, `carrier_load.log`, the acquisition stdout) are evidence and are
committed; `.gitignore`'s `*.log` rule is already negated under `evidence/`.

Step ①'s 15,432 raw files follow the ruled five-step order: **archive → verify by extraction →
`validate_index` under the relative layout the child argv records → upload as a GitHub release
asset, download it back, byte-compare → only then move**. `git diff --check` will warn on the
console records' CR and trailing whitespace; those bytes stay.

## 8. What a successful reproduction would and would not license

* It would make the location result **two observations under one instrument**, which is what
  the 2026-08-20 ruling asked for before anything downstream.
* It would **not** close the question of systematic instrument error (§2).
* It would **not** advance §9 step 6, which still stops at the interlock, and it is **not** a
  Claim B data point.
* It would leave the next question exactly where it is: why, in the first observation, the
  engine's pass-2 readback handed over a zero frame while JTAG reproduced the addressed frame.
  That investigation, and any RTL change, remain separate and unauthorised.

## 9. Decisions requested

1. Authorise ①–⑤ as one conditional chain with the §4 outcomes and the §8 limits, or authorise
   ① alone and rule again — noting that unlike last time there is no scale unknown left in ①.
2. Confirm the evidence root `evidence/location_reproduction_<D>/` and the release-asset
   archive for step ①'s raw files.

One `probe_ddr_capture.py --slot 0` in the fault boot is **not requested and not authorised by
this design**. Repeating the all-zero staging observation belongs to the deferred read-side
question. If the reproduction closes first and that volatile state is still worth using, it
requires a separate ruling after step ⑤; it is not pre-authorised as part of this chain.
