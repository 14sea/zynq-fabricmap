#!/usr/bin/env python3
"""B4 — the ARCHIVE-WIDE VERIFIER of an exploration run directory (the owner's review of cdf2c53, 2026-10-18, F2 / F3 /
F4): what `b4_sim_schema.validate_run_dir` does file by file, this does for the archive as a whole and for its conclusions.

    python3 b4/host/b4_sim_verify.py evidence/b4/sim/<label>_<UTC>      # prints the findings as JSON; exit 0 iff none

For a run directory it checks, in this order, and names every difference:
  1. the file set: the required files of the recorded status and of every pair's recorded state exist, no file exists that
     the report does not list, no `.part`, no duplicate entry; every listed sha256 / size equals the file on disk;
  2. the linkage: seeds.json ↔ manifest.seeds_sha256 ↔ report.identity; one label, one count, one HEAD across the three;
     the planned pairs are seeds.json's; STOPPED.json exists exactly when the status is not `complete` and equals the
     report's copy; the pair indexes list their pair's files with the same digests;
  3. every file against its typed validator, the pair's task bound (seed, digest, stimulus, provenance);
  4. (deep) the conclusions, recomputed from the raw readouts with the formal model: every arm result re-audited (the
     completion checks, the re-execution replay, the ledger recompute, the states) and held to its audit file; the controls
     (X seed by formula, D's view rebuilt from F's record, Omega / A0 by construction); K7's prefixes recomputed; K9 and K10
     recomputed from the kept grids; the curves from the results; the pooled summary from the rows — all held to the files.

AUTHENTICITY LIMIT (unchanged from b4_replay): a clean verification shows the archive is what the harness would have
written from these observations and that its conclusions follow from its raw readouts; it does not show that the
observation source told the truth. The verifier reads the directory and the formal inputs; it writes nothing.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_carto as bc  # noqa: E402
import b4_controls as ctl  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_k10 as k10  # noqa: E402
import b4_k9 as k9  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_replay as br  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_snapshot as sn  # noqa: E402
import b4_thresholds as th  # noqa: E402

ROLES = sc.ROLES
GRID = th.GRID
TOP = ("seeds.json", "manifest.json")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _j(x) -> str:
    """The canonical JSON text (sc.canonical): comparisons through it are exact in type (2, 2.0 and true differ)."""
    return sc.canonical(x)


def _load(path: Path):
    try:
        return json.loads(path.read_bytes()), None
    except (OSError, ValueError) as exc:
        return None, f"unreadable: {type(exc).__name__}: {exc}"


class _F:
    """Findings by location; `{}` when nothing was found."""

    def __init__(self):
        self.d: dict[str, list[str]] = {}

    def add(self, where: str, *msgs: str) -> None:
        if msgs:
            self.d.setdefault(where, []).extend(msgs)

    def __bool__(self):
        return bool(self.d)


def expected_pair_files(plan: dict) -> tuple[set, set]:
    """(must exist, may exist) for a pair from its planned record."""
    r = plan["pair"]
    pre = f"pair_{r:03d}/"
    must, may = set(), set()
    for role, state in plan["arms"].items():
        if state in ("written", "audited"):
            must.add(f"{pre}arm_{role}.result.json")
        if state == "audited":
            must.add(f"{pre}arm_{role}.audit.json")
        elif state == "written":
            may.add(f"{pre}arm_{role}.audit.json")                # an audit that found the run invalid is written before the stop
        if state == "result_malformed":
            must.add(f"{pre}arm_{role}.result.QUARANTINE.json")
    if plan["arms"]["F"] == "audited":
        must.add(f"{pre}controls.json")
    if plan["k7"] in ("complete", "in_progress"):
        must.add(f"{pre}k7.json")
    for k in ("k9", "k10"):
        if plan[k] in ("complete", "partial"):
            must.add(f"{pre}{k}.json")
        elif plan[k] == "invalid":
            may |= {f"{pre}{k}.json", f"{pre}{k}.QUARANTINE.json"}      # the invalid partial or its quarantine; none when the refusal came before any record
    if plan["status"] == "complete":
        must |= {f"{pre}curves.json", f"{pre}index.json"}
    return must, may


def diagnostic_state_findings(plan: dict, docs: dict) -> list[str]:
    """The recorded K7 / K9 / K10 state of a pair against its documents: `complete` needs a document that is complete (and
    for K9 / K10 neither stopped nor invalid, with the full fixed set); `partial` a document that is stopped and not complete;
    `invalid` a document with an invalid record (or its quarantine, or none when the refusal came before any record);
    `in_progress` for K7 (an invalid prefix) a document that is not complete, for K9 / K10 (entered, nothing returned — an
    interrupt before any record) no document; `not_started` no document. A complete pair needs all three complete.
    Total: a document that is not an object, or whose set is not a list, is a finding, never an exception (the owner's
    review of 2026-10-19 on 8d1eefd, finding 1) — the verifier passes only documents their typed validator accepted."""
    f: list[str] = []
    for k in ("k7", "k9", "k10"):
        state, doc = plan[k], docs.get(k)
        if doc is not None and not isinstance(doc, dict):
            f.append(f"{k}: the document is not an object"); continue
        if state == "complete":
            if doc is None or doc.get("complete") is not True:
                f.append(f"{k}: recorded complete, the document is {'missing' if doc is None else 'not complete'}"); continue
            if k != "k7" and (doc.get("stopped") is not None or doc.get("invalid") is not None):
                f.append(f"{k}: recorded complete, the document carries a stop or an invalid record")
            if k == "k9" and not (isinstance(doc.get("pairs"), list) and len(doc["pairs"]) == 1184):
                f.append("k9: recorded complete without the 1 184 pairs")
            if k == "k10" and not (isinstance(doc.get("units"), list) and len(doc["units"]) == 420):
                f.append("k10: recorded complete without the 420 units")
        elif state == "partial":
            if doc is None or doc.get("complete") is not False or doc.get("stopped") is None or doc.get("invalid") is not None:
                f.append(f"{k}: recorded partial, the document is not a stopped partial")
        elif state == "invalid":
            if doc is not None and (doc.get("complete") is not False or doc.get("invalid") is None):
                f.append(f"{k}: recorded invalid, the document is not an invalid partial")
        elif state == "in_progress":
            if k == "k7" and doc is not None and doc.get("complete") is not False:
                f.append("k7: recorded in progress, the document says complete")
            if k != "k7" and doc is not None:
                f.append(f"{k}: recorded in progress with a document")
        elif doc is not None:
            f.append(f"{k}: recorded not started with a document")
    if plan["status"] == "complete" and any(plan[k] != "complete" for k in ("k7", "k9", "k10")):
        f.append("a complete pair with a diagnostic not complete")
    return f


def verify_run_dir(out: Path, report: dict | None = None, deep: bool = True) -> dict:
    """The archive-wide verification; returns {location: [findings]} ({} = nothing found). `report` is the report document
    when the harness verifies its own directory before writing sim_report.json; otherwise the file is read."""
    out = Path(out)
    F = _F()
    if not out.is_dir():
        F.add("run directory", "does not exist"); return F.d
    disk = {str(p.relative_to(out)): p for p in sorted(out.rglob("*")) if p.is_file()}
    for rel in disk:
        if rel.endswith(".part"):
            F.add(rel, "an unfinished write")
    # --- an initialisation failure: INIT_FAILED.json (with or without seeds.json) and nothing else
    if "INIT_FAILED.json" in disk:
        doc, err = _load(disk["INIT_FAILED.json"])
        F.add("INIT_FAILED.json", *([err] if err else sc.init_failed_findings(doc)))
        extra = set(disk) - {"INIT_FAILED.json", "seeds.json", "manifest.json"}
        if extra:
            F.add("files", f"an initialisation failure with other files: {sorted(extra)[:5]}")
        if doc and not err and doc["seeds_derived"] is not ("seeds.json" in disk):
            F.add("INIT_FAILED.json", "seeds_derived does not match the presence of seeds.json")
        if "seeds.json" in disk:
            d, e = _load(disk["seeds.json"]); F.add("seeds.json", *([e] if e else sc.seeds_findings(d)))
        return F.d
    # --- the report
    if report is None:
        if "sim_report.json" not in disk:
            F.add("sim_report.json", "missing"); return F.d
        report, err = _load(disk["sim_report.json"])
        if err:
            F.add("sim_report.json", err); return F.d
    rf = sc.report_findings(report)
    if rf:
        F.add("sim_report.json", *rf); return F.d
    status = report["status"]
    # --- the top files and their linkage
    docs = {}
    for name in TOP:
        if name not in disk:
            F.add(name, "missing"); continue
        docs[name], err = _load(disk[name])
        if err:
            F.add(name, err); continue
        F.add(name, *sc.VALIDATORS[name](docs[name]))
    if F:
        return F.d
    seeds, manifest = docs["seeds.json"], docs["manifest.json"]
    seeds_sha, manifest_sha = _sha(disk["seeds.json"].read_bytes()), _sha(disk["manifest.json"].read_bytes())
    if manifest["seeds_sha256"] != seeds_sha:
        F.add("manifest.json", "seeds_sha256 is not seeds.json's digest")
    ident = report["identity"]
    if ident.get("seeds_sha256") != seeds_sha or ident.get("manifest_sha256") != manifest_sha:
        F.add("sim_report.json", "identity.seeds_sha256 / manifest_sha256 are not the files' digests")
    if ident.get("hypothesis_sha256") != hy.HYPOTHESIS_SHA256 or ident.get("certificate_sha256") != bm.CERTIFICATE_SHA256:
        F.add("sim_report.json", "identity: not the pinned hypothesis / certificate digests")
    if manifest["hypothesis"]["sha256"] != hy.HYPOTHESIS_SHA256 or manifest["inputs"].get(hy.HYPOTHESIS_REL) != hy.HYPOTHESIS_SHA256 or manifest["inputs"].get(bm.CERTIFICATE_REL) != bm.CERTIFICATE_SHA256:
        F.add("manifest.json", "the hypothesis / certificate digests are not the pinned ones")
    if ident.get("inputs") != manifest["inputs"]:
        F.add("sim_report.json", "identity.inputs are not the manifest's")
    if not (seeds["label"] == manifest["label"] == report["label"]) or not (seeds["count"] == manifest["count"] == report["count"]) or not (seeds["fixture"] == manifest["fixture"] == report["fixture"]):
        F.add("linkage", "label / count / fixture differ between seeds.json, manifest.json and the report")
    if manifest["head"] != report["head"]:
        F.add("linkage", "HEAD differs between manifest.json and the report")
    if _j(manifest["thresholds"]) != _j(th.THRESHOLDS) or _j(report["thresholds"]) != _j(th.THRESHOLDS):
        F.add("linkage", "the thresholds table is not the module's")
    import b4_sim as sim  # the harness's own constants and pure functions; imported here to avoid a cycle
    if _j(manifest["constants"]) != _j(sim.manifest_constants()) or _j(manifest["engine_arm"]) != _j(sim.ENGINE_ARM):
        F.add("manifest.json", "constants / engine_arm are not the harness's")
    if manifest["grid"] != list(GRID) or manifest["budget"] != th.B_MAX:
        F.add("manifest.json", "grid / budget are not the fixed ones")
    planned = report["pairs"]
    if _j([[p["landscape_seed"], p["operator_seed"]] for p in planned]) != _j(seeds["pairs"]):
        F.add("linkage", "the planned pairs are not seeds.json's")
    if F:
        return F.d
    # --- the deadline records bound to the declared duration (the manifest's, written before the first observation)
    F.add("sim_report.json", *sc.deadline_findings(report["deadline"], manifest["deadline_s"], "deadline"))
    if report["stopped"] is not None and isinstance(report["stopped"], dict) and isinstance(report["stopped"].get("deadline"), dict):
        F.add("sim_report.json", *sc.deadline_findings(report["stopped"]["deadline"], manifest["deadline_s"], "stopped.deadline"))
        sd_, rd_ = report["stopped"]["deadline"], report["deadline"]
        if isinstance(sd_.get("elapsed_s"), (int, float)) and isinstance(rd_.get("elapsed_s"), (int, float)) and sd_["elapsed_s"] > rd_["elapsed_s"] + sc.MS:
            F.add("sim_report.json", "the stop record's elapsed time exceeds the report's (the report is written after the stop)")
    if F:
        return F.d
    # --- the file set
    listed = {e["path"]: e for e in report["files"]}
    on_disk = set(disk) - {"sim_report.json"}
    if "sim_report.json" in disk and report is not None and "sim_report.json" in listed:
        F.add("sim_report.json", "the report lists itself")
    for rel in sorted(on_disk - set(listed)):
        F.add(rel, "on disk but not in the report's file index")
    for rel in sorted(set(listed) - on_disk):
        F.add(rel, "in the report's file index but not on disk")
    for rel, e in listed.items():
        if rel in disk:
            b = disk[rel].read_bytes()
            if _sha(b) != e["sha256"] or len(b) != e["size"]:
                F.add(rel, "the file's digest / size are not the index's")
    if (status != "complete") is not ("STOPPED.json" in disk):
        F.add("STOPPED.json", "exists exactly when the batch did not complete")
    if "STOPPED.json" in disk:
        sd, err = _load(disk["STOPPED.json"])
        F.add("STOPPED.json", *([err] if err else sc.stopped_findings(sd)))
        if sd is not None and not err and _j(sd) != _j(report["stopped"]):
            F.add("STOPPED.json", "not the report's copy")
    expected: set[str] = set(TOP)
    for plan in planned:
        must, may = expected_pair_files(plan)
        expected |= must
        for rel in sorted(must - on_disk):
            F.add(rel, f"required by pair {plan['pair']}'s recorded state ({plan['status']}) but missing")
        for k in ("k9", "k10"):
            if plan[k] == "invalid":
                have = {f"pair_{plan['pair']:03d}/{k}.json", f"pair_{plan['pair']:03d}/{k}.QUARANTINE.json"} & on_disk
                if len(have) != 1:
                    F.add(f"pair_{plan['pair']:03d}/{k}", "an invalid diagnostic keeps exactly one record: the partial or its quarantine")
                expected |= have
        expected |= may & on_disk
    if "STOPPED.json" in disk:
        expected.add("STOPPED.json")
    for rel in sorted(on_disk - expected):
        F.add(rel, "not a file any pair's recorded state accounts for")
    if F:
        return F.d
    # --- every file against its validator, the pair's task bound
    mapping = bm.site_mapping()
    tasks = {p["pair"]: bl.make_task(p["landscape_seed"], mapping.addresses) for p in planned}
    by_pair = {p["pair"]: p for p in planned}
    for rel, path in disk.items():
        if rel == "sim_report.json" or rel in TOP or rel == "STOPPED.json":
            continue
        m = re.match(r"pair_(\d+)/(.*)$", rel)
        if not m:
            F.add(rel, "not inside a pair directory"); continue
        r, name = int(m.group(1)), m.group(2)
        plan = by_pair.get(r)
        if plan is None:
            F.add(rel, "a pair directory the plan does not have"); continue
        expect = None
        am = re.match(r"arm_([A-Za-z0-9]+)\.result\.json$", name)
        if am:
            expect = {"pair": r, "role": am.group(1), "landscape_seed": plan["landscape_seed"], "operator_seed": plan["operator_seed"],
                      "x_control_seed": ctl.x_control_seed(plan["landscape_seed"], plan["operator_seed"])}
            if am.group(1) not in ROLES:
                F.add(rel, "not a role's result file"); continue
            doc, err = _load(path)
            F.add(rel, *([err] if err else sc.arm_result_findings(doc, tasks[r], expect)))
            continue
        f = sc.validate_file(path, tasks[r])
        F.add(rel, *f)
        if f:
            continue
        doc, _ = _load(path)
        # R2: every file of a pair names that pair (and the role of its name); curves / index name the pair's seeds
        if doc.get("pair") != r:
            F.add(rel, f"names pair {doc.get('pair')!r}, lies in pair {r}")
        rm = re.match(r"arm_([A-Za-z0-9]+)\.(audit|result\.QUARANTINE)\.json$", name)
        if rm and doc.get("role") != rm.group(1):
            F.add(rel, f"names role {doc.get('role')!r}, is the file of {rm.group(1)}")
        if name in ("curves.json", "index.json") and _j([doc.get("landscape_seed"), doc.get("operator_seed")]) != _j([plan["landscape_seed"], plan["operator_seed"]]):
            F.add(rel, "the seeds named are not the planned pair's")
        if name == "index.json" and _j(doc.get("arms")) != _j(plan["arms"]):
            F.add(rel, "the arm states are not the plan's")
    # --- the diagnostic state ↔ file contract: a plan's K7 / K9 / K10 state is confirmed by the document, never its own authority.
    # Only documents their typed validator accepted above enter the contract: a malformed one is already a named finding
    # (its own location), and the contract is not asked about a pair whose diagnostic files did not validate.
    for plan in planned:
        pre = f"pair_{plan['pair']:03d}/"
        present = [pre + f"{k}.json" for k in ("k7", "k9", "k10") if pre + f"{k}.json" in disk]
        if any(F.d.get(rel) for rel in present):
            continue
        F.add(pre, *diagnostic_state_findings(plan, {rel[len(pre):-5]: _load(disk[rel])[0] for rel in present}))
    if F:
        return F.d
    for plan in planned:
        if plan["status"] != "complete":
            continue
        pre = f"pair_{plan['pair']:03d}/"
        idx, err = _load(disk[pre + "index.json"])
        if err:
            continue
        pair_files = {rel[len(pre):] for rel in on_disk if rel.startswith(pre)} - {"index.json"}
        idx_files = {e["path"]: e for e in idx["files"]}
        if set(idx_files) != pair_files:
            F.add(pre + "index.json", f"the pair's files on disk differ from the index: {sorted(set(idx_files) ^ pair_files)[:5]}")
        for rel, e in idx_files.items():
            if listed.get(pre + rel) and (listed[pre + rel]["sha256"], listed[pre + rel]["size"]) != (e["sha256"], e["size"]):
                F.add(pre + "index.json", f"{rel}: the pair index and the report index disagree")
        if idx["status"] != "complete" or idx["arms"] != plan["arms"] or (idx["landscape_seed"], idx["operator_seed"]) != (plan["landscape_seed"], plan["operator_seed"]):
            F.add(pre + "index.json", "not the planned record of this pair")
    if F or not deep:
        return F.d
    # --- deep: the conclusions recomputed from the raw readouts on the formal model
    import b4_sim as sim  # the harness's own pure functions (completion checks, curves, summary); imported here to avoid a cycle
    try:
        hypothesis = hy.load()
        fabric = fm.Fabric(mapping, hypothesis)
    except Exception as exc:  # noqa: BLE001
        F.add("formal inputs", f"the formal model does not load: {type(exc).__name__}: {exc}"); return F.d
    rows = []
    for plan in planned:
        r = plan["pair"]
        pre = f"pair_{r:03d}/"
        task = tasks[r]
        results, views = {}, {}
        controls = _load(disk[pre + "controls.json"])[0] if pre + "controls.json" in disk else None
        if controls is not None:
            views = {"D": bc.MapView.from_dict(controls["d_view"]), "Omega": bc.MapView.from_dict(controls["omega_view"]), "A0": bc.MapView.from_dict(controls["a0_view"])}
            if controls["x_control_seed"] != ctl.x_control_seed(plan["landscape_seed"], plan["operator_seed"]):
                F.add(pre + "controls.json", "x_control_seed is not the section 8 formula's")
            if controls["omega_view"] != bc.oracle_view(mapping).as_dict() or controls["a0_view"] != bc.address_only_view(mapping.addresses).as_dict():
                F.add(pre + "controls.json", "omega_view / a0_view are not the ones built from the mapping")
        for role in ROLES:
            if pre + f"arm_{role}.result.json" not in disk:
                if plan["status"] == "complete":
                    F.add(pre + f"arm_{role}.result.json", "a complete pair without this arm's result")
                continue
            doc = _load(disk[pre + f"arm_{role}.result.json"])[0]
            d = doc["result"]
            results[role] = d
            audit = _load(disk[pre + f"arm_{role}.audit.json"])[0] if pre + f"arm_{role}.audit.json" in disk else None
            if plan["status"] == "complete" and (plan["arms"][role] != "audited" or audit is None):
                F.add(pre + f"arm_{role}.result.json", "a complete pair's arm is not audited (R1: a weaker recorded state cannot switch the audit off)")
            completion = sim.completion_findings(d, role, task, doc["port_calls"], views.get(role))
            replay = br.replay(d, task)
            rc = sn.recompute_findings(d, task)
            states = sn.arm_states(d, task)
            view_f = []
            if role in ("D", "Omega", "A0") and controls is not None:
                if d["given_view"] != views[role].as_dict():
                    view_f.append("the recorded given view is not the one handed to the arm")
                if role == "D" and "F" in results:
                    view_f += ctl.verify_d_view(d["given_view"], results["F"], task)
            if audit is not None:
                if _j((completion, replay, rc["findings"], states, view_f)) != _j((audit["completion_findings"], audit["replay_findings"], audit["recompute"]["findings"], audit["states"], audit["view_findings"])):
                    F.add(pre + f"arm_{role}.audit.json", "the audit recorded is not the audit recomputed (completion / replay / recompute / states / view)")
                if rc["relations_final"] is not None and audit["recompute"].get("relations_final_sha256") != ex.sha256_json(rc["relations_final"]):
                    F.add(pre + f"arm_{role}.audit.json", "relations_final_sha256 is not the recomputed relations'")
            if (plan["status"] == "complete" or plan["arms"][role] == "audited") and (completion or replay or rc["findings"] or view_f):
                F.add(pre + f"arm_{role}.result.json", "the arm does not re-audit clean: " + "; ".join((completion + replay + rc["findings"] + view_f)[:3]))
        if controls is not None and "F" in results:
            F.add(pre + "controls.json", *ctl.verify_d_view(controls["d_view"], results["F"], task))
        if pre + "k7.json" in disk and "O" in results:
            k7 = _load(disk[pre + "k7.json"])[0]
            for B, p in k7["prefixes"].items():
                if _j(sn.prefix_states(results["O"], task, int(B))) != _j(p):
                    F.add(pre + "k7.json", f"the prefix at B = {B} is not the one recomputed from O's ledger"); break
        k9d = _load(disk[pre + "k9.json"])[0] if pre + "k9.json" in disk else None
        if k9d is not None:
            F.add(pre + "k9.json", *k9.recompute(k9d, task, fabric))
        k10d = _load(disk[pre + "k10.json"])[0] if pre + "k10.json" in disk else None
        if k10d is not None:
            F.add(pre + "k10.json", *k10.recompute(k10d, task))
        if plan["status"] == "complete":
            if not (k9d and k9d.get("complete") is True and k10d and k10d.get("complete") is True):
                F.add(pre, "a complete pair's row needs complete K9 and K10 documents"); continue
            curves = _load(disk[pre + "curves.json"])[0]
            want = sim.curves_of(results, r, plan["landscape_seed"], plan["operator_seed"])
            if _j({k: v for k, v in curves.items() if k != "written_utc"}) != _j({k: v for k, v in want.items() if k != "written_utc"}):
                F.add(pre + "curves.json", "not the curves of the arm results")
            k7 = _load(disk[pre + "k7.json"])[0]
            rows.append({"pair": r, "landscape_seed": plan["landscape_seed"], "operator_seed": plan["operator_seed"], "base_fit": curves["base_fit"], "best_at_grid": curves["best_at_grid"],
                         "f_end_to_end_at_grid": [e["value"] for e in curves["f_end_to_end_at_grid"]], "k7_not_unknown_at_grid": [k7["prefixes"][str(B)]["not_unknown"] for B in GRID],
                         "k9": k9d["summary"]["per_semantic"], "k9_all_seven": k9d["summary"]["all_seven_positive_controls"], "k10_max_abs": k10d["max_abs_index"], "k10_outcome": k10d["outcome"]})
    if status == "complete":
        if len(rows) != report["count"]:
            F.add("sim_report.json", "a complete report without a complete row per pair")
        else:
            try:
                summary, _ = sim.summarise_batch(rows, report["count"])
            except Exception as exc:  # noqa: BLE001
                F.add("sim_report.json", f"the summary cannot be recomputed from the rows: {type(exc).__name__}: {exc}")
            else:
                if _j(summary) != _j(report["summary"]):
                    F.add("sim_report.json", "the pooled summary is not the one recomputed from the pairs' files")
    return F.d


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Verify an exploration run directory offline (archive-wide; writes nothing).")
    ap.add_argument("run_dir")
    ap.add_argument("--shallow", action="store_true", help="file set, linkage and validators only (no re-execution)")
    a = ap.parse_args(argv)
    try:
        f = verify_run_dir(Path(a.run_dir), deep=not a.shallow)
    except Exception as exc:  # noqa: BLE001 — the verifier failing is a finding, never a traceback in place of the result
        f = {"verifier": [f"the archive verifier raised {type(exc).__name__}: {exc}"]}
    print(json.dumps({"run_dir": a.run_dir, "findings": f, "clean": not f,
                      "limit": "a clean verification shows the archive follows from its raw readouts under the formal model, not that the source told the truth"}, indent=1))
    return 0 if not f else 1


if __name__ == "__main__":
    sys.exit(main())
