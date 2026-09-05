"""B1 SUCCESSOR of zynq-psoracle validators/records.py (derived by host-side patch; base hash in
manifests/b1_instrument_pins.json). ONE change: rule (iii) — see the B1 block below. Everything
else is the instrument's, verbatim.

Record validators for the P3 contracts, and the run-log rules (i)–(v).

These are evidence-consistency checks (`docs/contracts.md`); they never substitute for
the PL MAC gate. A record that fails is REJECTED (`RecordError`), not flagged.
"""

from __future__ import annotations

import hashlib
import json

from validators.schema import SchemaError, check_envelope   # the bound instrument's package

SUPPORTED = {
    "carrier_manifest": "1.0.0", "candidate": "1.0.0", "gate_verdict": "1.0.0",
    "oracle_record": "1.0.0", "arm_record": "1.0.0", "score_record": "1.0.0",
    "run_log": "1.0.0", "negative_control": "1.0.0", "principal_boundary": "1.0.0",
    # standalone plane (D1 — docs/d1_standalone_spec.md §7; contracts.md standalone section)
    "app_identity": "1.0.0", "sign_request": "1.0.0", "sign_reply": "1.0.0",
    "sign_refusal": "1.0.0", "notary_log": "1.0.0", "app_oracle_record": "1.0.0",
    "loop_record": "1.0.0", "session_summary": "1.0.0",
}
REQUIRED = {
    "carrier_manifest": ("bitstream_sha256", "frame_table_sha256", "part", "axi", "target_fars", "no_icap"),
    "candidate": ("carrier_manifest_sha256", "frames", "candidate_sha256", "stream_words", "sequence_sha256"),
    "gate_verdict": ("candidate_sha256", "writable", "findings", "gate_tool", "manifest_sha256"),
    "oracle_record": ("session", "candidate_sha256", "staged_sha256", "staged_stream_sha256", "write",
                      "readback_sha256", "configuration_valid_hw_expected"),
    "arm_record": ("oracle_record_sha256", "gate_verdict_sha256", "epoch", "nonce", "candidate_commit",
                   "expected_tables", "tag", "signer", "axi_before", "key_loaded_observed"),
    "score_record": ("arm_record_sha256", "configuration_valid_hw", "hw_candidate_commit",
                     "functional_readout", "scores", "host_prediction"),
    "run_log": ("ruling_sha256", "records", "epoch_final"),
    "principal_boundary": ("runner_user", "signer_user", "pod_group", "key_store", "checks", "all_passed", "at"),
    "negative_control": ("kind", "arm_record_sha256", "nonce", "configuration_valid_hw", "fault", "scored", "refused_as_expected"),
    "app_identity": ("control_plane", "pss_idcode", "token", "uboot_epoch", "carrier_sha256",
                     "nonce_at_start", "status_at_start", "fclk0_hz_decoded", "app_epoch", "findings"),
    "sign_request": ("token", "app_epoch", "seq", "genome", "nonce"),
    "sign_reply": ("seq", "commit", "expected_tables", "tag"),
    "sign_refusal": ("seq", "finding_kinds"),
    "notary_log": ("token", "entries"),
    "app_oracle_record": ("seq", "staged_sha256", "staged_stream_sha256", "readback_sha256",
                          "write", "audit_available"),
    "loop_record": ("seq", "genome", "outcome", "verified", "evidence"),
    "session_summary": ("token", "epoch_end", "counts", "closing", "audit",
                        "crc_dropped", "drop_budget", "written_by"),
}
NEGATIVE_KINDS = ("unsigned", "replay", "other_candidate", "wrong_table", "unprovisioned", "wrong_key")
EXPECTED_FAULT = {"unsigned": 13, "replay": 13, "other_candidate": 13, "wrong_table": 15,
                  "unprovisioned": 12, "wrong_key": 13}
# controls that must come BEFORE any valid ARM (the positive attempt itself is expected to be refused)
PRE_CONTROLS = ("unprovisioned", "wrong_key")
HEX64 = 64


from validators import records as _instrument_records  # noqa: E402  (the bound instrument's package)


class RecordError(_instrument_records.RecordError):
    """B1's rejections are the instrument's class (subclassed), so the instrument's own
    layers — validators.audit raising on served words, l5_runner.classify_rejection mapping
    Falsified → KILL and everything else → HOLD — treat a B1 rejection exactly as they treat
    theirs, and the adjudicator catches one base class for both."""


class Falsified(RecordError, _instrument_records.Falsified):
    """A rejection that is one of the preregistration's falsification items (L5 prereg §3):
    the interlock or the nonce model contradicted by the record itself. The runner maps
    ONLY these to KILL; every other RecordError is a schema / accounting / instrument
    defect and is a HOLD. Session 3 (2026-09-01) was labelled KILL by a runner that mapped
    every rejection to that word when the actual cause was a counter in the firmware's
    TERM frame — the owner ruled it HOLD and that the mapping follow the preregistration."""


def canonical_sha256(record: dict) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(record: dict) -> dict:
    name = record.get("schema") if isinstance(record, dict) else None
    if name not in SUPPORTED:
        raise RecordError(f"unknown schema {name!r}")
    try:
        known = check_envelope(record, name, SUPPORTED[name], REQUIRED[name])
    except SchemaError as exc:
        raise RecordError(str(exc)) from None
    checker = globals().get(f"_check_{name}")
    if checker:
        checker(known)
    return known


def _hex(v, n, what):
    if not isinstance(v, str) or len(v) != n or any(c not in "0123456789abcdef" for c in v):
        raise RecordError(f"{what} must be {n} lowercase hex chars")


