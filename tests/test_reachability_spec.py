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


def synthetic_lut(site, bel, fixed_indices):
    """A LUT record with an arbitrary mask, for exercising the predicate's SCOPE."""
    return {
        "site": site,
        "bel": bel,
        "feature_prefix": f"SYN.{site}.{bel}",
        "lock_pins": brs.LOCK_PINS,
        "base_init": "64'h0000000000000000",
        "mutable_indices": [i for i in range(64) if i not in fixed_indices],
        "fixed_indices": sorted(fixed_indices),
        "fixed_count": len(fixed_indices),
    }


class SelectionScopeTests(unittest.TestCase):
    """review v4's blocker: the predicate is PER LUT, never a conjunction over the six.

    A test that repeats the worst LUT's marginal probability cannot tell the two readings
    apart — it never executes the draw/replacement rule. These do, through the same
    `select_target_for_lut` the report producer will call.
    """

    SEED = 0xB1B0

    def find_discriminating_draw(self, lut_a, lut_b):
        """A k accepted for A and refused for B — the case the scopes disagree on."""
        for k in range(4096):
            entries = brs.target_vector(self.SEED, k)
            ca = brs.attainable_ceiling(entries, lut_a["fixed_indices"], 0)
            cb = brs.attainable_ceiling(entries, lut_b["fixed_indices"], 0)
            if ca >= brs.CEILING_MIN > cb:
                return k, ca, cb
        self.fail("no discriminating draw found in 4096 tries")

    def test_a_target_is_judged_by_its_own_lut_only(self):
        lut_a = synthetic_lut("SYN_A", "A6LUT", list(range(8)))       # 8 fixed: easy
        lut_b = synthetic_lut("SYN_B", "D6LUT", list(range(28)))      # 28 fixed: hard
        k, ca, cb = self.find_discriminating_draw(lut_a, lut_b)
        self.assertGreaterEqual(ca, brs.CEILING_MIN)
        self.assertLess(cb, brs.CEILING_MIN)

        result = brs.select_target_for_lut(lut_a, self.SEED, k)
        self.assertFalse(result["exhausted"])
        self.assertEqual(result["draw_index"], k, "the draw must be accepted for its own LUT")
        self.assertEqual(result["attainable_ceiling"], ca)

    def test_the_converse_the_other_lut_refuses_the_same_draw(self):
        lut_a = synthetic_lut("SYN_A", "A6LUT", list(range(8)))
        lut_b = synthetic_lut("SYN_B", "D6LUT", list(range(28)))
        k, _, _ = self.find_discriminating_draw(lut_a, lut_b)
        result = brs.select_target_for_lut(lut_b, self.SEED, k, cap=1)
        self.assertTrue(result["exhausted"])
        self.assertEqual([d["draw_index"] for d in result["discarded_draws"]], [k])

    def test_k_advances_across_rejected_draws_so_no_two_luts_share_a_target(self):
        luts = [synthetic_lut(f"S{i}", "A6LUT", list(range(20))) for i in range(4)]
        outcome = brs.select_targets(luts, self.SEED)
        indices = [a["draw_index"] for a in outcome["assignments"]]
        self.assertEqual(len(set(indices)), len(indices))
        self.assertEqual(indices, sorted(indices))
        for previous, current in zip(outcome["assignments"], outcome["assignments"][1:]):
            self.assertGreater(current["draw_index"], previous["draw_index"])

    def test_the_stop_path_fires_through_the_same_function(self):
        """An impossible mask: 40 fixed positions cannot leave a ceiling of 58."""
        impossible = synthetic_lut("SYN_X", "A6LUT", list(range(40)))
        result = brs.select_target_for_lut(impossible, self.SEED, 0)
        self.assertTrue(result["exhausted"])
        self.assertIsNone(result["draw_index"])
        self.assertEqual(len(result["discarded_draws"]), brs.REDRAW_CAP)

    def test_selection_stops_at_the_first_exhausted_lut(self):
        luts = [
            synthetic_lut("SYN_OK", "A6LUT", list(range(8))),
            synthetic_lut("SYN_BAD", "D6LUT", list(range(40))),
            synthetic_lut("SYN_NEVER", "A6LUT", list(range(8))),
        ]
        outcome = brs.select_targets(luts, self.SEED)
        self.assertTrue(outcome["exhausted"])
        self.assertFalse(outcome["complete"])
        self.assertEqual(len(outcome["assignments"]), 2, "must not continue past exhaustion")

    def test_the_real_six_complete_under_the_per_lut_scope(self):
        spec = brs.build_spec(MAP_PATH)
        outcome = brs.select_targets(spec["phenotype"]["luts"], int(spec["vectors"]["seed"], 16))
        self.assertTrue(outcome["complete"])
        self.assertFalse(outcome["exhausted"])
        for a in outcome["assignments"]:
            self.assertGreaterEqual(a["attainable_ceiling"], brs.CEILING_MIN)

    def test_the_conjunction_reading_would_have_exhausted(self):
        """Pins the erratum: the literal six-LUT reading finds nothing in 256 draws."""
        spec = brs.build_spec(MAP_PATH)
        luts = spec["phenotype"]["luts"]
        seed = int(spec["vectors"]["seed"], 16)
        passing = [
            k
            for k in range(brs.REDRAW_CAP)
            if all(
                brs.attainable_ceiling(
                    brs.target_vector(seed, k),
                    l["fixed_indices"],
                    int(l["base_init"].split("h")[1], 16),
                )
                >= brs.CEILING_MIN
                for l in luts
            )
        ]
        self.assertEqual(passing, [], "the conjunction reading must find nothing here")


