#!/usr/bin/env python3
"""The B4 carrier v2 records — the observation `O`, the fitness `F`, the transaction close `X` and the session-opening
record — built from an executing-side register trace and validated against the closed schemas of
docs/b4_observation_contract.md sections 4.1–4.3 (the carrier branch), 5.5 and 5.7. Three layers, kept apart:

  1. STRUCTURE (`validate_observation`, `validate_fitness`, `validate_close`, `validate_session_open`): every object's key
     set closed at EVERY level, every value typed (type-exact ints, 64-hex digests, closed enums, eight-cell vectors with
     no null on a carrier record), the status-dependent sets (a complete O; an invalid O with the phase table; a closed,
     injection_open or faulted X), and the internal consistency a record owes itself (digests over its own fields, the
     q_before chain, the applied steps equal to the declared stimulus they realise). Order of JSON members is nothing:
     a record survives a sorted-key round trip unchanged.
  2. BINDING (`validate_bound`): the record against a TRUSTED CONTEXT the caller supplies from the manifest, the task
     and the session — the instrument identity and VARIANT, the session label, the declared stimulus and configuration,
     mechanism (b)'s frame invariance (staging = pre-event = post-event readback), the fitness's task digest, the
     predecessor's close digest. The context is the authority; the record never grants itself anything.
  3. CHAIN (`validate_chain`): session_open open -> the root (predecessor session_root) -> each candidate's predecessor
     naming the previous X by digest, each X binding its O.

The builder (`observation`, `transaction_close`) reads what the carrier RECORDED — the samples (SLOT_READ) and the
inputs it APPLIED (SLOT_IN_READ) per slot, the base-state sample (BASE_STATE), the witnesses — never what the host merely
attempted on the bus. The declared stimulus is an INPUT (the task's), kept whole in `O.stimulus`; `O.steps` is the
acquired prefix of applied steps. Nothing is fabricated: no step without its sample, no `initial` without the pre-init
sample, no X without a CLOSE the carrier accepted. The PCAP-side fields (commit, staging / pre-event / post-event / base
readbacks, instrument) come from the instrument's path and manifest through `links`; on the bench they are symbolic but
mutually consistent fixture data, and the binding layer checks them as it would real ones."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import b4carrier_regmap as rm

ELEMENTS = ("AFF", "A5FF", "BFF", "B5FF", "CFF", "C5FF", "DFF", "D5FF")
SCHEMA_O, SCHEMA_F, SCHEMA_X, SCHEMA_SO = "ff_observation_carrier", "ff_fitness", "ff_transaction_close", "ff_session_open"
VERSION = "1.0.0"
MECHANISM_NAMES = {2: "gsr_startupe2"}
PREDECESSOR_KINDS = ("session_root", "closed", "a5_injection")
CONTEXTS = ("idle", "a5_injection")
PHASES = ("P1", "P2", "P3", "P4", "P5")
DENY = frozenset({"target", "expected", "tables", "oracle", "semantic", "decode", "ff_init", "ff_srval", "ce_mode", "sr_mode",
                  "sr_kind", "storage_kind", "clock_mode", "answer", "answer_bits", "truth"})


class RecordRefusal(ValueError):
    pass


# ------------------------------------------------------------------ primitives
def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _hex(v, n: int) -> bool:
    return isinstance(v, str) and len(v) == n and all(c in "0123456789abcdef" for c in v)


def bits(v: int) -> list:
    return [(v >> i) & 1 for i in range(8)]


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


# ------------------------------------------------------------------ the typed, closed schemas
# a schema is {key: checker}; `_closed` refuses extra keys, missing keys and bad values, naming each
def _t_int(lo=None, hi=None):
    return lambda v: _is_int(v) and (lo is None or v >= lo) and (hi is None or v <= hi)


def _t_enum(*vals):
    return lambda v: v in vals


def _t_hex(n):
    return lambda v: _hex(v, n)


def _t_cells(v) -> bool:
    return isinstance(v, list) and len(v) == 8 and all(_is_int(c) and c in (0, 1) for c in v)


def _t_cells_or_none(v) -> bool:                 # the model branch only — never used for a carrier record
    return v is None or _t_cells(v)


def _closed(obj, schema: dict, where: str, optional=()) -> list:
    if not isinstance(obj, dict):
        return [f"{where}: not an object"]
    f = []
    extra = set(obj) - set(schema)
    missing = set(schema) - set(obj) - set(optional)
    if extra:
        f.append(f"{where}: extra keys {sorted(extra)}")
    if missing:
        f.append(f"{where}: missing keys {sorted(missing)}")
    for k, chk in schema.items():
        if k in obj:
            try:
                ok = chk(obj[k])
            except Exception:
                ok = False
            if not ok:
                f.append(f"{where}.{k}: bad value {obj[k]!r}")
    return f


INSTRUMENT = {"variant": _t_hex(8), "carrier_sha256": _t_hex(64), "image_sha256": _t_hex(64)}
INIT_PARAMS = {"assert_delay": _t_int(0, 255), "pulse_clocks": _t_int(1, 15), "gsr_count_after": _t_int(0, 255), "pre_init_cleanup": lambda v: isinstance(v, bool)}
INIT_EVENT = {"mechanism": _t_enum(*MECHANISM_NAMES.values()), "parameters": lambda v: isinstance(v, dict)}
TIMING = {"settle": _t_int(1, 15), "hold": _t_int(1, 15), "release": _t_int(1, 255), "sample_offset": _t_int(1, 255)}
PREDECESSOR = {"kind": _t_enum(*PREDECESSOR_KINDS), "seq": lambda v: v is None or _t_int(0)(v), "close_sha256": lambda v: v is None or _hex(v, 64)}
INITIAL = {"context": _t_enum(*CONTEXTS), "clock": _t_int(0, 1), "ce": _t_int(0, 1), "sr": _t_int(0, 1), "d": _t_int(0, 255), "q": _t_cells}
STEP = {"step": _t_int(0), "kind": _t_enum("init", "set"), "prev_event": _t_enum("none", "init", "edge", "level"),
        "clock_before": _t_int(0, 1), "clock_after": _t_int(0, 1), "edge": _t_enum("rising", "falling", None),
        "ce": _t_int(0, 255), "sr": _t_int(0, 255), "d": _t_int(0, 255), "q_before": _t_cells, "q_after": _t_cells}
STIM_INIT = {"kind": _t_enum("init")}
STIM_SET = {"kind": _t_enum("set"), "clock": _t_int(0, 1), "ce": _t_int(0, 255), "sr": _t_int(0, 255), "d": _t_int(0, 255)}
# `premature_operation` is HOST-recorded, never a carrier register value: an operation of P7+ (cleanup / close / close_injection /
# restore_init) that the carrier ACCEPTED before the acquisition reached P6 (the carrier does not know the declared stimulus
# length, so it has no rule against a cleanup after fewer steps than declared). Every other code is the FAULT register's.
O_FAULT_CODES = tuple(rm.FAULT_NAMES) + ("premature_operation",)
FAULT = {"code": _t_enum(*O_FAULT_CODES), "phase_reached": _t_enum(*PHASES), "step_reached": lambda v: v is None or _t_int(0)(v)}
O_COMMON = {"schema": _t_enum(SCHEMA_O), "schema_version": _t_enum(VERSION), "instrument": lambda v: isinstance(v, dict),
            "session": lambda v: isinstance(v, str) and 0 < len(v) <= 64, "seq": _t_int(0), "nonce": _t_hex(16),
            "predecessor": lambda v: isinstance(v, dict), "config": lambda v: isinstance(v, list) and len(v) == 21 and all(_is_int(c) and c in (0, 1) for c in v),
            "config_sha256": _t_hex(64), "stimulus": lambda v: isinstance(v, list) and len(v) >= 1, "stimulus_sha256": _t_hex(64),
            "elements": lambda v: v == list(ELEMENTS), "init_event": lambda v: isinstance(v, dict), "timing": lambda v: isinstance(v, dict),
            "steps": lambda v: isinstance(v, list), "status": _t_enum("complete", "invalid")}
O_PHASE = {"P1": {"commit": _t_hex(64), "staging_readback_sha256": _t_hex(64)}, "P2": {"fabric_readback_sha256_pre_event": _t_hex(64)},
           "P3": {"initial": lambda v: isinstance(v, dict)}, "P4": {"fabric_readback_sha256_post_event": _t_hex(64)}, "P5": {}}
F_SCHEMA = {"schema": _t_enum(SCHEMA_F), "schema_version": _t_enum(VERSION), "observation_sha256": _t_hex(64), "task_digest": _t_hex(64), "fitness": _t_int(0)}
CLEANUP_STEP = {"clock_before": _t_int(0, 1), "clock_after": _t_int(0, 0), "edge": _t_enum("falling", None), "ce": _t_int(0, 0), "sr": _t_int(0, 0), "d": _t_int(0, 0), "q_after": _t_cells}
CLEANUP = {"steps": lambda v: isinstance(v, list) and len(v) == 1, "final_q": _t_cells}
X_COMMON = {"schema": _t_enum(SCHEMA_X), "schema_version": _t_enum(VERSION), "observation_sha256": _t_hex(64), "seq": _t_int(0),
            "idle_status": _t_int(0, 1), "status": _t_enum("closed", "injection_open", "faulted")}
X_CLOSED = {"cleanup": lambda v: isinstance(v, dict), "base_readback_sha256": _t_hex(64), "base_state_sample": _t_cells}
X_FAULTED = {"fault": lambda v: isinstance(v, dict)}
X_FAULT = {"code": _t_enum(*rm.FAULT_NAMES), "phase_reached": _t_enum("P7", "P9", "P10")}
SO_SCHEMA = {"schema": _t_enum(SCHEMA_SO), "schema_version": _t_enum(VERSION), "instrument": lambda v: isinstance(v, dict),
             "startup_readback_sha256": _t_hex(64), "base_frames_reference_sha256": _t_hex(64), "status": _t_enum("open", "refused")}


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
    return [e for e in evs if e.get("op") == "rd" and e.get("addr") == addr and e.get("resp", 0) == 0]


def _accepted_ctrl(evs: list[dict], op: str) -> list[int]:
    """The indices of CTRL writes the register file ACCEPTED (resp 0) naming `op`."""
    return [i for i, e in enumerate(evs) if e.get("op") == "wr" and e.get("addr") == rm.CTRL and e.get("resp", 0) == 0
            and (e["data"] >> rm.CTRL_BITS[op]) & 1]


def _cells_of(e: dict) -> list | None:
    """The eight cells of a SLOT_READ: ints, or None per cell where the bench's fabric drove x (the model's null —
    on silicon a carrier samples a physical value there; the bench's fabric is the hypothesis model, which has none)."""
    if e.get("data") is not None:
        return bits(e["data"])
    xs = e.get("x")
    if not isinstance(xs, str) or len(xs) != 32:
        return None
    low = xs[-8:][::-1]
    return [None if c in "xz" else int(c) for c in low]


