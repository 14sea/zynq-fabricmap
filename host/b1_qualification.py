#!/usr/bin/env python3
"""B1 — the carrier's QUALIFICATION as an evidence chain, not a flag (owner's review
2026-09-05, blocker 3).

A qualification RECORD (`qualification.json`, written beside the B1Q session's evidence by
b1q_runner after its adjudication) names: the session, the evidence directory and the
sha256 of every evidence file (run_log, audits, timeline, adjudication, summary), the
outcome, the ruling that authorised it, and the binding (carrier sha256 and variant, image
sha256, frozen prereg sha256, the manifest sha256 the session was bound to, the seed, the
budget, the instrument commit, the token). The manifest's `carrier.qualification` is that
record; `carrier.qualified` is DERIVED from it by `qualified()` and never set by hand.

`verify(manifest)` is what the mapping runner and the mapping adjudicator call: the record
exists; every evidence file still hashes to it; the binding is THIS manifest's carrier /
image / prereg / instrument; the recorded outcome is PASS; and the pinned evidence
RE-ADJUDICATES to PASS under the B1Q adjudicator now (pure, so it can) with no finding. Any
of these failing is a QualificationRefusal, and the carrier is not qualified.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))

SCHEMA = "b1_carrier_qualification"
SCHEMA_VERSION = "1.0.0"
EVIDENCE_FILES = ("run_log.json", "audits.json", "timeline.json", "adjudication.json", "summary.json")
BINDING_KEYS = ("carrier_sha256", "carrier_variant", "image_sha256", "prereg_sha256", "b1_manifest_sha256",
                "master_seed", "budget", "psoracle_commit", "token", "session")


class QualificationRefusal(Exception):
    pass


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path) -> str:
    p = Path(path).resolve()
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def make_record(evidence_dir: Path, manifest: dict, manifest_sha256: str, plan: dict, ruling: dict, result: dict, token: str) -> dict:
    """The record for a B1Q session whose adjudication `result` is on disk beside the
    evidence. The outcome is copied as adjudicated — a HOLD record is a record too (of a
    failed qualification); only a PASS record can qualify."""
    files = {}
    for name in EVIDENCE_FILES:
        p = Path(evidence_dir) / name
        files[name] = sha256_of(p) if p.is_file() else None
    return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "session": plan["session"],
            "evidence_dir": _rel(evidence_dir), "files": files, "outcome": result.get("outcome"),
            "ruling": {k: ruling.get(k) for k in ("ruling", "boardid", "granted_by", "date")},
            "binding": {"session": plan["session"], "carrier_sha256": manifest["carrier"]["bitstream_sha256"],
                        "carrier_variant": manifest["carrier"]["variant"], "image_sha256": manifest["image"]["sha256"],
                        "prereg_sha256": manifest["prereg"]["sha256"], "b1_manifest_sha256": manifest_sha256,
                        "master_seed": plan["master_seed"], "budget": plan["budget"],
                        "psoracle_commit": manifest["instrument"]["psoracle_commit"], "token": token},
            "note": "carrier.qualified is derived from this record by host/b1_qualification.py: the files must still hash, the "
                    "binding must be the manifest's, the outcome PASS, and the evidence must re-adjudicate to PASS"}


def verify(manifest: dict, root: Path = REPO_ROOT, require_git: bool = False, instrument_root: Path | None = None) -> dict:
    q = (manifest.get("carrier") or {}).get("qualification")
    if not isinstance(q, dict):
        raise QualificationRefusal("the manifest carries no carrier.qualification record: the B1Q session has not been run and pinned")
    if q.get("schema") != SCHEMA:
        raise QualificationRefusal(f"carrier.qualification schema {q.get('schema')!r} is not {SCHEMA!r}")
    if q.get("outcome") != "PASS":
        raise QualificationRefusal(f"the recorded qualification outcome is {q.get('outcome')!r}, not PASS")
    b = q.get("binding") or {}
    for k in BINDING_KEYS:
        if k not in b:
            raise QualificationRefusal(f"the qualification record's binding lacks {k!r}")
    want = {"session": "B1Q", "carrier_sha256": manifest["carrier"]["bitstream_sha256"], "carrier_variant": manifest["carrier"]["variant"],
            "image_sha256": manifest["image"]["sha256"], "prereg_sha256": manifest["prereg"]["sha256"],
            "psoracle_commit": manifest["instrument"]["psoracle_commit"]}
    if not want["prereg_sha256"]:
        raise QualificationRefusal("the preregistration is not frozen: a qualification cannot bind to a null prereg")
    for k, v in want.items():
        if b.get(k) != v:
            raise QualificationRefusal(f"the qualification was bound to {k} = {str(b.get(k))[:20]!r}, this manifest has {str(v)[:20]!r}")
    qp = manifest.get("qualification_plan") or {}
    if b.get("master_seed") != qp.get("master_seed") or b.get("budget") != qp.get("budget"):
        raise QualificationRefusal("the qualification was bound to another seed/budget than the manifest's qualification plan")
    ev = Path(q.get("evidence_dir", ""))
    ev = ev if ev.is_absolute() else root / ev
    if not ev.is_dir():
        raise QualificationRefusal(f"the qualification evidence directory {q.get('evidence_dir')!r} is absent")
    for name in EVIDENCE_FILES:
        want_sha = (q.get("files") or {}).get(name)
        p = ev / name
        if not want_sha or not p.is_file() or sha256_of(p) != want_sha:
            raise QualificationRefusal(f"qualification evidence {name} is missing or does not hash to the record")
    stored = json.loads((ev / "adjudication.json").read_text())
    if stored.get("outcome") != "PASS" or stored.get("session") != "B1Q":
        raise QualificationRefusal("the stored qualification adjudication is not a B1Q PASS")
    # re-adjudicate the pinned evidence NOW, against the manifest's pinned qualification plan
    import b1q_adjudicate as bq  # noqa: E402
    plan_path, pred_path = root / qp.get("path", "MISSING"), root / qp.get("prediction_path", "MISSING")
    if not plan_path.is_file() or not pred_path.is_file():
        raise QualificationRefusal("the manifest's qualification plan/prediction files are absent")
    plan, pred = json.loads(plan_path.read_text()), json.loads(pred_path.read_text())
    res = bq.adjudicate(ev, manifest, plan, pred, b["b1_manifest_sha256"], instrument_root=instrument_root, require_git=require_git,
                        plan_path=plan_path, prediction_path=pred_path)
    if res.get("outcome") != "PASS":
        raise QualificationRefusal(f"the pinned qualification evidence re-adjudicates to {res.get('outcome')!r}, not PASS")
    return {"evidence_dir": str(ev), "outcome": "PASS", "readjudicated": True, "token": b["token"]}


def qualified(manifest: dict, **kw) -> bool:
    try:
        verify(manifest, **kw)
        return True
    except QualificationRefusal:
        return False


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, default=REPO_ROOT / "manifests/b1_manifest.json")
    a = ap.parse_args(argv)
    m = json.loads(a.manifest.read_text())
    try:
        print(json.dumps(verify(m), indent=1))
    except QualificationRefusal as exc:
        print(f"NOT QUALIFIED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
