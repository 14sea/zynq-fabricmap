"""b4/host/b4_gonogo.py — the engineering go / no-go policy (docs/b4_architecture.md section 9.4; the owner's choice 5 of 2026-10-20) on
SYNTHETIC reports and a HERMETIC fixture batch only: the precondition (S = 32, every pair complete, else NO DECISION); statistic 1
(Omega − R at B = 64: positives > negatives and the one-sided sign-test p ≤ 0.20); statistic 2 (the seven judged conditional K9
medians ≥ 0.50); a go, a no-go on each failing condition, the boundaries; every budget carried, no other budget picked; the record
written for a fixture batch with formal = false, verified in process and by the CLI in a fresh process; refusals (a gate label, a
missing report, an archive of another version); NO PRODUCTION SET IS DERIVED (the guards of test_b4_sim). No skip."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "b4/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_gonogo as gg  # noqa: E402
import b4_k9 as k9  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim as sim  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_thresholds as th  # noqa: E402
from test_b4_gate import synthetic_summary  # noqa: E402
from test_b4_sim import SCHED1, build_hermetic, git, production_derivation_reached  # noqa: E402

GRID = th.GRID


def report(summary: dict | None, S=32, status="complete", label="b4-sim-9", fixture=False, pairs_complete=True) -> dict:
    plan = [{"pair": r, "landscape_seed": 100 + r, "operator_seed": 200 + r, "status": "complete" if pairs_complete else "partial", "task": "complete", "task_prefix": 4, "task_quarantine": None,
             "arms": {x: "audited" for x in sc.ROLES}, "k7": "complete", "k9": "complete", "k10": "complete"} for r in range(S)]
    return {"status": status, "label": label, "fixture": fixture, "count": S, "pairs": plan, "summary": summary, "head": "0" * 40, "generated_utc": "x"}


def syn(S=32, om=(8.0, 25, 4, 3), k9_medians=None, **kw) -> dict:
    """A coherent synthetic summary with Omega − R's counts given for S = 32 (positives, negatives, ties)."""
    return synthetic_summary(S=S, N=16, om=om, k9_medians=k9_medians, **kw)


