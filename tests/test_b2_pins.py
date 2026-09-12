"""host/b2_pins.py — the B2 pin table: every adjudication-critical file of this package, generated
from globs and verified fail-closed (a changed file, a missing file, a new file matching the globs
that the table does not list, a table that does not hash to the manifest's pin, a malformed table,
and B1's own table drifting under it)."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b2_manifest as bman  # noqa: E402
import b2_pins as bp  # noqa: E402

HAVE = (R / "evidence/b2/build_evidence.json").is_file()


def _manifest() -> dict:
    return bman.init(R / "evidence/b2/build_evidence.json")


class Table(unittest.TestCase):
    def test_the_generated_table_covers_the_decision_surface(self):
        t = bp.generate()
        names = set(t["files"])
        for must in ("host/b2_adjudicate.py", "host/b2_runner.py", "host/b2_records.py",
                     "host/b2_manifest.py", "host/b2_pins.py", "host/b2_search.py",
                     "host/b2_landscape.py", "host/b2_plan.py", "host/b2_session.py",
                     "host/b2_modelled_session.py", "host/gen_b2_data.py", "host/b3_online.py",
                     "firmware/b2/b2_app.c", "firmware/b2/b2_orch.c", "firmware/b2/b2_search.c",
                     "firmware/b2/b2_wire.c", "firmware/b2/p3_data.h", "firmware/b2/IMPORT.json",
                     "firmware/b2/bsp/build.sh", "firmware/b2/bsp/lscript.ld",
                     "schemas/self_map_v2.schema.json", "docs/b2_architecture.md",
                     "manifests/b1_instrument_pins.json",
                     # what the pinned harness test actually compiles and runs, and this
                     # repository's BSP inputs (the owner's P2-1 of 2026-09-12)
                     "tb/b2/hostapp/hostapp.c", "tb/b2/hostapp/build.sh",
                     "tb/b2/hostapp/hostbsp/xil_io.h", "tb/b2/hostapp/hostbsp/xparameters.h",
                     "firmware/b2/bsp/src/console.c", "firmware/b2/bsp/include/xparameters.h",
                     "tests/test_b2_adjudicate.py", "tests/test_b2_runner.py", "tests/test_b2_e2e.py",
                     "tests/test_b2_pins.py"):
            self.assertIn(must, names, must)
        self.assertEqual(t["file_count"], len(t["files"]))
        self.assertNotIn("manifests/b2_instrument_pins.json", names)      # never self-referential
        self.assertNotIn("manifests/b2_manifest.json", names)             # it pins the table
        self.assertNotIn("docs/b2_preregistration.md", names)             # pinned by its frozen hash

    @unittest.skipUnless(HAVE, "the B2 build evidence is absent")
    def test_verify_refuses_every_drift(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        t = bp.generate()
        pins = d / "pins.json"
        pins.write_text(json.dumps(t, indent=1, sort_keys=True) + "\n")
        m = _manifest()
        m["instrument_pins"] = {"path": "manifests/b2_instrument_pins.json", "sha256": bp.sha256_of(pins)}
        self.assertEqual(bp.verify(m, pins_path=pins)["files_verified"], t["file_count"])

        for bad, needle in (({"sha256": "0" * 64}, "does not hash"), ({"sha256": None}, "pins no"),
                            ({}, "pins no"), (None, "pins no"),
                            # type before use: these raised AttributeError (the owner's P2-2)
                            ("broken", "not a JSON object"), ([{}], "not a JSON object"),
                            (True, "not a JSON object"), (7, "not a JSON object"),
                            (0.5, "not a JSON object"), ("", "not a JSON object"),
                            ({"sha256": 7}, "not 64 lower-case hex"),
                            ({"sha256": "AB" * 32}, "not 64 lower-case hex"),
                            ({"sha256": "aa" * 31}, "not 64 lower-case hex"),
                            ({"sha256": ["x"]}, "not 64 lower-case hex")):
            with self.subTest(instrument_pins=bad):
                m2 = copy.deepcopy(m)
                m2["instrument_pins"] = bad
                with self.assertRaises(bp.PinRefusal) as cm:
                    bp.verify(m2, pins_path=pins)
                self.assertIn(needle, str(cm.exception))
        for bad in ("nope", [1], 7):
            with self.subTest(manifest=bad):
                with self.assertRaises(bp.PinRefusal) as cm:
                    bp.verify(bad, pins_path=pins)
                self.assertIn("not a JSON object", str(cm.exception))

        def table_at(doc: dict, name: str) -> tuple[Path, dict]:
            p = d / name
            p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
            mm = copy.deepcopy(m)
            mm["instrument_pins"] = {"path": "x", "sha256": bp.sha256_of(p)}
            return p, mm

        for how, needle in (("hash", "hash differs"), ("missing", "missing"),
                            ("short_digest", "not a 64-hex digest")):
            with self.subTest(how=how):
                t2 = copy.deepcopy(t)
                if how == "hash":
                    t2["files"]["host/b2_adjudicate.py"] = "f" * 64
                elif how == "missing":
                    t2["files"]["host/does_not_exist.py"] = "f" * 64
                else:
                    t2["files"]["host/b2_adjudicate.py"] = "f" * 10
                t2["file_count"] = len(t2["files"])
                p2, m2 = table_at(t2, f"pins_{how}.json")
                with self.assertRaises(bp.PinRefusal) as cm:
                    bp.verify(m2, pins_path=p2)
                self.assertIn(needle, str(cm.exception))

        t3 = copy.deepcopy(t)
        del t3["files"]["host/b2_records.py"]
        t3["file_count"] = len(t3["files"])
        p3, m3 = table_at(t3, "pins_short.json")
        with self.assertRaises(bp.PinRefusal) as cm:
            bp.verify(m3, pins_path=p3)
        self.assertIn("not in the table", str(cm.exception))

        for mutate, needle in ((lambda doc: doc.__setitem__("schema", "something_else"), "is not a b2_instrument_pins"),
                               (lambda doc: doc.__setitem__("schema_version", "9.9.9"), "is not a b2_instrument_pins"),
                               (lambda doc: doc.__setitem__("files", {}), "carries no file table"),
                               (lambda doc: doc.__setitem__("files", "nope"), "carries no file table"),
                               (lambda doc: doc.__setitem__("file_count", 1), "is not the")):
            with self.subTest(needle=needle):
                t4 = copy.deepcopy(t)
                mutate(t4)
                p4, m4 = table_at(t4, "pins_bad.json")
                with self.assertRaises(bp.PinRefusal) as cm:
                    bp.verify(m4, pins_path=p4)
                self.assertIn(needle, str(cm.exception))

        broken = d / "pins_notjson.json"
        broken.write_text("{nope")
        m5 = copy.deepcopy(m)
        m5["instrument_pins"] = {"path": "x", "sha256": bp.sha256_of(broken)}
        with self.assertRaises(bp.PinRefusal) as cm:
            bp.verify(m5, pins_path=broken)
        self.assertIn("not readable JSON", str(cm.exception))

        absent = d / "no_such_table.json"
        m6 = copy.deepcopy(m)
        m6["instrument_pins"] = {"path": "x", "sha256": "a" * 64}
        with self.assertRaises(bp.PinRefusal) as cm:
            bp.verify(m6, pins_path=absent)
        self.assertIn("is absent", str(cm.exception))

    @unittest.skipUnless(HAVE, "the B2 build evidence is absent")
    def test_b1s_own_table_is_verified_underneath(self):
        """The B2 image runs on the B1 carrier under the B1 instrument, so a drift there changes
        a B2 verdict too."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        shutil.copytree(R / "manifests", d / "manifests")
        b1 = json.loads((d / "manifests/b1_manifest.json").read_text())
        b1["pins"]["sha256"] = "0" * 64
        (d / "manifests/b1_manifest.json").write_text(json.dumps(b1))
        t = bp.generate()
        pins = d / "pins.json"
        pins.write_text(json.dumps(t, indent=1, sort_keys=True) + "\n")
        m = _manifest()
        m["instrument_pins"] = {"path": "x", "sha256": bp.sha256_of(pins)}
        with self.assertRaises(bp.PinRefusal) as cm:
            bp.verify(m, pins_path=pins, b1_root=d)
        self.assertIn("B1's instrument pin table", str(cm.exception))

    @unittest.skipUnless(HAVE, "the B2 build evidence is absent")
    def test_the_committed_table_matches_the_tree(self):
        """Fails whenever a pinned file was edited after `b2_pins.py --generate` — the
        regeneration is the last step before a commit."""
        self.assertTrue(bp.PINS.is_file(), "the committed pin table is absent")
        m = _manifest()
        self.assertEqual(m["instrument_pins"]["sha256"], bp.sha256_of(bp.PINS),
                         "the manifest initializer and the committed table disagree")
        bp.verify(m)

    @unittest.skipUnless(HAVE, "the B2 build evidence is absent")
    def test_a_malformed_pin_block_refuses_through_the_lifecycle_and_the_cli(self):
        """It raised AttributeError through both, and the CLI exited 1 with a traceback instead
        of its documented REFUSED exit 2 (the owner's P2-2 of 2026-09-12)."""
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        for bad in ("broken", [{}], True, 7):
            with self.subTest(instrument_pins=bad):
                m = _manifest()
                m["instrument_pins"] = bad
                with self.assertRaises(bman.Refusal) as cm:
                    bman.verify(m)
                self.assertIn("instrument pins", str(cm.exception))
                mp = d / "manifest.json"
                mp.write_text(json.dumps(m))
                p = subprocess.run([sys.executable, str(R / "host/b2_pins.py"), "--manifest", str(mp)],
                                   capture_output=True, text=True, cwd=R)
                self.assertEqual(p.returncode, 2, (p.returncode, p.stdout, p.stderr[-300:]))
                self.assertIn("REFUSED:", p.stderr)
                self.assertNotIn("Traceback", p.stderr)

    @unittest.skipUnless(HAVE, "the B2 build evidence is absent")
    def test_the_manifest_verifier_refuses_a_drifted_table(self):
        m = _manifest()
        m["instrument_pins"] = {"path": "manifests/b2_instrument_pins.json", "sha256": "0" * 64}
        with self.assertRaises(bman.Refusal) as cm:
            bman.verify(m)
        self.assertIn("instrument pins", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