def _slot_reads(evs: list[dict]) -> tuple[dict, dict]:
    """{slot: cells} from SLOT_READ and {slot: applied word} from SLOT_IN_READ, each after a SLOT_ADDR write."""
    q, inp, addr = {}, {}, None
    for e in evs:
        if e.get("op") == "wr" and e.get("addr") == rm.SLOT_ADDR and e.get("resp", 0) == 0:
            addr = e["data"] & 0x1F
        elif e.get("op") == "rd" and addr is not None and e.get("resp", 0) == 0:
            if e.get("addr") == rm.SLOT_READ:
                q[addr] = _cells_of(e)
            elif e.get("addr") == rm.SLOT_IN_READ and e.get("data") is not None:
                inp[addr] = e["data"]
    return q, inp


# ------------------------------------------------------------------ the P6 boundary
P7_OPS = ("cleanup", "close", "close_injection", "restore_init")


def _accepted_p7(e: dict) -> bool:
    return (e.get("op") == "wr" and e.get("addr") == rm.CTRL and e.get("resp", 0) == 0
            and any((e["data"] >> rm.CTRL_BITS[op]) & 1 for op in P7_OPS))


def acquisition_boundary(evs: list[dict], n_declared: int) -> tuple[int, str]:
    """The observation's terminal boundary, established from the carrier's ACQUISITION STATE as the host read it — never
    from an operation's name alone. Returns (index, how): `O` is built from `evs[:index]`.

      sealed              P6 was reached: init_done witnessed and as many set steps applied (STATUS step_index) as the
                          declared stimulus holds, no fault; the boundary is the first accepted P7+ operation after that
                          (nothing of P7–P10 enters O);
      stopped             the acquisition stopped at a fault the host read before any P7+ operation; the boundary is the
                          first accepted P7+ operation after the fault, or the end (the persistent slots read after the fault
                          belong to O's prefix);
      premature_refused   a P7+ operation was accepted on the bus BEFORE P6 and the engine refused it (a non-zero FAULT read
                          follows before the next CTRL write): O keeps everything up to and including that FAULT read — the
                          acquired prefix and the named fault at the phase actually reached (the owner's 2026-10-21 early
                          CLEANUP reproduction);
      premature_accepted  a P7+ operation the carrier accepted before P6 (fewer steps applied than declared): O ends before it
                          and is invalid with the host-recorded code `premature_operation`;
      open                the trace ends with neither P6, a fault nor a P7+ operation.
    A transaction close (X) exists only after `sealed`."""
    init_done, step_idx, fault_seen = False, 0, False
    for i, e in enumerate(evs):
        if e.get("op") == "rd" and e.get("resp", 0) == 0 and e.get("data") is not None:
            if e.get("addr") == rm.STATUS:
                st = rm.decode_status(e["data"])
                init_done = init_done or bool(st["init_done"])
                step_idx = max(step_idx, st["step_index"])
            elif e.get("addr") == rm.FAULT and e["data"] & 0xF:
                fault_seen = True
        if _accepted_p7(e):
            if fault_seen:
                return i, "stopped"
            if init_done and step_idx >= n_declared - 1:
                return i, "sealed"
            for j in range(i + 1, len(evs)):
                ej = evs[j]
                if ej.get("op") == "rd" and ej.get("addr") == rm.FAULT and ej.get("resp", 0) == 0 and (ej.get("data") or 0) & 0xF:
                    return j + 1, "premature_refused"
                if ej.get("op") == "wr" and ej.get("addr") == rm.CTRL:
                    break
            return i, "premature_accepted"
    return len(evs), ("stopped" if fault_seen else "open")


