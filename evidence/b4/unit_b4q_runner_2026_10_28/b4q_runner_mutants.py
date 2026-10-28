#!/usr/bin/env python3
"""The runner unit's FOCUSED mutant battery (host-only): one text edit at a time in the unit's own guards — the evidence log
(b4q_ring.c), the application's export path (b4q_app.c), the adapter (b4q_evidence_log.py), the verifier's source rules
(b4q_verify.py), the session's pull (b4q_console_session.py), the runner's control plane (b4q_runner.py) — restored byte for byte,
each probed by the scenario, the archive mutation or the direct call that observes the guard it removes. The discipline of the
earlier batteries: a mutant is killed only by a probe that observes its fault condition; an EDIT-MISS or a run of 0 is never a kill;
a survivor is named with what masks it; a probe that cannot run is PROBE-ERROR, not a kill; a hang caught by a timeout is a kill
only where the guard removed IS a bound, and is marked so. Run from the repository root:
    python3 -B evidence/b4/unit_b4q_runner_2026_10_28/b4q_runner_mutants.py [--out f] [ids…]"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

R = Path(__file__).resolve().parents[3]
FW = R / "firmware/b4q"
RING, APP = FW / "target/b4q_ring.c", FW / "target/b4q_app.c"
ADAPTER, VERIFY, SESSION, RUNNER = R / "host/b4q_evidence_log.py", R / "host/b4q_verify.py", R / "host/b4q_console_session.py", R / "host/b4q_runner.py"
VRUNNER, YMODEM = R / "host/b4q_verify_runner.py", R / "host/b4q_ymodem.py"
BUILD = ["make", "-C", str(FW), f"BUILD={R / 'build/b4q_firmware'}", "apphost", "wiretwin", "waittwin", "seqcut"]
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fresh(prefix="b4q_mut_") -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


def console_e2e(root: Path, *names: str, source: str | None = None, timeout: int = 300) -> dict:
    args = [sys.executable, "-B", str(R / "host/b4q_console_e2e.py")] + (["--source", source] if source else []) + [str(root), *names]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"timeout": True}
    if p.returncode != 0:
        return {"error": (p.stdout[-1500:] + p.stderr[-2500:]).replace("\n", " | ")}
    return {s["name"]: s for s in json.loads((root / "e2e_summary.json").read_text())}


def runner_e2e(root: Path, *names: str, timeout: int = 300) -> dict:
    try:
        p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_runner_e2e.py"), str(root), *names], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"timeout": True}
    if not (root / "e2e_summary.json").is_file():
        return {"error": (p.stdout[-400:] + p.stderr[-400:]).replace("\n", " | ")}
    return {s["name"]: s for s in json.loads((root / "e2e_summary.json").read_text())}


def verify(d: Path) -> dict:
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(d), "--json", str(d / "verify.json")], capture_output=True, text=True, timeout=600)
    try:
        return json.loads((d / "verify.json").read_text())
    except (OSError, ValueError):
        return {"error": (p.stdout[-300:] + p.stderr[-300:]).replace("\n", " | "), "refused": None, "agree": None, "session": [], "source": {"findings": []}}


_VALID: dict = {}


def valid_ps_archive() -> Path:
    """One PS-source valid archive produced with the UNMUTATED host (built before the battery edits anything): the archive mutations' base."""
    if "ps" not in _VALID:
        root = fresh("b4q_base_")
        s = console_e2e(root, "valid", source="ps-evidence-log-v1")
        if "valid" not in s:
            raise RuntimeError(f"no base archive: {s}")
        _VALID["ps"] = root / "valid"
    d = fresh() / "valid"
    shutil.copytree(_VALID["ps"], d)
    return d


# ---------------------------------------------------------------- the probes: each observes ONE guard
def _ran(s: dict, name: str, expect: str | None = None):
    """A scenario that did not run is never a kill: an e2e error whose text carries the expected halt IS the guard firing (the scenario's own
    assertions abort on it); any other error is a PROBE-ERROR (raised)."""
    if name in s:
        return None
    err = s.get("error") or ("TIMEOUT" if s.get("timeout") else str(s))
    if expect and expect in err:
        return True, f"the scenario aborted on the guard: …{err[err.find(expect) - 40:err.find(expect) + 120]}"
    raise RuntimeError(f"the scenario did not run: …{err[-400:]}")


def probe_log_vs_emulation(root):
    """the emulated valid scenario retains the PS log beside the fake's trace: the verifier holds the two witnesses equal"""
    s = console_e2e(root, "valid")
    r = _ran(s, "valid")
    if r:
        return r
    rep = verify(root / "valid")
    f = rep.get("source", {}).get("findings", [])
    if any("not the emulation" in x for x in f):
        return True, f"source: {f[0][:120]}"
    return False, f"agrees_with_emulation={rep.get('source', {}).get('agrees_with_emulation')}"


def probe_ps_halts(expect: str, scenario: str = "valid"):
    def probe(root):
        s = console_e2e(root, scenario, source="ps-evidence-log-v1")
        r = _ran(s, scenario, expect)
        if r:
            return r
        h = s[scenario].get("halted") or ""
        if expect in h:
            return True, f"halted: {h[:120]}"
        return False, f"halted={h[:80]!r}"
    probe.__doc__ = f"the PS-source {scenario} scenario halts on '{expect}'"
    return probe


def probe_ps_verify_finds(expect: str, where: str = "any"):
    def probe(root):
        s = console_e2e(root, "valid", source="ps-evidence-log-v1")
        r = _ran(s, "valid", expect)
        if r:
            return r
        rep = verify(root / "valid")
        pool = rep.get("session", []) + rep.get("source", {}).get("findings", []) + (rep.get("console") or {}).get("findings", []) + [m for T in rep.get("transactions", []) for m in T.get("findings", [])]
        hit = [x for x in pool if expect in x]
        if hit or (rep.get("agree") is False and where == "agree"):
            return True, f"verify: {(hit or rep.get('session') or ['disagree'])[0][:120]}"
        return False, f"verify agree={rep.get('agree')} findings={pool[:2]}"
    probe.__doc__ = f"the PS-source valid archive's verification finds '{expect}'"
    return probe


