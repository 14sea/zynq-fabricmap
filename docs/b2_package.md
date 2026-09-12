# B2 — the image package: what was built, what the gate showed, what is asked (v0.3, host-only, 2026-09-11)

> **Offline positive integration reviewed on 2026-09-12 (`9035b18`).** The B2Q
> S1 → S2 → S3 → fresh-process verification succeeds with real re-adjudication.
> An independent B2 demonstration uses the resulting plan's final slice, pairs 7 and 8
> at budget 600: **2,406 scored/audited records, PASS, zero findings**, and no pooled
> primary. The production finalizer's seal → callback → summary ordering also passes.
> Focused suite: **395 tests, zero skips, OK**. The missing positive integration
> blocker is closed for these demonstrated paths. See the
> [review and its explicit preflight doubles](b2_modelled_integration_review_2026_09_12.md).
> P3 corrections remain: **two forced-control CRC drops**, eleven negative tests,
> and the model CLI's export-only behavior versus the complete API workflow.
> `b2_pins`, `b2_test_report`, qualification-document/planning-rule freeze and final
> package review remain outstanding. No push or board clearance is granted here.
> Earlier status banners below are historical.

> **The complete offline B2Q lifecycle now runs, and the runner produces a PASS.**
> `host/b2_modelled_session.py` drives a whole B2Q session through the instrument's real host
> stack and the **production exporter**; the runner's own `judge_session` returns **PASS** (zero
> findings, zero kills, `binding_checked`, a rate of 4490.86/h MEASURED from the session's timing
> and a policy verified by the instrument's check); `qualify` **accepts** the transition and
> derives the calibration under the split rule; `pin_plan` pins the plan; and a **fresh process**
> `verify` returns stage S3, qualified, board 17A6, the B1 chain re-verified. `qualify` and
> `verify` are handed the real `readjudicator` — **no replay double and no stored-verdict double
> anywhere on the positive path**. The reference orchestrator now accepts explicit pair seeds, so
> B2Q's own seed rule can drive it. Ten negatives are applied one at a time to that passing
> evidence. **14 end-to-end tests, B2/B3 395, zero skips.**
> The model stands in for a board: not silicon evidence, not a session, not a qualification; the
> rulings are inert and authorise nothing. See
> [`evidence/b2/b2q_modelled_lifecycle_2026_09_11/`](../evidence/b2/b2q_modelled_lifecycle_2026_09_11/).
> Remaining for §7: `b2_pins`, `b2_test_report`, and a B2 (map-utility) profile demonstration.

> **Board authority correction accepted (`7c4f0ca`, implementation `ecb56a6`).**
> The board-authority P2 is closed: correct pairs pass, both-wrong pairs and malformed
> authorities are refused, and fresh-process verification rejects even a rewritten
> board plus a rehashed temporary lineage manifest through the real B1 chain. See
> [the acceptance review](b2_board_authority_acceptance_2026_09_11.md).
> **Overall runner HOLD remains** pending the complete modelled B2/B2Q positive
> lifecycle and remaining package tools. Continue with `b2_modelled_session`; this
> correction acceptance grants no push, freeze or board clearance. Earlier banners
> below are historical.

> **The ruling's board authority is now a frozen input.** Two rulings agreeing on the WRONG board
> used to pass: the manifest recorded no board, `parse_ruling` compared one only when the manifest
> declared one, neither session plan supplied one, and the archive check therefore only required
> the two archives to agree. The board is now taken from the validated lineage at S0 (manifest
> schema **0.2.2 → 0.2.3**), re-verified against that lineage on every `verify`, established
> before any ruling is read, carried in both session contracts' binding, and compared with each
> live and archived ruling — and its **absence is a refusal**, never permission to skip. Malformed
> boardid types and domains are refused too. **50 runner tests, B2/B3 381, zero skips.**
> **Still not done:** no modelled B2/B2Q session, so the complete offline S1 → B2Q → S2 → S3 →
> fresh-process verification is not demonstrated and this runner has never produced a PASS. See
> [`evidence/b2/corrections_ruling_board_2026_09_11/`](../evidence/b2/corrections_ruling_board_2026_09_11/).

> **Ruling board authority review (`39125fb`): HOLD remains.** The identity/input
> contract and archive/summary checks are implemented. One authorization P2 remains:
> S0 declares no board, neither session-plan constructor supplies an expected board,
> and both live and archived rulings can therefore agree on the wrong board. The
> independent same-board wrong-pair probe passes preflight and archive checking.
> See [the board-authority review](b2_ruling_board_review_2026_09_11.md) for controls
> and test-double limits. The complete modelled B2/B2Q positive lifecycle remains
> required before accepting/pushing the runner batch. No board or production action
> was taken. Earlier implementation and review banners below are historical.

> **The offline binding's two P2s are corrected; the positive path still is not.**
> (1) `expected_identity` is now the ONE `app_identity` 1.5.0 contract, used online before the
> board's identity is acknowledged and offline when the evidence is re-adjudicated — the carrier
> digest, carrier variant and universe digest included, which the offline path had omitted
> entirely. B2Q's reconstructed plan carries its `inputs` contract, the preflight compares it, and
> a session plan with no inputs contract is now a FINDING: a missing expectation never disables a
> required check. (2) Both archived authorisations are decoded through the instrument's strict
> envelope reader and rebound — text, board, session, image, preregistration, manifest and the
> whole-of-run master seed, with the two required to name the same board — and an archive that
> cannot be parsed is refused at acceptance rather than having its digest preserved. The final
> summary is cross-checked (outcome, token, the archived ruling and the provisioning ruling's byte
> digest) at the **post-finalisation lifecycle boundary**, since `b1_session.run` writes it after
> the callback. Archives stay inert: read, never claimed, never consumed.
> **46 runner tests, 13 lifecycle tests, B2/B3 377, zero skips.**
> **Still not done:** no modelled B2/B2Q session, so the complete offline S1 → B2Q → S2 → S3 →
> fresh-process verification is not demonstrated and this runner has never produced a PASS. See
> [`evidence/b2/corrections_binding_completion_2026_09_11/`](../evidence/b2/corrections_binding_completion_2026_09_11/).

