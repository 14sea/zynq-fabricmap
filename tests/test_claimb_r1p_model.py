"""host/claimb_r1p_model.py — the host model of the instrument's fitness and the
preregistered prediction.

What is pinned here: the per-bit table's shape (102 gains, 81 losses, 109 holdout-only
positions among the 292), the base scores (train 118, holdout 74), the additive table
agreeing with P3's exact predictor on real candidates, the block statistic's decision rule
on synthetic data (a discrimination test in both directions), and the committed prediction
hashing to the manifest and regenerating identically from the plan."""
from __future__ import annotations

import hashlib
import json
import random
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import claimb_r1p_instrument as inst  # noqa: E402
import claimb_r1p_model as mdl  # noqa: E402

MANIFEST = json.loads(inst.MANIFEST.read_text())
PLAN_PATH = R / "evidence/claimb_round1prime/plan.json"
PRED_PATH = R / "evidence/claimb_round1prime/model_prediction.json"
HAVE = inst.DEFAULT_ROOT.is_dir()

_MODEL = None


def model() -> mdl.Model:
    global _MODEL
    if _MODEL is None:
        _MODEL = mdl.Model(require_git=False)
    return _MODEL


def rows_with(diffs_per_block: list[int], block_pairs: int = 5, blocks: int = 4, base_a: int = 1) -> list[dict]:
    """Synthetic rows: every random-safe candidate gains base_a; in block b the best
    map-guided candidate gains base_a + diffs_per_block[b] (others base_a − 1)."""
    rows = []
    for b in range(blocks):
        for i in range(block_pairs):
            pair = b * block_pairs + i
            rows.append({"pair": pair, "arm": mdl.ARM_A, "d_train": base_a})
            gain = base_a + diffs_per_block[b] if i == 0 else base_a - 1
            rows.append({"pair": pair, "arm": mdl.ARM_B, "d_train": gain})
    return rows


class Metrics(unittest.TestCase):
    def test_primary_true_only_at_or_above_the_threshold(self):
        blocks = 16
        for pos in (0, 11, 12, 16):
            diffs = [1] * pos + [0] * (blocks - pos)
            m = mdl.metrics(rows_with(diffs, block_pairs=3, blocks=blocks), block_pairs=3, blocks=blocks)
            self.assertEqual(m["primary"]["positive"], pos)
            self.assertEqual(m["primary"]["map_guided_better"], pos >= mdl.SIGN_THRESHOLD, pos)

    def test_ties_count_against_and_negatives_are_counted(self):
        m = mdl.metrics(rows_with([0, -1, 0, 1], block_pairs=2, blocks=4), block_pairs=2, blocks=4)
        p = m["primary"]
        self.assertEqual((p["positive"], p["negative"], p["ties"]), (1, 1, 2))
        self.assertFalse(p["map_guided_better"])

    def test_secondary_is_the_per_pair_paired_difference(self):
        rows = rows_with([2, 2], block_pairs=2, blocks=2)
        m = mdl.metrics(rows, block_pairs=2, blocks=2)
        # per pair: (base_a+2) − base_a = +2 for i == 0, (base_a − 1) − base_a = −1 otherwise
        self.assertAlmostEqual(m["secondary"]["mean_paired_difference"], (2 - 1 + 2 - 1) / 4)
        self.assertEqual((m["secondary"]["positive"], m["secondary"]["negative"], m["secondary"]["ties"]), (2, 2, 0))

    def test_too_few_pairs_is_an_error_not_a_short_table(self):
        with self.assertRaises(mdl.ModelError):
            mdl.metrics(rows_with([1] * 3, block_pairs=2, blocks=3), block_pairs=2, blocks=4)


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class BitTable(unittest.TestCase):
    def test_shape_of_the_table(self):
        m = model()
        self.assertEqual(len(m.delta), 292)
        counts = {(t["d_train"], t["d_holdout"]) for t in m.delta}
        self.assertEqual(counts, {(1, 0), (-1, 0), (0, 1), (0, -1)})
        n = lambda dt, dh: sum(1 for t in m.delta if (t["d_train"], t["d_holdout"]) == (dt, dh))  # noqa: E731
        self.assertEqual((n(1, 0), n(-1, 0), n(0, 1), n(0, -1)), (102, 81, 59, 50))
        self.assertTrue(all(t["d_train"] == 0 or t["d_holdout"] == 0 for t in m.delta))

    def test_base_scores(self):
        m = model()
        self.assertEqual(m.base_train, [18, 22, 20, 20, 20, 18])
        self.assertEqual(sum(m.base_train), 118)
        self.assertEqual(sum(m.base_holdout), 74)

    def test_additive_table_agrees_with_p3s_exact_predictor(self):
        m = model()
        rng = random.Random(7)
        for _ in range(40):
            genome = 0
            for b in rng.sample(range(292), 4):
                genome |= 1 << b
            dt, dh = m.delta_of(genome)
            self.assertEqual(sum(m.predict(genome, False)) - 118, dt)
            self.assertEqual(sum(m.predict(genome, True)) - 74, dh)

    def test_every_candidate_gain_is_within_plus_minus_mutation_bits(self):
        m = model()
        rows = m.schedule_rows(0x0BADF00D, 200)
        for r in rows:
            self.assertEqual(len(r["bits"]), m.data["mutation_bits"])
            self.assertTrue(-4 <= r["d_train"] <= 4)

    def test_exact_expectations_are_linear_in_mutation_bits(self):
        m = model()
        e = m.exact_expectations()
        mean_all = sum(t["d_train"] for t in m.delta) / 292
        self.assertAlmostEqual(e["random_safe_E_d_train"], 4 * mean_all)
        self.assertNotEqual(e["random_safe_E_d_train"], e["map_guided_E_d_train"])


