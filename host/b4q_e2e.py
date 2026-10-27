#!/usr/bin/env python3
"""B4Q — the OFFLINE END-TO-END driver: the executing-side program against the host transport, through the session runner,
over the scenario set the owner's ruling names — session open / root, a normal P1–P10 transaction and close, the A5 injection
protocol (J1–J3), an A8-style 2 x 2 cross and an A2 pair of the plan's record types (mechanics on the hypothesis model, no
qualification claim), and the negatives: refusals (the notary, the gate under a wrong key), a fault inside the stimulus (a
non-uniform step), a DevC fault that stops a link, an unmodelled endpoint (a latch: the carrier record is refused for its
None cells — the host emulation's limit), the persisting fabric (A5 fail data), an external interruption. Every scenario is
its own session in its own directory under the evidence root; the summary names what each produced; host/b4q_verify.py
re-reads every directory in a fresh process. Fixtures are explicit and hermetic (no production registry, no seed)."""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4q_session as ss  # noqa: E402
import b4q_qual as ql  # noqa: E402
import b4_ff_model as fm  # noqa: E402

KEY_B = bytes(range(16, 32))


def u8(v): return 0xFF if v else 0x00


def stim(steps):
    return [fm.init()] + [fm.set_(c, u8(ce), u8(sr), d) for (c, ce, sr, d) in steps]


FIX0 = [(1, 0, 0, 0x5A), (0, 0, 0, 0xA5), (1, 0, 0, 0xA5), (0, 0, 0, 0x00), (1, 0, 0, 0x0F), (1, 0, 0, 0xF0), (0, 0, 0, 0xF0)]
FIX1 = [(1, 1, 0, 0x33), (0, 1, 0, 0x33), (1, 0, 0, 0xCC), (0, 0, 1, 0x00), (1, 1, 0, 0x0F), (0, 1, 1, 0x0F), (1, 1, 0, 0x55)]
FIX2 = [(1, 1, 0, 0xFF), (0, 1, 1, 0xFF), (1, 1, 1, 0x00), (0, 1, 0, 0x00), (1, 1, 0, 0x81), (0, 0, 0, 0x81), (1, 0, 0, 0x7E)]
G_BASE, G_CESR, G_SYNC, G_LATCH = 0x000000, (1 << 4) | (1 << 3), (1 << 0) | (1 << 3) | (1 << 4) | (1 << 8) | (1 << 2) | (1 << 17), (1 << 10) | (1 << 6) | (1 << 4)
# the demonstration stimulus of contract 6.5 on this carrier (slice-wide inputs; CE driven, SR driven background):
#   C0: a capture of 0; C1: a capture of 1; E0: capture 1 (prior P0 = 1), SR level, edge with d = 0 under SR; E1: capture 0 (P1 = 0), SR level, edge with d = 1 under SR
DEMO = [(1, 1, 0, 0x00), (0, 1, 0, 0x00),                  # 1 K0 (edge), 2
        (1, 1, 0, 0xFF), (0, 1, 0, 0xFF),                  # 3 K1 (edge), 4
        (1, 1, 0, 0xFF), (0, 1, 0, 0xFF),                  # 5 P0 (edge, d = 1), 6
        (0, 1, 1, 0x00), (1, 1, 1, 0x00), (0, 1, 0, 0x00),  # 7 SR level, 8 R0 (edge, d = 0 under SR), 9
        (1, 1, 0, 0x00), (0, 1, 0, 0x00),                  # 10 P1 (edge, d = 0), 11
        (0, 1, 1, 0xFF), (1, 1, 1, 0xFF), (0, 1, 0, 0xFF)]  # 12 SR level, 13 R1 (edge, d = 1 under SR), 14
