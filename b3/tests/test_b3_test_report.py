"""b3/host/b3_test_report.py — the B3 clean-tree proof, fail-closed.

Every case drives the PRODUCTION verdict (`b3_test_report.build` / `proof_refusals`); none reimplements it (the
B2 lesson of 2026-09-12: a copied condition list let a removed production check pass). A positive control — three
qualifying runs between two agreeing snapshots, the pinned surface manifest-bound and verified, every required
artifact present, the removal control exact — is built first, and each condition is then removed from it one at
a time, so deleting a production check fails a test here.

The pinned surface's BINDING is exercised on a temporary tree in all three modes (no table → unbound_snapshot;
table without manifest → table_self_bound, a diagnostic; table and manifest → manifest_bound through
`b3_manifest.read_manifest` and `b3_pins.verify`), and only the last can be `pins_verified`. The shadow and the
three runs are exercised with a fake runner (order, cwd, the shadow outside the root and removed after) and,
on a small temporary tree, with the REAL discovery command — the sentinel listed in the B3 run and gone from
the removal run, one test fewer.

Nothing here runs the canonical proof, writes under evidence/, generates a pin table or touches a manifest.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
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
for p in (R / "host", R / "b3/host", R / "b3/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b3_manifest as bman  # noqa: E402
import b3_pins as bp  # noqa: E402
import b3_test_report as tr  # noqa: E402

B3_IDS = [tr.SENTINEL_ID, "test_b3_pins.TheRule.test_discovery_is_exactly_the_rule", "test_b3_records.Records.test_a", "test_b3_runner.ZeroContact.test_b"]
# Tests with a docstring are listed on TWO lines: the header, then the docstring's first line ending in the status
# (the owner's P1 on 5b12dd2). The fixture mixes both forms; a docstring line may itself look like prose with parentheses.
DOCSTRINGS = {"test_b3_records.Records.test_a": "The owner's P2 on 02d179c: a source read earlier (in the snapshot) changed while a LATER one was",
              "test_b3_runner.ZeroContact.test_b": "Listed, then unexaminable (its directory closed) before lstat: named."}
RULE = "-" * 70


def verbose_log(ids: list[str], ran: int | None = None, result: str = "OK", status: str = "ok") -> str:
    body = "".join((f"{i.rsplit('.', 1)[1]} ({i})\n{DOCSTRINGS[i]} ... {status}\n" if i in DOCSTRINGS else f"{i.rsplit('.', 1)[1]} ({i}) ... {status}\n") for i in ids)
    return f"{body}\n{RULE}\nRan {len(ids) if ran is None else ran} tests in 1.500s\n\n{result}\n"


B2_LOG = "." * 20 + f"\n{RULE}\nRan 2096 tests in 700.000s\n\nOK\n"
B3_LOG = verbose_log(B3_IDS)
REMOVAL_LOG = verbose_log([i for i in B3_IDS if i != tr.SENTINEL_ID])
SHADOW_ROOT = "/tmp/b3_removal_control_fixture"


def clean_pins() -> dict:
    files = {"b3/host/b3_pins.py": "a" * 64, "b3/tests/test_b3_pins.py": "b" * 64, "docs/b3_architecture.md": "c" * 64}
    return {"table_present": True, "manifest_present": True, "mode": "manifest_bound",
            "snapshot": {"file_count": 3, "files": files, "digest": tr.canonical_digest(files)}, "snapshot_refusal": None,
            "pins_verified": True, "pins_refusal": None, "diagnostic": None, "files_verified": 3, "pins_sha256": "d" * 64}


def clean_snapshot() -> dict:
    return {"at": "2026-09-27T000000Z", "root": str(R), "head": "a" * 40, "worktree_dirty": False,
            "instrument": {"root": "/instrument", "head": "b" * 40, "dirty": False, "pinned_commit": "b" * 40},
            "pins": clean_pins(),
            "artifacts_sha256": {rel: hashlib.sha256(rel.encode()).hexdigest() for rel in tr.REQUIRED_ARTIFACTS},
            "artifacts_refusals": {},
            "b1_carrier": {"expected": tr.B1_CARRIER_REL, "named": tr.B1_CARRIER_REL}}


def suite(name: str, log: str, cwd: str = str(R), exit_status: int = 0) -> dict:
    return {"name": name, "argv": tr.suite_argv(name), "cwd": cwd, "started_at": "2026-09-27T000001Z", "wall_s": 1.0,
            "exit_status": exit_status, "log": log, "log_sha256": hashlib.sha256(log.encode()).hexdigest()}


def qualifying_run() -> dict:
    snap = clean_snapshot()
    return {"executed": True, "start": snap, "end": copy.deepcopy(snap),
            "suites": {"b2_tree": suite("b2_tree", B2_LOG), "b3_tree": suite("b3_tree", B3_LOG),
                       "b3_removal": suite("b3_removal", REMOVAL_LOG, cwd=SHADOW_ROOT)},
            "shadow": {"root": SHADOW_ROOT, "removed": tr.SENTINEL_FILE, "sentinel_in_tree": True,
                       "tests_linked": ["b3_test_fixtures.py", "test_b3_pins.py"], "removed_after": True}}


class Verdict(unittest.TestCase):
    def refused(self, mutate, needle: str, prefix: str | None = None) -> dict:
        run = qualifying_run()
        mutate(run)
        try:
            rep = tr.build(run)
        except Exception as exc:                 # noqa: BLE001 — the defect these cases exist for
            self.fail(f"build raised {type(exc).__name__}: {exc}")
        self.assertFalse(rep["clean_tree_proof"], rep["proof_refusals"])
        hits = [x for x in rep["proof_refusals"] if needle in x and (prefix is None or x.startswith(prefix))]
        self.assertTrue(hits, (prefix, needle, rep["proof_refusals"]))
        return rep


# ------------------------------------------------------------------ the positive control


class ThePositiveControl(Verdict):
    def test_a_qualifying_run_is_a_proof(self):
        rep = tr.build(qualifying_run())
        self.assertEqual(rep["proof_refusals"], [])
        self.assertTrue(rep["clean_tree_proof"])
        self.assertEqual(rep["ran"], {"b2_tree": 2096, "b3_tree": 4, "b3_removal": 3})
        self.assertEqual(rep["exit_status"], {"b2_tree": 0, "b3_tree": 0, "b3_removal": 0})
        self.assertEqual(rep["removal_control"], {"b3_ran": 4, "removal_ran": 3, "sentinel_in_b3_listing": 1, "sentinel_in_removal_listing": 0})
        self.assertEqual(rep["head_at_run"], "a" * 40, "the provenance must be the START snapshot")
        self.assertEqual((rep["schema"], rep["schema_version"], rep["package"]), (tr.SCHEMA, tr.SCHEMA_VERSION, tr.PACKAGE))
        for name, log in (("b2_tree", B2_LOG), ("b3_tree", B3_LOG), ("b3_removal", REMOVAL_LOG)):
            self.assertEqual(rep["suites"][name]["log_sha256"], hashlib.sha256(log.encode()).hexdigest())
            self.assertEqual(rep["suites"][name]["log_text"], log)                  # the log itself is kept
            self.assertEqual(rep["suites"][name]["argv"], tr.suite_argv(name))
        self.assertEqual(rep["commands"]["b2_tree"], [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"])
        self.assertEqual(rep["commands"]["b3_tree"], [sys.executable, "-B", "-m", "unittest", "discover", "-v", "-s", "b3/tests"])
        self.assertEqual(rep["commands"]["b3_removal"], rep["commands"]["b3_tree"])
        self.assertEqual(rep["suites"]["b3_tree"]["listed"], B3_IDS)
        self.assertIsNone(rep["suites"]["b2_tree"]["listed"])
        json.dumps(rep, sort_keys=True)                                                 # serialisable as published

    def test_the_report_is_never_a_proof_without_all_three_runs(self):
        for name in tr.SUITES:
            with self.subTest(name=name):
                self.refused(lambda r, n=name: r["suites"].pop(n), f"{name}: no run record")
                self.refused(lambda r, n=name: r["suites"].__setitem__(n, "nope"), f"{name}: no run record")


# ------------------------------------------------------------------ the log contract, per run


class TheLogContract(Verdict):
    CASES = [
        ("Ran 1869 tests in 400.000s\n", "no OK or FAILED result line"),
        ("Ran 1869 tests in 400.000s\n\nFAILED\n", "says FAILED"),
        ("Ran 0 tests in 0.000s\n\nOK\n", "zero tests"),
        ("Ran 1869\n", "no complete 'Ran N tests in X.XXXs' line"),
        ("Ran 4 tests in 1.0s\n\nOK (skipped=unknown)\n", "unparsed counter"),
        ("Ran 4 tests in 1.0s\n\nFAILED (failures=1, errors=2)\n", "says FAILED"),
        ("Ran 4 tests in 1.0s\n\nOK (skipped=3)\n", "not exactly 'OK'"),
        ("Ran 4 tests in 1.0s\n\nOK\nRan 5 tests in 1.0s\n\nOK\n", "which run is this"),
        ("nothing that looks like a unittest run\n", "no complete 'Ran N tests in X.XXXs' line"),
        ("Ran 4 tests in \n\nOK\n", "no complete 'Ran N tests in X.XXXs' line"),
        ("Ran 4 tests in nonsense\n\nOK\n", "no complete 'Ran N tests in X.XXXs' line"),
        ("Ran 4 tests in 1.000\n\nOK\n", "no complete 'Ran N tests in X.XXXs' line"),
        ("Ran 4 tests in 1.000s and more\n\nOK\n", "no complete 'Ran N tests in X.XXXs' line"),
        ("Ran 4 tests in 1.000s\n\nFAILED (failures=1)\n\nOK\n", "which result is this"),
        ("Ran 4 tests in 1.000s\n\nOK\nOK\n", "which result is this"),
        ("OK\nRan 4 tests in 1.000s\n", "comes before the run summary"),
        ("Ran 4 tests in 1.000s\n\nOK\nand then something else\n", "not the last thing the log says"),
    ]

    def test_every_review_fixture_through_every_run(self):
        for name in tr.SUITES:
            for log, needle in self.CASES:
                with self.subTest(run=name, log=log[:30]):
                    self.refused(lambda r, n=name, lg=log: r["suites"][n].__setitem__("log", lg), needle, prefix=f"{name}: ")

    def test_a_counted_failure_is_counted(self):
        rep = self.refused(lambda r: r["suites"]["b2_tree"].__setitem__("log", "Ran 4 tests in 1.0s\n\nFAILED (failures=1, errors=2)\n"), "says FAILED", prefix="b2_tree: ")
        self.assertEqual((rep["suites"]["b2_tree"]["log"]["failures"], rep["suites"]["b2_tree"]["log"]["errors"]), (1, 2))

    def test_a_skipped_run_in_the_verbose_listing_is_not_a_proof(self):
        log = B3_LOG.replace("OK\n", "OK (skipped=1)\n")
        self.refused(lambda r: r["suites"]["b3_tree"].__setitem__("log", log), "b3_tree: skipped is 1, not zero")
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("log", REMOVAL_LOG.replace("OK\n", "OK (skipped=1)\n")), "b3_removal: skipped is 1, not zero")

    def test_a_log_that_is_not_text_is_named_not_raised(self):
        for name in tr.SUITES:
            for bad in (None, [1], 7, {"a": 1}, b"bytes"):
                with self.subTest(run=name, log=repr(bad)[:12]):
                    rep = self.refused(lambda r, n=name, b=bad: r["suites"][n].__setitem__("log", b), f"{name}: the log is")
                    self.assertEqual(rep["suites"][name]["log_sha256"], hashlib.sha256(b"").hexdigest())

    def test_a_non_zero_exit_and_a_foreign_command(self):
        for name in tr.SUITES:
            with self.subTest(run=name):
                self.refused(lambda r, n=name: r["suites"][n].__setitem__("exit_status", 1), f"{name}: the run exited 1")
                self.refused(lambda r, n=name: r["suites"][n].__setitem__("exit_status", None), f"{name}: the run exited None")
                without_b = [a for a in tr.suite_argv(name) if a != "-B"]
                self.refused(lambda r, n=name, a=without_b: r["suites"][n].__setitem__("argv", a), f"{name}: the command run was")
                focused = tr.suite_argv(name) + ["-p", "test_b3_pins.py"]
                self.refused(lambda r, n=name, a=focused: r["suites"][n].__setitem__("argv", a), f"{name}: the command run was")
        self.refused(lambda r: r["suites"]["b3_tree"].__setitem__("argv", tr.suite_argv("b2_tree")), "b3_tree: the command run was")


# ------------------------------------------------------------------ the verbose listing


class TheListing(unittest.TestCase):
    CAPTURED = ("test_doc (test_demo.D.test_doc)\n"
                "A docstring's first line. ... ok\n"
                "test_skip (test_demo.D.test_skip) ... skipped 'why'\n"
                "test_sub (test_demo.D.test_sub) ... \n"
                "  test_sub (test_demo.D.test_sub) (i=1) ... FAIL\n"
                "test_plain (test_demo.D.test_plain) ... ok\n"
                "test_two (test_demo.E.test_two)\n"
                "Listed, then unexaminable (its directory closed) before lstat: named. The permission itself is ... ok\n"
                "test_err (test_demo.E.test_err) ... ERROR\n"
                "\n" + RULE + "\nRan 6 tests in 0.010s\n\nFAILED (failures=1, errors=1, skipped=1)\n")

    def test_the_shapes_unittest_prints(self):
        """Measured on this interpreter: one line without a docstring; two lines with one; a subTest failure's
        header with a bare ` ... ` and its indented lines; skipped / FAIL / ERROR statuses. A test is listed by its
        header at column 0, exactly once."""
        self.assertEqual(tr.listed_tests(self.CAPTURED),
                         ["test_demo.D.test_doc", "test_demo.D.test_skip", "test_demo.D.test_sub", "test_demo.D.test_plain", "test_demo.E.test_two", "test_demo.E.test_err"])
        self.assertEqual(len(tr.listed_tests(self.CAPTURED)), tr.parse_log(self.CAPTURED)["ran"])
        self.assertEqual(tr.listed_tests(B3_LOG), B3_IDS)
        self.assertEqual(tr.listed_tests(REMOVAL_LOG), [i for i in B3_IDS if i != tr.SENTINEL_ID])
        self.assertEqual(tr.listed_tests(verbose_log(B3_IDS, status="FAIL")), B3_IDS)

    def test_what_is_not_a_header(self):
        for line in ("Listed, then unexaminable (its directory closed) before lstat: named. ... ok",       # a docstring line
                     "The owner's P2 on 02d179c: a source (test_x.C.test_x) ... ok",                        # prose with an id-shaped token
                     "  test_sub (test_demo.D.test_sub) (i=1) ... FAIL",                                   # indented: a subTest line
                     "test_a (test_demo.D.test_b) ... ok",                                                # the name is not the id's last component
                     "test_a (test_a) ... ok",                                                            # no module.Class
                     "test_a(test_demo.D.test_a) ... ok",
                     "Ran 4 tests in 1.000s", RULE, "OK", ""):
            with self.subTest(line=line[:40]):
                self.assertEqual(tr.listed_tests(line + "\n"), [])
        self.assertEqual(tr.listed_tests(None), [])
        self.assertEqual(tr.listed_tests(b"bytes"), [])

    def test_a_real_verbose_run_lists_every_test_it_ran(self):
        """The load-bearing fixture: the REAL command on this repository's test_b3_pins.py (docstring tests among
        them) — the listing count equals the summary's Ran N, every id unique."""
        p = subprocess.run(tr.suite_argv("b3_tree") + ["-p", "test_b3_pins.py"], cwd=R, capture_output=True, text=True)
        log = p.stdout + p.stderr
        parsed = tr.parse_log(log)
        listed = tr.listed_tests(log)
        self.assertEqual(p.returncode, 0, log[-500:])
        self.assertEqual(parsed["result_line"], "OK")
        self.assertGreater(parsed["ran"], 30)
        self.assertEqual(len(listed), parsed["ran"])
        self.assertEqual(len(set(listed)), parsed["ran"])
        self.assertTrue(all(i.startswith("test_b3_pins.") for i in listed))
        two_line = [ln for ln in log.splitlines() if tr.LISTED_LINE.fullmatch(ln) and " ... " not in ln]
        self.assertGreater(len(two_line), 5, "the fixture must contain docstring (two-line) tests")


