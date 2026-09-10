"""The bytes the B2 image actually emits, fed to the real host validator
(the discipline of B1's `test_b1_wire.py`).

`firmware/b2/build/b2_twin wire` runs `b2_wire.c` and `b2_search.c` — the units the image
links — and prints one `app_identity` 1.5.0 and one `loop_record` 1.3.0 with a `search`
block. Those bytes go through `host/b1_records.validate`, which is the instrument's
validator: a green test here is evidence about what the board will put on the wire, not
about a model of it.
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
import claimb_r1p_instrument as inst  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402

FW = R / "firmware/b2"
TWIN = FW / "build/b2_twin"
HAVE_CC = shutil.which(os.environ.get("CC", "cc")) is not None
B2_ONLY_IDENTITY = ("search_version", "map_sha256", "fitness_id", "budget_per_arm", "pairs_total", "pair_first", "pair_count")


@unittest.skipUnless(HAVE_CC, "no host C compiler (CC): the twin cannot be built")
class Wire(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = subprocess.run(["make", "-s", "twin"], cwd=FW, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stdout + p.stderr)
        out = subprocess.run([str(TWIN), "wire"], capture_output=True, text=True, check=True).stdout
        cls.raw = {}
        for line in out.splitlines():
            tag, doc = line.split(" ", 1)
            cls.raw[tag] = doc
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import b1_records as br  # noqa: E402  (needs the bound instrument package)
        cls.br = br

    def test_both_documents_validate_under_the_instrument_validator(self):
        for tag in ("IDENT", "REC"):
            with self.subTest(tag=tag):
                self.br.validate(json.loads(self.raw[tag]))

    def test_both_are_compact_sorted_key_json(self):
        for tag, doc in self.raw.items():
            got = json.loads(doc)
            self.assertEqual(doc, json.dumps(got, sort_keys=True, separators=(",", ":")), tag)

    def test_identity_declares_what_this_image_is(self):
        d = json.loads(self.raw["IDENT"])
        self.assertEqual(d["schema"], "app_identity")
        self.assertEqual(d["schema_version"], "1.5.0")
        for k in B2_ONLY_IDENTITY:
            self.assertIn(k, d, k)
        self.assertEqual(d["search_version"], bs.ENGINE_VERSION)
        self.assertEqual(d["fitness_id"], "F1")
        self.assertEqual(d["map_sha256"], bmaps.sha256_of(bmaps.load_self_map()))
        self.assertEqual(d["master_seed"], bs.master_seed(bp.SESSION_LABEL, bp.INSTRUMENT_COMMIT))
        self.assertEqual(d["carrier_variant"], "0x42310001")
        self.assertEqual(d["control_plane"], "standalone")
        self.assertEqual(d["protocol"], "rel-v4")
        # this image runs no cartographer and issues no probes: it must not claim to
        self.assertNotIn("carto_version", d)
        self.assertNotIn("probe_budget", d)

    def test_the_pair_slice_is_the_session_and_not_the_experiment(self):
        d = json.loads(self.raw["IDENT"])
        self.assertEqual(d["pairs_total"], 9)
        self.assertLessEqual(d["pair_first"] + d["pair_count"], d["pairs_total"])
        self.assertGreater(d["pair_count"], 0)

    def test_record_carries_the_search_block(self):
        d = json.loads(self.raw["REC"])
        self.assertEqual(d["schema"], "loop_record")
        self.assertEqual(d["schema_version"], "1.3.0")
        self.assertEqual(d["outcome"], "SCORED")
        self.assertEqual(d["verified"], "audited")
        self.assertEqual(d["arm"], "map_guided")
        self.assertNotIn("carto", d)
        b = d["search"]
        self.assertEqual(sorted(b), ["arm", "best", "column_moves", "eval", "fitness", "generation", "holdout",
                                     "landscape_seed", "move", "operator_seed", "pair", "parent_born",
                                     "population", "selected", "state_sha256", "version"])
        self.assertEqual(b["version"], bs.ENGINE_VERSION)
        self.assertEqual(b["arm"], "B")
        self.assertEqual(len(b["population"]), bs.MU)
        self.assertEqual(len(b["state_sha256"]), 64)
        self.assertTrue(1 <= len(b["move"]["bits"]) <= bs.KMAX)
        self.assertIn(b["move"]["kind"], ("random", "column"))

    def test_the_evidence_members_are_the_instrument_s(self):
        d = json.loads(self.raw["REC"])
        ev = d["evidence"]
        for member in ("sign_reply", "app_oracle_record", "arm", "score"):
            self.assertIn(member, ev, member)


if __name__ == "__main__":
    unittest.main()
