#!/usr/bin/env python3
"""B4 — the TARGET SETUP of task-v0.2 (docs/b4_architecture.md section 7.1, DRAFT v0.2.0; the owner's rulings of 2026-10-20,
choices 2-3 and the supplementary target-setup contract). Harness side only: nothing here is handed to an arm.

Per pair, BEFORE any arm starts, the harness (b4_sim) does, in this order:
  1. plan(...)            the public stimuli / masks / weights from the landscape seed (b4_landscape.public_parts), the planted
                          configuration g* by the fixed rule (b4_landscape.planted_genome, the storage_kind bit read from the
                          certificate mapping), the two planned setup observations — persisted as task_setup.json BEFORE the
                          first target call (the pair identity, g*, the rule, the stimulus digests);
  2. observe_target(...)  g* under the SEARCH stimulus through the same execution port as every observation, phase `target`,
                          its raw trace and provenance persisted at once (target_search.json);
  3. observe_target(...)  g* under the HOLDOUT stimulus, phase `target_holdout`, persisted at once (target_holdout.json);
  4. finish(...)          the PublicTask (no seed, no g*, no private record) and task.json: the public fields, the task digest,
                          the commitment to the two setup observations and the digests of the three setup files.
Two logical observations, two physical port calls per pair, shared by the seven arms (the arms' own counts unchanged). A
DOMAIN, a SourceRefusal or a provenance drift inside the setup is `invalid` (a contract break under section 9.1); the deadline
or an interrupt is `incomplete`; a first observation that succeeded is kept when the second does not happen; a pair whose setup
began is never recorded as `not_started`; nothing is redrawn and no task digest is manufactured for an incomplete setup.

ISOLATION. The setup observations pass through no arm's ledger and no cartographer: they are pair-level records with their own
offline reconstruction (`setup_findings`), never a specimen, never in a map, a population, a parent, a champion, a best-so-far
trace or the operator's generator. The holdout target is fixed here, before any search, and is not an input to the search.

WHAT THE VERIFIER DOES (`setup_findings`): the plan re-derived from the recorded seed (the public parts, g* by the rule, the
storage_kind bit of the mapping), every digest recomputed from the kept q grids and genomes, the provenance held to the formal
source, the targets rebuilt from the kept grids and the task digest recomputed — a CONSISTENCY reconstruction from the retained
observations; the fabric is never asked again, and a clean result is not evidence of the target's physical truth (the
observation-authenticity limit of section 5.3).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402
import b4_landscape as bl  # noqa: E402

SETUP_SCHEMA = ("b4_sim_task_setup", "1.0.0")
TARGET_SCHEMA = ("b4_sim_target_observation", "1.0.0")
TASK_SCHEMA = ("b4_sim_task", "1.0.0")
PHASES = ("target", "target_holdout")                               # the two setup observations, in this order
SETUP_FILES = ("task_setup.json", "target_search.json", "target_holdout.json", "task.json")
SETUP_STATES = ("not_started", "in_progress", "partial", "complete", "invalid")
SETUP_COST = {"target": 1, "target_holdout": 1}                     # logical observations = physical port calls per pair, shared by the seven arms


def storage_kind_bit(mapping) -> int:
    """The genome bit of the slice-wide storage_kind address, read from the certificate mapping (the harness's read; the task
    generator receives the integer only)."""
    return mapping.genome_bit(mapping.address_of(None, "storage_kind"))


def plan(pair: int, landscape_seed: int, operator_seed: int, mapping) -> dict:
    """The task_setup document — the PRIVATE record, persisted before the first target call. No observation is made here."""
    parts = bl.public_parts(landscape_seed)
    bit = storage_kind_bit(mapping)
    g = bl.planted_genome(landscape_seed, bit, len(mapping.addresses))
    n = len(mapping.addresses)
    return {"schema": SETUP_SCHEMA[0], "schema_version": SETUP_SCHEMA[1], "pair": pair, "landscape_seed": landscape_seed, "operator_seed": operator_seed,
            "task_version": bl.TASK_VERSION, "addresses": list(mapping.addresses),
            "rule": {"text": bl.PLANTED_RULE, "salt": bl.SALT_TARGET, "storage_kind_bit": bit, "storage_kind_address": mapping.addresses[bit], "n_bits": n, "base_genome": 0},
            "planted_genome": g, "planted_genome_hex": ex.genome_hex(g, n), "planted_config_sha256": ex.sha256_json(ex.genome_to_config(g, mapping.addresses)),
            "planted_is_base": g == 0,
            "public": {"stimulus_sha256": ex.sha256_json(list(parts["stimulus"])), "holdout_stimulus_sha256": ex.sha256_json(list(parts["holdout_stimulus"])),
                       "mask_sha256": ex.sha256_json([list(c) for c in parts["mask"]]), "holdout_mask_sha256": ex.sha256_json([list(c) for c in parts["holdout_mask"]]),
                       "weights_sha256": ex.sha256_json(list(parts["weights"])), "holdout_weights_sha256": ex.sha256_json(list(parts["holdout_weights"])),
                       "search_steps": len(parts["stimulus"]), "holdout_steps": len(parts["holdout_stimulus"]), "ceiling": sum(parts["weights"]), "holdout_ceiling": sum(parts["holdout_weights"])},
            "planned": list(PHASES), "status": "in_progress",
            "note": "the private record of the pair's task: persisted before the first target observation; never read by an arm; the arms receive the PublicTask of task.json"}


def observe_target(port: ex.ObservationPort, genome: int, stimulus, addresses: tuple, phase: str) -> dict:
    """One setup observation through the execution port; the record carries the FULL q grid and the source identity. A DOMAIN
    propagates as DomainRefusal, a malformed or drifting identity as SourceRefusal — the caller decides (invalid)."""
    if phase not in PHASES:
        raise ValueError(phase)
    steps = list(stimulus)
    config = ex.genome_to_config(genome, addresses)
    trace = port.observe(config, steps)
    hdr = {k: trace.get(k) for k in ("hypothesis", "mapping", "fabric")} if isinstance(trace, dict) else None
    f = ex.provenance_findings(hdr)
    if f:
        raise ex.SourceRefusal("the setup observation's source identity is malformed: " + "; ".join(f))
    grid = [list(s["q_after"]) for s in trace["steps"]]
    return {"phase": phase, "genome": genome, "genome_hex": ex.genome_hex(genome, len(addresses)), "config_sha256": ex.sha256_json(config),
            "stimulus_sha256": ex.sha256_json(steps), "trace_sha256": ex.sha256_json(grid), "q_grid": grid,
            "provenance": hdr, "provenance_sha256": ex.sha256_json(hdr), "fixture": hdr["hypothesis"]["fixture"], "fabric_kind": hdr["fabric"]["kind"]}


def source_fields(rec: dict) -> dict:
    """The fields of a setup observation that the commitment covers: the phase, the configuration digest, the stimulus digest, the trace digest and the provenance digest."""
    return {"phase": rec["phase"], "config_sha256": rec["config_sha256"], "stimulus_sha256": rec["stimulus_sha256"], "trace_sha256": rec["trace_sha256"], "provenance_sha256": rec["provenance_sha256"]}


def target_source_sha256(rec_search: dict, rec_holdout: dict) -> str:
    """The commitment the PublicTask carries: sha256 of the canonical JSON of the two setup observations' source fields (the traces
    themselves are committed through their digests; the private record holds the grids)."""
    return ex.sha256_json({"search": source_fields(rec_search), "holdout": source_fields(rec_holdout)})


def rebuild_task(plan_doc: dict, rec_search: dict, rec_holdout: dict) -> ex.PublicTask:
    """The PublicTask from the persisted records: the public parts from the seed, the targets from the kept grids, the commitment
    from the two records. Raises TargetRefusal for a None / malformed cell (the setup is then invalid)."""
    parts = bl.public_parts(plan_doc["landscape_seed"])
    target = bl.targets_from_grid(rec_search["q_grid"], parts["mask"])
    holdout_target = bl.targets_from_grid(rec_holdout["q_grid"], parts["holdout_mask"])
    return bl.make_task(tuple(plan_doc["addresses"]), parts, target, holdout_target, target_source_sha256(rec_search, rec_holdout))


def finish(plan_doc: dict, rec_search: dict, rec_holdout: dict, setup_digests: dict) -> tuple[ex.PublicTask, dict]:
    """The PublicTask and the task.json document (the executing side's input as a record, plus the harness's bindings: the pair, the
    seeds, the digests of the three setup files, the planted scores). `setup_digests` = {file name: sha256} of the files already written."""
    task = rebuild_task(plan_doc, rec_search, rec_holdout)
    planted_search = bl.score_grid(rec_search["q_grid"], task)
    planted_holdout = bl.score_holdout_grid(rec_holdout["q_grid"], task)
    doc = {"schema": TASK_SCHEMA[0], "schema_version": TASK_SCHEMA[1], "pair": plan_doc["pair"], "landscape_seed": plan_doc["landscape_seed"], "operator_seed": plan_doc["operator_seed"],
           "public_task": public_task_dict(task), "task_digest": task.digest(),
           "setup_files_sha256": {k: setup_digests[k] for k in ("task_setup.json", "target_search.json", "target_holdout.json")},
           "planted_search_score": {"fitness": planted_search[0], "none_cells": planted_search[1], "ceiling": task.ceiling},
           "planted_holdout_score": {"fitness": planted_holdout[0], "none_cells": planted_holdout[1], "ceiling": task.holdout_ceiling},
           "status": "complete",
           "note": ("the executing side's input is `public_task` (no landscape seed, no planted genome, no private record: a fixed-program access contract, not information hiding); "
                    "the other fields are the harness's bindings for the audit")}
    return task, doc


def public_task_dict(task: ex.PublicTask) -> dict:
    return {"label": task.label, "version": task.version, "addresses": list(task.addresses), "base_genome": task.base_genome, "stimulus": list(task.stimulus),
            "mask": [list(c) for c in task.mask], "target": list(task.target), "weights": list(task.weights), "holdout_stimulus": list(task.holdout_stimulus),
            "holdout_mask": [list(c) for c in task.holdout_mask], "holdout_target": list(task.holdout_target), "holdout_weights": list(task.holdout_weights),
            "target_source_sha256": task.target_source_sha256}


def task_from_dict(d: dict) -> ex.PublicTask:
    return ex.PublicTask(label=d["label"], version=d["version"], addresses=tuple(d["addresses"]), base_genome=d["base_genome"], stimulus=tuple(d["stimulus"]),
                         mask=tuple(tuple(c) for c in d["mask"]), target=tuple(d["target"]), weights=tuple(d["weights"]), holdout_stimulus=tuple(d["holdout_stimulus"]),
                         holdout_mask=tuple(tuple(c) for c in d["holdout_mask"]), holdout_target=tuple(d["holdout_target"]), holdout_weights=tuple(d["holdout_weights"]),
                         target_source_sha256=d["target_source_sha256"])


# ------------------------------------------------------------------ the offline reconstruction (the verifier's)
def setup_findings(plan_doc: dict, rec_search: dict | None, rec_holdout: dict | None, task_doc: dict | None, mapping, formal_provenance: dict | None,
                   expect: dict | None = None) -> list[str]:
    """Every setup record held to the rule, the seed, the mapping, its own digests and the formal source; the task rebuilt from the
    kept grids and held to task.json. Total: a finding, never an exception. `expect` = {pair, landscape_seed, operator_seed} (the plan)."""
    f: list[str] = []
    try:
        if expect is not None and any(plan_doc.get(k) != expect[k] for k in ("pair", "landscape_seed", "operator_seed")):
            f.append("task_setup: not the planned pair / seeds")
        bit = storage_kind_bit(mapping)
        n = len(mapping.addresses)
        want_plan = plan(plan_doc["pair"], plan_doc["landscape_seed"], plan_doc["operator_seed"], mapping)
        for k in ("task_version", "addresses", "rule", "planted_genome", "planted_genome_hex", "planted_config_sha256", "planted_is_base", "public", "planned"):
            if ex.sha256_json(plan_doc.get(k)) != ex.sha256_json(want_plan[k]):
                f.append(f"task_setup.{k}: not what the seed, the rule and the mapping give")
        if (plan_doc.get("planted_genome", 0) >> bit) & 1:
            f.append("task_setup: the planted configuration is not a flip-flop configuration (T-i)")
        if plan_doc.get("rule", {}).get("storage_kind_bit") != bit or plan_doc.get("rule", {}).get("salt") != bl.SALT_TARGET or plan_doc.get("rule", {}).get("n_bits") != n:
            f.append("task_setup.rule: not the fixed rule")
        parts = bl.public_parts(plan_doc["landscape_seed"])
        for rec, phase, stim in ((rec_search, "target", parts["stimulus"]), (rec_holdout, "target_holdout", parts["holdout_stimulus"])):
            if rec is None:
                continue
            w = f"{phase}"
            if rec.get("phase") != phase:
                f.append(f"{w}: phase {rec.get('phase')!r}")
            if rec.get("genome") != plan_doc["planted_genome"] or rec.get("config_sha256") != plan_doc["planted_config_sha256"]:
                f.append(f"{w}: not the planted configuration")
            if rec.get("stimulus_sha256") != ex.sha256_json(list(stim)):
                f.append(f"{w}: not under the task's {phase} stimulus")
            grid = rec.get("q_grid")
            if not (isinstance(grid, list) and len(grid) == len(stim) and all(isinstance(r, list) and len(r) == bl.ELEMENTS and all(c is None or (c in (0, 1) and not isinstance(c, bool)) for c in r) for r in grid)):
                f.append(f"{w}: the q grid is not {len(stim)} rows of {bl.ELEMENTS} cells in 0 / 1 / None"); continue
            if ex.sha256_json(grid) != rec.get("trace_sha256"):
                f.append(f"{w}: the q grid does not hash to trace_sha256")
            pf = ex.provenance_findings(rec.get("provenance"))
            if pf:
                f.append(f"{w}: provenance: " + "; ".join(pf[:2])); continue
            if ex.sha256_json(rec["provenance"]) != rec.get("provenance_sha256"):
                f.append(f"{w}: the provenance does not hash to provenance_sha256")
            if formal_provenance is not None and ex.sha256_json(rec["provenance"]) != ex.sha256_json(formal_provenance):
                f.append(f"{w}: the source identity is not the formal one")
            if rec.get("fixture") is not rec["provenance"]["hypothesis"]["fixture"] or rec.get("fabric_kind") != rec["provenance"]["fabric"]["kind"]:
                f.append(f"{w}: fixture / fabric_kind are not the provenance's")
        if rec_search is not None and rec_holdout is not None and rec_search.get("provenance_sha256") != rec_holdout.get("provenance_sha256"):
            f.append("the two setup observations do not come from one source identity")
        if task_doc is None:
            return f
        if rec_search is None or rec_holdout is None:
            f.append("task.json exists without both setup observations"); return f
        try:
            task = rebuild_task(plan_doc, rec_search, rec_holdout)
        except bl.TargetRefusal as exc:
            f.append(f"the task cannot be rebuilt from the kept grids: {exc}"); return f
        if ex.sha256_json(task_doc.get("public_task")) != ex.sha256_json(public_task_dict(task)):
            f.append("task.public_task is not the task rebuilt from the setup records")
        if task_doc.get("task_digest") != task.digest():
            f.append("task.task_digest is not the rebuilt task's digest")
        if task_doc.get("public_task", {}).get("target_source_sha256") != target_source_sha256(rec_search, rec_holdout):
            f.append("task: target_source_sha256 is not the commitment to the two setup observations")
        ps, ph = bl.score_grid(rec_search["q_grid"], task), bl.score_holdout_grid(rec_holdout["q_grid"], task)
        if task_doc.get("planted_search_score") != {"fitness": ps[0], "none_cells": ps[1], "ceiling": task.ceiling} or task_doc.get("planted_holdout_score") != {"fitness": ph[0], "none_cells": ph[1], "ceiling": task.holdout_ceiling}:
            f.append("task: the planted scores are not the ones recomputed")
        if task_doc.get("planted_search_score", {}).get("fitness") != task.ceiling:
            f.append("task: the planted configuration does not reach the ceiling on its own trace (a None cell would have refused the target)")
        if any(task_doc.get(k) != plan_doc.get(k) for k in ("pair", "landscape_seed", "operator_seed")):
            f.append("task: not the plan's pair / seeds")
        if task_doc.get("status") != "complete":
            f.append("task.status is not complete")
    except Exception as exc:  # noqa: BLE001
        f.append(f"setup_findings: the reconstruction raised {type(exc).__name__}: {exc} — a record is malformed")
    return f
