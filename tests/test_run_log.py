"""The run log records enough to dispute the result, and refuses to launder a failure.

Two rules carry the weight, and both exist because the tempting shortcut is to record a
single tidy number:

* **candidate hash and readback hash are separate fields.** §6 item 8 scores fitness only
  when the readback equals the candidate; a log with one hash for both makes that check
  unfalsifiable after the run, because the record would agree with itself by construction.
* **`scored` is checked, not believed.** A caller that marks an entry scored while the gate
  refused it, or while the readback differs, is refused at record time *and* the finished
  log reports the same thing through `problems()` — so a log written by a modified runner
  still fails a reader's check.

`test_a_candidate_written_in_an_unauthorised_epoch_is_a_problem` is the one that ties this
file to the identity interlock: an epoch with no verification behind it is a write that
happened without a live authorisation, and a reader must be able to see that without
trusting whoever wrote the log.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_log as rl  # noqa: E402

MAP_PATH = REPO_ROOT / "maps/clb_lut_init_v1.local_map.json"


def fake_map() -> dict:
    return {"map_id": "m1", "universe": {"address_count": 292}}


def fake_manifest() -> dict:
    return {
        "phenotype_id": "p1",
        "base_bitstream": {"sha256": "ab" * 32},
        "write_envelope": {"target_far_count": 12, "flush_far_count": 3},
    }


def fake_identity(epoch: int = 0) -> dict:
    return {
        "epoch": epoch,
        "parsed": {"boardid": "17A6", "role": "verify"},
        "transport": {"resolved_port": "/dev/ttyUSB0"},
        "raw_replies": {"printenv boardid": "boardid=17A6"},
    }


def frames(seed: int = 0) -> dict[int, list[int]]:
    return {0x00400A20: [seed] * 101, 0x00400A21: [seed + 1] * 101}


def envelopes() -> list[list[int]]:
    return [[0xAA995566, 0x20000000], [0x30002001, 0x00400A20]]


PASS = {"writable": True, "buckets": {}, "findings": []}
FAIL = {"writable": False, "buckets": {"target_frame": 1}, "findings": [{"kind": "x"}]}


def new_log(arm: str = "map_guided") -> rl.RunLog:
    return rl.RunLog(
        run_id="r1",
        arm=arm,
        local_map=fake_map(),
        phenotype_manifest=fake_manifest(),
        budget={"evaluations": 10, "derived_from": "measured rate"},
        seed_schedule=[1, 2, 3],
        preregistration={"path": "docs/claimb_preregistration.md", "sha256": "cd" * 32},
    )


class HashTests(unittest.TestCase):
    def test_frames_hash_is_order_independent(self):
        a = {0x1: [1] * 101, 0x2: [2] * 101}
        b = {0x2: [2] * 101, 0x1: [1] * 101}
        self.assertEqual(rl.frames_hash(a), rl.frames_hash(b))

    def test_frames_hash_separates_far_from_content(self):
        """The same content at different addresses is a different candidate.

        Swapping content between two FARs is NOT the case that shows this: the
        concatenation differs either way. Only identical content at different addresses
        collides when the FAR is left out of the digest.
        """
        a = {0x00400A20: [1] * 101, 0x00400A21: [2] * 101}
        b = {0x00400C20: [1] * 101, 0x00400C21: [2] * 101}
        self.assertNotEqual(rl.frames_hash(a), rl.frames_hash(b))

    def test_sequence_hash_is_order_dependent(self):
        env = envelopes()
        self.assertNotEqual(rl.sequence_hash(env), rl.sequence_hash(env[::-1]))

    def test_a_single_word_changes_the_sequence_hash(self):
        env = envelopes()
        other = [list(env[0]), list(env[1])]
        other[1][1] ^= 1
        self.assertNotEqual(rl.sequence_hash(env), rl.sequence_hash(other))


class ArmTests(unittest.TestCase):
    def test_both_arms_are_expressible(self):
        for arm in ("map_guided", "random_safe"):
            self.assertEqual(new_log(arm).doc["arm"], arm)

    def test_an_unknown_arm_is_refused(self):
        with self.assertRaises(rl.RunLogError):
            new_log("whatever_we_ran")


class ScoringGuardTests(unittest.TestCase):
    def setUp(self):
        self.log = new_log()
        self.log.record_identity(fake_identity(0))

    def entry(self, **kwargs):
        base = dict(
            index=0, seed=1, epoch=0,
            candidate_frames=frames(), envelopes=envelopes(),
            gate_verdict=PASS, readback_frames=frames(),
            fitness=1.0, scored=True,
        )
        base.update(kwargs)
        return self.log.record_candidate(**base)

    def test_a_matching_readback_scores(self):
        entry = self.entry()
        self.assertTrue(entry["scored"])
        self.assertTrue(entry["readback_matches"])
        self.assertEqual(entry["candidate_sha256"], entry["readback_sha256"])

    def test_scoring_without_a_readback_is_refused(self):
        with self.assertRaises(rl.RunLogError) as ctx:
            self.entry(readback_frames=None)
        self.assertIn("only when the readback equals", str(ctx.exception))

    def test_scoring_a_differing_readback_is_refused(self):
        with self.assertRaises(rl.RunLogError) as ctx:
            self.entry(readback_frames=frames(seed=99))
        self.assertIn("differs from the candidate", str(ctx.exception))

    def test_scoring_a_refused_candidate_is_refused(self):
        with self.assertRaises(rl.RunLogError) as ctx:
            self.entry(gate_verdict=FAIL)
        self.assertIn("the gate refused it", str(ctx.exception))

    def test_scoring_without_a_fitness_is_refused(self):
        with self.assertRaises(rl.RunLogError):
            self.entry(fitness=None)

    def test_an_unscored_readback_mismatch_records_the_mismatch(self):
        """Written, read back wrong, not scored — the log must still say it did not match.

        With `scored=True` the guard raises before this field is ever set, so only the
        unscored path can show that `readback_matches` reports a real comparison rather
        than a constant.
        """
        entry = self.entry(readback_frames=frames(seed=99), scored=False, fitness=None)
        self.assertFalse(entry["readback_matches"])
        self.assertNotEqual(entry["candidate_sha256"], entry["readback_sha256"])
        doc = self.log.finish()
        self.assertEqual(doc["totals"]["readback_mismatches"], 1)

    def test_an_unscored_failure_is_recorded_not_rejected(self):
        """A refused candidate is data, not an error: safety metrics are the point."""
        entry = self.entry(gate_verdict=FAIL, scored=False, fitness=None,
                           readback_frames=None)
        self.assertFalse(entry["scored"])
        self.assertFalse(entry["gate"]["writable"])
        self.assertEqual(entry["gate"]["buckets"], {"target_frame": 1})


class ReaderChecksTests(unittest.TestCase):
    """`problems()` must catch what a modified runner could still have written."""

    def setUp(self):
        self.log = new_log()
        self.log.record_identity(fake_identity(0))
        self.log.pin_artifact("local_map", MAP_PATH)
        self.log.pin_artifact("phenotype_manifest", MAP_PATH)

    def add(self, **kwargs):
        base = dict(
            index=0, seed=1, epoch=0, candidate_frames=frames(),
            envelopes=envelopes(), gate_verdict=PASS,
            readback_frames=frames(), fitness=1.0, scored=True,
        )
        base.update(kwargs)
        return self.log.record_candidate(**base)

    def test_a_clean_run_has_no_problems(self):
        self.add()
        self.assertEqual(self.log.problems(), [])

    def test_an_unpinned_artifact_is_a_problem(self):
        log = new_log()
        log.record_identity(fake_identity(0))
        self.assertIn("local_map was never pinned", log.problems())

    def test_a_candidate_written_in_an_unauthorised_epoch_is_a_problem(self):
        self.add(epoch=3)
        problems = self.log.problems()
        self.assertTrue(any("no identity record opened" in p for p in problems), problems)

    def test_a_forged_scored_entry_is_caught_by_the_reader(self):
        """Bypass record_candidate entirely, as a modified runner would."""
        self.add()
        self.log.doc["candidates"].append(
            {
                "index": 1, "seed": 2, "arm": "map_guided", "epoch": 0,
                "candidate_sha256": "aa" * 32, "readback_sha256": "bb" * 32,
                "readback_matches": False,
                "gate": {"writable": True, "buckets": {}, "finding_count": 0},
                "scored": True, "fitness": 9.9, "notes": "",
            }
        )
        problems = self.log.problems()
        self.assertTrue(any("readback does not match" in p for p in problems), problems)

    def test_exceeding_the_budget_is_a_problem(self):
        for index in range(11):  # budget is 10
            self.add(index=index)
        self.assertTrue(any("exceed the budget" in p for p in self.log.problems()))


class LifecycleTests(unittest.TestCase):
    def test_disruptions_and_epochs_are_totalled(self):
        log = new_log()
        log.pin_artifact("local_map", MAP_PATH)
        log.pin_artifact("phenotype_manifest", MAP_PATH)
        log.record_identity(fake_identity(0))
        log.record_disruption({"epoch_ended": 0, "kind": "power_cycle", "detail": ""})
        log.record_identity(fake_identity(1))
        log.record_candidate(
            index=0, seed=1, epoch=1, candidate_frames=frames(),
            envelopes=envelopes(), gate_verdict=PASS, readback_frames=frames(),
            fitness=0.5, scored=True,
        )
        doc = log.finish()
        self.assertEqual(doc["totals"]["disruptions"], 1)
        self.assertEqual(doc["totals"]["epochs"], 2)
        self.assertEqual(doc["totals"]["scored"], 1)
        self.assertEqual(doc["problems"], [])

    def test_raw_identity_replies_survive_into_the_log(self):
        log = new_log()
        log.record_identity(fake_identity(0))
        self.assertIn(
            "boardid=17A6", log.doc["identity_records"][0]["raw_replies"]["printenv boardid"]
        )

    def test_written_log_round_trips(self):
        import json

        log = new_log()
        log.record_identity(fake_identity(0))
        log.pin_artifact("local_map", MAP_PATH)
        log.pin_artifact("phenotype_manifest", MAP_PATH)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            log.write(path)
            doc = json.loads(path.read_text())
        self.assertEqual(doc["schema"], "claimb_run_log")
        self.assertEqual(doc["schema_version"], "1.0.0")
        self.assertRegex(doc["local_map"]["sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
