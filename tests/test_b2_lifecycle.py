"""B2 manifest lifecycle, exercised ON DISK in FRESH PROCESSES (docs/b2_preregistration.md
§6/§8; the owner's reviews of 2026-09-10, `docs/b2_b3_host_review_2026_09_10.md` §2 (5) and
`docs/b2_b3_host_review_v02_2026_09_10.md` §2 (1–4)):

S0 init (real carrier lineage from the B1 manifest, re-verified fresh) → S1 freeze → S2
qualify (a fake B2Q evidence dir bound to the S1 manifest; a stub re-adjudicator passed in
code, never on the CLI) → S3 plan (generated from the calibration) — then:
  * every manifest-field change is refused;
  * every FILE-ONLY change with the manifest and evidence untouched is refused, on a
    mirrored tree: a pinned implementation file deleted or changed, the frozen
    preregistration edited, the map edited, the B1 manifest edited;
  * the record and the calibration mutated TOGETHER with the original evidence unchanged,
    a changed policy, an empty file table: refused;
  * a plan with any operational field wrong is refused at pinning AND at re-verification
    with its file hash updated;
  * an infeasible or invalid rate never yields a plan;
  * the B1 verifier is untouched.
Every probe runs `python3 -c` in a fresh interpreter."""
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
STUB_PASS = "lambda ev, m_run: json.loads((ev / 'adjudication.json').read_text())"
ORIGINAL_ADJ = {"outcome": "PASS", "session": "B2Q", "measured_rate_per_hour": 2500.0, "audit_policy": "all-self-reporting"}
FIXED_STUB = f"lambda ev, m_run: {ORIGINAL_ADJ!r}"          # the review's test double: always the ORIGINAL evidence-derived answer


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(code: str) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    e["PYTHONPATH"] = str(HOST)
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=e, cwd=R)


def refused(p: subprocess.CompletedProcess, needle: str = "Refusal") -> bool:
    return p.returncode != 0 and needle in p.stderr


