#!/usr/bin/env python3
"""B4 — the TYPED VALIDATORS of every file the exploration harness writes (the owner's ruling of 2026-10-18 on unit 2b-4a,
section 4.3; tightened after the owner's review of cdf2c53, F3). No schema library: each validator returns named findings,
total over the file's keys, type-exact on every scalar and on every NESTED value the arithmetic later reads (a q cell is 0,
1 or null; an id is an int that exists; a score is an int), and NEVER raises — a malformed document is findings, not an
exception. The harness validates a document BEFORE it writes it (a document that does not validate is never written as that
file; a returned object that does not validate is quarantined); `validate_run_dir` re-reads a run directory file by file,
and `b4_sim_verify.verify_run_dir` is the archive-wide verifier (required files, hashes, linkage, re-execution).

The FIXED comparison sets are enforced here, not only recomputed: a complete K9 record holds exactly the 1 184 forced pairs
in their order, a complete K10 record exactly the 420 units in theirs; a partial record holds a prefix. The declared task
and source are checked against the document whenever a task is given (seed, digest, stimulus digest, provenance).

Files of a run directory `evidence/b4/sim/<label>_<UTC>/`:
    seeds.json                      b4_sim_seeds 1.1.0         (b4_seeds.seeds_doc_findings; `fixture` False = production, True = mechanics)
    manifest.json                   b4_sim_manifest 1.1.0      the provenance snapshot before the first observation (external sources, registry snapshot)
    pair_NNN/arm_<role>.result.json b4_sim_arm_result 1.0.0    the engine's RunResult as returned, written before any audit
    pair_NNN/arm_<role>.result.QUARANTINE.json  b4_sim_quarantine 1.0.0  a returned RunResult that did NOT validate, kept raw with the findings
    pair_NNN/arm_<role>.audit.json  b4_sim_arm_audit 1.0.0     completion checks, replay, recompute, states, view checks
    pair_NNN/controls.json          b4_sim_controls 1.0.0      the X / D / Omega / A0 inputs of the pair
    pair_NNN/k7.json                b4_sim_k7 1.0.0            arm O's prefix snapshots at every grid budget
    pair_NNN/k9.json                b4_sim_k9 1.1.0            b4_k9.coverage's result (complete, stopped or invalid — the partial is kept)
    pair_NNN/k10.json               b4_sim_k10 1.0.0           b4_k10.seed_k10's result (complete, stopped or invalid — the partial is kept)
    pair_NNN/k9.QUARANTINE.json / k10.QUARANTINE.json          a partial that did not validate, kept raw
    pair_NNN/curves.json            b4_sim_curves 1.0.0        best-so-far at the grid per arm; F's end-to-end values
    pair_NNN/index.json             b4_sim_pair_index 1.0.0    the pair's files with digests and sizes (written last)
    STOPPED.json                    b4_sim_stopped 1.0.0       any batch that did not complete
    INIT_FAILED.json                b4_sim_init_failed 1.0.0   an initialisation that failed after the directory was created
    sim_report.json                 b4_sim_report 1.0.0        always: the status, the identity, the archive index; a summary only when complete
"""
from __future__ import annotations

import functools
import json
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_k10 as k10  # noqa: E402
import b4_k9 as k9  # noqa: E402
import b4_replay as br  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_stats as st  # noqa: E402
import b4_thresholds as th  # noqa: E402

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
ROLES = ("R", "F", "O", "X", "D", "Omega", "A0")
STATUSES = ("complete", "invalid", "incomplete")
STOP_KINDS = ("deadline", "interrupted", "contract", "domain", "control_failure", "refusal", "input_drift", "schema", "unexpected_exception",
              "k10_invalid", "k9_invalid", "self_validation")
ARM_STATES = ("not_started", "in_flight", "written", "audited", "result_unavailable", "result_malformed")
PAIR_STATES = ("not_started", "in_progress", "complete", "partial")
DIAG_STATES = ("not_started", "in_progress", "complete", "partial", "invalid")
GENOME_BITS = 21
ELEMENTS = 8


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _nonneg(v) -> bool:
    return _int(v) and v >= 0


def _num(v) -> bool:
    return (_int(v) or (isinstance(v, float) and math.isfinite(v)))


def _genome(v) -> bool:
    return _nonneg(v) and v < (1 << GENOME_BITS)


def _keys(doc, want: set, f: list[str], where: str) -> bool:
    if not isinstance(doc, dict):
        f.append(f"{where}: not an object"); return False
    if set(doc) != want:
        f.append(f"{where}: keys {sorted(set(doc) ^ want)} differ from the schema's"); return False
    return True


def _schema(doc, name: str, f: list[str], version: str = "1.0.0") -> None:
    if doc.get("schema") != name or doc.get("schema_version") != version:
        f.append(f"schema / schema_version is not {name} {version}")


def _file_entries(v, f: list[str], where: str) -> None:
    if not isinstance(v, list):
        f.append(f"{where}: not a list"); return
    seen = set()
    for i, e in enumerate(v):
        if not (isinstance(e, dict) and set(e) == {"path", "sha256", "size"} and isinstance(e["path"], str) and HEX64.match(str(e["sha256"])) and _nonneg(e["size"])):
            f.append(f"{where}[{i}]: not a (path, sha256, size) entry"); continue
        if e["path"] in seen:
            f.append(f"{where}[{i}]: the path {e['path']!r} is listed twice")
        seen.add(e["path"])


