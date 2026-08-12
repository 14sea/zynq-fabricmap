"""The one-line PS snapshot, and what it is allowed to conclude.

This exists because of two mistakes, one inside the other. `INT_STS.PCFG_DONE` was used as
though it said "the PL is configured", and it does not: it is a sticky write-1-to-clear
EVENT bit, so it speaks only about the past. The obvious replacement — `DEVCFG STATUS` bit
4, `PCFG_INIT` — is genuinely live, and still cannot answer the question: it is the INIT_B
pin, and this board reads it as 1 both unconfigured (`0x40000A30`, a fresh power-on) and
configured (`0x40000F30`). A live bit that does not discriminate is no better than a sticky
one. What is left is the empirical difference between those two measured values, and the
tests below pin all of it so neither mistake can quietly come back. They also pin the
parsing of a reply holding seven unrelated `md.l` dumps, which the transport's own
`parse_md` correctly refuses.

There is no board here. What is exercised is the reading and the judging, which is all of
the snapshot except the wire.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_isolate_carrier as iso  # noqa: E402

CLK_CTRL, THR_CNT, RST_CTRL, LVL = 0xF8000170, 0xF8000178, 0xF8000240, 0xF8000900
CTRL, STATUS, INT_STS = 0xF8007000, 0xF8007014, 0xF800700C

# A healthy board, measured on 17A6 after a good load.
HEALTHY = {
    CLK_CTRL: 0x00400800,
    THR_CNT: 0x00000000,
    RST_CTRL: 0x00000000,
    LVL: 0x0000000F,
    CTRL: 0x4E00E07F,
    STATUS: 0x40000F30,
    INT_STS: 0x50021004,
}


def dump(pairs) -> bytes:
    return b"".join(b"%08x: %08x    ....\r\n" % (addr, value) for addr, value in pairs)


class SnapshotOrder(unittest.TestCase):
    def test_status_is_read_before_int_sts(self):
        """The live bit is read first; the sticky event bit is a footnote, not the answer."""
        addrs = [addr for addr, _ in iso.SNAPSHOT]
        self.assertLess(addrs.index(STATUS), addrs.index(INT_STS))

    def test_every_required_register_is_in_the_snapshot(self):
        self.assertEqual([addr for addr, _ in iso.SNAPSHOT],
                         [CLK_CTRL, THR_CNT, RST_CTRL, LVL, CTRL, STATUS, INT_STS])

    def test_every_snapshot_address_is_in_the_ps(self):
        """Nothing here may be in the PL window — the whole point is that it cannot stall."""
        for addr, name in iso.SNAPSHOT:
            self.assertTrue(0xF8000000 <= addr < 0xF9000000, f"{name} at {addr:#x} is not PS")

    def test_pcfg_init_is_bit_four_of_status(self):
        self.assertEqual(iso.PCFG_INIT, 1 << 4)


class ParseSurvey(unittest.TestCase):
    def test_seven_dumps_in_one_reply(self):
        reply = dump(HEALTHY.items())
        self.assertEqual(iso.parse_survey(reply, list(HEALTHY)), HEALTHY)

    def test_a_reply_the_transports_own_parser_refuses(self):
        """`parse_md` is right to refuse this buffer, which is why `parse_survey` exists."""
        import board_uboot_axi as axi

        reply = dump(HEALTHY.items())
        with self.assertRaises(axi.AxiRefusal):
            axi.parse_md(reply, CLK_CTRL, 7)

    def test_a_truncated_line_is_refused_not_padded(self):
        """Console byte loss must become a refusal naming the missing registers."""
        partial = {a: v for a, v in HEALTHY.items() if a not in (STATUS, INT_STS)}
        with self.assertRaises(iso.Stalled) as caught:
            iso.parse_survey(dump(partial.items()), list(HEALTHY))
        self.assertIn("0xf8007014", str(caught.exception))
        self.assertIn("0xf800700c", str(caught.exception))

    def test_a_duplicated_address_is_refused_not_resolved(self):
        """An echo could supply a second value; picking one silently would invent a reading."""
        doubled = list(HEALTHY.items()) + [(STATUS, 0x00000000)]
        with self.assertRaises(iso.Stalled) as caught:
            iso.parse_survey(dump(doubled), list(HEALTHY))
        self.assertIn("more than one value", str(caught.exception))

    def test_values_are_taken_by_address_not_by_order(self):
        shuffled = list(reversed(list(HEALTHY.items())))
        self.assertEqual(iso.parse_survey(dump(shuffled), list(HEALTHY)), HEALTHY)


class JudgeSnapshot(unittest.TestCase):
    def test_a_healthy_board_has_no_problems(self):
        judged = iso.judge_snapshot(HEALTHY)
        self.assertEqual(judged["problems"], [])
        self.assertTrue(judged["pcfg_init"])
        self.assertTrue(judged["level_shifters_open"])
        self.assertFalse(judged["fclk0_gated_off"])
        self.assertFalse(judged["fpga_reset_held"])

    def test_pcfg_init_is_set_in_BOTH_measured_states(self):
        """PCFG_INIT is live and discriminates nothing — the correction this file exists for.

        Both constants are measurements from board 17A6, not assumptions: the unconfigured
        one is a fresh power-on. If a future change starts treating bit 4 as "configured",
        this test is what says it cannot be.
        """
        self.assertTrue(iso.STATUS_UNCONFIGURED_REF & iso.PCFG_INIT)
        self.assertTrue(iso.STATUS_CONFIGURED_REF & iso.PCFG_INIT)
        self.assertEqual(iso.STATUS_CONFIG_BITS, (1 << 8) | (1 << 10))

    def test_a_sticky_pcfg_done_does_not_rescue_an_unconfigured_status(self):
        """The exact error this snapshot was written to stop making."""
        values = dict(HEALTHY)
        values[STATUS] = iso.STATUS_UNCONFIGURED_REF   # the PL did not take the bitstream
        values[INT_STS] = 0x50021004                   # the sticky event bit still set
        judged = iso.judge_snapshot(values)
        self.assertTrue(judged["pcfg_done_event"])
        self.assertTrue(judged["pcfg_init"])           # and it still tells us nothing
        self.assertFalse(judged["looks_configured"])
        self.assertTrue(any("UNCONFIGURED" in problem for problem in judged["problems"]))

    def test_a_clear_pcfg_init_is_named_as_mid_clear_not_as_unconfigured(self):
        values = dict(HEALTHY)
        values[STATUS] = iso.STATUS_CONFIGURED_REF & ~iso.PCFG_INIT
        problems = iso.judge_snapshot(values)["problems"]
        self.assertTrue(any("mid-clear" in problem for problem in problems))

    def test_a_configured_status_is_not_a_problem(self):
        values = dict(HEALTHY)
        values[STATUS] = iso.STATUS_CONFIGURED_REF
        judged = iso.judge_snapshot(values)
        self.assertTrue(judged["looks_configured"])
        self.assertTrue(judged["matches_configured_ref"])
        self.assertEqual(judged["problems"], [])

    def test_a_gated_fclk0_is_named(self):
        values = dict(HEALTHY)
        values[THR_CNT] = 0x00000001
        judged = iso.judge_snapshot(values)
        self.assertTrue(judged["fclk0_gated_off"])
        self.assertTrue(any("FCLK0" in problem for problem in judged["problems"]))

    def test_a_held_fclkresetn_is_named(self):
        values = dict(HEALTHY)
        values[RST_CTRL] = 0x00000001
        self.assertTrue(any("FCLKRESETN" in p
                            for p in iso.judge_snapshot(values)["problems"]))

    def test_closed_level_shifters_are_named(self):
        values = dict(HEALTHY)
        values[LVL] = 0x00000000
        self.assertTrue(any("LVL_SHFTR_EN" in p
                            for p in iso.judge_snapshot(values)["problems"]))

    def test_pcap_pr_is_reported_but_is_not_a_problem_here(self):
        """PCAP_PR=1 only disconnects the fabric ICAPE2; it does not stop an AXI read."""
        judged = iso.judge_snapshot(HEALTHY)
        self.assertTrue(judged["pcap_pr"])
        self.assertEqual(judged["problems"], [])



class AdditiveOrder(unittest.TestCase):
    """The order the omitted steps are added back in is the experiment's design."""

    def test_the_bare_console_reopen_comes_before_either_tool(self):
        """Both tool steps contain a reopen, so a reopen tested later proves nothing."""
        labels = [what for what, _ in iso.ADDITIVE_STEPS]
        reopen = next(i for i, w in enumerate(labels) if "close and reopen" in w)
        tools = [i for i, (_, argv) in enumerate(iso.ADDITIVE_STEPS) if argv]
        self.assertTrue(tools)
        self.assertLess(reopen, min(tools))

    def test_the_first_step_is_a_control_that_changes_nothing(self):
        what, argv = iso.ADDITIVE_STEPS[0]
        self.assertIn("control", what)
        self.assertIsNone(argv)

    def test_both_calibration_tools_are_covered(self):
        argvs = " ".join(argv[0] for _, argv in iso.ADDITIVE_STEPS if argv)
        self.assertIn("board_set_fclk50.py", argvs)
        self.assertIn("gate_board_identity.py", argvs)

    def test_every_tool_step_is_read_only(self):
        """Nothing added back may itself change the board — then a breakage means something."""
        for what, argv in iso.ADDITIVE_STEPS:
            if argv and "board_set_fclk50" in argv[0]:
                self.assertIn("--verify-only", argv, f"{what} could write the clock")