# ------------------------------------------------------------------ the removal control


class TheRemovalControl(Verdict):
    def test_the_sentinel_must_be_listed_exactly_once_in_the_b3_run(self):
        self.refused(lambda r: r["suites"]["b3_tree"].__setitem__("log", verbose_log([i for i in B3_IDS if i != tr.SENTINEL_ID], ran=4)),
                     "b3_tree: the verbose listing names the sentinel 0 times")
        self.refused(lambda r: r["suites"]["b3_tree"].__setitem__("log", verbose_log(B3_IDS + [tr.SENTINEL_ID])),
                     "b3_tree: the verbose listing names the sentinel 2 times")

    def test_the_sentinel_must_be_gone_from_the_removal_run(self):
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("log", verbose_log(B3_IDS[:3], ran=3)),
                     "b3_removal: the verbose listing still names the sentinel")

    def test_the_removal_run_must_run_exactly_one_fewer(self):
        ids = [i for i in B3_IDS if i != tr.SENTINEL_ID]
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("log", verbose_log(ids + ["test_x.T.test_extra"])),
                     "b3_removal: ran 4, not exactly one fewer than b3_tree's 4")
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("log", verbose_log(ids[:2])),
                     "b3_removal: ran 2, not exactly one fewer than b3_tree's 4")

    def test_the_verbose_listing_must_match_the_summary(self):
        self.refused(lambda r: r["suites"]["b3_tree"].__setitem__("log", verbose_log(B3_IDS, ran=5)),
                     "b3_tree: the verbose listing has 4 tests but the summary ran 5")
        ids = [i for i in B3_IDS if i != tr.SENTINEL_ID]
        short = verbose_log(ids[:-1], ran=3)                                   # ids[-1] is a two-line (docstring) entry: dropped whole
        self.assertEqual(len(tr.listed_tests(short)), 2)
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("log", short), "b3_removal: the verbose listing has 2 tests but the summary ran 3")
        # a docstring line that mentions an id-shaped token is NOT a header; an indented subTest line is not either
        prose = verbose_log(B3_IDS, ran=5).replace(f"\n{RULE}", f"The owner's note (mod.C.test_z) ... ok\n  test_z (mod.C.test_z) (i=1) ... FAIL\n\n{RULE}", 1)
        self.refused(lambda r: r["suites"]["b3_tree"].__setitem__("log", prose), "b3_tree: the verbose listing has 4 tests but the summary ran 5")

    def test_the_removal_listing_must_be_the_b3_listing_minus_the_sentinel(self):
        """The owner's P1 on 5b12dd2: one fewer is not enough — a substituted id passed. Membership AND order."""
        ids = [i for i in B3_IDS if i != tr.SENTINEL_ID]
        substituted = ids[:-1] + ["test_b3_other.Other.test_z"]
        rep = self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("log", verbose_log(substituted)),
                           f"b3_removal: the verbose listing is not b3_tree's listing minus the sentinel: missing ['{ids[-1]}']: unexpected ['test_b3_other.Other.test_z']")
        self.assertEqual(rep["removal_control"]["removal_ran"], 3)                       # the count alone would have passed
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("log", verbose_log(list(reversed(ids)))),
                     "b3_removal: the verbose listing is not b3_tree's listing minus the sentinel: the order differs")
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("log", verbose_log(ids[:2] + [ids[1]])),
                     "b3_removal: the verbose listing is not b3_tree's listing minus the sentinel")

    def test_the_removal_run_itself_must_be_clean(self):
        ids = [i for i in B3_IDS if i != tr.SENTINEL_ID]
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("exit_status", 1), "b3_removal: the run exited 1")
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("log", verbose_log(ids, result="FAILED (failures=1)")), "says FAILED", prefix="b3_removal: ")
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("log", verbose_log(ids, result="OK (skipped=2)")), "b3_removal: skipped is 2")

    def test_the_removal_run_must_run_in_the_shadow_that_was_built(self):
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("cwd", str(R)), "b3_removal: ran in the same directory as b3_tree")
        self.refused(lambda r: r["suites"]["b3_removal"].__setitem__("cwd", "/tmp/somewhere_else"), "b3_removal did not run in the shadow that was built")
        self.refused(lambda r: r.__setitem__("shadow", None), "the shadow record is NoneType")
        self.refused(lambda r: r["shadow"].__setitem__("sentinel_in_tree", False), "was not in b3/tests: there was nothing to remove")
        self.refused(lambda r: r["shadow"].__setitem__("removed", "test_b3_pins.py"), "the shadow removed 'test_b3_pins.py', not test_b3_sentinel.py")
        self.refused(lambda r: r["shadow"].__setitem__("removed_after", False), "the shadow was not removed after the run (removed_after is False)")
        self.refused(lambda r: r["shadow"].pop("removed_after"), "the shadow was not removed after the run (removed_after is None)")

    def test_the_runs_must_happen_in_the_snapshotted_root_and_the_shadow_outside_it(self):
        """The owner's P1 on 5b12dd2: two runs in /elsewhere passed."""
        for name in ("b2_tree", "b3_tree"):
            with self.subTest(run=name):
                self.refused(lambda r, n=name: r["suites"][n].__setitem__("cwd", "/elsewhere"), f"{name}: ran in '/elsewhere', not in the snapshotted root")
                self.refused(lambda r, n=name: r["suites"][n].__setitem__("cwd", str(R) + "/b3"), f"{name}: ran in")
                self.refused(lambda r, n=name: r["suites"][n].__setitem__("cwd", None), f"{name}: ran in None")
        def both(r, cwd):
            for n in ("b2_tree", "b3_tree"):
                r["suites"][n]["cwd"] = cwd
        self.refused(lambda r: both(r, "/elsewhere"), "b2_tree: ran in '/elsewhere'")
        # the shadow must be outside the repository: inside it, or the repository inside it, or unnamed
        def shadow_at(r, root):
            r["shadow"]["root"] = root
            r["suites"]["b3_removal"]["cwd"] = root
        self.refused(lambda r: shadow_at(r, str(R) + "/shadow"), "is not outside the repository")
        self.refused(lambda r: shadow_at(r, str(R)), "is not outside the repository")
        self.refused(lambda r: shadow_at(r, str(R.parent)), "is not outside the repository")
        self.refused(lambda r: shadow_at(r, None), "the shadow names no root (None)")
        self.refused(lambda r: shadow_at(r, ""), "the shadow names no root ('')")
        self.refused(lambda r: r["start"].__setitem__("root", None), "the start snapshot names no root (None)")