DEMO_PARTS = {"K0": 1, "K1": 3, "P0": 5, "R0": 8, "P1": 10, "R1": 13}
# the A2 demonstration of the ce_mode row: a capture of 0 under CE, then a capture attempted with CE LOW — a tied-high CE captures the 1,
# a driven CE blocks it (under the DEMO stimulus CE is asserted throughout, so the ce_mode bit has nothing to show there)
CE_DEMO = [(1, 1, 0, 0x00), (0, 1, 0, 0x00), (1, 0, 0, 0xFF), (0, 0, 0, 0xFF)]
A2_STIMULI = {"ce_mode": CE_DEMO, "storage_kind": DEMO}
BIT_INIT_AFF, BIT_SRVAL_AFF = 13, 8


def task_for(n_steps: int, label: str) -> dict:
    mask = [(s, e) for s in range(1, n_steps + 1) for e in range(8)]
    return {"mask": mask, "target": [0] * len(mask), "weights": [1] * len(mask), "digest": hashlib.sha256(f"b4q-e2e-task|{label}|{n_steps}".encode()).hexdigest()}


def run_session(root: Path, name: str, body, **kw) -> dict:
    out = root / name
    s = ss.Session(out, label=f"B4Q-host-{name}", **kw)
    s.start()
    t0 = time.time()
    try:
        extra = body(s) or {}
    finally:
        s.stop()
    m = s.write()
    summary = {"name": name, "wall_s": round(time.time() - t0, 3), "records": m["records"], "chain_findings": m["chain_findings"], "accesses": m["accesses"], **extra}
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def scenario_valid(s: ss.Session) -> dict:
    so = s.open(); assert so["findings"] == [], so["findings"]
    s.transaction("root", 0, stim([]))
    s.transaction("normal", G_BASE, stim(FIX0), task_for(7, "fix0"))
    s.transaction("normal", G_CESR, stim(FIX1), task_for(7, "fix1"))
    s.transaction("normal", G_SYNC, stim(FIX2), task_for(7, "fix2"))
    return {}


def scenario_a5(s: ss.Session, cprime=(1, 1, 0, 0x00)) -> dict:
    """J1 c observed; J2 c′ (every element driven opposite to the init value 1, inputs held) closed with CLOSE_INJECTION; J3 c again
    under the A5 flag; then a normal candidate after."""
    s.open(); s.transaction("root", 0, stim([]))
    j1 = s.transaction("normal", G_CESR, stim(FIX1))
    j2 = s.transaction("inject", G_CESR, stim([cprime]))
    j3 = s.transaction("a5", G_CESR, stim(FIX1))
    after = s.transaction("normal", G_BASE, stim(FIX0), task_for(7, "after-a5"))
    v = ql.a5_verdict(j1["o"], j2["o"], j3["o"], j1["x"], j3["x"], j2["x"])
    s.qual_plan["a5"].append({"J1": j1["seq"], "J2": j2["seq"], "J3": j3["seq"], "conclusion_file": "a5_verdict.json"})
    (s.out / "a5_verdict.json").write_text(json.dumps(v, indent=1) + "\n")
    return {"a5": v["verdict"], "a5_why": v.get("why")}


def scenario_a8_cross(s: ss.Session) -> dict:
    s.open(); s.transaction("root", 0, stim([]))
    corners, recs, closes = {}, {}, {}
    for c in ("00", "01", "10", "11"):
        g = G_CESR | (int(c[0]) << BIT_INIT_AFF) | (int(c[1]) << BIT_SRVAL_AFF)
        e = s.transaction("normal", g, stim(DEMO))
        recs[c] = e; corners[c] = e["o"]; closes[c] = e["x"]
    out = {"AFF": ql.a8_classify(corners, 0, DEMO_PARTS, closes=closes), "BFF": ql.a8_classify(corners, 2, DEMO_PARTS, closes=closes)}   # the main element the cross is on, and a bystander
    s.qual_plan["a8"].append({"background_hex": f"{G_CESR:06x}", "bits": {"ff_init": BIT_INIT_AFF, "ff_srval": BIT_SRVAL_AFF}, "corners": {c: recs[c]["seq"] for c in corners},
                              "parts": DEMO_PARTS, "element": "AFF", "elements": {"AFF": 0, "BFF": 2}, "conclusion_file": "a8_cross.json"})   # AFF qualified; BFF a declared bystander
    (s.out / "a8_cross.json").write_text(json.dumps(out, indent=1) + "\n")
    return {"a8_AFF": out.get("AFF", {}).get("verdict"), "a8_BFF": out.get("BFF", {}).get("verdict")}


