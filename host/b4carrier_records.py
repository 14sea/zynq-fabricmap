#!/usr/bin/env python3
"""The B4 carrier v2 records — the observation `O`, the fitness `F`, the transaction close `X` and the session-opening
record — built from an executing-side register trace and validated against the closed field sets of
docs/b4_observation_contract.md sections 4.1–4.3 (the carrier branch). This is the host side of the O / F / X flow
the unit was asked to complete; the trace it reads here is the bench's (sim/b4/out/<scenario>.jsonl), the same
register program a PS application would issue.

What it does NOT do: it holds nothing to a model, computes no decode, scores nothing against a target it was not
given (the fitness needs the task's mask / target / weights: `fitness()` takes them explicitly), and it does not
validate a model trace (the model branch keeps its own reader, contract 3.2). The contract's `fabric_readback_*`,
`commit`, `staging_readback_sha256`, `instrument` and `session_open` fields come from the instrument's PCAP path and
manifest, which this unit does not drive: they are taken from a `links` dict the caller supplies (the bench supplies
symbolic witnesses) and are bound exactly as the contract says, not fabricated here."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import b4carrier_regmap as rm

ELEMENTS = ("AFF", "A5FF", "BFF", "B5FF", "CFF", "C5FF", "DFF", "D5FF")
SCHEMA_O, SCHEMA_F, SCHEMA_X, SCHEMA_SO = "ff_observation_carrier", "ff_fitness", "ff_transaction_close", "ff_session_open"
VERSION = "1.0.0"
MECHANISM_NAMES = {2: "gsr_startupe2"}
STEP_KEYS = ("step", "kind", "prev_event", "clock_before", "clock_after", "edge", "ce", "sr", "d", "q_before", "q_after")
O_KEYS = ("schema", "schema_version", "instrument", "session", "seq", "nonce", "commit", "staging_readback_sha256",
          "fabric_readback_sha256_pre_event", "fabric_readback_sha256_post_event", "init_event", "timing", "predecessor",
          "config", "config_sha256", "stimulus", "stimulus_sha256", "elements", "initial", "steps", "status")
# the phase table of contract 4.2 for an invalid O: which keys exist after a stop in each phase
PHASE_KEYS = {"P1": ("commit", "staging_readback_sha256"), "P2": ("fabric_readback_sha256_pre_event",),
              "P3": ("initial",), "P4": ("fabric_readback_sha256_post_event",), "P5": ()}
ALWAYS_KEYS = ("schema", "schema_version", "instrument", "session", "seq", "nonce", "predecessor", "config", "config_sha256",
               "stimulus", "stimulus_sha256", "elements", "init_event", "timing", "status", "fault", "steps")
F_KEYS = ("schema", "schema_version", "observation_sha256", "task_digest", "fitness")
X_KEYS_CLOSED = ("schema", "schema_version", "observation_sha256", "seq", "cleanup", "base_readback_sha256", "base_state_sample", "idle_status", "status")
X_KEYS_OPEN = ("schema", "schema_version", "observation_sha256", "seq", "idle_status", "status")
DENY = frozenset({"target", "expected", "tables", "oracle", "semantic", "decode", "ff_init", "ff_srval", "ce_mode", "sr_mode", "sr_kind", "storage_kind", "clock_mode"})


class RecordRefusal(ValueError):
    pass


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _hex64(v) -> bool:
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def _cells(v) -> list:
    if isinstance(v, list) and any(c is None for c in v):
        raise RecordRefusal("a null cell on a carrier record (the carrier samples a physical 0 / 1; null is the model's)")
    if not (isinstance(v, list) and len(v) == 8 and all(isinstance(c, int) and not isinstance(c, bool) and c in (0, 1) for c in v)):
        raise RecordRefusal(f"a carrier cell vector must be eight type-exact ints in {{0, 1}}: {v!r}")
    return list(v)


def bits(v: int) -> list:
    return [(v >> i) & 1 for i in range(8)]


# ------------------------------------------------------------------ the register trace
def load_trace(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def transactions(trace: list[dict]) -> list[list[dict]]:
    """Split a bench trace at its transaction marks."""
    out, cur = [], None
    for ev in trace:
        if ev.get("mark") == "transaction_begin":
            cur = []
        elif ev.get("mark") == "transaction_end":
            out.append(cur); cur = None
        elif cur is not None:
            cur.append(ev)
    return out


def _reads(evs: list[dict], addr: int) -> list[dict]:
    return [e for e in evs if e.get("op") == "rd" and e.get("addr") == addr]


def _cells_of(e: dict) -> list | None:
    """The eight cells of a SLOT_READ: ints, or None per cell where the bench's fabric drove x (the model's null —
    on silicon a carrier samples a physical value; here the fabric is the hypothesis model, which has none there)."""
    if e.get("data") is not None:
        return bits(e["data"])
    xs = e.get("x")
    if not isinstance(xs, str) or len(xs) != 32:
        return None
    low = xs[-8:][::-1]                       # bit 0 last in the printed vector
    return [None if c in "xz" else int(c) for c in low]


def _slot_reads(evs: list[dict]) -> dict[int, list | None]:
    """SLOT_ADDR write followed by a SLOT_READ: {slot: eight cells (None per x cell) or None (unreadable)}."""
    out, addr = {}, None
    for e in evs:
        if e.get("op") == "wr" and e.get("addr") == rm.SLOT_ADDR:
            addr = e["data"] & 0x1F
        elif e.get("op") == "rd" and e.get("addr") == rm.SLOT_READ and addr is not None:
            out[addr] = _cells_of(e)
    return out


def _steps_issued(evs: list[dict]) -> list[int]:
    """The STEP_IN words applied: a STEP_IN write followed by a CTRL.STEP."""
    out, staged = [], None
    for e in evs:
        if e.get("op") == "wr" and e.get("addr") == rm.STEP_IN:
            staged = e["data"]
        elif e.get("op") == "wr" and e.get("addr") == rm.CTRL and (e["data"] >> rm.CTRL_BITS["step"]) & 1:
            out.append(staged)
    return out


def _ctrl(evs: list[dict], bit: str) -> bool:
    return any(e.get("op") == "wr" and e.get("addr") == rm.CTRL and (e["data"] >> rm.CTRL_BITS[bit]) & 1 for e in evs)


# ------------------------------------------------------------------ the records
def observation(evs: list[dict], links: dict, timing: dict, seq: int, session: str, predecessor: dict, context: str = "idle") -> dict:
    """Build `O` from one transaction's register trace. `links` supplies what the instrument's PCAP path and manifest
    give: instrument, commit, staging_readback_sha256, fabric_readback_sha256_pre_event / _post_event, config
    (the 21-bit list in address order), nonce; the carrier's samples and witnesses come from the trace."""
    slots = _slot_reads(evs)
    words = _steps_issued(evs)
    in_live = _reads(evs, rm.IN_LIVE)
    status = [rm.decode_status(e["data"]) for e in _reads(evs, rm.STATUS)]
    final = status[-1] if status else None
    faults = [e["data"] & 0xF for e in _reads(evs, rm.FAULT) if e.get("data")]
    pre_in = in_live[0]["data"] if in_live else 0
    initial = {"context": context, "clock": (pre_in >> 10) & 1, "ce": (pre_in >> 8) & 1, "sr": (pre_in >> 9) & 1,
               "d": pre_in & 0xFF, "q": slots.get(0)}
    steps = []
    prev_event, clock, q_prev = "none", 0, initial["q"]
    # step 0 = the init event
    q0 = slots.get(1)
    steps.append({"step": 0, "kind": "init", "prev_event": prev_event, "clock_before": 0, "clock_after": 0, "edge": None,
                  "ce": 0, "sr": 0, "d": 0, "q_before": q_prev, "q_after": q0})
    prev_event, q_prev = "init", q0
    for n, w in enumerate(words, start=1):
        d, ce, sr, c = w & 0xFF, (w >> 8) & 0xFF, (w >> 16) & 0xFF, (w >> 24) & 1
        if 2 + n - 1 not in slots:
            break                                               # the stop: the acquired prefix ends here
        qa = slots.get(2 + n - 1)
        edge = "rising" if (clock, c) == (0, 1) else "falling" if (clock, c) == (1, 0) else None
        steps.append({"step": n, "kind": "set", "prev_event": prev_event, "clock_before": clock, "clock_after": c, "edge": edge,
                      "ce": ce, "sr": sr, "d": d, "q_before": q_prev, "q_after": qa})
        prev_event, clock, q_prev = ("edge" if edge else "level"), c, qa
    stimulus = [{"kind": "init"}] + [{"kind": "set", "clock": s["clock_after"], "ce": s["ce"], "sr": s["sr"], "d": s["d"]} for s in steps[1:]]
    mech = MECHANISM_NAMES[rm.MECHANISM]
    o = {"schema": SCHEMA_O, "schema_version": VERSION, "instrument": dict(links["instrument"]), "session": session, "seq": seq,
         "nonce": links["nonce"], "commit": links["commit"], "staging_readback_sha256": links["staging_readback_sha256"],
         "fabric_readback_sha256_pre_event": links["fabric_readback_sha256_pre_event"],
         "fabric_readback_sha256_post_event": links["fabric_readback_sha256_post_event"],
         "init_event": {"mechanism": mech, "parameters": {"assert_delay": timing["assert_delay"], "pulse": "self_timed",
                                                           "gsr_count_after": _witness_count(evs)}},
         "timing": {k: timing[k] for k in ("settle", "hold", "release", "sample_offset")},
         "predecessor": dict(predecessor), "config": list(links["config"]), "config_sha256": sha256_json(list(links["config"])),
         "stimulus": stimulus, "stimulus_sha256": sha256_json(stimulus), "elements": list(ELEMENTS), "initial": initial,
         "steps": steps, "status": "complete"}
    if faults and faults[-1] != 0:
        # the stop location from the engine's witnesses (the last STATUS), never from which slots the host read
        if final and final["init_done"]:
            phase = "P5"
        elif final and final["pre_sampled"]:
            phase = "P3"
        else:
            phase = "P2"
        o["status"] = "invalid"
        o["fault"] = {"code": rm.FAULT_CODES[faults[-1]], "phase_reached": phase,
                      "step_reached": (final["step_index"] if final else None) if phase == "P5" else (0 if phase == "P3" else None)}
        order = ["P1", "P2", "P3", "P4", "P5"]
        for ph in order[order.index(phase) + 1:]:
            for k in PHASE_KEYS[ph]:
                o.pop(k, None)
        if phase in ("P1", "P2"):
            o.pop("initial", None)
    return o