# ------------------------------------------------------------------ the snapshots


class TheRunState(Verdict):
    def test_a_report_this_tool_did_not_run(self):
        self.refused(lambda r: r.__setitem__("executed", False), "not executed by this tool")
        self.refused(lambda r: r.__setitem__("executed", None), "not executed by this tool")

    def test_a_dirty_worktree_or_no_head_at_either_end(self):
        for end in ("start", "end"):
            with self.subTest(end=end):
                self.refused(lambda r, e=end: r[e].__setitem__("worktree_dirty", True), f"worktree was True at the {end}")
                self.refused(lambda r, e=end: r[e].__setitem__("worktree_dirty", None), f"worktree was None at the {end}")
                self.refused(lambda r, e=end: r[e].__setitem__("head", None), f"no HEAD was observed at the {end}")

    def test_the_instrument_off_its_pin_or_dirty(self):
        for end in ("start", "end"):
            with self.subTest(end=end):
                self.refused(lambda r, e=end: r[e]["instrument"].__setitem__("head", "0" * 40), f"at the {end}, not its pinned commit")
                self.refused(lambda r, e=end: r[e]["instrument"].__setitem__("head", None), f"at the {end}, not its pinned commit")
                self.refused(lambda r, e=end: r[e]["instrument"].__setitem__("dirty", True), f"instrument was True at the {end}")

    def test_head_moving_or_the_root_changing(self):
        self.refused(lambda r: r["end"].__setitem__("head", "d" * 40), "HEAD moved during the run")
        self.refused(lambda r: r["end"].__setitem__("root", "/elsewhere"), "the repository root changed")

    def test_the_binding_must_be_the_manifest_and_verified(self):
        """unbound_snapshot and table_self_bound are recorded, named — and never a proof."""
        for end in ("start", "end"):
            with self.subTest(end=end):
                rep = self.refused(lambda r, e=end: r[e]["pins"].update(mode="unbound_snapshot", pins_verified=False, table_present=False,
                                                                        pins_refusal="unbound_snapshot: manifests/b3_instrument_pins.json does not exist"),
                                   f"not bound to the B3 manifest at the {end} ('unbound_snapshot'): unbound_snapshot:")
                self.assertTrue(any(f"did not verify at the {end}" in x for x in rep["proof_refusals"]))
                self.refused(lambda r, e=end: r[e]["pins"].update(mode="table_self_bound", pins_verified=False, manifest_present=False,
                                                                  diagnostic={"verified": True, "refusal": None}, pins_refusal="table_self_bound: no manifest"),
                             f"not bound to the B3 manifest at the {end} ('table_self_bound')")
                # manifest_bound but the verify refused
                self.refused(lambda r, e=end: r[e]["pins"].update(pins_verified=False, pins_refusal="instrument pins: pinned files changed: b3/x: hash differs"),
                             f"did not verify at the {end}: instrument pins: pinned files changed")
                # a verified flag with the wrong mode is still not a proof (the flag is not trusted on its own)
                self.refused(lambda r, e=end: r[e]["pins"].update(mode="table_self_bound", pins_verified=True), f"not bound to the B3 manifest at the {end}")
                self.refused(lambda r, e=end: r[e]["pins"].update(snapshot=None, snapshot_refusal="PinRefusal: b3/link is a symbolic link"),
                             f"could not be snapshotted at the {end}: PinRefusal: b3/link is a symbolic link")

    def test_the_pinned_surface_changing_during_the_run(self):
        self.refused(lambda r: r["end"]["pins"]["snapshot"]["files"].__setitem__("b3/host/b3_pins.py", "f" * 64),
                     "the pinned surface changed during the run: ['b3/host/b3_pins.py']")
        self.refused(lambda r: r["end"]["pins"]["snapshot"]["files"].__setitem__("b3/host/new.py", "f" * 64),
                     "the pinned surface changed during the run: ['b3/host/new.py']")

    def test_every_required_artifact_must_be_present_at_both_ends(self):
        owner_listed = (bman.MANIFEST_REL, bman.PIN_TABLE_REL, bman.PREREG_REL, "docs/b3_architecture.md", bman.GATE_REL,
                        "evidence/b3/gate_2/raw_F1.json", "evidence/b3/gate_2/raw_F2.json", bman.PLAN_REL, bman.PREDICTION_REL,
                        bman.QUAL_PLAN_REL, bman.QUAL_PREDICTION_REL, bman.BUILD_EVIDENCE_REL, bman.IMAGE_REL,
                        *bman.FROZEN_INPUTS, bman.B1_MANIFEST_REL, "builds/b1/b1.bit")
        self.assertEqual(set(owner_listed), set(tr.REQUIRED_ARTIFACTS))
        self.assertEqual(len(bman.FROZEN_INPUTS), 7)
        for rel in tr.REQUIRED_ARTIFACTS:
            for end in ("start", "end"):
                with self.subTest(rel=rel, end=end):
                    rep = self.refused(lambda r, e=end, k=rel: r[e]["artifacts_sha256"].__setitem__(k, None), f"required artifacts absent at the {end}: ['{rel}']")
                    if end == "end":
                        self.assertTrue(any("changed during the run" in x for x in rep["proof_refusals"]))
        self.refused(lambda r: r["start"]["artifacts_sha256"].pop(bman.IMAGE_REL), f"required artifacts absent at the start: ['{bman.IMAGE_REL}']")
        self.refused(lambda r: r["start"]["artifacts_sha256"].__setitem__(bman.GATE_REL, 7), f"required artifacts absent at the start: ['{bman.GATE_REL}']")

    def test_an_artifact_changing_or_refused_during_the_run(self):
        self.refused(lambda r: r["end"]["artifacts_sha256"].__setitem__("docs/b3_architecture.md", "f" * 64),
                     "required artifacts changed during the run: ['docs/b3_architecture.md']")
        for end in ("start", "end"):
            self.refused(lambda r, e=end: r[e]["artifacts_refusals"].__setitem__(bman.PREREG_REL, "docs/b3_preregistration.md is a symbolic link"),
                         f"artifacts refused at the {end}")

    def test_the_b1_carrier_must_be_the_named_bitstream(self):
        for end in ("start", "end"):
            self.refused(lambda r, e=end: r[e]["b1_carrier"].__setitem__("named", None), f"names None as its carrier at the {end}")
            self.refused(lambda r, e=end: r[e]["b1_carrier"].__setitem__("named", "builds/b1/other.bit"), f"names 'builds/b1/other.bit' as its carrier at the {end}")
            self.refused(lambda r, e=end: r[e].__setitem__("b1_carrier", None), f"as its carrier at the {end}")

    def test_a_run_with_no_snapshots_and_nested_blocks_of_the_wrong_shape_are_named_not_raised(self):
        self.refused(lambda r: r.update(start=None, end=None), "no start and end snapshots")
        self.refused(lambda r: r.update(start="nope"), "no start and end snapshots")
        for field in ("instrument", "pins", "artifacts_sha256"):
            for bad in (["nope"], "nope", 7, None):
                with self.subTest(field=field, value=repr(bad)[:12]):
                    self.refused(lambda r, f=field, b=bad: r["start"].__setitem__(f, b), f"start snapshot's {field} is")

    def test_a_run_record_of_the_wrong_shape_is_named_not_raised(self):
        for bad in ((0, B2_LOG), "nope", None, 7, [0, B2_LOG]):
            with self.subTest(run=repr(bad)[:24]):
                try:
                    rep = tr.build(bad)
                except Exception as exc:         # noqa: BLE001
                    self.fail(f"{type(exc).__name__}: {exc}")
                self.assertFalse(rep["clean_tree_proof"])
                self.assertTrue(any("not executed by this tool" in x for x in rep["proof_refusals"]))
                self.assertIsNotNone(rep["run"]["shape"])


