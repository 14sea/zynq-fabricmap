#!/usr/bin/env python3
"""Convert built formal `clb_ff_config` specimens into `specimen_attestation` 2.0.0
records, and stage the committed set for a certificate 1.6 measurement.

Two modes, and the difference between them is the whole point:

* ``--check`` converts and validates specimens one at a time and **writes nothing**.
  This is how a partially built tree (the mine instance, 23 of 184) is exercised. Naming
  ``--instance`` asserts that whole instance: 22 of its 23 converting is a failed check,
  not a 22/22 success. Without it the mode is diagnostic and a partial tree is fine — but
  an empty one never is.
* ``--stage RUN_ROOT`` converts every committed specimen and writes the staged set as
  ``<run-root>/staging_manifest.json`` beside ``<run-root>/specimens/<specimen_id>/``. It is
  **all or nothing**: with anything missing it refuses and leaves no output behind,
  because certificate 1.6 requires set equality with the commitment and a "successfully
  built subset" is exactly what that rule exists to reject.

There is deliberately no flag naming a commitment file. The commitment is
`gate_build_ff_formal.load_commitment()`, hash-pinned, or nothing — a tool that can be
pointed at a reduced `predictions.json` is a tool that can stage a mine-only set and
call it complete.

`requested` versus `resolved`, and why this file has an intent table
-------------------------------------------------------------------
`readback.tsv` records only what Vivado **resolved**. Filling `requested` from it would
make the consumer's requested/resolved comparison compare a value with itself. So
`requested` is derived here from the *pinned plan intent* — the BEL/LOC/primitive each
cell was constrained to, which follows from the variant and the site rule — and the
readback is then required to agree with it. The intent table mirrors
`vivado/specimen/build_ff_formal.tcl`, whose hash is pinned in every stamp;
`check_tcl_intent()` re-reads that Tcl and refuses if the mirror has drifted.

The builder is a recipe-domain file: every specimen stamps its hash. This tool imports
it and never edits it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import gate_build_ff_formal as builder  # noqa: E402
from host.verify_certificate import (  # noqa: E402
    ff_formal_attestation_errors,
    validate_external_schema,
)

ATTESTATION_SCHEMA = REPO / "schemas/specimen_attestation.schema.json"
STAGING_SCHEMA = REPO / "schemas/specimen_staging.schema.json"

# Directories a staging root may never be written into: a run namespace is certified
# evidence, `data/` is the freeze, `evidence/` is non-overwritable attempt history.
PROTECTED = ("gate_runs", "data", "evidence", ".git", "docs", "schemas", "host",
             "scripts", "tests", "vivado")

# ---------------------------------------------------------------------------------------
# Pinned plan intent (mirrors build_ff_formal.tcl; verified against it, not trusted)
# ---------------------------------------------------------------------------------------

LUT_BELS = ("A6LUT", "B6LUT", "C6LUT", "D6LUT", "A5LUT", "B5LUT", "C5LUT", "D5LUT")
LUT_REF = "LUT5"

# name -> (role, kind, bel, ref_name); the site each role resolves to comes from the
# stamp's site map, never from a table here.
AK_INTENT = {
    "anchor_lut1": ("anchor", "lut", "A6LUT", "LUT6"),
    "anchor_lut2": ("anchor", "lut", "B6LUT", "LUT6"),
    "q_reduce1": ("anchor", "lut", "C6LUT", "LUT6"),
    "q_reduce2": ("anchor", "lut", "D6LUT", "LUT6"),
    "anchor_ff": ("anchor", "storage", "AFF", "FDRE"),
    "anchor_ff2": ("keeper", "storage", "AFF", "FDRE"),
}

FOUR_ELEMENT = ("latch", "latch_base")


def storage_intent(variant: str) -> tuple[tuple[str, str], ...]:
    """`((bel, ref_name), …)` the variant constrains, in build order.

    Derived `zini_*` specimens reuse `base`'s routed checkpoint and change one cell
    property, so their primitive intent is `base`'s.
    """
    if variant not in builder.VARIANTS:
        raise SystemExit(f"unknown variant {variant!r}")
    bels = builder.MAIN_FFS if variant in FOUR_ELEMENT else builder.FF_ORDER
    out = []
    for bel in bels:
        if variant == "latch":
            ref = "LDCE"
        elif variant in ("latch_base", "async"):
            ref = "FDCE"
        elif variant.startswith("zrst_") and variant[len("zrst_"):] == bel:
            ref = "FDSE"
        else:
            ref = "FDRE"
        out.append((bel, ref))
    return tuple(out)


def check_tcl_intent(tcl_path: Path | None = None) -> None:
    """Refuse if the Tcl no longer assigns what the intent table above claims.

    The table is a mirror of a hash-pinned file, so drift must be loud rather than
    silently producing a `requested` block nothing was ever constrained to.
    """
    path = tcl_path or (REPO / "vivado/specimen/build_ff_formal.tcl")
    text = path.read_text(encoding="utf-8")

    def tcl_list(name: str, occurrence: int = 0) -> tuple[str, ...]:
        found = re.findall(rf"set\s+{name}\s+\{{([^}}]*)\}}", text)
        if len(found) <= occurrence:
            raise SystemExit(f"{path}: cannot read Tcl list {name!r}")
        return tuple(found[occurrence].split())

    if tcl_list("lut_bels") != LUT_BELS:
        raise SystemExit(f"{path}: lut_bels no longer matches this tool's intent table")
    four, eight = tcl_list("store_bels", 0), tcl_list("store_bels", 1)
    if four != builder.MAIN_FFS or eight != builder.FF_ORDER:
        raise SystemExit(f"{path}: store_bels no longer matches the builder's BEL order")

    block = re.search(r"foreach \{name bel where\} \[list \\\n(.*?)\]\s*\{", text, re.S)
    if not block:
        raise SystemExit(f"{path}: cannot read the anchor/keeper placement block")
    fields = block.group(1).replace("\\", " ").split()
    if len(fields) % 3:
        raise SystemExit(f"{path}: anchor/keeper block is not name/bel/site triples")
    seen = {fields[i]: (fields[i + 1], fields[i + 2]) for i in range(0, len(fields), 3)}
    if set(seen) != set(AK_INTENT):
        raise SystemExit(f"{path}: anchor/keeper cell set differs from this tool's table")
    for name, (bel, where) in seen.items():
        role, _kind, want_bel, _ref = AK_INTENT[name]
        want_where = "$asite2" if role == "keeper" else "$asite"
        if bel != want_bel or where != want_where:
            raise SystemExit(
                f"{path}: {name} is constrained to {bel}@{where}, "
                f"the intent table says {want_bel}@{want_where}")


# ---------------------------------------------------------------------------------------
# readback.tsv -> attestation 2.0.0
# ---------------------------------------------------------------------------------------

def cell_record(kv: dict[str, str], prefix: str, *, role: str, kind: str,
                logical_name: str, want_bel: str, want_ref: str, want_loc: str) -> dict:
    """One cell: resolved facts from the readback, requested facts from the plan."""
    resolved_bel = kv[f"{prefix}.bel"]
    leaf = resolved_bel.rsplit("/", 1)[-1].rsplit(".", 1)[-1]
    if leaf != want_bel:
        raise SystemExit(
            f"{prefix}: resolved BEL {resolved_bel} is not the constrained {want_bel}")
    if kv[f"{prefix}.ref"] != want_ref:
        raise SystemExit(
            f"{prefix}: resolved REF_NAME {kv[f'{prefix}.ref']} is not the "
            f"constrained {want_ref}")
    if kv[f"{prefix}.loc"] != want_loc:
        raise SystemExit(
            f"{prefix}: resolved LOC {kv[f'{prefix}.loc']} is not the constrained {want_loc}")

    pins: dict[str, dict[str, str]] = {}
    for key in kv:
        if key.startswith(f"{prefix}.pin.") and key.endswith(".net"):
            pin = key[len(prefix) + len(".pin."):-len(".net")]
            pins[pin] = {
                "net": kv[key],
                "direction": kv[f"{prefix}.pin.{pin}.dir"],
                "bel_pin": kv.get(f"{prefix}.pin.{pin}.belpin", ""),
            }
    if not pins:
        raise SystemExit(f"{prefix}: readback carries no pin facts")

    properties = {}
    init = kv.get(f"{prefix}.init", "")
    if init:
        properties["INIT"] = init
    for key, value in kv.items():
        if key.startswith(f"{prefix}.prop.") and value:
            properties[key.rsplit(".", 1)[-1]] = value
    if not properties:
        raise SystemExit(f"{prefix}: readback carries no cell properties")

    return {
        "logical_name": logical_name,
        "logical_bel": want_bel,
        "role": role,
        "kind": kind,
        "requested": {"ref_name": want_ref, "loc": want_loc, "bel": want_bel},
        "resolved": {"ref_name": kv[f"{prefix}.ref"], "loc": kv[f"{prefix}.loc"],
                     "bel": resolved_bel},
        "properties": properties,
        "lock_pins": kv.get(f"{prefix}.lock_pins", ""),
        "pin_mapping": ({name: fact["bel_pin"] for name, fact in sorted(pins.items())
                         if fact["direction"] == "IN" and fact["bel_pin"]}
                        if kind == "lut" else {}),
        "pins": pins,
    }


def resolved_block(kv: dict[str, str], stamp: dict) -> dict:
    """The routed facts, rebuilt from the readback in the plan's own cell order."""
    variant = stamp["variant"]
    sites = stamp["sites"]
    intent = storage_intent(variant)
    if int(kv["storage_count"]) != len(intent):
        raise SystemExit(
            f"{variant}: readback has {kv['storage_count']} storage cells, "
            f"the plan constrains {len(intent)}")
    if int(kv["lut_count"]) != len(LUT_BELS):
        raise SystemExit(f"{variant}: readback has {kv['lut_count']} target LUTs, plan says 8")

    cells = []
    for index, (bel, ref) in enumerate(intent):
        cells.append(cell_record(
            kv, f"store.{index}", role="target", kind="storage",
            logical_name=kv[f"store.{index}.name"], want_bel=bel, want_ref=ref,
            want_loc=sites["target"]))
    for index, bel in enumerate(LUT_BELS):
        cells.append(cell_record(
            kv, f"lut.{index}", role="target", kind="lut",
            logical_name=kv[f"lut.{index}.name"], want_bel=bel, want_ref=LUT_REF,
            want_loc=sites["target"]))
    for name, (role, kind, bel, ref) in AK_INTENT.items():
        cells.append(cell_record(
            kv, f"ak.{name}", role=role, kind=kind, logical_name=name,
            want_bel=bel, want_ref=ref, want_loc=sites[role]))

    nets = {}
    for index in range(int(kv["net_count"])):
        name = kv[f"net.{index}.name"]
        if name in nets:
            raise SystemExit(f"readback lists net {name!r} twice")
        nets[name] = {
            "driver": kv.get(f"net.{index}.driver", ""),
            "sinks": sorted(set(kv.get(f"net.{index}.sinks", "").split())),
            "ports": sorted(set(kv.get(f"net.{index}.ports", "").split())),
            "route_status": kv.get(f"net.{index}.route_status", ""),
            "route": kv.get(f"net.{index}.route", ""),
            "pips": sorted(set(kv.get(f"net.{index}.pips", "").split())),
        }
    if not nets:
        raise SystemExit("readback carries no nets")

    # The five `/resolved/*` summaries the frozen predictions point at. They are written
    # because the schema requires them; the consumer's verifier rebuilds every one of
    # them from `cells` and rejects any disagreement, so nothing here is load-bearing.
    storage = [cell for cell in cells if cell["role"] == "target" and cell["kind"] == "storage"]
    ff_init, ff_srval = {}, {}
    ce_tied, sr_tied, sr_kinds, storage_kinds, clock_modes = set(), set(), set(), set(), set()
    for cell in storage:
        bel = cell["logical_bel"]
        ref = cell["resolved"]["ref_name"]
        ff_init[bel] = "1" if cell["properties"].get("INIT", "").endswith("1") else "0"
        ff_srval[bel] = "1" if ref in ("FDSE", "FDPE") else "0"
        ce_pin = "GE" if ref == "LDCE" else "CE"
        sr_pin = "CLR" if ref in ("FDCE", "LDCE") else ("S" if ref in ("FDSE", "FDPE") else "R")
        ce_tied.add(is_tied(cell["pins"][ce_pin]["net"]))
        sr_tied.add(is_tied(cell["pins"][sr_pin]["net"]))
        sr_kinds.add("ASYNC" if ref in ("FDCE", "LDCE") else "SYNC")
        storage_kinds.add("LATCH" if ref == "LDCE" else "FF")
        if ref == "LDCE":
            clock_modes.add("LATCH")
        else:
            inverted = cell["properties"].get("IS_C_INVERTED", "")
            clock_modes.add("CLKINV" if inverted.endswith("1") else "NOCLKINV")
    for name, values in (("ce_mode", ce_tied), ("sr_mode", sr_tied), ("sr_kind", sr_kinds),
                         ("storage_kind", storage_kinds), ("clock_mode", clock_modes)):
        if len(values) != 1:
            raise SystemExit(f"{variant}: routed cells do not define one {name}: {sorted(values)}")

    return {
        "target": {"requested_site": sites["target"], "resolved_site": kv["site"],
                   "tile": kv["tile"], "tile_type": kv["tile_type"]},
        "cells": cells,
        "nets": nets,
        "ff_init": ff_init,
        "ff_srval": ff_srval,
        "ce_mode": "TIED" if next(iter(ce_tied)) else "DRIVEN",
        "sr_mode": "TIED" if next(iter(sr_tied)) else "DRIVEN",
        "sr_kind": next(iter(sr_kinds)),
        "storage_kind": next(iter(storage_kinds)),
        "clock_mode": next(iter(clock_modes)),
    }