def _encoded_stat(v) -> bool:
    return isinstance(v, dict) and set(v) == {"value", "special"} and (v["value"] is None or _num(v["value"])) and v["special"] in (None, "+inf", "-inf", "nan", "none")


def _q_grid(g, f: list[str], where: str, steps: int | None = None) -> bool:
    """A kept q grid: a list of rows, one per stimulus step, each of exactly ELEMENTS cells, each cell 0, 1 or null."""
    if not (isinstance(g, list) and g):
        f.append(f"{where}: not a non-empty list of rows"); return False
    for i, row in enumerate(g):
        if not (isinstance(row, list) and len(row) == ELEMENTS and all(c is None or (c in (0, 1) and _int(c)) for c in row)):
            f.append(f"{where}[{i}]: not {ELEMENTS} cells of 0 / 1 / null"); return False
    if steps is not None and len(g) != steps:
        f.append(f"{where}: {len(g)} rows, the stimulus has {steps} steps"); return False
    return True


def _observations(obs, f: list[str], where: str, stimulus_sha: str | None, memo: dict | None, steps: int | None) -> dict:
    """The kept observations of a K9 / K10 record: ids 0..n-1 in order, typed fields, the formal source, one provenance."""
    if not isinstance(obs, list):
        f.append(f"{where}: not a list"); return {}
    out: dict = {}
    for i, o in enumerate(obs):
        if not (isinstance(o, dict) and {"id", "genome", "genome_hex", "config_sha256", "stimulus_sha256", "provenance_sha256", "trace_sha256", "q_grid", "fixture", "fabric_kind"} <= set(o)):
            f.append(f"{where}[{i}]: not an observation record"); return out
        if not _int(o["id"]) or o["id"] != i:
            f.append(f"{where}[{i}]: id {o['id']!r} is not the int {i} (ids are 0 .. n-1 in order)"); return out
        if not _genome(o["genome"]):
            f.append(f"{where}[{i}]: the genome is not a {GENOME_BITS}-bit int"); return out
        for k in ("config_sha256", "stimulus_sha256", "provenance_sha256", "trace_sha256"):
            if not (isinstance(o[k], str) and HEX64.match(o[k])):
                f.append(f"{where}[{i}]: {k} is not a sha256"); return out
        if not _q_grid(o["q_grid"], f, f"{where}[{i}].q_grid", steps):
            return out
        if ex.sha256_json(o["q_grid"]) != o["trace_sha256"]:
            f.append(f"{where}[{i}]: the q grid does not hash to trace_sha256"); return out
        if o["fixture"] is not False or o["fabric_kind"] != "truth":
            f.append(f"{where}[{i}]: not the formal source"); return out
        if stimulus_sha is not None and o["stimulus_sha256"] != stimulus_sha:
            f.append(f"{where}[{i}]: not under the record's stimulus"); return out
        if isinstance(memo, dict) and o["provenance_sha256"] != memo.get("provenance_sha256"):
            f.append(f"{where}[{i}]: provenance_sha256 is not the memo's"); return out
        out[i] = o
    return out


def _memo(m, f: list[str], n_obs: int) -> None:
    if not (isinstance(m, dict) and set(m) == {"port_calls", "cache_hits", "unique_observations", "provenance", "provenance_sha256"}):
        f.append("memo: keys"); return
    if not (_nonneg(m["port_calls"]) and _nonneg(m["cache_hits"]) and _nonneg(m["unique_observations"])):
        f.append("memo: counts"); return
    if m["unique_observations"] != n_obs:
        f.append(f"memo.unique_observations {m['unique_observations']} is not the {n_obs} observations kept")
    if n_obs == 0:
        if not (m["provenance"] is None and m["provenance_sha256"] is None):
            f.append("memo: a provenance without an observation")
        return
    prov = m["provenance"]
    if not (isinstance(prov, dict) and ex.provenance_findings(prov) == [] and ex.sha256_json(prov) == m["provenance_sha256"]):
        f.append("memo.provenance: malformed or not hashing to provenance_sha256"); return
    if canonical(prov) != canonical(formal_provenance()):
        f.append("memo.provenance: not the formal source's identity (hypothesis, mapping, truth fabric)")


def _task_binding(doc, task, f: list[str]) -> None:
    if task is None:
        return
    if doc["landscape_seed"] != task.seed:
        f.append(f"landscape_seed {doc['landscape_seed']!r} is not the task's {task.seed}")
    if doc["task_digest"] != task.digest():
        f.append("task_digest is not the task's")
    if doc["stimulus_sha256"] != ex.sha256_json(list(task.stimulus)):
        f.append("stimulus_sha256 is not the task's")


