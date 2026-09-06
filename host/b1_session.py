#!/usr/bin/env python3
"""B1 — the board session function: the instrument's `run_l6` (zynq-psoracle/host/l6_runner.py)
as copied into the round 1′ runner, with two injection points — the identity check applied
to the IDENT before it is acknowledged, and the adjudicator run over the evidence files as
written to disk. The preamble (precheck, identity, dcache off, clock preflight, carrier
load, key provisioning, identity page, image load, `go`), the console loop, the collector,
the relay and the evidence files are the instrument's, imported read-only. HOST-ONLY until
the owner rules; this function is reached only through b1_runner.preflight.

FINALIZATION (B1Q session 1, 2026-09-06, LOST — the owner's review
docs/b1q_session1_review_2026_09_06.md): the copied tail called `collector.crashed_summary()`
whenever the board's summary was missing, which the instrument's method accepts only for a
CRASHED end; on that session's PROTOCOL end it raised BEFORE run_log / audits were written
and the collected evidence (11 records, 88 audit chunks, the notary log, the ledgers) was
lost. Now:
  * `collector_summary` writes the collector's summary for the ACTUAL end — CRASHED,
    PROTOCOL or STOPPED — never relabelling one as another and never promoting anything to
    COMPLETED; a valid app summary is always kept;
  * `export_evidence` persists every independent export — console.log, console.ts.log,
    timeline, run_log (records, notary log, timing, the summary), audits (chunks and the
    transaction ledgers) — each in its own try, BEFORE adjudication, recording per-file
    success or the error (`summary.exports`); one failure never blocks the others;
  * `finalize` = export, then adjudicate in its own try (an adjudicator error is recorded
    as the outcome, the evidence already on disk), then the qualification record;
  * the outer paths (a failure before or after the console exists) export what exists and
    keep the PRIMARY cause (`summary.epoch_end`, `summary.outcome`) beside any secondary
    host exception (`summary.host_error`).
The same functions are driven by the host-only modelled session (host/b1_modelled_session.py)
and tested with fake dependencies (tests/test_b1_session_finalize.py).
"""
from __future__ import annotations

import time
from pathlib import Path


import json
import traceback

INCOMPLETE = "INCOMPLETE"


def collector_summary(collector, audit: dict, crc_dropped: int, drop_budget: int) -> dict:
    """The collector-written session_summary for an epoch the board did not close with a
    valid TERM, for the ACTUAL end the collector recorded (CRASHED, PROTOCOL, STOPPED). No
    closing step is asserted (a valid CLOSE frame, if any, stays in `closing_negative` as
    an observation — it never becomes a closing claim here); the epoch_end's kind and
    reason are the collector's own. A missing epoch_end is CRASHED with the reason said."""
    end = collector.epoch_end or {"kind": "CRASHED", "last_seq": collector.last_rec_seq, "reason": "no epoch end was recorded"}
    if end["kind"] == "CRASHED":
        if collector.epoch_end is None:
            collector.epoch_end = end
        return collector.crashed_summary(audit=audit, crc_dropped=crc_dropped, drop_budget=drop_budget)
    if end["kind"] == "COMPLETED":
        # a COMPLETED epoch without a valid app summary cannot exist (the summary IS the TERM);
        # never synthesise one — record what the collector saw, as a protocol failure
        end = {"kind": "PROTOCOL", "last_seq": end.get("last_seq"), "reason": "COMPLETED recorded without a valid TERM summary"}
        collector.epoch_end = end
    return {"schema": "session_summary", "schema_version": "1.0.0", "token": collector.token,
            "epoch_end": dict(end),
            "counts": {"scored": sum(1 for r in collector.loop_records if r.get("outcome") == "SCORED"),
                       "refused_by_gate": sum(1 for r in collector.loop_records if r.get("outcome") == "REFUSED_BY_GATE")},
            "closing": {"restore": "not_reached", "baseline": "not_reached", "unsigned_control": "not_reached"},
            "audit": audit, "crc_dropped": crc_dropped, "drop_budget": drop_budget, "written_by": "collector"}


REQUIRED_EXPORTS = ("console.log", "console.ts.log", "timeline.json", "session_summary", "run_log.json", "audits.json")
EXPORTS_MANIFEST = "exports.json"


