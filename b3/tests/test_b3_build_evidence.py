"""The committed B3 image is the image of the committed SOURCE — and the guard that says so must be shown to REFUSE
(B3 lifecycle 2, image stage 5, first unit; the discipline of tests/test_b2_build_evidence.py).

`b3_build_evidence.verify_findings(evidence, root)` is a pure function, so every refusal below drives it with a deep
copy that has exactly one thing wrong. The verifier re-resolves the trusted build description from the build
configuration — the pinned toolchain, -print-file-name under the build's flags, this module's mandatory inventory,
build.sh's own unit lists — and never selects a file by the path the evidence supplies.

THE STACK (the owner's ruling of 2026-10-04): the image stack assessment is the next unit. The evidence must carry a
`stack` block stating it is INCOMPLETE and claiming no bound, `readiness.image_ready` must be false, a block that
claims completion is refused by this version of the tool, and `readiness_findings` is never empty — whatever else
stands, the image is NOT ready.

No skip: the evidence, the image and the toolchain are required.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

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

    def test_the_image_is_not_ready_because_the_stack_assessment_is_incomplete(self):
        st = self.ev["stack"]
        self.assertEqual((st["status"], st["complete"], st["bounds"], st["tool"]), ("INCOMPLETE", False, None, None))
        self.assertEqual(st["elf_sha256"], self.ev["image"]["elf_sha256"])
        self.assertIn(be.STACK_INCOMPLETE, st["findings"])
        self.assertIs(self.ev["readiness"]["image_ready"], False)
        self.assertIn("stack: INCOMPLETE", self.ev["readiness"]["blocking"])
        r = be.readiness_findings(self.ev, R)
        self.assertEqual(r, [f"stack: {be.STACK_INCOMPLETE}"], "the stack is the one thing between this image and ready")

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
            "is a recorded dependency but has no hash": lambda e: e["bsp_inputs"]["headers"].pop(sorted(e["bsp_inputs"]["headers"])[0]),
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

    def test_a_dirty_path_outside_b3_firmware_is_not_an_image_input(self):
        ev = copy.deepcopy(self.base)
        ev["git"]["dirty"].append("docs/notes.md")
        self.assertEqual(be.verify_findings(ev, R), [])

    def test_the_stack_block_cannot_be_dropped_softened_or_claimed_complete(self):
        cases = {
            "this tool version cannot check a completed stack assessment": lambda e: e["stack"].update(complete=True, status="COMPLETE"),
            "this tool version cannot check a completed stack assessment ": lambda e: e["stack"].__setitem__("status", "PASS"),
            "must name why and claim no bound": lambda e: e["stack"].__setitem__("bounds", {"main": 1024}),
            "must name why and claim no bound ": lambda e: e["stack"].__setitem__("findings", []),
            "the block is not about the named ELF": lambda e: e["stack"].__setitem__("elf_sha256", BAD),
            "the block's keys": lambda e: e["stack"].pop("note"),
            "image_ready must be false": lambda e: e["readiness"].__setitem__("image_ready", True),
            "the incomplete stack is not named among the blocking items": lambda e: e["readiness"].__setitem__("blocking", []),
        }
        for needle, fn in cases.items():
            with self.subTest(breach=needle):
                self.refused(fn, needle.strip())

    def test_readiness_never_passes_while_the_stack_is_incomplete(self):
        for mutate in (lambda e: None, lambda e: e["readiness"].__setitem__("image_ready", True),
                       lambda e: e["stack"].update(complete=True, status="COMPLETE")):
            ev = copy.deepcopy(self.base)
            mutate(ev)
            self.assertNotEqual(be.readiness_findings(ev, R), [])


if __name__ == "__main__":
    unittest.main()