@functools.lru_cache(maxsize=1)
def formal_provenance() -> dict:
    """The source identity EVERY formal observation carries (b4_execution.provenance_findings' shape), built from the formal
    inputs: the hypothesis (path, sha256, version, fixture False), the mapping (site, certificate, its digest), the truth
    fabric's descriptor. Every recorded provenance — a RunResult's, a memo's, the manifest's descriptors — is bound to it."""
    h, m = hy.load(), bm.site_mapping()
    fab = fm.Fabric(m, h)
    return {"hypothesis": {"path": h.path, "sha256": h.sha256, "version": h.version, "fixture": h.fixture},
            "mapping": {"site": m.site, "certificate": m.certificate_rel, "certificate_sha256": m.certificate_sha256},
            "fabric": dict(fab.source)}


def canonical(x) -> str:
    """The canonical JSON text of a value: comparisons through it are exact in type (2, 2.0, true are three different texts)."""
    return json.dumps(x, sort_keys=True, allow_nan=False)


def total(fn):
    """A validator never raises: an exception while validating is itself a finding."""
    @functools.wraps(fn)
    def wrapped(doc, *a, **kw):
        try:
            return fn(doc, *a, **kw)
        except Exception as exc:  # noqa: BLE001
            return [f"{fn.__name__}: the validator raised {type(exc).__name__}: {exc} — the document is malformed"]
    return wrapped


# ------------------------------------------------------------------ the documents
@total
def seeds_findings(doc) -> list[str]:
    return bs.seeds_doc_findings(doc)


@total
def init_failed_findings(doc) -> list[str]:
    return bs.init_failed_findings(doc)


MANIFEST_KEYS = {"schema", "schema_version", "label", "fixture", "count", "generated_utc", "head", "repo_root_kind", "code_root", "deadline_s", "arm_order", "engine_arm",
                 "budget", "grid", "constants", "thresholds", "inputs", "external_inputs", "tool_files", "hypothesis", "mapping", "fabric", "exclusion", "seeds_sha256", "note"}


@total
def manifest_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, MANIFEST_KEYS, f, "manifest"):
        return f
    _schema(doc, "b4_sim_manifest", f, "1.1.0")
    if not (isinstance(doc["label"], str) and bs.LABEL_RE.match(doc["label"])):
        f.append("label")
    if not isinstance(doc["fixture"], bool):
        f.append("fixture")
    elif isinstance(doc["label"], str) and doc["fixture"] is not bool(bs.FIXTURE_LABEL_RE.match(doc["label"])):
        f.append("fixture / label: a fixture batch has a b4-mech-<n> label and a production batch has not")
    if not (_int(doc["count"]) and doc["count"] > 0):
        f.append("count")
    if not (isinstance(doc["head"], str) and HEX40.match(doc["head"])):
        f.append("head")
    cr = doc["code_root"]
    if not (isinstance(cr, dict) and set(cr) == {"head", "clean", "same_as_input_root"} and (cr["head"] is None or (isinstance(cr["head"], str) and HEX40.match(cr["head"])))
            and (cr["clean"] is None or isinstance(cr["clean"], bool)) and isinstance(cr["same_as_input_root"], bool)):
        f.append("code_root")
    if not (_int(doc["deadline_s"]) and doc["deadline_s"] > 0):
        f.append("deadline_s")
    if not (isinstance(doc["arm_order"], list) and tuple(doc["arm_order"]) == ROLES):
        f.append("arm_order")
    if not (isinstance(doc["engine_arm"], dict) and set(doc["engine_arm"]) == set(ROLES)):
        f.append("engine_arm")
    if not (_int(doc["budget"]) and doc["budget"] > 0):
        f.append("budget")
    if not (isinstance(doc["grid"], list) and all(_int(b) and b > 0 for b in doc["grid"]) and doc["grid"] == sorted(doc["grid"])):
        f.append("grid")
    for k in ("constants", "thresholds", "fabric"):
        if not isinstance(doc[k], dict):
            f.append(k)
    for k in ("inputs", "external_inputs", "tool_files"):
        if not (isinstance(doc[k], dict) and all(isinstance(p, str) and isinstance(s, str) and HEX64.match(s) for p, s in doc[k].items())):
            f.append(k)
    e = doc["exclusion"]
    if not (isinstance(e, dict) and {"historical_sources", "pooled_total", "sim_registry", "sim_registry_note", "registry_snapshot"} <= set(e)
            and isinstance(e["registry_snapshot"], list) and all(isinstance(r, list) and len(r) == 3 for r in e["registry_snapshot"])):
        f.append("exclusion")
    h = doc["hypothesis"]
    if not (isinstance(h, dict) and set(h) == {"path", "sha256", "version", "fixture", "sources"} and isinstance(h["sha256"], str) and HEX64.match(h["sha256"]) and h["fixture"] is False
            and isinstance(h["sources"], list)):
        f.append("hypothesis")
    m = doc["mapping"]
    if not (isinstance(m, dict) and set(m) == {"site", "certificate", "certificate_sha256", "addresses"} and isinstance(m["certificate_sha256"], str) and HEX64.match(m["certificate_sha256"])
            and isinstance(m["addresses"], list) and len(m["addresses"]) == 21):
        f.append("mapping")
    if not f:                                                           # R2: the descriptors are the FORMAL inputs', not merely well-formed
        formal = formal_provenance()
        fh, fm_ = hy.load(), bm.site_mapping()
        if canonical({k: h[k] for k in ("path", "sha256", "version", "fixture")}) != canonical(formal["hypothesis"]) or canonical(h["sources"]) != canonical(fh.doc["sources"]):
            f.append("hypothesis: not the formal hypothesis's descriptor and sources")
        if canonical(m) != canonical({**formal["mapping"], "addresses": list(fm_.addresses)}):
            f.append("mapping: not the formal mapping's site / certificate / addresses")
        if canonical(doc["fabric"]) != canonical(formal["fabric"]):
            f.append("fabric: not the truth fabric's descriptor")
        if canonical(doc["thresholds"]) != canonical(th.THRESHOLDS) or doc["grid"] != list(th.GRID) or doc["budget"] != th.B_MAX:
            f.append("thresholds / grid / budget: not the fixed table's")
    if not (isinstance(doc["seeds_sha256"], str) and HEX64.match(doc["seeds_sha256"])):
        f.append("seeds_sha256")
    for k in ("note", "repo_root_kind", "generated_utc"):
        if not isinstance(doc[k], str):
            f.append(k)
    return f