def is_tied(net: str) -> bool:
    return net.strip().upper() in {"<CONST0>", "<CONST1>", "GND", "VCC"}


def commitment_reference(plan: dict) -> dict:
    """The certificate-shaped reference every attestation and the manifest must carry."""
    return {
        "run_id": builder.COMMITMENT.parent.name,
        "path": str(builder.COMMITMENT.relative_to(REPO)),
        "sha256": builder.COMMITTED_SHA256,
        "schema_version": plan["schema_version"],
        "seed": str(plan["seed"]),
        "totals": dict(plan["totals"]),
    }


def attestation_for(node: dict, reference: dict) -> dict:
    """`readback.tsv` + `stamp.json` for one verified node -> a 2.0.0 record."""
    outdir = node["outdir"]
    stamp = json.loads((outdir / "stamp.json").read_text(encoding="utf-8"))
    kv = builder.read_tsv(outdir / "readback.tsv")
    if kv.get("schema") != "ff_formal_readback/1":
        raise SystemExit(f"{outdir}: unexpected readback schema {kv.get('schema')!r}")
    if stamp["variant"] != kv["variant"] or stamp["instance"] != kv["site"]:
        raise SystemExit(f"{outdir}: stamp and readback describe different specimens")

    checkpoint_file = "derived.dcp" if stamp["node_type"] == "derived" else "base.dcp"
    checkpoint = {"kind": stamp["node_type"],
                  "artifact": {"file": checkpoint_file,
                               "sha256": stamp["artifacts"][checkpoint_file]}}
    if stamp["node_type"] == "derived":
        checkpoint["source"] = {"specimen_id": stamp["derived_from"]["specimen_id"],
                                "file": "base.dcp",
                                "sha256": stamp["derived_from"]["base_dcp_sha256"]}

    return {
        "schema": "specimen_attestation",
        "schema_version": "2.0.0",
        "profile": "ff_formal",
        "specimen_id": node["specimen_id"],
        "prediction_commitment": dict(reference),
        "source_build": stamp,
        "resolved": resolved_block(kv, stamp),
        "checkpoint": checkpoint,
        "outputs": {"spec.bit": stamp["artifacts"]["spec.bit"]},
    }


