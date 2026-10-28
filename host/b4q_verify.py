#!/usr/bin/env python3
"""B4Q — the FRESH-PROCESS OFFLINE VERIFIER of a session evidence directory written by host/b4q_session.py: it re-reads the
files and rebuilds everything the session claimed, holding each claim to the retained raw material —

  1. the records: O / F / X of every transaction rebuilt from trace.jsonl, the links and the declared stimulus (ctx.json) with
     host/b4carrier_records.py and compared to the stored o.json / f.json / x.json (canonical JSON equality); structure, binding
     and the chain validated (the session_open record first); the explicit schema files (b4q/schemas) applied to every record;
  2. the links: the host's view recomputed from pcap_log.jsonl (the envelope writes' frame-set digests, the read_frame groups'
     FAR-ordered digests) against links.json, and the executing side's reported digests (firmware_result.json) against the host's;
     the session_open's startup readback against the manifest's loaded-image reference; a closed X's base readback against the
     restored-base reference;
  3. A7: the executing side's accesses (accesses.jsonl) against the RTL decode and the register table (host/b4q_a7.py);
  4. the fitness: F recomputed over the full physical grid under the trusted task (ctx.json), the executing side's held to it;
  5. the view: every valid O read through the carrier adapter (host/b4q_view.py), the view validated against its schema;
  6. the manifest: its references equal the write-set record of record (firmware/b4q/b4q_data.json) and the hypothesis / mapping
     digests; the executing-side binary's digest equal to the manifest's when the binary is present.
The output is one JSON report: findings per transaction and for the session, empty for a valid path; a negative path's
outcome is NAMED (an invalid O with its fault, a missing O with the session's reason, a refused record) — never manufactured
into a clean one. Exit 0 iff the session's own findings and this verifier's agree (every finding here is also recorded there,
and vice versa) — a session that recorded no finding where this verifier finds one, or the reverse, is the failure.
Exit 1 also for a malformed archive, REFUSED by name before anything is consumed (the shapes of every file and field this verifier
indexes: load_archive / validate_record_files / validate_qualification_index — the owner's R2c). Exit 2, VERIFIER ERROR, names a
defect of this verifier itself on an archive it could not handle: never a finding about the evidence, never printed as a traceback.
Nothing here touches a board, derives a seed or writes under evidence/."""
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
import b4carrier_regmap as rm  # noqa: E402
import b4q_a7 as a7  # noqa: E402
import b4q_qual as ql  # noqa: E402
import b4q_session as ss  # noqa: E402
import b4q_frames as fr  # noqa: E402
import b4q_schema as sc  # noqa: E402
import b4q_view as vw  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4q_wire as wire  # noqa: E402


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def jl(p: Path) -> list:
    """A JSON-lines file, plain or gzip-compressed beside it (the archived evidence keeps the large access logs compressed)."""
    import gzip
    if p.is_file():
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    gz = p.with_suffix(p.suffix + ".gz")
    if gz.is_file():
        return [json.loads(l) for l in gzip.open(gz, "rt").read().splitlines() if l.strip()]
    return []


class ArchiveRefusal(ValueError):
    pass


def _int_pair(v) -> bool:
    return isinstance(v, list) and len(v) == 2 and all(type(x) is int and x >= 0 for x in v) and v[0] <= v[1]


def _is_hex(s, n: int) -> bool:
    return isinstance(s, str) and len(s) == n and all(c in "0123456789abcdef" for c in s)


def _need(cond: bool, msg: str):
    if not cond:
        raise ArchiveRefusal(msg)


def _fields(obj, where: str, spec: dict):
    """`spec`: field -> a type, a tuple of types, or None for 'present'. A missing / mistyped field is a named refusal (R2c)."""
    _need(isinstance(obj, dict), f"{where}: not an object")
    for k, typ in spec.items():
        if typ is None:
            _need(k in obj, f"{where}.{k}: missing")
        elif typ is bool:
            _need(isinstance(obj.get(k), bool), f"{where}.{k}: missing or not a bool")
        elif typ is int:
            _need(type(obj.get(k)) is int, f"{where}.{k}: missing or not an int")
        else:
            _need(isinstance(obj.get(k), typ), f"{where}.{k}: missing or not a {getattr(typ, '__name__', typ)}")


def _read_json_object(p: Path, where: str) -> dict:
    try:
        v = json.loads(p.read_text())
    except (ValueError, UnicodeDecodeError, OSError) as e:
        raise ArchiveRefusal(f"{where}: not the JSON it claims: {e}")
    _need(isinstance(v, dict), f"{where}: not a JSON object")
    return v


def _config_list(v) -> bool:
    return isinstance(v, list) and len(v) == fr.GENOME_BITS and all(type(b) is int and b in (0, 1) for b in v)


def validate_record_files(td: Path, r: dict) -> dict:
    """The per-record files' shapes (R2c): every field the verifier consumes exists with its type, before any indexing."""
    w = r["dir"]
    rj = _read_json_object(td / "record.json", f"{w}/record.json")
    _fields(rj, f"{w}/record.json", {"seq": int, "kind": str, "genome_hex": str, "findings": list, "trace_range": list, "pcap_range": list})
    _need(all(isinstance(m, str) for m in rj["findings"]), f"{w}/record.json.findings: not strings")
    _need(_is_hex(rj["genome_hex"], 6), f"{w}/record.json.genome_hex: not six hex digits")
    _need(rj.get("emulation") is None or isinstance(rj["emulation"], dict), f"{w}/record.json.emulation: not an object")
    _need(rj["seq"] == r["seq"] and rj["trace_range"] == r["trace_range"] and rj["pcap_range"] == r["pcap_range"] and rj["kind"] == r["kind"],
          f"{w}/record.json: seq / kind / ranges are not the manifest's")
    ctx = _read_json_object(td / "ctx.json", f"{w}/ctx.json")
    _fields(ctx, f"{w}/ctx.json", {"instrument": dict, "session": str, "stimulus": list, "config": list, "nonce": str, "mechanism": str, "base_readback_sha256": str,
                                   "loaded_frames_reference_sha256": str, "predecessor_close_sha256": None, "predecessor_seq": None, "task": None})
    _need(ctx["stimulus"] and all(isinstance(s, dict) for s in ctx["stimulus"]), f"{w}/ctx.json.stimulus: not a non-empty list of step objects")
    _need(_config_list(ctx["config"]), f"{w}/ctx.json.config: not the {fr.GENOME_BITS}-bit list")
    _need(ctx["task"] is None or isinstance(ctx["task"], dict), f"{w}/ctx.json.task: not an object or null")
    links = _read_json_object(td / "links.json", f"{w}/links.json")
    _fields(links, f"{w}/links.json", {"instrument": dict, "nonce": str, "config": list})
    for k in ("commit", "staging_readback_sha256", "fabric_readback_sha256_pre_event", "fabric_readback_sha256_post_event", "base_readback_sha256"):
        _need(k not in links or _is_hex(links[k], 64), f"{w}/links.json.{k}: not a sha256 hex")
    fw = _read_json_object(td / "firmware_result.json", f"{w}/firmware_result.json")
    _fields(fw, f"{w}/firmware_result.json", {"status": int, "reason": str, "phase": str})
    recs = {}
    for k in ("o", "f", "x"):
        if (td / f"{k}.json").is_file():
            recs[k] = _read_json_object(td / f"{k}.json", f"{w}/{k}.json")
    if "o" in recs:
        _fields(recs["o"], f"{w}/o.json", {"status": str, "seq": int, "config": list, "instrument": dict})   # an invalid O may lack initial / steps: the validators name that
        _need(recs["o"].get("steps") is None or isinstance(recs["o"]["steps"], list), f"{w}/o.json.steps: not a list")
        _need(recs["o"].get("initial") is None or isinstance(recs["o"]["initial"], dict), f"{w}/o.json.initial: not an object")
    if "x" in recs:
        _fields(recs["x"], f"{w}/x.json", {"status": str, "seq": int})
    return {"record": rj, "ctx": ctx, "links": links, "fw": fw, **recs}


