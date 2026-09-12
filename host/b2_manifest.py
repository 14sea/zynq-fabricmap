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
              REBUILDS the canonical plan and prediction from the frozen inputs
              (`b2_plan.build_plan` / `build_prediction`) and compares the WHOLE structures
              field for field; only `generated_utc` may differ, and `prediction_sha256` is
              instead tied to the sidecar's and the manifest's digests, which must name the
              same bytes (a relocated prediction is allowed only if it is that document).
  binding     the B2 ruling pair binds to the manifest's sha256 AFTER S3.

`verify()` recomputes EVERYTHING it can from live bytes and refuses on any disagreement
(v0.2.1, after the owner's second review, `docs/b2_b3_host_review_v02_2026_09_10.md`):
  * every required pin exists on disk and hashes to the manifest (a missing file is a
    refusal, never filtered out); the preregistration bytes (once frozen); the map in both
    encodings; the build evidence file AND the image binary itself — opened, hashed and
    sized against both the manifest and the build evidence (v0.2.2, the owner's third
    review: a declaration is not evidence that the binary exists);
  * the lineage: the B1 manifest file hashes to the pin, its carrier is this carrier, and its
    qualification chain is re-verified FRESH by host/b1_qualification.verify against the B1
    evidence tree (never a stored flag);
  * the qualification: the record's schema and EXACT file set, every file hashing, the
    record reconstructed from the evidence and compared field by field, the re-adjudication
    agreeing on outcome / rate / policy with the evidence, the policy equal to the frozen
    audit policy, the calibration equal to the reconstruction, the rate finite, positive
    and FEASIBLE under the split rule;
  * the plan: `plan_findings` on the pinned file and its prediction sidecar, and the
    manifest's prediction reference tied to that sidecar's bytes.
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
import b1_qualification as b1qual  # noqa: E402
import b1_qualification as b1q  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402

SCHEMA = "b2_manifest"
SCHEMA_VERSION = "0.2.5"          # 0.2.4 -> 0.2.5: B2Q's frozen experiment is a pinned input
MANIFEST = REPO_ROOT / "manifests/b2_manifest.json"
B1_MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"
B2_VARIANT = "0x42310001"
QUAL_SCHEMA = "b2_image_qualification"
QUAL_SCHEMA_VERSION = "1.2.0"          # 1.1.0 -> 1.2.0: the record pins the WHOLE evidence set
QUAL_SESSION = "B2Q"
MANIFEST_AT_RUN = "manifest_at_run.json"
# The EXACT set a record must carry. Until 1.1.0 this was three files, so the audits and the
# timeline a session verdict consumes — and the export seal, the raw console and the two rulings
# the session was authorised by — could all change without changing the reconstructed record
# (the owner's P2-2 of 2026-09-11). It is now B1's complete qualification evidence set, one
# definition for both stages.
QUAL_EVIDENCE_FILES = b1qual.EVIDENCE_FILES
QUAL_RECORD_KEYS = ("schema", "schema_version", "session", "evidence_dir", "files", "outcome", "measured_rate_per_hour", "audit_policy", "binding")
QUAL_BINDING_KEYS = ("session", "image_sha256", "prereg_sha256", "carrier_sha256", "carrier_variant", "map_canonical_json_sha256", "b2_manifest_sha256")
# the ONLY keys the B2Q qualification licenses to change between manifest_at_run and now
TRANSITION_KEYS = (("qualification",), ("qualified",), ("calibration",), ("plan",), ("status",), ("history",))   # history: the append-only log of these transitions
PINNED_CODE = ("host/b2_landscape.py", "host/b2_maps.py", "host/b2_search.py", "host/b2_gate.py", "host/b2_plan.py", "host/b2_manifest.py",
               "schemas/self_map_v2.schema.json", "docs/b2_architecture.md")
# The ONLY plan keys that may differ from the canonical rebuild. Everything else — schema,
# schema_version, session, fitness, budget, pairs, engine, carrier, map, seed derivation,
# gate provenance, audit policy, record accounting, arm order, session split, span limit,
# deadline formula, planning-rate notes, the primary statistic and its alpha / tie policy,
# the architecture pin — is OPERATIONAL and compared field for field (the owner's third
# review, finding 2). `prediction_sha256` is not compared as a value: it is tied to the
# sidecar's and the manifest's digests, which must all be the same bytes.
PLAN_NON_OPERATIONAL = ("generated_utc", "prediction_sha256")
PREDICTION_NON_OPERATIONAL = ()          # the prediction is compared in full


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


def qualification_plan_pin(manifest_seeds: list, fid: str, map_sha256: str, commit: str,
                           root: Path = REPO_ROOT) -> dict:
    """B2Q's frozen experiment, pinned by path and digest AND re-derived here, so the pinned bytes
    cannot drift from the rule that produced them. Recorded at S0 and frozen with the rest at S1,
    which is what makes the qualification reviewable BEFORE the session that calibrates from it
    (the owner's recommendation of 2026-09-11)."""
    rel_plan, rel_pred = "evidence/b2/b2q_plan.json", "evidence/b2/b2q_prediction.json"
    pp, qp = Path(root) / rel_plan, Path(root) / rel_pred
    for rel, path in ((rel_plan, pp), (rel_pred, qp)):
        if not path.is_file():
            raise Refusal(f"{rel} is absent: generate it with `python3 host/b2_plan.py --qualification`")
    plan, prediction = json.loads(pp.read_text()), json.loads(qp.read_text())
    want_plan = bp.build_qualification_plan(fid, map_sha256, commit, manifest_seeds)
    want_plan = {**want_plan, "prediction_sha256": canonical_sha256(prediction)}
    want_pred = bp.build_qualification_prediction(fid, map_sha256, commit, manifest_seeds)
    if _differences(plan, want_plan):
        raise Refusal(f"{rel_plan} is not the canonical B2Q plan: {_differences(plan, want_plan)[:3]}")
    if _differences(prediction, want_pred):
        raise Refusal(f"{rel_pred} is not the canonical B2Q prediction: "
                      f"{_differences(prediction, want_pred)[:3]}")
    return {"path": rel_plan, "sha256": sha256_file(pp), "prediction_path": rel_pred,
            "prediction_sha256": sha256_file(qp),
            "master_seed": plan["seed_derivation"]["master_seed"],
            "pairs": plan["seed_derivation"]["pairs"],
            "budget_per_arm": plan["budget_per_arm"], "records": plan["records"]["total"],
            "planning_bound": plan["planning_bound"]}


def instrument_pins_pin(root: Path = REPO_ROOT) -> dict:
    """The pin of the instrument pin TABLE: its path and its sha256."""
    rel = "manifests/b2_instrument_pins.json"
    p = Path(root) / rel
    if not p.is_file():
        raise Refusal(f"{rel} is absent: generate it with `python3 host/b2_pins.py --generate`")
    return {"path": rel, "sha256": sha256_file(p)}


def board_from_lineage(b1_manifest: Path = B1_MANIFEST) -> dict:
    """The intended board, from the B1 manifest the lineage pins. `boardid` is the authority the
    rulings are bound to; the rest is recorded so a reviewer can see what was scoped."""
    b = (json.loads(Path(b1_manifest).read_text()).get("board") or {})
    if not isinstance(b.get("boardid"), str) or not b["boardid"].strip():
        raise Refusal("the lineage's B1 manifest names no boardid: this stage has no board authority")
    return {k: b[k] for k in ("boardid", "role", "part", "idcode") if k in b}


def check_board(manifest: dict) -> str:
    """The frozen board authority. A manifest without one cannot authorise anything: absence is a
    refusal, never permission to skip the comparison."""
    b = manifest.get("board")
    if not isinstance(b, dict):
        raise Refusal("the manifest pins no board: this stage has no board authority")
    got = b.get("boardid")
    if not isinstance(got, str) or not got.strip():
        raise Refusal(f"the manifest's boardid {got!r} is not a non-empty string")
    return got


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
         # The board this stage is scoped to, taken from the VALIDATED lineage and never from a
         # ruling. Without it two rulings could agree on the wrong board and pass (the owner's
         # P2 of 2026-09-11); its absence is a refusal, not permission to skip the comparison.
         "board": board_from_lineage(b1_manifest),
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
         # The whole decision surface, by table (host/b2_pins.py). `pins` above is the eight
         # files this manifest's own derivations depend on; the table is everything a verdict
         # depends on, and is re-verified on every verify().
         "instrument_pins": instrument_pins_pin(root),
         "qualification_plan": qualification_plan_pin(seeds, fid, bmaps.sha256_of(self_map),
                                                      bp.INSTRUMENT_COMMIT, root),
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


def summary_findings(evidence_dir: Path) -> list[str]:
    """The completed session's FINAL summary, cross-checked against the evidence it closes.

    It is checked HERE and not inside the adjudication callback because `b1_session.run` persists
    `summary.json` AFTER the callback returns: requiring it inside would create a positive path
    that cannot exist. The ruling archives already exist before the callback and are rebound
    there; this is the post-finalisation boundary (the owner's P2-2 of 2026-09-11)."""
    ev = Path(evidence_dir)
    f: list[str] = []
    try:
        summary = json.loads((ev / "summary.json").read_text())
    except (OSError, ValueError) as exc:
        return [f"summary.json is not readable JSON: {exc}"]
    if not isinstance(summary, dict):
        return ["summary.json is not a JSON object"]
    try:
        adj = read_adjudication(ev)
    except Refusal as exc:
        return [f"summary.json cannot be cross-checked: {exc}"]
    if summary.get("outcome") != adj["outcome"]:
        f.append(f"summary.json's outcome {summary.get('outcome')!r} is not the adjudication's "
                 f"{adj['outcome']!r}")
    try:
        log = json.loads((ev / "run_log.json").read_text())
    except (OSError, ValueError) as exc:
        f.append(f"summary.json cannot be bound to the run log: {exc}")
        log = {}
    token = ((log.get("app_identity") or {}) if isinstance(log, dict) else {}).get("token")
    if token is not None and summary.get("token") != token:
        f.append("summary.json's token is not the session's")
    try:
        raw_whole, whole = b1qual.read_archived_ruling(ev / b1qual.RULING_FILES["whole_of_run"])
        raw_pk, _pk = b1qual.read_archived_ruling(ev / b1qual.RULING_FILES["provisioning"])
    except b1qual.QualificationRefusal as exc:
        return f + [f"summary.json cannot be bound to the archived rulings: {exc}"]
    if summary.get("ruling") != whole:
        f.append("summary.json's recorded ruling is not the archived whole-of-run ruling")
    want_pk = hashlib.sha256(raw_pk).hexdigest()
    if summary.get("provisioning_ruling_sha256") != want_pk:
        f.append(f"summary.json's provisioning_ruling_sha256 is not the archived provisioning "
                 f"ruling's bytes ({want_pk[:16]}…)")
    return f


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
    for name in b1qual.RULING_FILES.values():
        # An archive that never parsed must not be ACCEPTED here: recording its hash would
        # preserve the invalid declaration rather than catch it (the owner's P2-2 of 2026-09-11).
        try:
            b1qual.read_archived_ruling(ev / name)
        except b1qual.QualificationRefusal as exc:
            raise Refusal(f"the archived authorisation {name} is not a readable ruling archive: {exc}") from None
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


def _differences(got, want, path: str = "") -> list[str]:
    """Every path at which two JSON structures differ, deepest name first."""
    if isinstance(want, dict) and isinstance(got, dict):
        out = []
        for k in sorted(set(want) | set(got)):
            here = f"{path}.{k}" if path else k
            if k not in got:
                out.append(f"{here}: missing")
            elif k not in want:
                out.append(f"{here}: unexpected")
            else:
                out += _differences(got[k], want[k], here)
        return out
    if isinstance(want, list) and isinstance(got, list):
        if len(want) != len(got):
            return [f"{path}: {len(got)} entries, expected {len(want)}"]
        out = []
        for i, (g, w) in enumerate(zip(got, want)):
            out += _differences(g, w, f"{path}[{i}]")
        return out
    return [] if got == want else [f"{path or '(root)'}: {got!r} != {want!r}"]


def canonical_plan(manifest: dict, root: Path = REPO_ROOT) -> dict:
    """The plan the frozen manifest implies: built by `b2_plan.build_plan` from the gate the
    manifest pins and the calibration it carries."""
    gate = _resolve(manifest["experiment"]["gate"]["path"], root)
    if not gate.is_file() or sha256_file(gate) != manifest["experiment"]["gate"]["sha256"]:
        raise Refusal("the gate report the manifest pins is absent or changed")
    cal = manifest.get("calibration") or {}
    return bp.build_plan(cal.get("rate_per_hour"), gate, root=root)


def plan_findings(manifest: dict, plan_path: Path, root: Path = REPO_ROOT) -> list[str]:
    """The WHOLE operational plan and prediction, rebuilt from the frozen inputs and compared
    structure for structure (the owner's third review, finding 2). Only the keys of
    PLAN_NON_OPERATIONAL may differ; `prediction_sha256` is instead required to be the
    sidecar's actual digest, which the caller also ties to the manifest's reference."""
    f: list[str] = []
    p = _resolve(str(plan_path), root)
    if not p.is_file():
        return [f"plan file {plan_path} is absent"]
    try:
        plan = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        return [f"plan file {plan_path} is not JSON: {exc}"]
    if not isinstance(plan, dict):
        return ["the plan is not an object"]
    if not manifest.get("calibration"):
        return ["no calibration in the manifest: no plan can be derived"]
    try:
        want_plan = canonical_plan(manifest, root)
    except (Refusal, ValueError) as exc:
        return [f"the canonical plan cannot be built: {exc}"]
    if want_plan["session_split"]["status"] != "DETERMINED":
        f.append("the calibration is infeasible under the split rule")
    # the manifest's own experiment must be the gate's, or the plan is right about the wrong thing
    ex = manifest["experiment"]
    if (want_plan["fitness"], want_plan["budget_per_arm"], want_plan["pairs"]) != (ex["fitness"], ex["budget_per_arm"], ex["pairs"]):
        f.append("the manifest's experiment is not what the pinned gate selects")
    if want_plan["engine"] != ex["engine"]:
        f.append("the manifest's engine is not the reference engine")
    if want_plan["map"]["sha256"] != manifest["map"]["canonical_json_sha256"]:
        f.append("the manifest's map digest is not the map the plan is built from")
    if want_plan["audit_policy"] != manifest["audit"]["policy"]:
        f.append("the manifest's audit policy is not the plan's")
    if want_plan["seed_derivation"]["master_seed"] != manifest["seeds"]["master_seed"] \
            or [tuple(x) for x in manifest["seeds"]["pairs"]] != [tuple(x) for x in bp.session_seeds(want_plan["pairs"])[1]]:
        f.append("the manifest's seed sequence is not the frozen rule's")
    f += [f"plan {d}" for d in _differences({k: v for k, v in plan.items() if k not in PLAN_NON_OPERATIONAL},
                                            {k: v for k, v in want_plan.items() if k not in PLAN_NON_OPERATIONAL})]
    # the prediction sidecar: present, hashed by the plan, and equal to the canonical rebuild
    pred_path = p.parent / "prediction.json"
    if not pred_path.is_file():
        return f + ["prediction.json is absent beside the plan"]
    if plan.get("prediction_sha256") != sha256_file(pred_path):
        f.append("the plan's prediction digest is not the sidecar's hash")
    try:
        pred = json.loads(pred_path.read_text())
    except json.JSONDecodeError as exc:
        return f + [f"the prediction sidecar is not JSON: {exc}"]
    want_pred = bp.build_prediction(want_plan["fitness"], want_plan["budget_per_arm"],
                                    [tuple(x) for x in manifest["seeds"]["pairs"]], manifest["map"]["canonical_json_sha256"])
    f += [f"prediction {d}" for d in _differences({k: v for k, v in pred.items() if k not in PREDICTION_NON_OPERATIONAL},
                                                  {k: v for k, v in want_pred.items() if k not in PREDICTION_NON_OPERATIONAL})]
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
    pred = p.parent / "prediction.json"
    pred_rel = str(pred.relative_to(root)) if pred.is_relative_to(root) else str(pred)
    candidate["plan"] = {"path": rel, "sha256": sha256_file(p), "prediction_path": pred_rel,
                         "prediction_sha256": sha256_file(pred),
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
    # the image: its build evidence, AND the binary itself — opened, hashed and sized
    im = manifest.get("image") or {}
    if im.get("sha256") is not None:
        be = im.get("build_evidence") or {}
        bep = _resolve(be.get("path", "MISSING"), root)
        if not bep.is_file() or sha256_file(bep) != be.get("sha256"):
            raise Refusal("image: the build evidence file is absent or changed")
        ev_image = (json.loads(bep.read_text()).get("image") or {})
        if ev_image.get("sha256") != im["sha256"] or ev_image.get("path") != im.get("path"):
            raise Refusal("image: the build evidence does not name the pinned image")
        if im.get("bytes") is not None and ev_image.get("bytes") != im["bytes"]:
            raise Refusal("image: the build evidence's size is not the manifest's")
        ip = _resolve(im.get("path") or "MISSING", root)
        if not ip.is_file():
            raise Refusal(f"image: the image binary {im.get('path')!r} is absent — the declaration is not evidence that it exists")
        got, size = sha256_file(ip), ip.stat().st_size
        if got != im["sha256"]:
            raise Refusal("image: the image binary's bytes do not hash to the pinned sha256")
        for name, want in (("the manifest", im.get("bytes")), ("the build evidence", ev_image.get("bytes"))):
            if want is not None and size != want:
                raise Refusal(f"image: the image binary is {size} bytes, {name} says {want}")
        checks["image"] = f"ok (binary hashed: {got[:12]}…, {size} bytes)"
    # the lineage: the B1 manifest file by hash, the carrier, and the B1 chain re-verified FRESH
    lineage = manifest.get("carrier_lineage") or {}
    b1p = _resolve(lineage["b1_manifest"]["path"], root)
    if not b1p.is_file() or sha256_file(b1p) != lineage["b1_manifest"]["sha256"]:
        raise Refusal("lineage: the B1 manifest file is absent or changed")
    m1 = json.loads(b1p.read_text())
    if m1["carrier"]["bitstream_sha256"] != lineage["bitstream_sha256"] or lineage["bitstream_sha256"] != manifest["carrier"]["bitstream_sha256"] \
            or m1["carrier"]["variant"] != manifest["carrier"]["variant"]:
        raise Refusal("lineage: the B1 manifest's carrier is not this manifest's carrier")
    boardid = check_board(manifest)                      # present, well-formed — and the lineage's
    if boardid != (m1.get("board") or {}).get("boardid"):
        raise Refusal(f"board: the manifest is scoped to {boardid!r}, the validated lineage names "
                      f"{(m1.get('board') or {}).get('boardid')!r}")
    checks["board"] = boardid
    import b2_pins  # noqa: E402
    try:                                                 # the whole decision surface, by table
        checks["instrument_pins"] = b2_pins.verify(manifest, root=root, b1_root=b1_root)
    except b2_pins.PinRefusal as exc:
        raise Refusal(f"instrument pins: {exc}") from None
    # B2Q's frozen experiment: the pinned bytes, and the rule that produced them, on every call
    qp = manifest.get("qualification_plan")
    if not isinstance(qp, dict):
        raise Refusal("the manifest pins no B2Q qualification plan")
    rebuilt = qualification_plan_pin([tuple(x) for x in manifest["seeds"]["pairs"]],
                                     manifest["experiment"]["fitness"],
                                     manifest["map"]["canonical_json_sha256"],
                                     manifest["instrument"]["psoracle_commit"], root)
    diff = _differences(qp, rebuilt)
    if diff:
        raise Refusal(f"the pinned B2Q experiment is not the canonical one: {diff[:3]}")
    checks["qualification_plan"] = f"ok ({qp['records']} records at budget {qp['budget_per_arm']})"
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
            sf = summary_findings(ev)            # the post-finalisation boundary
            if sf:
                raise Refusal("the session's final summary does not close this evidence: " + "; ".join(sf[:3]))
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
        sidecar = p.parent / "prediction.json"
        if not sidecar.is_file():
            raise Refusal("S3: the plan has no prediction sidecar")
        if sha256_file(sidecar) != pl.get("prediction_sha256"):
            raise Refusal("S3: the manifest's prediction reference and the plan's sidecar are different bytes "
                          "(a relocated prediction is allowed only if it is the same document)")
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