def certificate_specimen(node: dict, plan_specimen: dict, attestation: dict) -> dict:
    """The specimen record the certifier will emit, assembled here so `--check` can run
    the consumer's own rule instead of a producer-side imitation of it."""
    stamp = attestation["source_build"]
    return {
        "specimen_id": node["specimen_id"],
        "loc_site": node["sites"]["target"],
        "tile": plan_specimen["tile"],
        "tile_type": plan_specimen["tile_type"],
        "part": stamp["recipe"]["part"],
        "vivado_version": stamp["recipe"]["vivado_version"],
        "build_seed": plan_specimen["build_seed"],
        "bitstream_sha256": stamp["artifacts"]["spec.bit"],
    }


def convert_node(node: dict, plan_specimen: dict, reference: dict) -> tuple[dict, list[str]]:
    """Convert one *verified* node and score it with the consumer's rules."""
    attestation = attestation_for(node, reference)
    problems = list(validate_external_schema(attestation, ATTESTATION_SCHEMA,
                                             f"{node['specimen_id']} attestation"))
    problems += ff_formal_attestation_errors(
        attestation, certificate_specimen(node, plan_specimen, attestation),
        plan_specimen, reference, REPO)
    return attestation, problems


# ---------------------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------------------

def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def structural_problems(plan: dict, nodes: list[dict], *, partial_scope: bool = False) -> list[str]:
    """The builder's whole structural gate, recomputed here from the artifacts.

    Not `run_report.json`: a producer-written verdict must never be what unlocks staging.
    Not a pair-only recomputation either — `ready_for_measurement` is a three-part
    conjunction, and enforcing two of the three is how a derived specimen with an
    unexpected change would have walked straight through.

    `builder.structural_gate` verifies every node before it opens a single readback, so a
    tree whose recipe has drifted reports the drift rather than stale comparisons of
    artifacts nobody should be reading. `partial_scope` says the node set is knowingly a
    subset — a diagnostic over a half-built tree — so pairs and derived specimens it
    cannot cover are out of scope rather than failures. It selects which identities are
    required; it never changes the rule applied to them.
    """
    return builder.gate_problems(
        builder.structural_gate(plan, nodes, partial_scope=partial_scope))