> **Binding completion review (`4d135be`): HOLD remains.** Export-seal validation,
> eleven-file qualification byte coverage and deadline comparison are implemented.
> Offline binding still omits carrier/universe identity and B2Q inputs; archived ruling
> and final-summary contents are hashed without semantic validation. See
> [the binding review](b2_binding_completion_review_2026_09_11.md) for independent
> positive/negative layer controls and their explicit limits. The complete modelled
> B2/B2Q producer-to-lifecycle positive flow remains required before accepting/pushing
> the runner batch. No production, image, manifest, ruling or board action was taken.
> Earlier implementation and review banners below are historical.

> **The session contract's three P2s are corrected; the positive path still is not.**
> (1) `binding_findings` holds the log's `l6.binding`/`l6.inputs` and the IDENT to what the
> invocation declares — the **slice** included, which a record count cannot separate when two
> slices share a length — and `archived_manifest_findings` makes the `manifest` argument
> load-bearing: the manifest archived beside the evidence must BE this invocation's, by bytes and
> stage, before anything else is read. `readjudicator` judges against the validated run manifest
> and refuses without one. (2) The export seal is verified on every standalone re-adjudication,
> and the qualification record migrates **`b2_image_qualification` 1.1.0 → 1.2.0** to pin B1's
> complete eleven-file evidence set, so the audits and timeline a verdict consumes — and the
> seal, console, summary and both rulings — can no longer change without changing the record.
> (3) The measured span is compared with the deadline the invocation authorised, and B2Q's
> planning bound is a declared constant with its rule so the offline verdict reconstructs the
> same limit; `--qual-rate-per-hour` may only agree with it. The epoch/deadline/count branches
> are now driven through the committed **real B1 session** evidence rather than by copying the
> production logic into a test. **32 runner tests, B2/B3 361, zero skips.**
> **Still not done:** no modelled B2/B2Q session, so the complete offline S1 → B2Q → S2 → S3 →
> fresh-process verification is not demonstrated and this runner has never produced a PASS. See
> [`evidence/b2/corrections_session_contract_2026_09_11/`](../evidence/b2/corrections_session_contract_2026_09_11/).

> **Runner correction review (`366d96f`): HOLD remains.** The earlier wire lookup,
> ruling master binding, seed-container validation and both P3s are closed. Session
> acceptance is only partially corrected: offline invocation/identity binding, export
> seal and qualification evidence coverage, and deadline enforcement remain incomplete.
> The complete offline B2Q positive lifecycle is still required. See
> [the correction review](b2_runner_correction_review_2026_09_11.md) for independently
> reproduced layer probes and their explicit limits; they are not a complete B2 PASS.
> Continue with the modelled session and real S1-to-S3 acceptance before clearing the
> runner batch for push. No board, image build, commit or push action was performed.
> The earlier implementation and review banners below are historical.

