#!/usr/bin/env python3
"""B4-FF — the OBSERVATION CARTOGRAPHER (the revised 2b-2 scope, section 4.2), closed-book: it eats only successful
observations — the genome written, the stimulus's digest and the visible q grid (q_after per step per element) —
and it names nothing of the decode. A relation says, for an address, what the address was SEEN to change in the
tested contexts: which cells (step, element) differed between two observations under the same stimulus whose
genomes differ in exactly that one bit, and which cells changed presence (a readout on one side, None on the other).
No difference in a pair is "no effect seen in this pair" — never a permanent no-effect; a pair with and a pair
without a difference make the address `context_dependent`; an address with no single-bit pair yet is `unknown`.
Multi-bit interventions are counted, never decomposed into single-address evidence. No semantic (INIT, CE, latch …)
is claimed here: `semantic_claims` is empty in v0.1, a slot for a later, separately reviewed rule with its own
positive and negative controls.

    carto = ObservationCarto(n)                  # n addresses, by genome bit
    carto.ingest(seq, genome, stimulus_sha256, q_grid)   -> True when a relation changed (a new map version)
    carto.view()                                 # the operator's groups (section 4.2): disjoint, by the set of elements an
                                                 # address was seen to affect; empty when nothing is known
    carto.commitment()                           # sha256 of the canonical relations document
    carto.render(binding)                        # a self_map v3 (draft) document

Controls: `derangement` / `derangement_attempts` (B3's rule, Fisher–Yates with rejection, the generator continuing
across attempts; every attempt auditable), `relabel_genome` (control X-A: the ADDRESSES relabelled by a fixed
derangement π before X's cartographer — bit a of the genome moves to bit π(a), the q grid untouched),
`isomorphic_addresses` (X against its shadow under π, in full), `residual_structure` (post hoc: did π preserve the
operator's partition — reported, never fed back); `permute_grid` / `isomorphic` (the LANE permutation, kept as the
cartographer's symmetry test of the relation / partition structure — not an arm); `address_only_view` (A0, from
the addresses' frame field alone), `shuffled_view` (D); `oracle_view` (Omega) is PRIVILEGED — it reads the
mapping — and says so in the view.
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
from b4_rng import Rng  # noqa: E402

ELEMENTS = 8
CARTO_VERSION = "b4-obs-carto-v0.1"
STATES = ("unknown", "effect_seen", "no_effect_seen", "context_dependent")


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass
class Relation:
    cells: set = field(default_factory=set)            # (step, element) where both sides read 0/1 and differed
    presence: set = field(default_factory=set)         # (step, element) where exactly one side read None
    pairs_with_effect: int = 0
    pairs_without_effect: int = 0
    contexts: set = field(default_factory=set)         # stimulus digests the pairs were seen under
    evidence: list = field(default_factory=list)       # (seq_i, seq_j) pairs

    @property
    def state(self) -> str:
        if self.pairs_with_effect == 0 and self.pairs_without_effect == 0:
            return "unknown"
        if self.pairs_with_effect and self.pairs_without_effect:
            return "context_dependent"
        return "effect_seen" if self.pairs_with_effect else "no_effect_seen"

    @property
    def elements(self) -> frozenset:
        return frozenset(e for _, e in self.cells) | frozenset(e for _, e in self.presence)

    def doc(self) -> dict:
        return {"state": self.state, "affected_cells": sorted(list(c) for c in self.cells), "presence_cells": sorted(list(c) for c in self.presence),
                "affected_elements": sorted(self.elements), "pairs_with_effect": self.pairs_with_effect, "pairs_without_effect": self.pairs_without_effect,
                "contexts": sorted(self.contexts), "evidence": [list(e) for e in self.evidence]}


@dataclass(frozen=True)
class MapView:
    groups: tuple                 # tuple of tuples of genome bits, disjoint; empty when nothing is known
    version: int
    commitment: str
    privileged: bool = False      # True when the view, or ANY view it was derived from, read the mapping
    origin: str = "learned"       # the last transformation
    provenance: tuple = ("learned",)   # the whole chain, first to last (a transformation never drops its parent)
    base_commitment: str = ""     # the parent view's commitment, for a derived view

    def as_dict(self) -> dict:
        return {"groups": [list(g) for g in self.groups], "version": self.version, "commitment": self.commitment, "privileged": self.privileged,
                "origin": self.origin, "provenance": list(self.provenance), "base_commitment": self.base_commitment}

    @staticmethod
    def from_dict(d: dict) -> "MapView":
        return MapView(tuple(tuple(g) for g in d["groups"]), d["version"], d["commitment"], bool(d["privileged"]), d["origin"], tuple(d["provenance"]), d.get("base_commitment", ""))


class ObservationCarto:
    def __init__(self, n: int):
        self.n = n
        self.specimens: list[dict] = []
        self.rel = {a: Relation() for a in range(n)}
        self.version = 0
        self.multi_bit_pairs = 0
        self.history: list[str] = []

    def _cells(self, g1: list, g2: list) -> tuple[set, set]:
        cells, presence = set(), set()
        for s, (r1, r2) in enumerate(zip(g1, g2)):
            for e, (a, b) in enumerate(zip(r1, r2)):
                if a is None and b is None:
                    continue
                if (a is None) != (b is None):
                    presence.add((s, e))
                elif a != b:
                    cells.add((s, e))
        return cells, presence

    def ingest(self, seq: int, genome: int, stimulus_sha256: str, q_grid: list) -> bool:
        if not isinstance(genome, int) or genome < 0 or genome >> self.n:
            raise ValueError("the genome is not over the cartographer's addresses")
        grid = [list(row) for row in q_grid]
        changed = False
        for other in self.specimens:
            if other["stimulus_sha256"] != stimulus_sha256:
                continue
            diff = genome ^ other["genome"]
            if diff == 0:
                continue
            if diff & (diff - 1):
                self.multi_bit_pairs += 1
                continue
            a = diff.bit_length() - 1
            cells, presence = self._cells(other["grid"], grid)
            r = self.rel[a]
            before = r.doc()
            if cells or presence:
                r.cells |= cells; r.presence |= presence; r.pairs_with_effect += 1
            else:
                r.pairs_without_effect += 1
            r.contexts.add(stimulus_sha256)
            r.evidence.append((other["seq"], seq))
            if r.doc() != before:
                changed = True
        self.specimens.append({"seq": seq, "genome": genome, "stimulus_sha256": stimulus_sha256, "grid": grid})
        if changed:
            self.version += 1
            self.history.append(self.commitment())
        return changed

    def relations_doc(self) -> dict:
        return {str(a): self.rel[a].doc() for a in range(self.n)}

    def commitment(self) -> str:
        return sha256_json({"carto": CARTO_VERSION, "n": self.n, "relations": self.relations_doc()})

    def view(self) -> MapView:
        """Disjoint groups by the set of elements an address was SEEN to affect (effect_seen only): one group per
        single element, one group for the addresses affecting two or more elements; unknown, no-effect and
        context-dependent addresses are in no group; an empty map gives no groups (the operator falls back to the
        random-safe move). Groups are drawn uniformly by the operator."""
        single: dict[int, list[int]] = {}
        multi: list[int] = []
        for a in range(self.n):
            r = self.rel[a]
            if r.state != "effect_seen":
                continue
            els = r.elements
            if len(els) == 1:
                single.setdefault(next(iter(els)), []).append(a)
            elif len(els) >= 2:
                multi.append(a)
        groups = [tuple(sorted(single[e])) for e in sorted(single)]
        if multi:
            groups.append(tuple(sorted(multi)))
        return MapView(tuple(groups), self.version, self.commitment(), False, "learned", ("learned",))

    def render(self, binding: dict, addresses: tuple) -> dict:
        return {"schema": "self_map", "schema_version": "3.0.0-draft", "cartographer": CARTO_VERSION, "binding": dict(binding),
                "universe": {"addresses": self.n, "class": "clb_ff_config", "safety_class": "content"}, "version": self.version,
                "relations": [{"genome_bit": a, "address": addresses[a], **self.rel[a].doc()} for a in range(self.n)],
                "semantic_claims": [], "groups": [list(g) for g in self.view().groups], "multi_bit_pairs_seen": self.multi_bit_pairs,
                "host_verdict": None}


# ------------------------------------------------------------------ the v3 document's shape (no external dependency)
def schema_findings(doc) -> list[str]:
    """The v3 draft's shape held without a schema library: the same constraints as b4/schemas/self_map_v3.schema.json."""
    import re
    f: list[str] = []
    if not isinstance(doc, dict):
        return ["not an object"]
    want = {"schema", "schema_version", "cartographer", "binding", "universe", "version", "relations", "semantic_claims", "groups", "multi_bit_pairs_seen", "host_verdict"}
    if set(doc) != want:
        f.append(f"keys {sorted(set(doc) ^ want)} differ from the schema's")
        return f
    if doc["schema"] != "self_map" or doc["schema_version"] != "3.0.0-draft":
        f.append("schema / schema_version")
    u = doc["universe"]
    if not (isinstance(u, dict) and set(u) == {"addresses", "class", "safety_class"} and isinstance(u["addresses"], int) and u["addresses"] >= 1
            and u["class"] == "clb_ff_config" and u["safety_class"] == "content"):
        f.append("universe")
    if doc["semantic_claims"] != []:
        f.append("semantic_claims must be empty in v0.1")
    if doc["host_verdict"] is not None:
        f.append("host_verdict must be null inside the map")
    if not isinstance(doc["multi_bit_pairs_seen"], int) or doc["multi_bit_pairs_seen"] < 0:
        f.append("multi_bit_pairs_seen")
    if not isinstance(doc["version"], int) or doc["version"] < 0:
        f.append("version")
    keys = {"genome_bit", "address", "state", "affected_cells", "presence_cells", "affected_elements", "pairs_with_effect", "pairs_without_effect", "contexts", "evidence"}
    for r in doc["relations"]:
        if not isinstance(r, dict) or set(r) != keys:
            f.append("a relation's keys"); continue
        if r["state"] not in STATES:
            f.append(f"relation {r['genome_bit']}: state {r['state']!r}")
        if not re.match(r"^0x[0-9a-f]{8}/[0-9]+/[0-9]+$", r["address"]):
            f.append(f"relation {r['genome_bit']}: address form")
        for k in ("affected_cells", "presence_cells"):
            if not all(isinstance(c, list) and len(c) == 2 and all(isinstance(x, int) and x >= 0 for x in c) for c in r[k]):
                f.append(f"relation {r['genome_bit']}: {k}")
        if not all(isinstance(e, int) and 0 <= e <= 7 for e in r["affected_elements"]):
            f.append(f"relation {r['genome_bit']}: affected_elements")
        if not all(isinstance(c, str) and re.match(r"^[0-9a-f]{64}$", c) for c in r["contexts"]):
            f.append(f"relation {r['genome_bit']}: contexts")
        if not all(isinstance(e, list) and len(e) == 2 and all(isinstance(x, int) and x >= 1 for x in e) for e in r["evidence"]):
            f.append(f"relation {r['genome_bit']}: evidence")
    for g in doc["groups"]:
        if not (isinstance(g, list) and g and all(isinstance(b, int) and b >= 0 for b in g)):
            f.append("groups")
    return f


