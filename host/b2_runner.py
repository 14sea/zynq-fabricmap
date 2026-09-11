#!/usr/bin/env python3
"""B2 — the board runner. HOST-ONLY UNTIL RULED, and no board work is authorised today.

    b2_runner.py --ruling <whole-of-run json> --provision-ruling <P3-K json>
                 --boundary <principal_boundary json> --out <evidence dir>
                 --pair-first N --pair-count N [--image …] [--manifest …]
                 [--instrument-root …] [--port …] [--key …] [--signer-user …]

Two PROFILES share this preflight and session function, in the preregistration's order (§6):

  B2Q  image qualification and calibration — the B2 image on the QUALIFIED B1 carrier against
       the **S1** manifest; one pair at budget 8 under the `b2-qualification` seed label; the
       session's measured all-self-reporting rate is what S2 pins as the calibration. The
       manifest must NOT yet carry a qualification or a plan.
  B2   map utility — one session per slice of the plan's split, against the **S3** manifest;
       the slice's pairs and seeds are the plan's, never redrawn. The manifest must be
       qualified and carry the pinned plan, and the slice must be one the split gives.

The identity page carries the master seed, the per-arm budget and the flags word with THIS
session's pair slice in its high half (`b2_session.encode_slice`), so a board that decodes a
different slice refuses before it proposes a candidate.

FAIL-CLOSED, in this order, before any board contact. Each is a named refusal:

  the manifest exists, is this schema, and `b2_manifest.verify` passes with the B2 adjudicator
  bound as its re-adjudication (a pluggable verifier with nothing plugged in is not a check);
  the preregistration FROZEN (a null pin is a draft) and the document hashing to it; the image
  pinned, `board_ready`, present and hashing, its build evidence hashing and reporting no
  findings from a clean tree; `firmware/b2/p3_data.h` fresh from its generator; the instrument
  at its pinned commit; the INSTRUMENT PIN TABLE verified (host/b2_pins.py — until that tool
  exists this is a refusal, never a skip); the carrier's bitstream, manifest and build record
  hashing to their pins, the VARIANT, and the B1 carrier's qualification chain RE-VERIFIED
  rather than its flag read; the profile's stage (B2Q: not yet qualified, no plan; B2: qualified
  with a pinned plan whose bytes hash to the manifest) and the plan and prediction accepted by
  the adjudicator's own input guards; the session's pair slice inside the experiment and, for
  B2, one the plan's split actually gives; BOTH rulings present, parseable, unconsumed, naming
  this board, and bound to this session, the frozen prereg, the pinned image and the sha256 of
  THIS manifest file — and the whole-of-run ruling to the master seed; the principal boundary
  fresh and bound to this invocation; `sb`; the evidence directory not existing.

The session function is B1's (`b1_session.run`) with B2's identity check and B2's adjudicator
at `scope="session"` — a session of a longer run is judged as a session, and the run's pooled
primary is `b2_adjudicate --scope run` over every session's log once they all exist.

THE RULING TEXTS BELOW ARE PROPOSALS. The owner writes rulings; if these strings are not the
ones the owner intends to sign, change them here — the runner refuses any other text, so the
two must agree before a board session is possible.

WHAT IS NOT DONE HERE, stated rather than implied:
  * `host/b2_pins.py` (§7 tool 4) does not exist, so `verify_pins` REFUSES. Every preflight
    ends there today. That is the intended state, not an oversight.
  * B2Q's plan, prediction and pair seeds are DERIVED here (`qualification_documents`) from the
    preregistration's §6a constants. They are not pinned in the manifest. If the owner would
    rather S0 recorded them, they belong in `b2_plan`/`b2_manifest` and this function becomes a
    reader — a decision worth making before the §7 package.
  * `b2_session.run` (the reference orchestrator) derives its pair seeds by B2's rule, so it
    cannot produce a B2Q session under B2Q's own exclusion set. The adjudicator can be given
    seeds explicitly (`adjudicate(..., seeds=…)`) and is; the reference orchestrator cannot yet,
    so there is no modelled B2Q session to test the B2Q re-adjudication end to end against.
  * No board session has been run, and none is authorised.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import secrets
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b2_adjudicate as adj  # noqa: E402
import b2_manifest as bman  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402
import b2_session as bsess  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

TOOL_VERSION = "b2_runner.py/0.1.0"
SESSION = "B2"
MANIFEST = bman.MANIFEST
B2_VARIANT = "0x42310001"
IMAGE = REPO_ROOT / "firmware/b2/bsp/out/b2_app.bin"

# Proposals until the owner signs them (module docstring).
RULING_TEXT = "whole-of-run B2 map utility"
QUAL_RULING_TEXT = "whole-of-run B2 image qualification and calibration"
PROVISION_RULING_TEXT = "provisioning P3-K"

# The qualification session's own experiment (preregistration §6a): one pair at budget 8 under
# its own seed label, excluding the frozen sets AND every seed B2 itself will use.
QUAL_LABEL = "b2-qualification"
QUAL_BUDGET = 8
QUAL_PAIRS = 1
WATCHDOG_LOAD, WATCHDOG_PRESCALER = 1250000035, 7


def deadline_s(records: int, rate_per_hour: float) -> float:
    """The preregistration's frozen formula (§2, `b2_plan.DEADLINE_FORMULA`)."""
    return 1.25 * records * 3600 / rate_per_hour + 600


