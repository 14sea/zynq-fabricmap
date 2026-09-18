#!/usr/bin/env python3
"""B3 lifecycle 2 — the manifest and its freeze / qualification / calibration / plan lifecycle
(host-only; preregistration v0.3.1 §2, §6a, §8; architecture v0.3 §6).

    b3_manifest.py init      [--manifest M]
    b3_manifest.py freeze    --manifest M --prereg-sha256 H            (the owner)
    b3_manifest.py qualify   --manifest M --evidence-dir D             (pin the B3Q record + the calibration)
    b3_manifest.py plan      --manifest M --plan P                     (pin the plan derived from the calibration)
    b3_manifest.py verify    [--manifest M] [--evidence-dir D]

There is no flag that skips a check, tolerates a missing prerequisite or substitutes an authority.

EVERY verify runs this fixed prefix, in this order, and only then looks at anything of B3's own:
  1. the seven AUDITED INDIRECT FROZEN INPUTS (audit §7a) — the path set is exactly FROZEN_INPUTS, each
     file present and hashing to the frozen digest, the absent or drifted one named;
  2. the production B2 verify, required to give S3 / true / null / aec84514… — a Refusal B2 declares is
     re-raised as "B2 lineage: …";
  3. the B1 lineage: the B1 manifest by hash, its carrier and board, and its qualification chain
     re-verified FRESH — a refusal B1's qualification declares is re-raised as "B1 lineage: …";
  4. the B3 pin table (its bytes AND its content, through the production b3_pins.verify), the image
     (build evidence, binary, size, digest), the preregistration, B3Q's pinned experiment, the
     experiment / seeds / map / instrument identity rebuilt from the gate and the plan tool, the
     preregistered prediction rebuilt in full with the stop rule still passing, and the stage's own
     content.
Any OTHER exception propagates unchanged: on the command line it is an INTERNAL ERROR (exit 3, with its
traceback), never a refusal. Nothing here unpacks the completion archive or writes into the working tree.

The lifecycle (B2's, stage for stage) and the ONLY changes each transition licenses:
  S0 -> S1  freeze    history, image.board_ready, prereg.frozen, prereg.sha256, status
  S1 -> S2  qualify   qualification, qualified, calibration, status, history
  S2 -> S3  plan      plan, status, history
`qualification_plan` (B3Q's frozen experiment) never changes after S0. `check_transition` holds a
before / after pair to exactly one of these; the command line applies it to the bytes on disk before an
atomic replace, and a failure leaves the original bytes.

S0 has no optional prerequisite: no allow-missing, no placeholder digest, no S0 without an image, no pin
table pinned by hash alone. `init` builds the candidate from the tree and then runs the SAME verify on
it; whatever is absent is a named refusal and no manifest is written (and `init` never overwrites one).

S2: the qualification record is RECONSTRUCTED from the evidence directory every time (B1's eleven
qualification files plus runner_session.json, the export seal checked) — never a caller's summary; the
evidence is RE-ADJUDICATED by the production `b3_runner.readjudicator` (the S1 manifest's pinned B3Q
plan / prediction -> the session plan -> `judge_session`), whose outcome, measured rate, verified audit
policy and qualification block (123 fitness values, 40 ledger entries, 2 baselines, the sequence digest)
must equal the evidence's; the calibration {rate_per_hour, margin 0.85, rate_for_split, the verified audit
policy, the split's session count} is recomputed from that and compared whole. No stored flag is trusted.

S3: `plan_findings` rebuilds the canonical plan from the calibration's rate_per_hour and the prediction in
full — every O run's every ledger entry — and compares path by path with `b3_gate.deep_findings`; the split
must be DETERMINED; the manifest's sessions / total_records / digests must be the files'.

Seams (`Seams`): a test may inject the pin verifier, the B2 verify, the B1 chain verify and the
re-adjudicator. `None` ALWAYS means the production path — never a skip. While b3/host/b3_pins.py, the pin
table, the image evidence or the B3Q documents do not exist, the production init / verify refuse by name.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_gate as b3g  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_plan as pl  # noqa: E402

SCHEMA = "b3_manifest"
SCHEMA_VERSION = "0.1.0"
MANIFEST_REL = "manifests/b3_manifest.json"
MANIFEST = REPO_ROOT / MANIFEST_REL
PIN_TABLE_REL = "manifests/b3_instrument_pins.json"
B1_MANIFEST_REL = "manifests/b1_manifest.json"
B2_MANIFEST_REL = "manifests/b2_manifest.json"
B2_MANIFEST_SHA256 = "aec84514ff29dda7957d46d650a370e155f6dc60a281b992e148f8a0fae6c4c0"
B2_REQUIRED = {"stage": "S3", "qualified": True, "refusal": None, "manifest_sha256": B2_MANIFEST_SHA256}
# The seven audited indirect frozen inputs (audit §7a; preregistration §2) — the path SET is fixed and the
# digests are the preregistration's; the old top-level ledger schema is one of them and stays where it is.
FROZEN_INPUTS = {
    B2_MANIFEST_REL: B2_MANIFEST_SHA256,
    "manifests/b2_instrument_pins.json": "82a5f2fb1d246c9cab506df65d53a0f329ca219ec3c5cdf50a272ff79ee319d1",
    "evidence/b2/b2_completion_inputs_2026-09-17/inputs.tar.zst": "20300d5f2476beafaa9411c11f2a412eb91f01149bf4318e79ccee2706337767",
    "evidence/b2/b2_completion_inputs_2026-09-17/archive.json": "ca5fedd7bb7a119883a5b74a9f19b0d02d147e6183404ddde8766b03abd46c5d",
    "evidence/b3/sim/sim_report.json": "d9c432f8b797933e26e24a77d33e5884f29c03c2be88e6c59c61bc0af250adf9",
    "evidence/b3/sim/raw_F1.json": "ccf4d24622c7cfb3ee698623047ea461303c603449d47ffb0452f83656b74c53",
    "schemas/specimen_ledger.schema.json": "7cc74295b5c76806bddaa995675b77dfea598fb6ad42fa4ec7bfbf426d12563d",
}
B3_VARIANT = "0x42310001"
PREREG_REL = "docs/b3_preregistration.md"
IMAGE_REL = "b3/firmware/bsp/out/b3_app.bin"
BUILD_EVIDENCE_REL = "evidence/b3/build_evidence.json"
GATE_REL = "evidence/b3/gate_2/gate_report.json"
PLAN_REL, PREDICTION_REL = "evidence/b3/plan.json", "evidence/b3/prediction.json"
QUAL_PLAN_REL, QUAL_PREDICTION_REL = "evidence/b3/b3q_plan.json", "evidence/b3/b3q_prediction.json"

QUAL_SCHEMA = "b3_image_qualification"
QUAL_SCHEMA_VERSION = "1.0.0"
QUAL_SESSION = "B3Q"
MANIFEST_AT_RUN = "manifest_at_run.json"
RUNNER_SESSION = "runner_session.json"
QUAL_RECORD_KEYS = ("schema", "schema_version", "session", "evidence_dir", "files", "outcome", "measured_rate_per_hour",
                    "audit_policy", "qualification_block", "binding")
QUAL_BINDING_KEYS = ("session", "image_sha256", "prereg_sha256", "carrier_sha256", "carrier_variant", "map_canonical_json_sha256",
                     "b3_manifest_sha256", "qualification_plan_sha256", "qualification_prediction_sha256")
QUAL_BLOCK_KEYS = ("fitness_values", "ledger_entries", "baselines", "fitness_sequence_sha256")
CALIBRATION_KEYS = ("rate_per_hour", "margin", "rate_for_split", "audit_policy", "sessions", "pairs_per_session_max", "source")

STAGES = ("S0", "S1", "S2", "S3")
STATUS = {
    "S0": "S0 INIT — derived from the tree; not frozen; no qualification; no plan; NO BOARD RULING",
    "S1": "S1 FROZEN — prereg pinned, image board_ready by the owner; awaiting the B3Q ruling pair",
    "S2": "S2 QUALIFIED — the B3Q record reconstructed from its evidence and pinned, the calibration written from it; awaiting the plan (S3)",
    "S3": "S3 PLANNED — the plan pinned from the calibration; every B3 ruling pair binds to THIS manifest's sha256",
}
HISTORY = {"S0": [], "S1": ["S1 freeze"], "S2": ["S1 freeze", "S2 qualify"], "S3": ["S1 freeze", "S2 qualify", "S3 plan"]}
# the ONLY paths each legal transition may change
TRANSITIONS = {
    ("S0", "S1"): (("history",), ("image", "board_ready"), ("prereg", "frozen"), ("prereg", "sha256"), ("status",)),
    ("S1", "S2"): (("qualification",), ("qualified",), ("calibration",), ("status",), ("history",)),
    ("S2", "S3"): (("plan",), ("status",), ("history",)),
}
SINCE_RUN = tuple(dict.fromkeys(TRANSITIONS[("S1", "S2")] + TRANSITIONS[("S2", "S3")]))     # manifest_at_run (S1) -> now (S2 / S3)
MANIFEST_KEYS = ("schema", "schema_version", "lifecycle", "status", "instrument", "frozen_inputs", "b2_authority", "carrier_lineage",
                 "board", "carrier", "prereg", "image", "map", "universe", "experiment", "audit", "seeds", "prediction",
                 "instrument_pins", "qualification_plan", "qualification", "qualified", "calibration", "plan", "rulings_binding", "history")
PLAN_NON_OPERATIONAL = pl.PLAN_NON_OPERATIONAL


class Refusal(Exception):
    pass


@dataclass
class Seams:
    """What a test may replace. None is ALWAYS the production path, never a skip."""
    pins: object = None             # (manifest, root) -> dict           production: b3_pins.verify
    b2: object = None               # (root) -> the B2 verify's result   production: b2_manifest.verify + b2_runner.readjudicator
    b1: object = None               # (b1_manifest, root) -> anything    production: b1_qualification.verify
    readjudicate: object = None     # (evidence_dir, manifest_at_run) -> the session verdict    production: b3_runner.readjudicator


# ------------------------------------------------------------------ small things


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canonical_sha256(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def render(manifest: dict) -> str:
    return json.dumps(manifest, indent=1, sort_keys=True) + "\n"


def manifest_sha256(manifest: dict) -> str:
    """The hash of the manifest AS A FILE is (indent 1, sorted keys, trailing newline) — what a ruling
    and a qualification record bind to."""
    return hashlib.sha256(render(manifest).encode()).hexdigest()


def _hex64(v) -> bool:
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _finite_positive(x) -> bool:
    import math
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def _resolve(rel, root: Path) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else Path(root) / rel


def _relative(p: Path, root: Path) -> str:
    p, root = Path(p).resolve(), Path(root).resolve()
    return str(p.relative_to(root)) if p.is_relative_to(root) else str(p)


def _load_json(path: Path, what: str):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise Refusal(f"{what} is not readable JSON: {exc}") from None


def _strip(m: dict, paths) -> dict:
    m = copy.deepcopy(m)
    for path in paths:
        d = m
        for k in path[:-1]:
            d = d.get(k) if isinstance(d, dict) else None
            if not isinstance(d, dict):
                break
        else:
            d.pop(path[-1], None)
    return m


def _same(block: str, got, want) -> None:
    """A derived block, held to its rebuild path by path."""
    diff = b3g.deep_findings(want, got, block)
    if diff:
        raise Refusal(f"the manifest's {block} is not what the tree gives now: " + "; ".join(diff[:4]))


# ------------------------------------------------------------------ 1–3: the fixed prefix


def check_frozen_inputs(block, root: Path) -> str:
    """The seven, by existence and digest, FIRST — the path set exactly fixed, the digests the
    preregistration's, the absent or drifted one named."""
    if not isinstance(block, dict):
        raise Refusal("frozen inputs: the manifest carries no frozen_inputs block")
    if set(block) != set(FROZEN_INPUTS):
        missing, extra = sorted(set(FROZEN_INPUTS) - set(block)), sorted(set(block) - set(FROZEN_INPUTS))
        raise Refusal(f"frozen inputs: the path set is not exactly the seven audited inputs (missing {missing}, unexpected {extra})")
    for rel, want in FROZEN_INPUTS.items():
        if block[rel] != want:
            raise Refusal(f"frozen inputs: the manifest pins {rel} at {str(block[rel])[:16]}…, the frozen digest is {want[:16]}…")
    for rel, want in FROZEN_INPUTS.items():
        p = Path(root) / rel
        if not p.is_file():
            raise Refusal(f"frozen inputs: {rel} is absent")
        got = sha256_file(p)
        if got != want:
            raise Refusal(f"frozen inputs: {rel} drifted ({got[:16]}… is not the frozen {want[:16]}…)")
    return f"ok ({len(FROZEN_INPUTS)} by existence and digest)"


