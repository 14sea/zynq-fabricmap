"""host/b2_test_report.py — the clean-tree proof, fail-closed.

Every case here drives the PRODUCTION verdict (`b2_test_report.build` / `proof_refusals`). None
of them reimplements it: the previous version of this file copied the condition list into the
test, so removing a production condition left all eleven tests passing — the owner's review of
2026-09-12 demonstrated exactly that. A positive control is built first and each condition is
then removed from it one at a time, so deleting a production check fails a test here.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b2_pins  # noqa: E402
import b2_test_report as tr  # noqa: E402

OK_LOG = "....\n" + "-" * 70 + "\nRan 402 tests in 400.000s\n\nOK\n"


def clean_snapshot() -> dict:
    """A snapshot that satisfies every condition — the shape `snapshot()` returns."""
    return {"at": "2026-09-12T000000Z", "root": str(R), "head": "a" * 40, "worktree_dirty": False,
            "instrument": {"root": "/instrument", "head": "b" * 40, "dirty": False,
                           "pinned_commit": "b" * 40},
            "pins": {"manifest_present": False, "pins_verified": True, "pins_refusal": None,
                     "files_verified": 71, "b1_files_verified": 105, "bound_to": "the table's own bytes"},
            "artifacts_sha256": {"docs/b2_architecture.md": "c" * 64, "manifests/b2_manifest.json": None}}


def qualifying_run(log: str = OK_LOG) -> dict:
    snap = clean_snapshot()
    return {"executed": True, "argv": ["python", "-m", "unittest"], "exit_status": 0, "log": log,
            "start": snap, "end": copy.deepcopy(snap)}


class ThePositiveControl(unittest.TestCase):
    def test_a_qualifying_run_is_a_proof(self):
        rep = tr.build(qualifying_run())
        self.assertEqual(rep["proof_refusals"], [])
        self.assertTrue(rep["clean_tree_proof"])
        self.assertEqual(rep["ran"], 402)
        self.assertEqual(rep["result_line"], "OK")
        self.assertEqual(rep["head_at_run"], "a" * 40, "the provenance must be the START snapshot")
        self.assertEqual(rep["schema_version"], tr.SCHEMA_VERSION)
        self.assertEqual(rep["log_sha256"], __import__("hashlib").sha256(OK_LOG.encode()).hexdigest())


class TheLogContract(unittest.TestCase):
    """The review's log fixtures, each through the production verdict."""

    def _refused(self, log: str, needle: str):
        rep = tr.build(qualifying_run(log))
        self.assertFalse(rep["clean_tree_proof"], (log, rep["proof_refusals"]))
        self.assertTrue(any(needle in x for x in rep["proof_refusals"]),
                        (needle, rep["proof_refusals"]))

    def test_a_log_with_no_result_line(self):
        self._refused("Ran 1869 tests in 400.000s\n", "no OK or FAILED result line")

    def test_a_log_ending_in_a_bare_failed(self):
        self._refused("Ran 1869 tests in 400.000s\n\nFAILED\n", "says FAILED")

    def test_a_log_recording_zero_tests(self):
        self._refused("Ran 0 tests in 0.000s\n\nOK\n", "zero tests")

    def test_a_truncated_ran_line(self):
        self._refused("Ran 1869\n", "no complete 'Ran N tests in ...' line")

    def test_a_counter_this_tool_cannot_parse(self):
        self._refused("Ran 4 tests in 1.0s\n\nOK (skipped=unknown)\n", "unparsed counter")

    def test_a_counted_failure(self):
        self._refused("Ran 4 tests in 1.0s\n\nFAILED (failures=1, errors=2)\n", "says FAILED")
        rep = tr.build(qualifying_run("Ran 4 tests in 1.0s\n\nFAILED (failures=1, errors=2)\n"))
        self.assertEqual((rep["failures"], rep["errors"]), (1, 2))

    def test_a_skipped_run(self):
        self._refused("Ran 4 tests in 1.0s\n\nOK (skipped=3)\n", "not exactly 'OK'")

    def test_two_runs_in_one_log(self):
        self._refused("Ran 4 tests in 1.0s\n\nOK\nRan 5 tests in 1.0s\n\nOK\n", "which run is this")

    def test_a_completely_unparseable_log(self):
        self._refused("nothing that looks like a unittest run\n", "no complete 'Ran N tests in ...' line")


