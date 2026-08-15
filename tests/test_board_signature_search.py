"""The one-process-per-frame signature search: its authority, its order, its bookkeeping.

Every case is synthetic. `run()` takes the signatures, the base and the runner as arguments
precisely so that a child failure, a tampered capture, a resumed run and a board that
restarts mid-search can each be exercised without a board — a check that only ever runs
against hardware is a check nobody has seen fail.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import board_signature_search as search  # noqa: E402

A20, A21, A22, A23 = 0x00400A20, 0x00400A21, 0x00400A22, 0x00400A23
A24 = 0x00400A24
CONTROL_FARS = [0x00400B00 + offset for offset in range(search.POSITIVE_CONTROL_COUNT)]
FARS = [A20, A21, A22, A23, A24, *CONTROL_FARS]
DIGEST = "d" * 64
CONTROL_DIGEST = "c" * 64
PLMARK = "18cc00f0fa537908"
ZERO = [0] * 101


def frame(seed: int) -> list[int]:
    words = list(ZERO)
    words[51] = seed
    words[50] = seed ^ 0x19C6
    return words


SIGNATURES = {A20: frame(0x40), A21: frame(0x41), A22: frame(0x42), A23: frame(0x43)}
BASE = {far: list(ZERO) for far in FARS}
CONTROLS = {far: frame(0x100 + offset) for offset, far in enumerate(CONTROL_FARS)}
BASE.update(CONTROLS)


def capture_for(far: int, words: list[int], tool: str = search.CHILD_TOOL_VERSION,
                config_status: str = "0x46107ffc") -> dict:
    body = b"".join(word.to_bytes(4, "big") for word in words)
    return {
        "tool": tool,
        "verdict": "READ",
        "idcode": search.IDCODE,
        "config_status": config_status,
        "frames": {f"{far:#010x}": {
            "frame": [f"{word:08x}" for word in words],
            "pad_frame": [f"{word:08x}" for word in ZERO],
            "frame_sha256": hashlib.sha256(body).hexdigest(),
        }},
    }


def runner_for(content: dict[int, list[int]], fail_on: int | None = None,
               asked: list[int] | None = None, tool: str | None = None,
               raise_on: int | None = None, garbage_on: int | None = None,
               config_status: str = "0x46107ffc"):
    """A child that writes what the fabric is pretending to hold, or fails like a real one."""
    def runner(far: int, out_path: Path) -> dict:
        if asked is not None:
            asked.append(far)
        argv = search.child_argv(far, out_path)
        if far == raise_on:
            raise subprocess.TimeoutExpired(argv, 600)
        if far == fail_on:
            return {"returncode": 1, "argv": argv, "stdout": "", "stderr": "openocd exploded"}
        if far == garbage_on:
            out_path.write_text("{not json", encoding="utf-8")
            return {"returncode": 0, "argv": argv, "stdout": "", "stderr": ""}
        out_path.write_text(json.dumps(capture_for(
            far, content.get(far, ZERO), tool or search.CHILD_TOOL_VERSION, config_status)),
                            encoding="utf-8")
        return {"returncode": 0, "argv": argv, "stdout": "", "stderr": ""}
    return runner


def go(tmp: Path, content: dict, **kwargs):
    wire_content = dict(content)
    if kwargs.pop("control_ok", True):
        wire_content.setdefault(CONTROL_FARS[0], CONTROLS[CONTROL_FARS[0]])
    return search.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST, CONTROLS,
                      runner=runner_for(wire_content, kwargs.pop("fail_on", None),
                                        kwargs.pop("asked", None), kwargs.pop("tool", None),
                                        kwargs.pop("raise_on", None),
                                        kwargs.pop("garbage_on", None),
                                        kwargs.pop("config_status", "0x46107ffc")),
                      plmark_reader=kwargs.pop("plmark_reader", lambda port: PLMARK),
                      **kwargs)


def go_control(tmp: Path, content: dict, **kwargs):
    return search.run_control_only(
        tmp, PLMARK, BASE, CONTROL_DIGEST, CONTROLS,
        runner=runner_for(content, kwargs.pop("fail_on", None),
                          kwargs.pop("asked", None), kwargs.pop("tool", None),
                          kwargs.pop("raise_on", None), kwargs.pop("garbage_on", None),
                          kwargs.pop("config_status", "0x46107ffc")),
        plmark_reader=kwargs.pop("plmark_reader", lambda port: PLMARK), **kwargs)


class TheAuthority(unittest.TestCase):
    def test_the_cli_cannot_be_pointed_at_another_run_or_report(self) -> None:
        source = Path(search.__file__).read_text("utf-8")
        for escape in ('"--run-dir"', '"--report"', '"--artifact"', '"--repo"'):
            self.assertNotIn(escape, source, "the authority must not be an argument")

    def test_the_canonical_paths_are_the_gate_s_own(self) -> None:
        import gate_claimb_known_answer as kagate
        self.assertEqual(search.CANONICAL_RUN, REPO / kagate.RUN_REL)
        self.assertEqual(search.CANONICAL_REPORT, REPO / kagate.REPORT_REL)

    def test_the_selection_is_checked_against_the_named_site_and_bel(self) -> None:
        self.assertEqual((search.EXPECTED_SITE, search.EXPECTED_BEL),
                         ("SLICE_X2Y25", "A6LUT"))
        source = Path(search.__file__).read_text("utf-8")
        self.assertIn("report entry", source)
        self.assertIn("EXPECTED_SITE", source)

    def test_the_instrument_is_part_of_the_digest(self) -> None:
        fars = [A20, A21]
        digest = search.instrument_digest(fars)
        self.assertEqual(len(digest), 64)
        self.assertNotEqual(digest, search.instrument_digest([A20]))
        source = ast.unparse(ast.parse(Path(search.__file__).read_text("utf-8")))
        for pinned in ("CHILD_TOOL_VERSION", "CHILD_CFG", "CHILD_SPEED", "TOOL_VERSION"):
            self.assertIn(pinned, source)

    def test_the_child_is_the_reviewed_probe_and_no_jtag_path_of_its_own(self) -> None:
        self.assertEqual(search.CHILD, REPO / "scripts/probe_jtag_config_read.py")
        self.assertEqual(search.CHILD_TOOL_VERSION, search.probe.TOOL_VERSION)
        tree = ast.parse(Path(search.__file__).read_text("utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                node.body = [child for child in node.body
                             if not (isinstance(child, ast.Expr)
                                     and isinstance(child.value, ast.Constant)
                                     and isinstance(child.value.value, str))]
        code = ast.unparse(tree)
        for forbidden in ("irscan", "drscan", "JPROGRAM", "JSTART", "0x0b", "0x0c"):
            self.assertNotIn(forbidden, code)

    def test_r4_rejects_every_older_probe_capture(self) -> None:
        for old in ("probe_jtag_config_read.py/2.0.0",
                    "probe_jtag_config_read.py/2.1.0",
                    "probe_jtag_config_read.py/2.2.0",
                    "probe_jtag_config_read.py/2.3.0"):
            with self.subTest(tool=old), self.assertRaises(search.SearchStop):
                search.frame_of(A20, capture_for(A20, ZERO, tool=old))

    def test_r4_control_and_r4_have_one_instrument(self) -> None:
        first_tcl, _ = search.probe.build_tcl([CONTROL_FARS[0]])
        second_tcl, _ = search.probe.build_tcl([CONTROL_FARS[0]])
        self.assertEqual(first_tcl.encode(), second_tcl.encode())
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            go_control(Path(first), CONTROLS)
            go_control(Path(second), CONTROLS)
            first_index = json.loads((Path(first) / "index.json").read_text("utf-8"))
            second_index = json.loads((Path(second) / "index.json").read_text("utf-8"))
        self.assertEqual(first_index["instrument_digest"], second_index["instrument_digest"])
        self.assertEqual(search.TOOL_VERSION, "board_signature_search.py/2.7.1")

    def test_a_child_is_given_exactly_one_far(self) -> None:
        argv = search.child_argv(A20, Path("/tmp/x.json"))
        self.assertEqual(argv.count("--far"), 1)
        with self.assertRaises(search.SearchStop):
            search.check_child_argv(argv + ["--far", "0x00400a21"])

    def test_the_positive_controls_are_authority_derived_and_pinned(self) -> None:
        base = search.base_frames()
        controls = search.canonical_positive_controls(base)
        self.assertEqual(tuple(controls), search.EXPECTED_POSITIVE_CONTROL_FARS)
        self.assertEqual(len(controls), search.POSITIVE_CONTROL_COUNT)
        self.assertTrue(all(any(words) for words in controls.values()))
        self.assertNotIn(search.INTENDED_FAR, controls)


class TheOrder(unittest.TestCase):
    def test_the_intended_far_is_the_first_child(self) -> None:
        asked: list[int] = []
        with tempfile.TemporaryDirectory() as name:
            go(Path(name), {}, asked=asked)
        self.assertEqual(asked[0], A20)

    def test_the_candidate_at_the_intended_far_reads_nothing_else(self) -> None:
        asked: list[int] = []
        with tempfile.TemporaryDirectory() as name:
            verdict = go(Path(name), {A20: SIGNATURES[A20]}, asked=asked)
        self.assertEqual(verdict["verdict"], "WRITE_LANDED_AT_THE_INTENDED_FAR")
        self.assertEqual(asked, [A20], "no sweep may run once the first frame has answered")

    def test_a_third_state_first_earns_one_control_then_reads_nothing_else(self) -> None:
        asked: list[int] = []
        with tempfile.TemporaryDirectory() as name:
            verdict = go(Path(name), {A20: frame(0xDEAD)}, asked=asked)
        self.assertEqual(verdict["verdict"], "INTENDED_FAR_IS_NEITHER")
        self.assertEqual(asked, [A20, CONTROL_FARS[0]],
                         "the third-state verdict must first earn a positive control")

    def test_only_the_base_starts_a_sweep(self) -> None:
        asked: list[int] = []
        with tempfile.TemporaryDirectory() as name:
            verdict = go(Path(name), {}, asked=asked)
        self.assertEqual(verdict["verdict"], "NOT_FOUND_COMPLETE")
        self.assertEqual(asked[0:2], [A20, CONTROL_FARS[0]])
        self.assertEqual(set(asked), set(FARS))


class ThePositiveControl(unittest.TestCase):
    def test_all_controls_mismatching_stops_before_the_sweep(self) -> None:
        asked: list[int] = []
        with tempfile.TemporaryDirectory() as name:
            verdict = go(Path(name), {}, asked=asked, control_ok=False)
        self.assertEqual(verdict["verdict"], "INSTRUMENT_INVALID")
        self.assertEqual(asked, [A20, *CONTROL_FARS])
        self.assertNotIn(A21, asked, "an invalid instrument must not start the sweep")

    def test_nonzero_but_wrong_controls_do_not_count(self) -> None:
        wrong = {far: frame(0xD000 + offset)
                 for offset, far in enumerate(CONTROL_FARS)}
        with tempfile.TemporaryDirectory() as name:
            verdict = go(Path(name), wrong, control_ok=False)
        self.assertEqual(verdict["verdict"], "INSTRUMENT_INVALID")
        self.assertTrue(all(item["observed_nonzero_words"] > 0
                            for item in verdict["positive_controls"]))
        self.assertFalse(verdict["positive_control_matches"])

    def test_an_unread_control_set_is_unvalidated_not_invalid(self) -> None:
        asked: list[int] = []
        with tempfile.TemporaryDirectory() as name:
            verdict = go(Path(name), {}, asked=asked, control_ok=False, max_reads=2)
        self.assertEqual(verdict["verdict"], "INSTRUMENT_UNVALIDATED")
        self.assertEqual(asked, [A20, *CONTROL_FARS[:2]])
        self.assertEqual(len(verdict["positive_controls_not_read"]), 14)

    def test_neither_cannot_bypass_a_failed_control(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            verdict = go(Path(name), {A20: frame(0xDEAD)}, control_ok=False)
        self.assertEqual(verdict["verdict"], "INSTRUMENT_INVALID")

    def test_judge_sweep_itself_cannot_emit_not_found_without_a_control(self) -> None:
        captures = {far: list(ZERO) for far in FARS}
        verdict = search.judge_sweep({}, captures, [], SIGNATURES, CONTROLS)
        self.assertEqual(verdict["verdict"], "INSTRUMENT_INVALID")


class TheControlOnlyMode(unittest.TestCase):
    LOCATION_VERDICTS = {
        "WRITE_LANDED_AT_THE_INTENDED_FAR", "WRITE_LANDED_ELSEWHERE",
        "INTENDED_FAR_IS_NEITHER", "NOT_FOUND_COMPLETE", "NOT_FOUND_INCOMPLETE",
        "SIGNATURE_AMBIGUOUS",
    }

    def test_it_reads_exactly_all_sixteen_controls_even_after_one_matches(self) -> None:
        asked: list[int] = []
        content = {CONTROL_FARS[0]: CONTROLS[CONTROL_FARS[0]]}
        with tempfile.TemporaryDirectory() as name:
            verdict = go_control(Path(name), content, asked=asked)
        self.assertEqual(verdict["verdict"], "INSTRUMENT_VALID")
        self.assertEqual(asked, CONTROL_FARS)
        self.assertNotIn(A20, asked)
        self.assertIn("in this acquisition", verdict["reading"])
        self.assertNotIn("post-fault", verdict["reading"])

    def test_wrong_but_nonzero_controls_are_invalid_and_have_no_location_fields(self) -> None:
        content = {far: frame(0xD000 + offset)
                   for offset, far in enumerate(CONTROL_FARS)}
        with tempfile.TemporaryDirectory() as name:
            verdict = go_control(Path(name), content)
        self.assertEqual(verdict["verdict"], "INSTRUMENT_INVALID")
        self.assertFalse(set(verdict) & {
            "signature_hits", "intended_far", "signature_fars",
            "frames_searched", "frames_not_searched",
        })
        self.assertNotIn(verdict["verdict"], self.LOCATION_VERDICTS)

    def test_an_incomplete_control_acquisition_is_unvalidated(self) -> None:
        wrong = {far: frame(0xD000 + offset)
                 for offset, far in enumerate(CONTROL_FARS)}
        captures = {far: wrong[far] for far in CONTROL_FARS[:5]}
        verdict = search.judge_positive_controls(captures, CONTROLS)
        self.assertEqual(verdict["verdict"], "INSTRUMENT_UNVALIDATED")
        self.assertEqual(len(verdict["positive_controls_not_read"]), 11)

    def test_no_controls_read_is_unvalidated_not_valid_empty(self) -> None:
        verdict = search.judge_positive_controls({}, CONTROLS)
        self.assertEqual(verdict["verdict"], "INSTRUMENT_UNVALIDATED")
        self.assertEqual(len(verdict["positive_controls_not_read"]), 16)

    def test_the_production_cli_cannot_cap_control_reads(self) -> None:
        with self.assertRaises(search.SearchStop) as stopped:
            search.validate_mode_options(control_only=True, max_reads=15)
        self.assertIn("exactly the sixteen", str(stopped.exception))
        search.validate_mode_options(control_only=True, max_reads=None)
        search.validate_mode_options(control_only=False, max_reads=15)

    def test_config_status_is_summarised_for_every_capture(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go_control(tmp, {}, config_status="0x46106FFD")
            index = json.loads((tmp / "index.json").read_text("utf-8"))
        self.assertEqual(index["mode"], search.MODE_CONTROL_ONLY)
        self.assertEqual(len(index["entries"]), 16)
        self.assertEqual({entry["config_status"] for entry in index["entries"].values()},
                         {"0x46106ffd"})

    def test_index_status_must_still_equal_the_capture(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go_control(tmp, {})
            index = json.loads((tmp / "index.json").read_text("utf-8"))
            index["entries"][f"{CONTROL_FARS[0]:#010x}"]["config_status"] = "0xdeadbeef"
            with self.assertRaises(search.SearchStop) as stopped:
                search.validate_index(
                    tmp, index, CONTROL_DIGEST, PLMARK, CONTROL_FARS, CONTROLS,
                    search.MODE_CONTROL_ONLY)
        self.assertIn("CONFIG_STATUS", str(stopped.exception))

    def test_control_index_cannot_resume_as_a_signature_search(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go_control(tmp, {})
            with self.assertRaises(search.SearchStop) as stopped:
                search.run(tmp, PLMARK, SIGNATURES, BASE, FARS, CONTROL_DIGEST, CONTROLS,
                           runner=runner_for({}), plmark_reader=lambda port: PLMARK)
        self.assertIn("index mode", str(stopped.exception))

    def test_search_index_cannot_resume_as_control_only(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go(tmp, {A20: SIGNATURES[A20]})
            with self.assertRaises(search.SearchStop) as stopped:
                search.run_control_only(
                    tmp, PLMARK, BASE, DIGEST, CONTROLS, runner=runner_for({}),
                    plmark_reader=lambda port: PLMARK)
        self.assertIn("index mode", str(stopped.exception))

    def test_control_index_cannot_be_judged_as_a_signature_search(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go_control(tmp, {})
            with self.assertRaises(search.SearchStop):
                search.judge_signature_search_index(
                    tmp, PLMARK, CONTROL_DIGEST, SIGNATURES, BASE, FARS, CONTROLS)

    def test_search_index_cannot_be_judged_as_control_only(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go(tmp, {A20: SIGNATURES[A20]})
            with self.assertRaises(search.SearchStop):
                search.judge_control_only_index(tmp, PLMARK, DIGEST, CONTROLS)

    def test_mode_is_part_of_the_instrument_digest(self) -> None:
        self.assertNotEqual(
            search.instrument_digest(CONTROL_FARS, search.MODE_CONTROL_ONLY),
            search.instrument_digest(CONTROL_FARS, search.MODE_SIGNATURE_SEARCH))


class TheBookkeeping(unittest.TestCase):
    def test_a_failed_child_stops_the_search_and_keeps_its_output(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            asked: list[int] = []
            with self.assertRaises(search.SearchStop):
                go(tmp, {}, fail_on=A22, asked=asked)
            index = json.loads((tmp / "index.json").read_text("utf-8"))
            entry = index["entries"][f"{A22:#010x}"]
            self.assertEqual(entry["status"], "failed")
            log = json.loads((tmp / entry["child_log"]).read_text("utf-8"))
            self.assertEqual(log["stderr"], "openocd exploded")
            self.assertEqual(search._digest_of(tmp / entry["child_log"]),
                             entry["child_log_sha256"])
            self.assertEqual(asked, [A20, CONTROL_FARS[0], A21, A22],
                             "the search must stop where it failed")

    def test_a_budget_leaves_the_rest_not_attempted_never_searched(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            verdict = go(tmp, {}, max_reads=2)
            self.assertEqual(verdict["verdict"], "NOT_FOUND_INCOMPLETE")
            self.assertEqual(verdict["frames_not_searched"], [
                f"{far:#010x}" for far in FARS
                if far not in (A20, A21, CONTROL_FARS[0])])

    def test_a_resume_re_reads_and_re_hashes_every_capture(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go(tmp, {}, max_reads=1)
            asked: list[int] = []
            go(tmp, {}, asked=asked)
            self.assertEqual(asked, [far for far in FARS
                                     if far not in (A20, CONTROL_FARS[0])],
                             "verified captures must not be re-read")

    def test_a_resume_refuses_a_tampered_capture(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go(tmp, {}, max_reads=1)
            victim = tmp / f"far_{CONTROL_FARS[0]:08x}.json"
            victim.write_text(json.dumps(capture_for(CONTROL_FARS[0], frame(0x99))),
                              encoding="utf-8")
            with self.assertRaises(search.SearchStop) as stopped:
                go(tmp, {})
            self.assertIn("changed since it was written", str(stopped.exception))

    def test_a_resume_refuses_a_truncated_capture(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go(tmp, {}, max_reads=1)
            (tmp / f"far_{CONTROL_FARS[0]:08x}.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(search.SearchStop):
                go(tmp, {})

    def test_a_resume_refuses_a_drifted_instrument(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go(tmp, {}, max_reads=1)
            with self.assertRaises(search.SearchStop):
                search.run(tmp, PLMARK, SIGNATURES, BASE, FARS, "0" * 64,
                           CONTROLS, runner=runner_for({}),
                           plmark_reader=lambda port: PLMARK)

    def test_a_resume_refuses_a_different_boot(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go(tmp, {}, max_reads=1)
            with self.assertRaises(search.SearchStop):
                search.run(tmp, "ffffffffffffffff", SIGNATURES, BASE, FARS, DIGEST,
                           CONTROLS, runner=runner_for({}),
                           plmark_reader=lambda port: "ffffffffffffffff")

    def test_a_restart_during_the_search_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaises(search.SearchStop):
                go(Path(name), {}, plmark_reader=lambda port: "ffffffffffffffff")

    def test_a_capture_for_the_wrong_far_is_refused(self) -> None:
        def liar(far: int, out_path: Path) -> dict:
            out_path.write_text(json.dumps(capture_for(A21, ZERO)), encoding="utf-8")
            return {"returncode": 0, "argv": [], "stdout": "", "stderr": ""}

        with tempfile.TemporaryDirectory() as name:
            with self.assertRaises(search.SearchStop):
                search.run(Path(name), PLMARK, SIGNATURES, BASE, FARS, DIGEST,
                           CONTROLS, runner=liar, plmark_reader=lambda port: PLMARK)

    def test_a_capture_from_another_tool_version_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaises(search.SearchStop):
                go(Path(name), {}, tool="probe_jtag_config_read.py/1.0.0")

    def test_validate_index_refuses_an_index_holding_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            with self.assertRaises(search.SearchStop):
                go(tmp, {}, fail_on=A21)
            index = json.loads((tmp / "index.json").read_text("utf-8"))
            with self.assertRaises(search.SearchStop) as stopped:
                search.validate_index(tmp, index, DIGEST, PLMARK, FARS, CONTROLS)
            self.assertIn("not coverage", str(stopped.exception))


class TheCoverageIsRecomputed(unittest.TestCase):
    """An interrupted run leaves a self-consistent index that is silent about the rest."""

    def interrupted(self, tmp: Path) -> dict:
        """A20 captured and atomically landed, then the process died before closing."""
        try:
            go(tmp, {}, max_reads=0, plmark_reader=lambda port: (_ for _ in ()).throw(
                RuntimeError("killed before the closing write")))
        except RuntimeError:
            pass
        index = json.loads((tmp / "index.json").read_text("utf-8"))
        index.pop("not_attempted", None)
        index.pop("plmark_at_end", None)
        (tmp / "index.json").write_text(json.dumps(index), encoding="utf-8")
        return index

    def test_missing_frames_are_recomputed_not_read_from_the_index(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            index = self.interrupted(tmp)
            self.assertEqual(list(index["entries"]), [f"{A20:#010x}"])
            self.assertNotIn("not_attempted", index)
            captures, missing = search.validate_index(
                tmp, index, DIGEST, PLMARK, FARS, CONTROLS)
            self.assertEqual(list(captures), [A20])
            self.assertEqual(missing, [f"{far:#010x}" for far in FARS[1:]],
                             "the frames nobody read must be recomputed from the frozen set")

    def test_a_lying_index_cannot_make_one_frame_a_complete_search(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            index = self.interrupted(tmp)
            index["not_attempted"] = []          # the claim an interrupted run leaves behind
            _, missing = search.validate_index(tmp, index, DIGEST, PLMARK, FARS, CONTROLS)
            verdict = search.judge_sweep(
                index, {A20: list(ZERO)}, missing, SIGNATURES, CONTROLS)
            self.assertEqual(verdict["verdict"], "INSTRUMENT_UNVALIDATED")

    def test_an_entry_outside_the_frozen_sequence_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            index = self.interrupted(tmp)
            with self.assertRaises(search.SearchStop) as stopped:
                search.validate_index(tmp, index, DIGEST, PLMARK, [A21, A22], CONTROLS)
            self.assertIn("frozen device frame sequence", str(stopped.exception))


class TheJudgeOnlyPath(unittest.TestCase):
    def test_an_index_its_run_never_closed_may_not_be_judged(self) -> None:
        with self.assertRaises(search.SearchStop) as stopped:
            search.require_closed({"plmark_at_start": PLMARK})
        self.assertIn("resume it, do not judge it", str(stopped.exception))

    def test_a_closed_index_may_be_judged(self) -> None:
        search.require_closed({"plmark_at_start": PLMARK, "plmark_at_end": PLMARK})

    def test_an_index_closed_by_a_different_boot_may_not_be_judged(self) -> None:
        with self.assertRaises(search.SearchStop):
            search.require_closed({"plmark_at_start": PLMARK, "plmark_at_end": "ffff"})

    def test_a_resume_cannot_reuse_the_previous_invocation_s_closure(self) -> None:
        """New captures may not inherit a matching end marker from an older partial run."""
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go(tmp, {}, max_reads=0)  # A20 only, and this invocation closes normally.
            before = json.loads((tmp / "index.json").read_text("utf-8"))
            self.assertEqual(before["plmark_at_end"], PLMARK)

            with self.assertRaises(search.SearchStop):
                go(tmp, {}, plmark_reader=lambda port: "rebooted")

            after = json.loads((tmp / "index.json").read_text("utf-8"))
            self.assertEqual(len(after["entries"]), len(FARS),
                             "the resume must reach the closing check for this regression")
            self.assertEqual(after["plmark_at_end"], "rebooted",
                             "the mismatching observation must be evidence on disk")
            with self.assertRaises(search.SearchStop):
                search.require_closed(after)

    def test_a_resume_is_unclosed_even_if_the_end_marker_read_raises(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            go(tmp, {}, max_reads=0)

            with self.assertRaises(RuntimeError):
                go(tmp, {}, plmark_reader=lambda port: (_ for _ in ()).throw(
                    RuntimeError("the UART disappeared")))

            after = json.loads((tmp / "index.json").read_text("utf-8"))
            self.assertNotIn("plmark_at_end", after)
            with self.assertRaises(search.SearchStop):
                search.require_closed(after)


class TheChildLogIsEvidence(unittest.TestCase):
    def one_capture(self, tmp: Path) -> dict:
        go(tmp, {A20: SIGNATURES[A20]})
        return json.loads((tmp / "index.json").read_text("utf-8"))

    def test_a_deleted_child_log_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            index = self.one_capture(tmp)
            (tmp / index["entries"][f"{A20:#010x}"]["child_log"]).unlink()
            with self.assertRaises(search.SearchStop) as stopped:
                search.validate_index(tmp, index, DIGEST, PLMARK, FARS, CONTROLS)
            self.assertIn("child log is gone", str(stopped.exception))

    def test_an_edited_child_log_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            index = self.one_capture(tmp)
            path = tmp / index["entries"][f"{A20:#010x}"]["child_log"]
            log = json.loads(path.read_text("utf-8"))
            log["stdout"] = "tampered"
            path.write_text(json.dumps(log), encoding="utf-8")
            with self.assertRaises(search.SearchStop):
                search.validate_index(tmp, index, DIGEST, PLMARK, FARS, CONTROLS)

    def test_a_child_log_from_another_invocation_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            index = self.one_capture(tmp)
            entry = index["entries"][f"{A20:#010x}"]
            path = tmp / entry["child_log"]
            log = json.loads(path.read_text("utf-8"))
            log["argv"] = log["argv"][:-2]
            path.write_text(json.dumps(log), encoding="utf-8")
            entry["child_log_sha256"] = search._digest_of(path)
            with self.assertRaises(search.SearchStop) as stopped:
                search.validate_index(tmp, index, DIGEST, PLMARK, FARS, CONTROLS)
            self.assertIn("different invocation", str(stopped.exception))

    def test_a_path_that_escapes_the_run_directory_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            index = self.one_capture(tmp)
            index["entries"][f"{A20:#010x}"]["capture"] = "../escape.json"
            with self.assertRaises(search.SearchStop) as stopped:
                search.validate_index(tmp, index, DIGEST, PLMARK, FARS, CONTROLS)
            self.assertIn("run directory", str(stopped.exception))


class TheFailureAlwaysLeavesEvidence(unittest.TestCase):
    def test_a_child_that_raises_still_lands_a_failed_entry_and_a_log(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            with self.assertRaises(search.SearchStop) as stopped:
                go(tmp, {}, raise_on=A20)
            self.assertIn("TimeoutExpired", str(stopped.exception))
            index = json.loads((tmp / "index.json").read_text("utf-8"))
            entry = index["entries"][f"{A20:#010x}"]
            self.assertEqual(entry["status"], "failed")
            log = json.loads((tmp / entry["child_log"]).read_text("utf-8"))
            self.assertIn("TimeoutExpired", log["exception"])
            self.assertEqual(log["argv"],
                             search.child_argv(A20, tmp / f"far_{A20:08x}.json.part"))

    def test_a_timeout_preserves_its_partial_streams_byte_for_byte(self) -> None:
        stdout, stderr = b"partial-stdout\x00\xff", b"partial-stderr\r\n"

        def timeout(far: int, out_path: Path) -> dict:
            raise subprocess.TimeoutExpired(["openocd"], 600, output=stdout, stderr=stderr)

        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            with self.assertRaises(search.SearchStop):
                search.run(tmp, PLMARK, SIGNATURES, BASE, FARS, DIGEST, CONTROLS,
                           runner=timeout,
                           plmark_reader=lambda port: PLMARK)
            index = json.loads((tmp / "index.json").read_text("utf-8"))
            entry = index["entries"][f"{A20:#010x}"]
            log = json.loads((tmp / entry["child_log"]).read_text("utf-8"))
            streams = log["exception_streams"]
            self.assertEqual(base64.b64decode(streams["stdout"]["base64"]), stdout)
            self.assertEqual(base64.b64decode(streams["stderr"]["base64"]), stderr)
            self.assertEqual(streams["stdout"]["sha256"], hashlib.sha256(stdout).hexdigest())
            self.assertEqual(streams["stderr"]["sha256"], hashlib.sha256(stderr).hexdigest())

    def test_an_unreadable_capture_lands_a_failed_entry_and_the_partial(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            with self.assertRaises(search.SearchStop) as stopped:
                go(tmp, {}, garbage_on=A20)
            self.assertIn("could not be read", str(stopped.exception))
            index = json.loads((tmp / "index.json").read_text("utf-8"))
            entry = index["entries"][f"{A20:#010x}"]
            self.assertEqual(entry["status"], "failed")
            partial = tmp / entry["partial"]
            self.assertEqual(partial.read_text("utf-8"), "{not json")
            self.assertEqual(search._digest_of(partial), entry["partial_sha256"])


class TheVerdict(unittest.TestCase):
    def sweep(self, captures, not_attempted=()):
        complete = dict(captures)
        complete[CONTROL_FARS[0]] = CONTROLS[CONTROL_FARS[0]]
        return search.judge_sweep(
            {}, complete, list(not_attempted), SIGNATURES, CONTROLS)

    def test_a_shifted_candidate_is_located(self) -> None:
        verdict = self.sweep({A20: list(ZERO), A21: SIGNATURES[A20]})
        self.assertEqual(verdict["verdict"], "WRITE_LANDED_ELSEWHERE")
        self.assertEqual(verdict["signature_hits"][f"{A20:#010x}"], [f"{A21:#010x}"])

    def test_all_base_with_complete_coverage_says_nowhere(self) -> None:
        self.assertEqual(self.sweep({far: list(ZERO) for far in FARS})["verdict"],
                         "NOT_FOUND_COMPLETE")

    def test_all_base_with_holes_refuses_to_say_nowhere(self) -> None:
        verdict = self.sweep({A20: list(ZERO)}, [f"{A21:#010x}"])
        self.assertEqual(verdict["verdict"], "NOT_FOUND_INCOMPLETE")
        self.assertIn("not there", verdict["reading"])

    def test_a_duplicated_signature_names_nothing(self) -> None:
        verdict = self.sweep({A21: SIGNATURES[A20], A22: SIGNATURES[A20]})
        self.assertEqual(verdict["verdict"], "SIGNATURE_AMBIGUOUS")

    def test_a_match_is_the_whole_frame_not_a_few_bits(self) -> None:
        nearly = list(SIGNATURES[A20])
        nearly[50] ^= 1
        self.assertEqual(self.sweep({A21: nearly})["verdict"], "NOT_FOUND_COMPLETE")

    def test_an_all_zero_signature_is_refused_at_the_source(self) -> None:
        source = Path(search.__file__).read_text("utf-8")
        self.assertIn("is all zero and names nothing", source)


if __name__ == "__main__":
    unittest.main()
