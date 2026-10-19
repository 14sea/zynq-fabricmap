# B4 gate judgement — b4-mech-1 — **invalid** (NOT A GATE RESULT)

Generated 2026-10-19T13:58:27Z at HEAD `3b494eea34707c51abdddd7dac25fb40caf5a90d` (clean tree: True). Evidence: batch_archive `evidence/b4/sim/b4-mech-1_invalid` (status invalid, label b4-mech-1, S = 2, fixture True, sha256 `39430b1823d0e6121736d46f0f05f9d3bd79f5418df166863e01b2fd4699b3e1`; seeds `e33c651e9118477746139dcb88187c046c2b52940c80748d3753add8fda8eeca`, manifest `92c516ffa027cd3dd963a2c346627e89aa04dbd2126703672119e1bf3311f789`; batch HEAD `3b494eea34707c51abdddd7dac25fb40caf5a90d`).

Hypothesis `59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8`, certificate `c69e419f836684872c9edb3754cdb7c76591aaabf69859dab448454c6d78ceef`; thresholds: docs/b4_architecture.md section 9 (v0.1.16), fixed before any exploration or gate run.

**Standing.** NOT A GATE RESULT: the gate's rows applied as written to batch_archive evidence under the label 'b4-mech-1' so that the tool's paths are exercised; this judgement can never be represented as a real gate result — the formal result needs the pinned gate label, S = 200 as planned and a production batch archive

**Scope.** every result is under the behaviour hypothesis v0.3 and the certificate mapping of the one site; a FAIL is confined to this model, public task / panel, operator / control design, budget grid and declared decision procedure; nothing here is a statement about silicon, about the carrier, or about the content class in general; a PASS is never read as evidence about the fabric

**Why this is not the formal result:** a fixture batch; the label 'b4-mech-1' is not the pinned gate label 'b4-gate-1'; S = 2 is not the planned 200; the batch is 'invalid', not complete.

## Verdict: **invalid** — a tool / source / replay / control contract break is invalid, never a landscape failure

## The budget rule — **not_assessable**: B* = None, N = None, N × 3 × B* = None, eligible None

the batch is invalid

## The rows

| id | criterion | status | reason | value | threshold |
|---|---|---|---|---|---|
| K1 | non-saturation | **not_assessable** | the batch is invalid: no pooled summary, nothing is judged | `null` | `{"medians":"median_r(best_R(B)) > median_r(base_r), two medians compared","omega_best_p95_lt":64}` |
| K2 | not a definitional lock | **not_assessable** | the batch is invalid: no pooled summary, nothing is judged | `null` | `{"population_variance_gt":0,"x_minus_r_nonrejection_min":0.9}` |
| K3 | wrong maps do not profit | **not_assessable** | the batch is invalid: no pooled summary, nothing is judged | `null` | `{"ratio_max":0.1,"sign_test_p_gt":0.05}` |
| K4 | headroom against the certificate-derived grouping | **not_assessable** | the batch is invalid: no pooled summary, nothing is judged | `null` | `{"f_over_omega_min":0.5,"omega_median_max":57.6}` |
| K5 | effect, power, N | **not_assessable** | the batch is invalid: no pooled summary, nothing is judged | `null` | `{"cap_search_evaluations":4000,"cohen_d_min":0.5,"power_min":0.9}` |
| K6 | no fixed-seed lock | **not_assessable** | the batch is invalid: no pooled summary, nothing is judged | `null` | `{"N_min":8,"S_gate":200}` |
| K7 | the map is a map | **not_assessable** | the batch is invalid: no pooled summary, nothing is judged | `null` | `{"o_prefix_median_not_unknown_min":11,"recomputation_mismatches":0}` |
| K8 | ledger replay | **not_assessable** | the batch is invalid: no pooled summary, nothing is judged | `null` | `{"replay":"no finding on every executed run; a broken tool contract is invalid under section 9.1"}` |
| K9 | observability | **not_assessable** | the batch is invalid: no pooled summary, nothing is judged | `null` | `{"median_coverage_per_semantic_min":0.5,"seeds_with_all_seven_positive_controls_min":0.9}` |
| K10 | real interaction | **not_assessable** | the batch is invalid: no pooled summary, nothing is judged | `null` | `{"interacting_seeds_over_S_min":0.5,"tau":2}` |

### Methods (fixed; section 9)

- **K1** — percentile(best_Omega(B*), 95) < 64 (B2 linear interpolation, by copy) and median_r(best_R(B*)) > median_r(base_r), two medians compared; eligibility at every grid budget decides B*
- **K2** — population variance of {delta1_r} at B* > 0; one grid budget with positives and negatives of delta1; the one-sided exact sign test on X - R at B* with size N (H1: P(X - R > 0 | X - R != 0) > 1/2) not rejecting H0 in >= 90 % of 1 000 bootstrap experiments (random.Random(7), alpha 0.05, ties out of n and kept in the population)
- **K3** — mean(F - R) > 0 and mean(D - R) <= 0.10 mean(F - R); mean(O - R) > 0 and mean(X - R) <= 0.10 mean(O - R); D's and X's one-sided sign tests (H1: P(control - R > 0 | != 0) > 1/2) not significant (p > 0.05); a non-positive denominator is not readable as satisfied
- **K4** — median_r(best_Omega(B*)) <= 0.90 * 64 = 57.6; mean(Omega - R) > 0 and mean(F - R) >= 0.50 mean(Omega - R)
- **K5** — paired Cohen's d of {delta1_r} at B* >= 0.5; N(B*) by the complete ascending scan of required_pairs (8 .. S, alpha 0.05, bootstrap power >= 0.90, 1 000 experiments, random.Random(1 + N)); N x 3 x B* <= 4 000 search evaluations
- **K6** — S = 200 planned (never the number completed) and N >= 8
- **K7** — (a) zero recomputation mismatches on every arm's own ledger (the completion contract: each audit's recompute findings empty, re-audited by the archive-wide verifier); (b) median_r over seeds of the addresses whose state is not unknown in arm O's B* prefix >= 11 of 21
- **K8** — the replay of every executed run reports no finding, the recorded q grid recomputes the recorded fitness, X's shadow isomorphism and the source-identity / fixture boundary hold (the completion contract; a break is invalid under 9.1)
- **K9** — on the fixed comparison set of 9.3: (a) >= 90 % of all S seeds have, for each of the seven semantics, an applicable pair whose readouts differ; (b) per semantic, the median over all S seeds of the coverage fraction >= 0.50 (a semantic not assessable for one seed has no median and does not meet (b))
- **K10** — tau = 2: interacting seeds (max|I| > 2 over both fixed backgrounds, all 210 pairs) / all S >= 0.50; not-assessable seeds stay in the denominator

## Diagnostics (no threshold)

```json
{
 "deadline": {
  "checks": 1649,
  "clock": "time.monotonic",
  "elapsed_s": 5.416,
  "expired": false,
  "first_expired_at_s": null,
  "seconds": 3600
 },
 "standing_of_the_batch": "exploration data under the label given, S as planned; not a gate verdict; the thresholds of docs/b4_architecture.md v0.1.15 section 9 are listed for reference only; candidate B* / N are estimates on this S, never the formal S = 200's"
}
```

Self-validation and the file index are in `gate_report.json`; the verifier `b4_gate_verify.py` recomputes this judgement from the evidence and re-renders this file.
