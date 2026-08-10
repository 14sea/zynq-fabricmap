"""The report producer executes the frozen rules, or writes nothing.

Scope of this file, deliberately: **conformance fixtures only**. Nothing here emits a
report from `specs/reachability_spec_v1.json`, and the profile guard is exercised with a
SYNTHETIC spec that merely carries the production `spec_id`, so the production artifact is
never fed to the producer at all.

The two cases that matter most:

* `test_the_conformance_emission_matches_the_consumer_fixture` — the producer's derivation
  and the consumer's independently committed fixture agree field for field. Two
  implementations agreeing is evidence; this is the same rendezvous the literal known
  answer provides one level down.
* `test_parameters_come_from_the_spec_not_the_module` — a producer that reached for
  `CEILING_MIN` / `REDRAW_CAP` / `VECTOR_SEED` would judge a conformance spec by production
  numbers and still emit a schema-valid report. The conformance spec's cap is 4 against the
  module's 256, so a synthetic spec that must exhaust under its own cap and would not under
  the module's separates them.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "host"))

import build_reachability_spec as rules  # noqa: E402
import gate_reachability_report as producer  # noqa: E402
import verify_reachability_report as consumer  # noqa: E402

CONF_SPEC = REPO_ROOT / "tests/fixtures/reachability_spec_conformance.json"
CONF_REPORT = REPO_ROOT / "tests/fixtures/reachability_report_conformance.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def synthetic_lut(site: str, fixed_count: int) -> dict:
    """A LUT record that satisfies the consumer's internal-consistency contract.

    `spec_contract` checks mutable_mask against mutable_indices and the phenotype totals
    against the LUT list, so a fixture cannot be sketched — it has to be coherent. That is
    the contract doing real work.
    """
    fixed = list(range(fixed_count))
    mutable = [i for i in range(64) if i not in fixed]
    mask = sum(1 << i for i in mutable)
    return {
        "site": site,
        "bel": "A6LUT",
        "feature_prefix": f"SYN.{site}",
        "lock_pins": rules.LOCK_PINS,
        "base_init": "64'h0000000000000000",
        "mutable_mask": f"64'h{mask:016X}",
        "mutable_indices": mutable,
        "mutable_count": len(mutable),
        "fixed_indices": fixed,
        "fixed_count": len(fixed),
        "fixed_values": {str(i): 0 for i in fixed},
        "reachable_truth_tables": f"2^{len(mutable)}",
    }


def with_luts(spec: dict, luts: list[dict]) -> dict:
    """Install a LUT list and repair the phenotype totals the contract cross-checks."""
    spec["phenotype"]["luts"] = luts
    spec["phenotype"]["lut_count"] = len(luts)
    spec["phenotype"]["total_mutable_positions"] = sum(l["mutable_count"] for l in luts)
    spec["phenotype"]["total_fixed_positions"] = sum(l["fixed_count"] for l in luts)
    return spec


def commit_spec(repo: Path, spec: dict, name: str = "spec.json") -> Path:
    """Write a synthetic spec into a scratch repo and COMMIT it.

    The preflight refuses anything absent from HEAD before it looks at content, so a
    synthetic spec left uncommitted is refused for the wrong reason and the rule under
    test never runs. This repo's own trap — never assert a late refusal through a path
    where an earlier one fires first — now reachable from the other direction, because
    the authority check moved earlier on purpose.
    """
    path = repo / "tests/fixtures" / name
    path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", name], check=True,
                   capture_output=True)
    return path


def scratch_repo(register_cleanup) -> Path:
    """A throwaway git repo holding the conformance spec, so Git authority EXISTS.

    The preflight refuses to answer without HEAD, and a `git archive` export has no
    history — so any test that reaches `build_report` against the real repo passes hot and
    fails cold. This repo's own trap, and the third time in this file alone: it moved from
    the verifier into `build_report` the moment the authority check moved earlier. The
    consumer's tests solve it by CONSTRUCTING the authority instead of depending on it.

    `register_cleanup` is `self.addCleanup` or `cls.addClassCleanup`, so the same helper
    serves setUp and setUpClass.
    """
    tmp = tempfile.TemporaryDirectory()
    register_cleanup(tmp.cleanup)
    repo = Path(tmp.name)
    (repo / "tests" / "fixtures").mkdir(parents=True)
    (repo / "schemas").mkdir()
    shutil.copy(CONF_SPEC, repo / "tests/fixtures" / CONF_SPEC.name)
    shutil.copy(
        REPO_ROOT / "schemas/reachability_report.schema.json",
        repo / "schemas/reachability_report.schema.json",
    )
    for args in (
        ["init", "-q", str(repo)],
        ["-C", str(repo), "config", "user.email", "test@example.invalid"],
        ["-C", str(repo), "config", "user.name", "Test"],
        ["-C", str(repo), "add", "."],
        ["-C", str(repo), "commit", "-qm", "fixture"],
    ):
        subprocess.run(["git", *args], check=True, capture_output=True)
    return repo


class ConformanceEmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = scratch_repo(cls.addClassCleanup)
        cls.spec = cls.repo / "tests/fixtures" / CONF_SPEC.name
        cls.report = producer.build_report(
            cls.spec, "conformance", "producer_conformance", cls.repo
        )

    def test_the_conformance_emission_matches_the_consumer_fixture(self):
        theirs = load(CONF_REPORT)
        for field in ("status", "per_lut", "totals", "spec", "spec_sha256"):
            self.assertEqual(self.report[field], theirs[field], field)

    def test_the_record_is_schema_valid(self):
        self.assertEqual(consumer.schema_problems(self.report), [])

    def test_the_consumer_verifier_accepts_it(self):
        path = self.repo / "report.json"
        path.write_text(json.dumps(self.report, indent=2) + "\n", encoding="utf-8")
        self.addCleanup(path.unlink)
        self.assertEqual(
            consumer.verify_path(path, self.repo, require_production=False), []
        )

    def test_discards_carry_blocked_positions_consistent_with_their_ceiling(self):
        seen = 0
        for record in self.report["per_lut"]:
            for discard in record["discarded_draws"]:
                seen += 1
                self.assertEqual(
                    discard["attainable_ceiling"], 64 - len(discard["blocked_positions"])
                )
        self.assertGreater(seen, 0, "the conformance spec must exercise a discard")

    def test_the_spec_is_hash_pinned_from_its_bytes(self):
        self.assertEqual(
            self.report["spec_sha256"], producer.sha256_bytes(self.spec.read_bytes())
        )
        # and the scratch copy really is the committed fixture, byte for byte
        self.assertEqual(self.spec.read_bytes(), CONF_SPEC.read_bytes())


class ParameterSourceTests(unittest.TestCase):
    """Where the seed, ceiling and cap come from is the producer's sharpest failure mode."""

    def setUp(self):
        self.repo = scratch_repo(self.addCleanup)

    def synthetic(self, **overrides) -> Path:
        # one LUT that cannot reach the ceiling: 40 fixed positions.
        spec = with_luts(copy.deepcopy(load(CONF_SPEC)), [synthetic_lut("SYN_HARD", 40)])
        spec["target_family"]["redraw_cap"] = 3
        spec.update(overrides)
        return commit_spec(self.repo, spec, "synthetic.json")

    def test_parameters_come_from_the_spec_not_the_module(self):
        """cap 3 must exhaust; the module's 256 would keep drawing."""
        path = self.synthetic()
        report = producer.build_report(path, "conformance", "syn", self.repo)
        self.assertEqual(report["status"], "exhausted")
        record = report["per_lut"][0]
        self.assertTrue(record["exhausted"])
        self.assertEqual(len(record["discarded_draws"]), 3)
        self.assertNotEqual(len(record["discarded_draws"]), rules.REDRAW_CAP)

    def test_an_exhausted_lut_reports_null_target_fields(self):
        report = producer.build_report(self.synthetic(), "conformance", "syn", self.repo)
        record = report["per_lut"][0]
        for field in ("target_truth_table", "draw_index", "attainable_ceiling",
                      "blocked_positions"):
            self.assertIsNone(record[field], field)

    def test_totals_sum_selected_ceilings_only(self):
        report = producer.build_report(self.synthetic(), "conformance", "syn", self.repo)
        self.assertEqual(report["totals"]["attainable_ceiling"], 0)
        self.assertEqual(report["totals"]["selected_luts"], 0)
        self.assertTrue(report["totals"]["exhausted"])

    def spec_from(self, luts, **overrides) -> Path:
        spec = with_luts(copy.deepcopy(load(CONF_SPEC)), luts)
        for key, value in overrides.items():
            if key == "ceiling_min":
                spec["ceiling"]["minimum_accepted"] = value
            elif key == "cap":
                spec["target_family"]["redraw_cap"] = value
        name = f"spec_{len(list((self.repo / 'tests/fixtures').iterdir()))}.json"
        return commit_spec(self.repo, spec, name)

    lut = staticmethod(synthetic_lut)

    def test_the_ceiling_is_read_from_the_spec_not_the_module(self):
        """The conformance spec's ceiling happens to equal the module's 58.

        So no fixture-based case can tell a hard-coded ceiling from a spec-read one: both
        agree everywhere. A spec with a DIFFERENT ceiling is the only separator, and
        without it a producer that reached for rules.CEILING_MIN passed every test.
        """
        luts = [self.lut("SYN_MID", 12)]
        lenient = producer.build_report(
            self.spec_from(luts, ceiling_min=50, cap=1), "conformance", "lenient", self.repo
        )
        strict = producer.build_report(
            self.spec_from(luts, ceiling_min=64, cap=1), "conformance", "strict", self.repo
        )
        self.assertEqual(lenient["status"], "complete")
        self.assertEqual(strict["status"], "exhausted")
        self.assertNotEqual(rules.CEILING_MIN, 50)
        self.assertNotEqual(rules.CEILING_MIN, 64)

    def test_totals_count_only_selected_luts_when_both_kinds_are_present(self):
        """One selected LUT and one exhausted one — the case a single-LUT spec cannot show.

        With only an exhausted LUT, summing over all records and summing over selected
        records both give 0, so the two implementations are indistinguishable.
        """
        luts = [self.lut("SYN_EASY", 0), self.lut("SYN_IMPOSSIBLE", 40)]
        report = producer.build_report(self.spec_from(luts, cap=2), "conformance", "mixed", self.repo)
        self.assertEqual(report["status"], "exhausted")
        self.assertEqual(len(report["per_lut"]), 2)
        self.assertFalse(report["per_lut"][0]["exhausted"])
        self.assertTrue(report["per_lut"][1]["exhausted"])

        selected_ceiling = report["per_lut"][0]["attainable_ceiling"]
        self.assertEqual(selected_ceiling, 64)
        self.assertEqual(report["totals"]["attainable_ceiling"], selected_ceiling)
        self.assertEqual(report["totals"]["selected_luts"], 1)
        self.assertEqual(report["totals"]["reported_luts"], 2)
        self.assertEqual(report["totals"]["expected_luts"], 2)

    def test_the_seed_is_read_from_the_spec(self):
        spec = copy.deepcopy(load(CONF_SPEC))
        base = self.repo / "tests/fixtures" / CONF_SPEC.name
        first = producer.build_report(base, "conformance", "a", self.repo)["per_lut"][0]
        spec["vectors"]["seed"] = "0x0002"
        path = commit_spec(self.repo, spec, "reseeded.json")
        second = producer.build_report(path, "conformance", "b", self.repo)["per_lut"][0]
        self.assertNotEqual(first["target_truth_table"], second["target_truth_table"])


