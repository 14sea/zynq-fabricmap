"""The B3 image's guards (B3 lifecycle 2, image stages 3 and 4; B2's tests/test_b2_leakage.py re-aimed at B3's boundary,
docs/b3_architecture.md v0.3 §7, Decision E1).

  * no source under b3/firmware carries a forbidden token — B2's list (the certificate and its derivations: LUT
    SITE KEYS, local_map, the operator-data tables of the instrument) plus B3's own — read through B2's
    comment stripper, the one whose fixtures prove it keeps string DATA and drops prose (the owner's core review
    of 2026-09-10, P3), re-held here;
  * B2_MAP_INIT — the frozen map's column relation — is named only by the F arm's engine (b2_search.c) and its
    data header: never by a B3 unit;
  * every unit includes only its allowlist, and every source has one;
  * b3/firmware/IMPORT.json is the CURRENT image-source surface (not yet the final image inventory): its file set
    is EXACTLY the files under b3/firmware but itself — none missing, none invented; every verbatim entry's base,
    target and recorded digest agree; every derived entry's base and derived digests are recorded, both files
    exist and their bytes differ; every new entry exists and names no base — a GENERATED one names its generator,
    which exists, and the file's first line names it back;
  * the binary: at this stage the canonical image (bsp/out/b3_app.bin and .elf) must NOT exist — asserted, never
    skipped — and the binary scanner the application stage will run on it is held load-bearing here on synthetic
    bytes (clean, a forbidden token, a missing declaration). Stage 5 turns the absence into the required scan.

No skip. Nothing here builds or writes anything.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_manifest as bman  # noqa: E402
import gen_b2_data as gen  # noqa: E402

FW = R / "b3/firmware"
IMPORT_PATH = FW / "IMPORT.json"
IMPORT = json.loads(IMPORT_PATH.read_text())
IMAGE = R / bman.IMAGE_REL                                     # b3/firmware/bsp/out/b3_app.bin
ELF = IMAGE.with_suffix(".elf")
FORBIDDEN = tuple(gen.FORBIDDEN) + ("truth_mapping", "b1_model")   # B2's list + the truth's Python names
REQUIRED_IN_IMAGE = (bs.ENGINE_VERSION, carto_mod.CARTO_VERSION)  # + the map digest (below)

STD = {"<stddef.h>", "<stdint.h>", "<string.h>"}
HOST = STD | {"<stdio.h>", "<stdlib.h>", "<errno.h>"}
INCLUDES = {
    # the verbatim copies: what B2's own guard allows them (tests/test_b2_leakage.py SEARCH_INCLUDES)
    "b2_search.c": {'"b2_search.h"', '"p3_data.h"', '"p3_derive.h"', "<stdio.h>", "<string.h>"},
    "b2_search.h": {"<stddef.h>", "<stdint.h>"},
    "p3_derive.c": {'"p3_derive.h"', '"p3_data.h"', "<string.h>"},
    "p3_derive.h": {"<stddef.h>", "<stdint.h>"},
    "p3_data.h": {"<stdint.h>"},
    # the B3 board units: freestanding, no stdio
    "b3_carto.c": {'"b3_carto.h"'} | STD,
    "b3_carto.h": {"<stddef.h>", "<stdint.h>"},
    "b3_online_view.c": {'"b3_online_view.h"', '"p3_data.h"'} | STD,
    "b3_online_view.h": {'"b2_search.h"', '"b3_carto.h"', "<stdint.h>"},
    "b3_record.c": {'"b3_record.h"', '"p3_derive.h"', '"p3_data.h"'} | STD,
    "b3_record.h": {'"b2_search.h"', '"b3_carto.h"', "<stddef.h>", "<stdint.h>"},
    "b3_wire.c": {'"b3_wire.h"', '"p3_derive.h"', "<stdarg.h>", "<stdio.h>", "<string.h>"},   # B2's wire's own
    "b3_wire.h": {"<stddef.h>", "<stdint.h>"},
    # the host twins
    "b3_carto_twin.c": {'"b3_carto.h"'} | HOST,
    "b3_record_twin.c": {'"b2_search.h"', '"b3_carto.h"', '"b3_online_view.h"', '"b3_record.h"', '"p3_derive.h"'} | HOST,
    "b3_wire_twin.c": {'"b2_search.h"', '"b3_carto.h"', '"b3_online_view.h"', '"b3_record.h"', '"b3_wire.h"',
                       '"p3_data.h"', '"p3_derive.h"'} | HOST,
    "b3_wire_parity.c": {'"b2_wire.h"', '"b3_wire.h"', '"p3_derive.h"'} | HOST,
    # image stage 4: the orchestrator, its generated seed data, its twin
    "b3_orch.c": {'"b3_orch.h"', '"b3_seed_data.h"', '"b3_wire.h"'} | STD,
    "b3_orch.h": {'"b2_search.h"', '"b3_carto.h"', '"b3_online_view.h"', '"b3_record.h"'},
    "b3_seed_data.h": {"<stdint.h>"},
    "b3_orch_twin.c": {'"b2_search.h"', '"b3_carto.h"', '"b3_online_view.h"', '"b3_orch.h"', '"p3_derive.h"'} | HOST,
}
BOARD_UNITS = ("b3_carto.c", "b3_carto.h", "b3_online_view.c", "b3_online_view.h", "b3_record.c", "b3_record.h",
               "b3_wire.c", "b3_wire.h", "b3_orch.c", "b3_orch.h", "b3_seed_data.h")
REQUIRED_DERIVED = ("b3/firmware/b3_wire.c", "b3/firmware/b3_wire.h", "b3/firmware/b3_orch.c", "b3/firmware/b3_orch.h")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sources() -> list[Path]:
    return sorted(p for p in FW.rglob("*") if p.is_file() and p.suffix in (".c", ".h"))


def import_findings(doc: dict, root: Path = R, fw: Path = FW) -> list[str]:
    """Every rule of the import table, as named findings (empty = the table is the tree)."""
    f: list[str] = []
    if doc.get("schema") != "b3_firmware_import" or doc.get("schema_version") != "1.0.0":
        f.append("the table is not b3_firmware_import 1.0.0")
    if "NOT yet the final image import inventory" not in str(doc.get("scope", "")):
        f.append("the table does not say it is the current surface, not the final inventory")
    files = doc.get("files")
    if not isinstance(files, dict):
        return f + ["files is not an object"]
    rel = fw.relative_to(root).as_posix()
    on_disk = {p.relative_to(root).as_posix() for p in fw.rglob("*") if p.is_file() and p.name != "IMPORT.json"}
    for path in sorted(on_disk - set(files)):
        f.append(f"{path}: under {rel}/ but not in the table")
    for path in sorted(set(files) - on_disk):
        f.append(f"{path}: in the table but no such file")
    for path, e in sorted(files.items()):
        target = root / path
        if not isinstance(e, dict):
            f.append(f"{path}: the entry is not an object")
            continue
        kind = e.get("kind")
        if kind == "verbatim":
            if sorted(e) != ["base", "kind", "note", "sha256"]:
                f.append(f"{path}: a verbatim entry's keys are base, kind, note, sha256")
                continue
            base = root / e["base"]
            if not base.is_file():
                f.append(f"{path}: the base {e['base']} is absent")
            elif sha(base) != e["sha256"]:
                f.append(f"{path}: the base {e['base']} does not hash to the recorded digest")
            if target.is_file() and sha(target) != e["sha256"]:
                f.append(f"{path}: the copy does not hash to the recorded digest")
        elif kind == "derived":
            if sorted(e) != ["base", "base_sha256", "kind", "note", "sha256"]:
                f.append(f"{path}: a derived entry's keys are base, base_sha256, kind, note, sha256")
                continue
            base = root / e["base"]
            if not base.is_file():
                f.append(f"{path}: the base {e['base']} is absent")
            elif sha(base) != e["base_sha256"]:
                f.append(f"{path}: the base {e['base']} moved")
            if target.is_file() and sha(target) != e["sha256"]:
                f.append(f"{path}: the derived file moved")
            if base.is_file() and target.is_file() and base.read_bytes() == target.read_bytes():
                f.append(f"{path}: a derived file identical to its base")
            if e["base_sha256"] == e["sha256"]:
                f.append(f"{path}: a derived entry records the same digest twice")
        elif kind == "new":
            if sorted(e) not in (["kind", "note", "role"], ["generated_by", "kind", "note", "role"]):
                f.append(f"{path}: a new entry's keys are kind, note, role [, generated_by] (no base, no invented provenance)")
                continue
            if e["role"] not in ("board unit", "host twin", "build"):
                f.append(f"{path}: role {e['role']!r}")
            if "generated_by" in e:
                gen_path = root / e["generated_by"]
                if not gen_path.is_file():
                    f.append(f"{path}: its generator {e['generated_by']} is absent")
                elif target.is_file() and f"GENERATED by {e['generated_by']}" not in target.read_text().splitlines()[0]:
                    f.append(f"{path}: its first line does not name its generator {e['generated_by']}")
        else:
            f.append(f"{path}: kind {kind!r}")
    return f


def binary_findings(blob: bytes, map_sha256: str) -> list[str]:
    """The scan the application stage runs on the built image: no forbidden token, and the declarations present."""
    f = [f"the image carries the forbidden token {t!r}" for t in FORBIDDEN if t.encode() in blob]
    for t in REQUIRED_IN_IMAGE + (map_sha256,):
        if t.encode() not in blob:
            f.append(f"the image does not declare {t!r}")
    return f


class Stripper(unittest.TestCase):
    """B2's stripper keeps DATA and drops PROSE; held again here because this guard depends on it."""

    def test_string_data_survives_and_prose_does_not(self):
        self.assertIn("certificate", gen.strip_comments('static const char *x = "/* certificate */";'))
        self.assertIn("local_map", gen.strip_comments('const char *y = "local_map"; /* prose local_map */'))
        self.assertIn("SLICE_X0", gen.strip_comments('/* " */ const char *w = "SLICE_X0";'))
        self.assertIn("certificate", gen.strip_comments(r'const char *z = "a\"/* certificate */";'))
        for src in ("/* the certificate is absent */ int a;", "// certificate\nint b;", "int a; /* certificate"):
            self.assertNotIn("certificate", gen.strip_comments(src), src)

    def test_the_stripper_is_load_bearing_on_the_real_sources(self):
        text = (FW / "p3_data.h").read_text()
        self.assertIn("certificate", text)                   # the prose names it
        self.assertNotIn("certificate", gen.strip_comments(text))


