"""b4/host/b4_sim.py and b4/host/b4_sim_schema.py — the exploration harness on a HERMETIC repository copy (only the files the
harness reads from its root, under its own git history; the model code and the pinned formal inputs are the real tree's,
read-only). S = 2 batches under the exploration labels b4-sim-1 / b4-sim-2 of the hermetic root (the formal namespace of the
real repository is never written). Mechanics: the pre-flight refusals write nothing; the freezing order; a complete batch
and its files; the registry of a second batch; the invalid stops (DOMAIN, a control failure, a replay finding, an unexpected
exception, an input drift); the incomplete stops (the deadline inside K9 and in the statistics, an external interrupt);
the typed validators; the pure summary on hand rows (a +inf Cohen's d). No K value is read as a result. No skip."""
from __future__ import annotations

import json
import os
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
import b4_carto as bc  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_gate_stats as gs  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_replay as br  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim as sim  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_thresholds as th  # noqa: E402
from b4_test_fixtures import InjectingPort  # noqa: E402

ROLES = sim.ROLES


def git(root: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True, text=True).stdout


def build_hermetic(dst: Path) -> Path:
    files = [f[0] for f in bs.FIELDS] + list(sim.ROOT_INPUTS)
    for s in hy.load().doc["sources"]:
        if s.get("kind") in ("repository_document", "certificate_mapping") and "root" not in s:
            files.append(s["path"])
    for rel in sorted(set(files)):
        d = dst / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(R / rel, d)
    git(dst, "init", "-q"); git(dst, "add", "-A"); git(dst, "commit", "-q", "-m", "hermetic")
    return dst


class RaisingPort(ex.ObservationPort):
    def __init__(self, fabric, at: int, exc):
        super().__init__(fabric)
        self.at, self.exc = at, exc

    def observe(self, config, stimulus):
        self.calls += 1
        if self.calls == self.at:
            raise self.exc
        return self._observe(config, stimulus)


class Clock:
    """A fake monotonic clock: `step` per call; `jump` is added once `trigger` has been set."""

    def __init__(self, step: float = 0.0):
        self.t, self.step, self.calls, self.jump_at, self.jump = 1000.0, step, 0, None, 0.0

    def __call__(self):
        self.calls += 1
        self.t += self.step
        if self.jump_at is not None and self.calls >= self.jump_at:
            return self.t + self.jump
        return self.t


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="b4sim_")
        cls.root = build_hermetic(Path(cls.tmp.name))
        cls.ns = cls.root / sim.SIM_REL
        cls.counter = 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def out(self, label="b4-sim-1") -> Path:
        type(self).counter += 1
        return self.ns / f"{label}_t{type(self).counter:03d}"

    def tearDown(self):
        # every batch directory of this test is committed so the hermetic tree is clean again (as production requires)
        if self.ns.exists() and git(self.root, "status", "--porcelain").strip():
            git(self.root, "add", "-A"); git(self.root, "commit", "-q", "-m", "archive")

    def report(self, res) -> dict:
        return json.loads((Path(res["out"]) / "sim_report.json").read_text())


class Preflight(Base):
    def test_refusals_write_nothing(self):
        before = sorted(p.name for p in self.ns.iterdir()) if self.ns.exists() else []
        cases = [("b4-gate-1", 2, 60, None, "exploration label"), ("b4-sim-1", 0, 60, None, "--seeds"), ("b4-sim-1", 2, 0, None, "--deadline-s"),
                 ("b4-sim-1", 2, True, None, "--deadline-s"), ("b4-sim-1", 2, 60, Path(self.tmp.name) / "elsewhere" / "b4-sim-1_x", "directly under"),
                 ("b4-sim-1", 2, 60, self.ns / "other_x", "begin with b4-sim-1_")]
        for label, S, dl, out, msg in cases:
            res = sim.run_batch(self.root, label, S, dl, out)
            self.assertEqual((res["status"], res["exit_code"]), ("refused", 2), (label, S, dl, out))
            self.assertIn(msg, res["reason"], (label, S, dl, out))
        existing = self.ns / "b4-sim-1_exists"
        existing.mkdir(parents=True)
        res = sim.run_batch(self.root, "b4-sim-1", 2, 60, existing)
        self.assertEqual(res["status"], "refused"); self.assertIn("exists", res["reason"])
        self.assertEqual(sorted(os.listdir(existing)), [], "nothing written inside an existing directory")
        existing.rmdir()
        link = self.ns / "b4-sim-1_link"
        link.symlink_to(Path(self.tmp.name))
        res = sim.run_batch(self.root, "b4-sim-1", 2, 60, link)
        self.assertEqual(res["status"], "refused"); link.unlink()
        (self.root / "dirty.txt").write_text("x")
        res = sim.run_batch(self.root, "b4-sim-1", 2, 60, self.out())
        self.assertEqual(res["status"], "refused"); self.assertIn("not clean", res["reason"])
        (self.root / "dirty.txt").unlink()
        after = sorted(p.name for p in self.ns.iterdir()) if self.ns.exists() else []
        self.assertEqual(before, after, "a refusal creates no run directory")
        self.assertFalse(git(self.root, "status", "--porcelain").strip())


