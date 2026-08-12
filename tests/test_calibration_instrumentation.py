"""The calibration must be able to say WHEN it did each thing, and add nothing to the wire.

Seven runs stopped at the same read, but they are not seven repeats: one used the pre-shim
carrier, which is erratum 002 itself, and of the six on the exact pinned carrier only the
last ran on the current source. One clean comparable stall, then, and five historical and
partly comparable events.

Every account of the gap between the load and that read was reconstructed from outside, and
one of them was wrong: the host-only gating was supposed to be some thirty seconds and it
measures two milliseconds. Hence a timeline. And hence, equally, a timeline that costs
nothing on the wire — an earlier version read PS registers before the first carrier command,
which would have added traffic immediately ahead of the read under investigation, on a board
whose successful path also reads PS first.
"""

from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_calibrate_noop as cal  # noqa: E402

SOURCE = Path(cal.__file__).read_text(encoding="utf-8")
WRAPPER = ast.parse(inspect.getsource(cal.InstrumentedTransport))


def inner_command_calls() -> list[ast.Call]:
    return [node for node in ast.walk(WRAPPER)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "command"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "inner"]


class ItAddsNothingToTheWire(unittest.TestCase):
    def test_the_wrapper_forwards_one_to_one(self):
        """Exactly one call to the inner transport, and it lives in `command`."""
        calls = inner_command_calls()
        self.assertEqual(len(calls), 1)
        owner = next(node for node in ast.walk(WRAPPER)
                     if isinstance(node, ast.FunctionDef)
                     and any(call in ast.walk(node) for call in calls))
        self.assertEqual(owner.name, "command")

    def test_there_is_no_ps_snapshot_left(self):
        for gone in ("_snapshot_ps", "ps_before_first_carrier_read", "SNAPSHOT"):
            self.assertNotIn(gone, inspect.getsource(cal.InstrumentedTransport))

    def test_the_wrapper_never_builds_a_command_string_of_its_own(self):
        """A formatted `md`/`mw` here would be traffic the calibration did not ask for."""
        for node in ast.walk(WRAPPER):
            if isinstance(node, (ast.JoinedStr, ast.Constant)):
                text = (node.value if isinstance(node, ast.Constant) else "")
                if isinstance(text, str):
                    self.assertNotRegex(text.strip().lower(), r"^(md|mw|setenv|printenv)\b")

    def test_only_command_is_intercepted(self):
        methods = {name for name, _ in inspect.getmembers(
            cal.InstrumentedTransport, predicate=inspect.isfunction)}
        self.assertEqual(methods & {"interrupt", "close", "descriptor"}, set())


class EveryCommandIsBracketed(unittest.TestCase):
    def test_start_end_and_elapsed_are_all_recorded(self):
        code = inspect.getsource(cal.InstrumentedTransport.command)
        for field in ("start_s", "end_s", "elapsed_s"):
            self.assertIn(field, code)

    def test_a_raising_command_records_its_end_and_the_exception_type(self):
        """The command that fails is the one whose timing matters most."""
        code = inspect.getsource(cal.InstrumentedTransport.command)
        raised = code.split("except", 1)[1]
        for field in ("end_s", "elapsed_s", "exception"):
            self.assertIn(field, raised)
        self.assertIn("raise", raised)

    def test_the_entry_is_appended_before_the_call_so_a_hang_still_leaves_a_trace(self):
        code = inspect.getsource(cal.InstrumentedTransport.command)
        self.assertLess(code.index("self.commands.append(entry)"),
                        code.index("self.inner.command"))


class TheHostGateIsBracketed(unittest.TestCase):
    def test_a_marker_is_taken_before_run_candidate_on_board(self):
        marker = SOURCE.index('transport.mark("before run_candidate_on_board")')
        call = SOURCE.index("ex.run_candidate_on_board(payload, authority, session)")
        self.assertLess(marker, call)

    def test_the_marker_is_host_side_only(self):
        code = inspect.getsource(cal.InstrumentedTransport.mark)
        self.assertNotIn("inner", code)
        self.assertIn("monotonic", code)


class TheTransportIsWrappedEarlyEnough(unittest.TestCase):
    def test_the_session_is_built_on_the_wrapper(self):
        self.assertLess(SOURCE.index("InstrumentedTransport(ident.SerialTransport"),
                        SOURCE.index("ident.BoardSession(transport)"))


if __name__ == "__main__":
    unittest.main()
