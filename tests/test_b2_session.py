"""The B2 session order: the C orchestrator against its Python reference, candidate for
candidate (the discipline of B1's `test_b1_session.py`).

`firmware/b2/b2_orch.c` is the unit `b2_app.c` drives. The twin's `session` mode runs it
exactly as the application's main does, and `host/b2_session.run` is the reference. Compared:
the candidate sequence (baseline brackets, pair, arm, holdout flag, genome), every `search`
record block byte for byte, the record arithmetic of preregistration §2, the arm order, and
the rule that a candidate which is not SCORED ends the epoch with no closing baseline.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402
import b2_session as bsess  # noqa: E402

FW = R / "firmware/b2"
TWIN = FW / "build/b2_twin"
HAVE_CC = shutil.which(os.environ.get("CC", "cc")) is not None
TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
VIEW = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
MASTER = bs.master_seed(bp.SESSION_LABEL, bp.INSTRUMENT_COMMIT)
TOKEN = "a13f38b53355fd4c1cac3145244727f8"
UNIVERSE = bmaps.load_self_map()["binding"]["universe_sha256"]


def tables_hex(t: list[int]) -> str:
    return " ".join(f"{x:016x}" for x in t)


def drive(master: int, budget: int, total: int, first: int, count: int, unscored_at: int | None = None) -> dict:
    p = subprocess.Popen([str(TWIN), "session"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert p.stdin and p.stdout
    out: dict = {"cands": [], "records": None}
    p.stdin.write(f"{master} {budget} {total} {first} {count} {TOKEN} {UNIVERSE} 12345678\n")
    p.stdin.flush()
    while True:
        line = p.stdout.readline()
        if not line:
            break
        if line.startswith("CAND"):
            head, ghex = line.split("|")
            parts = head.split()
            rec = {"is_baseline": bool(int(parts[1])), "pair": int(parts[2]),
                   "arm": None if parts[3] == "-" else parts[3], "holdout": bool(int(parts[4])),
                   "seq": int(parts[5]), "genome": bc.genome_from_hex(ghex.strip()), "block": ""}
            out["cands"].append(rec)
            if unscored_at is not None and rec["seq"] == unscored_at:
                p.stdin.write("UNSCORED\n")
            else:
                p.stdin.write(tables_hex(FAB(rec["genome"])) + "\n")
            p.stdin.flush()
        elif line.startswith("BLOCK"):
            out["cands"][-1]["block"] = line[len("BLOCK "):].strip()
        elif line.startswith("END"):
            out["records"] = int(line.split()[1])
            break
    p.stdin.close()
    p.stdout.close()
    p.wait()
    return out


@unittest.skipUnless(HAVE_CC, "no host C compiler (CC): the twin cannot be built")
class SessionOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = subprocess.run(["make", "-s", "twin"], cwd=FW, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stdout + p.stderr)

    def _compare(self, budget: int, total: int, first: int, count: int, unscored_at: int | None = None):
        got = drive(MASTER, budget, total, first, count, unscored_at)
        ref = bsess.run(MASTER, budget, total, first, count, FAB, VIEW, unscored_at=unscored_at,
                        truth=TRUTH, masks=MASKS)
        self.assertEqual(len(got["cands"]), len(ref.candidates), "candidate count")
        for c, r in zip(got["cands"], ref.candidates):
            self.assertEqual((c["seq"], c["is_baseline"], c["pair"], c["arm"], c["holdout"], c["genome"]),
                             (r.seq, r.is_baseline, r.pair, r.arm, r.holdout, r.genome), f"candidate {r.seq}")
            self.assertEqual(c["block"], r.block, f"the search block of candidate {r.seq}")
        return got, ref

    def test_a_two_pair_slice_at_a_small_budget(self):
        got, ref = self._compare(budget=4, total=9, first=0, count=2)
        self.assertEqual(got["records"], bsess.records(2, 4))
        self.assertEqual(got["records"], 2 + 2 * (2 * 4 + 2))

    def test_the_record_arithmetic_of_the_preregistration(self):
        for count, budget in ((1, 3), (2, 4), (3, 5)):
            with self.subTest(count=count, budget=budget):
                got, _ = self._compare(budget=budget, total=9, first=0, count=count)
                self.assertEqual(got["records"], 2 + count * (2 * budget + 2))

    def test_the_arm_order_alternates_by_absolute_pair(self):
        got, _ = self._compare(budget=2, total=9, first=0, count=4)
        first_of = {}
        for c in got["cands"]:
            if c["is_baseline"] or c["holdout"]:
                continue
            first_of.setdefault(c["pair"], c["arm"])
        self.assertEqual(first_of, {0: "random_safe", 1: "map_guided", 2: "random_safe", 3: "map_guided"})

    def test_a_later_slice_keeps_the_absolute_pair_and_its_order(self):
        got, _ = self._compare(budget=2, total=9, first=5, count=2)
        pairs = sorted({c["pair"] for c in got["cands"] if not c["is_baseline"]})
        self.assertEqual(pairs, [5, 6])
        first_of = {}
        for c in got["cands"]:
            if c["is_baseline"] or c["holdout"]:
                continue
            first_of.setdefault(c["pair"], c["arm"])
        self.assertEqual(first_of, {5: "map_guided", 6: "random_safe"})

    def test_the_brackets_are_the_blank_genome(self):
        got, _ = self._compare(budget=2, total=9, first=0, count=1)
        self.assertTrue(got["cands"][0]["is_baseline"] and got["cands"][0]["genome"] == 0)
        self.assertTrue(got["cands"][-1]["is_baseline"] and got["cands"][-1]["genome"] == 0)
        self.assertEqual(sum(1 for c in got["cands"] if c["is_baseline"]), 2)
        for c in got["cands"]:
            if c["is_baseline"]:
                self.assertEqual(c["block"], "")        # a baseline carries no search block
                self.assertIsNone(c["arm"])

    def test_the_holdout_evaluations_close_each_pair(self):
        got, _ = self._compare(budget=3, total=9, first=0, count=2)
        per_pair: dict[int, list[dict]] = {}
        for c in got["cands"]:
            if not c["is_baseline"]:
                per_pair.setdefault(c["pair"], []).append(c)
        for pair, cands in per_pair.items():
            self.assertEqual([c["holdout"] for c in cands], [False] * 6 + [True] * 2, pair)
            self.assertEqual([c["arm"] for c in cands[-2:]], [cands[0]["arm"], cands[3]["arm"]])
            for c in cands[-2:]:
                blk = json.loads(c["block"])
                self.assertIsNotNone(blk["holdout"])
                self.assertIsNone(blk["move"])
                self.assertIsNone(blk["fitness"])

    def test_an_unscored_candidate_ends_the_epoch(self):
        for at in (1, 5, 9, 10):
            with self.subTest(unscored_at=at):
                got, ref = self._compare(budget=4, total=9, first=0, count=2, unscored_at=at)
                self.assertEqual(got["records"], at)
                self.assertTrue(ref.ended_early)
                self.assertEqual(got["cands"][-1]["seq"], at)
                self.assertEqual(got["cands"][-1]["block"], "")     # never observed, so no block
                if at > 1:
                    self.assertFalse(got["cands"][-1]["is_baseline"] and at != 1)

    def test_the_slice_must_lie_inside_the_experiment(self):
        for total, first, count in ((9, 8, 2), (9, -1, 2), (9, 0, 0), (0, 0, 1), (17, 0, 1)):
            with self.subTest(total=total, first=first, count=count):
                p = subprocess.run([str(TWIN), "session"], input=f"{MASTER} 4 {total} {first} {count} {TOKEN} {UNIVERSE} 0\n",
                                   capture_output=True, text=True)
                self.assertNotEqual(p.returncode, 0, "an impossible slice must be refused")
                with self.assertRaises(ValueError):
                    bsess.run(MASTER, 4, total, first, count, FAB, VIEW, truth=TRUTH, masks=MASKS)

    def test_the_whole_experiment_in_one_session_matches_the_prediction(self):
        """Nine pairs at the planned budget: the champions give the preregistered deltas."""
        got, ref = self._compare(budget=600, total=9, first=0, count=9)
        self.assertEqual(got["records"], bsess.records(9, 600))
        self.assertEqual(got["records"], 10820)
        best: dict[tuple[int, str], int] = {}
        for c in got["cands"]:
            if c["is_baseline"] or c["holdout"]:
                continue
            blk = json.loads(c["block"])
            best[(c["pair"], blk["arm"])] = blk["best"]
        deltas = [best[(r, "B")] - best[(r, "A")] for r in range(9)]
        pred = json.loads((R / "evidence/b2/prediction.json").read_text())
        self.assertEqual(deltas, pred["deltas"])


if __name__ == "__main__":
    unittest.main()
