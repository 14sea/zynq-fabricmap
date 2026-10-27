# Owner review of 4fc3dc7 — PASS, 2c-obs document engineering acceptance

2026-10-21. Reviewed exact tip `4fc3dc70b5a84355298e4f3f30ab3443f62a0cf1`, parent `6927c2452ad7f8ead23d78a0061a3c201b872ac1`, branch `b4-2c-obs`, clean tree. **The 2c-obs document unit is accepted and may close.** No remaining P1/P2 finding was found in this review. This is acceptance of the draft observation contract, not a physical qualification or frozen preregistration.

## 1. Independent checks

- `python3 -B -m unittest b4.tests.test_b4_seeds b4.tests.test_b4_thresholds`: **29 tests OK**, no skip.
- The author's static script was rerun from a temporary copy; its generated output is **byte-identical** to the committed output and `all_pass` is true. No tracked output was overwritten.
- Independent static/manual cases cover an opening bound to a preexisting trusted reference; absence of the opening; a future/own-close reference; startup mismatch; a self-declared wrong reference; a wrong root-to-opening hash; and drift of the root's actual pre-event value. These are symbolic data and checks of the written dependency rules, not model or device observations.
- Independently derived the four constant-restore cases: value 0/1 with INIT present → row 4; value 0/1 with INIT absent → row 5. The author's function agrees. Restore values tracking INIT still yield row 1; the invalid-reference unknown path and A5 clear/persistence examples remain intact.
- The preceding owner review's **nine files** are archived byte-for-byte, including verified checksums. Selection scripts/outputs are unchanged and were not rerun. Architecture text before section 13, including choice 7, is unchanged.
- `b4/`, hypothesis/domain, statistics, historical pinned surfaces, certificates, production archives, receipt and decisions remain unchanged from `fceedd6`. The reviewer made no tracked changes. No full suite, mutants, production verifier, seed derivation, model or board observation was run.

## 2. Both remaining P2 items resolved

**R1, mechanism-(c) bootstrap: accepted.** Sections 4.1, 5.4 and 5.5 now give the root a session-opening record that exists before signing/event execution. Its startup readback is checked against an independently pinned carrier/base-frame input, not against a value derived from the session, its nonexistent predecessor or its own future X. A mismatch retains a refused record and prevents root signing. The root's event parameters identify the opening by digest. Normal and A5 J3 references remain distinct and unchanged. This resolves the circular reference.

The new opening and base-frame reference are **requirements on the future carrier/tool implementation**, not a claim that their schema, manifest extension or actual readback/reference encoding has already been built or measured. That implementation must use matching frame coverage and encoding, and must derive/pin the expected content independently before the session. The frame-table digest, bitstream-file digest and frame-content/readback digest are different commitments; metadata alone is not a measured configuration. The present acceptance checks the source/dependency contract with symbolic witnesses and makes no contrary claim.

**R2, absent SRVAL main effect with an identified restore: accepted.** Section 6.7 now includes all-restore with no within-INIT SRVAL contrast in `srval_absent`. This gives the intended reduced-claim rows for a constant restore. The separate cross-tracking guard still takes priority when the value changes with INIT. Existing mixed-corner, invalid-reference and direction rules remain. This restores the agreed distinction between an absent effect and inconsistent/wrong-bit evidence without changing a threshold or historical result.

The earlier corrections remain accepted: distinct retained representations/encodings and commitments; immutable O/F/X and partial invalid O; per-mechanism/context frame binding; A5's projection and explicit qualification exception; same-element A8 cross, valid reference/prior controls and bounded outcome classification; actual carrier samples separated from the model's null/scoring domain; trusted source selection; explicit G6 and unresolved physical mechanism/timing.

## 3. D4 selection decision and documentary closure

**Accept section 7.2's selection rule and section 7.3's nine pairs as the data-informed DRAFT A2 qualification-selection choice for later B4Q planning.** Its source is sim-4/task-v0.2/(b-prime), with the stated address-first pooling, tie breaks and main/x5FF coverage. Preserve the disclosure that it was selected using host-model data. It is not a certificate, legal-composition rule, whitelist, fixed qualification-stimulus guarantee or board-demonstrated control; those remain separate questions.

In the ordinary document-only closure, archive this review, mark the unit accepted/closed and synchronize the architecture's choice-7 note with this accepted selection rule and its reason/precedence. Preserve the old gate-1 choice as history; do not silently rewrite the prior ruling or change the K9 panel, either applicability, model, method, thresholds or archives. Update the related draft's status/pointers consistently. This is the previously proposed selection decision being resolved, not a new experiment or protocol run.

That closure may be completed together without a new scope proposal, per-edit approval or an extra review round. If it only archives this decision and makes those documentary status/selection-note changes, **do not rerun tests, static scripts, mutants or experiments**. The independently verified numerical selection outputs need no repeat.

## 4. Scope of PASS

PASS covers the 2c-obs **document contract**. It does not establish A8, a working init mechanism, electrical timing, schema/adapter implementation, carrier RTL, legal compositions, sampling feasibility on every configuration, silicon agreement or a gate result. The physical full-mask fitness/model-null comparison boundary remains explicit and unresolved for the board-study metric. N, B*, prediction, session partition, whole-site holdout choice and 2c freeze are not supplied by this unit.

The sim-4 no-go and all existing evidence remain unchanged. This review does not authorize production draws/runs, gate-2, another protocol revision, RTL/board work, push or merge. Subsequent work can be scoped around its own purpose; no new waiting date, fixed commit count or other procedural restriction is imposed here.

## 5. Evidence notes

The checks are the enumerated static/manual cases, not a universal validator or proof about a fabric. The earlier C1/C2 helpers retain historical names; their all_pass output should be read with that existing scope note.

`git diff --check fceedd6 HEAD` reports only trailing blank lines in two **byte-identical archived owner stdout files** (`owner_review_6927c24_HOLD/author_static_rerun.txt` and `owner_review_df3b65e_HOLD/author_static_rerun.txt`). Those originate in my earlier output, are not product/document defects, and should remain untrimmed in the raw archives. No correction or separate review is needed for them.

The interruption history can remain as the factual event record already disclosed; this review makes no finding about the internal cause of a classifier interruption and does not alter system restrictions.
