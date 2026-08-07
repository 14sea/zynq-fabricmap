#!/usr/bin/env python3
"""Build the committed 184-specimen `clb_ff_config` matrix.

Design of record: `docs/ff_builder_design.md`. This tool is a **deterministic executor**
of a plan that was frozen before it existed. It derives no key space of its own, builds
no subset, and never reads what any specimen is predicted to do — measurement belongs to
`gate_measure_ff.py`, which reads the same commitment independently.

Two authorities, and they are not interchangeable (design §1):

* **A — the commitment** (`predictions.json`, sha256 `5440ef27…`): key space, pairs,
  split, coverage. Everything here is a structural field or a direct consequence.
* **B — the pre-freeze plan** (`docs/ff_preregistration_plan.md` as of `2b40693`, sha256
  `ac9dbab8…`): the execution topology, i.e. which variants need their own
  place-and-route. The commitment's totals are 184/176/154 and nothing else — **120 is
  not readable from the JSON.** Authority B lives only in git history, which is why a
  certification run needs a clone and refuses to start without one (§1.3).

Usage:
    scripts/gate_build_ff_formal.py --build build/gate_ff_formal
    scripts/gate_build_ff_formal.py --build … --instance SLICE_X2Y25   # mine smoke only
    scripts/gate_build_ff_formal.py --build … --report-only
    scripts/gate_build_ff_formal.py --build … --retry-failed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC_V = REPO / "vivado/specimen/specimen_ff_formal.v"
BUILD_TCL = REPO / "vivado/specimen/build_ff_formal.tcl"
DERIVE_TCL = REPO / "vivado/specimen/derive_ff_formal.tcl"
READBACK_TCL = REPO / "vivado/specimen/ff_formal_readback.tcl"
RUN_VIVADO = REPO / "scripts/run_vivado.sh"

COMMITMENT = REPO / "gate_runs/run_2026_08_05_ff/predictions.json"
COMMITTED_SHA256 = "5440ef27acbd5b4f624cae54f4ffad89b3f656c1e6e5fa35b29226ff0d1b2e51"

# Authority B: the plan as it stood when the commitment was emitted. The working-tree
# copy is deliberately NOT this text — `a643992` rewrote it from DRAFT to COMMITTED — so
# the only source is the git object, and falling back to the working tree would silently
# substitute a different plan while every hash still verified.
PLAN_COMMIT = "2b40693"
PLAN_PATH = "docs/ff_preregistration_plan.md"
PLAN_SHA256 = "ac9dbab8ba299360b924dec20507ed3c4f014b276cd1e20d82c25d3e92997a64"

PART = "xc7z010clg400-1"

# Storage-element order. Index k is both the `lsort` position of the elaborated cell and
# the position in the BEL list the Tcl assigns, and the derive flow asserts the two agree
# rather than trusting them to.
FF_ORDER = ("AFF", "A5FF", "BFF", "B5FF", "CFF", "C5FF", "DFF", "D5FF")
MAIN_FFS = ("AFF", "BFF", "CFF", "DFF")

# The six anchor/keeper cells (design §4).
AK_CELLS = ("anchor_lut1", "anchor_lut2", "anchor_ff", "anchor_ff2",
            "q_reduce1", "q_reduce2")

# Nets whose driver and every sink lie inside the anchor/keeper subgraph — tier 2 of the
# comparison (§5.3). Membership is COMPUTED from the readback; this constant is what the
# computation must produce, so a net silently gaining a target sink fails loudly instead
# of quietly dropping out of the tier.
EXPECTED_DEDICATED = frozenset({
    "w1",                # anchor_lut1 -> anchor_lut2
    "w2",                # anchor_lut2 -> anchor_ff, anchor_ff2  (spans both columns)
    "qr1",               # q_reduce1   -> q_reduce2
    "q_OBUF",            # q_reduce2   -> pad
    "anchor_o_OBUF",     # anchor_ff   -> pad
    "anchor_o2_OBUF",    # anchor_ff2  -> pad
    "q", "anchor_o", "anchor_o2",   # the pad nets themselves
})

# Tier 1: local cell facts, hard equality between the two ends of every committed pair.
T1_CELL_KEYS = ("ref", "loc", "bel", "init", "lock_pins")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# --------------------------------------------------------------------------------------
# Authorities
# --------------------------------------------------------------------------------------

def frozen_plan_text() -> bytes:
    """Authority B, from git history only.

    No fallback to the working tree: that copy hashes to something else on purpose, and
    accepting it would defeat the entire pin. A tree without the object is a tree that
    cannot run a certification build, and saying so is the point.
    """
    checked = subprocess.run(
        ["git", "show", f"{PLAN_COMMIT}:{PLAN_PATH}"],
        cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if checked.returncode != 0:
        raise SystemExit(
            f"authority B unavailable: cannot read {PLAN_PATH} at {PLAN_COMMIT}.\n"
            f"  git said: {checked.stderr.decode(errors='replace').strip()}\n"
            "  A certification run requires a working tree whose git history contains\n"
            f"  {PLAN_COMMIT} — a clone, not an archive. The execution topology (15\n"
            "  place-and-routes + 8 derived per instance, hence 120) is not readable\n"
            "  from the commitment, and the working-tree plan is NOT the frozen text.")
    return checked.stdout


def load_commitment() -> dict:
    """Authority A, plus the counts that must recompute from it before anything is built.

    Only structural fields are ever consumed: `specimen_id`, `site`, `variant`, `tile`,
    `tile_type`, `site_prefix`, `split`, `pair_with`, `build_seed`.
    """
    if not COMMITMENT.is_file():
        raise SystemExit(f"commitment missing: {COMMITMENT}")
    digest = sha256_file(COMMITMENT)
    if digest != COMMITTED_SHA256:
        raise SystemExit(
            f"commitment sha256 is {digest}, expected {COMMITTED_SHA256}.\n"
            "  The plan moved; this builder does not cover it.")
    plan = json.loads(COMMITMENT.read_text())

    specimens = plan["specimens"]
    sites = sorted({s["site"] for s in specimens})
    if len(specimens) != 184:
        raise SystemExit(f"expected 184 specimens, commitment has {len(specimens)}")
    if len(sites) != 8:
        raise SystemExit(f"expected 8 site instances, commitment has {len(sites)}")
    for site in sites:
        n = sum(1 for s in specimens if s["site"] == site)
        if n != 23:
            raise SystemExit(f"{site}: expected 23 specimens, commitment has {n}")
    totals = plan["totals"]
    if totals.get("specimens") != 184 or totals.get("predictions") != 176 \
            or totals.get("holdout_predictions") != 154:
        raise SystemExit(f"commitment totals are not 184/176/154: {totals}")

    scopes, directed = committed_pairs(plan)
    if len(scopes) != 168:
        raise SystemExit(f"expected 168 canonical pairs, got {len(scopes)}")
    if len(directed) != 176:
        raise SystemExit(f"expected 176 directed observations, got {len(directed)}")

    # Authority B: the execution topology, and therefore 120.
    frozen = frozen_plan_text()
    got = hashlib.sha256(frozen).hexdigest()
    if got != PLAN_SHA256:
        raise SystemExit(
            f"authority B hash mismatch: {PLAN_PATH}@{PLAN_COMMIT} hashes to {got},\n"
            f"  expected {PLAN_SHA256}. The execution topology is not the reviewed one.")

    variants = sorted({s["variant"] for s in specimens})
    known = sorted(VARIANTS)
    if variants != known:
        missing = sorted(set(variants) - set(known))
        extra = sorted(set(known) - set(variants))
        raise SystemExit(
            "variant set mismatch between the commitment and this builder.\n"
            f"  in the commitment only: {missing}\n"
            f"  in the builder only   : {extra}")

    impls = [s for s in specimens if VARIANTS[s["variant"]]["kind"] == "impl"]
    derived = [s for s in specimens if VARIANTS[s["variant"]]["kind"] == "derived"]
    if len(impls) != 120 or len(derived) != 64:
        raise SystemExit(
            f"execution topology gives {len(impls)} implementations and {len(derived)} "
            "derived; authority B says 120 and 64")
    return plan


def committed_pairs(plan: dict):
    sys.path.insert(0, str(REPO / "scripts"))
    from gate_measure_ff import committed_pairs as _pairs  # noqa: PLC0415

    return _pairs(plan)


# --------------------------------------------------------------------------------------
# Variants (authority B's execution topology) and site mapping (design §3.2)
# --------------------------------------------------------------------------------------

def _variants() -> dict[str, dict]:
    table: dict[str, dict] = {
        "base":       {"kind": "impl", "mode": 0, "idx": 0},
        "ce_tied":    {"kind": "impl", "mode": 2, "idx": 0},
        "sr_tied":    {"kind": "impl", "mode": 3, "idx": 0},
        "async":      {"kind": "impl", "mode": 4, "idx": 0},
        "latch_base": {"kind": "impl", "mode": 5, "idx": 0},
        "latch":      {"kind": "impl", "mode": 6, "idx": 0},
        "clkinv":     {"kind": "impl", "mode": 7, "idx": 0},
    }
    for k, ff in enumerate(FF_ORDER):
        table[f"zrst_{ff}"] = {"kind": "impl", "mode": 1, "idx": k}
        table[f"zini_{ff}"] = {"kind": "derived", "mode": None, "idx": k, "bel": ff}
    return table


VARIANTS = _variants()


def sites_for(target: str) -> dict[str, str]:
    """Target -> anchor and keeper, from the rule rather than from a table (design §3.2).

    A rule, so a ninth instance could not be added by quietly inventing a site for it.
    """
    match = re.fullmatch(r"SLICE_X(\d+)Y(\d+)", target)
    if not match:
        raise SystemExit(f"not a slice site: {target}")
    column, row = int(match.group(1)), int(match.group(2))
    if row != 25:
        raise SystemExit(f"{target}: every committed target is in row 25, this is row {row}")
    return {"target": target,
            "keeper": f"SLICE_X{column}Y20",
            "anchor": f"SLICE_X{column + 2}Y20"}


def check_instance_scope(plan: dict, instance: str) -> None:
    """`--instance` accepts a mine site and nothing else.

    Split out as a pure function so it is testable without git history: the authority-B
    check runs before it in `main`, so a subprocess test of this rule would otherwise be
    testing authority B instead, and would fail from an archive for the wrong reason.
    """
    splits = {s["split"] for s in plan["specimens"] if s["site"] == instance}
    if not splits:
        raise SystemExit(f"--instance {instance}: not a committed site instance")
    if splits != {"mine"}:
        raise SystemExit(
            f"--instance {instance}: split is {sorted(splits)}, not mine.\n"
            "  This flag exists for the mine-instance smoke test. A flag that can\n"
            "  single out a holdout instance is a flag that can be used to look at\n"
            "  holdout evidence one convenient piece at a time.")


def check_site_mapping(plan: dict) -> dict[str, dict[str, str]]:
    """The collision proof of §3.3, recomputed every run rather than cited."""
    targets = sorted({s["site"] for s in plan["specimens"]})
    mapping = {t: sites_for(t) for t in targets}
    used: dict[str, str] = {}
    for target, trio in mapping.items():
        if len(set(trio.values())) != 3:
            raise SystemExit(f"{target}: target, keeper and anchor are not distinct: {trio}")
        for role, site in trio.items():
            if site in used:
                raise SystemExit(f"site {site} used twice: {used[site]} and {target}/{role}")
            used[site] = f"{target}/{role}"
    if len(used) != 24:
        raise SystemExit(f"expected 24 distinct role sites, got {len(used)}")
    # Total separation: every target is row 25, every anchor and keeper row 20. This is
    # what makes the check total instead of case-by-case.
    for target, trio in mapping.items():
        for role in ("anchor", "keeper"):
            if not trio[role].endswith("Y20"):
                raise SystemExit(f"{target}: {role} {trio[role]} is not in row 20")
    return mapping


# --------------------------------------------------------------------------------------
# Recipe, stamps, lock (design §7)
# --------------------------------------------------------------------------------------

def vivado_version() -> str:
    return os.environ.get("FF_VIVADO_VERSION", "2025.2")


def recipe(build_seed: int, tclargs: list[str]) -> dict:
    """Everything that can change what a build MEANS. A difference refuses reuse."""
    return {
        "sources": {str(p.relative_to(REPO)): sha256_file(p)
                    for p in (SPEC_V, BUILD_TCL, DERIVE_TCL, READBACK_TCL,
                              Path(__file__).resolve())},
        "commitment": COMMITTED_SHA256,
        "preregistration_plan": PLAN_SHA256,
        "part": PART,
        "vivado_version": vivado_version(),
        "tclargs": list(tclargs),
        "build_seed": build_seed,
    }


# Keyed by `node_type`, which is the value that travels into the stamp — not by the
# internal `kind`. Two names for one concept is how the first run died.
ARTIFACTS = {"implementation": ("spec.bit", "readback.tsv", "base.dcp"),
             "derived": ("spec.bit", "readback.tsv", "derived.dcp")}

# The six fields every dedicated net must carry, in both the first and the final record.
ROUTEPIN_FIELDS = ("route", "pips", "driver", "sinks", "status", "fixed")


def cache_state(outdir: Path, node: dict) -> tuple[str, str]:
    """`(state, why)`: build / reuse / failed / refuse.

    Artifacts existing is not evidence that they are THIS node's artifacts. Reuse needs a
    stamp naming the instance, the variant, the site mapping, every recipe input and every
    artifact hash. A stamp is written on every attempt, successful or not: a failure that
    left no stamp is indistinguishable from a directory nobody ever built in.
    """
    if not outdir.exists() or not any(outdir.iterdir()):
        return "build", "empty"
    stamp_path = outdir / "stamp.json"
    if not stamp_path.is_file():
        return "refuse", "output directory is not empty and carries no build stamp"
    try:
        stamp = json.loads(stamp_path.read_text())
    except json.JSONDecodeError as exc:
        return "refuse", f"build stamp is unreadable: {exc}"
    for field in ("instance", "variant", "node_type"):
        if stamp.get(field) != node[field]:
            return "refuse", (f"stamp is for {field}={stamp.get(field)!r}, "
                              f"this run wants {node[field]!r}")
    if stamp.get("sites") != node["sites"]:
        return "refuse", "stamp was built against a different site mapping"
    if stamp.get("recipe") != node["recipe"]:
        return "refuse", "stamp was produced by a different recipe"
    if not stamp.get("completed"):
        return "failed", "stamp records a build of this recipe that did not complete"
    for name in ARTIFACTS[node["node_type"]]:
        if not (outdir / name).is_file():
            return "refuse", f"stamp claims success but {name} is missing"
        if stamp.get("artifacts", {}).get(name) != sha256_file(outdir / name):
            return "refuse", f"{name} does not match the hash the stamp recorded"
    if node["node_type"] == "derived":
        if stamp.get("derived_from", {}).get("base_dcp_sha256") != node["base_dcp_sha256"]:
            return "refuse", "stamp derives from a different base checkpoint"
    return "reuse", "stamp matches"


def verified_state(outdir: Path, node: dict) -> tuple[str, str]:
    """The single gate every artifact passes before it is read, on every code path.

    `--report-only` must not be the one flag that skips verification: that is exactly how
    a report gets built on an older run's bitstreams with today's recipe stamped on them.
    """
    state, why = cache_state(outdir, node)
    if state in ("reuse", "failed"):
        return state, why
    raise SystemExit(
        f"{node['specimen_id']}: refusing to use {outdir} — {why}.\n"
        "  Rebuild it, or delete it deliberately if that is what you mean; a report\n"
        "  built on unverified artifacts answers a question nobody asked.")


def write_stamp(outdir: Path, stamp: dict, attempt_id: str) -> None:
    """Atomic, with a unique temporary name.

    A fixed `stamp.json.tmp` is itself a collision: two attempts sharing it can interleave
    writes and produce a well-formed stamp describing neither build. The directory is
    fsynced after the rename so the rename itself is durable.
    """
    tmp = outdir / f".stamp.{attempt_id}.tmp"
    try:
        with tmp.open("w") as handle:
            json.dump(stamp, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, outdir / "stamp.json")
        fd = os.open(outdir, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if tmp.exists():
            tmp.unlink()


class RunLock:
    """Whole-run exclusive lock.

    Two builders over one tree would overwrite each other's stamps and artifacts, and the
    damage would look exactly like a successful run. A stale lock is removed by a human,
    never automatically on a timeout: "the other process is probably dead" is a guess, and
    guessing here silently corrupts a 120-run matrix.
    """

    def __init__(self, root: Path, attempt_id: str) -> None:
        self.path = root / ".builder.lock"
        self.attempt_id = attempt_id
        self.fd: int | None = None

    def __enter__(self) -> RunLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise SystemExit(
                f"another builder holds {self.path}:\n"
                f"  {self.path.read_text().strip()}\n"
                "  Exiting rather than waiting. If that process is gone, delete the lock\n"
                "  deliberately — this tool will not decide that for you.") from None
        os.write(self.fd, json.dumps({
            "attempt_id": self.attempt_id, "pid": os.getpid(),
            "started": utc_now()}).encode() + b"\n")
        os.fsync(self.fd)
        return self

    def __exit__(self, *exc) -> None:
        if self.fd is not None:
            os.close(self.fd)
        self.path.unlink(missing_ok=True)


# --------------------------------------------------------------------------------------
# Node plan
# --------------------------------------------------------------------------------------

def plan_nodes(plan: dict, mapping: dict, root: Path,
               only_instance: str | None) -> list[dict]:
    nodes = []
    for specimen in plan["specimens"]:
        site = specimen["site"]
        if only_instance and site != only_instance:
            continue
        variant = specimen["variant"]
        spec = VARIANTS[variant]
        sites = mapping[site]
        outdir = root / site / variant
        if spec["kind"] == "impl":
            tclargs = [str(outdir), site, sites["anchor"], sites["keeper"],
                       variant, str(spec["mode"]), str(spec["idx"])]
        else:
            tclargs = [str(outdir), str(root / site / "base" / "base.dcp"), site,
                       sites["anchor"], sites["keeper"], variant,
                       str(spec["idx"]), spec["bel"]]
        nodes.append({
            "specimen_id": specimen["specimen_id"],
            "instance": site,
            "variant": variant,
            "node_type": "implementation" if spec["kind"] == "impl" else "derived",
            "kind": spec["kind"],
            "split": specimen["split"],
            "sites": sites,
            "outdir": outdir,
            "tclargs": tclargs,
            "recipe": recipe(specimen["build_seed"], tclargs),
            "base_dcp_sha256": None,
        })
    return nodes


# --------------------------------------------------------------------------------------
# Building
# --------------------------------------------------------------------------------------

def archive_node(node: dict, evidence_root: Path, attempt_id: str) -> Path:
    """Move a node directory into non-overwritable attempt evidence, atomically.

    Retrying may not write into the existing directory: the evidence most likely to be
    destroyed by an in-place rebuild is the failure someone is actively iterating on.
    """
    dest = evidence_root / attempt_id / node["instance"] / node["variant"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise SystemExit(f"evidence path already exists, refusing to overwrite: {dest}")
    os.replace(node["outdir"], dest)
    return dest


def run_vivado(node: dict, tcl: Path, timeout: int) -> tuple[bool, str]:
    node["outdir"].mkdir(parents=True, exist_ok=True)
    checked = subprocess.run(
        [str(RUN_VIVADO), "-mode", "batch", "-nojournal", "-notrace",
         "-log", str(node["outdir"] / "vivado.log"), "-source", str(tcl),
         "-tclargs", *node["tclargs"]],
        cwd=node["outdir"], capture_output=True, text=True, timeout=timeout, check=False)
    output = checked.stdout + checked.stderr
    (node["outdir"] / "run.out").write_text(output)
    produced = all((node["outdir"] / name).is_file()
                   for name in ARTIFACTS[node["node_type"]])
    ok = checked.returncode == 0 and "SPECIMEN_DONE" in output and produced
    return ok, output


def build_node(node: dict, timeout: int, attempt_id: str, seq: int) -> str:
    state, why = cache_state(node["outdir"], node)
    if state == "reuse":
        return "reuse"
    if state == "failed":
        return "failed"
    if state == "refuse":
        raise SystemExit(
            f"{node['specimen_id']}: refusing to touch {node['outdir']} — {why}.\n"
            "  Delete it deliberately if that is what you mean.")

    tcl = BUILD_TCL if node["kind"] == "impl" else DERIVE_TCL
    ok, output = run_vivado(node, tcl, timeout)
    failure: dict | None = None if ok else {"stage": "vivado",
                                            "problems": ["vivado exited non-zero"]}
    if ok:
        # A node is not complete because Vivado exited 0. The route-pin record is checked
        # here, and a failure still writes a stamp — `completed: false` with the reason and
        # the hashes of whatever this attempt produced. A directory holding half an
        # artifact set and no record of the attempt is the state this contract exists to
        # prevent.
        try:
            problems = routepin_problems(read_tsv(node["outdir"] / "readback.tsv"))
        except (OSError, ValueError) as exc:
            problems = [f"cannot read the readback: {exc}"]
        if problems:
            ok = False
            failure = {"stage": "route_pin", "problems": problems}
    stamp = {
        "schema": "ff_formal_stamp/1",
        "node_type": node["node_type"],
        "instance": node["instance"],
        "variant": node["variant"],
        "attempt_id": f"{attempt_id}-{seq}",
        "sites": node["sites"],
        "recipe": node["recipe"],
        "completed": ok,
        "artifacts": {name: sha256_file(node["outdir"] / name)
                      for name in ARTIFACTS[node["node_type"]]
                      if (node["outdir"] / name).is_file()},
    }
    if node["node_type"] == "derived":
        stamp["derived_from"] = {"specimen_id": f"{node['instance']}_base",
                                 "base_dcp_sha256": node["base_dcp_sha256"]}
    if failure is not None:
        stamp["failure"] = failure
    write_stamp(node["outdir"], stamp, f"{attempt_id}-{seq}")
    if not ok:
        if failure and failure["stage"] == "route_pin":
            for problem in failure["problems"][:4]:
                print(f"    route-pin: {problem}")
        for line in output.splitlines():
            if "ERROR" in line:
                print(f"    {line.strip()}")
    return "ok" if ok else "failed"


# --------------------------------------------------------------------------------------
# Readback parsing and the tiered comparison (design §5.3)
# --------------------------------------------------------------------------------------

def read_tsv(path: Path) -> dict[str, str]:
    """Key/value readback, refusing duplicate keys.

    A dict assignment silently keeps the last value, so a record could carry two
    `routepin.final.w1.pips` lines and every "exactly these fields" check would still
    pass while the reader saw only one of them. A duplicate is a malformed record, not a
    preference for the later line.
    """
    out: dict[str, str] = {}
    duplicates: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        key, _, value = line.partition("\t")
        if key in out:
            duplicates.append(key)
            continue
        out[key] = value
    if duplicates:
        raise ValueError(f"{path}: duplicate keys in the record: "
                         f"{sorted(set(duplicates))[:5]}")
    return out


def cell_of(pin: str) -> str:
    """Cell name from a pin path, tolerating the braces Tcl adds around bracketed names."""
    pin = pin.strip().strip("{}")
    return pin.rsplit("/", 1)[0] if "/" in pin else pin


def split_pins(value: str) -> list[str]:
    return [p.strip("{}") for p in re.findall(r"\{[^}]*\}|\S+", value or "")]


def nets_of(readback: dict[str, str]) -> dict[str, dict]:
    nets: dict[str, dict] = {}
    count = int(readback.get("net_count", "0"))
    for n in range(count):
        name = readback.get(f"net.{n}.name", "")
        nets[name] = {
            "driver": readback.get(f"net.{n}.driver", "").strip(),
            "sinks": split_pins(readback.get(f"net.{n}.sinks", "")),
            "route": readback.get(f"net.{n}.route", ""),
            "pips": readback.get(f"net.{n}.pips", ""),
            "route_status": readback.get(f"net.{n}.route_status", ""),
        }
    return nets


def classify_nets(readback: dict[str, str]) -> tuple[set[str], set[str]]:
    """Compute the dedicated set from the netlist; everything else is shared.

    Dedicated: driver and every sink lie inside the anchor/keeper subgraph, where an
    output buffer fed by an anchor/keeper cell counts as a member because it has exactly
    one input and that input is anchor-exclusive.
    """
    nets = nets_of(readback)
    ak = set(AK_CELLS)
    ext = set(ak)
    for info in nets.values():
        if cell_of(info["driver"]) in ak:
            for sink in info["sinks"]:
                cell = cell_of(sink)
                if cell.endswith("_OBUF_inst"):
                    ext.add(cell)
    dedicated, shared = set(), set()
    for name, info in nets.items():
        driver_cell = cell_of(info["driver"])
        sink_cells = {cell_of(s) for s in info["sinks"]}
        if driver_cell in ext and sink_cells <= ext:
            dedicated.add(name)
        else:
            shared.add(name)
    return dedicated, shared


def tier1_view(readback: dict[str, str]) -> dict[str, str]:
    """Local cell facts for the six anchor/keeper cells: hard equality, always."""
    view = {}
    for key, value in readback.items():
        if not key.startswith("ak."):
            continue
        rest = key[3:]
        name, _, field = rest.partition(".")
        if name not in AK_CELLS:
            continue
        if field in T1_CELL_KEYS or field.startswith("prop.") or field.startswith("pin."):
            view[key] = value
    return view


def tier2_view(readback: dict[str, str], dedicated: set[str]) -> dict[str, str]:
    nets = nets_of(readback)
    view = {}
    for name in sorted(dedicated):
        info = nets[name]
        view[f"{name}.driver"] = info["driver"]
        view[f"{name}.sinks"] = " ".join(sorted(info["sinks"]))
        view[f"{name}.route"] = info["route"]
        view[f"{name}.pips"] = info["pips"]
    return view


def compare_pair(a: dict[str, str], b: dict[str, str]) -> dict:
    """Tier 1 and tier 2 hard; tier 3 recorded and reported, never a FAIL."""
    ded_a, shared_a = classify_nets(a)
    ded_b, shared_b = classify_nets(b)
    result = {"t1_diffs": [], "t2_diffs": [], "t3_diffs": [],
              "dedicated": sorted(ded_a), "dedicated_mismatch": None}

    if ded_a != ded_b:
        result["dedicated_mismatch"] = {"only_a": sorted(ded_a - ded_b),
                                        "only_b": sorted(ded_b - ded_a)}
    for expected, got, side in ((EXPECTED_DEDICATED, ded_a, "a"), (EXPECTED_DEDICATED, ded_b, "b")):
        if got != expected:
            result.setdefault("dedicated_unexpected", []).append(
                {"side": side, "missing": sorted(expected - got), "extra": sorted(got - expected)})

    v1a, v1b = tier1_view(a), tier1_view(b)
    for key in sorted(set(v1a) | set(v1b)):
        if v1a.get(key) != v1b.get(key):
            result["t1_diffs"].append({"key": key, "a": v1a.get(key), "b": v1b.get(key)})

    common = ded_a & ded_b
    v2a, v2b = tier2_view(a, common), tier2_view(b, common)
    for key in sorted(set(v2a) | set(v2b)):
        if v2a.get(key) != v2b.get(key):
            result["t2_diffs"].append({"key": key, "a": v2a.get(key), "b": v2b.get(key)})

    nets_a, nets_b = nets_of(a), nets_of(b)
    for name in sorted(shared_a | shared_b):
        ia, ib = nets_a.get(name), nets_b.get(name)
        if ia is None or ib is None:
            result["t3_diffs"].append({"net": name, "what": "present on one side only"})
            continue
        for field in ("driver", "sinks", "route", "pips"):
            va = " ".join(sorted(ia[field])) if field == "sinks" else ia[field]
            vb = " ".join(sorted(ib[field])) if field == "sinks" else ib[field]
            if va != vb:
                result["t3_diffs"].append({"net": name, "what": field})
    return result


def compare_derived(base: dict[str, str], derived: dict[str, str], bel: str) -> dict:
    """Derived specimens get FULL identity — all three tiers, shared nets included.

    Legitimate here precisely because nothing was re-implemented: same routed checkpoint,
    one cell property changed. §5.3 has to tier its comparison because a pair's two ends
    are two different implementations; this is not that.
    """
    diffs = []
    ignore = re.compile(r"^(vivado_version|variant|mode|idx)$")
    keys = set(base) | set(derived)
    for key in sorted(keys):
        if ignore.match(key):
            continue
        if base.get(key) == derived.get(key):
            continue
        diffs.append({"key": key, "base": base.get(key), "derived": derived.get(key)})
    expected = [d for d in diffs
                if d["key"].endswith(".init") and d["base"] == "1'b1" and d["derived"] == "1'b0"]
    unexpected = [d for d in diffs if d not in expected]
    changed_cell = None
    if len(expected) == 1:
        changed_cell = expected[0]["key"]
    return {"expected_init_changes": expected, "unexpected": unexpected,
            "changed_key": changed_cell, "expected_bel": bel}


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", type=Path, required=True)
    ap.add_argument("--evidence", type=Path, default=None)
    ap.add_argument("--instance", default=None,
                    help="mine site only; a holdout instance is refused")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    plan = load_commitment()
    mapping = check_site_mapping(plan)

    if args.instance:
        check_instance_scope(plan, args.instance)

    attempt_id = f"{uuid.uuid4().hex[:12]}-{utc_now()}"
    root = args.build.resolve()
    evidence_root = (args.evidence or (REPO / f"evidence/ff_builder_{datetime.now(timezone.utc).strftime('%Y_%m_%d')}")).resolve()
    nodes = plan_nodes(plan, mapping, root, args.instance)
    impls = [n for n in nodes if n["kind"] == "impl"]
    derived = [n for n in nodes if n["kind"] == "derived"]

    print(f"attempt {attempt_id}")
    print(f"  scope       : {args.instance or 'ALL 8 INSTANCES'}")
    print(f"  nodes       : {len(impls)} implementations + {len(derived)} derived")

    with RunLock(root, attempt_id):
        seq = 0
        if not args.report_only:
            for node in impls:
                seq += 1
                if args.retry_failed and cache_state(node["outdir"], node)[0] == "failed":
                    moved = archive_node(node, evidence_root, attempt_id)
                    print(f"  {node['specimen_id']}: previous failure archived to {moved}")
                state = build_node(node, args.timeout, attempt_id, seq)
                print(f"  {node['specimen_id']:34} {state}")
            for node in derived:
                base_dir = root / node["instance"] / "base"
                base_dcp = base_dir / "base.dcp"
                if not base_dcp.is_file():
                    print(f"  {node['specimen_id']:34} skipped (no base checkpoint)")
                    continue
                node["base_dcp_sha256"] = sha256_file(base_dcp)
                seq += 1
                if args.retry_failed and cache_state(node["outdir"], node)[0] == "failed":
                    moved = archive_node(node, evidence_root, attempt_id)
                    print(f"  {node['specimen_id']}: previous failure archived to {moved}")
                state = build_node(node, args.timeout, attempt_id, seq)
                print(f"  {node['specimen_id']:34} {state}")

        for node in derived:
            base_dcp = root / node["instance"] / "base" / "base.dcp"
            if base_dcp.is_file():
                node["base_dcp_sha256"] = sha256_file(base_dcp)

        report = assemble_report(plan, nodes, mapping, attempt_id, args.instance)
        out = root / "run_report.json"
        out.write_text(json.dumps(report, indent=2) + "\n")
        print_summary(report)
        print(f"\nreport: {out}")
    return exit_code(report)


def parse_routepin(readback: dict[str, str]) -> dict:
    """The `routepin.` namespace of `readback.tsv` -> `{net: {phase: {field: value}}}`.

    Raw fields only. Nothing in the record is a verdict and nothing here reads one: a
    producer boolean saying "route pinning passed" would be exactly the summary the gate
    exists to do without. The record lives inside the readback, so it is pinned by that
    artifact's hash in the stamp and `verified_state` covers it without a sidecar file.
    """
    if readback.get("routepin.schema") != "ff_formal_routepin/2":
        raise ValueError("route-pin record: unexpected schema "
                         f"{readback.get('routepin.schema')!r}")
    declared = split_pins(readback.get("routepin.dedicated", ""))
    if len(declared) != len(set(declared)):
        raise ValueError(f"route-pin record: the dedicated list repeats a net: {declared}")
    if set(declared) != set(EXPECTED_DEDICATED):
        missing = sorted(set(EXPECTED_DEDICATED) - set(declared))
        extra = sorted(set(declared) - set(EXPECTED_DEDICATED))
        raise ValueError("route-pin record: the dedicated set is not the nine "
                         f"(missing {missing}, extra {extra})")

    for label in ("routable", "intrasite"):
        members = split_pins(readback.get(f"routepin.{label}", ""))
        if len(members) != len(set(members)):
            raise ValueError(f"route-pin record: the {label} list repeats a net: {members}")
        if not set(members) <= set(declared):
            raise ValueError(f"route-pin record: the {label} list names something outside "
                             f"the dedicated set: {sorted(set(members) - set(declared))}")

    prefix = "routepin."
    phases = ("first", "final")
    # The WHOLE namespace, not just the phase fields: an unexamined `routepin.foo` would
    # otherwise ride along, and a record that can carry anything is not an exact record.
    seen = {key for key in readback if key.startswith(prefix)}
    expected_keys = {f"{prefix}{key}" for key in
                     ("schema", "dedicated", "routable", "intrasite")}
    expected_keys |= {f"{prefix}{phase}.{name}.{field}"
                      for phase in phases for name in declared
                      for field in ROUTEPIN_FIELDS}
    if seen != expected_keys:
        missing = sorted(expected_keys - seen)
        extra = sorted(seen - expected_keys)
        raise ValueError(f"route-pin record: the namespace is not exactly "
                         f"4 + {len(declared)} nets x 2 phases x {len(ROUTEPIN_FIELDS)} "
                         f"fields (missing {missing[:3]}, extra {extra[:3]})")

    record = {name: {phase: {field: readback[f"{prefix}{phase}.{name}.{field}"]
                             for field in ROUTEPIN_FIELDS}
                     for phase in phases}
              for name in declared}
    return {"nets": record,
            "routable": split_pins(readback.get("routepin.routable", "")),
            "intrasite": split_pins(readback.get("routepin.intrasite", ""))}


def empty_route(value: str) -> bool:
    """Vivado prints an empty route as the empty Tcl list `{}`, and `bool("{}")` is True."""
    return (value or "").strip().strip("{}").strip() == ""


def routepin_problems(readback: dict[str, str]) -> list[str]:
    """Every reason a node's route-pin record is not acceptable, recomputed from raw fields.

    The partition into routed and intrasite is not taken from the file: it is recomputed
    from the readback by `classify_nets` and by `ROUTE_STATUS`, and the file has to agree.
    """
    try:
        record = parse_routepin(readback)
    except ValueError as exc:
        return [str(exc)]

    problems: list[str] = []
    dedicated, _shared = classify_nets(readback)
    if dedicated != set(EXPECTED_DEDICATED):
        problems.append(f"the readback's dedicated set is {sorted(dedicated)}, "
                        f"not the nine")

    nets = record["nets"]
    # "not intrasite" is not the same as routed: UNROUTED and ANTENNAS are neither, and
    # treating them as completion is how an unfinished route passes as a pinned one.
    routed_by_status = {name for name, tags in nets.items()
                        if tags["final"]["status"] == "ROUTED"}
    intrasite_by_status = {name for name, tags in nets.items()
                           if tags["final"]["status"] == "INTRASITE"}
    other = set(nets) - routed_by_status - intrasite_by_status
    if other:
        problems.append("nets whose final ROUTE_STATUS is neither ROUTED nor INTRASITE: "
                        + ", ".join(f"{n}={nets[n]['final']['status']!r}"
                                    for n in sorted(other)))
    if set(record["routable"]) != routed_by_status:
        problems.append(f"declared routable {sorted(record['routable'])} differs from "
                        f"what ROUTE_STATUS says {sorted(routed_by_status)}")
    if set(record["intrasite"]) != intrasite_by_status:
        problems.append(f"declared intrasite {sorted(record['intrasite'])} differs from "
                        f"what ROUTE_STATUS says {sorted(intrasite_by_status)}")

    # Two records emitted independently by the same run must agree about the same fact.
    from_readback = nets_of(readback)
    for name in sorted(nets):
        recorded = from_readback.get(name, {}).get("route_status")
        if recorded is not None and recorded != nets[name]["final"]["status"]:
            problems.append(f"{name}: readback says ROUTE_STATUS {recorded!r} but the "
                            f"route-pin record says {nets[name]['final']['status']!r}")

    for name, tags in sorted(nets.items()):
        first, final = tags["first"], tags["final"]
        # `fixed` is included: the flow sets IS_ROUTE_FIXED before it captures `first`,
        # so the two have no legitimate reason to differ, and excluding the field is
        # exactly how a net that lost its freeze would pass.
        for field in ROUTEPIN_FIELDS:
            if first[field] != final[field]:
                problems.append(f"{name}: {field} changed between the first and the "
                                f"final record")
        if name in routed_by_status:
            if final["fixed"] != "1":
                problems.append(f"{name} is routed but IS_ROUTE_FIXED reads "
                                f"{final['fixed']!r}")
            if empty_route(final["route"]):
                problems.append(f"{name} is routed but its ROUTE is empty")
        else:
            if final["status"] != "INTRASITE":
                problems.append(f"{name}: status is {final['status']!r}, not INTRASITE")
            if not empty_route(final["route"]) or final["pips"].strip():
                problems.append(f"{name} is intrasite but carries route/pips")
    return problems


def pair_status(result: dict) -> str:
    """`pass` or `FAIL` for one compared pair — the ONE definition of the T1/T2 gate.

    Extracted because it has two consumers that must not drift: this builder, and the
    stager, which recomputes the gate from the readbacks before it will stage anything.
    T3 is absent on purpose: shared nets are diagnostic and never a FAIL.
    """
    return "pass" if (not result["t1_diffs"] and not result["t2_diffs"]
                      and not result["dedicated_mismatch"]
                      and "dedicated_unexpected" not in result) else "FAIL"


def required_identities(plan: dict, nodes: list[dict]) -> tuple[list, list, list]:
    """The exact pair and derived identities a gate over these nodes must cover.

    Derived from the commitment restricted to the node scope, never from what happens to
    have been compared — "every record present passed" is not a gate, because a run that
    lost half its records satisfies it.
    """
    ids = {node["specimen_id"] for node in nodes}
    scopes, _direction = committed_pairs(plan)
    pairs, straddling = [], []
    for key in scopes:
        members = set(key)
        if members <= ids:
            pairs.append(sorted(key))
        elif members & ids:
            straddling.append(sorted(key))
    derived = sorted(node["specimen_id"] for node in nodes if node["kind"] == "derived")
    return sorted(pairs), derived, straddling


def structural_gate(plan: dict, nodes: list[dict], *, partial_scope: bool = False) -> dict:
    """Verify every artifact, then compare exactly what the commitment requires.

    Order is the point. Every node passes `verified_state` BEFORE a single `readback.tsv`
    is opened, so a tree whose recipe has drifted reports the drift — it does not report
    stale T1/T2 findings computed from artifacts nobody should be reading. Both the pair
    comparison and the derived comparison live here, so there is one structural gate and
    not two that can be enforced separately.
    """
    verification: list[str] = []
    for node in sorted(nodes, key=lambda item: item["specimen_id"]):
        try:
            state, why = verified_state(node["outdir"], node)
        except SystemExit as refusal:
            # `verified_state` already names the specimen; prefixing it again reads as
            # two different specimens on one line.
            verification.append(str(refusal).splitlines()[0].strip())
            continue
        if state != "reuse":
            verification.append(f"{node['specimen_id']}: {why}")

    pairs_required, derived_required, straddling = required_identities(plan, nodes)
    for pair in [] if partial_scope else straddling:
        verification.append(
            f"committed pair {pair[0]} <-> {pair[1]}: only one endpoint is in scope, "
            "so the pair can never be compared")

    gate = {
        "partial_scope": partial_scope,
        "pairs_required": len(pairs_required),
        "pairs_required_ids": pairs_required,
        "derived_required": len(derived_required),
        "derived_required_ids": derived_required,
        "verification_problems": verification,
        "pairs": [],
        "derived": [],
    }
    if verification:
        return gate  # nothing has been read, and nothing will be

    by_id = {node["specimen_id"]: node for node in nodes}
    # A malformed readback is a refusal, not a traceback: `read_tsv` rejects duplicate
    # keys, and a gate that crashes on bad input has not judged it.
    readbacks: dict[str, dict[str, str]] = {}
    for node in sorted(nodes, key=lambda item: item["specimen_id"]):
        try:
            readbacks[node["specimen_id"]] = read_tsv(node["outdir"] / "readback.tsv")
        except (OSError, ValueError) as exc:
            gate["verification_problems"].append(f"{node['specimen_id']}: {exc}")
    if gate["verification_problems"]:
        return gate

    # The route-pin record, recomputed here as well. `build_node` checked it before it
    # wrote `completed: true`, and this does not take that on trust: the stamp's boolean
    # is a producer summary, and the gate reads the raw fields for itself.
    for node in sorted(nodes, key=lambda item: item["specimen_id"]):
        for problem in routepin_problems(readbacks[node["specimen_id"]]):
            gate["verification_problems"].append(f"{node['specimen_id']}: {problem}")
    if gate["verification_problems"]:
        return gate

    for a_id, b_id in pairs_required:
        result = compare_pair(readbacks[a_id], readbacks[b_id])
        result["pair"] = [a_id, b_id]
        result["status"] = pair_status(result)
        gate["pairs"].append(result)
    for specimen_id in derived_required:
        node = by_id[specimen_id]
        base_id = f"{node['instance']}_base"
        if base_id not in readbacks:
            gate["verification_problems"].append(
                f"{specimen_id}: its base specimen {base_id} is not in scope")
            continue
        result = compare_derived(readbacks[base_id], readbacks[specimen_id],
                                 VARIANTS[node["variant"]]["bel"])
        result["specimen"] = specimen_id
        result["status"] = "pass" if len(result["expected_init_changes"]) == 1 \
            and not result["unexpected"] else "FAIL"
        gate["derived"].append(result)
    return gate


def gate_findings(gate: dict) -> dict[str, list[str]]:
    """Every reason a structural gate result is not measurable, **per category**.

    Structured rather than flat because the categories decide named fields. Classifying a
    finding by whether its sentence starts with the word "pair" is not classification: a
    missing `pairs_required_ids` produced the message "the record does not declare its
    required pair set", which begins with "the", so `pair_gate_pass` reported True about
    a gate that could not be evaluated at all. Strings are for display; the buckets are
    the decision.
    """
    findings: dict[str, list[str]] = {
        "verification": list(gate.get("verification_problems", [])),
        "pair": [],
        "derived": [],
    }
    if findings["verification"]:
        # Nothing was compared; saying more about pairs or derived would be inventing it.
        return findings

    # Key names are spelled out rather than pluralised from the label: "derived" does not
    # pluralise, and a KeyError-shaped bug here reads as a missing declaration.
    for label, records, key, ids_key, count_key in (
            ("pair", gate["pairs"], "pair", "pairs_required_ids", "pairs_required"),
            ("derived", gate["derived"], "specimen", "derived_required_ids",
             "derived_required")):
        bucket = findings[label]
        if ids_key not in gate or count_key not in gate:
            # A record that does not declare what it had to cover cannot be judged, and
            # "every record present passed" is the shape a trimmed report arrives in.
            bucket.append(f"the record does not declare its required {label} set")
            continue
        required = [tuple(item) if isinstance(item, list) else item
                    for item in gate[ids_key]]
        reported = [tuple(record[key]) if isinstance(record[key], list) else record[key]
                    for record in records]
        if len(reported) != len(set(reported)):
            bucket.append(f"{label} records contain duplicates")
        missing = sorted(set(required) - set(reported))
        extra = sorted(set(reported) - set(required))
        if missing or extra:
            bucket.append(
                f"{label} records do not cover the required set "
                f"(required {len(required)}, reported {len(reported)}, "
                f"missing {len(missing)}, extra {len(extra)}): first missing {missing[:2]}")
        if len(records) != gate[count_key]:
            bucket.append(f"{label} record count {len(records)} != required "
                          f"{gate[count_key]}")
        if not required and not gate.get("partial_scope"):
            bucket.append(f"no {label} is in scope: an unrun gate is not a pass")
        for record in records:
            if record["status"] != "pass":
                keys = [d["key"] for d in record.get("t1_diffs", [])
                        + record.get("t2_diffs", [])]
                keys += [d["key"] for d in record.get("unexpected", [])]
                detail = f" keys={keys[:4]}" if keys else ""
                bucket.append(f"{label} {record[key]}: {record['status']}{detail}")
    return findings


def gate_problems(gate: dict) -> list[str]:
    """`gate_findings` flattened for display and refusal messages, in evaluation order."""
    findings = gate_findings(gate)
    return findings["verification"] + findings["pair"] + findings["derived"]


def readiness(report: dict) -> dict:
    """The single decision every consumer of a run shares.

    `complete` answers "was everything built", and the exit code used to follow it alone.
    That is how the 2026-08-06 run exited 0 with a failing pair, and why the stager would
    have accepted its artifacts: build completeness is a *component* of readiness, never
    a synonym for it. An empty set is not a pass in either gate — a run that compared no
    pair has not passed the pair gate, it has not run it.
    """
    build_complete = (
        report["implementations_built"] == report["implementations_required"]
        and report["specimens_built"] == report["specimens_required"])
    findings = gate_findings(report)
    blocked = bool(findings["verification"])
    return {
        "build_complete": build_complete,
        "pair_gate_pass": not blocked and not findings["pair"],
        "derived_gate_pass": not blocked and not findings["derived"],
        "ready_for_measurement": build_complete and not any(findings.values()),
        "pairs_compared": len(report["pairs"]),
        "structural_problems": (findings["verification"] + findings["pair"]
                                + findings["derived"]),
        "pair_failures": [p["pair"] for p in report["pairs"] if p["status"] == "FAIL"],
        "derived_failures": [d["specimen"] for d in report["derived"]
                             if d["status"] == "FAIL"],
    }


def exit_code(report: dict) -> int:
    """The builder's exit status follows readiness, not build completeness."""
    return 0 if readiness(report)["ready_for_measurement"] else 1


