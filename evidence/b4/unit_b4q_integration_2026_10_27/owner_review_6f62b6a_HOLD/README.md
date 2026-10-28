# Owner review — 6f62b6a HOLD; R1–R3 residuals, R4/R5 and manifest correction accepted within scope

Reviewed `b4-b4q-integration@6f62b6ae22dd85a434ce7db97bddd6b6f750adf6`, repaired implementation `93cb570`, relative to prior delivery `3723b91`. **HOLD for three residual contracts below.** The repair is substantive and the original concrete negatives now refuse. Do not present this as an unchanged first delivery or as a failure of the silicon/model: these remain host integration boundaries.

## 1. Independent verification and accepted work

A new detached shared-object clone `/tmp/owner_b4q_repair_3ogm8sq4` was used (`snapshot.json`). Host firmware rebuilt under the submitted strict flags. The pre-existing ignored GSR-aware carrier netlist was supplied unchanged as a declared dependency, with its hash recorded; no fresh synthesis or bitstream build was performed.

- Nine modules: **Ran70, OK, skipped1**,97.043s (`tests.txt`). The schema-against-bench test ran before the inherited carrier tests generated sim/b4/out/flow.jsonl and skipped. After that dependency existed, the **one skipped test was run separately and passed** (`skipped_test_rerun.txt`). Thus all70 unique tests were exercised successfully, but the first full owner invocation was not70/no-skip. No gratuitous whole-suite repeat was made merely to change the label on this evidence.
- All **16 e2e scenarios regenerated** in the clone. Fresh-process CLI verifications of the16 submitted and16 regenerated archives: **32/32 exit0/agree=true**; clean versus named negative findings as recorded (`scenario_verifications.json`).
- RTL-trace fidelity independently reproduced: **zero mismatch** under the same27-trace comparison and the same declared hand-driven handshake limitations (`fidelity.json/txt`). This is not a stronger RTL/physical equivalence claim.
- Cortex-a9 pure-unit compile check succeeds (`xcheck.txt`); no board image, link/BSP or board operation.
- Old dropped-final-transaction, changed A5/A8 verdicts and malformed top-level manifest negatives now refuse by name. Missing A5 closes now gives not_demonstrated. R4 bad-source/missing-tag/unaligned DMA tuples and R5 float/bool/out-of-range raw bits are rejected by the relevant code/schema/adapter (`probes.json`). **R4 and R5 are accepted within this unit's scope; no further change to them is requested absent a concrete regression.**
- Manifest correction independently regenerated into **disposable build output only**: it equals the delivered current manifest. The retained old manifest equals its historical git blob; bitstream hash remains **4e406f1280d3cf5cabf43d001278ef3b807a9ce4a7d036445122f5636e3d18a9**,22/36 frame hashes differ before/after, all21 address values equal, natural-build mismatches empty. No RTL/bitstream change. This narrow metadata correction is accepted; it grants no live-write/composition authority (`scope_checks.json`).
- Previous owner's63 checksummed payloads match the original package byte for byte. Frozen IMPORT59 entries match, no untabled tracked B4 file. The protected-path diff is only the authorised `builds/b4/b4_carrier_manifest.json`. Canonical and clone tracked trees remain clean.

The submitted44-mutant record was inspected, not independently repeated:31 kills,13 named survivors,0 edit miss; combined guards are useful evidence for the supplied fault conditions. Neither the survivors nor combined kills prove coverage of all HAL failures or coordinated archive mutations. No332-test frozen B4 battery was repeated. No production seed derivation, physical observation, board operation, commit, push or merge occurred in this review.

## 2. R1 residual — P1: read/HAL failures still permit later commands

Locations: firmware/b4q/b4q_tx.c:88–89,256,283,348. Tests use the actual rebuilt C firmware against the injected HAL. They leave the returned data word unchanged and change **only the response to SLVERR**, so a successful-looking data word cannot mask an explicit failure indication.

