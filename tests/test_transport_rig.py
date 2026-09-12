#!/usr/bin/env python3
"""The transport rig, proved before it is believed — and re-proved against the owner's
counterexamples of 2026-09-12 (`docs/b1q_transport_stage1_review_2026_09_12.md`).

A capture tool that reports a clean run proves nothing until it is shown to report a dirty
one, so every fault the real sessions showed is injected into a known stream and must be
detected AND localised. Five of these classes exist because the first version passed its own
tests and still got them wrong: loss weighting, the denominator, delivery credited on an index
without its bytes, a replayed repetition, and an execution path that never ran.

What a pseudo-terminal cannot prove, said here rather than implied: a pty has no UART framing,
parity or overrun and loses nothing. It exercises the tool end to end; the plan's stage 1 also
requires a physical acceptance on a separate serial device or a self-loopback, which has NOT
happened.
"""
from __future__ import annotations

import json
import os
import pty
import select
import sys
import tempfile
import time
import tty
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import transport_rig as rig  # noqa: E402


def flip(buf: bytes, at: int) -> bytes:
    return buf[:at] + bytes([buf[at] ^ 0x01]) + buf[at + 1:]


def lines_of(kind: bytes, data: bytes) -> list[int]:
    """Offsets of every frame of one type in a captured stream, found without knowing the run —
    the doubles mutate by frame class, not by a remembered offset."""
    out, at = [], 0
    for ln in data.split(b"\n")[:-1]:
        if ln.startswith(b"P3L5 " + kind + b" "):
            out.append(at)
        at += len(ln) + 1
    return out


def loopback(mutate=None, fail_after=None, fd=None):
    """A real loopback double: what is written to the source comes back from the capture, so the
    traffic under test is THIS repetition's own — the token, the indexes and the bytes included.
    `mutate(bytes) -> bytes` damages the returned stream; `fail_after` raises on the Nth read."""
    state = {"buf": bytearray(), "reads": 0}

    def write(data):
        if data.startswith(b"P3L5 "):
            state["buf"] += data
        return len(data)

    def read(_timeout):
        state["reads"] += 1
        if fail_after is not None and state["reads"] > fail_after:
            raise OSError("synthetic detach")
        out, state["buf"] = bytes(state["buf"]), bytearray()
        return mutate(out) if (mutate and out) else out
    return rig.callable_port("loopback", write, read, fd=fd), state


def whole_stream(mutate=None, fail_after=None, fd=None):
    """A loopback that holds everything until the stream is complete, then returns it in one
    piece — for the analyses that need the whole repetition mutated as a unit."""
    state = {"buf": bytearray(), "reads": 0, "done": False}

    def write(data):
        if data.startswith(b"P3L5 "):
            state["buf"] += data
        return len(data)

    def read(_timeout):
        state["reads"] += 1
        if fail_after is not None and state["reads"] > fail_after:
            raise OSError("synthetic detach")
        if len(state["buf"]) < 98000:
            return b""
        out, state["buf"] = bytes(state["buf"]), bytearray()
        return mutate(out) if mutate else out
    return rig.callable_port("whole", write, read, fd=fd), state


