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


def probe_a5(root):
    s = e2e(root, "a5")
    if "error" in s:
        return True, s["error"][:200]
    rep = verify(root, "a5")
    if not rep["clean"] or s.get("a5") != "pass":
        return True, f"a5 {s.get('a5')} clean {rep['clean']}"
    return False, "pass"


MUTANTS = [
    # the executing side (C): rebuilt before each probe
    ("C1", FW, 'read_slot(2 + k, r);\n        r->steps_applied = k + 1;', 'read_slot(2 + k + (k == 1 ? 1 : 0), r);\n        r->steps_applied = k + 1;', "a step's sample read from the wrong slot", probe_valid_clean),
    ("C2", FW, 'if (engine_op(B4Q_CTRL_RESTORE_INIT, B4Q_ST_RESTORE_DONE, &st, r, "STOP_P9: RESTORE_INIT refused") != 0) goto faulted;', '/* P9 skipped */', "P9 (the restore event) skipped before CLOSE", probe_valid_clean),
    ("C3", FW, 'if (engine_op(B4Q_CTRL_CLEANUP, B4Q_ST_CLEANUP_DONE, &st, r, "STOP_P7: CLEANUP refused") != 0) goto faulted;', '/* P7 skipped */', "the cleanup skipped", probe_valid_clean),
    ("C4", FW, 'int k, a5 = (kind == B4Q_KIND_A5);', 'int k, a5 = 1;', "the A5 context flag on every ARM", probe_valid_clean),
    ("C5", FW, 'for (i = 0; i < 4; i++) axi_wr(B4Q_TAG0 + 4u * (uint32_t)i, words[20 + i]);', 'for (i = 0; i < 4; i++) axi_wr(B4Q_TAG0 + 4u * (uint32_t)i, words[20 + (i + 1) % 4]);', "the tag words staged rotated", probe_valid_clean),
    ("C6", FW, 'r->fitness = f; r->has_fitness = 1;', 'r->fitness = f + 1; r->has_fitness = 1;', "the executing side's fitness off by one", probe_valid_clean),
    ("C7", FW, 'g[0] = genome;\n    p3_derive_frames(g, g_frames);', 'g[0] = genome ^ 1u;\n    p3_derive_frames(g, g_frames);', "the frames derived for another genome than signed", probe_valid_clean),
    ("C8", FW, 'if (link3(pre_event_hex) != 0) return -1;\n    return 0;', 'strcpy(pre_event_hex, commit_hex); return 0;', "the pre-event readback skipped, its digest fabricated from the commit", probe_valid_clean),
    ("C9", FW, 'if (strcmp(staged_hex, commit_hex) != 0) { stop("STOP_LINK2: the re-read frames are not the signed candidate"); return -1; }', '', "the link-2 comparison removed (with the words staged shifted: see C10)", probe_valid_clean),
    ("C10", FW, 'mem_wr(P3_WR_BUF + (uint32_t)e * 4u * P3_STREAM_WORDS + 4u * (uint32_t)i, words[i]);', 'mem_wr(P3_WR_BUF + (uint32_t)e * 4u * P3_STREAM_WORDS + 4u * (uint32_t)i, words[i] ^ (i == 300 ? 1u : 0u));', "one staged frame word corrupted in DDR", probe_valid_clean),
    ("C11", FW, 'if (!bit(st, B4Q_ST_IDLE)) { stop("STOP_P10: not idle after CLOSE"); goto faulted; }', '', "the idle check after CLOSE removed (with C2 the X would still be faulted; alone it must be silent: an equivalent on the valid path, see the log)", probe_valid_clean),
    ("C12", FW, 'if (!axi_writable(off)) { stop("STOP_AXI: write outside the pinned map"); return B4Q_RESP_SLVERR; }', 'if (!axi_writable(off) && off != B4Q_KEY0) { stop("STOP_AXI: write outside the pinned map"); return B4Q_RESP_SLVERR; }\n    if (off == B4Q_SLOT_ADDR && v == 1u) (void)b4q_wr32(B4Q_AXI_BASE + B4Q_KEY0, 0u);', "a write into the key window", probe_valid_clean),
    ("C13", FW, 'if (wait_status(B4Q_ST_GATE_BUSY, 32u, &st) != 0) { r->fault_code = axi_rd(B4Q_FAULT); stop("STOP_ARM: the gate refused (FAULT latched)"); return -1; }', 'if (wait_status(B4Q_ST_GATE_BUSY, 32u, &st) != 0) { st = 0; }', "an ARM refusal ignored", probe_wrong_key),
    # the host: the session runner, the verifier, the record builder
    ("P1", SESSION, 'o = rec.observation(tx_events, links, self.timing, seq=seq, session=self.label, predecessor=pred, declared_stimulus=stimulus)',
     'o = rec.observation(tx_events, links, self.timing, seq=seq, session=self.label, predecessor=pred, declared_stimulus=stimulus); o["seq"] = seq + 100', "the stored O's seq altered after sealing", probe_valid_clean),
    ("P2", SESSION, 'if r.get("has_fitness") and r.get("fitness") != f["fitness"]:', 'if False and r.get("has_fitness") and r.get("fitness") != f["fitness"]:', "the session no longer holds the executing side's fitness to the host's", probe_valid_clean),
    ("P3", VERIFY, 'if o_stored is None or canon(o) != canon(o_stored):', 'if o_stored is None:', "the verifier no longer compares the stored O to the rebuilt one", probe_tamper),
    ("P4", VERIFY, 'rep["a7"] = a7.check(acc, pcap)', 'rep["a7"] = {"findings": [], "accesses": len(acc)}', "the verifier skips A7", probe_a7_tamper),
    ("P5", RECORDS, '        if s["ce"] not in (0, 255) or s["sr"] not in (0, 255):', '        if False:', "the realisability rule of the validator removed", probe_validator_rules),
    ("P6", RECORDS, 'if o["instrument"]["variant"] != f"{rm.VARIANT_WORD:08x}":', 'if False:', "the VARIANT binding removed", probe_validator_rules),
    ("P7", A7, 'if off in rm.KEY_WINDOW:', 'if False:', "the key-window finding of A7 removed", probe_a7_tamper),
    ("P8", RECORDS, '    if code is not None:\n        phase = "P5" if init_done else ("P3" if pre_sampled else "P2")', '    if code is not None:\n        phase = "P5"', "an invalid O's phase always P5", probe_bench_records),
]


