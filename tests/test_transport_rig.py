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
import types
import unittest
import unittest.mock
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
            kinds[s["reply"]] = kinds.get(s["reply"], 0) + 1
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
        self.assertIn("received bytes", res["denominator"])


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

    def trace_port(self, name="trace", clock=None):
        """A port that records what IT was asked to do — the host's frames are real rel-v4 now,
        so a classifier that looks at the bytes cannot tell source from host: the PORT does."""
        events = []

        def write(data, timeout=None):
            events.append({"op": "write", "t": clock(), "bytes": len(data), "port": name,
                           "timeout": timeout})
            return len(data)

        def read(t):
            events.append({"op": "read", "t": clock(), "timeout": t})
            return b""
        return rig.callable_port(name, write, read, takes_timeout=True), events

    def test_the_stream_is_written_frame_by_frame_and_drained_between(self):
        now = [0.0]
        port, events = self.trace_port(clock=lambda: now[0])
        rep = rig.Repetition(index=0, frames=rig.plan_frames("t", 0))
        rig.Driver(port, port, port, tx_during_rx=False, sleep=lambda s: None, clock=lambda: now[0]).run(rep, 1e9)
        writes = [e for e in events if e["op"] == "write"]
        self.assertEqual(len(writes), 302)                       # not one big write
        self.assertGreaterEqual(sum(1 for e in events if e["op"] == "read"), 302)

    def test_host_traffic_goes_to_the_host_port_at_its_scheduled_points(self):
        now = [0.0]
        source, s_events = self.trace_port("source", clock=lambda: now[0])
        host, h_events = self.trace_port("host", clock=lambda: now[0])
        capture, _ = self.trace_port("capture", clock=lambda: now[0])
        rep = rig.Repetition(index=0, frames=rig.plan_frames("t", 0))
        rig.Driver(source, host, capture, tx_during_rx=True,
                   sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0]).run(rep, 1e9)
        self.assertEqual(len([e for e in s_events if e["op"] == "write"]), 302)
        self.assertEqual(len([e for e in h_events if e["op"] == "write"]), 125)   # the derived schedule
        # the schedule is CONSUMED: the events interleave, they do not all follow the stream
        ordered = [e["op"] for e in rep.events]
        self.assertIn("write_host", ordered)
        self.assertLess(ordered.index("write_host"), len(ordered) - 1)
        self.assertEqual(sum(rep.host_writes.values()), 125)      # the echo ledger, by line

    def test_the_host_frames_are_rel_v4_with_a_justified_length_profile(self):
        """Not `COMMAND seq\n` at 9-14 bytes: the instrument builds every host reply with
        build_line and a payload — `{"seq": n}` for the acknowledgements, the signer's
        `sign_reply` for SIGNOK — so the rig's do too, and their lengths follow from that."""
        import l5_notary as l5
        frames = rig.plan_frames("t", 0)
        shape = rig.host_traffic_shape(frames)
        self.assertEqual(shape["frames"], 125)
        self.assertGreater(shape["bytes"], 10000)                  # real wire occupancy
        for s in rig.host_schedule(frames):
            parsed = l5.parse_line(s["line"].decode())              # a real frame, real CRC
            self.assertEqual(parsed["type"], s["reply"])
            self.assertEqual(parsed["token"], rig.token_for("t", 0))
        lengths = {s["reply"]: len(s["line"]) for s in rig.host_schedule(frames)}
        self.assertGreater(lengths["SIGNOK"], 400)                  # the signed answer
        for ack in ("IDENTACK", "AUDITGET", "RECACK", "AUDITDONE", "TERMACK"):
            self.assertTrue(65 <= lengths[ack] <= 90, (ack, lengths[ack]))

    def test_the_signok_length_matches_the_archived_answer(self):
        """The SIGNOK payload shape is taken from the archived notary log, not invented: building
        the real answer with the real builder gives the same length as the rig's."""
        import l5_notary as l5
        log = json.loads((R / rig.HOST_PAYLOAD_SOURCE).read_text())
        entry = log["notary_log"]["entries"][0]
        token = log["notary_log"]["token"]
        archived = len(l5.build_line("SIGNOK", entry["seq"], token, l5.encode_payload(entry["answer"])))
        ours = len(rig.host_frame("SIGNOK", entry["seq"], token))
        self.assertEqual(sorted(entry["answer"]), sorted(rig.host_payload("SIGNOK", entry["seq"])))
        self.assertLessEqual(abs(archived - ours), 2, (archived, ours))

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

    def budgeted(self, consume_read: bool, now):
        """A transport whose reader consumes exactly the timeout it is given — the owner's probe.
        Nothing here can overrun unless the driver asks it to."""
        def write(data, timeout=None):
            self.asked.append({"op": "write", "t": now[0], "timeout": timeout})
            return len(data)

        def read(t):
            self.asked.append({"op": "read", "t": now[0], "timeout": t})
            if consume_read:
                now[0] += t
            return b""
        return rig.callable_port("budgeted", write, read, takes_timeout=True)

    def test_the_deadline_bounds_the_read(self):
        """The counterexample: a 0.01 s limit, a reader that consumes its whole timeout, and the
        driver asked for 0.05 s and then started a host write at t=0.05 — after expiry."""
        self.asked, now = [], [0.0]
        port = self.budgeted(True, now)
        res = rig.Run("bounded", repetitions=1, seconds=0.01, tx_during_rx=True).execute(
            port, sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0])
        self.assertLessEqual(now[0], 0.01)
        self.assertTrue(all(e["timeout"] is None or e["timeout"] <= 0.01 for e in self.asked), self.asked)
        self.assertIn("deadline", res["stopped"])
        self.assertTrue(res["incomplete"])
        self.assertFalse(res["completed_exposure"])

    def test_the_deadline_bounds_the_source_write_and_the_host_write(self):
        """Every write is given the REMAINING budget, so a transport that can bound a write does.
        A post-operation check cannot stop a write that has already blocked."""
        self.asked, now = [], [0.0]
        port = self.budgeted(False, now)
        rig.Run("bounded", repetitions=1, seconds=0.5, tx_during_rx=True).execute(
            port, sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0])
        writes = [e for e in self.asked if e["op"] == "write"]
        self.assertTrue(writes)
        for w in writes:
            self.assertIsNotNone(w["timeout"])
            self.assertLessEqual(w["timeout"], 0.5)
            self.assertGreaterEqual(w["timeout"], 0.0)

    def test_the_deadline_bounds_the_scheduled_gap(self):
        """A gap is capped by what is left, so waiting cannot overrun."""
        now, slept = [0.0], []
        port = rig.callable_port("x", lambda d, t=None: len(d), lambda t: b"", takes_timeout=True)

        def sleep(s):
            slept.append(s)
            now[0] += s
        res = rig.Run("gap", repetitions=1, seconds=0.02, tx_during_rx=True).execute(
            port, sleep=sleep, clock=lambda: now[0])
        self.assertLessEqual(now[0], 0.02)
        self.assertTrue(all(x <= 0.02 for x in slept), slept)
        self.assertIn("deadline", res["stopped"])

    def test_the_deadline_bounds_a_paced_source(self):
        now = [0.0]
        port = rig.callable_port("p", lambda d, t=None: len(d), lambda t: b"", takes_timeout=True)
        res = rig.Run("paced", repetitions=1, seconds=0.05, tx_during_rx=False).execute(
            port, sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0], pace=True)
        self.assertLessEqual(now[0], 0.05)
        self.assertIn("deadline", res["stopped"])
        self.assertLess(res["frames_accepted"], 302)

    def test_a_serial_port_is_opened_exclusively_and_with_a_write_timeout(self):
        """An unbounded serial write cannot be stopped by any later check."""
        seen = {}

        class FakeSerial:
            def __init__(self, *a, **k):
                seen.update({"args": a, "kwargs": k})
                self.write_timeout = None
                self.timeout = None

            def write(self, data):
                seen["write_timeout_at_write"] = self.write_timeout
                return len(data)

            def read(self, n):
                return b""

            def fileno(self):
                return 7

            def close(self):
                seen["closed"] = True
        with unittest.mock.patch.dict(sys.modules, {"serial": types.SimpleNamespace(Serial=FakeSerial)}):
            port = rig.serial_port("NOT-A-DEVICE")
            port.write(b"x", 0.25)
            port.close()
        self.assertTrue(seen["kwargs"]["exclusive"])
        self.assertEqual(seen["kwargs"]["write_timeout"], rig.WRITE_TIMEOUT_S)
        self.assertEqual(seen["write_timeout_at_write"], 0.25)
        self.assertTrue(seen["closed"])                                        # the adapter's close is wired through

    def test_the_paced_model_puts_host_traffic_inside_the_source_transmission(self):
        """The independent variable of A1/B1. The source transmits continuously; a reply is due
        the measured gap after the frame that caused it, which lands while a LATER frame is on
        the wire. The first version's replies all fell after the source had finished."""
        now, busy, overlaps = [0.0], [0.0], []

        def source_write(data, timeout=None):
            busy[0] = now[0] + len(data) * rig.BYTE_TIME_S
            return len(data)

        def host_write(data, timeout=None):
            overlaps.append(now[0] < busy[0])
            return len(data)
        source = rig.callable_port("source", source_write, lambda t: b"", takes_timeout=True)
        host = rig.callable_port("host", host_write, lambda t: b"", takes_timeout=True)
        rep = rig.Repetition(index=0, frames=rig.plan_frames("t", 0))
        rig.Driver(source, host, source, tx_during_rx=True, pace=True,
                   sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0]).run(rep, 1e9)
        self.assertEqual(len(overlaps), 125)
        self.assertGreater(sum(overlaps), 100)                       # the overlap is real, not zero
        self.assertEqual(sum(1 for o in rep.overlap if o["overlapping"]), sum(overlaps))
        self.assertAlmostEqual(now[0], sum(f.bytes for f in rep.frames) * rig.BYTE_TIME_S, delta=0.2)

    def test_the_no_tx_control_writes_nothing_on_the_host_port(self):
        now = [0.0]
        source, _ = self.trace_port("source", clock=lambda: now[0])
        host, h_events = self.trace_port("host", clock=lambda: now[0])
        rep = rig.Repetition(index=0, frames=rig.plan_frames("t", 0))
        rig.Driver(source, host, source, tx_during_rx=False, pace=True,
                   sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0]).run(rep, 1e9)
        self.assertEqual([e for e in h_events if e["op"] == "write"], [])
        self.assertEqual(rep.overlap, [])
        self.assertEqual(rep.host_writes, {})


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

    def test_each_export_component_fails_on_its_own(self):
        """P2-5: one outer try meant that failing events_000.json left run.json unwritten. Start
        from a successful production run, fail ONE component at a time, and assert what survives."""
        for target in ("capture_000.bin", "events_000.json", "run.json"):
            with self.subTest(failed=target):
                d = Path(tempfile.mkdtemp(prefix="rigcomp_"))
                self.addCleanup(lambda p=d: __import__("shutil").rmtree(p, ignore_errors=True))
                port, _ = loopback()
                real_text, real_bytes = Path.write_text, Path.write_bytes

                def text(path, data, *a, _t=target, **k):
                    if path.name == _t:
                        raise OSError(f"injected {_t} failure")
                    return real_text(path, data, *a, **k)

                def raw(path, data, *a, _t=target, **k):
                    if path.name == _t:
                        raise OSError(f"injected {_t} failure")
                    return real_bytes(path, data, *a, **k)
                with unittest.mock.patch.object(Path, "write_text", text), \
                        unittest.mock.patch.object(Path, "write_bytes", raw):
                    res = rig.Run("component", repetitions=1, tx_during_rx=False).execute(
                        port, out_dir=d, sleep=lambda s: None)
                self.assertFalse(res["export_complete"])
                self.assertTrue(any(target in e for e in res["export_errors"]), res["export_errors"])
                survivors = sorted(f.name for f in d.iterdir())
                if target == "run.json":
                    self.assertIn("run.min.json", survivors)      # a minimal summary rather than none
                    self.assertIn("capture_000.bin", survivors)
                    minimal = json.loads((d / "run.min.json").read_text())
                    self.assertFalse(minimal["export_complete"])
                else:
                    self.assertIn("run.json", survivors)          # the summary is ALWAYS attempted
                    on_disk = json.loads((d / "run.json").read_text())
                    self.assertFalse(on_disk["export_complete"])
                    self.assertTrue(on_disk["export_errors"])

    def test_a_provenance_failure_does_not_replace_the_primary_error(self):
        """P2-5's second boundary: a read failure while provenance hashes the framing module
        raised a NEW OSError out of the summary, discarding the detach and its captured bytes."""
        port, _ = whole_stream(fail_after=400)
        real = Path.read_bytes
        framing = Path(rig.l5.__file__)

        def bad(path):
            if path == framing:
                raise OSError("injected provenance read failure")
            return real(path)
        with unittest.mock.patch.object(Path, "read_bytes", bad):
            with self.assertRaises(rig.RigError) as cm:
                rig.Run("prov", repetitions=3, tx_during_rx=False).execute(
                    port, out_dir=self.d, sleep=lambda s: None)
        self.assertIsInstance(cm.exception.__cause__, OSError)
        self.assertIn("synthetic detach", str(cm.exception.__cause__))    # the PRIMARY error
        self.assertIsNotNone(cm.exception.result)
        on_disk = json.loads((self.d / "run.json").read_text())
        self.assertTrue(on_disk["provenance"]["unavailable"])
        self.assertIn("injected provenance read failure", on_disk["provenance"]["error"])
        self.assertTrue((self.d / "capture_000.bin").is_file())

    def test_a_counter_failure_is_recorded_not_raised(self):
        port, _ = loopback()
        real = rig.read_icounters
        try:
            rig.read_icounters = lambda fd: (_ for _ in ()).throw(OSError("counter boom"))
            res = rig.Run("counters", repetitions=1, tx_during_rx=False).execute(
                port, fd=1, out_dir=self.d, sleep=lambda s: None)
        finally:
            rig.read_icounters = real
        self.assertTrue(res["counters_after"]["unavailable"])
        self.assertIn("counter boom", res["counters_after"]["error"])
        self.assertTrue((self.d / "run.json").is_file())

    def test_an_unwritable_export_is_recorded_and_does_not_replace_the_error(self):
        port, _ = whole_stream(fail_after=400)
        blocked = self.d / "file"
        blocked.write_text("not a directory")
        with self.assertRaises(rig.RigError) as cm:
            rig.Run("detach", repetitions=2, tx_during_rx=False).execute(
                port, out_dir=blocked / "under", sleep=lambda s: None)
        self.assertIsInstance(cm.exception.__cause__, OSError)
        self.assertIn("synthetic detach", str(cm.exception.__cause__))
        self.assertFalse(cm.exception.result["export_complete"])
        self.assertTrue(cm.exception.result["export_errors"])