def _production_b2(root: Path) -> dict:
    import b2_manifest as bman  # noqa: E402
    import b2_runner  # noqa: E402
    import claimb_r1p_instrument as inst  # noqa: E402
    m = json.loads((Path(root) / B2_MANIFEST_REL).read_text())
    return bman.verify(m, readjudicate=b2_runner.readjudicator(m, inst.DEFAULT_ROOT), root=Path(root), b1_root=Path(root))


def _b2_refusals() -> tuple:
    """The refusal classes B2's verify path DECLARES; only these become "B2 lineage: …"."""
    import b2_manifest as bman  # noqa: E402
    out = [bman.Refusal]
    runner = sys.modules.get("b2_runner")
    if runner is not None and isinstance(getattr(runner, "Refusal", None), type):
        out.append(runner.Refusal)
    return tuple(out)


def check_b2_authority(block, root: Path, seams: Seams) -> str:
    """The production B2 verify, required S3 / true / null / aec84514… . Nothing is unpacked or repaired
    here: if the B2 lineage does not verify (e.g. the 15 completion inputs are not in the tree), that is
    the refusal, and restoring them is the owner's act."""
    want_block = b2_authority_block()
    if block != want_block:
        raise Refusal("B2 lineage: the manifest's b2_authority block is not the frozen requirement (S3 / true / null / aec84514…)")
    run = seams.b2 or _production_b2
    try:
        res = run(Path(root))
    except _b2_refusals() as exc:
        raise Refusal(f"B2 lineage: {exc}") from None
    if not isinstance(res, dict):
        raise Refusal(f"B2 lineage: the B2 verify returned {type(res).__name__}, not a result")
    for key, want in B2_REQUIRED.items():
        got = res.get(key, "<absent>")
        if got != want or type(got) is not type(want):
            shown = f"{str(got)[:16]}…" if key == "manifest_sha256" and isinstance(got, str) else repr(got)
            raise Refusal(f"B2 lineage: the B2 verify gives {key} = {shown}, B3 requires "
                          f"{(want[:16] + '…') if isinstance(want, str) and len(want) == 64 else repr(want)}")
    return "ok (B2 verify: S3 / true / null / aec84514…)"


def b2_authority_block() -> dict:
    return {"path": B2_MANIFEST_REL, "required": dict(B2_REQUIRED),
            "note": "the closed B2 manifest, re-verified by the production B2 verify at every B3 verify; it qualifies nothing about B3 "
                    "(preregistration §8a)"}


def _read_b1_manifest(root: Path) -> tuple[Path, dict]:
    p = Path(root) / B1_MANIFEST_REL
    if not p.is_file():
        raise Refusal(f"B1 lineage: {B1_MANIFEST_REL} is absent")
    m1 = _load_json(p, f"B1 lineage: {B1_MANIFEST_REL}")
    if not isinstance(m1, dict) or not isinstance(m1.get("carrier"), dict):
        raise Refusal(f"B1 lineage: {B1_MANIFEST_REL} carries no carrier record")
    return p, m1


def lineage_blocks(root: Path) -> dict:
    """The carrier lineage, the board and the carrier, from the B1 manifest as it is NOW. Whether the B1
    chain verifies is never stored — every verify re-runs it."""
    p, m1 = _read_b1_manifest(root)
    car = m1["carrier"]
    for k in ("bitstream", "bitstream_sha256", "variant"):
        if not isinstance(car.get(k), str) or not car[k]:
            raise Refusal(f"B1 lineage: the B1 manifest's carrier names no {k}")
    if car["variant"] != B3_VARIANT:
        raise Refusal(f"B1 lineage: the B1 carrier's variant {car['variant']!r} is not the contract word {B3_VARIANT!r}")
    b = m1.get("board")
    if not isinstance(b, dict) or not isinstance(b.get("boardid"), str) or not b["boardid"].strip():
        raise Refusal("B1 lineage: the B1 manifest names no boardid: this stage has no board authority")
    return {"carrier_lineage": {"b1_manifest": {"path": B1_MANIFEST_REL, "sha256": sha256_file(p)},
                                "bitstream": car["bitstream"], "bitstream_sha256": car["bitstream_sha256"], "variant": car["variant"],
                                "b1_qualification_record_sha256": canonical_sha256(car["qualification"]) if car.get("qualification") else None,
                                "note": "the B1 evidence certifies the carrier's history under the B1 manifest and is re-verified FRESH by every "
                                        "verify(); it qualifies nothing about this manifest — the B3 image needs its own B3Q session (S2)"},
            "board": {k: b[k] for k in ("boardid", "role", "part", "idcode") if k in b},
            "carrier": {"bitstream_sha256": car["bitstream_sha256"], "variant": B3_VARIANT}}


def _production_b1(b1_manifest: dict, root: Path):
    import b1_qualification as b1q  # noqa: E402
    return b1q.verify(b1_manifest, root=Path(root))