class Sources(unittest.TestCase):
    def test_no_forbidden_token_in_any_source(self):
        srcs = sources()
        self.assertGreaterEqual(len(srcs), 17)
        for p in srcs:
            data = gen.strip_comments(p.read_text())
            for t in FORBIDDEN:
                self.assertNotIn(t, data, f"{p.name}: {t}")

    def test_the_scan_catches_a_planted_token(self):
        for t in FORBIDDEN:
            src = f'static const char *leak = "{t}";\n/* prose */ int x;'
            self.assertIn(t, gen.strip_comments(src), t)

    def test_b2_map_init_is_named_only_by_the_f_arm_s_engine_and_its_data(self):
        named = sorted(p.name for p in sources() if re.search(r"\bB2_MAP_INIT\b", gen.strip_comments(p.read_text())))
        self.assertEqual(named, ["b2_search.c", "p3_data.h"])

    def test_every_source_has_an_include_allowlist_and_keeps_to_it(self):
        names = {p.name for p in sources()}
        self.assertEqual(names, set(INCLUDES), "every source has an allowlist and every allowlist a source")
        for p in sources():
            got = set(re.findall(r"^\s*#\s*include\s+(\S+)", p.read_text(), re.M))
            with self.subTest(unit=p.name):
                self.assertTrue(got <= INCLUDES[p.name], f"{p.name}: {sorted(got - INCLUDES[p.name])}")
        for name in BOARD_UNITS:
            if name not in ("b3_wire.c",):                   # the wire is B2's, with B2's stdio
                self.assertNotIn("<stdio.h>", INCLUDES[name], name)