class OnlyCompleteLinesAndAccountedEchoes(unittest.TestCase):
    """P2-1: what may be credited, and what may be normalised away.

    Every case the review names: a complete stream, one legitimate echo, a missing final
    newline, extra echo copies, blank lines with and without an echo, an echo on a topology that
    does not echo, and a failed host write followed by apparent echo bytes.
    """

    def setUp(self):
        self.frames = rig.plan_frames("t", 0)
        self.stream = rig.stream_bytes(self.frames)
        self.echo = rig.host_schedule(self.frames)[0]["line"]

    def test_the_complete_stream(self):
        res = rig.analyse(self.frames, self.stream)
        self.assertTrue(res["clean"])
        self.assertEqual(res["bytes_fragment"], 0)

    def test_one_legitimate_echo(self):
        res = rig.analyse(self.frames, self.stream + self.echo,
                          echo_ledger={self.echo: 1}, echo_allowed=True)
        self.assertTrue(res["clean"], res["defects_by_kind"])
        self.assertEqual(res["host_echo_lines"], 1)
        self.assertEqual(res["bytes_host_echo"], len(self.echo))
        self.assertEqual(res["losses"], 0)

    def test_a_missing_final_newline_is_a_fragment_not_a_delivery(self):
        """The counterexample: 302 delivered and zero losses over 98 598 of 98 599 bytes."""
        res = rig.analyse(self.frames, self.stream[:-1])
        self.assertEqual(res["frames_delivered"], 301)
        self.assertEqual(res["losses"], 1)
        self.assertEqual(res["defects_by_kind"], {"fragment": 1})
        self.assertEqual(res["bytes_fragment"], len(self.frames[-1].line) - 1)
        self.assertFalse(res["clean"])

    def test_extra_echo_copies_are_defects(self):
        """One authorised echo appended a hundred times used to be clean."""
        res = rig.analyse(self.frames, self.stream + self.echo * 100,
                          echo_ledger={self.echo: 1}, echo_allowed=True)
        self.assertEqual(res["host_echo_lines"], 1)
        self.assertEqual(res["defects_by_kind"], {"unexpected_echo": 99})
        self.assertFalse(res["clean"])

    def test_blank_lines_are_defects_with_or_without_an_echo(self):
        for ledger, allowed, extra in (({self.echo: 1}, True, self.echo), (None, False, b"")):
            with self.subTest(echo=bool(extra)):
                res = rig.analyse(self.frames, self.stream + b"\n" * 100 + extra,
                                  echo_ledger=ledger, echo_allowed=allowed)
                self.assertEqual(res["defects_by_kind"].get("empty_line"), 100)
                self.assertFalse(res["clean"])

    def test_an_echo_on_a_topology_that_does_not_echo(self):
        res = rig.analyse(self.frames, self.stream + self.echo,
                          echo_ledger={self.echo: 1}, echo_allowed=False)
        self.assertEqual(res["host_echo_lines"], 0)
        self.assertEqual(res["defects_by_kind"], {"unexpected_echo": 1})
        self.assertIn("does not echo", res["defects"][0]["note"])
        self.assertFalse(res["clean"])

    def test_echo_bytes_after_a_host_write_that_failed(self):
        """A write that did not complete never enters the ledger, so bytes that look like its
        echo are unaccounted — the ledger counts SUCCESSFUL writes only."""
        res = rig.analyse(self.frames, self.stream + self.echo, echo_ledger={}, echo_allowed=True)
        self.assertEqual(res["host_echo_lines"], 0)
        self.assertFalse(res["clean"])
        self.assertGreaterEqual(res["unexpected_frames"] + len(res["defects"]), 1)

    def test_an_echo_does_not_normalise_anything_else_away(self):
        """The old `_without_echo` dropped any line that did not match, so merely having an echo
        activated a normalisation that hid bytes. Only the accounted occurrences are removed."""
        foreign = rig.build_frame(10 ** 6, "HB", 1, 66, rig.token_for("t", 0))
        res = rig.analyse(self.frames, self.stream + self.echo + foreign.line,
                          echo_ledger={self.echo: 1}, echo_allowed=True)
        self.assertEqual(res["host_echo_lines"], 1)
        self.assertEqual(res["defects_by_kind"], {"unexpected_index": 1})
        self.assertFalse(res["clean"])