def _check_candidate(r):
    _hex(r["candidate_sha256"], HEX64, "candidate_sha256")
    fars = [f["far"] for f in r["frames"]]
    if fars != sorted(fars):
        raise RecordError("candidate frames must be FAR-ordered")
    for f in r["frames"]:
        if len(f["words"]) != 101:
            raise RecordError("a frame has != 101 words")


def _check_gate_verdict(r):
    _hex(r["candidate_sha256"], HEX64, "candidate_sha256")
    if r["writable"] and r["findings"]:
        raise RecordError("writable with findings is a contradiction")
    for f in r["findings"]:
        if "kind" not in f:
            raise RecordError("a finding without a kind — findings are bucketed by kind, never by text")


def _check_oracle_record(r):
    for k in ("candidate_sha256", "staged_sha256", "staged_stream_sha256", "readback_sha256"):
        _hex(r[k], HEX64, k)
    if r["staged_sha256"] == r["staged_stream_sha256"]:
        raise RecordError("staged frames and staged stream hashes are different domains and cannot coincide")


def _check_arm_record(r):
    _hex(r["candidate_commit"], HEX64, "candidate_commit (the FULL candidate_sha256)")
    _hex(r["nonce"], 16, "nonce")
    _hex(r["tag"], 32, "tag")
    if len(r["expected_tables"]) != 6:
        raise RecordError("expected_tables must have six entries")
    if r["signer"].get("principal") != "gate-signer":
        raise RecordError("arm_record must be signed by the gate-signer principal")
    if not isinstance(r["key_loaded_observed"], bool):
        raise RecordError("key_loaded_observed must be the bool read from STATUS bit 11 before the ARM")


def _check_score_record(r):
    _hex(r["hw_candidate_commit"], HEX64, "hw_candidate_commit")
    if len(r["functional_readout"]) != 6 or len(r["scores"]) != 6 or len(r["host_prediction"]) != 6:
        raise RecordError("six LUTs: readout, scores and prediction must each have six entries")


BOUNDARY_CHECKS = ("R1_runner_is_not_signer", "R2_runner_cannot_read_key", "R3_runner_cannot_open_pod",
                   "R4_signer_reachable_and_holds_key", "R5_signer_in_pod_group")
BOUNDARY_MAX_AGE_S = 6 * 3600


def _check_principal_boundary(r):
    names = [c["check"] for c in r["checks"]]
    if names != list(BOUNDARY_CHECKS):
        raise RecordError(f"principal_boundary checks must be exactly {BOUNDARY_CHECKS}, got {names}")
    if r["runner_user"] == r["signer_user"]:
        raise RecordError("runner and signer are the same user: no boundary")
    if r["all_passed"] is not all(c["passed"] for c in r["checks"]):
        raise RecordError("all_passed disagrees with the checks")


def boundary_established(r: dict, now: float) -> None:
    """What the L3 runner requires before it forms a single line: validated, all passed, fresh."""
    validate(r)
    if not r["all_passed"]:
        raise RecordError("principal boundary NOT established: " + "; ".join(
            f"{c['check']}: {c['detail']}" for c in r["checks"] if not c["passed"]))
    if now - r["at"] > BOUNDARY_MAX_AGE_S:
        raise RecordError("principal_boundary record is older than 6 h; re-run the verifier")


def _check_negative_control(r):
    if r["kind"] not in NEGATIVE_KINDS:
        raise RecordError(f"negative_control kind {r['kind']!r} is not one of {NEGATIVE_KINDS}")
    _hex(r["nonce"], 16, "nonce")
    if r["configuration_valid_hw"] is not False or r["scored"] is not False:
        raise Falsified("a negative control that validated or scored is a KILL, never a record that passes")
    if r["refused_as_expected"] is not (r["fault"] == EXPECTED_FAULT[r["kind"]]):
        raise RecordError(f"refused_as_expected disagrees with fault {r['fault']} for kind {r['kind']}")


# ------------------------------------------------------------------ run_log rules (i)–(vi)


def validate_run_log(log: dict) -> dict:
    """NOT A B1 PATH. The instrument's L5 run_log validator (rules (i)–(vi), including rule
    (iii) `functional_readout == expected_tables`) is deliberately not carried into the B1
    successor: under the noninterference contract there are no host-attested tables to
    compare with, and a caller reaching for it would be re-introducing the attestation the
    contract removes. The only B1 validation path is `validate_standalone_run_log` (rules
    (vii)–(ix) with rule iii-B1). Calling this is a refusal (owner's review 2026-09-05)."""
    raise RecordError("validate_run_log is the instrument's L5 path (rule iii: readout == host tables); B1 has no such path — "
                      "use validate_standalone_run_log (docs/b1_carrier_contract.md)")


# ------------------------------------------------------- standalone plane (D1) — records


