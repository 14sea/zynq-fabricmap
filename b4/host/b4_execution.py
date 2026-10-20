#!/usr/bin/env python3
"""B4-FF — the EXECUTION BOUNDARY (the revised 2b-2 scope, section 3; the owner's rulings of 2026-10-18).

The executing side — engine, operators, cartographer, ledger — receives a `PublicTask` (the sorted addresses, the
declared base, the two stimuli, the public scoring — masks, targets, weights — and the commitment to the target's source;
task-v0.2 / H: NO landscape seed, NO planted configuration, NO private record) and an `ObservationPort`, which exposes
`observe(config, stimulus)` and the addresses and NOTHING else: no mapping entries, no hypothesis, no effect
table, no decode, no diagnose, no oracle. The port is built by the host assembler from a `Fabric`; the executing
side never holds the fabric. A test's call spy (`SpyPort`) records every attribute an engine touches.

A `DomainRefusal` raised by the port is a TERMINAL EVENT of the run (section 3.2): recorded as it came — the fixed
code, the phase, the attempt ordinal, the candidate's and the stimulus's digests, the seeds, the budget, the number
of successful observations, the generator's state, the population's and the map's commitments at that moment —
kept apart from the specimen ledger; the candidate has no fitness, no specimen, no place in the population and
triggers no map update; nothing is generated, observed, scored, selected or updated afterwards; the generator is
NOT rolled back (what the candidate consumed stays consumed). Any other refusal — a malformed step, a model
refusal that is not DOMAIN, an internal error — is recorded by its own name and never folded into DOMAIN.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_ff_model as fm  # noqa: E402  (the DomainRefusal / ModelRefusal classes and the Fabric the assembler wraps)

DOMAIN = fm.DomainRefusal.CODE
PHASES = ("base", "probe", "search", "holdout")
REFUSAL_KINDS = ("ValueError", "ModelRefusal", "SourceRefusal")      # the finite set the engine records and the replay re-raises
SOURCE_KINDS = ("truth", "permuted", "dropout", "custom")


def _hex64(v) -> bool:
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


class SourceRefusal(ValueError):
    """The observation source's identity is absent, malformed or drifting — a refusal by its own name."""


def provenance_findings(hdr) -> list[str]:
    """The observation source's identity as EVERY trace must carry it: the hypothesis (path, sha256, version, fixture),
    the mapping (site, certificate, certificate_sha256) and the fabric (kind, effect_sha256, dropout_sha256, dropout_count,
    seed) — exact fields, exact types, 64-hex digests. Used by the engine on every observation and by the replay on the
    record; a descriptor identifies the input and never carries the effect table itself."""
    f: list[str] = []
    if not isinstance(hdr, dict) or set(hdr) != {"hypothesis", "mapping", "fabric"}:
        return ["the source identity must carry exactly hypothesis, mapping and fabric"]
    h, m, fb = hdr["hypothesis"], hdr["mapping"], hdr["fabric"]
    if not isinstance(h, dict) or set(h) != {"path", "sha256", "version", "fixture"}:
        f.append("hypothesis identity: exactly path, sha256, version, fixture")
    else:
        if not (isinstance(h["path"], str) and h["path"]):
            f.append("hypothesis identity: path")
        if not _hex64(h["sha256"]):
            f.append("hypothesis identity: sha256 is not a 64-hex digest")
        if not (isinstance(h["version"], str) and h["version"]):
            f.append("hypothesis identity: version")
        if not isinstance(h["fixture"], bool):
            f.append("hypothesis identity: fixture is not a bool")
    if not isinstance(m, dict) or set(m) != {"site", "certificate", "certificate_sha256"}:
        f.append("mapping identity: exactly site, certificate, certificate_sha256")
    else:
        if not (isinstance(m["site"], str) and m["site"]) or not (isinstance(m["certificate"], str) and m["certificate"]):
            f.append("mapping identity: site / certificate")
        if not _hex64(m["certificate_sha256"]):
            f.append("mapping identity: certificate_sha256 is not a 64-hex digest")
    if not isinstance(fb, dict) or set(fb) != {"kind", "effect_sha256", "dropout_sha256", "dropout_count", "seed"}:
        f.append("fabric identity: exactly kind, effect_sha256, dropout_sha256, dropout_count, seed")
    else:
        if fb["kind"] not in SOURCE_KINDS:
            f.append(f"fabric identity: kind {fb['kind']!r}")
        if not _hex64(fb["effect_sha256"]) or not _hex64(fb["dropout_sha256"]):
            f.append("fabric identity: effect_sha256 / dropout_sha256 are not 64-hex digests")
        if not _is_int(fb["dropout_count"]) or fb["dropout_count"] < 0:
            f.append("fabric identity: dropout_count")
        if not (fb["seed"] is None or _is_int(fb["seed"])):
            f.append("fabric identity: seed")
    return f


def refusal_kind(exc: BaseException) -> str | None:
    """The finite name the engine records for a non-DOMAIN refusal; None for anything else (which propagates)."""
    if isinstance(exc, SourceRefusal):
        return "SourceRefusal"
    if isinstance(exc, fm.DomainRefusal):
        return None
    if isinstance(exc, fm.ModelRefusal):
        return "ModelRefusal"
    if isinstance(exc, ValueError):
        return "ValueError"
    return None


