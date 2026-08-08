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

PAD_NETS = ("q", "anchor_o", "anchor_o2")
DEDICATED = ("w1", "w2", "qr1", "q_OBUF", "anchor_o_OBUF", "anchor_o2_OBUF",
             "q", "anchor_o", "anchor_o2")

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


def routepin_lines() -> list[str]:
    """The `routepin.` section of a readback: nine nets, two phases, six fields, and
    first == final because a correct build does not move them."""
    routable = [n for n in DEDICATED if n not in PAD_NETS]
    intrasite = [n for n in DEDICATED if n in PAD_NETS]
    lines = [
        "routepin.schema\tff_formal_routepin/2",
        "routepin.dedicated\t" + " ".join(DEDICATED),
        "routepin.routable\t" + " ".join(routable),
        "routepin.intrasite\t" + " ".join(intrasite),
    ]
    for phase in ("first", "final"):
        for name in DEDICATED:
            pad = name in PAD_NETS
            lines += [
                f"routepin.{phase}.{name}.route\t" + ("{}" if pad else f"{{ {name}_ROUTE }}"),
                f"routepin.{phase}.{name}.pips\t" + ("" if pad else f"{name}_PIP"),
                f"routepin.{phase}.{name}.driver\t{name}_driver/O",
                f"routepin.{phase}.{name}.sinks\t{name}_sink/I",
                f"routepin.{phase}.{name}.status\t" + ("INTRASITE" if pad else "ROUTED"),
                f"routepin.{phase}.{name}.fixed\t" + ("0" if pad else "1"),
            ]
    return lines


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
    # The nine nets `EXPECTED_DEDICATED` must compute to, plus a shared one. Anything
    # less and `compare_pair` fails every pair with `dedicated_unexpected`, which would
    # mask the very mismatch these fixtures exist to inject.
    nets = [
        ("w2", "anchor_lut2/O", "anchor_ff/D anchor_ff2/D"),
        ("w1", "anchor_lut1/O", "anchor_lut2/I0"),
        ("qr1", "q_reduce1/O", "q_reduce2/I0"),
        ("q_OBUF", "q_reduce2/O", "q_OBUF_inst/I"),
        ("anchor_o_OBUF", "anchor_ff/Q", "anchor_o_OBUF_inst/I"),
        ("anchor_o2_OBUF", "anchor_ff2/Q", "anchor_o2_OBUF_inst/I"),
        ("q", "q_OBUF_inst/O", ""),
        ("anchor_o", "anchor_o_OBUF_inst/O", ""),
        ("anchor_o2", "anchor_o2_OBUF_inst/O", ""),
        ("clk_g", "bufg_inst/O", "anchor_ff/C"),
    ]
    for index, (name, driver, sinks) in enumerate(nets):
        # The three pad nets have no interconnect route at all, exactly as Vivado reports
        # them; a fixture that routed them would hide the case the gate has to handle.
        pad = name in PAD_NETS
        lines += [
            f"net.{index}.name\t{name}",
            f"net.{index}.driver\t{driver}",
            f"net.{index}.sinks\t{sinks}",
            f"net.{index}.ports\t",
            f"net.{index}.route_status\t{'INTRASITE' if pad else 'ROUTED'}",
            f"net.{index}.route\t{'{}' if pad else f'{{ {name}_ROUTE }}'}",
            f"net.{index}.pips\t{'' if pad else f'{name}_PIP'}",
        ]
    lines.append(f"net_count\t{len(nets)}")
    lines += routepin_lines()
    return "\n".join(lines) + "\n"