def probe_bad_page_pulled(root):
    """an END before the IDENT (a bad page) still has its log pulled through the export epilogue: the archive's source holds the END's bytes"""
    s = console_e2e(root, "bad_page", source="ps-evidence-log-v1")
    r = _ran(s, "bad_page")
    if r:
        return r
    m = json.loads((root / "bad_page/manifest.json").read_text())
    src, end = m.get("source") or {}, (m.get("transport") or {}).get("end") or {}
    if src.get("bytes", 0) >= end.get("log", 1) and src.get("digest_equal"):
        return False, f"pulled {src.get('bytes')} bytes = the END's position"
    return True, f"pulled {src.get('bytes')} of the END's {end.get('log')} bytes; halted={m.get('halted', '')[:80]!r}"


def probe_open_halts(expect: str):
    """a PS-source session driven directly: its opening's pull halts by name (the first halt is the latched one)"""
    def probe(root):
        import b4q_console_session as cs
        s = cs.ConsoleSession(root / "open", source="ps-evidence-log-v1")
        try:
            try:
                s.open()
            except Exception as e:                            # the opening may refuse after the halt: the halt reason is what is observed
                pass
            h = s.halted or ""
            if expect in h:
                return True, f"halted: {h[:120]}"
            return False, f"halted={h[:100]!r} pulls={s.pull_stats}"
        finally:
            s.stop()
    probe.__doc__ = f"the PS-source opening halts on '{expect}'"
    return probe


def probe_epilogue_nack(root):
    """a TX after the END is NACKed 'ended: export only' (the epilogue admits exports and QUIT alone)"""
    import b4q_console_session as cs
    import b4q_session as ss
    s = cs.ConsoleSession(root / "epi", source="ps-evidence-log-v1")
    try:
        s.open()
        s._send("QUIT"); r = s.serve("END")
        if r.get("status") != cs.END_STATUS:
            return True, f"no END after QUIT: {r}"
        s._console_write(s._frame_out("TX", "TX root 00000000 0"))
        try:
            r = s.serve("RESULT")
        except ss.SessionRefusal as e:
            return True, f"no NACK: {e}"
        if r.get("status") == cs.NACK_STATUS and "export only" in r.get("reason", ""):
            return False, "NACKed by name"
        return True, f"answered with {r}"
    finally:
        s.stop()


def probe_overflow_nack(root):
    """after the log overflows the application NACKs the next TX 'the evidence log is full' (the emulated-source host does not pull, so it sends one)"""
    import b4q_console_session as cs
    import b4q_console_e2e as ce
    os.environ["B4Q_APP_HOST_RING_BYTES"] = "16384"
    try:
        s = cs.ConsoleSession(root / "ovf")
        try:
            s.open(); s.transaction("root", 0, ce.stim([]))
            e = s.transaction("normal", ce.G_CESR, ce.stim(ce.FIX1))
            fw = e["firmware"]
            if fw.get("status") == cs.NACK_STATUS and "evidence log is full" in fw.get("reason", ""):
                return False, "NACKed by name"
            return True, f"the TX after the overflow answered with status {fw.get('status')} ({fw.get('reason', '')[:60]})"
        finally:
            s.stop()
    finally:
        del os.environ["B4Q_APP_HOST_RING_BYTES"]


def probe_parse_refuses(root):
    """the adapter refuses a truncated tail, a run outside the buffers and an unknown mark"""
    import importlib
    import b4q_evidence_log as el
    importlib.reload(el)
    raw = (valid_ps_archive() / "raw/evidence_log.bin").read_bytes()
    try:
        el.parse(raw[:-5]); return True, "a truncated tail parsed"
    except el.LogRefusal:
        pass
    win = next(r for r in el.parse(raw) if r["kind"] == el.KIND_WIN)
    rec = bytearray(raw[win["off"]:win["off"] + 16]); rec[6] |= 0x40
    try:
        el.parse(bytes(rec)); return True, "a run record outside the buffers parsed"
    except el.LogRefusal:
        pass
    rec = bytearray(raw[:16]); rec[4] = el.KIND_MARK; rec[8:12] = (99).to_bytes(4, "big")
    try:
        el.parse(bytes(rec)); return True, "an unknown mark parsed"
    except el.LogRefusal:
        return False, "refused by name"


def _synthetic(records_spec):
    """records as the adapter parses them, from (kind, op, count, addr, data, run) tuples; offsets assigned"""
    import b4q_evidence_log as el
    out = []
    for k, (kind, op, count, addr, data, run) in enumerate(records_spec):
        out.append({"off": 16 * k, "tick": k, "kind": kind, "op": op, "count": count, "run": run, "refused": False, "addr": addr, "data": data})
    return out


def probe_stale_staging(root):
    """a staging followed by another write into the same envelope is NOT the submitted stream (the 'untouched since' rule)"""
    import importlib
    import b4q_backend as bk
    import b4q_evidence_log as el
    import b4q_frames as fr
    importlib.reload(el)
    raw = (valid_ps_archive() / "raw/evidence_log.bin").read_bytes()
    words = el.stagings(el.parse(raw))[0]["words"]                               # a real staged stream (the base archive's first), re-staged synthetically
    spec = [(el.KIND_BUF, "wr", 1, bk.WR_BUF + 4 * i, words[i], False) for i in range(fr.STREAM_WORDS)]
    spec.append((el.KIND_BUF, "wr", 1, bk.WR_BUF + 4 * 7, 0xDEADBEEF, False))          # a later write into the staged envelope
    spec += [(el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_SRC_ADDR, bk.WR_BUF | bk.DMA_HOLD_TAG, False), (el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_DEST_ADDR, bk.PCAP_ENDPOINT, False),
             (el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_SRC_LEN, fr.STREAM_WORDS, False), (el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_DEST_LEN, 0, False)]
    D = el.derive(_synthetic(spec))
    subs = [e for e in D["pcap"] if e["pcap"] == "stream_submitted"]
    if subs:
        return True, "a stale staging reported as the submitted stream"
    return False, "no stream_submitted for a touched envelope"


