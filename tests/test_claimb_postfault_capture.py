"""The fixed post-fault capture CLI stops after two writes and cannot evaluate them."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import board_calibrate_noop as cal  # noqa: E402
import board_claimb_postfault_capture as capture  # noqa: E402
import board_uboot_axi as axi  # noqa: E402
import gate_claimb_postfault_capture as gate  # noqa: E402


class ScoreObservingSession:
    def __init__(self) -> None:
        self.score_calls = 0

    def score_last_transaction(self, *args, **kwargs):
        self.score_calls += 1
        return {"scores": []}


def authorities():
    return (object.__new__(capture.ex.PublishedCarrierAuthority),
            object.__new__(capture.kagate.KnownAnswerAuthority))


class RoundTests(unittest.TestCase):
    def test_the_tool_has_its_own_evidence_identity(self) -> None:
        self.assertEqual(capture.TOOL_VERSION,
                         "board_claimb_postfault_capture.py/1.0.0")

    def test_an_unexpected_pass_stops_after_two_steps_without_evaluation(self) -> None:
        authority, known = authorities()
        session = ScoreObservingSession()
        with mock.patch.object(capture.known_driver, "_write",
                               side_effect=[{"which": "restore"},
                                            {"which": "candidate"}]) as write:
            record = capture.run_postfault_capture(authority, known, session)
        self.assertEqual([(step["step"], step["state"]) for step in record["steps"]],
                         [("no_op", "passed"), ("known_answer", "passed")])
        self.assertEqual(write.call_count, 2)
        self.assertEqual(session.score_calls, 0)
        self.assertIn("FAULT STATE WAS NOT CREATED", record["verdict"])

    def test_a_fault_keeps_the_failed_step_and_child_evidence(self) -> None:
        authority, known = authorities()
        child = {"which": "candidate", "raw": "fault evidence"}
        failure = capture.known_driver.KnownAnswerStop(
            "candidate stopped", record=child, cause=axi.AxiRefusal("F_READBACK"))
        with mock.patch.object(capture.known_driver, "_write",
                               side_effect=[{"which": "restore"}, failure]):
            with self.assertRaises(capture.CaptureStop) as stopped:
                capture.run_postfault_capture(authority, known, ScoreObservingSession())
        self.assertIsInstance(stopped.exception.cause, axi.AxiRefusal)
        self.assertEqual(stopped.exception.record["steps"], [
            {"step": "no_op", "state": "passed", "result": {"which": "restore"}},
            {"step": "known_answer", "state": "stopped",
             "stop_reason": "KnownAnswerStop: candidate stopped",
             "failure_evidence": child},
        ])

    def test_the_round_rejects_unreviewed_authorities_before_a_write(self) -> None:
        with mock.patch.object(capture.known_driver, "_write") as write:
            with self.assertRaises(capture.CaptureStop):
                capture.run_postfault_capture(object(), object(), object())
        write.assert_not_called()


class FakeInnerTransport:
    def __init__(self, events: list[str]):
        self.events = events

    def command(self, line: str, timeout: float = 1.5) -> bytes:
        self.events.append(f"command:{line}")
        return b"Zynq> "

    def interrupt(self, timeout: float = 2.0) -> bytes:
        self.events.append("interrupt")
        return b"<INTERRUPT>\r\nZynq> "

    def close(self) -> None:
        self.events.append("close")


class FakeSession:
    def __init__(self, transport, events: list[str]):
        self.transport = transport
        self.events = events

    def verify_identity(self, tier: str) -> dict:
        self.events.append(f"identity:{tier}")
        return {"parsed": {"boardid": "17A6", "role": "verify"}}


class DriverTests(unittest.TestCase):
    def invoke(self, round_effect=None):
        events: list[str] = []
        authority = SimpleNamespace(manifest_sha256="a" * 64)
        known = object()
        setup = {"plmark": "abc123", "carrier_sha256": "b" * 64, "steps": []}

        def phase_setup(*args):
            events.append("phase_setup")
            return setup

        def serial_transport(port):
            events.append(f"serial:{port}")
            return FakeInnerTransport(events)

        def board_session(transport):
            events.append("session")
            return FakeSession(transport, events)

        def same_boot(transport, marker):
            events.append(f"same_boot:{marker}")

        def round_run(carrier, artifact, session):
            events.append("round")
            if isinstance(round_effect, BaseException):
                raise round_effect
            return {"tool": capture.TOOL_VERSION, "steps": [
                {"step": "no_op", "state": "passed"},
                {"step": "known_answer", "state": "passed"},
            ], "verdict": "KNOWN-ANSWER PASSED; REQUESTED FAULT STATE WAS NOT CREATED"}

        with tempfile.TemporaryDirectory(prefix="claimb-postfault-driver-test-") as temp:
            out = Path(temp) / "record.json"
            with (mock.patch.object(capture.ex.PublishedCarrierAuthority, "load",
                                    return_value=authority),
                  mock.patch.object(capture.kagate.KnownAnswerAuthority, "load",
                                    return_value=known),
                  mock.patch.object(capture.cal, "phase_setup", side_effect=phase_setup),
                  mock.patch.object(capture.ident, "SerialTransport",
                                    side_effect=serial_transport),
                  mock.patch.object(capture.ident, "BoardSession", side_effect=board_session),
                  mock.patch.object(capture.axi, "same_boot", side_effect=same_boot),
                  mock.patch.object(capture, "run_postfault_capture", side_effect=round_run),
                  mock.patch.object(sys, "argv", ["board_claimb_postfault_capture.py",
                                                   "--port", "/dev/fake",
                                                   "--out", str(out)])):
                rc = capture.main()
            self.assertFalse(out.with_name(out.name + ".part").exists())
            return rc, events, json.loads(out.read_text(encoding="utf-8"))

    def test_the_exact_production_prefix_precedes_the_two_step_capture(self) -> None:
        rc, events, record = self.invoke()
        self.assertEqual(rc, 1, "an unexpected pass is a stopped capture, not success")
        self.assertEqual(events, [
            "phase_setup", "serial:/dev/fake", "session", "identity:content",
            "same_boot:abc123", "round", "close"])
        self.assertTrue(record["same_boot"]["passed"])
        self.assertEqual(record["verdict"], "STOP")
        self.assertEqual([step["step"] for step in record["round"]["steps"]],
                         ["no_op", "known_answer"])
        self.assertNotIn("interrupt", events)

    def test_an_axi_fault_keeps_the_round_and_interrupt_evidence(self) -> None:
        partial = {"tool": capture.TOOL_VERSION, "steps": [
            {"step": "no_op", "state": "passed"},
            {"step": "known_answer", "state": "stopped", "stop_reason": "fault"},
        ]}
        failure = capture.CaptureStop(
            "known_answer stopped", record=partial, cause=axi.AxiRefusal("fault"))
        rc, events, record = self.invoke(failure)
        self.assertEqual(rc, 1)
        self.assertEqual(record["round"], partial)
        self.assertIn("<INTERRUPT>", record["interrupt_reply"])
        self.assertLess(events.index("interrupt"), events.index("close"))

    def test_the_cli_has_only_logistics_arguments_and_all_interlocks(self) -> None:
        problems = gate.verify_sources(
            (REPO / "scripts/board_claimb_postfault_capture.py").read_text("utf-8"),
            (REPO / "scripts/board_calibrate_noop.py").read_text("utf-8"))
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
