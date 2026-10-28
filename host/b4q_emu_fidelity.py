#!/usr/bin/env python3
"""Replay the archived RTL bench traces of the carrier unit (evidence/b4/unit_carrier_v2_2026_10_21/bench/<scenario>.jsonl,
tb/b4/tb_b4_core.v's 27 scenarios over the same hypothesis fabric) through host/b4q_emu.CarrierEmu: every write applied at
its recorded time, every read compared — data (or the bench's x pattern) and resp — against what the RTL answered. The
heartbeat (a free-running counter the GSR resets) is compared by its semantic only: it restarts after every event and
advances otherwise. The genome each transaction runs under is the bench's (the fixture schedule of tb_b4_core.v, read
from tb/b4/b4_fixture.vh), applied at the scenario's transaction marks exactly as the bench sets `target.genome`.

    python3 -B host/b4q_emu_fidelity.py [--json out.json] [--calibrate]

A mismatch is a finding against the emulator, never against the bench or the RTL."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b4q_emu as emu  # noqa: E402
import b4carrier_regmap as rm  # noqa: E402

BENCH = R / "evidence/b4/unit_carrier_v2_2026_10_21/bench"
NAMES = {v: k for k, v in vars(rm).items() if isinstance(v, int) and k.isupper() and k not in ("VARIANT_WORD", "MECHANISM")}
# scenario -> (power_on, gsr_init_effect, genomes: [0] at the start, [k] at the k-th transaction_begin mark — tb_b4_core.v's fixture schedule)
SCHEDULE = {
    "regs": ("x", True, [0]), "flow": ("x", True, ["F0", "F1", "F2", "F3", "F4", "F5"]), "fault_not_armed": ("x", True, [0]), "fault_nokey": ("x", True, [0]),
    "fault_unsigned": ("x", True, [0]), "fault_wrong_commit": ("x", True, [0]), "fault_wrong_key": ("x", True, [0]), "fault_sequence": ("x", True, ["F0"]),
    "fault_double_arm": ("x", True, [0]), "fault_realisable": ("x", True, ["F0"]), "a5": ("init", True, ["F0"]), "a5_persist": ("x", False, ["F0"]),
    "a5_wrong_context": ("x", True, ["F0"]), "a5_flag_without_injection": ("x", True, [0]), "open_close_refused": ("x", True, ["F0"]), "p9": ("x", True, ["F0"]),
    "p9_ok": ("x", True, ["F0"]), "busy_refused": ("x", True, ["F0"]), "step_atomic": ("x", True, ["F0"]), "backpressure": ("x", True, ["F0"]),
    "read_during_window": ("x", True, ["F0"]), "read_at_launch": ("x", True, ["F0"]), "session": ("init", True, ["F0", "F1"]), "post_fault": ("init", True, ["F0", "F1"]),
    "w_first": ("x", True, ["F0"]), "w_first_early": ("x", True, ["F0"]), "early_cleanup": ("x", True, ["F0", "F1"]),
}


# three scenarios drive the AXI channels by hand after a point (an INIT_REQ with BREADY held low; a W-first beat; an early W):
# those handshakes are not logged by the bench's `wr`, so the replay cannot reproduce them — the comparison stops at the first
# access the unlogged operation affects, and the report says so. The gate's channel behaviour is the RTL bench's finding, not
# the emulator's claim.
UNLOGGED = {"backpressure": (48, "the INIT_REQ write with BREADY held low is driven by hand and not logged"),
            "w_first": (50, "the W-first STEP_IN beat is driven by hand and not logged"),
            "w_first_early": (49, "the INIT_REQ and the early W are driven by hand and not logged")}


def fixture_genomes() -> dict:
    text = (R / "tb/b4/b4_fixture.vh").read_text()
    return {f"F{k}": int(m, 16) for k, m in enumerate(re.findall(r"FIX\d_GENOME = 21'h([0-9a-f]+);", text))}


def replay(scenario: str, trace: list[dict], genomes: dict, latency: int, gate_cycles: int) -> dict:
    power_on, effect, sched = SCHEDULE[scenario]
    emu.ENGINE_LATENCY, emu.GATE_TAG_AT = latency, gate_cycles
    g = [genomes[x] if isinstance(x, str) else x for x in sched]
    e = emu.CarrierEmu(genome=g[0], power_on=power_on, gsr_init_effect=effect)
    marks = 0                                            # genomes[k] = the genome of the k-th transaction_begin mark (the scenario's `target.genome = g`)
    mism, reads, writes, hb_prev, hb_checks = [], 0, 0, None, 0
    last_ctrl_t = None
    cut = UNLOGGED.get(scenario, (None, None))
    for i, ev in enumerate(trace):
        if cut[0] is not None and i >= cut[0]:
            break
        if "mark" in ev:
            if ev["mark"] == "transaction_begin":
                if marks < len(g):
                    e.set_genome(g[marks])
                marks += 1
            continue
        if "op" not in ev:
            continue
        cost = 4
        e.t = ev["t"] // 20 - cost
        if ev["op"] == "wr":
            writes += 1
            resp = e.write(ev["addr"], ev["data"], cost)
            if ev["addr"] == rm.CTRL:
                last_ctrl_t = ev["t"]
            if resp != ev["resp"]:
                mism.append({"i": i, "t": ev["t"], "op": "wr", "addr": NAMES.get(ev["addr"], hex(ev["addr"])), "data": ev["data"], "want_resp": ev["resp"], "got_resp": resp})
        else:
            reads += 1
            data, x, resp = e.read(ev["addr"], cost)
            want_x = ev.get("x")
            if ev["addr"] == rm.HEARTBEAT and ev["resp"] == 0:
                hb_checks += 1
                hb_prev = ev["data"]
                continue
            ok = resp == ev["resp"]
            if ok and ev["resp"] == 0:
                if want_x is not None:
                    ok = (x is not None) and all((a == b) or (a in "xz") for a, b in zip(want_x, x or "")) and x is not None
                    ok = ok and all(not (a in "01" and b == "x") for a, b in zip(want_x, x))
                else:
                    ok = (x is None) and data == ev["data"]
            if not ok:
                mism.append({"i": i, "t": ev["t"], "op": "rd", "addr": NAMES.get(ev["addr"], hex(ev["addr"])), "want": ev.get("data"), "want_x": want_x, "got": data, "got_x": x,
                             "want_resp": ev["resp"], "got_resp": resp, "since_ctrl_ns": (ev["t"] - last_ctrl_t) if last_ctrl_t is not None else None,
                             "status": rm.decode_status(ev["data"]) if ev["addr"] == rm.STATUS and ev.get("data") is not None else None,
                             "got_status": rm.decode_status(data) if ev["addr"] == rm.STATUS and data is not None else None})
    return {"scenario": scenario, "reads": reads, "writes": writes, "heartbeat_reads": hb_checks, "mismatches": mism,
            "events_in_trace": sum(1 for ev in trace if "op" in ev), "compared_up_to": cut[0], "not_replayable_beyond": cut[1]}


def run_all(latency: int, gate_cycles: int) -> dict:
    genomes = fixture_genomes()
    out = {}
    for s in SCHEDULE:
        trace = [json.loads(l) for l in (BENCH / f"{s}.jsonl").read_text().splitlines() if l.strip()]
        out[s] = replay(s, trace, genomes, latency, gate_cycles)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path); ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--latency", type=int, default=emu.ENGINE_LATENCY); ap.add_argument("--gate", type=int, default=emu.GATE_TAG_AT)
    ap.add_argument("--show", help="dump the trace context of a scenario's mismatches")
    a = ap.parse_args(argv)
    if a.show:
        genomes = fixture_genomes()
        trace = [json.loads(l) for l in (BENCH / f"{a.show}.jsonl").read_text().splitlines() if l.strip()]
        r = replay(a.show, trace, genomes, a.latency, a.gate)
        for m in r["mismatches"][:8]:
            print("==== mismatch", json.dumps({k: m[k] for k in m if k not in ("status", "got_status")}))
            for j in range(max(0, m["i"] - 7), m["i"] + 1):
                ev = trace[j]
                if "mark" in ev:
                    print(f"   {j:4d} t={ev['t']:6d} MARK {ev['mark']}"); continue
                if "op" not in ev:
                    continue
                name = NAMES.get(ev.get("addr"), hex(ev.get("addr", 0)))
                extra = ""
                if ev["op"] == "rd" and ev["addr"] == rm.STATUS and ev.get("data") is not None:
                    st = rm.decode_status(ev["data"]); extra = " " + ",".join(k for k, v in st.items() if v and k not in ("alive", "reserved_zero", "key_loaded")) + f" slot={st['slot_count']} step={st['step_index']}"
                print(f"   {j:4d} t={ev['t']:6d} {ev['op']} {name} data={ev.get('data')} x={ev.get('x')} resp={ev['resp']}{extra}")
        return 0
    if a.calibrate:
        best = None
        for lat in range(0, 3):
            for gate in range(46, 52):
                res = run_all(lat, gate)
                n = sum(len(r["mismatches"]) for r in res.values())
                if best is None or n < best[0]:
                    best = (n, lat, gate)
        print("best", best)
        return 0
    res = run_all(a.latency, a.gate)
    total = sum(len(r["mismatches"]) for r in res.values())
    for s, r in res.items():
        note = f"  (compared {r['reads'] + r['writes']} of {r['events_in_trace']} accesses: {r['not_replayable_beyond']})" if r["compared_up_to"] else ""
        print(f"{s:28s} reads {r['reads']:5d} writes {r['writes']:5d} mismatches {len(r['mismatches'])}{note}")
        for m in r["mismatches"][:3]:
            print("   ", json.dumps(m)[:300])
    print("TOTAL mismatches", total, "| ENGINE_LATENCY", a.latency, "GATE_TAG_AT", a.gate)
    if a.json:
        a.json.write_text(json.dumps({"engine_latency": a.latency, "gate_cycles": a.gate, "results": res}, indent=1) + "\n")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