class ProfileGuardTests(unittest.TestCase):
    """The production spec file is never touched here — only its spec_id, synthetically."""

    def test_profile_must_be_one_of_two(self):
        with self.assertRaises(producer.ReportError):
            producer.check_profile("whatever", "anything")

    def test_conformance_profile_refuses_the_production_spec_id(self):
        with self.assertRaises(producer.ReportError) as ctx:
            producer.check_profile("conformance", producer.PRODUCTION_SPEC_ID)
        self.assertIn("needs its own authorisation", str(ctx.exception))

    def test_production_profile_refuses_a_non_production_spec_id(self):
        with self.assertRaises(producer.ReportError) as ctx:
            producer.check_profile("production", "consumer_reachability_conformance_v1")
        self.assertIn("not 'claimb_round1_reachability_v1'", str(ctx.exception))

    def test_matching_pairs_are_accepted(self):
        producer.check_profile("conformance", "consumer_reachability_conformance_v1")
        producer.check_profile("production", producer.PRODUCTION_SPEC_ID)

    def test_a_synthetic_spec_bearing_the_production_id_is_refused_under_conformance(self):
        repo = scratch_repo(self.addCleanup)
        spec = copy.deepcopy(load(CONF_SPEC))
        spec["spec_id"] = producer.PRODUCTION_SPEC_ID
        path = commit_spec(repo, spec, "wears_production_id.json")
        with self.assertRaises(producer.ReportError) as ctx:
            producer.build_report(path, "conformance", "x", repo)
        self.assertIn("needs its own authorisation", str(ctx.exception))

    def test_there_is_no_default_profile(self):
        source = (REPO_ROOT / "scripts/gate_reachability_report.py").read_text()
        block = source[source.index('"--profile"'): source.index('"--report-id"')]
        self.assertIn("required=True", block)
        self.assertNotIn("default=", block)


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.repo = scratch_repo(self.addCleanup)

    def spec_with(self, mutate, name="mutated.json") -> Path:
        spec = copy.deepcopy(load(CONF_SPEC))
        mutate(spec)
        return commit_spec(self.repo, spec, name)

    def test_refuses_a_spec_without_the_per_lut_scope(self):
        """The review v4 blocker is unreachable — the consumer's contract refuses first.

        The producer used to carry its own scope guard; with the preflight it can never
        run, because `spec_contract` rejects the spec before the producer looks at it. The
        rule is the consumer's, which is where it belongs.
        """
        path = self.spec_with(lambda s: s["ceiling"].__setitem__("scope", "any_of_six"),
                              "scope.json")
        with self.assertRaises(producer.ReportError) as ctx:
            producer.build_report(path, "conformance", "x", self.repo)
        self.assertIn("ceiling.scope is not per_lut", str(ctx.exception))

    def test_refuses_a_spec_with_no_luts(self):
        path = self.spec_with(lambda s: with_luts(s, []), "empty.json")
        with self.assertRaises(producer.ReportError):
            producer.build_report(path, "conformance", "x", self.repo)

    def test_refuses_a_spec_outside_the_repository(self):
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / "spec.json"
            path.write_text(CONF_SPEC.read_text(), encoding="utf-8")
            with self.assertRaises(producer.ReportError) as ctx:
                producer.build_report(path, "conformance", "x", self.repo)
        self.assertIn("outside the repository", str(ctx.exception))

    def test_a_foreign_document_is_refused_by_the_consumer_contract(self):
        """`schema` is checked by the consumer's spec_contract, in the preflight."""
        path = self.spec_with(lambda s: s.__setitem__("schema", "something_else"),
                              "foreign.json")
        with self.assertRaises(producer.ReportError) as ctx:
            producer.build_report(path, "conformance", "x", self.repo)
        self.assertIn("spec contract refuses", str(ctx.exception))

    def test_an_uncommitted_spec_is_refused_before_anything_is_written(self):
        """Now caught by the preflight, so no candidate is ever created at all."""
        spec = self.repo / "tests/fixtures" / CONF_SPEC.name
        edited = json.loads(spec.read_text())
        edited["report_note"] = "uncommitted"
        spec.write_text(json.dumps(edited, indent=2) + "\n", encoding="utf-8")

        out = self.repo / "report.json"
        with self.assertRaises(producer.ReportError) as ctx:
            producer.emit(spec, "conformance", "x", out, repo=self.repo)
        self.assertIn("differs from HEAD", str(ctx.exception))
        self.assertFalse(out.exists())
        self.assertFalse(out.with_suffix(out.suffix + ".candidate").exists())