class Imports(unittest.TestCase):
    def test_the_table_is_the_tree(self):
        self.assertEqual(import_findings(IMPORT), [])          # the exact set and every entry (no count: a later stage adds files)
        derived = {p for p, e in IMPORT["files"].items() if e["kind"] == "derived"}
        self.assertTrue(set(REQUIRED_DERIVED) <= derived, sorted(set(REQUIRED_DERIVED) - derived))   # a required subset; the exact set is import_findings'
        for p in REQUIRED_DERIVED:
            self.assertEqual(IMPORT["files"][p]["base"], p.replace("b3/firmware/b3_", "firmware/b2/b2_"))
        self.assertEqual(IMPORT["files"]["b3/firmware/b3_seed_data.h"]["generated_by"], "b3/host/gen_b3_seed_data.py")
        self.assertTrue(IMPORT["stage"].startswith("image stage "))

    def test_every_rule_is_load_bearing(self):
        """Each rule refuses its own breach (the table is perturbed in memory; the tree is not touched)."""
        def broken(fn):
            d = json.loads(IMPORT_PATH.read_text())
            fn(d)
            return import_findings(d)
        v, dv, nw = "b3/firmware/p3_derive.c", "b3/firmware/b3_wire.c", "b3/firmware/b3_record.c"
        cases = {
            "not in the table": lambda d: d["files"].pop(nw),
            "no such file": lambda d: d["files"].__setitem__("b3/firmware/ghost.c", {"kind": "new", "role": "board unit", "note": "x"}),
            "the base firmware/b2/nothing.c is absent": lambda d: d["files"][v].__setitem__("base", "firmware/b2/nothing.c"),
            "does not hash to the recorded digest": lambda d: d["files"][v].__setitem__("sha256", "0" * 64),
            "the base firmware/b2/b2_wire.c moved": lambda d: d["files"][dv].__setitem__("base_sha256", "0" * 64),
            "the derived file moved": lambda d: d["files"][dv].__setitem__("sha256", "1" * 64),
            "records the same digest twice": lambda d: d["files"][dv].__setitem__("sha256", d["files"][dv]["base_sha256"]),
            "no invented provenance": lambda d: d["files"][nw].__setitem__("base", "firmware/b2/b2_search.c"),
            "a verbatim entry's keys": lambda d: d["files"][v].pop("note"),
            "kind 'copied'": lambda d: d["files"][v].__setitem__("kind", "copied"),
            "role 'other'": lambda d: d["files"][nw].__setitem__("role", "other"),
            "not the final inventory": lambda d: d.__setitem__("scope", "the final image import inventory"),
            "b3_firmware_import 1.0.0": lambda d: d.__setitem__("schema_version", "2.0.0"),
            "its generator b3/host/nothing.py is absent": lambda d: d["files"]["b3/firmware/b3_seed_data.h"].__setitem__("generated_by", "b3/host/nothing.py"),
            "does not name its generator b3/host/b3_plan.py": lambda d: d["files"]["b3/firmware/b3_seed_data.h"].__setitem__("generated_by", "b3/host/b3_plan.py"),
            "[, generated_by]": lambda d: d["files"]["b3/firmware/b3_seed_data.h"].__setitem__("source", "x"),
        }
        for needle, fn in cases.items():
            with self.subTest(rule=needle):
                f = broken(fn)
                self.assertTrue(any(needle in x for x in f), (needle, f))

    def test_a_derived_file_identical_to_its_base_is_refused(self):
        import shutil
        import tempfile
        d = Path(tempfile.mkdtemp(prefix="b3_import_"))
        self.addCleanup(shutil.rmtree, d, True)
        (d / "firmware/b2").mkdir(parents=True)
        (d / "b3/firmware").mkdir(parents=True)
        (d / "firmware/b2/b2_wire.c").write_text("base\n")
        (d / "b3/firmware/b3_wire.c").write_text("base\n")
        h = hashlib.sha256(b"base\n").hexdigest()
        doc = {"schema": "b3_firmware_import", "schema_version": "1.0.0", "scope": "NOT yet the final image import inventory",
               "files": {"b3/firmware/b3_wire.c": {"kind": "derived", "base": "firmware/b2/b2_wire.c", "base_sha256": h,
                                                   "sha256": h, "note": "x"}}}
        f = import_findings(doc, d, d / "b3/firmware")
        self.assertTrue(any("identical to its base" in x for x in f), f)

    def test_the_five_b2_copies_are_the_verbatim_entries(self):
        got = sorted(e["base"] for e in IMPORT["files"].values() if e["kind"] == "verbatim")
        self.assertEqual(got, sorted(f"firmware/b2/{n}" for n in ("b2_search.c", "b2_search.h", "p3_data.h", "p3_derive.c", "p3_derive.h")))


