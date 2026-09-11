"""host/b2_runner.py — the B2 board runner's fail-closed preflight.

The runner cannot run today and these tests pin that it refuses, in the documented order and
for the documented reason: there is no committed B2 manifest, the preregistration is not
frozen, the image is not board_ready, `host/b2_pins.py` does not exist. With a FIXTURE manifest
carried stage by stage — S0 from the real image's build evidence, S1 frozen to a fixture
document, S2 qualified from a fixture B2Q evidence dir, S3 with a generated plan pinned — the
later checks are reached one at a time.

No test opens a port, consumes a ruling, writes an evidence directory or contacts a board:
every one calls `preflight` and asserts a refusal, or asserts a pure function's answer.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
sys.path.insert(0, str(R / "tests"))
import b2_manifest as bman  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_runner as rn  # noqa: E402
import b2_search as bs  # noqa: E402
import b2_session as bsess  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

IMAGE_EVIDENCE = R / "evidence/b2/build_evidence.json"
IMAGE = R / "firmware/b2/bsp/out/b2_app.bin"
GATE = R / "evidence/b2/gate/recomputed_2026_09_10/gate_report.json"
HAVE = IMAGE_EVIDENCE.is_file() and IMAGE.is_file() and GATE.is_file()
STUB_RATE = 2807.0


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Fixture:
    """A B2 manifest carried from S0 to the requested stage, in a temp directory."""

    def __init__(self, stage: str = "S3"):
        self.d = Path(tempfile.mkdtemp(prefix="b2run_"))
        self.manifest = self._roundtrip(bman.init(IMAGE_EVIDENCE))
        self.prereg = self.d / "prereg.md"
        self.prereg.write_text("# fixture preregistration for the runner's tests\n")
        self.manifest["prereg"]["path"] = os.path.relpath(self.prereg, R)
        self.plan_doc = None
        if stage in ("S1", "S2", "S3"):
            self.manifest = self._roundtrip(bman.freeze(self.manifest, sha(self.prereg)))
        if stage in ("S2", "S3"):
            self._qualify()
        if stage == "S3":
            self._pin_plan()

    @staticmethod
    def _roundtrip(manifest: dict) -> dict:
        """Through JSON after every stage, as the tool's own CLI does: the seed pairs are tuples
        in memory and arrays on disk, and `manifest_at_run` is compared to the bytes."""
        return json.loads(bman.render(manifest))

    # -------------------------------------------------- the stages
    def _qualify(self) -> None:
        ev = self.d / "b2q"
        ev.mkdir(exist_ok=True)
        (ev / bman.MANIFEST_AT_RUN).write_text(bman.render(self.manifest))
        (ev / "run_log.json").write_text(json.dumps({"session": "B2Q"}))
        (ev / "adjudication.json").write_text(json.dumps(
            {"outcome": "PASS", "session": "B2Q", "measured_rate_per_hour": STUB_RATE,
             "audit_policy": bp.AUDIT_POLICY}))
        from test_b2_lifecycle import fill_evidence
        fill_evidence(ev)                           # the whole 1.2.0 set, with coherent archives
        self.ev = ev
        self.manifest = self._roundtrip(bman.qualify(self.manifest, ev, readjudicate=self.stub))

    def _pin_plan(self) -> None:
        plan = bp.build_plan(self.manifest["calibration"]["rate_per_hour"])
        prediction = bp.build_prediction(plan["fitness"], plan["budget_per_arm"],
                                         [tuple(p) for p in self.manifest["seeds"]["pairs"]],
                                         self.manifest["map"]["canonical_json_sha256"])
        self.plan_path, _ = bp.write(self.d, plan, prediction)
        self.manifest = self._roundtrip(bman.pin_plan(self.manifest, self.plan_path, readjudicate=self.stub))
        self.plan_doc = json.loads(self.plan_path.read_text())

    @staticmethod
    def stub(evidence_dir, manifest_at_run=None) -> dict:
        """The lifecycle's own test double: the evidence's recorded adjudication. The runner
        plugs the REAL adjudicator in; these fixtures carry no modelled B2Q session."""
        return json.loads((Path(evidence_dir) / "adjudication.json").read_text())

    # -------------------------------------------------- the invocation
    def path(self) -> Path:
        p = self.d / "b2_manifest.json"
        p.write_text(bman.render(self.manifest))
        return p

    def ruling(self, name: str, **fields) -> Path:
        p = self.d / f"{name}.json"
        p.write_text(json.dumps({"boardid": "17A6", "granted_by": "test", "date": "2026-09-11", **fields}))
        return p

    def args(self, profile: dict = rn.SEARCH, **over) -> types.SimpleNamespace:
        mp = self.path()
        session = profile["session"]
        seed = (self.plan_doc or {}).get("seed_derivation", {}).get("master_seed") \
            if profile is rn.SEARCH else rn.qualification_master(self.manifest)
        bound = dict(session=session, prereg_sha256=self.manifest["prereg"]["sha256"],
                     image_sha256=self.manifest["image"]["sha256"], b2_manifest_sha256=sha(mp))
        whole = dict(bound, ruling=profile["ruling_text"], master_seed=seed)
        base = dict(ruling=self.ruling("whole", **whole),
                    provision_ruling=self.ruling("pk", ruling=rn.PROVISION_RULING_TEXT, **bound),
                    boundary=self.d / "boundary.json", out=self.d / "out", manifest=mp,
                    instrument_root=inst.DEFAULT_ROOT, image=IMAGE, pair_first=0, pair_count=4,
                    qual_rate_per_hour=None, key=Path("/var/lib/p3signer/keys/K.bin"),
                    signer_user="p3signer", port="/dev/null")
        base.update(over)
        return types.SimpleNamespace(**base)

    def close(self) -> None:
        shutil.rmtree(self.d, ignore_errors=True)


def stub_pins(manifest, root):
    return {"stub": True}


@unittest.skipUnless(HAVE, "the built B2 image or its build evidence is absent")
class RefusalOrder(unittest.TestCase):
    """Each check, reached in the documented order, refuses for its own named reason."""

    def refuses(self, args, *words: str, profile: dict = rn.SEARCH, pins=stub_pins) -> str:
        with self.assertRaises(rn.Refusal) as cm:
            rn.preflight(args, profile, pins_verify=pins, readjudicate=Fixture.stub)
        msg = str(cm.exception)
        for w in words:
            self.assertIn(w, msg)
        return msg

    def test_there_is_no_committed_b2_manifest_yet(self):
        self.assertFalse(rn.MANIFEST.exists(), "a committed B2 manifest appeared; this test must change")
        a = types.SimpleNamespace(manifest=rn.MANIFEST)
        self.refuses(a, "no B2 manifest at", "does not exist until the image does")

    def test_a_document_that_is_not_a_b2_manifest(self):
        f = Fixture("S0")
        try:
            p = f.d / "not_a_manifest.json"
            p.write_text(json.dumps({"schema": "something_else"}))
            self.refuses(f.args(manifest=p), "not a b2_manifest")
            p.write_text("{nope")
            self.refuses(f.args(manifest=p), "not readable JSON")
        finally:
            f.close()

    def test_an_unfrozen_manifest_refuses_before_any_other_pin(self):
        f = Fixture("S0")
        try:
            self.refuses(f.args(), "preregistration is not frozen")
        finally:
            f.close()

    def test_a_frozen_manifest_whose_document_changed(self):
        f = Fixture("S1")
        try:
            f.prereg.write_text("# edited after the freeze\n")
            self.refuses(f.args(), "does not hash to the frozen preregistration")
        finally:
            f.close()

    def test_an_image_that_is_not_board_ready_or_not_the_pinned_bytes(self):
        f = Fixture("S1")
        try:
            f.manifest["image"]["board_ready"] = False
            self.refuses(f.args(), "not marked board_ready")
            f.manifest["image"]["board_ready"] = True
            self.refuses(f.args(image=f.prereg), "is not the pinned one")
            self.refuses(f.args(image=f.d / "absent.bin"), "no application image at")
        finally:
            f.close()

    def test_the_stage_each_profile_requires(self):
        f = Fixture("S1")
        try:
            self.refuses(f.args(), "not qualified")                      # B2 needs S2 and S3
        finally:
            f.close()
        g = Fixture("S3")
        try:                                                             # B2Q needs the S1 manifest
            self.refuses(g.args(profile=rn.QUALIFICATION, pair_first=None, pair_count=None),
                         "already qualified", profile=rn.QUALIFICATION)
        finally:
            g.close()

    def test_the_real_readjudicator_refuses_a_qualification_it_cannot_reproduce(self):
        """The default seam is the REAL B2 adjudicator over the pinned B2Q evidence, judged
        against B2Q's own documents and seeds. The fixture's B2Q evidence is a stub log, so it
        must not survive that — a pluggable verifier with nothing plugged in is not a check."""
        f = Fixture("S3")
        try:
            with self.assertRaises(rn.Refusal) as cm:
                rn.preflight(f.args(), rn.SEARCH, pins_verify=stub_pins)
            self.assertIn("re-adjudicates to", str(cm.exception))
        finally:
            f.close()

    def test_a_qualified_manifest_without_a_plan(self):
        f = Fixture("S2")
        try:
            self.refuses(f.args(), "pins no plan")
        finally:
            f.close()

    def test_a_pinned_plan_whose_bytes_changed(self):
        f = Fixture("S3")
        try:
            f.plan_path.write_text(f.plan_path.read_text() + "\n")
            self.refuses(f.args(), "does not hash to the manifest")
        finally:
            f.close()

    def test_the_instrument_pin_table_is_a_refusal_until_its_tool_exists(self):
        f = Fixture("S3")
        try:
            self.assertFalse((R / "host/b2_pins.py").exists(), "b2_pins.py appeared; this test must change")
            with self.assertRaises(rn.Refusal) as cm:
                rn.preflight(f.args(), rn.SEARCH, readjudicate=Fixture.stub)   # the REAL pins hook
            self.assertIn("b2_pins.py is not written yet", str(cm.exception))
        finally:
            f.close()

    def test_a_slice_outside_the_experiment_or_outside_the_split(self):
        f = Fixture("S3")
        try:
            total = f.plan_doc["pairs"]
            self.refuses(f.args(pair_first=total, pair_count=1), "does not lie inside the experiment")
            self.refuses(f.args(pair_first=0, pair_count=total + 1), "does not lie inside the experiment")
            self.refuses(f.args(pair_first=1, pair_count=4), "is not one the plan's split gives")
            self.refuses(f.args(pair_first=None, pair_count=None), "needs --pair-first and --pair-count")
        finally:
            f.close()

    def test_both_profiles_bind_their_own_master_seed(self):
        """B2Q's whole-of-run ruling was bound with master_seed None (the owner's P2-4)."""
        for stage, profile, first, count in (("S3", rn.SEARCH, 0, 4), ("S1", rn.QUALIFICATION, None, None)):
            f = Fixture(stage)
            try:
                want = f.plan_doc["seed_derivation"]["master_seed"] if profile is rn.SEARCH \
                    else rn.qualification_master(f.manifest)
                with self.subTest(profile=profile["session"]):
                    bound = dict(ruling=profile["ruling_text"], session=profile["session"],
                                 prereg_sha256=f.manifest["prereg"]["sha256"],
                                 image_sha256=f.manifest["image"]["sha256"],
                                 b2_manifest_sha256=sha(f.path()))
                    self.refuses(f.args(profile=profile, pair_first=first, pair_count=count,
                                        qual_rate_per_hour=2807.0,
                                        ruling=f.ruling("m", **dict(bound, master_seed=want ^ 1))),
                                 "bound to master_seed", profile=profile)
                    self.refuses(f.args(profile=profile, pair_first=first, pair_count=count,
                                        qual_rate_per_hour=2807.0, ruling=f.ruling("n", **bound)),
                                 "it lacks 'master_seed'", profile=profile)
            finally:
                f.close()

    def test_a_qualification_planning_rate_may_only_agree_with_the_declared_bound(self):
        """`inf` passed the positive-float check (the owner's P3-2), and the flag could widen the
        deadline the offline verdict has to reconstruct (P2-3). It may now only agree."""
        f = Fixture("S1")
        try:
            for bad, needle in ((float("inf"), "is not a finite positive rate"),
                                (float("-inf"), "is not a finite positive rate"),
                                (float("nan"), "is not a finite positive rate"),
                                (0, "is not a finite positive rate"),
                                (-1.0, "is not a finite positive rate"),
                                ("2807", "is not a finite positive rate"),
                                (True, "is not a finite positive rate"),
                                (1.0, "is not the declared planning bound"),
                                (rn.QUAL_PLANNING_RATE_PER_HOUR * 10, "is not the declared planning bound")):
                with self.subTest(rate=bad):
                    self.refuses(f.args(profile=rn.QUALIFICATION, pair_first=None, pair_count=None,
                                        qual_rate_per_hour=bad), needle, profile=rn.QUALIFICATION)
        finally:
            f.close()

    def test_the_qualification_deadline_comes_from_the_declared_bound(self):
        f = Fixture("S1")
        try:
            plan = rn.qualification_session_plan(f.manifest, "ab" * 32)
            self.assertAlmostEqual(plan["session_timeout_s"],
                                   rn.deadline_s(plan["expected_records"], rn.QUAL_PLANNING_RATE_PER_HOUR))
            self.assertEqual(plan["deadline_rate"]["rate_per_hour"], rn.QUAL_PLANNING_RATE_PER_HOUR)
            self.assertEqual(plan["binding"]["b2_manifest_sha256"], "ab" * 32)
        finally:
            f.close()

    def test_a_live_ruling_must_name_the_frozen_board(self):
        for stage, profile, first, count in (("S3", rn.SEARCH, 0, 4), ("S1", rn.QUALIFICATION, None, None)):
            f = Fixture(stage)
            try:
                want = f.plan_doc["seed_derivation"]["master_seed"] if profile is rn.SEARCH \
                    else rn.qualification_master(f.manifest)
                bound = dict(ruling=profile["ruling_text"], session=profile["session"],
                             prereg_sha256=f.manifest["prereg"]["sha256"],
                             image_sha256=f.manifest["image"]["sha256"],
                             b2_manifest_sha256=sha(f.path()), master_seed=want)
                with self.subTest(profile=profile["session"]):
                    wrong = f.ruling("bd", **bound)
                    wrong.write_text(json.dumps(dict(json.loads(wrong.read_text()), boardid="FFFF")))
                    self.refuses(f.args(profile=profile, pair_first=first, pair_count=count,
                                        ruling=wrong), "names board", profile=profile)
            finally:
                f.close()

    def test_a_manifest_without_a_board_authority_is_refused(self):
        f = Fixture("S3")
        try:
            for bad in (None, {}, {"boardid": ""}, {"boardid": ["17A6"]}, {"boardid": 17}):
                with self.subTest(board=bad):
                    f.manifest["board"] = bad
                    self.refuses(f.args(), "board")
            f.manifest.pop("board")
            self.refuses(f.args(), "pins no board")
        finally:
            f.close()

    def test_the_rulings_must_exist_be_this_text_and_be_bound(self):
        f = Fixture("S3")
        try:
            self.refuses(f.args(provision_ruling=None), "provisioning P3-K")
            self.refuses(f.args(ruling=f.ruling("x", ruling="whole-of-run B1 cartography")), "ruling text")
            self.refuses(f.args(ruling=f.d / "absent.json"), "no readable ruling at")
            bad = f.ruling("b", ruling=rn.RULING_TEXT, session="B2",
                           prereg_sha256=f.manifest["prereg"]["sha256"],
                           image_sha256=f.manifest["image"]["sha256"],
                           b2_manifest_sha256="0" * 64, master_seed=f.manifest["seeds"]["master_seed"])
            self.refuses(f.args(ruling=bad), "bound to b2_manifest_sha256")
            wrong_seed = f.ruling("c", ruling=rn.RULING_TEXT, session="B2",
                                  prereg_sha256=f.manifest["prereg"]["sha256"],
                                  image_sha256=f.manifest["image"]["sha256"],
                                  b2_manifest_sha256=sha(f.path()), master_seed=1)
            self.refuses(f.args(ruling=wrong_seed), "bound to master_seed")
            f.ruling("whole.json.consumed")                                # a claimed ruling
            (f.d / "whole.json.consumed").write_text("claimed at some time")
            self.refuses(f.args(), "was consumed")
        finally:
            f.close()


@unittest.skipUnless(HAVE, "the built B2 image or its build evidence is absent")
class PureParts(unittest.TestCase):
    """The pieces that are pure functions of the plan and the manifest."""

    @classmethod
    def setUpClass(cls):
        cls.f = Fixture("S3")

    @classmethod
    def tearDownClass(cls):
        cls.f.close()

    def test_the_split_decides_which_slices_exist(self):
        plan = self.f.plan_doc
        entry = rn.slice_in_split(plan, 0, 4)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["pairs"], [0, 1, 2, 3])
        self.assertIsNone(rn.slice_in_split(plan, 1, 4))
        self.assertIsNone(rn.slice_in_split(plan, 0, 9))
        undetermined = copy.deepcopy(plan)
        undetermined["session_split"] = {"status": "UNDETERMINED until B2Q measures the rate"}
        self.assertIsNone(rn.slice_in_split(undetermined, 0, 4), "an undetermined split licenses no slice")

    def test_the_qualification_seeds_are_disjoint_from_the_experiments(self):
        seeds = rn.qualification_seeds(self.f.manifest)
        self.assertEqual(len(seeds), rn.QUAL_PAIRS)
        used = {s for pair in self.f.manifest["seeds"]["pairs"] for s in pair}
        for pair in seeds:
            for s in pair:
                self.assertNotIn(s, used, "a B2Q seed collides with the experiment it calibrates")
                self.assertNotIn(s, bs.EXCLUDED_SEEDS)
        self.assertNotEqual(rn.qualification_master(self.f.manifest), self.f.manifest["seeds"]["master_seed"])

    def test_the_qualification_documents_are_b2qs_own(self):
        plan, prediction, seeds = rn.qualification_documents(self.f.manifest)
        self.assertEqual(plan["session"], bman.QUAL_SESSION)
        self.assertEqual(plan["budget_per_arm"], rn.QUAL_BUDGET)
        self.assertEqual(plan["pairs"], rn.QUAL_PAIRS)
        self.assertEqual(len(prediction["pairs"]), rn.QUAL_PAIRS)
        self.assertEqual(seeds, rn.qualification_seeds(self.f.manifest))
        import b2_adjudicate as adj
        adj.check_plan(plan)
        adj.check_prediction(prediction, plan)          # B2Q's own documents pass the same guards

    def test_the_identity_check_names_every_field_the_page_binds(self):
        cfg = {"manifest": self.f.manifest,
               "plan": {"n": 600, "master_seed": self.f.manifest["seeds"]["master_seed"],
                        "pairs_total": 9, "pair_first": 0, "pair_count": 4}}
        check = rn.identity_check_for(cfg)
        good = {"search_version": bs.ENGINE_VERSION,
                "map_sha256": self.f.manifest["map"]["canonical_json_sha256"],
                "operator_data_sha256": self.f.manifest["map"]["canonical_json_sha256"],
                "fitness_id": self.f.manifest["experiment"]["fitness"], "budget_per_arm": 600,
                "master_seed": self.f.manifest["seeds"]["master_seed"], "pairs_total": 9,
                "pair_first": 0, "pair_count": 4, "carrier_variant": rn.B2_VARIANT,
                "carrier_sha256": self.f.manifest["carrier"]["bitstream_sha256"],
                "universe_sha256": self.f.manifest["universe"]["sha256"],
                "protocol": rn.PROTOCOL_WIRE,
                "rec_retry_control": True, "sign_retry_control": True}
        self.assertEqual(check(good), [])
        for field in sorted(good):
            with self.subTest(field=field):
                bad = dict(good, **{field: "wrong"})
                self.assertTrue(any(field in x for x in check(bad)), check(bad))
        self.assertTrue(any("cartographer" in x for x in check(dict(good, carto_version="carto-v1"))))
        self.assertTrue(any("probes" in x for x in check(dict(good, probe_budget=333))))
        self.assertTrue(any("findings" in x for x in check(dict(good, findings=["something"]))))

    def test_the_deadline_is_the_preregistered_formula(self):
        self.assertAlmostEqual(rn.deadline_s(4810, 2807.0), 1.25 * 4810 * 3600 / 2807.0 + 600)
        entry = rn.slice_in_split(self.f.plan_doc, 0, 4)
        self.assertAlmostEqual(entry["deadline_s"], rn.deadline_s(entry["records"], STUB_RATE))
        self.assertEqual(entry["records"], bsess.records(4, self.f.plan_doc["budget_per_arm"]))

    def test_the_qualification_session_plan_is_the_preregistrations(self):
        plan = rn.qualification_session_plan(self.f.manifest)
        self.assertEqual(plan["session"], bman.QUAL_SESSION)
        self.assertEqual(plan["n"], rn.QUAL_BUDGET)
        self.assertEqual(plan["expected_records"], bsess.records(rn.QUAL_PAIRS, rn.QUAL_BUDGET))
        self.assertEqual(plan["expected_frames"]["records"], plan["expected_records"],
                         "the frame arithmetic counted the brackets twice")
        self.assertEqual(plan["audit_seqs"], set(range(1, plan["expected_records"] + 1)))
        self.assertEqual(plan["master_seed"], rn.qualification_master(self.f.manifest))

    def test_the_frame_arithmetic_counts_the_brackets_once(self):
        import l6_schedule as ls
        for pairs, budget in ((1, rn.QUAL_BUDGET), (4, 600)):
            with self.subTest(pairs=pairs, budget=budget):
                total = bsess.records(pairs, budget)
                frames = ls.expected_frames(total - 2, set(range(1, total + 1)), rn.PROTOCOL_WIRE)
                self.assertEqual(frames["records"], total)
                self.assertEqual(frames["audited_records"], total)


@unittest.skipUnless(HAVE, "the built B2 image or its build evidence is absent")
class SessionAcceptance(unittest.TestCase):
    """A record-complete log is NOT a session verdict. The owner's integration review of
    2026-09-11 showed the callback returning PASS for logs whose own summary declared STOPPED or
    PROTOCOL and for logs with no audits at all; the session's verdict now composes the
    instrument and evidence contract with the record replay.

    These fixtures are record-level only — they are the review's own probes — so they exercise
    the REFUSING half. A fully valid offline session fixture is not in this batch, and the
    positive path is therefore not demonstrated here (see the module's stated remainders)."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(R / "tests"))
        import test_b2_adjudicate as fx
        cls.fx = fx
        cls.f = Fixture("S3")
        cls.manifest_bytes = bman.render(cls.f.manifest)
        cls.manifest_sha = hashlib.sha256(cls.manifest_bytes.encode()).hexdigest()
        cls.session_plan = rn.qualification_session_plan(cls.f.manifest, cls.manifest_sha)

    @classmethod
    def tearDownClass(cls):
        cls.f.close()

    def _evidence(self, log: dict | None, *, audits=None, timeline=None, archive=True) -> Path:
        d = Path(tempfile.mkdtemp(prefix="b2sess_", dir=self.f.d))
        if log is not None:
            (d / "run_log.json").write_text(json.dumps(log))
        if archive:
            (d / bman.MANIFEST_AT_RUN).write_text(self.manifest_bytes)
        if audits is not None:
            (d / "audits.json").write_text(json.dumps(audits))
        if timeline is not None:
            (d / "timeline.json").write_text(json.dumps(timeline))
        return d

    def _judge(self, log, **kw) -> dict:
        return rn.judge_session(self._evidence(log, **kw), self.f.manifest, self.session_plan,
                                self.fx.PLAN, self.fx.PREDICTION, None, inst.DEFAULT_ROOT,
                                consts=self.fx.CONSTS)

    def test_a_record_complete_log_with_no_transport_evidence_is_not_a_pass(self):
        log = self.fx.modelled_log(0, self.fx.PAIRS)
        res = self._judge(log)
        self.assertNotEqual(res["outcome"], "PASS")
        self.assertTrue(any("audits.json" in x for x in res["findings"]), res["findings"][:3])
        self.assertTrue(any("timeline.json" in x for x in res["findings"]), res["findings"][:3])
        self.assertIsNone(res["measured_rate_per_hour"])
        self.assertIsNone(res["audit_policy"])

    def test_a_session_whose_own_summary_declares_it_failed_is_not_a_pass(self):
        """The review's STOPPED / PROTOCOL probes. They no longer reach a PASS. NOTE: with these
        record-only fixtures the instrument layer rejects the document before the epoch-outcome
        branch is evaluated, so this asserts the verdict, not that branch — which needs the
        complete session fixture this batch does not provide."""
        for kind in ("STOPPED", "PROTOCOL", "CRASHED"):
            with self.subTest(kind=kind):
                log = self.fx.modelled_log(0, self.fx.PAIRS)
                log["session_summary"] = {"epoch_end": {"kind": kind, "reason": "the review's probe",
                                                        "last_seq": len(log["loop_records"])}}
                res = self._judge(log, audits={}, timeline={})
                self.assertNotEqual(res["outcome"], "PASS", res["findings"][:3])

    def test_the_epoch_deadline_and_count_branches_through_a_real_session(self):
        """The review asked for these branches to be reached through a VALID instrument fixture,
        not by copying the production logic into a test. The fixture is the committed B1 session
        `evidence/b1/b1_17A6_2026-09-08-02` — a real sealed, audited, COMPLETED session — driven
        through the production `instrument_findings`. Only the B2 record replay is doubled (that
        log carries no search blocks); every instrument check here is the real one."""
        src = R / "evidence/b1/b1_17A6_2026-09-08-02"
        if not (src / "run_log.json").is_file():
            self.skipTest("the committed B1 session evidence is absent")
        d = Path(tempfile.mkdtemp(prefix="b2inst_", dir=self.f.d))
        for name in ("run_log.json", "audits.json", "timeline.json"):
            shutil.copy(src / name, d / name)
        log = json.loads((d / "run_log.json").read_text())
        l6 = log["l6"]
        base_plan = {"session": l6["session"], "audit_policy": l6["audit_policy"],
                     "audit_seqs": set(l6["audit_seqs"]), "protocol": l6["protocol"],
                     "crc_budget": l6["crc_budget"], "bad_frame_budget": l6["bad_frame_budget"],
                     "flags": l6["flags"], "expected_records": len(log["loop_records"]),
                     "session_timeout_s": l6["session_timeout_s"]}
        good = rn.instrument_findings(d, log, base_plan, inst.DEFAULT_ROOT)
        self.assertIsNone(good["rejected"], good.get("run_log_validation"))
        self.assertEqual(good["findings"], [], good["findings"][:4])
        self.assertIsNotNone(good["rate"], "the positive control measured no rate")
        self.assertEqual(good["audit_policy"], l6["audit_policy"])
        span = good["rate_report"]["session_span_s"]

        short = rn.instrument_findings(d, log, dict(base_plan, session_timeout_s=1.0), inst.DEFAULT_ROOT)
        self.assertTrue(any("deadline this session was authorised for" in x for x in short["findings"]),
                        short["findings"][:4])
        self.assertGreater(span, 1.0)

        none_deadline = dict(base_plan)
        none_deadline["session_timeout_s"] = None
        no_limit = rn.instrument_findings(d, log, none_deadline, inst.DEFAULT_ROOT)
        self.assertTrue(any("held to no limit" in x for x in no_limit["findings"]), no_limit["findings"][:4])

        miscount = rn.instrument_findings(d, log, dict(base_plan, expected_records=base_plan["expected_records"] - 1),
                                          inst.DEFAULT_ROOT)
        self.assertTrue(any("the epoch ended at seq" in x for x in miscount["findings"]), miscount["findings"][:4])

        stopped = copy.deepcopy(log)
        stopped["session_summary"]["epoch_end"]["kind"] = "STOPPED"
        (d / "run_log.json").write_text(json.dumps(stopped))
        bad_epoch = rn.instrument_findings(d, stopped, base_plan, inst.DEFAULT_ROOT)
        # A COMPLETED session relabelled STOPPED contradicts its own closing steps, so the
        # instrument's validator refuses it before the epoch-outcome line is reached. Either way
        # it is not clean — which is the property under test.
        self.assertTrue(bad_epoch["rejected"] or bad_epoch["findings"],
                        "a session declared STOPPED passed the instrument layer")

    def test_the_export_seal_is_checked_through_a_real_sealed_session(self):
        src = R / "evidence/b1/b1_17A6_2026-09-08-02"
        if not (src / "exports.json").is_file():
            self.skipTest("the committed B1 session evidence is absent")
        d = Path(tempfile.mkdtemp(prefix="b2seal_", dir=self.f.d))
        for name in ("run_log.json", "audits.json", "timeline.json", "exports.json",
                     "console.log", "console.ts.log"):
            shutil.copy(src / name, d / name)
        self.assertEqual(rn.export_seal_findings(d), [], "the real sealed session did not verify")
        (d / "console.log").write_text((d / "console.log").read_text() + "one more line\n")
        self.assertTrue(any("does not hash / size" in x for x in rn.export_seal_findings(d)))
        (d / "exports.json").unlink()
        self.assertTrue(any("no exports.json" in x for x in rn.export_seal_findings(d)))

    def test_a_record_only_log_is_rejected_by_the_instrument_layer_itself(self):
        """The review's fixture is record-complete but is not a session document: the instrument's
        standalone validator rejects it before any of the later checks are reached. That is the
        point — the record replay alone used to answer PASS here."""
        log = self.fx.modelled_log(0, self.fx.PAIRS)
        res = self._judge(log, audits={}, timeline={})
        self.assertNotEqual(res["outcome"], "PASS")
        self.assertIn("run_log rejected", res["outcome"])
        self.assertIn("REJECTED", str(res["instrument"]["run_log_validation"]))
        self.assertIsNone(res["measured_rate_per_hour"])
        self.assertIsNone(res["audit_policy"])

    def test_no_run_log_at_all(self):
        d = self._evidence(None)
        res = rn.judge_session(d, self.f.manifest, self.session_plan, self.fx.PLAN,
                               self.fx.PREDICTION, None, inst.DEFAULT_ROOT, consts=self.fx.CONSTS)
        self.assertTrue(res["outcome"].startswith("REFUSED"), res["outcome"][:120])
        self.assertIn("no run_log.json", res["outcome"])

    def test_evidence_that_does_not_belong_to_this_invocation(self):
        """The `manifest` argument used to be decoration: every other check read declarations
        that agreed with each other and with nothing else (the owner's P2-1 of 2026-09-11)."""
        log = self.fx.modelled_log(0, self.fx.PAIRS)
        res = rn.judge_session(self._evidence(log, archive=False), self.f.manifest, self.session_plan,
                               self.fx.PLAN, self.fx.PREDICTION, None, inst.DEFAULT_ROOT,
                               consts=self.fx.CONSTS)
        self.assertNotEqual(res["outcome"], "PASS")
        self.assertTrue(any("archived no manifest" in x for x in res["findings"]), res["findings"][:3])

        d = self._evidence(log)                      # an archived manifest that is not this one
        other = json.loads(self.manifest_bytes)
        other["status"] = "a different manifest"
        (d / bman.MANIFEST_AT_RUN).write_text(bman.render(other))
        res = rn.judge_session(d, self.f.manifest, self.session_plan, self.fx.PLAN, self.fx.PREDICTION,
                               None, inst.DEFAULT_ROOT, consts=self.fx.CONSTS)
        self.assertNotEqual(res["outcome"], "PASS")
        self.assertTrue(any("hashes to" in x for x in res["findings"]), res["findings"][:3])

        d = self._evidence(log)                      # the bytes match but the stage does not
        res = rn.judge_session(d, dict(self.f.manifest, image=dict(self.f.manifest["image"],
                                                                   sha256="aa" * 32)),
                               self.session_plan, self.fx.PLAN, self.fx.PREDICTION, None,
                               inst.DEFAULT_ROOT, consts=self.fx.CONSTS)
        self.assertTrue(any("archived manifest's image" in x for x in res["findings"]), res["findings"][:3])

    def test_the_result_carries_what_the_lifecycle_consumes(self):
        res = self._judge(self.fx.modelled_log(0, self.fx.PAIRS), audits={}, timeline={})
        for key in ("session", "outcome", "measured_rate_per_hour", "audit_policy"):
            self.assertIn(key, res, "the S2 transition reads this field")
        self.assertEqual(res["session"], self.session_plan["session"])

    def test_the_rate_and_policy_are_never_echoed_from_a_stored_adjudication(self):
        d = self._evidence(self.fx.modelled_log(0, self.fx.PAIRS), audits={}, timeline={})
        (d / "adjudication.json").write_text(json.dumps(
            {"outcome": "PASS", "session": "B2Q", "measured_rate_per_hour": 9999.0,
             "audit_policy": "all-self-reporting"}))
        res = rn.judge_session(d, self.f.manifest, self.session_plan, self.fx.PLAN,
                               self.fx.PREDICTION, None, inst.DEFAULT_ROOT, consts=self.fx.CONSTS)
        self.assertNotEqual(res["measured_rate_per_hour"], 9999.0,
                            "the stored adjudication was echoed instead of recomputed")
        self.assertNotEqual(res["outcome"], "PASS")


@unittest.skipUnless(HAVE, "the built B2 image or its build evidence is absent")
class OfflineBinding(unittest.TestCase):
    """A zero-finding positive control, then every field independently (the owner's binding
    completion review of 2026-09-11). `binding_findings` is a pure function of the log, the
    session plan and the manifest, so each mutation is isolated."""

    @classmethod
    def setUpClass(cls):
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        cls.f = Fixture("S1")
        cls.plan = rn.qualification_session_plan(cls.f.manifest, "ab" * 32)
        cls.log = {"l6": {"binding": copy.deepcopy(cls.plan["binding"]),
                          "inputs": copy.deepcopy(cls.plan["inputs"])},
                   "app_identity": dict(rn.expected_identity(cls.f.manifest, cls.plan),
                                        schema="app_identity", schema_version="1.5.0")}

    @classmethod
    def tearDownClass(cls):
        cls.f.close()

    def _findings(self, mutate=None) -> list[str]:
        log = copy.deepcopy(self.log)
        if mutate:
            mutate(log)
        return rn.binding_findings(log, self.plan, self.f.manifest)

    def test_the_positive_control_has_no_findings(self):
        self.assertEqual(self._findings(), [])

    def test_the_b2q_plan_carries_its_inputs_contract(self):
        """It carried none, and a missing expectation silently disabled the check."""
        self.assertIsInstance(self.plan.get("inputs"), dict)
        self.assertEqual(self.plan["inputs"], rn.expected_inputs(self.f.manifest, rn.QUALIFICATION))
        stripped = dict(self.plan)
        stripped.pop("inputs")
        self.assertTrue(any("carries no inputs contract" in x
                            for x in rn.binding_findings(copy.deepcopy(self.log), stripped, self.f.manifest)))

    def test_every_identity_field_is_held(self):
        for field in sorted(rn.expected_identity(self.f.manifest, self.plan)):
            with self.subTest(field=field):
                findings = self._findings(lambda log, k=field: log["app_identity"].__setitem__(k, "wrong"))
                self.assertTrue(any(f"IDENT {field}" in x for x in findings), findings[:3])

    def test_the_carrier_and_universe_digests_are_held(self):
        """The two the offline path used to omit entirely."""
        for field in ("carrier_sha256", "universe_sha256", "carrier_variant"):
            with self.subTest(field=field):
                findings = self._findings(lambda log, k=field: log["app_identity"].__setitem__(k, "0" * 64))
                self.assertTrue(any(f"IDENT {field}" in x for x in findings), findings[:3])

    def test_a_missing_or_wrong_inputs_block(self):
        self.assertTrue(any("carries no inputs block" in x
                            for x in self._findings(lambda log: log["l6"].pop("inputs"))))
        for k in sorted(self.plan["inputs"]):
            with self.subTest(field=k):
                findings = self._findings(lambda log, k=k: log["l6"]["inputs"].__setitem__(k, "0" * 64))
                self.assertTrue(any(f"inputs: the log's {k}" in x for x in findings), findings[:3])

    def test_every_binding_field_is_held(self):
        for k in sorted(self.plan["binding"]):
            with self.subTest(field=k):
                findings = self._findings(lambda log, k=k: log["l6"]["binding"].__setitem__(k, "wrong"))
                self.assertTrue(any(f"binding: the log's {k}" in x for x in findings), findings[:3])

    def test_a_missing_identity_or_binding_block(self):
        self.assertTrue(any("declared no app_identity" in x
                            for x in self._findings(lambda log: log.pop("app_identity"))))
        self.assertTrue(any("no binding block" in x
                            for x in self._findings(lambda log: log["l6"].pop("binding"))))
        self.assertTrue(any("no l6 block" in x for x in self._findings(lambda log: log.pop("l6"))))

    def test_without_a_manifest_the_identity_contract_is_named_unchecked(self):
        findings = rn.binding_findings(copy.deepcopy(self.log), self.plan, None)
        self.assertTrue(any("identity contract was not checked" in x for x in findings), findings)


@unittest.skipUnless(HAVE, "the built B2 image or its build evidence is absent")
class ArchivedRulings(unittest.TestCase):
    """The archives are DECODED and REBOUND, not merely hashed: recording the digest of an
    archive that was never parsed preserves an invalid declaration (the owner's P2-2)."""

    @classmethod
    def setUpClass(cls):
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import b1_qualification as bq
        cls.bq = bq
        cls.f = Fixture("S1")
        cls.plan = rn.qualification_session_plan(cls.f.manifest, "ab" * 32)

    @classmethod
    def tearDownClass(cls):
        cls.f.close()

    def _body(self, key: str) -> dict:
        b = self.plan["binding"]
        body = {"ruling": rn.QUAL_RULING_TEXT if key == "whole_of_run" else rn.PROVISION_RULING_TEXT,
                "boardid": "17A6", "granted_by": "t", "date": "2026-09-11", "session": b["session"],
                "prereg_sha256": b["prereg_sha256"], "image_sha256": b["image_sha256"],
                "b2_manifest_sha256": b["b2_manifest_sha256"]}
        if key == "whole_of_run":
            body["master_seed"] = b["master_seed"]
        return body

    def _dir(self, whole=None, prov=None) -> Path:
        d = Path(tempfile.mkdtemp(prefix="b2rul_", dir=self.f.d))
        for key, body in (("whole_of_run", whole if whole is not None else self._body("whole_of_run")),
                          ("provisioning", prov if prov is not None else self._body("provisioning"))):
            path = d / self.bq.RULING_FILES[key]
            if isinstance(body, str):
                path.write_text(body)
            else:
                path.write_text(json.dumps(self.bq.archive_envelope(json.dumps(body).encode())))
        return d

    def test_the_positive_control_has_no_findings(self):
        self.assertEqual(rn.archived_ruling_findings(self._dir(), self.plan), [])

    def test_an_archive_that_is_not_json_at_all(self):
        for whole, prov in (("not JSON", None), (None, "not JSON")):
            with self.subTest(whole=whole, prov=prov):
                findings = rn.archived_ruling_findings(self._dir(whole, prov), self.plan)
                self.assertTrue(findings, "an unparseable archive was accepted")

    def test_an_archive_declaring_another_session_seed_image_board_or_text(self):
        b = self.plan["binding"]
        for field, value, needle in (("master_seed", b["master_seed"] ^ 1, "master_seed"),
                                     ("image_sha256", "0" * 64, "image_sha256"),
                                     ("b2_manifest_sha256", "0" * 64, "b2_manifest_sha256"),
                                     ("prereg_sha256", "0" * 64, "prereg_sha256"),
                                     ("session", "B2", "session"),
                                     ("ruling", "whole-of-run B2 map utility", "ruling text"),
                                     ("boardid", "", "boardid"),
                                     ("granted_by", "", "granted_by")):
            with self.subTest(field=field):
                whole = self._body("whole_of_run")
                whole[field] = value
                findings = rn.archived_ruling_findings(self._dir(whole), self.plan)
                self.assertTrue(any(needle in x for x in findings), (field, findings[:3]))

    def test_the_two_archives_must_name_the_same_board(self):
        whole = self._body("whole_of_run")
        whole["boardid"] = "OTHER"
        findings = rn.archived_ruling_findings(self._dir(whole), self.plan)
        self.assertTrue(any("different boards" in x for x in findings), findings[:3])

    def test_an_unparseable_archive_is_refused_at_acceptance_not_merely_hashed(self):
        """The record builder used to hash an archive that had never been parsed, which preserves
        the invalid declaration instead of catching it."""
        import b2_manifest as m
        d = self._dir("not JSON")
        (d / m.MANIFEST_AT_RUN).write_text(bman.render(self.f.manifest))
        (d / "run_log.json").write_text("{}")
        (d / "adjudication.json").write_text(json.dumps(
            {"outcome": "PASS", "session": "B2Q", "measured_rate_per_hour": 2807.0,
             "audit_policy": "all-self-reporting"}))
        for name in m.QUAL_EVIDENCE_FILES:
            if not (d / name).exists():
                (d / name).write_text("{}")
        with self.assertRaises(m.Refusal) as cm:
            m.reconstruct_qualification_record(d)
        self.assertIn("not a readable ruling archive", str(cm.exception))

    def test_the_expected_board_is_required_and_compared(self):
        """Two archives agreeing on the WRONG board used to pass, because no expected board was
        ever established (the owner's P2 of 2026-09-11). The authority is the frozen manifest's,
        never a ruling's."""
        self.assertEqual(self.plan["binding"]["boardid"], bman.check_board(self.f.manifest))
        both_wrong = (self._body("whole_of_run"), self._body("provisioning"))
        for body in both_wrong:
            body["boardid"] = "FFFF"
        findings = rn.archived_ruling_findings(self._dir(*both_wrong), self.plan)
        self.assertEqual(len([x for x in findings if "names board" in x]), 2, findings)
        for bad in (None, "", "   ", ["17A6"], 17, {"boardid": "17A6"}):
            with self.subTest(boardid=bad):
                pair = (self._body("whole_of_run"), self._body("provisioning"))
                for body in pair:
                    body["boardid"] = bad
                findings = rn.archived_ruling_findings(self._dir(*pair), self.plan)
                self.assertTrue(findings, f"a boardid of {bad!r} was accepted")

    def test_a_session_that_declares_no_board_authority_is_refused(self):
        plan = copy.deepcopy(self.plan)
        plan["binding"].pop("boardid")
        findings = rn.archived_ruling_findings(self._dir(), plan)
        self.assertTrue(any("declares no board authority" in x for x in findings), findings)
        plan["binding"]["boardid"] = ""
        self.assertTrue(any("declares no board authority" in x
                            for x in rn.archived_ruling_findings(self._dir(), plan)))

    def test_a_missing_archive(self):
        d = self._dir()
        (d / self.bq.RULING_FILES["provisioning"]).unlink()
        self.assertTrue(any("archived no provisioning authorisation" in x
                            for x in rn.archived_ruling_findings(d, self.plan)))


@unittest.skipUnless(HAVE, "the built B2 image or its build evidence is absent")
class TheRulingTextsAreProposals(unittest.TestCase):
    def test_the_runner_refuses_any_text_but_the_two_it_declares(self):
        f = Fixture("S3")
        try:
            for text, needle in (("whole-of-run B2", "ruling text"),
                                 ("", "lacks 'ruling'"),
                                 ("whole-of-run B2 map utility ", "ruling text"),
                                 (rn.QUAL_RULING_TEXT, "ruling text")):
                with self.subTest(text=text):
                    with self.assertRaises(rn.Refusal) as cm:
                        rn.preflight(f.args(ruling=f.ruling("t", ruling=text)), rn.SEARCH,
                                     pins_verify=stub_pins, readjudicate=Fixture.stub)
                    self.assertIn(needle, str(cm.exception))
        finally:
            f.close()


if __name__ == "__main__":
    unittest.main()