# STOP_ARM: an ARM was written and the PL did not consume it — the nonce did not step.
# Added as INSTRUMENTATION after session 1 (2026-09-01), where the board entered exactly
# this state and the schema could not express it: REFUSED_BY_PL requires the nonce to have
# stepped, so the application had no legal record to emit and the observations were lost.
# It records that the state occurred; it asserts NOTHING about why, and no other rule is
# relaxed to accommodate it.
# STOP_SETTLE: the strobe was written and the bounded poll of STATUS exhausted its budget
# without the gate settling (busy never cleared, or nothing latched). Added after session 3
# (2026-09-01), which showed that the application had been reading the nonce while
# `gate_busy` was still set: the RTL steps the nonce only when the SipHash completes
# (rtl/p3_arm_gate.v state 1, `sh_done`), so an immediate read cannot see it. Every ARM
# record now carries `settle` — the poll's count, bound, first and last STATUS — and
# STOP_ARM means "the gate SETTLED and the nonce did not step", which is a different fact
# from "we did not wait". STOP_SETTLE is neutral: it consumes the nonce in the chain iff the
# nonce is observed stepped, forbids a score, and claims nothing about why.
# STOP_AUDIT (L6 pull protocol, docs/l6_audit_pull_design.md): the host-paced audit of a
# candidate that had staged and read back could not be completed (retries exhausted, the
# host aborted, or the board's bounded wait for the host ran out) BEFORE the ARM. The
# application then makes no ARM attempt and the epoch stops (restore, TERM). The record
# carries the oracle self-report and can never be marked audited, so the sampled and the
# all-self-reporting policies both refuse the log: it is always a HOLD, never a pass.
# STOP_SIGN (rel-v4, docs/l6_frame_reliability_design.md §3.1): the sign exchange was not
# acknowledged after the board's bounded resends — a TERMINAL record: nothing staged, no
# ARM, no nonce consumed; the record carries `sign_stop {attempts, why}` and nothing else;
# the host may or may not hold a notary entry for the seq (the reply may have been lost
# after the signature) — that entry is NOT an orphan because this record names its seq.
LOOP_OUTCOMES = ("SCORED", "REFUSED_BY_GATE", "STOP_LINK2", "STOP_LINK3", "REFUSED_BY_PL",
                 "STOP_AXI", "STOP_ARM", "STOP_SETTLE", "STOP_AUDIT", "STOP_SIGN")
EPOCH_END_KINDS = ("COMPLETED", "STOPPED", "PROTOCOL", "CRASHED")
VERIFIED_MARKS = ("audited", "replayed-only")     # rule (ix): a bounded guarantee, said out loud
CLOSING_STEPS = ("restore", "baseline", "unsigned_control")
GENOME_HEX = 80


def _check_app_identity(r):
    if r["control_plane"] != "standalone":
        raise RecordError("app_identity is a standalone-plane record")
    _hex(r["token"], 32, "token (the FULL 128-bit session token)")
    _hex(r["carrier_sha256"], HEX64, "carrier_sha256 (full width; review #1 blocker 3)")
    _hex(r["nonce_at_start"], 16, "nonce_at_start")
    if not isinstance(r["findings"], list):
        raise RecordError("app_identity findings must be a list")


def _check_sign_request(r):
    _hex(r["token"], 32, "token")
    _hex(r["genome"], GENOME_HEX, "genome")
    _hex(r["nonce"], 16, "nonce")
    if not isinstance(r["seq"], int) or r["seq"] < 1:
        raise RecordError("sign_request seq must be an integer >= 1")


def _check_sign_reply(r):
    _hex(r["commit"], HEX64, "commit (the FULL candidate_sha256)")
    _hex(r["tag"], 32, "tag")
    if len(r["expected_tables"]) != 6:
        raise RecordError("sign_reply expected_tables must have six entries")


def _check_sign_refusal(r):
    if not r["finding_kinds"] or not all(isinstance(k, str) for k in r["finding_kinds"]):
        raise RecordError("sign_refusal finding_kinds must be a non-empty list of kind strings")


def _check_notary_log(r):
    _hex(r["token"], 32, "token")
    last = 0
    for e in r["entries"]:
        for k in ("seq", "request", "answer", "at"):
            if k not in e:
                raise RecordError(f"notary_log entry missing {k!r}")
        req, ans = validate(e["request"]), validate(e["answer"])
        if ans["schema"] not in ("sign_reply", "sign_refusal"):
            raise RecordError("a notary_log answer is a sign_reply or a sign_refusal, nothing else")
        if not (e["seq"] == req["seq"] == ans["seq"]):
            raise RecordError(f"notary_log entry seq {e['seq']} disagrees with its request/answer")
        if req["token"] != r["token"]:
            raise RecordError("a notary_log entry's request token is not this session's")
        if e["seq"] <= last:
            raise RecordError("notary_log seq must be strictly increasing")
        last = e["seq"]


def _check_app_oracle_record(r):
    for k in ("staged_sha256", "staged_stream_sha256", "readback_sha256"):
        _hex(r[k], HEX64, k)
    if r["staged_sha256"] == r["staged_stream_sha256"]:
        raise RecordError("staged frames and staged stream hashes are different domains and cannot coincide")
    if not isinstance(r["audit_available"], bool):
        raise RecordError("audit_available must be a bool")


def _need(ev: dict, keys: tuple, outcome: str) -> None:
    missing = [k for k in keys if k not in ev]
    if missing:
        raise RecordError(f"loop_record outcome {outcome}: evidence missing {missing}")


def _forbid(ev: dict, keys: tuple, outcome: str) -> None:
    present = [k for k in keys if k in ev]
    if present:
        raise RecordError(f"loop_record outcome {outcome}: evidence must not contain {present}")


def _check_settle(arm: dict, out: str) -> None:
    """The bounded post-strobe poll every ARM record must describe (session 3)."""
    s = arm["settle"]
    if not isinstance(s, dict):
        raise RecordError("arm.settle must be an object")
    _need(s, ("polls", "polls_max", "settled", "status_first", "status_last"), out + " settle")
    if not isinstance(s["settled"], bool):
        raise RecordError("settle.settled must be a bool")
    if not isinstance(s["polls"], int) or not isinstance(s["polls_max"], int):
        raise RecordError("settle.polls and polls_max must be integers")
    if s["polls"] < 1 or s["polls_max"] < 1 or s["polls"] > s["polls_max"]:
        raise RecordError("settle.polls must lie in 1..polls_max")
    if s["settled"] and s["polls"] == s["polls_max"] and s["polls_max"] > 1:
        pass  # settling exactly on the last poll is legal; nothing to reject
    if s["status_last"] != arm["status_after"]:
        raise RecordError("status_after must be the last STATUS the poll read (settle.status_last)")