class Refusal(Exception):
    """Fail-closed: a named reason why this invocation does not reach a board."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualification_seeds(manifest: dict) -> list[tuple[int, int]]:
    """B2Q's pairs: its own label's stream, excluding the frozen archived sets and every seed
    the B2 experiment itself uses, so the calibration session can never share a landscape with
    the experiment it calibrates. (Kept here with the profile that needs it; if the owner wants
    it pinned into the manifest it belongs in `b2_plan`.)"""
    exclusion, _ = bp.frozen_seed_exclusion()
    used = {s for pair in manifest["seeds"]["pairs"] for s in pair}
    master = bs.master_seed(QUAL_LABEL, manifest["instrument"]["psoracle_commit"])
    return bs.pair_seeds(master, QUAL_PAIRS, exclude=frozenset(exclusion) | used)


def qualification_master(manifest: dict) -> int:
    return bs.master_seed(QUAL_LABEL, manifest["instrument"]["psoracle_commit"])


SEARCH = {"session": SESSION, "ruling_text": RULING_TEXT, "stage": "S3", "tool": TOOL_VERSION}
QUALIFICATION = {"session": bman.QUAL_SESSION, "ruling_text": QUAL_RULING_TEXT, "stage": "S1",
                 "tool": "b2_runner.py/0.1.0 (B2Q)"}


# ------------------------------------------------------------------ the rulings


def parse_ruling(path: Path, text: str, manifest: dict) -> dict:
    consumed = path.with_name(path.name + ".consumed")
    if consumed.exists():
        raise Refusal(f"the ruling {path} was consumed ({consumed.read_text().strip()[:80]})")
    try:
        r = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise Refusal(f"no readable ruling at {path}: {exc}") from None
    if not isinstance(r, dict):
        raise Refusal(f"the ruling at {path} is not a JSON object")
    for f in ("ruling", "boardid", "granted_by", "date"):
        if not r.get(f):
            raise Refusal(f"ruling {path} lacks {f!r}")
    if r["ruling"] != text:
        raise Refusal(f"ruling text {r['ruling']!r} != {text!r}")
    want_board = (manifest.get("board") or {}).get("boardid")
    if want_board is not None and r["boardid"] != want_board:
        raise Refusal(f"ruling names board {r['boardid']!r}, this stage is {want_board!r}")
    return r


def bind_ruling(ruling: dict, text: str, session: str, prereg_sha: str, image_sha: str,
                manifest_sha: str, master_seed: int | None) -> None:
    """The binding the manifest itself declares under `rulings_binding` (§8): a ruling that does
    not name this session, this preregistration, this image and THIS manifest file is not this
    session's ruling."""
    want = {"session": session, "prereg_sha256": prereg_sha, "image_sha256": image_sha,
            "b2_manifest_sha256": manifest_sha}
    if master_seed is not None:
        want["master_seed"] = master_seed
    for k, v in want.items():
        if k not in ruling:
            raise Refusal(f"ruling {text!r} is not bound: it lacks {k!r}")
        got = ruling[k]
        if k == "master_seed" and isinstance(got, str):
            try:
                got = int(got, 0)
            except ValueError:
                raise Refusal(f"ruling {text!r}: master_seed {got!r} is not a number") from None
        if got != v:
            raise Refusal(f"ruling {text!r} is bound to {k} = {got!r}, this session needs {v!r}")


