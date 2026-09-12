"""The owner's driver probes, re-expressed against the corrected rig — before beside after.

`evidence/b1q/review_transport_driver_2026_09_12/probe_driver.py` records the defective answers
at `146e60a` in `observed.json`. Its calls cannot all be re-run unchanged: `analyse` now takes an
echo LEDGER with multiplicity rather than a set, and a `Port` write takes the remaining budget —
both of which were the findings. This runs the same probes through the corrected public API.

Offline only: no serial device, no manifest, pin, instrument or ruling is touched. The serial
probe installs a fake module and opens nothing. Run from the repository root with `python3 -B`.
"""
import json
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "host"))
import transport_rig as rig                                        # noqa: E402

OBSERVED = json.loads((ROOT / "evidence/b1q/review_transport_driver_2026_09_12/observed.json").read_text())
RUN = "acceptance"
frames = rig.plan_frames(RUN, 0)
wire = rig.stream_bytes(frames)
token = rig.token_for(RUN, 0)
echo = rig.host_schedule(frames)[0]["line"]

out = {"provenance": rig.provenance(), "cases": {}}


def case(name, before, after):
    out["cases"][name] = {"observed_at_146e60a": before, "now": after}


def brief(r):
    return {k: r[k] for k in ("clean", "frames_delivered", "losses", "host_echo_lines", "defects_by_kind")}


def local_port(fail=False):
    st = {"buffer": b"", "writes": 0, "accepted_bytes": 0, "read_bytes": 0, "reads": 0}

    def write(data, timeout=None):
        st["writes"] += 1
        st["accepted_bytes"] += len(data)
        st["buffer"] += data
        return len(data)

    def read(_t):
        st["reads"] += 1
        if fail and st["reads"] == 2:
            raise OSError("primary synthetic detach")
        b, st["buffer"] = st["buffer"], b""
        st["read_bytes"] += len(b)
        return b
    return rig.callable_port("memory loopback", write, read, takes_timeout=True), st


# ---- P2-1 delivery and echo ------------------------------------------------
case("missing_final_newline",
     {k: OBSERVED["missing_final_newline"][k] for k in ("frames_delivered", "losses", "clean")},
     brief(rig.analyse(frames, wire[:-1], token)))
case("one_expected_echo",
     {k: OBSERVED["one_expected_echo_positive"][k] for k in ("clean", "host_echo_lines", "losses")},
     brief(rig.analyse(frames, wire + echo, token, echo_ledger={echo: 1}, echo_allowed=True)))
case("the_same_echo_a_hundred_times",
     {k: OBSERVED["duplicate_echo"][k] for k in ("clean", "host_echo_lines", "losses")},
     brief(rig.analyse(frames, wire + echo * 100, token, echo_ledger={echo: 1}, echo_allowed=True)))
case("blank_lines_with_an_echo",
     {k: OBSERVED["unsent_blank_lines_with_echo"][k] for k in ("clean", "host_echo_lines")},
     brief(rig.analyse(frames, wire + b"\n" * 100 + echo, token, echo_ledger={echo: 1}, echo_allowed=True)))
case("an_echo_on_a_topology_that_does_not_echo",
     {"not probed at 146e60a": "the echo list was supplied regardless of topology"},
     brief(rig.analyse(frames, wire + echo, token, echo_ledger={echo: 1}, echo_allowed=False)))