ARM_RESULT_KEYS = {"schema", "schema_version", "pair", "role", "engine_arm", "landscape_seed", "operator_seed", "budget", "port_calls", "wall_s", "written_utc", "result"}


ENGINE_ARM = {"R": "R", "F": "F", "O": "O", "X": "X", "D": "F", "Omega": "F", "A0": "F"}


@total
def arm_result_findings(doc, task=None, expect=None) -> list[str]:
    """`expect` (R2): {"pair", "role", "landscape_seed", "operator_seed", "x_control_seed"} — the planned identity the file must
    carry, in the wrapper and in the result; with a task, the result's digest and provenance are bound to the formal ones."""
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
    if isinstance(r, dict):
        if r.get("arm") != doc["engine_arm"]:
            f.append("result.arm is not engine_arm")
        if canonical([r.get("landscape_seed"), r.get("operator_seed"), r.get("budget")]) != canonical([doc["landscape_seed"], doc["operator_seed"], doc["budget"]]):
            f.append("result's seeds / budget are not the file's")
        if doc["role"] in ROLES and doc["engine_arm"] != ENGINE_ARM[doc["role"]]:
            f.append("engine_arm is not the role's")
        if doc["budget"] != th.B_MAX:
            f.append("budget is not the fixed B_max")
        if task is not None:
            if r.get("task_digest") != task.digest() or r.get("landscape_seed") != task.seed:
                f.append("result: not the pair's task")
            if canonical(r.get("provenance")) != canonical(formal_provenance()) or r.get("fixture") is not False or r.get("fabric_fixture") is not False:
                f.append("result: the provenance is not the formal source's")
        if expect is not None:
            if canonical([doc["pair"], doc["role"], doc["landscape_seed"], doc["operator_seed"]]) != canonical([expect["pair"], expect["role"], expect["landscape_seed"], expect["operator_seed"]]):
                f.append(f"the wrapper's pair / role / seeds are not the planned {expect['pair']} / {expect['role']} / {expect['landscape_seed']} / {expect['operator_seed']}")
            want_x = expect["x_control_seed"] if expect["role"] == "X" else None
            if canonical(r.get("x_control_seed")) != canonical(want_x):
                f.append("result.x_control_seed is not the planned control seed (X) / null (every other role)")
    return f


QUARANTINE_KEYS = {"schema", "schema_version", "pair", "role", "stage", "findings", "raw", "raw_repr", "written_utc"}


@total
def quarantine_findings(doc) -> list[str]:
    """A returned object that did not validate, kept as raw as JSON allows: the findings that refused it, the JSON-able
    projection (`raw`, or null when the object could not be serialised) and `repr` of the object."""
    f: list[str] = []
    if not _keys(doc, QUARANTINE_KEYS, f, "quarantine"):
        return f
    _schema(doc, "b4_sim_quarantine", f)
    if not _nonneg(doc["pair"]) or not (doc["role"] is None or doc["role"] in ROLES or doc["role"] in ("K9", "K10")):
        f.append("pair / role")
    if not (isinstance(doc["stage"], str) and isinstance(doc["written_utc"], str) and isinstance(doc["raw_repr"], str)):
        f.append("stage / written_utc / raw_repr")
    if not (isinstance(doc["findings"], list) and doc["findings"] and all(isinstance(x, str) for x in doc["findings"])):
        f.append("findings: a quarantine names what refused the object")
    return f


ARM_AUDIT_KEYS = {"schema", "schema_version", "pair", "role", "completion_findings", "replay_findings", "recompute", "states", "view_findings", "invalid", "audited_utc"}


@total
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
    if f:
        return f
    if doc["invalid"] is not bool(doc["completion_findings"] or doc["replay_findings"] or doc["view_findings"] or doc["recompute"].get("findings")):
        f.append("invalid is not the findings' disjunction")
    return f


CONTROLS_KEYS = {"schema", "schema_version", "pair", "x_control_seed", "d", "d_view", "omega_view", "a0_view", "written_utc"}


@total
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
    if f:
        return f
    if doc["omega_view"].get("privileged") is not True:
        f.append("omega_view is not privileged")
    if doc["d_view"].get("privileged") is not False or doc["d_view"].get("provenance") != ["learned", "shuffled"]:
        f.append("d_view's provenance")
    return f


