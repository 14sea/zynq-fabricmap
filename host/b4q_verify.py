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
import b4q_frames as fr  # noqa: E402
import b4q_schema as sc  # noqa: E402
import b4q_view as vw  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def jl(p: Path) -> list:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.is_file() else []


def verify(d: Path, repo_root: Path = R) -> dict:
    d = Path(d)
    rep = {"dir": str(d), "session": [], "transactions": [], "a7": None, "agree": None}
    S = rep["session"]
    manifest = json.loads((d / "manifest.json").read_text())
    trace, pcap, acc = jl(d / "trace.jsonl"), jl(d / "pcap_log.jsonl"), jl(d / "accesses.jsonl")
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
    # 1. the session_open record
    so_doc = json.loads((d / "session_open.json").read_text())
    so = so_doc["record"]
    f = rec.validate_session_open(so) + sc.validate_named(so, "ff_session_open_v1")
    S += [f"session_open: {m}" for m in f]
    if so["instrument"] != instrument:
        S.append("session_open: the instrument is not the manifest's")
    if so["base_frames_reference_sha256"] != manifest["loaded_frames_reference_sha256"]:
        S.append("session_open: the reference is not the manifest's loaded-image reference")
    # the host's view of the startup readback: the first read_frame group of the PCAP log
    reads = [e for e in pcap if e.get("pcap") == "read_frame"]
    if len(reads) >= len(fr.TARGET_FARS):
        g = reads[:len(fr.TARGET_FARS)]
        if len({x["target_frames_hash"] for x in g}) != 1 or g[0]["target_frames_hash"] != so["startup_readback_sha256"]:
            S.append("session_open: the startup readback is not the host's view of the frames delivered")
    if so["status"] != "open" and not so_doc.get("findings"):
        S.append("session_open: refused, and the session recorded no finding")
    # the stored session findings
    stored_session_findings = list(so_doc.get("findings", []))
    # 1./2./4./5. every transaction
    txs = rec.transactions(trace)
    tx_dirs = sorted(p for p in d.iterdir() if p.is_dir() and p.name.startswith("tx_"))
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
        env = [e for e in pl if e.get("pcap") == "envelope_written"]
        rds = [e for e in pl if e.get("pcap") == "read_frame"]
        groups = [rds[k:k + len(fr.TARGET_FARS)] for k in range(0, len(rds), len(fr.TARGET_FARS))]
        gh = [g[0]["target_frames_hash"] if len(g) == len(fr.TARGET_FARS) and len({x["target_frames_hash"] for x in g}) == 1 else None for g in groups]
        want = {"staging_readback_sha256": env[1]["target_frames_hash"] if len(env) >= 2 else None, "fabric_readback_sha256_pre_event": gh[0] if len(gh) > 0 else None,
                "fabric_readback_sha256_post_event": gh[1] if len(gh) > 1 else None, "base_readback_sha256": gh[2] if len(gh) > 2 else None}
        for k, v in want.items():
            if (links.get(k) or None) != v:
                F.append(f"links.{k}: not the host's view recomputed from the PCAP log")
        if "commit" in links:
            notary = json.load(open(d / "notary_log.json"))
            if links["commit"] not in {e.get("commit") for e in notary}:
                F.append("links.commit: not a commit the notary signed")
        for name, mine, theirs in (("commit", links.get("commit"), fw.get("commit")), ("staged", links.get("staging_readback_sha256"), fw.get("staged")),
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
        T["unmodelled_reads"] = record.get("emulation", {}).get("unmodelled_cells")
    # the chain
    chain = rec.validate_chain(so, chain_entries)
    rep["chain"] = chain
    if chain != manifest.get("chain_findings"):
        S.append("chain: the session's recorded chain findings are not this verifier's")
    # 3. A7
    rep["a7"] = a7.check(acc, pcap)
    S += [f"A7: {m}" for m in rep["a7"]["findings"]]
    # agreement: every finding the session recorded is found here and vice versa (per transaction)
    agree = True
    for T in rep["transactions"]:
        mine = set(T["findings"]); theirs = set(T["stored_findings"])
        T["agrees"] = mine == theirs
        if not T["agrees"]:
            agree = False
            T["only_here"], T["only_stored"] = sorted(mine - theirs), sorted(theirs - mine)
    rep["session_findings_stored"] = stored_session_findings
    rep["agree"] = agree and not [m for m in S if not m.startswith("manifest: the executing-side binary")]
    rep["clean"] = agree and not S and all(not T["findings"] for T in rep["transactions"])
    return rep


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    out = None
    if "--json" in argv:
        i = argv.index("--json"); out = Path(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    reps = [verify(Path(a)) for a in argv]
    for r in reps:
        print(f"{r['dir']}: clean={r['clean']} agree={r['agree']} session={r['session']} chain={len(r['chain'])} a7={len(r['a7']['findings'])}")
        for T in r["transactions"]:
            print(f"   {T['dir']}: {T['outcome']} | findings {len(T['findings'])} agrees={T['agrees']}")
    if out:
        out.write_text(json.dumps(reps if len(reps) > 1 else reps[0], indent=1) + "\n")
    return 0 if all(r["agree"] for r in reps) else 1


if __name__ == "__main__":
    sys.exit(main())