# ------------------------------------------------------------------ the binding, on a temporary tree


PINNED = {"b3/host/a.py": "print('a')\n", "b3/tests/test_a.py": "import unittest\n", "docs/b3_architecture.md": "# arch\n"}


def make_tree(d: Path) -> None:
    for rel, body in PINNED.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(body)
    (d / "manifests").mkdir()


class TheBinding(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="b3_tr_bind_"))
        self.addCleanup(shutil.rmtree, self.d, True)
        make_tree(self.d)

    def test_no_table_is_an_unbound_snapshot(self):
        st = tr.pin_state(self.d)
        self.assertEqual((st["mode"], st["table_present"], st["manifest_present"], st["pins_verified"]), ("unbound_snapshot", False, False, False))
        self.assertEqual(st["snapshot"]["file_count"], 3)
        self.assertEqual(st["snapshot"]["files"], bp.generate(self.d)["files"])
        self.assertEqual(st["snapshot"]["digest"], tr.canonical_digest(bp.generate(self.d)["files"]))
        self.assertIsNone(st["snapshot_refusal"])
        self.assertIn("unbound_snapshot", st["pins_refusal"])
        self.assertIsNone(st["diagnostic"])
        run = qualifying_run()
        run["start"]["pins"] = st
        rep = tr.build(run)
        self.assertFalse(rep["clean_tree_proof"])
        self.assertTrue(any("('unbound_snapshot')" in x for x in rep["proof_refusals"]))

    def test_a_snapshot_refusal_is_recorded_not_raised(self):
        os.symlink(self.d / "b3/host/a.py", self.d / "b3/link.py")
        st = tr.pin_state(self.d)
        self.assertIsNone(st["snapshot"])
        self.assertIn("b3/link.py is a symbolic link", st["snapshot_refusal"])
        self.assertFalse(st["pins_verified"])

    def test_a_table_without_a_manifest_is_a_diagnostic_never_verified(self):
        bp.write_table_once(bp.generate(self.d), self.d / bp.PIN_TABLE_REL)
        st = tr.pin_state(self.d)
        self.assertEqual((st["mode"], st["table_present"], st["manifest_present"], st["pins_verified"]), ("table_self_bound", True, False, False))
        self.assertEqual(st["diagnostic"]["verified"], True)
        self.assertEqual(st["diagnostic"]["files_verified"], 3)
        self.assertEqual(st["diagnostic"]["bound_to"], "the table's own bytes")
        self.assertIn("table_self_bound", st["pins_refusal"])
        self.assertIsNone(st["files_verified"])
        (self.d / "b3/host/a.py").write_text("changed\n")
        st = tr.pin_state(self.d)
        self.assertEqual(st["mode"], "table_self_bound")
        self.assertFalse(st["diagnostic"]["verified"])
        self.assertIn("b3/host/a.py: hash differs", st["diagnostic"]["refusal"])
        self.assertFalse(st["pins_verified"])
        run = qualifying_run()
        run["end"]["pins"] = st
        self.assertTrue(any("('table_self_bound')" in x for x in tr.build(run)["proof_refusals"]))

    def test_a_table_and_a_manifest_verify_through_the_trusted_reader(self):
        bp.write_table_once(bp.generate(self.d), self.d / bp.PIN_TABLE_REL)
        manifest = {"schema": bman.SCHEMA, "instrument_pins": bman.instrument_pins_block(self.d)}
        (self.d / bman.MANIFEST_REL).write_text(json.dumps(manifest))
        seen = []
        real = bman.read_manifest

        def read_manifest(path, wait=True):
            seen.append(Path(path))
            return real(path, wait)
        with mock.patch.object(bman, "read_manifest", read_manifest):
            st = tr.pin_state(self.d)
        self.assertEqual(seen, [self.d / bman.MANIFEST_REL])
        self.assertEqual((st["mode"], st["pins_verified"], st["pins_refusal"], st["files_verified"]), ("manifest_bound", True, None, 3))
        self.assertEqual(st["pins_sha256"], manifest["instrument_pins"]["sha256"])
        self.assertEqual(st["snapshot"]["file_count"], 3)
        run = qualifying_run()
        run["start"]["pins"] = st
        run["end"]["pins"] = copy.deepcopy(st)
        self.assertTrue(tr.build(run)["clean_tree_proof"])
        # the same tree, a source drifted: manifest_bound, refused by the pin verifier, never verified
        (self.d / "b3/host/a.py").write_text("changed\n")
        st = tr.pin_state(self.d)
        self.assertEqual((st["mode"], st["pins_verified"]), ("manifest_bound", False))
        self.assertIn("instrument pins: pinned files changed: b3/host/a.py: hash differs", st["pins_refusal"])
        (self.d / "b3/host/a.py").write_text(PINNED["b3/host/a.py"])
        # an unfinished transaction beside the manifest: the trusted reader's refusal, named
        journal = self.d / "manifests" / ".b3_manifest.json.transaction"
        journal.write_text("{}")
        st = tr.pin_state(self.d)
        self.assertEqual((st["mode"], st["pins_verified"]), ("manifest_bound", False))
        self.assertIn("manifest: ", st["pins_refusal"])
        self.assertIn("a b3_manifest transition did not finish", st["pins_refusal"])
        journal.unlink()
        # a manifest that is not JSON, a manifest that is a directory: named, not raised
        (self.d / bman.MANIFEST_REL).write_text("{not json")
        st = tr.pin_state(self.d)
        self.assertIn("manifest: manifests/b3_manifest.json is not readable JSON", st["pins_refusal"])
        (self.d / bman.MANIFEST_REL).unlink()
        (self.d / bman.MANIFEST_REL).mkdir()
        st = tr.pin_state(self.d)
        self.assertEqual(st["mode"], "manifest_bound")
        self.assertIn("manifest: manifests/b3_manifest.json cannot be read", st["pins_refusal"])
        self.assertFalse(st["pins_verified"])
        (self.d / bman.MANIFEST_REL).rmdir()
        # a manifest whose block is not the table's: the pin verifier's refusal
        (self.d / bman.MANIFEST_REL).write_text(json.dumps({"schema": bman.SCHEMA, "instrument_pins": {"path": bp.PIN_TABLE_REL, "sha256": "0" * 64}}))
        st = tr.pin_state(self.d)
        self.assertIn("instrument pins: manifests/b3_instrument_pins.json does not hash to the manifest's pin", st["pins_refusal"])

    def test_an_implementation_defect_in_the_binding_propagates(self):
        """A defect in the snapshot step is probed with NO table (so the verifier — which calls the same
        module-level snapshot — is never reached and cannot be the one raising); a defect in the verifier
        with the table and manifest present."""
        for exc in (TypeError("a defect"), KeyError("a defect")):
            with mock.patch.object(bp, "snapshot", side_effect=exc):
                with self.assertRaises(type(exc)):
                    tr.pin_state(self.d)
        bp.write_table_once(bp.generate(self.d), self.d / bp.PIN_TABLE_REL)
        (self.d / bman.MANIFEST_REL).write_text(json.dumps({"schema": bman.SCHEMA, "instrument_pins": bman.instrument_pins_block(self.d)}))
        for exc in (TypeError("a defect"), KeyError("a defect")):
            with mock.patch.object(bp, "verify", side_effect=exc):
                with self.assertRaises(type(exc)):
                    tr.pin_state(self.d)

    def test_artifacts_are_read_through_the_stable_reader(self):
        (self.d / "docs/b3_preregistration.md").write_text("prereg\n")
        (self.d / "evidence/b3").mkdir(parents=True)
        os.symlink(self.d / "docs/b3_architecture.md", self.d / "evidence/b3/plan.json")
        (self.d / "evidence/b3/prediction.json").mkdir()
        digests, refusals = tr.artifact_digests(self.d)
        self.assertEqual(set(digests), set(tr.REQUIRED_ARTIFACTS))
        self.assertEqual(digests["docs/b3_architecture.md"], hashlib.sha256(PINNED["docs/b3_architecture.md"].encode()).hexdigest())
        self.assertEqual(digests[bman.PREREG_REL], hashlib.sha256(b"prereg\n").hexdigest())
        self.assertIsNone(digests[bman.MANIFEST_REL])
        self.assertIsNone(digests[bman.PLAN_REL])
        self.assertIn("evidence/b3/plan.json is a symbolic link", refusals[bman.PLAN_REL])
        self.assertIsNone(digests[bman.PREDICTION_REL])
        self.assertIn("is a directory", refusals[bman.PREDICTION_REL])
        self.assertNotIn(bman.MANIFEST_REL, refusals)
        self.assertIsNone(tr.b1_carrier_named(self.d))
        (self.d / "manifests/b1_manifest.json").write_text(json.dumps({"carrier": {"bitstream": "builds/b1/b1.bit"}}))
        self.assertEqual(tr.b1_carrier_named(self.d), "builds/b1/b1.bit")
        (self.d / "manifests/b1_manifest.json").write_text(json.dumps({"carrier": {"bitstream": 7}}))
        self.assertIsNone(tr.b1_carrier_named(self.d))
        (self.d / "manifests/b1_manifest.json").write_text("nope")
        self.assertIsNone(tr.b1_carrier_named(self.d))


