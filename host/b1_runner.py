#!/usr/bin/env python3
"""B1 — the board runner. Ruling text RULING_TEXT. HOST-ONLY UNTIL RULED.

    b1_runner.py --ruling <whole-of-run B1 cartography json> --provision-ruling <P3-K json>
                 --boundary <principal_boundary json> --out <evidence dir> --image <b1_app.bin>
                 [--manifest …] [--instrument-root …] [--port …] [--key …] [--signer-user …]

Two PROFILES share this preflight and session function: MAPPING (this script; session "B1",
ruling `whole-of-run B1 cartography`, the manifest's plan/prediction, the carrier's
qualification evidence re-verified) and QUALIFICATION (host/b1q_runner.py; session "B1Q",
ruling `whole-of-run B1 carrier qualification`, the manifest's qualification plan, budget 9,
no qualification required of the carrier — it is what the session produces). Each session
needs its OWN `provisioning P3-K` ruling bound to its session name (a ruling is consumed once).

One session, "B1": the B1 image (the instrument's successor: cartographer instead of search)
on the B1 carrier (docs/b1_carrier_contract.md; qualified under its own ruling first), the identity page carrying the plan's seed and budget, the
ALL-SELF-REPORTING audit policy, the watchdog and both seq-1 controls armed, the runner's
deadline from the plan. The console loop, the notary relay, the collector, the reader and
the timeline are the instrument's, bound read-only; the session function is the round 1′
runner's (itself `run_l6` copied) with B1's identity check, plan and adjudication.

FAIL-CLOSED, in this order, before any board contact: the ruling texts; a P3-K ruling
present, parseable and unconsumed; the manifest's FROZEN preregistration hash (null = DRAFT
= refused) and the document hashing to it; the plan and the prediction hashing to the
manifest's pins; the instrument at its pinned commit, clean, every pinned file hashing;
the image file hashing to the manifest's pin and marked board_ready; the build evidence
hashing to its pin with a byte-identical rebuild; the data header fresh from its generator
and free of the operator tables; the carrier manifest and bitstream hashing to their pins;
the universe digest; the carrier's qualification evidence re-verified and RE-ADJUDICATED
(mapping profile; host/b1_qualification.py — a flag is nothing); BOTH rulings bound to this
session, the frozen prereg, the B1 image and the sha256 of THIS manifest file (and the
whole-of-run ruling to the plan's master seed); the principal boundary < 6 h and bound to
this invocation; `sb`; the evidence directory not existing. Each is a named refusal.
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
import b1_adjudicate as adj  # noqa: E402
import b1_pins as pins_mod  # noqa: E402
import b1_qualification as bq  # noqa: E402
import b1q_adjudicate as qadj  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

TOOL_VERSION = "b1_runner.py/0.2.0"
RULING_TEXT = "whole-of-run B1 cartography"
PROVISION_RULING_TEXT = "provisioning P3-K"
SESSION = "B1"
MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"
WATCHDOG_LOAD, WATCHDOG_PRESCALER = 1250000035, 7

# the two profiles (module docstring)
MAPPING = {"session": SESSION, "ruling_text": RULING_TEXT, "plan_section": "plan", "require_qualification": True,
           "adjudicate": adj.adjudicate, "tool": TOOL_VERSION}
QUALIFICATION = {"session": qadj.SESSION, "ruling_text": qadj.RULING_TEXT, "plan_section": "qualification_plan",
                 "require_qualification": False, "adjudicate": qadj.adjudicate, "tool": "b1q_runner.py/0.1.0"}


class Refusal(Exception):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind_ruling(ruling: dict, text: str, prereg_sha: str, image_sha: str, manifest_sha: str, master_seed: int | None,
                session: str = SESSION) -> None:
    want = {"session": session, "prereg_sha256": prereg_sha, "image_sha256": image_sha, "b1_manifest_sha256": manifest_sha}
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


def preflight(a, profile: dict = MAPPING) -> dict:
    manifest = json.loads(a.manifest.read_text())
    manifest_sha = _sha(a.manifest)
    session, ruling_text = profile["session"], profile["ruling_text"]

    def parse(path: Path, text: str) -> dict:
        consumed = path.with_name(path.name + ".consumed")
        if consumed.exists():
            raise Refusal(f"the ruling {path} was consumed ({consumed.read_text().strip()[:80]})")
        try:
            r = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise Refusal(f"no readable ruling at {path}: {exc}") from exc
        for f in ("ruling", "boardid", "granted_by", "date"):
            if not r.get(f):
                raise Refusal(f"ruling {path} lacks {f!r}")
        if r["ruling"] != text:
            raise Refusal(f"ruling text {r['ruling']!r} != {text!r}")
        if r["boardid"] != manifest["board"]["boardid"]:
            raise Refusal(f"ruling names board {r['boardid']!r}, this stage is {manifest['board']['boardid']!r}")
        return r
    ruling = parse(a.ruling, ruling_text)
    if a.provision_ruling is None:
        raise Refusal("--provision-ruling is mandatory: no `provisioning P3-K` ruling, no board contact")
    pk = parse(a.provision_ruling, PROVISION_RULING_TEXT)
    pinned_prereg = manifest["prereg"]["sha256"]
    if not pinned_prereg:
        raise Refusal("B1's preregistration is not frozen (manifest prereg.sha256 is null): host-only until the owner freezes it")
    prereg_path = REPO_ROOT / manifest["prereg"]["path"]
    if not prereg_path.is_file() or _sha(prereg_path) != pinned_prereg:
        raise Refusal(f"{manifest['prereg']['path']} does not hash to the frozen preregistration")
    if profile["plan_section"] == "plan":
        plan_path = REPO_ROOT / manifest["plan"]["path"]
        pred_path = REPO_ROOT / manifest["prediction"]["path"]
        pinned_seed = manifest["seeds"]["master_seed"]
    else:
        qp = manifest.get("qualification_plan")
        if not qp:
            raise Refusal("the manifest pins no qualification plan")
        plan_path, pred_path, pinned_seed = REPO_ROOT / qp["path"], REPO_ROOT / qp["prediction_path"], qp["master_seed"]
    try:
        if profile["plan_section"] == "plan":
            adj.check_pins(manifest, plan_path, pred_path)  # plan, prediction AND the pin table of every adjudication-critical file
        else:
            qadj.check_q_pins(manifest, plan_path, pred_path, None, None, None)
    except adj.Refusal as exc:
        raise Refusal(str(exc)) from None
    plan = json.loads(plan_path.read_text())
    prediction = json.loads(pred_path.read_text())
    if plan.get("session") != session:
        raise Refusal(f"the pinned plan is for session {plan.get('session')!r}, this runner is {session!r}")
    try:
        verified = inst.bind(a.instrument_root, manifest=manifest)
    except inst.InstrumentRefusal as exc:
        raise Refusal(f"instrument: {exc}") from None
    import l3_runner as l3  # noqa: E402
    import l6_schedule as ls  # noqa: E402
    from validators import records  # noqa: E402
    root = a.instrument_root
    # the image: bytes, pin, board_ready, build evidence, header freshness
    pinned_image = manifest["image"]["sha256"]
    if not a.image.is_file():
        raise Refusal(f"no application image at {a.image}")
    image_sha = _sha(a.image)
    if image_sha != pinned_image:
        raise Refusal(f"the image is not the pinned one: {image_sha[:16]}… != {pinned_image[:16]}…")
    if not manifest["image"].get("board_ready"):
        raise Refusal("the B1 image is not marked board_ready (the owner's compatibility review and freeze come first)")
    be = manifest["image"]["build_evidence"]
    be_path = REPO_ROOT / be["path"]
    if not be_path.is_file() or _sha(be_path) != be["sha256"]:
        raise Refusal("the build evidence does not hash to its pin")
    ev = json.loads(be_path.read_text())
    if ev["image"]["sha256"] != pinned_image or not ev["reproducibility"].get("reproduced_byte_identical"):
        raise Refusal("the build evidence does not record a byte-identical rebuild of the pinned image")
    import gen_b1_data as gen  # noqa: E402
    if gen.render_b1(require_git=True) != (REPO_ROOT / "firmware/b1/p3_data.h").read_text():
        raise Refusal("firmware/b1/p3_data.h is not fresh from its generator")
    l6m_path = root / "manifests/l6_manifest.json"
    if _sha(l6m_path) != manifest["instrument"]["l6_manifest_sha256"]:
        raise Refusal("the instrument's L6 manifest does not hash to this stage's pin")
    l6m = json.loads(l6m_path.read_text())
    wd = l6m["pinned_at_build"]
    if not wd["watchdog_enabled"] or wd["watchdog_load_value"] != WATCHDOG_LOAD or wd["watchdog_prescaler"] != WATCHDOG_PRESCALER:
        raise Refusal("D-s1: the watchdog pins are not the instrument's")
    car = manifest["carrier"]                              # the B1 carrier (builds/b1), not the instrument's
    car_manifest, car_bit = REPO_ROOT / car["carrier_manifest"]["path"], REPO_ROOT / car["bitstream"]
    if not car_manifest.is_file() or _sha(car_manifest) != car["carrier_manifest"]["sha256"]:
        raise Refusal("the B1 carrier manifest does not hash to the pin")
    build_rec = REPO_ROOT / car["build_record"]["path"]
    if not build_rec.is_file() or _sha(build_rec) != car["build_record"]["sha256"]:
        raise Refusal("the B1 carrier build record does not hash to the pin")
    if json.loads(build_rec.read_text()).get("bitstream_sha256") != car["bitstream_sha256"]:
        raise Refusal("the B1 carrier build record names another bitstream than the pin")
    if not car_bit.is_file() or _sha(car_bit) != car["bitstream_sha256"]:
        raise Refusal("the B1 carrier bitstream does not hash to the pin")
    if car.get("variant") != adj.B1_VARIANT:
        raise Refusal("the manifest's carrier variant is not the B1 gate contract word")
    if profile["require_qualification"]:
        try:                                         # the evidence chain, re-adjudicated — never the flag
            bq.verify(manifest, require_git=True, instrument_root=root)
        except bq.QualificationRefusal as exc:
            raise Refusal(f"the B1 carrier is not qualified: {exc} (docs/b1_carrier_qualification.md §3 comes first)") from None
        if not car.get("qualified"):
            raise Refusal("the manifest's carrier.qualified flag disagrees with its qualification evidence (refresh the manifest)")
    hdr = (REPO_ROOT / "firmware/b1/p3_data.h").read_text()
    if f'B1_UNIVERSE_SHA256 "{manifest["universe"]["sha256"]}"' not in hdr:
        raise Refusal("the header's universe digest is not the manifest's")
    if plan["master_seed"] != pinned_seed:
        raise Refusal("the plan's master seed is not the manifest's")
    bind_ruling(ruling, ruling_text, pinned_prereg, pinned_image, manifest_sha, plan["master_seed"], session)
    bind_ruling(pk, PROVISION_RULING_TEXT, pinned_prereg, pinned_image, manifest_sha, None, session)
    if shutil.which("sb") is None:
        raise Refusal("`sb` is not installed")
    carrier = json.loads(car_manifest.read_text()); records.validate(carrier)
    boundary = json.loads(a.boundary.read_text())
    records.boundary_established(boundary, time.time())
    me = pwd.getpwuid(os.getuid()).pw_name
    if boundary["runner_user"] != me:
        raise Refusal(f"principal boundary: the record's runner_user {boundary['runner_user']!r} is not this OS user {me!r}")
    if boundary["signer_user"] != a.signer_user:
        raise Refusal(f"principal boundary: --signer-user {a.signer_user!r} is not the record's {boundary['signer_user']!r}")
    want_key = os.path.normpath(os.path.join(boundary["key_store"], "K.bin"))
    if os.path.normpath(str(a.key)) != want_key:
        raise Refusal(f"principal boundary: --key {a.key} is not the record's key store's {want_key}")
    if a.out.exists():
        raise Refusal(f"{a.out} exists; evidence is never replaced")
    flags = ls.flags_for(ls.MODE_ABBA, watchdog=True, rec_control=True, sign_control=True)
    if flags != plan["flags"]:
        raise Refusal("the plan's flags word is not the one this runner would write")
    session_plan = {"session": session, "mode": "carto-v1", "master_seed": plan["master_seed"], "n": plan["budget"],
                    "schedule": [], "audit_policy": plan["audit_policy"], "audit_seqs": set(plan["audit_seqs"]),
                    "expected_frames": plan["expected_frames"], "crc_budget": plan["crc_budget"], "crc_formula": plan["crc_formula"],
                    "session_timeout_s": float(plan["session_timeout_s"]),
                    "inputs": {**expected_inputs(manifest, profile), "settle_polls_median_calibration": [16.0]},
                    "rules_version": "b1/v0.2 over L6 v0.7 rules", "bad_frame_policy": "ledger",
                    "bad_frame_budget": plan["bad_frame_budget"], "hb_rule": "v07", "protocol": plan["protocol"],
                    "rec_retry_control": True, "flags": flags,
                    "binding": {"image_sha256": image_sha, "prereg_sha256": pinned_prereg, "protocol": plan["protocol"],
                                "session": session, "schedule_mode": "carto-v1", "master_seed": plan["master_seed"],
                                "b1_manifest_sha256": manifest_sha, "psoracle_commit": verified["psoracle_commit"]}}
    return {"profile": profile, "ruling": ruling, "provision_ruling_parsed": pk, "manifest": manifest, "manifest_sha256": manifest_sha, "l6_manifest": l6m,
            "manifest_path": a.manifest, "ruling_path": a.ruling, "provision_ruling_path": a.provision_ruling,
            "carrier": carrier, "bitstream": car_bit, "image": a.image, "image_sha256": image_sha,
            "plan": session_plan, "round_plan": plan, "prediction": prediction,
            "signer": l3.SubprocessSigner(a.key, script=REPO_ROOT / "host/b1_sign_arm.py", signer_user=a.signer_user),
            "provision_execute": True, "provision_ruling": a.provision_ruling,
            "token": secrets.token_hex(16), "seed_nonce": int(manifest["carrier"]["nonce_seed"], 16),
            "heartbeat_s": l6m["protocol"]["heartbeat_s"], "instrument": verified, "instrument_root": root}


def expected_inputs(manifest: dict, profile: dict = MAPPING) -> dict:
    """What the session's run log must name as its inputs (l6.inputs): the plan, the
    prediction and the pin table the session was run against — per PROFILE (the v2.1 runner
    wrote the mapping hashes into a B1Q log; owner's review 2026-09-05)."""
    if profile["plan_section"] == "plan":
        plan_sha, pred_sha = manifest["plan"]["sha256"], manifest["prediction"]["sha256"]
    else:
        qp = manifest["qualification_plan"]
        plan_sha, pred_sha = qp["sha256"], qp["prediction_sha256"]
    return {"plan_sha256": plan_sha, "prediction_sha256": pred_sha, "pins_sha256": manifest["pins"]["sha256"]}


def identity_check_for(plan: dict, manifest: dict):
    """The B1 IDENT (app_identity 1.4.0) is verified before it is acknowledged."""
    def check(ident: dict) -> list[str]:
        out = []
        for k, v in (("carto_version", manifest["cartographer"]["version"]), ("universe_sha256", manifest["universe"]["sha256"]),
                     ("probe_budget", plan["budget"]), ("master_seed", plan["master_seed"]), ("protocol", plan["protocol"]),
                     ("rec_retry_control", True), ("sign_retry_control", True),
                     ("carrier_variant", adj.B1_VARIANT), ("carrier_sha256", manifest["carrier"]["bitstream_sha256"])):
            if ident.get(k) != v:
                out.append(f"IDENT {k}: {ident.get(k)!r} != {v!r}")
        if ident.get("findings"):
            out.append(f"IDENT findings: {ident['findings']}")
        return out
    return check


def run_session(session, out_dir: Path, ruling: dict, cfg: dict) -> dict:
    """The round 1′ session function with B1's identity check and the profile's adjudicator:
    the preamble, console loop and evidence files are the instrument's. A qualification
    session additionally leaves its qualification RECORD beside the evidence (PASS or not)."""
    import b1_session  # noqa: E402
    profile = cfg.get("profile", MAPPING)
    judge = profile["adjudicate"]
    # the session artifacts (manifest bytes, both rulings) were archived by execute() BEFORE
    # the port was opened; a session function reached without them is a programming error
    for name in (bq.MANIFEST_AT_RUN, *bq.RULING_FILES.values()):
        if not (Path(out_dir) / name).is_file():
            raise RuntimeError(f"session artifacts not archived before the session: {name} missing")
    summary = b1_session.run(session, out_dir, ruling, cfg, identity_check_for(cfg["round_plan"], cfg["manifest"]),
                             lambda d: judge(d, cfg["manifest"], cfg["round_plan"], cfg["prediction"], cfg["manifest_sha256"],
                                             instrument_root=cfg["instrument_root"], require_git=True),
                             profile["tool"])
    if profile is QUALIFICATION and (out_dir / "adjudication.json").is_file():
        rec = bq.make_record(out_dir, cfg["manifest"], cfg["manifest_sha256"], cfg["round_plan"],
                             json.loads((out_dir / "adjudication.json").read_text()))
        (out_dir / "qualification.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    return summary


def main(argv=None, profile: dict = MAPPING) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ruling", type=Path, required=True)
    ap.add_argument("--provision-ruling", type=Path, default=None)
    ap.add_argument("--boundary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--instrument-root", type=Path, default=inst.DEFAULT_ROOT)
    ap.add_argument("--image", type=Path, default=REPO_ROOT / "firmware/b1/bsp/out/b1_app.bin")
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
    """The order after a passed preflight, FIXED (owner's review 2026-09-05): (1) the evidence
    directory; (2) the session artifacts — the manifest bytes and both rulings — archived
    and verified against what the preflight parsed, in a guarded try: a failure here is a
    REFUSED with no ruling consumed and no port opened; (3) the whole-of-run ruling claimed;
    (4) the serial port opened (the first board contact); (5) the session. Tested as an
    order (tests/test_b1_runner.py::Order)."""
    import board_session as bsn  # noqa: E402
    import l3_runner as l3  # noqa: E402
    import pcap_probe_runner as pr  # noqa: E402
    try:
        a.out.mkdir(parents=True)
        bq.write_session_artifacts(a.out, cfg["manifest_path"], cfg["ruling_path"], cfg["provision_ruling_path"], cfg["manifest_sha256"],
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