K7_KEYS = {"schema", "schema_version", "pair", "arm", "grid", "prefixes", "complete", "written_utc"}


@total
def k7_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, K7_KEYS, f, "k7"):
        return f
    _schema(doc, "b4_sim_k7", f)
    if doc["arm"] != "O":
        f.append("arm")
    if not isinstance(doc["complete"], bool):
        f.append("complete")
    if not (isinstance(doc["grid"], list) and all(_int(b) and b > 0 for b in doc["grid"])):
        f.append("grid"); return f
    pre = doc["prefixes"]
    if not (isinstance(pre, dict) and set(pre) == {str(b) for b in doc["grid"][:len(pre)]}):
        f.append("prefixes: not the first budgets of the grid"); return f
    if doc["complete"] and len(pre) != len(doc["grid"]):
        f.append("a complete K7 has a prefix at every grid budget")
    for b, p in pre.items():
        if not (isinstance(p, dict) and {"arm", "budget", "records", "findings", "states", "not_unknown", "map_version", "map_commitment", "relations"} <= set(p)):
            f.append(f"prefixes[{b}]"); continue
        if p["budget"] != int(b) or not (isinstance(p["findings"], list) and all(isinstance(x, str) for x in p["findings"])):
            f.append(f"prefixes[{b}]: budget / findings")
        if p["states"] is not None and (not isinstance(p["states"], dict) or set(p["states"]) != {"unknown", "effect_seen", "no_effect_seen", "context_dependent"}
                                        or not all(_nonneg(v) for v in p["states"].values()) or sum(p["states"].values()) != 21):
            f.append(f"prefixes[{b}]: the four states do not sum to 21")
        if p["findings"] and doc["complete"]:
            f.append(f"prefixes[{b}]: a complete K7 carries a finding")
    return f


K9_KEYS = {"panel_version", "landscape_seed", "task_digest", "stimulus_sha256", "backgrounds", "pairs_total", "pairs_done", "pairs", "observations", "memo",
           "logical_observations", "complete", "stopped", "invalid", "summary", "note"}
K9_PAIR_KEYS = {"bit", "address", "semantic", "element", "g0", "g1", "backgrounds", "applicable", "reason", "scope", "obs0", "obs1", "hit0", "hit1", "differences", "covered"}


@total
def k9_findings(doc, task=None) -> list[str]:
    f: list[str] = []
    if not _keys(doc, K9_KEYS | {"schema", "schema_version", "pair"}, f, "k9"):
        return f
    _schema(doc, "b4_sim_k9", f, "1.1.0")
    mapping = bm.site_mapping()
    panel = k9.panel(mapping)
    if doc["backgrounds"] != panel:
        f.append("backgrounds: not the fixed 64-background panel")
    if doc["panel_version"] != k9.PANEL_VERSION:
        f.append("panel_version")
    if not (_nonneg(doc["landscape_seed"]) and isinstance(doc["task_digest"], str) and isinstance(doc["stimulus_sha256"], str) and HEX64.match(doc["stimulus_sha256"])):
        f.append("landscape_seed / task_digest / stimulus_sha256"); return f
    _task_binding(doc, task, f)
    if not isinstance(doc["complete"], bool):
        f.append("complete"); return f
    if doc["complete"] is not (doc["stopped"] is None and doc["invalid"] is None):
        f.append("complete exactly when neither stopped nor invalid")
    if doc["stopped"] is not None and doc["invalid"] is not None:
        f.append("stopped and invalid at once")
    if doc["complete"] is not (doc["summary"] is not None):
        f.append("a summary exists exactly when complete")
    if not (isinstance(doc["pairs"], list) and _nonneg(doc["pairs_done"]) and len(doc["pairs"]) == doc["pairs_done"]):
        f.append("pairs / pairs_done"); return f
    steps = len(task.stimulus) if task is not None else None
    obs = _observations(doc["observations"], f, "observations", doc["stimulus_sha256"], doc["memo"] if isinstance(doc["memo"], dict) else None, steps)
    _memo(doc["memo"], f, len(doc["observations"]) if isinstance(doc["observations"], list) else 0)
    for i, p in enumerate(doc["pairs"]):
        if not (isinstance(p, dict) and K9_PAIR_KEYS <= set(p)):
            f.append(f"pairs[{i}]: keys"); break
        if not (_nonneg(p["bit"]) and p["bit"] < GENOME_BITS and isinstance(p["address"], str) and p["semantic"] in k9.SEMANTICS and (p["element"] is None or isinstance(p["element"], str))
                and _genome(p["g0"]) and _genome(p["g1"]) and p["g0"] != p["g1"] and isinstance(p["backgrounds"], list) and (p["reason"] is None or isinstance(p["reason"], str))
                and isinstance(p["scope"], list) and isinstance(p["differences"], list)):
            f.append(f"pairs[{i}]: typing"); break
        if not isinstance(p["applicable"], bool) or (p["applicable"] and not isinstance(p["covered"], bool)) or (not p["applicable"] and p["covered"] is not None):
            f.append(f"pairs[{i}]: applicable / covered typing"); break
        if p["applicable"]:
            if not (_int(p["obs0"]) and _int(p["obs1"]) and p["obs0"] in obs and p["obs1"] in obs and isinstance(p["hit0"], bool) and isinstance(p["hit1"], bool)):
                f.append(f"pairs[{i}]: an applicable pair's observations are not kept records"); break
            if (obs[p["obs0"]]["genome"], obs[p["obs1"]]["genome"]) != (p["g0"], p["g1"]):
                f.append(f"pairs[{i}]: the observations are not of the pair's endpoints"); break
            if p["covered"] is not bool(p["differences"]):
                f.append(f"pairs[{i}]: covered is not the presence of differences"); break
        elif not (p["obs0"] is None and p["obs1"] is None and p["differences"] == []):
            f.append(f"pairs[{i}]: a not-applicable pair carries observations or differences"); break
    if f:
        return f
    f += k9.canonical_findings(doc, mapping)
    if not _int(doc["logical_observations"]) or doc["logical_observations"] != 2 * sum(1 for p in doc["pairs"] if p["applicable"]):
        f.append("logical_observations is not twice the applicable pairs")
    if doc["complete"] and canonical(doc["summary"]) != canonical(k9.summarise(doc["pairs"], mapping)):
        f.append("the summary is not what the pairs give")
    if doc["stopped"] is not None and not (isinstance(doc["stopped"], dict) and {"before_pair_index", "reason"} <= set(doc["stopped"]) and doc["stopped"]["before_pair_index"] == doc["pairs_done"]):
        f.append("stopped: not a record of the pair it stopped before")
    if doc["invalid"] is not None and not (isinstance(doc["invalid"], dict) and {"pair_index", "exception", "reason"} <= set(doc["invalid"]) and doc["invalid"]["pair_index"] == doc["pairs_done"]):
        f.append("invalid: not a record of the pair it failed in")
    if not isinstance(doc["note"], str):
        f.append("note")
    return f


