#!/usr/bin/env python3
"""B4 — K9's FIXED COMPARISON SET (docs/b4_architecture.md section 9.3; the owner's rulings of 2026-10-18 on unit 2b-3
section 3 and on unit 2b-4a section 4.2): the host-only observability diagnostic of the seven semantics under the task's own
stimulus, computed from traces that are kept whole so that every coverage value can be recomputed offline.

    bg = panel(mapping)                                    # the 64 fixed background configurations, as genomes
    pairs = forced_pairs(mapping, bg)                      # one forced address at a time; de-duplicated; ordered
    res = coverage(task, port, mapping, fabric, check=...) # per pair: applicability, the two observations, the differences;
                                                           # per semantic and per address: the counts; the memo's records

THE SET. The five slice-wide mode addresses (ce_mode, sr_mode, sr_kind, storage_kind, clock_mode) in all 32 combinations,
crossed with the 16 per-element INIT / SRVAL bits all 0 and all 1: 64 backgrounds, built from the host mapping for the
audit only (never handed to the cartographer or the engine). For each real address and each background the address is
forced to 0 and to 1 with every other bit held; identical endpoint pairs are de-duplicated and ordered by genome value;
both complete configurations are kept. By hand: a slice-wide address gives 32 pairs, a per-element address 64; 1 184 pairs.

APPLICABILITY IS A PROPERTY OF THE CONFIGURATION, read from the host decode of the two endpoints — never of whether the
two traces happened to differ. A per-element semantic (ff_init, ff_srval) compares its own element's `q_after` only and is
applicable when that element is a storage element at both endpoints (under a latch the x5FF elements are not: 128 pairs of
each per-element semantic are excluded, leaving 384); `sr_kind` is not applicable under a latch (16 of its 32 pairs stay);
`storage_kind` is always applicable, compares every element, and its endpoints may differ by an element's presence;
`ce_mode`, `sr_mode` and `clock_mode` compare the elements applicable at BOTH endpoints. A pair whose two traces are
identical is `covered = False` and STAYS in the denominator; a semantic with an empty denominator is not assessable and is
never 100 %. The whole public `q_after` trace is read, the init readout included (a difference only there rests on the
atomic-initialisation abstraction and stays conditional on A8; `ff_init` is reported with that flag).

WHAT IS KEPT. Every pair: the address (bit, string, semantic, element), the backgrounds that produced it, both endpoint
genomes, the applicability and its reason, the scope of elements compared, both observation ids and the positions and
kinds of every difference. Every unique observation: the genome, the configuration digest, the stimulus digest, the
source identity digest, the trace digest and the FULL q grid (`b4_observe.Memo`). The memo is per seed; a cache hit
changes the call count only. `recompute(result, task, fabric)` re-derives every applicability and coverage from the kept
grids and the decode and names any difference.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
from b4_deadline import StopWork  # noqa: E402
from b4_observe import Memo  # noqa: E402

SEMANTICS = bm.SEMANTICS                                            # ("ff_init", "ff_srval", "ce_mode", "sr_mode", "sr_kind", "storage_kind", "clock_mode")
MODE_SEMANTICS = ("ce_mode", "sr_mode", "sr_kind", "storage_kind", "clock_mode")
PER_ELEMENT = ("ff_init", "ff_srval")
ELEMENTS = bm.ELEMENTS
PANEL_VERSION = "k9-panel-v1 (section 9.3: 32 mode combinations x INIT/SRVAL all-0 / all-1)"


def _bits(mapping) -> tuple[list[int], list[int]]:
    mode_bits = [mapping.genome_bit(mapping.address_of(None, s)) for s in MODE_SEMANTICS]
    elem_bits = [mapping.genome_bit(mapping.address_of(e, s)) for e in ELEMENTS for s in PER_ELEMENT]
    return mode_bits, elem_bits


def panel(mapping) -> list[int]:
    mode_bits, elem_bits = _bits(mapping)
    out: set[int] = set()
    for combo in range(1 << len(mode_bits)):
        g = 0
        for i, b in enumerate(mode_bits):
            if (combo >> i) & 1:
                g |= 1 << b
        for v in (0, 1):
            gg = g
            if v:
                for b in elem_bits:
                    gg |= 1 << b
            out.add(gg)
    bgs = sorted(out)
    if len(bgs) != 64:
        raise ValueError(f"the panel has {len(bgs)} backgrounds, not 64")
    return bgs


def address_info(mapping, bit: int) -> dict:
    a = mapping.addresses[bit]
    e = mapping.entries[a]
    return {"bit": bit, "address": a, "semantic": e.semantic, "element": e.element}


def forced_pairs(mapping, backgrounds: list[int]) -> list[dict]:
    """For each address and background, that bit forced to 0 and to 1 with every other bit held; identical endpoint pairs
    de-duplicated (the backgrounds that produced them listed), ordered by (address bit, g0, g1)."""
    n = len(mapping.addresses)
    by: dict[tuple[int, int, int], list[int]] = {}
    for bit in range(n):
        for g in backgrounds:
            g0, g1 = g & ~(1 << bit), g | (1 << bit)
            by.setdefault((bit, g0, g1), []).append(g)
    out = []
    for (bit, g0, g1), bgs in sorted(by.items()):
        info = address_info(mapping, bit)
        out.append({**info, "g0": g0, "g1": g1, "g0_hex": ex.genome_hex(g0, n), "g1_hex": ex.genome_hex(g1, n), "backgrounds": sorted(bgs)})
    return out


def applicability(fabric, pair: dict) -> dict:
    """Read from the host decode of the two endpoints (configuration only): applicable or not, why, and the elements compared."""
    addrs = fabric.mapping.addresses
    d0, d1 = fabric.decode(ex.genome_to_config(pair["g0"], addrs)), fabric.decode(ex.genome_to_config(pair["g1"], addrs))
    latch0, latch1 = d0[ELEMENTS[0]].latch, d1[ELEMENTS[0]].latch
    both = [e for e in ELEMENTS if d0[e].applicable and d1[e].applicable]
    s = pair["semantic"]
    if s in PER_ELEMENT:
        e = pair["element"]
        ok = d0[e].applicable and d1[e].applicable
        return {"applicable": ok, "reason": None if ok else f"{e} is not a storage element under a latch (x5FF)", "scope": [e] if ok else [],
                "presence_allowed": False, "latch": [latch0, latch1]}
    if s == "sr_kind":
        ok = not (latch0 or latch1)
        return {"applicable": ok, "reason": None if ok else "sr_kind is not applicable under a latch", "scope": both if ok else [],
                "presence_allowed": False, "latch": [latch0, latch1]}
    if s == "storage_kind":
        return {"applicable": True, "reason": None, "scope": list(ELEMENTS), "presence_allowed": True, "latch": [latch0, latch1]}
    ok = bool(both)
    return {"applicable": ok, "reason": None if ok else "no element is a storage element at both endpoints", "scope": both,
            "presence_allowed": False, "latch": [latch0, latch1]}


def differences(grid0: list, grid1: list, scope: list) -> list[dict]:
    """Every position (step, element) inside the scope where the two readouts differ: by value (0 vs 1) or by presence (None vs a value)."""
    if len(grid0) != len(grid1):
        raise ValueError("the two traces are not of one stimulus")
    idx = [ELEMENTS.index(e) for e in scope]
    out = []
    for s, (r0, r1) in enumerate(zip(grid0, grid1)):
        for e in idx:
            a, b = r0[e], r1[e]
            if a is None and b is None:
                continue
            if (a is None) != (b is None):
                out.append({"step": s, "element": ELEMENTS[e], "kind": "presence", "q0": a, "q1": b})
            elif a != b:
                out.append({"step": s, "element": ELEMENTS[e], "kind": "value", "q0": a, "q1": b})
    return out


def summarise(pairs: list[dict], mapping) -> dict:
    """Per semantic: applicable / covered / fraction (None = not assessable) / positive control; per address: the counts;
    the uncovered applicable pairs; whether all seven semantics have a positive control."""
    per_sem = {s: {"applicable": 0, "covered": 0, "not_applicable": 0} for s in SEMANTICS}
    per_addr = {a: {"semantic": mapping.entries[a].semantic, "element": mapping.entries[a].element, "applicable": 0, "covered": 0, "not_applicable": 0}
                for a in mapping.addresses}
    uncovered = []
    for p in pairs:
        s, a = p["semantic"], p["address"]
        if not p["applicable"]:
            per_sem[s]["not_applicable"] += 1; per_addr[a]["not_applicable"] += 1
            continue
        per_sem[s]["applicable"] += 1; per_addr[a]["applicable"] += 1
        if p["covered"]:
            per_sem[s]["covered"] += 1; per_addr[a]["covered"] += 1
        else:
            uncovered.append({"address": a, "semantic": s, "g0": p["g0"], "g1": p["g1"]})
    for s, c in per_sem.items():
        c["fraction"] = (c["covered"] / c["applicable"]) if c["applicable"] else None
        c["assessable"] = c["applicable"] > 0
        c["positive_control"] = c["covered"] > 0
        c["conditional_on_A8"] = (s == "ff_init")
    for a, c in per_addr.items():
        c["fraction"] = (c["covered"] / c["applicable"]) if c["applicable"] else None
    return {"per_semantic": per_sem, "per_address": per_addr, "uncovered_applicable_pairs": uncovered,
            "all_seven_positive_controls": all(per_sem[s]["positive_control"] for s in SEMANTICS),
            "semantics_without_positive_control": [s for s in SEMANTICS if not per_sem[s]["positive_control"]]}


def coverage(task: ex.PublicTask, port: ex.ObservationPort, mapping, fabric, check=None) -> dict:
    """The whole K9 computation for one seed. `check` is called before each pair's observations; on StopWork the result is
    returned with `complete` False and no summary (nothing is judged on a partial set)."""
    if tuple(port.addresses) != tuple(mapping.addresses) or tuple(task.addresses) != tuple(mapping.addresses):
        raise ValueError("the task, the port and the mapping are not over the same addresses")
    bgs = panel(mapping)
    pairs = forced_pairs(mapping, bgs)
    memo = Memo(port)
    done: list[dict] = []
    stopped = None

    def record(complete: bool, stopped, invalid) -> dict:
        return {"panel_version": PANEL_VERSION, "landscape_seed": task.seed, "task_digest": task.digest(), "stimulus_sha256": ex.sha256_json(list(task.stimulus)),
                "backgrounds": bgs, "pairs_total": len(pairs), "pairs_done": len(done), "pairs": list(done),
                "observations": memo.records(), "memo": memo.summary(), "logical_observations": 2 * sum(1 for r in done if r["applicable"]),
                "complete": complete, "stopped": stopped, "invalid": invalid, "summary": summarise(done, mapping) if complete else None,
                "note": NOTE}
    for i, p in enumerate(pairs):
        if check is not None:
            try:
                check()
            except StopWork as exc:
                stopped = {"before_pair_index": i, "reason": str(exc)}
                break
        try:
            app = applicability(fabric, p)
            rec = {**p, **app, "obs0": None, "obs1": None, "hit0": None, "hit1": None, "differences": [], "covered": None}
            if app["applicable"]:
                id0, grid0, hit0 = memo.observe(p["g0"], task.stimulus)
                id1, grid1, hit1 = memo.observe(p["g1"], task.stimulus)
                diffs = differences(grid0, grid1, app["scope"])
                rec.update(obs0=id0, obs1=id1, hit0=hit0, hit1=hit1, differences=diffs, covered=bool(diffs))
        except BaseException as exc:  # noqa: BLE001 — the evidence obtained so far travels with the exception, whatever it is
            if isinstance(exc, KeyboardInterrupt):
                exc.k9_partial = record(False, {"before_pair_index": i, "reason": "KeyboardInterrupt: an external interrupt inside pair " + str(i)}, None)
            else:
                exc.k9_partial = record(False, None, {"pair_index": i, "bit": p["bit"], "g0": p["g0"], "g1": p["g1"], "exception": type(exc).__name__, "reason": str(exc),
                                                      "note": "a refusal or an error inside the K9 computation: invalid under section 9.1; the pairs and observations obtained before it are kept"})
            raise
        done.append(rec)
    return record(stopped is None, stopped, None)


NOTE = ("host-only observability on the fixed section 9.3 set; applicability is read from the configuration's decode, never from the traces; "
        "identical traces are covered = False and stay in the denominator; these observations enter no ledger and no cartographer")


def canonical_findings(result: dict, mapping) -> list[str]:
    """The fixed comparison set: a complete record holds EXACTLY the 1 184 forced pairs in their order; a partial record
    holds a prefix of them; nothing is omitted, duplicated or reordered."""
    want = forced_pairs(mapping, panel(mapping))
    f: list[str] = []
    pairs = result["pairs"]
    if result["complete"] and len(pairs) != len(want):
        f.append(f"a complete K9 record holds {len(pairs)} pairs, the fixed set has {len(want)}")
    if len(pairs) > len(want):
        f.append(f"{len(pairs)} pairs recorded, more than the fixed set's {len(want)}")
    for i, (p, w) in enumerate(zip(pairs, want)):
        if (p["bit"], p["g0"], p["g1"], p["semantic"], p["element"], p["backgrounds"]) != (w["bit"], w["g0"], w["g1"], w["semantic"], w["element"], w["backgrounds"]):
            f.append(f"pair {i}: not the fixed set's pair {i}"); break
    if result["pairs_done"] != len(pairs):
        f.append("pairs_done is not the number of pairs recorded")
    return f


def recompute(result: dict, task: ex.PublicTask, fabric) -> list[str]:
    """Offline: every pair's applicability from the decode and its coverage from the kept grids, held to the record; the
    summary recomputed from the pairs. Names every difference."""
    f: list[str] = []
    mapping = fabric.mapping
    if result["backgrounds"] != panel(mapping):
        f.append("the recorded backgrounds are not the fixed panel")
    want_pairs = forced_pairs(mapping, panel(mapping))
    if result["pairs_total"] != len(want_pairs):
        f.append(f"pairs_total {result['pairs_total']} != {len(want_pairs)}")
    f += canonical_findings(result, mapping)
    if len(result["pairs"]) > len(want_pairs):
        return f
    obs = {o["id"]: o for o in result["observations"]}
    for o in obs.values():
        if ex.sha256_json(o["q_grid"]) != o["trace_sha256"]:
            f.append(f"observation {o['id']}: the q grid does not hash to its digest")
        if ex.sha256_json(ex.genome_to_config(o["genome"], mapping.addresses)) != o["config_sha256"]:
            f.append(f"observation {o['id']}: the genome does not hash to its config digest")
    for i, p in enumerate(result["pairs"]):
        w = want_pairs[i]
        if (p["bit"], p["g0"], p["g1"], p["semantic"], p["element"]) != (w["bit"], w["g0"], w["g1"], w["semantic"], w["element"]):
            f.append(f"pair {i}: not the fixed set's pair"); continue
        app = applicability(fabric, p)
        if (p["applicable"], p["scope"], p["reason"]) != (app["applicable"], app["scope"], app["reason"]):
            f.append(f"pair {i}: applicability recomputed differently")
            continue
        if not app["applicable"]:
            if p["covered"] is not None or p["differences"]:
                f.append(f"pair {i}: a not-applicable pair carries a coverage")
            continue
        if p["obs0"] not in obs or p["obs1"] not in obs:
            f.append(f"pair {i}: an observation id is not in the record"); continue
        o0, o1 = obs[p["obs0"]], obs[p["obs1"]]
        if (o0["genome"], o1["genome"]) != (p["g0"], p["g1"]) or o0["stimulus_sha256"] != result["stimulus_sha256"] or o1["stimulus_sha256"] != result["stimulus_sha256"]:
            f.append(f"pair {i}: the observations are not of the pair's endpoints under the task's stimulus"); continue
        diffs = differences(o0["q_grid"], o1["q_grid"], app["scope"])
        if diffs != p["differences"] or bool(diffs) != p["covered"]:
            f.append(f"pair {i}: coverage recomputed differently from the kept grids")
    if result["complete"]:
        if result["summary"] != summarise(result["pairs"], mapping):
            f.append("the summary is not what the pairs give")
        if result["stopped"] is not None or result.get("invalid") is not None:
            f.append("a complete result carries a stop or an invalid record")
    elif result["summary"] is not None:
        f.append("an incomplete result carries a summary")
    ids = [o["id"] for o in result["observations"]]
    if ids != list(range(len(ids))):
        f.append("the observation ids are not 0 .. n-1 in order")
    if result["memo"]["unique_observations"] != len(ids):
        f.append("memo.unique_observations is not the number of observations kept")
    if result["logical_observations"] != 2 * sum(1 for p in result["pairs"] if p["applicable"]):
        f.append("logical_observations is not twice the applicable pairs")
    return f
