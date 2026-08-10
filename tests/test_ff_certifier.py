"""`gate_certify_ff.py` emits certificate 1.6, or emits nothing.

The oracle here is deliberately not mine. Every bundle is built with the **consumer's own**
`Feature16Bundle` — the same synthetic staging + attestations `tests/test_round11.py` uses
to prove its 1.6 rules — and the acceptance test is that `host/verify_certificate.py
--require-production` accepts what my certifier emits from a measurement of it. A
producer-side imitation of the consumer's rules would prove only that I agree with myself.

What is being falsified:

* **1.6.0 or nothing.** A 1.4 or 1.5 measurement is refused even when internally perfect,
  because "internally perfect" is exactly what it will always look like: those records
  were produced by a tool that built its own artifact paths and copied attestations, and
  no field inside one reveals that.
* **the staging reference is copied, not rebuilt.** Certificate 1.6 compares the
  certificate's per-specimen attestation reference with the staging entry for equality, so
  anything this gate normalises or re-derives is rejected one layer later.
* **nothing invalid reaches the disk.** The candidate is verified before it is put in
  place; a rejected one leaves no file at all, not even a draft.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT))

import test_round11 as consumer  # noqa: E402  — the consumer's own fixture builder

PYTHON = sys.executable
CERTIFIER = REPO_ROOT / "scripts/gate_certify_ff.py"
MEASUREMENT_VERSION = "1.6.0"


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


class Bundle:
    """A consumer-clean 1.6 staging, plus the measurement my certifier consumes.

    The measurement is *inverted* out of the consumer's passing certificate rather than
    invented: results, accounting and specimen identity are what a real `gate_measure_ff`
    1.6 run would have written for this bundle, so the certifier is exercised on the shape
    it will actually meet.
    """

    def __init__(self, case: unittest.TestCase,
                 semantic_pointer: str | None = None) -> None:
        (REPO_ROOT / "build").mkdir(exist_ok=True)
        scratch = tempfile.TemporaryDirectory(dir=REPO_ROOT / "build")
        case.addCleanup(scratch.cleanup)

        # The consumer's predictions fixture predates `build_seed` in the specimen plan;
        # the real commitment has it and 1.6 verification reads it off both the plan and
        # the stamp, so it is added here rather than weakening the certifier's check.
        predictions = consumer.load(consumer.PREDICTIONS15)
        for specimen in predictions["specimens"]:
            specimen["build_seed"] = 1
        prepared = Path(scratch.name) / "predictions_with_build_seed.json"
        prepared.write_bytes(consumer.encoded(predictions))

        run_id = json.loads(consumer.CERTIFICATE15.read_text())[
            "prediction_commitment"]["run_id"]
        self.run = Path(scratch.name) / run_id
        # The consumer's fixture recipe is a `.txt` stand-in; the real one pins the
        # specimen Verilog, which is where `design_source_sha256` comes from under a 2.0
        # attestation. Pointing it at the real design keeps that path exercised.
        with unittest.mock.patch.object(consumer, "PREDICTIONS15", prepared), \
                unittest.mock.patch.object(
                    consumer, "FIXTURE_RECIPE",
                    REPO_ROOT / "vivado/specimen/specimen_ff_formal.v"):
            self.bundle = consumer.Feature16Bundle(self.run, semantic_pointer)
        self.certificate = self.bundle.certificate
        self.plan = json.loads((self.run / "predictions.json").read_text())
        self.entries = {entry["specimen_id"]: entry
                        for entry in self.bundle.manifest["specimens"]}
        self.measurement = self.invert()
        self.write_measurement()
        self.out = self.run / "emitted.json"

    # -- inversion -----------------------------------------------------------------
    def invert(self) -> dict:
        committed = {item["specimen_id"]: item for item in self.plan["specimens"]}
        specimens = []
        for specimen in self.certificate["specimens"]:
            specimen_id = specimen["specimen_id"]
            entry = self.entries[specimen_id]
            recipe = self.bundle.attestations[specimen_id]["source_build"]["recipe"]
            specimens.append({
                "specimen_id": specimen_id,
                "split": committed[specimen_id]["split"],
                "variant": committed[specimen_id]["variant"],
                "loc_site": specimen["loc_site"],
                "tile": specimen["tile"],
                "tile_type": specimen["tile_type"],
                "tile_frame_base": specimen["tile_frame_base"],
                "build_seed": committed[specimen_id]["build_seed"],
                "part": recipe["part"],
                "vivado_version": recipe["vivado_version"],
                "design_source_sha256": next(
                    value for name, value in sorted(recipe["sources"].items())
                    if name.endswith(".v")),
                "bitstream": copy.deepcopy(entry["bitstream"]),
                "bitstream_sha256": entry["bitstream"]["sha256"],
                "attestation": copy.deepcopy(entry["attestation"]),
            })
        holdout = sum(1 for result in self.certificate["feature_results"]
                      if result["split"] == "holdout")
        return {
            "schema": "gate_measurement",
            "schema_version": MEASUREMENT_VERSION,
            "bit_class": "clb_ff_config",
            "staging_manifest": copy.deepcopy(self.certificate["staging_manifest"]),
            "prediction_commitment": copy.deepcopy(
                self.certificate["prediction_commitment"]),
            "split_policy": self.plan["split_policy"],
            "specimens": specimens,
            "totals": {
                "mine": {"tp": 0, "fn": 0, "fp": 0,
                         "member_identity": {"pass": 0, "fail": 0}},
                "holdout": {"tp": holdout, "fn": 0, "fp": 0,
                            "member_identity": {"pass": holdout, "fail": 0}},
            },
            "results": copy.deepcopy(self.certificate["feature_results"]),
            "accounting": [dict(copy.deepcopy(record), false_positive_addresses=[])
                           for record in self.certificate["pair_accounting"]],
            "decision": "PASS",
            "semantic_decision": "PASS",
            "address_problems": [],
            "semantic_findings": [],
        }

    # -- handles -------------------------------------------------------------------
    def write_measurement(self) -> None:
        (self.run / "measurement.json").write_text(
            json.dumps(self.measurement, indent=2) + "\n")

    def certify(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, str(CERTIFIER), "--run", str(self.run), "--out", str(self.out)],
            cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False)

    def emitted(self) -> dict:
        return json.loads(self.out.read_text())

    def refuses(self, case: unittest.TestCase, text: str) -> str:
        checked = self.certify()
        case.assertNotEqual(checked.returncode, 0, checked.stdout)
        case.assertIn(text, checked.stdout)
        case.assertFalse(self.out.exists(), "a refused run wrote a certificate")
        case.assertFalse(self.out.with_name(self.out.name + ".candidate").exists(),
                         "a refused run left its candidate behind")
        return checked.stdout


class CertifierTests(unittest.TestCase):
    def bundle(self, semantic_pointer: str | None = None) -> Bundle:
        return Bundle(self, semantic_pointer)

    # -- the known answer ----------------------------------------------------------

    def test_a_clean_16_run_certifies_and_the_consumer_accepts_it(self) -> None:
        bundle = self.bundle()
        checked = bundle.certify()
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertIn("verified by host/verify_certificate.py", checked.stdout)

        emitted = bundle.emitted()
        self.assertEqual(emitted["schema_version"], "1.6.0")
        self.assertEqual(emitted["profile"], "production")
        self.assertEqual(emitted["status"], "passed")

        # and it verifies as the consumer will run it, from a second invocation that
        # knows nothing about how it was produced
        verified = consumer.run(bundle.out, "--require-production")
        self.assertEqual(verified.returncode, 0, verified.stdout)

    def test_the_staging_reference_is_the_measurements_object_verbatim(self) -> None:
        bundle = self.bundle()
        self.assertEqual(bundle.certify().returncode, 0)
        emitted = bundle.emitted()
        self.assertEqual(emitted["staging_manifest"],
                         bundle.measurement["staging_manifest"])
        self.assertEqual(set(emitted["staging_manifest"]),
                         {"path", "sha256", "schema_version"})
        for specimen in emitted["specimens"]:
            entry = bundle.entries[specimen["specimen_id"]]
            self.assertEqual(specimen["attestation"], entry["attestation"])
            self.assertEqual(specimen["bitstream_sha256"], entry["bitstream"]["sha256"])

    def test_a_reference_the_certificate_cannot_represent_is_refused_not_trimmed(self) -> None:
        """The difference between copying and rebuilding, made observable.

        A gate that reconstructs the reference from the fields it knows would silently
        drop this one and emit a clean certificate. Copying it verbatim carries it to the
        verifier, which refuses — and refusing is right: the measurement recorded
        something the certificate has no way to express, and normalising that away is a
        producer deciding what evidence means.
        """
        bundle = self.bundle()
        bundle.measurement["staging_manifest"]["note"] = "staged by hand"
        bundle.write_measurement()
        message = bundle.refuses(self, "the production verifier rejects")
        self.assertIn("staging_manifest", message)

    def test_the_tool_versions_name_what_actually_produced_the_record(self) -> None:
        bundle = self.bundle()
        self.assertEqual(bundle.certify().returncode, 0)
        versions = bundle.emitted()["gate_run"]["tool_versions"]
        self.assertEqual(versions["gate"], "gate_measure_ff.py/1.6.0")
        self.assertEqual(versions["certifier"], "gate_certify_ff.py/1.6.0")

    # -- 1.6.0 or nothing ----------------------------------------------------------

    def test_an_older_measurement_is_refused_however_consistent_it_is(self) -> None:
        for version in ("1.4.0", "1.5.0"):
            with self.subTest(version=version):
                bundle = self.bundle()
                bundle.measurement["schema_version"] = version
                bundle.write_measurement()
                message = bundle.refuses(self, f"measurement is schema_version {version!r}")
                self.assertIn("refused even when internally consistent", message)

    def test_a_record_that_is_not_a_measurement_is_refused(self) -> None:
        bundle = self.bundle()
        bundle.measurement["schema"] = "gate_something_else"
        bundle.write_measurement()
        bundle.refuses(self, "is not a gate_measurement record")

    # -- the staging manifest ------------------------------------------------------

    def test_a_measurement_without_a_staging_manifest_is_refused(self) -> None:
        bundle = self.bundle()
        del bundle.measurement["staging_manifest"]
        bundle.write_measurement()
        bundle.refuses(self, "carries no staging_manifest")

    def test_a_manifest_that_moved_since_the_measurement_is_refused(self) -> None:
        bundle = self.bundle()
        path = REPO_ROOT / bundle.measurement["staging_manifest"]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        bundle.refuses(self, "does not match the hash the measurement pins")

    def test_a_manifest_that_is_not_a_manifest_is_refused(self) -> None:
        """Re-validated here, not taken on the measurement's word."""
        bundle = self.bundle()
        manifest = copy.deepcopy(bundle.bundle.manifest)
        manifest.pop("complete")
        path = REPO_ROOT / bundle.measurement["staging_manifest"]["path"]
        payload = consumer.encoded(manifest)
        path.write_bytes(payload)
        bundle.measurement["staging_manifest"]["sha256"] = consumer.digest(payload)
        bundle.write_measurement()
        bundle.refuses(self, "staging manifest does not validate")

    def test_a_manifest_for_another_run_is_refused(self) -> None:
        bundle = self.bundle()
        manifest = copy.deepcopy(bundle.bundle.manifest)
        manifest["run_id"] = "some_other_run"
        path = REPO_ROOT / bundle.measurement["staging_manifest"]["path"]
        payload = consumer.encoded(manifest)
        path.write_bytes(payload)
        bundle.measurement["staging_manifest"]["sha256"] = consumer.digest(payload)
        bundle.write_measurement()
        bundle.refuses(self, "staging manifest names run")

    def test_a_manifest_and_measurement_disagreeing_on_the_commitment_is_refused(self) -> None:
        bundle = self.bundle()
        manifest = copy.deepcopy(bundle.bundle.manifest)
        manifest["prediction_commitment"]["seed"] = "another-seed"
        path = REPO_ROOT / bundle.measurement["staging_manifest"]["path"]
        payload = consumer.encoded(manifest)
        path.write_bytes(payload)
        bundle.measurement["staging_manifest"]["sha256"] = consumer.digest(payload)
        bundle.write_measurement()
        bundle.refuses(self, "disagree about the prediction commitment")

    # -- the commitment, recomputed rather than believed ---------------------------

    def test_a_measurement_pinning_another_commitment_is_refused(self) -> None:
        for field, value in (("sha256", "0" * 64), ("run_id", "another_run"),
                             ("seed", "another-seed")):
            with self.subTest(field=field):
                bundle = self.bundle()
                bundle.measurement["prediction_commitment"][field] = value
                bundle.write_measurement()
                bundle.refuses(self, "prediction_commitment")

    def test_a_measurement_pinning_another_predictions_file_is_refused(self) -> None:
        bundle = self.bundle()
        twin = bundle.run / "twin.json"
        twin.write_bytes((bundle.run / "predictions.json").read_bytes())
        bundle.measurement["prediction_commitment"]["path"] = str(
            twin.resolve().relative_to(REPO_ROOT))
        bundle.write_measurement()
        bundle.refuses(self, "pins a different predictions.json")

    # -- the specimen set ----------------------------------------------------------

    def test_a_measured_set_smaller_than_the_staging_is_refused(self) -> None:
        bundle = self.bundle()
        bundle.measurement["specimens"].pop()
        bundle.write_measurement()
        message = bundle.refuses(self, "differ from the staging manifest")
        self.assertIn("differ from the commitment", message)

    def test_a_specimen_the_commitment_never_named_is_refused(self) -> None:
        bundle = self.bundle()
        extra = copy.deepcopy(bundle.measurement["specimens"][0])
        extra["specimen_id"] = "fixture_not_committed"
        bundle.measurement["specimens"].append(extra)
        bundle.write_measurement()
        bundle.refuses(self, "differ from the staging manifest")

    def test_a_reference_that_is_not_the_staging_entry_verbatim_is_refused(self) -> None:
        """Adding a field keeps every value true and still breaks the equality the
        verifier performs — which is the whole reason this is checked here."""
        bundle = self.bundle()
        bundle.measurement["specimens"][0]["attestation"]["profile"] = "ff_formal"
        bundle.write_measurement()
        bundle.refuses(self, "attestation reference is not the staging entry verbatim")

    def test_a_bitstream_reference_that_drifted_from_the_staging_is_refused(self) -> None:
        bundle = self.bundle()
        bundle.measurement["specimens"][0]["bitstream"]["path"] = "staging/elsewhere/spec.bit"
        bundle.write_measurement()
        bundle.refuses(self, "bitstream reference is not the staging entry verbatim")

    def test_a_specimen_identity_that_differs_from_the_commitment_is_refused(self) -> None:
        for field, value in (("loc_site", "SLICE_X9Y9"), ("tile", "CLBLL_L_X9Y9"),
                             ("build_seed", 99), ("split", "mine")):
            with self.subTest(field=field):
                bundle = self.bundle()
                bundle.measurement["specimens"][0][field] = value
                bundle.write_measurement()
                bundle.refuses(self, f"{field} is")

    # -- nothing invalid reaches the disk ------------------------------------------

    def test_a_candidate_the_consumer_would_reject_is_never_written(self) -> None:
        """The staged bitstream is corrupted after the measurement, so the record is
        internally consistent and externally false — exactly what the pre-emission
        verification exists to catch."""
        bundle = self.bundle()
        staged = REPO_ROOT / bundle.entries[
            bundle.measurement["specimens"][0]["specimen_id"]]["bitstream"]["path"]
        staged.write_bytes(b"corrupted after measurement\n")
        message = bundle.refuses(self, "the production verifier rejects this certificate")
        self.assertIn("hash mismatch", message)

    # -- semantic isolation, re-established on a 1.6 record ------------------------

    def test_a_semantic_only_failure_still_certifies_as_address_passed(self) -> None:
        """A real one, not a fabricated flag: the assertion is pointed at a field whose
        attested value differs from the preregistered one, so the consumer rebuilds the
        same `passed: false` and accepts the record. What must not happen is the naming
        claim reaching the address decision."""
        bundle = self.bundle(semantic_pointer="/resolved/ce_mode")
        for result in bundle.measurement["results"]:
            result["semantic_outcome"]["passed"] = False
            result["semantic_outcome"]["observed_value"] = "DRIVEN"
        bundle.measurement["totals"]["holdout"]["member_identity"] = {"pass": 0, "fail": 2}
        bundle.measurement["semantic_decision"] = "FAIL"
        bundle.measurement["semantic_findings"] = ["the attested ce_mode is not the "
                                                   "preregistered member"]
        bundle.write_measurement()
        checked = bundle.certify()
        self.assertEqual(checked.returncode, 0, checked.stdout)
        emitted = bundle.emitted()
        self.assertEqual(emitted["status"], "passed")
        self.assertEqual(emitted["semantic_status"], "failed")
        self.assertEqual(emitted["failure_reasons"], [])
        self.assertEqual(emitted["bit_class"]["semantic_accounting"]["member_identity"],
                         {"pass_count": 0, "fail_count": 2})
        self.assertEqual(consumer.run(bundle.out, "--require-production").returncode, 0)

    def test_an_address_problem_fails_the_certificate(self) -> None:
        bundle = self.bundle()
        bundle.measurement["address_problems"] = ["synthetic address problem"]
        bundle.write_measurement()
        checked = bundle.certify()
        if checked.returncode == 0:
            self.assertEqual(bundle.emitted()["status"], "failed")
            self.assertIn("holdout_false_negative",
                          json.dumps(bundle.emitted()["failure_reasons"]))
        else:
            # a failed certificate the consumer will not accept is still not written
            self.assertFalse(bundle.out.exists())


if __name__ == "__main__":
    unittest.main()
