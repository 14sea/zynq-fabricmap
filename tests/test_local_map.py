"""`build_local_map.py` re-indexes a certificate, or refuses.

A correct certificate satisfies a lax builder exactly as well as a strict one, so every
rule here is exercised by handing the builder a **wrong** certificate and requiring the
refusal. The happy path is checked against the real production certificate and validated
against the schema, but on its own it would demonstrate almost nothing.

What is being falsified:

* **the map adds no knowledge** — every address, polarity and feature name is the
  certificate's, and a map whose universe disagrees with a fresh derivation is drift;
* **provenance is a gate, not a label** — a failed or conformance certificate is refused
  outright, so a map can never descend from evidence that says nothing about this device;
* **the bijection is checked, not assumed** — the 388 results cover 292 features, so
  features are re-attested; disagreeing re-attestation and two features claiming one
  address are both refusals;
* **the collateral rule is lifted from the certificate**, never compiled in — a constant
  in the gate would keep agreeing with itself after the certificate's rule changed.

Refusals are asserted through the pure functions, not through a subprocess: this repo has
been bitten four times by tests that assert a late refusal through a path where an earlier
one fires first (or where missing git history ends the run before the rule is reached).
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_local_map as blm  # noqa: E402

CERT_PATH = REPO_ROOT / "gate_runs/run_2026_08_02_a/certificate.json"
MANIFEST_PATH = REPO_ROOT / "data/MANIFEST.json"
MAP_PATH = REPO_ROOT / "maps/clb_lut_init_v1.local_map.json"
SCHEMA_PATH = REPO_ROOT / "schemas/local_map.schema.json"


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


class AddressKeyTests(unittest.TestCase):
    def test_canonical_form(self):
        self.assertEqual(blm.address_key("0x00400A20", 51, 15), "0x00400A20/51/15")

    def test_key_distinguishes_word_and_bit(self):
        # 51/5 and 5/15 must not collide into the same string.
        self.assertNotEqual(
            blm.address_key("0x00400A20", 51, 5), blm.address_key("0x00400A20", 5, 15)
        )


class AdmissibilityTests(unittest.TestCase):
    """Provenance rules, checked on minimal dicts so nothing else can fire first."""

    def base(self) -> dict:
        return {
            "schema": "fabric_bit_class_certificate",
            "status": "passed",
            "profile": "production",
            "feature_results": [{"feature": "x"}],
        }

    def test_accepts_a_passing_production_certificate(self):
        blm.check_certificate_admissible(self.base(), Path("c.json"))

    def test_refuses_a_failed_certificate(self):
        cert = self.base()
        cert["status"] = "failed"
        with self.assertRaises(blm.MapError) as ctx:
            blm.check_certificate_admissible(cert, Path("c.json"))
        self.assertIn("not 'passed'", str(ctx.exception))

    def test_refuses_a_conformance_certificate(self):
        cert = self.base()
        cert["profile"] = "conformance"
        with self.assertRaises(blm.MapError) as ctx:
            blm.check_certificate_admissible(cert, Path("c.json"))
        self.assertIn("not 'production'", str(ctx.exception))

    def test_refuses_a_foreign_schema(self):
        cert = self.base()
        cert["schema"] = "something_else"
        with self.assertRaises(blm.MapError):
            blm.check_certificate_admissible(cert, Path("c.json"))

    def test_refuses_a_group_model_certificate(self):
        cert = self.base()
        del cert["feature_results"]
        with self.assertRaises(blm.MapError) as ctx:
            blm.check_certificate_admissible(cert, Path("c.json"))
        self.assertIn("feature evidence model", str(ctx.exception))


def result(feature, far, word, bit, value=1, split="mine", observed=None):
    obs = observed if observed is not None else (far, word, bit, value)
    return {
        "feature": feature,
        "split": split,
        "rule_file": "prjxray/zynq7/segbits_clbll_l.db",
        "predicted_assignments": [
            {
                "address": {"far": far, "word": word, "bit": bit},
                "expected_value": value,
            }
        ],
        "observed_assignments": [
            {
                "address": {"far": obs[0], "word": obs[1], "bit": obs[2]},
                "observed_value": obs[3],
            }
        ],
        "exclusion_rules": [
            {
                "reason": "frame_ecc",
                "rule": "word == 50 and 0 <= bit <= 12",
                "why": "the frame ECC field is recomputed",
            }
        ],
    }


class UniverseTests(unittest.TestCase):
    def test_collapses_reattestation_that_agrees(self):
        rows = [
            result("T.S.ALUT.INIT[00]", "0x00400A20", 51, 15),
            result("T.S.ALUT.INIT[00]", "0x00400A20", 51, 15),
        ]
        universe = blm.universe_from_certificate(rows)
        self.assertEqual(len(universe), 1)

    def test_refuses_reattestation_that_disagrees(self):
        rows = [
            result("T.S.ALUT.INIT[00]", "0x00400A20", 51, 15),
            result("T.S.ALUT.INIT[00]", "0x00400A21", 51, 15),
        ]
        with self.assertRaises(blm.MapError) as ctx:
            blm.universe_from_certificate(rows)
        self.assertIn("re-attested", str(ctx.exception))

    def test_refuses_two_features_claiming_one_address(self):
        rows = [
            result("T.S.ALUT.INIT[00]", "0x00400A20", 51, 15),
            result("T.S.ALUT.INIT[01]", "0x00400A20", 51, 15),
        ]
        with self.assertRaises(blm.MapError) as ctx:
            blm.universe_from_certificate(rows)
        self.assertIn("claimed by two features", str(ctx.exception))

    def test_refuses_predicted_observed_address_mismatch(self):
        rows = [
            result(
                "T.S.ALUT.INIT[00]", "0x00400A20", 51, 15,
                observed=("0x00400A21", 51, 15, 1),
            )
        ]
        with self.assertRaises(blm.MapError) as ctx:
            blm.universe_from_certificate(rows)
        self.assertIn("observed", str(ctx.exception))

    def test_refuses_polarity_mismatch(self):
        """The one place a silent inversion would ride into every candidate."""
        rows = [
            result(
                "T.S.ALUT.INIT[00]", "0x00400A20", 51, 15, value=1,
                observed=("0x00400A20", 51, 15, 0),
            )
        ]
        with self.assertRaises(blm.MapError) as ctx:
            blm.universe_from_certificate(rows)
        self.assertIn("expected value", str(ctx.exception))

    def test_refuses_multi_assignment_feature(self):
        row = result("T.S.ALUT.INIT[00]", "0x00400A20", 51, 15)
        row["predicted_assignments"].append(
            {"address": {"far": "0x00400A21", "word": 51, "bit": 15}, "expected_value": 1}
        )
        with self.assertRaises(blm.MapError) as ctx:
            blm.universe_from_certificate([row])
        self.assertIn("shrink the universe silently", str(ctx.exception))

    def test_negated_polarity_survives_into_the_universe(self):
        """No real certified bit is negated, so this path only exists synthetically."""
        rows = [result("T.S.ALUT.INIT[00]", "0x00400A20", 51, 15, value=0)]
        universe = blm.universe_from_certificate(rows)
        self.assertEqual(universe[0]["expected_value"], 0)


class CollateralTests(unittest.TestCase):
    def test_lifts_the_rule_from_the_certificate(self):
        rule = blm.collateral_from_certificate([result("f", "0x00400A20", 51, 15)])
        self.assertEqual((rule["word"], rule["bit_low"], rule["bit_high"]), (50, 0, 12))
        self.assertEqual(rule["scope"], "touched_frames_only")

    def test_refuses_two_conflicting_ecc_rules(self):
        rows = [result("f1", "0x00400A20", 51, 15), result("f2", "0x00400A21", 51, 15)]
        rows[1]["exclusion_rules"][0]["rule"] = "word == 49 and 0 <= bit <= 12"
        with self.assertRaises(blm.MapError) as ctx:
            blm.collateral_from_certificate(rows)
        self.assertIn("exactly one", str(ctx.exception))

    def test_refuses_an_unparseable_rule(self):
        rows = [result("f1", "0x00400A20", 51, 15)]
        rows[0]["exclusion_rules"][0]["rule"] = "whatever the ECC field is"
        with self.assertRaises(blm.MapError):
            blm.collateral_from_certificate(rows)

    def test_a_truncated_rule_is_refused_and_does_not_crash(self):
        """A gate that crashes has not judged anything (ruled here 2026-08-07).

        Note for whoever mutation-tests this next: making the final group optional
        (`(\\d+)?`) is an EQUIVALENT mutant and survives on purpose. It would leave the
        group as None — and `int(None)` is a crash, not a refusal — but only for a rule
        ending in a trailing space, and `.strip()` removes that before the match. No
        input distinguishes the two patterns, so this is a fair category and not a
        coverage hole.
        """
        rows = [result("f1", "0x00400A20", 51, 15)]
        rows[0]["exclusion_rules"][0]["rule"] = "word == 50 and 0 <= bit <= "
        with self.assertRaises(blm.MapError):
            blm.collateral_from_certificate(rows)

    def test_a_widened_rule_is_a_different_rule(self):
        """A gate that read 'word == 50' and dropped the bit range would admit word-50
        bits 13..31 as collateral. The parse must carry the range."""
        rows = [result("f1", "0x00400A20", 51, 15)]
        rows[0]["exclusion_rules"][0]["rule"] = "word == 50 and 0 <= bit <= 31"
        rule = blm.collateral_from_certificate(rows)
        self.assertEqual(rule["bit_high"], 31)


class IndexTests(unittest.TestCase):
    def test_by_lut_orders_by_init_index(self):
        universe = blm.universe_from_certificate(
            [
                result("T.S.ALUT.INIT[02]", "0x00400A20", 51, 14),
                result("T.S.ALUT.INIT[00]", "0x00400A20", 51, 15),
                result("T.S.ALUT.INIT[01]", "0x00400A21", 51, 15),
            ]
        )
        index = blm.build_index(universe)
        self.assertEqual(
            [b["init_index"] for b in index["by_lut"]["T.S.ALUT"]], [0, 1, 2]
        )

    def test_by_far_groups_the_frame(self):
        universe = blm.universe_from_certificate(
            [
                result("T.S.ALUT.INIT[00]", "0x00400A20", 51, 15),
                result("T.S.ALUT.INIT[01]", "0x00400A21", 51, 15),
                result("T.S.ALUT.INIT[02]", "0x00400A20", 51, 14),
            ]
        )
        index = blm.build_index(universe)
        self.assertEqual(len(index["by_far"]["0x00400A20"]), 2)
        self.assertEqual(len(index["by_far"]["0x00400A21"]), 1)

    def test_refuses_a_non_init_feature(self):
        universe = blm.universe_from_certificate(
            [result("CLBLL_L.SLICEL_X0.CEUSEDMUX", "0x00400A20", 51, 15)]
        )
        with self.assertRaises(blm.MapError) as ctx:
            blm.build_index(universe)
        self.assertIn("clb_lut_init only", str(ctx.exception))


class RealCertificateTests(unittest.TestCase):
    """The happy path, against the artifact that will actually be used."""

    @classmethod
    def setUpClass(cls):
        if not CERT_PATH.exists():
            raise unittest.SkipTest(f"{CERT_PATH} absent")
        cls.doc = blm.build_map(CERT_PATH, MANIFEST_PATH, "clb_lut_init_v1")

    def test_universe_is_the_certified_292(self):
        self.assertEqual(self.doc["universe"]["address_count"], 292)
        self.assertEqual(len(self.doc["universe"]["addresses"]), 292)

    def test_class_is_larger_than_what_is_certified(self):
        """The gap must be visible in the artifact, not hidden by reporting one number."""
        bit_class = self.doc["bit_class"]
        self.assertEqual(bit_class["class_entry_count"], 2048)
        self.assertEqual(bit_class["attested_count"], 292)
        self.assertLess(bit_class["attested_count"], bit_class["class_entry_count"])

    def test_addresses_are_unique(self):
        keys = [a["key"] for a in self.doc["universe"]["addresses"]]
        self.assertEqual(len(set(keys)), len(keys))

    def test_index_covers_exactly_the_universe(self):
        keys = {a["key"] for a in self.doc["universe"]["addresses"]}
        by_far = {k for keys_ in self.doc["index"]["by_far"].values() for k in keys_}
        by_lut = {
            b["address_key"]
            for bits in self.doc["index"]["by_lut"].values()
            for b in bits
        }
        self.assertEqual(by_far, keys)
        self.assertEqual(by_lut, keys)

    def test_no_lut_is_fully_writable(self):
        """Recorded in the preregistration: the fitness cannot assume a free 64-bit INIT."""
        for lut, bits in self.doc["index"]["by_lut"].items():
            self.assertLess(len(bits), 64, f"{lut} is fully covered — prereg §2 is stale")

    def test_provenance_pins_the_certificate_and_the_freeze(self):
        prov = self.doc["provenance"]
        self.assertEqual(prov["kind"], "certificate_inherited")
        self.assertEqual(prov["certificate"]["status"], "passed")
        self.assertEqual(prov["certificate"]["profile"], "production")
        self.assertRegex(prov["certificate"]["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(prov["frozen_data"]["sha256"], r"^[0-9a-f]{64}$")

    def test_derivation_is_deterministic(self):
        again = blm.build_map(CERT_PATH, MANIFEST_PATH, "clb_lut_init_v1")
        self.assertEqual(blm.serialise(again), blm.serialise(self.doc))

    def test_target_mismatch_against_the_freeze_is_refused(self):
        cert = load(CERT_PATH)
        cert["target"] = dict(cert["target"], part="xc7a35tcpg236-1")
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "certificate.json"
            path.write_text(json.dumps(cert), encoding="utf-8")
            with self.assertRaises(blm.MapError) as ctx:
                blm.build_map(path, MANIFEST_PATH, "x")
        self.assertIn("stale by construction", str(ctx.exception))


class CommittedMapTests(unittest.TestCase):
    """The committed map must still be what the certificate derives — no hand edits."""

    def setUp(self):
        if not MAP_PATH.exists():
            self.skipTest(f"{MAP_PATH} absent")

    def test_committed_map_matches_a_fresh_derivation(self):
        fresh = blm.build_map(CERT_PATH, MANIFEST_PATH, "clb_lut_init_v1")
        self.assertEqual(load(MAP_PATH), fresh)

    def test_committed_map_validates_against_the_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        jsonschema.validate(load(MAP_PATH), load(SCHEMA_PATH))

    def test_schema_refuses_a_self_cartography_map(self):
        """kind is a const on purpose: a later provenance is a different claim."""
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        doc = copy.deepcopy(load(MAP_PATH))
        doc["provenance"]["kind"] = "self_cartography"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(doc, load(SCHEMA_PATH))

    def test_schema_refuses_an_absolute_path(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        doc = copy.deepcopy(load(MAP_PATH))
        doc["provenance"]["certificate"]["path"] = "/home/test/zynq_fabricmap/c.json"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(doc, load(SCHEMA_PATH))


if __name__ == "__main__":
    unittest.main()