# ------------------------------------------------------------------ the instrument pin table


def verify_pins(manifest: dict, root: Path) -> dict:
    """`host/b2_pins.py` is tool 4 of the §7 package and does not exist yet. Until it does this
    is a REFUSAL, not a skip: a board session whose instrument pin table was never checked is
    exactly the session this runner exists to prevent."""
    try:
        import b2_pins  # noqa: F401
    except ImportError:
        raise Refusal("host/b2_pins.py is not written yet: no board contact without the "
                      "instrument pin table (§7 tool 4)") from None
    return b2_pins.verify(manifest=manifest, root=root)


# ------------------------------------------------------------------ preflight


def qualification_documents(manifest: dict) -> tuple[dict, dict, list]:
    """B2Q's OWN plan, prediction and pair seeds (preregistration §6a): one pair at budget 8 over
    the same frozen map and fitness, under the qualification seed label. Derived here, not
    pinned — the manifest pins B2's; if the owner wants B2Q's seeds pinned they belong in S0."""
    fid = manifest["experiment"]["fitness"]
    map_sha = manifest["map"]["canonical_json_sha256"]
    seeds = qualification_seeds(manifest)
    plan = {"schema": "b2_plan", "session": bman.QUAL_SESSION, "fitness": fid,
            "budget_per_arm": QUAL_BUDGET, "pairs": QUAL_PAIRS, "map": {"sha256": map_sha},
            "seed_derivation": {"label": QUAL_LABEL, "master_seed": qualification_master(manifest),
                                "rule": "first 4 bytes of sha256(label|instrument commit); the frozen "
                                        "archived sets AND every B2 pair seed excluded"}}
    prediction = bp.build_prediction(fid, QUAL_BUDGET, seeds, map_sha)
    return plan, prediction, seeds


def readjudicator(manifest: dict, consts: dict | None = None):
    """The callable `b2_manifest.verify`/`qualify` take to RE-ADJUDICATE the pinned qualification
    evidence — `(evidence_dir, manifest_at_run)`. The evidence is a B2Q session, so it is judged
    against B2Q's own documents and B2Q's own seeds, never against B2's plan. Session-scoped:
    B2Q is one pair of its own little experiment, and claims no primary."""
    plan, prediction, seeds = qualification_documents(manifest)

    def again(evidence_dir, manifest_at_run=None) -> dict:
        log = json.loads((Path(evidence_dir) / "run_log.json").read_text())
        return adj.adjudicate([log], plan, prediction, consts=consts, scope="session", seeds=seeds)
    return again


