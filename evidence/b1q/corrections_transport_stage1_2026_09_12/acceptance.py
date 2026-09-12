"""The owner's stage-1 probes, re-expressed against the corrected rig — before beside after.

`evidence/b1q/review_transport_stage1_2026_09_12/probe_rig.py` records the DEFECTIVE answers at
`4528ef8` in `observed.json`, deliberately, "so a corrected implementation can be compared".
Its own calls cannot simply be re-run: `Run.execute` no longer takes two bare callables, because
the missing execution contract was P2-3. This runs the same probes through the corrected public
API and prints each observation beside theirs.

Offline only: no serial device, no manifest, pin, instrument or ruling is touched; the counter
fd is never a real device. Run from the repository root with `python3 -B`.
"""
import base64
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "host"))
import transport_rig as rig                                        # noqa: E402

OBSERVED = json.loads((ROOT / "evidence/b1q/review_transport_stage1_2026_09_12/observed.json").read_text())
RUN = "acceptance"
frames = rig.plan_frames(RUN, 0)
wire = rig.stream_bytes(frames)
token = rig.token_for(RUN, 0)
rec = next(f for f in frames if f.kind == "REC")


def lines_of(kind, data):
    out, at = [], 0
    for ln in data.split(b"\n")[:-1]:
        if ln.startswith(b"P3L5 " + kind + b" "):
            out.append(at)
        at += len(ln) + 1
    return out


def whole(mutate=None, fail_after=None):
    state = {"buf": bytearray(), "reads": 0}

    def write(data):
        if data.startswith(b"P3L5 "):
            state["buf"] += data
        return len(data)

    def read(_t):
        state["reads"] += 1
        if fail_after is not None and state["reads"] > fail_after:
            raise OSError("synthetic detach")
        if len(state["buf"]) < 98000:
            return b""
        out, state["buf"] = bytes(state["buf"]), bytearray()
        return mutate(out) if mutate else out
    return rig.callable_port("double", write, read)


def damage(n):
    def mutate(data):
        buf = bytearray(data)
        for at in lines_of(b"REC", data)[:n]:
            buf[at + 20] ^= 1
        return bytes(buf)
    return mutate


out = {"provenance": rig.provenance(), "cases": {}}


def case(name, before, after):
    out["cases"][name] = {"observed_at_4528ef8": before, "now": after}


# P2-1 the loss unit and the denominator
one = rig.analyse(frames, damage(1)(wire), token)
case("one_corrupted_frame_losses", OBSERVED["one_corrupted_frame"]["losses"], one["losses"])
two = rig.Run("two damaged", repetitions=1, tx_during_rx=False, run_id=RUN).execute(whole(damage(2)), sleep=lambda s: None)
case("two_corrupted_frames",
     {"losses": OBSERVED["two_corrupted_frames_run"]["losses"], "stopped": OBSERVED["two_corrupted_frames_run"]["stopped"]},
     {"losses": two["losses"], "stopped": two["stopped"]})
silence = rig.Run("silence", repetitions=1, tx_during_rx=False, run_id=RUN).execute(whole(lambda d: b""), sleep=lambda s: None)
case("silence_denominator",
     {"denominator_bytes": OBSERVED["silence_run"]["denominator_bytes"],
      "losses_per_100k_bytes": OBSERVED["silence_run"]["losses_per_100k_bytes"],
      "losses": OBSERVED["silence_run"]["losses"]},
     {"denominator_bytes": silence["denominator_bytes"], "losses_per_100k_bytes": silence["losses_per_100k_bytes"],
      "losses": silence["losses"], "denominator": silence["denominator"]})

# P2-2 delivery needs the bytes, and the repetition's own epoch
parsed = rig.l5.parse_line(rec.line.decode())
payload = bytearray(base64.urlsafe_b64decode(parsed["payload"]))
payload[-1] ^= 1
altered = rig.l5.build_line(rec.kind, rec.seq, parsed["token"], base64.urlsafe_b64encode(payload).decode()).encode()
foreign = rig.analyse(frames, wire[:rec.offset] + altered + wire[rec.offset + rec.bytes:], token)
case("valid_crc_over_bytes_we_did_not_send",
     {"frames_delivered": OBSERVED["foreign_payload_known_index"]["frames_delivered"],
      "losses": OBSERVED["foreign_payload_known_index"]["losses"]},
     {"frames_delivered": foreign["frames_delivered"], "losses": foreign["losses"],
      "damaged": foreign["damaged"], "defects_by_kind": foreign["defects_by_kind"]})

