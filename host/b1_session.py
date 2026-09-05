#!/usr/bin/env python3
"""B1 — the board session function: the instrument's `run_l6` (zynq-psoracle/host/l6_runner.py)
as copied into the round 1′ runner, with two injection points — the identity check applied
to the IDENT before it is acknowledged, and the adjudicator run over the evidence files as
written to disk. The preamble (precheck, identity, dcache off, clock preflight, carrier
load, key provisioning, identity page, image load, `go`), the console loop, the collector,
the relay and the evidence files are the instrument's, imported read-only. HOST-ONLY until
the owner rules; this function is reached only through b1_runner.preflight.
"""
from __future__ import annotations

import time
from pathlib import Path


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
        summary["provisioning"] = cfg["signer"].provision(execute=cfg["provision_execute"], ruling=cfg["provision_ruling"])
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

        (out_dir / "console.log").write_bytes(bytes(reader.raw))
        (out_dir / "console.ts.log").write_bytes(timeline.console_ts_log())
        pr.write_record(out_dir, "timeline", timeline.to_json())
        summary["epoch_end"] = collector.epoch_end
        summary["audits"] = len(collector.audits)
        summary["fragments"] = len(timeline.fragments)
        if collector.session_summary is None:
            gate_log = {"loop_records": collector.loop_records}
            audited_n, audited_src = lc.crash_audit_count(gate_log, collector.audits, g.load_manifest())
            summary["crash_summary_audit"] = {"audited": audited_n, "total": len(collector.loop_records), "source": audited_src}
            collector.session_summary = collector.crashed_summary(audit={"audited": audited_n, "total": len(collector.loop_records)},
                                                                  crc_dropped=console.crc_dropped, drop_budget=plan["crc_budget"])
        seqs = [r["seq"] for r in collector.loop_records]
        timing = lt.record_timing(timeline.frames, seqs)
        log = {"control_plane": "standalone", "app_identity": collector.app_identity,
               "loop_records": collector.loop_records, "session_summary": collector.session_summary,
               "notary_log": relay.notary_log(),
               "timing": {"clocks": lt.CLOCKS, "t_go_mono": t_go, "records": {str(s): timing[s] for s in seqs}},
               "l6": {**plan, "audit_seqs": sorted(plan["audit_seqs"])}}
        if collector.closing_negative is not None:
            log["closing_negative"] = collector.closing_negative
        pr.write_record(out_dir, "run_log", log)
        pr.write_record(out_dir, "audits", {"chunks": collector.audits, "pulls": console.pull_ledgers,
                                            "recs": console.rec_ledgers_json(), **console.rel_ledgers_json()})
        res = adjudicate(out_dir)
        pr.write_record(out_dir, "adjudication", {k: v for k, v in res.items() if k != "self_map_v2"})
        if res.get("self_map_v2") is not None:
            pr.write_record(out_dir, "self_map_v2", res["self_map_v2"])
        summary["adjudication"] = {k: res.get(k) for k in ("outcome", "findings", "replay", "b1_result", "prediction_comparison")}
        summary["findings"] = res.get("findings") or []
        summary["outcome"] = res["outcome"]
    except l3.Stop as stop:
        summary["outcome"] = (f"KILL {stop.detail}" if stop.verdict == "KILL" else f"STOP {stop.verdict}: {stop.detail}")
    except pr.ProbeStop as stop:
        summary["outcome"] = f"STOP {stop.verdict}: {stop.detail}"
    except bsn.SessionRefusal as refusal:
        summary["outcome"] = f"REFUSED: {refusal}"
    except Exception as exc:  # noqa: BLE001
        import traceback
        summary["outcome"] = f"CRASHED host-side: {type(exc).__name__}: {exc}"
        summary["traceback"] = traceback.format_exc()
    finally:
        if reader is not None and not (out_dir / "console.log").exists():
            (out_dir / "console.log").write_bytes(bytes(reader.raw))
            (out_dir / "console.ts.log").write_bytes(timeline.console_ts_log())
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
