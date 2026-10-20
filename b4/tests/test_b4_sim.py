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

import contextlib
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
import b4_protocol as bp  # noqa: E402
import b4_replay as br  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim as sim  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_sim_verify as sv  # noqa: E402
import b4_target as bt  # noqa: E402
import b4_thresholds as th  # noqa: E402
from b4_test_fixtures import InjectingPort  # noqa: E402


def task_of(out: Path):
    """The (PublicTask, landscape seed) of a pair, rebuilt from the archive's task.json (task-v0.2: the task is a record of the setup, not a function of the seed)."""
    def f(r: int):
        d = json.loads((out / f"pair_{r:03d}/task.json").read_text())
        return bt.task_from_dict(d["public_task"]), d["landscape_seed"]
    return f


SETUP_FILES = list(bt.SETUP_FILES)

ROLES = sim.ROLES
SCHED1 = sim.FixtureSchedule("b4-mech-1", ((7, 11), (8, 12)))
SCHED2 = sim.FixtureSchedule("b4-mech-2", ((3, 13), (5, 12)))
SCHED_ONE = sim.FixtureSchedule("b4-mech-1", ((7, 11),))


def git(root: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True, text=True).stdout


def build_hermetic(dst: Path) -> Path:
    files = [f[0] for f in bs.FIELDS] + list(sim.ROOT_INPUTS) + [bs.EXPOSURE_RECEIPT_REL]   # the receipt copied in its own right (not only as a root input)
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
                 ("b4-gate-1", 2, 60, None, None, "exploration label"), ("b4-sim-4", 0, 60, None, None, "--seeds"), ("b4-sim-4", 2, 0, None, None, "--deadline-s"),
                 ("b4-sim-1", 2, 60, None, None, "retired"), ("b4-sim-2", 32, 3600, None, None, "retired"),      # the settlement of 2026-10-19: refused before any master
                 ("b4-sim-3", 32, 3600, None, None, "consumed"),                                                  # protocol v0.2.0: consumed by its archived records
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

    def test_a_retired_label_is_refused_before_the_tree_is_read(self):
        """The owner's ruling of 2026-10-19 (section 4): b4-sim-1 / b4-sim-2 are refused on the new-production-derivation path
        before any tree is read and before any master is formed — through the API and the CLI; the exploration label is not."""
        for label, word in (("b4-sim-1", "retired"), ("b4-sim-2", "retired"), ("b4-sim-3", "consumed")):
            with mock.patch.object(sim, "porcelain", side_effect=AssertionError("the tree was read")):
                res = sim.run_batch(self.root, label, 32, 3600, None)
                self.assertEqual((res["status"], res["exit_code"]), ("refused", 2)); self.assertIn(word, res["reason"]); self.assertIn("b4-sim-4", res["reason"])
                with mock.patch("sys.stdout"):
                    self.assertEqual(sim.main(["--label", label, "--seeds", "32", "--deadline-s", "3600"]), 2)
        with mock.patch.object(sim, "porcelain", side_effect=AssertionError("the tree was read")):
            res = sim.run_batch(self.root, "b4-gate-1", 200, 3600, None, mode="gate")
            self.assertEqual(res["status"], "refused"); self.assertIn("consumed", res["reason"]); self.assertIn("b4-gate-2", res["reason"])
        self.assertEqual([m.call_count for m in self.guard_mocks], [0, 0], "no retired or consumed label reached a derivation")
        self.assertEqual(bs.EXPLORATION_LABEL, "b4-sim-4"); bs.check_label_not_retired(bs.EXPLORATION_LABEL)
        self.assertEqual(th.THRESHOLDS["anchor"]["exploration_label"], bs.EXPLORATION_LABEL, "the table and the loader name the same next label")
        self.assertTrue(sim.LABEL_RE.match(bs.EXPLORATION_LABEL))

    def test_a_missing_or_rehashed_receipt_refuses_the_pre_flight(self):
        """The receipt is a root input: a root whose receipt is re-hashed or missing is refused before anything is written."""
        for variant in ("rehashed", "missing"):
            with tempfile.TemporaryDirectory(prefix="b4mech_rcpt_") as tmp:
                root = build_hermetic(Path(tmp) / "root")
                p = root / bs.EXPOSURE_RECEIPT_REL
                if variant == "rehashed":
                    p.write_bytes(p.read_bytes() + b"\n")
                else:
                    p.unlink()
                git(root, "add", "-A"); git(root, "commit", "-q", "-m", variant)
                res = sim.run_batch(root, "b4-mech-1", 2, 60, None, schedule=SCHED1)
                self.assertEqual((res["status"], res["exit_code"]), ("refused", 2), variant)
                self.assertIn("receipt", res["reason"], variant)
                self.assertFalse((root / sim.SIM_REL).exists(), f"{variant}: nothing written")

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

        cls.ports = []

        def factory(fabric, role, pair):
            cls.seen.append((pair, role, (cls.out_dir / "seeds.json").exists(), (cls.out_dir / "manifest.json").exists()))
            port = ex.ObservationPort(fabric)
            cls.ports.append((pair, role, port))
            return port
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
            want += [f"pair_{r:03d}/{n}" for n in SETUP_FILES]
        self.assertEqual(names, sorted(want))
        self.assertEqual(sc.validate_run_dir(out, task_of=task_of(out)), {})
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
        self.assertEqual([(p, role) for p, role, _, _ in self.seen], [(p, role) for p in (0, 1) for role in [sim.SETUP_ROLE] + list(ROLES) + ["K9", "K10"]], "one worker, the fixed order: the target setup first")
        seeds = json.loads((self.out_dir / "seeds.json").read_text())
        self.assertEqual(bs.seeds_doc_findings(seeds), [])
        self.assertEqual((seeds["fixture"], seeds["master_seed"], seeds["anchor"]["hypothesis_sha256"], seeds["label"]), (True, None, None, "b4-mech-1"))
        self.assertIn("fixture", seeds["anchor"]["rule"])
        self.assertEqual(seeds["pairs"], [[7, 11], [8, 12]], "the schedule, as given; nothing derived")
        self.assertEqual(len(seeds["exclusion"]["sources"]), 38)
        self.assertEqual(seeds["exclusion"]["sim_registry"], [], "the first batch: no archived set yet")
        rc = bs.read_exposure_receipt(self.root)
        self.assertEqual(seeds["exclusion"]["exposure_receipt"], {"path": bs.EXPOSURE_RECEIPT_REL, "sha256": bs.EXPOSURE_RECEIPT_SHA256, "count": len(rc.values)}, "the receipt was pooled into this derivation")
        self.assertEqual(seeds["exclusion"]["pooled_total"], len(bs.load_exclusion_set(self.root).values))
        self.assertEqual(seeds["schema_version"], "1.2.0")
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
        self.assertEqual(man["exclusion"]["exposure_receipt"], seeds["exclusion"]["exposure_receipt"])
        self.assertEqual(man["inputs"][bs.EXPOSURE_RECEIPT_REL], bs.EXPOSURE_RECEIPT_SHA256, "the receipt is a root input held at the checkpoints")
        self.assertFalse(man["code_root"]["same_as_input_root"], "a hermetic input root is not the code root")
        self.assertIn("b4/host/b4_sim.py", man["tool_files"]); self.assertIn("b4/host/b4_sim_verify.py", man["tool_files"])
        self.assertEqual(man["seeds_sha256"], sim.sha_file(self.out_dir / "seeds.json"))
        self.assertEqual(man["schema_version"], "1.2.0")
        self.assertEqual(bp.identity_findings(man["protocol"]["identity"]), []); self.assertEqual(man["protocol"]["protocol_sha256"], bp.protocol_sha256(man["protocol"]["identity"]))
        self.assertEqual(bp.compare(man["protocol"]["identity"], bp.identity()), [], "the archive's identity is this tool's")
        rep = self.report(self.res); self.assertEqual(rep["identity"]["protocol_sha256"], man["protocol"]["protocol_sha256"])
        self.assertEqual(man["constants"]["task"], "task-v0.2"); self.assertEqual(man["constants"]["target"]["setup_cost"], {"target": 1, "target_holdout": 1})

    def test_the_task_setup_files_the_planted_target_and_the_arms_task(self):
        """task-v0.2 (section 7.1): per pair the private plan, the two setup observations and the public task; the planted configuration a
        flip-flop one scoring its own ceilings; every arm ran under the task of task.json (its digest), which carries no seed; the setup
        port made exactly two calls; the non-triviality record read from R's base trace; the pair index records the setup state."""
        out = self.out_dir
        for r, (l, o) in enumerate(SCHED1.pairs):
            setup = json.loads((out / f"pair_{r:03d}/task_setup.json").read_text()); ts = json.loads((out / f"pair_{r:03d}/target_search.json").read_text())
            th_ = json.loads((out / f"pair_{r:03d}/target_holdout.json").read_text()); task = json.loads((out / f"pair_{r:03d}/task.json").read_text())
            self.assertEqual((setup["landscape_seed"], setup["operator_seed"], setup["status"]), (l, o, "in_progress"))
            self.assertEqual((setup["planted_genome"] >> setup["rule"]["storage_kind_bit"]) & 1, 0, "T-i: a flip-flop configuration")
            self.assertEqual(setup["planted_genome"], bl.planted_genome(l, setup["rule"]["storage_kind_bit"]))
            self.assertEqual((ts["phase"], th_["phase"], ts["genome"], th_["genome"]), ("target", "target_holdout", setup["planted_genome"], setup["planted_genome"]))
            self.assertEqual(ts["provenance_sha256"], th_["provenance_sha256"]); self.assertIs(ts["fixture"], False)
            self.assertEqual((task["planted_search_score"], task["planted_holdout_score"]), ({"fitness": 64, "none_cells": 0, "ceiling": 64}, {"fitness": 80, "none_cells": 0, "ceiling": 80}))
            self.assertEqual(task["setup_files_sha256"], {n: sim.sha_file(out / f"pair_{r:03d}/{n}") for n in SETUP_FILES[:3]})
            pt = task["public_task"]
            self.assertEqual(set(pt), sc.PUBLIC_TASK_KEYS); self.assertNotIn("landscape_seed", pt); self.assertNotIn("seed", pt); self.assertNotIn("planted_genome", pt)
            self.assertEqual((pt["label"], pt["version"]), ("b4-task", "task-v0.2"), "no identifying value smuggled through the label")
            scalars = {k: v for k, v in pt.items() if not isinstance(v, (list, tuple))}
            self.assertEqual(scalars, {"label": "b4-task", "version": "task-v0.2", "base_genome": 0, "target_source_sha256": pt["target_source_sha256"]}, "no scalar of the executing side's input is a seed")
            self.assertEqual([p_.calls for (pr, role, p_) in self.ports if (pr, role) == (r, sim.SETUP_ROLE)], [2], "the setup port made exactly two calls")
            self.assertEqual(pt["target_source_sha256"], bt.target_source_sha256(ts, th_))
            rebuilt = bt.rebuild_task(setup, ts, th_); self.assertEqual(rebuilt.digest(), task["task_digest"])
            self.assertEqual(list(rebuilt.target), [ts["q_grid"][s_][e] for (s_, e) in rebuilt.mask], "the target IS the planted configuration's trace")
            for role in ROLES:
                d = json.loads((out / f"pair_{r:03d}/arm_{role}.result.json").read_text())
                self.assertEqual(d["result"]["task_digest"], task["task_digest"], role); self.assertNotIn("landscape_seed", d["result"]); self.assertEqual(d["landscape_seed"], l)
                for e in d["result"]["ledger"]:
                    self.assertNotEqual((e["genome"], e["stimulus_sha256"]), (setup["planted_genome"], ts["stimulus_sha256"]), "the setup observation is in no arm's ledger")
            cv = json.loads((out / f"pair_{r:03d}/curves.json").read_text())
            r_base = json.loads((out / f"pair_{r:03d}/arm_R.result.json").read_text())["result"]["ledger"][0]["q_grid"]
            self.assertIs(cv["target_equals_R_base_search_trace"], r_base == ts["q_grid"])
            idx = json.loads((out / f"pair_{r:03d}/index.json").read_text()); self.assertEqual(idx["task"], "complete")
            k9d = json.loads((out / f"pair_{r:03d}/k9.json").read_text()); self.assertEqual(k9d["judged_estimand"], "conditional_sr_driven"); self.assertEqual(k9d["landscape_seed"], l)
            self.assertIn("per_semantic_all_panel", k9d["summary"])
        self.assertEqual([x for x in self.seen if x[1] == sim.SETUP_ROLE], [(0, sim.SETUP_ROLE, True, True), (1, sim.SETUP_ROLE, True, True)], "one setup port per pair, after the freezing files")
        rep = self.report(self.res)
        self.assertTrue(all(p["task"] == "complete" for p in rep["pairs"]))
        self.assertIn("per_semantic_all_panel", rep["summary"]["k9"]); self.assertEqual(rep["summary"]["k9"]["judged_estimand"], "conditional_sr_driven")

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

    def test_a_domain_at_the_target_setup_is_target_invalid_with_the_plan_kept(self):
        """Section 7.1: a DOMAIN at the first target observation — task_setup.json was persisted before the call, no target file, no arm
        file, the plan's task state `invalid`, the pair `partial` (never not_started), the kind `target_invalid`; the archive verifies."""
        def factory(fabric, role, pair):
            return InjectingPort(fabric, 1) if (pair, role) == (0, sim.SETUP_ROLE) else ex.ObservationPort(fabric)
        res = self.run_with(factory)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["role"], res["stopped"]["stage"], res["stopped"]["pair"]), ("invalid", 1, "target_invalid", sim.SETUP_ROLE, "target_setup", 0))
        out = Path(res["out"])
        self.assertTrue((out / "pair_000/task_setup.json").exists(), "the plan was persisted before the first target call")
        self.assertFalse((out / "pair_000/target_search.json").exists()); self.assertFalse((out / "pair_000/task.json").exists()); self.assertFalse((out / "pair_000/arm_R.result.json").exists())
        rep = self.report(res)
        self.assertEqual((rep["pairs"][0]["status"], rep["pairs"][0]["task"], rep["pairs"][0]["arms"]["R"]), ("partial", "invalid", "not_started"))
        self.assertEqual((rep["pairs"][0]["task_prefix"], rep["pairs"][0]["task_quarantine"]), (1, None), "a DOMAIN returns nothing: no quarantine, the plan alone")
        self.assertIn("DOMAIN", res["stopped"]["detail"]); self.assertIn("never a redraw", res["stopped"]["detail"])
        self.assertEqual(sv.verify_run_dir(out, deep=True), {})
        self.tearDown()
        # a DOMAIN at the SECOND setup observation: the first is kept on disk
        def factory2(fabric, role, pair):
            return InjectingPort(fabric, 2) if (pair, role) == (0, sim.SETUP_ROLE) else ex.ObservationPort(fabric)
        res = self.run_with(factory2)
        self.assertEqual((res["status"], res["stopped"]["kind"]), ("invalid", "target_invalid"))
        out = Path(res["out"])
        self.assertTrue((out / "pair_000/target_search.json").exists(), "the first observation is kept"); self.assertFalse((out / "pair_000/target_holdout.json").exists())
        p0 = self.report(res)["pairs"][0]
        self.assertEqual((p0["task"], p0["task_prefix"], p0["task_quarantine"]), ("invalid", 2, None))
        self.assertEqual(sv.verify_run_dir(out, deep=True), {})

    def test_a_source_drift_inside_the_setup_and_a_setup_port_that_calls_more_than_twice(self):
        """R2 (the owner's review of 04385ae): a second setup observation from another source identity — a VALID-SHAPED trace whose fabric
        identity differs — is `target_invalid`; the RETURNED object is kept raw in target_holdout.QUARANTINE.json with its findings and its
        context BEFORE the stop; the first record is kept; the plan carries prefix 2 / quarantine target_holdout; nothing is redrawn; the
        archive verifies. (A setup port that is called a third time is the next test's.)"""
        class Drifting(ex.ObservationPort):
            def observe(self, config, stimulus):
                t = super().observe(config, stimulus)
                if self.calls == 2:
                    t["fabric"] = dict(t["fabric"], effect_sha256="a" * 64); t["owner_raw_marker"] = "returned_target_with_drift"
                return t

        def factory(fabric, role, pair):
            return Drifting(fabric) if (pair, role) == (0, sim.SETUP_ROLE) else ex.ObservationPort(fabric)
        res = self.run_with(factory)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["role"]), ("invalid", "target_invalid", sim.SETUP_ROLE))
        self.assertIn("drift", res["stopped"]["detail"]); self.assertIn("target_holdout.QUARANTINE.json", res["stopped"]["detail"])
        out = Path(res["out"])
        self.assertTrue((out / "pair_000/target_search.json").exists()); self.assertFalse((out / "pair_000/target_holdout.json").exists())
        q = json.loads((out / "pair_000/target_holdout.QUARANTINE.json").read_text())
        self.assertEqual(sc.quarantine_findings(q), [])
        self.assertEqual((q["role"], q["stage"], q["context"]["phase"], q["raw"]["owner_raw_marker"], q["raw"]["fabric"]["effect_sha256"]), (sim.SETUP_ROLE, "target_setup", "target_holdout", "returned_target_with_drift", "a" * 64))
        self.assertTrue(any("drift" in x for x in q["findings"])); self.assertEqual(q["context"]["returned_sha256"], ex.sha256_json(q["raw"]))
        first = json.loads((out / "pair_000/target_search.json").read_text())
        self.assertEqual(q["context"]["expected_provenance_sha256"], first["provenance_sha256"]); self.assertEqual(q["context"]["genome"], first["genome"])
        p0 = self.report(res)["pairs"][0]
        self.assertEqual((p0["status"], p0["task"], p0["task_prefix"], p0["task_quarantine"]), ("partial", "invalid", 2, "target_holdout"))
        self.assertEqual(sv.verify_run_dir(out, deep=True), {})

    def test_a_returned_object_that_is_not_a_target_observation_is_quarantined_then_invalid(self):
        """R2 / R4: a malformed step at the first call, a None in the INIT readout (outside the scored mask), a cell of 2, a non-finite
        (non-serialisable) cell, a non-object at the second call, a truncated grid at the second call — each RETURN is kept raw with its
        findings and context (raw null + repr when it cannot be serialised), the pair is `invalid` with the exact prefix and the quarantined
        phase recorded, no observation file is written for that phase, the stop names the quarantine file, the archive verifies clean."""
        class Alter(ex.ObservationPort):
            def __init__(self, fabric, kind):
                super().__init__(fabric); self.kind = kind

            def observe(self, config, stimulus):
                t = super().observe(config, stimulus)
                if self.kind == "malformed" and self.calls == 1:
                    t["steps"][0] = {"owner_raw_marker": "returned_malformed_target"}
                if self.kind == "init_none" and self.calls == 1:
                    t["steps"][0]["q_after"][0] = None
                if self.kind == "bad_cell" and self.calls == 1:
                    t["steps"][2]["q_after"][5] = 2
                if self.kind == "nan" and self.calls == 1:
                    t["steps"][1]["q_after"][1] = float("nan")
                if self.kind == "not_an_object" and self.calls == 2:
                    return ["not", "an", "object"]
                if self.kind == "short_second" and self.calls == 2:
                    t["steps"] = t["steps"][:3]
                return t
        for kind, phase, needle in (("malformed", "target", "no q_after"), ("init_none", "target", "element 0: None"), ("bad_cell", "target", "2 is not 0 / 1"), ("nan", "target", "nan"),
                                    ("not_an_object", "target_holdout", "not an object"), ("short_second", "target_holdout", "steps returned")):
            with self.subTest(kind=kind):
                res = self.run_with(lambda fabric, role, pair, kind=kind: Alter(fabric, kind) if (pair, role) == (0, sim.SETUP_ROLE) else ex.ObservationPort(fabric))
                self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["role"], res["stopped"]["stage"]), ("invalid", 1, "target_invalid", sim.SETUP_ROLE, "target_setup"), kind)
                out = Path(res["out"]); qname = {"target": "target_search", "target_holdout": "target_holdout"}[phase] + ".QUARANTINE.json"
                want = ["task_setup.json"] + (["target_search.json"] if phase == "target_holdout" else []) + [qname]
                self.assertEqual(sorted(p.name for p in (out / "pair_000").iterdir()), sorted(want), kind)
                q = json.loads((out / f"pair_000/{qname}").read_text())
                self.assertEqual(sc.quarantine_findings(q), []); self.assertEqual((q["role"], q["stage"], q["context"]["phase"]), (sim.SETUP_ROLE, "target_setup", phase))
                self.assertTrue(any(needle in x for x in q["findings"]), (kind, q["findings"]))
                if kind == "nan":
                    self.assertIsNone(q["raw"]); self.assertIsNone(q["context"]["returned_sha256"]); self.assertIn("nan", q["raw_repr"])
                elif kind == "malformed":
                    self.assertEqual(q["raw"]["steps"][0]["owner_raw_marker"], "returned_malformed_target"); self.assertEqual(q["context"]["returned_sha256"], ex.sha256_json(q["raw"]))
                elif kind == "init_none":
                    self.assertIsNone(q["raw"]["steps"][0]["q_after"][0])
                elif kind == "not_an_object":
                    self.assertEqual(q["raw"], ["not", "an", "object"])
                p0 = self.report(res)["pairs"][0]
                self.assertEqual((p0["status"], p0["task"], p0["task_prefix"], p0["task_quarantine"], p0["arms"]["R"]), ("partial", "invalid", 1 if phase == "target" else 2, phase, "not_started"), kind)
                self.assertIn(qname, res["stopped"]["detail"])
                self.assertEqual(sv.verify_run_dir(out, deep=True), {}, kind)
                self.tearDown()

    def test_a_setup_that_observes_more_than_twice_is_named(self):
        """Section 7.1: the setup makes exactly two port calls per pair; a setup observation routine that made a third call (here: the target
        observation wrapped to observe once more) is `target_invalid` — the shared cost is two observations, never more."""
        real = bt.observe_target

        def thrice(port, genome, stimulus, addresses, phase, *rest):
            rec = real(port, genome, stimulus, addresses, phase, *rest)
            if phase == "target_holdout":
                port.observe(ex.genome_to_config(genome, addresses), list(stimulus))          # an extra, unrecorded observation
            return rec
        with mock.patch.object(sim.bt, "observe_target", thrice):
            res = self.run_with(None)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["role"]), ("invalid", "target_invalid", sim.SETUP_ROLE)); self.assertIn("port calls, not 2", res["stopped"]["detail"])
        self.assertEqual(self.report(res)["pairs"][0]["task"], "invalid")
        self.assertEqual(sv.verify_run_dir(Path(res["out"]), deep=True), {})

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

    def test_a_receipt_drift_during_the_batch_is_invalid(self):
        """The exposure receipt changes during the batch: caught at the pair's input checkpoint as input_drift, never complete."""
        rc = self.root / bs.EXPOSURE_RECEIPT_REL
        original = rc.read_bytes()

        def drift(fabric, role, pair):
            if (pair, role) == (1, "R"):
                rc.write_bytes(original + b"\n")
            return ex.ObservationPort(fabric)
        try:
            res = self.run_with(drift)
        finally:
            rc.write_bytes(original)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"]), ("invalid", 1, "input_drift"))
        self.assertIn(bs.EXPOSURE_RECEIPT_REL, res["stopped"]["detail"]); self.assertEqual(res["stopped"]["stage"], "pair 1 end")
        self.assertIsNone(self.report(res)["summary"])

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
    def test_an_interrupt_or_the_deadline_between_the_two_setup_observations_keeps_the_first(self):
        """Section 7.1: an external interrupt at the second target call — incomplete, the first observation on disk, the task `partial`, the
        pair `partial`; the deadline expiring before the second call — incomplete (deadline), the same records; the archive verifies."""
        def interrupt(fabric, role, pair):
            return RaisingPort(fabric, 2, KeyboardInterrupt()) if (pair, role) == (0, sim.SETUP_ROLE) else ex.ObservationPort(fabric)
        res = self.run_with(interrupt)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["role"], res["stopped"]["stage"]), ("incomplete", 3, "interrupted", sim.SETUP_ROLE, "target_setup"))
        out = Path(res["out"])
        self.assertTrue((out / "pair_000/task_setup.json").exists()); self.assertTrue((out / "pair_000/target_search.json").exists()); self.assertFalse((out / "pair_000/target_holdout.json").exists())
        rep = self.report(res)
        self.assertEqual((rep["pairs"][0]["status"], rep["pairs"][0]["task"]), ("partial", "partial")); self.assertEqual(rep["pairs"][1]["status"], "not_started")
        self.assertEqual(sv.verify_run_dir(out, deep=True), {})
        self.tearDown()
        clock = Clock(step=0.0)

        def late(fabric, role, pair):
            if (pair, role) == (0, sim.SETUP_ROLE):
                clock.jump_at, clock.jump = clock.calls + 2, 10 ** 6               # the first check passes, the second (before the holdout target) expires
            return ex.ObservationPort(fabric)
        res = self.run_with(late, dl=60, clock=clock)
        self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["stage"]), ("incomplete", 3, "deadline", "target_setup"))
        out = Path(res["out"])
        self.assertTrue((out / "pair_000/target_search.json").exists()); self.assertFalse((out / "pair_000/target_holdout.json").exists())
        self.assertEqual(self.report(res)["pairs"][0]["task"], "partial")
        self.assertEqual(sv.verify_run_dir(out, deep=True), {})

    def test_an_interrupt_or_the_deadline_at_every_persistence_boundary_keeps_the_ordered_prefix(self):
        """R3 (the owner's review of 04385ae): at EVERY boundary of the setup — right after each of the four writes returned, during each
        of the two observations, at the deadline check before each observation — the pair's planned record carries the durable ordered
        prefix (task_prefix) and exactly those files are on disk; every archive verifies clean. A prefix of three (both observations
        written, the interrupt before task.json) is a genuine partial, not an unaccounted file."""
        original = sim.Batch.write

        def after(suffix):
            def write(self_, rel, doc, validator):
                e = original(self_, rel, doc, validator)
                if rel.endswith(suffix):
                    raise KeyboardInterrupt()
                return e
            return write
        cases = [("after task_setup.json", "/task_setup.json", None, "in_progress", 1), ("during the first observation", None, 1, "in_progress", 1),
                 ("after target_search.json", "/target_search.json", None, "partial", 2), ("during the second observation", None, 2, "partial", 2),
                 ("after target_holdout.json", "/target_holdout.json", None, "partial", 3), ("after task.json", "/task.json", None, "complete", 4)]
        for name, suffix, at, task_state, prefix in cases:
            with self.subTest(boundary=name):
                factory = (lambda fabric, role, pair, at=at: RaisingPort(fabric, at, KeyboardInterrupt()) if (pair, role) == (0, sim.SETUP_ROLE) else ex.ObservationPort(fabric)) if at else None
                try:
                    with (mock.patch.object(sim.Batch, "write", after(suffix)) if suffix else contextlib.nullcontext()):
                        res = self.run_with(factory)
                    self.assertEqual((res["status"], res["exit_code"], res["stopped"]["kind"], res["stopped"]["stage"], res["stopped"]["role"]), ("incomplete", 3, "interrupted", "target_setup", sim.SETUP_ROLE), (name, res.get("reason")))
                    out = Path(res["out"]); p0 = self.report(res)["pairs"][0]
                    self.assertEqual((p0["status"], p0["task"], p0["task_prefix"], p0["task_quarantine"]), ("partial", task_state, prefix, None), name)
                    self.assertEqual(sorted(p.name for p in (out / "pair_000").iterdir()), sorted(SETUP_FILES[:prefix]), name)
                    self.assertEqual(sv.verify_run_dir(out, deep=True), {}, name)
                finally:
                    self.tearDown()
        # the deadline at the check before the FIRST observation (the check before the second is the previous test's)
        clock = Clock(step=0.0)

        def expire_first(fabric, role, pair):
            if (pair, role) == (0, sim.SETUP_ROLE):
                clock.jump_at, clock.jump = clock.calls + 1, 10 ** 6
            return ex.ObservationPort(fabric)
        res = self.run_with(expire_first, dl=60, clock=clock)
        self.assertEqual((res["status"], res["stopped"]["kind"], res["stopped"]["stage"]), ("incomplete", "deadline", "target_setup"))
        out = Path(res["out"]); p0 = self.report(res)["pairs"][0]
        self.assertEqual((p0["task"], p0["task_prefix"]), ("in_progress", 1)); self.assertEqual(sorted(p.name for p in (out / "pair_000").iterdir()), ["task_setup.json"])
        self.assertEqual(sv.verify_run_dir(out, deep=True), {})

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
    man = json.loads((out / "manifest.json").read_text())
    if man["seeds_sha256"] != sim.sha_file(out / "seeds.json"):                  # seeds.json rewritten: the manifest's copy of its digest refreshed too
        man["seeds_sha256"] = sim.sha_file(out / "seeds.json"); (out / "manifest.json").write_text(json.dumps(man, sort_keys=True, indent=1) + "\n")
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
        cls.task = task_of(cls.out_dir)(0)[0]
        cls.target_grid = json.loads(cls.originals["pair_000/target_search.json"])["q_grid"]
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
        self.assertTrue(any("planned pair's" in x for x in sc.k9_findings(d, self.task, 7)), "the declared seed is held to the planned pair's, not another user string")
        self.put("pair_000/k9.json", d); reindex(self.out_dir); self.assertIn("pair_000/k9.json", self.findings())
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
        curves = sim.curves_of(results, 0, 7, 11, self.target_grid); self.put("pair_000/curves.json", curves)
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
        partial = k10.seed_k10(self.task, ex.ObservationPort(fabric), 7, check=one_unit)
        self.assertEqual((partial["complete"], len(partial["units"])), (False, 1))
        doc = self.load("pair_000/k10.json"); doc.update(partial); self.put("pair_000/k10.json", doc)
        self.assertEqual(sc.k10_findings(doc, self.task), [], "the partial is a valid record in itself")
        curves, k7, k9d = self.load("pair_000/curves.json"), self.load("pair_000/k7.json"), self.load("pair_000/k9.json")
        row = sim.row_of(0, 7, 11, curves, k7["prefixes"], k9d, partial)
        rep = self.load("sim_report.json"); rep["summary"] = sim.summarise_batch([row], 1)[0]; self.put("sim_report.json", rep); reindex(out)
        f = self.findings()
        self.assertTrue(any("k10: recorded complete" in x for xs in f.values() for x in xs), f)
        n["k"] = 0

        def three_pairs():
            n["k"] += 1
            if n["k"] > 3:
                raise StopWork("stopped after three pairs")
        p9 = k9.coverage(self.task, ex.ObservationPort(fabric), bm.site_mapping(), fabric, 7, check=three_pairs)
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

    def test_the_exposure_receipt_is_bound_in_seeds_the_manifest_and_the_inputs(self):
        """The settlement of 2026-10-19: the receipt named by seeds.json and the manifest, and held in the inputs, is exactly
        the pinned one — a changed digest, path or count, or a held input digest that is not the pinned one, is a finding."""
        out = self.out_dir
        man = self.load("manifest.json"); man["exclusion"]["exposure_receipt"]["sha256"] = "00" * 32; self.put("manifest.json", man); reindex(out)
        f = self.findings(); self.assertTrue(any("exposure_receipt" in x for x in f.get("manifest.json", [])), f)
        man = self.load("manifest.json"); man["inputs"][bs.EXPOSURE_RECEIPT_REL] = "00" * 32; self.put("manifest.json", man); reindex(out)
        f = self.findings(); self.assertTrue(any("receipt" in x for x in f.get("manifest.json", [])), f)
        sd = self.load("seeds.json"); sd["exclusion"]["exposure_receipt"]["count"] = 1; self.put("seeds.json", sd); reindex(out)
        f = self.findings(); self.assertTrue(any("receipt" in x for xs in f.values() for x in xs), f)
        sd = self.load("seeds.json"); del sd["exclusion"]["exposure_receipt"]; self.put("seeds.json", sd); reindex(out)
        f = self.findings(); self.assertIn("seeds.json", f, f)
        with mock.patch.dict(sc.VALIDATORS, {"seeds.json": lambda d: [], "manifest.json": lambda d: []}):     # defence in depth: the linkage check alone
            man = self.load("manifest.json"); man["exclusion"]["exposure_receipt"]["sha256"] = "00" * 32; self.put("manifest.json", man); reindex(out)
            f = self.findings(); self.assertTrue(any("exposure receipt" in x for x in f.get("linkage", [])), f)
        self.assertEqual(self.findings(), {}, "restored")

    def test_a_coordinated_wrong_receipt_count_in_both_records_is_refused(self):
        """The owner's review of 2026-10-19 on 1d9525c (P2): seeds.json's and the manifest's receipt counts changed TOGETHER
        (0, 1, 67 against a 66-value receipt), every digest and index refreshed — two records agreeing is not the authority;
        the count must be the pooled length of the hash-verified pinned receipt. Named by the validators, and by the linkage
        alone when the record validators are mocked away. The pristine count stays clean."""
        out = self.out_dir
        n_true = bs.pinned_receipt_count()
        self.assertEqual(n_true, len(bs.read_exposure_receipt(self.root).values))

        def both(n):
            sd = self.load("seeds.json"); sd["exclusion"]["exposure_receipt"]["count"] = n; self.put("seeds.json", sd)
            man = self.load("manifest.json"); man["exclusion"]["exposure_receipt"]["count"] = n; self.put("manifest.json", man)
            reindex(out)
        for n in (0, 1, n_true + 1):
            both(n)
            f = self.findings()
            self.assertTrue(any("pooled length" in x for xs in f.values() for x in xs), (n, f))
            self.assertTrue(f.get("seeds.json") and f.get("manifest.json"), (n, f))
            with mock.patch.dict(sc.VALIDATORS, {"seeds.json": lambda d: [], "manifest.json": lambda d: []}):
                both(n)
                f = self.findings()
                self.assertTrue(any("pooled length" in x for x in f.get("linkage", [])), (n, f))
        both(n_true)
        self.assertEqual(self.findings(), {}, "the true count is clean")
        self.assertEqual(self.findings(), {}, "restored")

    def test_the_setup_records_are_bound_and_every_tamper_is_named(self):
        """task-v0.2: the target flipped in task.json, a target grid cell flipped, the planted genome changed in the plan, a setup file's digest
        in task.json, the arms' task digest — each with every index refreshed — are named by the verifier; the protocol identity removed or
        altered in the manifest is a named refusal before anything else; the committed v0.1.16 archive is refused by name, untouched."""
        out = self.out_dir
        d = self.load("pair_000/task.json"); d["public_task"]["target"][0] = 1 - d["public_task"]["target"][0]; self.put("pair_000/task.json", d); reindex(out)
        f = self.findings(); self.assertTrue(any("task_digest is not the public task" in x for x in f.get("pair_000/task.json", [])) or any("rebuilt" in x for xs in f.values() for x in xs), f)
        d = self.load("pair_000/target_search.json"); d["q_grid"][2][1] = 1 - d["q_grid"][2][1]; self.put("pair_000/target_search.json", d); reindex(out)
        f = self.findings(); self.assertTrue(any("does not hash to trace_sha256" in x for x in f.get("pair_000/target_search.json", [])), f)
        d = self.load("pair_000/target_search.json"); d["q_grid"][2][1] = 1 - d["q_grid"][2][1]; d["trace_sha256"] = ex.sha256_json(d["q_grid"]); self.put("pair_000/target_search.json", d); reindex(out)
        f = self.findings(); self.assertTrue(any("setup_files_sha256" in x or "rebuilt" in x for xs in f.values() for x in xs), f)
        d = self.load("pair_000/task_setup.json"); d["planted_genome"] ^= 1 << 2; d["planted_genome_hex"] = ex.genome_hex(d["planted_genome"], 21); self.put("pair_000/task_setup.json", d); reindex(out)
        f = self.findings(); self.assertTrue(any("not what the seed, the rule and the mapping give" in x for xs in f.values() for x in xs), f)
        d = self.load("pair_000/task.json"); d["setup_files_sha256"]["target_holdout.json"] = "0" * 64; self.put("pair_000/task.json", d); reindex(out)
        f = self.findings(); self.assertTrue(any("setup_files_sha256[target_holdout.json]" in x for xs in f.values() for x in xs), f)
        d = self.load("pair_000/arm_R.result.json"); d["result"]["task_digest"] = "0" * 64; self.put("pair_000/arm_R.result.json", d); reindex(out)
        f = self.findings(); self.assertIn("pair_000/arm_R.result.json", f)
        man = self.load("manifest.json"); del man["protocol"]; self.put("manifest.json", man); reindex(out)
        f = self.findings(); self.assertEqual(list(f), ["protocol"]); self.assertIn("no protocol identity", f["protocol"][0]); self.assertIn("b4_archive_reverification", f["protocol"][0])
        man = self.load("manifest.json"); man["protocol"]["identity"]["k9"]["judged"] = "all_panel"; self.put("manifest.json", man); reindex(out)
        f = self.findings(); self.assertEqual(list(f), ["protocol"]); self.assertIn("k9: judged", f["protocol"][0])
        man = self.load("manifest.json"); man["protocol"]["identity"]["architecture_revision"] = "v9.9.9"; self.put("manifest.json", man); reindex(out)
        f = self.findings(); self.assertEqual(f, {}, "the document's revision is outside the equality and outside the digest: with the indexes refreshed there is nothing to name")
        man = self.load("manifest.json"); man["protocol"]["protocol_sha256"] = "0" * 64; self.put("manifest.json", man); reindex(out)
        f = self.findings(); self.assertTrue(any("protocol_sha256" in x for xs in f.values() for x in xs), f)
        old = R / "evidence/b4/sim/b4-sim-3_20261019T121833Z"
        before = sorted((p.name, sim.sha_file(p)) for p in old.iterdir() if p.is_file())
        f = sv.verify_run_dir(old, deep=False)
        self.assertEqual(list(f), ["protocol"]); self.assertIn("no protocol identity", f["protocol"][0]); self.assertIn("933545a", f["protocol"][0])
        self.assertEqual(sorted((p.name, sim.sha_file(p)) for p in old.iterdir() if p.is_file()), before, "the committed archive is untouched")
        self.assertEqual(self.findings(), {}, "restored")

    def test_a_later_setup_file_without_its_prerequisite_is_refused_by_name(self):
        """R3, the owner's forgeries: an invalid setup archive with target_search.json removed and a valid target_holdout.json put in its
        place, every report digest refreshed — refused by name (the prefix file missing, the later file unaccounted for); a prefix-3 partial
        with its holdout removed — refused; its task_prefix lowered to 2 — a genuine prefix again, clean; raised back to 3 — refused; a
        quarantined return the plan does not carry — refused; an inconsistent state / prefix — refused by the report validator."""
        def refresh(out):
            rep = json.loads((out / "sim_report.json").read_text())
            rep["files"] = [entry(p, str(p.relative_to(out))) for p in sorted(out.rglob("*")) if p.is_file() and p.name != "sim_report.json"]
            rep["identity"]["seeds_sha256"] = sim.sha_file(out / "seeds.json"); rep["identity"]["manifest_sha256"] = sim.sha_file(out / "manifest.json")
            (out / "sim_report.json").write_text(json.dumps(rep, sort_keys=True, indent=1) + "\n")

        def set_plan(out, **kw):
            rep = json.loads((out / "sim_report.json").read_text()); rep["pairs"][0].update(kw); rep["stopped"]["planned"][0].update(kw)
            (out / "sim_report.json").write_text(json.dumps(rep, sort_keys=True, indent=1) + "\n")
            st = json.loads((out / "STOPPED.json").read_text()); st["planned"][0].update(kw)
            (out / "STOPPED.json").write_text(json.dumps(st, sort_keys=True, indent=1) + "\n")
            refresh(out)

        def names(out, *needles):
            f = sv.verify_run_dir(out, deep=True)
            for n in needles:
                self.assertTrue(any(n in where or n in x for where, xs in f.items() for x in xs), (n, f))
            return f

        class Drifting(ex.ObservationPort):
            def observe(self, config, stimulus):
                t = super().observe(config, stimulus)
                if self.calls == 2:
                    t["fabric"] = dict(t["fabric"], effect_sha256="a" * 64)
                return t
        drift = self.run_with(lambda fabric, role, pair: Drifting(fabric) if (pair, role) == (0, sim.SETUP_ROLE) else ex.ObservationPort(fabric), out=self.ns / "b4-mech-1_drift_src")
        self.assertEqual(drift["status"], "invalid"); self.tearDown()
        forged = self.ns / "b4-mech-1_impossible_order"; shutil.copytree(drift["out"], forged)
        (forged / "pair_000/target_search.json").unlink(); shutil.copy(self.out_dir / "pair_000/target_holdout.json", forged / "pair_000/target_holdout.json"); refresh(forged)
        names(forged, "pair_000/target_search.json", "required by pair 0's recorded state", "not a file any pair's recorded state accounts for")
        shutil.rmtree(forged)
        q = self.ns / "b4-mech-1_quarantine_unrecorded"; shutil.copytree(drift["out"], q); set_plan(q, task_quarantine=None)
        names(q, "not a file any pair's recorded state accounts for"); set_plan(q, task_quarantine="target_holdout", task_prefix=1)
        names(q, "does not carry the durable ordered prefix"); shutil.rmtree(q); self.tearDown()
        original = sim.Batch.write

        def write(self_, rel, doc, validator):
            e = original(self_, rel, doc, validator)
            if rel.endswith("/target_holdout.json"):
                raise KeyboardInterrupt()
            return e
        with mock.patch.object(sim.Batch, "write", write):
            three = self.run_with(None, out=self.ns / "b4-mech-1_prefix3_src")
        self.assertEqual((three["status"], self.report(three)["pairs"][0]["task_prefix"]), ("incomplete", 3)); self.tearDown()
        p3 = self.ns / "b4-mech-1_prefix3_forged"; shutil.copytree(three["out"], p3)
        (p3 / "pair_000/target_holdout.json").unlink(); refresh(p3)
        names(p3, "pair_000/target_holdout.json", "required by pair 0's recorded state")
        set_plan(p3, task_prefix=2); self.assertEqual(sv.verify_run_dir(p3, deep=True), {}, "a genuine prefix of two: the contract is the recorded prefix, not a list of allowed files")
        set_plan(p3, task_prefix=3); names(p3, "required by pair 0's recorded state")
        shutil.copy(three["out"] + "/pair_000/target_holdout.json", p3 / "pair_000/target_holdout.json"); set_plan(p3, task_prefix=2)
        names(p3, "pair_000/target_holdout.json", "not a file any pair's recorded state accounts for")
        set_plan(p3, task_prefix=4); names(p3, "does not carry the durable ordered prefix")
        shutil.rmtree(p3); self.tearDown()

    def test_the_archive_holds_real_files_in_pair_directories_only(self):
        """A subdirectory inside a pair, a directory that is not a pair directory, a pair directory the plan does not have, a symlink — each
        is named (a directory entry is not ignored because it holds no file)."""
        out = self.out_dir
        for make, undo, needle in (((out / "pair_000/junk").mkdir, (out / "pair_000/junk").rmdir, "not a pair directory"),
                                   ((out / "junk").mkdir, (out / "junk").rmdir, "not a pair directory"),
                                   ((out / "pair_007").mkdir, (out / "pair_007").rmdir, "the plan does not have"),
                                   (lambda: (out / "pair_000/link.json").symlink_to(out / "pair_000/k7.json"), (out / "pair_000/link.json").unlink, "a symlink")):
            make()
            try:
                f = sv.verify_run_dir(out, deep=False)
                self.assertTrue(any(needle in x for xs in f.values() for x in xs), (needle, f))
            finally:
                undo()
        self.assertEqual(self.findings(deep=False), {}, "restored")

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
                "k9_all_panel": {s: {"applicable": 8, "covered": 2, "not_applicable": 0, "fraction": 0.25, "assessable": True, "positive_control": True, "conditional_on_A8": s == "ff_init"} for s in sc_semantics()},
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
        self.assertEqual((s["k9"]["judged_estimand"], s["k9"]["per_semantic"]["ff_srval"]["median_coverage_over_all_S"], s["k9"]["per_semantic_all_panel"]["ff_srval"]["median_coverage_over_all_S"]), ("conditional_sr_driven", 0.5, 0.25))
        json.dumps(s, allow_nan=False)
        self.assertEqual(gs.finite_findings(s), [])
        with self.assertRaises(ValueError):
            sim.summarise_batch(rows, 3)
        rows[1]["k9"]["sr_kind"]["fraction"] = None; rows[1]["k9"]["sr_kind"]["assessable"] = False
        s2, _ = sim.summarise_batch(rows, 2)
        self.assertEqual((s2["k9"]["per_semantic"]["sr_kind"]["not_assessable_seeds"], s2["k9"]["per_semantic"]["sr_kind"]["median_coverage_over_all_S"]), (1, None), "one not-assessable seed: the median is not assessable")

    def test_the_quarantine_record_carries_a_context_for_a_target_return_only_and_the_prefix_contract(self):
        base = {"schema": "b4_sim_quarantine", "schema_version": "1.1.0", "pair": 0, "role": "R", "stage": "engine_return", "findings": ["x"], "raw": {"a": 1}, "raw_repr": "r", "context": None, "written_utc": "t"}
        self.assertEqual(sc.quarantine_findings(base), [])
        self.assertTrue(sc.quarantine_findings(dict(base, schema_version="1.0.0")), "the 1.0.0 record without a context is another version")
        self.assertTrue(any("null for every quarantine" in x for x in sc.quarantine_findings(dict(base, context={}))))
        ctx = {"phase": "target", "genome": 5, "genome_hex": ex.genome_hex(5, 21), "config_sha256": "0" * 64, "stimulus_sha256": "1" * 64, "expected_provenance_sha256": None, "returned_sha256": ex.sha256_json({"a": 1})}
        t = dict(base, role="TARGET", stage="target_setup", context=ctx)
        self.assertEqual(sc.quarantine_findings(t), [])
        self.assertTrue(any("context" in x for x in sc.quarantine_findings(dict(t, context=None))))
        self.assertTrue(any("returned_sha256" in x for x in sc.quarantine_findings(dict(t, context=dict(ctx, returned_sha256="2" * 64)))))
        self.assertTrue(any("returned_sha256" in x for x in sc.quarantine_findings(dict(t, raw=None))))
        self.assertEqual(sc.quarantine_findings(dict(t, raw=None, context=dict(ctx, returned_sha256=None))), [], "an unserialisable return: raw null, no digest")
        self.assertTrue(any("target_setup" in x for x in sc.quarantine_findings(dict(t, stage="engine_return"))))
        self.assertTrue(any("context" in x for x in sc.quarantine_findings(dict(t, context=dict(ctx, phase="x")))))
        ok = sc.setup_prefix_ok
        for state, prefixes in (("not_started", {0}), ("in_progress", {1}), ("partial", {2, 3}), ("complete", {4}), ("invalid", {1, 2, 3})):
            for n in range(5):
                self.assertEqual(ok(state, n, None), n in prefixes, (state, n))
        self.assertTrue(ok("invalid", 1, "target")); self.assertTrue(ok("invalid", 2, "target_holdout"))
        for state, n, q in (("invalid", 2, "target"), ("invalid", 1, "target_holdout"), ("invalid", 3, "target_holdout"), ("partial", 2, "target_holdout"), ("complete", 4, "target")):
            self.assertFalse(ok(state, n, q), (state, n, q))

    def test_a_summary_with_a_verdict_key_is_refused_by_the_report_validator(self):
        plan = {"pair": 0, "landscape_seed": 7, "operator_seed": 11, "status": "complete", "task": "complete", "task_prefix": 4, "task_quarantine": None, "arms": {r: "audited" for r in ROLES}, "k7": "complete", "k9": "complete", "k10": "complete"}
        rep = {"schema": "b4_sim_report", "schema_version": "1.2.0", "status": "complete", "label": "b4-mech-1", "fixture": True, "count": 1, "head": "0" * 40, "generated_utc": "x",
               "deadline": {"seconds": 60, "elapsed_s": 1.5, "checks": 3, "expired": False, "first_expired_at_s": None, "clock": "time.monotonic"},
               "standing": "not a gate verdict", "thresholds": {}, "identity": {"protocol_sha256": "0" * 64}, "pairs": [plan], "files": [], "stopped": None,
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
        rep["pairs"][0]["k9"] = "complete"; rep["pairs"][0]["task"] = "partial"
        self.assertTrue(any("weaker state" in f for f in sc.report_findings(rep)), "a complete pair needs its task setup complete")
        rep["pairs"][0]["task"] = "complete"; rep["pairs"][0]["status"] = "not_started"; rep["pairs"][0]["arms"] = {r: "not_started" for r in ROLES}; rep["pairs"][0]["k7"] = rep["pairs"][0]["k9"] = rep["pairs"][0]["k10"] = "not_started"
        self.assertTrue(any("never not_started" in f for f in sc.report_findings(rep)), "a pair whose task setup began is never not_started")
        rep["pairs"][0]["task"] = "not_started"; rep["pairs"][0]["arms"]["R"] = "audited"
        self.assertTrue(any("without a complete task setup" in f for f in sc.report_findings(rep)))
        rep["pairs"][0] = plan; rep["status"] = "invalid"
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
