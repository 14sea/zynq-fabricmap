"""host/b1_pins.py — the B1 pin table: every adjudication-critical fabricmap file, generated
from globs, verified fail-closed (a changed file, a missing file, a new file matching the
globs that is not in the table, a table that does not hash to the manifest's pin)."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_pins as bp  # noqa: E402

MANIFEST = json.loads(bp.MANIFEST.read_text())


class Table(unittest.TestCase):
    def test_the_generated_table_covers_the_critical_files(self):
        t = bp.generate()
        names = set(t["files"])
        for must in ("host/b1_adjudicate.py", "host/b1_records.py", "host/b1_sign_arm.py", "host/b1_carto.py", "host/b1_verify.py",
                     "host/b1_runner.py", "host/b1_pins.py", "firmware/b1/b1_app.c", "firmware/b1/b1_carto.c", "firmware/b1/b1_orch.c",
                     "rtl/b1/b1_arm_gate.v", "rtl/b1/b1_axil.v", "schemas/self_map_v2.schema.json",
                     "host/b1q_adjudicate.py", "host/b1_qualification.py", "host/b1q_runner.py", "host/b1_manifest.py",
                     "docs/b1_carrier_contract.md", "docs/b1_carrier_qualification.md", "docs/b1_architecture.md",
                     "manifests/claimb_round1prime_instrument_pins.json", "tests/test_b1_adjudicate.py"):
            self.assertIn(must, names, must)
        self.assertEqual(t["file_count"], len(t["files"]))
        self.assertNotIn("manifests/b1_instrument_pins.json", names)       # never self-referential

    def test_verify_refuses_every_drift(self):
        d = Path(tempfile.mkdtemp())
        t = bp.generate()
        pins = d / "pins.json"; pins.write_text(json.dumps(t, indent=1, sort_keys=True) + "\n")
        m = copy.deepcopy(MANIFEST); m["pins"]["sha256"] = bp.sha256_of(pins)
        self.assertEqual(bp.verify(pins, m)["files_verified"], t["file_count"])
        # the manifest pins another table
        m2 = copy.deepcopy(m); m2["pins"]["sha256"] = "0" * 64
        with self.assertRaises(bp.PinRefusal): bp.verify(pins, m2)
        m2 = copy.deepcopy(m); m2["pins"]["sha256"] = None
        with self.assertRaises(bp.PinRefusal): bp.verify(pins, m2)
        # a pinned file's hash differs / a pinned file is missing
        for how in ("hash", "missing"):
            t2 = copy.deepcopy(t)
            k = "host/b1_adjudicate.py"
            if how == "hash":
                t2["files"][k] = "f" * 64
            else:
                t2["files"]["host/does_not_exist.py"] = "f" * 64
            p2 = d / f"pins_{how}.json"; p2.write_text(json.dumps(t2, indent=1, sort_keys=True) + "\n")
            m2 = copy.deepcopy(m); m2["pins"]["sha256"] = bp.sha256_of(p2)
            with self.assertRaises(bp.PinRefusal) as cm: bp.verify(p2, m2)
            self.assertIn("hash differs" if how == "hash" else "missing", str(cm.exception))
        # a file matching the globs that the table does not list
        t3 = copy.deepcopy(t); del t3["files"]["host/b1_records.py"]
        p3 = d / "pins_short.json"; p3.write_text(json.dumps(t3, indent=1, sort_keys=True) + "\n")
        m3 = copy.deepcopy(m); m3["pins"]["sha256"] = bp.sha256_of(p3)
        with self.assertRaises(bp.PinRefusal) as cm: bp.verify(p3, m3)
        self.assertIn("not in the table", str(cm.exception))

    def test_the_committed_table_matches_the_tree(self):
        """Fails whenever a pinned file was edited after `b1_pins.py --generate` — the
        regeneration is the last step before a commit."""
        if not bp.PINS.is_file():
            self.skipTest("no committed pin table yet")
        bp.verify(bp.PINS, MANIFEST)


if __name__ == "__main__":
    unittest.main()