# ------------------------------------------------------------------ controls
def derangement_attempts(seed_x: int, n: int = ELEMENTS) -> list[list[int]]:
    """B3's rule, every attempt kept: Fisher–Yates from i = n-1 down to 1 with j = rng.uniform(i + 1), each attempt
    from the identity, the generator continuing across attempts, until no fixed point. The rejected attempts are a
    generation procedure fixed in advance — never a choice made after seeing a map, a partition or a result — and
    they are recorded with the final one (the last of the list) so the rule is auditable."""
    rng = Rng(seed_x)
    attempts: list[list[int]] = []
    while True:
        p = list(range(n))
        for i in range(n - 1, 0, -1):
            j = rng.uniform(i + 1)
            p[i], p[j] = p[j], p[i]
        attempts.append(p)
        if all(p[i] != i for i in range(n)):
            return attempts


def derangement(seed_x: int, n: int = ELEMENTS) -> list[int]:
    """The derangement B3's rule yields: the last attempt of `derangement_attempts`."""
    return derangement_attempts(seed_x, n)[-1]


def relabel_genome(genome: int, perm: list[int]) -> int:
    """Control X-A: bit a of the genome moves to bit perm[a]. The TRUE genome is what the search observed and what
    the ledger keeps; the relabelled genome is the cartographer's input only, reconstructible from the fixed π."""
    if not isinstance(genome, int) or genome < 0 or genome >> len(perm):
        raise ValueError("the genome is not over the permutation's addresses")
    out = 0
    for a, pa in enumerate(perm):
        if (genome >> a) & 1:
            out |= 1 << pa
    return out


