"""The offline acceptance run, through the PRODUCTION entry point, over a pty pair.

Superseded scope (the owner's review of 2026-09-12): this is the SOFTWARE half of the plan's
stage 1. The plan also requires a physical acceptance on a separate serial device or a physical
self-loopback, which has not happened and which a pseudo-terminal cannot replace.

Four artifacts, all offline:
  * `profiles.json`  — the transmitted shape of all four recorded B1Q sessions, derived from the
                       committed console logs (the plan's §2 table checked against bytes)
  * `schedule.json`  — the host's actual schedule and tx→rx gaps, derived from the clean
                       session's own timeline, which is where the rig's rule comes from
  * `generated.json` — the shape of what the generator emits, beside that measured shape
  * `run_tx.json` / `run_notx.json` — `Run.execute` over a raw pty for BOTH §3 TX conditions,
                       with the raw capture and per-read events exported beside them

No board, no serial device, no ruling, no attribution. Run from the repository root: python3 -B.
"""
import json
import os
import pty
import select
import shutil
import sys
import tty
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "host"))
import transport_rig as rig                                        # noqa: E402

OUT = Path(__file__).resolve().parent


def pty_port():
    master, slave = pty.openpty()
    tty.setraw(master)
    tty.setraw(slave)
    os.set_blocking(master, False)
    os.set_blocking(slave, False)

    def write(data):
        sent = 0
        while sent < len(data):
            _, w, _ = select.select([], [master], [], 1.0)
            if not w:
                break
            sent += os.write(master, data[sent:sent + 2048])
        return sent

    def read(timeout):
        r, _, _ = select.select([slave], [], [], timeout)
        if not r:
            return b""
        try:
            return os.read(slave, 65536)
        except (BlockingIOError, OSError):
            return b""
    return rig.callable_port("pty", write, read, fd=slave), (master, slave)


# 1. the measured shape of every recorded session
profiles = {p.parent.name: rig.profile_from_log(p)
            for p in sorted((ROOT / "evidence/b1q").glob("b1q_17A6_*/console.log"))}
(OUT / "profiles.json").write_text(json.dumps(profiles, indent=1, sort_keys=True) + "\n")

# 2. the host schedule the rig's rule is derived from
schedule = rig.host_schedule_from_timeline(ROOT / rig.TIMELINE_SOURCE)
frames = rig.plan_frames("proof", 0)
emitted: dict = {}
for s in rig.host_schedule(frames):
    k = s["line"].split(b" ")[0].decode()
    emitted[k] = emitted.get(k, 0) + 1
schedule["the_rigs_schedule_by_that_rule"] = {"total": sum(emitted.values()), "by_type": emitted}
(OUT / "schedule.json").write_text(json.dumps(schedule, indent=1, sort_keys=True) + "\n")

# 3. what the generator emits, beside the measured shape
by: dict = {}
for f in frames:
    e = by.setdefault(f.kind, {"count": 0, "min": f.bytes, "max": f.bytes, "max_abs_target_error": 0})
    e["count"] += 1
    e["min"], e["max"] = min(e["min"], f.bytes), max(e["max"], f.bytes)
    e["max_abs_target_error"] = max(e["max_abs_target_error"], abs(f.bytes - f.target_bytes))
(OUT / "generated.json").write_text(json.dumps(
    {"frames": len(frames), "bytes": len(rig.stream_bytes(frames)), "by_type": by,
     "measured_for_comparison": {k: {"count": c, "min": lo, "max": hi} for k, c, lo, hi in rig.SESSION_PROFILE},
     "note": "base64 grows four characters at a time, so a frame is the first reachable length at or "
             "above the measured target; the error is bounded and recorded"}, indent=1, sort_keys=True) + "\n")

# 4. the production entry point, over a pty, for both TX conditions
for tx, name in ((True, "run_tx"), (False, "run_notx")):
    d = OUT / name
    shutil.rmtree(d, ignore_errors=True)
    port, fds = pty_port()
    try:
        run = rig.Run(f"pty tx_during_rx={tx}", repetitions=1, seconds=120.0, tx_during_rx=tx)
        result = run.execute(port, fd=port.fileno(), out_dir=d, sleep=lambda s: None, read_timeout=0.05)
    finally:
        for fd in fds:
            os.close(fd)
    rep = result["repetition_results"][0]
    assert rep["ended"] == "complete" and result["losses"] == 0, rep
    assert rep["reads"] > 10 and result["denominator"] == "received bytes"
    assert result["counters_after"]["available"] is False and result["counters_after"]["reason"]
    print(json.dumps({"condition": name, "tx_during_rx": tx, "frames": rep["frames_sent"],
                      "delivered": rep["frames_delivered"], "losses": result["losses"],
                      "reads": rep["reads"], "denominator_bytes": result["denominator_bytes"],
                      "counters": result["counters_after"]["available"],
                      "exported": str(d.relative_to(ROOT))}, sort_keys=True))