def staging_scratch(case: unittest.TestCase) -> Path:
    """A staging root under the real publish namespace.

    `build/` is gitignored, and the stager now refuses to stage anywhere git excludes —
    a root that cannot be committed could only ever be copied to the published location
    afterwards, and that copy is an unverified publishing step. So the fixtures stage
    where a real run would, and clean up after themselves.
    """
    base = REPO_ROOT / "staging"
    base.mkdir(exist_ok=True)
    directory = tempfile.TemporaryDirectory(dir=base)
    case.addCleanup(lambda: base.rmdir() if base.is_dir() and not any(base.iterdir())
                    else None)
    case.addCleanup(directory.cleanup)
    return Path(directory.name) / "staged"


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
        # One committed pair over the two specimens, so `committed_pairs()` — and
        # therefore the T1/T2 gate — has something real to recompute.
        first, second = (f"{SITE}_{variant}" for variant in variants[:2]) if len(variants) > 1 \
            else (f"{SITE}_{variants[0]}", None)
        if second is not None:
            self.plan["predictions"] = [{
                "feature": "CLBLL_L.SLICEL_X0.FIXTURE",
                "specimen_id": first,
                "comparison_specimen_id": second,
                "split": "mine",
                "expected_transition": {"before": 0, "after": 1},
                "predicted_assignments": [
                    {"token": "31_03", "segbit": {"frame_offset": 31, "bit_offset": 3,
                                                  "negated": False},
                     "address": {"far": "0x00400A1F", "word": 51, "bit": 3},
                     "expected_value": 1}],
            }]
        else:
            self.plan["predictions"] = []
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
        self.out = staging_scratch(self)

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


class StructuralGateTests(unittest.TestCase):
    """The 2026-08-06 hole: the run built 184/184 and exited 0 with one committed pair
    structurally incomparable, and the stager would have staged it."""

    def setUp(self) -> None:
        scratch = REPO_ROOT / "build"
        scratch.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.directory.cleanup)
        self.tree = Tree(Path(self.directory.name))
        self.out = staging_scratch(self)

    def break_a_dedicated_route(self) -> None:
        """Give one endpoint of the committed pair a different route for `w2`.

        `w2` is dedicated by the netlist rule (driver and both sinks are anchor/keeper
        cells), so this is the same tier and the same shape as the real failure: same
        driver, same sinks, one PIP different.
        """
        self.tree.edit_readback("zini_AFF", "net.0.pips\tw2_PIP", "net.0.pips\tw2_OTHER_PIP")
        self.tree.edit_readback("zini_AFF", "net.0.route\t{ w2_ROUTE }",
                                "net.0.route\t{ w2_OTHER_ROUTE }")

    def test_the_fixture_pair_passes_before_it_is_broken(self) -> None:
        self.assertEqual(stager.structural_problems(self.tree.plan, self.tree.nodes), [])

    def test_a_t2_route_mismatch_fails_the_gate(self) -> None:
        self.break_a_dedicated_route()
        problems = stager.structural_problems(self.tree.plan, self.tree.nodes)
        pair_problems = [item for item in problems if item.startswith("pair ")]
        self.assertEqual(len(pair_problems), 1, problems)
        self.assertIn("w2.pips", pair_problems[0])
        self.assertIn("w2.route", pair_problems[0])

    def test_the_stager_refuses_and_writes_nothing(self) -> None:
        self.break_a_dedicated_route()
        with self.assertRaises(SystemExit) as caught:
            stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertIn("structural gate does not pass", str(caught.exception))
        self.assertFalse(self.out.exists())
        self.assertFalse(self.out.with_name(self.out.name + ".partial").exists())

    def test_check_exits_non_zero_on_a_failing_pair(self) -> None:
        self.break_a_dedicated_route()
        self.assertEqual(stager.check(self.tree.plan, self.tree.nodes, None, verbose=False), 1)

    def test_a_drifted_recipe_stops_the_gate_before_any_readback_is_read(self) -> None:
        """Verification precedes comparison, and this pins the order rather than the
        message: with a drifted stamp, `compare_pair` must never be called at all.

        The 2026-08-06 tree is in exactly this state, and the first version of this
        stager reported that run's stale T2 finding instead of the drift.
        """
        node = next(item for item in self.tree.nodes if item["variant"] == "base")
        stamp_path = node["outdir"] / "stamp.json"
        stamp = json.loads(stamp_path.read_text())
        stamp["recipe"]["sources"]["scripts/gate_build_ff_formal.py"] = "0" * 64
        stamp_path.write_text(json.dumps(stamp), encoding="utf-8")

        def must_not_run(*_args, **_kwargs):
            raise AssertionError("compare_pair was called on unverified artifacts")

        with unittest.mock.patch.object(builder, "compare_pair", side_effect=must_not_run):
            with unittest.mock.patch.object(builder, "compare_derived",
                                            side_effect=must_not_run):
                problems = stager.structural_problems(self.tree.plan, self.tree.nodes)
                with self.assertRaises(SystemExit) as caught:
                    stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertTrue(any("different recipe" in item for item in problems), problems)
        self.assertIn("different recipe", str(caught.exception))
        self.assertFalse(self.out.exists())

    def test_a_derived_specimen_with_an_unexpected_change_blocks_staging(self) -> None:
        """T1 and T2 pass; the derived gate does not. `ready_for_measurement` is a
        three-part conjunction, and staging used to enforce two of them."""
        # A shared net's route: diagnostic for a pair (T3, never a FAIL), but an
        # unexpected difference between a derived specimen and the base it was made from.
        self.tree.edit_readback("zini_AFF", "net.9.route\t{ clk_g_ROUTE }",
                                "net.9.route\t{ clk_g_OTHER_ROUTE }")
        gate = builder.structural_gate(self.tree.plan, self.tree.nodes)
        self.assertEqual([p["status"] for p in gate["pairs"]], ["pass"],
                         "the pair gate must still pass, or this proves nothing")
        self.assertEqual([d["status"] for d in gate["derived"]], ["FAIL"])
        with self.assertRaises(SystemExit) as caught:
            stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertIn("structural gate does not pass", str(caught.exception))
        self.assertFalse(self.out.exists())
        self.assertFalse(self.out.with_name(self.out.name + ".partial").exists())

    def test_a_half_scoped_pair_is_a_failure_when_the_scope_is_not_partial(self) -> None:
        """A committed pair with one endpoint outside the node set can never be compared.
        Over a declared partial scope that is a scope fact; over a full one it is a hole."""
        half = [node for node in self.tree.nodes if node["variant"] == "base"]
        problems = stager.structural_problems(self.tree.plan, half)
        self.assertTrue(any("only one endpoint is in scope" in item for item in problems),
                        problems)
        self.assertEqual(
            stager.structural_problems(self.tree.plan, half, partial_scope=True), [])

    def test_an_uncomparable_gate_is_not_a_pass(self) -> None:
        """No pair compared means the gate did not run, which is not the same as passing."""
        problems = stager.structural_problems({"specimens": [], "predictions": []}, [])
        self.assertTrue(problems)
        self.assertTrue(any("an unrun gate is not a pass" in item for item in problems), problems)

    def test_the_stager_does_not_read_the_producers_verdict(self) -> None:
        """A run report claiming success must not be able to unlock staging."""
        self.break_a_dedicated_route()
        (self.tree.build.resolve() / "run_report.json").write_text(json.dumps({
            "schema": "ff_formal_run/2", "complete": True, "build_complete": True,
            "pair_gate_pass": True, "derived_gate_pass": True,
            "ready_for_measurement": True, "pairs": [], "derived": []}), encoding="utf-8")
        with self.assertRaises(SystemExit):
            stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertFalse(self.out.exists())