class EmissionTests(unittest.TestCase):
    def test_emit_writes_only_after_the_consumer_accepts(self):
        repo = scratch_repo(self.addCleanup)
        spec = repo / "tests/fixtures" / CONF_SPEC.name
        out = repo / "report.json"
        producer.emit(spec, "conformance", "smoke", out, repo=repo)
        self.assertTrue(out.exists())
        self.assertEqual(consumer.verify_path(out, repo, require_production=False), [])
        self.assertFalse(out.with_suffix(out.suffix + ".candidate").exists())

    def test_the_repo_is_a_function_parameter_and_not_a_cli_flag(self):
        """Tests may construct authority; a command line may not point at another repo."""
        source = (REPO_ROOT / "scripts/gate_reachability_report.py").read_text()
        self.assertIn("repo: Path = REPO_ROOT", source)
        self.assertNotIn('"--repo"', source)


class CliSurfaceTests(unittest.TestCase):
    """No skip-authority or alternate-authority option may exist. review v6 blocker 1."""

    def options(self) -> set[str]:
        import ast

        source = (REPO_ROOT / "scripts/gate_reachability_report.py").read_text()
        tree = ast.parse(source)
        found = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "attr", "") != "add_argument":
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found.add(arg.value)
        return found

    def test_the_option_set_is_exactly_the_four_required(self):
        self.assertEqual(
            self.options(), {"--spec", "--profile", "--report-id", "--out"}
        )

    def test_no_bypass_option_of_any_spelling(self):
        for banned in (
            "--no-verify", "--skip-verify", "--allow", "--force", "--repo",
            "--unverified", "--draft", "--no-gate",
        ):
            self.assertNotIn(banned, self.options())

    def test_emit_has_no_verify_parameter(self):
        import inspect

        self.assertNotIn("verify", inspect.signature(producer.emit).parameters)

    def test_the_cli_help_advertises_no_bypass(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/gate_reachability_report.py"), "--help"],
            capture_output=True, text=True, check=True,
        )
        self.assertNotIn("--no-verify", result.stdout)
        self.assertNotIn("without the consumer gate", result.stdout)