def probe_group_order(root):
    """eight frames read back out of the pinned FAR order are not a link-3 group"""
    import importlib
    import b4q_backend as bk
    import b4q_evidence_log as el
    import b4q_frames as fr
    importlib.reload(el)
    spec = []
    fars = list(fr.TARGET_FARS); fars[0], fars[1] = fars[1], fars[0]
    for far in fars:
        cmd = fr.build_readback_command(far)
        spec += [(el.KIND_BUF, "wr", 1, bk.CMD_BUF + 4 * i, cmd[i], False) for i in range(fr.READBACK_CMD_WORDS)]
        spec += [(el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_SRC_ADDR, bk.CMD_BUF | bk.DMA_HOLD_TAG, False), (el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_DEST_ADDR, bk.PCAP_ENDPOINT, False),
                 (el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_SRC_LEN, fr.READBACK_CMD_WORDS, False), (el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_DEST_LEN, 0, False)]
        spec += [(el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_SRC_ADDR, bk.PCAP_ENDPOINT, False), (el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_DEST_ADDR, bk.DST_BUF | bk.DMA_HOLD_TAG, False),
                 (el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_SRC_LEN, 0, False), (el.KIND_DEVC, "wr", 1, bk.DEVCFG_DMA_DEST_LEN, fr.READBACK_WORDS, False)]
        spec += [(el.KIND_BUF, "rd", 1, bk.DST_BUF + 4 * i, far & 0xFF, False) for i in range(fr.FRAME_WORDS, fr.READBACK_WORDS)]
    D = el.derive(_synthetic(spec))
    rf = [e for e in D["pcap"] if e["pcap"] == "read_frame"]
    if len(rf) != 8:
        return True, f"{len(rf)} read_frame entries derived, not 8 (the probe cannot reach the grouping)"
    if any(e["target_frames_hash"] for e in rf):
        return True, "an out-of-order octet hashed as a group"
    return False, "no group for the wrong order"


def probe_archive(mutate, expect: str, refused: bool = False):
    def probe(root):
        d = valid_ps_archive()
        mutate(d)
        rep = verify(d)
        pool = rep.get("session", []) + rep.get("source", {}).get("findings", []) + (rep.get("console") or {}).get("findings", [])
        if refused:
            if rep.get("refused") and expect in rep["refused"]:
                return False, f"refused: {rep['refused'][:100]}"
            return True, f"not refused by name: refused={rep.get('refused')!r} findings={pool[:2]}"
        if any(expect in x for x in pool):
            return False, "found by name"
        return True, f"not found: refused={rep.get('refused')!r} agree={rep.get('agree')} findings={pool[:2]}"
    probe.__doc__ = f"the mutated valid archive is {'refused' if refused else 'found'}: '{expect}'"
    return probe


def _m_manifest(fn):
    def m(d):
        mf = json.loads((d / "manifest.json").read_text()); fn(mf); (d / "manifest.json").write_text(json.dumps(mf, indent=1) + "\n")
    return m


def _m_raw_flip_declared(d):
    raw = bytearray((d / "raw/evidence_log.bin").read_bytes()); raw[12] ^= 1; raw = bytes(raw)
    (d / "raw/evidence_log.bin").write_bytes(raw)
    _m_manifest(lambda mf: mf["source"].update({"sha256": hashlib.sha256(raw).hexdigest()}))(d)


def _m_raw_flip(d):
    raw = bytearray((d / "raw/evidence_log.bin").read_bytes()); raw[12] ^= 1; (d / "raw/evidence_log.bin").write_bytes(bytes(raw))