def scenario_a2(s: ss.Session) -> dict:
    s.open(); s.transaction("root", 0, stim([]))
    rows = {}
    for sem, g0, g1 in (("ce_mode", 0x000000, 0x000010), ("storage_kind", 0x000000, 0x000400)):
        a = s.transaction("normal", g0, stim(A2_STIMULI[sem]))
        if s.halted:                                                       # the latch endpoint's refused record halts the session (R1): the row stays not assessable
            rows[sem] = {"verdict": "not_assessable", "why": "the session halted before the second endpoint: " + s.halted, "g0_findings": a["findings"], "g1_findings": None}
            s.qual_plan["a2"].append({"semantic": sem, "g0_hex": f"{g0:06x}", "g1_hex": f"{g1:06x}", "g0": a["seq"], "g1": None, "conclusion_file": "a2_rows.json"})
            break
        b = s.transaction("normal", g1, stim(A2_STIMULI[sem]))
        rows[sem] = ql.a2_row(a["o"] if not a["findings"] else None, b["o"] if not b["findings"] else None, a["x"], b["x"])
        rows[sem]["g0_findings"], rows[sem]["g1_findings"] = a["findings"], b["findings"]
        s.qual_plan["a2"].append({"semantic": sem, "g0_hex": f"{g0:06x}", "g1_hex": f"{g1:06x}", "g0": a["seq"], "g1": b["seq"], "conclusion_file": "a2_rows.json"})
    (s.out / "a2_rows.json").write_text(json.dumps(rows, indent=1) + "\n")
    return {"a2": {k: v["verdict"] for k, v in rows.items()}}


def scenario_not_realisable(s: ss.Session) -> dict:
    s.open(); s.transaction("root", 0, stim([]))
    bad = stim(FIX0[:2]) + [{"kind": "set", "clock": 0, "ce": 0x3C, "sr": 0, "d": 0xA5}] + stim(FIX0[3:])[1:]
    e = s.transaction("normal", G_BASE, bad, task_for(7, "bad"))
    signed_before = len(s.notary.log)
    try:
        s.transaction("normal", G_BASE, stim(FIX0)); refused = None       # must not happen: the session halted on the invalid record
    except ss.SessionRefusal as ex:
        refused = str(ex)
    return {"invalid_phase": e["o"]["fault"]["phase_reached"] if e["o"] else None, "invalid_code": e["o"]["fault"]["code"] if e["o"] else None,
            "next_refused": refused, "signed_after": len(s.notary.log) - signed_before, "halted": s.halted}


def scenario_wrong_key(s: ss.Session) -> dict:
    s.open(); e = s.transaction("root", 0, stim([]))
    return {"root_status": e["firmware"]["status"], "root_reason": e["firmware"]["reason"], "o_status": e["o"]["status"] if e["o"] else None, "o_phase": e["o"]["fault"]["phase_reached"] if e["o"] else None}


def scenario_notary_refuses(s: ss.Session) -> dict:
    s.open(); s.transaction("root", 0, stim([]))
    e = s.transaction("normal", G_CESR, stim(FIX1))
    return {"status": e["firmware"]["status"], "reason": e["firmware"]["reason"], "o": e["o"] is not None, "findings": e["findings"]}


def scenario_dma_never(s: ss.Session) -> dict:
    s.open(); s.transaction("root", 0, stim([]))
    e = s.transaction("normal", G_BASE, stim(FIX0))
    return {"status": e["firmware"]["status"], "phase": e["firmware"]["phase"], "reason": e["firmware"]["reason"], "o": e["o"] is not None, "findings": e["findings"]}


