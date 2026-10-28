#!/usr/bin/env python3
"""The PS-image unit's FOCUSED mutant battery (host-only): one text edit at a time in the image's own pure units (the board
application b4q_app.c, the framing b4q_wire.c, the allowlist b4q_psmap.c), restored byte for byte, each probed by the console
scenario or the twin check that observes the guard it removes. The discipline of the integration unit's battery: a mutant is
killed only by a probe that observes its fault condition; an EDIT-MISS or a run of 0 is never a kill; a survivor is named with
what masks it. Run from the repository root:  python3 -B evidence/b4/unit_b4q_image_2026_10_28/b4q_image_mutants.py [--out f] [ids…]"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

R = Path(__file__).resolve().parents[3]
FW = R / "firmware/b4q"
APP, WIRE, PSMAP, CMD = FW / "target/b4q_app.c", FW / "target/b4q_wire.c", FW / "target/b4q_psmap.c", FW / "b4q_cmd.c"
SESSION, VERIFY = R / "host/b4q_console_session.py", R / "host/b4q_verify.py"
BUILD = ["make", "-C", str(FW), f"BUILD={R / 'build/b4q_firmware'}", "apphost", "wiretwin", "waittwin"]
WAIT = R / "build/b4q_firmware/b4q_wait_twin"
TWIN = R / "build/b4q_firmware/b4q_wire_twin"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def e2e(root: Path, *names: str, timeout: int = 300) -> dict:
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_console_e2e.py"), str(root), *names], capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        return {"error": (p.stdout[-400:] + p.stderr[-400:]).replace("\n", " | ")}
    return {s["name"]: s for s in json.loads((root / "e2e_summary.json").read_text())}


def twin(cmds: list[str]) -> list[str]:
    p = subprocess.run([str(TWIN)], input="".join(c + "\n" for c in cmds), capture_output=True, text=True, timeout=60)
    return p.stdout.splitlines()


def probe_kicks(root):
    """every emitted line restarts the watchdog, as the PLATFORM counts it (the harness's HALT line), and the END's own count agrees"""
    s = e2e(root, "valid")
    if "error" in s:
        return True, s["error"][:200]
    v = s["valid"]
    if v.get("platform_kicks") != v["end"]["lines"] + 1 or v["end"]["kicks"] != v["end"]["lines"]:      # the END line's own kick is the +1
        return True, f"platform kicks {v.get('platform_kicks')} / end kicks {v['end']['kicks']} / lines {v['end']['lines']}"
    return False, "as expected"


def probe_page_and_watchdog(root):
    """a bad page and an unarmed watchdog: no IDENT, nothing signed, END STOPPED by name"""
    s = e2e(root, "bad_page", "watchdog_fail")
    if "error" in s:
        return True, s["error"][:200]
    for name in ("bad_page", "watchdog_fail"):
        v = s[name]
        if v.get("ident") is not None or v.get("signatures") != 0 or (v.get("end") or {}).get("kind") != "STOPPED":
            return True, f"{name}: ident {v.get('ident') is not None} signatures {v.get('signatures')} end {(v.get('end') or {}).get('kind')}"
    return False, "as expected"


def probe_framing(root):
    """a corrupted reply is NACKed 'bad crc' and re-requested; a line under another token is NACKed 'wrong token'; a stale reply (another
    request's, garbage words) is ignored; a malformed line is NACKed"""
    s = e2e(root, "reply_corrupt", "wrong_token", "stale_reply", "garbage_command")
    if "error" in s:
        return True, s["error"][:200]
    rc = s["reply_corrupt"]
    if rc["tx"]["status"] != 0 or rc["end"]["nacks"] != 1 or rc["end"]["sign_requests"] != 3:
        return True, f"reply_corrupt: status {rc['tx']['status']} nacks {rc['end']['nacks']} sign_requests {rc['end']['sign_requests']}"
    nacks = [json.loads(l) for l in (root / "reply_corrupt/console.jsonl").read_text().splitlines() if '"NACK"' in l]
    import base64
    if not any(base64.urlsafe_b64decode(n["line"].split()[4]) == b"bad crc" for n in nacks):
        return True, "reply_corrupt: the NACK does not say 'bad crc'"
    wt = s["wrong_token"]
    if wt["tx"]["status"] != 0 or "NACK wrong token" not in wt.get("nacks", []):
        return True, f"wrong_token: status {wt['tx']['status']} nacks {wt.get('nacks')}"
    st = s["stale_reply"]
    if st["tx"]["status"] != 0 or st["tx"]["x"] != "closed":
        return True, f"stale_reply: status {st['tx']['status']} x {st['tx']['x']}"
    gc = s["garbage_command"]
    if gc["tx"]["status"] != 0 or gc["end"]["nacks"] != 1:
        return True, f"garbage_command: status {gc['tx']['status']} nacks {gc['end']['nacks']}"
    return False, "as expected"


def probe_bounds(root):
    """every reply dropped: the bound ends the wait (three attempts), STOP_SIGN, the session halted — within a wall-clock limit that a
    missing bound cannot meet; a silent host: END STOPPED on the idle bound"""
    try:
        s = e2e(root, "replies_dropped", "silent_host", timeout=240)
    except subprocess.TimeoutExpired:
        return True, "the run did not end within 240 s: a bound is not enforced"
    if "error" in s:
        return True, s["error"][:200]
    rd = s["replies_dropped"]
    if rd["tx"]["status"] != 1 or rd["end"]["sign_requests"] != 4 or not rd.get("halted"):
        return True, f"replies_dropped: status {rd['tx']['status']} sign_requests {rd['end']['sign_requests']} halted {bool(rd.get('halted'))}"
    sh = s["silent_host"]
    if (sh.get("end") or {}).get("kind") != "STOPPED" or "idle bound" not in (sh.get("end") or {}).get("reason", ""):
        return True, f"silent_host: end {sh.get('end')}"
    return False, "as expected"


def probe_allowlist(root):
    """the pure allowlist: the key window and the page are never writable, an address outside every region is neither"""
    out = twin(["PSMAP 43c02160", "PSMAP 43c0216c", "PSMAP 10440000", "PSMAP 10500000", "PSMAP 43c02004", "PAGE " + " ".join(["42345149", "00000001"] + ["00000000"] * 22)])
    want = ["r=0 w=0", "r=0 w=0", "r=1 w=0", "r=0 w=0", "r=1 w=0"]
    if out[:5] != want:
        return True, f"allowlist {out[:5]} (want {want})"
    # a page with a correct checksum (all zeros xor magic xor layout) but a non-zero reserved word must be refused
    words = [0x42345149, 1] + [0] * 18 + [0, 0, 0]
    words[20] = 7
    x = 0
    for v in words:
        x ^= v
    out2 = twin(["PAGE " + " ".join(f"{v:08x}" for v in words + [x])])
    if out2 != ["REFUSED"]:
        return True, f"page with a reserved word set accepted: {out2}"
    return False, "as expected"


def probe_budget(root):
    """R1: the budget twin — a silent peer, a stale-reply flood and an overlong line each end at exactly 3 x the attempt's budget; the
    command wait under a non-command flood and a silent host end within the idle budget (the fixture's 50x cap is OVER_BUDGET, exit 77)"""
    out = {}
    for mode in range(7):
        p = subprocess.run([str(WAIT), str(mode)], capture_output=True, text=True, timeout=120)
        if p.returncode != 0:
            return True, f"mode {mode}: exit {p.returncode}: {p.stdout.strip()[:100]}"
        out[mode] = dict(kv.split("=") for kv in p.stdout.split())
    for mode in (0, 1, 2, 6):
        if out[mode]["polls"] != "30000" or out[mode]["ret"] != "-1":
            return True, f"mode {mode}: polls {out[mode]['polls']} ret {out[mode]['ret']}"
    if int(out[4]["polls"]) > 20000 or out[5]["polls"] != "20000":
        return True, f"mode 4 polls {out[4]['polls']} / mode 5 polls {out[5]['polls']}"
    return False, "as expected"


def probe_freshness(root):
    """R2: a replayed TX is NACKed stale (nothing signed, nothing run); the host refuses duplicate / decreasing board frames"""
    s = e2e(root, "duplicate_tx")
    if "error" in s:
        return True, s["error"][:200]
    v = s["duplicate_tx"]
    if v["second"]["status"] != 7 or v["new_signreqs"] != 0 or v["new_trace_events"] != 0 or "stale sequence" not in v["second"]["reason"]:
        return True, f"duplicate_tx: status {v['second']['status']} signreqs {v['new_signreqs']} trace {v['new_trace_events']}"
    p = subprocess.run([sys.executable, "-B", "-c", f"""
import sys; sys.path[:0] = ['{R}/host', '{R}/b4/host']
import b4q_console_session as cs, b4q_wire as w
s = cs.ConsoleSession('{root}/unit_board_seq', label='unit'); s._fds = {{'c2h_r': -1}}
s._con_buf = (w.frame('HB', 7, s.token) + w.frame('HB', 7, s.token) + w.frame('HB', 6, s.token)).encode()
for _ in range(3): s._console_line()
print(s.stats['hb'], s.stats['stale_board'], s.halted is not None)"""], capture_output=True, text=True, timeout=120)
    if p.stdout.split() != ["1", "2", "True"]:
        return True, f"host board freshness: {p.stdout.strip()} {p.stderr[-120:]}"
    return False, "as expected"


def probe_latch(root):
    """R3: after a failed transaction a TX at the console boundary is NACKed 'halted' (nothing signed); the host's notary refuses while halted"""
    s = e2e(root, "after_stop_tx")
    if "error" in s:
        return True, s["error"][:200]
    v = s["after_stop_tx"]
    if v["raw_next"]["status"] != 7 or v["new_signreqs"] != 0 or v["new_trace_events"] != 0 or "halted" not in v["raw_next"]["reason"]:
        return True, f"after_stop_tx: status {v['raw_next']['status']} signreqs {v['new_signreqs']} trace {v['new_trace_events']}"
    p = subprocess.run([sys.executable, "-B", "-c", f"""
import sys, json; sys.path[:0] = ['{R}/host', '{R}/b4/host']
import b4q_console_session as cs, b4q_wire as w
s = cs.ConsoleSession('{root}/unit_halted_sign', label='unit'); s._fds = {{'h2c_w': -1}}; out = []
s._console_write = lambda line, note='': out.append(line)
s.halt('t'); s._answer_sign({{'payload': json.dumps({{'genome': '00000000', 'nonce': '0' * 16, 'req': 5}}).encode(), 'seq': 5}})
print(len(out), 'REFUSED 5' in w.parse(out[0], s.token)['payload'].decode() if out else None)"""], capture_output=True, text=True, timeout=120)
    if p.stdout.split() != ["1", "True"]:
        return True, f"host halted notary: {p.stdout.strip()} {p.stderr[-120:]}"
    return False, "as expected"


def probe_console_archive(root):
    """R4: dropped / corrupted / edited console material is never clean"""
    import re
    import shutil
    s = e2e(root, "valid")
    if "error" in s:
        return True, s["error"][:200]
    sys.path[:0] = [str(R / "host"), str(R / "b4/host")]
    import importlib
    import b4q_wire as w
    import b4q_verify as vf
    importlib.reload(vf)
    src = root / "valid"
    def copy(name):
        d = root / f"valid_console_{name}"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(src, d); return d
    def edit_line(d, pred, change):
        lines = [json.loads(l) for l in (d / "console.jsonl").read_text().splitlines() if l.strip()]
        for e in lines:
            if e.get("line") and pred(e):
                e["line"] = change(e["line"]); break
        (d / "console.jsonl").write_text("".join(json.dumps(e) + "\n" for e in lines))
    def reframe(line, edit):
        f = w.parse(line + "\n"); return w.frame(f["type"], f["seq"], f["token"], edit(f["payload"].decode())).rstrip("\n")
    d = copy("dropped"); (d / "console.jsonl").unlink()
    if not (vf.verify(d).get("refused") or ""):
        return True, "a dropped console log was not refused"
    cases = [("ident_crc", lambda e: e["dir"] == "board" and " IDENT " in e["line"], lambda l: l[:-1] + ("0" if l[-1] != "0" else "1")),
             ("result_fitness", lambda e: e["dir"] == "board" and " RESULT " in e["line"] and '"has_fitness": 1' in w.parse(e["line"] + "\n")["payload"].decode(),
              lambda l: reframe(l, lambda p: p.replace('"has_fitness": 1, "fitness": ', '"has_fitness": 1, "fitness": 999, "fitness_was": '))),
             ("ident_token", lambda e: e["dir"] == "board" and " IDENT " in e["line"], lambda l: reframe(l, lambda p: re.sub(r'"token": "[0-9a-f]{32}"', '"token": "' + "f" * 32 + '"', p))),
             ("end_transactions", lambda e: e["dir"] == "board" and " END " in e["line"], lambda l: reframe(l, lambda p: re.sub(r'"transactions": \d+', '"transactions": 999', p)))]
    for name, pred, change in cases:
        d = copy(name); edit_line(d, pred, change)
        rep = vf.verify(d)
        if rep.get("clean") or rep.get("agree"):
            return True, f"{name}: clean {rep.get('clean')} agree {rep.get('agree')}"
    for name, edit in (("cached_ident", lambda tr: tr["ident"].update({"token": "f" * 32})), ("cached_end", lambda tr: tr["end"].update({"transactions": 999}))):
        d = copy("m_" + name)
        m = json.loads((d / "manifest.json").read_text()); edit(m["transport"]); (d / "manifest.json").write_text(json.dumps(m))
        rep = vf.verify(d)
        if rep.get("clean") or rep.get("agree"):
            return True, f"{name}: clean {rep.get('clean')} agree {rep.get('agree')}"
    # the coordinated tampers: the console line AND the cached summary changed together — only the derivation can catch them
    for name, pred, change, edit in (("coord_ident_token", cases[2][1], cases[2][2], lambda tr: tr["ident"].update({"token": "f" * 32})),
                                     ("coord_end_transactions", cases[3][1], cases[3][2], lambda tr: tr["end"].update({"transactions": 999}))):
        d = copy(name); edit_line(d, pred, change)
        m = json.loads((d / "manifest.json").read_text()); edit(m["transport"]); (d / "manifest.json").write_text(json.dumps(m))
        rep = vf.verify(d)
        if rep.get("clean") or rep.get("agree"):
            return True, f"{name}: clean {rep.get('clean')} agree {rep.get('agree')}"
    return False, "never clean"


def probe_grammar(root):
    """R5: the six reproduced malformed commands are refused by the parser twin; a legitimate one parses"""
    D = "a" * 64
    cmds = ["TX mystery 0 0", "TX normal 100000000 0", "TX normal 0 1 100000000", "TX normal 0 0 GARBAGE", f"TX normal 0 0 TASK {D} 2 1 0 0 1", f"TX normal 0 0 TASK {D} 1 257 256 256 65537",
            "TX normal 00200000 0", "TX root 0 1 0", f"TX normal 0 1 0 TASK {D} 1 2 0 0 1", "TX normal 0 00000000001 0", "TX normal 000000001 0",
            f"TX normal 0 1 0 TASK {D} 2 1 0 0 1",                     # two cells declared, one given, the first valid (n = 1): the count itself
            "TX root 00000000 0", f"TX a5 18 1 1000001 TASK {D} 1 1 7 1 65535"]
    out = twin(cmds)
    if out[:12] != ["REFUSED"] * 12 or not out[12].startswith("OK kind=1") or not out[13].startswith("OK kind=3"):
        return True, f"parser: {out}"
    return False, "as expected"


def probe_c1_c3(root):
    """C1: both the transport and the console log removed is refused as a downgraded source; C3: a [] IDENT / END, a [] SIGNREQ, an
    object req, a broken RESULT, a float counter are named findings (exit 1), never clean, never a verifier error"""
    import re
    import shutil
    s = e2e(root, "valid")
    if "error" in s:
        return True, s["error"][:200]
    sys.path[:0] = [str(R / "host"), str(R / "b4/host")]
    import importlib
    import b4q_wire as w
    import b4q_verify as vf
    importlib.reload(vf)
    src = root / "valid"
    def copy(name):
        d = root / f"c13_{name}"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(src, d); return d
    d = copy("downgrade"); m = json.loads((d / "manifest.json").read_text()); m.pop("transport"); (d / "manifest.json").write_text(json.dumps(m)); (d / "console.jsonl").unlink()
    rep = vf.verify(d)
    if not rep.get("refused") or rep.get("clean"):
        return True, f"downgrade: refused {rep.get('refused')!r} clean {rep.get('clean')}"
    def reframe(line, edit):
        f = w.parse(line + "\n"); return w.frame(f["type"], f["seq"], f["token"], edit(f["payload"].decode())).rstrip("\n")
    for name, kind, edit in (("ident_array", "IDENT", lambda p: "[]"), ("end_array", "END", lambda p: "[]"), ("signreq_array", "SIGNREQ", lambda p: "[]"),
                             ("signreq_req_obj", "SIGNREQ", lambda p: re.sub(r'"req": \d+', '"req": {}', p)), ("result_broken", "RESULT", lambda p: "{broken"),
                             ("end_float", "END", lambda p: re.sub(r'"transactions": \d+', '"transactions": 4.0', p))):
        d = copy(name)
        lines = [json.loads(l) for l in (d / "console.jsonl").read_text().splitlines() if l.strip()]
        for e in lines:
            if e.get("line") and e["dir"] == "board" and f" {kind} " in e["line"]:
                e["line"] = reframe(e["line"], edit); break
        (d / "console.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
        if name == "end_float":
            m = json.loads((d / "manifest.json").read_text()); m["transport"]["end"]["transactions"] = 4.0; (d / "manifest.json").write_text(json.dumps(m))
        p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(d), "--json", str(d / "v.json")], capture_output=True, text=True)
        rep = json.loads((d / "v.json").read_text()) if (d / "v.json").is_file() else {}
        if p.returncode != 1 or rep.get("clean") or rep.get("agree") or "VERIFIER ERROR" in p.stdout:
            return True, f"{name}: exit {p.returncode} clean {rep.get('clean')} agree {rep.get('agree')} {p.stdout[:80]}"
    return False, "as expected"


def probe_c2(root):
    """C2: a changed TX genome, every TX removed, a changed reply request id, a reply before its request, the signed words changed in
    the console and the notary log together, the IDENT's nonce echo changed in the line and the cache together — never clean"""
    import re
    import shutil
    s = e2e(root, "valid")
    if "error" in s:
        return True, s["error"][:200]
    sys.path[:0] = [str(R / "host"), str(R / "b4/host")]
    import importlib
    import b4q_wire as w
    import b4q_verify as vf
    importlib.reload(vf)
    src = root / "valid"
    def copy(name):
        d = root / f"c2_{name}"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(src, d); return d
    def reframe(line, edit):
        f = w.parse(line + "\n"); return w.frame(f["type"], f["seq"], f["token"], edit(f["payload"].decode())).rstrip("\n")
    def lines_of(d):
        return [json.loads(l) for l in (d / "console.jsonl").read_text().splitlines() if l.strip()]
    def write(d, lines):
        (d / "console.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    is_tx = lambda e: e["dir"] == "host" and e.get("line") and " TX " in e["line"] and not e.get("note")
    is_reply = lambda e: e["dir"] == "host" and e.get("line") and " SIGNREPLY " in e["line"] and not e.get("note")
    cases = {}
    d = copy("tx_genome"); L = lines_of(d); e = [x for x in L if is_tx(x)][1]; e["line"] = reframe(e["line"], lambda p: p.replace("TX normal 00000000", "TX normal 00000001", 1)); write(d, L); cases["tx_genome"] = d
    d = copy("tx_removed"); L = [x for x in lines_of(d) if not is_tx(x)]; write(d, L); m = json.loads((d / "manifest.json").read_text()); m["transport"]["console_lines"] = len(L); (d / "manifest.json").write_text(json.dumps(m)); cases["tx_removed"] = d
    d = copy("reply_req"); L = lines_of(d); e = [x for x in L if is_reply(x)][0]; e["line"] = reframe(e["line"], lambda p: re.sub(r"^OK \d+", "OK 999999", p)); write(d, L); cases["reply_req"] = d
    d = copy("reply_first"); L = lines_of(d); ir = next(i for i, x in enumerate(L) if is_reply(x)); iq = next(i for i, x in enumerate(L) if x["dir"] == "board" and " SIGNREQ " in (x.get("line") or "")); L.insert(iq, L.pop(ir)); write(d, L); cases["reply_first"] = d
    d = copy("words_both"); L = lines_of(d); e = [x for x in L if is_reply(x)][0]; e["line"] = reframe(e["line"], lambda p: p[:-8] + ("00000000" if p[-8:] != "00000000" else "00000001")); write(d, L)
    nl = json.loads((d / "notary_log.json").read_text()); e0 = next(x for x in nl if "words" in x); e0["words"][23] = 0 if e0["words"][23] != 0 else 1; (d / "notary_log.json").write_text(json.dumps(nl)); cases["words_both"] = d
    d = copy("ident_echo"); L = lines_of(d); e = next(x for x in L if x["dir"] == "board" and " IDENT " in (x.get("line") or ""))
    e["line"] = reframe(e["line"], lambda p: re.sub(r'"page_nonce_seen": "[0-9a-f]{16}"', '"page_nonce_seen": "ffffffffffffffff"', p.replace('"nonce_echo_equal": 1', '"nonce_echo_equal": 0'))); write(d, L)
    m = json.loads((d / "manifest.json").read_text()); m["transport"]["ident"].update({"nonce_echo_equal": 0, "page_nonce_seen": "ffffffffffffffff"}); (d / "manifest.json").write_text(json.dumps(m)); cases["ident_echo"] = d
    # the echo flag ALONE changed (line + cache): only its derivation from the page and the opening can catch it
    d = copy("ident_echo_flag"); L = lines_of(d); e = next(x for x in L if x["dir"] == "board" and " IDENT " in (x.get("line") or ""))
    e["line"] = reframe(e["line"], lambda p: p.replace('"nonce_echo_equal": 1', '"nonce_echo_equal": 0')); write(d, L)
    m = json.loads((d / "manifest.json").read_text()); m["transport"]["ident"]["nonce_echo_equal"] = 0; (d / "manifest.json").write_text(json.dumps(m)); cases["ident_echo_flag"] = d
    # an extra RESULT (a copy of the last, a fresh board sequence) with the END's transaction count and the cached END raised to match:
    # the records still count four; only the exchange (a RESULT without an admitted TX) can catch it
    d = copy("extra_result"); L = lines_of(d)
    last_res = [x for x in L if x["dir"] == "board" and " RESULT " in (x.get("line") or "")][-1]
    end_i = next(i for i, x in enumerate(L) if x["dir"] == "board" and " END " in (x.get("line") or ""))
    fr_ = w.parse(last_res["line"] + "\n"); fe = w.parse(L[end_i]["line"] + "\n")
    extra = dict(last_res); extra["line"] = w.frame("RESULT", fe["seq"] - 1 + 1000, fr_["token"], fr_["payload"]).rstrip("\n"); extra["seq"] = fe["seq"] + 999
    endp = json.loads(fe["payload"].decode()); endp["transactions"] += 1; endp["lines"] += 1; endp["kicks"] += 1
    L[end_i]["line"] = w.frame("END", fe["seq"] + 1000, fe["token"], json.dumps(endp)).rstrip("\n"); L[end_i]["seq"] = fe["seq"] + 1000
    L.insert(end_i, extra); write(d, L)
    m = json.loads((d / "manifest.json").read_text()); m["transport"]["end"] = endp; m["transport"]["console_lines"] = len(L); (d / "manifest.json").write_text(json.dumps(m)); cases["extra_result"] = d
    for name, d in cases.items():
        rep = vf.verify(d)
        if rep.get("refused") or rep.get("clean") or rep.get("agree"):
            return True, f"{name}: refused {rep.get('refused')!r} clean {rep.get('clean')} agree {rep.get('agree')}"
    return False, "never clean"


def probe_c4(root):
    """C4: at SEQ_LIMIT - 1 in a silent sign wait, the next line is the terminal END with the limit's sequence; no wrap, nothing after"""
    p = subprocess.run([str(WAIT), "7"], capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        return True, f"exit {p.returncode}: {p.stdout.strip()[:100]}"
    out = dict(kv.split("=") for kv in p.stdout.split())
    if (out["first"], out["last"], out["lines"], out["wraps"], out["ends"], out["terminal"]) != ("ffffffef", "fffffff0", "2", "0", "1", "1"):
        return True, p.stdout.strip()[:160]
    return False, "as expected"


MUTANTS = [
    ("K1", APP, "    b4q_plat_kick(); S.sum.kicks_requested++;      /* the one place the watchdog is kicked: after a framed line went out */\n", "    S.sum.kicks_requested++;\n", "the watchdog kick removed (the application still CLAIMS the kicks)", probe_kicks),
    ("P1", WIRE, "    if (words[0] != B4Q_PAGE_MAGIC || words[1] != B4Q_PAGE_LAYOUT || words[B4Q_PAGE_WORDS - 1] != checksum) return -1;\n", "    if (words[0] != B4Q_PAGE_MAGIC || words[1] != B4Q_PAGE_LAYOUT) return -1;\n", "the page checksum no longer checked", probe_page_and_watchdog),
    ("P2", WIRE, "    for (i = 20; i < 23; i++) if (words[i] != 0u) return -1;      /* the reserved words are zero in layout 1 */\n", "", "the reserved page words no longer held to zero", probe_allowlist),
    ("W1", APP, '        if (b4q_plat_watchdog_start() != 0) { emit_end(B4Q_END_STOPPED, "the watchdog could not be armed"); return; }\n', "        (void)b4q_plat_watchdog_start();\n", "a watchdog that cannot be armed no longer ends the session", probe_page_and_watchdog),
    ("F1", WIRE, "    if (strcmp(expect, last + 1) != 0) return -1;\n", "", "the CRC no longer checked", probe_framing),
    ("F2", WIRE, "    if (want_token && strcmp(f[3], want_token) != 0) return -3;\n", "    if (want_token && strcmp(f[3], want_token) != 0) { /* accepted anyway */ }\n", "the token no longer refused (the comparison kept so that the build accepts the mutant: a kill must come from the probe)", probe_framing),
    ("F3", APP, "    if ((uint32_t)v != req_seq) return 0;\n", "    if (0) return 0;\n", "a SIGNREPLY to another request accepted (the stale reply's garbage words staged)", probe_framing),
    ("B1", APP, '            if (r == 0) { S.sign_why = "no SIGNREPLY within the attempt\'s budget"; break; }\n', "            if (r == 0) { b.left = B4Q_APP_REPLY_POLLS; continue; }\n", "the reply budget refilled when spent: the wait never ends", probe_bounds),
    ("B2", APP, '        if (rc == 0) { emit_end(B4Q_END_STOPPED, "no host command within the idle bound"); return; }\n', "        if (rc == 0) { continue; }\n", "the idle bound no longer ends the session", probe_bounds),
    ("A1", PSMAP, "    return 0;   /* the key window among the rest: the signer principal's, never this program's */\n", "    return off >= 0x2160u && off < 0x2170u;\n", "the key window writable", probe_allowlist),
    ("A2", PSMAP, "    return 0;   /* the identity page is the host's (written before `go`), the IDCODE is read-only, the key window absent */\n", "    return in_buffer(addr, B4Q_PSMAP_PAGE_ADDR, B4Q_PAGE_WORDS);\n", "the identity page writable by the program", probe_allowlist),
    # the round-2 guards (the owner's HOLD on ba18e3c)
    ("R1a", APP, "    if (b->left == 0 || S.terminal) return -1;\n    b->left--; b->spent++;\n", "    if (S.terminal) return -1;\n    b->spent++;\n", "the budget never spent (no poll charged)", probe_budget),
    ("R1b", APP, "            if (strcmp(f.type, \"SIGNREPLY\") != 0) continue;       /* another frame during the wait: charged, not this reply */\n", "            if (strcmp(f.type, \"SIGNREPLY\") != 0) { b.left = B4Q_APP_REPLY_POLLS; continue; }\n", "another frame replenishes the attempt's budget again", probe_budget),
    ("R1c", APP, "                    ready = poll_rx(b);\n                    if (ready < 0) return 0;\n                    if (ready && b4q_con_getc() == '\\n') break;\n", "                    if (b4q_con_rx_ready() && b4q_con_getc() == '\\n') break;\n", "the oversize discard uncharged again", probe_budget),
    ("R2a", APP, "        if (S.have_host_seq && f->seq <= S.last_host_seq) {     /* R2: a duplicate or decreasing host sequence has no effect */", "        if (0) {", "the host sequence no longer checked by the application", probe_freshness),
    ("R2b", SESSION, "            if self.board_seq is not None and f[\"seq\"] <= self.board_seq:        # R2: a duplicate or decreasing board sequence has no effect", "            if False:", "the board sequence no longer checked by the host", probe_freshness),
    ("R3a", APP, "            if (S.sum.halted) {                          /* R3: nothing further is run or signed after a transaction that did not close */", "            if (0) {", "the application's session latch removed (a TX after a failed one runs)", probe_latch),
    ("R3b", SESSION, "        if self.halted is not None:                       # R3: a halted session signs nothing more, whatever the application asks", "        if False:", "the host's notary no longer refuses while halted", probe_latch),
    ("R4a", VERIFY, "        _need((d / \"console.jsonl\").is_file(), \"console.jsonl: missing (the console source's retained lines are the evidence of its framing, identity and results)\")\n        console = jl(d / \"console.jsonl\")\n", "        console = jl(d / \"console.jsonl\") if (d / \"console.jsonl\").is_file() else []\n", "a dropped console log no longer refused by the console branch (since round 3 masked by C1a's source anchor, which refuses it first: see R4a+C1a)", probe_console_archive),
    ("R4b", VERIFY, "            if canon(m[\"obj\"]) != canon(r[\"fw\"]):\n                F.append(f\"board RESULT at line {m['idx']}: not the retained transaction result of {tx_dirs[cur['k']].name}\")\n", "", "the RESULT lines no longer held to the retained results", probe_console_archive),
    ("R4c", VERIFY, "                if o[\"token\"] != page[\"token\"] or o[\"carrier_sha256\"] != page[\"carrier_sha256\"] or o[\"flags\"] != page[\"flags\"] or o[\"uboot_epoch\"] != page[\"uboot_epoch\"]:\n", "                if o[\"carrier_sha256\"] != page[\"carrier_sha256\"] or o[\"flags\"] != page[\"flags\"] or o[\"uboot_epoch\"] != page[\"uboot_epoch\"]:\n", "the IDENT's token no longer held to the page", probe_console_archive),
    ("R4d", VERIFY, "            for kk, v in counts.items():\n                if o[kk] != v:\n                    F.append(f\"END.{kk} is {o[kk]}, the lines say {v}\")\n", "", "the END's counters no longer recomputed", probe_console_archive),
    ("R4e", VERIFY, "            if canon(o) != canon(tr[\"ident\"]):\n                F.append(\"the transport's cached IDENT is not the one the console carried\")\n", "", "the cached IDENT no longer held to the carried one", probe_console_archive),
    ("R5a", CMD, "    else return -1;                                      /* an unknown kind is refused, never defaulted */", "    else { while (*p && *p != ' ') p++; out->kind = B4Q_KIND_NORMAL; }", "an unknown kind consumed and defaulted to normal again", probe_grammar),
    ("R5b", CMD, "        if (n >= (base == 16 ? 8 : 10)) return -1;       /* more digits than the width allows: never truncated */\n", "", "a number wider than the field no longer refused", probe_grammar),
    ("R5c", CMD, "    return *p == 0 ? 0 : -1;                             /* nothing but trailing spaces after the grammar */", "    return 0;", "trailing text ignored again", probe_grammar),
    ("R5d", CMD, "                if (!spaces(&p) || b4q_cmd_u32(&p, 10, (unsigned long long)out->n_steps, &s) != 0 || s == 0) return -1;   /* 1 .. n */", "                if (!spaces(&p) || b4q_cmd_u32(&p, 10, (unsigned long long)out->n_steps, &s) != 0 || s == 0) break;", "a partial TASK accepted again (the count declared, fewer cells given)", probe_grammar),
    # the round-3 guards (the owner's HOLD on 0606758)
    ("C1a", VERIFY, "    console_expected = page_reads > 0 or Path(manifest[\"executing_side\"][\"binary\"]).name == \"b4q_apphost\"\n", "    console_expected = False\n", "the console source no longer anchored in the raw evidence (a downgrade verifies as host-only)", probe_c1_c3),
    ("C2a", VERIFY, "        if m[\"text\"] != want:\n            F.append(f\"host TX at line {m['idx']}: not the command of record {tx_dirs[k].name} (its kind / genome / declared steps / task)\")\n", "", "the admitted TX no longer held to its record's command", probe_c2),
    ("C2b", VERIFY, "            if phase != \"admitted\" or cur is None:\n                F.append(f\"board RESULT at line {m['idx']}: without an admitted TX\"); continue\n", "            if phase != \"admitted\" or cur is None:\n                continue\n", "a RESULT without an admitted TX no longer a finding", probe_c2),
 ("C2c", VERIFY, "                if req is None:\n                    F.append(f\"host SIGNREPLY at line {m['idx']}: answers request {o['req']}, which is not an open request of the current transaction\")\n                    continue\n", "                if req is None:\n                    continue\n", "a reply to no open request (a changed id, a reply before its request) no longer a finding", probe_c2),
    ("C2d", VERIFY, "                    elif staged != q[\"answered\"][\"words\"]:\n                        F.append(f\"the words staged into PAYLOAD / TAG after request {q['req']}'s reply are not the reply's\")\n", "", "the reply's words no longer held to the staged PAYLOAD / TAG writes", probe_c2),
    ("C2e", VERIFY, "                if o[\"nonce_echo_equal\"] != int(f\"{page['nonce_seen']:016x}\" == o[\"open\"][\"nonce\"]):\n                    F.append(\"the IDENT's nonce echo flag is not what the page and the opening say\")\n", "", "the IDENT's nonce echo no longer derived from the page and the opening", probe_c2),
    ("C3a", VERIFY, "    if not isinstance(obj, dict):\n        return \"not an object\"\n", "    if not isinstance(obj, dict):\n        return None\n", "a non-object payload passes the shape check (its contracts skipped)", probe_c1_c3),
    ("C3b", VERIFY, "            if type(v) is not int:\n                return f\"{k}: not an int\"\n", "            if not isinstance(v, (int, float)):\n                return f\"{k}: not an int\"\n", "a float counter accepted as an int again", probe_c1_c3),
    ("C4a", APP, "    if (S.seq >= B4Q_APP_SEQ_LIMIT) {                /* C4: the last usable sequence carries the terminal END, whatever this line was going to be */", "    if (0) {", "the emitter's exhaustion gate removed (the sequence wraps inside a wait)", probe_c4),
]


COMBINED = [
    ("R4a+C1a", ["R4a", "C1a"], "the source anchor AND the console branch's log requirement removed: a dropped console log verifies", probe_console_archive),
]


def _m(mid):
    return [m for m in MUTANTS if m[0] == mid][0]


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    out = R / "evidence/b4/unit_b4q_image_2026_10_28/mutants.txt"
    if "--out" in argv:
        i = argv.index("--out"); out = R / argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    only = set(argv)
    lines = [f"B4Q PS-image mutant battery — {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} HEAD {subprocess.run(['git', '-C', str(R), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()}"]
    killed = survived = missed = 0
    tmp = Path(tempfile.mkdtemp(prefix="b4q_img_mut_"))
    subprocess.run(BUILD, check=True, capture_output=True)
    for name, probe in (("kicks", probe_kicks), ("page_and_watchdog", probe_page_and_watchdog), ("framing", probe_framing), ("bounds", probe_bounds), ("allowlist", probe_allowlist),
                        ("budget", probe_budget), ("freshness", probe_freshness), ("latch", probe_latch), ("console_archive", probe_console_archive), ("grammar", probe_grammar),
                        ("c1_c3", probe_c1_c3), ("c2", probe_c2), ("c4", probe_c4)):
        broken, why = probe(tmp / "base")
        lines.append(f"BASELINE {name}: {'BROKEN — ' + why if broken else 'green'}")
        if broken:
            print("\n".join(lines)); out.write_text("\n".join(lines) + "\n"); return 2
    n = 0
    for mid, path, old, new, what, probe in MUTANTS:
        if only and mid not in only:
            continue
        n += 1
        text = path.read_text(); before = sha(path)
        if text.count(old) != 1:
            lines.append(f"{mid} EDIT-MISS ({text.count(old)} occurrences) — {what}"); missed += 1; continue
        try:
            path.write_text(text.replace(old, new))
            b = subprocess.run(BUILD, capture_output=True, text=True)
            if b.returncode != 0:
                lines.append(f"{mid} KILLED (the build refused the mutant) — {what}"); killed += 1; continue
            root = tmp / mid; root.mkdir(parents=True, exist_ok=True)
            broken, why = probe(root)
        finally:
            path.write_text(text); assert sha(path) == before, f"{path} not restored"
            subprocess.run(BUILD, check=True, capture_output=True)
        if broken:
            killed += 1; lines.append(f"{mid} KILLED — {what}: {why[:160]}")
        else:
            survived += 1; lines.append(f"{mid} SURVIVED — {what}: {why[:160]}")
        print(lines[-1], flush=True)
    for mid, parts, what, probe in COMBINED:
        if only and mid not in only:
            continue
        n += 1
        edits = [_m(x) for x in parts]
        saved = {e[1]: (e[1].read_text(), sha(e[1])) for e in edits}
        if any(saved[e[1]][0].count(e[2]) != 1 for e in edits):
            lines.append(f"{mid} EDIT-MISS — {what}"); missed += 1; continue
        try:
            for e in edits:
                e[1].write_text(e[1].read_text().replace(e[2], e[3]))
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
    lines.append(f"TOTAL killed {killed} survived {survived} edit-miss {missed} of {n}")
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
