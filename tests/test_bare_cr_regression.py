"""The bare CR that rebooted the board three times, pinned shut.

For a whole session three restarts were called spontaneous, blamed on the supply, on the PL
being configured, and on the serial port's lifecycle. They were none of those. The console
helper wrote a bare `\\r` when it reopened the port; U-Boot treats an empty line as "repeat
the last command"; the last command was an `md` of the carrier, which resumes from an
address the previous call had already advanced past; that address is unmapped, the carrier
answers SLVERR by design, the A9 takes a data abort, and U-Boot's abort path resets the CPU.
The old settle then flushed the "data abort" text away, so all that survived was a boot
banner with no cause attached.

Every link is checked below against the source that carries it, not against a summary of it,
so that a kernel bump or an RTL edit that breaks a link fails here rather than on a board.
"""

from __future__ import annotations

import ast
import inspect
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_isolate_carrier as iso  # noqa: E402
import board_uboot_axi as axi  # noqa: E402

UBOOT = Path("/home/test/u-boot")
CARRIER_AXIL = REPO_ROOT / "vivado/carrier/carrier_axil.v"

PRODUCTION_CONSOLE_MODULES = [
    "board_isolate_carrier.py",
    "board_uboot_axi.py",
    "board_serial.py",
    "board_calibrate_noop.py",
    "board_uboot_fpga_load.py",
]


def statements_of(func) -> str:
    """A function's code with its docstring dropped — prose about a call is not a call."""
    parsed = ast.parse(inspect.getsource(func).lstrip()).body[0]
    body = [node for node in parsed.body
            if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str))]
    return "\n".join(ast.unparse(node) for node in body)


class ProbeOpenTransmitsNothing(unittest.TestCase):
    """Link 0 — the one thing entirely within our control."""

    def test_open_writes_nothing_at_all(self):
        code = statements_of(iso.Probe.__init__)
        for forbidden in (".write(", "write_paced", "\\r"):
            self.assertNotIn(forbidden, code,
                             f"Probe.__init__ transmits: {forbidden!r} appears in its body")

    def test_open_has_no_send_cr_switch_left_to_turn_back_on(self):
        self.assertNotIn("send_cr", inspect.signature(iso.Probe.__init__).parameters)

    def test_no_production_console_module_writes_a_bare_cr(self):
        """A lone CR is never a command — its meaning is whatever was typed last."""
        bare_cr = re.compile(r"""write(?:_paced)?\(\s*(?:\w+\s*,\s*)?b?["']\\r["']\s*\)""")
        for name in PRODUCTION_CONSOLE_MODULES:
            path = REPO_ROOT / "scripts" / name
            if not path.exists():
                continue
            with self.subTest(module=name):
                hits = bare_cr.findall(path.read_text(encoding="utf-8"))
                self.assertEqual(hits, [], f"{name} writes a bare CR: {hits}")

    def test_no_production_module_sends_an_EMPTY_command_line(self):
        """The subtler form of the same bug, and the one that hid the longest.

        `ub_cmd(ser, "")` appends the CR itself, so an empty command string IS a bare CR.
        `sync_prompt` did exactly that, and it is the helper every board script shares.
        """
        senders = {"ub_cmd", "cmd", "command", "write_paced"}
        for path in sorted((REPO_ROOT / "scripts").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and (
                        (isinstance(node.func, ast.Attribute) and node.func.attr in senders)
                        or (isinstance(node.func, ast.Name) and node.func.id in senders))):
                    continue
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and arg.value == "":
                        self.fail(f"{path.name} sends an empty command line "
                                  f"at line {node.lineno} — that is a bare CR")

    def test_the_sync_is_a_named_harmless_command(self):
        import board_serial as bs

        self.assertTrue(bs.SYNC_COMMAND.strip(), "the sync command is blank — a bare CR")
        self.assertRegex(bs.SYNC_COMMAND, r"^[a-z]+")
        self.assertNotIn("md", bs.SYNC_COMMAND.split())
        self.assertNotIn("mw", bs.SYNC_COMMAND.split())

    def test_the_settle_keeps_what_arrives_and_cmd_keeps_it_too(self):
        """Both flush windows must read before they purge, or a cause vanishes again."""
        opened = statements_of(iso.Probe.__init__)
        self.assertLess(opened.index("discarded_on_open"), opened.index("reset_input_buffer"))
        issued = statements_of(iso.Probe.cmd)
        self.assertLess(issued.index("pending"), issued.index("reset_input_buffer"))


