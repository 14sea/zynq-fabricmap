"""b4/host/b4_sim.py, b4/host/b4_sim_schema.py, b4/host/b4_sim_verify.py — the exploration harness on a HERMETIC repository
copy (only the files the harness reads from its root, under its own git history; the model code and the pinned formal
inputs are the real tree's, read-only), driven by MECHANICS FIXTURE SCHEDULES ONLY (`b4-mech-<n>` labels; explicit pairs of
values already exposed under section 9.2: 7 / 11, 8 / 12, 3 / 13, 5 / 12). NO PRODUCTION SET IS DERIVED HERE: for every
class, `b4_seeds.master_seed` and `b4_seeds.pair_seeds` are replaced by guards that raise, and the class's teardown
asserts they were never called (the owner's review of cdf2c53, F1). The real repository's exploration namespace is never
written.

Mechanics: the pre-flight refusals write nothing (incl. a symlinked namespace, F7); the freezing order; a complete batch
and its files (every file typed, the archive-wide verifier clean, no verdict); the registry of a second fixture batch; the
invalid stops (DOMAIN, a control failure, a replay finding, an unexpected exception, an input / external / registry drift
F9, a quarantined malformed RunResult F6, a refusal inside K9 with its partial kept F6, a bad q cell from the source F3,
self-validation findings and an unwritable report F4); the incomplete stops (the deadline inside K9, in the statistics,
before finalisation F8, an external interrupt); the archive-wide verifier on a tampered complete archive (F2 / F3); the
pure summary on hand rows. No K value is read as a result. No skip."""
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
import b4_gate_stats as gs  # noqa: E402
import b4_k10 as k10  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_replay as br  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim as sim  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_sim_verify as sv  # noqa: E402
import b4_thresholds as th  # noqa: E402
from b4_test_fixtures import InjectingPort  # noqa: E402

ROLES = sim.ROLES
SCHED1 = sim.FixtureSchedule("b4-mech-1", ((7, 11), (8, 12)))
SCHED2 = sim.FixtureSchedule("b4-mech-2", ((3, 13), (5, 12)))
SCHED_ONE = sim.FixtureSchedule("b4-mech-1", ((7, 11),))


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


def production_derivation_reached(*a, **kw):
    raise AssertionError("a production seed derivation (b4_seeds.master_seed / pair_seeds) was reached from a test")


class RaisingPort(ex.ObservationPort):
    def __init__(self, fabric, at: int, exc):
        super().__init__(fabric)
        self.at, self.exc = at, exc

    def observe(self, config, stimulus):
        self.calls += 1
        if self.calls == self.at:
            raise self.exc
        return self._observe(config, stimulus)


class BadGridPort(ex.ObservationPort):
    """A source whose first trace carries a q cell of 2 (not 0 / 1 / null): the model never does this; the harness must not archive it as valid."""

    def observe(self, config, stimulus):
        t = super().observe(config, stimulus)
        if self.calls == 1:
            t["steps"][0]["q_after"][0] = 2
        return t


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
        cls.guards = [mock.patch.object(bs, "master_seed", side_effect=production_derivation_reached),
                      mock.patch.object(bs, "pair_seeds", side_effect=production_derivation_reached)]
        cls.guard_mocks = [g.start() for g in cls.guards]
        cls.tmp = tempfile.TemporaryDirectory(prefix="b4mech_")
        cls.root = build_hermetic(Path(cls.tmp.name))
        cls.ns = cls.root / sim.SIM_REL
        cls.counter = 0

    @classmethod
    def tearDownClass(cls):
        try:
            calls = [m.call_count for m in cls.guard_mocks]
            for g in cls.guards:
                g.stop()
            assert calls == [0, 0], f"a production derivation was attempted from {cls.__name__}: {calls}"
        finally:
            cls.tmp.cleanup()

    def out(self, label="b4-mech-1") -> Path:
        type(self).counter += 1
        return self.ns / f"{label}_t{type(self).counter:03d}"

    def tearDown(self):
        # every batch directory of this test is committed so the hermetic tree is clean again (as production requires)
        if self.ns.exists() and git(self.root, "status", "--porcelain").strip():
            git(self.root, "add", "-A"); git(self.root, "commit", "-q", "-m", "archive")

    def run_with(self, factory, out=None, label="b4-mech-1", schedule=SCHED1, S=2, dl=3600, **kw):
        return sim.run_batch(self.root, label, S, dl, out or self.out(label), port_factory=factory, schedule=schedule, **kw)

    def report(self, res) -> dict:
        return json.loads((Path(res["out"]) / "sim_report.json").read_text())


class Preflight(Base):
    def test_refusals_write_nothing(self):
        before = sorted(p.name for p in self.ns.iterdir()) if self.ns.exists() else []
        cases = [("b4-sim-1", 2, 60, None, SCHED1, "mechanics label"),            # a production label never runs on a fixture
                 ("b4-mech-1", 2, 60, None, None, "needs a FixtureSchedule"),       # a fixture label never derives
                 ("b4-gate-1", 2, 60, None, None, "exploration label"), ("b4-sim-1", 0, 60, None, None, "--seeds"), ("b4-sim-1", 2, 0, None, None, "--deadline-s"),
                 ("b4-mech-1", 2, True, None, SCHED1, "--deadline-s"), ("b4-mech-1", 1, 60, None, SCHED1, "schedule's 2 pairs"),
                 ("b4-mech-1", 1, 60, None, sim.FixtureSchedule("b4-mech-1", ((7, 1000001),)), "already-exposed"),
                 ("b4-mech-1", 1, 60, None, sim.FixtureSchedule("b4-mech-1", ((7, 7),)), "equal"),
                 ("b4-mech-1", 2, 60, None, SCHED2, "its label is not the batch's"),
                 ("b4-mech-1", 2, 60, Path(self.tmp.name) / "elsewhere" / "b4-mech-1_x", "directly under", SCHED1),
                 ("b4-mech-1", 2, 60, self.ns / "other_x", "begin with b4-mech-1_", SCHED1),
                 ("b4-mech-1", 2, 60, self.ns / ".." / "sim" / "b4-mech-1_dots", "written plainly", SCHED1)]
        for case in cases:
            label, S, dl, out, a, b = case
            schedule, msg = (a, b) if isinstance(a, (sim.FixtureSchedule, type(None))) else (b, a)
            res = sim.run_batch(self.root, label, S, dl, out, schedule=schedule)
            self.assertEqual((res["status"], res["exit_code"]), ("refused", 2), case)
            self.assertIn(msg, res["reason"], case)
        existing = self.ns / "b4-mech-1_exists"
        existing.mkdir(parents=True)
        res = sim.run_batch(self.root, "b4-mech-1", 2, 60, existing, schedule=SCHED1)
        self.assertEqual(res["status"], "refused"); self.assertIn("exists", res["reason"])
        self.assertEqual(sorted(os.listdir(existing)), [], "nothing written inside an existing directory")
        existing.rmdir()
        link = self.ns / "b4-mech-1_link"
        link.symlink_to(Path(self.tmp.name))
        res = sim.run_batch(self.root, "b4-mech-1", 2, 60, link, schedule=SCHED1)
        self.assertEqual(res["status"], "refused"); link.unlink()
        (self.root / "dirty.txt").write_text("x")
        res = sim.run_batch(self.root, "b4-mech-1", 2, 60, self.out(), schedule=SCHED1)
        self.assertEqual(res["status"], "refused"); self.assertIn("not clean", res["reason"])
        (self.root / "dirty.txt").unlink()
        after = sorted(p.name for p in self.ns.iterdir()) if self.ns.exists() else []
        self.assertEqual(before, after, "a refusal creates no run directory")
        self.assertFalse(git(self.root, "status", "--porcelain").strip())
        self.assertEqual([m.call_count for m in self.guard_mocks], [0, 0], "no refusal reached a derivation")

    def test_a_symlinked_namespace_is_refused_at_every_level(self):
        """F7: evidence/b4/sim, evidence/b4 or evidence as a tracked symlink to a directory outside the root — the pre-flight
        refuses; the outside directory stays empty."""
        for level in ("evidence/b4/sim", "evidence/b4", "evidence"):
            with tempfile.TemporaryDirectory(prefix="b4mech_sym_") as tmp:
                root = build_hermetic(Path(tmp) / "root")
                outside = Path(tmp) / "outside"; outside.mkdir()
                link = root / level
                if link.exists():                                  # the inputs under it stay readable through the symlink: only the chain is wrong
                    shutil.copytree(link, outside, dirs_exist_ok=True)
                    shutil.rmtree(link)
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(outside, target_is_directory=True)
                git(root, "add", "-A"); git(root, "commit", "-q", "-m", "symlink namespace")
                res = sim.run_batch(root, "b4-mech-1", 2, 60, root / sim.SIM_REL / "b4-mech-1_probe", schedule=SCHED1)
                self.assertEqual((res["status"], res["exit_code"]), ("refused", 2), level)
                self.assertIn("real directory chain", res["reason"], f"{level}: refused by the PRE-FLIGHT's chain check (not only by the re-check at creation)")
                before = sorted(str(p.relative_to(outside)) for p in outside.rglob("*"))
                self.assertFalse(any("b4-mech-1_" in x for x in before), f"{level}: nothing written through the symlink")
                res = sim.run_batch(root, "b4-mech-1", 2, 60, None, schedule=SCHED1)
                self.assertEqual(res["status"], "refused", f"{level}: the default output path is refused too")
                self.assertEqual(sorted(str(p.relative_to(outside)) for p in outside.rglob("*")), before)

    def test_the_cli_has_no_fixture_path(self):
        """The CLI accepts production labels only and cannot build a schedule: a mechanics label is refused before any tree is read."""
        with mock.patch.object(sim, "porcelain", side_effect=AssertionError("the tree was read")):
            with mock.patch("sys.stdout"):
                code = sim.main(["--label", "b4-mech-1", "--seeds", "2", "--deadline-s", "60"])
        self.assertEqual(code, 2)


