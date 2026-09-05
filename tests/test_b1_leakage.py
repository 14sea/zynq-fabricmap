"""B1 leakage guards — the cartographer is closed-book by construction, not by trust.

The claim B1 makes is runtime-blind reconstruction by the executable: no LUT key, INIT
index, polarity or group table reaches the cartographer. These tests make that a fact
about bytes: the generated data header carries no operator tables and matches its
generator; the cartographer's sources include nothing but the pure derive layer and the
header; the built image (when present) contains none of the table strings the instrument's
two-operator image carried; the verbatim imports hash to the archived instrument's files;
and, behaviourally, the reference follows a permuted fixture instead of the truth and an
address-only guesser scores nowhere near it."""
from __future__ import annotations

import json
import re
import shutil
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b1_verify as bv  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

FW = R / "firmware/b1"
HEADER = FW / "p3_data.h"
IMAGE = FW / "bsp/out/b1_app.bin"
FORBIDDEN_TOKENS = ("P3_LUT_KEYS", "P3_LUT_LEN", "P3_LUT_BITS", "P3_MUTATION_BITS", "P3_OPERATOR_DATA_SHA256",
                    "CLBLL_L.", "CLBLM_L.", "init_index", "random_safe", "map_guided", "p3_search")
HAVE_INSTRUMENT = inst.DEFAULT_ROOT.is_dir()


class HeaderAndSources(unittest.TestCase):
    def test_header_carries_no_operator_tables_and_declares_it(self):
        text = HEADER.read_text()
        for tok in FORBIDDEN_TOKENS:
            self.assertNotIn(tok, text, tok)
        self.assertIn("B1_DATA_NO_OPERATOR_TABLES 1", text)
        self.assertRegex(text, r'B1_UNIVERSE_SHA256 "[0-9a-f]{64}"')

    @unittest.skipUnless(HAVE_INSTRUMENT, "the instrument checkout is not present")
    def test_header_is_fresh_from_the_generator(self):
        import gen_b1_data as gen
        self.assertEqual(gen.render_b1(require_git=False), HEADER.read_text())

    def test_cartographer_sources_include_only_the_pure_layer(self):
        for name in ("b1_carto.c", "b1_carto.h"):
            src = (FW / name).read_text()
            includes = set(re.findall(r'#include\s+"([^"]+)"', src))
            self.assertLessEqual(includes, {"b1_carto.h", "p3_derive.h"}, includes)
            for tok in FORBIDDEN_TOKENS:
                self.assertNotIn(tok, src, f"{name}: {tok}")
        app = (FW / "b1_app.c").read_text()
        for tok in ("P3_LUT", "P3_OPERATOR_DATA_SHA256", "p3_search_next", "P3_ARM_NAME", "P3_MODE_NAME"):
            self.assertNotIn(tok, app, tok)
        compile_lines = [l for l in (FW / "bsp/build.sh").read_text().splitlines() if l.startswith("for s in b1_app.c")]
        self.assertEqual(len(compile_lines), 1)
        self.assertNotIn("p3_search", compile_lines[0])
        self.assertIn("b1_carto.c", compile_lines[0])

    @unittest.skipUnless(IMAGE.is_file(), "the built image is not present (bsp/out is not committed)")
    def test_built_image_contains_no_table_strings(self):
        b = IMAGE.read_bytes()
        for tok in (b"CLBLL_L.", b"CLBLM_L.", b"P3_LUT", b"random_safe", b"map_guided"):
            self.assertNotIn(tok, b, tok)
        self.assertIn(b"carto-v1", b)
        self.assertIn(HEADER.read_text().split('B1_UNIVERSE_SHA256 "')[1][:64].encode(), b)


class Imports(unittest.TestCase):
    def test_verbatim_imports_hash_to_the_archived_instrument(self):
        imp = json.loads((FW / "IMPORT.json").read_text())
        pins = json.loads(inst.PINS.read_text())
        self.assertEqual(imp["source_commit"], pins["psoracle_commit"])
        import hashlib
        for rel, row in imp["files"].items():
            self.assertEqual(row["sha256"], pins["files"][rel], rel)
            local = R / row["copied_to"]
            if local.is_file() and not local.name.startswith("b1_"):
                self.assertEqual(hashlib.sha256(local.read_bytes()).hexdigest(), row["sha256"], f"{local} was edited")


class Behaviour(unittest.TestCase):
    def test_reference_follows_a_permuted_fixture_not_the_truth(self):
        truth = bm.truth_mapping()
        fab = bm.fixture("permuted", seed=5)
        r = bm.simulate(11, 400, fab)
        m = r["carto"]
        vs_fixture = sum(1 for i, e in enumerate(m.e) if (e.lut, e.init) == fab.mapping[i])
        vs_truth = sum(1 for i, e in enumerate(m.e) if (e.lut, e.init) == truth["mapping"][i])
        self.assertEqual(vs_fixture, bc.N)
        self.assertLess(vs_truth, 10)

    def test_address_only_baseline_scores_nowhere_near_the_reference(self):
        truth = bm.truth_mapping()
        base = bv.score(bm.address_only_baseline(truth), truth)
        ref = bv.score(bm.simulate(3, 400, bm.fixture("truth"))["carto"].map_dict(), truth)
        self.assertLess(base["precision"], 0.2)
        self.assertEqual(ref["precision"], 1.0)
        self.assertEqual(ref["recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
