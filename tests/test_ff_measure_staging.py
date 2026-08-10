"""`gate_measure_ff.py` consumes a staging manifest, and consumes nothing else.

What is being falsified here is not "does the loader work" but the two properties the
measurement's authority rests on:

* **the set is the committed set, or there is no measurement.** Missing, extra,
  duplicated, escaping, mismatched or untracked references each refuse the whole run
  before anything is scored and before anything is written. A measurement over the
  specimens that happened to verify would carry the accounting of a complete run.
* **every path comes from the manifest.** The tool no longer knows the
  `<root>/<specimen_id>/spec.bit` naming rule, so it cannot disagree with the stager
  about which file it read, and the attestation reference it records is the manifest's
  entry verbatim — certificate 1.6 requires that reference to equal the staging entry
  exactly, which a re-hashed copy in `run/attestations/` cannot.

Every case builds its own synthetic staging, so the suite runs on a cold checkout with no
`build/` tree and no Vivado. The bitstreams are not real bitstreams on purpose: nothing
in this file may reach frame parsing, and a case that started to would fail loudly rather
than quietly measure something.
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

import gate_measure_ff as measure  # noqa: E402

PYTHON = sys.executable
TOOL = REPO_ROOT / "scripts/gate_measure_ff.py"
PART = "xc7z010clg400-1"
DESIGN = "a" * 64

SPECIMENS = (
    ("FIXTURE_X0Y0_base", "SLICE_X0Y0", "base", 11),
    ("FIXTURE_X0Y0_clkinv", "SLICE_X0Y0", "clkinv", 22),
)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def repo_relative(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


def published(relatives: list[str]) -> list[str]:
    """The "every reference is in HEAD with these bytes" check, stubbed as satisfied.

    Injected in every case that is about something else: these fixtures live in a scratch
    directory under the gitignored `build/`, so the real check refuses all of them and
    would make each case pass for the wrong reason. The real checker is exercised against
    purpose-built repositories in `PublishedEvidenceTests`.
    """
    return []


def pointers_ok(pinned: list, ordinary: list) -> list[str]:
    """The LFS pointer gate, stubbed as satisfied.

    Same reason as `published`: these fixtures are scratch files under a gitignored tree
    with no attribute rule and no HEAD blobs, so the real gate refuses all of them. It is
    exercised for real against purpose-built LFS repositories in `PointerGateTests`.
    """
    return []


def git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=test",
         *arguments], cwd=repository, capture_output=True, text=True, check=True)


class Bundle:
    """A complete, verifying staging — and the handles to break exactly one thing."""

    def __init__(self, root: Path, specimens=SPECIMENS) -> None:
        self.root = root
        self.specimens = tuple(specimens)
        self.run = root / "run_fixture"
        self.stage = root / "staging"
        self.run.mkdir()
        self.stage.mkdir()

        self.doc = {
            "schema": "gate_predictions",
            "schema_version": "1.5.0",
            "bit_class": "clb_ff_config",
            "seed": "0xFF07",
            "split_policy": {"rule": "fixture"},
            "specimens": [
                {"specimen_id": specimen_id, "site": site, "variant": variant,
                 "tile": "CLBLL_L_X2Y25", "tile_type": "CLBLL_L", "split": "mine",
                 "build_seed": seed}
                for specimen_id, site, variant, seed in self.specimens
            ],
            "predictions": [],
            "totals": {"specimens": len(self.specimens), "predictions": 1,
                       "holdout_predictions": 1},
        }
        self.commitment_path = self.run / "predictions.json"
        self.commitment_path.write_bytes(encode(self.doc))
        self.commitment_sha256 = digest(self.commitment_path.read_bytes())
        self.reference = {
            "run_id": self.run.name,
            "path": repo_relative(self.commitment_path),
            "sha256": self.commitment_sha256,
            "schema_version": self.doc["schema_version"],
            "seed": str(self.doc["seed"]),
            "totals": dict(self.doc["totals"]),
        }

        self.entries: list[dict] = []
        for specimen_id, site, variant, seed in self.specimens:
            directory = self.stage / specimen_id
            directory.mkdir()
            bit = directory / "spec.bit"
            bit.write_bytes(f"synthetic bitstream {specimen_id}\n".encode())
            bit_hash = digest(bit.read_bytes())
            attestation = {
                "schema": "specimen_attestation",
                "schema_version": "2.0.0",
                "profile": "ff_formal",
                "specimen_id": specimen_id,
                "prediction_commitment": dict(self.reference),
                "source_build": {
                    "schema": "ff_formal_stamp/1",
                    "completed": True,
                    "node_type": "implementation",
                    "instance": site,
                    "variant": variant,
                    "artifacts": {"spec.bit": bit_hash},
                    "recipe": {"commitment": self.commitment_sha256,
                               "build_seed": seed,
                               "part": PART,
                               "vivado_version": "2025.2",
                               "sources": {"vivado/specimen/specimen_ff_formal.v": DESIGN,
                                           "scripts/gate_build_ff_formal.py": "b" * 64}},
                },
                "resolved": {"clock_mode": "CLKINV" if variant == "clkinv" else "NOCLKINV"},
                "outputs": {"spec.bit": bit_hash},
            }
            attestation_path = directory / "attestation.json"
            attestation_path.write_bytes(encode(attestation))
            self.entries.append({
                "specimen_id": specimen_id,
                "bitstream": {"path": repo_relative(bit), "sha256": bit_hash},
                "attestation": {"path": repo_relative(attestation_path),
                                "sha256": digest(attestation_path.read_bytes()),
                                "schema_version": "2.0.0"},
            })
        self.manifest = {
            "schema": "specimen_staging",
            "schema_version": "1.0.0",
            "run_id": self.run.name,
            "prediction_commitment": dict(self.reference),
            "complete": True,
            "specimens": self.entries,
        }
        self.manifest_path = self.stage / "staging_manifest.json"
        self.write_manifest()

    # -- handles ------------------------------------------------------------------
    def write_manifest(self) -> None:
        self.manifest["specimens"] = self.entries
        self.manifest_path.write_bytes(encode(self.manifest))

    def attestation_of(self, index: int) -> dict:
        path = REPO_ROOT / self.entries[index]["attestation"]["path"]
        return json.loads(path.read_text())

    def rewrite_attestation(self, index: int, attestation: dict) -> None:
        """Rewrite one attestation and re-pin it, so the case under test is the record's
        content and not a hash mismatch it would trip first."""
        path = REPO_ROOT / self.entries[index]["attestation"]["path"]
        content = encode(attestation)
        path.write_bytes(content)
        self.entries[index]["attestation"]["sha256"] = digest(content)
        self.write_manifest()

    def load(self, tracked_check=published, pointer_check=pointers_ok):
        return measure.load_staging(self.manifest_path, self.commitment_path,
                                    self.commitment_sha256, self.doc, self.run.name,
                                    tracked_check=tracked_check,
                                    pointer_check=pointer_check)

    def refusal(self, test: unittest.TestCase, tracked_check=published,
                pointer_check=pointers_ok) -> str:
        with test.assertRaises(SystemExit) as caught:
            self.load(tracked_check=tracked_check, pointer_check=pointer_check)
        return str(caught.exception)


class StagingContractTests(unittest.TestCase):
    def bundle(self) -> Bundle:
        (REPO_ROOT / "build").mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=REPO_ROOT / "build")
        self.addCleanup(directory.cleanup)
        return Bundle(Path(directory.name))

    # -- the known answer ---------------------------------------------------------

    def test_a_complete_staging_loads_and_returns_the_manifests_own_references(self) -> None:
        bundle = self.bundle()
        reference, entries, attestations = bundle.load()

        self.assertEqual(reference["path"], repo_relative(bundle.manifest_path))
        self.assertEqual(reference["schema_version"], "1.0.0")
        # recomputed from the bytes on disk, not read out of any field
        self.assertEqual(reference["sha256"], digest(bundle.manifest_path.read_bytes()))
        self.assertEqual(set(entries), {item[0] for item in SPECIMENS})
        self.assertEqual(set(attestations), set(entries))
        for specimen_id, entry in entries.items():
            self.assertEqual(entry, next(item for item in bundle.entries
                                         if item["specimen_id"] == specimen_id))
            # exactly the three fields certificate 1.6 compares, and no convenience
            # extras: the verifier requires this dict to equal the staging entry
            self.assertEqual(set(entry["attestation"]), {"path", "sha256", "schema_version"})

    def test_the_manifest_hash_follows_the_bytes(self) -> None:
        """A reference that copied a field would not move when the file did."""
        bundle = self.bundle()
        before = bundle.load()[0]["sha256"]
        bundle.manifest_path.write_bytes(bundle.manifest_path.read_bytes() + b"\n")
        after = bundle.load()[0]["sha256"]
        self.assertNotEqual(before, after)
        self.assertEqual(after, digest(bundle.manifest_path.read_bytes()))

    # -- the set is the committed set ---------------------------------------------

    def test_a_missing_specimen_refuses_the_whole_run(self) -> None:
        bundle = self.bundle()
        bundle.entries.pop()
        bundle.write_manifest()
        message = bundle.refusal(self)
        self.assertIn("staging is not the committed set", message)
        self.assertIn("missing 1", message)

    def test_an_extra_specimen_refuses_the_whole_run(self) -> None:
        bundle = self.bundle()
        extra = json.loads(json.dumps(bundle.entries[0]))
        extra["specimen_id"] = "FIXTURE_not_committed"
        bundle.entries.append(extra)
        bundle.write_manifest()
        message = bundle.refusal(self)
        self.assertIn("staging is not the committed set", message)
        self.assertIn("extra 1", message)

    def test_a_duplicated_specimen_id_is_refused(self) -> None:
        bundle = self.bundle()
        bundle.entries.append(json.loads(json.dumps(bundle.entries[0])))
        bundle.write_manifest()
        self.assertIn("duplicates", bundle.refusal(self))

    def test_two_entries_pointing_at_one_file_are_refused(self) -> None:
        """Set equality alone would accept this: two ids, two entries, one bitstream."""
        bundle = self.bundle()
        bundle.entries[1]["bitstream"] = dict(bundle.entries[0]["bitstream"])
        bundle.write_manifest()
        self.assertIn("resolves to the same file", bundle.refusal(self))

    def test_two_spellings_of_one_file_are_still_one_file(self) -> None:
        """The reference strings differ, so a string-keyed check reports two staged
        specimens over one artifact. Identity has to be decided after resolution."""
        for label, rewritten in (("dot segment", "/./spec.bit"),
                                 ("doubled separator", "//spec.bit")):
            with self.subTest(spelling=label):
                bundle = self.bundle()
                first = bundle.entries[0]["bitstream"]
                bundle.entries[1]["bitstream"] = {
                    "path": first["path"].replace("/spec.bit", rewritten),
                    "sha256": first["sha256"]}
                bundle.write_manifest()
                self.assertNotEqual(bundle.entries[1]["bitstream"]["path"], first["path"])
                self.assertIn("resolves to the same file", bundle.refusal(self))

    def test_a_symlink_alias_of_another_staged_file_is_refused(self) -> None:
        """No string transformation relates these two references at all."""
        bundle = self.bundle()
        real = REPO_ROOT / bundle.entries[0]["bitstream"]["path"]
        alias = bundle.stage / "alias.bit"
        alias.symlink_to(real)
        bundle.entries[1]["bitstream"] = {
            "path": str(alias.relative_to(REPO_ROOT)),
            "sha256": bundle.entries[0]["bitstream"]["sha256"]}
        bundle.write_manifest()
        self.assertIn("resolves to the same file", bundle.refusal(self))

    # -- what is hashed is what is read --------------------------------------------

    def test_the_manifest_is_hashed_and_parsed_in_one_read(self) -> None:
        """Hash the path, re-open it, and a swap in between yields a record that pins A
        and was computed from B. The read is the one the parse gets."""
        bundle = self.bundle()
        original = bundle.manifest_path.read_bytes()
        swapped = dict(bundle.manifest, run_id="run_something_else")

        reads = {"count": 0}
        real_read = Path.read_bytes
        real_write = Path.write_bytes

        def read_once(self_path):
            payload = real_read(self_path)
            if self_path == bundle.manifest_path:
                reads["count"] += 1
                # the swap lands *after* this read returns; a second read would see it
                real_write(bundle.manifest_path, encode(swapped))
            return payload

        with unittest.mock.patch.object(Path, "read_bytes", read_once):
            reference, _, _ = bundle.load()
        self.assertEqual(reads["count"], 1)
        self.assertEqual(reference["sha256"], digest(original))

    def test_an_attestation_is_hashed_and_parsed_in_one_read(self) -> None:
        """Same rule one level down: the semantic values are read out of the bytes whose
        hash the measurement carries."""
        bundle = self.bundle()
        path = (REPO_ROOT / bundle.entries[0]["attestation"]["path"]).resolve()
        original = json.loads(path.read_bytes())
        real_read = Path.read_bytes
        real_write = Path.write_bytes

        def read_once(self_path):
            payload = real_read(self_path)
            if self_path == path:
                swapped = json.loads(payload)
                swapped["source_build"]["variant"] = "async"
                real_write(path, encode(swapped))
            return payload

        with unittest.mock.patch.object(Path, "read_bytes", read_once):
            _, _, attestations = bundle.load()
        # parsed from the verified bytes, not from what is on disk now
        self.assertEqual(attestations[bundle.entries[0]["specimen_id"]]
                         ["source_build"]["variant"],
                         original["source_build"]["variant"])
        self.assertEqual(json.loads(path.read_bytes())["source_build"]["variant"], "async")

    # -- every reference is resolved, and resolved safely -------------------------

    def test_a_traversing_or_absolute_path_never_reaches_the_filesystem(self) -> None:
        """The staging schema's own `repo_path` pattern rejects both spellings, so this
        pins where that boundary is enforced rather than asserting a message from the
        resolver below it."""
        for spelling in ("../outside/spec.bit", "/etc/passwd", "staging/../../spec.bit"):
            with self.subTest(path=spelling):
                bundle = self.bundle()
                bundle.entries[0]["bitstream"]["path"] = spelling
                bundle.write_manifest()
                self.assertIn("does not validate", bundle.refusal(self))

    def test_a_symlinked_path_that_leaves_the_repository_is_refused(self) -> None:
        """The one escape the path pattern cannot see: no `..`, no leading slash, and it
        still resolves outside. This is what `safe_child` is for, and without it the tool
        would hash and read a file the certificate could never pin."""
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        (Path(outside.name) / "spec.bit").write_bytes(b"elsewhere\n")
        bundle = self.bundle()
        link = bundle.root / "link"
        link.symlink_to(outside.name, target_is_directory=True)
        bundle.entries[0]["bitstream"]["path"] = str(
            (link / "spec.bit").relative_to(REPO_ROOT))
        bundle.write_manifest()
        self.assertIn("escapes allowed root", bundle.refusal(self))

    def test_a_missing_artifact_is_refused(self) -> None:
        bundle = self.bundle()
        (REPO_ROOT / bundle.entries[0]["bitstream"]["path"]).unlink()
        self.assertIn("bitstream does not exist", bundle.refusal(self))

    def test_a_bitstream_edited_after_staging_is_refused(self) -> None:
        bundle = self.bundle()
        (REPO_ROOT / bundle.entries[0]["bitstream"]["path"]).write_bytes(b"tampered\n")
        self.assertIn("bitstream does not match its pinned hash", bundle.refusal(self))

    def test_an_attestation_edited_after_staging_is_refused(self) -> None:
        bundle = self.bundle()
        path = REPO_ROOT / bundle.entries[0]["attestation"]["path"]
        path.write_bytes(path.read_bytes() + b" \n")
        self.assertIn("attestation does not match its pinned hash", bundle.refusal(self))

    # -- the commitment it claims is the commitment being scored -------------------

    def test_a_manifest_for_another_commitment_is_refused(self) -> None:
        bundle = self.bundle()
        bundle.manifest["prediction_commitment"]["sha256"] = "0" * 64
        bundle.write_manifest()
        self.assertIn("staged commitment hash differs", bundle.refusal(self))

    def test_a_manifest_pinning_another_predictions_file_is_refused(self) -> None:
        """Same hash, different file: the path must resolve to what is being scored."""
        bundle = self.bundle()
        twin = bundle.root / "twin.json"
        twin.write_bytes(bundle.commitment_path.read_bytes())
        bundle.manifest["prediction_commitment"]["path"] = repo_relative(twin)
        bundle.write_manifest()
        self.assertIn("staging pins a different predictions.json", bundle.refusal(self))

    def test_a_drifted_commitment_projection_is_refused(self) -> None:
        """`totals`, `seed` and `schema_version` are recomputed from the commitment
        document — a manifest that merely agrees with itself proves nothing."""
        for field, value in (("totals", {"specimens": 1, "predictions": 1,
                                         "holdout_predictions": 1}),
                             ("seed", "0x0000"),
                             ("schema_version", "1.9.0")):
            with self.subTest(field=field):
                bundle = self.bundle()
                bundle.manifest["prediction_commitment"][field] = value
                bundle.write_manifest()
                self.assertIn(f"staged commitment {field} differs from predictions.json",
                              bundle.refusal(self))

    def test_a_manifest_for_another_run_is_refused(self) -> None:
        bundle = self.bundle()
        bundle.manifest["run_id"] = "run_something_else"
        bundle.write_manifest()
        self.assertIn("is not the run being measured", bundle.refusal(self))

    # -- the staged record really describes that committed specimen ---------------

    def test_an_attestation_that_describes_another_specimen_is_refused(self) -> None:
        cases = {
            "attestation names specimen": ("specimen_id", "FIXTURE_other"),
            "built variant": (("source_build", "variant"), "async"),
            "built instance": (("source_build", "instance"), "SLICE_X9Y9"),
            "source build is not completed": (("source_build", "completed"), False),
            "build recipe pins a different commitment":
                (("source_build", "recipe", "commitment"), "0" * 64),
            "build recipe seed": (("source_build", "recipe", "build_seed"), 999),
            "build recipe has no part": (("source_build", "recipe", "part"), ""),
            "attestation pins a different prediction commitment":
                (("prediction_commitment", "sha256"), "0" * 64),
            "attested output bitstream is not the staged one":
                (("outputs", "spec.bit"), "0" * 64),
            "stamped bitstream is not the staged one":
                (("source_build", "artifacts", "spec.bit"), "0" * 64),
        }
        for expected, (where, value) in cases.items():
            with self.subTest(expected=expected):
                bundle = self.bundle()
                attestation = bundle.attestation_of(0)
                target = attestation
                keys = (where,) if isinstance(where, str) else where
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                bundle.rewrite_attestation(0, attestation)
                self.assertIn(expected, bundle.refusal(self))

    def test_a_recipe_without_exactly_one_design_source_is_refused(self) -> None:
        """`design_source_sha256` is required on every certificate specimen and a 2.0
        attestation has no field to copy it from, so it comes from the recipe's single
        `.v`. Zero or two of them is a change to what a specimen is, not a default."""
        for label, sources in (
                ("none", {"scripts/gate_build_ff_formal.py": "b" * 64}),
                ("two", {"vivado/specimen/specimen_ff_formal.v": DESIGN,
                         "vivado/specimen/specimen_ff.v": "c" * 64})):
            with self.subTest(designs=label):
                bundle = self.bundle()
                attestation = bundle.attestation_of(0)
                attestation["source_build"]["recipe"]["sources"] = sources
                bundle.rewrite_attestation(0, attestation)
                self.assertIn("does not name exactly one design source",
                              bundle.refusal(self))

    def test_a_schema_version_that_disagrees_with_the_manifest_is_refused(self) -> None:
        bundle = self.bundle()
        attestation = bundle.attestation_of(0)
        attestation["schema_version"] = "1.0.0"
        bundle.rewrite_attestation(0, attestation)
        self.assertIn("schema_version differs from the manifest entry",
                      bundle.refusal(self))

    # -- shape, and shape first ----------------------------------------------------

    def test_a_manifest_that_is_not_a_manifest_is_refused_before_anything_else(self) -> None:
        """Every check below the schema reads named fields. Reading them out of a document
        whose shape was never established is how a pass gets computed over something that
        is not a manifest."""
        bundle = self.bundle()
        bundle.manifest["complete"] = False
        bundle.manifest.pop("run_id")
        bundle.write_manifest()
        message = bundle.refusal(self)
        self.assertIn("does not validate", message)
        self.assertNotIn("is not the run being measured", message)

    def test_a_manifest_outside_the_repository_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / "staging_manifest.json"
            path.write_text("{}")
            with self.assertRaises(SystemExit) as caught:
                measure.load_staging(path, path, "0" * 64, {}, "run",
                                     tracked_check=published)
            self.assertIn("outside the repository", str(caught.exception))

    def test_a_manifest_that_does_not_exist_is_refused(self) -> None:
        bundle = self.bundle()
        bundle.manifest_path.unlink()
        self.assertIn("does not exist", bundle.refusal(self))

    # -- references a fresh clone cannot resolve -----------------------------------

    def test_an_unpublished_reference_is_refused(self) -> None:
        bundle = self.bundle()
        message = bundle.refusal(
            self, tracked_check=lambda paths: ["3 reference(s) are not in HEAD"])
        self.assertIn("not in HEAD", message)

    def test_every_reference_kind_reaches_the_pointer_gate(self) -> None:
        """The gate can only judge what it is handed, and it used to be handed only the
        staging entries — so the manifest and the commitment were never looked at, and an
        attribute rule naming just the manifest would have passed everything."""
        bundle = self.bundle()
        seen: list[tuple[list, list]] = []
        bundle.load(pointer_check=lambda pinned, ordinary: seen.append((pinned, ordinary))
                    or [])
        pinned, ordinary = seen[0]

        self.assertEqual({item[1] for item in pinned},
                         {entry["bitstream"]["path"] for entry in bundle.entries})
        self.assertEqual({item[2] for item in pinned},
                         {entry["bitstream"]["sha256"] for entry in bundle.entries})
        self.assertEqual(
            {item[1] for item in ordinary},
            {repo_relative(bundle.manifest_path), repo_relative(bundle.commitment_path)}
            | {entry["attestation"]["path"] for entry in bundle.entries})
        # nothing the measurement reads is in neither list
        self.assertEqual(set(), ({entry["bitstream"]["path"] for entry in bundle.entries}
                                 | {entry["attestation"]["path"] for entry in bundle.entries})
                         - {item[1] for item in pinned} - {item[1] for item in ordinary})

    def test_the_commitment_itself_is_checked_for_publication(self) -> None:
        """Not only the 184×2 artifacts: a measurement pinning a commitment that is not
        in HEAD is unrepeatable for exactly the same reason."""
        bundle = self.bundle()
        seen: list[list[str]] = []
        bundle.load(tracked_check=lambda paths: seen.append(list(paths)) or [])
        self.assertIn(repo_relative(bundle.commitment_path), seen[0])
        self.assertIn(repo_relative(bundle.manifest_path), seen[0])
        for entry in bundle.entries:
            self.assertIn(entry["bitstream"]["path"], seen[0])
            self.assertIn(entry["attestation"]["path"], seen[0])


class PointerGateTests(unittest.TestCase):
    """What HEAD says a staged bitstream is, against real Git LFS repositories.

    Real ones, built here and never pushed: `git lfs track` + `git add` runs the clean
    filter locally, so a genuine pointer blob and a genuine object store exist without a
    remote. Faking the pointer text would test the parser and nothing else — the point of
    the gate is what `git cat-file` returns for a path someone actually committed.
    """

    def repository(self, *, lfs: bool = True, attributes: str | None = None):
        """A real repository whose staged tree went through the real filter.

        Returns `(root, pinned, ordinary)` in the shape the gate takes: what must be an
        LFS pointer, and what must not.
        """
        if subprocess.run(["git", "lfs", "version"], capture_output=True,
                          check=False).returncode != 0:
            self.skipTest("git-lfs is not installed: the pointer gate cannot be answered")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        git(root, "init", "-q", "-b", "main")
        if lfs or attributes is not None:
            (root / ".gitattributes").write_text(
                attributes if attributes is not None
                else "staging/**/*.bit filter=lfs diff=lfs merge=lfs -text\n")
            git(root, "add", ".gitattributes")

        run = root / "staging" / "run"
        stage = run / "specimens" / "FIXTURE_base"
        stage.mkdir(parents=True)
        payload = b"synthetic bitstream bytes\n" * 8
        (stage / "spec.bit").write_bytes(payload)
        (stage / "attestation.json").write_text('{"schema": "specimen_attestation"}\n')
        (run / "staging_manifest.json").write_text('{"schema": "specimen_staging"}\n')
        commitment = root / "gate_runs" / "run" / "predictions.json"
        commitment.parent.mkdir(parents=True)
        commitment.write_text('{"schema": "gate_predictions"}\n')
        git(root, "add", "staging", "gate_runs")
        git(root, "commit", "-q", "-m", "stage")

        pinned = [("staged FIXTURE_base bitstream",
                   "staging/run/specimens/FIXTURE_base/spec.bit", digest(payload))]
        ordinary = [("staging manifest", "staging/run/staging_manifest.json"),
                    ("prediction commitment", "gate_runs/run/predictions.json"),
                    ("staged FIXTURE_base attestation",
                     "staging/run/specimens/FIXTURE_base/attestation.json")]
        return root, pinned, ordinary

    def asked(self, root: Path, pinned, ordinary) -> list[str]:
        with unittest.mock.patch.object(measure, "REPO", root):
            return measure.lfs_pointer_problems(pinned, ordinary)

    def relfs(self, root: Path, attributes: str, *paths: str) -> None:
        """Re-commit some paths under a different attribute rule, so the filter that runs
        on them is the one the rule names."""
        (root / ".gitattributes").write_text(attributes)
        for relative in paths:
            (root / relative).write_text((root / relative).read_text() + " ")
        git(root, "add", ".gitattributes", *paths)
        git(root, "commit", "-q", "-m", "re-scope the attribute rule")

    def test_a_committed_lfs_bitstream_passes(self) -> None:
        root, pinned, ordinary = self.repository()
        blob = subprocess.run(
            ["git", "cat-file", "blob", f"HEAD:{pinned[0][1]}"],
            cwd=root, capture_output=True, text=True, check=True).stdout
        # a real pointer, produced by the real filter, naming the real content
        self.assertIn("git-lfs.github.com/spec/v1", blob)
        self.assertIn(pinned[0][2], blob)
        self.assertEqual(blob.splitlines()[0].split()[0], "version")
        self.assertEqual(self.asked(root, pinned, ordinary), [])

    def test_an_ordinary_git_blob_is_refused(self) -> None:
        """The failure the gate exists for: 366 MiB of binary in ordinary history."""
        root, pinned, ordinary = self.repository(lfs=False)
        problems = self.asked(root, pinned, ordinary)
        self.assertTrue(any("ordinary Git blob" in item for item in problems), problems)
        self.assertTrue(any(".gitattributes is not in HEAD" in item for item in problems),
                        problems)

    def test_a_pointer_naming_another_object_is_refused(self) -> None:
        root, pinned, ordinary = self.repository()
        label, relative, _ = pinned[0]
        problems = self.asked(root, [(label, relative, "b" * 64)], ordinary)
        self.assertTrue(any("the manifest pins" in item for item in problems), problems)

    def test_a_malformed_pointer_is_refused_and_named_as_such(self) -> None:
        root, pinned, ordinary = self.repository()
        relative = pinned[0][1]
        version = f"version {measure.LFS_POINTER_VERSION}"
        for label, pointer in (
                ("no oid", f"{version}\nsize 200\n"),
                ("not sha256", f"{version}\noid md5:deadbeef\nsize 200\n"),
                ("short digest", f"{version}\noid sha256:abcd\nsize 200\n"),
                ("no size", f"{version}\noid sha256:{'a' * 64}\n"),
                ("valueless line", f"{version}\nnonsense\n"),
                # a truncated pointer: without the length rule this reached
                # `fields["oid"]` and raised, and a gate that crashes has judged nothing
                ("version only", f"{version}\n"),
                ("out of order", f"{version}\nsize 200\noid sha256:{'a' * 64}\n"),
                ("an unknown extra field",
                 f"{version}\noid sha256:{'a' * 64}\nsize 200\nbanana value\n")):
            with self.subTest(pointer=label):
                # written with the filter disabled, so the damaged text is what lands in
                # HEAD — which is exactly how a hand-edited pointer would arrive
                blob = subprocess.run(
                    ["git", "-c", "filter.lfs.clean=cat", "-c", "filter.lfs.required=false",
                     "hash-object", "-w", "--stdin"],
                    cwd=root, input=pointer, capture_output=True, text=True,
                    check=True).stdout.strip()
                git(root, "update-index", "--add", "--cacheinfo", f"100644,{blob},{relative}")
                git(root, "-c", "filter.lfs.required=false", "commit", "-q", "-m", label)
                problems = self.asked(root, pinned, ordinary)
                self.assertTrue(any("malformed LFS pointer" in item for item in problems),
                                (label, problems))

    def test_a_path_no_filter_governs_is_refused(self) -> None:
        """A pointer can be correct while the rule that keeps it one has been narrowed;
        the next commit of that file would then be an ordinary blob."""
        root, pinned, ordinary = self.repository()
        (root / ".gitattributes").write_text("staging/**/*.other filter=lfs -text\n")
        git(root, "add", ".gitattributes")
        git(root, "commit", "-q", "-m", "narrow the rule")
        problems = self.asked(root, pinned, ordinary)
        self.assertTrue(any("no LFS filter governs this path" in item for item in problems),
                        problems)

    def test_an_ordinary_reference_stored_as_a_pointer_is_refused(self) -> None:
        """Each of the three JSON kinds on its own, because a gate that only sees the
        staging entries cannot see two of them at all — an attribute rule naming just the
        manifest passed every other check while the manifest left the repository.
        """
        for label, relative in (
                ("manifest", "staging/run/staging_manifest.json"),
                ("commitment", "gate_runs/run/predictions.json"),
                ("attestation", "staging/run/specimens/FIXTURE_base/attestation.json")):
            with self.subTest(reference=label):
                root, pinned, ordinary = self.repository()
                self.relfs(root,
                           "staging/**/*.bit filter=lfs -text\n"
                           f"{relative} filter=lfs -text\n",
                           relative)
                blob = subprocess.run(["git", "cat-file", "blob", f"HEAD:{relative}"],
                                      cwd=root, capture_output=True, text=True,
                                      check=True).stdout
                self.assertIn("git-lfs.github.com/spec/v1", blob,
                              "the fixture did not actually store a pointer")
                problems = self.asked(root, pinned, ordinary)
                self.assertTrue(
                    any("ordinary Git file by ruling" in item for item in problems),
                    (label, problems))

    def test_an_ordinary_reference_missing_from_head_is_refused(self) -> None:
        root, pinned, ordinary = self.repository()
        ordinary.append(("staging manifest", "staging/run/never_committed.json"))
        problems = self.asked(root, pinned, ordinary)
        self.assertTrue(any("is not in HEAD" in item for item in problems), problems)

    def test_without_git_authority_the_pointer_gate_refuses(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        problems = self.asked(Path(directory.name), [], [])
        self.assertTrue(any("no git authority" in item for item in problems), problems)

    def test_the_gate_reads_head_and_not_the_working_file(self) -> None:
        """A pointer-only checkout has bytes on disk that are not the bitstream, and a
        materialised one has the bitstream whatever HEAD holds. Neither is the witness."""
        root, pinned, ordinary = self.repository()
        (root / pinned[0][1]).write_bytes(b"whatever the worktree happens to hold\n")
        self.assertEqual(self.asked(root, pinned, ordinary), [])


class PublishedEvidenceTests(unittest.TestCase):
    """"Tracked" was the wrong question, so these are the four states it confused.

    Each runs against a purpose-built repository rather than this one, so the cases are
    real git answers and still run from a cold checkout — which is the point: a `git
    archive` export can exercise this function, and precisely because it cannot satisfy
    it, that export can never produce a measurement.
    """

    def repository(self) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        git(root, "init", "-q", "-b", "main")
        return root

    def committed(self) -> Path:
        root = self.repository()
        (root / "artifact.bin").write_bytes(b"published\n")
        git(root, "add", "artifact.bin")
        git(root, "commit", "-q", "-m", "publish")
        return root

    def asked(self, root: Path, relatives: list[str]) -> list[str]:
        with unittest.mock.patch.object(measure, "REPO", root):
            return measure.uncommitted_references(relatives)

    def test_a_clean_head_is_accepted(self) -> None:
        self.assertEqual(self.asked(self.committed(), ["artifact.bin"]), [])

    def test_added_to_the_index_but_never_committed_is_refused(self) -> None:
        """The state the old check passed: `git add` makes a file tracked, and tracked is
        not published."""
        root = self.committed()
        (root / "staged.bin").write_bytes(b"only in the index\n")
        git(root, "add", "staged.bin")
        problems = self.asked(root, ["artifact.bin", "staged.bin"])
        self.assertTrue(any("not in HEAD" in item for item in problems), problems)

    def test_committed_and_then_edited_is_refused(self) -> None:
        """Also passed before: the path is in HEAD, but not with these bytes — so a clone
        would score something else."""
        root = self.committed()
        (root / "artifact.bin").write_bytes(b"edited after publication\n")
        problems = self.asked(root, ["artifact.bin"])
        self.assertTrue(any("differ from HEAD" in item for item in problems), problems)

    def test_without_git_authority_it_refuses_rather_than_assuming(self) -> None:
        """The worst of the three: no git meant "nothing is untracked", which read as
        approval. Here the answer *is* the evidence, so its absence is a refusal."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        problems = self.asked(Path(directory.name), ["artifact.bin"])
        self.assertTrue(any("no git authority" in item for item in problems), problems)

    def test_an_initialised_repository_with_no_commit_is_refused(self) -> None:
        """`git rev-parse HEAD` fails before any commit exists — that is still no
        authority, not an empty answer."""
        problems = self.asked(self.repository(), ["artifact.bin"])
        self.assertTrue(any("no git authority" in item for item in problems), problems)


