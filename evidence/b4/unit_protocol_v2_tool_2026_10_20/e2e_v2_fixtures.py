#!/usr/bin/env python3
"""End-to-end fixtures of the protocol v0.2.0 tool unit, SECOND DRIVER (the correction round after the owner's HOLD on 04385ae, R1-R6).
The first driver (e2e_fixtures_v02.py, its record e2e/) is kept as it was: its "canonical digest" comparison dropped volatile keys but not
their DEPENDENCY CHAIN (a target file's raw digest sits in task.json, the pair index, the report, the gate and the go / no-go records; the
hermetic HEAD in the manifest and the registry snapshot), so the owner's regeneration reproduced 811 of 908 digests. This driver replaces
that comparison with an explicit NORMALISATION OF THE DEPENDENCY GRAPH and proves it both ways (a fresh-root, different-time repeat that
passes; a semantic tamper that fails and is localised), on a HERMETIC repository copy with b4_seeds.master_seed / pair_seeds guarded so
that NO PRODUCTION SET can be derived. Nothing here is a result.

THE NORMALISED DIGEST of a JSON file (`normalise`), stated before any comparison:
  1. the keys VOLATILE below are dropped at every depth (times, wall-clock durations, the deadline record, the quarantine's repr, the
     traceback, the hermetic root's `code_root` block, the tree-cleanliness flag, a stop's free-text `reason` / `detail` that may quote a
     path);
  2. every string equal to a commit hash of the HERMETIC repository is replaced by "<HEAD>", every occurrence of the hermetic root's
     absolute path by "<ROOT>";
  3. every string equal to the RAW sha256 of a file under the hermetic root's evidence/ is replaced by "norm:" + that file's NORMALISED
     digest — computed to a fixed point, so that a record which embeds another record's digest (task.json -> the target files; the pair
     index and the report -> every pair file; the gate and the go / no-go record -> the report, the seeds, the manifest; the registry
     snapshot -> earlier batches' seeds.json) compares through the normalised chain, never through the raw bytes;
  4. the `size` of a file index entry whose digest was substituted in step 3 is replaced by "<N>": a file that carries volatile fields
     (a wall-clock duration, a deadline sample) has a volatile LENGTH too; the raw size is validated against the live file by
     `validate_links` and by the fresh verifiers, not compared across runs;
  5. a non-JSON file (the markdown renderings gate_report.md / gonogo.md, which quote digests and times) is not compared across runs:
     its normalised digest is null and a reference to it substitutes the constant "norm:rendering" — the fresh verifier holds every
     rendering byte for byte to its JSON record, and the JSON record is what is compared;
  6. the canonical JSON (sorted keys, no spaces) of the result is hashed.
Everything that is not volatile — the seeds, the plans, the planted genomes, the grids, the ledgers, the audits, the summaries, the
verdicts, the identity components, the file sets — must reproduce bit for bit on the same tree in a fresh root at another time.
RAW LINKS are validated in the live hermetic root: every file index entry {path, sha256, size} of every record resolves to an existing
file with that raw digest and size (`validate_links`; the fresh-process verifiers check the same binding by their own rules).

Cases (every archive re-verified by its verifier CLI in a FRESH PROCESS; expectations asserted, `as_expected` only when all hold):
  complete, complete_32, invalid, incomplete            as in the first driver (gate mode / exploration mode, judged, decided);
  target_partial                                        an interrupt at the SECOND setup call: incomplete, prefix 2;
  interrupt_after_holdout                               the owner's R3 case: the interrupt right after target_holdout.json is durably written:
                                                        incomplete, task partial, prefix 3, both target files kept, verified clean;
  target_invalid                                        a DOMAIN at the first setup call: invalid, nothing returned, no quarantine, prefix 1;
  source_drift                                          the owner's R2 case 1: a VALID-SHAPED second return with another fabric digest and a
                                                        marker: invalid, the return kept in target_holdout.QUARANTINE.json (marker found),
                                                        prefix 2, quarantine recorded;
  return_malformed / return_init_none / return_bad_cell / return_nonserialisable
                                                        the owner's R2 case 2 and R4: a malformed first return (marker), a None in the unscored
                                                        init row, a cell of 2, a non-finite cell: each kept in target_search.QUARANTINE.json
                                                        (raw null + repr for the non-serialisable one), invalid, prefix 1;
  impossible_order                                      the owner's R3 forgery: target_search.json removed from an invalid archive, a valid
                                                        target_holdout.json put in, every hash refreshed: the fresh verifier REFUSES by name;
  gonogo_contract                                       the owner's R5 probes on a clean decision, MD and hashes refreshed: count 1.0, fixture 1,
                                                        path ../escaped_batch (an identical archive outside the root), an extra subdirectory:
                                                        each refused by the fresh verifier by name;
  identity_revision                                     the owner's R1 probe in fresh interpreters on a copy of the tool files: the revision file
                                                        changed and its table entry refreshed -> the same protocol_sha256, the new revision; a
                                                        threshold number changed -> refused unrefreshed, another digest refreshed;
  tampered/…                                            the six tampers of the first driver, each refused and named;
  old_archives                                          the committed v0.1.16 archives refused by name, untouched;
  semantic_tamper                                       the proof that the normalised comparison FAILS on a semantic change: the complete archive
                                                        copied, one target-grid cell flipped with every chain digest refreshed: exactly the file
                                                        and its dependents differ, every other file is equal.
"""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
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
import b4_target as bt  # noqa: E402
import b4_thresholds as th  # noqa: E402
from b4_test_fixtures import InjectingPort  # noqa: E402
from test_b4_sim import SCHED1, Clock, RaisingPort, build_hermetic, entry, git, reindex  # noqa: E402

