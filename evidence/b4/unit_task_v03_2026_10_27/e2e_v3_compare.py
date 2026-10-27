#!/usr/bin/env python3
"""Compare two records of e2e_v3_fixtures.py by their NORMALISED digests (the rule is in that driver's docstring): every case, every
directory, every file — equal, different or missing — and exit 1 on any difference. Two forms:

    python3 -B e2e_v2_compare.py <run A dir> <run B dir>            # every case/record.json of A against B (the fresh-root repeat)
    python3 -B e2e_v2_compare.py --files <record A> <record B> <dir> # one directory of two record.json files (e.g. the semantic tamper)

A markdown rendering (normalised digest null) is skipped and listed. The raw digests are NOT expected to match across roots / times (they carry the dependency chain of the volatile fields); they are
validated against the live files by the driver (`raw_links`) and by the fresh-process verifiers at generation time."""
import json, sys
from pathlib import Path


def compare_dir(a: dict, b: dict) -> dict:
    out = {"comparable": 0, "equal": 0, "different": [], "missing_in_b": [], "extra_in_b": [], "renderings_skipped": []}
    for rel, e in a.items():
        t = b.get(rel)
        if t is None:
            out["missing_in_b"].append(rel); continue
        if e["normalised_sha256"] is None or t["normalised_sha256"] is None:
            out["renderings_skipped"].append(rel); continue          # a markdown rendering: the verifier holds it to its JSON; the JSON is compared
        out["comparable"] += 1
        if e["normalised_sha256"] == t["normalised_sha256"]:
            out["equal"] += 1
        else:
            out["different"].append(rel)
    out["extra_in_b"] = sorted(set(b) - set(a))
    return out


def main(argv) -> int:
    if argv[:1] == ["--files"]:
        ra, rb, d = json.loads(Path(argv[1]).read_text()), json.loads(Path(argv[2]).read_text()), argv[3]
        res = {d: compare_dir(ra["digests"][d], rb["digests"][d])}
    else:
        A, B = Path(argv[0]), Path(argv[1])
        res = {}
        for p in sorted(A.glob("*/record.json")):
            q = B / p.relative_to(A)
            if not q.exists():
                res[p.parent.name] = {"error": "missing record in B"}; continue
            ra, rb = json.loads(p.read_text()), json.loads(q.read_text())
            if "digests" not in ra:                 # the semantic-tamper record carries original / tampered, compared with --files
                continue
            for d, files in ra["digests"].items():
                res[f"{p.parent.name}/{d}"] = compare_dir(files, rb["digests"].get(d, {}))
    total = {"comparable": sum(v.get("comparable", 0) for v in res.values()), "equal": sum(v.get("equal", 0) for v in res.values()),
             "different": sum(len(v.get("different", [])) for v in res.values()), "missing": sum(len(v.get("missing_in_b", [])) + len(v.get("extra_in_b", [])) for v in res.values()) + sum("error" in v for v in res.values())}
    print(json.dumps({"per_directory": res, "total": total, "pass": total["different"] == 0 and total["missing"] == 0 and total["comparable"] > 0}, indent=1))
    return 0 if total["different"] == 0 and total["missing"] == 0 and total["comparable"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