def isomorphic_addresses(x: ObservationCarto, shadow: ObservationCarto, perm: list[int]) -> list[str]:
    """X-A's shadow contract, EXACT and in full: X's relation at perm[a] equals the shadow's relation at a — the
    seen cells, the presence cells, the pair counts, the contexts, the evidence references — and the version, the
    multi-bit count and the specimen count agree. Any difference is named; a difference is a defect of the control
    (a control failure), never a result."""
    f: list[str] = []
    if x.n != shadow.n or len(perm) != shadow.n or sorted(perm) != list(range(shadow.n)):
        return ["the permutation is not over the cartographers' addresses"]
    if x.version != shadow.version:
        f.append(f"version {x.version} != shadow {shadow.version}")
    if x.multi_bit_pairs != shadow.multi_bit_pairs:
        f.append("multi-bit pair counts differ")
    if len(x.specimens) != len(shadow.specimens):
        f.append("specimen counts differ")
    for a in range(shadow.n):
        s, xr = shadow.rel[a], x.rel[perm[a]]
        if (xr.cells, xr.presence, xr.pairs_with_effect, xr.pairs_without_effect, xr.contexts, xr.evidence) != \
           (s.cells, s.presence, s.pairs_with_effect, s.pairs_without_effect, s.contexts, s.evidence):
            f.append(f"address {a} -> {perm[a]}: X's relation is not the shadow's under the relabelling")
    return f