K10_KEYS = {"landscape_seed", "task_digest", "stimulus_sha256", "tau", "backgrounds", "backgrounds_equal", "units_total", "units", "observations", "memo",
            "complete", "stopped", "invalid", "max_abs_index", "comparable_pairs", "not_comparable_pairs", "outcome", "logical_corners", "note"}
K10_UNIT_KEYS = {"background_index", "background", "a", "b", "comparable", "illegal_corners", "index", "corners"}


@total
def k10_findings(doc, task=None) -> list[str]:
    f: list[str] = []
    if not _keys(doc, K10_KEYS | {"schema", "schema_version", "pair"}, f, "k10"):
        return f
    _schema(doc, "b4_sim_k10", f)
    if not (_nonneg(doc["landscape_seed"]) and isinstance(doc["task_digest"], str) and isinstance(doc["stimulus_sha256"], str) and HEX64.match(doc["stimulus_sha256"])):
        f.append("landscape_seed / task_digest / stimulus_sha256"); return f
    _task_binding(doc, task, f)
    if not (isinstance(doc["backgrounds"], list) and len(doc["backgrounds"]) == 2 and all(_genome(b) for b in doc["backgrounds"])):
        f.append("backgrounds"); return f
    if doc["backgrounds"] != k10.backgrounds(doc["landscape_seed"]):
        f.append("backgrounds: not the seed's two fixed backgrounds")
    if doc["backgrounds_equal"] is not (doc["backgrounds"][0] == doc["backgrounds"][1]):
        f.append("backgrounds_equal")
    if not _int(doc["tau"]) or doc["tau"] != k10.TAU:
        f.append("tau is not the fixed threshold")
    if not isinstance(doc["complete"], bool) or not isinstance(doc["units"], list):
        f.append("complete / units"); return f
    if doc["complete"] is not (doc["stopped"] is None and doc["invalid"] is None):
        f.append("complete exactly when neither stopped nor invalid")
    if doc["stopped"] is not None and doc["invalid"] is not None:
        f.append("stopped and invalid at once")
    steps = len(task.stimulus) if task is not None else None
    obs = _observations(doc["observations"], f, "observations", doc["stimulus_sha256"], doc["memo"] if isinstance(doc["memo"], dict) else None, steps)
    _memo(doc["memo"], f, len(doc["observations"]) if isinstance(doc["observations"], list) else 0)
    for i, u in enumerate(doc["units"]):
        if not (isinstance(u, dict) and K10_UNIT_KEYS <= set(u)):
            f.append(f"units[{i}]: keys"); break
        if not (u["background_index"] in (0, 1) and _int(u["background_index"]) and _genome(u["background"]) and u["background"] == doc["backgrounds"][u["background_index"]]
                and _nonneg(u["a"]) and _nonneg(u["b"]) and u["a"] < u["b"] < GENOME_BITS and isinstance(u["comparable"], bool) and isinstance(u["illegal_corners"], list)
                and isinstance(u["corners"], dict) and set(u["corners"]) == set(k10.CORNERS)):
            f.append(f"units[{i}]: typing"); break
        sc_ = {}
        for k, c in u["corners"].items():
            if not (isinstance(c, dict) and set(c) == {"genome", "score", "obs"} and c["genome"] == k10._corner_genome(u["background"], u["a"], u["b"], k)
                    and (c["score"] is None or _int(c["score"])) and (c["obs"] is None or (_int(c["obs"]) and c["obs"] in obs)) and ((c["score"] is None) == (c["obs"] is None))):
                f.append(f"units[{i}].corners[{k}]: typing"); break
            if c["obs"] is not None and obs[c["obs"]]["genome"] != c["genome"]:
                f.append(f"units[{i}].corners[{k}]: the observation is not of this corner"); break
            sc_[k] = c["score"]
        if len(sc_) != 4:
            break
        if u["comparable"]:
            if u["illegal_corners"] != [] or any(v is None for v in sc_.values()) or not _int(u["index"]) or u["index"] != sc_["11"] - sc_["10"] - sc_["01"] + sc_["00"]:
                f.append(f"units[{i}]: a comparable unit has four scores and index = f11 - f10 - f01 + f00"); break
        elif u["index"] is not None or not u["illegal_corners"] or not set(u["illegal_corners"]) <= set(k10.CORNERS) or any(sc_[k] is not None for k in u["illegal_corners"]):
            f.append(f"units[{i}]: a not-comparable unit names its refused corner(s), with no score there and no index"); break
        if not u["comparable"] and (doc["invalid"] is None or i != len(doc["units"]) - 1):
            f.append(f"units[{i}]: a refused corner is the invalid event and the last unit, never absorbed"); break
    if f:
        return f
    f += k10.canonical_findings(doc)
    if not _int(doc["logical_corners"]):
        f.append("logical_corners is not an int")
    if doc["complete"]:
        m, counts = st.seed_max(doc["units"])
        if canonical([doc["max_abs_index"], doc["comparable_pairs"], doc["not_comparable_pairs"]]) != canonical([m, counts["comparable_pairs"], counts["not_comparable_pairs"]]):
            f.append("max_abs_index / counts are not the units'")
        if doc["outcome"] != st.classify(m, doc["tau"]):
            f.append("the outcome is not the classification of the max")
    elif not (doc["max_abs_index"] is None and doc["comparable_pairs"] is None and doc["not_comparable_pairs"] is None and doc["outcome"] is None):
        f.append("an incomplete K10 carries a max / counts / outcome")
    if doc["stopped"] is not None and not (isinstance(doc["stopped"], dict) and {"before_unit_index", "reason"} <= set(doc["stopped"]) and doc["stopped"]["before_unit_index"] == len(doc["units"])):
        f.append("stopped: not a record of the unit it stopped before")
    if doc["invalid"] is not None and not (isinstance(doc["invalid"], dict) and {"unit_index", "illegal_corners", "exception", "reason"} <= set(doc["invalid"])):
        f.append("invalid: not a record of the unit it failed in")
    if not isinstance(doc["note"], str):
        f.append("note")
    return f