def check_scope(plan: dict, instance: str | None, built: set[str]) -> list[str]:
    """What `--check` may call a success.

    Naming an instance asserts *that instance*, so 22 of its 23 specimens converting is
    a failed check, not a 22/22 success — otherwise the exit code says "clean" about a
    set nobody chose. Without `--instance` the mode is diagnostic and a partial tree is
    allowed, but an empty one still is not: a run that verified nothing must never exit 0.
    """
    problems: list[str] = []
    if not built:
        return ["nothing is built: a check that verified no specimen is not a pass"]
    if instance is None:
        return problems
    expected = {item["specimen_id"] for item in plan["specimens"]
                if item["site"] == instance}
    missing = sorted(expected - built)
    extra = sorted(built - expected)
    if missing or extra:
        problems.append(
            f"--instance {instance} asserts all {len(expected)} of its committed "
            f"specimens; {len(built & expected)} are built "
            f"(missing {len(missing)}, extra {len(extra)}). First missing: {missing[:3]}")
    return problems


def check(plan: dict, nodes: list[dict], instance: str | None, *, verbose: bool = True) -> int:
    """Convert and validate specimen by specimen. Writes nothing; returns an exit code."""
    reference = commitment_reference(plan)
    by_id = {item["specimen_id"]: item for item in plan["specimens"]}
    built = [node for node in nodes if (node["outdir"] / "stamp.json").is_file()]
    if verbose:
        print(f"checking {len(built)} built of {len(nodes)} planned "
              f"({len(plan['specimens'])} committed)")
    built_ids = {node["specimen_id"] for node in built}
    in_scope = {item["specimen_id"] for item in plan["specimens"]
                if instance is None or item["site"] == instance}
    # Verification first, for every node, before a single artifact is converted — the
    # same order the stager uses. A drifted recipe must be reported as drift, not as
    # comparisons of artifacts nobody should be reading.
    gate = builder.structural_gate(plan, built, partial_scope=built_ids != in_scope)
    gate_problems = builder.gate_problems(gate)
    verification = gate["verification_problems"]
    if verification:
        if verbose:
            print(f"REFUSED before reading any artifact: {len(verification)} problem(s)")
            for problem in verification[:5]:
                print(f"  {problem}")
        return 1

    failures = 0
    for node in sorted(built, key=lambda item: item["specimen_id"]):
        _record, problems = convert_node(node, by_id[node["specimen_id"]], reference)
        if verbose:
            print(f"  {node['specimen_id']:34} {'OK' if not problems else 'FAIL'}")
            for problem in problems:
                print(f"      {problem}")
        failures += 1 if problems else 0

    scope_problems = check_scope(plan, instance, built_ids)
    # The same gate the stager enforces, reported here too: otherwise a full `--check`
    # prints "184/184 OK" over a run that may not be measured. The scope is expressed by
    # which nodes are passed — over a half-built tree the pairs and derived specimens it
    # cannot cover are simply not required, which is a scope fact, not a relaxed rule.
    if verbose:
        print(f"converted {len(built) - failures}/{len(built)} without problems")
        for problem in gate_problems:
            print(f"  STRUCTURAL GATE: {problem}")
        for problem in scope_problems:
            print(f"  SCOPE: {problem}")
        if len(built) != len(plan["specimens"]):
            print("NOTE: this is a check, not a staging — the committed set is "
                  f"{len(plan['specimens'])} specimens and nothing was written.")
    return 1 if (failures or scope_problems or gate_problems) else 0


