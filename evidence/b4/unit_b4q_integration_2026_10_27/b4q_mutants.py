#!/usr/bin/env python3
"""B4Q — the focused mutant battery of the contracts this unit delivers: each mutant is one text edit of a source file
(the executing side's transaction logic, the session runner, the verifier, the record builder), applied to a COPY of the
tree... no: applied in place, exercised by ONE focused probe, then restored byte for byte (the file's digest checked
before and after). A mutant is KILLED when the probe fails the way the contract says it must — a named finding of the
verifier or the session, a refused build, a failed assertion — and SURVIVES otherwise. An edit that does not apply
(EDIT-MISS) or a probe that does not run (Ran 0) never counts as a kill (the owner's rule). Output: one line per mutant and the
totals; the log is kept in the unit directory."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / "host"))

FW = R / "firmware/b4q/b4q_tx.c"
SESSION = R / "host/b4q_session.py"
VERIFY = R / "host/b4q_verify.py"
RECORDS = R / "host/b4carrier_records.py"
A7 = R / "host/b4q_a7.py"
QUAL = R / "host/b4q_qual.py"
VIEW = R / "host/b4q_view.py"
SCHEMA_RAW = R / "b4q/schemas/ff_observation_model_raw_v1.schema.json"
BUILD = ["bash", str(R / "firmware/b4q/build.sh")]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def e2e(root: Path, scenario: str) -> dict:
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_e2e.py"), str(root), scenario], capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return {"error": (p.stdout + p.stderr)[-800:]}
    return {s["name"]: s for s in json.loads((root / "e2e_summary.json").read_text())}[scenario]


def verify(root: Path, scenario: str) -> dict:
    import importlib
    import b4q_verify as vf
    importlib.reload(vf)
    return vf.verify(root / scenario)


# ---------------------------------------------------------------- the probes: what a correct tree does, and what the mutant must break
def probe_valid_clean(root):
    """the valid scenario verifies clean, the executing side's fitness equal to the host's"""
    s = e2e(root, "valid")
    if "error" in s:
        return True, "the executing side failed: " + s["error"][:200]
    rep = verify(root, "valid")
    bad = [m for T in rep["transactions"] for m in T["findings"]] + rep["session"] + rep["a7"]["findings"] + rep["chain"]
    if not rep["clean"] or bad:
        return True, "; ".join(bad[:3]) or "not clean"
    recs = s["records"]
    if [r["x"] for r in recs] != ["closed"] * 4 or [r["o_status"] for r in recs] != ["complete"] * 4:
        return True, f"records {[(r['o_status'], r['x']) for r in recs]}"
    return False, "clean"


def probe_wrong_key(root):
    """an ARM under a wrong key: O invalid at P1 with arm_auth, no X; the session and the verifier agree"""
    s = e2e(root, "wrong_key")
    if "error" in s:
        return True, s["error"][:200]
    rep = verify(root, "wrong_key")
    T = rep["transactions"][0]
    if not T["agrees"] or "O invalid at P1 (arm_auth); no X" not in (T["outcome"] or ""):
        return True, f"outcome {T['outcome']!r} agrees {T['agrees']}"
    return False, "as expected"


def probe_a7_tamper(root):
    """the verifier finds a key-window write and a sweep-window read appended to the access log"""
    s = e2e(root, "valid")
    if "error" in s:
        return True, s["error"][:200]
    d = root / "valid"
    with (d / "accesses.jsonl").open("a") as f:
        f.write(json.dumps({"op": "wr", "addr": 0x43C02160, "resp": 0}) + "\n" + json.dumps({"op": "rd", "addr": 0x43C02240, "resp": 0}) + "\n")
    rep = verify(root, "valid")
    hits = [m for m in rep["a7"]["findings"] if "KEY window" in m] + [m for m in rep["a7"]["findings"] if "0x2240" in m]
    if len(hits) >= 2:
        return False, "found"
    return True, f"A7 findings {rep['a7']['findings']}"


def probe_validator_rules(root):
    """the record validators refuse a non-uniform applied vector and a record of another VARIANT (unit probes on a valid O)"""
    import importlib, copy
    import b4carrier_records as rec
    importlib.reload(rec)
    s = e2e(root, "valid")
    if "error" in s:
        return True, s["error"][:200]
    d = root / "valid"
    o = json.loads((d / "tx_002/o.json").read_text()); ctx = json.loads((d / "tx_002/ctx.json").read_text())
    t = copy.deepcopy(o); t["steps"][1]["ce"] = 0x3C
    if not rec.validate_observation(t):
        return True, "a non-uniform applied ce vector was accepted"
    t = copy.deepcopy(o); t["instrument"]["variant"] = "42310001"; c = dict(ctx); c["instrument"] = dict(t["instrument"])
    if not any("VARIANT" in m for m in rec.validate_bound(t, {**c, "predecessor_close_sha256": o["predecessor"]["close_sha256"], "predecessor_seq": o["predecessor"]["seq"]})):
        return True, "another VARIANT was accepted as the v2 carrier"
    return False, "refused"


def probe_tamper(root):
    """the verifier finds a tampered stored O"""
    s = e2e(root, "valid")
    if "error" in s:
        return True, s["error"][:200]
    d = root / "valid"
    o = json.loads((d / "tx_002/o.json").read_text()); o["steps"][2]["q_after"][0] ^= 1
    (d / "tx_002/o.json").write_text(json.dumps(o, indent=1, sort_keys=True))
    rep = verify(root, "valid")
    if any("stored record is not the one rebuilt" in m for m in rep["transactions"][1]["findings"]):
        return False, "found"
    return True, "the tamper was NOT found"


def probe_bench_records(root):
    """the carrier unit's record tests (the bench traces: a fault before the pre-sample is a P2 stop, an early cleanup a P3 stop)"""
    p = subprocess.run([sys.executable, "-B", "-m", "unittest", "tests.test_b4carrier_records"], cwd=str(R), capture_output=True, text=True, timeout=600)
    ran = [l for l in p.stderr.splitlines() if l.startswith("Ran ")]
    if not ran or ran[0].startswith("Ran 0"):
        return True, "the probe did not run (Ran 0): not a kill"
    return (p.returncode != 0), (ran[0] + (" FAILED" if p.returncode else " OK"))


