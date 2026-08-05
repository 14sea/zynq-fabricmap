"""The `clb_ff_config` plan, checked before anything is committed or built.

These tests run entirely on the freeze. They are what makes the draft reviewable: the
plan claims to cover the class exactly once, to compute every address from the normative
arithmetic, and to predict a direction for each feature that a bitstream can refute.
Each of those is checked here rather than asserted in prose.

The hold itself is tested too. Pre-registration is the author's to lift, and a tool that
could be talked into writing a commitment by passing a path is not held at all. The
author lifted it on 2026-08-05 and the commitment is emitted, so the guard is now
exercised with the flag forced on rather than as it ships — and the test that matters
most is the new one: the emitter must still reproduce the committed hash exactly.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
EMITTER = REPO_ROOT / "scripts/gate_emit_ff.py"
CERTIFIER = REPO_ROOT / "scripts/gate_certify_ff.py"
DB = REPO_ROOT / "data/prjxray/zynq7"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from gate_measure_ff import address_decision, semantic_verdict  # noqa: E402


COMMITMENT = REPO_ROOT / "gate_runs/run_2026_08_05_ff/predictions.json"
COMMITTED_SHA256 = "5440ef27acbd5b4f624cae54f4ffad89b3f656c1e6e5fa35b29226ff0d1b2e51"


def scratch() -> tempfile.TemporaryDirectory:
    """A scratch directory inside `build/`, created if it is not there.

    The location is load-bearing, not a habit: the emitter's hold permits a draft only
    under `build/`, so a test that exercises the held path cannot scratch anywhere else.
    But `build/` is gitignored, so it does not exist in a fresh clone — and this suite
    exists precisely so that someone who clones the repo can try to falsify its
    artifacts. Without this, nine tests error out on a clean checkout and twenty-four
    more never run.
    """
    (REPO_ROOT / "build").mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(dir=REPO_ROOT / "build")


def emit(out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(EMITTER), "--out", str(out)],
        cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )


def emit_with_the_hold_forced_on(out: Path) -> subprocess.CompletedProcess[str]:
    """Run the shipped guard, not a copy of it, with `PREREGISTRATION_HOLD` set True.

    The flag is False since the author lifted it, so the refusal path can no longer be
    reached the way the tool ships. Setting the module global in a child process still
    executes the real `main()`, which is the code that has to refuse.
    """
    driver = (
        "import sys; sys.path.insert(0, 'scripts');"
        "import gate_emit_ff as emitter;"
        "emitter.PREREGISTRATION_HOLD = True;"
        "sys.argv = ['gate_emit_ff.py', '--out', sys.argv[1]];"
        "sys.exit(emitter.main())"
    )
    return subprocess.run(
        [PYTHON, "-c", driver, str(out)],
        cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )


class FfPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = scratch()
        out = Path(cls._directory.name) / "predictions.json"
        checked = emit(out)
        assert checked.returncode == 0, checked.stdout
        cls.plan = json.loads(out.read_text())
        spec = json.loads((REPO_ROOT / "data/subset_spec.json").read_text())
        cls.pattern = re.compile(
            next(c["feature_regex"] for c in spec["bit_classes"] if c["id"] == "clb_ff_config")
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def test_every_frozen_entry_is_asserted_exactly_once(self) -> None:
        frozen = set()
        for tile_type in {s["tile_type"] for s in self.plan["specimens"]}:
            for line in (DB / f"segbits_{tile_type.lower()}.db").read_text().splitlines():
                fields = line.split()
                if fields and self.pattern.fullmatch(fields[0]):
                    frozen.add(fields[0])
        asserted = [p["feature"] for p in self.plan["predictions"]]
        self.assertEqual(len(frozen), 176)
        self.assertEqual(sorted(asserted), sorted(frozen))
        self.assertEqual(len(asserted), len(set(asserted)))

    def test_manifest_denominator_and_totals_agree(self) -> None:
        manifest = json.loads((REPO_ROOT / "data/MANIFEST.json").read_text())
        entries = next(c["entries"] for c in manifest["bit_classes"] if c["id"] == "clb_ff_config")
        self.assertEqual(entries, len(self.plan["predictions"]))
        self.assertEqual(self.plan["totals"]["predictions"], len(self.plan["predictions"]))
        self.assertEqual(
            self.plan["totals"]["holdout_predictions"],
            sum(1 for p in self.plan["predictions"] if p["split"] == "holdout"),
        )

    def test_split_leaves_the_established_site_unable_to_score(self) -> None:
        mine = {p["feature"] for p in self.plan["predictions"] if p["split"] == "mine"}
        self.assertEqual(len(mine), 22)
        for prediction in self.plan["predictions"]:
            specimen = next(s for s in self.plan["specimens"]
                            if s["specimen_id"] == prediction["specimen_id"])
            expected = "mine" if specimen["site"] == "SLICE_X2Y25" else "holdout"
            self.assertEqual(prediction["split"], expected)

    def test_every_rule_is_single_bit_and_addressed_by_the_normative_arithmetic(self) -> None:
        tilegrid = json.loads((DB / "xc7z010/tilegrid.json").read_text())
        for prediction in self.plan["predictions"]:
            specimen = next(s for s in self.plan["specimens"]
                            if s["specimen_id"] == prediction["specimen_id"])
            block = tilegrid[specimen["tile"]]["bits"]["CLB_IO_CLK"]
            self.assertEqual(len(prediction["predicted_assignments"]), 1)
            item = prediction["predicted_assignments"][0]
            frame, bit = item["segbit"]["frame_offset"], item["segbit"]["bit_offset"]
            self.assertEqual(
                item["address"],
                {"far": f"0x{int(block['baseaddr'], 16) + frame:08X}",
                 "word": block["offset"] + bit // 32, "bit": bit % 32},
            )

    def test_the_asserted_endpoint_is_a_refutable_direction(self) -> None:
        for prediction in self.plan["predictions"]:
            item = prediction["predicted_assignments"][0]
            expected = 0 if item["segbit"]["negated"] else 1
            self.assertEqual(item["expected_value"], expected)
            # the other endpoint must carry the complement, or the pair asserts nothing
            self.assertEqual(prediction["expected_transition"],
                             {"before": 1 - expected, "after": expected})

    def test_the_negated_tokens_are_exactly_the_noclkinv_features(self) -> None:
        negated = {p["feature"] for p in self.plan["predictions"]
                   if p["predicted_assignments"][0]["segbit"]["negated"]}
        self.assertEqual(len(negated), 8)
        self.assertTrue(all(name.endswith(".NOCLKINV") for name in negated))

    def test_complementary_clock_features_share_one_address(self) -> None:
        by_feature = {p["feature"]: p for p in self.plan["predictions"]}
        for name, prediction in by_feature.items():
            if not name.endswith(".CLKINV"):
                continue
            partner = by_feature[name.replace(".CLKINV", ".NOCLKINV")]
            self.assertEqual(prediction["predicted_assignments"][0]["address"],
                             partner["predicted_assignments"][0]["address"])
            # opposite values in different specimens: the 1.4 complementary pattern
            self.assertNotEqual(prediction["specimen_id"], partner["specimen_id"])

    def test_every_feature_has_exactly_one_endpoint_pair(self) -> None:
        owners = {}
        for specimen in self.plan["specimens"]:
            for feature in specimen["pair_features"]:
                self.assertNotIn(feature, owners)
                owners[feature] = specimen
        self.assertEqual(len(owners), len(self.plan["predictions"]))
        for prediction in self.plan["predictions"]:
            variant = owners[prediction["feature"]]
            base_id = f"{variant['site']}_base"
            # the asserting endpoint is one of the pair's two ends and never both
            self.assertIn(prediction["specimen_id"], (base_id, variant["specimen_id"]))
            self.assertTrue(any(s["specimen_id"] == base_id for s in self.plan["specimens"]))

    def test_four_features_are_claimed_to_assert_in_the_baseline(self) -> None:
        # ZRST, CEUSEDMUX, SRUSEDMUX, FFSYNC and NOCLKINV read the Z convention as
        # "asserted when the control is in its default state". If that is backwards the
        # gate must record FN, so the plan has to state it rather than accept either way.
        tails = {p["feature"].split(".", 2)[2] for p in self.plan["predictions"]
                 if p["specimen_id"].endswith("_base")}
        self.assertEqual(
            {t for t in tails if not t.endswith(".ZRST")},
            {"CEUSEDMUX", "SRUSEDMUX", "FFSYNC", "NOCLKINV"},
        )
        self.assertEqual(sum(1 for t in tails if t.endswith(".ZRST")), 8)

    def test_semantic_assertions_are_scalar_and_point_into_the_attestation(self) -> None:
        for prediction in self.plan["predictions"]:
            assertion = prediction["semantic_assertion"]
            self.assertEqual(assertion["kind"], "member_identity")
            self.assertTrue(assertion["semantic"])
            self.assertEqual(assertion["predicted_member"], prediction["feature"])
            self.assertTrue(assertion["attestation_field"].startswith("/resolved/"))
            self.assertIsInstance(assertion["expected_value"], str)

    def test_prediction_records_carry_exactly_the_1_5_contract_fields(self) -> None:
        self.assertEqual(self.plan["schema_version"], "1.5.0")
        expected = {"specimen_id", "comparison_specimen_id", "feature", "split",
                    "rule_file", "predicted_assignments", "expected_transition",
                    "semantic_assertion"}
        for prediction in self.plan["predictions"]:
            self.assertEqual(set(prediction), expected)

    def test_both_endpoints_of_every_pair_are_committed(self) -> None:
        # The round-10 rule: the comparison endpoint is preregistered, so it cannot be
        # chosen after the bitstreams exist. Every value it takes must be a real
        # specimen, must differ from the asserting one, and must agree with the
        # specimen plan's own pairing.
        ids = {s["specimen_id"] for s in self.plan["specimens"]}
        owners = {feature: s for s in self.plan["specimens"]
                  for feature in s["pair_features"]}
        for prediction in self.plan["predictions"]:
            comparison = prediction["comparison_specimen_id"]
            self.assertIn(comparison, ids)
            self.assertNotEqual(comparison, prediction["specimen_id"])
            owner = owners[prediction["feature"]]
            ends = {owner["specimen_id"], owner["pair_with"]}
            self.assertEqual({prediction["specimen_id"], comparison}, ends)

    def test_the_latch_pair_is_against_its_control_matched_baseline(self) -> None:
        # Measured, not assumed: pairing LATCH against the shared base moves FFSYNC and
        # CLKINV too, and eight latches per slice will not build at all.
        for prediction in self.plan["predictions"]:
            if not prediction["feature"].endswith(".LATCH"):
                continue
            self.assertTrue(prediction["specimen_id"].endswith("_latch"))
            self.assertTrue(prediction["comparison_specimen_id"].endswith("_latch_base"))

    def test_the_pair_set_is_a_consequence_of_the_commitment(self) -> None:
        pairs = {frozenset((p["specimen_id"], p["comparison_specimen_id"]))
                 for p in self.plan["predictions"]}
        self.assertEqual(len(pairs), 168)
        self.assertEqual(len(self.plan["specimens"]), 184)
        # no specimen is committed that no pair uses
        used = {name for pair in pairs for name in pair}
        self.assertEqual(used, {s["specimen_id"] for s in self.plan["specimens"]})

    def test_the_emitter_refuses_to_write_a_commitment_while_the_hold_stands(self) -> None:
        probe = REPO_ROOT / "gate_runs/ff_hold_probe"
        self.addCleanup(lambda: shutil.rmtree(probe, ignore_errors=True))
        checked = emit_with_the_hold_forced_on(probe / "predictions.json")
        self.assertNotEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("pre-registration is HELD", checked.stdout)
        self.assertFalse(probe.exists())

    def test_the_hold_is_lifted_and_the_committed_plan_is_frozen(self) -> None:
        # With the hold lifted nothing in the tool stops an edit to the plan from
        # silently changing what a re-emission produces. `gate_measure_ff.py` would
        # catch it at scoring time by hash; this catches it at the commit that causes
        # it. The ordering is the evidence, so the hash is not allowed to move.
        self.assertTrue(COMMITMENT.is_file(), f"{COMMITMENT} is the commitment of record")
        digest = hashlib.sha256(COMMITMENT.read_bytes()).hexdigest()
        self.assertEqual(digest, COMMITTED_SHA256)

        with scratch() as directory:
            fresh = Path(directory) / "predictions.json"
            checked = emit(fresh)
            self.assertEqual(checked.returncode, 0, checked.stdout)
            self.assertIn("COMMIT THIS HASH", checked.stdout)
            self.assertEqual(fresh.read_bytes(), COMMITMENT.read_bytes())


class CommittedPairAccountingTests(unittest.TestCase):
    """176 predictions must produce 168 accounting records, not 176.

    A pair is an unordered set of two specimens: one diff, one five-bucket record. The
    eight complementary `CLKINV`/`NOCLKINV` pairs assert in both directions over one
    bit, so keying the accounting by `(comparison, asserting)` recorded each of them
    twice — which double-counts any FP they carry and fails the verifier's
    "exactly the committed pair set, once per pair" check outright. The direction is
    still per feature, because the transition is read from a specific end.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = scratch()
        out = Path(cls._directory.name) / "predictions.json"
        checked = emit(out)
        assert checked.returncode == 0, checked.stdout
        cls.plan = json.loads(out.read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def pairs(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from gate_measure_ff import committed_pairs  # noqa: PLC0415

        return committed_pairs(self.plan)

    def test_the_accounting_key_is_the_unordered_pair(self) -> None:
        scopes, direction = self.pairs()
        self.assertEqual(len(self.plan["predictions"]), 176)
        self.assertEqual(len(scopes), 168)
        self.assertEqual(len(direction), 176)
        # and it agrees with the commitment read independently of the tool
        expected = {tuple(sorted((p["specimen_id"], p["comparison_specimen_id"])))
                    for p in self.plan["predictions"]}
        self.assertEqual(set(scopes), expected)

    def test_complementary_features_share_one_accounting_record(self) -> None:
        scopes, direction = self.pairs()
        clkinv = next(f for f in direction if f.endswith(".CLKINV"))
        noclkinv = clkinv.replace(".CLKINV", ".NOCLKINV")
        # opposite directions, one pair, one scope entry
        self.assertEqual(direction[clkinv], tuple(reversed(direction[noclkinv])))
        self.assertEqual(tuple(sorted(direction[clkinv])),
                         tuple(sorted(direction[noclkinv])))
        self.assertEqual(len(scopes[tuple(sorted(direction[clkinv]))]), 1)

    def test_the_direction_still_names_which_end_asserts(self) -> None:
        _scopes, direction = self.pairs()
        for prediction in self.plan["predictions"]:
            comparison, asserting = direction[prediction["feature"]]
            self.assertEqual(asserting, prediction["specimen_id"])
            self.assertEqual(comparison, prediction["comparison_specimen_id"])

    def test_every_pair_scope_covers_all_of_its_features(self) -> None:
        scopes, _direction = self.pairs()
        for prediction in self.plan["predictions"]:
            key = tuple(sorted((prediction["specimen_id"],
                                prediction["comparison_specimen_id"])))
            for item in prediction["predicted_assignments"]:
                address = (int(item["address"]["far"], 16),
                           item["address"]["word"], item["address"]["bit"])
                self.assertIn(address, scopes[key])

    def test_the_pair_alarm_names_fields_the_record_actually_has(self) -> None:
        # This branch only runs when something is already wrong, so it is the one most
        # likely to be broken and least likely to be noticed.
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from gate_measure_ff import format_pair_alarm  # noqa: PLC0415

        record = {
            "site": "SLICE_X3Y25", "variants": ["base", "clkinv"],
            "specimen_ids": ["SLICE_X3Y25_base", "SLICE_X3Y25_clkinv"],
            "raw_diff_bits": 7,
            "counts": {"in_scope": 1, "frame_ecc": 5, "db_attributed": 0,
                       "ownership_unknown": 1, "unattributed": 0},
            "false_positive_addresses": [{"far": "0x00400A01", "word": 52, "bit": 19}],
        }
        line = format_pair_alarm(record)
        self.assertIn("base+clkinv", line)
        self.assertIn("unk=  1", line)
        self.assertIn("FP=1", line)


class LatchProbeScopeTests(unittest.TestCase):
    """The probe's scope limits, which are enforcement rather than documentation.

    Exploration runs on the mine site because that site's evidence is already spent.
    A probe that could be pointed at a holdout site would quietly destroy the only
    thing a holdout is for, and it would do so through a flag nobody reviews.
    """

    PROBE = REPO_ROOT / "scripts/gate_build_ff.py"

    def run_probe(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, str(self.PROBE), *arguments],
            cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False)

    def test_a_holdout_site_is_refused(self) -> None:
        for site in ("SLICE_X3Y25", "SLICE_X8Y25", "SLICE_X25Y25"):
            with self.subTest(site):
                checked = self.run_probe("--site", site, "--report-only")
                self.assertIn("builds SLICE_X2Y25 only", checked.stdout)

    def test_writing_into_the_committed_evidence_tree_is_refused(self) -> None:
        checked = self.run_probe("--out", "gate_runs/latch_probe", "--report-only")
        self.assertIn("writes under build/ only", checked.stdout)
        self.assertFalse((REPO_ROOT / "gate_runs/latch_probe").exists())

    def test_the_probe_never_touches_the_pre_registration_hold(self) -> None:
        source = self.PROBE.read_text()
        self.assertNotIn("PREREGISTRATION_HOLD =", source)
        self.assertNotIn("predictions.json", source)

    def test_a_stale_or_unstamped_output_directory_is_refused(self) -> None:
        # Artifacts existing is not evidence that they are THIS run's artifacts. The
        # cases below all look like a successful build from the outside.
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from gate_build_ff import cache_state, recipe_hashes  # noqa: PLC0415

        with scratch() as directory:
            outdir = Path(directory) / "mode"
            outdir.mkdir()
            for name in ("spec.bit", "readback.tsv", "base.dcp"):
                (outdir / name).write_bytes(b"stale")
            self.assertEqual(cache_state(outdir, 0)[0], "refuse")

            def stamp(**overrides) -> None:
                value = {
                    "completed": True, "mode": 0, "site": "SLICE_X2Y25",
                    "recipe": recipe_hashes(),
                    "artifacts": {name: hashlib.sha256(b"stale").hexdigest()
                                  for name in ("spec.bit", "readback.tsv", "base.dcp")},
                }
                value.update(overrides)
                (outdir / "stamp.json").write_text(json.dumps(value))

            stamp()
            self.assertEqual(cache_state(outdir, 0)[0], "reuse")
            stamp(mode=3)
            self.assertEqual(cache_state(outdir, 0)[0], "refuse")
            stamp(site="SLICE_X9Y25")
            self.assertEqual(cache_state(outdir, 0)[0], "refuse")
            # a stamp of THIS recipe that did not complete is "failed", not "refuse" —
            # it is a real outcome, and the next test pins the difference
            stamp(completed=False)
            self.assertEqual(cache_state(outdir, 0)[0], "failed")
            stamp(recipe={"vivado/specimen/specimen_ff_probe.v": "0" * 64})
            self.assertEqual(cache_state(outdir, 0)[0], "refuse")
            stamp()
            (outdir / "spec.bit").write_bytes(b"different")
            self.assertEqual(cache_state(outdir, 0)[0], "refuse")

    def test_a_failed_build_of_this_recipe_is_distinguished_from_a_stale_one(self) -> None:
        # "This exact recipe failed here" is an answer for a MAY_FAIL mode; "something
        # else was built here" never is. Collapsing the two would let a stale directory
        # be reported as an unbuildable mode.
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from gate_build_ff import cache_state, recipe_hashes, verified_state  # noqa: PLC0415

        with scratch() as directory:
            outdir = Path(directory) / "mode"
            outdir.mkdir()
            (outdir / "run.out").write_text("ERROR: nope\n")
            (outdir / "stamp.json").write_text(json.dumps({
                "completed": False, "mode": 5, "site": "SLICE_X2Y25",
                "recipe": recipe_hashes(), "artifacts": {}}))
            self.assertEqual(cache_state(outdir, 5)[0], "failed")
            self.assertEqual(verified_state(5, outdir)[0], "failed")
            # a failure stamped under a different recipe is stale, not an answer
            (outdir / "stamp.json").write_text(json.dumps({
                "completed": False, "mode": 5, "site": "SLICE_X2Y25",
                "recipe": {"vivado/specimen/specimen_ff_probe.v": "0" * 64},
                "artifacts": {}}))
            self.assertEqual(cache_state(outdir, 5)[0], "refuse")
            with self.assertRaises(SystemExit):
                verified_state(5, outdir)


class LatchProbeEvidenceTests(unittest.TestCase):
    """The committed evidence must be self-describing, because build/ is gitignored.

    A record that pointed at artifacts a fresh clone cannot resolve is a record nobody
    can check — the same reason measurements copy their attestations into the run
    directory.
    """

    EVIDENCE = REPO_ROOT / "evidence/ff_latch_probe_2026_08_04"

    def test_the_manifest_hashes_match_the_files_it_names(self) -> None:
        manifest = json.loads((self.EVIDENCE / "manifest.json").read_text())
        self.assertTrue(manifest["files"])
        for name, digest in manifest["files"].items():
            path = self.EVIDENCE / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, name)

    def test_the_recorded_result_is_the_one_the_documents_cite(self) -> None:
        report = json.loads((self.EVIDENCE / "probe_report.json").read_text())
        pairs = {item["pair"]: item for item in report["pairs"]}
        formal = pairs["main_only"]
        self.assertTrue(formal["isolated_to_latch_bit"])
        self.assertEqual(formal["false_positive_count_under_1_4"], 0)
        self.assertEqual(formal["counts"]["in_scope"], 1)
        self.assertEqual(len(formal["same_class_movers"]), 1)
        self.assertEqual(formal["same_class_movers"][0]["direction"], "0->1")
        # eight latches per slice is not buildable, and the record must say so
        self.assertIn("full_latch", report["unbuildable_modes"])
        self.assertIn("not_measured", pairs["full_slice"])
        self.assertTrue(report["recipe"])

    def test_the_unbuildable_mode_carries_its_own_log_not_a_pointer_into_build(self) -> None:
        manifest = json.loads((self.EVIDENCE / "manifest.json").read_text())
        for name, record in manifest["unbuildable_modes"].items():
            self.assertTrue(record["error_lines"], name)
            self.assertIn("FF_INIT", " ".join(record["error_lines"]))
            log = record["log"]
            self.assertIn(log, manifest["files"])
            self.assertTrue((self.EVIDENCE / log).is_file())


