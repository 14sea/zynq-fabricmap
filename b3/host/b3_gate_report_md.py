#!/usr/bin/env python3
"""Render evidence/b3/gate/gate_report.json as docs/b3_gate_report.md (the numbers, every criterion
PASS / FAIL, the pins). A renderer only: it computes nothing and changes nothing in the JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def fmt(x, nd=3):
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        if x.is_integer() and (x == 0 or abs(x) >= 2):        # medians and counts; a p-value of 1.0 stays "1.00"
            return str(int(x))
        return f"{x:.{nd}g}" if abs(x) < 1e-3 or abs(x) >= 1e4 else f"{x:.{nd}f}"
    return str(x)


def render(rep: dict) -> str:
    L = []
    L.append(f"# B3 gate report — {rep['generated_utc']} (`{rep['head_at_run'][:7] if rep['head_at_run'] else 'no commit'}`, dirty at start: {rep['worktree_dirty_at_start']})\n")
    L.append(f"Rules: {rep['thresholds']['rules_version']} — `{rep['architecture']['path']}` sha256 `{rep['architecture']['sha256']}` "
             f"(last commit `{(rep['architecture']['last_commit'] or '')[:7]}`). Engine `{rep['engine']['version']}` (μ {rep['engine']['mu']}, λ {rep['engine']['lambda']}, k ≤ {rep['engine']['kmax']}); "
             f"cartographer `{rep['carto_version']}`; map `{rep['map']['sha256'][:8]}…`. Seeds: label `{rep['seeds']['label']}`, master {rep['seeds']['master_seed']}, "
             f"{rep['seeds']['count']} pairs, {rep['seeds']['excluded_values_total']} excluded values from {len(rep['seeds']['excluded_sources'])} archived sources plus the fixed list. "
             f"Control X: seed_x {rep['control_x']['seed_x']} ({rep['control_x']['attempts']} attempt(s)), permutation sha256 `{rep['control_x']['permutation_sha256']}`. Wall {rep['wall_s']} s.\n")
    L.append("The gate fitness is **F1**; other fitnesses are reported for information. H9 is a condition on the claim, not on passing.\n")
    for fid, res in rep["results"].items():
        L.append(f"## {fid} — ceiling {res['ceiling']}, {res['seeds']} seeds — **{'PASS' if res['pass'] else 'FAIL'}**"
                 + (f", B* = {res['b_star']}, H9 {'holds' if res.get('H9_claim_condition') else 'fails'}" if res.get("b_star") else "") + "\n")
        L.append("| budget | R | F | O | X | F end-to-end | Δ1 mean (pos/neg/ties, p) | Δ2 mean (p) | ΔX mean (p) | O decoded | N(B) | cost | H1 |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for t in res["per_budget"]:
            d1, d2, dx = t["delta1_O_minus_R"], t["delta2_O_minus_endtoend_F"], t["deltaX_X_minus_R"]
            L.append(f"| {t['budget']} | {fmt(t['median']['R'])} | {fmt(t['median']['F'])} | {fmt(t['median']['O'])} | {fmt(t['median']['X'])} | {fmt(t['median_F_end_to_end'])} | "
                     f"{d1['mean']:+.2f} ({d1['positives']}/{d1['negatives']}/{d1['ties']}, {fmt(d1['sign_test_p'], 2)}) | {d2['mean']:+.2f} ({fmt(d2['sign_test_p'], 2)}) | "
                     f"{dx['mean']:+.2f} ({fmt(dx['sign_test_p'], 2)}) | {fmt(t['decoded_median_O'])} | {fmt(t['required_pairs_N'])} | {fmt(t['search_evaluations'])} | {fmt(t['H1'])} |")
        L.append("")
        L.append("| criterion | result | numbers |")
        L.append("|---|---|---|")
        for name, c in res["criteria"].items():
            nums = {k: v for k, v in c.items() if k not in ("pass", "candidates", "signs_by_budget", "delta2_by_budget_from_b_star", "note", "rule", "claim_condition", "exclusions")}
            L.append(f"| {name} | **{'PASS' if c['pass'] else 'FAIL'}** | " + "; ".join(f"{k} = {fmt(v)}" if not isinstance(v, (dict, list)) else f"{k} = {json.dumps(v)[:120]}" for k, v in nums.items()) + " |")
        L.append("")
        if res.get("b_star"):
            L.append(f"Champion holdout medians at B_max: {res['champion_holdout_median']}. At B* = {res['b_star']}: medians {res['at_b_star_median']}, F end-to-end {res['at_b_star_median_F_end_to_end']}.\n")
    return "\n".join(L).rstrip("\n") + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default="evidence/b3/gate/gate_report.json")
    ap.add_argument("--out", default="docs/b3_gate_report.md")
    a = ap.parse_args(argv)
    rep = json.loads((REPO_ROOT / a.report).read_text())
    (REPO_ROOT / a.out).write_text(render(rep))
    print(REPO_ROOT / a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
