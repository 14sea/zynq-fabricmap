"""The hardware CLI around the reviewed Claim B known-answer chain."""

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
import board_claimb_known_answer as driver  # noqa: E402
import board_uboot_axi as axi  # noqa: E402
import gate_claimb_board_driver as gate  # noqa: E402


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
            return {"tool": driver.TOOL_VERSION, "steps": [],
                    "verdict": "KNOWN-ANSWER ROUND PASSED"}

        with tempfile.TemporaryDirectory(prefix="claimb-driver-test-") as temp:
            out = Path(temp) / "record.json"
            with (mock.patch.object(driver.ex.PublishedCarrierAuthority, "load",
                                    return_value=authority),
                  mock.patch.object(driver.kagate.KnownAnswerAuthority, "load",
                                    return_value=known),
                  mock.patch.object(driver.cal, "phase_setup", side_effect=phase_setup),
                  mock.patch.object(driver.ident, "SerialTransport",
                                    side_effect=serial_transport),
                  mock.patch.object(driver.ident, "BoardSession", side_effect=board_session),
                  mock.patch.object(driver.axi, "same_boot", side_effect=same_boot),
                  mock.patch.object(driver, "run_known_answer_round", side_effect=round_run),
                  mock.patch.object(sys, "argv", ["board_claimb_known_answer.py",
                                                   "--port", "/dev/fake",
                                                   "--out", str(out)])):
                rc = driver.main()
            return rc, events, json.loads(out.read_text(encoding="utf-8"))

    def test_the_exact_production_prefix_precedes_the_round(self) -> None:
        rc, events, record = self.invoke()
        self.assertEqual(rc, 0)
        self.assertEqual(events, [
            "phase_setup", "serial:/dev/fake", "session", "identity:content",
            "same_boot:abc123", "round", "close"])
        self.assertTrue(record["same_boot"]["passed"])
        self.assertEqual(record["verdict"], "KNOWN-ANSWER BOARD ROUND PASSED")
        self.assertEqual(record["carrier_run"],
                         str(cal.DEFAULT_RUN.relative_to(REPO)))

    def test_an_axi_stop_keeps_the_partial_round_and_interrupt_evidence(self) -> None:
        partial = {"tool": driver.TOOL_VERSION, "steps": [
            {"step": "known_answer", "state": "stopped", "stop_reason": "bad"}]}
        failure = driver.KnownAnswerStop(
            "known_answer stopped", record=partial, cause=axi.AxiRefusal("fault"))
        rc, events, record = self.invoke(failure)
        self.assertEqual(rc, 1)
        self.assertEqual(record["verdict"], "STOP")
        self.assertEqual(record["round"], partial)
        self.assertIn("<INTERRUPT>", record["interrupt_reply"])
        self.assertLess(events.index("interrupt"), events.index("close"))

    def test_the_cli_exposes_no_authority_or_relaxation_argument(self) -> None:
        problems = gate.verify_sources(
            (REPO / "scripts/board_claimb_known_answer.py").read_text(encoding="utf-8"),
            (REPO / "scripts/board_calibrate_noop.py").read_text(encoding="utf-8"))
        self.assertEqual(problems, [])


