"""Evidence a record points at must actually be in the record.

`evidence/ff_route_pin_probe_2026_08_06/` shipped a README citing `probe_run.log`, which
`.gitignore`'s `*.log` rule silently excluded — the reference survived review, the file
did not survive the commit. Nothing about that failure is specific to one directory, so
the check is over every evidence manifest.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = REPO_ROOT / "evidence"


def manifests() -> list[Path]:
    """Only the manifests that declare this schema. Older evidence directories carry
    their own shapes; the universal guard below covers those without assuming one."""
    out = []
    for path in sorted(EVIDENCE.glob("*/manifest.json")):
        try:
            if json.loads(path.read_text()).get("schema") == "probe_evidence/1":
                out.append(path)
        except json.JSONDecodeError:
            continue
    return out


def has_git() -> bool:
    checked = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=REPO_ROOT,
                             capture_output=True, check=False)
    return checked.returncode == 0


class EvidenceManifestTests(unittest.TestCase):
    def test_there_is_at_least_one_manifest_to_check(self) -> None:
        """Otherwise every case below passes by having nothing to look at."""
        self.assertTrue(manifests(), "no evidence manifest found — this suite is vacuous")

    def test_every_listed_file_exists_and_matches_its_hash(self) -> None:
        for manifest_path in manifests():
            manifest = json.loads(manifest_path.read_text())
            for name, record in manifest["files"].items():
                with self.subTest(manifest=manifest_path.parent.name, file=name):
                    path = manifest_path.parent / name
                    self.assertTrue(path.is_file(), f"{path} is listed but absent")
                    self.assertEqual(
                        hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])

    def test_nothing_under_evidence_is_excluded_by_gitignore(self) -> None:
        """The universal guard, and the one that would have caught the original defect.
        It does not depend on any manifest schema: an evidence file that git ignores is
        a citation with nothing behind it, whoever wrote the directory."""
        if not has_git():
            self.skipTest("no git here — the ignore rules cannot be consulted")
        present = [str(path.relative_to(REPO_ROOT))
                   for path in sorted(EVIDENCE.rglob("*")) if path.is_file()]
        self.assertTrue(present, "evidence/ has no files — this check is vacuous")
        checked = subprocess.run(["git", "check-ignore", *present], cwd=REPO_ROOT,
                                 capture_output=True, text=True, check=False)
        self.assertEqual(checked.stdout.strip(), "",
                         "these evidence files are excluded by .gitignore:\n"
                         + checked.stdout)

    def test_every_listed_file_is_tracked(self) -> None:
        if not has_git():
            self.skipTest("no git here — tracking cannot be consulted")
        tracked = set(subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, text=True,
                                     capture_output=True, check=True).stdout.split())
        self.assertTrue(manifests(), "no probe manifest to check")
        for manifest_path in manifests():
            manifest = json.loads(manifest_path.read_text())
            for name in manifest["files"]:
                relative = str((manifest_path.parent / name).relative_to(REPO_ROOT))
                with self.subTest(file=relative):
                    self.assertIn(relative, tracked, f"{relative} is listed but untracked")

    def test_the_hash_note_is_present_and_does_not_overclaim(self) -> None:
        """A manifest of hashes invites being read as provenance. Say what it is."""
        for manifest_path in manifests():
            manifest = json.loads(manifest_path.read_text())
            with self.subTest(manifest=manifest_path.parent.name):
                note = manifest.get("note", "").lower()
                self.assertIn("integrity anchor", note)
                self.assertIn("do not prove", note)


if __name__ == "__main__":
    unittest.main()
