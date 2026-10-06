"""The committed B3 image is the image of the committed SOURCE — and the guard that says so must be shown to REFUSE
(B3 lifecycle 2, image stage 5, first unit; the discipline of tests/test_b2_build_evidence.py).

`b3_build_evidence.verify_findings(evidence, root)` is a pure function, so every refusal below drives it with a deep
copy that has exactly one thing wrong. The verifier re-resolves the trusted build description from the build
configuration — the pinned toolchain, -print-file-name under the build's flags, this module's mandatory inventory,
build.sh's own unit lists — and never selects a file by the path the evidence supplies.

The dependencies are RE-DISCOVERED by the verifier (the owner's HOLD on 171b638): every unit's -M is run again with
build.sh's own compile flags (printed by build.sh itself, -O2 included; only the output-only options removed) and
compared unit by unit — a header deleted from the hash table AND from every dependency list is still named. The two
clean builds are not only read from the evidence: TheRealBuild runs the production build.sh twice into fresh
directories (B3_OUT_DIR / B3_IMG_DIR, never the committed image) and compares the binaries and the ELFs.

THE STACK (the owner's rulings of 2026-10-04 and 2026-10-06): the evidence carries the stack assessment of the final
ELF, the verifier RE-RUNS b3/host/b3_image_stack.py and requires the block to match it and to be within budget
(main <= 0x2000, each exception entry within its mode's stack), and `readiness.image_ready` is true only for a
COMPLETE block. THE COMMITTED IMAGE'S BLOCK IS `FINDINGS`: the image has writes the analysis cannot place, none of
them is proved to miss a callback cell, no bound is published for an entry that calls through memory, and the image
is NOT ready — the tests below require exactly that. A block whose recorded bounds / findings / rules differ from a
fresh analysis, or that claims completion with a finding, or that is over budget, is refused; the passing case is a
synthetic one (a COMPLETE block with the fresh analysis stubbed to it).

No skip: the evidence, the image and the toolchain are required.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b3_build_evidence as be  # noqa: E402
import b3_manifest as bman  # noqa: E402

EVIDENCE = R / be.EVIDENCE_REL
IMAGE = R / be.IMAGE_REL
ELF = R / be.ELF_REL
BAD = "00" * 32


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Committed(unittest.TestCase):
    """The committed evidence stands on its own — and says the image is not ready."""

    @classmethod
    def setUpClass(cls):
        cls.ev = json.loads(EVIDENCE.read_text())

    def test_the_paths_are_the_manifest_s(self):
        self.assertEqual(be.EVIDENCE_REL, bman.BUILD_EVIDENCE_REL)
        self.assertEqual(be.IMAGE_REL, bman.IMAGE_REL)
        self.assertEqual(self.ev["image"]["path"], bman.IMAGE_REL)

    def test_the_committed_evidence_has_no_provenance_finding(self):
        self.assertEqual(be.verify_findings(self.ev, R), [])

    def test_the_stack_assessment_has_findings_and_the_image_is_blocked(self):
        """The owner's strict ruling of 2026-10-06: the committed image's assessment is FINDINGS — no verified main
        bound, no bound for any entry that calls through memory, and the image not ready."""
        st = self.ev["stack"]
        self.assertEqual((st["status"], st["complete"]), ("FINDINGS", False))
        self.assertEqual(st["elf_sha256"], self.ev["image"]["elf_sha256"])
        self.assertEqual(st["main_limit"], 0x2000)
        self.assertEqual(sorted(st["entries"]), sorted(["main", "undefined", "svc", "prefetch_abort", "data_abort", "irq", "fiq"]))
        for name, b in st["entries"].items():
            self.assertIsNone(b["bound"], f"{name}: no bound is published")
        self.assertNotIn("unpublished", st["entries"]["main"], "no main bound was even computed")
        self.assertEqual(sum(f.startswith("main (_start): ") and "may be written" in f and "it is not placed" in f
                             for f in st["findings"]), 1, "main is refused where it reads a table's callback")
        self.assertGreater(sum("write(s) not placed" in f for f in st["findings"]), 100)
        self.assertEqual(sum("no bound is published" in f for f in st["findings"]), 6, "the six exception entries")
        self.assertIn("write_placement", st["rules"])
        self.assertEqual(st["rules"]["read_only_tables"]["targets"], [], "no table is proved read-only")
        self.assertTrue(st["newlib"] and st["newlib"]["rule"] == "newlib_bounded_sbprintf")
        self.assertIn("this block is NOT complete", st["note"], "the note says what this block shows")
        self.assertNotIn("the main path is bounded at or below 0x2000", st["note"])
        rd = self.ev["readiness"]
        self.assertIs(rd["image_ready"], False)
        self.assertEqual(rd["blocking"], [f"stack: {m}" for m in st["findings"]])
        rf = be.readiness_findings(self.ev, R)
        self.assertIn("stack: the image stack assessment is not complete", rf)
        self.assertLessEqual({f"stack: {m}" for m in st["findings"]}, set(rf), "every stack finding stands in the way")

    def test_the_outputs_exist_and_are_the_ones_it_names(self):
        self.assertTrue(IMAGE.is_file() and ELF.is_file())
        self.assertEqual(sha(IMAGE), self.ev["image"]["sha256"])
        self.assertEqual(sha(ELF), self.ev["image"]["elf_sha256"])
        self.assertEqual(IMAGE.stat().st_size, self.ev["image"]["bytes"])

    def test_two_clean_builds_reproduced_both_outputs(self):
        rep = self.ev["reproducibility"]
        self.assertEqual(len(rep["builds"]), 2)
        self.assertTrue(rep["reproduced_byte_identical"] and rep["bin_identical"] and rep["elf_identical"])
        for b in rep["builds"]:
            self.assertEqual((b["bin_sha256"], b["elf_sha256"]), (sha(IMAGE), sha(ELF)))
        self.assertIn("removed", rep["clean"])

    def test_the_mandatory_inventory_is_the_module_s(self):
        for rel in be.APP_SOURCES:
            self.assertIn(rel, self.ev["sources"], rel)
        for rel in ("bsp/build.sh", "bsp/lscript.ld", "bsp/src/console.c", "b3_seed_data.h", "b3_app.c"):
            self.assertIn(rel, be.APP_SOURCES)

    def test_the_inventory_is_the_whole_build(self):
        bi = self.ev["bsp_inputs"]
        lists = be.build_script_sources()
        self.assertEqual(bi["build_script_lists"], lists)
        self.assertEqual(set(bi["translation_units"]), be.expected_units(lists))
        self.assertEqual(lists["APP_SRCS"], ["b3_app.c", "p3_derive.c", "b2_search.c", "b3_orch.c", "b3_record.c",
                                             "b3_online_view.c", "b3_carto.c", "b3_wire.c", "p3_rectx.c", "p3_pull.c"])
        self.assertEqual(len(be.expected_units(lists)), 50)

    def test_the_recorded_dependencies_are_the_compiler_s_own(self):
        """Re-run the compiler's -M over every unit and require the recorded map — the toolchain's own headers included."""
        bi = self.ev["bsp_inputs"]
        fresh = be.bsp_inputs()
        self.assertEqual(set(fresh["dependencies"]), set(bi["dependencies"]))
        for unit, deps in fresh["dependencies"].items():
            self.assertEqual(sorted(bi["dependencies"][unit]), sorted(deps), unit)
        self.assertEqual(fresh["headers"], bi["headers"])
        self.assertTrue(any(str(be.TC) in h and h.endswith("stdint.h") for h in bi["headers"]), "the toolchain's own headers are hashed")

    def test_the_compiler_and_the_runtime_objects_are_the_resolved_ones(self):
        cc = be.trusted_compiler()
        self.assertTrue(cc.is_file(), "the pinned toolchain is required: a failure, not a skip")
        self.assertEqual(self.ev["toolchain"]["gcc_sha256"], sha(cc))
        resolved = be.resolved_runtime_objects()
        recorded = self.ev["bsp_inputs"]["toolchain_objects"]
        self.assertEqual(sorted(recorded), sorted(be.RUNTIME_OBJECTS))
        for name, want in resolved.items():
            self.assertEqual(recorded[name]["sha256"], want["sha256"], name)
        self.assertEqual(len({v["sha256"] for v in resolved.values()}), len(be.RUNTIME_OBJECTS))


class TheFlags(unittest.TestCase):
    def test_the_flags_are_build_sh_s_less_only_the_output_only_options(self):
        bsp, app = be.build_flags()
        raw = {}
        p = subprocess_run_print_flags()
        for line in p.splitlines():
            k, _, v = line.partition("=")
            raw[k] = v.split()
        for got, key in ((bsp, "BSP_CFLAGS"), (app, "APP_CFLAGS")):
            self.assertEqual(got, [t for t in raw[key] if not t.startswith(("-fstack-usage", "-fcallgraph-info"))])
            self.assertIn("-O2", got)
            self.assertIn("-g", got)
        self.assertTrue(any(t.startswith("-fstack-usage") for t in raw["APP_CFLAGS"]), "the build itself still produces them")

    def test_a_header_behind_optimize_is_found_with_the_build_s_flags_and_missed_without_o2(self):
        """The owner's discriminating case on 171b638: a header read only under -O2 (`#ifdef __OPTIMIZE__`)."""
        d = Path(tempfile.mkdtemp(prefix="b3_opt_"))
        self.addCleanup(shutil.rmtree, d, True)
        (d / "only_optimized.h").write_text("#define ONLY_OPTIMIZED 1\n")
        (d / "unit.c").write_text('#ifdef __OPTIMIZE__\n#include "only_optimized.h"\n#endif\nint x;\n')
        _bsp, app = be.build_flags()
        with_build = be.dependency_set(d / "unit.c", app + ["-I", str(d)])
        without_o2 = be.dependency_set(d / "unit.c", [t for t in app if t != "-O2"] + ["-I", str(d)])
        self.assertIn(str(d / "only_optimized.h"), with_build)
        self.assertNotIn(str(d / "only_optimized.h"), without_o2, "the control: without -O2 the header is not read")


