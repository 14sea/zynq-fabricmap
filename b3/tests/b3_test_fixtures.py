"""Shared fixtures for b3/tests (not a test module): synthetic gate rows shaped like the gate's, and
a lifecycle-2 gate report FIXTURE written into a directory through the tool's own report builder —
its seeds drawn under `b3-gate-2` from a chosen head with the real exclusion, its raw file digested,
its results `evaluate()` on the synthetic rows — so `b3_gate.validate_report` accepts it exactly as it
would a real run. Its numbers are a fixture, never a gate result. THRESHOLDS at the time of writing
are copied into the report: write it under the thresholds the validation will run under."""
from __future__ import annotations

import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b2_search as bs  # noqa: E402
import b3_gate as g  # noqa: E402

G = list(g.GRID)
FIXTURE_HEAD = "f" * 40


def synthetic_rows(S=200, seed=1):
    """Rows shaped like the gate's: O beats R from 600 on with both signs early, F above O in search
    accounting, F end-to-end below O, X ≈ R and wrong everywhere, O decoding well, all obligations clean."""
    import random
    rng = random.Random(seed)
    rows = []
    for r in range(S):
        base = 2
        Rt, Ft, Ot, Xt, Fe, dec = [], [], [], [], [], []
        for b in G:
            rv = min(39, base + int(b ** 0.5 / 2) + rng.randint(-1, 1))
            fv = min(39, rv + 3 + b // 300 + rng.randint(-1, 1))
            ov = min(39, rv + (b // 150 - 2) + rng.randint(-2, 2))          # negative-ish below 300, positive from 600
            xv = min(39, rv + rng.randint(-1, 1))
            fe = base if b <= 333 else max(0, fv - 6)                       # the charged frozen arm: below O from 600 on
            Rt.append(rv); Ft.append(fv); Ot.append(ov); Xt.append(xv); Fe.append(fe)
            dec.append(min(292, b // 3))                                       # decoded count: 200 at 600, complete by 900
        rows.append({"r": r, "landscape_seed": 1000 + r, "operator_seed": 5000 + r, "base_fit": base,
                     "arms": {"R": {"at_grid": Rt, "champion_holdout": 1, "column_moves": 0},
                              "F": {"at_grid": Ft, "champion_holdout": 1, "column_moves": 100, "end_to_end_at_grid": Fe},
                              "O": {"at_grid": Ot, "champion_holdout": 1, "column_moves": 90, "decoded_at_grid": dec, "versions_final": 100,
                                    "anomalies": 0, "wrong_decodes": 0, "evals_to_full_map": 1500, "ledger_entries": 3000, "ledger_schema_findings": [],
                                    "replay_findings": [], "online_map_ok": True, "online_map_findings": [], "online_map_sha256": "0" * 64, "final_state_sha256": "0" * 64},
                              "X": {"at_grid": Xt, "champion_holdout": 1, "column_moves": 90, "decoded_at_grid": dec, "anomalies": 0, "wrong_decodes": 200,
                                    "decoded_final": 200, "shadow_findings": [], "perm_sha256": "0" * 64}}})
    return rows


def write_gate_fixture(d: Path, S: int = 200, head: str = FIXTURE_HEAD, label: str = "fixture", mutate_rows=None) -> Path:
    """gate_report.json + raw_F1.json under d, valid for `validate_report` under the current THRESHOLDS.
    `mutate_rows(rows)` may reshape the synthetic rows before evaluation (the seeds are set afterwards)."""
    d.mkdir(parents=True, exist_ok=True)
    excl, sources = g.gate_exclusion()
    master = bs.master_seed(g.GATE_LABEL, head)
    seeds = bs.pair_seeds(master, S, exclude=frozenset(excl))
    rows = synthetic_rows(S)
    if mutate_rows:
        mutate_rows(rows)
    for row, (l, o) in zip(rows, seeds):
        row["landscape_seed"], row["operator_seed"] = l, o
    b = g.raw_bytes("F1", rows)
    (d / "raw_F1.json").write_bytes(b)
    results = {"F1": g.evaluate("F1", rows)}
    results["F1"]["wall_s"] = 0.0
    seed_x, perm, attempts = g.control_x_draw()
    rep = g.build_report(label, head, False, master, S, excl, sources, seed_x, perm, attempts, results,
                         {"F1": {"path": "raw_F1.json", "sha256": g.sha256_bytes(b), "rows": len(rows)}}, 0.0)
    (d / "gate_report.json").write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
    return d / "gate_report.json"


def rewrite_report(path: Path, mutate) -> None:
    """Apply `mutate(rep)` to a fixture report in place (a tamper for a negative test)."""
    rep = json.loads(path.read_text())
    mutate(rep)
    path.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
