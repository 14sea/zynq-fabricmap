#!/usr/bin/env python3
"""Stage 1 of the B1Q transport plan: the tool is proved BEFORE it is believed.

`docs/b1q_transport_plan_2026_09_07.md` §4 stage 1 — "build the generator/capture tool and
prove it against a separate traffic source, not the Zynq". A capture tool that reports a
clean run proves nothing unless it is shown to report a dirty one, so every fault the real
sessions showed — a dropped byte, a flipped bit, a lost frame, a truncated stream — is
injected here and must be both DETECTED and LOCALISED. The end-to-end proof runs over a
pty pair: a separate traffic source, no board, no Zynq.

What a pty cannot prove, and this file says so rather than implying otherwise: a pty has no
UART framing, parity or overrun, so it exercises the tool, never the link. The link
questions belong to stage 2, which needs the hosts and the rig the owner must supply.
"""
from __future__ import annotations

import os
import pty
import select
import sys
import time
import tty
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import transport_rig as rig  # noqa: E402


def flip(buf: bytes, at: int) -> bytes:
    return buf[:at] + bytes([buf[at] ^ 0x01]) + buf[at + 1:]


class TheGeneratedStream(unittest.TestCase):
    def setUp(self):
        self.frames = rig.plan_frames(1)
        self.stream = rig.stream_bytes(self.frames)

    def test_it_is_the_measured_shape(self):
        """One repetition is one session's worth of traffic: 302 frames, every class present,
        every frame within the tolerance of the length the measured range asked for."""
        self.assertEqual(len(self.frames), rig.FRAMES_PER_PROFILE)
        self.assertEqual(len(self.frames), 302)
        for kind, count, lo, hi in rig.SESSION_PROFILE:
            got = [f for f in self.frames if f.kind == kind]
            self.assertEqual(len(got), count, kind)
            for f in got:
                self.assertLessEqual(abs(f.bytes - f.target_bytes), rig.LENGTH_TOLERANCE, f"{kind} {f.index}")
                self.assertGreaterEqual(f.bytes, lo - rig.LENGTH_TOLERANCE, kind)
                self.assertLessEqual(f.bytes, hi + rig.LENGTH_TOLERANCE, kind)
        # both extremes of the real traffic, which is where the real corruptions landed
        self.assertLess(min(f.bytes for f in self.frames), 70)
        self.assertGreater(max(f.bytes for f in self.frames), 2600)

    def test_the_bytes_are_known_in_advance_and_deterministic(self):
        self.assertEqual(rig.stream_bytes(rig.plan_frames(1)), self.stream)
        self.assertEqual(sum(f.bytes for f in self.frames), len(self.stream))
        for f in self.frames:                       # the offset index the localisation uses
            self.assertEqual(self.stream[f.offset:f.offset + f.bytes], f.line)

    def test_the_frames_are_real_rel_v4(self):
        """Built by the instrument's own `l5_notary`, so the parser under test is the real one
        and the bytes are the real shape."""
        import l5_notary as l5
        for f in self.frames[:20]:
            parsed = l5.parse_line(f.line.decode())
            self.assertEqual(parsed["type"], f.kind)
            self.assertEqual(parsed["seq"], f.seq)

    def test_host_sends_exist_and_carry_the_measured_gap(self):
        sends = rig.host_sends(self.frames)
        self.assertTrue(sends)
        self.assertTrue(all(s["gap_s"] >= rig.TX_GAP_MIN_S for s in sends))


class ThePositiveControl(unittest.TestCase):
    def test_an_untouched_stream_is_clean(self):
        frames = rig.plan_frames(1)
        res = rig.analyse(frames, rig.stream_bytes(frames))
        self.assertTrue(res["clean"], res)
        self.assertEqual((res["losses"], res["missing"], res["duplicated"]), (0, [], []))
        self.assertFalse(res["out_of_order"])
        self.assertIsNone(res["divergence"])
        self.assertEqual(res["frames_delivered"], res["frames_sent"])


