"""The submitted image is the image of the submitted SOURCE.

The owner's integration review of 2026-09-10 found the build evidence pinned at one commit
while a later commit changed a runtime string in `b2_app.c`: the binary held the old string,
the harness asserted the new one, and a green harness run therefore did not test the source
revision the image represents. A binary string-presence scan does not detect that — only a
comparison of the recorded build inputs with the tree does.

This test is that comparison. It refuses when any source the evidence records has moved, when
the recorded dependency set no longer covers the sources, or when the built image on disk is
not the one the evidence names. It does not rebuild; it checks that a rebuild is not owed.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))

FW = R / "firmware/b2"
EVIDENCE = R / "evidence/b2/build_evidence.json"
IMAGE = FW / "bsp/out/b2_app.bin"
ELF = FW / "bsp/out/b2_app.elf"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@unittest.skipUnless(EVIDENCE.is_file(), "no B2 build evidence yet")
class BuildEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = json.loads(EVIDENCE.read_text())

    def test_every_recorded_source_still_hashes_to_its_record(self):
        stale = []
        for rel, want in self.ev["sources"].items():
            p = FW / rel
            self.assertTrue(p.is_file(), rel)
            if sha(p) != want:
                stale.append(rel)
        self.assertEqual(stale, [], "the image predates these sources: rebuild and regenerate the evidence")

    def test_every_recorded_translation_unit_still_hashes(self):
        stale = []
        for rel, rec in self.ev["bsp_inputs"]["translation_units"].items():
            p = Path(rel)
            if not p.is_absolute():
                p = R / rel
            if not p.is_file():
                p = FW / Path(rel).name
            if not p.is_file():
                continue                      # a toolchain or embeddedsw unit outside the tree
            want = rec["sha256"] if isinstance(rec, dict) else rec
            if sha(p) != want:
                stale.append(rel)
        self.assertEqual(stale, [], "a linked translation unit moved after the build")

    def test_the_linked_repository_sources_are_all_recorded(self):
        """Every C file the build script links from this repository must be in `sources`."""
        script = (FW / "bsp/build.sh").read_text()
        line = [l for l in script.splitlines() if l.strip().startswith("for s in b2_app.c")][0]
        linked = [tok for tok in line.split("in", 1)[1].split(";")[0].split() if tok.endswith(".c")]
        self.assertIn("b2_app.c", linked)
        for name in linked:
            self.assertIn(name, self.ev["sources"], f"{name} is linked but not recorded")

    def test_the_evidence_was_taken_from_a_clean_tree(self):
        self.assertFalse(self.ev["git"]["worktree_dirty"],
                         "the evidence was taken from a dirty tree: regenerate it from a clean one")

    def test_two_clean_builds_agree_in_both_outputs(self):
        rep = self.ev["reproducibility"]
        self.assertEqual(len(rep["builds"]), 2)
        for b in rep["builds"]:
            self.assertIn("bin_sha256", b)
            self.assertIn("elf_sha256", b)
        self.assertTrue(rep["bin_identical"], "the two builds' binaries differ")
        self.assertTrue(rep["elf_identical"], "the two builds' ELFs differ")
        self.assertTrue(rep["reproduced_byte_identical"])
        self.assertEqual(rep["builds"][0]["bin_sha256"], self.ev["image"]["sha256"])
        self.assertEqual(rep["builds"][0]["elf_sha256"], self.ev["image"]["elf_sha256"])

    @unittest.skipUnless(IMAGE.is_file(), "no built image on disk")
    def test_the_image_on_disk_is_the_one_the_evidence_names(self):
        self.assertEqual(sha(IMAGE), self.ev["image"]["sha256"])
        self.assertEqual(IMAGE.stat().st_size, self.ev["image"]["bytes"])
        if ELF.is_file():
            self.assertEqual(sha(ELF), self.ev["image"]["elf_sha256"])

    def test_the_header_categories_are_reported_honestly(self):
        """The 86 headers are not 86 embeddedsw headers (the review's clarification)."""
        headers = self.ev["bsp_inputs"]["headers"]
        repo = [h for h in headers if str(h).startswith("firmware/b2/") or "/zynq_fabricmap/" in str(h)]
        self.assertTrue(len(headers) > len(repo) > 0, "the header set must span more than this repository")


if __name__ == "__main__":
    unittest.main()