class PartialRepetitions(unittest.TestCase):
    """P2-2: planned, attempted and accepted are three different numbers."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="rigpart_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.d, ignore_errors=True))

    def port_that_stops_after(self, frames: int):
        """Accepts `frames` source writes, then the reader detaches."""
        state = {"writes": 0, "buf": bytearray(), "reads": 0}

        def write(data, timeout=None):
            state["writes"] += 1
            state["buf"] += data
            return len(data)

        def read(_t):
            state["reads"] += 1
            if state["writes"] > frames:
                raise OSError("synthetic detach")
            out, state["buf"] = bytes(state["buf"]), bytearray()
            return out
        return rig.callable_port("stopping", write, read, takes_timeout=True), state

    def test_a_deadline_does_not_turn_untransmitted_frames_into_losses(self):
        """The counterexample: one IDENT written and read, then 302 sent and 301 losses."""
        now = [0.0]

        def read(t):
            now[0] += t
            return b""
        port = rig.callable_port("timed", lambda d, t=None: len(d), read, takes_timeout=True)
        res = rig.Run("deadline", repetitions=1, seconds=0.01, tx_during_rx=False).execute(
            port, out_dir=self.d, clock=lambda: now[0], sleep=lambda t: now.__setitem__(0, now[0] + t))
        self.assertEqual(res["frames_planned"], 302)
        self.assertEqual(res["frames_accepted"], 1)
        self.assertEqual(res["frames_sent"], 1)
        self.assertEqual(res["losses"], 0)                    # nothing was lost: it was never sent
        self.assertTrue(res["incomplete"])
        self.assertFalse(res["completed_exposure"])
        self.assertIn("deadline", res["stopped"])

    def test_a_detach_analyses_and_aggregates_the_partial_capture(self):
        """The counterexample: capture_000.bin held 1048 bytes while the summary said
        frames_sent 0, bytes_sent 0, denominator_bytes 0, losses 0."""
        port, _ = self.port_that_stops_after(1)
        with self.assertRaises(rig.RigError):
            rig.Run("detach", repetitions=1, tx_during_rx=False).execute(
                port, out_dir=self.d, sleep=lambda s: None)
        on_disk = json.loads((self.d / "run.json").read_text())
        raw = (self.d / "capture_000.bin").read_bytes()
        self.assertEqual(len(raw), 1048)                       # the IDENT
        self.assertEqual(on_disk["frames_accepted"], 2)        # the second write completed too
        self.assertEqual(on_disk["denominator_bytes"], 1048)   # the partial capture IS the denominator
        self.assertEqual(on_disk["losses"], 0)                 # nothing lost: the second was in flight
        self.assertEqual(on_disk["censored_in_flight"], 1)
        self.assertEqual(on_disk["repetitions_run"], 1)
        self.assertTrue(on_disk["incomplete"])
        self.assertIn("tool error", on_disk["stopped"])

    def test_a_detach_after_several_complete_frames(self):
        port, _ = self.port_that_stops_after(5)
        with self.assertRaises(rig.RigError):
            rig.Run("detach 5", repetitions=1, tx_during_rx=False).execute(
                port, out_dir=self.d, sleep=lambda s: None)
        on_disk = json.loads((self.d / "run.json").read_text())
        planned = rig.plan_frames(on_disk["run_id"], 0)
        self.assertEqual(on_disk["frames_accepted"], 6)
        self.assertEqual(on_disk["losses"], 0)
        self.assertEqual(on_disk["censored_in_flight"], 1)
        self.assertEqual((self.d / "capture_000.bin").stat().st_size, sum(f.bytes for f in planned[:5]))

    def test_a_write_that_fails_mid_repetition_is_uncertain_not_a_loss(self):
        state = {"n": 0}

        def write(data, timeout=None):
            state["n"] += 1
            if state["n"] == 4:
                raise OSError("write failed in flight")
            return len(data)
        port = rig.callable_port("flaky", write, lambda t: b"", takes_timeout=True)
        with self.assertRaises(rig.RigError):
            rig.Run("uncertain", repetitions=1, tx_during_rx=False).execute(
                port, out_dir=self.d, sleep=lambda s: None)
        on_disk = json.loads((self.d / "run.json").read_text())
        self.assertEqual(on_disk["frames_accepted"], 3)
        self.assertEqual(on_disk["frames_uncertain"], 1)       # the write that died in flight
        self.assertEqual(on_disk["losses"], 0)                 # the three that were sent arrived
        self.assertTrue(on_disk["incomplete"])

    def test_a_zero_loss_incomplete_run_is_not_a_completed_exposure(self):
        port, _ = self.port_that_stops_after(1)
        with self.assertRaises(rig.RigError) as cm:
            rig.Run("incomplete", repetitions=1, tx_during_rx=False).execute(
                port, out_dir=self.d, sleep=lambda s: None)
        res = cm.exception.result
        self.assertEqual(res["losses"], 0)
        self.assertFalse(res["completed_exposure"])
        self.assertTrue(res["incomplete"])


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


class TheWriterContract(unittest.TestCase):
    """The boundary review's P2-1: a writer's contract is declared and checked before any byte
    moves, never discovered by calling it — an exception from an active write is that write's
    failure, and a retry can deliver the bytes twice while reporting success."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="rigwc_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.d, ignore_errors=True))

    @staticmethod
    def side_effecting_writer():
        """Accepts the bytes, THEN fails internally — once. The counterexample's writer."""
        st = {"calls": [], "accepted": bytearray()}

        def write(data, timeout=None):
            st["calls"].append(timeout)
            st["accepted"] += data
            if len(st["calls"]) == 1:
                raise TypeError("internal writer failure after accepting bytes")
            return len(data)
        return write, st

    def test_a_writer_that_fails_after_accepting_bytes_is_called_exactly_once(self):
        """At 38c91b0: two calls with timeouts [0.25, None], `abcabc` accepted, 3 returned, no error."""
        write, st = self.side_effecting_writer()
        port = rig.callable_port("side-effecting", write, lambda t: b"", takes_timeout=True)
        with self.assertRaises(TypeError) as cm:
            port.write(b"abc", 0.25)
        self.assertEqual(str(cm.exception), "internal writer failure after accepting bytes")
        self.assertEqual(st["calls"], [0.25])                  # one invocation, with its budget
        self.assertEqual(bytes(st["accepted"]), b"abc")        # no hidden duplicate bytes

    def test_the_same_failure_inside_a_run_stops_it_with_the_frame_uncertain(self):
        """Through the production Run: one source write, no second source write, no host write
        after the error, the frame uncertain, the ORIGINAL exception as the cause."""
        write, st = self.side_effecting_writer()
        host_writes = []
        source = rig.callable_port("source", write, lambda t: b"", takes_timeout=True)
        host = rig.callable_port("host", lambda d, t=None: host_writes.append(d) or len(d),
                                 lambda t: b"", takes_timeout=True)
        with self.assertRaises(rig.RigError) as cm:
            rig.Run("uncertain write", repetitions=2).execute(source, host=host, capture=source,
                                                              out_dir=self.d, sleep=lambda s: None)
        self.assertIsInstance(cm.exception.__cause__, TypeError)
        self.assertEqual(len(st["calls"]), 1)                   # the source was written ONCE
        self.assertEqual(host_writes, [])                       # nothing followed the error
        on_disk = json.loads((self.d / "run.json").read_text())
        self.assertEqual(on_disk["error"], "TypeError: internal writer failure after accepting bytes")
        self.assertEqual(on_disk["terminal"]["reason"], "tool_error")
        self.assertEqual(on_disk["repetitions_run"], 1)
        self.assertEqual(on_disk["frames_uncertain"], 1)
        self.assertEqual(on_disk["frames_accepted"], 0)
        self.assertEqual(on_disk["losses"], 0)                  # nothing accepted, nothing lost
        self.assertFalse(on_disk["completed_exposure"])

    def test_both_declared_contracts_are_honoured_without_probing(self):
        """The two supported signatures as positive controls: each is called once, with exactly
        the arguments its declaration says, and neither is ever tried the other way."""
        one_arg, two_arg = [], []

        def w1(data):
            one_arg.append(data)
            return len(data)

        def w2(data, timeout):
            two_arg.append((data, timeout))
            return len(data)
        p1 = rig.callable_port("one", w1, lambda t: b"", takes_timeout=False)
        p2 = rig.callable_port("two", w2, lambda t: b"", takes_timeout=True)
        self.assertEqual(p1.write(b"xy", 0.5), 2)
        self.assertEqual(p2.write(b"xyz", 0.5), 3)
        self.assertEqual(one_arg, [b"xy"])
        self.assertEqual(two_arg, [(b"xyz", 0.5)])

    def test_a_declaration_that_contradicts_the_signature_is_refused_before_any_write(self):
        calls = []
        with self.assertRaises(rig.RigError) as cm:
            rig.callable_port("lies", lambda d: calls.append(d) or len(d), lambda t: b"", takes_timeout=True)
        self.assertIn("declared to take a timeout", str(cm.exception))
        self.assertEqual(calls, [])                              # refused without writing
        with self.assertRaises(rig.RigError):                    # and the other way round
            rig.callable_port("lies", lambda d, t: len(d), lambda t: b"", takes_timeout=False)

    def test_an_uninspectable_writer_is_taken_as_declared(self):
        """A builtin has no inspectable signature: the declaration stands, and is still not probed."""
        buf = bytearray()
        port = rig.callable_port("builtin", buf.extend, lambda t: b"", takes_timeout=False)
        with self.assertRaises(rig.RigError):                    # extend returns None: refused as such
            port.write(b"ab")
        self.assertEqual(bytes(buf), b"ab")                      # written once, not twice