def check_b1_lineage(manifest: dict, root: Path, seams: Seams) -> str:
    import b1_qualification as b1q  # noqa: E402
    want = lineage_blocks(root)
    for key in ("carrier_lineage", "board", "carrier"):
        diff = b3g.deep_findings(want[key], manifest.get(key), key)
        if diff:
            raise Refusal("B1 lineage: the manifest's " + "; ".join(diff[:3]) + " — not the B1 manifest's now")
    _p, m1 = _read_b1_manifest(root)
    try:
        (seams.b1 or _production_b1)(m1, Path(root))
    except b1q.QualificationRefusal as exc:
        raise Refusal(f"B1 lineage: the B1 qualification chain does not verify now: {exc}") from None
    return f"ok (B1 chain re-verified; board {want['board']['boardid']})"


def check_board(manifest: dict) -> str:
    """The frozen board authority. A manifest without one cannot authorise anything: absence is a
    refusal, never permission to skip the comparison."""
    b = manifest.get("board")
    if not isinstance(b, dict):
        raise Refusal("the manifest pins no board: this stage has no board authority")
    got = b.get("boardid")
    if not isinstance(got, str) or not got.strip():
        raise Refusal(f"the manifest's boardid {got!r} is not a non-empty string")
    return got


# ------------------------------------------------------------------ 4: B3's own pins


def instrument_pins_block(root: Path) -> dict:
    p = Path(root) / PIN_TABLE_REL
    if not p.is_file():
        raise Refusal(f"instrument pins: {PIN_TABLE_REL} is absent (b3/host/b3_pins.py generates it once, after every pinned edit — a later unit)")
    return {"path": PIN_TABLE_REL, "sha256": sha256_file(p)}


def _production_pins(manifest: dict, root: Path) -> dict:
    """The production pin verifier. ONLY the absence of b3_pins itself is the named refusal; a dependency
    missing inside it, or anything else, propagates (an INTERNAL ERROR)."""
    try:
        b3_pins = importlib.import_module("b3_pins")
    except ModuleNotFoundError as exc:
        if exc.name == "b3_pins":
            raise Refusal("instrument pins: b3/host/b3_pins.py does not exist yet — the pin table's CONTENT cannot be verified, and "
                          "a table pinned by hash alone is not accepted") from None
        raise
    refusals = tuple(c for c in (getattr(b3_pins, n, None) for n in ("PinRefusal", "Refusal")) if isinstance(c, type) and issubclass(c, BaseException))
    try:
        return b3_pins.verify(manifest=manifest)
    except refusals as exc:
        raise Refusal(f"instrument pins: {exc}") from None


def check_instrument_pins(manifest: dict, root: Path, seams: Seams):
    _same("instrument_pins", manifest.get("instrument_pins"), instrument_pins_block(root))
    return (seams.pins or _production_pins)(manifest, Path(root))


def image_block(root: Path) -> dict:
    """The image from its build evidence AND the binary itself — opened, hashed and sized against the
    evidence. There is no S0 without an image."""
    evp = Path(root) / BUILD_EVIDENCE_REL
    if not evp.is_file():
        raise Refusal(f"image: the build evidence {BUILD_EVIDENCE_REL} is absent — there is no S0 without a built image")
    ev = _load_json(evp, f"image: {BUILD_EVIDENCE_REL}")
    im = ev.get("image") if isinstance(ev, dict) else None
    if not isinstance(im, dict):
        raise Refusal(f"image: {BUILD_EVIDENCE_REL} carries no image record")
    if im.get("path") != IMAGE_REL:
        raise Refusal(f"image: the build evidence names {im.get('path')!r}, the B3 image is {IMAGE_REL}")
    for k in ("sha256", "elf_sha256"):
        if not _hex64(im.get(k)):
            raise Refusal(f"image: the build evidence's {k} is not 64 lower-case hex")
    if not _int(im.get("bytes")) or im["bytes"] <= 0:
        raise Refusal(f"image: the build evidence's bytes {im.get('bytes')!r} is not a positive integer")
    ip = Path(root) / IMAGE_REL
    if not ip.is_file():
        raise Refusal(f"image: the image binary {IMAGE_REL} is absent — the declaration is not evidence that it exists")
    got, size = sha256_file(ip), ip.stat().st_size
    if got != im["sha256"]:
        raise Refusal(f"image: the image binary hashes to {got[:16]}…, the build evidence says {im['sha256'][:16]}…")
    if size != im["bytes"]:
        raise Refusal(f"image: the image binary is {size} bytes, the build evidence says {im['bytes']}")
    return {"path": IMAGE_REL, "sha256": im["sha256"], "elf_sha256": im["elf_sha256"], "bytes": im["bytes"],
            "build_evidence": {"path": BUILD_EVIDENCE_REL, "sha256": sha256_file(evp)},
            "note": f"pinned from its build evidence ({BUILD_EVIDENCE_REL}); every verify opens the binary and compares its digest and "
                    f"size with this record and with the evidence; board_ready is the owner's mark at the freeze"}


def check_image(manifest: dict, root: Path) -> str:
    im = manifest.get("image")
    if not isinstance(im, dict) or not isinstance(im.get("board_ready"), bool):
        raise Refusal("image: the manifest's image record carries no boolean board_ready")
    want = image_block(root)
    _same("image", {k: v for k, v in im.items() if k != "board_ready"}, want)
    return f"ok (binary hashed: {want['sha256'][:12]}…, {want['bytes']} bytes)"


def check_prereg(manifest: dict, root: Path) -> str:
    pr = manifest.get("prereg")
    if not isinstance(pr, dict) or set(pr) != {"path", "sha256", "frozen"} or pr.get("path") != PREREG_REL or not isinstance(pr.get("frozen"), bool):
        raise Refusal(f"prereg: the manifest's prereg record is not {{path: {PREREG_REL}, sha256, frozen}}")
    p = Path(root) / PREREG_REL
    if not p.is_file():
        raise Refusal(f"prereg: {PREREG_REL} is absent")
    if not pr["frozen"]:
        if pr["sha256"] is not None:
            raise Refusal("prereg: a preregistration digest on an unfrozen manifest")
        return "present (not frozen)"
    if not _hex64(pr["sha256"]) or sha256_file(p) != pr["sha256"]:
        raise Refusal("prereg: the frozen preregistration file changed")
    return "ok (frozen bytes)"


def gate_path(root: Path) -> Path:
    p = Path(root) / GATE_REL
    if not p.is_file():
        raise Refusal(f"experiment: the gate report {GATE_REL} is absent")
    return p


def experiment_blocks(root: Path) -> dict:
    """The experiment, the session seeds, the map and the instrument identity, REBUILT from the gate (read
    only through its production validator) and the plan tool — what the committed plan was built from."""
    gate = gate_path(root)
    try:
        g = pl.gate_inputs(gate)
        master, seeds, _sources, _excl = pl.session_seeds(g["pairs"], gate)
    except b3g.Refusal as exc:
        raise Refusal(f"experiment: the gate: {exc}") from None
    self_map = bmaps.load_self_map()
    return {"instrument": {"psoracle_commit": pl.INSTRUMENT_COMMIT},
            "map": {"path": str(bmaps.SELF_MAP.relative_to(REPO_ROOT)), "canonical_json_sha256": bmaps.sha256_of(self_map),
                    "file_sha256": sha256_file(bmaps.SELF_MAP), "cartographer": self_map["cartographer"],
                    "note": "arm F's map, two digests (canonical JSON; the file bytes); arm O starts empty and has no map pin"},
            "universe": {"addresses": 292, "sha256": self_map["binding"]["universe_sha256"]},
            "experiment": {"fitness": g["fitness"], "budget_per_arm": g["budget_per_arm"], "pairs": g["pairs"],
                           "engine": {"version": bs.ENGINE_VERSION, "mu": bs.MU, "lambda": bs.LAMBDA, "kmax": bs.KMAX},
                           "carto_version": carto_mod.CARTO_VERSION, "b1_map_cost": oa.B1_MAP_COST,
                           "arm_order": ["".join(pl.arm_order(r)) for r in range(g["pairs"])],
                           "calibration_margin": pl.CALIBRATION_MARGIN, "session_span_max_s": pl.SESSION_SPAN_MAX_S,
                           "gate": {"path": GATE_REL, "sha256": sha256_file(gate), "rules_version": g["rules_version"],
                                    "head_at_run": g["head_at_run"], "architecture_sha256": g["architecture_sha256"]}},
            "audit": {"policy": pl.AUDIT_POLICY, "note": "every record's readout served and host-verified (B2's, the owner's decision of 2026-09-10)"},
            "seeds": {"label": pl.SESSION_LABEL, "master_seed": master, "pairs": [list(x) for x in seeds],
                      "rule": "first 4 bytes of sha256(label|instrument commit); the fixed excluded seeds and every archived set explicitly excluded"}}