class CompleteBatch(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.seen = []

        def factory(fabric, role, pair):
            cls.seen.append((pair, role, (cls.out_dir / "seeds.json").exists(), (cls.out_dir / "manifest.json").exists()))
            return ex.ObservationPort(fabric)
        cls.out_dir = cls.ns / "b4-mech-1_complete"
        cls.head_at_run = git(cls.root, "rev-parse", "HEAD").strip()
        cls.res = sim.run_batch(cls.root, "b4-mech-1", 2, 3600, cls.out_dir, port_factory=factory, schedule=SCHED1)
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
        self.assertEqual(sv.verify_run_dir(out, deep=True), {}, "the archive-wide verifier is clean on the untouched archive")
        rep = self.report(res)
        self.assertEqual(rep["status"], "complete"); self.assertIsNone(rep["stopped"]); self.assertEqual(rep["missing"], [])
        self.assertEqual(rep["self_validation"], {}); self.assertTrue(rep["fixture"]); self.assertFalse(rep["deadline"]["expired"])
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
        self.assertEqual({e["path"] for e in rep["files"]}, set(names) - {"sim_report.json"})
        for e in rep["files"]:
            self.assertEqual(sim.sha_file(out / e["path"]), e["sha256"], e["path"])

    def test_the_freezing_order_the_fixture_seeds_and_the_manifest(self):
        self.assertTrue(self.seen, "ports were created")
        self.assertTrue(all(s and m for _, _, s, m in self.seen), "seeds.json and manifest.json existed before every port was created")
        self.assertEqual([(p, role) for p, role, _, _ in self.seen], [(p, role) for p in (0, 1) for role in list(ROLES) + ["K9", "K10"]], "one worker, the fixed order")
        seeds = json.loads((self.out_dir / "seeds.json").read_text())
        self.assertEqual(bs.seeds_doc_findings(seeds), [])
        self.assertEqual((seeds["fixture"], seeds["master_seed"], seeds["anchor"]["hypothesis_sha256"], seeds["label"]), (True, None, None, "b4-mech-1"))
        self.assertIn("fixture", seeds["anchor"]["rule"])
        self.assertEqual(seeds["pairs"], [[7, 11], [8, 12]], "the schedule, as given; nothing derived")
        self.assertEqual(len(seeds["exclusion"]["sources"]), 38)
        self.assertEqual(seeds["exclusion"]["sim_registry"], [], "the first batch: no archived set yet")
        self.assertEqual([m.call_count for m in self.guard_mocks], [0, 0], "no production derivation was reached by the complete batch")
        man = json.loads((self.out_dir / "manifest.json").read_text())
        self.assertEqual(sc.manifest_findings(man), [])
        self.assertEqual(man["head"], self.head_at_run, "the HEAD the batch ran under (the archive commit came after)")
        self.assertEqual(man["inputs"][hy.HYPOTHESIS_REL], hy.HYPOTHESIS_SHA256)
        self.assertTrue(man["fixture"])
        for rel, _, sha in bs.FIELDS:
            self.assertEqual(man["inputs"].get(rel), sha, f"F9: the exclusion source {rel} is bound at the start")
        vendors = {str(Path(s["root"]) / s["path"]): s["sha256"] for s in hy.load().doc["sources"] if "root" in s}
        self.assertEqual(len(vendors), 6); self.assertEqual(man["external_inputs"], vendors, "F9: the six external sources are bound by absolute path and digest")
        self.assertEqual(man["exclusion"]["registry_snapshot"], [])
        self.assertFalse(man["code_root"]["same_as_input_root"], "a hermetic input root is not the code root")
        self.assertIn("b4/host/b4_sim.py", man["tool_files"]); self.assertIn("b4/host/b4_sim_verify.py", man["tool_files"])
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
            k9 = json.loads((self.out_dir / f"pair_{r:03d}/k9.json").read_text()); self.assertTrue(k9["complete"]); self.assertIsNone(k9["invalid"])
            k10r = json.loads((self.out_dir / f"pair_{r:03d}/k10.json").read_text()); self.assertTrue(k10r["complete"])
            self.assertEqual([(u["background_index"], u["a"], u["b"]) for u in k10r["units"]], k10.canonical_units())
            cv = json.loads((self.out_dir / f"pair_{r:03d}/curves.json").read_text())
            self.assertTrue(cv["f_end_to_end_at_grid"][0]["mapping_in_progress"]); self.assertFalse(cv["f_end_to_end_at_grid"][-1]["mapping_in_progress"])

    def test_a_second_fixture_batch_lists_the_first_in_its_registry(self):
        out2 = self.ns / "b4-mech-2_second"
        res = sim.run_batch(self.root, "b4-mech-2", 2, 3600, out2, schedule=SCHED2)
        self.assertEqual(res["status"], "complete", res.get("reason"))
        s1 = json.loads((self.out_dir / "seeds.json").read_text()); s2 = json.loads((out2 / "seeds.json").read_text())
        reg = s2["exclusion"]["sim_registry"]
        self.assertEqual([(r["status"], r["master_seed"], r["count"]) for r in reg], [("seeds_fixture", None, 4)])
        self.assertTrue(reg[0]["dir"].endswith("b4-mech-1_complete"))
        self.assertEqual(s2["exclusion"]["pooled_total"], s1["exclusion"]["pooled_total"], "fixture values are already in the pool: the pooled total does not grow")
        man2 = json.loads((out2 / "manifest.json").read_text())
        self.assertEqual(man2["exclusion"]["registry_snapshot"], [[reg[0]["dir"], "seeds_fixture", reg[0]["seeds_sha256"]]])
        self.assertEqual(s2["pairs"], [[3, 13], [5, 12]])
        self.assertEqual([m.call_count for m in self.guard_mocks], [0, 0])


class InvalidStops(Base):
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
        self.assertEqual(rep["self_validation"], {}, "an invalid archive still verifies as the archive of its recorded state")
        self.assertEqual(sv.verify_run_dir(out, deep=True), {})

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
        k10d = json.loads((Path(res["out"]) / "pair_000/k10.json").read_text())
        self.assertFalse(k10d["complete"]); self.assertIsNotNone(k10d["invalid"]); self.assertFalse(k10d["units"][-1]["comparable"])
        self.assertEqual(len(k10d["units"][-1]["illegal_corners"]), 1)
        self.assertEqual((k10d["memo"]["port_calls"], len(k10d["observations"])), (100, 99), "F5: the refused call was the last one; nothing was observed after it")
        self.assertEqual(self.report(res)["pairs"][0]["k10"], "invalid")
        self.assertTrue((Path(res["out"]) / "pair_000/k9.json").exists())
        self.assertEqual(sv.verify_run_dir(Path(res["out"]), deep=True), {})

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

    def test_a_malformed_returned_result_is_quarantined_not_lost(self):
        """F6: the engine returns a RunResult with completed = 1 (not the bool True): the pre-write validator refuses it, the
        object is kept raw in a quarantine file with the findings, the arm's state says so, the batch is invalid."""
        orig = sim.be.run

        def malformed(*a, **kw):
            x = orig(*a, **kw)
            x.completed = 1
            return x
        with mock.patch.object(sim.be, "run", malformed):
            res = self.run_with(None)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["stage"], res["stopped"]["role"]), ("invalid", 1, "schema", "engine_return", "R"))
        out = Path(res["out"])
        self.assertFalse((out / "pair_000/arm_R.result.json").exists(), "an object that does not validate is never written as the result")
        q = json.loads((out / "pair_000/arm_R.result.QUARANTINE.json").read_text())
        self.assertEqual(sc.quarantine_findings(q), [])
        self.assertEqual(q["raw"]["result"]["completed"], 1, "the returned object, raw")
        self.assertTrue(any("completed" in f for f in q["findings"]))
        rep = self.report(res)
        self.assertEqual(rep["pairs"][0]["arms"]["R"], "result_malformed")
        self.assertEqual(sv.verify_run_dir(out, deep=True), {})

    def test_a_refusal_inside_k9_keeps_the_partial(self):
        """F6: a DOMAIN at K9's second observation — the first observation and the pair in progress are on disk, the plan says
        `invalid`, the batch is k9_invalid; the archive verifies as the archive of that state."""
        def factory(fabric, role, pair):
            return InjectingPort(fabric, 2) if (pair, role) == (0, "K9") else ex.ObservationPort(fabric)
        res = self.run_with(factory)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["role"], res["stopped"]["stage"]), ("invalid", "k9_invalid", "K9", "k9"))
        out = Path(res["out"])
        k9d = json.loads((out / "pair_000/k9.json").read_text())
        self.assertEqual((k9d["complete"], k9d["stopped"], k9d["pairs_done"], len(k9d["observations"]), k9d["summary"]), (False, None, 0, 1, None))
        self.assertEqual((k9d["invalid"]["pair_index"], k9d["invalid"]["exception"]), (0, "DomainRefusal"))
        self.assertEqual(self.report(res)["pairs"][0]["k9"], "invalid")
        self.assertNotIn("no partial record", res["stopped"]["detail"])
        self.assertEqual(sv.verify_run_dir(out, deep=True), {})

    def test_a_bad_q_cell_from_the_source_is_never_archived_as_complete(self):
        """F3: a source trace with a q cell of 2 — the K9 record returned does not validate, is quarantined, and the batch is
        invalid (schema), never complete with exit 0."""
        def factory(fabric, role, pair):
            return BadGridPort(fabric) if (pair, role) == (0, "K9") else ex.ObservationPort(fabric)
        res = self.run_with(factory)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["role"]), ("invalid", 1, "schema", "K9"))
        out = Path(res["out"])
        self.assertFalse((out / "pair_000/k9.json").exists())
        q = json.loads((out / "pair_000/k9.QUARANTINE.json").read_text())
        self.assertEqual(sc.quarantine_findings(q), [])
        self.assertTrue(any("q_grid" in f for f in q["findings"]), q["findings"][:3])
        self.assertEqual(q["raw"]["observations"][0]["q_grid"][0][0], 2, "the bad readout is kept raw, where it was")
        self.assertEqual(self.report(res)["pairs"][0]["k9"], "invalid")
        self.assertEqual(sv.verify_run_dir(out, deep=True), {})

    def test_an_unexpected_exception_and_the_three_drifts(self):
        def factory(fabric, role, pair):
            return RaisingPort(fabric, 7, RuntimeError("boom")) if (pair, role) == (0, "O") else ex.ObservationPort(fabric)
        res = self.run_with(factory)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["role"]), ("invalid", "unexpected_exception", "O"))
        rep = self.report(res)
        self.assertEqual(rep["pairs"][0]["arms"]["O"], "result_unavailable"); self.assertEqual(rep["pairs"][0]["arms"]["F"], "audited")
        self.assertTrue((Path(res["out"]) / "pair_000/arm_F.audit.json").exists(), "the six arms before it are not lost")
        self.assertIn("RuntimeError", res["stopped"]["detail"])
        self.tearDown()
        # an input drift: the architecture document edited during pair 1
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
        self.assertIn("the input docs/b4_architecture.md changed", res["stopped"]["detail"])
        self.assertTrue((Path(res["out"]) / "pair_001/k10.json").exists(), "the pair's work is kept; the drift is caught at its checkpoint")
        self.assertIsNone(self.report(res)["summary"])
        self.tearDown()
        # F9: an exclusion source (one of the 38) edited during pair 0
        src = self.root / bs.FIELDS[0][0]
        orig_src = src.read_bytes()

        def drift_source(fabric, role, pair):
            if (pair, role) == (0, "X"):
                src.write_bytes(orig_src + b"\n")
            return ex.ObservationPort(fabric)
        try:
            res = self.run_with(drift_source)
        finally:
            src.write_bytes(orig_src)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["stage"]), ("invalid", "input_drift", "pair 0 end"))
        self.assertIn(bs.FIELDS[0][0], res["stopped"]["detail"])
        self.tearDown()
        # F9: an external (vendor) source changing its digest — simulated through the digest function, the vendor file untouched
        vendor = next(str(Path(s["root"]) / s["path"]) for s in hy.load().doc["sources"] if "root" in s)
        real_sha = sim.sha_file
        state = {"armed": False}

        def sha(p):
            if state["armed"] and str(p) == vendor:
                return "0" * 64
            return real_sha(p)

        def arm_external(fabric, role, pair):
            if (pair, role) == (0, "A0"):
                state["armed"] = True
            return ex.ObservationPort(fabric)
        with mock.patch.object(sim, "sha_file", sha):
            res = self.run_with(arm_external)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["stage"]), ("invalid", "input_drift", "pair 0 end"))
        self.assertIn("external source", res["stopped"]["detail"]); self.assertIn(vendor, res["stopped"]["detail"])
        self.tearDown()
        # F9: a foreign run directory appearing in the namespace during the batch (the registry snapshot drifts)
        foreign = self.ns / "b4-mech-9_foreign"

        def drift_registry(fabric, role, pair):
            if (pair, role) == (0, "D"):
                foreign.mkdir()
                (foreign / "INIT_FAILED.json").write_text(json.dumps({"schema": "b4_sim_init_failed", "schema_version": "1.0.0", "label": "b4-mech-9", "seeds_derived": False, "reason": "x", "generated_utc": "x"}))
            return ex.ObservationPort(fabric)
        try:
            res = self.run_with(drift_registry)
        finally:
            shutil.rmtree(foreign, ignore_errors=True)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["stage"]), ("invalid", "input_drift", "pair 0 end"))
        self.assertIn("registry changed", res["stopped"]["detail"])

    def test_an_input_drift_during_the_final_verification_is_invalid(self):
        """R5: the architecture document changes while the deep verification runs (after it returns clean) — the final
        checkpoint after the verification catches it: invalid, input_drift, stage publication, no success published."""
        arch = self.root / "docs/b4_architecture.md"
        original = arch.read_bytes()
        real = sv.verify_run_dir

        def drift_late(*a, **kw):
            f = real(*a, **kw)
            if kw.get("deep"):
                arch.write_bytes(original + b"\n<!-- drift during the final verification -->\n")
            return f
        try:
            with mock.patch.object(sv, "verify_run_dir", side_effect=drift_late):
                res = self.run_with(None)
        finally:
            arch.write_bytes(original)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["stage"]), ("invalid", 1, "input_drift", "publication"))
        self.assertIn("docs/b4_architecture.md", res["stopped"]["detail"])
        self.assertIsNone(self.report(res)["summary"])

    def test_self_validation_findings_and_an_unwritable_report_are_never_complete(self):
        """F4: a finding of the batch's own archive-wide verification turns a would-be complete batch invalid (exit 1, no
        summary, STOPPED written); a report that cannot be validated leaves no sim_report.json, an ERROR file, status invalid, exit 1."""
        with mock.patch.object(sv, "verify_run_dir", return_value={"file": ["injected corruption"]}):
            res = self.run_with(None)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["stage"]), ("invalid", 1, "self_validation", "finalisation"))
        out = Path(res["out"])
        self.assertTrue((out / "STOPPED.json").exists())
        rep = self.report(res)
        self.assertEqual((rep["status"], rep["summary"], rep["self_validation"]), ("invalid", None, {"file": ["injected corruption"]}))
        self.assertEqual(sc.report_findings(rep), [])
        self.tearDown()
        real_write = sim.Batch.write

        def failing_report_write(self_, rel, doc, validator):
            if rel == "sim_report.json":
                raise sim.Invalid("schema", "injected report validation error", stage="write")
            return real_write(self_, rel, doc, validator)
        with mock.patch.object(sim.Batch, "write", failing_report_write):
            res = self.run_with(None)
        self.assertEqual((res["status"], res["exit_code"], res["original_status"]), ("invalid", 1, "complete"), "the batch had completed; the report could not be written: invalid")
        out = Path(res["out"])
        self.assertFalse((out / "sim_report.json").exists()); self.assertTrue((out / "sim_report.ERROR.txt").exists())
        self.assertIn("injected report validation error", res["report_error"])
        self.assertIn("missing", sv.verify_run_dir(out, deep=False).get("sim_report.json", []), "an archive without its report does not verify")