class NoBuildTreeTests(unittest.TestCase):
    """The tool cannot read a build tree — not "does not", cannot."""

    def test_there_is_no_build_option(self) -> None:
        helped = subprocess.run([PYTHON, str(TOOL), "--help"], cwd=REPO_ROOT, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                check=False)
        self.assertEqual(helped.returncode, 0, helped.stdout)
        self.assertIn("--staging-manifest", helped.stdout)
        self.assertNotIn("--build BUILD", helped.stdout)

    def test_the_path_builder_is_gone(self) -> None:
        self.assertFalse(hasattr(measure, "bit_path"))

    def test_a_refused_staging_writes_no_measurement_and_no_attestation_copies(self) -> None:
        """The promise is not "it fails", it is "it fails before writing anything"."""
        (REPO_ROOT / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "build") as directory:
            bundle = Bundle(Path(directory))
            bundle.entries.pop()
            bundle.write_manifest()
            out = bundle.run / "measurement.json"
            checked = subprocess.run(
                [PYTHON, str(TOOL), "--run", str(bundle.run),
                 "--staging-manifest", str(bundle.manifest_path), "--out", str(out)],
                cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, check=False)
            self.assertNotEqual(checked.returncode, 0, checked.stdout)
            self.assertIn("refusing to measure", checked.stdout)
            self.assertIn("staging is not the committed set", checked.stdout)
            self.assertFalse(out.exists(), "a refused run wrote a measurement")
            self.assertFalse((bundle.run / "attestations").exists(),
                             "a refused run created the attestation copy directory")