def prediction_block(root: Path, blocks: dict) -> dict:
    """The preregistered prediction, by path and digest — and REBUILT in full (every O run's every ledger
    entry) from the manifest's own seeds, with the preflight's stop rule still passing."""
    p = Path(root) / PREDICTION_REL
    if not p.is_file():
        raise Refusal(f"prediction: {PREDICTION_REL} is absent")
    doc = _load_json(p, f"prediction: {PREDICTION_REL}")
    ex = blocks["experiment"]
    want = pl.build_prediction(ex["fitness"], ex["budget_per_arm"], [tuple(x) for x in blocks["seeds"]["pairs"]], blocks["map"]["canonical_json_sha256"])
    diff = pl.prediction_findings(want, doc)
    if diff:
        raise Refusal(f"prediction: {PREDICTION_REL} is not the canonical prediction: " + "; ".join(diff[:3]))
    stop = pl.stop_rule_findings(doc)
    if stop:
        raise Refusal("prediction: the preflight's stop rule no longer passes: " + "; ".join(stop))
    return {"path": PREDICTION_REL, "sha256": sha256_file(p), "fitness_sequence_sha256": doc["fitness_sequence_sha256"],
            "note": "the preregistered prediction; the S3 plan's sidecar must be these bytes"}


def committed_plan_findings(root: Path, blocks: dict) -> list[str]:
    """At S0 only: the committed plan is the tool's own rate-less document (the committed-plan stage
    rule), and it pins the committed prediction."""
    p = Path(root) / PLAN_REL
    if not p.is_file():
        return [f"{PLAN_REL} is absent"]
    plan = _load_json(p, PLAN_REL)
    if not isinstance(plan, dict):
        return [f"{PLAN_REL} is not an object"]
    try:
        want = pl.build_plan(None, gate_path(root))
    except b3g.Refusal as exc:
        return [f"the canonical plan cannot be built: {exc}"]
    f = [f"plan {d}" for d in b3g.deep_findings({k: v for k, v in want.items() if k not in PLAN_NON_OPERATIONAL},
                                                 {k: v for k, v in plan.items() if k not in PLAN_NON_OPERATIONAL})]
    pred = Path(root) / PREDICTION_REL
    if pred.is_file() and plan.get("prediction_sha256") != sha256_file(pred):
        f.append(f"{PLAN_REL}'s prediction digest is not {PREDICTION_REL}'s hash")
    return f


def qualification_plan_block(root: Path, blocks: dict) -> dict:
    """B3Q's frozen experiment, pinned by path and digest AND re-derived here, so the pinned bytes cannot
    drift from the rule that produced them. Recorded at S0, unchanged ever after."""
    pp, qp = Path(root) / QUAL_PLAN_REL, Path(root) / QUAL_PREDICTION_REL
    for rel, path in ((QUAL_PLAN_REL, pp), (QUAL_PREDICTION_REL, qp)):
        if not path.is_file():
            raise Refusal(f"qualification plan: {rel} is absent (generate it with `python3 b3/host/b3_plan.py --qualification`)")
    plan, prediction = _load_json(pp, f"qualification plan: {QUAL_PLAN_REL}"), _load_json(qp, f"qualification plan: {QUAL_PREDICTION_REL}")
    gate = gate_path(root)
    fid, map_sha = blocks["experiment"]["fitness"], blocks["map"]["canonical_json_sha256"]
    pairs = [tuple(x) for x in blocks["seeds"]["pairs"]]
    try:
        want_pred = pl.build_qualification_prediction(fid, map_sha, pairs, gate)
        want_plan = {**pl.build_qualification_plan(fid, map_sha, pairs, gate), "prediction_sha256": pl.sha256_json(want_pred)}
    except b3g.Refusal as exc:
        raise Refusal(f"qualification plan: the gate: {exc}") from None
    diff = b3g.deep_findings(want_plan, plan)
    if diff:
        raise Refusal(f"qualification plan: {QUAL_PLAN_REL} is not the canonical B3Q plan: " + "; ".join(diff[:3]))
    diff = pl.prediction_findings(want_pred, prediction)
    if diff:
        raise Refusal(f"qualification plan: {QUAL_PREDICTION_REL} is not the canonical B3Q prediction: " + "; ".join(diff[:3]))
    return {"path": QUAL_PLAN_REL, "sha256": sha256_file(pp), "prediction_path": QUAL_PREDICTION_REL, "prediction_sha256": sha256_file(qp),
            "master_seed": plan["seed_derivation"]["master_seed"], "pairs": plan["seed_derivation"]["pairs"],
            "budget_per_arm": plan["budget_per_arm"], "records": plan["records"]["total"], "ledger_entries": plan["records"]["ledger_entries"],
            "fitness_sequence_sha256": prediction["fitness_sequence_sha256"], "planning_bound": plan["planning_bound"]}


def expected_qualification_block(qp: dict) -> dict:
    """123 fitness values, 40 ledger entries, 2 baselines and the sequence digest — from the PINNED B3Q
    experiment (preregistration §6a), never from the evidence."""
    return {"fitness_values": qp["records"] - 2, "ledger_entries": qp["ledger_entries"], "baselines": 2,
            "fitness_sequence_sha256": qp["fitness_sequence_sha256"]}


RULINGS_BINDING = {"B3Q": ["session=B3Q", "image_sha256", "prereg_sha256", "b3_manifest_sha256 (manifest_at_run: the S1 manifest)",
                           "master_seed (B3Q's)", "pair_first=0", "pair_count=1", "transport_disposition", "resend_budget"],
                   "B3": ["session=B3", "master_seed", "pair_first", "pair_count", "image_sha256", "prereg_sha256",
                          "b3_manifest_sha256 (the S3 manifest)", "transport_disposition", "resend_budget"]}


# ------------------------------------------------------------------ the stage, from the structure


def stage_of(manifest: dict) -> str:
    """The stage a manifest's STRUCTURE declares — every illegal pairing of stage fields, a wrong status
    and a wrong history are named refusals. Whether the declared content is TRUE is verify's business."""
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise Refusal("not a b3_manifest")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise Refusal(f"b3_manifest schema_version {manifest.get('schema_version')!r} is not {SCHEMA_VERSION}")
    if set(manifest) != set(MANIFEST_KEYS):
        raise Refusal(f"the manifest's key set is not the schema's (missing {sorted(set(MANIFEST_KEYS) - set(manifest))}, "
                      f"unexpected {sorted(set(manifest) - set(MANIFEST_KEYS))})")
    pr, im = manifest["prereg"], manifest["image"]
    if not isinstance(pr, dict) or not isinstance(pr.get("frozen"), bool):
        raise Refusal("prereg: the manifest's prereg record carries no boolean frozen")
    if not isinstance(im, dict) or not isinstance(im.get("board_ready"), bool):
        raise Refusal("image: the manifest's image record carries no boolean board_ready")
    if not isinstance(manifest["qualified"], bool):
        raise Refusal("the manifest's qualified flag is not a boolean")
    q, cal, plan = manifest["qualification"], manifest["calibration"], manifest["plan"]
    if not pr["frozen"]:
        if pr.get("sha256") is not None or im["board_ready"]:
            raise Refusal("S0: a preregistration digest or a board_ready image on an unfrozen manifest")
        if q is not None or manifest["qualified"] or cal is not None:
            raise Refusal("S0: a qualification, a qualified flag or a calibration on an unfrozen manifest")
        if plan is not None:
            raise Refusal("S0: a plan on an unfrozen manifest")
        stage = "S0"
    else:
        if not _hex64(pr.get("sha256")) or not im["board_ready"]:
            raise Refusal("S1: frozen without a preregistration digest or without board_ready")
        if q is None:
            if manifest["qualified"] or cal is not None:
                raise Refusal("S1: qualified / calibration without a qualification record")
            if plan is not None:
                raise Refusal("S1: a plan on a manifest that is not qualified")
            stage = "S1"
        else:
            if not isinstance(q, dict) or not manifest["qualified"] or not isinstance(cal, dict):
                raise Refusal("S2: a qualification record without the qualified flag and its calibration")
            if plan is not None and not isinstance(plan, dict):
                raise Refusal("S3: the plan pin is not an object")
            stage = "S2" if plan is None else "S3"
    if manifest["status"] != STATUS[stage]:
        raise Refusal(f"{stage}: the manifest's status is {str(manifest['status'])[:40]!r}…, this stage's is {STATUS[stage][:40]!r}…")
    hist = manifest["history"]
    if not isinstance(hist, list) or any(not isinstance(h, dict) for h in hist) or [h.get("transition") for h in hist] != HISTORY[stage]:
        raise Refusal(f"{stage}: the manifest's history is not exactly {HISTORY[stage]}")
    return stage