class PartialRoundEvidenceTests(unittest.TestCase):
    def test_the_step_is_recorded_before_its_action_can_fail(self) -> None:
        authority = object.__new__(driver.ex.PublishedCarrierAuthority)
        known = object.__new__(driver.kagate.KnownAnswerAuthority)
        with (mock.patch.object(driver, "_write",
                                side_effect=[{"ok": 1}, axi.AxiRefusal("bad frame")]),
              mock.patch.object(driver, "_score", return_value={"scores": []})):
            with self.assertRaises(driver.KnownAnswerStop) as stopped:
                driver.run_known_answer_round(authority, known, object())
        self.assertIsInstance(stopped.exception.cause, axi.AxiRefusal)
        self.assertEqual(stopped.exception.record["steps"], [
            {"step": "no_op", "state": "passed", "result": {"ok": 1}},
            {"step": "known_answer", "state": "stopped",
             "stop_reason": "AxiRefusal: bad frame"},
        ])

    def test_a_digest_mismatch_keeps_the_transaction_that_proved_it(self) -> None:
        known = SimpleNamespace(payload=lambda which: b"candidate",
                                frames_sha256=lambda which: "1" * 64)
        transaction = {"readback_frames": {0x400A20: [0] * 101}}
        result = {"transaction": transaction, "sent_sha256": "2" * 64}
        with (mock.patch.object(driver.ex, "run_candidate_on_board", return_value=result),
              mock.patch.object(driver.axi, "_frames_hash", return_value="3" * 64)):
            with self.assertRaises(driver.KnownAnswerStop) as stopped:
                driver._write("candidate", object(), known, object())
        evidence = stopped.exception.record
        self.assertEqual(evidence["expected_readback_sha256"], "1" * 64)
        self.assertEqual(evidence["actual_readback_sha256"], "3" * 64)
        self.assertIs(evidence["result"], result)

    def test_a_score_mismatch_keeps_both_vectors(self) -> None:
        session = SimpleNamespace(score_last_transaction=lambda *args, **kwargs: {
            "scores": [1, 2, 3, 4, 5, 6], "mode": "train"})
        known = SimpleNamespace(
            frames_sha256=lambda which: "1" * 64,
            scores=lambda which, mode: [6, 5, 4, 3, 2, 1])
        with self.assertRaises(driver.KnownAnswerStop) as stopped:
            driver._score("candidate", "train", known, session)
        self.assertEqual(stopped.exception.record["actual"]["scores"],
                         [1, 2, 3, 4, 5, 6])
        self.assertEqual(stopped.exception.record["expected_scores"],
                         [6, 5, 4, 3, 2, 1])


class SetupContractTests(unittest.TestCase):
    def test_the_reused_loader_really_requires_an_empty_pl(self) -> None:
        with tempfile.TemporaryDirectory(prefix="claimb-setup-test-") as temp:
            bit = Path(temp) / "carrier.bit"
            bit.write_bytes(b"carrier")
            expected = __import__("hashlib").sha256(b"carrier").hexdigest()
            calls = []

            def run(argv, **kwargs):
                calls.append(argv)
                stdout = "[plmark] abc123\n" if "board_uboot_fpga_load.py" in argv[1] else ""
                return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

            with mock.patch.object(cal.subprocess, "run", side_effect=run):
                result = cal.phase_setup("/dev/fake", bit, expected)
        loader = next(argv for argv in calls if "board_uboot_fpga_load.py" in argv[1])
        self.assertEqual(loader.count("--require-unconfigured"), 1)
        self.assertEqual(result["plmark"], "abc123")


class MutationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.driver = (REPO / "scripts/board_claimb_known_answer.py").read_text(
            encoding="utf-8")
        self.setup = (REPO / "scripts/board_calibrate_noop.py").read_text(encoding="utf-8")

    def test_removing_same_boot_is_refused(self) -> None:
        anchor = '        axi.same_boot(transport, record["setup"]["plmark"])\n'
        self.assertEqual(self.driver.count(anchor), 1)
        problems = gate.verify_sources(self.driver.replace(anchor, ""), self.setup)
        self.assertTrue(any("same_boot" in problem for problem in problems), problems)

    def test_removing_require_unconfigured_is_refused(self) -> None:
        anchor = '          "--require-unconfigured"],\n'
        self.assertEqual(self.setup.count(anchor), 1)
        problems = gate.verify_sources(
            self.driver, self.setup.replace(anchor, "          ],\n"))
        self.assertTrue(any("require-unconfigured" in problem for problem in problems),
                        problems)


if __name__ == "__main__":
    unittest.main()
