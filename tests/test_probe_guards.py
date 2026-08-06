"""The probe's own decision functions, which have twice been where a bug hid.

Neither needs Vivado, git history or an artifact, so both run on a cold checkout:

* `check_scope` is what stops a sacrificial probe from writing into one of the
  commitment's 24 role sites;
* `empty_route` is what decides whether an INTRASITE net "carries a route". Vivado prints
  an empty route as the empty Tcl list `{}`, and a truthiness test on that string called
  every pad net a routed one — 18 fabricated problems in a run whose five criteria had
  actually all passed.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import gate_build_ff_formal as builder  # noqa: E402
import probe_sacrificial_site as probe  # noqa: E402


class EmptyRouteTests(unittest.TestCase):
    def test_vivados_empty_route_spellings_are_empty(self) -> None:
        for value in ("{}", " {} ", "", "   ", None, "{ }"):
            with self.subTest(value=value):
                self.assertTrue(probe.empty_route(value))

    def test_a_real_route_is_not_empty(self) -> None:
        for value in ("{ CLBLL_L_A CLBLL_LOGIC_OUTS8 }", "{ NL1BEG_N3 IMUX13 }"):
            with self.subTest(value=value):
                self.assertFalse(probe.empty_route(value))

    def test_the_string_braces_alone_do_not_make_a_route(self) -> None:
        """The original bug in one line: `bool("{}")` is True."""
        self.assertTrue(bool("{}"))
        self.assertTrue(probe.empty_route("{}"))


class ScopeRefusalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.roles = builder.sites_for(probe.TARGET)

    def test_the_declared_probe_scope_is_accepted(self) -> None:
        scope = probe.check_scope(self.roles, probe.CONGEST_SITES)
        self.assertEqual(len(scope["committed_sites"]), 24)
        for role in ("target", "anchor", "keeper"):
            self.assertEqual(scope["probe_roles"][role]["tile_type"], "CLBLM_R")
            self.assertEqual(scope["probe_roles"][role]["site_type"], "SLICEL")

    def test_no_probe_site_is_a_committed_site(self) -> None:
        scope = probe.check_scope(self.roles, probe.CONGEST_SITES)
        committed = set(scope["committed_sites"])
        for site in list(self.roles.values()) + list(probe.CONGEST_SITES):
            with self.subTest(site=site):
                self.assertNotIn(site, committed)

    def test_a_committed_role_site_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            probe.check_scope({"target": "SLICE_X31Y25", "anchor": "SLICE_X33Y20",
                               "keeper": "SLICE_X2Y20"}, [])
        self.assertIn("would touch committed sites", str(caught.exception))

    def test_a_committed_congestion_site_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            probe.check_scope(self.roles, [*probe.CONGEST_SITES, "SLICE_X2Y25"])
        self.assertIn("SLICE_X2Y25", str(caught.exception))

    def test_roles_that_do_not_follow_the_site_rule_are_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            probe.check_scope({"target": "SLICE_X31Y25", "anchor": "SLICE_X35Y20",
                               "keeper": "SLICE_X31Y20"}, [])
        self.assertIn("not what the site rule", str(caught.exception))

    def test_a_site_absent_from_the_freeze_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            probe.check_scope(self.roles, ["SLICE_X999Y999"])
        self.assertIn("absent from the freeze", str(caught.exception))



class MatrixCompletenessTests(unittest.TestCase):
    """A verdict over whatever happens to be on disk is how a run that lost a build
    reports one route set and passes. Driven from the versioned evidence, so it needs no
    Vivado — the snapshots are the same bytes the run produced."""

    EVIDENCE = REPO_ROOT / "evidence/ff_route_pin_sacrificial_2026_08_06"

    def populate(self, root: Path, skip: str | None = None) -> None:
        for label, *_rest in probe.MATRIX:
            if label == skip:
                continue
            stem = label.replace("/", "_")
            target = root / stem
            target.mkdir(parents=True)
            (target / "probe_routes.tsv").write_bytes(
                (self.EVIDENCE / f"{stem}.probe_routes.tsv").read_bytes())

    def scratch(self) -> Path:
        base = REPO_ROOT / "build"
        base.mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def test_the_complete_matrix_passes(self) -> None:
        root = self.scratch()
        self.populate(root)
        self.assertEqual(probe.verdict(root, {"probe_roles": {}}), 0)

    def test_dropping_one_passing_run_fails(self) -> None:
        """The dropped run passes on its own — the failure must come from its absence."""
        root = self.scratch()
        self.populate(root, skip="pinned/ce_tied/Default/c32")
        self.assertEqual(probe.verdict(root, {"probe_roles": {}}), 1)
        recorded = json.loads((root / "verdict.json").read_text())
        self.assertEqual(recorded["runs_present"], len(probe.MATRIX) - 1)
        self.assertTrue(any("matrix incomplete" in item
                            for item in recorded["problems"]), recorded["problems"])

    def test_evidence_refuses_to_pin_an_incomplete_set(self) -> None:
        root = self.scratch()
        self.populate(root)
        with self.assertRaises(SystemExit) as caught:
            probe.collect_evidence(root, self.scratch() / "out", {"probe_roles": {}})
        self.assertIn("evidence set is whole or it is not evidence",
                      str(caught.exception))


if __name__ == "__main__":
    unittest.main()
