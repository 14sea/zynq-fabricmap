#!/usr/bin/env python3
"""Refresh b4/IMPORT.json for protocol v0.3.0 (the task-v0.3 revision unit; no new file under b4/): every existing entry's sha256 (and base / copied-function digests) recomputed from the tree;
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
NEW = {}   # v0.3.0 adds no file under b4/
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
T["stage"] = T["stage"].split(" | v0.3.0")[0] + " | v0.3.0 (the owner's ruling of 2026-10-27, after the carrier v2 finding of one CE / SR / CLK pin per slice): task-v0.3 — one slice-wide CE value (p = 1/2) and one slice-wide SR value (p = 1/4) per set step, independent, broadcast as 0xFF / 0x00 in the common 8-bit grammar, d per element; the shape held by b4_landscape.stimulus_findings in the task validators and the reconstruction; the stimulus rule in the protocol identity; b4-sim-4 consumed, b4-sim-5 reserved; the go / no-go row of b4-sim-5 with p_max_go (the same 0.20, a cost threshold, not an alpha); no model, hypothesis, certificate, operator, statistic, panel, applicability or K-number changed; every digest refreshed"
(R / "b4/IMPORT.json").write_text(json.dumps(T, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
print(json.dumps({"changed": changed, "untabled": untabled, "entries": len(T["files"])}, indent=1))
