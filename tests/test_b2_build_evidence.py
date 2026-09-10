"""The submitted image is the image of the submitted SOURCE — and the guard that says so
must be shown to REFUSE, not merely to pass on good data.

The owner's integration review of 2026-09-10 found the evidence pinned at one commit while a
later commit changed a runtime string in `b2_app.c`. The first guard caught that, and the
owner's correction review then showed the guard itself was incomplete: seven isolated
corruptions of the evidence still passed it, because the tests read the real file and could
never be driven with a corrupted one.

So the checking is now a pure function — `b2_build_evidence.verify_findings(evidence, root)` —
and every case below drives it with a deep copy that has exactly one thing wrong. The seven
counterexamples the review named are the seven `test_refuses_*` cases; the three controls it
also ran are kept. One slower test recomputes the compiler's own dependency sets and requires
the recorded map to be them, so the map cannot be internally consistent but untrue.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b2_build_evidence as be  # noqa: E402

FW = R / "firmware/b2"
EVIDENCE = R / "evidence/b2/build_evidence.json"
IMAGE = FW / "bsp/out/b2_app.bin"
ELF = FW / "bsp/out/b2_app.elf"
BAD = "00" * 32


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def a_header(ev: dict, needle: str = "stdint.h") -> str:
    for k in ev["bsp_inputs"]["headers"]:
        if k.endswith(needle):
            return k
    return sorted(ev["bsp_inputs"]["headers"])[0]


@unittest.skipUnless(EVIDENCE.is_file(), "no B2 build evidence yet")
class Committed(unittest.TestCase):
    """The evidence as committed must stand on its own."""

    @classmethod
    def setUpClass(cls):
        cls.ev = json.loads(EVIDENCE.read_text())

    def test_the_committed_evidence_has_no_findings(self):
        self.assertEqual(be.verify_findings(self.ev, R), [])

    def test_the_outputs_exist_and_are_the_ones_it_names(self):
        """A completed image package requires the artifacts; it does not skip past them."""
        self.assertTrue(IMAGE.is_file(), "the image must be built")
        self.assertTrue(ELF.is_file(), "the ELF must be present")
        self.assertEqual(sha(IMAGE), self.ev["image"]["sha256"])
        self.assertEqual(sha(ELF), self.ev["image"]["elf_sha256"])
        self.assertEqual(IMAGE.stat().st_size, self.ev["image"]["bytes"])

    def test_the_inventory_is_the_whole_build(self):
        bi = self.ev["bsp_inputs"]
        want = be.expected_units(bi["build_script_lists"], bi["header_roots"])
        self.assertEqual(set(bi["translation_units"]), want)
        self.assertEqual(len(want), 47)
        console = [u for u in want if u.endswith("bsp/src/console.c")]
        self.assertEqual(len(console), 1, "the separately compiled console glue must be in the set")
        self.assertIn("bsp/src/console.c", self.ev["sources"])

    def test_the_recorded_dependencies_are_the_compilers(self):
        """Slower: re-run the compiler's own -M over every unit and require the recorded map."""
        if not (be.TC / "bin/arm-none-eabi-gcc").is_file():
            self.skipTest("the pinned cross toolchain is not present")
        bi = self.ev["bsp_inputs"]
        fresh = be.bsp_inputs()
        self.assertEqual(set(fresh["dependencies"]), set(bi["dependencies"]))
        for unit, deps in fresh["dependencies"].items():
            self.assertEqual(sorted(bi["dependencies"][unit]), sorted(deps), unit)
        self.assertEqual(set(fresh["headers"]), set(bi["headers"]))


