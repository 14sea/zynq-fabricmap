"""Tests for the decidability census (`scripts/diag_safety_decidability.py`).

The census is a diagnostic, not a gate — and not the preregistered Claim B safety
comparison (`docs/zynq7_decidability_census.md` §0) — but its two load-bearing pieces — how decode
groups are formed, and what counts as "decidable" — are exactly the places where a
wrong answer would look like a clean result.  Each test below is written so that it
FAILS if the piece under test loses its discriminating power.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import diag_safety_decidability as D  # noqa: E402


# A synthetic tile type: two features share bits despite unrelated names, and two
# features share a name prefix despite sharing no bit.  Grouping by name would get
# both cases wrong — `docs/mux_groups.md`.
SYNTHETIC = {
    "T.MUX.A": [(0, 0, 1), (0, 1, 0)],
    "T.OTHER.B": [(0, 0, 0), (0, 1, 1)],
    "T.MUX.FAR": [(9, 9, 1)],
    "T.LONE": [(5, 5, 1)],
}


class DecodeGroups(unittest.TestCase):
    def test_groups_follow_bits_not_names(self):
        groups, bit_users = D.decode_groups(SYNTHETIC)
        by_member = {tuple(sorted(m)): bits for m, bits in groups}
        self.assertIn(("T.MUX.A", "T.OTHER.B"), by_member,
                      "features sharing bit 0_00 must land in one group")
        self.assertIn(("T.MUX.FAR",), by_member,
                      "a shared name prefix must NOT create a group")
        self.assertIn(("T.LONE",), by_member)
        self.assertEqual(len(groups), 3)
        self.assertEqual(sorted(bit_users[(0, 0)]), ["T.MUX.A", "T.OTHER.B"])

    def test_bits_of_a_group_are_the_union(self):
        groups, _ = D.decode_groups(SYNTHETIC)
        bits = {tuple(sorted(m)): b for m, b in groups}[("T.MUX.A", "T.OTHER.B")]
        self.assertEqual(bits, [(0, 0), (0, 1)])


class Classify(unittest.TestCase):
    MEMBERS = ["T.MUX.A", "T.OTHER.B"]

    def test_all_zero(self):
        self.assertEqual(
            D.classify({(0, 0): 0, (0, 1): 0}, self.MEMBERS, SYNTHETIC), "ALLZERO")

    def test_decoded(self):
        self.assertEqual(
            D.classify({(0, 0): 1, (0, 1): 0}, self.MEMBERS, SYNTHETIC), "DECODED")

    def test_undecodable_is_not_reported_as_safe(self):
        # bits are set, no pattern matches: the database cannot say what this does.
        self.assertEqual(
            D.classify({(0, 0): 1, (0, 1): 1}, self.MEMBERS, SYNTHETIC), "UNDECODABLE")

    def test_multi_is_detected(self):
        # A guard that cannot see a two-source state would silently report the safe
        # answer for the one case this census exists to find.
        both = {"X.M.P": [(0, 0, 1)], "X.M.Q": [(0, 1, 1)]}
        self.assertEqual(
            D.classify({(0, 0): 1, (0, 1): 1}, list(both), both), "MULTI")
        self.assertEqual(
            D.classify({(0, 0): 1, (0, 1): 0}, list(both), both), "DECODED")


class MapUniverseCheck(unittest.TestCase):
    """`semantic_bits_decidable` must be able to say NO."""

    def _check(self, addresses, feats):
        groups, bit_users = D.decode_groups(feats)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.local_map.json"
            path.write_text(json.dumps({"universe": {"addresses": addresses}}))
            return D.check_map(path, {"T": feats}, {"T": bit_users})

    def test_width_one_unshared_universe_passes(self):
        feats = {"T.S.ALUT.INIT[0]": [(1, 1, 1)], "T.S.ALUT.INIT[1]": [(1, 2, 1)]}
        out = self._check([{"feature": f} for f in feats], feats)
        self.assertTrue(out["semantic_bits_decidable"])
        self.assertEqual(out["single_bit_and_unshared"], 2)

    def test_the_flag_names_semantic_bits_only(self):
        """A serialized candidate also carries ECC collateral; the flag must not imply it."""
        feats = {"T.S.ALUT.INIT[0]": [(1, 1, 1)]}
        out = self._check([{"feature": "T.S.ALUT.INIT[0]"}], feats)
        self.assertIn("semantic_bits_decidable", out)
        self.assertNotIn("decidable_by_construction", out,
                         "the old name claimed more than the check establishes")

    def test_a_mux_member_fails_the_check(self):
        feats = {"T.AFFMUX.AX": [(3, 0, 0), (3, 1, 1), (3, 2, 0), (3, 3, 0)],
                 "T.AFFMUX.CY": [(3, 0, 1), (3, 1, 0), (3, 2, 1), (3, 3, 0)]}
        out = self._check([{"feature": "T.AFFMUX.AX"}], feats)
        self.assertFalse(out["semantic_bits_decidable"],
                         "a multi-bit mux member is not decidable by construction")
        self.assertEqual(out["feature_widths"], {"4": 1})

    def test_a_shared_bit_fails_the_check(self):
        feats = {"T.A": [(2, 2, 1)], "T.B": [(2, 2, 1)]}
        out = self._check([{"feature": "T.A"}], feats)
        self.assertFalse(out["semantic_bits_decidable"])
        self.assertEqual(out["shared_with_another_feature"], 1)

    def test_a_feature_absent_from_the_rules_fails_the_check(self):
        feats = {"T.A": [(2, 2, 1)]}
        out = self._check([{"feature": "T.NOT_IN_DB"}], feats)
        self.assertFalse(out["semantic_bits_decidable"])
        self.assertEqual(out["not_in_frozen_rules"], 1)


class CandidateFootprint(unittest.TestCase):
    """A Hamming-1 flip is not a candidate: every frame write recomputes the ECC word."""

    def test_footprint_counts_ecc_collateral(self):
        out = D.candidate_footprint(D.DEFAULT_MAP)
        self.assertEqual(out["semantic_bits"], 292)
        self.assertEqual(out["target_frames"], 12)
        self.assertEqual(out["ecc_collateral_bit_positions"],
                         12 * D.ECC_BITS_PER_FRAME)

    def test_ecc_constants_match_the_ecc_module(self):
        import frame_ecc
        self.assertEqual(D.ECC_WORD, frame_ecc.ECC_WORD)
        self.assertEqual(D.ECC_BITS_PER_FRAME, frame_ecc.ECC_MASK.bit_length())


class ReportSchema(unittest.TestCase):
    """The machine output must not re-assert the framing the document retracted."""

    RETRACTED = ("claimb_safety_decidability_pilot", "safety_leg", "safety_conjunct")
    SOURCE = REPO_ROOT / "scripts/diag_safety_decidability.py"

    def test_schema_constant_is_neutral(self):
        self.assertEqual(D.SCHEMA, "zynq7_hamming1_decidability_census")

    def test_the_report_takes_its_schema_from_that_constant(self):
        """Structural, not textual.

        A substring search over the source passes when the correct name sits in a comment
        and the emitted value is wrong — demonstrated, which is why this reads the AST:
        the report's "schema" value must be the NAME `SCHEMA`, never a literal.
        """
        import ast
        tree = ast.parse(self.SOURCE.read_text())
        found = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "schema":
                    found.append(value)
        self.assertEqual(len(found), 1, "exactly one report dict should carry a schema")
        self.assertIsInstance(found[0], ast.Name,
                              "the schema must reference the SCHEMA constant, not a "
                              "literal a comment could shadow")
        self.assertEqual(found[0].id, "SCHEMA")

    def test_the_retracted_names_cannot_come_back(self):
        source = self.SOURCE.read_text()
        for name in self.RETRACTED:
            self.assertNotIn(name, source,
                             f"{name!r} was retracted in "
                             "docs/zynq7_decidability_census.md 0")


class FrozenRuleFiles(unittest.TestCase):
    def test_the_map_universe_is_decidable_on_the_frozen_data(self):
        """The published claim, re-derived rather than quoted."""
        feats, users = {}, {}
        for tile_type in ("CLBLL_L", "CLBLM_L"):
            f = D.load_segbits(tile_type)
            _, bu = D.decode_groups(f)
            feats[tile_type], users[tile_type] = f, bu
        out = D.check_map(D.DEFAULT_MAP, feats, users)
        self.assertEqual(out["addresses"], 292)
        self.assertEqual(out["feature_widths"], {"1": 292})
        self.assertEqual(out["shared_with_another_feature"], 0)
        self.assertTrue(out["semantic_bits_decidable"])

    def test_int_rule_patterns_are_two_or_five_bits(self):
        widths = {len(p) for p in D.load_segbits("INT_L").values()}
        self.assertEqual(widths, {2, 5},
                         "the single-flip result depends on this encoding shape")


if __name__ == "__main__":
    unittest.main()