class BuilderReadinessTests(unittest.TestCase):
    """`ready_for_measurement`, and the exit code that must follow it."""

    def report(self, *, pair_status: str = "pass", derived_status: str = "pass",
               impls: int = 120, specimens: int = 184) -> dict:
        return {
            "implementations_built": impls, "implementations_required": 120,
            "specimens_built": specimens, "specimens_required": 184,
            "verification_problems": [],
            "pairs_required": 1, "pairs_required_ids": [["a", "b"]],
            "derived_required": 1, "derived_required_ids": ["d"],
            "pairs": [{"pair": ["a", "b"], "status": pair_status}],
            "derived": [{"specimen": "d", "status": derived_status}],
        }

    def test_a_complete_green_run_is_ready(self) -> None:
        verdict = builder.readiness(self.report())
        self.assertTrue(verdict["ready_for_measurement"])
        self.assertEqual(builder.exit_code(self.report()), 0)

    def test_a_t2_failure_blocks_a_fully_built_run(self) -> None:
        report = self.report(pair_status="FAIL")
        verdict = builder.readiness(report)
        self.assertTrue(verdict["build_complete"], "the build really did finish")
        self.assertFalse(verdict["pair_gate_pass"])
        self.assertFalse(verdict["ready_for_measurement"])
        self.assertEqual(verdict["pair_failures"], [["a", "b"]])
        self.assertEqual(builder.exit_code(report), 1)

    def test_a_derived_failure_blocks_it_too(self) -> None:
        self.assertEqual(builder.exit_code(self.report(derived_status="FAIL")), 1)

    def test_an_incomplete_build_is_not_ready(self) -> None:
        self.assertEqual(builder.exit_code(self.report(impls=119, specimens=183)), 1)

    def test_an_unbuilt_pair_is_not_a_pass(self) -> None:
        report = self.report()
        report["pairs"].append({"pair": ["c", "d"], "status": "unbuilt"})
        self.assertFalse(builder.readiness(report)["pair_gate_pass"])
        self.assertEqual(builder.exit_code(report), 1)

    def test_no_pairs_at_all_is_not_a_pass(self) -> None:
        report = self.report()
        report["pairs"] = []
        self.assertFalse(builder.readiness(report)["pair_gate_pass"])
        self.assertEqual(builder.exit_code(report), 1)

    def test_dropping_one_passing_pair_still_fails(self) -> None:
        """The trimmed-report attack: keep the counts, keep every surviving record
        passing, and delete one. "All present passed" is not coverage."""
        report = self.report()
        report["pairs_required"] = 2
        report["pairs_required_ids"] = [["a", "b"], ["c", "d"]]
        verdict = builder.readiness(report)
        self.assertFalse(verdict["ready_for_measurement"])
        self.assertTrue(any("do not cover the required set" in item
                            for item in verdict["structural_problems"]), verdict)
        self.assertEqual(builder.exit_code(report), 1)

    def test_dropping_one_passing_derived_record_still_fails(self) -> None:
        report = self.report()
        report["derived_required"] = 2
        report["derived_required_ids"] = ["d", "e"]
        self.assertFalse(builder.readiness(report)["derived_gate_pass"])
        self.assertEqual(builder.exit_code(report), 1)

    def test_a_duplicated_record_is_not_coverage(self) -> None:
        report = self.report()
        report["pairs_required"] = 2
        report["pairs_required_ids"] = [["a", "b"], ["c", "d"]]
        report["pairs"].append({"pair": ["a", "b"], "status": "pass"})
        problems = builder.readiness(report)["structural_problems"]
        self.assertTrue(any("duplicates" in item for item in problems), problems)
        self.assertEqual(builder.exit_code(report), 1)

    def test_a_declared_count_that_contradicts_the_declared_identities_fails(self) -> None:
        """The count is not redundant with the identity check: it cross-checks the two
        declarations against each other, so a record cannot say "168 required" while
        listing one identity and reporting one passing record."""
        report = self.report()
        report["pairs_required"] = 168
        problems = builder.readiness(report)["structural_problems"]
        self.assertTrue(any("record count" in item for item in problems), problems)
        self.assertEqual(builder.exit_code(report), 1)

    def test_a_report_that_declares_no_required_set_cannot_be_judged(self) -> None:
        report = self.report()
        del report["pairs_required_ids"]
        problems = builder.readiness(report)["structural_problems"]
        self.assertTrue(any("does not declare its required pair set" in item
                            for item in problems), problems)
        self.assertEqual(builder.exit_code(report), 1)

    def test_a_missing_pair_declaration_sinks_the_pair_gate_field(self) -> None:
        """The field must follow the category, not the wording. This message begins with
        "the", so classifying by `startswith("pair")` reported pair_gate_pass True about a
        gate that could not be evaluated at all."""
        report = self.report()
        del report["pairs_required_ids"]
        verdict = builder.readiness(report)
        self.assertFalse(verdict["pair_gate_pass"])
        self.assertTrue(verdict["derived_gate_pass"])
        self.assertFalse(verdict["ready_for_measurement"])

    def test_a_missing_derived_declaration_sinks_only_the_derived_gate_field(self) -> None:
        report = self.report()
        del report["derived_required_ids"]
        verdict = builder.readiness(report)
        self.assertTrue(verdict["pair_gate_pass"])
        self.assertFalse(verdict["derived_gate_pass"])
        self.assertFalse(verdict["ready_for_measurement"])

    def test_pair_count_and_duplicate_problems_sink_only_the_pair_gate(self) -> None:
        for mutate in (lambda r: r.__setitem__("pairs_required", 168),
                       lambda r: r["pairs"].append({"pair": ["a", "b"], "status": "pass"})):
            with self.subTest(mutation=mutate):
                report = self.report()
                mutate(report)
                verdict = builder.readiness(report)
                self.assertFalse(verdict["pair_gate_pass"])
                self.assertTrue(verdict["derived_gate_pass"])
                self.assertFalse(verdict["ready_for_measurement"])

    def test_derived_count_and_duplicate_problems_sink_only_the_derived_gate(self) -> None:
        for mutate in (lambda r: r.__setitem__("derived_required", 64),
                       lambda r: r["derived"].append({"specimen": "d", "status": "pass"})):
            with self.subTest(mutation=mutate):
                report = self.report()
                mutate(report)
                verdict = builder.readiness(report)
                self.assertTrue(verdict["pair_gate_pass"])
                self.assertFalse(verdict["derived_gate_pass"])
                self.assertFalse(verdict["ready_for_measurement"])

    def test_one_verification_problem_sinks_both_gate_fields(self) -> None:
        report = self.report()
        report["verification_problems"] = ["SLICE_X2Y25_base: refusing to use … — "
                                           "stamp was produced by a different recipe."]
        verdict = builder.readiness(report)
        self.assertFalse(verdict["pair_gate_pass"])
        self.assertFalse(verdict["derived_gate_pass"])
        self.assertFalse(verdict["ready_for_measurement"])
        # and nothing else is asserted about pairs or derived, because nothing was compared
        self.assertEqual(verdict["structural_problems"], report["verification_problems"])

    def test_the_categories_are_buckets_not_string_prefixes(self) -> None:
        """Every finding must arrive already classified, so no consumer has to parse."""
        report = self.report(pair_status="FAIL", derived_status="FAIL")
        findings = builder.gate_findings(report)
        self.assertEqual(sorted(findings), ["derived", "pair", "verification"])
        self.assertEqual(len(findings["pair"]), 1, findings)
        self.assertEqual(len(findings["derived"]), 1, findings)
        self.assertEqual(findings["verification"], [])
        self.assertEqual(builder.gate_problems(report),
                         findings["verification"] + findings["pair"] + findings["derived"])

    def test_a_verification_problem_stops_the_verdict_before_any_comparison(self) -> None:
        report = self.report()
        report["verification_problems"] = ["SLICE_X2Y25_base: stamp was produced by a "
                                           "different recipe"]
        verdict = builder.readiness(report)
        self.assertFalse(verdict["pair_gate_pass"])
        self.assertFalse(verdict["derived_gate_pass"])
        self.assertFalse(verdict["ready_for_measurement"])
        self.assertEqual(verdict["structural_problems"], report["verification_problems"])

    def test_the_preserved_failing_run_is_refused_by_the_new_gate(self) -> None:
        """The real artifact of 2026-08-06, versioned in evidence/, must not be ready."""
        report = json.loads((REPO_ROOT / "evidence/ff_holdout_2026_08_06_t2fail"
                             / "run_report.json").read_text())
        verdict = builder.readiness(report)
        self.assertTrue(verdict["build_complete"])
        self.assertEqual(verdict["pairs_compared"], 168)
        self.assertEqual(verdict["pair_failures"],
                         [["SLICE_X25Y25_base", "SLICE_X25Y25_ce_tied"]])
        self.assertFalse(verdict["ready_for_measurement"])
        self.assertEqual(builder.exit_code(report), 1)


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

    @staticmethod
    def matches_current_recipe() -> bool:
        """A recipe-domain change invalidates every artifact on disk, by design. When
        that has happened the precondition for this case is absent — which is a fact
        about the tree, not a silent pass: the synthetic cases above carry the logic."""
        stamp = RealMineArtifactTests.MINE / "base" / "stamp.json"
        if not stamp.is_file():
            return False
        recorded = json.loads(stamp.read_text())["recipe"]["sources"]
        return all(builder.sha256_file(REPO_ROOT / path) == digest
                   for path, digest in recorded.items())

    @unittest.skipUnless(MINE.is_dir(), f"no built mine instance at {MINE}")
    def test_the_real_mine_instance_converts(self) -> None:
        if not self.matches_current_recipe():
            self.skipTest("the built mine artifacts predate the current recipe — "
                          "they are invalidated until rebuilt")
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