def _check_loop_record(r):
    from validators import nonce as nc
    if r["outcome"] not in LOOP_OUTCOMES:
        raise RecordError(f"loop_record outcome {r['outcome']!r} is not one of {LOOP_OUTCOMES}")
    if r["verified"] not in VERIFIED_MARKS:
        raise RecordError(f"loop_record verified {r['verified']!r} is not one of {VERIFIED_MARKS} (rule ix)")
    _hex(r["genome"], GENOME_HEX, "genome")
    ev = r["evidence"]
    if not isinstance(ev, dict):
        raise RecordError("loop_record evidence must be an object")
    out = r["outcome"]
    if out == "REFUSED_BY_GATE":
        _need(ev, ("sign_refusal",), out)
        _forbid(ev, ("sign_reply", "arm", "score", "app_oracle_record"), out)
        ref = validate(ev["sign_refusal"])
        if ref["seq"] != r["seq"]:
            raise RecordError("sign_refusal seq differs from the loop_record's")
        return
    if out == "STOP_SIGN":
        _need(ev, ("sign_stop",), out)
        _forbid(ev, ("sign_reply", "sign_refusal", "arm", "score", "app_oracle_record"), out)
        ss = ev["sign_stop"]
        if not isinstance(ss, dict) or not isinstance(ss.get("attempts"), int) or ss["attempts"] < 1 \
                or not isinstance(ss.get("why"), str) or not ss["why"]:
            raise RecordError("STOP_SIGN: sign_stop must carry attempts (an integer >= 1) and why")
        if r["verified"] != "replayed-only":
            raise RecordError("STOP_SIGN: nothing was staged, the record cannot be marked audited")
        return
    _need(ev, ("sign_reply",), out)
    reply = validate(ev["sign_reply"])
    if reply["seq"] != r["seq"]:
        raise RecordError("sign_reply seq differs from the loop_record's")
    if out == "STOP_AXI":
        _forbid(ev, ("arm", "score"), out)
        if "app_oracle_record" in ev:       # a post-staging stop: its self-report is checked
            oracle = validate(ev["app_oracle_record"])
            if oracle["seq"] != r["seq"]:
                raise RecordError("app_oracle_record seq differs from the loop_record's")
            if oracle["staged_sha256"] != reply["commit"]:
                raise Falsified("staged_sha256 != the signed commit — link 2's binding failed, this record cannot stand (prereg §3: a candidate past link 2 while staged != commit)")
        return
    if out == "STOP_LINK2":
        _forbid(ev, ("arm", "score"), out)
        return
    if out == "STOP_AUDIT":
        # staged and (usually) read back; the audit failed before any ARM: no arm, no score
        _forbid(ev, ("arm", "score"), out)
        _need(ev, ("app_oracle_record", "audit_stop"), out)
        oracle = validate(ev["app_oracle_record"])
        if oracle["seq"] != r["seq"]:
            raise RecordError("app_oracle_record seq differs from the loop_record's")
        if oracle["staged_sha256"] != reply["commit"]:
            raise Falsified("staged_sha256 != the signed commit — link 2's binding failed, this record cannot stand (prereg §3: a candidate past link 2 while staged != commit)")
        if r["verified"] != "replayed-only":
            raise RecordError("STOP_AUDIT: an audit that did not complete cannot be marked audited")
        return
    _need(ev, ("app_oracle_record",), out)
    oracle = validate(ev["app_oracle_record"])
    if oracle["seq"] != r["seq"]:
        raise RecordError("app_oracle_record seq differs from the loop_record's")
    if oracle["staged_sha256"] != reply["commit"]:
        raise Falsified("staged_sha256 != the signed commit — link 2's binding failed, this record cannot stand (prereg §3: a candidate past link 2 while staged != commit)")
    if out == "STOP_LINK3":
        _forbid(ev, ("arm", "score"), out)
        if oracle["readback_sha256"] == reply["commit"]:
            raise RecordError("STOP_LINK3 with readback == commit is a contradiction")
        return
    # STOP_ARM, REFUSED_BY_PL and SCORED all carry an ARM attempt
    if oracle["readback_sha256"] != reply["commit"]:
        raise RecordError(f"{out} requires readback == commit (no ARM without link 3)")
    _need(ev, ("arm",), out)
    arm = ev["arm"]
    _need(arm, ("nonce_before", "nonce_after", "status_after", "fault_after", "key_loaded_observed",
                "settle"), out)
    _hex(arm["nonce_before"], 16, "nonce_before"); _hex(arm["nonce_after"], 16, "nonce_after")
    _check_settle(arm, out)
    nb, na = int(arm["nonce_before"], 16), int(arm["nonce_after"], 16)
    if out == "STOP_SETTLE":
        # the bounded poll ran out: the gate never settled. Neutral — nothing is claimed
        # about why, and the nonce is whatever it was last seen to be.
        _forbid(ev, ("score",), out)
        if arm["settle"]["settled"] is not False or arm["settle"]["polls"] != arm["settle"]["polls_max"]:
            raise RecordError("STOP_SETTLE means the poll exhausted polls_max without settling")
        if na != nb and na != nc.step(nb):
            raise Falsified("STOP_SETTLE: the nonce is neither unchanged nor stepped once by "
                            "the model — the PL consumed something the model does not describe")
        return
    if arm["settle"]["settled"] is not True:
        raise RecordError(f"{out} requires the gate to have settled; an ARM that never settled is STOP_SETTLE")
    if out == "STOP_ARM":
        # the defining observation: the gate settled and the PL did not consume the attempt
        _forbid(ev, ("score",), out)
        if na != nb:
            raise RecordError(
                "STOP_ARM but the nonce stepped — the PL DID consume this ARM, so the "
                "outcome is REFUSED_BY_PL or SCORED, not STOP_ARM")
        return
    if na != nc.step(nb):
        raise Falsified("the nonce did not step by the model across a consumed ARM attempt (prereg §3: nonce chain)")
    if out == "REFUSED_BY_PL":
        _forbid(ev, ("score",), out)
        if not arm["fault_after"]:
            raise RecordError("REFUSED_BY_PL with fault 0 is a contradiction")
        return
    # SCORED
    _need(ev, ("score",), out)
    if arm["fault_after"]:
        raise RecordError("SCORED with a fault is a contradiction")
    if arm["key_loaded_observed"] is not True:
        raise RecordError("(v) a score with key_loaded_observed false")
    score = ev["score"]
    _need(score, ("hw_candidate_commit", "functional_readout", "scores", "heartbeat"), out)
    if score["hw_candidate_commit"] != reply["commit"]:
        raise Falsified("(ii) hw_candidate_commit != the signed commit")
    # B1 (docs/b1_carrier_contract.md): rule (iii) of the instrument compared the readout with
    # the HOST'S expected tables — the host attesting semantics before the measurement, which
    # is exactly what B1 must not do. Under the B1 contract the signed table slots are the
    # twelve zero words (the host supplied NO semantics) and the readout is the PL's raw
    # observation: six 64-bit tables, checked for shape only. A reply carrying non-zero
    # tables is a contract violation — the host attested something — and is refused.
    for t in reply["expected_tables"]:
        _hex(t, 16, "expected_tables[]")
    if any(int(t, 16) != 0 for t in reply["expected_tables"]):
        raise RecordError("(iii-B1) the signed expected_tables are not the zero contract: the host attested semantics")
    if len(score["functional_readout"]) != 6:
        raise RecordError("six LUTs read out six tables")
    for t in score["functional_readout"]:
        _hex(t, 16, "functional_readout[]")
    if len(score["scores"]) != 6:
        raise RecordError("six LUTs score six counters")


