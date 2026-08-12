"""A prompt from a different boot is not a prompt.

This mistake has now been made twice in the same investigation. First a console reopen was
called a "spontaneous restart" because the settle flushed the evidence away. Then a pass-1
envelope was recorded with prompt_returned=True while the board was rebooting inside it —
the reply held a whole U-Boot banner and a fresh prompt, and the instrument read the prompt
and stopped there.

So a boot banner is looked for BEFORE any prompt is believed, in every reply, everywhere a
reply is judged. And when a reply is anomalous, all of it is kept: a 400-character tail is
how a `data abort` message went missing from the one record that needed it.
"""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_calibrate_noop as cal  # noqa: E402
import board_isolate_carrier as iso  # noqa: E402
import board_serial as bs  # noqa: E402
import board_uboot_axi as axi  # noqa: E402

# Taken verbatim from evidence/calibration_noop_2026_08_12f: the envelope's reply.
REBOOT_REPLY = (
    b" 2026 - 15:00:50 +0100)\r\n\r\nCPU:   Zynq 7z010\r\nSilicon: v3.1\r\n"
    b"Model: Ebang EBAZ4203\r\nDRAM:  ECC disabled 512 MiB\r\n"
    b"Loading Environment from FAT... OK\r\nIn:    serial@e0001000\r\n"
    b"Net:   Could not get PHY for eth0: addr 0\r\nNo ethernet found.\r\n\r\nZynq> ")
GOOD_REPLY = b"md.l 0x10001800 0x48\r\n10001800: 00000000\r\nZynq> "


class ABannerBeatsAPrompt(unittest.TestCase):
    def test_the_real_reply_that_fooled_the_instrument_is_detected(self):
        self.assertTrue(bs.PROMPT_RE.search(REBOOT_REPLY), "it really does end in a prompt")
        self.assertTrue(bs.BOOT_BANNER_RE.search(REBOOT_REPLY))

    def test_an_ordinary_reply_is_not_mistaken_for_a_reboot(self):
        self.assertTrue(bs.PROMPT_RE.search(GOOD_REPLY))
        self.assertFalse(bs.BOOT_BANNER_RE.search(GOOD_REPLY))

    def test_the_transport_checks_the_banner_before_the_prompt(self):
        code = inspect.getsource(axi.command)
        self.assertLess(code.index("BOOT_BANNER_RE"), code.index("PROMPT_RE"))

    def test_the_transport_refuses_a_rebooted_reply(self):
        class Rebooted:
            def command(self, line, timeout):
                return REBOOT_REPLY

        with self.assertRaises(axi.AxiRefusal) as caught:
            axi.command(Rebooted(), "mw.l 0x0 0x4 1", 5.0)
        self.assertIn("REBOOTED", str(caught.exception))

    def test_a_good_reply_still_passes_through(self):
        class Fine:
            def command(self, line, timeout):
                return GOOD_REPLY

        self.assertEqual(axi.command(Fine(), "md.l 0x0 0x1", 5.0), GOOD_REPLY)


class EveryJudgeAgrees(unittest.TestCase):
    def test_probe_marks_a_rebooted_reply_and_withholds_the_prompt(self):
        code = inspect.getsource(iso.Probe.cmd)
        self.assertIn("BOOT_BANNER_RE", code)
        self.assertIn("and not rebooted", code)

    def test_the_instrumented_transport_does_the_same(self):
        code = inspect.getsource(cal.InstrumentedTransport.command)
        self.assertIn("BOOT_BANNER_RE", code)
        self.assertIn("and not rebooted", code)


class AnomaliesAreKeptWhole(unittest.TestCase):
    def test_the_instrument_keeps_full_bytes_when_a_reply_is_odd(self):
        code = inspect.getsource(cal.InstrumentedTransport.command)
        self.assertIn("raw_b64", code)
        self.assertIn("[-400:]", code)          # the tail is the EXCEPTION, for clean replies
        self.assertLess(code.index("raw_b64"), code.index("return reply"))

    def test_the_transports_refusal_quotes_the_complete_reply(self):
        code = inspect.getsource(axi.command)
        self.assertIn("Received (complete)", code)


if __name__ == "__main__":
    unittest.main()
