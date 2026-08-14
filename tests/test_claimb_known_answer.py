"""Producer/consumer separation and the complete offline known-answer dry run."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import board_carrier_exec as ex  # noqa: E402
import board_claimb_known_answer as round_exec  # noqa: E402
import build_claimb_known_answer as producer  # noqa: E402
import gate_board_identity as ident  # noqa: E402
import gate_claimb_known_answer as consumer  # noqa: E402

ARTIFACT = REPO / "gate_runs/claimb_round1_known_answer_2026_08_14/known_answer.json"
RUN = REPO / "gate_runs/claimb_round1_carrier_2026_08_13_erratum006"


def load_fake_board():
    spec = importlib.util.spec_from_file_location(
        "claimb_axi_test_fixture", REPO / "tests/test_board_uboot_axi.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.FakeBoard


class ArtifactTests(unittest.TestCase):
    def doc(self):
        return json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_the_producer_is_deterministic_byte_for_byte(self) -> None:
        self.assertEqual(producer.canonical_bytes(producer.build()), ARTIFACT.read_bytes())

    def test_the_independent_consumer_accepts(self) -> None:
        self.assertEqual(consumer.verify_document(self.doc()), [])

    def test_the_consumer_does_not_import_the_producer(self) -> None:
        source = (REPO / "scripts/gate_claimb_known_answer.py").read_text(encoding="utf-8")
        self.assertNotIn("import build_claimb_known_answer", source)
        self.assertNotIn("from build_claimb_known_answer", source)

    def test_every_shipped_known_bad_fixture_is_refused_for_its_reason(self) -> None:
        fixtures = sorted((REPO / "tests/fixtures").glob("claimb_known_answer_bad_*.json"))
        self.assertEqual(len(fixtures), 3)
        for path in fixtures:
            with self.subTest(path=path.name):
                fixture = json.loads(path.read_text(encoding="utf-8"))
                bad = copy.deepcopy(self.doc())
                parent = bad
                for component in fixture["path"][:-1]:
                    parent = parent[component]
                parent[fixture["path"][-1]] = fixture["value"]
                problems = consumer.verify_document(bad)
                self.assertTrue(any(fixture["expected_problem"] in p for p in problems),
                                problems)

    def test_the_discriminator_is_26_nonzero_bits_over_four_frames(self) -> None:
        doc = self.doc()
        self.assertEqual(doc["selection"]["actual_init"], "0x50785CE844305DC4")
        self.assertEqual(doc["candidate"]["changed_content_bit_count"], 26)
        counts = {}
        for rec in doc["candidate"]["changed_content_bits"]:
            counts[rec["far"]] = counts.get(rec["far"], 0) + 1
        self.assertEqual(counts, {"0x00400A20": 6, "0x00400A21": 7,
                                 "0x00400A22": 2, "0x00400A23": 11})
        for frame in doc["candidate"]["touched_frames"]:
            self.assertEqual(frame["stored_ecc"], frame["recomputed_ecc"])

    def test_all_twelve_candidate_scores_and_restore_scores_are_pinned(self) -> None:
        scores = self.doc()["scores"]
        self.assertEqual(scores["candidate"]["train"], [35, 22, 20, 20, 20, 18])
        self.assertEqual(scores["candidate"]["holdout"], [23, 10, 12, 12, 12, 14])
        self.assertEqual(scores["base_restore"]["train"], [18, 22, 20, 20, 20, 18])
        self.assertEqual(scores["base_restore"]["holdout"], [14, 10, 12, 12, 12, 14])
        self.assertEqual(scores["blocked_split"],
                         {"train": [5, 25, 33, 49, 56], "holdout": [23]})
        self.assertEqual(scores["target_popcounts"], [32] * 6)


class ArmInterlockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.FakeBoard = load_fake_board()
        self.board = self.FakeBoard()
        self.board.recovery = False
        self.board.config_valid = True
        self.board.rb_frames_ok = 15
        self.board.score_queue = [[35, 22, 20, 20, 20, 18]]
        self.session = ident.BoardSession(self.board)
        self.session.verify_identity()
        frames = {far: [[0] * 101][0] for far in range(15)}
        self.session.last_transaction = {
            "epoch": self.session.epoch, "readback_frames": frames,
        }
        import board_uboot_axi as axi
        self.expected = axi._frames_hash(frames)

    def arm(self):
        return self.session.score_last_transaction(self.expected, holdout=False)

    def test_the_good_path_returns_six_scores(self) -> None:
        self.assertEqual(self.arm()["scores"], [35, 22, 20, 20, 20, 18])

    def test_a_different_readback_hash_writes_no_arm(self) -> None:
        before = len(self.board.lines)
        with self.assertRaises(Exception):
            self.session.score_last_transaction("0" * 64, holdout=False)
        self.assertFalse(any(" 0x40 1" in line for line in self.board.lines[before:]))

    def test_the_capability_cannot_be_supplied_by_a_caller(self) -> None:
        import board_uboot_axi as axi
        with self.assertRaisesRegex(Exception, "only through BoardSession"):
            axi.arm_scorer(object(), self.board, self.session.last_transaction,
                           self.expected, holdout=False)

    def test_configuration_valid_is_required(self) -> None:
        self.board.config_valid = False
        before = len(self.board.lines)
        with self.assertRaisesRegex(Exception, "configuration_valid"):
            self.arm()
        self.assertFalse(any(" 0x40 1" in line for line in self.board.lines[before:]))

    def test_recovery_required_is_required_clear(self) -> None:
        self.board.recovery = True
        before = len(self.board.lines)
        with self.assertRaisesRegex(Exception, "recovery_required"):
            self.arm()
        self.assertFalse(any(" 0x40 1" in line for line in self.board.lines[before:]))

    def test_holdout_is_the_same_door_with_the_mode_bit(self) -> None:
        self.board.score_queue = [[23, 10, 12, 12, 12, 14]]
        result = self.session.score_last_transaction(self.expected, holdout=True)
        self.assertEqual(result["mode"], "holdout")
        self.assertTrue(any(" 0xc0 1" in line for line in self.board.lines))


class WholeChainDryRun(unittest.TestCase):
    def test_noop_candidate_scores_restore_and_postbaseline(self) -> None:
        FakeBoard = load_fake_board()
        board = FakeBoard()
        board.score_queue = [
            [35, 22, 20, 20, 20, 18], [23, 10, 12, 12, 12, 14],
            [18, 22, 20, 20, 20, 18], [14, 10, 12, 12, 12, 14],
        ]
        session = ident.BoardSession(board)
        session.verify_identity()

        raw = ARTIFACT.read_bytes()
        known = consumer.KnownAnswerAuthority(
            consumer.KnownAnswerAuthority._CAPABILITY, raw)
        # PublishedCarrierAuthority has the same no-test-constructor policy; tests exercise
        # the capability layer while production load() additionally binds HEAD.
        manifest_raw = (RUN / "phenotype_manifest.json").read_bytes()
        authority = ex.PublishedCarrierAuthority(
            ex.PublishedCarrierAuthority._CAPABILITY, manifest_raw, RUN)
        record = round_exec.run_known_answer_round(authority, known, session)
        self.assertEqual(record["verdict"], "KNOWN-ANSWER ROUND PASSED")
        self.assertEqual([step["step"] for step in record["steps"]], [
            "no_op", "known_answer", "candidate_train", "candidate_holdout",
            "restore", "post_baseline_train", "post_baseline_holdout"])
        self.assertEqual(len([line for line in board.lines if " 0x40 1" in line]), 2)
        self.assertEqual(len([line for line in board.lines if " 0xc0 1" in line]), 2)


if __name__ == "__main__":
    unittest.main()
