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
  * **The positive path is not demonstrated.** `judge_session` composes the instrument and
    evidence contract with the record replay, but there is no modelled B2/B2Q session yet (a
    `b2_modelled_session` in the shape of `b1_modelled_session.py`, writing `run_log.json`,
    `audits.json` and `timeline.json` through the instrument's real host stack). So: the
    instrument layer's later branches are exercised only in isolation, `b2_manifest.qualify`
    has not been shown to ACCEPT a B2Q transition, and this runner has never produced a PASS.
  * No board session has been run, and none is authorised.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
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
PROTOCOL_WIRE = "rel-v4"
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
# B2Q's deadline is a PLANNING bound — it measures the real rate — and the offline verdict must
# reconstruct the SAME limit the producer used, so the rate is a declared constant with its rule,
# not an argument the producer may widen (the owner's P2-3 of 2026-09-11). The rule: the slowest
# archived planning rate in `evidence/b2/plan.json`'s planning_rates_NOT_calibration (the last
# observed B1 mapping). Pinning it in the manifest at S0/S1 remains the owner's recommendation.
QUAL_PLANNING_RATE_PER_HOUR = 2807.0
QUAL_PLANNING_RATE_RULE = ("the slowest archived planning rate (the last observed B1 mapping, "
                           "evidence/b2/plan.json planning_rates_NOT_calibration); B2Q MEASURES the real one")
WATCHDOG_LOAD, WATCHDOG_PRESCALER = 1250000035, 7


def deadline_s(records: int, rate_per_hour: float) -> float:
    """The preregistration's frozen formula (§2, `b2_plan.DEADLINE_FORMULA`)."""
    return 1.25 * records * 3600 / rate_per_hour + 600


class Refusal(Exception):
    """Fail-closed: a named reason why this invocation does not reach a board."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _short(v) -> str:
    text = repr(v) if isinstance(v, str) else json.dumps(v, sort_keys=True, default=str)
    return text if len(text) <= 72 else text[:69] + "..."


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
    # The expected board is a FROZEN input, never derived from a ruling, and its absence is a
    # refusal — two rulings agreeing on the wrong board used to pass (the owner's P2 of
    # 2026-09-11).
    try:
        want_board = bman.check_board(manifest)
    except bman.Refusal as exc:
        raise Refusal(f"ruling {path}: {exc}") from None
    if r["boardid"] != want_board:
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
    """The instrument pin table: the whole decision surface by hash, plus B1's own table against
    B1's manifest. A board session whose pin table was never checked is exactly the session this
    runner exists to prevent, so every failure here is a refusal."""
    import b2_pins  # noqa: E402
    try:
        return b2_pins.verify(manifest=manifest)
    except b2_pins.PinRefusal as exc:
        raise Refusal(f"instrument pins: {exc}") from None


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


def qualification_session_plan(manifest: dict, manifest_sha256: str | None = None) -> dict:
    """B2Q's session plan, derived from the manifest and the preregistration's §6a constants, so
    the runner and the re-adjudicator judge the SAME session — including the SAME deadline, which
    comes from the declared planning rate and not from whatever rate the session went on to
    measure. The instrument must be bound."""
    import l6_schedule as ls  # noqa: E402
    records_expected = bsess.records(QUAL_PAIRS, QUAL_BUDGET)
    audit_seqs = set(range(1, records_expected + 1))
    frames = ls.expected_frames(records_expected - 2, audit_seqs, PROTOCOL_WIRE)
    flags = bsess.encode_slice(ls.flags_for(ls.MODE_ABBA, watchdog=True, rec_control=True, sign_control=True),
                               QUAL_PAIRS, 0, QUAL_PAIRS)
    return {"session": bman.QUAL_SESSION, "n": QUAL_BUDGET, "master_seed": qualification_master(manifest),
            "pairs_total": QUAL_PAIRS, "pair_first": 0, "pair_count": QUAL_PAIRS, "flags": flags,
            "audit_policy": bp.AUDIT_POLICY, "audit_seqs": audit_seqs, "protocol": PROTOCOL_WIRE,
            "expected_records": records_expected, "expected_frames": frames,
            "crc_budget": ls.crc_budget(frames["total"]), "bad_frame_budget": ls.crc_budget(frames["total"]),
            "session_timeout_s": deadline_s(records_expected, QUAL_PLANNING_RATE_PER_HOUR),
            "deadline_formula": bp.DEADLINE_FORMULA,
            "deadline_rate": {"source": QUAL_PLANNING_RATE_RULE, "rate_per_hour": QUAL_PLANNING_RATE_PER_HOUR},
            "binding": qualification_binding(manifest, manifest_sha256),
            "inputs": expected_inputs(manifest, QUALIFICATION)}


def qualification_binding(manifest: dict, manifest_sha256: str | None) -> dict:
    """What a B2Q session's log must declare it was run under."""
    return {"session": bman.QUAL_SESSION, "image_sha256": (manifest.get("image") or {}).get("sha256"),
            "prereg_sha256": (manifest.get("prereg") or {}).get("sha256"),
            "b2_manifest_sha256": manifest_sha256, "schedule_mode": bs.ENGINE_VERSION,
            "master_seed": qualification_master(manifest), "protocol": PROTOCOL_WIRE,
            "psoracle_commit": manifest["instrument"]["psoracle_commit"],
            "map_canonical_json_sha256": manifest["map"]["canonical_json_sha256"],
            "fitness_id": manifest["experiment"]["fitness"], "budget_per_arm": QUAL_BUDGET,
            "pair_first": 0, "pair_count": QUAL_PAIRS,
            "carrier_sha256": manifest["carrier"]["bitstream_sha256"], "carrier_variant": B2_VARIANT,
            "universe_sha256": manifest["universe"]["sha256"], "boardid": bman.check_board(manifest)}


def binding_findings(log: dict, session_plan: dict, manifest: dict | None = None) -> list[str]:
    """The session's IDENTITY and its invocation, established from the EVIDENCE — not assumed
    from the plan that judged it. The instrument layer proves the log is internally consistent
    and the replay proves the algorithm was followed under the slice the log DECLARES; neither
    proves that this log is the session this invocation authorised (the owner's P2-1 of
    2026-09-11). A set of mutually consistent declarations is not proof of belonging."""
    f: list[str] = []
    want = session_plan.get("binding") or {}
    if not want:
        return ["the session plan carries no binding: nothing to hold this evidence to"]
    l6 = log.get("l6")
    if not isinstance(l6, dict):
        return ["the run log carries no l6 block: the session declared no binding at all"]
    got = l6.get("binding")
    if not isinstance(got, dict):
        return ["the run log's l6 carries no binding block"]
    for k in sorted(want):
        if want[k] is None:
            f.append(f"binding: this invocation declares no {k}, so the evidence cannot be held to one")
        elif got.get(k) != want[k]:
            f.append(f"binding: the log's {k} is {_short(got.get(k))}, this invocation's is {_short(want[k])}")
    # The inputs contract is REQUIRED. A plan that carries none used to disable this check
    # silently, which is exactly how the B2Q offline path skipped it.
    inputs_want = session_plan.get("inputs")
    if not isinstance(inputs_want, dict):
        f.append("the session plan carries no inputs contract: a missing expectation is not a pass")
    else:
        inputs_got = l6.get("inputs")
        if not isinstance(inputs_got, dict):
            f.append("the run log's l6 carries no inputs block")
        else:
            for k in sorted(inputs_want):
                if inputs_got.get(k) != inputs_want[k]:
                    f.append(f"inputs: the log's {k} is {_short(inputs_got.get(k))}, this "
                             f"invocation's is {_short(inputs_want[k])}")
    if manifest is not None:
        # the WHOLE identity contract, the carrier and universe digests included
        f += identity_findings(log.get("app_identity"), manifest, session_plan)
    else:
        f.append("no manifest to hold the IDENT to: the identity contract was not checked")
    return f


def archived_ruling_findings(evidence: Path, session_plan: dict) -> list[str]:
    """The two archived authorisations, DECODED and REBOUND — not merely hashed. Recording the
    digest of an archive that was never parsed preserves an invalid declaration instead of
    catching it, and later detection of changes to already-pinned bytes says nothing about what
    was accepted the first time (the owner's P2-2 of 2026-09-11).

    They are read through the instrument's own strict envelope reader. An archive is INERT: it is
    read, never claimed, never consumed, and nothing here reactivates it."""
    import b1_qualification as bq  # noqa: E402
    want = session_plan.get("binding") or {}
    session = session_plan.get("session")
    texts = {"whole_of_run": QUAL_RULING_TEXT if session == bman.QUAL_SESSION else RULING_TEXT,
             "provisioning": PROVISION_RULING_TEXT}
    f: list[str] = []
    boards: dict[str, object] = {}
    want_board = (session_plan.get("binding") or {}).get("boardid")
    if not isinstance(want_board, str) or not want_board.strip():
        f.append(f"this session declares no board authority ({want_board!r}): the archived "
                 f"authorisations cannot be rebound to one, and agreeing with each other is not enough")
        want_board = None
    for key, name in bq.RULING_FILES.items():
        path = Path(evidence) / name
        if not path.is_file():
            f.append(f"the evidence carries no {name}: the session archived no {key} authorisation")
            continue
        try:
            _raw, ruling = bq.read_archived_ruling(path)
        except bq.QualificationRefusal as exc:
            f.append(f"{name}: {exc}")
            continue
        text = texts[key]
        if ruling.get("ruling") != text:
            f.append(f"{name}: the archived ruling text is {_short(ruling.get('ruling'))}, not {_short(text)}")
        for field in ("boardid", "granted_by", "date"):
            if not ruling.get(field):
                f.append(f"{name}: the archived ruling lacks {field!r}")
        boards[key] = ruling.get("boardid")
        bind = {"session": session, "prereg_sha256": want.get("prereg_sha256"),
                "image_sha256": want.get("image_sha256"),
                "b2_manifest_sha256": want.get("b2_manifest_sha256")}
        if key == "whole_of_run":                       # only this one names the experiment's seed
            bind["master_seed"] = want.get("master_seed")
        for k, v in bind.items():
            got = ruling.get(k)
            if k == "master_seed" and isinstance(got, str):
                try:
                    got = int(got, 0)
                except ValueError:
                    got = None
            if v is None:
                f.append(f"{name}: this invocation declares no {k}, so the archive cannot be rebound to one")
            elif got != v:
                f.append(f"{name}: the archived ruling is bound to {k} = {_short(got)}, this session's "
                         f"is {_short(v)}")
    if len(boards) == len(bq.RULING_FILES) and len(set(map(str, boards.values()))) != 1:
        f.append(f"the two archived authorisations name different boards: "
                 f"{ {k: _short(v) for k, v in boards.items()} }")
    if want_board is not None:
        for key, got in boards.items():
            if not isinstance(got, str) or not got.strip():
                f.append(f"{bq.RULING_FILES[key]}: the archived ruling's boardid {_short(got)} is not "
                         f"a non-empty string")
            elif got != want_board:
                f.append(f"{bq.RULING_FILES[key]}: the archived ruling names board {_short(got)}, "
                         f"this stage is {_short(want_board)}")
    return f


def export_seal_findings(evidence: Path) -> list[str]:
    """The evidence directory's own seal. The production finalizer checks it when it writes the
    files; a STANDALONE re-adjudication months later has no such protection, and a verdict over
    a subset of the evidence is no verdict. B1's declared schema and check are used unchanged —
    the same code writes both sessions' exports (the owner's P2-2 of 2026-09-11)."""
    import b1_adjudicate as b1adj  # noqa: E402
    try:
        b1adj.check_exports(Path(evidence))
    except b1adj.Refusal as exc:
        return [f"evidence seal: {exc}"]
    return []


def instrument_findings(evidence: Path, log: dict, session_plan: dict, instrument_root: Path) -> dict:
    """The instrument and evidence contract for ONE session — B1's `_p3_layer` over B2's plan.
    The record replay says the board followed the algorithm; THIS says the session happened at
    all: the standalone run-log validation with the audit gate, the declared audit policy, the
    structural / baseline / REC / rel closure and control findings, the transport budgets, the
    rate report, and the epoch's own outcome. A verdict without it is a verdict about
    arithmetic, not about a session (the owner's integration review of 2026-09-11)."""
    import b1_records as records  # noqa: E402
    from validators import records as _instrument_records  # noqa: E402
    import l5_runner as l5  # noqa: E402
    import l6_checks as lc  # noqa: E402
    import l6_rate as lr  # noqa: E402
    import l6_schedule as ls  # noqa: E402
    import p3_gate as g  # noqa: E402
    import p3_genome as gn  # noqa: E402
    out: dict = {"findings": [], "rejected": None, "rate": None, "audit_policy": None}
    f = out["findings"]
    for name in ("audits.json", "timeline.json"):
        if not (evidence / name).is_file():
            f.append(f"the evidence carries no {name}: the session's transport was not recorded")
    if f:
        return out
    audits = json.loads((evidence / "audits.json").read_text())
    timeline = json.loads((evidence / "timeline.json").read_text())
    frames = timeline.get("frames") or []
    chunks = audits.get("chunks") or []
    b1_manifest = json.loads(bman.B1_MANIFEST.read_text())
    nonce_seed = int(b1_manifest["carrier"]["nonce_seed"], 16)
    phen = g.load_manifest()
    blank_commit = g.gate(g.build_streams(gn.frames_from_genome(gn.blank_genome(phen), phen), phen),
                          phen)["candidate_sha256"]
    l6m = json.loads((Path(instrument_root) / "manifests/l6_manifest.json").read_text())
    try:
        v = records.validate_standalone_run_log(log, blank_commit, nonce_seed, chunks, phen)
        out["run_log_validation"] = {k: v[k] for k in ("scored", "audited", "chain_length") if k in v}
        records.check_audit_policy(log, v["marks"], session_plan["audit_policy"], None)
        out["audit_policy"] = session_plan["audit_policy"]          # VERIFIED, not echoed
        f += lc.structural_findings(log, chunks, set(session_plan["audit_seqs"]), frames,
                                    protocol=session_plan["protocol"], hb_rule="v07")
        f += lc.baseline_findings(log)
        rec_ledgers = audits.get("recs") or []
        f += lc.rec_closure_findings(log, rec_ledgers)
        f += lc.rec_control_findings(rec_ledgers, bool(session_plan["flags"] & ls.FLAG_REC_CONTROL))
        f += lc.rel_closure_findings(log, audits, audits.get("pulls") or [])
        f += lc.rel_control_findings(audits.get("signs") or [], bool(session_plan["flags"] & ls.FLAG_SIGN_CONTROL))
        try:
            rep = lr.rate_report_from_evidence_dir(evidence, None)
            out["rate_report"] = {k: rep.get(k) for k in ("candidates", "evals_per_hour", "cov", "session_span_s")}
            out["rate"] = rep.get("evals_per_hour")
            pc = l6m["pass_conditions"]
            f += lc.soak_findings(log, frames, int(timeline.get("crc_dropped") or 0), session_plan["crc_budget"],
                                  rep["session_span_s"], duration_s=0.0, hb_gap_max_s=pc["hb_gap_max_s"],
                                  settle_median_calib=16.0, settle_bound_factor=pc["settle_bound_factor"],
                                  wall_fraction_min=0.0, bad_frames=int(timeline.get("bad_frames") or 0),
                                  bad_frame_budget=session_plan["bad_frame_budget"])
            # `soak_findings` bounds heartbeat gaps, CRC and bad frames and a MINIMUM duration;
            # the session's own MAXIMUM is this check, against the limit the invocation
            # authorised — never against the rate the session went on to measure.
            limit = session_plan.get("session_timeout_s")
            if limit is None:
                f.append("the session plan carries no deadline: the archived session is held to no limit")
            elif rep["session_span_s"] > float(limit):
                f.append(f"the session spanned {rep['session_span_s']:.1f} s, past the "
                         f"{float(limit):.1f} s deadline this session was authorised for")
        except lr.RateError as exc:
            f.append(f"no rate report: {exc}")
        summary = log.get("session_summary")
        if not isinstance(summary, dict) or not isinstance(summary.get("epoch_end"), dict):
            f.append("the run log carries no session_summary with an epoch_end: the session did not close")
        else:
            base = l5.outcome_for(summary["epoch_end"])
            if base != "PASS":
                f.append(f"epoch outcome {base}")
            last = summary["epoch_end"].get("last_seq")
            if last != session_plan["expected_records"]:
                f.append(f"the epoch ended at seq {last!r}, not the {session_plan['expected_records']} "
                         f"records this session's slice requires")
    except _instrument_records.RecordError as exc:
        out["rejected"] = l5.classify_rejection(exc)
        out["run_log_validation"] = f"REJECTED: {exc}"
    return out


def archived_manifest_findings(evidence: Path, manifest: dict, session_plan: dict) -> list[str]:
    """The manifest the session archived beside its evidence must BE the manifest this verdict is
    for, by bytes. Without it the `manifest` argument is decoration: every other check would be
    reading declarations that agree with each other and with nothing else."""
    p = Path(evidence) / bman.MANIFEST_AT_RUN
    if not p.is_file():
        return [f"the evidence carries no {bman.MANIFEST_AT_RUN}: the session archived no manifest"]
    want_sha = (session_plan.get("binding") or {}).get("b2_manifest_sha256")
    got_sha = _sha(p)
    f: list[str] = []
    if want_sha is None:
        f.append("this invocation declares no manifest digest to hold the archived manifest to")
    elif got_sha != want_sha:
        f.append(f"the archived {bman.MANIFEST_AT_RUN} hashes to {got_sha[:16]}…, this invocation's "
                 f"manifest to {want_sha[:16]}…")
    try:
        at_run = json.loads(p.read_text())
    except ValueError as exc:
        return f + [f"the archived {bman.MANIFEST_AT_RUN} is not readable JSON: {exc}"]
    if not isinstance(at_run, dict) or at_run.get("schema") != bman.SCHEMA:
        return f + [f"the archived {bman.MANIFEST_AT_RUN} is not a b2_manifest document"]
    for path, label in ((("image", "sha256"), "image"), (("prereg", "sha256"), "preregistration"),
                        (("map", "canonical_json_sha256"), "map"),
                        (("carrier", "bitstream_sha256"), "carrier")):
        a, b = at_run, manifest
        for k in path:
            a = (a or {}).get(k) if isinstance(a, dict) else None
            b = (b or {}).get(k) if isinstance(b, dict) else None
        if a != b:
            f.append(f"the archived manifest's {label} is not this invocation's")
    return f


def judge_session(evidence_dir, manifest: dict, session_plan: dict, plan_doc: dict | None,
                  prediction_doc: dict | None, seeds: list | None, instrument_root: Path,
                  consts: dict | None = None) -> dict:
    """The session's verdict: the instrument and evidence contract COMPOSED with the record
    replay. Neither alone is a session verdict — the replay proves the algorithm was followed,
    the instrument layer proves there was a session to follow it in.

    The result carries the fields the lifecycle consumes (§8 S2): the session identity, the
    outcome, the MEASURED all-self-reporting rate from the evidence's own timing, and the
    VERIFIED audit policy. None of them is echoed from a stored adjudication."""
    evidence = Path(evidence_dir)
    session = session_plan["session"]
    # Every exit carries the same keys: a caller reading this result must not have to guess
    # which checks ran, and a missing key is not a way to hide one.
    out = {"tool": TOOL_VERSION, "session": session, "scope": "session", "outcome": None,
           "findings": [], "kills": [], "measured_rate_per_hour": None, "audit_policy": None,
           "instrument": {}, "binding_checked": False, "replay": {}}
    archived = archived_manifest_findings(evidence, manifest, session_plan)
    if archived:                       # the evidence does not belong to this invocation at all
        out["findings"] = archived
        out["outcome"] = "HOLD: " + "; ".join(archived[:4])
        return out
    log_path = evidence / "run_log.json"
    if not log_path.is_file():
        out["outcome"] = "REFUSED: the evidence carries no run_log.json"
        return out
    try:
        log = json.loads(log_path.read_text())
    except ValueError as exc:
        out["outcome"] = f"REFUSED: run_log.json is not readable JSON: {exc}"
        return out
    seal = export_seal_findings(evidence)
    rulings = archived_ruling_findings(evidence, session_plan)
    binding = binding_findings(log, session_plan, manifest)
    p3 = instrument_findings(evidence, log, session_plan, instrument_root)
    out["instrument"] = {k: v for k, v in p3.items() if k not in ("findings", "rejected")}
    out["measured_rate_per_hour"] = p3["rate"]
    out["audit_policy"] = p3["audit_policy"]
    out["findings"] = seal + rulings + binding + list(p3["findings"])
    out["binding_checked"] = not binding and not seal and not rulings
    if p3["rejected"]:                              # the instrument's own falsification / refusal
        out["outcome"] = p3["rejected"]
        return out
    if plan_doc is None or prediction_doc is None:
        out["findings"].append("no plan and prediction to replay this session against")
        out["outcome"] = "HOLD: " + out["findings"][0]
        return out
    rep = adj.adjudicate([log], plan_doc, prediction_doc, consts=consts, scope="session", seeds=seeds)
    out["replay"] = {k: rep.get(k) for k in ("scope", "measurement", "replay", "pair_seeds") if k in rep}
    out["findings"] += rep.get("findings") or []
    out["kills"] = rep.get("kills") or []
    if rep.get("refusal"):
        out["outcome"] = f"REFUSED: the replay: {rep['refusal']}"
    elif out["kills"]:
        out["outcome"] = "KILL: " + "; ".join(out["kills"][:4])
    elif out["findings"]:
        out["outcome"] = "HOLD: " + "; ".join(out["findings"][:6])
    elif out["measured_rate_per_hour"] is None or out["audit_policy"] is None:
        out["outcome"] = "HOLD: the session produced no measured rate or no verified audit policy"
    else:
        out["outcome"] = "PASS"
    return out


def readjudicator(manifest: dict, instrument_root=None, consts: dict | None = None):
    """The callable `b2_manifest.verify`/`qualify` take to RE-ADJUDICATE the pinned qualification
    evidence — `(evidence_dir, manifest_at_run)`. It RECOMPUTES the outcome, the measured rate and
    the audit policy from the evidence files; it never echoes `adjudication.json`, which is what
    the lifecycle compares its own reconstruction against.

    It judges against the VALIDATED RUN MANIFEST the lifecycle hands it — the manifest the session
    actually ran under — not against the manifest being transitioned, and refuses if the two are
    not the same stage's (the owner's P2-1 of 2026-09-11). The evidence is a B2Q session, so B2Q's
    own plan, prediction and seeds judge it, never B2's."""
    def again(evidence_dir, manifest_at_run=None) -> dict:
        refuse = {"tool": TOOL_VERSION, "session": bman.QUAL_SESSION, "scope": "session",
                  "findings": [], "kills": [], "measured_rate_per_hour": None, "audit_policy": None}
        if not isinstance(manifest_at_run, dict) or manifest_at_run.get("schema") != bman.SCHEMA:
            refuse["outcome"] = ("REFUSED: no validated run manifest was given: a re-adjudication "
                                 "cannot judge a session against a manifest it was not run under")
            return refuse
        run_manifest_path = Path(evidence_dir) / bman.MANIFEST_AT_RUN
        if not run_manifest_path.is_file():
            refuse["outcome"] = f"REFUSED: the evidence carries no {bman.MANIFEST_AT_RUN}"
            return refuse
        for path, label in ((("image", "sha256"), "image"), (("prereg", "sha256"), "preregistration")):
            a, b = manifest_at_run, manifest
            for k in path:
                a = (a or {}).get(k) if isinstance(a, dict) else None
                b = (b or {}).get(k) if isinstance(b, dict) else None
            if a != b:
                refuse["outcome"] = (f"REFUSED: the run manifest's {label} is not the one this "
                                     f"transition is for")
                return refuse
        plan, prediction, seeds = qualification_documents(manifest_at_run)
        session_plan = qualification_session_plan(manifest_at_run, _sha(run_manifest_path))
        return judge_session(evidence_dir, manifest_at_run, session_plan, plan, prediction, seeds,
                             instrument_root or inst.DEFAULT_ROOT, consts=consts)
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

    try:
        board = bman.check_board(manifest)        # the frozen authority, before any ruling is read
    except bman.Refusal as exc:
        raise Refusal(str(exc)) from None
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
        bman.verify(manifest, readjudicate=readjudicate or readjudicator(manifest, a.instrument_root))
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
        # The planning bound is DECLARED (QUAL_PLANNING_RATE_PER_HOUR), so the offline verdict
        # reconstructs the same deadline. The flag may only agree with it, never widen it.
        if a.qual_rate_per_hour is not None:
            if not isinstance(a.qual_rate_per_hour, (int, float)) or isinstance(a.qual_rate_per_hour, bool) \
                    or not math.isfinite(a.qual_rate_per_hour) or a.qual_rate_per_hour <= 0:
                raise Refusal(f"--qual-rate-per-hour {a.qual_rate_per_hour!r} is not a finite positive rate")
            if float(a.qual_rate_per_hour) != QUAL_PLANNING_RATE_PER_HOUR:
                raise Refusal(f"--qual-rate-per-hour {a.qual_rate_per_hour!r} is not the declared planning "
                              f"bound {QUAL_PLANNING_RATE_PER_HOUR} ({QUAL_PLANNING_RATE_RULE}); the "
                              f"offline verdict reconstructs THAT limit, so this flag may only agree")
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
    # BOTH profiles bind the master seed of the experiment they run: B2's is the manifest's,
    # B2Q's is its own derived one (the owner's P2-4 of 2026-09-11).
    bind_ruling(ruling, profile["ruling_text"], session, prereg["sha256"], image_sha, manifest_sha, master)
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
    wire = (b1_manifest.get("protocol") or {}).get("wire")
    # The L6 manifest's `protocol` carries heartbeat/silence/timeout and NO wire selector; the
    # wire is pinned by the B1 manifest, whose bytes this preflight has already re-verified
    # through the carrier lineage (the owner's integration review of 2026-09-11).
    if not isinstance(wire, str) or not wire:
        raise Refusal("the B1 manifest pins no protocol.wire: the frame arithmetic has no authority")
    if wire != PROTOCOL_WIRE:
        raise Refusal(f"the pinned wire protocol {wire!r} is not the {PROTOCOL_WIRE!r} this stage speaks")
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
        timeout = deadline_s(records_expected, QUAL_PLANNING_RATE_PER_HOUR)
        rate_note = {"source": QUAL_PLANNING_RATE_RULE, "rate_per_hour": QUAL_PLANNING_RATE_PER_HOUR}
    audit_seqs = set(range(1, records_expected + 1))        # all-self-reporting: every record audited
    # `expected_frames` takes the count of NON-bracket candidates and adds the two baselines
    # itself; handing it the bracketed total counted them twice (the owner's P3 of 2026-09-11).
    expected_frames = ls.expected_frames(records_expected - 2, audit_seqs, wire)
    if expected_frames["records"] != records_expected:
        raise Refusal(f"the frame arithmetic says {expected_frames['records']} records, the record "
                      f"arithmetic says {records_expected}")
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
                    "pair_first": first, "pair_count": count, "protocol": wire,
                    "carrier_sha256": manifest["carrier"]["bitstream_sha256"], "carrier_variant": B2_VARIANT,
                    "universe_sha256": manifest["universe"]["sha256"], "boardid": board},
    }
    if profile is QUALIFICATION:
        # The producer and the offline verdict must judge the SAME session: the plan this
        # preflight built has to equal the one `qualification_session_plan` rebuilds from the
        # manifest alone, field for field on everything a verdict reads.
        rebuilt = qualification_session_plan(manifest, manifest_sha)
        differ = [k for k in ("session", "n", "master_seed", "pairs_total", "pair_first", "pair_count",
                              "flags", "audit_policy", "audit_seqs", "protocol", "expected_records",
                              "expected_frames", "crc_budget", "bad_frame_budget", "session_timeout_s",
                              "binding", "inputs") if session_plan.get(k) != rebuilt.get(k)]
        if differ:
            raise Refusal(f"the B2Q session plan this preflight built is not the one the offline "
                          f"verdict rebuilds: {differ}")
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


