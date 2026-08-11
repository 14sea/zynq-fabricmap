"""The three gates that decide a carrier run: the bundle loader, the two verdicts, and
publication.

Erratum 001 made bit invariance against one exact bitstream the safety authority, so these
gates are the authority now. They were written and exercised by hand; hand-running is not
coverage, and none of the negative controls survived the session that produced them.

Two kinds of case here, deliberately:

* **synthetic** — the bundle loader, the base gate and the publication gate never parse a
  bitstream, so their cases build small files and real Git repositories with real Git LFS.
  They run anywhere, including a cold `git archive` tree.
* **the real run** — the ECO differential has to parse actual frames, so those cases read
  `gate_runs/claimb_round1_carrier_2026_08_11_erratum002/`. In a tree where LFS content has not been
  pulled the artifacts are ~130-byte pointers, and the cases skip with that named reason
  rather than pretending to pass.

The mutations are the point. A gate that only ever sees good input has not been tested.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import carrier_run as cr  # noqa: E402
import gate_carrier_base as base_gate  # noqa: E402
import gate_init_eco as eco_gate  # noqa: E402
import gate_publish_carrier_run as publish  # noqa: E402

REAL_RUN = REPO_ROOT / "gate_runs/claimb_round1_carrier_2026_08_11_erratum002"
RULE = ("gate_runs/**/*.bit filter=lfs diff=lfs merge=lfs -text\n"
        "gate_runs/**/*.dcp filter=lfs diff=lfs merge=lfs -text\n")
RUN_ROOT = "gate_runs/run_fixture"

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


def head_blob_sha(rel: str) -> str:
    blob = subprocess.run(["git", "cat-file", "blob", f"HEAD:{rel}"],
                          cwd=REPO_ROOT, capture_output=True, check=True).stdout
    return hashlib.sha256(blob).hexdigest()


def kinds_of(names) -> dict:
    return {n: {"lfs": n.endswith((".bit", ".dcp"))} for n in names}


class BundleFixture(unittest.TestCase):
    """A run directory with a self-consistent bundle over small synthetic files."""

    ARTIFACTS = ("carrier.bit", "carrier_eco.bit", "post_route.dcp",
                 "local_map.json", "phenotype_manifest.json",
                 "carrier_build.json", "carrier_eco.json", "isolation.txt")

    def run_dir(self) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name) / "run"
        root.mkdir(parents=True)
        payloads = {name: f"synthetic {name}\n".encode() * 3 for name in self.ARTIFACTS}

        payloads["carrier_build.json"] = (json.dumps({
            "schema": "carrier_build", "routed": True, "cell_isolation": "passed",
            "part": "xc7z010clg400-1", "bitstream": "carrier.bit",
            "bitstream_sha256": digest(payloads["carrier.bit"]),
            "post_route_dcp_sha256": digest(payloads["post_route.dcp"]),
            "isolation_evidence_sha256": digest(payloads["isolation.txt"]),
            "source_commit": "0" * 40,
            "source_tree": "clean",
            # a real tracked path at its real HEAD hash, so the good case passes for the
            # right reason rather than because the check was skipped
            "sources": {"vivado/carrier/carrier_crc32.v": head_blob_sha(
                "vivado/carrier/carrier_crc32.v")},
        }, indent=2) + "\n").encode()
        payloads["carrier_eco.json"] = (json.dumps({
            "schema": "carrier_eco", "cell": "evolvable_0", "loc": "SLICE_X2Y25",
            "bel": "SLICEL.A6LUT", "reimplemented": False, "bitstream": "carrier_eco.bit",
            "init_before": "64'h0000000000000000", "init_after": "64'h0000000000000001",
            "bitstream_sha256": digest(payloads["carrier_eco.bit"]),
        }, indent=2) + "\n").encode()
        payloads["phenotype_manifest.json"] = (json.dumps({
            "schema": "phenotype_manifest",
            "base_bitstream": {"path": f"{RUN_ROOT}/carrier.bit",
                               "sha256": digest(payloads["carrier.bit"])},
            "local_map": {"path": f"{RUN_ROOT}/local_map.json",
                          "sha256": digest(payloads["local_map.json"])},
        }, indent=2) + "\n").encode()

        for name, payload in payloads.items():
            (root / name).write_bytes(payload)

        bundle = {
            "schema": "carrier_run", "schema_version": "1.0.0", "run_id": "run_fixture",
            "artifacts": {
                name: {"sha256": digest(payload), "bytes": len(payload),
                       "lfs": name.endswith((".bit", ".dcp"))}
                for name, payload in payloads.items()},
            "eco": {"cell": "evolvable_0", "loc": "SLICE_X2Y25", "bel": "SLICEL.A6LUT",
                    "map_lut_key": "CLBLL_L.SLICEL_X0.ALUT"},
        }
        (root / "carrier_run.json").write_text(json.dumps(bundle, indent=2) + "\n")
        return root

    def rewrite_bundle(self, root: Path, mutate) -> None:
        bundle = json.loads((root / "carrier_run.json").read_text())
        mutate(bundle)
        (root / "carrier_run.json").write_text(json.dumps(bundle, indent=2) + "\n")


class BundleLoaderTests(BundleFixture):
    def test_a_consistent_bundle_loads_clean(self) -> None:
        doc, problems = cr.load(self.run_dir())
        self.assertEqual(problems, [])
        self.assertEqual(len(cr.input_digests(doc)), len(self.ARTIFACTS))

    def test_a_directory_without_a_bundle_is_not_a_run(self) -> None:
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, empty)
        doc, problems = cr.load(empty)
        self.assertIsNone(doc)
        self.assertEqual([p["kind"] for p in problems], ["bundle"])

    def test_an_artifact_whose_bytes_changed_is_refused(self) -> None:
        root = self.run_dir()
        (root / "isolation.txt").write_bytes(b"edited after the bundle was written\n")
        _, problems = cr.load(root)
        self.assertTrue(any(p["kind"] == "artifact" and "isolation.txt" in p["message"]
                            for p in problems), problems)

    def test_a_missing_artifact_is_refused(self) -> None:
        root = self.run_dir()
        (root / "post_route.dcp").unlink()
        _, problems = cr.load(root)
        self.assertTrue(any("post_route.dcp" in p["message"] for p in problems), problems)

    def test_an_unpulled_lfs_pointer_is_reported_as_itself(self) -> None:
        """The confusing failure: in a fresh clone without `git lfs pull` the file is a
        pointer, and a bare digest mismatch sends the reader looking for corruption."""
        root = self.run_dir()
        (root / "carrier.bit").write_bytes(
            b"version https://git-lfs.github.com/spec/v1\n"
            b"oid sha256:" + b"0" * 64 + b"\nsize 2083863\n")
        _, problems = cr.load(root)
        self.assertTrue(any(p["kind"] == "lfs" for p in problems), problems)

    def test_the_loader_reports_every_problem_not_just_the_first(self) -> None:
        root = self.run_dir()
        (root / "isolation.txt").write_bytes(b"edited\n")
        (root / "local_map.json").write_bytes(b"{}\n")
        _, problems = cr.load(root)
        self.assertGreaterEqual(len(problems), 2, problems)


class CarrierBaseGateTests(BundleFixture):
    def test_a_good_run_is_accepted(self) -> None:
        problems, digests = base_gate.findings(self.run_dir())
        self.assertEqual(problems, [])
        self.assertEqual(len(digests), len(self.ARTIFACTS))

    def test_a_manifest_pointing_at_another_bitstream_is_refused(self) -> None:
        root = self.run_dir()
        manifest = json.loads((root / "phenotype_manifest.json").read_text())
        manifest["base_bitstream"]["sha256"] = "0" * 64
        payload = (json.dumps(manifest, indent=2) + "\n").encode()
        (root / "phenotype_manifest.json").write_bytes(payload)
        self.rewrite_bundle(root, lambda b: b["artifacts"]["phenotype_manifest.json"].update(
            {"sha256": digest(payload), "bytes": len(payload)}))
        problems, _ = base_gate.findings(root)
        self.assertTrue(any(p["kind"] == "binding" for p in problems), problems)

    def test_a_record_that_does_not_claim_a_routed_design_is_refused(self) -> None:
        root = self.run_dir()
        record = json.loads((root / "carrier_build.json").read_text())
        record["routed"] = False
        payload = (json.dumps(record, indent=2) + "\n").encode()
        (root / "carrier_build.json").write_bytes(payload)
        self.rewrite_bundle(root, lambda b: b["artifacts"]["carrier_build.json"].update(
            {"sha256": digest(payload), "bytes": len(payload)}))
        problems, _ = base_gate.findings(root)
        self.assertTrue(any(p["kind"] == "provenance" and "routed" in p["message"]
                            for p in problems), problems)

    def test_a_record_without_a_passing_isolation_verdict_is_refused(self) -> None:
        root = self.run_dir()
        record = json.loads((root / "carrier_build.json").read_text())
        record["cell_isolation"] = "not run"
        payload = (json.dumps(record, indent=2) + "\n").encode()
        (root / "carrier_build.json").write_bytes(payload)
        self.rewrite_bundle(root, lambda b: b["artifacts"]["carrier_build.json"].update(
            {"sha256": digest(payload), "bytes": len(payload)}))
        problems, _ = base_gate.findings(root)
        self.assertTrue(any(p["kind"] == "isolation" for p in problems), problems)

    def test_a_record_without_source_hashes_is_refused(self) -> None:
        """Output hashes alone cannot connect a bitstream to the RTL in history."""
        root = self.run_dir()
        record = json.loads((root / "carrier_build.json").read_text())
        record.pop("sources", None)
        payload = (json.dumps(record, indent=2) + "\n").encode()
        (root / "carrier_build.json").write_bytes(payload)
        self.rewrite_bundle(root, lambda b: b["artifacts"]["carrier_build.json"].update(
            {"sha256": digest(payload), "bytes": len(payload)}))
        problems, _ = base_gate.findings(root)
        self.assertTrue(any(p["kind"] == "sources" for p in problems), problems)

    def test_a_source_that_moved_since_the_build_is_refused(self) -> None:
        """The exact defect: RTL edited after a published build, benches verifying the new
        sources, and the bitstream a board would load still the pre-fix one."""
        root = self.run_dir()
        record = json.loads((root / "carrier_build.json").read_text())
        # a real tracked path, pinned to a hash it does not have
        record["source_tree"] = "clean"
        record["sources"] = {"vivado/carrier/carrier_stream.v": "0" * 64}
        payload = (json.dumps(record, indent=2) + "\n").encode()
        (root / "carrier_build.json").write_bytes(payload)
        self.rewrite_bundle(root, lambda b: b["artifacts"]["carrier_build.json"].update(
            {"sha256": digest(payload), "bytes": len(payload)}))
        problems, _ = base_gate.findings(root)
        self.assertTrue(any(p["kind"] == "sources" and "has changed since" in p["message"]
                            for p in problems), problems)

    def test_a_build_from_a_dirty_tree_is_refused(self) -> None:
        root = self.run_dir()
        record = json.loads((root / "carrier_build.json").read_text())
        record["source_tree"] = "DIRTY"
        record["sources"] = {"vivado/carrier/carrier_stream.v": "0" * 64}
        payload = (json.dumps(record, indent=2) + "\n").encode()
        (root / "carrier_build.json").write_bytes(payload)
        self.rewrite_bundle(root, lambda b: b["artifacts"]["carrier_build.json"].update(
            {"sha256": digest(payload), "bytes": len(payload)}))
        problems, _ = base_gate.findings(root)
        self.assertTrue(any("not clean" in p["message"] for p in problems), problems)

    def test_a_bundle_the_loader_rejects_stops_the_gate(self) -> None:
        root = self.run_dir()
        (root / "carrier.bit").write_bytes(b"different bytes\n")
        problems, _ = base_gate.findings(root)
        self.assertTrue(problems)


def real_run_or_skip(test: unittest.TestCase) -> Path:
    if not (REAL_RUN / "carrier_run.json").is_file():
        test.skipTest("the published carrier run is not in this tree")
    for name in ("carrier.bit", "carrier_eco.bit"):
        path = REAL_RUN / name
        if not path.is_file() or cr.looks_like_lfs_pointer(path):
            test.skipTest(f"{name} is an unpulled Git LFS pointer: run `git lfs pull`")
    return REAL_RUN


class InitEcoGateTests(unittest.TestCase):
    """These parse real frames, so they need the real artifacts."""

    def copy_run(self) -> Path:
        source = real_run_or_skip(self)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name) / "run"
        shutil.copytree(source, root)
        return root

    def judge(self, root: Path):
        bundle, problems = cr.load(root)
        if problems:
            return problems, {}
        eco_rec = json.loads((root / "carrier_eco.json").read_text())
        eco_rec["map_lut_key"] = bundle["eco"]["map_lut_key"]
        local_map = json.loads((root / "local_map.json").read_text())
        return eco_gate.findings(root / "carrier.bit", root / eco_rec["bitstream"],
                                 local_map, eco_rec)

    def repin(self, root: Path, name: str) -> None:
        payload = (root / name).read_bytes()
        bundle = json.loads((root / "carrier_run.json").read_text())
        bundle["artifacts"][name].update({"sha256": digest(payload), "bytes": len(payload)})
        (root / "carrier_run.json").write_text(json.dumps(bundle, indent=2) + "\n")

    def test_the_published_differential_is_accepted(self) -> None:
        problems, summary = self.judge(self.copy_run())
        self.assertEqual(problems, [], problems)
        self.assertEqual(summary["frames_differing"], summary["frames_predicted"])
        self.assertGreater(summary["bits_predicted"], 0)
        # not vacuous: it looked at the whole device, not just the write envelope
        self.assertGreater(summary["frames_total"], 5000)

    def test_a_bit_changed_in_an_unpredicted_frame_is_refused(self) -> None:
        import bitstream_frames as bf
        root = self.copy_run()
        path = root / "carrier_eco.bit"
        words, sync = bf.config_words(path)
        data = bytearray(path.read_bytes())
        data[sync + 4 * (len(words) // 2)] ^= 0x01
        path.write_bytes(bytes(data))
        self.repin(root, "carrier_eco.bit")
        problems, _ = self.judge(root)
        self.assertTrue(any(p["kind"] == "stray_frame" for p in problems), problems)

    def test_a_bit_changed_in_a_predicted_frame_at_an_unpredicted_address_is_refused(self) -> None:
        """The subtle one: inside a frame the map DOES predict, at an address it does not,
        with the ECC recomputed so only the address rule can catch it. A frame-level check
        would wave this through."""
        import struct

        import bitstream_frames as bf
        import frame_ecc as fe
        root = self.copy_run()
        path = root / "carrier_eco.bit"
        parsed = bf.parse_frames(path)
        far = int(json.loads((root / "phenotype_manifest.json").read_text())
                  ["write_envelope"]["envelopes"][0]["target_fars"][0], 16)
        original = list(parsed["frames"][far])
        patched = list(original)
        patched[10] ^= (1 << 3)          # word 10 is in no certified address
        patched = fe.update_ecc(patched)
        data = bytearray(path.read_bytes())
        needle = b"".join(struct.pack(">I", w) for w in original)
        at = bytes(data).find(needle)
        self.assertGreater(at, 0, "the frame is not in the stream verbatim")
        data[at:at + 404] = b"".join(struct.pack(">I", w) for w in patched)
        path.write_bytes(bytes(data))
        self.repin(root, "carrier_eco.bit")
        problems, _ = self.judge(root)
        self.assertTrue(any(p["kind"] == "stray_bit" for p in problems), problems)

    def test_a_wrong_lut_key_in_the_bundle_is_refused(self) -> None:
        root = self.copy_run()
        bundle = json.loads((root / "carrier_run.json").read_text())
        local_map = json.loads((root / "local_map.json").read_text())
        other = [k for k in local_map["index"]["by_lut"]
                 if k != bundle["eco"]["map_lut_key"]][0]
        bundle["eco"]["map_lut_key"] = other
        (root / "carrier_run.json").write_text(json.dumps(bundle, indent=2) + "\n")
        with self.assertRaises(ValueError):
            self.judge(root)

    def test_the_eco_record_must_name_the_eco_bitstream_in_this_run(self) -> None:
        """Checked in the gate, not only in the bundle builder: a chain that trusts the
        builder to have compared them has one link asserted rather than verified."""
        problems = eco_gate.eco_record_problems(
            {"bitstream_sha256": "0" * 64, "reimplemented": False},
            {"carrier_eco.bit": "a" * 64})
        self.assertTrue(any("declares a bitstream digest" in p["message"]
                            for p in problems), problems)

    def test_a_reimplemented_eco_is_refused(self) -> None:
        problems = eco_gate.eco_record_problems(
            {"bitstream_sha256": "a" * 64, "reimplemented": True},
            {"carrier_eco.bit": "a" * 64})
        self.assertTrue(any("reimplemented=false" in p["message"]
                            for p in problems), problems)

    def test_a_well_formed_eco_record_raises_nothing(self) -> None:
        """So the two refusals above are not passing on a record that could never pass."""
        self.assertEqual(eco_gate.eco_record_problems(
            {"bitstream_sha256": "a" * 64, "reimplemented": False},
            {"carrier_eco.bit": "a" * 64}), [])


class HeadAuthorityTests(unittest.TestCase):
    """`load()` proves the files agree with the bundle. Only this proves the bundle is the
    one HEAD published — a whole run copied outside any repository agrees with itself."""

    def repo_with_run(self) -> tuple[Path, str]:
        if subprocess.run(["git", "lfs", "version"], capture_output=True,
                          check=False).returncode != 0:
            self.skipTest("git-lfs is not installed")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        git(root, "init", "-q", "-b", "main")
        (root / ".gitattributes").write_text(RULE)
        git(root, "add", ".gitattributes")
        git(root, "commit", "-q", "-m", "policy")

        run = root / RUN_ROOT
        run.mkdir(parents=True)
        payloads = {"carrier.bit": b"synthetic bitstream\n" * 8,
                    "phenotype_manifest.json": b'{"schema": "phenotype_manifest"}\n'}
        for name, payload in payloads.items():
            (run / name).write_bytes(payload)
        bundle = {"schema": "carrier_run", "schema_version": "1.0.0", "run_id": "run_fixture",
                  "artifacts": {n: {"sha256": digest(p), "bytes": len(p),
                                    "lfs": n.endswith(".bit")}
                                for n, p in payloads.items()}}
        (run / "carrier_run.json").write_text(json.dumps(bundle, indent=2) + "\n")
        git(root, "add", RUN_ROOT)
        git(root, "commit", "-q", "-m", "publish the run")
        return root, RUN_ROOT

    def ask(self, root: Path, run_root: str) -> list[dict]:
        """The module's REPO_ROOT is this repository; point it at the fixture's."""
        import unittest.mock
        with unittest.mock.patch.object(cr, "REPO_ROOT", root):
            return cr.head_authority_problems(root / run_root)

    def test_a_published_run_carries_head_authority(self) -> None:
        root, run_root = self.repo_with_run()
        self.assertEqual(self.ask(root, run_root), [])

    def test_a_run_copied_outside_any_repository_is_refused(self) -> None:
        """The reviewer's reproduction: /tmp copy, no git at all, every digest agrees."""
        root, run_root = self.repo_with_run()
        loose = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, loose)
        shutil.copytree(root / run_root, loose / "run")
        import unittest.mock
        with unittest.mock.patch.object(cr, "REPO_ROOT", root):
            problems = cr.head_authority_problems(loose / "run")
        self.assertTrue(problems, "a directory outside any repository was accepted")

    def test_an_artifact_edited_after_publication_is_refused(self) -> None:
        root, run_root = self.repo_with_run()
        (root / run_root / "phenotype_manifest.json").write_text('{"schema": "edited"}\n')
        self.assertTrue(self.ask(root, run_root))

    def test_a_staged_change_to_a_tracked_file_is_refused(self) -> None:
        """Staging is not a way to answer "is anything different from what is published".
        `git diff` compares the working tree against the INDEX, so editing a gate and then
        `git add`-ing it left it empty and the verdict was accepted."""
        root, run_root = self.repo_with_run()
        (root / ".gitattributes").write_text(RULE + "# edited\n")
        git(root, "add", ".gitattributes")
        self.assertEqual(git(root, "diff", "--name-only").stdout.strip(), "",
                         "the fixture must reproduce the empty `git diff`")
        problems = self.ask(root, run_root)
        self.assertTrue(any("differ from HEAD" in p["message"] for p in problems), problems)

    def test_an_unstaged_change_to_any_tracked_file_is_refused(self) -> None:
        """Including the gates: a verdict from an edited working copy describes nothing
        anyone can review."""
        root, run_root = self.repo_with_run()
        (root / ".gitattributes").write_text(RULE + "# edited\n")
        problems = self.ask(root, run_root)
        self.assertTrue(any("differ from HEAD" in p["message"] for p in problems), problems)

    def test_neither_cli_offers_a_repo_override(self) -> None:
        """Asked of the parser, not of the source text: an earlier version grepped for the
        string and failed on the comment that explains why the option does not exist."""
        for script in ("gate_carrier_base.py", "gate_init_eco.py"):
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / script),
                 "--run-dir", str(REAL_RUN), "--repo", "/tmp"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, script)
            self.assertIn("unrecognized arguments", result.stderr, script)
            self.assertIn("head_authority_problems",
                          (REPO_ROOT / "scripts" / script).read_text(), script)