def scenario_latch(s: ss.Session) -> dict:
    s.open(); s.transaction("root", 0, stim([]))
    e = s.transaction("normal", G_LATCH, stim(FIX0), task_for(7, "latch"))
    try:
        s.transaction("normal", G_BASE, stim(FIX0)); refused = None
    except ss.SessionRefusal as ex:
        refused = str(ex)
    return {"status": e["firmware"]["status"], "o_status": e["o"]["status"] if e["o"] else None, "findings": e["findings"][:3], "unmodelled_reads": e["emulation"]["unmodelled_cells"], "next_refused": refused}


def scenario_interrupt(s: ss.Session) -> dict:
    s.open(); s.transaction("root", 0, stim([]))
    e = s.transaction("normal", G_BASE, stim(FIX0))
    return {"status": e["firmware"]["status"], "interrupted": e["interrupted"], "o": e["o"] is not None, "findings": e["findings"]}


def _step_in_slverr(s: ss.Session) -> dict:
    """STEP_IN answered SLVERR without a change: no STEP is launched on the stale word"""
    s.open(); s.transaction("root", 0, stim([]))
    s.backend.refuse_writes.add(0x2038)
    e = s.transaction("normal", G_BASE, stim(FIX0[:2]))
    steps = [ev for ev in s.backend.trace[e["trace_range"][0]:] if ev.get("op") == "wr" and ev.get("addr") == 0x2000 and ev.get("data") == 0x800]
    return {"status": e["firmware"]["status"], "phase": e["firmware"]["phase"], "reason": e["firmware"]["reason"], "step_launches": len(steps), "o": e["o"] is not None, "o_status": e["o"]["status"] if e["o"] else None, "halted": s.halted}


def _read_slverr(s: ss.Session, arm, want_phase: str) -> dict:
    """a read answered SLVERR (the word unchanged): the executing side admits NO later event — no signature on a refused nonce, no
    INIT_REQ after a refused pre-event read, no DMA after a refused DEVCFG read; the session halts; the next candidate is refused"""
    s.open(); s.transaction("root", 0, stim([]))
    arm(s)
    signed_before, n_acc, n_pcap = len(s.notary.log), len(s.backend.accesses), len(s.backend.pcap_log)
    e = s.transaction("normal", G_CESR, stim(FIX1))
    try:
        s.transaction("normal", G_BASE, stim(FIX0)); refused = None
    except ss.SessionRefusal as ex:
        refused = str(ex)
    acc = s.backend.accesses[n_acc:]
    first = next((i for i, a in enumerate(acc) if a[2] != 0), None)
    after = acc[first + 1:] if first is not None else acc
    ctrl = [hex(ev["data"]) for ev in s.backend.trace[e["trace_range"][0]:e["trace_range"][1]] if ev.get("op") == "wr" and ev.get("addr") == 0x2000]
    return {"status": e["firmware"]["status"], "phase": e["firmware"]["phase"], "reason": e["firmware"]["reason"], "want_phase": want_phase, "o": e["o"] is not None,
            "x": e["x"]["status"] if e["x"] else None, "signed_in_tx": len(s.notary.log) - signed_before, "ctrl_writes_in_tx": ctrl,
            "dma_submits_in_tx": sum(1 for ev in s.backend.pcap_log[n_pcap:] if ev.get("pcap") == "submit"),
            "writes_after_the_refused_read": sum(1 for a in after if a[0] == "wr"), "refused_read_seen": first is not None, "next_refused": refused, "halted": s.halted}


def scenario_startup_corrupt(s: ss.Session) -> dict:
    """the startup readback corrupted: session_open refused; no root is signed (nothing further at all)"""
    s.corrupt_frame_reads.add(1)
    so = s.open()
    try:
        s.transaction("root", 0, stim([])); refused = None
    except ss.SessionRefusal as ex:
        refused = str(ex)
    return {"open_status": so["record"]["status"], "open_findings": so["findings"], "root_refused": refused, "signatures": len(s.notary.log), "halted": s.halted}