class TheGeneratedStream(unittest.TestCase):
    def setUp(self):
        self.frames = rig.plan_frames("t", 0)
        self.stream = rig.stream_bytes(self.frames)

    def test_it_is_the_measured_shape(self):
        self.assertEqual(len(self.frames), rig.FRAMES_PER_PROFILE)
        self.assertEqual(len(self.frames), 302)
        for kind, count, lo, hi in rig.SESSION_PROFILE:
            got = [f for f in self.frames if f.kind == kind]
            self.assertEqual(len(got), count, kind)
            for f in got:
                self.assertLessEqual(abs(f.bytes - f.target_bytes), rig.LENGTH_TOLERANCE, f"{kind} {f.index}")
                self.assertGreaterEqual(f.bytes, lo - rig.LENGTH_TOLERANCE, kind)
                self.assertLessEqual(f.bytes, hi + rig.LENGTH_TOLERANCE, kind)
        self.assertLess(min(f.bytes for f in self.frames), 70)
        self.assertGreater(max(f.bytes for f in self.frames), 2600)

    def test_the_bytes_are_known_in_advance_and_reproducible(self):
        """The positive deterministic control: the same run and repetition regenerate the same
        bytes, so a capture can be re-analysed later."""
        self.assertEqual(rig.stream_bytes(rig.plan_frames("t", 0)), self.stream)
        for f in self.frames:
            self.assertEqual(self.stream[f.offset:f.offset + f.bytes], f.line)

    def test_every_repetition_has_its_own_epoch(self):
        """The counterexample: repetition 1's bytes replayed as repetition 2 were clean. Each
        repetition now carries its own token, so its traffic is distinguishable."""
        a, b = rig.plan_frames("t", 0), rig.plan_frames("t", 1)
        self.assertNotEqual(rig.stream_bytes(a), rig.stream_bytes(b))
        self.assertNotEqual(rig.token_for("t", 0), rig.token_for("t", 1))
        self.assertNotEqual(rig.token_for("one", 0), rig.token_for("two", 0))
        self.assertEqual(len(rig.token_for("t", 0)), 32)

    def test_the_frames_are_real_rel_v4(self):
        import l5_notary as l5
        for f in self.frames[:20]:
            parsed = l5.parse_line(f.line.decode())
            self.assertEqual((parsed["type"], parsed["seq"]), (f.kind, f.seq))
            self.assertEqual(parsed["token"], rig.token_for("t", 0))

    def test_the_host_schedule_is_the_rule_the_recorded_session_shows(self):
        """Not `i % len(HOST_SENDS)`: one reply per frame that causes one, by the rule the clean
        session's own timeline exhibits, and the same 125 host frames it sent."""
        derived = rig.host_schedule_from_timeline(R / rig.TIMELINE_SOURCE)
        self.assertEqual(derived["tx_total"], 125)
        for pair in ("SIGNREQ->SIGNOK", "AUDIT->AUDITGET", "AUDIT->AUDITDONE", "REC->RECACK",
                     "IDENT->IDENTACK", "AUDIT_READY->AUDITGET", "TERM->TERMACK"):
            self.assertIn(pair, derived["rx_then_tx"], pair)
        self.assertAlmostEqual(derived["tx_to_next_rx_s"]["median"], rig.TX_GAP_MEDIAN_S, places=2)
        self.assertAlmostEqual(derived["tx_to_next_rx_s"]["min"], rig.TX_GAP_MIN_S, places=2)

        schedule = rig.host_schedule(self.frames)
        kinds: dict = {}
        for s in schedule:
            k = s["line"].split(b" ")[0].decode()
            kinds[k] = kinds.get(k, 0) + 1
        self.assertEqual(len(schedule), 125)
        self.assertEqual(kinds["AUDITGET"], 88)          # one per chunk: 11 openers + 77 follow-ons
        self.assertEqual(kinds["AUDITDONE"], 11)         # one per record's last chunk
        self.assertEqual(kinds["IDENTACK"], 1)
        self.assertEqual({s["after_frame"] for s in schedule}.issubset(range(len(self.frames))), True)