def expected_identity(manifest: dict, session_plan: dict) -> dict:
    """The complete `app_identity` 1.5.0 contract for a session — ONE definition, used by the
    online check before the board's identity is acknowledged AND by the offline binding check
    when the evidence is re-adjudicated later. Two definitions would drift, and the offline one
    is the only check a standalone re-adjudication gets (the owner's P2-1 of 2026-09-11)."""
    return {"search_version": bs.ENGINE_VERSION,
            "map_sha256": manifest["map"]["canonical_json_sha256"],
            "operator_data_sha256": manifest["map"]["canonical_json_sha256"],
            "fitness_id": manifest["experiment"]["fitness"],
            "budget_per_arm": session_plan["n"], "master_seed": session_plan["master_seed"],
            "pairs_total": session_plan["pairs_total"], "pair_first": session_plan["pair_first"],
            "pair_count": session_plan["pair_count"], "carrier_variant": B2_VARIANT,
            "carrier_sha256": manifest["carrier"]["bitstream_sha256"],
            "universe_sha256": manifest["universe"]["sha256"], "protocol": PROTOCOL_WIRE,
            "rec_retry_control": True, "sign_retry_control": True}


def identity_findings(ident, manifest: dict, session_plan: dict) -> list[str]:
    if not isinstance(ident, dict):
        return ["the session declared no app_identity object"]
    out = [f"IDENT {k}: {_short(ident.get(k))} != {_short(v)}"
           for k, v in sorted(expected_identity(manifest, session_plan).items()) if ident.get(k) != v]
    for forbidden in ("carto_version", "probe_budget"):
        if forbidden in ident:
            out.append(f"IDENT {forbidden}: this image runs no cartographer and issues no probes")
    if ident.get("findings"):
        out.append(f"IDENT findings: {ident['findings']}")
    return out