def _check_session_summary(r):
    end = r["epoch_end"]
    for k in ("kind", "reason", "last_seq"):
        if k not in end:
            raise RecordError(f"epoch_end missing {k!r}")
    if end["kind"] not in EPOCH_END_KINDS:
        raise RecordError(f"epoch_end kind {end['kind']!r} is not one of {EPOCH_END_KINDS}")
    _hex(r["token"], 32, "token")
    closing = r["closing"]
    if sorted(closing) != sorted(CLOSING_STEPS) or any(v not in ("done", "not_reached") for v in closing.values()):
        raise RecordError(f"closing must map exactly {CLOSING_STEPS} to done|not_reached")
    kind = end["kind"]
    if kind == "COMPLETED" and any(closing[s] != "done" for s in CLOSING_STEPS):
        raise RecordError("(viii) COMPLETED requires all three closing steps done — the brackets are not optional")
    if kind in ("STOPPED", "PROTOCOL") and (closing["baseline"] == "done" or closing["unsigned_control"] == "done"):
        raise RecordError(f"(viii) {kind}: no closing ARM after a stop (restore only)")
    if kind == "CRASHED":
        if r["written_by"] != "collector":
            raise RecordError("a CRASHED summary is written by the collector; the application is gone")
        if any(v != "not_reached" for v in closing.values()):
            raise RecordError("CRASHED with closing steps done is a contradiction")
    if r["written_by"] not in ("app", "collector"):
        raise RecordError("written_by must be app or collector")
    audit = r["audit"]
    if "audited" not in audit or "total" not in audit or audit["audited"] > audit["total"]:
        raise RecordError("audit must report audited <= total (rule ix)")
    if r["crc_dropped"] > r["drop_budget"] and kind not in ("PROTOCOL", "CRASHED"):
        raise RecordError("crc_dropped exceeds the drop budget but the epoch did not end PROTOCOL")


