"""b3/host/b3_runner.py — the B3 board runner's fail-closed preflight, its execution order and its
session verdict, with every device and every not-yet-existing authority behind an injected seam.

No test opens a port, starts a subprocess, consumes a real ruling or contacts a board: the
authority is a fake object (the manifest / pin tools do not exist yet — `production_authority`
refuses by name, tested through an injected import failure, never through a permanent "must not
exist" assertion), and every instrument / device member of `Ports` is a fake that records what
was called. The instrument checkout is bound host-only for its schedule arithmetic and its
validators (pure functions).

Held here: every preflight refusal is zero-contact (no evidence directory, no ruling claimed, no
port); the slice / seed / ruling / boundary / transport bindings; B3Q and B3 record accounting from
the frozen arithmetic; no-clobber; the claim order (artifacts → claim → port → session); the session
verdict at scope "session" with no pooled primary; KILL / HOLD / LOST recorded once with no retry;
evidence preserved and the primary cause kept through a detach, a timeout, an export error, a close
error and a record error; the production authority missing → REFUSED with nothing written.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import pwd
import shutil
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host", R / "b3/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import claimb_r1p_instrument as inst  # noqa: E402

INSTRUMENT = inst.bind(inst.DEFAULT_ROOT, require_git=False)       # host-only: the checkout's pins; its validators and schedule
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b1_records as br  # noqa: E402
import b1_session as b1s  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_adjudicate as badj  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_plan as pl  # noqa: E402
import b3_records as brec  # noqa: E402
import b3_runner as rn  # noqa: E402
import b3_session as bsess  # noqa: E402
import b3_test_fixtures as fx  # noqa: E402
import l6_schedule as ls  # noqa: E402

TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
SELF_MAP = bmaps.load_self_map()
VIEW = bmaps.MapView(SELF_MAP, bl.train_vectors())
MAP_SHA = bmaps.sha256_of(SELF_MAP)
CONSTS = json.loads(bl.CARRIER_CONSTANTS.read_text())
BUDGET, PAIRS = 12, 3
SEEDS = [(1000, 5000), (1001, 5001), (1002, 5002)]
MASTER = 716169644
RATE_MEASURED = 60.0                 # a rate at which two pairs fit a session and three do not: the split is [0, 1], [2]
QUAL_SEED = (2000, 6000)
QUAL_RATE = 2630.433828050359
BOARD = "17A6"
ME = pwd.getpwuid(os.getuid()).pw_name


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rendered(doc) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def rel(p: Path) -> str:
    return os.path.relpath(p, R)


# ------------------------------------------------------------------ the fixtures


PRED = pl.build_prediction("F1", BUDGET, SEEDS)
QPRED = pl.build_prediction("F1", pl.QUAL_BUDGET, [QUAL_SEED])


def b3_plan() -> dict:
    split = pl.session_split(PAIRS, BUDGET, RATE_MEASURED)
    return {"schema": "b3_plan", "schema_version": pl.SCHEMA_VERSION, "lifecycle": pl.LIFECYCLE, "session": "B3", "fitness": "F1",
            "budget_per_arm": BUDGET, "pairs": PAIRS, "seed_derivation": {"label": pl.SESSION_LABEL, "master_seed": MASTER},
            "map": {"sha256": MAP_SHA}, "carto_version": carto_mod.CARTO_VERSION, "b1_map_cost": oa.B1_MAP_COST,
            "records": {"per_pair": pl.records_per_pair(BUDGET), "ledger_entries_per_pair": BUDGET, "single_session_total": pl.session_records(PAIRS, BUDGET)},
            "session_split": split, "audit_policy": pl.AUDIT_POLICY}


def b3q_plan() -> dict:
    total = pl.session_records(pl.QUAL_PAIRS, pl.QUAL_BUDGET)
    return {"schema": "b3_plan", "schema_version": pl.SCHEMA_VERSION, "lifecycle": pl.LIFECYCLE, "session": "B3Q", "fitness": "F1",
            "budget_per_arm": pl.QUAL_BUDGET, "pairs": pl.QUAL_PAIRS, "carto_version": carto_mod.CARTO_VERSION, "b1_map_cost": oa.B1_MAP_COST,
            "map": {"sha256": MAP_SHA}, "seed_derivation": {"label": pl.QUAL_LABEL, "master_seed": 424242, "pairs": [list(QUAL_SEED)]},
            "records": {"per_pair": pl.records_per_pair(pl.QUAL_BUDGET), "search": 120, "holdout": 3, "ledger_entries": 40, "baselines": 2, "total": total},
            "audit_policy": pl.AUDIT_POLICY,
            "planning_bound": {"rate_per_hour": QUAL_RATE, "rule": pl.QUAL_PLANNING_RATE_RULE, "session_timeout_s": rn.deadline_s(total, QUAL_RATE)}}


class FakeAuthority(rn.Authority):
    name = "fake"

    def __init__(self, verify_refusal: str | None = None, pins_refusal: str | None = None):
        self.calls: list[str] = []
        self.verify_refusal, self.pins_refusal = verify_refusal, pins_refusal

    def verify(self, manifest, readjudicate=None):
        self.calls.append("verify")
        if self.verify_refusal:
            raise rn.Refusal(f"manifest: {self.verify_refusal}")
        return {"stage": "fixture", "readjudicate": readjudicate is not None}

    def verify_pins(self, manifest, root):
        self.calls.append("pins")
        if self.pins_refusal:
            raise rn.Refusal(f"instrument pins: {self.pins_refusal}")
        return {"verified": 0}


class FakeTransport:
    def __init__(self, log, close_error=None):
        self.log, self.close_error = log, close_error
        self.closed = False

    def close(self):
        self.log.append("close")
        self.closed = True
        if self.close_error:
            raise self.close_error


class SessionRefusal(Exception):
    pass


def write_evidence(out: Path, cfg: dict, log: dict, adjudicate, tamper=None, partial=False) -> dict:
    """What the instrument's session driver leaves behind (the modelled shape): the five files, the
    exports seal, then the adjudication callback — exactly the finalize order."""
    out = Path(out)
    (out / "console.log").write_bytes(b"fake console\n")
    (out / "console.ts.log").write_bytes(b"0.0 fake\n")
    (out / "timeline.json").write_text(json.dumps({"frames": [{"t": 0}] * 10, "crc_dropped": 1, "bad_frames": 0}))
    if tamper:
        tamper(log)
    (out / "run_log.json").write_text(json.dumps(log))
    (out / "audits.json").write_text(json.dumps({"chunks": []}))
    statuses = {k: "ok" for k in b1s.REQUIRED_EXPORTS}
    if partial:
        statuses["audits.json"] = "PARTIAL: ledgers INCOMPLETE"
    doc = b1s.write_exports_manifest(out, statuses)
    summary = {"outcome": None, "crc_dropped": 1, "bad_frames": 0, "disruptions": [], "transport_rereads": 0, "exports": statuses}
    if not doc["complete"]:
        summary["outcome"] = "HOLD host-side: evidence export incomplete: audits.json"
        return summary
    res = adjudicate(out)
    (out / "adjudication.json").write_text(json.dumps(res, default=str))
    summary["adjudication"] = {k: res.get(k) for k in ("outcome", "findings", "replay", "b1_result", "prediction_comparison")}   # b1_session.finalize's subset
    summary["outcome"] = res["outcome"]
    return summary


class Fixture:
    """A B3 manifest at S1 (B3Q) or S3 (B3) with its pinned documents, image, preregistration, B1
    manifest, rulings and boundary in a temp directory, plus the fake authority and ports."""

    def __init__(self, stage: str = "S3", first: int = 0, count: int = 2):
        self.d = Path(tempfile.mkdtemp(prefix="b3run_"))
        d = self.d
        self.stage, self.first, self.count = stage, first, count
        (d / "prereg.md").write_text("# fixture preregistration\n")
        (d / "b3_app.bin").write_bytes(b"fixture image bytes")
        (d / "b1.bit").write_bytes(b"fixture carrier bitstream")
        (d / "carrier_manifest.json").write_text("{}\n")
        self.b1_manifest = d / "b1_manifest.json"
        self.b1_manifest.write_text(json.dumps({"carrier": {"bitstream": rel(d / "b1.bit"), "carrier_manifest": {"path": rel(d / "carrier_manifest.json"),
                                                                                                                    "sha256": sha(d / "carrier_manifest.json")},
                                                            "nonce_seed": "00000000"}, "protocol": {"wire": "rel-v4"}}))
        self.plan_doc, self.pred_doc = b3_plan(), PRED
        self.qplan_doc, self.qpred_doc = b3q_plan(), QPRED
        for name, doc in (("plan.json", self.plan_doc), ("prediction.json", self.pred_doc), ("b3q_plan.json", self.qplan_doc), ("b3q_prediction.json", self.qpred_doc)):
            (d / name).write_text(rendered(doc))
        m = {"schema": "b3_manifest", "schema_version": "0.1.0", "board": {"boardid": BOARD},
             "prereg": {"path": rel(d / "prereg.md"), "sha256": sha(d / "prereg.md"), "frozen": True},
             "image": {"sha256": sha(d / "b3_app.bin"), "board_ready": True},
             "instrument": {"psoracle_commit": INSTRUMENT["psoracle_commit"]},
             "carrier": {"bitstream_sha256": sha(d / "b1.bit"), "variant": rn.B3_VARIANT},
             "map": {"canonical_json_sha256": MAP_SHA}, "universe": {"sha256": "u" * 64}, "experiment": {"fitness": "F1"},
             "seeds": {"master_seed": MASTER},
             "qualification_plan": {"path": rel(d / "b3q_plan.json"), "sha256": sha(d / "b3q_plan.json"),
                                    "prediction_path": rel(d / "b3q_prediction.json"), "prediction_sha256": sha(d / "b3q_prediction.json")},
             "qualified": False, "qualification": None, "plan": None}
        if stage == "S3":
            m["qualified"], m["qualification"] = True, {"outcome": "PASS"}
            m["plan"] = {"path": rel(d / "plan.json"), "sha256": sha(d / "plan.json"), "prediction_path": rel(d / "prediction.json"),
                         "prediction_sha256": sha(d / "prediction.json")}
        self.manifest = m
        self.manifest_path = d / "b3_manifest.json"
        self.manifest_path.write_text(rendered(m))
        self.manifest_sha = sha(self.manifest_path)
        self.authority = FakeAuthority()
        self.profile = rn.QUALIFICATION if stage == "S1" else rn.SEARCH
        self.plan, self.pred = (self.qplan_doc, self.qpred_doc) if stage == "S1" else (self.plan_doc, self.pred_doc)
        if stage == "S1":
            self.first, self.count = 0, 1
        self.records = bsess.records(self.count, self.plan["budget_per_arm"])
        self.frames = ls.expected_frames(self.records - 2, set(range(1, self.records + 1)), "rel-v4")
        self.resend = rn.resend_budget(self.frames["total"])
        self.master = self.plan["seed_derivation"]["master_seed"]
        self.boundary = d / "boundary.json"
        self.boundary.write_text(json.dumps(self.boundary_doc()))
        self.ruling = d / "ruling.json"
        self.pk = d / "pk.json"
        self.ruling.write_text(json.dumps(self.ruling_doc()))
        self.pk.write_text(json.dumps(self.pk_doc()))
        self.calls: list[str] = []
        self.ports = self.make_ports()
        self.patches = [mock.patch.object(rn, "B1_MANIFEST", self.b1_manifest)]
        for p_ in self.patches:
            p_.start()

    def close(self):
        for p_ in self.patches:
            p_.stop()
        shutil.rmtree(self.d, True)

    def boundary_doc(self) -> dict:
        return {"schema": "principal_boundary", "schema_version": "1.0.0", "runner_user": ME, "signer_user": "p3signer", "pod_group": "p3pod",
                "key_store": str(self.d / "keys"), "at": time.time(), "all_passed": True,
                "checks": [{"check": c, "passed": True, "detail": "ok"} for c in br.BOUNDARY_CHECKS]}

    def ruling_doc(self) -> dict:
        return {"ruling": self.profile["ruling_text"], "boardid": BOARD, "granted_by": "the owner", "date": "2026-09-18",
                "session": self.profile["session"], "prereg_sha256": self.manifest["prereg"]["sha256"], "image_sha256": self.manifest["image"]["sha256"],
                "b3_manifest_sha256": self.manifest_sha, "master_seed": self.master, "pair_first": self.first, "pair_count": self.count,
                "transport_disposition": "CH340 single-byte-deletion stop-loss in force; no session-scoped exception", "resend_budget": self.resend}

    def pk_doc(self) -> dict:
        return {"ruling": rn.PROVISION_RULING_TEXT, "boardid": BOARD, "granted_by": "the owner", "date": "2026-09-18",
                "session": self.profile["session"], "prereg_sha256": self.manifest["prereg"]["sha256"], "image_sha256": self.manifest["image"]["sha256"],
                "b3_manifest_sha256": self.manifest_sha}

    def args(self, **over) -> types.SimpleNamespace:
        a = dict(ruling=self.ruling, provision_ruling=self.pk, boundary=self.boundary, out=self.d / "evidence", pair_first=self.first,
                 pair_count=self.count, manifest=self.manifest_path, instrument_root=inst.DEFAULT_ROOT, image=self.d / "b3_app.bin",
                 key=self.d / "keys" / "K.bin", signer_user="p3signer", port="/dev/null-fake")
        if self.stage == "S1":
            a["pair_first"] = a["pair_count"] = None
        a.update(over)
        return types.SimpleNamespace(**a)

    # -- the fake device seam
    def make_ports(self, run=None, close_error=None, record_error=None, session_refusal=SessionRefusal) -> rn.Ports:
        calls = self.calls

        def claim(path):
            calls.append("claim")
            consumed = Path(path).with_name(Path(path).name + ".consumed")
            fd = os.open(consumed, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            os.close(fd)
            consumed.write_text("claimed\n")
            return consumed

        def record_outcome(consumed, why):
            calls.append("record_outcome")
            if record_error:
                raise record_error
            with open(consumed, "a") as f:
                f.write(why + "\n")

        def record_pk(pk_path, outcome):
            calls.append("record_pk")
            with open(str(pk_path) + ".consumed", "a") as f:
                f.write(f"provisioning session outcome: {outcome}\n")

        def open_transport(port):
            calls.append("port")
            return FakeTransport(calls, close_error)

        def write_artifacts(out, manifest_path, ruling_path, pk_path, manifest_sha, expected):
            calls.append("artifacts")
            return rn._prod_write_artifacts(out, manifest_path, ruling_path, pk_path, manifest_sha, expected)     # host-only: b1_qualification

        def run_session(session, out_dir, ruling, cfg, identity_check, adjudicate, tool):
            calls.append("session")
            return (run or self.correct_session)(session, out_dir, ruling, cfg, identity_check, adjudicate, tool)

        def instrument_layer(evidence, log, session_plan, root):
            calls.append("instrument_layer")
            return {"findings": [], "rejected": None, "rate": 2500.0, "audit_policy": session_plan["audit_policy"], "rate_report": {"evals_per_hour": 2500.0}}

        class FakeSigner:
            def __init__(self, key, user):
                self.key, self.user = key, user

            def sign_genome(self, req):
                raise AssertionError("the fake signer signs nothing")

            def provision(self, execute=True, ruling=None):
                raise AssertionError("the fake signer provisions nothing")

        return rn.Ports(which=lambda name: "/usr/bin/sb" if name == "sb" else None, make_signer=lambda key, user: FakeSigner(key, user),
                        bind_instrument=lambda root: dict(INSTRUMENT), verify_carrier_chain=lambda b1m, root: calls.append("carrier_chain"),
                        schedule=lambda: ls, write_artifacts=write_artifacts, claim_ruling=claim, record_outcome=record_outcome, record_pk=record_pk,
                        install_sigterm=lambda: calls.append("sigterm"), open_transport=open_transport, board_session=lambda t: ("board", t),
                        run_session=run_session, instrument_layer=instrument_layer, session_refusal=session_refusal, consts=CONSTS,
                        common_validation=False)          # the modelled evidence carries no wire envelope; production keeps it on

    # -- the modelled run log a correct board would have written for this invocation
    def run_log(self, cfg: dict, tamper=None) -> dict:
        ctx = cfg["context"]
        s = bsess.run_context(ctx, FAB, VIEW, TRUTH, MASKS)
        log = fx.run_log(ctx, s)
        for rec, c in zip(log["loop_records"], s.candidates):
            tables = FAB(c.genome)
            rec["evidence"] = {"score": {"functional_readout": [f"{t:016x}" for t in tables], "scores": badj.additive_scores(tables, CONSTS)}}
        ident = log["app_identity"]
        ident.update(rn.expected_identity(cfg["manifest"], cfg["plan"]))
        log["l6"] = {"binding": dict(cfg["plan"]["binding"]), "inputs": dict(cfg["plan"]["inputs"])}
        if tamper:
            tamper(log)
        return log

    def correct_session(self, session, out_dir, ruling, cfg, identity_check, adjudicate, tool):
        self.identity_findings = identity_check(self.run_log(cfg)["app_identity"])
        return write_evidence(out_dir, cfg, self.run_log(cfg), adjudicate)

    def preflight(self, **over) -> dict:
        return rn.preflight(self.args(**over), self.profile, authority=self.authority, ports=self.ports)


def refusal(fixture: Fixture, needle: str, **over) -> str:
    with unittest.TestCase().assertRaises(rn.Refusal) as cm:
        fixture.preflight(**over)
    msg = str(cm.exception)
    assert needle in msg, f"{needle!r} not in {msg!r}"
    return msg


class ZeroContact(unittest.TestCase):
    """Every preflight refusal: no evidence directory, no ruling claimed, no port, no session."""

    def setUp(self):
        self.f = Fixture("S3")

    def tearDown(self):
        self.f.close()

    def _refused(self, needle: str, **over):
        refusal(self.f, needle, **over)
        self.assertFalse((self.f.d / "evidence").exists())
        self.assertFalse(list(self.f.d.glob("*.consumed")))
        for contact in ("claim", "port", "session", "artifacts"):
            self.assertNotIn(contact, self.f.calls)

    def test_no_clobber_is_the_first_refusal(self):
        (self.f.d / "evidence").mkdir()
        refusal(self.f, "exists; evidence is never replaced (no-clobber)")
        self.assertEqual(list((self.f.d / "evidence").iterdir()), [], "nothing was written into the existing directory")
        self.assertFalse(list(self.f.d.glob("*.consumed")))
        self.assertEqual(self.f.authority.calls, [], "the authority was not even consulted")
        self.assertEqual(self.f.calls, [], "nothing at all was reached — not even the instrument bind")
        (self.f.d / "evidence").rmdir()
        (self.f.d / "evidence").symlink_to(self.f.d)
        refusal(self.f, "exists; evidence is never replaced (no-clobber)")

    def test_the_rulings(self):
        self._refused("--provision-ruling is mandatory", provision_ruling=None)
        self._refused("no readable ruling at", ruling=self.f.d / "missing.json")
        r = self.f.ruling_doc(); r["ruling"] = "whole-of-run B2 map utility"; self.f.ruling.write_text(json.dumps(r))
        self._refused("ruling text 'whole-of-run B2 map utility' != 'whole-of-run B3 closed loop'")
        self.f.ruling.write_text(json.dumps(self.f.ruling_doc()))
        (self.f.d / "ruling.json.consumed").write_text("2026-09-18 claimed pid=1\n")
        refusal(self.f, "was consumed")
        (self.f.d / "ruling.json.consumed").unlink()
        r = self.f.ruling_doc(); r["boardid"] = "08EB"; self.f.ruling.write_text(json.dumps(r))
        self._refused("names board '08EB', this stage is '17A6'")

    def test_the_boundary(self):
        b = self.f.boundary_doc(); b["at"] -= 7 * 3600; self.f.boundary.write_text(json.dumps(b))
        self._refused("principal boundary: principal_boundary record is older than 6 h")
        b = self.f.boundary_doc(); b["checks"][1]["passed"] = False; b["all_passed"] = False; self.f.boundary.write_text(json.dumps(b))
        self._refused("principal boundary NOT established")
        b = self.f.boundary_doc(); b["runner_user"] = "someone-else"; self.f.boundary.write_text(json.dumps(b))
        self._refused("is not this OS user")
        self.f.boundary.write_text(json.dumps(self.f.boundary_doc()))
        self._refused("--signer-user 'x' is not the record's", signer_user="x")
        self._refused("--key", key=self.f.d / "elsewhere" / "K.bin")

    def test_the_manifest_authority(self):
        self._refused("no B3 manifest at", manifest=self.f.d / "absent.json")
        m = dict(self.f.manifest, schema="b2_manifest"); self.f.manifest_path.write_text(rendered(m))
        self._refused("the manifest is not a b3_manifest document")
        m = copy.deepcopy(self.f.manifest); m.pop("board"); self.f.manifest_path.write_text(rendered(m))
        self._refused("the manifest pins no board")
        m = copy.deepcopy(self.f.manifest); m["prereg"]["frozen"] = False; self.f.manifest_path.write_text(rendered(m))
        self._refused("preregistration is not frozen")
        m = copy.deepcopy(self.f.manifest); m["image"]["board_ready"] = False; self.f.manifest_path.write_text(rendered(m))
        self._refused("not marked board_ready")
        self.f.manifest_path.write_text(rendered(self.f.manifest))
        (self.f.d / "b3_app.bin").write_bytes(b"other bytes")
        self._refused("the image is not the pinned one")
        (self.f.d / "b3_app.bin").write_bytes(b"fixture image bytes")
        self.f.authority = FakeAuthority(verify_refusal="S3: the pinned plan drifted")
        self._refused("manifest: S3: the pinned plan drifted")
        self.f.authority = FakeAuthority(pins_refusal="b3/host/b3_gate.py is not in the table")
        self._refused("instrument pins: b3/host/b3_gate.py is not in the table")

    def test_the_profile_and_stage(self):
        m = copy.deepcopy(self.f.manifest); m["qualified"] = False; m["qualification"] = None; self.f.manifest_path.write_text(rendered(m))
        self._refused("the manifest is not qualified: B3Q and S2 come before any B3 session")
        m = copy.deepcopy(self.f.manifest); m["plan"] = None; self.f.manifest_path.write_text(rendered(m))
        self._refused("the manifest pins no plan")
        m = copy.deepcopy(self.f.manifest); m["plan"]["sha256"] = "0" * 64; self.f.manifest_path.write_text(rendered(m))
        self._refused("the pinned plan plan.json does not hash to the manifest's pin".replace("plan.json", rel(self.f.d / "plan.json")))
        self.f.manifest_path.write_text(rendered(self.f.manifest))
        q = Fixture("S1")
        try:
            with self.assertRaises(rn.Refusal) as cm:
                rn.preflight(q.args(manifest=self.f.manifest_path), rn.QUALIFICATION, authority=q.authority, ports=q.ports)
            self.assertIn("already qualified: B3Q runs against the S1 manifest", str(cm.exception))
            with self.assertRaises(rn.Refusal) as cm:
                rn.preflight(self.f.args(manifest=q.manifest_path), rn.SEARCH, authority=self.f.authority, ports=self.f.ports)
            self.assertIn("not qualified", str(cm.exception))
        finally:
            q.close()

    def test_the_pinned_plan_and_prediction_go_through_the_adjudicators_guards(self):
        bad = dict(self.f.plan_doc, fitness="F2"); (self.f.d / "plan.json").write_text(rendered(bad))
        m = copy.deepcopy(self.f.manifest); m["plan"]["sha256"] = sha(self.f.d / "plan.json"); self.f.manifest_path.write_text(rendered(m))
        self._refused("the pinned plan/prediction: the plan's fitness 'F2' is not the preregistered 'F1'")
        (self.f.d / "plan.json").write_text(rendered(self.f.plan_doc)); m["plan"]["sha256"] = sha(self.f.d / "plan.json")
        bad = copy.deepcopy(self.f.pred_doc); bad["pairs"][0].pop("operator_seed"); (self.f.d / "prediction.json").write_text(rendered(bad))
        m["plan"]["prediction_sha256"] = sha(self.f.d / "prediction.json"); self.f.manifest_path.write_text(rendered(m))
        self._refused("the pinned plan/prediction: the prediction's pair 0 carries no 'operator_seed'")

    def test_the_instrument_commit_carrier_and_chain(self):
        m = copy.deepcopy(self.f.manifest); m["instrument"]["psoracle_commit"] = "f" * 40; self.f.manifest_path.write_text(rendered(m))
        self._refused("the instrument is not at the commit this manifest pins")
        m = copy.deepcopy(self.f.manifest); m["carrier"]["variant"] = "0x00000000"; self.f.manifest_path.write_text(rendered(m))
        self._refused("carrier variant is not the qualified carrier's contract word")
        m = copy.deepcopy(self.f.manifest); m["carrier"]["bitstream_sha256"] = "0" * 64; self.f.manifest_path.write_text(rendered(m))
        self._refused("the carrier bitstream does not hash to the manifest's pin")
        self.f.manifest_path.write_text(rendered(self.f.manifest))

        def chain_refuses(b1m, root):
            raise rn.Refusal("the B1 carrier this image runs on is not qualified: fixture")
        self.f.ports.verify_carrier_chain = chain_refuses
        self._refused("the B1 carrier this image runs on is not qualified")

    def test_the_slice(self):
        self._refused("a B3 session needs --pair-first and --pair-count", pair_first=None)
        self._refused("the slice (3, 1) does not lie inside the experiment's 3 pairs", pair_first=3, pair_count=1)
        self._refused("the slice (-1, 1) does not lie inside", pair_first=-1, pair_count=1)
        self._refused("the slice (0, 3) is not one the plan's split gives", pair_first=0, pair_count=3)
        self._refused("the slice (1, 1) is not one the plan's split gives", pair_first=1, pair_count=1)
        undetermined = copy.deepcopy(self.f.plan_doc); undetermined["session_split"] = pl.session_split(PAIRS, BUDGET, None)
        (self.f.d / "plan.json").write_text(rendered(undetermined))
        m = copy.deepcopy(self.f.manifest); m["plan"]["sha256"] = sha(self.f.d / "plan.json"); self.f.manifest_path.write_text(rendered(m))
        self._refused("is not one the plan's split gives (the split is UNDETERMINED")

    def test_the_master_seed_and_the_ruling_binding(self):
        m = copy.deepcopy(self.f.manifest); m["seeds"]["master_seed"] = 1; self.f.manifest_path.write_text(rendered(m))
        self._refused("the plan's master seed is not the manifest's")
        self.f.manifest_path.write_text(rendered(self.f.manifest))
        for k, v, needle in (("master_seed", 1, "bound to master_seed = 1"), ("pair_first", 1, "bound to pair_first = 1"), ("pair_count", 1, "bound to pair_count = 1"),
                             ("b3_manifest_sha256", "0" * 64, "bound to b3_manifest_sha256"), ("image_sha256", "0" * 64, "bound to image_sha256"),
                             ("session", "B3Q", "bound to session = 'B3Q'"), ("prereg_sha256", "0" * 64, "bound to prereg_sha256")):
            with self.subTest(field=k):
                r = self.f.ruling_doc(); r[k] = v; self.f.ruling.write_text(json.dumps(r))
                self._refused(needle)
        r = self.f.ruling_doc(); r.pop("pair_count"); self.f.ruling.write_text(json.dumps(r))
        self._refused("is not bound: it lacks 'pair_count'")
        self.f.ruling.write_text(json.dumps(self.f.ruling_doc()))
        pk = self.f.pk_doc(); pk["master_seed"] = self.f.master; self.f.pk.write_text(json.dumps(pk))
        self._refused("carries a master_seed: the provisioning ruling binds no experiment")
        pk = self.f.pk_doc(); pk["b3_manifest_sha256"] = "0" * 64; self.f.pk.write_text(json.dumps(pk))
        self._refused("ruling 'provisioning P3-K' is bound to b3_manifest_sha256")

    def test_the_transport_disposition_and_resend_budget(self):
        r = self.f.ruling_doc(); r.pop("transport_disposition"); self.f.ruling.write_text(json.dumps(r))
        self._refused("carries no transport_disposition")
        r = self.f.ruling_doc(); r["transport_disposition"] = " "; self.f.ruling.write_text(json.dumps(r))
        self._refused("carries no transport_disposition")
        r = self.f.ruling_doc(); r["resend_budget"] = self.f.resend + 1; self.f.ruling.write_text(json.dumps(r))
        self._refused(f"carries resend_budget {self.f.resend + 1}, this session's schedule gives ceil(4 × {self.f.frames['total']} / 1000) = {self.f.resend}")
        r = self.f.ruling_doc(); r["resend_budget"] = "13"; self.f.ruling.write_text(json.dumps(r))
        self._refused("carries no integer resend_budget")

    def test_sb_and_the_wire(self):
        self.f.ports.which = lambda name: None
        self._refused("`sb` is not installed")
        self.f.ports.which = lambda name: "/usr/bin/sb"
        b1m = json.loads(self.f.b1_manifest.read_text()); b1m["protocol"]["wire"] = "push-v1"; self.f.b1_manifest.write_text(json.dumps(b1m))
        self._refused("the pinned wire protocol 'push-v1' is not the 'rel-v4' this stage speaks")

    def test_the_production_authority_is_missing_and_refuses_by_name(self):
        """Injected import failure (never a permanent 'must not exist' assertion): while b3_manifest /
        b3_pins are absent, the production authority refuses before anything is read or written."""
        with mock.patch.dict(sys.modules, {"b3_manifest": None, "b3_pins": None}):
            with self.assertRaises(rn.Refusal) as cm:
                rn.production_authority()
            self.assertIn("no B3 manifest / pin authority", str(cm.exception))
            with self.assertRaises(rn.Refusal) as cm:
                rn.preflight(self.f.args(), rn.SEARCH, authority=None, ports=self.f.ports)
            self.assertIn("no B3 manifest / pin authority", str(cm.exception))
            with self.assertRaises(rn.Refusal) as cm:            # before the manifest is even read: an absent manifest is not what is named
                rn.preflight(self.f.args(manifest=self.f.d / "absent.json"), rn.SEARCH, authority=None, ports=self.f.ports)
            self.assertIn("no B3 manifest / pin authority", str(cm.exception))
        self.assertFalse((self.f.d / "evidence").exists())
        self.assertFalse(list(self.f.d.glob("*.consumed")))
        self.assertNotIn("port", self.f.calls)

    def test_the_cli_offers_no_skip(self):
        import argparse
        text = (R / "b3/host/b3_runner.py").read_text()
        self.assertNotIn("--skip", text)
        self.assertNotIn("--no-verify", text)
        self.assertNotIn("--authority", text)
        with mock.patch.dict(sys.modules, {"b3_manifest": None, "b3_pins": None}):
            with mock.patch("sys.stderr", new=__import__("io").StringIO()) as err:
                rc = rn.main(["--ruling", str(self.f.ruling), "--provision-ruling", str(self.f.pk), "--boundary", str(self.f.boundary),
                              "--out", str(self.f.d / "evidence"), "--pair-first", "0", "--pair-count", "2", "--manifest", str(self.f.manifest_path),
                              "--image", str(self.f.d / "b3_app.bin"), "--key", str(self.f.d / "keys" / "K.bin")])
        self.assertEqual(rc, 2)
        self.assertIn("REFUSED: no B3 manifest / pin authority", err.getvalue())
        self.assertFalse((self.f.d / "evidence").exists())
        self.assertFalse(list(self.f.d.glob("*.consumed")))
        self.assertIsInstance(argparse.ArgumentParser(), argparse.ArgumentParser)


class SessionDriverContract(unittest.TestCase):
    """The owner's P1 on ab71192: the cfg the preflight returns must carry everything the instrument's
    session driver reads — `heartbeat_s` and `signer` before its own protected block — or a real
    session would claim the ruling, open the port and crash."""

    def setUp(self):
        self.f = Fixture("S3", 0, 2)

    def tearDown(self):
        self.f.close()

    def test_every_key_the_driver_reads_is_in_the_cfg_and_in_the_contract(self):
        import re
        src = (R / "host/b1_session.py").read_text()
        keys = sorted(set(re.findall(r'cfg\["([a-z_0-9]+)"\]', src)))
        self.assertEqual(keys, sorted(rn.SESSION_CFG_KEYS), "the contract list must be the driver's actual reads")
        cfg = self.f.preflight()
        for k in keys:
            self.assertIsNotNone(cfg.get(k), k)
        self.assertTrue(callable(cfg["signer"].sign_genome) and callable(cfg["signer"].provision))
        self.assertEqual((cfg["signer"].key, cfg["signer"].user), (self.f.d / "keys" / "K.bin", "p3signer"))
        l6m = json.loads((inst.DEFAULT_ROOT / "manifests/l6_manifest.json").read_text())
        self.assertEqual(cfg["heartbeat_s"], l6m["protocol"]["heartbeat_s"])
        self.assertEqual(cfg["l6_manifest"]["pinned_at_build"]["watchdog_load_value"], rn.WATCHDOG_LOAD)
        self.assertEqual(cfg["carrier"]["bitstream_sha256"], self.f.manifest["carrier"]["bitstream_sha256"])
        with self.assertRaises(rn.Refusal) as cm:
            rn.check_session_cfg(dict(cfg, heartbeat_s=None))
        self.assertIn("lacks ['heartbeat_s']", str(cm.exception))
        with self.assertRaises(rn.Refusal):
            rn.check_session_cfg(dict(cfg, signer=object()))
        # and the PREFLIGHT itself holds its cfg to the contract: a signer without the driver's methods is a refusal, zero-contact
        self.f.ports.make_signer = lambda key, user: object()
        refusal(self.f, "the signer has no callable 'sign_genome': the session driver would crash after the ruling was claimed")
        self.assertNotIn("port", self.f.calls)
        self.assertFalse((self.f.d / "evidence").exists())

    def test_the_real_session_driver_refuses_through_a_board_that_answers_nothing(self):
        """The PRODUCTION driver (b1_session.run, the instrument's own code) over the preflight's cfg
        and a board session whose every method refuses: it must reach its own refusal path and
        persist a summary — never a KeyError on the cfg. Host-only: nothing is opened."""
        import board_session as bsn
        cfg = self.f.preflight()

        class Nothing:
            def __getattr__(self, name):
                raise bsn.SessionRefusal(f"fixture: no board ({name})")
        out = self.f.d / "evidence"
        out.mkdir()
        summary = rn._prod_run_session(Nothing(), out, cfg["ruling"], cfg, rn.identity_check_for(cfg), rn.adjudication_for(cfg), "test")
        self.assertTrue(summary["outcome"].startswith("REFUSED: fixture: no board"), summary["outcome"])
        self.assertTrue((out / "summary.json").is_file())
        self.assertNotIn("host_error", summary)
        shutil.rmtree(out)
        self.f.ports.run_session = rn._prod_run_session
        self.f.ports.board_session = lambda transport: Nothing()
        self.f.ports.session_refusal = bsn.SessionRefusal
        rc, outcome = rn.execute(self.f.args(), self.f.preflight())
        self.assertEqual(rc, 1)
        self.assertTrue(outcome.startswith("REFUSED: fixture: no board"), outcome)
        rec = json.loads((out / "runner_session.json").read_text())
        self.assertEqual(rec["cause"], "LOST")
        self.assertIn(outcome, (self.f.d / "ruling.json.consumed").read_text())


class Preflight(unittest.TestCase):
    def test_a_b3_slice_binds_the_actual_slice_seeds_and_transport(self):
        f = Fixture("S3", 0, 2)
        try:
            cfg = f.preflight()
            plan = cfg["plan"]
            self.assertEqual((plan["session"], plan["pair_first"], plan["pair_count"], plan["pairs_total"], plan["n"]), ("B3", 0, 2, PAIRS, BUDGET))
            self.assertEqual(cfg["seeds"], SEEDS)
            self.assertEqual(plan["expected_records"], 2 + 2 * (3 * BUDGET + 3))
            self.assertEqual(plan["ledger_entries"], 2 * BUDGET)
            self.assertEqual(plan["expected_frames"], f.frames)
            self.assertEqual(plan["crc_budget"], ls.crc_budget(f.frames["total"]))
            self.assertEqual(plan["resend_budget"], math.ceil(4 * f.frames["total"] / 1000))
            self.assertEqual(plan["bad_frame_budget"], plan["crc_budget"])
            self.assertEqual(plan["binding"]["pair_first"], 0)
            self.assertEqual(plan["binding"]["resend_budget"], f.resend)
            self.assertEqual(plan["binding"]["boardid"], BOARD)
            self.assertEqual(plan["binding"]["b3_manifest_sha256"], f.manifest_sha)
            entry = rn.slice_in_split(f.plan_doc, 0, 2)
            self.assertAlmostEqual(plan["session_timeout_s"], entry["deadline_s"])
            self.assertAlmostEqual(plan["session_timeout_s"], rn.deadline_s(plan["expected_records"], 0.85 * RATE_MEASURED))
            self.assertEqual(plan["inputs"]["stage"], "S3")
            self.assertEqual(cfg["authority"], "fake")
            self.assertEqual(f.authority.calls, ["verify", "pins"])
            self.assertEqual(cfg["transport"]["resend_budget"], f.resend)
            self.assertNotIn("port", f.calls)
        finally:
            f.close()

    def test_the_later_slice_of_the_split(self):
        f = Fixture("S3", 2, 1)
        try:
            cfg = f.preflight()
            self.assertEqual((cfg["plan"]["pair_first"], cfg["plan"]["pair_count"]), (2, 1))
            self.assertEqual(cfg["plan"]["expected_records"], 2 + 3 * BUDGET + 3)
            self.assertEqual(cfg["context"].seeds, SEEDS)
            flags = cfg["plan"]["flags"]
            import b2_session as b2sess
            self.assertEqual(b2sess.page_slice(flags), (PAIRS, 2, 1))
        finally:
            f.close()

    def test_b3q_is_pair_0_count_1_budget_40(self):
        f = Fixture("S1")
        try:
            cfg = f.preflight()
            plan = cfg["plan"]
            self.assertEqual((plan["session"], plan["pair_first"], plan["pair_count"], plan["pairs_total"], plan["n"]), ("B3Q", 0, 1, 1, 40))
            self.assertEqual(plan["expected_records"], 125)
            self.assertEqual(plan["ledger_entries"], 40)
            self.assertEqual(plan["records_per_pair"], 123)
            self.assertAlmostEqual(plan["session_timeout_s"], rn.deadline_s(125, QUAL_RATE))
            self.assertEqual(plan["deadline_rate"]["source"], "the pinned B3Q planning bound (never a calibration)")
            self.assertEqual(cfg["seeds"], [QUAL_SEED])
            self.assertEqual(plan["master_seed"], 424242)
            self.assertEqual(plan["inputs"]["stage"], "S1")
            refusal(f, "B3Q runs 1 pair at budget 40: it takes no slice", pair_first=0, pair_count=2)
            q = copy.deepcopy(f.qplan_doc); q["budget_per_arm"] = 41; q["records"]["total"] = 128
            (f.d / "b3q_plan.json").write_text(rendered(q))
            m = copy.deepcopy(f.manifest); m["qualification_plan"]["sha256"] = sha(f.d / "b3q_plan.json"); f.manifest_path.write_text(rendered(m))
            refusal(f, "a B3Q plan runs at budget 40, not 41")
        finally:
            f.close()

    def test_the_watchdog_build_contract_and_heartbeat_come_from_the_pinned_l6_manifest(self):
        f = Fixture("S3", 0, 2)
        try:
            root = f.d / "inst"
            (root / "manifests").mkdir(parents=True)
            l6m = json.loads((inst.DEFAULT_ROOT / "manifests/l6_manifest.json").read_text())
            for mutate, needle in ((lambda m: m["pinned_at_build"].__setitem__("watchdog_load_value", 1), "D-s1: the watchdog pins are not the instrument's"),
                                   (lambda m: m["pinned_at_build"].__setitem__("watchdog_enabled", False), "D-s1"),
                                   (lambda m: m["pinned_at_build"].__setitem__("watchdog_prescaler", 8), "D-s1"),
                                   (lambda m: m["protocol"].pop("heartbeat_s"), "pins no positive heartbeat_s"),
                                   (lambda m: m["protocol"].__setitem__("heartbeat_s", 0), "pins no positive heartbeat_s")):
                with self.subTest(needle=needle):
                    m = copy.deepcopy(l6m)
                    mutate(m)
                    (root / "manifests/l6_manifest.json").write_text(json.dumps(m))
                    refusal(f, needle, instrument_root=root)
                    self.assertNotIn("port", f.calls)
            refusal(f, "no readable instrument l6 manifest", instrument_root=f.d / "nowhere")
        finally:
            f.close()

    def test_the_deadline_and_records_must_be_the_frozen_arithmetic(self):
        f = Fixture("S3", 0, 2)
        try:
            bad = copy.deepcopy(f.plan_doc); bad["session_split"]["sessions"][0]["deadline_s"] += 1.0
            (f.d / "plan.json").write_text(rendered(bad))
            m = copy.deepcopy(f.manifest); m["plan"]["sha256"] = sha(f.d / "plan.json"); f.manifest_path.write_text(rendered(m))
            refusal(f, "is not the frozen formula's")
            bad = copy.deepcopy(f.plan_doc); bad["session_split"]["sessions"][0]["records"] += 1
            (f.d / "plan.json").write_text(rendered(bad))
            m["plan"]["sha256"] = sha(f.d / "plan.json"); f.manifest_path.write_text(rendered(m))
            refusal(f, "the record arithmetic says")
        finally:
            f.close()
        q = Fixture("S1")
        try:
            bad = copy.deepcopy(q.qplan_doc); bad["planning_bound"]["session_timeout_s"] += 1
            (q.d / "b3q_plan.json").write_text(rendered(bad))
            m = copy.deepcopy(q.manifest); m["qualification_plan"]["sha256"] = sha(q.d / "b3q_plan.json"); q.manifest_path.write_text(rendered(m))
            refusal(q, "session_timeout_s")
        finally:
            q.close()

    def test_the_identity_contract_is_1_6_0(self):
        f = Fixture("S3", 0, 2)
        try:
            cfg = f.preflight()
            want = rn.expected_identity(cfg["manifest"], cfg["plan"])
            self.assertEqual((want["schema_version"], want["carto_version"], want["arms"], want["b1_map_cost"]), ("1.6.0", carto_mod.CARTO_VERSION, "RFO", 333))
            check = rn.identity_check_for(cfg)
            self.assertEqual(check(dict(want)), [])
            self.assertTrue(any("IDENT pair_count" in x for x in check(dict(want, pair_count=1))))
            self.assertTrue(any("probe_budget" in x for x in check(dict(want, probe_budget=333))))
            self.assertTrue(any("IDENT carto_version" in x for x in check(dict(want, carto_version="specimen-carto-v1.0"))))
        finally:
            f.close()

    def test_the_frozen_formulas(self):
        self.assertEqual(rn.resend_budget(3216), 13)
        self.assertEqual(rn.resend_budget(1), 1)
        with self.assertRaises(rn.Refusal):
            rn.resend_budget(0)
        self.assertAlmostEqual(rn.deadline_s(125, 2500.0), 1.25 * 125 * 3600 / 2500.0 + 600)
        self.assertEqual(rn.classify("PASS"), "PASS")
        self.assertEqual(rn.classify("KILL: x"), "KILL")
        self.assertEqual(rn.classify("HOLD: x"), "HOLD")
        for s in ("STOP DEADLINE: x", "CRASHED host-side", "REFUSED: detach", ""):
            self.assertEqual(rn.classify(s), "LOST")


class Execution(unittest.TestCase):
    """The claim order, the session verdict, and every error path finalising with the primary
    cause kept — through the fake device seam."""

    def setUp(self):
        self.f = Fixture("S3", 0, 2)

    def tearDown(self):
        self.f.close()

    def _run(self, **ports_over) -> tuple[int, str, dict]:
        f = self.f
        if ports_over:
            f.ports = f.make_ports(**ports_over)
        cfg = f.preflight()
        rc, outcome = rn.execute(f.args(), cfg)
        rec = json.loads((f.d / "evidence" / "runner_session.json").read_text()) if (f.d / "evidence" / "runner_session.json").is_file() else None
        return rc, outcome, rec

    def test_a_correct_session_passes_in_the_fixed_order_at_session_scope(self):
        rc, outcome, rec = self._run()
        self.assertEqual((rc, outcome), (0, "PASS"))
        f = self.f
        contact = [c for c in f.calls if c in ("artifacts", "claim", "sigterm", "port", "session", "close", "record_outcome", "record_pk")]
        self.assertEqual(contact, ["artifacts", "claim", "sigterm", "port", "session", "close", "record_outcome", "record_pk"])
        ev = f.d / "evidence"
        for name in ("manifest_at_run.json", "ruling_whole_of_run.json", "ruling_provisioning.json", "run_log.json", "exports.json", "adjudication.json", "runner_session.json"):
            self.assertTrue((ev / name).is_file(), name)
        adjudication = json.loads((ev / "adjudication.json").read_text())
        self.assertEqual((adjudication["outcome"], adjudication["scope"], adjudication["session"]), ("PASS", "session", "B3"))
        for k in ("primary", "secondary_outcome", "deltas1", "deltas2", "fitness_sequence_sha256"):
            self.assertNotIn(k, adjudication["replay"])
            self.assertNotIn(k, adjudication)
        self.assertEqual(adjudication["replay"]["replay"]["pairs"], [0, 1])
        self.assertEqual(adjudication["measured_rate_per_hour"], 2500.0)
        self.assertTrue(adjudication["binding_checked"])
        self.assertEqual(f.identity_findings, [])
        self.assertEqual((rec["cause"], rec["outcome"], rec["reached"], rec["pair_first"], rec["pair_count"]), ("PASS", "PASS", "session", 0, 2))
        self.assertEqual(rec["transport"]["resend_budget"], f.resend)
        self.assertEqual(rec["transport"]["crc_dropped"], 1)
        self.assertEqual(rec["transport"]["frames_seen"], 10)
        self.assertEqual(rec["finalise_errors"], [])
        self.assertIn("no retry", rec["ruling_pair"])
        self.assertIn("PASS", (f.d / "ruling.json.consumed").read_text())
        self.assertIn("provisioning session outcome: PASS", (f.d / "pk.json.consumed").read_text())
        self.assertEqual(f.calls.count("session"), 1)

    def test_no_clobber_after_preflight_writes_nothing_into_a_directory_it_did_not_create(self):
        """The owner's P2 on ab71192: a directory (or a symlink to one) that appears between the
        preflight and the session is someone else's — REFUSED, and not a byte written into it."""
        f = self.f
        cfg = f.preflight()
        (f.d / "evidence").mkdir()
        (f.d / "evidence" / "owner.txt").write_text("not ours\n")
        rc, outcome = rn.execute(f.args(), cfg)
        self.assertEqual(rc, 2)
        self.assertTrue(outcome.startswith("REFUSED:") and "no-clobber" in outcome, outcome)
        self.assertEqual([p.name for p in (f.d / "evidence").iterdir()], ["owner.txt"])
        for contact in ("artifacts", "claim", "port"):
            self.assertNotIn(contact, f.calls)
        self.assertFalse((f.d / "ruling.json.consumed").exists())
        shutil.rmtree(f.d / "evidence")
        target = f.d / "someone_elses"
        target.mkdir()
        (target / "owner.txt").write_text("not ours\n")
        (f.d / "evidence").symlink_to(target)
        rc, outcome = rn.execute(f.args(), cfg)
        self.assertEqual(rc, 2)
        self.assertIn("no-clobber", outcome)
        self.assertEqual([p.name for p in target.iterdir()], ["owner.txt"])
        self.assertNotIn("artifacts", f.calls)

    def test_a_ruling_that_changed_between_preflight_and_archive_is_refused_before_the_claim(self):
        f = self.f
        cfg = f.preflight()
        r = f.ruling_doc(); r["granted_by"] = "someone else"; f.ruling.write_text(json.dumps(r))
        rc, outcome = rn.execute(f.args(), cfg)
        self.assertEqual(rc, 2)
        self.assertIn("not the ruling the preflight parsed", outcome)
        self.assertNotIn("claim", f.calls)
        self.assertFalse((f.d / "ruling.json.consumed").exists())
        self.assertFalse((f.d / "evidence" / "ruling_whole_of_run.json").exists(), "a failed archive leaves no partial artifact")

    def test_an_already_claimed_ruling_is_refused_with_no_port(self):
        f = self.f
        cfg = f.preflight()
        (f.d / "ruling.json.consumed").write_text("claimed by another runner\n")
        rc, outcome = rn.execute(f.args(), cfg)
        self.assertEqual(rc, 2)
        self.assertIn("could not be claimed", outcome)
        self.assertNotIn("port", f.calls)

    def test_a_kill_is_recorded_once_and_never_retried(self):
        def kill(session, out_dir, ruling, cfg, identity_check, adjudicate, tool):
            def tamper(log):
                rec = next(r for r in log["loop_records"] if isinstance(r.get("search"), dict) and r["search"]["holdout"] is None)
                rec["search"]["fitness"] = (rec["search"]["fitness"] + 1) % 41
            return write_evidence(out_dir, cfg, self.f.run_log(cfg, tamper=tamper), adjudicate)
        rc, outcome, rec = self._run(run=kill)
        self.assertEqual(rc, 1)
        self.assertTrue(outcome.startswith("KILL"), outcome)
        self.assertEqual(rec["cause"], "KILL")
        self.assertEqual(self.f.calls.count("session"), 1)
        self.assertIn("KILL", (self.f.d / "ruling.json.consumed").read_text())

    def test_a_hold_from_the_binding_or_the_export_seal(self):
        def wrong_binding(session, out_dir, ruling, cfg, identity_check, adjudicate, tool):
            def tamper(log):
                log["l6"]["binding"]["pair_count"] = 1
            return write_evidence(out_dir, cfg, self.f.run_log(cfg, tamper=tamper), adjudicate)
        rc, outcome, rec = self._run(run=wrong_binding)
        self.assertTrue(outcome.startswith("HOLD"), outcome)
        self.assertIn("binding: the log's pair_count is 1", outcome)
        self.assertEqual(rec["cause"], "HOLD")
        self.f.close(); self.f = Fixture("S3", 0, 2)

        def partial(session, out_dir, ruling, cfg, identity_check, adjudicate, tool):
            return write_evidence(out_dir, cfg, self.f.run_log(cfg), adjudicate, partial=True)
        rc, outcome, rec = self._run(run=partial)
        self.assertTrue(outcome.startswith("HOLD host-side: evidence export incomplete"), outcome)
        self.assertEqual(rec["cause"], "HOLD")
        self.assertFalse((self.f.d / "evidence" / "adjudication.json").exists(), "no verdict over a subset of the evidence")

    def test_a_detach_keeps_the_partial_evidence_and_the_primary_cause(self):
        def detach(session, out_dir, ruling, cfg, identity_check, adjudicate, tool):
            (Path(out_dir) / "console.log").write_bytes(b"partial console before the CH340 dropped\n")
            raise SessionRefusal("the port disappeared: /dev/ebaz-uart detached (CH340 dropout)")
        rc, outcome, rec = self._run(run=detach)
        self.assertEqual(rc, 1)
        self.assertEqual(outcome, "REFUSED: the port disappeared: /dev/ebaz-uart detached (CH340 dropout)")
        self.assertEqual(rec["cause"], "LOST")
        self.assertTrue((self.f.d / "evidence" / "console.log").is_file())
        self.assertIn("close", self.f.calls)
        self.assertIn(outcome, (self.f.d / "ruling.json.consumed").read_text())
        self.assertEqual(self.f.calls.count("session"), 1)

    def test_a_timeout_stop_is_lost_not_retried(self):
        def timeout(session, out_dir, ruling, cfg, identity_check, adjudicate, tool):
            return {"outcome": "STOP DEADLINE: the runner's own 5000.0 s bound elapsed", "crc_dropped": 3, "bad_frames": 1}
        rc, outcome, rec = self._run(run=timeout)
        self.assertEqual(rc, 1)
        self.assertEqual(rec["cause"], "LOST")
        self.assertEqual((rec["transport"]["crc_dropped"], rec["transport"]["bad_frames"]), (3, 1))
        self.assertEqual(self.f.calls.count("session"), 1)

    def test_a_host_crash_is_finalised_with_its_traceback(self):
        def crash(*a, **k):
            raise RuntimeError("the reader thread died")
        rc, outcome, rec = self._run(run=crash)
        self.assertEqual(outcome, "CRASHED host-side: RuntimeError: the reader thread died")
        self.assertEqual(rec["cause"], "LOST")
        self.assertTrue(any("traceback" in e for e in rec["finalise_errors"]))
        self.assertIn(outcome, (self.f.d / "ruling.json.consumed").read_text())

    def test_a_close_error_never_replaces_the_outcome(self):
        rc, outcome, rec = self._run(close_error=OSError("close: device gone"))
        self.assertEqual((rc, outcome), (0, "PASS"))
        self.assertEqual(rec["finalise_errors"], ["transport close: OSError: close: device gone"])
        self.assertIn("PASS", (self.f.d / "ruling.json.consumed").read_text())

    def test_a_record_error_never_replaces_the_outcome(self):
        rc, outcome, rec = self._run(record_error=OSError("disk full"))
        self.assertEqual((rc, outcome), (0, "PASS"))
        self.assertEqual(rec["finalise_errors"], ["record_outcome: OSError: disk full"])
        self.assertEqual(rec["outcome"], "PASS")

    def test_b3q_reports_the_measured_rate_and_transitions_nothing(self):
        self.f.close()
        self.f = Fixture("S1")
        before = self.f.manifest_path.read_bytes()
        rc, outcome, rec = self._run()
        self.assertEqual((rc, outcome), (0, "PASS"))
        adjudication = json.loads((self.f.d / "evidence" / "adjudication.json").read_text())
        self.assertEqual(adjudication["session"], "B3Q")
        self.assertEqual(adjudication["measured_rate_per_hour"], 2500.0)
        self.assertEqual(adjudication["audit_policy"], "all-self-reporting")
        self.assertEqual(adjudication["replay"]["replay"]["records_replayed"], 123)
        self.assertNotIn("primary", adjudication)
        self.assertEqual(rec["measured_rate_per_hour"], 2500.0)
        self.assertEqual(rec["expected_records"], 125)
        self.assertEqual(self.f.manifest_path.read_bytes(), before, "the runner never transitions the manifest")
        self.assertNotIn("qualify", self.f.authority.calls)

    def test_the_b3q_rate_is_read_from_the_adjudication_on_disk(self):
        """The owner's P2 on ab71192: the production finalizer keeps only a subset of the verdict in
        the summary; the rate comes from adjudication.json."""
        self.f.close()
        self.f = Fixture("S1")
        rc, outcome, rec = self._run()
        self.assertEqual(outcome, "PASS")
        self.assertEqual(rec["measured_rate_per_hour"], 2500.0)
        self.assertIsNone(rn.measured_rate_from(self.f.d, {"adjudication": {"outcome": "PASS"}}), "no file, no rate — never invented")
        self.assertEqual(rn.measured_rate_from(self.f.d / "evidence", {"adjudication": {"outcome": "PASS", "measured_rate_per_hour": 7.0}}), 7.0)

    def test_an_implementation_error_is_never_a_refusal(self):
        """The owner's P3 on ab71192: a defect inside the authority propagates (an INTERNAL ERROR on
        the CLI, exit 3), and only the authority's own refusal classes become REFUSED."""
        class Buggy(FakeAuthority):
            def verify(self, manifest, readjudicate=None):
                raise AttributeError("'NoneType' object has no attribute 'stage'")
        self.f.authority = Buggy()
        with self.assertRaises(AttributeError):
            self.f.preflight()
        with mock.patch.object(rn, "production_authority", lambda: Buggy()), mock.patch.object(rn.Ports, "production", lambda self: self.f_ports):
            rn.Ports.f_ports = self.f.ports
            with mock.patch("sys.stderr", new=__import__("io").StringIO()) as err:
                rc = rn.main(["--ruling", str(self.f.ruling), "--provision-ruling", str(self.f.pk), "--boundary", str(self.f.boundary),
                              "--out", str(self.f.d / "evidence"), "--pair-first", "0", "--pair-count", "2", "--manifest", str(self.f.manifest_path),
                              "--image", str(self.f.d / "b3_app.bin"), "--key", str(self.f.d / "keys" / "K.bin")])
        self.assertEqual(rc, 3)
        self.assertIn("INTERNAL ERROR: AttributeError", err.getvalue())
        self.assertIn("Traceback", err.getvalue())
        self.assertFalse((self.f.d / "evidence").exists())
        # the production adapter converts ONLY the module's declared refusal classes
        class ManifestRefusal(Exception):
            pass
        fake_m = types.SimpleNamespace(Refusal=ManifestRefusal, check_board=lambda m: "17A6", manifest_sha256=lambda m: "0" * 64,
                                       verify=lambda m, readjudicate=None: (_ for _ in ()).throw(ManifestRefusal("S3: drifted")))
        fake_p = types.SimpleNamespace(PinRefusal=ManifestRefusal, verify=lambda manifest=None: (_ for _ in ()).throw(TypeError("bad call")))
        with mock.patch.dict(sys.modules, {"b3_manifest": fake_m, "b3_pins": fake_p}):
            auth = rn.production_authority()
            with self.assertRaises(rn.Refusal) as cm:
                auth.verify({}, None)
            self.assertEqual(str(cm.exception), "manifest: S3: drifted")
            with self.assertRaises(TypeError):
                auth.verify_pins({}, R)

    def test_the_session_verdict_refuses_without_the_plan_and_prediction(self):
        cfg = self.f.preflight()
        cfg = dict(cfg, prediction=None)
        res = rn.adjudication_for(cfg)(self.f.d)
        self.assertTrue(res["outcome"].startswith("REFUSED: no session verdict without ['prediction']"))


class Verdict(unittest.TestCase):
    """judge_session over evidence on disk: what it holds the evidence to."""

    def setUp(self):
        self.f = Fixture("S3", 0, 2)
        self.cfg = self.f.preflight()
        self.ev = self.f.d / "evidence"
        self.ev.mkdir()
        import b1_qualification as bq
        bq.write_session_artifacts(self.ev, self.f.manifest_path, self.f.ruling, self.f.pk, self.f.manifest_sha, expected_rulings=(self.cfg["ruling"], self.cfg["provision_ruling_parsed"]))

    def tearDown(self):
        self.f.close()

    def _judge(self, tamper=None, **kw):
        write_evidence(self.ev, self.cfg, self.f.run_log(self.cfg, tamper=tamper), lambda d: {"outcome": "unused"}, **kw)
        return rn.judge_session(self.ev, self.cfg["manifest"], self.cfg["plan"], self.cfg["round_plan"], self.cfg["prediction"], inst.DEFAULT_ROOT, self.f.ports)

    def test_the_positive_control_passes_at_session_scope(self):
        res = self._judge()
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual(res["scope"], "session")
        self.assertNotIn("primary", res)
        self.assertIn("pooled_primary", res)

    def test_the_archived_manifest_must_be_this_invocations(self):
        (self.ev / "manifest_at_run.json").write_text(rendered(dict(self.f.manifest, universe={"sha256": "v" * 64})))
        res = self._judge()
        self.assertTrue(res["outcome"].startswith("HOLD: the archived manifest_at_run.json hashes to"), res["outcome"])
        self.assertEqual(res["replay"], {}, "the evidence does not belong to this invocation: nothing replayed")

    def test_the_archived_rulings_are_rebound_with_the_preflights_own_guards(self):
        """The owner's P2 on ab71192: the offline rebinding uses the same semantics as the preflight —
        the slice, the resend budget, the transport disposition EQUAL to the invocation's, and the
        provisioning ruling binding no master seed and no slice."""
        import b1_qualification as bq

        def archive(name, doc):
            (self.ev / name).write_text(json.dumps(bq.archive_envelope(json.dumps(doc).encode()), indent=1) + "\n")
        r = self.f.ruling_doc(); r["pair_count"] = 1; r["resend_budget"] = 1
        archive("ruling_whole_of_run.json", r)
        res = self._judge()
        self.assertTrue(any("bound to pair_count = 1" in x for x in res["findings"]), res["findings"][:4])
        r = self.f.ruling_doc(); r["resend_budget"] = 1
        archive("ruling_whole_of_run.json", r)
        res = self._judge()
        self.assertTrue(any("carries resend_budget 1, this session's schedule gives" in x for x in res["findings"]), res["findings"][:4])
        r = self.f.ruling_doc(); r["transport_disposition"] = "stop-loss lifted for this session"
        archive("ruling_whole_of_run.json", r)
        res = self._judge()
        self.assertTrue(any("carries the transport disposition 'stop-loss lifted for this session', this session's is" in x for x in res["findings"]), res["findings"][:4])
        archive("ruling_whole_of_run.json", self.f.ruling_doc())
        pk = self.f.pk_doc(); pk["master_seed"] = self.f.master; pk["pair_first"] = 0; pk["pair_count"] = 2
        archive("ruling_provisioning.json", pk)
        res = self._judge()
        self.assertTrue(any("carries a master_seed: the provisioning ruling binds no experiment" in x for x in res["findings"]), res["findings"][:4])
        self.assertTrue(any("carries 'pair_first': it binds no slice" in x for x in res["findings"]), res["findings"][:4])
        archive("ruling_provisioning.json", self.f.pk_doc())
        self.assertEqual(self._judge()["outcome"], "PASS")

    def test_the_identity_and_inputs_are_held(self):
        res = self._judge(tamper=lambda log: log["app_identity"].__setitem__("arms", "RF"))
        self.assertTrue(any("IDENT arms" in x for x in res["findings"]), res["findings"][:4])
        res = self._judge(tamper=lambda log: log["l6"]["inputs"].__setitem__("stage", "S1"))
        self.assertTrue(any("inputs: the log's stage is 'S1'" in x for x in res["findings"]), res["findings"][:4])

    def test_an_instrument_rejection_is_the_outcome(self):
        self.f.ports.instrument_layer = lambda ev, log, plan, root: {"findings": [], "rejected": "KILL: a served readout contradicts the audit chain", "rate": None, "audit_policy": None}
        res = self._judge()
        self.assertEqual(res["outcome"], "KILL: a served readout contradicts the audit chain")
        self.assertEqual(res["replay"], {}, "the record replay is not consulted after the instrument's own rejection")

    def test_no_rate_or_policy_is_a_hold(self):
        self.f.ports.instrument_layer = lambda ev, log, plan, root: {"findings": [], "rejected": None, "rate": None, "audit_policy": None}
        res = self._judge()
        self.assertEqual(res["outcome"], "HOLD: the session produced no measured rate or no verified audit policy")

    def test_no_run_log(self):
        res = rn.judge_session(self.ev, self.cfg["manifest"], self.cfg["plan"], self.cfg["round_plan"], self.cfg["prediction"], inst.DEFAULT_ROOT, self.f.ports)
        self.assertEqual(res["outcome"], "REFUSED: the evidence carries no run_log.json")


if __name__ == "__main__":
    unittest.main()
