"""The complete offline B2Q lifecycle: a MODELLED session through the instrument's real host
stack and the production exporter, judged by the runner's own verdict, then S1 → B2Q → S2 → S3
and a FRESH-PROCESS verification — with no replay double and no stored-verdict double anywhere
on the positive path (the owner's standing acceptance requirement).

The model stands in for a board. Nothing here is silicon evidence, a session, or a qualification;
the rulings are inert modelled documents that authorise nothing. What it establishes is that the
checks this batch added can be SATISFIED, not only failed — the positive control every negative
case above it was missing.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
sys.path.insert(0, str(R / "tests"))
import b2_manifest as bman  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_runner as rn  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402
from test_b2_runner import HAVE, Fixture  # noqa: E402


@unittest.skipUnless(HAVE, "the built B2 image or its build evidence is absent")
class ModelledB2Q(unittest.TestCase):
    """One modelled session, driven once; every case works on its own copy of the evidence."""

    @classmethod
    def setUpClass(cls):
        import b2_modelled_session as ms
        cls.ms = ms
        ms.bind_instrument(False)
        cls.f = Fixture("S1")
        cls.manifest_path = cls.f.path()
        cls.manifest_sha = hashlib.sha256(cls.manifest_path.read_bytes()).hexdigest()
        cls.plan = rn.qualification_session_plan(cls.f.manifest, cls.manifest_sha)
        cls.seeds = rn.qualification_seeds(cls.f.manifest)
        cls.docs = rn.qualification_documents(cls.f.manifest)
        cls.source = Path(tempfile.mkdtemp(prefix="b2q_e2e_"))
        cls.session = ms.run_modelled(cls.f.manifest, cls.manifest_sha, cls.plan, cls.seeds, cls.source)
        verdict = cls.judge_dir(cls.source)
        ms.finalize(cls.source, verdict, cls.session["summary"], cls.session["rulings"])
        cls.verdict = verdict

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.source, ignore_errors=True)
        cls.f.close()

    @classmethod
    def judge_dir(cls, d: Path, plan=None) -> dict:
        qplan, qpred, qseeds = cls.docs
        return rn.judge_session(d, cls.f.manifest, plan or cls.plan, qplan, qpred, qseeds, inst.DEFAULT_ROOT)

    def _copy(self) -> Path:
        d = Path(tempfile.mkdtemp(prefix="b2q_case_", dir=self.source.parent))
        shutil.rmtree(d)
        shutil.copytree(self.source, d)
        self.addCleanup(shutil.rmtree, d, True)
        return d

    @staticmethod
    def _reseal(d: Path) -> None:
        """Re-hash the export seal so a case tests what it means to test and not the seal."""
        doc = json.loads((d / "exports.json").read_text())
        for name, entry in doc["files"].items():
            p = d / name
            entry["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
            entry["bytes"] = p.stat().st_size
        (d / "exports.json").write_text(json.dumps(doc, indent=1))

    # ---------------------------------------------------------------- the positive control
    def test_the_session_completed_through_the_production_exporter(self):
        self.assertEqual(self.session["epoch_end"]["kind"], "COMPLETED")
        self.assertEqual(self.session["records"], self.plan["expected_records"])
        self.assertTrue(all(v == "ok" for v in self.session["exports"].values()), self.session["exports"])
        for name in ("run_log.json", "audits.json", "timeline.json", "exports.json", "console.log",
                     "console.ts.log", bman.MANIFEST_AT_RUN, "ruling_whole_of_run.json",
                     "ruling_provisioning.json", "summary.json", "adjudication.json"):
            self.assertTrue((self.source / name).is_file(), name)

    def test_the_runners_own_verdict_is_a_pass(self):
        self.assertEqual(self.verdict["outcome"], "PASS", self.verdict["findings"][:6])
        self.assertEqual(self.verdict["session"], bman.QUAL_SESSION)
        self.assertTrue(self.verdict["binding_checked"])
        self.assertEqual(self.verdict["kills"], [])
        self.assertEqual(self.verdict["audit_policy"], bp.AUDIT_POLICY)
        self.assertGreater(self.verdict["measured_rate_per_hour"], 0)

    def test_the_whole_lifecycle_and_a_fresh_process_verification(self):
        m2 = json.loads(bman.render(bman.qualify(self.f.manifest, self.source,
                                                 readjudicate=rn.readjudicator(self.f.manifest))))
        self.assertTrue(m2["qualified"])
        self.assertEqual(m2["calibration"]["rate_per_hour"], self.verdict["measured_rate_per_hour"])
        self.assertEqual(m2["calibration"]["audit_policy"], bp.AUDIT_POLICY)
        self.assertEqual(sorted(m2["qualification"]["files"]), sorted(bman.QUAL_EVIDENCE_FILES))

        d = Path(tempfile.mkdtemp(prefix="b2plan_"))
        self.addCleanup(shutil.rmtree, d, True)
        plan = bp.build_plan(m2["calibration"]["rate_per_hour"])
        prediction = bp.build_prediction(plan["fitness"], plan["budget_per_arm"],
                                         [tuple(x) for x in m2["seeds"]["pairs"]],
                                         m2["map"]["canonical_json_sha256"])
        plan_path, _ = bp.write(d, plan, prediction)
        m3 = json.loads(bman.render(bman.pin_plan(m2, plan_path, readjudicate=rn.readjudicator(m2))))
        self.assertIsNotNone(m3["plan"])

        mp = d / "b2_manifest.json"
        mp.write_text(bman.render(m3))
        env = dict(os.environ, PYTHONPATH=str(R / "host"))
        code = (f"import json,sys; sys.path.insert(0,{str(R / 'host')!r});"
                f"import b2_manifest as m, b2_runner as rn;"
                f"d=json.loads(open({str(mp)!r}).read());"
                f"print(json.dumps(m.verify(d, readjudicate=rn.readjudicator(d))))")
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=R)
        self.assertEqual(p.returncode, 0, p.stderr[-600:])
        out = json.loads(p.stdout)
        self.assertEqual(out["stage"], "S3")
        self.assertTrue(out["qualified"])
        self.assertEqual(out["checks"]["board"], bman.check_board(self.f.manifest))

    def test_the_command_line_judges_and_finalises(self):
        """The CLI exported and stopped: no adjudication, no final summary, no verdict, exit 0
        (the owner's P3 of 2026-09-12). It now runs the whole thing."""
        out = Path(tempfile.mkdtemp(prefix="b2q_cli_")) / "evidence"
        self.addCleanup(shutil.rmtree, out.parent, True)
        env = dict(os.environ, PYTHONPATH=str(R / "host"))
        p = subprocess.run([sys.executable, str(R / "host/b2_modelled_session.py"),
                            "--out", str(out), "--manifest", str(self.manifest_path)],
                           capture_output=True, text=True, env=env, cwd=R)
        self.assertEqual(p.returncode, 0, p.stderr[-600:])
        doc = json.loads(p.stdout)
        self.assertEqual(doc["verdict"]["outcome"], "PASS", doc["verdict"]["findings"][:4])
        for name in ("adjudication.json", "summary.json"):
            self.assertTrue((out / name).is_file(), f"the CLI left no {name}")
        final = json.loads((out / "summary.json").read_text())
        self.assertEqual(final["outcome"], "PASS")
        self.assertIn("provisioning_ruling_sha256", final)

    # ---------------------------------------------------------------- the negatives, on a PASS
    def test_a_relabelled_epoch_is_refused(self):
        d = self._copy()
        log = json.loads((d / "run_log.json").read_text())
        log["session_summary"]["epoch_end"]["kind"] = "STOPPED"
        (d / "run_log.json").write_text(json.dumps(log))
        self._reseal(d)
        res = self.judge_dir(d)
        self.assertNotEqual(res["outcome"], "PASS")

    def test_a_short_epoch_is_refused(self):
        d = self._copy()
        log = json.loads((d / "run_log.json").read_text())
        log["session_summary"]["epoch_end"]["last_seq"] -= 1
        (d / "run_log.json").write_text(json.dumps(log))
        self._reseal(d)
        res = self.judge_dir(d)
        self.assertTrue(any("the epoch ended at seq" in x for x in res["findings"]), res["findings"][:4])

    def test_a_record_that_was_not_audited_is_refused(self):
        d = self._copy()
        log = json.loads((d / "run_log.json").read_text())
        next(r for r in log["loop_records"] if r.get("verified") == "audited")["verified"] = "replayed-only"
        (d / "run_log.json").write_text(json.dumps(log))
        self._reseal(d)
        res = self.judge_dir(d)
        self.assertNotEqual(res["outcome"], "PASS")

    def test_a_broken_seal_is_refused(self):
        d = self._copy()
        (d / "console.log").write_text((d / "console.log").read_text() + "one more line\n")
        res = self.judge_dir(d)
        self.assertTrue(any("evidence seal" in x for x in res["findings"]), res["findings"][:4])

    def test_a_changed_binding_is_refused(self):
        d = self._copy()
        log = json.loads((d / "run_log.json").read_text())
        log["l6"]["binding"]["image_sha256"] = "0" * 64
        (d / "run_log.json").write_text(json.dumps(log))
        self._reseal(d)
        res = self.judge_dir(d)
        self.assertTrue(any("binding: the log's image_sha256" in x for x in res["findings"]), res["findings"][:4])

    def test_a_wrong_identity_carrier_is_refused(self):
        d = self._copy()
        log = json.loads((d / "run_log.json").read_text())
        log["app_identity"]["carrier_sha256"] = "0" * 64
        (d / "run_log.json").write_text(json.dumps(log))
        self._reseal(d)
        res = self.judge_dir(d)
        self.assertTrue(any("IDENT carrier_sha256" in x for x in res["findings"]), res["findings"][:4])

    def test_an_over_deadline_session_is_refused(self):
        d = self._copy()
        tight = dict(self.plan, session_timeout_s=0.001)
        res = self.judge_dir(d, plan=tight)
        self.assertTrue(any("deadline this session was authorised for" in x for x in res["findings"]),
                        res["findings"][:4])

    def test_a_tampered_readout_is_a_kill(self):
        d = self._copy()
        log = json.loads((d / "run_log.json").read_text())
        rec = next(r for r in log["loop_records"] if isinstance(r.get("search"), dict)
                   and r["search"]["holdout"] is None)
        words = rec["evidence"]["score"]["functional_readout"]
        words[2] = "%016x" % (int(words[2], 16) ^ 0xFF)
        (d / "run_log.json").write_text(json.dumps(log))
        self._reseal(d)
        res = self.judge_dir(d)
        self.assertTrue(res["outcome"].startswith("KILL"), res["outcome"][:160])

    def test_an_archived_ruling_naming_another_board_is_refused(self):
        d = self._copy()
        import b1_qualification as bq
        raw, body = bq.read_archived_ruling(d / bq.RULING_FILES["whole_of_run"])
        body["boardid"] = "FFFF"
        (d / bq.RULING_FILES["whole_of_run"]).write_text(
            json.dumps(bq.archive_envelope(json.dumps(body).encode())))
        res = self.judge_dir(d)
        self.assertTrue(any("names board" in x for x in res["findings"]), res["findings"][:4])

    def test_a_tampered_calibration_is_refused_by_the_lifecycle(self):
        m2 = bman.qualify(self.f.manifest, self.source, readjudicate=rn.readjudicator(self.f.manifest))
        m2 = json.loads(bman.render(m2))
        m2["calibration"]["rate_per_hour"] = m2["calibration"]["rate_per_hour"] * 2
        with self.assertRaises(bman.Refusal) as cm:
            bman.verify(m2, readjudicate=rn.readjudicator(m2))
        self.assertIn("calibration", str(cm.exception))

    def test_a_changed_evidence_file_is_refused_by_the_lifecycle(self):
        m2 = json.loads(bman.render(bman.qualify(self.f.manifest, self.source,
                                                 readjudicate=rn.readjudicator(self.f.manifest))))
        d = self._copy()
        (d / "timeline.json").write_text((d / "timeline.json").read_text() + " ")
        m2["qualification"]["evidence_dir"] = str(d)
        with self.assertRaises(bman.Refusal) as cm:
            bman.verify(m2, readjudicate=rn.readjudicator(m2))
        self.assertTrue(str(cm.exception))


if __name__ == "__main__":
    unittest.main()
