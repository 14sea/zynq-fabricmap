#!/usr/bin/env python3
"""B4-FF — ledger REPLAY as RE-EXECUTION (the owner's P1-1 on 2eae943; the revised 2b-2 scope, section 3.2 item 5
and section 6 item 3). From the declared inputs — the arm, the public task, the operator seed, the budget, the given
view, control X's permutation — and the RECORDED OBSERVATIONS alone, the engine is run again against a port that
hands back the ledger's q grids in order and raises the recorded refusal at the recorded attempt; every decision
(the generator's draws, the parents, the moves, the probe order, the selections, the map versions and commitments,
the pending children, the terminal candidate and its context, the counts and costs, the champion and the holdout)
is thereby regenerated and the whole result compared with the recorded one, field by field. The replay port also
holds every call to the ledger: the config and stimulus digests of attempt k must be the k-th entry's (or the
terminal event's), and no observation beyond the ledger is served — the replay never re-observes after DOMAIN and
never consults a fabric, a mapping or a hypothesis.

    findings = replay(result_dict, task, x_perm=None)      # [] only when everything reconstructs EXACTLY

WHAT THIS PROVES, AND ITS LIMIT. The replay proves the INTERNAL EXECUTION SEQUENCE: that the recorded result is
what the engine produces from the declared inputs and the recorded observations, with nothing decided, drawn or
learned beyond them. It does NOT prove that an observation, or a DOMAIN, genuinely came from the model or from
hardware — the observation source's identity is bound (`provenance`) and checked for consistency, not re-derived.
A malformed record is a named finding, never a pass.
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


class ReplayMismatch(ValueError):
    """The re-executing engine asked for an observation the ledger does not hold at that attempt."""


class ReplayPort:
    """Serves the ledger's observations in order and the recorded refusal at its attempt; holds every call to the
    record. Exposes `observe` and `addresses` like the real port; holds no fabric."""

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
            raise fm.ModelRefusal(self.other["message"])
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
        steps = []
        prev = [None] * 8
        for row in grid:
            steps.append({"q_before": list(prev), "q_after": list(row)})
            prev = row
        return {"steps": steps, "hypothesis": dict(self.provenance.get("hypothesis", {})), "mapping": dict(self.provenance.get("mapping", {}))}


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
    elif a != b:
        out.append(f"{path}: recorded {str(a)[:40]!r}, reconstructed {str(b)[:40]!r}")


def structural_findings(result: dict, task: ex.PublicTask) -> list[str]:
    """The record's shape and its ledger-internal arithmetic, before any re-execution."""
    f: list[str] = []
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        return [f"the result's keys differ from the engine's: {sorted(set(result) ^ RESULT_KEYS) if isinstance(result, dict) else 'not a dict'}"]
    if result["arm"] not in be.ARMS:
        f.append(f"arm {result['arm']!r}")
    if result["task_digest"] != task.digest():
        f.append("the result was not produced under this task")
    if result["landscape_seed"] != task.seed:
        f.append("the landscape seed is not the task's")
    ledger = result["ledger"]
    if not isinstance(ledger, list):
        return f + ["the ledger is not a list"]
    for i, e in enumerate(ledger):
        if not isinstance(e, dict) or set(e) != ENTRY_KEYS and set(e) != ENTRY_KEYS | {"generation"}:
            f.append(f"ledger[{i}]: keys differ from the engine's entry")
            continue
        if e["seq"] != i + 1:
            f.append(f"ledger[{i}]: seq {e['seq']} is not {i + 1}")
        grid = e["q_grid"]
        if ex.sha256_json(grid) != e["trace_sha256"]:
            f.append(f"seq {e['seq']}: the q grid does not hash to the recorded trace digest")
        if ex.sha256_json(ex.genome_to_config(e["genome"], task.addresses)) != e["config_sha256"]:
            f.append(f"seq {e['seq']}: the genome does not hash to the recorded config digest")
        if e["phase"] == "holdout":
            fit, nones = bl._score({"steps": [{"q_after": r} for r in grid]}, task.holdout_mask, task.holdout_target, task.holdout_weights)
        else:
            fit, nones = bl.score_grid(grid, task)
        if (fit, nones) != (e["fitness"], e["none_cells"]):
            f.append(f"seq {e['seq']}: fitness recomputed ({fit}, {nones}) != recorded ({e['fitness']}, {e['none_cells']})")
        if result.get("provenance") is not None and e["provenance_sha256"] != ex.sha256_json(result["provenance"]):
            f.append(f"seq {e['seq']}: the entry's provenance digest is not the result's")
        if e["fixture"] != result.get("fixture"):
            f.append(f"seq {e['seq']}: the entry's fixture marker is not the result's")
    prov = result.get("provenance")
    if ledger and isinstance(prov, dict) and isinstance(prov.get("hypothesis"), dict) and result.get("fixture") != bool(prov["hypothesis"].get("fixture")):
        f.append("the result's fixture marker is not its provenance's")
    if ledger and not (isinstance(prov, dict) and isinstance(prov.get("hypothesis"), dict) and isinstance(prov.get("mapping"), dict)
                       and isinstance(prov["hypothesis"].get("sha256"), str) and "fixture" in prov["hypothesis"] and isinstance(prov["mapping"].get("certificate_sha256"), str)):
        f.append("the result carries no complete observation-source provenance (hypothesis sha256 / fixture, mapping certificate sha256)")
    t = result.get("terminal")
    if t is not None:
        if result["completed"]:
            f.append("a terminated run is marked completed")
        if t.get("code") != ex.DOMAIN:
            f.append(f"the terminal code is {t.get('code')!r}, not {ex.DOMAIN}")
        if t.get("phase") not in ex.PHASES:
            f.append(f"the terminal phase {t.get('phase')!r}")
        if t.get("attempt") != len(ledger) + 1:
            f.append("the terminal attempt is not the observation after the ledger's last")
        if t.get("successful_observations") != len(ledger):
            f.append(f"the terminal event counts {t.get('successful_observations')} observations, the ledger {len(ledger)}")
        if (t.get("landscape_seed"), t.get("operator_seed"), t.get("budget")) != (result["landscape_seed"], result["operator_seed"], result["budget"]):
            f.append("the terminal event's seeds / budget are not the run's")
        if result.get("rng_state_final") != t.get("rng_state"):
            f.append("the generator advanced after the terminal event")
        if (result.get("champion") is not None) != (t.get("phase") == "holdout"):
            f.append("a champion is carried if and only if the search completed and the holdout was refused")
        if result.get("champion_holdout") is not None:
            f.append("a terminated run carries a holdout score")
    elif result["completed"]:
        if not ledger or ledger[-1]["phase"] != "holdout":
            f.append("a completed run's last entry is not the holdout")
    if result.get("completed") and not result.get("search_completed"):
        f.append("completed without the search completed")
    return f


def replay(result: dict, task: ex.PublicTask, x_perm: list[int] | None = None) -> list[str]:
    f = structural_findings(result, task)
    if f:
        return f
    view = bc.MapView.from_dict(result["given_view"]) if result.get("given_view") else None
    port = ReplayPort(result, task)
    try:
        again = be.run(result["arm"], task, port, result["operator_seed"], result["budget"], view=view, x_perm=x_perm)
    except (ValueError, fm.ModelRefusal) as exc:
        return port.mismatches + [f"the re-execution did not run to its end: {type(exc).__name__}: {exc}"]
    out: list[str] = list(port.mismatches)
    if port.calls != len(result["ledger"]) + (1 if result.get("terminal") or result.get("other_refusal") else 0):
        out.append(f"the re-execution made {port.calls} observations, the record implies {len(result['ledger']) + (1 if result.get('terminal') or result.get('other_refusal') else 0)}")
    _diff(result, again.as_dict(), "result", out)
    return out