class PreflightOrderTests(unittest.TestCase):
    """review v6 blocker 2: authority is judged BEFORE the frozen rules run.

    Each case patches `select_targets` and asserts it was never reached. A producer that
    checked authority only afterwards would execute a whole target stream and only then
    discover it had read an uncommitted, mis-pathed or malformed spec — and a malformed
    one would raise a bare TypeError out of the frozen helpers instead of refusing.
    """

    def setUp(self):
        self.repo = scratch_repo(self.addCleanup)
        self.spec = self.repo / "tests/fixtures" / CONF_SPEC.name

    def assert_refuses_without_selecting(self, spec_path, profile="conformance"):
        import unittest.mock

        with unittest.mock.patch.object(
            producer.rules, "select_targets",
            side_effect=AssertionError("select_targets must not be reached"),
        ) as patched:
            with self.assertRaises(producer.ReportError) as ctx:
                producer.build_report(spec_path, profile, "x", self.repo)
        patched.assert_not_called()
        return str(ctx.exception)

    def test_an_uncommitted_spec_never_reaches_selection(self):
        edited = json.loads(self.spec.read_text())
        edited["note"] = "uncommitted"
        self.spec.write_text(json.dumps(edited, indent=2) + "\n", encoding="utf-8")
        self.assertIn("differs from HEAD", self.assert_refuses_without_selecting(self.spec))

    def test_a_production_profile_at_a_non_canonical_path_never_reaches_selection(self):
        message = self.assert_refuses_without_selecting(self.spec, profile="production")
        self.assertIn("specs/reachability_spec_v1.json", message)

    def test_a_synthetic_spec_wearing_the_production_id_never_reaches_selection(self):
        spec = json.loads(self.spec.read_text())
        spec["spec_id"] = producer.PRODUCTION_SPEC_ID
        self.spec.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "renamed"],
                       check=True, capture_output=True)
        self.assert_refuses_without_selecting(self.spec)

    def test_a_malformed_spec_refuses_instead_of_raising(self):
        """A string where a number belongs would blow up inside the frozen helpers."""
        spec = json.loads(self.spec.read_text())
        spec["ceiling"]["minimum_accepted"] = "fifty-eight"
        self.spec.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "malformed"],
                       check=True, capture_output=True)
        self.assert_refuses_without_selecting(self.spec)

    def test_a_production_spec_with_the_wrong_lut_count_never_reaches_selection(self):
        """A spec at the canonical path, wearing the production id, with two LUTs.

        The six-LUT requirement was unreachable by every earlier case: production always
        failed the path check first, so no test ever got far enough to exercise it. This
        builds the whole production shape in a throwaway repo — the real
        specs/reachability_spec_v1.json is never read.
        """
        spec = copy.deepcopy(load(CONF_SPEC))
        spec["spec_id"] = producer.PRODUCTION_SPEC_ID
        (self.repo / "specs").mkdir(exist_ok=True)
        path = self.repo / "specs/reachability_spec_v1.json"
        path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "prodshape"],
                       check=True, capture_output=True)

        message = self.assert_refuses_without_selecting(path, profile="production")
        self.assertIn("six LUTs", message)
        self.assertIn("not 2", message)

    def test_a_spec_absent_from_head_never_reaches_selection(self):
        loose = self.repo / "tests/fixtures/not_committed.json"
        shutil.copy(CONF_SPEC, loose)
        self.assertIn("absent from HEAD", self.assert_refuses_without_selecting(loose))


