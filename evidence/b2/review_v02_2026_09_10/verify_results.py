#!/usr/bin/env python3
"""Offline checks of the correction batch; existing raw evidence is read only."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import math
import statistics
import subprocess
import sys
import tempfile

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / "host"))
import b2_gate as g
import b2_plan as p
import b2_search as s
import b3_sim as sim

def load(rel):
    return json.loads((R / rel).read_text())

def main():
    report = load("evidence/b2/gate/recomputed_2026_09_10/controls_report.json")
    gate = load("evidence/b2/gate/recomputed_2026_09_10/gate_report.json")
    out = {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=R, text=True).strip(),
           "controls": {}, "selected_budget_power": {}, "b3": {}}
    predeclared = "fcfff981cf007fd96889c88794b98d0df3988061"
    subprocess.run(["git", "merge-base", "--is-ancestor", predeclared, report["head_at_run"]], cwd=R, check=True)
    assert report["architecture"]["last_commit"] == predeclared
    assert report["architecture"]["sha256"] == hashlib.sha256(subprocess.check_output(
        ["git", "show", predeclared + ":docs/b2_architecture.md"], cwd=R)).hexdigest()
    out["control_criteria_committed_before_run"] = True
    for fid in report["results"]:
        rows = load(f"evidence/b2/gate/raw_{fid}.json")["rows"]
        controls = load(f"evidence/b2/gate/recomputed_2026_09_10/raw_controls_{fid}.json")["rows"]
        assert [(x["r"], x["landscape_seed"], x["operator_seed"]) for x in rows] == [
            (x["r"], x["landscape_seed"], x["operator_seed"]) for x in controls]
        bstar = gate["results"][fid]["b_star"]
        k = g.GRID.index(bstar)
        got = g.evaluate_controls(fid, rows, controls, bstar)
        assert got == {k: v for k, v in report["results"][fid].items() if k != "wall_s"}
        out["controls"][fid] = {}
        for arm in ("T", "W"):
            ds = [a["arms"]["B"]["at_grid"][k] - b["arms"][arm]["at_grid"][k] for a, b in zip(rows, controls)]
            pos, neg = sum(d > 0 for d in ds), sum(d < 0 for d in ds)
            prob = sum(math.comb(pos + neg, i) for i in range(pos, pos + neg + 1)) / 2 ** (pos + neg)
            assert prob == got["arms"][arm]["sign_test_p_B_gt_arm"]
            assert statistics.mean(ds) == got["arms"][arm]["mean_delta_B_minus_arm"]
            out["controls"][fid][arm] = {"mean": statistics.mean(ds), "positive": pos,
                "negative": neg, "ties": len(ds) - pos - neg, "p": prob}
        g._init_worker(fid)
        for idx in (0, 199):
            row = controls[idx]
            assert g._one_seed_controls((idx, row["landscape_seed"], row["operator_seed"])) == row
        out["controls"][fid]["fresh_full_grid_rows"] = [0, 199]
        delta = [row["arms"]["B"]["at_grid"][k] - row["arms"]["A"]["at_grid"][k] for row in rows]
        claimed_n = gate["results"][fid]["criteria"]["G5"]["required_pairs_N"]
        n, power = g.required_pairs(delta, .05, .9, 1000, 1, 8, claimed_n)
        assert n == claimed_n
        out["selected_budget_power"][fid] = {"budget": bstar, "minimum_N": n, "power": power}
        print("control checks passed: " + fid, file=sys.stderr, flush=True)

    # Original model evidence and unchanged engine bytes, including all 400 B3 rows.
    old_search = subprocess.check_output(["git", "show", "fabbef1:host/b2_search.py"], cwd=R)
    assert old_search.split(b"def pair_seeds(")[0] == (R / "host/b2_search.py").read_bytes().split(b"def pair_seeds(")[0]
    out["search_unchanged_before_pair_seeds_helper"] = True
    unchanged = ["host/b2_landscape.py", "evidence/b2/prediction.json"]
    unchanged += [str(x.relative_to(R)) for folder in ("evidence/b2/gate/v0.1_2026-09-10", "evidence/b3/sim")
                  for x in (R / folder).glob("*.json")]
    unchanged += ["evidence/b2/gate/gate_report.json"] + [f"evidence/b2/gate/raw_{f}.json" for f in ("F1", "F2", "F3")]
    for rel in unchanged:
        assert (R / rel).read_bytes() == subprocess.check_output(["git", "show", "fabbef1:" + rel], cwd=R), rel
    out["unchanged_since_original_submission"] = unchanged
    b3report = load("evidence/b3/sim_v0.1.1/sim_report.json")
    for fid, stored in b3report["results"].items():
        old, new = R / f"evidence/b3/sim/raw_{fid}.json", R / f"evidence/b3/sim_v0.1.1/raw_{fid}.json"
        assert old.read_bytes() == new.read_bytes()
        rows = json.loads(new.read_text())["rows"]
        assert sim.summarise(fid, rows) == {k: v for k, v in stored.items() if k != "wall_s"}
        sim._init(fid)
        for idx in (0, 199):
            row = rows[idx]
            assert sim._one((idx, row["landscape_seed"], row["operator_seed"])) == row
        out["b3"][fid] = {"all_rows_byte_identical": len(rows), "all_rows_statistics_reproduced": True,
                           "fresh_full_grid_rows": [0, 199]}
        print("B3 checks passed: " + fid, file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(prefix="b2_review_prediction_") as td:
        with contextlib.redirect_stdout(io.StringIO()):
            p.main(["--out", td])
        assert (Path(td) / "prediction.json").read_bytes() == (R / "evidence/b2/prediction.json").read_bytes()
        out["prediction_bytes_reproduced"] = True
        out["deltas"] = json.loads((Path(td) / "prediction.json").read_text())["deltas"]
    excluded, _ = p.frozen_seed_exclusion()
    session = s.pair_seeds(s.master_seed(p.SESSION_LABEL, p.INSTRUMENT_COMMIT), 9, exclude=excluded)
    assert not ({x for pair in session for x in pair} & (excluded | set(s.EXCLUDED_SEEDS)))
    out["excluded_seed_values"] = len(excluded | set(s.EXCLUDED_SEEDS))
    print(json.dumps(out, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
