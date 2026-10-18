#!/usr/bin/env python3
"""B4 — the HOST-ONLY EXPLORATION HARNESS (docs/b4_architecture.md sections 8, 9, 9.1–9.3; the owner's ruling of 2026-10-18 on
unit 2b-4a). It runs the seven arms per pair on the FORMAL model, audits every run, computes K7 / K9 / K10's data and the
descriptive statistics, and archives everything typed — values beside the fixed thresholds, NEVER a gate verdict.

    b4_sim.py --label b4-sim-1 --seeds 32 --deadline-s 3600 [--out evidence/b4/sim/<label>_<UTC>]

NOTHING IS AUTHORISED BY THIS FILE: running it is a separate authorisation (ruling section 5). The CLI has no fixture,
no allow-dirty, no test mode; a test drives `run_batch` on a hermetic repository copy with its own `port_factory`.

PRE-FLIGHT (no write on any failure; exit 2): the label is `b4-sim-<n>`; S and the deadline are positive ints; the tree is
clean (`git status --porcelain` empty, no override); the formal hypothesis loads (not a fixture), the mapping, the truth
fabric; the root's copies of the formal inputs hash to the pinned digests; every exclusion source reads; the output
directory lies directly under `evidence/b4/sim/`, is named `<label>_…`, follows no symlink and does not exist. Then the
directory is created EXCLUSIVELY and the batch begins; the deadline counts from the pre-flight's start.

FREEZING ORDER: `seeds.json` (the anchor, the master, the exclusion snapshot, every planned pair) is written, then
`manifest.json` (HEAD, every input's digest, the tool files' digests, the constants, the thresholds table), and only then
the first observation. An initialisation failure after the directory exists leaves `INIT_FAILED.json`.

PER PAIR, IN THE FIXED ORDER R → F → O → X → D → Ω → A0 (one worker, never more): a new port per arm; the engine's
`RunResult` is written AT ONCE, exclusively, before any audit; then the typed completion checks (section 4.3), the replay,
the ledger recompute (K7 a), the given-view checks; a finding is `invalid`. After F the D view is built from F's rebuilt
map (`b4_controls`); after O the K7 prefix snapshots at every grid budget; after the arms K9 and K10 on their own ports;
the curves; the pair index last. After every pair the HEAD and the input digests are held to the manifest (a drift is
`invalid`). Every file is validated against `b4_sim_schema` BEFORE it is written.

STOP RULES (section 9.1; fail-closed): a DOMAIN, another refusal, a control failure, a replay or recompute finding, a
K10 `comparable = False`, a schema finding, an input drift or an unexpected exception is `invalid`; the soft deadline
(`b4_deadline`, checked before and after every arm, every replay, every snapshot, every K9 pair, every K10 unit, every
statistics unit) or an external interrupt is `incomplete`. In every case what has returned is on disk, `STOPPED.json`
names the kind, the pair, the stage and the whole planned list (unstarted pairs `not_started`, an interrupted engine call
`result_unavailable`), and `sim_report.json` carries the status, the identity and the archive index — a pooled numeric
summary ONLY when the batch is `complete`. Nothing is skipped, swapped or redrawn. Exit codes: 0 complete, 1 invalid,
2 refused / init failed, 3 incomplete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_carto as bc  # noqa: E402
import b4_controls as ctl  # noqa: E402
import b4_engine as be  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_gate_stats as gs  # noqa: E402
import b4_k10 as k10  # noqa: E402
import b4_k9 as k9  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_replay as br  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_snapshot as sn  # noqa: E402
import b4_stats as st  # noqa: E402
import b4_thresholds as th  # noqa: E402
from b4_deadline import Deadline, StopWork  # noqa: E402

SIM_REL = bs.SIM_REL
LABEL_RE = re.compile(r"^b4-sim-[1-9][0-9]*$")
ROLES = sc.ROLES
ENGINE_ARM = {"R": "R", "F": "F", "O": "O", "X": "X", "D": "F", "Omega": "F", "A0": "F"}
GRID = th.GRID
B_MAX = th.B_MAX
PROBES = th.PROBES
EXPECTED_COST = {role: {"base": 1, "probes": PROBES if role == "F" else 0, "search": B_MAX, "holdout": 1} for role in ROLES}
STANDING = ("exploration data under the label given, S as planned; not a gate verdict; the thresholds of docs/b4_architecture.md "
            "v0.1.14 section 9 are listed for reference only; candidate B* / N are estimates on this S, never the formal S = 200's")
ROOT_INPUTS = ("docs/b4_architecture.md", "b4/IMPORT.json", hy.HYPOTHESIS_REL, bm.CERTIFICATE_REL)


class Refusal(Exception):
    """A pre-flight refusal: nothing was written."""


class Invalid(Exception):
    def __init__(self, kind: str, detail: str, role: str | None = None, stage: str = ""):
        super().__init__(detail)
        self.kind, self.detail, self.role, self.stage = kind, detail, role, stage


# ------------------------------------------------------------------ small helpers
def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    return sha_bytes(Path(p).read_bytes())


def git(root: Path, *args) -> str:
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise Refusal(f"git {' '.join(args)} failed in {root}: {p.stderr.strip()}")
    return p.stdout


def porcelain(root: Path) -> list[str]:
    return [ln for ln in git(root, "status", "--porcelain", "--untracked-files=all").splitlines() if ln.strip()]


def tool_files(code_root: Path) -> list[str]:
    out = sorted(str(p.relative_to(code_root)) for p in (code_root / "b4/host").glob("*.py"))
    out += sorted(str(p.relative_to(code_root)) for p in (code_root / "b4/schemas").glob("*"))
    return out


def input_snapshot(root: Path, hypothesis: hy.Hypothesis) -> tuple[dict, dict]:
    """The digests of every root-relative input the batch depends on, and of the tool files (from the code tree)."""
    inputs: dict[str, str] = {}
    for rel in ROOT_INPUTS:
        p = root / rel
        if not p.is_file():
            raise Refusal(f"the input {rel} is missing under the root")
        inputs[rel] = sha_file(p)
    if inputs[hy.HYPOTHESIS_REL] != hy.HYPOTHESIS_SHA256:
        raise Refusal("the root's hypothesis file does not hash to the pinned formal digest")
    if inputs[bm.CERTIFICATE_REL] != bm.CERTIFICATE_SHA256:
        raise Refusal("the root's certificate does not hash to the pinned digest")
    for s in hypothesis.doc["sources"]:
        if s.get("kind") in ("repository_document", "certificate_mapping") and "root" not in s:
            rel = s["path"]
            p = root / rel
            if not p.is_file():
                raise Refusal(f"the hypothesis source {rel} is missing under the root")
            got = sha_file(p)
            if got != s["sha256"]:
                raise Refusal(f"the hypothesis source {rel} hashes to {got[:16]}…, not its recorded digest")
            inputs[rel] = got
    tools = {rel: sha_file(REPO_ROOT / rel) for rel in tool_files(REPO_ROOT)}
    return inputs, tools


def json_text(doc) -> bytes:
    return (json.dumps(doc, indent=1, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def write_exclusive(path: Path, doc, validator=None) -> dict:
    """Validate, then write to a .part file and LINK it to the final name (fails if the name exists); never overwrite."""
    if validator is not None:
        f = validator(doc)
        if f:
            raise Invalid("schema", f"{path.name}: " + "; ".join(f[:6]), stage="write")
    nf = gs.finite_findings(doc)
    if nf:
        raise Invalid("schema", f"{path.name}: " + "; ".join(nf[:3]), stage="write")
    data = json_text(doc)
    part = path.with_name(path.name + f".{os.getpid()}.part")
    with open(part, "xb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        os.link(part, path)
    finally:
        os.unlink(part)
    return {"path": path.name, "sha256": sha_bytes(data), "size": len(data)}


# ------------------------------------------------------------------ pre-flight
def preflight(root: Path, label: str, count: int, deadline_s: int, out: Path | None) -> dict:
    if not isinstance(label, str) or not LABEL_RE.match(label):
        raise Refusal(f"the label {label!r} is not an exploration label b4-sim-<n> (the gate's label is unit 2b-4's)")
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise Refusal("--seeds must be a positive int")
    if not isinstance(deadline_s, int) or isinstance(deadline_s, bool) or deadline_s <= 0:
        raise Refusal("--deadline-s must be a positive int (no default)")
    root = Path(root).resolve()
    dirty = porcelain(root)
    if dirty:
        raise Refusal(f"the tree is not clean ({len(dirty)} entries; the first: {dirty[0]!r}); there is no override")
    head = git(root, "rev-parse", "HEAD").strip()
    try:
        hypothesis = hy.load()
        mapping = bm.site_mapping()
    except (hy.HypothesisRefusal, bm.MappingRefusal) as exc:
        raise Refusal(f"the formal inputs do not load: {exc}") from None
    if hypothesis.fixture is not False or hypothesis.sha256 != hy.HYPOTHESIS_SHA256:
        raise Refusal("the hypothesis is not the formal one")
    fabric = fm.Fabric(mapping, hypothesis)
    if fabric.source["kind"] != "truth":
        raise Refusal("the fabric is not the truth")
    inputs, tools = input_snapshot(root, hypothesis)
    try:
        exclusion = bs.load_exclusion_set(root)
    except bs.ExclusionSourceRefusal as exc:
        raise Refusal(f"the exclusion set cannot be loaded: {exc}") from None
    ns = root / SIM_REL
    stamp = utc().replace("-", "").replace(":", "")
    out_p = Path(out) if out is not None else ns / f"{label}_{stamp}"
    out_p = out_p if out_p.is_absolute() else root / out_p
    if out_p.is_symlink() or out_p.exists():
        raise Refusal(f"the output directory {out_p} exists (or is a symlink); nothing is overwritten")
    parent = out_p.parent
    if parent.exists() and parent.resolve() != ns.resolve():
        raise Refusal(f"the output directory must lie directly under {SIM_REL}/ (resolved); got {out_p}")
    if not parent.exists() and parent != ns:
        raise Refusal(f"the output directory must lie directly under {SIM_REL}/; got {out_p}")
    if not out_p.name.startswith(label + "_"):
        raise Refusal(f"the output directory's name must begin with {label}_")
    return {"root": root, "head": head, "hypothesis": hypothesis, "mapping": mapping, "fabric": fabric, "inputs": inputs, "tools": tools,
            "exclusion": exclusion, "out": out_p, "label": label, "count": count, "deadline_s": deadline_s}


# ------------------------------------------------------------------ the batch
class Batch:
    def __init__(self, ctx: dict, dl: Deadline, port_factory):
        self.c = ctx
        self.dl = dl
        self.port_factory = port_factory or (lambda fabric, role, pair: ex.ObservationPort(fabric))
        self.out: Path = ctx["out"]
        self.files: list[dict] = []
        self.pairs: list[tuple[int, int]] = []
        self.planned: list[dict] = []
        self.rows: list[dict] = []
        self.seeds_sha: str | None = None
        self.manifest_sha: str | None = None
        self.summary: dict | None = None
        self.stats_record: dict | None = None
        self.current: dict = {"pair": None, "stage": "init", "role": None}

    # -- writing
    def write(self, rel: str, doc, validator) -> dict:
        e = write_exclusive(self.out / rel, doc, validator)
        e["path"] = rel
        self.files.append(e)
        return e

    # -- init: seeds, then manifest, then (and only then) observations
    def init(self) -> None:
        c = self.c
        master = bs.master_seed(c["label"], hy.HYPOTHESIS_SHA256)
        self.pairs = bs.pair_seeds(master, c["count"], c["exclusion"].values)
        exd = c["exclusion"].as_dict()
        seeds = {"schema": "b4_sim_seeds", "schema_version": "1.0.0", "label": c["label"],
                 "anchor": {"rule": th.THRESHOLDS["anchor"]["rule"], "hypothesis_sha256": hy.HYPOTHESIS_SHA256, "label": c["label"]},
                 "master_seed": master, "count": c["count"], "pairs": [list(p) for p in self.pairs],
                 "exclusion": {"sources": exd["sources"], "b4_exposed_values": exd["b4_exposed_values"], "sim_registry": exd["sim_registry"], "pooled_total": exd["pooled_total"]},
                 "generated_utc": utc()}
        self.seeds_sha = self.write("seeds.json", seeds, sc.seeds_findings)["sha256"]
        self.planned = [{"pair": r, "landscape_seed": l, "operator_seed": o, "status": "not_started", "arms": {role: "not_started" for role in ROLES},
                         "k7": "not_started", "k9": "not_started", "k10": "not_started"} for r, (l, o) in enumerate(self.pairs)]
        h, m = c["hypothesis"], c["mapping"]
        manifest = {"schema": "b4_sim_manifest", "schema_version": "1.0.0", "label": c["label"], "count": c["count"], "generated_utc": utc(), "head": c["head"],
                    "repo_root_kind": "the repository root the batch read its inputs from (git HEAD above); the model code is the b4/host tree of the tool files",
                    "deadline_s": c["deadline_s"], "arm_order": list(ROLES), "engine_arm": dict(ENGINE_ARM), "budget": B_MAX, "grid": list(GRID),
                    "constants": {"engine": {"version": be.ENGINE_VERSION, "mu": be.MU, "lambda": be.LAMBDA, "kmax": be.KMAX}, "cartographer": bc.CARTO_VERSION,
                                  "task": bl.TASK_VERSION, "probes_per_F": PROBES, "expected_cost": EXPECTED_COST, "k9_panel": k9.PANEL_VERSION, "k10_salt": k10.SALT, "tau": k10.TAU,
                                  "prng": "b4_rng.Rng (xorshift64, a derived copy of b1_carto.Rng); the bootstrap random.Random", "anchor": th.THRESHOLDS["anchor"], "controls": th.THRESHOLDS["controls"]},
                    "thresholds": th.THRESHOLDS, "inputs": c["inputs"], "tool_files": c["tools"],
                    "hypothesis": {"path": h.path, "sha256": h.sha256, "version": h.version, "fixture": h.fixture, "sources": h.doc["sources"]},
                    "mapping": {"site": m.site, "certificate": m.certificate_rel, "certificate_sha256": m.certificate_sha256, "addresses": list(m.addresses)},
                    "fabric": dict(c["fabric"].source),
                    "exclusion": {"historical_sources": len(exd["sources"]), "pooled_total": exd["pooled_total"], "sim_registry": exd["sim_registry"], "sim_registry_note": exd["sim_registry_note"]},
                    "seeds_sha256": self.seeds_sha, "note": "written before the first observation; held at every pair's end and at the batch's end"}
        self.manifest_sha = self.write("manifest.json", manifest, sc.manifest_findings)["sha256"]

    # -- checkpoints
    def hold_inputs(self, stage: str) -> None:
        c = self.c
        head = git(c["root"], "rev-parse", "HEAD").strip()
        if head != c["head"]:
            raise Invalid("input_drift", f"HEAD moved from {c['head'][:12]} to {head[:12]} ({stage})", stage=stage)
        for rel, sha in c["inputs"].items():
            if sha_file(c["root"] / rel) != sha:
                raise Invalid("input_drift", f"the input {rel} changed during the batch ({stage})", stage=stage)
        for rel, sha in c["tools"].items():
            if sha_file(REPO_ROOT / rel) != sha:
                raise Invalid("input_drift", f"the tool file {rel} changed during the batch ({stage})", stage=stage)

    def hold_tree(self) -> None:
        """At the end: the only untracked / changed entries are this batch's own output."""
        c = self.c
        own = str(self.out.relative_to(c["root"])).rstrip("/") + "/"
        for ln in porcelain(c["root"]):
            path = ln[3:].strip()
            if not (ln.startswith("??") and (path == own or path.startswith(own))):
                raise Invalid("input_drift", f"the working tree carries a change that is not this batch's output: {ln!r}", stage="final")

    # -- one pair
    def run_pair(self, r: int) -> None:
        c = self.c
        l, o = self.pairs[r]
        plan = self.planned[r]
        plan["status"] = "in_progress"
        self.current = {"pair": r, "stage": "arms", "role": None}
        pdir = self.out / f"pair_{r:03d}"
        pdir.mkdir(exist_ok=False)
        task = bl.make_task(l, c["mapping"].addresses)
        fabric, mapping = c["fabric"], c["mapping"]
        results: dict[str, dict] = {}
        views: dict[str, bc.MapView] = {}
        x_seed = ctl.x_control_seed(l, o)
        for role in ROLES:
            self.current["role"] = role
            self.dl.check()
            kw = {}
            if role == "X":
                kw["control_seed"] = x_seed
            elif role in ("D", "Omega", "A0"):
                kw["view"] = views[role]
            port = self.port_factory(fabric, role, r)
            plan["arms"][role] = "in_flight"
            t0 = time.monotonic()
            try:
                res = be.run(ENGINE_ARM[role], task, port, o, B_MAX, **kw)
            except KeyboardInterrupt:
                plan["arms"][role] = "result_unavailable"
                raise
            except Exception as exc:  # noqa: BLE001 — the engine returned no RunResult: unexpected, invalid, the arm named
                plan["arms"][role] = "result_unavailable"
                raise Invalid("unexpected_exception", f"the engine raised {type(exc).__name__}: {exc}", role=role, stage="engine")
            wall = time.monotonic() - t0
            d = res.as_dict()
            self.write(f"pair_{r:03d}/arm_{role}.result.json",
                       {"schema": "b4_sim_arm_result", "schema_version": "1.0.0", "pair": r, "role": role, "engine_arm": ENGINE_ARM[role], "landscape_seed": l,
                        "operator_seed": o, "budget": B_MAX, "port_calls": port.calls, "wall_s": round(wall, 6), "written_utc": utc(), "result": d},
                       lambda doc: sc.arm_result_findings(doc, task))
            plan["arms"][role] = "written"
            results[role] = d
            self.dl.check()
            completion = completion_findings(d, role, task, port.calls, views.get(role))
            replay = br.replay(d, task)
            self.dl.check()
            rc = sn.recompute_findings(d, task)
            states = sn.arm_states(d, task)
            view_f: list[str] = []
            if role in ("D", "Omega", "A0"):
                if d["given_view"] != views[role].as_dict():
                    view_f.append("the recorded given view is not the one handed to the arm")
                if role == "D":
                    view_f += ctl.verify_d_view(d["given_view"], results["F"], task)
            invalid = bool(completion or replay or rc["findings"] or view_f)
            self.write(f"pair_{r:03d}/arm_{role}.audit.json",
                       {"schema": "b4_sim_arm_audit", "schema_version": "1.0.0", "pair": r, "role": role, "completion_findings": completion, "replay_findings": replay,
                        "recompute": {k: v for k, v in rc.items() if k != "relations_final"} | {"relations_final_sha256": None if rc["relations_final"] is None else ex.sha256_json(rc["relations_final"])},
                        "states": states, "view_findings": view_f, "invalid": invalid, "audited_utc": utc()}, sc.arm_audit_findings)
            if invalid:
                kind = "domain" if d.get("terminal") else "control_failure" if d.get("control_failure") else "refusal" if d.get("other_refusal") else "contract"
                raise Invalid(kind, "; ".join((completion + replay + rc["findings"] + view_f)[:6]), role=role, stage="audit")
            plan["arms"][role] = "audited"
            if role == "F":
                self.dl.check()
                try:
                    dv, dinfo = ctl.d_view(d, task)
                except ctl.ControlInputRefusal as exc:
                    raise Invalid("contract", f"D's input cannot be built from F's record: {exc}", role="D", stage="controls")
                views["D"], views["Omega"], views["A0"] = dv, bc.oracle_view(mapping), bc.address_only_view(mapping.addresses)
                self.write(f"pair_{r:03d}/controls.json", {"schema": "b4_sim_controls", "schema_version": "1.0.0", "pair": r, "x_control_seed": x_seed, "d": dinfo,
                                                           "d_view": dv.as_dict(), "omega_view": views["Omega"].as_dict(), "a0_view": views["A0"].as_dict(), "written_utc": utc()}, sc.controls_findings)
            if role == "O":
                self.current["stage"] = "k7"
                plan["k7"] = "in_progress"
                prefixes = {}
                for B in GRID:
                    self.dl.check()
                    prefixes[str(B)] = sn.prefix_states(d, task, B)
                    if prefixes[str(B)]["findings"]:
                        self.write(f"pair_{r:03d}/k7.json", {"schema": "b4_sim_k7", "schema_version": "1.0.0", "pair": r, "arm": "O", "grid": list(GRID), "prefixes": prefixes, "complete": False, "written_utc": utc()}, sc.k7_findings)
                        raise Invalid("contract", f"K7 prefix at B = {B}: " + "; ".join(prefixes[str(B)]["findings"][:3]), role="O", stage="k7")
                self.write(f"pair_{r:03d}/k7.json", {"schema": "b4_sim_k7", "schema_version": "1.0.0", "pair": r, "arm": "O", "grid": list(GRID), "prefixes": prefixes, "complete": True, "written_utc": utc()}, sc.k7_findings)
                plan["k7"] = "complete"
                self.current["stage"] = "arms"
        # K9
        self.current.update(stage="k9", role="K9")
        plan["k9"] = "in_progress"
        self.dl.check()
        try:
            k9r = k9.coverage(task, self.port_factory(fabric, "K9", r), mapping, fabric, check=self.dl.check)
        except (fm.DomainRefusal, ex.SourceRefusal, fm.ModelRefusal, ValueError) as exc:
            raise Invalid("k9_invalid", f"K9 observation refused: {type(exc).__name__}: {exc}", role="K9", stage="k9")
        self.write(f"pair_{r:03d}/k9.json", {"schema": "b4_sim_k9", "schema_version": "1.0.0", "pair": r, **k9r}, sc.k9_findings)
        if not k9r["complete"]:
            plan["k9"] = "partial"
            raise StopWork(k9r["stopped"]["reason"])
        plan["k9"] = "complete"
        # K10
        self.current.update(stage="k10", role="K10")
        plan["k10"] = "in_progress"
        self.dl.check()
        try:
            k10r = k10.seed_k10(task, self.port_factory(fabric, "K10", r), tau=k10.TAU, check=self.dl.check)
        except k10.K10Invalid as exc:
            self.write(f"pair_{r:03d}/k10.json", {"schema": "b4_sim_k10", "schema_version": "1.0.0", "pair": r, **exc.partial}, sc.k10_findings)
            raise Invalid("k10_invalid", str(exc), role="K10", stage="k10")
        except (ex.SourceRefusal, fm.ModelRefusal) as exc:
            raise Invalid("k10_invalid", f"K10 observation refused: {type(exc).__name__}: {exc}", role="K10", stage="k10")
        self.write(f"pair_{r:03d}/k10.json", {"schema": "b4_sim_k10", "schema_version": "1.0.0", "pair": r, **k10r}, sc.k10_findings)
        if not k10r["complete"]:
            plan["k10"] = "partial"
            raise StopWork(k10r["stopped"]["reason"])
        plan["k10"] = "complete"
        # curves and the row the statistics use
        self.current.update(stage="curves", role=None)
        self.dl.check()
        curves = curves_of(results, r, l, o)
        self.write(f"pair_{r:03d}/curves.json", curves, sc.curves_findings)
        self.rows.append({"pair": r, "landscape_seed": l, "operator_seed": o, "base_fit": curves["base_fit"], "best_at_grid": curves["best_at_grid"],
                          "f_end_to_end_at_grid": [e["value"] for e in curves["f_end_to_end_at_grid"]],
                          "k7_not_unknown_at_grid": [prefixes[str(B)]["not_unknown"] for B in GRID],
                          "k9": k9r["summary"]["per_semantic"], "k9_all_seven": k9r["summary"]["all_seven_positive_controls"],
                          "k10_max_abs": k10r["max_abs_index"], "k10_outcome": k10r["outcome"]})
        self.hold_inputs(f"pair {r} end")
        plan["status"] = "complete"
        self.write(f"pair_{r:03d}/index.json", {"schema": "b4_sim_pair_index", "schema_version": "1.0.0", "pair": r, "landscape_seed": l, "operator_seed": o, "status": "complete",
                                                "arms": dict(plan["arms"]), "files": [dict(e, path=e["path"].split("/", 1)[1]) for e in self.files if e["path"].startswith(f"pair_{r:03d}/")],
                                                "written_utc": utc()}, sc.pair_index_findings)

    # -- the statistics stage
    def stats(self) -> None:
        self.current = {"pair": None, "stage": "statistics", "role": None}
        self.summary, self.stats_record = summarise_batch(self.rows, self.c["count"], check=self.dl.check)

    # -- the end
    def finish(self, status: str, stop: dict | None, exit_code: int) -> dict:
        self.current["stage"] = "finish"
        for p in self.planned:
            if p["status"] == "in_progress":
                p["status"] = "partial"
        stopped_doc = None
        if stop is not None:
            stopped_doc = {"schema": "b4_sim_stopped", "schema_version": "1.0.0", "status": status, "kind": stop["kind"], "detail": stop["detail"], "pair": self.current.get("pair"),
                           "stage": stop.get("stage") or self.current.get("stage") or "", "role": stop.get("role"), "stopped_utc": utc(), "deadline": self.dl.record(),
                           "planned": [dict(p) for p in self.planned], "head_at_stop": _head_or_none(self.c["root"]), "traceback": stop.get("traceback")}
            try:
                self.write("STOPPED.json", stopped_doc, sc.stopped_findings)
            except (Invalid, OSError) as exc:          # the stop record itself could not be written: say so in the report
                stopped_doc["detail"] += f" [STOPPED.json not written: {exc}]"
        missing: list[str] = []
        if status != "complete":
            missing.append("no pooled numeric summary: the batch did not complete")
            for p in self.planned:
                if p["status"] != "complete":
                    missing.append(f"pair {p['pair']}: {p['status']} (arms {p['arms']}, k7 {p['k7']}, k9 {p['k9']}, k10 {p['k10']})")
        self_validation = sc.validate_run_dir(self.out, task_of=lambda r: bl.make_task(self.pairs[r][0], self.c["mapping"].addresses)) if self.pairs else {}
        report = {"schema": "b4_sim_report", "schema_version": "1.0.0", "status": status, "label": self.c["label"], "count": self.c["count"], "head": self.c["head"],
                  "generated_utc": utc(), "deadline": self.dl.record(), "standing": STANDING, "thresholds": th.THRESHOLDS,
                  "identity": {"seeds_sha256": self.seeds_sha, "manifest_sha256": self.manifest_sha, "hypothesis_sha256": hy.HYPOTHESIS_SHA256, "certificate_sha256": bm.CERTIFICATE_SHA256,
                               "inputs": self.c["inputs"], "out": str(self.out.relative_to(self.c["root"]))},
                  "pairs": [dict(p) for p in self.planned], "files": [dict(e) for e in self.files], "stopped": stopped_doc,
                  "summary": self.summary if status == "complete" else None, "missing": missing, "self_validation": self_validation}
        try:
            self.write("sim_report.json", report, sc.report_findings)
        except Invalid as exc:
            report["status_report_error"] = str(exc)
            (self.out / "sim_report.ERROR.txt").write_text(str(exc) + "\n")
        return {"status": status, "exit_code": exit_code, "out": str(self.out), "stopped": stopped_doc, "report": report}


