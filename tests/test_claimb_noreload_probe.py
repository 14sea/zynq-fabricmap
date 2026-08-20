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
import board_uboot_axi as axi  # noqa: E402
import gate_claimb_noreload_probe as gate  # noqa: E402

MARKER = "18cd7cb81a291de5"

# What the board actually returns in each pre-registered branch.
FAULT_8 = "the engine faulted during pass 2 of envelope 0: fault_code 8 (readback)"
FAULT_12 = "the engine faulted during pass 2 of envelope 0: fault_code 12 (rbsync)"
PASSING_RESULT = {
    "which": "restore",
    "transaction": {
        "status_before": {"raw": 0x04040082, "recovery_required": True,
                          "configuration_valid": False, "rb_frames_ok": 0},
        "readback_frames": {str(0x00400A20): [0] * 101},
    },
    "readback_sha256": "0" * 64,
}


class Harness:
    """`main()` with the tty replaced. Records every board-facing thing it was asked to do."""

    def __init__(self, tmp: Path, *, marker: str = MARKER,
                 write=None, same_boot=None, identity=None) -> None:
        self.out = tmp / "record.json"
        self.marker = marker
        self.transports_opened = 0
        self.writes: list[str] = []
        self._write = write
        self._same_boot = same_boot
        self._identity = identity

    def _serial(self, port):
        self.transports_opened += 1
        return mock.MagicMock(name=f"serial({port})")

    def _instrumented(self, inner, record):
        """The real one appends command telemetry; this one only has to be JSON-safe."""
        transport = mock.MagicMock(name="instrumented")
        transport.interrupt.return_value = b"<INTERRUPT> Zynq> "
        return transport

    def _write_payload(self, which, authority, known, session):
        self.writes.append(which)
        if self._write is not None:
            return self._write(which)
        return dict(PASSING_RESULT)

    def run(self) -> tuple[int, dict]:
        session = mock.MagicMock(name="session")
        session.verify_identity.side_effect = (
            self._identity if self._identity is not None
            else (lambda tier: {"parsed": {"boardid": "17A6", "role": "carrier"}}))
        argv = ["board_claimb_noreload_noop.py", "--plmark", self.marker,
                "--out", str(self.out)]
        with (mock.patch.object(sys, "argv", argv),
              mock.patch.object(probe.ident, "SerialTransport", self._serial),
              mock.patch.object(probe.cal, "InstrumentedTransport", self._instrumented),
              mock.patch.object(probe.ident, "BoardSession", lambda transport: session),
              mock.patch.object(probe.axi, "same_boot",
                                self._same_boot if self._same_boot is not None
                                else (lambda transport, marker: None)),
              mock.patch.object(probe.known_driver, "_write", self._write_payload)):
            code = probe.main()
        record = json.loads(self.out.read_text("utf-8")) if self.out.exists() else {}
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

    def test_a1_a2_a3_are_separated_by_the_step_three_capture_not_here(self) -> None:
        """The tool must not pretend to answer what only the staging copy can answer."""
        source = (REPO_ROOT / "scripts/board_claimb_noreload_noop.py").read_text("utf-8")
        for name in ("A1", "A2", "A3", "H-PAD", "H-ADDR", "H-IDLE"):
            self.assertNotIn(f'"{name}"', source)
        self.assertIn("status_before", (
            REPO_ROOT / "scripts/board_claimb_noreload_noop.py").read_text("utf-8"))


class TheB1ConditionalNegative(unittest.TestCase):
    def test_an_unexpected_pass_is_still_a_stop(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            code, record, harness = run(tmp)
        self.assertEqual(code, 1, "a pass is a fail-closed stop, never a green light")
        self.assertEqual(record["verdict"], "STOP")
        self.assertEqual(harness.writes, ["restore"])
        self.assertEqual([s["step"] for s in record["round"]["steps"]], ["diagnostic_no_op"])
        self.assertEqual(record["round"]["steps"][0]["state"], "passed")

    def test_the_pass_verdict_is_conditional_and_never_a_refutation(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, record, _ = run(tmp)
        for text in (record["stop_reason"], record["round"]["verdict"]):
            self.assertIn("CONDITIONAL NEGATIVE", text)
            self.assertIn("did not observe its own starting content", text)
            for forbidden in ("REFUTED", "refutes", "DISPROVED", "PROVEN"):
                self.assertNotIn(forbidden, text)

    def test_the_pre_state_survives_into_the_record(self) -> None:
        """C1 is step ①'s verdict, but a reviewer must still be able to see the pre-state."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _, record, _ = run(tmp)
        status = record["round"]["steps"][0]["result"]["transaction"]["status_before"]
        self.assertEqual(status["raw"], 0x04040082)
        self.assertTrue(status["recovery_required"])
        self.assertFalse(status["configuration_valid"])


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
