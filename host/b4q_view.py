#!/usr/bin/env python3
"""B4Q — the ADAPTERS of docs/b4_observation_contract.md 3.1 / 3.2: every retained representation of an observation is read
through the adapter its representation names into ONE logical view, field by field tagged R (retained as the source wrote
it), D (derived by the reader) or A (absent in that representation) — a D field is never presented as something the source
wrote, nothing under evidence/ is rewritten, re-encoded, re-digested or retagged, and every digest is verified under the
encoding its representation declares and never recomputed under another:

  M-raw     observe()'s full return (a quarantined return; b4_ff_observation_trace 0.2.0): config a DICTIONARY, config_sha256
            = sha256(json.dumps(config_dict, sort_keys=True)) with Python's DEFAULT separators ("raw-dict-default"); no
            stimulus_sha256 field (D); q_grid_sha256 D; null cells allowed
  M-ledger / M-target / M-memo   the engine ledger entry / the target record / the K9-K10 observation: a PROJECTION — genome R,
            config_sha256 = sha256_json(genome_to_config(genome, addresses)) ("proj-dict-canonical"), stimulus A (the pair's
            task stimulus is the reference, bound by stimulus_sha256 R), trace_sha256 R = sha256_json(q_grid) (the Q grid and
            nothing else), q_after R per step, every other step key D from the task's steps, the pre-init state D (q null)
  C-O       the carrier observation: config a LIST ("list-canonical"), stimulus R, initial R, steps R, observation_sha256 R
            (the only whole-record digest), q_grid_sha256 D

The SOURCE is never taken from the record (3.5): the caller's trusted context names the branch and the representation, and
the record's descriptor / provenance digest must agree with the context's expected source, else the read is refused by name.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4carrier_records as rec  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_ff_model as fm  # noqa: E402

ELEMENTS = list(fm.ELEMENTS)
REPRESENTATIONS = {"M-raw": "model", "M-ledger": "model", "M-target": "model", "M-memo": "model", "C-O": "carrier"}
STEP_KEYS = ("step", "kind", "prev_event", "clock_before", "clock_after", "edge", "ce", "sr", "d", "q_before", "q_after")


class ViewRefusal(ValueError):
    pass


def R_(v): return {"kind": "R", "value": v}
def D_(v): return {"kind": "D", "value": v}
def A_(): return {"kind": "A", "value": None}


def sha256_default(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def _derive_steps_from_stimulus(stimulus: list, q_grid: list, initial_q: list) -> list:
    """The step keys a projection does not retain, derived from the task's declared steps and the previous q_after."""
    out, clock, prev_event, ce, sr, d, q_prev = [], 0, "none", 0, 0, 0, list(initial_q)
    for n, (st, q_after) in enumerate(zip(stimulus, q_grid)):
        if st["kind"] == "init":
            rec_ = {"step": n, "kind": "init", "prev_event": prev_event, "clock_before": clock, "clock_after": clock, "edge": None, "ce": ce, "sr": sr, "d": d}
            prev_event = "init"
        else:
            ce, sr, d = st["ce"], st["sr"], st["d"]
            cb, clock = clock, st["clock"]
            edge = "rising" if (cb, clock) == (0, 1) else "falling" if (cb, clock) == (1, 0) else None
            rec_ = {"step": n, "kind": "set", "prev_event": prev_event, "clock_before": cb, "clock_after": clock, "edge": edge, "ce": ce, "sr": sr, "d": d}
            prev_event = "edge" if edge else "level"
        rec_["q_before"], rec_["q_after"] = list(q_prev), list(q_after)
        rec_["derived_keys"] = [k for k in STEP_KEYS if k != "q_after"]
        out.append(rec_); q_prev = list(q_after)
    return out


def _check_source(expected: dict, hdr: dict | None, provenance_sha256: str | None, where: str):
    """3.5: the expected source comes from the trusted context; the record's descriptor must equal it."""
    if expected is None:
        raise ViewRefusal(f"{where}: no trusted source in the context")
    exp_sha = ex.sha256_json(expected)
    if hdr is not None:
        if ex.provenance_findings(hdr):
            raise ViewRefusal(f"{where}: the record's source descriptor is malformed")
        if ex.sha256_json(hdr) != exp_sha:
            raise ViewRefusal(f"{where}: the record's source descriptor is not the trusted source")
    if provenance_sha256 is not None and provenance_sha256 != exp_sha:
        raise ViewRefusal(f"{where}: provenance_sha256 is not the trusted source's")


def _is_bit(v) -> bool:
    return type(v) is int and v in (0, 1)


def _is_cell(v) -> bool:
    return v is None or _is_bit(v)