# ------------------------------------------------------------------ the real tree


class TheRealTree(unittest.TestCase):
    def test_a_snapshot_of_this_tree_has_the_shape_the_verdict_reads_and_is_not_yet_a_proof(self):
        snap = tr.snapshot(R)
        for key in ("at", "root", "head", "worktree_dirty", "instrument", "pins", "artifacts_sha256", "artifacts_refusals", "b1_carrier"):
            self.assertIn(key, snap)
        self.assertEqual(snap["instrument"]["pinned_commit"], tr.pl.INSTRUMENT_COMMIT)
        pins = snap["pins"]
        table = bp.generate(R)
        self.assertEqual(pins["snapshot"]["file_count"], table["file_count"])
        self.assertEqual(pins["snapshot"]["files"], table["files"])
        self.assertIn("b3/host/b3_test_report.py", pins["snapshot"]["files"])
        self.assertIn("b3/tests/test_b3_test_report.py", pins["snapshot"]["files"])
        self.assertEqual(set(snap["artifacts_sha256"]), set(tr.REQUIRED_ARTIFACTS))
        for rel, sha in bman.FROZEN_INPUTS.items():
            self.assertEqual(snap["artifacts_sha256"][rel], sha, rel)          # the seven frozen inputs, as frozen
        self.assertEqual(snap["b1_carrier"]["named"], tr.B1_CARRIER_REL)
        self.assertEqual(snap["artifacts_sha256"][tr.B1_CARRIER_REL], hashlib.sha256((R / tr.B1_CARRIER_REL).read_bytes()).hexdigest())
        if not (R / bp.PIN_TABLE_REL).exists():                                # before the pin table is generated
            self.assertEqual(pins["mode"], "unbound_snapshot")
            self.assertFalse(pins["pins_verified"])
            run = qualifying_run()
            run["start"], run["end"] = snap, copy.deepcopy(snap)
            rep = tr.build(run)
            self.assertFalse(rep["clean_tree_proof"])
            self.assertTrue(any("('unbound_snapshot')" in x for x in rep["proof_refusals"]))
            self.assertTrue(any(f"required artifacts absent at the start: " in x and bp.PIN_TABLE_REL in x for x in rep["proof_refusals"]))

    def test_the_sentinel_constants_name_the_real_sentinel(self):
        text = (R / tr.B3_START / tr.SENTINEL_FILE).read_text()
        module, cls, meth = tr.SENTINEL_ID.split(".")
        self.assertEqual(module, tr.SENTINEL_FILE[:-3])
        self.assertIn(f"class {cls}(unittest.TestCase)", text)
        self.assertIn(f"def {meth}(self)", text)
        self.assertEqual(text.count("def test_"), 1)


