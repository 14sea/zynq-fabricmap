"""The formal `clb_ff_config` converter and stager, checked without Vivado.

Two things are being falsified here:

* the **converter** turns `readback.tsv` + `stamp.json` into a record the *consumer's*
  own rules accept — `ff_formal_attestation_errors` is the oracle, never a producer-side
  imitation of it — and refuses a readback that disagrees with the pinned plan intent;
* the **stager** is all-or-nothing. An incomplete committed set must leave no output at
  all, because the failure mode this guards against is a mine-only staging that reads
  like a small certification.

Every case builds its own synthetic readback, so the suite runs on a cold checkout with
no `build/` tree. `test_the_real_mine_instance_converts` is the one artifact-dependent
case; it is named so that a skip is visible rather than mistaken for a pass.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest.mock
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import gate_build_ff_formal as builder  # noqa: E402
import gate_stage_ff_formal as stager  # noqa: E402

SITE = "SLICE_X2Y25"
SITES = {"target": SITE, "anchor": "SLICE_X4Y20", "keeper": "SLICE_X2Y20"}
TILE = "CLBLL_L_X2Y25"
TILE_TYPE = "CLBLL_L"

PINS = {
    "FDRE": ("C", "CE", "R"),
    "FDSE": ("C", "CE", "S"),
    "FDCE": ("C", "CE", "CLR"),
    "LDCE": ("G", "GE", "CLR"),
}


def storage_cell(lines: list[str], prefix: str, name: str, ref: str, loc: str, bel: str,
                 *, init: str, inverted: str, ce_net: str, sr_net: str) -> None:
    clock, ce, sr = PINS[ref]
    put = lines.append
    put(f"{prefix}.name\t{name}")
    put(f"{prefix}.ref\t{ref}")
    put(f"{prefix}.loc\t{loc}")
    put(f"{prefix}.bel\tSLICEL.{bel}")
    put(f"{prefix}.init\t{init}")
    put(f"{prefix}.lock_pins\t")
    if ref != "LDCE":
        put(f"{prefix}.prop.IS_C_INVERTED\t{inverted}")
    for pin, net in ((clock, "clk_g"), (ce, ce_net), (sr, sr_net),
                     ("D", "o_OBUF"), ("Q", f"q_{bel}")):
        direction = "OUT" if pin == "Q" else "IN"
        put(f"{prefix}.pin.{pin}.net\t{net}")
        put(f"{prefix}.pin.{pin}.dir\t{direction}")
        put(f"{prefix}.pin.{pin}.belpin\t{loc}/{bel}/{pin}")


def lut_cell(lines: list[str], prefix: str, name: str, ref: str, loc: str, bel: str) -> None:
    put = lines.append
    lock = "I0:A1 I1:A2 I2:A3 I3:A4 I4:A5"
    put(f"{prefix}.name\t{name}")
    put(f"{prefix}.ref\t{ref}")
    put(f"{prefix}.loc\t{loc}")
    put(f"{prefix}.bel\tSLICEL.{bel}")
    put(f"{prefix}.init\t32'hA5A5A5A5")
    put(f"{prefix}.lock_pins\t{lock}")
    for index in range(5):
        put(f"{prefix}.pin.I{index}.net\ti_IBUF[{index}]")
        put(f"{prefix}.pin.I{index}.dir\tIN")
        put(f"{prefix}.pin.I{index}.belpin\t{loc}/{bel}/A{index + 1}")
    put(f"{prefix}.pin.O.net\t{name}_o")
    put(f"{prefix}.pin.O.dir\tOUT")
    put(f"{prefix}.pin.O.belpin\t{loc}/{bel}/O6")


def readback_text(variant: str) -> str:
    """A synthetic `ff_formal_readback/1` file for one variant, in the plan's own order."""
    spec = builder.VARIANTS[variant]
    lines = [
        "schema\tff_formal_readback/1",
        f"part\t{builder.PART}",
        f"vivado_version\t{builder.vivado_version()}",
        f"variant\t{variant}",
        f"mode\t{spec['mode']}",
        f"idx\t{spec['idx']}",
        f"site\t{SITE}",
        f"anchor_site\t{SITES['anchor']}",
        f"keeper_site\t{SITES['keeper']}",
        f"tile\t{TILE}",
        f"tile_type\t{TILE_TYPE}",
        "site_type\tSLICEL",
    ]
    intent = stager.storage_intent(variant)
    lines.append(f"storage_count\t{len(intent)}")
    lines.append(f"lut_count\t{len(stager.LUT_BELS)}")
    zini = variant[len("zini_"):] if variant.startswith("zini_") else None
    for index, (bel, ref) in enumerate(intent):
        storage_cell(
            lines, f"store.{index}", f"g_store[{index}].g_used.g_s.s", ref, SITE, bel,
            init="1'b0" if bel == zini else "1'b1",
            inverted="1'b1" if variant in ("clkinv", "latch_base") else "1'b0",
            ce_net="<const1>" if variant == "ce_tied" else "ce_IBUF",
            sr_net="<const0>" if variant == "sr_tied" else "rst_IBUF")
    for index, bel in enumerate(stager.LUT_BELS):
        lut_cell(lines, f"lut.{index}", f"g_hi[{index}].l", stager.LUT_REF, SITE, bel)
    for name, (role, kind, bel, ref) in stager.AK_INTENT.items():
        loc = SITES[role]
        if kind == "lut":
            lut_cell(lines, f"ak.{name}", name, ref, loc, bel)
        else:
            storage_cell(lines, f"ak.{name}", name, ref, loc, bel,
                         init="1'b0", inverted="1'b0", ce_net="ce_IBUF", sr_net="rst_IBUF")
    lines += [
        "net.0.name\tw2",
        "net.0.driver\tanchor_lut2/O",
        "net.0.sinks\tanchor_ff/D anchor_ff2/D",
        "net.0.ports\t",
        "net.0.route_status\tROUTED",
        "net.0.route\t{ CLBLL_LL_A }",
        "net.0.pips\tsynthetic/pip",
        "net.1.name\tclk_g",
        "net.1.driver\tbufg_inst/O",
        "net.1.sinks\tanchor_ff/C",
        "net.1.ports\t",
        "net.1.route_status\tROUTED",
        "net.1.route\t{ HCLK }",
        "net.1.pips\tsynthetic/clkpip",
        "net_count\t2",
    ]
    return "\n".join(lines) + "\n"


