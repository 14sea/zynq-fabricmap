"""The B4 carrier v2 register map against the RTL decode (the instrument's test_axi_map_vs_rtl rule, ported as
tests/test_b1_carrier.py::MmioAllowlist did): app reads ⊆ RTL reads, app writes ⊆ RTL writes, RTL − app = the key
window on write and nothing on read; the VARIANT word and the mechanism as the RTL has them; the STEP_IN packing
and the realisability rule as the engine decodes them."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b4carrier_regmap as rm  # noqa: E402

AXIL = (R / "rtl/b4/b4_axil.v").read_text()
ENGINE = (R / "rtl/b4/b4_engine.v").read_text()


def rtl_reads() -> set:
    out = set()
    for m in re.finditer(r"ra == 16'h([0-9A-Fa-f]{4})", AXIL):
        out.add(int(m.group(1), 16))
    for m in re.finditer(r"ra >= 16'h([0-9A-Fa-f]{4}) && ra < 16'h([0-9A-Fa-f]{4})", AXIL):
        out.update(range(int(m.group(1), 16), int(m.group(2), 16), 4))
    return out


def rtl_writes() -> set:
    out = set()
    for m in re.finditer(r"wire wr_\w+\s*=\s*\(wa == 16'h([0-9A-Fa-f]{4})\)", AXIL):
        out.add(int(m.group(1), 16))
    for m in re.finditer(r"wire wr_\w+\s*=\s*\(wa >= 16'h([0-9A-Fa-f]{4})\) && \(wa < 16'h([0-9A-Fa-f]{4})\)", AXIL):
        out.update(range(int(m.group(1), 16), int(m.group(2), 16), 4))
    return out


class Allowlist(unittest.TestCase):
    def test_reads_within_rtl_and_rtl_within_app(self):
        rtl = rtl_reads()
        self.assertEqual(sorted(hex(x) for x in rm.APP_READABLE - rtl), [])
        self.assertEqual(sorted(hex(x) for x in rtl - rm.APP_READABLE), [])
        self.assertIn(rm.VARIANT, rm.APP_READABLE)

    def test_writes_within_rtl_and_only_the_key_window_beyond(self):
        rtl = rtl_writes()
        self.assertEqual(sorted(hex(x) for x in rm.APP_WRITABLE - rtl), [])
        self.assertEqual(rtl - rm.APP_WRITABLE, rm.KEY_WINDOW)

    def test_stable_words_keep_their_offsets(self):
        self.assertEqual((rm.STATUS, rm.FAULT, rm.HEARTBEAT, rm.NONCE_LO, rm.NONCE_HI, rm.VARIANT, rm.BASE_STATE, rm.SLOT_IN_READ), (0x2004, 0x2008, 0x2028, 0x202C, 0x2030, 0x2034, 0x203C, 0x2040))
        self.assertEqual(rm.PAYLOAD[0], 0x2100); self.assertEqual(rm.TAG[0], 0x2150); self.assertEqual(rm.KEY[0], 0x2160); self.assertEqual(rm.HW_COMMIT[0], 0x2200)

    def test_variant_and_mechanism_match_the_rtl(self):
        self.assertIn(f"VARIANT_WORD = 32'h{rm.VARIANT_WORD:08X}", AXIL)
        self.assertIn(f"MECHANISM    = 8'd{rm.MECHANISM}", AXIL)
        for name, bit in rm.CTRL_BITS.items():
            self.assertRegex(AXIL, rf"w_data\[{bit}\]", name)
        self.assertIn("ctrl_accept = ctrl_one && ctrl_known && ctrl_a5_ok && !engine_busy && !gate_busy", AXIL)

    def test_ctrl_acceptance_rule(self):
        self.assertTrue(rm.ctrl_accepted(rm.ctrl_word("step")))
        self.assertTrue(rm.ctrl_accepted(rm.ctrl_word("arm", a5=True)))
        self.assertFalse(rm.ctrl_accepted(rm.ctrl_word("step") | rm.ctrl_word("close")))      # combined
        self.assertFalse(rm.ctrl_accepted(1 << 7))                                               # the A5 flag alone
        self.assertFalse(rm.ctrl_accepted(rm.ctrl_word("step") | (1 << 16)))                     # an unknown bit
        self.assertFalse(rm.ctrl_accepted(0))
        with self.assertRaises(ValueError):
            rm.ctrl_word("step", a5=True)

    def test_fault_codes_match_the_rtl(self):
        for code, name in rm.FAULT_CODES.items():
            if code:
                self.assertRegex(ENGINE + (R / "rtl/b4/b4_gate.v").read_text(), rf"= 4'd{code}\b", name)


class StepWord(unittest.TestCase):
    def test_packing_matches_the_engine(self):
        w = rm.step_word(0xA5, 0xFF, 0x00, 1)
        self.assertEqual((w & 0xFF, (w >> 8) & 0xFF, (w >> 16) & 0xFF, (w >> 24) & 1), (0xA5, 0xFF, 0x00, 1))
        # the engine LATCHES the accepted word (`cmd <= step_in`) and applies only the latched copy
        self.assertIn("cmd <= step_in", ENGINE)
        self.assertIn("slice_d <= cmd[7:0]", ENGINE); self.assertIn("slice_ce <= cmd[8]", ENGINE); self.assertIn("slice_sr <= cmd[16]", ENGINE)
        self.assertIn("slice_clk <= cmd[24]", ENGINE)

    def test_realisability(self):
        self.assertTrue(rm.realisable(0x00, 0xFF)); self.assertFalse(rm.realisable(0x3C, 0x00)); self.assertFalse(rm.realisable(0xFF, 0x01))
        self.assertIn("(step_in[15:8] == 8'h00) || (step_in[15:8] == 8'hFF)", ENGINE)

    def test_bad_inputs_refused(self):
        with self.assertRaises(ValueError):
            rm.step_word(256, 0, 0, 0)
        with self.assertRaises(ValueError):
            rm.step_word(0, 0, 0, 2)

    def test_status_and_witness_decode(self):
        st = rm.decode_status((1 << 26) | (3 << 21) | (5 << 16) | (1 << 12))
        self.assertEqual((st["restore_done"], st["step_index"], st["slot_count"], st["idle"], st["reserved_zero"]), (1, 3, 5, 1, True))
        w = rm.decode_witness((1 << 25) | (2 << 16) | (2 << 8) | 7)
        self.assertEqual((w["pre_context_a5"], w["pulse"], w["mechanism"], w["gsr_count"]), (1, 2, 2, 7))
        self.assertEqual(rm.decode_applied(rm.step_word(0xA5, 0xFF, 0x00, 1)), {"d": 0xA5, "ce": 0xFF, "sr": 0, "clock": 1})

    def test_timing_round_trip(self):
        w = rm.timing_word(8, 16, 4, 4, 4)
        self.assertEqual(rm.decode_timing(w), {"assert_delay": 8, "release": 16, "sample_offset": 4, "settle": 4, "hold": 4})


if __name__ == "__main__":
    unittest.main()
