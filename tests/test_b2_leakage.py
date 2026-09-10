"""The B2 image's guards: what is compiled in, what is not, and that the imports are the
instrument's bytes (B1's `test_b1_leakage.py`, re-aimed at stage B2's boundary).

B1's question was to RECOVER the map, so its image was forbidden every LUT key, INIT index,
polarity and group table. B2's question is whether that map is USEFUL, so the map itself —
the board's own product of stage B1 — is legitimately compiled in, and the guard moves:

  * the certificate and its derivations (`local_map`, the LUT SITE KEYS, polarity, groups)
    stay forbidden: the image must carry the board's answer, not the ground truth's file;
  * the map compiled in must be the COMMITTED B1 map, by canonical digest and by file digest;
  * the header must be fresh from its generator, so the tables cannot drift from the map;
  * the search unit must include only its own header, the data header and the imported
    derive unit — never the landscape's Python, never a certificate reader;
  * every verbatim import must still hash to its byte — the instrument's for the firmware
    units, B1's for the BSP scaffold — and every derived file must exist and differ from its
    base (`firmware/b2/IMPORT.json`);
  * when the built image is present, its bytes are scanned for the same forbidden tokens
    and required to contain the engine version and the map digest.

The source scan is a source-level guard, NOT a substitute for that binary scan: it reads C
lexically, and a token reachable only at run time would not appear in it. The stripper's own
fixtures below exist because a regex version silently deleted string data (the owner's core
review of 2026-09-10, P3).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b2_maps as bmaps  # noqa: E402
import gen_b2_data as gen  # noqa: E402

FW = R / "firmware/b2"
HEADER = FW / "p3_data.h"
IMAGE = FW / "bsp/out/b2_app.bin"
IMPORT = json.loads((FW / "IMPORT.json").read_text())
FORBIDDEN = gen.FORBIDDEN
SEARCH_INCLUDES = {'"b2_search.h"', '"p3_data.h"', '"p3_derive.h"', "<stddef.h>", "<stdint.h>", "<stdio.h>", "<string.h>"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Header(unittest.TestCase):
    def test_no_forbidden_token_in_the_headers_data(self):
        data = gen.strip_comments(HEADER.read_text())
        for f in FORBIDDEN:
            self.assertNotIn(f, data, f)

    def test_the_header_is_fresh_from_its_generator(self):
        self.assertEqual(HEADER.read_text(), gen.render_b2(require_git=False),
                         "firmware/b2/p3_data.h is stale: run host/gen_b2_data.py")

    def test_the_compiled_map_is_the_committed_b1_map(self):
        text = HEADER.read_text()
        doc = bmaps.load_self_map()
        self.assertIn(f'#define B2_MAP_SHA256 "{bmaps.sha256_of(doc)}"', text)
        self.assertIn(f'#define B2_MAP_FILE_SHA256 "{sha(bmaps.SELF_MAP)}"', text)
        self.assertIn(f'#define B2_MAP_CARTOGRAPHER "{doc["cartographer"]}"', text)
        # the tables themselves, entry by entry
        lut = [int(x) for x in re.search(r"B2_MAP_LUT\[B2_MAP_N\] = \{(.*?)\};", text, re.S).group(1).replace(",", " ").split()]
        init = [int(x) for x in re.search(r"B2_MAP_INIT\[B2_MAP_N\] = \{(.*?)\};", text, re.S).group(1).replace(",", " ").split()]
        entries = {e["genome_bit"]: e["relation"] for e in doc["entries"]}
        self.assertEqual(len(lut), 292)
        self.assertEqual(len(init), 292)
        for i in range(292):
            self.assertEqual((lut[i], init[i]), (entries[i]["lut_index"], entries[i]["init_index"]), i)

    def test_the_seed_exclusion_covers_every_archived_run(self):
        import b2_plan as bp
        import b2_search as bs
        excl, sources = bp.frozen_seed_exclusion()
        want = sorted(excl | set(bs.EXCLUDED_SEEDS))
        text = HEADER.read_text()
        self.assertIn(f"#define B2_EXCLUDED_SEEDS_N {len(want)}", text)
        got = [int(x, 16) for x in re.findall(r"0x([0-9a-f]{8})ul", text)]
        self.assertEqual(got, want)
        self.assertEqual(len(sources), len(bp.FROZEN_SEED_SETS))


class Stripper(unittest.TestCase):
    """The comment stripper keeps DATA and drops PROSE — the P3 of the owner's core review."""

    def test_a_comment_marker_inside_a_string_is_data(self):
        self.assertIn("certificate", gen.strip_comments('static const char *x = "/* certificate */";'))
        self.assertIn("local_map", gen.strip_comments('const char *y = "local_map"; /* prose local_map */'))
        self.assertIn("SLICE_X0", gen.strip_comments('/* " */ const char *w = "SLICE_X0";'))

    def test_an_escaped_quote_does_not_end_the_literal(self):
        self.assertIn("certificate", gen.strip_comments(r'const char *z = "a\"/* certificate */";'))
        self.assertIn("certificate", gen.strip_comments("const char c = '\\''; const char *q = \"certificate\";"))

    def test_prose_is_dropped(self):
        for src in ("/* the certificate is absent */ int a;", "// certificate\nint b;",
                    "/* multi\n * line certificate\n */ int c;"):
            self.assertNotIn("certificate", gen.strip_comments(src), src)

    def test_an_unterminated_comment_does_not_leak_prose(self):
        self.assertNotIn("certificate", gen.strip_comments("int a; /* certificate"))

    def test_the_stripper_is_the_one_the_generator_uses(self):
        text = HEADER.read_text()
        self.assertIn("certificate", text)                       # the prose says the file is absent
        self.assertNotIn("certificate", gen.strip_comments(text))