class TheRunState(unittest.TestCase):
    """Every snapshot condition, removed one at a time from the qualifying control."""

    def _refused(self, mutate, needle: str):
        run = qualifying_run()
        mutate(run)
        rep = tr.build(run)
        self.assertFalse(rep["clean_tree_proof"], rep["proof_refusals"])
        self.assertTrue(any(needle in x for x in rep["proof_refusals"]), (needle, rep["proof_refusals"]))

    def test_a_report_this_tool_did_not_run(self):
        self._refused(lambda r: r.__setitem__("executed", False), "not executed by this tool")

    def test_a_non_zero_exit(self):
        self._refused(lambda r: r.__setitem__("exit_status", 1), "exited 1")

    def test_a_dirty_worktree_at_either_end(self):
        for end in ("start", "end"):
            with self.subTest(end=end):
                self._refused(lambda r, e=end: r[e].__setitem__("worktree_dirty", True),
                              f"worktree was True at the {end}")
                self._refused(lambda r, e=end: r[e].__setitem__("worktree_dirty", None),
                              f"worktree was None at the {end}")

    def test_an_unobserved_head(self):
        self._refused(lambda r: r["start"].__setitem__("head", None), "no HEAD was observed")

    def test_the_instrument_off_its_pin_or_dirty(self):
        for end in ("start", "end"):
            with self.subTest(end=end):
                self._refused(lambda r, e=end: r[e]["instrument"].__setitem__("head", "0" * 40),
                              f"at the {end}, not its pinned commit")
                self._refused(lambda r, e=end: r[e]["instrument"].__setitem__("dirty", True),
                              f"instrument was True at the {end}")

    def test_a_drifted_pinned_surface_at_either_end(self):
        for end in ("start", "end"):
            with self.subTest(end=end):
                self._refused(lambda r, e=end: r[e]["pins"].update(pins_verified=False,
                                                                   pins_refusal="PinRefusal: drift"),
                              f"pinned surface did not verify at the {end}")

    def test_head_moving_during_the_run(self):
        self._refused(lambda r: r["end"].__setitem__("head", "d" * 40), "HEAD moved during the run")

    def test_a_dirty_start_and_a_clean_finish(self):
        """The review's ordering probe: the old builder read Git only after the suite."""
        self._refused(lambda r: r["start"].__setitem__("worktree_dirty", True),
                      "worktree was True at the start")

    def test_an_artifact_changing_during_the_run(self):
        self._refused(lambda r: r["end"]["artifacts_sha256"].__setitem__("docs/b2_architecture.md", "f" * 64),
                      "pinned artifacts changed during the run")

    def test_a_run_with_no_snapshots_at_all(self):
        self._refused(lambda r: r.update(start=None, end=None), "no start and end snapshots")


class TheRealTree(unittest.TestCase):
    def test_a_snapshot_of_this_tree_has_the_shape_the_verdict_reads(self):
        snap = tr.snapshot()
        for key in ("at", "root", "head", "worktree_dirty", "instrument", "pins", "artifacts_sha256"):
            self.assertIn(key, snap)
        self.assertTrue(snap["pins"]["pins_verified"], snap["pins"].get("pins_refusal"))
        self.assertEqual(snap["pins"]["files_verified"], b2_pins.generate()["file_count"])
        self.assertEqual(snap["pins"]["b1_files_verified"], 105)
        self.assertIn("manifests/b2_instrument_pins.json", snap["artifacts_sha256"])

    def test_a_drifted_surface_is_named_and_demoted_on_a_mirrored_tree(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        table = json.loads((R / "manifests/b2_instrument_pins.json").read_text())
        for rel in list(table["files"]) + ["manifests/b2_instrument_pins.json",
                                           "manifests/b1_instrument_pins.json", "manifests/b1_manifest.json"]:
            dest = d / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(R / rel, dest)
        first = sorted(table["files"])[0]
        (d / first).write_text((d / first).read_text() + "\n# review drift\n")
        state = tr.pin_state(root=d)
        self.assertFalse(state["pins_verified"])
        self.assertIn("PinRefusal", state["pins_refusal"])
        run = qualifying_run()
        run["start"]["pins"] = state
        self.assertFalse(tr.build(run)["clean_tree_proof"])


class TheCommandLine(unittest.TestCase):
    def _cli(self, *args, cwd=R):
        return subprocess.run([sys.executable, str(R / "host/b2_test_report.py"), *args],
                              capture_output=True, text=True, cwd=cwd)

    def test_no_run_writes_a_report_that_is_never_a_proof(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        log = d / "suite.log"
        log.write_text(OK_LOG)
        p = self._cli("--no-run", "--log", str(log), "--exit-status", "0", "--out-dir", str(d / "out"))
        self.assertEqual(p.returncode, 0, p.stderr[-400:])
        written = sorted((d / "out").glob("test_report_*.json"))
        self.assertEqual(len(written), 1, p.stdout)
        rep = json.loads(written[0].read_text())
        self.assertEqual(rep["ran"], 402)
        self.assertFalse(rep["clean_tree_proof"], "a reconstructed report was called a proof")
        self.assertTrue(any("not executed by this tool" in x for x in rep["proof_refusals"]))

    def test_every_io_failure_exits_three(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        log = d / "suite.log"
        log.write_text(OK_LOG)
        blocker = d / "not_a_dir"
        blocker.write_text("I am a regular file\n")
        cases = {
            "no log and no status": ("--no-run",),
            "no status": ("--no-run", "--log", str(log)),
            "a log that is not there": ("--no-run", "--log", str(d / "absent.log"), "--exit-status", "0"),
            "an out-dir that is a file": ("--no-run", "--log", str(log), "--exit-status", "0",
                                          "--out-dir", str(blocker)),
        }
        for name, args in cases.items():
            with self.subTest(case=name):
                p = self._cli(*args)
                self.assertEqual(p.returncode, 3, (name, p.returncode, p.stderr[-300:]))
                self.assertIn("EXIT 3:", p.stderr)
                self.assertNotIn("Traceback", p.stderr)

    def test_a_failed_suites_status_is_returned_with_the_report_written(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        log = d / "suite.log"
        log.write_text("Ran 4 tests in 1.0s\n\nFAILED (failures=1, errors=2)\n")
        p = self._cli("--no-run", "--log", str(log), "--exit-status", "1", "--out-dir", str(d / "out"))
        self.assertEqual(p.returncode, 1, p.stderr[-400:])
        rep = json.loads(sorted((d / "out").glob("test_report_*.json"))[0].read_text())
        self.assertFalse(rep["clean_tree_proof"])
        self.assertEqual((rep["failures"], rep["errors"]), (1, 2))


if __name__ == "__main__":
    unittest.main()
