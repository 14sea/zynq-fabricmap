# B2 — the pre-image package: what was built, what the gate showed, what is asked (v0.1, host-only, 2026-09-10)

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
before it ran. Run 1 failed every fitness on three rules that the run showed were
mis-specified (cost, a wrong "a negative must appear" test, a wrong continuity assumption);
the rules were revised **with the reasons written down and the first report kept**, and
run 3 on a clean tree with fresh seeds **passes F1** (B* = 600 evaluations per arm, N = 9
pairs, 10 800 evaluations ≈ 1.6 h at the sampled-audit rate). F2 and F3 also discriminate
but cost 2–3× more board time. The shuffled and within-LUT maps **lose** to random-safe,
the benefit is column identity not LUT membership, the dose–response is monotone and
crosses zero (a poor map is worse than none), holdout is neutral. The frozen session seeds
predict **8 of 9 pairs positive (p = 0.0195)** — the minimum that passes.

## 1. What was built (host-only; every file additive; nothing in B1 or the instrument changed)

| file | role | tests |
|---|---|---|
| `docs/b2_architecture.md` v0.2 | D1 carrier kept; D2 landscape; the fitness family F2/F1/F3 in frozen order; D3 engine; D4 operators and the controls; the autonomy boundary; §7 gate criteria and the selection rule; the v0.1 → v0.2 revision with reasons; §8 what is not claimed | `test_b2_gate.test_thresholds_are_the_architecture_documents` |
| `host/b2_landscape.py` | universe mask, public target rule, train/holdout, F1/F2/F3 | `tests/test_b2_landscape.py` (13) |
| `host/b2_maps.py` | the operator's view of a `self_map` 2.0.0; oracle / shuffled / within-LUT-shuffled / degraded renderings; schema validation (draft 2020-12, a missing validator is a refusal) | `tests/test_b2_maps.py` (11) |
| `host/b2_search.py` | the (μ + λ) engine, the two operators, the model fabric with the incremental toggle, seed derivation | `tests/test_b2_search.py` (13) |
| `host/b2_gate.py` | the gate: runs, statistics (exact sign test, bootstrap power, Cohen's d), criteria G1–G8, the budget rule, the report | `tests/test_b2_gate.py` (21; one negative per criterion through `evaluate()`) |
| `host/b2_gate_report_md.py` | renders `docs/b2_gate_report.md` from the JSON | — |
| `host/b2_plan.py` | the session seeds by the B1 rule under `b2-session|`, the plan, the prediction (every fitness, every Δ, the champions' holdout known answers) | `tests/test_b2_plan.py` (7) |
| `evidence/b2/gate/` | run 3 (rules v0.2): `gate_report.json`, `raw_F1/F2/F3.json`; run 1 (rules v0.1) under `v0.1_2026-09-10/` | — |
| `evidence/b2/plan.json`, `prediction.json` | the frozen-seed plan and prediction | — |
| `docs/b2_preregistration.md` DRAFT v0.1 | the claim, pins, prediction, decision rule, falsifiers, the two sessions, compatibility, freeze | — |

## 2. What the gate showed (`docs/b2_gate_report.md`; the numbers are the JSON's)

- **Discrimination is not the problem.** On every fitness arm B (self-map) beats arm A
  (random-safe) with a large effect at the selected budget (F1: Cohen's d ≈ 1.5, 182 / 9 / 9
  positives / negatives / ties over 200 seeds at 600; F2: d ≈ 0.8; F3: d ≈ 0.7).
- **A wrong map does not merely fail to help; it hurts.** Shuffled (D) and within-LUT
  shuffled (E) have negative mean Δ on every fitness, and the sign test on D is nowhere near
  significant. G8: LUT membership alone carries nothing — the round 1′ lesson, reproduced on
  a non-additive fitness.
- **Dose–response**: Δ falls monotonically with the fraction of the map removed and crosses
  zero between q = ½ and q = ¾. Under the ½ mixture a poor map diverts half the budget to a
  small subset. This is a property of the operator and is stated, not tuned (architecture
  §8); the mixture weight was not changed after seeing it.
- **Holdout is neutral**: champion holdout medians are equal across arms.
- **Cost decides between fitnesses**, not discrimination: F1's powered test fits one
  two-hour session at the sampled-audit rate; F2 needs ≈ 24 000 evaluations, F3 ≈ 20 000.
- **Consistency across seed sets**: F1 was the passing fitness in run 2 (`eff1771`, N = 10,
  12 000) and run 3 (`7b49f4c`, N = 9, 10 800); run 1 under the v0.1 rules already showed
  the same effects with the failing rows being cost, the q = 1 endpoint and the F1 sign
  test at 1 500 (200/200 positive).

## 3. What the owner is asked to rule on

1. **The design** — D1 (the B1 carrier kept, fitness on the PS from the raw readout: no RTL,
   no Vivado, no new carrier qualification; the image still needs its own qualification
   session and compatibility review), D2–D4, the controls, and the honest reading of holdout
   (architecture §8).
2. **The v0.1 → v0.2 revision of §7** — three rules changed after run 1 with reasons; run 1
   kept. The owner may reject any of the three; the gate is then re-run under the owner's
   rule and F1 may or may not pass (under v0.1's rules nothing passes, on cost).
3. **The audit policy for the B2 session** — sampled audit (S #3's evidenced policy,
   ≈ 1.6 h, fits one session) or all-self-reporting (≈ 3.2 h, two sessions under two rulings).
   Under either, every record carries the board's fitness and the readout hash, and the
   adjudicator replays the whole search; the difference is how many raw readouts are pulled
   and host-verified.
4. **N** — the gate's N = 9 gives power 0.93 and the frozen seeds predict 8/9, the minimum
   that passes. Raising N is a margin decision with a cost of 1 200 evaluations per pair; the
   package does not recommend it, because changing N after seeing the prediction is the
   kind of step this line has refused before; if the owner wants margin, the reason is
   recorded before freeze.
5. **Whether to build the image** — `firmware/b2/`: the B1 lineage with the search in place
   of the cartographer, the `search` record block, the map's column table and the landscape
   rule compiled in, the C = Python twin, the leakage guards extended to the certificate and
   the oracle rendering, the host application harness, the runner / adjudicator / manifest /
   pin table — the B1 pattern, file for file.

## 4. What is not asked, and not done

No board contact. No image. No manifest. No ruling text. No change to `zynq-psoracle`, to
B1's files, evidence or manifest, or to the B1 carrier. No probe of unattested bits, no
routing, no `08EB`. No tuning of the engine or the operator after the gate. B3 is a separate
package (`docs/b3_architecture.md`, design and host simulation only).

## 5. Tests and the clean-tree proof

The whole suite (B1's 1 456 + B2's) runs from a clean tree; the report is written by
`host/b1_test_report.py`'s discipline once the B2 artifacts exist to pin (a `b2_test_report.py`
comes with the image). Until then the suite's result line is in the commit messages.
