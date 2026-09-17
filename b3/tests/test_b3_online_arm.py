"""b3/host/b3_online_arm.py — the online arm: trace-for-trace and entry-for-entry equivalence with the
B2-pinned `host/b3_online.run_online`; the 1.1.0 ledger validates and the frozen 1.0.0 refuses it;
the holdout has no entry and no map update; the replay reproduces every version, decode and state
commitment, and names a tampered entry; the end-to-end frozen-arm rule."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_online as frozen  # noqa: E402
import b3_online_arm as oa  # noqa: E402

TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
LAND = bl.Landscape("F1", 2468, masks=MASKS, truth=TRUTH)


def ledger_doc(res, budget, version="1.1.0"):
    return {"schema": "specimen_ledger", "schema_version": version,
            "binding": {"token": "00" * 16, "universe_sha256": "00" * 32, "image_sha256_lo32": "00000000", "landscape_seed": LAND.seed},
            "seed": 9, "fitness": "F1", "budget": budget, "anomalies": res.anomalies, "final_map_version": res.version_trace[-1],
            "entries": res.ledger}


def validator(schema_path: Path):
    import jsonschema
    schema = json.loads(schema_path.read_text())
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


class Equivalence(unittest.TestCase):
    def test_the_copy_reproduces_the_frozen_reference(self):
        mine = oa.run_online(LAND, 9, 600, FAB)
        ref = frozen.run_online(LAND, 9, 600, FAB, keep_ledger=True)
        self.assertEqual(mine.best_trace, ref.best_trace)
        self.assertEqual(mine.decoded_trace, ref.decoded_trace)
        self.assertEqual(mine.version_trace, ref.version_trace)
        self.assertEqual(mine.anomalies, ref.anomalies)
        self.assertEqual(mine.column_moves, ref.column_moves)
        self.assertEqual(len(mine.ledger), len(ref.ledger))
        for a, b in zip(mine.ledger, ref.ledger):
            a2 = dict(a)
            self.assertIn("anomalies", a2)
            del a2["anomalies"]
            self.assertEqual(a2, b)

    def test_the_committed_ideal_model_row_is_reproduced(self):
        row = json.loads((R / "evidence/b3/sim/raw_F1.json").read_text())["rows"][0]
        land = bl.Landscape("F1", row["landscape_seed"], masks=MASKS, truth=TRUTH)
        res = oa.run_online(land, row["operator_seed"], 3000, FAB, keep_ledger=False)
        grid = (100, 200, 300, 400, 600, 800, 1000, 1500, 2000, 3000)
        self.assertEqual([res.best_trace[b - 1] for b in grid], row["search"]["O"])
        self.assertEqual([res.decoded_trace[b - 1] for b in grid], row["online"]["decoded_at_grid"])
        self.assertEqual(res.anomalies, 0)


class Ledger(unittest.TestCase):
    def test_1_1_0_validates_and_the_frozen_1_0_0_refuses_the_entry(self):
        res = oa.run_online(LAND, 9, 64, FAB)
        v11 = validator(R / "b3/schemas/specimen_ledger.schema.json")
        self.assertEqual(list(v11.iter_errors(ledger_doc(res, 64))), [])
        bad = ledger_doc(res, 64)
        bad["entries"][0]["anomalies"] = -1
        self.assertTrue(list(v11.iter_errors(bad)))
        v10 = validator(R / "schemas/specimen_ledger.schema.json")
        errs = list(v10.iter_errors(ledger_doc(res, 64, version="1.0.0")))
        self.assertTrue(errs, "the frozen 1.0.0 entry must refuse the running anomaly count (that is why 1.1.0 exists)")
        self.assertTrue(any("anomalies" in e.message for e in errs))

    def test_the_holdout_has_no_entry_and_does_not_touch_the_map(self):
        res = oa.run_online(LAND, 9, 120, FAB)
        self.assertEqual(len(res.ledger), 120)
        self.assertEqual(res.ledger[-1]["map_version_after"], res.carto.version)
        self.assertEqual(res.ledger[-1]["anomalies"], res.carto.anomalies)
        self.assertEqual(res.champion_holdout, LAND.holdout_fitness(res.champion.tables))
        self.assertEqual(res.state_trace[-1], res.carto.state_sha256())

    def test_the_replay_reproduces_every_version_decode_and_commitment(self):
        res = oa.run_online(LAND, 9, 400, FAB)
        c = carto_mod.SpecimenCarto()
        for e, want_state in zip(res.ledger, res.state_trace):
            self.assertEqual(c.version, e["map_version"])
            newly = c.observe(e["intervention"], [tuple(p) for p in e["behaviour_delta"]])
            self.assertEqual(sorted(newly), sorted(i for i, _, _ in e["decoded"]))
            self.assertEqual(c.version, e["map_version_after"])
            self.assertEqual(c.anomalies, e["anomalies"])
            self.assertEqual(c.state_sha256(), want_state)
        replayed, f = oa.replay(res.ledger)
        self.assertEqual(f, [])
        self.assertEqual(replayed.snapshot(), res.carto.snapshot())

    def test_a_tampered_ledger_is_named_by_the_replay(self):
        res = oa.run_online(LAND, 9, 200, FAB)
        for how in ("decoded", "version", "delta"):
            with self.subTest(how=how):
                ledger = json.loads(json.dumps(res.ledger))
                target = next(e for e in ledger if e["decoded"])
                if how == "decoded":
                    target["decoded"] = []
                elif how == "version":
                    target["map_version_after"] += 1
                else:
                    k, v = target["behaviour_delta"][0]
                    target["behaviour_delta"][0] = [k, (v + 1) % 64]
                _, f = oa.replay(ledger)
                self.assertEqual(len(f), 1, f)
                self.assertIn(f"seq {target['seq']}", f[0])


class EndToEnd(unittest.TestCase):
    def test_the_frozen_arm_is_charged_333(self):
        trace = list(range(1, 1001))
        self.assertEqual(oa.end_to_end_frozen(trace, 2, 100), 2)
        self.assertEqual(oa.end_to_end_frozen(trace, 2, 333), 2)
        self.assertEqual(oa.end_to_end_frozen(trace, 2, 334), 1)
        self.assertEqual(oa.end_to_end_frozen(trace, 2, 1000), 667)
        self.assertEqual(oa.B1_MAP_COST, 333)
        self.assertEqual(bc.N, 292)


if __name__ == "__main__":
    unittest.main()
