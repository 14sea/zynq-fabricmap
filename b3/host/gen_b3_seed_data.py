#!/usr/bin/env python3
"""B3 lifecycle 2 — generate b3/firmware/b3_seed_data.h, the data the image needs to REPRODUCE the B3 seed rule
(image stage 4; the owner's ruling of 2026-10-01: the formal B3 rule in C, not B2's table).

    gen_b3_seed_data.py            write the header
    gen_b3_seed_data.py --check    exit 0 if the header is byte-identical to a fresh render, 1 otherwise

The rule (b3/host/b3_plan.py): master = first 4 bytes of sha256(label | instrument commit); pairs drawn from one
xorshift stream off the master (b2_search.pair_seeds: (landscape, operator) per draw, the whole pair skipped when
either seed is excluded, already drawn, or the two are equal). The excluded set is PRODUCTION's —
`b3_plan.session_exclusion()` (every archived set and the lifecycle-2 gate's pairs and master, read through the
gate report's validator) plus `b2_search.EXCLUDED_SEEDS` — emitted sorted, so the board's lookup is a binary search.
B3Q's draw additionally excludes every seed of B3's pairs; the board derives those itself from the B3 profile, so
they are not compiled in.

The header carries ONLY that: the sorted excluded set, the two profiles (B3: master, budget, pairs; B3Q: likewise)
and the source binding (the label, the instrument commit, the gate report's and the committed plan's digests, the
excluded set's digest). Nothing of the prediction — no fitness, genome, ledger or commitment.

The B3 profile is a contract the board accepts, so the committed plan is checked before it is compiled in
(`plan_findings`): schema b3_plan, its version, lifecycle, session B3, strict integer types, the preregistered F1,
the production master — and, against the VALIDATED gate (`b3_plan.gate_inputs()`), the fitness, B* (the budget), the
required N (the pairs) and the gate binding. The profile's budget and N are taken from the gate. Any disagreement is a
named refusal before a header is rendered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b2_search as bs  # noqa: E402
import b3_plan as pl  # noqa: E402
import b3_session as bsess  # noqa: E402

HEADER = REPO_ROOT / "b3/firmware/b3_seed_data.h"
PLAN = REPO_ROOT / "evidence/b3/plan.json"
GENERATOR = "b3/host/gen_b3_seed_data.py"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def excluded_sha256(values: list[int]) -> str:
    """The digest of the sorted excluded set as the header states it: the decimal values joined by ','."""
    return hashlib.sha256(",".join(str(v) for v in values).encode()).hexdigest()


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def plan_findings(plan, gi: dict | None = None) -> list[str]:
    """Every check the B3 profile rests on, as named findings (empty = the plan may be compiled in). The structural
    checks first — schema, version, lifecycle, session, the JSON type of every value read — then, given the
    production gate inputs `gi` (`b3_plan.gate_inputs()`, the validated gate report), the fitness, the budget, N and
    the gate binding. The owner's P2 on 0fe24b0: the profile is compiled into a contract the board accepts, so a plan
    that merely parses is not enough."""
    if not isinstance(plan, dict):
        return ["the plan is not a JSON object"]
    f: list[str] = []
    for key, want in (("schema", "b3_plan"), ("schema_version", pl.SCHEMA_VERSION), ("session", "B3")):
        if plan.get(key) != want:
            f.append(f"the plan's {key} {plan.get(key)!r} is not {want!r}")
    if not _int(plan.get("lifecycle")) or plan.get("lifecycle") != pl.LIFECYCLE:
        f.append(f"the plan's lifecycle {plan.get('lifecycle')!r} is not the integer {pl.LIFECYCLE}")
    for key in ("budget_per_arm", "pairs"):
        if not _int(plan.get(key)) or plan.get(key) <= 0:
            f.append(f"the plan's {key} {plan.get(key)!r} is not a positive integer")
    if plan.get("fitness") != bsess.PREREGISTERED_FITNESS:
        f.append(f"the plan's fitness {plan.get('fitness')!r} is not the preregistered {bsess.PREREGISTERED_FITNESS!r}")
    sd = plan.get("seed_derivation")
    if not isinstance(sd, dict):
        return f + ["the plan has no seed_derivation object"]
    master = bs.master_seed(pl.SESSION_LABEL, pl.INSTRUMENT_COMMIT)
    if (sd.get("label"), sd.get("commit")) != (pl.SESSION_LABEL, pl.INSTRUMENT_COMMIT):
        f.append("the plan's seed derivation label / commit are not the production rule's")
    if not _int(sd.get("master_seed")) or sd.get("master_seed") != master:
        f.append(f"the plan's master_seed {sd.get('master_seed')!r} is not the production rule's {master}")
    if not _int(sd.get("excluded_values_total")):
        f.append("the plan's excluded_values_total is not an integer")
    gate = plan.get("gate")
    if not isinstance(gate, dict):
        return f + ["the plan has no gate object"]
    if f or gi is None:
        return f
    if gi["fitness"] != plan["fitness"]:
        f.append(f"the gate's fitness {gi['fitness']!r} is not the plan's {plan['fitness']!r}")
    if gi["budget_per_arm"] != plan["budget_per_arm"]:
        f.append(f"the plan's budget_per_arm {plan['budget_per_arm']} is not the gate's B* {gi['budget_per_arm']}")
    if gi["pairs"] != plan["pairs"]:
        f.append(f"the plan's pairs {plan['pairs']} is not the gate's required N {gi['pairs']}")
    if gate.get("path") != pl._rel(pl.GATE_REPORT) or gate.get("sha256") != sha256_file(pl.GATE_REPORT):
        f.append("the plan's gate binding (path, sha256) is not the gate report's")
    for key in ("head_at_run", "rules_version", "architecture_sha256", "control_x_permutation_sha256"):
        if gate.get(key) != gi[key]:
            f.append(f"the plan's gate {key} {gate.get(key)!r} is not the validated report's {gi[key]!r}")
    return f


def inputs(plan_path: Path = PLAN) -> dict:
    """Everything the header is rendered from, each read through production: the plan is checked structurally FIRST
    (a malformed one is refused before any slow work), then against the validated gate (`b3_plan.gate_inputs()`) —
    the profile's budget and N are the GATE's, which the plan must agree with — and the excluded set is
    `session_exclusion()` plus `EXCLUDED_SEEDS`, whose size the plan must state. Any disagreement is a ValueError
    naming every finding, raised before a header is rendered or written."""
    try:
        plan = json.loads(Path(plan_path).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError(f"the plan {plan_path} cannot be read: {exc}") from exc
    f = plan_findings(plan)
    if f:
        raise ValueError("; ".join(f))
    gi = pl.gate_inputs()
    f = plan_findings(plan, gi)
    if f:
        raise ValueError("; ".join(f))
    exclusion, _sources = pl.session_exclusion()
    values = sorted(set(exclusion) | set(bs.EXCLUDED_SEEDS))
    if any(not (0 <= v <= 0xFFFFFFFF) for v in values):
        raise ValueError("an excluded value is not a 32-bit seed")
    if plan["seed_derivation"]["excluded_values_total"] != len(values):
        raise ValueError(f"the plan excludes {plan['seed_derivation']['excluded_values_total']} values, production {len(values)}")
    return {"values": values,
            "b3": {"label": pl.SESSION_LABEL, "master": plan["seed_derivation"]["master_seed"], "budget": gi["budget_per_arm"], "pairs": gi["pairs"]},
            "b3q": {"label": pl.QUAL_LABEL, "master": pl.qualification_master(), "budget": pl.QUAL_BUDGET, "pairs": pl.QUAL_PAIRS},
            "commit": pl.INSTRUMENT_COMMIT, "gate_report": pl._rel(pl.GATE_REPORT), "gate_report_sha256": sha256_file(pl.GATE_REPORT),
            "plan": pl._rel(Path(plan_path)), "plan_sha256": sha256_file(Path(plan_path))}


def render(inp: dict | None = None) -> str:
    inp = inp or inputs()
    v = inp["values"]
    rows = []
    for i in range(0, len(v), 6):
        rows.append("    " + ", ".join(f"{x}u" for x in v[i:i + 6]) + ",")
    b3, q = inp["b3"], inp["b3q"]
    return f"""/* b3_seed_data.h — GENERATED by {GENERATOR}; do not edit (b3/tests/test_b3_orch_twin.py holds it byte for byte
 * to a fresh render and its set to production's).
 *
 * The data the image needs to reproduce the B3 seed rule (b3/host/b3_plan.py; b2_search.pair_seeds): the sorted
 * excluded set — b3_plan.session_exclusion() plus b2_search.EXCLUDED_SEEDS — and the two session profiles. B3Q's
 * draw also excludes every seed of B3's pairs, which the board derives from the B3 profile. Nothing of the
 * prediction is here: no fitness, no genome, no ledger, no commitment.
 */