def _op_completed(evs: list[dict], i: int, op: str) -> bool:
    """An MMIO acknowledgement (OKAY on the CTRL write at `i`) is not the operation's completion: the engine refuses
    out-of-phase operations AFTER accepting the write. The completion witness is in the STATUS / FAULT reads that follow."""
    after = evs[i + 1:]
    faults = [e for e in after if e.get("op") == "rd" and e.get("addr") == rm.FAULT and (e.get("data") or 0) & 0xF]
    statuses = [rm.decode_status(e["data"]) for e in after if e.get("op") == "rd" and e.get("addr") == rm.STATUS and e.get("data") is not None]
    if faults:
        return False
    if op == "close":
        return any(st["configuration_valid_hw"] == 0 and st["idle"] == 1 for st in statuses)
    if op == "close_injection":
        return any(st["configuration_valid_hw"] == 0 and st["injection_open"] == 1 for st in statuses)
    return bool(statuses)


# ------------------------------------------------------------------ the builders
def _stim_item(applied: dict) -> dict:
    return {"kind": "set", "clock": applied["clock"], "ce": applied["ce"], "sr": applied["sr"], "d": applied["d"]}


def observation(evs: list[dict], links: dict, timing: dict, seq: int, session: str, predecessor: dict, declared_stimulus: list) -> dict:
    """Build `O` from one transaction's register trace and the task's DECLARED stimulus. The steps are the carrier's
    applied record (a sample and its applied inputs per slot); the declared stimulus is kept whole."""
    for k in ("instrument", "nonce", "config"):
        if k not in links:
            raise RecordRefusal(f"links: {k} missing (the instrument's PCAP path / manifest supplies it)")
    # the PCAP-side witnesses exist only when their link completed (contract 4.2's phase table): an absent one is never written as
    # a placeholder, and the stop phase cannot lie beyond the last link that completed (B4Q, 2026-10-27: the builder reads the
    # links the instrument's path actually produced; a complete O still requires all four)
    LINK_PHASE = (("commit", "P1"), ("staging_readback_sha256", "P1"), ("fabric_readback_sha256_pre_event", "P2"), ("fabric_readback_sha256_post_event", "P4"))
    cap = None
    for k, ph in LINK_PHASE:
        if k not in links:
            cap = ph if cap is None or PHASES.index(ph) < PHASES.index(cap) else cap
    if not isinstance(declared_stimulus, list) or not declared_stimulus:
        raise RecordRefusal("the declared stimulus is a non-empty list (its step 0 is the init event)")
    boundary, how = acquisition_boundary(evs, len(declared_stimulus))
    evs = evs[:boundary]                                  # the terminal boundary: nothing after it enters O
    q, inp = _slot_reads(evs)
    status_words = [rm.decode_status(e["data"]) for e in _reads(evs, rm.STATUS)]
    seen = {k: max((w[k] for w in status_words), default=0) for k in ("pre_sampled", "init_done", "cleanup_done", "restore_done", "step_index")}
    final = seen if status_words else None
    faults = [e["data"] & 0xF for e in _reads(evs, rm.FAULT)]
    witness = [rm.decode_witness(e["data"]) for e in _reads(evs, rm.WITNESS)]
    o = {"schema": SCHEMA_O, "schema_version": VERSION, "instrument": dict(links["instrument"]), "session": session, "seq": seq,
         "nonce": links["nonce"],
         **{k: links[k] for k, _ in LINK_PHASE if k in links},
         "init_event": {"mechanism": MECHANISM_NAMES[rm.MECHANISM], "parameters": {"assert_delay": timing["assert_delay"], "pulse_clocks": timing.get("pulse", 2),
                                                                                  "gsr_count_after": (witness[-1]["gsr_count"] if witness else 0),
                                                                                  "pre_init_cleanup": bool(witness and witness[-1].get("pre_init_cleanup"))}},
         "timing": {k: timing[k] for k in ("settle", "hold", "release", "sample_offset")},
         "predecessor": dict(predecessor), "config": list(links["config"]), "config_sha256": sha256_json(list(links["config"])),
         "stimulus": [dict(s) for s in declared_stimulus], "stimulus_sha256": sha256_json([dict(s) for s in declared_stimulus]),
         "elements": list(ELEMENTS), "steps": [], "status": "complete"}
    # the pre-init sample: only if the carrier took it (pre_sampled) and the host read slot 0 and its applied inputs
    pre_sampled = bool(final and final["pre_sampled"])          # the carrier's witness — never an accepted CTRL write the engine refused
    if pre_sampled and 0 in q and 0 in inp:
        a = rm.decode_applied(inp[0])
        o["initial"] = {"context": "a5_injection" if (witness and witness[-1]["pre_context_a5"]) else "idle",
                        "clock": a["clock"], "ce": 1 if a["ce"] else 0, "sr": 1 if a["sr"] else 0, "d": a["d"], "q": q[0]}
    # the steps: the acquired prefix — slot 1 = the init event (step 0), slot 2 + k = applied set step k
    init_done = bool(final and final["init_done"])
    steps, prev_event, clock, q_prev = [], "none", 0, (o["initial"]["q"] if "initial" in o else None)
    if init_done and 1 in q:
        steps.append({"step": 0, "kind": "init", "prev_event": "none", "clock_before": 0, "clock_after": 0, "edge": None,
                      "ce": 0, "sr": 0, "d": 0, "q_before": q_prev, "q_after": q[1]})
        prev_event, q_prev = "init", q[1]
        n = 1
        while (2 + n - 1) in q and (2 + n - 1) in inp:
            if final and n > final["step_index"]:
                break                                   # the cleanup slot (if read) is not a step
            a = rm.decode_applied(inp[2 + n - 1])
            c = a["clock"]
            edge = "rising" if (clock, c) == (0, 1) else "falling" if (clock, c) == (1, 0) else None
            steps.append({"step": n, "kind": "set", "prev_event": prev_event, "clock_before": clock, "clock_after": c, "edge": edge,
                          "ce": a["ce"], "sr": a["sr"], "d": a["d"], "q_before": q_prev, "q_after": q[2 + n - 1]})
            prev_event, clock, q_prev = ("edge" if edge else "level"), c, q[2 + n - 1]
            n += 1
    o["steps"] = steps
    code = rm.FAULT_CODES[faults[-1]] if (faults and faults[-1] != 0) else ("premature_operation" if how == "premature_accepted" else None)
    if code is None and how == "open" and len(steps) < len(declared_stimulus):
        raise RecordRefusal("the trace ends before the acquisition reached P6 and no fault stopped it: nothing to seal yet")
    if code is None and cap is not None:
        raise RecordRefusal(f"a complete observation needs every PCAP-side witness; the link of {cap} did not complete and no fault stopped the acquisition: nothing to seal")
    if code is not None:
        phase = "P5" if init_done else ("P3" if pre_sampled else "P2")
        if cap is not None and PHASES.index(cap) < PHASES.index(phase):
            phase = cap                                    # the stop lies where the instrument's path stopped producing witnesses
        o["status"] = "invalid"
        o["fault"] = {"code": code, "phase_reached": phase,
                      "step_reached": (final["step_index"] if (final and phase == "P5") else (0 if phase == "P3" else None))}
        for ph in PHASES[PHASES.index(phase) + 1:]:
            for k in O_PHASE[ph]:
                o.pop(k, None)
        if phase in ("P1", "P2"):
            o.pop("initial", None)
    return o