kept = {"bytes": None}


def replay(data):
    if kept["bytes"] is None:
        kept["bytes"] = data
    return kept["bytes"]


rep = rig.Run("replay", repetitions=2, tx_during_rx=False, run_id=RUN).execute(whole(replay), sleep=lambda s: None)
case("stale_repetition_replayed",
     {"results_clean": OBSERVED["repetition_replay"]["results_clean"],
      "both_writes_equal": OBSERVED["repetition_replay"]["both_writes_equal"]},
     {"results_clean": [r["clean"] for r in rep["repetition_results"]],
      "second_losses": rep["repetition_results"][1]["losses"],
      "both_streams_equal": rig.stream_bytes(rig.plan_frames(RUN, 0)) == rig.stream_bytes(rig.plan_frames(RUN, 1))})

try:
    rig.Run("short write", repetitions=1, tx_during_rx=False).execute(
        rig.callable_port("short", lambda d: 0, lambda t: b""), sleep=lambda s: None)
    short = "ACCEPTED — still a defect"
except rig.RigError as exc:
    short = f"REFUSED: {exc}"
case("short_write", {"clean_result_reported": OBSERVED["short_write_ignored"]}, short)

# P2-3 the execution contract
now = [0.0]
events = []


def trace_write(data):
    events.append({"op": "write", "t": now[0], "bytes": len(data),
                   "kind": "source stream" if data.startswith(b"P3L5 ") else "host command"})
    return len(data)


def trace_read(_t):
    events.append({"op": "read", "t": now[0]})
    return b""


port = rig.callable_port("trace", trace_write, trace_read)
timed = rig.Run("trace", repetitions=1, seconds=0.1, tx_during_rx=True, run_id=RUN).execute(
    port, sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0])
sched: dict = {}
for s in rig.host_schedule(frames):
    k = s["line"].split(b" ")[0].decode()
    sched[k] = sched.get(k, 0) + 1
# and the same trace with a deadline that does not bite, to show the whole contract
now2 = [0.0]
events2 = []


def trace2_write(data):
    events2.append({"op": "write", "t": now2[0], "bytes": len(data),
                    "kind": "source stream" if data.startswith(b"P3L5 ") else "host command"})
    return len(data)


def trace2_read(_t):
    events2.append({"op": "read", "t": now2[0]})
    return b""


full = rig.Run("trace", repetitions=1, seconds=1e6, tx_during_rx=True, run_id=RUN).execute(
    rig.callable_port("trace", trace2_write, trace2_read),
    sleep=lambda s: now2.__setitem__(0, now2[0] + s), clock=lambda: now2[0])
case("driver_contract",
     {"source_writes": 1, "reads": 1, "after_frame_used": False,
      "host_command_counts": OBSERVED["driver_trace"]["host_command_counts"],
      "elapsed_vs_limit": [OBSERVED["driver_trace"]["elapsed"], OBSERVED["driver_trace"]["declared_limit"]],
      "stopped": OBSERVED["driver_trace"]["stopped"]},
     {"source_writes": sum(1 for e in events2 if e["op"] == "write" and e["kind"] == "source stream"),
      "host_writes": sum(1 for e in events2 if e["op"] == "write" and e["kind"] == "host command"),
      "reads": sum(1 for e in events2 if e["op"] == "read"),
      "after_frame_used": True, "host_command_counts": sched,
      "interleaved": [e["kind"] if e["op"] == "write" else "read" for e in events2[:6]],
      "stopped": full["stopped"]})
case("the_deadline_bounds_the_operations",
     {"declared_limit_s": OBSERVED["driver_trace"]["declared_limit"],
      "elapsed_s": OBSERVED["driver_trace"]["elapsed"], "stopped": OBSERVED["driver_trace"]["stopped"]},
     {"declared_limit_s": 0.1, "elapsed_s": now[0], "stopped": timed["stopped"],
      "source_writes_before_the_stop": sum(1 for e in events if e["op"] == "write" and e["kind"] == "source stream"),
      "note": "the deadline is checked around every operation, so the run stops INSIDE the repetition; a scheduled gap already begun still completes, so the bound is the limit plus at most one gap"})

