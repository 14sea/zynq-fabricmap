#!/usr/bin/env python3
"""End-to-end fixtures of the gate tool (unit 2b-4), kept as evidence: on a HERMETIC repository copy (a temp directory), with
b4_seeds.master_seed / pair_seeds guarded so that NO PRODUCTION SET can be derived, the tool runs
  fail        — a b4-mech-1 batch of two fixture pairs (7 / 11, 8 / 12) under mode gate: complete, no B* (S = 2 < n_min), judged FAIL;
  invalid     — the same with a DOMAIN refusal injected in pair 1's arm O: the batch invalid, judged invalid;
  incomplete  — the same under a fake clock that expires the 60 s deadline inside pair 0's K9: judged incomplete;
  pass        — a SYNTHETIC summary (invented numbers, label b4-mech-7) judged PASS with formal = false;
  fail_b_star — the same synthetic summary with ff_srval's median coverage 0.427083 (the exploration's value): B* exists, K9 FAILS.
Each gate directory is verified by the verifier CLI in a FRESH PROCESS (stdout and exit code kept), then the hermetic root's
evidence/b4/{sim,gate} trees of the case are copied here under e2e/<case>/root/ so that the verification can be repeated from
this evidence directory, and repeated it is (a second fresh-process run on the copy). Nothing here is a gate result.
"""
import json, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
sys.path[:0] = [str(R / "b4/host"), str(R / "b4/tests")]
import b4_execution as ex  # noqa: E402
import b4_gate as bg  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim as sim  # noqa: E402
from b4_test_fixtures import InjectingPort  # noqa: E402
from test_b4_gate import SCHED1, SYN_LABEL, Clock, build_hermetic, git, synthetic_doc, synthetic_summary  # noqa: E402


def guard(*a, **k):
    raise AssertionError("a production seed derivation was reached")


def fresh(gate_dir: Path) -> tuple[int, str]:
    p = subprocess.run([sys.executable, "-B", str(R / "b4/host/b4_gate_verify.py"), str(gate_dir)], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main() -> int:
    out = HERE / "e2e"
    if out.exists():
        raise SystemExit(f"{out} exists: nothing is overwritten")
    head = subprocess.run(["git", "-C", str(R), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    summary = {"head": head, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cases": {}}
    with mock.patch.object(bs, "master_seed", side_effect=guard) as g1, mock.patch.object(bs, "pair_seeds", side_effect=guard) as g2:
        with tempfile.TemporaryDirectory(prefix="b4gate_e2e_") as tmp:
            root = build_hermetic(Path(tmp))
            ns, gns = root / sim.SIM_REL, root / bg.GATE_REL

            def commit():
                if git(root, "status", "--porcelain").strip():
                    git(root, "add", "-A"); git(root, "commit", "-q", "-m", "archive")

            def domain(fabric, role, pair):
                return InjectingPort(fabric, 30) if (pair, role) == (1, "O") else ex.ObservationPort(fabric)
            syn_fail = synthetic_summary()
            syn_fail["k9"]["per_semantic"]["ff_srval"]["median_coverage_over_all_S"] = 0.4270833333333333
            cases = [
                ("fail", lambda: bg.run_gate(root, "b4-mech-1", 2, 3600, out_batch=ns / "b4-mech-1_fail", out_gate=gns / "b4-mech-1_fail", schedule=SCHED1)),
                ("invalid", lambda: bg.run_gate(root, "b4-mech-1", 2, 3600, out_batch=ns / "b4-mech-1_invalid", out_gate=gns / "b4-mech-1_invalid", schedule=SCHED1, port_factory=domain)),
                ("incomplete", lambda: bg.run_gate(root, "b4-mech-1", 2, 60, out_batch=ns / "b4-mech-1_incomplete", out_gate=gns / "b4-mech-1_incomplete", schedule=SCHED1, clock=Clock(step=1.0))),
                ("pass", lambda: bg.judge_synthetic(root, synthetic_doc(synthetic_summary()), gns / f"{SYN_LABEL}_pass")),
                ("fail_b_star", lambda: bg.judge_synthetic(root, synthetic_doc(syn_fail), gns / f"{SYN_LABEL}_fail_b_star")),
            ]
            for name, run in cases:
                res = run()
                commit()
                rec = {"status": res["status"], "exit_code": res["exit_code"], "gate_out": res.get("gate_out") and str(Path(res["gate_out"]).relative_to(root)),
                       "batch_out": res.get("out") and str(Path(res["out"]).relative_to(root)), "reason": res.get("reason")}
                gdir = Path(res["gate_out"])
                doc = json.loads((gdir / bg.REPORT_JSON).read_text())
                rec["verdict"] = doc["verdict"]; rec["formal"] = doc["formal"]; rec["rows"] = {r["id"]: r["status"] for r in doc["rows"]}; rec["budget_rule"] = doc["budget_rule"]["status"]
                code, text = fresh(gdir)
                rec["fresh_verifier_exit_in_hermetic_root"] = code
                case_dir = out / name
                (case_dir / "root" / "evidence/b4").mkdir(parents=True)
                shutil.copytree(gdir, case_dir / "root" / bg.GATE_REL / gdir.name)
                if res.get("out"):
                    shutil.copytree(Path(res["out"]), case_dir / "root" / sim.SIM_REL / Path(res["out"]).name)
                (case_dir / "verify_in_hermetic_root.txt").write_text(f"HEAD {head}\ncommand: python3 -B b4/host/b4_gate_verify.py {gdir}\nexit {code}\n\n{text}")
                code2, text2 = fresh(case_dir / "root" / bg.GATE_REL / gdir.name)
                rec["fresh_verifier_exit_on_the_evidence_copy"] = code2
                (case_dir / "verify_on_the_evidence_copy.txt").write_text(f"HEAD {head}\ncommand: python3 -B b4/host/b4_gate_verify.py {case_dir / 'root' / bg.GATE_REL / gdir.name}\nexit {code2}\n\n{text2}")
                summary["cases"][name] = rec
                print(name, rec["status"], rec["exit_code"], "verifier", code, code2, flush=True)
        summary["production_derivation_calls"] = [g1.call_count, g2.call_count]
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(json.dumps(summary["production_derivation_calls"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