def validate_standalone_run_log(log: dict, blank_commit: str, nonce_seed: int,
                                audits: list[dict], manifest: dict | None = None) -> dict:
    """Rules (vii)–(ix) over one standalone session (spec §7), WITH the audit gate.
    `blank_commit` is the blank candidate's gate hash; `nonce_seed` the carrier's
    NONCE_SEED; `audits` the served audit chunks (an empty list when none were served —
    it is not optional, so that no caller can forget the gate); `manifest` the frame
    manifest the words are recomputed against (required when chunks were served).

    Every record's `verified` mark is DERIVED here from the served words (validators.audit)
    and the application's own mark must agree with it — the mark is never taken on trust.
    Served words that do not recompute the record's hashes are `Falsified` (prereg §3).
    Raises RecordError naming the rule; returns {scored, audited, chain_length, marks, audit}."""
    from validators import nonce as nc
    from validators import audit as au
    for k in ("app_identity", "notary_log", "loop_records", "session_summary"):
        if k not in log:
            raise RecordError(f"standalone run log missing {k!r}")
    ident = validate(log["app_identity"])
    notary = validate(log["notary_log"])
    summary = validate(log["session_summary"])
    records = [validate(r) for r in log["loop_records"]]
    if ident["token"] != notary["token"] or ident["token"] != summary["token"]:
        raise RecordError("token differs across app_identity / notary_log / session_summary")
    by_seq = {}
    for r in records:
        if r["seq"] in by_seq:
            raise RecordError(f"two loop_records share seq {r['seq']}")
        by_seq[r["seq"]] = r
    # STOP_SIGN exists only under rel-v4 (review 2026-09-02, item 6): under any other wire
    # protocol the board has no sign transaction to exhaust, so the outcome is a lie
    if any(r["outcome"] == "STOP_SIGN" for r in records) and log["app_identity"].get("protocol") != "rel-v4":
        raise RecordError(f"STOP_SIGN under wire protocol {log['app_identity'].get('protocol')!r}: the outcome exists "
                          f"only under rel-v4")
    # the audit gate: host-derived marks, and the application's marks must agree
    marks, audit_detail = au.verify(log, audits, manifest)
    for seq in sorted(by_seq):
        if by_seq[seq]["verified"] != marks[seq]:
            raise RecordError(
                f"(ix) seq {seq}: the record says verified {by_seq[seq]['verified']!r} but the host "
                f"{'verified the served words' if marks[seq] == 'audited' else 'could not verify it'}: "
                f"host-derived mark is {marks[seq]!r}"
                + (f" — {audit_detail[seq]['short']}" if audit_detail[seq].get("short") else ""))
    notary_by_seq = {e["seq"]: e for e in notary["entries"]}
    # (vii) every ARM-carrying record has a notary entry binding the same seq, commit, nonce
    chain = nonce_seed & 0xFFFFFFFFFFFFFFFF
    attempts = 0
    for seq in sorted(by_seq):
        r = by_seq[seq]
        if r["outcome"] == "STOP_SIGN":
            # rel-v4: the exchange was never acknowledged on the board; a notary entry for
            # this seq may exist (the reply was lost after the signature) and consumed nothing
            if seq != max(by_seq):
                raise RecordError(f"(vii) seq {seq}: STOP_SIGN is terminal — no record may follow it")
            e = notary_by_seq.get(seq)
            if e is not None and e["answer"].get("schema") not in ("sign_reply", "sign_refusal"):
                raise RecordError(f"(vii) seq {seq}: the notary entry behind STOP_SIGN is not a reply or refusal")
            continue
        if r["outcome"] == "REFUSED_BY_GATE":
            e = notary_by_seq.get(seq)
            if e is None or e["answer"].get("schema") != "sign_refusal":
                raise RecordError(f"(vii) seq {seq}: REFUSED_BY_GATE without a matching notary refusal")
            continue
        e = notary_by_seq.get(seq)
        if e is None:
            raise RecordError(f"(vii) seq {seq}: no notary_log entry")
        if e["answer"].get("schema") != "sign_reply":
            raise RecordError(f"(vii) seq {seq}: the notary answered a refusal but the record claims a signed candidate")
        if e["answer"]["commit"] != r["evidence"]["sign_reply"]["commit"]:
            raise RecordError(f"(vii) seq {seq}: notary commit != the record's commit")
        arm = r["evidence"].get("arm")
        if arm is not None:
            if e["request"]["nonce"] != arm["nonce_before"]:
                raise Falsified(f"(vii) seq {seq}: the nonce signed is not the nonce the ARM consumed")
            if int(arm["nonce_before"], 16) != chain:
                raise Falsified(f"(vii) seq {seq}: nonce_before is not the model chain value {chain:016x}")
            # A STOP_ARM consumed nothing: the gate settled and never stepped the nonce, so
            # the chain does not advance and no attempt is counted. A STOP_SETTLE advances
            # iff the nonce was seen stepped (checked per record). Anything else advances both.
            if r["outcome"] == "STOP_ARM":
                pass
            elif r["outcome"] == "STOP_SETTLE":
                if arm["nonce_after"] != arm["nonce_before"]:
                    chain = nc.step(chain)
                    attempts += 1
            else:
                chain = nc.step(chain)
                attempts += 1
    # (vii-b, rel-v4 review 2026-09-02) an application-written epoch leaves no notary entry
    # without a record: every signature the host gave is accounted for by a record of its
    # seq (SCORED, a stop, REFUSED_BY_GATE, or the terminal STOP_SIGN). A collector-written
    # (CRASHED) summary may leave the in-flight candidate's entry, and says so by its kind.
    if summary["written_by"] == "app":
        orphans = sorted(s for s in notary_by_seq if s not in by_seq)
        if orphans:
            raise RecordError(f"(vii) notary entries without a record: {orphans} — a signed request the application "
                              f"never recorded (a lost reply under rec-v3; under rel-v4 that seq must be a STOP_SIGN record)")
    # closing negative control consumes the last nonce (COMPLETED only)
    kind = summary["epoch_end"]["kind"]
    closing_neg = log.get("closing_negative")
    if kind == "COMPLETED":
        if closing_neg is None:
            raise RecordError("(viii) COMPLETED without the closing unsigned-ARM control")
        if closing_neg.get("fault") != EXPECTED_FAULT["unsigned"]:
            raise Falsified("(viii) the closing unsigned ARM was not refused F_ARM_AUTH — KILL, not a record")
        if int(closing_neg["nonce_before"], 16) != chain:
            raise Falsified("(viii) the closing control's nonce is not the model chain value")
        chain = nc.step(chain)
        attempts += 1
        scored = [by_seq[s] for s in sorted(by_seq) if by_seq[s]["outcome"] == "SCORED"]
        if not scored or scored[0]["evidence"]["sign_reply"]["commit"] != blank_commit:
            raise RecordError("(viii) the first scored record is not the opening baseline (blank candidate)")
        if scored[-1]["evidence"]["sign_reply"]["commit"] != blank_commit:
            raise RecordError("(viii) the last scored record is not the closing baseline (blank candidate)")
    elif closing_neg is not None:
        raise RecordError(f"(viii) {kind}: a closing ARM control cannot exist after a stop")
    # (ix) audit accounting — against the HOST-derived marks
    audited = sum(1 for m in marks.values() if m == "audited")
    if summary["audit"]["audited"] != audited:
        raise RecordError(f"(ix) summary says {summary['audit']['audited']} audited, the host verified {audited}")
    if summary["audit"]["total"] != len(records):
        raise RecordError("(ix) audit total != number of loop records")
    return {"scored": sum(1 for r in records if r["outcome"] == "SCORED"),
            "audited": audited, "chain_length": attempts, "marks": marks, "audit": audit_detail}


