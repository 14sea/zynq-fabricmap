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
APP, WIRE, PSMAP = FW / "target/b4q_app.c", FW / "target/b4q_wire.c", FW / "target/b4q_psmap.c"
BUILD = ["make", "-C", str(FW), f"BUILD={R / 'build/b4q_firmware'}", "apphost", "wiretwin"]
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


MUTANTS = [
    ("K1", APP, "    b4q_plat_kick(); S.sum.kicks_requested++;      /* the one place the watchdog is kicked: after a framed line went out */\n", "    S.sum.kicks_requested++;\n", "the watchdog kick removed (the application still CLAIMS the kicks)", probe_kicks),
    ("P1", WIRE, "    if (words[0] != B4Q_PAGE_MAGIC || words[1] != B4Q_PAGE_LAYOUT || words[B4Q_PAGE_WORDS - 1] != checksum) return -1;\n", "    if (words[0] != B4Q_PAGE_MAGIC || words[1] != B4Q_PAGE_LAYOUT) return -1;\n", "the page checksum no longer checked", probe_page_and_watchdog),
    ("P2", WIRE, "    for (i = 20; i < 23; i++) if (words[i] != 0u) return -1;      /* the reserved words are zero in layout 1 */\n", "", "the reserved page words no longer held to zero", probe_allowlist),
    ("W1", APP, '        if (b4q_plat_watchdog_start() != 0) { emit_end(B4Q_END_STOPPED, "the watchdog could not be armed"); return; }\n', "        (void)b4q_plat_watchdog_start();\n", "a watchdog that cannot be armed no longer ends the session", probe_page_and_watchdog),
    ("F1", WIRE, "    if (strcmp(expect, last + 1) != 0) return -1;\n", "", "the CRC no longer checked", probe_framing),
    ("F2", WIRE, "    if (want_token && strcmp(f[3], want_token) != 0) return -3;\n", "    if (want_token && strcmp(f[3], want_token) != 0) { /* accepted anyway */ }\n", "the token no longer refused (the comparison kept so that the build accepts the mutant: a kill must come from the probe)", probe_framing),
    ("F3", APP, "            if (strncmp(g_plain, \"OK \", 3) == 0 && sscanf(g_plain + 3, \"%lu\", &got_req) == 1 && got_req == req_seq) {", "            if (strncmp(g_plain, \"OK \", 3) == 0 && sscanf(g_plain + 3, \"%lu\", &got_req) == 1) {", "a SIGNREPLY to another request accepted (the stale reply's garbage words staged)", probe_framing),
    ("B1", APP, '            if (r == 0) { S.sign_why = "no SIGNREPLY within the bound"; break; }\n', "            if (r == 0) { continue; }\n", "the reply bound no longer ends the wait", probe_bounds),
    ("B2", APP, '        if (rc == 0) { emit_end(B4Q_END_STOPPED, "no host command within the idle bound"); return; }\n', "        if (rc == 0) { continue; }\n", "the idle bound no longer ends the session", probe_bounds),
    ("A1", PSMAP, "    return 0;   /* the key window among the rest: the signer principal's, never this program's */\n", "    return off >= 0x2160u && off < 0x2170u;\n", "the key window writable", probe_allowlist),
    ("A2", PSMAP, "    return 0;   /* the identity page is the host's (written before `go`), the IDCODE is read-only, the key window absent */\n", "    return in_buffer(addr, B4Q_PSMAP_PAGE_ADDR, B4Q_PAGE_WORDS);\n", "the identity page writable by the program", probe_allowlist),
]


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
    for name, probe in (("kicks", probe_kicks), ("page_and_watchdog", probe_page_and_watchdog), ("framing", probe_framing), ("bounds", probe_bounds), ("allowlist", probe_allowlist)):
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
    lines.append(f"TOTAL killed {killed} survived {survived} edit-miss {missed} of {n}")
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