@unittest.skipUnless(HAVE and PRED_PATH.is_file(), "the prediction artifact or the instrument is absent")
class CommittedPrediction(unittest.TestCase):
    def test_prediction_hashes_to_the_manifest_pin(self):
        self.assertEqual(hashlib.sha256(PRED_PATH.read_bytes()).hexdigest(), MANIFEST["model_prediction"]["sha256"])

    def test_prediction_pins_the_plan_and_the_instrument(self):
        pred = json.loads(PRED_PATH.read_text())
        self.assertEqual(pred["plan_sha256"], hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest())
        self.assertEqual(pred["pins"]["psoracle_commit"], MANIFEST["instrument"]["psoracle_commit"])
        self.assertEqual(pred["pins"]["operator_data_sha256"], MANIFEST["instrument"]["operator_data_sha256"])
        self.assertEqual(pred["pins"]["image_sha256"], MANIFEST["instrument"]["image_sha256"])

    def test_prediction_regenerates_identically_from_the_plan(self):
        plan = json.loads(PLAN_PATH.read_text())
        pred = json.loads(PRED_PATH.read_text())
        m = model()
        again = mdl.prediction(m, plan["master_seed"], plan["n"], MANIFEST)
        self.assertEqual(len(again["candidates"]), len(pred["candidates"]))
        self.assertEqual(again["metrics_train"]["primary"], pred["metrics_train"]["primary"])
        self.assertEqual(again["metrics_train"]["secondary"], pred["metrics_train"]["secondary"])
        self.assertEqual(again["exact_expectations"], pred["exact_expectations"])
        for a, b in zip(again["candidates"][:500], pred["candidates"][:500]):
            self.assertEqual((a["seq"], a["arm"], a["genome"], a["d_train"]), (b["seq"], b["arm"], b["genome"], b["d_train"]))
        # the exact predictor on a sample of the committed rows
        for c in pred["candidates"][::997]:
            self.assertEqual(m.predict(m.gn.from_hex(c["genome"])), c["scores_train"])

    def test_the_predicted_outcome_is_the_negative_by_arithmetic(self):
        pred = json.loads(PRED_PATH.read_text())
        po = pred["predicted_outcome"]
        self.assertFalse(po["primary_map_guided_better"])
        self.assertEqual(po["primary_ties"], mdl.BLOCKS)
        for b in pred["metrics_train"]["primary"]["blocks"]:
            self.assertEqual((b["best_random_safe"], b["best_map_guided"]), (4, 4))


if __name__ == "__main__":
    unittest.main()
