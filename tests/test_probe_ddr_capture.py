"""The read-only DRAM forensic capture, and the things it must never do.

A capture tool earns trust by what it cannot send. These tests pin the wire traffic
exactly, refuse anything that could disturb a fault state, and require that a capture
claiming three commands can produce all three.
"""

from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import board_serial as bs  # noqa: E402
import probe_ddr_capture as probe  # noqa: E402

SOURCE = REPO / "scripts/probe_ddr_capture.py"
PLMARK = "18cba2892df42cbd"
PROMPT = b"\r\nZynq> "


def md_reply(base: int, words: list[int]) -> bytes:
    """An `md.l` dump in U-Boot's format, four words to a line."""
    out = []
    for row in range(0, len(words), 4):
        chunk = words[row:row + 4]
        cells = " ".join(f"{word:08x}" for word in chunk)
        out.append(f"{base + row * 4:08x}: {cells}    ....")
    return ("\r\n".join(out)).encode() + PROMPT


class FakeSerial:
    """Answers exactly what the caller asked for, and remembers every line sent."""

    def __init__(self, replies) -> None:
        self.replies = replies
        self.sent: list[str] = []
        self._line = b""
        self._pending = b""

    def __enter__(self) -> "FakeSerial":
        return self

    def __exit__(self, *_) -> bool:
        return False

    def reset_input_buffer(self) -> None:
        self._pending = b""

    def write(self, data: bytes) -> None:
        self._line += data
        if self._line.endswith(b"\r"):
            line = self._line[:-1].decode("ascii")
            self._line = b""
            self.sent.append(line)
            self._pending = self.replies(line)

    def read(self, size: int) -> bytes:
        head, self._pending = self._pending[:size], self._pending[size:]
        return head


def replies_for(words: list[int], *, base: int = probe.CAPTURE_ADDR,
                plmark: str = PLMARK, banner_on: str | None = None,
                promptless_on: str | None = None):
    def answer(line: str) -> bytes:
        if line == banner_on:
            return b"\r\nU-Boot SPL 2026.04-rc5\r\nTrying to boot from MMC1" + PROMPT
        if line == promptless_on:
            return b"\r\nsomething partial and unterminated"
        if line == bs.SYNC_COMMAND:
            return b"\r\n" + PROMPT
        if line == "printenv plmark":
            return f"\r\nplmark={plmark}".encode() + PROMPT
        if line.startswith("md.l "):
            return md_reply(base, words)
        raise AssertionError(f"the tool sent an unexpected line: {line!r}")
    return answer


def run_capture(answer, slot: int = 0, plmark: str = PLMARK) -> tuple[int, dict, FakeSerial]:
    fake = FakeSerial(answer)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "capture.json"
        argv = ["probe_ddr_capture.py", "--plmark", plmark,
                "--slot", str(slot), "--out", str(out)]
        with mock.patch.object(probe.serial, "Serial", lambda *a, **k: fake), \
                mock.patch.object(sys, "argv", argv):
            code = probe.main()
        return code, json.loads(out.read_text("utf-8")), fake


