#!/usr/bin/env python3
"""The main-preparation tools (archive_session.py, restore_rejudge.py) over SYNTHETIC B3 sessions — hermetic,
host-only, every device and authority behind the same fake seams b3/tests/test_b3_runner.py uses for the runner
(its `Fixture` runs the REAL production preflight and execute over a fixture manifest at S3; its instrument layer
is a fake that passes, its record replay runs with common validation off). Run in its OWN process:

    python3 -B evidence/b3/main_preparation_2026_10_14/test_main_preparation.py

What this proves and what it does not: `search_session_plan` equals the production preflight's plan key for key
on the same inputs; the archive → fresh restore → re-judge round trip ACCEPTs a synthetic SEARCH session and a
synthetic B3Q session and refuses, by name, a tampered archive member, a changed binding, a changed slice, a
changed deadline, a changed budget, a mislabelled profile and a wrong boundary. It does NOT exercise the
production instrument layer on SEARCH evidence (no such evidence exists before the first board session);
test_main_preparation_production.py runs the production path over the real B3Q -02 archive in its own process.
No skip: a missing instrument checkout is a failure.
"""
from __future__ import annotations
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]
for p in (R / "host", R / "b3/host", R / "b3/tests", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import b1_qualification as bq  # noqa: E402
import b3_runner as rn  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402
import test_b3_runner as rt  # noqa: E402  (the pinned fixture: the real preflight / execute behind fake seams)
import restore_rejudge as rr  # noqa: E402
import archive_session as ar  # noqa: E402

SYNTHETIC = "SYNTHETIC (test_main_preparation.py): not written by the driver\n"


def synth_session(f: rt.Fixture) -> tuple[dict, Path]:
    """The production execute over the fixture's fake board, then the five small files the real driver writes and
    the fixture's modelled driver does not (summary.json with the plan as l6, the preflight / identity-page /
    ymodem records) — exactly sixteen files, as the runner leaves them."""
    cfg = f.preflight()
    rc, outcome = rn.execute(f.args(), cfg)
    assert (rc, outcome) == (0, "PASS"), (rc, outcome)
    ev = f.d / "evidence"
    rec = json.loads((ev / "runner_session.json").read_text())
    summary = {"outcome": outcome, "l6": {**cfg["plan"], "audit_seqs": sorted(cfg["plan"]["audit_seqs"])},
               "crc_dropped": rec["transport"]["crc_dropped"], "bad_frames": rec["transport"]["bad_frames"],
               "disruptions": [], "transport_rereads": [], "token": cfg["token"], "synthetic": SYNTHETIC.strip()}
    (ev / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    (ev / "B1_0_preflight.json").write_text(json.dumps({"synthetic": SYNTHETIC.strip()}) + "\n")
    (ev / "B1_1_identity_page.json").write_text(json.dumps({"synthetic": SYNTHETIC.strip(), "flags": cfg["plan"]["flags"]}) + "\n")
    (ev / "ymodem.log").write_text(SYNTHETIC)
    (ev / "ymodem_app.log").write_text(SYNTHETIC)
    assert sorted(p.name for p in ev.iterdir()) == list(rr.SESSION_FILES)
    return cfg, ev


def archived(f: rt.Fixture, raw: Path, name: str = "synthetic_session") -> Path:
    out = f.d / "archived" / name
    ar.archive(raw, out, f.boundary, None, HERE / "restore_rejudge.py", root=rr.ROOT)
    return out


def rejudge(f: rt.Fixture, session_dir: Path) -> dict:
    return rr.rejudge(session_dir, ports=f.ports, authority=f.authority, instrument_root=inst.DEFAULT_ROOT, root=rr.ROOT)


def envelope(doc: dict) -> str:
    return json.dumps(bq.archive_envelope(json.dumps(doc).encode()), indent=1) + "\n"


def relist(session_dir: Path) -> None:
    """Re-record the ordinary files' sizes and digests in archive.json after a deliberate edit (so the restore
    passes and the LATER check is the one that refuses)."""
    doc = json.loads((session_dir / "archive.json").read_text())
    doc["ordinary_files"] = [ar.entry(session_dir / m) for m in rr.ORDINARY]
    (session_dir / "archive.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")


class ThePlanRebuild(unittest.TestCase):
    """search_session_plan equals the production preflight's plan, key for key, on the same inputs."""

    def _equal(self, first, count):
        f = rt.Fixture("S3", first, count)
        try:
            cfg = f.preflight()
            instrument = f.ports.bind_instrument(inst.DEFAULT_ROOT)
            plan = rr.search_session_plan(f.manifest, f.manifest_sha, f.plan_doc, f.pred_doc, first, count,
                                          cfg["ruling"]["transport_disposition"], instrument, f.ports, f.authority)
            self.assertEqual(sorted(plan), sorted(cfg["plan"]))
            for k in sorted(plan):
                self.assertEqual(plan[k], cfg["plan"][k], f"key {k}")
            self.assertEqual(rr._jsonable(plan), rr._jsonable(cfg["plan"]))
        finally:
            f.close()

    def test_the_first_split_session_equals_the_preflight_s_plan(self):
        self._equal(0, 2)

    def test_the_second_split_session_equals_the_preflight_s_plan(self):
        self._equal(2, 1)

    def test_the_refusals_are_the_preflight_s(self):
        f = rt.Fixture("S3", 0, 2)
        try:
            instrument = f.ports.bind_instrument(inst.DEFAULT_ROOT)
            with self.assertRaises(rr.Refusal) as cm:
                rr.search_session_plan(f.manifest, f.manifest_sha, f.plan_doc, f.pred_doc, 1, 1, "d", instrument, f.ports, f.authority)
            self.assertIn("is not one the plan's split gives", str(cm.exception))
            m = copy.deepcopy(f.manifest); m["seeds"]["master_seed"] += 1
            with self.assertRaises(rr.Refusal) as cm:
                rr.search_session_plan(m, f.manifest_sha, f.plan_doc, f.pred_doc, 0, 2, "d", instrument, f.ports, f.authority)
            self.assertIn("master seed is not the manifest's", str(cm.exception))
            with self.assertRaises(rr.Refusal) as cm:
                rr.search_session_plan(f.manifest, f.manifest_sha, f.qplan_doc, f.qpred_doc, 0, 1, "d", instrument, f.ports, f.authority)
            self.assertIn("is not a B3 plan", str(cm.exception))
            with self.assertRaises(rr.Refusal) as cm:
                rr.search_session_plan(f.manifest, f.manifest_sha, f.plan_doc, f.pred_doc, 0, 2, "  ", instrument, f.ports, f.authority)
            self.assertIn("no transport disposition", str(cm.exception))
            with self.assertRaises(rr.Refusal) as cm:
                rr.search_session_plan(f.manifest, f.manifest_sha, f.plan_doc, f.pred_doc, 0, 2, "d", {"psoracle_commit": "f" * 40}, f.ports, f.authority)
            self.assertIn("bound instrument's commit", str(cm.exception))
        finally:
            f.close()


class TheRoundTrip(unittest.TestCase):
    """archive → fresh restore → re-judge on a synthetic SEARCH session (fake seams): ACCEPT, equal to the archived
    verdict; and every named refusal on a tampered copy."""

    @classmethod
    def setUpClass(cls):
        cls.f = rt.Fixture("S3", 0, 2)
        cls.cfg, cls.raw = synth_session(cls.f)
        cls.session = archived(cls.f, cls.raw)

    @classmethod
    def tearDownClass(cls):
        cls.f.close()

    def copy(self) -> Path:
        d = Path(tempfile.mkdtemp(prefix="b3prep_mut_", dir=self.f.d))
        dst = d / self.session.name
        shutil.copytree(self.session, dst)
        return dst

    def refused(self, session_dir: Path, needle: str) -> dict:
        res = rejudge(self.f, session_dir)
        self.assertEqual(res["verdict"], "REFUSE", res)
        self.assertIn(needle, res["refusal"], res["refusal"])
        self.assertTrue(res.get("restored_dir_removed"), "the restore directory is removed on a refusal too")
        return res

    def test_the_archive_is_form_c(self):
        doc = json.loads((self.session / "archive.json").read_text())
        self.assertEqual(doc["schema"], rr.ARCHIVE_SCHEMA)
        self.assertEqual([m["name"] for m in doc["archive"]["members"]], list(rr.MEMBERS))
        self.assertEqual([m["name"] for m in doc["ordinary_files"]], list(rr.ORDINARY))
        self.assertEqual(sorted(p.name for p in self.session.iterdir()), sorted(list(rr.ORDINARY) + ["archive.json", "exports.tar.zst", "restore_rejudge.py"]))
        self.assertTrue(doc["restore_rejudge"]["equals_preparation_copy"])
        self.assertEqual(doc["session"], "B3")
        self.assertEqual(doc["boundary"]["sha256"], rt.sha(self.f.boundary))
        for m in rr.MEMBERS:          # the raw directory is untouched
            self.assertTrue((self.raw / m).is_file())
        self.assertEqual(sorted(p.name for p in self.raw.iterdir()), list(rr.SESSION_FILES))

    def test_the_archive_is_deterministic(self):
        again = archived(self.f, self.raw, "again")
        self.assertEqual(rt.sha(again / "exports.tar.zst"), rt.sha(self.session / "exports.tar.zst"))

    def test_the_positive_control_accepts_and_equals_the_archived_verdict(self):
        res = rejudge(self.f, self.session)
        self.assertEqual(res["verdict"], "ACCEPT", res)
        self.assertIsNone(res["refusal"])
        self.assertEqual(res["steps"]["judge"]["outcome"], "PASS")
        self.assertEqual(res["steps"]["judge"]["keys_differing_from_archived"], [])
        self.assertTrue(res["steps"]["session_plan"]["summary_l6_equal"] and res["steps"]["session_plan"]["run_log_l6_equal"])
        self.assertEqual(res["steps"]["session_plan"]["pair_first"], 0)
        self.assertEqual(res["steps"]["session_plan"]["pair_count"], 2)
        self.assertEqual(res["steps"]["session_plan"]["resend_budget"], self.f.resend)
        self.assertEqual(res["steps"]["restore"]["files"], 16)
        self.assertEqual(res["steps"]["seal"], "ok")
        self.assertTrue(res["restored_dir_removed"])

    def test_the_script_runs_from_a_session_copy_as_a_process(self):
        import subprocess
        r = subprocess.run([sys.executable, "-B", str(self.session / "restore_rejudge.py"), "--session-dir", str(self.session), "--repo-root", str(rr.ROOT)],
                           capture_output=True, text=True, cwd=self.f.d)
        # the process uses the PRODUCTION seams, under which the fixture's modelled evidence cannot pass: it must
        # refuse (or error) by name, never accept — the fixture's instrument layer is a fake only inside this process
        self.assertNotEqual(r.returncode, 0, r.stdout[-400:])
        self.assertNotIn('"verdict": "ACCEPT"', r.stdout)

    def test_a_tampered_member_is_refused(self):
        s = self.copy()
        with open(s / "exports.tar.zst", "ab") as fh:
            fh.write(b"\0")
        self.refused(s, "does not size / hash to archive.json")
        s = self.copy()
        doc = json.loads((s / "archive.json").read_text())
        doc["archive"]["members"][0]["sha256"] = "0" * 64
        (s / "archive.json").write_text(json.dumps(doc))
        self.refused(s, "sha256 differs from archive.json")

    def test_a_missing_member_is_refused(self):
        s = self.copy()
        raw2 = s.parent / "raw2"
        shutil.copytree(self.raw, raw2)
        (raw2 / "timeline.json").write_text("{}")                      # a drifted member: the seal catches it after the restore
        doc = json.loads((s / "archive.json").read_text())
        ar.build_tar(raw2, s / "exports.tar.zst.new", doc["archive"]["member_mtime_epoch"])
        os.replace(s / "exports.tar.zst.new", s / "exports.tar.zst")
        doc["archive"]["bytes"], doc["archive"]["sha256"] = (s / "exports.tar.zst").stat().st_size, rt.sha(s / "exports.tar.zst")
        (s / "archive.json").write_text(json.dumps(doc))
        self.refused(s, "timeline.json: size")
        doc["archive"]["members"] = [ar.entry(raw2 / m) for m in rr.MEMBERS]
        (s / "archive.json").write_text(json.dumps(doc))
        self.refused(s, "evidence seal")

    def test_a_changed_binding_is_refused(self):
        s = self.copy()
        m = json.loads((s / "manifest_at_run.json").read_text())
        (s / "manifest_at_run.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")     # whitespace only: another file digest
        relist(s)
        self.refused(s, "the archived ruling binds")

    def test_a_changed_slice_is_refused(self):
        s = self.copy()
        r = self.f.ruling_doc(); r["pair_first"], r["pair_count"] = 2, 1                          # another legal slice of the split
        (s / "ruling_whole_of_run.json").write_text(envelope(r))
        relist(s)
        self.refused(s, "differs from summary.json's l6")
        s = self.copy()
        rec = json.loads((s / "runner_session.json").read_text()); rec["pair_count"] = 1
        (s / "runner_session.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
        relist(s)
        self.refused(s, "runner_session.json against the rebuilt plan")

    def test_a_changed_deadline_is_refused(self):
        s = self.copy()
        sm = json.loads((s / "summary.json").read_text()); sm["l6"]["session_timeout_s"] += 1.0
        (s / "summary.json").write_text(json.dumps(sm, indent=2, default=str) + "\n")
        relist(s)
        res = self.refused(s, "differs from summary.json's l6")
        self.assertIn("session_timeout_s", res["refusal"])

    def test_a_changed_budget_is_refused(self):
        s = self.copy()
        sm = json.loads((s / "summary.json").read_text()); sm["l6"]["resend_budget"] += 1
        (s / "summary.json").write_text(json.dumps(sm, indent=2, default=str) + "\n")
        relist(s)
        res = self.refused(s, "differs from summary.json's l6")
        self.assertIn("resend_budget", res["refusal"])
        s = self.copy()
        r = self.f.ruling_doc(); r["resend_budget"] += 1                                             # the archived authorisation itself
        (s / "ruling_whole_of_run.json").write_text(envelope(r))
        relist(s)
        res = self.refused(s, "re-judge differs from the archived adjudication.json")
        self.assertIn("resend_budget", json.dumps(res["steps"]["judge"]["findings"]))
        s = self.copy()
        sm = json.loads((s / "summary.json").read_text()); sm["l6"]["crc_budget"] += 1
        (s / "summary.json").write_text(json.dumps(sm, indent=2, default=str) + "\n")
        relist(s)
        self.refused(s, "crc_budget")

    def test_a_mislabelled_profile_is_refused(self):
        s = self.copy()
        rec = json.loads((s / "runner_session.json").read_text()); rec["session"] = "B3Q"
        (s / "runner_session.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
        relist(s)
        self.refused(s, "is not the B3Q text")
        s = self.copy()
        rec = json.loads((s / "runner_session.json").read_text()); rec["session"] = "B2"
        (s / "runner_session.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
        relist(s)
        self.refused(s, "not a B3 session record")

    def test_a_wrong_boundary_is_refused(self):
        s = self.copy()
        doc = json.loads((s / "archive.json").read_text()); doc["boundary"]["sha256"] = "0" * 64
        (s / "archive.json").write_text(json.dumps(doc))
        self.refused(s, "boundary record does not hash")
        s = self.copy()
        b = self.f.boundary_doc(); b["all_passed"] = False
        bp = s.parent / "boundary_failed.json"; bp.write_text(json.dumps(b))
        doc = json.loads((s / "archive.json").read_text()); doc["boundary"] = {"path": os.path.relpath(bp, rr.ROOT), "sha256": rt.sha(bp)}
        (s / "archive.json").write_text(json.dumps(doc))
        self.refused(s, "not a passed principal_boundary")

    def test_an_authority_refusal_is_the_verdict(self):
        f = self.f
        keep = f.authority
        try:
            f.authority = rt.FakeAuthority(pins_refusal="b3/host/b3_gate.py is not in the table")
            self.refused(self.session, "instrument pins: b3/host/b3_gate.py is not in the table")
            f.authority = rt.FakeAuthority(verify_refusal="S3: the pinned plan drifted")
            self.refused(self.session, "manifest: S3: the pinned plan drifted")
        finally:
            f.authority = keep


class TheArchiver(unittest.TestCase):
    def test_the_refusals(self):
        f = rt.Fixture("S3", 0, 2)
        try:
            cfg, raw = synth_session(f)
            out = f.d / "archived" / "x"
            (raw / "ymodem_app.log").unlink()
            with self.assertRaises(ar.Refusal) as cm:
                ar.archive(raw, out, f.boundary, None, HERE / "restore_rejudge.py", root=rr.ROOT)
            self.assertIn("missing ['ymodem_app.log']", str(cm.exception))
            self.assertFalse(out.exists())
            (raw / "ymodem_app.log").write_text(SYNTHETIC)
            (raw / "audits.json").write_text("{}")
            with self.assertRaises(ar.Refusal) as cm:
                ar.archive(raw, out, f.boundary, None, HERE / "restore_rejudge.py", root=rr.ROOT)
            self.assertIn("evidence seal", str(cm.exception))
        finally:
            f.close()

    def test_no_clobber(self):
        f = rt.Fixture("S3", 0, 2)
        try:
            cfg, raw = synth_session(f)
            out = f.d / "archived" / "x"
            out.mkdir(parents=True)
            with self.assertRaises(ar.Refusal) as cm:
                ar.archive(raw, out, f.boundary, None, HERE / "restore_rejudge.py", root=rr.ROOT)
            self.assertIn("already exists", str(cm.exception))
        finally:
            f.close()


class TheQualificationProfile(unittest.TestCase):
    """A B3Q archive goes through the production qualification_session_plan under the same restore."""

    def test_a_synthetic_b3q_session_round_trips(self):
        f = rt.Fixture("S1")
        try:
            cfg, raw = synth_session(f)
            s = archived(f, raw, "b3q")
            res = rejudge(f, s)
            self.assertEqual(res["verdict"], "ACCEPT", res)
            self.assertEqual(res["steps"]["session_plan"]["rebuilt_by"], "b3_runner.qualification_session_plan")
            self.assertEqual(res["steps"]["judge"]["outcome"], "PASS")
        finally:
            f.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