def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_exports_manifest(out_dir: Path, exports: dict) -> dict:
    """exports.json — the per-export status table and the sha256 / size of every file that
    was written, the LAST export; `complete` is true only when every required export is
    "ok". The adjudicators require it (b1_adjudicate.check_exports) and the qualification
    chain binds it: a session whose exports are not complete cannot be adjudicated PASS
    from a subset of its files (owner's review of v2.4, 2026-09-06)."""
    out_dir = Path(out_dir)
    files = {}
    for name in ("console.log", "console.ts.log", "timeline.json", "run_log.json", "audits.json"):
        p = out_dir / name
        files[name] = {"status": exports.get(name, "INCOMPLETE: not attempted"),
                       "sha256": _sha(p) if p.is_file() else None, "bytes": p.stat().st_size if p.is_file() else None}
    doc = {"schema": "b1_session_exports", "schema_version": "1.0.0", "required": list(REQUIRED_EXPORTS),
           "statuses": {k: exports.get(k, "INCOMPLETE: not attempted") for k in REQUIRED_EXPORTS},
           "files": files, "complete": all(exports.get(k) == "ok" for k in REQUIRED_EXPORTS)}
    tmp = out_dir / (EXPORTS_MANIFEST + ".part")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n"); tmp.replace(out_dir / EXPORTS_MANIFEST)
    return doc


def exports_complete(exports: dict) -> tuple[bool, list[str]]:
    missing = [k for k in REQUIRED_EXPORTS if exports.get(k) != "ok"]
    return (not missing), [f"{k}={exports.get(k, 'INCOMPLETE: not attempted')}" for k in missing]


def export_evidence(out_dir: Path, summary: dict, plan: dict, collector, console, relay, timeline, reader, t_go) -> dict:
    """Every independent export, each in its own try, and WITHIN run_log.json / audits.json
    the base data (the records; the chunks) written independently of every enrichment
    (timing, the notary log, each transaction ledger): an enrichment that fails is marked
    INCOMPLETE in place and the file's status is PARTIAL — the collected data is never
    lost to a helper (owner's review of v2.4, 2026-09-06). The result table goes into
    summary["exports"] and exports.json. Nothing here raises."""
    import l6_checks as lc  # noqa: E402
    import l6_timing as lt  # noqa: E402
    import p3_gate as g  # noqa: E402
    import pcap_probe_runner as pr  # noqa: E402
    out_dir = Path(out_dir)
    exports: dict = summary.setdefault("exports", {})

    def attempt(name, fn):
        try:
            fn(); exports[name] = "ok"
        except Exception as exc:  # noqa: BLE001 — recorded, never fatal to the other exports
            exports[name] = f"{INCOMPLETE}: {type(exc).__name__}: {exc}"

    def component(doc, key, fn, partial: list):
        """One enrichment of a document: its value, or an INCOMPLETE marker in its place."""
        try:
            doc[key] = fn()
        except Exception as exc:  # noqa: BLE001
            doc[key] = {INCOMPLETE: f"{type(exc).__name__}: {exc}"}
            partial.append(f"{key} {INCOMPLETE}: {type(exc).__name__}: {exc}")

    if reader is not None:
        attempt("console.log", lambda: (out_dir / "console.log").write_bytes(bytes(reader.raw)))
    else:
        exports["console.log"] = f"{INCOMPLETE}: no console was opened"
    if timeline is not None:
        attempt("console.ts.log", lambda: (out_dir / "console.ts.log").write_bytes(timeline.console_ts_log()))
        attempt("timeline.json", lambda: pr.write_record(out_dir, "timeline", timeline.to_json()))
    else:
        exports["console.ts.log"] = exports["timeline.json"] = f"{INCOMPLETE}: no timeline"
    if collector is None:
        exports["session_summary"] = exports["run_log.json"] = exports["audits.json"] = f"{INCOMPLETE}: no collector"
        write_exports_manifest(out_dir, exports)
        return exports
    summary["epoch_end"] = collector.epoch_end
    summary["audits"] = len(collector.audits)
    if timeline is not None:
        summary["fragments"] = len(timeline.fragments)

    def build_summary():
        if collector.session_summary is not None:
            summary["session_summary_written_by"] = collector.session_summary.get("written_by", "app")
            return
        gate_log = {"loop_records": collector.loop_records}
        audited_n, audited_src = lc.crash_audit_count(gate_log, collector.audits, g.load_manifest())
        summary["collector_summary_audit"] = {"audited": audited_n, "total": len(collector.loop_records), "source": audited_src}
        collector.session_summary = collector_summary(collector, {"audited": audited_n, "total": len(collector.loop_records)},
                                                      console.crc_dropped if console is not None else 0, plan["crc_budget"])
        summary["session_summary_written_by"] = "collector"
    attempt("session_summary", build_summary)
    summary["epoch_end"] = collector.epoch_end          # a missing end became CRASHED in the summary construction

    def write_run_log():
        partial: list[str] = []
        # the BASE: what the collector holds, no helper in the way
        log = {"control_plane": "standalone", "app_identity": collector.app_identity,
               "loop_records": collector.loop_records, "session_summary": collector.session_summary,
               "l6": {**plan, "audit_seqs": sorted(plan["audit_seqs"])}}
        if collector.closing_negative is not None:
            if collector.session_summary is not None and collector.session_summary.get("written_by") == "app":
                log["closing_negative"] = collector.closing_negative
            else:
                # a valid CLOSE frame was received but the board's own summary was not: the
                # frame is kept as an OBSERVATION, never as the closing claim rule (viii) reads
                # `closing_negative` as (owner's review of B1Q session 1, 2026-09-06)
                log["observed_close_frame"] = {"frame": collector.closing_negative,
                                               "note": "received as a valid CLOSE frame; not a closing claim: the epoch has no valid app summary"}
        if collector.session_summary is None:
            partial.append(f"session_summary {INCOMPLETE}: {exports.get('session_summary')}")
        # the ENRICHMENTS, each on its own
        component(log, "notary_log", lambda: relay.notary_log() if relay is not None else {INCOMPLETE: "no relay"}, partial)
        seqs = [r["seq"] for r in collector.loop_records]
        def timing():
            if timeline is None:
                raise RuntimeError("no timeline")
            t = lt.record_timing(timeline.frames, seqs)
            return {"clocks": lt.CLOCKS, "t_go_mono": t_go, "records": {str(sq): t.get(sq) for sq in seqs}}
        component(log, "timing", timing, partial)
        if partial:
            log[INCOMPLETE] = partial
        pr.write_record(out_dir, "run_log", log)
        if partial:
            raise PartialExport("; ".join(partial))
    attempt("run_log.json", write_run_log)

    def write_audits():
        partial: list[str] = []
        doc = {"chunks": collector.audits}                       # the BASE
        if console is not None:
            component(doc, "pulls", lambda: list(console.pull_ledgers), partial)
            component(doc, "recs", lambda: console.rec_ledgers_json(), partial)
            def rel():
                d = console.rel_ledgers_json()
                if not isinstance(d, dict):
                    raise TypeError("rel_ledgers_json did not return a dict")
                return d
            component(doc, "rel", rel, partial)
            if isinstance(doc.get("rel"), dict) and INCOMPLETE not in doc["rel"]:
                doc.update(doc.pop("rel"))                       # the instrument's layout: signs/terms/… at the top
        else:
            partial.append(f"ledgers {INCOMPLETE}: no console")
        if partial:
            doc[INCOMPLETE] = partial
        pr.write_record(out_dir, "audits", doc)
        if partial:
            raise PartialExport("; ".join(partial))
    attempt("audits.json", write_audits)
    write_exports_manifest(out_dir, exports)
    return exports