def observation_sha256(o: dict) -> str:
    return sha256_json(o)


def validate_task(task: dict, n_steps: int) -> list[str]:
    f = []
    if not isinstance(task, dict) or set(task) != {"mask", "target", "weights", "digest"}:
        return ["task: exactly mask, target, weights, digest"]
    m, t, w = task["mask"], task["target"], task["weights"]
    if not (isinstance(m, list) and isinstance(t, list) and isinstance(w, list) and len(m) == len(t) == len(w)):
        f.append("task: mask, target and weights must be lists of one length")
        return f
    for i, (cell, tv, wv) in enumerate(zip(m, t, w)):
        if not (isinstance(cell, (list, tuple)) and len(cell) == 2 and _is_int(cell[0]) and _is_int(cell[1]) and 1 <= cell[0] < n_steps and 0 <= cell[1] < 8):
            f.append(f"task.mask[{i}]: not a (step >= 1, element) cell inside the observation")
        if not (_is_int(tv) and tv in (0, 1)):
            f.append(f"task.target[{i}]: not a bit")
        if not (_is_int(wv) and wv >= 0):
            f.append(f"task.weights[{i}]: not a non-negative int")
    if not _hex(task["digest"], 64):
        f.append("task.digest")
    return f


def fitness(o: dict, task: dict) -> dict:
    """The executing side's fitness over the FULL mask on the physical values (contract 3.4 (i)); only for a complete,
    structurally valid observation; the task's dimensions validated first — nothing is truncated or zipped short."""
    if validate_observation(o):
        raise RecordRefusal("a fitness exists only for a structurally valid observation")
    if o["status"] != "complete":
        raise RecordRefusal("a fitness exists only for a complete observation")
    tf = validate_task(task, len(o["steps"]))
    if tf:
        raise RecordRefusal("; ".join(tf))
    grid = [s["q_after"] for s in o["steps"]]
    score = sum(w for (s, e), t, w in zip(task["mask"], task["target"], task["weights"]) if grid[s][e] == t)
    return {"schema": SCHEMA_F, "schema_version": VERSION, "observation_sha256": observation_sha256(o), "task_digest": task["digest"], "fitness": score}