class ObservationIsNotDelivery(unittest.TestCase):
    """The boundary review's P2-2: at a cutoff, a frame is censored only when NOTHING of it was
    observed. A complete damaged line, an altered frame or an identifying fragment is an
    observation, and a cutoff never turns observed damage into in-flight traffic."""

    def setUp(self):
        self.frames = rig.plan_frames("cut", 0)
        self.token = rig.token_for("cut", 0)

    def stream(self, upto: int) -> bytes:
        return rig.stream_bytes(self.frames[:upto])

    def both(self, expected, received):
        """The same bytes under normal completion and under a cutoff."""
        return (rig.analyse(expected, received, self.token, censor_tail=False),
                rig.analyse(expected, received, self.token, censor_tail=True))

    def test_a_complete_crc_failure_at_the_tail_is_a_loss_under_a_cutoff_too(self):
        """The counterexample: one accepted IDENT, the whole 1048-byte line with one byte changed.
        At 38c91b0 normal completion said 1 loss and the cutoff said 0 loss, frame 0 censored."""
        one = self.frames[:1]
        bad = flip(one[0].line, 60)
        normal, cut = self.both(one, bad)
        for res in (normal, cut):
            self.assertEqual(res["losses"], 1)
            self.assertEqual(res["censored"], [])
            self.assertEqual(res["unresolved"], [])
            self.assertEqual(res["defects_by_kind"], {"crc_failed": 1})
            self.assertEqual(res["observed"], [0])
            self.assertEqual(res["observed_damaged"], {"0": "crc_failed"})
        self.assertEqual(cut["cutoff"]["observation_frontier"], 0)
        self.assertFalse(cut["cutoff"]["ambiguous"])

    def test_complete_silence_is_censored_and_stays_distinguishable(self):
        normal, cut = self.both(self.frames[:1], b"")
        self.assertEqual((normal["losses"], normal["censored"]), (1, []))
        self.assertEqual((cut["losses"], cut["censored"], cut["observed"]), (0, [0], []))

    def test_a_valid_crc_alteration_at_the_tail_is_a_loss_under_a_cutoff(self):
        one = self.frames[:1]
        parsed = rig.l5.parse_line(one[0].line.decode())
        altered = rig.l5.build_line(parsed["type"], parsed["seq"], parsed["token"],
                                    parsed["payload"][:-4] + "AAAA").encode()
        _, cut = self.both(one, altered)
        self.assertEqual(cut["losses"], 1)
        self.assertEqual(cut["damaged"], [0])
        self.assertEqual(cut["censored"], [])

    def test_a_later_damaged_arrival_moves_the_frontier(self):
        """Frames 0-2 delivered, frame 3 absent, frame 4 arrives CRC-damaged, frames 5.. nothing.
        Frame 3 is a loss (something later was observed), frame 4 is a loss (observed damaged),
        5.. are censored. At 38c91b0 the frontier was max(delivered) = 2, hiding both."""
        expected = self.frames[:8]
        received = self.stream(3) + flip(self.frames[4].line, 30)     # a 65-byte HB, hit in its token
        _, cut = self.both(expected, received)
        self.assertEqual(cut["losses"], 2)
        self.assertEqual(cut["missing"], [3, 4])
        self.assertEqual(cut["censored"], [5, 6, 7])
        self.assertEqual(cut["unresolved"], [])
        self.assertEqual(cut["cutoff"]["observation_frontier"], 4)
        self.assertEqual(cut["defects"][0]["identified_by"], "near")   # header damaged; same length, 1 byte off

    def test_a_genuinely_partial_line_is_censored_as_partial(self):
        """Frames 0-1 delivered, half of frame 2: frame 2 was arriving — censored, 0 losses."""
        expected = self.frames[:5]
        received = self.stream(2) + self.frames[2].line[:len(self.frames[2].line) // 2]
        normal, cut = self.both(expected, received)
        self.assertEqual((cut["losses"], cut["censored"], cut["unresolved"]), (0, [2, 3, 4], []))
        self.assertEqual(cut["cutoff"]["partial_frame"], 2)
        self.assertEqual(cut["defects"][0]["identified_by"], "prefix")
        self.assertEqual(cut["defects_by_kind"], {"fragment": 1})
        self.assertEqual(normal["losses"], 3)                    # without a cutoff they are all losses

    def test_a_partial_line_of_a_later_frame_makes_the_skipped_one_a_loss(self):
        """Frames 0-1 delivered, frame 2 absent, half of frame 3: frame 2 is a loss, 3.. censored."""
        expected = self.frames[:5]
        received = self.stream(2) + self.frames[3].line[:len(self.frames[3].line) // 2]
        _, cut = self.both(expected, received)
        self.assertEqual((cut["losses"], cut["missing"], cut["censored"]), (1, [2], [3, 4]))

    def test_unidentifiable_damage_after_the_frontier_is_unresolved_not_censored(self):
        """Frame 0 delivered, then a complete line whose header is destroyed. Something above the
        frontier was observed damaged and cannot be told which: the frames above are reported as
        UNRESOLVED — not losses (that would be inventing which), and not in flight (that would be
        asserting zero damage that was observed)."""
        expected = self.frames[:4]
        garbage = b"~" * (len(self.frames[1].line) + 7) + b"\n"       # no header, no length, nothing
        _, cut = self.both(expected, self.stream(1) + garbage)
        self.assertEqual(cut["confirmed_losses"], 0)             # nothing is DEFINITELY lost …
        self.assertIsNone(cut["losses"])                         # … and the total is not known
        self.assertFalse(cut["losses_known"])
        self.assertEqual(cut["losses_upper_bound"], 3)           # at most the three unresolved
        self.assertEqual(cut["censored"], [])
        self.assertEqual(cut["unresolved"], [1, 2, 3])
        self.assertTrue(cut["cutoff"]["ambiguous"])
        self.assertEqual(cut["cutoff"]["unidentified_after_frontier"], 1)
        self.assertFalse(cut["clean"])

    def test_two_frames_merged_by_a_lost_newline_are_not_one_identified_frame(self):
        """Frames 1 and 2 with the newline between them gone: one line with two headers. It
        identifies neither, so frames 1.. are unresolved rather than 2.. censored behind 1."""
        expected = self.frames[:4]
        merged = self.frames[1].line[:-1] + self.frames[2].line
        _, cut = self.both(expected, self.stream(1) + merged)
        self.assertEqual(cut["unresolved"], [1, 2, 3])
        self.assertEqual(cut["censored"], [])
        self.assertIsNone(cut["losses"])

    def test_the_cutoff_report_flows_through_a_run(self):
        """Through the production Run: the transport damages the LAST frame it accepts before the
        reader detaches. The damaged line is observed; it is a loss, not censored."""
        state = {"writes": 0, "buf": bytearray()}

        def write(data, timeout=None):
            state["writes"] += 1
            if state["writes"] == 3:
                data = flip(data, 20)                    # a 65-byte HB, hit inside its token
            state["buf"] += data
            return len(data)

        def read(_t):
            if state["writes"] >= 3 and not state["buf"]:
                raise OSError("synthetic detach")
            out, state["buf"] = bytes(state["buf"]), bytearray()
            return out
        d = Path(tempfile.mkdtemp(prefix="rigcut_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        with self.assertRaises(rig.RigError):
            rig.Run("damaged then detached", repetitions=1, tx_during_rx=False).execute(
                rig.callable_port("p", write, read, takes_timeout=True), out_dir=d, sleep=lambda s: None)
        on_disk = json.loads((d / "run.json").read_text())
        rep = on_disk["repetition_results"][0]
        self.assertTrue(rep["cut_short"])
        self.assertEqual(rep["losses"], 1)
        self.assertEqual(rep["observed_damaged"], {"2": "crc_failed"})
        self.assertEqual(on_disk["losses"], 1)
        self.assertEqual(on_disk["censored_in_flight"], rep["censored_in_flight"])


class TheTerminalReason(unittest.TestCase):
    """The boundary review's P2-3: a run states WHY it ended, and `completed_exposure` follows
    from that reason and the traffic state — never from the count of accepted writes. An
    analyser failure is a tool error: losses stay unknown and nothing more is transmitted."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="rigterm_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.d, ignore_errors=True))

    @staticmethod
    def memory_loopback(damage_first: int = 0):
        state = {"queued": bytearray(), "writes": 0}

        def write(data, timeout=None):
            state["writes"] += 1
            if state["writes"] <= damage_first:
                data = flip(data, 50)
            state["queued"] += data
            return len(data)

        def read(_t):
            out, state["queued"] = bytes(state["queued"]), bytearray()
            return out
        return rig.callable_port("memory loopback", write, read, takes_timeout=True), state

    def persisted(self, name):
        return json.loads((self.d / name / "run.json").read_text())

    def check(self, returned, name, **expect):
        """The same fields on the returned result AND on the persisted run.json."""
        for where, res in (("returned", returned), ("persisted", self.persisted(name))):
            for k, v in expect.items():
                self.assertEqual(res[k] if k != "reason" else res["terminal"]["reason"], v, f"{where}: {k}")

    def test_the_two_repetition_zero_loss_control_still_completes(self):
        port, _ = self.memory_loopback()
        res = rig.Run("positive", repetitions=2, tx_during_rx=False).execute(
            port, out_dir=self.d / "positive", sleep=lambda t: None)
        self.check(res, "positive", reason="exposure_repetitions", exposure_reached=True,
                   traffic_resolved=True, completed_exposure=True, incomplete=False,
                   losses=0, losses_per_100k_bytes=0.0, repetitions_unanalysed=[], error=None)
        self.assertTrue(all(r["resolved"] for r in res["repetition_results"]))

    def test_an_early_loss_stop_is_not_a_completed_exposure(self):
        """The counterexample: 200 requested, three frames damaged in the first, the stop rule
        fires — and 38c91b0 said completed_exposure true, incomplete false."""
        port, state = self.memory_loopback(damage_first=3)
        res = rig.Run("three losses", repetitions=200, tx_during_rx=False).execute(
            port, out_dir=self.d / "stopped", sleep=lambda t: None)
        self.assertEqual(state["writes"], 302)                   # one repetition transmitted
        self.check(res, "stopped", reason="stop_rule_losses", exposure_reached=False,
                   traffic_resolved=True, completed_exposure=False, incomplete=True,
                   losses=3, repetitions_run=1)
        self.assertTrue(res["repetition_results"][0]["resolved"])   # the REPETITION did resolve
        self.assertIn("1 of 200 requested", res["stopped"])

    def test_a_deadline_during_the_drain_leaves_the_exposure_reached_but_not_complete(self):
        """The counterexample: every source write accepted, the clock expires while draining and
        nothing came back — 302 censored, and 38c91b0 said completed_exposure true."""
        now = [0.0]

        def write(data, timeout=None):
            if b" TERM " in data:
                now[0] = 1.0
            return len(data)
        port = rig.callable_port("accepted then cut", write, lambda t: b"", takes_timeout=True)
        res = rig.Run("drain cutoff", repetitions=2, seconds=1.0, tx_during_rx=False).execute(
            port, out_dir=self.d / "cutoff", sleep=lambda t: None, clock=lambda: now[0])
        self.check(res, "cutoff", reason="exposure_seconds_censored", exposure_reached=True,
                   traffic_resolved=False, completed_exposure=False, incomplete=True,
                   losses=0, censored_in_flight=302, denominator_bytes=0, repetitions_run=1)
        rep = res["repetition_results"][0]
        self.assertEqual(rep["frames_accepted"], 302)
        self.assertTrue(rep["cut_short"])
        self.assertTrue(rep["incomplete"])                        # not merely "fewer accepted than planned"
        self.assertFalse(rep["resolved"])
        self.assertIn("302 frames censored", res["stopped"])

    def test_a_time_bound_reached_between_resolved_repetitions_is_complete(self):
        """The registered time bound is a legitimate end (plan §5: 200 repetitions or 60 minutes,
        whichever first). Here the analysis of the first repetition consumes the budget, so the
        bound is reached BETWEEN repetitions with everything resolved."""
        now = [0.0]
        real = rig.analyse

        def slow_analyse(*a, **k):
            now[0] += 100.0
            return real(*a, **k)
        port, state = self.memory_loopback()
        with unittest.mock.patch.object(rig, "analyse", slow_analyse):
            res = rig.Run("time bound", repetitions=5, seconds=50.0, tx_during_rx=False).execute(
                port, out_dir=self.d / "bound", sleep=lambda t: None, clock=lambda: now[0])
        self.assertEqual(state["writes"], 302)
        self.check(res, "bound", reason="exposure_seconds", exposure_reached=True,
                   traffic_resolved=True, completed_exposure=True, incomplete=False, repetitions_run=1)

    def test_an_analyser_failure_stops_transmission_and_leaves_losses_unknown(self):
        """The counterexample: with the analyser raising after repetition 1, 38c91b0 went on to
        repetition 2 (604 source frames), returned normally with error null, 'completed' in the
        stop message and a loss rate of 0.0."""
        port, state = self.memory_loopback()
        with unittest.mock.patch.object(rig, "analyse", side_effect=ValueError("injected analyser failure")):
            with self.assertRaises(rig.RigError) as cm:
                rig.Run("analysis unavailable", repetitions=2, tx_during_rx=False).execute(
                    port, out_dir=self.d / "analysis", sleep=lambda t: None)
        self.assertEqual(state["writes"], 302)                   # NO second repetition started
        self.assertIsInstance(cm.exception.__cause__, ValueError)
        res = cm.exception.result
        self.check(res, "analysis", reason="analysis_unavailable", exposure_reached=False,
                   traffic_resolved=False, completed_exposure=False, incomplete=True,
                   losses=None, losses_per_100k_bytes=None, repetitions_unanalysed=[0],
                   repetitions_run=1, error="ValueError: injected analyser failure",
                   export_complete=True)                          # files written; not a valid measurement
        rep = res["repetition_results"][0]
        self.assertFalse(rep["analysis_available"])
        self.assertIsNone(rep["losses"])
        self.assertIn("tool error", res["stopped"])
        self.assertIn("unknown", res["stopped"])
        self.assertNotIn("completed", res["stopped"])
        self.assertIn("loss metric unknown", res["denominator"])
        self.assertTrue((self.d / "analysis" / "capture_000.bin").stat().st_size > 0)  # the evidence

    def test_an_analyser_failure_after_a_driver_failure_is_secondary(self):
        """Both fail in the same repetition: the driver's error is primary, the analyser's is
        recorded as secondary, nothing is lost and nothing is substituted."""
        def write(data, timeout=None):
            raise OSError("primary detach")
        port = rig.callable_port("dead", write, lambda t: b"", takes_timeout=True)
        with unittest.mock.patch.object(rig, "analyse", side_effect=ValueError("secondary")):
            with self.assertRaises(rig.RigError) as cm:
                rig.Run("both", repetitions=2, tx_during_rx=False).execute(
                    port, out_dir=self.d / "both", sleep=lambda t: None)
        self.assertIsInstance(cm.exception.__cause__, OSError)
        res = cm.exception.result
        self.assertEqual(res["terminal"]["reason"], "tool_error")
        self.assertEqual(res["error"], "OSError: primary detach")
        self.assertEqual(res["secondary_errors"], ["analysis of repetition 0: ValueError: secondary"])
        self.assertIsNone(res["losses"])

    def test_every_terminal_reason_is_one_the_tool_names(self):
        self.assertEqual(set(rig.TERMINAL_REASONS), {
            "exposure_repetitions", "exposure_seconds", "exposure_seconds_censored",
            "stop_rule_losses", "tool_error", "analysis_unavailable"})


class TheLossMetric(unittest.TestCase):
    """The uncertainty review's P2: a confirmed count is a lower bound, not the total. The total
    and its rate are numbers only when every repetition was analysed and nothing is unresolved;
    otherwise the total is null with a named reason and the bounds are reported separately, so
    an uninterpretable capture and an intact frame never share an unqualified zero rate."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="rigmetric_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.d, ignore_errors=True))

    def owner_double(self, shape: str):
        """The review's fixture: a 0.01 s budget, a cooperative reader that spends it, one IDENT
        accepted, and the capture returning the shape named."""
        now, queued = [0.0], [b""]

        def write(data, timeout=None):
            if shape == "intact":
                queued[0] += data
            elif shape == "known_crc_damage":
                queued[0] += flip(data, 60)
            elif shape == "unidentifiable_damage":
                queued[0] += b"garbled\n"
            return len(data)                                     # "silence": accepted, nothing back

        def read(t):
            now[0] += t
            out, queued[0] = queued[0], b""
            return out
        port = rig.callable_port("owner double", write, read, takes_timeout=True)
        return port, now

    def run_shape(self, shape: str, **kw):
        port, now = self.owner_double(shape)
        res = rig.Run(shape, repetitions=200, seconds=0.01, tx_during_rx=False, **kw).execute(
            port, out_dir=self.d / shape, clock=lambda: now[0],
            sleep=lambda t: now.__setitem__(0, now[0] + t))
        return res, json.loads((self.d / shape / "run.json").read_text())

    def check(self, shape, **expect):
        returned, persisted = self.run_shape(shape)
        for where, res in (("returned", returned), ("persisted", persisted)):
            for k, v in expect.items():
                got = res["loss_metric"]["status"] if k == "metric" else res[k]
                self.assertEqual(got, v, f"{shape} {where}: {k}")
        return returned

    def test_intact_observed_bytes_are_an_exact_zero(self):
        res = self.check("intact", frames_accepted=1, confirmed_losses=0, losses=0, losses_upper_bound=0,
                         losses_per_100k_bytes=0.0, confirmed_losses_per_100k_bytes=0.0,
                         losses_per_100k_bytes_upper_bound=0.0, metric="exact", unresolved_at_cutoff=0)
        self.assertTrue(res["loss_metric"]["exact"])

    def test_a_fully_identified_corrupted_frame_is_one_exact_confirmed_loss(self):
        res = self.check("known_crc_damage", frames_accepted=1, confirmed_losses=1, losses=1,
                         losses_upper_bound=1, metric="exact", denominator_bytes=1048)
        self.assertAlmostEqual(res["losses_per_100k_bytes"], 100000 / 1048)
        self.assertEqual(res["losses_per_100k_bytes"], res["confirmed_losses_per_100k_bytes"])

    def test_unidentifiable_damage_at_a_cutoff_has_no_exact_rate(self):
        """The counterexample: one accepted IDENT, `garbled\\n` back, `losses_per_100k_bytes: 0.0`."""
        res = self.check("unidentifiable_damage", frames_accepted=1, denominator_bytes=8,
                         unresolved_at_cutoff=1, confirmed_losses=0, losses=None, losses_upper_bound=1,
                         losses_per_100k_bytes=None, confirmed_losses_per_100k_bytes=0.0,
                         metric="bounded", traffic_resolved=False, completed_exposure=False)
        self.assertFalse(res["loss_metric"]["exact"])
        self.assertIn("unresolved", res["loss_metric"]["reason"])
        self.assertAlmostEqual(res["losses_per_100k_bytes_upper_bound"], 100000 / 8)
        self.assertIn("bounded", res["denominator"])
        self.assertIsNone(res["repetition_results"][0]["losses"])
        self.assertFalse(res["repetition_results"][0]["losses_known"])

    def test_silence_has_no_rate_and_keeps_its_censored_state(self):
        res = self.check("silence", frames_accepted=1, denominator_bytes=0, censored_in_flight=1,
                         confirmed_losses=0, losses=0, losses_per_100k_bytes=None,
                         confirmed_losses_per_100k_bytes=None, losses_per_100k_bytes_upper_bound=None,
                         metric="no_denominator")
        self.assertEqual(res["repetition_results"][0]["censored"], [0])

    def mixed_double(self, damaged: int):
        """Frames 1..damaged arrive with one payload byte flipped (identified), the next write is
        replaced by garbage, and only then does the reader spend the budget."""
        st = {"writes": 0, "queued": b"", "now": 0.0}

        def write(data, timeout=None):
            st["writes"] += 1
            i = st["writes"] - 1
            n = len(data)                                            # the write is accepted in full …
            if 1 <= i <= damaged:
                data = flip(data, 60)
            elif i == damaged + 1:
                data = b"garbled\n"                                  # … whatever the capture gets back
            st["queued"] += data
            return n

        def read(t):
            if st["writes"] > damaged + 1:
                st["now"] += t
            out, st["queued"] = st["queued"], b""
            return out
        return rig.callable_port("mixed", write, read, takes_timeout=True), st

    def test_confirmed_losses_followed_by_unresolved_damage_keep_the_count_but_not_the_total(self):
        port, st = self.mixed_double(damaged=2)
        res = rig.Run("mixed", repetitions=200, seconds=0.01, tx_during_rx=False).execute(
            port, out_dir=self.d / "mixed", clock=lambda: st["now"],
            sleep=lambda t: st.__setitem__("now", st["now"] + t))
        for where, r in (("returned", res), ("persisted", json.loads((self.d / "mixed/run.json").read_text()))):
            self.assertEqual(r["frames_accepted"], 4, where)
            self.assertEqual(r["confirmed_losses"], 2, where)             # frames 1 and 2, definitely
            self.assertEqual(r["unresolved_at_cutoff"], 1, where)         # frame 3, cannot be told
            self.assertIsNone(r["losses"], where)                         # so the total is not 2
            self.assertEqual(r["losses_upper_bound"], 3, where)
            self.assertIsNone(r["losses_per_100k_bytes"], where)
            self.assertEqual(r["loss_metric"]["status"], "bounded", where)
            self.assertAlmostEqual(r["confirmed_losses_per_100k_bytes"], 2 * 100000 / r["denominator_bytes"])
            self.assertEqual(r["terminal"]["reason"], "exposure_seconds_censored", where)
        rep = res["repetition_results"][0]
        self.assertEqual(rep["observed_damaged"], {"1": "crc_failed", "2": "crc_failed"})
        self.assertEqual(rep["unresolved"], [3])

    def test_three_confirmed_losses_stop_the_run_whatever_is_unresolved(self):
        """The registered threshold counts DEFINITE losses; the stop rule outranks the deadline
        reason when both hold, and the total still stays unknown."""
        port, st = self.mixed_double(damaged=3)
        res = rig.Run("three then garbage", repetitions=200, seconds=0.01, tx_during_rx=False).execute(
            port, out_dir=self.d / "stop", clock=lambda: st["now"],
            sleep=lambda t: st.__setitem__("now", st["now"] + t))
        self.assertEqual(res["terminal"]["reason"], "stop_rule_losses")
        self.assertIn("3 confirmed losses", res["stopped"])
        self.assertEqual(res["confirmed_losses"], 3)
        self.assertIsNone(res["losses"])
        self.assertEqual(res["losses_upper_bound"], 4)

    def test_an_unanalysed_repetition_leaves_no_bound_either(self):
        """The previous round's null-rate case, now with the bounds: no total, no upper bound,
        the confirmed count of the analysed repetitions still stated."""
        state = {"queued": bytearray()}

        def write(data, timeout=None):
            state["queued"] += data
            return len(data)

        def read(_t):
            out, state["queued"] = bytes(state["queued"]), bytearray()
            return out
        port = rig.callable_port("loop", write, read, takes_timeout=True)
        with unittest.mock.patch.object(rig, "analyse", side_effect=ValueError("injected")):
            with self.assertRaises(rig.RigError) as cm:
                rig.Run("unanalysed", repetitions=2, tx_during_rx=False).execute(
                    port, out_dir=self.d / "unanalysed", sleep=lambda t: None)
        res = cm.exception.result
        self.assertEqual(res["loss_metric"]["status"], "unknown")
        self.assertIsNone(res["losses"])
        self.assertIsNone(res["losses_upper_bound"])
        self.assertIsNone(res["losses_per_100k_bytes"])
        self.assertEqual(res["confirmed_losses"], 0)
        self.assertEqual(res["repetitions_unanalysed"], [0])


class TheDeviceEntryPoint(unittest.TestCase):
    """`run --device`: the entry point stage 1's physical half will be driven through, proved
    here against a fake serial module that loops back in memory — never a real port. What it
    must do: identify the device, refuse silence before spending the exposure, pass the real fd
    so the counters are attempted, export everything, and exit with the tool's state."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="rigdev_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.d, ignore_errors=True))
        self.opened, self.closed, self.opened_objects = [], [], []

    def fake_serial(self, loopback=True, fail_open=False, fail_after=None, fail_open_after=None,
                    mode="loop"):
        """A `serial.Serial` double: exclusive, with timeouts, looping written bytes back, and
        recording every close. `mode` faults the PREFLIGHT specifically: "continuous" answers every
        read with unrelated bytes forever (a line that never goes quiet); "detach_after_nonce"
        returns the whole nonce on the first read and raises on the next; "write_fail" raises on
        the first write. Reads advance a virtual clock (`self.now`) by the timeout they were given,
        so the preflight's deadline can be proved without waiting for it."""
        opened, closed = self.opened, self.closed

        class FakeSerial:
            def __init__(self, device, baud, **kw):
                if fail_open or (fail_open_after is not None and len(opened) >= fail_open_after):
                    raise OSError(f"could not open port {device}: No such file or directory")
                opened.append({"device": device, "baud": baud, **kw})
                self.device, self.buf, self.writes, self.reads = device, bytearray(), 0, 0
                self.timeout, self.write_timeout = kw.get("timeout"), kw.get("write_timeout")
                self.now, self.closed_count = 0.0, 0

            def write(self, data):
                self.writes += 1
                if mode == "write_fail":
                    raise OSError("write: device gone")
                if fail_after is not None and self.writes > fail_after:
                    raise OSError("device detached")
                if loopback:
                    self.buf += data
                return len(data)

            def read(self, n):
                self.reads += 1
                self.now += self.timeout or 0.0
                if mode == "continuous":
                    return b"background noise from something else on the line\n"
                if mode == "detach_after_nonce" and self.reads > 1:
                    raise OSError("read: device detached after the nonce")
                out, self.buf = bytes(self.buf[:n]), self.buf[n:]
                return out

            def fileno(self):
                return 999999                              # not a real fd: the counters must say so

            def close(self):
                self.closed_count += 1
                closed.append(self.device)
        return types.SimpleNamespace(Serial=FakeSerial)

    def run_cli(self, *extra, serial=None, out=None, virtual_clock=False, fault_export=()):
        """Drive `main(["run", …])` end to end. `virtual_clock` hands the preflight the fake
        port's own clock (advanced by each read's timeout) so its deadline is proved without real
        waiting; `fault_export` names evidence files whose write must raise."""
        import contextlib
        import io
        argv = ["run", "--device", "/dev/NOT-A-DEVICE", "--label", "t", "--out", str(out or self.d),
                "--repetitions", "1", *extra]
        buf = io.StringIO()
        original_preflight, original_write = rig.loopback_preflight, rig._write_evidence

        def preflight(port, **kw):
            s = self.opened_objects[-1] if self.opened_objects else None
            return original_preflight(port, clock=(lambda: s.now) if (virtual_clock and s) else time.monotonic, **kw)

        def write_evidence(path, data):
            if path.name in fault_export:
                raise OSError(f"disk says no: {path.name}")
            return original_write(path, data)

        module = serial or self.fake_serial()
        real_serial = module.Serial
        objects = self.opened_objects = []

        def remember(*args, **kw):
            o = real_serial(*args, **kw)
            objects.append(o)
            return o
        module.Serial = remember
        with unittest.mock.patch.dict(sys.modules, {"serial": module}):
            with unittest.mock.patch.object(rig.time, "sleep", lambda s: None), \
                    unittest.mock.patch.object(rig, "loopback_preflight", preflight), \
                    unittest.mock.patch.object(rig, "_write_evidence", write_evidence):
                with contextlib.redirect_stdout(buf):
                    code = rig.main(argv)
        return code, json.loads(buf.getvalue().strip().splitlines()[-1])

    def test_a_looped_back_device_runs_one_condition_and_exports_everything(self):
        code, brief = self.run_cli("--no-tx-during-rx")
        self.assertEqual(code, 0, brief)
        self.assertEqual(brief["terminal"], "exposure_repetitions")
        self.assertEqual((brief["confirmed_losses"], brief["losses"], brief["loss_metric"]), (0, 0, "exact"))
        self.assertTrue(brief["completed_exposure"] and brief["export_complete"])
        for name in ("invocation.json", "preflight.json", "run.json", "capture_000.bin", "events_000.json"):
            self.assertTrue((self.d / name).is_file(), name)
        on_disk = json.loads((self.d / "run.json").read_text())
        self.assertEqual(on_disk["frames_accepted"], 302)
        self.assertEqual(on_disk["repetition_results"][0]["frames_delivered"], 302)
        self.assertIn("one device", on_disk["topology"])                       # self-loopback, named
        self.assertFalse(on_disk["counters_before"]["available"])              # attempted on the fd …
        self.assertIn("reason", on_disk["counters_before"])                    # … and unavailable, with why
        inv = json.loads((self.d / "invocation.json").read_text())
        self.assertEqual(inv["identity"]["source"]["path"], "/dev/NOT-A-DEVICE")
        self.assertIn("error", inv["identity"]["source"])                      # no such node: said, not guessed
        self.assertEqual(inv["provenance"]["tool_sha256"], rig.self_sha256())
        self.assertEqual(self.opened[0]["baud"], 115200)
        self.assertTrue(self.opened[0]["exclusive"])
        self.assertEqual(self.closed, ["/dev/NOT-A-DEVICE"])                    # released on the way out
        self.assertEqual(brief["ports_closed"], ["/dev/NOT-A-DEVICE"])
        pre = json.loads((self.d / "preflight.json").read_text())
        self.assertEqual(pre["received_file"], "preflight_rx.bin")
        self.assertEqual(pre["received_sha256"], rig.hashlib.sha256((self.d / "preflight_rx.bin").read_bytes()).hexdigest())
        self.assertEqual((self.d / "preflight_rx.bin").read_bytes().decode(), pre["nonce"])   # the nonce, as sent

    def test_the_preflight_nonce_is_drained_and_never_reaches_the_capture(self):
        code, _ = self.run_cli("--no-tx-during-rx")
        self.assertEqual(code, 0)
        pre = json.loads((self.d / "preflight.json").read_text())
        self.assertTrue(pre["matched"])
        self.assertEqual(pre["received_bytes"], pre["nonce_bytes"])
        self.assertNotIn(b"PREFLIGHT", (self.d / "capture_000.bin").read_bytes())

    def test_silence_at_the_preflight_refuses_before_any_exposure(self):
        code, brief = self.run_cli("--no-tx-during-rx", serial=self.fake_serial(loopback=False))
        self.assertEqual(code, 3, brief)
        self.assertEqual(brief["refusal"], "silence")
        self.assertIn("no loopback", brief["refused"])
        self.assertTrue((self.d / "preflight.json").is_file())
        self.assertEqual((self.d / "preflight_rx.bin").read_bytes(), b"")         # nothing came: recorded as nothing
        self.assertFalse((self.d / "run.json").exists())                        # nothing was spent
        self.assertEqual(self.opened_objects[0].writes, 1)
        self.assertEqual(self.closed, ["/dev/NOT-A-DEVICE"])

    def test_no_preflight_skips_the_check_and_silence_is_then_a_measured_total_loss(self):
        """Without the preflight, a repetition that drains to silence is what the analyser has
        always said it is: 302 confirmed losses with no denominator — not a refusal."""
        code, brief = self.run_cli("--no-tx-during-rx", "--no-preflight",
                                   serial=self.fake_serial(loopback=False))
        self.assertEqual(code, 0, brief)
        self.assertFalse((self.d / "preflight.json").exists())
        self.assertEqual((brief["confirmed_losses"], brief["loss_metric"]), (302, "no_denominator"))
        self.assertIsNone(brief["losses_per_100k_bytes"])
        self.assertEqual(brief["terminal"], "stop_rule_losses")               # 302 >= 3: it stops

    def test_a_device_that_will_not_open_is_exit_4_with_the_error_on_disk(self):
        code, brief = self.run_cli("--no-tx-during-rx", serial=self.fake_serial(fail_open=True))
        self.assertEqual(code, 4)
        self.assertIn("could not open port", brief["error"])
        self.assertTrue((self.d / "open_error.json").is_file())
        self.assertTrue((self.d / "invocation.json").is_file())               # the attempt is recorded
        self.assertEqual(self.closed, [])                                       # nothing opened, nothing to close

    def test_a_second_device_that_will_not_open_closes_the_first(self):
        code, brief = self.run_cli("--no-tx-during-rx", "--capture-device", "/dev/OTHER",
                                   serial=self.fake_serial(fail_open_after=1))
        self.assertEqual(code, 4, brief)
        self.assertEqual([o["device"] for o in self.opened], ["/dev/NOT-A-DEVICE"])
        self.assertEqual(self.closed, ["/dev/NOT-A-DEVICE"])                    # the one that did open is released
        self.assertEqual(json.loads((self.d / "open_error.json").read_text())["opened"], ["/dev/NOT-A-DEVICE"])

    def test_a_tool_error_mid_run_is_exit_2_and_the_evidence_still_lands(self):
        code, brief = self.run_cli("--no-tx-during-rx", serial=self.fake_serial(fail_after=5))
        self.assertEqual(code, 2, brief)
        self.assertEqual(brief["terminal"], "tool_error")
        self.assertIn("device detached", brief["error"])
        on_disk = json.loads((self.d / "run.json").read_text())
        self.assertEqual(on_disk["frames_accepted"], 4)                        # the preflight took write 1
        self.assertEqual(on_disk["frames_uncertain"], 1)
        self.assertTrue((self.d / "capture_000.bin").is_file())
        self.assertEqual(self.closed, ["/dev/NOT-A-DEVICE"])                    # closed after the dead run too

    def test_the_tx_condition_runs_too_and_its_echoes_are_accounted(self):
        code, brief = self.run_cli("--tx-during-rx")
        self.assertEqual(code, 0, brief)
        on_disk = json.loads((self.d / "run.json").read_text())
        self.assertEqual(on_disk["host_frames_written"], 125)
        self.assertEqual(on_disk["repetition_results"][0]["host_echo_lines"], 125)
        self.assertEqual((brief["confirmed_losses"], brief["loss_metric"]), (0, "exact"))

    def test_a_two_device_topology_opens_both_and_names_them(self):
        code, brief = self.run_cli("--no-tx-during-rx", "--capture-device", "/dev/OTHER", "--seconds", "0.5")
        self.assertEqual([o["device"] for o in self.opened], ["/dev/NOT-A-DEVICE", "/dev/OTHER"])
        self.assertIn("capture=/dev/OTHER", brief["topology"])
        pre = json.loads((self.d / "preflight.json").read_text())
        self.assertTrue(pre["skipped"])                                        # nothing loops back to preflight
        self.assertEqual(code, 0, brief)                                       # the fakes are separate: silence,
        self.assertEqual(brief["confirmed_losses"], 302)                       # measured on the capture device
        self.assertEqual(sorted(self.closed), ["/dev/NOT-A-DEVICE", "/dev/OTHER"])   # both released

    def test_the_offline_subcommands_still_answer(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(rig.main(["plan"]), 0)
        plan = json.loads(buf.getvalue())
        self.assertEqual(plan["frames"], 302)

    def test_the_exposure_defaults_are_the_registered_ones(self):
        import argparse
        seen = {}
        with unittest.mock.patch.object(rig, "run_device", lambda a: seen.update(vars(a)) or 0):
            rig.main(["run", "--device", "x", "--label", "l", "--out", str(self.d), "--tx-during-rx"])
        self.assertEqual((seen["repetitions"], seen["seconds"]), (rig.EXPOSURE_REPETITIONS, rig.EXPOSURE_SECONDS))
        self.assertEqual((seen["baud"], seen["read_timeout"], seen["pace"]), (115200, 0.05, False))
        self.assertIsNone(seen["expect_usb"])                                  # metadata only, unless declared

    # ---- the owner's entry-point review of 2026-09-13: P2-1, the preflight has an absolute deadline

    def test_a_line_that_never_goes_quiet_is_refused_at_the_preflight_deadline_with_its_bytes_kept(self):
        """P2-1 (as received): every nonempty read reset `quiet_since`, so a line that kept
        producing bytes kept the drain alive indefinitely — before `Run` had started its clock —
        and the buffer grew with every read. Now the whole preflight is bounded by one absolute
        deadline; expiry during the drain is a NAMED refusal, the bytes are kept, and nothing is
        spent on the exposure."""
        code, brief = self.run_cli("--no-tx-during-rx", serial=self.fake_serial(mode="continuous"),
                                   virtual_clock=True)
        self.assertEqual(code, 3, brief)
        self.assertEqual((brief["stage"], brief["refusal"]), ("preflight", "not_quiet"))
        self.assertIn("still arriving", brief["refused"])
        port = self.opened_objects[0]
        self.assertLessEqual(port.now, rig.PREFLIGHT_DEADLINE_S + 1e-9)          # bounded: the fake clock stopped there
        self.assertGreater(port.now, rig.PREFLIGHT_TIMEOUT_S)                   # …and it did go past the nonce wait
        pre = json.loads((self.d / "preflight.json").read_text())
        self.assertFalse(pre["quiet"])
        self.assertFalse(pre["matched"])
        self.assertEqual(pre["received_bytes"], len((self.d / "preflight_rx.bin").read_bytes()))
        self.assertGreater(pre["received_bytes"], 0)                            # what arrived is preserved …
        self.assertIn(b"background noise", (self.d / "preflight_rx.bin").read_bytes())
        self.assertEqual(pre["elapsed_s"], port.now)
        self.assertFalse((self.d / "run.json").exists())                        # … and no exposure began
        self.assertEqual(self.closed, ["/dev/NOT-A-DEVICE"])

    def test_the_preflight_deadline_caps_every_read_and_a_late_nonce_still_passes(self):
        """The reads are capped by the remaining budget, and a nonce that arrives late but within
        its own wait, followed by quiet, is a pass — the clean control of the deadline."""
        seen = []

        class Late:
            def __init__(self):
                self.now, self.pending = 0.0, b""

            def write(self, data, timeout=None):
                self.pending = data
                return len(data)

            def read(self, t):
                seen.append(t)
                self.now += t
                if self.now >= 0.8 and self.pending:                          # the nonce shows up late
                    out, self.pending = self.pending, b""
                    return out
                return b""
        port = Late()
        res = rig.loopback_preflight(rig.callable_port("late", port.write, port.read, takes_timeout=True),
                                     clock=lambda: port.now)
        self.assertTrue(res["matched"] and res["quiet"])
        self.assertIsNone(res["refusal"])
        self.assertIsNone(res["error"])
        self.assertLessEqual(max(seen), rig.PREFLIGHT_READ_S)
        self.assertLessEqual(port.now, rig.PREFLIGHT_DEADLINE_S)
        # and with a deadline shorter than the quiet window, expiry during the drain is the refusal
        port = Late()
        res = rig.loopback_preflight(rig.callable_port("late", port.write, port.read, takes_timeout=True),
                                     clock=lambda: port.now, deadline_s=0.9)
        self.assertEqual(res["refusal"], "not_quiet")
        self.assertTrue(res["matched"])                                        # the nonce did come …
        self.assertFalse(res["quiet"])                                         # … but quiet was not proved
        self.assertLessEqual(port.now, 0.9 + 1e-9)
        self.assertEqual(res["received_raw"], res["nonce"].encode())

    # ---- P2-2, the preflight has its own guarded boundary

    def test_a_detach_after_the_nonce_is_exit_2_with_the_nonce_the_error_and_both_counter_attempts_on_disk(self):
        """P2-2 (as received): the preflight ran outside any guard, so a read that raised after the
        nonce had arrived escaped as a traceback — only `invocation.json` existed, one counter was
        sampled, the received nonce and the diagnosis were lost. Now the transport error is the
        primary error, exit 2, with everything observed up to it on disk."""
        code, brief = self.run_cli("--no-tx-during-rx", serial=self.fake_serial(mode="detach_after_nonce"))
        self.assertEqual(code, 2, brief)
        self.assertEqual(brief["stage"], "preflight")
        self.assertIn("detached after the nonce", brief["error"])
        self.assertEqual(brief["failed_phase"], "drain")                        # read 1 brought the nonce; read 2 died
        pre = json.loads((self.d / "preflight.json").read_text())
        self.assertEqual(pre["error"], brief["error"])
        self.assertTrue(pre["matched"])
        self.assertEqual(pre["received_bytes"], pre["nonce_bytes"])
        self.assertEqual((self.d / "preflight_rx.bin").read_bytes().decode(), pre["nonce"])   # the nonce, kept
        for k in ("counters_before", "counters_after"):                        # both ATTEMPTED, independently
            self.assertFalse(pre[k]["available"])
            self.assertIn("reason", pre[k])
        self.assertIn("elapsed_s", pre)
        self.assertFalse((self.d / "run.json").exists())
        self.assertEqual(self.closed, ["/dev/NOT-A-DEVICE"])

    def test_a_write_fault_at_the_preflight_is_exit_2_in_the_write_phase(self):
        code, brief = self.run_cli("--no-tx-during-rx", serial=self.fake_serial(mode="write_fail"))
        self.assertEqual(code, 2, brief)
        self.assertEqual((brief["stage"], brief["failed_phase"]), ("preflight", "write"))
        pre = json.loads((self.d / "preflight.json").read_text())
        self.assertEqual(pre["received_bytes"], 0)
        self.assertIsNone(pre["refusal"])                                       # an error is not "silence"
        self.assertIn("device gone", pre["error"])
        self.assertFalse((self.d / "run.json").exists())
        self.assertEqual(self.closed, ["/dev/NOT-A-DEVICE"])

    def test_a_preflight_export_failure_never_replaces_the_transport_error_and_the_other_files_still_land(self):
        code, brief = self.run_cli("--no-tx-during-rx", serial=self.fake_serial(mode="detach_after_nonce"),
                                   fault_export=("preflight.json",))
        self.assertEqual(code, 2, brief)                                        # the PRIMARY error decides
        self.assertIn("detached after the nonce", brief["error"])
        self.assertEqual(len(brief["entry_export_errors"]), 1)
        self.assertIn("preflight.json", brief["entry_export_errors"][0])
        self.assertFalse((self.d / "preflight.json").exists())
        self.assertTrue((self.d / "preflight_rx.bin").is_file())                # attempted on its own
        self.assertEqual(self.closed, ["/dev/NOT-A-DEVICE"])

    def test_a_preflight_that_passed_but_could_not_be_recorded_is_exit_5_and_spends_nothing(self):
        code, brief = self.run_cli("--no-tx-during-rx", fault_export=("preflight.json",))
        self.assertEqual(code, 5, brief)
        self.assertEqual(brief["stage"], "preflight_export")
        self.assertFalse((self.d / "run.json").exists())                        # no exposure without its record
        self.assertEqual(self.opened_objects[0].writes, 1)                      # only the nonce was written
        self.assertEqual(self.closed, ["/dev/NOT-A-DEVICE"])

    # ---- P2-3, the destination is claimed fresh before any port opens

    def test_a_nonempty_destination_is_refused_before_any_port_opens_and_left_byte_identical(self):
        """P2-3 (as received): an existing `--out` was accepted and its invocation overwritten
        before the port opened; the exporter then replaced the captures and the summary and left
        the earlier run's extra captures beside them — a mixture of two acquisitions, exit 0,
        `export_complete: true`. Now a nonempty destination is refused with nothing changed."""
        old = {"invocation.json": b'{"old": "invocation"}\n', "run.json": b'{"old": "run"}\n',
               "capture_000.bin": b"old capture", "capture_001.bin": b"old second capture"}
        for name, data in old.items():
            (self.d / name).write_bytes(data)
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.d.iterdir()}
        code, brief = self.run_cli("--no-tx-during-rx")
        self.assertEqual(code, 5, brief)
        self.assertEqual((brief["stage"], brief["refusal"]), ("destination", "destination"))
        self.assertIn("not empty", brief["refused"])
        self.assertEqual(self.opened, [])                                       # the opener was never called
        after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.d.iterdir()}
        self.assertEqual(after, before)                                         # byte-identical, nothing added
        self.assertEqual(sorted(after), sorted(old))

    def test_a_fresh_destination_is_created_and_an_empty_one_is_accepted(self):
        fresh = self.d / "new" / "deeper"
        code, brief = self.run_cli("--no-tx-during-rx", out=fresh)
        self.assertEqual(code, 0, brief)
        self.assertTrue((fresh / "run.json").is_file())
        # a second run into the SAME directory is now a refusal, and the first run's files are intact
        first = {p.name: p.read_bytes() for p in fresh.iterdir()}
        self.opened.clear()
        code, brief = self.run_cli("--no-tx-during-rx", out=fresh)
        self.assertEqual(code, 5, brief)
        self.assertEqual(self.opened, [])
        self.assertEqual({p.name: p.read_bytes() for p in fresh.iterdir()}, first)

    def test_the_claim_is_atomic_a_directory_claimed_between_check_and_claim_is_refused(self):
        """Two runs racing for one empty directory: the check saw it empty, the other run's
        `invocation.json` then appeared, and `O_EXCL` refuses the claim — no overwrite."""
        empty = self.d / "race"
        empty.mkdir()
        (empty / "invocation.json").write_bytes(b"the other run's claim\n")
        with unittest.mock.patch.object(rig.Path, "iterdir", lambda self_: iter(())):    # the stale "empty" view
            fd, why = rig.claim_destination(empty)
        self.assertIsNone(fd)
        self.assertIn("claimed by another run", why)
        self.assertEqual((empty / "invocation.json").read_bytes(), b"the other run's claim\n")
        # and a file where the directory should be is refused too
        as_file = self.d / "a_file"
        as_file.write_bytes(b"x")
        fd, why = rig.claim_destination(as_file)
        self.assertIsNone(fd)
        self.assertIn("not a directory", why)

    # ---- P3, the recorded identity is metadata; `--expect-usb` is the gate

    def test_expect_usb_refuses_before_opening_when_the_identity_is_unavailable_or_different(self):
        code, brief = self.run_cli("--no-tx-during-rx", "--expect-usb", "1a86:7523")
        self.assertEqual(code, 3, brief)                                        # /dev/NOT-A-DEVICE has no identity
        self.assertEqual((brief["stage"], brief["refusal"]), ("identity", "identity"))
        self.assertIn("cannot be confirmed", brief["refused"])
        self.assertEqual(self.opened, [])                                       # refused BEFORE the port opened
        inv = json.loads((self.d / "invocation.json").read_text())              # the attempt is recorded
        self.assertFalse(inv["identity_check"]["matched"])
        self.assertFalse((self.d / "preflight.json").exists())
        other = {"path": "/dev/NOT-A-DEVICE", "realpath": "/dev/ttyUSB9", "char_device": True, "rdev": "188:9",
                 "usb": {"idVendor": "0403", "idProduct": "6001"}}
        with unittest.mock.patch.object(rig, "device_identity", lambda path: dict(other)):
            code, brief = self.run_cli("--no-tx-during-rx", "--expect-usb", "1a86:7523", out=self.d / "ftdi")
        self.assertEqual(code, 3, brief)
        self.assertIn("the node is 0403:6001", brief["refused"])
        self.assertEqual(self.opened, [])

    def test_expect_usb_passes_the_declared_device_and_without_it_identity_is_metadata_only(self):
        ch340 = {"path": "/dev/NOT-A-DEVICE", "realpath": "/dev/ttyUSB0", "char_device": True, "rdev": "188:0",
                 "usb": {"idVendor": "1a86", "idProduct": "7523", "product": "USB Serial"}}
        with unittest.mock.patch.object(rig, "device_identity", lambda path: dict(ch340)):
            code, brief = self.run_cli("--no-tx-during-rx", "--expect-usb", "1A86:7523")   # case-insensitive
        self.assertEqual(code, 0, brief)
        inv = json.loads((self.d / "invocation.json").read_text())
        self.assertTrue(inv["identity_check"]["matched"])
        # without the flag a different device runs — and the record says the identity is not acceptance
        other = {**ch340, "usb": {"idVendor": "0403", "idProduct": "6001"}}
        with unittest.mock.patch.object(rig, "device_identity", lambda path: dict(other)):
            code, brief = self.run_cli("--no-tx-during-rx", out=self.d / "generic")
        self.assertEqual(code, 0, brief)
        inv = json.loads((self.d / "generic" / "invocation.json").read_text())
        self.assertNotIn("identity_check", inv)
        self.assertIn("not acceptance", inv["identity_note"])

    def test_identity_matches_never_passes_an_unavailable_identity(self):
        self.assertEqual(rig.identity_matches({"path": "x", "error": "FileNotFoundError: x"}, "1a86:7523")[0], False)
        self.assertEqual(rig.identity_matches({"usb": {"unavailable": True, "reason": "no idVendor"}}, "1a86:7523")[0],
                         False)
        self.assertEqual(rig.identity_matches({"usb": {}}, "1a86:7523")[0], False)
        self.assertEqual(rig.identity_matches({"usb": {"idVendor": "1a86", "idProduct": "7523"}}, "1a86:7523"),
                         (True, "USB 1a86:7523 as expected"))


if __name__ == "__main__":
    unittest.main()