class TargetVectorTests(unittest.TestCase):
    def test_every_target_is_balanced(self):
        for k in range(32):
            self.assertEqual(sum(brs.target_vector(0xB1B0, k)), 32)

    def test_the_known_answer_is_reproduced(self):
        """A literal an independent implementation must match — not a self-comparison."""
        entries = brs.target_vector(0x0001, 0)
        self.assertEqual(f"64'h{brs.target_init(entries):016X}", "64'h197787B4D6152EC4")
        self.assertEqual(entries[:8], [0, 0, 1, 0, 0, 0, 1, 1])

    def test_the_spec_carries_that_known_answer(self):
        spec = brs.build_spec(MAP_PATH)
        known = spec["target_family"]["bit_vector_convention"]["known_answer"]
        self.assertEqual(known["init"], "64'h197787B4D6152EC4")
        self.assertEqual(known["ones"], 32)

    def test_init_integer_uses_entry_v_shifted_by_v(self):
        entries = [0] * 64
        entries[3] = 1
        entries[40] = 1
        self.assertEqual(brs.target_init(entries), (1 << 3) | (1 << 40))

    def test_blocked_positions_are_the_disagreeing_fixed_ones(self):
        entries = [0] * 64
        entries[5] = 1
        self.assertEqual(brs.blocked_positions(entries, [4, 5, 6], 0), [5])
        self.assertEqual(brs.attainable_ceiling(entries, [4, 5, 6], 0), 63)

    def test_a_different_k_gives_a_different_target(self):
        self.assertNotEqual(brs.target_vector(0xB1B0, 0), brs.target_vector(0xB1B0, 1))


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


class VerifierIndependenceTests(unittest.TestCase):
    """review v5: the spec must not tell a verifier to call the producer.

    The first fix for v4 said the producer "and any independent verifier" call these
    functions — the reverse of this repo's writer/verifier contract. A defect in the draw,
    the ceiling, k advancement or the exhaustion path would then produce the report AND
    certify it. These cases pin the wording so an edit cannot quietly restore it.
    """

    @classmethod
    def setUpClass(cls):
        cls.spec = brs.build_spec(MAP_PATH)

    def test_the_spec_requires_an_independent_reimplementation(self):
        rule = self.spec["target_family"]["verifier_independence"]
        self.assertIn("MUST reimplement", rule)
        self.assertIn("MUST NOT import", rule)
        self.assertIn("build_reachability_spec", rule)

    def test_producer_and_verifier_roles_are_named_separately(self):
        family = self.spec["target_family"]
        self.assertIn("producer_implementation", family)
        self.assertIn("verifier_independence", family)
        self.assertNotIn("selection_implemented_by", family)

    def test_no_field_tells_a_verifier_to_call_the_producer(self):
        blob = json.dumps(self.spec)
        for phrase in (
            "and any independent verifier call",
            "any independent verifier call this function",
        ):
            self.assertNotIn(phrase, blob)

    def test_the_known_answer_is_named_as_the_rendezvous(self):
        cross = self.spec["target_family"]["bit_vector_convention"]["cross_check"]
        self.assertIn("known_answer", cross)
        self.assertIn("independent", cross)

    def test_the_source_comment_matches_the_spec(self):
        source = (REPO_ROOT / "scripts/build_reachability_spec.py").read_text()
        self.assertIn("An independent verifier must NOT", source)


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
