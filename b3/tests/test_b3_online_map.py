"""b3/host/b3_online_map.py — render, the fail-closed verifier, the ledger binding, accuracy against
the truth mapping, and the negatives; and that this is not the B1 map-lifecycle verifier."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    sys.path.insert(0, str(p))
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_online_map as om  # noqa: E402

TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
LAND = bl.Landscape("F1", 2468, masks=MASKS, truth=TRUTH)
BINDING = {"landscape_seed": 2468, "operator_seed": 9, "fitness": "F1", "budget": 300}


class OnlineMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = oa.run_online(LAND, 9, 300, FAB)
        cls.doc = om.render(cls.res.carto, BINDING, cls.res.ledger)

    def test_render_validates_and_is_bound_to_its_ledger(self):
        self.assertEqual(om.findings(self.doc, self.res.ledger), [])
        self.assertEqual(self.doc["schema"], "online_map")
        self.assertNotEqual(self.doc["schema"], "self_map")
        self.assertEqual(self.doc["decoded_count"], self.res.decoded_trace[-1])
        self.assertEqual(self.doc["ledger_entries"], 300)

    def test_accuracy_against_the_truth(self):
        acc = om.accuracy(self.doc, TRUTH)
        self.assertEqual(acc["wrong"], 0)
        self.assertEqual(acc["decoded"], self.doc["decoded_count"])
        self.assertEqual(acc["universe"], 292)
        self.assertGreater(acc["coverage"], 0.3)

    def test_negatives(self):
        d = json.loads(json.dumps(self.doc))
        d["schema_version"] = "9.9.9"
        self.assertTrue(any("schema" in f for f in om.findings(d)))
        d = json.loads(json.dumps(self.doc))
        d["entries"][0]["relation"]["init_index"] = d["entries"][1]["relation"]["init_index"]
        d["entries"][0]["relation"]["lut_index"] = d["entries"][1]["relation"]["lut_index"]
        self.assertTrue(any("two addresses" in f for f in om.findings(d)))
        d = json.loads(json.dumps(self.doc))
        d["entries"][0]["relation"]["init_index"] = (d["entries"][0]["relation"]["init_index"] + 1) % 64
        if not om.findings(d):
            self.assertEqual(om.accuracy(d, TRUTH)["wrong"], 1)
        d = json.loads(json.dumps(self.doc))
        d["ledger_sha256"] = "0" * 64
        self.assertTrue(any("ledger_sha256" in f for f in om.findings(d, self.res.ledger)))
        self.assertTrue(om.findings("not a document"))
        d = json.loads(json.dumps(self.doc))
        d["decoded_count"] += 1
        self.assertTrue(om.findings(d))

    def test_the_b1_verifier_is_not_applied(self):
        """The document has none of what B1's map lifecycle requires (code probes, interaction edges,
        confirmations) and the B3 verifier never imports that verifier."""
        src = (R / "b3/host/b3_online_map.py").read_text()
        self.assertNotIn("import verify_local_map", src)
        self.assertNotIn("from verify_local_map", src)
        for key in ("code_probes", "edges", "confirmed"):
            self.assertNotIn(key, json.dumps(self.doc))


if __name__ == "__main__":
    unittest.main()