def _head_or_none(root: Path):
    try:
        return git(root, "rev-parse", "HEAD").strip()
    except Refusal:
        return None


# ------------------------------------------------------------------ the typed completion checks (ruling section 4.3)
def completion_findings(d: dict, role: str, task: ex.PublicTask, port_calls: int, view: bc.MapView | None) -> list[str]:
    f: list[str] = []
    if d.get("completed") is not True or d.get("search_completed") is not True:
        f.append("completed / search_completed are not the bool True")
    for k in ("terminal", "other_refusal", "control_failure"):
        if d.get(k) is not None:
            f.append(f"{k} is not None")
    if d.get("evals") != B_MAX or len(d.get("best_trace") or []) != B_MAX:
        f.append(f"evals / len(best_trace) are not exactly {B_MAX}")
    if d.get("cost") != EXPECTED_COST[role]:
        f.append(f"cost {d.get('cost')} is not the arm's {EXPECTED_COST[role]}")
    total = sum(EXPECTED_COST[role].values())
    if not (d.get("observations") == total == port_calls == len(d.get("ledger") or [])):
        f.append(f"observations {d.get('observations')} / port calls {port_calls} / ledger {len(d.get('ledger') or [])} are not all {total}")
    L = d.get("ledger") or []
    if sum(1 for e in L if e.get("phase") == "holdout") != 1 or not L or L[-1].get("phase") != "holdout":
        f.append("the holdout is not exactly the last record, once")
    if d.get("arm") != ENGINE_ARM[role] or d.get("budget") != B_MAX or d.get("landscape_seed") != task.seed or d.get("task_digest") != task.digest():
        f.append("arm / budget / seed / task do not match the plan")
    prov = d.get("provenance") or {}
    if d.get("fixture") is not False or d.get("fabric_fixture") is not False or prov.get("hypothesis", {}).get("sha256") != hy.HYPOTHESIS_SHA256 \
            or prov.get("hypothesis", {}).get("fixture") is not False or prov.get("fabric", {}).get("kind") != "truth":
        f.append("the observation source is not the formal hypothesis on the truth fabric")
    if d.get("champion_holdout") is None:
        f.append("no holdout score")
    if role in ("D", "Omega", "A0"):
        if view is None or d.get("given_view") is None:
            f.append("a control role without its given view")
        elif d.get("map_privileged") is not view.privileged:
            f.append("map_privileged is not the given view's")
    elif role == "X" and d.get("x_control_seed") is None:
        f.append("X without its control seed")
    elif role == "F" and (d.get("given_view") is not None or d.get("map_origin") != "learned"):
        f.append("F did not learn its map")
    return f


