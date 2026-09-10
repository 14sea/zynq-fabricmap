"""B3 online cartography from specimens: correctness against the truth, replayability from
the ledger, the schema, and the accounting (docs/b3_architecture.md)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_online as b3  # noqa: E402

TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
LAND = bl.Landscape("F1", 2468, masks=MASKS, truth=TRUTH)


def ledger_doc(res: b3.OnlineResult, budget: int) -> dict:
    return {"schema": "specimen_ledger", "schema_version": "1.0.0",
            "binding": {"token": "00" * 16, "universe_sha256": "00" * 32, "image_sha256_lo32": "00000000", "landscape_seed": LAND.seed},
            "seed": 1, "fitness": "F1", "budget": budget, "anomalies": res.anomalies, "final_map_version": res.version_trace[-1],
            "entries": res.ledger}


class Carto(unittest.TestCase):
    def test_single_bit_specimen_decodes_directly(self):
        c = b3.SpecimenCarto()
        i = 5
        k, v = TRUTH["mapping"][i]
        self.assertEqual(c.observe([i], [(k, v)]), [i])
        self.assertEqual(c.decoded[i], (k, v))
        self.assertEqual(c.version, 1)

    def test_multi_bit_specimens_narrow_then_decode(self):
        c = b3.SpecimenCarto()
        a, b, d = 1, 2, 3
        pa, pb, pd = TRUTH["mapping"][a], TRUTH["mapping"][b], TRUTH["mapping"][d]
        self.assertEqual(c.observe([a, b], [pa, pb]), [])            # {a,b} -> {pa,pb}: narrowed, nothing decoded
        newly = c.observe([a, d], [pa, pd])                          # a by intersection, then d and b by exclusion
        self.assertEqual(sorted(newly), [a, b, d])
        self.assertEqual(c.version, 1)
        self.assertEqual(c.decoded[a], pa)
        self.assertEqual(c.decoded[b], pb)
        self.assertEqual(c.decoded[d], pd)

    def test_anomaly_on_size_mismatch_and_empty_intersection(self):
        c = b3.SpecimenCarto()
        self.assertEqual(c.observe([1, 2], [TRUTH["mapping"][1]]), [])
        self.assertEqual(c.anomalies, 1)
        c.observe([7, 8], [TRUTH["mapping"][7], TRUTH["mapping"][8]])
        c.observe([7, 9], [TRUTH["mapping"][11], TRUTH["mapping"][9]])   # inconsistent for 7
        self.assertEqual(c.anomalies, 2)

    def test_positions_of(self):
        self.assertEqual(b3.positions_of([0b101, 0, 0, 0, 1 << 63, 0]), [(0, 0), (0, 2), (4, 63)])


class Online(unittest.TestCase):
    def test_no_wrong_decode_and_full_map_by_budget(self):
        res = b3.run_online(LAND, 9, 2000, FAB)
        wrong = [(i, k, v) for e in res.ledger for i, k, v in e["decoded"] if TRUTH["mapping"][i] != (k, v)]
        self.assertEqual(wrong, [])
        self.assertEqual(res.anomalies, 0)
        self.assertEqual(res.decoded_trace[-1], bc.N)
        self.assertEqual(len(res.ledger), 2000)
        self.assertTrue(all(a <= b for a, b in zip(res.decoded_trace, res.decoded_trace[1:])))

    def test_starts_as_random_safe(self):
        # before any decode, the online arm's moves are random-safe moves from the same stream
        res = b3.run_online(LAND, 9, 1, FAB)
        self.assertEqual(res.ledger[0]["move_kind"], "random")
        self.assertEqual(res.ledger[0]["map_version"], 0)

    def test_ledger_replays_every_map_version(self):
        res = b3.run_online(LAND, 9, 600, FAB)
        c = b3.SpecimenCarto()
        for e in res.ledger:
            self.assertEqual(c.version, e["map_version"])
            newly = c.observe(e["intervention"], [tuple(p) for p in e["behaviour_delta"]])
            self.assertEqual(sorted(newly), sorted(i for i, _, _ in e["decoded"]))
            self.assertEqual(c.version, e["map_version_after"])
        self.assertEqual(len(c.decoded), res.decoded_trace[-1])

    def test_deterministic(self):
        a = b3.run_online(LAND, 9, 300, FAB)
        b = b3.run_online(LAND, 9, 300, FAB)
        self.assertEqual(a.best_trace, b.best_trace)
        self.assertEqual(a.ledger, b.ledger)

    def test_ledger_validates(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("no jsonschema")
        schema = json.loads((R / "schemas/specimen_ledger.schema.json").read_text())
        res = b3.run_online(LAND, 9, 64, FAB)
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        errors = list(cls(schema).iter_errors(ledger_doc(res, 64)))
        self.assertEqual(errors, [])
        bad = ledger_doc(res, 64)
        bad["entries"][0]["confidence"] = 3
        self.assertTrue(list(cls(schema).iter_errors(bad)))



class ReviewRegressions(unittest.TestCase):
    """docs/b2_b3_host_review_2026_09_10.md §2, third finding: the three counterexamples
    (evidence/b2/review_2026_09_10/reproduce_findings.py) and the atomicity guarantee."""

    P, Q, RR, T, U = (0, 0), (0, 1), (0, 2), (0, 3), (0, 4)

    def test_decoded_contradiction_is_an_anomaly_and_changes_nothing(self):
        c = b3.SpecimenCarto()
        c.observe([0], [self.P])
        before = c.snapshot()
        self.assertEqual(c.observe([0], [self.Q]), [])
        self.assertEqual(c.anomalies, 1)
        self.assertEqual(c.snapshot(), before)

    def test_mixed_specimen_omitting_a_known_position_is_refused(self):
        c = b3.SpecimenCarto()
        c.observe([0], [self.P])
        before = c.snapshot()
        self.assertEqual(c.observe([0, 1], [self.Q, self.RR]), [])
        self.assertEqual(c.anomalies, 1)
        self.assertEqual(c.snapshot(), before)
        self.assertNotIn(1, c.candidates)

    def test_mixed_specimen_with_the_known_position_narrows_the_rest(self):
        c = b3.SpecimenCarto()
        c.observe([0], [self.P])
        self.assertEqual(c.observe([0, 1], [self.P, self.RR]), [1])
        self.assertEqual(c.decoded[1], self.RR)
        self.assertEqual(c.anomalies, 0)

    def test_refusal_is_atomic(self):
        c = b3.SpecimenCarto()
        c.observe([0, 2], [self.P, self.Q])
        c.observe([1, 3], [self.RR, self.T])
        before = c.snapshot()
        self.assertEqual(c.observe([0, 1], [self.P, self.U]), [])       # 1 cannot be at U: empty intersection
        self.assertEqual(c.anomalies, 1)
        self.assertEqual(c.snapshot(), before)
        self.assertEqual(c.candidates[0], {self.P, self.Q})

    def test_position_of_an_unmoved_decoded_address_is_refused(self):
        c = b3.SpecimenCarto()
        c.observe([0], [self.P])
        before = c.snapshot()
        self.assertEqual(c.observe([1], [self.P]), [])
        self.assertEqual(c.anomalies, 1)
        self.assertEqual(c.snapshot(), before)

    def test_closure_conflict_is_refused_atomically(self):
        c = b3.SpecimenCarto()
        c.observe([0, 1], [self.P, self.Q])         # {0,1} -> {P,Q}
        c.observe([2, 3], [self.P, self.Q])         # {2,3} -> {P,Q}: four addresses, two positions — consistent so far
        before = c.snapshot()
        # decoding 0 at P would leave 1 at Q, then 2 and 3 both need Q — a closure conflict
        self.assertEqual(c.observe([0], [self.P]), [])
        self.assertEqual(c.anomalies, 1)
        self.assertEqual(c.snapshot(), before)

    def test_malformed_specimens_are_refused(self):
        c = b3.SpecimenCarto()
        for moved, delta in (([0, 0], [self.P, self.Q]), ([0], [(6, 0)]), ([0], [(0, 64)]), ([0, 1], [self.P, self.P]), ([], []), ([999], [self.P])):
            before = c.snapshot()
            self.assertEqual(c.observe(moved, delta), [])
            self.assertEqual(c.snapshot(), before)
        self.assertEqual(c.anomalies, 6)

    def test_ideal_model_run_is_unchanged_by_the_correction(self):
        # the committed B3 simulation (carto v1) row 0 for F1 must be reproduced by carto v1.1
        raw = R / "evidence/b3/sim/raw_F1.json"
        if not raw.exists():
            self.skipTest("no committed B3 rows")
        row = json.loads(raw.read_text())["rows"][0]
        land = bl.Landscape("F1", row["landscape_seed"], masks=MASKS, truth=TRUTH)
        res = b3.run_online(land, row["operator_seed"], 3000, FAB)
        grid = (100, 200, 300, 400, 600, 800, 1000, 1500, 2000, 3000)
        self.assertEqual([res.best_trace[b - 1] for b in grid], row["search"]["O"])
        self.assertEqual([res.decoded_trace[b - 1] for b in grid], row["online"]["decoded_at_grid"])
        self.assertEqual(res.anomalies, 0)

if __name__ == "__main__":
    unittest.main()