CURVES_KEYS = {"schema", "schema_version", "pair", "landscape_seed", "operator_seed", "grid", "base_fit", "best_at_grid", "f_end_to_end_at_grid", "holdout", "written_utc"}


@total
def curves_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, CURVES_KEYS, f, "curves"):
        return f
    _schema(doc, "b4_sim_curves", f)
    if not _nonneg(doc["base_fit"]):
        f.append("base_fit")
    g = doc["grid"]
    if not (isinstance(g, list) and all(_int(b) and b > 0 for b in g)):
        f.append("grid"); return f
    bag = doc["best_at_grid"]
    if not (isinstance(bag, dict) and set(bag) == set(ROLES) and all(isinstance(v, list) and len(v) == len(g) and all(_nonneg(x) for x in v) for v in bag.values())):
        f.append("best_at_grid")
    elif any(v[i] > v[i + 1] for v in bag.values() for i in range(len(g) - 1)):
        f.append("best_at_grid: best-so-far is non-decreasing along the grid")
    fe = doc["f_end_to_end_at_grid"]
    if not (isinstance(fe, list) and len(fe) == len(g) and all(isinstance(e, dict) and set(e) == {"T", "value", "mapping_in_progress"} and _nonneg(e["value"]) and isinstance(e["mapping_in_progress"], bool) for e in fe)):
        f.append("f_end_to_end_at_grid")
    elif [e["T"] for e in fe] != g:
        f.append("f_end_to_end_at_grid: T is not the grid")
    if not (isinstance(doc["holdout"], dict) and set(doc["holdout"]) == set(ROLES) and all(_nonneg(v) for v in doc["holdout"].values())):
        f.append("holdout")
    return f


PAIR_INDEX_KEYS = {"schema", "schema_version", "pair", "landscape_seed", "operator_seed", "status", "arms", "files", "written_utc"}


@total
def pair_index_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, PAIR_INDEX_KEYS, f, "pair index"):
        return f
    _schema(doc, "b4_sim_pair_index", f)
    if doc["status"] not in PAIR_STATES:
        f.append("status")
    if not (isinstance(doc["arms"], dict) and set(doc["arms"]) == set(ROLES) and all(v in ARM_STATES for v in doc["arms"].values())):
        f.append("arms")
    elif doc["status"] == "complete" and any(v != "audited" for v in doc["arms"].values()):
        f.append("a complete pair's index has every arm audited")
    _file_entries(doc["files"], f, "files")
    return f


