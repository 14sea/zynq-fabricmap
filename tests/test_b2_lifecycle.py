"""B2 manifest lifecycle, exercised ON DISK in FRESH PROCESSES (docs/b2_preregistration.md
§6/§8; the owner's review of 2026-09-10, fifth finding): S0 init (real carrier lineage
from the B1 manifest) → S1 freeze → S2 qualify (a fake B2Q evidence dir bound to the S1
manifest; a stub re-adjudicator passed in code, never on the CLI) → S3 plan (generated
from the calibration) — then every later change (image, plan, pin, prereg, calibration)
is refused, and the B1 verifier is not touched."""
from __future__ import annotations

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
HOST = R / "host"
GATE = R / "evidence/b2/gate/recomputed_2026_09_10/gate_report.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(code: str, env=None) -> subprocess.CompletedProcess:
    """A fresh interpreter with the host dir on its path."""
    e = dict(os.environ)
    e["PYTHONPATH"] = str(HOST)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=e, cwd=R)


STUB_PASS = "lambda ev, m_run: json.loads((ev / 'adjudication.json').read_text())"


@unittest.skipUnless(GATE.exists(), "no recomputed gate report")
class Lifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="b2life_"))
        cls.manifest = cls.tmp / "b2_manifest.json"
        cls.image_ev = cls.tmp / "build_evidence.json"
        cls.image_ev.write_text(json.dumps({"image": {"path": "firmware/b2/bsp/out/b2_app.bin", "sha256": "ab" * 32, "elf_sha256": "cd" * 32, "bytes": 123456}}))
        cls.prereg_sha = sha(R / "docs/b2_preregistration.md")
        # S0 — real lineage (the B1 chain is re-verified in this call)
        p = run(f"import b2_manifest as m, json; d = m.init({str(cls.image_ev)!r}); open({str(cls.manifest)!r}, 'w').write(m.render(d))")
        assert p.returncode == 0, p.stderr

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _load(self):
        return json.loads(self.manifest.read_text())

    def _verify(self, extra="", evidence_dir=None, stub=True):
        ev = f"evidence_dir={str(evidence_dir)!r}," if evidence_dir else ""
        rj = f"readjudicate={STUB_PASS}," if stub else ""
        return run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); {extra}\n"
                   f"print(json.dumps(m.verify(d, {ev} {rj})))")

    def test_0_init_has_real_lineage_and_no_state(self):
        d = self._load()
        self.assertEqual(d["schema"], "b2_manifest")
        self.assertTrue(d["carrier_lineage"]["b1_chain_verified_now"], d["carrier_lineage"].get("b1_chain"))
        self.assertEqual(d["carrier_lineage"]["bitstream_sha256"], d["carrier"]["bitstream_sha256"])
        self.assertEqual(d["carrier_lineage"]["b1_manifest"]["sha256"], sha(R / "manifests/b1_manifest.json"))
        self.assertEqual(d["map"]["canonical_json_sha256"][:8], "c6a4b23e")
        self.assertEqual(d["map"]["file_sha256"][:8], "b6607a9a")
        self.assertIsNone(d["qualification"]); self.assertFalse(d["qualified"]); self.assertIsNone(d["plan"]); self.assertIsNone(d["calibration"])
        self.assertEqual(d["experiment"]["fitness"], "F1"); self.assertEqual(d["experiment"]["pairs"], 9); self.assertEqual(d["experiment"]["budget_per_arm"], 600)
        self.assertEqual(len(d["seeds"]["pairs"]), 9)
        v = json.loads(self._verify(stub=False).stdout)
        self.assertEqual(v["stage"], "S0"); self.assertFalse(v["qualified"])

    def test_1_qualify_before_freeze_is_refused_and_freeze_works(self):
        ev = self.tmp / "b2q_early"
        ev.mkdir(exist_ok=True)
        shutil.copy(self.manifest, ev / "manifest_at_run.json")
        (ev / "run_log.json").write_text("{}")
        (ev / "adjudication.json").write_text(json.dumps({"outcome": "PASS", "measured_rate_per_hour": 2500.0, "audit_policy": "all-self-reporting"}))
        p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); m.qualify(d, Path({str(ev)!r}), readjudicate={STUB_PASS})")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("unfrozen", p.stderr)
        p = subprocess.run([sys.executable, str(HOST / "b2_manifest.py"), "freeze", "--manifest", str(self.manifest), "--prereg-sha256", self.prereg_sha], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        d = self._load()
        self.assertTrue(d["prereg"]["frozen"]); self.assertTrue(d["image"]["board_ready"])
        self.assertEqual(json.loads(self._verify(stub=False).stdout)["stage"], "S1")

    def test_2_qualify_binds_to_manifest_at_run_and_writes_the_calibration(self):
        ev = self.tmp / "b2q"
        ev.mkdir(exist_ok=True)
        shutil.copy(self.manifest, ev / "manifest_at_run.json")       # the S1 manifest
        (ev / "run_log.json").write_text(json.dumps({"session": "B2Q"}))
        (ev / "adjudication.json").write_text(json.dumps({"outcome": "PASS", "session": "B2Q", "measured_rate_per_hour": 2500.0, "audit_policy": "all-self-reporting"}))
        # the CLI has no re-adjudicator: it must refuse (the B2 adjudicator does not exist yet)
        p = subprocess.run([sys.executable, str(HOST / "b2_manifest.py"), "qualify", "--manifest", str(self.manifest), "--evidence-dir", str(ev)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("re-adjudicator", p.stderr)
        # with a re-adjudicator (in code), the transition is licensed
        p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); "
                f"d2 = m.qualify(d, Path({str(ev)!r}), readjudicate={STUB_PASS}); open({str(self.manifest)!r}, 'w').write(m.render(d2))")
        self.assertEqual(p.returncode, 0, p.stderr)
        d = self._load()
        self.assertTrue(d["qualified"]); self.assertEqual(d["calibration"]["rate_per_hour"], 2500.0)
        self.assertEqual(d["qualification"]["binding"]["b2_manifest_sha256"], sha(ev / "manifest_at_run.json"))
        v = json.loads(self._verify(evidence_dir=ev).stdout)
        self.assertEqual(v["stage"], "S2"); self.assertTrue(v["qualified"], v)
        # without a re-adjudicator a manifest that claims `qualified` is a contradiction: verify raises
        p = self._verify(evidence_dir=ev, stub=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("no B2Q re-adjudicator", p.stderr)
        # a re-adjudicator that does not PASS un-qualifies (raises for the same reason)
        p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); "
                f"m.verify(d, evidence_dir={str(ev)!r}, readjudicate=lambda ev, m_run: {{'outcome': 'HOLD'}})")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("re-adjudicates to 'HOLD'", p.stderr)

    def test_3_plan_from_the_calibration_and_only_that(self):
        d = self._load()
        plan_dir = self.tmp / "plan_undetermined"
        p = subprocess.run([sys.executable, str(HOST / "b2_plan.py"), "--out", str(plan_dir), "--gate-report", str(GATE)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); m.pin_plan(d, Path({str(plan_dir / 'plan.json')!r}))")
        self.assertNotEqual(p.returncode, 0); self.assertIn("DETERMINED", p.stderr)
        plan_dir = self.tmp / "plan_wrong_rate"
        p = subprocess.run([sys.executable, str(HOST / "b2_plan.py"), "--out", str(plan_dir), "--gate-report", str(GATE), "--rate-per-hour", "9999"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); m.pin_plan(d, Path({str(plan_dir / 'plan.json')!r}))")
        self.assertNotEqual(p.returncode, 0); self.assertIn("calibration", p.stderr)
        plan_dir = self.tmp / "plan"
        p = subprocess.run([sys.executable, str(HOST / "b2_plan.py"), "--out", str(plan_dir), "--gate-report", str(GATE), "--rate-per-hour", str(d["calibration"]["rate_per_hour"])], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        plan = json.loads((plan_dir / "plan.json").read_text())
        self.assertEqual(plan["session_split"]["status"], "DETERMINED")
        self.assertEqual(plan["session_split"]["pairs_per_session_max"], 4)        # 2 + 4*1202 = 4810 records at 2500/h = 6926 s <= 7200
        self.assertEqual(len(plan["session_split"]["sessions"]), 3)               # 4 + 4 + 1
        p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); "
                f"d2 = m.pin_plan(d, Path({str(plan_dir / 'plan.json')!r})); open({str(self.manifest)!r}, 'w').write(m.render(d2))")
        self.assertEqual(p.returncode, 0, p.stderr)
        d = self._load()
        self.assertEqual(d["plan"]["sessions"], 3)
        v = json.loads(self._verify(evidence_dir=self.tmp / "b2q").stdout)
        self.assertEqual(v["stage"], "S3"); self.assertTrue(v["qualified"])

    def test_4_later_changes_are_refused(self):
        ev = self.tmp / "b2q"
        cases = {
            "image": "d['image']['sha256'] = 'ef' * 32",
            "prereg": "d['prereg']['sha256'] = '00' * 32",
            "map": "d['map']['canonical_json_sha256'] = '11' * 32",
            "seeds": "d['seeds']['master_seed'] = 42",
            "calibration": "d['calibration']['rate_per_hour'] = 2600.0",
            "lineage": "d['carrier_lineage']['bitstream_sha256'] = '22' * 32",
            "experiment": "d['experiment']['pairs'] = 12",
            "qualified_flag_lie": "d['qualification']['outcome'] = 'HOLD'",
        }
        for name, mutation in cases.items():
            p = self._verify(extra=mutation, evidence_dir=ev)
            self.assertNotEqual(p.returncode, 0, f"{name}: {p.stdout}")
            self.assertIn("Refusal", p.stderr, name)
        # a changed plan file
        d = self._load()
        plan_path = R / d["plan"]["path"] if not Path(d["plan"]["path"]).is_absolute() else Path(d["plan"]["path"])
        original = plan_path.read_text()
        try:
            plan = json.loads(original)
            plan["session_split"]["sessions"] = plan["session_split"]["sessions"][:1]
            plan_path.write_text(json.dumps(plan))
            p = self._verify(evidence_dir=ev)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("plan", p.stderr)
        finally:
            plan_path.write_text(original)
        # a pin drift after the freeze
        p = self._verify(extra="d['pins']['host/b2_search.py'] = '33' * 32", evidence_dir=ev)
        self.assertNotEqual(p.returncode, 0); self.assertIn("pinned files changed", p.stderr)
        # a second freeze / a second plan
        p = run(f"import b2_manifest as m, json; d = json.loads(open({str(self.manifest)!r}).read()); m.freeze(d, 'aa' * 32)")
        self.assertNotEqual(p.returncode, 0); self.assertIn("first transition", p.stderr)
        p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); m.pin_plan(d, Path({str(self.tmp / 'plan' / 'plan.json')!r}))")
        self.assertNotEqual(p.returncode, 0); self.assertIn("already pinned", p.stderr)

    def test_5_b1_verifier_untouched(self):
        p = subprocess.run(["git", "-C", str(R), "diff", "--quiet", "6ac2cf2", "--", "host/b1_qualification.py", "host/b1_manifest.py", "manifests/b1_manifest.json"])
        self.assertEqual(p.returncode, 0, "B1 files changed since 6ac2cf2")


if __name__ == "__main__":
    unittest.main()
