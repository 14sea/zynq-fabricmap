"""The JTAG configuration probe, and the instructions it must be unable to issue.

This tool shifts bits into a configured device, so its safety is a property of the words it
generates. These tests read those words rather than the docstring.
"""

from __future__ import annotations

import inspect
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import probe_jtag_config_read as probe  # noqa: E402

FAR = 0x00400A20


class TheAllowedSet(unittest.TestCase):
    def test_only_the_three_reviewed_ir_codes_are_ever_shifted(self) -> None:
        tcl, _ = probe.build_tcl([FAR, FAR + 1])
        issued = sorted({int(code, 16)
                         for code in re.findall(r"irscan \S+ (0x[0-9a-fA-F]+)", tcl)})
        self.assertEqual(issued, sorted(probe.IR.values()))

    def test_forbidden_ir_is_not_reachable(self) -> None:
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


class TheEnvelopes(unittest.TestCase):
    """One FAR-set per `sync … DESYNC`, retained as a conservative contract."""

    def setUp(self) -> None:
        self.tcl, self.steps = probe.build_tcl([FAR, FAR + 1])

    def events(self) -> list[str]:
        found = []
        for line in self.tcl.splitlines():
            if line.strip() == f"irscan {probe.TAP} 0x{probe.IR['CFG_OUT']:02x}":
                found.append("CFG_OUT")
                continue
            words = probe._payload_words(line)
            if not words:
                continue
            if probe.SYNC in words:
                found.append("SYNC")
            if any(words[i] == probe.t1(True, probe.CMD_REG, 1)
                   and words[i + 1] == probe.CMD_DESYNC for i in range(len(words) - 1)):
                found.append("DESYNC")
        return found

    def test_the_reviewed_script_leaves_no_envelope_open(self) -> None:
        self.assertEqual(probe.envelope_violations(self.tcl), [])

    def test_each_far_gets_its_own_desync(self) -> None:
        closes = [step for step in self.steps if step["step"].startswith("DESYNC after FDRO")]
        self.assertEqual([step["step"] for step in closes],
                         [f"DESYNC after FDRO {FAR:#010x}",
                          f"DESYNC after FDRO {FAR + 1:#010x}"])

    def test_a_desync_separates_a_read_from_the_next_sync(self) -> None:
        events = self.events()
        for index, event in enumerate(events):
            if event != "CFG_OUT":
                continue
            rest = events[index + 1:]
            self.assertIn("DESYNC", rest, "a CFG_OUT with no DESYNC after it")
            if "SYNC" in rest:
                self.assertLess(rest.index("DESYNC"), rest.index("SYNC"),
                                "a new SYNC opens before the previous envelope is closed")

    def test_r3_has_no_jshutdown_and_no_runtest(self) -> None:
        self.assertNotIn("JSHUTDOWN", probe.IR)
        self.assertEqual(probe.FORBIDDEN_IR["JSHUTDOWN"], 0x0D)
        self.assertNotRegex(self.tcl, r"(?m)^runtest\s+")

    def test_r3_places_rcrc_and_pre_read_desync_before_the_first_fdro(self) -> None:
        self.assertEqual(probe.recovery_order_violations(self.tcl), [])
        lines = self.tcl.splitlines()
        rcrc_words = [probe.DUMMY, probe.SYNC, probe.NOOP,
                      probe.t1(True, probe.CMD_REG, 1), probe.CMD_RCRC,
                      probe.NOOP, probe.NOOP]
        pre_read_words = [probe.DUMMY, probe.SYNC, probe.NOOP, *probe.DESYNC_TAIL]
        fdro_words = [probe.DUMMY, probe.SYNC, probe.NOOP,
                      probe.t1(True, probe.CMD_REG, 1), probe.CMD_RCFG, probe.NOOP,
                      probe.t1(True, probe.FAR_REG, 1), FAR,
                      probe.t1(False, probe.FDRO_REG, 0),
                      probe.t2_read(probe.READ_WORDS)] + [probe.NOOP] * 32
        rcrc = lines.index(f"drscan {probe.TAP} {probe.field_list(rcrc_words)}")
        pre_read_desync = lines.index(
            f"drscan {probe.TAP} {probe.field_list(pre_read_words)}")
        first_fdro = lines.index(f"drscan {probe.TAP} {probe.field_list(fdro_words)}")
        self.assertEqual([rcrc, pre_read_desync, first_fdro],
                         sorted([rcrc, pre_read_desync, first_fdro]))

    def test_r3_refuses_a_restored_jshutdown(self) -> None:
        restored = self.tcl.replace(
            "init\n", f"init\nirscan {probe.TAP} 0x{probe.FORBIDDEN_IR['JSHUTDOWN']:02x}\n", 1)
        problems = probe.recovery_order_violations(restored)
        self.assertTrue(any("forbids JSHUTDOWN" in problem for problem in problems), problems)

    def test_r3_refuses_a_restored_shutdown_dwell(self) -> None:
        restored = self.tcl.replace("init\n", "init\nruntest 1024\n", 1)
        problems = probe.recovery_order_violations(restored)
        self.assertTrue(any("forbids the shutdown RTI dwell" in problem
                            for problem in problems), problems)

    def test_r3_refuses_a_missing_rcrc(self) -> None:
        words = [probe.DUMMY, probe.SYNC, probe.NOOP,
                 probe.t1(True, probe.CMD_REG, 1), probe.CMD_RCRC,
                 probe.NOOP, probe.NOOP]
        missing = self.tcl.replace(
            f"drscan {probe.TAP} {probe.field_list(words)}", "", 1)
        problems = probe.recovery_order_violations(missing)
        self.assertTrue(any("RCRC" in problem for problem in problems), problems)

    def test_r3_refuses_a_missing_pre_read_desync(self) -> None:
        words = [probe.DUMMY, probe.SYNC, probe.NOOP, *probe.DESYNC_TAIL]
        missing = self.tcl.replace(
            f"drscan {probe.TAP} {probe.field_list(words)}", "", 1)
        problems = probe.recovery_order_violations(missing)
        self.assertTrue(any("pre-read" in problem for problem in problems), problems)

    def test_r3_refuses_the_pre_read_envelope_after_the_first_fdro(self) -> None:
        words = [probe.DUMMY, probe.SYNC, probe.NOOP, *probe.DESYNC_TAIL]
        line = f"drscan {probe.TAP} {probe.field_list(words)}"
        moved = self.tcl.replace(line + "\n", "", 1).replace(
            "echo \"@@ desync done\"", line + "\necho \"@@ desync done\"", 1)
        problems = probe.recovery_order_violations(moved)
        self.assertTrue(any("recovery prefix" in problem for problem in problems), problems)

    def test_r3_control_and_r3_use_byte_identical_child_tcl(self) -> None:
        self.assertEqual(tuple(inspect.signature(probe.build_tcl).parameters), ("far_list",))
        control_tcl, _ = probe.build_tcl([FAR])
        post_noop_tcl, _ = probe.build_tcl([FAR])
        self.assertEqual(control_tcl.encode(), post_noop_tcl.encode())

    def test_a_hole_in_an_envelope_is_named(self) -> None:
        holed = self.tcl.replace(
            f"drscan {probe.TAP} {probe.field_list(list(probe.DESYNC_TAIL))}", "", 1)
        self.assertTrue(probe.envelope_violations(holed),
                        "removing a DESYNC must be detected, not tolerated")


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
    def test_the_tool_identity_names_the_r3_sequence(self) -> None:
        self.assertEqual(probe.TOOL_VERSION, "probe_jtag_config_read.py/2.3.0")

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