def _witness_count(evs: list[dict]) -> int | None:
    w = _reads(evs, rm.WITNESS)
    return (w[-1]["data"] & 0xFF) if w else None


def observation_sha256(o: dict) -> str:
    return sha256_json(o)


def fitness(o: dict, task_digest: str, mask: list, target: list, weights: list) -> dict:
    """The executing side's fitness over the FULL mask on the physical values (contract 3.4 (i)): a cell scores
    `weight` when its q_after equals the target; no cell is excluded by a decode, none is None on a carrier record."""
    if o["status"] != "complete":
        raise RecordRefusal("a fitness exists only for a complete observation")
    grid = [s["q_after"] for s in o["steps"]]
    score = 0
    for (s, e), t, w in zip(mask, target, weights):
        if grid[s][e] == t:
            score += w
    return {"schema": SCHEMA_F, "schema_version": VERSION, "observation_sha256": observation_sha256(o), "task_digest": task_digest, "fitness": score}


def transaction_close(evs: list[dict], o: dict, seq: int, links: dict) -> dict:
    """`X` from the trace after the observation: closed (cleanup done) or injection_open (CLOSE without cleanup)."""
    slots = _slot_reads(evs)
    status = [rm.decode_status(e["data"]) for e in _reads(evs, rm.STATUS)]
    final = status[-1] if status else {}
    osha = observation_sha256(o)
    if _ctrl(evs, "cleanup"):
        n_steps = len(o["steps"]) - 1
        cleanup_slot = 2 + n_steps
        fq = slots.get(cleanup_slot)
        in_after = [e for e in _reads(evs, rm.IN_LIVE)]
        edge = bool(final.get("cleanup_edge"))
        x = {"schema": SCHEMA_X, "schema_version": VERSION, "observation_sha256": osha, "seq": seq,
             "cleanup": {"steps": [{"clock_before": 1 if edge else 0, "clock_after": 0, "edge": "falling" if edge else None, "ce": 0, "sr": 0, "d": 0, "q_after": fq}],
                         "final_q": fq},
             "base_readback_sha256": links["base_readback_sha256"], "base_state_sample": links["base_state_sample"],
             "idle_status": final.get("idle", 0), "status": "closed"}
    else:
        x = {"schema": SCHEMA_X, "schema_version": VERSION, "observation_sha256": osha, "seq": seq,
             "idle_status": final.get("idle", 0), "status": "injection_open"}
    return x


