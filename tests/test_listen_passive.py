"""The passive listener's silence, checked as a property of the source.

The whole value of a supply baseline is that the host is not a participant: if anything is
sent, an unprompted restart can always be explained away as the host's doing. "I intended
not to write" is not a property of a program, so the transmit path is checked by parsing
the module rather than by reading it.
"""

from __future__ import annotations

import ast
import base64
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_listen_passive as listen  # noqa: E402

SOURCE = Path(listen.__file__).read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def called_attributes() -> set[str]:
    return {node.func.attr for node in ast.walk(TREE)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}


class ItNeverTransmits(unittest.TestCase):
    def test_no_write_of_any_kind_is_called(self):
        """The one property that makes the measurement mean anything."""
        forbidden = {"write", "write_paced", "send", "sendall", "write_timeout",
                     "ub_cmd", "sync_prompt", "command"}
        self.assertEqual(called_attributes() & forbidden, set())

    def test_the_serial_object_is_only_ever_read_from(self):
        methods = {node.func.attr for node in ast.walk(TREE)
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and isinstance(node.func.value, ast.Name) and node.func.value.id == "ser"}
        self.assertTrue(methods, "the listener does not use `ser` at all — test is vacuous")
        self.assertEqual(methods - {"read", "close"}, set())

    def test_it_runs_no_external_tool(self):
        """No JTAG, no loader, no gate — a baseline that ran a tool is not a baseline."""
        imported = {alias.name for node in ast.walk(TREE)
                    if isinstance(node, ast.Import) for alias in node.names}
        imported |= {node.module for node in ast.walk(TREE)
                     if isinstance(node, ast.ImportFrom) and node.module}
        self.assertNotIn("subprocess", imported)
        self.assertNotIn("board_uboot_axi", imported)
        self.assertNotIn("openocd", SOURCE.lower())

    def test_the_dtr_rts_side_effect_is_recorded_not_hidden(self):
        """Opening a port asserts them. That is the one thing it does, so it must be said."""
        self.assertIn("caveat_dtr_rts", SOURCE)


class BannerDetection(unittest.TestCase):
    OBSERVED = (b"U-Boot SPL 2026.04-rc5-dirty (Aug 01 2026 - 15:00:50 +0100)\r\n"
                b"Silicon version:\t3\r\nTrying to boot from MMC1\r\n\r\n\r\n"
                b"U-Boot 2026.04-rc5-dirty (Aug 01 2026 - 15:00:50 +0100)\r\n")

    def test_it_matches_the_banner_this_board_actually_printed(self):
        """Taken verbatim from evidence/isolate_additive_2026_08_12/record.json."""
        self.assertTrue(listen.SPL_RE.search(self.OBSERVED))
        self.assertTrue(listen.UBOOT_RE.search(self.OBSERVED))

    def test_one_restart_is_counted_once(self):
        self.assertEqual(len(listen.SPL_RE.findall(self.OBSERVED)), 1)

    def test_two_restarts_are_counted_twice(self):
        self.assertEqual(len(listen.SPL_RE.findall(self.OBSERVED * 2)), 2)

    def test_an_idle_console_is_not_a_restart(self):
        self.assertIsNone(listen.SPL_RE.search(b"Zynq> \r\nZynq> "))


class OffsetTimestamps(unittest.TestCase):
    def chunks(self):
        return [
            {"wall": "T0", "mono": 10.0, "b64": base64.b64encode(b"aaaa").decode()},
            {"wall": "T1", "mono": 20.0, "b64": base64.b64encode(b"bbbb").decode()},
            {"wall": "T2", "mono": 30.0, "b64": base64.b64encode(b"cccc").decode()},
        ]

    def test_an_offset_is_dated_by_the_chunk_it_arrived_in(self):
        for offset, expected in ((0, 10.0), (3, 10.0), (4, 20.0), (7, 20.0), (8, 30.0)):
            with self.subTest(offset=offset):
                self.assertEqual(
                    listen.timestamp_for_offset(self.chunks(), offset)["mono"], expected)

    def test_an_offset_past_the_end_is_undated_rather_than_guessed(self):
        self.assertIsNone(listen.timestamp_for_offset(self.chunks(), 999)["mono"])

    def test_both_clocks_are_kept(self):
        """Monotonic cannot jump, so it measures intervals; wall-clock lines up with events."""
        stamp = listen.now()
        self.assertIn("wall", stamp)
        self.assertIn("mono", stamp)


if __name__ == "__main__":
    unittest.main()
