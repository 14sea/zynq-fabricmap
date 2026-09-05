#!/usr/bin/env python3
"""Claim B round 1′ — the board runner. Ruling text RULING_TEXT. HOST-ONLY UNTIL RULED.

    claimb_r1p_runner.py --ruling <whole-of-run Claim B round 1′ json> --provision-ruling <P3-K json>
                         --boundary <principal_boundary json> --out <evidence dir> --image <p3_app_l6.bin>
                         [--manifest …] [--instrument-root …] [--port …] [--key …] [--signer-user …]

One session, "B": the pinned two-operator image on the pinned P3 carrier, `abba` over the
plan's N candidates with the plan's master seed, the sampled audit policy, the watchdog
and both seq-1 controls armed — the S #3 configuration with this round's seed and N, and
the runner's deadline = the evidenced window after `go`. The console loop, the notary
relay, the collector, the reader and the timeline are the instrument's (bound read-only by
`claimb_r1p_instrument`); the session function below is `zynq-psoracle/host/l6_runner.py`'s
`run_l6` copied — the instrument that PASSED is not edited to serve this round — with the
adjudication replaced by `claimb_r1p_adjudicate` over the files as written to disk.

FAIL-CLOSED, in this order, before any board contact: the ruling text; a `provisioning
P3-K` ruling present, parseable and unconsumed; the manifest's FROZEN preregistration hash
(null = DRAFT = refused) and the document hashing to it; the plan and the prediction
hashing to the manifest's pins; the instrument at its pinned commit, clean, every pinned
file hashing (then bound); the instrument's L6 manifest hashing to its pin, the image
pinned there and board-ready, the watchdog pinned ON with the D-s1 load value; the image
file hashing to the pin; the carrier manifest and bitstream hashing to their pins; the
operator data regenerated equal to the pin; BOTH rulings bound to this session, the
frozen prereg, the pinned image and the sha256 of THIS round's manifest file (and the
Claim B ruling to the plan's master seed); the principal boundary < 6 h AND bound to this
invocation; `sb` installed; the evidence directory not existing. Each is a named refusal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import secrets
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import claimb_r1p_adjudicate as adj  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

TOOL_VERSION = "claimb_r1p_runner.py/0.1.0"
RULING_TEXT = "whole-of-run Claim B round 1′"
PROVISION_RULING_TEXT = "provisioning P3-K"
SESSION = "B"
WATCHDOG_LOAD, WATCHDOG_PRESCALER = 1250000035, 7


class Refusal(Exception):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind_ruling(ruling: dict, text: str, prereg_sha: str, image_sha: str, manifest_sha: str,
                master_seed: int | None) -> None:
    want = {"session": SESSION, "prereg_sha256": prereg_sha, "image_sha256": image_sha,
            "claimb_manifest_sha256": manifest_sha}
    if master_seed is not None:
        want["master_seed"] = master_seed
    for k, v in want.items():
        if k not in ruling:
            raise Refusal(f"ruling {text!r} is not bound: it lacks {k!r}")
        got = ruling[k]
        if k == "master_seed" and isinstance(got, str):
            try:
                got = int(got, 0)
            except ValueError:
                raise Refusal(f"ruling {text!r}: master_seed {got!r} is not a number") from None
        if got != v:
            raise Refusal(f"ruling {text!r} is bound to {k} = {got!r}, this session needs {v!r}")


def preflight(a) -> dict:
    """The fail-closed checks, in the documented order. Returns cfg or raises Refusal."""
    manifest = json.loads(a.manifest.read_text())
    manifest_sha = _sha(a.manifest)
    # the two rulings, by text, unconsumed — before anything else is even read
    # (the instrument's parser is used AFTER the instrument is verified; until then the
    # file is checked for its text and consumption marker here)
    def parse(path: Path, text: str) -> dict:
        consumed = path.with_name(path.name + ".consumed")
        if consumed.exists():
            raise Refusal(f"the ruling {path} was consumed ({consumed.read_text().strip()[:80]})")
        try:
            r = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise Refusal(f"no readable ruling at {path}: {exc}") from exc
        for f in ("ruling", "boardid", "granted_by", "date"):
            if not r.get(f):
                raise Refusal(f"ruling {path} lacks {f!r}")
        if r["ruling"] != text:
            raise Refusal(f"ruling text {r['ruling']!r} != {text!r}")
        if r["boardid"] != manifest["board"]["boardid"]:
            raise Refusal(f"ruling names board {r['boardid']!r}, this round is {manifest['board']['boardid']!r}")
        return r
    ruling = parse(a.ruling, RULING_TEXT)
    if a.provision_ruling is None:
        raise Refusal("--provision-ruling is mandatory: no `provisioning P3-K` ruling, no board contact")
    pk = parse(a.provision_ruling, PROVISION_RULING_TEXT)
    # the frozen preregistration
    pinned_prereg = manifest["prereg"]["sha256"]
    if not pinned_prereg:
        raise Refusal("the round 1′ preregistration is not frozen (manifest prereg.sha256 is null): host-only until the owner freezes it")
    prereg_path = REPO_ROOT / manifest["prereg"]["path"]
    if not prereg_path.is_file() or _sha(prereg_path) != pinned_prereg:
        raise Refusal(f"{manifest['prereg']['path']} does not hash to the frozen preregistration")
    # the plan and the prediction
    plan_path = REPO_ROOT / manifest["plan"]["path"]
    pred_path = REPO_ROOT / manifest["model_prediction"]["path"]
    try:
        adj.check_pins(manifest, plan_path, pred_path)
    except adj.Refusal as exc:
        raise Refusal(str(exc)) from None
    plan = json.loads(plan_path.read_text())
    pred = json.loads(pred_path.read_text())
    # the instrument, verified then bound
    try:
        verified = inst.bind(a.instrument_root, manifest=manifest)
    except inst.InstrumentRefusal as exc:
        raise Refusal(f"instrument: {exc}") from None
    import board_session as bsn  # noqa: E402
    import l3_runner as l3  # noqa: E402
    import l6_operators as lo  # noqa: E402
    import l6_schedule as ls  # noqa: E402
    import p3_gate as g  # noqa: E402
    from validators import records  # noqa: E402
    root = a.instrument_root
    l6m_path = root / "manifests/l6_manifest.json"
    if _sha(l6m_path) != manifest["instrument"]["l6_manifest_sha256"]:
        raise Refusal("the instrument's L6 manifest does not hash to this round's pin")
    l6m = json.loads(l6m_path.read_text())
    wd = l6m["pinned_at_build"]
    pinned_image = manifest["instrument"]["image_sha256"]
    if wd["app_image_sha256"] != pinned_image or not wd.get("board_ready"):
        raise Refusal("the instrument's pinned image is not this round's image, or is not board-ready")
    if not wd["watchdog_enabled"] or wd["watchdog_load_value"] != WATCHDOG_LOAD or wd["watchdog_prescaler"] != WATCHDOG_PRESCALER:
        raise Refusal("D-s1: the watchdog must be pinned ON with prescaler 7 and load 1250000035")
    if wd.get("protocol") != manifest["protocol"]["wire"] or l6m["prereg"].get("protocol") != manifest["protocol"]["wire"]:
        raise Refusal("the image / L6 preregistration protocol is not this round's wire protocol")
    if l6m["prereg"]["sha256"] != manifest["instrument"]["l6_prereg_sha256"]:
        raise Refusal("the instrument's frozen L6 preregistration hash is not this round's pin")
    if not a.image.is_file():
        raise Refusal(f"no application image at {a.image}")
    image_sha = _sha(a.image)
    if image_sha != pinned_image:
        raise Refusal(f"the image is not the pinned one: {image_sha[:16]}… != {pinned_image[:16]}…")
    car = manifest["instrument"]["carrier"]
    car_manifest, car_bit = root / car["manifest"], root / car["bitstream"]
    if not car_manifest.is_file() or _sha(car_manifest) != car["manifest_sha256"]:
        raise Refusal("the carrier manifest does not hash to the pin")
    if not car_bit.is_file() or _sha(car_bit) != car["bitstream_sha256"]:
        raise Refusal("the carrier bitstream does not hash to the pin")
    if l6m["instrument"]["carrier"]["bitstream_sha256"] != car["bitstream_sha256"]:
        raise Refusal("the instrument's carrier pin is not this round's carrier")
    data = lo.operator_data(g.load_manifest(), lo.load_local_map())
    if lo.operator_data_sha256(data) != manifest["instrument"]["operator_data_sha256"]:
        raise Refusal("the operator data regenerated from local_map.json is not the pinned derivation")
    if plan["master_seed"] != manifest["seeds"]["master_seed"]:
        raise Refusal("the plan's master seed is not the manifest's")
    bind_ruling(ruling, RULING_TEXT, pinned_prereg, pinned_image, manifest_sha, plan["master_seed"])
    bind_ruling(pk, PROVISION_RULING_TEXT, pinned_prereg, pinned_image, manifest_sha, None)
    if shutil.which("sb") is None:
        raise Refusal("`sb` is not installed")
    carrier = json.loads(car_manifest.read_text()); records.validate(carrier)
    boundary = json.loads(a.boundary.read_text())
    records.boundary_established(boundary, time.time())
    me = pwd.getpwuid(os.getuid()).pw_name
    if boundary["runner_user"] != me:
        raise Refusal(f"principal boundary: the record's runner_user {boundary['runner_user']!r} is not this OS user {me!r}")
    if boundary["signer_user"] != a.signer_user:
        raise Refusal(f"principal boundary: --signer-user {a.signer_user!r} is not the record's {boundary['signer_user']!r}")
    want_key = os.path.normpath(os.path.join(boundary["key_store"], "K.bin"))
    if os.path.normpath(str(a.key)) != want_key:
        raise Refusal(f"principal boundary: --key {a.key} is not the record's key store's {want_key}")
    if a.out.exists():
        raise Refusal(f"{a.out} exists; evidence is never replaced")
    sched = ls.schedule(plan["master_seed"], plan["n"], plan["mode"])
    if hashlib.sha256(json.dumps(sched, sort_keys=True).encode()).hexdigest() != plan["schedule_sha256"]:
        raise Refusal("the regenerated schedule does not hash to the plan's schedule_sha256")
    flags = ls.flags_for(plan["mode"], watchdog=True, rec_control=True, sign_control=True)
    if flags != plan["flags"]:
        raise Refusal("the plan's flags word is not the one this runner would write")
    session_plan = {"session": SESSION, "mode": plan["mode"], "master_seed": plan["master_seed"], "n": plan["n"],
                    "schedule": sched, "audit_policy": plan["audit_policy"], "audit_seqs": set(plan["audit_seqs"]),
                    "expected_frames": plan["expected_frames"], "crc_budget": plan["crc_budget"],
                    "crc_formula": plan["crc_formula"], "session_timeout_s": float(plan["session_timeout_s"]),
                    "inputs": {"plan_sha256": manifest["plan"]["sha256"], "prediction_sha256": manifest["model_prediction"]["sha256"],
                               "window_s": plan["window_s"], "sizing": plan["sizing"]["formula"],
                               "settle_polls_median_calibration": [plan["settle_polls_median_calibration"]]},
                    "rules_version": "claimb-r1p/v0.1 over L6 v0.7 rules", "bad_frame_policy": "ledger",
                    "bad_frame_budget": plan["bad_frame_budget"], "hb_rule": "v07", "protocol": plan["protocol"],
                    "rec_retry_control": True, "flags": flags,
                    "binding": {"image_sha256": image_sha, "prereg_sha256": pinned_prereg, "protocol": plan["protocol"],
                                "session": SESSION, "schedule_mode": plan["mode"], "master_seed": plan["master_seed"],
                                "claimb_manifest_sha256": manifest_sha, "psoracle_commit": verified["psoracle_commit"]}}
    expected_genomes = {row["seq"]: __import__("p3_genome").to_hex(lo.OPERATORS[row["arm"]](row["seed"], data)) for row in sched}
    return {"ruling": ruling, "manifest": manifest, "manifest_sha256": manifest_sha, "l6_manifest": l6m,
            "carrier": carrier, "bitstream": car_bit, "image": a.image, "image_sha256": image_sha,
            "plan": session_plan, "round_plan": plan, "prediction": pred, "expected_genomes": expected_genomes,
            "signer": l3.SubprocessSigner(a.key, signer_user=a.signer_user),
            "provision_execute": True, "provision_ruling": a.provision_ruling,
            "token": secrets.token_hex(16), "seed_nonce": int(l6m["instrument"]["carrier"]["nonce_seed"], 16),
            "heartbeat_s": l6m["protocol"]["heartbeat_s"], "instrument": verified, "instrument_root": root}


def run_session(session, out_dir: Path, ruling: dict, cfg: dict) -> dict:
    """`zynq-psoracle/host/l6_runner.py:run_l6`, copied: the preamble, the console loop and
    the evidence files are the instrument's; the adjudication is this round's, over the
    files as written."""
    import board_session as bsn  # noqa: E402
    import l3_runner as l3  # noqa: E402
    import l5_notary as n  # noqa: E402
    import l5_runner as l5  # noqa: E402
    import l6_checks as lc  # noqa: E402
    import l6_console as lcs  # noqa: E402
    import l6_reader as lrd  # noqa: E402
    import l6_schedule as ls  # noqa: E402
    import l6_timing as lt  # noqa: E402
    import p2_observe as ob  # noqa: E402
    import p3_oracle as po  # noqa: E402
    import pcap_probe_runner as pr  # noqa: E402
    from validators import records  # noqa: E402
    manifest = cfg["carrier"]
    token = cfg["token"]
    plan = cfg["plan"]
    l6m = cfg["l6_manifest"]
    summary = {"tool": TOOL_VERSION, "ruling": ruling, "outcome": None, "token": token, "stages": {},
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
        preflight_rec = {"stage": "B_0_preflight", "CPU_CLK_CTRL": f"{cpu_clk:#010x}",
                         "addr": f"{l5.CPU_CLK_CTRL:#010x}", "verdict": "READ"}
        finish(preflight_rec, "B_0_preflight")
        summary["cpu_clk_ctrl"] = preflight_rec["CPU_CLK_CTRL"]
        fclk = ob.fclk0_mhz(*[session.read_word(a) for a in
                              (ob.IO_PLL_CTRL, ob.ARM_PLL_CTRL, ob.DDR_PLL_CTRL, ob.FPGA0_CLK_CTRL)])
        summary["fclk0"] = fclk
        summary["setup_load"] = session.load_carrier(
            bsn.SETUP_LOAD_CAPABILITY, cfg["bitstream"], manifest["bitstream_sha256"], out_dir / "ymodem.log")
        summary["provisioning"] = cfg["signer"].provision(
            execute=cfg["provision_execute"], ruling=cfg["provision_ruling"])
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
        finish({"stage": "B_1_identity_page", "words": [f"{w:08x}" for w in page],
                "flags": f"{plan['flags']:#x}", "verdict": "WRITTEN"}, "B_1_identity_page")
        session.begin_ymodem(l5.APP_LOAD_ADDR)
        session.finish_ymodem(cfg["image"], out_dir / "ymodem_app.log", cfg["image"].stat().st_size)
        summary["image_loaded"] = {"addr": f"{l5.APP_LOAD_ADDR:#010x}", "sha256": cfg["image_sha256"],
                                   "bytes": cfg["image"].stat().st_size}

        reader = lrd.L6LineReader(session.transport._serial)  # noqa: SLF001 — same handle, same epoch
        l5.send_raw_line(session.transport, f"go {l5.APP_LOAD_ADDR:#x}")
        t_go = time.monotonic()
        collector.last_heard = collector.clock()
        deadline = t_go + plan["session_timeout_s"]       # the evidenced window, from `go`

        def identity_check(ident: dict) -> list[str]:
            try:
                records.check_l6_identity(ident, plan["master_seed"], plan["mode"], l6m["operator"]["operator_data_sha256"],
                                          protocol=plan["protocol"], rec_retry_control=bool(plan["flags"] & ls.FLAG_REC_CONTROL),
                                          sign_retry_control=bool(plan["flags"] & ls.FLAG_SIGN_CONTROL))
            except records.RecordError as exc:
                return [str(exc)]
            return []
        console = lcs.ConsoleSession(token, collector, relay, timeline, plan["audit_seqs"], plan["crc_budget"], send,
                                     reader=reader, clock=time.monotonic, protocol=plan["protocol"],
                                     identity_check=identity_check, bad_frame_policy=lcs.BAD_FRAME_LEDGER,
                                     bad_frame_budget=plan["bad_frame_budget"])
        import l6_runner as l6  # noqa: E402  (the loop condition, verbatim)
        while l6.session_loop_continues(collector, console, time.monotonic(), deadline):
            for line, t_mono, t_wall in reader.poll():
                console.on_line(line, t_mono, t_wall)
            console.tick()
            if reader.saw_uboot_banner():
                collector.on_banner()
            collector.poll()
            time.sleep(0.02)
        if collector.epoch_end is None:
            collector._crash(f"the runner's own {plan['session_timeout_s']} s bound (the evidenced window) elapsed")

        (out_dir / "console.log").write_bytes(bytes(reader.raw))
        (out_dir / "console.ts.log").write_bytes(timeline.console_ts_log())
        pr.write_record(out_dir, "timeline", timeline.to_json())
        summary["epoch_end"] = collector.epoch_end
        summary["audits"] = len(collector.audits)
        summary["fragments"] = len(timeline.fragments)
        if collector.session_summary is None:
            gate_log = {"loop_records": collector.loop_records}
            audited_n, audited_src = lc.crash_audit_count(gate_log, collector.audits, __import__("p3_gate").load_manifest())
            summary["crash_summary_audit"] = {"audited": audited_n, "total": len(collector.loop_records), "source": audited_src}
            collector.session_summary = collector.crashed_summary(
                audit={"audited": audited_n, "total": len(collector.loop_records)},
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
        # ---- adjudicate, from the files as written ------------------------------------
        res = adj.adjudicate(out_dir, cfg["manifest"], cfg["round_plan"], cfg["prediction"],
                             instrument_root=cfg["instrument_root"], require_git=True)
        pr.write_record(out_dir, "adjudication", res)
        summary["adjudication"] = {k: res.get(k) for k in ("outcome", "findings", "known_answer", "claimb_result", "prediction_comparison")}
        summary["findings"] = res.get("findings") or []
        summary["outcome"] = res["outcome"]
    except l3.Stop as stop:
        summary["outcome"] = (f"KILL {stop.detail}" if stop.verdict == "KILL" else f"STOP {stop.verdict}: {stop.detail}")
    except pr.ProbeStop as stop:
        summary["outcome"] = f"STOP {stop.verdict}: {stop.detail}"
    except bsn.SessionRefusal as refusal:
        summary["outcome"] = f"REFUSED: {refusal}"
    except Exception as exc:  # noqa: BLE001 — any exception must still leave a summary
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ruling", type=Path, required=True)
    ap.add_argument("--provision-ruling", type=Path, default=None)
    ap.add_argument("--boundary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=inst.MANIFEST)
    ap.add_argument("--instrument-root", type=Path, default=inst.DEFAULT_ROOT)
    ap.add_argument("--image", type=Path, required=True, help="the pinned p3_app_l6.bin (gitignored in the instrument; hash-checked)")
    ap.add_argument("--key", type=Path, default=Path("/var/lib/p3signer/keys/K.bin"))
    ap.add_argument("--signer-user", default="p3signer")
    ap.add_argument("--port", default="/dev/ebaz-uart")
    a = ap.parse_args(argv)
    try:
        cfg = preflight(a)
    except (Refusal, ValueError, OSError, KeyError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — the instrument's own refusals (RecordError, SessionRefusal) land here
        print(f"REFUSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    import board_session as bsn  # noqa: E402
    import l3_runner as l3  # noqa: E402
    import pcap_probe_runner as pr  # noqa: E402
    consumed = pr.claim_ruling(a.ruling)
    a.out.mkdir(parents=True)
    l3._install_sigterm()
    outcome = "CRASHED before a summary was written"
    try:
        transport = bsn.SerialTransport(a.port)
        try:
            outcome = run_session(bsn.BoardSession(transport), a.out, cfg["ruling"], cfg)["outcome"]
        finally:
            transport.close()
    except bsn.SessionRefusal as exc:
        outcome = f"REFUSED: {exc}"
    finally:
        pr.record_outcome(consumed, outcome)
        if a.provision_ruling:
            l3._record_pk(a.provision_ruling, outcome)
    print(outcome, file=sys.stderr if outcome != "PASS" else sys.stdout)
    return 0 if outcome == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
