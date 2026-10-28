# B4Q — the carrier v2 qualification session: the plan (DRAFT v0.3, documents only, 2026-10-28; v0.2 accepted with the integration unit — the owner's PASS on `a41f573`; v0.3 names the PS image, P2 built host-only — `docs/b4q_image.md`)

> **Standing.** The reviewable plan the owner's disposition of 2026-10-27 asked for (deliverable 4 of its section 4): "the limited
> qualification claim; exact fixed demonstration vectors, A5 c′ and witnesses, main / x5FF A8 crosses and reference-validity rules,
> the accepted nine A2 pairs, timing parameters and which are not yet measured, required session / instrument / board identities,
> legal-write / composition authority, evidence / schema versions, outcomes and stopping rules"; F8B3 bring-up distinguished from 17A6
> qualification; unknown / not-demonstrated outcomes preserved; device / power / provisioning facts not yet measured left as
> prerequisites; no N / B\* / prediction / session design. **This plan authorises nothing**: no board is powered, provisioned or
> loaded by it; its acceptance is not a board session; a B4Q session needs its own ruling pair naming the board, the images, the
> session label and the date, after the prerequisites of §8 are met. Date, branch name and commit count are organisational.

## 0. Status index

| section | fixed here | prerequisite / measured later | for the owner |
|---|---|---|---|
| 1 the claim | what a PASS would establish and what it would not | — | — |
| 2 the identities | the carrier, the executing side, the hypothesis / certificate, the write set, the references of the two frame domains, the schema versions | the regenerated carrier manifest (§8 P1), the board image and its build evidence (§8 P2) | the manifest regeneration |
| 3 the session's records | the record types, the demonstration vectors, c′, the A8 crosses, the A2 pairs, the order | — | the vectors, if the owner fixes others |
| 4 the outcomes and the stop rules | per record type, the contract's rules applied by `host/b4q_qual.py`; the session's stop conditions | — | — |
| 5 the legal-write / composition authority | the write set's facts from the build of record; what a write of these frames touches | the frames' safety for the carrier's own routing on a live device is **not shown**; a bring-up fact on `F8B3` | the authority to write these frames |
| 6 timing | the declared parameters and their origin; which are measured (none) | all of them, on the board | — |
| 7 the boards and the two stages | `F8B3` bring-up (engineering rehearsal) ≠ `17A6` qualification | 2d provisioning (`F8B3`, the control plane, the supply measurement) | the 2d rulings |
| 8 prerequisites, in order | P1–P6 | — | each its own authority |
| 9 what the plan does not do | — | — | — |

## 1. The limited qualification claim

A B4Q PASS on a named device and site would establish, **for the named elements, backgrounds and contexts actually run**:

- **A8**: that the declared initialisation mechanism — (b) GSR through STARTUPE2, raised by the carrier's engine for PULSE clocks — has
  an event-to-Q effect on this die: the init sample (`steps[0].q_after`) tracks the element's `ff_init` bit in the predicted direction;
  and that the SR restore evidence (6.5's joint reading) tracks the element's `ff_srval` bit — on the crossed elements in their
  crossed backgrounds (§3.3), each corner judged by 6.7's precedence rows;
- **A2**: that for each of the seven semantics the accepted positive-control address (7.3's nine pairs) gives different observations at
  its two endpoints under the row's demonstration vectors (§3.4);
- **A5**: that the specified adversarial state *c′* (§3.2) reaches the pre-init boundary and is cleared by the initialisation (5.6's
  decision table: pass) — and nothing about any other leftover state;
- **A1 / A3 / A4 / A6 / A7 on the device**: the session root and the closing baseline equal under both witnesses of 5.4 (frame
  binding and Q-state restoration), every record audited, the sampling path type-exact on every record, the identity page over the
  PS path (`VARIANT` v2, the carrier and image digests, the declared mechanism and timing), the closing unsigned / replay /
  wrong-key controls refused, the executing side's actual MMIO accesses within the allowlist.

It would **not** establish: the 21-bit hypothesis or its domain (one site, chosen elements and backgrounds); any other die by
transfer; the timing parameters' adequacy beyond the contexts run; a reduced claim's interpretation (rows 3–5 of 6.7 are 2c's
decision); any revision of the host results (`b4-gate-1` FAIL, `b4-sim-4` / `b4-sim-5` no-go) — it can constrain their future physical
interpretation and nothing more; N, `B*`, a prediction or a session partition for a mapping study; a go for anything.

## 2. The identities a session binds (contract 3.5, 5.5; B1Q's evidence-chain form re-aimed)

| what | value / source | status |
|---|---|---|
| the carrier (the loaded image) | `builds/b4/b4.bit`, sha256 `4e406f1280d3cf5cabf43d001278ef3b807a9ce4a7d036445122f5636e3d18a9` (`builds/b4/b4_build.json`; routed v0.4, WNS +7.263 ns, 12 target cells, 279 RAM32X1S, 1 STARTUPE2, 0 ICAPE2); `VARIANT 0x42340001`; the declared mechanism 2 (GSR via STARTUPE2); `NONCE_SEED 0x9E3779B97F4A7C15` | fixed (the build of record) |
| the loaded-image frame reference | the FAR-ordered digest of the write set's eight frames as the loaded image holds them: `firmware/b4q/b4q_data.json` → `loaded_image_target_frames_sha256`; the per-frame digests of all 36 column frames beside it; the manifest of record `builds/b4/b4_carrier_manifest.json` **regenerated from the committed bitstream** (the HOLD review's disposition 1; the old file and the comparison archived in the unit directory) now names the same bitstream and the same frames | fixed |
| the restored study base reference | the signed base genome 0's frames (the loaded image with the two mux bits cleared and the ECC words recomputed), FAR-ordered digest — a different commitment in the same hash domain, never compared to the loaded-image reference | fixed (derived; `host/b4q_frames.py`) |
| the write set | two envelopes: FAR `0x00400a00` (targets `a00`–`a03`, flush `a04`) and `0x00400a1c` (targets `a1c`–`a1f`, flush `a20`); the 21 whitelisted bits in the mapping's address order | fixed (`firmware/b4q/b4q_data.json`); its authority §5 |
| the hypothesis / the certificate | `b4/hypothesis/ff_behaviour_v0.3.json` `59948f9b…`; `gate_runs/run_2026_08_05_ff/certificate.json` `c69e419f…`; site `SLICE_X2Y25` | fixed (unchanged) |
| the executing side | `firmware/b4q/b4q_tx.c` and its units at the unit's commit; the HOST build's digest in `build/b4q_firmware/build.json`; **the board image does not exist** (§8 P2) | the board image, its build evidence and its digest: later |
| the notary | the signer principal with the production key (`provisioning P3-K`, a ruling) — not the bench fixture key | a ruling per session |
| the record / schema versions | `ff_observation_carrier` / `ff_fitness` / `ff_transaction_close` / `ff_session_open` 1.0.0 (`host/b4carrier_records.py`; the files `b4q/schemas/*_v1.schema.json`); the record types of 9.2 (`a2_qualification`, `a5_qualification`, `a8_qualification`) are **the same three objects with the session's record-type label in the evidence index**, not new schemas | fixed |
| the session label and the ruling pair | `B4Q-F8B3-<date>` (bring-up) / `B4Q-17A6-<date>` (qualification); the whole-of-run ruling and the provisioning ruling archived as inert envelopes beside the evidence (B1Q's form) | the rulings |
| the timing parameters | §6 | declared, unmeasured |

## 3. The session's records, in order

A B4Q session is one session (5.5): `session_open` → the root → the records below → the closing baseline → the closing controls. Every
record is `O` / `F` / `X` of the contract; qualification observations carry no `F`.

### 3.1 The root and the baselines

The session root on the base (genome 0) as 5.5 fixes it; the closing baseline (genome 0 again, after every record) compared with the
root under both witnesses of 5.4: `X.base_readback_sha256` equal to the restored-base reference; `X.base_state_sample` equal to the
root's; the closing unsigned ARM, the replay of an earlier payload and a wrong-key payload each refused (`F_ARM_AUTH`) — B1Q's closing
controls, on the v2 gate.

### 3.2 A5 (5.6): the one injection protocol

J1 observe *c* = the CE / SR-driven background `b = 0x000018` under the fixture stimulus `FIX1` (the carrier bench's CE_SR_ASYNC schedule; init
values all 1); J2 the injecting transaction *c′* = the same genome under the one-step stimulus **`clock 1, ce 0xFF, sr 0x00, d 0x00`**
(every element driven to 0, the opposite of INIT 1; the inputs held; `CLOSE_INJECTION`); J3 *c* again under the A5 flag with the
pre-init cleanup recorded inside step 0. The witnesses: `O_c2.initial.q` ≠ `O_c1.initial.q` and = `O_c′.steps[-1].q_after` (the
injection arrived); the post-init projection of `O_c2` = `O_c1`'s (cleared). Computed by `host/b4q_qual.a5_verdict` exactly as 5.6's
table; **a pass is about this *c′* only**. Run once on each element set the crosses use (one protocol per session suffices: the
injection drives all eight elements).

### 3.3 A8 (6.4–6.7): the crosses

Two crosses, **one on a main element (AFF: bits 13 `ff_init`, 8 `ff_srval`) and one on an x5FF element (A5FF: bits 14 `ff_init`,
1 `ff_srval`)**, each on the background `0x000018` (FF storage, CE and SR driven, asynchronous, clock not inverted); the four corners
`(INIT, SRVAL) ∈ {00, 01, 10, 11}` as the bits are written (bit 1 reads INIT = 0 / SRVAL = 0); **one demonstration stimulus for all
four corners**, 6.5's parts on this carrier's slice-wide controls (the other elements receive the same inputs):

| step | clock | ce | sr | d | part |
|---|---|---|---|---|---|
| 1 | 1 | FF | 00 | 00 | C0: the reference capture of 0 → `K0` |
| 2 | 0 | FF | 00 | 00 | |
| 3 | 1 | FF | 00 | FF | C1: the reference capture of 1 → `K1` |
| 4 | 0 | FF | 00 | FF | |
| 5 | 1 | FF | 00 | FF | E0: the prior 1 → `P0` |
| 6 | 0 | FF | 00 | FF | |
| 7 | 0 | FF | FF | 00 | E0: SR asserted on a level step |
| 8 | 1 | FF | FF | 00 | E0: the edge with `d = 0` under SR → `R0` |
| 9 | 0 | FF | 00 | 00 | release |
| 10 | 1 | FF | 00 | 00 | E1: the prior 0 → `P1` |
| 11 | 0 | FF | 00 | 00 | |
| 12 | 0 | FF | FF | FF | E1: SR asserted |
| 13 | 1 | FF | FF | FF | E1: the edge with `d = 1` under SR → `R1` |
| 14 | 0 | FF | 00 | FF | release |

(`host/b4q_e2e.DEMO` / `DEMO_PARTS`; the init step precedes step 1.) Per corner and element: `i_c` = `steps[0].q_after[e]`, `s_c` =
6.5's joint reading of (`K0 K1 P0 R0 P1 R1`) — `restore(v)` / `capture` / `hold` / `inconsistent` / `unknown` (an invalid reference or a
prior not as planted); the row of 6.7 by precedence (`host/b4q_qual.a8_classify`). The other clock-mode value is **not run** by this
plan: reported as not demonstrated for that context. The latch context is excluded (9.3 clauses 4 / 6).

### 3.4 A2 (7.1, 7.3): the nine pairs

Each row's two endpoints observed under the row's demonstration vectors; the row's verdict: the readout differs at some point or does
not (`host/b4q_qual.a2_row`); a 0 / 1 result is reported, never repaired by choosing another address.

| semantic | g0 / g1 (hex) | element | the demonstration vectors |
|---|---|---|---|
| `ce_mode` | `000000` / `000010` | slice | a capture of 0 under CE, then a capture attempted with **CE low** (`host/b4q_e2e.CE_DEMO`): tied-high CE captures, driven CE blocks |
| `clock_mode` | `000000` / `000040` | slice | the DEMO stimulus (the capture edge moves: K0 / K1 read on the other edge) |
| `sr_kind` | `000008` / `000009` | slice | the DEMO stimulus: an asynchronous element restores at the level step 7 / 12 already, a synchronous one at the edge 8 / 13 — the samples of steps 7 and 12 discriminate |
| `sr_mode` | `000000` / `000008` | slice | the DEMO stimulus: SR tied low ignores steps 7 / 12 |
| `storage_kind` | `000000` / `000400` | slice | the DEMO stimulus; **the latch endpoint's x5FF elements are unmodelled on the host** (the board supplies physical values); the main elements' transparency at the level steps discriminates |
| `ff_init` (main) | `000000` / `002000` | AFF | the init sample `steps[0].q_after` |
| `ff_init` (x5FF) | `000000` / `004000` | A5FF | the same |
| `ff_srval` (main) | `000008` / `000208` | BFF | the DEMO stimulus's episodes (`R0`, `R1`) |
| `ff_srval` (x5FF) | `000008` / `000028` | C5FF | the same |

The vectors are proposals from the model's distinguishability (the e2e shows them discriminating on the model for `ce_mode`, and the
cross for INIT / SRVAL); the owner may fix others before the session; **a vector changed after a board result is a new session**.