class UBootRepeatsTheLastCommand(unittest.TestCase):
    """Links 1 and 2 — checked in U-Boot's source, since that is what runs on the board."""

    def setUp(self):
        if not (UBOOT / "cmd/mem.c").exists():
            self.skipTest("the U-Boot tree this board runs is not present here")

    def test_md_is_declared_repeatable(self):
        """The third U_BOOT_CMD column is `repeatable`; a 0 there would break the chain."""
        source = (UBOOT / "cmd/mem.c").read_text(errors="replace")
        entry = re.search(r"U_BOOT_CMD\(\s*md,\s*(\d+),\s*(\d+),\s*do_mem_md", source)
        self.assertIsNotNone(entry, "the md command table entry has moved")
        self.assertEqual(entry.group(2), "1", "md is no longer repeatable")

    def test_md_resumes_from_the_advanced_address(self):
        source = (UBOOT / "cmd/mem.c").read_text(errors="replace")
        self.assertIn("addr = dp_last_addr;", source)
        self.assertIn("addr += bytes;", source)
        self.assertIn("dp_last_addr = addr;", source)

    def test_panic_resets_rather_than_hanging_in_this_build(self):
        config = UBOOT / ".config"
        if not config.exists():
            self.skipTest("no .config for the board's build")
        self.assertIn("# CONFIG_PANIC_HANG is not set", config.read_text(errors="replace"))

    def test_a_data_abort_reaches_panic(self):
        source = (UBOOT / "arch/arm/lib/interrupts.c").read_text(errors="replace")
        self.assertRegex(source, r"do_data_abort[\s\S]{0,400}bad_mode\s*\(")
        self.assertRegex(source, r"void bad_mode[\s\S]{0,120}panic\s*\(")


class TheRepeatLandsOnAnAddressTheCarrierRefuses(unittest.TestCase):
    """Links 3 and 4 — the arithmetic, and the RTL that answers it."""

    def test_the_repeat_of_a_fault_read_targets_fault_plus_four(self):
        """`md.l <FAULT> 1` prints one 4-byte word, so the repeat starts one word on.

        Expressed as offsets from the transport's own constants rather than as an absolute
        address: `test_single_write_entrypoint` requires the AXI window to be named in ONE
        module, and writing the literal here would quietly make this a second namer of it.
        """
        self.assertEqual(axi.FAULT + 4, axi.STATUS + 8)
        self.assertEqual(axi.STATUS + 4, axi.FAULT)

    def test_that_address_is_outside_every_window_the_carrier_decodes(self):
        offset = (axi.FAULT + 4) & 0xFFFF          # the slave decodes addr[15:0] only
        self.assertEqual(offset, 0x200C)
        self.assertNotIn(offset, {0x2004, 0x2008})
        self.assertLess(offset, 0x2010, "it would fall inside the score window")

    def test_the_rtl_answers_slverr_for_an_unmapped_register_read(self):
        rtl = CARRIER_AXIL.read_text(encoding="utf-8")
        self.assertIn("REG_BASE = 16'h2000", rtl)
        # Two read arms must refuse: an address inside the register page that decodes to
        # nothing (which is where 0x200c lands), and anything outside it.
        refusals = re.findall(r"rdata_reg\s*<=\s*32'd0;\s*s_rresp\s*<=\s*2'b10;", rtl)
        self.assertGreaterEqual(len(refusals), 2,
                                "an unmapped read no longer answers SLVERR with zero data")

    def test_refusing_is_deliberate_not_an_oversight(self):
        """If this ever becomes a stall instead, the failure mode changes completely."""
        self.assertIn("returns SLVERR rather than stalling",
                      CARRIER_AXIL.read_text(encoding="utf-8"))


class TheSupersededExperimentStaysSuperseded(unittest.TestCase):
    def test_the_factorial_refuses_to_run(self):
        import board_probe_reopen_factorial as fac

        self.assertEqual(fac.main(), 2)

    def test_it_says_e_and_f_were_never_run_and_why_they_were_insufficient(self):
        import board_probe_reopen_factorial as fac

        self.assertIn("never run", fac.SUPERSEDED)
        self.assertIn("printenv plmark", fac.SUPERSEDED)


if __name__ == "__main__":
    unittest.main()
