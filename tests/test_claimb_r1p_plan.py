"""host/claimb_r1p_plan.py — the session plan: seed rule and exclusion, N, budgets, blocks.

The seed rule is pure and is tested without the instrument (the derivation advances past
an excluded value; the trace records it). The pair-seed exclusion is shown to DETECT a
collision (a master seed equal to L6's S seed collides on every pair) and to find none for
the committed seed. The committed plan hashes to the manifest's pin and regenerates
identically; its numbers satisfy the preregistered formula and the window ceiling."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import claimb_r1p_instrument as inst  # noqa: E402
import claimb_r1p_model as mdl  # noqa: E402
import claimb_r1p_plan as cp  # noqa: E402

MANIFEST = json.loads(inst.MANIFEST.read_text())
PLAN_PATH = R / "evidence/claimb_round1prime/plan.json"
HAVE = inst.DEFAULT_ROOT.is_dir()


class SeedRule(unittest.TestCase):
    def test_rule_is_the_digest_prefix_and_records_its_derivation(self):
        s = cp.master_seed_by_rule(MANIFEST)
        digest = hashlib.sha256(cp.SEED_LABEL + MANIFEST["instrument"]["psoracle_commit"].encode()).digest()
        self.assertEqual(s["digest"], digest.hex())
        self.assertEqual(s["master_seed"], int.from_bytes(digest[s["offset"]:s["offset"] + 4], "big"))
        self.assertNotIn(s["master_seed"], cp.excluded_seeds(MANIFEST))

    def test_rule_advances_past_an_excluded_value(self):
        m = copy.deepcopy(MANIFEST)
        first = cp.master_seed_by_rule(m)
        m["seeds"]["excluded"]["test_only"] = [first["master_seed"]]
        second = cp.master_seed_by_rule(m)
        self.assertEqual(second["offset"], first["offset"] + 4)
        self.assertTrue(second["trace"][0]["excluded"])
        self.assertNotEqual(second["master_seed"], first["master_seed"])

    def test_every_l6_and_l5_seed_is_excluded(self):
        ex = cp.excluded_seeds(MANIFEST)
        for s in (1, 1278624577, 1278628687):
            self.assertIn(s, ex)

    def test_a_digest_of_all_excluded_windows_is_an_error(self):
        m = copy.deepcopy(MANIFEST)
        digest = hashlib.sha256(cp.SEED_LABEL + m["instrument"]["psoracle_commit"].encode()).digest()
        m["seeds"]["excluded"]["test_only"] = [int.from_bytes(digest[o:o + 4], "big") for o in range(0, 32, 4)]
        with self.assertRaises(cp.PlanError):
            cp.master_seed_by_rule(m)


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class PairSeedExclusion(unittest.TestCase):
    def setUp(self):
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import l6_schedule as ls
        self.ls = ls

    def test_the_check_detects_a_collision(self):
        s_seed = MANIFEST["seeds"]["excluded"]["L6_S"][0]
        r = cp.pair_seed_exclusion(self.ls, s_seed, 200, MANIFEST)
        self.assertTrue(r["collisions"])
        self.assertTrue(all(c["l6_session"] == "S" for c in r["collisions"]))
        self.assertEqual(len(r["collisions"]), 100)

    def test_the_committed_seed_has_none(self):
        r = cp.pair_seed_exclusion(self.ls, MANIFEST["seeds"]["master_seed"], 11752, MANIFEST)
        self.assertEqual(r["collisions"], [])
        self.assertEqual(r["l6_pairs_checked"], 32 + 32 + 6284)


@unittest.skipUnless(HAVE and PLAN_PATH.is_file(), "the plan artifact or the instrument is absent")
class CommittedPlan(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(PLAN_PATH.read_text())

    def test_plan_hashes_to_the_manifest_pin_and_names_the_manifest_seed(self):
        self.assertEqual(hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(), MANIFEST["plan"]["sha256"])
        self.assertEqual(self.plan["master_seed"], MANIFEST["seeds"]["master_seed"])
        self.assertEqual(self.plan["master_seed"], cp.master_seed_by_rule(MANIFEST)["master_seed"])

    def test_n_follows_the_formula_with_the_slower_arm_and_fits_the_window(self):
        p, s = self.plan, self.plan["sizing"]
        self.assertEqual(s["sizing_arm"], "min")
        self.assertAlmostEqual(s["unrounded"], cp.WINDOW_FRACTION * min(s["rate_C1"], s["rate_C2"]) * p["window_s"] / 3600.0)
        self.assertEqual(p["n"], int(s["unrounded"]) - (int(s["unrounded"]) % 2))
        self.assertEqual(p["n"] % 2, 0)
        self.assertEqual(p["pairs"], p["n"] // 2)
        self.assertEqual(p["window_s"], MANIFEST["window"]["span_s"])
        self.assertEqual(p["session_timeout_s"], p["window_s"])
        v = p["soak_validation"]
        self.assertTrue(v["pass"])
        self.assertLessEqual(v["predicted_wall_s"], cp.WALL_MARGIN * p["window_s"])
        self.assertAlmostEqual(v["predicted_wall_s"], p["n"] * v["normalised_interval_s"])

    def test_audit_schedule_frames_and_budgets_are_the_soaks_rules(self):
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import l6_schedule as ls
        p = self.plan
        self.assertEqual(p["audit_policy"], "sampled")
        self.assertEqual(set(p["audit_seqs"]), ls.sampled_audit_seqs(p["n"], 16))
        self.assertEqual(p["expected_frames"], ls.expected_frames(p["n"], set(p["audit_seqs"]), "rel-v4"))
        self.assertEqual(p["crc_budget"], ls.crc_budget(p["expected_frames"]["total"]))
        self.assertEqual(p["bad_frame_budget"], p["crc_budget"])
        self.assertEqual(p["flags"], ls.flags_for("abba", watchdog=True, rec_control=True, sign_control=True))

    def test_blocks_cover_the_pairs(self):
        b = self.plan["blocks"]
        self.assertEqual((b["block_pairs"], b["blocks"], b["sign_threshold"]), (mdl.BLOCK_PAIRS, mdl.BLOCKS, mdl.SIGN_THRESHOLD))
        self.assertEqual(b["pairs_in_blocks"] + b["pairs_beyond_blocks"], self.plan["pairs"])
        self.assertLess(b["pairs_beyond_blocks"], mdl.BLOCK_PAIRS)

    def test_plan_regenerates_identically(self):
        again = cp.build_plan(MANIFEST, require_git=False)
        for k in ("master_seed", "n", "pairs", "audit_seqs", "crc_budget", "schedule_sha256", "flags", "session_timeout_s"):
            self.assertEqual(again[k], self.plan[k], k)
        self.assertEqual(again["sizing"]["unrounded"], self.plan["sizing"]["unrounded"])
        self.assertEqual(again["soak_validation"]["predicted_wall_s"], self.plan["soak_validation"]["predicted_wall_s"])

    def test_compatibility_drift_is_a_refusal(self):
        m = copy.deepcopy(MANIFEST)
        m["fabricmap_artifacts"]["local_map"]["sha256"] = "0" * 64
        with self.assertRaises(cp.PlanError) as cm:
            cp.build_plan(m, require_git=False)
        self.assertIn("falsifier 3", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
