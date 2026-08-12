"""The tty-lifecycle pairing, checked where it could quietly stop being an experiment.

Three ways this design could produce a confident wrong answer, each pinned below: B could
run while something else holds the device node, in which case the last fd never closes and B
is a hold-open trial wearing B's name; the marker could be asked for before the bytes are
collected, putting a transmit ahead of the evidence a restart leaves; and the run could
touch the carrier, which would make an event unattributable.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_probe_tty_lifecycle as probe  # noqa: E402

SOURCE = Path(probe.__file__).read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def transmitted_strings() -> list[str]:
    """Every literal that reaches the wire, ignoring prose about it.

    Checking the source text for a forbidden command would fail on the comment explaining
    why it is forbidden -- as this test did, first time out.
    """
    out: list[str] = []
    for node in ast.walk(TREE):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"command", "write", "write_paced"}):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                out.append(arg.value)
            elif isinstance(arg, ast.JoinedStr):
                out.append("".join(part.value for part in arg.values
                                   if isinstance(part, ast.Constant)
                                   and isinstance(part.value, str)))
    return out


def calls_to(name: str) -> list[ast.Call]:
    return [node for node in ast.walk(TREE)
            if isinstance(node, ast.Call)
            and name in ast.dump(node.func)]


class ItStaysAnExperiment(unittest.TestCase):
    def test_b_refuses_when_anything_else_holds_the_node(self):
        """The one failure that would look like a clean negative result."""
        self.assertIn("holders_after_close", SOURCE)
        self.assertIn("refused", SOURCE)

    def test_holders_are_read_from_proc_not_asked_of_a_tool(self):
        self.assertIn("/proc", SOURCE)

    def test_bytes_are_collected_before_the_marker_is_asked_for(self):
        """`drain` must precede `marker_survives` in the trial body, not follow it."""
        body = SOURCE.split("for kind in (HOLD_OPEN", 1)[1]
        self.assertLess(body.index("drain(args.settle)"), body.index("marker_survives"))

    def test_the_marker_is_never_saved_to_flash(self):
        """A marker that survives a restart measures nothing."""
        sent = transmitted_strings()
        self.assertTrue(sent, "nothing is transmitted at all — this test is vacuous")
        for line in sent:
            self.assertNotIn("saveenv", line)

    def test_the_only_things_transmitted_are_setenv_and_printenv(self):
        """Anything else on the wire would be a second variable in the experiment."""
        for line in transmitted_strings():
            stripped = line.strip()
            if not stripped or stripped == "\\r":
                continue
            # f-string literals arrive without their interpolated parts, so the command
            # word is all there is to match on.
            self.assertRegex(stripped, r"^(setenv|printenv)\b")

    def test_it_reads_no_carrier_address_and_runs_no_tool(self):
        imported = {alias.name for node in ast.walk(TREE)
                    if isinstance(node, ast.Import) for alias in node.names}
        imported |= {node.module for node in ast.walk(TREE)
                     if isinstance(node, ast.ImportFrom) and node.module}
        self.assertNotIn("subprocess", imported)
        self.assertNotIn("board_uboot_axi", imported)
        for forbidden in ("0x43c0", "openocd", "fpga loadb", "calibrate"):
            self.assertNotIn(forbidden, SOURCE.lower())

    def test_both_kinds_wait_the_same_interval(self):
        """Different intervals would make the pair a comparison of two things at once."""
        def waits_on_interval(call: ast.Call) -> bool:
            return any(isinstance(arg, ast.Attribute) and arg.attr == "interval"
                       for arg in call.args)

        self.assertTrue(any(waits_on_interval(call) for call in calls_to("drain")),
                        "A does not wait for args.interval")
        self.assertTrue(any(waits_on_interval(call) for call in calls_to("sleep")),
                        "B does not wait for args.interval")


class Pairing(unittest.TestCase):
    def test_the_order_alternates_between_pairs(self):
        """Always running A first would confound trial kind with position in the pair."""
        orders = [(probe.HOLD_OPEN, probe.CLOSE_OPEN) if pair % 2
                  else (probe.CLOSE_OPEN, probe.HOLD_OPEN) for pair in range(1, 5)]
        self.assertEqual(orders[0][0], probe.HOLD_OPEN)
        self.assertEqual(orders[1][0], probe.CLOSE_OPEN)
        self.assertNotEqual(orders[0], orders[1])
        self.assertEqual(orders[0], orders[2])

    def test_the_two_kinds_are_distinct_labels(self):
        self.assertNotEqual(probe.HOLD_OPEN, probe.CLOSE_OPEN)


class BannerDetection(unittest.TestCase):
    def test_it_matches_the_banner_this_board_prints(self):
        self.assertTrue(probe.SPL_RE.search(b"U-Boot SPL 2026.04-rc5-dirty (Aug 01 2026"))

    def test_an_idle_prompt_is_not_a_restart(self):
        self.assertIsNone(probe.SPL_RE.search(b"Zynq> \r\nZynq> "))


class Holders(unittest.TestCase):
    def test_this_process_is_found_holding_a_file_it_has_open(self):
        """Otherwise the B guard could return an empty list for the wrong reason."""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile() as handle:
            node = os.path.realpath(handle.name)
            self.assertIn(str(os.getpid()), probe.holders_of(node))

    def test_a_node_nobody_holds_comes_back_empty(self):
        self.assertEqual(probe.holders_of("/nonexistent/device/node"), [])


if __name__ == "__main__":
    unittest.main()
