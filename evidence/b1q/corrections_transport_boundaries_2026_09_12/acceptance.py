#!/usr/bin/env python3
"""The owner's boundary probes, re-run against the corrected rig — before beside after.

`evidence/b1q/review_transport_boundaries_2026_09_12/probe_boundaries.py` records the defective
answers at `38c91b0` in `observed.json`. Its structure is kept and its calls run unchanged
through the public API; what is added is the assertion the review asks for on each — the
negative controls now FAIL LOUDLY if the old answer comes back, and the positive controls
(the intact stream, the two-repetition zero-loss run) must still pass.

Offline only: no serial device, no manifest, pin, instrument or ruling is touched. Temporary
export directories only. Run from the repository root with `python3 -B`.
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "host"))
import transport_rig as rig                                        # noqa: E402

OBSERVED = json.loads((ROOT / "evidence/b1q/review_transport_boundaries_2026_09_12/observed.json").read_text())
out = {"provenance": rig.provenance(), "cases": {}}


def case(name, before, after):
    out["cases"][name] = {"observed_at_38c91b0": before, "now": after}


frames = rig.plan_frames("boundary-review", 0)
clean = rig.analyse(frames, rig.stream_bytes(frames))
assert clean["clean"] and clean["losses"] == 0                      # positive control, unchanged
case("positive_stream", OBSERVED["positive_stream"], {k: clean[k] for k in ("clean", "losses", "frames_delivered")})

# ---- P2-1 a writer that accepted bytes, then failed internally ------------
calls, accepted = [], bytearray()


def writer(data, timeout=None):
    calls.append(timeout)
    accepted.extend(data)
    if len(calls) == 1:
        raise TypeError("internal writer failure after accepting bytes")
    return len(data)


port = rig.callable_port("side-effecting writer", writer, lambda t: b"", takes_timeout=True)
try:
    n = port.write(b"abc", 0.25)
    got = {"returned_count": n, "exception": None}
except Exception as exc:                                           # noqa: BLE001
    got = {"exception": f"{type(exc).__name__}: {exc}"}
got.update({"timeouts_received": list(calls), "actual_bytes_accepted": accepted.decode()})
assert got["exception"] == "TypeError: internal writer failure after accepting bytes", got
assert got["timeouts_received"] == [0.25] and got["actual_bytes_accepted"] == "abc", got
case("typeerror_writer", OBSERVED["typeerror_writer"], got)

# the two supported signatures, each called once as declared; a contradicting declaration refused
one_arg, two_arg = [], []
p1 = rig.callable_port("one", lambda d: one_arg.append(d) or len(d), lambda t: b"", takes_timeout=False)
p2 = rig.callable_port("two", lambda d, t: two_arg.append((d, t)) or len(d), lambda t: b"", takes_timeout=True)
p1.write(b"xy", 0.5)
p2.write(b"xyz", 0.5)
assert one_arg == [b"xy"] and two_arg == [(b"xyz", 0.5)]
try:
    rig.callable_port("lies", lambda d: len(d), lambda t: b"", takes_timeout=True)
    refused = None
except rig.RigError as exc:
    refused = str(exc)
assert refused and "declared to take a timeout" in refused
case("writer_contracts", {"not probed at 38c91b0": "the contract was discovered by catching TypeError"},
     {"one_arg_calls": [b.decode() for b in one_arg], "two_arg_calls": [[b.decode(), t] for b, t in two_arg],
      "contradicting_declaration": refused})

# ---- P2-2 the same corrupted complete line, normal completion vs cutoff --
one = frames[:1]
bad = bytearray(one[0].line)
bad[60] ^= 1
for censor in (False, True):
    r = rig.analyse(one, bytes(bad), censor_tail=censor)
    key = "crc_with_cutoff" if censor else "crc_without_cutoff"
    now = {k: r[k] for k in ("losses", "censored", "missing", "defects_by_kind", "bytes_received")}
    now.update({"unresolved": r["unresolved"], "observed": r["observed"], "observed_damaged": r["observed_damaged"]})
    assert now["losses"] == 1 and now["censored"] == [] and now["observed"] == [0], now
    case(key, OBSERVED[key], now)
silent = rig.analyse(one, b"", censor_tail=True)
now = {k: silent[k] for k in ("losses", "censored", "defects_by_kind")}
assert now == {"losses": 0, "censored": [0], "defects_by_kind": {}}, now   # still distinguishable
case("truly_in_flight_control", OBSERVED["truly_in_flight_control"], now)

# the review's further cases under the same cutoff
five = frames[:5]
stream2 = rig.stream_bytes(frames[:2])
later = rig.analyse(frames[:8], rig.stream_bytes(frames[:3]) + rig.stream_bytes([frames[4]])[:-3] + b"X\n",
                    censor_tail=True)
partial = rig.analyse(five, stream2 + frames[2].line[:-10], censor_tail=True)
garbage = rig.analyse(five, stream2 + b"~" * 300 + b"\n", censor_tail=True)
assert (later["losses"], later["missing"], later["censored"], later["unresolved"]) == (2, [3, 4], [5, 6, 7], []), later
assert (partial["losses"], partial["censored"], partial["unresolved"]) == (0, [2, 3, 4], []), partial
assert (garbage["losses"], garbage["censored"], garbage["unresolved"]) == (0, [], [2, 3, 4]), garbage
case("cutoff_boundaries", {"not probed at 38c91b0": "the frontier was max(delivered) in every case"},
     {"later_damaged_arrival": {k: later[k] for k in ("losses", "missing", "censored", "unresolved")},
      "genuinely_partial_line": {k: partial[k] for k in ("losses", "censored", "unresolved")} | {"cutoff": partial["cutoff"]},
      "unidentifiable_damage": {k: garbage[k] for k in ("losses", "censored", "unresolved")} | {"cutoff": garbage["cutoff"]}})


# ---- P2-3 the terminal state, through the production Run -----------------
def loopback(damage_first=0):
    state = {"queued": bytearray(), "writes": 0}

    def write(data, timeout=None):
        state["writes"] += 1
        if state["writes"] <= damage_first:
            data = bytearray(data)
            data[50] ^= 1
        state["queued"].extend(data)
        return len(data)

    def read(timeout):
        data = bytes(state["queued"])
        state["queued"].clear()
        return data
    return rig.callable_port("memory loopback", write, read, takes_timeout=True), state


KEYS = ("repetitions_run", "stopped", "losses", "denominator_bytes", "losses_per_100k_bytes",
        "completed_exposure", "incomplete", "error", "export_complete")


def summary(r):
    return {k: r.get(k) for k in KEYS} | {"terminal_reason": r.get("terminal", {}).get("reason"),
                                          "exposure_reached": r.get("exposure_reached"),
                                          "traffic_resolved": r.get("traffic_resolved"),
                                          "repetitions_unanalysed": r.get("repetitions_unanalysed")}


def before(name):
    v = OBSERVED[name]
    s = v.get("persisted", v)
    return {k: s.get(k) for k in KEYS} | ({"actual_source_writes": v["actual_source_writes"]}
                                          if "actual_source_writes" in v else {})


with tempfile.TemporaryDirectory(prefix="acceptance_boundaries_") as temp:
    temp = Path(temp)
    p, _ = loopback()
    positive = rig.Run("positive", repetitions=2, tx_during_rx=False).execute(
        p, out_dir=temp / "positive", sleep=lambda t: None)
    assert positive["completed_exposure"] and positive["losses"] == 0
    assert positive["terminal"]["reason"] == "exposure_repetitions"
    case("positive_run", before("positive_run"), summary(json.loads((temp / "positive/run.json").read_text())))

    p, state = loopback(damage_first=3)
    rig.Run("three losses", repetitions=200, tx_during_rx=False).execute(
        p, out_dir=temp / "stopped", sleep=lambda t: None)
    on_disk = json.loads((temp / "stopped/run.json").read_text())
    now = summary(on_disk) | {"actual_source_writes": state["writes"], "requested_repetitions": 200}
    assert state["writes"] == 302 and on_disk["losses"] == 3
    assert on_disk["completed_exposure"] is False and on_disk["incomplete"] is True, now
    assert on_disk["terminal"]["reason"] == "stop_rule_losses" and on_disk["exposure_reached"] is False
    case("stop_loss_run", before("stop_loss_run"), now)

    p, state = loopback()
    with patch.object(rig, "analyse", side_effect=ValueError("injected analyser failure")):
        try:
            rig.Run("analysis unavailable", repetitions=2, tx_during_rx=False).execute(
                p, out_dir=temp / "analysis_failure", sleep=lambda t: None)
            exception = None
        except rig.RigError as exc:
            exception = f"{type(exc).__name__}: {exc} (cause {type(exc.__cause__).__name__})"
    on_disk = json.loads((temp / "analysis_failure/run.json").read_text())
    now = summary(on_disk) | {"actual_source_writes": state["writes"], "exception": exception}
    assert state["writes"] == 302, now                             # no second repetition started
    assert exception is not None and "cause ValueError" in exception
    assert on_disk["losses"] is None and on_disk["losses_per_100k_bytes"] is None, now
    assert on_disk["error"] == "ValueError: injected analyser failure"
    assert on_disk["terminal"]["reason"] == "analysis_unavailable" and "completed" not in on_disk["stopped"]
    assert on_disk["repetition_results"][0]["losses"] is None
    case("analyser_failure", before("analyser_failure"), now)

    now_clock = [0.0]

    def last_write(data, timeout=None):
        if b" TERM " in data:
            now_clock[0] = 1.0
        return len(data)
    p = rig.callable_port("all accepted before cutoff", last_write, lambda t: b"", takes_timeout=True)
    cut = rig.Run("drain cutoff", repetitions=2, seconds=1.0, tx_during_rx=False).execute(
        p, out_dir=temp / "cutoff", sleep=lambda t: None, clock=lambda: now_clock[0])
    now = summary(cut) | {"censored_in_flight": cut["censored_in_flight"],
                          "repetition_0": {k: cut["repetition_results"][0][k]
                                           for k in ("frames_accepted", "cut_short", "incomplete", "resolved")}}
    assert cut["censored_in_flight"] == 302 and cut["completed_exposure"] is False, now
    assert cut["terminal"]["reason"] == "exposure_seconds_censored" and cut["exposure_reached"] is True
    assert cut["repetition_results"][0]["incomplete"] is True
    case("all_writes_then_cutoff", before("all_writes_then_cutoff"), now)

print(json.dumps(out, indent=2, sort_keys=True))
