"""B2 maps: the operator's view, the oracle rendering, and the control renderings
(docs/b2_architecture.md §5) — invariants and the fact that B1's map equals the oracle."""
from __future__ import annotations

import collections
import copy
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402

TRUTH = bm.truth_mapping()
SELF = bmaps.load_self_map()
ORACLE = bmaps.oracle_map(TRUTH)
TRAIN = bl.train_vectors()


def relations(doc):
    return sorted((e["relation"]["lut_index"], e["relation"]["init_index"]) for e in bmaps._claims(doc))


class Documents(unittest.TestCase):
    def test_self_map_is_the_committed_b1_map(self):
        self.assertEqual(SELF["cartographer"], "carto-v1")
        self.assertEqual(len(SELF["entries"]), bc.N)
        self.assertEqual(bmaps.schema_findings(SELF), [])

    def test_self_map_equals_the_oracle_in_every_relation(self):
        self.assertEqual(bmaps.relations_equal(SELF, ORACLE), (bc.N, bc.N))

    def test_oracle_validates_and_carries_no_polarity_or_lut_key(self):
        self.assertEqual(bmaps.schema_findings(ORACLE), [])
        self.assertNotIn("polarity", str(ORACLE))
        self.assertNotIn("SLICE", str(ORACLE))

    def test_schema_validation_refuses_a_bad_document(self):
        bad = copy.deepcopy(SELF)
        bad["entries"][0]["relation"]["init_index"] = 64
        self.assertTrue(bmaps.schema_findings(bad))
        with self.assertRaises(ValueError):
            bmaps.MapView(bad, TRAIN)


class Controls(unittest.TestCase):
    def test_shuffled_keeps_the_multiset_and_moves_most_relations(self):
        d = bmaps.shuffled_map(SELF, 3)
        self.assertEqual(relations(d), relations(SELF))
        agree, n = bmaps.relations_equal(SELF, d)
        self.assertEqual(n, bc.N)
        self.assertLess(agree, 20)
        self.assertEqual(bmaps.schema_findings(d), [])
        self.assertEqual(bmaps.sha256_of(d), bmaps.sha256_of(bmaps.shuffled_map(SELF, 3)))
        self.assertNotEqual(bmaps.sha256_of(d), bmaps.sha256_of(bmaps.shuffled_map(SELF, 4)))

    def test_lut_shuffled_keeps_lut_membership_and_destroys_columns(self):
        d = bmaps.lut_shuffled_map(SELF, 3)
        for a, b in zip(SELF["entries"], d["entries"]):
            self.assertEqual(a["relation"]["lut_index"], b["relation"]["lut_index"])
        self.assertEqual(relations(d), relations(SELF))
        agree, _ = bmaps.relations_equal(SELF, d)
        self.assertLess(agree, 20)

    def test_degraded_resets_the_fraction(self):
        for q, want in ((0.25, 73), (0.5, 146), (0.75, 219)):
            d = bmaps.degraded_map(SELF, q, 3)
            self.assertEqual(bmaps.schema_findings(d), [])
            states = collections.Counter(e["state"] for e in d["entries"])
            self.assertEqual(states["unknown"], want)
            self.assertEqual(states["confirmed"], bc.N - want)
            agree, _ = bmaps.relations_equal(SELF, d)
            self.assertEqual(agree, bc.N - want)

    def test_original_document_untouched(self):
        before = bmaps.sha256_of(SELF)
        bmaps.shuffled_map(SELF, 1); bmaps.lut_shuffled_map(SELF, 1); bmaps.degraded_map(SELF, 0.5, 1)
        self.assertEqual(bmaps.sha256_of(SELF), before)


class View(unittest.TestCase):
    def test_columns_are_train_only_and_correct_under_the_oracle(self):
        view = bmaps.MapView(ORACLE, TRAIN)
        self.assertEqual(set(view.column_keys), set(TRAIN))
        self.assertEqual(view.mapped_bits(), 183)
        for v, bits in view.columns.items():
            for i in bits:
                self.assertEqual(TRUTH["mapping"][i][1], v)
            self.assertEqual(bits, sorted(bits))
        self.assertEqual(sorted(collections.Counter(len(b) for b in view.columns.values()).items()),
                         [(2, 1), (3, 9), (4, 8), (5, 10), (6, 12)])

    def test_no_map_is_empty(self):
        view = bmaps.MapView(None, TRAIN)
        self.assertEqual(view.column_keys, [])
        self.assertEqual(view.mapped_bits(), 0)
        self.assertIsNone(view.sha256)

    def test_unknown_entries_are_not_consulted(self):
        d = bmaps.degraded_map(SELF, 0.5, 9)
        view = bmaps.MapView(d, TRAIN)
        known = {e["genome_bit"] for e in bmaps._claims(d)}
        for bits in view.columns.values():
            self.assertTrue(set(bits) <= known)


if __name__ == "__main__":
    unittest.main()