def preflight(a, profile: dict = SEARCH, pins_verify=verify_pins, readjudicate=None) -> dict:
    """`pins_verify` and `readjudicate` are the two seams a test may replace; both default to
    the real thing, and neither default is a skip."""
    session = profile["session"]
    manifest_path = Path(a.manifest)
    if not manifest_path.is_file():
        raise Refusal(f"no B2 manifest at {manifest_path}: the manifest does not exist until the "
                      f"image does (S0), and no board session exists without it")
    try:
        manifest = json.loads(manifest_path.read_text())
    except ValueError as exc:
        raise Refusal(f"the B2 manifest is not readable JSON: {exc}") from None
    if not isinstance(manifest, dict) or manifest.get("schema") != bman.SCHEMA:
        raise Refusal("the manifest is not a b2_manifest document")
    manifest_sha = _sha(manifest_path)

    prereg = manifest.get("prereg") or {}
    if not prereg.get("sha256") or not prereg.get("frozen"):
        raise Refusal("B2's preregistration is not frozen (S1): host-only until the owner freezes it")
    prereg_path = REPO_ROOT / prereg["path"]
    if not prereg_path.is_file() or _sha(prereg_path) != prereg["sha256"]:
        raise Refusal(f"{prereg['path']} does not hash to the frozen preregistration")

    image = manifest.get("image") or {}
    if not image.get("sha256"):
        raise Refusal("the manifest pins no image")
    if not image.get("board_ready"):
        raise Refusal("the B2 image is not marked board_ready (the compatibility review and the freeze come first)")
    image_path = Path(a.image)
    if not image_path.is_file():
        raise Refusal(f"no application image at {image_path}")
    image_sha = _sha(image_path)
    if image_sha != image["sha256"]:
        raise Refusal(f"the image is not the pinned one: {image_sha[:16]}… != {image['sha256'][:16]}…")

    # the stage the profile requires, BEFORE the manifest's own verifier runs over it
    if profile is QUALIFICATION:
        if manifest.get("qualified") or manifest.get("qualification"):
            raise Refusal("this manifest is already qualified: B2Q runs against the S1 manifest")
        if manifest.get("plan"):
            raise Refusal("this manifest already carries a plan: B2Q precedes S3")
        plan_doc, prediction_doc = None, None
    else:
        if not manifest.get("qualified") or not manifest.get("qualification"):
            raise Refusal("the manifest is not qualified: B2Q and S2 come before any B2 session")
        pinned = manifest.get("plan")
        if not pinned:
            raise Refusal("the manifest pins no plan (S3): a B2 session has no slice without it")
        plan_path = REPO_ROOT / pinned["path"]
        pred_path = REPO_ROOT / pinned["prediction_path"]
        for path, want, what in ((plan_path, pinned["sha256"], "plan"),
                                 (pred_path, pinned["prediction_sha256"], "prediction")):
            if not path.is_file() or _sha(path) != want:
                raise Refusal(f"the pinned {what} at {path} does not hash to the manifest")
        plan_doc = json.loads(plan_path.read_text())
        prediction_doc = json.loads(pred_path.read_text())
        if plan_doc.get("session") != SESSION:
            raise Refusal(f"the pinned plan is for session {plan_doc.get('session')!r}, this runner is {SESSION!r}")
        try:                                   # the adjudicator's own input guards, before the board
            adj.check_plan(plan_doc)
            adj.check_prediction(prediction_doc, plan_doc)
        except adj.Refusal as exc:
            raise Refusal(f"the pinned plan/prediction: {exc}") from None

    try:                                       # the whole frozen chain, re-hashed, every call
        bman.verify(manifest, readjudicate=readjudicate or readjudicator(manifest))
    except bman.Refusal as exc:
        raise Refusal(f"manifest: {exc}") from None

    be = image.get("build_evidence") or {}
    be_path = REPO_ROOT / be.get("path", "")
    if not be.get("sha256") or not be_path.is_file() or _sha(be_path) != be["sha256"]:
        raise Refusal("the image's build evidence does not hash to its pin")
    import b2_build_evidence as bbe  # noqa: E402
    findings = bbe.verify_findings(json.loads(be_path.read_text()))
    if findings:
        raise Refusal(f"the image's build evidence does not verify: {findings[0]}")
    import gen_b2_data as gen  # noqa: E402
    if gen.render_b2(require_git=True) != (REPO_ROOT / "firmware/b2/p3_data.h").read_text():
        raise Refusal("firmware/b2/p3_data.h is not fresh from its generator")

    try:
        verified = inst.bind(a.instrument_root)
    except inst.InstrumentRefusal as exc:
        raise Refusal(f"instrument: {exc}") from None
    if verified.get("psoracle_commit") != manifest["instrument"]["psoracle_commit"]:
        raise Refusal("the instrument is not at the commit this manifest pins")
    pins = pins_verify(manifest, a.instrument_root)

    car = manifest["carrier"]
    if car.get("variant") != B2_VARIANT:
        raise Refusal("the manifest's carrier variant is not the qualified carrier's contract word")
    import b1_qualification as bq  # noqa: E402
    b1_manifest = json.loads(bman.B1_MANIFEST.read_text())
    try:                                       # the B1 carrier's chain, re-adjudicated, never its flag
        bq.verify(b1_manifest, require_git=True, instrument_root=a.instrument_root)
    except bq.QualificationRefusal as exc:
        raise Refusal(f"the B1 carrier this image runs on is not qualified: {exc}") from None
    bitstream = REPO_ROOT / b1_manifest["carrier"]["bitstream"]
    if not bitstream.is_file() or _sha(bitstream) != car["bitstream_sha256"]:
        raise Refusal("the carrier bitstream does not hash to the manifest's pin")
    carrier_manifest_path = REPO_ROOT / b1_manifest["carrier"]["carrier_manifest"]["path"]
    if _sha(carrier_manifest_path) != b1_manifest["carrier"]["carrier_manifest"]["sha256"]:
        raise Refusal("the carrier manifest does not hash to the B1 manifest's pin")

    # the session's slice and its experiment
    if profile is QUALIFICATION:
        master = qualification_master(manifest)
        budget, pairs_total = QUAL_BUDGET, QUAL_PAIRS
        first, count = 0, QUAL_PAIRS
        seeds = qualification_seeds(manifest)
        if a.pair_first not in (None, 0) or a.pair_count not in (None, QUAL_PAIRS):
            raise Refusal(f"B2Q runs {QUAL_PAIRS} pair at budget {QUAL_BUDGET}: it takes no slice")
    else:
        master = plan_doc["seed_derivation"]["master_seed"]
        budget, pairs_total = plan_doc["budget_per_arm"], plan_doc["pairs"]
        if a.pair_first is None or a.pair_count is None:
            raise Refusal("a B2 session needs --pair-first and --pair-count: the plan's split assigns them")
        first, count = a.pair_first, a.pair_count
        if first < 0 or count <= 0 or first + count > pairs_total:
            raise Refusal(f"the slice ({first}, {count}) does not lie inside the experiment's {pairs_total} pairs")
        split_entry = slice_in_split(plan_doc, first, count)
        if split_entry is None:
            raise Refusal(f"the slice ({first}, {count}) is not one the plan's split gives")
        seeds = bsess.pair_seeds(master, pairs_total)
        if master != manifest["seeds"]["master_seed"]:
            raise Refusal("the plan's master seed is not the manifest's")

    ruling = parse_ruling(a.ruling, profile["ruling_text"], manifest)
    if a.provision_ruling is None:
        raise Refusal("--provision-ruling is mandatory: no `provisioning P3-K` ruling, no board contact")
    pk = parse_ruling(a.provision_ruling, PROVISION_RULING_TEXT, manifest)
    bind_ruling(ruling, profile["ruling_text"], session, prereg["sha256"], image_sha, manifest_sha,
                master if profile is SEARCH else None)
    bind_ruling(pk, PROVISION_RULING_TEXT, session, prereg["sha256"], image_sha, manifest_sha, None)

    if shutil.which("sb") is None:
        raise Refusal("`sb` is not installed")
    boundary = json.loads(Path(a.boundary).read_text())
    from validators import records  # noqa: E402
    records.boundary_established(boundary, time.time())
    me = pwd.getpwuid(os.getuid()).pw_name
    if boundary["runner_user"] != me:
        raise Refusal(f"principal boundary: runner_user {boundary['runner_user']!r} is not this OS user {me!r}")
    if boundary["signer_user"] != a.signer_user:
        raise Refusal(f"principal boundary: --signer-user {a.signer_user!r} is not the record's "
                      f"{boundary['signer_user']!r}")
    want_key = os.path.normpath(os.path.join(boundary["key_store"], "K.bin"))
    if os.path.normpath(str(a.key)) != want_key:
        raise Refusal(f"principal boundary: --key {a.key} is not the record's key store's {want_key}")
    if Path(a.out).exists():
        raise Refusal(f"{a.out} exists; evidence is never replaced")

    import l3_runner as l3  # noqa: E402
    import l6_schedule as ls  # noqa: E402
    l6m_path = Path(a.instrument_root) / "manifests/l6_manifest.json"
    l6m = json.loads(l6m_path.read_text())
    wd = l6m["pinned_at_build"]
    if not wd["watchdog_enabled"] or wd["watchdog_load_value"] != WATCHDOG_LOAD \
            or wd["watchdog_prescaler"] != WATCHDOG_PRESCALER:
        raise Refusal("D-s1: the watchdog pins are not the instrument's")
    base_flags = ls.flags_for(ls.MODE_ABBA, watchdog=True, rec_control=True, sign_control=True)
    try:
        flags = bsess.encode_slice(base_flags, pairs_total, first, count)
    except ValueError as exc:
        raise Refusal(f"the identity page cannot carry this slice: {exc}") from None
    records_expected = bsess.records(count, budget)
    if profile is SEARCH:
        if split_entry.get("records") != records_expected:
            raise Refusal(f"the plan's split says {split_entry.get('records')} records for this slice, "
                          f"the record arithmetic says {records_expected}")
        timeout = float(split_entry["deadline_s"])
        rate_note = {"source": "the plan's split, from the B2Q calibration",
                     "rate_per_hour": plan_doc["session_split"].get("rate_per_hour")}
    else:
        if a.qual_rate_per_hour is None:
            raise Refusal("B2Q needs --qual-rate-per-hour: the calibration session's own deadline is a "
                          "PLANNING bound (the rate it measures does not exist yet)")
        if not (isinstance(a.qual_rate_per_hour, float) and a.qual_rate_per_hour > 0):
            raise Refusal(f"--qual-rate-per-hour {a.qual_rate_per_hour!r} is not a positive rate")
        timeout = deadline_s(records_expected, a.qual_rate_per_hour)
        rate_note = {"source": "a planning bound given to this invocation; B2Q MEASURES the rate",
                     "rate_per_hour": a.qual_rate_per_hour}
    audit_seqs = set(range(1, records_expected + 1))        # all-self-reporting: every record audited
    wire = l6m["protocol"]["wire"]
    expected_frames = ls.expected_frames(records_expected, audit_seqs, wire)
    crc_budget = ls.crc_budget(expected_frames["total"])
    session_plan = {
        "session": session, "mode": bs.ENGINE_VERSION, "master_seed": master, "n": budget,
        "schedule": [], "audit_policy": bp.AUDIT_POLICY, "audit_seqs": audit_seqs,
        "pair_first": first, "pair_count": count, "pairs_total": pairs_total, "flags": flags,
        "expected_records": records_expected, "expected_frames": expected_frames,
        "crc_budget": crc_budget, "bad_frame_budget": crc_budget,
        "crc_formula": "ceil(4 x expected_total / 1000) (D-s4), from the instrument's l6_schedule",
        "session_timeout_s": timeout, "deadline_formula": bp.DEADLINE_FORMULA, "deadline_rate": rate_note,
        "protocol": wire,
        "rules_version": "b2/v0.1 over L6 v0.7 rules", "bad_frame_policy": "ledger", "hb_rule": "v07",
        "rec_retry_control": True,
        "inputs": expected_inputs(manifest, profile),
        "binding": {"image_sha256": image_sha, "prereg_sha256": prereg["sha256"], "session": session,
                    "schedule_mode": bs.ENGINE_VERSION, "master_seed": master,
                    "b2_manifest_sha256": manifest_sha, "psoracle_commit": verified["psoracle_commit"],
                    "map_canonical_json_sha256": manifest["map"]["canonical_json_sha256"],
                    "fitness_id": manifest["experiment"]["fitness"], "budget_per_arm": budget,
                    "pair_first": first, "pair_count": count},
    }
    return {"profile": profile, "ruling": ruling, "provision_ruling_parsed": pk, "manifest": manifest,
            "manifest_sha256": manifest_sha, "manifest_path": manifest_path, "ruling_path": Path(a.ruling),
            "provision_ruling_path": Path(a.provision_ruling), "pins": pins,
            "carrier": json.loads(carrier_manifest_path.read_text()), "bitstream": bitstream,
            "image": image_path, "image_sha256": image_sha, "plan": session_plan,
            "round_plan": plan_doc, "prediction": prediction_doc, "seeds": seeds,
            "signer": l3.SubprocessSigner(a.key, script=REPO_ROOT / "host/b1_sign_arm.py",
                                          signer_user=a.signer_user),
            "provision_execute": True, "provision_ruling": a.provision_ruling,
            "token": secrets.token_hex(16), "instrument": verified, "instrument_root": a.instrument_root,
            "l6_manifest": l6m, "heartbeat_s": l6m["protocol"]["heartbeat_s"],
            "seed_nonce": int(json.loads(bman.B1_MANIFEST.read_text())["carrier"]["nonce_seed"], 16)}