class TheLossUnit(unittest.TestCase):
    """P2-1: one affected expected frame is ONE loss, however its damage happens to parse."""

    def setUp(self):
        self.frames = rig.plan_frames("t", 0)
        self.stream = rig.stream_bytes(self.frames)
        self.recs = [f for f in self.frames if f.kind == "REC"]

    def test_one_two_and_three_affected_frames_count_exactly_once_each(self):
        for n in (1, 2, 3):
            with self.subTest(frames=n):
                buf = bytearray(self.stream)
                for f in self.recs[:n]:
                    buf[f.offset + 20] ^= 1
                res = rig.analyse(self.frames, bytes(buf))
                self.assertEqual(res["losses"], n)
                self.assertEqual(res["frames_delivered"], len(self.frames) - n)

    def test_every_kind_of_damage_to_one_frame_weighs_the_same(self):
        f = self.recs[0]
        cases = {
            "bit flipped": flip(self.stream, f.offset + 20),
            "byte dropped": self.stream[:f.offset + 20] + self.stream[f.offset + 21:],
            "frame deleted": self.stream[:f.offset] + self.stream[f.offset + f.bytes:],
            "newline inserted": self.stream[:f.offset + 100] + b"\n" + self.stream[f.offset + 100:],
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                res = rig.analyse(self.frames, data)
                self.assertEqual(res["losses"], 1, f"{name}: {res['defects_by_kind']}")

    @staticmethod
    def damage(n: int):
        def mutate(data: bytes) -> bytes:
            buf = bytearray(data)
            for at in lines_of(b"REC", data)[:n]:
                buf[at + 20] ^= 1
            return bytes(buf)
        return mutate

    def test_two_corrupted_frames_do_not_trip_a_three_loss_stop(self):
        """The registered threshold is unchanged; the unit it counts is now correct, so two
        damaged frames are two losses and the condition keeps running."""
        port, _ = whole_stream(self.damage(2))
        res = rig.Run("two damaged", repetitions=1, tx_during_rx=False).execute(port, sleep=lambda s: None)
        self.assertEqual(res["losses"], 2)
        self.assertNotIn("stop rule", res["stopped"])

    def test_three_affected_frames_do_stop_it(self):
        port, _ = whole_stream(self.damage(3))
        res = rig.Run("three damaged", repetitions=5, tx_during_rx=False).execute(port, sleep=lambda s: None)
        self.assertEqual(res["repetitions_run"], 1)
        self.assertEqual(res["losses"], 3)
        self.assertIn("stop rule", res["stopped"])
        self.assertIn("reproducing the failure", res["stopped"])

    def test_the_diagnostics_stay_distinguishable(self):
        f = self.recs[0]
        res = rig.analyse(self.frames, flip(self.stream, f.offset + 20))
        self.assertEqual(res["losses"], 1)
        self.assertEqual(res["defects_by_kind"], {"crc_failed": 1})
        self.assertEqual(res["missing"], [f.index])
        self.assertEqual(res["damaged"], [])
        self.assertEqual(res["loss_unit"], rig.LOSS_UNIT)


class TheDenominator(unittest.TestCase):
    """P2-1: plan §5 says losses per RECEIVED byte, and silence has no denominator at all."""

    def setUp(self):
        self.frames = rig.plan_frames("t", 0)
        self.stream = rig.stream_bytes(self.frames)

    def test_silence_has_no_rate_but_still_has_losses(self):
        port, _ = whole_stream(lambda data: b"")
        res = rig.Run("silence", repetitions=1, tx_during_rx=False).execute(port, sleep=lambda s: None)
        self.assertEqual(res["denominator_bytes"], 0)
        self.assertIsNone(res["losses_per_100k_bytes"])
        self.assertIn("unavailable", res["denominator"])
        self.assertEqual(res["losses"], 302)

    def test_a_deletion_divides_by_what_arrived(self):
        def drop_first_rec(data: bytes) -> bytes:
            at = lines_of(b"REC", data)[0]
            end = data.index(b"\n", at) + 1
            return data[:at] + data[end:]
        port, _ = whole_stream(drop_first_rec)
        res = rig.Run("deleted", repetitions=1, tx_during_rx=False).execute(port, sleep=lambda s: None)
        self.assertEqual(res["losses"], 1)
        self.assertLess(res["denominator_bytes"], res["bytes_sent"])
        self.assertAlmostEqual(res["losses_per_100k_bytes"], 100000 / res["denominator_bytes"], places=6)
        self.assertEqual(res["denominator"], "received bytes")


class DeliveryNeedsTheBytesNotTheIndex(unittest.TestCase):
    """P2-2: an index is not a delivery."""

    def setUp(self):
        self.frames = rig.plan_frames("t", 0)
        self.stream = rig.stream_bytes(self.frames)
        self.rec = next(f for f in self.frames if f.kind == "REC")

    def altered(self) -> bytes:
        """The owner's counterexample: keep the index, change a pad byte, rebuild a VALID CRC."""
        import base64
        import l5_notary as l5
        parsed = l5.parse_line(self.rec.line.decode())
        payload = bytearray(base64.urlsafe_b64decode(parsed["payload"]))
        payload[-1] ^= 1
        line = l5.build_line(self.rec.kind, self.rec.seq, parsed["token"],
                             base64.urlsafe_b64encode(payload).decode()).encode()
        return self.stream[:self.rec.offset] + line + self.stream[self.rec.offset + self.rec.bytes:]

    def test_a_valid_crc_over_bytes_we_did_not_send_is_not_delivered(self):
        res = rig.analyse(self.frames, self.altered())
        self.assertEqual(res["frames_delivered"], 301)
        self.assertEqual(res["losses"], 1)
        self.assertEqual(res["damaged"], [self.rec.index])
        self.assertEqual(res["defects_by_kind"], {"altered": 1})
        self.assertFalse(res["clean"])

    def test_a_stale_repetition_is_a_total_loss_not_a_clean_run(self):
        """Repetition 0's capture replayed into repetition 1."""
        stale = rig.stream_bytes(rig.plan_frames("t", 0))
        res = rig.analyse(rig.plan_frames("t", 1), stale, rig.token_for("t", 1))
        self.assertEqual(res["frames_delivered"], 0)
        self.assertEqual(res["losses"], 302)
        self.assertEqual(res["defects_by_kind"], {"foreign_epoch": 302})

    def test_a_replayed_capture_through_the_driver_is_not_clean(self):
        kept = {"bytes": None}

        def replay(data: bytes) -> bytes:
            if kept["bytes"] is None:                   # keep repetition 0's traffic and repeat it
                kept["bytes"] = data
            return kept["bytes"]
        port, _ = whole_stream(replay)
        res = rig.Run("replay", repetitions=2, tx_during_rx=False).execute(port, sleep=lambda s: None)
        self.assertTrue(res["repetition_results"][0]["clean"])
        self.assertFalse(res["repetition_results"][1]["clean"])
        self.assertEqual(res["repetition_results"][1]["losses"], 302)

    def test_an_unexpected_index_is_a_defect_not_a_delivery(self):
        far = rig.build_frame(10 ** 6, "HB", 1, 66, rig.token_for("t", 0))
        res = rig.analyse(self.frames, self.stream + far.line)
        self.assertEqual(res["defects_by_kind"], {"unexpected_index": 1})
        self.assertEqual(res["frames_delivered"], 302)
        self.assertEqual(res["unexpected_frames"], 1)
        self.assertFalse(res["clean"])

    def test_a_short_write_is_a_tool_error_not_a_clean_run(self):
        port = rig.callable_port("short", lambda data: 0, lambda t: b"")
        with self.assertRaises(rig.RigError) as cm:
            rig.Run("short write", repetitions=1, tx_during_rx=False).execute(port, sleep=lambda s: None)
        self.assertIn("short write", str(cm.exception))

    def test_a_write_that_reports_nothing_is_refused(self):
        port = rig.callable_port("silent", lambda data: None, lambda t: b"")
        with self.assertRaises(rig.RigError) as cm:
            rig.Run("no count", repetitions=1, tx_during_rx=False).execute(port, sleep=lambda s: None)
        self.assertIn("cannot be detected", str(cm.exception))


class ItDetectsAndLocalisesEveryFault(unittest.TestCase):
    def setUp(self):
        self.frames = rig.plan_frames("t", 0)
        self.stream = rig.stream_bytes(self.frames)
        self.rec = next(f for f in self.frames if f.kind == "REC")
        self.hb = next(f for f in self.frames if f.kind == "HB")

    def test_an_untouched_stream_is_clean(self):
        res = rig.analyse(self.frames, self.stream)
        self.assertTrue(res["clean"], res)
        self.assertEqual((res["losses"], res["missing"], res["duplicated"], res["defects"]), (0, [], [], []))
        self.assertIsNone(res["divergence"])

    def test_one_byte_dropped_inside_the_longest_frame(self):
        at = self.rec.offset + 100
        res = rig.analyse(self.frames, self.stream[:at] + self.stream[at + 1:])
        d = res["divergence"]
        self.assertEqual((d["frame_index"], d["frame_kind"], d["offset_in_frame"]), (self.rec.index, "REC", 100))
        self.assertEqual(res["losses"], 1)

    def test_one_bit_flipped_in_the_shortest_frame(self):
        at = self.hb.offset + 20
        res = rig.analyse(self.frames, flip(self.stream, at))
        self.assertEqual(res["missing"], [self.hb.index])
        self.assertEqual(res["divergence"]["offset_in_frame"], 20)

    def test_a_run_of_bytes_dropped_is_reported_with_its_length(self):
        at = self.rec.offset + 50
        res = rig.analyse(self.frames, self.stream[:at] + self.stream[at + 200:])
        d = res["divergence"]
        self.assertEqual(d["first_offset"], at)
        self.assertEqual(d["expected_bytes"] - d["received_bytes"], 200)
        self.assertGreater(res["losses"], 0)

    def test_a_duplicated_frame(self):
        f = self.frames[10]
        res = rig.analyse(self.frames, self.stream[:f.offset + f.bytes] + f.line + self.stream[f.offset + f.bytes:])
        self.assertEqual(res["duplicated"], [f.index])
        self.assertFalse(res["clean"])
        self.assertEqual(res["losses"], 0)               # it arrived; the DUPLICATE is the finding

    def test_two_frames_swapped(self):
        a, b = self.frames[5], self.frames[6]
        res = rig.analyse(self.frames, self.stream[:a.offset] + b.line + a.line + self.stream[b.offset + b.bytes:])
        self.assertTrue(res["out_of_order"])
        self.assertEqual(res["losses"], 0)

    def test_a_truncated_stream(self):
        res = rig.analyse(self.frames, self.stream[:-500])
        self.assertGreater(res["losses"], 0)
        self.assertLess(res["divergence"]["received_bytes"], res["divergence"]["expected_bytes"])

    def test_silence(self):
        res = rig.analyse(self.frames, b"")
        self.assertEqual(res["frames_delivered"], 0)
        self.assertEqual(res["losses"], len(self.frames))
        self.assertEqual(res["divergence"]["first_offset"], 0)

    def test_line_noise_that_is_not_a_frame(self):
        res = rig.analyse(self.frames, self.stream + b"U-Boot 2018.01 (Jan 01 2018)\n")
        self.assertEqual(res["defects_by_kind"], {"malformed": 1})

    def test_an_inserted_newline_does_not_count_as_resynchronisation(self):
        """P3: the old field found the next newline and called it resynchronisation. What
        follows an inserted newline is the remainder of a broken frame, and the field that
        claims resynchronisation must name a VERIFIED expected frame."""
        at = self.rec.offset + 100
        res = rig.analyse(self.frames, self.stream[:at] + b"\n" + self.stream[at:])
        d = res["divergence"]
        self.assertEqual(d["bytes_to_next_newline"], 1)
        self.assertIsNotNone(d["resynchronised_at"])
        self.assertGreater(d["resynchronised_at"]["bytes_after_first_divergence"], 1)
        self.assertEqual(d["resynchronised_at"]["verified_frame_index"], self.rec.index + 1)
        self.assertEqual(res["losses"], 1)

    def test_nothing_resynchronises_when_the_tail_is_gone(self):
        res = rig.analyse(self.frames, self.stream[:self.rec.offset + 10])
        self.assertIsNone(res["divergence"]["resynchronised_at"])


class TheDriver(unittest.TestCase):
    """P2-3: the execution contract, exercised — ordering, overlap, incremental capture and a
    deadline that bounds the operations rather than only the gaps between repetitions."""

    def trace_port(self, response=b"", clock=None, sleep=None):
        events = []

        def write(data):
            events.append({"op": "write", "t": clock(), "bytes": len(data),
                           "kind": "source" if data.startswith(b"P3L5 ") else "host"})
            return len(data)

        def read(_t):
            events.append({"op": "read", "t": clock()})
            return b""
        return rig.callable_port("trace", write, read), events

    def test_the_stream_is_written_frame_by_frame_and_drained_between(self):
        now = [0.0]
        port, events = self.trace_port(clock=lambda: now[0])
        rep = rig.Repetition(index=0, frames=rig.plan_frames("t", 0))
        rig.Driver(port, port, port, tx_during_rx=False, sleep=lambda s: None, clock=lambda: now[0]).run(rep, 1e9)
        writes = [e for e in events if e["op"] == "write"]
        self.assertEqual(len(writes), 302)                       # not one big write
        self.assertTrue(all(e["kind"] == "source" for e in writes))
        self.assertGreaterEqual(sum(1 for e in events if e["op"] == "read"), 302)

    def test_host_traffic_goes_to_the_host_port_at_its_scheduled_points(self):
        now = [0.0]
        source, s_events = self.trace_port(clock=lambda: now[0])
        host, h_events = self.trace_port(clock=lambda: now[0])
        capture, _ = self.trace_port(clock=lambda: now[0])
        rep = rig.Repetition(index=0, frames=rig.plan_frames("t", 0))
        rig.Driver(source, host, capture, tx_during_rx=True,
                   sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0]).run(rep, 1e9)
        self.assertEqual(len([e for e in s_events if e["op"] == "write"]), 302)
        self.assertEqual(len([e for e in h_events if e["op"] == "write"]), 125)   # the derived schedule
        self.assertTrue(all(e["kind"] == "host" for e in h_events if e["op"] == "write"))
        # the schedule is CONSUMED: the events interleave, they do not all follow the stream
        ordered = [e["op"] for e in rep.events]
        self.assertIn("write_host", ordered)
        self.assertLess(ordered.index("write_host"), len(ordered) - 1)

    def test_without_tx_during_rx_the_host_port_stays_silent(self):
        now = [0.0]
        source, _ = self.trace_port(clock=lambda: now[0])
        host, h_events = self.trace_port(clock=lambda: now[0])
        rep = rig.Repetition(index=0, frames=rig.plan_frames("t", 0))
        rig.Driver(source, host, source, tx_during_rx=False, sleep=lambda s: None, clock=lambda: now[0]).run(rep, 1e9)
        self.assertEqual([e for e in h_events if e["op"] == "write"], [])

    def test_reads_are_incremental_and_timestamped(self):
        now = [0.0]
        chunks = [b"abc", b"def", b""]

        def read(_t):
            now[0] += 0.01
            return chunks.pop(0) if chunks else b""
        port = rig.callable_port("chunky", lambda d: len(d), read)
        rep = rig.Repetition(index=0, frames=rig.plan_frames("t", 0)[:1])
        rig.Driver(port, port, port, tx_during_rx=False, sleep=lambda s: None, clock=lambda: now[0]).run(rep, 1e9)
        reads = [e for e in rep.events if e["op"] == "read"]
        self.assertEqual(bytes(rep.received), b"abcdef")
        self.assertEqual([e["bytes"] for e in reads], [3, 3])
        self.assertTrue(all("t" in e for e in reads))
        self.assertLess(reads[0]["t"], reads[1]["t"])

    def test_the_deadline_bounds_the_operations_not_just_the_repetitions(self):
        """The counterexample: a 0.1 s limit spent 2.232 s writing host commands and still
        reported a completed repetition."""
        now = [0.0]

        def sleep(s):
            now[0] += s
        port = rig.callable_port("slow", lambda d: len(d), lambda t: b"")
        run = rig.Run("bounded", repetitions=1, seconds=0.1, tx_during_rx=True)
        res = run.execute(port, sleep=sleep, clock=lambda: now[0])
        self.assertLessEqual(now[0], 0.1 + rig.TX_GAP_MEDIAN_S)
        self.assertIn("deadline", res["stopped"])
        self.assertEqual(res["repetition_results"][0]["ended"][:8], "deadline")
        self.assertLess(res["repetition_results"][0]["frames_delivered"], 302)