def _raw_shape(trace: dict, addresses: tuple):
    """The raw model trace's shape, type-exact, BEFORE any field is read for derivation (the owner's R5): the schema file first
    (closed sets, typed fields, the configuration a dictionary of 21 address-keyed bits), then the dynamic bindings the file cannot
    express — the key set is exactly the trusted mapping's addresses; every cell of every row is None or the int 0 / 1."""
    import b4q_schema as sc
    f = sc.validate_named(trace, "ff_observation_model_raw_v1")
    if f:
        raise ViewRefusal("M-raw: not an instance of the raw schema: " + "; ".join(f[:3]))
    config = trace["config"]
    if set(config) != set(addresses):
        raise ViewRefusal("M-raw: config is not the dictionary over the trusted mapping's addresses")
    for a, b in config.items():
        if not _is_bit(b):
            raise ViewRefusal(f"M-raw: config[{a}] is {b!r}, not the int 0 / 1 (no coercion)")
    for i, s in enumerate(trace["steps"]):
        for key in ("q_before", "q_after"):
            if not (isinstance(s[key], list) and len(s[key]) == 8 and all(_is_cell(c) for c in s[key])):
                raise ViewRefusal(f"M-raw: steps[{i}].{key} is not eight cells of None / 0 / 1")
    if not all(_is_cell(c) for c in trace["initial"]["q"]):
        raise ViewRefusal("M-raw: initial.q is not eight cells of None / 0 / 1")


def view_model_raw(trace: dict, ctx: dict) -> dict:
    """ctx: {source: the formal source descriptor {hypothesis, mapping, fabric}, addresses: the mapping's address tuple}."""
    if not isinstance(trace, dict) or trace.get("schema") != "b4_ff_observation_trace":
        raise ViewRefusal("M-raw: not a b4_ff_observation_trace")
    addresses = tuple(ctx["addresses"])
    _raw_shape(trace, addresses)
    hdr = {k: trace.get(k) for k in ("hypothesis", "mapping", "fabric")}
    _check_source(ctx.get("source"), hdr, None, "M-raw")
    config = trace["config"]
    if trace.get("config_sha256") != sha256_default(config):
        raise ViewRefusal("M-raw: config_sha256 does not digest the dictionary under raw-dict-default")
    genome = sum(config[a] << i for i, a in enumerate(addresses))
    grid = [list(s["q_after"]) for s in trace["steps"]]
    steps = [{**{k: s[k] for k in STEP_KEYS}, "derived_keys": []} for s in trace["steps"]]
    return {"schema": "ff_observation_view", "schema_version": "1.0.0", "source": {"kind": "model", "representation": "M-raw"},
            "provenance": R_(hdr), "config_vector": D_([int(config[a]) for a in addresses]), "genome": D_(genome),
            "config_sha256_raw": R_({"value": trace["config_sha256"], "encoding": "raw-dict-default"}),
            "stimulus": R_(trace["stimulus"]), "stimulus_sha256": D_(ex.sha256_json(list(trace["stimulus"]))), "elements": R_(list(trace["elements"])),
            "pre_init_state": R_({"context": "idle", **{k: trace["initial"][k] for k in ("clock", "ce", "sr", "d", "q")}}),
            "steps": R_(steps), "q_grid_sha256": D_(ex.sha256_json(grid)), "record_sha256": D_(ex.sha256_json(trace))}


