"""The read-side analyses must FAIL when the evidence chain is wrong, not just pass today.

W1 and W2 make two kinds of claim that are only worth what their enforcement is worth: "these
are the pinned inputs" and "this is the whole population". A tool that reports either from a
hand-written constant, or from a scan that silently absorbs whatever it finds, produces the
right number today and a wrong one the first time the tree moves.

The suite is negative-first: each adversarial check breaks exactly one link — a drifted digest,
a missing input, an unpinned import, a population with one record too many or too few, a forged
landing flag, a fault that is not code 8, a driver whose no-op writes something else — and
requires a refusal. A small set of positive baselines proves that the real frozen tree reaches
the gates those adversarial cases exercise. The derived positive results live in
`evidence/read_side_facts_2026_08_20/`; these are the reasons to believe them.
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import analyse_read_side_facts as w1  # noqa: E402
import audit_readback_evidence as w2  # noqa: E402
import read_side_evidence as rse  # noqa: E402


def build_root(tmp: Path) -> Path:
    """A tree that hashes identically to the repo: symlinks, so a test can replace one file."""
    root = tmp / "root"
    for relative in rse.PINNED:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(REPO_ROOT / relative)
    return root


def rewrite(root: Path, relative: str, document) -> None:
    """Replace one file, breaking the symlink so the original is untouched."""
    path = root / relative
    path.unlink()
    path.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")


def repin(root: Path, relative: str) -> None:
    """Re-pin a file a test has deliberately rewritten, so a LATER check is what fails."""
    rse.PINNED[relative] = rse.sha256_of(root / relative)


class PinnedInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = dict(rse.PINNED)
        self.addCleanup(lambda: (rse.PINNED.clear(), rse.PINNED.update(self.original)))

    def test_a_drifted_pinned_input_refuses(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            manifest = rse.load(root, f"{rse.RUN_DIR}/phenotype_manifest.json")
            manifest["frames"][0]["role"] = "not what it was"
            rewrite(root, f"{rse.RUN_DIR}/phenotype_manifest.json", manifest)
            with self.assertRaises(rse.DerivationStop) as stop:
                rse.checked_inputs(root)
            self.assertIn("phenotype_manifest.json", str(stop.exception))
            self.assertIn("!= pinned", str(stop.exception))

    def test_a_missing_pinned_input_refuses(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            (root / rse.KNOWN_ANSWER).unlink()
            with self.assertRaises(rse.DerivationStop) as stop:
                rse.checked_inputs(root)
            self.assertIn("missing", str(stop.exception))

    def test_an_unpinned_loaded_module_refuses(self) -> None:
        """Rule 3: importing a repo module without pinning it is a refusal, not a shrug."""
        unpinned = "scripts/icap_sequence.py"
        self.assertNotIn(unpinned, rse.PINNED, "pick a module this deliverable does not pin")
        fake = types.ModuleType("pretend_unpinned_import")
        fake.__file__ = str(REPO_ROOT / unpinned)
        sys.modules["pretend_unpinned_import"] = fake
        self.addCleanup(sys.modules.pop, "pretend_unpinned_import", None)
        with self.assertRaises(rse.DerivationStop) as stop:
            rse.checked_inputs(REPO_ROOT)
        self.assertIn(unpinned, str(stop.exception))

    def test_the_deliverables_own_files_are_the_only_exemption(self) -> None:
        for relative in rse.SELF:
            self.assertTrue((REPO_ROOT / relative).exists(), relative)
            self.assertNotIn(relative, rse.PINNED, "a file cannot pin itself")
        self.assertEqual(len(rse.SELF), 3)


class PopulationTests(unittest.TestCase):
    def test_discovery_equals_the_freeze_in_the_real_tree(self) -> None:
        discovered = rse.discover_engine_records(REPO_ROOT)
        self.assertEqual(sorted(discovered), sorted(rse.ENGINE_RECORDS))

    def test_one_record_too_many_refuses(self) -> None:
        extra = list(rse.ENGINE_RECORDS) + ["evidence/somewhere/new_record.json"]
        with self.assertRaises(rse.DerivationStop) as stop:
            rse.check_population(extra, rse.ENGINE_RECORDS, "engine record")
        self.assertIn("new_record.json", str(stop.exception))

    def test_one_record_too_few_refuses(self) -> None:
        short = list(rse.ENGINE_RECORDS)[:-1]
        with self.assertRaises(rse.DerivationStop) as stop:
            rse.check_population(short, rse.ENGINE_RECORDS, "engine record")
        self.assertIn(rse.ENGINE_RECORDS[-1], str(stop.exception))

    def test_the_staging_discovery_equals_the_freeze_in_the_real_tree(self) -> None:
        discovered = rse.discover_staging_copies(REPO_ROOT)
        self.assertEqual(sorted(discovered), sorted(rse.STAGING))

    def test_one_staging_copy_too_many_refuses(self) -> None:
        extra = list(rse.STAGING) + ["evidence/somewhere/ddr_slot0.json"]
        with self.assertRaises(rse.DerivationStop) as stop:
            rse.check_population(extra, tuple(rse.STAGING), "staging copy")
        self.assertIn("somewhere/ddr_slot0.json", str(stop.exception))

    def test_one_staging_copy_too_few_refuses(self) -> None:
        short = list(rse.STAGING)[:-1]
        with self.assertRaises(rse.DerivationStop) as stop:
            rse.check_population(short, tuple(rse.STAGING), "staging copy")
        self.assertIn(list(rse.STAGING)[-1], str(stop.exception))

    def test_an_unlisted_staging_copy_on_disk_would_be_caught(self) -> None:
        """The scan is shape-based, so a new naming convention cannot slip past either.

        `stage_dump_2.json` DID slip past the 1.0.1 inventory, which is why this exists.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            stray = root / "evidence/pretend_run/some_other_name.json"
            stray.parent.mkdir(parents=True, exist_ok=True)
            stray.write_text(json.dumps({"words": ["0x00000000"] * rse.FRAME_WORDS}))
            discovered = rse.discover_staging_copies(root)
            self.assertIn("evidence/pretend_run/some_other_name.json", discovered)
            with self.assertRaises(rse.DerivationStop):
                rse.check_population(discovered, tuple(rse.STAGING), "staging copy")

    def test_a_jtag_capture_is_not_mistaken_for_a_staging_copy(self) -> None:
        """JTAG captures carry their words under frames[far]; they are the other path."""
        discovered = rse.discover_staging_copies(REPO_ROOT)
        self.assertEqual([p for p in discovered if "far_" in p], [])

    def test_a_new_engine_record_would_be_caught(self) -> None:
        """The scan is real: a seventh record on disk breaks the closed population."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            seventh = root / "evidence/pretend_run/record.json"
            seventh.parent.mkdir(parents=True, exist_ok=True)
            seventh.write_text(json.dumps({"round": {"steps": [
                {"step": "no_op", "state": "passed",
                 "result": {"transaction": {"readback_frames": {"4196896": [0] * 101}}}}]}}))
            discovered = rse.discover_engine_records(root)
            with self.assertRaises(rse.DerivationStop):
                rse.check_population(discovered, rse.ENGINE_RECORDS, "engine record")


class StagingExpectationTests(unittest.TestCase):
    """What a correct readback owed is per instance, and blank-expecting-blank must not be
    filed with the three that owed the candidate."""

    def test_every_staging_entry_declares_what_was_owed(self) -> None:
        for relative, meta in rse.STAGING.items():
            self.assertIn(meta["expected"], ("candidate", "base", "none"), relative)

    def test_the_read_side_copy_owed_the_base_not_the_candidate(self) -> None:
        meta = rse.STAGING["evidence/read_side_divergence_2026_08_20/ddr_slot0.json"]
        self.assertEqual(meta["expected"], "base")
        self.assertIsNone(meta["landing_source"], "it is not a landing observation")

    def test_the_three_candidate_fault_copies_still_owe_the_candidate(self) -> None:
        owed = [r for r, m in rse.STAGING.items() if m["expected"] == "candidate"]
        self.assertEqual(sorted(owed), sorted([
            "evidence/known_answer_2026_08_14_erratum006/ddr_slot0.json",
            "evidence/location_reproduction_2026_08_20/fault/ddr_slot0_shutdown_read.json",
            "evidence/location_sweep_2026_08_20/fault/ddr_slot0_shutdown_read.json"]))

    def test_the_audit_no_longer_generalises_about_all_staging(self) -> None:
        source = (REPO_ROOT / "scripts/audit_readback_evidence.py").read_text("utf-8")
        self.assertNotIn("Every staging copy below was taken AFTER", source)
        self.assertNotIn("every blank one was expected to be blank", source)


class LandingTests(unittest.TestCase):
    """`landing_verified` must be derived from the instance, and breakable."""

    def setUp(self) -> None:
        self.original = dict(rse.PINNED)
        self.addCleanup(lambda: (rse.PINNED.clear(), rse.PINNED.update(self.original)))
        manifest = rse.load(REPO_ROOT, f"{rse.RUN_DIR}/phenotype_manifest.json")
        local_map = rse.load(REPO_ROOT, f"{rse.RUN_DIR}/local_map.json")
        report = rse.load(REPO_ROOT, rse.REPORT)
        import analyse_ddr_capture as add
        candidate, _, _ = add.derive_candidate(manifest, local_map, report)
        self.candidate = candidate[rse.INTENDED_FAR]
        self.device = rse.device_frames(REPO_ROOT)

    def test_the_real_instances_verify(self) -> None:
        for run in rse.LOCATION_RUNS:
            landing = rse.verify_landing(REPO_ROOT, run, self.candidate, self.device)
            self.assertTrue(landing["landing_verified"], run)
            self.assertEqual(landing["words_matching_candidate"], "101/101")
            self.assertEqual(landing["controls_exact"], rse.POSITIVE_CONTROLS)
            self.assertEqual(
                landing["controls_vs_bitstream"]["exact_against_the_bitstream"],
                rse.POSITIVE_CONTROLS)

    def test_a_broken_plmark_chain_fails_the_landing(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            relative = f"{rse.LOCATION_RUNS['run2']}/step4_sweep/index.json"
            index = rse.load(root, relative)
            index["plmark_at_start"] = "0000000000000000"
            rewrite(root, relative, index)
            landing = rse.verify_landing(root, "run2", self.candidate, self.device)
            self.assertFalse(landing["landing_verified"])
            self.assertFalse(
                landing["checks"]["one_plmark_across_fault_staging_and_acquisition"])

    def test_four_missing_plmarks_do_not_form_a_valid_chain(self) -> None:
        """Four equal nulls are absence of evidence, not evidence of one boot."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            run_dir = rse.LOCATION_RUNS["run1"]

            fault_relative = f"{run_dir}/fault/record.json"
            fault = rse.load(root, fault_relative)
            fault["same_boot"]["expected_plmark"] = None
            rewrite(root, fault_relative, fault)

            staging_relative = f"{run_dir}/fault/ddr_slot0_shutdown_read.json"
            staging = rse.load(root, staging_relative)
            staging["plmark"] = None
            rewrite(root, staging_relative, staging)

            index_relative = f"{run_dir}/step4_sweep/index.json"
            index = rse.load(root, index_relative)
            index["plmark_at_start"] = None
            index["plmark_at_end"] = None
            rewrite(root, index_relative, index)

            landing = rse.verify_landing(root, "run1", self.candidate, self.device)
            self.assertFalse(landing["landing_verified"])
            self.assertFalse(landing["checks"]["four_plmarks_present_and_well_formed"])
            self.assertFalse(
                landing["checks"]["one_plmark_across_fault_staging_and_acquisition"])

    def test_a_missing_positive_control_fails_the_landing(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            relative = f"{rse.LOCATION_RUNS['run1']}/step4_sweep/verdict.json"
            verdict = rse.load(root, relative)
            verdict["positive_controls"] = verdict["positive_controls"][:-1]
            rewrite(root, relative, verdict)
            landing = rse.verify_landing(root, "run1", self.candidate, self.device)
            self.assertFalse(landing["landing_verified"])
            self.assertFalse(landing["checks"]["sixteen_controls_exact"])

    def test_one_exact_control_repeated_sixteen_times_fails_the_landing(self) -> None:
        """A count of exact rows cannot substitute for the frozen sixteen-FAR sequence."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            relative = f"{rse.LOCATION_RUNS['run1']}/step4_sweep/verdict.json"
            verdict = rse.load(root, relative)
            verdict["positive_controls"] = [verdict["positive_controls"][0]] * \
                rse.POSITIVE_CONTROLS
            rewrite(root, relative, verdict)

            landing = rse.verify_landing(root, "run1", self.candidate, self.device)
            self.assertFalse(landing["landing_verified"])
            self.assertTrue(landing["checks"]["sixteen_controls_exact"])
            self.assertFalse(
                landing["checks"]["verdict_control_fars_match_declared_sequence"])

    def test_a_control_whose_digests_agree_but_not_with_the_bitstream_fails(self) -> None:
        """`expected == observed` is the acquisition tool agreeing with itself, not a control."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            relative = f"{rse.LOCATION_RUNS['run1']}/step4_sweep/verdict.json"
            verdict = rse.load(root, relative)
            forged = "0" * 64
            verdict["positive_controls"][0]["expected_sha256"] = forged
            verdict["positive_controls"][0]["observed_sha256"] = forged
            rewrite(root, relative, verdict)

            landing = rse.verify_landing(root, "run1", self.candidate, self.device)
            self.assertFalse(landing["landing_verified"])
            self.assertTrue(landing["checks"]["sixteen_controls_exact"])
            self.assertFalse(
                landing["checks"]["controls_re_derived_from_the_carrier_bitstream"])
            self.assertEqual(
                landing["controls_vs_bitstream"]["exact_against_the_bitstream"], 15)

    def test_a_forged_control_capture_is_caught_by_the_bitstream(self) -> None:
        """Every digest re-stated, verdict included — only carrier.bit can still tell."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            run_dir = rse.LOCATION_RUNS["run1"]
            far_key = rse.load(root, f"{run_dir}/step4_sweep/index.json")[
                "positive_control_fars"][0]
            far = int(far_key, 16)
            relative = f"{run_dir}/step4_sweep/far_{far:08x}.json"

            capture = rse.load(root, relative)
            node = capture["frames"][far_key]
            node["frame"][7] = "0000dead"
            node["all_words"][rse.FRAME_WORDS + 7] = "0000dead"
            forged = rse.frame_sha(rse.as_words(node["frame"]))
            node["frame_sha256"] = forged
            rewrite(root, relative, capture)

            index = rse.load(root, f"{run_dir}/step4_sweep/index.json")
            entry = index["entries"][far_key]
            entry["capture_sha256"] = rse.sha256_of(root / relative)
            entry["frame_sha256"] = forged
            rewrite(root, f"{run_dir}/step4_sweep/index.json", index)

            verdict_relative = f"{run_dir}/step4_sweep/verdict.json"
            verdict = rse.load(root, verdict_relative)
            for control in verdict["positive_controls"]:
                if str(control["far"]).lower() == far_key:
                    control["expected_sha256"] = forged
                    control["observed_sha256"] = forged
            rewrite(root, verdict_relative, verdict)

            landing = rse.verify_landing(root, "run1", self.candidate, self.device)
            self.assertFalse(landing["landing_verified"])
            self.assertTrue(landing["checks"]["sixteen_controls_exact"])
            self.assertFalse(
                landing["checks"]["controls_re_derived_from_the_carrier_bitstream"])
            bad = [d for d in landing["controls_vs_bitstream"]["detail"]
                   if not d["equals_the_bitstream"]]
            self.assertEqual([d["far"] for d in bad], [far_key])

    def test_a_capture_that_disagrees_with_its_own_digest_refuses(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            run_dir = rse.LOCATION_RUNS["run2"]
            relative = f"{run_dir}/step4_sweep/far_{rse.INTENDED_FAR:08x}.json"
            capture = rse.load(root, relative)
            node = capture["frames"][f"0x{rse.INTENDED_FAR:08x}"]
            node["frame"][51] = "0000dead"
            node["all_words"][rse.FRAME_WORDS + 51] = "0000dead"
            rewrite(root, relative, capture)
            index = rse.load(root, f"{run_dir}/step4_sweep/index.json")
            index["entries"][f"0x{rse.INTENDED_FAR:08x}"]["capture_sha256"] = \
                rse.sha256_of(root / relative)
            rewrite(root, f"{run_dir}/step4_sweep/index.json", index)
            with self.assertRaises(rse.DerivationStop) as stop:
                rse.verify_landing(root, "run2", self.candidate, self.device)
            self.assertIn("hashes to", str(stop.exception))

    def test_a_forged_capture_with_consistent_digests_still_fails_the_landing(self) -> None:
        """The strong case: every digest re-stated, so only the WORDS can give it away."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            run_dir = rse.LOCATION_RUNS["run2"]
            relative = f"{run_dir}/step4_sweep/far_{rse.INTENDED_FAR:08x}.json"
            capture = rse.load(root, relative)
            node = capture["frames"][f"0x{rse.INTENDED_FAR:08x}"]
            node["frame"][51] = "0000dead"
            node["all_words"][rse.FRAME_WORDS + 51] = "0000dead"
            forged = rse.frame_sha(rse.as_words(node["frame"]))
            node["frame_sha256"] = forged
            rewrite(root, relative, capture)
            index = rse.load(root, f"{run_dir}/step4_sweep/index.json")
            entry = index["entries"][f"0x{rse.INTENDED_FAR:08x}"]
            entry["capture_sha256"] = rse.sha256_of(root / relative)
            entry["frame_sha256"] = forged
            rewrite(root, f"{run_dir}/step4_sweep/index.json", index)
            landing = rse.verify_landing(root, "run2", self.candidate, self.device)
            self.assertFalse(landing["landing_verified"])
            self.assertFalse(landing["checks"]["capture_equals_candidate_word_for_word"])
            self.assertEqual(landing["words_matching_candidate"], "100/101")


class FaultCodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.o5 = rse.load(REPO_ROOT, "evidence/known_answer_2026_08_14_erratum006/record.json")

    def test_the_real_records_give_code_eight(self) -> None:
        fact = w1.fact_f5(REPO_ROOT, self.o5)
        self.assertEqual(fact["fault_code"], 8)
        self.assertEqual(fact["fault_code_name"], "readback")
        for run in fact["runs"].values():
            self.assertEqual(run["last_fault_word"], "0x00000008")

    def test_a_fault_word_that_is_not_eight_refuses(self) -> None:
        """Both runs moved together, so the "they disagree" guard cannot be what fires."""
        import tempfile
        import board_uboot_axi as axi
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            want = f"md.l 0x{axi.FAULT:08x} 0x1"
            changed = 0
            for run_dir in rse.LOCATION_RUNS.values():
                relative = f"{run_dir}/fault/record.json"
                record = rse.load(root, relative)
                for command in record["instrumentation"]["commands"]:
                    if command.get("command", "").lower() == want:
                        command["raw"] = command["raw"].replace("00000008", "0000000c")
                        changed += 1
                rewrite(root, relative, record)
            self.assertGreater(changed, 0, "no FAULT read to mutate")
            with self.assertRaises(rse.DerivationStop) as stop:
                w1.fact_f5(root, self.o5)
            self.assertIn("code 12", str(stop.exception))
            self.assertIn("rbsync", str(stop.exception))

    def test_two_runs_that_disagree_refuse(self) -> None:
        import tempfile
        import board_uboot_axi as axi
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            relative = f"{rse.LOCATION_RUNS['run1']}/fault/record.json"
            record = rse.load(root, relative)
            want = f"md.l 0x{axi.STATUS:08x} 0x1"
            for command in record["instrumentation"]["commands"]:
                if command.get("command", "").lower() == want:
                    command["raw"] = command["raw"].replace("04040082", "04040086")
            rewrite(root, relative, record)
            with self.assertRaises(rse.DerivationStop) as stop:
                w1.fact_f5(root, self.o5)
            self.assertIn("disagree", str(stop.exception))


class DriverTests(unittest.TestCase):
    """F2 reads the driver's AST. A driver that changed must not be reported as unchanged."""

    def _driver(self, tmp: Path, body: str) -> Path:
        root = tmp / "root"
        path = root / rse.DRIVER
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return root

    def test_the_real_driver_writes_restore(self) -> None:
        payload = w1.no_op_payload(REPO_ROOT)
        self.assertEqual(payload["writes"], "restore")

    def test_a_driver_whose_no_op_writes_something_else_is_reported(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._driver(Path(tmp), 'step("no_op", lambda: _write("candidate", a, b))\n')
            self.assertEqual(w1.no_op_payload(root)["writes"], "candidate")

    def test_a_driver_with_two_write_sites_refuses(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._driver(Path(tmp), 'step("no_op", lambda: (_write("restore", a),'
                                           ' _write("candidate", a)))\n')
            with self.assertRaises(rse.DerivationStop) as stop:
                w1.no_op_payload(root)
            self.assertIn("found 2", str(stop.exception))

    def test_a_driver_with_no_no_op_step_refuses(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._driver(Path(tmp), 'step("candidate", lambda: _write("candidate", a))\n')
            with self.assertRaises(rse.DerivationStop):
                w1.no_op_payload(root)

    def test_a_drifted_driver_is_caught_by_the_pin(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            path = root / rse.DRIVER
            path.unlink()
            path.write_text('step("no_op", lambda: _write("candidate", a, b))\n')
            with self.assertRaises(rse.DerivationStop) as stop:
                rse.checked_inputs(root)
            self.assertIn(rse.DRIVER, str(stop.exception))


class VerdictWordingTests(unittest.TestCase):
    def test_the_verdict_is_scoped_to_the_frozen_inventory(self) -> None:
        """"EVER" would quantify over runs nobody recorded. The wording must not."""
        source = (REPO_ROOT / "scripts/audit_readback_evidence.py").read_text("utf-8")
        self.assertIn("NO_NONBLANK_READBACK_IN_THE_FROZEN_COMMITTED_INVENTORY", source)
        self.assertNotIn("NO_NONBLANK_READBACK_HAS_EVER_BEEN_RETURNED", source)


if __name__ == "__main__":
    unittest.main()