def transaction_close(evs: list[dict], o: dict, seq: int, links: dict) -> dict:
    """`X` from the trace AFTER the P6 seal: closed (a CLOSE the engine COMPLETED after cleanup and the restore event — the
    base-state sample is the carrier's BASE_STATE register), injection_open (a CLOSE_INJECTION the engine completed), or
    faulted (the engine latched a fault after P6, with the stop phase from its witnesses: cleanup not done -> P7; cleanup
    done, restore not -> P9; restore done -> P10). A CTRL write the register file answered OKAY is NOT a completion.
    Without any of those the transaction is not closed and no X exists — and none exists unless the acquisition reached the
    P6 seal (`acquisition_boundary` = sealed): a premature operation or an acquisition fault leaves O invalid and no X."""
    k, how = acquisition_boundary(evs, len(o["stimulus"]))
    if how != "sealed":
        raise RecordRefusal(f"no transaction close: the acquisition never reached the P6 seal ({how})")
    after = evs[k:]
    q, inp = _slot_reads(evs)
    status_words = [rm.decode_status(e["data"]) for e in _reads(after, rm.STATUS)]
    seen = {key: max((w[key] for w in status_words), default=0) for key in ("cleanup_done", "cleanup_edge", "restore_done")}
    last = status_words[-1] if status_words else {}
    osha = observation_sha256(o)
    faults = [e["data"] & 0xF for e in _reads(after, rm.FAULT) if (e.get("data") or 0) & 0xF]
    closes = [i for i in range(k, len(evs)) if evs[i].get("op") == "wr" and evs[i].get("addr") == rm.CTRL and evs[i].get("resp", 0) == 0 and (evs[i]["data"] >> rm.CTRL_BITS["close"]) & 1]
    injections = [i for i in range(k, len(evs)) if evs[i].get("op") == "wr" and evs[i].get("addr") == rm.CTRL and evs[i].get("resp", 0) == 0 and (evs[i]["data"] >> rm.CTRL_BITS["close_injection"]) & 1]
    if closes and _op_completed(evs, closes[-1], "close"):
        n_steps = len(o["steps"]) - 1
        fq = q.get(2 + n_steps)
        base_reads = _reads(after, rm.BASE_STATE)
        if fq is None or not base_reads or "base_readback_sha256" not in links:
            raise RecordRefusal("a closed X needs the cleanup sample, the carrier's BASE_STATE read and the base readback")
        edge = bool(seen["cleanup_edge"])
        last_clock = o["steps"][-1]["clock_after"] if o["steps"] else 0
        return {"schema": SCHEMA_X, "schema_version": VERSION, "observation_sha256": osha, "seq": seq,
                "cleanup": {"steps": [{"clock_before": last_clock, "clock_after": 0, "edge": "falling" if edge else None, "ce": 0, "sr": 0, "d": 0, "q_after": fq}],
                            "final_q": fq},
                "base_readback_sha256": links["base_readback_sha256"], "base_state_sample": _cells_of(base_reads[-1]),
                "idle_status": last.get("idle", 0), "status": "closed"}
    if injections and _op_completed(evs, injections[-1], "close_injection"):
        return {"schema": SCHEMA_X, "schema_version": VERSION, "observation_sha256": osha, "seq": seq, "idle_status": last.get("idle", 0), "status": "injection_open"}
    if faults:
        phase = "P10" if seen["restore_done"] else ("P9" if seen["cleanup_done"] else "P7")
        x = {"schema": SCHEMA_X, "schema_version": VERSION, "observation_sha256": osha, "seq": seq, "idle_status": last.get("idle", 0),
             "fault": {"code": rm.FAULT_CODES[faults[-1]], "phase_reached": phase}, "status": "faulted"}
        if seen["cleanup_done"] and o["steps"] and q.get(2 + len(o["steps"]) - 1) is not None:
            fq = q[2 + len(o["steps"]) - 1]
            x["cleanup"] = {"steps": [{"clock_before": o["steps"][-1]["clock_after"], "clock_after": 0, "edge": "falling" if seen["cleanup_edge"] else None, "ce": 0, "sr": 0, "d": 0, "q_after": fq}], "final_q": fq}
        return x
    raise RecordRefusal("the transaction is not closed: no completed CLOSE / CLOSE_INJECTION and no fault after the observation")


def session_open(instrument: dict, startup_readback_sha256, base_frames_reference_sha256) -> dict:
    """The bootstrap record of contract 5.5: open only on equality of two real digests; refused otherwise."""
    ok = _hex(startup_readback_sha256, 64) and _hex(base_frames_reference_sha256, 64) and startup_readback_sha256 == base_frames_reference_sha256
    return {"schema": SCHEMA_SO, "schema_version": VERSION, "instrument": dict(instrument),
            "startup_readback_sha256": startup_readback_sha256, "base_frames_reference_sha256": base_frames_reference_sha256,
            "status": "open" if ok else "refused"}