class ItDetectsAndLocalisesEveryFault(unittest.TestCase):
    """Each of the faults the real sessions showed, injected into a known stream."""

    def setUp(self):
        self.frames = rig.plan_frames(1)
        self.stream = rig.stream_bytes(self.frames)
        self.rec = next(f for f in self.frames if f.kind == "REC")
        self.hb = next(f for f in self.frames if f.kind == "HB")

    def test_one_byte_dropped_inside_the_longest_frame(self):
        at = self.rec.offset + 100
        res = rig.analyse(self.frames, self.stream[:at] + self.stream[at + 1:])
        self.assertFalse(res["clean"])
        self.assertIn(self.rec.index, res["missing"])
        self.assertEqual(len(res["crc_failed"]), 1)
        d = res["divergence"]
        self.assertEqual((d["frame_index"], d["frame_kind"]), (self.rec.index, "REC"))
        self.assertEqual(d["offset_in_frame"], 100)
        self.assertEqual(d["first_offset"], at)
        self.assertEqual(d["received_bytes"], d["expected_bytes"] - 1)

    def test_one_bit_flipped_in_the_shortest_frame(self):
        at = self.hb.offset + 20
        res = rig.analyse(self.frames, flip(self.stream, at))
        self.assertIn(self.hb.index, res["missing"])
        self.assertEqual([c["offset"] for c in res["crc_failed"]], [self.hb.offset])
        self.assertEqual(res["divergence"]["offset_in_frame"], 20)

    def test_a_whole_frame_removed(self):
        """Byte-level localisation lands on the first DIFFERING byte, which for a clean excision
        is a few bytes into the frame — two frames of the same type share their head. The
        finding is that the divergence lies inside the removed frame's span and names it."""
        f = self.frames[40]
        res = rig.analyse(self.frames, self.stream[:f.offset] + self.stream[f.offset + f.bytes:])
        self.assertEqual(res["missing"], [f.index])
        d = res["divergence"]
        self.assertEqual(d["frame_index"], f.index)
        self.assertGreaterEqual(d["first_offset"], f.offset)
        self.assertLess(d["first_offset"], f.offset + f.bytes)
        self.assertEqual(d["expected_bytes"] - d["received_bytes"], f.bytes)
        self.assertEqual(res["crc_failed"], [])          # no damaged line: a clean excision

    def test_a_run_of_bytes_dropped_is_reported_with_its_length(self):
        at = self.rec.offset + 50
        res = rig.analyse(self.frames, self.stream[:at] + self.stream[at + 200:])
        d = res["divergence"]
        self.assertEqual(d["first_offset"], at)
        self.assertEqual(d["expected_bytes"] - d["received_bytes"], 200)
        self.assertIsNotNone(d["bytes_to_resync"])
        self.assertGreater(len(res["missing"]), 0)

    def test_a_duplicated_frame(self):
        f = self.frames[10]
        res = rig.analyse(self.frames, self.stream[:f.offset + f.bytes] + f.line + self.stream[f.offset + f.bytes:])
        self.assertEqual(res["duplicated"], [f.index])
        self.assertFalse(res["clean"])

    def test_two_frames_swapped(self):
        a, b = self.frames[5], self.frames[6]
        swapped = (self.stream[:a.offset] + b.line + a.line + self.stream[b.offset + b.bytes:])
        res = rig.analyse(self.frames, swapped)
        self.assertTrue(res["out_of_order"])
        self.assertEqual(res["missing"], [])             # both arrived; the ORDER is the fault

    def test_a_truncated_stream(self):
        res = rig.analyse(self.frames, self.stream[:-500])
        self.assertFalse(res["clean"])
        self.assertTrue(res["missing"])
        self.assertLess(res["divergence"]["received_bytes"], res["divergence"]["expected_bytes"])

    def test_silence(self):
        res = rig.analyse(self.frames, b"")
        self.assertEqual(res["frames_delivered"], 0)
        self.assertEqual(len(res["missing"]), len(self.frames))
        self.assertEqual(res["divergence"]["first_offset"], 0)

    def test_line_noise_that_is_not_a_frame(self):
        res = rig.analyse(self.frames, self.stream + b"U-Boot 2018.01 (Jan 01 2018)\n")
        self.assertEqual(len(res["malformed"]), 1)
        self.assertFalse(res["clean"])

    def test_a_valid_frame_that_is_not_the_rigs(self):
        """A line whose CRC is perfectly good but whose payload the rig never sent. Without the
        known-transmitted-bytes property this would count as a delivered frame."""
        import l5_notary as l5
        foreign = l5.build_line("HB", 9999, rig.TOKEN, l5.encode_payload({"not": "ours"})).encode()
        res = rig.analyse(self.frames, self.stream + foreign)
        self.assertEqual(len(res["malformed"]), 1)
        self.assertIn("not the rig's", res["malformed"][0]["note"])
        self.assertEqual(res["frames_delivered"], res["frames_sent"])   # and it was not counted as one
        self.assertFalse(res["clean"])

    def test_a_frame_whose_payload_decodes_to_an_index_never_sent(self):
        """The same hole, reached the other way: a payload that decodes cleanly but carries an
        index outside the transmitted set. It must not be credited as a delivered frame."""
        far = rig.build_frame(10 ** 6, "HB", 1, 66)
        res = rig.analyse(self.frames, self.stream + far.line)
        self.assertEqual(len(res["malformed"]), 1)
        self.assertIn("never transmitted", res["malformed"][0]["note"])
        self.assertEqual(res["malformed"][0]["index"], 10 ** 6)


