"""The no-reload diagnostic no-op must produce a distinguishable shape for every outcome.

`docs/claimb_read_side_divergence_design.md` §8 pre-registers seven readings. Four of them are
things this entrypoint can produce (the A-family fault, B1's pass, B2's other fault code, and
C2's interlock refusals); the other two are judged elsewhere, and the tests say where, because
a reading table with a row nobody can observe is worse than no table.

Every test drives `main()` or the round with the write path stubbed. Nothing here touches a
board, and the module is written so that it could not: the refusals below all happen before a
payload exists.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_claimb_noreload_noop as probe  # noqa: E402
# Captured before any patching: `_instrumented` builds the REAL one, and reaching for it
# through the patched module attribute would call the harness back into itself.
REAL_INSTRUMENTED = probe.cal.InstrumentedTransport
import board_uboot_axi as axi  # noqa: E402
import gate_claimb_noreload_probe as gate  # noqa: E402

MARKER = "18cd7cb81a291de5"

# What the board actually returns in each pre-registered branch.
FAULT_8 = "the engine faulted during pass 2 of envelope 0: fault_code 8 (readback)"
FAULT_12 = "the engine faulted during pass 2 of envelope 0: fault_code 12 (rbsync)"

# B1 as the board really produces it. A clean second transaction completes all three
# envelopes and then the transport refuses anyway, because `fault_since_reset` is latched from
# the fault this probe attaches to. So `_write` RAISES; it does not return a result, and
# nothing structured survives except the command telemetry. Anything that stubs a returned
# transaction record is testing a path the hardware cannot take.
STICKY = ("configuration_valid is set but recovery_required is still set: a fault happened "
          "since the carrier was loaded, and what was written before it may never be scored")
CLEAN_SECOND_TRANSACTION_STATUS = 0x0407FAC4      # cv=1 fault=0 rr=1 rb_frames_ok=15
FAULTED_STATUS = 0x04040082                       # the specified fault, for comparison


def status_reply(word: int) -> bytes:
    return (f"md.l 0x{axi.STATUS:08x} 0x1\r\n"
            f"{axi.STATUS:08x}: {word:08x}    ....\r\nZynq> ").encode("ascii")


class FakeSerial:
    """A tty that answers with whatever the test queued. It counts interrupts; it never sends
    one of its own, so a non-zero count is always the entrypoint's doing."""

    def __init__(self, harness) -> None:
        self.harness = harness

    def command(self, line: str, timeout: float = 1.5) -> bytes:
        return self.harness.replies.get(line.lower(), b"Zynq> ")

    def interrupt(self) -> bytes:
        self.harness.interrupts += 1
        return b"<INTERRUPT> Zynq> "

    def close(self) -> None:
        pass


