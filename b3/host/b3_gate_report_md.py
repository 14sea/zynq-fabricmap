#!/usr/bin/env python3
"""Render evidence/b3/gate_2/gate_report.json as docs/b3_gate_2_report.md (the numbers, every criterion
PASS / FAIL, H9 as a diagnostic, the pins). A renderer only: it computes nothing and changes nothing in
the JSON. Lifecycle 2 (architecture v0.3 §9): H9 is reported, never "holds" or "fails"; lifecycle 1's
docs/b3_gate_report.md is never overwritten (the tool refuses that output path) and a lifecycle-1
report (H9 as a criterion / claim condition) is refused rather than rendered under the new reading."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b3/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b3_gate as b3g  # noqa: E402

REPORT_DEFAULT = "evidence/b3/gate_2/gate_report.json"
OUT_DEFAULT = "docs/b3_gate_2_report.md"
LIFECYCLE1_OUT = REPO_ROOT / "docs/b3_gate_report.md"


def fmt(x, nd=3):
    """Medians and counts: integral values as integers, others to `nd` significant digits."""
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        if x.is_integer() and (x == 0 or abs(x) >= 2):
            return str(int(x))
        return f"{x:.{nd}g}"
    return str(x)


def fmt_p(p) -> str:
    """A p-value never rounds to 0: three significant digits, scientific when small (0.0024 -> 0.0024,
    3.79e-09 -> 3.79e-09, 1.0 -> 1)."""
    if p is None:
        return "—"
    return f"{p:.3g}"


def fmt_any(v) -> str:
    """Any JSON value, complete — nothing is truncated; floats to 6 significant digits."""
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return fmt(v) if not isinstance(v, str) else v
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, list):
        return "[" + ", ".join(fmt_any(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {fmt_any(x)}" for k, x in v.items()) + "}"
    return str(v)


def render(rep: dict) -> str:
    """The Markdown of a report dict of the lifecycle-2 shape (the shape alone is checked here; the
    CLI reads a report only through `b3_gate.validate_report`)."""
    if not b3g.is_lifecycle2_report(rep):
        raise b3g.Refusal("not a lifecycle-2 gate report (H9 must be under diagnostics, never a criterion or a claim condition): not rendered")
    L = []
    L.append(f"# B3 gate report (lifecycle {rep['lifecycle']}) — {rep['generated_utc']} (`{rep['head_at_run'][:7] if rep['head_at_run'] else 'no commit'}`, dirty at start: {rep['worktree_dirty_at_start']})\n")
    L.append(f"Rules: {rep['thresholds']['rules_version']} — `{rep['architecture']['path']}` sha256 `{rep['architecture']['sha256']}` "
             f"(last commit `{(rep['architecture']['last_commit'] or '')[:7]}`). Engine `{rep['engine']['version']}` (μ {rep['engine']['mu']}, λ {rep['engine']['lambda']}, k ≤ {rep['engine']['kmax']}); "
             f"cartographer `{rep['carto_version']}`; map `{rep['map']['sha256'][:8]}…`. Seeds: label `{rep['seeds']['label']}`, master {rep['seeds']['master_seed']}, "
             f"{rep['seeds']['count']} pairs, {rep['seeds']['excluded_values_total']} excluded values from {len(rep['seeds']['excluded_sources'])} archived sources plus the fixed list. "
             f"Control X: seed_x {rep['control_x']['seed_x']} ({rep['control_x']['attempts']} attempt(s)), permutation sha256 `{rep['control_x']['permutation_sha256']}`. Wall {rep['wall_s']} s.\n")
    L.append("The gate fitness is **F1**; other fitnesses are reported for information. The gate is H1–H8 and the budget rule. "
             "H9 is a diagnostic (architecture v0.3 §9): Δ2 = O − end-to-end F at every budget ≥ B*, with N₂(B) by the same bootstrap rule "
             "and Δ2's power at the gate's N — reported, it decides nothing (Δ2 is the preregistration's secondary outcome).\n")
    for fid, res in rep["results"].items():
        L.append(f"## {fid} — ceiling {res['ceiling']}, {res['seeds']} seeds — **{'PASS' if res['pass'] else 'FAIL'}**"
                 + (f", B* = {res['b_star']}" if res.get("b_star") else "") + "\n")
        L.append("| budget | R | F | O | X | F end-to-end | Δ1 mean (pos/neg/ties, p) | Δ2 mean (p) | ΔX mean (p) | O decoded | N(B) | cost | H1 | N₂(B) | Δ2 power at N(B) |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for t in res["per_budget"]:
            d1, d2, dx = t["delta1_O_minus_R"], t["delta2_O_minus_endtoend_F"], t["deltaX_X_minus_R"]
            L.append(f"| {t['budget']} | {fmt(t['median']['R'])} | {fmt(t['median']['F'])} | {fmt(t['median']['O'])} | {fmt(t['median']['X'])} | {fmt(t['median_F_end_to_end'])} | "
                     f"{d1['mean']:+.2f} ({d1['positives']}/{d1['negatives']}/{d1['ties']}, p {fmt_p(d1['sign_test_p'])}) | {d2['mean']:+.2f} (p {fmt_p(d2['sign_test_p'])}) | "
                     f"{dx['mean']:+.2f} (p {fmt_p(dx['sign_test_p'])}) | {fmt(t['decoded_median_O'])} | {fmt(t['required_pairs_N'])} | {fmt(t['search_evaluations'])} | {fmt(t['H1'])} | "
                     f"{fmt(t['required_pairs_N2'])} | {fmt_p(t['power_delta2_at_gate_N'])} |")
        L.append("")
        L.append("| criterion | result | numbers |")
        L.append("|---|---|---|")
        for name, c in res["criteria"].items():
            nums = {k: v for k, v in c.items() if k not in ("pass", "candidates", "signs_by_budget", "note", "rule", "exclusions")}
            cells = []
            for k, v in nums.items():
                if k.startswith("sign_test_p") or k.endswith("_p") or k in ("power_at_N", "control_X_nonreject_rate"):
                    cells.append(f"{k} = {fmt_p(v)}")
                elif isinstance(v, dict) and "sign_test_p" in v:
                    cells.append(f"{k} = " + fmt_any({kk: (fmt_p(vv) if kk == "sign_test_p" else vv) for kk, vv in v.items()}))
                else:
                    cells.append(f"{k} = {fmt_any(v)}")
            L.append(f"| {name} | **{'PASS' if c['pass'] else 'FAIL'}** | " + "; ".join(cells) + " |")
        L.append("")
        h9 = res["diagnostics"].get("H9")
        if h9:
            L.append(f"H9 diagnostic (decides nothing) — Δ2 = O − end-to-end F at every budget ≥ B* (one-sided sign test, α = {h9['alpha']}); "
                     f"N₂(B) = the pair count the gate's bootstrap rule would need for Δ2 (power ≥ {h9['power_min']}); the gate's N = {h9['gate_N']}:\n")
            L.append("| budget | p | mean Δ2 | median Δ2 | pos/neg/ties | Cohen's d | N₂(B) | power at N₂ | Δ2 power at the scan's last N (no N₂) | Δ2 power at the gate's N |")
            L.append("|---|---|---|---|---|---|---|---|---|---|")
            for r in h9["delta2_by_budget_from_b_star"]:
                at_max = "—" if r["power_delta2_at_scan_max_N"] is None else f"{fmt_p(r['power_delta2_at_scan_max_N'])} at N = {r['scan_max_N']}"
                L.append(f"| {r['budget']} | {fmt_p(r['sign_test_p'])} | {r['mean']:+.3f} | {fmt(r['median'])} | {r['positives']}/{r['negatives']}/{r['ties']} | "
                         f"{fmt(r['cohen_d'])} | {fmt(r['required_pairs_N2'])} | {fmt_p(r['power_at_N2'])} | {at_max} | {fmt_p(r['power_delta2_at_gate_N'])} |")
            L.append("")
        else:
            L.append("H9 diagnostic: no B*, nothing to report.\n")
        cands = res["criteria"]["budget_rule"].get("candidates")
        if cands:
            L.append("Budget rule candidates (N(B), search cost N × 3 × B, H1): " + "; ".join(f"{c['budget']}: N {fmt(c['N'])}, cost {fmt(c['cost'])}, H1 {fmt(c['H1'])}" for c in cands) + "\n")
        if res.get("b_star"):
            L.append(f"Champion holdout medians at B_max: {res['champion_holdout_median']}. At B* = {res['b_star']}: medians {res['at_b_star_median']}, F end-to-end {res['at_b_star_median_F_end_to_end']}.\n")
    return "\n".join(L).rstrip("\n") + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=REPORT_DEFAULT)
    ap.add_argument("--out", default=OUT_DEFAULT)
    a = ap.parse_args(argv)
    out = REPO_ROOT / a.out
    try:
        if out.resolve() == LIFECYCLE1_OUT.resolve():
            raise b3g.Refusal(f"{b3g._rel(LIFECYCLE1_OUT)} is lifecycle 1's rendered report and is never overwritten (write to {OUT_DEFAULT})")
        b3g.refuse_lifecycle1_path(out)
        rep = b3g.validate_report(REPO_ROOT / a.report)        # the same validator the plan uses: nothing unvalidated is rendered
        text = render(rep)
        try:
            out.write_text(text)
        except OSError as e:
            raise b3g.Refusal(f"cannot write {b3g._rel(out)} ({e.__class__.__name__}: {e})") from None
    except b3g.Refusal as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