# ------------------------------------------------------------------ the shadow and the three runs


class Tiny(unittest.TestCase):
    """A small tree with a real sentinel, two more B3 tests and one B2 test — enough for the REAL discovery command."""

    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="b3_tr_tree_"))
        self.addCleanup(shutil.rmtree, self.t, True)
        (self.t / "b3/tests").mkdir(parents=True)
        (self.t / "b3/host").mkdir()
        (self.t / "tests").mkdir()
        (self.t / "docs").mkdir()
        (self.t / "docs/b3_architecture.md").write_text("# arch\n")
        (self.t / "b3/host/a.py").write_text("x = 1\n")
        (self.t / "b3/tests" / tr.SENTINEL_FILE).write_text((R / tr.B3_START / tr.SENTINEL_FILE).read_text())
        (self.t / "b3/tests/test_two.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        \"\"\"A docstring (with parentheses) on its first line.\n        and more\"\"\"\n"
                                                     "    def test_b(self): pass\n    def test_c(self):\n        \"\"\"Another.\"\"\"\n")
        (self.t / "b3/tests/__pycache__").mkdir()
        (self.t / "b3/tests/__pycache__/junk.pyc").write_bytes(b"\x00")
        (self.t / "tests/test_one.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_x(self): pass\n")


class Completed:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


class TheShadow(Tiny):
    def test_the_shadow_is_the_tree_minus_the_sentinel(self):
        d = Path(tempfile.mkdtemp(prefix="b3_tr_shadow_"))
        self.addCleanup(shutil.rmtree, d, True)
        sh = tr.build_shadow(self.t, d)
        self.assertEqual(sh, {"root": str(d), "removed": tr.SENTINEL_FILE, "sentinel_in_tree": True, "tests_linked": ["test_two.py"]})
        self.assertEqual(sorted(os.listdir(d)), sorted(os.listdir(self.t)))
        for name in os.listdir(self.t):
            if name != "b3":
                self.assertTrue(os.path.islink(d / name), name)
                self.assertEqual(os.readlink(d / name), str(self.t / name))
        self.assertFalse(os.path.islink(d / "b3"))
        self.assertTrue(os.path.islink(d / "b3/host"))
        self.assertFalse(os.path.islink(d / "b3/tests"))
        self.assertEqual(sorted(os.listdir(d / "b3/tests")), ["test_two.py"])          # no sentinel, no __pycache__
        self.assertEqual(os.readlink(d / "b3/tests/test_two.py"), str(self.t / "b3/tests/test_two.py"))
        self.assertTrue((self.t / "b3/tests" / tr.SENTINEL_FILE).exists())                # the tree itself untouched

    def test_the_shadow_without_a_sentinel_to_remove_says_so(self):
        (self.t / "b3/tests" / tr.SENTINEL_FILE).unlink()
        d = Path(tempfile.mkdtemp(prefix="b3_tr_shadow_"))
        self.addCleanup(shutil.rmtree, d, True)
        sh = tr.build_shadow(self.t, d)
        self.assertFalse(sh["sentinel_in_tree"])
        run = qualifying_run()
        run["shadow"].update(sh)
        self.assertTrue(any("nothing to remove" in x for x in tr.build(run)["proof_refusals"]))

    def test_the_shadow_must_be_outside_the_tree_and_empty(self):
        inside = self.t / "shadow"
        inside.mkdir()
        with self.assertRaises(tr.ReportIOError) as cm:
            tr.build_shadow(self.t, inside)
        self.assertIn("inside the repository", str(cm.exception))
        with self.assertRaises(tr.ReportIOError):
            tr.build_shadow(self.t, self.t)
        d = Path(tempfile.mkdtemp(prefix="b3_tr_shadow_"))
        self.addCleanup(shutil.rmtree, d, True)
        (d / "occupied").write_text("x")
        with self.assertRaises(tr.ReportIOError) as cm:
            tr.build_shadow(self.t, d)
        self.assertIn("is not empty", str(cm.exception))