1. After a valid opening, return SLVERR on the transaction's NONCE_LO read. The accessor sets STOP_AXI, yet **one notary signature and ARM are still issued** before the transaction finally stops. Probe `nonce_read_slverr`: signature1, CTRL words include0x40 (ARM), firmware status1 with the read-error reason.
2. After a valid opening, return SLVERR on HEARTBEAT just before INIT. STOP_AXI is set, yet **INIT_REQ0x400 is still issued** before the final stop. Probe `heartbeat_read_slverr`: CTRL words include0x200 (PRE_SAMPLE) then0x400 (INIT_REQ), firmware status1. A final stopped result does not undo the forbidden event.
3. Return SLVERR on DEVCFG_CTRL during the root transaction's configuration path. `mem_rd` discards the response entirely, and the transaction returns **status0/reason closed, X closed, no findings** (`read_error_supplement.json`). The same helper design ignores the response of memory/DevC writes.

The previous response checks fixed the demonstrated writes; this is the remaining same R1 contract. Propagate/hold unsuccessful HAL reads and writes through the transaction state, and do not admit SIGN, ARM, engine operations or a new DMA after a prerequisite read/transport failure. Centralise the admission invariant where useful instead of fixing only these named offsets. Failure-state diagnostic reads may be retained, but are not permission to perform later events. Preserve the first reason, actual phase/raw prefix and halt behaviour. Add read/DevC fault probes that assert **no forbidden subsequent signature/CTRL/DMA**, not merely that the eventual result reports failure. Normal and explicitly permitted A5 paths must remain valid. No RTL change is needed.

## 3. R2 residual — P1 completeness, P2 refusal boundary

### R2a: an internal PCAP gap is still accepted

Location: host/b4q_verify.py:155–163. The test changes `tx_002`'s PCAP start by+1 in **both manifest.records and tx_002/record.json**, leaving all raw logs and numerical results untouched. This removes the first submission event from the transaction's assigned range. Fresh CLI: **exit0, clean=true, agree=true** (`pcap_internal_gap`).

The condition `(start != cursor) and not(start >= cursor)` rejects overlap but accepts **every gap**. Startup needs its own recognised prefix; that is not a reason to permit arbitrary later unowned intervals. Validate opening ownership, then exact coverage/order and in-bounds ranges of every record and any explicitly declared partial tail. Per-record completeness must not be replaced by a global A7 pass over the same log. Include the coordinated range mutation above; preserve the suffix/missing-directory checks already fixed.

### R2c: only the top-level malformed-manifest example was made total

Location: host/b4q_verify.py:67–124 and subsequent field consumption. Fresh CLI still produces uncaught traceback for each:

- `tx_001/record.json = []`;
- `tx_001/ctx.json = []`;
- `manifest.executing_side = {}` (missing indexed binary field).

The original `manifest=[]` now refuses correctly. Apply the same named refusal/finding discipline to the consumed nested objects, references and fields **before** `.get`, indexing, arithmetic or reconstruction. Validate the qualification index's shapes and typed roles as part of R3. A final nonzero process exit with a traceback is not a named malformed-archive finding. No universal numeric-fuzz/proof campaign is requested: cover these real public file/field boundaries and distinguish malformed evidence from a verifier implementation error.

The new retained pre-write stream bytes improve R2b and are accepted as a pre-frame-write emulation witness. The wording of their exact capture time needs the P3 clarification below; do not revert to a post-write frame-store hash as staging evidence.

## 4. R3 residual — P1: qualification labels/index and data fields remain unbound

Location: host/b4q_verify.py:372–430. The code now recomputes verdicts from selected records, which fixes the old single-file verdict tamper. It still accepts the selection's descriptive labels as their own authority and compares only some fields of the recomputed result.

All of these fresh-process cases leave the raw observations unchanged:

| mutation | result |
|---|---|
| in the A8 index rename `AFF:0` to **`A5FF:0`**, and rename the conclusion key AFF to A5FF | **exit0, clean=true** — the record still observes index0/AFF and varies AFF's configuration bits, but the qualified name now says A5FF |
| change A8 `background_hex` to000000 and `bits` to INIT0/SRVAL1 | **exit0, clean=true** — these declarations are never held to the actual corner configurations |
| flip AFF's stored `init_samples["00"]` and set stored `quantities.init_effect=false`, retaining row2/both demonstrated | **exit0, clean=true** — recomputation notices neither contradictory data field |
| rename A2 `ce_mode` to **`ff_init`** in index and conclusion together | **exit0/agree=true**, with no added qualification finding (the fixture remains non-clean for its separately disclosed latch endpoint) — a CE-bit pair can be relabelled an INIT positive control |

Required:

- Validate index types, record-role uniqueness/order as applicable and the accepted element-name/index correspondence. Bind declared endpoint genomes, background and varied bit(s) to the referenced **actual O.config**, and to the selected address/semantic metadata. Verify a same-element2x2 cross, common non-varied background and common demonstration stimulus/parts. This checks configuration/selection identity, **not model-predicted Q answers**.
- Keep explicitly declared bystanders such as BFF as diagnostics; do not require their configuration bits to vary in an AFF cross, and do not allow renaming the actual measured element into a different qualification target.
- Validate the retained conclusion's complete data-bearing content against recomputation, including init_samples, quantities, differing points/positions and all claimed roles. A whitelist of merely row/verdict and one reading block does not bind “every conclusion”. Define any genuinely informational/version text separately rather than leaving numerical/witness fields unaudited.
- Preserve the repaired closed-X and complete-record preconditions and the plan's valid-data-versus-established-claim distinction. Negative/unknown data remains data, with no tuning or fabricated physical cells.

These are residuals of the original R3 requirement to bind roles/elements/backgrounds and compare conclusions, not a request for a new study or new stimuli.

## 5. P3 and accepted boundaries

1. The submitted stream bytes are captured in `Devc.data()` immediately before emulated frame-store writes, reached from status handling, **not in submit() when the DMA is queued**. Current comments and documents call them “at submission/queued”. Correct that timing description (or actually snapshot at the declared time), and disclose what remains available when a DMA never reaches data handling. The accepted assertion is “before the emulated frame update”; it is not a physical DDR re-read proof.
2. README section6 still says the carrier manifest “is stale” and the host-failure disposition is a future owner decision, despite section9 and the repaired artifacts resolving them. Mark these as historical first-delivery findings with explicit resolved status and references; do not leave two present-tense states.
3. Keep the owner test evidence honest:70-test invocation skipped1, followed by1 focused pass. The author's canonical no-skip run can remain as its own record. If claiming a fresh source-only no-skip suite in the future, generate/declare the bench-trace prerequisite before the schema test; no extra whole-suite run is requested solely for this wording.
4. The31/13/0 mutant result remains the submitted result. Use “masked on the tested fault conditions” where semantic equivalence is not separately proved. Do not recount a combined kill as a single-mutant kill, and do not expand a STEP_IN guard's evidence into a claim about every read/transport stop.

R4/R5, the metadata correction, the host-link-failure non-success/no-fabricated-O disposition, and the honest latch limitation remain accepted. Do not reopen them without a concrete regression. Carrier RTL/regmap, hypothesis/model/task, formal protocol/statistics/thresholds, labels/receipt and historical results remain unchanged; no new physical or scientific interpretation is licensed.

## 6. Repair authorisation and proportional verification

Complete the residual R1–R3, their focused tests and affected mutants, and the corresponding record/index/plan documentation **in the same unit**, then return one package. No per-edit question, preliminary scope round or new experimental authorisation is needed for this repair. Preserve previous raw runs and mutant outcomes.

Rebuild the host program; regenerate the16 offline scenarios and fresh-verify the retained positive/negative evidence, including the coordinated index/range/conclusion mutations and read/HAL failures above. Run the affected suites and the full inexpensive nine-module regression once at closure with its prerequisites stated. Only affected/relocated mutants need rerunning; repeating the whole44 or frozen332 battery is unnecessary while unrelated code is unchanged. An accepted failure finding must occur for the intended rule, not a collateral missing artifact.

**No board/power/provisioning/physical PCAP, routing, production seed/search/gate, push or merge is authorised.** This review performs none of those actions and changes no tracked source.