class ThePolicy(unittest.TestCase):
    def test_a_go_on_the_policy_and_every_budget_carried(self):
        s = syn()
        self.assertEqual(sc.canonical(gg.POLICY), sc.canonical(th.THRESHOLDS["gonogo"]))
        d = gg.decide(report(s))
        self.assertEqual(d["decision"], "go", d["reason"]); self.assertTrue(d["formal"]); self.assertEqual(d["formal_reasons"], [])
        st1 = d["statistic_1"]
        self.assertEqual((st1["budget"], st1["positives"], st1["negatives"], st1["ties"], st1["p_max_go"]), (64, 25, 4, 3, 0.20))
        self.assertEqual(st1["sign_test_p"], s["per_budget"]["64"]["deltas"]["Omega_minus_R"]["sign_test_p"]); self.assertTrue(st1["positives_gt_negatives"] and st1["p_le_p_max_go"])
        self.assertNotIn("alpha_go", st1); self.assertIn("not the alpha", st1["p_max_go_standing"]); self.assertIn("not an alpha", d["reason"])
        self.assertEqual(d["statistic_2"]["judged_estimand"], k9.JUDGED_ESTIMAND); self.assertTrue(d["statistic_2"]["all_ge_min"])
        self.assertEqual(set(d["omega_minus_R_by_budget"]), {str(B) for B in GRID}, "every budget's record carried; none picked afterwards")
        self.assertIn("not a gate result", d["reason"]); self.assertIn("not an authorisation", d["reason"])
        self.assertEqual(d["precondition"], {"status_complete": True, "S_is_32": True, "every_pair_complete": True, "summary_present": True})

    def test_each_condition_fails_on_its_own_number_and_the_boundaries(self):
        d = gg.decide(report(syn(om=(0.5, 14, 15, 3))))                                      # negatives ≥ positives
        self.assertEqual(d["decision"], "no-go"); self.assertIn("not more than negatives", d["reason"])
        d = gg.decide(report(syn(om=(0.5, 16, 13, 3))))                                      # 16 / 13: p = 0.3555 > 0.20
        self.assertEqual(d["decision"], "no-go"); self.assertIn("> the cost threshold p_max_go 0.2", d["reason"]); self.assertGreater(d["statistic_1"]["sign_test_p"], 0.20)
        d = gg.decide(report(syn(om=(0.5, 18, 11, 3))))                                      # 18 / 11: p = 0.1325 ≤ 0.20
        self.assertEqual(d["decision"], "go", d["reason"])
        d = gg.decide(report(syn(k9_medians={"ff_srval": 0.49})))
        self.assertEqual(d["decision"], "no-go"); self.assertIn("ff_srval 0.49", d["reason"]); self.assertFalse(d["statistic_2"]["all_ge_min"])
        d = gg.decide(report(syn(k9_medians=dict.fromkeys(k9.SEMANTICS, 0.5))))
        self.assertEqual(d["decision"], "go", "the boundary written with an equal sign")
        d = gg.decide(report(syn(k9_na={"sr_kind": 1})))
        self.assertEqual(d["decision"], "no-go"); self.assertIn("not assessable", d["reason"]); self.assertIn("sr_kind None", d["reason"])
        d = gg.decide(report(syn(om=(0.5, 14, 15, 3), k9_medians={"ff_srval": 0.1})))
        self.assertEqual(d["decision"], "no-go"); self.assertIn("negatives", d["reason"]); self.assertIn("ff_srval", d["reason"])
        d = gg.decide(report(syn(k9_medians={"ff_srval": 0.6}, k9_medians_all_panel={"ff_srval": 0.4})))
        self.assertEqual(d["decision"], "go", "statistic 2 reads the JUDGED conditional medians; the all-panel record is carried as a description")
        self.assertEqual(d["statistic_2"]["all_panel_medians_descriptive"]["ff_srval"], 0.4)

    def test_no_decision_when_the_precondition_is_not_met_and_nothing_is_interpreted(self):
        for rep, part in ((report(syn(S=31), S=31), "S_is_32"), (report(syn(S=200), S=200), "S_is_32"), (report(syn(), pairs_complete=False), "every_pair_complete"),
                          (report(None, status="invalid"), "status_complete"), (report(None, status="incomplete"), "status_complete")):
            d = gg.decide(rep)
            self.assertEqual(d["decision"], "no_decision", part); self.assertIn(part, d["reason"]); self.assertIn("stop and report", d["reason"])
            self.assertIsNone(d["statistic_1"]); self.assertIsNone(d["statistic_2"]); self.assertIsNone(d["omega_minus_R_by_budget"])
        s = syn(); s["k9"]["judged_estimand"] = "all_panel"
        d = gg.decide(report(s)); self.assertEqual(d["decision"], "no_decision"); self.assertTrue(d["contract_findings"])
        d = gg.decide({"status": "complete"}); self.assertEqual(d["decision"], "no_decision"); self.assertTrue(d["contract_findings"])
        d = gg.decide(report(syn(), fixture=True, label="b4-mech-3")); self.assertEqual(d["decision"], "go"); self.assertFalse(d["formal"]); self.assertEqual(len(d["formal_reasons"]), 2)


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guards = [mock.patch.object(bs, "master_seed", side_effect=production_derivation_reached), mock.patch.object(bs, "pair_seeds", side_effect=production_derivation_reached)]
        cls.guard_mocks = [g.start() for g in cls.guards]
        cls.tmp = tempfile.TemporaryDirectory(prefix="b4gonogo_")
        cls.root = build_hermetic(Path(cls.tmp.name))
        cls.ns, cls.gns = cls.root / sim.SIM_REL, cls.root / gg.GONOGO_REL
        cls.batch = cls.ns / "b4-mech-1_gonogo"
        cls.res = sim.run_batch(cls.root, "b4-mech-1", 2, 3600, cls.batch, schedule=SCHED1)
        assert cls.res["status"] == "complete", cls.res
        git(cls.root, "add", "-A"); git(cls.root, "commit", "-q", "-m", "archive")

    @classmethod
    def tearDownClass(cls):
        try:
            calls = [m.call_count for m in cls.guard_mocks]
            for g in cls.guards:
                g.stop()
            assert calls == [0, 0], f"a production derivation was attempted: {calls}"
        finally:
            cls.tmp.cleanup()

    def fresh(self, gdir: Path, shallow=False):
        p = subprocess.run([sys.executable, "-B", str(R / "b4/host/b4_gonogo.py"), "verify", str(gdir)] + (["--shallow"] if shallow else []), capture_output=True, text=True)
        return p.returncode, json.loads(p.stdout)

    def test_a_fixture_batch_of_two_pairs_is_no_decision_written_verified_and_never_of_record(self):
        out = self.gns / "b4-mech-1_dec"
        r = gg.write_decision(self.root, self.batch, out)
        self.assertEqual((r["status"], r["exit_code"]), ("no_decision", 3), r.get("reason"))
        doc = json.loads((out / gg.DECISION_JSON).read_text())
        self.assertEqual(gg.decision_findings(doc), [])
        self.assertEqual((doc["decision"], doc["formal"], doc["fixture"], doc["S"]), ("no_decision", False, True, 2)); self.assertIn("S_is_32", doc["reason"])
        self.assertIn("NOT A DECISION OF RECORD", doc["standing"]); self.assertIn("a fixture batch", doc["formal_reasons"])
        self.assertEqual(doc["batch"]["path"], str(self.batch.relative_to(self.root))); self.assertEqual(doc["self_validation"], {})
        self.assertEqual(sorted(p.name for p in out.iterdir()), [gg.DECISION_JSON, gg.DECISION_MD])
        self.assertEqual((out / gg.DECISION_MD).read_bytes(), gg.render_md(doc).encode("utf-8"))
        self.assertEqual(gg.verify_gonogo_dir(out, deep=True), {})
        git(self.root, "add", "-A"); git(self.root, "commit", "-q", "-m", "gonogo")
        code, res = self.fresh(out); self.assertEqual((code, res["findings"], res["clean"]), (0, {}, True))
        # tampers with the digests refreshed: the decision, the policy, the standing, the evidence path
        original = (out / gg.DECISION_JSON).read_bytes()
        try:
            for mutate, part in ((lambda d: d.__setitem__("decision", "go"), "carries"), (lambda d: d["policy"].__setitem__("p_max_go", 0.5), "policy"),
                                 (lambda d: d.__setitem__("standing", gg.STANDING_FORMAL), "standing"), (lambda d: d["batch"].__setitem__("sha256", "0" * 64), "does not hash"),
                                 (lambda d: d.__setitem__("precondition", {}), "precondition is not the one recomputed")):
                d = json.loads(original); mutate(d)
                (out / gg.DECISION_MD).write_bytes(gg.render_md(d).encode("utf-8")); b = (out / gg.DECISION_MD).read_bytes()
                d["files"] = [{"path": gg.DECISION_MD, "sha256": gg._sha(b), "size": len(b)}]
                (out / gg.DECISION_JSON).write_bytes(sim.json_text(d))
                f = gg.verify_gonogo_dir(out, deep=False)
                self.assertTrue(any(part in m for v in f.values() for m in v), (part, f))
        finally:
            (out / gg.DECISION_JSON).write_bytes(original); (out / gg.DECISION_MD).write_bytes(gg.render_md(json.loads(original)).encode("utf-8"))
        self.assertEqual(gg.verify_gonogo_dir(out, deep=False), {}, "restored")
        r2 = gg.write_decision(self.root, self.batch, out); self.assertEqual(r2["status"], "refused"); self.assertIn("new directory", r2["reason"])

    def test_the_evidence_contract_is_held_exactly_in_type_namespace_and_entries(self):
        """R5 of the owner's review of 04385ae, with every hash and the markdown refreshed after each alteration: count 1 -> 1.0, fixture
        true -> 1, S 2 -> 2.0, the batch path escaping the root (`../escaped_batch`, an identical archive outside), an absolute path, a `..`
        inside the namespace, a symlinked batch directory — each named by the record validator / the verifier AND refused by the CLI in a
        fresh process; the gonogo directory's ENTRIES held: a subdirectory, an extra file, a symlink, an unfinished write — each named."""
        out = self.gns / "b4-mech-1_contract"
        r = gg.write_decision(self.root, self.batch, out); self.assertEqual(r["status"], "no_decision", r.get("reason"))
        git(self.root, "add", "-A"); git(self.root, "commit", "-q", "-m", "gonogo contract")
        original = (out / gg.DECISION_JSON).read_bytes()

        def alter(mutate):
            d = json.loads(original); mutate(d)
            (out / gg.DECISION_MD).write_bytes(gg.render_md(d).encode("utf-8")); b = (out / gg.DECISION_MD).read_bytes()
            d["files"] = [{"path": gg.DECISION_MD, "sha256": gg._sha(b), "size": len(b)}]
            (out / gg.DECISION_JSON).write_bytes(sim.json_text(d)); return d
        with tempfile.TemporaryDirectory(prefix="b4escaped_") as outside:
            escaped = Path(outside) / "escaped_batch"; shutil.copytree(self.batch, escaped)
            link = self.ns / "b4-mech-1_linked"; link.symlink_to(escaped)
            try:
                for name, mutate, needle in (("float count", lambda d: d["batch"].__setitem__("count", 1.0), "exact types"),
                                             ("integer fixture", lambda d: d["batch"].__setitem__("fixture", 1), "exact types"),
                                             ("float S", lambda d: d.__setitem__("S", 2.0), "label / S / fixture"),
                                             ("escaped path", lambda d: d["batch"].__setitem__("path", "../escaped_batch"), "batch.path"),
                                             ("absolute path", lambda d: d["batch"].__setitem__("path", str(self.batch)), "batch.path"),
                                             ("dotdot inside", lambda d: d["batch"].__setitem__("path", f"{sim.SIM_REL}/../sim/{self.batch.name}"), "batch.path"),
                                             ("symlinked batch directory", lambda d: d["batch"].__setitem__("path", f"{sim.SIM_REL}/b4-mech-1_linked"), "not a real directory")):
                    with self.subTest(name):
                        d = alter(mutate)
                        if needle != "not a real directory":
                            self.assertTrue(any(needle in x for x in gg.decision_findings(d)), (name, gg.decision_findings(d)))
                        f = gg.verify_gonogo_dir(out, deep=False); self.assertTrue(any(needle in m for v in f.values() for m in v), (name, f))
                        code, res = self.fresh(out, shallow=True); self.assertEqual(code, 1, name); self.assertFalse(res["clean"])
            finally:
                link.unlink()
                (out / gg.DECISION_JSON).write_bytes(original); (out / gg.DECISION_MD).write_bytes(gg.render_md(json.loads(original)).encode("utf-8"))
        self.assertEqual(gg.verify_gonogo_dir(out, deep=False), {}, "restored")
        for make, undo, needle in (((out / "sub").mkdir, (out / "sub").rmdir, "no subdirectory"),
                                   (lambda: (out / "extra.json").write_text("{}"), (out / "extra.json").unlink, "not a file of a gonogo directory"),
                                   (lambda: (out / "link").symlink_to(out / gg.DECISION_MD), (out / "link").unlink, "no symlink"),
                                   (lambda: (out / "gonogo.json.1.part").write_text(""), (out / "gonogo.json.1.part").unlink, "unfinished")):
            make()
            try:
                f = gg.verify_gonogo_dir(out, deep=False); self.assertTrue(any(needle in m for v in f.values() for m in v), (needle, f))
                code, res = self.fresh(out, shallow=True); self.assertEqual(code, 1, needle)
            finally:
                undo()
        self.assertEqual(gg.verify_gonogo_dir(out, deep=False), {}, "restored")
        self.assertFalse(git(self.root, "status", "--porcelain").strip(), "the hermetic tree is clean again")

    def test_refusals_write_nothing(self):
        before = sorted(p.name for p in self.gns.iterdir()) if self.gns.exists() else []
        r = gg.write_decision(self.root, Path(self.tmp.name) / "nowhere"); self.assertEqual(r["status"], "refused")
        empty = self.ns / "b4-mech-1_empty"; empty.mkdir()
        r = gg.write_decision(self.root, empty); self.assertEqual(r["status"], "refused"); self.assertIn("no sim_report.json", r["reason"]); empty.rmdir()
        # an archive without the protocol identity (the committed v0.1.16 exploration, read-only): refused by name before anything else;
        # an archive of ANOTHER identity (the committed v0.2.0 exploration b4-sim-4, read-only): refused by name, the differing components listed.
        # The repository's own gonogo namespace holds the committed b4-sim-4 decision since 2026-10-21: its listing must be unchanged, not absent.
        repo_gonogo = sorted(p.name for p in (R / gg.GONOGO_REL).iterdir()) if (R / gg.GONOGO_REL).exists() else []
        r = gg.write_decision(R, R / "evidence/b4/sim/b4-sim-3_20261019T121833Z")
        self.assertEqual(r["status"], "refused"); self.assertIn("no protocol identity", r["reason"]); self.assertIn("b4_archive_reverification", r["reason"])
        r = gg.write_decision(R, R / "evidence/b4/sim/b4-sim-4_20261021T065339Z")
        self.assertEqual(r["status"], "refused"); self.assertIn("not this tool's", r["reason"]); self.assertIn("task", r["reason"]); self.assertIn("b4_archive_reverification", r["reason"])
        self.assertEqual(sorted(p.name for p in (R / gg.GONOGO_REL).iterdir()) if (R / gg.GONOGO_REL).exists() else [], repo_gonogo, "nothing was written to the repository")
        after = sorted(p.name for p in self.gns.iterdir()) if self.gns.exists() else []
        self.assertEqual(before, after)
        self.assertFalse(git(self.root, "status", "--porcelain").strip())

    def test_the_cli(self):
        with mock.patch("sys.stdout"):
            with mock.patch.object(sim, "porcelain", return_value=[" M x"]):
                self.assertEqual(gg.main(["decide", str(self.batch)]), 2, "a dirty tree refuses")
        code, res = self.fresh(Path(self.tmp.name) / "nowhere"); self.assertEqual(code, 1); self.assertIn("gonogo directory", res["findings"])


if __name__ == "__main__":
    unittest.main()
