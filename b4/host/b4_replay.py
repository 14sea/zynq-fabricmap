#!/usr/bin/env python3
"""B4-FF — ledger REPLAY as RE-EXECUTION (the owner's P1-1 on 2eae943, P2s on 8d2757a; the revised 2b-2 scope,
section 3.2 item 5 and section 6 item 3). From the declared inputs — the arm, the public task, the operator seed, the
budget, the given view, control X's permutation — and the RECORDED OBSERVATIONS alone, the engine is run again against
a port that hands back the ledger's q grids in order and raises the recorded refusal, by its finite kind, at the
recorded attempt; every decision is thereby regenerated and the whole result compared with the recorded one, field by
field. The replay port holds every call to the ledger (config and stimulus digests of attempt k are the k-th entry's or
the terminal event's; nothing beyond the ledger is served); the replay never re-observes after DOMAIN and never
consults a fabric, a mapping or a hypothesis.

    findings = replay(result_dict, task)                   # [] only when everything reconstructs EXACTLY

Control X-A's π is re-derived from the recorded control seed by the engine itself and compared with the recorded
π and attempts; a recorded control failure must reproduce from the ledger (the relabelled cartographer and the
shadow disagreeing at the same observation) or it is a named finding.

VALIDATION IS TOTAL AND TYPE-EXACT before anything is hashed, indexed, scored or reconstructed: every field of the
record, every ledger entry, every q grid (its dimensions against the phase's public stimulus, its cells 0 / 1 / None,
ints never bools), the terminal event, the other refusal (a finite kind), the given view and the source identity
(the same validator the engine applies). A malformed record is a NAMED FINDING, never a pass and never an uncaught
exception; an internal error during the re-execution is reported as such, distinct from a refusal.

WHAT THIS PROVES, AND ITS LIMIT. The replay proves the INTERNAL EXECUTION SEQUENCE: that the recorded result is what
the engine produces from the declared inputs and the recorded observations, with nothing decided, drawn or learned
beyond them. It does NOT prove that an observation, or a DOMAIN, genuinely came from the model or from hardware —
the observation source's identity is validated and bound, not re-derived; a source that told a consistent lie passes.
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
import b4_ff_model as fm  # noqa: E402
import b4_landscape as bl  # noqa: E402

RESULT_KEYS = set(be.RunResult.__dataclass_fields__)
ENTRY_KEYS = {"seq", "phase", "genome", "genome_hex", "config_sha256", "provenance_sha256", "fixture", "stimulus_sha256", "trace_sha256", "q_grid", "fitness",
              "none_cells", "map_version_before", "map_version_after", "map_commitment_after", "parent_born", "bits", "move_kind", "best"}
TERMINAL_KEYS = {"code", "phase", "attempt", "genome", "config_sha256", "stimulus_sha256", "landscape_seed", "operator_seed", "budget",
                 "successful_observations", "rng_state", "population_commitment", "map_commitment", "map_version"}
REFUSAL_KEYS = {"kind", "message", "phase", "attempt"}
CONTROL_FAILURE_KEYS = {"phase", "attempt", "seq", "findings", "successful_observations", "rng_state", "population_commitment", "map_version", "map_commitment", "shadow_commitment"}
RESIDUAL_KEYS = {"partition_preserved", "groups_moved", "groups_true", "groups_x", "true_groups", "x_groups"}
VIEW_KEYS = {"groups", "version", "commitment", "privileged", "origin", "provenance", "base_commitment"}
MOVE_KINDS = ("base", "probe", "random", "group", "holdout")
ELEMENTS = 8


class ReplayMismatch(ValueError):
    """The re-executing engine asked for an observation the ledger does not hold at that attempt."""


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _nonneg(v) -> bool:
    return _int(v) and v >= 0


def _hex64(v) -> bool:
    return ex._hex64(v)


def _is_bool(v) -> bool:
    return isinstance(v, bool)


def _individual(v) -> bool:
    return isinstance(v, list) and len(v) == 3 and _nonneg(v[0]) and _nonneg(v[1]) and _nonneg(v[2])


class ReplayPort:
    """Serves the ledger's observations in order and the recorded refusal (by its finite kind) at its attempt; holds every
    call to the record. Exposes `observe` and `addresses` like the real port; holds no fabric."""

    def __init__(self, result: dict, task: ex.PublicTask):
        self.addresses = tuple(task.addresses)
        self.ledger = list(result["ledger"])
        self.terminal = result.get("terminal")
        self.other = result.get("other_refusal")
        self.provenance = result.get("provenance") or {}
        self.calls = 0
        self.mismatches: list[str] = []

    def observe(self, config: dict, stimulus: list) -> dict:
        self.calls += 1
        k = self.calls
        csha, ssha = ex.sha256_json(config), ex.sha256_json(list(stimulus))
        if self.terminal and k == self.terminal["attempt"]:
            if (csha, ssha) != (self.terminal["config_sha256"], self.terminal["stimulus_sha256"]):
                self.mismatches.append(f"attempt {k}: the terminal candidate / stimulus is not what the re-execution asked for")
            raise fm.DomainRefusal()
        if self.other and k == self.other["attempt"]:
            ex.raise_refusal(self.other["kind"], self.other["message"])
        if k > len(self.ledger):
            self.mismatches.append(f"attempt {k}: an observation beyond the ledger ({len(self.ledger)} entries) was asked for")
            raise ReplayMismatch(f"attempt {k} beyond the ledger")
        e = self.ledger[k - 1]
        if e["config_sha256"] != csha:
            self.mismatches.append(f"attempt {k}: the re-execution asked for config {csha[:12]}…, the ledger holds {e['config_sha256'][:12]}…")
            raise ReplayMismatch(f"attempt {k}: config")
        if e["stimulus_sha256"] != ssha:
            self.mismatches.append(f"attempt {k}: the stimulus is not the ledger's")
            raise ReplayMismatch(f"attempt {k}: stimulus")
        grid = e["q_grid"]
        steps, prev = [], [None] * ELEMENTS
        for row in grid:
            steps.append({"q_before": list(prev), "q_after": list(row)})
            prev = row
        return {"steps": steps, "hypothesis": dict(self.provenance["hypothesis"]), "mapping": dict(self.provenance["mapping"]), "fabric": dict(self.provenance["fabric"])}


def _diff(a, b, path: str, out: list[str], limit: int = 40) -> None:
    if len(out) >= limit:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: present on one side only")
            else:
                _diff(a[k], b[k], f"{path}.{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} recorded, {len(b)} reconstructed")
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out, limit)
    elif type(a) is not type(b) or a != b:                   # type-exact: 1 is not True
        out.append(f"{path}: recorded {str(a)[:40]!r} ({type(a).__name__}), reconstructed {str(b)[:40]!r} ({type(b).__name__})")


def shape_findings(result, task: ex.PublicTask) -> list[str]:
    """Every field's presence, type and range, BEFORE any use. Named; total."""
    f: list[str] = []
    if not isinstance(result, dict):
        return ["the result is not an object"]
    if set(result) != RESULT_KEYS:
        return [f"the result's keys differ from the engine's: {sorted(set(result) ^ RESULT_KEYS)}"]
    r = result
    n = len(task.addresses)
    if r["arm"] not in be.ARMS:
        f.append(f"arm {r['arm']!r}")
    for k in ("task_digest", "map_commitment_final", "map_origin"):
        if not isinstance(r[k], str):
            f.append(f"{k} is not a string")
    for k in ("landscape_seed", "operator_seed", "budget", "observations", "evals", "group_moves", "map_version_final", "map_specimens_final", "map_multi_bit_pairs_final", "rng_state_final"):
        if not _nonneg(r[k]):
            f.append(f"{k} is not a non-negative integer")
    for k in ("completed", "search_completed", "map_privileged"):
        if not _is_bool(r[k]):
            f.append(f"{k} is not a bool")
    for k in ("fixture", "fabric_fixture"):
        if not (r[k] is None or _is_bool(r[k])):
            f.append(f"{k} is not a bool / None")
    if not (r["base_fit"] is None or _nonneg(r["base_fit"])):
        f.append("base_fit")
    if not (isinstance(r["best_trace"], list) and all(_nonneg(x) for x in r["best_trace"])):
        f.append("best_trace is not a list of non-negative integers")
    if not (r["champion"] is None or (isinstance(r["champion"], dict) and set(r["champion"]) == {"genome", "fit", "born"} and all(_nonneg(r["champion"][k]) for k in ("genome", "fit", "born")))):
        f.append("champion")
    for k in ("champion_holdout", "champion_holdout_nones"):
        if not (r[k] is None or _nonneg(r[k])):
            f.append(k)
    for k in ("population", "pending_children"):
        if not (isinstance(r[k], list) and all(_individual(x) for x in r[k])):
            f.append(f"{k} is not a list of [genome, fit, born]")
    if not (isinstance(r["cost"], dict) and set(r["cost"]) == {"base", "probes", "search", "holdout"} and all(_nonneg(v) for v in r["cost"].values())):
        f.append("cost")
    if not (r["frozen_view"] is None or (isinstance(r["frozen_view"], list) and all(isinstance(g, list) and all(_nonneg(b) and b < n for b in g) for g in r["frozen_view"]))):
        f.append("frozen_view")
    gv = r["given_view"]
    if gv is not None:
        if not (isinstance(gv, dict) and set(gv) == VIEW_KEYS and isinstance(gv["groups"], list) and all(isinstance(g, list) and g and all(_nonneg(b) and b < n for b in g) for g in gv["groups"])
                and _nonneg(gv["version"]) and _hex64(gv["commitment"]) and _is_bool(gv["privileged"]) and isinstance(gv["origin"], str)
                and isinstance(gv["provenance"], list) and all(isinstance(x, str) for x in gv["provenance"]) and isinstance(gv["base_commitment"], str)):
            f.append("given_view is not a complete, typed view record")
    if not (r["x_isomorphism_findings"] is None or (isinstance(r["x_isomorphism_findings"], list) and all(isinstance(x, str) for x in r["x_isomorphism_findings"]))):
        f.append("x_isomorphism_findings")
    if not (r["x_control_seed"] is None or _nonneg(r["x_control_seed"])):
        f.append("x_control_seed is not a non-negative integer / None")
    perm_ok = lambda p: isinstance(p, list) and len(p) == n and all(_nonneg(b) and b < n for b in p) and sorted(p) == list(range(n))  # noqa: E731
    if not (r["x_perm"] is None or perm_ok(r["x_perm"])):
        f.append("x_perm is not a permutation of the addresses / None")
    if not (r["x_perm_attempts"] is None or (isinstance(r["x_perm_attempts"], list) and r["x_perm_attempts"] and all(perm_ok(p) for p in r["x_perm_attempts"]))):
        f.append("x_perm_attempts is not a non-empty list of permutations / None")
    xr = r["x_residual"]
    if not (xr is None or (isinstance(xr, dict) and set(xr) == RESIDUAL_KEYS and _is_bool(xr["partition_preserved"]) and all(_nonneg(xr[k]) for k in ("groups_moved", "groups_true", "groups_x"))
                           and all(isinstance(xr[k], list) and all(isinstance(g, list) and all(_nonneg(b) and b < n for b in g) for g in xr[k]) for k in ("true_groups", "x_groups")))):
        f.append("x_residual is not a complete, typed residual-structure record / None")
    cf = r["control_failure"]
    if not (cf is None or (isinstance(cf, dict) and set(cf) == CONTROL_FAILURE_KEYS and cf["phase"] in ex.PHASES and all(_nonneg(cf[k]) for k in ("attempt", "seq", "successful_observations", "rng_state", "map_version"))
                           and isinstance(cf["findings"], list) and cf["findings"] and all(isinstance(x, str) for x in cf["findings"])
                           and _hex64(cf["population_commitment"]) and _hex64(cf["map_commitment"]) and _hex64(cf["shadow_commitment"]))):
        f.append("control_failure is not a complete, typed control-failure event / None")
    gc = r["generation_closes"]
    if not isinstance(gc, list):
        f.append("generation_closes is not a list")
    else:
        for i, g in enumerate(gc):
            if not (isinstance(g, dict) and set(g) == {"generation", "after_seq", "population_commitment", "population", "before"} and _nonneg(g["generation"]) and _nonneg(g["after_seq"])
                    and _hex64(g["population_commitment"]) and all(isinstance(g[k], list) and all(_individual(x) for x in g[k]) for k in ("population", "before"))):
                f.append(f"generation_closes[{i}]")
    # the source identity, with the engine's validator
    pf = ex.provenance_findings(r["provenance"]) if r["provenance"] is not None else []
    f += [f"provenance: {x}" for x in pf]
    # the ledger
    L = r["ledger"]
    if not isinstance(L, list):
        return f + ["the ledger is not a list"]
    n_search, n_hold = len(task.stimulus), len(task.holdout_stimulus)
    for i, e in enumerate(L):
        if not isinstance(e, dict) or (set(e) != ENTRY_KEYS and set(e) != ENTRY_KEYS | {"generation"}):
            f.append(f"ledger[{i}]: keys differ from the engine's entry"); continue
        if e["phase"] not in ex.PHASES:
            f.append(f"ledger[{i}]: phase {e['phase']!r}"); continue
        if not (_nonneg(e["seq"]) and _nonneg(e["genome"]) and e["genome"] < (1 << n) and isinstance(e["genome_hex"], str) and _hex64(e["config_sha256"]) and _hex64(e["provenance_sha256"])
                and (e["fixture"] is None or _is_bool(e["fixture"])) and _hex64(e["stimulus_sha256"]) and _hex64(e["trace_sha256"]) and _nonneg(e["fitness"]) and _nonneg(e["none_cells"])
                and _nonneg(e["map_version_before"]) and _nonneg(e["map_version_after"]) and isinstance(e["map_commitment_after"], str)
                and (e["parent_born"] is None or _nonneg(e["parent_born"])) and isinstance(e["bits"], list) and all(_nonneg(b) and b < n for b in e["bits"])
                and e["move_kind"] in MOVE_KINDS and _nonneg(e["best"]) and ("generation" not in e or _nonneg(e["generation"]))):
            f.append(f"ledger[{i}]: a field has the wrong type or range"); continue
        g = e["q_grid"]
        want_rows = n_hold if e["phase"] == "holdout" else n_search
        if not (isinstance(g, list) and len(g) == want_rows and all(isinstance(row, list) and len(row) == ELEMENTS and all(c is None or (c in (0, 1) and _int(c)) for c in row) for row in g)):
            f.append(f"ledger[{i}]: the q grid is not {want_rows} rows of {ELEMENTS} cells in 0 / 1 / None"); continue
    t = r["terminal"]
    if t is not None and not (isinstance(t, dict) and set(t) == TERMINAL_KEYS and isinstance(t["code"], str) and t["phase"] in ex.PHASES and _nonneg(t["attempt"]) and _nonneg(t["genome"]) and t["genome"] < (1 << n)
                              and _hex64(t["config_sha256"]) and _hex64(t["stimulus_sha256"]) and all(_nonneg(t[k]) for k in ("landscape_seed", "operator_seed", "budget", "successful_observations", "rng_state", "map_version"))
                              and _hex64(t["population_commitment"]) and isinstance(t["map_commitment"], str)):
        f.append("terminal is not a complete, typed terminal event")
    o = r["other_refusal"]
    if o is not None and not (isinstance(o, dict) and set(o) == REFUSAL_KEYS and o["kind"] in ex.REFUSAL_KINDS and isinstance(o["message"], str) and o["phase"] in ex.PHASES and _nonneg(o["attempt"])):
        f.append("other_refusal is not a typed refusal of a finite kind")
    if t is not None and o is not None:
        f.append("a terminal event and another refusal on one run")
    if cf is not None and (t is not None or o is not None):
        f.append("a control failure beside a terminal event or a refusal on one run")
    return f