@unittest.skipUnless(GATE.exists(), "no recomputed gate report")
class Lifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="b2life_"))
        cls.manifest = cls.tmp / "b2_manifest.json"
        cls.image_ev = cls.tmp / "build_evidence.json"
        cls.image_ev.write_text(json.dumps({"image": {"path": "firmware/b2/bsp/out/b2_app.bin", "sha256": "ab" * 32, "elf_sha256": "cd" * 32, "bytes": 123456}}))
        cls.prereg_sha = sha(R / "docs/b2_preregistration.md")
        p = run(f"import b2_manifest as m, json; d = m.init({str(cls.image_ev)!r}); open({str(cls.manifest)!r}, 'w').write(m.render(d))")
        assert p.returncode == 0, p.stderr
        cls.ev = cls.tmp / "b2q"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _load(self):
        return json.loads(self.manifest.read_text())

    def _verify(self, extra="", evidence_dir=None, stub=STUB_PASS, root=None, manifest=None):
        ev = f"evidence_dir={str(evidence_dir)!r}," if evidence_dir else ""
        rj = f"readjudicate={stub}," if stub else ""
        rt = f"root=Path({str(root)!r})," if root else ""
        man = str(manifest or self.manifest)
        return run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({man!r}).read()); {extra}\n"
                   f"print(json.dumps(m.verify(d, {ev} {rj} {rt})))")

    def _make_evidence(self, ev: Path, adj=ORIGINAL_ADJ):
        ev.mkdir(exist_ok=True)
        shutil.copy(self.manifest, ev / "manifest_at_run.json")
        (ev / "run_log.json").write_text(json.dumps({"session": "B2Q"}))
        (ev / "adjudication.json").write_text(json.dumps(adj))

    # ------------------------------------------------------------ S0, S1

    def test_0_init_has_lineage_and_no_state(self):
        d = self._load()
        self.assertEqual(d["schema"], "b2_manifest")
        self.assertNotIn("b1_chain_verified_now", d["carrier_lineage"])          # no stored flag: verify re-runs the chain
        self.assertEqual(d["carrier_lineage"]["bitstream_sha256"], d["carrier"]["bitstream_sha256"])
        self.assertEqual(d["carrier_lineage"]["b1_manifest"]["sha256"], sha(R / "manifests/b1_manifest.json"))
        self.assertEqual(d["map"]["canonical_json_sha256"][:8], "c6a4b23e")
        self.assertEqual(d["map"]["file_sha256"][:8], "b6607a9a")
        self.assertIsNone(d["qualification"]); self.assertFalse(d["qualified"]); self.assertIsNone(d["plan"]); self.assertIsNone(d["calibration"])
        self.assertEqual((d["experiment"]["fitness"], d["experiment"]["pairs"], d["experiment"]["budget_per_arm"]), ("F1", 9, 600))
        self.assertEqual(sorted(d["pins"]), sorted(["host/b2_landscape.py", "host/b2_maps.py", "host/b2_search.py", "host/b2_gate.py", "host/b2_plan.py",
                                                    "host/b2_manifest.py", "schemas/self_map_v2.schema.json", "docs/b2_architecture.md"]))
        v = json.loads(self._verify(stub=None).stdout)
        self.assertEqual(v["stage"], "S0"); self.assertFalse(v["qualified"]); self.assertEqual(v["checks"]["lineage"], "ok (B1 chain re-verified)")

    def test_1_freeze(self):
        self._make_evidence(self.tmp / "b2q_early")
        p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); m.qualify(d, Path({str(self.tmp / 'b2q_early')!r}), readjudicate={STUB_PASS})")
        self.assertTrue(refused(p)); self.assertIn("unfrozen", p.stderr)
        p = subprocess.run([sys.executable, str(HOST / "b2_manifest.py"), "freeze", "--manifest", str(self.manifest), "--prereg-sha256", "00" * 32], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2); self.assertIn("not the hash of the preregistration", p.stderr)
        p = subprocess.run([sys.executable, str(HOST / "b2_manifest.py"), "freeze", "--manifest", str(self.manifest), "--prereg-sha256", self.prereg_sha], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        d = self._load()
        self.assertTrue(d["prereg"]["frozen"]); self.assertTrue(d["image"]["board_ready"])
        self.assertEqual(json.loads(self._verify(stub=None).stdout)["stage"], "S1")

    # ------------------------------------------------------------ S2

    def test_2_qualify_reconstructs_the_record_and_the_calibration(self):
        self._make_evidence(self.ev)
        p = subprocess.run([sys.executable, str(HOST / "b2_manifest.py"), "qualify", "--manifest", str(self.manifest), "--evidence-dir", str(self.ev)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2); self.assertIn("re-adjudicator", p.stderr)          # the CLI has none: refuses
        p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); "
                f"d2 = m.qualify(d, Path({str(self.ev)!r}), readjudicate={STUB_PASS}); open({str(self.manifest)!r}, 'w').write(m.render(d2))")
        self.assertEqual(p.returncode, 0, p.stderr)
        d = self._load()
        self.assertTrue(d["qualified"])
        self.assertEqual(d["calibration"]["rate_per_hour"], 2500.0)
        self.assertEqual(d["calibration"]["audit_policy"], "all-self-reporting")
        self.assertEqual((d["calibration"]["sessions"], d["calibration"]["pairs_per_session_max"]), (3, 4))
        self.assertEqual(sorted(d["qualification"]["files"]), ["adjudication.json", "manifest_at_run.json", "run_log.json"])
        self.assertEqual(d["qualification"]["binding"]["b2_manifest_sha256"], sha(self.ev / "manifest_at_run.json"))
        v = json.loads(self._verify(evidence_dir=self.ev).stdout)
        self.assertEqual(v["stage"], "S2"); self.assertTrue(v["qualified"], v)
        v = json.loads(self._verify(evidence_dir=self.ev, stub=FIXED_STUB).stdout)
        self.assertTrue(v["qualified"])
        # no re-adjudicator, or one that does not agree, is a contradiction with the flag
        for stub, needle in ((None, "no B2Q re-adjudicator"), ("lambda ev, m_run: {'outcome': 'HOLD'}", "re-adjudicates to 'HOLD'"),
                             ("lambda ev, m_run: {'outcome': 'PASS', 'measured_rate_per_hour': 2600.0, 'audit_policy': 'all-self-reporting'}", "disagree with the evidence"),
                             ("lambda ev, m_run: {'outcome': 'PASS', 'measured_rate_per_hour': 2500.0, 'audit_policy': 'sampled'}", "disagree with the evidence")):
            p = self._verify(evidence_dir=self.ev, stub=stub)
            self.assertTrue(refused(p), (stub, p.stdout, p.stderr)); self.assertIn(needle, p.stderr)

    def test_2a_record_and_calibration_mutated_together_are_refused(self):
        """Review v02 finding 2: the evidence still says 2 500 / all-self-reporting; the fixed
        double still answers the original — a co-mutation of the record and the calibration,
        a policy change, an empty file table, must each be refused."""
        cases = {
            "rate_100000": "d['calibration']['rate_per_hour'] = 100000.0; d['qualification']['measured_rate_per_hour'] = 100000.0; d['calibration'].update(sessions=1, pairs_per_session_max=9)",
            "rate_100000_partial": "d['calibration']['rate_per_hour'] = 100000.0; d['qualification']['measured_rate_per_hour'] = 100000.0",
            "policy_sampled": "d['calibration']['audit_policy'] = 'sampled'; d['qualification']['audit_policy'] = 'sampled'",
            "empty_files": "d['qualification']['files'] = {}",
            "missing_file_entry": "d['qualification']['files'].pop('run_log.json')",
            "extra_file_entry": "d['qualification']['files']['extra.json'] = '00' * 32",
            "outcome_lie": "d['qualification']['outcome'] = 'HOLD'",
            "binding_extra_key": "d['qualification']['binding']['x'] = 1",
            "schema_version": "d['qualification']['schema_version'] = '1.0.0'",
            "calibration_sessions": "d['calibration']['sessions'] = 2",
        }
        for name, mutation in cases.items():
            for stub in (STUB_PASS, FIXED_STUB):
                p = self._verify(extra=mutation, evidence_dir=self.ev, stub=stub)
                self.assertTrue(refused(p), (name, stub, p.stdout, p.stderr))

    def test_2b_manifest_field_changes_are_refused(self):
        cases = {
            "image": "d['image']['sha256'] = 'ef' * 32",
            "prereg": "d['prereg']['sha256'] = '00' * 32",
            "map": "d['map']['canonical_json_sha256'] = '11' * 32",
            "map_file_digest": "d['map']['file_sha256'] = '11' * 32",
            "seeds": "d['seeds']['master_seed'] = 42",
            "seed_pairs": "d['seeds']['pairs'][0] = [1, 2]",
            "lineage": "d['carrier_lineage']['bitstream_sha256'] = '22' * 32",
            "lineage_b1_hash": "d['carrier_lineage']['b1_manifest']['sha256'] = '22' * 32",
            "experiment": "d['experiment']['pairs'] = 12",
            "engine": "d['experiment']['engine']['mu'] = 5",
            "audit_policy": "d['audit']['policy'] = 'sampled'",
            "pin_value": "d['pins']['host/b2_search.py'] = '33' * 32",
            "pin_removed": "d['pins'].pop('host/b2_gate.py')",
            "qualified_flag_off": "d['qualified'] = False",
            "calibration_removed": "d['calibration'] = None",
        }
        for name, mutation in cases.items():
            p = self._verify(extra=mutation, evidence_dir=self.ev)
            self.assertTrue(refused(p), (name, p.stdout, p.stderr))

    def test_2c_file_only_changes_are_refused_on_a_mirrored_tree(self):
        """Review v02 finding 1: the manifest and the evidence untouched; only files change."""
        d = self._load()
        mirror = self.tmp / "mirror"
        rels = list(d["pins"]) + [d["carrier_lineage"]["b1_manifest"]["path"], d["prereg"]["path"], d["map"]["path"]]
        for rel in rels:
            dest = mirror / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(R / rel, dest)
        v = json.loads(self._verify(evidence_dir=self.ev, root=mirror).stdout)      # the faithful mirror verifies
        self.assertTrue(v["qualified"], v)
        cases = [("delete_pinned_search", "host/b2_search.py", "delete", "absent"),
                 ("delete_pinned_architecture", "docs/b2_architecture.md", "delete", "absent"),
                 ("change_pinned_gate", "host/b2_gate.py", "append", "changed"),
                 ("change_prereg", d["prereg"]["path"], "append", "preregistration"),
                 ("change_map_bytes", d["map"]["path"], "append", "map"),
                 ("change_b1_manifest", d["carrier_lineage"]["b1_manifest"]["path"], "append", "B1 manifest")]
        for name, rel, how, needle in cases:
            p = mirror / rel
            original = p.read_bytes()
            try:
                if how == "delete":
                    p.unlink()
                else:
                    p.write_bytes(original + b"\n ")
                r = self._verify(evidence_dir=self.ev, root=mirror)
                self.assertTrue(refused(r), (name, r.stdout, r.stderr)); self.assertIn(needle, r.stderr, name)
            finally:
                p.write_bytes(original)
        # the map re-encoded with the same canonical content but different bytes: the file digest catches it
        mp = mirror / d["map"]["path"]
        original = mp.read_bytes()
        try:
            mp.write_text(json.dumps(json.loads(original), indent=2))
            r = self._verify(evidence_dir=self.ev, root=mirror)
            self.assertTrue(refused(r)); self.assertIn("map file bytes", r.stderr)
        finally:
            mp.write_bytes(original)
        # the build evidence file changed
        be = self.image_ev
        original = be.read_bytes()
        try:
            be.write_bytes(original + b" ")
            r = self._verify(evidence_dir=self.ev, root=mirror)
            self.assertTrue(refused(r)); self.assertIn("build evidence", r.stderr)
        finally:
            be.write_bytes(original)

    # ------------------------------------------------------------ S3

    def _plan(self, name: str, rate, mutate: str = "") -> Path:
        plan_dir = self.tmp / name
        args = [sys.executable, str(HOST / "b2_plan.py"), "--out", str(plan_dir), "--gate-report", str(GATE)]
        if rate is not None:
            args += ["--rate-per-hour", str(rate)]
        p = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        if mutate:
            pp = plan_dir / "plan.json"
            plan = json.loads(pp.read_text())
            exec(mutate, {"plan": plan, "json": json})
            pp.write_text(json.dumps(plan))
        return plan_dir / "plan.json"

    def _pin(self, plan_path: Path, save: bool = False) -> subprocess.CompletedProcess:
        tail = f"open({str(self.manifest)!r}, 'w').write(m.render(d2))" if save else "pass"
        return run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); "
                   f"d2 = m.pin_plan(d, Path({str(plan_path)!r}), readjudicate={STUB_PASS}); {tail}")

    def test_3_plan_only_from_the_calibration(self):
        self.assertTrue(refused(self._pin(self._plan("plan_undetermined", None))))
        self.assertTrue(refused(self._pin(self._plan("plan_wrong_rate", 9999))))
        d = self._load()
        rate = d["calibration"]["rate_per_hour"]
        wrong = {
            "map_digest": "plan['map']['sha256'] = '00' * 32",
            "map_path": "plan['map']['path'] = 'evidence/other.json'",
            "engine_mu": "plan['engine']['mu'] = 999",
            "engine_version": "plan['engine']['version'] = 'b2-es-v2'",
            "audit_policy": "plan['audit_policy'] = 'sampled'",
            "prediction_digest": "plan['prediction_sha256'] = '00' * 32",
            "master_seed": "plan['seed_derivation']['master_seed'] = 42",
            "label": "plan['seed_derivation']['label'] = 'b2-other'",
            "pairs": "plan['pairs'] = 12",
            "budget": "plan['budget_per_arm'] = 601",
            "fitness": "plan['fitness'] = 'F2'",
            "split_sessions": "plan['session_split']['sessions'] = plan['session_split']['sessions'][:1]",
            "split_status": "plan['session_split']['status'] = 'INFEASIBLE'",
            "span_limit": "plan['session_span_max_s'] = 99999",
            "schema": "plan['schema'] = 'other'",
        }
        for name, mutation in wrong.items():
            p = self._pin(self._plan("plan_wrong_" + name, rate, mutation))
            self.assertTrue(refused(p), (name, p.stdout, p.stderr)); self.assertIn("plan:", p.stderr, name)
        # a wrong prediction FILE beside a correct plan (its digest updated in the plan): re-derivation catches it
        good = self._plan("plan_bad_prediction", rate)
        pred = good.parent / "prediction.json"
        doc = json.loads(pred.read_text()); doc["deltas"][0] += 1
        pred.write_text(json.dumps(doc))
        plan = json.loads(good.read_text()); plan["prediction_sha256"] = sha(pred); good.write_text(json.dumps(plan))
        p = self._pin(good)
        self.assertTrue(refused(p)); self.assertIn("reference engine", p.stderr)
        # the good plan pins; the unqualified manifest cannot pin
        good = self._plan("plan", rate)
        p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(self.manifest)!r}).read()); d['qualified'] = False; d['qualification'] = None; d['calibration'] = None; m.pin_plan(d, Path({str(good)!r}), readjudicate={STUB_PASS})")
        self.assertTrue(refused(p)); self.assertIn("not qualified", p.stderr)
        p = self._pin(good, save=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        d = self._load()
        self.assertEqual(d["plan"]["sessions"], 3); self.assertEqual(d["plan"]["total_records"], 3 * 2 + 9 * 1202)
        v = json.loads(self._verify(evidence_dir=self.ev).stdout)
        self.assertEqual(v["stage"], "S3"); self.assertTrue(v["qualified"])

    def test_4_reverification_catches_a_rehashed_changed_plan(self):
        """Review v02 finding 3, second probe: the pinned plan file changed AND its recorded
        hash updated (before any ruling): re-verification must still refuse."""
        d = self._load()
        plan_path = Path(d["plan"]["path"]) if Path(d["plan"]["path"]).is_absolute() else R / d["plan"]["path"]
        original = plan_path.read_text()
        for name, mutation in (("master_seed", "plan['seed_derivation']['master_seed'] = 42"), ("map", "plan['map']['sha256'] = '00' * 32"),
                               ("audit_policy", "plan['audit_policy'] = 'sampled'"), ("engine", "plan['engine']['lambda'] = 16"),
                               ("split", "plan['session_split']['sessions'] = plan['session_split']['sessions'][:1]"),
                               ("prediction_digest", "plan['prediction_sha256'] = '00' * 32")):
            try:
                plan = json.loads(original)
                exec(mutation, {"plan": plan})
                plan_path.write_text(json.dumps(plan))
                r = self._verify(extra=f"d['plan']['sha256'] = m.sha256_file(Path({str(plan_path)!r}))", evidence_dir=self.ev)
                self.assertTrue(refused(r), (name, r.stdout, r.stderr)); self.assertIn("S3", r.stderr)
            finally:
                plan_path.write_text(original)
        # the plan file changed without updating the hash
        try:
            plan_path.write_text(original + " ")
            r = self._verify(evidence_dir=self.ev)
            self.assertTrue(refused(r)); self.assertIn("plan file", r.stderr)
        finally:
            plan_path.write_text(original)
        # the prediction file changed (hash kept)
        pred = plan_path.parent / "prediction.json"
        original_pred = pred.read_text()
        try:
            pred.write_text(original_pred + " ")
            r = self._verify(evidence_dir=self.ev)
            self.assertTrue(refused(r)); self.assertIn("prediction file", r.stderr)
        finally:
            pred.write_text(original_pred)
        # a second freeze / a second plan
        p = run(f"import b2_manifest as m, json; d = json.loads(open({str(self.manifest)!r}).read()); m.freeze(d, 'aa' * 32)")
        self.assertTrue(refused(p)); self.assertIn("first transition", p.stderr)
        p = self._pin(plan_path)
        self.assertTrue(refused(p)); self.assertIn("already pinned", p.stderr)

    def test_5_infeasible_rate_never_qualifies(self):
        """Review v02 finding 4: a rate under which not even one pair fits, or an invalid rate,
        is refused when the calibration is accepted."""
        s1 = self.ev / "manifest_at_run.json"
        for tag, adj_text, needle in (("100", json.dumps(dict(ORIGINAL_ADJ, measured_rate_per_hour=100.0)), "INFEASIBLE"),
                                      ("601", json.dumps(dict(ORIGINAL_ADJ, measured_rate_per_hour=601.0)), "INFEASIBLE"),
                                      ("0", json.dumps(dict(ORIGINAL_ADJ, measured_rate_per_hour=0)), "finite positive"),
                                      ("neg", json.dumps(dict(ORIGINAL_ADJ, measured_rate_per_hour=-1)), "finite positive"),
                                      ("inf", json.dumps(dict(ORIGINAL_ADJ, measured_rate_per_hour=1)).replace('"measured_rate_per_hour": 1', '"measured_rate_per_hour": 1e999'), "finite positive"),
                                      ("nan", json.dumps(dict(ORIGINAL_ADJ, measured_rate_per_hour=1)).replace('"measured_rate_per_hour": 1', '"measured_rate_per_hour": NaN'), "finite positive"),
                                      ("string", json.dumps(dict(ORIGINAL_ADJ, measured_rate_per_hour="2500")), "finite positive"),
                                      ("bool", json.dumps(dict(ORIGINAL_ADJ, measured_rate_per_hour=True)), "finite positive")):
            ev = self.tmp / f"b2q_rate_{tag}"
            ev.mkdir(exist_ok=True)
            shutil.copy(s1, ev / "manifest_at_run.json")
            (ev / "run_log.json").write_text(json.dumps({"session": "B2Q"}))
            (ev / "adjudication.json").write_text(adj_text)
            p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(s1)!r}).read()); "
                    f"m.qualify(d, Path({str(ev)!r}), readjudicate={STUB_PASS})")
            self.assertTrue(refused(p), (tag, p.stdout, p.stderr)); self.assertIn(needle, p.stderr, tag)
        # the exact boundary: 602 records/h fits one pair (1 204 records in 7 200 s)
        ev = self.tmp / "b2q_rate_602"
        ev.mkdir(exist_ok=True)
        shutil.copy(s1, ev / "manifest_at_run.json")
        (ev / "run_log.json").write_text(json.dumps({"session": "B2Q"}))
        (ev / "adjudication.json").write_text(json.dumps(dict(ORIGINAL_ADJ, measured_rate_per_hour=602.0)))
        p = run(f"import b2_manifest as m, json; from pathlib import Path; d = json.loads(open({str(s1)!r}).read()); "
                f"d2 = m.qualify(d, Path({str(ev)!r}), readjudicate={STUB_PASS}); print(d2['calibration']['sessions'], d2['calibration']['pairs_per_session_max'])")
        self.assertEqual(p.returncode, 0, p.stderr); self.assertEqual(p.stdout.split(), ["9", "1"])

    def test_6_b1_verifier_untouched(self):
        p = subprocess.run(["git", "-C", str(R), "diff", "--quiet", "6ac2cf2", "--", "host/b1_qualification.py", "host/b1_manifest.py", "manifests/b1_manifest.json",
                            "host/b1q_adjudicate.py", "manifests/b1_instrument_pins.json"])
        self.assertEqual(p.returncode, 0, "B1 files changed since 6ac2cf2")


if __name__ == "__main__":
    unittest.main()