if __name__ == "__main__":
    unittest.main()


class TheFclk50Cell(unittest.TestCase):
    """One cell, one added thing. The value of the comparison is that nothing else moved."""

    SOURCE = (REPO_ROOT / "scripts" / "board_isolate_carrier.py").read_text(encoding="utf-8")

    def test_fclk50_runs_before_the_load_not_after(self):
        """`board_set_fclk50` BEFORE the load is the calibration's ordering, and the point."""
        body = self.SOURCE.split("def run_snapshot", 1)[1]
        self.assertLess(body.index("board_set_fclk50.py"),
                        body.index("board_uboot_fpga_load.py"))

    def test_it_is_the_production_invocation_not_verify_only(self):
        """--verify-only is a different thing to measure; the calibration does not pass it."""
        # Split on a TOP-LEVEL def: run_snapshot has a nested `def flush()`, and splitting
        # on any "def " truncated the body before the code under test.
        body = self.SOURCE.split("def run_snapshot", 1)[1].split("\ndef ", 1)[0]
        fclk_call = body[body.index("board_set_fclk50.py"):][:400]
        self.assertNotIn("--verify-only", fclk_call)

    def test_the_snapshot_loader_never_passes_require_unconfigured(self):
        """The successful snapshot did not pass it, so this cell must not either."""
        # Split on a TOP-LEVEL def: run_snapshot has a nested `def flush()`, and splitting
        # on any "def " truncated the body before the code under test.
        body = self.SOURCE.split("def run_snapshot", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("--require-unconfigured", body)

    def test_whether_an_mw_went_out_is_recorded_not_assumed(self):
        self.assertIn("issued_an_mw", self.SOURCE)
        self.assertIn("writing FPGA0_CLK_CTRL", self.SOURCE)

    def test_the_cell_is_off_unless_asked_for(self):
        """Every earlier snapshot run must stay comparable to this one."""
        self.assertIn('"--fclk50-before-load", action="store_true"', self.SOURCE)
