#!/usr/bin/env python3
"""B4 — the TYPED VALIDATORS of every file the exploration harness writes (the owner's ruling of 2026-10-18 on unit 2b-4a,
section 4.3: "the schema covers seeds / manifest / raw / checkpoints / STOPPED and the status report, or validators of the
same strictness per file, with tests"). No schema library: each validator returns named findings, total over the file's
keys, type-exact on every scalar; the harness validates a document BEFORE it writes it (a document that does not validate is
never written), and `validate_run_dir` re-reads a run directory offline.

Files of a run directory `evidence/b4/sim/<label>_<UTC>/`:
    seeds.json                      b4_sim_seeds 1.0.0         (b4_seeds.seeds_doc_findings)
    manifest.json                   b4_sim_manifest 1.0.0      the provenance snapshot before the first observation
    pair_NNN/arm_<role>.result.json b4_sim_arm_result 1.0.0    the engine's RunResult as returned, written before any audit
    pair_NNN/arm_<role>.audit.json  b4_sim_arm_audit 1.0.0     completion checks, replay, recompute, states, view checks
    pair_NNN/controls.json          b4_sim_controls 1.0.0      the X / D / Omega / A0 inputs of the pair
    pair_NNN/k7.json                b4_sim_k7 1.0.0            arm O's prefix snapshots at every grid budget
    pair_NNN/k9.json                b4_sim_k9 1.0.0            b4_k9.coverage's result
    pair_NNN/k10.json               b4_sim_k10 1.0.0           b4_k10.seed_k10's result (or the partial carried by K10Invalid)
    pair_NNN/curves.json            b4_sim_curves 1.0.0        best-so-far at the grid per arm; F's end-to-end values
    pair_NNN/index.json             b4_sim_pair_index 1.0.0    the pair's files with digests and sizes (written last)
    STOPPED.json                    b4_sim_stopped 1.0.0       any batch that did not complete
    INIT_FAILED.json                b4_sim_init_failed 1.0.0   an initialisation that failed after the directory was created
    sim_report.json                 b4_sim_report 1.0.0        always: the status, the identity, the archive index; a summary only when complete
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_replay as br  # noqa: E402
import b4_seeds as bs  # noqa: E402

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
ROLES = ("R", "F", "O", "X", "D", "Omega", "A0")
STATUSES = ("complete", "invalid", "incomplete")
STOP_KINDS = ("deadline", "interrupted", "contract", "domain", "control_failure", "refusal", "input_drift", "schema", "unexpected_exception", "k10_invalid", "k9_invalid")
ARM_STATES = ("not_started", "in_flight", "written", "audited", "result_unavailable")
PAIR_STATES = ("not_started", "in_progress", "complete", "partial")


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _nonneg(v) -> bool:
    return _int(v) and v >= 0


def _num(v) -> bool:
    return (_int(v) or (isinstance(v, float) and math.isfinite(v)))


def _keys(doc, want: set, f: list[str], where: str) -> bool:
    if not isinstance(doc, dict):
        f.append(f"{where}: not an object"); return False
    if set(doc) != want:
        f.append(f"{where}: keys {sorted(set(doc) ^ want)} differ from the schema's"); return False
    return True


def _schema(doc, name: str, f: list[str]) -> None:
    if doc.get("schema") != name or doc.get("schema_version") != "1.0.0":
        f.append(f"schema / schema_version is not {name} 1.0.0")


def _file_entries(v, f: list[str], where: str) -> None:
    if not isinstance(v, list):
        f.append(f"{where}: not a list"); return
    for i, e in enumerate(v):
        if not (isinstance(e, dict) and set(e) == {"path", "sha256", "size"} and isinstance(e["path"], str) and HEX64.match(str(e["sha256"])) and _nonneg(e["size"])):
            f.append(f"{where}[{i}]: not a (path, sha256, size) entry")


def _encoded_stat(v) -> bool:
    return isinstance(v, dict) and set(v) == {"value", "special"} and (v["value"] is None or _num(v["value"])) and v["special"] in (None, "+inf", "-inf", "nan", "none")


# ------------------------------------------------------------------ the documents
def seeds_findings(doc) -> list[str]:
    return bs.seeds_doc_findings(doc)


def init_failed_findings(doc) -> list[str]:
    return bs.init_failed_findings(doc)


MANIFEST_KEYS = {"schema", "schema_version", "label", "count", "generated_utc", "head", "repo_root_kind", "deadline_s", "arm_order", "engine_arm",
                 "budget", "grid", "constants", "thresholds", "inputs", "tool_files", "hypothesis", "mapping", "fabric", "exclusion", "seeds_sha256", "note"}


def manifest_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, MANIFEST_KEYS, f, "manifest"):
        return f
    _schema(doc, "b4_sim_manifest", f)
    if not (isinstance(doc["label"], str) and bs.LABEL_RE.match(doc["label"])):
        f.append("label")
    if not (_int(doc["count"]) and doc["count"] > 0):
        f.append("count")
    if not (isinstance(doc["head"], str) and HEX40.match(doc["head"])):
        f.append("head")
    if not (_int(doc["deadline_s"]) and doc["deadline_s"] > 0):
        f.append("deadline_s")
    if tuple(doc["arm_order"]) != ROLES:
        f.append("arm_order")
    if not (isinstance(doc["engine_arm"], dict) and set(doc["engine_arm"]) == set(ROLES)):
        f.append("engine_arm")
    if not (_int(doc["budget"]) and doc["budget"] > 0):
        f.append("budget")
    if not (isinstance(doc["grid"], list) and all(_int(b) and b > 0 for b in doc["grid"]) and doc["grid"] == sorted(doc["grid"])):
        f.append("grid")
    for k in ("constants", "thresholds", "fabric", "exclusion"):
        if not isinstance(doc[k], dict):
            f.append(k)
    for k in ("inputs", "tool_files"):
        if not (isinstance(doc[k], dict) and all(isinstance(p, str) and HEX64.match(str(s)) for p, s in doc[k].items())):
            f.append(k)
    h = doc["hypothesis"]
    if not (isinstance(h, dict) and set(h) == {"path", "sha256", "version", "fixture", "sources"} and HEX64.match(str(h["sha256"])) and h["fixture"] is False
            and isinstance(h["sources"], list)):
        f.append("hypothesis")
    m = doc["mapping"]
    if not (isinstance(m, dict) and set(m) == {"site", "certificate", "certificate_sha256", "addresses"} and HEX64.match(str(m["certificate_sha256"]))
            and isinstance(m["addresses"], list) and len(m["addresses"]) == 21):
        f.append("mapping")
    if not HEX64.match(str(doc["seeds_sha256"])):
        f.append("seeds_sha256")
    if not isinstance(doc["note"], str):
        f.append("note")
    return f


ARM_RESULT_KEYS = {"schema", "schema_version", "pair", "role", "engine_arm", "landscape_seed", "operator_seed", "budget", "port_calls", "wall_s", "written_utc", "result"}


def arm_result_findings(doc, task=None) -> list[str]:
    f: list[str] = []
    if not _keys(doc, ARM_RESULT_KEYS, f, "arm result"):
        return f
    _schema(doc, "b4_sim_arm_result", f)
    if doc["role"] not in ROLES:
        f.append("role")
    if doc["engine_arm"] not in ("R", "F", "O", "X"):
        f.append("engine_arm")
    for k in ("pair", "landscape_seed", "operator_seed", "budget", "port_calls"):
        if not _nonneg(doc[k]):
            f.append(k)
    if not (_num(doc["wall_s"]) and doc["wall_s"] >= 0):
        f.append("wall_s")
    if not isinstance(doc["written_utc"], str):
        f.append("written_utc")
    r = doc["result"]
    if task is not None:
        f += [f"result: {x}" for x in br.shape_findings(r, task)]
    elif not isinstance(r, dict):
        f.append("result: not an object")
    if isinstance(r, dict) and r.get("arm") != doc["engine_arm"]:
        f.append("result.arm is not engine_arm")
    return f


ARM_AUDIT_KEYS = {"schema", "schema_version", "pair", "role", "completion_findings", "replay_findings", "recompute", "states", "view_findings", "invalid", "audited_utc"}


def arm_audit_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, ARM_AUDIT_KEYS, f, "arm audit"):
        return f
    _schema(doc, "b4_sim_arm_audit", f)
    if doc["role"] not in ROLES:
        f.append("role")
    if not _nonneg(doc["pair"]):
        f.append("pair")
    for k in ("completion_findings", "replay_findings", "view_findings"):
        if not (isinstance(doc[k], list) and all(isinstance(x, str) for x in doc[k])):
            f.append(k)
    for k in ("recompute", "states"):
        if not isinstance(doc[k], dict):
            f.append(k)
    if not isinstance(doc["invalid"], bool):
        f.append("invalid")
    if doc["invalid"] is not bool(doc["completion_findings"] or doc["replay_findings"] or doc["view_findings"] or (isinstance(doc["recompute"], dict) and doc["recompute"].get("findings"))):
        f.append("invalid is not the findings' disjunction")
    return f


CONTROLS_KEYS = {"schema", "schema_version", "pair", "x_control_seed", "d", "d_view", "omega_view", "a0_view", "written_utc"}


def controls_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, CONTROLS_KEYS, f, "controls"):
        return f
    _schema(doc, "b4_sim_controls", f)
    if not _nonneg(doc["pair"]) or not (_int(doc["x_control_seed"]) and 0 <= doc["x_control_seed"] <= 0xFFFFFFFF):
        f.append("pair / x_control_seed")
    if not (isinstance(doc["d"], dict) and {"d_shuffle_seed", "parent_commitment", "permutation", "identity", "residual_structure", "logical_cost_probes", "reobserved"} <= set(doc["d"])):
        f.append("d")
    for k in ("d_view", "omega_view", "a0_view"):
        v = doc[k]
        if not (isinstance(v, dict) and set(v) == br.VIEW_KEYS):
            f.append(k)
    if isinstance(doc.get("omega_view"), dict) and doc["omega_view"].get("privileged") is not True:
        f.append("omega_view is not privileged")
    if isinstance(doc.get("d_view"), dict) and (doc["d_view"].get("privileged") is not False or doc["d_view"].get("provenance") != ["learned", "shuffled"]):
        f.append("d_view's provenance")
    return f


K7_KEYS = {"schema", "schema_version", "pair", "arm", "grid", "prefixes", "complete", "written_utc"}


def k7_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, K7_KEYS, f, "k7"):
        return f
    _schema(doc, "b4_sim_k7", f)
    if doc["arm"] != "O":
        f.append("arm")
    if not isinstance(doc["complete"], bool):
        f.append("complete")
    pre = doc["prefixes"]
    if not (isinstance(pre, dict) and all(str(b) in pre for b in doc["grid"][:len(pre)])):
        f.append("prefixes"); return f
    for b, p in pre.items():
        if not (isinstance(p, dict) and {"arm", "budget", "records", "findings", "states", "not_unknown", "map_version", "map_commitment", "relations"} <= set(p)):
            f.append(f"prefixes[{b}]"); continue
        if p["states"] is not None and (set(p["states"]) != {"unknown", "effect_seen", "no_effect_seen", "context_dependent"} or sum(p["states"].values()) != 21):
            f.append(f"prefixes[{b}]: the four states do not sum to 21")
    return f


K9_KEYS = {"panel_version", "landscape_seed", "task_digest", "stimulus_sha256", "backgrounds", "pairs_total", "pairs_done", "pairs", "observations", "memo",
           "logical_observations", "complete", "stopped", "summary", "note"}


def k9_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, K9_KEYS | {"schema", "schema_version", "pair"}, f, "k9"):
        return f
    _schema(doc, "b4_sim_k9", f)
    if not (isinstance(doc["backgrounds"], list) and len(doc["backgrounds"]) == 64):
        f.append("backgrounds")
    if doc["pairs_total"] != 1184 or not _nonneg(doc["pairs_done"]) or len(doc["pairs"]) != doc["pairs_done"]:
        f.append("pairs_total / pairs_done")
    if not isinstance(doc["complete"], bool):
        f.append("complete")
    if doc["complete"] is not (doc["stopped"] is None):
        f.append("complete / stopped")
    if doc["complete"] is not (doc["summary"] is not None):
        f.append("a summary exists exactly when complete")
    for i, p in enumerate(doc["pairs"]):
        if not (isinstance(p, dict) and {"bit", "address", "semantic", "element", "g0", "g1", "backgrounds", "applicable", "reason", "scope", "obs0", "obs1", "differences", "covered"} <= set(p)):
            f.append(f"pairs[{i}]"); break
        if not isinstance(p["applicable"], bool) or (p["applicable"] and not isinstance(p["covered"], bool)) or (not p["applicable"] and p["covered"] is not None):
            f.append(f"pairs[{i}]: applicable / covered typing"); break
    for i, o in enumerate(doc["observations"]):
        if not (isinstance(o, dict) and {"id", "genome", "config_sha256", "stimulus_sha256", "provenance_sha256", "trace_sha256", "q_grid", "fixture", "fabric_kind"} <= set(o)):
            f.append(f"observations[{i}]"); break
        if o["fixture"] is not False or o["fabric_kind"] != "truth":
            f.append(f"observations[{i}]: not the formal source"); break
    return f


K10_KEYS = {"landscape_seed", "task_digest", "stimulus_sha256", "tau", "backgrounds", "backgrounds_equal", "units_total", "units", "observations", "memo",
            "complete", "stopped", "invalid", "max_abs_index", "comparable_pairs", "not_comparable_pairs", "outcome", "logical_corners", "note"}


def k10_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, K10_KEYS | {"schema", "schema_version", "pair"}, f, "k10"):
        return f
    _schema(doc, "b4_sim_k10", f)
    if not (isinstance(doc["backgrounds"], list) and len(doc["backgrounds"]) == 2 and all(_nonneg(b) for b in doc["backgrounds"])):
        f.append("backgrounds")
    if doc["units_total"] != 420 or not isinstance(doc["units"], list):
        f.append("units_total / units")
    if not isinstance(doc["complete"], bool):
        f.append("complete")
    if doc["complete"] and (doc["stopped"] is not None or doc["invalid"] is not None or len(doc["units"]) != 420 or doc["outcome"] is None):
        f.append("a complete K10 has 420 units, an outcome, no stop and no invalid")
    if not doc["complete"] and doc["outcome"] is not None:
        f.append("an incomplete K10 carries an outcome")
    for i, u in enumerate(doc["units"]):
        if not (isinstance(u, dict) and {"background_index", "background", "a", "b", "comparable", "illegal_corners", "index", "corners"} <= set(u)):
            f.append(f"units[{i}]"); break
        if set(u["corners"]) != {"00", "01", "10", "11"}:
            f.append(f"units[{i}]: corners"); break
    return f


CURVES_KEYS = {"schema", "schema_version", "pair", "landscape_seed", "operator_seed", "grid", "base_fit", "best_at_grid", "f_end_to_end_at_grid", "holdout", "written_utc"}


def curves_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, CURVES_KEYS, f, "curves"):
        return f
    _schema(doc, "b4_sim_curves", f)
    if not _nonneg(doc["base_fit"]):
        f.append("base_fit")
    g = doc["grid"]
    bag = doc["best_at_grid"]
    if not (isinstance(bag, dict) and set(bag) == set(ROLES) and all(isinstance(v, list) and len(v) == len(g) and all(_nonneg(x) for x in v) for v in bag.values())):
        f.append("best_at_grid")
    fe = doc["f_end_to_end_at_grid"]
    if not (isinstance(fe, list) and len(fe) == len(g) and all(isinstance(e, dict) and set(e) == {"T", "value", "mapping_in_progress"} and _nonneg(e["value"]) and isinstance(e["mapping_in_progress"], bool) for e in fe)):
        f.append("f_end_to_end_at_grid")
    if not (isinstance(doc["holdout"], dict) and set(doc["holdout"]) == set(ROLES) and all(_nonneg(v) for v in doc["holdout"].values())):
        f.append("holdout")
    return f


PAIR_INDEX_KEYS = {"schema", "schema_version", "pair", "landscape_seed", "operator_seed", "status", "arms", "files", "written_utc"}


def pair_index_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, PAIR_INDEX_KEYS, f, "pair index"):
        return f
    _schema(doc, "b4_sim_pair_index", f)
    if doc["status"] not in PAIR_STATES:
        f.append("status")
    if not (isinstance(doc["arms"], dict) and set(doc["arms"]) == set(ROLES) and all(v in ARM_STATES for v in doc["arms"].values())):
        f.append("arms")
    _file_entries(doc["files"], f, "files")
    return f


STOPPED_KEYS = {"schema", "schema_version", "status", "kind", "detail", "pair", "stage", "role", "stopped_utc", "deadline", "planned", "head_at_stop", "traceback"}


def stopped_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, STOPPED_KEYS, f, "STOPPED"):
        return f
    _schema(doc, "b4_sim_stopped", f)
    if doc["status"] not in ("invalid", "incomplete"):
        f.append("status")
    if doc["kind"] not in STOP_KINDS:
        f.append("kind")
    if not isinstance(doc["detail"], str):
        f.append("detail")
    if not (doc["pair"] is None or _nonneg(doc["pair"])):
        f.append("pair")
    if not isinstance(doc["stage"], str) or not (doc["role"] is None or doc["role"] in ROLES or doc["role"] in ("K9", "K10")):
        f.append("stage / role")
    if not isinstance(doc["deadline"], dict):
        f.append("deadline")
    pl = doc["planned"]
    if not (isinstance(pl, list) and all(isinstance(p, dict) and {"pair", "landscape_seed", "operator_seed", "status", "arms"} <= set(p) and p["status"] in PAIR_STATES for p in pl)):
        f.append("planned")
    if not (doc["head_at_stop"] is None or HEX40.match(str(doc["head_at_stop"]))):
        f.append("head_at_stop")
    if not (doc["traceback"] is None or isinstance(doc["traceback"], str)):
        f.append("traceback")
    return f


REPORT_KEYS = {"schema", "schema_version", "status", "label", "count", "head", "generated_utc", "deadline", "standing", "thresholds", "identity",
               "pairs", "files", "stopped", "summary", "missing", "self_validation"}


def report_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, REPORT_KEYS, f, "report"):
        return f
    _schema(doc, "b4_sim_report", f)
    if doc["status"] not in STATUSES:
        f.append("status")
    if not (isinstance(doc["label"], str) and bs.LABEL_RE.match(doc["label"])):
        f.append("label")
    if not (_int(doc["count"]) and doc["count"] > 0):
        f.append("count")
    if not (isinstance(doc["head"], str) and HEX40.match(doc["head"])):
        f.append("head")
    for k in ("deadline", "thresholds", "identity"):
        if not isinstance(doc[k], dict):
            f.append(k)
    if not isinstance(doc["standing"], str) or "not a gate verdict" not in doc["standing"]:
        f.append("standing must say it is not a gate verdict")
    pl = doc["pairs"]
    if not (isinstance(pl, list) and len(pl) == doc.get("count") and all(isinstance(p, dict) and p.get("status") in PAIR_STATES for p in pl)):
        f.append("pairs")
    _file_entries(doc["files"], f, "files")
    if doc["status"] == "complete":
        if doc["stopped"] is not None or doc["summary"] is None or doc["missing"] != []:
            f.append("a complete report has a summary, no STOPPED and nothing missing")
    else:
        if doc["summary"] is not None:
            f.append("a batch that did not complete carries no pooled numeric summary")
        if not isinstance(doc["stopped"], dict):
            f.append("a batch that did not complete carries its STOPPED record")
        if not (isinstance(doc["missing"], list) and all(isinstance(x, str) for x in doc["missing"])):
            f.append("missing")
    if isinstance(doc["summary"], dict):
        verdict_like = re.compile(r"(^|_)(pass|passed|fail|failed|verdict|holds)($|_)")
        for k in _all_keys(doc["summary"]):
            if verdict_like.search(k.lower()):
                f.append(f"the summary carries a verdict-like key {k!r}")
                break
    if not (isinstance(doc["self_validation"], dict) and all(isinstance(v, list) for v in doc["self_validation"].values())):
        f.append("self_validation")
    return f


def _all_keys(obj, out=None) -> list[str]:
    out = [] if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k)); _all_keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _all_keys(v, out)
    return out


# ------------------------------------------------------------------ the run directory, offline
VALIDATORS = {"seeds.json": seeds_findings, "manifest.json": manifest_findings, "STOPPED.json": stopped_findings, "INIT_FAILED.json": init_failed_findings,
              "sim_report.json": report_findings, "controls.json": controls_findings, "k7.json": k7_findings, "k9.json": k9_findings, "k10.json": k10_findings,
              "curves.json": curves_findings, "index.json": pair_index_findings}


def validate_file(path: Path, task=None) -> list[str]:
    try:
        doc = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        return [f"unreadable: {exc.__class__.__name__}: {exc}"]
    name = path.name
    if name.endswith(".result.json"):
        return arm_result_findings(doc, task)
    if name.endswith(".audit.json"):
        return arm_audit_findings(doc)
    v = VALIDATORS.get(name)
    if v is None:
        return [f"{name}: no validator for this file"]
    return v(doc)


def validate_run_dir(out: Path, task_of=None) -> dict:
    """Every JSON file under the run directory against its validator (a .part file is a finding: an unfinished write).
    `task_of(pair_index)` gives the PublicTask for the arm results' shape check; without it the result is checked as an object."""
    out = Path(out)
    findings: dict = {}
    for p in sorted(out.rglob("*")):
        if p.is_dir():
            continue
        rel = str(p.relative_to(out))
        if p.name.endswith(".part"):
            findings[rel] = ["an unfinished write"]; continue
        if not p.name.endswith(".json"):
            findings[rel] = ["not a JSON file of the harness"]; continue
        task = None
        if p.name.endswith(".result.json") and task_of is not None:
            m = re.match(r"pair_(\d+)$", p.parent.name)
            task = task_of(int(m.group(1))) if m else None
        f = validate_file(p, task)
        if f:
            findings[rel] = f
    return findings