class TheRuns(Tiny):
    def test_the_three_runs_in_order_between_the_snapshots_with_the_shadow_removed_after(self):
        calls: list = []
        shadows: list = []

        def runner(argv, cwd, capture_output, text):
            calls.append(("run", list(argv), Path(cwd)))
            if Path(cwd) != self.t:
                shadows.append(Path(cwd))
                self.assertTrue(Path(cwd).exists())
                self.assertFalse((Path(cwd) / "b3/tests" / tr.SENTINEL_FILE).exists())
                self.assertTrue((Path(cwd) / "b3/tests/test_two.py").exists())
                self.assertFalse(Path(cwd).resolve().is_relative_to(self.t.resolve()))
            return Completed(0, "", "Ran 1 test in 0.001s\n\nOK\n")
        real = tr.snapshot

        def snapshot(root):
            calls.append(("snapshot", root))
            return real(root)
        with mock.patch.object(tr, "snapshot", snapshot):
            run = tr.run_suites(self.t, runner=runner)
        kinds = [c[0] for c in calls]
        self.assertEqual(kinds, ["snapshot", "run", "run", "run", "snapshot"])
        self.assertEqual([c[1] for c in calls if c[0] == "run"], [tr.suite_argv("b2_tree"), tr.suite_argv("b3_tree"), tr.suite_argv("b3_removal")])
        self.assertEqual([c[2] for c in calls if c[0] == "run"][:2], [self.t, self.t])
        self.assertEqual(len(shadows), 1)
        self.assertFalse(shadows[0].exists(), "the shadow must be removed after the run")
        self.assertEqual(run["shadow"]["root"], str(shadows[0]))
        self.assertTrue(run["shadow"]["removed_after"])
        self.assertEqual(run["suites"]["b3_removal"]["cwd"], str(shadows[0]))
        self.assertEqual(run["suites"]["b2_tree"]["cwd"], str(self.t))
        self.assertTrue(run["executed"])
        self.assertEqual(run["start"]["root"], str(self.t))
        for name in tr.SUITES:
            self.assertEqual(run["suites"][name]["log"], "Ran 1 test in 0.001s\n\nOK\n")
            self.assertEqual(run["suites"][name]["exit_status"], 0)

    def test_a_shadow_that_cannot_be_removed_is_exit_three_never_a_report(self):
        """The owner's P2 on 5b12dd2: rmtree(ignore_errors=True) swallowed the failure and the function returned."""
        real = shutil.rmtree
        left: list = []

        def failing_rmtree(path, *a, **kw):
            if Path(path).name.startswith("b3_removal_control_") and not kw.get("ignore_errors"):
                left.append(Path(path))
                raise OSError(13, "Permission denied", str(path))
            return real(path, *a, **kw)
        with mock.patch.object(shutil, "rmtree", failing_rmtree):
            with self.assertRaises(tr.ReportIOError) as cm:
                tr.run_suites(self.t, runner=TheRuns.ok)
        self.assertIn("could not be removed after the run", str(cm.exception))
        self.assertEqual(len(left), 1)
        self.assertTrue(left[0].exists())
        shutil.rmtree(left[0], ignore_errors=True)

        def silent_rmtree(path, *a, **kw):
            if Path(path).name.startswith("b3_removal_control_"):
                left.append(Path(path))
                return None                                         # says nothing, removes nothing
            return real(path, *a, **kw)
        with mock.patch.object(shutil, "rmtree", silent_rmtree):
            with self.assertRaises(tr.ReportIOError) as cm:
                tr.run_suites(self.t, runner=TheRuns.ok)
        self.assertIn("still exists after its removal", str(cm.exception))
        shutil.rmtree(left[-1], ignore_errors=True)

    @staticmethod
    def ok(argv, cwd, capture_output, text):
        return Completed(0, "", "Ran 1 test in 0.001s\n\nOK\n")

    def test_a_runner_failure_still_removes_the_shadow(self):
        shadows: list = []

        def runner(argv, cwd, capture_output, text):
            if Path(cwd) != self.t:
                shadows.append(Path(cwd))
                raise OSError("the interpreter vanished")
            return Completed(0, "", "Ran 1 test in 0.001s\n\nOK\n")
        with self.assertRaises(OSError):
            tr.run_suites(self.t, runner=runner)
        self.assertEqual(len(shadows), 1)
        self.assertFalse(shadows[0].exists())

    def test_the_real_discovery_command_on_the_tiny_tree(self):
        """The REAL python3 -B -m unittest discover, in the tree and in its shadow: the sentinel listed once
        and gone from the removal run, exactly one fewer; the verdict's only refusals are the tiny tree's
        missing provenance and artifacts, never the runs or the removal control."""
        with mock.patch.object(tr, "snapshot", lambda root: dict(clean_snapshot(), root=str(self.t))):
            run = tr.run_suites(self.t)
        rep = tr.build(run)
        self.assertEqual(rep["ran"], {"b2_tree": 1, "b3_tree": 4, "b3_removal": 3})
        self.assertEqual(rep["exit_status"], {"b2_tree": 0, "b3_tree": 0, "b3_removal": 0})
        self.assertEqual(rep["suites"]["b3_tree"]["listed"], [tr.SENTINEL_ID, "test_two.T.test_a", "test_two.T.test_b", "test_two.T.test_c"])
        self.assertEqual(rep["suites"]["b3_removal"]["listed"], ["test_two.T.test_a", "test_two.T.test_b", "test_two.T.test_c"])
        self.assertIn("A docstring (with parentheses) on its first line. ... ok", rep["suites"]["b3_tree"]["log_text"])   # the two-line form, for real
        self.assertEqual(rep["removal_control"], {"b3_ran": 4, "removal_ran": 3, "sentinel_in_b3_listing": 1, "sentinel_in_removal_listing": 0})
        self.assertEqual(rep["proof_refusals"], [])                       # with clean snapshots injected, the runs alone qualify
        self.assertTrue(rep["clean_tree_proof"])
        self.assertFalse(list(self.t.rglob("*.pyc"))[1:], "-B: no bytecode written by the runs")   # only the fixture's junk.pyc