def assemble_report(plan: dict, nodes: list[dict], mapping: dict,
                    attempt_id: str, only_instance: str | None) -> dict:
    """The run record. Every structural fact in it comes from `structural_gate()`.

    It used to build its own pair and derived comparisons, which is how the stager could
    enforce two thirds of a three-part verdict: two implementations of one gate are two
    gates. The counting stays here; the judging does not.
    """
    states = {}
    for node in nodes:
        state, why = cache_state(node["outdir"], node)
        states[node["specimen_id"]] = {"state": state, "why": why}

    built_impl = sum(1 for n in nodes if n["kind"] == "impl"
                     and states[n["specimen_id"]]["state"] == "reuse")
    built_all = sum(1 for n in nodes if states[n["specimen_id"]]["state"] == "reuse")

    gate = structural_gate(plan, nodes)
    by_id = {n["specimen_id"]: n for n in nodes}
    for record in gate["derived"]:
        node = by_id[record["specimen"]]
        record["base_dcp_sha256"] = node["base_dcp_sha256"]
        record["derived_dcp_sha256"] = sha256_file(node["outdir"] / "derived.dcp")
        record["bitstream_sha256"] = sha256_file(node["outdir"] / "spec.bit")
        record["readback_sha256"] = sha256_file(node["outdir"] / "readback.tsv")

    report = {
        "schema": "ff_formal_run/2",
        "attempt_id": attempt_id,
        "scope": only_instance or "all",
        "commitment_sha256": COMMITTED_SHA256,
        "preregistration_plan_sha256": PLAN_SHA256,
        "site_mapping": mapping,
        "implementations_built": built_impl,
        "implementations_required": 120,
        "specimens_built": built_all,
        "specimens_required": 184,
        "node_states": states,
        **gate,
    }
    # `complete` is retained with its original meaning — everything was BUILT — and is
    # deliberately no longer the run's verdict. `readiness()` is.
    report["complete"] = (built_impl == 120 and built_all == 184)
    report.update(readiness(report))
    return report