class Harness:
    """`main()` with the tty replaced, through the REAL instrumented transport.

    The telemetry path is production code here, because the reconstruction under test reads
    that telemetry: a mocked transport would let the entrypoint pass a test the board could
    never reproduce.
    """

    def __init__(self, tmp: Path, *, marker: str = MARKER, out: Path | None = None,
                 write=None, same_boot=None, identity=None) -> None:
        self.out = out if out is not None else tmp / "record.json"
        self.marker = marker
        self.transports_opened = 0
        self.interrupts = 0
        self.writes: list[str] = []
        self.replies: dict[str, bytes] = {}
        self.transport = None
        self._write = write
        self._same_boot = same_boot
        self._identity = identity

    def _serial(self, port):
        self.transports_opened += 1
        return FakeSerial(self)

    def _instrumented(self, inner, record):
        self.transport = REAL_INSTRUMENTED(inner, record)
        return self.transport

    def _write_payload(self, which, authority, known, session):
        """Stand in for the transaction: issue its STATUS read, then behave as asked."""
        self.writes.append(which)
        if self.transport is not None:
            self.transport.command(f"md.l 0x{axi.STATUS:08x} 0x1")
        if self._write is not None:
            return self._write(which)
        raise axi.AxiRefusal(STICKY)

    def _authorities(self):
        """Real types, stubbed loads.

        `PublishedCarrierAuthority.load` refuses whenever a tracked file differs from HEAD,
        which is correct for a board run and useless as a test dependency: it would make these
        results a property of the working tree rather than of the entrypoint. The round's own
        type checks still see the real classes, and that the loaders are called at all is what
        the structural gate pins.
        """
        authority = object.__new__(probe.ex.PublishedCarrierAuthority)
        authority._raw = b"stub manifest"        # manifest_sha256 is a computed property
        known = object.__new__(probe.kagate.KnownAnswerAuthority)
        return authority, known

    def run(self) -> tuple[int, dict]:
        authority, known = self._authorities()
        session = mock.MagicMock(name="session")
        session.verify_identity.side_effect = (
            self._identity if self._identity is not None
            else (lambda tier: {"parsed": {"boardid": "17A6", "role": "carrier"}}))
        self.replies.setdefault(
            f"md.l 0x{axi.STATUS:08x} 0x1", status_reply(CLEAN_SECOND_TRANSACTION_STATUS))
        argv = ["board_claimb_noreload_noop.py", "--plmark", self.marker,
                "--out", str(self.out)]
        with (mock.patch.object(sys, "argv", argv),
              mock.patch.object(probe.ex.PublishedCarrierAuthority, "load",
                                staticmethod(lambda run_dir: authority)),
              mock.patch.object(probe.kagate.KnownAnswerAuthority, "load",
                                staticmethod(lambda: known)),
              mock.patch.object(probe.ident, "SerialTransport", self._serial),
              mock.patch.object(probe.cal, "InstrumentedTransport", self._instrumented),
              mock.patch.object(probe.ident, "BoardSession", lambda transport: session),
              mock.patch.object(probe.axi, "same_boot",
                                self._same_boot if self._same_boot is not None
                                else (lambda transport, marker: None)),
              mock.patch.object(probe.known_driver, "_write", self._write_payload)):
            code = probe.main()
        try:
            record = json.loads(self.out.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            # A refusal that never claimed the destination writes nothing, and a destination
            # this run refused to touch may hold anything at all.
            record = {}
        return code, record


def run(tmp, **kwargs) -> tuple[int, dict, Harness]:
    harness = Harness(Path(tmp), **kwargs)
    code, record = harness.run()
    return code, record, harness


class TheAFamilyFault(unittest.TestCase):
    """A1/A2/A3: the engine faults. Which of the three it is, is decided by step ③."""

    def test_the_specified_fault_stops_with_its_shape_preserved(self) -> None:
        import tempfile
        def faulting(which):
            raise axi.AxiRefusal(FAULT_8)
        with tempfile.TemporaryDirectory() as tmp:
            code, record, harness = run(tmp, write=faulting)
        self.assertEqual(code, 1)
        self.assertEqual(record["verdict"], "STOP")
        self.assertIn("fault_code 8 (readback)", record["stop_reason"])
        self.assertEqual([s["step"] for s in record["round"]["steps"]], ["diagnostic_no_op"])
        self.assertEqual(record["round"]["steps"][0]["state"], "stopped")
        self.assertEqual(harness.writes, ["restore"], "exactly one payload, and only restore")

    def test_the_fault_branch_never_writes_again(self) -> None:
        import tempfile
        def faulting(which):
            raise axi.AxiRefusal(FAULT_8)
        with tempfile.TemporaryDirectory() as tmp:
            _, record, harness = run(tmp, write=faulting)
        self.assertEqual(len(harness.writes), 1)
        self.assertNotIn("verdict", record["round"], "a stopped round claims no verdict")
        self.assertEqual(record["reading"]["shape"], "NOT_A_CLEAN_SECOND_TRANSACTION")
        self.assertFalse(record["reading"]["sticky_recovery_refusal"])

    def test_a1_a2_a3_are_separated_by_the_step_three_capture_not_here(self) -> None:
        """The tool must not pretend to answer what only the staging copy can answer."""
        source = (REPO_ROOT / "scripts/board_claimb_noreload_noop.py").read_text("utf-8")
        for name in ("A1", "A2", "A3", "H-PAD", "H-ADDR", "H-IDLE"):
            self.assertNotIn(f'"{name}"', source)



class TheB1ConditionalNegative(unittest.TestCase):
    """B1 as the hardware produces it: a refusal, not a return."""

    def test_a_clean_second_transaction_is_recognised_from_the_refusal(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            code, record, harness = run(tmp)
        self.assertEqual(code, 1, "a pass is a fail-closed stop, never a green light")
        self.assertEqual(record["verdict"], "STOP")
        self.assertEqual(harness.writes, ["restore"])
        self.assertEqual(record["reading"]["shape"], "CLEAN_SECOND_TRANSACTION")
        self.assertTrue(record["reading"]["sticky_recovery_refusal"])
        self.assertIn("recovery_required is still set", record["raised"])

    def test_the_four_fields_are_reconstructed_from_the_telemetry(self) -> None:
        """15/15, configuration_valid, no fault, sticky recovery — recovered, not lost."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, record, _ = run(tmp)
        status = record["reading"]["final_status"]
        self.assertEqual(status["rb_frames_ok"], 15)
        self.assertTrue(status["configuration_valid"])
        self.assertFalse(status["fault"])
        self.assertTrue(status["recovery_required"])
        self.assertEqual(record["reading"]["matches_a_clean_second_transaction"],
                         {"rb_frames_ok": True, "configuration_valid": True,
                          "fault": True, "recovery_required": True})
        self.assertIn("nothing was re-read", record["reading"]["reconstructed_from"])

    def test_the_reconstruction_reads_the_run_s_own_recorded_reply(self) -> None:
        """Not a constant: change what the board said, and the reconstruction changes."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            harness = Harness(Path(tmp))
            harness.replies[f"md.l 0x{axi.STATUS:08x} 0x1"] = status_reply(FAULTED_STATUS)
            code, record = harness.run()
        self.assertEqual(record["reading"]["final_status"]["raw"], FAULTED_STATUS)
        self.assertEqual(record["reading"]["shape"], "NOT_A_CLEAN_SECOND_TRANSACTION")
        self.assertIsNone(record["reading"]["verdict"])
        self.assertNotIn("CONDITIONAL", record["stop_reason"])

    def test_a_sticky_refusal_without_the_status_is_not_promoted(self) -> None:
        """The refusal text alone must not be enough; the status has to agree."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            harness = Harness(Path(tmp))
            harness.replies[f"md.l 0x{axi.STATUS:08x} 0x1"] = b"Zynq> "
            code, record = harness.run()
        self.assertTrue(record["reading"]["sticky_recovery_refusal"])
        self.assertIsNone(record["reading"]["final_status"])
        self.assertEqual(record["reading"]["shape"], "NOT_A_CLEAN_SECOND_TRANSACTION")

    def test_the_pass_verdict_is_conditional_and_never_a_refutation(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, record, _ = run(tmp)
        for text in (record["stop_reason"], record["reading"]["verdict"]):
            self.assertIn("CONDITIONAL NEGATIVE", text)
            self.assertIn("did not observe its own starting content", text)
            for forbidden in ("REFUTED", "refutes", "DISPROVED", "PROVEN"):
                self.assertNotIn(forbidden, text)


class TheB2OtherFault(unittest.TestCase):
    def test_another_fault_code_is_recorded_as_itself(self) -> None:
        import tempfile
        def faulting(which):
            raise axi.AxiRefusal(FAULT_12)
        with tempfile.TemporaryDirectory() as tmp:
            code, record, harness = run(tmp, write=faulting)
        self.assertEqual(code, 1)
        self.assertIn("fault_code 12 (rbsync)", record["stop_reason"])
        self.assertNotIn("fault_code 8", record["stop_reason"])
        self.assertEqual(harness.writes, ["restore"])


class TheC2Interlocks(unittest.TestCase):
    """Every refusal must cost zero transactions, and the marker one must cost zero contact."""

    def test_a_malformed_marker_refuses_before_the_tty_is_opened(self) -> None:
        import tempfile
        for bad in ("", "nope", "18CD7CB81A291DE5", "18cd7cb81a291de", "18cd7cb81a291de55"):
            with tempfile.TemporaryDirectory() as tmp:
                code, record, harness = run(tmp, marker=bad)
            self.assertEqual(code, 1, bad)
            self.assertEqual(harness.transports_opened, 0, f"{bad!r} opened the tty")
            self.assertEqual(harness.writes, [], bad)
            self.assertIn("--plmark", record["stop_reason"])
            self.assertNotIn("same_boot", record)

    def test_a_marker_mismatch_costs_zero_transactions(self) -> None:
        import tempfile
        def refusing(transport, marker):
            raise axi.AxiRefusal(
                f"`plmark` is 0000000000000000, the load set {marker}: this is a different "
                "boot")
        with tempfile.TemporaryDirectory() as tmp:
            code, record, harness = run(tmp, same_boot=refusing)
        self.assertEqual(code, 1)
        self.assertEqual(harness.writes, [], "a different boot must not be written to")
        self.assertFalse(record["same_boot"]["passed"])
        self.assertEqual(record["same_boot"]["expected_plmark"], MARKER)
        self.assertNotIn("round", record)

    def test_an_identity_refusal_costs_zero_transactions(self) -> None:
        import tempfile
        def refusing(tier):
            raise RuntimeError("boardid is '4203', this run is preregistered for '17A6'")
        with tempfile.TemporaryDirectory() as tmp:
            code, record, harness = run(tmp, identity=refusing)
        self.assertEqual(code, 1)
        self.assertEqual(harness.writes, [])
        self.assertNotIn("same_boot", record)
        self.assertNotIn("round", record)
        self.assertIn("17A6", record["stop_reason"])


class TheEntrypointSendsNoConsoleActionOfItsOwn(unittest.TestCase):
    """1.0.0 sent a Ctrl-C out of every AxiRefusal. By then every command had already got a
    prompt back, so it was an extra board action that no telemetry recorded."""

    def _interrupts_on(self, **kwargs) -> int:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, _, harness = run(tmp, **kwargs)
        return harness.interrupts

    def test_no_stop_path_interrupts_the_console(self) -> None:
        def fault_8(which):
            raise axi.AxiRefusal(FAULT_8)

        def fault_12(which):
            raise axi.AxiRefusal(FAULT_12)

        def refusing_boot(transport, marker):
            raise axi.AxiRefusal("`plmark` is 0000000000000000: this is a different boot")

        def refusing_identity(tier):
            raise RuntimeError("boardid is '4203'")

        for name, kwargs in (
                ("the clean second transaction", {}),
                ("the specified fault", {"write": fault_8}),
                ("another fault code", {"write": fault_12}),
                ("a marker mismatch", {"same_boot": refusing_boot}),
                ("an identity refusal", {"identity": refusing_identity}),
                ("a malformed marker", {"marker": "nope"})):
            self.assertEqual(self._interrupts_on(**kwargs), 0, name)

    def test_the_record_says_so_and_the_source_cannot_take_it_back(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, record, _ = run(tmp)
        self.assertIn("no console action of its own", record["no_interrupt"])
        source = (REPO_ROOT / "scripts/board_claimb_noreload_noop.py").read_text("utf-8")
        self.assertNotIn(".interrupt(", source)


class TheEvidenceDestinationIsClaimedFirst(unittest.TestCase):
    """1.0.0 replaced an existing record, and only discovered an unwritable destination after
    the board had been touched."""

    def test_an_existing_record_is_never_overwritten(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "record.json"
            original = b'{"this": "is someone else\'s evidence"}\n'
            out.write_bytes(original)
            harness = Harness(Path(tmp), out=out)
            code, _ = harness.run()
            self.assertEqual(code, 1)
            self.assertEqual(out.read_bytes(), original, "the old bytes must be untouched")
            self.assertEqual(harness.transports_opened, 0)
            self.assertEqual(harness.writes, [])

    def test_a_stale_reservation_stops_the_run(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "record.json"
            partial = out.with_name(out.name + ".part")
            partial.write_bytes(b"half a record from a killed run")
            harness = Harness(Path(tmp), out=out)
            code, _ = harness.run()
            self.assertEqual(code, 1)
            self.assertEqual(harness.transports_opened, 0)
            self.assertEqual(harness.writes, [])
            self.assertFalse(out.exists())
            self.assertEqual(partial.read_bytes(), b"half a record from a killed run")

    def test_an_unwritable_destination_stops_before_board_contact(self) -> None:
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            locked = Path(tmp) / "locked"
            locked.mkdir()
            os.chmod(locked, 0o500)
            try:
                harness = Harness(Path(tmp), out=locked / "record.json")
                code, _ = harness.run()
                self.assertEqual(code, 1)
                self.assertEqual(harness.transports_opened, 0)
                self.assertEqual(harness.writes, [])
            finally:
                os.chmod(locked, 0o700)

    def test_a_normal_run_leaves_no_partial_behind(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "record.json"
            harness = Harness(Path(tmp), out=out)
            harness.run()
            self.assertTrue(out.exists())
            self.assertFalse(out.with_name(out.name + ".part").exists())


class TheStructuralGateHolds(unittest.TestCase):
    def test_the_shipped_driver_is_accepted(self) -> None:
        source = (REPO_ROOT / "scripts/board_claimb_noreload_noop.py").read_text("utf-8")
        self.assertEqual(gate.verify_source(source), [])

    def test_the_cli_offers_nothing_but_the_three_permitted_options(self) -> None:
        source = (REPO_ROOT / "scripts/board_claimb_noreload_noop.py").read_text("utf-8")
        for forbidden in ("--force", "--retry", "--continue", "--score", "--arm",
                          "--holdout", "--skip", "--allow", "--reload", "--run-dir"):
            self.assertNotIn(forbidden, source)

    def test_the_module_cannot_name_the_reload_or_evaluation_paths(self) -> None:
        source = (REPO_ROOT / "scripts/board_claimb_noreload_noop.py").read_text("utf-8")
        self.assertEqual([n for n in gate.FORBIDDEN_REFERENCES if n in source], [])

    def test_the_round_is_reached_from_exactly_one_place(self) -> None:
        import ast
        source = (REPO_ROOT / "scripts/board_claimb_noreload_noop.py").read_text("utf-8")
        calls = [node for node in ast.walk(ast.parse(source))
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == "run_noreload_noop"]
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
