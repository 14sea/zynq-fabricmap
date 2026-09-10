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
              its standing qualification chain re-verified by host/b1_qualification.verify —
              it certifies the B1 carrier's history; it does NOT qualify this manifest), the
              map (canonical-JSON digest AND file-byte digest), the universe, the engine
              constants, the B2 code pins, the session seeds (with the archived sets excluded).
  S1 freeze   the owner writes the preregistration's sha256 and marks the image board_ready
              (the image pinned from its build evidence). From here the manifest is the
              document a B2Q ruling binds to.
  S2 qualify  the B2Q session ran against manifest_at_run (a copy in its evidence dir).
              Pinning its record is licensed ONLY if the current manifest equals
              manifest_at_run outside TRANSITION_KEYS. The record carries the MEASURED
              all-self-reporting rate; pinning writes it into `calibration` in the same step.
  S3 plan     the B2 plan (host/b2_plan.py) is generated FROM the calibration (the session
              split and deadlines) and pinned; the plan's rate must equal the calibration's
              and its split must equal session_split(pairs, budget, rate). This is the only
              plan edit the qualification licenses; it is checked, not trusted.
  binding     the B2 ruling pair binds to the manifest's sha256 AFTER S3. verify() refuses
              any later change of the image, prereg, map, lineage, seeds, pins or plan.

Every step is re-verified from scratch by `verify()` (used by every later tool): it never
reads a flag, it recomputes. The B2 adjudicator does not exist yet (it comes with the
image, B1's pattern), so re-adjudication of the B2Q evidence is a pluggable step
(`readjudicate=`): without it `qualified` is False and verify() says why.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_qualification as b1q  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402

SCHEMA = "b2_manifest"
SCHEMA_VERSION = "0.1.0"
MANIFEST = REPO_ROOT / "manifests/b2_manifest.json"
B1_MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"
B2_VARIANT = "0x42310001"
QUAL_SCHEMA = "b2_image_qualification"
QUAL_SESSION = "B2Q"
MANIFEST_AT_RUN = "manifest_at_run.json"
QUAL_EVIDENCE_FILES = ("run_log.json", "adjudication.json", MANIFEST_AT_RUN)
# the ONLY keys the B2Q qualification licenses to change between manifest_at_run and now
TRANSITION_KEYS = (("qualification",), ("qualified",), ("calibration",), ("plan",), ("status",), ("history",))   # history: the append-only log of these transitions
PINNED_CODE = ("host/b2_landscape.py", "host/b2_maps.py", "host/b2_search.py", "host/b2_gate.py", "host/b2_plan.py", "host/b2_manifest.py",
               "schemas/self_map_v2.schema.json", "docs/b2_architecture.md")


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


# ------------------------------------------------------------------ S0


def carrier_lineage(root: Path = REPO_ROOT, b1_manifest: Path = B1_MANIFEST, verify_chain: bool = True) -> dict:
    """The B1 carrier's history: the B1 manifest by hash, its carrier record, and whether its
    standing qualification chain re-verifies NOW. It certifies the carrier's history under
    the B1 manifest; it qualifies nothing about this manifest."""
    m1 = json.loads(b1_manifest.read_text())
    car = m1["carrier"]
    chain = None
    if verify_chain:
        try:
            chain = b1q.verify(m1, root=root)
            chain_ok = True
        except b1q.QualificationRefusal as exc:
            chain, chain_ok = {"refusal": str(exc)}, False
    else:
        chain_ok = None
    return {"b1_manifest": {"path": str(b1_manifest.relative_to(root)) if b1_manifest.is_relative_to(root) else str(b1_manifest), "sha256": sha256_file(b1_manifest)},
            "bitstream": car["bitstream"], "bitstream_sha256": car["bitstream_sha256"], "variant": car["variant"],
            "b1_qualification_record_sha256": canonical_sha256(car.get("qualification")) if car.get("qualification") else None,
            "b1_chain_verified_now": chain_ok, "b1_chain": chain,
            "note": "the B1 evidence certifies the carrier's history under the B1 manifest; it does not qualify this manifest — "
                    "the B2 image needs its own B2Q session (S2)"}


def init(image_evidence: Path | None, root: Path = REPO_ROOT, b1_manifest: Path = B1_MANIFEST, verify_chain: bool = True,
         gate_report: Path | None = None) -> dict:
    gate = json.loads((gate_report or bp.GATE_REPORT).read_text())
    fid = gate["selected_fitness"]
    res = gate["results"][fid]
    self_map = bmaps.load_self_map()
    excl, sources = bp.frozen_seed_exclusion()
    master = bs.master_seed(bp.SESSION_LABEL, bp.INSTRUMENT_COMMIT)
    seeds = bs.pair_seeds(master, res["criteria"]["G5"]["required_pairs_N"], exclude=excl)
    image = {"path": None, "sha256": None, "elf_sha256": None, "bytes": None, "build_evidence": None, "board_ready": False,
             "note": "no B2 image exists yet; pinned from its build evidence when built; board_ready is the owner's mark at the freeze"}
    if image_evidence is not None:
        ev = json.loads(Path(image_evidence).read_text())
        im = ev["image"]
        image.update({"path": im["path"], "sha256": im["sha256"], "elf_sha256": im.get("elf_sha256"), "bytes": im.get("bytes"),
                      "build_evidence": {"path": str(image_evidence), "sha256": sha256_file(Path(image_evidence))}})
    return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION,
            "status": "S0 INIT — derived from the tree; not frozen; no image; no qualification; no plan; NO BOARD RULING",
            "instrument": {"psoracle_commit": bp.INSTRUMENT_COMMIT},
            "carrier_lineage": carrier_lineage(root, b1_manifest, verify_chain),
            "carrier": {"bitstream_sha256": json.loads(b1_manifest.read_text())["carrier"]["bitstream_sha256"], "variant": B2_VARIANT},
            "prereg": {"path": "docs/b2_preregistration.md", "sha256": None, "frozen": False},
            "image": image,
            "map": {"path": str(bmaps.SELF_MAP.relative_to(root)), "canonical_json_sha256": bmaps.sha256_of(self_map),
                    "file_sha256": sha256_file(bmaps.SELF_MAP), "cartographer": self_map["cartographer"],
                    "note": "two digests, two encodings: canonical JSON (sorted keys, no spaces) and the file bytes; the IDENT carries the canonical one"},
            "universe": {"addresses": 292, "sha256": self_map["binding"]["universe_sha256"]},
            "experiment": {"fitness": fid, "budget_per_arm": res["b_star"], "pairs": res["criteria"]["G5"]["required_pairs_N"],
                           "engine": {"version": bs.ENGINE_VERSION, "mu": bs.MU, "lambda": bs.LAMBDA, "kmax": bs.KMAX},
                           "gate": {"path": str((gate_report or bp.GATE_REPORT).relative_to(root)), "sha256": sha256_file(gate_report or bp.GATE_REPORT),
                                    "rules_version": gate["thresholds"]["rules_version"]}},
            "audit": {"policy": bp.AUDIT_POLICY, "note": "every record's readout served and host-verified (the owner's decision of 2026-09-10)"},
            "seeds": {"label": bp.SESSION_LABEL, "master_seed": master, "pairs": seeds, "excluded_frozen_sets": sources,
                      "rule": "first 4 bytes of sha256(label|instrument commit); archived seed sets explicitly excluded"},
            "pins": {p: sha256_file(root / p) for p in PINNED_CODE if (root / p).is_file()},
            "qualification": None, "qualified": False, "calibration": None, "plan": None,
            "rulings_binding": {"B2Q": ["session=B2Q", "image_sha256", "prereg_sha256", "b2_manifest_sha256 (manifest_at_run: the S1 manifest)"],
                                "B2": ["session=B2", "master_seed", "image_sha256", "prereg_sha256", "b2_manifest_sha256 (the S3 manifest)"]},
            "history": []}