# ------------------------------------------------------------------ layer 1: structure
def validate_observation(o) -> list[str]:
    if not isinstance(o, dict):
        return ["O: not an object"]
    f = []
    status = o.get("status")
    schema = dict(O_COMMON)
    if status == "complete":
        for ph in PHASES:
            schema.update(O_PHASE[ph])
        f += _closed(o, schema, "O")
    elif status == "invalid":
        schema["fault"] = lambda v: isinstance(v, dict)
        fault = o.get("fault")
        phase = fault.get("phase_reached") if isinstance(fault, dict) else None
        if phase not in PHASES:
            return _closed(o, schema, "O") + ["O.fault.phase_reached: not a phase"]
        for ph in PHASES[: PHASES.index(phase)]:
            schema.update(O_PHASE[ph])                      # completed phases: required
        f += _closed(o, schema | O_PHASE[phase], "O", optional=tuple(O_PHASE[phase]))   # the stop phase: optional
        f += _closed(fault, FAULT, "O.fault")
    else:
        return _closed(o, schema, "O") + ["O.status: not complete / invalid"]
    f += _closed(o.get("instrument"), INSTRUMENT, "O.instrument")
    f += _closed(o.get("predecessor"), PREDECESSOR, "O.predecessor")
    pred = o.get("predecessor") if isinstance(o.get("predecessor"), dict) else {}
    if pred.get("kind") == "session_root" and (pred.get("seq") is not None or pred.get("close_sha256") is not None):
        f.append("O.predecessor: the session root names no previous close")
    if pred.get("kind") in ("closed", "a5_injection") and (pred.get("seq") is None or pred.get("close_sha256") is None):
        f.append("O.predecessor: a closed / a5_injection predecessor names the previous close by seq and digest")
    f += _closed(o.get("init_event"), INIT_EVENT, "O.init_event")
    if isinstance(o.get("init_event"), dict):
        f += _closed(o["init_event"].get("parameters"), INIT_PARAMS, "O.init_event.parameters")
    f += _closed(o.get("timing"), TIMING, "O.timing")
    if "initial" in o:
        f += _closed(o["initial"], INITIAL, "O.initial")
        ini = o["initial"]
        if isinstance(ini, dict) and ini.get("context") == "idle" and (ini.get("clock"), ini.get("ce"), ini.get("sr"), ini.get("d")) != (0, 0, 0, 0):
            f.append("O.initial: under context idle the inputs are 0")
    stim = o.get("stimulus") if isinstance(o.get("stimulus"), list) else []
    for i, s in enumerate(stim):
        f += _closed(s, STIM_INIT if i == 0 else STIM_SET, f"O.stimulus[{i}]")
    steps = o.get("steps") if isinstance(o.get("steps"), list) else []
    for i, s in enumerate(steps):
        f += _closed(s, STEP, f"O.steps[{i}]")
    if f:
        f += _deny(o)
        return f
    # internal consistency (only once the shapes are right)
    if o["config_sha256"] != sha256_json(o["config"]):
        f.append("O.config_sha256 does not digest config under the carrier's encoding")
    if o["stimulus_sha256"] != sha256_json(o["stimulus"]):
        f.append("O.stimulus_sha256 does not digest the declared stimulus")
    pic = o["init_event"]["parameters"].get("pre_init_cleanup", False)
    if "initial" in o:
        held = (o["initial"]["clock"], o["initial"]["ce"], o["initial"]["sr"], o["initial"]["d"]) != (0, 0, 0, 0)
        if held != pic:
            f.append("O.init_event.parameters.pre_init_cleanup must be true exactly when the pre-init sample was taken with held inputs")
        if pic and o["initial"]["context"] != "a5_injection":
            f.append("O: a pre-init cleanup belongs to the a5_injection context only")
    if status == "complete":
        if len(steps) == 0:
            f.append("O: a complete observation has at least the init step")
        if len(steps) != len(stim):
            f.append(f"O: a complete observation applies every declared step ({len(steps)} of {len(stim)} acquired)")
        if "initial" not in o:
            f.append("O: a complete observation has the pre-init sample")
    else:
        if len(steps) > len(stim):
            f.append("O: more applied steps than declared")
        ph, sr = o["fault"]["phase_reached"], o["fault"]["step_reached"]
        # the phase table decides which ACQUISITIONS can exist, not only which readback keys (contract 4.2)
        if ph in ("P1", "P2") and (steps or "initial" in o or sr is not None):
            f.append(f"O: a stop in {ph} has no pre-init sample and no step")
        if ph == "P3" and (steps or sr not in (None, 0)):
            f.append("O: a stop in P3 has no step")
        if ph == "P4" and (len(steps) != 1 or "initial" not in o):
            f.append("O: a stop in P4 has the pre-init sample and exactly the init step")
        if ph == "P5" and (len(steps) < 1 or sr != len(steps) - 1):
            f.append("O.fault.step_reached does not equal the acquired prefix")
    for i, s in enumerate(steps):
        if s["step"] != i:
            f.append(f"O.steps[{i}].step")
        if i == 0:
            if s["kind"] != "init" or s["prev_event"] != "none" or s["edge"] is not None or (s["ce"], s["sr"], s["d"], s["clock_before"], s["clock_after"]) != (0, 0, 0, 0, 0):
                f.append("O.steps[0]: the init step's fields")
            if "initial" in o and s["q_before"] != o["initial"]["q"]:
                f.append("O.steps[0].q_before is not the pre-init sample")
        else:
            if s["kind"] != "set":
                f.append(f"O.steps[{i}].kind")
            d = stim[i] if i < len(stim) else None
            if d is None or (s["clock_after"], s["ce"], s["sr"], s["d"]) != (d["clock"], d["ce"], d["sr"], d["d"]):
                f.append(f"O.steps[{i}]: the applied step is not the declared step {i}")
            p = steps[i - 1]
            if s["clock_before"] != p["clock_after"] or s["q_before"] != p["q_after"]:
                f.append(f"O.steps[{i}]: the chain from step {i - 1} (clock_before / q_before)")
            want_edge = "rising" if (s["clock_before"], s["clock_after"]) == (0, 1) else "falling" if (s["clock_before"], s["clock_after"]) == (1, 0) else None
            if s["edge"] != want_edge:
                f.append(f"O.steps[{i}].edge")
            want_prev = "init" if i == 1 else ("edge" if p["edge"] else "level")
            if s["prev_event"] != want_prev:
                f.append(f"O.steps[{i}].prev_event")
            if s["ce"] not in (0, 255) or s["sr"] not in (0, 255):
                f.append(f"O.steps[{i}]: an applied ce / sr vector is uniform on this carrier")
    f += _deny(o)
    return f