def subprocess_run_print_flags() -> str:
    import subprocess
    return subprocess.run(["bash", str(be.BUILD)], capture_output=True, text=True, check=True,
                          env=dict(os.environ, B3_PRINT_FLAGS="1")).stdout


class TheRealBuild(unittest.TestCase):
    """The production build.sh, run twice, each time CLEAN, into fresh directories under the ignored build/ (never the
    committed image, never the default intermediate directory), the second from another working directory: both
    binaries and both ELFs identical — and identical to the committed image and to the evidence's record."""

    def test_two_clean_builds_reproduce_the_committed_image(self):
        before = (sha(IMAGE), sha(ELF), IMAGE.stat().st_mtime_ns, ELF.stat().st_mtime_ns)
        default_map = be.INTERMEDIATE / "b3_app.map"
        map_before = default_map.stat().st_mtime_ns if default_map.is_file() else None
        root = Path(tempfile.mkdtemp(prefix="b3_rebuild_", dir=R / "build"))
        self.addCleanup(shutil.rmtree, root, True)
        results = []
        for k in (1, 2):
            out, img = root / f"out{k}", root / f"img{k}"
            out.mkdir()
            (out / "stale.o").write_text("a stale object from an earlier build\n")       # must not survive: a CLEAN build
            img.mkdir()
            (img / "b3_app.bin").write_text("stale image\n")
            here = os.getcwd()
            if k == 2:                                         # the second build from ANOTHER working directory: the
                os.chdir(tempfile.mkdtemp(prefix="b3_cwd_", dir=root))   # ELF must not depend on the caller's cwd
            try:
                results.append(be.build_once(out, img))
            finally:
                os.chdir(here)
            self.assertFalse((out / "stale.o").exists(), "the intermediate directory was removed before the build")
            self.assertTrue((out / "b3_app.c.o").is_file() and (out / "b3_app.map").is_file())
            self.assertEqual(sorted(x.name for x in img.iterdir()), ["b3_app.bin", "b3_app.elf"])
        self.assertEqual(results[0], results[1], "the two builds agree in the binary AND the ELF")
        ev = json.loads(EVIDENCE.read_text())
        self.assertEqual(results[0], {"bin_sha256": ev["image"]["sha256"], "elf_sha256": ev["image"]["elf_sha256"]})
        self.assertEqual(results[0], {"bin_sha256": before[0], "elf_sha256": before[1]}, "the committed image is what the build makes")
        self.assertEqual((sha(IMAGE), sha(ELF), IMAGE.stat().st_mtime_ns, ELF.stat().st_mtime_ns), before, "the committed image was not touched")
        if map_before is not None:
            self.assertEqual(default_map.stat().st_mtime_ns, map_before, "the default intermediate directory was not touched")


