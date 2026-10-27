#!/usr/bin/env python3
"""Refresh b4/IMPORT.json for protocol v0.2.0: every existing entry's sha256 (and base / copied-function digests) recomputed from the tree;
new files added with their notes; the table's stage text updated. Prints what changed. Run from the repository root."""
import hashlib, inspect, json, pathlib, sys
R = pathlib.Path(__file__).resolve()
for cand in (pathlib.Path.cwd(), *pathlib.Path.cwd().parents):
    if (cand / "b4/IMPORT.json").is_file():
        R = cand; break
else:
    raise SystemExit("run from inside the repository")
sys.path.insert(0, str(R / "b4/host"))
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
T = json.loads((R / "b4/IMPORT.json").read_text())
NEW = {
    "b4/host/b4_target.py": {"kind": "new", "role": "host", "note": "protocol v0.2.0 (the owner's rulings of 2026-10-20, choices 2-3 and the target-setup contract): the per-pair target setup of task-v0.2 — the private plan (seeds, the planted flip-flop genome by the fixed rule, the stimulus digests) persisted before the first target call, each setup observation of the planted configuration through the execution port saved on return, the PublicTask (no seed, no planted genome, no private record) and task.json last; the offline reconstruction (setup_findings) from the kept records, the fabric never asked again."},
    "b4/host/b4_protocol.py": {"kind": "new", "role": "host", "note": "protocol v0.2.0 (choice 6): the machine identity of the execution / judgement method, built from the tree's trusted inventory (every tool file held to this table's digest, the copied statistics by per-function digest, the thresholds table's digest without its source text, the task / K9 / K10 constants, the engine, every record schema by version and validator digest, the formal inputs, the labels); the document's revision carried as provenance and excluded from the digest and the equality; compare() names the differing components; an archive of another version is refused by name."},
    "b4/host/b4_gonogo.py": {"kind": "new", "role": "host", "note": "protocol v0.2.0 (choice 5): the engineering go / no-go policy of section 9.4 applied to an exploration archive — S = 32, B_go = 64, the one-sided exact sign test on Omega - R with positives > negatives and p <= 0.20, the seven judged conditional K9 medians >= 0.50, every planned pair complete else no decision; a cost policy record with its own validator, verifier and markdown; never a gate verdict or an authorisation."},
    "b4/tests/test_b4_target.py": {"kind": "new", "role": "test"}, "b4/tests/test_b4_protocol.py": {"kind": "new", "role": "test"}, "b4/tests/test_b4_gonogo.py": {"kind": "new", "role": "test"},
    "b4/architecture_revision.json": {"kind": "new", "role": "provenance", "note": "the owner's review of 04385ae, R1: the architecture document's revision the tool tree was written against — PROVENANCE outside the identity's inventory (not a tool file), read by b4_thresholds.ARCHITECTURE_REVISION and held to the document's first line by the static pin test; a documentation-only revision changes this file and the document, never a tool file, and the method's identity does not move. Listed here like every file under b4/; not in the identity's import_table_sha256 projection."},
}
changed = []
for rel, e in NEW.items():
    if (R / rel).is_file() and rel not in T["files"]:
        T["files"][rel] = dict(e, sha256=sha(R / rel)); changed.append(("added", rel))
for rel, e in T["files"].items():
    p = R / rel
    if not p.is_file():
        changed.append(("MISSING", rel)); continue
    got = sha(p)
    if e.get("sha256") != got:
        e["sha256"] = got; changed.append(("digest", rel))
    if "base" in e:
        bgot = sha(R / e["base"])
        if e.get("base_sha256") != bgot:
            e["base_sha256"] = bgot; changed.append(("base", rel))
    if "copied_functions" in e:
        import b4_gate_stats as gs
        for n in list(e["copied_functions"]):
            d = hashlib.sha256(inspect.getsource(getattr(gs, n)).encode()).hexdigest()
            if e["copied_functions"][n] != d:
                e["copied_functions"][n] = d; changed.append(("function", f"{rel}.{n}"))
tracked = [str(p.relative_to(R)) for p in (R / "b4").rglob("*") if p.is_file() and "__pycache__" not in str(p) and p.name != "IMPORT.json"]
untabled = sorted(t for t in tracked if t not in T["files"])
T["stage"] = T["stage"].split(" | v0.2.0")[0] + " | v0.2.0 (the owner's rulings of 2026-10-20): task-v0.2 with the planted flip-flop target and the PublicTask / PrivateTask boundary (b4_target), K9's two applicabilities with (b') judged, the protocol identity (b4_protocol), the go / no-go policy (b4_gonogo), the consumed labels b4-sim-3 / b4-gate-1, the next labels b4-sim-4 / b4-gate-2; every digest refreshed"
(R / "b4/IMPORT.json").write_text(json.dumps(T, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
print(json.dumps({"changed": changed, "untabled": untabled, "entries": len(T["files"])}, indent=1))
