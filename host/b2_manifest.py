#!/usr/bin/env python3
"""B2 — the manifest and its qualification / calibration / plan lifecycle (host-only).

    b2_manifest.py init      [--manifest M] [--image-evidence E]
    b2_manifest.py freeze    --manifest M --prereg-sha256 H            (the owner)
    b2_manifest.py qualify   --manifest M --evidence-dir D             (pin the B2Q record + the measured rate)
    b2_manifest.py plan      --manifest M --plan P                     (pin the plan derived from the calibration)
    b2_manifest.py verify    --manifest M [--evidence-dir D]

The lifecycle the owner's review of 2026-09-10 asked to be specified and exercised on disk
(docs/b2_preregistration.md §6, §8), with B1's strict transition rule kept — not relaxed:

  S0 init     derived fields from the tree: the carrier LINEAGE (the B1 manifest by hash and
              its standing qualification chain — it certifies the B1 carrier's history; it
              does NOT qualify this manifest), the map (canonical-JSON digest AND file-byte
              digest), the universe, the engine constants, the B2 code pins, the session
              seeds (with the archived sets excluded), the image from its build evidence.
  S1 freeze   the owner writes the preregistration's sha256 and marks the image board_ready.
  S2 qualify  the B2Q session ran against manifest_at_run (a copy in its evidence dir).
              Pinning its record is licensed ONLY if the current manifest equals
              manifest_at_run outside TRANSITION_KEYS. The record is RECONSTRUCTED from the
              evidence files, never taken from the caller; the measured rate and policy go
              into `calibration` in the same step, from that reconstruction.
  S3 plan     the B2 plan (host/b2_plan.py) is generated FROM the calibration and pinned;
              ONE validator (`plan_findings`) — used at pinning and at every later verify —
              derives every operational field of the plan and of its prediction from the
              frozen experiment, the exact seed sequence, the map, the engine, the policy
              and the verified calibration; only generation time and planning-rate notes
              are non-operational.
  binding     the B2 ruling pair binds to the manifest's sha256 AFTER S3.

`verify()` recomputes EVERYTHING it can from live bytes and refuses on any disagreement
(v0.2.1, after the owner's second review, `docs/b2_b3_host_review_v02_2026_09_10.md`):
  * every required pin exists on disk and hashes to the manifest (a missing file is a
    refusal, never filtered out); the preregistration bytes (once frozen), the map in both
    encodings, the image build evidence file and the image it names;
  * the lineage: the B1 manifest file hashes to the pin, its carrier is this carrier, and its
    qualification chain is re-verified FRESH by host/b1_qualification.verify against the B1
    evidence tree (never a stored flag);
  * the qualification: the record's schema and EXACT file set, every file hashing, the
    record reconstructed from the evidence and compared field by field, the re-adjudication
    agreeing on outcome / rate / policy with the evidence, the policy equal to the frozen
    audit policy, the calibration equal to the reconstruction, the rate finite, positive
    and FEASIBLE under the split rule;
  * the plan: `plan_findings` on the pinned file and its prediction file.
The B2 adjudicator does not exist yet (it comes with the image), so re-adjudication is a
pluggable step (`readjudicate=`): without it a manifest cannot be qualified, and a manifest
that claims to be is a contradiction (a refusal).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_model as bmodel  # noqa: E402
import b1_qualification as b1q  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402

SCHEMA = "b2_manifest"
SCHEMA_VERSION = "0.2.1"
MANIFEST = REPO_ROOT / "manifests/b2_manifest.json"
B1_MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"
B2_VARIANT = "0x42310001"
QUAL_SCHEMA = "b2_image_qualification"
QUAL_SCHEMA_VERSION = "1.1.0"
QUAL_SESSION = "B2Q"
MANIFEST_AT_RUN = "manifest_at_run.json"
QUAL_EVIDENCE_FILES = ("run_log.json", "adjudication.json", MANIFEST_AT_RUN)          # the EXACT set a record must carry
QUAL_RECORD_KEYS = ("schema", "schema_version", "session", "evidence_dir", "files", "outcome", "measured_rate_per_hour", "audit_policy", "binding")
QUAL_BINDING_KEYS = ("session", "image_sha256", "prereg_sha256", "carrier_sha256", "carrier_variant", "map_canonical_json_sha256", "b2_manifest_sha256")
# the ONLY keys the B2Q qualification licenses to change between manifest_at_run and now
TRANSITION_KEYS = (("qualification",), ("qualified",), ("calibration",), ("plan",), ("status",), ("history",))   # history: the append-only log of these transitions
PINNED_CODE = ("host/b2_landscape.py", "host/b2_maps.py", "host/b2_search.py", "host/b2_gate.py", "host/b2_plan.py", "host/b2_manifest.py",
               "schemas/self_map_v2.schema.json", "docs/b2_architecture.md")
PLAN_NON_OPERATIONAL = ("generated_utc", "planning_rates_NOT_calibration", "carrier", "gate", "architecture", "prediction_sha256", "deadline_formula")


class Refusal(Exception):
    pass


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def canonical_sha256(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def manifest_sha256(manifest: dict) -> str:
    """The hash of the manifest AS A FILE would be (indent 1, sorted keys, trailing newline) —
    what a ruling and a qualification record bind to."""
    return hashlib.sha256(render(manifest).encode()).hexdigest()


def render(manifest: dict) -> str:
    return json.dumps(manifest, indent=1, sort_keys=True) + "\n"


def _strip(m: dict) -> dict:
    m = copy.deepcopy(m)
    for path in TRANSITION_KEYS:
        d = m
        for k in path[:-1]:
            d = d.get(k) or {}
        d.pop(path[-1], None)
    return m


def _resolve(rel: str, root: Path) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else root / rel


def _finite_positive(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


# ------------------------------------------------------------------ S0


def carrier_lineage(root: Path = REPO_ROOT, b1_manifest: Path = B1_MANIFEST, b1_root: Path = REPO_ROOT) -> dict:
    """The B1 carrier's history: the B1 manifest by hash and its carrier record. Whether the
    B1 qualification chain verifies is NOT stored as a fact — verify() re-runs it fresh."""
    m1 = json.loads(b1_manifest.read_text())
    car = m1["carrier"]
    return {"b1_manifest": {"path": str(b1_manifest.relative_to(root)) if b1_manifest.is_relative_to(root) else str(b1_manifest), "sha256": sha256_file(b1_manifest)},
            "bitstream": car["bitstream"], "bitstream_sha256": car["bitstream_sha256"], "variant": car["variant"],
            "b1_qualification_record_sha256": canonical_sha256(car.get("qualification")) if car.get("qualification") else None,
            "note": "the B1 evidence certifies the carrier's history under the B1 manifest and is re-verified FRESH by every verify(); "
                    "it does not qualify this manifest — the B2 image needs its own B2Q session (S2)"}


def init(image_evidence: Path | None, root: Path = REPO_ROOT, b1_manifest: Path = B1_MANIFEST, gate_report: Path | None = None) -> dict:
    gate_path = gate_report or bp.GATE_REPORT
    gate = json.loads(gate_path.read_text())
    fid = gate["selected_fitness"]
    res = gate["results"][fid]
    self_map = bmaps.load_self_map()
    excl, sources = bp.frozen_seed_exclusion()
    master = bs.master_seed(bp.SESSION_LABEL, bp.INSTRUMENT_COMMIT)
    seeds = bs.pair_seeds(master, res["criteria"]["G5"]["required_pairs_N"], exclude=excl)
    image = {"path": None, "sha256": None, "elf_sha256": None, "bytes": None, "build_evidence": None, "board_ready": False,
             "note": "no B2 image exists yet; pinned from its build evidence when built; board_ready is the owner's mark at the freeze"}
    if image_evidence is not None:
        evp = Path(image_evidence)
        ev = json.loads(evp.read_text())
        im = ev["image"]
        image.update({"path": im["path"], "sha256": im["sha256"], "elf_sha256": im.get("elf_sha256"), "bytes": im.get("bytes"),
                      "build_evidence": {"path": str(evp.relative_to(root)) if evp.is_relative_to(root) else str(evp), "sha256": sha256_file(evp)}})
    m = {"schema": SCHEMA, "schema_version": SCHEMA_VERSION,
         "status": "S0 INIT — derived from the tree; not frozen; no qualification; no plan; NO BOARD RULING",
         "instrument": {"psoracle_commit": bp.INSTRUMENT_COMMIT},
         "carrier_lineage": carrier_lineage(root, b1_manifest),
         "carrier": {"bitstream_sha256": json.loads(b1_manifest.read_text())["carrier"]["bitstream_sha256"], "variant": B2_VARIANT},
         "prereg": {"path": "docs/b2_preregistration.md", "sha256": None, "frozen": False},
         "image": image,
         "map": {"path": str(bmaps.SELF_MAP.relative_to(root)), "canonical_json_sha256": bmaps.sha256_of(self_map),
                 "file_sha256": sha256_file(bmaps.SELF_MAP), "cartographer": self_map["cartographer"],
                 "note": "two digests, two encodings: canonical JSON (sorted keys, no spaces) and the file bytes; the IDENT carries the canonical one"},
         "universe": {"addresses": 292, "sha256": self_map["binding"]["universe_sha256"]},
         "experiment": {"fitness": fid, "budget_per_arm": res["b_star"], "pairs": res["criteria"]["G5"]["required_pairs_N"],
                        "engine": {"version": bs.ENGINE_VERSION, "mu": bs.MU, "lambda": bs.LAMBDA, "kmax": bs.KMAX},
                        "gate": {"path": str(gate_path.relative_to(root)) if gate_path.is_relative_to(root) else str(gate_path), "sha256": sha256_file(gate_path),
                                 "rules_version": gate["thresholds"]["rules_version"]}},
         "audit": {"policy": bp.AUDIT_POLICY, "note": "every record's readout served and host-verified (the owner's decision of 2026-09-10)"},
         "seeds": {"label": bp.SESSION_LABEL, "master_seed": master, "pairs": seeds, "excluded_frozen_sets": sources,
                   "rule": "first 4 bytes of sha256(label|instrument commit); archived seed sets explicitly excluded"},
         "pins": {p: sha256_file(root / p) for p in PINNED_CODE},
         "qualification": None, "qualified": False, "calibration": None, "plan": None,
         "rulings_binding": {"B2Q": ["session=B2Q", "image_sha256", "prereg_sha256", "b2_manifest_sha256 (manifest_at_run: the S1 manifest)"],
                             "B2": ["session=B2", "master_seed", "image_sha256", "prereg_sha256", "b2_manifest_sha256 (the S3 manifest)"]},
         "history": []}
    return m


# ------------------------------------------------------------------ S1


def freeze(manifest: dict, prereg_sha256: str, root: Path = REPO_ROOT) -> dict:
    if manifest.get("image", {}).get("sha256") is None:
        raise Refusal("freeze: no image pinned (S0 with --image-evidence first)")
    if manifest.get("qualification") is not None or manifest.get("plan") is not None or manifest.get("prereg", {}).get("frozen"):
        raise Refusal("freeze: the manifest already carries a freeze, a qualification or a plan; a freeze is the first transition")
    prereg = _resolve(manifest["prereg"]["path"], root)
    if not prereg.is_file() or sha256_file(prereg) != prereg_sha256:
        raise Refusal("freeze: the given preregistration sha256 is not the hash of the preregistration file on disk")
    manifest["prereg"]["sha256"] = prereg_sha256
    manifest["prereg"]["frozen"] = True
    manifest["image"]["board_ready"] = True
    manifest["status"] = "S1 FROZEN — prereg pinned, image board_ready by the owner; awaiting the B2Q ruling pair"
    manifest["history"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "transition": "S1 freeze", "prereg_sha256": prereg_sha256})
    return manifest


# ------------------------------------------------------------------ S2


def read_adjudication(ev: Path) -> dict:
    """The B2Q adjudication file, validated: outcome, session, a finite positive measured
    all-self-reporting rate, the audit policy."""
    p = ev / "adjudication.json"
    if not p.is_file():
        raise Refusal("adjudication.json is absent")
    adj = json.loads(p.read_text())
    for k in ("outcome", "session", "measured_rate_per_hour", "audit_policy"):
        if k not in adj:
            raise Refusal(f"adjudication.json lacks {k}")
    if adj["session"] != QUAL_SESSION:
        raise Refusal(f"adjudication.json names session {adj['session']!r}, not {QUAL_SESSION}")
    if not _finite_positive(adj["measured_rate_per_hour"]):
        raise Refusal("adjudication.json: the measured rate is not a finite positive number")
    return adj


def reconstruct_qualification_record(evidence_dir: Path) -> dict:
    """The B2Q record as the B2Q runner writes it beside its evidence — RECONSTRUCTED from
    the files, every time: files by hash (the exact set), the binding read from
    manifest_at_run, the outcome / rate / policy from the adjudication."""
    ev = Path(evidence_dir)
    files = {}
    for n in QUAL_EVIDENCE_FILES:
        if not (ev / n).is_file():
            raise Refusal(f"evidence file {n} is absent")
        files[n] = sha256_file(ev / n)
    m_run = json.loads((ev / MANIFEST_AT_RUN).read_text())
    adj = read_adjudication(ev)
    return {"schema": QUAL_SCHEMA, "schema_version": QUAL_SCHEMA_VERSION, "session": QUAL_SESSION, "evidence_dir": str(ev), "files": files,
            "outcome": adj["outcome"], "measured_rate_per_hour": adj["measured_rate_per_hour"], "audit_policy": adj["audit_policy"],
            "binding": {"session": QUAL_SESSION, "image_sha256": m_run["image"]["sha256"], "prereg_sha256": m_run["prereg"]["sha256"],
                        "carrier_sha256": m_run["carrier"]["bitstream_sha256"], "carrier_variant": m_run["carrier"]["variant"],
                        "map_canonical_json_sha256": m_run["map"]["canonical_json_sha256"],
                        "b2_manifest_sha256": files[MANIFEST_AT_RUN]}}


make_qualification_record = reconstruct_qualification_record


def calibration_from(record: dict, manifest: dict) -> dict:
    rate = record["measured_rate_per_hour"]
    split = bp.session_split(manifest["experiment"]["pairs"], manifest["experiment"]["budget_per_arm"], rate)
    if split["status"] != "DETERMINED":
        raise Refusal(f"the measured rate {rate} /h is INFEASIBLE under the split rule: no whole pair fits the {bp.SESSION_SPAN_MAX_S} s expected span")
    return {"rate_per_hour": rate, "audit_policy": record["audit_policy"],
            "source": "reconstructed from the B2Q evidence (adjudication.json) — the only source a B2 plan may be sized from",
            "sessions": len(split["sessions"]), "pairs_per_session_max": split["pairs_per_session_max"]}


def qualify(manifest: dict, evidence_dir: Path, readjudicate=None, root: Path = REPO_ROOT, b1_root: Path = REPO_ROOT) -> dict:
    ev = Path(evidence_dir)
    rec = reconstruct_qualification_record(ev)
    candidate = copy.deepcopy(manifest)
    candidate["qualification"] = rec
    candidate["calibration"] = calibration_from(rec, candidate)
    candidate["status"] = "S2 QUALIFIED — the B2Q record reconstructed from its evidence and pinned, the calibration written from it; awaiting the plan (S3)"
    candidate["qualified"] = True
    result = verify(candidate, evidence_dir=ev, readjudicate=readjudicate, root=root, b1_root=b1_root)
    if not result["qualified"]:
        raise Refusal(f"qualify: the record does not qualify this manifest: {result['refusal']}")
    candidate["history"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "transition": "S2 qualify",
                                 "manifest_at_run_sha256": rec["binding"]["b2_manifest_sha256"], "rate_per_hour": rec["measured_rate_per_hour"]})
    return candidate


# ------------------------------------------------------------------ S3: one validator for pinning and verification


def plan_findings(manifest: dict, plan_path: Path, root: Path = REPO_ROOT) -> list[str]:
    """Every operational field of the plan and its prediction derived from the frozen
    experiment, the exact seed sequence, the map, the engine, the audit policy and the
    verified calibration. Returns the list of disagreements (empty = the plan is THE plan)."""
    f: list[str] = []
    p = _resolve(str(plan_path), root)
    if not p.is_file():
        return [f"plan file {plan_path} is absent"]
    plan = json.loads(p.read_text())
    ex = manifest["experiment"]
    cal = manifest.get("calibration") or {}
    if plan.get("schema") != "b2_plan":
        f.append("not a b2_plan")
    if plan.get("fitness") != ex["fitness"] or plan.get("budget_per_arm") != ex["budget_per_arm"] or plan.get("pairs") != ex["pairs"]:
        f.append("fitness / budget / pairs differ from the manifest's experiment")
    if plan.get("engine") != ex["engine"]:
        f.append("engine constants differ from the manifest's")
    if (plan.get("map") or {}).get("sha256") != manifest["map"]["canonical_json_sha256"] or (plan.get("map") or {}).get("path") != manifest["map"]["path"]:
        f.append("the plan's map is not the manifest's map (canonical digest / path)")
    if plan.get("audit_policy") != manifest["audit"]["policy"]:
        f.append("the plan's audit policy is not the frozen one")
    sd = plan.get("seed_derivation") or {}
    if sd.get("master_seed") != manifest["seeds"]["master_seed"] or sd.get("label") != manifest["seeds"]["label"] or sd.get("commit") != manifest["instrument"]["psoracle_commit"]:
        f.append("the plan's seed derivation (master / label / commit) is not the manifest's")
    split = plan.get("session_split") or {}
    if not cal:
        f.append("no calibration in the manifest")
    else:
        want = bp.session_split(ex["pairs"], ex["budget_per_arm"], cal["rate_per_hour"])
        keys = ("status", "rate_per_hour", "pairs_per_session_max", "sessions", "total_records")
        if want["status"] != "DETERMINED":
            f.append("the calibration is infeasible under the split rule")
        elif any(split.get(k) != want.get(k) for k in keys):
            f.append("the plan's split is not session_split(pairs, budget, calibration rate)")
    if plan.get("session_span_max_s") != bp.SESSION_SPAN_MAX_S:
        f.append("the plan's session span limit is not the registered one")
    # the prediction file beside the plan: bound by hash and re-derived from the reference engine
    pred_path = p.parent / "prediction.json"
    if not pred_path.is_file():
        f.append("prediction.json is absent beside the plan")
        return f
    if plan.get("prediction_sha256") != sha256_file(pred_path):
        f.append("the plan's prediction digest is not the prediction file's hash")
    pred = json.loads(pred_path.read_text())
    if pred.get("fitness") != ex["fitness"] or pred.get("budget_per_arm") != ex["budget_per_arm"]:
        f.append("the prediction's fitness / budget differ from the manifest's experiment")
    want_seeds = [tuple(x) for x in manifest["seeds"]["pairs"]]
    got_seeds = [(x.get("landscape_seed"), x.get("operator_seed")) for x in pred.get("pairs", [])]
    if got_seeds != want_seeds:
        f.append("the prediction's seed sequence is not the manifest's")
        return f
    expected = bp.predict(ex["fitness"], ex["budget_per_arm"], want_seeds, manifest["map"]["canonical_json_sha256"])
    if expected["fitness_sequence_sha256"] != pred.get("fitness_sequence_sha256") or expected["deltas"] != pred.get("deltas"):
        f.append("the prediction is not the reference engine's for the frozen experiment, seeds and map")
    for a, b in zip(expected["pairs"], pred["pairs"]):
        if a["runs"] != b.get("runs") or a["arm_order"] != b.get("arm_order") or a["target"] != b.get("target"):
            f.append(f"pair {a['pair']}: runs / arm order / target differ from the reference")
            break
    return f


def pin_plan(manifest: dict, plan_path: Path, root: Path = REPO_ROOT, readjudicate=None, b1_root: Path = REPO_ROOT) -> dict:
    result = verify(manifest, readjudicate=readjudicate, root=root, b1_root=b1_root)      # never trust the input's flag
    if not result["qualified"]:
        raise Refusal(f"plan: the manifest is not qualified ({result['refusal']})")
    if manifest.get("plan") is not None:
        raise Refusal("plan: a plan is already pinned; a new plan needs a new preregistration")
    findings = plan_findings(manifest, plan_path, root)
    if findings:
        raise Refusal("plan: " + "; ".join(findings))
    p = _resolve(str(plan_path), root)
    plan = json.loads(p.read_text())
    candidate = copy.deepcopy(manifest)
    rel = str(p.relative_to(root)) if p.is_relative_to(root) else str(p)
    candidate["plan"] = {"path": rel, "sha256": sha256_file(p), "prediction_path": str(Path(rel).parent / "prediction.json"),
                         "prediction_sha256": sha256_file(p.parent / "prediction.json"),
                         "sessions": len(plan["session_split"]["sessions"]), "total_records": plan["session_split"]["total_records"]}
    candidate["status"] = "S3 PLANNED — the plan pinned from the calibration; the B2 ruling pair binds to THIS manifest's sha256"
    candidate["history"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "transition": "S3 plan", "plan_sha256": candidate["plan"]["sha256"]})
    verify(candidate, readjudicate=readjudicate, root=root, b1_root=b1_root)
    return candidate


# ------------------------------------------------------------------ verify (recomputes everything from live bytes; never trusts a flag)


def _check_frozen_inputs(manifest: dict, root: Path, b1_root: Path) -> dict:
    checks: dict = {}
    pins = manifest.get("pins") or {}
    missing = [p for p in PINNED_CODE if p not in pins]
    if missing:
        raise Refusal(f"pins: the manifest does not pin {missing}")
    absent = [p for p in PINNED_CODE if not (root / p).is_file()]
    if absent:
        raise Refusal(f"pins: pinned files absent from the tree: {absent}")
    drift = [p for p in PINNED_CODE if sha256_file(root / p) != pins[p]]
    if drift:
        raise Refusal(f"pins: pinned files changed: {drift}")
    checks["pins"] = "ok"
    # the map, both encodings
    mp = _resolve(manifest["map"]["path"], root)
    if not mp.is_file():
        raise Refusal("map: the map file is absent")
    if sha256_file(mp) != manifest["map"]["file_sha256"]:
        raise Refusal("map: the map file bytes changed")
    doc = json.loads(mp.read_text())
    if bmaps.sha256_of(doc) != manifest["map"]["canonical_json_sha256"]:
        raise Refusal("map: the map's canonical JSON digest changed")
    if bmaps.schema_findings(doc):
        raise Refusal("map: the map no longer validates under self_map 2.0.0")
    checks["map"] = "ok"
    # the preregistration, once frozen
    if manifest["prereg"].get("frozen"):
        pp = _resolve(manifest["prereg"]["path"], root)
        if not pp.is_file() or sha256_file(pp) != manifest["prereg"]["sha256"]:
            raise Refusal("prereg: the frozen preregistration file is absent or changed")
        checks["prereg"] = "ok"
    # the image and its build evidence
    im = manifest.get("image") or {}
    if im.get("sha256") is not None:
        be = im.get("build_evidence") or {}
        bep = _resolve(be.get("path", "MISSING"), root)
        if not bep.is_file() or sha256_file(bep) != be.get("sha256"):
            raise Refusal("image: the build evidence file is absent or changed")
        ev = json.loads(bep.read_text())
        if (ev.get("image") or {}).get("sha256") != im["sha256"] or (ev.get("image") or {}).get("path") != im.get("path"):
            raise Refusal("image: the build evidence does not name the pinned image")
        checks["image"] = "ok"
    # the lineage: the B1 manifest file by hash, the carrier, and the B1 chain re-verified FRESH
    lineage = manifest.get("carrier_lineage") or {}
    b1p = _resolve(lineage["b1_manifest"]["path"], root)
    if not b1p.is_file() or sha256_file(b1p) != lineage["b1_manifest"]["sha256"]:
        raise Refusal("lineage: the B1 manifest file is absent or changed")
    m1 = json.loads(b1p.read_text())
    if m1["carrier"]["bitstream_sha256"] != lineage["bitstream_sha256"] or lineage["bitstream_sha256"] != manifest["carrier"]["bitstream_sha256"] \
            or m1["carrier"]["variant"] != manifest["carrier"]["variant"]:
        raise Refusal("lineage: the B1 manifest's carrier is not this manifest's carrier")
    try:
        b1q.verify(m1, root=b1_root)
    except b1q.QualificationRefusal as exc:
        raise Refusal(f"lineage: the B1 qualification chain does not verify now: {exc}") from None
    checks["lineage"] = "ok (B1 chain re-verified)"
    return checks


def verify(manifest: dict, evidence_dir: Path | None = None, readjudicate=None, root: Path = REPO_ROOT, b1_root: Path = REPO_ROOT) -> dict:
    """Returns {stage, qualified, refusal, checks}; raises Refusal on a manifest that contradicts
    itself or its live inputs (a later change the lifecycle does not license)."""
    if manifest.get("schema") != SCHEMA:
        raise Refusal("not a b2_manifest")
    checks = _check_frozen_inputs(manifest, root, b1_root)
    stage = "S0"
    frozen = bool((manifest.get("prereg") or {}).get("frozen"))
    if frozen:
        stage = "S1"
        if not manifest["prereg"].get("sha256") or not (manifest.get("image") or {}).get("sha256") or not manifest["image"].get("board_ready"):
            raise Refusal("S1: frozen without a prereg hash, an image or board_ready")
    qualified = False
    refusal = None
    q = manifest.get("qualification")
    if q is not None:
        stage = "S2"
        if not frozen:
            raise Refusal("S2: a qualification on an unfrozen manifest")
        try:
            if not isinstance(q, dict) or [k for k in QUAL_RECORD_KEYS if k not in q]:
                raise Refusal("the record lacks required keys")
            if q.get("schema") != QUAL_SCHEMA or q.get("schema_version") != QUAL_SCHEMA_VERSION or q.get("session") != QUAL_SESSION:
                raise Refusal("the record is not a B2Q image qualification of the current schema")
            if sorted(q["files"]) != sorted(QUAL_EVIDENCE_FILES):
                raise Refusal(f"the record's file set is not exactly {list(QUAL_EVIDENCE_FILES)}")
            if not isinstance(q["binding"], dict) or sorted(q["binding"]) != sorted(QUAL_BINDING_KEYS):
                raise Refusal("the record's binding does not carry exactly the required keys")
            ev = Path(evidence_dir) if evidence_dir else Path(q["evidence_dir"])
            rebuilt = reconstruct_qualification_record(ev)
            for k in ("files", "outcome", "measured_rate_per_hour", "audit_policy", "binding"):
                if rebuilt[k] != q[k]:
                    raise Refusal(f"the record's {k} is not what the evidence gives")
            if q["outcome"] != "PASS":
                raise Refusal(f"the stored B2Q adjudication is {q['outcome']!r}, not PASS")
            m_run = json.loads((ev / MANIFEST_AT_RUN).read_text())
            b = q["binding"]
            if b["image_sha256"] != manifest["image"]["sha256"] or b["prereg_sha256"] != manifest["prereg"]["sha256"] \
                    or b["carrier_sha256"] != manifest["carrier"]["bitstream_sha256"] or b["carrier_variant"] != manifest["carrier"]["variant"] \
                    or b["map_canonical_json_sha256"] != manifest["map"]["canonical_json_sha256"]:
                raise Refusal("the record's binding (image / prereg / carrier / map) is not this manifest's")
            if _strip(m_run) != _strip(manifest):
                raise Refusal("the current manifest differs from manifest_at_run in more than the qualification, calibration, plan, status and history: "
                              "the image was qualified for another manifest")
            if m_run.get("qualification") is not None or m_run.get("plan") is not None:
                raise Refusal("manifest_at_run already carried a qualification or a plan: not the S1 manifest")
            if q["audit_policy"] != manifest["audit"]["policy"]:
                raise Refusal(f"the B2Q session's audit policy {q['audit_policy']!r} is not the frozen policy {manifest['audit']['policy']!r}")
            want_cal = calibration_from(rebuilt, manifest)
            cal = manifest.get("calibration") or {}
            if any(cal.get(k) != want_cal[k] for k in ("rate_per_hour", "audit_policy", "sessions", "pairs_per_session_max")):
                raise Refusal("the calibration is not the one derived from the evidence's measured rate under the split rule")
            if readjudicate is None:
                raise Refusal("no B2Q re-adjudicator available (it comes with the image): the evidence cannot be re-adjudicated now")
            res = readjudicate(ev, m_run) or {}
            if res.get("outcome") != "PASS":
                raise Refusal(f"the pinned B2Q evidence re-adjudicates to {res.get('outcome')!r}, not PASS")
            if res.get("measured_rate_per_hour") != rebuilt["measured_rate_per_hour"] or res.get("audit_policy") != rebuilt["audit_policy"]:
                raise Refusal("the re-adjudication's measured rate / audit policy disagree with the evidence's adjudication")
            qualified = True
        except Refusal as exc:
            refusal = str(exc)
        if manifest.get("qualified") and not qualified:
            raise Refusal(f"the manifest's qualified flag disagrees with its evidence: {refusal}")
        if qualified and not manifest.get("qualified"):
            raise Refusal("the manifest's evidence qualifies it but its flag says otherwise (refresh)")
    elif manifest.get("qualified") or manifest.get("calibration") is not None:
        raise Refusal("qualified / calibration without a qualification record")
    if manifest.get("plan") is not None:
        stage = "S3"
        if not qualified:
            raise Refusal(f"S3: a plan on a manifest that is not qualified ({refusal})")
        pl = manifest["plan"]
        p = _resolve(pl["path"], root)
        if not p.is_file() or sha256_file(p) != pl["sha256"]:
            raise Refusal("S3: the pinned plan file is absent or changed")
        pred = _resolve(pl.get("prediction_path", "MISSING"), root)
        if not pred.is_file() or sha256_file(pred) != pl.get("prediction_sha256"):
            raise Refusal("S3: the pinned prediction file is absent or changed")
        findings = plan_findings(manifest, p, root)
        if findings:
            raise Refusal("S3: " + "; ".join(findings))
        plan = json.loads(p.read_text())
        if pl.get("sessions") != len(plan["session_split"]["sessions"]) or pl.get("total_records") != plan["session_split"]["total_records"]:
            raise Refusal("S3: the manifest's plan summary is not the plan's")
    checks["stage"] = stage
    return {"stage": stage, "qualified": qualified, "refusal": refusal, "checks": checks, "manifest_sha256": manifest_sha256(manifest)}


# ------------------------------------------------------------------ CLI


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["init", "freeze", "qualify", "plan", "verify"])
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--image-evidence", type=Path, default=None)
    ap.add_argument("--prereg-sha256", default=None)
    ap.add_argument("--evidence-dir", type=Path, default=None)
    ap.add_argument("--plan", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.command == "init":
        m = init(a.image_evidence)
    else:
        m = json.loads(a.manifest.read_text())
        if a.command == "freeze":
            if not a.prereg_sha256:
                raise SystemExit("freeze needs --prereg-sha256 (the owner writes it)")
            m = freeze(m, a.prereg_sha256)
        elif a.command == "qualify":
            m = qualify(m, a.evidence_dir)           # no re-adjudicator on the CLI: refuses until the B2 adjudicator exists
        elif a.command == "plan":
            m = pin_plan(m, a.plan)
        elif a.command == "verify":
            print(json.dumps(verify(m, a.evidence_dir), indent=1, sort_keys=True))
            return 0
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(render(m))
    print(f"{a.command}: {a.manifest} ({manifest_sha256(m)[:12]}…) — {m['status']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        sys.exit(2)