def totals(tp: int, fn: int, fp: int, semantic_pass: int, semantic_fail: int) -> dict:
    return {
        "mine": {"tp": 0, "fn": 0, "fp": 0, "member_identity": {"pass": 0, "fail": 0}},
        "holdout": {"tp": tp, "fn": fn, "fp": fp,
                    "member_identity": {"pass": semantic_pass, "fail": semantic_fail}},
    }


EXACT_PAIR = [{"partition_exact": True}]


class SemanticIsolationTests(unittest.TestCase):
    """A naming claim must never be able to fail an addressing result.

    The defect these tests exist against was real: the measurement tool appended a
    semantic mismatch to the same `problems` list that sank the address decision, so a
    wrong attestation field would have failed a class whose addressing the bitstream
    itself confirmed. 1.4 isolates the two, and isolation that is not tested is a
    comment.
    """

    def test_semantic_only_failure_keeps_the_address_decision_passing(self) -> None:
        self.assertEqual(
            address_decision(totals(154, 0, 0, 153, 1), EXACT_PAIR, [], 154), "PASS")

    def test_address_problems_still_sink_the_address_decision(self) -> None:
        for problems, description in (
            (["specimen X: no attestation"], "evidence integrity"),
            (["base/variant: buckets overlap"], "partition integrity"),
        ):
            with self.subTest(description):
                self.assertEqual(
                    address_decision(totals(154, 0, 0, 154, 0), EXACT_PAIR, problems, 154),
                    "FAIL")

    def test_the_address_decision_cannot_see_semantics_at_all(self) -> None:
        # Same call, every semantic count swept from clean to broken: the decision is a
        # function of address evidence only, so it must not move.
        for semantic_pass, semantic_fail in ((154, 0), (77, 77), (0, 154)):
            self.assertEqual(
                address_decision(totals(154, 0, 0, semantic_pass, semantic_fail),
                                 EXACT_PAIR, [], 154),
                "PASS")

    def test_fn_fp_and_short_holdout_counts_still_fail(self) -> None:
        self.assertEqual(address_decision(totals(153, 1, 0, 154, 0), EXACT_PAIR, [], 154), "FAIL")
        self.assertEqual(address_decision(totals(154, 0, 1, 154, 0), EXACT_PAIR, [], 154), "FAIL")
        self.assertEqual(address_decision(totals(153, 0, 0, 154, 0), EXACT_PAIR, [], 154), "FAIL")
        self.assertEqual(
            address_decision(totals(154, 0, 0, 154, 0), [{"partition_exact": False}], [], 154),
            "FAIL")

    def test_semantic_pass_is_the_verifier_rule_not_the_attestation_alone(self) -> None:
        # host/verify_certificate.py rebuilds `passed` as
        # transition_exact and attestation_basis_consistent, and rejects a record whose
        # copied boolean disagrees. A producer that passed on the attestation alone
        # would emit certificates the consumer refuses.
        self.assertTrue(semantic_verdict(True, "CLKINV", "CLKINV"))
        self.assertFalse(semantic_verdict(False, "CLKINV", "CLKINV"))
        self.assertFalse(semantic_verdict(True, "NOCLKINV", "CLKINV"))
        self.assertFalse(semantic_verdict(True, None, "CLKINV"))


