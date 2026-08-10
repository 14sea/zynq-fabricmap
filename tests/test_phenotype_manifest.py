"""The write envelope is derived from the device, or it is refused.

The rule this file exists to defend is preregistration §6 item 2 and item 10: within the
target and flush frames, everything except the whitelisted addresses belongs to the pinned
base — *including our own logic* — and a flush frame is authority, not a writable frame.

The sharpest case here is `test_flush_is_not_far_plus_one`. "The neighbour frame" reads
like FAR+1, and on this device that is wrong for two of the three groups: their targets end
at the last minor of a column, so the FAR auto-increment continues into the **next column**
(`0x00400A23` -> `0x00400A80`). A builder that computed FAR+1 would have pinned
`0x00400A24`, which does not exist, and the error would only have surfaced on hardware.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402
import build_phenotype_manifest as bpm  # noqa: E402

MAP_PATH = REPO_ROOT / "maps/clb_lut_init_v1.local_map.json"
BASE_BIT = REPO_ROOT / "build/specimen_locked/spec_0000000000000000.bit"


class GroupingTests(unittest.TestCase):
    """Pure, so they run on a tree with no bitstreams at all."""

    def test_maximal_runs(self):
        self.assertEqual(
            bpm.consecutive_groups([5, 1, 2, 3, 9, 10]), [[1, 2, 3], [5], [9, 10]]
        )

    def test_a_single_far_is_its_own_group(self):
        self.assertEqual(bpm.consecutive_groups([7]), [[7]])

    def test_successor_skips_pad_frames(self):
        self.assertEqual(bpm.successor_in_device_order(1, [0, 1, None, None, 2]), 2)

    def test_successor_refuses_an_unknown_far(self):
        with self.assertRaises(bpm.EnvelopeError) as ctx:
            bpm.successor_in_device_order(99, [0, 1, 2])
        self.assertIn("not a frame this device carries", str(ctx.exception))

    def test_successor_refuses_the_last_frame(self):
        with self.assertRaises(bpm.EnvelopeError) as ctx:
            bpm.successor_in_device_order(2, [0, 1, 2])
        self.assertIn("nothing can flush it", str(ctx.exception))


class DeviceOrderTests(unittest.TestCase):
    """The finding that would otherwise have been discovered on hardware."""

    @classmethod
    def setUpClass(cls):
        cls.sequence = bf.device_frame_sequence(bf.device_layout())

    def test_flush_is_not_far_plus_one(self):
        # 0x00400A23 is major 20 minor 35, the last frame of its column.
        self.assertNotIn(0x00400A24, self.sequence)
        self.assertEqual(
            bpm.successor_in_device_order(0x00400A23, self.sequence), 0x00400A80
        )

    def test_the_middle_group_does_have_an_in_column_neighbour(self):
        self.assertEqual(
            bpm.successor_in_device_order(0x00400C1D, self.sequence), 0x00400C1E
        )

    def test_the_third_group_also_crosses_a_column(self):
        self.assertNotIn(0x00400C24, self.sequence)
        self.assertEqual(
            bpm.successor_in_device_order(0x00400C23, self.sequence), 0x00400C80
        )

    def test_cross_column_flush_is_a_different_major(self):
        for last, flush in ((0x00400A23, 0x00400A80), (0x00400C23, 0x00400C80)):
            self.assertNotEqual(
                bf.far_fields(last)["major"], bf.far_fields(flush)["major"]
            )


class BaseEccGateTests(unittest.TestCase):
    """Every real base frame verifies, so this rule needs a wrong record to be visible."""

    def test_accepts_consistent_frames(self):
        bpm.check_base_ecc([{"far": "0x1", "ecc_consistent": True}])

    def test_refuses_an_inconsistent_frame(self):
        with self.assertRaises(bpm.EnvelopeError) as ctx:
            bpm.check_base_ecc(
                [{"far": "0x1", "ecc_consistent": True},
                 {"far": "0x2", "ecc_consistent": False}]
            )
        self.assertIn("0x2", str(ctx.exception))
        self.assertIn("not a clean authority", str(ctx.exception))


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BASE_BIT.exists():
            raise unittest.SkipTest(f"{BASE_BIT} absent (build/ is gitignored)")
        cls.doc = bpm.build_manifest(MAP_PATH, BASE_BIT, "probe", None)

    def test_envelope_arithmetic(self):
        env = self.doc["write_envelope"]
        self.assertEqual(env["target_far_count"], 12)
        self.assertEqual(env["flush_far_count"], 3)
        self.assertEqual(len(env["envelopes"]), 3)
        for e in env["envelopes"]:
            self.assertEqual(len(e["target_fars"]), 4)
            self.assertEqual(e["payload_words"], 5 * bf.FRAME_WORDS)  # 505
            self.assertEqual(e["total_words"], 536)
        self.assertEqual(env["total_words"], 1608)
        self.assertEqual(env["total_bytes"], 6432)

    def test_two_of_three_flushes_leave_the_column(self):
        same = [e["flush_is_same_column"] for e in self.doc["write_envelope"]["envelopes"]]
        self.assertEqual(same.count(False), 2)

    def test_every_frame_is_pinned_whole(self):
        self.assertEqual(len(self.doc["frames"]), 15)
        for record in self.doc["frames"]:
            self.assertEqual(len(record["words"]), bf.FRAME_WORDS)
            self.assertRegex(record["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(record["ecc_consistent"])

    def test_roles_are_disjoint(self):
        targets = {r["far"] for r in self.doc["frames"] if r["role"] == "target"}
        flushes = {r["far"] for r in self.doc["frames"] if r["role"] == "flush"}
        self.assertEqual(len(targets), 12)
        self.assertEqual(len(flushes), 3)
        self.assertEqual(targets & flushes, set())

    def test_whitelist_totals_the_map(self):
        self.assertEqual(self.doc["ownership"]["writable_addresses"], 292)

    def test_clock_requirement_is_pinned(self):
        self.assertEqual(self.doc["clock"]["fclk0_mhz"], 50.0)
        self.assertIn("80 MHz on a 4203", self.doc["clock"]["rule"])

    def test_map_and_base_are_hash_pinned(self):
        self.assertRegex(self.doc["local_map"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(self.doc["base_bitstream"]["sha256"], r"^[0-9a-f]{64}$")


class RefusalTests(unittest.TestCase):
    """Hand it wrong inputs; a correct one cannot show a rule exists."""

    def setUp(self):
        if not BASE_BIT.exists():
            self.skipTest(f"{BASE_BIT} absent")
        # Inside the repo on purpose: the builder refuses to pin a path it cannot
        # express repo-relative, so an out-of-tree fixture would test that rule instead
        # of the one each case is about.
        self.tmp = tempfile.TemporaryDirectory(dir=REPO_ROOT)
        self.addCleanup(self.tmp.cleanup)

    def write_map(self, mutate) -> Path:
        doc = json.loads(MAP_PATH.read_text())
        mutate(doc)
        path = Path(self.tmp.name) / "map.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def test_refuses_a_foreign_document(self):
        path = self.write_map(lambda d: d.__setitem__("schema", "not_a_map"))
        with self.assertRaises(bpm.EnvelopeError) as ctx:
            bpm.build_manifest(path, BASE_BIT, "x", None)
        self.assertIn("not a local_map", str(ctx.exception))

    def test_refuses_a_target_frame_the_base_does_not_carry(self):
        def mutate(doc):
            doc["index"]["by_far"]["0x00FFFFFF"] = ["0x00FFFFFF/51/0"]

        path = self.write_map(mutate)
        with self.assertRaises(bpm.EnvelopeError) as ctx:
            bpm.build_manifest(path, BASE_BIT, "x", None)
        self.assertIn("not in", str(ctx.exception))

    def test_refuses_a_whitelist_address_outside_the_target_frames(self):
        def mutate(doc):
            entry = dict(doc["universe"]["addresses"][0])
            entry.update(far="0x00400A1F", key="0x00400A1F/51/0")
            doc["universe"]["addresses"].append(entry)

        path = self.write_map(mutate)
        with self.assertRaises(bpm.EnvelopeError) as ctx:
            bpm.build_manifest(path, BASE_BIT, "x", None)
        self.assertIn("outside the target frames", str(ctx.exception))

    def test_refuses_when_a_flush_would_be_a_target(self):
        """0x00400A80 is group 1's flush, and it is not consecutive with 0x00400A23.

        Adding 0x00400C1E instead would NOT reach this rule: it is consecutive with
        0x00400C1D, so the run simply grows and the flush moves to 0x00400C1F. The
        distinction is the reason this case names a cross-column frame.
        """

        def mutate(doc):
            doc["index"]["by_far"]["0x00400A80"] = ["0x00400A80/51/0"]
            entry = dict(doc["universe"]["addresses"][0])
            entry.update(far="0x00400A80", word=51, bit=0, key="0x00400A80/51/0")
            doc["universe"]["addresses"].append(entry)

        path = self.write_map(mutate)
        with self.assertRaises(bpm.EnvelopeError) as ctx:
            bpm.build_manifest(path, BASE_BIT, "x", None)
        self.assertIn("do not partition", str(ctx.exception))


    def test_refuses_a_map_outside_the_repository(self):
        """Was a ValueError from Path.relative_to — a crash, not a judgement."""
        outside = Path(tempfile.mkdtemp()) / "map.json"
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        outside.write_text(MAP_PATH.read_text(), encoding="utf-8")
        with self.assertRaises(bpm.EnvelopeError) as ctx:
            bpm.build_manifest(outside, BASE_BIT, "x", None)
        self.assertIn("outside the repository", str(ctx.exception))

    def test_refuses_a_base_bitstream_outside_the_repository(self):
        with self.assertRaises(bpm.EnvelopeError) as ctx:
            bpm.build_manifest(MAP_PATH, Path("/etc/hostname"), "x", None)
        self.assertIn("outside the repository", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
