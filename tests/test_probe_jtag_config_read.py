"""The JTAG configuration probe, and the instructions it must be unable to issue.

This tool shifts bits into a configured device, so its safety is a property of the words it
generates. These tests read those words rather than the docstring.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import probe_jtag_config_read as probe  # noqa: E402

FAR = 0x00400A20


class TheAllowedSet(unittest.TestCase):
    def test_only_the_four_reviewed_ir_codes_are_ever_shifted(self) -> None:
        tcl, _ = probe.build_tcl([FAR, FAR + 1])
        issued = sorted({int(code, 16)
                         for code in re.findall(r"irscan \S+ (0x[0-9a-fA-F]+)", tcl)})
        self.assertEqual(issued, sorted(probe.IR.values()))

    def test_jprogram_and_jstart_are_not_reachable(self) -> None:
        tcl, _ = probe.build_tcl([FAR])
        for name, code in probe.FORBIDDEN_IR.items():
            with self.subTest(instruction=name):
                self.assertNotIn(f"irscan {probe.TAP} 0x{code:02x}", tcl)
        self.assertEqual(set(probe.IR.values()) & set(probe.FORBIDDEN_IR.values()), set())

    def test_the_generated_payloads_pass_their_own_refusal_check(self) -> None:
        _, steps = probe.build_tcl([FAR, FAR + 1])
        self.assertTrue(steps)
        for step in steps:
            probe.check_sequence([int(word, 16) for word in step["words"]])


class TheRefusals(unittest.TestCase):
    def test_an_fdri_write_is_refused(self) -> None:
        with self.assertRaises(probe.ProbeStop):
            probe.check_sequence([probe.t1(True, probe.FDRI_REG, 1), 0xDEADBEEF])

    def test_a_wcfg_command_is_refused(self) -> None:
        with self.assertRaises(probe.ProbeStop):
            probe.check_sequence([probe.t1(True, probe.CMD_REG, 1), probe.CMD_WCFG])

    def test_a_type2_write_is_refused(self) -> None:
        word = 0x40000000 | (0b10 << 27) | 202
        with self.assertRaises(probe.ProbeStop):
            probe.check_sequence([word])

    def test_the_reads_this_tool_needs_are_not_refused(self) -> None:
        probe.check_sequence([probe.t1(True, probe.CMD_REG, 1), probe.CMD_RCFG,
                              probe.t1(True, probe.FAR_REG, 1), FAR,
                              probe.t1(False, probe.FDRO_REG, 0),
                              probe.t2_read(probe.READ_WORDS),
                              probe.t1(True, probe.CMD_REG, 1), probe.CMD_DESYNC])


class ThePacketEncoding(unittest.TestCase):
    def test_the_headers_are_the_documented_values(self) -> None:
        self.assertEqual(probe.t1(True, probe.CMD_REG, 1), 0x30008001)
        self.assertEqual(probe.t1(True, probe.FAR_REG, 1), 0x30002001)
        self.assertEqual(probe.t1(False, probe.FDRO_REG, 0), 0x28006000)
        self.assertEqual(probe.t1(False, probe.STAT_REG, 1), 0x2800E001)
        self.assertEqual(probe.t2_read(202), 0x480000CA)

    def test_the_wire_order_survives_a_round_trip(self) -> None:
        words = [0xAA995566, 0x20000000, 0x30008001, 0x00000004]
        packed = probe.field_list(words).split()[1]
        self.assertEqual(probe.decode_capture(packed, len(words)), words)

    def test_one_field_carries_the_whole_burst(self) -> None:
        """Not one field per word: a second field for the same TAP trips OpenOCD's assert."""
        spec = probe.field_list([0] * 8)
        self.assertEqual(len(spec.split()), 2, f"expected one (bits, value) pair: {spec}")
        self.assertEqual(spec.split()[0], "256")


if __name__ == "__main__":
    unittest.main()
