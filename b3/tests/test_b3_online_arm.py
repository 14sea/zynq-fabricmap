"""b3/host/b3_online_arm.py — the online arm: trace-for-trace and entry-for-entry equivalence with the
B2-pinned `host/b3_online.run_online`; the 1.1.0 ledger validates and the frozen 1.0.0 refuses it;
the holdout has no entry and no map update; the combined record commitment (B2's search state text
joined to the cartographer's text — held to B2's own function, and load-bearing in both halves); the
replay reproduces every version, decode and commitment and names a tampered entry, a tampered
commitment and a half-given commitment check; the end-to-end frozen-arm rule."""
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
        self.assertEqual(res.carto_state_trace[-1], res.carto.state_text())
        self.assertEqual(len(res.state_trace), 120)
        self.assertEqual(len(res.search_state_trace), 120)

    def test_the_replay_reproduces_every_version_decode_and_commitment(self):
        res = oa.run_online(LAND, 9, 400, FAB)
        c = carto_mod.SpecimenCarto()
        for e, ctext, stext, want in zip(res.ledger, res.carto_state_trace, res.search_state_trace, res.state_trace):
            self.assertEqual(c.version, e["map_version"])
            newly = c.observe(e["intervention"], [tuple(p) for p in e["behaviour_delta"]])
            self.assertEqual(sorted(newly), sorted(i for i, _, _ in e["decoded"]))
            self.assertEqual(c.version, e["map_version_after"])
            self.assertEqual(c.anomalies, e["anomalies"])
            self.assertEqual(c.state_text(), ctext)
            self.assertEqual(oa.state_sha256(stext, ctext), want)
        # the production replay, with the commitments: clean
        replayed, f = oa.replay(res.ledger, res.search_state_trace, res.state_trace)
        self.assertEqual(f, [])
        self.assertEqual(replayed.snapshot(), res.carto.snapshot())
        # a tampered commitment is named at its entry
        bad = list(res.state_trace)
        bad[77] = "0" * 64
        _, f = oa.replay(res.ledger, res.search_state_trace, bad)
        self.assertEqual(len(f), 1)
        self.assertIn("seq 78: state_sha256", f[0])
        # a tampered search state (the population) is named through the commitment
        bad_s = list(res.search_state_trace)
        bad_s[5] = bad_s[5].replace(";", ";9:9:00;", 1)
        _, f = oa.replay(res.ledger, bad_s, res.state_trace)
        self.assertEqual(len(f), 1)
        self.assertIn("seq 6: state_sha256", f[0])
        # a half-given check is a named finding, never a silent skip
        for args in ((res.search_state_trace, None), (None, res.state_trace), (res.search_state_trace[:-1], res.state_trace)):
            _, f = oa.replay(res.ledger, *args)
            self.assertEqual(len(f), 1, args)
            self.assertIn("commitment check", f[0])

    def test_the_commitment_is_b2s_text_plus_the_cartographer_and_load_bearing_in_both_halves(self):
        res = oa.run_online(LAND, 9, 96, FAB)
        # the search half is byte for byte what b2_search.state_sha256 hashes (checked through B2's own function)
        pop = [bs.Individual(3, [0] * 6, 7, born=1), bs.Individual(0, [0] * 6, 2, born=0)]
        text = oa.search_state_text(1, 11, 22, 600, 33, 4, 7, pop)
        import hashlib
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), bs.state_sha256(1, 11, 22, 600, 33, 4, 7, pop))
        self.assertTrue(text.startswith(f"{bs.ENGINE_VERSION}|1|11|22|600|33|4|7|"))
        # control 1: the search state changes, the cartographer does not -> the digest changes
        stext, ctext = res.search_state_trace[-1], res.carto_state_trace[-1]
        self.assertEqual(oa.state_sha256(stext, ctext), res.state_trace[-1])
        other_pop = oa.search_state_text(oa.ARM_CODE, LAND.seed, 9, 96, 96, 12, res.best_trace[-1] + 1, [])
        self.assertNotEqual(oa.state_sha256(other_pop, ctext), res.state_trace[-1])
        # control 2: the cartographer changes, the search state does not -> the digest changes
        c2 = carto_mod.SpecimenCarto()
        for e in res.ledger:
            c2.observe(e["intervention"], [tuple(p) for p in e["behaviour_delta"]])
        self.assertEqual(c2.state_text(), ctext)
        free = next(i for i in range(292) if i not in c2.decoded)
        c2.observe([free], [TRUTH["mapping"][free]])           # one more decode
        self.assertNotEqual(c2.state_text(), ctext)
        self.assertNotEqual(oa.state_sha256(stext, c2.state_text()), res.state_trace[-1])
        self.assertEqual(oa.ARM_CODE, 2)

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