def check_staging_root(out: Path) -> Path:
    resolved = out.resolve()
    try:
        relative = resolved.relative_to(REPO)
    except ValueError:
        raise SystemExit(
            f"staging root {out} is outside the repository; every path in the manifest "
            "must be repository-relative") from None
    if relative.parts and relative.parts[0] in PROTECTED:
        raise SystemExit(
            f"refusing to stage into {relative.parts[0]}/: that namespace holds "
            "committed evidence, not build output")
    if resolved.exists():
        raise SystemExit(f"staging root {out} already exists; stage into a fresh path")
    if is_ignored(relative):
        # A staging root under `build/` cannot be committed, so it could only ever be
        # copied to the published location afterwards — and that copy is an unverified
        # publishing step nobody gates. Stage where it will live.
        raise SystemExit(
            f"refusing to stage into {relative}: it is excluded by .gitignore, so this "
            "staging root could never be the published one. Certificate 1.6 pins the "
            "manifest and every artifact by repository-relative path; stage directly "
            "where they will be committed, for example staging/<run_id>/.")
    return resolved


def is_ignored(relative: Path) -> bool:
    """Whether git would exclude this path. A tree without git cannot answer, and says so
    by not objecting — the check is a guard against a mistake, not an authority."""
    checked = subprocess.run(["git", "check-ignore", "-q", str(relative)],
                             cwd=REPO, capture_output=True, check=False)
    return checked.returncode == 0


