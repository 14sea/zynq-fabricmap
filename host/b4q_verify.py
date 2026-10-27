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
import b4q_a7 as a7  # noqa: E402
import b4q_qual as ql  # noqa: E402
import b4q_session as ss  # noqa: E402
import b4q_frames as fr  # noqa: E402
import b4q_schema as sc  # noqa: E402
import b4q_view as vw  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402


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
    for k, typ in (("label", str), ("instrument", dict), ("executing_side", dict), ("loaded_frames_reference_sha256", str), ("base_readback_reference_sha256", str),
                   ("write_set", dict), ("timing", dict), ("hypothesis", dict), ("mapping", dict), ("records", list), ("chain_findings", list), ("accesses", int), ("trace_events", int),
                   ("open_trace_range", list), ("qualification_plan", dict), ("emulated", bool)):
        if not isinstance(manifest.get(k), typ):
            raise ArchiveRefusal(f"manifest.{k}: missing or not a {typ.__name__}")
    if not isinstance(so_doc, dict) or not isinstance(so_doc.get("record"), dict) or not isinstance(so_doc.get("findings"), list):
        raise ArchiveRefusal("session_open.json: not {record, findings, ...}")
    if not isinstance(notary, list):
        raise ArchiveRefusal("notary_log.json: not a list")
    if not all(isinstance(e, dict) for e in trace + pcap + acc):
        raise ArchiveRefusal("a JSON-lines file holds a non-object line")
    recs = manifest["records"]
    for i, r in enumerate(recs):
        if not isinstance(r, dict) or type(r.get("seq")) is not int or not isinstance(r.get("dir"), str) or not _int_pair(r.get("trace_range")) or not _int_pair(r.get("pcap_range")) \
                or not isinstance(r.get("findings"), list) or r.get("kind") not in ("root", "normal", "inject", "a5"):
            raise ArchiveRefusal(f"manifest.records[{i}]: not a record entry (seq, dir, kind, trace_range, pcap_range, findings)")
        if r["seq"] != i + 1 or r["dir"] != f"tx_{i + 1:03d}":
            raise ArchiveRefusal(f"manifest.records[{i}]: seq / dir out of order ({r['seq']}, {r['dir']})")
    if not _int_pair(manifest["open_trace_range"]):
        raise ArchiveRefusal("manifest.open_trace_range: not an int pair")
    for r in recs:
        td = d / r["dir"]
        if not td.is_dir():
            raise ArchiveRefusal(f"{r['dir']}: declared in the manifest, not present")
        for f in ("record.json", "ctx.json", "links.json", "firmware_result.json"):
            if not (td / f).is_file():
                raise ArchiveRefusal(f"{r['dir']}/{f}: missing")
        try:
            rj = json.loads((td / "record.json").read_text())
        except ValueError as e:
            raise ArchiveRefusal(f"{r['dir']}/record.json: {e}")
        if rj.get("seq") != r["seq"] or rj.get("trace_range") != r["trace_range"] or rj.get("pcap_range") != r["pcap_range"]:
            raise ArchiveRefusal(f"{r['dir']}/record.json: seq / ranges are not the manifest's")
    extra = sorted(p.name for p in d.iterdir() if p.is_dir() and p.name.startswith("tx_") and p.name not in {r["dir"] for r in recs})
    if extra:
        raise ArchiveRefusal(f"record directories not declared in the manifest: {extra}")
    return {"manifest": manifest, "so_doc": so_doc, "notary": notary, "trace": trace, "pcap": pcap, "acc": acc}


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
    lo0 = manifest["open_trace_range"][1]
    cursor_t, cursor_p = lo0, 0
    for r in recs:
        if r["trace_range"][0] != cursor_t:
            S.append(f"completeness: {r['dir']} does not start where the previous record ended in the trace ({r['trace_range'][0]} vs {cursor_t})")
        if r["pcap_range"][0] != cursor_p and not (r["pcap_range"][0] >= cursor_p):
            S.append(f"completeness: {r['dir']} overlaps the previous record in the PCAP log")
        cursor_t, cursor_p = r["trace_range"][1], r["pcap_range"][1]
    tail = [e for e in trace[cursor_t:] if "op" in e or "mark" in e]
    if tail:
        S.append(f"completeness: {len(tail)} trace event(s) after the last declared record are not covered by any record (an unindexed suffix)")
    if recs and cursor_p < len(pcap):
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
        record = json.loads((td / "record.json").read_text())
        ctx = json.loads((td / "ctx.json").read_text())
        links = json.loads((td / "links.json").read_text())
        fw = json.loads((td / "firmware_result.json").read_text())
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
        o_stored = json.loads((td / "o.json").read_text()) if (td / "o.json").is_file() else None
        f_stored = json.loads((td / "f.json").read_text()) if (td / "f.json").is_file() else None
        x_stored = json.loads((td / "x.json").read_text()) if (td / "x.json").is_file() else None
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
    rep["qualification"] = verify_qualification(d, manifest, rep["transactions"], tx_dirs)
    S += [f"qualification: {m}" for m in rep["qualification"]["findings"]]
    # the chain
    chain = rec.validate_chain(so, chain_entries)
    rep["chain"] = chain
    if chain != manifest.get("chain_findings"):
        S.append("chain: the session's recorded chain findings are not this verifier's")
    # 3. A7
    rep["a7"] = a7.check(acc, pcap)
    declared = (manifest.get("backend") or {}).get("fault_injections") or {}
    injected = [a for a in acc if a.get("resp") and f"{(a['addr'] - a7.bk.AXI_BASE) & 0xFFFF:#06x}" in set(declared.get("refuse_writes", []))]
    for m in rep["a7"]["findings"]:
        if m.endswith("access(es) of the carrier window answered SLVERR") and injected and rep["a7"]["slverr"] == len(injected):
            rep["a7"].setdefault("declared_injections", []).append(f"{len(injected)} SLVERR(s) are the bench's declared refused writes {declared['refuse_writes']}: a simulation")
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