def identity_check_for(cfg: dict):
    """The B2 IDENT is verified BEFORE it is acknowledged, against the same contract the offline
    verdict holds the archived evidence to."""
    def check(ident: dict) -> list[str]:
        return identity_findings(ident, cfg["manifest"], cfg["plan"])
    return check


REQUIRED_CFG = ("profile", "manifest", "plan", "instrument_root")


def adjudication_for(cfg: dict):
    """A session is judged as a SESSION: the instrument and evidence contract composed with the
    record replay. The run's pooled primary is a later `b2_adjudicate --scope run` over every
    session's log. B2Q is judged against its OWN plan, prediction and seeds — and its result
    carries the session identity, the measured rate and the verified policy that §8's S2
    transition consumes.

    A caller that cannot supply what a session verdict needs gets a NAMED refusal from the
    returned callable, never a KeyError and never a verdict from a subset of the checks."""
    missing = [k for k in REQUIRED_CFG if cfg.get(k) is None]
    if missing:
        def refuse(evidence_dir) -> dict:
            return {"tool": TOOL_VERSION, "scope": "session", "findings": [], "kills": [],
                    "measured_rate_per_hour": None, "audit_policy": None,
                    "outcome": f"REFUSED: no session verdict without {missing}: a record replay "
                               f"alone is not one"}
        return refuse
    if cfg["profile"] is QUALIFICATION:
        plan, prediction, seeds = qualification_documents(cfg["manifest"])
    else:
        plan, prediction, seeds = cfg.get("round_plan"), cfg.get("prediction"), None

    def judge(evidence_dir) -> dict:
        return judge_session(evidence_dir, cfg["manifest"], cfg["plan"], plan, prediction, seeds,
                             cfg["instrument_root"])
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