class Tree:
    """A synthetic commitment plus a build root holding completed nodes for it."""

    def __init__(self, root: Path, variants: tuple[str, ...] = ("base", "zini_AFF")) -> None:
        self.root = root
        self.build = root / "gate_ff_formal"
        self.plan = {
            "schema_version": "1.5.0",
            "seed": "0xFF07",
            "totals": {"specimens": len(variants), "predictions": 1, "holdout_predictions": 1},
            "specimens": [
                {"specimen_id": f"{SITE}_{variant}", "site": SITE, "variant": variant,
                 "tile": TILE, "tile_type": TILE_TYPE, "site_prefix": "SLICEL_X0",
                 "split": "mine", "pair_with": None, "build_seed": 2259084486}
                for variant in variants
            ],
        }
        self.nodes = builder.plan_nodes(self.plan, {SITE: SITES}, self.build.resolve(), None)
        for node in self.nodes:
            self.write_node(node)
        for node in self.nodes:
            if node["node_type"] == "derived":
                node["base_dcp_sha256"] = builder.sha256_file(
                    self.build.resolve() / SITE / "base" / "base.dcp")
                self.write_node(node)

    def write_node(self, node: dict, *, completed: bool = True) -> None:
        outdir = node["outdir"]
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "readback.tsv").write_text(readback_text(node["variant"]), encoding="utf-8")
        (outdir / "spec.bit").write_bytes(f"synthetic bitstream {node['specimen_id']}\n".encode())
        checkpoint = "derived.dcp" if node["node_type"] == "derived" else "base.dcp"
        (outdir / checkpoint).write_bytes(f"synthetic checkpoint {node['variant']}\n".encode())
        artifacts = {name: builder.sha256_file(outdir / name)
                     for name in ("spec.bit", "readback.tsv", checkpoint)}
        stamp = {
            "schema": "ff_formal_stamp/1",
            "node_type": node["node_type"],
            "instance": node["instance"],
            "variant": node["variant"],
            "attempt_id": "synthetic-stager-fixture",
            "sites": node["sites"],
            "recipe": node["recipe"],
            "completed": completed,
            "artifacts": artifacts,
        }
        if node["node_type"] == "derived":
            stamp["derived_from"] = {"specimen_id": f"{SITE}_base",
                                     "base_dcp_sha256": node["base_dcp_sha256"]}
        (outdir / "stamp.json").write_text(json.dumps(stamp, indent=1), encoding="utf-8")

    def edit_readback(self, variant: str, old: str, new: str) -> None:
        path = self.build.resolve() / SITE / variant / "readback.tsv"
        text = path.read_text(encoding="utf-8")
        assert old in text, f"anchor {old!r} is not in the synthetic readback"
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        node = next(item for item in self.nodes if item["variant"] == variant)
        stamp_path = node["outdir"] / "stamp.json"
        stamp = json.loads(stamp_path.read_text())
        stamp["artifacts"]["readback.tsv"] = builder.sha256_file(path)
        stamp_path.write_text(json.dumps(stamp, indent=1), encoding="utf-8")


class ConverterTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = REPO_ROOT / "build"
        scratch.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.directory.cleanup)
        self.tree = Tree(Path(self.directory.name))

    def convert(self, variant: str) -> tuple[dict, list[str]]:
        node = next(item for item in self.tree.nodes if item["variant"] == variant)
        specimen = next(item for item in self.tree.plan["specimens"]
                        if item["variant"] == variant)
        return stager.convert_node(node, specimen, stager.commitment_reference(self.tree.plan))

    def test_a_converted_record_satisfies_the_consumers_own_rules(self) -> None:
        record, problems = self.convert("base")
        self.assertEqual(problems, [])
        self.assertEqual(record["schema_version"], "2.0.0")
        self.assertEqual(len(record["resolved"]["cells"]), 22)
        self.assertEqual(record["resolved"]["clock_mode"], "NOCLKINV")

    def test_a_derived_record_pins_its_source_checkpoint(self) -> None:
        record, problems = self.convert("zini_AFF")
        self.assertEqual(problems, [])
        self.assertEqual(record["checkpoint"]["kind"], "derived")
        self.assertEqual(record["checkpoint"]["source"]["specimen_id"], f"{SITE}_base")
        self.assertEqual(record["resolved"]["ff_init"]["AFF"], "0")

    def test_every_variant_family_converts(self) -> None:
        for variant in ("latch", "latch_base", "async", "ce_tied", "sr_tied",
                        "clkinv", "zrst_AFF"):
            with self.subTest(variant=variant):
                tree = Tree(Path(self.directory.name) / variant, (variant,))
                node = tree.nodes[0]
                record, problems = stager.convert_node(
                    node, tree.plan["specimens"][0], stager.commitment_reference(tree.plan))
                self.assertEqual(problems, [])
                expected = 18 if variant in stager.FOUR_ELEMENT else 22
                self.assertEqual(len(record["resolved"]["cells"]), expected)

    def test_requested_is_the_plan_intent_spelled_out(self) -> None:
        """The literal expectation, independent of both the readback and the intent table.

        Copying `resolved` into `requested` is *not* observable while the three drift
        guards below stand, because they make the two provably equal — so this case
        exercises the intent path on its own, and fires if the table ever moves.
        """
        tree = Tree(Path(self.directory.name) / "intent", ("zrst_AFF",))
        record, problems = stager.convert_node(
            tree.nodes[0], tree.plan["specimens"][0], stager.commitment_reference(tree.plan))
        self.assertEqual(problems, [])
        requested = {(cell["role"], cell["kind"], cell["logical_bel"]): cell["requested"]
                     for cell in record["resolved"]["cells"]}
        self.assertEqual(requested[("target", "storage", "AFF")],
                         {"ref_name": "FDSE", "loc": SITE, "bel": "AFF"})
        self.assertEqual(requested[("target", "storage", "BFF")],
                         {"ref_name": "FDRE", "loc": SITE, "bel": "BFF"})
        self.assertEqual(requested[("keeper", "storage", "AFF")],
                         {"ref_name": "FDRE", "loc": SITES["keeper"], "bel": "AFF"})
        self.assertEqual(requested[("anchor", "lut", "C6LUT")],
                         {"ref_name": "LUT6", "loc": SITES["anchor"], "bel": "C6LUT"})
        self.assertEqual(
            [cell["requested"]["bel"] for cell in record["resolved"]["cells"]
             if cell["role"] == "target" and cell["kind"] == "lut"],
            list(stager.LUT_BELS))

    def test_a_resolved_bel_that_drifts_from_plan_intent_is_refused(self) -> None:
        """`requested` is intent. If the readback disagrees, the record is not written —
        which is the check that a converter copying `resolved` into `requested` loses."""
        self.tree.edit_readback("base", "store.0.bel\tSLICEL.AFF", "store.0.bel\tSLICEL.BFF")
        with self.assertRaises(SystemExit) as caught:
            self.convert("base")
        self.assertIn("is not the constrained AFF", str(caught.exception))

    def test_a_resolved_primitive_that_drifts_from_plan_intent_is_refused(self) -> None:
        self.tree.edit_readback("base", "store.0.ref\tFDRE", "store.0.ref\tFDSE")
        with self.assertRaises(SystemExit) as caught:
            self.convert("base")
        self.assertIn("is not the constrained FDRE", str(caught.exception))

    def test_a_cell_placed_outside_its_role_site_is_refused(self) -> None:
        self.tree.edit_readback("base", "ak.anchor_ff2.loc\tSLICE_X2Y20",
                                "ak.anchor_ff2.loc\tSLICE_X4Y20")
        with self.assertRaises(SystemExit) as caught:
            self.convert("base")
        self.assertIn("is not the constrained", str(caught.exception))