### 3.5 The order and the count

`session_open` → root → A2 rows (18 observations) → the AFF cross (4) → the A5FF cross (4) → A5 J1–J3 (3) → the closing baseline → the
closing controls (3 refused ARMs): **31 signed transactions** plus the controls. On the host emulation a session of this size runs in
≈ 25 s; on a board the PCAP path dominates (unmeasured, §6).

## 4. Outcomes and stop rules

| record | the outcome, as the rule fixes it | what stops the session |
|---|---|---|
| `session_open` | `open` iff the startup readback equals the loaded-image reference; `refused` otherwise — **the session does not open, no root is signed** (5.5) | a refusal |
| the root | `O` complete (init only), `X` closed; the base-state reference = `X.base_state_sample` | a faulted `X`; a frame-binding or Q-restoration failure |
| every `O` | `complete` under A3 (closed sets, type-exact cells); `invalid` with its fault at the phase reached (the prefix retained, no `F`, `X` faulted) | an `invalid` O stops the **record**, not the session: the next candidate is signed only after a `closed` X; a fault under recovery requires a reconfiguration (the carrier's persistent fault) — **the session ends there**, the records kept |
| A2 rows | `differs` / `does_not_differ` / `not_assessable` per row; the session's A2 result is the nine rows, none repaired | — |
| the crosses | 6.7's row per element and context; row 0 (`not demonstrated`) and row 1 (`failed / unresolved`) are findings with the samples retained; rows 2–5 are the demonstrated contexts' verdicts; **no attribution, no hypothesis revision, no carrier re-tuning follows automatically** | — |
| A5 | `pass` / `fail` / `not_demonstrated` per 5.6; a fail is the data of a persisting fabric | — |
| the closing baseline and controls | equal under both witnesses; the three refusals | a difference or an accepted control: the session is a HOLD |
| the session | **PASS** iff every row above holds for the contexts run, every record audited, the chain unbroken, A7 empty on the actual accesses; otherwise **HOLD** with the records of a failed qualification (never deleted, never re-run under the same label) | — |

**One attempt per session label**; a HOLD session's records stay; what follows (a repair unit, another label) is a ruling. A
`not_demonstrated` context is not a HOLD and not a reduced claim: it stays unknown. Nothing is filled from a model prediction.

### 4.1 Data recorded versus claims established — the machine-checkable distinction (the owner's R3)

A session's conclusions are never read from a conclusion file: the session **declares** which records play which role (the
qualification index in its manifest — `qualification_plan`: the A5 roles J1 / J2 / J3 by record, the A8 crosses by background,
bits, corner records, element indices and demonstration-part indices, the A2 rows by endpoint records), and the verifier
**recomputes** every conclusion from the retained `O` / `X` of those records with the contract's rules (`host/b4q_qual.py`) and
holds the retained conclusion files to the recomputation — a difference is a finding; an undeclared conclusion file is a finding.
What each recomputed value means for the claim of §1:

| recorded value | is it the claim? | what it is |
|---|---|---|
| A2 `differs` on a row | **yes** — that row's positive control | the readout differed at some point between the two endpoints under the row's vectors |
| A2 `does_not_differ` | **no** | a recorded negative for that address and vector: the row is **not** a positive control; nothing is tuned to change it |
| A2 `not_assessable` | **no** | an endpoint without a complete, closed observation (the host's latch endpoint among them): unknown |
| A5 `pass` | **yes**, for this *c′* | the injection arrived and was cleared — valid only with J1 and J3 complete and `closed` (their cleanup witnesses) and J2 `injection_open`; without any of them the value is `not_demonstrated` |
| A5 `fail` | **no** — the data of a persisting fabric | retained as the finding it is; never a pass |
| A5 `not_demonstrated` | **no** | the test did not run (the injection did not reach the boundary, or a witness is missing) |
| A8 row 2 | **yes** — both demonstrated for that element and context | every corner complete and `closed`, a valid reference, both effects in the predicted direction |
| A8 rows 3–5 | **only the stated reduced claim** (SRVAL only / INIT only / neither), and whether a reduced claim is wanted is 2c's | — |
| A8 row 1 | **no** — failed / unresolved | retained; no attribution follows |
| A8 row 0 | **no** — not demonstrated | unknown; a missing corner, a corner not closed, an invalid reference or a prior not as planted |
| "every record audited, the chain unbroken, A7 empty" | **necessary, never sufficient** | the session's integrity, which §1's PASS presupposes and does not consist of |

A B4Q **PASS** is therefore: integrity (the row above) **and** A2 `differs` on every row of 7.3 **and** A5 `pass` **and** A8 row 2 on
both crosses in their run contexts; anything less is a HOLD with the retained data, or a reduced claim only where a row 3–5 names
one and 2c accepts it. No negative or unknown datum is erased; no vector is changed to obtain a verdict.

### 4.2 A host-side failure that cannot be sealed (the owner's disposition 2)

A failure on the host's side of the transaction — the notary refuses, a DMA never completes, a stream does not parse, the
transport is interrupted — leaves no carrier fault and no `O` the contract could seal: the session keeps a **named host
non-success result** (the executing side's phase and reason, the acquired raw prefix of the trace and the PCAP log, the
links that did complete) with **no fabricated `O`** and no future-phase witness, and **latches the stop**: nothing further is
signed until a ruling. An already sealed `O` stays immutable; a failure after P6 keeps the partial / faulted closing evidence
the contract defines. This is the integration's reading of 5.7's rows, not a new carrier fault code.

## 5. The legal-write / composition authority

What is known from the build of record (`builds/b4/isolation.txt`, v0.4): the target column (`CLBLL_L_X2Y*`, `INT_L_X2Y*` — the
column whose frames are `0x00400a00`–`0x00400a23`) holds **exactly the 12 target cells** and no other cell; no RAM32X1S (the carrier's
persistent state) is in it; the flush columns hold no cell; **874 foreign nets are routed through its interconnect** (erratum 001: the
route inventory is evidence, not a verdict). The write set writes eight frames of that column and lets the device's auto-increment
land on two flush frames (`a04`, `a20`), all with the loaded image's own content except the 21 bits and the ECC words.

What is **not** shown: that writing frames that carry the carrier's own routing (the interconnect frames `a02`–`a04`, `a1c`–`a1d` and
the flush frames) with their identical content is harmless to a live device while the carrier's engine, gate and AXI path run through
those nets. The B1–B3 sessions wrote frames of this grammar on this part; the B1 carrier's isolation checks were the same kind; none
of that is this carrier's evidence. **The authority to write these frames on a live device is the owner's**, taken on the bring-up
stage first (§7): the session root (the base written, read back, the engine's event raised, the carrier still answering) is the
first fact about it, on `F8B3`, under a ruling that names the write set by digest. The composition rule of architecture 4.2 (which
21-bit configurations are legal to write) is **2c's and unresolved**; the nine A2 pairs and the four corners of each cross are the
only configurations this plan writes, each named here, none made legal by being named.

## 6. Timing — declared, none measured

`ASSERT_DELAY 8`, `PULSE 2`, `RELEASE 16`, `SAMPLE_OFFSET 4`, `SETTLE 4`, `HOLD 4` cycles of FCLK0 = 50 MHz (the identity page's `TIMING` and
`WITNESS` words; `docs/b4_carrier_v2.md` §4) — values declared for the bench and the build. **Not measured on any device**: the GSR
pulse width as the die sees it, the release skew, whether `RELEASE + SAMPLE_OFFSET` suffices for the elements to settle after the
event, whether `SETTLE` / `HOLD` suffice for the slice-wide inputs. The board clock itself (FCLK0 pinned to 50 MHz before every load:
the EBAZ4203 note of `reference_fclk0_125mhz`) is a provisioning fact. The session records the words as read; a parameter changed is a
new build and a new session. The wall time of a transaction on the PCAP path is unmeasured (B1's sessions: ≈ 6.9 s per 300-frame
pair-set; B4's eight frames and two readbacks per candidate are of the same kind).

## 7. The boards and the two stages

| stage | board | what it is | what it is not |
|---|---|---|---|
| **bring-up (engineering rehearsal)** | `F8B3` (the spare, not yet provisioned: `docs/board_roles.md`, architecture §11) | the carrier loaded under the sha-gated path; the identity page; the key provisioned (a `provisioning P3-K` ruling); `session_open`; the root (§5's first fact); a candidate transaction; the executing side's actual accesses logged; the timing words read — the session of §3 may be run in full to rehearse the records and the adjudication | **not** evidence that `17A6` is qualified; its records are engineering evidence of the path, under their own label |
| **qualification** | `17A6` (the verification board, under the content-class interlock; `docs/board_roles.md`) | the session of §3 under the whole-of-run ruling and its provisioning ruling; the adjudication; the qualification record in B1Q's evidence-chain form (`verified before pinned`; `qualified` derived, never set; a HOLD leaves a record) | not a mapping session; not a freeze of 2c |

2d's provisioning of `F8B3` (the control plane, the `role`, the current-limited supply's **measurement** — a design intention with no
measurement evidence, architecture §11) precedes the bring-up stage and is its own ruling per step.

**The handoffs, made explicit (the PS-image unit, 2026-10-28).** The image that the bring-up loads is `b4q_app.bin` as pinned by the
build evidence (its sha256 and the IDENT's `app_image_sha_lo32` echo must agree); the session token and the page are the runner's
acts before `go`; the key is provisioned by the signer principal under a `provisioning P3-K` ruling (the image never touches the
key window: `firmware/b4q/target/b4q_psmap.c`). Still pending before any bring-up, each its own authority: 2d's provisioning of
F8B3 with the supply's measurement (P4); FCLK0 at 50 MHz and the acceptance regression touched on the board (P4); the write-set /
composition authority of §5 (the bring-up's ruling); F8B3's PERIPHCLK (the watchdog's period is B1's 17A6 pin until measured);
the UART, the DMA / PCAP path and the exception path on the device (`docs/b4q_image.md` §4). Then the bring-up (P5) under its own
execution plan and ruling pair, then the qualification on 17A6 (P6). None of these is met by the image's existence; the no-go
results of gate-1 / sim-4 / sim-5 stand; no N / B\* / prediction / session size is chosen and 2c is not frozen by this build.

## 8. Prerequisites, in order — none met by this unit

| # | prerequisite | who |
|---|---|---|
| P1 | ~~the carrier manifest regenerated~~ — **done in the repair** (a narrow metadata correction from the committed `b4.bit`, the old manifest archived with the comparison: `evidence/b4/unit_b4q_integration_2026_10_27/manifest_regeneration/`); it certifies no composition, routing isolation, live rewriting or device | — |
| P2 | **the board image — BUILT, host-only (the PS-image unit, `docs/b4q_image.md`): `b4q_app.bin` from the accepted executing side under the board application, B1's BSP, the console notary (b4q-v1 framing with the instrument's CRC / base64url), the watchdog, the MMU attributes of the buffers, the exception-to-stop path; cross-compiled with the pinned toolchain, two clean builds byte-identical, every input by hash (`evidence/b4/unit_b4q_image_2026_10_28/build_evidence.json`); A7 on its accesses re-run on the host harness. NOT MET as a board prerequisite until a device shows it: the image has never been loaded; the sha-gated load, the UART, the real DMA / PCAP, the watchdog's clock are the bring-up's (§7) | the image: done host-side; its on-device demonstration: the F8B3 bring-up |
| P3 | ~~a host-recorded fault code for link failures~~ — **decided by the HOLD review**: such a stop leaves no `O`; the session keeps a named host non-success result and latches the stop (§4.2) | — |
| P4 | 2d: `F8B3` provisioned; the supply measured; FCLK0 at 50 MHz; the acceptance regression on the board touched | the 2d rulings |
| P5 | the bring-up session on `F8B3` (§7) with its own label and ruling pair; the write-set authority of §5 taken there | the owner |
| P6 | the qualification session on `17A6`: the ruling pair, the date, the label; the pins; nothing pinned changed between P5 and P6 or the pins are re-taken | the owner |

## 9. What this plan does not do

It powers, provisions or loads no board; it fixes no N, `B*`, prediction, session partition or calibrated rate; it changes no program,
schema, threshold, hypothesis or archive; it does not freeze 2c; it decides neither the composition rule nor the write-set authority of
§5; it does not make a board image; it authorises nothing. Its vectors and crosses are proposals computed on the host emulation
(`host/b4q_e2e.py`) and the reasons are stated; its outcome rules are the contract's, made executable in `host/b4q_qual.py` so that no
row is applied by hand.
