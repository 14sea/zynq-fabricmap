#!/usr/bin/env python3
"""B3 lifecycle 1 — the online-map document and its verifier (docs/b3_architecture.md v0.2.3 §8 item 6).

`render` writes an `online_map` 1.0.0 document from a finished O-arm run; `findings` checks it against
the schema (fail-closed: no validator, no pass), for internal consistency and against its ledger digest;
`accuracy` scores it, host-only and after the fact, against the B1 truth mapping (the certificate). This
is deliberately NOT B1's map-lifecycle verifier (`host/verify_local_map.py`): the online map has no code
probes, no interaction edges and no confirmations, and passing that verifier is neither required nor
claimed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b3_carto as carto_mod  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "b3/schemas/online_map.schema.json"
SCHEMA, SCHEMA_VERSION = "online_map", "1.0.0"


def canonical_sha256(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def render(carto: carto_mod.SpecimenCarto, binding: dict, ledger: list[dict]) -> dict:
    return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "carto_version": carto_mod.CARTO_VERSION,
            "binding": {k: binding[k] for k in ("landscape_seed", "operator_seed", "fitness", "budget")},
            "map_version": carto.version, "anomalies": carto.anomalies, "decoded_count": len(carto.decoded),
            "ledger_entries": len(ledger), "ledger_sha256": canonical_sha256(ledger),
            "entries": carto.decoded_entries()}


def findings(doc, ledger: list[dict] | None = None) -> list[str]:
    """Every way the document is not a valid, internally consistent online map. Type before use;
    the schema check is fail-closed (an absent validator is a finding, not a pass)."""
    f: list[str] = []
    if not isinstance(doc, dict):
        return [f"the document is {type(doc).__name__}, not a JSON object"]
    try:
        import jsonschema
        schema = json.loads(SCHEMA_PATH.read_text())
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        f += [f"schema: {e.json_path}: {e.message}" for e in cls(schema).iter_errors(doc)]
    except ImportError:
        f.append("schema: jsonschema is not importable — the document cannot be validated (no pass without it)")
    if f:
        return f
    entries = doc["entries"]
    bits = [e["genome_bit"] for e in entries]
    if bits != sorted(set(bits)):
        f.append("entries are not sorted by genome_bit without repeats")
    positions = [(e["relation"]["lut_index"], e["relation"]["init_index"]) for e in entries]
    if len(set(positions)) != len(positions):
        f.append("a position is decoded for two addresses")
    if doc["decoded_count"] != len(entries):
        f.append(f"decoded_count {doc['decoded_count']} is not the {len(entries)} entries")
    if doc["map_version"] < 1 and entries:
        f.append("entries without a map version")
    if ledger is not None:
        if doc["ledger_entries"] != len(ledger):
            f.append(f"ledger_entries {doc['ledger_entries']} is not the ledger's {len(ledger)}")
        if doc["ledger_sha256"] != canonical_sha256(ledger):
            f.append("ledger_sha256 is not the ledger's digest")
        if ledger and (doc["map_version"] != ledger[-1]["map_version_after"] or doc["anomalies"] != ledger[-1]["anomalies"]):
            f.append("map_version / anomalies are not the ledger's final values")
    return f


def accuracy(doc: dict, truth: dict) -> dict:
    """Host-only, after the fact: the decoded relations against the certificate's mapping."""
    wrong = [e for e in doc["entries"] if tuple(truth["mapping"][e["genome_bit"]]) != (e["relation"]["lut_index"], e["relation"]["init_index"])]
    n = len(doc["entries"])
    return {"decoded": n, "wrong": len(wrong), "correct": n - len(wrong), "coverage": n / bc.N,
            "wrong_entries": [e["genome_bit"] for e in wrong], "universe": bc.N}