def residual_structure(x_view: MapView, shadow_view: MapView) -> dict:
    """POST HOC, reported and never fed back: did the relabelling preserve the operator's partition? The TRUE
    partition is the shadow's groups; X's partition is its image under π. `groups_moved` counts the true groups
    that are not, as a set of addresses, a group of X's partition; `partition_preserved` is the two partitions being
    equal as sets of address sets. A derangement does not guarantee a changed partition (a within-group swap preserves
    it), so a preserved partition is a fact of the run, reported beside its numbers — never a reason to redraw."""
    true_groups = [frozenset(g) for g in shadow_view.groups]
    x_groups = {frozenset(g) for g in x_view.groups}
    moved = sum(1 for g in true_groups if g not in x_groups)
    return {"partition_preserved": set(true_groups) == x_groups, "groups_moved": moved, "groups_true": len(true_groups),
            "groups_x": len(x_groups), "true_groups": [sorted(g) for g in shadow_view.groups], "x_groups": [sorted(g) for g in x_view.groups]}


def permute_grid(q_grid: list, perm: list[int]) -> list:
    """The LANE permutation — lane i's readout appears at lane perm[i]. Kept as the cartographer's symmetry test (the
    relation / partition structure is invariant under lane relabelling); not an arm, not the negative control."""
    out = []
    for row in q_grid:
        new = [None] * len(row)
        for i, v in enumerate(row):
            new[perm[i]] = v
        out.append(new)
    return out


def isomorphic(x: ObservationCarto, shadow: ObservationCarto, perm: list[int]) -> list[str]:
    """The lane symmetry: a cartographer over lane-permuted grids equals the untransformed one with every element
    mapped through perm — version and multi-bit count included. EXACT; any difference named. A test of the
    cartographer, not the engine's control."""
    f: list[str] = []
    if x.version != shadow.version:
        f.append(f"version {x.version} != shadow {shadow.version}")
    if x.multi_bit_pairs != shadow.multi_bit_pairs:
        f.append("multi-bit pair counts differ")
    for a in range(shadow.n):
        s, xr = shadow.rel[a], x.rel[a]
        want_cells = {(st, perm[e]) for st, e in s.cells}
        want_presence = {(st, perm[e]) for st, e in s.presence}
        if (xr.cells, xr.presence, xr.pairs_with_effect, xr.pairs_without_effect, xr.contexts, xr.evidence) != \
           (want_cells, want_presence, s.pairs_with_effect, s.pairs_without_effect, s.contexts, s.evidence):
            f.append(f"address {a}: X's relation is not the shadow's under the permutation")
    return f


def address_only_view(addresses: tuple) -> MapView:
    """A0: what the address structure alone gives — addresses grouped by their frame (the far field)."""
    by_far: dict[str, list[int]] = {}
    for i, a in enumerate(addresses):
        by_far.setdefault(a.split("/")[0], []).append(i)
    groups = tuple(tuple(v) for _, v in sorted(by_far.items()))
    return MapView(groups, 0, sha256_json([list(g) for g in groups]), origin="address_only", provenance=("address_only",))


def shuffled_view(view: MapView, seed: int) -> MapView:
    """D: the view's addresses relabelled by a seeded permutation of the bits that appear in it — the group sizes
    kept, the membership wrong. The parent's provenance and privilege are KEPT: a shuffled oracle is still
    oracle-derived, never a learned, closed-book source (the owner's P1-2 on 2eae943)."""
    bits = sorted(b for g in view.groups for b in g)
    rng = Rng(seed)
    perm = rng.sample(bits, len(bits))
    relabel = dict(zip(bits, perm))
    groups = tuple(tuple(sorted(relabel[b] for b in g)) for g in view.groups)
    return MapView(groups, view.version, sha256_json([list(g) for g in groups]), privileged=view.privileged, origin="shuffled",
                   provenance=view.provenance + ("shuffled",), base_commitment=view.commitment)


def oracle_view(mapping) -> MapView:
    """Omega — PRIVILEGED: built from the certificate mapping (one group per element, one for the slice-wide bits),
    for the host's simulation bound only; never handed to an executing arm of the gate's R / F / O / X."""
    by: dict[str, list[int]] = {}
    for a, e in mapping.entries.items():
        by.setdefault(e.element or "slice", []).append(mapping.genome_bit(a))
    groups = tuple(tuple(sorted(by[k])) for k in sorted(by))
    return MapView(groups, 0, sha256_json([list(g) for g in groups]), privileged=True, origin="oracle", provenance=("oracle",))
