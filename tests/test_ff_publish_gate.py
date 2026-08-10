"""`gate_publish_ff_staging.py` judges the index, which is what the next commit contains.

The stager's attribute pre-check says the paths *would* be stored as pointers under the
published rule. It cannot say what actually entered the index, because `git add` happens
later and can be told otherwise. Both bypasses are exercised here for real — the filter
overridden on the command line, and the working rule edited between staging and adding —
because a gate that only refuses hand-written fixtures has not met the way this actually
goes wrong.

Every case builds a real repository with real Git LFS, offline: `git add` runs the clean
filter locally, so genuine pointers and genuine ordinary blobs both exist without a
remote.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import gate_publish_ff_staging as publish  # noqa: E402

RULE = "staging/**/*.bit filter=lfs diff=lfs merge=lfs -text\n"
RUN_ROOT = "staging/run_fixture"
COMMITMENT = "gate_runs/run_fixture/predictions.json"
SPECIMENS = ("FIXTURE_base", "FIXTURE_clkinv")

# What it actually takes to put ordinary blobs in the index on a normal install:
# `filter.lfs.process` wins over `clean`, so clearing `clean` alone changes nothing.
BYPASS = ["-c", "filter.lfs.process=", "-c", "filter.lfs.clean=cat",
          "-c", "filter.lfs.required=false"]


def git(root: Path, *arguments: str, check: bool = True):
    return subprocess.run(
        ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=test", *arguments],
        cwd=root, capture_output=True, text=True, check=check)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class PublishGateTests(unittest.TestCase):
    def staged(self, *, rule: str = RULE, add: list[str] | None = None,
               specimens: tuple[str, ...] = SPECIMENS) -> Path:
        """A repository with the rule and the commitment committed, and a staging added.

        The manifest is a **legal** `specimen_staging` 1.0.0 record, pinning a real
        commitment file. An earlier version of this fixture had no `prediction_commitment`
        at all, which meant the gate could not have rebuilt the committed specimen set
        even if it had tried — the fixture was hiding the hole rather than testing it.
        """
        if subprocess.run(["git", "lfs", "version"], capture_output=True,
                          check=False).returncode != 0:
            self.skipTest("git-lfs is not installed: the index gate cannot be answered")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        git(root, "init", "-q", "-b", "main")
        (root / ".gitattributes").write_text(rule)

        commitment = {"schema": "gate_predictions", "schema_version": "1.5.0",
                      "seed": "publish-gate-fixture",
                      "specimens": [{"specimen_id": specimen_id}
                                    for specimen_id in SPECIMENS],
                      "totals": {"specimens": len(SPECIMENS), "predictions": 1,
                                 "holdout_predictions": 1}}
        commitment_bytes = (json.dumps(commitment, indent=2) + "\n").encode()
        # The fixture's own frozen authority, standing in for the builder's hash pin.
        self.frozen = digest(commitment_bytes)
        commitment_path = root / COMMITMENT
        commitment_path.parent.mkdir(parents=True)
        commitment_path.write_bytes(commitment_bytes)
        # stand-ins for the sources the gate reads at run time, tracked so a case can
        # modify one: the point of the execution-source seal is that *any* tracked file
        # counts, not a hardcoded list of this gate's imports
        for relative, text in (("scripts/gate_build_ff_formal.py",
                                "COMMITMENT = 'gate_runs/run_fixture/predictions.json'\n"),
                               ("scripts/gate_measure_ff.py", "# pointer parser\n"),
                               ("schemas/specimen_staging.schema.json", "{}\n")):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        git(root, "add", ".gitattributes", COMMITMENT, "scripts", "schemas")
        git(root, "commit", "-q", "-m", "publish the rule, the commitment and the gates")

        entries = []
        for specimen_id in specimens:
            directory_path = root / RUN_ROOT / "specimens" / specimen_id
            directory_path.mkdir(parents=True)
            payload = f"synthetic bitstream {specimen_id}\n".encode() * 4
            (directory_path / "spec.bit").write_bytes(payload)
            attestation = ('{"schema": "specimen_attestation", "specimen_id": "'
                           + specimen_id + '"}\n').encode()
            (directory_path / "attestation.json").write_bytes(attestation)
            entries.append({
                "specimen_id": specimen_id,
                "bitstream": {
                    "path": f"{RUN_ROOT}/specimens/{specimen_id}/spec.bit",
                    "sha256": digest(payload)},
                "attestation": {
                    "path": f"{RUN_ROOT}/specimens/{specimen_id}/attestation.json",
                    "sha256": digest(attestation), "schema_version": "2.0.0"}})
        self.write_manifest(root, entries, commitment_bytes)
        git(root, *(add or ["add", RUN_ROOT]))
        return root

    def write_manifest(self, root: Path, entries: list, commitment_bytes: bytes) -> None:
        manifest = {
            "schema": "specimen_staging", "schema_version": "1.0.0",
            "run_id": "run_fixture",
            "prediction_commitment": {
                "run_id": "run_fixture", "path": COMMITMENT,
                "sha256": digest(commitment_bytes), "schema_version": "1.5.0",
                "seed": "publish-gate-fixture",
                "totals": {"specimens": len(SPECIMENS), "predictions": 1,
                           "holdout_predictions": 1}},
            "complete": True, "specimens": entries}
        (root / RUN_ROOT / "staging_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n")

    def manifest_of(self, root: Path) -> dict:
        return json.loads((root / RUN_ROOT / "staging_manifest.json").read_text())

    def rewrite_manifest(self, root: Path, manifest: dict) -> None:
        (root / RUN_ROOT / "staging_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n")
        git(root, "add", f"{RUN_ROOT}/staging_manifest.json")

    def asked(self, root: Path, *, authority: bool = True) -> list[str]:
        """`authority=True` substitutes the fixture's frozen commitment for the builder's.

        Substituted rather than bypassed: the rule under test is "an authority this commit
        cannot rewrite", and the fixture needs one of its own. The real constants are left
        in force by `authority=False`, which is its own case below.
        """
        if not authority:
            return publish.publication_problems(RUN_ROOT, root)
        with unittest.mock.patch.object(
                publish, "CANONICAL_COMMITMENT", publish.REPO / COMMITMENT), \
                unittest.mock.patch.object(publish, "COMMITTED_SHA256", self.frozen):
            return publish.publication_problems(RUN_ROOT, root)

    # -- the known answer ----------------------------------------------------------

    def test_a_correctly_added_staging_is_publishable(self) -> None:
        root = self.staged()
        self.assertEqual(self.asked(root), [])
        # and the index really does hold pointers, not the bytes
        listed = git(root, "ls-files", "-s", "--",
                     f"{RUN_ROOT}/specimens/{SPECIMENS[0]}/spec.bit").stdout
        blob = listed.split()[1]
        self.assertIn("git-lfs.github.com/spec/v1",
                      git(root, "cat-file", "blob", blob).stdout)

    # -- the two bypasses the pre-check cannot see ---------------------------------

    def test_adding_with_the_filter_overridden_is_refused(self) -> None:
        """The filter simply did not run: no rule was broken and every earlier check
        still passes.

        `filter.lfs.process` has to be cleared as well, and that is worth stating —
        overriding `clean` and `required` alone does **not** bypass anything where
        git-lfs installed its long-running process filter, which is every standard
        install. Checked before this case was written: with `clean=cat` alone the index
        still receives a pointer.
        """
        root = self.staged(add=BYPASS + ["add", RUN_ROOT])
        problems = self.asked(root)
        self.assertEqual(len([item for item in problems if "is not a pointer" in item]),
                         len(SPECIMENS), problems)
        self.assertTrue(any("no later commit undoes" in item for item in problems))

    def test_a_rule_narrowed_between_staging_and_adding_is_refused(self) -> None:
        """No flags at all: append one line to the working `.gitattributes` and add."""
        root = self.staged()
        git(root, "restore", "--staged", RUN_ROOT)
        (root / ".gitattributes").write_text(
            RULE + f"{RUN_ROOT}/specimens/FIXTURE_base/spec.bit -filter\n")
        git(root, "add", RUN_ROOT)
        problems = self.asked(root)
        self.assertTrue(any("FIXTURE_base" in item and "is not a pointer" in item
                            for item in problems), problems)

    # -- the set is exactly what the manifest names --------------------------------

    def test_a_missing_bitstream_is_refused(self) -> None:
        root = self.staged()
        git(root, "restore", "--staged",
            f"{RUN_ROOT}/specimens/FIXTURE_base/spec.bit")
        self.assertTrue(any("is named by the manifest and is not in the index" in item
                            for item in self.asked(root)), self.asked(root))

    def test_a_missing_attestation_is_refused(self) -> None:
        root = self.staged()
        git(root, "restore", "--staged",
            f"{RUN_ROOT}/specimens/FIXTURE_base/attestation.json")
        self.assertTrue(any("attestation.json is named by the manifest and is not in the "
                            "index" in item for item in self.asked(root)))

    def test_an_extra_staged_path_is_refused(self) -> None:
        root = self.staged()
        rogue = root / RUN_ROOT / "specimens" / "NOT_COMMITTED"
        rogue.mkdir(parents=True)
        (rogue / "spec.bit").write_bytes(b"uninvited\n")
        git(root, "add", RUN_ROOT)
        self.assertTrue(any("the manifest does not name" in item
                            for item in self.asked(root)), self.asked(root))

    def test_a_pointer_for_the_wrong_object_is_refused(self) -> None:
        """The pointer is well-formed and the filter ran; it names other content."""
        root = self.staged()
        manifest_path = root / RUN_ROOT / "staging_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["specimens"][0]["bitstream"]["sha256"] = "c" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        git(root, "add", RUN_ROOT)
        self.assertTrue(any("points at object" in item for item in self.asked(root)),
                        self.asked(root))

    # -- the reviewable half must stay reviewable ----------------------------------

    def test_a_json_stored_as_a_pointer_is_refused(self) -> None:
        for name, expected in (("staging_manifest.json", "the manifest is an ordinary"),
                               ("attestation.json", "attestations are ordinary")):
            with self.subTest(file=name):
                root = self.staged(rule=RULE + f"{RUN_ROOT}/**/{name} filter=lfs -text\n")
                git(root, "restore", "--staged", RUN_ROOT)
                git(root, "add", RUN_ROOT)
                self.assertTrue(any(expected in item for item in self.asked(root)),
                                self.asked(root))

    # -- the committed set is the authority, not the manifest ----------------------

    def test_a_manifest_cut_to_one_specimen_is_refused(self) -> None:
        """With the other specimen's paths dropped from the index too, the manifest and
        the index agree perfectly. Only the commitment says how many there should be."""
        root = self.staged()
        manifest = self.manifest_of(root)
        dropped = manifest["specimens"].pop()
        self.rewrite_manifest(root, manifest)
        for reference in (dropped["bitstream"]["path"], dropped["attestation"]["path"]):
            git(root, "restore", "--staged", reference)
        problems = self.asked(root)
        self.assertTrue(any("the commitment names 2" in item for item in problems),
                        problems)
        # and nothing else complains — which is the point of the case
        self.assertTrue(all("not in the index" not in item for item in problems), problems)

    def test_a_manifest_that_is_not_complete_is_refused(self) -> None:
        root = self.staged()
        manifest = self.manifest_of(root)
        manifest["complete"] = False
        self.rewrite_manifest(root, manifest)
        self.assertTrue(any("does not validate" in item or "complete" in item
                            for item in self.asked(root)), self.asked(root))

    def test_a_manifest_of_the_wrong_shape_is_refused_by_the_schema(self) -> None:
        """Asserted on the *schema* finding, not on any message: a later check happens to
        complain about a missing commitment too, so a looser assertion here would pass
        with the schema validation removed."""
        root = self.staged()
        manifest = self.manifest_of(root)
        manifest.pop("prediction_commitment")
        self.rewrite_manifest(root, manifest)
        problems = self.asked(root)
        self.assertTrue(any("staged manifest schema" in item and
                            "'prediction_commitment' is a required property" in item
                            for item in problems), problems)

    def test_an_unknown_manifest_field_is_refused(self) -> None:
        """`additionalProperties: false` — and nothing but the schema check sees this."""
        root = self.staged()
        manifest = self.manifest_of(root)
        manifest["staged_by_hand"] = True
        self.rewrite_manifest(root, manifest)
        self.assertTrue(any("staged manifest schema" in item
                            for item in self.asked(root)), self.asked(root))

    def test_a_commitment_that_moved_under_its_pin_is_refused(self) -> None:
        root = self.staged()
        Path(root / COMMITMENT).write_text('{"schema": "gate_predictions"}\n')
        git(root, "add", COMMITMENT)
        # the manifest still pins the frozen hash, so the refusal comes from the bytes
        self.assertTrue(any("in the index is not the frozen" in item
                            for item in self.asked(root)), self.asked(root))

    def test_rewriting_commitment_manifest_and_index_together_is_refused(self) -> None:
        """The blocker this authority exists for: cut the commitment to one specimen, cut
        the manifest to match, drop the other specimen's paths, and re-pin the manifest to
        the new commitment. All three records are then perfectly consistent — and none of
        them is the frozen one."""
        root = self.staged()
        keep = SPECIMENS[0]
        commitment = json.loads((root / COMMITMENT).read_text())
        commitment["specimens"] = [{"specimen_id": keep}]
        commitment["totals"]["specimens"] = 1
        payload = (json.dumps(commitment, indent=2) + "\n").encode()
        (root / COMMITMENT).write_bytes(payload)

        manifest = self.manifest_of(root)
        dropped = [entry for entry in manifest["specimens"]
                   if entry["specimen_id"] != keep]
        manifest["specimens"] = [entry for entry in manifest["specimens"]
                                 if entry["specimen_id"] == keep]
        manifest["prediction_commitment"]["sha256"] = digest(payload)
        manifest["prediction_commitment"]["totals"]["specimens"] = 1
        self.rewrite_manifest(root, manifest)
        for entry in dropped:
            for reference in (entry["bitstream"]["path"], entry["attestation"]["path"]):
                git(root, "restore", "--staged", reference)
        git(root, "add", COMMITMENT)

        problems = self.asked(root)
        # two independent refusals, and either alone would be enough: the manifest no
        # longer pins the frozen hash, and the commit is not staging-only
        self.assertTrue(any("the manifest pins commitment hash" in item
                            for item in problems), problems)
        self.assertTrue(any("a publication commit is staging-only" in item
                            for item in problems), problems)
        self.assertEqual(len(problems), 2, problems)

    def test_a_commitment_staged_for_deletion_is_refused(self) -> None:
        """HEAD still has it, so a fallback would resolve happily; the next tree does not."""
        root = self.staged()
        git(root, "rm", "-q", "--cached", COMMITMENT)
        problems = self.asked(root)
        self.assertTrue(any("is not in the index" in item and "frozen commitment" in item
                            for item in problems), problems)

    def test_a_manifest_pinning_something_other_than_the_frozen_commitment_is_refused(self) -> None:
        """With the real constants in force — the fixture's commitment is not the frozen
        one, and that alone must stop it."""
        root = self.staged()
        problems = self.asked(root, authority=False)
        self.assertTrue(any("the frozen commitment for this class is" in item
                            for item in problems), problems)
        self.assertTrue(any("gate_runs/run_2026_08_05_ff/predictions.json" in item
                            for item in problems), problems)

    def test_a_commitment_whose_totals_disagree_with_itself_is_refused(self) -> None:
        root = self.staged()
        commitment = json.loads((root / COMMITMENT).read_text())
        commitment["totals"]["specimens"] = 99
        payload = (json.dumps(commitment, indent=2) + "\n").encode()
        (root / COMMITMENT).write_bytes(payload)
        git(root, "add", COMMITMENT)
        manifest = self.manifest_of(root)
        manifest["prediction_commitment"]["sha256"] = digest(payload)
        manifest["prediction_commitment"]["totals"]["specimens"] = 99
        self.rewrite_manifest(root, manifest)
        with unittest.mock.patch.object(
                publish, "CANONICAL_COMMITMENT", publish.REPO / COMMITMENT), \
                unittest.mock.patch.object(publish, "COMMITTED_SHA256", digest(payload)):
            problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any("declares totals.specimens=99" in item for item in problems),
                        problems)

    def test_a_commitment_naming_a_specimen_twice_is_refused(self) -> None:
        """The rebuilt set has to be a set, and `len()` of a list with a repeat is not
        the number of specimens it names."""
        root = self.staged()
        commitment = json.loads((root / COMMITMENT).read_text())
        commitment["specimens"].append({"specimen_id": SPECIMENS[0]})
        commitment["totals"]["specimens"] = len(commitment["specimens"])
        payload = (json.dumps(commitment, indent=2) + "\n").encode()
        (root / COMMITMENT).write_bytes(payload)
        git(root, "add", COMMITMENT)
        manifest = self.manifest_of(root)
        manifest["prediction_commitment"]["sha256"] = digest(payload)
        manifest["prediction_commitment"]["totals"]["specimens"] = len(
            commitment["specimens"])
        self.rewrite_manifest(root, manifest)
        with unittest.mock.patch.object(
                publish, "CANONICAL_COMMITMENT", publish.REPO / COMMITMENT), \
                unittest.mock.patch.object(publish, "COMMITTED_SHA256", digest(payload)):
            problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any("names a specimen twice" in item for item in problems),
                        problems)

    def test_a_manifest_describing_the_commitment_differently_is_refused(self) -> None:
        """The manifest carries a copy of the commitment's own description. A copy that
        disagrees with the document it copies is a record about something else."""
        for field, value in (("seed", "another-seed"), ("schema_version", "1.9.0")):
            with self.subTest(field=field):
                root = self.staged()
                manifest = self.manifest_of(root)
                manifest["prediction_commitment"][field] = value
                self.rewrite_manifest(root, manifest)
                problems = self.asked(root)
                self.assertTrue(any(f"commitment {field} differs from the frozen "
                                    "commitment document" in item for item in problems),
                                problems)

    def test_a_duplicated_specimen_id_is_refused(self) -> None:
        root = self.staged()
        manifest = self.manifest_of(root)
        manifest["specimens"].append(json.loads(json.dumps(manifest["specimens"][0])))
        self.rewrite_manifest(root, manifest)
        self.assertTrue(any("twice" in item for item in self.asked(root)),
                        self.asked(root))

    def test_two_specimens_naming_one_artifact_are_refused(self) -> None:
        root = self.staged()
        manifest = self.manifest_of(root)
        manifest["specimens"][1]["bitstream"] = json.loads(
            json.dumps(manifest["specimens"][0]["bitstream"]))
        self.rewrite_manifest(root, manifest)
        self.assertTrue(any("is already named by" in item for item in self.asked(root)),
                        self.asked(root))

    # -- the bytes are the pinned bytes --------------------------------------------

    def test_an_attestation_edited_without_the_manifest_is_refused(self) -> None:
        """Still an ordinary blob, still the right path, still named by the manifest —
        and not the bytes the manifest pins."""
        root = self.staged()
        relative = f"{RUN_ROOT}/specimens/{SPECIMENS[0]}/attestation.json"
        (root / relative).write_text('{"schema": "specimen_attestation", "edited": 1}\n')
        git(root, "add", relative)
        problems = self.asked(root)
        self.assertTrue(any("does not hash to the value the manifest pins" in item
                            for item in problems), problems)

    # -- the change set is sealed --------------------------------------------------

    def test_a_publication_commit_that_also_edits_its_own_authority_is_refused(self) -> None:
        """The blocker this seal exists for. The frozen path and hash are read from a
        working-tree Python file, so a commit that stages an edited builder is judged by
        the authority it is rewriting. No further hash closes that — only refusing the
        change set does."""
        root = self.staged()
        builder = root / "scripts" / "gate_build_ff_formal.py"
        builder.parent.mkdir(parents=True, exist_ok=True)
        builder.write_text("COMMITMENT = 'somewhere/else.json'\n")
        git(root, "add", "scripts/gate_build_ff_formal.py")
        problems = self.asked(root)
        self.assertTrue(any("a publication commit is staging-only" in item
                            for item in problems), problems)
        self.assertTrue(any("scripts/gate_build_ff_formal.py" in item
                            for item in problems), problems)

    def test_a_publication_commit_that_also_lands_the_rule_is_refused(self) -> None:
        """`.gitattributes` is policy and lands before a publication, not with one."""
        root = self.staged()
        (root / ".gitattributes").write_text(RULE + "# touched\n")
        git(root, "add", ".gitattributes")
        self.assertTrue(any("a publication commit is staging-only" in item
                            for item in self.asked(root)), self.asked(root))

    def test_any_unrelated_staged_change_is_refused(self) -> None:
        for relative in ("docs/note.md", "schemas/whatever.json"):
            with self.subTest(path=relative):
                root = self.staged()
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("staged alongside a publication\n")
                git(root, "add", relative)
                self.assertTrue(any("a publication commit is staging-only" in item
                                    for item in self.asked(root)), self.asked(root))

    def test_a_manifest_path_unchanged_against_head_is_refused(self) -> None:
        """A path the manifest names that this commit does not change is a path this
        commit is not publishing."""
        root = self.staged()
        git(root, "commit", "-q", "-m", "publish once")
        git(root, "add", RUN_ROOT)
        problems = self.asked(root)
        self.assertTrue(any("staged but unchanged against HEAD" in item
                            for item in problems), problems)

    # -- the gate that ran is the gate the index carries ---------------------------

    def test_an_unstaged_edit_to_the_authority_is_refused(self) -> None:
        """The index seal says what the commit contains; it says nothing about what
        judged it. An unstaged edit to the file the frozen pin is read from changes the
        verdict while `git diff --cached` stays exactly a staging."""
        root = self.staged()
        (root / "scripts/gate_build_ff_formal.py").write_text(
            "COMMITMENT = 'somewhere/else.json'\n")
        problems = self.asked(root)
        self.assertTrue(any("differ between the working tree and the index" in item
                            for item in problems), problems)
        self.assertTrue(any("scripts/gate_build_ff_formal.py" in item
                            for item in problems), problems)
        # and the index seal is silent, which is the point of the case
        self.assertFalse(any("staging-only" in item for item in problems), problems)

    def test_an_unstaged_edit_to_any_other_runtime_source_is_refused(self) -> None:
        """Representative rather than exhaustive — the rule is "no tracked file differs",
        not a list of this gate's imports."""
        for relative in ("schemas/specimen_staging.schema.json",
                         "scripts/gate_measure_ff.py"):
            with self.subTest(path=relative):
                root = self.staged()
                (root / relative).write_text("# edited but not staged\n")
                problems = self.asked(root)
                self.assertTrue(any("differ between the working tree and the index" in item
                                    for item in problems), problems)
                self.assertTrue(any(relative in item for item in problems), problems)

    def test_an_artifact_swapped_after_git_add_is_refused(self) -> None:
        """Falls out of the same rule: under the normal filter a materialised `.bit`
        cleans back to the same pointer and reads clean, so a working file that differs
        is one that changed."""
        root = self.staged()
        (root / RUN_ROOT / "specimens" / SPECIMENS[0] / "spec.bit").write_bytes(
            b"swapped after the add\n")
        self.assertTrue(any("differ between the working tree and the index" in item
                            for item in self.asked(root)), self.asked(root))

    # -- the frame around it -------------------------------------------------------

    def test_a_manifest_absent_from_the_index_is_refused(self) -> None:
        root = self.staged()
        git(root, "restore", "--staged", f"{RUN_ROOT}/staging_manifest.json")
        self.assertTrue(any("the manifest that describes a publication" in item
                            for item in self.asked(root)))

    def test_nothing_staged_is_refused(self) -> None:
        root = self.staged()
        git(root, "restore", "--staged", RUN_ROOT)
        self.assertTrue(any("nothing is staged" in item for item in self.asked(root)))

    def test_publishing_before_the_policy_commit_landed_is_refused(self) -> None:
        """The likeliest operator mistake, and it gets its own message: the rule was never
        landed at all. Both this and the index check fire; the HEAD one is what says why."""
        root = self.staged()
        git(root, "rm", "-q", "--cached", ".gitattributes")
        (root / ".gitattributes").unlink()
        git(root, "commit", "-q", "-m", "no policy commit after all")
        git(root, "add", RUN_ROOT)
        problems = self.asked(root)
        self.assertTrue(any("is not in HEAD: the rule that keeps these paths in LFS "
                            "belongs to a policy commit" in item for item in problems),
                        problems)

    def test_a_rule_deleted_in_the_same_index_is_refused(self) -> None:
        """HEAD carries the rule and the commit removes it: `in_head or in_index` called
        that publishable, and every path after that commit is stored as an ordinary blob."""
        root = self.staged()
        git(root, "rm", "-q", "--cached", ".gitattributes")
        problems = self.asked(root)
        self.assertTrue(any("is not in the index" in item and ".gitattributes" in item
                            for item in problems), problems)
        self.assertTrue(any("A staged deletion of it counts" in item
                            for item in problems), problems)

    def test_a_rule_narrowed_in_the_same_index_is_refused(self) -> None:
        """The pointers in the index are correct; the rule that will be committed
        alongside them is not, so the next write of these paths is an ordinary blob."""
        root = self.staged()
        (root / ".gitattributes").write_text("staging/**/*.other filter=lfs -text\n")
        git(root, "add", ".gitattributes")
        problems = self.asked(root)
        self.assertTrue(any("the index's own .gitattributes resolves it to "
                            "filter=unspecified, not lfs" in item for item in problems),
                        problems)

    def test_the_rule_is_read_from_the_index_not_the_working_tree(self) -> None:
        """The worktree rule is correct and the staged one is not. What gets committed is
        the staged one, so that is the rule the paths will live under."""
        root = self.staged()
        (root / ".gitattributes").write_text("staging/**/*.other filter=lfs -text\n")
        git(root, "add", ".gitattributes")
        (root / ".gitattributes").write_text(RULE)   # tidy worktree, wrong index
        problems = self.asked(root)
        self.assertTrue(any("the index's own .gitattributes resolves it to "
                            "filter=unspecified, not lfs" in item for item in problems),
                        problems)

    def test_a_rule_swallowing_the_json_in_the_same_index_is_refused(self) -> None:
        root = self.staged()
        (root / ".gitattributes").write_text(RULE + f"{RUN_ROOT}/**/*.json filter=lfs\n")
        git(root, "add", ".gitattributes")
        self.assertTrue(any("ordinary Git file by ruling" in item
                            for item in self.asked(root)), self.asked(root))

    def test_a_tree_without_git_is_refused(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.assertTrue(any("not a git repository" in item for item in
                            publish.publication_problems(RUN_ROOT, Path(directory.name))))

    # -- the command line ----------------------------------------------------------

    def test_the_tool_runs_and_reports_its_verdict(self) -> None:
        root = self.staged(add=BYPASS + ["add", RUN_ROOT])
        checked = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/gate_publish_ff_staging.py"),
             "--run-root", RUN_ROOT, "--repo", str(root)],
            capture_output=True, text=True, check=False)
        self.assertEqual(checked.returncode, 1, checked.stdout)
        self.assertIn("REFUSING TO PUBLISH", checked.stdout)
        # the fixture's own reason, not "nothing is staged" from some other repository:
        # without --repo this judged the checkout the script lives in and passed for it
        self.assertIn("is not a pointer", checked.stdout)
        self.assertIn("Do not commit", checked.stdout)

    def test_the_tool_reports_a_pass_through_main(self) -> None:
        """The refusal path had a case and the pass path did not, so a crash lived on a
        line that only runs when everything is right — and it was found by running the
        real thing on the real 184, which is exactly the moment it must not crash.

        Through `main()` in-process rather than the CLI, because a passing run needs the
        fixture's own authority substituted and there is deliberately no flag for that:
        a command-line switch that replaces the frozen commitment would be the hole this
        gate exists to close.
        """
        import contextlib
        import io

        root = self.staged()
        output = io.StringIO()
        with unittest.mock.patch.object(
                publish, "CANONICAL_COMMITMENT", publish.REPO / COMMITMENT), \
                unittest.mock.patch.object(publish, "COMMITTED_SHA256", self.frozen), \
                unittest.mock.patch.object(
                    sys, "argv", ["gate_publish_ff_staging.py", "--run-root", RUN_ROOT,
                                  "--repo", str(root)]), \
                contextlib.redirect_stdout(output):
            code = publish.main()
        self.assertEqual(code, 0, output.getvalue())
        self.assertIn("PUBLISHABLE", output.getvalue())
        self.assertIn(f"{1 + 2 * len(SPECIMENS)} path(s) staged", output.getvalue())

    def test_the_documented_command_line_is_executable(self) -> None:
        """Mode 100644 makes every command line in the docstring exit 126."""
        tool = REPO_ROOT / "scripts/gate_publish_ff_staging.py"
        self.assertTrue(tool.stat().st_mode & 0o111, "the tool is not executable")
        self.assertTrue(tool.read_text().startswith("#!"), "no shebang")


if __name__ == "__main__":
    unittest.main()