class IncompleteStops(Base):
    def test_the_deadline_inside_k9(self):
        clock = Clock(step=1.0)
        res = self.run_with(None, dl=60, clock=clock)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["role"]), ("incomplete", 3, "deadline", "K9"))
        out = Path(res["out"])
        k9d = json.loads((out / "pair_000/k9.json").read_text())
        self.assertFalse(k9d["complete"]); self.assertIsNone(k9d["summary"]); self.assertIsNone(k9d["invalid"]); self.assertGreater(k9d["pairs_done"], 0); self.assertLess(k9d["pairs_done"], 1184)
        for role in ROLES:
            self.assertTrue((out / f"pair_000/arm_{role}.audit.json").exists(), role)
        rep = self.report(res)
        self.assertEqual((rep["status"], rep["summary"]), ("incomplete", None))
        self.assertEqual(rep["pairs"][0]["k9"], "partial"); self.assertEqual(rep["pairs"][1]["status"], "not_started")
        self.assertTrue(rep["deadline"]["expired"]); self.assertEqual(rep["deadline"]["clock"], "time.monotonic")
        self.assertEqual(sv.verify_run_dir(out, deep=True), {})

    def test_the_deadline_in_the_statistics_and_an_interrupt(self):
        clock = Clock(step=0.0)

        def factory(fabric, role, pair):
            if (pair, role) == (1, "K10"):
                clock.jump_at, clock.jump = clock.calls + 423, 10 ** 6       # after K10's 421 checks and the curves' check
            return ex.ObservationPort(fabric)
        res = self.run_with(factory, dl=60, clock=clock)
        self.assertEqual((res["status"], res["stopped"]["kind"]), ("incomplete", "deadline"))
        self.assertIn(res["stopped"]["stage"], ("statistics", "curves"))
        out = Path(res["out"])
        self.assertTrue(json.loads((out / "pair_001/k10.json").read_text())["complete"], "K10 finished before the expiry")
        self.assertIsNone(self.report(res)["summary"], "no pooled summary without a complete statistics stage")
        self.tearDown()

        def interrupt(fabric, role, pair):
            return RaisingPort(fabric, 5, KeyboardInterrupt()) if (pair, role) == (0, "F") else ex.ObservationPort(fabric)
        res = self.run_with(interrupt)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["role"]), ("incomplete", 3, "interrupted", "F"))
        rep = self.report(res)
        self.assertEqual((rep["pairs"][0]["arms"]["R"], rep["pairs"][0]["arms"]["F"]), ("audited", "result_unavailable"))
        self.assertNotIn("DOMAIN", res["stopped"]["detail"])
        self.tearDown()

        def interrupt_k9(fabric, role, pair):
            return RaisingPort(fabric, 5, KeyboardInterrupt()) if (pair, role) == (0, "K9") else ex.ObservationPort(fabric)
        res = self.run_with(interrupt_k9)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["role"]), ("incomplete", "interrupted", "K9"))
        k9d = json.loads((Path(res["out"]) / "pair_000/k9.json").read_text())
        self.assertEqual((k9d["complete"], k9d["invalid"], len(k9d["observations"])), (False, None, 4), "F6: the partial before the interrupt is on disk, as a stop")
        self.assertIsNotNone(k9d["stopped"]); self.assertEqual(self.report(res)["pairs"][0]["k9"], "partial")

    def test_the_deadline_expiring_during_the_final_verification_is_incomplete(self):
        """R4: the clock crosses the deadline while the batch's own deep verification runs (after it returns clean) — the
        success is not published: incomplete, exit 3, no summary, the deadline record taken after the check says expired."""
        clock = Clock(step=0.0)
        real = sv.verify_run_dir

        def late(*a, **kw):
            f = real(*a, **kw)
            if kw.get("deep"):
                clock.t += 10000
            return f
        with mock.patch.object(sv, "verify_run_dir", side_effect=late):
            res = self.run_with(None, dl=60, clock=clock)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["stage"]), ("incomplete", 3, "deadline", "publication"))
        rep = self.report(res)
        self.assertIsNone(rep["summary"]); self.assertTrue(rep["deadline"]["expired"]); self.assertGreaterEqual(rep["deadline"]["elapsed_s"], 10000)
        self.assertTrue(all(p["status"] == "complete" for p in rep["pairs"]), "every pair's work is kept")

    def test_the_deadline_expiring_before_finalisation_is_incomplete(self):
        """F8: the clock crosses the deadline at the final input checkpoint — after the statistics, before finalisation: the
        batch is incomplete (exit 3), no summary, the deadline record says expired; never complete / exit 0."""
        clock = Clock(step=0.0)
        original_hold = sim.Batch.hold_inputs

        def hold(self_, stage):
            if stage == "final":
                clock.t += 10000
            return original_hold(self_, stage)
        with mock.patch.object(sim.Batch, "hold_inputs", hold):
            res = self.run_with(None, dl=60, clock=clock)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"]), ("incomplete", 3, "deadline"))
        self.assertIn(res["stopped"]["stage"], ("final", "finalisation"))
        rep = self.report(res)
        self.assertIsNone(rep["summary"]); self.assertTrue(rep["deadline"]["expired"])
        self.assertTrue(all(p["status"] == "complete" for p in rep["pairs"]), "every pair's work is kept")
        self.assertEqual(sc.report_findings(rep), [])

    def test_a_stop_at_the_deadline_boundary_still_writes_stopped_json(self):
        """The owner's review of 2026-10-19 (finding 2), the full-batch form: an external interrupt at the K9 entry while the
        monotonic clock crosses the deadline between the stop record's and the report's samples (1059.990 / 1060.010 /
        1060.030 after a start of 1000.000, through the public clock argument, the record method untouched). Before: the
        stop record contradicted itself, failed its own pre-write validation and STOPPED.json was not written. Now: STOPPED.json
        (not yet expired at 59.99 s), the report (expired at 60.01 s), the original stop cause kept, offline verification clean.
        Then the same with the stop itself past the boundary: STOPPED expired, first expiry equal to its elapsed time."""
        class Values:
            def __init__(self):
                self.t, self.queue = 1000.0, []

            def __call__(self):
                if self.queue:
                    self.t = self.queue.pop(0)
                return self.t
        for queue, stop_expired, stop_first in (([1059.990, 1060.010, 1060.030, 1060.050], False, None), ([1060.010, 1060.030, 1060.050, 1060.070], True, 60.01)):
            clock = Values()

            def interrupt(*a, **kw):
                clock.queue = list(queue)
                raise KeyboardInterrupt("an external interruption at the K9 entry")
            with mock.patch.object(sim.k9, "coverage", side_effect=interrupt):
                res = self.run_with(None, dl=60, clock=clock, S=1, schedule=SCHED_ONE)
            out = Path(res["out"])
            self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["role"]), ("incomplete", 3, "interrupted", "K9"))
            self.assertTrue((out / "STOPPED.json").exists(), "the stop record is written at the boundary")
            self.assertNotIn("STOPPED.json not written", res["stopped"]["detail"])
            stopped, rep = json.loads((out / "STOPPED.json").read_text()), self.report(res)
            self.assertEqual((stopped["kind"], stopped["deadline"]["expired"], stopped["deadline"]["first_expired_at_s"]), ("interrupted", stop_expired, stop_first))
            self.assertEqual((stopped["deadline"]["elapsed_s"], rep["deadline"]["elapsed_s"]), (round(queue[0] - 1000.0, 3), round(queue[1] - 1000.0, 3)))
            self.assertTrue(rep["deadline"]["expired"]); self.assertEqual(rep["deadline"]["first_expired_at_s"], 60.01)
            self.assertEqual((rep["status"], rep["summary"], rep["stopped"]["kind"]), ("incomplete", None, "interrupted"))
            # nothing returned from K9 before the interrupt: the stage is recorded as entered (`in_progress`), not as a
            # `partial` that would promise a stopped document the directory does not hold
            self.assertEqual(rep["pairs"][0]["k9"], "in_progress"); self.assertFalse((out / "pair_000/k9.json").exists())
            self.assertEqual(sv.verify_run_dir(out, deep=True), {})
            self.tearDown()


