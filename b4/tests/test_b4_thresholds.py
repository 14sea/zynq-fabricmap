"""b4/host/b4_thresholds.py — the machine table of section 9's fixed thresholds, pinned FIELD BY FIELD to the text of
docs/b4_architecture.md (the owner's ruling on unit 2b-4a, section 3.4): every pinned text must appear in the named row or
paragraph of the document, and the table's numbers must be the document's. A change to either side fails here. No skip."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_k10 as k10  # noqa: E402
import b4_protocol as bp  # noqa: E402
import b4_thresholds as th  # noqa: E402
from b4_ff_hypothesis import HYPOTHESIS_SHA256  # noqa: E402


def rows_of_section_9(doc: str) -> dict:
    """The K rows of the section-9 table by id, the grid / B* paragraph, section 9.2's text, section 8's control-generator block, the intro."""
    i9 = doc.index("\n## 9. The discriminability gate")
    i91 = doc.index("\n### 9.1 ")
    i92 = doc.index("\n### 9.2 ")
    i93 = doc.index("\n### 9.3 ")
    i10 = doc.index("\n## 10. ")
    i8 = doc.index("\n## 8. Controls")
    i71 = doc.index("\n### 7.1 ")
    sec9 = doc[i9:i91]
    out = {"9-intro": sec9[:sec9.index("| id | criterion |")], "9.2": doc[i92:i93], "9.3": doc[i93:i10], "8": doc[i8:i9], "7.1": doc[i71:i8]}
    for m in re.finditer(r"^\| (K\d+) [^|]*\|(.*)$", sec9, re.M):
        out[m.group(1)] = m.group(0)
    out["K-grid"] = sec9[sec9.index("**The budget grid and `B*`.**"):]
    return out


class ThePins(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = (R / th.ARCHITECTURE_REL).read_text(encoding="utf-8")
        cls.rows = rows_of_section_9(cls.doc)

    def test_every_pinned_text_is_in_its_row(self):
        for path, row, text in th.PINS:
            self.assertIn(row, self.rows, f"{path}: the row {row} exists")
            self.assertIn(text, self.rows[row], f"{path}: {text!r} is in row {row}")
            th.lookup(path)                                   # the table path exists

    def test_the_numbers_are_the_document_s(self):
        T = th.THRESHOLDS
        self.assertEqual(T["grid"], [8, 16, 24, 32, 48, 64, 96, 128, 192, 256]); self.assertEqual(T["B_max"], 256)
        self.assertEqual((T["K1"]["omega_best_p95_lt"], T["K1"]["percentile"]), (64, 95))
        self.assertEqual((T["K2"]["x_minus_r_nonrejection_min"], T["K2"]["bootstrap_experiments"], T["K2"]["alpha"], T["K2"]["bootstrap_seed"]), (0.90, 1000, 0.05, 7))
        self.assertEqual((T["K3"]["ratio_max"], T["K3"]["alpha"]), (0.10, 0.05))
        self.assertEqual((T["K4"]["omega_median_max"], T["K4"]["f_over_omega_min"]), (57.6, 0.50))
        self.assertEqual(T["K4"]["omega_median_max"], 0.90 * 64)
        self.assertEqual((T["K5"]["cohen_d_min"], T["K5"]["power_min"], T["K5"]["bootstrap_experiments"], T["K5"]["n_min"], T["K5"]["cap_search_evaluations"]), (0.5, 0.90, 1000, 8, 4000))
        self.assertEqual((T["K6"]["S_gate"], T["K6"]["N_min"]), (200, 8))
        self.assertEqual((T["K7"]["recomputation_mismatches"], T["K7"]["o_prefix_median_not_unknown_min"], T["K7"]["of_addresses"]), (0, 11, 21))
        self.assertEqual((T["K9"]["seeds_with_all_seven_positive_controls_min"], T["K9"]["median_coverage_per_semantic_min"], T["K9"]["semantics"]), (0.90, 0.50, 7))
        self.assertEqual((T["K10"]["tau"], T["K10"]["interacting_seeds_over_S_min"], T["K10"]["pairs_per_background"], T["K10"]["backgrounds"], T["K10"]["background_salt"]), (2, 0.50, 210, 2, 0x4C0A4E55))
        self.assertEqual((T["K10"]["tau"], T["K10"]["background_salt"]), (k10.TAU, k10.SALT), "the driver's constants are the table's")
        self.assertEqual(T["anchor"]["hypothesis_sha256"], HYPOTHESIS_SHA256)
        self.assertEqual((T["anchor"]["gate_label"], T["anchor"]["exploration_label"]), ("b4-gate-2", "b4-sim-4"), "protocol v0.2.0: the next labels; the retired and consumed ones never")
        self.assertEqual(sorted(T["anchor"]["retired_exploration_labels"]), ["b4-sim-1", "b4-sim-2"]); self.assertEqual(sorted(T["anchor"]["consumed_labels"]), ["b4-gate-1", "b4-sim-3"])
        import b4_seeds as bs
        self.assertEqual((set(T["anchor"]["retired_exploration_labels"]), T["anchor"]["exploration_label"]), (set(bs.RETIRED_LABELS), bs.EXPLORATION_LABEL), "the table and the loader agree")
        self.assertEqual((set(T["anchor"]["consumed_labels"]), T["anchor"]["gate_label"]), (set(bs.CONSUMED_LABELS), bs.GATE_LABEL))
        self.assertNotIn(bs.EXPLORATION_LABEL, bs.RETIRED_LABELS | bs.CONSUMED_LABELS); self.assertNotIn(bs.GATE_LABEL, bs.RETIRED_LABELS | bs.CONSUMED_LABELS)
        self.assertEqual(T["delta2_F_shift"], 21)
        self.assertEqual((T["task"]["version"], T["task"]["target_salt"], T["task"]["setup_observations_per_pair"]), ("task-v0.2", 0x54415247, 2))
        self.assertEqual((T["gonogo"]["S"], T["gonogo"]["B_go"], T["gonogo"]["alpha_go"], T["gonogo"]["k9_conditional_medians_min"]), (32, 64, 0.20, 0.50))
        self.assertEqual(T["K9"]["judged_estimand"], "conditional_sr_driven")
        import b4_landscape as bl
        self.assertEqual((bl.TASK_VERSION, bl.SALT_TARGET), (T["task"]["version"], T["task"]["target_salt"]), "the generator's constants are the table's")

    def test_the_document_version_is_informational_outside_the_table_and_outside_the_method_digest(self):
        """The new pin / identity contract (the owner's choice 6, 2026-10-20): the document's first line carries the revision the table was written
        against (an informational constant, not a table field); the table's source text carries no version; the thresholds digest and the
        protocol identity's digest do not move when the revision text moves."""
        self.assertEqual(th.ARCHITECTURE_REVISION, "v0.2.0")
        self.assertIn(f"(DRAFT {th.ARCHITECTURE_REVISION},", self.doc.splitlines()[0])
        self.assertNotIn("v0.", th.THRESHOLDS["source"]); self.assertNotIn("v0.", th.ARCHITECTURE_SECTION)
        self.assertNotIn("architecture_revision", th.THRESHOLDS)
        self.assertEqual(bp.thresholds_sha256(dict(th.THRESHOLDS, source="x")), bp.thresholds_sha256(th.THRESHOLDS))
        p = bp.identity(); q = dict(p, architecture_revision="v0.3.0")
        self.assertEqual(bp.protocol_sha256(p), bp.protocol_sha256(q)); self.assertEqual(bp.compare(q, p), [])
        self.assertEqual(p["architecture_revision"], th.ARCHITECTURE_REVISION)

    def test_a_changed_number_would_be_caught(self):
        rows = dict(self.rows)
        rows["K6"] = rows["K6"].replace("**S = 200**", "**S = 199**")
        with self.assertRaises(AssertionError):
            for path, row, text in th.PINS:
                self.assertIn(text, rows[row])


if __name__ == "__main__":
    unittest.main()