class CompleteBatch(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.seen = []

        def factory(fabric, role, pair):
            cls.seen.append((pair, role, (cls.out_dir / "seeds.json").exists(), (cls.out_dir / "manifest.json").exists()))
            return ex.ObservationPort(fabric)
        cls.out_dir = cls.ns / "b4-sim-1_complete"
        cls.head_at_run = git(cls.root, "rev-parse", "HEAD").strip()
        cls.res = sim.run_batch(cls.root, "b4-sim-1", 2, 3600, cls.out_dir, port_factory=factory)
        git(cls.root, "add", "-A"); git(cls.root, "commit", "-q", "-m", "archive complete")

    def test_complete_with_every_file_typed_and_no_verdict(self):
        res, out = self.res, self.out_dir
        self.assertEqual((res["status"], res["exit_code"]), ("complete", 0), res.get("reason"))
        names = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
        want = ["manifest.json", "seeds.json", "sim_report.json"]
        for r in (0, 1):
            want += [f"pair_{r:03d}/arm_{role}.{k}.json" for role in ROLES for k in ("result", "audit")]
            want += [f"pair_{r:03d}/{n}.json" for n in ("controls", "curves", "index", "k10", "k7", "k9")]
        self.assertEqual(names, sorted(want))
        pairs = json.loads((out / "seeds.json").read_text())["pairs"]
        self.assertEqual(sc.validate_run_dir(out, task_of=lambda r: bl.make_task(pairs[r][0], bm.site_mapping().addresses)), {})
        rep = self.report(res)
        self.assertEqual(rep["status"], "complete"); self.assertIsNone(rep["stopped"]); self.assertEqual(rep["missing"], [])
        self.assertEqual(rep["self_validation"], {})
        self.assertEqual(rep["thresholds"], th.THRESHOLDS)
        self.assertIn("not a gate verdict", rep["standing"])
        s = rep["summary"]
        self.assertEqual(s["S"], 2)
        self.assertEqual(s["candidate_B_star"]["value"], None, "S = 2 < n_min: no N, so no candidate — null with the reason, not invalid")
        self.assertIn("not invented", s["candidate_B_star"]["reason_if_none"])
        self.assertEqual(sum(s["k10"]["counts"].values()), 2)
        for B in th.GRID:
            pb = s["per_budget"][str(B)]
            self.assertEqual(set(pb["arm_values"]), set(ROLES))
            self.assertEqual(pb["required_pairs"]["N"], None)
            self.assertIn("cohen_d", pb["deltas"]["delta1_O_minus_R"])
        self.assertEqual(sc.report_findings(rep), [])
        self.assertEqual([p["status"] for p in rep["pairs"]], ["complete", "complete"])
        self.assertTrue(all(all(v == "audited" for v in p["arms"].values()) for p in rep["pairs"]))
        self.assertEqual({e["path"] for e in rep["files"]} - {"sim_report.json"}, set(names) - {"sim_report.json"})
        for e in rep["files"]:
            if e["path"] != "sim_report.json":
                self.assertEqual(sim.sha_file(out / e["path"]), e["sha256"], e["path"])

    def test_the_freezing_order_and_the_seeds(self):
        self.assertTrue(self.seen, "ports were created")
        self.assertTrue(all(s and m for _, _, s, m in self.seen), "seeds.json and manifest.json existed before every port was created")
        self.assertEqual([(p, role) for p, role, _, _ in self.seen], [(p, role) for p in (0, 1) for role in list(ROLES) + ["K9", "K10"]], "one worker, the fixed order")
        seeds = json.loads((self.out_dir / "seeds.json").read_text())
        self.assertEqual(bs.seeds_doc_findings(seeds), [])
        self.assertEqual(seeds["anchor"]["hypothesis_sha256"], hy.HYPOTHESIS_SHA256)
        self.assertEqual(seeds["master_seed"], bs.master_seed("b4-sim-1", hy.HYPOTHESIS_SHA256))
        flat = [v for p in seeds["pairs"] for v in p]
        self.assertEqual(len(set(flat)), 4)
        ex_ = bs.load_exclusion_set(self.root, str(self.ns / "nonexistent"))
        self.assertFalse(set(flat) & ex_.values, "no planned value is in the pooled set")
        self.assertEqual(len(seeds["exclusion"]["sources"]), 38)
        self.assertEqual(seeds["exclusion"]["sim_registry"], [], "the first batch: no archived set yet")
        man = json.loads((self.out_dir / "manifest.json").read_text())
        self.assertEqual(sc.manifest_findings(man), [])
        self.assertEqual(man["head"], self.head_at_run, "the HEAD the batch ran under (the archive commit came after)")
        self.assertEqual(man["inputs"][hy.HYPOTHESIS_REL], hy.HYPOTHESIS_SHA256)
        self.assertIn("b4/host/b4_sim.py", man["tool_files"])
        self.assertEqual(man["seeds_sha256"], sim.sha_file(self.out_dir / "seeds.json"))

    def test_the_arm_files_are_the_engine_s_and_the_audits_clean(self):
        for r in (0, 1):
            for role in ROLES:
                d = json.loads((self.out_dir / f"pair_{r:03d}/arm_{role}.result.json").read_text())
                a = json.loads((self.out_dir / f"pair_{r:03d}/arm_{role}.audit.json").read_text())
                self.assertEqual((d["role"], d["engine_arm"], d["result"]["arm"]), (role, sim.ENGINE_ARM[role], sim.ENGINE_ARM[role]))
                self.assertEqual(d["result"]["evals"], 256); self.assertEqual(d["port_calls"], sum(sim.EXPECTED_COST[role].values()))
                self.assertEqual((a["invalid"], a["completion_findings"], a["replay_findings"], a["view_findings"], a["recompute"]["findings"]), (False, [], [], [], []))
            c = json.loads((self.out_dir / f"pair_{r:03d}/controls.json").read_text())
            self.assertEqual(c["d_view"]["provenance"], ["learned", "shuffled"]); self.assertTrue(c["omega_view"]["privileged"])
            k7 = json.loads((self.out_dir / f"pair_{r:03d}/k7.json").read_text())
            self.assertTrue(k7["complete"]); self.assertEqual(sorted(int(b) for b in k7["prefixes"]), list(th.GRID))
            k9 = json.loads((self.out_dir / f"pair_{r:03d}/k9.json").read_text()); self.assertTrue(k9["complete"])
            k10 = json.loads((self.out_dir / f"pair_{r:03d}/k10.json").read_text()); self.assertTrue(k10["complete"])
            cv = json.loads((self.out_dir / f"pair_{r:03d}/curves.json").read_text())
            self.assertTrue(cv["f_end_to_end_at_grid"][0]["mapping_in_progress"]); self.assertFalse(cv["f_end_to_end_at_grid"][-1]["mapping_in_progress"])

    def test_a_second_batch_excludes_the_first_s_archived_set(self):
        out2 = self.ns / "b4-sim-2_second"
        res = sim.run_batch(self.root, "b4-sim-2", 2, 3600, out2)
        self.assertEqual(res["status"], "complete", res.get("reason"))
        s1 = json.loads((self.out_dir / "seeds.json").read_text()); s2 = json.loads((out2 / "seeds.json").read_text())
        reg = s2["exclusion"]["sim_registry"]
        self.assertEqual([(r["status"], r["master_seed"], r["count"]) for r in reg], [("seeds", s1["master_seed"], 5)])
        self.assertTrue(reg[0]["dir"].endswith("b4-sim-1_complete"))
        v1 = {s1["master_seed"]} | {v for p in s1["pairs"] for v in p}
        v2 = {v for p in s2["pairs"] for v in p}
        self.assertFalse(v1 & v2, "the second set avoids every value of the first")
        self.assertNotEqual(s1["master_seed"], s2["master_seed"], "another label, another master")


class InvalidStops(Base):
    def run_with(self, factory, out=None, **kw):
        return sim.run_batch(self.root, "b4-sim-1", 2, 3600, out or self.out(), port_factory=factory, **kw)

    def test_domain_in_the_second_pair_s_o_arm(self):
        def factory(fabric, role, pair):
            return InjectingPort(fabric, 30) if (pair, role) == (1, "O") else ex.ObservationPort(fabric)
        res = self.run_with(factory)
        self.assertEqual((res["status"], res["exit_code"]), ("invalid", 1))
        out = Path(res["out"])
        self.assertEqual((res["stopped"]["kind"], res["stopped"]["pair"], res["stopped"]["role"], res["stopped"]["stage"]), ("domain", 1, "O", "audit"))
        self.assertTrue((out / "pair_000/index.json").exists(), "the first pair is whole")
        for role in ("R", "F", "O"):
            self.assertTrue((out / f"pair_001/arm_{role}.result.json").exists(), role)
        self.assertFalse((out / "pair_001/arm_X.result.json").exists())
        o = json.loads((out / "pair_001/arm_O.result.json").read_text())["result"]
        self.assertIsNotNone(o["terminal"]); self.assertFalse(o["completed"])
        a = json.loads((out / "pair_001/arm_O.audit.json").read_text())
        self.assertTrue(a["invalid"]); self.assertTrue(a["completion_findings"])
        rep = self.report(res)
        self.assertEqual(rep["status"], "invalid"); self.assertIsNone(rep["summary"]); self.assertTrue(rep["missing"])
        self.assertEqual(rep["pairs"][0]["status"], "complete"); self.assertEqual(rep["pairs"][1]["status"], "partial")
        self.assertEqual(rep["pairs"][1]["arms"], {"R": "audited", "F": "audited", "O": "written", "X": "not_started", "D": "not_started", "Omega": "not_started", "A0": "not_started"})
        self.assertEqual(sc.stopped_findings(rep["stopped"]), []); self.assertEqual(sc.report_findings(rep), [])
        self.assertEqual(sc.validate_run_dir(out), {})

    def test_a_control_failure_a_replay_finding_and_a_k10_domain(self):
        real = bc.isomorphic_addresses
        calls = {"n": 0}

        def fake(x, shadow, perm):
            calls["n"] += 1
            return ["injected"] if calls["n"] == 9 else real(x, shadow, perm)
        with mock.patch.object(bc, "isomorphic_addresses", fake):
            res = self.run_with(None)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["role"]), ("invalid", "control_failure", "X"))
        x = json.loads((Path(res["out"]) / "pair_000/arm_X.result.json").read_text())["result"]
        self.assertIsNotNone(x["control_failure"], "the exposing run is on disk as returned")
        self.tearDown()
        with mock.patch.object(br, "replay", lambda result, task: ["an injected replay finding"]):
            res = self.run_with(None)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["role"], res["stopped"]["pair"]), ("invalid", "contract", "R", 0))
        self.assertTrue((Path(res["out"]) / "pair_000/arm_R.result.json").exists())
        self.tearDown()

        def factory(fabric, role, pair):
            return InjectingPort(fabric, 100) if (pair, role) == (0, "K10") else ex.ObservationPort(fabric)
        res = self.run_with(factory)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["role"]), ("invalid", "k10_invalid", "K10"))
        k10 = json.loads((Path(res["out"]) / "pair_000/k10.json").read_text())
        self.assertFalse(k10["complete"]); self.assertIsNotNone(k10["invalid"]); self.assertFalse(k10["units"][-1]["comparable"])
        self.assertTrue((Path(res["out"]) / "pair_000/k9.json").exists())
        self.assertEqual(sc.validate_run_dir(Path(res["out"])), {})

    def test_a_crashing_audit_does_not_lose_the_run_that_returned(self):
        def boom(result, task):
            raise RuntimeError("audit crashed")
        with mock.patch.object(br, "replay", boom):
            res = self.run_with(None)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["role"]), ("invalid", "unexpected_exception", "R"))
        out = Path(res["out"])
        self.assertTrue((out / "pair_000/arm_R.result.json").exists(), "the RunResult was written before the audit began")
        self.assertFalse((out / "pair_000/arm_R.audit.json").exists())
        self.assertEqual(self.report(res)["pairs"][0]["arms"]["R"], "written")

    def test_an_unexpected_exception_and_an_input_drift(self):
        def factory(fabric, role, pair):
            return RaisingPort(fabric, 7, RuntimeError("boom")) if (pair, role) == (0, "O") else ex.ObservationPort(fabric)
        res = self.run_with(factory)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["role"]), ("invalid", "unexpected_exception", "O"))
        rep = self.report(res)
        self.assertEqual(rep["pairs"][0]["arms"]["O"], "result_unavailable"); self.assertEqual(rep["pairs"][0]["arms"]["F"], "audited")
        self.assertTrue((Path(res["out"]) / "pair_000/arm_F.audit.json").exists(), "the six arms before it are not lost")
        self.assertIn("RuntimeError", res["stopped"]["detail"])
        self.tearDown()
        arch = self.root / "docs/b4_architecture.md"
        original = arch.read_bytes()

        def drift(fabric, role, pair):
            if (pair, role) == (1, "R"):
                arch.write_bytes(original + b"\n<!-- drift -->\n")
            return ex.ObservationPort(fabric)
        try:
            res = self.run_with(drift)
        finally:
            arch.write_bytes(original)
        self.assertEqual((res["status"], res["stopped"]["kind"]), ("invalid", "input_drift"))
        self.assertEqual(res["stopped"]["stage"], "pair 1 end", "caught by the input checkpoint at the end of the pair it drifted in — not by the final working-tree check")
        self.assertIn("the input docs/b4_architecture.md changed during the batch", res["stopped"]["detail"])
        self.assertTrue((Path(res["out"]) / "pair_001/k10.json").exists(), "the pair's work is kept; the drift is caught at its checkpoint")
        rep = self.report(res)
        self.assertIsNone(rep["summary"])


