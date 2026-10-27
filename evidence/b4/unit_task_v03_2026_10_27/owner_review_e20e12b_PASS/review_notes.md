# Independent review notes — task-v0.3, e20e12b

Final disposition: see README.md (PASS). These notes preserve the independently established source/test findings; this is not a production execution authorisation.

## Established checks

- Reviewed committed branch tip e20e12b, base e084f07. Local shared-object clone with detached checkout for all tests; ignored/untracked original files were not imported. Original tracked worktree remains untouched.
- Full local B4 test suite: 332 tests OK, no skip, 560.683s. Explicit mechanics schedules and their production-draw guards are retained.
- New-contract mutants M58–M72, including re-aimed M67: independently rerun, 15/15 KILLED, each with a green baseline and Ran N>0 / FAILED, no EDIT-MISS or BASELINE-NOT-GREEN. The full historical72 battery was inspected rather than repeated; the historical disk-authority equivalents are unchanged.
- Independent scripted input verifies uniform() arguments 2,4,256 per step, in that order, and expected high/low broadcast outputs. Four already exposed mechanics values (3,5,7,8) exercise real FF planted configurations: complete target returns, raw-grid self-score64/80, setup reconstruction zero findings, carrier STEP_IN round-trip and realisability, non-broadcast task tamper refused after its digest is refreshed. No search benefit or K9 rate is estimated by this probe.
- Source comparison to historical table e084f07 confirms all K1–K10, grid/budget/controls and original target rules unchanged; all previous go/no-go values/rules unchanged after alpha_go→p_max_go rename. The provenance source string is excluded from this comparison. Every one of59 IMPORT file digests matches.
- Protected scientific/historical and carrier paths unchanged: model state machine, hypothesis/mapping, engine/carto/replay/execution, K9/K10/statistics, RTL/regmap/records, certificates, receipt, production archives/decisions, B1–B3 surfaces.
- Protocol SHA256 is 5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f; task stimulus rule/constants/broadcast are bound in the task component and complete file inventory. Model hypothesis and anchor basis are unchanged.
- Manifest-only historical re-verification preparation for sim-4: recorded code HEAD495cc36,45 repository-input hashes and28 tool hashes match their git blobs; all6 external UNISIM input hashes still match. No seeds, coverage/search-effect statistics, historical deep verifier or new observation was read/run in that check. The documented old-HEAD route is backed by its inputs; old source code remains historical, not upgraded in place.

## Accepted implementation choices

The new task generates shared CE/SR control values as0/255 without changing the common8-bit grammar. INIT/SRVAL per element, D per element, K6/8, masks, weights, ceiling64/80, planted T-i rule and PublicTask boundary are retained. Non-uniform vectors remain valid hypothetical inputs of the unchanged general model, but are named refusals at the new task-record boundary; the carrier's own rejection remains an invariant. The model-state-machine decision is supported by the uniform-bit identity at every element and the model/twin test, not by an assertion of silicon behaviour.

Ceiling is the number/weight of scored cells. The target's own stored trace self-scores at that ceiling when its full return is valid. Neither fact implies that an arm finds the target or that a map helps. K9's set/rules remain unchanged, while coverage under a changed stimulus is a new estimand. No new K9/arm-benefit value is predicted or inferred from the mechanics checks.

b4-sim-4 is consumed; b4-sim-5 is only reserved. Retaining the never-derived b4-gate-2 reservation does not reuse an exposed set. Test assertions were examined: the K9 change reads the intended all-panel uncovered list for its assertion; registry tests now recognise existing gonogo output; standing text is pinned to the new version. No loader or scientific rule was weakened by those assertion corrections.

## Nonblocking document correction to fold into closure

`docs/b4_archive_reverification.md` section6 currently says every newer verifier/judge/policy refusal lists protocol components and points to that document. The batch verifier, judge and policy's **batch** entry do so. The **existing gonogo decision-record verifier**, however, first checks the recorded policy's shape; an old alpha_go policy is rejected as `policy: not the table's` before protocol identity comparison. This is safe named refusal, no reinterpretation or new decision, and was disclosed in the unit README. Amend section6 to state that exception and keep directing historical verification to the recorded HEAD. No runtime change, method-identity change or new test round is requested for that wording correction.

A3/A8, physical initialization/sampling, PCAP/firmware integration, B4Q and frozen board preregistration remain outside this engineering acceptance. Prior gate FAIL and sim-4 no-go remain unchanged. No production seed derivation/exploration/gate, board/2d/routing, push or merge is authorised by this review.
