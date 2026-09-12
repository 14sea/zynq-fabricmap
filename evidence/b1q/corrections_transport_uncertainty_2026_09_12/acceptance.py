#!/usr/bin/env python3
"""The owner's uncertainty probe, re-run against the corrected rig — before beside after.

`evidence/b1q/review_transport_uncertainty_2026_09_12/probe_uncertainty.py` records the answers at
`328e9c1` in `observed.json`: four fixture shapes through a production Run with a 0.01 s budget.
The same four run here unchanged, plus the mixed confirmed-then-unresolved case the review asks
for as an additional regression, and each is ASSERTED on the returned result and on the persisted
run.json — the old unqualified 0.0 now fails loudly.

Offline only: no serial device, no manifest, pin, instrument or ruling is touched. Temporary
export directories only. Run from the repository root with `python3 -B`.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "host"))
import transport_rig as rig                                        # noqa: E402

OBSERVED = json.loads((ROOT / "evidence/b1q/review_transport_uncertainty_2026_09_12/observed.json").read_text())
FIELDS = ("frames_accepted", "denominator_bytes", "censored_in_flight", "unresolved_at_cutoff",
          "confirmed_losses", "losses", "losses_upper_bound", "losses_per_100k_bytes",
          "confirmed_losses_per_100k_bytes", "losses_per_100k_bytes_upper_bound",
          "traffic_resolved", "completed_exposure")
out = {"provenance": rig.provenance(), "cases": {}}


def flip(buf: bytes, at: int) -> bytes:
    return buf[:at] + bytes([buf[at] ^ 0x01]) + buf[at + 1:]


def view(r):
    return {k: r.get(k) for k in FIELDS} | {"loss_metric": r.get("loss_metric"),
                                            "terminal_reason": r.get("terminal", {}).get("reason")}


def before(name):
    return {k: OBSERVED["cases"][name]["persisted"].get(k) for k in FIELDS if k in OBSERVED["cases"][name]["persisted"]}


EXPECT = {
    "intact": {"confirmed_losses": 0, "losses": 0, "losses_upper_bound": 0, "losses_per_100k_bytes": 0.0,
               "status": "exact"},
    "known_crc_damage": {"confirmed_losses": 1, "losses": 1, "losses_upper_bound": 1, "status": "exact"},
    "unidentifiable_damage": {"confirmed_losses": 0, "losses": None, "losses_upper_bound": 1,
                              "losses_per_100k_bytes": None, "confirmed_losses_per_100k_bytes": 0.0,
                              "unresolved_at_cutoff": 1, "status": "bounded"},
    "silence": {"confirmed_losses": 0, "losses": 0, "losses_per_100k_bytes": None, "censored_in_flight": 1,
                "denominator_bytes": 0, "status": "no_denominator"},
}

with tempfile.TemporaryDirectory(prefix="acceptance_uncertainty_") as temp:
    temp = Path(temp)
    for name in ("intact", "known_crc_damage", "unidentifiable_damage", "silence"):
        now, queued = [0.0], [b""]

        def write(data, timeout=None, name=name, queued=queued):
            if name == "intact":
                queued[0] += data
            elif name == "known_crc_damage":
                queued[0] += flip(data, 60)
            elif name == "unidentifiable_damage":
                queued[0] += b"garbled\n"
            return len(data)

        def read(timeout, now=now, queued=queued):
            now[0] += timeout
            data, queued[0] = queued[0], b""
            return data
        port = rig.callable_port("offline double", write, read, takes_timeout=True)
        d = temp / name
        result = rig.Run(name, repetitions=200, seconds=0.01, tx_during_rx=False, run_id="review").execute(
            port, clock=lambda now=now: now[0], out_dir=d, sleep=lambda t, now=now: now.__setitem__(0, now[0] + t))
        persisted = json.loads((d / "run.json").read_text())
        for where, r in (("returned", result), ("persisted", persisted)):
            for k, v in EXPECT[name].items():
                got = r["loss_metric"]["status"] if k == "status" else r[k]
                assert got == v, (name, where, k, got, v)
        case = {"observed_at_328e9c1": before(name), "now": view(persisted)}
        out["cases"][name] = case

    # the mixed regression: two identified corrupted frames, then unidentifiable damage, then the cutoff
    st = {"writes": 0, "queued": b"", "now": 0.0}

    def mixed_write(data, timeout=None):
        st["writes"] += 1
        i = st["writes"] - 1
        n = len(data)                                                  # accepted in full
        if 1 <= i <= 2:
            data = flip(data, 60)
        elif i == 3:
            data = b"garbled\n"
        st["queued"] += data
        return n

    def mixed_read(t):
        if st["writes"] > 3:
            st["now"] += t
        out_, st["queued"] = st["queued"], b""
        return out_
    port = rig.callable_port("mixed", mixed_write, mixed_read, takes_timeout=True)
    d = temp / "confirmed_then_unresolved"
    result = rig.Run("confirmed then unresolved", repetitions=200, seconds=0.01, tx_during_rx=False).execute(
        port, out_dir=d, clock=lambda: st["now"], sleep=lambda t: st.__setitem__("now", st["now"] + t))
    persisted = json.loads((d / "run.json").read_text())
    for where, r in (("returned", result), ("persisted", persisted)):
        assert (r["confirmed_losses"], r["losses"], r["losses_upper_bound"], r["unresolved_at_cutoff"]) == (2, None, 3, 1), (where, view(r))
        assert r["losses_per_100k_bytes"] is None and r["loss_metric"]["status"] == "bounded", (where, view(r))
        assert r["confirmed_losses_per_100k_bytes"] == 2 * 100000 / r["denominator_bytes"], where
    out["cases"]["confirmed_then_unresolved"] = {"observed_at_328e9c1": "not probed: requested as an additional regression",
                                                "now": view(persisted)}

print(json.dumps(out, indent=2, sort_keys=True))
