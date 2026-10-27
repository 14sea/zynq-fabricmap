#!/usr/bin/env python3
"""End-to-end fixtures of the protocol v0.2.0 tool unit, kept as evidence (the owner's authorisation of 2026-10-20: "the acceptance must include
... end-to-end cases on b4-mech-* explicit schedules: a complete result, invalid, a stop under way, a target-setup partial, a source drift and
refreshed-hash tampering; a completed fixture archive must re-verify clean under a fresh-process verifier"). On a HERMETIC repository copy
(a temp directory) with b4_seeds.master_seed / pair_seeds guarded so that NO PRODUCTION SET can be derived, the tool runs:

  complete         a b4-mech-1 batch of two fixture pairs under mode gate — complete; judged (FAIL: no B* at S = 2); the batch, the gate and
                   the go / no-go record (no decision: S = 2) each verified by its verifier CLI in a fresh process;
  complete_32      a b4-mech-5 batch of THIRTY-TWO fixture pairs (explicit already-exposed values) under mode exploration — the section 9.4
                   go / no-go policy applied once (whatever it says on fixture data: a path exercised, never a decision of record);
  invalid          the two-pair batch with a DOMAIN injected in pair 1's arm O — invalid, judged invalid;
  incomplete       the same under a fake clock that expires the 60 s deadline inside pair 0's K9 — incomplete, judged incomplete;
  target_partial   an external interrupt at the SECOND target setup call of pair 0 — incomplete, the first setup observation kept, the task
                   `partial`, the pair `partial` (never not_started);
  target_invalid   a DOMAIN at the first target setup call — invalid (kind target_invalid), task_setup.json persisted before the call;
  source_drift     the second setup observation from another source identity — invalid (target_invalid), the first observation kept;
  tampered/…       the complete archive with (a) the target of task.json flipped and every digest refreshed, (b) a target-grid cell flipped with
                   the trace digest refreshed, (c) the planted genome of the plan changed, (d) the protocol identity removed from the manifest,
                   (e) one identity component changed, (f) the gate report's identity digest changed — the fresh-process verifiers must refuse
                   each (exit 1) and NAME it;
  old_archives     the committed v0.1.16 archives (b4-sim-3, b4-gate-1) read-only: the v0.2.0 verifiers, judge and policy refuse them BY NAME
                   with nothing written.

THE RECORD (the owner's proportionality ruling of 2026-10-20, rule 2): the fixture archives are NOT committed. For each case this script keeps
the exact command / call, the tool's status and exit code, every fresh-process verifier's stdout and exit, and a per-file digest list in TWO
forms — the raw sha256 of the bytes, and the CANONICAL sha256 of the JSON with the NON-DETERMINISTIC FIELDS removed, the rule stated here
before any comparison: the keys VOLATILE below (times, wall-clock durations, the hermetic root's HEAD and absolute path, the deadline record's
elapsed / checks, the quarantine's repr) are dropped at every depth; everything else — the seeds, the plans, the planted genomes, the traces,
the ledgers, the audits, the summaries, the verdicts, the identity — must reproduce bit for bit on the same tree. Nothing here is a result.
"""
import hashlib, json, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
sys.path[:0] = [str(R / "b4/host"), str(R / "b4/tests")]
import b4_execution as ex  # noqa: E402
import b4_gate as bg  # noqa: E402
import b4_gonogo as gg  # noqa: E402
import b4_protocol as bp  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim as sim  # noqa: E402
import b4_sim_verify as sv  # noqa: E402
from b4_test_fixtures import InjectingPort  # noqa: E402
from test_b4_sim import SCHED1, Clock, RaisingPort, build_hermetic, git, reindex  # noqa: E402

VOLATILE = {"written_utc", "generated_utc", "audited_utc", "stopped_utc", "wall_s", "head", "head_at_stop", "deadline", "code_root", "clean_tree", "raw_repr", "traceback",
            "reconstruction_utc", "reason"}   # `reason` of a stop record may quote the hermetic root's absolute path; the kind / stage / role are kept
TOOLS = {"sim": "b4/host/b4_sim_verify.py", "gate": "b4/host/b4_gate_verify.py", "gonogo": "b4/host/b4_gonogo.py"}