def check_history(manifest: dict, stage: str) -> None:
    hist = manifest["history"]
    if stage >= "S1" and hist[0].get("prereg_sha256") != manifest["prereg"]["sha256"]:
        raise Refusal("history: the S1 entry's preregistration digest is not the manifest's")
    if stage >= "S2":
        q = manifest["qualification"]
        if hist[1].get("manifest_at_run_sha256") != (q.get("binding") or {}).get("b3_manifest_sha256") \
                or hist[1].get("rate_per_hour") != q.get("measured_rate_per_hour"):
            raise Refusal("history: the S2 entry is not the qualification record's manifest_at_run digest and rate")
    if stage >= "S3" and hist[2].get("plan_sha256") != manifest["plan"].get("sha256"):
        raise Refusal("history: the S3 entry's plan digest is not the pinned plan's")


def check_transition(before: dict, after: dict) -> tuple[str, str]:
    """A before / after pair is a legal lifecycle step: adjacent stages, in order, and NOTHING changed
    outside that step's licensed paths."""
    pair = (stage_of(before), stage_of(after))
    if pair not in TRANSITIONS:
        raise Refusal(f"transition: {pair[0]} -> {pair[1]} is not a lifecycle step (only S0 -> S1, S1 -> S2, S2 -> S3)")
    allowed = TRANSITIONS[pair]
    diff = b3g.deep_findings(_strip(before, allowed), _strip(after, allowed))
    if diff:
        raise Refusal(f"transition: {pair[0]} -> {pair[1]} may change only {['.'.join(p) for p in allowed]}; also changed: " + "; ".join(diff[:4]))
    return pair


# ------------------------------------------------------------------ S2: the record, from the evidence


def qualification_evidence_files() -> tuple:
    import b1_qualification as b1q  # noqa: E402
    return tuple(b1q.EVIDENCE_FILES) + (RUNNER_SESSION,)


def read_adjudication(ev: Path) -> dict:
    """adjudication.json, validated: the B3Q session verdict with a finite positive measured
    all-self-reporting rate, the audit policy and the qualification block."""
    p = Path(ev) / "adjudication.json"
    if not p.is_file():
        raise Refusal("adjudication.json is absent")
    adj = _load_json(p, "adjudication.json")
    if not isinstance(adj, dict):
        raise Refusal("adjudication.json is not an object")
    for k in ("outcome", "session", "scope", "measured_rate_per_hour", "audit_policy", "qualification"):
        if k not in adj:
            raise Refusal(f"adjudication.json lacks {k}")
    if adj["session"] != QUAL_SESSION or adj["scope"] != "session":
        raise Refusal(f"adjudication.json is session {adj['session']!r} at scope {adj['scope']!r}, not {QUAL_SESSION} at scope 'session'")
    if adj["outcome"] != "PASS":              # before the block's shape: a session that did not pass publishes no block
        raise Refusal(f"the stored B3Q adjudication is {str(adj['outcome'])[:200]!r}, not PASS")
    if not _finite_positive(adj["measured_rate_per_hour"]):
        raise Refusal("adjudication.json: the measured rate is not a finite positive number")
    block = adj["qualification"]
    if not isinstance(block, dict) or set(block) != set(QUAL_BLOCK_KEYS):
        raise Refusal(f"adjudication.json: the qualification block does not carry exactly {list(QUAL_BLOCK_KEYS)}")
    return adj


def reconstruct_qualification_record(evidence_dir: Path, root: Path = REPO_ROOT) -> dict:
    """The B3Q record, RECONSTRUCTED from the files, every time: the exact file set by hash, the export
    seal, the two ruling archives readable, the binding read from manifest_at_run, the outcome / rate /
    policy / qualification block from the adjudication. Never a caller's summary."""
    import b1_adjudicate as b1adj  # noqa: E402
    import b1_qualification as b1q  # noqa: E402
    ev = Path(evidence_dir)
    files = {}
    for n in qualification_evidence_files():
        if not (ev / n).is_file():
            raise Refusal(f"evidence file {n} is absent")
        files[n] = sha256_file(ev / n)
    try:
        b1adj.check_exports(ev)
    except b1adj.Refusal as exc:
        raise Refusal(f"evidence seal: {exc}") from None
    for name in b1q.RULING_FILES.values():
        try:
            b1q.read_archived_ruling(ev / name)
        except b1q.QualificationRefusal as exc:
            raise Refusal(f"the archived authorisation {name} is not a readable ruling archive: {exc}") from None
    m_run = _load_json(ev / MANIFEST_AT_RUN, MANIFEST_AT_RUN)
    try:
        if stage_of(m_run) != "S1":
            raise Refusal(f"it is at {stage_of(m_run)}")
    except Refusal as exc:
        raise Refusal(f"{MANIFEST_AT_RUN} is not an S1 b3_manifest: {exc}") from None
    if files[MANIFEST_AT_RUN] != manifest_sha256(m_run):
        raise Refusal(f"{MANIFEST_AT_RUN} is not the manifest file's canonical bytes: its digest is not the one a ruling binds to")
    adj = read_adjudication(ev)
    return {"schema": QUAL_SCHEMA, "schema_version": QUAL_SCHEMA_VERSION, "session": QUAL_SESSION, "evidence_dir": _relative(ev, root),
            "files": files, "outcome": adj["outcome"], "measured_rate_per_hour": adj["measured_rate_per_hour"],
            "audit_policy": adj["audit_policy"], "qualification_block": adj["qualification"],
            "binding": {"session": QUAL_SESSION, "image_sha256": m_run["image"]["sha256"], "prereg_sha256": m_run["prereg"]["sha256"],
                        "carrier_sha256": m_run["carrier"]["bitstream_sha256"], "carrier_variant": m_run["carrier"]["variant"],
                        "map_canonical_json_sha256": m_run["map"]["canonical_json_sha256"],
                        "b3_manifest_sha256": files[MANIFEST_AT_RUN],
                        "qualification_plan_sha256": m_run["qualification_plan"]["sha256"],
                        "qualification_prediction_sha256": m_run["qualification_plan"]["prediction_sha256"]}}


def summary_findings(evidence_dir: Path) -> list[str]:
    """The post-finalisation boundary (B2's): summary.json and runner_session.json are written AFTER the
    adjudication callback, so they are cross-checked here against the evidence they close."""
    import b1_qualification as b1q  # noqa: E402
    ev = Path(evidence_dir)
    f: list[str] = []
    try:
        adj = read_adjudication(ev)
    except Refusal as exc:
        return [f"the final records cannot be cross-checked: {exc}"]
    try:
        summary = json.loads((ev / "summary.json").read_text())
    except (OSError, ValueError) as exc:
        return [f"summary.json is not readable JSON: {exc}"]
    if not isinstance(summary, dict):
        return ["summary.json is not a JSON object"]
    if summary.get("outcome") != adj["outcome"]:
        f.append(f"summary.json's outcome {summary.get('outcome')!r} is not the adjudication's {adj['outcome']!r}")
    try:
        log = json.loads((ev / "run_log.json").read_text())
    except (OSError, ValueError) as exc:
        f.append(f"summary.json cannot be bound to the run log: {exc}")
        log = {}
    ident = log.get("app_identity") if isinstance(log, dict) else None
    token = ident.get("token") if isinstance(ident, dict) else None
    if token is not None and summary.get("token") != token:
        f.append("summary.json's token is not the session's")
    try:
        _raw_whole, whole = b1q.read_archived_ruling(ev / b1q.RULING_FILES["whole_of_run"])
        raw_pk, _pk = b1q.read_archived_ruling(ev / b1q.RULING_FILES["provisioning"])
    except b1q.QualificationRefusal as exc:
        return f + [f"summary.json cannot be bound to the archived rulings: {exc}"]
    if summary.get("ruling") != whole:
        f.append("summary.json's recorded ruling is not the archived whole-of-run ruling")
    want_pk = hashlib.sha256(raw_pk).hexdigest()
    if summary.get("provisioning_ruling_sha256") != want_pk:
        f.append(f"summary.json's provisioning_ruling_sha256 is not the archived provisioning ruling's bytes ({want_pk[:16]}…)")
    try:
        rs = json.loads((ev / RUNNER_SESSION).read_text())
    except (OSError, ValueError) as exc:
        return f + [f"{RUNNER_SESSION} is not readable JSON: {exc}"]
    # The finalisation record's EXACT schema, and every authority field bound — type-strictly — to the B3Q
    # session: the slice, the master seed and the record count from the experiment manifest_at_run pins, the
    # profile / stage, the point reached, the tool, the outcome / cause / rate from the adjudication, the
    # transport disposition and resend budget from the archived whole-of-run ruling. (The frame and CRC budgets
    # need the instrument's schedule: the re-adjudicator binds those, with all of these again, to the session
    # plan it rebuilds.) The owner's P2 on 8ba72c4.
    import b3_runner  # noqa: E402
    try:
        qp = json.loads((ev / MANIFEST_AT_RUN).read_text())["qualification_plan"]
        want = {"tool": b3_runner.TOOL_VERSION, "session": QUAL_SESSION, "profile_stage": "S1", "reached": "session",
                "pair_first": 0, "pair_count": 1, "master_seed": qp["master_seed"], "expected_records": qp["records"],
                "outcome": adj["outcome"], "cause": "PASS", "measured_rate_per_hour": adj["measured_rate_per_hour"],
                "transport": {"transport_disposition": whole.get("transport_disposition"), "resend_budget": whole.get("resend_budget")}}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return f + [f"{RUNNER_SESSION} cannot be bound to {MANIFEST_AT_RUN}'s pinned experiment: {type(exc).__name__}: {exc}"]
    return f + b3_runner.session_record_findings(rs, want)


