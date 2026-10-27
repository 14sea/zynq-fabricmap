#!/usr/bin/env python3
"""B4Q — the EXPLICIT SCHEMA FILES of the B4 observation records (docs/b4_observation_contract.md 4.4, the owner's
provisional names) and a small, closed JSON-Schema-subset validator for them. The files live under b4q/schemas/ (the
frozen b4/schemas is untouched); each is a JSON Schema (draft 2020-12 vocabulary, the subset below) written from the
contract's 4.2 field sets and held, by tests/test_b4q_schema.py, to the code validators of host/b4carrier_records.py on
every record of the session evidence and of the bench — the schema files are the reviewable artefact, the code validator
stays the authority (contract 4.3; a disagreement is a finding against the file).

  ff_observation_carrier_v1     O, complete and invalid (the invalid variant's phase-dependent sets as oneOf)
  ff_fitness_v1                 F
  ff_transaction_close_v1       X, closed / injection_open / faulted
  ff_session_open_v1            the session-opening record
  ff_observation_model_raw_v1   the legacy raw model trace as observe() writes it (3.2 M-raw): null cells allowed
  ff_observation_view_v1        the logical view of 3.1 (host/b4q_view.py builds it; never written by a source)

The subset: type, enum, const, properties, required, additionalProperties (false), items, minItems, maxItems, pattern,
minimum, maximum, oneOf, allOf, $ref to #/$defs. Nothing else is interpreted; an unknown keyword in a file is a refusal."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
SCHEMAS = R / "b4q/schemas"
KNOWN = {"$schema", "$id", "title", "description", "type", "enum", "const", "properties", "required", "additionalProperties", "items", "minItems", "maxItems",
         "pattern", "minimum", "maximum", "oneOf", "allOf", "$ref", "$defs", "x-contract", "propertyNames", "minProperties", "maxProperties"}
NAMES = ("ff_observation_carrier_v1", "ff_fitness_v1", "ff_transaction_close_v1", "ff_session_open_v1", "ff_observation_model_raw_v1", "ff_observation_view_v1")


class SchemaRefusal(ValueError):
    pass


def load(name: str) -> dict:
    doc = json.loads((SCHEMAS / f"{name}.schema.json").read_text())
    _check_keywords(doc, name)
    return doc


def _check_keywords(node, where):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("properties", "$defs"):
                for kk, vv in v.items():
                    _check_keywords(vv, f"{where}.{k}.{kk}")
            elif k in ("oneOf", "allOf"):
                for i, vv in enumerate(v):
                    _check_keywords(vv, f"{where}.{k}[{i}]")
            elif k == "items" or (k in ("additionalProperties", "propertyNames") and isinstance(v, dict)):
                _check_keywords(v, f"{where}.{k}")
            elif k not in KNOWN:
                raise SchemaRefusal(f"{where}: unknown keyword {k!r} — the subset validator does not interpret it")


def _type_ok(v, t) -> bool:
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "null":
        return v is None
    raise SchemaRefusal(f"type {t!r}")


def validate(doc, schema: dict, root: dict | None = None, where: str = "$") -> list[str]:
    """The findings (empty = valid)."""
    root = root if root is not None else schema
    f: list[str] = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise SchemaRefusal(f"$ref {ref!r}")
        return validate(doc, root["$defs"][ref[len("#/$defs/"):]], root, where)
    if "allOf" in schema:
        for s in schema["allOf"]:
            f += validate(doc, s, root, where)
    if "oneOf" in schema:
        oks = [i for i, s in enumerate(schema["oneOf"]) if not validate(doc, s, root, where)]
        if len(oks) != 1:
            f.append(f"{where}: matches {len(oks)} of the oneOf variants, not exactly one")
    if "type" in schema:
        ts = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(doc, t) for t in ts):
            return f + [f"{where}: not of type {schema['type']}"]
    if "enum" in schema and doc not in schema["enum"]:
        f.append(f"{where}: {doc!r} not in the enum")
    if "const" in schema and doc != schema["const"]:
        f.append(f"{where}: {doc!r} is not the constant {schema['const']!r}")
    if isinstance(doc, str) and "pattern" in schema and not re.fullmatch(schema["pattern"], doc):
        f.append(f"{where}: does not match {schema['pattern']!r}")
    if isinstance(doc, (int, float)) and not isinstance(doc, bool):
        if "minimum" in schema and doc < schema["minimum"]:
            f.append(f"{where}: below the minimum {schema['minimum']}")
        if "maximum" in schema and doc > schema["maximum"]:
            f.append(f"{where}: above the maximum {schema['maximum']}")
    if isinstance(doc, list):
        if "minItems" in schema and len(doc) < schema["minItems"]:
            f.append(f"{where}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(doc) > schema["maxItems"]:
            f.append(f"{where}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, v in enumerate(doc):
                f += validate(v, schema["items"], root, f"{where}[{i}]")
    if isinstance(doc, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in doc:
                f.append(f"{where}: missing {k!r}")
        ap = schema.get("additionalProperties")
        if ap is False:
            extra = sorted(set(doc) - set(props))
            if extra:
                f.append(f"{where}: extra keys {extra}")
        if "minProperties" in schema and len(doc) < schema["minProperties"]:
            f.append(f"{where}: fewer than {schema['minProperties']} properties")
        if "maxProperties" in schema and len(doc) > schema["maxProperties"]:
            f.append(f"{where}: more than {schema['maxProperties']} properties")
        for k, v in doc.items():
            if "propertyNames" in schema:
                f += validate(k, schema["propertyNames"], root, f"{where}.<{k}>")
            if k in props:
                f += validate(v, props[k], root, f"{where}.{k}")
            elif isinstance(ap, dict):
                f += validate(v, ap, root, f"{where}.{k}")
    return f


def validate_named(doc, name: str) -> list[str]:
    return validate(doc, load(name))


def main(argv=None) -> int:
    name, path = (argv or sys.argv[1:])[:2]
    f = validate_named(json.loads(Path(path).read_text()), name)
    print("\n".join(f) if f else "valid")
    return 0 if not f else 1


if __name__ == "__main__":
    sys.exit(main())
