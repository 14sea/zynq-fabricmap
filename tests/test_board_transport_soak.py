#!/usr/bin/env python3
"""The board-side transport soak, proved offline — against a fake U-Boot that emits md.l lines,
never a real port. A capture tool that reports a clean path proves nothing until it is shown to
report a dirty one, so every fault the real console showed is injected: a deleted byte inside a
line, a short reply, a board reset banner, silence, a wrong adapter, a reused destination."""
from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
import unittest.mock
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import board_transport_soak as soak  # noqa: E402


def md_reply(addr: int, words: list[int]) -> bytes:
    """A U-Boot `md.l` reply: four words per line, address prefix, ASCII column, then the prompt."""
    out = bytearray()
    for i in range(0, len(words), 4):
        row = words[i:i + 4]
        hexpart = " ".join(f"{w:08x}" for w in row)
        out += f"{addr + i * 4:08x}: {hexpart}    ................\r\n".encode()
    out += b"Zynq> "
    return bytes(out)


class FakeBoard:
    """A serial.Serial double that answers `md.l` from a fixed memory image. `damage` mutates the
    reply to a chosen read index: 'delete' removes one byte, 'short' drops the last word, 'banner'
    injects a boot banner, 'silent' returns nothing. Reads pop the pending reply in chunks."""

    def __init__(self, addr, words_image, damage=None, damage_at=None, fail_open=False):
        self.addr, self.image, self.damage, self.damage_at = addr, words_image, damage, damage_at
        self.fail_open = fail_open
        self.pending = bytearray()
        self.cmd_index = -1                # -1 = the sync, 0.. = the soak reads (baseline is 0)
        self.closed = 0
        self.timeout = self.write_timeout = None

    # serial.Serial surface
    def write(self, data):
        text = bytes(data)
        if text == b"\r":
            self.pending += b"Zynq> "
            return len(data)
        if text.startswith(b"md.l"):
            self.cmd_index += 1
            self.pending += self._answer(self.cmd_index)
        return len(data)

    def read(self, n):
        out, self.pending = bytes(self.pending[:n]), self.pending[n:]
        return out

    def fileno(self):
        return 999999

    def close(self):
        self.closed += 1

    def _answer(self, idx: int) -> bytes:
        reply = md_reply(self.addr, self.image)
        if self.damage is None or idx != self.damage_at:
            return reply
        if self.damage == "delete":
            cut = reply.index(b": ") + 2                  # inside the first hex word: one digit deleted
            return reply[:cut] + reply[cut + 1:]
        if self.damage == "short":
            return md_reply(self.addr, self.image[:-1])  # one word missing
        if self.damage == "banner":
            return b"\r\nU-Boot 2026.04-rc5 (Ebang EBAZ4203)\r\nZynq> "
        if self.damage == "silent":
            return b""
        raise AssertionError(self.damage)