def session_open(instrument: dict, startup_readback_sha256: str, base_frames_reference_sha256: str) -> dict:
    """The bootstrap record of contract 5.5: open only on equality with the pinned reference; refused otherwise."""
    status = "open" if startup_readback_sha256 == base_frames_reference_sha256 else "refused"
    return {"schema": SCHEMA_SO, "schema_version": VERSION, "instrument": dict(instrument),
            "startup_readback_sha256": startup_readback_sha256, "base_frames_reference_sha256": base_frames_reference_sha256, "status": status}


# ------------------------------------------------------------------ the validator (the carrier branch, closed sets)
def _keys_at_all_levels(o, acc=None):
    acc = set() if acc is None else acc
    if isinstance(o, dict):
        acc |= set(o)
        for v in o.values():
            _keys_at_all_levels(v, acc)
    elif isinstance(o, list):
        for v in o:
            _keys_at_all_levels(v, acc)
    return acc


def validate_observation(o: dict) -> list[str]:
    f = []
    if o.get("status") == "complete":
        if set(o) != set(O_KEYS):
            f.append(f"complete O keys: extra {sorted(set(o) - set(O_KEYS))} missing {sorted(set(O_KEYS) - set(o))}")
    elif o.get("status") == "invalid":
        fault = o.get("fault", {})
        phase = fault.get("phase_reached")
        order = ["P1", "P2", "P3", "P4", "P5"]
        if phase not in order:
            f.append("invalid O: phase_reached"); return f
        # contract 4.2: the keys of every phase completed BEFORE the stop are required; the stop phase's own keys are
        # present only if acquired; nothing of a later phase
        required = set(ALWAYS_KEYS) | {k for ph in order[: order.index(phase)] for k in PHASE_KEYS[ph]}
        allowed = required | set(PHASE_KEYS[phase])
        if set(o) - allowed:
            f.append(f"invalid O at {phase}: keys of a later phase present: {sorted(set(o) - allowed)}")
        if required - set(o):
            f.append(f"invalid O at {phase}: keys of a completed phase missing: {sorted(required - set(o))}")
        if fault.get("code") not in rm.FAULT_NAMES:
            f.append("invalid O: the fault code is not one of the carrier's named refusals")
    else:
        f.append("O.status"); return f
    if _keys_at_all_levels(o) & DENY:
        f.append(f"deny-listed key names: {sorted(_keys_at_all_levels(o) & DENY)}")
    for k in ("commit", "staging_readback_sha256", "fabric_readback_sha256_pre_event", "fabric_readback_sha256_post_event", "config_sha256", "stimulus_sha256"):
        if k in o and not _hex64(o[k]):
            f.append(f"{k} is not a 64-hex digest")
    if "config" in o and not (isinstance(o["config"], list) and len(o["config"]) == 21 and all(c in (0, 1) and isinstance(c, int) and not isinstance(c, bool) for c in o["config"])):
        f.append("config is not a list of 21 ints in {0, 1}")
    if "config" in o and o.get("config_sha256") != sha256_json(list(o["config"])):
        f.append("config_sha256 does not digest config under the carrier's encoding")
    if "stimulus" in o and o.get("stimulus_sha256") != sha256_json(o["stimulus"]):
        f.append("stimulus_sha256 does not digest the stimulus")
    if o.get("init_event", {}).get("mechanism") not in MECHANISM_NAMES.values():
        f.append("init_event.mechanism is not a declared mechanism")
    if "initial" in o:
        ini = o["initial"]
        if set(ini) != {"context", "clock", "ce", "sr", "d", "q"} or ini["context"] not in ("idle", "a5_injection"):
            f.append("initial: keys / context")
        elif ini["q"] is not None:
            try:
                _cells(ini["q"])
            except RecordRefusal as e:
                f.append(f"initial.q: {e}")
        if ini.get("context") == "idle" and (ini.get("clock"), ini.get("ce"), ini.get("sr"), ini.get("d")) != (0, 0, 0, 0):
            f.append("initial under context idle must have the inputs at 0")
    for s in o.get("steps", []):
        if tuple(s) != STEP_KEYS:
            f.append(f"step {s.get('step')}: keys {sorted(s)}"); continue
        for k in ("q_before", "q_after"):
            if k == "q_before" and s["step"] == 0 and "initial" in o and s[k] == o["initial"].get("q"):
                continue                      # the copy of the pre-init state: judged once, as initial.q
            if s[k] is None:
                f.append(f"step {s['step']}: {k} is null on a carrier record")
            else:
                try:
                    _cells(s[k])
                except RecordRefusal as e:
                    f.append(f"step {s['step']}: {k}: {e}")
    if o.get("predecessor", {}).get("kind") not in ("session_root", "closed", "a5_injection"):
        f.append("predecessor.kind")
    return f