class FrameCacheTests(unittest.TestCase):
    """184 parsed bitstreams are several GB. The cache has to be a constant."""

    def counting_cache(self, size=None):
        loaded: list[str] = []
        cache = measure.FrameCache(lambda specimen_id: loaded.append(specimen_id)
                                   or {"id": specimen_id},
                                   **({} if size is None else {"size": size}))
        return cache, loaded

    def test_the_cache_does_not_grow_with_the_committed_set(self) -> None:
        cache, loaded = self.counting_cache()
        for index in range(184):
            cache.frames_of(f"specimen_{index:03d}")
            self.assertLessEqual(len(cache), cache.size)
        self.assertEqual(len(loaded), 184)
        self.assertEqual(cache.evictions, 184 - cache.size)
        self.assertEqual(len(cache), cache.size)

    def test_it_is_least_recently_used_so_a_shared_baseline_stays(self) -> None:
        """Why an LRU and not a per-pair teardown: every pair in an instance is
        differenced against one baseline, and re-parsing that 23 times per instance is
        the cost this ordering avoids."""
        cache, loaded = self.counting_cache(size=2)
        for variant in range(6):
            cache.frames_of("base")
            cache.frames_of(f"variant_{variant}")
        self.assertEqual(loaded.count("base"), 1)
        self.assertEqual(len(loaded), 7)

    def test_a_repeat_after_eviction_goes_back_through_the_loader(self) -> None:
        """Which is what keeps the hash check covering the whole run, not just the
        first read of each specimen."""
        cache, loaded = self.counting_cache(size=2)
        for specimen_id in ("a", "b", "c", "a"):
            cache.frames_of(specimen_id)
        self.assertEqual(loaded, ["a", "b", "c", "a"])

    def test_a_cache_too_small_to_hold_a_pair_is_refused(self) -> None:
        with self.assertRaises(ValueError) as caught:
            measure.FrameCache(lambda specimen_id: {}, size=1)
        self.assertIn("both endpoints", str(caught.exception))