@unittest.skipUnless(EVIDENCE.is_file(), "no B2 build evidence yet")
class Refuses(unittest.TestCase):
    """One thing wrong at a time. Every case must yield at least one finding."""

    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(EVIDENCE.read_text())

    def _refuses(self, mutate, needle: str):
        ev = copy.deepcopy(self.base)
        mutate(ev)
        findings = be.verify_findings(ev, R)
        self.assertTrue(findings, "the corrupted evidence was accepted")
        self.assertTrue(any(needle in x for x in findings), f"{needle!r} not named in {findings[:4]}")

    # ---- the three controls the review also ran
    def test_refuses_a_changed_application_hash(self):
        self._refuses(lambda ev: ev["sources"].__setitem__("b2_app.c", BAD), "source b2_app.c")

    def test_refuses_a_changed_image_hash(self):
        self._refuses(lambda ev: ev["image"].__setitem__("sha256", BAD), "the image")

    def test_refuses_a_dirty_tree_declaration(self):
        self._refuses(lambda ev: ev["git"].__setitem__("worktree_dirty", True), "dirty tree")

    # ---- the seven counterexamples of the correction review
    def test_refuses_a_second_build_that_disagrees(self):
        def mutate(ev):
            ev["reproducibility"]["builds"][1]["bin_sha256"] = BAD
            ev["reproducibility"]["builds"][1]["elf_sha256"] = BAD
        self._refuses(mutate, "the two builds")

    def test_refuses_a_wrong_header_hash(self):
        self._refuses(lambda ev: ev["bsp_inputs"]["headers"].__setitem__(a_header(ev), BAD), "header")

    def test_refuses_a_missing_header_entry(self):
        self._refuses(lambda ev: ev["bsp_inputs"]["headers"].pop(a_header(ev)), "has no hash")

    def test_refuses_a_wrong_compiler_hash(self):
        self._refuses(lambda ev: ev["toolchain"].__setitem__("gcc_sha256", BAD), "the compiler")

    def test_refuses_a_wrong_libc_hash(self):
        self._refuses(lambda ev: ev["bsp_inputs"]["toolchain_objects"]["libc.a"].__setitem__("sha256", BAD),
                      "runtime object libc.a")

    def test_refuses_a_nonexistent_external_unit(self):
        def mutate(ev):
            tus = ev["bsp_inputs"]["translation_units"]
            victim = next(k for k in tus if "embeddedsw" in k)
            tus["/nonexistent/xil_cache.c"] = tus.pop(victim)
            ev["bsp_inputs"]["dependencies"]["/nonexistent/xil_cache.c"] = ev["bsp_inputs"]["dependencies"].pop(victim)
        self._refuses(mutate, "does not exist")

    def test_refuses_the_console_removed_from_the_inventory(self):
        def mutate(ev):
            ev["sources"].pop("bsp/src/console.c")
            tus = ev["bsp_inputs"]["translation_units"]
            victim = next(k for k in tus if k.endswith("bsp/src/console.c"))
            tus.pop(victim)
            ev["bsp_inputs"]["dependencies"].pop(victim, None)
        self._refuses(mutate, "console.c")

    # ---- a few more the same structure makes free
    def test_refuses_a_runtime_object_that_is_not_recorded(self):
        self._refuses(lambda ev: ev["bsp_inputs"]["toolchain_objects"].pop("crti.o"), "crti.o")

    def test_refuses_an_extra_translation_unit(self):
        def mutate(ev):
            ev["bsp_inputs"]["translation_units"]["/tmp/extra.c"] = BAD
            ev["bsp_inputs"]["dependencies"]["/tmp/extra.c"] = []
        self._refuses(mutate, "not compiled by the build script")

    def test_refuses_a_unit_with_no_dependency_list(self):
        def mutate(ev):
            unit = next(k for k in ev["bsp_inputs"]["translation_units"] if k.endswith("b2_app.c"))
            for h in ev["bsp_inputs"]["dependencies"].pop(unit):
                ev["bsp_inputs"]["headers"].pop(h, None)
        self._refuses(mutate, "no dependency list")

    def test_refuses_a_verdict_that_disagrees_with_the_digests(self):
        self._refuses(lambda ev: ev["reproducibility"].__setitem__("elf_identical", False), "verdicts disagree")

    def test_refuses_a_build_that_is_not_the_named_image(self):
        self._refuses(lambda ev: ev["reproducibility"]["builds"][0].__setitem__("elf_sha256", BAD), "is not the named")

    def test_refuses_a_missing_section(self):
        for section in ("sources", "bsp_inputs", "image", "reproducibility", "git", "toolchain"):
            with self.subTest(section=section):
                self._refuses(lambda ev, k=section: ev.pop(k), section)

    def test_refuses_a_missing_bsp_subsection(self):
        for key in ("translation_units", "headers", "dependencies", "toolchain_objects",
                    "build_script_lists", "header_roots"):
            with self.subTest(key=key):
                self._refuses(lambda ev, k=key: ev["bsp_inputs"].pop(k), key)


if __name__ == "__main__":
    unittest.main()
