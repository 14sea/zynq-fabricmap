#!/usr/bin/env python3
"""B3 lifecycle 2 — the board runner. HOST-ONLY UNTIL RULED, and no board work is authorised today.
B2's `host/b2_runner.py` is the template; docs/b3_architecture.md v0.3 §7–§8, preregistration
v0.3.1 §2 (transport, deadline, records), §6.

    b3_runner.py --ruling <whole-of-run json> --provision-ruling <P3-K json>
                 --boundary <principal_boundary json> --out <evidence dir>
                 --pair-first N --pair-count N [--image …] [--manifest …]
                 [--instrument-root …] [--port …] [--key …] [--signer-user …]

Two PROFILES share this preflight and session function, in the preregistration's order (§6):

  B3Q  image qualification and calibration — the B3 image on the QUALIFIED B1 carrier against the
       **S1** manifest; ONE pair at budget 40 (pair_first 0, pair_count 1: 120 search + 3 holdout
       + 2 baselines = 125 records, 40 ledger entries); the session's measured all-self-reporting
       rate is what S2 pins as the calibration — REPORTED here, never pinned here.
  B3   the closed loop — one session per slice of the plan's split, against the **S3** manifest;
       the slice's pairs and seeds are the plan's and the prediction's, never redrawn.

FAIL-CLOSED, in this order, before any port, any JTAG and any ruling claim — each a named refusal
and none of them a skip:

  the evidence directory does not exist (no-clobber, first of all); both rulings exist, parse,
  carry their text and are unconsumed; the instrument checkout binds (host-only, its own pins);
  the principal boundary is a valid, passed, fresh record naming this OS user, the signer and
  the key; the manifest / pin AUTHORITY (see the seam below):
  the manifest exists and is a B3 manifest, names the board, the preregistration is FROZEN and
  hashes, the image is pinned, board_ready, present and hashing; the profile's stage (B3Q: not yet
  qualified, no plan; B3: qualified with a pinned plan and prediction whose bytes hash to the
  manifest) and the plan and prediction accepted by the adjudicator's own input guards and the
  records context; the manifest's own lifecycle verify and the instrument pin table; the
  instrument at its pinned commit; the carrier's bitstream hashing to its pin and the B1 chain
  re-verified; the session's slice (B3: --pair-first / --pair-count inside the experiment AND one
  the plan's split gives; B3Q: none — pair 0, count 1, budget 40 are fixed); the identity 1.6.0
  contract; the record count from the frozen arithmetic (2 + N × (3B + 3)) against the split /
  the pinned experiment; the deadline from the frozen formula; the transport: the expected frames
  from the instrument's production schedule over the ACTUAL record count, the CRC / bad-frame
  budget from the frozen formula (never a literal), the rel-v4 resend budget the ruling must
  carry and its transport disposition; then both rulings BOUND — the whole-of-run ruling to this
  session, the frozen preregistration, the pinned image, the sha256 of THIS manifest file, the
  master seed and (B3) the actual slice; the P3-K ruling to session / preregistration / image /
  manifest and to no master seed.

THE AUTHORITY SEAM. `manifests/b3_manifest.json`, `b3/host/b3_manifest.py` and `b3/host/b3_pins.py`
do not exist yet (they are later pinned edits). The runner reaches them only through an `Authority`
adapter: `production_authority()` imports them lazily and, while they are absent, is a named
REFUSED — no output directory, no ruling claimed, no device touched. A test may inject a fake
authority; the command line offers no way to skip or replace one. The manifest's production
re-adjudicator wiring, the real pin verification and every stage transition belong to the
manifest / pins units: this runner never transitions a manifest.

THE DEVICE SEAM. The image load, the serial port, the session loop, the ruling claim and the
export are reached through `Ports`, whose production members import the instrument lazily; a test
injects fakes and never starts a device or a subprocess.

ONE RULING PAIR, ONE ATTEMPT. The runner never retries, never redraws a seed, never lifts the
transport stop-loss: it records this session's cause and transport accounting
(`runner_session.json`) and leaves the cross-session "two sessions lost to the same cause → stop"
to the owner's process. Every error path finalises; the primary cause is kept and a secondary
export / close / record error never replaces it.

THE RULING TEXTS BELOW ARE PROPOSALS. The owner writes rulings; if these strings are not the ones
the owner intends to sign, change them here — the runner refuses any other text.

WHAT IS NOT DONE HERE: no board session has been run and none is authorised; every fixture is the
model standing in for a board; the pooled primary is `b3_adjudicate --scope run` over every
session's log once they all exist, never this runner's.
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
import traceback
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b2_search as bs  # noqa: E402
import b2_session as b2sess  # noqa: E402
import b3_adjudicate as adj  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_plan as pl  # noqa: E402
import b3_records as brec  # noqa: E402
import b3_session as bsess  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

TOOL_VERSION = "b3_runner.py/0.1.0"
SESSION = "B3"
QUAL_SESSION = "B3Q"
MANIFEST_SCHEMA = "b3_manifest"
MANIFEST = REPO_ROOT / "manifests/b3_manifest.json"
B1_MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"
MANIFEST_AT_RUN = "manifest_at_run.json"
B3_VARIANT = "0x42310001"
PROTOCOL_WIRE = "rel-v4"
IMAGE = REPO_ROOT / "b3/firmware/bsp/out/b3_app.bin"
IDENTITY_SCHEMA_VERSION = brec.IDENTITY_SCHEMA_VERSION            # 1.6.0

# Proposals until the owner signs them (module docstring).
RULING_TEXT = "whole-of-run B3 closed loop"
QUAL_RULING_TEXT = "whole-of-run B3 image qualification and calibration"
PROVISION_RULING_TEXT = "provisioning P3-K"

QUAL_BUDGET = pl.QUAL_BUDGET                                       # 40
QUAL_PAIRS = pl.QUAL_PAIRS                                         # 1
AUDIT_POLICY = pl.AUDIT_POLICY                                     # all-self-reporting
CALIBRATION_MARGIN = pl.CALIBRATION_MARGIN                         # 0.85
RESEND_PER_MILLE = 4                                               # preregistration §2 transport: N = ceil(4 × expected_frames / 1000)
WATCHDOG_LOAD, WATCHDOG_PRESCALER = 1250000035, 7

SEARCH = {"session": SESSION, "ruling_text": RULING_TEXT, "stage": "S3", "tool": TOOL_VERSION}
QUALIFICATION = {"session": QUAL_SESSION, "ruling_text": QUAL_RULING_TEXT, "stage": "S1", "tool": "b3_runner.py/0.1.0 (B3Q)"}


def deadline_s(records: int, rate_for_split: float) -> float:
    """The preregistration's frozen formula (§2: 1.25 × records × 3600 / rate_for_split + 600)."""
    return 1.25 * records * 3600 / rate_for_split + 600


def resend_budget(expected_frames_total: int) -> int:
    """The rel-v4 resend budget of preregistration §2: N = ceil(4 × expected_frames / 1000)."""
    if expected_frames_total < 1:
        raise Refusal(f"expected frames {expected_frames_total}: no budget can be derived")
    return math.ceil(RESEND_PER_MILLE * expected_frames_total / 1000)


class Refusal(Exception):
    """Fail-closed: a named reason why this invocation does not reach a board."""


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _short(v) -> str:
    text = repr(v) if isinstance(v, str) else json.dumps(v, sort_keys=True, default=str)
    return text if len(text) <= 72 else text[:69] + "..."


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


# ------------------------------------------------------------------ the authority seam