def guard(*a, **k):
    raise AssertionError("a production seed derivation was reached")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def strip(x):
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if k not in VOLATILE}
    if isinstance(x, list):
        return [strip(v) for v in x]
    return x


def digests(d: Path) -> dict:
    out = {}
    for p in sorted(d.rglob("*")):
        if not p.is_file():
            continue
        b = p.read_bytes()
        rec = {"sha256": sha(b), "size": len(b)}
        if p.suffix == ".json":
            try:
                rec["canonical_sha256"] = sha(json.dumps(strip(json.loads(b)), sort_keys=True, separators=(",", ":")).encode())
            except ValueError:
                rec["canonical_sha256"] = None
        out[str(p.relative_to(d))] = rec
    return out


def fresh(tool: str, target: Path, *extra) -> tuple[int, str]:
    cmd = [sys.executable, "-B", str(R / TOOLS[tool])] + (["verify"] if tool == "gonogo" else []) + [str(target)] + list(extra)
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, " ".join(cmd[2:]) + "\n" + p.stdout + p.stderr


def sched32() -> sim.FixtureSchedule:
    """Thirty-two distinct pairs of already-exposed values (section 9.2's fixture namespace); nothing derived."""
    import itertools
    v = sorted(bs.FIXTURE_VALUES)
    pairs = list(itertools.islice(itertools.combinations(v, 2), 32))         # the first 32 of the C(n, 2) distinct pairs, in value order
    return sim.FixtureSchedule("b4-mech-5", tuple(pairs))