def load_archive(d: Path) -> dict:
    """The archive's shape, validated before anything is consumed (R2c): the files, the manifest's indexed fields and ranges, the
    record directories against the declared records. A malformed archive is refused by name."""
    d = Path(d)
    if not d.is_dir():
        raise ArchiveRefusal(f"{d}: not a directory")
    for f in ("manifest.json", "trace.jsonl", "pcap_log.jsonl", "session_open.json", "notary_log.json"):
        if not (d / f).is_file():
            raise ArchiveRefusal(f"{f}: missing")
    if not (d / "accesses.jsonl").is_file() and not (d / "accesses.jsonl.gz").is_file():
        raise ArchiveRefusal("accesses.jsonl(.gz): missing")
    try:
        manifest = json.loads((d / "manifest.json").read_text())
        so_doc = json.loads((d / "session_open.json").read_text())
        notary = json.loads((d / "notary_log.json").read_text())
        trace, pcap, acc = jl(d / "trace.jsonl"), jl(d / "pcap_log.jsonl"), jl(d / "accesses.jsonl")
    except (ValueError, UnicodeDecodeError) as e:
        raise ArchiveRefusal(f"a file is not the JSON it claims: {e}")
    if not isinstance(manifest, dict) or manifest.get("schema") != "b4q_session":
        raise ArchiveRefusal("manifest.json: not a b4q_session manifest object")
    _fields(manifest, "manifest", {"label": str, "instrument": dict, "executing_side": dict, "loaded_frames_reference_sha256": str, "base_readback_reference_sha256": str,
                                   "write_set": dict, "timing": dict, "hypothesis": dict, "mapping": dict, "records": list, "chain_findings": list, "accesses": int, "trace_events": int,
                                   "open_trace_range": list, "open_pcap_range": list, "qualification_plan": dict, "emulated": bool, "halted": None, "backend": None})
    # the nested objects the verifier consumes (R2c): each indexed field present with its type, before any `.get` chain or arithmetic
    _fields(manifest["executing_side"], "manifest.executing_side", {"binary": str, "sha256": str})
    _fields(manifest["instrument"], "manifest.instrument", {"variant": str, "carrier_sha256": str, "image_sha256": str})
    _fields(manifest["hypothesis"], "manifest.hypothesis", {"sha256": str})
    _fields(manifest["mapping"], "manifest.mapping", {"certificate_sha256": str})
    _fields(manifest["qualification_plan"], "manifest.qualification_plan", {"a5": list, "a8": list, "a2": list})
    _need(manifest["halted"] is None or isinstance(manifest["halted"], str), "manifest.halted: not a string or null")
    _need(manifest["backend"] is None or isinstance(manifest["backend"], dict), "manifest.backend: not an object or null")
    _need(all(isinstance(m, str) for m in manifest["chain_findings"]), "manifest.chain_findings: not strings")
    _need(_is_hex(manifest["loaded_frames_reference_sha256"], 64) and _is_hex(manifest["base_readback_reference_sha256"], 64), "manifest: a reference is not a sha256 hex")
    validate_qualification_index(manifest["qualification_plan"])
    if not isinstance(so_doc, dict) or not isinstance(so_doc.get("record"), dict) or not isinstance(so_doc.get("findings"), list):
        raise ArchiveRefusal("session_open.json: not {record, findings, ...}")
    _fields(so_doc["record"], "session_open.record", {"status": str, "instrument": dict, "base_frames_reference_sha256": str, "startup_readback_sha256": str})
    _need(isinstance(so_doc.get("executing_side"), dict), "session_open.executing_side: missing or not an object")
    _fields(so_doc["executing_side"], "session_open.executing_side", {"status": int})
    _need(all(isinstance(m, str) for m in so_doc["findings"]), "session_open.findings: not strings")
    if not isinstance(notary, list) or not all(isinstance(e, dict) for e in notary):
        raise ArchiveRefusal("notary_log.json: not a list of objects")
    if not all(isinstance(e, dict) for e in trace + pcap + acc):
        raise ArchiveRefusal("a JSON-lines file holds a non-object line")
    _need(all(isinstance(e.get("pcap"), str) for e in pcap), "pcap_log.jsonl: an entry without its kind")
    _need(all(type(e.get("addr")) is int and e.get("op") in ("rd", "wr") and type(e.get("resp")) is int for e in acc), "accesses.jsonl: an entry without op / addr / resp")
    recs = manifest["records"]
    for i, r in enumerate(recs):
        if not isinstance(r, dict) or type(r.get("seq")) is not int or not isinstance(r.get("dir"), str) or not _int_pair(r.get("trace_range")) or not _int_pair(r.get("pcap_range")) \
                or not isinstance(r.get("findings"), list) or r.get("kind") not in ("root", "normal", "inject", "a5"):
            raise ArchiveRefusal(f"manifest.records[{i}]: not a record entry (seq, dir, kind, trace_range, pcap_range, findings)")
        if r["seq"] != i + 1 or r["dir"] != f"tx_{i + 1:03d}":
            raise ArchiveRefusal(f"manifest.records[{i}]: seq / dir out of order ({r['seq']}, {r['dir']})")
    if not _int_pair(manifest["open_trace_range"]) or manifest["open_trace_range"][0] != 0:
        raise ArchiveRefusal("manifest.open_trace_range: not an int pair from 0")
    if not _int_pair(manifest["open_pcap_range"]) or manifest["open_pcap_range"][0] != 0:
        raise ArchiveRefusal("manifest.open_pcap_range: not an int pair from 0")
    for r in recs:
        _need(r["trace_range"][1] <= len(trace) and r["pcap_range"][1] <= len(pcap), f"{r['dir']}: a declared range lies outside the retained log")
    files = {}
    for r in recs:
        td = d / r["dir"]
        if not td.is_dir():
            raise ArchiveRefusal(f"{r['dir']}: declared in the manifest, not present")
        for f in ("record.json", "ctx.json", "links.json", "firmware_result.json"):
            if not (td / f).is_file():
                raise ArchiveRefusal(f"{r['dir']}/{f}: missing")
        files[r["dir"]] = validate_record_files(td, r)
    extra = sorted(p.name for p in d.iterdir() if p.is_dir() and p.name.startswith("tx_") and p.name not in {r["dir"] for r in recs})
    if extra:
        raise ArchiveRefusal(f"record directories not declared in the manifest: {extra}")
    console = None
    tr = manifest.get("transport")
    # C1: the SOURCE is anchored in the raw evidence, never in the optional material under test — a program that read the identity
    # page (the board application does, the host-only program never) or that is the console harness produced a console archive, and
    # a console archive without its transport / console log is a downgraded source: refused by name
    page_reads = sum(1 for e in acc if e["op"] == "rd" and a7.PAGE_ADDR <= e["addr"] < a7.PAGE_ADDR + a7.PAGE_BYTES)
    console_expected = page_reads > 0 or Path(manifest["executing_side"]["binary"]).name == "b4q_apphost"
    if console_expected and (tr is None or not (d / "console.jsonl").is_file()):
        raise ArchiveRefusal(f"a console source without its console evidence: the program read the identity page {page_reads} time(s) / the executing side is "
                             f"{Path(manifest['executing_side']['binary']).name}, but manifest.transport {'is absent' if tr is None else 'is present'} and console.jsonl "
                             f"{'is present' if (d / 'console.jsonl').is_file() else 'is absent'} (a downgraded source is never verified as a host-only archive)")
    if tr is not None or (d / "console.jsonl").is_file():
        # the console source (R4): its retained material is evidence to verify, never a cached summary to trust
        _need(isinstance(tr, dict), "manifest.transport: missing or not an object while console material is present")
        _fields(tr, "manifest.transport", {"kind": str, "protocol": str, "token": str, "page_words": list, "page_flags": int, "knobs": dict, "stats": dict, "console_lines": int, "findings": list,
                                           "ident": None, "end": None})
        _need(tr["kind"] == "console-emulated", f"manifest.transport.kind: {tr['kind']!r} is not a transport this verifier knows")
        _need(_is_hex(tr["token"], wire.TOKEN_HEX), "manifest.transport.token: not 32 hex")
        _need(len(tr["page_words"]) == wire.PAGE_WORDS and all(_is_hex(w, 8) for w in tr["page_words"]), "manifest.transport.page_words: not 24 hex words")
        _need(tr["ident"] is None or isinstance(tr["ident"], dict), "manifest.transport.ident: not an object or null")
        _need(tr["end"] is None or isinstance(tr["end"], dict), "manifest.transport.end: not an object or null")
        _need(all(isinstance(m, str) for m in tr["findings"]), "manifest.transport.findings: not strings")
        _need((d / "console.jsonl").is_file(), "console.jsonl: missing (the console source's retained lines are the evidence of its framing, identity and results)")
        console = jl(d / "console.jsonl")
        for i, e in enumerate(console):
            _need(isinstance(e, dict) and e.get("dir") in ("host", "board") and (e.get("line") is None or isinstance(e["line"], str)) and type(e.get("i")) is int,
                  f"console.jsonl[{i}]: not a console entry (dir, line, i)")
            _need(e.get("note") is None or isinstance(e["note"], str), f"console.jsonl[{i}].note: not a string")
    return {"manifest": manifest, "so_doc": so_doc, "notary": notary, "trace": trace, "pcap": pcap, "acc": acc, "files": files, "console": console}


def validate_qualification_index(plan: dict):
    """The qualification index's SHAPE (R3, with R2c's discipline): typed roles, the accepted keys, int references — a malformed
    index is a named refusal; its BINDING to the records is verify_qualification's findings."""
    for i, e in enumerate(plan["a5"]):
        _fields(e, f"qualification_plan.a5[{i}]", {"J1": int, "J2": int, "J3": int, "conclusion_file": str})
    for i, e in enumerate(plan["a8"]):
        w = f"qualification_plan.a8[{i}]"
        _fields(e, w, {"element": str, "elements": dict, "bits": dict, "background_hex": str, "corners": dict, "parts": dict, "conclusion_file": str})
        _need(set(e["corners"]) == {"00", "01", "10", "11"} and all(type(v) is int for v in e["corners"].values()), f"{w}.corners: not the four corners -> int")
        _need(set(e["bits"]) == {"ff_init", "ff_srval"} and all(type(v) is int for v in e["bits"].values()), f"{w}.bits: not {{ff_init, ff_srval}} -> int")
        _need(set(e["parts"]) == {"K0", "K1", "P0", "R0", "P1", "R1"} and all(type(v) is int for v in e["parts"].values()), f"{w}.parts: not the six demonstration parts -> int")
        _need(e["elements"] and all(isinstance(k, str) and type(v) is int for k, v in e["elements"].items()), f"{w}.elements: not name -> int")
        _need(_is_hex(e["background_hex"], 6), f"{w}.background_hex: not six hex digits")
    for i, e in enumerate(plan["a2"]):
        w = f"qualification_plan.a2[{i}]"
        _fields(e, w, {"semantic": str, "g0_hex": str, "g1_hex": str, "g0": int, "g1": None, "conclusion_file": str})
        _need(e["g1"] is None or type(e["g1"]) is int, f"{w}.g1: not an int or null")
        _need(_is_hex(e["g0_hex"], 6) and _is_hex(e["g1_hex"], 6), f"{w}: an endpoint genome is not six hex digits")