def slice_in_split(plan: dict, first: int, count: int) -> dict | None:
    """The split entry for this slice, or None. A B2 session runs a slice the plan's split
    actually gives — never an arbitrary one — and the entry carries the session's own deadline.
    Until B2Q measures the rate the split is UNDETERMINED and no slice is licensed at all."""
    split = plan.get("session_split")
    if not isinstance(split, dict) or split.get("status") != "DETERMINED":
        return None
    sessions = split.get("sessions")
    if not isinstance(sessions, list):
        return None
    want = list(range(first, first + count))
    for entry in sessions:
        if isinstance(entry, dict) and entry.get("pairs") == want:
            return entry
    return None


def expected_inputs(manifest: dict, profile: dict) -> dict:
    """What the session's run log must name as its inputs: the pinned plan and prediction (a
    qualification session has neither) and the manifest this session was run against."""
    pinned = manifest.get("plan") or {}
    return {"plan_sha256": pinned.get("sha256"), "prediction_sha256": pinned.get("prediction_sha256"),
            "b2_manifest_sha256": bman.manifest_sha256(manifest), "stage": profile["stage"]}


def identity_check_for(cfg: dict):
    """The B2 IDENT (app_identity 1.5.0) is verified BEFORE it is acknowledged: the engine, the
    map digest, the fitness, the budget, the seed, the slice, the carrier and the protocol."""
    plan, manifest = cfg["plan"], cfg["manifest"]

    def check(ident: dict) -> list[str]:
        out = []
        want = {"search_version": bs.ENGINE_VERSION,
                "map_sha256": manifest["map"]["canonical_json_sha256"],
                "operator_data_sha256": manifest["map"]["canonical_json_sha256"],
                "fitness_id": manifest["experiment"]["fitness"],
                "budget_per_arm": plan["n"], "master_seed": plan["master_seed"],
                "pairs_total": plan["pairs_total"], "pair_first": plan["pair_first"],
                "pair_count": plan["pair_count"], "carrier_variant": B2_VARIANT,
                "carrier_sha256": manifest["carrier"]["bitstream_sha256"],
                "universe_sha256": manifest["universe"]["sha256"],
                "rec_retry_control": True, "sign_retry_control": True}
        for k, v in want.items():
            if ident.get(k) != v:
                out.append(f"IDENT {k}: {ident.get(k)!r} != {v!r}")
        for forbidden in ("carto_version", "probe_budget"):
            if forbidden in ident:
                out.append(f"IDENT {forbidden}: this image runs no cartographer and issues no probes")
        if ident.get("findings"):
            out.append(f"IDENT findings: {ident['findings']}")
        return out
    return check