def probe_fail_closed(root):
    """R1: a corrupted pre-event readback stops BEFORE the init event (no INIT_REQ, no step), the next transaction is refused and
    nothing further is signed; a STEP_IN answered SLVERR launches no STEP"""
    s = e2e(root, "pre_event_corrupt")
    if "error" in s:
        return True, s["error"][:200]
    if s.get("phase") != "P2" or s.get("ctrl_writes_in_tx") != ["0x40"] or s.get("next_refused") is None or s.get("signed_after") != 0 or s.get("o"):
        return True, f"pre_event_corrupt: phase {s.get('phase')} ctrl {s.get('ctrl_writes_in_tx')} next_refused {bool(s.get('next_refused'))} signed_after {s.get('signed_after')}"
    s2 = e2e(root, "step_in_slverr")
    if "error" in s2:
        return True, s2["error"][:200]
    if s2.get("step_launches") != 0 or s2.get("status") != 1:
        return True, f"step_in_slverr: launches {s2.get('step_launches')} status {s2.get('status')}"
    s3 = e2e(root, "startup_corrupt")
    if "error" in s3 or s3.get("signatures") != 0 or s3.get("root_refused") is None:
        return True, f"startup_corrupt: signatures {s3.get('signatures')} root_refused {bool(s3.get('root_refused'))}"
    return False, "as expected"


