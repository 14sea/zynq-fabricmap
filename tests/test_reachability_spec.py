"""The reachability spec is frozen before the measurement, and carries no target.

The rule it exists to enforce: a target may not be chosen after the reachable space is
known. So the strongest case here is `test_the_spec_contains_no_target` — the spec fixes a
family, a draw rule, an unreachability test, a redraw cap and a stop-on-exhaustion rule,
and the target itself is *derived* by applying those to the measured space.

The second thing under test is that the per-LUT masks are the certified universe and not a
transcription: they come from `local_map`'s `by_lut` index, so a map change moves them and
a typo cannot.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from math import comb
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_reachability_spec as brs  # noqa: E402

MAP_PATH = REPO_ROOT / "maps/clb_lut_init_v1.local_map.json"
SPEC_PATH = REPO_ROOT / "specs/reachability_spec_v1.json"


class PermutationTests(unittest.TestCase):
    def test_is_a_permutation(self):
        order = brs.lcg_permutation(brs.VECTOR_SEED, 64)
        self.assertEqual(sorted(order), list(range(64)))

    def test_is_deterministic(self):
        self.assertEqual(
            brs.lcg_permutation(0x1234, 64), brs.lcg_permutation(0x1234, 64)
        )

    def test_a_different_seed_gives_a_different_order(self):
        self.assertNotEqual(
            brs.lcg_permutation(0x1234, 64), brs.lcg_permutation(0x1235, 64)
        )

    def test_it_is_not_the_identity(self):
        self.assertNotEqual(brs.lcg_permutation(brs.VECTOR_SEED, 64), list(range(64)))


class SpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = brs.build_spec(MAP_PATH)

    def test_masks_come_from_the_map(self):
        local_map = json.loads(MAP_PATH.read_text())
        by_lut = {
            lut: sorted(b["init_index"] for b in bits)
            for lut, bits in local_map["index"]["by_lut"].items()
        }
        for lut in self.spec["phenotype"]["luts"]:
            self.assertEqual(lut["mutable_indices"], by_lut[lut["feature_prefix"]])

    def test_mutable_and_fixed_partition_64(self):
        for lut in self.spec["phenotype"]["luts"]:
            self.assertEqual(lut["mutable_count"] + lut["fixed_count"], 64)
            self.assertEqual(
                set(lut["mutable_indices"]) & set(lut["fixed_indices"]), set()
            )

    def test_totals_match_the_certified_universe(self):
        self.assertEqual(self.spec["phenotype"]["total_mutable_positions"], 292)
        self.assertEqual(self.spec["phenotype"]["total_fixed_positions"], 92)

    def test_the_mask_integer_agrees_with_the_indices(self):
        for lut in self.spec["phenotype"]["luts"]:
            mask = int(lut["mutable_mask"].split("h")[1], 16)
            self.assertEqual(
                sorted(i for i in range(64) if mask >> i & 1), lut["mutable_indices"]
            )

    def test_fixed_values_come_from_the_base_init(self):
        for lut in self.spec["phenotype"]["luts"]:
            base = int(lut["base_init"].split("h")[1], 16)
            for index, value in lut["fixed_values"].items():
                self.assertEqual(value, (base >> int(index)) & 1)

    def test_lock_pins_are_pinned_on_every_lut(self):
        for lut in self.spec["phenotype"]["luts"]:
            self.assertEqual(lut["lock_pins"], brs.LOCK_PINS)

    def test_split_is_disjoint_and_complete(self):
        split = self.spec["vectors"]["split"]
        self.assertEqual(set(split["train"]) & set(split["holdout"]), set())
        self.assertEqual(sorted(split["train"] + split["holdout"]), list(range(64)))

    def test_the_spec_contains_no_target(self):
        """A family and a rule, never a chosen function."""
        family = self.spec["target_family"]
        for key in ("family", "draw_rule", "replacement_rule", "exhaustion_rule"):
            self.assertIn(key, family)
        blob = json.dumps(self.spec)
        # the only mention of a target truth table is the REPORT's field name
        self.assertNotIn('"target_truth_table":', blob)
        self.assertIn("per_lut[].target_truth_table", self.spec["output"]["required_fields"])

    def test_the_stop_rule_forbids_widening(self):
        rule = self.spec["target_family"]["exhaustion_rule"]
        for phrase in ("does not widen", "lower the ceiling", "change the seed"):
            self.assertIn(phrase, rule)

    def test_frozen_before_measurement_is_asserted(self):
        self.assertIs(self.spec["frozen_before_measurement"], True)

    def test_the_map_is_hash_pinned(self):
        pin = self.spec["provenance"]["local_map"]
        self.assertRegex(pin["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(pin["address_count"], 292)


class CeilingArithmeticTests(unittest.TestCase):
    """The threshold was chosen from combinatorics, so the combinatorics must hold."""

    @classmethod
    def setUpClass(cls):
        cls.spec = brs.build_spec(MAP_PATH)

    @staticmethod
    def p_accept(fixed: int, max_blocked: int, ones: int = 32, n: int = 64) -> float:
        return sum(
            comb(fixed, k) * comb(n - fixed, ones - k) for k in range(max_blocked + 1)
        ) / comb(n, ones)

    def test_the_binding_lut_is_the_one_named(self):
        worst = max(self.spec["phenotype"]["luts"], key=lambda l: l["fixed_count"])
        self.assertEqual(worst["site"], "SLICE_X8Y25")
        self.assertEqual(worst["bel"], "D6LUT")
        self.assertEqual(worst["fixed_count"], 20)

    def test_the_recorded_probabilities_are_reproducible(self):
        recorded = self.spec["ceiling"]["acceptance_arithmetic"]["p_accept_per_draw"]
        for ceiling, expected in (("ceiling_60", 4), ("ceiling_58", 6), ("ceiling_56", 8)):
            self.assertAlmostEqual(
                self.p_accept(20, expected), recorded[ceiling], places=4
            )

    def test_the_rejected_threshold_really_would_have_exhausted(self):
        """60 was the first draft; the point is that it fails by construction."""
        p = self.p_accept(20, 64 - 60)
        self.assertGreater((1 - p) ** brs.REDRAW_CAP, 0.5)

    def test_the_chosen_threshold_does_not(self):
        p = self.p_accept(20, 64 - brs.CEILING_MIN)
        self.assertLess((1 - p) ** brs.REDRAW_CAP, 0.01)

    def test_exhaustion_remains_possible(self):
        """A stop condition that can never fire is a formality, not a gate."""
        p = self.p_accept(20, 64 - brs.CEILING_MIN)
        self.assertGreater((1 - p) ** brs.REDRAW_CAP, 0.0)


class RefusalTests(unittest.TestCase):
    def write_map(self, mutate) -> Path:
        doc = json.loads(MAP_PATH.read_text())
        mutate(doc)
        tmp = tempfile.TemporaryDirectory(dir=REPO_ROOT)
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "map.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def test_refuses_a_foreign_document(self):
        path = self.write_map(lambda d: d.__setitem__("schema", "not_a_map"))
        with self.assertRaises(brs.SpecError):
            brs.build_spec(path)

    def test_refuses_a_map_missing_one_of_the_six_luts(self):
        def mutate(doc):
            doc["index"]["by_lut"].pop("CLBLM_L.SLICEM_X0.DLUT")

        path = self.write_map(mutate)
        with self.assertRaises(brs.SpecError) as ctx:
            brs.build_spec(path)
        self.assertIn("does not carry", str(ctx.exception))

    def test_refuses_an_out_of_range_init_index(self):
        def mutate(doc):
            doc["index"]["by_lut"]["CLBLL_L.SLICEL_X0.ALUT"][0]["init_index"] = 99

        path = self.write_map(mutate)
        with self.assertRaises(brs.SpecError) as ctx:
            brs.build_spec(path)
        self.assertIn("out of range", str(ctx.exception))


class CommittedSpecTests(unittest.TestCase):
    def setUp(self):
        if not SPEC_PATH.exists():
            self.skipTest(f"{SPEC_PATH} absent")

    def test_the_committed_spec_matches_a_fresh_derivation(self):
        self.assertEqual(
            json.loads(SPEC_PATH.read_text()), brs.build_spec(MAP_PATH)
        )


if __name__ == "__main__":
    unittest.main()