class IncompleteStops(Base):
    def test_the_deadline_inside_k9(self):
        clock = Clock(step=1.0)
        res = sim.run_batch(self.root, "b4-sim-1", 2, 60, self.out(), clock=clock)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["role"]), ("incomplete", 3, "deadline", "K9"))
        out = Path(res["out"])
        k9 = json.loads((out / "pair_000/k9.json").read_text())
        self.assertFalse(k9["complete"]); self.assertIsNone(k9["summary"]); self.assertGreater(k9["pairs_done"], 0); self.assertLess(k9["pairs_done"], 1184)
        for role in ROLES:
            self.assertTrue((out / f"pair_000/arm_{role}.audit.json").exists(), role)
        rep = self.report(res)
        self.assertEqual((rep["status"], rep["summary"]), ("incomplete", None))
        self.assertEqual(rep["pairs"][0]["k9"], "partial"); self.assertEqual(rep["pairs"][1]["status"], "not_started")
        self.assertTrue(rep["deadline"]["expired"]); self.assertEqual(rep["deadline"]["clock"], "time.monotonic")
        self.assertEqual(sc.validate_run_dir(out), {})

    def test_the_deadline_in_the_statistics_and_an_interrupt(self):
        clock = Clock(step=0.0)

        def factory(fabric, role, pair):
            if (pair, role) == (1, "K10"):
                clock.jump_at, clock.jump = clock.calls + 423, 10 ** 6       # after K10's 421 checks and the curves' check
            return ex.ObservationPort(fabric)
        res = sim.run_batch(self.root, "b4-sim-1", 2, 60, self.out(), clock=clock, port_factory=factory)
        self.assertEqual((res["status"], res["stopped"]["kind"]), ("incomplete", "deadline"))
        self.assertIn(res["stopped"]["stage"], ("statistics", "curves"))
        out = Path(res["out"])
        self.assertTrue(json.loads((out / "pair_001/k10.json").read_text())["complete"], "K10 finished before the expiry")
        self.assertIsNone(self.report(res)["summary"], "no pooled summary without a complete statistics stage")
        self.tearDown()

        def interrupt(fabric, role, pair):
            return RaisingPort(fabric, 5, KeyboardInterrupt()) if (pair, role) == (0, "F") else ex.ObservationPort(fabric)
        res = sim.run_batch(self.root, "b4-sim-1", 2, 3600, self.out(), port_factory=interrupt)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["role"]), ("incomplete", 3, "interrupted", "F"))
        rep = self.report(res)
        self.assertEqual((rep["pairs"][0]["arms"]["R"], rep["pairs"][0]["arms"]["F"]), ("audited", "result_unavailable"))
        self.assertNotIn("DOMAIN", res["stopped"]["detail"])