def structural_findings(result: dict, task: ex.PublicTask) -> list[str]:
    """The shape first (total), then the record's internal arithmetic and the terminal / refusal consistency."""
    f = shape_findings(result, task)
    if f:
        return f
    r = result
    if r["task_digest"] != task.digest():
        f.append("the result was not produced under this task")
    if r["landscape_seed"] != task.seed:
        f.append("the landscape seed is not the task's")
    L = r["ledger"]
    for i, e in enumerate(L):
        if e["seq"] != i + 1:
            f.append(f"ledger[{i}]: seq {e['seq']} is not {i + 1}")
        grid = e["q_grid"]
        if ex.sha256_json(grid) != e["trace_sha256"]:
            f.append(f"seq {e['seq']}: the q grid does not hash to the recorded trace digest")
        if ex.sha256_json(ex.genome_to_config(e["genome"], task.addresses)) != e["config_sha256"]:
            f.append(f"seq {e['seq']}: the genome does not hash to the recorded config digest")
        if e["phase"] == "holdout":
            fit, nones = bl._score({"steps": [{"q_after": row} for row in grid]}, task.holdout_mask, task.holdout_target, task.holdout_weights)
        else:
            fit, nones = bl.score_grid(grid, task)
        if (fit, nones) != (e["fitness"], e["none_cells"]):
            f.append(f"seq {e['seq']}: fitness recomputed ({fit}, {nones}) != recorded ({e['fitness']}, {e['none_cells']})")
        if r["provenance"] is not None and e["provenance_sha256"] != ex.sha256_json(r["provenance"]):
            f.append(f"seq {e['seq']}: the entry's provenance digest is not the result's")
        if e["fixture"] != r["fixture"]:
            f.append(f"seq {e['seq']}: the entry's fixture marker is not the result's")
    if L and r["provenance"] is None:
        f.append("observations were made but no source identity is recorded")
    if r["provenance"] is not None:
        if r["fixture"] is not r["provenance"]["hypothesis"]["fixture"]:
            f.append("the result's fixture marker is not its provenance's")
        if r["fabric_fixture"] is not (r["provenance"]["fabric"]["kind"] != "truth"):
            f.append("the result's fabric_fixture marker is not its provenance's")
    # control X-A: π re-derived from the control seed; the other arms carry no control fields
    if r["arm"] == "X":
        if r["x_control_seed"] is None or r["x_perm"] is None or r["x_perm_attempts"] is None:
            f.append("control X carries no control seed / π / attempts")
        else:
            attempts = bc.derangement_attempts(r["x_control_seed"], len(task.addresses))
            if r["x_perm_attempts"] != attempts or r["x_perm"] != attempts[-1]:
                f.append("the recorded π / attempts are not the ones B3's rule derives from the control seed")
    else:
        for k in ("x_control_seed", "x_perm", "x_perm_attempts", "x_residual", "control_failure", "x_isomorphism_findings"):
            if r[k] is not None:
                f.append(f"{k} on an arm other than X")
    t, o, cf = r["terminal"], r["other_refusal"], r["control_failure"]
    if cf is not None:
        if r["completed"] or r["search_completed"]:
            f.append("a run with a control failure is marked completed")
        if not L or cf["attempt"] != len(L) or cf["seq"] != len(L) or cf["successful_observations"] != len(L):
            f.append("the control failure's exposing observation is not the ledger's last entry")
        if L and cf["phase"] != L[-1]["phase"]:
            f.append("the control failure's phase is not the exposing entry's")
        if L and (cf["map_version"], cf["map_commitment"]) != (L[-1]["map_version_after"], L[-1]["map_commitment_after"]):
            f.append("the control failure's map state is not the exposing entry's")
        if r["rng_state_final"] != cf["rng_state"]:
            f.append("the generator advanced after the control failure")
        if r["champion"] is not None or r["champion_holdout"] is not None:
            f.append("a run with a control failure carries a champion")
    if t is not None:
        if r["completed"]:
            f.append("a terminated run is marked completed")
        if t["code"] != ex.DOMAIN:
            f.append(f"the terminal code is {t['code']!r}, not {ex.DOMAIN}")
        if t["attempt"] != len(L) + 1:
            f.append("the terminal attempt is not the observation after the ledger's last")
        if t["successful_observations"] != len(L):
            f.append(f"the terminal event counts {t['successful_observations']} observations, the ledger {len(L)}")
        if (t["landscape_seed"], t["operator_seed"], t["budget"]) != (r["landscape_seed"], r["operator_seed"], r["budget"]):
            f.append("the terminal event's seeds / budget are not the run's")
        if r["rng_state_final"] != t["rng_state"]:
            f.append("the generator advanced after the terminal event")
        if (r["champion"] is not None) != (t["phase"] == "holdout"):
            f.append("a champion is carried if and only if the search completed and the holdout was refused")
        if r["champion_holdout"] is not None:
            f.append("a terminated run carries a holdout score")
    elif o is not None:
        if r["completed"]:
            f.append("a refused run is marked completed")
        if o["attempt"] != len(L) + 1:
            f.append("the refusal's attempt is not the observation after the ledger's last")
    elif cf is not None:
        pass
    elif r["completed"]:
        if not L or L[-1]["phase"] != "holdout":
            f.append("a completed run's last entry is not the holdout")
    else:
        f.append("a run that neither completed nor was terminated nor refused nor failed its control")
    if r["completed"] and not r["search_completed"]:
        f.append("completed without the search completed")
    return f