with tempfile.TemporaryDirectory(prefix="acceptance_driver_") as temp:
    temp = Path(temp)
    # ---- P2-2/P2-3 the deadline --------------------------------------------
    now, events, pending = [0.0], [], [b""]

    def write(data, timeout=None):
        events.append({"op": "write", "t": now[0], "source": data.startswith(b"P3L5 " + b"IDENT"),
                       "bytes": len(data), "timeout": timeout})
        pending[0] += data
        return len(data)

    def read(timeout):
        events.append({"op": "read", "t": now[0], "timeout": timeout})
        now[0] += timeout
        b, pending[0] = pending[0], b""
        return b
    p = rig.callable_port("timed loopback", write, read, takes_timeout=True)
    bounded = rig.Run("deadline", repetitions=1, seconds=0.01, run_id=RUN).execute(
        p, out_dir=temp / "deadline", clock=lambda: now[0],
        sleep=lambda t: now.__setitem__(0, now[0] + t))
    case("deadline",
         {"declared_limit_s": 0.01, "elapsed_s": OBSERVED["deadline"]["elapsed"],
          "frames_sent": OBSERVED["deadline"]["result"]["frames_sent"],
          "bytes_sent": OBSERVED["deadline"]["result"]["bytes_sent"],
          "losses": OBSERVED["deadline"]["result"]["losses"]},
         {"declared_limit_s": 0.01, "elapsed_s": now[0], "events": len(events),
          "every_wait_within_budget": all(e.get("timeout") is None or e["timeout"] <= 0.01 for e in events),
          "frames_planned": bounded["frames_planned"], "frames_accepted": bounded["frames_accepted"],
          "frames_sent": bounded["frames_sent"], "bytes_sent": bounded["bytes_sent"],
          "losses": bounded["losses"], "censored_in_flight": bounded["censored_in_flight"],
          "incomplete": bounded["incomplete"], "completed_exposure": bounded["completed_exposure"],
          "stopped": bounded["stopped"]})

    # ---- P2-2 the partial capture ------------------------------------------
    p, state = local_port(fail=True)
    try:
        rig.Run("detach", repetitions=1, tx_during_rx=False, run_id=RUN).execute(
            p, out_dir=temp / "detach", sleep=lambda _: None)
    except rig.RigError as exc:
        on_disk = json.loads((temp / "detach/run.json").read_text())
        case("partial_detach",
             {"actual_accepted_bytes": OBSERVED["partial_detach"]["actual"]["accepted_bytes"],
              "raw_capture_bytes": OBSERVED["partial_detach"]["raw_capture_bytes"],
              "summary": {k: OBSERVED["partial_detach"]["result"][k]
                          for k in ("frames_sent", "bytes_sent", "denominator_bytes", "losses", "repetitions_run")}},
             {"actual_accepted_bytes": state["accepted_bytes"],
              "raw_capture_bytes": (temp / "detach/capture_000.bin").stat().st_size,
              "summary": {k: on_disk[k] for k in ("frames_planned", "frames_accepted", "frames_sent",
                                                  "bytes_sent", "denominator_bytes", "losses",
                                                  "censored_in_flight", "repetitions_run",
                                                  "incomplete", "completed_exposure")},
              "error": str(exc)})

    # ---- P2-5 one export component at a time --------------------------------
    real_text = Path.write_text

    def failing_events(path, data, *a, **k):
        if path.name == "events_000.json":
            raise OSError("injected events write failure")
        return real_text(path, data, *a, **k)
    for fail in (False, True):
        p, _ = local_port(fail=fail)
        d = temp / ("export_error_with_detach" if fail else "export_error_clean")
        with patch.object(Path, "write_text", failing_events):
            try:
                result = rig.Run("export", repetitions=1, tx_during_rx=False, run_id=RUN).execute(
                    p, out_dir=d, sleep=lambda _: None)
                err = None
            except rig.RigError as exc:
                result, err = exc.result, str(exc)
        case(d.name,
             {"files": OBSERVED[d.name]["files"], "exception": OBSERVED[d.name]["exception"],
              "export_error": OBSERVED[d.name]["result"].get("export_error"),
              "stopped": OBSERVED[d.name]["result"]["stopped"]},
             {"files": sorted(f.name for f in d.iterdir()), "exception": err,
              "export_complete": result["export_complete"], "export_errors": result["export_errors"],
              "stopped": result["stopped"], "completed_exposure": result["completed_exposure"]})

    # ---- P2-5 provenance ----------------------------------------------------
    real_bytes = Path.read_bytes
    framing = Path(rig.l5.__file__)

    def inaccessible(path):
        if path == framing:
            raise OSError("injected provenance read failure")
        return real_bytes(path)
    p, _ = local_port(fail=True)
    d = temp / "provenance_error"
    with patch.object(Path, "read_bytes", inaccessible):
        try:
            rig.Run("provenance", repetitions=1, tx_during_rx=False).execute(
                p, out_dir=d, sleep=lambda _: None)
            got = {"raised": None}
        except Exception as exc:                                   # noqa: BLE001
            got = {"raised": type(exc).__name__, "error": str(exc),
                   "primary_cause": type(exc.__cause__).__name__ if exc.__cause__ else None,
                   "primary_error": str(exc.__cause__) if exc.__cause__ else None,
                   "has_result": getattr(exc, "result", None) is not None,
                   "directory_exists": d.exists(),
                   "provenance_recorded": json.loads((d / "run.json").read_text())["provenance"]}
    case("provenance_error", OBSERVED["provenance_error"], got)

# ---- P2-3 the serial constructor -------------------------------------------
seen = {}