class TheSummaryAndTheValidators(unittest.TestCase):
    def row(self, r, best):
        g = list(th.GRID)
        return {"pair": r, "landscape_seed": 100 + r, "operator_seed": 200 + r, "base_fit": 10, "best_at_grid": {role: [best[role]] * len(g) for role in ROLES},
                "f_end_to_end_at_grid": [10] * len(g), "k7_not_unknown_at_grid": [3] * len(g),
                "k9": {s: {"applicable": 4, "covered": 2, "not_applicable": 0, "fraction": 0.5, "assessable": True, "positive_control": True, "conditional_on_A8": s == "ff_init"} for s in sc_semantics()},
                "k9_all_seven": True, "k10_max_abs": 3, "k10_outcome": "interacting"}

    def test_on_hand_rows_including_an_infinite_cohen_d(self):
        best = {"R": 20, "F": 30, "O": 25, "X": 20, "D": 20, "Omega": 40, "A0": 20}
        rows = [self.row(0, best), self.row(1, best)]
        s, rec = sim.summarise_batch(rows, 2)
        pb = s["per_budget"]["8"]
        self.assertEqual(pb["deltas"]["delta1_O_minus_R"]["cohen_d"], {"value": None, "special": "+inf"}, "two equal positive deltas: +inf, named, not 0")
        self.assertEqual(pb["deltas"]["delta1_O_minus_R"]["positives"], 2)
        self.assertEqual(pb["required_pairs"]["N"], None, "S = 2 < 8")
        self.assertIsNone(s["candidate_B_star"]["value"])
        self.assertEqual(s["k10"]["counts"]["interacting"], 2); self.assertEqual(s["k9"]["seeds_with_all_seven_positive_controls"], 2)
        json.dumps(s, allow_nan=False)
        self.assertEqual(gs.finite_findings(s), [])
        with self.assertRaises(ValueError):
            sim.summarise_batch(rows, 3)
        rows[1]["k9"]["sr_kind"]["fraction"] = None; rows[1]["k9"]["sr_kind"]["assessable"] = False
        s2, _ = sim.summarise_batch(rows, 2)
        self.assertEqual((s2["k9"]["per_semantic"]["sr_kind"]["not_assessable_seeds"], s2["k9"]["per_semantic"]["sr_kind"]["median_coverage_over_all_S"]), (1, None), "one not-assessable seed: the median is not assessable")

    def test_a_summary_with_a_verdict_key_is_refused_by_the_report_validator(self):
        rep = {"schema": "b4_sim_report", "schema_version": "1.0.0", "status": "complete", "label": "b4-sim-1", "count": 1, "head": "0" * 40, "generated_utc": "x",
               "deadline": {}, "standing": "not a gate verdict", "thresholds": {}, "identity": {}, "pairs": [{"status": "complete"}], "files": [], "stopped": None,
               "summary": {"k1_pass": True}, "missing": [], "self_validation": {}}
        self.assertTrue(any("verdict-like" in f for f in sc.report_findings(rep)))
        rep["summary"] = {"thresholds_for_reference": {}}
        self.assertEqual(sc.report_findings(rep), [], "'thresholds' is not a verdict word")
        rep["status"] = "invalid"
        self.assertTrue(sc.report_findings(rep), "a batch that did not complete carries no summary and needs its STOPPED record")

    def test_write_exclusive_never_overwrites_and_refuses_non_finite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.json"
            e = sim.write_exclusive(p, {"a": 1})
            self.assertEqual((e["path"], e["size"]), ("a.json", len(sim.json_text({"a": 1}))))
            with self.assertRaises(FileExistsError):
                sim.write_exclusive(p, {"a": 2})
            self.assertEqual(json.loads(p.read_text()), {"a": 1})
            with self.assertRaises(sim.Invalid):
                sim.write_exclusive(Path(tmp) / "b.json", {"d": float("inf")})
            self.assertFalse((Path(tmp) / "b.json").exists())
            self.assertEqual([q.name for q in Path(tmp).iterdir()], ["a.json"], "no .part file is left behind")


def sc_semantics():
    import b4_k9 as k9
    return k9.SEMANTICS


if __name__ == "__main__":
    unittest.main()