def entry(p: Path, rel: str) -> dict:
    b = p.read_bytes()
    return {"path": rel, "sha256": sim.sha_bytes(b), "size": len(b)}


def reindex(out: Path) -> None:
    """Refresh every digest a tampered archive carries (the pair index, the report's file index and identity) so that the
    verifier's finding, if any, comes from the contract and not from a stale hash (the owner's probe method)."""
    idx = json.loads((out / "pair_000/index.json").read_text())
    idx["files"] = [entry(p, p.name) for p in sorted((out / "pair_000").iterdir()) if p.is_file() and p.name != "index.json"]
    (out / "pair_000/index.json").write_text(json.dumps(idx, sort_keys=True, indent=1) + "\n")
    rep = json.loads((out / "sim_report.json").read_text())
    rep["files"] = [entry(p, str(p.relative_to(out))) for p in sorted(out.rglob("*")) if p.is_file() and p.name != "sim_report.json"]
    rep["identity"]["seeds_sha256"] = sim.sha_file(out / "seeds.json"); rep["identity"]["manifest_sha256"] = sim.sha_file(out / "manifest.json")
    (out / "sim_report.json").write_text(json.dumps(rep, sort_keys=True, indent=1) + "\n")


class TheArchiveVerifier(Base):
    """F2 / F3 and the owner's second review R1–R3: the archive-wide verifier on a complete S = 1 fixture archive, tampered one
    way at a time with every digest refreshed (every file restored after), so that each finding is the contract's."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.out_dir = cls.ns / "b4-mech-1_verify"
        cls.res = sim.run_batch(cls.root, "b4-mech-1", 1, 3600, cls.out_dir, schedule=SCHED_ONE)
        assert cls.res["status"] == "complete", cls.res
        cls.originals = {str(p.relative_to(cls.out_dir)): p.read_bytes() for p in cls.out_dir.rglob("*") if p.is_file()}
        cls.task = bl.make_task(7, bm.site_mapping().addresses)
        git(cls.root, "add", "-A"); git(cls.root, "commit", "-q", "-m", "archive verify")

    def restore(self):
        for rel, b in self.originals.items():
            p = self.out_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists() or p.read_bytes() != b:
                p.write_bytes(b)
        for p in list(self.out_dir.rglob("*")):
            if p.is_file() and str(p.relative_to(self.out_dir)) not in self.originals:
                p.unlink()

    def load(self, rel):
        return json.loads(self.originals[rel])

    def put(self, rel, doc):
        (self.out_dir / rel).write_text(json.dumps(doc))

    def findings(self, deep=True):
        try:
            return sv.verify_run_dir(self.out_dir, deep=deep)
        finally:
            self.restore()

    def test_the_untouched_archive_is_clean_and_every_tamper_is_named(self):
        self.assertEqual(self.findings(), {})
        d = self.load("pair_000/curves.json"); d["best_at_grid"]["O"] = [0] * len(th.GRID); self.put("pair_000/curves.json", d)
        f = self.findings(); self.assertIn("pair_000/curves.json", f, f)
        (self.out_dir / "pair_000/arm_R.result.json").unlink()
        f = self.findings(); self.assertTrue(any("missing" in x for x in f.get("pair_000/arm_R.result.json", [])), f)
        d = self.load("sim_report.json"); d["summary"]["per_budget"]["8"]["deltas"]["delta1_O_minus_R"]["mean"] = 999; self.put("sim_report.json", d)
        f = self.findings(); self.assertTrue(any("pooled summary" in x for x in f.get("sim_report.json", [])), f)
        (self.out_dir / "stray.json").write_text("{}")
        f = self.findings(); self.assertIn("stray.json", f)
        (self.out_dir / "STOPPED.json").write_text("{}")
        f = self.findings(); self.assertIn("STOPPED.json", f)
        d = self.load("manifest.json"); d["arm_order"] = None; self.put("manifest.json", d)
        f = self.findings(); self.assertTrue(any("arm_order" in x for x in f.get("manifest.json", [])), f)
        self.assertEqual(self.findings(), {}, "restored")

    def test_the_comparison_sets_and_the_cell_types_are_enforced_by_the_validators(self):
        d = self.load("pair_000/k10.json")
        d["units"] = [json.loads(json.dumps(d["units"][0])) for _ in range(420)]
        from b4_stats import classify, seed_max
        m, counts = seed_max(d["units"]); d.update(max_abs_index=m, comparable_pairs=counts["comparable_pairs"], not_comparable_pairs=counts["not_comparable_pairs"], outcome=classify(m, d["tau"]))
        self.assertTrue(any("not the fixed set's unit" in x for x in sc.k10_findings(d, self.task)))
        self.assertTrue(any("not the fixed set's unit" in x for x in k10.recompute(d, self.task)))
        self.put("pair_000/k10.json", d); f = self.findings(); self.assertIn("pair_000/k10.json", f)
        import b4_k9 as k9
        d = self.load("pair_000/k9.json"); d["pairs"] = []; d["pairs_done"] = 0; d["summary"] = k9.summarise([], bm.site_mapping()); d["logical_observations"] = 0
        self.assertTrue(any("fixed set has 1184" in x for x in sc.k9_findings(d, self.task)))
        self.put("pair_000/k9.json", d); f = self.findings(); self.assertIn("pair_000/k9.json", f)
        d = self.load("pair_000/k9.json"); d["observations"][0]["q_grid"][0][0] = 2
        self.assertTrue(any("q_grid" in x for x in sc.k9_findings(d, self.task)), "a q cell of 2 is named")
        d = self.load("pair_000/k9.json"); d["observations"][0]["id"] = 5
        self.assertTrue(sc.k9_findings(d, self.task), "a duplicated / shifted observation id is named")
        d = self.load("pair_000/k9.json"); d["landscape_seed"] = 8
        self.assertTrue(any("task's" in x for x in sc.k9_findings(d, self.task)), "the declared task is checked, not another user string")
        d = self.load("pair_000/k10.json"); d["units"][3]["corners"]["11"]["score"] += 1
        self.assertTrue(any("index" in x for x in sc.k10_findings(d, self.task)), "a score that no longer gives the index is named")
        for mutate in (lambda m: m.update(arm_order=None), lambda m: m.update(inputs=None), lambda m: m.update(grid="x"), lambda m: m.update(code_root=[])):
            d = self.load("manifest.json"); mutate(d)
            f = sc.manifest_findings(d)
            self.assertTrue(f and not any("raised" in x for x in f), (mutate, f))
        self.assertEqual(sc.k9_findings(None, self.task), ["k9: not an object"])
        self.assertTrue(sc.k10_findings({"schema": 1}, self.task))
        self.assertTrue(all(not x.startswith("k9_findings: the validator raised") for x in sc.k9_findings({k: None for k in sc.K9_KEYS | {"schema", "schema_version", "pair"}}, self.task)))

    def test_a_downgraded_arm_state_cannot_switch_the_audit_off(self):
        """R1: R's state set to `written` in the report and the pair index, its audit deleted, one bit of its final RNG state
        flipped, every digest refreshed — the planned-state validator, the pair-index validator and the deep verifier all name it."""
        out = self.out_dir
        rep = self.load("sim_report.json"); rep["pairs"][0]["arms"]["R"] = "written"; self.put("sim_report.json", rep)
        idx = self.load("pair_000/index.json"); idx["arms"]["R"] = "written"; self.put("pair_000/index.json", idx)
        (out / "pair_000/arm_R.audit.json").unlink()
        doc = self.load("pair_000/arm_R.result.json"); doc["result"]["rng_state_final"] ^= 1; self.put("pair_000/arm_R.result.json", doc)
        reindex(out)
        rep2 = json.loads((out / "sim_report.json").read_text())
        self.assertTrue(any("weaker state" in x for x in sc.report_findings(rep2)), "the planned record alone is refused")
        self.assertTrue(any("every arm audited" in x for x in sc.pair_index_findings(json.loads((out / "pair_000/index.json").read_text()))))
        f = self.findings()
        self.assertTrue(f, "the archive does not verify")
        self.assertTrue(any("not audited" in x or "weaker" in x for xs in f.values() for x in xs), f)
        # the same with the report left saying `audited` but the audit deleted and the RNG flipped: the deep re-audit names the RNG
        (out / "pair_000/arm_R.audit.json").unlink()
        doc = self.load("pair_000/arm_R.result.json"); doc["result"]["rng_state_final"] ^= 1; self.put("pair_000/arm_R.result.json", doc)
        reindex(out)
        f = self.findings()
        self.assertTrue(any("re-audit" in x or "missing" in x for xs in f.values() for x in xs), f)

    def test_the_deep_verifier_re_audits_even_if_the_record_validators_were_bypassed(self):
        """R1, defence in depth: with the planned-record and pair-index validators mocked to accept everything, a complete pair
        whose R is recorded `written` with no audit file and a flipped RNG state is still refused by the deep stage itself."""
        out = self.out_dir
        rep = self.load("sim_report.json"); rep["pairs"][0]["arms"]["R"] = "written"; self.put("sim_report.json", rep)
        idx = self.load("pair_000/index.json"); idx["arms"]["R"] = "written"; self.put("pair_000/index.json", idx)
        (out / "pair_000/arm_R.audit.json").unlink()
        doc = self.load("pair_000/arm_R.result.json"); doc["result"]["rng_state_final"] ^= 1; self.put("pair_000/arm_R.result.json", doc)
        reindex(out)
        real_report, real_index = sc.report_findings, sc.pair_index_findings
        try:
            with mock.patch.object(sc, "report_findings", lambda d: []), mock.patch.dict(sc.VALIDATORS, {"index.json": lambda d: []}):
                f = sv.verify_run_dir(out, deep=True)
        finally:
            self.restore()
        self.assertTrue(any("not audited" in x for x in f.get("pair_000/arm_R.result.json", [])), f)
        self.assertIs(sc.report_findings, real_report); self.assertIs(sc.VALIDATORS["index.json"], real_index)

    def test_every_record_is_bound_to_the_planned_pair_and_the_formal_source(self):
        """R2: a self-consistent R from ANOTHER exposed operator seed (12) under a plan that says 11 — replay accepts it, the
        verifier must not; a wrapper naming another pair / role; a manifest whose fabric / mapping / constants are not the formal ones."""
        import b4_engine as be
        import b4_snapshot as sn
        out = self.out_dir
        task = self.task
        fabric = sim.fm.Fabric(bm.site_mapping(), hy.load())
        port = ex.ObservationPort(fabric)
        d = be.run("R", task, port, 12, sim.B_MAX).as_dict()
        doc = self.load("pair_000/arm_R.result.json"); doc.update(operator_seed=12, result=d, port_calls=port.calls); self.put("pair_000/arm_R.result.json", doc)
        rc = sn.recompute_findings(d, task)
        aud = self.load("pair_000/arm_R.audit.json")
        aud.update(completion_findings=sim.completion_findings(d, "R", task, port.calls, None), replay_findings=br.replay(d, task),
                   recompute={k: v for k, v in rc.items() if k != "relations_final"} | {"relations_final_sha256": ex.sha256_json(rc["relations_final"])},
                   states=sn.arm_states(d, task), view_findings=[], invalid=False)
        self.put("pair_000/arm_R.audit.json", aud)
        self.assertEqual(br.replay(d, task), [], "the foreign result replays clean under its own seed: replay alone cannot see the plan")
        results = {role: self.load(f"pair_000/arm_{role}.result.json")["result"] for role in ROLES}; results["R"] = d
        curves = sim.curves_of(results, 0, 7, 11); self.put("pair_000/curves.json", curves)
        reindex(out)
        f = self.findings()
        self.assertTrue(any("planned" in x and "11" in x for xs in f.values() for x in xs), f)
        # a wrapper naming another pair and role
        doc = self.load("pair_000/arm_R.result.json"); doc.update(pair=99, role="O"); self.put("pair_000/arm_R.result.json", doc); reindex(out)
        f = self.findings()
        self.assertTrue(any("planned" in x for xs in f.values() for x in xs), f)
        doc = self.load("pair_000/curves.json"); doc["operator_seed"] = 12; self.put("pair_000/curves.json", doc); reindex(out)
        f = self.findings(); self.assertTrue(any("planned pair" in x for xs in f.values() for x in xs), f)
        # the manifest's descriptors are the formal inputs', not merely well-formed
        for mutate, why in ((lambda m: m.update(fabric={"kind": "dropout"}), "fabric"), (lambda m: m["mapping"].update(addresses=[None] * 21), "mapping"),
                            (lambda m: m["hypothesis"].update(version="0.2.1"), "hypothesis"), (lambda m: m["constants"]["engine"].update(mu=5), "constants")):
            man = self.load("manifest.json"); mutate(man); self.put("manifest.json", man); reindex(out)
            direct = sc.manifest_findings(man)
            f = self.findings()
            self.assertTrue(f, why)
            if why != "constants":
                self.assertTrue(any(why in x for x in direct), (why, direct))
            else:
                self.assertTrue(any("constants" in x for xs in f.values() for x in xs), f)
        self.assertEqual(self.findings(), {}, "restored")

    def test_nested_scalars_are_exact_in_type(self):
        """R3: an observation id of false, a float interaction index, a float count — equal in Python, refused by the validators
        and by the verifier after re-indexing (the finding is the type, not a hash)."""
        out = self.out_dir
        d = self.load("pair_000/k9.json"); d["observations"][0]["id"] = False
        self.assertTrue(any("int 0" in x for x in sc.k9_findings(d, self.task)), sc.k9_findings(d, self.task)[:3])
        self.put("pair_000/k9.json", d); reindex(out); self.assertIn("pair_000/k9.json", self.findings())
        d = self.load("pair_000/k10.json"); d["units"][0]["index"] = float(d["units"][0]["index"])
        self.assertTrue(any("index" in x for x in sc.k10_findings(d, self.task)))
        self.put("pair_000/k10.json", d); reindex(out); self.assertIn("pair_000/k10.json", self.findings())
        d = self.load("pair_000/k10.json"); d["logical_corners"] = float(d["logical_corners"])
        self.assertTrue(any("logical_corners" in x for x in sc.k10_findings(d, self.task)))
        d = self.load("pair_000/k10.json"); d["tau"] = 2.0
        self.assertTrue(any("tau" in x for x in sc.k10_findings(d, self.task)))
        d = self.load("pair_000/k9.json"); d["pairs"][0]["obs0"] = False
        self.assertTrue(sc.k9_findings(d, self.task))
        d = self.load("pair_000/k9.json"); d["logical_observations"] = float(d["logical_observations"])
        self.assertTrue(any("logical_observations" in x for x in sc.k9_findings(d, self.task)))
        d = self.load("sim_report.json"); d["summary"]["per_budget"]["8"]["deltas"]["delta1_O_minus_R"]["positives"] = float(d["summary"]["per_budget"]["8"]["deltas"]["delta1_O_minus_R"]["positives"])
        self.put("sim_report.json", d); reindex(out)
        f = self.findings(); self.assertTrue(any("pooled summary" in x for x in f.get("sim_report.json", [])), "a float where the recomputed summary has an int")
        self.assertEqual(self.findings(), {}, "restored")

    def test_a_genuine_partial_diagnostic_cannot_belong_to_a_complete_batch(self):
        """Round 3, finding 1: a VALID partial K10 (the production driver stopped by StopWork after one unit) and a valid
        partial K9 put under a plan that still says complete, the pooled summary and every digest recomputed — refused by the
        diagnostic state ↔ file contract, not by a hash."""
        from b4_deadline import StopWork
        import b4_k9 as k9
        out = self.out_dir
        fabric = sim.fm.Fabric(bm.site_mapping(), hy.load())
        n = {"k": 0}

        def one_unit():
            n["k"] += 1
            if n["k"] > 1:
                raise StopWork("stopped after one unit")
        partial = k10.seed_k10(self.task, ex.ObservationPort(fabric), check=one_unit)
        self.assertEqual((partial["complete"], len(partial["units"])), (False, 1))
        doc = self.load("pair_000/k10.json"); doc.update(partial); self.put("pair_000/k10.json", doc)
        self.assertEqual(sc.k10_findings(doc, self.task), [], "the partial is a valid record in itself")
        curves, k7, k9d = self.load("pair_000/curves.json"), self.load("pair_000/k7.json"), self.load("pair_000/k9.json")
        row = {"pair": 0, "landscape_seed": 7, "operator_seed": 11, "base_fit": curves["base_fit"], "best_at_grid": curves["best_at_grid"],
               "f_end_to_end_at_grid": [x["value"] for x in curves["f_end_to_end_at_grid"]], "k7_not_unknown_at_grid": [k7["prefixes"][str(B)]["not_unknown"] for B in th.GRID],
               "k9": k9d["summary"]["per_semantic"], "k9_all_seven": k9d["summary"]["all_seven_positive_controls"], "k10_max_abs": partial["max_abs_index"], "k10_outcome": partial["outcome"]}
        rep = self.load("sim_report.json"); rep["summary"] = sim.summarise_batch([row], 1)[0]; self.put("sim_report.json", rep); reindex(out)
        f = self.findings()
        self.assertTrue(any("k10: recorded complete" in x for xs in f.values() for x in xs), f)
        n["k"] = 0

        def three_pairs():
            n["k"] += 1
            if n["k"] > 3:
                raise StopWork("stopped after three pairs")
        p9 = k9.coverage(self.task, ex.ObservationPort(fabric), bm.site_mapping(), fabric, check=three_pairs)
        self.assertFalse(p9["complete"])
        doc = self.load("pair_000/k9.json"); doc.update(p9); self.put("pair_000/k9.json", doc); reindex(out)
        f = self.findings()
        self.assertTrue(any("k9: recorded complete" in x for xs in f.values() for x in xs), f)
        self.assertEqual(self.findings(), {}, "restored")

    def test_the_remaining_counts_and_genomes_are_exact_in_type(self):
        """Round 3, finding 2: pairs_total 1184.0, units_total 420.0, a corner genome of false, a float prefix budget — equal in
        Python, refused by the validators and, re-indexed, by the verifier."""
        out = self.out_dir
        d = self.load("pair_000/k9.json"); d["pairs_total"] = 1184.0
        self.assertTrue(sc.k9_findings(d, self.task)); self.put("pair_000/k9.json", d); reindex(out); self.assertIn("pair_000/k9.json", self.findings())
        d = self.load("pair_000/k10.json"); d["units_total"] = 420.0
        self.assertTrue(sc.k10_findings(d, self.task)); self.put("pair_000/k10.json", d); reindex(out); self.assertIn("pair_000/k10.json", self.findings())
        d = self.load("pair_000/k10.json"); d["units"][0]["corners"]["00"]["genome"] = False
        self.assertTrue(any("corners[00]" in x for x in sc.k10_findings(d, self.task))); self.put("pair_000/k10.json", d); reindex(out); self.assertIn("pair_000/k10.json", self.findings())
        d = self.load("pair_000/k7.json"); d["prefixes"]["8"]["budget"] = 8.0
        self.assertTrue(any("budget" in x for x in sc.k7_findings(d)))
        d = self.load("pair_000/k9.json"); d["pairs"][0]["backgrounds"] = [0.0, 1]
        self.assertTrue(sc.k9_findings(d, self.task))
        d = self.load("pair_000/curves.json"); d["f_end_to_end_at_grid"][0]["T"] = 8.0
        self.assertTrue(any("T is not the grid" in x for x in sc.curves_findings(d)))
        self.assertEqual(self.findings(), {}, "restored")

    def test_the_deadline_records_are_consistent_and_bound_to_the_manifest(self):
        """Round 3, finding 3: the manifest's deadline_s changed to 1 while the report says 3600; a report elapsed_s of 10 000
        with expired false; malformed records — each refused; a genuinely late stopped record stays acceptable."""
        out = self.out_dir
        man = self.load("manifest.json"); man["deadline_s"] = 1; self.put("manifest.json", man); reindex(out)
        f = self.findings(); self.assertTrue(any("not the declared 1" in x for x in f.get("sim_report.json", [])), f)
        rep = self.load("sim_report.json"); rep["deadline"].update(elapsed_s=10000.0, expired=False, first_expired_at_s=None)
        self.assertTrue(any("not expired with elapsed_s" in x for x in sc.report_findings(rep)))
        self.put("sim_report.json", rep); reindex(out); f = self.findings(); self.assertIn("sim_report.json", f)
        self.assertEqual(sc.deadline_findings({"seconds": 60, "elapsed_s": 60.0, "checks": 3, "expired": True, "first_expired_at_s": 60.0, "clock": "time.monotonic"}), [], "expired at the boundary")
        self.assertEqual(sc.deadline_findings({"seconds": 60, "elapsed_s": 59.999, "checks": 3, "expired": False, "first_expired_at_s": None, "clock": "time.monotonic"}), [])
        self.assertEqual(sc.deadline_findings({"seconds": 60, "elapsed_s": 10000.0, "checks": 3, "expired": True, "first_expired_at_s": 60.0, "clock": "time.monotonic"}), [], "a late stop is a consistent record")
        for bad, why in (({"seconds": 60, "elapsed_s": 10.0, "checks": 3, "expired": True, "first_expired_at_s": 10.0, "clock": "time.monotonic"}, "expired before the deadline"),
                         ({"seconds": 60, "elapsed_s": 61.0, "checks": 3, "expired": False, "first_expired_at_s": None, "clock": "time.monotonic"}, "not expired after it"),
                         ({"seconds": 60, "elapsed_s": 61.0, "checks": 3, "expired": True, "first_expired_at_s": None, "clock": "time.monotonic"}, "expired without a first expiry"),
                         ({"seconds": 60.0, "elapsed_s": 1.0, "checks": 3, "expired": False, "first_expired_at_s": None, "clock": "time.monotonic"}, "float seconds"),
                         ({"seconds": 60, "elapsed_s": 1.0, "checks": 3, "expired": False, "first_expired_at_s": None, "clock": "time.time"}, "another clock"),
                         ({"seconds": 60, "elapsed_s": 1.0, "checks": 3, "expired": False, "first_expired_at_s": None}, "a missing key")):
            self.assertTrue(sc.deadline_findings(bad), why)
        self.assertTrue(sc.deadline_findings({"seconds": 60, "elapsed_s": 1.0, "checks": 3, "expired": False, "first_expired_at_s": None, "clock": "time.monotonic"}, seconds=3600), "bound to another duration")
        self.assertEqual(self.findings(), {}, "restored")

    def test_a_malformed_diagnostic_is_a_named_finding_never_an_exception(self):
        """The owner's review of 2026-10-19 (finding 1): a K7 / K9 document replaced by a list, a K10 by a string, a K9
        with `pairs: 5`, null, an unreadable file — each with every digest refreshed — made the verifier raise
        AttributeError / TypeError out of the diagnostic state ↔ file contract instead of returning the typed finding.
        Now: the contract is asked only about documents their typed validator accepted, the helper itself is total, and
        the CLI reports a finding (exit 1) instead of a traceback."""
        out = self.out_dir
        cases = (("k7", json.dumps([])), ("k9", json.dumps([])), ("k10", json.dumps("malformed")), ("k9", json.dumps(None)), ("k9", json.dumps(5)),
                 ("k7", b"\x00{not json"), ("k9", json.dumps({**self.load("pair_000/k9.json"), "pairs": 5})),
                 ("k10", json.dumps({**self.load("pair_000/k10.json"), "units": "x"})), ("k10", json.dumps({**self.load("pair_000/k10.json"), "complete": "yes"})))
        for k, body in cases:
            f_path = out / f"pair_000/{k}.json"
            f_path.write_bytes(body if isinstance(body, bytes) else body.encode())
            reindex(out)
            f = self.findings()                                     # raises → the test errors: that is the regression
            self.assertIn(f"pair_000/{k}.json", f, (k, body[:40], f))
            self.assertNotIn("pair_000/", f, "the contract is not asked about a pair whose diagnostic did not validate")
        plan = {"pair": 0, "status": "complete", "k7": "complete", "k9": "complete", "k10": "complete"}
        for doc in ([], "x", 5, True, {"complete": True, "pairs": 5}, {"complete": True, "units": None}, {"complete": True}):
            self.assertTrue(sv.diagnostic_state_findings(plan, {"k7": doc, "k9": doc, "k10": doc}), doc)
        self.assertTrue(sv.diagnostic_state_findings({**plan, "k9": "partial"}, {"k9": []}))
        import io
        from contextlib import redirect_stdout
        (out / "pair_000/k9.json").write_text("[]"); reindex(out)
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                code = sv.main([str(out), "--shallow"])
        finally:
            self.restore()
        res = json.loads(buf.getvalue())
        self.assertEqual((code, res["clean"]), (1, False)); self.assertIn("pair_000/k9.json", res["findings"])
        buf = io.StringIO()
        with mock.patch.object(sv, "verify_run_dir", side_effect=RuntimeError("boom")), redirect_stdout(buf):
            code = sv.main([str(out), "--shallow"])
        res = json.loads(buf.getvalue())
        self.assertEqual((code, res["clean"]), (1, False)); self.assertIn("RuntimeError", res["findings"]["verifier"][0])
        self.assertEqual(self.findings(), {}, "restored")

    def test_the_cli_of_the_verifier(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = sv.main([str(self.out_dir), "--shallow"])
        self.assertEqual(code, 0); self.assertTrue(json.loads(buf.getvalue())["clean"])
        (self.out_dir / "pair_000/k7.json").unlink()
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                code = sv.main([str(self.out_dir), "--shallow"])
        finally:
            self.restore()
        self.assertEqual(code, 1); self.assertFalse(json.loads(buf.getvalue())["clean"])


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
        plan = {"pair": 0, "landscape_seed": 7, "operator_seed": 11, "status": "complete", "arms": {r: "audited" for r in ROLES}, "k7": "complete", "k9": "complete", "k10": "complete"}
        rep = {"schema": "b4_sim_report", "schema_version": "1.0.0", "status": "complete", "label": "b4-mech-1", "fixture": True, "count": 1, "head": "0" * 40, "generated_utc": "x",
               "deadline": {"seconds": 60, "elapsed_s": 1.5, "checks": 3, "expired": False, "first_expired_at_s": None, "clock": "time.monotonic"},
               "standing": "not a gate verdict", "thresholds": {}, "identity": {}, "pairs": [plan], "files": [], "stopped": None,
               "summary": {"k1_pass": True}, "missing": [], "self_validation": {}}
        self.assertTrue(any("verdict-like" in f for f in sc.report_findings(rep)))
        rep["summary"] = {"thresholds_for_reference": {}}
        self.assertEqual(sc.report_findings(rep), [], "'thresholds' is not a verdict word")
        rep["deadline"] = {"seconds": 60, "elapsed_s": 61.0, "checks": 3, "expired": True, "first_expired_at_s": 60.0, "clock": "time.monotonic"}
        self.assertTrue(any("expired" in f for f in sc.report_findings(rep)), "F8: a complete report's deadline has not expired")
        rep["deadline"] = {"seconds": 60, "elapsed_s": 1.5, "checks": 3, "expired": False, "first_expired_at_s": None, "clock": "time.monotonic"}; rep["self_validation"] = {"x": ["y"]}
        self.assertTrue(any("self-validation" in f for f in sc.report_findings(rep)), "F4: a complete report has no self-validation finding")
        rep["self_validation"] = {}; rep["pairs"][0]["arms"]["R"] = "written"
        self.assertTrue(any("weaker state" in f for f in sc.report_findings(rep)), "R1: a complete pair with an arm not audited is refused by the planned-record validator")
        rep["pairs"][0]["arms"]["R"] = "audited"; rep["pairs"][0]["k9"] = "partial"
        self.assertTrue(any("weaker state" in f for f in sc.report_findings(rep)))
        rep["pairs"][0]["k9"] = "complete"; rep["status"] = "invalid"
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

    def test_the_fixture_schedule_s_own_findings(self):
        self.assertEqual(SCHED1.findings(), [])
        self.assertTrue(sim.FixtureSchedule("b4-sim-1", ((7, 11),)).findings())
        self.assertTrue(any("already-exposed" in f for f in sim.FixtureSchedule("b4-mech-1", ((7, 4242),)).findings()))
        self.assertTrue(any("twice" in f for f in sim.FixtureSchedule("b4-mech-1", ((7, 11), (7, 11))).findings()))
        self.assertTrue(sim.FixtureSchedule("b4-mech-1", ()).findings())
        self.assertTrue(sim.FixtureSchedule("b4-mech-1", ((True, 11),)).findings())


def sc_semantics():
    import b4_k9 as k9
    return k9.SEMANTICS


if __name__ == "__main__":
    unittest.main()