def curves_of(results: dict, r: int, l: int, o: int) -> dict:
    best = {role: [results[role]["best_trace"][B - 1] for B in GRID] for role in ROLES}
    base = results["R"]["base_fit"]
    f_trace = results["F"]["best_trace"]
    fe = []
    for T in GRID:
        if T <= PROBES:
            fe.append({"T": T, "value": results["F"]["base_fit"], "mapping_in_progress": True})
        else:
            fe.append({"T": T, "value": f_trace[T - PROBES - 1], "mapping_in_progress": False})
    return {"schema": "b4_sim_curves", "schema_version": "1.0.0", "pair": r, "landscape_seed": l, "operator_seed": o, "grid": list(GRID), "base_fit": base,
            "best_at_grid": best, "f_end_to_end_at_grid": fe, "holdout": {role: results[role]["champion_holdout"] for role in ROLES}, "written_utc": utc()}


# ------------------------------------------------------------------ the descriptive statistics (values beside thresholds; no verdict)
def _delta_stats(deltas: list) -> dict:
    p, pos, neg, ties = gs.sign_test_p(deltas)
    return {"n": len(deltas), "mean": gs.mean(deltas) if deltas else None, "median": gs.median(deltas) if deltas else None,
            "positives": pos, "negatives": neg, "ties": ties, "sign_test_p": p,
            "population_variance": statistics.pvariance(deltas) if deltas else None, "cohen_d": gs.encode_stat(gs.cohen_d(deltas)) if deltas else gs.encode_stat(None)}