class TheCountersNoSessionHad(unittest.TestCase):
    def test_a_pty_has_no_uart_counters_and_says_so(self):
        """The point of the field: unavailable is recorded as unavailable WITH its reason and
        never as zero, which would read as 'no framing errors'."""
        master, slave = os.openpty()
        try:
            got = rig.read_icounters(slave)
        finally:
            os.close(master)
            os.close(slave)
        self.assertFalse(got["available"])
        self.assertTrue(got["reason"])
        self.assertNotIn("frame", got)
        self.assertNotIn("overrun", got)

    def test_a_delta_of_unavailable_counters_is_unavailable(self):
        d = rig.counter_delta({"available": False, "reason": "x"}, {"available": True, **{k: 0 for k in rig.ICOUNTER_FIELDS}})
        self.assertFalse(d["available"])
        self.assertNotIn("frame", d)

    def test_a_delta_of_available_counters_is_the_difference(self):
        before = {"available": True, **{k: 0 for k in rig.ICOUNTER_FIELDS}}
        after = {"available": True, **{k: 0 for k in rig.ICOUNTER_FIELDS}, "frame": 7, "overrun": 2}
        d = rig.counter_delta(before, after)
        self.assertEqual((d["frame"], d["overrun"], d["parity"]), (7, 2, 0))