VOLATILE = {"written_utc", "generated_utc", "audited_utc", "stopped_utc", "reconstruction_utc", "wall_s", "deadline", "raw_repr", "traceback", "code_root", "clean_tree", "reason", "detail"}
TOOLS = {"sim": "b4/host/b4_sim_verify.py", "gate": "b4/host/b4_gate_verify.py", "gonogo": "b4/host/b4_gonogo.py"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def guard(*a, **k):
    raise AssertionError("a production seed derivation was reached")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ the normalisation of the dependency graph
def normalise(root: Path, heads: set, compare_dirs: dict) -> dict:
    """{dir name: {rel: {"sha256": raw, "size": n, "normalised_sha256": ...}}} for the compared directories; the raw map and the fixed point are
    computed over EVERY file under root/evidence so that cross-archive references (registry snapshots, the gate's and the decision's batch
    digests) resolve. Returns also the pass count and the number of substituted references."""
    root_s = str(root)
    allfiles: dict[str, bytes] = {}
    for p in sorted((root / "evidence").rglob("*")):
        if p.is_file():
            allfiles[str(p.relative_to(root))] = p.read_bytes()
    raw = {sha(b): rel for rel, b in allfiles.items()}
    varsize = {s for s, rel in raw.items() if root_s.encode() in allfiles[rel]}
    parsed = {}
    for s_, rel in raw.items():
        try:
            parsed[s_] = json.loads(allfiles[rel])
        except ValueError:
            parsed[s_] = None
    norm: dict[str, str] = {}
    subs = [0]

    def subst(x):
        if isinstance(x, dict):
            d = {k: subst(v) for k, v in x.items() if k not in VOLATILE}
            if set(x) >= {"path", "sha256", "size"} and (x.get("sha256") in norm or x.get("sha256") in varsize):
                d["size"] = "<N>"
            return d
        if isinstance(x, list):
            return [subst(v) for v in x]
        if isinstance(x, str):
            if x in norm:
                subs[0] += 1; return "norm:" + norm[x]
            if x in heads:
                return "<HEAD>"
            if root_s in x:
                return x.replace(root_s, "<ROOT>")
        return x

    def one(s_: str) -> str:
        doc = parsed[s_]
        if doc is None:
            return "rendering"                                   # a markdown rendering: held to its JSON by the verifier, not compared across runs
        return sha(json.dumps(subst(doc), sort_keys=True, separators=(",", ":")).encode())
    passes = 0
    while True:                     # the chain's depth is the number of archives in the root (every seeds.json cites every earlier one through the registry): bounded, linear
        passes += 1
        subs[0] = 0
        new = {s_: one(s_) for s_ in raw}
        if new == norm:
            break
        norm = new
        if passes > 500:
            raise RuntimeError("the normalisation did not reach a fixed point")
    out = {}
    for dname, d in compare_dirs.items():
        d = Path(d)
        out[dname] = {str(p.relative_to(d)): {"sha256": sha(p.read_bytes()), "size": len(p.read_bytes()), "normalised_sha256": (None if norm[sha(p.read_bytes())] == "rendering" else norm[sha(p.read_bytes())])}
                      for p in sorted(d.rglob("*")) if p.is_file()}
    return {"digests": out, "fixed_point_passes": passes, "substituted_references": subs[0], "files_in_raw_map": len(raw)}


def validate_links(root: Path, dirs: dict) -> dict:
    """Every file index entry {path, sha256, size} in every JSON of the directories resolves to an existing file with that raw digest and
    size — tried against the record's own directory, the archive directory and the root (the conventions of the pair index, the report,
    the gate and the decision records)."""
    ok, unresolved = 0, []

    def walk(x, where: Path, archive: Path, rel: str):
        nonlocal ok
        if isinstance(x, dict):
            if set(x) >= {"path", "sha256", "size"} and isinstance(x.get("path"), str) and isinstance(x.get("sha256"), str):
                found = False
                for cand in (where / x["path"], archive / x["path"], root / x["path"], root / x["path"] / "sim_report.json"):
                    if cand.is_file():
                        b = cand.read_bytes()
                        if sha(b) == x["sha256"] and (len(b) == x["size"] or x["path"].endswith("/")):
                            found = True; break
                if found:
                    ok += 1
                else:
                    unresolved.append(f"{rel}: {x['path']}")
            for v in x.values():
                walk(v, where, archive, rel)
        elif isinstance(x, list):
            for v in x:
                walk(v, where, archive, rel)
    for dname, d in dirs.items():
        d = Path(d)
        for p in sorted(d.rglob("*.json")):
            try:
                doc = json.loads(p.read_bytes())
            except ValueError:
                continue
            walk(doc, p.parent, d, f"{dname}/{p.relative_to(d)}")
    return {"resolved": ok, "unresolved": unresolved}


def fresh(tool: str, target: Path, *extra) -> tuple:
    cmd = [sys.executable, "-B", str(R / TOOLS[tool])] + (["verify"] if tool == "gonogo" else []) + [str(target)] + list(extra)
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, " ".join(cmd[2:]) + "\n" + p.stdout + p.stderr


def sched32() -> sim.FixtureSchedule:
    import itertools
    v = sorted(bs.FIXTURE_VALUES)
    return sim.FixtureSchedule("b4-mech-5", tuple(itertools.islice(itertools.combinations(v, 2), 32)))


def refresh_report(out: Path) -> None:
    """Every digest of a stopped archive (no pair index): the report's file index and identity."""
    rep = json.loads((out / "sim_report.json").read_text())
    rep["files"] = [entry(p, str(p.relative_to(out))) for p in sorted(out.rglob("*")) if p.is_file() and p.name != "sim_report.json"]
    rep["identity"]["seeds_sha256"] = sim.sha_file(out / "seeds.json"); rep["identity"]["manifest_sha256"] = sim.sha_file(out / "manifest.json")
    (out / "sim_report.json").write_text(json.dumps(rep, sort_keys=True, indent=1) + "\n")


def main() -> int:
    out = HERE / (sys.argv[1] if len(sys.argv) > 1 else "e2e_v2")
    if out.exists():
        raise SystemExit(f"{out} exists: nothing is overwritten")
    out.mkdir(parents=True)
    head = subprocess.run(["git", "-C", str(R), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    ident = bp.identity()
    summary = {"head": head, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "protocol_sha256": bp.protocol_sha256(ident), "architecture_revision": ident["architecture_revision"],
               "normalisation": {"volatile_keys_dropped": sorted(VOLATILE), "rule": "see the module docstring: volatile keys dropped, <HEAD> / <ROOT> symbols, embedded raw digests replaced by the referenced file's normalised digest to a fixed point, variable sizes marked"},
               "cases": {}, "tampered": {}, "old_archives": {}, "semantic_tamper": {}, "identity_revision": {}}
    bad = 0
    pending: dict = {}

    def keep(name: str, rec: dict, dirs: dict):
        case = out / name
        case.mkdir(parents=True, exist_ok=True)
        for k, (tool, d, *extra) in rec.pop("verify", {}).items():
            code, text = fresh(tool, d, *extra)
            rec[f"fresh_{k}_exit"] = code
            (case / f"verify_{k}.txt").write_text(f"HEAD {head}\nexit {code}\n\n{text}")
        pending[name] = (rec, {k: Path(d) for k, d in dirs.items() if d is not None and Path(d).is_dir()})
        print(name, {k: v for k, v in rec.items() if k.startswith("fresh_") or k in ("status", "exit_code", "verdict", "decision", "stopped_kind")}, flush=True)

    with mock.patch.object(bs, "master_seed", side_effect=guard) as g1, mock.patch.object(bs, "pair_seeds", side_effect=guard) as g2:
        with tempfile.TemporaryDirectory(prefix="b4v02_e2e_") as tmp:
            root = build_hermetic(Path(tmp))
            ns, gns, dns = root / sim.SIM_REL, root / bg.GATE_REL, root / gg.GONOGO_REL

            def commit():
                if git(root, "status", "--porcelain").strip():
                    git(root, "add", "-A"); git(root, "commit", "-q", "-m", "archive")

            def pair0(res):
                rep = json.loads((Path(res["out"]) / "sim_report.json").read_text())
                p = rep["pairs"][0]
                return rep, {k: p[k] for k in ("status", "task", "task_prefix", "task_quarantine")}, sorted(q.name for q in (Path(res["out"]) / "pair_000").iterdir())
            # --- complete (gate mode, judged) + its go / no-go (no decision at S = 2)
            res = bg.run_gate(root, "b4-mech-1", 2, 3600, out_batch=ns / "b4-mech-1_complete", out_gate=gns / "b4-mech-1_complete", schedule=SCHED1)
            commit()
            doc = json.loads((Path(res["gate_out"]) / bg.REPORT_JSON).read_text())
            dec = gg.write_decision(root, Path(res["out"]), dns / "b4-mech-1_complete")
            commit()
            rec = {"call": "bg.run_gate(root, 'b4-mech-1', 2, 3600, schedule=SCHED1) then gg.write_decision(root, batch)", "status": res["status"], "exit_code": res["exit_code"],
                   "batch_status": res["batch"]["status"], "verdict": doc["verdict"]["status"], "formal": doc["formal"], "rows": {r["id"]: r["status"] for r in doc["rows"]},
                   "identity_protocol_sha256": doc["identity"]["protocol_sha256"], "decision": dec["status"], "decision_exit": dec["exit_code"], "decision_reason": dec["report"]["reason"],
                   "verify": {"batch": ("sim", Path(res["out"])), "gate": ("gate", Path(res["gate_out"])), "gonogo": ("gonogo", Path(dec["gonogo_out"]))}}
            keep("complete", rec, {"batch": Path(res["out"]), "gate": Path(res["gate_out"]), "gonogo": Path(dec["gonogo_out"])})
            bad += (res["status"] != "FAIL") + (rec["fresh_batch_exit"] != 0) + (rec["fresh_gate_exit"] != 0) + (rec["fresh_gonogo_exit"] != 0) + (dec["status"] != "no_decision")
            complete_batch, complete_gate, complete_dec = Path(res["out"]), Path(res["gate_out"]), Path(dec["gonogo_out"])
            # --- complete_32
            s32 = sched32()
            r32 = sim.run_batch(root, "b4-mech-5", 32, 7200, ns / "b4-mech-5_complete32", schedule=s32)
            commit()
            rec = {"call": "sim.run_batch(root, 'b4-mech-5', 32, 7200, schedule=<32 explicit pairs>) then gg.write_decision", "status": r32["status"], "exit_code": r32["exit_code"], "schedule": [list(p) for p in s32.pairs]}
            if r32["status"] == "complete":
                d32 = gg.write_decision(root, Path(r32["out"]), dns / "b4-mech-5_complete32")
                commit()
                rec.update(decision=d32["status"], decision_exit=d32["exit_code"], decision_reason=d32["report"]["reason"], formal=d32["report"]["formal"],
                           statistic_1=d32["report"]["statistic_1"], statistic_2=d32["report"]["statistic_2"], verify={"batch": ("sim", Path(r32["out"])), "gonogo": ("gonogo", Path(d32["gonogo_out"]))})
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
                       "verdict": doc["verdict"]["status"], "pairs": [{k: p[k] for k in ("status", "task", "task_prefix", "k9")} for p in rep["pairs"]],
                       "verify": {"batch": ("sim", Path(res["out"])), "gate": ("gate", Path(res["gate_out"]))}}
                keep(name, rec, {"batch": Path(res["out"]), "gate": Path(res["gate_out"])})
                bad += (res["status"] != name) + (rec["fresh_batch_exit"] != 0) + (rec["fresh_gate_exit"] != 0)
            # --- the target setup: partial / the interrupt after the holdout write / invalid (a DOMAIN) / the returns kept in quarantine
            class Alter(ex.ObservationPort):
                def __init__(self, fabric, kind):
                    super().__init__(fabric); self.kind = kind

                def observe(self, config, stimulus):
                    t = super().observe(config, stimulus)
                    if self.kind == "drift" and self.calls == 2:
                        t["fabric"] = dict(t["fabric"], effect_sha256="a" * 64); t["owner_raw_marker"] = "returned_target_with_drift"
                    if self.kind == "malformed" and self.calls == 1:
                        t["steps"][0] = {"owner_raw_marker": "returned_malformed_target"}
                    if self.kind == "init_none" and self.calls == 1:
                        t["steps"][0]["q_after"][0] = None
                    if self.kind == "bad_cell" and self.calls == 1:
                        t["steps"][2]["q_after"][5] = 2
                    if self.kind == "nan" and self.calls == 1:
                        t["steps"][1]["q_after"][1] = float("nan")
                    return t
            original_write = sim.Batch.write

            def interrupt_after_holdout(self_, rel, doc, validator):
                e = original_write(self_, rel, doc, validator)
                if rel.endswith("/target_holdout.json"):
                    raise KeyboardInterrupt()
                return e
            setup_cases = [
                ("target_partial", lambda f: RaisingPort(f, 2, KeyboardInterrupt()), None, ("incomplete", "interrupted", "partial", 2, None), ["task_setup.json", "target_search.json"], None),
                ("interrupt_after_holdout", None, interrupt_after_holdout, ("incomplete", "interrupted", "partial", 3, None), ["task_setup.json", "target_holdout.json", "target_search.json"], None),
                ("target_invalid", lambda f: InjectingPort(f, 1), None, ("invalid", "target_invalid", "invalid", 1, None), ["task_setup.json"], None),
                ("source_drift", lambda f: Alter(f, "drift"), None, ("invalid", "target_invalid", "invalid", 2, "target_holdout"), ["target_holdout.QUARANTINE.json", "target_search.json", "task_setup.json"], "returned_target_with_drift"),
                ("return_malformed", lambda f: Alter(f, "malformed"), None, ("invalid", "target_invalid", "invalid", 1, "target"), ["target_search.QUARANTINE.json", "task_setup.json"], "returned_malformed_target"),
                ("return_init_none", lambda f: Alter(f, "init_none"), None, ("invalid", "target_invalid", "invalid", 1, "target"), ["target_search.QUARANTINE.json", "task_setup.json"], "element 0: None"),
                ("return_bad_cell", lambda f: Alter(f, "bad_cell"), None, ("invalid", "target_invalid", "invalid", 1, "target"), ["target_search.QUARANTINE.json", "task_setup.json"], "2 is not 0 / 1"),
                ("return_nonserialisable", lambda f: Alter(f, "nan"), None, ("invalid", "target_invalid", "invalid", 1, "target"), ["target_search.QUARANTINE.json", "task_setup.json"], "nan"),
            ]
            drift_out = None
            for name, make, write_patch, want, want_files, marker in setup_cases:
                def factory(fabric, role, pair, make=make):
                    return make(fabric) if (pair, role) == (0, sim.SETUP_ROLE) and make else ex.ObservationPort(fabric)
                with (mock.patch.object(sim.Batch, "write", write_patch) if write_patch else mock.patch.object(sim.Batch, "write", original_write)):
                    res = sim.run_batch(root, "b4-mech-1", 2, 3600, ns / f"b4-mech-1_{name}", port_factory=factory, schedule=SCHED1)
                commit()
                rep, p0, files = pair0(res)
                rec = {"status": res["status"], "exit_code": res["exit_code"], "stopped_kind": rep["stopped"]["kind"], "stopped_stage": rep["stopped"]["stage"], "stopped_role": rep["stopped"]["role"],
                       "pair_000": p0, "pair_000_files": files, "expected": {"status": want[0], "kind": want[1], "task": want[2], "prefix": want[3], "quarantine": want[4], "files": sorted(want_files)},
                       "verify": {"batch": ("sim", Path(res["out"]))}}
                if p0["task_quarantine"]:
                    q = json.loads((Path(res["out"]) / "pair_000" / ("target_search" if p0["task_quarantine"] == "target" else "target_holdout")).with_suffix(".QUARANTINE.json").read_text())
                    rec["quarantine"] = {"findings": q["findings"], "raw_is_null": q["raw"] is None, "context": q["context"], "marker_found": marker in json.dumps(q) if marker else None}
                    bad += (marker is not None and marker not in json.dumps(q))
                keep(name, rec, {"batch": Path(res["out"])})
                bad += (res["status"] != want[0]) + (rep["stopped"]["kind"] != want[1]) + ((p0["task"], p0["task_prefix"], p0["task_quarantine"]) != want[2:]) + (files != sorted(want_files)) + (rec["fresh_batch_exit"] != 0)
                if name == "source_drift":
                    drift_out = Path(res["out"])
            # --- the owner's R3 forgery: a later setup file without its prerequisite, every digest refreshed: refused by name
            forged = ns / "b4-mech-1_impossible_order"; shutil.copytree(drift_out, forged)
            (forged / "pair_000/target_search.json").unlink(); shutil.copy(complete_batch / "pair_000/target_holdout.json", forged / "pair_000/target_holdout.json"); refresh_report(forged); commit()
            code, text = fresh("sim", forged)
            named = "required by pair 0's recorded state" in text and "not a file any pair's recorded state accounts for" in text
            (out / "impossible_order").mkdir(); (out / "impossible_order/verify.txt").write_text(f"HEAD {head}\nexpected: exit 1 naming the missing prefix file and the unaccounted later file\nexit {code}\n\n{text}")
            summary["cases"]["impossible_order"] = {"fresh_verifier_exit": code, "named": named}; bad += (code != 1) + (not named)
            print("impossible_order", summary["cases"]["impossible_order"], flush=True)
            # --- the owner's R5 probes on a clean decision, MD and hashes refreshed
            cdir = dns / "b4-mech-1_contract"; cres = gg.write_decision(root, complete_batch, cdir); commit()
            original = (cdir / gg.DECISION_JSON).read_bytes()
            with tempfile.TemporaryDirectory(prefix="b4escaped_") as outside:
                shutil.copytree(complete_batch, Path(outside) / "escaped_batch")
                probes = {}
                for name, field, value, needle in (("float_count", "count", 1.0, "exact types"), ("integer_fixture", "fixture", 1, "exact types"), ("outside_root_path", "path", "../escaped_batch", "batch.path")):
                    d = json.loads(original); d["batch"][field] = value
                    md = gg.render_md(d).encode(); (cdir / gg.DECISION_MD).write_bytes(md); d["files"] = [{"path": gg.DECISION_MD, "sha256": sha(md), "size": len(md)}]
                    (cdir / gg.DECISION_JSON).write_bytes(sim.json_text(d))
                    code, text = fresh("gonogo", cdir, "--shallow")
                    probes[name] = {"fresh_verifier_exit": code, "named": needle in text}; bad += (code != 1) + (needle not in text)
                    (out / "gonogo_contract").mkdir(exist_ok=True); (out / f"gonogo_contract/verify_{name}.txt").write_text(f"HEAD {head}\nexpected: exit 1 naming {needle!r}\nexit {code}\n\n{text}")
                (cdir / gg.DECISION_JSON).write_bytes(original); (cdir / gg.DECISION_MD).write_bytes(gg.render_md(json.loads(original)).encode())
                (cdir / "sub").mkdir(); code, text = fresh("gonogo", cdir, "--shallow"); (cdir / "sub").rmdir()
                probes["extra_subdirectory"] = {"fresh_verifier_exit": code, "named": "no subdirectory" in text}; bad += (code != 1) + ("no subdirectory" not in text)
                (out / "gonogo_contract/verify_extra_subdirectory.txt").write_text(f"HEAD {head}\nexpected: exit 1 naming 'no subdirectory'\nexit {code}\n\n{text}")
                code, text = fresh("gonogo", cdir, "--shallow"); probes["restored"] = {"fresh_verifier_exit": code}; bad += (code != 0)
            summary["cases"]["gonogo_contract"] = probes; print("gonogo_contract", probes, flush=True)
            # --- the six tampers of the first driver
            def tamper(name: str, mutate, tool: str, target: Path, needle: str):
                tdir = target.parent / (target.name + "_tamper_" + name)
                shutil.copytree(target, tdir); mutate(tdir); commit()
                code, text = fresh(tool, tdir)
                case = out / "tampered" / name; case.mkdir(parents=True)
                (case / "verify.txt").write_text(f"HEAD {head}\nexpected: exit 1 naming {needle!r}\nexit {code}\n\n{text}")
                summary["tampered"][name] = {"expected_exit": 1, "fresh_verifier_exit": code, "named": needle in text, "needle": needle}
                print("tampered", name, "exit", code, "named", needle in text, flush=True)
                return (code != 1) + (needle not in text)

            def flip_target(d):
                t = json.loads((d / "pair_000/task.json").read_text()); t["public_task"]["target"][0] = 1 - t["public_task"]["target"][0]; (d / "pair_000/task.json").write_bytes(sim.json_text(t)); reindex(d)

            def flip_grid(d):
                t = json.loads((d / "pair_000/target_search.json").read_text()); t["q_grid"][2][1] = 1 - t["q_grid"][2][1]; t["trace_sha256"] = ex.sha256_json(t["q_grid"]); (d / "pair_000/target_search.json").write_bytes(sim.json_text(t)); reindex(d)

            def change_plan(d):
                t = json.loads((d / "pair_000/task_setup.json").read_text()); t["planted_genome"] ^= 1 << 2; t["planted_genome_hex"] = ex.genome_hex(t["planted_genome"], 21); (d / "pair_000/task_setup.json").write_bytes(sim.json_text(t)); reindex(d)

            def drop_identity(d):
                m = json.loads((d / "manifest.json").read_text()); del m["protocol"]; (d / "manifest.json").write_bytes(sim.json_text(m)); reindex(d)

            def change_identity(d):
                m = json.loads((d / "manifest.json").read_text()); m["protocol"]["identity"]["k9"]["judged"] = "all_panel"; (d / "manifest.json").write_bytes(sim.json_text(m)); reindex(d)

            def gate_identity(d):
                g = json.loads((d / bg.REPORT_JSON).read_text()); g["identity"]["protocol_sha256"] = "0" * 64
                (d / bg.REPORT_MD).write_bytes(bg.render_md(g).encode("utf-8")); b = (d / bg.REPORT_MD).read_bytes()
                g["files"] = [{"path": bg.REPORT_MD, "sha256": sha(b), "size": len(b)}]; (d / bg.REPORT_JSON).write_bytes(sim.json_text(g))
            bad += tamper("task_target_flipped", flip_target, "sim", complete_batch, "task")
            bad += tamper("target_grid_cell_flipped", flip_grid, "sim", complete_batch, "rebuilt")
            bad += tamper("planted_genome_changed", change_plan, "sim", complete_batch, "not what the seed, the rule and the mapping give")
            bad += tamper("protocol_identity_removed", drop_identity, "sim", complete_batch, "no protocol identity")
            bad += tamper("protocol_identity_component_changed", change_identity, "sim", complete_batch, "k9: judged")
            bad += tamper("gate_identity_digest_changed", gate_identity, "gate", complete_gate, "not this tool's")
            # --- the semantic tamper for the NORMALISED comparison: one grid cell flipped, every chain digest refreshed
            def flip_grid_chain(d):          # the semantic change with its WHOLE chain refreshed: the task's binding to the target file, the pair index, the report index
                t = json.loads((d / "pair_000/target_search.json").read_text()); t["q_grid"][2][1] = 1 - t["q_grid"][2][1]; t["trace_sha256"] = ex.sha256_json(t["q_grid"])
                (d / "pair_000/target_search.json").write_bytes(sim.json_text(t))
                k = json.loads((d / "pair_000/task.json").read_text()); k["setup_files_sha256"]["target_search.json"] = sim.sha_file(d / "pair_000/target_search.json")
                (d / "pair_000/task.json").write_bytes(sim.json_text(k)); reindex(d)
            sdir = ns / "b4-mech-1_complete_semantic"; shutil.copytree(complete_batch, sdir); flip_grid_chain(sdir); commit()
            # --- the committed v0.1.16 archives, read-only
            olds = {"b4-sim-3": R / "evidence/b4/sim/b4-sim-3_20261019T121833Z", "b4-gate-1": R / "evidence/b4/sim/b4-gate-1_20261020T102526Z"}
            gate1 = R / "evidence/b4/gate/b4-gate-1_20261020T102526Z"
            before = {k: sorted((p.name, sha(p.read_bytes())) for p in d.iterdir() if p.is_file()) for k, d in olds.items()}
            orec = {}
            (out / "old_archives").mkdir()
            for k, d in olds.items():
                code, text = fresh("sim", d, "--shallow")
                (out / "old_archives" / f"verify_{k}.txt").write_text(f"HEAD {head}\nexpected: exit 1, refused by name (no protocol identity)\nexit {code}\n\n{text}")
                j = bg.judge_batch(R, d); dd = gg.write_decision(R, d)
                orec[k] = {"fresh_verifier_exit": code, "named": "no protocol identity" in text, "judge": j["status"], "judge_reason": (j.get("reason") or "")[:200], "gonogo": dd["status"], "gonogo_reason": (dd.get("reason") or "")[:200]}
                bad += (code != 1) + (not orec[k]["named"]) + (j["status"] != "refused") + (dd["status"] != "refused") + (j.get("gate_out") is not None) + (dd.get("gonogo_out") is not None)
            code, text = fresh("gate", gate1, "--shallow")
            (out / "old_archives" / "verify_b4-gate-1_gate.txt").write_text(f"HEAD {head}\nexpected: exit 1, refused by name\nexit {code}\n\n{text}")
            orec["b4-gate-1_gate_dir"] = {"fresh_verifier_exit": code, "named": "not this tool's" in text or "protocol" in text}; bad += (code != 1) + (not orec["b4-gate-1_gate_dir"]["named"])
            after = {k: sorted((p.name, sha(p.read_bytes())) for p in d.iterdir() if p.is_file()) for k, d in olds.items()}
            orec["untouched"] = before == after and not (R / gg.GONOGO_REL).exists(); bad += (not orec["untouched"])
            summary["old_archives"] = orec; print("old_archives", orec, flush=True)
            # --- the owner's R1 probe, fresh interpreters on a copy of the tool files
            with tempfile.TemporaryDirectory(prefix="b4ident_") as itmp:
                iroot = Path(itmp)
                for rel in ("b4/host", "b4/schemas"):
                    shutil.copytree(R / rel, iroot / rel, ignore=shutil.ignore_patterns("__pycache__"))
                for rel in ("b4/IMPORT.json", th.ARCHITECTURE_REVISION_REL):
                    shutil.copy(R / rel, iroot / rel)

                def icli():
                    p = subprocess.run([sys.executable, "-B", str(iroot / "b4/host/b4_protocol.py")], capture_output=True, text=True)
                    return p.returncode, (json.loads(p.stdout) if p.returncode == 0 else (p.stdout + p.stderr)[-400:])

                def irefresh(rel):
                    t = json.loads((iroot / "b4/IMPORT.json").read_text()); t["files"][rel]["sha256"] = sha((iroot / rel).read_bytes()); (iroot / "b4/IMPORT.json").write_text(json.dumps(t))
                c0, a = icli()
                f = iroot / th.ARCHITECTURE_REVISION_REL; d = json.loads(f.read_text()); d["revision"] = "v0.2.1"; f.write_text(json.dumps(d, indent=1) + "\n"); irefresh(th.ARCHITECTURE_REVISION_REL)
                c1, b = icli()
                tf = iroot / "b4/host/b4_thresholds.py"; tf.write_text(tf.read_text().replace('"median_coverage_per_semantic_min": 0.50', '"median_coverage_per_semantic_min": 0.51'))
                c2, c = icli(); irefresh("b4/host/b4_thresholds.py"); c3, e = icli()
                irec = {"before": {"exit": c0, "protocol_sha256": a.get("protocol_sha256") if isinstance(a, dict) else a, "architecture_revision": a.get("architecture_revision") if isinstance(a, dict) else None},
                        "revision_file_changed_entry_refreshed": {"exit": c1, "protocol_sha256": b.get("protocol_sha256") if isinstance(b, dict) else b, "architecture_revision": b.get("architecture_revision") if isinstance(b, dict) else None},
                        "threshold_changed_unrefreshed": {"exit": c2, "refused_by_name": isinstance(c, str) and "not its inventory" in c},
                        "threshold_changed_refreshed": {"exit": c3, "protocol_sha256": e.get("protocol_sha256") if isinstance(e, dict) else e}}
                irec["method_unchanged_by_the_revision"] = c0 == c1 == 0 and a["protocol_sha256"] == b["protocol_sha256"] and b["architecture_revision"] == "v0.2.1"
                irec["method_changed_by_the_number"] = c3 == 0 and isinstance(e, dict) and e["protocol_sha256"] != a["protocol_sha256"]
                bad += (not irec["method_unchanged_by_the_revision"]) + (not irec["threshold_changed_unrefreshed"]["refused_by_name"]) + (not irec["method_changed_by_the_number"])
                summary["identity_revision"] = irec; print("identity_revision", {k: v for k, v in irec.items() if k.startswith("method") or k == "threshold_changed_unrefreshed"}, flush=True)
            # --- the normalised digests of every kept case, the raw links, the semantic tamper proof — all on the live hermetic root
            heads = set(git(root, "rev-list", "--all").split())
            for name, (rec, dirs) in pending.items():
                n = normalise(root, heads, dirs)
                links = validate_links(root, dirs)
                rec["digests"] = n["digests"]; rec["normalisation"] = {k: v for k, v in n.items() if k != "digests"}; rec["raw_links"] = links
                bad += bool(links["unresolved"])
                (out / name / "record.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
                summary["cases"][name] = {k: v for k, v in rec.items() if k not in ("digests", "schedule")}
            n_orig = normalise(root, heads, {"batch": complete_batch})["digests"]["batch"]
            n_sem = normalise(root, heads, {"batch": sdir})["digests"]["batch"]
            differ = sorted(k for k in n_orig if k in n_sem and n_orig[k]["normalised_sha256"] != n_sem[k]["normalised_sha256"])
            equal = sorted(k for k in n_orig if k in n_sem and n_orig[k]["normalised_sha256"] == n_sem[k]["normalised_sha256"])
            expected = ["pair_000/index.json", "pair_000/target_search.json", "pair_000/task.json", "sim_report.json"]
            summary["semantic_tamper"] = {"mutation": "pair_000/target_search.json q_grid[2][1] flipped, trace_sha256 refreshed, task.json's setup_files_sha256 binding refreshed, the pair index and the report's file index refreshed (reindex)",
                                          "differ": differ, "expected_to_differ": expected, "equal_count": len(equal), "localised": differ == expected and set(n_orig) == set(n_sem)}
            (out / "semantic_tamper").mkdir(); (out / "semantic_tamper/record.json").write_text(json.dumps({"original": n_orig, "tampered": n_sem, **summary["semantic_tamper"]}, indent=1, sort_keys=True) + "\n")
            bad += (not summary["semantic_tamper"]["localised"])
            print("semantic_tamper", {k: v for k, v in summary["semantic_tamper"].items() if k != "mutation"}, flush=True)
        summary["production_derivation_calls"] = [g1.call_count, g2.call_count]
    summary["as_expected"] = bad == 0
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(json.dumps(summary["production_derivation_calls"]), "as expected:", summary["as_expected"], "bad:", bad)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