def _m_trace(d):
    lines = (d / "trace.jsonl").read_text().splitlines(); e = json.loads(lines[len(lines) // 2]); e["data"] ^= 1
    lines[len(lines) // 2] = json.dumps(e); (d / "trace.jsonl").write_text("\n".join(lines) + "\n")


def _m_console_i(d):
    lines = (d / "console.jsonl").read_text().splitlines()
    k = next(i for i, l in enumerate(lines) if json.loads(l).get("type") == "RESULT")
    e = json.loads(lines[k]); e["i"] += 1; lines[k] = json.dumps(e); (d / "console.jsonl").write_text("\n".join(lines) + "\n")


def _m_tx_after_end(d):
    lines = (d / "console.jsonl").read_text().splitlines()
    k = next(i for i, l in enumerate(lines) if json.loads(l).get("type") == "END")
    host = json.loads(next(l for l in lines if json.loads(l)["dir"] == "host" and (json.loads(l).get("line") or "").startswith("B4Q1 TX ")))
    import b4q_wire as wire
    f = wire.parse(host["line"] + "\n", None)
    tx = {"i": json.loads(lines[k])["i"], "pcap_n": 0, "dir": "host", "line": wire.frame("TX", 4000, f["token"], f["payload"]).rstrip("\n"), "note": ""}
    lines.insert(k + 1, json.dumps(tx)); (d / "console.jsonl").write_text("\n".join(lines) + "\n")
    _m_manifest(lambda mf: mf["transport"].update({"console_lines": mf["transport"]["console_lines"] + 1}))(d)


def _m_banner_bytes(d):
    """a line noted as a boot banner whose bytes are a framed HB (R1: the note is not authority)"""
    lines = (d / "console.jsonl").read_text().splitlines()
    k = next(i for i, l in enumerate(lines) if json.loads(l).get("type") == "HB")
    e = json.loads(lines[k]); e["note"] = "a boot banner: the PS reset mid-session"; e.pop("type", None); e.pop("seq", None)
    lines[k] = json.dumps(e); (d / "console.jsonl").write_text("\n".join(lines) + "\n")
    _m_manifest(lambda mf: mf.update({"interrupted": {"transport": "x", "console_line": k}}))(d)


def probe_runner(name: str, expect_stop: str | None = None, expect_opened: bool | None = None, timeout: int = 300):
    def probe(root):
        s = runner_e2e(root, name, timeout=timeout)
        if s.get("timeout"):
            return True, f"TIMEOUT after {timeout} s (a hang: the bound removed IS the guard)"
        if name not in s:
            raise RuntimeError(f"the scenario did not run: {str(s)[:200]}")
        v = s[name]
        stop = (v.get("stop") or {}).get("why", "")
        if expect_stop is not None and not stop.startswith(expect_stop):
            return True, f"stop {stop[:80]!r} (expected {expect_stop!r}); opened={v.get('opened')}"
        if expect_opened is not None and bool(v.get("opened")) != expect_opened:
            return True, f"opened={v.get('opened')}"
        if v.get("expect_failures"):
            return True, f"expectations: {v['expect_failures'][:2]}"
        return False, f"as expected ({stop[:60] or 'no stop'})"
    probe.__doc__ = f"the runner scenario {name}: stop {expect_stop!r} / opened {expect_opened}"
    return probe


# ---------------------------------------------------------------- the repair's guards (the owner's R1–R3 on dad9e4de): the runner, its archive contract, the transport
def _tests():
    """The tests' fakes (FakePort, the scripted U-Boot) without the module's heavy setup."""
    import importlib
    sys.path.insert(0, str(R / "tests"))
    T = importlib.import_module("test_b4q_runner")
    T.setUpModule = lambda: None
    for mod in ("b4q_runner", "b4q_verify_runner", "b4q_verify", "b4q_ymodem", "b4q_console_session", "b4q_device_fixture"):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    importlib.reload(T)
    T.setUpModule = lambda: None
    return T


_RUNNER_VALID: dict = {}


def valid_runner_archive() -> Path:
    """One runner `valid` archive produced over the surrogate with the UNMUTATED tree, copied per use."""
    if "d" not in _RUNNER_VALID:
        root = fresh("b4q_rbase_")
        s = runner_e2e(root, "valid")
        if "valid" not in s or s["valid"].get("expect_failures"):
            raise RuntimeError(f"no base runner archive: {str(s)[:200]}")
        _RUNNER_VALID["d"] = root / "valid"
    d = fresh() / "valid"
    shutil.copytree(_RUNNER_VALID["d"], d)
    return d


def _runner_edit(d: Path, fn):
    u = json.loads((d / "uboot.json").read_text()); m = json.loads((d / "manifest.json").read_text())
    fn(u, m)
    m["transport"]["runner"] = u
    (d / "uboot.json").write_text(json.dumps(u, indent=1) + "\n"); (d / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")


def probe_runner_archive(mutate, expect: str):
    def probe(root):
        import importlib
        import b4q_verify as vf
        importlib.reload(sys.modules["b4q_verify_runner"]) if "b4q_verify_runner" in sys.modules else None
        importlib.reload(vf)
        d = valid_runner_archive()
        mutate(d)
        rep = vf.verify(d)
        pool = rep.get("session", []) + ([rep["refused"]] if rep.get("refused") else [])
        if any(expect in x for x in pool):
            return False, "found by name"
        return True, f"not found: agree={rep.get('agree')} refused={rep.get('refused')!r} findings={pool[:2]}"
    probe.__doc__ = f"the mutated runner valid archive is found: '{expect}'"
    return probe


def _m_transfer_flip(d: Path):
    """One payload byte of the transferred image flipped in the SENT stream (its block CRC-16 and the device's crc line made consistent with
    the flipped bytes, the witnesses too): only the identity check (the transferred bytes vs the executing-side image) can find it."""
    import zlib
    import b4q_verify_runner as vr
    tx = bytearray((d / "raw/console_tx.bin").read_bytes()); rx = bytearray((d / "raw/console.bin").read_bytes())
    k = tx.find(bytes([1, 0, 0xFF])); pos = k + 3 + 130
    assert tx[pos] == 2
    tx[pos + 3 + 5] ^= 1
    payload = bytes(tx[pos + 3:pos + 3 + 1024]); tx[pos + 3 + 1024:pos + 3 + 1026] = vr._crc16(payload).to_bytes(2, "big")
    full, info = vr.ymodem_payload(bytes(tx), k - 20)
    crc = zlib.crc32(full) & 0xFFFFFFFF
    m = vr.CRC_RE.search(bytes(rx)); rx[m.start(3):m.end(3)] = f"{crc:08x}".encode()
    (d / "raw/console_tx.bin").write_bytes(bytes(tx)); (d / "raw/console.bin").write_bytes(bytes(rx))
    def fix(u, mf):
        u["raw"].update({"console_bin_sha256": hashlib.sha256(bytes(rx)).hexdigest(), "console_tx_bin_sha256": hashlib.sha256(bytes(tx)).hexdigest()})
        u["load_witness"].update({"host_crc32": f"{crc:08x}", "uboot_crc32": f"{crc:08x}", "equal": True, "image_sha256": hashlib.sha256(full).hexdigest()})
        for s in u["uboot_steps"]:
            if s["what"] == "crc32":
                s["crc32"] = f"{crc:08x}"
        u["admission"]["image"]["file_sha256"] = hashlib.sha256(full).hexdigest()
    _runner_edit(d, fix)


def _m_invented_stop(d: Path):
    (d / "session_open.json").write_text("null\n")
    import shutil as sh
    for p in d.glob("tx_*"):
        sh.rmtree(p)
    _runner_edit(d, lambda u, m: (m.update({"records": [], "no_session": True}), u.update({"phase": "stopped", "phase_at_stop": "pre-go", "stops": [{"why": "load witness: invented", "kind": "TransportStop"}]})))


def _m_crc_range(d: Path):
    import b4q_verify_runner as vr
    rx = bytearray((d / "raw/console.bin").read_bytes())
    m = vr.CRC_RE.search(bytes(rx)); end = int(m.group(2), 16) - 4
    rx[m.start(2):m.end(2)] = f"{end:08x}".encode()
    (d / "raw/console.bin").write_bytes(bytes(rx))
    def fix(u, mf):
        u["raw"]["console_bin_sha256"] = hashlib.sha256(bytes(rx)).hexdigest()
        for s in u["uboot_steps"]:
            if s["what"] == "crc32":
                s["range"][1] = f"{end:08x}"
    _runner_edit(d, fix)


def _m_console_line(d: Path):
    lines = (d / "console.jsonl").read_text().splitlines()
    k = next(i for i, l in enumerate(lines) if json.loads(l).get("type") == "HB")
    e = json.loads(lines[k]); e["line"] = e["line"][:-8] + "00000000"; lines[k] = json.dumps(e); (d / "console.jsonl").write_text("\n".join(lines) + "\n")


def probe_device_downgrade(root):
    """a PTY archive rewritten into the device format but keeping the surrogate's banner is found by the provenance check"""
    import importlib
    import b4q_device_fixture as df
    import b4q_verify as vf
    importlib.reload(sys.modules["b4q_verify_runner"]) if "b4q_verify_runner" in sys.modules else None
    importlib.reload(vf)
    out = fresh() / "dg"
    df.make(valid_runner_archive(), out, downgrade="keep-banner")
    rep = vf.verify(out)
    if any("surrogate's banner" in x for x in rep.get("session", [])):
        return False, "found by name"
    return True, f"not found: agree={rep.get('agree')} findings={rep.get('session', [])[:2]}"


def probe_fake(kind: str):
    """the runner against the tests' scripted U-Boot (no device): the named guard observed directly"""
    def probe(root):
        T = _tests()
        rn = T.rn
        pin = hashlib.sha256(rn.IMAGE.read_bytes()).hexdigest()
        if kind == "md_addr":
            port = T.FakePort(T.scripted_uboot(md_addr_shift=4)); ub = rn.UBoot(port, []); port.write(b"\r"); ub.read_until(rn.PROMPT_RE, 1.0)
            try:
                ub.md_l(T.w.PAGE_ADDR, 1); return True, "a line for another address accepted"
            except rn.TransportStop:
                return False, "refused by name"
        if kind == "crc_range":
            port = T.FakePort(T.scripted_uboot(crc_range=(0x02000000, 0x02000000))); ub = rn.UBoot(port, []); port.write(b"\r"); ub.read_until(rn.PROMPT_RE, 1.0)
            try:
                ub.crc32(0x02000000, 100); return True, "a crc for another range accepted"
            except rn.TransportStop:
                return False, "refused by name"
        if kind == "go_tail":
            port = T.FakePort(T.scripted_uboot()); ub = rn.UBoot(port, []); port.write(b"\r"); ub.read_until(rn.PROMPT_RE, 1.0); ub.go(0x02000000)
            return (False, "the first application line kept") if bytes(port.buf).startswith(b"B4Q1 IDENT") else (True, f"the application's first line lost: buf={bytes(port.buf)[:40]!r}")
        if kind in ("pin", "dram", "variant"):
            if kind == "pin":
                f = fresh() / "x.bin"; f.write_bytes(b"\x00" * 56)
                ctx, script = rn.ExecutionContext(image_sha256=pin, image_path=str(f)), T.scripted_uboot()
            elif kind == "dram":
                ctx, script = rn.ExecutionContext(image_sha256=pin, image_path=str(rn.IMAGE), board_models=("Ebang EBAZ4205",)), T.scripted_uboot(model=b"Ebang EBAZ4205 (fixture)", dram=256)
            else:
                ctx, script = rn.ExecutionContext(image_sha256=pin, image_path=str(rn.IMAGE)), T.scripted_uboot(variant=0x42340002)
            port = T.FakePort(script)
            s = rn.run("fake", fresh() / "run", rn.body_control_plane, context=ctx, port=port)
            if (s.get("stop") or {}).get("kind") == "AdmissionStop" and b"loady" not in port.tx_log:
                return False, "refused before any load"
            return True, f"proceeded: stop={s.get('stop')} loady_sent={b'loady' in port.tx_log}"
        if kind == "phase_before_go":
            class P(T.FakePort):
                def write(self, data):
                    if data.startswith(b"go "):
                        self.tx_log += data
                        raise OSError(5, "Input/output error")
                    return super().write(data)
            port = P(T.scripted_uboot())
            out = fresh() / "run"
            try:
                rn.run("fake", out, rn.body_open, context=rn.ExecutionContext(image_sha256=pin, image_path=str(rn.IMAGE)), port=port)
            except OSError:
                pass
            u = json.loads((out / "uboot.json").read_text())
            if u.get("phase_at_stop") == "go-issued":
                return False, "the phase on disk says go-issued before the command left"
            return True, f"the phase on disk says {u.get('phase_at_stop')!r} although `go` is in the sent stream"
        raise RuntimeError(kind)
    probe.__doc__ = f"the runner against a scripted U-Boot: {kind}"
    return probe


def probe_loady_tail(root):
    """the ymodem's last ACK coalesced with U-Boot's tail and the prompt: the prompt reader still sees `## Total Size`"""
    T = _tests()
    rn, ym = T.rn, T.ym
    data = os.urandom(3000); state = {"n": 0, "eot": 0}

    def script(chunk):
        if chunk.startswith(b"loady"):
            return chunk + b"\r\n## Ready for binary (ymodem) download to 0x02000000 at 115200 bps...\r\nC"
        if chunk == bytes([ym.EOT]):
            state["eot"] += 1
            return bytes([ym.NAK]) if state["eot"] == 1 else bytes([ym.ACK]) + b"C"
        if chunk[:1] in (bytes([ym.STX]), bytes([ym.SOH])):
            state["n"] += 1
            if chunk[1] == 0 and state["n"] > 1:
                return bytes([ym.ACK]) + b"\r\n## Total Size = 0x00000bb8 = 3000 Bytes\r\nZynq> "
            return bytes([ym.ACK]) + (b"C" if chunk[1] == 0 else b"")
        return b""
    port = T.FakePort(script); ub = rn.UBoot(port, [])
    try:
        st = ub.loady(0x02000000, data, "x.bin", timeout=10)
    except rn.TransportStop as e:
        return True, f"the tail was lost: {e}"
    return (False, "the tail reached the prompt reader") if st.get("total") == 3000 else (True, f"total={st.get('total')}")


def probe_junk_deadline(root):
    """a receiver flooding junk (slowly): the transfer ends at its deadline (2 s), not after the retries' worth of junk (a hang observed in a subprocess)"""
    snippet = f"""import sys, os, time; sys.path[:0] = [{str(R / 'host')!r}, {str(R / 'tests')!r}]
import test_b4q_runner as T; T.setUpModule = lambda: None
import b4q_ymodem as ym
class Slow(T.FakePort):
    def fill(self, timeout):
        self.queue.append(b'q' * 50); time.sleep(0.02); return super().fill(timeout)   # junk keeps coming whether or not the sender writes
port = Slow(lambda chunk: b'')
port.queue.append(b'C')                        # the receiver asked for the header once: the transfer starts, then only junk comes
t0 = time.monotonic()
try:
    ym.send(port, os.urandom(2048), 'x.bin', timeout=2.0, retries=50)
except ym.YModemError as e:
    print('ERR', round(time.monotonic() - t0, 2), e)
"""
    try:
        p = subprocess.run([sys.executable, "-B", "-c", snippet], capture_output=True, text=True, timeout=12)
    except subprocess.TimeoutExpired:
        return True, "TIMEOUT after 12 s: the transfer did not end at its 2 s deadline (the bound removed)"
    out = p.stdout.strip()
    if out.startswith("ERR"):
        secs = float(out.split()[1])
        return (False, f"ended at {secs} s (the deadline)") if secs < 5 else (True, f"ended only after {secs} s")
    return True, f"no error raised: {out[-120:] or p.stderr[-120:]}"


MUTANTS = [
    # the evidence log (firmware)
    ("R1", RING, '''            r->last_count++;
            put16(r->base + r->used - B4Q_RING_RECORD + 6, r->last_count);
            r->compressed++;
            return;
        }
        /* a RUN''', '''            r->last_count++;
            r->compressed++;
            return;
        }
        /* a RUN''', "a compressed poll counted but the record not amended in place (the pulled log says 1 where the program polled many times)", probe_log_vs_emulation),
    ("R2", RING, "    p3_sha256_update(&c, r->base, r->used);", "    p3_sha256_update(&c, r->base, r->used > B4Q_RING_RECORD ? r->used - B4Q_RING_RECORD : 0u);", "the digest over all but the last record (the board's digest is not of the bytes it exports)", probe_ps_halts("does not hash to the board's digest")),
    ("R3", RING, "    if (r->used + B4Q_RING_RECORD > r->capacity) { r->overflow = 1; return; }", "    if (r->used + B4Q_RING_RECORD > r->capacity) { r->used = 0; r->records = 0; return; }", "a full log wraps to the start instead of stopping (silent loss)", probe_overflow_nack),
    # the application's export path (firmware)
    ("A1", APP, '        snprintf(g_json, sizeof g_json, "RING %lu %lu %d %s", (unsigned long)S.ring.used, (unsigned long)S.ring.capacity, S.ring.overflow, dhex);',
     '        snprintf(g_json, sizeof g_json, "RING %lu %lu %d %s", (unsigned long)(S.ring.used > 16u ? S.ring.used - 16u : 0u), (unsigned long)S.ring.capacity, S.ring.overflow, dhex);', "RING under-reports the log by one record (its digest still covers the whole: the host's digest check fires first)", probe_open_halts("does not hash to the board's digest")),
    ("A2", APP, '            snprintf(tail, sizeof tail, ", \\"log\\": %lu}", (unsigned long)S.ring.used);', '            snprintf(tail, sizeof tail, ", \\"log\\": %lu}", 0ul);', "the RESULT's log position always 0 (the line no longer binds to the log)", probe_ps_verify_finds("never staged", "agree")),
    ("A3", APP, '            snprintf(g_json, sizeof g_json, "CHUNK %lu %s", off, b64);', '            snprintf(g_json, sizeof g_json, "CHUNK %lu %s", 0ul, b64);', "every CHUNK claims offset 0 (the host's offset check refuses it, bounded)", probe_open_halts("too many bad chunks")),
    ("A3b", APP, "            uint32_t got = b4q_ring_read(&S.ring, (uint32_t)off, (uint32_t)n, raw);", "            uint32_t got = b4q_ring_read(&S.ring, 0u, (uint32_t)n, raw);", "PULL returns the first bytes whatever the offset (the chunk lines keep their offsets: the digest is the guard)", probe_open_halts("does not hash to the board's digest")),
    ("A4", APP, "    if (S.sum.end != B4Q_END_NONE && !S.terminal) export_epilogue();", "    (void)export_epilogue;", "no export epilogue after the END (the log of a stopped session cannot be pulled)", probe_bad_page_pulled),   # the valid scenario cannot see it (its stop swallows the failed pull); the opening's halt reason is overwritten by the open findings — the archive's source bytes are the observable
    ("A5", APP, '            if (rc == 0) { emit_text("NACK", "ended: export only"); S.sum.nacks++; }', "            if (rc == 0) { }", "a command after the END silently ignored instead of NACKed by name", probe_epilogue_nack),
    ("A6", APP, '''            if (S.ring.overflow) {                       /* the evidence log is full: nothing further is admitted (a named stop, never silent loss) */
                emit_text("NACK", "halted: the evidence log is full: nothing further is admitted"); S.sum.nacks++; S.sum.refused_tx++;
                if (!S.sum.halted) S.sum.halted = "the evidence log is full";
            } else if (S.sum.halted) {''', '''            if (S.sum.halted) {''', "a TX admitted after the log overflowed (the transaction runs unobserved)", probe_overflow_nack),
    # the adapter (host)
    ("E1", ADAPTER, '''    if len(data) % RECORD:
        raise LogRefusal(f"the log holds {len(data)} bytes: not a whole number of {RECORD}-byte records")''', '''    data = data[:len(data) - len(data) % RECORD]''', "a truncated tail silently dropped instead of refused", probe_parse_refuses),
    ("E2", ADAPTER, '''        if (count & RUN_BIT) and kind != KIND_BUF:
            raise LogRefusal(f"record at {off}: a run record outside the buffers")''', '''        pass''', "a run record outside the buffers accepted", probe_parse_refuses),
    ("E3", ADAPTER, '''            if s is not None and self.touched.get(e) == s["log_last"]:''', '''            if s is not None:''', "a staging followed by a later write into its envelope still reported as the submitted stream", probe_stale_staging),
    ("E4", ADAPTER, '''        if [x[0]["far"] for x in self.open_frames] != want[:len(self.open_frames)]:
            self.open_frames = [] if entry["far"] != want[0] else [(entry, frame)]''', '''        pass''', "eight frames in any order hashed as a link-3 group", probe_group_order),
    # the verifier's source rules (host)
    ("V1", VERIFY, '''    if [canon(e) for e in A["trace"]] != [canon(e) for e in D["trace"]]:
        F.append("trace.jsonl is not the adapter's derivation of the raw log")''', '''    pass''', "trace.jsonl no longer held to the derivation", probe_archive(_m_trace, "derivation")),
    ("V2", VERIFY, '''        if hashlib.sha256(raw).hexdigest() != source["sha256"] or len(raw) != source["bytes"]:
            raise ArchiveRefusal("raw/evidence_log.bin: not the bytes the manifest's source declares (digest / length)")''', '''        pass''', "a raw log that is not the declared bytes accepted", probe_archive(_m_raw_flip, "not the bytes the manifest's source declares", refused=True)),
    ("V3", VRUNNER, '''        if SURROGATE_MARK in rx:
            F.append("provenance: a device-format archive whose received stream carries the surrogate's banner (an emulator-only witness: a downgraded fixture, not a device)")''', '''        pass''', "a device-format archive whose stream carries the surrogate's banner no longer found (a PTY fixture passes as the device format)", probe_device_downgrade),
    ("V4", VERIFY, '''        if last["used"] != len(raw) or last["sha256"] != digest:''', '''        if False:''', "the raw log no longer held to the board's last RING", probe_archive(_m_raw_flip_declared, "last RING reported")),
    ("V5", VERIFY, '''        if e.get("i") != i or (e.get("pcap_n") is not None and e["pcap_n"] != p):
            bad += 1''', '''        pass''', "the console positions no longer held to the board's log offsets", probe_archive(_m_console_i, "position is not the board's log offset")),
    ("V6", VERIFY, '''            if not BOOT_BANNER_LINE_RE.match(e["line"]):
                m["bad"] = "noted as a boot banner but its bytes are not one"; F.append(f"board line at line {idx}: {m['bad']}")''', '''            pass''', "a line noted as a banner trusted without its bytes (R1)", probe_archive(_m_banner_bytes, "not one")),
    ("V7", VERIFY, '''                if phase == "ended" and protocol == "b4q-v2":
                    expect_nack.append("ended: export only")   # anything else after the END is refused by name, nothing runs
                else:''', '''                if False:
                    pass
                else:''', "a command after the END no longer owed its NACK (the epilogue's rule dropped)", probe_archive(_m_tx_after_end, "never answered by a NACK")),
    ("V8", VERIFY, '''    if source["records"] != len(recs) or (not source["digest_equal"] and not cut):''', '''    if False:''', "the manifest's source declaration no longer held to the raw log", probe_archive(_m_manifest(lambda mf: mf["source"].update({"records": 1})), "declares 1 records")),
    # the runner's control plane (host)
    ("N1", RUNNER, '''        if not w["equal"]:
            raise TransportStop(f"load witness: U-Boot's crc32 {dev_crc:08x} over the loaded range is not the file's {host_crc:08x}: the image in DDR is not the file (not run)")''', '''        pass''', "a load witness mismatch no longer stops before go", probe_runner("wrong_crc", expect_stop="load witness:", expect_opened=False)),
    ("N2", RUNNER, '''        if back != words:
            raise TransportStop("page witness: the page read back with md.l is not the one written with mw.l (not run)")''', '''        pass''', "a page witness mismatch no longer stops before go", probe_runner("page_witness_fails", expect_stop="page witness:", expect_opened=False)),
    ("N3", RUNNER, '''        if BANNER_LINE_RE.match(head):''', '''        if False:''', "a boot banner mid-session no longer named as the cut", probe_runner("reset_mid_session")),
    ("N4", RUNNER, '''            left = deadline - time.monotonic()
            if left <= 0:
                self._stop_transport(f"the console was silent for {self.silence_s} s while awaiting {getattr(self, '_awaiting', '?')}")''', '''            left = deadline - time.monotonic()
            if False:
                self._stop_transport(f"the console was silent for {self.silence_s} s while awaiting {getattr(self, '_awaiting', '?')}")''', "the silence bound removed (the host waits forever)", probe_runner("silence_mid_session", timeout=90)),
    # the session's pull (host)
    ("S1", SESSION, '''                self.pull_stats["bad_chunks"] += 1
                if self.pull_stats["bad_chunks"] > 8:
                    raise ss.SessionRefusal("the log could not be pulled: too many bad chunks")
                continue
            data = base64.urlsafe_b64decode(parts[2])''', '''                self.pull_stats["bad_chunks"] += 1
                continue
            data = base64.urlsafe_b64decode(parts[2])''', "the bad-chunk bound on a wrong-offset CHUNK removed (re-asked forever)", None),   # COMBINED with A3 below; the bound on an unparsable CHUNK line is a sibling guard exercised once by the runner's corrupt_chunk scenario, not mutated here
    # the runner archive contract (R1)
    ("V9", VRUNNER, '''            if image_sha != manifest["instrument"]["image_sha256"]:
                F.append("load: the transferred bytes are not the archive's executing-side image (instrument.image_sha256)")''', '''            pass''', "the transferred bytes no longer held to the executing-side image", probe_runner_archive(_m_transfer_flip, "transferred bytes are not the archive's executing-side image")),
    ("V10", VRUNNER, '''            if go_cmds or starting is not None:
                F.append("no session: the streams show `go` / the application's start — not a control-plane-only archive")''', '''            pass''', "an invented pre-go stop no longer refuted by the `go` in the streams", probe_runner_archive(_m_invented_stop, "streams show `go`")),
    ("V11", VRUNNER, '''                if (start, end) != (addr, addr + len(payload) - 1):
                    F.append(f"load: the device's crc32 is over {start:08x}..{end:08x}, not the loaded range {addr:08x}..{addr + len(payload) - 1:08x}")''', '''                pass''', "the device's crc32 no longer held to exactly the loaded range", probe_runner_archive(_m_crc_range, "not the loaded range")),
    ("V12", VRUNNER, '''            if k < 0:
                F.append(f"console linkage: board line {e.get('i')} ({e['line'][:30]}…) is not in the received stream after `go` in order"); break''', '''            if k < 0:
                break''', "a retained console line no longer held to the received stream", probe_runner_archive(_m_console_line, "console linkage")),
    # the transport (R2)
    ("P1", RUNNER, '''                out = bytes(self.port.buf[:end])
                del self.port.buf[:end]''', '''                out = bytes(self.port.buf[:end])
                del self.port.buf[:]''', "a reader consumes the whole buffer past its boundary (the next phase's first bytes lost)", probe_fake("go_tail")),
    ("P2", YMODEM, '''        if not port.buf:
            port.fill(timeout)
        if not port.buf:
            return None
        b = port.buf[0]
        del port.buf[:1]
        return b''', '''        q = getattr(port, "_ym_buf", b"")
        if not q:
            if not port.buf:
                port.fill(timeout)
            q = bytes(port.buf); del port.buf[:]
        if not q:
            return None
        port._ym_buf = q[1:]
        return q[0]''', "the ymodem keeps bytes beyond the transfer in a private queue (U-Boot's tail lost to the prompt reader)", probe_loady_tail),
    ("Y1", YMODEM, '''                clock.check(f"awaiting the ACK of {what}")''', '''                pass''', "the inner ACK loop's own deadline check removed — EXPECTED TO SURVIVE alone: the per-read clock bound (_read_byte) and the junk limit are sibling guards that still end the loop; Y1+Y2 is the kill", probe_junk_deadline),
    ("Y3", YMODEM, '''    if clock is not None:
        timeout = min(timeout, max(0.0, clock.left()))''', '''    pass''', "the per-read clock bound removed (a member of Y1+Y2+Y3 only)", None),
    ("Y2", YMODEM, '''                if junk >= junk_limit:
                    stats["retries"] += 1
                    break''', '''                pass''', "the junk limit per block removed — EXPECTED TO SURVIVE alone: the deadline (the clock on every read) still ends the transfer; Y1+Y2 is the kill", probe_junk_deadline),
    ("N5", RUNNER, '''                if a != addr + 4 * len(words):''', '''                if False:''', "md.l no longer held to the asked address", probe_fake("md_addr")),
    ("N6", RUNNER, '''        if (start, end) != (addr, addr + length - 1):''', '''        if False:''', "crc32 no longer held to the asked range", probe_fake("crc_range")),
    # the admission (R3)
    ("N7", RUNNER, '''        if not adm["image"]["equal"]:''', '''        if False:''', "a file that is not the pinned image loaded anyway", probe_fake("pin")),
    ("N8", RUNNER, '''        if not adm["board"]["dram_ok"]:''', '''        if False:''', "a board whose DRAM cannot hold the map admitted", probe_fake("dram")),
    ("N9", RUNNER, '''        if v != c.variant_word:''', '''        if False:''', "another carrier's variant word admitted", probe_fake("variant")),
    ("N10", RUNNER, '''        self._set_phase("go-issued")                                          # written before the command leaves this host
        self.runner["go"]["issued"] = True
        self.uboot.go(self.context.load_addr)''', '''        self.runner["go"]["issued"] = True
        self.uboot.go(self.context.load_addr)
        self._set_phase("go-issued")''', "the execution phase persisted only after `go` returns (a failed command leaves a pre-go record with `go` in the stream)", probe_fake("phase_before_go")),
    ("S2", SESSION, '''        elif info["overflow"]:
            self.halt("the evidence log overflowed on the board: nothing after the overflow is observed; nothing further is signed")   # named; the application NACKs the next TX too''', '''        pass''', "the host no longer halts on the board's overflow flag", probe_runner("log_overflow")),
]
def probe_open_hangs(root):
    """a PS-source opening driven in a subprocess: with the bad-chunk bound removed and a device whose every CHUNK claims offset 0, the pull never ends (a hang within 60 s is the guard's absence)"""
    snippet = f"import sys; sys.path[:0] = [{str(R / 'host')!r}, {str(R / 'b4/host')!r}]; import b4q_console_session as cs; s = cs.ConsoleSession({str(root / 'hang')!r}, source='ps-evidence-log-v1')\ntry:\n    s.open()\nexcept Exception as e:\n    pass\nprint('HALTED', s.halted, s.pull_stats); s.stop()"
    try:
        p = subprocess.run([sys.executable, "-B", "-c", snippet], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return True, "TIMEOUT after 60 s: the pull never ends (the bound removed IS the guard)"
    return False, f"the opening ended: {p.stdout.strip()[-120:] or p.stderr.strip()[-120:]}"


COMBINED = [
    ("A3+S1", [("A3", APP), ("S1", SESSION)], "every CHUNK claims offset 0 AND the host's bad-chunk bound is removed: the pull re-asks forever (the bound IS the guard; observed as a hang)", probe_open_hangs),
    ("Y1+Y2+Y3", [("Y1", YMODEM), ("Y2", YMODEM), ("Y3", YMODEM)], "the inner deadline check, the junk limit AND the per-read clock bound removed: a junk-flooding receiver holds the transfer forever (observed as a hang in a subprocess)", probe_junk_deadline),
]


def apply(path: Path, old: str, new: str) -> bool:
    t = path.read_text()
    if t.count(old) != 1:
        return False
    path.write_text(t.replace(old, new))
    return True


def build() -> str | None:
    p = subprocess.run(BUILD, capture_output=True, text=True)
    return None if p.returncode == 0 else (p.stdout[-300:] + p.stderr[-300:]).replace("\n", " | ")


def run_one(mid: str, path: Path, old: str, new: str, what: str, probe) -> dict:
    orig = path.read_bytes()
    h0 = sha(path)
    res = {"id": mid, "file": str(path.relative_to(R)), "what": what}
    try:
        if not apply(path, old, new):
            res.update({"verdict": "EDIT-MISS", "note": "the mutation text was not found exactly once"}); return res
        if path.suffix == ".c":
            err = build()
            if err:
                res.update({"verdict": "PROBE-ERROR", "note": "the mutant does not build: " + err[:200]}); return res
        root = fresh()
        t0 = time.time()
        try:
            killed, note = probe(root)
        except Exception as e:                       # the probe itself failed: never a kill
            res.update({"verdict": "PROBE-ERROR", "note": f"{type(e).__name__}: {str(e)[:600]}"}); return res
        res.update({"verdict": "KILLED" if killed else "SURVIVED", "note": note, "probe": (probe.__doc__ or "").strip().split("\n")[0], "seconds": round(time.time() - t0, 1)})
        return res
    finally:
        path.write_bytes(orig)
        assert sha(path) == h0
        if path.suffix == ".c":
            build()


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    out = None
    if "--out" in argv:
        k = argv.index("--out"); out = Path(argv[k + 1]); del argv[k:k + 2]
    ids = set(argv)
    valid_ps_archive()                                   # the base archive from the UNMUTATED tree, first
    results = []
    for mid, path, old, new, what, probe in MUTANTS:
        if ids and mid not in ids:
            continue
        if probe is None:
            continue                                     # a member of a COMBINED mutant only
        r = run_one(mid, path, old, new, what, probe)
        results.append(r)
        print(f"{mid} {r['verdict']} — {what}: {r.get('note', '')[:160]}", flush=True)
    for cid, members, what, probe in COMBINED:
        if ids and cid not in ids:
            continue
        origs = {p: p.read_bytes() for _, p in members}
        try:
            ok = all(apply(p, next(m for m in MUTANTS if m[0] == i)[2], next(m for m in MUTANTS if m[0] == i)[3]) for i, p in members)
            if not ok:
                results.append({"id": cid, "verdict": "EDIT-MISS", "what": what}); print(f"{cid} EDIT-MISS"); continue
            err = build()
            if err:
                results.append({"id": cid, "verdict": "PROBE-ERROR", "what": what, "note": err[:200]}); print(f"{cid} PROBE-ERROR"); continue
            try:
                killed, note = probe(fresh())
            except Exception as e:
                results.append({"id": cid, "verdict": "PROBE-ERROR", "what": what, "note": f"{type(e).__name__}: {str(e)[:200]}"}); print(f"{cid} PROBE-ERROR — {e}"[:200]); continue
            results.append({"id": cid, "verdict": "KILLED" if killed else "SURVIVED", "what": what, "note": note, "combined": [i for i, _ in members]})
            print(f"{cid} {'KILLED' if killed else 'SURVIVED'} — {what}: {note[:160]}", flush=True)
        finally:
            for p, b in origs.items():
                p.write_bytes(b)
            build()
    counts = {v: sum(1 for r in results if r["verdict"] == v) for v in ("KILLED", "SURVIVED", "EDIT-MISS", "PROBE-ERROR")}
    print(f"TOTAL killed {counts['KILLED']} survived {counts['SURVIVED']} edit-miss {counts['EDIT-MISS']} probe-error {counts['PROBE-ERROR']} of {len(results)}")
    if out:
        out.write_text(json.dumps({"results": results, "counts": counts, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