def print_summary(report: dict) -> None:
    print("\n--- run accounting -------------------------------------------------")
    print(f"  implementations : {report['implementations_built']} / 120")
    print(f"  specimens       : {report['specimens_built']} / 184")
    print(f"  build complete  : {report['build_complete']}")
    pairs = [p for p in report["pairs"] if p["status"] != "unbuilt"]
    failed = [p for p in pairs if p["status"] == "FAIL"]
    t3 = sum(len(p.get("t3_diffs", [])) for p in pairs)
    print(f"  pairs compared  : {len(pairs)}  T1/T2 failures: {len(failed)}")
    print(f"  T3 diagnostics  : {t3} field differences on shared nets (never a FAIL)")
    drv = [d for d in report["derived"] if d["status"] != "unbuilt"]
    bad = [d for d in drv if d["status"] == "FAIL"]
    print(f"  derived checked : {len(drv)}  failures: {len(bad)}")
    print(f"  pair gate       : {'pass' if report['pair_gate_pass'] else 'FAIL'}"
          f"   derived gate: {'pass' if report['derived_gate_pass'] else 'FAIL'}")
    print(f"  READY FOR MEASUREMENT: {report['ready_for_measurement']}")
    for pair in report["pair_failures"]:
        print(f"    pair FAIL: {pair[0]} <-> {pair[1]}")
    if not report["ready_for_measurement"]:
        print("  This run may not be staged or measured. A built artifact is not a\n"
              "  comparable one, and the pair gate is a stop condition, not a report.")


if __name__ == "__main__":
    sys.exit(main())