def replay(result, task: ex.PublicTask) -> list[str]:
    try:
        f = structural_findings(result, task)
    except Exception as exc:  # noqa: BLE001 — never a pass, never an uncaught exception
        return [f"internal error while validating the record: {type(exc).__name__}: {exc}"]
    if f:
        return f
    try:
        view = bc.MapView.from_dict(result["given_view"]) if result["given_view"] is not None else None
        port = ReplayPort(result, task)
        again = be.run(result["arm"], task, port, result["operator_seed"], result["budget"], view=view, control_seed=result["x_control_seed"])
    except (ReplayMismatch, ValueError, fm.ModelRefusal) as exc:
        return (port.mismatches if "port" in dir() else []) + [f"the re-execution did not run to its end: {type(exc).__name__}: {exc}"]
    except Exception as exc:  # noqa: BLE001
        return [f"internal error during the re-execution: {type(exc).__name__}: {exc}"]
    out: list[str] = list(port.mismatches)
    implied = len(result["ledger"]) + (1 if (result["terminal"] or result["other_refusal"]) else 0)
    if port.calls != implied:
        out.append(f"the re-execution made {port.calls} observations, the record implies {implied}")
    if result["control_failure"] is not None and again.control_failure is None:
        out.append("the recorded control failure did not reproduce: on re-execution the relabelled cartographer and the shadow agree")
    _diff(result, again.as_dict(), "result", out)
    return out
