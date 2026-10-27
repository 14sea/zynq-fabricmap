#!/usr/bin/env python3
"""B4 — the ENGINEERING GO / NO-GO POLICY of an exploration (docs/b4_architecture.md section 9.4, DRAFT v0.3.0; the owner's choice 5
of 2026-10-20, carried to b4-sim-5 unchanged by the owner's ruling of 2026-10-27): a COST POLICY for spending the production gate's
budget — not a significance result, not a gate verdict, not an authorisation of anything, and never a scientific impossibility. The
p threshold p_max_go = 0.20 is an engineering cost threshold on the sign test's p, NOT the alpha of a formal scientific test.

    b4_gonogo.py decide <batch_dir> [--out-dir evidence/b4/gonogo/<label>_<UTC>]   # the decision record of an exploration archive (runs nothing)
    b4_gonogo.py verify <gonogo_dir>                                                # the record re-decided from its evidence in a fresh process

THE POLICY (b4_thresholds.THRESHOLDS["gonogo"]): precondition — a complete batch of exactly S = 32 planned pairs, every pair complete,
the archive verifying clean under this method version (else NO DECISION: stop and report); statistic 1 — the one-sided exact sign
test on Ω − R at the budget B_go = 64 (ties excluded from n and counted; the harness's own record of it), positives > negatives and
p ≤ p_max_go = 0.20 (a cost threshold, not an α); statistic 2 — K9's seven JUDGED conditional medians all ≥ 0.50; GO iff both; NO-GO otherwise. Every budget's Ω − R
record is carried in full; no other budget is picked afterwards. A `formal` record needs a production exploration label (b4-sim-<n>);
a mechanics fixture batch is decided with `formal = false` and a standing that says NOT A DECISION OF RECORD.

WHAT A GO MEANS: that the fixed certificate grouping with the fixed operator showed a positive signal on this task at one budget, and
that the conditional coverage was not below threshold — a proxy (Ω is not the upper bound over maps and operators), good enough to spend
the gate's cost; NOT a prediction of the gate and NOT an authorisation of its execution. A NO-GO stops; what follows needs its own
argument and ruling (no automatic successor).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_gate as bg  # noqa: E402
import b4_k9 as k9  # noqa: E402
import b4_protocol as bp  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim as sim  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_sim_verify as sv  # noqa: E402
import b4_thresholds as th  # noqa: E402

GONOGO_REL = "evidence/b4/gonogo"
SCHEMA = ("b4_gonogo_decision", "1.0.0")
DECISION_JSON, DECISION_MD = "gonogo.json", "gonogo.md"
DECISIONS = ("go", "no-go", "no_decision")
POLICY = th.THRESHOLDS["gonogo"]
EXPLORATION_LABEL_RE = sim.LABEL_RE
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
STANDING_FORMAL = ("the engineering go / no-go policy of docs/b4_architecture.md section 9.4 applied to an exploration archive: a cost policy for spending the "
                   "production gate's budget — not a significance result, not a gate verdict, not an authorisation of any execution; a go is a proxy signal at one "
                   "budget, not a prediction of the gate; a no-go stops and what follows needs its own ruling (no automatic successor)")
STANDING_NOT_FORMAL = ("NOT A DECISION OF RECORD: the policy applied to {kind} evidence under the label {label!r} so that the tool's paths are exercised; "
                       "a decision of record needs a production exploration archive (b4-sim-<n>)")


class Refusal(Exception):
    """A refusal before anything is written."""


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def formal_reasons(report: dict) -> list[str]:
    r: list[str] = []
    if report.get("fixture") is not False:
        r.append("a fixture batch")
    if not (isinstance(report.get("label"), str) and EXPLORATION_LABEL_RE.match(report["label"])):
        r.append(f"the label {report.get('label')!r} is not a production exploration label")
    return r


def decide(report: dict) -> dict:
    """The decision from a sim_report-like document (status, label, fixture, count, pairs, summary). Pure; total on a validated report."""
    T = POLICY
    idf = bg.doc_identity_findings(report)
    out = {"label": report.get("label") if isinstance(report, dict) else None, "S": report.get("count") if isinstance(report, dict) else None,
           "fixture": report.get("fixture") if isinstance(report, dict) else None, "batch_status": report.get("status") if isinstance(report, dict) else None,
           "policy": dict(T), "formal": False, "formal_reasons": [], "contract_findings": [], "precondition": {}, "statistic_1": None, "statistic_2": None,
           "omega_minus_R_by_budget": None, "decision": "no_decision", "reason": ""}
    if idf:
        out["contract_findings"] = idf
        out["formal_reasons"] = ["the document's identity fields break the contract"]
        out["reason"] = "no decision: the document's identity fields break the contract: " + "; ".join(idf[:3])
        return out
    out["formal_reasons"] = formal_reasons(report)
    out["formal"] = not out["formal_reasons"]
    pre = {"status_complete": report["status"] == "complete", "S_is_32": report["count"] == T["S"],
           "every_pair_complete": isinstance(report.get("pairs"), list) and len(report["pairs"]) == report["count"] and all(isinstance(p, dict) and p.get("status") == "complete" for p in report["pairs"]),
           "summary_present": isinstance(report.get("summary"), dict)}
    out["precondition"] = pre
    if not all(pre.values()):
        failed = [k for k, v in pre.items() if not v]
        out["reason"] = f"no decision: the precondition is not met ({', '.join(failed)}); the batch is {report['status']} with S = {report['count']} — stop and report"
        return out
    cf = bg.summary_contract_findings(report["summary"], report["count"])
    if cf:
        out["contract_findings"] = cf
        out["reason"] = "no decision: the summary breaks its contract: " + "; ".join(cf[:3])
        return out
    s = report["summary"]
    pb = s["per_budget"]
    B = T["B_go"]
    out["omega_minus_R_by_budget"] = {str(b): dict(pb[str(b)]["deltas"]["Omega_minus_R"]) for b in th.GRID}
    om = pb[str(B)]["deltas"]["Omega_minus_R"]
    pos_ok = om["positives"] > om["negatives"]
    p_ok = _num(om["sign_test_p"]) and om["sign_test_p"] <= T["p_max_go"]
    out["statistic_1"] = {"budget": B, "positives": om["positives"], "negatives": om["negatives"], "ties": om["ties"], "sign_test_p": om["sign_test_p"], "mean": om["mean"],
                          "cohen_d": om["cohen_d"], "positives_gt_negatives": pos_ok, "p_le_p_max_go": p_ok, "p_max_go": T["p_max_go"],
                          "p_max_go_standing": T["p_max_go_standing"]}
    med = {sem: s["k9"]["per_semantic"][sem]["median_coverage_over_all_S"] for sem in k9.SEMANTICS}
    k9_ok = all(_num(m) and m >= T["k9_conditional_medians_min"] for m in med.values())
    out["statistic_2"] = {"judged_estimand": s["k9"]["judged_estimand"], "conditional_medians": med, "all_ge_min": k9_ok, "min": T["k9_conditional_medians_min"],
                          "all_panel_medians_descriptive": {sem: s["k9"]["per_semantic_all_panel"][sem]["median_coverage_over_all_S"] for sem in k9.SEMANTICS}}
    if pos_ok and p_ok and k9_ok:
        out["decision"] = "go"
        out["reason"] = (f"go: at B = {B} Omega - R has {om['positives']} positives > {om['negatives']} negatives with one-sided sign-test p = {om['sign_test_p']:.4g} <= {T['p_max_go']} (a cost threshold, not an alpha), "
                         f"and every judged conditional K9 median >= {T['k9_conditional_medians_min']} — a cost policy met, not a gate result and not an authorisation")
    else:
        why = []
        if not pos_ok:
            why.append(f"at B = {B} positives {om['positives']} are not more than negatives {om['negatives']}")
        if not p_ok:
            why.append(f"at B = {B} the one-sided sign-test p {om['sign_test_p']!r} > the cost threshold p_max_go {T['p_max_go']}")
        if not k9_ok:
            below = [f"{sem} {m!r}" for sem, m in med.items() if not (_num(m) and m >= T["k9_conditional_medians_min"])]
            why.append("judged conditional K9 medians below 0.50 or not assessable: " + ", ".join(below))
        out["decision"] = "no-go"
        out["reason"] = "no-go: " + "; ".join(why) + " — the exploration is archived as a result; what follows needs its own ruling (no automatic successor)"
    return out


DECISION_KEYS = {"schema", "schema_version", "generated_utc", "head", "clean_tree", "label", "S", "fixture", "formal", "formal_reasons", "standing", "batch", "identity", "policy",
                 "precondition", "statistic_1", "statistic_2", "omega_minus_R_by_budget", "decision", "reason", "contract_findings", "self_validation", "files"}
BATCH_KEYS = {"path", "status", "label", "count", "fixture", "head", "generated_utc", "sha256", "seeds_sha256", "manifest_sha256"}


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def batch_path_ok(path, label: str) -> bool:
    """The publication contract of the evidence path: EXACTLY `evidence/b4/sim/<label>_<rest>` — relative, plain (normpath is itself),
    four components, none empty or `.` / `..`, the last named after the label (the owner's review of 04385ae R5)."""
    if not isinstance(path, str) or not path or path.startswith("/") or os.path.normpath(path) != path:
        return False
    parts = path.split("/")
    return len(parts) == 4 and parts[:3] == sim.SIM_REL.split("/") and all(x and x not in (".", "..") for x in parts) and parts[3].startswith(label + "_")


def decision_findings(doc) -> list[str]:
    f: list[str] = []
    if not isinstance(doc, dict) or set(doc) != DECISION_KEYS:
        return [f"gonogo record: keys {sorted(set(doc) ^ DECISION_KEYS) if isinstance(doc, dict) else 'not an object'} differ from the schema's"]
    nf = bg.numeric_findings(doc, "gonogo record")
    if nf:
        return nf[:20]
    if doc["schema"] != SCHEMA[0] or doc["schema_version"] != SCHEMA[1]:
        f.append("schema / schema_version")
    if not (isinstance(doc["head"], str) and HEX40.match(doc["head"])) or not isinstance(doc["clean_tree"], bool):
        f.append("head / clean_tree")
    if not (isinstance(doc["label"], str) and bs.LABEL_RE.match(doc["label"])) or not (isinstance(doc["S"], int) and not isinstance(doc["S"], bool) and doc["S"] > 0) or not isinstance(doc["fixture"], bool):
        f.append("label / S / fixture")
    if not isinstance(doc["formal"], bool) or not (isinstance(doc["formal_reasons"], list) and all(isinstance(x, str) for x in doc["formal_reasons"])):
        f.append("formal / formal_reasons")
    elif doc["formal"] is not (doc["formal_reasons"] == []):
        f.append("formal is true exactly when there is no reason against it")
    elif doc["formal"] and (doc["fixture"] or not EXPLORATION_LABEL_RE.match(doc["label"])):
        f.append("a decision of record is a production exploration archive's")
    if not isinstance(doc["standing"], str) or (doc["formal"] is False and "NOT A DECISION OF RECORD" not in doc["standing"]) or (doc["formal"] is True and "NOT A DECISION OF RECORD" in doc["standing"]):
        f.append("standing")
    b = doc["batch"]
    if not (isinstance(b, dict) and set(b) == BATCH_KEYS and b["status"] in sc.STATUSES and b["label"] == doc["label"]
            and _int(b["count"]) and b["count"] == doc["S"] and isinstance(b["fixture"], bool) and b["fixture"] is doc["fixture"]        # type-exact: 1.0 is not 1, 1 is not true (R5)
            and isinstance(b["head"], str) and HEX40.match(b["head"]) and isinstance(b["generated_utc"], str)
            and all(isinstance(b[k], str) and HEX64.match(b[k]) for k in ("sha256", "seeds_sha256", "manifest_sha256"))):
        f.append("batch: the evidence record (exact types)")
    elif not batch_path_ok(b["path"], doc["label"]):
        f.append(f"batch.path: not a direct archive path {sim.SIM_REL}/{doc['label']}_… written plainly (no absolute path, no `..`, no extra component)")
    ident = doc["identity"]
    if not (isinstance(ident, dict) and set(ident) == {"protocol_sha256", "architecture_revision", "policy_source"} and isinstance(ident["protocol_sha256"], str) and HEX64.match(ident["protocol_sha256"])
            and isinstance(ident["architecture_revision"], str) and ident["policy_source"] == th.THRESHOLDS["source"]):
        f.append("identity")
    if sc.canonical(doc["policy"]) != sc.canonical(POLICY):
        f.append("policy: not the table's")
    if doc["decision"] not in DECISIONS or not isinstance(doc["reason"], str) or not isinstance(doc["precondition"], dict):
        f.append("decision / reason / precondition")
    if doc["decision"] != "no_decision" and not (isinstance(doc["statistic_1"], dict) and isinstance(doc["statistic_2"], dict) and isinstance(doc["omega_minus_R_by_budget"], dict)):
        f.append("a decision carries both statistics and every budget's record")
    if doc["decision"] == "no_decision" and (doc["statistic_1"] is not None or doc["statistic_2"] is not None):
        f.append("no decision carries no statistic")
    if not (isinstance(doc["contract_findings"], list) and all(isinstance(x, str) for x in doc["contract_findings"])):
        f.append("contract_findings")
    if not (isinstance(doc["self_validation"], dict) and all(isinstance(v, list) for v in doc["self_validation"].values())):
        f.append("self_validation")
    elif doc["self_validation"] != {} and doc["decision"] != "no_decision":
        f.append("a record with self-validation findings is no decision")
    fe = doc["files"]
    if not (isinstance(fe, list) and [e.get("path") if isinstance(e, dict) else None for e in fe] == [DECISION_MD] and all(set(e) == {"path", "sha256", "size"} for e in fe)):
        f.append("files: the markdown rendering only")
    return f


def render_md(doc: dict) -> str:
    L = [f"# B4 go / no-go — {doc['label']} — **{doc['decision']}** ({'OF RECORD' if doc['formal'] else 'NOT A DECISION OF RECORD'})", "",
         f"Generated {doc['generated_utc']} at HEAD `{doc['head']}` (clean tree: {doc['clean_tree']}). Evidence `{doc['batch']['path']}` (status {doc['batch']['status']}, label {doc['batch']['label']}, "
         f"S = {doc['batch']['count']}, fixture {doc['batch']['fixture']}, sha256 `{doc['batch']['sha256']}`; batch HEAD `{doc['batch']['head']}`). Protocol identity `{doc['identity']['protocol_sha256']}`.", "",
         f"**Standing.** {doc['standing']}", "", f"**Policy.** {bg._j(doc['policy'])}", "", f"## Decision: **{doc['decision']}** — {doc['reason']}", "",
         "## Precondition", "", "```json", json.dumps(doc["precondition"], indent=1, sort_keys=True), "```", ""]
    if doc["statistic_1"] is not None:
        L += ["## Statistic 1 — Ω − R at B_go", "", "```json", json.dumps(doc["statistic_1"], indent=1, sort_keys=True, allow_nan=False), "```", "",
              "## Statistic 2 — K9 judged conditional medians", "", "```json", json.dumps(doc["statistic_2"], indent=1, sort_keys=True, allow_nan=False), "```", "",
              "## Ω − R at every budget (descriptive; no other budget is picked)", "", "```json", json.dumps(doc["omega_minus_R_by_budget"], indent=1, sort_keys=True, allow_nan=False), "```", ""]
    if doc["contract_findings"]:
        L += ["## Contract findings", ""] + [f"- {x}" for x in doc["contract_findings"]] + [""]
    L += ["Self-validation and the file index are in `gonogo.json`; `b4_gonogo.py verify` re-decides this record from its evidence.", ""]
    return "\n".join(L)


def _create(root: Path, out_p: Path) -> None:
    for i in range(1, len(Path(GONOGO_REL).parts) + 1):
        anc = root.joinpath(*Path(GONOGO_REL).parts[:i])
        if anc.is_symlink():
            raise Refusal(f"{anc.relative_to(root)} is a symlink")
        anc.mkdir(exist_ok=True)
    out_p.mkdir(exist_ok=False)


def write_decision(root: Path, batch_dir: Path, out_dir: Path | None = None) -> dict:
    """The decision record of an exploration archive into a new directory under evidence/b4/gonogo/ (exclusive; the verifier in process first)."""
    root = Path(root).resolve()
    batch_dir = Path(batch_dir)
    batch_dir = batch_dir if batch_dir.is_absolute() else root / batch_dir
    try:
        rel = str(batch_dir.resolve().relative_to(root))
    except ValueError:
        return {"status": "refused", "exit_code": 2, "gonogo_out": None, "reason": f"the batch directory {batch_dir} is not under the root {root}"}
    if not rel.startswith(sim.SIM_REL + "/") or rel.count("/") != 3 or not batch_dir.is_dir():
        return {"status": "refused", "exit_code": 2, "gonogo_out": None, "reason": f"the batch directory must lie directly under {sim.SIM_REL}/ of the root; got {rel}"}
    rp = batch_dir / "sim_report.json"
    if not rp.is_file():
        return {"status": "refused", "exit_code": 2, "gonogo_out": None, "reason": f"{rel} carries no sim_report.json"}
    raw = rp.read_bytes()
    try:
        report = json.loads(raw)
    except ValueError as exc:
        return {"status": "refused", "exit_code": 2, "gonogo_out": None, "reason": f"{rel}/sim_report.json is not JSON: {exc}"}
    pf = bg.archive_identity_findings(batch_dir)                       # FIRST: an archive of another method version (or none) is never decided by this tool
    if pf:
        return {"status": "refused", "exit_code": 2, "gonogo_out": None, "reason": f"{rel}: " + "; ".join(pf[:2])}
    rf = bg.numeric_findings(report, "sim_report") or sc.report_findings(report)
    if rf:
        return {"status": "refused", "exit_code": 2, "gonogo_out": None, "reason": f"{rel}/sim_report.json does not validate: " + "; ".join(rf[:4])}
    label = report["label"]
    if not (EXPLORATION_LABEL_RE.match(label) or sim.FIXTURE_LABEL_RE.match(label)):
        return {"status": "refused", "exit_code": 2, "gonogo_out": None, "reason": f"the batch's label {label!r} is neither an exploration label nor a mechanics fixture label: a gate archive is not decided by this policy"}
    if not batch_dir.name.startswith(label + "_"):
        return {"status": "refused", "exit_code": 2, "gonogo_out": None, "reason": f"the batch directory {batch_dir.name!r} is not named after its report's label {label!r}"}
    stamp = utc().replace("-", "").replace(":", "")
    out_p = Path(out_dir) if out_dir is not None else root / GONOGO_REL / f"{label}_{stamp}"
    out_p = out_p if out_p.is_absolute() else root / out_p
    if Path(os.path.normpath(out_p)) != out_p or out_p.parent != root / GONOGO_REL or not out_p.name.startswith(label + "_") or out_p.exists() or out_p.is_symlink():
        return {"status": "refused", "exit_code": 2, "gonogo_out": None, "reason": f"the gonogo directory must be a new directory directly under {GONOGO_REL}/ named {label}_…; got {out_p}"}
    protocol = bp.identity()
    head, clean = bg._tree_state(root, rel)
    d = decide(report)
    doc = {"schema": SCHEMA[0], "schema_version": SCHEMA[1], "generated_utc": utc(), "head": head, "clean_tree": clean, "label": d["label"], "S": d["S"], "fixture": d["fixture"],
           "formal": d["formal"], "formal_reasons": d["formal_reasons"],
           "standing": STANDING_FORMAL if d["formal"] else STANDING_NOT_FORMAL.format(kind="batch_archive", label=d["label"]),
           "batch": {"path": rel, "status": report["status"], "label": report["label"], "count": report["count"], "fixture": report["fixture"], "head": report["head"],
                     "generated_utc": report["generated_utc"], "sha256": _sha(raw), "seeds_sha256": _sha((batch_dir / "seeds.json").read_bytes()), "manifest_sha256": _sha((batch_dir / "manifest.json").read_bytes())},
           "identity": {"protocol_sha256": bp.protocol_sha256(protocol), "architecture_revision": protocol["architecture_revision"], "policy_source": th.THRESHOLDS["source"]},
           "policy": d["policy"], "precondition": d["precondition"], "statistic_1": d["statistic_1"], "statistic_2": d["statistic_2"], "omega_minus_R_by_budget": d["omega_minus_R_by_budget"],
           "decision": d["decision"], "reason": d["reason"], "contract_findings": d["contract_findings"], "self_validation": {}, "files": []}
    try:
        _create(root, out_p)
    except (Refusal, FileExistsError) as exc:
        return {"status": "refused", "exit_code": 2, "gonogo_out": None, "reason": str(exc)}
    doc["files"] = [{"path": DECISION_MD, "sha256": "0" * 64, "size": 0}]
    try:
        svf = verify_gonogo_dir(out_p, doc=doc, root=root, deep=True, check_md=False)
    except Exception as exc:  # noqa: BLE001
        svf = {"verifier": [f"the verifier raised {type(exc).__name__}: {exc}"]}
    if svf:
        doc["self_validation"] = svf
        doc["decision"], doc["statistic_1"], doc["statistic_2"] = "no_decision", None, None
        doc["reason"] = f"no decision: the record does not verify against its evidence: {next(iter(svf.items()))[0]}: {next(iter(svf.items()))[1][0]}"
    md = render_md(doc).encode("utf-8")
    doc["files"] = [bg._write_bytes_exclusive(out_p / DECISION_MD, md)]
    f = decision_findings(doc)
    if f:
        (out_p / "gonogo.ERROR.txt").write_text("gonogo.json does not validate: " + "; ".join(f) + "\n")
        return {"status": "invalid", "exit_code": 1, "gonogo_out": str(out_p), "report": doc, "report_error": f}
    sim.write_exclusive(out_p / DECISION_JSON, doc, None)
    code = {"go": 0, "no-go": 0, "no_decision": 3}[doc["decision"]]
    return {"status": doc["decision"], "exit_code": code, "gonogo_out": str(out_p), "report": doc}


def verify_gonogo_dir(gdir: Path, doc: dict | None = None, root: Path | None = None, deep: bool = True, check_md: bool = True) -> dict:
    """{location: [findings]}: the directory's shape, the record's validator, the identity, the evidence binding (digests, identity), the batch
    archive re-verified (deep), the decision recomputed and held to the record, the markdown re-rendered."""
    F: dict[str, list[str]] = {}

    def add(where, *m):
        if m:
            F.setdefault(where, []).extend(m)
    gdir = Path(gdir)
    if not gdir.is_dir():
        add("gonogo directory", "does not exist"); return F
    gdir = gdir.resolve()
    root = Path(root).resolve() if root is not None else gdir.parents[3]
    try:
        rel = gdir.relative_to(root)
    except ValueError:
        add("gonogo directory", f"not under the root {root}"); return F
    if str(rel.parent) != GONOGO_REL:
        add("gonogo directory", f"lies at {rel}, not directly under {GONOGO_REL}/"); return F
    disk = {p.name: p for p in sorted(gdir.iterdir()) if p.is_file() and not p.is_symlink()}
    for sub in sorted(gdir.iterdir()):                                  # the directory's ENTRIES, not only its files: no subdirectory, no symlink, no unfinished write (R5)
        if sub.is_symlink() or not sub.is_file():
            add(sub.name, "a gonogo directory holds its two files only: no subdirectory, no symlink")
        elif sub.name.endswith(".part"):
            add(sub.name, "an unfinished write")
    from_disk = doc is None
    if from_disk:
        if DECISION_JSON not in disk:
            add(DECISION_JSON, "missing"); return F
        try:
            doc = json.loads(disk[DECISION_JSON].read_bytes())
        except ValueError as exc:
            add(DECISION_JSON, f"not JSON: {exc}"); return F
    f = decision_findings(doc)
    if f:
        add(DECISION_JSON, *f); return F
    expected = {DECISION_MD} | ({DECISION_JSON} if from_disk else set())
    if not check_md:
        expected.discard(DECISION_MD)
    for name in sorted(set(disk) - expected):
        add(name, "not a file of a gonogo directory")
    for name in sorted(expected - set(disk)):
        add(name, "missing")
    if not gdir.name.startswith(doc["label"] + "_"):
        add("gonogo directory", "its name does not begin with the decided label")
    try:
        mine = bp.protocol_sha256(bp.identity())
    except bp.IdentityRefusal as exc:
        add("protocol", f"this tool's own tree is not its inventory: {exc}"); return F
    if doc["identity"]["protocol_sha256"] != mine:
        add("protocol", "the record's protocol identity is not this tool's — re-verify it with its own tool at its recorded HEAD (docs/b4_archive_reverification.md)"); return F
    if F:
        return F
    if check_md:
        e = doc["files"][0]
        b = disk[DECISION_MD].read_bytes()
        if _sha(b) != e["sha256"] or len(b) != e["size"]:
            add(DECISION_MD, "the file's digest / size are not the index's")
    b = doc["batch"]
    bdir = root / b["path"]
    if any(a.is_symlink() for a in sim.namespace_chain(root)) or bdir.is_symlink() or not bdir.is_dir() or bdir.resolve() != bdir:
        add("batch", f"the batch archive {b['path']} is not a real directory directly under {sim.SIM_REL}/ of the root {root} (missing, a symlink, or reached through one)"); return F
    try:
        rep = json.loads((bdir / "sim_report.json").read_bytes()); raw = (bdir / "sim_report.json").read_bytes()
    except (OSError, ValueError) as exc:
        add("batch", f"sim_report.json unreadable: {type(exc).__name__}: {exc}"); return F
    if _sha(raw) != b["sha256"]:
        add("batch", "sim_report.json does not hash to the recorded digest")
    for name, key in (("seeds.json", "seeds_sha256"), ("manifest.json", "manifest_sha256")):
        p = bdir / name
        if not p.is_file() or _sha(p.read_bytes()) != b[key]:
            add("batch", f"{name} does not hash to the recorded digest")
    rfs = sc.report_findings(rep)
    if rfs:
        add("batch", "sim_report.json does not validate: " + "; ".join(rfs[:3])); return F
    if sc.canonical([rep[k] for k in ("label", "count", "fixture", "status", "head", "generated_utc")]) != sc.canonical([b[k] for k in ("label", "count", "fixture", "status", "head", "generated_utc")]):
        add("batch", "the archive's identity is not the recorded one (exact in type)")
    add("batch: protocol", *bg.archive_identity_findings(bdir))
    if F:
        return F
    if deep:
        bf = sv.verify_run_dir(bdir, deep=True)
        for where, msgs in bf.items():
            add(f"batch: {where}", *msgs)
    d = decide(rep)
    for k in ("precondition", "statistic_1", "statistic_2", "omega_minus_R_by_budget", "contract_findings", "formal", "formal_reasons", "policy"):
        if sc.canonical(d[k]) != sc.canonical(doc[k]):
            add(DECISION_JSON, f"{k} is not the one recomputed from the evidence")
    if doc["self_validation"] != {}:
        add(DECISION_JSON, "the record recorded self-validation findings: its decision did not stand (never clean)")
    elif (d["decision"], d["reason"]) != (doc["decision"], doc["reason"]):
        add(DECISION_JSON, f"the decision {doc['decision']!r} is not the recomputed {d['decision']!r}")
    want_standing = STANDING_FORMAL if d["formal"] else STANDING_NOT_FORMAL.format(kind="batch_archive", label=d["label"])
    if doc["standing"] != want_standing:
        add(DECISION_JSON, "the standing is not the one of the recomputed formal flag")
    if check_md and disk[DECISION_MD].read_bytes() != render_md(doc).encode("utf-8"):
        add(DECISION_MD, "not the rendering of gonogo.json")
    return F


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="B4 engineering go / no-go policy (section 9.4): a cost policy, never a gate verdict or an authorisation.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decide"); d.add_argument("batch_dir"); d.add_argument("--out-dir", default=None)
    v = sub.add_parser("verify"); v.add_argument("gonogo_dir"); v.add_argument("--shallow", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "decide":
        rp = Path(a.batch_dir); rp = rp if rp.is_absolute() else REPO_ROOT / rp
        dirty = sim.porcelain(REPO_ROOT)
        if dirty:
            res = {"status": "refused", "exit_code": 2, "gonogo_out": None, "reason": f"the tree is not clean ({len(dirty)} entries); there is no override"}
        else:
            res = write_decision(REPO_ROOT, rp, Path(a.out_dir) if a.out_dir else None)
        print(json.dumps({k: v for k, v in res.items() if k in ("status", "exit_code", "gonogo_out", "reason", "report_error")}, indent=1))
        return res["exit_code"]
    try:
        f = verify_gonogo_dir(Path(a.gonogo_dir), deep=not a.shallow)
    except Exception as exc:  # noqa: BLE001
        f = {"verifier": [f"the verifier raised {type(exc).__name__}: {exc}"]}
    print(json.dumps({"gonogo_dir": a.gonogo_dir, "findings": f, "clean": not f, "limit": "a clean verification shows the record follows from its evidence under the fixed policy; a go is not a gate result and not an authorisation"}, indent=1))
    return 0 if not f else 1


if __name__ == "__main__":
    sys.exit(main())
