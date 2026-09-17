"""b3/host/b3_online_map.py — render; `verify(doc, ledger, truth)` as the single boundary (every missing or
wrong input a finding, never a pass), the fail-closed schema loading (absent / broken / invalid schema
files are named findings, not tracebacks); and that this is not the B1 map-lifecycle verifier."""
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

    def test_verify_passes_a_true_map_with_its_ledger(self):
        v = om.verify(self.doc, self.res.ledger, TRUTH)
        self.assertEqual(v["findings"], [])
        self.assertTrue(v["ok"])
        self.assertEqual(v["accuracy"]["wrong"], 0)
        self.assertEqual(v["accuracy"]["decoded"], self.res.decoded_trace[-1])
        self.assertEqual(v["accuracy"]["universe"], 292)
        self.assertEqual(self.doc["schema"], "online_map")
        self.assertEqual(self.doc["ledger_entries"], 300)

    def _bad(self, mutate):
        d = json.loads(json.dumps(self.doc))
        mutate(d)
        return d

    @staticmethod
    def _move_first_decode_to_a_free_position(d):
        """A wrong decode that keeps the document well-formed: a position no entry uses."""
        used = {(e["relation"]["lut_index"], e["relation"]["init_index"]) for e in d["entries"]}
        k, v = next((k, v) for k in range(6) for v in range(64) if (k, v) not in used)
        d["entries"][0]["relation"].update({"lut_index": k, "init_index": v})

    def test_every_missing_or_wrong_input_is_a_finding_not_a_pass(self):
        """The owner's counterexamples of 2026-09-17 on the previous verifier, each now refused."""
        cases = {
            "no ledger": (self.doc, None, TRUTH, "ledger"),
            "no truth": (self.doc, self.res.ledger, None, "truth"),
            "not a document": ("nope", self.res.ledger, TRUTH, "not a JSON object"),
            "budget 301 with 300 entries": (self._bad(lambda d: d["binding"].__setitem__("budget", 301)), self.res.ledger, TRUTH, "300 entries for a budget of 301"),
            "arbitrary carto_version": (self._bad(lambda d: d.__setitem__("carto_version", "whatever")), self.res.ledger, TRUTH, "carto_version"),
            "one decode moved to a wrong, unused position": (self._bad(self._move_first_decode_to_a_free_position), self.res.ledger, TRUTH, "wrong decode: address"),
            "ledger digest": (self._bad(lambda d: d.__setitem__("ledger_sha256", "0" * 64)), self.res.ledger, TRUTH, "ledger_sha256"),
            "ledger_entries count": (self._bad(lambda d: d.__setitem__("ledger_entries", 299)), self.res.ledger, TRUTH, "ledger_entries 299"),
            "final version": (self._bad(lambda d: d.__setitem__("map_version", d["map_version"] + 1)), self.res.ledger, TRUTH, "not the ledger's final"),
            "anomalies claimed": (self._bad(lambda d: d.__setitem__("anomalies", 1)), self.res.ledger, TRUTH, "anomalies"),
            "schema_version": (self._bad(lambda d: d.__setitem__("schema_version", "9.9.9")), self.res.ledger, TRUTH, "schema:"),
            "a position decoded twice": (self._bad(lambda d: d["entries"][0]["relation"].update(d["entries"][1]["relation"])), self.res.ledger, TRUTH, "two addresses"),
            "decoded_count": (self._bad(lambda d: d.__setitem__("decoded_count", d["decoded_count"] + 1)), self.res.ledger, TRUTH, "decoded_count"),
            "a shorter ledger": (self.doc, self.res.ledger[:-1], TRUTH, "ledger_entries 300 is not the ledger's 299"),
        }
        for name, (doc, ledger, truth, needle) in cases.items():
            with self.subTest(case=name):
                v = om.verify(doc, ledger, truth)
                self.assertFalse(v["ok"])
                self.assertTrue(any(needle in f for f in v["findings"]), (name, v["findings"]))
        # a wrong decode is a finding EVEN THOUGH the document is well-formed: the schema helper alone says nothing
        d = self._bad(self._move_first_decode_to_a_free_position)
        self.assertEqual(om.schema_findings(d), [])                       # well-formed ...
        self.assertFalse(om.verify(d, self.res.ledger, TRUTH)["ok"])       # ... and refused

    def test_the_schema_boundary_is_fail_closed_without_a_traceback(self):
        import tempfile
        d = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, d, True)
        orig = om.SCHEMA_PATH
        try:
            for name, content, needle in (("absent.json", None, "cannot be read"),
                                          ("broken.json", "{nope", "is not JSON"),
                                          ("invalid.json", json.dumps({"type": 5}), "not a valid JSON Schema")):
                with self.subTest(case=name):
                    p = d / name
                    if content is not None:
                        p.write_text(content)
                    om.SCHEMA_PATH = p
                    f = om.schema_findings(self.doc)
                    self.assertEqual(len(f), 1, f)
                    self.assertIn(needle, f[0])
                    v = om.verify(self.doc, self.res.ledger, TRUTH)
                    self.assertFalse(v["ok"])
        finally:
            om.SCHEMA_PATH = orig
        self.assertEqual(om.schema_findings(self.doc), [])

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