SPECIMENS_DIR = "specimens"


def stage(plan: dict, nodes: list[dict], out: Path, *, verbose: bool = True) -> Path:
    """All or nothing: convert every committed specimen, then write, or write nothing.

    `out` is the **run root**, and the published shape is one level of nesting:

        staging/<run_id>/staging_manifest.json
        staging/<run_id>/specimens/<specimen_id>/{spec.bit,attestation.json}

    The consumer derives its staging root from the artifact paths, so its root is
    `specimens/` — which then holds exactly the committed specimen directories and no
    files, while the manifest sits beside it. That is the whole reason for the extra
    level: `load_feature_staging` requires the root it derives to contain *only* those
    directories, and this tool used to write the manifest into it, which made every
    staging it produced uncertifiable (`root_files=1`). Nobody had staged for real, so
    the two rules had never met. Ruled 2026-08-10; the alternative — relaxing the
    verifier — would have widened a consumer rule to fit a producer habit.
    """
    resolved_out = check_staging_root(out)
    reference = commitment_reference(plan)
    by_id = {item["specimen_id"]: item for item in plan["specimens"]}

    planned = {node["specimen_id"]: node for node in nodes}
    # Completeness is measured against what exists on disk, not against the node plan:
    # the plan is derived from the commitment and would always match itself, which would
    # make this refusal unreachable and therefore untested.
    staged = {specimen_id: node for specimen_id, node in planned.items()
              if (node["outdir"] / "stamp.json").is_file()}
    missing = sorted(set(by_id) - set(staged))
    extra = sorted(set(staged) - set(by_id))
    if missing or extra:
        raise SystemExit(
            f"refusing to stage: {len(staged)} of {len(by_id)} committed specimens are "
            f"built (missing {len(missing)}, extra {len(extra)}).\n"
            "  Certificate 1.6 requires set equality with the commitment, so a\n"
            "  successfully built subset is not a smaller staging — it is no staging.\n"
            f"  First missing: {missing[:3]}")

    # Before any conversion and long before any write: the run must be measurable, not
    # merely built. Recomputed from the artifacts, never read from run_report.json, and
    # it covers all three parts of `ready_for_measurement` — verification, the pair gate
    # and the derived gate — because enforcing a subset of a conjunction enforces nothing.
    gate = structural_problems(plan, nodes)
    if gate:
        raise SystemExit(
            "refusing to stage: the structural gate does not pass ({} problem(s)).\n"
            "  A built artifact is not a comparable one.\n  {}".format(
                len(gate), "\n  ".join(gate[:5])))

    records: dict[str, dict] = {}
    problems: list[str] = []
    for specimen_id in sorted(staged):
        node = staged[specimen_id]
        attestation, found = convert_node(node, by_id[specimen_id], reference)
        records[specimen_id] = attestation
        problems.extend(found)
    if problems:
        raise SystemExit("refusing to stage: {} problem(s), first few:\n  {}".format(
            len(problems), "\n  ".join(problems[:5])))

    partial = resolved_out.with_name(resolved_out.name + ".partial")
    if partial.exists():
        raise SystemExit(f"{partial} exists; remove it deliberately")
    # Everything below either ends in the rename or leaves nothing on disk. A staging
    # root that failed halfway is worse than none: it looks like output.
    try:
        partial.mkdir(parents=True)
        specimens_root = partial / SPECIMENS_DIR
        specimens_root.mkdir()
        manifest_entries = []
        for specimen_id in sorted(records):
            node = staged[specimen_id]
            directory = specimens_root / specimen_id
            directory.mkdir()
            bit = directory / "spec.bit"
            bit.write_bytes((node["outdir"] / "spec.bit").read_bytes())
            # `verified_state` checked the source before it was read; this checks what
            # was actually written. A source edited in between those two moments would
            # otherwise be published with its own new hash agreeing with itself.
            staged_hash = builder.sha256_file(bit)
            pinned = records[specimen_id]["outputs"]["spec.bit"]
            if staged_hash != pinned:
                raise SystemExit(
                    f"refusing to stage: {specimen_id} bitstream changed between "
                    f"verification and staging.\n"
                    f"  stamped {pinned}\n  staged  {staged_hash}")
            attestation_bytes = encode(records[specimen_id])
            (directory / "attestation.json").write_bytes(attestation_bytes)
            # The path a reference carries is where the artifact will live after the
            # rename, spelled `specimens/<id>/…` verbatim — the manifest is the path
            # authority for the certificate, so it must not describe the `.partial`.
            final = resolved_out / SPECIMENS_DIR / specimen_id
            manifest_entries.append({
                "specimen_id": specimen_id,
                "bitstream": {"path": str((final / "spec.bit").relative_to(REPO)),
                              "sha256": staged_hash},
                "attestation": {"path": str((final / "attestation.json").relative_to(REPO)),
                                "sha256": hashlib.sha256(attestation_bytes).hexdigest(),
                                "schema_version": "2.0.0"},
            })
        manifest = {
            "schema": "specimen_staging",
            "schema_version": "1.0.0",
            "run_id": reference["run_id"],
            "prediction_commitment": reference,
            "complete": True,
            "specimens": manifest_entries,
        }
        findings = validate_external_schema(manifest, STAGING_SCHEMA, "staging manifest")
        if findings:
            raise SystemExit("refusing to stage: manifest does not validate:\n  "
                             + "\n  ".join(findings))
        (partial / "staging_manifest.json").write_bytes(encode(manifest))
        partial.rename(resolved_out)
    except BaseException as failure:
        # Not `ignore_errors=True`: a cleanup that quietly fails leaves exactly the
        # half-written root this block exists to prevent, and reports the original
        # error as if the tree were clean. If it cannot be removed, say so with the path.
        try:
            if partial.exists():
                shutil.rmtree(partial)
            residue = partial.exists()
        except OSError as cleanup:
            raise SystemExit(
                f"staging failed AND its partial root could not be removed.\n"
                f"  partial root : {partial}\n"
                f"  cleanup error: {cleanup}\n"
                f"  original     : {failure}") from failure
        if residue:
            raise SystemExit(
                f"staging failed AND its partial root still exists after cleanup.\n"
                f"  partial root : {partial}\n"
                f"  original     : {failure}") from failure
        raise
    if verbose:
        print(f"staged {len(manifest_entries)} specimens -> "
              f"{(resolved_out / SPECIMENS_DIR).relative_to(REPO)}/")
        print(f"  manifest: {(resolved_out / 'staging_manifest.json').relative_to(REPO)}")
    return resolved_out


# ---------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, required=True,
                    help="the builder's output root, e.g. build/gate_ff_formal")
    ap.add_argument("--instance", default=None,
                    help="check one mine site; a holdout instance is refused")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="convert and validate, write nothing")
    group.add_argument("--stage", type=Path, default=None,
                       help="write the complete staged set to this fresh directory")
    args = ap.parse_args()

    check_tcl_intent()
    plan = builder.load_commitment()
    mapping = builder.check_site_mapping(plan)
    if args.instance:
        builder.check_instance_scope(plan, args.instance)
    if args.stage is not None and args.instance:
        raise SystemExit("--instance narrows the set; staging is all 184 or nothing")

    root = args.build.resolve()
    nodes = builder.plan_nodes(plan, mapping, root, args.instance)
    for node in nodes:
        if node["node_type"] == "derived":
            base = root / node["instance"] / "base" / "base.dcp"
            if base.is_file():
                node["base_dcp_sha256"] = builder.sha256_file(base)

    with builder.RunLock(root, "stage-" + builder.utc_now()):
        if args.stage is not None:
            stage(plan, nodes, args.stage)
            return 0

        return check(plan, nodes, args.instance)


if __name__ == "__main__":
    raise SystemExit(main())
