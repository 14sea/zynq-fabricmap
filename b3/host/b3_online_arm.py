#!/usr/bin/env python3
"""B3 lifecycle 1 — the online-updating arm O (and, with a permutation, control X), on B2's engine.

The loop is the frozen reference's (`host/b3_online.run_online`, B2-pinned; the equivalence test in
b3/tests/test_b3_online_arm.py holds this copy to it trace for trace and entry for entry). What this
copy adds, per docs/b3_architecture.md v0.2.3 §7–§9:
  * every ledger entry is a `specimen_ledger` 1.1.0 entry (the running `anomalies` count);
  * the champion's holdout evaluation, as B2's run does it — it produces NO ledger entry and does
    not update the map (the ledger has exactly `budget` entries);
  * the O-arm record commitment after every evaluation (`state_trace`): ONE digest over B2's search
    state text (engine, arm, seeds, budget, evaluations, generation, best, the whole population —
    byte for byte the text `b2_search.state_sha256` hashes) joined by `|` to the cartographer's
    state text (`b3_carto.SpecimenCarto.state_text`), so a change in either changes the digest
    (`state_sha256`, the twin of the C image's `b3_state_hex`); `replay` recomputes and compares it;
  * control X: `delta_perm` maps every behaviour delta through π before it enters the cartographer
    (and nothing else); with `shadow=True` a shadow cartographer is fed the unpermuted deltas and the
    isomorphism under π is checked after every specimen (`shadow_findings`).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_control_x as cx  # noqa: E402

ARM_ONLINE = "online"
ARM_LETTER = "O"
ARM_CODE = 2                 # B2's record commitment codes the arm as an integer: 0 random-safe, 1 map-guided; 2 = online


def search_state_text(arm: int, landscape_seed: int, operator_seed: int, budget: int, evals: int,
                      generation: int, best: int, pop: list) -> str:
    """Byte for byte the text `b2_search.state_sha256` hashes (b3/tests/test_b3_online_arm.py holds
    this to B2's function); kept as text here so the cartographer's text can be appended."""
    text = f"{bs.ENGINE_VERSION}|{arm}|{landscape_seed}|{operator_seed}|{budget}|{evals}|{generation}|{best}|"
    for ind in pop:
        text += f"{ind.fit}:{ind.born}:{bc.genome_to_hex(ind.genome)};"
    return text


def state_sha256(search_text: str, carto_text: str) -> str:
    """The O-arm record commitment: sha256(<B2 search state text> | <cartographer state text>)."""
    import hashlib
    return hashlib.sha256(f"{search_text}|{carto_text}".encode()).hexdigest()
B1_MAP_COST = 333            # B1's budget: 9 code probes + 292 confirmations + 32 pairs — the evaluation-count constant charged to F
LEDGER_SCHEMA_VERSION = "1.1.0"


@dataclass
class OnlineResult:
    best_trace: list[int]
    decoded_trace: list[int]
    version_trace: list[int]
    ledger: list[dict]
    anomalies: int
    champion: bs.Individual
    champion_holdout: int
    column_moves: int
    carto: carto_mod.SpecimenCarto
    state_trace: list[str] = field(default_factory=list)          # the combined commitment after evaluation 1..budget
    search_state_trace: list[str] = field(default_factory=list)   # B2's search state text per evaluation (what a search replay regenerates)
    carto_state_trace: list[str] = field(default_factory=list)    # the cartographer's text per evaluation (what the ledger replay regenerates)
    shadow_findings: list[tuple[int, str]] = field(default_factory=list)
    perm_sha256: str | None = None


def ledger_entry(seq: int, version_before: int, parent_born: int, bits: list[int], kind: str,
                 delta: list[tuple[int, int]], fit: int, newly: list[int], carto: carto_mod.SpecimenCarto) -> dict:
    return {"seq": seq, "map_version": version_before, "parent_born": parent_born, "intervention": list(bits),
            "move_kind": kind, "behaviour_delta": [[k, v] for k, v in delta], "fitness": fit,
            "confidence": 2 if len(bits) == 1 else 1,
            "decoded": [[i, carto.decoded[i][0], carto.decoded[i][1]] for i in newly],
            "map_version_after": carto.version, "anomalies": carto.anomalies}


def run_online(landscape: bl.Landscape, operator_seed: int, budget: int, fabric: bs.ModelFabric,
               keep_ledger: bool = True, delta_perm: list[int] | None = None, shadow: bool = False) -> OnlineResult:
    rng = bc.Rng(operator_seed)
    carto = carto_mod.SpecimenCarto()
    shadow_carto = carto_mod.SpecimenCarto() if shadow else None
    view = carto.map_view(landscape.train)
    base_tables = fabric(0)
    base_fit = landscape.train_fitness(base_tables)
    pop = [bs.Individual(0, base_tables, base_fit, born=i) for i in range(bs.MU)]
    born = bs.MU
    evals = 0
    best = base_fit
    trace, dtrace, vtrace, ledger, states, findings = [], [], [], [], [], []
    search_states, carto_states = [], []
    column_moves = 0
    generation = 0
    while evals < budget:
        children = []
        pending = []                                  # (evals, best, carto_text) per child, committed after the selection as B2 does
        pop_before = list(pop)
        for _ in range(bs.LAMBDA):
            if evals == budget:
                break
            pidx = rng.uniform(bs.MU)
            parent = pop[pidx]
            bits, kind = bs.map_guided_move(rng, view)
            if kind == "column":
                column_moves += 1
            genome = bs.apply_move(parent.genome, bits)
            tables = fabric.toggle(parent.tables, bits)
            fit = landscape.train_fitness(tables)
            delta = carto_mod.positions_of([tables[k] ^ parent.tables[k] for k in range(bl.LUTS)])
            fed = cx.map_delta(delta, delta_perm) if delta_perm is not None else delta
            version_before = carto.version
            newly = carto.observe(bits, fed)
            if shadow_carto is not None:
                shadow_carto.observe(bits, delta)
                for what in cx.isomorphism_findings(carto, shadow_carto, delta_perm or list(range(cx.N_POS))):
                    findings.append((evals + 1, what))
            if newly:
                view = carto.map_view(landscape.train)
            children.append(bs.Individual(genome, tables, fit, born))
            born += 1
            evals += 1
            best = max(best, fit)
            trace.append(best)
            dtrace.append(len(carto.decoded))
            vtrace.append(carto.version)
            pending.append((evals, best, carto.state_text()))
            if keep_ledger:
                ledger.append(ledger_entry(evals, version_before, parent.born, bits, kind, fed, fit, newly, carto))
        pool = pop + children
        pool.sort(key=lambda ind: (-ind.fit, ind.born))
        pop = pool[:bs.MU]
        generation += 1
        for j, (ev, bst, ctext) in enumerate(pending):
            closed = j == len(pending) - 1            # B2's convention: the image selects on the last child of the generation
            stext = search_state_text(ARM_CODE, landscape.seed, operator_seed, budget, ev,
                                      generation if closed else generation - 1, bst, pop if closed else pop_before)
            search_states.append(stext)
            carto_states.append(ctext)
            states.append(state_sha256(stext, ctext))
    champion = min(pop, key=lambda ind: (-ind.fit, ind.born))
    champion_holdout = landscape.holdout_fitness(champion.tables)          # no specimen, no ledger entry, no map update
    return OnlineResult(trace, dtrace, vtrace, ledger, carto.anomalies, champion, champion_holdout, column_moves, carto,
                        states, search_states, carto_states, findings,
                        cx.permutation_sha256(delta_perm) if delta_perm is not None else None)


def replay(ledger: list[dict], search_states: list[str] | None = None,
           commitments: list[str] | None = None) -> tuple[carto_mod.SpecimenCarto, list[str]]:
    """The reference cartographer over a ledger: reproduces every version and decode, or names the
    first entry that does not follow (the host's ledger replay, architecture §8 item 3). With
    `search_states` (B2's search state text per entry, as the search replay regenerates it) and
    `commitments` (the records' `state_sha256` per entry) it also recomputes the combined commitment
    after every specimen and names the first one that differs. Giving one without the other, or
    lists of the wrong length, is a named finding, never a silent skip."""
    c = carto_mod.SpecimenCarto()
    f: list[str] = []
    check = search_states is not None or commitments is not None
    if check and (search_states is None or commitments is None or len(search_states) != len(ledger) or len(commitments) != len(ledger)):
        return c, [f"commitment check: search_states / commitments must both be given with one entry per ledger entry "
                   f"({None if search_states is None else len(search_states)} / {None if commitments is None else len(commitments)} for {len(ledger)})"]
    for n, e in enumerate(ledger):
        if c.version != e["map_version"]:
            f.append(f"seq {e['seq']}: map_version {e['map_version']} but the replay is at {c.version}")
            break
        newly = c.observe(e["intervention"], [tuple(p) for p in e["behaviour_delta"]])
        if sorted(newly) != sorted(i for i, _, _ in e["decoded"]) or any(c.decoded.get(i) != (k, v) for i, k, v in e["decoded"]):
            f.append(f"seq {e['seq']}: decoded {e['decoded']} but the replay decoded {sorted(newly)}")
            break
        if c.version != e["map_version_after"] or c.anomalies != e["anomalies"]:
            f.append(f"seq {e['seq']}: version_after/anomalies {e['map_version_after']}/{e['anomalies']} but the replay is at {c.version}/{c.anomalies}")
            break
        if check:
            want = state_sha256(search_states[n], c.state_text())
            if want != commitments[n]:
                f.append(f"seq {e['seq']}: state_sha256 {commitments[n][:12]}… is not the recomputed {want[:12]}…")
                break
    return c, f


def end_to_end_frozen(best_trace_f: list[int], base_fit: int, total_budget: int) -> int:
    """The frozen arm's end-to-end value at total budget T: its own trace at T − 333, the base
    fitness while T ≤ 333 (architecture §9)."""
    s = total_budget - B1_MAP_COST
    return base_fit if s <= 0 else best_trace_f[s - 1]