STOPPED_KEYS = {"schema", "schema_version", "status", "kind", "detail", "pair", "stage", "role", "stopped_utc", "deadline", "planned", "head_at_stop", "traceback"}


@total
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
    _planned(doc["planned"], f)
    if not (doc["head_at_stop"] is None or (isinstance(doc["head_at_stop"], str) and HEX40.match(doc["head_at_stop"]))):
        f.append("head_at_stop")
    if not (doc["traceback"] is None or isinstance(doc["traceback"], str)):
        f.append("traceback")
    return f


def _planned(pl, f: list[str]) -> None:
    if not isinstance(pl, list):
        f.append("planned: not a list"); return
    for i, p in enumerate(pl):
        if not (isinstance(p, dict) and {"pair", "landscape_seed", "operator_seed", "status", "arms", "k7", "k9", "k10"} <= set(p) and p["pair"] == i
                and _nonneg(p["landscape_seed"]) and _nonneg(p["operator_seed"]) and p["status"] in PAIR_STATES
                and isinstance(p["arms"], dict) and set(p["arms"]) == set(ROLES) and all(v in ARM_STATES for v in p["arms"].values())
                and all(p[k] in DIAG_STATES for k in ("k7", "k9", "k10"))):
            f.append(f"planned[{i}]"); return
        if p["status"] == "complete" and not (all(v == "audited" for v in p["arms"].values()) and all(p[k] == "complete" for k in ("k7", "k9", "k10"))):
            f.append(f"planned[{i}]: a complete pair has every arm audited and K7 / K9 / K10 complete — a weaker state cannot be recorded as complete"); return


REPORT_KEYS = {"schema", "schema_version", "status", "label", "fixture", "count", "head", "generated_utc", "deadline", "standing", "thresholds", "identity",
               "pairs", "files", "stopped", "summary", "missing", "self_validation"}


@total
def report_findings(doc) -> list[str]:
    f: list[str] = []
    if not _keys(doc, REPORT_KEYS, f, "report"):
        return f
    _schema(doc, "b4_sim_report", f)
    if doc["status"] not in STATUSES:
        f.append("status")
    if not (isinstance(doc["label"], str) and bs.LABEL_RE.match(doc["label"])):
        f.append("label")
    if not isinstance(doc["fixture"], bool):
        f.append("fixture")
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
    _planned(pl, f)
    if isinstance(pl, list) and len(pl) != doc.get("count"):
        f.append("pairs: not one entry per planned pair")
    _file_entries(doc["files"], f, "files")
    if doc["status"] == "complete":
        if doc["stopped"] is not None or doc["summary"] is None or doc["missing"] != []:
            f.append("a complete report has a summary, no STOPPED and nothing missing")
        if isinstance(pl, list) and any(not isinstance(p, dict) or p.get("status") != "complete" for p in pl):
            f.append("a complete report has every pair complete")
        if isinstance(doc["deadline"], dict) and doc["deadline"].get("expired") is not False:
            f.append("a complete report's deadline has not expired")
        if doc["self_validation"] != {}:
            f.append("a complete report has an empty self-validation")
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
    if not (isinstance(doc["self_validation"], dict) and all(isinstance(v, list) and all(isinstance(x, str) for x in v) for v in doc["self_validation"].values())):
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


# ------------------------------------------------------------------ the run directory, offline, file by file
VALIDATORS = {"seeds.json": seeds_findings, "manifest.json": manifest_findings, "STOPPED.json": stopped_findings, "INIT_FAILED.json": init_failed_findings,
              "sim_report.json": report_findings, "controls.json": controls_findings, "k7.json": k7_findings, "curves.json": curves_findings, "index.json": pair_index_findings}
TASKED = {"k9.json": k9_findings, "k10.json": k10_findings}


def validate_file(path: Path, task=None) -> list[str]:
    try:
        doc = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        return [f"unreadable: {exc.__class__.__name__}: {exc}"]
    name = path.name
    if name.endswith(".QUARANTINE.json"):
        return quarantine_findings(doc)
    if name.endswith(".result.json"):
        return arm_result_findings(doc, task)
    if name.endswith(".audit.json"):
        return arm_audit_findings(doc)
    if name in TASKED:
        return TASKED[name](doc, task)
    v = VALIDATORS.get(name)
    if v is None:
        return [f"{name}: no validator for this file"]
    return v(doc)


def validate_run_dir(out: Path, task_of=None) -> dict:
    """Every JSON file under the run directory against its validator (a .part file is a finding: an unfinished write).
    `task_of(pair_index)` gives the PublicTask for the pair's files. FILE BY FILE ONLY: the archive-wide checks (required
    files, hashes, linkage, re-execution) are `b4_sim_verify.verify_run_dir`."""
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
        m = re.match(r"pair_(\d+)$", p.parent.name)
        if m and task_of is not None:
            try:
                task = task_of(int(m.group(1)))
            except Exception as exc:  # noqa: BLE001
                findings[rel] = [f"no task for this pair: {type(exc).__name__}: {exc}"]; continue
        f = validate_file(p, task)
        if f:
            findings[rel] = f
    return findings