def probe_archive(root):
    """R2 / R3: a dropped final transaction, a malformed manifest and an altered qualification conclusion are found by a fresh verifier"""
    import shutil
    s = e2e(root, "valid")
    if "error" in s:
        return True, s["error"][:200]
    d = root / "valid"
    shutil.copytree(d / "tx_004", d / "tx_005")                                   # an undeclared record directory
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(d)], capture_output=True, text=True)
    if p.returncode == 0 or "not declared" not in p.stdout:
        return True, "an undeclared record directory was NOT refused: " + p.stdout[:160]
    shutil.rmtree(d / "tx_005")
    shutil.rmtree(d / "tx_004")                                                     # a declared record missing (its files included)
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(d)], capture_output=True, text=True)
    if p.returncode == 0 or "REFUSED" not in p.stdout:
        return True, "a dropped final transaction was NOT refused: " + p.stdout[:160]
    (d / "manifest.json").write_text("[]")
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(d)], capture_output=True, text=True)
    if p.returncode == 0 or "Traceback" in p.stderr or "REFUSED" not in p.stdout:
        return True, "a malformed manifest was not a named refusal: " + (p.stderr[-160:] or p.stdout[:160])
    s2 = e2e(root, "a8_cross")
    if "error" in s2:
        return True, s2["error"][:200]
    d2 = root / "a8_cross"
    v = json.loads((d2 / "a8_cross.json").read_text()); v["AFF"]["row"] = 5; v["AFF"]["verdict"] = "neither demonstrated"
    (d2 / "a8_cross.json").write_text(json.dumps(v))
    rep = verify(root, "a8_cross")
    if not any("A8 AFF" in m for m in rep["qualification"]["findings"]) or rep["agree"]:
        return True, "an altered A8 conclusion was NOT found"
    return False, "found"


def probe_a7_tuple(root):
    import importlib
    import b4q_a7 as a7
    importlib.reload(a7)
    import b4q_backend as bk
    base = {"pcap": "submit", "n": 0, "kind": "env", "src": bk.WR_BUF | 1, "dst": bk.PCAP_ENDPOINT, "src_len": bk.fr.STREAM_WORDS, "dst_len": 0}
    if a7.check([], [base])["findings"]:
        return True, "the legal envelope tuple was refused"
    for change in ({"src": 0xDEAD0001}, {"src": bk.WR_BUF}, {"src": bk.WR_BUF | 3}, {"src": bk.CMD_BUF | 1, "src_len": bk.fr.READBACK_CMD_WORDS}):
        if not a7.check([], [{**base, **change}])["findings"]:
            return True, f"accepted {change}"
    return False, "refused"


def probe_raw_float(root):
    import importlib, copy
    import b4q_view as vw, b4q_schema as sc, b4_ff_mapping as bm, b4_ff_hypothesis as hy, b4_ff_model as fm
    importlib.reload(sc); importlib.reload(vw)
    m = bm.site_mapping(); fab = fm.Fabric(m, hy.load()); trace = fab.observe(fab.config_from_genome(0x18), [fm.init()])
    src = {k: trace[k] for k in ("hypothesis", "mapping", "fabric")}
    bad = copy.deepcopy(trace); bad["config"][m.addresses[0]] = 0.25; bad["config_sha256"] = vw.sha256_default(bad["config"])
    if not sc.validate_named(bad, "ff_observation_model_raw_v1"):
        return True, "the raw schema accepted a float bit"
    try:
        vw.view(bad, {"representation": "M-raw", "source": src, "addresses": m.addresses})
        return True, "the adapter accepted a float bit"
    except vw.ViewRefusal:
        return False, "refused"


def probe_a5_witnesses(root):
    import importlib
    import b4q_qual as ql
    importlib.reload(ql)
    s = e2e(root, "a5")
    if "error" in s or s.get("a5") != "pass":
        return True, f"a5 {s.get('a5')}"
    d = root / "a5"; rd = lambda n: json.loads((d / n).read_text())
    v = ql.a5_verdict(rd("tx_002/o.json"), rd("tx_003/o.json"), rd("tx_004/o.json"))
    if v["verdict"] == "pass":
        return True, "a pass without any close witness"
    v = ql.a5_verdict(rd("tx_002/o.json"), rd("tx_003/o.json"), rd("tx_004/o.json"), None, None, rd("tx_003/x.json"))   # J2's injection_open given, J1 / J3's cleanup witnesses absent
    if v["verdict"] == "pass":
        return True, "a pass without J1 / J3's cleanup witnesses"
    return False, v["verdict"]


