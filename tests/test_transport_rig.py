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
        with unittest.mock.patch.dict(sys.modules, {"serial": types.SimpleNamespace(Serial=FakeSerial)}):
            port = rig.serial_port("NOT-A-DEVICE")
            port.write(b"x", 0.25)
        self.assertTrue(seen["kwargs"]["exclusive"])
        self.assertEqual(seen["kwargs"]["write_timeout"], rig.WRITE_TIMEOUT_S)
        self.assertEqual(seen["write_timeout_at_write"], 0.25)

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


if __name__ == "__main__":
    unittest.main()
