#!/usr/bin/env python3
"""B4-FF — the BEHAVIOUR HYPOTHESIS: the per-element state machine the model assumes under each decoded
configuration (docs/b4_architecture.md section 4.4). Read from `b4/hypothesis/ff_behaviour_v0.1.json`,
whose `status` is "unverified": nothing in it has been observed on silicon. The sources are listed in the
file by kind — the vendor's UNISIM primitives (root + path + sha256 + the lines adopted), the certificate
(path + sha256), and the project's own decode assumptions — and this module holds the file to its shape
and re-hashes every named source when the root is present.

    h = load()                       # the hypothesis object (refuses a malformed file by name)
    h.decode(config_bits, mapping)   # per element: primitive, INIT, SRVAL, ce_driven, sr_driven, sync, latch, clk_inverted, applicable
    h.flag("ce_gates_capture")       # a behaviour flag the model reads (never a literal in the model)

The model (`b4_ff_model.py`) implements the state machine PARAMETERISED by `behaviour` and `decode`; a
different hypothesis file must give different observations (the hypothesis-swap fixture), which is how
a model that ignores its hypothesis is caught.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HYPOTHESIS_REL = "b4/hypothesis/ff_behaviour_v0.1.json"
HYPOTHESIS = REPO_ROOT / HYPOTHESIS_REL
SCHEMA = "b4_ff_behaviour_hypothesis"
ELEMENTS = ("AFF", "A5FF", "BFF", "B5FF", "CFF", "C5FF", "DFF", "D5FF")
X5FF = ("A5FF", "B5FF", "C5FF", "D5FF")
FLAGS = ("init_event_sets_q_to_init", "clock_inversion_swaps_edge", "ff_capture_on_physical_rising_edge", "ce_gates_capture",
         "sr_tied_low_when_not_driven", "sync_sr_acts_on_edge_only", "async_sr_acts_on_level", "sr_has_priority_over_capture",
         "latch_transparent_when_gate_high_and_ge", "latch_gate_is_physical_clock", "x5ff_not_storage_when_latch")
DECODE_KEYS = ("ff_init", "ff_srval", "ce_mode", "sr_mode", "sr_kind", "storage_kind", "clock_mode")


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
    clk_inverted: bool


class Hypothesis:
    def __init__(self, doc: dict, path: str, sha256: str):
        self.doc = doc
        self.path = path
        self.sha256 = sha256

    @property
    def version(self) -> str:
        return self.doc["schema_version"]

    def flag(self, name: str) -> bool:
        if name not in FLAGS:
            raise HypothesisRefusal(f"{name!r} is not a behaviour flag of this hypothesis")
        return bool(self.doc["behaviour"][name])

    def with_flag(self, name: str, value: bool, label: str = "swap") -> "Hypothesis":
        """A DIFFERENT hypothesis (the swap fixture): one flag changed, the status still unverified, its own digest."""
        if name not in FLAGS:
            raise HypothesisRefusal(f"{name!r} is not a behaviour flag of this hypothesis")
        d = copy.deepcopy(self.doc)
        d["behaviour"][name] = bool(value)
        d["schema_version"] = f"{self.version}+{label}"
        text = json.dumps(d, indent=1, sort_keys=True) + "\n"
        return Hypothesis(d, f"{self.path}+{label}", hashlib.sha256(text.encode()).hexdigest())

    def with_reading(self, semantic: str, bit_one_means: str, bit_zero_means: str, label: str = "swap") -> "Hypothesis":
        """A different decode reading (the polarity-swap fixture)."""
        if semantic not in DECODE_KEYS:
            raise HypothesisRefusal(f"{semantic!r} is not a decoded semantic")
        d = copy.deepcopy(self.doc)
        d["decode"][semantic]["bit_one_means"], d["decode"][semantic]["bit_zero_means"] = bit_one_means, bit_zero_means
        d["schema_version"] = f"{self.version}+{label}"
        text = json.dumps(d, indent=1, sort_keys=True) + "\n"
        return Hypothesis(d, f"{self.path}+{label}", hashlib.sha256(text.encode()).hexdigest())

    # -- the decode: configuration bits -> per-element parameters, through the hypothesis's readings
    def _reads(self, semantic: str, bit: int) -> str:
        return self.doc["decode"][semantic]["bit_one_means" if bit else "bit_zero_means"]

    def decode(self, config: dict[str, int], mapping) -> dict[str, ElementConfig]:
        """`config` maps every address of `mapping` to 0 / 1. Every reading goes through the hypothesis's text
        (`decode.*.bit_one_means`), so a swapped reading changes the decode."""
        missing = [a for a in mapping.addresses if a not in config]
        if missing:
            raise HypothesisRefusal(f"the configuration lacks {len(missing)} addresses")
        bit = lambda element, semantic: int(config[mapping.address_of(element, semantic)])  # noqa: E731
        latch = self._reads("storage_kind", bit(None, "storage_kind")).startswith("latch")
        ce_driven = self._reads("ce_mode", bit(None, "ce_mode")).startswith("CE driven")
        sr_driven = self._reads("sr_mode", bit(None, "sr_mode")).startswith("SR driven")
        sync = self._reads("sr_kind", bit(None, "sr_kind")).startswith("synchronous")
        inv = self._reads("clock_mode", bit(None, "clock_mode")).startswith("clock inverted")
        out = {}
        for e in ELEMENTS:
            applicable = not (latch and e in X5FF and self.flag("x5ff_not_storage_when_latch"))
            init = 0 if self._reads("ff_init", bit(e, "ff_init")).startswith("INIT = 0") else 1
            srval = 0 if self._reads("ff_srval", bit(e, "ff_srval")).startswith("SRVAL = 0") else 1
            if not applicable:
                out[e] = ElementConfig(e, False, None, None, None, ce_driven, sr_driven, sync, latch, inv)
                continue
            if latch:
                prim = "LDCE" if srval == 0 else "LDPE"
            elif sync:
                prim = "FDRE" if srval == 0 else "FDSE"
            else:
                prim = "FDCE" if srval == 0 else "FDPE"
            out[e] = ElementConfig(e, True, prim, init, srval, ce_driven, sr_driven, (sync and not latch), latch, inv)
        return out


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
    if not isinstance(dec, dict) or set(dec) != set(DECODE_KEYS):
        f.append(f"decode must carry exactly {sorted(DECODE_KEYS)}")
    else:
        for k, v in dec.items():
            if not isinstance(v, dict) or not all(isinstance(v.get(x), str) for x in ("bit_one_means", "bit_zero_means", "per")):
                f.append(f"decode.{k} must carry bit_one_means, bit_zero_means, per as strings")
    src = doc.get("sources")
    if not isinstance(src, list) or not src:
        f.append("sources must be a non-empty list")
    else:
        kinds = {s.get("kind") for s in src if isinstance(s, dict)}
        for want in ("vendor_primitive", "certificate_mapping", "project_decode_assumption"):
            if want not in kinds:
                f.append(f"sources lack a {want!r} entry")
        for s in src:
            if not isinstance(s, dict):
                f.append("a source is not an object"); continue
            if s.get("kind") in ("vendor_primitive", "certificate_mapping"):
                if not isinstance(s.get("path"), str) or not isinstance(s.get("sha256"), str) or len(s["sha256"]) != 64:
                    f.append(f"source {s.get('kind')} {s.get('path')!r} lacks a path or a 64-hex sha256")
                if s.get("kind") == "vendor_primitive" and not isinstance(s.get("root"), str):
                    f.append(f"vendor source {s.get('path')!r} names no root")
            if not s.get("adopted") and not s.get("items"):
                f.append(f"source {s.get('kind')} {s.get('path', '')!r} states nothing adopted")
    for k in ("valid_configuration", "applicable_semantics", "observation_context", "initialisation_event"):
        if not isinstance(doc.get(k), dict):
            f.append(f"{k} is absent")
    return f


def source_findings(doc: dict, repo_root: Path = REPO_ROOT) -> list[str]:
    """Every named source re-hashed: a vendor file under its root, the certificate under the repository. A
    source that is absent is a FINDING (never a skip): the hypothesis names what it was written from."""
    f: list[str] = []
    for s in doc.get("sources", []):
        if s.get("kind") == "vendor_primitive":
            p = Path(s["root"]) / s["path"]
        elif s.get("kind") == "certificate_mapping":
            p = repo_root / s["path"]
        else:
            continue
        if not p.is_file():
            f.append(f"source {s['path']} is absent at {p}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != s["sha256"]:
            f.append(f"source {s['path']} does not hash to the recorded digest")
    return f


def load(path: Path = HYPOTHESIS, check_sources: bool = False) -> Hypothesis:
    try:
        text = Path(path).read_text()
        doc = json.loads(text)
    except (OSError, ValueError) as exc:
        raise HypothesisRefusal(f"the hypothesis {path} cannot be read: {exc}") from exc
    f = shape_findings(doc)
    if f:
        raise HypothesisRefusal("; ".join(f))
    if check_sources:
        f = source_findings(doc)
        if f:
            raise HypothesisRefusal("; ".join(f))
    rel = str(Path(path).resolve().relative_to(REPO_ROOT)) if Path(path).resolve().is_relative_to(REPO_ROOT) else str(path)
    return Hypothesis(doc, rel, hashlib.sha256(text.encode()).hexdigest())


if __name__ == "__main__":
    h = load(check_sources=True)
    print(h.path, h.sha256, h.version, "sources ok")
