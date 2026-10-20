#!/usr/bin/env python3
"""B4 — the PROTOCOL IDENTITY (docs/b4_architecture.md section 9.5, DRAFT v0.2.0; the owner's choice 6 of 2026-10-20): the
machine identity of the execution / judgement METHOD, as a canonical document built from the tree's TRUSTED INVENTORY — never
from a digest an archive recorded of itself.

    payload = identity()                      # from the code tree: refused (IdentityRefusal) when a file is not its import-table digest
    sha = protocol_sha256(payload)            # over the payload WITHOUT the informational fields (the document's revision)
    f = compare(archived, rebuilt)            # the component-wise differences, the informational fields excluded from the equality

THE PAYLOAD covers the whole execution / judgement stack: the thresholds table's digest (the table WITHOUT its `source` text, so a
documentation revision does not move it); the task (version, planted rule, salt, the generator module); the K9 panel and the two
applicability rules; K10 (tau, salt); the seven copied statistics by per-function digest; the engine, the cartographer, the execution
boundary, the snapshot, the replay, the target setup; the summary stage (b4_sim), the judgement (b4_gate), the go / no-go policy, the
validators and verifiers (b4_sim_schema, b4_sim_verify, b4_gate_verify, b4_target); every record schema by version AND by the digest
of the validator module that implements it; the formal inputs (the hypothesis, the certificate, the exposure receipt); the labels;
and the COMPLETE tool-file inventory (every b4/host module and every b4/schemas file by digest, and the import table's entries for
exactly those files), so that no stage is left out — and nothing else: a change of a test file is not a change of the method.
`architecture_revision` is carried as PROVENANCE only: excluded from the digest and from the equality (choice 6).

NO SELF-REFERENCE: the payload holds the digests of source files; no file holds the payload's digest; the manifest that records the
payload is not part of it.

WHAT A VERIFIER DOES WITH IT (b4_sim_verify, b4_gate_verify): it rebuilds the payload from ITS OWN tree and compares it with the
archive's, component by component; equal → the archive is of this method version and the verification proceeds under this version's
schemas and methods; not equal, malformed or absent → a NAMED refusal that lists the differing components and points to
docs/b4_archive_reverification.md (re-verify with the archive's own tool at its recorded HEAD). No re-judgement of an old archive
under a new method, no partial verification, and no general version selector.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_carto as bc  # noqa: E402
import b4_engine as be  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_gate_stats as gs  # noqa: E402
import b4_k10 as k10  # noqa: E402
import b4_k9 as k9  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_thresholds as th  # noqa: E402

SCHEMA = ("b4_protocol_identity", "1.0.0")
INFORMATIONAL = ("architecture_revision",)                       # provenance: excluded from the digest and from the equality
IMPORT_REL = "b4/IMPORT.json"
HEX64 = lambda v: isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)  # noqa: E731
RECORD_SCHEMAS = {                                               # every record schema the method writes, by version and by the module that validates it
    "b4_sim_seeds": ("1.2.0", "b4/host/b4_seeds.py"), "b4_exposure_receipt": ("1.0.0", "b4/host/b4_seeds.py"), "b4_sim_init_failed": ("1.0.0", "b4/host/b4_seeds.py"),
    "b4_sim_manifest": ("1.2.0", "b4/host/b4_sim_schema.py"), "b4_sim_arm_result": ("1.0.0", "b4/host/b4_sim_schema.py"), "b4_sim_arm_audit": ("1.0.0", "b4/host/b4_sim_schema.py"),
    "b4_sim_quarantine": ("1.1.0", "b4/host/b4_sim_schema.py"), "b4_sim_controls": ("1.0.0", "b4/host/b4_sim_schema.py"), "b4_sim_k7": ("1.0.0", "b4/host/b4_sim_schema.py"),
    "b4_sim_k9": ("1.2.0", "b4/host/b4_sim_schema.py"), "b4_sim_k10": ("1.0.0", "b4/host/b4_sim_schema.py"), "b4_sim_curves": ("1.1.0", "b4/host/b4_sim_schema.py"),
    "b4_sim_pair_index": ("1.1.0", "b4/host/b4_sim_schema.py"), "b4_sim_stopped": ("1.2.0", "b4/host/b4_sim_schema.py"), "b4_sim_report": ("1.2.0", "b4/host/b4_sim_schema.py"),
    "b4_sim_task_setup": ("1.0.0", "b4/host/b4_sim_schema.py"), "b4_sim_target_observation": ("1.0.0", "b4/host/b4_sim_schema.py"), "b4_sim_task": ("1.0.0", "b4/host/b4_sim_schema.py"),
    "b4_gate_report": ("1.1.0", "b4/host/b4_gate.py"), "b4_gate_synthetic_summary": ("1.0.0", "b4/host/b4_gate.py"),
    "b4_gonogo_decision": ("1.0.0", "b4/host/b4_gonogo.py"), "b4_protocol_identity": ("1.0.0", "b4/host/b4_protocol.py"),
}
STACK = {"engine": "b4/host/b4_engine.py", "cartographer": "b4/host/b4_carto.py", "execution": "b4/host/b4_execution.py", "snapshot": "b4/host/b4_snapshot.py",
         "replay": "b4/host/b4_replay.py", "target_setup": "b4/host/b4_target.py", "controls": "b4/host/b4_controls.py", "observe": "b4/host/b4_observe.py",
         "deadline": "b4/host/b4_deadline.py", "seeds": "b4/host/b4_seeds.py", "summary": "b4/host/b4_sim.py", "judgement": "b4/host/b4_gate.py",
         "gonogo": "b4/host/b4_gonogo.py", "validators": "b4/host/b4_sim_schema.py", "archive_verifier": "b4/host/b4_sim_verify.py",
         "gate_verifier": "b4/host/b4_gate_verify.py", "identity": "b4/host/b4_protocol.py"}


class IdentityRefusal(ValueError):
    """The tree is not its own inventory (a file does not hash to its import-table digest, or the table is unreadable): no identity is built from it."""


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False)


def thresholds_sha256(table: dict | None = None) -> str:
    """The digest of the thresholds table WITHOUT its `source` text (the document reference carries the revision; a documentation-only
    revision must not move the method's identity)."""
    t = dict(th.THRESHOLDS if table is None else table)
    t.pop("source", None)
    return _sha(canonical(t).encode())


def inventory(code_root: Path = REPO_ROOT) -> dict:
    """Every tool file (b4/host/*.py and b4/schemas/*) by digest, each held to the import table's recorded digest: the trusted inventory.
    A file absent from the table, or hashing differently, is an IdentityRefusal."""
    code_root = Path(code_root)
    try:
        table = json.loads((code_root / IMPORT_REL).read_bytes())
    except (OSError, ValueError) as exc:
        raise IdentityRefusal(f"{IMPORT_REL} is unreadable: {type(exc).__name__}: {exc}") from None
    files = table.get("files") if isinstance(table, dict) else None
    if not isinstance(files, dict):
        raise IdentityRefusal(f"{IMPORT_REL} carries no file table")
    out: dict[str, str] = {}
    rels = sorted(str(p.relative_to(code_root)) for p in (code_root / "b4/host").glob("*.py")) + sorted(str(p.relative_to(code_root)) for p in (code_root / "b4/schemas").glob("*"))
    for rel in rels:
        got = _sha((code_root / rel).read_bytes())
        entry = files.get(rel)
        if not isinstance(entry, dict) or entry.get("sha256") != got:
            raise IdentityRefusal(f"{rel} is not the import table's: {'absent from the table' if entry is None else 'the digest differs'} — the tree is not its inventory")
        out[rel] = got
    return out


def identity(code_root: Path = REPO_ROOT) -> dict:
    """The payload, from the tree's trusted inventory and the modules' declared constants."""
    inv = inventory(code_root)
    table = json.loads((code_root / IMPORT_REL).read_bytes())
    stats_entry = table["files"].get("b4/host/b4_gate_stats.py", {})
    copied = stats_entry.get("copied_functions") or {}
    stats = {}
    for name in gs.COPIED:
        src = inspect.getsource(getattr(gs, name))
        got = _sha(src.encode())
        if copied.get(name) != got:
            raise IdentityRefusal(f"the copied statistic {name} is not the import table's")
        stats[name] = got
    payload = {
        "schema": SCHEMA[0], "schema_version": SCHEMA[1],
        "architecture_revision": th.ARCHITECTURE_REVISION,
        "thresholds_sha256": thresholds_sha256(),
        "task": {"version": bl.TASK_VERSION, "planted_rule": bl.PLANTED_RULE, "salt": bl.SALT_TARGET, "k_default": bl.K_DEFAULT, "k_holdout": bl.K_HOLDOUT, "level_steps": bl.LEVEL_STEPS,
                 "holdout_salt": bl.HOLDOUT_SALT, "n_bits": bl.N_BITS, "module_sha256": inv["b4/host/b4_landscape.py"]},
        "k9": {"panel_version": k9.PANEL_VERSION, "applicability_all_panel": k9.APPLICABILITY_ALL_PANEL, "applicability_conditional": k9.APPLICABILITY_CONDITIONAL,
               "judged": k9.JUDGED_ESTIMAND, "module_sha256": inv["b4/host/b4_k9.py"]},
        "k10": {"tau": k10.TAU, "salt": k10.SALT, "module_sha256": inv["b4/host/b4_k10.py"]},
        "statistics": stats,
        "engine": {"version": be.ENGINE_VERSION, "mu": be.MU, "lambda": be.LAMBDA, "kmax": be.KMAX, "arms": list(be.ARMS)},
        "cartographer": {"version": bc.CARTO_VERSION},
        "stack": {name: inv[rel] for name, rel in STACK.items()},
        "schemas": {name: {"version": v, "validator": rel, "validator_sha256": inv[rel]} for name, (v, rel) in RECORD_SCHEMAS.items()},
        "hypothesis_sha256": hy.HYPOTHESIS_SHA256, "certificate_sha256": bm.CERTIFICATE_SHA256, "exposure_receipt_sha256": bs.EXPOSURE_RECEIPT_SHA256,
        "labels": {"gate": th.THRESHOLDS["anchor"]["gate_label"], "exploration": th.THRESHOLDS["anchor"]["exploration_label"],
                   "retired": sorted(bs.RETIRED_LABELS), "consumed": sorted(bs.CONSUMED_LABELS)},
        "inventory": inv,
        "import_table_sha256": _sha(canonical({rel: table["files"][rel] for rel in inv}).encode()),   # the table's TOOL-FILE entries only: a test-only edit is not a new method version
    }
    return payload


def digest_view(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if k not in INFORMATIONAL}


def protocol_sha256(payload: dict) -> str:
    return _sha(canonical(digest_view(payload)).encode())


def identity_findings(doc) -> list[str]:
    """The shape of a recorded identity: total, never raises."""
    f: list[str] = []
    if not isinstance(doc, dict):
        return ["protocol identity: not an object"]
    want = {"schema", "schema_version", "architecture_revision", "thresholds_sha256", "task", "k9", "k10", "statistics", "engine", "cartographer", "stack", "schemas",
            "hypothesis_sha256", "certificate_sha256", "exposure_receipt_sha256", "labels", "inventory", "import_table_sha256"}
    if set(doc) != want:
        return [f"protocol identity: keys {sorted(set(doc) ^ want)} differ from the schema's"]
    if doc["schema"] != SCHEMA[0] or doc["schema_version"] != SCHEMA[1]:
        f.append("protocol identity: schema / schema_version")
    for k in ("thresholds_sha256", "hypothesis_sha256", "certificate_sha256", "exposure_receipt_sha256", "import_table_sha256"):
        if not HEX64(doc[k]):
            f.append(f"protocol identity: {k} is not a sha256")
    if not isinstance(doc["architecture_revision"], str):
        f.append("protocol identity: architecture_revision is not a string")
    for k in ("task", "k9", "k10", "statistics", "engine", "cartographer", "stack", "schemas", "labels", "inventory"):
        if not isinstance(doc[k], dict):
            f.append(f"protocol identity: {k} is not an object")
    if isinstance(doc["inventory"], dict) and not all(isinstance(p, str) and HEX64(s) for p, s in doc["inventory"].items()):
        f.append("protocol identity: inventory is not {path: sha256}")
    return f


def compare(archived, rebuilt: dict) -> list[str]:
    """The archived identity against the rebuilt one, component by component, the informational fields excluded. Empty = the same method
    version. Each finding names the component; a malformed archived identity is named as such."""
    f = identity_findings(archived)
    if f:
        return f
    diffs = []
    for k in sorted(set(digest_view(archived)) | set(digest_view(rebuilt))):
        a, b = archived.get(k), rebuilt.get(k)
        if canonical(a) != canonical(b):
            if isinstance(a, dict) and isinstance(b, dict):
                sub = sorted(x for x in set(a) | set(b) if canonical(a.get(x)) != canonical(b.get(x)))
                diffs.append(f"{k}: {', '.join(str(x) for x in sub[:8])}{' …' if len(sub) > 8 else ''}")
            else:
                diffs.append(k)
    if diffs:
        return [f"the archive's protocol identity is not this tool's: {'; '.join(diffs)} — re-verify the archive with its own tool at its recorded HEAD (docs/b4_archive_reverification.md)"]
    return []


def refusal_for_missing(manifest: dict) -> str:
    """The named refusal of an archive that carries no protocol identity (written before v0.2.0)."""
    head = manifest.get("head") if isinstance(manifest, dict) else None
    src = ((manifest.get("thresholds") or {}).get("source") if isinstance(manifest, dict) else None)
    return (f"the archive carries no protocol identity: written by a tool before the identity existed (its thresholds source {src!r}, HEAD {head!r}); "
            "it is not verified by this tool — re-verify it with its own tool at its recorded HEAD (docs/b4_archive_reverification.md)")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Print this tree's protocol identity and its digest (writes nothing).")
    ap.add_argument("--root", default=str(REPO_ROOT))
    a = ap.parse_args(argv)
    try:
        p = identity(Path(a.root))
    except IdentityRefusal as exc:
        print(json.dumps({"refused": str(exc)}, indent=1))
        return 2
    print(json.dumps({"protocol_sha256": protocol_sha256(p), "architecture_revision": p["architecture_revision"], "labels": p["labels"], "task": p["task"]["version"], "k9": p["k9"]["judged"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