def main() -> int:
    out = HERE / (sys.argv[1] if len(sys.argv) > 1 else "e2e")
    if out.exists():
        raise SystemExit(f"{out} exists: nothing is overwritten")
    out.mkdir(parents=True)
    head = subprocess.run(["git", "-C", str(R), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    ident = bp.identity()
    summary = {"head": head, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "protocol_sha256": bp.protocol_sha256(ident), "volatile_fields_dropped_from_canonical_digests": sorted(VOLATILE),
               "cases": {}, "tampered": {}, "old_archives": {}}
    bad = 0

    def keep(name: str, rec: dict, dirs: dict):
        case = out / name
        case.mkdir(parents=True, exist_ok=True)
        rec["digests"] = {k: digests(d) for k, d in dirs.items() if d is not None and Path(d).is_dir()}
        for k, (tool, d, *extra) in rec.pop("verify", {}).items():
            code, text = fresh(tool, d, *extra)
            rec[f"fresh_{k}_exit"] = code
            (case / f"verify_{k}.txt").write_text(f"HEAD {head}\nexit {code}\n\n{text}")
        (case / "record.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
        summary["cases" if name not in ("old_archives",) else "old_archives"][name] = {k: v for k, v in rec.items() if k != "digests"}
        print(name, {k: v for k, v in rec.items() if k.startswith("fresh_") or k in ("status", "exit_code", "verdict", "decision")}, flush=True)

    with mock.patch.object(bs, "master_seed", side_effect=guard) as g1, mock.patch.object(bs, "pair_seeds", side_effect=guard) as g2:
        with tempfile.TemporaryDirectory(prefix="b4v02_e2e_") as tmp:
            root = build_hermetic(Path(tmp))
            ns, gns, dns = root / sim.SIM_REL, root / bg.GATE_REL, root / gg.GONOGO_REL

            def commit():
                if git(root, "status", "--porcelain").strip():
                    git(root, "add", "-A"); git(root, "commit", "-q", "-m", "archive")
            # --- complete (gate mode, judged) + its go / no-go (no decision at S = 2)
            res = bg.run_gate(root, "b4-mech-1", 2, 3600, out_batch=ns / "b4-mech-1_complete", out_gate=gns / "b4-mech-1_complete", schedule=SCHED1)
            commit()
            doc = json.loads((Path(res["gate_out"]) / bg.REPORT_JSON).read_text())
            dec = gg.write_decision(root, Path(res["out"]), dns / "b4-mech-1_complete")
            commit()
            rec = {"call": "bg.run_gate(root, 'b4-mech-1', 2, 3600, schedule=SCHED1) then gg.write_decision(root, batch)", "status": res["status"], "exit_code": res["exit_code"],
                   "batch_status": res["batch"]["status"], "verdict": doc["verdict"]["status"], "formal": doc["formal"], "rows": {r["id"]: r["status"] for r in doc["rows"]},
                   "k9_row_value_keys": sorted(next(r for r in doc["rows"] if r["id"] == "K9")["value"]), "identity_protocol_sha256": doc["identity"]["protocol_sha256"],
                   "decision": dec["status"], "decision_exit": dec["exit_code"], "decision_reason": dec["report"]["reason"],
                   "verify": {"batch": ("sim", Path(res["out"])), "gate": ("gate", Path(res["gate_out"])), "gonogo": ("gonogo", Path(dec["gonogo_out"]))}}
            keep("complete", rec, {"batch": Path(res["out"]), "gate": Path(res["gate_out"]), "gonogo": Path(dec["gonogo_out"])})
            bad += (res["status"] != "FAIL") + (rec["fresh_batch_exit"] != 0) + (rec["fresh_gate_exit"] != 0) + (rec["fresh_gonogo_exit"] != 0) + (dec["status"] != "no_decision")
            complete_batch, complete_gate = Path(res["out"]), Path(res["gate_out"])
            # --- complete_32: the policy applied once on fixture data
            s32 = sched32()
            r32 = sim.run_batch(root, "b4-mech-5", 32, 7200, ns / "b4-mech-5_complete32", schedule=s32)
            commit()
            rec = {"call": "sim.run_batch(root, 'b4-mech-5', 32, 7200, schedule=<32 explicit pairs>) then gg.write_decision", "status": r32["status"], "exit_code": r32["exit_code"],
                   "reason": r32.get("reason") or (r32.get("stopped") or {}).get("detail"), "schedule": [list(p) for p in s32.pairs]}
            if r32["status"] == "complete":
                d32 = gg.write_decision(root, Path(r32["out"]), dns / "b4-mech-5_complete32")
                commit()
                rec.update(decision=d32["status"], decision_exit=d32["exit_code"], decision_reason=d32["report"]["reason"], formal=d32["report"]["formal"],
                           statistic_1=d32["report"]["statistic_1"], statistic_2=d32["report"]["statistic_2"],
                           verify={"batch": ("sim", Path(r32["out"])), "gonogo": ("gonogo", Path(d32["gonogo_out"]))})
                keep("complete_32", rec, {"batch": Path(r32["out"]), "gonogo": Path(d32["gonogo_out"])})
                bad += (rec["fresh_batch_exit"] != 0) + (rec["fresh_gonogo_exit"] != 0) + (d32["status"] not in ("go", "no-go")) + (d32["report"]["formal"] is not False)
            else:
                keep("complete_32", rec, {"batch": Path(r32["out"])}); bad += 1
            # --- invalid / incomplete (judged)
            def domain(fabric, role, pair):
                return InjectingPort(fabric, 30) if (pair, role) == (1, "O") else ex.ObservationPort(fabric)
            for name, kw in (("invalid", {"port_factory": domain}), ("incomplete", {"clock": Clock(step=1.0)})):
                res = bg.run_gate(root, "b4-mech-1", 2, 3600 if name == "invalid" else 60, out_batch=ns / f"b4-mech-1_{name}", out_gate=gns / f"b4-mech-1_{name}", schedule=SCHED1, **kw)
                commit()
                doc = json.loads((Path(res["gate_out"]) / bg.REPORT_JSON).read_text())
                rep = json.loads((Path(res["out"]) / "sim_report.json").read_text())
                rec = {"status": res["status"], "exit_code": res["exit_code"], "batch_status": rep["status"], "stopped_kind": rep["stopped"]["kind"], "stopped_stage": rep["stopped"]["stage"],
                       "verdict": doc["verdict"]["status"], "pairs": [{k: p[k] for k in ("status", "task", "k9")} for p in rep["pairs"]],
                       "verify": {"batch": ("sim", Path(res["out"])), "gate": ("gate", Path(res["gate_out"]))}}
                keep(name, rec, {"batch": Path(res["out"]), "gate": Path(res["gate_out"])})
                bad += (res["status"] != name) + (rec["fresh_batch_exit"] != 0) + (rec["fresh_gate_exit"] != 0)
            # --- the target setup: partial (an interrupt at the second call), invalid (a DOMAIN at the first), a source drift
            class Drifting(ex.ObservationPort):
                def observe(self, config, stimulus):
                    t = super().observe(config, stimulus)
                    if self.calls == 2:
                        t["fabric"] = dict(t["fabric"], kind="dropout")
                    return t
            for name, make, want in (("target_partial", lambda f: RaisingPort(f, 2, KeyboardInterrupt()), ("incomplete", "interrupted", "partial")),
                                     ("target_invalid", lambda f: InjectingPort(f, 1), ("invalid", "target_invalid", "invalid")),
                                     ("source_drift", lambda f: Drifting(f), ("invalid", "target_invalid", "invalid"))):
                def factory(fabric, role, pair, make=make):
                    return make(fabric) if (pair, role) == (0, sim.SETUP_ROLE) else ex.ObservationPort(fabric)
                res = sim.run_batch(root, "b4-mech-1", 2, 3600, ns / f"b4-mech-1_{name}", port_factory=factory, schedule=SCHED1)
                commit()
                rep = json.loads((Path(res["out"]) / "sim_report.json").read_text())
                files = sorted(p.name for p in (Path(res["out"]) / "pair_000").iterdir())
                rec = {"status": res["status"], "exit_code": res["exit_code"], "stopped_kind": rep["stopped"]["kind"], "stopped_stage": rep["stopped"]["stage"], "stopped_role": rep["stopped"]["role"],
                       "pair_000": {k: rep["pairs"][0][k] for k in ("status", "task")}, "pair_000_files": files, "verify": {"batch": ("sim", Path(res["out"]))}}
                keep(name, rec, {"batch": Path(res["out"])})
                bad += (res["status"] != want[0]) + (rep["stopped"]["kind"] != want[1]) + (rep["pairs"][0]["task"] != want[2]) + (rec["fresh_batch_exit"] != 0)
                bad += ("task_setup.json" not in files) + (("target_search.json" in files) != (name != "target_invalid")) + ("target_holdout.json" in files) + ("task.json" in files)
            # --- tampering with every digest refreshed: the fresh-process verifiers must refuse and name
            def tamper(name: str, mutate, tool: str, target: Path, needle: str):
                tdir = target.parent / (target.name + "_tamper_" + name)
                shutil.copytree(target, tdir)
                mutate(tdir)
                commit()
                code, text = fresh(tool, tdir)
                case = out / "tampered" / name
                case.mkdir(parents=True)
                (case / "verify.txt").write_text(f"HEAD {head}\nexpected: exit 1 naming {needle!r}\nexit {code}\n\n{text}")
                named = needle in text
                summary["tampered"][name] = {"expected_exit": 1, "fresh_verifier_exit": code, "named": named, "needle": needle}
                print("tampered", name, "exit", code, "named", named, flush=True)
                return (code != 1) + (not named)

            def flip_target(d: Path):
                t = json.loads((d / "pair_000/task.json").read_text()); t["public_task"]["target"][0] = 1 - t["public_task"]["target"][0]
                (d / "pair_000/task.json").write_bytes(sim.json_text(t)); reindex(d)

            def flip_grid(d: Path):
                t = json.loads((d / "pair_000/target_search.json").read_text()); t["q_grid"][2][1] = 1 - t["q_grid"][2][1]; t["trace_sha256"] = ex.sha256_json(t["q_grid"])
                (d / "pair_000/target_search.json").write_bytes(sim.json_text(t)); reindex(d)

            def change_plan(d: Path):
                t = json.loads((d / "pair_000/task_setup.json").read_text()); t["planted_genome"] ^= 1 << 2; t["planted_genome_hex"] = ex.genome_hex(t["planted_genome"], 21)
                (d / "pair_000/task_setup.json").write_bytes(sim.json_text(t)); reindex(d)

            def drop_identity(d: Path):
                m = json.loads((d / "manifest.json").read_text()); del m["protocol"]; (d / "manifest.json").write_bytes(sim.json_text(m)); reindex(d)

            def change_identity(d: Path):
                m = json.loads((d / "manifest.json").read_text()); m["protocol"]["identity"]["k9"]["judged"] = "all_panel"; (d / "manifest.json").write_bytes(sim.json_text(m)); reindex(d)

            def gate_identity(d: Path):
                g = json.loads((d / bg.REPORT_JSON).read_text()); g["identity"]["protocol_sha256"] = "0" * 64
                (d / bg.REPORT_MD).write_bytes(bg.render_md(g).encode("utf-8")); b = (d / bg.REPORT_MD).read_bytes()
                g["files"] = [{"path": bg.REPORT_MD, "sha256": sha(b), "size": len(b)}]; (d / bg.REPORT_JSON).write_bytes(sim.json_text(g))
            bad += tamper("task_target_flipped", flip_target, "sim", complete_batch, "task")
            bad += tamper("target_grid_cell_flipped", flip_grid, "sim", complete_batch, "rebuilt")
            bad += tamper("planted_genome_changed", change_plan, "sim", complete_batch, "not what the seed, the rule and the mapping give")
            bad += tamper("protocol_identity_removed", drop_identity, "sim", complete_batch, "no protocol identity")
            bad += tamper("protocol_identity_component_changed", change_identity, "sim", complete_batch, "k9: judged")
            bad += tamper("gate_identity_digest_changed", gate_identity, "gate", complete_gate, "not this tool's")
            # --- the committed v0.1.16 archives, read-only
            olds = {"b4-sim-3": R / "evidence/b4/sim/b4-sim-3_20261019T121833Z", "b4-gate-1": R / "evidence/b4/sim/b4-gate-1_20261020T102526Z"}
            gate1 = R / "evidence/b4/gate/b4-gate-1_20261020T102526Z"
            before = {k: sorted((p.name, sha(p.read_bytes())) for p in d.iterdir() if p.is_file()) for k, d in olds.items()}
            rec = {"verify": {}}
            for k, d in olds.items():
                code, text = fresh("sim", d, "--shallow")
                (out / "old_archives").mkdir(exist_ok=True)
                (out / "old_archives" / f"verify_{k}.txt").write_text(f"HEAD {head}\nexpected: exit 1, refused by name (no protocol identity)\nexit {code}\n\n{text}")
                j = bg.judge_batch(R, d); dd = gg.write_decision(R, d)
                rec[k] = {"fresh_verifier_exit": code, "named": "no protocol identity" in text, "judge": j["status"], "judge_reason": (j.get("reason") or "")[:200], "gonogo": dd["status"], "gonogo_reason": (dd.get("reason") or "")[:200]}
                bad += (code != 1) + (not rec[k]["named"]) + (j["status"] != "refused") + (dd["status"] != "refused") + (j.get("gate_out") is not None) + (dd.get("gonogo_out") is not None)
            code, text = fresh("gate", gate1, "--shallow")
            (out / "old_archives" / "verify_b4-gate-1_gate.txt").write_text(f"HEAD {head}\nexpected: exit 1, refused by name\nexit {code}\n\n{text}")
            rec["b4-gate-1_gate_dir"] = {"fresh_verifier_exit": code, "named": "not this tool's" in text or "protocol" in text}
            bad += (code != 1) + (not rec["b4-gate-1_gate_dir"]["named"])
            after = {k: sorted((p.name, sha(p.read_bytes())) for p in d.iterdir() if p.is_file()) for k, d in olds.items()}
            rec["untouched"] = before == after and not (R / gg.GONOGO_REL).exists()
            bad += (not rec["untouched"])
            summary["old_archives"] = rec
            print("old_archives", {k: v for k, v in rec.items() if k != "verify"}, flush=True)
        summary["production_derivation_calls"] = [g1.call_count, g2.call_count]
    summary["as_expected"] = bad == 0
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(json.dumps(summary["production_derivation_calls"]), "as expected:", summary["as_expected"], "bad:", bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