# ------------------------------------------------------------------ S1


def freeze(manifest: dict, prereg_sha256: str) -> dict:
    if manifest.get("image", {}).get("sha256") is None:
        raise Refusal("freeze: no image pinned (S0 with --image-evidence first)")
    if manifest.get("qualification") is not None or manifest.get("plan") is not None:
        raise Refusal("freeze: the manifest already carries a qualification or a plan; a freeze is the first transition")
    manifest["prereg"]["sha256"] = prereg_sha256
    manifest["prereg"]["frozen"] = True
    manifest["image"]["board_ready"] = True
    manifest["status"] = "S1 FROZEN — prereg pinned, image board_ready by the owner; awaiting the B2Q ruling pair"
    manifest["history"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "transition": "S1 freeze", "prereg_sha256": prereg_sha256})
    return manifest


# ------------------------------------------------------------------ S2


def make_qualification_record(evidence_dir: Path, measured_rate_per_hour: float | None = None) -> dict:
    """The B2Q record as the B2Q runner would write it beside its evidence: files by hash,
    the binding read from manifest_at_run, the adjudication's outcome, the measured rate."""
    ev = Path(evidence_dir)
    files = {n: (sha256_file(ev / n) if (ev / n).is_file() else None) for n in QUAL_EVIDENCE_FILES}
    m_run = json.loads((ev / MANIFEST_AT_RUN).read_text())
    adj = json.loads((ev / "adjudication.json").read_text())
    rate = measured_rate_per_hour if measured_rate_per_hour is not None else adj.get("measured_rate_per_hour")
    return {"schema": QUAL_SCHEMA, "schema_version": "1.0.0", "session": QUAL_SESSION, "evidence_dir": str(ev), "files": files,
            "outcome": adj.get("outcome"), "measured_rate_per_hour": rate, "audit_policy": adj.get("audit_policy"),
            "binding": {"session": QUAL_SESSION, "image_sha256": m_run["image"]["sha256"], "prereg_sha256": m_run["prereg"]["sha256"],
                        "carrier_sha256": m_run["carrier"]["bitstream_sha256"], "carrier_variant": m_run["carrier"]["variant"],
                        "map_canonical_json_sha256": m_run["map"]["canonical_json_sha256"],
                        "b2_manifest_sha256": sha256_file(ev / MANIFEST_AT_RUN)}}


