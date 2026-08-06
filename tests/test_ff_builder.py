"""The formal `clb_ff_config` builder, checked without Vivado.

Split deliberately, per `docs/ff_builder_design.md` §10:

* **history-independent** tests run from a `git archive` of the tree, where `.git` does
  not exist. The only authority-B assertion possible there is that the builder *refuses
  to start* — which is a real assertion, not a skip;
* **authority-B** tests need history and are marked as such. A test that quietly skipped
  when history is missing would report green for the check that matters most.

Nothing here launches Vivado. The tiering of §5.3 is computed on the Python side from a
readback file precisely so it can be falsified at this level.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil  # noqa: F401  (kept for evidence-path tests)
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
BUILDER = REPO_ROOT / "scripts/gate_build_ff_formal.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import gate_build_ff_formal as builder  # noqa: E402


def has_history() -> bool:
    checked = subprocess.run(["git", "cat-file", "-e", f"{builder.PLAN_COMMIT}^{{commit}}"],
                             cwd=REPO_ROOT, capture_output=True, check=False)
    return checked.returncode == 0


def scratch() -> tempfile.TemporaryDirectory:
    (REPO_ROOT / "build").mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(dir=REPO_ROOT / "build")


class AuthorityTests(unittest.TestCase):
    """Authority A is readable anywhere; authority B needs git history."""

    def test_the_commitment_hash_and_counts_are_asserted_before_anything_is_built(self) -> None:
        source = BUILDER.read_text()
        self.assertIn(builder.COMMITTED_SHA256, source)
        plan = json.loads(builder.COMMITMENT.read_text())
        self.assertEqual(len(plan["specimens"]), 184)
        self.assertEqual(plan["totals"],
                         {"specimens": 184, "predictions": 176, "holdout_predictions": 154})

    def test_120_is_not_in_the_commitment_and_comes_from_the_variant_topology(self) -> None:
        # The defect that cost a review round: totals carry 184/176/154 and nothing else.
        plan = json.loads(builder.COMMITMENT.read_text())
        self.assertNotIn("node_type", json.dumps(plan["totals"]))
        for specimen in plan["specimens"]:
            self.assertNotIn("derived_from", specimen)
        impls = [s for s in plan["specimens"]
                 if builder.VARIANTS[s["variant"]]["kind"] == "impl"]
        self.assertEqual(len(impls), 120)
        self.assertEqual(len(plan["specimens"]) - len(impls), 64)

    def test_the_variant_table_matches_the_commitment_in_both_directions(self) -> None:
        plan = json.loads(builder.COMMITMENT.read_text())
        self.assertEqual(sorted({s["variant"] for s in plan["specimens"]}),
                         sorted(builder.VARIANTS))

    @unittest.skipUnless(has_history(), "requires git history — see the clone-only step")
    def test_authority_b_resolves_from_history_and_not_from_the_working_tree(self) -> None:
        import hashlib

        frozen = builder.frozen_plan_text()
        self.assertEqual(hashlib.sha256(frozen).hexdigest(), builder.PLAN_SHA256)
        current = (REPO_ROOT / builder.PLAN_PATH).read_bytes()
        self.assertNotEqual(hashlib.sha256(current).hexdigest(), builder.PLAN_SHA256,
                            "the working copy must NOT be the frozen text — that is the point")

    def test_the_builder_refuses_to_start_without_git_history(self) -> None:
        """History-independent: this is what the archive run asserts about authority B.

        The scratch directory has to be OUTSIDE the repository. A temporary directory
        under `build/` is still inside the working tree, so `git` walks up and finds the
        history anyway — the first version of this test passed for that reason and
        proved nothing.
        """
        with tempfile.TemporaryDirectory() as outside:
            fake = Path(outside) / "norepo"
            fake.mkdir()
            (fake / builder.PLAN_PATH).parent.mkdir(parents=True)
            # A working-tree copy is present and still must not be accepted.
            (fake / builder.PLAN_PATH).write_bytes(b"a plausible but unfrozen plan\n")
            original = builder.REPO
            builder.REPO = fake
            try:
                with self.assertRaises(SystemExit) as caught:
                    builder.frozen_plan_text()
            finally:
                builder.REPO = original
        message = str(caught.exception)
        self.assertIn("authority B unavailable", message)
        self.assertIn("a clone, not an archive", message)


class SiteMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = json.loads(builder.COMMITMENT.read_text())

    def test_the_mapping_comes_from_the_rule_and_has_24_distinct_sites(self) -> None:
        mapping = builder.check_site_mapping(self.plan)
        self.assertEqual(len(mapping), 8)
        sites = {s for trio in mapping.values() for s in trio.values()}
        self.assertEqual(len(sites), 24)

    def test_no_anchor_or_keeper_can_ever_be_a_target(self) -> None:
        mapping = builder.check_site_mapping(self.plan)
        targets = set(mapping)
        for trio in mapping.values():
            self.assertTrue(trio["anchor"].endswith("Y20"))
            self.assertTrue(trio["keeper"].endswith("Y20"))
            self.assertNotIn(trio["anchor"], targets)
            self.assertNotIn(trio["keeper"], targets)

    def test_the_lutram_keeper_rule_would_have_collided_at_every_instance(self) -> None:
        # Not a regression test for code — a record of why the rule changed. The eight
        # targets fill four tiles, so "the other slice of the target tile" is a target
        # for every instance, not only for SLICE_X9Y25.
        by_tile: dict[str, set[str]] = {}
        for specimen in self.plan["specimens"]:
            by_tile.setdefault(specimen["tile"], set()).add(specimen["site"])
        self.assertEqual(len(by_tile), 4)
        for sites in by_tile.values():
            self.assertEqual(len(sites), 2)

    def test_a_target_outside_row_25_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            builder.sites_for("SLICE_X2Y20")


class NetClassificationTests(unittest.TestCase):
    """The tier boundary of §5.3, which is where a wrong answer silently narrows a gate."""

    def readback(self, nets: list[tuple[str, str, list[str]]]) -> dict[str, str]:
        out = {"net_count": str(len(nets))}
        for n, (name, driver, sinks) in enumerate(nets):
            out[f"net.{n}.name"] = name
            out[f"net.{n}.driver"] = driver
            out[f"net.{n}.sinks"] = " ".join(sinks)
            out[f"net.{n}.route"] = "ROUTE"
            out[f"net.{n}.pips"] = "PIPS"
            out[f"net.{n}.route_status"] = "ROUTED"
        return out

    def test_a_net_wholly_inside_the_subgraph_is_dedicated(self) -> None:
        rb = self.readback([("w1", "anchor_lut1/O", ["anchor_lut2/I2"])])
        dedicated, shared = builder.classify_nets(rb)
        self.assertEqual(dedicated, {"w1"})
        self.assertEqual(shared, set())

    def test_an_output_buffer_fed_by_an_anchor_counts_as_inside(self) -> None:
        rb = self.readback([("anchor_o_OBUF", "anchor_ff/Q", ["anchor_o_OBUF_inst/I"])])
        dedicated, _ = builder.classify_nets(rb)
        self.assertEqual(dedicated, {"anchor_o_OBUF"})

    def test_a_net_that_also_reaches_the_target_is_shared(self) -> None:
        # This is the case that revision 2 got wrong: ce reaches anchor_lut2 AND the
        # target flip-flops, and ce_tied exists precisely to remove the target sinks.
        rb = self.readback([("ce_IBUF", "ce_IBUF_inst/O",
                             ["anchor_lut2/I0", "{g_store[0].g_used.g_s.s/CE}"])])
        dedicated, shared = builder.classify_nets(rb)
        self.assertEqual(dedicated, set())
        self.assertEqual(shared, {"ce_IBUF"})

    def test_a_dedicated_net_gaining_a_target_sink_stops_being_dedicated(self) -> None:
        clean = self.readback([("w2", "anchor_lut2/O", ["anchor_ff/D", "anchor_ff2/D"])])
        self.assertEqual(builder.classify_nets(clean)[0], {"w2"})
        leaked = self.readback([("w2", "anchor_lut2/O",
                                 ["anchor_ff/D", "{g_store[3].g_used.g_s.s/D}"])])
        self.assertEqual(builder.classify_nets(leaked)[0], set())

    def test_braced_pin_names_are_parsed(self) -> None:
        self.assertEqual(builder.cell_of("{g_store[0].g_used.g_s.s/D}"),
                         "g_store[0].g_used.g_s.s")
        self.assertEqual(builder.split_pins("{a b/C} d/E"), ["a b/C", "d/E"])


class PairComparisonTests(unittest.TestCase):
    """Tier 1 and 2 fail a pair; tier 3 never does. Both directions are tested."""

    def base_readback(self) -> dict[str, str]:
        rb = {
            "net_count": "2",
            "net.0.name": "w1", "net.0.driver": "anchor_lut1/O",
            "net.0.sinks": "anchor_lut2/I2", "net.0.route": "R1", "net.0.pips": "P1",
            "net.0.route_status": "ROUTED",
            "net.1.name": "ce_IBUF", "net.1.driver": "ce_IBUF_inst/O",
            "net.1.sinks": "anchor_lut2/I0 {g_store[0].g_used.g_s.s/CE}",
            "net.1.route": "R2", "net.1.pips": "P2", "net.1.route_status": "ROUTED",
        }
        for name in builder.AK_CELLS:
            rb[f"ak.{name}.ref"] = "LUT6"
            rb[f"ak.{name}.loc"] = "SLICE_X4Y20"
            rb[f"ak.{name}.bel"] = "SLICEM.A6LUT"
            rb[f"ak.{name}.init"] = "1'b0"
            rb[f"ak.{name}.lock_pins"] = "I0:A1"
            rb[f"ak.{name}.prop.IS_C_INVERTED"] = "0"
            rb[f"ak.{name}.pin.O.net"] = "w1"
        return rb

    def test_identical_ends_pass_with_no_diffs(self) -> None:
        a = self.base_readback()
        result = builder.compare_pair(a, dict(a))
        self.assertEqual(result["t1_diffs"], [])
        self.assertEqual(result["t2_diffs"], [])
        self.assertEqual(result["t3_diffs"], [])

    def test_a_moved_anchor_fails_tier_1(self) -> None:
        a = self.base_readback()
        b = self.base_readback()
        b["ak.anchor_ff.loc"] = "SLICE_X5Y20"
        result = builder.compare_pair(a, b)
        self.assertEqual([d["key"] for d in result["t1_diffs"]], ["ak.anchor_ff.loc"])

    def test_an_inversion_attribute_change_fails_tier_1(self) -> None:
        a = self.base_readback()
        b = self.base_readback()
        b["ak.anchor_ff2.prop.IS_C_INVERTED"] = "1"
        result = builder.compare_pair(a, b)
        self.assertTrue(result["t1_diffs"])

    def test_a_rerouted_dedicated_net_fails_tier_2(self) -> None:
        a = self.base_readback()
        b = self.base_readback()
        b["net.0.pips"] = "P1-DIFFERENT"
        result = builder.compare_pair(a, b)
        self.assertEqual([d["key"] for d in result["t2_diffs"]], ["w1.pips"])

    def test_a_shared_net_difference_is_reported_and_does_not_fail(self) -> None:
        # The revision-3 correction, as an executable statement: ce_tied legitimately
        # removes the target sink from a shared net, and that must not fail the pair.
        a = self.base_readback()
        b = self.base_readback()
        b["net.1.sinks"] = "anchor_lut2/I0"
        b["net.1.route"] = "R2-SHORTER"
        result = builder.compare_pair(a, b)
        self.assertEqual(result["t1_diffs"], [])
        self.assertEqual(result["t2_diffs"], [])
        self.assertEqual({d["net"] for d in result["t3_diffs"]}, {"ce_IBUF"})


class DerivedComparisonTests(unittest.TestCase):
    def test_only_the_one_init_may_change(self) -> None:
        base = {"store.0.init": "1'b1", "store.1.init": "1'b1", "ak.anchor_ff.loc": "X"}
        drv = dict(base, **{"store.0.init": "1'b0"})
        result = builder.compare_derived(base, drv, "AFF")
        self.assertEqual(len(result["expected_init_changes"]), 1)
        self.assertEqual(result["unexpected"], [])

    def test_a_second_difference_is_unexpected(self) -> None:
        base = {"store.0.init": "1'b1", "ak.anchor_ff.loc": "X"}
        drv = {"store.0.init": "1'b0", "ak.anchor_ff.loc": "Y"}
        result = builder.compare_derived(base, drv, "AFF")
        self.assertEqual([d["key"] for d in result["unexpected"]], ["ak.anchor_ff.loc"])


class StampAndLockTests(unittest.TestCase):
    def node(self, outdir: Path, **over) -> dict:
        node = {"specimen_id": "SLICE_X2Y25_base", "instance": "SLICE_X2Y25",
                "variant": "base", "node_type": "implementation", "kind": "impl",
                "sites": {"target": "SLICE_X2Y25", "keeper": "SLICE_X2Y20",
                          "anchor": "SLICE_X4Y20"},
                "outdir": outdir, "recipe": {"part": "xc7z010clg400-1"},
                "base_dcp_sha256": None}
        node.update(over)
        return node

    def populate(self, outdir: Path, node: dict, completed: bool = True,
                 **stamp_over) -> None:
        outdir.mkdir(parents=True, exist_ok=True)
        for name in builder.ARTIFACTS[node["node_type"]]:
            (outdir / name).write_text(name)
        stamp = {"node_type": node["node_type"], "instance": node["instance"],
                 "variant": node["variant"], "sites": node["sites"],
                 "recipe": node["recipe"], "completed": completed,
                 "artifacts": {name: builder.sha256_file(outdir / name)
                               for name in builder.ARTIFACTS[node["node_type"]]}}
        stamp.update(stamp_over)
        (outdir / "stamp.json").write_text(json.dumps(stamp))

    def test_a_matching_stamp_is_the_only_path_to_reuse(self) -> None:
        with scratch() as directory:
            outdir = Path(directory) / "n"
            node = self.node(outdir)
            self.populate(outdir, node)
            self.assertEqual(builder.cache_state(outdir, node)[0], "reuse")

    def test_every_tampering_case_refuses_and_names_its_reason(self) -> None:
        cases = {
            "no stamp": lambda o, n: (o / "stamp.json").unlink(),
            "another variant": lambda o, n: self.populate(o, n, variant="clkinv"),
            "another instance": lambda o, n: self.populate(o, n, instance="SLICE_X9Y25"),
            "different sites": lambda o, n: self.populate(
                o, n, sites={"target": "SLICE_X2Y25", "keeper": "SLICE_X9Y20",
                             "anchor": "SLICE_X4Y20"}),
            "different recipe": lambda o, n: self.populate(o, n, recipe={"part": "other"}),
            "artifact hash": lambda o, n: (o / "spec.bit").write_text("tampered"),
            "artifact deleted": lambda o, n: (o / "spec.bit").unlink(),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                with scratch() as directory:
                    outdir = Path(directory) / "n"
                    node = self.node(outdir)
                    self.populate(outdir, node)
                    mutate(outdir, node)
                    state, why = builder.cache_state(outdir, node)
                    self.assertEqual(state, "refuse", f"{label}: {why}")
                    self.assertTrue(why)

    def test_an_incomplete_stamp_is_failed_not_refused(self) -> None:
        with scratch() as directory:
            outdir = Path(directory) / "n"
            node = self.node(outdir)
            self.populate(outdir, node, completed=False)
            self.assertEqual(builder.cache_state(outdir, node)[0], "failed")

    def test_a_derived_node_pinned_to_another_base_refuses(self) -> None:
        with scratch() as directory:
            outdir = Path(directory) / "n"
            node = self.node(outdir, node_type="derived", kind="derived",
                             variant="zini_AFF", base_dcp_sha256="aa")
            self.populate(outdir, node, derived_from={"base_dcp_sha256": "bb"})
            state, why = builder.cache_state(outdir, node)
            self.assertEqual(state, "refuse", why)

    def test_report_only_cannot_bypass_verification(self) -> None:
        with scratch() as directory:
            outdir = Path(directory) / "n"
            node = self.node(outdir)
            self.populate(outdir, node)
            (outdir / "stamp.json").unlink()
            with self.assertRaises(SystemExit):
                builder.verified_state(outdir, node)

    def test_the_stamp_is_written_atomically_and_leaves_no_temporary(self) -> None:
        with scratch() as directory:
            outdir = Path(directory)
            builder.write_stamp(outdir, {"completed": True}, "attempt-1")
            self.assertTrue((outdir / "stamp.json").is_file())
            self.assertEqual([p for p in outdir.iterdir() if p.name.startswith(".stamp")], [])

    def test_a_second_builder_exits_instead_of_waiting_and_the_lock_is_not_auto_cleared(self) -> None:
        with scratch() as directory:
            root = Path(directory)
            with builder.RunLock(root, "first"):
                self.assertTrue((root / ".builder.lock").is_file())
                with self.assertRaises(SystemExit):
                    with builder.RunLock(root, "second"):
                        pass
                # still held: the failed acquisition must not have removed it
                self.assertTrue((root / ".builder.lock").is_file())
            self.assertFalse((root / ".builder.lock").is_file())


class EvidenceTests(unittest.TestCase):
    def test_an_existing_attempt_directory_is_never_overwritten(self) -> None:
        with scratch() as directory:
            root = Path(directory)
            outdir = root / "SLICE_X2Y25" / "base"
            outdir.mkdir(parents=True)
            (outdir / "run.out").write_text("first failure")
            node = {"instance": "SLICE_X2Y25", "variant": "base", "outdir": outdir}
            evidence = root / "evidence"
            moved = builder.archive_node(node, evidence, "attempt-1")
            self.assertTrue((moved / "run.out").is_file())
            self.assertFalse(outdir.exists())

            outdir.mkdir(parents=True)
            (outdir / "run.out").write_text("second failure")
            with self.assertRaises(SystemExit):
                builder.archive_node(node, evidence, "attempt-1")
            self.assertEqual((moved / "run.out").read_text(), "first failure")

    def test_a_retry_archives_before_rebuilding_rather_than_overwriting(self) -> None:
        source = BUILDER.read_text()
        self.assertIn("archive_node", source)
        self.assertIn("os.replace", source)


class ScopeDisciplineTests(unittest.TestCase):
    def test_the_builder_never_reads_the_predicted_bits(self) -> None:
        source = BUILDER.read_text()
        body = source.split('"""', 2)[2] if source.count('"""') >= 2 else source
        for forbidden in ("predicted_assignments", "expected_value", "expected_transition"):
            self.assertNotIn(forbidden, body,
                             "a builder that can see the expected bits can be tuned to them")

    def test_there_is_no_subset_flag_beyond_the_mine_instance(self) -> None:
        source = BUILDER.read_text()
        for forbidden in ("--only", "--features", "--continue-from"):
            self.assertNotIn(f'"{forbidden}"', source)

    def test_a_holdout_instance_is_refused_and_the_mine_site_is_accepted(self) -> None:
        # Tested through the pure scope function, not through a subprocess: `main` checks
        # authority B first, so from a `git archive` a subprocess would exit on the
        # missing history and this test would "pass" for the wrong reason.
        plan = json.loads(builder.COMMITMENT.read_text())
        mine = {s["site"] for s in plan["specimens"] if s["split"] == "mine"}
        self.assertEqual(mine, {"SLICE_X2Y25"})

        builder.check_instance_scope(plan, "SLICE_X2Y25")   # must not raise
        for holdout in sorted({s["site"] for s in plan["specimens"]} - mine):
            with self.subTest(holdout), self.assertRaises(SystemExit) as caught:
                builder.check_instance_scope(plan, holdout)
            self.assertIn("not mine", str(caught.exception))
        with self.assertRaises(SystemExit):
            builder.check_instance_scope(plan, "SLICE_X99Y25")


if __name__ == "__main__":
    unittest.main()


class MineDiagnosticTests(unittest.TestCase):
    """The mine-only bit-accounting diagnostic — `scripts/diag_measure_ff_mine.py`.

    It exists because §10's stop-on-FP condition is not evaluable by the smoke: FP,
    `ownership_unknown` and `unattributed` come from the measurement, and §7.6 forbids
    that on an incomplete run. What must be true of it is that it reuses the measurement
    core rather than reimplementing it, that it cannot be pointed at a holdout instance,
    and that nothing downstream can mistake it for a certificate.
    """

    DIAG = REPO_ROOT / "scripts/diag_measure_ff_mine.py"

    def test_it_reuses_the_measurement_core_and_defines_no_classifier_of_its_own(self) -> None:
        source = self.DIAG.read_text()
        for name in ("classify_diff", "raw_diff", "committed_pairs", "as_addresses"):
            self.assertIn(f"    {name},", source, f"{name} must be imported, not rewritten")
        # A second implementation of the bucket rule is the failure this guards against.
        self.assertNotIn("def classify_diff", source)
        self.assertNotIn("def raw_diff", source)
        self.assertNotIn("BUCKETS = (", source)

    def test_only_the_committed_mine_site_is_accepted(self) -> None:
        """Checked through the pure scope function, for the second time in this file.

        The subprocess form of this test failed from a `git archive`: the diagnostic
        checks authority B before the site scope, so with no `.git` present it exits on
        the missing history and the assertion never sees "not mine". Exactly the trap
        already fixed for the builder's copy of this test — and reintroduced here, which
        is why the rule is now written down: **never assert a late refusal through a
        subprocess when an earlier refusal can fire first.**
        """
        import json as _json

        doc = _json.loads(builder.COMMITMENT.read_text())
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import diag_measure_ff_mine as diag  # noqa: PLC0415

        self.assertEqual(diag.mine_site(doc), "SLICE_X2Y25")
        holdouts = sorted({s["site"] for s in doc["specimens"] if s["split"] == "holdout"})
        self.assertEqual(len(holdouts), 7)
        # The diagnostic calls the builder's scope function, so this is the same rule the
        # tool enforces, not a restatement of it.
        self.assertIs(diag.check_instance_scope, builder.check_instance_scope)
        for site in holdouts:
            with self.subTest(site), self.assertRaises(SystemExit) as caught:
                diag.check_instance_scope(doc, site)
            self.assertIn("not mine", str(caught.exception))

    def test_the_false_positive_rule_has_exactly_one_definition_in_the_repo(self) -> None:
        """Lives here, not with the artifact-gated negatives, because it needs no build.

        It sat in a class whose `setUp` skips when `build/` has no smoke artifacts, so a
        cold checkout skipped the one check that the FP rule is not duplicated — a silent
        pass for the property most worth guarding.
        """
        definitions = [path for path in (REPO_ROOT / "scripts").glob("*.py")
                       if "def false_positive_bits(" in path.read_text()]
        self.assertEqual([p.name for p in definitions], ["gate_measure_ff.py"])
        for consumer in ("scripts/gate_measure_ff.py", "scripts/diag_measure_ff_mine.py"):
            self.assertIn("false_positive_bits(buckets, class_claimed_out_of_scope)",
                          (REPO_ROOT / consumer).read_text(), consumer)

    def test_the_output_cannot_be_mistaken_for_a_certificate(self) -> None:
        source = self.DIAG.read_text()
        self.assertIn('"diagnostic_only": True', source)
        self.assertIn('"certifiable": False', source)
        self.assertIn('"complete": False', source)
        # No schema_version, so the consumer's very first check rejects it.
        self.assertNotIn('"schema_version"', source)

    def test_it_refuses_to_write_into_the_certification_path(self) -> None:
        # Checked by running it, not by grepping for "gate_runs/": the tool legitimately
        # READS the commitment from there, so a source scan would either miss the real
        # rule or ban a necessary line. What matters is that it will not WRITE there.
        checked = subprocess.run(
            [PYTHON, str(self.DIAG), "--build", str(REPO_ROOT / "build/gate_ff_formal"),
             "--out", str(REPO_ROOT / "gate_runs/run_2026_08_05_ff/sneaked.json")],
            cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("refusing to write a diagnostic into the certification path",
                      checked.stdout + checked.stderr)
        self.assertFalse((REPO_ROOT / "gate_runs/run_2026_08_05_ff/sneaked.json").exists())

    def test_the_false_positive_rule_is_exercised_and_not_merely_present(self) -> None:
        # Neutering the FP computation used to pass the whole suite. Each of the three
        # contributing sets is checked to reach the result, and the three that must NOT
        # contribute are checked to stay out.
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import diag_measure_ff_mine as diag  # noqa: PLC0415

        empty = {name: set() for name in builder_buckets()}
        self.assertEqual(diag.false_positive_bits(empty, set()), set())

        for contributing in ("ownership_unknown", "unattributed"):
            with self.subTest(contributing):
                buckets = {name: set() for name in builder_buckets()}
                buckets[contributing] = {(1, 2, 3)}
                self.assertEqual(diag.false_positive_bits(buckets, set()), {(1, 2, 3)})

        for excluded in ("in_scope", "frame_ecc", "db_attributed"):
            with self.subTest(excluded):
                buckets = {name: set() for name in builder_buckets()}
                buckets[excluded] = {(4, 5, 6)}
                self.assertEqual(diag.false_positive_bits(buckets, set()), set())

        # db_attributed contributes only through the class-claimed-out-of-scope subset.
        buckets = {name: set() for name in builder_buckets()}
        buckets["db_attributed"] = {(7, 8, 9)}
        self.assertEqual(diag.false_positive_bits(buckets, {(7, 8, 9)}), {(7, 8, 9)})


def builder_buckets():
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from gate_measure_ff import BUCKETS  # noqa: PLC0415

    return BUCKETS


@unittest.skipUnless(has_history(), "the diagnostic itself requires a clone (§1.3)")
class DiagnosticArtifactGateTests(unittest.TestCase):
    """The diagnostic must not score anything the builder's own gate would refuse.

    **Clone-only, and for the tool's own reason rather than a testing convenience.** The
    diagnostic checks authority B before anything else, so from a `git archive` every
    case here exits on the missing history and none of them tests what it claims to.
    That is the same trap that has now caught this file three times: a subprocess
    asserting a late refusal, with an earlier refusal able to fire first. The tamper
    negatives themselves need no real bitstreams — they run on a synthetic tree — so in
    a clone they run whether or not `build/` has been populated.

    It read `spec.bit` straight off a path convention until this was caught. A
    substituted bitstream, or a stamp whose recipe had drifted from the committed
    sources, would still have produced a confident FP=0 — the most dangerous shape a
    result can have, since it is the number that decides whether the ladder proceeds.

    Every case below must be refused BEFORE any frame is parsed, which is checked by
    asserting the refusal names the gate rather than a bitstream-parsing error.
    """

    DIAG = REPO_ROOT / "scripts/diag_measure_ff_mine.py"
    BUILD = REPO_ROOT / "build/gate_ff_formal"

    def synthetic_tree(self, root: Path) -> dict:
        """A build tree that PASSES the artifact gate, with placeholder artifacts.

        Every refusal below fires before a frame is parsed, so the tamper negatives do
        not need real bitstreams — and building them synthetically is what stops them
        from being skipped on a cold checkout, where `build/` is empty. A skipped
        negative is a silent pass, and these guard the number that decides whether the
        ladder proceeds.
        """
        doc = json.loads(builder.COMMITMENT.read_text())
        mapping = builder.check_site_mapping(doc)
        nodes = builder.plan_nodes(doc, mapping, root, "SLICE_X2Y25")
        base_dir = root / "SLICE_X2Y25" / "base"
        for node in nodes:
            node["outdir"].mkdir(parents=True, exist_ok=True)
            for name in builder.ARTIFACTS[node["node_type"]]:
                (node["outdir"] / name).write_text(f"placeholder {node['variant']} {name}")
        base_dcp = builder.sha256_file(base_dir / "base.dcp")
        for node in nodes:
            stamp = {"schema": "ff_formal_stamp/1", "node_type": node["node_type"],
                     "instance": node["instance"], "variant": node["variant"],
                     "sites": node["sites"], "recipe": node["recipe"], "completed": True,
                     "artifacts": {name: builder.sha256_file(node["outdir"] / name)
                                   for name in builder.ARTIFACTS[node["node_type"]]}}
            if node["node_type"] == "derived":
                node["base_dcp_sha256"] = base_dcp
                stamp["derived_from"] = {"specimen_id": "SLICE_X2Y25_base",
                                         "base_dcp_sha256": base_dcp}
            (node["outdir"] / "stamp.json").write_text(json.dumps(stamp, indent=2))
        return {n["specimen_id"]: n for n in nodes}

    def run_diag(self, build: Path) -> subprocess.CompletedProcess[str]:
        with tempfile.NamedTemporaryFile(suffix=".json") as out:
            return subprocess.run(
                [PYTHON, str(self.DIAG), "--build", str(build), "--out", out.name],
                cwd=REPO_ROOT, capture_output=True, text=True, check=False)

    def copy_tree(self, directory: str) -> Path:
        """Copy the build tree and relocate the absolute paths inside each stamp.

        `recipe.tclargs` records the invocation verbatim, absolute paths and all, so a
        copied tree fails the recipe check for a reason that has nothing to do with what
        these tests are probing. Rewriting the root is what makes each negative below
        fail for its OWN reason rather than all of them failing identically — and it is
        also the concrete cost of absolute paths in the recipe domain: a build tree is
        not relocatable without rewriting its stamps.
        """
        target = Path(directory) / "build"
        shutil.copytree(self.BUILD, target)
        for stamp_path in target.glob("*/*/stamp.json"):
            stamp = json.loads(stamp_path.read_text())
            stamp["recipe"]["tclargs"] = [
                arg.replace(str(self.BUILD.resolve()), str(target.resolve()))
                for arg in stamp["recipe"]["tclargs"]]
            stamp_path.write_text(json.dumps(stamp))
        return target

    def test_the_untampered_tree_passes(self) -> None:
        # The only case here that needs REAL bitstreams: it parses frames. The tamper
        # negatives all refuse earlier and run everywhere on a synthetic tree.
        stamp_path = self.BUILD / "SLICE_X2Y25" / "base" / "stamp.json"
        if not (self.BUILD / "SLICE_X2Y25" / "base" / "spec.bit").is_file():
            self.skipTest("mine smoke artifacts not present in build/ (gitignored)")
        # A recipe-domain change invalidates every artifact on disk by design, and the
        # diagnostic refuses them for that reason. Say so, rather than reporting the
        # deliberate invalidation as a broken diagnostic.
        recorded = json.loads(stamp_path.read_text())["recipe"]["sources"]
        drifted = [path for path, digest in recorded.items()
                   if hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest() != digest]
        if drifted:
            self.skipTest("built artifacts predate the current recipe and are invalidated "
                          f"until rebuilt (changed: {', '.join(sorted(drifted))})")
        checked = self.run_diag(self.BUILD)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn("false positives     : 0", checked.stdout)

    def test_a_substituted_bitstream_is_refused(self) -> None:
        with scratch() as directory:
            build = Path(directory) / "build"
            self.synthetic_tree(build)
            victim = build / "SLICE_X2Y25" / "zrst_AFF" / "spec.bit"
            shutil.copy(build / "SLICE_X2Y25" / "clkinv" / "spec.bit", victim)
            checked = self.run_diag(build)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("does not match the hash the stamp recorded",
                          checked.stdout + checked.stderr)

    def test_a_drifted_stamp_source_hash_is_refused(self) -> None:
        with scratch() as directory:
            build = Path(directory) / "build"
            self.synthetic_tree(build)
            stamp_path = build / "SLICE_X2Y25" / "base" / "stamp.json"
            stamp = json.loads(stamp_path.read_text())
            key = "scripts/gate_build_ff_formal.py"
            stamp["recipe"]["sources"][key] = "0" * 64
            stamp_path.write_text(json.dumps(stamp))
            checked = self.run_diag(build)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("different recipe", checked.stdout + checked.stderr)

    def test_a_missing_specimen_is_refused(self) -> None:
        with scratch() as directory:
            build = Path(directory) / "build"
            self.synthetic_tree(build)
            shutil.rmtree(build / "SLICE_X2Y25" / "latch")
            checked = self.run_diag(build)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("refusing to use", checked.stdout + checked.stderr)

    def test_a_derived_specimen_pinned_to_another_base_is_refused(self) -> None:
        with scratch() as directory:
            build = Path(directory) / "build"
            self.synthetic_tree(build)
            stamp_path = build / "SLICE_X2Y25" / "zini_AFF" / "stamp.json"
            stamp = json.loads(stamp_path.read_text())
            stamp["derived_from"]["base_dcp_sha256"] = "0" * 64
            stamp_path.write_text(json.dumps(stamp))
            checked = self.run_diag(build)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("derives from a different base checkpoint",
                          checked.stdout + checked.stderr)

