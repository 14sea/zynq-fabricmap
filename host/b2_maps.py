#!/usr/bin/env python3
"""B2 — the map as the operator sees it, and the control renderings
(docs/b2_architecture.md §5).

The operator's whole view of a map is `MapView`: for each train column (INIT index) the
genome bits the map places there, taken from `self_map` 2.0.0 entries in state decoded /
confirmed via `relation.init_index` — and nothing else (no LUT key, no certificate, no
target). LUT membership is read here only to build the within-LUT-shuffled control (E),
which is a host rendering of a document, not something the operator consults.

Renderings (all return a self_map 2.0.0 document, schema-validated when a validator is
present):
  * self_map    — the B1 board-authored map, as committed;
  * oracle      — the certificate's mapping in the same schema (host-made; the bound);
  * shuffled    — the relations permuted across all entries (seeded);
  * lut_shuffled — init_index permuted within each LUT (LUT membership kept);
  * degraded(q) — a fraction q of entries reset to unknown (seeded);
  * none        — no map (the random-safe endpoint, q = 1).
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402

SELF_MAP = REPO_ROOT / "evidence/b1/b1_17A6_2026-09-08-02/self_map_v2.json"
SCHEMA = REPO_ROOT / "schemas/self_map_v2.schema.json"
CLAIM_STATES = ("decoded", "confirmed")


def sha256_of(doc: dict) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def schema_findings(doc: dict, schema_path: Path = SCHEMA) -> list[str]:
    schema = json.loads(schema_path.read_text())
    try:
        import jsonschema
    except ImportError:
        return ["self_map_v2: no JSON-schema validator available (python3-jsonschema): the map is unvalidated"]
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return [f"self_map_v2: {e.json_path}: {e.message}" for e in sorted(cls(schema).iter_errors(doc), key=lambda e: str(e.json_path))]


def load_self_map(path: Path = SELF_MAP) -> dict:
    doc = json.loads(path.read_text())
    f = schema_findings(doc)
    if f:
        raise ValueError("; ".join(f))
    return doc


def oracle_map(truth: dict | None = None) -> dict:
    """The certificate rendered as a self_map 2.0.0 document (host-made; binding zero)."""
    truth = truth or bm.truth_mapping()
    entries = []
    for i, (far, w, b) in enumerate(truth["addresses"]):
        k, v = truth["mapping"][i]
        entries.append({"genome_bit": i, "address": f"{far:#010x}/{w}/{b}",
                        "relation": {"kind": "lut_init", "lut_index": k, "init_index": v},
                        "confidence": 2, "state": "confirmed", "observed_transition": {"base": 0, "set": 1},
                        "evidence": {"code_probe_seqs": [1], "confirm_seq": 1}})
    doc = {"schema": "self_map", "schema_version": "2.0.0", "cartographer": "oracle-from-certificate",
           "binding": {"token": "00" * 16, "universe_sha256": "00" * 32, "image_sha256_lo32": "00000000"},
           "seed": 0, "budget": 1, "anomalies": 0, "code_probe_seqs": [1] * 9,
           "universe": {"addresses": bc.N, "class": "clb_lut_init", "safety_class": "content"},
           "entries": entries, "interaction_edges": []}
    f = schema_findings(doc)
    if f:
        raise ValueError("; ".join(f))
    return doc


def _claims(doc: dict) -> list[dict]:
    return [e for e in doc["entries"] if e["state"] in CLAIM_STATES and e["relation"]]


def shuffled_map(doc: dict, seed: int) -> dict:
    """Relations permuted across all claiming entries by a seeded permutation."""
    out = copy.deepcopy(doc)
    out["cartographer"] = f"{doc['cartographer']}+shuffled:{seed}"
    claims = _claims(out)
    rels = [copy.deepcopy(e["relation"]) for e in claims]
    random.Random(f"shuffled:{seed}").shuffle(rels)
    for e, r in zip(claims, rels):
        e["relation"] = r
    return out


def lut_shuffled_map(doc: dict, seed: int) -> dict:
    """init_index permuted within each LUT (LUT membership kept, column identity destroyed)."""
    out = copy.deepcopy(doc)
    out["cartographer"] = f"{doc['cartographer']}+lut_shuffled:{seed}"
    rng = random.Random(f"lut_shuffled:{seed}")
    by_lut: dict[int, list[dict]] = {}
    for e in _claims(out):
        by_lut.setdefault(e["relation"]["lut_index"], []).append(e)
    for k in sorted(by_lut):
        idx = [e["relation"]["init_index"] for e in by_lut[k]]
        rng.shuffle(idx)
        for e, v in zip(by_lut[k], idx):
            e["relation"]["init_index"] = v
    return out


def degraded_map(doc: dict, q: float, seed: int) -> dict:
    """A fraction q of the claiming entries reset to unknown (relation null)."""
    out = copy.deepcopy(doc)
    out["cartographer"] = f"{doc['cartographer']}+degraded:{q}:{seed}"
    claims = _claims(out)
    n = int(round(q * len(claims)))
    for e in random.Random(f"degraded:{q}:{seed}").sample(claims, n):
        e["relation"] = None
        e["state"] = "unknown"
        e["confidence"] = 0
        e["observed_transition"] = None
        e["evidence"] = {"code_probe_seqs": [], "confirm_seq": None}
    return out


def no_map() -> dict | None:
    return None


class MapView:
    """What the operator consults: train column -> sorted genome bits the map places there."""

    def __init__(self, doc: dict | None, train_vectors: list[int]):
        self.doc = doc
        self.sha256 = sha256_of(doc) if doc else None
        self.columns: dict[int, list[int]] = {}
        if doc is not None:
            f = schema_findings(doc)
            if f:
                raise ValueError("; ".join(f))
            train = set(train_vectors)
            for e in doc["entries"]:
                if e["state"] in CLAIM_STATES and e["relation"] and e["relation"]["init_index"] in train:
                    self.columns.setdefault(e["relation"]["init_index"], []).append(e["genome_bit"])
            for v in self.columns:
                self.columns[v].sort()
        self.column_keys = sorted(self.columns)      # the operator's draw list, in a fixed order

    def mapped_bits(self) -> int:
        return sum(len(b) for b in self.columns.values())

    def describe(self) -> dict:
        return {"map_sha256": self.sha256, "cartographer": self.doc["cartographer"] if self.doc else None,
                "train_columns_named": len(self.column_keys), "mapped_bits_in_train": self.mapped_bits()}


def relations_equal(a: dict, b: dict) -> tuple[int, int]:
    """(entries whose relation agrees, entries compared) between two documents by genome bit."""
    ra = {e["genome_bit"]: (e["relation"]["lut_index"], e["relation"]["init_index"]) for e in _claims(a)}
    rb = {e["genome_bit"]: (e["relation"]["lut_index"], e["relation"]["init_index"]) for e in _claims(b)}
    keys = set(ra) | set(rb)
    return sum(1 for k in keys if ra.get(k) == rb.get(k)), len(keys)