COMBINED = [
    ("C9+C10", [(FW, MUTANTS[8][2], MUTANTS[8][3]), (FW, MUTANTS[9][2], MUTANTS[9][3])], "the link-2 comparison removed AND a staged word corrupted: the corrupted candidate is written", probe_valid_clean),
    ("P2+C6", [(SESSION, MUTANTS[14][2], MUTANTS[14][3]), (FW, MUTANTS[5][2], MUTANTS[5][3])], "the session no longer holds the fitness AND the executing side's is off by one: the verifier must still find it and the two must disagree", probe_valid_clean),
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
    for name, probe in (("valid", probe_valid_clean), ("wrong_key", probe_wrong_key), ("tamper", probe_tamper), ("a5", probe_a5)):
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
    lines.append("SURVIVORS acknowledged (each an equivalent or a redundancy on every available probe, named with what masks it): C9 (the link-2 comparison alone: on a correct executing side the re-read always equals the commit — its removal is observable only beside a corruption, C9+C10, killed), P2 (the session's fitness hold alone: the verifier recomputes it independently and the executing side's is correct — observable only beside C6, P2+C6, killed), P5 (the applied-vector realisability rule: the declared-step equality check catches a non-uniform applied vector first, since the declared stimulus is uniform by task-v0.3), P7 (A7's key-window line: the key window is also outside the application's write allowlist, which the next line reports), C11 (the idle check after CLOSE: the valid path's CLOSE always leaves idle, so its removal is equivalent on every available probe — the RTL's idle semantics are the carrier bench's finding, scenario open_close_refused), C13 (an ARM refusal ignored by the executing side: the record layer judges the TRACE, not the executing side's claim, so the O is still invalid at P1 with arm_auth — the mutant is silent by the record layer's authority, which is the design)")
    out.write_text("\n".join(lines) + "\n")
    print(lines[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