# A gate refusal makes no oracle self-report: nothing was staged, no raw words exist, and
# the notary_log itself corroborates it (rule vii). STOP_AXI is exempt ONLY while it is a
# pre-staging stop, i.e. carries no `app_oracle_record` (L6 prereg §3a item 3); a STOP_AXI
# that carries one is a raw self-report like any other and must be auto-audited (review
# 2026-09-01: exempting the outcome by NAME let a post-staging STOP_AXI with an unaudited
# oracle record through). The classification is by content, `self_report_class`.
NO_SELF_REPORT_OUTCOMES = ("REFUSED_BY_GATE", "STOP_SIGN")
# L6 prereg §3a item 2: the non-SCORED outcomes that may carry a raw self-report — under
# the sampled policy the firmware audits these unconditionally, before the record.
AUTO_AUDIT_OUTCOMES = ("STOP_LINK2", "STOP_LINK3", "REFUSED_BY_PL", "STOP_ARM", "STOP_SETTLE", "STOP_AXI", "STOP_AUDIT")
AUDIT_POLICIES = ("all-self-reporting", "sampled")
ARMS = ("random_safe", "map_guided")                       # L6 prereg §2.4
L6_IDENTITY_FIELDS = ("master_seed", "schedule_mode", "operator_data_sha256")


def self_report_class(r: dict) -> str:
    """What a record claims that only raw words can back: "none" (a gate refusal, or a
    pre-staging STOP_AXI with no oracle record), "scored" (a SCORED record's oracle
    claim), or "auto" (a non-SCORED record that staged: an oracle record, or STOP_LINK2's
    staged != commit claim). Decided from the record's content, never from its name alone."""
    out = r["outcome"]
    ev = r.get("evidence", {})
    if out in NO_SELF_REPORT_OUTCOMES:
        return "none"
    if out == "STOP_LINK2" or "app_oracle_record" in ev:
        return "scored" if out == "SCORED" else "auto"
    return "none"


def _self_reporting(r: dict) -> bool:
    return self_report_class(r) != "none"


def check_audit_policy(log: dict, marks: dict, policy: str = "all-self-reporting",
                       schedule: set | None = None) -> dict:
    """The audit condition, machine-checked instead of asserted in prose.

    `all-self-reporting` (L5 session 1, L6 C1/C2): every candidate which made a claim the
    host cannot otherwise verify -- every record carrying an `app_oracle_record`, and every
    candidate that staged and then refused itself at link 2 -- was backed by raw words the
    application served AND the host recomputed. A candidate refused by the gate never
    staged anything, so no raw words exist and it is exempt.

    `sampled` (L6 soak, prereg §3a): a SCORED candidate must be audited iff its seq is in
    the preregistered `schedule` (an audit outside the schedule is recorded, not refused);
    EVERY non-SCORED self-report (`AUTO_AUDIT_OUTCOMES`) must have been auto-audited by the
    firmware -- one that was not is an unaudited self-report under the policy and is
    refused here (the session is a HOLD, §3a item 5). Whether served words recompute is
    the audit gate's question (validators.audit), asked before this one: words that do not
    recompute are `Falsified` there, for auto-served words exactly as for requested ones.

    `marks` are the HOST-derived marks returned by `validate_standalone_run_log`; the
    record's own mark is not consulted. Returns the accounting; raises RecordError naming
    the offenders.
    """
    if policy not in AUDIT_POLICIES:
        raise RecordError(f"unknown audit policy {policy!r}")
    if policy == "sampled" and not isinstance(schedule, (set, frozenset)):
        raise RecordError("the sampled audit policy needs its preregistered schedule (a set of seqs)")
    must, auto, exempt, extra = [], [], [], []
    offenders, offenders_auto = [], []
    for r in log["loop_records"]:
        seq = r["seq"]
        if not _self_reporting(r):
            exempt.append(seq)
            continue
        audited = marks.get(seq) == "audited"
        if policy == "all-self-reporting":
            must.append(seq)
            if not audited:
                offenders.append(seq)
        elif r["outcome"] == "SCORED":
            if seq in schedule:
                must.append(seq)
                if not audited:
                    offenders.append(seq)
            elif audited:
                extra.append(seq)
        else:
            auto.append(seq)
            if not audited:
                offenders_auto.append(seq)
    problems = []
    if offenders:
        problems.append(f"candidates {offenders} made a self-report the host cannot otherwise check "
                        f"but were not audited" + (" (scheduled)" if policy == "sampled" else ""))
    if offenders_auto:
        problems.append(f"non-SCORED self-reports {offenders_auto} were not auto-audited by the firmware "
                        f"(§3a item 2): an unaudited self-report under the sampled policy")
    if problems:
        raise RecordError(f"audit policy {policy!r}: " + "; ".join(problems))
    out = {"policy": policy, "audited": must, "exempt_no_self_report": exempt}
    if policy == "sampled":
        out.update({"schedule": sorted(s for s in schedule), "audited_auto": auto, "unscheduled_audited": extra})
    return out