class SerialDouble:
    def __init__(self, *args, **kwargs):
        seen.update({"args": list(args), "kwargs": kwargs})
        self.write_timeout = None
        self.timeout = None

    def write(self, data):
        seen["write_timeout_at_write"] = self.write_timeout
        return len(data)

    def read(self, size):
        return b""

    def fileno(self):
        return 123


with patch.dict(sys.modules, {"serial": types.SimpleNamespace(Serial=SerialDouble)}):
    port = rig.serial_port("OFFLINE-NOT-A-DEVICE")
    port.write(b"x", 0.25)
case("serial_constructor", OBSERVED["serial_constructor"], seen)

# ---- P2-4 the overlap and the traffic shape --------------------------------
now, busy, checks = [0.0], [0.0], []


def source_write(data, timeout=None):
    busy[0] = now[0] + len(data) * rig.BYTE_TIME_S
    return len(data)


def host_write(data, timeout=None):
    checks.append(now[0] < busy[0])
    return len(data)


source = rig.callable_port("source", source_write, lambda t: b"", takes_timeout=True)
host = rig.callable_port("host", host_write, lambda t: b"", takes_timeout=True)
rep = rig.Repetition(index=0, frames=frames)
rig.Driver(source, host, source, pace=True, sleep=lambda t: now.__setitem__(0, now[0] + t),
           clock=lambda: now[0]).run(rep, 1e6)
checks_no_tx = []
rep2 = rig.Repetition(index=0, frames=frames)
now[0] = 0.0
rig.Driver(source, host, source, tx_during_rx=False, pace=True,
           sleep=lambda t: now.__setitem__(0, now[0] + t), clock=lambda: now[0]).run(rep2, 1e6)
case("paced_overlap",
     OBSERVED["paced_overlap"],
     {"host_writes": len(checks), "host_writes_during_source_rx": sum(checks),
      "driver_recorded_overlap": sum(1 for o in rep.overlap if o["overlapping"]),
      "no_tx_control_host_writes": len(rep2.overlap)})
case("host_traffic_shape",
     {"min": OBSERVED["host_schedule_lengths"]["min"], "max": OBSERVED["host_schedule_lengths"]["max"],
      "note": "plain COMMAND seq lines, 9-14 bytes"},
     {**rig.host_traffic_shape(frames),
      "min": min(len(s["line"]) for s in rig.host_schedule(frames)),
      "max": max(len(s["line"]) for s in rig.host_schedule(frames)),
      "note": "real rel-v4 frames; SIGNOK carries the archived sign_reply shape"})

c = out["cases"]
assert c["missing_final_newline"]["now"]["frames_delivered"] == 301
assert c["missing_final_newline"]["now"]["losses"] == 1
assert c["one_expected_echo"]["now"]["clean"] is True
assert c["the_same_echo_a_hundred_times"]["now"]["clean"] is False
assert c["blank_lines_with_an_echo"]["now"]["clean"] is False
assert c["an_echo_on_a_topology_that_does_not_echo"]["now"]["clean"] is False
assert c["deadline"]["now"]["elapsed_s"] <= 0.01
assert c["deadline"]["now"]["every_wait_within_budget"]
assert c["deadline"]["now"]["losses"] == 0 and c["deadline"]["now"]["frames_planned"] == 302
assert c["deadline"]["now"]["completed_exposure"] is False
assert c["partial_detach"]["now"]["summary"]["denominator_bytes"] == 1048
assert c["partial_detach"]["now"]["summary"]["bytes_sent"] > 0
assert "run.json" in c["export_error_clean"]["now"]["files"]
assert c["export_error_clean"]["now"]["export_complete"] is False
assert "run.json" in c["export_error_with_detach"]["now"]["files"]
assert c["provenance_error"]["now"]["primary_cause"] == "OSError"
assert "primary synthetic detach" in c["provenance_error"]["now"]["primary_error"]
assert c["provenance_error"]["now"]["has_result"] and c["provenance_error"]["now"]["directory_exists"]
assert c["serial_constructor"]["now"]["kwargs"]["write_timeout"] == rig.WRITE_TIMEOUT_S
assert c["serial_constructor"]["now"]["write_timeout_at_write"] == 0.25
assert c["paced_overlap"]["now"]["host_writes_during_source_rx"] > 100
assert c["paced_overlap"]["now"]["no_tx_control_host_writes"] == 0
assert c["host_traffic_shape"]["now"]["bytes"] > 10000
print(json.dumps(out, indent=2, sort_keys=True))