def calibration_from(record: dict, manifest: dict) -> dict:
    """The calibration, from the reconstructed record: the measured rate, the frozen 0.85 margin, the rate
    the split uses, the verified audit policy — and FEASIBLE under the split rule."""
    rate = record["measured_rate_per_hour"]
    ex = manifest["experiment"]
    try:
        split = pl.session_split(ex["pairs"], ex["budget_per_arm"], rate)
    except pl.RateInvalid as exc:
        raise Refusal(f"calibration: {exc}") from None
    if split["status"] != "DETERMINED":
        raise Refusal(f"calibration: the measured rate {rate} /h is INFEASIBLE under the split rule at the {pl.CALIBRATION_MARGIN} margin: "
                      f"no whole pair fits the {pl.SESSION_SPAN_MAX_S} s expected span")
    return {"rate_per_hour": rate, "margin": pl.CALIBRATION_MARGIN, "rate_for_split": rate * pl.CALIBRATION_MARGIN,
            "audit_policy": record["audit_policy"], "sessions": len(split["sessions"]), "pairs_per_session_max": split["pairs_per_session_max"],
            "source": "reconstructed from the B3Q evidence and its re-adjudication (the measured all-self-reporting rate; the audit policy "
                      "VERIFIED by the instrument layer) — the only source a B3 plan may be sized from; the margin is frozen, not measured"}


def _production_readjudicator(manifest: dict, root: Path):
    import b3_runner  # noqa: E402
    return b3_runner.readjudicator(manifest, root=Path(root))


def check_qualification(manifest: dict, evidence_dir, readjudicate, root: Path) -> str:
    q = manifest["qualification"]
    if set(q) != set(QUAL_RECORD_KEYS):
        raise Refusal(f"S2: the qualification record does not carry exactly {list(QUAL_RECORD_KEYS)}")
    if q["schema"] != QUAL_SCHEMA or q["schema_version"] != QUAL_SCHEMA_VERSION or q["session"] != QUAL_SESSION:
        raise Refusal("S2: the record is not a B3Q image qualification of the current schema")
    if not isinstance(q["files"], dict) or sorted(q["files"]) != sorted(qualification_evidence_files()):
        raise Refusal(f"S2: the record's file set is not exactly {sorted(qualification_evidence_files())}")
    if not isinstance(q["binding"], dict) or sorted(q["binding"]) != sorted(QUAL_BINDING_KEYS):
        raise Refusal("S2: the record's binding does not carry exactly the required keys")
    if not isinstance(q["evidence_dir"], str) or not q["evidence_dir"]:
        raise Refusal("S2: the record names no evidence directory")
    ev = Path(evidence_dir) if evidence_dir else _resolve(q["evidence_dir"], root)
    if not ev.is_dir():
        raise Refusal(f"S2: the qualification evidence directory {q['evidence_dir']} is absent")
    rebuilt = reconstruct_qualification_record(ev, root)
    for k in QUAL_RECORD_KEYS:
        if k != "evidence_dir" and (rebuilt[k] != q[k] or type(rebuilt[k]) is not type(q[k])):
            raise Refusal(f"S2: the record's {k} is not what the evidence gives")
    sf = summary_findings(ev)
    if sf:
        raise Refusal("S2: the session's final records do not close this evidence: " + "; ".join(sf[:8]))
    b = rebuilt["binding"]
    qp = manifest["qualification_plan"]
    if (b["image_sha256"], b["prereg_sha256"], b["carrier_sha256"], b["carrier_variant"], b["map_canonical_json_sha256"],
            b["qualification_plan_sha256"], b["qualification_prediction_sha256"]) != \
            (manifest["image"]["sha256"], manifest["prereg"]["sha256"], manifest["carrier"]["bitstream_sha256"], manifest["carrier"]["variant"],
             manifest["map"]["canonical_json_sha256"], qp["sha256"], qp["prediction_sha256"]):
        raise Refusal("S2: the record's binding (image / prereg / carrier / map / B3Q experiment) is not this manifest's")
    m_run = json.loads((ev / MANIFEST_AT_RUN).read_text())
    diff = b3g.deep_findings(_strip(m_run, SINCE_RUN), _strip(manifest, SINCE_RUN))
    if diff:
        raise Refusal("S2: the current manifest differs from manifest_at_run in more than the qualification, calibration, plan, status and "
                      "history: the image was qualified for another manifest (" + "; ".join(diff[:3]) + ")")
    if rebuilt["audit_policy"] != manifest["audit"]["policy"]:
        raise Refusal(f"S2: the B3Q session's audit policy {rebuilt['audit_policy']!r} is not the frozen policy {manifest['audit']['policy']!r}")
    want_block = expected_qualification_block(qp)
    if rebuilt["qualification_block"] != want_block:
        raise Refusal("S2: the evidence's qualification block is not the pinned B3Q experiment's (123 fitness values, 40 ledger entries, "
                      "2 baselines, the sequence digest): " + "; ".join(b3g.deep_findings(want_block, rebuilt["qualification_block"])[:3]))
    again = readjudicate or _production_readjudicator(manifest, root)
    res = again(ev, m_run)
    if not isinstance(res, dict):
        raise Refusal(f"S2: the re-adjudication returned {type(res).__name__}, not a verdict")
    if res.get("outcome") != "PASS":
        raise Refusal(f"S2: the pinned B3Q evidence re-adjudicates to {str(res.get('outcome'))[:200]!r}, not PASS")
    for k, mine in (("measured_rate_per_hour", "measured_rate_per_hour"), ("audit_policy", "audit_policy"), ("qualification", "qualification_block")):
        if res.get(k) != rebuilt[mine] or type(res.get(k)) is not type(rebuilt[mine]):
            raise Refusal(f"S2: the re-adjudication's {k} ({str(res.get(k))[:80]}) disagrees with the evidence's adjudication ({str(rebuilt[mine])[:80]})")
    want_cal = calibration_from(rebuilt, manifest)
    cal = manifest["calibration"]
    diff = b3g.deep_findings(want_cal, cal, "calibration")
    if diff:
        raise Refusal("S2: the calibration is not the one the evidence gives under the frozen margin and split rule: " + "; ".join(diff[:3]))
    return f"ok (record rebuilt, re-adjudicated PASS at {rebuilt['measured_rate_per_hour']} /h; calibration recomputed)"


# ------------------------------------------------------------------ S3: one validator for pinning and verification


