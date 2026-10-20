# The owner's ruling on the gate tool versus the production execution (2026-10-19), as relayed by the user (build/wip/b4_gate_tool_owner_ruling_2026_10_19.md)

# Owner ruling — B4 gate tool versus production execution, 2026-10-19

Context: b4-prework 85c95d9; b4-sim-3 S=32 accepted as an exploratory data delivery. No formal gate has run. This ruling replaces the earlier recommendation to bundle gate-tool development and the first production S=200 execution into one authorization.

## 1. Decision

Split 2b-4 into (a) a host-only gate-tool unit and (b) the production b4-gate-1 execution. Authorize (a) now. Do not derive the b4-gate-1 master/pairs or execute a production gate under this authorization. A docs-only 2c skeleton may be written alongside the tool unit as described below.

For the current protocol version, retain the fixed K9 comparison set, applicability rule, thresholds, tau, task generator, hypothesis, search engines and seed/anchor/control formulas. A valid formal FAIL is an acceptable result of that version. Do not revise the panel or lower a threshold to make the exploratory result pass. A separately proposed protocol revision may later explain an estimand/design problem and disclose the influence of b4-sim-3, but it cannot be presented as validation by the data that motivated it or silently replace this version. No such revision is authorized here.

The production execution is separately withheld pending tool acceptance and its concrete execution plan. This is not a demand to preserve a label for a favorable result; label consumption alone is not a reason to change the method.

## 2. What the evidence does and does not establish

An independent raw-archive aggregation agrees with the supplied per-address maxima/medians for ff_srval and the sr_kind median. The 32 semantic ff_srval fractions have median 0.4270833333333333 and maximum 0.4791666666666667; none reaches 0.5.

A configuration-only audit (no observations, new seed or simulation run) finds exactly half of each ff_srval address's applicable K9 pairs have SR tied low: 32/64 for AFF/BFF/CFF/DFF and 16/32 for A5FF/B5FF/C5FF/D5FF. Under the current model, SRVAL cannot affect the trace when SR is tied low, yielding the structural upper bound 0.5. This explains why the present coverage criterion is stringent. It does not by itself prove universal FAIL: the frozen criterion is >= 0.5, so equality is allowed. At S=200, with every fraction <= 0.5 and the ordinary median of the two central observations, passing requires at least 101 semantic seed fractions exactly 0.5. No proof about all unobserved task seeds or their distribution was supplied by the 32-seed maxima. Record the bound and the observed deficit separately.

The K5 impossibility claim is also not established. required_pairs_scan uses bootstrap rejection rates of the one-sided exact sign test on O-R. Power depends on the sign/tie distribution and planned N; Cohen's d alone does not determine it. For example, the observed B=32 delta1 has 10 positives, 9 negatives, 13 ties despite a slightly negative mean/d. Increasing N can improve power for a positive conditional sign probability; finite bootstrap rates need not be monotone. Increasing S also changes the empirical distribution and scan limit. None of this guarantees S=200 will pass, raises d automatically, or licenses extending the sample. The current exploration remains no solution for N=8..32, not proof of no effect for every S/N.

If a formal gate fails, its scope is this model, public task/panel, operator/control design, budget grid and declared decision procedure. Do not call it a proof that FF bits or the content class in general are intrinsically indistinguishable.

## 3. Authorized gate-tool deliverable (one complete unit)

Implement b4/host/b4_gate.py and narrowly necessary B4 support, tests, import provenance and report contracts. Reuse the accepted harness/replay/archive-verification machinery as appropriate; do not weaken it or alter scientific constants. Keep the fixture path internal to tests; the public production CLI must not offer a mechanics/allow-dirty bypass. No old B1/B2/B3 pinned surface is edited.

The tool must report every fixed K1-K10 criterion with its method, value, status and reason. Preserve the declared distinctions: a valid complete failure is FAIL; a tool/source/replay/control contract break is invalid; unfinished work is incomplete; absent B*/N leaves dependent criteria not assessable and cannot produce an overall PASS. Do not adjust the budget or sample to repair a failed row. The formal result requires the planned S=200 and the actual production identity; fixture/synthetic cases can never be represented as a real gate result.

Acceptance starts with end-to-end archives and a fresh-process independent verifier, not only green unit tests. On clearly marked mechanics/synthetic evidence cover valid PASS, valid FAIL including no B*, invalid, incomplete, and coordinated-tampering negatives with hashes refreshed. Test refusal/persistence and authoritative bindings, all intended K criteria and their interactions, and a changed single contract with a load-bearing mutant. The independent verifier must be able to return no findings for an internally valid FAIL archive as well as for a valid PASS fixture; it must not confuse clean evidence with a passing scientific criterion. Preserve the original S=32 data unchanged as a read-only descriptive reference if used.

Production seed derivation is forbidden in tests, smoke runs and mutants. Use existing b4-mech schedules, hand fixtures and explicit identity markers, with guards on master/pair derivation. No b4-gate-1 or new b4-sim set is drawn. Derivation formulas can be tested on non-production hand cases as in the accepted seed tests. Keep all fixture output outside real production run namespaces.

Deliver implementation, updated IMPORT, raw B4 regression/affected-mutant results, fresh-process end-to-end verification, and an English unit report together as local commits. Ordinary fixes, tests and document cleanup inside this scope are completed autonomously and reviewed once as a whole unit. Stop early only for a true scope/method change or an unmet explicit stop condition. No full B1/B2/B3 proof is requested. No push or merge is authorized.

## 4. Authorized optional 2c skeleton

One host-only docs/b4_preregistration.md DRAFT skeleton may be prepared in parallel: claims and scope, address-only universe/whole-site holdout choices to be decided, executing-side versus host authority, raw observation versus scoring, carrier A1-A8 obligations, falsifiers, provenance/lifecycle and unresolved dependencies. N, B*, main seeds/prediction, session partition, calibrated rates and board execution must remain explicitly unresolved; nothing is frozen or pinned by this skeleton. No speculation that the gate has passed and no derived production seed is included. Keep it clearly separable from the gate-tool deliverable for review.

Carrier v2 RTL, image builds, provisioning, electrical measurements, purchase, routing operations, 2d and B4-R implementation remain outside this authorization. A host-only observation-contract requirement in the 2c skeleton does not grant carrier or board work.