def _deny(o) -> list[str]:
    hit = _keys_at_all_levels(o) & DENY
    return [f"deny-listed key names: {sorted(hit)}"] if hit else []


def validate_fitness(fr, o) -> list[str]:
    if not isinstance(fr, dict):
        return ["F: not an object"]
    f = _closed(fr, F_SCHEMA, "F")
    if f:
        return f + _deny(fr)
    if validate_observation(o) or o.get("status") != "complete":
        f.append("F: the observation it names is not a valid complete observation")
    elif fr["observation_sha256"] != observation_sha256(o):
        f.append("F does not bind this O")
    return f + _deny(fr)


def validate_close(x, o) -> list[str]:
    if not isinstance(x, dict):
        return ["X: not an object"]
    status = x.get("status")
    schema = dict(X_COMMON)
    if status == "closed":
        schema.update(X_CLOSED)
    elif status == "faulted":
        schema.update(X_FAULTED); schema.update(X_CLOSED)
        f = _closed(x, schema, "X", optional=tuple(X_CLOSED))
    elif status != "injection_open":
        return _closed(x, schema, "X") + ["X.status: not closed / injection_open / faulted"]
    if status != "faulted":
        f = _closed(x, schema, "X")
    if isinstance(x.get("cleanup"), dict):
        cf = _closed(x["cleanup"], CLEANUP, "X.cleanup")
        f += cf
        if not cf:
            sf = _closed(x["cleanup"]["steps"][0], CLEANUP_STEP, "X.cleanup.steps[0]")
            f += sf
            if not sf and x["cleanup"]["steps"][0]["q_after"] != x["cleanup"]["final_q"]:
                f.append("X.cleanup.final_q is not the cleanup sample")
    if isinstance(x.get("fault"), dict):
        f += _closed(x["fault"], X_FAULT, "X.fault")
    if f:
        return f + _deny(x)
    if validate_observation(o):
        f.append("X: the observation it names is not structurally valid")
    elif x["observation_sha256"] != observation_sha256(o):
        f.append("X does not bind this O")
    else:
        if x["seq"] != o["seq"]:
            f.append("X.seq is not the observation's seq")
        if "cleanup" in x and o.get("steps"):
            c = x["cleanup"]["steps"][0]
            last_clock = o["steps"][-1]["clock_after"]
            if c["clock_before"] != last_clock:
                f.append("X.cleanup does not continue the observation's final clock")
            if c["edge"] != ("falling" if last_clock == 1 else None):
                f.append("X.cleanup.edge does not follow from the final clock")
    if status == "closed" and x["idle_status"] != 1:
        f.append("X: a closed transaction ends idle")
    if status == "injection_open" and x["idle_status"] != 0:
        f.append("X: an injection leaves the inputs held, not idle")
    if status == "closed" and o.get("status") != "complete":
        f.append("X: only a complete observation closes")
    return f + _deny(x)


def validate_session_open(so) -> list[str]:
    if not isinstance(so, dict):
        return ["session_open: not an object"]
    f = _closed(so, SO_SCHEMA, "session_open")
    if not f:
        f += _closed(so["instrument"], INSTRUMENT, "session_open.instrument")
    if f:
        return f + _deny(so)
    want = "open" if so["startup_readback_sha256"] == so["base_frames_reference_sha256"] else "refused"
    if so["status"] != want:
        f.append("session_open.status does not follow from the comparison")
    return f + _deny(so)


