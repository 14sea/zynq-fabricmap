"""Stage 1 of the B1Q transport plan, executed: the tool proved against a pty, not the Zynq.

Three artifacts, all offline:
  * `profiles.json`   — the transmitted shape of all four recorded B1Q sessions, DERIVED from
                        the committed console logs (the plan's §2 table checked against bytes)
  * `generated.json`  — the shape of what the generator emits, against that measured shape
  * `pty_run.json`    — a bounded run over a pty pair: a clean control, then the same run with
                        a single byte removed, to show the tool reports the difference

No board, no port, no ruling, no attribution. A pty has no UART framing, parity or overrun,
so nothing here measures any link. Run from the repository root with `python3 -B`.
"""
import json
import os
import pty
import select
import sys
import time
import tty
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "host"))
import transport_rig as rig                                    # noqa: E402

OUT = Path(__file__).resolve().parent


def pump(data: bytes, drop_at: int | None = None) -> bytes:
    master, slave = pty.openpty()
    tty.setraw(master)
    tty.setraw(slave)
    os.set_blocking(master, False)
    os.set_blocking(slave, False)
    got, at, deadline = bytearray(), 0, time.monotonic() + 30.0
    try:
        while at < len(data) or time.monotonic() < deadline:
            if at < len(data):
                _, w, _ = select.select([], [master], [], 0.2)
                if w:
                    at += os.write(master, data[at:at + 4096])
            r, _, _ = select.select([slave], [], [], 0.05)
            if r:
                chunk = os.read(slave, 65536)
                if chunk:
                    got += chunk
                    continue
            if at >= len(data) and not r:
                break
    finally:
        os.close(master)
        os.close(slave)
    out = bytes(got)
    return out if drop_at is None else out[:drop_at] + out[drop_at + 1:]


# 1. the measured shape of every recorded session
profiles = {p.parent.name: rig.profile_from_log(p)
            for p in sorted((ROOT / "evidence/b1q").glob("b1q_17A6_*/console.log"))}
(OUT / "profiles.json").write_text(json.dumps(profiles, indent=1, sort_keys=True) + "\n")

# 2. what the generator emits, beside it
frames = rig.plan_frames(1)
by: dict = {}
for f in frames:
    e = by.setdefault(f.kind, {"count": 0, "min": f.bytes, "max": f.bytes, "max_abs_target_error": 0})
    e["count"] += 1
    e["min"], e["max"] = min(e["min"], f.bytes), max(e["max"], f.bytes)
    e["max_abs_target_error"] = max(e["max_abs_target_error"], abs(f.bytes - f.target_bytes))
generated = {"frames": len(frames), "bytes": len(rig.stream_bytes(frames)), "by_type": by,
             "measured_for_comparison": {k: {"count": c, "min": lo, "max": hi}
                                         for k, c, lo, hi in rig.SESSION_PROFILE},
             "note": "base64 grows four characters at a time, so a frame is the first reachable "
                     "length at or above the measured target; the error is bounded and recorded"}
(OUT / "generated.json").write_text(json.dumps(generated, indent=1, sort_keys=True) + "\n")

# 3. a bounded run over a pty pair — control, then one byte removed
rec = next(f for f in frames if f.kind == "REC")
control = rig.analyse(frames, pump(rig.stream_bytes(frames)))
damaged = rig.analyse(frames, pump(rig.stream_bytes(frames), drop_at=rec.offset + 11))
master, slave = pty.openpty()
counters = rig.read_icounters(slave)
os.close(master)
os.close(slave)
run = {"tool": "host/transport_rig.py", "self_sha256": rig.self_sha256(),
       "transport": "pty pair (raw), a separate traffic source — NOT a UART and NOT the Zynq",
       "control": {k: control[k] for k in ("clean", "frames_sent", "frames_delivered", "losses",
                                           "bytes_sent", "bytes_received", "divergence")},
       "one_byte_removed": {k: damaged[k] for k in ("clean", "frames_sent", "frames_delivered",
                                                    "losses", "missing", "divergence")},
       "counters_on_a_pty": counters,
       "scope": "the tool is proved end to end; no link property is measured, nothing is attributed, "
                "no condition of the plan's §3 was run (that is stage 2 and needs the owner's rig)"}
assert control["clean"] and not damaged["clean"]
assert damaged["divergence"]["frame_index"] == rec.index and damaged["divergence"]["offset_in_frame"] == 11
assert counters["available"] is False and counters["reason"]
(OUT / "pty_run.json").write_text(json.dumps(run, indent=1, sort_keys=True) + "\n")
print(json.dumps({"profiles": list(profiles), "generated_bytes": generated["bytes"],
                  "control_clean": control["clean"], "damaged_clean": damaged["clean"],
                  "localised_to": (damaged["divergence"]["frame_kind"], damaged["divergence"]["offset_in_frame"]),
                  "counters": counters["available"]}, indent=1))