def plan_findings(manifest: dict, plan_path, root: Path = REPO_ROOT) -> list[str]:
    """The WHOLE plan and the WHOLE prediction — every O run's every ledger entry — rebuilt from the
    frozen inputs and the calibration's rate_per_hour and compared path by path (`b3_gate.deep_findings`);
    a drifted ledger entry is named as `prediction pairs[r].runs.O.ledger[n]…`. Only PLAN_NON_OPERATIONAL
    may differ; `prediction_sha256` is instead tied to the sidecar's bytes."""
    p = _resolve(str(plan_path), root)
    if not p.is_file():
        return [f"plan file {plan_path} is absent"]
    try:
        plan = json.loads(p.read_text())
    except ValueError as exc:
        return [f"plan file {plan_path} is not JSON: {exc}"]
    if not isinstance(plan, dict):
        return ["the plan is not an object"]
    cal = manifest.get("calibration")
    if not isinstance(cal, dict) or not _finite_positive(cal.get("rate_per_hour")):
        return ["no calibration with a finite positive rate_per_hour in the manifest: no plan can be derived"]
    try:
        want_plan = pl.build_plan(cal["rate_per_hour"], gate_path(root))
    except (Refusal, b3g.Refusal, pl.RateInvalid) as exc:
        return [f"the canonical plan cannot be built: {exc}"]
    f: list[str] = []
    split = want_plan["session_split"]
    if split["status"] != "DETERMINED":
        f.append(f"the calibration's split is {split['status']}, not DETERMINED")
    elif split["rate_for_split"] != cal.get("rate_for_split"):
        f.append("the calibration's rate_for_split is not the split rule's")
    ex = manifest["experiment"]
    if (want_plan["fitness"], want_plan["budget_per_arm"], want_plan["pairs"], want_plan["engine"], want_plan["arm_order"]["per_pair"]) != \
            (ex["fitness"], ex["budget_per_arm"], ex["pairs"], ex["engine"], ex["arm_order"]):
        f.append("the manifest's experiment is not what the pinned gate selects")
    if want_plan["map"]["sha256"] != manifest["map"]["canonical_json_sha256"]:
        f.append("the manifest's map digest is not the map the plan is built from")
    if want_plan["audit_policy"] != manifest["audit"]["policy"]:
        f.append("the manifest's audit policy is not the plan's")
    if want_plan["seed_derivation"]["master_seed"] != manifest["seeds"]["master_seed"]:
        f.append("the manifest's master seed is not the frozen rule's")
    f += [f"plan {d}" for d in b3g.deep_findings({k: v for k, v in want_plan.items() if k not in PLAN_NON_OPERATIONAL},
                                                  {k: v for k, v in plan.items() if k not in PLAN_NON_OPERATIONAL})]
    pred_path = p.parent / "prediction.json"
    if not pred_path.is_file():
        return f + ["prediction.json is absent beside the plan"]
    if plan.get("prediction_sha256") != sha256_file(pred_path):
        f.append("the plan's prediction digest is not the sidecar's hash")
    if sha256_file(pred_path) != (manifest.get("prediction") or {}).get("sha256"):
        f.append("the plan's prediction sidecar is not the preregistered prediction the manifest pinned at S0")
    try:
        pred = json.loads(pred_path.read_text())
    except ValueError as exc:
        return f + [f"the prediction sidecar is not JSON: {exc}"]
    want_pred = pl.build_prediction(ex["fitness"], ex["budget_per_arm"], [tuple(x) for x in manifest["seeds"]["pairs"]],
                                    manifest["map"]["canonical_json_sha256"])
    f += [f"prediction {d}" for d in pl.prediction_findings(want_pred, pred)]
    return f


def check_plan(manifest: dict, root: Path) -> str:
    plp = manifest["plan"]
    if set(plp) != {"path", "sha256", "prediction_path", "prediction_sha256", "sessions", "total_records"}:
        raise Refusal("S3: the plan pin does not carry exactly path, sha256, prediction_path, prediction_sha256, sessions, total_records")
    p = _resolve(plp["path"], root)
    if not p.is_file() or sha256_file(p) != plp["sha256"]:
        raise Refusal("S3: the pinned plan file is absent or changed")
    pred = _resolve(plp["prediction_path"], root)
    if not pred.is_file() or sha256_file(pred) != plp["prediction_sha256"]:
        raise Refusal("S3: the pinned prediction file is absent or changed")
    sidecar = p.parent / "prediction.json"
    if not sidecar.is_file() or sha256_file(sidecar) != plp["prediction_sha256"]:
        raise Refusal("S3: the manifest's prediction reference and the plan's sidecar are different bytes")
    findings = plan_findings(manifest, p, root)
    if findings:
        raise Refusal("S3: " + "; ".join(findings[:6]))
    split = json.loads(p.read_text())["session_split"]
    if plp["sessions"] != len(split["sessions"]) or plp["total_records"] != split["total_records"] \
            or not _int(plp["sessions"]) or not _int(plp["total_records"]):
        raise Refusal("S3: the manifest's plan summary (sessions / total_records) is not the plan's")
    if len(split["sessions"]) != manifest["calibration"]["sessions"]:
        raise Refusal("S3: the plan's session count is not the calibration's")
    return f"ok ({plp['sessions']} sessions, {plp['total_records']} records; plan and prediction rebuilt entry by entry)"


# ------------------------------------------------------------------ verify


def verify(manifest: dict, evidence_dir=None, readjudicate=None, root: Path = REPO_ROOT, seams: Seams | None = None) -> dict:
    """{stage, qualified, refusal, checks, manifest_sha256}; raises Refusal on anything the lifecycle does
    not license. Recomputes everything from live bytes; trusts no stored flag. `readjudicate` (or
    `seams.readjudicate`) None = the production re-adjudicator."""
    seams = seams or Seams()
    root = Path(root)
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise Refusal("not a b3_manifest")
    checks: dict = {}
    checks["frozen_inputs"] = check_frozen_inputs(manifest.get("frozen_inputs"), root)            # 1
    checks["b2_authority"] = check_b2_authority(manifest.get("b2_authority"), root, seams)        # 2
    checks["b1_lineage"] = check_b1_lineage(manifest, root, seams)                                # 3
    stage = stage_of(manifest)                                                                    # 4
    checks["board"] = check_board(manifest)
    checks["instrument_pins"] = check_instrument_pins(manifest, root, seams)
    checks["image"] = check_image(manifest, root)
    checks["prereg"] = check_prereg(manifest, root)
    blocks = experiment_blocks(root)
    for key in ("instrument", "map", "universe", "experiment", "audit", "seeds"):
        _same(key, manifest[key], blocks[key])
    _same("qualification_plan", manifest["qualification_plan"], qualification_plan_block(root, blocks))
    checks["qualification_plan"] = f"ok ({manifest['qualification_plan']['records']} records at budget {manifest['qualification_plan']['budget_per_arm']})"
    _same("prediction", manifest["prediction"], prediction_block(root, blocks))
    checks["prediction"] = "ok (rebuilt in full; the stop rule passes)"
    if manifest["lifecycle"] != pl.LIFECYCLE or manifest["rulings_binding"] != RULINGS_BINDING:
        raise Refusal("the manifest's lifecycle or rulings_binding block is not this lifecycle's")
    qualified = False
    if stage >= "S2":
        checks["qualification"] = check_qualification(manifest, evidence_dir, readjudicate or seams.readjudicate, root)
        qualified = True
    if stage == "S3":
        checks["plan"] = check_plan(manifest, root)
    check_history(manifest, stage)
    checks["stage"] = stage
    return {"stage": stage, "qualified": qualified, "refusal": None, "checks": checks, "manifest_sha256": manifest_sha256(manifest)}


# ------------------------------------------------------------------ the transitions


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _require(manifest: dict, stage: str, what: str, **kw) -> None:
    got = verify(manifest, **kw)["stage"]
    if got != stage:
        raise Refusal(f"{what}: the manifest is at {got}, this transition starts from {stage}")


def _checked(before: dict, candidate: dict, stage: str, **kw) -> dict:
    check_transition(before, candidate)
    got = verify(candidate, **kw)["stage"]
    if got != stage:
        raise Refusal(f"the transition produced a manifest at {got}, not {stage}")
    return candidate


def init(root: Path = REPO_ROOT, seams: Seams | None = None) -> dict:
    """S0 — CONSTRUCTED here, never executed by this unit. Every prerequisite is required and verified: the
    fixed prefix first, then the pin table, the image, B3Q's documents, the committed plan and prediction;
    the candidate then passes the same verify as any manifest. Absent anything: a named refusal, nothing
    written."""
    seams = seams or Seams()
    root = Path(root)
    check_frozen_inputs(dict(FROZEN_INPUTS), root)
    check_b2_authority(b2_authority_block(), root, seams)
    lineage = lineage_blocks(root)
    pins = instrument_pins_block(root)
    image = {**image_block(root), "board_ready": False}
    if not (root / PREREG_REL).is_file():
        raise Refusal(f"prereg: {PREREG_REL} is absent")
    blocks = experiment_blocks(root)
    qplan = qualification_plan_block(root, blocks)
    prediction = prediction_block(root, blocks)
    stale = committed_plan_findings(root, blocks)
    if stale:
        raise Refusal("init: the committed plan is not the canonical rate-less plan: " + "; ".join(stale[:4]))
    m = {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "lifecycle": pl.LIFECYCLE, "status": STATUS["S0"],
         "instrument": blocks["instrument"], "frozen_inputs": dict(FROZEN_INPUTS), "b2_authority": b2_authority_block(),
         "carrier_lineage": lineage["carrier_lineage"], "board": lineage["board"], "carrier": lineage["carrier"],
         "prereg": {"path": PREREG_REL, "sha256": None, "frozen": False}, "image": image,
         "map": blocks["map"], "universe": blocks["universe"], "experiment": blocks["experiment"], "audit": blocks["audit"],
         "seeds": blocks["seeds"], "prediction": prediction, "instrument_pins": pins, "qualification_plan": qplan,
         "qualification": None, "qualified": False, "calibration": None, "plan": None,
         "rulings_binding": copy.deepcopy(RULINGS_BINDING), "history": []}
    got = verify(m, root=root, seams=seams)["stage"]
    if got != "S0":
        raise Refusal(f"init produced a manifest at {got}, not S0")
    return m


