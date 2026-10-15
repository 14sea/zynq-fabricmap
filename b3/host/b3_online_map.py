#!/usr/bin/env python3
"""B3 lifecycle 1 — the online-map document and its verifier (docs/b3_architecture.md v0.2.3 §8 item 6).

`render` writes an `online_map` 1.0.0 document from a finished O-arm run; `verify(doc, ledger, truth)` is
THE verification boundary — all three inputs required; schema, shape, cartographer version, ledger
binding (count = budget, digest, final version / anomalies), the anomaly count and every decode against
the B1 truth mapping decide the verdict together; `schema_findings` is the schema-and-shape helper only
and proves nothing by itself; `accuracy` is the scoring `verify` uses (host-only, after the fact). This
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
import b2_landscape as bl  # noqa: E402
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


def _schema_name() -> str:
    try:
        return str(SCHEMA_PATH.relative_to(REPO_ROOT))
    except ValueError:                      # a schema path outside the repository (tests point it at a temp file)
        return str(SCHEMA_PATH)


def schema_findings(doc) -> list[str]:
    """The SCHEMA AND SHAPE helper only — every way `doc` is not a well-formed, internally consistent
    online-map document. It is not the verifier: an empty list here proves nothing about the ledger
    the map was built from, the cartographer version or the decodes' truth. Fail-closed on its own
    inputs: an absent, unreadable, broken or invalid schema file, or an absent validator, is a named
    finding, never a pass and never a traceback; anything else is an internal error and propagates."""
    f: list[str] = []
    if not isinstance(doc, dict):
        return [f"the document is {type(doc).__name__}, not a JSON object"]
    try:
        import jsonschema
    except ImportError:
        return ["schema: jsonschema is not importable — the document cannot be validated (no pass without it)"]
    try:
        text = SCHEMA_PATH.read_text()
    except OSError as exc:
        return [f"schema: {_schema_name()} cannot be read: {exc.__class__.__name__}"]
    try:
        schema = json.loads(text)
    except ValueError as exc:
        return [f"schema: {_schema_name()} is not JSON: {exc}"]
    try:
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        f += [f"schema: {e.json_path}: {e.message}" for e in cls(schema).iter_errors(doc)]
    except jsonschema.exceptions.SchemaError as exc:
        return [f"schema: {_schema_name()} is not a valid JSON Schema: {exc.message}"]
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
    return f


def verify(doc, ledger, truth) -> dict:
    """THE production verification boundary (docs/b3_architecture.md v0.2.3 §8 item 6; the
    preregistration's decode-audit row). All three inputs are required and are checked type before
    use; the verdict is the conjunction of: the schema and shape (`schema_findings`); the
    cartographer version; the ledger binding (one entry per search evaluation — `ledger_entries` =
    `binding.budget` = the ledger's length —, the ledger digest, the final map version and anomaly
    count); the anomaly count itself (the prediction is 0; a nonzero count is a finding the
    adjudicator classifies, never a silent number); the truth mapping's own shape for every address
    the document names (`truth_findings`); and every decode against the truth mapping (each wrong
    decode is a finding). Returns {"ok", "findings", "accuracy"}: ok iff findings is
    empty. There is no optional input and no separate verdict-free accuracy path."""
    f: list[str] = []
    if not isinstance(ledger, list):
        f.append(f"ledger: {type(ledger).__name__}, not a list — the map cannot be verified without the ledger it was built from")
    if not isinstance(truth, dict) or not isinstance(truth.get("mapping"), dict):
        f.append("truth: not a truth mapping — the decodes cannot be audited")
    f += schema_findings(doc)
    if f:
        return {"ok": False, "findings": f, "accuracy": None}
    f += truth_findings(truth, [e["genome_bit"] for e in doc["entries"]])
    if f:
        return {"ok": False, "findings": f, "accuracy": None}
    if doc["carto_version"] != carto_mod.CARTO_VERSION:
        f.append(f"carto_version {doc['carto_version']!r} is not {carto_mod.CARTO_VERSION!r}")
    budget = doc["binding"]["budget"]
    if doc["ledger_entries"] != len(ledger):
        f.append(f"ledger_entries {doc['ledger_entries']} is not the ledger's {len(ledger)}")
    if len(ledger) != budget:
        f.append(f"the ledger has {len(ledger)} entries for a budget of {budget} (one entry per search evaluation)")
    if doc["ledger_sha256"] != canonical_sha256(ledger):
        f.append("ledger_sha256 is not the ledger's digest")
    if ledger:
        last = ledger[-1]
        if not isinstance(last, dict) or "map_version_after" not in last or "anomalies" not in last:
            f.append("the ledger's last entry carries no map_version_after / anomalies")
        elif doc["map_version"] != last["map_version_after"] or doc["anomalies"] != last["anomalies"]:
            f.append(f"map_version / anomalies {doc['map_version']} / {doc['anomalies']} are not the ledger's final {last['map_version_after']} / {last['anomalies']}")
    elif doc["map_version"] != 0 or doc["anomalies"] != 0 or doc["entries"]:
        f.append("an empty ledger cannot have produced a map")
    if doc["anomalies"] != 0:
        f.append(f"anomalies {doc['anomalies']} (the predicted count is 0)")
    acc = accuracy(doc, truth)
    for gb in acc["wrong_entries"]:
        e = next(x for x in doc["entries"] if x["genome_bit"] == gb)
        f.append(f"wrong decode: address {gb} at ({e['relation']['lut_index']}, {e['relation']['init_index']}), the truth is {tuple(truth['mapping'][gb])}")
    return {"ok": not f, "findings": f, "accuracy": acc}


TRUTH_FINDINGS_MAX = 5


def truth_findings(truth: dict, addresses: list[int]) -> list[str]:
    """The truth mapping's shape, before any use: every address the document names must be present,
    and every relation used must be exactly two integers, LUT 0..5 and vector 0..63 (a bool is not
    an int here). Named findings, never a KeyError / TypeError inside the audit. The first
    TRUTH_FINDINGS_MAX findings are kept verbatim; on the first one beyond them a single suppression
    marker is appended and the scan stops — the same rule for a missing address and for a
    malformed relation."""
    f: list[str] = []
    mapping = truth["mapping"]

    def add(what: str) -> bool:
        """Append; return False when the scan must stop."""
        if len(f) < TRUTH_FINDINGS_MAX:
            f.append(what)
            return True
        f.append(f"truth: … (further truth findings suppressed after {TRUTH_FINDINGS_MAX})")
        return False

    for i in addresses:
        if i not in mapping:
            if not add(f"truth: address {i} has no relation in the truth mapping"):
                break
            continue
        rel = mapping[i]
        ok = isinstance(rel, (tuple, list)) and len(rel) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in rel) \
            and 0 <= rel[0] < bl.LUTS and 0 <= rel[1] < bl.VECTORS
        if not ok and not add(f"truth: address {i} has a malformed relation {rel!r} (want (lut 0..5, vector 0..63))"):
            break
    return f


def accuracy(doc: dict, truth: dict) -> dict:
    """Host-only, after the fact: the decoded relations against the certificate's mapping."""
    wrong = [e for e in doc["entries"] if tuple(truth["mapping"][e["genome_bit"]]) != (e["relation"]["lut_index"], e["relation"]["init_index"])]
    n = len(doc["entries"])
    return {"decoded": n, "wrong": len(wrong), "correct": n - len(wrong), "coverage": n / bc.N,
            "wrong_entries": [e["genome_bit"] for e in wrong], "universe": bc.N}