class TheBuildDirectories(unittest.TestCase):
    """build_once cleans, builds and reads ONE pair of directories, whatever B3_OUT_DIR / B3_IMG_DIR the caller's
    environment carries (the owner's HOLD on 3405273). Hermetic: the module's default directories are patched to temp
    directories under the ignored build/, the inherited variables point at decoys, and the committed image is never
    the build's target."""

    def setUp(self):
        self.before = (sha(IMAGE), sha(ELF), IMAGE.stat().st_mtime_ns, ELF.stat().st_mtime_ns)
        self.root = Path(tempfile.mkdtemp(prefix="b3_dirs_", dir=R / "build"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.ev = json.loads(EVIDENCE.read_text())

    def tearDown(self):
        self.assertEqual((sha(IMAGE), sha(ELF), IMAGE.stat().st_mtime_ns, ELF.stat().st_mtime_ns), self.before,
                         "the committed image was not touched")

    def dirs(self, *names):
        out = []
        for n in names:
            d = self.root / n
            d.mkdir()
            out.append(d)
        return out

    def decoys(self):
        """Two decoy directories the inherited environment names, each holding a marker that must survive."""
        dout, dimg = self.dirs("decoy_out", "decoy_img")
        for d in (dout, dimg):
            (d / "marker").write_text("not the build's\n")
        return dout, dimg

    def assert_built(self, inter, img, result, decoys):
        self.assertTrue((inter / "b3_app.c.o").is_file() and (inter / "b3_app.map").is_file(), "built into the chosen intermediate directory")
        self.assertFalse((inter / "stale.o").exists(), "the chosen intermediate directory was cleaned")
        self.assertEqual(sorted(x.name for x in img.iterdir()), ["b3_app.bin", "b3_app.elf"])
        self.assertEqual(result, {"bin_sha256": sha(img / "b3_app.bin"), "elf_sha256": sha(img / "b3_app.elf")})
        self.assertEqual(result, {"bin_sha256": self.ev["image"]["sha256"], "elf_sha256": self.ev["image"]["elf_sha256"]})
        for d in decoys:
            self.assertEqual(sorted(x.name for x in d.iterdir()), ["marker"], f"{d.name}: the inherited directory was not used")

    def seed(self, inter, img):
        (inter / "stale.o").write_text("stale\n")
        (img / "b3_app.bin").write_text("stale image\n")

    def test_no_argument_uses_the_defaults_not_the_environment(self):
        inter, img = self.dirs("default_out", "default_img")
        self.seed(inter, img)
        dout, dimg = self.decoys()
        with mock.patch.object(be, "INTERMEDIATE", inter), mock.patch.object(be, "OUT", img), \
                mock.patch.dict(os.environ, {"B3_OUT_DIR": str(dout), "B3_IMG_DIR": str(dimg)}):
            result = be.build_once()
        self.assert_built(inter, img, result, (dout, dimg))

    def test_only_the_intermediate_directory_given(self):
        inter, img = self.dirs("given_out", "default_img")
        self.seed(inter, img)
        dout, dimg = self.decoys()
        with mock.patch.object(be, "OUT", img), \
                mock.patch.dict(os.environ, {"B3_OUT_DIR": str(dout), "B3_IMG_DIR": str(dimg)}):
            result = be.build_once(out_dir=inter)
        self.assert_built(inter, img, result, (dout, dimg))

    def test_only_the_image_directory_given_relative_from_another_cwd(self):
        """A RELATIVE directory means the caller's cwd, not the repository root build.sh builds from: here the two
        resolve to different directories under the temp root, so a path handed over unresolved is caught."""
        inter, cwd = self.dirs("default_out", "cwd")
        img = cwd / "img"
        img.mkdir()
        self.seed(inter, img)
        dout, dimg = self.decoys()
        here = os.getcwd()
        os.chdir(cwd)
        try:
            with mock.patch.object(be, "INTERMEDIATE", inter), \
                    mock.patch.dict(os.environ, {"B3_OUT_DIR": str(dout), "B3_IMG_DIR": str(dimg)}):
                result = be.build_once(img_dir=Path("img"))
        finally:
            os.chdir(here)
        self.assert_built(inter, img, result, (dout, dimg))
        self.assertFalse((R / "img").exists(), "nothing was built at the repository root")


class Refuses(unittest.TestCase):
    """One thing wrong at a time; each must be named."""

    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(EVIDENCE.read_text())

    def refused(self, mutate, needle: str):
        ev = copy.deepcopy(self.base)
        mutate(ev)
        f = be.verify_findings(ev, R)
        self.assertTrue(any(needle in x for x in f), f"{needle!r} not named in {f[:4]}")

    def test_provenance_breaches(self):
        cases = {
            "source b3_app.c": lambda e: e["sources"].__setitem__("b3_app.c", BAD),
            "b3_seed_data.h is a required build input but is not recorded": lambda e: e["sources"].pop("b3_seed_data.h"),
            "bsp/lscript.ld is a required build input": lambda e: e["sources"].pop("bsp/lscript.ld"),
            "the image: ": lambda e: e["image"].__setitem__("sha256", BAD),
            "the ELF": lambda e: e["image"].__setitem__("elf_sha256", BAD),
            "the two builds' binaries differ": lambda e: e["reproducibility"]["builds"][1].__setitem__("bin_sha256", BAD),
            "the two builds' ELFs differ": lambda e: e["reproducibility"]["builds"][1].__setitem__("elf_sha256", BAD),
            "two builds, each with both output digests": lambda e: e["reproducibility"]["builds"].pop(),
            "the recorded verdicts disagree": lambda e: e["reproducibility"].__setitem__("bin_identical", False),
            "header": lambda e: e["bsp_inputs"]["headers"].__setitem__(sorted(e["bsp_inputs"]["headers"])[0], BAD),
            "is read by the build but has no hash": lambda e: e["bsp_inputs"]["headers"].pop(sorted(e["bsp_inputs"]["headers"])[0]),
            "compiled by the build script but not recorded": lambda e: e["bsp_inputs"]["translation_units"].pop(sorted(e["bsp_inputs"]["translation_units"])[0]),
            "is recorded but not compiled": lambda e: e["bsp_inputs"]["translation_units"].__setitem__("/tmp/extra.c", BAD),
            "no dependency list": lambda e: e["bsp_inputs"]["dependencies"].pop(sorted(e["bsp_inputs"]["dependencies"])[0]),
            "the recorded lists are not build.sh's": lambda e: e["bsp_inputs"]["build_script_lists"]["APP_SRCS"].pop(),
            "the recorded hash is not the build compiler's": lambda e: e["toolchain"].__setitem__("gcc_sha256", BAD),
            "runtime object libc.a: the recorded hash": lambda e: e["bsp_inputs"]["toolchain_objects"]["libc.a"].__setitem__("sha256", BAD),
            "runtime object libc.a: the evidence names": lambda e: e["bsp_inputs"]["toolchain_objects"]["libc.a"].__setitem__(
                "path", e["bsp_inputs"]["toolchain_objects"]["libm.a"]["path"]),
            "libgcc.a is not recorded": lambda e: e["bsp_inputs"]["toolchain_objects"].pop("libgcc.a"),
            "neither a recorded source nor an output": lambda e: e["git"]["dirty"].append("b3/firmware/stray.c"),
            "no head recorded": lambda e: e["git"].__setitem__("head", None),
            "the B3 image is": lambda e: e["image"].__setitem__("path", "b3/firmware/bsp/out/other.bin"),
            "the evidence has no 'stack' section": lambda e: e.pop("stack"),
            "the evidence is not b3_build_evidence": lambda e: e.__setitem__("schema_version", "0.9.0"),
        }
        for needle, fn in cases.items():
            with self.subTest(breach=needle):
                self.refused(fn, needle)

    def test_a_header_deleted_from_the_table_and_from_every_list_is_still_named(self):
        """The owner's first counterexample on 171b638: stdio.h removed from the hash table AND from every unit's list."""
        ev = copy.deepcopy(self.base)
        bi = ev["bsp_inputs"]
        gone = [h for h in bi["headers"] if h.endswith("/stdio.h")]
        self.assertTrue(gone, "the build reads stdio.h")
        for h in gone:
            bi["headers"].pop(h)
        for unit in bi["dependencies"]:
            bi["dependencies"][unit] = [h for h in bi["dependencies"][unit] if h not in gone]
        f = be.verify_findings(ev, R)
        self.assertTrue(any("is not the compiler's dependency set" in x for x in f), f[:3])
        self.assertTrue(any("stdio.h is read by the build but has no hash" in x for x in f), f[:3])

    def test_an_emptied_header_table_and_empty_dependency_lists_are_named(self):
        """The owner's second counterexample: every header gone and every unit's list emptied."""
        ev = copy.deepcopy(self.base)
        bi = ev["bsp_inputs"]
        bi["headers"] = {}
        bi["dependencies"] = {u: [] for u in bi["dependencies"]}
        f = be.verify_findings(ev, R)
        named = sum(1 for x in f if "is not the compiler's dependency set" in x)
        reading = sum(1 for deps in be.fresh_dependencies(R).values() if deps)
        self.assertGreater(reading, 40)
        self.assertEqual(named, reading, "every unit that reads a header is named")
        self.assertTrue(any("is read by the build but has no hash" in x for x in f))

    def test_recorded_flags_that_are_not_build_sh_s_are_named(self):
        ev = copy.deepcopy(self.base)
        ev["bsp_inputs"]["dependency_flags"]["app"].remove("-O2")
        self.assertIn("dependency_flags: the recorded -M flags are not build.sh's compile flags", be.verify_findings(ev, R))

    def test_a_dirty_path_outside_b3_firmware_is_not_an_image_input(self):
        ev = copy.deepcopy(self.base)
        ev["git"]["dirty"].append("docs/notes.md")
        self.assertEqual(be.verify_findings(ev, R), [])

    def test_the_stack_block_must_match_a_fresh_analysis_within_budget(self):
        def bump_main(e):
            e["stack"]["entries"]["main"]["bound"] = 0x2001
        cases = {
            "the recorded entries is not the analyser's fresh result": bump_main,
            "the recorded findings is not the analyser's fresh result": lambda e: e["stack"].__setitem__("findings", ["made up"]),
            "the recorded newlib is not the analyser's fresh result": lambda e: e["stack"]["newlib"].__setitem__("rule", "x"),
            "the recorded rules is not the analyser's fresh result": lambda e: e["stack"]["rules"].clear(),
            "the recorded tool is not the analyser's fresh result": lambda e: e["stack"].__setitem__("tool", "forged 9.9"),
            "the block's ELF digest is not the built image's": lambda e: e["stack"].__setitem__("elf_sha256", BAD),
            "the block's keys": lambda e: e["stack"].pop("note"),
            "complete / status disagree": lambda e: e["stack"].__setitem__("status", "PASS"),
            "image_ready must be": lambda e: e["readiness"].__setitem__("image_ready", True),
            "a complete block must have no finding": lambda e: e["stack"].update(complete=True),
        }
        for needle, fn in cases.items():
            with self.subTest(breach=needle):
                self.refused(fn, needle.strip())

    def test_the_note_follows_the_status(self):
        """The block's note states the bounded result only for a COMPLETE block (the analyser stubbed either way)."""
        import b3_image_stack as isa
        r = dict(copy.deepcopy(self.base["stack"]), elf={"sha256": self.base["stack"]["elf_sha256"]})
        with mock.patch.object(isa, "assess", return_value=r):
            blocked = be.stack_block(R)
        self.assertEqual((blocked["status"], blocked["complete"]), ("FINDINGS", False))
        self.assertIn("this block is NOT complete", blocked["note"])
        self.assertNotIn("is bounded at or below 0x2000", blocked["note"])
        good = copy.deepcopy(r)
        good["findings"] = []
        for name, b in good["entries"].items():
            b["bound"] = 0x1000 if name == "main" else 16
        with mock.patch.object(isa, "assess", return_value=good):
            done = be.stack_block(R)
        self.assertEqual((done["status"], done["complete"]), ("COMPLETE", True))
        self.assertIn("the main path is bounded at or below 0x2000", done["note"])
        self.assertNotIn("NOT complete", done["note"])

    def test_a_main_path_over_budget_is_refused_and_not_ready(self):
        ev = copy.deepcopy(self.base)
        ev["stack"]["entries"]["main"]["bound"] = 0x2001          # as if the main path exceeded 0x2000
        self.assertTrue(any("exceeds its budget" in x or "not the analyser's fresh result" in x
                            for x in be.verify_findings(ev, R)))

    def complete(self):
        """A synthetic positive: the committed evidence as it would stand with a COMPLETE stack block — every entry
        bounded within its budget, no finding, ready. (The numbers are made up; they are no claim about the image.)"""
        ev = copy.deepcopy(self.base)
        st = ev["stack"]
        st.update(status="COMPLETE", complete=True, findings=[])
        for name, b in st["entries"].items():
            b.pop("unpublished", None)
            b["bound"] = 0x1000 if name == "main" else 16
        ev["readiness"].update(image_ready=True, blocking=[])
        return ev

    def test_readiness_is_empty_only_when_complete_and_within_budget(self):
        self.assertNotEqual(be.readiness_findings(self.base, R), [], "the committed image is not ready")
        good = self.complete()
        with mock.patch.object(be, "stack_block", side_effect=lambda root=R: copy.deepcopy(good["stack"])):
            self.assertEqual(be.verify_findings(good, R), [], "a complete block the fresh analysis agrees with verifies")
            self.assertEqual(be.readiness_findings(good, R), [], "and nothing stands between that image and ready")
            for mutate in (lambda e: e["stack"].__setitem__("findings", ["x"]),
                           lambda e: e["stack"].__setitem__("complete", False),
                           lambda e: e["readiness"].__setitem__("image_ready", False)):
                ev = self.complete()
                mutate(ev)
                self.assertNotEqual(be.readiness_findings(ev, R), [])
        over = self.complete()
        over["stack"]["entries"]["main"]["bound"] = 0x2001
        with mock.patch.object(be, "stack_block", side_effect=lambda root=R: copy.deepcopy(over["stack"])):
            f = be.verify_findings(over, R)                # even when the fresh analysis says the same
            self.assertIn("stack: main bound 8193 exceeds its budget 8192", f)
            self.assertIn("readiness: image_ready must be False for this stack result and provenance", f)


if __name__ == "__main__":
    unittest.main()