def adjudication_for(cfg: dict):
    """A session is adjudicated as a SESSION; the run's pooled primary is a later
    `b2_adjudicate --scope run` over every session's log."""
    def judge(evidence_dir: Path) -> dict:
        if cfg["round_plan"] is None:                     # B2Q has no pinned plan yet (§8: S3 follows)
            return {"tool": adj.TOOL_VERSION, "scope": "session", "outcome":
                    "NOT ADJUDICATED HERE: B2Q precedes the plan; its record is reconstructed at S2",
                    "findings": [], "kills": []}
        log = json.loads((Path(evidence_dir) / "run_log.json").read_text())
        return adj.adjudicate([log], cfg["round_plan"], cfg["prediction"], scope="session")
    return judge


def run_session(session, out_dir: Path, ruling: dict, cfg: dict) -> dict:
    import b1_session  # noqa: E402
    return b1_session.run(session, out_dir, ruling, cfg, identity_check_for(cfg),
                          adjudication_for(cfg), cfg["profile"]["tool"])


def main(argv=None, profile: dict = SEARCH) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ruling", type=Path, required=True)
    ap.add_argument("--provision-ruling", type=Path, default=None)
    ap.add_argument("--boundary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pair-first", type=int, default=None)
    ap.add_argument("--pair-count", type=int, default=None)
    ap.add_argument("--qual-rate-per-hour", type=float, default=None,
                    help="B2Q only: the PLANNING rate its deadline is computed from (it measures the real one)")
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--instrument-root", type=Path, default=inst.DEFAULT_ROOT)
    ap.add_argument("--image", type=Path, default=IMAGE)
    ap.add_argument("--key", type=Path, default=Path("/var/lib/p3signer/keys/K.bin"))
    ap.add_argument("--signer-user", default="p3signer")
    ap.add_argument("--port", default="/dev/ebaz-uart")
    a = ap.parse_args(argv)
    try:
        cfg = preflight(a, profile)
    except (Refusal, ValueError, OSError, KeyError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"REFUSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    rc, outcome = execute(a, cfg)
    print(outcome, file=sys.stderr if outcome != "PASS" else sys.stdout)
    return rc


def execute(a, cfg: dict) -> tuple[int, str]:
    """The order after a passed preflight, FIXED as B1's: (1) the evidence directory; (2) the
    session artifacts — the manifest bytes and both rulings — archived and verified against what
    the preflight parsed, a failure here being a REFUSED with no ruling consumed and no port
    opened; (3) the whole-of-run ruling claimed; (4) the port opened — the FIRST board contact;
    (5) the session."""
    import b1_qualification as bq  # noqa: E402
    import board_session as bsn  # noqa: E402
    import l3_runner as l3  # noqa: E402
    import pcap_probe_runner as pr  # noqa: E402
    try:
        a.out.mkdir(parents=True)
        bq.write_session_artifacts(a.out, cfg["manifest_path"], cfg["ruling_path"], cfg["provision_ruling_path"],
                                   cfg["manifest_sha256"],
                                   expected_rulings=(cfg["ruling"], cfg["provision_ruling_parsed"]))
    except (bq.QualificationRefusal, OSError, ValueError) as exc:
        return 2, f"REFUSED: session artifacts not archived: {exc}"
    consumed = pr.claim_ruling(a.ruling)
    l3._install_sigterm()
    outcome = "CRASHED before a summary was written"
    try:
        transport = bsn.SerialTransport(a.port)
        try:
            outcome = run_session(bsn.BoardSession(transport), a.out, cfg["ruling"], cfg)["outcome"]
        finally:
            transport.close()
    except bsn.SessionRefusal as exc:
        outcome = f"REFUSED: {exc}"
    finally:
        pr.record_outcome(consumed, outcome)
        if a.provision_ruling:
            l3._record_pk(a.provision_ruling, outcome)
    return (0 if outcome == "PASS" else 1), outcome


if __name__ == "__main__":
    sys.exit(main())