class PartialExport(Exception):
    """The file was written with its base data, but an enrichment is missing (the message
    names it): the export's status is PARTIAL, never ok."""


def finalize(out_dir: Path, summary: dict, plan: dict, collector, console, relay, timeline, reader, t_go, adjudicate) -> dict:
    """Export first, adjudicate second (in its own try), record third. EVERY required export
    must be "ok" — the raw console, its timestamps, the timeline, the summary construction,
    run_log and audits complete with all their components — or the outcome is a named HOLD
    and the adjudicator is not consulted (a diagnostic result over a subset of the evidence
    must not become the session's PASS). An adjudicator error is the outcome too, with the
    primary end kept in summary["epoch_end"]."""
    import pcap_probe_runner as pr  # noqa: E402
    exports = export_evidence(out_dir, summary, plan, collector, console, relay, timeline, reader, t_go)
    for k, v in list(exports.items()):
        if v.startswith(f"{INCOMPLETE}: PartialExport"):
            exports[k] = "PARTIAL: " + v.split(": ", 2)[2]
    write_exports_manifest(out_dir, exports)
    complete, missing = exports_complete(exports)
    if not complete:
        summary["outcome"] = "HOLD host-side: evidence export incomplete: " + "; ".join(missing)
        return summary
    try:
        res = adjudicate(out_dir)
        pr.write_record(out_dir, "adjudication", {k: v for k, v in res.items() if k != "self_map_v2"})
        if res.get("self_map_v2") is not None:
            pr.write_record(out_dir, "self_map_v2", res["self_map_v2"])
        summary["adjudication"] = {k: res.get(k) for k in ("outcome", "findings", "replay", "b1_result", "prediction_comparison")}
        summary["findings"] = res.get("findings") or []
        summary["outcome"] = res["outcome"]
    except Exception as exc:  # noqa: BLE001 — the evidence is on disk; the error is the outcome
        summary["host_error"] = {"where": "adjudicate", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
        summary["outcome"] = f"HOLD host-side: adjudicator error: {type(exc).__name__}: {exc}"
        pr.write_record(out_dir, "adjudication", {"outcome": summary["outcome"], "session": plan.get("session"),
                                                  "INCOMPLETE": "the adjudicator raised; the evidence files stand"})
    return summary


def run(session, out_dir: Path, ruling: dict, cfg: dict, identity_check, adjudicate, tool_version: str) -> dict:
    import board_session as bsn  # noqa: E402
    import l3_runner as l3  # noqa: E402
    import l5_notary as n  # noqa: E402
    import l5_runner as l5  # noqa: E402
    import l6_checks as lc  # noqa: E402
    import l6_console as lcs  # noqa: E402
    import l6_reader as lrd  # noqa: E402
    import l6_runner as l6  # noqa: E402
    import l6_timing as lt  # noqa: E402
    import p2_observe as ob  # noqa: E402
    import p3_gate as g  # noqa: E402
    import p3_oracle as po  # noqa: E402
    import pcap_probe_runner as pr  # noqa: E402
    manifest = cfg["carrier"]
    token = cfg["token"]
    plan = cfg["plan"]
    summary = {"tool": tool_version, "ruling": ruling, "outcome": None, "token": token, "stages": {},
               "l6": {**plan, "audit_seqs": sorted(plan["audit_seqs"])}, "findings": [],
               "round": {"manifest_sha256": cfg["manifest_sha256"], "instrument": cfg["instrument"]}}
    collector = n.Collector(token, heartbeat_s=cfg["heartbeat_s"])
    relay = n.NotaryRelay(token, cfg["signer"].sign_genome, drop_budget=plan["crc_budget"])
    timeline = lt.Timeline()
    reader = None
    console = None
    t_go = None
    finalized = False

    def finish(rec, name):
        pr.write_record(out_dir, name, rec)
        summary["stages"][name] = rec.get("verdict", "recorded")

    def send(line: str, mtype: str, seq: int) -> None:
        l5.send_raw_line(session.transport, line)
        timeline.note_sent(mtype, seq, time.monotonic(), time.time())

    try:
        summary["precheck"] = pr.precheck(session)
        summary["identity"] = session.verify_identity()
        l3.ensure_dcache_off(session)
        cpu_clk = session.read_word(l5.CPU_CLK_CTRL)
        preflight_rec = {"stage": "B1_0_preflight", "CPU_CLK_CTRL": f"{cpu_clk:#010x}", "addr": f"{l5.CPU_CLK_CTRL:#010x}", "verdict": "READ"}
        finish(preflight_rec, "B1_0_preflight")
        summary["cpu_clk_ctrl"] = preflight_rec["CPU_CLK_CTRL"]
        fclk = ob.fclk0_mhz(*[session.read_word(a) for a in (ob.IO_PLL_CTRL, ob.ARM_PLL_CTRL, ob.DDR_PLL_CTRL, ob.FPGA0_CLK_CTRL)])
        summary["fclk0"] = fclk
        summary["setup_load"] = session.load_carrier(bsn.SETUP_LOAD_CAPABILITY, cfg["bitstream"], manifest["bitstream_sha256"], out_dir / "ymodem.log")
        # the digest of the provisioning ruling's BYTES the signer is handed, taken before and
        # after the call: the qualification chain requires it to equal the archived copy's
        import hashlib as _h
        pk_path = Path(cfg["provision_ruling"])
        summary["provisioning_ruling_sha256"] = _h.sha256(pk_path.read_bytes()).hexdigest()
        summary["provisioning"] = cfg["signer"].provision(execute=cfg["provision_execute"], ruling=cfg["provision_ruling"])
        if _h.sha256(pk_path.read_bytes()).hexdigest() != summary["provisioning_ruling_sha256"]:
            raise l3.Stop("PROVISION_RULING_CHANGED", "the provisioning ruling file changed while the signer used it")
        plane = l3.Plane(session)
        status = plane.read(po.STATUS)
        if not status >> po.ST["key_loaded"] & 1:
            raise l3.Stop("KEY_NOT_LOADED", f"STATUS {status:#010x}")
        nonce = plane.read(po.NONCE_LO) | plane.read(po.NONCE_HI) << 32
        page = l5.build_page(token, session.epoch, cfg["image_sha256"], manifest["bitstream_sha256"], nonce,
                             status, plan["master_seed"], plan["n"], plan["flags"], int(fclk["mhz"] * 1e6))
        for i, w in enumerate(page):
            session.command(f"mw.l {l5.PAGE_ADDR + 4 * i:#010x} {w:#010x} 1")
        readback = session.read_words(l5.PAGE_ADDR, len(page))
        if readback != page:
            raise l3.Stop("PAGE_MISMATCH", "the identity page did not read back as written")
        finish({"stage": "B1_1_identity_page", "words": [f"{w:08x}" for w in page], "flags": f"{plan['flags']:#x}", "verdict": "WRITTEN"}, "B1_1_identity_page")
        session.begin_ymodem(l5.APP_LOAD_ADDR)
        session.finish_ymodem(cfg["image"], out_dir / "ymodem_app.log", cfg["image"].stat().st_size)
        summary["image_loaded"] = {"addr": f"{l5.APP_LOAD_ADDR:#010x}", "sha256": cfg["image_sha256"], "bytes": cfg["image"].stat().st_size}

        reader = lrd.L6LineReader(session.transport._serial)  # noqa: SLF001
        l5.send_raw_line(session.transport, f"go {l5.APP_LOAD_ADDR:#x}")
        t_go = time.monotonic()
        collector.last_heard = collector.clock()
        deadline = t_go + plan["session_timeout_s"]
        console = lcs.ConsoleSession(token, collector, relay, timeline, plan["audit_seqs"], plan["crc_budget"], send,
                                     reader=reader, clock=time.monotonic, protocol=plan["protocol"],
                                     identity_check=identity_check, bad_frame_policy=lcs.BAD_FRAME_LEDGER,
                                     bad_frame_budget=plan["bad_frame_budget"])
        while l6.session_loop_continues(collector, console, time.monotonic(), deadline):
            for line, t_mono, t_wall in reader.poll():
                console.on_line(line, t_mono, t_wall)
            console.tick()
            if reader.saw_uboot_banner():
                collector.on_banner()
            collector.poll()
            time.sleep(0.02)
        if collector.epoch_end is None:
            collector._crash(f"the runner's own {plan['session_timeout_s']} s bound elapsed")
        finalized = True
        finalize(out_dir, summary, plan, collector, console, relay, timeline, reader, t_go, adjudicate)
    except l3.Stop as stop:
        summary["outcome"] = (f"KILL {stop.detail}" if stop.verdict == "KILL" else f"STOP {stop.verdict}: {stop.detail}")
    except pr.ProbeStop as stop:
        summary["outcome"] = f"STOP {stop.verdict}: {stop.detail}"
    except bsn.SessionRefusal as refusal:
        summary["outcome"] = f"REFUSED: {refusal}"
    except Exception as exc:  # noqa: BLE001
        summary["host_error"] = {"where": "session", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
        summary["outcome"] = f"CRASHED host-side: {type(exc).__name__}: {exc}"
    finally:
        if not finalized and console is not None:
            # the console existed (the board was running) and the normal finalization was not
            # reached: export everything collected, with the primary cause kept above
            ex = export_evidence(out_dir, summary, plan, collector, console, relay, timeline, reader, t_go)
            for k, v in list(ex.items()):
                if v.startswith(f"{INCOMPLETE}: PartialExport"):
                    ex[k] = "PARTIAL: " + v.split(": ", 2)[2]
            write_exports_manifest(out_dir, ex)
        elif not finalized and reader is not None:
            export_evidence(out_dir, summary, plan, None, None, None, timeline, reader, t_go)
        summary["uart_log"] = session.log
        summary["disruptions"] = session.disruptions
        summary["transport_rereads"] = session.rereads
        summary["epoch_final"] = session.epoch
        summary["crc_dropped"] = timeline.crc_dropped
        summary["crc_dropped_by_type"] = dict(timeline.crc_dropped_by_type)
        summary["bad_frames"] = timeline.bad_frames
        summary["crc_budget"] = plan["crc_budget"]
        pr.write_record(out_dir, "summary", summary)
    return summary
