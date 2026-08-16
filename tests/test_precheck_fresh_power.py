"""The fresh-power precheck refuses a board that moved underneath it.

Written against 1.0.0's actual failure: a board that reboots partway through the precheck
returns correct values for every register it has already answered, and 1.0.0 looked for a boot
banner only on the opening sync. The first test here is that scenario, driven end to end.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "precheck_fresh_power", REPO_ROOT / "scripts" / "precheck_fresh_power.py")
precheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(precheck)

PROMPT = b"\r\nZynq>"
BANNER = b"\r\nU-Boot SPL 2018.01 (Aug 16 2026 - 08:00:00)\r\nZynq> "
GOOD = {
    0xF8007000: b"f8007000: 4e00e07f    ....",
    0xF800700C: b"f800700c: a802000b    ....",
    0xF8007014: b"f8007014: 40000a30    0...",
    0xF8000170: b"f8000170: 00400800    ..@.",
}
PLMARK_ABSENT = b'printenv plmark\r\n## Error: "plmark" not defined'


def scripted(*, reboot_after: int | None = None, drop_prompt_at: int | None = None,
             plmark: bytes = PLMARK_ABSENT, values: dict | None = None):
    """A `send` that answers correctly, optionally rebooting or truncating at one reply."""
    table = dict(GOOD)
    table.update(values or {})
    seen = [0]

    def send(command: str) -> bytes:
        index = seen[0]
        seen[0] += 1
        if command == "echo":
            body = b""
        elif command.startswith("md.l"):
            body = table[int(command.split()[1], 16)]
        else:
            body = plmark
        if index == drop_prompt_at:
            return body
        raw = body + PROMPT
        if index == reboot_after:
            raw += BANNER
        return raw

    return send


class ARebootDuringTheChecksIsRefused(unittest.TestCase):
    def test_a_banner_after_a_correct_register_reply_stops_it(self) -> None:
        # Every value is right; the board just restarted while being asked.
        record = precheck.run_precheck(scripted(reboot_after=3))
        self.assertFalse(record["passed"])
        self.assertTrue(any("restarted mid-precheck" in problem
                            for problem in record["problems"]), record["problems"])

    def test_a_banner_on_the_opening_sync_still_stops_it(self) -> None:
        record = precheck.run_precheck(scripted(reboot_after=0))
        self.assertFalse(record["passed"])

    def test_a_banner_on_the_very_last_reply_stops_it(self) -> None:
        record = precheck.run_precheck(scripted(reboot_after=5))
        self.assertFalse(record["passed"])

    def test_every_reply_is_guarded_not_just_the_first_and_last(self) -> None:
        for index in range(6):
            with self.subTest(reply=index):
                self.assertFalse(precheck.run_precheck(scripted(reboot_after=index))["passed"])


class ATruncatedReplyIsRefused(unittest.TestCase):
    def test_a_reply_without_a_prompt_stops_it(self) -> None:
        record = precheck.run_precheck(scripted(drop_prompt_at=2))
        self.assertFalse(record["passed"])
        self.assertTrue(any("truncated" in problem for problem in record["problems"]),
                        record["problems"])

    def test_every_reply_needs_its_prompt(self) -> None:
        for index in range(6):
            with self.subTest(reply=index):
                self.assertFalse(precheck.run_precheck(scripted(drop_prompt_at=index))["passed"])


class TheFivePreconditionsStillDecide(unittest.TestCase):
    def test_a_clean_fresh_power_on_passes(self) -> None:
        record = precheck.run_precheck(scripted())
        self.assertTrue(record["passed"], record["problems"])
        self.assertEqual(len(record["checks"]), 5)
        self.assertEqual(len(record["replies"]), 6)

    def test_a_wrong_register_value_stops_it(self) -> None:
        record = precheck.run_precheck(
            scripted(values={0xF8007014: b"f8007014: 40000a31    1..."}))
        self.assertFalse(record["passed"])

    def test_pcfg_done_set_stops_it_even_though_int_sts_would_match(self) -> None:
        record = precheck.run_precheck(
            scripted(values={0xF800700C: b"f800700c: a802000f    ...."}))
        self.assertFalse(record["passed"])
        self.assertTrue(any("PCFG_DONE=1" in problem for problem in record["problems"]))

    def test_a_defined_plmark_stops_it(self) -> None:
        record = precheck.run_precheck(scripted(plmark=b"plmark=18cc352c956bf6bd"))
        self.assertFalse(record["passed"])

    def test_an_unreadable_plmark_reply_stops_it(self) -> None:
        record = precheck.run_precheck(scripted(plmark=b"something else entirely"))
        self.assertFalse(record["passed"])


class TheRawBytesSurviveIntact(unittest.TestCase):
    def test_each_reply_is_recoverable_byte_for_byte(self) -> None:
        sent: list[bytes] = []
        base = scripted()

        def send(command: str) -> bytes:
            raw = base(command) + b"\xff\xfe non-ascii \x00"
            sent.append(raw)
            return raw

        record = precheck.run_precheck(send)
        self.assertEqual(len(record["replies"]), len(sent))
        for reply, raw in zip(record["replies"], sent):
            self.assertEqual(base64.b64decode(reply["base64"]), raw)
            self.assertEqual(reply["byte_count"], len(raw))
            import hashlib
            self.assertEqual(reply["sha256"], hashlib.sha256(raw).hexdigest())


class TheRecordIsNeverReplaced(unittest.TestCase):
    def test_an_existing_record_is_refused_before_the_port_is_opened(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "precheck.json"
            out.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(precheck.PrecheckStop):
                precheck.refuse_existing(out)

    def test_an_existing_transcript_alone_is_also_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "precheck.json"
            out.with_name(out.name + ".txt").write_text("old\n", encoding="utf-8")
            with self.assertRaises(precheck.PrecheckStop):
                precheck.refuse_existing(out)

    def test_a_fresh_path_is_allowed_and_written_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sub" / "precheck.json"
            transcript = precheck.refuse_existing(out)
            record = precheck.run_precheck(scripted())
            precheck.write_record(out, transcript, record)
            self.assertEqual(json.loads(out.read_text())["passed"], True)
            self.assertTrue(transcript.exists())
            self.assertEqual(list(out.parent.glob("*.part")), [])


class ItCannotWrite(unittest.TestCase):
    def test_the_only_commands_it_can_send_are_reads(self) -> None:
        import ast
        source = (REPO_ROOT / "scripts" / "precheck_fresh_power.py").read_text(encoding="utf-8")
        literals = {node.value for node in ast.walk(ast.parse(source))
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        for literal in literals:
            self.assertFalse(literal.startswith(("mw ", "mw.", "fpga ", "setenv ", "saveenv")),
                             f"{literal!r} would change board state")


if __name__ == "__main__":
    unittest.main()
