#!/usr/bin/env python3
"""B4 — the HOST-ONLY EXPLORATION HARNESS (docs/b4_architecture.md sections 7.1, 8, 9, 9.1–9.5; the owner's ruling of 2026-10-18 on
unit 2b-4a; repaired after the owner's review of cdf2c53, F1–F9; protocol v0.2.0 after the owner's rulings of 2026-10-20). It sets
up each pair's task-v0.2 target (the planted configuration observed through the port, persisted call by call), runs the seven arms
per pair on the FORMAL model, audits every run, computes K7 / K9 / K10's data and the descriptive statistics, and archives
everything typed — values beside the fixed thresholds, NEVER a gate verdict.

    b4_sim.py --label b4-sim-4 --seeds 32 --deadline-s 3600 [--out evidence/b4/sim/<label>_<UTC>]   # b4-sim-1 / b4-sim-2 retired; b4-sim-3 / b4-gate-1 consumed

TASK-V0.2 (section 7.1; the owner's choices 1-3 and the target-setup contract). Per pair, BEFORE any arm: task_setup.json (the
private record — the seeds, the planted flip-flop genome g* by the fixed rule, the stimulus digests — persisted before the first
target call) → the search-stimulus observation of g* through a dedicated port, its raw trace and provenance saved at once
(target_search.json) → the holdout-stimulus observation, saved at once (target_holdout.json) → task.json (the PublicTask the arms
receive: no seed, no g*, no private record; its digest; the setup files' digests). Two port calls per pair, shared by the seven
arms; the arms' counts unchanged. A DOMAIN, a SourceRefusal, a drift between the two observations or a None in a formal target
is `invalid` (kind `target_invalid`); the deadline or an interrupt is `incomplete` with whatever was written kept; a pair whose
setup began is `in_progress` / `partial`, never `not_started`; nothing is redrawn. The setup observations enter no ledger and no
cartographer. The manifest carries the PROTOCOL IDENTITY (section 9.5, b4_protocol) and its digest.

NOTHING IS AUTHORISED BY THIS FILE: running it is a separate authorisation (ruling section 5). The CLI has no fixture,
no allow-dirty, no test mode; a test drives `run_batch` on a hermetic repository copy with its own `port_factory` and a
`FixtureSchedule`.

SEEDS (F1). A PRODUCTION batch (label `b4-sim-<n>`) derives its master from the anchor and draws its pairs against the pooled
exclusion set — that derivation is the formal act of section 9.2 and happens ONLY here, only for a production label. A
MECHANICS batch (label `b4-mech-<n>`, Python API only) takes a `FixtureSchedule`: an explicit list of pairs made solely of
values already exposed under section 9.2 (`b4_seeds.FIXTURE_VALUES`); no anchor, no master, no draw, `fixture = true` in
every record; it can never reach a production set. A production label with a schedule, or a fixture label without one, is
refused before anything is written.

PRE-FLIGHT (no write on any failure; exit 2): the label and the schedule as above; S and the deadline are positive ints; the
tree is clean (`git status --porcelain` empty, no override); the formal hypothesis loads (not a fixture), the mapping, the
truth fabric; the root's copies of the formal inputs hash to the pinned digests; the hypothesis's repository AND external
(vendor) sources hash to their recorded digests; every exclusion source reads; the output directory is `evidence/b4/sim/
<label>_…` LITERALLY under the resolved root — no ancestor of the namespace is a symlink, the leaf does not exist — then
it is created EXCLUSIVELY and checked again (F7); the deadline counts from the pre-flight's start.

FREEZING ORDER: `seeds.json`, then `manifest.json` (HEAD, every input's digest — the root inputs, the hypothesis's
repository sources, the 38 exclusion sources, the external sources by absolute path — the tool files' digests, the code
root's HEAD and cleanliness, the archived-set registry snapshot, the constants, the thresholds table), and only then the
first observation (F9). An initialisation failure after the directory exists leaves `INIT_FAILED.json`.

PER PAIR, IN THE FIXED ORDER R → F → O → X → D → Ω → A0 (one worker, never more): a new port per arm; the engine's
`RunResult` is validated and written AT ONCE, exclusively, before any audit — a returned object that does not validate is
QUARANTINED raw with the findings (`arm_<role>.result.QUARANTINE.json`, state `result_malformed`) and the batch is invalid
(F6); then the typed completion checks (section 4.3), the replay, the ledger recompute (K7 a), the given-view checks; a
finding is `invalid`. After F the D view from F's rebuilt map; after O the K7 prefixes at every grid budget; after the arms
K9 and K10 on their own ports — a refusal, an error or an interrupt inside them leaves the PARTIAL record on disk (F5, F6;
K10 observes no corner after the first refused one); the curves; the pair index last. After every pair and at the end the
HEAD, every input digest, every external digest, every tool digest and the registry snapshot are held to the manifest (a
drift is `invalid`); at the end the working tree must carry nothing but this batch's output.

STOP RULES (section 9.1; fail-closed): a DOMAIN, another refusal, a control failure, a replay or recompute finding, a
K10 `comparable = False`, a schema finding, an input drift, an unexpected exception or a finding of the batch's own
archive-wide verification is `invalid`; the soft deadline (checked before and after every arm, replay, snapshot, K9 pair,
K10 unit, statistics unit AND before every finalisation unit — a batch whose deadline expired is never `complete`, F8) or
an external interrupt is `incomplete`. In every case what has returned is on disk, `STOPPED.json` names the kind, the pair,
the stage and the whole planned list, and `sim_report.json` carries the status, the identity, the archive index and the
self-validation — a pooled numeric summary ONLY when the batch is `complete` AND its archive verifies clean. A report that
cannot be validated or written is itself a failure: the batch is then `invalid`, exit 1, whatever happened before (F4).
Nothing is skipped, swapped or redrawn. Exit codes: 0 complete, 1 invalid, 2 refused / init failed, 3 incomplete.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
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
import b4_protocol as bp  # noqa: E402
import b4_replay as br  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_sim_verify as sv  # noqa: E402
import b4_snapshot as sn  # noqa: E402
import b4_stats as st  # noqa: E402
import b4_target as bt  # noqa: E402
import b4_thresholds as th  # noqa: E402
from b4_deadline import Deadline, StopWork  # noqa: E402

SIM_REL = bs.SIM_REL
LABEL_RE = re.compile(r"^b4-sim-[1-9][0-9]*$")                      # production exploration labels (the CLI's only labels)
GATE_LABEL_RE = re.compile(r"^b4-gate-[1-9][0-9]*$")                 # the formal gate's labels: accepted in mode "gate" only (b4_gate.py, unit 2b-4); the exploration CLI refuses them
MODES = ("exploration", "gate")
FIXTURE_LABEL_RE = bs.FIXTURE_LABEL_RE                              # mechanics fixture labels (Python API only)
ROLES = sc.ROLES
ENGINE_ARM = {"R": "R", "F": "F", "O": "O", "X": "X", "D": "F", "Omega": "F", "A0": "F"}
GRID = th.GRID
B_MAX = th.B_MAX
PROBES = th.PROBES
EXPECTED_COST = {role: {"base": 1, "probes": PROBES if role == "F" else 0, "search": B_MAX, "holdout": 1} for role in ROLES}
SETUP_ROLE = "TARGET"                                                # the port role of the per-pair target setup (two calls, shared by the seven arms)
STANDING = ("exploration data under the label given, S as planned; not a gate verdict; the thresholds of docs/b4_architecture.md "
            "section 9 (protocol v0.2.0: task-v0.2, K9 (b') judged) are listed for reference only; candidate B* / N are estimates on this S, never the formal S = 200's")
# (the text every archived v0.2.0 exploration carries in its summary; the archive-wide verifier recomputes the summary with it. The
# v0.1.x explorations carried their own text and are verified by their own tool at their recorded HEAD — docs/b4_archive_reverification.md)
STANDING_GATE = ("the batch of the formal gate under the label given, S as planned; values beside the thresholds of docs/b4_architecture.md section 9 "
                 "and not a gate verdict here: the verdict is b4_gate.py's, written in a gate directory under evidence/b4/gate/ and bound to this "
                 "archive by digest (unit 2b-4); candidate B* / N are the budget rule's on this batch")


def standing_for(label: str) -> str:
    """The standing text a batch's report and summary carry: the gate's for a b4-gate-<n> label, the exploration's otherwise
    (a mechanics fixture carries the exploration's). A function of the label alone, so the verifier needs no other input."""
    return STANDING_GATE if isinstance(label, str) and GATE_LABEL_RE.match(label) else STANDING
ROOT_INPUTS = ("docs/b4_architecture.md", "b4/IMPORT.json", hy.HYPOTHESIS_REL, bm.CERTIFICATE_REL, bs.EXPOSURE_RECEIPT_REL)   # the receipt: pinned, pooled, held at every checkpoint
FIXTURE_ANCHOR_RULE = "mechanics fixture: an explicit schedule of already-exposed values (b4_seeds.FIXTURE_VALUES); no anchor, no master, no draw"


class Refusal(Exception):
    """A pre-flight refusal: nothing was written."""


class Invalid(Exception):
    def __init__(self, kind: str, detail: str, role: str | None = None, stage: str = ""):
        super().__init__(detail)
        self.kind, self.detail, self.role, self.stage = kind, detail, role, stage


@dataclass(frozen=True)
class FixtureSchedule:
    """A MECHANICS fixture: the pairs of a `b4-mech-<n>` batch, given explicitly, every value already exposed under
    section 9.2. Nothing is derived from it and nothing production-like can be reached through it."""
    label: str
    pairs: tuple

    def findings(self) -> list[str]:
        f: list[str] = []
        if not (isinstance(self.label, str) and FIXTURE_LABEL_RE.match(self.label)):
            f.append(f"the fixture label {self.label!r} is not b4-mech-<n>")
        if not (isinstance(self.pairs, tuple) and self.pairs):
            return f + ["the schedule is a non-empty tuple of (landscape_seed, operator_seed) pairs"]
        for i, p in enumerate(self.pairs):
            if not (isinstance(p, tuple) and len(p) == 2 and all(bs.is_seed_int(v) for v in p)):
                f.append(f"pair {i}: not two seed ints"); continue
            if p[0] == p[1]:
                f.append(f"pair {i}: the two seeds are equal")
            for v in p:
                if v not in bs.FIXTURE_VALUES:
                    f.append(f"pair {i}: the value {v} is not an already-exposed value (b4_seeds.FIXTURE_VALUES)")
        if len(set(self.pairs)) != len(self.pairs):
            f.append("a pair is scheduled twice")
        return f


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


def code_root_state() -> dict:
    """The model code's tree (REPO_ROOT): its HEAD and cleanliness, recorded so that a hermetic input root is never mistaken
    for the code root (F9). None when the code root is not a git tree."""
    try:
        head = git(REPO_ROOT, "rev-parse", "HEAD").strip()
        clean = not porcelain(REPO_ROOT)
    except Refusal:
        head, clean = None, None
    return {"head": head, "clean": clean}


def input_snapshot(root: Path, hypothesis: hy.Hypothesis, exclusion) -> tuple[dict, dict, dict, list]:
    """The digests of every input the batch depends on: root-relative (the root inputs, the hypothesis's repository sources,
    the 38 exclusion sources), external by absolute path (the hypothesis's vendor sources), the tool files (from the code
    tree), and the registry snapshot [(dir, status, seeds_sha256)] of the archived sets (F9)."""
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
    if inputs[bs.EXPOSURE_RECEIPT_REL] != bs.EXPOSURE_RECEIPT_SHA256:
        raise Refusal("the root's exposure receipt does not hash to the pinned digest")
    external: dict[str, str] = {}
    for s in hypothesis.doc["sources"]:
        if "path" not in s or "sha256" not in s:
            continue
        if "root" in s:
            p = Path(s["root"]) / s["path"]
            if not p.is_file():
                raise Refusal(f"the external source {p} is missing")
            got = sha_file(p)
            if got != s["sha256"]:
                raise Refusal(f"the external source {p} hashes to {got[:16]}…, not its recorded digest")
            external[str(p)] = got
        else:
            rel = s["path"]
            p = root / rel
            if not p.is_file():
                raise Refusal(f"the hypothesis source {rel} is missing under the root")
            got = sha_file(p)
            if got != s["sha256"]:
                raise Refusal(f"the hypothesis source {rel} hashes to {got[:16]}…, not its recorded digest")
            inputs[rel] = got
    for src in exclusion.sources:                                   # read against their digests already; bound here for the checkpoints
        inputs[src.path] = src.sha256
    tools = {rel: sha_file(REPO_ROOT / rel) for rel in tool_files(REPO_ROOT)}
    registry = [[r.dir, r.status, r.seeds_sha256] for r in exclusion.registry]
    return inputs, external, tools, registry


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


def raw_projection(obj) -> tuple:
    """(a JSON-able projection of a returned object or None, its repr) for a quarantine record."""
    try:
        d = obj.as_dict() if hasattr(obj, "as_dict") else obj
        return json.loads(json.dumps(d, default=repr, allow_nan=False)), repr(obj)[:20000]
    except Exception:  # noqa: BLE001
        return None, repr(obj)[:20000]


# ------------------------------------------------------------------ pre-flight
def namespace_chain(root: Path) -> list[Path]:
    """root/evidence, root/evidence/b4, root/evidence/b4/sim — every existing one must be a real directory, none a symlink."""
    parts = Path(SIM_REL).parts
    return [root.joinpath(*parts[:i + 1]) for i in range(len(parts))]


def preflight(root: Path, label: str, count: int, deadline_s: int, out: Path | None, schedule: FixtureSchedule | None = None, mode: str = "exploration") -> dict:
    if mode not in MODES:
        raise Refusal(f"the mode {mode!r} is not one of {MODES}")
    if schedule is None:
        if mode == "gate":
            if not isinstance(label, str) or not GATE_LABEL_RE.match(label):
                raise Refusal(f"the label {label!r} is not a gate label b4-gate-<n> (mode gate; a mechanics batch needs a FixtureSchedule)")
        elif not isinstance(label, str) or not LABEL_RE.match(label):
            raise Refusal(f"the label {label!r} is not an exploration label b4-sim-<n> (the gate's label is unit 2b-4's, accepted by b4_gate.py in mode gate only; a mechanics batch needs a FixtureSchedule)")
        try:
            bs.check_label_not_retired(label)                   # a retired label is refused here, before any tree is read and before any master is formed
        except bs.RetiredLabelRefusal as exc:
            raise Refusal(str(exc)) from None
    else:
        if not isinstance(schedule, FixtureSchedule):
            raise Refusal("the schedule is not a FixtureSchedule")
        if not isinstance(label, str) or not FIXTURE_LABEL_RE.match(label):
            raise Refusal(f"a batch with a FixtureSchedule carries a mechanics label b4-mech-<n>, not {label!r}: a production label never runs on a fixture")
        f = schedule.findings()
        if f or schedule.label != label:
            raise Refusal("the fixture schedule is refused: " + "; ".join(f or ["its label is not the batch's"]))
        if count != len(schedule.pairs):
            raise Refusal(f"--seeds {count} is not the schedule's {len(schedule.pairs)} pairs")
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise Refusal("--seeds must be a positive int")
    if not isinstance(deadline_s, int) or isinstance(deadline_s, bool) or deadline_s <= 0:
        raise Refusal("--deadline-s must be a positive int (no default)")
    try:
        protocol = bp.identity(REPO_ROOT)                        # the method's identity from the code tree's trusted inventory: refused when the tree is not its inventory
    except bp.IdentityRefusal as exc:
        raise Refusal(f"no protocol identity can be built from the code tree: {exc}") from None
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
    try:
        exclusion = bs.load_exclusion_set(root)
    except bs.ExclusionSourceRefusal as exc:
        raise Refusal(f"the exclusion set cannot be loaded: {exc}") from None
    inputs, external, tools, registry = input_snapshot(root, hypothesis, exclusion)
    # the output directory: literally <root>/evidence/b4/sim/<label>_…, through no symlink anywhere in the chain (F7)
    ns = root / SIM_REL
    for anc in namespace_chain(root):
        if anc.is_symlink():
            raise Refusal(f"{anc.relative_to(root)} is a symlink: the exploration namespace must be a real directory chain under the root")
        if anc.exists() and not anc.is_dir():
            raise Refusal(f"{anc.relative_to(root)} exists and is not a directory")
    stamp = utc().replace("-", "").replace(":", "")
    out_p = Path(out) if out is not None else ns / f"{label}_{stamp}"
    out_p = out_p if out_p.is_absolute() else root / out_p
    if Path(os.path.normpath(out_p)) != out_p or out_p.parent != ns:
        raise Refusal(f"the output directory must lie directly under {SIM_REL}/ of the root, written plainly; got {out_p}")
    if not out_p.name.startswith(label + "_") or "/" in out_p.name:
        raise Refusal(f"the output directory's name must begin with {label}_")
    if out_p.is_symlink() or out_p.exists():
        raise Refusal(f"the output directory {out_p} exists (or is a symlink); nothing is overwritten")
    return {"root": root, "head": head, "hypothesis": hypothesis, "mapping": mapping, "fabric": fabric, "inputs": inputs, "external": external, "tools": tools,
            "registry": registry, "exclusion": exclusion, "out": out_p, "label": label, "count": count, "deadline_s": deadline_s, "schedule": schedule,
            "code_root": code_root_state(), "protocol": {"identity": protocol, "protocol_sha256": bp.protocol_sha256(protocol)}}


def create_out_dir(ctx: dict) -> None:
    """Create the namespace chain and the output directory exclusively, then check the chain again: no symlink anywhere."""
    root = ctx["root"]
    for anc in namespace_chain(root):
        if anc.is_symlink():
            raise Refusal(f"{anc.relative_to(root)} became a symlink")
        anc.mkdir(exist_ok=True)
    ctx["out"].mkdir(exist_ok=False)
    if ctx["out"].is_symlink() or ctx["out"].resolve() != ctx["out"] or any(a.is_symlink() for a in namespace_chain(root)):
        raise Refusal(f"the output directory {ctx['out']} does not resolve to itself under the root")


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
        self.own_rel = str(self.out.relative_to(ctx["root"]))

    # -- writing
    def write(self, rel: str, doc, validator) -> dict:
        e = write_exclusive(self.out / rel, doc, validator)
        e["path"] = rel
        self.files.append(e)
        return e

    def quarantine(self, rel: str, pair: int, role: str | None, stage: str, findings: list[str], obj) -> dict:
        """Keep a returned object that did not validate, raw, with the findings that refused it (F6)."""
        raw, rep = raw_projection(obj)
        doc = {"schema": "b4_sim_quarantine", "schema_version": "1.0.0", "pair": pair, "role": role, "stage": stage, "findings": list(findings), "raw": raw, "raw_repr": rep, "written_utc": utc()}
        try:
            return self.write(rel, doc, sc.quarantine_findings)
        except Invalid:
            doc["raw"] = None                                       # a raw projection that is not finite JSON: keep the repr only
            return self.write(rel, doc, sc.quarantine_findings)

    def write_or_quarantine(self, rel: str, doc, validator, pair: int, role: str | None, stage: str) -> bool:
        """Write `rel` if it validates, else its quarantine; True when the document was written as itself."""
        f = validator(doc)
        if not f:
            self.write(rel, doc, validator)
            return True
        self.quarantine(rel.replace(".json", ".QUARANTINE.json"), pair, role, stage, f, doc)
        return False

    # -- init: seeds, then manifest, then (and only then) observations
    def init(self) -> None:
        c = self.c
        exd = c["exclusion"].as_dict()
        if c["schedule"] is None:
            bs.check_label_not_retired(c["label"])                                  # defence in depth: the pre-flight refused already
            master = bs.master_seed(c["label"], hy.HYPOTHESIS_SHA256)              # the formal derivation: production labels only
            self.pairs = bs.pair_seeds(master, c["count"], c["exclusion"].values)
            anchor = {"rule": th.THRESHOLDS["anchor"]["rule"], "hypothesis_sha256": hy.HYPOTHESIS_SHA256, "label": c["label"]}
            fixture = False
        else:
            master = None
            self.pairs = [tuple(p) for p in c["schedule"].pairs]
            anchor = {"rule": FIXTURE_ANCHOR_RULE, "hypothesis_sha256": None, "label": c["label"]}
            fixture = True
        seeds = {"schema": bs.SEEDS_SCHEMA[0], "schema_version": bs.SEEDS_SCHEMA[1], "label": c["label"], "fixture": fixture, "anchor": anchor,
                 "master_seed": master, "count": c["count"], "pairs": [list(p) for p in self.pairs],
                 "exclusion": {"sources": exd["sources"], "b4_exposed_values": exd["b4_exposed_values"], "sim_registry": exd["sim_registry"],
                               "exposure_receipt": exd["exposure_receipt"], "pooled_total": exd["pooled_total"]},
                 "generated_utc": utc()}
        self.seeds_sha = self.write("seeds.json", seeds, sc.seeds_findings)["sha256"]
        self.planned = [{"pair": r, "landscape_seed": l, "operator_seed": o, "status": "not_started", "task": "not_started", "arms": {role: "not_started" for role in ROLES},
                         "k7": "not_started", "k9": "not_started", "k10": "not_started"} for r, (l, o) in enumerate(self.pairs)]
        h, m = c["hypothesis"], c["mapping"]
        cr = c["code_root"]
        manifest = {"schema": "b4_sim_manifest", "schema_version": "1.2.0", "label": c["label"], "fixture": fixture, "count": c["count"], "generated_utc": utc(), "head": c["head"],
                    "protocol": c["protocol"],
                    "repo_root_kind": "the repository root the batch read its inputs from (git HEAD above); the model code is the b4/host tree of the tool files (code_root)",
                    "code_root": {"head": cr["head"], "clean": cr["clean"], "same_as_input_root": REPO_ROOT.resolve() == c["root"]},
                    "deadline_s": c["deadline_s"], "arm_order": list(ROLES), "engine_arm": dict(ENGINE_ARM), "budget": B_MAX, "grid": list(GRID),
                    "constants": manifest_constants(),
                    "thresholds": th.THRESHOLDS, "inputs": c["inputs"], "external_inputs": c["external"], "tool_files": c["tools"],
                    "hypothesis": {"path": h.path, "sha256": h.sha256, "version": h.version, "fixture": h.fixture, "sources": h.doc["sources"]},
                    "mapping": {"site": m.site, "certificate": m.certificate_rel, "certificate_sha256": m.certificate_sha256, "addresses": list(m.addresses)},
                    "fabric": dict(c["fabric"].source),
                    "exclusion": {"historical_sources": len(exd["sources"]), "pooled_total": exd["pooled_total"], "sim_registry": exd["sim_registry"], "sim_registry_note": exd["sim_registry_note"],
                                  "registry_snapshot": c["registry"], "exposure_receipt": exd["exposure_receipt"]},
                    "seeds_sha256": self.seeds_sha, "note": "written before the first observation; every digest and the registry snapshot held at every pair's end and at the batch's end"}
        self.manifest_sha = self.write("manifest.json", manifest, sc.manifest_findings)["sha256"]

    # -- checkpoints
    def hold_inputs(self, stage: str) -> None:
        c = self.c
        head = git(c["root"], "rev-parse", "HEAD").strip()
        if head != c["head"]:
            raise Invalid("input_drift", f"HEAD moved from {c['head'][:12]} to {head[:12]} ({stage})", stage=stage)
        for rel, sha in c["inputs"].items():
            p = c["root"] / rel
            if not p.is_file() or sha_file(p) != sha:
                raise Invalid("input_drift", f"the input {rel} changed or disappeared during the batch ({stage})", stage=stage)
        for abs_path, sha in c["external"].items():
            p = Path(abs_path)
            if not p.is_file() or sha_file(p) != sha:
                raise Invalid("input_drift", f"the external source {abs_path} changed or disappeared during the batch ({stage})", stage=stage)
        for rel, sha in c["tools"].items():
            p = REPO_ROOT / rel
            if not p.is_file() or sha_file(p) != sha:
                raise Invalid("input_drift", f"the tool file {rel} changed or disappeared during the batch ({stage})", stage=stage)
        try:
            recs, _ = bs.sim_registry(c["root"])
        except bs.ExclusionSourceRefusal as exc:
            raise Invalid("input_drift", f"the archived-set registry no longer reads: {exc} ({stage})", stage=stage)
        now = [[r.dir, r.status, r.seeds_sha256] for r in recs if r.dir != self.own_rel]
        if now != c["registry"]:
            raise Invalid("input_drift", f"the archived-set registry changed during the batch ({stage}): {len(c['registry'])} records at start, {len(now)} now", stage=stage)

    def hold_tree(self) -> None:
        """At the end: the only untracked / changed entries are this batch's own output."""
        c = self.c
        own = self.own_rel.rstrip("/") + "/"
        for ln in porcelain(c["root"]):
            path = ln[3:].strip()
            if not (ln.startswith("??") and (path == own or path.startswith(own))):
                raise Invalid("input_drift", f"the working tree carries a change that is not this batch's output: {ln!r}", stage="final")

    # -- one pair
    def setup_task(self, r: int, pdir: Path) -> tuple[ex.PublicTask, dict]:
        """task-v0.2 (section 7.1): the private plan persisted before the first target call; each setup observation saved on return
        before the next call; the PublicTask and task.json last. Returns (task, the search-target record)."""
        c = self.c
        l, o = self.pairs[r]
        plan = self.planned[r]
        fabric, mapping = c["fabric"], c["mapping"]
        self.current = {"pair": r, "stage": "target_setup", "role": SETUP_ROLE}
        setup = dict(bt.plan(r, l, o, mapping), written_utc=utc())
        digests = {"task_setup.json": self.write(f"pair_{r:03d}/task_setup.json", setup, sc.task_setup_findings)["sha256"]}
        plan["task"] = "in_progress"
        port = self.port_factory(fabric, SETUP_ROLE, r)
        parts = bl.public_parts(l)
        recs: dict[str, dict] = {}
        for phase, stim, name in (("target", parts["stimulus"], "target_search.json"), ("target_holdout", parts["holdout_stimulus"], "target_holdout.json")):
            self.dl.check()                                                     # a deadline here is `incomplete` with what was written kept
            try:
                rec = bt.observe_target(port, setup["planted_genome"], stim, mapping.addresses, phase)
            except KeyboardInterrupt:
                raise                                                           # the plan's task state stays in_progress / partial: nothing is lost, nothing fabricated
            except fm.DomainRefusal:
                plan["task"] = "invalid"
                raise Invalid("target_invalid", f"the target setup observation ({phase}) of the planted configuration was refused: DOMAIN — a contract break, never a redraw", role=SETUP_ROLE, stage="target_setup")
            except ex.SourceRefusal as exc:
                plan["task"] = "invalid"
                raise Invalid("target_invalid", f"the target setup observation ({phase}): {exc}", role=SETUP_ROLE, stage="target_setup")
            except Exception as exc:  # noqa: BLE001
                plan["task"] = "invalid"
                raise Invalid("unexpected_exception", f"the target setup observation ({phase}) raised {type(exc).__name__}: {exc}", role=SETUP_ROLE, stage="target_setup")
            if recs and rec["provenance_sha256"] != recs["target"]["provenance_sha256"]:
                plan["task"] = "invalid"
                raise Invalid("target_invalid", f"the target setup observation ({phase}) does not come from the first observation's source identity (a drift inside the setup)", role=SETUP_ROLE, stage="target_setup")
            doc = {"schema": bt.TARGET_SCHEMA[0], "schema_version": bt.TARGET_SCHEMA[1], "pair": r, "written_utc": utc(), **rec}
            digests[name] = self.write(f"pair_{r:03d}/{name}", doc, lambda d, ph=phase: sc.target_observation_findings(d, ph))["sha256"]   # saved at once, before the next call
            recs[phase] = doc
            plan["task"] = "partial"
        if port.calls != sum(bt.SETUP_COST.values()):
            plan["task"] = "invalid"
            raise Invalid("target_invalid", f"the target setup made {port.calls} port calls, not {sum(bt.SETUP_COST.values())}", role=SETUP_ROLE, stage="target_setup")
        if recs["target"]["provenance_sha256"] != recs["target_holdout"]["provenance_sha256"]:
            plan["task"] = "invalid"
            raise Invalid("target_invalid", "the two setup observations do not come from one source identity (a drift inside the setup)", role=SETUP_ROLE, stage="target_setup")
        try:
            task, tdoc = bt.finish(setup, recs["target"], recs["target_holdout"], digests)
        except bl.TargetRefusal as exc:
            plan["task"] = "invalid"
            raise Invalid("target_invalid", f"the planted configuration's trace is not a target: {exc}", role=SETUP_ROLE, stage="target_setup")
        self.write(f"pair_{r:03d}/task.json", dict(tdoc, written_utc=utc()), sc.task_findings)
        plan["task"] = "complete"
        return task, recs["target"]

    def run_pair(self, r: int) -> None:
        c = self.c
        l, o = self.pairs[r]
        plan = self.planned[r]
        plan["status"] = "in_progress"
        pdir = self.out / f"pair_{r:03d}"
        pdir.mkdir(exist_ok=False)
        task, target_search = self.setup_task(r, pdir)
        self.current = {"pair": r, "stage": "arms", "role": None}
        fabric, mapping = c["fabric"], c["mapping"]
        results: dict[str, dict] = {}
        views: dict[str, bc.MapView] = {}
        prefixes: dict = {}
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
            try:
                d = res.as_dict()
            except Exception as exc:  # noqa: BLE001
                plan["arms"][role] = "result_malformed"
                self.quarantine(f"pair_{r:03d}/arm_{role}.result.QUARANTINE.json", r, role, "engine_return", [f"as_dict raised {type(exc).__name__}: {exc}"], res)
                raise Invalid("schema", f"the engine's return cannot be read as a RunResult ({type(exc).__name__}); quarantined", role=role, stage="engine_return")
            doc = {"schema": "b4_sim_arm_result", "schema_version": "1.0.0", "pair": r, "role": role, "engine_arm": ENGINE_ARM[role], "landscape_seed": l,
                   "operator_seed": o, "budget": B_MAX, "port_calls": port.calls, "wall_s": round(wall, 6), "written_utc": utc(), "result": d}
            f = sc.arm_result_findings(doc, task, {"pair": r, "role": role, "landscape_seed": l, "operator_seed": o, "x_control_seed": x_seed})
            if f:
                plan["arms"][role] = "result_malformed"
                self.quarantine(f"pair_{r:03d}/arm_{role}.result.QUARANTINE.json", r, role, "engine_return", f, doc)
                raise Invalid("schema", f"arm_{role}.result.json: the returned RunResult does not validate (quarantined): " + "; ".join(f[:4]), role=role, stage="engine_return")
            self.write(f"pair_{r:03d}/arm_{role}.result.json", doc, None)
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
                    view_f += ctl.verify_d_view(d["given_view"], results["F"], task, l)
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
                    dv, dinfo = ctl.d_view(d, task, l)
                except ctl.ControlInputRefusal as exc:
                    raise Invalid("contract", f"D's input cannot be built from F's record: {exc}", role="D", stage="controls")
                views["D"], views["Omega"], views["A0"] = dv, bc.oracle_view(mapping), bc.address_only_view(mapping.addresses)
                self.write(f"pair_{r:03d}/controls.json", {"schema": "b4_sim_controls", "schema_version": "1.0.0", "pair": r, "x_control_seed": x_seed, "d": dinfo,
                                                           "d_view": dv.as_dict(), "omega_view": views["Omega"].as_dict(), "a0_view": views["A0"].as_dict(), "written_utc": utc()}, sc.controls_findings)
            if role == "O":
                self.current["stage"] = "k7"
                plan["k7"] = "in_progress"
                for B in GRID:
                    self.dl.check()
                    prefixes[str(B)] = sn.prefix_states(d, task, B)
                    if prefixes[str(B)]["findings"]:
                        self.write(f"pair_{r:03d}/k7.json", {"schema": "b4_sim_k7", "schema_version": "1.0.0", "pair": r, "arm": "O", "grid": list(GRID), "prefixes": prefixes, "complete": False, "written_utc": utc()}, sc.k7_findings)
                        raise Invalid("contract", f"K7 prefix at B = {B}: " + "; ".join(prefixes[str(B)]["findings"][:3]), role="O", stage="k7")
                self.write(f"pair_{r:03d}/k7.json", {"schema": "b4_sim_k7", "schema_version": "1.0.0", "pair": r, "arm": "O", "grid": list(GRID), "prefixes": prefixes, "complete": True, "written_utc": utc()}, sc.k7_findings)
                plan["k7"] = "complete"
                self.current["stage"] = "arms"
        # K9 — a refusal, an error or an interrupt inside it leaves the partial on disk (F6)
        self.current.update(stage="k9", role="K9")
        plan["k9"] = "in_progress"
        self.dl.check()
        try:
            k9r = k9.coverage(task, self.port_factory(fabric, "K9", r), mapping, fabric, l, check=self.dl.check)
        except KeyboardInterrupt as exc:
            # `partial` promises a stopped document on disk; an interrupt before anything returned (nothing carried, or the
            # partial not even quarantinable) leaves the stage `in_progress`: entered, no record (the owner's review of 2026-10-19)
            plan["k9"] = "partial" if self._keep_partial(r, "k9", getattr(exc, "k9_partial", None), lambda doc: sc.k9_findings(doc, task, l), "K9", "interrupt") else "in_progress"
            raise
        except Exception as exc:  # noqa: BLE001 — DOMAIN, another refusal or an error: invalid, the partial kept
            plan["k9"] = "invalid"
            kept = self._keep_partial(r, "k9", getattr(exc, "k9_partial", None), lambda doc: sc.k9_findings(doc, task, l), "K9", "refusal")
            raise Invalid("k9_invalid", f"K9 observation refused or failed: {type(exc).__name__}: {exc}" + ("" if kept else " [no partial record was available]"), role="K9", stage="k9")
        if not self.write_or_quarantine(f"pair_{r:03d}/k9.json", {"schema": "b4_sim_k9", "schema_version": "1.2.0", "pair": r, **k9r}, lambda doc: sc.k9_findings(doc, task, l), r, "K9", "k9_return"):
            plan["k9"] = "invalid"
            raise Invalid("schema", "k9.json: the K9 record returned does not validate (quarantined)", role="K9", stage="k9")
        if not k9r["complete"]:
            plan["k9"] = "partial"
            raise StopWork(k9r["stopped"]["reason"])
        plan["k9"] = "complete"
        # K10 — no corner is observed after the first refused one (F5); the partial is kept on every failure (F6)
        self.current.update(stage="k10", role="K10")
        plan["k10"] = "in_progress"
        self.dl.check()
        try:
            k10r = k10.seed_k10(task, self.port_factory(fabric, "K10", r), l, tau=k10.TAU, check=self.dl.check)
        except k10.K10Invalid as exc:
            plan["k10"] = "invalid"
            self._keep_partial(r, "k10", exc.partial, lambda doc: sc.k10_findings(doc, task, l), "K10", "refusal")
            raise Invalid("k10_invalid", str(exc), role="K10", stage="k10")
        except KeyboardInterrupt as exc:
            # `partial` promises a stopped document on disk; an interrupt before anything returned (nothing carried, or the
            # partial not even quarantinable) leaves the stage `in_progress`: entered, no record (the owner's review of 2026-10-19)
            plan["k10"] = "partial" if self._keep_partial(r, "k10", getattr(exc, "k10_partial", None), lambda doc: sc.k10_findings(doc, task, l), "K10", "interrupt") else "in_progress"
            raise
        except Exception as exc:  # noqa: BLE001
            plan["k10"] = "invalid"
            kept = self._keep_partial(r, "k10", getattr(exc, "k10_partial", None), lambda doc: sc.k10_findings(doc, task, l), "K10", "refusal")
            raise Invalid("k10_invalid", f"K10 observation refused or failed: {type(exc).__name__}: {exc}" + ("" if kept else " [no partial record was available]"), role="K10", stage="k10")
        if not self.write_or_quarantine(f"pair_{r:03d}/k10.json", {"schema": "b4_sim_k10", "schema_version": "1.0.0", "pair": r, **k10r}, lambda doc: sc.k10_findings(doc, task, l), r, "K10", "k10_return"):
            plan["k10"] = "invalid"
            raise Invalid("schema", "k10.json: the K10 record returned does not validate (quarantined)", role="K10", stage="k10")
        if not k10r["complete"]:
            plan["k10"] = "partial"
            raise StopWork(k10r["stopped"]["reason"])
        plan["k10"] = "complete"
        # curves and the row the statistics use
        self.current.update(stage="curves", role=None)
        self.dl.check()
        curves = curves_of(results, r, l, o, target_search["q_grid"])
        self.write(f"pair_{r:03d}/curves.json", curves, sc.curves_findings)
        self.rows.append(row_of(r, l, o, curves, prefixes, k9r, k10r))
        self.hold_inputs(f"pair {r} end")
        plan["status"] = "complete"
        self.write(f"pair_{r:03d}/index.json", {"schema": "b4_sim_pair_index", "schema_version": "1.1.0", "pair": r, "landscape_seed": l, "operator_seed": o, "status": "complete",
                                                "task": plan["task"], "arms": dict(plan["arms"]), "files": [dict(e, path=e["path"].split("/", 1)[1]) for e in self.files if e["path"].startswith(f"pair_{r:03d}/")],
                                                "written_utc": utc()}, sc.pair_index_findings)

    def _keep_partial(self, r: int, name: str, partial: dict | None, validator, role: str, stage: str) -> bool:
        """Write the partial K9 / K10 record (or its quarantine when it does not validate); False when none was carried."""
        if partial is None:
            return False
        version = "1.2.0" if name == "k9" else "1.0.0"
        doc = {"schema": f"b4_sim_{name}", "schema_version": version, "pair": r, **partial}
        try:
            self.write_or_quarantine(f"pair_{r:03d}/{name}.json", doc, validator, r, role, stage)
        except (Invalid, OSError):
            return False
        return True

    # -- the statistics stage
    def stats(self) -> None:
        self.current = {"pair": None, "stage": "statistics", "role": None}
        self.summary, self.stats_record = summarise_batch(self.rows, self.c["count"], check=self.dl.check, standing=standing_for(self.c["label"]))

    # -- the end: the archive verified, the report written — both conditions of success (F4, F8)
    def finish(self, status: str, stop: dict | None, exit_code: int) -> dict:
        self.current["stage"] = "finish"
        if status == "complete":
            try:
                self.dl.check()                                     # a finalisation unit never starts after the expiry
            except StopWork as exc:
                return self.finish("incomplete", {"kind": "deadline", "detail": f"the deadline expired before finalisation: {exc}", "role": None, "stage": "finalisation"}, 3)
        for p in self.planned:
            if p["status"] == "in_progress":
                p["status"] = "partial"
        stopped_doc = None
        if stop is not None:
            stopped_doc = {"schema": "b4_sim_stopped", "schema_version": "1.1.0", "status": status, "kind": stop["kind"], "detail": stop["detail"], "pair": self.current.get("pair"),
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
                    missing.append(f"pair {p['pair']}: {p['status']} (task {p['task']}, arms {p['arms']}, k7 {p['k7']}, k9 {p['k9']}, k10 {p['k10']})")
        report = {"schema": "b4_sim_report", "schema_version": "1.1.0", "status": status, "label": self.c["label"], "fixture": self.c["schedule"] is not None, "count": self.c["count"],
                  "head": self.c["head"], "generated_utc": utc(), "deadline": self.dl.record(), "standing": standing_for(self.c["label"]), "thresholds": th.THRESHOLDS,
                  "identity": {"seeds_sha256": self.seeds_sha, "manifest_sha256": self.manifest_sha, "hypothesis_sha256": hy.HYPOTHESIS_SHA256, "certificate_sha256": bm.CERTIFICATE_SHA256,
                               "inputs": self.c["inputs"], "out": self.own_rel, "protocol_sha256": self.c["protocol"]["protocol_sha256"]},
                  "pairs": [dict(p) for p in self.planned], "files": [dict(e) for e in self.files], "stopped": stopped_doc,
                  "summary": self.summary if status == "complete" else None, "missing": missing, "self_validation": {}}
        try:
            self_validation = sv.verify_run_dir(self.out, report=report, deep=(status == "complete"))
        except Exception as exc:  # noqa: BLE001 — the verifier itself failing is a finding, never a pass
            self_validation = {"verifier": [f"the archive verifier raised {type(exc).__name__}: {exc}"]}
        if status == "complete" and self_validation:
            first = next(iter(self_validation.items()))
            return self.finish("invalid", {"kind": "self_validation", "detail": f"the archive does not verify: {first[0]}: {first[1][0]} ({sum(len(v) for v in self_validation.values())} findings)",
                                           "role": None, "stage": "finalisation", "traceback": json.dumps(self_validation)[:20000]}, 1)
        if status == "complete":
            # the deep verification was a long unit: the deadline (R4) and every input, the registry and the tree (R5) are
            # checked again before the success is published, and the deadline record is taken AFTER these checks
            try:
                self.dl.check()
                self.hold_inputs("publication")
                self.hold_tree()
                self.dl.check()
            except StopWork as exc:
                return self.finish("incomplete", {"kind": "deadline", "detail": f"the deadline expired during the final verification: {exc}", "role": None, "stage": "publication"}, 3)
            except Invalid as exc:
                return self.finish("invalid", {"kind": exc.kind, "detail": exc.detail, "role": None, "stage": "publication"}, 1)
            report["deadline"] = self.dl.record()
            report["generated_utc"] = utc()
        report["self_validation"] = self_validation
        out = {"status": status, "exit_code": exit_code, "out": str(self.out), "stopped": stopped_doc, "report": report}
        try:
            self.write("sim_report.json", report, sc.report_findings)
        except (Invalid, OSError) as exc:                           # the report is a condition of success: no report, no success (F4)
            msg = f"sim_report.json could not be validated / written: {type(exc).__name__}: {exc}"
            try:
                (self.out / "sim_report.ERROR.txt").write_text(msg + "\n" + json.dumps({"original_status": status, "original_exit_code": exit_code}) + "\n")
            except OSError:
                pass
            out.update(status="invalid", exit_code=1, report_error=msg, original_status=status)
        return out


def manifest_constants() -> dict:
    """The constants a manifest records; the verifier binds a manifest to exactly these (R2)."""
    return {"engine": {"version": be.ENGINE_VERSION, "mu": be.MU, "lambda": be.LAMBDA, "kmax": be.KMAX}, "cartographer": bc.CARTO_VERSION,
            "task": bl.TASK_VERSION, "target": {"rule": bl.PLANTED_RULE, "salt": bl.SALT_TARGET, "setup_cost": bt.SETUP_COST, "setup_role": SETUP_ROLE},
            "probes_per_F": PROBES, "expected_cost": EXPECTED_COST, "k9_panel": k9.PANEL_VERSION,
            "k9_applicability": {"all_panel": k9.APPLICABILITY_ALL_PANEL, "conditional": k9.APPLICABILITY_CONDITIONAL, "judged": k9.JUDGED_ESTIMAND},
            "k10_salt": k10.SALT, "tau": k10.TAU, "gonogo": th.THRESHOLDS["gonogo"],
            "prng": "b4_rng.Rng (xorshift64, a derived copy of b1_carto.Rng); the bootstrap random.Random", "anchor": th.THRESHOLDS["anchor"], "controls": th.THRESHOLDS["controls"]}


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
        f.append(f"cost {json.dumps(d.get('cost'), sort_keys=True)} is not the arm's {json.dumps(EXPECTED_COST[role], sort_keys=True)}")   # deterministic text: the audit is compared offline
    total = sum(EXPECTED_COST[role].values())
    if not (d.get("observations") == total == port_calls == len(d.get("ledger") or [])):
        f.append(f"observations {d.get('observations')} / port calls {port_calls} / ledger {len(d.get('ledger') or [])} are not all {total}")
    L = d.get("ledger") or []
    if sum(1 for e in L if e.get("phase") == "holdout") != 1 or not L or L[-1].get("phase") != "holdout":
        f.append("the holdout is not exactly the last record, once")
    if d.get("arm") != ENGINE_ARM[role] or d.get("budget") != B_MAX or d.get("task_digest") != task.digest():
        f.append("arm / budget / task do not match the plan")
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


def curves_of(results: dict, r: int, l: int, o: int, target_search_grid: list) -> dict:
    """The best-so-far at the grid per arm, F's end-to-end values, the holdouts, and the NON-TRIVIALITY record of section 7.1: whether
    the target's search trace equals arm R's EXISTING base observation under the same stimulus (read from records; no observation added)."""
    best = {role: [results[role]["best_trace"][B - 1] for B in GRID] for role in ROLES}
    base = results["R"]["base_fit"]
    r_base_grid = results["R"]["ledger"][0]["q_grid"] if results["R"].get("ledger") else None
    f_trace = results["F"]["best_trace"]
    fe = []
    for T in GRID:
        if T <= PROBES:
            fe.append({"T": T, "value": results["F"]["base_fit"], "mapping_in_progress": True})
        else:
            fe.append({"T": T, "value": f_trace[T - PROBES - 1], "mapping_in_progress": False})
    return {"schema": "b4_sim_curves", "schema_version": "1.1.0", "pair": r, "landscape_seed": l, "operator_seed": o, "grid": list(GRID), "base_fit": base,
            "best_at_grid": best, "f_end_to_end_at_grid": fe, "holdout": {role: results[role]["champion_holdout"] for role in ROLES},
            "target_equals_R_base_search_trace": r_base_grid is not None and ex.sha256_json(r_base_grid) == ex.sha256_json(target_search_grid), "written_utc": utc()}


def row_of(r: int, l: int, o: int, curves: dict, prefixes: dict, k9r: dict, k10r: dict) -> dict:
    """The row of the pooled statistics: the curves, K7's counts, BOTH K9 records (the judged conditional and the all-panel), K10."""
    return {"pair": r, "landscape_seed": l, "operator_seed": o, "base_fit": curves["base_fit"], "best_at_grid": curves["best_at_grid"],
            "f_end_to_end_at_grid": [e["value"] for e in curves["f_end_to_end_at_grid"]],
            "k7_not_unknown_at_grid": [prefixes[str(B)]["not_unknown"] for B in GRID],
            "k9": k9r["summary"]["per_semantic"], "k9_all_panel": k9r["summary"]["per_semantic_all_panel"], "k9_all_seven": k9r["summary"]["all_seven_positive_controls"],
            "k10_max_abs": k10r["max_abs_index"], "k10_outcome": k10r["outcome"]}


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


def summarise_batch(rows: list[dict], S: int, check=None, standing: str = STANDING) -> tuple[dict, dict]:
    """Descriptive statistics over the completed rows (= all S rows when the batch is complete), per grid budget and at the
    candidate B*; every value beside the fixed threshold it is compared with elsewhere. Pure; `check` is called before each
    budget's N scan, each bootstrap and each K9 / K10 unit. `standing` is the text the summary carries (`standing_for(label)`)."""
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
    # K9 over all S rows: the JUDGED conditional record (b') and the DESCRIPTIVE all-panel record (b), each per semantic; (a) from the all-panel positive controls
    if check:
        check()

    def k9_block(key: str) -> dict:
        out: dict = {}
        for s in k9.SEMANTICS:
            fr = [row[key][s]["fraction"] for row in rows]
            na = sum(1 for x in fr if x is None)
            out[s] = {"seeds_with_positive_control": sum(1 for row in rows if row["k9_all_panel"][s]["positive_control"]), "not_assessable_seeds": na,
                      "median_coverage_over_all_S": (gs.median(fr) if na == 0 else None), "median_rule": T["K9"]["median_population"], "conditional_on_A8": s == "ff_init"}
        return out
    k9s, k9s_all = k9_block("k9"), k9_block("k9_all_panel")
    k9_all = sum(1 for row in rows if row["k9_all_seven"])
    # K10 over all S rows
    if check:
        check()
    k10s = st.summarise([row["k10_max_abs"] for row in rows], k10.TAU, S)
    summary = {"S": S, "grid": list(GRID), "per_budget": per_budget, "eligible_budgets": eligible,
               "candidate_B_star": {"value": b_star, "reason_if_none": reason, "note": T["B_star"]["no_eligible_budget"]}, "at_candidate_B_star": at,
               "k9": {"judged_estimand": k9.JUDGED_ESTIMAND, "per_semantic": k9s, "per_semantic_all_panel": k9s_all, "seeds_with_all_seven_positive_controls": k9_all, "fraction_of_S": k9_all / S},
               "k10": k10s, "thresholds_for_reference": T, "standing": standing}
    return summary, record


# ------------------------------------------------------------------ the batch runner and the CLI
def run_batch(root: Path, label: str, count: int, deadline_s: int, out: Path | None = None, clock=time.monotonic, port_factory=None, schedule: FixtureSchedule | None = None,
              mode: str = "exploration") -> dict:
    """`mode` "exploration" (the default and the CLI's only mode) accepts b4-sim-<n> labels; "gate" accepts b4-gate-<n> and is
    reached through b4_gate.py only (unit 2b-4). Everything else — the pre-flight, the freezing order, the arms, the audits, the
    diagnostics, the statistics, the archive verification — is the same batch."""
    try:
        dl = Deadline(deadline_s, clock=clock) if isinstance(deadline_s, int) and not isinstance(deadline_s, bool) and deadline_s > 0 else None
        ctx = preflight(root, label, count, deadline_s, out, schedule, mode)
    except Refusal as exc:
        return {"status": "refused", "exit_code": 2, "out": None, "reason": str(exc), "stopped": None, "report": None}
    try:
        create_out_dir(ctx)
    except FileExistsError:
        return {"status": "refused", "exit_code": 2, "out": None, "reason": f"{ctx['out']} appeared before it could be created exclusively", "stopped": None, "report": None}
    except Refusal as exc:
        return {"status": "refused", "exit_code": 2, "out": None, "reason": str(exc), "stopped": None, "report": None}
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
        batch.dl.check()                                            # after the last statistics unit (F8)
        batch.current = {"pair": None, "stage": "final", "role": None}
        batch.hold_inputs("final")
        batch.hold_tree()
        batch.dl.check()                                            # before the finalisation units (F8)
    except StopWork as exc:
        return batch.finish("incomplete", {"kind": "deadline", "detail": str(exc), "role": batch.current.get("role"), "stage": batch.current.get("stage")}, 3)
    except KeyboardInterrupt:
        return batch.finish("incomplete", {"kind": "interrupted", "detail": "KeyboardInterrupt: an external interrupt, not a model event", "role": batch.current.get("role"), "stage": batch.current.get("stage")}, 3)
    except Invalid as exc:
        return batch.finish("invalid", {"kind": exc.kind, "detail": exc.detail, "role": exc.role or batch.current.get("role"), "stage": exc.stage or batch.current.get("stage")}, 1)
    except Exception as exc:  # noqa: BLE001 — never lose what is on disk; name it
        return batch.finish("invalid", {"kind": "unexpected_exception", "detail": f"{type(exc).__name__}: {exc}", "role": batch.current.get("role"),
                                        "stage": batch.current.get("stage"), "traceback": traceback.format_exc()}, 1)
    return batch.finish("complete", None, 0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="B4 host-only exploration harness (values beside thresholds; no gate verdict). Running it needs the owner's authorisation. "
                                             "Production labels only: a mechanics fixture batch has no CLI.")
    ap.add_argument("--label", required=True, help="b4-sim-<n> (b4-sim-1 / b4-sim-2 retired, b4-sim-3 / b4-gate-1 consumed; the next exploration label is b4-sim-4)")
    ap.add_argument("--seeds", required=True, type=int, help="S, the number of pairs planned")
    ap.add_argument("--deadline-s", required=True, type=int, help="the soft monotonic deadline in seconds, from the pre-flight on (no default)")
    ap.add_argument("--out", default=None, help=f"the output directory, directly under {SIM_REL}/ and named <label>_…; default <label>_<UTC>")
    a = ap.parse_args(argv)
    res = run_batch(REPO_ROOT, a.label, a.seeds, a.deadline_s, Path(a.out) if a.out else None)
    print(json.dumps({k: v for k, v in res.items() if k in ("status", "exit_code", "out", "reason", "report_error")}, indent=1))
    return res["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