class RoutePinTamperTests(unittest.TestCase):
    """The route-pin record lives inside `readback.tsv`, so it is pinned by that
    artifact's hash — and the gate still recomputes it from the raw fields rather than
    trusting that the hash matched. Both layers are checked here, because either alone
    is defeated by the other's blind spot."""

    def setUp(self) -> None:
        scratch = REPO_ROOT / "build"
        scratch.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.directory.cleanup)
        self.tree = Tree(Path(self.directory.name))
        self.out = staging_scratch(self)
        self.node = next(n for n in self.tree.nodes if n["variant"] == "base")

    def edit_routepin(self, old: str, new: str, *, forge_stamp: bool) -> None:
        path = self.node["outdir"] / "readback.tsv"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, "the anchor is not in the fixture readback")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        if forge_stamp:
            stamp_path = self.node["outdir"] / "stamp.json"
            stamp = json.loads(stamp_path.read_text())
            stamp["artifacts"]["readback.tsv"] = builder.sha256_file(path)
            stamp_path.write_text(json.dumps(stamp, indent=1), encoding="utf-8")

    def test_layer_one_an_edited_record_without_a_matching_stamp_is_refused(self) -> None:
        self.edit_routepin("routepin.final.w1.pips\tw1_PIP",
                           "routepin.final.w1.pips\tw1_OTHER_PIP", forge_stamp=False)
        problems = stager.structural_problems(self.tree.plan, self.tree.nodes)
        self.assertTrue(any("does not match the hash the stamp recorded" in item
                            for item in problems), problems)
        with self.assertRaises(SystemExit):
            stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertFalse(self.out.exists())

    def test_layer_two_a_forged_stamp_hash_does_not_help(self) -> None:
        """Hash agreement is not agreement with the facts: the record now says the final
        PIPs differ from the first, and that is read from the fields themselves."""
        self.edit_routepin("routepin.final.w1.pips\tw1_PIP",
                           "routepin.final.w1.pips\tw1_OTHER_PIP", forge_stamp=True)
        problems = stager.structural_problems(self.tree.plan, self.tree.nodes)
        self.assertFalse(any("hash" in item for item in problems),
                         f"the hash layer should be satisfied now: {problems}")
        self.assertTrue(any("pips changed between the first and the final record" in item
                            for item in problems), problems)
        with self.assertRaises(SystemExit):
            stager.stage(self.tree.plan, self.tree.nodes, self.out, verbose=False)
        self.assertFalse(self.out.exists())

    def test_a_forged_stamp_cannot_hide_an_unfrozen_net(self) -> None:
        self.edit_routepin("routepin.final.w1.fixed\t1", "routepin.final.w1.fixed\t0",
                           forge_stamp=True)
        problems = stager.structural_problems(self.tree.plan, self.tree.nodes)
        self.assertTrue(any("IS_ROUTE_FIXED reads '0'" in item for item in problems),
                        problems)

    def test_a_forged_stamp_cannot_hide_a_missing_field(self) -> None:
        self.edit_routepin("routepin.final.w1.sinks\tw1_sink/I\n", "", forge_stamp=True)
        problems = stager.structural_problems(self.tree.plan, self.tree.nodes)
        self.assertTrue(any("the namespace is not exactly" in item for item in problems),
                        problems)

    def test_a_forged_stamp_cannot_hide_a_shrunken_dedicated_set(self) -> None:
        self.edit_routepin("routepin.dedicated\t" + " ".join(DEDICATED),
                           "routepin.dedicated\t" + " ".join(DEDICATED[:8]),
                           forge_stamp=True)
        problems = stager.structural_problems(self.tree.plan, self.tree.nodes)
        self.assertTrue(any("dedicated set is not the nine" in item for item in problems),
                        problems)

    def test_a_forged_stamp_cannot_hide_a_pad_net_that_grew_a_route(self) -> None:
        self.edit_routepin("routepin.final.q.pips\t", "routepin.final.q.pips\tq_PIP",
                           forge_stamp=True)
        problems = stager.structural_problems(self.tree.plan, self.tree.nodes)
        self.assertTrue(any("intrasite but carries route/pips" in item
                            or "changed between the first and the final" in item
                            for item in problems), problems)