#ifndef B3_SEED_DATA_H
#define B3_SEED_DATA_H

#include <stdint.h>

/* the source binding */
#define B3_SEED_INSTRUMENT_COMMIT "{inp['commit']}"
#define B3_SEED_GATE_REPORT "{inp['gate_report']}"
#define B3_SEED_GATE_REPORT_SHA256 "{inp['gate_report_sha256']}"
#define B3_SEED_PLAN "{inp['plan']}"
#define B3_SEED_PLAN_SHA256 "{inp['plan_sha256']}"

/* the profiles: a session is B3's or B3Q's, by (master, budget, pairs_total) exactly */
#define B3_PROFILE_B3_LABEL "{b3['label']}"
#define B3_PROFILE_B3_MASTER {b3['master']}u
#define B3_PROFILE_B3_BUDGET {b3['budget']}u
#define B3_PROFILE_B3_PAIRS {b3['pairs']}
#define B3_PROFILE_B3Q_LABEL "{q['label']}"
#define B3_PROFILE_B3Q_MASTER {q['master']}u
#define B3_PROFILE_B3Q_BUDGET {q['budget']}u
#define B3_PROFILE_B3Q_PAIRS {q['pairs']}

/* the excluded set, ascending; its digest is sha256 of the decimal values joined by ',' */
#define B3_SEED_EXCLUDED_N {len(v)}
#define B3_SEED_EXCLUDED_SHA256 "{excluded_sha256(v)}"
static const uint32_t B3_SEED_EXCLUDED[B3_SEED_EXCLUDED_N] = {{
""" + "\n".join(rows) + """
};

#endif
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    text = render()
    if a.check:
        ok = HEADER.is_file() and HEADER.read_text() == text
        print("fresh" if ok else f"STALE: {HEADER.relative_to(REPO_ROOT)} is not a fresh render")
        return 0 if ok else 1
    HEADER.write_text(text)
    print(f"wrote {HEADER.relative_to(REPO_ROOT)} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