def _ratio(num: float | None, den: float | None) -> dict:
    if num is None or den is None:
        return {"numerator": num, "denominator": den, "ratio": None, "readable": False, "note": "no data"}
    if den <= 0:
        return {"numerator": num, "denominator": den, "ratio": None, "readable": False, "note": "a non-positive denominator cannot be read as a ratio condition"}
    return {"numerator": num, "denominator": den, "ratio": num / den, "readable": True, "note": None}


def summarise_batch(rows: list[dict], S: int, check=None) -> tuple[dict, dict]:
    """Descriptive statistics over the completed rows (= all S rows when the batch is complete), per grid budget and at the
    candidate B*; every value beside the fixed threshold it is compared with elsewhere. Pure; `check` is called before each
    budget's N scan, each bootstrap and each K9 / K10 unit."""
    T = th.THRESHOLDS
    if len(rows) != S:
        raise ValueError("the summary is computed on all S rows only")
    record: dict = {"n_scans": {}}
    per_budget: dict = {}
    for i, B in enumerate(GRID):
        if check:
            check()
        v = {role: [row["best_at_grid"][role][i] for row in rows] for role in ROLES}
        base = [row["base_fit"] for row in rows]
        fe = [row["f_end_to_end_at_grid"][i] for row in rows]
        d1 = [o - r for o, r in zip(v["O"], v["R"])]
        d2 = [o - f for o, f in zip(v["O"], fe)]
        diffs = {"delta1_O_minus_R": d1, "delta2_O_minus_endtoend_F": d2, "F_minus_R": [a - b for a, b in zip(v["F"], v["R"])],
                 "X_minus_R": [a - b for a, b in zip(v["X"], v["R"])], "D_minus_R": [a - b for a, b in zip(v["D"], v["R"])],
                 "Omega_minus_R": [a - b for a, b in zip(v["Omega"], v["R"])], "A0_minus_R": [a - b for a, b in zip(v["A0"], v["R"])]}
        n, last, scan = gs.required_pairs_scan(d1, T["K5"]["alpha"], T["K5"]["power_min"], T["K5"]["bootstrap_experiments"], 1, T["K5"]["n_min"], S, check=check)
        record["n_scans"][str(B)] = scan
        if not scan["complete"]:
            raise StopWork(scan["reason"])
        p95 = gs.percentile(v["Omega"], T["K1"]["percentile"])
        k1 = {"omega_best_p95": p95, "median_best_R": gs.median(v["R"]), "median_base": gs.median(base),
              "eligibility": bool(p95 < T["K1"]["omega_best_p95_lt"] and gs.median(v["R"]) > gs.median(base))}
        per_budget[str(B)] = {"budget": B, "arm_values": {role: {"mean": gs.mean(x), "median": gs.median(x), "min": min(x), "max": max(x)} for role, x in v.items()},
                              "base": {"mean": gs.mean(base), "median": gs.median(base)}, "f_end_to_end": {"mean": gs.mean(fe), "median": gs.median(fe), "mapping_in_progress": B <= PROBES},
                              "deltas": {k: _delta_stats(x) for k, x in diffs.items()}, "k1": k1,
                              "required_pairs": {"N": n, "power_at_N_or_last": last, "scan": scan["scanned"], "n_min": T["K5"]["n_min"], "n_max": S},
                              "cost_N_x_3_x_B": None if n is None else n * 3 * B,
                              "k7_O_prefix_not_unknown": {"values": [row["k7_not_unknown_at_grid"][i] for row in rows], "median": gs.median([row["k7_not_unknown_at_grid"][i] for row in rows])}}
    eligible = [B for B in GRID if per_budget[str(B)]["k1"]["eligibility"] and per_budget[str(B)]["required_pairs"]["N"] is not None]
    if eligible:
        b_star = min(eligible, key=lambda B: (per_budget[str(B)]["cost_N_x_3_x_B"], B))
        reason = None
    else:
        b_star, reason = None, "no grid budget has both K1 eligibility and an N: the budget rule's candidate does not exist on this S (not invented)"
    at = None
    if b_star is not None:
        if check:
            check()
        pb = per_budget[str(b_star)]
        i = GRID.index(b_star)
        N = pb["required_pairs"]["N"]
        xr = [row["best_at_grid"]["X"][i] - row["best_at_grid"]["R"][i] for row in rows]
        nonreject = 1.0 - gs.bootstrap_reject_rate(xr, N, T["K2"]["alpha"], T["K2"]["bootstrap_experiments"], T["K2"]["bootstrap_seed"])
        both_signs = [B for B in GRID if per_budget[str(B)]["deltas"]["delta1_O_minus_R"]["positives"] > 0 and per_budget[str(B)]["deltas"]["delta1_O_minus_R"]["negatives"] > 0]
        dl = pb["deltas"]
        at = {"B_star": b_star, "N": N, "cost_N_x_3_x_B_star": pb["cost_N_x_3_x_B"],
              "k2": {"population_variance_delta1": dl["delta1_O_minus_R"]["population_variance"], "budgets_with_both_signs": both_signs,
                     "x_minus_r_bootstrap_nonrejection": nonreject, "bootstrap": {"N": N, "experiments": T["K2"]["bootstrap_experiments"], "alpha": T["K2"]["alpha"], "seed": T["K2"]["bootstrap_seed"]}},
              "k3": {"D_over_F": _ratio(dl["D_minus_R"]["mean"], dl["F_minus_R"]["mean"]), "X_over_O": _ratio(dl["X_minus_R"]["mean"], dl["delta1_O_minus_R"]["mean"]),
                     "D_sign_test_p": dl["D_minus_R"]["sign_test_p"], "X_sign_test_p": dl["X_minus_R"]["sign_test_p"]},
              "k4": {"median_best_Omega": pb["arm_values"]["Omega"]["median"], "mean_Omega_minus_R": dl["Omega_minus_R"]["mean"], "mean_F_minus_R": dl["F_minus_R"]["mean"],
                     "F_over_Omega": _ratio(dl["F_minus_R"]["mean"], dl["Omega_minus_R"]["mean"])},
              "k5": {"cohen_d_delta1": dl["delta1_O_minus_R"]["cohen_d"], "N": N, "cost": pb["cost_N_x_3_x_B"]},
              "k7": {"median_O_prefix_not_unknown": pb["k7_O_prefix_not_unknown"]["median"], "values": pb["k7_O_prefix_not_unknown"]["values"]}}
    # K9 over all S rows
    if check:
        check()
    k9s: dict = {}
    for s in k9.SEMANTICS:
        fr = [row["k9"][s]["fraction"] for row in rows]
        na = sum(1 for x in fr if x is None)
        k9s[s] = {"seeds_with_positive_control": sum(1 for row in rows if row["k9"][s]["positive_control"]), "not_assessable_seeds": na,
                  "median_coverage_over_all_S": (gs.median(fr) if na == 0 else None), "median_rule": T["K9"]["median_population"], "conditional_on_A8": s == "ff_init"}
    k9_all = sum(1 for row in rows if row["k9_all_seven"])
    # K10 over all S rows
    if check:
        check()
    k10s = st.summarise([row["k10_max_abs"] for row in rows], k10.TAU, S)
    summary = {"S": S, "grid": list(GRID), "per_budget": per_budget, "eligible_budgets": eligible,
               "candidate_B_star": {"value": b_star, "reason_if_none": reason, "note": T["B_star"]["no_eligible_budget"]}, "at_candidate_B_star": at,
               "k9": {"per_semantic": k9s, "seeds_with_all_seven_positive_controls": k9_all, "fraction_of_S": k9_all / S},
               "k10": k10s, "thresholds_for_reference": T, "standing": STANDING}
    return summary, record