class TheExposureAndStopRules(unittest.TestCase):
    """Plan §5, fixed in advance: bounded exposure, an early stop when the condition is
    reproducing the failure, and a stop on any tool error."""

    def clean_transport(self):
        box = {}

        def write(data):
            box["last"] = box.get("last", b"") + data

        def read():
            out = box.pop("last", b"")
            return b"".join(ln + b"\n" for ln in out.split(b"\n") if ln.startswith(b"P3L5 "))
        return write, read

    def test_a_clean_run_completes_its_exposure(self):
        write, read = self.clean_transport()
        run = rig.Run("control", repetitions=2, tx_during_rx=False)
        res = run.execute(write, read, sleep=lambda s: None)
        self.assertEqual(res["repetitions_run"], 2)
        self.assertEqual(res["losses"], 0)
        self.assertIn("2 repetitions completed", res["stopped"])
        self.assertEqual(res["losses_per_100k_bytes"], 0.0)
        self.assertEqual(res["denominator_bytes"], res["bytes_sent"])
        self.assertFalse(res["counters_before"]["available"])      # no fd supplied, and it says so

    def test_three_losses_in_one_repetition_stop_the_run(self):
        write, read = self.clean_transport()

        def lossy_read():
            data = read()
            for at in (500, 5000, 20000):                # three damaged lines
                data = flip(data, at)
            return data
        run = rig.Run("lossy", repetitions=10, tx_during_rx=False)
        res = run.execute(write, lossy_read, sleep=lambda s: None)
        self.assertEqual(res["repetitions_run"], 1)
        self.assertIn("stop rule", res["stopped"])
        self.assertIn("reproducing the failure", res["stopped"])
        self.assertGreaterEqual(res["losses"], rig.LOSSES_PER_REPETITION_STOP)
        self.assertGreater(res["losses_per_100k_bytes"], 0)

    def test_a_tool_error_stops_the_run(self):
        def boom(_data=None):
            raise OSError("device detached")
        run = rig.Run("broken", repetitions=5)
        with self.assertRaises(rig.RigError) as cm:
            run.execute(boom, boom, sleep=lambda s: None)
        self.assertIn("tool error", str(cm.exception))

    def test_the_time_bound_ends_a_run(self):
        write, read = self.clean_transport()
        ticks = iter([0.0, 0.0, 999.0, 999.0, 999.0])
        run = rig.Run("timed", repetitions=100, seconds=10.0, tx_during_rx=False)
        res = run.execute(write, read, sleep=lambda s: None, clock=lambda: next(ticks))
        self.assertIn("exposure", res["stopped"])
        self.assertIn("s reached", res["stopped"])
        self.assertLess(res["repetitions_run"], 100)


class OverAPtyPair(unittest.TestCase):
    """The end-to-end proof against a separate traffic source — no Zynq, no board, no ruling.

    A pty is not a UART: it has no framing, parity or overrun, and it does not lose bytes. It
    proves the generator, the capture and the analysis end to end; it proves nothing about
    any link, which is stage 2's question.
    """

    def pump(self, data: bytes) -> bytes:
        """Push the whole stream through a pty pair and collect what comes out. RAW mode on
        both ends — a cooked pty would translate the frames' newlines and echo them back, and
        the tool would be measuring the terminal discipline instead of the transport."""
        master, slave = pty.openpty()
        tty.setraw(master)
        tty.setraw(slave)
        got = bytearray()
        deadline = time.monotonic() + 20.0
        try:
            os.set_blocking(master, False)
            os.set_blocking(slave, False)
            at = 0
            while at < len(data) or time.monotonic() < deadline:
                if at < len(data):
                    _, writable, _ = select.select([], [master], [], 0.2)
                    if writable:
                        at += os.write(master, data[at:at + 4096])
                readable, _, _ = select.select([slave], [], [], 0.05)
                if readable:
                    try:
                        chunk = os.read(slave, 65536)
                    except (BlockingIOError, OSError):
                        chunk = b""
                    if chunk:
                        got += chunk
                        continue
                if at >= len(data) and not readable:
                    break
                self.assertLess(time.monotonic(), deadline, "the pty pump did not drain")
        finally:
            os.close(master)
            os.close(slave)
        return bytes(got)

    def test_a_clean_pty_round_trip(self):
        frames = rig.plan_frames(1)
        received = self.pump(rig.stream_bytes(frames))
        res = rig.analyse(frames, received)
        self.assertTrue(res["clean"], {k: res[k] for k in ("missing", "crc_failed", "malformed", "divergence")})
        self.assertEqual(res["bytes_received"], res["bytes_sent"])

    def test_a_drop_injected_after_the_pty_is_still_localised(self):
        """The same round trip, with one byte removed from what came back: the tool must not
        become blind just because the bytes travelled through a device."""
        frames = rig.plan_frames(1)
        rec = next(f for f in frames if f.kind == "REC")
        received = self.pump(rig.stream_bytes(frames))
        res = rig.analyse(frames, received[:rec.offset + 7] + received[rec.offset + 8:])
        self.assertIn(rec.index, res["missing"])
        self.assertEqual(res["divergence"]["frame_index"], rec.index)
        self.assertEqual(res["divergence"]["offset_in_frame"], 7)


