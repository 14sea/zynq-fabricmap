"""host/b2_test_report.py — the clean-tree proof, fail-closed.

A report is only a PROOF when the worktree is clean, nothing was skipped, the suite exited zero
with no failures or errors, the instrument is at its pinned commit and clean, AND the pinned
decision surface verifies. Each of those is tested by removing exactly one of them. The suite is
not re-run here: `--no-run` builds the report from a captured log, which is how the flag exists.
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
SKIP_LOG = "....\n" + "-" * 70 + "\nRan 402 tests in 400.000s\n\nOK (skipped=3)\n"
FAIL_LOG = ("....\n" + "-" * 70 + "\nRan 402 tests in 400.000s\n\nFAILED (failures=1, errors=2)\n")


class Parsing(unittest.TestCase):
    def test_it_reads_the_counts_and_the_result_line(self):
        rep = tr.build(0, OK_LOG)
        self.assertEqual(rep["ran"], 402)
        self.assertEqual(rep["result_line"], "OK")
        self.assertEqual((rep["skipped"], rep["failures"], rep["errors"]), (0, 0, 0))
        self.assertEqual(rep["schema"], tr.SCHEMA)
        self.assertEqual(rep["scope"], "whole suite")
        self.assertEqual(tr.build(0, OK_LOG, focused=True)["scope"], "focused (test_b[23]*)")

    def test_it_reads_a_skipped_and_a_failed_run(self):
        self.assertEqual(tr.build(0, SKIP_LOG)["skipped"], 3)
        bad = tr.build(1, FAIL_LOG)
        self.assertEqual((bad["failures"], bad["errors"]), (1, 2))
        self.assertTrue(bad["result_line"].startswith("FAILED"))
        self.assertFalse(bad["clean_tree_proof"])

    def test_a_log_it_cannot_parse_is_never_a_proof(self):
        rep = tr.build(0, "nothing that looks like a unittest run\n")
        self.assertIsNone(rep["ran"])
        self.assertIsNone(rep["result_line"])
        self.assertFalse(rep["clean_tree_proof"])


class CleanTreeProof(unittest.TestCase):
    """Exactly one condition removed at a time, from a report that would otherwise qualify."""

    @staticmethod
    def _qualifying() -> dict:
        rep = tr.build(0, OK_LOG)
        rep["worktree_dirty"] = False
        rep["instrument"] = dict(rep["instrument"], dirty=False,
                                 head=rep["instrument"]["pinned_commit"])
        rep["pins"] = dict(rep["pins"], pins_verified=True, pins_refusal=None)
        return rep

    @staticmethod
    def _proof(rep: dict) -> bool:
        return (rep["worktree_dirty"] is False and rep["skipped"] == 0 and rep["exit_status"] == 0
                and rep["failures"] == 0 and rep["errors"] == 0 and rep["ran"] is not None
                and rep["instrument"]["head"] == rep["instrument"]["pinned_commit"]
                and rep["instrument"]["dirty"] is False and rep["pins"]["pins_verified"] is True)

    def test_the_qualifying_report_is_a_proof(self):
        self.assertTrue(self._proof(self._qualifying()))

    def test_each_condition_alone_destroys_it(self):
        cases = {
            "dirty worktree": lambda r: r.__setitem__("worktree_dirty", True),
            "unknown worktree state": lambda r: r.__setitem__("worktree_dirty", None),
            "a skip": lambda r: r.__setitem__("skipped", 1),
            "a non-zero exit": lambda r: r.__setitem__("exit_status", 1),
            "a failure": lambda r: r.__setitem__("failures", 1),
            "an error": lambda r: r.__setitem__("errors", 1),
            "an unparseable log": lambda r: r.__setitem__("ran", None),
            "the instrument at another commit": lambda r: r["instrument"].__setitem__("head", "0" * 40),
            "a dirty instrument": lambda r: r["instrument"].__setitem__("dirty", True),
            "a drifted pin table": lambda r: r["pins"].__setitem__("pins_verified", False),
        }
        for name, mutate in cases.items():
            with self.subTest(condition=name):
                rep = self._qualifying()
                mutate(rep)
                self.assertFalse(self._proof(rep), f"{name} still counted as a clean-tree proof")

    def test_the_builder_computes_the_same_verdict(self):
        rep = tr.build(0, OK_LOG)
        self.assertEqual(rep["clean_tree_proof"], self._proof(rep))


class Pins(unittest.TestCase):
    def test_the_pinned_surface_is_reverified_while_the_report_is_built(self):
        state = tr.pin_state()
        self.assertTrue(state["pins_verified"], state.get("pins_refusal"))
        self.assertEqual(state["files_verified"], b2_pins.generate()["file_count"])
        self.assertEqual(state["b1_files_verified"], 105)
        self.assertIn("no manifest before S0" if not state["manifest_present"] else "manifest's pin",
                      state["bound_to"])

    def test_a_drifted_surface_is_named_and_is_not_a_proof(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        table = json.loads((R / "manifests/b2_instrument_pins.json").read_text())
        first = sorted(table["files"])[0]
        (d / "manifests").mkdir(parents=True)
        for rel in list(table["files"]) + ["manifests/b2_instrument_pins.json",
                                           "manifests/b1_instrument_pins.json", "manifests/b1_manifest.json"]:
            dest = d / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(R / rel, dest)
        (d / first).write_text((d / first).read_text() + "\n# review drift\n")
        state = tr.pin_state(root=d)
        self.assertFalse(state["pins_verified"])
        self.assertIn("PinRefusal", state["pins_refusal"])
        rep = tr.build(0, OK_LOG, root=d)
        self.assertFalse(rep["clean_tree_proof"])


class TheCommandLine(unittest.TestCase):
    def test_no_run_builds_a_report_from_a_captured_log(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        log = d / "suite.log"
        log.write_text(OK_LOG)
        p = subprocess.run([sys.executable, str(R / "host/b2_test_report.py"), "--no-run",
                            "--log", str(log), "--exit-status", "0", "--out-dir", str(d / "out")],
                           capture_output=True, text=True, cwd=R)
        self.assertEqual(p.returncode, 0, p.stderr[-400:])
        written = sorted((d / "out").glob("test_report_*.json"))
        self.assertEqual(len(written), 1, p.stdout)
        rep = json.loads(written[0].read_text())
        self.assertEqual(rep["ran"], 402)
        self.assertEqual(rep["schema_version"], tr.SCHEMA_VERSION)
        self.assertIn("clean_tree_proof", rep)
        self.assertIn("manifests/b2_instrument_pins.json", rep["artifacts_sha256"])

    def test_no_run_without_its_inputs_exits_three(self):
        for args in (["--no-run"], ["--no-run", "--exit-status", "0"]):
            with self.subTest(args=args):
                p = subprocess.run([sys.executable, str(R / "host/b2_test_report.py"), *args],
                                   capture_output=True, text=True, cwd=R)
                self.assertEqual(p.returncode, 3, p.stderr[-300:])
                self.assertIn("needs --log and --exit-status", p.stderr)

    def test_a_failed_suite_is_reported_and_its_status_returned(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        log = d / "suite.log"
        log.write_text(FAIL_LOG)
        p = subprocess.run([sys.executable, str(R / "host/b2_test_report.py"), "--no-run",
                            "--log", str(log), "--exit-status", "1", "--out-dir", str(d / "out")],
                           capture_output=True, text=True, cwd=R)
        self.assertEqual(p.returncode, 1, p.stderr[-400:])
        rep = json.loads(sorted((d / "out").glob("test_report_*.json"))[0].read_text())
        self.assertFalse(rep["clean_tree_proof"])
        self.assertEqual((rep["failures"], rep["errors"]), (1, 2))


if __name__ == "__main__":
    unittest.main()