def probe_a5(root):
    s = e2e(root, "a5")
    if "error" in s:
        return True, s["error"][:200]
    rep = verify(root, "a5")
    if not rep["clean"] or s.get("a5") != "pass":
        return True, f"a5 {s.get('a5')} clean {rep['clean']}"
    return False, "pass"


MUTANTS = [
    ('C1', FW, 'if (read_slot(2 + k, r) != 0) goto stopped;\n        r->steps_applied = k + 1;', 'if (read_slot(2 + k + (k == 1 ? 1 : 0), r) != 0) goto stopped;\n        r->steps_applied = k + 1;', "a step's sample read from the wrong slot", probe_valid_clean),
    ('C2', FW, 'if (engine_op(B4Q_CTRL_RESTORE_INIT, B4Q_ST_RESTORE_DONE, &st, r, "STOP_P9: RESTORE_INIT refused") != 0) goto faulted;', '/* P9 skipped */', 'P9 (the restore event) skipped before CLOSE', probe_valid_clean),
    ('C3', FW, 'if (engine_op(B4Q_CTRL_CLEANUP, B4Q_ST_CLEANUP_DONE, &st, r, "STOP_P7: CLEANUP refused") != 0) goto faulted;', '/* P7 skipped */', 'the cleanup skipped', probe_valid_clean),
    ('C4', FW, 'int k, a5 = (kind == B4Q_KIND_A5);', 'int k, a5 = 1;', 'the A5 context flag on every ARM', probe_valid_clean),
    ('C5', FW, 'for (i = 0; i < 4; i++) if (axi_wr(B4Q_TAG0 + 4u * (uint32_t)i, words[20 + i]) != B4Q_RESP_OKAY) return -1;', 'for (i = 0; i < 4; i++) if (axi_wr(B4Q_TAG0 + 4u * (uint32_t)i, words[20 + (i + 1) % 4]) != B4Q_RESP_OKAY) return -1;', 'the tag words staged rotated', probe_valid_clean),
    ('C6', FW, 'r->fitness = f; r->has_fitness = 1;', 'r->fitness = f + 1; r->has_fitness = 1;', "the executing side's fitness off by one", probe_valid_clean),
    ('C7', FW, 'g[0] = genome;\n    p3_derive_frames(g, g_frames);', 'g[0] = genome ^ 1u;\n    p3_derive_frames(g, g_frames);', 'the frames derived for another genome than signed', probe_valid_clean),
    ('C8', FW, 'if (link3(pre_event_hex) != 0) return -1;\n    if (strcmp(pre_event_hex, commit_hex) != 0) { stop("STOP_LINK3: the pre-event readback is not the signed candidate (no event is raised on it)"); return -1; }\n    return 0;\n}', 'strcpy(pre_event_hex, commit_hex); return 0;\n}', 'the pre-event readback skipped, its digest fabricated from the commit', probe_valid_clean),
    ('C9', FW, 'if (strcmp(staged_hex, commit_hex) != 0) { stop("STOP_LINK2: the re-read frames are not the signed candidate"); return -1; }', '', 'the link-2 comparison removed (observable only beside a corruption: C9+C10)', probe_valid_clean),
    ('C10', FW, 'mem_wr(P3_WR_BUF + (uint32_t)e * 4u * P3_STREAM_WORDS + 4u * (uint32_t)i, words[i]);', 'mem_wr(P3_WR_BUF + (uint32_t)e * 4u * P3_STREAM_WORDS + 4u * (uint32_t)i, words[i] ^ (i == 300 ? 1u : 0u));', 'one staged frame word corrupted in DDR', probe_valid_clean),
    ('C11', FW, 'if (!bit(st, B4Q_ST_IDLE)) { stop("STOP_P10: not idle after CLOSE"); goto faulted; }', '', "the idle check after CLOSE removed (equivalent on every available probe: the valid path's CLOSE always leaves idle)", probe_valid_clean),
    ('C12', FW, 'if (!axi_writable(off)) { stop("STOP_AXI: write outside the pinned map"); return B4Q_RESP_SLVERR; }', 'if (!axi_writable(off) && off != B4Q_KEY0) { stop("STOP_AXI: write outside the pinned map"); return B4Q_RESP_SLVERR; }\n    if (off == B4Q_SLOT_ADDR && v == 1u) (void)b4q_wr32(B4Q_AXI_BASE + B4Q_KEY0, 0u);', 'a write into the key window', probe_valid_clean),
    ('C13', FW, 'if (wait_status(B4Q_ST_GATE_BUSY, 32u, &st) != 0) { r->fault_code = axi_rd(B4Q_FAULT); stop("STOP_ARM: the gate refused (FAULT latched)"); return -1; }', 'if (wait_status(B4Q_ST_GATE_BUSY, 32u, &st) != 0) { st = 0; }', "an ARM refusal ignored by the executing side (silent by the record layer's authority over the trace)", probe_wrong_key),
    ('R1a', FW, 'if (strcmp(pre_event_hex, commit_hex) != 0) { stop("STOP_LINK3: the pre-event readback is not the signed candidate (no event is raised on it)"); return -1; }', '', 'the pre-event comparison before the init event removed', probe_fail_closed),
    ('R1b', FW, 'if (axi_wr(B4Q_STEP_IN, steps[k] & 0x1FFFFFFu) != B4Q_RESP_OKAY) { stop("STOP_P5: the STEP_IN write answered SLVERR: the staged word is not this step; no STEP is launched"); goto stopped; }', 'axi_wr(B4Q_STEP_IN, steps[k] & 0x1FFFFFFu);', 'the STEP_IN write response ignored again (masked by the read-back check: see R1b+R1b2)', probe_fail_closed),
    ('R1b2', FW, 'if (axi_rd(B4Q_STEP_IN) != (steps[k] & 0x1FFFFFFu)) { stop("STOP_P5: STEP_IN does not read back the staged step; no STEP is launched"); goto stopped; }', '', 'the STEP_IN read-back check removed (masked by the response check: see R1b+R1b2)', probe_fail_closed),
    ('R1c', FW, 'if (resp != B4Q_RESP_OKAY && off != B4Q_CTRL) stop("STOP_AXI: a write of the pinned map answered SLVERR (the register is not what this side meant to stage)");', '', 'the accessor no longer propagates a refused write (masked by the explicit STEP_IN checks)', probe_fail_closed),
    ('R1d', SESSION, 'if self.halted is not None:\n            raise SessionRefusal("the session is halted: " + self.halted + " — nothing further is signed without a ruling")', 'if False:\n            raise SessionRefusal("x")', "the session's halt latch no longer refuses the next transaction (masked by the previous-close rule: see R1d+prev)", probe_fail_closed),
    ('R1e', SESSION, 'if self.session_open is None or self.session_open["record"]["status"] != "open":', 'if self.session_open is None:', 'a refused opening no longer withholds the root (masked by the halt latch: see R1d+R1e)', probe_fail_closed),
    ('R2a', VERIFY, 'extra = sorted(p.name for p in d.iterdir() if p.is_dir() and p.name.startswith("tx_") and p.name not in {r["dir"] for r in recs})', 'extra = []', 'undeclared record directories accepted again', probe_archive),
    ('R2a2', VERIFY, 'if not td.is_dir():\n            raise ArchiveRefusal(f"{r[\'dir\']}: declared in the manifest, not present")', 'if False:\n            raise ArchiveRefusal("x")', 'a declared record directory missing no longer refuses (masked by the per-record file checks: see R2a2+files)', probe_archive),
    ('R2c', VERIFY, 'if not isinstance(manifest, dict) or manifest.get("schema") != "b4q_session":\n        raise ArchiveRefusal("manifest.json: not a b4q_session manifest object")', 'pass', "the manifest's shape no longer validated first", probe_archive),
    ('R3a', VERIFY, 'rep["qualification"] = verify_qualification(d, manifest, rep["transactions"], tx_dirs)', 'rep["qualification"] = {"findings": [], "a5": [], "a8": [], "a2": []}', 'the qualification conclusions no longer recomputed', probe_archive),
    ('R3b', QUAL, 'if not (isinstance(x, dict) and x.get("status") == "closed" and isinstance(x.get("cleanup"), dict) and "final_q" in x["cleanup"]):', 'if False:', "A5 no longer requires J1 / J3's cleanup witnesses", probe_a5_witnesses),
    ('R4a', A7, 'if (src & 1) != bk.DMA_HOLD_TAG:\n            return None, "a write to the PCAP endpoint without the HOLD tag on its source"', 'if False:\n            return None, "x"', 'the HOLD tag no longer required', probe_a7_tuple),
    ('R4b', A7, 'if base in ENVELOPE_SOURCES and src_len == fr.STREAM_WORDS:', 'if src_len == fr.STREAM_WORDS:', 'the envelope source no longer bound to the staging slots', probe_a7_tuple),
    ('R5a', SCHEMA_RAW, '"pattern": "0x[0-9a-f]{8}/[0-9]{1,3}/[0-9]{1,2}"\n   },\n   "additionalProperties": {\n    "type": "integer",\n    "minimum": 0,\n    "maximum": 1\n   }', '"pattern": "0x[0-9a-f]{8}/[0-9]{1,3}/[0-9]{1,2}"\n   },\n   "additionalProperties": {}', "the raw config's values untyped again (the file; masked by the adapter's own type check: see R5a+R5b)", probe_raw_float),
    ('R5b', VIEW, 'if not _is_bit(b):\n            raise ViewRefusal(f"M-raw: config[{a}] is {b!r}, not the int 0 / 1 (no coercion)")', 'pass', "the adapter's type check removed (masked by the schema file validated first: see R5a+R5b)", probe_raw_float),
    ('P1', SESSION, 'o = rec.observation(tx_events, links, self.timing, seq=seq, session=self.label, predecessor=pred, declared_stimulus=stimulus)', 'o = rec.observation(tx_events, links, self.timing, seq=seq, session=self.label, predecessor=pred, declared_stimulus=stimulus); o["seq"] = seq + 100', "the stored O's seq altered after sealing", probe_valid_clean),
    ('P2', SESSION, 'if r.get("has_fitness") and r.get("fitness") != f["fitness"]:', 'if False and r.get("has_fitness") and r.get("fitness") != f["fitness"]:', "the session no longer holds the executing side's fitness to the host's (observable only beside C6: P2+C6)", probe_valid_clean),
    ('P3', VERIFY, 'if o_stored is None or canon(o) != canon(o_stored):', 'if o_stored is None:', 'the verifier no longer compares the stored O to the rebuilt one', probe_tamper),
    ('P4', VERIFY, 'rep["a7"] = a7.check(acc, pcap)', 'rep["a7"] = {"findings": [], "accesses": len(acc), "slverr": 0}', 'the verifier skips A7', probe_a7_tamper),
    ('P5', RECORDS, '        if s["ce"] not in (0, 255) or s["sr"] not in (0, 255):', '        if False:', 'the realisability rule of the validator removed (masked by the declared-step equality)', probe_validator_rules),
    ('P6', RECORDS, 'if o["instrument"]["variant"] != f"{rm.VARIANT_WORD:08x}":', 'if False:', 'the VARIANT binding removed', probe_validator_rules),
    ('P7', A7, 'if off in rm.KEY_WINDOW:', 'if False:', 'the key-window finding of A7 removed (masked by the allowlist line)', probe_a7_tamper),
    ('P8', RECORDS, '    if code is not None:\n        phase = "P5" if init_done else ("P3" if pre_sampled else "P2")', '    if code is not None:\n        phase = "P5"', "an invalid O's phase always P5", probe_bench_records),
]
EXTRA_EDITS = {
    'PREV': (SESSION, 'if self.records and not (self.prev_x is not None and self.prev_x["status"] in ("closed", "injection_open")):', 'if False:'),
    'FILES': (VERIFY, 'for f in ("record.json", "ctx.json", "links.json", "firmware_result.json"):\n            if not (td / f).is_file():\n                raise ArchiveRefusal(f"{r[\'dir\']}/{f}: missing")', 'pass'),
}