# P2-4 the error path
with tempfile.TemporaryDirectory(prefix="rig_acceptance_") as td:
    calls = []
    real = rig.read_icounters
    rig.read_icounters = lambda fd: (calls.append(fd), {"available": False, "reason": "offline double"})[1]
    try:
        rig.Run("detach", repetitions=3, tx_during_rx=False, run_id=RUN).execute(
            whole(fail_after=400), fd=123, out_dir=Path(td), sleep=lambda s: None)
        err = None
    except rig.RigError as exc:
        err = exc
    finally:
        rig.read_icounters = real
    on_disk = json.loads((Path(td) / "run.json").read_text())
    captures = [c["capture"] for c in on_disk["captures"]]
    readable = all((Path(td) / c).is_file() for c in captures) and \
        all((Path(td) / c.replace("capture", "events").replace(".bin", ".json")).is_file() for c in captures)
    case("error_path",
         OBSERVED["error_path"],
         {"error": str(err), "original_error_preserved": type(err.__cause__).__name__,
          "counter_samples": len(calls), "returned_result": err.result is not None,
          "exported_to_disk": True, "captures": len(captures), "capture_files_readable": readable,
          "completed_repetitions_on_disk": on_disk["repetitions_run"],
          "counters_after_available": on_disk["counters_after"]["available"]})

# P3 resynchronisation
at = rec.offset + 100
ins = rig.analyse(frames, wire[:at] + b"\n" + wire[at:], token)
case("inserted_newline",
     {"bytes_to_resync": OBSERVED["inserted_newline"]["divergence"]["bytes_to_resync"],
      "losses": OBSERVED["inserted_newline"]["losses"]},
     {"bytes_to_next_newline": ins["divergence"]["bytes_to_next_newline"],
      "resynchronised_at": ins["divergence"]["resynchronised_at"], "losses": ins["losses"]})

# P2-5 the exposure units
sys.path.insert(0, str(ROOT / "host"))
import b2_runner as rn                                             # noqa: E402
m = json.loads((ROOT / "manifests/b2_manifest.json").read_text())
case("b2q_exposure_units",
     {"claimed": "20 B2Q records vs 302 B1Q frames — 'a much shorter exposure'"},
     {"b2q_expected_frames": rn.qualification_session_plan(m)["expected_frames"]["total"],
      "b1q_transmitted_frames": rig.FRAMES_PER_PROFILE,
      "withdrawn": True,
      "note": "planning arithmetic, not an observed run; frames, bytes, duration, controls and "
              "retries must be compared in like units before any disposition"})

assert out["cases"]["one_corrupted_frame_losses"]["now"] == 1
assert out["cases"]["two_corrupted_frames"]["now"]["losses"] == 2
assert "stop rule" not in out["cases"]["two_corrupted_frames"]["now"]["stopped"]
assert out["cases"]["silence_denominator"]["now"]["denominator_bytes"] == 0
assert out["cases"]["silence_denominator"]["now"]["losses_per_100k_bytes"] is None
assert out["cases"]["valid_crc_over_bytes_we_did_not_send"]["now"]["losses"] == 1
assert out["cases"]["stale_repetition_replayed"]["now"]["results_clean"] == [True, False]
assert out["cases"]["short_write"]["now"].startswith("REFUSED")
assert out["cases"]["driver_contract"]["now"]["source_writes"] == 302
assert out["cases"]["driver_contract"]["now"]["host_writes"] == 125
assert out["cases"]["driver_contract"]["now"]["reads"] > 302
assert out["cases"]["the_deadline_bounds_the_operations"]["now"]["elapsed_s"] <= 0.1 + rig.TX_GAP_MEDIAN_S
assert "deadline" in out["cases"]["the_deadline_bounds_the_operations"]["now"]["stopped"]
assert out["cases"]["error_path"]["now"]["counter_samples"] == 2
assert out["cases"]["error_path"]["now"]["returned_result"] is True
assert out["cases"]["inserted_newline"]["now"]["losses"] == 1
assert out["cases"]["inserted_newline"]["now"]["resynchronised_at"]["bytes_after_first_divergence"] > 1
assert out["cases"]["b2q_exposure_units"]["now"]["b2q_expected_frames"] == 543
print(json.dumps(out, indent=2, sort_keys=True))