def freeze(manifest: dict, prereg_sha256: str, root: Path = REPO_ROOT, seams: Seams | None = None) -> dict:
    _require(manifest, "S0", "freeze", root=root, seams=seams)
    prereg = Path(root) / PREREG_REL
    if not _hex64(prereg_sha256) or not prereg.is_file() or sha256_file(prereg) != prereg_sha256:
        raise Refusal("freeze: the given preregistration sha256 is not the hash of the preregistration file on disk")
    c = copy.deepcopy(manifest)
    c["prereg"]["sha256"], c["prereg"]["frozen"] = prereg_sha256, True
    c["image"]["board_ready"] = True
    c["status"] = STATUS["S1"]
    c["history"].append({"at": _now(), "transition": "S1 freeze", "prereg_sha256": prereg_sha256})
    return _checked(manifest, c, "S1", root=root, seams=seams)


def qualify(manifest: dict, evidence_dir, readjudicate=None, root: Path = REPO_ROOT, seams: Seams | None = None) -> dict:
    _require(manifest, "S1", "qualify", root=root, seams=seams)
    if evidence_dir is None:
        raise Refusal("qualify needs the B3Q evidence directory")
    rec = reconstruct_qualification_record(Path(evidence_dir), Path(root))
    c = copy.deepcopy(manifest)
    c["qualification"], c["qualified"] = rec, True
    c["calibration"] = calibration_from(rec, c)
    c["status"] = STATUS["S2"]
    c["history"].append({"at": _now(), "transition": "S2 qualify", "manifest_at_run_sha256": rec["binding"]["b3_manifest_sha256"],
                         "rate_per_hour": rec["measured_rate_per_hour"]})
    return _checked(manifest, c, "S2", evidence_dir=evidence_dir, readjudicate=readjudicate, root=root, seams=seams)


def pin_plan(manifest: dict, plan_path, readjudicate=None, root: Path = REPO_ROOT, seams: Seams | None = None) -> dict:
    _require(manifest, "S2", "plan", readjudicate=readjudicate, root=root, seams=seams)     # never trust the input's flag
    if plan_path is None:
        raise Refusal("plan needs the plan file")
    findings = plan_findings(manifest, plan_path, root)
    if findings:
        raise Refusal("plan: " + "; ".join(findings[:6]))
    p = _resolve(str(plan_path), root)
    split = json.loads(p.read_text())["session_split"]
    pred = p.parent / "prediction.json"
    c = copy.deepcopy(manifest)
    c["plan"] = {"path": _relative(p, root), "sha256": sha256_file(p), "prediction_path": _relative(pred, root),
                 "prediction_sha256": sha256_file(pred), "sessions": len(split["sessions"]), "total_records": split["total_records"]}
    c["status"] = STATUS["S3"]
    c["history"].append({"at": _now(), "transition": "S3 plan", "plan_sha256": c["plan"]["sha256"]})
    return _checked(manifest, c, "S3", readjudicate=readjudicate, root=root, seams=seams)


# ------------------------------------------------------------------ publishing: no-clobber init, atomic replace


def publish_new(path: Path, text: str) -> None:
    """`init` never overwrites: the manifest is linked into place from a private temp file, which fails
    atomically if the name exists (a symlink too)."""
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise Refusal(f"init: {path} exists; a manifest is never overwritten (no-clobber)")
    if not path.parent.is_dir():
        raise Refusal(f"init: the directory {path.parent} does not exist")
    tmp = path.with_name(f".{path.name}.{os.getpid()}.part")
    try:
        with open(tmp, "x") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            raise Refusal(f"init: {path} appeared; a manifest is never overwritten (no-clobber)") from None
    finally:
        tmp.unlink(missing_ok=True)


def _rename_exchange(a: Path, b: Path) -> None:
    """renameat2(RENAME_EXCHANGE): the two names swap their files in ONE atomic step. No fallback: a
    system without it cannot give a transition compare-and-swap semantics, and that is an OSError."""
    import ctypes
    import errno
    libc = ctypes.CDLL(None, use_errno=True)
    if not hasattr(libc, "renameat2"):
        raise OSError(errno.ENOSYS, "renameat2 is not available: no atomic exchange on this system")
    libc.renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    AT_FDCWD, RENAME_EXCHANGE = -100, 2
    if libc.renameat2(AT_FDCWD, os.fsencode(a), AT_FDCWD, os.fsencode(b), RENAME_EXCHANGE) != 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e), str(b))


def replace_atomic(path: Path, original: bytes, text: str) -> None:
    """A transition's write, as a COMPARE-AND-SWAP over the bytes it was computed from (the owner's P2 on
    8ba72c4: a read followed by os.replace left a window in which a competitor's bytes were overwritten).

    Writers of this tool are serialised by an exclusive flock on the manifest's DIRECTORY (no lock file is
    left in the tree). The swap itself does not rely on that: the new file and the manifest are EXCHANGED in
    one atomic rename, so what this function then holds under the temp name is exactly — not "probably" —
    the file it displaced. If those are the original bytes, the swap stands. If they are not, a competitor
    wrote after the last comparison: the files are exchanged back, the competitor's bytes are the manifest
    again, and the transition is refused. Should yet another writer land between the two exchanges, its
    bytes are kept under a `.conflict` name and named in the refusal — nothing a competitor wrote is lost."""
    import fcntl
    path = Path(path)
    new = text.encode()
    tmp = path.with_name(f".{path.name}.{os.getpid()}.part")
    lock = os.open(path.parent, os.O_RDONLY)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refusal(f"{path}: another b3_manifest transition holds the directory lock; nothing was written") from None
        with open(tmp, "xb") as f:
            f.write(new)
            f.flush()
            os.fsync(f.fileno())
        try:
            if path.read_bytes() != original:          # the cheap early answer; the exchange below is the authority
                raise Refusal(f"{path} changed while the transition was being verified; nothing was written")
            _rename_exchange(tmp, path)
        except FileNotFoundError:
            raise Refusal(f"{path} vanished while the transition was being verified; nothing was written") from None
        displaced = tmp.read_bytes()
        if displaced != original:
            _rename_exchange(tmp, path)                # the competitor's file is the manifest again
            if tmp.read_bytes() != new:                # a second writer, between the two exchanges
                kept = path.with_name(f"{path.name}.conflict.{os.getpid()}")
                os.link(tmp, kept)
                raise Refusal(f"{path} changed twice while the transition was being published; the transition was withdrawn, the first "
                              f"competitor's bytes are the manifest and the second's are kept at {kept}")
            raise Refusal(f"{path} changed after the last comparison and before the publish; the transition was withdrawn and the "
                          f"competitor's bytes are preserved")
        os.fsync(lock)
    finally:
        tmp.unlink(missing_ok=True)
        os.close(lock)


# ------------------------------------------------------------------ CLI


def run(a, root: Path = REPO_ROOT, seams: Seams | None = None) -> int:
    path = Path(a.manifest)
    if a.command == "init":
        if path.exists() or path.is_symlink():
            raise Refusal(f"init: {path} exists; a manifest is never overwritten (no-clobber)")
        m = init(root, seams)
        publish_new(path, render(m))
        print(f"init: {path} ({manifest_sha256(m)[:12]}…) — {m['status']}")
        return 0
    if not path.is_file():
        raise Refusal(f"no B3 manifest at {path}: the manifest does not exist until S0")
    original = path.read_bytes()
    try:
        before = json.loads(original)
    except ValueError as exc:
        raise Refusal(f"the B3 manifest is not readable JSON: {exc}") from None
    if a.command == "verify":
        print(json.dumps(verify(before, a.evidence_dir, root=root, seams=seams), indent=1, sort_keys=True))
        return 0
    if a.command == "freeze":
        if not a.prereg_sha256:
            raise Refusal("freeze needs --prereg-sha256 (the owner writes it)")
        after = freeze(before, a.prereg_sha256, root=root, seams=seams)
    elif a.command == "qualify":
        after = qualify(before, a.evidence_dir, root=root, seams=seams)
    else:
        after = pin_plan(before, a.plan, root=root, seams=seams)
    check_transition(before, after)                      # the bytes read, against the bytes about to be written
    replace_atomic(path, original, render(after))
    print(f"{a.command}: {path} ({manifest_sha256(after)[:12]}…) — {after['status']}")
    return 0


def main(argv=None, root: Path = REPO_ROOT, seams: Seams | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["init", "freeze", "qualify", "plan", "verify"])
    ap.add_argument("--manifest", type=Path, default=None)
    ap.add_argument("--prereg-sha256", default=None)
    ap.add_argument("--evidence-dir", type=Path, default=None)
    ap.add_argument("--plan", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.manifest is None:
        a.manifest = Path(root) / MANIFEST_REL
    try:
        return run(a, root, seams)
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — a defect here or in an authority, never an input refusal
        print(f"INTERNAL ERROR: {type(exc).__name__}: {exc}\n{traceback.format_exc()}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
