"""The one-process-per-frame signature search: its bookkeeping and its verdict.

Every case here is synthetic. The driver takes an injectable runner precisely so that a
child failure, a resumed run and a board that restarts mid-search can each be exercised
without a board — a check that only ever runs against hardware is a check nobody has seen
fail.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import board_signature_search as search  # noqa: E402

A20, A21, A22, A23 = 0x00400A20, 0x00400A21, 0x00400A22, 0x00400A23
FARS = [A20, A21, A22, A23, 0x00400A24]
DIGEST = "d" * 64
PLMARK = "18cc00f0fa537908"

ZERO = [0] * 101


def frame(seed: int) -> list[int]:
    words = list(ZERO)
    words[51] = seed
    words[50] = seed ^ 0x19C6
    return words


def capture_for(far: int, words: list[int]) -> dict:
    body = b"".join(word.to_bytes(4, "big") for word in words)
    return {
        "tool": "probe_jtag_config_read.py/2.0.0",
        "verdict": "READ",
        "idcode": "0x13722093",
        "config_status": "0x46107ffc",
        "frames": {f"{far:#010x}": {
            "frame": [f"{word:08x}" for word in words],
            "pad_frame": [f"{word:08x}" for word in ZERO],
            "frame_sha256": hashlib.sha256(body).hexdigest(),
            "nonzero_words_in_frame": sum(1 for word in words if word),
        }},
    }


def runner_for(content: dict[int, list[int]], fail_on: int | None = None):
    """A child that writes what the fabric is pretending to hold, or fails."""
    def runner(far: int, out_path: Path) -> int:
        if far == fail_on:
            return 1
        out_path.write_text(json.dumps(capture_for(far, content.get(far, ZERO))),
                            encoding="utf-8")
        return 0
    return runner


class TheChildContract(unittest.TestCase):
    def test_a_child_is_given_exactly_one_far(self) -> None:
        argv = search.child_argv(A20, Path("/tmp/x.json"), None, None)
        self.assertEqual(argv.count("--far"), 1)
        self.assertIn(f"{A20:#010x}", argv)

    def test_two_fars_in_one_child_are_refused(self) -> None:
        argv = search.child_argv(A20, Path("/tmp/x.json"), None, None) + ["--far", "0x00400a21"]
        with self.assertRaises(search.SearchStop):
            search.check_child_argv(argv)

    def test_the_child_is_the_reviewed_probe(self) -> None:
        """No JTAG path of its own. Judged on code, not on prose that names the forbidden."""
        self.assertEqual(search.CHILD, REPO / "scripts/probe_jtag_config_read.py")
        tree = ast.parse(Path(search.__file__).read_text("utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                node.body = [child for child in node.body
                             if not (isinstance(child, ast.Expr)
                                     and isinstance(child.value, ast.Constant)
                                     and isinstance(child.value.value, str))]
        code = ast.unparse(tree)
        for forbidden in ("irscan", "drscan", "JPROGRAM", "JSTART", "0x0b", "0x0c"):
            self.assertNotIn(forbidden, code,
                             "this module must not build a JTAG path of its own")


class TheBookkeeping(unittest.TestCase):
    def search_in(self, tmp: Path, content: dict, **kwargs):
        return search.run_search(FARS, tmp, PLMARK, DIGEST,
                                 runner=runner_for(content, kwargs.pop("fail_on", None)),
                                 plmark_reader=kwargs.pop("plmark_reader",
                                                          lambda port: PLMARK),
                                 **kwargs)

    def test_every_far_is_captured_once_and_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            index = self.search_in(tmp, {A20: frame(0x40)})
            self.assertEqual(sorted(index["entries"]), sorted(f"{far:#010x}" for far in FARS))
            self.assertTrue(all(entry["status"] == "ok"
                                for entry in index["entries"].values()))
            self.assertEqual(index["not_attempted"], [])
            self.assertEqual(json.loads((tmp / "index.json").read_text())["entries"].keys(),
                             index["entries"].keys())

    def test_a_failed_child_stops_the_run_and_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            with self.assertRaises(search.SearchStop):
                self.search_in(tmp, {}, fail_on=A22)
            index = json.loads((tmp / "index.json").read_text("utf-8"))
            self.assertEqual(index["entries"][f"{A22:#010x}"]["status"], "failed")
            self.assertNotIn(f"{A23:#010x}", index["entries"],
                             "the run must stop, not carry on past a failure")

    def test_a_budget_leaves_the_rest_not_attempted_never_searched(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            index = self.search_in(tmp, {}, max_reads=2)
            self.assertEqual(len(index["entries"]), 2)
            self.assertEqual(index["not_attempted"],
                             [f"{far:#010x}" for far in FARS[2:]])

    def test_a_resumed_run_keeps_the_verified_captures(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            self.search_in(tmp, {}, max_reads=2)
            seen: list[int] = []

            def counting(far: int, out_path: Path) -> int:
                seen.append(far)
                return runner_for({})(far, out_path)

            index = search.run_search(FARS, tmp, PLMARK, DIGEST, runner=counting,
                                      plmark_reader=lambda port: PLMARK)
            self.assertEqual(seen, FARS[2:], "already-verified FARs must not be re-read")
            self.assertEqual(len(index["entries"]), len(FARS))

    def test_a_resume_against_different_inputs_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            self.search_in(tmp, {}, max_reads=1)
            with self.assertRaises(search.SearchStop):
                search.run_search(FARS, tmp, PLMARK, "0" * 64, runner=runner_for({}),
                                  plmark_reader=lambda port: PLMARK)

    def test_a_restart_during_the_search_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            with self.assertRaises(search.SearchStop):
                self.search_in(tmp, {}, plmark_reader=lambda port: "ffffffffffffffff")

    def test_a_capture_for_the_wrong_far_is_refused(self) -> None:
        def liar(far: int, out_path: Path) -> int:
            out_path.write_text(json.dumps(capture_for(A21, ZERO)), encoding="utf-8")
            return 0

        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            with self.assertRaises(search.SearchStop):
                search.run_search([A20], tmp, PLMARK, DIGEST, runner=liar,
                                  plmark_reader=lambda port: PLMARK)


class TheVerdict(unittest.TestCase):
    def setUp(self) -> None:
        self.signatures = {A20: frame(0x40), A21: frame(0x41),
                           A22: frame(0x42), A23: frame(0x43)}
        self.base = {far: list(ZERO) for far in FARS}
        self.base[A20] = list(ZERO)

    def decide(self, captures, index=None):
        return search.judge(index or {"not_attempted": []}, captures, self.base,
                            self.signatures)

    def test_the_candidate_at_the_intended_far_ends_it(self) -> None:
        verdict = self.decide({A20: self.signatures[A20]})
        self.assertEqual(verdict["verdict"], "WRITE_LANDED_AT_THE_INTENDED_FAR")

    def test_a_shifted_candidate_is_located(self) -> None:
        captures = {A20: list(ZERO), A21: self.signatures[A20], A22: list(ZERO)}
        verdict = self.decide(captures)
        self.assertEqual(verdict["verdict"], "WRITE_LANDED_ELSEWHERE")
        self.assertEqual(verdict["signature_hits"][f"{A20:#010x}"], [f"{A21:#010x}"])

    def test_all_base_with_complete_coverage_says_nowhere(self) -> None:
        verdict = self.decide({far: list(ZERO) for far in FARS})
        self.assertEqual(verdict["verdict"], "NOT_FOUND_COMPLETE")

    def test_all_base_with_holes_refuses_to_say_nowhere(self) -> None:
        verdict = self.decide({A20: list(ZERO)},
                              index={"not_attempted": [f"{A21:#010x}"]})
        self.assertEqual(verdict["verdict"], "NOT_FOUND_INCOMPLETE")
        self.assertIn("not there", verdict["reading"])

    def test_a_duplicated_signature_names_nothing(self) -> None:
        captures = {A20: list(ZERO), A21: self.signatures[A20], A22: self.signatures[A20]}
        verdict = self.decide(captures)
        self.assertEqual(verdict["verdict"], "SIGNATURE_AMBIGUOUS")

    def test_an_intended_frame_that_is_neither_stops(self) -> None:
        verdict = self.decide({A20: frame(0xDEAD)})
        self.assertEqual(verdict["verdict"], "INTENDED_FAR_IS_NEITHER")

    def test_a_missing_intended_far_decides_nothing(self) -> None:
        self.assertEqual(self.decide({A21: list(ZERO)})["verdict"], "INCOMPLETE")

    def test_a_match_is_the_whole_frame_not_a_few_bits(self) -> None:
        nearly = list(self.signatures[A20])
        nearly[50] ^= 1
        verdict = self.decide({A20: list(ZERO), A21: nearly})
        self.assertEqual(verdict["verdict"], "NOT_FOUND_COMPLETE")

    def test_an_all_zero_signature_is_refused_at_the_source(self) -> None:
        """The zero floor may never be a search key; the refusal lives in the derivation."""
        source = Path(search.__file__).read_text("utf-8")
        self.assertIn("is all zero and cannot be searched for", source)


if __name__ == "__main__":
    unittest.main()