# ------------------------------------------------------------------ layer 2: binding to the trusted context
def validate_bound(o, ctx: dict, fr=None, x=None) -> list[str]:
    """`ctx`: instrument (the manifest's), session, stimulus (the task's declared steps), config (the planned genome
    list), task (the TRUSTED task: mask, target, weights, digest — the fitness is recomputed from it), predecessor_close_sha256
    and predecessor_seq (None for the root), nonce (what the PL showed), mechanism 'b', pulse_clocks, and two DISTINCT trusted
    frame references in their own hash domains (contract 5.5, design section 3): `loaded_frames_reference_sha256` — the
    loaded natural carrier image (CEUSEDMUX = SRUSEDMUX = 1), which session_open binds — and `base_readback_sha256` — the
    restored study base (signed base genome 0) that every closed X's P8 readback binds. They differ by those mux bits."""
    f = validate_observation(o)
    if f:
        return f
    if o["instrument"] != ctx["instrument"]:
        f.append("bound: O.instrument is not the manifest's instrument")
    if o["instrument"]["variant"] != f"{rm.VARIANT_WORD:08x}":
        f.append("bound: the carrier VARIANT is not the v2 word")
    if o["session"] != ctx["session"]:
        f.append("bound: O.session is not this session")
    if o["stimulus"] != ctx["stimulus"]:
        f.append("bound: O.stimulus is not the task's declared stimulus")
    if o["config"] != list(ctx["config"]):
        f.append("bound: O.config is not the planned configuration")
    if o["nonce"] != ctx["nonce"]:
        f.append("bound: O.nonce is not the nonce the PL showed")
    if o["predecessor"]["close_sha256"] != ctx["predecessor_close_sha256"]:
        f.append("bound: O.predecessor does not name the previous close")
    if ctx.get("mechanism", "b") == "b":
        rb = [o.get(k) for k in ("staging_readback_sha256", "fabric_readback_sha256_pre_event", "fabric_readback_sha256_post_event") if k in o]
        if len(set(rb)) > 1:
            f.append("bound: mechanism (b) frame invariance — staging, pre-event and post-event readbacks must be equal")
    if o["init_event"]["parameters"]["pulse_clocks"] != ctx.get("pulse_clocks", o["init_event"]["parameters"]["pulse_clocks"]):
        f.append("bound: pulse_clocks is not the identity page's")
    if o["predecessor"]["kind"] != "session_root":
        if ctx.get("predecessor_seq") is not None and o["predecessor"]["seq"] != ctx["predecessor_seq"]:
            f.append("bound: O.predecessor.seq is not the previous close's seq")
        if ctx.get("predecessor_seq") is not None and o["seq"] != ctx["predecessor_seq"] + 1:
            f.append("bound: O.seq does not follow the previous close")
    if fr is not None:
        f += validate_fitness(fr, o)
        task = ctx.get("task")
        if not f and task is None:
            f.append("bound: no trusted task in the context to recompute the fitness")
        if not f:
            if fr["task_digest"] != task["digest"]:
                f.append("bound: F.task_digest is not the trusted task's")
            else:
                try:
                    if fitness(o, task)["fitness"] != fr["fitness"]:
                        f.append("bound: F.fitness is not the score recomputed over the full physical grid under the trusted task")
                except RecordRefusal as e:
                    f.append(f"bound: {e}")
    if x is not None:
        f += validate_close(x, o)
        if not f and x["status"] == "closed":
            if not _hex(ctx.get("base_readback_sha256"), 64):
                f.append("bound: no trusted restored-base frame reference (ctx.base_readback_sha256) to bind X")
            elif x["base_readback_sha256"] != ctx["base_readback_sha256"]:
                f.append("bound: X.base_readback_sha256 is not the trusted restored study-base (signed base genome 0) frame reference")
    return f


# ------------------------------------------------------------------ layer 3: the chain
def validate_chain(so, records: list[dict]) -> list[str]:
    """`records`: [{o, x, ctx, f?}] in session order; the first is the root.

    The session-opening record binds the LOADED-IMAGE frame reference of every transaction's trusted context
    (`ctx.loaded_frames_reference_sha256`, the loaded natural carrier image) and the manifest's instrument — a session_open
    naming another carrier or a reference of its own choosing opens nothing, whatever its two digests say to each other.
    The RESTORED STUDY-BASE reference (`ctx.base_readback_sha256`, signed base genome 0) is a different commitment in a
    different hash domain, bound by each closed X (validate_bound); the two are never compared to each other.

    Every source record's SHAPE is validated before it is traversed: a malformed session_open, entry, O or X is a named
    finding and the terminal result for the chain at that point — nothing of a malformed value is dereferenced."""
    f = validate_session_open(so)
    if f:
        return f + ["chain: the session-opening record is malformed; no transaction can be bound to it"]
    if so["status"] != "open":
        return ["chain: the session did not open"]
    if not isinstance(records, list):
        return ["chain: records is not a list"]
    prev_x = None
    for i, r in enumerate(records):
        if not isinstance(r, dict) or not isinstance(r.get("o"), dict) or not isinstance(r.get("ctx"), dict):
            f.append(f"chain[{i}]: a record entry is {{o, x, ctx}} with objects; the chain ends here"); break
        o, x, ctx = r["o"], r.get("x"), r["ctx"]
        shape = validate_observation(o)
        if not shape and x is not None:
            shape = validate_close(x, o)
        if shape:
            f += [f"chain[{i}]: {m}" for m in shape]
            f.append(f"chain[{i}]: a malformed record; the chain ends here"); break
        if so["instrument"] != ctx.get("instrument"):
            f.append(f"chain[{i}]: session_open.instrument is not the trusted context's instrument")
        if not _hex(ctx.get("loaded_frames_reference_sha256"), 64):
            f.append(f"chain[{i}]: no trusted loaded-image frame reference (ctx.loaded_frames_reference_sha256) to bind session_open")
        elif so["base_frames_reference_sha256"] != ctx["loaded_frames_reference_sha256"]:
            f.append(f"chain[{i}]: session_open does not name the pinned loaded-image frame reference")
        kind = o["predecessor"]["kind"]                    # O's shape is valid: predecessor is a closed object
        if i == 0 and kind != "session_root":
            f.append("chain: the first transaction is the session root")
        if i > 0:
            want_kind = "a5_injection" if prev_x["status"] == "injection_open" else "closed"
            if kind != want_kind:
                f.append(f"chain[{i}]: predecessor.kind must be {want_kind} after the previous close")
        exp_prev = sha256_json(prev_x) if prev_x is not None else None
        exp_seq = prev_x["seq"] if prev_x is not None else None
        f += [f"chain[{i}]: {m}" for m in validate_bound(o, {**ctx, "predecessor_close_sha256": exp_prev, "predecessor_seq": exp_seq}, r.get("f"), x)]
        if x is None:
            f.append(f"chain[{i}]: no transaction close; the chain ends here"); break
        if x["status"] == "faulted":                      # X's shape is valid: fault is a closed object
            f.append(f"chain[{i}]: the transaction faulted at {x['fault']['phase_reached']}; the chain ends here"); break
        prev_x = x
    return f