# ------------------------------------------------------------------ the batch runner and the CLI
def run_batch(root: Path, label: str, count: int, deadline_s: int, out: Path | None = None, clock=time.monotonic, port_factory=None) -> dict:
    t_start = clock()
    try:
        dl = Deadline(deadline_s, clock=clock) if isinstance(deadline_s, int) and not isinstance(deadline_s, bool) and deadline_s > 0 else None
        ctx = preflight(root, label, count, deadline_s, out)
    except Refusal as exc:
        return {"status": "refused", "exit_code": 2, "out": None, "reason": str(exc), "stopped": None, "report": None}
    ns = ctx["root"] / SIM_REL
    ns.mkdir(parents=True, exist_ok=True)
    try:
        ctx["out"].mkdir(exist_ok=False)
    except FileExistsError:
        return {"status": "refused", "exit_code": 2, "out": None, "reason": f"{ctx['out']} appeared before it could be created exclusively", "stopped": None, "report": None}
    batch = Batch(ctx, dl, port_factory)
    try:
        batch.init()
    except Exception as exc:  # noqa: BLE001 — the directory exists: leave an identifiable record
        doc = {"schema": "b4_sim_init_failed", "schema_version": "1.0.0", "label": label, "seeds_derived": batch.seeds_sha is not None,
               "reason": f"{type(exc).__name__}: {exc}", "generated_utc": utc()}
        try:
            write_exclusive(ctx["out"] / bs.INIT_FAILED_FILE, doc, sc.init_failed_findings)
        except Exception:  # noqa: BLE001
            pass
        return {"status": "init_failed", "exit_code": 2, "out": str(ctx["out"]), "reason": doc["reason"], "stopped": None, "report": None}
    try:
        for r in range(count):
            batch.run_pair(r)
        batch.stats()
        batch.hold_inputs("final")
        batch.hold_tree()
    except StopWork as exc:
        return batch.finish("incomplete", {"kind": "deadline", "detail": str(exc), "role": batch.current.get("role"), "stage": batch.current.get("stage")}, 3)
    except KeyboardInterrupt:
        return batch.finish("incomplete", {"kind": "interrupted", "detail": "KeyboardInterrupt: an external interrupt, not a model event", "role": batch.current.get("role"), "stage": batch.current.get("stage")}, 3)
    except Invalid as exc:
        return batch.finish("invalid", {"kind": exc.kind, "detail": exc.detail, "role": exc.role or batch.current.get("role"), "stage": exc.stage or batch.current.get("stage")}, 1)
    except Exception as exc:  # noqa: BLE001 — never lose what is on disk; name it
        return batch.finish("invalid", {"kind": "unexpected_exception", "detail": f"{type(exc).__name__}: {exc}", "role": batch.current.get("role"),
                                        "stage": batch.current.get("stage"), "traceback": traceback.format_exc()}, 1)
    _ = t_start
    return batch.finish("complete", None, 0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="B4 host-only exploration harness (values beside thresholds; no gate verdict). Running it needs the owner's authorisation.")
    ap.add_argument("--label", required=True, help="b4-sim-<n>")
    ap.add_argument("--seeds", required=True, type=int, help="S, the number of pairs planned")
    ap.add_argument("--deadline-s", required=True, type=int, help="the soft monotonic deadline in seconds, from the pre-flight on (no default)")
    ap.add_argument("--out", default=None, help=f"the output directory, directly under {SIM_REL}/ and named <label>_…; default <label>_<UTC>")
    a = ap.parse_args(argv)
    res = run_batch(REPO_ROOT, a.label, a.seeds, a.deadline_s, Path(a.out) if a.out else None)
    print(json.dumps({k: v for k, v in res.items() if k in ("status", "exit_code", "out", "reason")}, indent=1))
    return res["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
