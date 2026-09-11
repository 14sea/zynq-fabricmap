# B2 runner correction review — 2026-09-11

Reviewed HEAD: `366d96f08a9e0bfef228b88091a3f838d5060be7`, six commits ahead of
`origin/main` (`0d294ea`). Review scope: offline code inspection, correction acceptance,
live build-input verification and isolated session-contract probes.

**HOLD remains on accepting/pushing the runner batch.** The earlier wire lookup, ruling
master binding, seed-container validation and both arithmetic/domain P3s are corrected.
The earlier session-acceptance P2 is only partially corrected; the B2Q positive lifecycle
remains unproven, as the implementation report acknowledges. Three remaining P2 gaps in
the composed contract are detailed below. Complete these and the real offline positive
flow before considering the runner complete.

## Correction acceptance

The earlier `review_runner_2026_09_11/reproduce_runner.py` was run unchanged. Its imported
`Fixture.args` now supplies the correct B2Q master; this fixture change is explicitly
acknowledged. Results agree with the correction report:

- The actual pinned instrument shape reaches successful preflight with the previously
  disclosed missing-pins and boundary/`sb` doubles. No wire-field double is needed for
  this first success probe.
- Wrong B2Q master `505806526` is refused in favor of `505806527`.
- B2Q frame arithmetic is 543 frames / 20 records, CRC budget 3.
- Infinite planning rate and malformed explicit seed containers receive named refusals.
- The real B2Q callback returns session `B2Q` and refuses evidence without audits/timing.
  Its rate and policy are absent on that refused input, not echoed from stored results.

The four original record-only callback probes now stop at missing configuration fields.
That is useful API behavior, but it does **not** exercise the new epoch/audit checks.
The new tests also acknowledge that their record-only fixtures stop before the later
instrument branches. In particular,
`test_the_epoch_and_record_count_checks_are_reachable_in_isolation` copies the branch
logic into the test rather than calling `instrument_findings`; removing the production
branch would not make that test fail. Replace that demonstration with calls through a
valid instrument fixture. This review's independent record-count negative control does
call the production branch and receives HOLD.

Live `b2_build_evidence.verify_findings` reports no findings; B1 pins verify all 105
files. Image `d164cd1d…`, ELF `7de96ed2…` and B1 manifest `38238271…fd4ba8` retain their
expected hashes. No ARM rebuild was performed. The independent B2/B3 suite completed:
**358 tests, zero skips, OK in 360.050 seconds**. This is a focused-suite result, not
a full-repository clean-tree report. Review artifacts were written while it ran;
production files remained at the reviewed commit throughout.

## P2-1. Session identity and invocation bindings are still not verified offline

`host/b2_runner.py:314` accepts a `manifest` argument but does not use it anywhere in
`judge_session`. Neither it nor `instrument_findings` compares the run log's
`l6.binding` / `l6.inputs` with the expected invocation. The instrument layer validates
internal consistency; record replay checks the experiment and the slice declared by
the log. Neither establishes the image/prereg/manifest/session authority for this run.
The callback also never compares the log's actual slice with `session_plan`'s selected
slice. Matching the expected record count is insufficient when two slices have the
same length.

The online identity check and preflight remain useful, but the lifecycle calls this
offline callback again without rerunning those online checks. Its output `session`
is assigned from the supplied plan, not established from the evidence's binding.
`readjudicator` at line 375 also ignores its `manifest_at_run` argument.

Independent probes over the real instrument layer receive no finding after removing
`l6.binding`, changing its image or manifest digest, or changing the IDENT carrier
digest. Changing the `manifest` argument likewise has no effect. Separately, real B2
record replay with common validation enabled accepts its own positive fixture with
`l6` removed or the IDENT carrier digest changed. These are complementary layer tests,
not a claimed full B2 session bypass.

Add an explicit B2 session binding validator before granting a session verdict. Bind the
log and IDENT to the expected session, image, preregistration, instrument, manifest,
carrier, universe, experiment, selected slice and pinned inputs. Validate the archived
authorization artifacts against that same invocation. Re-adjudication must use the
validated run manifest and frozen qualification documents; a mutually consistent set
of declarations is not proof that the underlying log belongs to it. Test transplanted
evidence and same-length wrong slices through the actual callback and lifecycle.

## P2-2. Export sealing and qualification input coverage remain incomplete