def raise_refusal(kind: str, message: str):
    """The replay re-raises a recorded refusal by its finite kind — never by importing a name."""
    if kind == "SourceRefusal":
        raise SourceRefusal(message)
    if kind == "ModelRefusal":
        raise fm.ModelRefusal(message)
    if kind == "ValueError":
        raise ValueError(message)
    raise ValueError(f"unknown refusal kind {kind!r}")


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ObservationPort:
    """The only model access the executing side has. Built from a Fabric by the host; keeps no reference the
    executing side could reach (the fabric is captured in a closure)."""
    __slots__ = ("addresses", "_observe", "calls")

    def __init__(self, fabric: fm.Fabric):
        observe = fabric.observe
        self.addresses = tuple(fabric.mapping.addresses)
        self._observe = observe
        self.calls = 0

    def observe(self, config: dict, stimulus: list) -> dict:
        self.calls += 1
        return self._observe(config, stimulus)


class SpyPort(ObservationPort):
    """A port that records every attribute name touched FROM OUTSIDE its own methods (a test's capability spy):
    what the engine reads is recorded; what `observe` does to its own counter is not."""
    __slots__ = ("touched", "_inside")

    def __init__(self, fabric: fm.Fabric):
        object.__setattr__(self, "touched", [])
        object.__setattr__(self, "_inside", False)
        super().__init__(fabric)

    def __getattribute__(self, name):
        if name not in ("touched", "__class__") and not name.startswith("_") and not object.__getattribute__(self, "_inside"):
            object.__getattribute__(self, "touched").append(name)
        return object.__getattribute__(self, name)

    def observe(self, config: dict, stimulus: list) -> dict:
        object.__setattr__(self, "_inside", True)
        try:
            return ObservationPort.observe(self, config, stimulus)
        finally:
            object.__setattr__(self, "_inside", False)


@dataclass(frozen=True)
class PublicTask:
    """What every arm receives — identical for all arms of a pair; nothing here was read from a mapping. task-v0.2 (H): no
    landscape seed, no planted genome, no private record — the targets are the planted configuration's observed traces and
    `target_source_sha256` commits to the two setup observations (b4_target). A fixed-program access contract, not secrecy."""
    label: str
    version: str
    addresses: tuple
    base_genome: int                 # declared: all-zero (the owner's ruling 3 of 2026-10-18)
    stimulus: tuple                  # the steps, as the model's validate_step accepts them
    mask: tuple                      # (step_index, element_index) cells that score
    target: tuple                    # 0 / 1 per mask cell
    weights: tuple                   # integer weight per mask cell
    holdout_stimulus: tuple
    holdout_mask: tuple
    holdout_target: tuple
    holdout_weights: tuple
    target_source_sha256: str

    @property
    def ceiling(self) -> int:
        return sum(self.weights)

    @property
    def holdout_ceiling(self) -> int:
        return sum(self.holdout_weights)

    def digest(self) -> str:
        return sha256_json({"label": self.label, "version": self.version, "addresses": list(self.addresses),
                            "base_genome": self.base_genome, "stimulus": list(self.stimulus), "mask": list(self.mask), "target": list(self.target),
                            "weights": list(self.weights), "holdout_stimulus": list(self.holdout_stimulus), "holdout_mask": list(self.holdout_mask),
                            "holdout_target": list(self.holdout_target), "holdout_weights": list(self.holdout_weights), "target_source_sha256": self.target_source_sha256})


def genome_to_config(genome: int, addresses: tuple) -> dict:
    return {a: (genome >> i) & 1 for i, a in enumerate(addresses)}


def genome_hex(genome: int, n: int) -> str:
    return f"{genome:0{(n + 3) // 4}x}"


@dataclass(frozen=True)
class TerminalEvent:
    code: str
    phase: str
    attempt: int                     # the ordinal of the observation that was refused (1-based over all phases)
    genome: int
    config_sha256: str
    stimulus_sha256: str
    task_digest: str                 # the engine knows the task by its digest only (task-v0.2 / H): the pair's seeds are the harness's record
    operator_seed: int
    budget: int
    successful_observations: int
    rng_state: int
    population_commitment: str
    map_commitment: str
    map_version: int

    def as_dict(self) -> dict:
        return {"code": self.code, "phase": self.phase, "attempt": self.attempt, "genome": self.genome, "config_sha256": self.config_sha256,
                "stimulus_sha256": self.stimulus_sha256, "task_digest": self.task_digest, "operator_seed": self.operator_seed,
                "budget": self.budget, "successful_observations": self.successful_observations, "rng_state": self.rng_state,
                "population_commitment": self.population_commitment, "map_commitment": self.map_commitment, "map_version": self.map_version}


class Terminated(Exception):
    """Raised inside the engine to unwind after a terminal event has been recorded."""

    def __init__(self, event: TerminalEvent):
        super().__init__(event.code)
        self.event = event


@dataclass
class OtherRefusal:
    """A refusal that is not DOMAIN: kept by its own name, never counted as a terminal event."""
    kind: str
    message: str
    phase: str
    attempt: int

    def as_dict(self) -> dict:
        return {"kind": self.kind, "message": self.message, "phase": self.phase, "attempt": self.attempt}


def observe_candidate(port: ObservationPort, genome: int, stimulus, phase: str, attempt: int, context: dict) -> dict:
    """One observation through the port. DOMAIN -> a TerminalEvent (raised as Terminated, with everything the
    engine passed in `context` recorded as it stood BEFORE the call); any other exception propagates by its name."""
    if phase not in PHASES:
        raise ValueError(phase)
    config = genome_to_config(genome, port.addresses)
    try:
        return port.observe(config, list(stimulus))
    except fm.DomainRefusal as exc:
        raise Terminated(TerminalEvent(
            code=exc.CODE, phase=phase, attempt=attempt, genome=genome, config_sha256=sha256_json(config),
            stimulus_sha256=sha256_json(list(stimulus)), task_digest=context["task_digest"], operator_seed=context["operator_seed"],
            budget=context["budget"], successful_observations=context["successful_observations"], rng_state=context["rng_state"],
            population_commitment=context["population_commitment"], map_commitment=context["map_commitment"], map_version=context["map_version"])) from None
