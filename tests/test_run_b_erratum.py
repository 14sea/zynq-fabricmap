"""Run B's certificate was re-emitted under certificate 1.4. Nothing was re-measured.

`docs/round9_ruling.md` ruled that `group_exclusivity` is vacuous for bit-set groups and
that `decode_validity` is entailed by strict codeword equality, so the committed record's
`address_pass=32` counted one observation twice and one that could not come out false.
The corrected reading is 16 falsifiable address passes, 16 vacuous diagnostics, and
semantic 16/16.

These tests pin the two halves of that erratum:

* the **artifact** — the committed certificate carries the corrected accounting, still
  verifies as production, and its manifest index agrees with it;
* the **boundary** — every observation, prediction, hash and pair-accounting record is
  bit-identical to the archived 1.3 evidence. A recount that quietly moved a measurement
  would be a new run wearing an erratum's clothes.

The adversarial case is the point of the exercise: putting the vacuous outcome back into
`address_accounting` must be rejected, otherwise the correction is a comment rather than
a rule.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
RUN_DIR = REPO_ROOT / "gate_runs/run_2026_08_02_b"
CERTIFICATE = RUN_DIR / "certificate.json"
ARCHIVED_1_3 = REPO_ROOT / "tests/fixtures/certificate_group13_run_b.json"
MANIFEST = REPO_ROOT / "data/MANIFEST.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify(value: dict[str, Any], *arguments: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "certificate.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return subprocess.run(
            [PYTHON, "host/verify_certificate.py", str(path), *arguments],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )


def strip_recounted(value: dict[str, Any]) -> dict[str, Any]:
    """The record minus every field the 1.4 recount is permitted to rewrite."""

    value = copy.deepcopy(value)
    value.pop("schema_version")
    value["bit_class"].pop("address_accounting")
    value["bit_class"].pop("diagnostic_accounting", None)
    value["bit_class"].pop("decision_rule")
    value["gate_run"].pop("tool_versions")
    for result in value["group_results"]:
        result.pop("assertion_outcomes")
    return value


class RunBErratumTests(unittest.TestCase):
    def certificate(self) -> dict[str, Any]:
        return load(CERTIFICATE)

    def assert_fails(self, checked: subprocess.CompletedProcess[str], text: str) -> None:
        self.assertNotEqual(checked.returncode, 0, checked.stdout)
        self.assertIn(text, checked.stdout)

    def test_committed_certificate_carries_the_corrected_accounting(self) -> None:
        value = self.certificate()
        self.assertEqual(value["schema_version"], "1.4.0")
        self.assertEqual(value["evidence_model"], "group")
        self.assertEqual(
            value["bit_class"]["address_accounting"],
            {"strict_codeword_equality": {"pass_count": 16, "fail_count": 0}},
        )
        self.assertEqual(
            value["bit_class"]["diagnostic_accounting"],
            {
                "group_exclusivity": {"vacuous_count": 16, "ambiguity_count": 0},
                "decode_validity": {"pass_count": 16, "fail_count": 0},
            },
        )
        self.assertEqual(
            value["bit_class"]["semantic_accounting"],
            {"member_identity": {"pass_count": 16, "fail_count": 0}},
        )

    def test_committed_certificate_still_verifies_as_production(self) -> None:
        checked = subprocess.run(
            [PYTHON, "host/verify_certificate.py", str(CERTIFICATE), "--require-production"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("address_pass=16 address_fail=0", checked.stdout)
        self.assertIn("vacuous=16 ambiguity=0", checked.stdout)
        self.assertIn("semantic_pass=16 semantic_fail=0", checked.stdout)

    def test_no_observation_changed_between_the_two_records(self) -> None:
        self.assertEqual(strip_recounted(load(ARCHIVED_1_3)), strip_recounted(self.certificate()))

    def test_every_outcome_keeps_its_independently_decoded_members(self) -> None:
        archived = {
            (item["prediction_specimen_id"], item["group"]): item
            for item in load(ARCHIVED_1_3)["group_results"]
        }
        for result in self.certificate()["group_results"]:
            key = result["prediction_specimen_id"], result["group"]
            before = {item["kind"]: item for item in archived[key]["assertion_outcomes"]}
            after = {item["kind"]: item for item in result["assertion_outcomes"]}
            self.assertEqual(set(after) - set(before), {"decode_validity"})
            self.assertEqual(
                after["group_exclusivity"]["decoded_members"],
                before["group_exclusivity"]["decoded_members"],
            )
            self.assertEqual(after["scope_assignment"], before["scope_assignment"])
            self.assertEqual(after["member_identity"], before["member_identity"])
            self.assertNotIn("passed", after["group_exclusivity"])
            self.assertEqual(after["group_exclusivity"]["classification"], "vacuous")
            self.assertTrue(after["decode_validity"]["diagnostic"])

    def test_prediction_commitment_is_untouched(self) -> None:
        archived = load(ARCHIVED_1_3)["prediction_commitment"]
        self.assertEqual(self.certificate()["prediction_commitment"], archived)
        self.assertEqual(
            load(RUN_DIR / "measurement.json")["prediction_commitment"]["sha256"],
            archived["sha256"],
        )

    def test_vacuous_exclusivity_cannot_be_reintroduced_as_an_address_pass(self) -> None:
        value = self.certificate()
        value["bit_class"]["address_accounting"]["group_exclusivity"] = {
            "pass_count": 16,
            "fail_count": 0,
        }
        self.assert_fails(verify(value), "address_accounting mismatch")

    def test_the_old_two_assertion_accounting_is_not_expressible_at_1_4(self) -> None:
        # Reverting the whole bucket, not just adding to it, does not even reach the
        # semantic checks: 1.4 requires the falsifiable count by name.
        value = self.certificate()
        value["bit_class"]["address_accounting"] = {
            "group_exclusivity": {"pass_count": 16, "fail_count": 0},
            "scope_assignment": {"pass_count": 16, "fail_count": 0},
        }
        self.assert_fails(verify(value), "'strict_codeword_equality' is a required property")

    def test_reintroducing_the_exclusivity_verdict_is_also_rejected(self) -> None:
        # The count and the outcome shape are two doors into the same overcount, so the
        # adversarial case is only closed if both are shut. Here the accounting stays
        # correct and only the per-result outcome regresses to a 1.3-style verdict.
        value = self.certificate()
        for result in value["group_results"]:
            for outcome in result["assertion_outcomes"]:
                if outcome["kind"] == "group_exclusivity":
                    outcome.pop("classification")
                    outcome["passed"] = True
        self.assert_fails(verify(value), "vacuity outcome is wrong")

    def test_decode_validity_diagnostic_cannot_be_counted_either(self) -> None:
        value = self.certificate()
        value["bit_class"]["address_accounting"]["decode_validity"] = {
            "pass_count": 16,
            "fail_count": 0,
        }
        self.assert_fails(verify(value), "address_accounting mismatch")

    def test_manifest_index_agrees_with_the_certificate(self) -> None:
        certificate = self.certificate()
        slot = next(
            item["certification"]
            for item in load(MANIFEST)["bit_classes"]
            if item["id"] == "clb_mux"
        )
        self.assertEqual(slot["certificate_schema_version"], certificate["schema_version"])
        self.assertEqual(slot["address_accounting"], certificate["bit_class"]["address_accounting"])
        self.assertEqual(
            slot["diagnostic_accounting"], certificate["bit_class"]["diagnostic_accounting"]
        )
        self.assertEqual(
            slot["semantic_accounting"], certificate["bit_class"]["semantic_accounting"]
        )
        self.assertTrue(slot["diagnostics_are_not_address_passes"])


if __name__ == "__main__":
    unittest.main()
