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
    def test_only_the_five_reviewed_ir_codes_are_ever_shifted(self) -> None:
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

    def test_r4_allowlists_jstart_without_allowing_jprogram(self) -> None:
        self.assertEqual(probe.IR["JSHUTDOWN"], 0x0D)
        self.assertEqual(probe.IR["JSTART"], 0x0C)
        self.assertEqual(probe.FORBIDDEN_IR, {"JPROGRAM": 0x0B})

    def test_r4_pins_the_complete_prefix_and_exact_dwells(self) -> None:
        self.assertEqual(probe.recovery_order_violations(self.tcl), [])
        lines = self.tcl.splitlines()
        rcrc_words = [probe.DUMMY, probe.SYNC, probe.NOOP,
                      probe.t1(True, probe.CMD_REG, 1), probe.CMD_RCRC,
                      probe.NOOP, probe.NOOP]
        fdro_words = [probe.DUMMY, probe.SYNC, probe.NOOP,
                      probe.t1(True, probe.CMD_REG, 1), probe.CMD_RCFG, probe.NOOP,
                      probe.t1(True, probe.FAR_REG, 1), FAR,
                      probe.t1(False, probe.FDRO_REG, 0),
                      probe.t2_read(probe.READ_WORDS)] + [probe.NOOP] * 32
        leading_shutdown = lines.index(f"irscan {probe.TAP} 0x{probe.IR['JSHUTDOWN']:02x}")
        first_dwell = lines.index("runtest 12")
        jstart = lines.index(f"irscan {probe.TAP} 0x{probe.IR['JSTART']:02x}")
        startup_dwell = lines.index("runtest 2000")
        rcrc = lines.index(f"drscan {probe.TAP} {probe.field_list(rcrc_words)}")
        final_shutdown = lines.index(
            f"irscan {probe.TAP} 0x{probe.IR['JSHUTDOWN']:02x}", leading_shutdown + 1)
        final_dwell = lines.index("runtest 12", first_dwell + 1)
        first_fdro = lines.index(f"drscan {probe.TAP} {probe.field_list(fdro_words)}")
        prefix = [leading_shutdown, first_dwell, jstart, startup_dwell, rcrc,
                  final_shutdown, final_dwell, first_fdro]
        self.assertEqual(prefix, sorted(prefix))
        self.assertEqual(re.findall(r"(?m)^runtest\s+(\d+)$", self.tcl),
                         ["12", "2000", "12"])

    def test_every_r4_dwell_has_document_provenance(self) -> None:
        self.assertEqual(set(probe.R4_DWELLS),
                         {"startup_cycle_shutdown", "startup", "readback_shutdown"})
        self.assertEqual([entry["cycles"] for entry in probe.R4_DWELLS.values()],
                         [12, 2000, 12])
        self.assertEqual([(entry["chapter"], entry["table"])
                          for entry in probe.R4_DWELLS.values()],
                         [("6", "6-6"), ("10", "10-4"), ("6", "6-6")])
        for name, entry in probe.R4_DWELLS.items():
            with self.subTest(dwell=name):
                self.assertEqual(set(entry),
                                 {"cycles", "document_id", "version", "chapter", "table"})
                self.assertEqual(entry["document_id"], "UG470")
                self.assertEqual(entry["version"], "v1.17")
                self.assertRegex(entry["chapter"], r"^\d+$")
                self.assertRegex(entry["table"], r"^\d+-\d+$")

    def test_r4_refuses_a_missing_rcrc(self) -> None:
        words = [probe.DUMMY, probe.SYNC, probe.NOOP,
                 probe.t1(True, probe.CMD_REG, 1), probe.CMD_RCRC,
                 probe.NOOP, probe.NOOP]
        missing = self.tcl.replace(
            f"drscan {probe.TAP} {probe.field_list(words)}", "", 1)
        problems = probe.recovery_order_violations(missing)
        self.assertTrue(any("RCRC" in problem for problem in problems), problems)

    def test_r4_refuses_the_r2_pre_read_envelope(self) -> None:
        words = [probe.DUMMY, probe.SYNC, probe.NOOP, *probe.DESYNC_TAIL]
        line = f"drscan {probe.TAP} {probe.field_list(words)}"
        restored = self.tcl.replace("runtest 12\n", "runtest 12\n" + line + "\n", 1)
        problems = probe.recovery_order_violations(restored)
        self.assertTrue(any("pre-read" in problem for problem in problems), problems)

    def test_r4_refuses_missing_or_misordered_instructions(self) -> None:
        jstart = f"irscan {probe.TAP} 0x{probe.IR['JSTART']:02x}\n"
        first_shutdown = f"irscan {probe.TAP} 0x{probe.IR['JSHUTDOWN']:02x}\n"
        cases = {
            "missing JSTART": self.tcl.replace(jstart, "", 1),
            "missing leading JSHUTDOWN": self.tcl.replace(first_shutdown, "", 1),
            "JSTART after first FDRO": self.tcl.replace(jstart, "", 1).replace(
                "echo \"@@ desync done\"", jstart + "echo \"@@ desync done\"", 1),
        }
        for name, altered in cases.items():
            with self.subTest(case=name):
                self.assertTrue(probe.recovery_order_violations(altered))

    def test_r4_refuses_each_wrong_dwell_in_both_directions(self) -> None:
        replacements = [("runtest 12", "runtest 11", 1),
                        ("runtest 12", "runtest 13", 1),
                        ("runtest 2000", "runtest 1999", 1),
                        ("runtest 2000", "runtest 2001", 1)]
        second_12 = self.tcl.rfind("runtest 12")
        cases = [self.tcl[:second_12] + "runtest 11" + self.tcl[second_12 + 10:],
                 self.tcl[:second_12] + "runtest 13" + self.tcl[second_12 + 10:]]
        cases.extend(self.tcl.replace(old, new, count) for old, new, count in replacements)
        for altered in cases:
            with self.subTest(dwells=re.findall(r"(?m)^runtest\s+(\d+)$", altered)):
                self.assertTrue(probe.recovery_order_violations(altered))

    def test_r4_refuses_rcrc_after_the_final_jshutdown(self) -> None:
        rcrc_words = [probe.DUMMY, probe.SYNC, probe.NOOP,
                      probe.t1(True, probe.CMD_REG, 1), probe.CMD_RCRC,
                      probe.NOOP, probe.NOOP]
        rcrc_line = f"drscan {probe.TAP} {probe.field_list(rcrc_words)}\n"
        moved = self.tcl.replace(rcrc_line, "", 1)
        after_final_shutdown = moved.rfind("runtest 12\n") + len("runtest 12\n")
        moved = moved[:after_final_shutdown] + rcrc_line + moved[after_final_shutdown:]
        problems = probe.recovery_order_violations(moved)
        self.assertTrue(problems)

    def test_r4_control_and_r4_use_byte_identical_child_tcl(self) -> None:
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
    def test_the_tool_identity_names_the_r4_sequence(self) -> None:
        self.assertEqual(probe.TOOL_VERSION, "probe_jtag_config_read.py/2.4.0")

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