def check_arm_schedule(log: dict, schedule_rows: list[dict], n: int,
                       expected_genomes: dict | None = None) -> dict:
    """L6 prereg §2.4 / §6.5: every candidate record names its arm, and it is the schedule's
    arm for that index; the two baselines (seq 1 and seq N+2) are brackets and carry none.
    With `expected_genomes` ({seq: genome hex} from the host twin of the operators) the
    record's genome must also be the one the scheduled operator produces for that seed —
    naming the right arm while running the wrong operator is refused too."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise RecordError("check_arm_schedule needs the session's N")
    by_seq = {}
    for row in schedule_rows:
        if row["arm"] not in ARMS:
            raise RecordError(f"schedule names arm {row['arm']!r}, not one of {ARMS}")
        by_seq[row["seq"]] = row["arm"]
    first, last = 1, n + 2
    checked, brackets = [], []
    for r in log["loop_records"]:
        seq, arm = r["seq"], r.get("arm")
        if seq in (first, last):
            if arm is not None:
                raise RecordError(f"seq {seq} is a baseline bracket and must not carry an arm (got {arm!r})")
            brackets.append(seq)
            continue
        if seq > last:
            raise RecordError(f"seq {seq} lies beyond the session's N + 2 = {last}")
        if arm is None:
            raise RecordError(f"seq {seq}: loop_record.arm is required for a candidate (prereg §2.4)")
        if arm not in ARMS:
            raise RecordError(f"seq {seq}: arm {arm!r} is not one of {ARMS}")
        if seq not in by_seq:
            raise RecordError(f"seq {seq}: the schedule has no row for this candidate")
        if arm != by_seq[seq]:
            raise RecordError(f"seq {seq}: the record says arm {arm!r} but the schedule says {by_seq[seq]!r} "
                              f"(prereg §2.4: a swapped arm is refused)")
        if expected_genomes is not None:
            want = expected_genomes.get(seq)
            if want is None:
                raise RecordError(f"seq {seq}: no expected genome from the operator twin")
            if r["genome"] != want:
                raise RecordError(f"seq {seq}: the genome is not what the scheduled {arm} operator produces "
                                  f"for this seed (twin mismatch)")
        checked.append(seq)
    return {"checked": checked, "brackets": brackets, "n": n}


def check_l6_identity(app_identity: dict, master_seed: int, schedule_mode: str,
                      operator_data_sha256: str, protocol: str | None = None,
                      rec_retry_control: bool | None = None, sign_retry_control: bool | None = None) -> dict:
    """L6 prereg §2.4: the IDENT names the master seed and the operator-image identity (the
    hash of the map data compiled in), and the schedule mode the page asked for. Read from
    the raw record (additive 1.1.0 fields); each must equal what the host wrote.

    rec-v3 (prereg v0.4 draft): with `protocol` given, the IDENT (1.2.0) must declare that
    wire protocol — an image that does not say `rec-v3` cannot be running the REC
    transaction, whatever the manifest claims; with `rec_retry_control` given, the IDENT
    must echo the identity page's control flag as the application decoded it."""
    missing = [k for k in L6_IDENTITY_FIELDS if k not in app_identity]
    if missing:
        raise RecordError(f"app_identity lacks the L6 fields {missing} (prereg §2.4)")
    if protocol is not None:
        got = app_identity.get("protocol")
        if got != protocol:
            raise RecordError(f"app_identity declares wire protocol {got!r}, this session requires {protocol!r} "
                              f"(an image without the REC transaction cannot run under it)")
    if rec_retry_control is not None:
        got = app_identity.get("rec_retry_control")
        if not isinstance(got, bool) or got != rec_retry_control:
            raise RecordError(f"app_identity rec_retry_control is {got!r}, the identity page armed {rec_retry_control}")
    if sign_retry_control is not None:
        # rel-v4 (v0.6 §2.6d, IDENT 1.3.0): the page's flags.bit5 echoed, like bit4
        got = app_identity.get("sign_retry_control")
        if not isinstance(got, bool) or got != sign_retry_control:
            raise RecordError(f"app_identity sign_retry_control is {got!r}, the identity page armed {sign_retry_control}")
    if app_identity["master_seed"] != master_seed:
        raise RecordError(f"app_identity master_seed {app_identity['master_seed']!r} != the page's {master_seed}")
    if app_identity["schedule_mode"] != schedule_mode:
        raise RecordError(f"app_identity schedule_mode {app_identity['schedule_mode']!r} != {schedule_mode!r}")
    _hex(app_identity["operator_data_sha256"], HEX64, "operator_data_sha256")
    if app_identity["operator_data_sha256"] != operator_data_sha256:
        raise RecordError("app_identity operator_data_sha256 is not the pinned map derivation: the image's "
                          "compiled-in map data is not the one regenerated from local_map.json")
    out = {k: app_identity[k] for k in L6_IDENTITY_FIELDS}
    for k in ("protocol", "rec_retry_control", "sign_retry_control"):
        if k in app_identity:
            out[k] = app_identity[k]
    return out