def view_model_projection(entry: dict, ctx: dict, representation: str) -> dict:
    """ctx: {source, addresses, stimulus: the pair's task stimulus for this phase (bound by stimulus_sha256)}."""
    if representation not in ("M-ledger", "M-target", "M-memo"):
        raise ViewRefusal(f"{representation}: not a projection")
    for k in ("genome", "config_sha256", "provenance_sha256", "stimulus_sha256", "trace_sha256", "q_grid"):
        if k not in entry:
            raise ViewRefusal(f"{representation}: missing {k}")
    hdr = entry.get("provenance") if representation == "M-target" else None
    _check_source(ctx.get("source"), hdr, entry["provenance_sha256"], representation)
    addresses = tuple(ctx["addresses"])
    genome = entry["genome"]
    if type(genome) is not int or not 0 <= genome < (1 << len(addresses)):
        raise ViewRefusal(f"{representation}: genome is not an int over the mapping's addresses")
    if not (isinstance(entry["q_grid"], list) and all(isinstance(r, list) and len(r) == 8 and all(_is_cell(c) for c in r) for r in entry["q_grid"])):
        raise ViewRefusal(f"{representation}: q_grid is not rows of eight cells of None / 0 / 1")
    for k in ("config_sha256", "provenance_sha256", "stimulus_sha256", "trace_sha256"):
        if not (isinstance(entry[k], str) and len(entry[k]) == 64 and all(c in "0123456789abcdef" for c in entry[k])):
            raise ViewRefusal(f"{representation}: {k} is not a 64-hex digest")
    if entry["config_sha256"] != ex.sha256_json(ex.genome_to_config(genome, addresses)):
        raise ViewRefusal(f"{representation}: config_sha256 does not digest the reconstructed dictionary under proj-dict-canonical")
    grid = [list(r) for r in entry["q_grid"]]
    if entry["trace_sha256"] != ex.sha256_json(grid):
        raise ViewRefusal(f"{representation}: trace_sha256 is not the Q grid's digest")
    stimulus = ctx.get("stimulus")
    if stimulus is None or ex.sha256_json(list(stimulus)) != entry["stimulus_sha256"]:
        raise ViewRefusal(f"{representation}: the context's stimulus is not the one stimulus_sha256 binds")
    if len(stimulus) != len(grid):
        raise ViewRefusal(f"{representation}: the grid has {len(grid)} rows, the stimulus {len(stimulus)} steps")
    steps = _derive_steps_from_stimulus(stimulus, grid, [None] * 8)
    return {"schema": "ff_observation_view", "schema_version": "1.0.0", "source": {"kind": "model", "representation": representation},
            "provenance": R_(hdr) if hdr is not None else A_(), "config_vector": D_(list(ex.genome_to_config(genome, addresses).values())), "genome": R_(genome),
            "config_sha256_raw": R_({"value": entry["config_sha256"], "encoding": "proj-dict-canonical"}),
            "stimulus": A_(), "stimulus_sha256": R_(entry["stimulus_sha256"]), "elements": D_(ELEMENTS),
            "pre_init_state": D_({"context": "idle", "clock": 0, "ce": 0, "sr": 0, "d": 0, "q": [None] * 8}),
            "steps": D_(steps), "q_grid_sha256": R_(entry["trace_sha256"]), "record_sha256": A_()}


def view_carrier(o: dict, ctx: dict) -> dict:
    """ctx: {instrument: the manifest's pinned instrument} — the carrier branch (3.5: the raw instrument block must equal it)."""
    f = rec.validate_observation(o)
    if f:
        raise ViewRefusal("C-O: not a structurally valid carrier observation: " + "; ".join(f[:3]))
    if ctx.get("instrument") is None or o["instrument"] != ctx["instrument"]:
        raise ViewRefusal("C-O: the record's instrument is not the trusted (pinned) instrument")
    if o["config_sha256"] != rec.sha256_json(list(o["config"])):
        raise ViewRefusal("C-O: config_sha256 does not digest the list under list-canonical")
    grid = [list(s["q_after"]) for s in o["steps"]]
    steps = [{**{k: s[k] for k in STEP_KEYS}, "derived_keys": []} for s in o["steps"]]
    pre = R_(dict(o["initial"])) if "initial" in o else A_()
    return {"schema": "ff_observation_view", "schema_version": "1.0.0", "source": {"kind": "carrier", "representation": "C-O"},
            "provenance": R_(dict(o["instrument"])), "config_vector": R_(list(o["config"])), "genome": D_(sum(b << i for i, b in enumerate(o["config"]))),
            "config_sha256_raw": R_({"value": o["config_sha256"], "encoding": "list-canonical"}),
            "stimulus": R_(list(o["stimulus"])), "stimulus_sha256": R_(o["stimulus_sha256"]), "elements": R_(list(o["elements"])),
            "pre_init_state": pre, "steps": R_(steps), "q_grid_sha256": D_(ex.sha256_json(grid)), "record_sha256": R_(rec.observation_sha256(o))}


def view(record, ctx: dict) -> dict:
    """ONE entry point: the trusted context names the branch and the representation (3.5); the record is read under that
    adapter only. A record that declares or implies another branch is refused by name."""
    rep = ctx.get("representation")
    if rep not in REPRESENTATIONS:
        raise ViewRefusal(f"the context names no representation ({rep!r})")
    if REPRESENTATIONS[rep] == "carrier":
        if isinstance(record, dict) and record.get("schema") == "b4_ff_observation_trace":
            raise ViewRefusal("a model trace offered under the carrier branch: refused by name")
        return view_carrier(record, ctx)
    if isinstance(record, dict) and record.get("schema") == rec.SCHEMA_O:
        raise ViewRefusal("a carrier observation offered under the model branch: refused by name")
    if rep == "M-raw":
        return view_model_raw(record, ctx)
    return view_model_projection(record, ctx, rep)


def unmodelled_cells(v: dict) -> int:
    """The host diagnostic of 3.4 (iii): null cells in the view's grid (a model representation only)."""
    return sum(1 for s in v["steps"]["value"] for c in s["q_after"] if c is None)