class TheCommandLine(Tiny):
    def cli(self, *argv, runner=None) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = tr.main(list(argv), root=self.t, runner=runner or self.ok_runner)
        return rc, out.getvalue(), err.getvalue()

    @staticmethod
    def ok_runner(argv, cwd, capture_output, text):
        if "-v" in argv:
            ids = [tr.SENTINEL_ID, "test_two.T.test_a", "test_two.T.test_b", "test_two.T.test_c"]
            if not (Path(cwd) / "b3/tests" / tr.SENTINEL_FILE).exists():
                ids = ids[1:]
            return Completed(0, "", verbose_log(ids))
        return Completed(0, "", "Ran 1 test in 0.001s\n\nOK\n")

    def test_a_report_lands_and_is_a_diagnostic_never_a_proof_on_this_tree(self):
        out_dir = self.t / "out"
        rc, o, e = self.cli("--out-dir", str(out_dir))
        self.assertEqual((rc, e), (0, ""), e)
        written = sorted(out_dir.glob("test_report_*.json"))
        self.assertEqual(len(written), 1)
        self.assertEqual(sorted(os.listdir(out_dir)), [written[0].name])          # no .part left behind
        rep = json.loads(written[0].read_text())
        self.assertEqual(rep["ran"], {"b2_tree": 1, "b3_tree": 4, "b3_removal": 3})
        self.assertFalse(rep["clean_tree_proof"])
        self.assertEqual(rep["pins"]["mode"], "unbound_snapshot")
        self.assertTrue(any("('unbound_snapshot')" in x for x in rep["proof_refusals"]))
        self.assertTrue(any("no HEAD was observed" in x for x in rep["proof_refusals"]))
        self.assertFalse(any(x.startswith(("b2_tree:", "b3_tree:", "b3_removal")) for x in rep["proof_refusals"]), rep["proof_refusals"])
        self.assertIn("clean_tree_proof False", o)
        self.assertIn("report: ", o)
        for name in tr.SUITES:
            self.assertEqual(rep["suites"][name]["argv"], tr.suite_argv(name))
            self.assertIsInstance(rep["suites"][name]["log_text"], str)
        self.assertEqual(rep["run"]["shadow"]["removed"], tr.SENTINEL_FILE)
        self.assertTrue(rep["run"]["shadow"]["removed_after"])

    def test_a_failing_run_returns_its_status_with_the_report_written(self):
        def runner(argv, cwd, capture_output, text):
            if "-v" not in argv:
                return Completed(1, "", "Ran 1 test in 0.001s\n\nFAILED (failures=1)\n")
            return self.ok_runner(argv, cwd, capture_output, text)
        rc, o, e = self.cli("--out-dir", str(self.t / "out"), runner=runner)
        self.assertEqual(rc, 1)
        rep = json.loads(sorted((self.t / "out").glob("test_report_*.json"))[0].read_text())
        self.assertEqual(rep["exit_status"]["b2_tree"], 1)
        self.assertTrue(any(x.startswith("b2_tree: ") and "says FAILED" in x for x in rep["proof_refusals"]), rep["proof_refusals"])

    def test_the_report_is_never_overwritten(self):
        rep = tr.build(qualifying_run())
        out = self.t / "r.json"
        tr.publish_once(rep, out)
        before = out.read_bytes()
        self.assertEqual(json.loads(before)["schema"], tr.SCHEMA)
        with self.assertRaises(tr.ReportIOError) as cm:
            tr.publish_once(dict(rep, at="later"), out)
        self.assertIn("already exists", str(cm.exception))
        self.assertEqual(out.read_bytes(), before)
        self.assertEqual(sorted(os.listdir(self.t)), sorted(os.listdir(self.t)))       # no .part left behind
        self.assertFalse([n for n in os.listdir(self.t) if n.startswith(".r.json.part")])
        os.symlink(self.t / "elsewhere.json", self.t / "link.json")
        with self.assertRaises(tr.ReportIOError):
            tr.publish_once(rep, self.t / "link.json")
        self.assertFalse((self.t / "elsewhere.json").exists())
        with mock.patch.object(tr, "utc_now", return_value="2026-09-27T000000Z"):
            self.assertEqual(self.cli("--out-dir", str(self.t / "out"))[0], 0)
            rc, o, e = self.cli("--out-dir", str(self.t / "out"))
        self.assertEqual(rc, 3)
        self.assertIn("EXIT 3: the report", e)
        self.assertIn("already exists", e)

    def test_the_publishs_own_cleanup_and_sync_failures_are_exit_three(self):
        """The owner's P2 on 5b12dd2: the .part's unlink failure and the directory fsync failure were swallowed."""
        rep = tr.build(qualifying_run())
        out = self.t / "r.json"
        real_unlink = os.unlink

        def failing_unlink(path, *a, **kw):
            if ".part-" in str(path):
                raise OSError(1, "Operation not permitted", str(path))
            return real_unlink(path, *a, **kw)
        with mock.patch.object(os, "unlink", failing_unlink):
            with self.assertRaises(tr.ReportIOError) as cm:
                tr.publish_once(rep, out)
        self.assertIn("landed and its temporary file", str(cm.exception))
        self.assertIn("could not be removed", str(cm.exception))
        parts = [n for n in os.listdir(self.t) if ".part-" in n]
        self.assertTrue(out.exists() and parts, (out.exists(), parts))                 # both left behind — and named, never silent
        for n in parts:
            os.unlink(self.t / n)
        out.unlink()
        real_fsync = os.fsync

        def failing_fsync(fd):
            if os.fstat(fd).st_mode & 0o170000 == 0o040000:                              # the directory's descriptor
                raise OSError(5, "Input/output error")
            return real_fsync(fd)
        with mock.patch.object(os, "fsync", failing_fsync):
            with self.assertRaises(tr.ReportIOError) as cm:
                tr.publish_once(rep, out)
        self.assertIn("directory could not be synced", str(cm.exception))
        out.unlink()
        with mock.patch.object(os, "unlink", failing_unlink):
            rc, o, e = self.cli("--out-dir", str(self.t / "out"))
        self.assertEqual(rc, 3)
        self.assertIn("EXIT 3: the report", e)
        self.assertIn("temporary file", e)
        with mock.patch.object(os, "fsync", failing_fsync):
            rc, o, e = self.cli("--out-dir", str(self.t / "out2"))
        self.assertEqual(rc, 3)
        self.assertIn("EXIT 3: the report", e)
        self.assertIn("directory could not be synced", e)

    def test_io_failures_exit_three_and_defects_are_internal_errors(self):
        blocker = self.t / "not_a_dir"
        blocker.write_text("I am a regular file\n")
        rc, o, e = self.cli("--out-dir", str(blocker))
        self.assertEqual(rc, 3)
        self.assertIn("EXIT 3:", e)
        self.assertNotIn("Traceback", e)

        def broken(argv, cwd, capture_output, text):
            raise TypeError("a defect in the runner seam")
        rc, o, e = self.cli("--out-dir", str(self.t / "out"), runner=broken)
        self.assertEqual(rc, 3)
        self.assertIn("INTERNAL ERROR: TypeError: a defect in the runner seam", e)
        self.assertIn("Traceback", e)
        self.assertNotIn("EXIT 3:", e)
        self.assertFalse((self.t / "out").exists() and list((self.t / "out").iterdir()))

    def test_the_tool_offers_no_shortcut(self):
        text = (R / "b3/host/b3_test_report.py").read_text()
        for flag in ('"--no-run"', '"--focused"', '"--log"', '"--exit-status"', '"--skip"', '"--pattern"', '"--removal-control"', '"-p"'):
            self.assertNotIn(flag, text)                                          # no such option is DEFINED
        opts = {o for a in tr.parser()._actions for o in a.option_strings}
        self.assertEqual(opts, {"-h", "--help", "--out-dir"})
        for flag in ("--no-run", "--focused", "--log", "--pattern"):
            with mock.patch("sys.stderr", new=io.StringIO()):
                with self.assertRaises(SystemExit):
                    tr.main([flag, "x"], root=self.t, runner=self.ok_runner)
        self.assertEqual(tr.OUT_DIR_REL, "evidence/b3/tests")


if __name__ == "__main__":
    unittest.main()