class PublishGateTests(unittest.TestCase):
    """Real repositories with real Git LFS, offline: `git add` runs the clean filter
    locally, so genuine pointers and genuine ordinary blobs both exist without a remote."""

    def staged(self, *, rule: str = RULE, add: list[str] | None = None) -> Path:
        if subprocess.run(["git", "lfs", "version"], capture_output=True,
                          check=False).returncode != 0:
            self.skipTest("git-lfs is not installed: the index gate cannot be answered")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        git(root, "init", "-q", "-b", "main")
        (root / ".gitattributes").write_text(rule)
        git(root, "add", ".gitattributes")
        git(root, "commit", "-q", "-m", "policy first, and alone")

        run = root / RUN_ROOT
        run.mkdir(parents=True)
        payloads = {
            "carrier.bit": b"synthetic carrier bitstream\n" * 8,
            "post_route.dcp": b"synthetic checkpoint\n" * 8,
            "phenotype_manifest.json": b'{"schema": "phenotype_manifest"}\n',
        }
        for name, payload in payloads.items():
            (run / name).write_bytes(payload)
        bundle = {
            "schema": "carrier_run", "schema_version": "1.0.0", "run_id": "run_fixture",
            "artifacts": {
                name: {"sha256": digest(payload), "bytes": len(payload),
                       "lfs": name.endswith((".bit", ".dcp"))}
                for name, payload in payloads.items()}}
        (run / "carrier_run.json").write_text(json.dumps(bundle, indent=2) + "\n")
        git(root, *(add or ["add", RUN_ROOT]))
        return root

    def bundle_of(self, root: Path) -> dict:
        return json.loads((root / RUN_ROOT / "carrier_run.json").read_text())

    def rewrite_bundle(self, root: Path, bundle: dict) -> None:
        (root / RUN_ROOT / "carrier_run.json").write_text(json.dumps(bundle, indent=2) + "\n")
        git(root, "add", f"{RUN_ROOT}/carrier_run.json")

    def test_a_correctly_added_run_is_publishable(self) -> None:
        self.assertEqual(publish.publication_problems(RUN_ROOT, self.staged()), [])

    def test_adding_with_the_filter_overridden_is_refused(self) -> None:
        root = self.staged(add=[*BYPASS, "add", RUN_ROOT])
        problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any("carrier.bit" in p and "filter did not run" in p
                            for p in problems), problems)

    def test_a_rule_disabled_between_staging_and_adding_is_refused(self) -> None:
        root = self.staged(add=["status"])
        (root / ".gitattributes").write_text(RULE + "gate_runs/**/*.bit -filter\n")
        git(root, "add", RUN_ROOT)
        problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(problems)

    def test_staging_the_policy_alongside_the_artifacts_is_refused(self) -> None:
        root = self.staged()
        (root / ".gitattributes").write_text(RULE + "# a late edit\n")
        git(root, "add", ".gitattributes")
        problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any(".gitattributes" in p for p in problems), problems)

    def test_a_pinned_artifact_that_is_not_staged_is_refused(self) -> None:
        root = self.staged()
        git(root, "rm", "-q", "--cached", f"{RUN_ROOT}/post_route.dcp")
        problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any("post_route.dcp" in p and "not staged" in p
                            for p in problems), problems)

    def test_a_file_the_bundle_does_not_pin_is_refused(self) -> None:
        root = self.staged()
        (root / RUN_ROOT / "extra_notes.json").write_text("{}\n")
        git(root, "add", f"{RUN_ROOT}/extra_notes.json")
        problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any("extra_notes.json" in p for p in problems), problems)

    def test_an_ordinary_blob_edited_without_repinning_is_refused(self) -> None:
        root = self.staged()
        (root / RUN_ROOT / "phenotype_manifest.json").write_text('{"schema": "edited"}\n')
        git(root, "add", f"{RUN_ROOT}/phenotype_manifest.json")
        problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any("phenotype_manifest.json" in p and "hash to" in p
                            for p in problems), problems)

    def test_a_pointer_whose_oid_is_not_the_pin_is_refused(self) -> None:
        """The bytes behind the pointer are what the bundle vouches for. Restaging a
        different bitstream leaves a valid pointer with the wrong oid."""
        root = self.staged()
        (root / RUN_ROOT / "carrier.bit").write_bytes(b"a different bitstream\n" * 8)
        git(root, "add", f"{RUN_ROOT}/carrier.bit")
        problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any("carrier.bit" in p and "oid" in p for p in problems), problems)

    def test_an_ordinary_file_turned_into_a_pointer_is_refused(self) -> None:
        """Manifests must stay readable and diffable; a pointer is neither."""
        root = self.staged()
        bundle = self.bundle_of(root)
        pointer = (b"version https://git-lfs.github.com/spec/v1\noid sha256:"
                   + b"1" * 64 + b"\nsize 31\n")
        (root / RUN_ROOT / "phenotype_manifest.json").write_bytes(pointer)
        bundle["artifacts"]["phenotype_manifest.json"].update(
            {"sha256": digest(pointer), "bytes": len(pointer)})
        self.rewrite_bundle(root, bundle)
        git(root, "add", f"{RUN_ROOT}/phenotype_manifest.json")
        problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any("ordinary Git file" in p for p in problems), problems)

    def test_a_change_set_that_carries_the_gates_is_refused(self) -> None:
        """The defect a reviewer reproduced on the real commit: artifacts, builder, both
        production gates, this gate and its tests staged together, and PUBLISHABLE — the
        commit was judging itself."""
        root = self.staged()
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "scripts/gate_publish_carrier_run.py").write_text("# an edited judge\n")
        git(root, "add", "scripts/gate_publish_carrier_run.py")
        problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any("outside" in p and "own judge" in p for p in problems), problems)

    def test_an_unstaged_modification_to_a_tracked_file_is_refused(self) -> None:
        root = self.staged()
        (root / ".gitattributes").write_text(RULE + "# edited but not staged\n")
        problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any("unstaged" in p for p in problems), problems)

    def test_a_run_without_a_bundle_is_refused(self) -> None:
        root = self.staged()
        git(root, "rm", "-q", "--cached", f"{RUN_ROOT}/carrier_run.json")
        problems = publish.publication_problems(RUN_ROOT, root)
        self.assertTrue(any("carrier_run.json" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
