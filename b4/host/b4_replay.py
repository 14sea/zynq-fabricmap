#!/usr/bin/env python3
"""B4-FF — ledger REPLAY (the revised 2b-2 scope, section 3.2 item 5 and section 6 item 3): from a run's ledger and
the public task alone — no fabric, no mapping, no hypothesis — rebuild the fitness of every entry from its q grid,
the cartographer's versions and commitments entry by entry, the best-so-far prefix, the populations at every
generation close, and, for a terminated run, the terminal event's consistency: no entry after it, its commitments
equal to the state after the last entry, its count of successful observations equal to the ledger's length. EXACT;
every difference is a named finding; nothing is corrected.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_carto as bc  # noqa: E402
import b4_engine as be  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_landscape as bl  # noqa: E402


def replay(result: dict, task: ex.PublicTask, x_perm: list[int] | None = None) -> list[str]:
    f: list[str] = []
    ledger = result["ledger"]
    n = len(task.addresses)
    arm = result["arm"]
    if result["task_digest"] != task.digest():
        f.append("the result was not produced under this task")
    seqs = [e["seq"] for e in ledger]
    if seqs != list(range(1, len(ledger) + 1)):
        f.append("the ledger's seqs are not 1..N in order")
    if result["observations"] != len(ledger):
        f.append(f"observations {result['observations']} != ledger entries {len(ledger)}")
    learning = arm in ("O", "X") or (arm == "F" and result.get("frozen_view") is not None and result.get("map_origin") == "learned")
    carto = bc.ObservationCarto(n) if learning else None
    frozen_after_probes = None
    best = None
    trace_prefix = []
    search_entries = []
    stim_sha = ex.sha256_json(list(task.stimulus))
    for e in ledger:
        grid = e["q_grid"]
        if e["phase"] == "holdout":
            fit, nones = bl._score({"steps": [{"q_after": r} for r in grid]}, task.holdout_mask, task.holdout_target, task.holdout_weights)
        else:
            fit, nones = bl.score_grid(grid, task)
        if (fit, nones) != (e["fitness"], e["none_cells"]):
            f.append(f"seq {e['seq']}: fitness recomputed ({fit}, {nones}) != recorded ({e['fitness']}, {e['none_cells']})")
        if ex.sha256_json(grid) != e["trace_sha256"]:
            f.append(f"seq {e['seq']}: the q grid does not hash to the recorded trace digest")
        if ex.sha256_json(ex.genome_to_config(e["genome"], task.addresses)) != e["config_sha256"]:
            f.append(f"seq {e['seq']}: the genome does not hash to the recorded config digest")
        if carto is not None and e["phase"] in ("base", "probe", "search"):
            if arm == "F" and e["phase"] == "search":
                frozen_after_probes = True                      # the frozen arm learned nothing after its probe pass
            if frozen_after_probes:
                if (e["map_version_before"], e["map_version_after"], e["map_commitment_after"]) != (carto.version, carto.version, carto.commitment()):
                    f.append(f"seq {e['seq']}: the frozen map moved during the search")
            else:
                vb = carto.version
                carto.ingest(e["seq"], e["genome"], stim_sha, bc.permute_grid(grid, x_perm) if arm == "X" else grid)
                if (vb, carto.version, carto.commitment()) != (e["map_version_before"], e["map_version_after"], e["map_commitment_after"]):
                    f.append(f"seq {e['seq']}: the map version / commitment differ from the ledger")
        if e["phase"] == "base":
            best = e["fitness"]
        if e["phase"] == "search":
            best = max(best, e["fitness"]) if best is not None else e["fitness"]
            trace_prefix.append(best)
            search_entries.append(e)
            if e["best"] != best:
                f.append(f"seq {e['seq']}: best-so-far {e['best']} != recomputed {best}")
        if arm == "F" and e["phase"] == "probe" and carto is not None:
            pass
    if arm == "F" and carto is not None:
        probes = [e for e in ledger if e["phase"] == "probe"]
        if probes and result.get("frozen_view") is not None:
            # the frozen view is the cartographer's view after the last probe: rebuild it over base + probes only
            c2 = bc.ObservationCarto(n)
            for e in [x for x in ledger if x["phase"] in ("base", "probe")]:
                c2.ingest(e["seq"], e["genome"], stim_sha, e["q_grid"])
            if [list(g) for g in c2.view().groups] != result["frozen_view"]:
                f.append("the frozen view is not the cartographer's view after the probe pass")
    if trace_prefix != list(result["best_trace"]):
        f.append("the best-so-far prefix differs from the ledger's")
    # the populations at every generation close, from the ledger's children
    pop = [[task.base_genome, result["base_fit"], i] for i in range(be.MU)] if result.get("base_fit") is not None else []
    born = be.MU
    by_gen: dict[int, list] = {}
    for e in search_entries:
        by_gen.setdefault(e["generation"], []).append(e)
    for gc in result["generation_closes"]:
        g = gc["generation"] - 1
        kids = []
        for e in by_gen.get(g, []):
            kids.append([e["genome"], e["fitness"], born]); born += 1
        pool = sorted(pop + kids, key=lambda i: (-i[1], i[2]))
        pop = pool[:be.MU]
        if ex.sha256_json(pop) != gc["population_commitment"] or pop != gc["population"]:
            f.append(f"generation {gc['generation']}: the population after selection differs from the ledger's")
    t = result.get("terminal")
    if t is not None:
        if result["completed"]:
            f.append("a terminated run is marked completed")
        if t["successful_observations"] != len(ledger):
            f.append(f"the terminal event counts {t['successful_observations']} observations, the ledger {len(ledger)}")
        if t["attempt"] != len(ledger) + 1:
            f.append("the terminal attempt is not the observation after the ledger's last")
        last_cm = ledger[-1]["map_commitment_after"] if ledger else (bc.ObservationCarto(n).commitment() if learning else "")
        if carto is not None and t["map_commitment"] != carto.commitment():
            f.append("the terminal event's map commitment is not the cartographer's after the last entry")
        if ledger and carto is None and t["map_commitment"] != last_cm:
            f.append("the terminal event's map commitment is not the ledger's last")
        expected_pop = ex.sha256_json(pop) if pop else ex.sha256_json([])
        if t["population_commitment"] != expected_pop:
            f.append("the terminal event's population commitment is not the population after the last generation close")
        if result.get("champion") is not None or result.get("champion_holdout") is not None:
            f.append("a terminated run carries a champion or a holdout score")
        if result.get("rng_state_final") != t["rng_state"]:
            f.append("the generator advanced after the terminal event")
    elif result["completed"]:
        if not ledger or ledger[-1]["phase"] != "holdout":
            f.append("a completed run's last entry is not the holdout")
    return f
