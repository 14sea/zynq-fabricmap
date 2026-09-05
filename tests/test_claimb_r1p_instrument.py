"""host/claimb_r1p_instrument.py — the read-only binding to the archived P3 instrument.

The instrument is used exactly as committed at the pinned archive head, or not at all. The
pin table is regenerated from the checkout and must equal the committed one; a table with
one altered hash, a manifest pinning another commit, and a missing checkout are each a
named refusal. Tests that need the checkout skip without it — a skip is not a pass, and
the package's clean-tree test report records the skip count."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

MANIFEST = json.loads(inst.MANIFEST.read_text())
PINS = json.loads(inst.PINS.read_text())
HAVE = inst.DEFAULT_ROOT.is_dir() and (inst.DEFAULT_ROOT / ".git").exists()


class PinTable(unittest.TestCase):
    def test_table_names_the_manifest_commit_and_every_pinned_file(self):
        self.assertEqual(PINS["psoracle_commit"], MANIFEST["instrument"]["psoracle_commit"])
        for f in inst.PINNED_FILES:
            self.assertIn(f, PINS["files"])
        self.assertEqual(PINS["file_count"], len(PINS["files"]))
        for rel, sha in PINS["files"].items():
            self.assertRegex(sha, r"^[0-9a-f]{64}$", rel)

    def test_table_pins_the_authority_files_by_name(self):
        for rel in ("host/l6_runner.py", "host/l6_operators.py", "host/l6_schedule.py", "host/l6_soak_plan.py",
                    "host/p3_oracle.py", "validators/records.py", "scripts/board_session.py",
                    "manifests/l6_manifest.json", "builds/p3/p3.bit", "builds/p3/carrier_manifest.json",
                    "imported/fabricmap/vivado/carrier/generated/carrier_constants.json"):
            self.assertIn(rel, PINS["files"], rel)

    @unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
    def test_regenerated_table_equals_the_committed_one(self):
        gen = inst.generate_pins(inst.DEFAULT_ROOT)
        self.assertEqual(gen["psoracle_commit"], PINS["psoracle_commit"])
        self.assertEqual(gen["files"], PINS["files"])

    @unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
    def test_verify_passes_and_bind_puts_the_instrument_first(self):
        v = inst.bind(inst.DEFAULT_ROOT)
        self.assertEqual(v["files_verified"], PINS["file_count"])
        self.assertEqual(Path(sys.path[0]), inst.DEFAULT_ROOT / "scripts")
        import l6_schedule  # noqa: F401
        self.assertTrue(Path(l6_schedule.__file__).resolve().is_relative_to(inst.DEFAULT_ROOT.resolve()))


class Refusals(unittest.TestCase):
    def _tampered(self, mutate) -> Path:
        pins = copy.deepcopy(PINS)
        mutate(pins)
        d = Path(tempfile.mkdtemp())
        p = d / "pins.json"
        p.write_text(json.dumps(pins))
        return p

    def test_a_table_from_another_commit_is_refused(self):
        p = self._tampered(lambda x: x.update(psoracle_commit="0" * 40))
        with self.assertRaises(inst.InstrumentRefusal) as cm:
            inst.verify(inst.DEFAULT_ROOT, pins_path=p, require_git=False)
        self.assertIn("generated from", str(cm.exception))

    @unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
    def test_one_altered_hash_is_refused_by_name(self):
        def mutate(x):
            x["files"]["host/l6_runner.py"] = "f" * 64
        p = self._tampered(mutate)
        with self.assertRaises(inst.InstrumentRefusal) as cm:
            inst.verify(inst.DEFAULT_ROOT, pins_path=p, require_git=False)
        self.assertIn("host/l6_runner.py", str(cm.exception))

    def test_a_missing_checkout_is_refused(self):
        with self.assertRaises(inst.InstrumentRefusal) as cm:
            inst.verify(Path("/nonexistent/zynq_psoracle"), require_git=False)
        self.assertIn("no instrument checkout", str(cm.exception))

    def test_a_manifest_pinning_another_commit_is_refused(self):
        m = copy.deepcopy(MANIFEST)
        m["instrument"]["psoracle_commit"] = "1" * 40
        with self.assertRaises(inst.InstrumentRefusal):
            inst.verify(inst.DEFAULT_ROOT, manifest=m, require_git=False)


if __name__ == "__main__":
    unittest.main()