class IntentMirrorTests(unittest.TestCase):
    def test_the_intent_table_matches_the_pinned_tcl(self) -> None:
        stager.check_tcl_intent()

    def test_a_drifted_tcl_is_refused(self) -> None:
        source = REPO_ROOT / "vivado/specimen/build_ff_formal.tcl"
        scratch = REPO_ROOT / "build"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            copy = Path(directory) / "build_ff_formal.tcl"
            copy.write_text(source.read_text(encoding="utf-8").replace(
                "set lut_bels {A6LUT B6LUT C6LUT D6LUT A5LUT B5LUT C5LUT D5LUT}",
                "set lut_bels {A5LUT B5LUT C5LUT D5LUT A6LUT B6LUT C6LUT D6LUT}"),
                encoding="utf-8")
            with self.assertRaises(SystemExit) as caught:
                stager.check_tcl_intent(copy)
            self.assertIn("lut_bels", str(caught.exception))

    def test_an_anchor_moved_in_the_tcl_is_refused(self) -> None:
        source = REPO_ROOT / "vivado/specimen/build_ff_formal.tcl"
        scratch = REPO_ROOT / "build"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            copy = Path(directory) / "build_ff_formal.tcl"
            copy.write_text(source.read_text(encoding="utf-8").replace(
                "anchor_ff2  AFF   $asite2", "anchor_ff2  BFF   $asite2"), encoding="utf-8")
            with self.assertRaises(SystemExit) as caught:
                stager.check_tcl_intent(copy)
            self.assertIn("anchor_ff2", str(caught.exception))


class StagingTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = REPO_ROOT / "build"
        scratch.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.directory.cleanup)
        self.tree = Tree(Path(self.directory.name))
        self.out = Path(self.directory.name) / "staging"

    def test_a_complete_set_stages_exactly_two_files_per_specimen(self) -> None:
        stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        expected = {item["specimen_id"] for item in self.tree.plan["specimens"]}
        directories = {item.name for item in self.out.iterdir() if item.is_dir()}
        self.assertEqual(directories, expected)
        for specimen_id in expected:
            self.assertEqual({item.name for item in (self.out / specimen_id).iterdir()},
                             {"spec.bit", "attestation.json"})
        manifest = json.loads((self.out / "staging_manifest.json").read_text())
        self.assertTrue(manifest["complete"])
        self.assertEqual({entry["specimen_id"] for entry in manifest["specimens"]}, expected)
        for entry in manifest["specimens"]:
            for pinned in (entry["bitstream"], entry["attestation"]):
                self.assertFalse(Path(pinned["path"]).is_absolute())
                self.assertEqual(
                    builder.sha256_file(REPO_ROOT / pinned["path"]), pinned["sha256"])

    def test_an_incomplete_set_refuses_and_writes_nothing(self) -> None:
        shutil.rmtree(self.tree.build.resolve() / SITE / "zini_AFF")
        with self.assertRaises(SystemExit) as caught:
            stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertIn("1 of 2 committed specimens are built", str(caught.exception))
        self.assertFalse(self.out.exists())
        self.assertFalse(self.out.with_name(self.out.name + ".partial").exists())

    def test_an_unbuilt_extra_directory_cannot_enter_the_staged_set(self) -> None:
        rogue = self.tree.build.resolve() / SITE / "not_committed"
        rogue.mkdir(parents=True)
        (rogue / "stamp.json").write_text("{}", encoding="utf-8")
        stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertEqual({item.name for item in self.out.iterdir() if item.is_dir()},
                         {item["specimen_id"] for item in self.tree.plan["specimens"]})

    def test_a_stamp_that_did_not_complete_refuses_the_whole_staging(self) -> None:
        node = next(item for item in self.tree.nodes if item["variant"] == "base")
        self.tree.write_node(node, completed=False)
        with self.assertRaises(SystemExit) as caught:
            stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertIn("did not complete", str(caught.exception))
        self.assertFalse(self.out.exists())

    def test_a_tampered_bitstream_refuses_the_whole_staging(self) -> None:
        node = next(item for item in self.tree.nodes if item["variant"] == "base")
        (node["outdir"] / "spec.bit").write_bytes(b"tampered\n")
        with self.assertRaises(SystemExit) as caught:
            stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertIn("does not match the hash the stamp recorded", str(caught.exception))
        self.assertFalse(self.out.exists())

    def test_staging_into_a_committed_namespace_is_refused(self) -> None:
        for protected in ("gate_runs/x", "data/x", "evidence/x"):
            with self.subTest(path=protected):
                with self.assertRaises(SystemExit) as caught:
                    stager.check_staging_root(REPO_ROOT / protected)
                self.assertIn("refusing to stage into", str(caught.exception))

    def test_staging_outside_the_repository_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            stager.check_staging_root(Path(tempfile.gettempdir()) / "ff_staging")
        self.assertIn("outside the repository", str(caught.exception))

    def test_a_manifest_that_fails_validation_leaves_no_partial_root(self) -> None:
        """The failure arrives *after* files are written, which is exactly when a
        half-written staging root can survive and be mistaken for output."""
        real = stager.validate_external_schema

        def fail_the_manifest(document, schema, label):
            return ["forced manifest failure"] if "manifest" in label else real(
                document, schema, label)

        with unittest.mock.patch.object(stager, "validate_external_schema",
                                        side_effect=fail_the_manifest):
            with self.assertRaises(SystemExit) as caught:
                stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertIn("manifest does not validate", str(caught.exception))
        self.assertFalse(self.out.exists())
        self.assertFalse(self.out.with_name(self.out.name + ".partial").exists())

    def test_a_cleanup_that_fails_is_reported_and_not_swallowed(self) -> None:
        """The guarantee is "no directory survives", so a cleanup that cannot deliver it
        must say which path is left rather than re-raise the original error as if the
        tree were clean."""
        real = stager.validate_external_schema

        def fail_the_manifest(document, schema, label):
            return ["forced manifest failure"] if "manifest" in label else real(
                document, schema, label)

        with unittest.mock.patch.object(stager, "validate_external_schema",
                                        side_effect=fail_the_manifest):
            with unittest.mock.patch.object(stager.shutil, "rmtree",
                                            side_effect=OSError("device busy")):
                with self.assertRaises(SystemExit) as caught:
                    stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        message = str(caught.exception)
        self.assertIn("could not be removed", message)
        self.assertIn("device busy", message)
        self.assertIn(self.out.name + ".partial", message)
        self.assertFalse(self.out.exists())
        # the residue is real, and the message is what tells the operator about it
        partial = self.out.with_name(self.out.name + ".partial")
        self.assertTrue(partial.exists())
        shutil.rmtree(partial)

    def test_a_bitstream_edited_after_verification_is_refused(self) -> None:
        """`verified_state` checks the source before it is read. This edits the source in
        the window between that check and the copy, so the published file would otherwise
        carry its own new hash and agree with itself."""
        node = next(item for item in self.tree.nodes if item["variant"] == "base")
        real = builder.verified_state
        tampered = []

        def tamper_after_verifying(outdir, verified_node):
            state = real(outdir, verified_node)
            if verified_node["specimen_id"] == node["specimen_id"] and not tampered:
                (outdir / "spec.bit").write_bytes(b"edited after verification\n")
                tampered.append(True)
            return state

        with unittest.mock.patch.object(builder, "verified_state",
                                        side_effect=tamper_after_verifying):
            with self.assertRaises(SystemExit) as caught:
                stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertTrue(tampered, "the fixture never reached the tamper window")
        self.assertIn("changed between verification and staging", str(caught.exception))
        self.assertFalse(self.out.exists())
        self.assertFalse(self.out.with_name(self.out.name + ".partial").exists())

    def test_an_existing_root_is_never_overwritten(self) -> None:
        self.out.mkdir()
        with self.assertRaises(SystemExit) as caught:
            stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertIn("already exists", str(caught.exception))