def validate_fitness(fr: dict, o: dict) -> list[str]:
    f = []
    if set(fr) != set(F_KEYS):
        f.append("F keys")
    if fr.get("observation_sha256") != observation_sha256(o):
        f.append("F does not bind this O")
    if not isinstance(fr.get("fitness"), int):
        f.append("fitness is not an int")
    return f


def validate_close(x: dict, o: dict) -> list[str]:
    f = []
    want = X_KEYS_CLOSED if x.get("status") == "closed" else X_KEYS_OPEN if x.get("status") == "injection_open" else None
    if want is None:
        f.append("X.status"); return f
    if set(x) != set(want):
        f.append(f"X keys for {x['status']}: extra {sorted(set(x) - set(want))} missing {sorted(set(want) - set(x))}")
    if x.get("observation_sha256") != observation_sha256(o):
        f.append("X does not bind this O")
    if x.get("status") == "closed":
        if x["cleanup"].get("final_q") is None:
            f.append("closed X without a cleanup sample")
        if not _hex64(x.get("base_readback_sha256", "")):
            f.append("base_readback_sha256")
    return f


def validate_session_open(so: dict) -> list[str]:
    f = []
    if set(so) != {"schema", "schema_version", "instrument", "startup_readback_sha256", "base_frames_reference_sha256", "status"}:
        f.append("session_open keys")
    if so.get("status") != ("open" if so.get("startup_readback_sha256") == so.get("base_frames_reference_sha256") else "refused"):
        f.append("session_open status does not follow from the comparison")
    return f