class TheBoardSoak(unittest.TestCase):
    ADDR = 0x00100000
    IMAGE = [0xA5A5A5A5, 0x5A5A5A5A, 0xDEADBEEF, 0xCAFEF00D,
             0x00010203, 0x04050607, 0x08090A0B, 0x0C0D0E0F]

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="soak_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.d, ignore_errors=True))
        self.boards: list = []

    def module(self, **kw):
        boards = self.boards
        addr, image = self.ADDR, self.IMAGE

        class S:
            def __init__(self, device, baud, **kwargs):
                if kw.get("fail_open"):
                    raise OSError(f"could not open port {device}")
                b = FakeBoard(addr, image, damage=kw.get("damage"), damage_at=kw.get("damage_at"))
                b.device, b.timeout, b.write_timeout = device, kwargs.get("timeout"), kwargs.get("write_timeout")
                boards.append(b)
                self._b = b
            def __getattr__(self, n):
                return getattr(self._b, n)
        return types.SimpleNamespace(Serial=S)

    def run_cli(self, *extra, module=None, out=None, ident=None):
        import contextlib
        import io
        argv = ["--device", "/dev/ebaz-uart", "--label", "t", "--out", str(out or self.d),
                "--addr", hex(self.ADDR), "--words", str(len(self.IMAGE)),
                "--repetitions", "6", "--expect-usb", "", *extra]
        buf = io.StringIO()
        ch340 = ident or {"path": "/dev/ebaz-uart", "realpath": "/dev/ttyUSB0", "char_device": True,
                          "rdev": "188:0", "usb": {"idVendor": "1a86", "idProduct": "7523"}}
        with unittest.mock.patch.dict(sys.modules, {"serial": module or self.module()}), \
                unittest.mock.patch.object(soak, "device_identity", lambda p: dict(ch340)), \
                unittest.mock.patch.object(soak.time, "sleep", lambda s: None):
            with contextlib.redirect_stdout(buf):
                code = soak.main(argv)
        return code, json.loads(buf.getvalue().strip().splitlines()[-1])

    def test_a_clean_path_soaks_to_completion_with_zero_damage(self):
        code, brief = self.run_cli()
        self.assertEqual(code, 0, brief)
        self.assertEqual(brief["terminal"], "exposure_repetitions")
        self.assertEqual(brief["damaged_reads"], 0)
        self.assertGreater(brief["received_bytes"], 0)
        self.assertEqual(brief["damaged_per_100k_bytes"], 0.0)
        for name in ("invocation.json", "baseline.json", "baseline.bin", "soak.json", "entry.json"):
            self.assertTrue((self.d / name).is_file(), name)
        result = json.loads((self.d / "soak.json").read_text())
        self.assertEqual(result["reads_done"], 6)
        self.assertEqual(result["b2q_reference"]["crc_budget"], 3)
        self.assertEqual(self.boards[0].closed, 1)                              # released
        self.assertTrue(brief["export_complete"])

    def test_a_deleted_byte_in_a_line_is_one_structural_damage(self):
        code, brief = self.run_cli(module=self.module(damage="delete", damage_at=2))
        self.assertEqual(code, 0, brief)
        self.assertEqual(brief["damaged_reads"], 1)
        self.assertGreater(brief["damaged_per_100k_bytes"], 0)
        result = json.loads((self.d / "soak.json").read_text())
        hit = [r for r in result["reads"] if r.get("damaged")]
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["damage"], "structural")               # the shift breaks the word count/address

    def test_a_word_that_differs_from_the_baseline_is_a_word_mismatch(self):
        # a reply that parses cleanly but with a changed value: patch the image mid-stream
        boards = self.boards
        addr, image = self.ADDR, self.IMAGE

        class S:
            def __init__(self, device, baud, **kw):
                b = FakeBoard(addr, list(image))
                b.device = device
                orig = b._answer
                def answer(idx, _b=b, _o=orig):
                    if idx == 3:
                        _b.image = list(image); _b.image[5] ^= 0x1        # one flipped bit, valid format
                        r = _o(idx); _b.image = list(image); return r
                    return _o(idx)
                b._answer = answer
                boards.append(b); self._b = b
            def __getattr__(self, n): return getattr(self._b, n)
        code, brief = self.run_cli(module=types.SimpleNamespace(Serial=S))
        self.assertEqual(code, 0, brief)
        self.assertEqual(brief["damaged_reads"], 1)
        hit = [r for r in json.loads((self.d / "soak.json").read_text())["reads"] if r.get("damaged")]
        self.assertEqual(hit[0]["damage"], "word_mismatch")
        self.assertEqual(hit[0]["diff_count"], 1)

    def test_three_damaged_reads_stop_the_soak_on_the_registered_rule(self):
        # every read after the baseline is short → damage accrues until the stop rule fires
        boards = self.boards
        addr, image = self.ADDR, self.IMAGE

        class S:
            def __init__(self, device, baud, **kw):
                b = FakeBoard(addr, image)
                b.device = device
                b._answer = lambda idx, _b=b: (md_reply(addr, image) if idx == 0
                                               else md_reply(addr, image[:-1]))
                boards.append(b); self._b = b
            def __getattr__(self, n): return getattr(self._b, n)
        code, brief = self.run_cli("--repetitions", "10", module=types.SimpleNamespace(Serial=S))
        self.assertEqual(code, 0, brief)
        self.assertEqual(brief["terminal"], "stop_rule_damage")
        self.assertEqual(brief["damaged_reads"], soak.STOP_AT_DAMAGE)

    def test_a_boot_banner_mid_soak_is_a_board_disruption_exit_2(self):
        code, brief = self.run_cli(module=self.module(damage="banner", damage_at=3))
        self.assertEqual(code, 2, brief)
        self.assertEqual(brief["terminal"], "board_disruption")
        self.assertIn("boot banner", brief["detail"])
        self.assertTrue((self.d / "soak.json").is_file())               # evidence still lands

    def test_silence_at_the_baseline_refuses_before_the_soak(self):
        code, brief = self.run_cli(module=self.module(damage="silent", damage_at=0))
        self.assertEqual(code, 3, brief)
        self.assertEqual(brief["refusal"], "baseline")
        self.assertFalse((self.d / "soak.json").exists())              # nothing was spent

    def test_the_wrong_adapter_is_refused_before_opening(self):
        ftdi = {"path": "/dev/ebaz-uart", "realpath": "/dev/ttyUSB9", "char_device": True,
                "rdev": "188:9", "usb": {"idVendor": "0403", "idProduct": "6001"}}
        code, brief = self.run_cli("--expect-usb", "1a86:7523", ident=ftdi)
        self.assertEqual(code, 3, brief)
        self.assertEqual(brief["refusal"], "identity")
        self.assertEqual(self.boards, [])                              # never opened

    def test_a_device_that_will_not_open_is_exit_4(self):
        code, brief = self.run_cli(module=self.module(fail_open=True))
        self.assertEqual(code, 4, brief)
        self.assertIn("could not open", brief["error"])
        self.assertTrue((self.d / "open_error.json").is_file())

    def test_a_nonempty_destination_is_refused_byte_untouched(self):
        (self.d / "soak.json").write_bytes(b"old")
        code, brief = self.run_cli()
        self.assertEqual(code, 5, brief)
        self.assertEqual(brief["stage"], "destination")
        self.assertEqual((self.d / "soak.json").read_bytes(), b"old")
        self.assertEqual(self.boards, [])

    def test_parse_md_flags_a_short_or_misaddressed_reply(self):
        good = md_reply(self.ADDR, self.IMAGE)
        words, err = soak.parse_md(good, self.ADDR, len(self.IMAGE))
        self.assertIsNone(err)
        self.assertEqual(words, self.IMAGE)
        _, err = soak.parse_md(good, self.ADDR, len(self.IMAGE) + 4)
        self.assertIn("not", err)
        _, err = soak.parse_md(md_reply(self.ADDR + 0x40, self.IMAGE), self.ADDR, len(self.IMAGE))
        self.assertIn("expected", err)


if __name__ == "__main__":
    unittest.main()
