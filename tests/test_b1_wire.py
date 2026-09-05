"""The B1 image's actual serialisation against the instrument's validator.

`firmware/b1/b1_wire.c` is the instrument's p3_wire.c with two additive changes: the
loop_record's `carto` block (1.2.0) and the app_identity's B1 fields (1.4.0). The twin's
`wire` mode renders both for fixed inputs through the SAME functions the image links; the
instrument's `validators.records.validate` must accept them (MAJOR 1, unknown minor fields
ignored), and the B1 fields must be present and sorted where the C writer put them."""
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

FW = R / "firmware/b1"
TWIN = FW / "build/b1_twin"
HAVE_CC = shutil.which(os.environ.get("CC", "cc")) is not None
HAVE_INSTRUMENT = inst.DEFAULT_ROOT.is_dir()


def wire() -> dict:
    subprocess.run(["make", "-s", "twin"], cwd=FW, check=True, capture_output=True)
    p = subprocess.run([str(TWIN), "wire"], capture_output=True, text=True, check=True)
    out = {}
    for line in p.stdout.splitlines():
        t, body = line.split(" ", 1)
        out[t] = (body, json.loads(body))
    return out


@unittest.skipUnless(HAVE_CC and HAVE_INSTRUMENT, "needs a host C compiler and the instrument checkout")
class Wire(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        from validators import records
        cls.records = records
        cls.w = wire()

    def test_identity_1_4_0_is_accepted_and_carries_the_b1_fields(self):
        body, ident = self.w["IDENT"]
        known = self.records.validate(ident)
        self.assertEqual(known["schema"], "app_identity")
        self.assertEqual(ident["schema_version"], "1.4.0")
        self.assertEqual(ident["carto_version"], "carto-v1")
        self.assertEqual(ident["probe_budget"], 333)
        self.assertEqual(ident["universe_sha256"], "895baf85ed31df9beae28a533646182ffb8d0e0735c9849ede9641af81ee7458")
        self.assertEqual(ident["schedule_mode"], "carto-v1")
        keys = list(ident.keys())
        self.assertEqual(keys, sorted(keys), "the writer emits sorted keys")

    def test_loop_record_1_2_0_with_carto_is_accepted(self):
        body, rec = self.w["REC"]
        known = self.records.validate(rec)          # the loop_record checker runs inside
        self.assertEqual(known["outcome"], "SCORED")
        self.assertEqual(rec["schema_version"], "1.2.0")
        self.assertNotIn("arm", rec)
        c = rec["carto"]
        self.assertEqual(c["version"], "carto-v1")
        self.assertEqual(c["phase"], "code")
        self.assertRegex(c["map_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(len(c["changed"]), 2)
        keys = list(rec.keys())
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(list(c.keys()), sorted(c.keys()))

    def test_the_bytes_fit_the_boards_payload_buffer(self):
        body, rec = self.w["REC"]
        self.assertLess(len(body), 4096 - 512, "the record with a carto block must leave headroom in g_payload (4096)")


if __name__ == "__main__":
    unittest.main()