class TheFinalisation(unittest.TestCase):
    """P2-4: the error path must still land the evidence."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="rigout_"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.d, ignore_errors=True)

    def test_a_tool_error_still_exports_the_capture_and_keeps_the_original_error(self):
        """One good repetition, then the device goes away in the next."""
        port, _ = whole_stream(fail_after=400)
        run = rig.Run("detach", repetitions=3, tx_during_rx=False)
        with self.assertRaises(rig.RigError) as cm:
            run.execute(port, fd=None, out_dir=self.d, sleep=lambda s: None)
        exc = cm.exception
        self.assertIn("synthetic detach", str(exc))
        self.assertIsInstance(exc.__cause__, OSError)                 # the ORIGINAL error survives
        self.assertIsNotNone(exc.result)                              # and the result is not lost
        self.assertTrue((self.d / "run.json").is_file())
        on_disk = json.loads((self.d / "run.json").read_text())
        self.assertEqual(on_disk["error"][:7], "OSError")
        self.assertIn("tool error", on_disk["stopped"])
        self.assertTrue(on_disk["captures"])                          # partial capture retained
        for c in on_disk["captures"]:
            self.assertTrue((self.d / c["capture"]).is_file())
            self.assertTrue((self.d / c["events"]).is_file())
            json.loads((self.d / c["events"]).read_text())            # readable
        self.assertFalse(on_disk["counters_before"]["available"])
        self.assertFalse(on_disk["counters_after"]["available"])      # ATTEMPTED on both sides
        self.assertIn("reason", on_disk["counters_after"])

    def test_the_counters_are_sampled_on_both_sides_of_a_failed_run(self):
        calls = []
        real = rig.read_icounters
        try:
            rig.read_icounters = lambda fd: (calls.append(fd), {"available": False, "reason": "double"})[1]
            port, _ = whole_stream(fail_after=400)
            with self.assertRaises(rig.RigError):
                rig.Run("detach", repetitions=3, tx_during_rx=False).execute(
                    port, fd=123, out_dir=self.d, sleep=lambda s: None)
        finally:
            rig.read_icounters = real
        self.assertEqual(calls, [123, 123])

    def test_a_clean_run_exports_the_same_record(self):
        frames = rig.plan_frames("x", 0)
        port, _ = loopback()
        res = rig.Run("clean", repetitions=1, tx_during_rx=False, run_id="x").execute(
            port, out_dir=self.d, sleep=lambda s: None)
        on_disk = json.loads((self.d / "run.json").read_text())
        self.assertEqual(on_disk["run_id"], res["run_id"])
        self.assertIsNone(on_disk["error"])
        self.assertEqual(on_disk["provenance"]["tool"], "host/transport_rig.py")
        for k in ("tool_sha256", "framing_sha256", "instrument_root", "loss_unit"):
            self.assertIn(k, on_disk["provenance"])
        self.assertEqual(on_disk["parameters"]["stop_at_losses"], rig.LOSSES_PER_REPETITION_STOP)
        raw = (self.d / on_disk["captures"][0]["capture"]).read_bytes()
        self.assertEqual(rig.analyse(frames, raw, rig.token_for("x", 0))["clean"], True)

    def test_an_unwritable_export_is_recorded_and_does_not_replace_the_error(self):
        port, _ = whole_stream(fail_after=400)
        blocked = self.d / "file"
        blocked.write_text("not a directory")
        with self.assertRaises(rig.RigError) as cm:
            rig.Run("detach", repetitions=2, tx_during_rx=False).execute(
                port, out_dir=blocked / "under", sleep=lambda s: None)
        self.assertIsInstance(cm.exception.__cause__, OSError)
        self.assertIn("synthetic detach", str(cm.exception.__cause__))
        self.assertIn("export_error", cm.exception.result)


class TheCountersNoSessionHad(unittest.TestCase):
    def test_a_pty_has_no_uart_counters_and_says_so(self):
        master, slave = os.openpty()
        try:
            got = rig.read_icounters(slave)
        finally:
            os.close(master)
            os.close(slave)
        self.assertFalse(got["available"])
        self.assertTrue(got["reason"])
        self.assertNotIn("frame", got)

    def test_no_fd_is_unavailable_not_zero(self):
        got = rig.read_icounters(None)
        self.assertFalse(got["available"])
        self.assertNotIn("overrun", got)

    def test_a_delta_of_unavailable_counters_is_unavailable(self):
        d = rig.counter_delta({"available": False, "reason": "x"},
                              {"available": True, **{k: 0 for k in rig.ICOUNTER_FIELDS}})
        self.assertFalse(d["available"])
        self.assertNotIn("frame", d)

    def test_a_delta_of_available_counters_is_the_difference(self):
        before = {"available": True, **{k: 0 for k in rig.ICOUNTER_FIELDS}}
        after = {"available": True, **{k: 0 for k in rig.ICOUNTER_FIELDS}, "frame": 7, "overrun": 2}
        d = rig.counter_delta(before, after)
        self.assertEqual((d["frame"], d["overrun"], d["parity"]), (7, 2, 0))


class OverAPtyPair(unittest.TestCase):
    """The offline acceptance run, through the PRODUCTION entry point `Run.execute`, for both
    TX conditions. A pty is not a UART — no framing, parity or overrun, and it loses nothing —
    so this proves the driver, the capture and the analysis, and no link property whatever."""

    def ports(self):
        master, slave = pty.openpty()
        tty.setraw(master)
        tty.setraw(slave)
        os.set_blocking(master, False)
        os.set_blocking(slave, False)
        self.addCleanup(lambda: [os.close(fd) for fd in (master, slave)])

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
        return rig.callable_port("pty", write, read, fd=slave)

    def test_a_self_loopback_returns_the_rigs_own_host_traffic_and_says_so(self):
        """The review's point: on one device the host commands loop back into the capture. They
        are neither transport damage nor traffic under test, so they are counted as host_echo,
        kept out of the defects, and the topology is recorded beside the run."""
        d = Path(tempfile.mkdtemp(prefix="rigecho_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        port = self.ports()
        res = rig.Run("echo", repetitions=1, seconds=60.0, tx_during_rx=True).execute(
            port, out_dir=d, sleep=lambda s: None, read_timeout=0.05)
        rep = res["repetition_results"][0]
        self.assertEqual(rep["host_echo_lines"], 125)
        self.assertGreater(rep["bytes_host_echo"], 0)
        self.assertEqual(rep["defects"], [])
        self.assertEqual(res["losses"], 0)
        self.assertTrue(rep["clean"])
        self.assertIn("one device", res["topology"])
        self.assertEqual(res["denominator_bytes"], rep["bytes_received"])
        self.assertGreater(res["denominator_bytes"], res["bytes_sent"])   # the echo is in there

    def test_a_two_port_topology_is_named_as_such(self):
        a, b = self.ports(), self.ports()
        driver = rig.Driver(a, b, a, tx_during_rx=True)
        self.assertIn("source=", driver.topology)
        self.assertNotIn("one device", driver.topology)

    def test_both_tx_conditions_run_clean_through_the_production_entry_point(self):
        for tx in (False, True):
            with self.subTest(tx_during_rx=tx):
                d = Path(tempfile.mkdtemp(prefix="rigpty_"))
                self.addCleanup(lambda p=d: __import__("shutil").rmtree(p, ignore_errors=True))
                port = self.ports()
                run = rig.Run(f"pty tx={tx}", repetitions=1, seconds=60.0, tx_during_rx=tx)
                res = run.execute(port, fd=port.fileno(), out_dir=d, sleep=lambda s: None, read_timeout=0.05)
                rep = res["repetition_results"][0]
                self.assertEqual(rep["ended"], "complete")
                self.assertEqual(res["losses"], 0, rep["defects_by_kind"])
                self.assertEqual(res["denominator_bytes"], res["bytes_sent"] if not tx else res["denominator_bytes"])
                self.assertGreater(rep["reads"], 10)                    # incremental, not one read
                self.assertFalse(res["counters_after"]["available"])    # a pty has none, and says so
                self.assertTrue((d / "run.json").is_file())

    def test_a_drop_injected_into_a_pty_capture_is_still_localised(self):
        frames = rig.plan_frames("p", 0)
        port = self.ports()
        rep = rig.Repetition(index=0, frames=frames)
        rig.Driver(port, port, port, tx_during_rx=False, read_timeout=0.05).run(rep, time.monotonic() + 60)
        received = bytes(rep.received)
        self.assertEqual(len(received), len(rig.stream_bytes(frames)))
        rec = next(f for f in frames if f.kind == "REC")
        res = rig.analyse(frames, received[:rec.offset + 7] + received[rec.offset + 8:], rig.token_for("p", 0))
        self.assertEqual(res["losses"], 1)
        self.assertEqual(res["divergence"]["frame_index"], rec.index)
        self.assertEqual(res["divergence"]["offset_in_frame"], 7)


class TheProfileIsDerivedFromTheSessions(unittest.TestCase):
    LOG = R / rig.PROFILE_SOURCE

    def test_the_frozen_profile_is_what_the_clean_session_transmitted(self):
        got = rig.profile_from_log(self.LOG)["frames"]
        self.assertNotIn("UNKNOWN", got)
        self.assertEqual(sorted(got), sorted(k for k, _, _, _ in rig.SESSION_PROFILE))
        for kind, count, lo, hi in rig.SESSION_PROFILE:
            self.assertEqual(got[kind]["count"], count, kind)
            self.assertEqual((got[kind]["min"], got[kind]["max"]), (lo, hi), kind)
        self.assertEqual(sum(e["count"] for e in got.values()), rig.FRAMES_PER_PROFILE)

    @staticmethod
    def split_controls(damaged: list):
        """The session's two FORCED controls are, by its design, the first damaged SIGNREQ seq 1
        and the first damaged REC seq 1 — identified by that rule, not by a byte offset."""
        controls, events, fragments = [], [], []
        for c in damaged:
            first = not any(k["type"] == c["type"] for k in controls)
            if c["type"] in ("SIGNREQ", "REC") and c.get("seq") == 1 and first:
                controls.append(c)
            elif c["type"] == "UNKNOWN":
                fragments.append(c)
            else:
                events.append(c)
        return controls, events, fragments

    def test_the_forced_controls_are_the_same_two_frames_in_every_complete_session(self):
        for name in ("b1q_17A6_2026-09-06-01", "b1q_17A6_2026-09-06-02", "b1q_17A6_2026-09-08-01"):
            d = rig.profile_from_log(R / "evidence/b1q" / name / "console.log")
            controls, events, fragments = self.split_controls(d["crc_failed"])
            self.assertEqual([(c["type"], c["seq"], c["offset"]) for c in controls],
                             [("SIGNREQ", 1, 1105), ("REC", 1, 6463)], name)
            self.assertEqual(fragments, [], name)
            self.assertEqual(len(events), 1 if name.endswith("06-01") else 0, (name, events))

    def test_it_reproduces_the_owners_corrected_non_control_count(self):
        """The transport review of 2026-09-07 corrected the diagnosis to FOUR non-control CRC
        events across the three reviewed sessions plus one fragment; five was withdrawn."""
        events, fragments = [], []
        for name in ("b1q_17A6_2026-09-06-01", "b1q_17A6_2026-09-06-02", "b1q_17A6_2026-09-06-03"):
            d = rig.profile_from_log(R / "evidence/b1q" / name / "console.log")
            _, e, f = self.split_controls(d["crc_failed"])
            events += [(name, c["type"], c["offset"]) for c in e]
            fragments += [(name, c["type"], c["offset"]) for c in f]
        self.assertEqual(len(events), 4, events)
        self.assertEqual(len(fragments), 1, fragments)
        self.assertEqual({t for _, t, _ in events}, {"TERM", "HB", "REC", "AUDIT"})


if __name__ == "__main__":
    unittest.main()