class TheBinary(unittest.TestCase):
    def test_the_canonical_image_does_not_exist_yet(self):
        """Image stage 3: no image. Stage 5 replaces this assertion by the required scan of the real bytes."""
        self.assertEqual(bman.IMAGE_REL, "b3/firmware/bsp/out/b3_app.bin")
        self.assertFalse(IMAGE.exists(), IMAGE)
        self.assertFalse(ELF.exists(), ELF)
        self.assertFalse((FW / "bsp").exists(), "no BSP at this stage")

    def test_the_scanner_is_load_bearing_on_synthetic_bytes(self):
        m = bmaps.sha256_of(bmaps.load_self_map())
        clean = b"\x00\x7fELF..." + b"\x00".join(t.encode() for t in REQUIRED_IN_IMAGE + (m,)) + b"\x00tail"
        self.assertEqual(binary_findings(clean, m), [])
        for t in FORBIDDEN:
            with self.subTest(forbidden=t):
                self.assertEqual(binary_findings(clean + t.encode(), m), [f"the image carries the forbidden token {t!r}"])
        for t in REQUIRED_IN_IMAGE + (m,):
            with self.subTest(required=t):
                self.assertEqual(binary_findings(clean.replace(t.encode(), b"X" * len(t)), m), [f"the image does not declare {t!r}"])


if __name__ == "__main__":
    unittest.main()
