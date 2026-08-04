"""The `clb_ff_config` plan, checked before anything is committed or built.

These tests run entirely on the freeze. They are what makes the draft reviewable: the
plan claims to cover the class exactly once, to compute every address from the normative
arithmetic, and to predict a direction for each feature that a bitstream can refute.
Each of those is checked here rather than asserted in prose.

The hold itself is tested too. Pre-registration is the author's to lift, and a tool that
could be talked into writing a commitment by passing a path is not held at all.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
EMITTER = REPO_ROOT / "scripts/gate_emit_ff.py"
DB = REPO_ROOT / "data/prjxray/zynq7"


def emit(out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(EMITTER), "--out", str(out)],
        cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )


class FfPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory(dir=REPO_ROOT / "build")
        out = Path(cls._directory.name) / "predictions.json"
        checked = emit(out)
        assert checked.returncode == 0, checked.stdout
        cls.plan = json.loads(out.read_text())
        spec = json.loads((REPO_ROOT / "data/subset_spec.json").read_text())
        cls.pattern = re.compile(
            next(c["feature_regex"] for c in spec["bit_classes"] if c["id"] == "clb_ff_config")
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def test_every_frozen_entry_is_asserted_exactly_once(self) -> None:
        frozen = set()
        for tile_type in {s["tile_type"] for s in self.plan["specimens"]}:
            for line in (DB / f"segbits_{tile_type.lower()}.db").read_text().splitlines():
                fields = line.split()
                if fields and self.pattern.fullmatch(fields[0]):
                    frozen.add(fields[0])
        asserted = [p["feature"] for p in self.plan["predictions"]]
        self.assertEqual(len(frozen), 176)
        self.assertEqual(sorted(asserted), sorted(frozen))
        self.assertEqual(len(asserted), len(set(asserted)))

    def test_manifest_denominator_and_totals_agree(self) -> None:
        manifest = json.loads((REPO_ROOT / "data/MANIFEST.json").read_text())
        entries = next(c["entries"] for c in manifest["bit_classes"] if c["id"] == "clb_ff_config")
        self.assertEqual(entries, len(self.plan["predictions"]))
        self.assertEqual(self.plan["totals"]["predictions"], len(self.plan["predictions"]))
        self.assertEqual(
            self.plan["totals"]["holdout_predictions"],
            sum(1 for p in self.plan["predictions"] if p["split"] == "holdout"),
        )

    def test_split_leaves_the_established_site_unable_to_score(self) -> None:
        mine = {p["feature"] for p in self.plan["predictions"] if p["split"] == "mine"}
        self.assertEqual(len(mine), 22)
        for prediction in self.plan["predictions"]:
            specimen = next(s for s in self.plan["specimens"]
                            if s["specimen_id"] == prediction["specimen_id"])
            expected = "mine" if specimen["site"] == "SLICE_X2Y25" else "holdout"
            self.assertEqual(prediction["split"], expected)

    def test_every_rule_is_single_bit_and_addressed_by_the_normative_arithmetic(self) -> None:
        tilegrid = json.loads((DB / "xc7z010/tilegrid.json").read_text())
        for prediction in self.plan["predictions"]:
            specimen = next(s for s in self.plan["specimens"]
                            if s["specimen_id"] == prediction["specimen_id"])
            block = tilegrid[specimen["tile"]]["bits"]["CLB_IO_CLK"]
            self.assertEqual(len(prediction["predicted_assignments"]), 1)
            item = prediction["predicted_assignments"][0]
            frame, bit = item["segbit"]["frame_offset"], item["segbit"]["bit_offset"]
            self.assertEqual(
                item["address"],
                {"far": f"0x{int(block['baseaddr'], 16) + frame:08X}",
                 "word": block["offset"] + bit // 32, "bit": bit % 32},
            )

    def test_the_asserted_endpoint_is_a_refutable_direction(self) -> None:
        for prediction in self.plan["predictions"]:
            item = prediction["predicted_assignments"][0]
            expected = 0 if item["segbit"]["negated"] else 1
            self.assertEqual(item["expected_value"], expected)
            # the other endpoint must carry the complement, or the pair asserts nothing
            self.assertEqual(prediction["expected_transition"],
                             {"before": 1 - expected, "after": expected})

    def test_the_negated_tokens_are_exactly_the_noclkinv_features(self) -> None:
        negated = {p["feature"] for p in self.plan["predictions"]
                   if p["predicted_assignments"][0]["segbit"]["negated"]}
        self.assertEqual(len(negated), 8)
        self.assertTrue(all(name.endswith(".NOCLKINV") for name in negated))

    def test_complementary_clock_features_share_one_address(self) -> None:
        by_feature = {p["feature"]: p for p in self.plan["predictions"]}
        for name, prediction in by_feature.items():
            if not name.endswith(".CLKINV"):
                continue
            partner = by_feature[name.replace(".CLKINV", ".NOCLKINV")]
            self.assertEqual(prediction["predicted_assignments"][0]["address"],
                             partner["predicted_assignments"][0]["address"])
            # opposite values in different specimens: the 1.4 complementary pattern
            self.assertNotEqual(prediction["specimen_id"], partner["specimen_id"])

    def test_every_feature_has_exactly_one_endpoint_pair(self) -> None:
        owners = {}
        for specimen in self.plan["specimens"]:
            for feature in specimen["pair_features"]:
                self.assertNotIn(feature, owners)
                owners[feature] = specimen
        self.assertEqual(len(owners), len(self.plan["predictions"]))
        for prediction in self.plan["predictions"]:
            variant = owners[prediction["feature"]]
            base_id = f"{variant['site']}_base"
            # the asserting endpoint is one of the pair's two ends and never both
            self.assertIn(prediction["specimen_id"], (base_id, variant["specimen_id"]))
            self.assertTrue(any(s["specimen_id"] == base_id for s in self.plan["specimens"]))

    def test_four_features_are_claimed_to_assert_in_the_baseline(self) -> None:
        # ZRST, CEUSEDMUX, SRUSEDMUX, FFSYNC and NOCLKINV read the Z convention as
        # "asserted when the control is in its default state". If that is backwards the
        # gate must record FN, so the plan has to state it rather than accept either way.
        tails = {p["feature"].split(".", 2)[2] for p in self.plan["predictions"]
                 if p["specimen_id"].endswith("_base")}
        self.assertEqual(
            {t for t in tails if not t.endswith(".ZRST")},
            {"CEUSEDMUX", "SRUSEDMUX", "FFSYNC", "NOCLKINV"},
        )
        self.assertEqual(sum(1 for t in tails if t.endswith(".ZRST")), 8)

    def test_semantic_assertions_are_scalar_and_point_into_the_attestation(self) -> None:
        for prediction in self.plan["predictions"]:
            assertion = prediction["semantic_assertion"]
            self.assertEqual(assertion["kind"], "member_identity")
            self.assertTrue(assertion["semantic"])
            self.assertEqual(assertion["predicted_member"], prediction["feature"])
            self.assertTrue(assertion["attestation_field"].startswith("/resolved/"))
            self.assertIsInstance(assertion["expected_value"], str)

    def test_prediction_records_carry_exactly_the_1_4_contract_fields(self) -> None:
        expected = {"specimen_id", "feature", "split", "rule_file",
                    "predicted_assignments", "expected_transition", "semantic_assertion"}
        for prediction in self.plan["predictions"]:
            self.assertEqual(set(prediction), expected)

    def test_the_emitter_refuses_to_write_a_commitment_while_the_hold_stands(self) -> None:
        checked = emit(REPO_ROOT / "gate_runs/ff_hold_probe/predictions.json")
        self.assertNotEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("pre-registration is HELD", checked.stdout)
        self.assertFalse((REPO_ROOT / "gate_runs/ff_hold_probe").exists())


if __name__ == "__main__":
    unittest.main()