def qualify(manifest: dict, evidence_dir: Path, readjudicate=None) -> dict:
    rec = make_qualification_record(evidence_dir)
    candidate = copy.deepcopy(manifest)
    candidate["qualification"] = rec
    if rec["measured_rate_per_hour"] is None:
        raise Refusal("qualify: the B2Q adjudication carries no measured all-self-reporting rate")
    candidate["calibration"] = {"rate_per_hour": rec["measured_rate_per_hour"], "audit_policy": rec["audit_policy"],
                                "source": "the B2Q record (qualification.files) — the only source a B2 plan may be sized from"}
    candidate["status"] = "S2 QUALIFIED — the B2Q record pinned, the calibration written from it; awaiting the plan (S3)"
    result = verify(candidate, evidence_dir=evidence_dir, readjudicate=readjudicate)
    candidate["qualified"] = result["qualified"]
    if not candidate["qualified"]:
        raise Refusal(f"qualify: the record does not qualify this manifest: {result['refusal']}")
    candidate["history"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "transition": "S2 qualify",
                                 "manifest_at_run_sha256": rec["binding"]["b2_manifest_sha256"], "rate_per_hour": rec["measured_rate_per_hour"]})
    return candidate


# ------------------------------------------------------------------ S3


def pin_plan(manifest: dict, plan_path: Path, root: Path = REPO_ROOT) -> dict:
    if not manifest.get("qualified"):
        raise Refusal("plan: the manifest is not qualified (S2 first)")
    if manifest.get("plan") is not None:
        raise Refusal("plan: a plan is already pinned; a new plan needs a new preregistration")
    plan = json.loads(Path(plan_path).read_text())
    cal = manifest["calibration"]
    ex = manifest["experiment"]
    split = plan.get("session_split") or {}
    want = bp.session_split(ex["pairs"], ex["budget_per_arm"], cal["rate_per_hour"])
    if split.get("status") != "DETERMINED" or split.get("rate_per_hour") != cal["rate_per_hour"]:
        raise Refusal("plan: the plan's split is not DETERMINED from the manifest's calibration rate")
    if split.get("sessions") != want["sessions"] or split.get("pairs_per_session_max") != want["pairs_per_session_max"]:
        raise Refusal("plan: the plan's split is not session_split(pairs, budget, calibration rate)")
    if plan.get("fitness") != ex["fitness"] or plan.get("budget_per_arm") != ex["budget_per_arm"] or plan.get("pairs") != ex["pairs"]:
        raise Refusal("plan: the plan's fitness / budget / pairs differ from the manifest's experiment")
    if plan.get("seed_derivation", {}).get("master_seed") != manifest["seeds"]["master_seed"]:
        raise Refusal("plan: the plan's master seed differs from the manifest's")
    candidate = copy.deepcopy(manifest)
    rel = str(Path(plan_path).relative_to(root)) if Path(plan_path).is_relative_to(root) else str(plan_path)
    candidate["plan"] = {"path": rel, "sha256": sha256_file(Path(plan_path)), "prediction_sha256": plan.get("prediction_sha256"),
                         "sessions": len(want["sessions"]), "total_records": want["total_records"]}
    candidate["status"] = "S3 PLANNED — the plan pinned from the calibration; the B2 ruling pair binds to THIS manifest's sha256"
    candidate["history"].append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "transition": "S3 plan", "plan_sha256": candidate["plan"]["sha256"]})
    return candidate


# ------------------------------------------------------------------ verify (recomputes everything; never trusts a flag)