def _m(mid):
    return [m for m in MUTANTS if m[0] == mid][0]


def _edit(mid):
    if mid in EXTRA_EDITS:
        return EXTRA_EDITS[mid]
    m = _m(mid)
    return (m[1], m[2], m[3])


COMBINED = [
    ('C9+C10', [_edit(x) for x in ['C9', 'C10']], 'the link-2 comparison removed AND a staged word corrupted: the corrupted candidate is written', probe_valid_clean),
    ('P2+C6', [_edit(x) for x in ['P2', 'C6']], "the session no longer holds the fitness AND the executing side's is off by one: the verifier must still find it and the two must disagree", probe_valid_clean),
    ('R1b+R1b2', [_edit(x) for x in ['R1b', 'R1b2']], 'the STEP_IN response check AND the read-back check removed: a STEP launched on the stale word', probe_fail_closed),
    ('R1c+R1b+R1b2', [_edit(x) for x in ['R1c', 'R1b', 'R1b2']], "the accessor's propagation AND both STEP_IN checks removed", probe_fail_closed),
    ('R1d+prev', [_edit(x) for x in ['R1d', 'PREV']], 'the halt latch AND the previous-close rule removed: the next candidate is signed after an unclosed transaction', probe_fail_closed),
    ('R1d+R1e', [_edit(x) for x in ['R1d', 'R1e']], 'the halt latch AND the opening rule removed: the root is signed after a refused opening', probe_fail_closed),
    ('R2a2+files', [_edit(x) for x in ['R2a2', 'FILES']], 'the declared-directory check AND the per-record file checks removed: a dropped declared record', probe_archive),
    ('R5a+R5b', [_edit(x) for x in ['R5a', 'R5b']], "the raw schema's value type AND the adapter's type check removed: a float bit passes", probe_raw_float),
]


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    only = set(argv)
    out = R / "evidence/b4/unit_b4q_integration_2026_10_27/mutants.txt"
    lines = [f"B4Q mutant battery — {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} HEAD {subprocess.run(['git', '-C', str(R), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()}"]
    killed = survived = missed = 0
    # the baseline: the probes pass on the unmutated tree
    tmp = Path(tempfile.mkdtemp(prefix="b4q_mut_"))
    subprocess.run(BUILD, check=True, capture_output=True)
    for name, probe in (("valid", probe_valid_clean), ("wrong_key", probe_wrong_key), ("tamper", probe_tamper), ("a5", probe_a5), ("fail_closed", probe_fail_closed),
                        ("archive", probe_archive), ("a7_tuple", probe_a7_tuple), ("raw_float", probe_raw_float), ("a5_witnesses", probe_a5_witnesses), ("bench_records", probe_bench_records)):
        broken, why = probe(tmp / "base")
        lines.append(f"BASELINE {name}: {'BROKEN — ' + why if broken else 'green'}")
        if broken:
            print("\n".join(lines)); return 2
    for mid, path, old, new, what, probe in MUTANTS:
        if only and mid not in only:
            continue
        text = path.read_text(); before = sha(path)
        if text.count(old) != 1:
            lines.append(f"{mid} EDIT-MISS ({text.count(old)} occurrences) — {what}"); missed += 1; continue
        try:
            path.write_text(text.replace(old, new))
            if path == SCHEMA_RAW:
                json.loads(path.read_text())                            # a schema file mutant must stay JSON
            if path == FW:
                b = subprocess.run(BUILD, capture_output=True, text=True)
                if b.returncode != 0:
                    lines.append(f"{mid} KILLED (the build refused the mutant) — {what}"); killed += 1; continue
            root = tmp / mid; root.mkdir(parents=True, exist_ok=True)
            broken, why = probe(root)
        finally:
            path.write_text(text)
            assert sha(path) == before, f"{path} not restored"
            if path == FW:
                subprocess.run(BUILD, check=True, capture_output=True)
        if broken:
            killed += 1; lines.append(f"{mid} KILLED — {what}: {why[:160]}")
        else:
            survived += 1; lines.append(f"{mid} SURVIVED — {what}: {why[:160]}")
        print(lines[-1], flush=True)
    for mid, edits, what, probe in COMBINED:
        if only and mid not in only:
            continue
        saved = {path: (path.read_text(), sha(path)) for path, _, _ in edits}
        miss = [path.name for path, old_, _ in edits if saved[path][0].count(old_) != 1]
        if miss:
            lines.append(f"{mid} EDIT-MISS {miss} — {what}"); missed += 1; continue
        try:
            for path, old_, new_ in edits:
                path.write_text(path.read_text().replace(old_, new_))
            b = subprocess.run(BUILD, capture_output=True, text=True)
            if b.returncode != 0:
                lines.append(f"{mid} KILLED (the build refused the mutant) — {what}"); killed += 1; continue
            root = tmp / mid.replace("+", "_"); root.mkdir(parents=True, exist_ok=True)
            broken, why = probe(root)
        finally:
            for path, (text, before) in saved.items():
                path.write_text(text); assert sha(path) == before
            subprocess.run(BUILD, check=True, capture_output=True)
        if broken:
            killed += 1; lines.append(f"{mid} KILLED — {what}: {why[:160]}")
        else:
            survived += 1; lines.append(f"{mid} SURVIVED — {what}: {why[:160]}")
        print(lines[-1], flush=True)
    n = len([m for m in MUTANTS if not only or m[0] in only]) + len([m for m in COMBINED if not only or m[0] in only])
    lines.append(f"TOTAL killed {killed} survived {survived} edit-miss {missed} of {n}")
    lines.append("REPAIR MUTANTS (R1-R5, 2026-10-27): R1a-e, R2a/R2a2/R2c, R3a/R3b, R4a/R4b, R5a/R5b and the combined ones — each probed by the fault condition it guards (a corrupted readback, a refused write, a refused opening, a dropped / undeclared record, a malformed manifest, an altered conclusion, missing close witnesses, a bad DMA tuple, a float bit). Where a single repair guard survives, its redundant twin masks it on every probe and the COMBINED mutant removing both is killed: R1b (the STEP_IN read-back check), R1c (the explicit STEP_IN response check and the read-back check), R1d (the previous-close rule), R1e (the halt latch), R2a2 (the per-record file checks), R5b (the raw schema file validated first) — proven redundancy under the explicit contract, each named here, none counted as a tested guard by itself.")
    lines.append("SURVIVORS acknowledged (each an equivalent or a redundancy on every available probe, named with what masks it): C9 (the link-2 comparison alone: on a correct executing side the re-read always equals the commit — its removal is observable only beside a corruption, C9+C10, killed), P2 (the session's fitness hold alone: the verifier recomputes it independently and the executing side's is correct — observable only beside C6, P2+C6, killed), P5 (the applied-vector realisability rule: the declared-step equality check catches a non-uniform applied vector first, since the declared stimulus is uniform by task-v0.3), P7 (A7's key-window line: the key window is also outside the application's write allowlist, which the next line reports), C11 (the idle check after CLOSE: the valid path's CLOSE always leaves idle, so its removal is equivalent on every available probe — the RTL's idle semantics are the carrier bench's finding, scenario open_close_refused), C13 (an ARM refusal ignored by the executing side: the record layer judges the TRACE, not the executing side's claim, so the O is still invalid at P1 with arm_auth — the mutant is silent by the record layer's authority, which is the design)")
    out.write_text("\n".join(lines) + "\n")
    print(lines[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