def _corruption(s: ss.Session, ordinal: int, want_phase: str) -> dict:
    s.corrupt_frame_reads.add(ordinal)
    s.open(); s.transaction("root", 0, stim([]))
    e = s.transaction("normal", G_CESR, stim(FIX1))
    signed_before = len(s.notary.log)
    try:
        s.transaction("normal", G_BASE, stim(FIX0)); refused = None
    except ss.SessionRefusal as ex:
        refused = str(ex)
    ctrl_after = [ev for ev in s.backend.trace[e["trace_range"][0]:] if ev.get("op") == "wr" and ev.get("addr") == 0x2000]
    return {"status": e["firmware"]["status"], "phase": e["firmware"]["phase"], "reason": e["firmware"]["reason"], "o": e["o"] is not None,
            "o_status": e["o"]["status"] if e["o"] else None, "x": e["x"]["status"] if e["x"] else None, "ctrl_writes_in_tx": [hex(c["data"]) for c in ctrl_after],
            "next_refused": refused, "signed_after": len(s.notary.log) - signed_before, "want_phase": want_phase}


SCENARIOS = {
    "startup_corrupt": (scenario_startup_corrupt, {}),
    "pre_event_corrupt": (lambda s: _corruption(s, 33, "P2"), {}),       # frame reads: 8 at the open, 24 in the root; 33 = the candidate's pre-event readback
    "post_event_corrupt": (lambda s: _corruption(s, 41, "P4"), {}),      # 41 = the candidate's post-event readback
    "base_readback_corrupt": (lambda s: _corruption(s, 49, "P8"), {}),   # 49 = the candidate's restored-base readback
    "step_in_slverr": (lambda s: _step_in_slverr(s), {}),
    "nonce_read_slverr": (lambda s: _read_slverr(s, lambda s: s.refuse_read(ss.rm.NONCE_LO), "P1"), {}),            # no signature is requested on a nonce that is not evidence
    "heartbeat_read_slverr": (lambda s: _read_slverr(s, lambda s: s.refuse_read(ss.rm.HEARTBEAT), "P3"), {}),       # no INIT_REQ after a refused pre-event read
    "devc_ctrl_read_slverr": (lambda s: _read_slverr(s, lambda s: s.refuse_mem_read(ss.bk.DEVCFG_CTRL), "P2"), {}),   # no DMA after a refused DEVCFG read
    "valid": (scenario_valid, {}),
    "a5": (scenario_a5, {}),
    "a5_persist": (scenario_a5, {"gsr_init_effect": False}),
    "a8_cross": (scenario_a8_cross, {}),
    "a2_pairs": (scenario_a2, {}),
    "not_realisable": (scenario_not_realisable, {}),
    "wrong_key": (scenario_wrong_key, {"provision_key": KEY_B}),
    "notary_refuses": (scenario_notary_refuses, {"notary_deny": {G_CESR}}),
    "dma_never": (scenario_dma_never, {"devc_faults": {("frame", 35): "never"}}),     # frame reads: 8 at the open, 24 in the root (pre-event, post-event, base); the 35th is inside the candidate's pre-event readback (P2)
    "latch_unmodelled": (scenario_latch, {}),
    "interrupt": (scenario_interrupt, {"interrupt_after_accesses": 3000, "interrupt_tx": 2}),   # the candidate (the root is transaction 1), inside its P2 writes
}


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    root = Path(argv[0]) if argv else R / "build/b4q_e2e"
    root.mkdir(parents=True, exist_ok=True)
    names = argv[1:] or list(SCENARIOS)
    summaries = []
    for name in names:
        body, kw = SCENARIOS[name]
        print("==", name, flush=True)
        summaries.append(run_session(root, name, body, **kw))
        print(json.dumps({k: v for k, v in summaries[-1].items() if k != "records"})[:400])
    (root / "e2e_summary.json").write_text(json.dumps(summaries, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