def verify(d: Path, repo_root: Path = R) -> dict:
    d = Path(d)
    rep = {"dir": str(d), "session": [], "transactions": [], "a7": None, "agree": None, "refused": None}
    S = rep["session"]
    try:
        A = load_archive(d)
    except ArchiveRefusal as e:
        rep.update({"refused": str(e), "clean": False, "agree": False, "chain": [], "a7": {"findings": [f"not run: {e}"]}})
        return rep
    manifest, so_doc, trace, pcap, acc = A["manifest"], A["so_doc"], A["trace"], A["pcap"], A["acc"]
    # 6. the manifest's references
    data_rec = json.loads((repo_root / "firmware/b4q/b4q_data.json").read_text())
    if manifest.get("write_set") != data_rec:
        S.append("manifest: the write-set record is not the one of record (firmware/b4q/b4q_data.json)")
    if manifest.get("loaded_frames_reference_sha256") != data_rec["loaded_image_target_frames_sha256"]:
        S.append("manifest: the loaded-image frame reference is not the write-set record's")
    hyp, mp = hy.load(), bm.site_mapping()
    if manifest.get("hypothesis", {}).get("sha256") != hyp.sha256 or manifest.get("mapping", {}).get("certificate_sha256") != mp.certificate_sha256:
        S.append("manifest: the hypothesis / certificate digests are not the repository's")
    if not manifest.get("emulated"):
        S.append("manifest: not labelled emulated")
    binary = repo_root / manifest["executing_side"]["binary"]
    if binary.is_file() and hashlib.sha256(binary.read_bytes()).hexdigest() != manifest["executing_side"]["sha256"]:
        S.append("manifest: the executing-side binary present on disk is not the one the session ran (a rebuild since; the record binds the session's)")
    instrument = manifest["instrument"]
    # R2a: completeness — the declared records tile the raw evidence after the opening, in order, without a gap, an overlap or an
    # unconsumed suffix; the file counts are the manifest's; the trace's transaction marks are the declared transactions
    recs = manifest["records"]
    if manifest["trace_events"] != len(trace) or manifest["accesses"] != len(acc):
        S.append(f"completeness: the manifest declares {manifest['trace_events']} trace events / {manifest['accesses']} accesses, the files hold {len(trace)} / {len(acc)}")
    lo0, po0 = manifest["open_trace_range"][1], manifest["open_pcap_range"][1]
    # the opening owns exactly its prefix: the startup readback (read commands / frames / cleanups and their submissions) and nothing of
    # a transaction (no stream, no envelope); its end is where the first record begins (or the log's end when no record was signed)
    if (recs and po0 != recs[0]["pcap_range"][0]) or (not recs and po0 != len(pcap)):
        S.append(f"completeness: the opening's PCAP range [0, {po0}) does not end where the first record begins")
    if recs and lo0 != recs[0]["trace_range"][0]:
        S.append(f"completeness: the opening's trace range [0, {lo0}) does not end where the first record begins")
    opening_kinds = {e["pcap"] for e in pcap[:po0]}
    if opening_kinds - {"submit", "read_command", "read_frame", "cleanup", "frame_corrupted_by_the_bench"}:
        S.append(f"completeness: the opening's PCAP prefix holds transaction events {sorted(opening_kinds - {'submit', 'read_command', 'read_frame', 'cleanup', 'frame_corrupted_by_the_bench'})}")
    if sum(1 for e in pcap[:po0] if e["pcap"] == "read_frame") > len(fr.TARGET_FARS):
        S.append("completeness: the opening's PCAP prefix holds more than one readback group")
    cursor_t, cursor_p = lo0, po0
    for r in recs:
        if r["trace_range"][0] != cursor_t:
            S.append(f"completeness: {r['dir']} does not start where the previous record ended in the trace ({r['trace_range'][0]} vs {cursor_t})")
        if r["pcap_range"][0] != cursor_p:                                 # exact tiling: neither an overlap nor a gap (R2a: an unowned interval is never clean)
            S.append(f"completeness: {r['dir']} does not start where the previous record ended in the PCAP log ({r['pcap_range'][0]} vs {cursor_p}): an interval is unowned or shared")
        cursor_t, cursor_p = r["trace_range"][1], r["pcap_range"][1]
    tail = [e for e in trace[cursor_t:] if "op" in e or "mark" in e]
    if tail:
        S.append(f"completeness: {len(tail)} trace event(s) after the last declared record are not covered by any record (an unindexed suffix)")
    if cursor_p < len(pcap):
        S.append(f"completeness: {len(pcap) - cursor_p} PCAP event(s) after the last declared record are not covered by any record")
    if not recs and any("op" in e for e in trace[lo0:]):
        S.append("completeness: trace events after the opening with no declared record")
    marks = [e for e in trace if e.get("mark") == "transaction_begin"]
    if len(marks) != len(recs):
        S.append(f"completeness: the trace holds {len(marks)} transaction marks, the manifest declares {len(recs)} records")
    # 1. the session_open record
    so = so_doc["record"]
    f = rec.validate_session_open(so) + sc.validate_named(so, "ff_session_open_v1")
    S += [f"session_open: {m}" for m in f]
    if so["instrument"] != instrument:
        S.append("session_open: the instrument is not the manifest's")
    if so["base_frames_reference_sha256"] != manifest["loaded_frames_reference_sha256"]:
        S.append("session_open: the reference is not the manifest's loaded-image reference")
    # the host's view of the startup readback: the first read_frame group of the PCAP log (before any record's range)
    reads = [e for e in pcap[:recs[0]["pcap_range"][0]] if e.get("pcap") == "read_frame"] if recs else [e for e in pcap if e.get("pcap") == "read_frame"]
    if len(reads) >= len(fr.TARGET_FARS):
        g = reads[:len(fr.TARGET_FARS)]
        if len({x["target_frames_hash"] for x in g}) != 1 or g[0]["target_frames_hash"] != so["startup_readback_sha256"]:
            S.append(ss.STARTUP_MISMATCH)
    else:
        S.append("session_open: no startup readback group in the PCAP log before the first record")
    if so_doc["executing_side"]["status"] != 0:                            # the executing side's own refusal, as the session records it
        S.append(f"session_open: the executing side refused to open: {so_doc['executing_side'].get('reason')}")
    if so["status"] != "open" and not so_doc.get("findings"):
        S.append("session_open: refused, and the session recorded no finding")
    # the stored session findings
    stored_session_findings = list(so_doc.get("findings", []))
    # 1./2./4./5. every transaction
    tx_dirs = [d / r["dir"] for r in recs]
    chain_entries = []
    prev_x = None
    for i, td in enumerate(tx_dirs):
        T = {"dir": td.name, "findings": [], "stored_findings": [], "outcome": None}
        rep["transactions"].append(T)
        F = T["findings"]
        FL = A["files"][td.name]
        record, ctx, links, fw = FL["record"], FL["ctx"], FL["links"], FL["fw"]
        T["stored_findings"] = list(record.get("findings", []))
        T["executing_side"] = {"status": fw.get("status"), "phase": fw.get("phase"), "reason": fw.get("reason")}
        lo, hi = record["trace_range"]
        evs_all = trace[lo:hi]
        tx_evs = rec.transactions(evs_all)
        evs = tx_evs[0] if tx_evs else [e for e in evs_all if "op" in e]
        plo, phi = record["pcap_range"]
        pl = pcap[plo:phi]
        # 2. the host's view of the links, recomputed from the PCAP log
        subs = [e for e in pl if e.get("pcap") == "stream_submitted"]
        rds = [e for e in pl if e.get("pcap") == "read_frame"]
        groups = [rds[k:k + len(fr.TARGET_FARS)] for k in range(0, len(rds), len(fr.TARGET_FARS))]
        gh = [g[0]["target_frames_hash"] if len(g) == len(fr.TARGET_FARS) and len({x["target_frames_hash"] for x in g}) == 1 else None for g in groups]
        # the staging witness: the pre-write commitment recomputed from the RETAINED submitted stream bytes (R2b), apart from the
        # post-write readbacks; the executing side's stream / staged / base_staged digests held to the same bytes
        cand_staged = ss.staging_witness(subs[0:2]) if len(subs) >= 2 else None
        want = {"staging_readback_sha256": cand_staged, "fabric_readback_sha256_pre_event": gh[0] if len(gh) > 0 else None,
                "fabric_readback_sha256_post_event": gh[1] if len(gh) > 1 else None, "base_readback_sha256": gh[2] if len(gh) > 2 else None}
        for e in subs:
            if fr.words_sha256([int(e["stream_words_hex"][8 * i:8 * i + 8], 16) for i in range(len(e["stream_words_hex"]) // 8)]) != e["stream_sha256"]:
                F.append("links: a retained submitted stream does not hash to its recorded digest")
        for k, v in want.items():
            if (links.get(k) or None) != v:
                F.append(f"links.{k}: not the host's view recomputed from the PCAP log")
        if "commit" in links:
            notary = json.loads((d / "notary_log.json").read_text())
            if links["commit"] not in {e.get("commit") for e in notary}:
                F.append("links.commit: not a commit the notary signed")
        for name, mine, theirs in (("commit", links.get("commit"), fw.get("commit")), ("staged", links.get("staging_readback_sha256"), fw.get("staged")),
                                   ("stream", ss.stream_words_sha256(subs[0:2]), fw.get("stream")), ("base_staged", ss.staging_witness(subs[2:4]) if len(subs) >= 4 else None, fw.get("base_staged")),
                                   ("pre_event", links.get("fabric_readback_sha256_pre_event"), fw.get("pre_event")), ("post_event", links.get("fabric_readback_sha256_post_event"), fw.get("post_event")),
                                   ("base_readback", links.get("base_readback_sha256"), fw.get("base_readback"))):
            if theirs and mine and theirs != mine:
                F.append(f"link: the executing side's {name} digest is not the host's view")
        # 1. the records rebuilt
        pred = {"kind": "session_root", "seq": None, "close_sha256": None} if prev_x is None and i == 0 else \
            ({"kind": ("a5_injection" if prev_x["status"] == "injection_open" else "closed"), "seq": prev_x["seq"], "close_sha256": rec.sha256_json(prev_x)} if prev_x else {"kind": "session_root", "seq": None, "close_sha256": None})
        o_stored, f_stored, x_stored = FL.get("o"), FL.get("f"), FL.get("x")
        o = f_ = x = None
        try:
            o = rec.observation(evs, links, manifest["timing"], seq=record["seq"], session=manifest["label"], predecessor=pred, declared_stimulus=ctx["stimulus"])
        except rec.RecordRefusal as e:
            if o_stored is not None:
                F.append(f"O: stored but not rebuildable from the trace: {e}")
            T["outcome"] = f"no observation sealed: {e}"
            F.append(f"no observation sealed: {e}")                      # the named outcome, recorded as the session records it
        if o is not None:
            if o_stored is None or canon(o) != canon(o_stored):
                F.append("O: the stored record is not the one rebuilt from the trace and the links")
            of = rec.validate_observation(o)
            sf = sc.validate_named(o, "ff_observation_carrier_v1")
            if bool(of) != bool(sf):
                F.append(f"O: the schema file and the code validator disagree ({len(sf)} vs {len(of)} findings)")
            F += [f"O: {m}" for m in of]
            T["outcome"] = f"O {o['status']}" + (f" at {o['fault']['phase_reached']} ({o['fault']['code']})" if o["status"] == "invalid" else "")
            task = ctx.get("task")
            if not of and o["status"] == "complete" and task and record["kind"] != "root":
                f_ = rec.fitness(o, task)
                if f_stored is None or canon(f_) != canon(f_stored):
                    F.append("F: the stored fitness record is not the one recomputed over the full physical grid")
                if sc.validate_named(f_, "ff_fitness_v1"):
                    F.append("F: not an instance of the schema")
                if fw.get("has_fitness") and fw.get("fitness") != f_["fitness"]:
                    F.append(f"F: the executing side's fitness {fw.get('fitness')} is not the host's recomputation {f_['fitness']} over the full physical grid")
            elif f_stored is not None:
                F.append("F: stored for a record that has no fitness")
            try:
                x = rec.transaction_close(evs, o, seq=record["seq"], links=links)
            except rec.RecordRefusal as e:
                if x_stored is not None:
                    F.append(f"X: stored but not rebuildable: {e}")
                T["outcome"] += f"; no X ({e})"
                F.append(f"no transaction close: {e}")
            if x is not None:
                if x_stored is None or canon(x) != canon(x_stored):
                    F.append("X: the stored close is not the one rebuilt from the trace")
                xf = rec.validate_close(x, o); xs = sc.validate_named(x, "ff_transaction_close_v1")
                if bool(xf) != bool(xs):
                    F.append("X: the schema file and the code validator disagree")
                if not of:
                    F += [f"X: {m}" for m in xf]                     # as the session records it: X is judged only beside a structurally valid O
                else:
                    T["x_findings_beside_refused_o"] = xf
                T["outcome"] += f"; X {x['status']}"
                if x["status"] == "closed" and x["base_readback_sha256"] != manifest["base_readback_reference_sha256"]:
                    F.append("X: the base readback is not the restored-base reference (signed genome 0)")
            if not of:
                F += [f"bound: {m}" for m in rec.validate_bound(o, {**ctx, "predecessor_close_sha256": pred["close_sha256"], "predecessor_seq": pred["seq"]}, f_, x)]
                # 5. the view (a reading aid beside the validators; its own findings are reported apart, never counted against the session)
                try:
                    v = vw.view(o, {"representation": "C-O", "instrument": instrument})
                    T["view_findings"] = sc.validate_named(v, "ff_observation_view_v1")
                except vw.ViewRefusal as e:
                    T["view_findings"] = [str(e)]
            chain_entries.append({"o": o, "x": x, "ctx": ctx, "f": f_})       # every sealed O enters the chain, valid or not (the chain names the malformed one)
            if x is not None and x["status"] in ("closed", "injection_open"):
                prev_x = x
            elif x is not None:
                prev_x = None
        else:
            if fw.get("status") in (0,):
                F.append("the executing side reports a closed transaction but no observation was sealed")
        if fw.get("status") == 0 and not (o is not None and o["status"] == "complete" and x is not None and x["status"] in ("closed", "injection_open")):
            F.append("the executing side reports success but the records do not show a sealed complete O with a closed / injection_open X")
        if fw.get("status") in (1, 2, 3, 4, 5) and o is not None and x is not None and x["status"] == "closed" and o["status"] == "complete":
            F.append(f"the executing side reports a stop ({fw.get('reason')}) but the records show a closed transaction")
        T["unmodelled_reads"] = record.get("emulation", {}).get("unmodelled_cells")
        T["halt_expected"] = (o is None) or (x is None or x["status"] not in ("closed", "injection_open"))
    # R1 on the archive: after the first record that must halt (no O, or no closed / injection_open X), no later transaction may exist
    for i, T in enumerate(rep["transactions"]):
        if T.get("halt_expected") and i + 1 < len(rep["transactions"]):
            S.append(f"fail-closed: {T['dir']} required a halt but {rep['transactions'][i + 1]['dir']} was signed and run after it")
            break
    if so["status"] != "open" and rep["transactions"]:
        S.append("fail-closed: the session did not open but a transaction was signed and run")
    # R3: the qualification conclusions recomputed from the retained records against the retained conclusion files
    rep["qualification"] = verify_qualification(d, manifest, rep["transactions"], tx_dirs, mp, A["files"])
    S += [f"qualification: {m}" for m in rep["qualification"]["findings"]]
    # R4: the console source — its retained lines re-parsed and bound to the page, the opening, the records and the notary
    if A.get("console") is not None:
        rep["console"] = verify_console(A["console"], manifest, so_doc, A["files"], A["notary"], tx_dirs, trace)
        if rep["console"]["findings"] != list(manifest["transport"]["findings"]):
            S += [f"console: {m}" for m in rep["console"]["findings"] if m not in manifest["transport"]["findings"]]
            S += [f"console: the session recorded a console finding this verifier does not: {m}" for m in manifest["transport"]["findings"] if m not in rep["console"]["findings"]]
    # the chain
    chain = rec.validate_chain(so, chain_entries)
    rep["chain"] = chain
    if chain != manifest.get("chain_findings"):
        S.append("chain: the session's recorded chain findings are not this verifier's")
    # 3. A7
    rep["a7"] = a7.check(acc, pcap)
    declared = (manifest.get("backend") or {}).get("fault_injections") or {}
    injected = [a for a in acc if a.get("resp") and ((a["op"] == "wr" and f"{(a['addr'] - a7.bk.AXI_BASE) & 0xFFFF:#06x}" in set(declared.get("refuse_writes", [])))
                                                     or (a["op"] == "rd" and f"{(a['addr'] - a7.bk.AXI_BASE) & 0xFFFF:#06x}" in set(declared.get("refuse_reads", []))))]
    for m in rep["a7"]["findings"]:
        if m.endswith("access(es) of the carrier window answered SLVERR") and injected and rep["a7"]["slverr"] == len(injected):
            rep["a7"].setdefault("declared_injections", []).append(f"{len(injected)} SLVERR(s) are the bench's declared refused accesses (writes {declared.get('refuse_writes')}, reads {declared.get('refuse_reads')}): a simulation")
            continue
        S.append(f"A7: {m}")
    # agreement: every finding the session recorded is found here and vice versa (per transaction)
    agree = True
    for T in rep["transactions"]:
        mine = set(T["findings"]); theirs = set(T["stored_findings"])
        T["agrees"] = mine == theirs
        if not T["agrees"]:
            agree = False
            T["only_here"], T["only_stored"] = sorted(mine - theirs), sorted(theirs - mine)
    rep["session_findings_stored"] = stored_session_findings
    # agreement at the session level: every finding here is either one the session stored on its opening, or an archive-level
    # finding (completeness, fail-closed, qualification, A7, manifest) that the session could not have stored — those are the
    # verifier's own and any of them breaks the agreement
    own = [m for m in S if m not in stored_session_findings and not m.startswith("manifest: the executing-side binary")]
    missing = [m for m in stored_session_findings if m not in S]
    rep["session_only_here"], rep["session_only_stored"] = own, missing
    rep["agree"] = agree and not own and not missing
    # the session's own halt latch must agree with the records: a record that required a halt with none declared is a finding
    if manifest.get("halted") is None and any(T.get("halt_expected") for T in rep["transactions"]):
        S.append("fail-closed: a record required a halt but the session declared none"); rep["agree"] = False
    rep["clean"] = agree and not S and all(not T["findings"] for T in rep["transactions"])
    return rep


def _rec_of(tx_dirs, seq):
    if seq is None or not (1 <= seq <= len(tx_dirs)):
        return None, None
    td = tx_dirs[seq - 1]
    o = json.loads((td / "o.json").read_text()) if (td / "o.json").is_file() else None
    x = json.loads((td / "x.json").read_text()) if (td / "x.json").is_file() else None
    return o, x


# ---------------------------------------------------------------- the console source: shapes (C3), the exchange (C2)
_INT = "int"
CONSOLE_SHAPES = {
    "IDENT": {"protocol": str, "token": str, "uboot_epoch": _INT, "app_image_sha_lo32": _INT, "carrier_sha256": str, "flags": _INT, "page_nonce_seen": str,
              "page_status_seen": _INT, "nonce_echo_equal": _INT, "watchdog": str, "open": dict},
    "IDENT.open": {"status": _INT, "reason": str, "idcode": _INT, "variant": _INT, "timing": _INT, "witness": _INT, "status_word": _INT, "heartbeat": _INT, "nonce": str, "startup_readback": str},
    "SIGNREQ": {"genome": str, "nonce": str, "req": _INT},
    "RESULT": {"status": _INT, "phase": str, "reason": str, "fault_code": _INT, "commit": str, "staged": str, "stream": str, "pre_event": str, "post_event": str, "base_staged": str,
               "base_readback": str, "n_slots": _INT, "slot_q": list, "slot_in": list, "in_live_pre": _INT, "witness_after_init": _INT, "witness_after_restore": _INT,
               "heartbeat_before": _INT, "heartbeat_after": _INT, "base_state": _INT, "status_final": _INT, "steps_applied": _INT, "has_fitness": _INT, "fitness": _INT,
               "task_digest": str, "nonce_before": str, "nonce_after": str},
    "END": {"kind": str, "reason": str, "lines": _INT, "hb": _INT, "nacks": _INT, "sign_requests": _INT, "sign_replies": _INT, "transactions": _INT, "kicks": _INT,
            "flushed": _INT, "stale_frames": _INT, "refused_tx": _INT, "watchdog_armed": _INT, "opened": _INT, "halted": str},
}


def _shape_ok(obj, spec: dict) -> str | None:
    """None when `obj` is an object with every field of `spec` of exactly its type (an int is `int`, never a bool or a float); else why."""
    if not isinstance(obj, dict):
        return "not an object"
    for k, typ in spec.items():
        if k not in obj:
            return f"{k}: missing"
        v = obj[k]
        if typ is _INT:
            if type(v) is not int:
                return f"{k}: not an int"
        elif not isinstance(v, typ):
            return f"{k}: not a {typ.__name__}"
    return None


def _decode_console(console: list, token: str | None, F: list) -> list:
    """Every console entry decoded ONCE into a message: {idx, dir, type, seq, i, note, text, obj, bad}. A noted host line (a declared
    bench fault) is kept with its note and not decoded; a board line the session noted as a refused stale frame likewise. A line that
    does not parse, or whose payload is not its type's shape, is a message with `bad` set — a finding, never an exception."""
    out = []
    for idx, e in enumerate(console):
        m = {"idx": idx, "dir": e["dir"], "note": e.get("note") or "", "i": e["i"], "line": e["line"], "type": None, "seq": None, "text": None, "obj": None, "bad": None}
        if e["line"] is None or (m["note"] and e["dir"] == "host") or m["note"].startswith("stale sequence"):
            out.append(m); continue
        try:
            f = wire.parse(e["line"] + "\n", token)
        except wire.WireError as ex:
            m["bad"] = str(ex); F.append(f"{e['dir']} line at line {idx}: {m['bad']}"); out.append(m); continue
        m["type"], m["seq"] = f["type"], f["seq"]
        try:
            m["text"] = f["payload"].decode("utf-8")
        except UnicodeDecodeError:
            m["bad"] = "payload not utf-8"; F.append(f"{e['dir']} {m['type']} at line {idx}: {m['bad']}"); out.append(m); continue
        if e["dir"] == "board":
            if m["type"] not in wire.BOARD_TYPES:
                m["bad"] = f"type {m['type']!r} is not the protocol's"
            elif m["type"] in ("IDENT", "SIGNREQ", "RESULT", "END"):
                try:
                    obj = json.loads(m["text"])
                except ValueError as ex:
                    m["bad"] = f"payload not JSON ({str(ex)[:40]})"; F.append(f"board {m['type']} at line {idx}: {m['bad']}"); out.append(m); continue
                why = _shape_ok(obj, CONSOLE_SHAPES[m["type"]])
                if why is None and m["type"] == "IDENT":
                    why = _shape_ok(obj["open"], CONSOLE_SHAPES["IDENT.open"])
                    why = f"open: {why}" if why else None
                if why is None and m["type"] == "SIGNREQ" and not (_is_hex(obj["genome"], 8) and _is_hex(obj["nonce"], 16)):
                    why = "genome / nonce not hex8 / hex16"
                if why:
                    m["bad"] = f"payload: {why}"
                else:
                    m["obj"] = obj
            elif m["type"] == "HB" and m["text"] != "":
                m["bad"] = "a heartbeat with a payload"
        else:
            if m["type"] not in wire.HOST_TYPES:
                m["bad"] = f"type {m['type']!r} is not the protocol's"
            elif m["type"] == "SIGNREPLY":
                parts = m["text"].split(" ")
                if len(parts) >= 2 and parts[0] in ("OK", "REFUSED") and parts[1].isdigit() and len(parts[1]) <= 10 and int(parts[1]) <= 0xFFFFFFFF:
                    if parts[0] == "OK":
                        words = [w for w in parts[2:] if w != ""]
                        if len(words) == 24 and all(_is_hex(w, 8) for w in words) and parts[2:] == words:
                            m["obj"] = {"ok": True, "req": int(parts[1]), "words": words}
                        else:
                            m["bad"] = "payload: an OK reply without exactly 24 hex words"
                    else:
                        m["obj"] = {"ok": False, "req": int(parts[1]), "why": " ".join(parts[2:])}
                else:
                    m["bad"] = "payload: neither 'OK <req> <words>' nor 'REFUSED <req> <why>'"
            elif m["type"] == "QUIT" and m["text"] != "":
                m["bad"] = "a QUIT with a payload"
            elif m["type"] == "TX":
                m["obj"] = {"tx": wire.parse_tx(m["text"])}               # None when the grammar refuses: then a NACK malformed TX is the expected answer
        if m["bad"]:
            F.append(f"{e['dir']} {m['type'] or 'line'} at line {idx}: {m['bad']}")
        out.append(m)
    return out


def _nonce_from_trace(trace: list, before: int) -> str | None:
    """The PL nonce as the executing side last read it before trace position `before`: the last NONCE_LO and NONCE_HI reads."""
    lo = hi = None
    for e in reversed(trace[:before]):
        if e.get("op") == "rd" and e.get("addr") == rm.NONCE_LO and lo is None:
            lo = e.get("data")
        elif e.get("op") == "rd" and e.get("addr") == rm.NONCE_HI and hi is None:
            hi = e.get("data")
        if lo is not None and hi is not None:
            break
    return f"{(hi << 32) | lo:016x}" if lo is not None and hi is not None else None


def _staged_words_from_trace(trace: list, lo_i: int, hi_i: int) -> list | None:
    """The 20 PAYLOAD and 4 TAG words the executing side wrote between trace positions lo_i and hi_i (the first complete staging)."""
    words = {}
    for k, e in enumerate(trace[lo_i:hi_i], lo_i):
        if e.get("op") == "wr" and e.get("addr") in rm.PAYLOAD and e.get("resp", 0) == 0:
            words[("p", rm.PAYLOAD.index(e["addr"]))] = e["data"]
        elif e.get("op") == "wr" and e.get("addr") in rm.TAG and e.get("resp", 0) == 0:
            words[("t", rm.TAG.index(e["addr"]))] = e["data"]
            if all(("p", j) in words for j in range(20)) and all(("t", j) in words for j in range(4)):
                return [f"{words[('p', j)]:08x}" for j in range(20)] + [f"{words[('t', j)]:08x}" for j in range(4)]
    return None


def verify_console(console: list, manifest: dict, so_doc: dict, files: dict, notary: list, tx_dirs: list, trace: list) -> dict:
    """The console source's archive contract (the owner's R4 of 2026-10-28, its C2 / C3 residuals): from the retained lines alone,
    decoded once with every message's shape checked before it is used (C3), the ORDERED protocol exchange is replayed (C2) — the
    opening (EV / HB, then the IDENT derived from the page, the executing-side image and the retained opening result), then for
    each host command: a fresh, well-formed TX on a session that may run it is ADMITTED and bound to the next retained record (its
    kind / genome / declared steps / task rebuild the exact TX text); its candidate SIGNREQ carries that record's genome and the nonce
    the executing side read from the PL just before (the trace); replies are accepted only after their request, by request id, at most
    three requests per candidate; an OK reply's 24 words are the ones the executing side then staged into PAYLOAD / TAG (the trace)
    and the ones the notary log handed out; the restore's SIGNREQ carries genome 0 and the nonce read before it; the RESULT is the
    retained transaction result and follows its own exchange; a refused command (stale / malformed / halted / unknown) is answered by
    the NACK that names it and makes no record; after a transaction that did not close nothing is admitted; the END's counters are
    recomputed from the lines and its kind held to the host's last line. The cached transport summaries (ident / end / stats) are held
    to what is derived. Internal consistency of the retained evidence, not authenticity and not a physical proof."""
    F = []
    tr = manifest["transport"]
    page = wire.parse_page([int(w, 16) for w in tr["page_words"]])
    if page is None and not tr["knobs"].get("bad_page"):
        F.append("the transport's page words do not parse")
    token = page["token"] if page else wire.ZERO_TOKEN
    if page and page["token"] != tr["token"]:
        F.append("the transport's token is not the page's")
    msgs = _decode_console(console, token, F)
    board = [m for m in msgs if m["dir"] == "board" and m["type"] and not m["bad"]]
    host = [m for m in msgs if m["dir"] == "host" and m["type"] and not m["bad"]]
    # freshness per direction, the noted lines counted against the declared knobs
    noted = {"corrupted": 0, "garbage": 0, "wrong_token": 0, "stale": 0, "dropped": 0, "stale_board": 0, "replayed": 0, "other": 0}
    last_b = last_h = None
    for m in msgs:
        note = m["note"]
        if m["line"] is None:
            noted["dropped" if "unanswered" in note else "other"] += 1; continue
        if m["dir"] == "board":
            if note.startswith("stale sequence"):
                try:
                    f = wire.parse(m["line"] + "\n", token)
                    if last_b is None or f["seq"] > last_b:
                        F.append(f"board line {m['idx']}: noted as stale but its sequence {f['seq']} is fresh")
                except wire.WireError:
                    F.append(f"board line {m['idx']}: noted as stale but does not parse")
                noted["stale_board"] += 1; continue
            if m["seq"] is None:
                continue
            if last_b is not None and m["seq"] <= last_b:
                F.append(f"board line {m['idx']}: sequence {m['seq']} after {last_b}: not fresh, and the session did not refuse it")
            last_b = m["seq"] if last_b is None else max(last_b, m["seq"])
        else:
            if note:
                key = ("corrupted" if "corrupted" in note else "garbage" if "malformed" in note else "wrong_token" if "another session's token" in note else "stale" if "stale SIGNREPLY" in note
                       else "replayed" if "replayed" in note else "other")
                noted[key] += 1
                if key == "other":
                    F.append(f"host line {m['idx']}: a noted line this verifier does not classify: {note[:60]}")
                if key == "replayed":
                    try:
                        rf = wire.parse(m["line"] + "\n", tr["token"])
                        if last_h is None or rf["seq"] > last_h:
                            F.append(f"host line {m['idx']}: noted as replayed but its sequence is fresh")
                    except wire.WireError:
                        F.append(f"host line {m['idx']}: noted as replayed but does not parse")
                continue
            if m["seq"] is None:
                continue
            if last_h is not None and m["seq"] <= last_h:
                F.append(f"host line {m['idx']}: sequence {m['seq']} after {last_h}: not fresh")
            last_h = m["seq"] if last_h is None else max(last_h, m["seq"])
    for key, want in (("corrupted", tr["stats"].get("corrupted")), ("garbage", tr["stats"].get("garbage")), ("wrong_token", tr["stats"].get("wrong_token")), ("stale", tr["stats"].get("stale")),
                      ("dropped", tr["stats"].get("dropped")), ("stale_board", tr["stats"].get("stale_board")), ("replayed", tr["stats"].get("replayed"))):
        if want is not None and noted[key] != want:
            F.append(f"the noted {key} lines ({noted[key]}) are not the declared knob count ({want})")
    es = so_doc.get("executing_side") or {}
    recs = [files[td.name] for td in tx_dirs]
    signed = {}
    for e in notary:
        if "words" in e and isinstance(e["words"], list) and len(e["words"]) == 24 and all(type(w) is int for w in e["words"]):
            signed[(f"{int(e['genome_hex'], 16):08x}" if e.get("genome_hex") else f"{e.get('genome', 0):08x}", e.get("nonce") if isinstance(e.get("nonce"), str) else f"{e.get('nonce', 0):016x}")] = [f"{w:08x}" for w in e["words"]]
        elif "words" in e:
            F.append("a notary log entry carries no 24-word signature")
    refusals = {(f"{int(e['genome_hex'], 16):08x}" if e.get("genome_hex") else None, e.get("nonce")) for e in notary if "refused" in e}
    # ---- the exchange, replayed in file order
    phase = "pre_ident"                   # pre_ident | idle | admitted | quit | ended
    ident = None; ends = []; results = []; signreqs = []
    k = 0                                 # the next record an admitted TX binds to
    cur = None                            # the open transaction: {rec, k, tx_idx, reqs: [{req, genome, nonce, msgs, replies, ok_words, stage}], stage}
    halted = None                         # the first failing RESULT's reason (the latch on the lines)
    expect_nack = []                      # reasons the board must NACK next, in order (declared bench faults, refused commands)
    hb = nacks = 0
    refused_cmds = 0
    host_last_type = None
    nonce_first = None
    def bind_tx(m):
        """classify a well-formed, fresh TX: 'admitted' (bound to record k), or the NACK reason the board owes"""
        nonlocal k, cur
        if halted is not None:
            return "halted:"
        if m["obj"]["tx"] is None:
            return "malformed TX"
        if k >= len(recs):
            F.append(f"host TX at line {m['idx']}: admitted but there is no retained record left to bind it to"); return "unbound"
        r = recs[k]
        want = ss.tx_command(r["record"]["kind"], r["record"]["genome"], r["ctx"]["stimulus"], r["ctx"]["task"])
        if m["text"] != want:
            F.append(f"host TX at line {m['idx']}: not the command of record {tx_dirs[k].name} (its kind / genome / declared steps / task)")
        cur = {"rec": r, "k": k, "tx_idx": m["idx"], "reqs": [], "result": None}
        k += 1
        return "admitted"
    for m in msgs:
        if m["line"] is None:
            continue
        if m["dir"] == "host":
            if m["note"]:                                 # the declared bench faults the board must answer
                if "corrupted" in m["note"] or "malformed" in m["note"]:
                    expect_nack.append("bad crc")
                elif "another session's token" in m["note"]:
                    expect_nack.append("wrong token")
                elif "replayed" in m["note"]:
                    expect_nack.append("stale sequence"); refused_cmds += 1      # a replayed TX is a command the exchange refuses
                continue                                  # a stale SIGNREPLY: ignored by the application, owed nothing
            if m["bad"]:
                continue
            host_last_type = m["type"]
            if phase in ("pre_ident", "ended"):
                F.append(f"host {m['type']} at line {m['idx']}: before the IDENT / after the END")
            if m["type"] == "TX":
                if phase == "admitted":
                    F.append(f"host TX at line {m['idx']}: while transaction {cur['k'] + 1} is still open (no RESULT yet)")
                verdict = bind_tx(m)
                if verdict == "admitted":
                    phase = "admitted"
                elif verdict != "unbound":
                    expect_nack.append(verdict); refused_cmds += 1
            elif m["type"] == "QUIT":
                phase = "quit"
            elif m["type"] == "SIGNREPLY":
                o = m["obj"]
                req = next((q for q in (cur["reqs"] if cur else []) if q["req"] == o["req"]), None)
                if req is None:
                    F.append(f"host SIGNREPLY at line {m['idx']}: answers request {o['req']}, which is not an open request of the current transaction")
                    continue
                if req["answered"]:
                    F.append(f"host SIGNREPLY at line {m['idx']}: a second reply to request {o['req']}")
                    continue
                req["answered"] = o
                if o["ok"]:
                    key = (req["genome"], req["nonce"])
                    if key not in signed:
                        F.append(f"host SIGNREPLY at line {m['idx']}: OK for a candidate the notary log did not sign {key}")
                    elif signed[key] != o["words"]:
                        F.append(f"host SIGNREPLY at line {m['idx']}: its words are not the notary's for {key}")
                    req["ok_i"] = m["i"]
                else:
                    if (req["genome"], req["nonce"]) not in refusals:
                        F.append(f"host SIGNREPLY at line {m['idx']}: a refusal the notary log does not record")
            continue
        # board
        if m["bad"] or m["type"] is None:
            continue
        if phase == "ended":
            F.append(f"board {m['type']} at line {m['idx']}: after the END"); continue
        if m["type"] == "HB":
            hb += 1; continue
        if m["type"] == "EV":
            continue
        if m["type"] == "NACK":
            nacks += 1
            if expect_nack:
                want = expect_nack.pop(0)
                if not m["text"].startswith(want):
                    F.append(f"board NACK at line {m['idx']}: '{m['text'][:40]}' where '{want}' was owed")
            elif host_last_type == "SIGNREPLY" and m["text"] == "bad SIGNREPLY":
                pass
            else:
                F.append(f"board NACK at line {m['idx']}: '{m['text'][:40]}' answers nothing this host sent")
            continue
        if m["type"] == "IDENT":
            if ident is not None:
                F.append(f"board IDENT at line {m['idx']}: a second IDENT"); continue
            if phase != "pre_ident":
                F.append(f"board IDENT at line {m['idx']}: not at the opening")
            ident = m["obj"]; phase = "idle"
            o = ident
            if o["protocol"] != "b4q-v1":
                F.append(f"the IDENT's protocol {o['protocol']!r} is not b4q-v1")
            if page:
                if o["token"] != page["token"] or o["carrier_sha256"] != page["carrier_sha256"] or o["flags"] != page["flags"] or o["uboot_epoch"] != page["uboot_epoch"]:
                    F.append("the IDENT's page fields (token / carrier / flags / epoch) are not the page's")
                if o["page_nonce_seen"] != f"{page['nonce_seen']:016x}" or o["page_status_seen"] != page["status_seen"]:
                    F.append("the IDENT's page nonce / status are not the page's")
                if o["nonce_echo_equal"] != int(f"{page['nonce_seen']:016x}" == o["open"]["nonce"]):
                    F.append("the IDENT's nonce echo flag is not what the page and the opening say")
                if o["watchdog"] != ("armed" if page["flags"] & wire.PAGE_FLAG_WATCHDOG else "off"):
                    F.append("the IDENT's watchdog state is not what the page's flags ask")
            if o["app_image_sha_lo32"] != int(manifest["executing_side"]["sha256"][:8], 16):
                F.append("the IDENT's image digest echo is not the executing-side image's")
            if canon({kk: v for kk, v in es.items() if kk not in ("ident", "end")}) != canon(o["open"]):
                F.append("the IDENT's opening object is not the retained opening result")
            if canon(o) != canon(tr["ident"]):
                F.append("the transport's cached IDENT is not the one the console carried")
            continue
        if m["type"] == "SIGNREQ":
            signreqs.append(m)
            if phase != "admitted" or cur is None:
                F.append(f"board SIGNREQ at line {m['idx']}: outside an admitted transaction"); continue
            o = m["obj"]
            prev = next((q for q in cur["reqs"] if q["req"] == o["req"]), None)
            if prev is not None:                          # a re-request: the same candidate, at most three lines, none after an answer
                prev["n"] += 1
                if (o["genome"], o["nonce"]) != (prev["genome"], prev["nonce"]):
                    F.append(f"board SIGNREQ at line {m['idx']}: re-requests request {o['req']} with another candidate")
                if prev["n"] > 3:
                    F.append(f"board SIGNREQ at line {m['idx']}: request {o['req']} sent more than three times")
                if prev["answered"]:
                    F.append(f"board SIGNREQ at line {m['idx']}: request {o['req']} re-sent after it was answered")
                continue
            if o["req"] != m["seq"]:
                F.append(f"board SIGNREQ at line {m['idx']}: its request id {o['req']} is not its own sequence {m['seq']}")
            nonce_trace = _nonce_from_trace(trace, m["i"])
            if nonce_trace is not None and nonce_trace != o["nonce"]:
                F.append(f"board SIGNREQ at line {m['idx']}: its nonce {o['nonce']} is not the one the executing side read from the PL just before ({nonce_trace})")
            if len(cur["reqs"]) == 0:                     # the candidate
                r = cur["rec"]
                if o["genome"] != f"{r['record']['genome']:08x}":
                    F.append(f"board SIGNREQ at line {m['idx']}: candidate genome {o['genome']} is not record {tx_dirs[cur['k']].name}'s")
                if o["nonce"] != r["ctx"]["nonce"]:
                    F.append(f"board SIGNREQ at line {m['idx']}: candidate nonce {o['nonce']} is not the record's ctx.nonce")
            elif len(cur["reqs"]) == 1:                   # the restore (genome 0)
                if o["genome"] != "00000000":
                    F.append(f"board SIGNREQ at line {m['idx']}: the second request of a transaction is the restore's (genome 0), not {o['genome']}")
            else:
                F.append(f"board SIGNREQ at line {m['idx']}: a third distinct request in one transaction")
            cur["reqs"].append({"req": o["req"], "genome": o["genome"], "nonce": o["nonce"], "n": 1, "answered": None, "ok_i": None, "idx": m["idx"]})
            continue
        if m["type"] == "RESULT":
            results.append(m)
            if phase != "admitted" or cur is None:
                F.append(f"board RESULT at line {m['idx']}: without an admitted TX"); continue
            r = cur["rec"]
            if canon(m["obj"]) != canon(r["fw"]):
                F.append(f"board RESULT at line {m['idx']}: not the retained transaction result of {tx_dirs[cur['k']].name}")
            if cur["reqs"] and m["obj"]["nonce_before"] != cur["reqs"][0]["nonce"]:
                F.append(f"board RESULT at line {m['idx']}: its nonce_before is not the candidate request's nonce")
            # every OK reply's words were staged into PAYLOAD / TAG between the reply and this result
            for q in cur["reqs"]:
                if q["answered"] and q["answered"]["ok"]:
                    staged = _staged_words_from_trace(trace, q["ok_i"], m["i"])
                    if staged is None:
                        F.append(f"the words of request {q['req']} were never staged into PAYLOAD / TAG after the reply")
                    elif staged != q["answered"]["words"]:
                        F.append(f"the words staged into PAYLOAD / TAG after request {q['req']}'s reply are not the reply's")
            if m["obj"]["status"] == 0 and not cur["reqs"]:
                F.append(f"board RESULT at line {m['idx']}: a closed transaction without any SIGNREQ")
            if m["obj"]["status"] != 0 and halted is None:
                halted = m["obj"]["reason"]
            cur["result"] = m; phase = "idle"; cur = None
            continue
        if m["type"] == "END":
            ends.append(m)
            if phase == "admitted" and manifest.get("interrupted") is None:
                F.append(f"board END at line {m['idx']}: inside transaction {cur['k'] + 1} (no RESULT) and the session was not interrupted")
            phase = "ended"
            o = m["obj"]
            counts = {"lines": sum(1 for b in board if b["idx"] < m["idx"]) + noted["stale_board"], "hb": hb, "nacks": nacks, "sign_requests": len(signreqs), "transactions": len(results),
                      "refused_tx": sum(1 for b in board if b["type"] == "NACK" and b["text"].startswith("halted:") and b["idx"] < m["idx"]),
                      "stale_frames": sum(1 for b in board if b["type"] == "NACK" and b["text"] == "stale sequence" and b["idx"] < m["idx"])}
            for kk, v in counts.items():
                if o[kk] != v:
                    F.append(f"END.{kk} is {o[kk]}, the lines say {v}")
            if o["kicks"] != o["lines"]:
                F.append("END.kicks is not END.lines")
            if o["kind"] == "COMPLETED" and host_last_type != "QUIT":
                F.append("END COMPLETED without the host's QUIT as its last line")
            if o["kind"] != "COMPLETED" and phase == "quit":
                F.append("the host's QUIT answered by an END that is not COMPLETED")
            if o["opened"] != (1 if es.get("status") == 0 else 0):
                F.append("END.opened is not the retained opening's status")
            if page and o["watchdog_armed"] != (1 if page["flags"] & wire.PAGE_FLAG_WATCHDOG else 0) and o["kind"] != "STOPPED":
                F.append("END.watchdog_armed is not what the page asked")
            if (o["halted"] or "") != (halted or "") and not (o["halted"] and o["kind"] in ("PROTOCOL", "ABORT") and halted is None):
                F.append(f"END.halted {o['halted']!r} is not the first failing RESULT's reason {halted!r}")
            if canon(o) != canon(tr["end"]):
                F.append("the transport's cached END is not the one the console carried")
            continue
    if ident is None and not (ends and board and ends[0] is board[0]):
        F.append("no IDENT line and no END as the first board line")
    if ident is None and tr["ident"] is not None:
        F.append("the transport caches an IDENT the console never carried")
    if phase == "admitted" and manifest.get("interrupted") is None:
        F.append(f"transaction {cur['k'] + 1} admitted and never answered by a RESULT, and the session was not interrupted")
    if k != len(recs) - (1 if manifest.get("interrupted") is not None and phase == "admitted" else 0) and not (k == len(recs)):
        F.append(f"{k} TX admitted for {len(recs)} retained records")
    if k < len(recs):
        F.append(f"{len(recs) - k} retained record(s) without an admitted TX")
    if expect_nack:
        F.append(f"{len(expect_nack)} refused / faulty host line(s) never answered by a NACK")
    if not ends and manifest.get("interrupted") is None:
        F.append("no END line and the session was not interrupted")
    if len(ends) > 1:
        F.append(f"{len(ends)} END lines")
    if ends and board and ends[-1] is not board[-1]:
        F.append("the END is not the last board line")
    tr_ref = tr.get("refused_commands")
    if isinstance(tr_ref, list) and len(tr_ref) != refused_cmds:
        F.append(f"the transport's refused commands ({len(tr_ref)}) are not the commands the exchange refused ({refused_cmds})")
    if tr["console_lines"] != len(console):
        F.append(f"the transport declares {tr['console_lines']} console lines, the log holds {len(console)}")
    for kk, want in (("hb", hb), ("nack", nacks), ("signreq", len(signreqs))):
        if tr["stats"].get(kk) != want:
            F.append(f"the transport's stats.{kk} is {tr['stats'].get(kk)}, the lines say {want}")
    return {"findings": F, "board_lines": len(board), "host_lines": len(host), "noted": noted, "ident": ident is not None, "results": len(results), "signreqs": len(signreqs), "ends": len(ends), "admitted": k}


def _role(files: dict, tx_dirs: list, seq):
    """The record files of a referenced seq (None when the reference is outside the records): record / ctx / o / x."""
    if seq is None or not (1 <= seq <= len(tx_dirs)):
        return None
    return files[tx_dirs[seq - 1].name]


def _cfg(fl: dict | None):
    """The ACTUAL configuration a role's record observed: O.config (bound to the links / commit by the record validators); the declared
    ctx.config when no O was sealed (then the role's reading is not demonstrated anyway)."""
    if fl is None:
        return None
    return (fl.get("o") or {}).get("config") or fl["ctx"]["config"]


def _genome_cfg(hex6: str) -> list:
    return ss.config_list(int(hex6, 16))


def verify_qualification(d: Path, manifest: dict, transactions: list, tx_dirs: list, mp, files: dict) -> dict:
    """The qualification index declared by the session (manifest.qualification_plan: which records play which role) BOUND to the
    records it references (R3): every role's identity — the element and its index against the mapping's element order, the varied
    bit(s) against the mapping's address of (element, semantic), the corners' / endpoints' actual O.config against the declared
    labels, the common background and the common demonstration stimulus — then every conclusion recomputed with host/b4q_qual from
    the retained O / X and the retained conclusion file held to it IN FULL (the whole data-bearing content: samples, readings,
    quantities, differing points, witnesses; nothing is informational-only). A conclusion file is never trusted; a missing corner,
    close witness or malformed record is `not demonstrated` / `not assessable`, never a positive claim. A declared bystander (an
    element the cross does not vary) is a diagnostic reading: its bits are not required to vary; it is never the qualified element."""
    plan = manifest["qualification_plan"]
    out = {"findings": [], "a5": [], "a8": [], "a2": []}
    F = out["findings"]
    valid = {t["dir"]: (not t["findings"]) for t in transactions}
    def ok(seq):
        return seq is not None and 1 <= seq <= len(tx_dirs) and valid.get(tx_dirs[seq - 1].name, False)
    def stim(fl):
        return canon(fl["ctx"]["stimulus"]) if fl else None
    def findings_of(fl):
        return list(fl["record"]["findings"]) if fl else None
    def conclusion(e, what):
        p = d / e["conclusion_file"]
        if not p.is_file():
            F.append(f"{what}: the conclusion file {e['conclusion_file']} is missing"); return None
        try:
            v = json.loads(p.read_text())
        except ValueError:
            F.append(f"{what}: the conclusion file {e['conclusion_file']} is not JSON"); return None
        if not isinstance(v, dict):
            F.append(f"{what}: the conclusion file {e['conclusion_file']} is not an object"); return None
        return v
    for n, e in enumerate(plan["a5"]):
        what = f"A5[{n}]"
        R1, R2, R3 = (_role(files, tx_dirs, e[k]) for k in ("J1", "J2", "J3"))
        if len({e["J1"], e["J2"], e["J3"]}) != 3 or not (e["J2"] == e["J1"] + 1 and e["J3"] == e["J2"] + 1):
            F.append(f"{what}: the roles are not three consecutive distinct records (J1, J1+1, J1+2)")
        for name, fl, kind in (("J1", R1, "normal"), ("J2", R2, "inject"), ("J3", R3, "a5")):
            if fl is None:
                F.append(f"{what}: {name} references no record")
            elif fl["record"]["kind"] != kind:
                F.append(f"{what}: {name} is a {fl['record']['kind']} transaction, not the {kind} one of the protocol")
        if R1 and R2 and R3:
            if not (_cfg(R1) == _cfg(R2) == _cfg(R3)):
                F.append(f"{what}: J1 / J2 / J3 do not observe one configuration (the A5 protocol varies the state, never the configuration)")
            if stim(R1) != stim(R3):
                F.append(f"{what}: J1 and J3 do not declare the same stimulus")
        o1, x1 = ((R1 or {}).get("o"), (R1 or {}).get("x")); o2, x2 = ((R2 or {}).get("o"), (R2 or {}).get("x")); o3, x3 = ((R3 or {}).get("o"), (R3 or {}).get("x"))
        v = ql.a5_verdict(o1, o2, o3, x1, x3, x2) if (o1 and o2 and o3) else {"verdict": "not_demonstrated", "why": "a role's record is absent", "per_element": None}
        if not all(ok(e[k]) for k in ("J1", "J2", "J3")) and v["verdict"] == "pass":
            v = {"verdict": "not_demonstrated", "why": "a role's record carries findings: no pass is claimed on it", "per_element": None}
        stored = conclusion(e, what)
        if stored is not None and canon(stored) != canon(v):
            F.append(f"{what}: the retained conclusion ({stored.get('verdict')}) is not the one recomputed from the records ({v['verdict']}) in full")
        out["a5"].append({"recomputed": v["verdict"], "stored": stored.get("verdict") if stored else None})
    for n, e in enumerate(plan["a8"]):
        what = f"A8[{n}]"
        el = e["element"]
        if el not in bm.ELEMENTS:
            F.append(f"{what}: the qualified element {el!r} is not an element of the mapping")
        if el not in e["elements"]:
            F.append(f"{what}: the qualified element {el!r} is not among the index's elements")
        for name, idx in e["elements"].items():
            if name not in bm.ELEMENTS or idx != bm.ELEMENTS.index(name):
                F.append(f"{what}: element {name!r} / index {idx} is not the mapping's element order")
        want_bits = None
        if el in bm.ELEMENTS:
            try:
                want_bits = {s: mp.genome_bit(mp.address_of(el, s)) for s in ("ff_init", "ff_srval")}
            except KeyError:
                F.append(f"{what}: the mapping has no (element, ff_init / ff_srval) address for {el!r}")
        if want_bits is not None and e["bits"] != want_bits:
            F.append(f"{what}: the declared varied bits {e['bits']} are not the mapping's addresses of ({el}, ff_init / ff_srval) {want_bits}")
        bits = want_bits or e["bits"]
        bg = _genome_cfg(e["background_hex"])
        if bg[bits["ff_init"]] or bg[bits["ff_srval"]]:
            F.append(f"{what}: the declared background sets a varied bit")
        corners, closes, roles = {}, {}, {}
        if len(set(e["corners"].values())) != 4:
            F.append(f"{what}: the four corners do not reference four distinct records")
        for c, seq in e["corners"].items():
            fl = _role(files, tx_dirs, seq); roles[c] = fl
            corners[c] = (fl or {}).get("o"); closes[c] = (fl or {}).get("x") if ok(seq) else None
            if fl is None:
                F.append(f"{what}: corner {c} references no record"); continue
            cfg = _cfg(fl)
            if cfg[bits["ff_init"]] != int(c[0]) or cfg[bits["ff_srval"]] != int(c[1]):
                F.append(f"{what}: corner {c}'s record does not observe (INIT bit, SRVAL bit) = ({c[0]}, {c[1]}) of {el}")
            rest = [b for i, b in enumerate(cfg) if i not in (bits["ff_init"], bits["ff_srval"])]
            if rest != [b for i, b in enumerate(bg) if i not in (bits["ff_init"], bits["ff_srval"])]:
                F.append(f"{what}: corner {c}'s record does not observe the declared background outside the varied bits")
        stims = {stim(fl) for fl in roles.values() if fl}
        if len(stims) > 1:
            F.append(f"{what}: the corners do not declare one demonstration stimulus")
        nsteps = min((len(fl["ctx"]["stimulus"]) for fl in roles.values() if fl), default=0)
        if any(not (1 <= v < nsteps) for v in e["parts"].values()):
            F.append(f"{what}: a demonstration part lies outside the declared stimulus")
        stored = conclusion(e, what)
        res = {}
        for name, idx in e["elements"].items():
            res[name] = ql.a8_classify(corners, idx, e["parts"], closes=closes) if all(corners.values()) else {"row": 0, "verdict": "not demonstrated", "why": "a corner's record is absent", "quantities": {"not_assessable": True}}
        if stored is not None:
            if set(stored) != set(e["elements"]):
                F.append(f"{what}: the conclusion file's elements {sorted(stored)} are not the index's {sorted(e['elements'])}")
            for name, v in res.items():
                if canon(stored.get(name)) != canon(v):
                    F.append(f"{what} {name}: the retained conclusion (row {(stored.get(name) or {}).get('row')}) is not the one recomputed from the records (row {v['row']}) in full")
        out["a8"].append({name: {"recomputed": v["verdict"], "stored": ((stored or {}).get(name) or {}).get("verdict")} for name, v in res.items()})
    for n, e in enumerate(plan["a2"]):
        sem = e["semantic"]; what = f"A2[{n}] {sem}"
        if sem not in bm.SEMANTICS:
            F.append(f"{what}: not a semantic of the mapping")
        G0, G1 = _role(files, tx_dirs, e["g0"]), _role(files, tx_dirs, e["g1"])
        if G0 is None:
            F.append(f"{what}: g0 references no record")
        if e["g1"] is not None and G1 is None:
            F.append(f"{what}: g1 references no record")
        if e["g1"] is not None and e["g0"] == e["g1"]:
            F.append(f"{what}: the two endpoints are one record")
        c0, c1 = _genome_cfg(e["g0_hex"]), _genome_cfg(e["g1_hex"])
        if G0 is not None and _cfg(G0) != c0:
            F.append(f"{what}: g0's record does not observe the declared endpoint {e['g0_hex']}")
        if G1 is not None and _cfg(G1) != c1:
            F.append(f"{what}: g1's record does not observe the declared endpoint {e['g1_hex']}")
        diff = [mp.addresses[i] for i in range(fr.GENOME_BITS) if c0[i] != c1[i]]
        sems = {mp.entries[a].semantic for a in diff}; els = {mp.entries[a].element for a in diff}
        if not diff or sems != {sem} or len(els) != 1:
            F.append(f"{what}: the two endpoints do not differ exactly in the bit(s) of one ({sem}) address (they differ at {diff})")
        if G0 and G1 and stim(G0) != stim(G1):
            F.append(f"{what}: the endpoints do not declare one demonstration stimulus")
        v = ql.a2_row((G0 or {}).get("o") if ok(e["g0"]) else None, (G1 or {}).get("o") if ok(e["g1"]) else None, (G0 or {}).get("x"), (G1 or {}).get("x"))
        stored = conclusion(e, what)
        if stored is not None:
            row = stored.get(sem)
            if not isinstance(row, dict):
                F.append(f"{what}: the conclusion file has no row for this semantic")
            else:
                body = {k: v_ for k, v_ in row.items() if k not in ("g0_findings", "g1_findings")}
                if row.get("g0_findings") != findings_of(G0) or row.get("g1_findings") != findings_of(G1):
                    F.append(f"{what}: the row's endpoint findings are not the records'")
                elif G1 is None and e["g1"] is None:
                    if body.get("verdict") != "not_assessable":
                        F.append(f"{what}: a row with one endpoint claims {body.get('verdict')!r}")
                elif canon(body) != canon(v):
                    F.append(f"{what}: the retained conclusion ({body.get('verdict')}) is not the one recomputed from the records ({v['verdict']}) in full")
        out["a2"].append({"semantic": sem, "recomputed": v["verdict"], "stored": ((stored or {}).get(sem) or {}).get("verdict")})
    # a conclusion file nobody declared is an undeclared claim
    for f, key in (("a5_verdict.json", "a5"), ("a8_cross.json", "a8"), ("a2_rows.json", "a2")):
        if (d / f).is_file() and not plan.get(key):
            F.append(f"{f} is retained but the session declared no {key} qualification index for it")
    return out


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    out = None
    if "--json" in argv:
        i = argv.index("--json"); out = Path(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    reps = []
    for a in argv:
        try:
            reps.append(verify(Path(a)))
        except Exception as e:                                             # noqa: BLE001 — named, never a traceback: this is the VERIFIER's defect, not the archive's
            import traceback
            reps.append({"dir": str(a), "verifier_error": f"{type(e).__name__}: {e}", "where": traceback.format_exc().strip().splitlines()[-3:], "clean": False, "agree": False, "refused": None,
                         "session": [], "transactions": [], "chain": [], "a7": {"findings": []}, "qualification": {"findings": []}})
    for r in reps:
        if r.get("verifier_error"):
            print(f"{r['dir']}: VERIFIER ERROR — {r['verifier_error']} (the verifier's own defect on this archive; not a finding about the evidence)")
            continue
        if r.get("refused"):
            print(f"{r['dir']}: REFUSED — {r['refused']}")
            continue
        print(f"{r['dir']}: clean={r['clean']} agree={r['agree']} session={r['session']} chain={len(r['chain'])} a7={len(r['a7']['findings'])} qualification={r['qualification']['findings']}")
        for T in r["transactions"]:
            print(f"   {T['dir']}: {T['outcome']} | findings {len(T['findings'])} agrees={T['agrees']}")
    if out:
        out.write_text(json.dumps(reps if len(reps) > 1 else reps[0], indent=1) + "\n")
    if any(r.get("verifier_error") for r in reps):
        return 2
    return 0 if all(r["agree"] for r in reps) else 1


if __name__ == "__main__":
    sys.exit(main())