class ToolInvocationTests(unittest.TestCase):
    """A tool the docs invoke as `scripts/…` must be runnable that way.

    No artifacts, no git history, no Vivado: this is the cheapest possible check and it
    catches a mode that makes every documented command line exit 126.
    """

    TOOLS = ("scripts/gate_stage_ff_formal.py", "scripts/gate_build_ff_formal.py")

    def test_documented_tools_carry_a_shebang_and_the_executable_bit(self) -> None:
        for relative in self.TOOLS:
            with self.subTest(tool=relative):
                path = REPO_ROOT / relative
                self.assertTrue(path.is_file(), relative)
                self.assertTrue(path.read_bytes().startswith(b"#!"), f"{relative}: no shebang")
                mode = path.stat().st_mode
                self.assertTrue(mode & 0o111, f"{relative}: mode {mode & 0o777:o} is not executable")

    def test_the_stager_actually_runs_from_its_documented_path(self) -> None:
        checked = subprocess.run([str(REPO_ROOT / "scripts/gate_stage_ff_formal.py"), "--help"],
                                 cwd=REPO_ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("--stage", checked.stdout)


class CheckScopeTests(unittest.TestCase):
    """`--check` may not report success about a set nobody chose."""

    def setUp(self) -> None:
        scratch = REPO_ROOT / "build"
        scratch.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.directory.cleanup)
        self.tree = Tree(Path(self.directory.name))
        self.all_ids = {item["specimen_id"] for item in self.tree.plan["specimens"]}

    def test_a_named_instance_missing_one_specimen_is_not_a_pass(self) -> None:
        short = set(self.all_ids)
        short.discard(f"{SITE}_zini_AFF")
        problems = stager.check_scope(self.tree.plan, SITE, short)
        self.assertTrue(problems)
        self.assertIn("asserts all 2 of its committed specimens", problems[0])

    def test_a_complete_named_instance_passes(self) -> None:
        self.assertEqual(stager.check_scope(self.tree.plan, SITE, self.all_ids), [])

    def test_nothing_built_is_never_a_pass(self) -> None:
        for instance in (SITE, None):
            with self.subTest(instance=instance):
                problems = stager.check_scope(self.tree.plan, instance, set())
                self.assertTrue(problems)
                self.assertIn("nothing is built", problems[0])

    def test_a_partial_tree_is_allowed_only_without_an_instance(self) -> None:
        partial = {f"{SITE}_base"}
        self.assertEqual(stager.check_scope(self.tree.plan, None, partial), [])
        self.assertTrue(stager.check_scope(self.tree.plan, SITE, partial))

    def test_check_exits_non_zero_when_a_named_instance_is_short(self) -> None:
        shutil.rmtree(self.tree.build.resolve() / SITE / "zini_AFF")
        self.assertEqual(stager.check(self.tree.plan, self.tree.nodes, SITE, verbose=False), 1)
        # the same tree is a legitimate partial diagnostic without --instance
        self.assertEqual(stager.check(self.tree.plan, self.tree.nodes, None, verbose=False), 0)

    def test_check_exits_zero_only_for_a_complete_named_instance(self) -> None:
        self.assertEqual(stager.check(self.tree.plan, self.tree.nodes, SITE, verbose=False), 0)


class RealMineArtifactTests(unittest.TestCase):
    """Artifact-dependent. A skip here is a skip, not a pass — the synthetic cases above
    carry the logic, and the real 23-specimen result is recorded in the commit."""

    MINE = REPO_ROOT / "build/gate_ff_formal" / SITE

    @unittest.skipUnless(MINE.is_dir(), f"no built mine instance at {MINE}")
    def test_the_real_mine_instance_converts(self) -> None:
        plan = builder.load_commitment()
        mapping = builder.check_site_mapping(plan)
        nodes = builder.plan_nodes(plan, mapping, (REPO_ROOT / "build/gate_ff_formal").resolve(),
                                   SITE)
        by_id = {item["specimen_id"]: item for item in plan["specimens"]}
        reference = stager.commitment_reference(plan)
        converted = 0
        for node in nodes:
            if node["node_type"] == "derived":
                node["base_dcp_sha256"] = builder.sha256_file(
                    node["outdir"].parent / "base" / "base.dcp")
            state, why = builder.verified_state(node["outdir"], node)
            self.assertEqual(state, "reuse", why)
            _record, problems = stager.convert_node(node, by_id[node["specimen_id"]], reference)
            self.assertEqual(problems, [], node["specimen_id"])
            converted += 1
        self.assertEqual(converted, 23)


if __name__ == "__main__":
    unittest.main()