The new session verdict reads `run_log.json`, `audits.json` and `timeline.json`, but
never invokes an export-seal verifier. The B1 production finalizer checks its immediate
export statuses before calling the callback; that protection does not apply to later
standalone re-adjudication. B1's complete adjudicator separately calls `check_exports`
before `_p3_layer`; copying `_p3_layer` alone omits this check.

The instrument-layer control in this review contains only those three files: no
`exports.json`, `console.log` or `console.ts.log`. The session verdict reaches PASS
when its unrelated B2 record replay is explicitly doubled. This locates the missing
seal check without claiming the B1 transcript is a B2 session.

There is also a concrete lifecycle coverage mismatch: `host/b2_manifest.py:83` still
defines the exact qualification file set as only `run_log.json`, `adjudication.json`
and `manifest_at_run.json`. The now-consumed audits/timeline and the export seal/raw
console are not pinned. Calling `reconstruct_qualification_record` before and after
changing each omitted file produces an identical record. This membership probe uses
synthetic declarations and claims no valid transition. Re-adjudication might catch
some semantic damage; it cannot replace binding the accepted evidence bytes, including
changes that leave the selected metrics unchanged.

Require the declared export schema, exact statuses/file set, file hashes and byte counts
on every session re-adjudication. Expand the qualification record to cover all evidence
inputs and authorization artifacts on which acceptance depends, including the seal.
Use an explicit schema migration as needed. Add valid sealed positive controls and
independent missing/changed-file negatives through real `qualify` and fresh-process
`verify`, rather than only testing record construction with a stored-verdict double.

## P2-3. The session deadline is not enforced by re-adjudication

At `host/b2_runner.py:285`, the measured `session_span_s` is obtained but never compared
with `session_plan['session_timeout_s']`. The called `soak_findings` checks heartbeat
gaps, CRC/bad frames, settle bounds and a minimum duration; it does not implement the
maximum session deadline. B1 checks that limit separately in `b1_findings`, another
piece not supplied by copying `_p3_layer`.

The independent instrument control measures `14.269399352000164` seconds. Giving this
isolated check a one-second deadline changes neither its findings nor its outcome.
This is a scalar boundary probe, **not** a claim that preflight can generate a one-second
B2Q deadline. It demonstrates that the configured maximum has no effect on the offline
verdict. The runtime loop's timeout is not a substitute for validating the archived
session against its authorized limit.

Compare measured span against the expected deadline for B2 and B2Q. The reconstructed
`qualification_session_plan` currently supplies no deadline at all: persist and bind
B2Q's planning-rate input/rule so the offline callback can reconstruct the same limit
used by the producer. Do not derive a permissive deadline from the just-measured rate.
Add boundary controls and an over-deadline fixture with heartbeat gaps still within
their own limit, using the real session adjudicator.

## Evidence limits and completion criteria

`probe_session_contract.py` copies only three files from the committed successful B1Q
attempt 4 into a temporary directory. It runs the real standalone validator, audit
gate, ledger/closure/control checks and timing report. Because that B1 log contains no
B2 search blocks, **only record replay is doubled** for those instrument/composition
probes. The source evidence is untouched. Separate B2 numerical replay probes use the
real adjudicator with common validation. The CRC-over-budget and wrong-record-count
controls correctly HOLD. The file-membership probe exercises the real record builder,
without asserting acceptance by the lifecycle. No end-to-end B2 PASS is claimed here.

The next deliverable remains a complete offline B2/B2Q session model using the real
collector, console, notary, timing and production exporter, then real session adjudication
and S1 → B2Q → S2 → S3 → fresh-process verification. Establish the successful controls
before mutating epoch/closing, audit coverage, timing, bindings, seals and calibration.
No replay or stored-adjudication double may establish that positive transition.

Retain the previous recommendation to pin B2Q's documents/seeds and planning-bound
rule at S0/S1. Keep `b2_pins` and `b2_test_report` tracked as unfinished, without treating
their absence as an explanation for the composed verdict's missing checks.

Artifacts: [`evidence/b2/review_runner_correction_2026_09_11/`](../evidence/b2/review_runner_correction_2026_09_11/).
This review changes only English review artifacts and the package status banner. No
production code, firmware, manifest, ruling, original session evidence or instrument
file was changed. No commit, push or board/port action was performed.
