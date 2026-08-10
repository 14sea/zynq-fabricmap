from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

from host.verify_certificate import ff_formal_attestation_errors, safe_child


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
CERTIFICATE15 = REPO_ROOT / "tests/fixtures/certificate_feature15_pass.json"
PREDICTIONS15 = REPO_ROOT / "tests/fixtures/predictions_feature15_pass.json"
FF_COMMITMENT = REPO_ROOT / "gate_runs/run_2026_08_05_ff/predictions.json"
FIXTURE_RECIPE = REPO_ROOT / "tests/fixtures/ff20_recipe_source.v"
NON_DESIGN_RECIPE = REPO_ROOT / "tests/fixtures/ff20_recipe_source.txt"
ALL_BELS = ("AFF", "A5FF", "BFF", "B5FF", "CFF", "C5FF", "DFF", "D5FF")
LUT_BELS = ("A6LUT", "B6LUT", "C6LUT", "D6LUT", "A5LUT", "B5LUT", "C5LUT", "D5LUT")
SUPPORT = {
    "anchor_lut1": ("anchor", "lut", "A6LUT"),
    "anchor_lut2": ("anchor", "lut", "B6LUT"),
    "q_reduce1": ("anchor", "lut", "C6LUT"),
    "q_reduce2": ("anchor", "lut", "D6LUT"),
    "anchor_ff": ("anchor", "storage", "AFF"),
    "anchor_ff2": ("keeper", "storage", "AFF"),
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def encoded(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def run(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, "host/verify_certificate.py", str(path), *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def pin(ref_name: str, loc: str, bel: str, net: str) -> dict[str, Any]:
    clock_pin = "G" if ref_name == "LDCE" else "C"
    ce_pin = "GE" if ref_name == "LDCE" else "CE"
    sr_pin = "CLR" if ref_name in {"FDCE", "LDCE"} else ("S" if ref_name == "FDSE" else "R")
    return {
        "logical_name": "",
        "logical_bel": bel,
        "role": "target",
        "kind": "storage",
        "requested": {"ref_name": ref_name, "loc": loc, "bel": bel},
        "resolved": {"ref_name": ref_name, "loc": loc, "bel": f"SLICEL.{bel}"},
        "properties": {"INIT": "1'b1", "IS_C_INVERTED": "1'b0"},
        "lock_pins": "",
        "pin_mapping": {},
        "pins": {
            clock_pin: {"net": "clk_g", "direction": "IN", "bel_pin": f"{loc}/{bel}/CK"},
            ce_pin: {"net": "ce_IBUF", "direction": "IN", "bel_pin": f"{loc}/{bel}/CE"},
            sr_pin: {"net": "rst_IBUF", "direction": "IN", "bel_pin": f"{loc}/{bel}/SR"},
            "D": {"net": net, "direction": "IN", "bel_pin": f"{loc}/{bel}/D"},
            "Q": {"net": f"q_{bel}", "direction": "OUT", "bel_pin": f"{loc}/{bel}/Q"},
        },
    }


def lut_cell(name: str, role: str, loc: str, bel: str, ref_name: str = "LUT5") -> dict[str, Any]:
    return {
        "logical_name": name,
        "logical_bel": bel,
        "role": role,
        "kind": "lut",
        "requested": {"ref_name": ref_name, "loc": loc, "bel": bel},
        "resolved": {"ref_name": ref_name, "loc": loc, "bel": f"SLICEL.{bel}"},
        "properties": {"INIT": "32'hA5A5A5A5"},
        "lock_pins": "I0:A1 I1:A2 I2:A3 I3:A4 I4:A5",
        "pin_mapping": {"I0": f"{loc}/{bel}/A1"},
        "pins": {
            "I0": {"net": "i_IBUF[0]", "direction": "IN", "bel_pin": f"{loc}/{bel}/A1"},
            "O": {"net": f"{name}_o", "direction": "OUT", "bel_pin": f"{loc}/{bel}/O6"},
        },
    }


def multi_cell_attestation(
    specimen: dict[str, Any],
    committed: dict[str, Any],
    commitment_ref: dict[str, Any],
    bit_hash: str,
    checkpoint_hash: str,
    clock_mode: str,
    *,
    derived_source: tuple[str, str] | None = None,
) -> dict[str, Any]:
    site = specimen["loc_site"]
    anchor = "SLICE_X4Y20"
    keeper = "SLICE_X2Y20"
    variant = committed["variant"].lower()
    storage_bels = ("AFF", "BFF", "CFF", "DFF") if variant in {"latch", "latch_base"} else ALL_BELS
    zrst_bel = variant.removeprefix("zrst_").upper() if variant.startswith("zrst_") else None
    zini_bel = variant.removeprefix("zini_").upper() if variant.startswith("zini_") else None
    storage = []
    for index, bel in enumerate(storage_bels):
        if variant == "latch":
            ref_name = "LDCE"
        elif variant in {"latch_base", "async"}:
            ref_name = "FDCE"
        elif bel == zrst_bel:
            ref_name = "FDSE"
        else:
            ref_name = "FDRE"
        cell = pin(ref_name, site, bel, f"target_lut_{index}_o")
        cell["logical_name"] = f"store.{index}"
        if bel == zini_bel:
            cell["properties"]["INIT"] = "1'b0"
        if ref_name != "LDCE":
            cell["properties"]["IS_C_INVERTED"] = (
                "1'b1" if variant in {"clkinv", "latch_base"} or clock_mode == "CLKINV" else "1'b0"
            )
        if variant == "ce_tied":
            cell["pins"]["CE"]["net"] = "<const1>"
        if variant == "sr_tied":
            cell["pins"]["R"]["net"] = "<const0>"
        storage.append(cell)
    luts = [lut_cell(f"target_lut_{bel}", "target", site, bel) for bel in LUT_BELS]
    support = []
    for name, (role, kind, bel) in SUPPORT.items():
        loc = keeper if role == "keeper" else anchor
        if kind == "lut":
            support.append(lut_cell(name, role, loc, bel, "LUT6"))
        else:
            cell = pin("FDRE", loc, bel, "w2")
            cell.update({"logical_name": name, "role": role})
            support.append(cell)

    source_hash = file_digest(FIXTURE_RECIPE)
    artifacts = {
        "spec.bit": bit_hash,
        "readback.tsv": digest((specimen["specimen_id"] + "-readback").encode()),
    }
    checkpoint: dict[str, Any]
    if derived_source is None:
        node_type = "implementation"
        artifacts["base.dcp"] = checkpoint_hash
        checkpoint = {
            "kind": "implementation",
            "artifact": {"file": "base.dcp", "sha256": checkpoint_hash},
        }
    else:
        node_type = "derived"
        artifacts["derived.dcp"] = checkpoint_hash
        checkpoint = {
            "kind": "derived",
            "artifact": {"file": "derived.dcp", "sha256": checkpoint_hash},
            "source": {
                "specimen_id": derived_source[0],
                "file": "base.dcp",
                "sha256": derived_source[1],
            },
        }

    source_build: dict[str, Any] = {
        "schema": "ff_formal_stamp/1",
        "node_type": node_type,
        "instance": site,
        "variant": committed["variant"],
        "attempt_id": "consumer-round11-fixture",
        "sites": {"target": site, "anchor": anchor, "keeper": keeper},
        "recipe": {
            "sources": {repo_path(FIXTURE_RECIPE): source_hash},
            "commitment": commitment_ref["sha256"],
            "preregistration_plan": "a" * 64,
            "part": specimen["part"],
            "vivado_version": specimen["vivado_version"],
            # Absolute invocation text is deliberately legal here. It is history, not
            # an artifact reference; every actual reference in the certificate is relative.
            "tclargs": ["/synthetic/build/invocation", site, committed["variant"]],
            "build_seed": specimen["build_seed"],
        },
        "completed": True,
        "artifacts": artifacts,
    }
    if derived_source is not None:
        source_build["derived_from"] = {
            "specimen_id": derived_source[0],
            "base_dcp_sha256": derived_source[1],
        }
    return {
        "schema": "specimen_attestation",
        "schema_version": "2.0.0",
        "profile": "ff_formal",
        "specimen_id": specimen["specimen_id"],
        "prediction_commitment": copy.deepcopy(commitment_ref),
        "source_build": source_build,
        "resolved": {
            "target": {
                "requested_site": site,
                "resolved_site": site,
                "tile": specimen["tile"],
                "tile_type": specimen["tile_type"],
            },
            "cells": storage + luts + support,
            "nets": {
                "w2": {
                    "driver": "anchor_lut2/O",
                    "sinks": ["anchor_ff/D", "anchor_ff2/D"],
                    "ports": [],
                    "route_status": "ROUTED",
                    "route": "synthetic route",
                    "pips": ["synthetic/pip"],
                }
            },
            "ff_init": {bel: ("0" if bel == zini_bel else "1") for bel in storage_bels},
            "ff_srval": {bel: ("1" if bel == zrst_bel else "0") for bel in storage_bels},
            "ce_mode": "TIED" if variant == "ce_tied" else "DRIVEN",
            "sr_mode": "TIED" if variant == "sr_tied" else "DRIVEN",
            "sr_kind": "ASYNC" if variant in {"async", "latch", "latch_base"} else "SYNC",
            "storage_kind": "LATCH" if variant == "latch" else "FF",
            "clock_mode": (
                "LATCH"
                if variant == "latch"
                else ("CLKINV" if variant in {"clkinv", "latch_base"} or clock_mode == "CLKINV" else "NOCLKINV")
            ),
        },
        "checkpoint": checkpoint,
        "outputs": {"spec.bit": bit_hash},
    }


def standalone_variant(variant: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Consumer-owned routed-fact fixture for one formal variant, without staging."""

    specimen_id = f"fixture_{variant}"
    bit_hash = digest((specimen_id + "-bitstream").encode())
    specimen = {
        "specimen_id": specimen_id,
        "split": "mine",
        "design_source_sha256": file_digest(FIXTURE_RECIPE),
        "vivado_version": "fixture",
        "part": "xc7z010clg400-1",
        "loc_site": "SLICE_X2Y25",
        "tile": "CLBLL_L_X2Y25",
        "tile_type": "CLBLL_L",
        "tile_frame_base": "0x00400A00",
        "build_seed": 7,
        "bitstream_sha256": bit_hash,
    }
    committed = {
        "specimen_id": specimen_id,
        "site": specimen["loc_site"],
        "variant": variant,
        "tile": specimen["tile"],
        "tile_type": specimen["tile_type"],
        "split": "mine",
    }
    commitment_ref = {
        "run_id": "consumer_round11_variant_fixture",
        "path": "tests/fixtures/predictions_feature15_pass.json",
        "sha256": "2" * 64,
        "schema_version": "1.5.0",
        "seed": "consumer-round11-variant-fixture",
        "totals": {"specimens": 1, "predictions": 1, "holdout_predictions": 1},
    }
    attestation = multi_cell_attestation(
        specimen,
        committed,
        commitment_ref,
        bit_hash,
        digest((specimen_id + "-checkpoint").encode()),
        "NOCLKINV",
    )
    return attestation, specimen, committed, commitment_ref


class Feature16Bundle:
    """Synthetic 1.6 conformance fixture with real files and recomputable hashes."""

    def __init__(self, root: Path, semantic_pointer: str | None = None) -> None:
        self.root = root
        self.stage = root / "staging"
        self.stage.mkdir(parents=True)
        self.certificate = load(CERTIFICATE15)
        self.predictions = load(PREDICTIONS15)
        self.certificate["schema_version"] = "1.6.0"
        if semantic_pointer is not None:
            for prediction in self.predictions["predictions"]:
                prediction["semantic_assertion"]["attestation_field"] = semantic_pointer
            for result in self.certificate["feature_results"]:
                result["semantic_assertion"]["attestation_field"] = semantic_pointer
                result["semantic_outcome"]["attestation_field"] = semantic_pointer

        prediction_path = root / "predictions.json"
        prediction_bytes = encoded(self.predictions)
        prediction_path.write_bytes(prediction_bytes)
        commitment_ref = self.certificate["prediction_commitment"]
        commitment_ref["path"] = repo_path(prediction_path)
        commitment_ref["sha256"] = digest(prediction_bytes)
        committed = {item["specimen_id"]: item for item in self.predictions["specimens"]}

        expected_modes = {
            result["feature_specimen_id"]: result["semantic_assertion"]["expected_value"]
            for result in self.certificate["feature_results"]
        }
        self.attestations: dict[str, dict[str, Any]] = {}
        self.manifest = {
            "schema": "specimen_staging",
            "schema_version": "1.0.0",
            "run_id": commitment_ref["run_id"],
            "prediction_commitment": copy.deepcopy(commitment_ref),
            "complete": True,
            "specimens": [],
        }
        checkpoints = {
            item["specimen_id"]: digest((item["specimen_id"] + "-checkpoint").encode())
            for item in self.certificate["specimens"]
        }
        derived_id = "fixture_ff_clkinv"
        derived_source_id = "fixture_ff_clkinv__base"
        for specimen in self.certificate["specimens"]:
            specimen_id = specimen["specimen_id"]
            specimen["design_source_sha256"] = file_digest(FIXTURE_RECIPE)
            specimen_dir = self.stage / specimen_id
            specimen_dir.mkdir()
            bit_path = specimen_dir / "spec.bit"
            bit_path.write_bytes(("synthetic bitstream " + specimen_id + "\n").encode())
            bit_hash = file_digest(bit_path)
            specimen["bitstream_sha256"] = bit_hash
            derived_source = (
                (derived_source_id, checkpoints[derived_source_id])
                if specimen_id == derived_id
                else None
            )
            attestation = multi_cell_attestation(
                specimen,
                committed[specimen_id],
                commitment_ref,
                bit_hash,
                checkpoints[specimen_id],
                expected_modes.get(specimen_id, "NOCLKINV"),
                derived_source=derived_source,
            )
            self.attestations[specimen_id] = attestation
            att_ref = self.write_attestation(specimen_id, update_manifest=False)
            specimen["attestation"] = copy.deepcopy(att_ref)
            self.manifest["specimens"].append(
                {
                    "specimen_id": specimen_id,
                    "bitstream": {"path": repo_path(bit_path), "sha256": bit_hash},
                    "attestation": copy.deepcopy(att_ref),
                }
            )
        self.write_manifest()
        self.write_certificate()

    def write_attestation(self, specimen_id: str, *, update_manifest: bool = True) -> dict[str, Any]:
        path = self.stage / specimen_id / "attestation.json"
        content = encoded(self.attestations[specimen_id])
        path.write_bytes(content)
        reference = {
            "path": repo_path(path),
            "sha256": digest(content),
            "schema_version": "2.0.0",
        }
        if update_manifest:
            next(
                item for item in self.manifest["specimens"] if item["specimen_id"] == specimen_id
            )["attestation"] = copy.deepcopy(reference)
            next(
                item for item in self.certificate["specimens"] if item["specimen_id"] == specimen_id
            )["attestation"] = copy.deepcopy(reference)
            self.write_manifest()
        return reference

    def write_manifest(self) -> None:
        path = self.root / "staging_manifest.json"
        content = encoded(self.manifest)
        path.write_bytes(content)
        self.certificate["staging_manifest"] = {
            "path": repo_path(path),
            "sha256": digest(content),
            "schema_version": "1.0.0",
        }
        self.write_certificate()

    def write_certificate(self) -> None:
        self.certificate_path = self.root / "certificate.json"
        self.certificate_path.write_bytes(encoded(self.certificate))

    def rewrite_attestation(self, specimen_id: str) -> None:
        self.write_attestation(specimen_id)


class Round11AttestationAndStagingTests(unittest.TestCase):
    def with_bundle(
        self,
        check: Callable[[Feature16Bundle], None],
        *,
        semantic_pointer: str | None = None,
    ) -> None:
        (REPO_ROOT / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "build") as directory:
            check(Feature16Bundle(Path(directory), semantic_pointer))

    def assert_fails(self, checked: subprocess.CompletedProcess[str], text: str) -> None:
        self.assertNotEqual(checked.returncode, 0, checked.stdout)
        self.assertIn(text, checked.stdout)

    def test_multicell_derived_staging_known_answer_passes(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            checked = run(bundle.certificate_path)
            self.assertEqual(checked.returncode, 0, checked.stdout)
            self.assertIn("tp=2 fp=0 fn=0", checked.stdout)
            raw_args = bundle.attestations["fixture_ff_clkinv"]["source_build"]["recipe"]["tclargs"]
            self.assertTrue(raw_args[0].startswith("/"))
            for reference in (
                bundle.certificate["prediction_commitment"],
                bundle.certificate["staging_manifest"],
                *(item["attestation"] for item in bundle.certificate["specimens"]),
            ):
                self.assertFalse(Path(reference["path"]).is_absolute())

        self.with_bundle(check)

    def test_production_ff_cannot_downgrade_to_1_5_to_omit_staging(self) -> None:
        """A version downgrade must not turn the exact staging contract off.

        Apart from the two fields that select 1.6, this is the same complete,
        self-consistent certificate as the passing known answer.  Under the old policy it
        passed as production 1.5 and the verifier never attempted to load staging at all.
        """
        def check(bundle: Feature16Bundle) -> None:
            bundle.certificate["schema_version"] = "1.5.0"
            bundle.certificate["profile"] = "production"
            bundle.certificate.pop("staging_manifest")
            bundle.write_certificate()
            checked = run(bundle.certificate_path, "--require-production")
            self.assert_fails(
                checked,
                "production clb_ff_config feature evidence requires certificate "
                "schema_version >= 1.6.0",
            )
            # This is the only finding: deleting the lower-bound rule makes this exact
            # downgraded record green, rather than merely exposing some unrelated reject.
            self.assertIn("FAIL — 1 finding(s)", checked.stdout)

        self.with_bundle(check)

    def test_non_clock_variants_rebuild_from_routed_cells(self) -> None:
        expected = {
            "latch": ("storage_kind", "LATCH"),
            "latch_base": ("clock_mode", "CLKINV"),
            "zrst_AFF": ("ff_srval", {"AFF": "1"}),
            "ce_tied": ("ce_mode", "TIED"),
            "sr_tied": ("sr_mode", "TIED"),
            "async": ("sr_kind", "ASYNC"),
        }
        for variant, (field, wanted) in expected.items():
            with self.subTest(variant=variant):
                attestation, specimen, committed, reference = standalone_variant(variant)
                errors = ff_formal_attestation_errors(
                    attestation, specimen, committed, reference, REPO_ROOT
                )
                self.assertEqual(errors, [])
                observed = attestation["resolved"][field]
                if field == "ff_srval":
                    self.assertEqual({key: observed[key] for key in wanted}, wanted)
                else:
                    self.assertEqual(observed, wanted)
                target_storage = [
                    cell
                    for cell in attestation["resolved"]["cells"]
                    if cell["role"] == "target" and cell["kind"] == "storage"
                ]
                self.assertEqual(
                    len(target_storage), 4 if variant in {"latch", "latch_base"} else 8
                )

    def test_lut_lock_pins_and_mapping_are_enforced(self) -> None:
        attestation, specimen, committed, reference = standalone_variant("async")
        target_lut = next(
            cell
            for cell in attestation["resolved"]["cells"]
            if cell["role"] == "target" and cell["kind"] == "lut"
        )
        target_lut["lock_pins"] = ""
        target_lut["pin_mapping"] = {}
        errors = ff_formal_attestation_errors(
            attestation, specimen, committed, reference, REPO_ROOT
        )
        self.assertTrue(any("lacks LOCK_PINS/pin mapping" in item for item in errors), errors)

    def test_source_stamp_bitstream_link_is_enforced(self) -> None:
        attestation, specimen, committed, reference = standalone_variant("ce_tied")
        attestation["source_build"]["artifacts"]["spec.bit"] = "f" * 64
        errors = ff_formal_attestation_errors(
            attestation, specimen, committed, reference, REPO_ROOT
        )
        self.assertTrue(any("source stamp bitstream hash differs" in item for item in errors), errors)

    def test_design_source_hash_is_recomputed_from_the_single_verilog_source(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            bundle.certificate["specimens"][0]["design_source_sha256"] = "f" * 64
            bundle.write_certificate()
            self.assert_fails(run(bundle.certificate_path), "design_source_sha256 differs")

        self.with_bundle(check)

    def test_a_recipe_without_a_verilog_design_source_is_rejected(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            specimen_id = bundle.certificate["specimens"][0]["specimen_id"]
            bundle.attestations[specimen_id]["source_build"]["recipe"]["sources"] = {
                repo_path(NON_DESIGN_RECIPE): file_digest(NON_DESIGN_RECIPE)
            }
            bundle.rewrite_attestation(specimen_id)
            self.assert_fails(
                run(bundle.certificate_path), "exactly one .v design source (found 0)"
            )

        self.with_bundle(check)

    def test_a_recipe_with_two_verilog_design_sources_is_rejected(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            specimen_id = bundle.certificate["specimens"][0]["specimen_id"]
            second = REPO_ROOT / "vivado/specimen/specimen_ff.v"
            bundle.attestations[specimen_id]["source_build"]["recipe"]["sources"][
                repo_path(second)
            ] = file_digest(second)
            bundle.rewrite_attestation(specimen_id)
            self.assert_fails(
                run(bundle.certificate_path), "exactly one .v design source (found 2)"
            )

        self.with_bundle(check)

    def test_missing_required_cell_is_rejected(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            specimen_id = "fixture_ff_clkinv"
            cells = bundle.attestations[specimen_id]["resolved"]["cells"]
            cells[:] = [item for item in cells if item["logical_bel"] != "A5FF"]
            bundle.rewrite_attestation(specimen_id)
            self.assert_fails(run(bundle.certificate_path), "target storage cells differ")

        self.with_bundle(check)

    def test_missing_semantic_pointer_is_rejected(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            self.assert_fails(run(bundle.certificate_path), "JSON pointer '/resolved/not_present' does not exist")

        self.with_bundle(check, semantic_pointer="/resolved/not_present")

    def test_self_consistent_wrong_derived_source_checkpoint_is_rejected(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            specimen_id = "fixture_ff_clkinv"
            wrong = "f" * 64
            attestation = bundle.attestations[specimen_id]
            attestation["checkpoint"]["source"]["sha256"] = wrong
            attestation["source_build"]["derived_from"]["base_dcp_sha256"] = wrong
            bundle.rewrite_attestation(specimen_id)
            self.assert_fails(run(bundle.certificate_path), "does not match the pinned source specimen")

        self.with_bundle(check)

    def test_semantic_summary_cannot_override_raw_cells(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            specimen_id = "fixture_ff_clkinv"
            attestation = bundle.attestations[specimen_id]
            for cell in attestation["resolved"]["cells"]:
                if cell["role"] == "target" and cell["kind"] == "storage":
                    cell["properties"]["IS_C_INVERTED"] = "1'b0"
            # Leave resolved.clock_mode == CLKINV. A verifier that trusted the summary
            # would pass the semantic assertion; the routed cell rebuild must reject it.
            bundle.rewrite_attestation(specimen_id)
            self.assert_fails(run(bundle.certificate_path), "resolved.clock_mode differs")

        self.with_bundle(check)

    def test_bitstream_substitution_is_rejected(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            path = bundle.stage / "fixture_ff_clkinv" / "spec.bit"
            path.write_bytes(path.read_bytes() + b"tampered")
            self.assert_fails(run(bundle.certificate_path), "hash mismatch")

        self.with_bundle(check)

    def test_staging_may_not_omit_a_committed_specimen(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            bundle.manifest["specimens"].pop()
            bundle.write_manifest()
            self.assert_fails(run(bundle.certificate_path), "staging specimen completeness mismatch")

        self.with_bundle(check)

    def test_staging_may_not_add_an_uncommitted_directory(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            extra = bundle.stage / "not_committed"
            extra.mkdir()
            (extra / "spec.bit").write_bytes(b"extra")
            (extra / "attestation.json").write_text("{}")
            self.assert_fails(run(bundle.certificate_path), "staging root contents differ")

        self.with_bundle(check)

    def test_staging_may_not_duplicate_a_specimen_or_path(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            bundle.manifest["specimens"].append(copy.deepcopy(bundle.manifest["specimens"][0]))
            bundle.write_manifest()
            self.assert_fails(run(bundle.certificate_path), "duplicates specimen_id")

        self.with_bundle(check)

    def test_unverified_source_stamp_is_rejected(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            specimen_id = "fixture_ff_clkinv"
            bundle.attestations[specimen_id]["source_build"]["completed"] = False
            bundle.rewrite_attestation(specimen_id)
            self.assert_fails(run(bundle.certificate_path), "source build is not completed/verified")

        self.with_bundle(check)

    def test_staged_directory_must_contain_exactly_two_artifacts(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            (bundle.stage / "fixture_ff_clkinv" / "unverified.tmp").write_text("extra")
            self.assert_fails(run(bundle.certificate_path), "directory must contain exactly")

        self.with_bundle(check)

    def test_certificate_artifact_references_must_be_repo_relative(self) -> None:
        def check(bundle: Feature16Bundle) -> None:
            bundle.certificate["staging_manifest"]["path"] = str(
                (bundle.root / "staging_manifest.json").resolve()
            )
            bundle.write_certificate()
            self.assert_fails(run(bundle.certificate_path), "does not match")

        self.with_bundle(check)

    def test_safe_child_itself_rejects_an_absolute_path_inside_the_repo(self) -> None:
        # Schema rejection is not a substitute for the filesystem boundary. Without
        # safe_child's explicit is_absolute() check, this particular absolute path is
        # under the allowed root and would otherwise be accepted.
        with self.assertRaisesRegex(ValueError, "must be repository-relative"):
            safe_child(REPO_ROOT, str((REPO_ROOT / "README.md").resolve()))

    def test_public_ff_commitment_is_the_184_specimen_contract(self) -> None:
        commitment = load(FF_COMMITMENT)
        ids = [item["specimen_id"] for item in commitment["specimens"]]
        self.assertEqual(len(ids), 184)
        self.assertEqual(len(set(ids)), 184)
        self.assertEqual(commitment["totals"], {
            "specimens": 184,
            "predictions": 176,
            "holdout_predictions": 154,
        })


if __name__ == "__main__":
    unittest.main()