class Authority:
    """What the runner needs of the manifest / pin authority. `production_authority()` binds it to
    `b3_manifest` / `b3_pins` when they exist; a test injects an object with these members.

    The manifest fields the runner READS (the contract the manifest unit must meet): `schema`,
    `board.boardid`, `prereg.{path,sha256,frozen}`, `image.{sha256,board_ready}`, `qualified`,
    `qualification`, `plan.{path,sha256,prediction_path,prediction_sha256}`,
    `qualification_plan.{path,sha256,prediction_path,prediction_sha256}`, `seeds.master_seed`,
    `instrument.psoracle_commit`, `carrier.{bitstream_sha256,variant}`, `map.canonical_json_sha256`,
    `universe.sha256`, `experiment.fitness`."""

    name = "abstract"

    def check_board(self, manifest: dict) -> str:
        b = manifest.get("board")
        if not isinstance(b, dict) or not isinstance(b.get("boardid"), str) or not b["boardid"].strip():
            raise Refusal("the manifest pins no board: this stage has no board authority")
        return b["boardid"]

    def manifest_sha256(self, manifest: dict) -> str:
        return hashlib.sha256((json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode()).hexdigest()

    def verify(self, manifest: dict, readjudicate=None) -> dict:      # the manifest lifecycle verify (S0–S3, the §7a pre-check, B2 authority, B1 lineage)
        raise Refusal(f"{self.name}: no manifest verifier")

    def verify_pins(self, manifest: dict, root: Path) -> dict:         # the B3 instrument pin table
        raise Refusal(f"{self.name}: no pin verifier")


class ProductionAuthority(Authority):
    """`b3_manifest` / `b3_pins`, imported on first use; absent → a named refusal."""

    name = "production"

    def __init__(self):
        self._m = self._p = None

    def _modules(self):
        if self._m is None:
            try:
                import b3_manifest as m  # noqa: E402
                import b3_pins as p  # noqa: E402
            except ImportError as exc:
                raise Refusal("no B3 manifest / pin authority: b3/host/b3_manifest.py and b3/host/b3_pins.py do not exist "
                              f"yet (they are later pinned edits; S0 has not happened) — host-only, no output, no ruling, "
                              f"no device ({exc})") from None
            self._m, self._p = m, p
        return self._m, self._p

    @staticmethod
    def _refusals(module, *names) -> tuple:
        """The refusal classes the authority module DECLARES (`Refusal`, `PinRefusal`); only those become
        this runner's Refusal — an AttributeError or TypeError inside the authority is an implementation
        defect and stays an INTERNAL ERROR (the owner's P3 on ab71192)."""
        return tuple(c for c in (getattr(module, n, None) for n in names) if isinstance(c, type) and issubclass(c, BaseException))

    def check_board(self, manifest: dict) -> str:
        m, _ = self._modules()
        try:
            return m.check_board(manifest)
        except self._refusals(m, "Refusal") as exc:
            raise Refusal(str(exc)) from None

    def manifest_sha256(self, manifest: dict) -> str:
        m, _ = self._modules()
        return m.manifest_sha256(manifest)

    def verify(self, manifest: dict, readjudicate=None) -> dict:
        m, _ = self._modules()
        try:
            return m.verify(manifest, readjudicate=readjudicate)
        except self._refusals(m, "Refusal") as exc:
            raise Refusal(f"manifest: {exc}") from None

    def verify_pins(self, manifest: dict, root: Path) -> dict:
        _, p = self._modules()
        try:
            return p.verify(manifest=manifest)
        except self._refusals(p, "PinRefusal", "Refusal") as exc:
            raise Refusal(f"instrument pins: {exc}") from None


def production_authority() -> Authority:
    """The only authority the command line can use. It refuses by name until the manifest and pin
    tools exist; there is no flag to skip it."""
    a = ProductionAuthority()
    a._modules()                      # refuse NOW, before anything else is read or written
    return a


# ------------------------------------------------------------------ the device / instrument seam


@dataclass
class Ports:
    """Every contact with the instrument, a port or the filesystem of a session, as callables a
    test replaces. The production members import the instrument lazily (never at module import)."""
    which: object = shutil.which
    bind_instrument: object = None                 # (root) -> {"psoracle_commit": …, …}
    verify_carrier_chain: object = None            # (b1_manifest, instrument_root) -> None, or raises
    schedule: object = None                        # () -> the instrument's l6_schedule module
    write_artifacts: object = None                 # (out, manifest_path, ruling_path, pk_path, manifest_sha, expected) -> dict
    claim_ruling: object = None                    # (path) -> consumed marker path
    record_outcome: object = None                  # (consumed, why) -> None
    record_pk: object = None                       # (pk_path, outcome) -> None
    install_sigterm: object = None                 # () -> None
    open_transport: object = None                  # (port) -> transport (with .close())
    board_session: object = None                   # (transport) -> session
    run_session: object = None                     # (session, out_dir, ruling, cfg, identity_check, adjudicate, tool) -> summary dict
    instrument_layer: object = None                # (evidence, log, session_plan, instrument_root) -> {"findings", "rejected", "rate", "audit_policy", ...}
    make_signer: object = None                     # (key_path, signer_user) -> the signer (sign_genome / provision), the gate-signer principal
    session_refusal: type = Exception              # the transport / session refusal exception type
    consts: object = None                          # the carrier constants for the adjudicator (None = the instrument's)
    common_validation: bool = True                 # the instrument's common-envelope validation inside the record replay (production: always)

    def production(self) -> "Ports":
        return Ports(which=shutil.which, bind_instrument=_prod_bind, verify_carrier_chain=_prod_carrier_chain,
                     schedule=_prod_schedule, write_artifacts=_prod_write_artifacts, claim_ruling=_prod_claim,
                     record_outcome=_prod_record_outcome, record_pk=_prod_record_pk, install_sigterm=_prod_sigterm,
                     open_transport=_prod_transport, board_session=_prod_board_session, run_session=_prod_run_session,
                     instrument_layer=instrument_findings, make_signer=_prod_signer, session_refusal=_prod_session_refusal(), consts=None,
                     common_validation=True)


def _prod_bind(root):
    try:
        return inst.bind(root)
    except inst.InstrumentRefusal as exc:
        raise Refusal(f"instrument: {exc}") from None


def _prod_carrier_chain(b1_manifest: dict, instrument_root) -> None:
    import b1_qualification as bq  # noqa: E402
    try:
        bq.verify(b1_manifest, require_git=True, instrument_root=instrument_root)
    except bq.QualificationRefusal as exc:
        raise Refusal(f"the B1 carrier this image runs on is not qualified: {exc}") from None


def _prod_schedule():
    import l6_schedule as ls  # noqa: E402
    return ls


def _prod_write_artifacts(out, manifest_path, ruling_path, pk_path, manifest_sha, expected) -> dict:
    import b1_qualification as bq  # noqa: E402
    try:
        return bq.write_session_artifacts(Path(out), Path(manifest_path), Path(ruling_path), Path(pk_path), manifest_sha,
                                          expected_rulings=expected)
    except bq.QualificationRefusal as exc:
        raise Refusal(str(exc)) from None


def _prod_claim(path):
    import pcap_probe_runner as pr  # noqa: E402
    return pr.claim_ruling(Path(path))


def _prod_record_outcome(consumed, why):
    import pcap_probe_runner as pr  # noqa: E402
    pr.record_outcome(Path(consumed), why)


def _prod_record_pk(pk_path, outcome):
    import l3_runner as l3  # noqa: E402
    l3._record_pk(Path(pk_path), outcome)


def _prod_signer(key_path, signer_user):
    import l3_runner as l3  # noqa: E402
    return l3.SubprocessSigner(Path(key_path), script=REPO_ROOT / "host/b1_sign_arm.py", signer_user=signer_user)


# The cfg keys the instrument's session driver (`b1_session.run`) reads — BEFORE its own protected
# block for `heartbeat_s` and `signer`. A preflight that returns a cfg without any of them would claim
# the ruling and open the port and then crash (the owner's P1 on ab71192); `check_session_cfg` holds
# the returned cfg to this list.
SESSION_CFG_KEYS = ("bitstream", "carrier", "heartbeat_s", "image", "image_sha256", "instrument", "manifest_sha256", "plan",
                    "provision_execute", "provision_ruling", "signer", "token")


def check_session_cfg(cfg: dict) -> None:
    missing = [k for k in SESSION_CFG_KEYS if cfg.get(k) is None]
    if missing:
        raise Refusal(f"the session cfg lacks {missing}: the session driver would crash after the ruling was claimed")
    signer = cfg["signer"]
    for attr in ("sign_genome", "provision"):
        if not callable(getattr(signer, attr, None)):
            raise Refusal(f"the signer has no callable {attr!r}: the session driver would crash after the ruling was claimed")
    if not isinstance(cfg["heartbeat_s"], (int, float)) or isinstance(cfg["heartbeat_s"], bool) or cfg["heartbeat_s"] <= 0:
        raise Refusal(f"heartbeat_s {cfg['heartbeat_s']!r} is not a positive number")


def _prod_sigterm():
    import l3_runner as l3  # noqa: E402
    l3._install_sigterm()


def _prod_transport(port):
    import board_session as bsn  # noqa: E402
    return bsn.SerialTransport(port)


def _prod_board_session(transport):
    import board_session as bsn  # noqa: E402
    return bsn.BoardSession(transport)


def _prod_run_session(session, out_dir, ruling, cfg, identity_check, adjudicate, tool):
    import b1_session  # noqa: E402
    return b1_session.run(session, out_dir, ruling, cfg, identity_check, adjudicate, tool)


def _prod_session_refusal():
    try:
        import board_session as bsn  # noqa: E402
        return bsn.SessionRefusal
    except ImportError:
        return Refusal


# ------------------------------------------------------------------ the rulings


def read_ruling(path: Path, text: str) -> dict:
    """The ruling file: unconsumed, readable, an object with the four fields and THIS text. The
    board it names is compared once the manifest authority is loaded (`check_ruling_board`)."""
    path = Path(path)
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
    return r


def check_ruling_board(r: dict, path: Path, want_board: str) -> None:
    if r["boardid"] != want_board:
        raise Refusal(f"ruling {path} names board {r['boardid']!r}, this stage is {want_board!r}")


def bind_ruling(ruling: dict, text: str, session: str, prereg_sha: str, image_sha: str, manifest_sha: str,
                master_seed: int | None, slice_: tuple[int, int] | None) -> None:
    """The binding a ruling must carry: this session, this preregistration, this image, THIS
    manifest file; the whole-of-run ruling also the master seed and (B3) the actual slice; the P3-K
    ruling neither."""
    want = {"session": session, "prereg_sha256": prereg_sha, "image_sha256": image_sha, "b3_manifest_sha256": manifest_sha}
    if master_seed is not None:
        want["master_seed"] = master_seed
    if slice_ is not None:
        want["pair_first"], want["pair_count"] = slice_
    for k, v in want.items():
        if k not in ruling:
            raise Refusal(f"ruling {text!r} is not bound: it lacks {k!r}")
        got = ruling[k]
        if k in ("master_seed", "pair_first", "pair_count") and isinstance(got, str):
            try:
                got = int(got, 0)
            except ValueError:
                raise Refusal(f"ruling {text!r}: {k} {got!r} is not a number") from None
        if got != v or (k in ("master_seed", "pair_first", "pair_count") and not _int(got)):
            raise Refusal(f"ruling {text!r} is bound to {k} = {got!r}, this session needs {v!r}")
    if master_seed is None and "master_seed" in ruling:
        raise Refusal(f"ruling {text!r} carries a master_seed: the provisioning ruling binds no experiment")


def check_transport_ruling(ruling: dict, text: str, want_resend: int, expected_total: int, want_disposition: str | None = None) -> dict:
    """Preregistration §2: every B3 session's ruling pair carries its own transport disposition and
    its rel-v4 resend budget N = ceil(4 × expected_frames / 1000) — computed from the production
    schedule over this session's actual record count, never a literal. With `want_disposition` (the
    offline rebinding) the disposition must be the one this invocation captured."""
    disp = ruling.get("transport_disposition")
    if not isinstance(disp, str) or not disp.strip():
        raise Refusal(f"ruling {text!r} carries no transport_disposition: no session runs without one (the CH340 stop-loss is in force)")
    if want_disposition is not None and disp != want_disposition:
        raise Refusal(f"ruling {text!r} carries the transport disposition {disp!r}, this session's is {want_disposition!r}")
    got = ruling.get("resend_budget")
    if not _int(got):
        raise Refusal(f"ruling {text!r} carries no integer resend_budget")
    if got != want_resend:
        raise Refusal(f"ruling {text!r} carries resend_budget {got}, this session's schedule gives ceil(4 × {expected_total} / 1000) = {want_resend}")
    return {"transport_disposition": disp, "resend_budget": got, "expected_frames_total": expected_total}


# ------------------------------------------------------------------ the pinned documents


def pinned_documents(manifest: dict, pin_key: str, session: str, root: Path = REPO_ROOT) -> tuple[dict, dict, dict]:
    """The plan and the prediction the manifest pins under `pin_key` ("plan" for B3 at S3,
    "qualification_plan" for B3Q), READ from the pinned bytes and held to them, then accepted by
    the adjudicator's own input guards and the records context."""
    pin = manifest.get(pin_key)
    if not isinstance(pin, dict):
        raise Refusal(f"the manifest pins no {pin_key}")
    for key in ("path", "sha256", "prediction_path", "prediction_sha256"):
        if not isinstance(pin.get(key), str) or not pin[key]:
            raise Refusal(f"the manifest's {pin_key} pins no {key}")
    docs = []
    for key, digest_key, what in (("path", "sha256", "plan"), ("prediction_path", "prediction_sha256", "prediction")):
        path = Path(root) / pin[key]
        if not path.is_file():
            raise Refusal(f"the pinned {what} {pin[key]} is absent")
        if _sha(path) != pin[digest_key]:
            raise Refusal(f"the pinned {what} {pin[key]} does not hash to the manifest's pin")
        try:
            docs.append(json.loads(path.read_text()))
        except ValueError as exc:
            raise Refusal(f"the pinned {what} {pin[key]} is not readable JSON: {exc}") from None
    plan, prediction = docs
    if not isinstance(plan, dict) or plan.get("session") != session:
        raise Refusal(f"the pinned plan is for session {plan.get('session') if isinstance(plan, dict) else None!r}, this profile is {session!r}")
    try:
        adj.check_plan(plan)
        adj.check_prediction(prediction, plan)
    except adj.Refusal as exc:
        raise Refusal(f"the pinned plan/prediction: {exc}") from None
    return plan, prediction, pin


def slice_in_split(plan: dict, first: int, count: int) -> dict | None:
    """The split entry for this slice, or None: a B3 session runs a slice the plan's split gives —
    never an arbitrary one — and the entry carries the session's records and deadline. Until B3Q
    measures the rate the split is UNDETERMINED and no slice is licensed at all."""
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


# ------------------------------------------------------------------ the identity and the binding


def expected_identity(manifest: dict, session_plan: dict) -> dict:
    """The complete `app_identity` 1.6.0 contract for a session — ONE definition, used online
    before the board's identity is acknowledged AND offline when the evidence is re-adjudicated."""
    return {"schema_version": IDENTITY_SCHEMA_VERSION, "search_version": bs.ENGINE_VERSION,
            "map_sha256": manifest["map"]["canonical_json_sha256"], "operator_data_sha256": manifest["map"]["canonical_json_sha256"],
            "fitness_id": manifest["experiment"]["fitness"], "budget_per_arm": session_plan["n"],
            "master_seed": session_plan["master_seed"], "pairs_total": session_plan["pairs_total"],
            "pair_first": session_plan["pair_first"], "pair_count": session_plan["pair_count"],
            "carrier_variant": B3_VARIANT, "carrier_sha256": manifest["carrier"]["bitstream_sha256"],
            "universe_sha256": manifest["universe"]["sha256"], "protocol": PROTOCOL_WIRE,
            "rec_retry_control": True, "sign_retry_control": True,
            "carto_version": carto_mod.CARTO_VERSION, "arms": brec.ARMS, "b1_map_cost": oa.B1_MAP_COST}


def identity_findings(ident, manifest: dict, session_plan: dict) -> list[str]:
    if not isinstance(ident, dict):
        return ["the session declared no app_identity object"]
    out = [f"IDENT {k}: {_short(ident.get(k))} != {_short(v)}" for k, v in sorted(expected_identity(manifest, session_plan).items())
           if ident.get(k) != v]
    for forbidden in brec.IDENTITY_FORBIDDEN:
        if forbidden in ident:
            out.append(f"IDENT {forbidden}: this image issues no probes (the online map is built from specimens)")
    if ident.get("findings"):
        out.append(f"IDENT findings: {ident['findings']}")
    return out


def identity_check_for(cfg: dict):
    def check(ident: dict) -> list[str]:
        return identity_findings(ident, cfg["manifest"], cfg["plan"])
    return check


def expected_inputs(manifest: dict, profile: dict, authority: Authority) -> dict:
    pin = manifest.get("plan" if profile is SEARCH else "qualification_plan") or {}
    return {"plan_sha256": pin.get("sha256"), "prediction_sha256": pin.get("prediction_sha256"),
            "b3_manifest_sha256": authority.manifest_sha256(manifest), "stage": profile["stage"]}


def binding_findings(log: dict, session_plan: dict, manifest: dict | None = None) -> list[str]:
    """The session's identity and its invocation, established from the EVIDENCE — the l6 block's
    binding and inputs, and the whole identity 1.6.0 contract."""
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
                    f.append(f"inputs: the log's {k} is {_short(inputs_got.get(k))}, this invocation's is {_short(inputs_want[k])}")
    if manifest is not None:
        f += identity_findings(log.get("app_identity"), manifest, session_plan)
    else:
        f.append("no manifest to hold the IDENT to: the identity contract was not checked")
    return f


def archived_ruling_findings(evidence: Path, session_plan: dict) -> list[str]:
    """The two archived authorisations, DECODED and REBOUND through the instrument's strict
    envelope reader — read, never claimed, never consumed."""
    import b1_qualification as bq  # noqa: E402
    want = session_plan.get("binding") or {}
    session = session_plan.get("session")
    texts = {"whole_of_run": QUAL_RULING_TEXT if session == QUAL_SESSION else RULING_TEXT, "provisioning": PROVISION_RULING_TEXT}
    want = dict(want, transport_disposition=session_plan.get("transport_disposition"))
    f: list[str] = []
    boards: dict[str, object] = {}
    want_board = want.get("boardid")
    if not isinstance(want_board, str) or not want_board.strip():
        f.append(f"this session declares no board authority ({want_board!r}): the archived authorisations cannot be rebound to one")
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
        for field_ in ("boardid", "granted_by", "date"):
            if not ruling.get(field_):
                f.append(f"{name}: the archived ruling lacks {field_!r}")
        boards[key] = ruling.get("boardid")
        # the SAME guards the preflight applied to the live rulings (the owner's P2 on ab71192): the binding
        # (the whole-of-run ruling to the master seed and the slice; the P3-K ruling to neither), and the
        # transport disposition and resend budget equal to what this invocation captured
        needed = ("session", "prereg_sha256", "image_sha256", "b3_manifest_sha256") + \
            (("master_seed", "pair_first", "pair_count", "resend_budget", "transport_disposition") if key == "whole_of_run" else ())
        absent = [k for k in needed if want.get(k) is None]
        if absent:
            f.append(f"{name}: this invocation declares no {absent}, so the archive cannot be rebound")
            continue
        try:
            if key == "whole_of_run":
                bind_ruling(ruling, text, session, want["prereg_sha256"], want["image_sha256"], want["b3_manifest_sha256"], want["master_seed"],
                            (want["pair_first"], want["pair_count"]))
                check_transport_ruling(ruling, text, want["resend_budget"], session_plan["expected_frames"]["total"], want["transport_disposition"])
            else:
                for k in ("pair_first", "pair_count"):
                    if k in ruling:
                        f.append(f"{name}: the archived provisioning ruling carries {k!r}: it binds no slice")
                bind_ruling(ruling, text, session, want["prereg_sha256"], want["image_sha256"], want["b3_manifest_sha256"], None, None)
        except Refusal as exc:
            f.append(f"{name}: {exc}")
    if len(boards) == len(bq.RULING_FILES) and len(set(map(str, boards.values()))) != 1:
        f.append(f"the two archived authorisations name different boards: { {k: _short(v) for k, v in boards.items()} }")
    if want_board is not None:
        for key, got in boards.items():
            if not isinstance(got, str) or not got.strip():
                f.append(f"{bq.RULING_FILES[key]}: the archived ruling's boardid {_short(got)} is not a non-empty string")
            elif got != want_board:
                f.append(f"{bq.RULING_FILES[key]}: the archived ruling names board {_short(got)}, this stage is {_short(want_board)}")
    return f


def export_seal_findings(evidence: Path) -> list[str]:
    import b1_adjudicate as b1adj  # noqa: E402
    try:
        b1adj.check_exports(Path(evidence))
    except b1adj.Refusal as exc:
        return [f"evidence seal: {exc}"]
    return []


def archived_manifest_findings(evidence: Path, manifest: dict, session_plan: dict) -> list[str]:
    p = Path(evidence) / MANIFEST_AT_RUN
    if not p.is_file():
        return [f"the evidence carries no {MANIFEST_AT_RUN}: the session archived no manifest"]
    want_sha = (session_plan.get("binding") or {}).get("b3_manifest_sha256")
    got_sha = _sha(p)
    f: list[str] = []
    if want_sha is None:
        f.append("this invocation declares no manifest digest to hold the archived manifest to")
    elif got_sha != want_sha:
        f.append(f"the archived {MANIFEST_AT_RUN} hashes to {got_sha[:16]}…, this invocation's manifest to {want_sha[:16]}…")
    try:
        at_run = json.loads(p.read_text())
    except ValueError as exc:
        return f + [f"the archived {MANIFEST_AT_RUN} is not readable JSON: {exc}"]
    if not isinstance(at_run, dict) or at_run.get("schema") != MANIFEST_SCHEMA:
        return f + [f"the archived {MANIFEST_AT_RUN} is not a {MANIFEST_SCHEMA} document"]
    for path, label in ((("image", "sha256"), "image"), (("prereg", "sha256"), "preregistration"),
                        (("map", "canonical_json_sha256"), "map"), (("carrier", "bitstream_sha256"), "carrier")):
        a, b = at_run, manifest
        for k in path:
            a = (a or {}).get(k) if isinstance(a, dict) else None
            b = (b or {}).get(k) if isinstance(b, dict) else None
        if a != b:
            f.append(f"the archived manifest's {label} is not this invocation's")
    return f


def instrument_findings(evidence: Path, log: dict, session_plan: dict, instrument_root: Path) -> dict:
    """The instrument and evidence contract for ONE session — B2's `instrument_findings`, over B3's
    plan: the standalone run-log validation with the audit gate, the declared audit policy, the
    structural / baseline / REC / rel closure and control findings, the transport budgets, the rate
    report, the deadline, the epoch's own outcome. Production only (the instrument modules)."""
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
        if not (Path(evidence) / name).is_file():
            f.append(f"the evidence carries no {name}: the session's transport was not recorded")
    if f:
        return out
    audits = json.loads((Path(evidence) / "audits.json").read_text())
    timeline = json.loads((Path(evidence) / "timeline.json").read_text())
    frames = timeline.get("frames") or []
    chunks = audits.get("chunks") or []
    b1_manifest = json.loads(B1_MANIFEST.read_text())
    nonce_seed = int(b1_manifest["carrier"]["nonce_seed"], 16)
    phen = g.load_manifest()
    blank_commit = g.gate(g.build_streams(gn.frames_from_genome(gn.blank_genome(phen), phen), phen), phen)["candidate_sha256"]
    l6m = json.loads((Path(instrument_root) / "manifests/l6_manifest.json").read_text())
    try:
        v = records.validate_standalone_run_log(log, blank_commit, nonce_seed, chunks, phen)
        out["run_log_validation"] = {k: v[k] for k in ("scored", "audited", "chain_length") if k in v}
        records.check_audit_policy(log, v["marks"], session_plan["audit_policy"], None)
        out["audit_policy"] = session_plan["audit_policy"]
        f += lc.structural_findings(log, chunks, set(session_plan["audit_seqs"]), frames, protocol=session_plan["protocol"], hb_rule="v07")
        f += lc.baseline_findings(log)
        rec_ledgers = audits.get("recs") or []
        f += lc.rec_closure_findings(log, rec_ledgers)
        f += lc.rec_control_findings(rec_ledgers, bool(session_plan["flags"] & ls.FLAG_REC_CONTROL))
        f += lc.rel_closure_findings(log, audits, audits.get("pulls") or [])
        f += lc.rel_control_findings(audits.get("signs") or [], bool(session_plan["flags"] & ls.FLAG_SIGN_CONTROL))
        try:
            rep = lr.rate_report_from_evidence_dir(Path(evidence), None)
            out["rate_report"] = {k: rep.get(k) for k in ("candidates", "evals_per_hour", "cov", "session_span_s")}
            out["rate"] = rep.get("evals_per_hour")
            pc = l6m["pass_conditions"]
            f += lc.soak_findings(log, frames, int(timeline.get("crc_dropped") or 0), session_plan["crc_budget"], rep["session_span_s"],
                                  duration_s=0.0, hb_gap_max_s=pc["hb_gap_max_s"], settle_median_calib=16.0,
                                  settle_bound_factor=pc["settle_bound_factor"], wall_fraction_min=0.0,
                                  bad_frames=int(timeline.get("bad_frames") or 0), bad_frame_budget=session_plan["bad_frame_budget"])
            limit = session_plan.get("session_timeout_s")
            if limit is None:
                f.append("the session plan carries no deadline: the archived session is held to no limit")
            elif rep["session_span_s"] > float(limit):
                f.append(f"the session spanned {rep['session_span_s']:.1f} s, past the {float(limit):.1f} s deadline this session was authorised for")
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
                f.append(f"the epoch ended at seq {last!r}, not the {session_plan['expected_records']} records this session's slice requires")
    except _instrument_records.RecordError as exc:
        out["rejected"] = l5.classify_rejection(exc)
        out["run_log_validation"] = f"REJECTED: {exc}"
    return out


# ------------------------------------------------------------------ the session verdict


def judge_session(evidence_dir, manifest: dict, session_plan: dict, plan_doc: dict, prediction_doc: dict,
                  instrument_root: Path, ports: Ports) -> dict:
    """The session's verdict: the instrument and evidence contract COMPOSED with the B3 record
    replay at scope "session". Never a pooled primary. The result carries what the lifecycle
    consumes (a B3Q session's MEASURED all-self-reporting rate and VERIFIED audit policy) — reported
    for a later S2 transition, never pinned here."""
    evidence = Path(evidence_dir)
    session = session_plan["session"]
    out = {"tool": TOOL_VERSION, "session": session, "scope": "session", "outcome": None, "findings": [], "kills": [],
           "measured_rate_per_hour": None, "audit_policy": None, "instrument": {}, "binding_checked": False, "replay": {},
           "pooled_primary": "not this runner's: b3_adjudicate --scope run over every session's log"}
    archived = archived_manifest_findings(evidence, manifest, session_plan)
    if archived:
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
    p3 = ports.instrument_layer(evidence, log, session_plan, instrument_root)
    out["instrument"] = {k: v for k, v in p3.items() if k not in ("findings", "rejected")}
    out["measured_rate_per_hour"] = p3.get("rate")
    out["audit_policy"] = p3.get("audit_policy")
    out["findings"] = seal + rulings + binding + list(p3.get("findings") or [])
    out["binding_checked"] = not binding and not seal and not rulings
    if p3.get("rejected"):
        out["outcome"] = p3["rejected"]
        return out
    rep = adj.adjudicate([log], plan_doc, prediction_doc, consts=ports.consts, common=ports.common_validation, scope="session")
    out["replay"] = {k: rep.get(k) for k in ("scope", "measurement", "replay", "pair_seeds", "online_maps") if k in rep}
    for k in ("primary", "secondary_outcome", "deltas1", "deltas2", "fitness_sequence_sha256"):
        if k in rep:
            out["findings"].append(f"the session adjudication published {k}: a session scope must not")
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


REQUIRED_CFG = ("profile", "manifest", "plan", "instrument_root", "round_plan", "prediction", "ports")


def adjudication_for(cfg: dict):
    missing = [k for k in REQUIRED_CFG if cfg.get(k) is None]
    if missing:
        def refuse(evidence_dir) -> dict:
            return {"tool": TOOL_VERSION, "scope": "session", "findings": [], "kills": [], "measured_rate_per_hour": None,
                    "audit_policy": None, "outcome": f"REFUSED: no session verdict without {missing}: a record replay alone is not one"}
        return refuse

    def judge(evidence_dir) -> dict:
        return judge_session(evidence_dir, cfg["manifest"], cfg["plan"], cfg["round_plan"], cfg["prediction"], cfg["instrument_root"], cfg["ports"])
    return judge


# ------------------------------------------------------------------ preflight


def preflight(a, profile: dict = SEARCH, authority: Authority | None = None, ports: Ports | None = None, readjudicate=None) -> dict:
    """Everything host-only, in the documented order, before any port, JTAG or ruling claim.
    `authority` and `ports` are the seams; both default to production (a refusal while the
    authority does not exist), and neither default is a skip."""
    ports = ports or Ports().production()
    session = profile["session"]
    out = Path(a.out)
    if out.exists() or out.is_symlink():
        raise Refusal(f"{out} exists; evidence is never replaced (no-clobber)")
    if a.provision_ruling is None:
        raise Refusal("--provision-ruling is mandatory: no `provisioning P3-K` ruling, no board contact")
    ruling = read_ruling(a.ruling, profile["ruling_text"])
    pk = read_ruling(a.provision_ruling, PROVISION_RULING_TEXT)
    verified = ports.bind_instrument(a.instrument_root)          # host-only: the checkout's own pins; its validators read the boundary
    try:
        boundary = json.loads(Path(a.boundary).read_text())
    except (OSError, ValueError) as exc:
        raise Refusal(f"no readable principal boundary at {a.boundary}: {exc}") from None
    import b1_records as br  # noqa: E402 — the instrument's validators, bound above
    try:
        br.boundary_established(boundary, time.time())
    except (br.RecordError, br.SchemaError) as exc:
        raise Refusal(f"principal boundary: {exc}") from None
    me = pwd.getpwuid(os.getuid()).pw_name
    if boundary["runner_user"] != me:
        raise Refusal(f"principal boundary: runner_user {boundary['runner_user']!r} is not this OS user {me!r}")
    if boundary["signer_user"] != a.signer_user:
        raise Refusal(f"principal boundary: --signer-user {a.signer_user!r} is not the record's {boundary['signer_user']!r}")
    want_key = os.path.normpath(os.path.join(boundary["key_store"], "K.bin"))
    if os.path.normpath(str(a.key)) != want_key:
        raise Refusal(f"principal boundary: --key {a.key} is not the record's key store's {want_key}")

    authority = authority or production_authority()
    manifest_path = Path(a.manifest)
    if not manifest_path.is_file():
        raise Refusal(f"no B3 manifest at {manifest_path}: the manifest does not exist until S0, and no board session exists without it")
    try:
        manifest = json.loads(manifest_path.read_text())
    except ValueError as exc:
        raise Refusal(f"the B3 manifest is not readable JSON: {exc}") from None
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise Refusal(f"the manifest is not a {MANIFEST_SCHEMA} document")
    manifest_sha = _sha(manifest_path)
    board = authority.check_board(manifest)
    check_ruling_board(ruling, Path(a.ruling), board)
    check_ruling_board(pk, Path(a.provision_ruling), board)
    prereg = manifest.get("prereg") or {}
    if not prereg.get("sha256") or not prereg.get("frozen"):
        raise Refusal("B3's preregistration is not frozen (S1): host-only until the owner freezes it")
    prereg_path = REPO_ROOT / prereg["path"]
    if not prereg_path.is_file() or _sha(prereg_path) != prereg["sha256"]:
        raise Refusal(f"{prereg['path']} does not hash to the frozen preregistration")
    image = manifest.get("image") or {}
    if not image.get("sha256"):
        raise Refusal("the manifest pins no image")
    if not image.get("board_ready"):
        raise Refusal("the B3 image is not marked board_ready (the compatibility review and the freeze come first)")
    image_path = Path(a.image)
    if not image_path.is_file():
        raise Refusal(f"no application image at {image_path}")
    image_sha = _sha(image_path)
    if image_sha != image["sha256"]:
        raise Refusal(f"the image is not the pinned one: {image_sha[:16]}… != {image['sha256'][:16]}…")

    # the stage the profile requires, and the pinned documents
    if profile is QUALIFICATION:
        if manifest.get("qualified") or manifest.get("qualification"):
            raise Refusal("this manifest is already qualified: B3Q runs against the S1 manifest")
        if manifest.get("plan"):
            raise Refusal("this manifest already carries a plan: B3Q precedes S3")
        plan_doc, prediction_doc, pin = pinned_documents(manifest, "qualification_plan", QUAL_SESSION)
    else:
        if not manifest.get("qualified") or not manifest.get("qualification"):
            raise Refusal("the manifest is not qualified: B3Q and S2 come before any B3 session")
        plan_doc, prediction_doc, pin = pinned_documents(manifest, "plan", SESSION)

    authority.verify(manifest, readjudicate=readjudicate)      # the whole frozen chain, re-hashed, every call
    pins = authority.verify_pins(manifest, REPO_ROOT)
    if verified.get("psoracle_commit") != (manifest.get("instrument") or {}).get("psoracle_commit"):
        raise Refusal("the instrument is not at the commit this manifest pins")
    car = manifest.get("carrier") or {}
    if car.get("variant") != B3_VARIANT:
        raise Refusal("the manifest's carrier variant is not the qualified carrier's contract word")
    try:
        b1_manifest = json.loads(B1_MANIFEST.read_text())
    except (OSError, ValueError) as exc:
        raise Refusal(f"no readable B1 manifest: {exc}") from None
    ports.verify_carrier_chain(b1_manifest, a.instrument_root)
    bitstream = REPO_ROOT / b1_manifest["carrier"]["bitstream"]
    if not bitstream.is_file() or _sha(bitstream) != car.get("bitstream_sha256"):
        raise Refusal("the carrier bitstream does not hash to the manifest's pin")
    carrier_manifest_path = REPO_ROOT / b1_manifest["carrier"]["carrier_manifest"]["path"]
    if _sha(carrier_manifest_path) != b1_manifest["carrier"]["carrier_manifest"]["sha256"]:
        raise Refusal("the carrier manifest does not hash to the B1 manifest's pin")

    # the session's slice and its experiment — the plan's and the prediction's, never redrawn
    budget, pairs_total = plan_doc["budget_per_arm"], plan_doc["pairs"]
    master = plan_doc["seed_derivation"]["master_seed"]
    if profile is QUALIFICATION:
        first, count = 0, QUAL_PAIRS
        if a.pair_first not in (None, 0) or a.pair_count not in (None, QUAL_PAIRS):
            raise Refusal(f"B3Q runs {QUAL_PAIRS} pair at budget {QUAL_BUDGET}: it takes no slice")
        if budget != QUAL_BUDGET or pairs_total != QUAL_PAIRS:
            raise Refusal(f"the pinned B3Q plan is {pairs_total} pairs at budget {budget}, not {QUAL_PAIRS} at {QUAL_BUDGET}")
        split_entry = None
        pb = plan_doc.get("planning_bound") or {}
        rate = pb.get("rate_per_hour")
        if not isinstance(rate, (int, float)) or isinstance(rate, bool) or not math.isfinite(rate) or rate <= 0:
            raise Refusal(f"the pinned B3Q planning bound's rate {rate!r} is not a finite positive rate")
    else:
        if a.pair_first is None or a.pair_count is None:
            raise Refusal("a B3 session needs --pair-first and --pair-count: the plan's split assigns them")
        first, count = a.pair_first, a.pair_count
        if not _int(first) or not _int(count) or first < 0 or count <= 0 or first + count > pairs_total:
            raise Refusal(f"the slice ({first!r}, {count!r}) does not lie inside the experiment's {pairs_total} pairs")
        split_entry = slice_in_split(plan_doc, first, count)
        if split_entry is None:
            raise Refusal(f"the slice ({first}, {count}) is not one the plan's split gives (the split is "
                          f"{(plan_doc.get('session_split') or {}).get('status', 'absent')})")
        if master != (manifest.get("seeds") or {}).get("master_seed"):
            raise Refusal("the plan's master seed is not the manifest's")
    try:
        ctx = brec.context_from(plan_doc, prediction_doc, first, count)
    except brec.ContextError as exc:
        raise Refusal(f"the records context: {exc}") from None
    seeds = ctx.seeds

    # the record count, the deadline, the transport — the frozen arithmetic, never a literal
    records_expected = bsess.records(count, budget)
    if profile is SEARCH:
        if split_entry.get("records") != records_expected:
            raise Refusal(f"the plan's split says {split_entry.get('records')} records for this slice, the record arithmetic says {records_expected}")
        split = plan_doc["session_split"]
        rate_for_split = split.get("rate_for_split")
        if not isinstance(rate_for_split, (int, float)) or isinstance(rate_for_split, bool) or rate_for_split <= 0:
            raise Refusal("the plan's split carries no rate_for_split")
        timeout = deadline_s(records_expected, rate_for_split)
        if not math.isclose(float(split_entry.get("deadline_s", -1)), timeout, rel_tol=1e-9):
            raise Refusal(f"the split's deadline {split_entry.get('deadline_s')} is not the frozen formula's {timeout}")
        rate_note = {"source": "the plan's split, from the B3Q calibration under the 0.85 margin", "rate_for_split": rate_for_split,
                     "rate_measured": split.get("rate_measured"), "margin": split.get("calibration_margin")}
    else:
        if records_expected != (plan_doc.get("records") or {}).get("total"):
            raise Refusal(f"the pinned B3Q plan says {(plan_doc.get('records') or {}).get('total')} records, the record arithmetic says {records_expected}")
        timeout = deadline_s(records_expected, rate)
        if not math.isclose(float(pb.get("session_timeout_s", -1)), timeout, rel_tol=1e-9):
            raise Refusal(f"the pinned B3Q planning bound's session_timeout_s {pb.get('session_timeout_s')} is not the frozen formula's {timeout}")
        rate_note = {"source": "the pinned B3Q planning bound (never a calibration)", "rule": pb.get("rule"), "rate_per_hour": rate}
    ls = ports.schedule()
    l6m_path = Path(a.instrument_root) / "manifests/l6_manifest.json"
    try:
        l6m = json.loads(l6m_path.read_text())
    except (OSError, ValueError) as exc:
        raise Refusal(f"no readable instrument l6 manifest at {l6m_path}: {exc}") from None
    wd = l6m.get("pinned_at_build") or {}
    if not wd.get("watchdog_enabled") or wd.get("watchdog_load_value") != WATCHDOG_LOAD or wd.get("watchdog_prescaler") != WATCHDOG_PRESCALER:
        raise Refusal("D-s1: the watchdog pins are not the instrument's (watchdog_enabled / watchdog_load_value / watchdog_prescaler)")
    heartbeat_s = (l6m.get("protocol") or {}).get("heartbeat_s")
    if not isinstance(heartbeat_s, (int, float)) or isinstance(heartbeat_s, bool) or heartbeat_s <= 0:
        raise Refusal(f"the instrument's l6 manifest pins no positive heartbeat_s ({heartbeat_s!r})")
    wire = (b1_manifest.get("protocol") or {}).get("wire")
    if not isinstance(wire, str) or not wire:
        raise Refusal("the B1 manifest pins no protocol.wire: the frame arithmetic has no authority")
    if wire != PROTOCOL_WIRE:
        raise Refusal(f"the pinned wire protocol {wire!r} is not the {PROTOCOL_WIRE!r} this stage speaks")
    base_flags = ls.flags_for(ls.MODE_ABBA, watchdog=True, rec_control=True, sign_control=True)
    try:
        flags = b2sess.encode_slice(base_flags, pairs_total, first, count)
    except ValueError as exc:
        raise Refusal(f"the identity page cannot carry this slice: {exc}") from None
    audit_seqs = set(range(1, records_expected + 1))        # all-self-reporting: every record audited
    expected_frames = ls.expected_frames(records_expected - 2, audit_seqs, wire)
    if expected_frames["records"] != records_expected:
        raise Refusal(f"the frame arithmetic says {expected_frames['records']} records, the record arithmetic says {records_expected}")
    crc_budget = ls.crc_budget(expected_frames["total"])
    resend = resend_budget(expected_frames["total"])
    transport = check_transport_ruling(ruling, profile["ruling_text"], resend, expected_frames["total"])

    bind_ruling(ruling, profile["ruling_text"], session, prereg["sha256"], image_sha, manifest_sha, master,
                (first, count) if profile is SEARCH else (0, QUAL_PAIRS))
    bind_ruling(pk, PROVISION_RULING_TEXT, session, prereg["sha256"], image_sha, manifest_sha, None, None)
    if ports.which("sb") is None:
        raise Refusal("`sb` is not installed")

    session_plan = {
        "session": session, "mode": bs.ENGINE_VERSION, "master_seed": master, "n": budget, "schedule": [],
        "audit_policy": AUDIT_POLICY, "audit_seqs": audit_seqs, "pair_first": first, "pair_count": count, "pairs_total": pairs_total,
        "flags": flags, "expected_records": records_expected, "records_per_pair": pl.records_per_pair(budget),
        "ledger_entries": count * budget, "expected_frames": expected_frames,
        "crc_budget": crc_budget, "bad_frame_budget": crc_budget,
        "crc_formula": "ceil(4 x expected_total / 1000) (D-s4), from the instrument's l6_schedule",
        "resend_budget": resend, "resend_formula": "ceil(4 x expected_frames / 1000) (preregistration v0.3.1 §2 transport)",
        "transport_disposition": transport["transport_disposition"],
        "session_timeout_s": timeout, "deadline_formula": pl.DEADLINE_FORMULA, "deadline_rate": rate_note, "protocol": wire,
        "rules_version": "b3/v0.3 over L6 v0.7 rules", "bad_frame_policy": "ledger", "hb_rule": "v07", "rec_retry_control": True,
        "carto_version": carto_mod.CARTO_VERSION, "arms": brec.ARMS, "b1_map_cost": oa.B1_MAP_COST,
        "inputs": expected_inputs(manifest, profile, authority),
        "binding": {"image_sha256": image_sha, "prereg_sha256": prereg["sha256"], "session": session, "schedule_mode": bs.ENGINE_VERSION,
                    "master_seed": master, "b3_manifest_sha256": manifest_sha, "psoracle_commit": verified["psoracle_commit"],
                    "map_canonical_json_sha256": manifest["map"]["canonical_json_sha256"], "fitness_id": manifest["experiment"]["fitness"],
                    "budget_per_arm": budget, "pair_first": first, "pair_count": count, "protocol": wire,
                    "carrier_sha256": car["bitstream_sha256"], "carrier_variant": B3_VARIANT,
                    "universe_sha256": manifest["universe"]["sha256"], "boardid": board, "resend_budget": resend,
                    "carto_version": carto_mod.CARTO_VERSION},
    }
    cfg = {"profile": profile, "ruling": ruling, "provision_ruling_parsed": pk, "manifest": manifest, "manifest_sha256": manifest_sha,
           "manifest_path": manifest_path, "ruling_path": Path(a.ruling), "provision_ruling_path": Path(a.provision_ruling),
           "pins": pins, "carrier": {"bitstream_sha256": car["bitstream_sha256"]}, "bitstream": bitstream,
           "image": image_path, "image_sha256": image_sha, "plan": session_plan, "round_plan": plan_doc, "prediction": prediction_doc,
           "seeds": seeds, "context": ctx, "signer": ports.make_signer(a.key, a.signer_user), "provision_execute": True,
           "provision_ruling": a.provision_ruling, "token": secrets.token_hex(16), "instrument": verified, "instrument_root": a.instrument_root,
           "ports": ports, "authority": authority.name, "transport": transport, "l6_manifest": l6m, "heartbeat_s": heartbeat_s,
           "seed_nonce": int(b1_manifest["carrier"]["nonce_seed"], 16)}
    check_session_cfg(cfg)
    return cfg


# ------------------------------------------------------------------ execution


def classify(outcome: str) -> str:
    """The session's cause class for the owner's cross-session process: PASS, KILL, HOLD, or LOST
    (a stop, a crash, a refusal after the claim — re-run for the SAME pairs and seeds under a NEW
    ruling pair; never here)."""
    s = str(outcome)
    for k in ("PASS", "KILL", "HOLD"):
        if s.startswith(k):
            return k
    return "LOST"


def transport_accounting(out_dir: Path, summary: dict | None, session_plan: dict) -> dict:
    """What this session's transport did against what it was authorised: from the summary and the
    timeline when they exist, INCOMPLETE where they do not — never invented."""
    acc = {"expected_frames_total": session_plan["expected_frames"]["total"], "crc_budget": session_plan["crc_budget"],
           "bad_frame_budget": session_plan["bad_frame_budget"], "resend_budget": session_plan["resend_budget"],
           "transport_disposition": session_plan["transport_disposition"], "crc_dropped": None, "bad_frames": None,
           "frames_seen": None, "disruptions": None, "transport_rereads": None}
    if isinstance(summary, dict):
        for k in ("crc_dropped", "bad_frames", "disruptions", "transport_rereads"):
            if k in summary:
                acc[k] = summary[k]
    tl = Path(out_dir) / "timeline.json"
    if tl.is_file():
        try:
            t = json.loads(tl.read_text())
            acc["frames_seen"] = len(t.get("frames") or [])
            if acc["crc_dropped"] is None:
                acc["crc_dropped"] = t.get("crc_dropped")
            if acc["bad_frames"] is None:
                acc["bad_frames"] = t.get("bad_frames")
        except (OSError, ValueError) as exc:
            acc["timeline_error"] = f"{type(exc).__name__}: {exc}"
    return acc


def measured_rate_from(out_dir: Path, summary: dict | None) -> float | None:
    """The session verdict's measured all-self-reporting rate: from the summary when the driver kept
    it, else from the adjudication.json the finalizer wrote (the production `b1_session.finalize`
    copies only a subset of the verdict into the summary — the owner's P2 on ab71192)."""
    adjud = (summary or {}).get("adjudication") if isinstance(summary, dict) else None
    if isinstance(adjud, dict) and "measured_rate_per_hour" in adjud:
        return adjud["measured_rate_per_hour"]
    p = Path(out_dir) / "adjudication.json"
    if p.is_file():
        try:
            doc = json.loads(p.read_text())
            if isinstance(doc, dict):
                return doc.get("measured_rate_per_hour")
        except (OSError, ValueError):
            return None
    return None


def write_session_record(out_dir: Path, cfg: dict, outcome: str, summary: dict | None, stage: str, errors: list[str]) -> str | None:
    """runner_session.json: this session's outcome, its cause class, its transport accounting, and
    the statement that this ruling pair is spent — the runner retries nothing."""
    doc = {"tool": TOOL_VERSION, "session": cfg["plan"]["session"], "profile_stage": cfg["profile"]["stage"], "outcome": outcome,
           "cause": classify(outcome), "reached": stage, "pair_first": cfg["plan"]["pair_first"], "pair_count": cfg["plan"]["pair_count"],
           "master_seed": cfg["plan"]["master_seed"], "expected_records": cfg["plan"]["expected_records"],
           "transport": transport_accounting(out_dir, summary, cfg["plan"]),
           "ruling_pair": "spent: one ruling pair, one attempt — no retry, no redraw of seeds, no lifting of the transport stop-loss by this runner",
           "cross_session_stop_loss": "the owner's process: two sessions lost to the same cause → stop; three without COMPLETED → design review",
           "measured_rate_per_hour": measured_rate_from(out_dir, summary),
           "finalise_errors": list(errors), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        tmp = Path(out_dir) / "runner_session.json.part"
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str) + "\n")
        os.replace(tmp, Path(out_dir) / "runner_session.json")
        return "runner_session.json"
    except OSError as exc:
        errors.append(f"runner_session.json: {type(exc).__name__}: {exc}")
        return None