class CertifierSemanticIsolationTests(unittest.TestCase):
    """The same isolation, end to end through `gate_certify_ff.py`.

    Built from the real draft plan rather than a hand-written stub, so the projection
    comparison the certifier performs is exercised against genuine preregistered
    records. No Vivado: the certifier reads JSON.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = scratch()
        root = Path(cls._directory.name)
        draft = root / "draft.json"
        checked = emit(draft)
        assert checked.returncode == 0, checked.stdout
        cls.plan = json.loads(draft.read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def build_run(self, root: Path, *, semantic_ok: bool, address_problems: list[str]) -> Path:
        """A two-key run: one clkinv pair, both endpoints, everything matched."""
        plan = copy.deepcopy(self.plan)
        site = "SLICE_X3Y25"          # holdout, so the keys actually score
        keep = [p for p in plan["predictions"]
                if p["feature"].endswith(("CLKINV", "NOCLKINV"))
                and p["specimen_id"].startswith(site + "_")]
        specimen_ids = {f"{site}_base", f"{site}_clkinv"}
        plan["specimens"] = [s for s in plan["specimens"] if s["specimen_id"] in specimen_ids]
        plan["predictions"] = keep
        plan["totals"] = {"specimens": len(plan["specimens"]), "predictions": len(keep),
                          "holdout_predictions": len(keep)}

        run = root / "run"
        run.mkdir()
        predictions_path = run / "predictions.json"
        predictions_path.write_text(json.dumps(plan, indent=2) + "\n")

        results = []
        for index, prediction in enumerate(keep):
            other = (specimen_ids - {prediction["specimen_id"]}).pop()
            item = prediction["predicted_assignments"][0]
            transition = prediction["expected_transition"]
            assertion = prediction["semantic_assertion"]
            observed = assertion["expected_value"] if semantic_ok or index else "WRONG_MODE"
            results.append({
                "prediction_specimen_id": prediction["specimen_id"],
                "feature": prediction["feature"],
                "split": prediction["split"],
                "rule_file": prediction["rule_file"],
                "baseline_specimen_id": other,
                "feature_specimen_id": prediction["specimen_id"],
                "predicted_assignments": prediction["predicted_assignments"],
                "expected_transition": transition,
                "semantic_assertion": assertion,
                "observed_assignments": [{
                    "address": item["address"],
                    "observed_value": transition["after"],
                    "before_value": transition["before"],
                    "after_value": transition["after"],
                }],
                "semantic_outcome": {
                    "kind": "member_identity", "semantic": True,
                    "passed": semantic_verdict(True, observed, assertion["expected_value"]),
                    "predicted_member": assertion["predicted_member"],
                    "attestation_field": assertion["attestation_field"],
                    "expected_value": assertion["expected_value"],
                    "observed_value": observed,
                },
                "verdict": "matched",
            })
        semantic_fail = sum(1 for r in results if not r["semantic_outcome"]["passed"])
        measurement = {
            "schema": "gate_measurement", "schema_version": "1.4.0",
            "bit_class": "clb_ff_config",
            "prediction_commitment": {
                "run_id": "run", "path": "build/x/predictions.json",
                "sha256": hashlib.sha256(predictions_path.read_bytes()).hexdigest(),
                "schema_version": plan["schema_version"], "seed": plan["seed"],
                "totals": plan["totals"],
            },
            "split_policy": plan["split_policy"],
            "specimens": [{
                "specimen_id": s["specimen_id"], "split": s["split"],
                "loc_site": s["site"], "tile": s["tile"], "tile_type": s["tile_type"],
                "tile_frame_base": "0x00400A00", "build_seed": s["build_seed"],
                "bitstream_sha256": "00" * 32, "design_source_sha256": "11" * 32,
                "vivado_version": "test", "part": "xc7z010clg400-1",
            } for s in plan["specimens"]],
            "totals": totals(len(results) - 0, 0, 0, len(results) - semantic_fail, semantic_fail),
            "results": results,
            "accounting": [{
                "site": site, "variant": "clkinv",
                "specimen_ids": sorted(specimen_ids), "raw_diff_bits": 0,
                "counts": {k: 0 for k in ("in_scope", "frame_ecc", "db_attributed",
                                          "ownership_unknown", "unattributed")},
                "buckets": {k: [] for k in ("in_scope", "frame_ecc", "db_attributed",
                                            "ownership_unknown", "unattributed")},
                "partition_exact": True,
                "false_positive_addresses": [],
            }],
            "decision": "PASS",
            "semantic_decision": "FAIL" if semantic_fail else "PASS",
            "address_problems": address_problems,
            "semantic_findings": ["synthetic semantic mismatch"] if semantic_fail else [],
        }
        (run / "measurement.json").write_text(json.dumps(measurement, indent=2) + "\n")
        return run

    def certify(self, run: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, str(CERTIFIER), "--run", str(run), "--out", str(run / "certificate.json")],
            cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False,
        )

    def test_semantic_only_failure_certifies_as_address_passed(self) -> None:
        with scratch() as directory:
            run = self.build_run(Path(directory), semantic_ok=False, address_problems=[])
            checked = self.certify(run)
            self.assertEqual(checked.returncode, 0, checked.stdout)
            certificate = json.loads((run / "certificate.json").read_text())
            self.assertEqual(certificate["status"], "passed")
            self.assertEqual(certificate["semantic_status"], "failed")
            self.assertEqual(certificate["failure_reasons"], [])
            self.assertEqual(certificate["bit_class"]["accounting"],
                             {"tp_count": 2, "fp_count": 0, "fn_count": 0})
            self.assertEqual(
                certificate["bit_class"]["semantic_accounting"]["member_identity"],
                {"pass_count": 1, "fail_count": 1})

    def test_an_address_problem_still_fails_the_certificate(self) -> None:
        with scratch() as directory:
            run = self.build_run(Path(directory), semantic_ok=True,
                                 address_problems=["specimen: no attestation"])
            checked = self.certify(run)
            self.assertEqual(checked.returncode, 0, checked.stdout)
            certificate = json.loads((run / "certificate.json").read_text())
            self.assertEqual(certificate["status"], "failed")
            self.assertEqual(certificate["semantic_status"], "passed")
            self.assertTrue(certificate["failure_reasons"])

    def test_a_clean_run_certifies_both_ways(self) -> None:
        with scratch() as directory:
            run = self.build_run(Path(directory), semantic_ok=True, address_problems=[])
            checked = self.certify(run)
            self.assertEqual(checked.returncode, 0, checked.stdout)
            certificate = json.loads((run / "certificate.json").read_text())
            self.assertEqual(certificate["status"], "passed")
            self.assertEqual(certificate["semantic_status"], "passed")
            self.assertEqual(certificate["bit_class"]["coverage"]["class_entry_count"], 176)


if __name__ == "__main__":
    unittest.main()
