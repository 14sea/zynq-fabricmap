#!/usr/bin/env python3
"""B4 — the INDEPENDENT VERIFIER of a gate directory (unit 2b-4; the owner's ruling of 2026-10-19, section 3: "acceptance
starts with end-to-end archives and a fresh-process independent verifier ... it must not confuse clean evidence with a passing
scientific criterion").

    python3 b4/host/b4_gate_verify.py evidence/b4/gate/<label>_<UTC>     # prints the findings as JSON; exit 0 iff none

For a gate directory it checks, and names every difference:
  1. the directory lies at evidence/b4/gate/<label>_… under a root and holds exactly gate_report.json, gate_report.md (and
     synthetic_summary.json when that is the evidence) — no .part, no error file, nothing else;
  2. gate_report.json against its typed validator (`b4_gate.gate_report_findings`);
  3. the evidence binding: a batch archive directly under evidence/b4/sim/ of the same root whose sim_report.json, seeds.json and
     manifest.json hash to the recorded digests and whose identity (label, count, fixture, status, HEAD, time) is the recorded one
     — or the synthetic summary file in the gate directory, hashed and validated;
  4. (deep) the batch archive re-verified archive-wide by `b4_sim_verify.verify_run_dir` (re-execution of every arm on the formal
     model, the diagnostics recomputed, the pooled summary recomputed) — findings under "batch: …";
  5. the judgement recomputed from the evidence by `b4_gate.judge` and held to the report row by row: the budget rule, the ten
     rows, the formal flag and its reasons, the contract findings, the verdict, the standing, the diagnostics;
  6. gate_report.md re-rendered from gate_report.json and compared byte for byte; the file index's digests.

A gate report that recorded self-validation findings of its own never verifies clean: it said itself that its judgement did not
stand. A clean verification of a FAIL report means the FAIL follows from the evidence; a clean verification of a fixture or
synthetic report means the tool applied the rows as written to evidence that is NOT a gate result. The verifier writes nothing.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_gate as bg  # noqa: E402
import b4_sim as sim  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_sim_verify as sv  # noqa: E402

PLACEHOLDER_SHA = "0" * 64


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _j(x) -> str:
    return sc.canonical(x)


class _F:
    def __init__(self):
        self.d: dict[str, list[str]] = {}

    def add(self, where: str, *msgs: str) -> None:
        if msgs:
            self.d.setdefault(where, []).extend(msgs)

    def __bool__(self):
        return bool(self.d)


def _load(path: Path):
    try:
        raw = path.read_bytes()
        return json.loads(raw), raw, None
    except (OSError, ValueError) as exc:
        return None, None, f"unreadable: {type(exc).__name__}: {exc}"


def verify_gate_dir(gate_dir: Path, doc: dict | None = None, root: Path | None = None, deep: bool = True, check_md: bool = True) -> dict:
    """{location: [findings]} ({} = nothing found). `doc` is the report document when the tool verifies its own judgement before
    writing gate_report.json (then `check_md` is False: the markdown is rendered after); otherwise the file is read."""
    F = _F()
    gate_dir = Path(gate_dir)
    if not gate_dir.is_dir():
        F.add("gate directory", "does not exist"); return F.d
    gate_dir = gate_dir.resolve()
    if root is None:
        if len(gate_dir.parents) < 4:
            F.add("gate directory", "does not lie under a root"); return F.d
        root = gate_dir.parents[3]
    root = Path(root).resolve()
    try:
        rel = gate_dir.relative_to(root)
    except ValueError:
        F.add("gate directory", f"not under the root {root}"); return F.d
    if str(rel.parent) != bg.GATE_REL:
        F.add("gate directory", f"lies at {rel}, not directly under {bg.GATE_REL}/"); return F.d
    disk = {p.name: p for p in sorted(gate_dir.iterdir()) if p.is_file()}
    for sub in gate_dir.iterdir():
        if sub.is_dir() or sub.is_symlink():
            F.add(sub.name, "a gate directory holds files only, none a symlink")
    for name in disk:
        if name.endswith(".part"):
            F.add(name, "an unfinished write")
    from_disk = doc is None
    if from_disk:
        if bg.REPORT_JSON not in disk:
            F.add(bg.REPORT_JSON, "missing"); return F.d
        doc, _, err = _load(disk[bg.REPORT_JSON])
        if err:
            F.add(bg.REPORT_JSON, err); return F.d
    rf = bg.gate_report_findings(doc)
    if rf:
        F.add(bg.REPORT_JSON, *rf); return F.d
    kind = doc["evidence_kind"]
    expected = {bg.REPORT_MD} | ({bg.REPORT_JSON} if from_disk else set()) | ({bg.SYNTHETIC_JSON} if kind == "synthetic_summary" else set())
    if not check_md:
        expected.discard(bg.REPORT_MD)
    for name in sorted(set(disk) - expected):
        F.add(name, "not a file of a gate directory")
    for name in sorted(expected - set(disk)):
        F.add(name, "missing")
    if not gate_dir.name.startswith(doc["label"] + "_"):
        F.add("gate directory", f"its name does not begin with the judged label {doc['label']}_")
    if F:
        return F.d
    # --- the file index
    for e in doc["files"]:
        if e["path"] == bg.REPORT_MD and not check_md:
            continue
        p = disk.get(e["path"])
        if p is None:
            F.add(e["path"], "indexed but not on disk"); continue
        b = p.read_bytes()
        if _sha(b) != e["sha256"] or len(b) != e["size"]:
            F.add(e["path"], "the file's digest / size are not the index's")
    # --- the evidence binding
    b = doc["batch"]
    evidence_doc = None
    if kind == "batch_archive":
        parts = Path(b["path"]).parts
        if not (len(parts) == 4 and str(Path(*parts[:3])) == sim.SIM_REL and parts[3].startswith(doc["label"] + "_")):
            F.add("batch", f"the batch path {b['path']!r} is not directly under {sim.SIM_REL}/ with the judged label"); return F.d
        bdir = root / b["path"]
        if not bdir.is_dir():
            F.add("batch", f"the batch archive {b['path']} does not exist under the root"); return F.d
        rep, raw, err = _load(bdir / "sim_report.json")
        if err:
            F.add("batch", f"sim_report.json {err}"); return F.d
        if _sha(raw) != b["sha256"]:
            F.add("batch", "sim_report.json does not hash to the recorded digest")
        for name, key in (("seeds.json", "seeds_sha256"), ("manifest.json", "manifest_sha256")):
            p = bdir / name
            if not p.is_file():
                F.add("batch", f"{name} is missing from the archive")
            elif b[key] is None or _sha(p.read_bytes()) != b[key]:
                F.add("batch", f"{name} does not hash to the recorded digest")
        rfs = sc.report_findings(rep)
        if rfs:
            F.add("batch", "sim_report.json does not validate: " + "; ".join(rfs[:3])); return F.d
        if not (rep["label"] == b["label"] and rep["count"] == b["count"] and rep["fixture"] == b["fixture"] and rep["status"] == b["status"] and rep["head"] == b["head"] and rep["generated_utc"] == b["generated_utc"]):
            F.add("batch", "the archive's identity (label / count / fixture / status / HEAD / time) is not the recorded one")
        if not (sim.GATE_LABEL_RE.match(rep["label"]) or sim.FIXTURE_LABEL_RE.match(rep["label"])):
            F.add("batch", f"the archive's label {rep['label']!r} is neither a gate label nor a mechanics fixture label: an exploration archive is never a gate's evidence")
        if F:
            return F.d
        if deep:
            try:
                bf = sv.verify_run_dir(bdir, deep=True)
            except Exception as exc:  # noqa: BLE001
                bf = {"verifier": [f"the archive verifier raised {type(exc).__name__}: {exc}"]}
            for where, msgs in bf.items():
                F.add(f"batch: {where}", *msgs)
        evidence_doc = rep
    else:
        want_rel = f"{bg.GATE_REL}/{gate_dir.name}/{bg.SYNTHETIC_JSON}"
        if b["path"] != want_rel:
            F.add("batch", f"the synthetic summary's path {b['path']!r} is not {want_rel!r}"); return F.d
        syn, raw, err = _load(disk[bg.SYNTHETIC_JSON])
        if err:
            F.add(bg.SYNTHETIC_JSON, err); return F.d
        if _sha(raw) != b["sha256"]:
            F.add("batch", "synthetic_summary.json does not hash to the recorded digest")
        sf = bg.synthetic_findings(syn)
        if sf:
            F.add(bg.SYNTHETIC_JSON, *sf); return F.d
        if not (syn["label"] == b["label"] and syn["count"] == b["count"] and syn["fixture"] == b["fixture"] and syn["status"] == b["status"] and syn["head"] == b["head"] and syn["generated_utc"] == b["generated_utc"]):
            F.add("batch", "the synthetic summary's identity is not the recorded one")
        if b["seeds_sha256"] is not None or b["manifest_sha256"] is not None:
            F.add("batch", "a synthetic summary has no seeds / manifest digest")
        if doc["formal"] is not False:
            F.add(bg.REPORT_JSON, "a synthetic judgement is never formal")
        evidence_doc = syn
    if F:
        return F.d
    # --- the judgement recomputed
    j = bg.judge(evidence_doc, kind)
    if _j(j["budget_rule"]) != _j(doc["budget_rule"]):
        F.add(bg.REPORT_JSON, "the budget rule is not the one recomputed from the evidence")
    if _j(j["rows"]) != _j(doc["rows"]):
        diff = [a["id"] for a, c in zip(j["rows"], doc["rows"]) if _j(a) != _j(c)]
        F.add(bg.REPORT_JSON, f"the rows are not the ones recomputed from the evidence: {diff}")
    if j["formal"] != doc["formal"] or j["formal_reasons"] != doc["formal_reasons"]:
        F.add(bg.REPORT_JSON, "formal / formal_reasons are not the ones recomputed")
    if j["contract_findings"] != doc["contract_findings"]:
        F.add(bg.REPORT_JSON, "contract_findings are not the ones recomputed")
    if doc["self_validation"] != {}:
        F.add(bg.REPORT_JSON, "the report recorded self-validation findings: its judgement did not stand (never clean)")
    elif _j(j["verdict"]) != _j(doc["verdict"]):
        F.add(bg.REPORT_JSON, f"the verdict {doc['verdict']['status']} is not the recomputed {j['verdict']['status']}")
    want_standing = bg.STANDING_FORMAL if j["formal"] else bg.STANDING_NOT_FORMAL.format(kind=kind, label=j["label"])
    if doc["standing"] != want_standing:
        F.add(bg.REPORT_JSON, "the standing is not the one of the recomputed formal flag")
    if _j(bg._diagnostics(evidence_doc, kind)) != _j(doc["diagnostics"]):
        F.add(bg.REPORT_JSON, "the diagnostics are not the ones of the evidence")
    # --- the markdown
    if check_md:
        md = bg.render_md(doc).encode("utf-8")
        if disk[bg.REPORT_MD].read_bytes() != md:
            F.add(bg.REPORT_MD, "not the rendering of gate_report.json")
    return F.d


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Verify a gate directory offline (the evidence re-verified, the judgement recomputed; writes nothing).")
    ap.add_argument("gate_dir")
    ap.add_argument("--shallow", action="store_true", help="no re-execution of the batch archive (bindings, validators, the judgement and the rendering only)")
    a = ap.parse_args(argv)
    try:
        f = verify_gate_dir(Path(a.gate_dir), deep=not a.shallow)
    except Exception as exc:  # noqa: BLE001
        f = {"verifier": [f"the gate verifier raised {type(exc).__name__}: {exc}"]}
    print(json.dumps({"gate_dir": a.gate_dir, "findings": f, "clean": not f,
                      "limit": "a clean verification shows the judgement follows from its evidence under the fixed criteria; it is not itself a PASS, and a fixture or synthetic judgement is never a gate result"}, indent=1))
    return 0 if not f else 1


if __name__ == "__main__":
    sys.exit(main())