def verify(manifest: dict, evidence_dir: Path | None = None, readjudicate=None, root: Path = REPO_ROOT) -> dict:
    """Returns {stage, qualified, refusal, checks}; raises Refusal on a manifest that contradicts
    itself (a later change the lifecycle does not license)."""
    checks: dict[str, bool | str] = {}
    if manifest.get("schema") != SCHEMA:
        raise Refusal("not a b2_manifest")
    # S0 invariants (the tree may have moved on; the pins say so — a moved pin is a refusal once frozen)
    pin_drift = {p: h for p, h in (manifest.get("pins") or {}).items() if (root / p).is_file() and sha256_file(root / p) != h}
    checks["pins_drifted"] = sorted(pin_drift)
    lineage = manifest.get("carrier_lineage") or {}
    checks["lineage_b1_manifest_hash"] = (root / lineage["b1_manifest"]["path"]).is_file() and sha256_file(root / lineage["b1_manifest"]["path"]) == lineage["b1_manifest"]["sha256"] \
        if lineage.get("b1_manifest") and not Path(lineage["b1_manifest"]["path"]).is_absolute() else False
    checks["lineage_bitstream_matches_carrier"] = lineage.get("bitstream_sha256") == (manifest.get("carrier") or {}).get("bitstream_sha256")
    checks["lineage_b1_chain_verified"] = lineage.get("b1_chain_verified_now") is True
    stage = "S0"
    frozen = bool((manifest.get("prereg") or {}).get("frozen"))
    if frozen:
        stage = "S1"
        if not manifest["prereg"].get("sha256") or not (manifest.get("image") or {}).get("sha256") or not manifest["image"].get("board_ready"):
            raise Refusal("S1: frozen without a prereg hash, an image or board_ready")
        if pin_drift:
            raise Refusal(f"S1: pinned files changed after the freeze: {sorted(pin_drift)}")
    qualified = False
    refusal = None
    q = manifest.get("qualification")
    if q is not None:
        stage = "S2"
        if not frozen:
            raise Refusal("S2: a qualification on an unfrozen manifest")
        ev = Path(evidence_dir) if evidence_dir else Path(q["evidence_dir"])
        try:
            if q.get("schema") != QUAL_SCHEMA or q.get("session") != QUAL_SESSION:
                raise Refusal("the record is not a B2Q image qualification")
            for n, h in q["files"].items():
                if h is None or not (ev / n).is_file() or sha256_file(ev / n) != h:
                    raise Refusal(f"evidence file {n} absent or not hashing to the record")
            m_run = json.loads((ev / MANIFEST_AT_RUN).read_text())
            if sha256_file(ev / MANIFEST_AT_RUN) != q["binding"]["b2_manifest_sha256"]:
                raise Refusal("manifest_at_run does not hash to the record's binding")
            b = q["binding"]
            if b["image_sha256"] != manifest["image"]["sha256"] or b["prereg_sha256"] != manifest["prereg"]["sha256"] \
                    or b["carrier_sha256"] != manifest["carrier"]["bitstream_sha256"] or b["carrier_variant"] != manifest["carrier"]["variant"] \
                    or b["map_canonical_json_sha256"] != manifest["map"]["canonical_json_sha256"]:
                raise Refusal("the record's binding (image / prereg / carrier / map) is not this manifest's")
            if q.get("outcome") != "PASS":
                raise Refusal(f"the stored B2Q adjudication is {q.get('outcome')!r}, not PASS")
            if _strip(m_run) != _strip(manifest):
                raise Refusal("the current manifest differs from manifest_at_run in more than the qualification, calibration, plan and status: "
                              "the image was qualified for another manifest")
            cal = manifest.get("calibration")
            if not cal or cal.get("rate_per_hour") != q.get("measured_rate_per_hour"):
                raise Refusal("the calibration is absent or is not the B2Q record's measured rate")
            if readjudicate is None:
                raise Refusal("no B2Q re-adjudicator available (it comes with the image): the evidence cannot be re-adjudicated now")
            res = readjudicate(ev, m_run)
            if res.get("outcome") != "PASS":
                raise Refusal(f"the pinned B2Q evidence re-adjudicates to {res.get('outcome')!r}, not PASS")
            qualified = True
        except Refusal as exc:
            refusal = str(exc)
        if manifest.get("qualified") and not qualified:
            raise Refusal(f"the manifest's qualified flag disagrees with its evidence: {refusal}")
    if manifest.get("plan") is not None:
        stage = "S3"
        if not qualified:
            raise Refusal(f"S3: a plan on a manifest that is not qualified ({refusal})")
        pl = manifest["plan"]
        p = root / pl["path"]
        if not p.is_file() or sha256_file(p) != pl["sha256"]:
            raise Refusal("S3: the pinned plan file is absent or changed")
        plan = json.loads(p.read_text())
        want = bp.session_split(manifest["experiment"]["pairs"], manifest["experiment"]["budget_per_arm"], manifest["calibration"]["rate_per_hour"])
        if (plan.get("session_split") or {}).get("sessions") != want["sessions"]:
            raise Refusal("S3: the pinned plan's split is not the calibration's")
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
    ap.add_argument("--no-chain-verify", action="store_true", help="init only: skip the B1 chain re-verification (recorded as unverified)")
    a = ap.parse_args(argv)
    if a.command == "init":
        m = init(a.image_evidence, verify_chain=not a.no_chain_verify)
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