class RoutePinFailOpenTests(unittest.TestCase):
    """Three checks that a correct record satisfies whatever the gate does — so the only
    way to know they exist is to hand the gate a wrong one. Each of these passed before
    the gate was tightened, on data that happened to be clean."""

    def setUp(self) -> None:
        scratch = REPO_ROOT / "build"
        scratch.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.directory.cleanup)
        self.tree = Tree(Path(self.directory.name))
        self.node = next(n for n in self.tree.nodes if n["variant"] == "base")
        self.path = self.node["outdir"] / "readback.tsv"

    def rewrite(self, text: str) -> None:
        self.path.write_text(text, encoding="utf-8")
        stamp_path = self.node["outdir"] / "stamp.json"
        stamp = json.loads(stamp_path.read_text())
        stamp["artifacts"]["readback.tsv"] = builder.sha256_file(self.path)
        stamp_path.write_text(json.dumps(stamp, indent=1), encoding="utf-8")

    def problems(self) -> list[str]:
        return stager.structural_problems(self.tree.plan, self.tree.nodes)

    def test_a_duplicated_key_is_refused_rather_than_overwritten(self) -> None:
        """A dict assignment keeps the last value, so a second `pips` line would pass
        every "exactly these fields" check while the reader saw only one of them."""
        text = self.path.read_text(encoding="utf-8")
        self.rewrite(text + "routepin.final.w1.pips\tw1_SECOND_VALUE\n")
        self.assertTrue(any("duplicate keys in the record" in item
                            for item in self.problems()), self.problems())

    def test_an_extra_key_in_the_namespace_is_refused(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        self.rewrite(text + "routepin.note\tlooks harmless\n")
        self.assertTrue(any("the namespace is not exactly" in item
                            for item in self.problems()), self.problems())

    def test_a_repeated_member_in_the_routable_list_is_refused(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        routable = [n for n in DEDICATED if n not in PAD_NETS]
        self.rewrite(text.replace("routepin.routable\t" + " ".join(routable),
                                  "routepin.routable\t" + " ".join(routable + ["w1"]), 1))
        self.assertTrue(any("routable list repeats a net" in item
                            for item in self.problems()), self.problems())

    def test_a_list_member_outside_the_dedicated_set_is_refused(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        self.rewrite(text.replace("routepin.intrasite\tq anchor_o anchor_o2",
                                  "routepin.intrasite\tq anchor_o clk_g", 1))
        self.assertTrue(any("names something outside the dedicated set" in item
                            for item in self.problems()), self.problems())

    def test_a_net_that_lost_its_freeze_between_phases_is_refused(self) -> None:
        """`fixed` used to be excluded from the first/final comparison. The flow sets
        IS_ROUTE_FIXED before it captures `first`, so the two cannot legitimately differ."""
        text = self.path.read_text(encoding="utf-8")
        self.rewrite(text.replace("routepin.final.w1.fixed\t1",
                                  "routepin.final.w1.fixed\t0", 1))
        problems = self.problems()
        self.assertTrue(any("fixed changed between the first and the final record" in item
                            for item in problems), problems)

    def test_an_unrouted_net_is_not_treated_as_completed(self) -> None:
        """"not INTRASITE" is not "routed": UNROUTED is neither, and counting it as
        completion is how an unfinished route passes as a pinned one."""
        text = self.path.read_text(encoding="utf-8")
        text = text.replace("routepin.first.w1.status\tROUTED",
                            "routepin.first.w1.status\tUNROUTED", 1)
        text = text.replace("routepin.final.w1.status\tROUTED",
                            "routepin.final.w1.status\tUNROUTED", 1)
        self.rewrite(text)
        problems = self.problems()
        self.assertTrue(any("neither ROUTED nor INTRASITE" in item for item in problems),
                        problems)



class PublishPathTests(unittest.TestCase):
    """A staging root that git excludes cannot be the published one, so staging there
    could only ever be followed by a copy — an unverified publishing step nobody gates."""

    def test_a_gitignored_root_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            stager.check_staging_root(REPO_ROOT / "build/ff_staging")
        self.assertIn("excluded by .gitignore", str(caught.exception))
        self.assertIn("staging/<run_id>/", str(caught.exception))

    def test_the_intended_publish_location_is_accepted(self) -> None:
        resolved = stager.check_staging_root(REPO_ROOT / "staging/run_2026_08_05_ff")
        self.assertEqual(resolved, (REPO_ROOT / "staging/run_2026_08_05_ff").resolve())
        self.assertFalse(resolved.exists(), "the check must not create anything")


if __name__ == "__main__":
    unittest.main()
