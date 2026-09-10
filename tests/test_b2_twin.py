"""The B2 C search unit against the Python reference — evaluation by evaluation
(the discipline of B1's `test_b1_twin.py`).

The twin (`firmware/b2/build/b2_twin`) is compiled from the SAME `b2_search.c` the image
links. It is driven over a pipe: for every proposal the twin prints the parent's birth
index, the move kind and its bits, and the candidate genome; the harness answers with the
fabric's MEASURED readout for that genome (the additive model — what a correct instrument
returns), and the twin's fitness, best-so-far, generation boundaries, population state,
champion, column-move count and holdout value must equal the reference's.

Also compared: the RNG, the frozen pair-seed rule (with the archived-set exclusion the
image compiles in), the universe mask, the public target rule and F1 over both vector sets.
Skipped only without a host C compiler — and the skip says so.
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

FW = R / "firmware/b2"
TWIN = FW / "build/b2_twin"
HAVE_CC = shutil.which(os.environ.get("CC", "cc")) is not None
TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
VIEW = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
MASTER = bs.master_seed(bp.SESSION_LABEL, bp.INSTRUMENT_COMMIT)


def build_twin() -> None:
    p = subprocess.run(["make", "-s", "twin"], cwd=FW, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stdout + p.stderr)


def twin(mode: str, text: str) -> str:
    return subprocess.run([str(TWIN), mode], input=text, capture_output=True, text=True, check=True).stdout


def tables_hex(t: list[int]) -> str:
    return " ".join(f"{x:016x}" for x in t)


def drive(arm: int, landscape_seed: int, operator_seed: int, budget: int, unscored_at: int | None = None, pair: int = 0) -> dict:
    """Run the twin over the additive fabric; return everything it reported."""
    land = bl.Landscape("F1", landscape_seed, masks=MASKS, truth=TRUTH)
    p = subprocess.Popen([str(TWIN), "run"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert p.stdin and p.stdout
    out: dict = {"evals": [], "pops": [], "champion": None, "holdout": None, "blocks": [], "champion_block": ""}
    p.stdin.write(f"{arm} {landscape_seed} {operator_seed} {budget} {pair}\n{tables_hex(FAB(0))}\n")
    p.stdin.flush()
    while True:
        line = p.stdout.readline()
        if not line:
            break
        if line.startswith("EVAL"):
            head, ghex = line.split("|")
            parts = head.split()
            n = int(parts[1])
            rec = {"eval": n, "parent_born": int(parts[2]), "kind": "random" if int(parts[3]) == 0 else "column",
                   "bits": [int(x) for x in parts[4:]], "genome": bc.genome_from_hex(ghex.strip())}
            out["evals"].append(rec)
            if unscored_at is not None and n == unscored_at:
                p.stdin.write("UNSCORED\n")
            else:
                p.stdin.write(tables_hex(FAB(rec["genome"])) + "\n")
            p.stdin.flush()
        elif line.startswith("FIT"):
            head, rest = line.split("|")
            parts = head.split()
            out["evals"][-1].update(fit=int(parts[1]), best=int(parts[2]), selected=int(parts[3]))
            if int(parts[3]):
                out["pops"].append([tuple(int(y) for y in x.split(":")) for x in rest.split()])
        elif line.startswith("CHAMPION"):
            parts = line.split()
            out["champion"] = {"genome": bc.genome_from_hex(parts[1]), "fit": int(parts[2]), "column_moves": int(parts[3])}
            p.stdin.write(tables_hex(FAB(out["champion"]["genome"])) + "\n")
            p.stdin.flush()
        elif line.startswith("BLOCK"):
            block = line[len("BLOCK "):].strip()
            if out["holdout"] is None:
                out["blocks"].append(block)
            else:
                out["champion_block"] = block
                break
        elif line.startswith("HOLDOUT"):
            out["holdout"] = int(line.split()[1])
    p.stdin.close()
    p.stdout.close()
    p.wait()
    out["landscape"] = land
    return out


@unittest.skipUnless(HAVE_CC, "no host C compiler (CC): the twin cannot be built")
class Twin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_twin()
        excl, _ = bp.frozen_seed_exclusion()
        cls.seeds = bs.pair_seeds(MASTER, 9, exclude=excl)

    def test_rng_equals_the_instrument(self):
        cases = [(1, 5), (77, 292), (MASTER, 4), (0, 2), (4294967295, 64)]
        lines = twin("rng", "".join(f"{s} {n}\n" for s, n in cases)).split("\n")
        for (s, n), line in zip(cases, lines):
            r = bc.Rng(s)
            self.assertEqual(line.split(), [f"{r.next32():08x}", str(r.uniform(n))], (s, n))

    def test_pair_seeds_are_the_frozen_rule(self):
        got = [tuple(int(x) for x in l.split()) for l in twin("seeds", f"{MASTER} 9\n").splitlines() if l.strip()]
        self.assertEqual(got, self.seeds)
        self.assertEqual(len(got), 9)
        flat = [x for pair in got for x in pair]
        self.assertEqual(len(set(flat)), 18)
        excl, _ = bp.frozen_seed_exclusion()
        self.assertFalse(set(flat) & (excl | set(bs.EXCLUDED_SEEDS)))

    def test_universe_mask_and_target(self):
        for lseed, _ in self.seeds[:3]:
            lines = twin("landscape", f"{lseed}\n").splitlines()
            mask = [int(x, 16) for x in lines[0].split()[1:]]
            target = [int(x, 16) for x in lines[1].split()[1:]]
            self.assertEqual(mask, MASKS)
            self.assertEqual(target, bl.Landscape("F1", lseed, masks=MASKS, truth=TRUTH).target)
            for k in range(6):
                self.assertEqual(target[k] & ~mask[k], 0)

    def test_f1_over_both_vector_sets(self):
        import random
        rng = random.Random(11)
        lseed = self.seeds[0][0]
        land = bl.Landscape("F1", lseed, masks=MASKS, truth=TRUTH)
        cases = [0, land.optimum()] + [rng.getrandbits(bc.N) for _ in range(6)]
        text = "".join(f"{lseed} {tables_hex(FAB(g))}\n" for g in cases)
        lines = [l.split() for l in twin("fitness", text).splitlines() if l.strip()]
        for g, parts in zip(cases, lines):
            t = FAB(g)
            self.assertEqual((int(parts[1]), int(parts[2])), (land.train_fitness(t), land.holdout_fitness(t)))

    def _compare(self, arm: int, lseed: int, oseed: int, budget: int, pair: int = 0):
        got = drive(arm, lseed, oseed, budget, pair=pair)
        land = got["landscape"]
        ref = bs.run(bs.ARM_RANDOM_SAFE if arm == 0 else bs.ARM_MAP_GUIDED, land, None if arm == 0 else VIEW,
                     oseed, budget, FAB, log_moves=True, pair=pair)
        self.assertEqual(len(got["evals"]), len(ref.moves), "evaluation count")
        for c, r in zip(got["evals"], ref.moves):
            self.assertEqual((c["parent_born"], c["kind"], c["bits"], c["fit"]),
                             (r["parent_born"], r["kind"], r["bits"], r["fit"]), f"eval {c['eval']}")
        self.assertEqual([c["best"] for c in got["evals"]], ref.best_trace, "best-so-far trace")
        self.assertEqual(got["pops"], [[tuple(x) for x in g] for g in ref.population_trace], "population after each selection")
        self.assertEqual(got["champion"]["genome"], ref.champion.genome, "champion genome")
        self.assertEqual(got["champion"]["fit"], ref.champion.fit, "champion fitness")
        self.assertEqual(got["champion"]["column_moves"], ref.column_moves, "column moves")
        self.assertEqual(got["holdout"], ref.champion_holdout, "champion holdout")
        self.assertEqual(len(got["blocks"]), len(got["evals"]), "one record block per evaluation")
        self.assertEqual(got["blocks"], ref.blocks, "the `search` record block, byte for byte")
        self.assertEqual(got["champion_block"], ref.champion_block, "the champion's holdout record block")
        for b in got["blocks"] + [got["champion_block"]]:
            doc = json.loads(b)                                  # the image writes valid, sorted-key JSON
            self.assertEqual(b, json.dumps(doc, sort_keys=True, separators=(",", ":")))
        return got, ref

    def test_random_safe_arm_over_budgets(self):
        lseed, oseed = self.seeds[0]
        for budget in (0, 1, 7, 8, 9, 16, 64, 600):
            with self.subTest(budget=budget):
                got, ref = self._compare(0, lseed, oseed, budget)
                self.assertEqual(got["champion"]["column_moves"], 0)

    def test_map_guided_arm_over_budgets(self):
        lseed, oseed = self.seeds[0]
        for budget in (0, 1, 7, 8, 9, 16, 64, 600):
            with self.subTest(budget=budget):
                got, ref = self._compare(1, lseed, oseed, budget)
        self.assertGreater(got["champion"]["column_moves"], 0)

    def test_every_session_pair_at_the_planned_budget(self):
        for r, (lseed, oseed) in enumerate(self.seeds):
            for arm in (0, 1):
                with self.subTest(pair=r, arm=arm):
                    self._compare(arm, lseed, oseed, 600, pair=r)

    def test_the_session_deltas_are_the_prediction(self):
        """The twin's champions over the nine pairs give the preregistered deltas."""
        deltas = []
        for lseed, oseed in self.seeds:
            a = drive(0, lseed, oseed, 600)["champion"]["fit"]
            b = drive(1, lseed, oseed, 600)["champion"]["fit"]
            deltas.append(b - a)
        import json
        pred = json.loads((R / "evidence/b2/prediction.json").read_text())
        self.assertEqual(deltas, pred["deltas"])

    def test_an_unscored_proposal_stops_the_arm(self):
        lseed, oseed = self.seeds[0]
        got = drive(0, lseed, oseed, 64, unscored_at=20)
        self.assertEqual(len(got["evals"]), 20)
        self.assertIsNone(got["evals"][-1].get("fit"))          # the 20th was never scored
        self.assertIsNone(got["holdout"])                       # no champion holdout after a stop
        ref = bs.run(bs.ARM_RANDOM_SAFE, bl.Landscape("F1", lseed, masks=MASKS, truth=TRUTH), None, oseed, 19, FAB, log_moves=True)
        for c, r in zip(got["evals"][:19], ref.moves):
            self.assertEqual((c["parent_born"], c["bits"], c["fit"]), (r["parent_born"], r["bits"], r["fit"]))


if __name__ == "__main__":
    unittest.main()
