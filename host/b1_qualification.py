#!/usr/bin/env python3
"""B1 — the carrier's QUALIFICATION as an evidence chain, not a flag (owner's reviews
2026-09-05, blockers 3 of v2 and v2.1).

A B1Q session leaves, beside the instrument's evidence files (run_log, audits, timeline,
adjudication, summary), the session's OWN evidence of what it was bound to, written by the
runner before `go` (`write_session_artifacts`): `manifest_at_run.json` — the exact bytes of
the manifest the preflight read — and `ruling_whole_of_run.json` / `ruling_provisioning.json`
— the two ruling files verbatim. The qualification RECORD (`qualification.json`) then names
every one of those files by sha256, the outcome, the session token (taken from the run log,
never from a caller), the full content of both rulings, the plan / prediction / pin-table
hashes the session ran against, and the binding (carrier sha256 and variant, image sha256,
frozen prereg sha256, the manifest sha256 — which IS the hash of manifest_at_run.json —
the seed, the budget, the instrument commit).

`verify(manifest)` is what the mapping runner and the mapping adjudicator call. It holds
only if ALL of:
  * the record is present with outcome PASS and every evidence file hashes to it;
  * manifest_at_run.json hashes to the record's / the run log's b1_manifest_sha256, and the
    manifest it contains binds the same carrier / image / prereg / instrument / plan pins;
  * the run log's token (app_identity, notary_log, session_summary) and the summary's
    token / session / outcome agree with the record;
  * both rulings re-bind: the right texts, session B1Q, the plan's seed, the prereg, the
    image and the manifest sha256 of manifest_at_run;
  * the run log's l6.inputs are the qualification plan / prediction / pin table of
    manifest_at_run;
  * the pinned evidence RE-ADJUDICATES to PASS under the B1Q adjudicator NOW, against
    manifest_at_run (the manifest the session was bound to), with no finding;
  * the CURRENT manifest differs from manifest_at_run in nothing but the qualification
    state (`carrier.qualification`, `carrier.qualified`): the only transition a
    qualification licenses. Anything else that changed since (a pin, a plan, the image, the
    prereg, a note) means the carrier was qualified for another manifest.
Any of these failing is a QualificationRefusal, and the carrier is not qualified.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))

SCHEMA = "b1_carrier_qualification"
SCHEMA_VERSION = "2.1.0"
# A ruling is archived as an INERT envelope, never as a parseable copy: a verbatim copy is
# a second, unconsumed authorisation to every ruling parser (the instrument's check_ruling,
# this runner's preflight, the signer's provisioning path — owner's review 2026-09-05).
# The envelope carries the original bytes base64-encoded and their sha256; it has no
# top-level `ruling` / `boardid` / `granted_by` / `date`, so every parser refuses it.
ARCHIVE_SCHEMA = "archived_ruling_bytes"
ARCHIVE_VERSION = "1.0.0"
# the envelope's EXACT key set (additionalProperties: false): an envelope carrying anything
# else — a ruling field re-added at the top level in particular — is refused even when every
# hash in the evidence and the record was updated to match (owner's review 2026-09-05)
ARCHIVE_KEYS = frozenset({"schema", "schema_version", "sha256", "content_base64", "note"})
RULING_FIELDS = ("ruling", "boardid", "granted_by", "date", "session", "master_seed", "prereg_sha256", "image_sha256", "b1_manifest_sha256")
SESSION = "B1Q"
RULING_TEXT = "whole-of-run B1 carrier qualification"
PROVISION_RULING_TEXT = "provisioning P3-K"
MANIFEST_AT_RUN = "manifest_at_run.json"
RULING_FILES = {"whole_of_run": "ruling_whole_of_run.json", "provisioning": "ruling_provisioning.json"}
EVIDENCE_FILES = ("run_log.json", "audits.json", "timeline.json", "adjudication.json", "summary.json",
                  MANIFEST_AT_RUN, RULING_FILES["whole_of_run"], RULING_FILES["provisioning"])
BINDING_KEYS = ("session", "carrier_sha256", "carrier_variant", "image_sha256", "prereg_sha256", "b1_manifest_sha256",
                "master_seed", "budget", "psoracle_commit", "token")
# the ONLY keys a qualification may change between manifest_at_run and the current manifest
TRANSITION_KEYS = (("carrier", "qualification"), ("carrier", "qualified"))


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


def archive_envelope(raw: bytes) -> dict:
    return {"schema": ARCHIVE_SCHEMA, "schema_version": ARCHIVE_VERSION, "sha256": hashlib.sha256(raw).hexdigest(),
            "content_base64": base64.b64encode(raw).decode("ascii"),
            "note": "an archived copy of a ruling's bytes; NOT a ruling — no parser accepts it, and it authorises nothing"}


def read_archived_ruling(path: Path) -> tuple[bytes, dict]:
    """The original bytes and the parsed ruling from an envelope; a refusal if the file is
    not an envelope, or its bytes do not hash to its own sha256, or they do not parse."""
    try:
        env = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise QualificationRefusal(f"no readable ruling archive at {path}: {exc}") from exc
    if not isinstance(env, dict) or env.get("schema") != ARCHIVE_SCHEMA or env.get("schema_version") != ARCHIVE_VERSION:
        raise QualificationRefusal(f"{Path(path).name} is not an {ARCHIVE_SCHEMA} envelope")
    if set(env) != ARCHIVE_KEYS:
        extra, missing = sorted(set(env) - ARCHIVE_KEYS), sorted(ARCHIVE_KEYS - set(env))
        raise QualificationRefusal(f"{Path(path).name}: an envelope carries exactly {sorted(ARCHIVE_KEYS)}; extra {extra}, missing {missing} "
                                   f"(a ruling field on an envelope would make it a ruling again)")
    if any(k in env for k in RULING_FIELDS):
        raise QualificationRefusal(f"{Path(path).name}: an envelope must carry no ruling field")
    if not isinstance(env.get("sha256"), str) or not isinstance(env.get("content_base64"), str) or not isinstance(env.get("note", ""), str):
        raise QualificationRefusal(f"{Path(path).name}: envelope fields of the wrong type")
    try:
        raw = base64.b64decode(env.get("content_base64") or "", validate=True)
    except (ValueError, TypeError) as exc:
        raise QualificationRefusal(f"{Path(path).name}: the archived bytes do not decode: {exc}") from None
    if hashlib.sha256(raw).hexdigest() != env.get("sha256"):
        raise QualificationRefusal(f"{Path(path).name}: the archived bytes do not hash to the envelope's sha256")
    try:
        content = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise QualificationRefusal(f"{Path(path).name}: the archived bytes are not a JSON ruling: {exc}") from None
    if not isinstance(content, dict):
        raise QualificationRefusal(f"{Path(path).name}: the archived bytes are not a ruling object")
    return raw, content


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def write_session_artifacts(out_dir: Path, manifest_path: Path, ruling_path: Path, provision_ruling_path: Path,
                            manifest_sha256: str, expected_rulings: tuple[dict, dict] | None = None) -> dict:
    """Archive the manifest bytes (verbatim) and both rulings (as INERT envelopes, never as
    parseable copies) into the evidence directory, BEFORE the port is opened
    (b1_runner.execute). The manifest copy must hash to the sha256 the preflight bound the
    session to; each ruling's bytes must parse to exactly what the preflight parsed
    (`expected_rulings` = (whole-of-run, provisioning)) — a file that changed between
    preflight and archive is a refusal, with nothing consumed and no port. Every write is
    atomic and a failure removes what was written, so no partial artifact — and never any
    executable ruling — is left behind."""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        dst = out_dir / MANIFEST_AT_RUN
        shutil.copyfile(manifest_path, dst.with_name(dst.name + ".tmp")); os.replace(dst.with_name(dst.name + ".tmp"), dst)
        written.append(dst)
        if sha256_of(dst) != manifest_sha256:
            raise QualificationRefusal("the manifest bytes copied into the evidence do not hash to the preflight's manifest sha256")
        for src, name, want in ((ruling_path, RULING_FILES["whole_of_run"], expected_rulings[0] if expected_rulings else None),
                                (provision_ruling_path, RULING_FILES["provisioning"], expected_rulings[1] if expected_rulings else None)):
            raw = Path(src).read_bytes()
            try:
                got = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise QualificationRefusal(f"the ruling at {src} is not JSON: {exc}") from None
            if want is not None and got != want:
                raise QualificationRefusal(f"the ruling at {src} is not the ruling the preflight parsed")
            _write_atomic(out_dir / name, json.dumps(archive_envelope(raw), indent=1) + "\n")
            written.append(out_dir / name)
            read_archived_ruling(out_dir / name)          # the envelope round-trips before we go on
    except BaseException:
        for p in written:
            p.unlink(missing_ok=True)
        for p in out_dir.glob("*.tmp"):
            p.unlink(missing_ok=True)
        raise
    return {name: sha256_of(out_dir / name) for name in (MANIFEST_AT_RUN, *RULING_FILES.values())}


def _strip_transition(m: dict) -> dict:
    m = copy.deepcopy(m)
    for path in TRANSITION_KEYS:
        d = m
        for k in path[:-1]:
            d = d.get(k) or {}
        d.pop(path[-1], None)
    return m


def make_record(evidence_dir: Path, manifest: dict, manifest_sha256: str, plan: dict, result: dict) -> dict:
    """The record for a B1Q session whose adjudication `result` and session artifacts are on
    disk beside the evidence. The token and the rulings are READ FROM THE EVIDENCE, never
    given by a caller. The outcome is copied as adjudicated — a HOLD record is a record too
    (of a failed qualification); only a PASS record can qualify."""
    ev = Path(evidence_dir)
    files = {}
    for name in EVIDENCE_FILES:
        p = ev / name
        files[name] = sha256_of(p) if p.is_file() else None
    log = json.loads((ev / "run_log.json").read_text())
    token = (log.get("app_identity") or {}).get("token")
    rulings = {}
    for key, name in RULING_FILES.items():
        p = ev / name
        if p.is_file():
            raw, content = read_archived_ruling(p)
            rulings[key] = {"file": name, "envelope_sha256": files[name], "bytes_sha256": hashlib.sha256(raw).hexdigest(), "content": content}
        else:
            rulings[key] = {"file": name, "envelope_sha256": None, "bytes_sha256": None, "content": None}
    qp = manifest.get("qualification_plan") or {}
    return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "session": plan["session"],
            "evidence_dir": _rel(ev), "files": files, "outcome": result.get("outcome"),
            "rulings": rulings,
            "inputs": {"plan_sha256": qp.get("sha256"), "prediction_sha256": qp.get("prediction_sha256"),
                       "pins_sha256": (manifest.get("pins") or {}).get("sha256")},
            "binding": {"session": plan["session"], "carrier_sha256": manifest["carrier"]["bitstream_sha256"],
                        "carrier_variant": manifest["carrier"]["variant"], "image_sha256": manifest["image"]["sha256"],
                        "prereg_sha256": manifest["prereg"]["sha256"], "b1_manifest_sha256": manifest_sha256,
                        "master_seed": plan["master_seed"], "budget": plan["budget"],
                        "psoracle_commit": manifest["instrument"]["psoracle_commit"], "token": token},
            "note": "carrier.qualified is derived from this record by host/b1_qualification.py: the files must still hash, "
                    "manifest_at_run.json must hash to b1_manifest_sha256, the tokens and rulings must agree, the evidence must "
                    "re-adjudicate to PASS against manifest_at_run, and the current manifest may differ from it only in the "
                    "qualification state"}


def _bind_ruling(r: dict, text: str, b: dict, need_seed: bool) -> None:
    if not isinstance(r, dict):
        raise QualificationRefusal(f"the {text!r} ruling is not recorded")
    if r.get("ruling") != text:
        raise QualificationRefusal(f"the recorded ruling text is {r.get('ruling')!r}, not {text!r}")
    want = {"session": SESSION, "prereg_sha256": b["prereg_sha256"], "image_sha256": b["image_sha256"],
            "b1_manifest_sha256": b["b1_manifest_sha256"]}
    if need_seed:
        want["master_seed"] = b["master_seed"]
    for k, v in want.items():
        got = r.get(k)
        if k == "master_seed" and isinstance(got, str):
            try:
                got = int(got, 0)
            except ValueError:
                got = None
        if got != v:
            raise QualificationRefusal(f"the {text!r} ruling is bound to {k} = {str(got)[:16]!r}, the qualification needs {str(v)[:16]!r}")
    for f in ("boardid", "granted_by", "date"):
        if not r.get(f):
            raise QualificationRefusal(f"the {text!r} ruling lacks {f!r}")


def verify(manifest: dict, root: Path = REPO_ROOT, require_git: bool = False, instrument_root: Path | None = None) -> dict:
    q = (manifest.get("carrier") or {}).get("qualification")
    if not isinstance(q, dict):
        raise QualificationRefusal("the manifest carries no carrier.qualification record: the B1Q session has not been run and pinned")
    if q.get("schema") != SCHEMA or q.get("schema_version") != SCHEMA_VERSION:
        raise QualificationRefusal(f"carrier.qualification schema {q.get('schema')!r} {q.get('schema_version')!r} is not {SCHEMA!r} {SCHEMA_VERSION!r}")
    if q.get("outcome") != "PASS":
        raise QualificationRefusal(f"the recorded qualification outcome is {q.get('outcome')!r}, not PASS")
    b = q.get("binding") or {}
    for k in BINDING_KEYS:
        if k not in b:
            raise QualificationRefusal(f"the qualification record's binding lacks {k!r}")
    want = {"session": SESSION, "carrier_sha256": manifest["carrier"]["bitstream_sha256"], "carrier_variant": manifest["carrier"]["variant"],
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
    # the evidence files
    ev = Path(q.get("evidence_dir", ""))
    ev = ev if ev.is_absolute() else root / ev
    if not ev.is_dir():
        raise QualificationRefusal(f"the qualification evidence directory {q.get('evidence_dir')!r} is absent")
    for name in EVIDENCE_FILES:
        want_sha = (q.get("files") or {}).get(name)
        p = ev / name
        if not want_sha or not p.is_file() or sha256_of(p) != want_sha:
            raise QualificationRefusal(f"qualification evidence {name} is missing or does not hash to the record")
    # the manifest the session was bound to, by its bytes
    m_at_run_path = ev / MANIFEST_AT_RUN
    if sha256_of(m_at_run_path) != b["b1_manifest_sha256"]:
        raise QualificationRefusal("manifest_at_run.json does not hash to the record's b1_manifest_sha256")
    m_at_run = json.loads(m_at_run_path.read_text())
    for k, v in want.items():
        got = {"session": SESSION, "carrier_sha256": m_at_run["carrier"]["bitstream_sha256"], "carrier_variant": m_at_run["carrier"]["variant"],
               "image_sha256": m_at_run["image"]["sha256"], "prereg_sha256": m_at_run["prereg"]["sha256"],
               "psoracle_commit": m_at_run["instrument"]["psoracle_commit"]}[k]
        if got != v:
            raise QualificationRefusal(f"manifest_at_run binds {k} = {str(got)[:20]!r}, the current manifest {str(v)[:20]!r}")
    if not m_at_run["image"].get("board_ready"):
        raise QualificationRefusal("manifest_at_run was not board_ready: the qualification session ran before the freeze")
    # the run log, the summary, the tokens
    log = json.loads((ev / "run_log.json").read_text())
    summary = json.loads((ev / "summary.json").read_text())
    token = (log.get("app_identity") or {}).get("token")
    if not token or token != b["token"]:
        raise QualificationRefusal("the record's token is not the run log's app_identity token")
    if (log.get("notary_log") or {}).get("token") != token or (log.get("session_summary") or {}).get("token") != token:
        raise QualificationRefusal("the run log's notary_log / session_summary token is not the app_identity token")
    if summary.get("token") != token or summary.get("outcome") != "PASS" or (summary.get("l6") or {}).get("session") != SESSION:
        raise QualificationRefusal("summary.json does not name this token, session B1Q and outcome PASS")
    archived = {key: read_archived_ruling(ev / name) for key, name in RULING_FILES.items()}      # (bytes, content)
    if summary.get("ruling") != archived["whole_of_run"][1]:
        raise QualificationRefusal("summary.ruling is not the archived whole-of-run ruling: the session ran under another ruling")
    if summary.get("provisioning_ruling_sha256") != hashlib.sha256(archived["provisioning"][0]).hexdigest():
        raise QualificationRefusal("the provisioning ruling the signer was handed (summary.provisioning_ruling_sha256) is not the archived bytes")
    lb = (log.get("l6") or {}).get("binding") or {}
    if lb.get("b1_manifest_sha256") != b["b1_manifest_sha256"] or lb.get("session") != SESSION:
        raise QualificationRefusal("the run log's binding is not the record's (manifest sha256 / session)")
    # the inputs the session ran against are manifest_at_run's qualification pins
    qp_run = m_at_run.get("qualification_plan") or {}
    want_inputs = {"plan_sha256": qp_run.get("sha256"), "prediction_sha256": qp_run.get("prediction_sha256"),
                   "pins_sha256": (m_at_run.get("pins") or {}).get("sha256")}
    li = (log.get("l6") or {}).get("inputs") or {}
    for k, v in want_inputs.items():
        if not v or li.get(k) != v or (q.get("inputs") or {}).get(k) != v:
            raise QualificationRefusal(f"the session's inputs ({k}) are not manifest_at_run's qualification pins")
    # both rulings, from their verbatim copies (never from the record's copy alone)
    for key, text, need_seed in (("whole_of_run", RULING_TEXT, True), ("provisioning", PROVISION_RULING_TEXT, False)):
        rec_r = (q.get("rulings") or {}).get(key) or {}
        p = ev / RULING_FILES[key]
        raw, content = archived[key]
        if rec_r.get("envelope_sha256") != sha256_of(p) or rec_r.get("bytes_sha256") != hashlib.sha256(raw).hexdigest():
            raise QualificationRefusal(f"the recorded {key} ruling hashes are not the archived envelope's / bytes'")
        if rec_r.get("content") != content:
            raise QualificationRefusal(f"the recorded {key} ruling content differs from the archived bytes")
        _bind_ruling(content, text, b, need_seed)
        if content.get("boardid") != m_at_run["board"]["boardid"]:
            raise QualificationRefusal(f"the {key} ruling names board {content.get('boardid')!r}, the manifest {m_at_run['board']['boardid']!r}")
    stored = json.loads((ev / "adjudication.json").read_text())
    if stored.get("outcome") != "PASS" or stored.get("session") != SESSION:
        raise QualificationRefusal("the stored qualification adjudication is not a B1Q PASS")
    # re-adjudicate the pinned evidence NOW, against the manifest the session was bound to
    import b1q_adjudicate as bq  # noqa: E402
    plan_path, pred_path = root / qp_run.get("path", "MISSING"), root / qp_run.get("prediction_path", "MISSING")
    if not plan_path.is_file() or not pred_path.is_file():
        raise QualificationRefusal("the qualification plan/prediction files are absent")
    plan, pred = json.loads(plan_path.read_text()), json.loads(pred_path.read_text())
    res = bq.adjudicate(ev, m_at_run, plan, pred, b["b1_manifest_sha256"], instrument_root=instrument_root, require_git=require_git,
                        plan_path=plan_path, prediction_path=pred_path)
    if res.get("outcome") != "PASS":
        raise QualificationRefusal(f"the pinned qualification evidence re-adjudicates to {res.get('outcome')!r}, not PASS")
    # the only transition a qualification licenses
    if _strip_transition(m_at_run) != _strip_transition(manifest):
        raise QualificationRefusal("the current manifest differs from manifest_at_run in more than the qualification state: "
                                   "the carrier was qualified for another manifest")
    return {"evidence_dir": str(ev), "outcome": "PASS", "readjudicated": True, "token": token,
            "manifest_at_run_sha256": b["b1_manifest_sha256"]}


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