> **The runner review's five P2s and two P3s are corrected — and one half of it is not.**
> The session verdict now COMPOSES the instrument and evidence contract with the record replay
> (`judge_session`), so the review's four probes — its control, STOPPED, PROTOCOL and
> replayed-only/no-audits logs — no longer reach PASS; the result carries the session identity,
> the measured rate and the verified policy that §8's S2 reads, recomputed rather than echoed.
> The wire protocol is read from the B1 manifest (the L6 manifest has no wire selector), so a
> successful preflight no longer raises and the review's `preflight_actual_instrument_shape`
> is ACCEPTED against the real pinned shape; both profiles bind their own master seed; the
> explicit `seeds` are validated before any conversion; the frame arithmetic counts the two
> brackets once (543 frames for 20 records, equal to the review's own figure); the planning
> rate must be finite. **29 runner tests, B2/B3 358, zero skips.**
> **NOT corrected here:** there is still no modelled B2/B2Q session, so the complete offline
> S1 → B2Q → S2 → S3 path is not demonstrated, `b2_manifest.qualify` has not been shown to
> ACCEPT a transition, and the runner has never produced a PASS. See
> [`evidence/b2/corrections_runner_2026_09_11/`](../evidence/b2/corrections_runner_2026_09_11/).

> **Runner integration review HOLD (`fb71b00`).** The redundant-delta P3 is closed;
> the independent B2/B3 suite passes 346 tests with zero skips. The runner still needs
> session-level acceptance around record replay, a working B2Q result/calibration chain,
> a successful preflight against the actual instrument schema, B2Q ruling master binding
> and safe validation of the new explicit seed input. Two frame/rate boundary corrections
> are also recorded. See [the runner review](b2_runner_review_2026_09_11.md) for the
> independent offline counterexamples and their test-double limits. Keep the runner batch
> under review before push. No board clearance, commit or push was performed here.

> **Host tool 3 of 5 written: `host/b2_runner.py`** (with `b1_runner.py` as the template), plus
> two additions to the accepted adjudicator that it needs: a **session scope** (a session of a
> longer run is judged as a session and never claims the run's pooled primary) and an **explicit
> pair-seed list** (B2Q draws under its own label and excludes B2's own set, preregistration
> §6a, so its seeds are not B2's derivation). Two profiles, B2Q against the S1 manifest and B2
> against the S3 manifest; the identity page carries the session's pair slice; the preflight is
> fail-closed in a documented order — manifest, frozen prereg, image and build evidence, header
> freshness, instrument, **instrument pin table**, carrier and its re-adjudicated B1
> qualification, stage and pinned plan through the adjudicator's own input guards, the slice
> inside the plan's split, both rulings bound to session/prereg/image/this manifest (and the
> master seed), boundary, `sb`, evidence directory. `b2_manifest.verify`'s pluggable
> re-adjudication is plugged in: the pinned B2Q evidence is re-judged by the real adjudicator
> against B2Q's own documents and seeds.
> **19 runner tests; the B2/B3 suite is 346, zero skips.** Stated remainders: `host/b2_pins.py`
> does not exist so every preflight refuses there today; B2Q's documents are derived here rather
> than pinned; and `b2_session.run` cannot yet drive a B2Q session under B2Q's seed rule, so the
> B2Q re-adjudication has no modelled end-to-end fixture. **No board session was run and none is
> authorised.** The ruling texts in the module are PROPOSALS until the owner signs them.

> **Adjudicator accepted; its last P3 is closed too.** The owner's acceptance review closed the
> blocking input-validation P2 (135 invalid inputs refused, the valid F1/F2/F3 families accepted,
> an in-domain disagreeing prediction still a named HOLD, an injected defect still INTERNAL
> ERROR / exit 3) and confirmed `best_train = 999` is correctly REFUSED with the domain checks
> retained. The batch was pushed. The remaining P3 — the optional redundant
> `pairs[i].delta_B_minus_A` accepting `false` or `0.0` for 0 — is now typed before comparison:
> **71 adjudicator tests, B2/B3 316, zero skips**; the owner's unchanged `reproduce_domains.py`
> refuses both aliases, so the only two of its 138 cases that no longer match are the two that
> recorded the defect as expected. See
> [`evidence/b2/corrections_delta_type_2026_09_11/`](../evidence/b2/corrections_delta_type_2026_09_11/).
> Next: `b2_runner`, `b2_pins`, `b2_test_report`, then the complete §7 review. Neither §7 nor
> freeze/B2Q nor board work is cleared.

> **Adjudicator correction review PASS (`0d294ea`).** The blocking input-validation P2
> is closed. Both original reproducers pass correction acceptance; 135 additional invalid
> cases are refused, and a valid, self-consistent but disagreeing prediction receives HOLD.
> The independent B2/B3 suite passes 315 tests with zero skips; full-size model replay
> still matches the preregistered numbers. One nonblocking P3 remains on the optional
> redundant `delta_B_minus_A` field's integer type. See
> [the acceptance review](b2_adjudicate_domain_review_2026_09_11.md).
> The host batch may proceed to push and `b2_runner` implementation. The three remaining
> tools and complete §7 review are still required; no freeze/B2Q/board clearance is granted.
> This review performed no commit, push or board action. Earlier HOLD blocks are historical.

> **The adjudicator's input-validation P2 is corrected too.** (A) `check_plan` establishes that
> `fitness` is a string **before** the membership lookup, and every consumed field now follows
> type → domain → use; the CLI's `fitness=[]` case exits 1 with a named refusal instead of
> INTERNAL ERROR / exit 3. (B) `check_prediction` types every value it compares — the run
> counts and digests, the primary counts, the probabilities, the verdict — so Python's numeric
> equality can no longer accept `true` for 1 or `2.0` for 2 in values reported as EXACT; the
> pair identities must be `0..pairs-1` exactly once in order, established **before** any lookup
> is built from them, so a contradictory duplicate is named and an out-of-range entry cannot
> sit unvisited; domains and the document's own accounting (deltas, primary counts, the sign
> test over its own deltas, the sequence length) are checked. (C) the plan's `master_seed` must
> be in `0..2**32-1` (Rng masks to 32 bits) and its map digest 64 lower-case hex.
> The owner's unchanged `reproduce_input_guards.py` now refuses every accepted case with a named
> reason and the previous round's reproducer shows no regression. **70 adjudicator tests
> (was 57); the B2/B3 suite is 315, zero skips**; reverting only `host/b2_adjudicate.py` fails
> 42 sub-cases. One stated consequence: the review's own `best_train = 999` control is now a
> REFUSED (999 is outside F1's ceiling of 40), and the invalid-input vs disagreeing-prediction
> distinction is kept with an in-domain control instead.
> See [`evidence/b2/corrections_adjudicate_inputs_2026_09_11/`](../evidence/b2/corrections_adjudicate_inputs_2026_09_11/).

> **Adjudicator correction review (`da89506`): HOLD remains on input validation.**
> The baseline P2 and planning-scenario P3 are closed; the original counterexamples now
> return named results, including the mixed KILL case. The independent B2/B3 suite passes
> 302 tests with zero skips, and the full-size model replay still matches the prediction.
> The input-validation P2 remains incomplete: array/object fitness values still raise,
> and mistyped or ambiguous prediction declarations can still PASS. See
> [the input review](b2_adjudicate_input_review_2026_09_11.md) for the reproduced cases,
> including seed/digest domain gaps. Correct these before accepting/pushing the adjudicator
> batch. Earlier approvals are unchanged; no push or board action was performed.

> **The adjudicator review's two P2s are corrected.** (1) Shapes are now established before
> each dependent operation — `check_plan` / `check_prediction` over every plan and prediction
> value the module consumes, `structure_findings` over the record array, and a readout map
> keyed by the record's POSITION so a wire value is never a dictionary key; the stateful replay
> does not run over a session the record layer refused (`replay.not_run`), while the per-record
> measurement pass still does, so a served-readout contradiction is never hidden by a shape
> finding; the CLI's last-resort net writes the result file and labels a module defect
> **INTERNAL ERROR** with a traceback and exit 3, never an input refusal. (2) **Both brackets
> must carry the blank genome**, checked where the zero-genome starting population is assumed —
> either bracket failing stops the replay and claims no primary. The owner's own
> `reproduce_adjudicate.py`, unchanged and with common validation enabled, now returns a named
> result for every case that raised, and refuses both baseline mutations. **57 adjudicator
> tests (was 41); the B2/B3 suite is 302, zero skips**; reverting only `host/b2_adjudicate.py`
> fails 37 sub-cases across 16 methods. The P3 is corrected too: the demonstrated 4 + 4 + 1
> partition is labelled an illustrative planning scenario — the plan's split stays UNDETERMINED
> until B2Q. See [`evidence/b2/corrections_adjudicate_2026_09_11/`](../evidence/b2/corrections_adjudicate_2026_09_11/).

> **Adjudicator review HOLD (`1b39951`).** The prior digest-format P3 is closed and
> 286 B2/B3 tests pass with zero skips. The full-size model run reproduces the prediction.
> Two P2 findings remain: malformed inputs can raise after record validation, and
> nonblank opening/closing baseline genomes still pass replay. See
> [the adjudicator review](b2_adjudicate_review_2026_09_11.md) and its independent probes.
> Correct these before accepting/pushing the new adjudicator commit. The demonstrated
> 4+4+1 split is a planning scenario; the committed plan remains UNDETERMINED pending B2Q.
> This review performs no push or board action. Earlier approvals are unchanged.

> **Host tool 2 of 5 written: `host/b2_adjudicate.py`.** It consumes a run's sessions in
> session order and, per record, recomputes the fitness **from the readout that record
> served** (train F1, or the holdout F1 of a champion's re-measurement) and checks the PL's
> additive scores against the same bytes — a served readout contradicting a self-report is a
> KILL, one finding per record. It then replays the reference engine from those same readouts:
> every parent draw, move, child genome, counter, generation, selection, champion and
> `state_sha256`, stopping at the first divergence (a HOLD). Finally it compares each pair and
> arm with the pinned `prediction.json` and, when the sessions cover every preregistered pair,
> the run's fitness-sequence digest and the primary sign test. It verifies no manifest pin,
> qualification chain, rate/deadline budget or export — those are the runner's and `b2_pins`'
> work and are named in its own result under `not_checked_here`.
> **41 tests**; the B2/B3 suite is **286 tests, zero skips**. Demonstrated end to end against
> the real pinned plan and prediction — 10 824 records, PASS, deltas, fitness-sequence digest
> and primary all equal to the preregistered values; one flipped readout word gives a KILL —
> with the **model standing in for a board**: no board, no image build, no session.
> See [`evidence/b2/b2_adjudicate_2026_09_11/`](../evidence/b2/b2_adjudicate_2026_09_11/).
> Remaining: `b2_runner`, `b2_pins`, `b2_test_report`, then the complete §7 review.

> **Record-type correction review PASS (`45791a7`).** The extension-type P2 is closed:
> the original four cases and 330 independent negative cases are rejected; the B2/B3
> suite passes 243 tests with zero skips. One nonblocking P3 remains: a trailing newline
> passes the `state_sha256` format check — **corrected in `9422ae0`**: the digest is matched
> against the whole string with `fullmatch()`, the owner's 330-case matrix still refuses all
> 330 and its newline probe is now a named finding, and the suite is **245 tests, zero skips**.
> See [the correction review](b2_records_types_review_2026_09_11.md).
> The reviewed host-work batch may advance to push and adjudicator implementation;
> this review performs no push or board action. The four remaining host tools and the
> complete §7 image review are still required. Earlier status blocks are historical.

> **Runtime freshness correction PASS (`fe69f95`, verified at `aced532`).**
> The cache P2 is closed and the build-guard review HOLD is lifted. Current image
> `d164cd1d…` and its build inputs verify. The independent B2/B3 suite passes 232 tests,
> zero skips, including the newly added record validator. See
> [the runtime review](b2_runtime_live_review_2026_09_11.md).
> **The new `b2_records` had a separate P2** — malformed extension values could raise
> incidental exceptions or pass unchecked
> ([its initial review](b2_records_initial_review_2026_09_11.md)). **Corrected:** every
> identity and search-block value's JSON type is now checked before anything compares,
> indexes, sorts, hashes or counts it, a JSON boolean is not an integer, and the owner's
> own `reproduce_record_types.py` names all four mutations while still accepting the twin's
> real record. The B2/B3 suite is **243 tests, zero skips**. That validator still awaits
> the owner's review; the other four host tools remain, then §7.

> **Authority-correction review (`fb37ee0`): prior role/inventory findings closed.**
> All 193 B2/B3 tests pass with zero skips, and image `d164cd1d…` still matches its actual
> build inputs. One new P2 remains: cached runtime hashes hide file modification or deletion
> after an earlier successful verification in the same process. See
> [the authority-correction review](b2_build_authority_review_2026_09_10.md) and its isolated
> file-mutation reproducer. Correct the verifier cache and finish the remaining §7 tools;
> this finding alone requires no firmware change or replacement image.

> **Build-guard review (`9c1f3ca`): the previous seven counterexamples are closed.**
> Current image `d164cd1d…` and its actual build inputs verify; all 186 B2/B3 tests pass
> with zero skips. One P2 remains: compiler/runtime identities and required linker/build
> script entries are not fully bound to the actual build. Four additional fixtures pass
> both the verifier and all committed-evidence checks. See
> [the build-guard review](b2_build_guard_review_2026_09_10.md).
> Host work may continue; complete this guard and the five remaining §7 tools before clearance.

> **Correction review (`842abb9`): startup and current image provenance verified.**
> Image `d164cd1d…` matches its recorded source, binary and ELF hashes; the original
> IDENT ordering defect is closed. One P2 remains in the new build-evidence regression
> guard: seven isolated incomplete/contradictory evidence cases still pass. See
> [the correction review](b2_image_correction_review_2026_09_10.md).
> The complete B2/B3 suite passes 172 tests, zero skips (144 excludes the 28 gate tests).
> Host work may continue; complete the guard and remaining §7 tools before clearance.

> **Image integration review (`a32b1fe`): HOLD on accepting image `e06b77a6…`.**
> Two P2 findings: IDENT reports a zero pair slice before initialization, and the built
> image/evidence precede the tested application revision. The independent B2/B3 suite
> passes 159 tests with zero skips. See [the integration review](b2_image_integration_review_2026_09_10.md)
> and its actual-main startup reproducer. Corrections and unfinished host tools may
> proceed; a replacement build and the complete §7 package are required before clearance.
> Earlier status blocks below are historical, including their statements that no image exists.

> **Image core review (`aef237d`): stages 1/2a/2b may proceed to application integration.**
> The independent B2/B3 run is 132 tests: 130 passed, two binary scans skipped because no
> image exists. UBSan host-twin checks reproduce all 10,800 candidate genomes and the
> record blocks, plus ten perturbed-readout runs. See
> [the core review](b2_image_core_review_2026_09_10.md) for a nonblocking comment-scanner
> defect, the limits of legacy wire validation, and the remaining §7 deliverables.
> This is not a completed-image compatibility review or board authorization.

> **Fourth review PASS (`8958b2b`).** Both remaining lifecycle P2 findings are closed;
> all 105 B2/B3 host tests pass. The host-review HOLD on advancing the batch and beginning
> B2 image implementation/build work is lifted. See
> [the fourth review](b2_b3_host_review_v022_2026_09_10.md) for evidence and scope.
> The resulting image still requires the §7 compatibility review before freeze and B2Q.
> Earlier HOLD notices below describe superseded reviews of earlier commits. No push,
> image build, ruling or board action was performed by this review.

> **v0.2.1 third review: HOLD remains.** Record/calibration reconstruction and rate
> feasibility are resolved. Two P2 findings remain: checking the actual image binary,
> and validating the complete plan/prediction contract, including their shared digest.
> See [the third review](b2_b3_host_review_v021_2026_09_10.md). All 104 B2/B3 host tests
> pass, but the additional isolated counterexamples are still accepted. Push and image
> construction are not cleared.

> **v0.2 re-review: HOLD remains.** Five previous P2 findings are resolved at the
> host-design stage. Four reproducible P2 findings remain in the new lifecycle:
> live input verification, evidence-derived calibration, complete plan derivation,
> and refusal of infeasible session durations. See
> [the correction-batch review](b2_b3_host_review_v02_2026_09_10.md).
> Push and image construction are not cleared.

> **Review HOLD (2026-09-10).** Nominal simulation results reproduce, but the control
> design, minimum-N search, B3 anomaly handling and B2 evidence/qualification contracts
> require correction before image construction or push approval. Decisions on D1–D4,
> gate revisions, audit policy and N are in `docs/b2_b3_host_review_2026_09_10.md`.
> The descriptions below preserve the submitted package; they are not a superseding
> approval of the reviewed issues.
>
> **v0.3 (2026-09-11) — the image is built.** The host-only HOLD was lifted by the owner's
> fourth review and the batch was pushed. Two further reviews followed on the image itself:
> the core stages passed with one P3 (fixed), and the integration review raised two P2s —
> the IDENT was emitted before the pair slice was decoded, and the evidence predated a
> firmware edit. Both are corrected in §0d's terms and the image was rebuilt from the tested
> source. What remains for the §7 package: `b2_records`, `b2_adjudicate`, `b2_runner`,
> `b2_pins`, `b2_test_report`.
>
> **v0.2 — the correction batch, submitted for the owner's re-review. HOLD
> stood until the owner lifted it.** **v0.2.1** — the second review
> (`docs/b2_b3_host_review_v02_2026_09_10.md`) closed five of the six findings and found four
> P2 defects in the lifecycle's enforcement; §0b maps those to their corrections. §0a below maps each finding to its correction and
> evidence; §1 lists the new files; §3 is what is asked now. Nothing in the engine, the
> mixture, the fitness family or the session seeds changed; run 1 / run 3 / B3 raw files and
> reports are untouched; corrected summaries are in separately labelled directories.

> **Standing: host-only. No image, no manifest, no ruling, no board.** Stage B2 of
> `docs/autonomous_cartography_roadmap.md`, opened on the owner's instruction of 2026-09-09.
> Roadmap §7 asks for *"a host-only architecture / preregistration package … reviewed before
> carrier v2 is designed — so that no more engineering is spent sending an experiment that
> arithmetic has already decided to the board."* This is that package. The owner reviews it
> and rules; the image is built only after.

## 0. The one paragraph

B2 asks whether B1's board-built map makes the same search engine beat random-safe on a
fitness with real interaction. The package keeps the **qualified B1 carrier unchanged** and
puts the fitness on the PS, because the carrier's raw functional readout already *is* the
whole phenotype (`docs/b2_architecture.md` §2). The landscape is a public seeded rule; three
non-additive fitnesses were fixed in a frozen order; the (μ + λ) engine and the two
operators are shared code with one difference; five controls (oracle, shuffled,
within-LUT-shuffled, three degraded maps) ride the same code path. The **discriminability
gate** (host simulation, 200 landscape seeds, every arm, every fitness) was specified
before it ran. Run 1 failed every fitness on four rows that the run showed were
mis-specified (the budget rule, a wrong "a negative must appear" test, a cost cap tied to
an unstated audit policy, a wrong continuity assumption); the rules were revised **with the
reasons written down and the first report kept**, and run 3 on a clean tree with fresh
seeds **passes F1**; re-evaluated under rules v0.3 (§0a) it still does: B* = 600
evaluations per arm, N = 9 pairs, **10 800 evaluations in total** — how many
all-self-reporting sessions they take is decided by the B2Q-measured rate (three at the
last B1 mapping's rate). F2 and F3 also discriminate but cost 2× more. The shuffled and
within-LUT maps **lose** to random-safe, and the predeclared controls of v0.3 §7a show the
benefit is **correct column grouping** beyond train membership and beyond the size
distributions (G9); the dose–response is monotone and crosses zero (a poor map is worse
than none); holdout is neutral **for F1 / F2** (F3's trajectories reach holdout rows). The
frozen session seeds predict **8 of 9 pairs positive (p = 0.0195)** — the minimum that
passes; the silicon run is a prospective reproduction of that prediction.

## 0a. The review's findings and their corrections (v0.2)

| finding (review §2) | correction | where |
|---|---|---|
| controls D / E cross the train / holdout boundary: the benefit was not attributable to column grouping | two controls predeclared in architecture v0.3 §7a **before running** (`fcfff98`): **T** train-membership only, **W** within-train column scramble (membership and column-size / move-size distributions kept); **G9** = B beats both by exact sign tests at B*. Run on run 3's 200 seeds: **PASS on F1 / F2 / F3** (F1 at 600: B − T +3.23, 169/17/14, p 6e-33; B − W +3.63, 172/17/11, p 9e-34; T retains 22 %, W 13 % of B's benefit). The claim is attributed; D / E stand as "a wrong map costs budget" | `host/b2_maps.py`, `host/b2_gate.py controls`, `evidence/b2/gate/recomputed_2026_09_10/controls_report.json`, `docs/b2_gate_report_v0.3.md` §4, `tests/test_b2_maps.py`, `tests/test_b2_gate.py` |
| `required_pairs` skipped candidate N (F3 / 300: 91 returned, 89 had power 0.906) | a full ascending scan, no bracketing, no n_max shortcut; the counterexample is a test (N = 89, power 0.906, cost 53 400); a synthetic non-monotone profile is a second test. Run 3's rows re-evaluated under v0.3 into a labelled directory (run 3's report untouched): **F1 still selected, B* = 600, N = 9, 10 800**; F2 (N = 8 at 1 500, 24 000) and F3 (N = 13 at 800, 20 800) still fail on cost only | `host/b2_gate.py`, `evidence/b2/gate/recomputed_2026_09_10/gate_report.json`, `tests/test_b2_gate.py` |
| B3 ignored contradictions on decoded addresses; refusals mutated state | `SpecimenCarto.observe` validates (malformed specimens, a decoded moved address whose position is missing, a position of an unmoved decoded address, empty intersections, closure conflicts) and **commits atomically**; the review's three counterexamples plus closure-conflict and malformed cases are tests with `snapshot()` equality; the ideal-model simulation re-run on the same seeds is **bit-identical** (400 rows) | `host/b3_online.py` (carto v1.1), `evidence/b3/sim_v0.1.1/`, `tests/test_b3_online.py` |
| sampled-audit replay underspecified; "recompute every fitness" overclaimed | **all-self-reporting** for B2 (the owner's decision): every record's six readout words served and host-verified; every fitness recomputed from a *measured* readout; no readout-hash language; a sampled policy is not specified for B2 and what one would need is listed | `docs/b2_preregistration.md` §2, §4 |
| B2Q / calibration / final-manifest lifecycle not closed | `host/b2_manifest.py`: S0 init (carrier **lineage** from the B1 manifest, re-verified — certifies history, qualifies nothing) → S1 freeze → S2 qualify (record bound to `manifest_at_run`; the measured rate written into `calibration` in the same licensed transition) → S3 plan (regenerated from the calibration; split and rate checked). B1's strict rule kept; the plan edit that used to break the binding is now the licensed, checked production. Exercised on disk in fresh processes; every later change refused; B1 files asserted unchanged | `host/b2_manifest.py`, `tests/test_b2_lifecycle.py` (6 tests, 20+ refusals), `docs/b2_preregistration.md` §8 |
| a negative primary was impossible under the EXACT prediction gate | the silicon run is a **prospective reproduction of a predicted outcome**; a mismatch is HOLD / KILL; the falsifier that could not occur is removed; a design whose primary is not fixed by the prediction is named as a separate preregistration | `docs/b2_preregistration.md` §1, §3, §4, §5 |
| documentation / provenance (review §3) | four changed rows; `9f347e9` vs `342450b`; canonical-JSON vs file-byte digests (`c6a4b23e…` / `b6607a9a…`), both pinned in the manifest; F3's train trajectories enter holdout rows (seed 123 example) — the neutrality reading restricted to F1 / F2; F1 / F2 have many train optima; Cohen's d at the selected budgets **F2 1.4437, F1 1.5364, F3 0.8506** (§2 below corrected); seed exclusion explicit (1 223 values, recorded in the plan); the sign test stated exactly (ties move the threshold); B3's accounting named an evaluation-count model; "grow without bound" withdrawn; O − F at all budgets = exploratory | `docs/b2_architecture.md` v0.3 header and §8, `docs/b3_architecture.md`, `host/b2_plan.py` |
| the "ahead 10" statement | nine commits were ahead of `6ac2cf2` at review; corrected in the memory file | — |

## 0b. The second review's lifecycle findings and their corrections (v0.2.1)

| finding (review v02 §2) | correction | where |
|---|---|---|
| 1 frozen live inputs not enforced (missing pins filtered out; lineage a diagnostic; a stored chain flag; prereg / map / image not re-hashed) | `verify()` refuses on: any required pin missing from the manifest, absent from the tree or changed; the map changed in **either** encoding or no longer validating; the frozen preregistration's bytes changed; the build-evidence file changed or not naming the image; the B1 manifest file changed or its carrier not this carrier; and the B1 qualification chain **re-verified fresh** by `b1_qualification.verify` on every call (no stored flag). File-only mutation tests on a mirrored tree (deletion, whitespace on prereg / map / B1 manifest) with an unchanged manifest and evidence | `host/b2_manifest.py` `_check_frozen_inputs`, `tests/test_b2_lifecycle.py` |
| 2 calibration and record not reconstructed from evidence | the record is **reconstructed from the evidence files** (exact file set, hashes, the adjudication's outcome / rate / policy, the binding from `manifest_at_run`) and compared field by field with the embedded one; the record schema and key sets are exact; the calibration must equal the one derived from the reconstruction under the split rule; the re-adjudication must agree on outcome **and** rate **and** policy; the policy must be the frozen audit policy. Record + calibration co-mutation, policy change, empty file table: each refused with unchanged evidence | same; tests |
| 3 S3 plan derivation unvalidated | one validator `plan_findings` used at pinning and at every verify: fitness / budget / pairs / engine / map (canonical digest and path) / audit policy / seed derivation (master, label, commit) / the whole split against the calibration / the span limit / the prediction file's hash / the prediction's seed sequence / **the prediction re-derived by the reference engine** (`b2_plan.predict`) for the frozen experiment, seeds and map. `pin_plan` verifies the manifest first (never its flag) and re-verifies the result. Wrong-field tests at pinning and at re-verification with the file hash updated | same; `host/b2_plan.predict`; tests |
| 4 infeasible rate accepted | `session_split` raises on a non-finite / non-positive rate and returns **INFEASIBLE** when not even one pair with its baselines fits the registered expected span; `calibration_from` and `plan_findings` refuse on INFEASIBLE; the one-pair boundary (602 records / h) and 0 / −1 / NaN / ∞ are tests | `host/b2_plan.py`, `tests/test_b2_plan.py` |
| P3 documentation | §0 above agrees with §0a (four rows, total evaluations, F1 / F2 holdout); the plan module's docstring says exclusion is enforced, not assumed | — |

## 0c. The third review's two findings and their corrections (v0.2.2)

| finding (review v021) | correction | where |
|---|---|---|
| 1 the image binary is never opened — a same-size overwrite or a deletion left `qualified: true`, `image: ok`; only the build evidence's *declaration* was compared | `verify()` resolves the image path, **requires the file to exist, hashes its bytes and compares its size** against both the manifest and the build evidence; the check reports the digest it computed (`ok (binary hashed: …)`), so a declaration can no longer masquerade as verification. Every successful fixture now carries genuine image bytes; deletion, truncation, extension, emptying and same-size replacement are tests, as is a manifest whose declared size disagrees | `host/b2_manifest.py` `_check_frozen_inputs`, `tests/test_b2_lifecycle.py::test_2d` |
| 2 the plan / prediction comparison was a subset (session, schema version, the primary block, record counts, per-pair results and the sequence length were never reached), and the manifest's prediction reference was not tied to the plan's sidecar | `plan_findings` now **rebuilds the canonical plan and prediction** from the frozen inputs (`b2_plan.build_plan` / `build_prediction`, factored out of the CLI so the generator and the validator are the same code) and compares the **whole structures** with a recursive diff that names the differing path. `PLAN_NON_OPERATIONAL` is now used and holds exactly two keys: `generated_utc`, and `prediction_sha256` — which is not compared as a value but required to equal the sidecar's digest **and** the manifest's, so a relocated prediction is allowed only when it is the same bytes. Nothing else may differ: any added, missing or changed field is refused at pinning and at every re-verification, including after rehashing | `host/b2_plan.py` `build_plan` / `build_prediction` / `write`, `host/b2_manifest.py` `plan_findings` / `_differences` / `canonical_plan`, `tests/test_b2_lifecycle.py::test_3`, `::test_4` |

The owner's reproducer runs unchanged against the correction and accepts only its three
legitimate baselines (`evidence/b2/corrections_v021_2026_09_10/`); the second review's
twenty cases still behave, with a real fixture binary added so their baseline exercises
the new image check.

## 0d. The image (`firmware/b2/`), and what each part is checked by

The image exists and is reproducible. It has never been on a board; no B2 ruling exists and
it is not `board_ready`.

| part | what it is | its evidence |
|---|---|---|
| `b2_search.c/h` | the (μ + λ) engine, both operators, the public landscape rule (the universe mask DERIVED from the compiled map), F1 from the MEASURED readout | C = Python evaluation by evaluation over both arms, eight budgets and all nine session pairs, including every `search` record block byte for byte — and the C unit's champions give the preregistered deltas (`tests/test_b2_twin.py`) |
| `b2_orch.c/h` | the session order: opening baseline, per pair both arms then both champions' holdout evaluations, closing baseline; the pair seeds derived on the board; the slice decode | C = Python candidate by candidate; the whole nine-pair session is 10 820 records with the preregistered deltas (`tests/test_b2_session.py`) |
| `b2_wire.c/h` | `app_identity` 1.5.0 and `loop_record` 1.3.0 with the `search` block | the bytes the image emits, through the instrument's validator (`tests/test_b2_wire.py`) — **common-envelope compatibility only**: that validator ignores unknown extension fields, so the B2 fields and their cross-record bindings are `b2_records`' and the adjudicator's job, and those are unfinished |
| `b2_app.c` | HAL and state machine; derived from `b1_app.c` (recorded in `IMPORT.json`) | the REAL application off-board, including its `main()` and `establish_identity` (`tests/test_b2_hostapp.py`) |
| `p3_data.h` | the B1 self-map, the carrier's train/holdout split, the seed exclusion | fresh from its generator, map tables equal the committed map entry by entry, forbidden-token scans of the data and of the built binary (`tests/test_b2_leakage.py`) |
| the build | cross-compiled for cortex-a9 with the instrument's pinned toolchain | two clean builds identical in the **binary and the ELF**; the evidence records the toolchain, the sources, 47 translation units and 86 headers, and `tests/test_b2_build_evidence.py` refuses if any recorded source has moved, if the evidence came from a dirty tree, or if the image on disk is not the one it names |

Reading the counts honestly: the 86 headers are **26 embeddedsw, 10 from this repository and
50 toolchain** headers, not 86 embeddedsw headers; the 20 `sources` entries include headers,
the linker script and the build script — the C files linked from this repository are eight
(`b2_app.c`, `b2_search.c`, `b2_orch.c`, `b2_wire.c`, `p3_derive.c`, `p3_rectx.c`,
`p3_pull.c`, `bsp/src/console.c`), and the 47 translation units are those plus the BSP's.

## 1. What was built (host-only; every file additive; nothing in B1 or the instrument changed)

| file | role | tests |
|---|---|---|
| `docs/b2_architecture.md` v0.2 | D1 carrier kept; D2 landscape; the fitness family F2/F1/F3 in frozen order; D3 engine; D4 operators and the controls; the autonomy boundary; §7 gate criteria and the selection rule; the v0.1 → v0.2 revision with reasons; §8 what is not claimed | `test_b2_gate.test_thresholds_are_the_architecture_documents` |
| `host/b2_landscape.py` | universe mask, public target rule, train/holdout, F1/F2/F3 | `tests/test_b2_landscape.py` (13) |
| `host/b2_maps.py` | the operator's view of a `self_map` 2.0.0; oracle / shuffled / within-LUT-shuffled / degraded renderings; schema validation (draft 2020-12, a missing validator is a refusal) | `tests/test_b2_maps.py` (11) |
| `host/b2_search.py` | the (μ + λ) engine, the two operators, the model fabric with the incremental toggle, seed derivation | `tests/test_b2_search.py` (13) |
| `host/b2_gate.py` | the gate: runs, statistics (exact sign test, bootstrap power, Cohen's d), criteria G1–G8, the budget rule, the report | `tests/test_b2_gate.py` (21; one negative per criterion through `evaluate()`) |
| `host/b2_gate_report_md.py` | renders `docs/b2_gate_report.md` from the JSON | — |
| `host/b2_plan.py` | the session seeds by the B1 rule under `b2-session|` with every archived set excluded, the all-self-reporting plan, the frozen split rule (`session_split`), the prediction | `tests/test_b2_plan.py` (8) |
| `host/b2_manifest.py` (v0.2.2) | the manifest lifecycle S0–S3 and `verify`: live-byte checks including the image binary, the reconstructed B2Q record, and the canonical plan / prediction comparison | `tests/test_b2_lifecycle.py` (11, fresh-process) |
| `evidence/b2/gate/` | run 3 (rules v0.2, as run): `gate_report.json`, `raw_F1/F2/F3.json`; run 1 (rules v0.1) under `v0.1_2026-09-10/`; **`recomputed_2026_09_10/`** = run 3's rows under rules v0.3 + the §7a controls (`controls_report.json`, `raw_controls_*.json`) | — |
| `evidence/b2/plan.json`, `prediction.json` | the frozen-seed plan (split UNDETERMINED until S2) and prediction — deltas unchanged by the corrections | — |
| `docs/b2_gate_report_v0.3.md` | the recomputation and G9, rendered from the JSON | — |
| `docs/b2_preregistration.md` DRAFT v0.2 | the claim as a prospective reproduction, pins, prediction, decision rule, falsifiers, the sessions and the split rule, compatibility, the lifecycle and freeze | — |

## 2. What the gate showed (`docs/b2_gate_report.md`; the numbers are the JSON's)

- **Discrimination is not the problem.** On every fitness arm B (self-map) beats arm A
  (random-safe) with a large effect at the selected budget (at B*: F1 / 600 Cohen's d 1.5364,
  182 / 9 / 9 positives / negatives / ties over 200 seeds; F2 / 1 500 d 1.4437; F3 / 800
  d 0.8506 — the v0.1 prose's "F2 ≈ 0.8 / F3 ≈ 0.7" were stale run-1 numbers).
- **A wrong map does not merely fail to help; it hurts.** Shuffled (D) and within-LUT
  shuffled (E) have negative mean Δ on every fitness, and the sign test on D is nowhere near
  significant. D and E also move addresses across the train / holdout boundary, so this
  shows a wrong map costs budget; it does **not** by itself attribute the benefit.
- **The attribution is G9 (v0.2):** the self-map beats train-membership-only (T) and the
  within-train column scramble (W) on every fitness — correct column grouping adds benefit
  beyond knowing which addresses matter and beyond the column-size / move-size
  distributions (`docs/b2_gate_report_v0.3.md` §4).
- **Dose–response**: Δ falls monotonically with the fraction of the map removed and crosses
  zero between q = ½ and q = ¾. Under the ½ mixture a poor map diverts half the budget to a
  small subset. This is a property of the operator and is stated, not tuned (architecture
  §8); the mixture weight was not changed after seeing it.
- **Holdout is neutral**: champion holdout medians are equal across arms.
- **Cost decides between fitnesses**, not discrimination: F1's powered test is 10 800
  evaluations in total; F2 needs 24 000, F3 20 800. How many all-self-reporting sessions
  10 800 take is decided by the B2Q-measured rate under the split rule (at the last B1
  mapping's ≈ 2 807 / h: three sessions, 4 + 4 + 1; two is not assumed).
- **Consistency across seed sets**: F1 was the passing fitness in run 2 (`eff1771`, N = 10,
  12 000) and run 3 (`7b49f4c`, N = 9, 10 800); run 1 under the v0.1 rules already showed
  the same effects with the failing rows being cost, the q = 1 endpoint and the F1 sign
  test at 1 500 (200/200 positive).

## 3. What the owner is asked to rule on (v0.2)

The five items of v0.1 were decided in the review (D1–D4 accepted in principle; the gate
revisions accepted as development revisions; all-self-reporting; N = 9 retained; no image
yet). What is asked now:

1. **Re-review of the corrections** (§0a) — in particular: the §7a controls and G9 as the
   attribution; the v0.3 G5 (a total-evaluation bound; sessions from the measured rate);
   the reproduction framing of the preregistration; the lifecycle S0–S3 and its tests.
2. **Whether the HOLD is lifted** for (a) pushing the batch, (b) building the image under
   the preregistration's §7 guards. Neither is assumed. No B3 firmware or board work is
   asked.

## 4. What is not asked, and not done

No board contact. No image. No manifest. No ruling text. No change to `zynq-psoracle`, to
B1's files, evidence or manifest, or to the B1 carrier. No probe of unattested bits, no
routing, no `08EB`. No tuning of the engine or the operator after the gate. B3 is a separate
package (`docs/b3_architecture.md`, design and host simulation only).

## 5. Tests and the clean-tree proof

The whole suite (B1's 1 456 + B2/B3's) runs from a clean tree; the result line and the
tested commit are in the commit message of the batch's last commit. A `b2_test_report.py`
in `host/b1_test_report.py`'s discipline comes with the image.
