#!/usr/bin/env python3
"""B4-FF — the BEHAVIOUR HYPOTHESIS: the per-element state machine the model assumes under each decoded
configuration (docs/b4_architecture.md section 4.4). Read from `b4/hypothesis/ff_behaviour_v0.2.json`, whose
`status` is "unverified": nothing in it has been observed on silicon.

    h = load()                        # THE entry, no path: the committed file only, held to HYPOTHESIS_SHA256, its shape, EVERY source re-hashed
    h.decode(config_bits, mapping)    # per element: primitive, INIT, SRVAL, modes, kind, inversion, applicability
    h.flag("ce_gates_capture")        # a behaviour flag the model reads (never a literal in the model)

Readings are MACHINE ENUMS (`READINGS`): the loader refuses a reading it does not know, and the decode compares
enums — an unrecognised reading is never read as a default (the owner's P2 on 2bad829). `clock_mode` is decoded
by storage context: for a flip-flop bit 1 means inverted; under a latch the CLKINV bit is asserted while
IS_G_INVERTED = 0 (docs/ff_latch_probe.md), so bit 1 means NOT inverted and bit 0 has no attested reading —
`unknown`, which puts that configuration outside the model's domain (the owner's P1).

Fixtures: a hypothesis that is not the committed file — a changed copy anywhere, a document built in a test —
enters ONLY through `fixture(doc, label)` / `fixture_file(path, label)`, which mark the object `fixture = True`
(the model writes that into every trace header) and verify no source; `load()` takes no path and reads the
committed file only, against the digest pinned here, so no external file can be loaded as formal (the owner's
P1 on 2bad829 and on b91162c). `unknown` is a reading only in clock_mode's latch context (the shape check).
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HYPOTHESIS_REL = "b4/hypothesis/ff_behaviour_v0.2.json"
HYPOTHESIS = REPO_ROOT / HYPOTHESIS_REL
HYPOTHESIS_SHA256 = "1118bedf4831bac3806be4aa3d9b56630912a946156869807f2c26f6374e6ed2"   # the committed file; a change to it is a change here
SCHEMA = "b4_ff_behaviour_hypothesis"
ELEMENTS = ("AFF", "A5FF", "BFF", "B5FF", "CFF", "C5FF", "DFF", "D5FF")
X5FF = ("A5FF", "B5FF", "C5FF", "D5FF")
FLAGS = ("init_event_sets_q_to_init", "clock_inversion_swaps_edge", "ff_capture_on_physical_rising_edge", "ce_gates_capture",
         "sr_tied_low_when_not_driven", "sync_sr_acts_on_edge_only", "async_sr_acts_on_level", "sr_has_priority_over_capture",
         "latch_transparent_when_gate_high_and_ge", "latch_gate_is_physical_clock", "x5ff_not_storage_when_latch")
# the machine readings each semantic may take; "unknown" only where the file says no attestation exists
READINGS = {
    "ff_init": ("init_0", "init_1"), "ff_srval": ("srval_0", "srval_1"), "ce_mode": ("driven", "tied_high"),
    "sr_mode": ("driven", "tied_low"), "sr_kind": ("synchronous", "asynchronous"), "storage_kind": ("latch", "flipflop"),
    "clock_mode": ("inverted", "not_inverted", "unknown"),
}
PER = {"ff_init": "element", "ff_srval": "element", "ce_mode": "slice", "sr_mode": "slice", "sr_kind": "slice", "storage_kind": "slice", "clock_mode": "slice"}
CONTEXTS = ("flipflop", "latch")
SOURCE_KINDS = ("vendor_primitive", "certificate_mapping", "repository_document", "project_decode_assumption")
UNKNOWN_ALLOWED = {("clock_mode", "latch")}        # the only (semantic, context) with no attested reading for one bit value
REQUIRED_BLOCKS = ("valid_configuration", "applicable_semantics", "observation_context", "initialisation_event", "domain_refusal", "formal_input")


class HypothesisRefusal(ValueError):
    pass


@dataclass(frozen=True)
class ElementConfig:
    element: str
    applicable: bool
    primitive: str | None
    init: int | None
    srval: int | None
    ce_driven: bool
    sr_driven: bool
    sync: bool
    latch: bool
    clk_inverted: bool | None      # None: the reading is unknown (outside the domain)


@dataclass(frozen=True)
class Decode:
    elements: dict
    unknown_readings: tuple        # (semantic, context, bit) with no attested reading; non-empty => outside the domain

    def __getitem__(self, e: str) -> ElementConfig:
        return self.elements[e]

    @property
    def in_domain(self) -> bool:
        return not self.unknown_readings


class Hypothesis:
    def __init__(self, doc: dict, path: str, sha256: str, fixture: bool):
        self.doc, self.path, self.sha256, self.fixture = doc, path, sha256, fixture

    @property
    def version(self) -> str:
        return self.doc["schema_version"]

    def flag(self, name: str) -> bool:
        if name not in FLAGS:
            raise HypothesisRefusal(f"{name!r} is not a behaviour flag of this hypothesis")
        return bool(self.doc["behaviour"][name])

    # -- fixtures: a changed hypothesis is ANOTHER object, marked, never the committed one
    def _variant(self, d: dict, label: str) -> "Hypothesis":
        d["schema_version"] = f"{self.version}+{label}"
        f = shape_findings(d)
        if f:
            raise HypothesisRefusal("; ".join(f))
        text = json.dumps(d, indent=1, sort_keys=True) + "\n"
        return Hypothesis(d, f"{self.path}+{label}", hashlib.sha256(text.encode()).hexdigest(), fixture=True)

    def with_flag(self, name: str, value: bool, label: str = "swap") -> "Hypothesis":
        if name not in FLAGS:
            raise HypothesisRefusal(f"{name!r} is not a behaviour flag of this hypothesis")
        d = copy.deepcopy(self.doc)
        d["behaviour"][name] = bool(value)
        return self._variant(d, label)

    def with_reading(self, semantic: str, bit_one: str, bit_zero: str, label: str = "swap", context: str | None = None) -> "Hypothesis":
        """Swap the readings of a semantic (for clock_mode, of one storage context); the enums are validated."""
        d = copy.deepcopy(self.doc)
        if semantic == "clock_mode":
            if context not in CONTEXTS:
                raise HypothesisRefusal("clock_mode readings are per storage context: flipflop or latch")
            d["decode"]["clock_mode"]["by_storage_context"][context] = {"bit_one": bit_one, "bit_zero": bit_zero}
        elif semantic in READINGS:
            d["decode"][semantic]["bit_one"], d["decode"][semantic]["bit_zero"] = bit_one, bit_zero
        else:
            raise HypothesisRefusal(f"{semantic!r} is not a decoded semantic")
        return self._variant(d, label)

    # -- the decode: every reading an enum of READINGS, compared by equality
    def _read(self, semantic: str, bit: int, context: str | None = None) -> str:
        entry = self.doc["decode"][semantic]
        table = entry["by_storage_context"][context] if semantic == "clock_mode" else entry
        reading = table["bit_one" if bit else "bit_zero"]
        if reading not in READINGS[semantic]:
            raise HypothesisRefusal(f"decode.{semantic}: the reading {reading!r} is not one of {READINGS[semantic]}")
        return reading

    def decode(self, config: dict[str, int], mapping) -> Decode:
        missing = [a for a in mapping.addresses if a not in config]
        if missing:
            raise HypothesisRefusal(f"the configuration lacks {len(missing)} addresses")
        bit = lambda element, semantic: int(config[mapping.address_of(element, semantic)])  # noqa: E731
        latch = self._read("storage_kind", bit(None, "storage_kind")) == "latch"
        context = "latch" if latch else "flipflop"
        ce_driven = self._read("ce_mode", bit(None, "ce_mode")) == "driven"
        sr_driven = self._read("sr_mode", bit(None, "sr_mode")) == "driven"
        sync = self._read("sr_kind", bit(None, "sr_kind")) == "synchronous"
        clk_bit = bit(None, "clock_mode")
        clk = self._read("clock_mode", clk_bit, context)
        unknown = (("clock_mode", context, clk_bit),) if clk == "unknown" else ()
        inv: bool | None = None if clk == "unknown" else clk == "inverted"
        out = {}
        for e in ELEMENTS:
            applicable = not (latch and e in X5FF and self.flag("x5ff_not_storage_when_latch"))
            init = 0 if self._read("ff_init", bit(e, "ff_init")) == "init_0" else 1
            srval = 0 if self._read("ff_srval", bit(e, "ff_srval")) == "srval_0" else 1
            if not applicable:
                out[e] = ElementConfig(e, False, None, None, None, ce_driven, sr_driven, sync, latch, inv)
                continue
            prim = ("LDCE" if srval == 0 else "LDPE") if latch else ("FDRE" if srval == 0 else "FDSE") if sync else ("FDCE" if srval == 0 else "FDPE")
            out[e] = ElementConfig(e, True, prim, init, srval, ce_driven, sr_driven, (sync and not latch), latch, inv)
        return Decode(out, unknown)


def shape_findings(doc) -> list[str]:
    f: list[str] = []
    if not isinstance(doc, dict):
        return ["the hypothesis is not an object"]
    if doc.get("schema") != SCHEMA:
        f.append(f"schema {doc.get('schema')!r} is not {SCHEMA!r}")
    if not isinstance(doc.get("schema_version"), str):
        f.append("schema_version is not a string")
    if doc.get("status") != "unverified":
        f.append(f"status {doc.get('status')!r} is not 'unverified' — no hypothesis of this line has been verified on silicon")
    if tuple(doc.get("elements") or ()) != ELEMENTS:
        f.append("elements are not the eight storage elements in order")
    beh = doc.get("behaviour")
    if not isinstance(beh, dict) or set(beh) != set(FLAGS) or not all(isinstance(v, bool) for v in beh.values()):
        f.append(f"behaviour must carry exactly the flags {sorted(FLAGS)}, each a bool")
    dec = doc.get("decode")
    if not isinstance(dec, dict) or set(dec) != set(READINGS):
        f.append(f"decode must carry exactly {sorted(READINGS)}")
    else:
        for k, v in dec.items():
            if not isinstance(v, dict) or v.get("per") != PER[k]:
                f.append(f"decode.{k} must be an object with per = {PER[k]!r}")
                continue
            tables = v.get("by_storage_context") if k == "clock_mode" else {"": v}
            if not isinstance(tables, dict) or (k == "clock_mode" and set(tables) != set(CONTEXTS)):
                f.append("decode.clock_mode must carry by_storage_context for exactly flipflop and latch")
                continue
            for ctx, t in tables.items():
                for side in ("bit_one", "bit_zero"):
                    r = (t or {}).get(side) if isinstance(t, dict) else None
                    if r not in READINGS[k]:
                        f.append(f"decode.{k}{('.' + ctx) if ctx else ''}.{side}: {r!r} is not one of {READINGS[k]}")
                    elif r == "unknown" and (k, ctx) not in UNKNOWN_ALLOWED:
                        f.append(f"decode.{k}{('.' + ctx) if ctx else ''}.{side}: unknown is allowed only where no attestation exists — clock_mode under a latch")
            if not isinstance(v.get("meaning"), dict) or set(v["meaning"]) != set(READINGS[k]) - ({"unknown"} if k != "clock_mode" else set()):
                f.append(f"decode.{k}.meaning must give the human meaning of every reading")
    src = doc.get("sources")
    if not isinstance(src, list) or not src:
        f.append("sources must be a non-empty list")
    else:
        kinds = {s.get("kind") for s in src if isinstance(s, dict)}
        for want in ("vendor_primitive", "certificate_mapping", "project_decode_assumption"):
            if want not in kinds:
                f.append(f"sources lack a {want!r} entry")
        for s in src:
            if not isinstance(s, dict) or s.get("kind") not in SOURCE_KINDS:
                f.append(f"a source has an unknown kind {s.get('kind') if isinstance(s, dict) else s!r}"); continue
            if s["kind"] != "project_decode_assumption":
                if not isinstance(s.get("path"), str) or not isinstance(s.get("sha256"), str) or len(s["sha256"]) != 64:
                    f.append(f"source {s['kind']} {s.get('path')!r} lacks a path or a 64-hex sha256")
                if s["kind"] == "vendor_primitive" and not isinstance(s.get("root"), str):
                    f.append(f"vendor source {s.get('path')!r} names no root")
            if not s.get("adopted") and not s.get("items"):
                f.append(f"source {s['kind']} {s.get('path', '')!r} states nothing adopted")
    for k in REQUIRED_BLOCKS:
        if not isinstance(doc.get(k), dict):
            f.append(f"{k} is absent")
    oc = doc.get("observation_context")
    if isinstance(oc, dict) and not (isinstance(oc.get("executing_side_visible"), list) and isinstance(oc.get("host_only_diagnostics"), list)):
        f.append("observation_context must list executing_side_visible and host_only_diagnostics")
    return f


def source_findings(doc: dict, repo_root: Path = REPO_ROOT) -> list[str]:
    """Every named source re-hashed: a vendor file under its root, a repository file under the repository. An absent
    source is a FINDING (never a skip): the hypothesis names what it was written from."""
    f: list[str] = []
    for s in doc.get("sources", []):
        if s.get("kind") == "vendor_primitive":
            p = Path(s["root"]) / s["path"]
        elif s.get("kind") in ("certificate_mapping", "repository_document"):
            p = repo_root / s["path"]
        else:
            continue
        if not p.is_file():
            f.append(f"source {s['path']} is absent at {p}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != s["sha256"]:
            f.append(f"source {s['path']} does not hash to the recorded digest")
    return f


def load() -> Hypothesis:
    """THE entry for the formal hypothesis: the committed file, held to HYPOTHESIS_SHA256, its shape, its sources —
    always, and nothing else can be loaded here (no path argument exists)."""
    try:
        raw = HYPOTHESIS.read_bytes()
        doc = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise HypothesisRefusal(f"the committed hypothesis {HYPOTHESIS_REL} cannot be read: {exc}") from exc
    got = hashlib.sha256(raw).hexdigest()
    if got != HYPOTHESIS_SHA256:
        raise HypothesisRefusal(f"the committed hypothesis hashes to {got[:16]}…, not the pinned {HYPOTHESIS_SHA256[:16]}…")
    f = shape_findings(doc) or source_findings(doc)
    if f:
        raise HypothesisRefusal("; ".join(f))
    return Hypothesis(doc, HYPOTHESIS_REL, got, fixture=False)


def fixture_file(path: Path, label: str) -> Hypothesis:
    """A hypothesis document from ANY file — including a valid copy of the committed one — is a fixture: marked,
    its sources unverified. There is no path by which a file becomes the formal hypothesis."""
    try:
        doc = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise HypothesisRefusal(f"the fixture {path} cannot be read: {exc}") from exc
    return fixture(doc, label)


def fixture(doc: dict, label: str) -> Hypothesis:
    """The ONLY way in for a hypothesis that is not the committed file: the shape is held, the sources are NOT
    verified, and the object is marked `fixture = True` — every trace made under it says so."""
    if not isinstance(label, str) or not label:
        raise HypothesisRefusal("a fixture hypothesis needs a label")
    f = shape_findings(doc)
    if f:
        raise HypothesisRefusal("; ".join(f))
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    return Hypothesis(copy.deepcopy(doc), f"fixture:{label}", hashlib.sha256(text.encode()).hexdigest(), fixture=True)


if __name__ == "__main__":
    h = load()
    print(h.path, h.sha256, h.version, "sources ok")
