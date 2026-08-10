"""The board identity gate refuses, and cannot be talked out of it.

No board is needed: a fake transport replays U-Boot replies, so every refusal is exercised
including the ones a real correct board can never produce (wrong IDCODE, duplicated
variable, silence). That is the point — a gate is only known to work by the wrong inputs
it rejects.

Two cases carry most of the weight:

* `test_write_is_refused_without_a_verification_on_this_session` — the interlock. Verifying
  on one session and writing on another must not be expressible, because between the two
  the symlink can move to a different CH340 or the boards can be swapped.
* `test_no_argument_can_relax_a_requirement` — reads the parser's own option strings. A
  `--force` added later fails this test rather than passing review unnoticed.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_set_fclk50 as fclk  # noqa: E402
import gate_board_identity as gbi  # noqa: E402

PROMPT = b"\r\nZynq> "

class FakeTransport:
    """Replays replies keyed by command, and records what was asked."""

    def __init__(self, env=None, regs=None, silent_for=(), duplicate=()):
        self.env = {"boardid": "17A6", "role": "verify"} if env is None else env
        self.regs = dict(regs) if regs is not None else {}
        self.silent_for = set(silent_for)
        self.duplicate = set(duplicate)
        self.commands = []

    def command(self, line: str, timeout: float = 1.5) -> bytes:
        self.commands.append(line)
        if line in self.silent_for:
            return b"" + PROMPT
        if line.startswith("printenv "):
            name = line.split()[1]
            if name not in self.env:
                return b'## Error: "' + name.encode() + b'" not defined' + PROMPT
            body = f"{name}={self.env[name]}".encode()
            if name in self.duplicate:
                body += b"\r\n" + body
            # U-Boot echoes the command line first, exactly like the real thing.
            return line.encode() + b"\r\n" + body + PROMPT
        if line.startswith("md "):
            addr = int(line.split()[1], 16)
            if addr not in self.regs:
                return b"unknown" + PROMPT
            return (
                line.encode()
                + b"\r\n"
                + f"{addr:08x}: {self.regs[addr]:08x}".encode()
                + PROMPT
            )
        return PROMPT

    def descriptor(self) -> dict:
        return {"requested_port": "/dev/ebaz-uart", "resolved_port": "/dev/ttyUSB0",
                "device_id": "188:0"}


def good_regs() -> dict:
    """Registers a real 4203 at 50 MHz would return, computed not guessed."""
    io_pll = None
    for ctrl in range(0x00000000, 0x00100000, 0x1000):
        if abs(fclk.pll_mhz(ctrl, gbi.PS_CLK_MHZ) - 1600.0) < 0.5:
            io_pll = ctrl
            break
    assert io_pll is not None, "no IO PLL_CTRL encoding yields 1600 MHz"
    return {
        gbi.SLCR_PSS_IDCODE: 0x13722093,
        fclk.IO_PLL_CTRL: io_pll,
        fclk.ARM_PLL_CTRL: io_pll,
        fclk.DDR_PLL_CTRL: io_pll,
        fclk.FPGA0_CLK_CTRL: 0x00400800,  # /8 /4 -> 50 MHz
    }


class ParsingTests(unittest.TestCase):
    def test_exactly_one_assignment(self):
        self.assertEqual(gbi.parse_env_value(b"boardid=17A6\r\n", "boardid"), "17A6")

    def test_missing_variable_is_refused(self):
        with self.assertRaises(gbi.IdentityError) as ctx:
            gbi.parse_env_value(b'## Error: "role" not defined\r\n', "role")
        self.assertIn("treated as 'reference'", str(ctx.exception))

    def test_duplicate_assignment_is_refused(self):
        with self.assertRaises(gbi.IdentityError) as ctx:
            gbi.parse_env_value(b"boardid=17A6\r\nboardid=08EB\r\n", "boardid")
        self.assertIn("ambiguous", str(ctx.exception))

    def test_empty_value_is_refused(self):
        with self.assertRaises(gbi.IdentityError):
            gbi.parse_env_value(b"role=\r\n", "role")

    def test_another_variable_does_not_answer_for_this_one(self):
        with self.assertRaises(gbi.IdentityError):
            gbi.parse_env_value(b"boardid=17A6\r\n", "role")

    def test_register_read_requires_exactly_one_line(self):
        transport = FakeTransport(regs={0x100: 0xDEADBEEF})
        self.assertEqual(gbi.read_register(transport, 0x100), 0xDEADBEEF)

    def test_register_silence_is_refused(self):
        transport = FakeTransport(regs={}, silent_for={"md 0x00000100 1"})
        with self.assertRaises(gbi.IdentityError) as ctx:
            gbi.read_register(transport, 0x100)
        self.assertIn("timeout or unparseable", str(ctx.exception))

    def test_two_md_lines_are_refused(self):
        class TwoLines(FakeTransport):
            def command(self, line, timeout=1.5):
                return b"00000100: aaaaaaaa\r\n00000104: bbbbbbbb\r\n" + PROMPT

        with self.assertRaises(gbi.IdentityError) as ctx:
            gbi.read_register(TwoLines(), 0x100)
        self.assertIn("ambiguous", str(ctx.exception))


class IdentityTests(unittest.TestCase):
    def session(self, **kwargs) -> gbi.BoardSession:
        regs = kwargs.pop("regs", None) or good_regs()
        return gbi.BoardSession(FakeTransport(regs=regs, **kwargs))

    def test_the_right_board_is_accepted(self):
        identity = self.session().verify_identity()
        self.assertEqual(identity["parsed"]["boardid"], "17A6")
        self.assertEqual(identity["parsed"]["role"], "verify")
        self.assertAlmostEqual(identity["parsed"]["fclk0_mhz"], 50.0, places=1)
        self.assertEqual(identity["findings"], [])

    def test_raw_replies_and_parsed_fields_are_both_kept(self):
        identity = self.session().verify_identity()
        self.assertIn("printenv boardid", identity["raw_replies"])
        self.assertIn("17A6", identity["raw_replies"]["printenv boardid"])
        self.assertIn("parsed", identity)

    def test_a_different_boardid_is_refused(self):
        session = self.session(env={"boardid": "08EB", "role": "sacrificial"})
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.verify_identity()
        self.assertIn("preregistered for '17A6'", str(ctx.exception))

    def test_the_reference_board_is_refused(self):
        session = self.session(env={"boardid": "4205", "role": "reference"})
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.verify_identity()
        self.assertIn("may not host a content-class write", str(ctx.exception))

    def test_a_board_with_no_role_is_refused(self):
        session = self.session(env={"boardid": "17A6"})
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.verify_identity()
        self.assertIn("role", str(ctx.exception))

    def test_the_right_board_with_the_wrong_role_is_refused(self):
        """boardid 17A6 but role=sacrificial.

        `sacrificial` is an allowed role for a content-class write in general, so the
        tier check passes it; only the preregistered role requirement refuses it. Without
        this case, deleting that requirement leaves every test green.
        """
        session = self.session(env={"boardid": "17A6", "role": "sacrificial"})
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.verify_identity()
        self.assertIn("role is 'sacrificial', expected 'verify'", str(ctx.exception))

    def test_a_duplicated_boardid_is_refused(self):
        session = self.session(duplicate={"boardid"})
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.verify_identity()
        self.assertIn("ambiguous", str(ctx.exception))

    def test_a_wrong_idcode_is_refused(self):
        regs = good_regs()
        regs[gbi.SLCR_PSS_IDCODE] = 0x1372C093  # a different 7-series device
        session = self.session(regs=regs)
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.verify_identity()
        self.assertIn("is not XC7Z010", str(ctx.exception))

    def test_the_silicon_revision_nibble_is_ignored(self):
        regs = good_regs()
        regs[gbi.SLCR_PSS_IDCODE] = 0x33722093  # revision 3, same device
        self.session(regs=regs).verify_identity()

    def test_a_wrong_clock_is_refused(self):
        regs = good_regs()
        regs[fclk.FPGA0_CLK_CTRL] = 0x00200A00  # the 4205 magic: 80 MHz on a 4203
        session = self.session(regs=regs)
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.verify_identity()
        self.assertIn("FCLK0 is", str(ctx.exception))
        self.assertIn("never from a remembered constant", str(ctx.exception))

    def test_silence_on_identity_is_refused(self):
        session = self.session(silent_for={"printenv boardid"})
        with self.assertRaises(gbi.IdentityError):
            session.verify_identity()

    def test_routing_class_requires_the_sacrificial_board(self):
        session = self.session()  # role=verify
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.verify_identity(bit_class_tier="routing")
        self.assertIn("may not host a routing-class write", str(ctx.exception))


class InterlockTests(unittest.TestCase):
    def test_write_is_refused_without_a_verification_on_this_session(self):
        session = gbi.BoardSession(FakeTransport(regs=good_regs()))
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.authorise_write()
        self.assertIn("SAME open session", str(ctx.exception))

    def test_write_is_authorised_after_verification(self):
        session = gbi.BoardSession(FakeTransport(regs=good_regs()))
        session.verify_identity()
        self.assertEqual(session.authorise_write()["parsed"]["boardid"], "17A6")

    def test_a_failed_verification_leaves_no_authorisation(self):
        session = gbi.BoardSession(
            FakeTransport(env={"boardid": "08EB", "role": "verify"}, regs=good_regs())
        )
        with self.assertRaises(gbi.IdentityError):
            session.verify_identity()
        with self.assertRaises(gbi.IdentityError):
            session.authorise_write()

    def test_another_session_cannot_borrow_an_authorisation(self):
        """The window this closes: verify here, write over a re-resolved symlink there."""
        verified = gbi.BoardSession(FakeTransport(regs=good_regs()))
        verified.verify_identity()
        other = gbi.BoardSession(FakeTransport(regs=good_regs()))
        with self.assertRaises(gbi.IdentityError):
            other.authorise_write()

    def test_a_later_failed_verification_revokes_the_earlier_one(self):
        """Verify, then the board changes underneath, then verify again and fail.

        Without revocation the session keeps the FIRST identity and authorises a write to
        whatever is on the wire now — the exact swap this interlock exists to stop. A
        session that has never verified starts at None, so only this sequence can show
        the reset is really there.
        """
        transport = FakeTransport(regs=good_regs())
        session = gbi.BoardSession(transport)
        session.verify_identity()
        self.assertIsNotNone(session.identity)

        transport.env = {"boardid": "08EB", "role": "sacrificial"}  # a different board
        with self.assertRaises(gbi.IdentityError):
            session.verify_identity()
        self.assertIsNone(session.identity)
        with self.assertRaises(gbi.IdentityError):
            session.authorise_write()

    def test_identity_is_bound_to_the_transport_that_answered(self):
        transport = FakeTransport(regs=good_regs())
        session = gbi.BoardSession(transport)
        identity = session.verify_identity()
        self.assertEqual(identity["transport"], transport.descriptor())


class EpochTests(unittest.TestCase):
    """An authorisation is scoped to an epoch, and recovery ends an epoch."""

    def verified(self) -> gbi.BoardSession:
        session = gbi.BoardSession(FakeTransport(regs=good_regs()))
        session.verify_identity()
        return session

    def test_many_writes_within_one_stable_epoch(self):
        """An evolution loop cannot afford a printenv per candidate."""
        session = self.verified()
        for _ in range(1000):
            session.authorise_write()
        self.assertEqual(session.epoch, 0)
        self.assertEqual(session.transport.commands.count("printenv boardid"), 1)

    def test_every_disruption_kind_revokes(self):
        for kind in sorted(gbi.DISRUPTIONS):
            with self.subTest(kind=kind):
                session = self.verified()
                session.note_disruption(kind, "detail")
                with self.assertRaises(gbi.IdentityError):
                    session.authorise_write()

    def test_disruption_increments_the_epoch(self):
        session = self.verified()
        self.assertEqual(session.epoch, 0)
        self.assertEqual(session.note_disruption("power_cycle"), 1)
        self.assertEqual(session.note_disruption("recovery"), 2)

    def test_re_verification_restores_authorisation_in_the_new_epoch(self):
        session = self.verified()
        session.note_disruption("soft_reset")
        identity = session.verify_identity()
        self.assertEqual(identity["epoch"], 1)
        self.assertEqual(session.authorise_write()["epoch"], 1)

    def test_an_identity_from_an_older_epoch_is_refused(self):
        """The epoch moves without clearing: the authorisation must still not travel."""
        session = self.verified()
        stale = dict(session.identity)
        session.epoch += 1
        session._identity = stale
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.authorise_write()
        self.assertIn("re-verify before writing", str(ctx.exception))

    def test_an_unknown_disruption_kind_is_refused(self):
        session = self.verified()
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.note_disruption("something_happened")
        self.assertIn("must be one of", str(ctx.exception))
        self.assertEqual(session.epoch, 0)

    def test_a_prompt_change_ends_the_epoch(self):
        session = self.verified()
        session.observe_prompt("Zynq>")
        self.assertEqual(session.epoch, 0)
        session.observe_prompt("Zynq>")
        self.assertEqual(session.epoch, 0)
        session.observe_prompt("zynq-uboot>")  # a different board's U-Boot
        self.assertEqual(session.epoch, 1)
        with self.assertRaises(gbi.IdentityError):
            session.authorise_write()

    def test_disruptions_are_recorded_for_the_run_log(self):
        session = self.verified()
        session.note_disruption("uart_disconnect", "CH340 brownout")
        self.assertEqual(len(session.disruptions), 1)
        entry = session.disruptions[0]
        self.assertEqual(entry["kind"], "uart_disconnect")
        self.assertEqual(entry["detail"], "CH340 brownout")
        self.assertEqual(entry["epoch_ended"], 0)


class ControlPlaneTests(unittest.TestCase):
    """Verify over U-Boot, write from Linux: the boundary an epoch alone does not cover."""

    def verified(self) -> gbi.BoardSession:
        session = gbi.BoardSession(FakeTransport(regs=good_regs()))
        session.verify_identity()
        return session

    def test_identity_records_the_control_plane_it_interrogated(self):
        self.assertEqual(self.verified().identity["control_plane"], "uboot")

    def test_a_uboot_identity_authorises_a_uboot_write(self):
        self.assertTrue(self.verified().authorise_write("uboot"))

    def test_a_uboot_identity_does_not_authorise_a_linux_write(self):
        session = self.verified()
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.authorise_write("linux")
        self.assertIn("booting Linux ends the U-Boot authorisation", str(ctx.exception))

    def test_an_unknown_control_plane_is_refused(self):
        session = self.verified()
        with self.assertRaises(gbi.IdentityError) as ctx:
            session.authorise_write("jtag")
        self.assertIn("unknown control plane", str(ctx.exception))

    def test_booting_is_a_prompt_change_and_also_ends_the_epoch(self):
        """Two independent refusals: the epoch and the control plane."""
        session = self.verified()
        session.observe_prompt("Zynq>")
        session.observe_prompt("# ")  # a Linux shell
        self.assertEqual(session.epoch, 1)
        with self.assertRaises(gbi.IdentityError):
            session.authorise_write("uboot")


class NoOverrideTests(unittest.TestCase):
    def test_no_argument_can_relax_a_requirement(self):
        source = (REPO_ROOT / "scripts/gate_board_identity.py").read_text()
        options = set(re.findall(r'ap\.add_argument\(\s*"(--[a-z0-9-]+)"', source))
        self.assertEqual(options, {"--port", "--baud", "--tier", "--out"})
        for banned in ("--force", "--allow", "--skip", "--no-verify", "--any-board"):
            self.assertNotIn(banned, options)

    def test_requirements_are_not_read_from_the_environment(self):
        source = (REPO_ROOT / "scripts/gate_board_identity.py").read_text()
        self.assertNotIn("os.environ", source)
        self.assertNotIn("getenv", source)

    def test_the_required_identity_is_a_constant(self):
        self.assertEqual(gbi.REQUIRED_BOARDID, "17A6")
        self.assertEqual(gbi.REQUIRED_ROLE, "verify")
        self.assertEqual(gbi.REQUIRED_FCLK0_MHZ, 50.0)
        self.assertEqual(gbi.ROLES_FOR_ROUTING_CLASS, frozenset({"sacrificial"}))


if __name__ == "__main__":
    unittest.main()
