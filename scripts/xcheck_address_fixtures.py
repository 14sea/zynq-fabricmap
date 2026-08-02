#!/usr/bin/env python3
"""Producer-side independent cross-check of the author's address fixtures.

`host/verify_address_fixtures.py` (author-owned) checks the fixtures with the
author's implementation of the arithmetic.  This script checks the same fixtures
with the *producer's* implementation, written from `docs/freeze_format.md` §5 and
the frozen data without reading the author's verifier.  Two independent
implementations agreeing is the evidence; one implementation agreeing with itself
is not, which is why both live in the repo and both are run.

It also re-derives, from `tilegrid.json` rather than from the fixture: the block
record (`baseaddr`/`frames`/`offset`/`words`), the site -> `SLICE[LM]_X{0,1}` prefix
mapping (§5.5), the complete ordered segbits rule for each feature, the bit-less
assertion for a ppip, and the mask-token coordinate.  A case whose `kind` it does
not recognise is reported as uncovered rather than silently skipped — an earlier
draft of this script matched the mask token under the wrong key and passed
vacuously.

    scripts/xcheck_address_fixtures.py      # exits non-zero on any disagreement
"""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
D = REPO / "data/prjxray"
grid = json.loads((D / "zynq7/xc7z010/tilegrid.json").read_text())
fx = json.loads((REPO / "tests/fixtures/address_known_answers.json").read_text())

def rule(dbrel, feature):
    for line in (D / dbrel).read_text().splitlines():
        t = line.split()
        if t and t[0] == feature:
            return t[1:]
    return None

def mask_bits(dbrel):
    return {l.split()[1] for l in (D / dbrel).read_text().splitlines() if l.startswith("bit ")}

problems, checked = [], 0
for c in fx["cases"]:
    cid, kind = c["id"], c.get("kind")
    tile = c.get("tile")
    blk = (grid[tile]["bits"]["CLB_IO_CLK"] if tile else None)

    if blk and "expected_block" in c:
        for k, v in c["expected_block"].items():
            got = blk[k]
            if (int(got, 16) if isinstance(got, str) else got) != (int(v, 16) if isinstance(v, str) else v):
                problems.append(f"{cid}: block.{k} fixture={v} tilegrid={got}")

    # site -> SLICE[LM]_X{0,1} prefix (freeze_format §5.5): lower X == index 0
    if c.get("site") and c.get("feature"):
        sites = sorted(grid[tile]["sites"].items(), key=lambda kv: int(kv[0].split("X")[1].split("Y")[0]))
        idx = [s for s, _ in sites].index(c["site"])
        want = f"{grid[tile]['sites'][c['site']]}_X{idx}"
        if want not in c["feature"]:
            problems.append(f"{cid}: site {c['site']} => prefix {want}, feature says {c['feature']}")

    if kind == "feature":
        toks = rule(c["database"], c["feature"])
        if toks is None:
            problems.append(f"{cid}: feature {c['feature']} not in {c['database']}")
            continue
        exp = c["expected_assignments"]
        if len(toks) != len(exp):
            problems.append(f"{cid}: rule has {len(toks)} tokens, fixture lists {len(exp)}")
        for tok, e in zip(toks, exp):
            neg = tok.startswith("!")
            F, B = (int(x) for x in tok.lstrip("!").split("_"))
            far = int(blk["baseaddr"], 16) + F
            word, bit = blk["offset"] + B // 32, B % 32
            val = 0 if neg else 1
            if not (0 <= F < blk["frames"]):
                problems.append(f"{cid}: F={F} outside frames={blk['frames']}")
            for label, mine, theirs in (
                ("token", tok.lstrip("!"), e["token"].lstrip("!")),
                ("negated", neg, e["segbit"]["negated"]),
                ("far", far, int(e["address"]["far"], 16)),
                ("word", word, e["address"]["word"]),
                ("bit", bit, e["address"]["bit"]),
                ("expected_value", val, e["expected_value"]),
            ):
                if mine != theirs:
                    problems.append(f"{cid} {tok}: {label} mine={mine} fixture={theirs}")
            checked += 1

    elif kind in ("ppip", "bitless", "ppip_bitless"):
        toks = rule(c["database"], c["feature"])
        if toks is None:
            problems.append(f"{cid}: {c['feature']} not in {c['database']}")
        elif toks[0] not in ("always", "default", "hint"):
            problems.append(f"{cid}: expected a bit-less ppip, rule is {toks}")
        if c.get("expected_assignments"):
            problems.append(f"{cid}: a bit-less ppip must predict no bits")
        checked += 1

    elif kind == "mask":
        want = c.get("mask_token") or c.get("mask_bit") or c.get("token")
        if not want:
            problems.append(f"{cid}: no mask token key found — cross-check would be vacuous")
        mb = mask_bits(c["database"])
        if want and want not in mb:
            problems.append(f"{cid}: {want} not listed in {c['database']}")
        addr = c.get("expected_address") or (c.get("expected_assignments") or [{}])[0].get("address")
        if want and addr and blk:
            F, B = (int(x) for x in want.split("_"))
            mine = (int(blk["baseaddr"], 16) + F, blk["offset"] + B // 32, B % 32)
            theirs = (int(addr["far"], 16), addr["word"], addr["bit"])
            if mine != theirs:
                problems.append(f"{cid}: mask addr mine={mine} fixture={theirs}")
        checked += 1
    else:
        problems.append(f"{cid}: unhandled kind {kind!r} — cross-check did not cover it")

print(f"cases={len(fx['cases'])} assignments/objects checked={checked}")
for p in problems:
    print("  MISMATCH:", p)
print("PRODUCER CROSS-CHECK:", "FAIL" if problems else "OK")
sys.exit(1 if problems else 0)