def execute(a, cfg: dict) -> tuple[int, str]:
    """The order after a passed preflight, FIXED as B1's: (1) the evidence directory; (2) the
    session artifacts — the manifest bytes and both rulings — archived and verified against what
    the preflight parsed, a failure here a REFUSED with no ruling consumed and no port; (3) the
    whole-of-run ruling claimed; (4) the port — the FIRST device contact; (5) the session. Every
    exit finalises: the outcome is recorded on the consumed markers and in runner_session.json;
    the primary cause is kept and a secondary export / close / record error never replaces it."""
    ports: Ports = cfg["ports"]
    out = Path(a.out)
    errors: list[str] = []
    stage = "artifacts"
    try:
        out.mkdir(parents=True, exist_ok=False)            # THIS invocation's directory, or nothing is ever written (the owner's P2 on ab71192)
    except OSError as exc:
        return 2, f"REFUSED: {out} appeared before the session could create it (no-clobber): {type(exc).__name__}: {exc}"
    try:
        ports.write_artifacts(out, cfg["manifest_path"], cfg["ruling_path"], cfg["provision_ruling_path"], cfg["manifest_sha256"],
                              (cfg["ruling"], cfg["provision_ruling_parsed"]))
    except (Refusal, OSError, ValueError) as exc:
        outcome = f"REFUSED: session artifacts not archived: {exc}"
        write_session_record(out, cfg, outcome, None, stage, errors)
        return 2, outcome
    stage = "claim"
    try:
        consumed = ports.claim_ruling(a.ruling)
    except Exception as exc:  # noqa: BLE001 — a claim that fails is a refusal with no port opened
        outcome = f"REFUSED: the ruling could not be claimed: {type(exc).__name__}: {exc}"
        write_session_record(out, cfg, outcome, None, stage, errors)
        return 2, outcome
    outcome = "CRASHED before a summary was written"
    summary = None
    transport = None
    try:
        ports.install_sigterm()
        stage = "port"
        transport = ports.open_transport(a.port)
        stage = "session"
        try:
            summary = ports.run_session(ports.board_session(transport), out, cfg["ruling"], cfg, identity_check_for(cfg),
                                        adjudication_for(cfg), cfg["profile"]["tool"])
            outcome = str((summary or {}).get("outcome") or "CRASHED: the session returned no outcome")
        finally:
            if transport is not None:
                try:
                    transport.close()
                except Exception as exc:  # noqa: BLE001 — secondary: recorded, never the outcome
                    errors.append(f"transport close: {type(exc).__name__}: {exc}")
    except ports.session_refusal as exc:
        outcome = f"REFUSED: {exc}"
    except Exception as exc:  # noqa: BLE001
        outcome = f"CRASHED host-side: {type(exc).__name__}: {exc}"
        errors.append("traceback: " + traceback.format_exc())
    finally:
        try:
            ports.record_outcome(consumed, outcome)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"record_outcome: {type(exc).__name__}: {exc}")
        try:
            ports.record_pk(a.provision_ruling, outcome)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"record_pk: {type(exc).__name__}: {exc}")
        write_session_record(out, cfg, outcome, summary, stage, errors)
    return (0 if outcome == "PASS" else 1), outcome


def main(argv=None, profile: dict = SEARCH) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ruling", type=Path, required=True)
    ap.add_argument("--provision-ruling", type=Path, default=None)
    ap.add_argument("--boundary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pair-first", type=int, default=None)
    ap.add_argument("--pair-count", type=int, default=None)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--instrument-root", type=Path, default=inst.DEFAULT_ROOT)
    ap.add_argument("--image", type=Path, default=IMAGE)
    ap.add_argument("--key", type=Path, default=Path("/var/lib/p3signer/keys/K.bin"))
    ap.add_argument("--signer-user", default="p3signer")
    ap.add_argument("--port", default="/dev/ebaz-uart")
    a = ap.parse_args(argv)
    try:
        cfg = preflight(a, profile)                       # the production authority and ports: no flag replaces them
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — a defect in this runner or its authority, never an input refusal
        print(f"INTERNAL ERROR: {type(exc).__name__}: {exc}\n{traceback.format_exc()}", file=sys.stderr)
        return 3
    rc, outcome = execute(a, cfg)
    print(outcome, file=sys.stderr if outcome != "PASS" else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