class ExclusivePublicationTests(unittest.TestCase):
    """review v6 blocker 3: never overwrite, and never leave a candidate behind."""

    def setUp(self):
        self.repo = scratch_repo(self.addCleanup)
        self.spec = self.repo / "tests/fixtures" / CONF_SPEC.name
        self.out = self.repo / "report.json"

    def test_an_existing_output_is_refused_and_left_untouched(self):
        self.out.write_text("SENTINEL", encoding="utf-8")
        with self.assertRaises(producer.ReportError) as ctx:
            producer.emit(self.spec, "conformance", "x", self.out, repo=self.repo)
        self.assertIn("will not be overwritten", str(ctx.exception))
        self.assertEqual(self.out.read_text(), "SENTINEL")

    def test_an_existing_candidate_is_refused(self):
        candidate = self.out.with_suffix(self.out.suffix + ".candidate")
        candidate.write_text("LEFTOVER", encoding="utf-8")
        with self.assertRaises(producer.ReportError):
            producer.emit(self.spec, "conformance", "x", self.out, repo=self.repo)
        self.assertEqual(candidate.read_text(), "LEFTOVER")
        self.assertFalse(self.out.exists())

    def test_a_raising_verifier_leaves_no_candidate(self):
        import unittest.mock

        with unittest.mock.patch.object(
            producer.consumer, "verify_path", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(producer.ReportError) as ctx:
                producer.emit(self.spec, "conformance", "x", self.out, repo=self.repo)
        self.assertIn("RuntimeError", str(ctx.exception))
        self.assertFalse(self.out.exists())
        self.assertFalse(
            self.out.with_suffix(self.out.suffix + ".candidate").exists()
        )

    def test_a_rejecting_verifier_leaves_no_candidate(self):
        import unittest.mock

        with unittest.mock.patch.object(
            producer.consumer, "verify_path", return_value=["synthetic finding"]
        ):
            with self.assertRaises(producer.ReportError):
                producer.emit(self.spec, "conformance", "x", self.out, repo=self.repo)
        self.assertFalse(self.out.exists())
        self.assertFalse(
            self.out.with_suffix(self.out.suffix + ".candidate").exists()
        )

    def test_a_second_emission_to_the_same_path_is_refused(self):
        producer.emit(self.spec, "conformance", "first", self.out, repo=self.repo)
        first = self.out.read_text()
        with self.assertRaises(producer.ReportError):
            producer.emit(self.spec, "conformance", "second", self.out, repo=self.repo)
        self.assertEqual(self.out.read_text(), first)

    def test_this_suite_only_ever_feeds_the_conformance_fixture(self):
        """A standing check, over what is actually checkable.

        Two earlier attempts measured the wrong thing: the first asserted the production
        spec path appears nowhere in the file and tripped on its own module docstring; the
        second scanned string literals and tripped on the assertion's own argument. A
        check that fails on the sentence describing it is not a check. What can be
        verified is where the fixtures point and what profile the emitting calls use.
        """
        import ast

        for constant in (CONF_SPEC, CONF_REPORT):
            self.assertTrue(
                constant.is_relative_to(REPO_ROOT / "tests/fixtures"),
                f"{constant} is not a fixture",
            )

        tree = ast.parse(Path(__file__).read_text())
        emitting = {"build_report", "emit"}
        checked = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name not in emitting:
                continue
            checked += 1
            args = [a.value for a in node.args if isinstance(a, ast.Constant)]
            self.assertNotIn(
                "production", args, f"{name}() is called with the production profile"
            )
        self.assertGreater(checked, 0, "no emitting call was inspected")


if __name__ == "__main__":
    unittest.main()