class TheWireTraffic(unittest.TestCase):
    def test_exactly_three_named_commands_and_nothing_else(self) -> None:
        code, record, fake = run_capture(replies_for([0] * probe.FRAME_WORDS))
        self.assertEqual(code, 0)
        self.assertEqual(record["verdict"], "CAPTURED")
        self.assertEqual(fake.sent, ["echo", "printenv plmark", "md.l 0x10100000 0x65"])

    def test_every_reply_is_preserved_whole(self) -> None:
        _, record, fake = run_capture(replies_for([0] * probe.FRAME_WORDS))
        self.assertEqual([entry["command"] for entry in record["commands"]], fake.sent)
        for entry in record["commands"]:
            self.assertTrue(entry["base64"])
            self.assertEqual(len(entry["sha256"]), 64)
            self.assertGreater(entry["bytes"], 0)

    def test_the_source_can_send_no_write_or_carrier_access(self) -> None:
        source = SOURCE.read_text("utf-8")
        body = "\n".join(line for line in source.splitlines()
                         if not line.strip().startswith("#"))
        for forbidden in ("mw.l", "mw ", "0x43c", "saveenv", "fpga ", "run zw", "setenv"):
            self.assertNotIn(forbidden, body, f"{forbidden!r} must not be reachable here")

    def test_only_allowlisted_command_expressions_are_sent(self) -> None:
        tree = ast.parse(SOURCE.read_text("utf-8"))
        sent = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "ub_cmd":
                sent.append(node.args[1])
        self.assertTrue(sent, "the tool must send its commands through board_serial.ub_cmd")
        for expression in sent:
            if isinstance(expression, ast.Name):
                continue  # the `line` local, whose values the callers below pin
            self.fail(f"an unreviewed command expression: {ast.dump(expression)}")
        literals = {node.value for node in ast.walk(tree)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and ("md" in node.value or "printenv" in node.value)}
        self.assertIn("printenv plmark", literals)


class TheRefusals(unittest.TestCase):
    def test_a_slot_outside_the_archive_is_refused(self) -> None:
        for slot in (-1, probe.SLOTS, probe.SLOTS + 5):
            with self.subTest(slot=slot), self.assertRaises(SystemExit) as raised:
                run_capture(replies_for([0] * probe.FRAME_WORDS), slot=slot)
            self.assertNotEqual(raised.exception.code, 0)

    def test_a_boot_banner_stops_the_capture(self) -> None:
        for line in (bs.SYNC_COMMAND, "printenv plmark", "md.l 0x10100000 0x65"):
            with self.subTest(line=line):
                code, record, _ = run_capture(
                    replies_for([0] * probe.FRAME_WORDS, banner_on=line))
                self.assertEqual(code, 1)
                self.assertEqual(record["verdict"], "STOP")
                self.assertIn("restarted", record["stop_reason"])

    def test_a_missing_prompt_stops_the_capture(self) -> None:
        code, record, _ = run_capture(
            replies_for([0] * probe.FRAME_WORDS, promptless_on="printenv plmark"))
        self.assertEqual(code, 1)
        self.assertIn("no prompt", record["stop_reason"])

    def test_a_different_plmark_stops_the_capture(self) -> None:
        code, record, _ = run_capture(
            replies_for([0] * probe.FRAME_WORDS, plmark="ffffffffffffffff"))
        self.assertEqual(code, 1)
        self.assertIn("different boot", record["stop_reason"])


class TheParsing(unittest.TestCase):
    def test_a_full_contiguous_frame_is_parsed_in_address_order(self) -> None:
        words = [(i * 0x01010101) & 0xFFFFFFFF for i in range(probe.FRAME_WORDS)]
        code, record, _ = run_capture(replies_for(words))
        self.assertEqual(code, 0)
        self.assertEqual([int(w, 16) for w in record["words"]], words)
        self.assertEqual(record["nonzero_words"], sum(1 for w in words if w))

    def test_a_short_dump_is_refused(self) -> None:
        code, record, _ = run_capture(replies_for([0] * (probe.FRAME_WORDS - 4)))
        self.assertEqual(code, 1)
        self.assertIn("expected", record["stop_reason"])

    def test_a_non_contiguous_dump_is_refused(self) -> None:
        base = probe.CAPTURE_ADDR
        body = (f"{base:08x}: 00000000 00000000 00000000 00000000    ....\r\n"
                f"{base + 0x40:08x}: 00000000 00000000 00000000 00000000    ....")

        def answer(line: str) -> bytes:
            if line == bs.SYNC_COMMAND:
                return b"\r\n" + PROMPT
            if line == "printenv plmark":
                return f"\r\nplmark={PLMARK}".encode() + PROMPT
            return body.encode() + PROMPT

        code, record, _ = run_capture(answer)
        self.assertEqual(code, 1)
        self.assertIn("not contiguous", record["stop_reason"])


if __name__ == "__main__":
    unittest.main()