class Sources(unittest.TestCase):
    def test_the_search_unit_includes_nothing_else(self):
        for name in ("b2_search.c", "b2_search.h"):
            includes = set(re.findall(r'^#include\s+(\S+)', (FW / name).read_text(), re.M))
            self.assertTrue(includes <= SEARCH_INCLUDES, f"{name}: {includes - SEARCH_INCLUDES}")

    def test_no_forbidden_token_in_the_b2_sources(self):
        for name in ("b2_search.c", "b2_search.h", "b2_wire.c", "b2_wire.h", "b2_twin.c"):
            data = gen.strip_comments((FW / name).read_text())
            for f in FORBIDDEN:
                self.assertNotIn(f, data, f"{name}: {f}")

    def test_the_operator_reads_only_the_column(self):
        """The map-guided operator's view is built from INIT indices; the LUT index is used
        only for the universe mask (docs/b2_architecture.md §5)."""
        src = (FW / "b2_search.c").read_text()
        view = src[src.index("static void build_view"):src.index("/* ------------------------------------------------------------------ the operators")]
        self.assertIn("B2_MAP_INIT", view)
        self.assertNotIn("B2_MAP_LUT", view)
        mask = src[src.index("void b2_universe_mask"):src.index("void b2_target")]
        self.assertIn("B2_MAP_LUT", mask)


class Imports(unittest.TestCase):
    def test_every_verbatim_import_is_the_instrument_s_byte(self):
        n = 0
        for src, rec in IMPORT["files"].items():
            if rec["kind"] != "verbatim":
                continue
            target = R / rec["copied_to"]
            self.assertTrue(target.is_file(), rec["copied_to"])
            self.assertEqual(sha(target), rec["sha256"], rec["copied_to"])
            n += 1
        self.assertEqual(n, 10)          # six instrument firmware units + four BSP scaffold files

    def test_every_derived_file_exists_and_differs_from_its_base(self):
        n = 0
        for base, rec in IMPORT["files"].items():
            if rec["kind"] != "derived":
                continue
            b, d = R / base, R / rec["derived_to"]
            self.assertTrue(b.is_file() and d.is_file(), base)
            self.assertEqual(sha(b), rec["sha256"], f"{base}: the base moved")
            self.assertEqual(sha(d), rec["derived_sha256"], f"{rec['derived_to']}: the derived file moved")
            self.assertNotEqual(sha(b), sha(d), base)
            n += 1
        self.assertEqual(n, 2)

    def test_the_import_table_names_the_archived_instrument(self):
        self.assertEqual(IMPORT["source_commit"], "689dde1dad374536c625bbe2b05986ee89eb4c94")
        self.assertEqual(IMPORT["schema"], "b2_firmware_import")


@unittest.skipUnless(IMAGE.is_file(), "no built B2 image yet (firmware/b2/bsp/build.sh)")
class Image(unittest.TestCase):
    def test_the_image_carries_no_forbidden_token(self):
        blob = IMAGE.read_bytes()
        for f in FORBIDDEN:
            self.assertNotIn(f.encode(), blob, f)

    def test_the_image_declares_the_engine_and_the_map(self):
        blob = IMAGE.read_bytes()
        import b2_search as bs
        self.assertIn(bs.ENGINE_VERSION.encode(), blob)
        self.assertIn(bmaps.sha256_of(bmaps.load_self_map()).encode(), blob)


if __name__ == "__main__":
    unittest.main()
