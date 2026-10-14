#!/usr/bin/env python3
"""Fresh restore and production re-judge of ONE archived B3 session (lifecycle 2, form (c) archives).

    python3 -B evidence/b3/main_preparation_2026_10_14/restore_rejudge.py --session-dir evidence/b3/b3_17A6_<date>-NN [--keep] [--out result.json]

Run from the repository root. In order, and every step fail-closed by name:
 (1) `archive.json` must be the session's (schema b3_session_evidence_archive); `exports.tar.zst` must size and
     hash to it; an EMPTY temporary directory is created; the five members are extracted into it; the eleven
     ordinary files are copied in; the restored set must be EXACTLY the sixteen; every file's size and sha256
     must equal archive.json.
 (2) The export seal (`exports.json`, the production `b1_adjudicate.check_exports`) over the restored files.
 (3) The archived manifest (`manifest_at_run.json`): a b3_manifest document; its FILE digest is the binding every
     later check holds to; its plan pin locates the plan and prediction, both verified byte-for-byte BEFORE being
     read (the production `b3_runner.pinned_documents`); the authority's `verify` (production: `b3_manifest.verify`
     with the production B3Q re-adjudicator — the lifecycle verify, in this process) and `verify_pins` (the tree's
     pinned surface equals the archived manifest's table — the judge below is the pinned code) must pass.
 (4) The two archived rulings, decoded through the instrument's strict envelope reader — read, never claimed. The
     whole-of-run ruling is the AUTHORITY for the slice (pair_first, pair_count) and the transport disposition.
 (5) The SEARCH session plan REBUILT from the authoritative inputs — the archived manifest, its pinned plan and
     prediction, the ruling's slice and disposition, the bound instrument's schedule arithmetic — by
     `search_session_plan` below, which mirrors the production preflight's construction (b3/host/b3_runner.py,
     `preflight`, the SEARCH branch) field for field; a test holds the two equal key for key. (A B3Q archive is
     rebuilt by the production `qualification_session_plan` instead.) `summary.json["l6"]` and `run_log.json["l6"]`
     are then COMPARED to the rebuilt plan; they are never the authority.
 (6) The production `b3_runner.judge_session` over the restored directory, against the rebuilt plan; its verdict
     must equal the archived `adjudication.json` key for key; `runner_session.json` must satisfy the production
     `session_record_findings` against the rebuilt plan and THIS verdict.
 (7) The boundary record archive.json names must exist, hash as recorded, be a passed principal_boundary of the
     recorded runner user.
Exit status 0 only if every step holds (verdict ACCEPT); 2 on a named refusal; 3 on an internal error. Read-only on
the repository; the temporary directory is removed unless --keep. The result document (--out) records every step.

This file is the session's evidence, not an instrument: it lives beside the archive it re-judges; the copy in a
session directory must hash to the preparation's (archive.json records both). Seams: `rejudge(..., ports=None,
authority=None)` are the production instrument and the production authority; a test injects fakes exactly as
b3/tests/test_b3_runner.py does for the runner.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

def _repo_root(*starts: Path) -> Path:
    """The repository: --repo-root / B3_REPO_ROOT, else the first ancestor of this file or of the working directory
    that holds the B3 manifest and runner (a session copy of this script may live outside the tree)."""
    env = os.environ.get("B3_REPO_ROOT")
    cands = ([Path(env)] if env else []) + [q for s in starts for q in (s, *s.parents)]
    for p in cands:
        if (p / "manifests" / "b3_manifest.json").is_file() and (p / "b3" / "host" / "b3_runner.py").is_file():
            return p.resolve()
    raise SystemExit("not inside the zynq_fabricmap repository: run from the repository root or set B3_REPO_ROOT")


_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--repo-root", default=None)
_known, _ = _pre.parse_known_args()
if _known.repo_root:
    os.environ["B3_REPO_ROOT"] = _known.repo_root
ROOT = _repo_root(HERE, Path.cwd())
for p in (ROOT / "host", ROOT / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import b1_adjudicate as b1adj  # noqa: E402
import b1_qualification as bq  # noqa: E402
import b2_session as b2sess  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_plan as pl  # noqa: E402
import b3_records as brec  # noqa: E402
import b3_runner as rn  # noqa: E402
import b3_session as bsess  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

TOOL = "restore_rejudge.py/1.0.0 (b3 lifecycle 2, main preparation 2026-10-14)"
ARCHIVE_SCHEMA = "b3_session_evidence_archive"
MEMBERS = ("audits.json", "console.log", "console.ts.log", "run_log.json", "timeline.json")
ORDINARY = ("B1_0_preflight.json", "B1_1_identity_page.json", "adjudication.json", "exports.json", "manifest_at_run.json",
            "ruling_provisioning.json", "ruling_whole_of_run.json", "runner_session.json", "summary.json", "ymodem.log", "ymodem_app.log")
SESSION_FILES = tuple(sorted(MEMBERS + ORDINARY))          # the sixteen the runner writes
assert len(SESSION_FILES) == 16


class Refusal(Exception):
    pass


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _jsonable(plan: dict) -> dict:
    """The session plan as the driver serialises it into summary.json (b1_session: audit_seqs sorted)."""
    return json.loads(json.dumps({**plan, "audit_seqs": sorted(plan["audit_seqs"])}, sort_keys=True, default=str))


# ------------------------------------------------------------------ (5) the SEARCH session plan, rebuilt


def search_session_plan(manifest: dict, manifest_file_sha256: str, plan_doc: dict, prediction_doc: dict, first: int, count: int,
                        transport_disposition: str, instrument: dict, ports, authority) -> dict:
    """B3's (SEARCH) session plan REBUILT from the run manifest's pinned experiment and the ruling's slice — the plan
    the production preflight built for the live session (b3/host/b3_runner.py `preflight`, SEARCH branch), so the
    runner and this offline re-judge judge the SAME session: the same slice, records, frames, budgets and deadline
    (the split's rate_for_split, never the rate the session went on to measure). Every refusal is the preflight's."""
    if not isinstance(plan_doc, dict) or plan_doc.get("session") != rn.SESSION:
        raise Refusal(f"the pinned plan is not a {rn.SESSION} plan")
    budget, pairs_total = plan_doc["budget_per_arm"], plan_doc["pairs"]
    master = plan_doc["seed_derivation"]["master_seed"]
    if not rn._int(first) or not rn._int(count) or first < 0 or count <= 0 or first + count > pairs_total:
        raise Refusal(f"the slice ({first!r}, {count!r}) does not lie inside the experiment's {pairs_total} pairs")
    split_entry = rn.slice_in_split(plan_doc, first, count)
    if split_entry is None:
        raise Refusal(f"the slice ({first}, {count}) is not one the plan's split gives (the split is "
                      f"{(plan_doc.get('session_split') or {}).get('status', 'absent')})")
    if master != (manifest.get("seeds") or {}).get("master_seed"):
        raise Refusal("the plan's master seed is not the manifest's")
    try:
        brec.context_from(plan_doc, prediction_doc, first, count)
    except brec.ContextError as exc:
        raise Refusal(f"the records context: {exc}") from None
    records_expected = bsess.records(count, budget)
    if not rn._int(split_entry.get("records")):
        raise Refusal(f"the plan's split entry carries no integer records ({split_entry.get('records')!r})")
    if split_entry["records"] != records_expected:
        raise Refusal(f"the plan's split says {split_entry['records']} records for this slice, the record arithmetic says {records_expected}")
    split = plan_doc["session_split"]
    rate_for_split = split.get("rate_for_split")
    if not rn._finite_positive(rate_for_split):
        raise Refusal(f"the plan's split carries no finite positive rate_for_split ({rate_for_split!r})")
    if not rn._finite_positive(split_entry.get("deadline_s")):
        raise Refusal(f"the plan's split entry carries no finite positive deadline_s ({split_entry.get('deadline_s')!r})")
    import math
    timeout = rn.deadline_s(records_expected, rate_for_split)
    if not math.isclose(float(split_entry["deadline_s"]), timeout, rel_tol=1e-9):
        raise Refusal(f"the split's deadline {split_entry['deadline_s']} is not the frozen formula's {timeout}")
    rate_note = {"source": "the plan's split, from the B3Q calibration under the 0.85 margin", "rate_for_split": rate_for_split,
                 "rate_measured": split.get("rate_measured"), "margin": split.get("calibration_margin")}
    try:
        b1_manifest = json.loads(rn.B1_MANIFEST.read_text())
    except (OSError, ValueError) as exc:
        raise Refusal(f"no readable B1 manifest: {exc}") from None
    wire = (b1_manifest.get("protocol") or {}).get("wire")
    if wire != rn.PROTOCOL_WIRE:
        raise Refusal(f"the pinned wire protocol {wire!r} is not the {rn.PROTOCOL_WIRE!r} this stage speaks")
    ls = ports.schedule()
    base_flags = ls.flags_for(ls.MODE_ABBA, watchdog=True, rec_control=True, sign_control=True)
    try:
        flags = b2sess.encode_slice(base_flags, pairs_total, first, count)
    except ValueError as exc:
        raise Refusal(f"the identity page cannot carry this slice: {exc}") from None
    audit_seqs = set(range(1, records_expected + 1))
    expected_frames = ls.expected_frames(records_expected - 2, audit_seqs, wire)
    if expected_frames["records"] != records_expected:
        raise Refusal(f"the frame arithmetic says {expected_frames['records']} records, the record arithmetic says {records_expected}")
    crc_budget = ls.crc_budget(expected_frames["total"])
    resend = rn.resend_budget(expected_frames["total"])
    if not isinstance(transport_disposition, str) or not transport_disposition.strip():
        raise Refusal("no transport disposition: a B3 session runs under one")
    board = authority.check_board(manifest)
    car = manifest.get("carrier") or {}
    psoracle_commit = instrument.get("psoracle_commit")
    if psoracle_commit != (manifest.get("instrument") or {}).get("psoracle_commit"):
        raise Refusal(f"the bound instrument's commit {str(psoracle_commit)[:12]} is not the manifest's {str((manifest.get('instrument') or {}).get('psoracle_commit'))[:12]}")
    return {
        "session": rn.SESSION, "mode": bs.ENGINE_VERSION, "master_seed": master, "n": budget, "schedule": [],
        "audit_policy": rn.AUDIT_POLICY, "audit_seqs": audit_seqs, "pair_first": first, "pair_count": count, "pairs_total": pairs_total,
        "flags": flags, "expected_records": records_expected, "records_per_pair": pl.records_per_pair(budget),
        "ledger_entries": count * budget, "expected_frames": expected_frames,
        "crc_budget": crc_budget, "bad_frame_budget": crc_budget,
        "crc_formula": "ceil(4 x expected_total / 1000) (D-s4), from the instrument's l6_schedule",
        "resend_budget": resend, "resend_formula": "ceil(4 x expected_frames / 1000) (preregistration v0.3.1 §2 transport)",
        "transport_disposition": transport_disposition,
        "session_timeout_s": timeout, "deadline_formula": pl.DEADLINE_FORMULA, "deadline_rate": rate_note, "protocol": wire,
        "rules_version": "b3/v0.3 over L6 v0.7 rules", "bad_frame_policy": "ledger", "hb_rule": "v07", "rec_retry_control": True,
        "carto_version": carto_mod.CARTO_VERSION, "arms": brec.ARMS, "b1_map_cost": oa.B1_MAP_COST,
        "inputs": rn.expected_inputs(manifest, rn.SEARCH, authority),
        "binding": {"image_sha256": (manifest.get("image") or {}).get("sha256"), "prereg_sha256": (manifest.get("prereg") or {}).get("sha256"),
                    "session": rn.SESSION, "schedule_mode": bs.ENGINE_VERSION,
                    "master_seed": master, "b3_manifest_sha256": manifest_file_sha256, "psoracle_commit": psoracle_commit,
                    "map_canonical_json_sha256": manifest["map"]["canonical_json_sha256"], "fitness_id": manifest["experiment"]["fitness"],
                    "budget_per_arm": budget, "pair_first": first, "pair_count": count, "protocol": wire,
                    "carrier_sha256": car.get("bitstream_sha256"), "carrier_variant": rn.B3_VARIANT,
                    "universe_sha256": manifest["universe"]["sha256"], "boardid": board, "resend_budget": resend,
                    "carto_version": carto_mod.CARTO_VERSION},
    }


# ------------------------------------------------------------------ (1) the restore


def read_archive_doc(session_dir: Path) -> dict:
    p = session_dir / "archive.json"
    if not p.is_file():
        raise Refusal(f"{session_dir} carries no archive.json")
    try:
        doc = json.loads(p.read_text())
    except ValueError as exc:
        raise Refusal(f"archive.json is not JSON: {exc}") from None
    if not isinstance(doc, dict) or doc.get("schema") != ARCHIVE_SCHEMA or doc.get("schema_version") != "1.0.0":
        raise Refusal(f"archive.json is not a {ARCHIVE_SCHEMA} 1.0.0 document")
    members = {m["name"]: m for m in doc.get("archive", {}).get("members", [])}
    ordinary = {m["name"]: m for m in doc.get("ordinary_files", [])}
    if sorted(members) != sorted(MEMBERS) or sorted(ordinary) != sorted(ORDINARY):
        raise Refusal(f"archive.json does not list exactly the 5 members {list(MEMBERS)} and the 11 ordinary files {list(ORDINARY)}")
    return doc


def restore(session_dir: Path, doc: dict, tmp: Path) -> dict:
    members = {m["name"]: m for m in doc["archive"]["members"]}
    ordinary = {m["name"]: m for m in doc["ordinary_files"]}
    want = {**members, **ordinary}
    archive = session_dir / doc["archive"]["path"]
    if not archive.is_file():
        raise Refusal(f"the archive {doc['archive']['path']} is absent")
    if archive.stat().st_size != doc["archive"]["bytes"] or sha(archive) != doc["archive"]["sha256"]:
        raise Refusal(f"{archive.name} does not size / hash to archive.json")
    if any(tmp.iterdir()):
        raise Refusal(f"the restore directory {tmp} is not empty")
    r = subprocess.run(["bash", "-c", 'zstd -dc "$0" | tar -xf - -C "$1"', str(archive), str(tmp)], capture_output=True, text=True)
    if r.returncode != 0:
        raise Refusal(f"extracting {archive.name} failed: {r.stderr.strip()[:200]}")
    for name in ordinary:
        src = session_dir / name
        if not src.is_file():
            raise Refusal(f"the ordinary file {name} is absent from {session_dir}")
        shutil.copyfile(src, tmp / name)
    present = sorted(p.name for p in tmp.iterdir())
    if present != sorted(want):
        raise Refusal(f"the restored file set is not exactly the 16: extra {sorted(set(present) - set(want))}, missing {sorted(set(want) - set(present))}")
    for name, m in want.items():
        p = tmp / name
        if p.stat().st_size != m["bytes"]:
            raise Refusal(f"{name}: size {p.stat().st_size} != archive.json's {m['bytes']}")
        if sha(p) != m["sha256"]:
            raise Refusal(f"{name}: sha256 differs from archive.json")
    return {"restored_to": str(tmp), "files": len(present), "archive_sha256": doc["archive"]["sha256"]}


# ------------------------------------------------------------------ the re-judge


def rejudge(session_dir: Path, ports=None, authority=None, instrument_root=None, keep: bool = False, root: Path = ROOT) -> dict:
    session_dir = Path(session_dir).resolve()
    out = {"tool": TOOL, "session_dir": os.path.relpath(session_dir, root), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "verdict": None, "refusal": None, "steps": {}}
    tmp = Path(tempfile.mkdtemp(prefix="b3_fresh_restore_")).resolve()
    production = ports is None
    try:
        doc = read_archive_doc(session_dir)
        out["steps"]["restore"] = restore(session_dir, doc, tmp)
        # (2) the seal
        try:
            b1adj.check_exports(tmp)
        except b1adj.Refusal as exc:
            raise Refusal(f"evidence seal: {exc}") from None
        out["steps"]["seal"] = "ok"
        # (3) the manifest, its pins, its pinned documents
        p = ports or rn.Ports().production()
        a = authority or rn.production_authority()
        iroot = instrument_root or inst.DEFAULT_ROOT
        instrument = p.bind_instrument(iroot)
        mpath = tmp / rn.MANIFEST_AT_RUN
        manifest_sha = sha(mpath)
        try:
            manifest = json.loads(mpath.read_text())
        except ValueError as exc:
            raise Refusal(f"{rn.MANIFEST_AT_RUN} is not JSON: {exc}") from None
        if not isinstance(manifest, dict) or manifest.get("schema") != rn.MANIFEST_SCHEMA:
            raise Refusal(f"{rn.MANIFEST_AT_RUN} is not a {rn.MANIFEST_SCHEMA} document")
        # the session's profile, from the finalisation record and the archived whole-of-run ruling (both must agree)
        try:
            record = json.loads((tmp / "runner_session.json").read_text())
        except ValueError as exc:
            raise Refusal(f"runner_session.json is not JSON: {exc}") from None
        session = record.get("session") if isinstance(record, dict) else None
        if session not in (rn.SESSION, rn.QUAL_SESSION):
            raise Refusal(f"runner_session.json names session {session!r}: not a B3 session record")
        profile = rn.SEARCH if session == rn.SESSION else rn.QUALIFICATION
        try:
            _raw, ruling = bq.read_archived_ruling(tmp / bq.RULING_FILES["whole_of_run"])
        except bq.QualificationRefusal as exc:
            raise Refusal(f"the archived whole-of-run ruling: {exc}") from None
        if ruling.get("ruling") != profile["ruling_text"]:
            raise Refusal(f"the archived whole-of-run ruling's text {str(ruling.get('ruling'))[:60]!r} is not the {session} text")
        if ruling.get("b3_manifest_sha256") != manifest_sha:
            raise Refusal(f"the archived manifest hashes to {manifest_sha[:16]}…, the archived ruling binds {str(ruling.get('b3_manifest_sha256'))[:16]}…")
        try:
            vres = a.verify(manifest)
            pres = a.verify_pins(manifest, root)
        except rn.Refusal as exc:
            raise Refusal(str(exc)) from None
        out["steps"]["manifest"] = {"file_sha256": manifest_sha, "verify": {k: vres.get(k) for k in ("stage", "qualified", "refusal") if isinstance(vres, dict)},
                                    "pins": pres if isinstance(pres, dict) else str(pres)}
        if profile is rn.SEARCH and (not manifest.get("qualified") or not manifest.get("qualification")):
            raise Refusal("the archived manifest is not qualified: no B3 session runs before S2")
        try:
            plan_doc, prediction_doc, pin = rn.pinned_documents(manifest, "plan" if profile is rn.SEARCH else "qualification_plan", session, root)
        except rn.Refusal as exc:
            raise Refusal(str(exc)) from None
        out["steps"]["pinned_documents"] = {"plan_sha256": pin.get("sha256"), "prediction_sha256": pin.get("prediction_sha256")}
        # (4)+(5) the slice and disposition from the archived ruling; the plan rebuilt
        disposition = ruling.get("transport_disposition")
        if profile is rn.SEARCH:
            try:
                first, count = int(ruling.get("pair_first"), 0) if isinstance(ruling.get("pair_first"), str) else ruling.get("pair_first"), \
                    int(ruling.get("pair_count"), 0) if isinstance(ruling.get("pair_count"), str) else ruling.get("pair_count")
            except (TypeError, ValueError):
                raise Refusal("the archived whole-of-run ruling carries no integer slice") from None
            session_plan = search_session_plan(manifest, manifest_sha, plan_doc, prediction_doc, first, count, disposition, instrument, p, a)
        else:
            try:
                session_plan = rn.qualification_session_plan(manifest, manifest_sha, plan_doc, disposition, p)
            except rn.Refusal as exc:
                raise Refusal(str(exc)) from None
        rebuilt = _jsonable(session_plan)
        try:
            summary = json.loads((tmp / "summary.json").read_text())
            log = json.loads((tmp / "run_log.json").read_text())
        except ValueError as exc:
            raise Refusal(f"summary.json / run_log.json: {exc}") from None
        l6 = summary.get("l6") if isinstance(summary, dict) else None
        if not isinstance(l6, dict):
            raise Refusal("summary.json carries no l6 session plan to compare against")
        diff = sorted(k for k in set(rebuilt) | set(l6) if rebuilt.get(k) != l6.get(k))
        if diff:
            raise Refusal(f"the session plan rebuilt from the authoritative inputs differs from summary.json's l6 in {diff}")
        log_l6 = (log.get("l6") or {}) if isinstance(log, dict) else {}
        for k in ("binding", "inputs"):
            if log_l6.get(k) != rebuilt[k]:
                raise Refusal(f"run_log.json's l6.{k} is not the rebuilt plan's")
        out["steps"]["session_plan"] = {"rebuilt_by": "search_session_plan (mirrors b3_runner.preflight)" if profile is rn.SEARCH else "b3_runner.qualification_session_plan",
                                        "pair_first": session_plan["pair_first"], "pair_count": session_plan["pair_count"],
                                        "expected_records": session_plan["expected_records"], "expected_frames_total": session_plan["expected_frames"]["total"],
                                        "crc_budget": session_plan["crc_budget"], "resend_budget": session_plan["resend_budget"],
                                        "session_timeout_s": session_plan["session_timeout_s"], "summary_l6_equal": True, "run_log_l6_equal": True}
        # (6) the production judge, against the archived verdict and the finalisation record
        verdict = rn.judge_session(tmp, manifest, session_plan, plan_doc, prediction_doc, iroot, p)
        try:
            stored = json.loads((tmp / "adjudication.json").read_text())
        except ValueError as exc:
            raise Refusal(f"adjudication.json is not JSON: {exc}") from None
        vj = json.loads(json.dumps(verdict, default=str))
        vdiff = sorted(k for k in set(vj) | set(stored) if vj.get(k) != stored.get(k))
        out["steps"]["judge"] = {"outcome": verdict.get("outcome"), "measured_rate_per_hour": verdict.get("measured_rate_per_hour"),
                                 "findings": verdict.get("findings"), "kills": verdict.get("kills"), "keys_differing_from_archived": vdiff}
        if vdiff:
            raise Refusal(f"the re-judge differs from the archived adjudication.json in {vdiff}")
        want = {**rn.session_record_expectation(session_plan, profile["stage"]), "outcome": verdict["outcome"], "cause": rn.classify(verdict["outcome"]),
                "measured_rate_per_hour": verdict.get("measured_rate_per_hour")}
        rf = rn.session_record_findings(record, want)
        if rf:
            raise Refusal("runner_session.json against the rebuilt plan and this verdict: " + "; ".join(rf[:4]))
        if record.get("transport", {}).get("transport_disposition") != disposition:
            raise Refusal("runner_session.json's transport disposition is not the archived ruling's")
        out["steps"]["session_record"] = "ok"
        # (7) the boundary record
        b = doc.get("boundary") or {}
        bpath = root / b.get("path", "")
        if not b.get("path") or not bpath.is_file():
            raise Refusal(f"the boundary record archive.json names ({b.get('path')!r}) is absent")
        if sha(bpath) != b.get("sha256"):
            raise Refusal("the boundary record does not hash to archive.json")
        try:
            bdoc = json.loads(bpath.read_text())
        except ValueError as exc:
            raise Refusal(f"the boundary record is not JSON: {exc}") from None
        if bdoc.get("schema") != "principal_boundary" or bdoc.get("all_passed") is not True:
            raise Refusal("the boundary record is not a passed principal_boundary")
        if b.get("runner_user") and bdoc.get("runner_user") != b.get("runner_user"):
            raise Refusal("the boundary record's runner_user is not the one archive.json records")
        out["steps"]["boundary"] = {"path": b["path"], "sha256": b["sha256"], "all_passed": True, "at": bdoc.get("at")}
        out["verdict"] = "ACCEPT"
    except Refusal as exc:
        out["verdict"], out["refusal"] = "REFUSE", str(exc)
    finally:
        if keep:
            out["restored_dir_kept"] = str(tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
            out["restored_dir_removed"] = not tmp.exists()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--session-dir", type=Path, default=HERE if (HERE / "archive.json").is_file() else None, required=not (HERE / "archive.json").is_file())
    ap.add_argument("--instrument-root", default=None)
    ap.add_argument("--repo-root", default=None, help="the zynq_fabricmap checkout (default: found from this file or the working directory)")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    try:
        res = rejudge(a.session_dir, instrument_root=a.instrument_root, keep=a.keep)
    except Exception as exc:  # noqa: BLE001 — an internal error is not a verdict
        print(json.dumps({"tool": TOOL, "verdict": "INTERNAL ERROR", "error": f"{type(exc).__name__}: {exc}"}))
        return 3
    text = json.dumps(res, indent=1, sort_keys=True, default=str) + "\n"
    if a.out:
        a.out.write_text(text)
    print(text)
    return 0 if res["verdict"] == "ACCEPT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