class TheProfileIsDerivedFromTheSessions(unittest.TestCase):
    """The plan's §2 table is checked against the committed bytes, not copied from the doc."""

    LOG = R / rig.PROFILE_SOURCE

    def test_the_frozen_profile_is_what_the_clean_session_transmitted(self):
        got = rig.profile_from_log(self.LOG)["frames"]
        self.assertNotIn("UNKNOWN", got)
        self.assertEqual(sorted(got), sorted(k for k, _, _, _ in rig.SESSION_PROFILE))
        for kind, count, lo, hi in rig.SESSION_PROFILE:
            self.assertEqual(got[kind]["count"], count, kind)
            self.assertEqual((got[kind]["min"], got[kind]["max"]), (lo, hi), kind)
        self.assertEqual(sum(e["count"] for e in got.values()), rig.FRAMES_PER_PROFILE)

    def test_the_two_forced_controls_are_the_only_damaged_frames_there(self):
        """The clean session's two CRC failures are the session's own forced controls, which is
        why the rig transmits none: every CRC failure a rig run sees is a transport event."""
        d = rig.profile_from_log(self.LOG)
        self.assertEqual([c["type"] for c in d["crc_failed"]], ["SIGNREQ", "REC"])
        self.assertEqual(d["frames"]["SIGNREQ"]["crc_failed"], 1)
        self.assertEqual(d["frames"]["REC"]["crc_failed"], 1)

    def test_the_lost_sessions_show_more_than_their_controls(self):
        """Session 3 — the one the stop-loss is about — carries damage beyond the two controls,
        and the tool reports each with its byte offset."""
        d = rig.profile_from_log(R / "evidence/b1q/b1q_17A6_2026-09-06-03/console.log")
        self.assertGreater(len(d["crc_failed"]), 2)
        self.assertTrue(all(isinstance(c["offset"], int) for c in d["crc_failed"]))

    @staticmethod
    def split_controls(damaged: list) -> tuple[list, list, list]:
        """The session's two FORCED controls are, by its design, the first damaged SIGNREQ seq 1
        and the first damaged REC seq 1 (`docs/b1q_transport_plan_2026_09_07.md`, attempt 4:
        "the only two CRC drops are the two forced controls (SIGNREQ seq 1, REC)"). They are
        identified by that rule — not by a byte offset, which would be a number that happens to
        be true today."""
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
        """Why the rig transmits no controls: in all three complete sessions the damaged frames
        are exactly those two, at the same offsets — what a deterministic session feature looks
        like, and what a transport event does not."""
        for name in ("b1q_17A6_2026-09-06-01", "b1q_17A6_2026-09-06-02", "b1q_17A6_2026-09-08-01"):
            d = rig.profile_from_log(R / "evidence/b1q" / name / "console.log")
            controls, events, fragments = self.split_controls(d["crc_failed"])
            self.assertEqual([(c["type"], c["seq"], c["offset"]) for c in controls],
                             [("SIGNREQ", 1, 1105), ("REC", 1, 6463)], name)
            self.assertEqual(fragments, [], name)
            self.assertEqual(len(events), 1 if name.endswith("06-01") else 0, (name, events))

    def test_it_reproduces_the_owners_corrected_non_control_count(self):
        """The transport review of 2026-09-07 corrected the diagnosis to **four** non-control CRC
        events across the three reviewed sessions, plus one fragment; the original claim of five
        was withdrawn. Deriving it from the committed bytes must give that, or one of the two is
        wrong. Sessions 1, 2 and 3 — attempt 4 came later and is not in that count."""
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