def verify_qualification(d: Path, manifest: dict, transactions: list, tx_dirs: list) -> dict:
    """The qualification index declared by the session (manifest.qualification_plan: which records play which role) validated
    against the available records, every conclusion recomputed with host/b4q_qual from the retained O / X and compared to the
    retained conclusion files (a5_verdict.json, a8_cross.json, a2_rows.json) — a conclusion file is never trusted; a missing
    corner, close witness or malformed record is `not demonstrated` / `not assessable`, never a positive claim (R3)."""
    plan = manifest.get("qualification_plan") or {}
    out = {"findings": [], "a5": [], "a8": [], "a2": []}
    F = out["findings"]
    valid = {t["dir"]: (not t["findings"]) for t in transactions}
    def ok(seq):
        return seq is not None and 1 <= seq <= len(tx_dirs) and valid.get(tx_dirs[seq - 1].name, False)
    for e in plan.get("a5", []):
        o1, x1 = _rec_of(tx_dirs, e.get("J1")); o2, x2 = _rec_of(tx_dirs, e.get("J2")); o3, x3 = _rec_of(tx_dirs, e.get("J3"))
        v = ql.a5_verdict(o1, o2, o3, x1, x3, x2) if (o1 and o2 and o3) else {"verdict": "not_demonstrated", "why": "a role's record is absent"}
        if not all(ok(e.get(k)) for k in ("J1", "J2", "J3")) and v["verdict"] == "pass":
            v = {"verdict": "not_demonstrated", "why": "a role's record carries findings: no pass is claimed on it"}
        stored = json.loads((d / e["conclusion_file"]).read_text()) if (d / e.get("conclusion_file", "")).is_file() else None
        if stored is None:
            F.append("A5: the conclusion file is missing")
        elif stored.get("verdict") != v["verdict"] or (v["verdict"] in ("pass", "fail") and canon(stored) != canon(v)):
            F.append(f"A5: the retained conclusion ({stored.get('verdict')}) is not the one recomputed from the records ({v['verdict']})")
        out["a5"].append({"recomputed": v["verdict"], "stored": stored.get("verdict") if stored else None})
    for e in plan.get("a8", []):
        corners, closes = {}, {}
        for c, seq in e.get("corners", {}).items():
            o, x = _rec_of(tx_dirs, seq); corners[c] = o; closes[c] = x if ok(seq) else None
        stored = json.loads((d / e["conclusion_file"]).read_text()) if (d / e.get("conclusion_file", "")).is_file() else None
        res = {}
        for el, idx in e.get("elements", {}).items():
            res[el] = ql.a8_classify(corners, idx, e.get("parts", {}), closes=closes) if all(corners.values()) else {"row": 0, "verdict": "not demonstrated", "why": "a corner's record is absent"}
        if stored is None:
            F.append("A8: the conclusion file is missing")
        else:
            for el, v in res.items():
                sv = stored.get(el) or {}
                if sv.get("row") != v["row"] or sv.get("verdict") != v["verdict"] or (v["row"] >= 2 and canon(sv.get("sr_readings")) != canon(v.get("sr_readings"))):
                    F.append(f"A8 {el}: the retained conclusion (row {sv.get('row')}) is not the one recomputed from the records (row {v['row']})")
        out["a8"].append({el: {"recomputed": v["verdict"], "stored": (stored or {}).get(el, {}).get("verdict")} for el, v in res.items()})
    for e in plan.get("a2", []):
        o0, x0 = _rec_of(tx_dirs, e.get("g0")); o1, x1 = _rec_of(tx_dirs, e.get("g1"))
        v = ql.a2_row(o0 if ok(e.get("g0")) else None, o1 if ok(e.get("g1")) else None, x0, x1)
        stored = json.loads((d / e["conclusion_file"]).read_text()) if (d / e.get("conclusion_file", "")).is_file() else None
        sv = (stored or {}).get(e.get("semantic"), {})
        if stored is None:
            F.append("A2: the conclusion file is missing")
        elif sv.get("verdict") != v["verdict"] or (v["verdict"] == "differs" and sv.get("n_differing") != v.get("n_differing")):
            F.append(f"A2 {e.get('semantic')}: the retained conclusion ({sv.get('verdict')}) is not the one recomputed from the records ({v['verdict']})")
        out["a2"].append({"semantic": e.get("semantic"), "recomputed": v["verdict"], "stored": sv.get("verdict")})
    # a conclusion file nobody declared is an undeclared claim
    for f in ("a5_verdict.json", "a8_cross.json", "a2_rows.json"):
        key = {"a5_verdict.json": "a5", "a8_cross.json": "a8", "a2_rows.json": "a2"}[f]
        if (d / f).is_file() and not plan.get(key):
            F.append(f"{f} is retained but the session declared no {key} qualification index for it")
    return out


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    out = None
    if "--json" in argv:
        i = argv.index("--json"); out = Path(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    reps = [verify(Path(a)) for a in argv]
    for r in reps:
        if r.get("refused"):
            print(f"{r['dir']}: REFUSED — {r['refused']}")
            continue
        print(f"{r['dir']}: clean={r['clean']} agree={r['agree']} session={r['session']} chain={len(r['chain'])} a7={len(r['a7']['findings'])} qualification={r['qualification']['findings']}")
        for T in r["transactions"]:
            print(f"   {T['dir']}: {T['outcome']} | findings {len(T['findings'])} agrees={T['agrees']}")
    if out:
        out.write_text(json.dumps(reps if len(reps) > 1 else reps[0], indent=1) + "\n")
    return 0 if all(r["agree"] for r in reps) else 1


if __name__ == "__main__":
    sys.exit(main())
