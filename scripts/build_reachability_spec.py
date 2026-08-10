#!/usr/bin/env python3
"""Freeze the reachability spec BEFORE the reachable space is measured.

Ruled 2026-08-10: the reachable space may be measured before the carrier exists, but the
spec that governs the measurement is committed and hash-pinned first. Measuring and *then*
choosing a convenient target family, vector order or draw rule is choosing the hypothesis
after seeing the data — the failure this whole line is built to avoid.

Everything the measurement is allowed to consume is fixed here:

* per-LUT **mutable mask** and **fixed values** — derived mechanically from the local_map,
  never hand-entered, because the mask IS the certified universe restricted to that LUT;
* the **attainable ceiling** rule, and the reachable truth-table count per LUT;
* **base INIT** and **LOCK_PINS**, which together decide what the fixed positions hold;
* the **64 input vectors in order**, and the train/holdout split seed;
* the **target family**, the draw rule, the unreachability test, the redraw cap and the
  stop-on-exhaustion rule;
* the output format the measurement must emit.

The one thing this file does NOT contain is a target. A target is *derived* by applying the
frozen draw rule to the measured space, and if every draw is unreachable that is a result
about the space — not a licence to widen the family.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

TOOL_VERSION = "build_reachability_spec.py/1.0.0"
SCHEMA_VERSION = "1.0.0"

# The six LUTs, in the order the envelopes address them. Site and BEL are the carrier's
# obligation; the feature prefix is how the map names the same LUT.
LUT_ORDER = [
    ("SLICE_X2Y25", "A6LUT", "CLBLL_L.SLICEL_X0.ALUT"),
    ("SLICE_X2Y25", "D6LUT", "CLBLL_L.SLICEL_X0.DLUT"),
    ("SLICE_X9Y25", "A6LUT", "CLBLM_L.SLICEL_X1.ALUT"),
    ("SLICE_X9Y25", "D6LUT", "CLBLM_L.SLICEL_X1.DLUT"),
    ("SLICE_X8Y25", "A6LUT", "CLBLM_L.SLICEM_X0.ALUT"),
    ("SLICE_X8Y25", "D6LUT", "CLBLM_L.SLICEM_X0.DLUT"),
]

LOCK_PINS = "I0:A1 I1:A2 I2:A3 I3:A4 I4:A5 I5:A6"

# Neutral and verifiable: every fixed position then holds 0, so "what the uncertified bits
# contain" is a single stated fact rather than a property of whatever the tools emitted.
BASE_INIT = 0

VECTOR_SEED = 0xB1B0            # names the round: claim B, round 0-indexed 0
SPLIT_TRAIN = 40                # of 64 vectors
# Of 64. Chosen from the combinatorics BEFORE any measurement, not tuned to a result.
# A fixed position is blocked when the target wants 1 there and the base holds 0; for a
# balanced target the count of blocked positions is hypergeometric. The binding case is
# SLICE_X8Y25/D6LUT with 20 fixed positions:
#
#   ceiling >= 60 (<=4 blocked): P(accept) = 0.0013 -> P(exhaust at cap 256) = 0.72
#   ceiling >= 58 (<=6 blocked): P(accept) = 0.0288 -> P(exhaust at cap 256) = 0.0006
#   ceiling >= 56 (<=8 blocked): P(accept) = 0.2095 -> P(exhaust at cap 256) ~ 0
#
# The first draft used 60 and would have reported exhaustion for that LUT with ~72%
# probability — a dead experiment by construction rather than by discovery. 58 keeps a
# high bar (90.6% of the vectors attainable), needs ~35 draws for the worst LUT, and
# leaves exhaustion a real stop condition rather than a formality.
CEILING_MIN = 58
REDRAW_CAP = 256


class SpecError(Exception):
    """A refusal."""


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def masks_from_map(local_map: dict) -> dict[str, dict]:
    """Per-LUT mutable INIT positions, taken from the map and nothing else."""
    by_lut: dict[str, set[int]] = {}
    for lut, bits in local_map["index"]["by_lut"].items():
        by_lut[lut] = {b["init_index"] for b in bits}
    for lut, indices in by_lut.items():
        if not indices or max(indices) > 63:
            raise SpecError(f"{lut}: INIT indices out of range {sorted(indices)[:4]}…")
    return by_lut


def lcg_permutation(seed: int, n: int) -> list[int]:
    """A deterministic permutation of 0..n-1, specified rather than borrowed.

    Fisher-Yates driven by a 64-bit LCG whose constants are written here so the sequence
    is reproducible from this file alone — `random.Random` is a reimplementation risk
    across Python versions and a reviewer would have to trust the interpreter instead of
    the spec.
    """
    state = seed & 0xFFFFFFFFFFFFFFFF
    order = list(range(n))
    for i in range(n - 1, 0, -1):
        state = (state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        j = (state >> 33) % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


# ---------------------------------------------------------------- the executable rules
#
# These are the rules themselves, not a description of them. **The report producer calls
# these functions. An independent verifier must NOT** — it reimplements the algorithm from
# the committed spec, without importing this module or the report producer, because a
# defect in `target_vector`, the ceiling, k advancement or the exhaustion path would
# otherwise both produce the report and certify it. The literal known answer below is the
# rendezvous point where the two implementations must agree.
#
# Review v4 showed why prose is not enough — the same words admitted a per-LUT and a
# six-LUT-conjunction reading, and the second silently reinstated the exhaustion failure
# the ceiling threshold had just removed. Review v5 caught the opposite error in the fix:
# telling the verifier to call the producer's code says the reverse of this repo's own
# writer/verifier contract.


def target_vector(seed: int, k: int) -> list[int]:
    """Draw k's target truth table as 64 entries indexed by INPUT VALUE.

    Convention, pinned so an independent consumer builds the identical vector:

    * the initial vector is indices 0..31 = 1 and indices 32..63 = 0;
    * Fisher-Yates swaps the VALUES at positions i and j, i descending, using the same LCG
      as the vector order, seeded with ``vectors.seed XOR (k + 1)``;
    * entry ``v`` is the output for the input assignment ``Ij = (v >> j) & 1``, which is
      the mapping the pinned LOCK_PINS ``I0:A1 … I5:A6`` fixes;
    * the INIT integer is ``sum(entry[v] << v)``.
    """
    state = (seed ^ (k + 1)) & 0xFFFFFFFFFFFFFFFF
    entries = [1] * 32 + [0] * 32
    for i in range(63, 0, -1):
        state = (state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        j = (state >> 33) % (i + 1)
        entries[i], entries[j] = entries[j], entries[i]
    return entries


def target_init(entries: list[int]) -> int:
    return sum(bit << v for v, bit in enumerate(entries))


def blocked_positions(entries: list[int], fixed_indices: list[int], base_init: int) -> list[int]:
    """Fixed positions where the target disagrees with the base — the unreachable ones."""
    return [p for p in fixed_indices if entries[p] != ((base_init >> p) & 1)]


def attainable_ceiling(entries: list[int], fixed_indices: list[int], base_init: int) -> int:
    return 64 - len(blocked_positions(entries, fixed_indices, base_init))


def select_target_for_lut(lut: dict, seed: int, start_k: int,
                          ceiling_min: int = CEILING_MIN,
                          cap: int = REDRAW_CAP) -> dict:
    """Assign one target to ONE LUT, judged by THAT LUT's mask alone.

    The scope is the correction of review v4: another LUT's mask does not judge a target
    that will never be installed there. `k` advances across both accepted and rejected
    draws, so no two LUTs can share a target.

    Producer-side. A verifier reimplements this from the spec instead of calling it.
    """
    fixed = lut["fixed_indices"]
    base = int(lut["base_init"].split("h")[1], 16)
    discarded = []
    k = start_k
    while len(discarded) < cap:
        entries = target_vector(seed, k)
        ceiling = attainable_ceiling(entries, fixed, base)
        if ceiling >= ceiling_min:
            return {
                "site": lut["site"],
                "bel": lut["bel"],
                "draw_index": k,
                "attainable_ceiling": ceiling,
                "blocked_positions": blocked_positions(entries, fixed, base),
                "target_init": f"64'h{target_init(entries):016X}",
                "discarded_draws": discarded,
                "exhausted": False,
                "next_k": k + 1,
            }
        discarded.append({"draw_index": k, "attainable_ceiling": ceiling})
        k += 1
    return {
        "site": lut["site"],
        "bel": lut["bel"],
        "draw_index": None,
        "attainable_ceiling": None,
        "blocked_positions": None,
        "target_init": None,
        "discarded_draws": discarded,
        "exhausted": True,
        "next_k": k,
    }


def select_targets(luts: list[dict], seed: int,
                   ceiling_min: int = CEILING_MIN,
                   cap: int = REDRAW_CAP) -> dict:
    """Assign a target to each LUT in order, stopping on the first exhaustion."""
    assignments, k = [], 0
    for lut in luts:
        result = select_target_for_lut(lut, seed, k, ceiling_min, cap)
        assignments.append(result)
        k = result["next_k"]
        if result["exhausted"]:
            break
    return {
        "assignments": assignments,
        "exhausted": any(a["exhausted"] for a in assignments),
        "complete": len(assignments) == len(luts)
        and not any(a["exhausted"] for a in assignments),
    }


def known_answer_literal() -> dict:
    """A small literal an independent consumer must reproduce byte for byte.

    Determinism tests that call the same helper twice prove only that the helper is a
    function. This is the cross-implementation check: a synthetic seed, the full 64-entry
    vector's INIT, and its first eight entries written out.
    """
    entries = target_vector(0x0001, 0)
    return {
        "seed_expression": "vectors.seed = 0x0001, k = 0",
        "init": f"64'h{target_init(entries):016X}",
        "first_eight_entries": entries[:8],
        "ones": sum(entries),
    }


def build_spec(map_path: Path) -> dict:
    local_map = json.loads(map_path.read_text())
    if local_map.get("schema") != "local_map":
        raise SpecError(f"{map_path}: not a local_map")

    masks = masks_from_map(local_map)
    missing = [prefix for _, _, prefix in LUT_ORDER if prefix not in masks]
    if missing:
        raise SpecError(f"the map does not carry these LUTs: {missing}")
    if len(masks) != len(LUT_ORDER):
        raise SpecError(
            f"the map has {len(masks)} LUTs, this spec names {len(LUT_ORDER)}: "
            f"{sorted(set(masks) ^ {p for _, _, p in LUT_ORDER})}"
        )

    luts = []
    for site, bel, prefix in LUT_ORDER:
        mutable = sorted(masks[prefix])
        fixed = [i for i in range(64) if i not in masks[prefix]]
        mask_int = sum(1 << i for i in mutable)
        luts.append(
            {
                "site": site,
                "bel": bel,
                "feature_prefix": prefix,
                "lock_pins": LOCK_PINS,
                "base_init": f"64'h{BASE_INIT:016X}",
                "mutable_mask": f"64'h{mask_int:016X}",
                "mutable_indices": mutable,
                "mutable_count": len(mutable),
                "fixed_indices": fixed,
                "fixed_count": len(fixed),
                "fixed_values": {str(i): (BASE_INIT >> i) & 1 for i in fixed},
                "reachable_truth_tables": f"2^{len(mutable)}",
            }
        )

    vector_order = lcg_permutation(VECTOR_SEED, 64)
    return {
        "schema": "reachability_spec",
        "schema_version": SCHEMA_VERSION,
        "spec_id": "claimb_round1_reachability_v1",
        "frozen_before_measurement": True,
        "provenance": {
            "local_map": {
                "path": map_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_of(map_path),
                "map_id": local_map["map_id"],
                "address_count": local_map["universe"]["address_count"],
            },
            "preregistration": "docs/claimb_preregistration.md",
            "carrier_design": "docs/claimb_carrier_design.md",
        },
        "phenotype": {
            "lut_count": len(luts),
            "inputs_per_lut": 6,
            "luts": luts,
            "total_mutable_positions": sum(l["mutable_count"] for l in luts),
            "total_fixed_positions": sum(l["fixed_count"] for l in luts),
            "note": (
                "the carrier MUST instantiate exactly these LUTs, at these BELs, with this "
                "base INIT and these LOCK_PINS; a permuted pin mapping puts the same truth "
                "table on different INIT bits and silently invalidates every address"
            ),
        },
        "vectors": {
            "count": 64,
            "definition": "the 64 six-bit input combinations, permuted",
            "seed": f"0x{VECTOR_SEED:04X}",
            "permutation_rule": (
                "Fisher-Yates over 0..63, descending i, swap index j = (state >> 33) % "
                "(i+1), where state is a 64-bit LCG state updated as "
                "state = state*6364136223846793005 + 1442695040888963407 (mod 2^64), "
                "seeded with `seed`. The constants are written out so the order is "
                "reproducible from this spec alone."
            ),
            "order": vector_order,
            "split": {
                "train": vector_order[:SPLIT_TRAIN],
                "holdout": vector_order[SPLIT_TRAIN:],
                "train_count": SPLIT_TRAIN,
                "holdout_count": 64 - SPLIT_TRAIN,
                "firewall": (
                    "search sees train only; holdout is evaluated once, on each arm's "
                    "final champion"
                ),
            },
        },
        "ceiling": {
            "rule": (
                "for LUT i and candidate target T, attainable_ceiling(i, T) = 64 - "
                "|{p in fixed_indices(i) : T(p) != base_init_bit(i, p)}| — the fixed "
                "positions are the only ones evolution cannot reach, so each disagreement "
                "there costs exactly one vector"
            ),
            "why_not_exact_reachability": (
                "requiring T to agree on every fixed position would reject almost every "
                "target: a LUT has 13-20 fixed positions, so a uniformly drawn balanced "
                "function agrees on all of them with probability about 2^-15. Fitness is a "
                "match count, so a partially attainable target is still a usable one; the "
                "ceiling is what must be known and reported"
            ),
            "minimum_accepted": CEILING_MIN,
            "acceptance_arithmetic": {
                "note": (
                    "computed from the hypergeometric distribution BEFORE any measurement, "
                    "so the threshold is not tuned to an outcome; reproducible from the "
                    "fixed counts alone"
                ),
                "binding_lut": "SLICE_X8Y25/D6LUT (20 fixed positions)",
                "p_accept_per_draw": {
                    "ceiling_60": 0.0013,
                    "ceiling_58": 0.0288,
                    "ceiling_56": 0.2095,
                },
                "p_exhaust_at_cap_256": {
                    "ceiling_60": 0.7247,
                    "ceiling_58": 0.0006,
                    "ceiling_56": 0.0,
                },
                "why_58": (
                    "60 would have reported exhaustion for the binding LUT with ~72% "
                    "probability — the experiment would have died by construction rather "
                    "than by discovery. 58 keeps 90.6% of the vectors attainable, needs "
                    "about 35 draws for that LUT, and leaves exhaustion a real stop "
                    "condition"
                ),
            },
            "scope": "per_lut",
            "unreachable_test": (
                f"a drawn target is UNREACHABLE FOR THE LUT IT WAS DRAWN FOR when "
                f"attainable_ceiling(that LUT, target) < {CEILING_MIN}. The predicate is "
                "per LUT and never a conjunction over the six: another LUT's mask does "
                "not judge a target that will never be installed there"
            ),
            "scope_erratum": (
                "review v4 (against commit 16804b8) found this field previously read "
                "'for any of the six LUTs', which contradicted the per-LUT draw rule two "
                "fields below. Executed literally the conjunction accepts about 0.0005 of "
                "draws, so 256 draws exhaust with probability ~0.88 and NONE of k=0..255 "
                "passes under the frozen seed — reinstating, through the predicate's "
                "scope, exactly the dead-experiment failure the ceiling threshold had just "
                "removed. Both sides reproduced both readings independently before the "
                "wording was corrected"
            ),
            "producer_implementation": (
                "scripts/build_reachability_spec.py:attainable_ceiling — the report "
                "PRODUCER calls this. An independent verifier reimplements the rule from "
                "this field and must not import the producer"
            ),
        },
        "target_family": {
            "family": "balanced 6-input Boolean functions",
            "definition": "truth tables over 6 inputs with exactly 32 ones",
            "draw_rule": (
                "draw index k = 0,1,2,… ; target_k is built by taking a 64-entry vector "
                "whose indices 0..31 hold 1 and 32..63 hold 0, then applying the same "
                "Fisher-Yates rule — swapping the VALUES at positions i and j, i "
                "descending — with the LCG seeded by (vectors.seed XOR (k+1)). Draws are "
                "consumed in strict k order; none may be skipped for being inconvenient"
            ),
            "bit_vector_convention": {
                "initial_vector": "indices 0..31 = 1, indices 32..63 = 0",
                "shuffle": "Fisher-Yates swapping the values at positions i and j, i descending",
                "seed_expression": "vectors.seed XOR (k + 1)",
                "truth_table_indexing": (
                    "entry v is the output for the input assignment Ij = (v >> j) & 1, "
                    "which is the mapping the pinned LOCK_PINS I0:A1 … I5:A6 fixes"
                ),
                "init_integer": "sum(entry[v] << v)",
                "known_answer": known_answer_literal(),
                "producer_implementation": (
                    "scripts/build_reachability_spec.py:target_vector — producer side "
                    "only; a verifier builds the vector from the fields above"
                ),
                "cross_check": (
                    "`known_answer` is the rendezvous point: two independent "
                    "implementations must agree on it before either is trusted"
                ),
            },
            "per_lut": (
                "one target is drawn per LUT, in the LUT order listed in `phenotype.luts`, "
                "advancing k across accepted AND rejected draws so no two LUTs share a "
                "target. Each draw is offered to the LUT currently being assigned and is "
                "judged by that LUT's mask alone"
            ),
            "producer_implementation": (
                "scripts/build_reachability_spec.py:select_targets — the report PRODUCER "
                "calls this rather than reimplementing the prose"
            ),
            "verifier_independence": (
                "an independent verifier MUST reimplement this algorithm from the "
                "machine-readable fields of this spec and MUST NOT import "
                "build_reachability_spec, the report producer, or their helpers. A defect "
                "in the producer's draw, ceiling, k-advancement or exhaustion logic would "
                "otherwise produce the report AND certify it, which is not a gate. The two "
                "implementations meet at `bit_vector_convention.known_answer`"
            ),
            "replacement_rule": (
                "if a drawn target is UNREACHABLE by the test above, it is discarded and "
                "the next k is drawn. Discards are recorded with their ceiling"
            ),
            "redraw_cap": REDRAW_CAP,
            "exhaustion_rule": (
                f"if {REDRAW_CAP} consecutive draws are unreachable for one LUT, the "
                "measurement STOPS and reports exhaustion. It does not widen the family, "
                "lower the ceiling threshold, or change the seed. Exhaustion is a result "
                "about the space and is reported as one"
            ),
        },
        "output": {
            "schema": "reachability_report",
            "schema_version": "1.0.0",
            "required_fields": [
                "spec_sha256",
                "per_lut[].site",
                "per_lut[].mutable_count",
                "per_lut[].target_truth_table",
                "per_lut[].draw_index",
                "per_lut[].discarded_draws[]",
                "per_lut[].attainable_ceiling",
                "per_lut[].blocked_positions[]",
                "totals.attainable_ceiling",
                "totals.exhausted",
            ],
            "rule": (
                "the report pins the sha256 of THIS spec; a report whose pin does not match "
                "the committed spec describes a different experiment"
            ),
        },
        "tool_versions": {"builder": TOOL_VERSION},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--map", type=Path, default=REPO_ROOT / "maps/clb_lut_init_v1.local_map.json")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    try:
        spec = build_spec(args.map.resolve())
    except SpecError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    ph = spec["phenotype"]
    print(f"{args.out}: {ph['lut_count']} LUTs, {ph['total_mutable_positions']} mutable "
          f"positions, {ph['total_fixed_positions']} fixed")
    for lut in ph["luts"]:
        print(f"  {lut['site']}/{lut['bel']:6s} mutable {lut['mutable_count']:2d}/64  "
              f"reachable {lut['reachable_truth_tables']}")
    print(f"  vectors: 64, train {spec['vectors']['split']['train_count']} / "
          f"holdout {spec['vectors']['split']['holdout_count']}, seed {spec['vectors']['seed']}")
    print("  NO TARGET IS IN THIS FILE — targets follow from the frozen draw rule")
    return 0


if __name__ == "__main__":
    sys.exit(main())