class Frames(dict):
    """An empty frame map that still knows which specimen it came from.

    Empty so `raw_diff` sees no changed bits; labelled so the tile-bit stub can answer
    per endpoint. The point of the stubs is that *no real bitstream exists in this suite*
    — measuring the real 184 is not something a test may do — while everything above
    frame parsing runs for real.
    """

    def __init__(self, specimen_id: str) -> None:
        super().__init__()
        self.specimen_id = specimen_id


class MeasurementRecordTests(unittest.TestCase):
    """What ends up in `measurement.json`, run through `main()` end to end."""

    ASSERTING = SPECIMENS[1][0]
    TOKEN = "AFF.ZINI"
    ADDRESS = {"far": "0x00400A00", "word": 31, "bit": 3}

    def prediction(self, asserting: str, comparison: str, feature: str) -> dict:
        return {
            "specimen_id": asserting,
            "comparison_specimen_id": comparison,
            "feature": feature,
            "split": "holdout",
            "rule_file": "prjxray/zynq7/segbits_clbll_l.db",
            "predicted_assignments": [{"token": self.TOKEN, "address": self.ADDRESS,
                                       "expected_value": 1}],
            "expected_transition": {"before": 0, "after": 1},
            "semantic_assertion": {
                "kind": "member_identity", "semantic": True,
                "claim": "the fixture's clock mode is the one this feature names",
                "predicted_member": "CLBLL_L.SLICEL_X0.CLKINV",
                "attestation_field": "/resolved/clock_mode",
                "expected_value": "CLKINV"},
        }

    def prepared(self, variants: int = 1) -> Bundle:
        """A verifying staging whose commitment carries one prediction per variant.

        `variants` exists so the cache can be driven past its bound with a committed set
        big enough to evict — the shape of the real run, at a size a test may build.
        """
        (REPO_ROOT / "build").mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=REPO_ROOT / "build")
        self.addCleanup(directory.cleanup)
        specimens = SPECIMENS if variants == 1 else (SPECIMENS[0],) + tuple(
            (f"FIXTURE_X0Y0_v{index:02d}", "SLICE_X0Y0", f"v{index:02d}", 100 + index)
            for index in range(variants))
        bundle = Bundle(Path(directory.name), specimens)
        bundle.doc["predictions"] = [
            self.prediction(specimen_id, SPECIMENS[0][0],
                            f"CLBLL_L.SLICEL_X0.AFF.ZINI_{index:02d}")
            for index, (specimen_id, *_rest) in enumerate(specimens[1:])]
        bundle.doc["totals"] = {"specimens": len(specimens), "predictions": variants,
                                "holdout_predictions": variants}
        bundle.commitment_path.write_bytes(encode(bundle.doc))
        # the commitment changed, so everything that pins it has to be re-pinned
        self.repin(bundle)
        return bundle

    def measured(self, parse_frames=None, bundle=None,
                 cache_size=None) -> tuple[Bundle, dict]:
        bundle = bundle if bundle is not None else self.prepared()
        out = bundle.run / "measurement.json"
        argv = [str(TOOL), "--run", str(bundle.run),
                "--staging-manifest", str(bundle.manifest_path), "--out", str(out)]

        def default_parse_frames(path, cols, layout, data=None):
            return {"frames": Frames(Path(path).parent.name)}

        def read_tile_bits(frames, block):
            # the baseline endpoint reads 0, every asserting endpoint reads 1
            return {self.TOKEN: 0 if frames.specimen_id == SPECIMENS[0][0] else 1}

        size = cache_size if cache_size is not None else measure.FRAME_CACHE_SIZE
        with unittest.mock.patch.object(sys, "argv", argv), \
                unittest.mock.patch.object(measure, "parse_frames",
                                           parse_frames or default_parse_frames), \
                unittest.mock.patch.object(measure, "read_tile_bits", read_tile_bits), \
                unittest.mock.patch.object(measure, "FRAME_CACHE_SIZE", size), \
                unittest.mock.patch.object(measure, "uncommitted_references", published), \
                unittest.mock.patch.object(measure, "lfs_pointer_problems", pointers_ok):
            # The publication check is the one thing that cannot hold here: this staging
            # lives in a scratch directory under the gitignored `build/`, so it is stubbed
            # and exercised for real in PublishedEvidenceTests.
            self.assertEqual(measure.main(), 0)
        return bundle, json.loads(out.read_text())

    def repin(self, bundle: Bundle) -> None:
        """Re-pin every reference to the edited commitment, the way the stager would."""
        bundle.commitment_sha256 = digest(bundle.commitment_path.read_bytes())
        bundle.reference["sha256"] = bundle.commitment_sha256
        bundle.reference["totals"] = dict(bundle.doc["totals"])
        for index, entry in enumerate(bundle.entries):
            attestation = bundle.attestation_of(index)
            attestation["prediction_commitment"] = dict(bundle.reference)
            attestation["source_build"]["recipe"]["commitment"] = bundle.commitment_sha256
            bundle.rewrite_attestation(index, attestation)
        bundle.manifest["prediction_commitment"] = dict(bundle.reference)
        bundle.write_manifest()

    def test_the_measurement_carries_the_manifest_reference_and_the_staged_ones(self) -> None:
        bundle, measurement = self.measured()

        self.assertEqual(measurement["schema_version"], "1.6.0")
        self.assertEqual(measurement["staging_manifest"], {
            "path": repo_relative(bundle.manifest_path),
            "sha256": digest(bundle.manifest_path.read_bytes()),
            "schema_version": "1.0.0"})

        by_id = {record["specimen_id"]: record for record in measurement["specimens"]}
        self.assertEqual(set(by_id), {item[0] for item in SPECIMENS})
        for entry in bundle.entries:
            record = by_id[entry["specimen_id"]]
            # verbatim, because certificate 1.6 compares this reference with the staging
            # entry for equality — not for agreement on the fields it happens to share
            self.assertEqual(record["attestation"], entry["attestation"])
            self.assertEqual(record["bitstream"], entry["bitstream"])
            self.assertEqual(record["bitstream_sha256"], entry["bitstream"]["sha256"])
            self.assertEqual(record["part"], PART)
            self.assertEqual(record["vivado_version"], "2025.2")
            self.assertEqual(record["design_source_sha256"], DESIGN)
        self.assertEqual([record["build_seed"] for record in measurement["specimens"]],
                         [item[3] for item in SPECIMENS])

    def test_no_attestation_is_copied_into_the_run(self) -> None:
        bundle, _ = self.measured()
        self.assertFalse((bundle.run / "attestations").exists())
        staged = {entry["attestation"]["path"] for entry in bundle.entries}
        for record in json.loads((bundle.run / "measurement.json").read_text())["specimens"]:
            self.assertIn(record["attestation"]["path"], staged)

    def test_a_bitstream_swapped_between_verification_and_scoring_is_caught(self) -> None:
        """`load_staging` hashed the file; that read is over. The tamper hook fires in the
        window the loader cannot cover — a run that scored these frames while pinning the
        old hash would be a record about bytes nobody measured."""
        bundle = self.prepared()
        real_loader = measure.load_staging

        def tamper_after_verification(*arguments, **keywords):
            loaded = real_loader(*arguments, **keywords)
            target = REPO_ROOT / bundle.entries[0]["bitstream"]["path"]
            target.write_bytes(b"swapped after the check\n")
            return loaded

        out = bundle.run / "measurement.json"
        argv = [str(TOOL), "--run", str(bundle.run),
                "--staging-manifest", str(bundle.manifest_path), "--out", str(out)]
        with unittest.mock.patch.object(sys, "argv", argv), \
                unittest.mock.patch.object(measure, "load_staging",
                                           tamper_after_verification), \
                unittest.mock.patch.object(measure, "uncommitted_references", published), \
                unittest.mock.patch.object(measure, "lfs_pointer_problems", pointers_ok):
            with self.assertRaises(SystemExit) as caught:
                measure.main()
        self.assertIn("changed after staging verification", str(caught.exception))
        self.assertFalse(out.exists())

    def test_the_parser_is_given_the_bytes_that_were_hashed(self) -> None:
        """Not "hashed, then handed a path it re-reads": the stub rewrites the file and
        the parse still sees the verified bytes, which is the only way the record's hash
        describes what was scored."""
        seen: list[bytes] = []

        def parse_frames(path, cols, layout, data=None):
            self.assertIsNotNone(data, "the parser was given a path to re-read")
            seen.append(data)
            Path(path).write_bytes(b"rewritten while parsing\n")
            self.assertNotEqual(Path(path).read_bytes(), data)
            return {"frames": Frames(Path(path).parent.name)}

        _, measurement = self.measured(parse_frames=parse_frames)
        self.assertEqual(len(seen), len(SPECIMENS))
        for payload, (specimen_id, _site, _variant, _seed) in zip(seen, SPECIMENS):
            self.assertEqual(digest(payload), next(
                record["bitstream_sha256"] for record in measurement["specimens"]
                if record["specimen_id"] == specimen_id))

    def test_eviction_changes_nothing_about_what_is_measured(self) -> None:
        """Run one committed set twice: once with room for every specimen, once with a
        cache small enough to evict on almost every access. The bound is a memory
        decision and it must not be able to become an evidence decision."""
        watched: list[measure.FrameCache] = []

        class Watched(measure.FrameCache):
            def __init__(self, load, size=None):
                super().__init__(load, size)
                self.peak = 0
                watched.append(self)

            def frames_of(self, specimen_id):
                frames = super().frames_of(specimen_id)
                self.peak = max(self.peak, len(self))
                return frames

        with unittest.mock.patch.object(measure, "FrameCache", Watched):
            _, roomy = self.measured(bundle=self.prepared(variants=8), cache_size=64)
            _, cramped = self.measured(bundle=self.prepared(variants=8), cache_size=2)

        roomy_cache, cramped_cache = watched
        self.assertEqual(roomy_cache.evictions, 0)
        self.assertGreater(cramped_cache.evictions, 0, "the small cache never evicted, "
                                                       "so this compares nothing")
        self.assertLessEqual(cramped_cache.peak, 2)
        self.assertGreater(cramped_cache.parses, roomy_cache.parses)
        self.assertEqual(roomy_cache.parses, 9, "the roomy run should parse each once")

        for record in (roomy, cramped):
            record.pop("staging_manifest")
            record.pop("prediction_commitment")
            for specimen in record["specimens"]:
                specimen.pop("bitstream")
                specimen.pop("attestation")
        self.assertEqual(roomy, cramped)
        self.assertEqual(len(roomy["accounting"]), 8)
        self.assertEqual(roomy["totals"]["holdout"]["tp"], 8)
        self.assertEqual(roomy["decision"], "PASS")

    def test_a_bitstream_swapped_while_evicted_is_caught_on_the_next_use(self) -> None:
        """The cache is what makes this reachable: the second use of a specimen is a
        second read, and it must be a second verification too."""
        bundle = self.prepared(variants=4)
        first = REPO_ROOT / bundle.entries[0]["bitstream"]["path"]
        seen: list[str] = []

        def parse_frames(path, cols, layout, data=None):
            seen.append(Path(path).parent.name)
            if len(seen) == 3:
                # the baseline has been evicted by now; corrupt it before it is re-read
                first.write_bytes(b"swapped while evicted\n")
            return {"frames": Frames(Path(path).parent.name)}

        with self.assertRaises(SystemExit) as caught:
            self.measured(parse_frames=parse_frames, bundle=bundle, cache_size=2)
        self.assertIn("changed after staging verification", str(caught.exception))
        self.assertFalse((bundle.run / "measurement.json").exists())

    def test_the_semantic_value_is_read_from_the_staged_attestation(self) -> None:
        _, measurement = self.measured()
        outcome = measurement["results"][0]["semantic_outcome"]
        self.assertEqual(outcome["observed_value"], "CLKINV")
        self.assertTrue(outcome["passed"])
        self.assertEqual(measurement["decision"], "PASS")
        self.assertEqual(measurement["totals"]["holdout"]["tp"], 1)
        self.assertEqual(measurement["address_problems"], [])


if __name__ == "__main__":
    unittest.main()
