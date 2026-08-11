"""The U-Boot AXI transport, against a fake board.

There is no board in a test run, so what is exercised here is everything between the sealed
bytes and the wire: the command shapes, the `md` parsing, the frame-to-FAR mapping, the
readback capture, and — most of it — the refusals. The fake engine is a *cooperative*
device on the happy path and a hostile one everywhere else; nothing here claims to model
`carrier_stream`'s timing, which is the one thing only silicon can settle.

The pacing arithmetic is checked as arithmetic (`test_the_pacing_budget_is_stated`), because
the shape of every command in this module follows from it: a per-frame console round trip
does not fit inside the engine's watchdog, so the readback must be one line.
"""

from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_carrier_guard as guard  # noqa: E402
import board_uboot_axi as axi  # noqa: E402
import icap_sequence as iseq  # noqa: E402

import board_set_fclk50 as fclk  # noqa: E402
import gate_board_identity as ident  # noqa: E402

IDCODE = 0x13722093
PREAMBLE = 23


def slcr_regs() -> dict:
    """What a 4203 at 50 MHz answers, computed from the PLL encoding rather than guessed."""
    io_pll = next(ctrl for ctrl in range(0, 0x100000, 0x1000)
                  if abs(fclk.pll_mhz(ctrl, ident.PS_CLK_MHZ) - 1600.0) < 0.5)
    return {
        ident.SLCR_PSS_IDCODE: IDCODE,
        fclk.IO_PLL_CTRL: io_pll,
        fclk.ARM_PLL_CTRL: io_pll,
        fclk.DDR_PLL_CTRL: io_pll,
        fclk.FPGA0_CLK_CTRL: 0x00400800,        # /8 /4 -> 50 MHz
    }


def a_payload(seed: int = 1) -> bytes:
    """Three structurally real envelopes, with arbitrary frame content."""
    envelopes = []
    for env in range(axi.ENVELOPES):
        frames = []
        for frame in range(axi.FRAMES_PER_ENVELOPE):
            base = seed * 1_000_000 + env * 1000 + frame * 100
            frames.append([(base + word) & 0xFFFFFFFF for word in range(axi.FRAME_WORDS)])
        envelopes.append(
            iseq.build_envelope(guard.ENVELOPE_FAR[env], frames, IDCODE))
    return b"".join(struct.pack(f">{len(e)}I", *e) for e in envelopes)


class FakeBoard:
    """A U-Boot console over a small model of the engine.

    Faithful about *sequence* — which control writes are legal when, what the readback
    hands back — and deliberately silent about time, which is where the real device is the
    only authority.
    """

    CMD_RE = re.compile(r"^(mw|cp|md)(?:\.l)? (\S+) (\S+)(?: (\S+))?$")

    def __init__(self, *, corrupt_stage=None, fault_at=None, armed_at_end=False,
                 status_override=None, swallow_prompt=False, stuck_busy=None,
                 abort_on=None):
        self.mem: dict[int, int] = {}
        self.lines: list[str] = []
        self.corrupt_stage = corrupt_stage        # word index to mangle while staging
        self.fault_at = fault_at                  # "pass1", "pass2" or None
        self.stuck_busy = stuck_busy              # a pass that never finishes
        self.armed_at_end = armed_at_end
        self.status_override = status_override
        self.swallow_prompt = swallow_prompt
        self.abort_on = abort_on          # substring of a command that faults the CPU
        self.staged_writes = 0
        self.uboot_env = {"boardid": "17A6", "role": "verify"}
        self.regs = slcr_regs()
        self.regs[guard.PCAP_PR_ADDR] = 0x4E00E07F      # PCAP_PR set, as the board reads
        self.pcap_writes: list[int] = []

        self.busy = False
        self.fault = False
        self.fault_code = 0
        self.config_valid = False
        self.recovery = True                      # fail-closed out of reset
        self.pass1_complete = False
        self.expect_env = 0
        self.env_committed = 0
        self.rb_frames_ok = 0
        self.mode = None
        self.env = 0
        self.pending: list[list[int]] = []

    # -- the console ------------------------------------------------------------

    def descriptor(self) -> dict:
        return {"requested_port": "/dev/ebaz-uart", "resolved_port": "/dev/ttyUSB9",
                "device_id": "188:9"}

    def command(self, line: str, timeout: float = 1.5) -> bytes:
        self.lines.append(line)
        if self.abort_on and self.abort_on in line:
            # What U-Boot really prints when an AXI error response reaches the CPU: a
            # register dump, and never a prompt again.
            return (line + "\r\ndata abort\r\npc : [<1ffa1ab4>]   lr : [<1ffa1a30>]\r\n"
                    "Resetting CPU ...\r\n### ERROR ### Please RESET the board ###\r\n"
                    ).encode()
        if line.startswith("printenv "):
            name = line.split()[1]
            if name not in self.uboot_env:
                return f'## Error: "{name}" not defined\r\nZynq> '.encode()
            return f"{line}\r\n{name}={self.uboot_env[name]}\r\nZynq> ".encode()
        body = ""
        stripped = line.replace(axi.WAIT, "WAIT")
        for part in stripped.split("; "):
            part = part.strip()
            if not part or part == "WAIT" or part.startswith("setenv"):
                continue
            body += self._one(part)
        prompt = "" if self.swallow_prompt else "Zynq> "
        return (line + "\r\n" + body + prompt).encode()

    def _one(self, part: str) -> str:
        match = self.CMD_RE.match(part)
        if not match:
            return f"Unknown command '{part}'\r\n"
        verb, first, second, third = match.groups()
        first_i = int(first, 16)
        if verb == "mw":
            self._write(first_i, int(second, 16))
            return ""
        if verb == "cp":
            self._copy(first_i, int(second, 16), int(third, 16))
            return ""
        return self._dump(first_i, int(second, 16))

    def _dump(self, addr: int, count: int) -> str:
        out = ""
        for index in range(0, count, 4):
            row = [self._read(addr + (index + k) * 4)
                   for k in range(min(4, count - index))]
            words = " ".join(f"{value:08x}" for value in row)
            out += f"{addr + index * 4:08x}: {words}    {'.' * (len(row) * 4)}\r\n"
        return out

    # -- memory and registers ---------------------------------------------------

    def _read(self, addr: int) -> int:
        if addr in self.regs:
            return self.regs[addr]
        if addr == axi.STATUS:
            return self.status_word()
        if addr == axi.FAULT:
            return self.fault_code
        if axi.RDBACK <= addr < axi.RDBACK + axi.FRAME_WORDS * 4:
            frame = self.pending[0] if self.pending else [0] * axi.FRAME_WORDS
            return frame[(addr - axi.RDBACK) // 4]
        return self.mem.get(addr, 0)

    def _write(self, addr: int, value: int) -> None:
        if addr == guard.PCAP_PR_ADDR:
            self.pcap_writes.append(value)
            self.regs[addr] = value
            return
        if addr == axi.CTRL:
            self._ctrl(value)
            return
        if self.corrupt_stage is not None and self.staged_writes == self.corrupt_stage:
            value ^= 0xFF
        self.staged_writes += 1
        self.mem[addr] = value

    def _copy(self, src: int, dst: int, count: int) -> None:
        if dst == axi.STREAM:
            self._stream([self.mem.get(src + i * 4, 0) for i in range(count)])
            return
        for i in range(count):
            self.mem[dst + i * 4] = self._read(src + i * 4)

    def status_word(self) -> int:
        if self.status_override is not None:
            return self.status_override
        word = 0
        stuck = self.stuck_busy is not None and self.stuck_busy == self.mode
        word |= axi.ST_BUSY if (self.busy or stuck) else 0
        word |= axi.ST_FAULT if self.fault else 0
        word |= axi.ST_CONFIGURATION_VALID if self.config_valid else 0
        word |= axi.ST_PASS1_COMPLETE if self.pass1_complete else 0
        word |= axi.ST_RECOVERY_REQUIRED if self.recovery else 0
        word |= axi.ST_RB_FRAME_READY if self.pending else 0
        word |= axi.ST_SCORER_ARMED if self.armed_at_end and self.config_valid else 0
        word |= (self.expect_env & 0x3) << 8
        word |= (self.env_committed & 0x7) << 11
        word |= (self.rb_frames_ok & 0xF) << 14
        return word

    # -- the engine -------------------------------------------------------------

    def _ctrl(self, value: int) -> None:
        if value & axi.CTRL_BEGIN_TXN:
            self.env_committed = 0
            self.rb_frames_ok = 0
            self.pass1_complete = False
            self.fault = False
            self.fault_code = 0
            self.config_valid = False
            self.expect_env = 0
        if value & (axi.CTRL_PASS1 | axi.CTRL_PASS2):
            self.env = (value >> axi.CTRL_ENV_SHIFT) & 0x3
            self.mode = "pass1" if value & axi.CTRL_PASS1 else "pass2"
        if value & axi.CTRL_RB_ACK and self.pending:
            self.pending.pop(0)
            self.rb_frames_ok += 1
            if not self.pending:
                if self.env == axi.ENVELOPES - 1:
                    self.config_valid = True
                    self.recovery = False
                    self.expect_env = 0
                else:
                    self.expect_env = self.env + 1

    def _stream(self, words: list[int]) -> None:
        if len(words) != axi.ENVELOPE_WORDS:
            self._fault(4)
            return
        if self.fault_at == self.mode:
            self._fault(6)
            return
        payload = words[PREAMBLE:PREAMBLE + axi.FRAMES_PER_ENVELOPE * axi.FRAME_WORDS]
        frames = [payload[i * axi.FRAME_WORDS:(i + 1) * axi.FRAME_WORDS]
                  for i in range(axi.FRAMES_PER_ENVELOPE)]
        if self.mode == "pass1":
            self.env_committed |= 1 << self.env
            self.expect_env = (self.env + 1) % axi.ENVELOPES
            if self.env == axi.ENVELOPES - 1:
                self.pass1_complete = True
        else:
            self.pending = frames

    def _fault(self, code: int) -> None:
        self.fault = True
        self.fault_code = code
        self.pending = []
        self.config_valid = False
        self.env_committed = 0
        self.rb_frames_ok = 0


def run(board, payload=None):
    return axi.execute_transaction(axi.WRITE_CAPABILITY, board, payload or a_payload())


class TheHappyPath(unittest.TestCase):
    def test_a_whole_transaction_returns_the_fifteen_frames(self) -> None:
        payload = a_payload()
        board = FakeBoard()
        record = run(board, payload)

        self.assertEqual(len(record["readback_frames"]), axi.TOTAL_FRAMES)
        expected_fars = set(guard.PERMITTED_TARGET_FARS) | set(guard.PERMITTED_FLUSH_FARS)
        self.assertEqual(set(record["readback_frames"]), expected_fars)

        # what came back is what was streamed, frame for frame, in the right FAR
        words = struct.unpack(f">{len(payload) // 4}I", payload)
        for env in range(axi.ENVELOPES):
            block = words[env * axi.ENVELOPE_WORDS:(env + 1) * axi.ENVELOPE_WORDS]
            for frame in range(axi.FRAMES_PER_ENVELOPE):
                start = PREAMBLE + frame * axi.FRAME_WORDS
                self.assertEqual(
                    record["readback_frames"][axi.far_of(env, frame)],
                    list(block[start:start + axi.FRAME_WORDS]),
                    f"envelope {env} frame {frame}")

        self.assertTrue(record["status_after"]["configuration_valid"])
        self.assertFalse(record["status_after"]["recovery_required"])
        self.assertEqual(record["status_after"]["rb_frames_ok"], axi.TOTAL_FRAMES)
        self.assertEqual(record["payload_sha256"][:8],
                         __import__("hashlib").sha256(payload).hexdigest()[:8])

    def test_pass_one_runs_before_any_pass_two(self) -> None:
        """Pass 1 asserts no CSIB, so all three must clear before the fabric is touched."""
        board = FakeBoard()
        run(board)
        order = [line.split(";")[0] for line in board.lines if line.startswith("mw.l")]
        pass1 = [i for i, line in enumerate(board.lines) if "0x4 1" in line or "0x14 1" in line
                 or "0x24 1" in line]
        pass2 = [i for i, line in enumerate(board.lines) if "0x8 1" in line or "0x18 1" in line
                 or "0x28 1" in line]
        self.assertEqual(len(pass1), 3)
        self.assertEqual(len(pass2), 3)
        self.assertLess(max(pass1), min(pass2), f"passes interleaved: {order}")


class TheCommandShapes(unittest.TestCase):
    def test_the_pacing_budget_is_stated(self) -> None:
        """21 ms, and a per-frame round trip does not fit in it."""
        self.assertAlmostEqual(axi.WATCHDOG_BUDGET_S, 0.02097152, places=8)
        measured_round_trip_s = 0.007            # board 17A6, 2026-08-11
        per_frame = 2 * measured_round_trip_s    # poll, then read-and-ack
        self.assertGreater(axi.FRAMES_PER_ENVELOPE * per_frame, axi.WATCHDOG_BUDGET_S)

    def test_the_readback_of_an_envelope_is_one_line(self) -> None:
        line = axi.pass2_line(0)
        self.assertEqual(line.count(axi.WAIT), axi.FRAMES_PER_ENVELOPE)
        self.assertEqual(line.count(f"0x{axi.CTRL_RB_ACK:x} 1"), axi.FRAMES_PER_ENVELOPE)
        self.assertEqual(line.count("cp.l"), 1 + axi.FRAMES_PER_ENVELOPE)
        self.assertLess(len(line), 2000, "U-Boot CBSIZE is 2048 on this build")

    def test_the_wait_loop_also_exits_on_a_fault(self) -> None:
        """Without the fault bit it spins forever exactly when the engine has given up."""
        self.assertEqual(axi.WAIT_MASK, axi.ST_RB_FRAME_READY | axi.ST_FAULT)
        self.assertIn(f"0x{axi.WAIT_MASK:x}", axi.WAIT)
        self.assertIn("setenv zr 0", axi.WAIT)

    def test_the_capture_areas_do_not_overlap_the_payload(self) -> None:
        payload_end = axi.PAYLOAD_ADDR + guard.TOTAL_BYTES
        first = axi.capture_addr(0, 0)
        last = axi.capture_addr(axi.ENVELOPES - 1, axi.FRAMES_PER_ENVELOPE - 1)
        self.assertGreaterEqual(first, payload_end)
        self.assertEqual(last + axi.FRAME_WORDS * 4 - first,
                         axi.TOTAL_FRAMES * axi.FRAME_WORDS * 4)

    def test_every_frame_has_its_own_capture_address(self) -> None:
        seen = {axi.capture_addr(e, f)
                for e in range(axi.ENVELOPES) for f in range(axi.FRAMES_PER_ENVELOPE)}
        self.assertEqual(len(seen), axi.TOTAL_FRAMES)

    def test_the_far_order_is_the_guards(self) -> None:
        flat = [axi.far_of(e, f) for e in range(axi.ENVELOPES)
                for f in range(axi.FRAMES_PER_ENVELOPE - 1)]
        self.assertEqual(tuple(flat), guard.PERMITTED_TARGET_FARS)
        self.assertEqual(
            tuple(axi.far_of(e, axi.FRAMES_PER_ENVELOPE - 1) for e in range(axi.ENVELOPES)),
            guard.PERMITTED_FLUSH_FARS)


class TheRefusals(unittest.TestCase):
    def refuses(self, board, payload=None, contains=""):
        with self.assertRaises(axi.AxiRefusal) as caught:
            run(board, payload)
        if contains:
            self.assertIn(contains, str(caught.exception))
        return str(caught.exception)

    def test_without_the_capability(self) -> None:
        with self.assertRaises(axi.AxiRefusal) as caught:
            axi.execute_transaction(object(), FakeBoard(), a_payload())
        self.assertIn("second entrypoint", str(caught.exception))

    def test_a_payload_of_the_wrong_length(self) -> None:
        self.refuses(FakeBoard(), a_payload()[:-4], contains="fixed envelope")

    def test_a_status_word_with_reserved_bits_set(self) -> None:
        self.refuses(FakeBoard(status_override=0x00040080), contains="not the carrier")

    def test_a_status_word_of_zero(self) -> None:
        self.refuses(FakeBoard(status_override=0), contains="cannot read zero")

    def test_recovery_already_clear_before_the_transaction(self) -> None:
        """A carrier that has already run a transaction — not the state a run assumes."""
        board = FakeBoard()
        board.recovery = False
        board.config_valid = True
        self.refuses(board, contains="sticky to reset")

    def test_dram_that_does_not_hold_the_sealed_bytes(self) -> None:
        self.refuses(FakeBoard(corrupt_stage=17), contains="not the bytes that were sealed")

    def test_a_fault_during_pass_one(self) -> None:
        message = self.refuses(FakeBoard(fault_at="pass1"), contains="faulted during pass 1")
        self.assertIn("timeout", message)

    def test_a_fault_during_pass_two(self) -> None:
        self.refuses(FakeBoard(fault_at="pass2"), contains="faulted during pass 2")

    def test_a_scorer_that_is_armed_at_the_end(self) -> None:
        self.refuses(FakeBoard(armed_at_end=True), contains="scorer is armed")

    def test_a_console_that_does_not_return_a_prompt(self) -> None:
        message = self.refuses(FakeBoard(swallow_prompt=True),
                               contains="did not answer at all")
        self.assertIn("Received:", message, "the received bytes are the evidence")

    def test_a_cpu_exception_is_not_reported_as_silence(self) -> None:
        """A data abort and a stalled CPU both end with no prompt, and they mean opposite
        things: the abort is the fabric answering with an error, the stall is the fabric
        not answering. Two calibration stops could not be told apart because this was one
        message."""
        message = self.refuses(FakeBoard(abort_on="md.l"), contains="fabric ANSWERED")
        self.assertIn("data abort", message)
        self.assertNotIn("did not answer at all", message)

    def test_a_command_line_longer_than_the_console_buffer(self) -> None:
        with self.assertRaises(axi.AxiRefusal) as caught:
            axi.command(FakeBoard(), "md.l 0x0 1" + " " * 2100, 1.0)
        self.assertIn("CBSIZE", str(caught.exception))


class TheSessionIsTheDoor(unittest.TestCase):
    """`BoardSession.write_sequence` is the only way in, so its interlock is tested here
    against a board that would otherwise answer perfectly."""

    def session(self, board):
        return ident.BoardSession(board)

    def test_a_stuck_pass_one_is_refused(self) -> None:
        with self.assertRaises(axi.AxiRefusal) as caught:
            run(FakeBoard(stuck_busy="pass1"))
        self.assertIn("did not finish", str(caught.exception))

    def test_a_stuck_pass_two_is_refused(self) -> None:
        with self.assertRaises(axi.AxiRefusal) as caught:
            run(FakeBoard(stuck_busy="pass2"))
        self.assertIn("did not finish", str(caught.exception))

    def test_it_refuses_without_a_verified_identity_and_sends_nothing(self) -> None:
        board = FakeBoard()
        session = self.session(board)
        with self.assertRaises(ident.IdentityError):
            session.write_sequence(a_payload())
        self.assertEqual(board.lines, [], "a refused write must not reach the console")
        self.assertIsNone(session.last_transaction)

    def test_it_refuses_after_a_disruption_even_though_the_board_is_the_same(self) -> None:
        board = FakeBoard()
        session = self.session(board)
        session.verify_identity()
        session.note_disruption("power_cycle")
        before = len(board.lines)
        with self.assertRaises(ident.IdentityError):
            session.write_sequence(a_payload())
        self.assertEqual(board.lines[before:], [])

    def test_the_transaction_is_recorded_on_the_session(self) -> None:
        board = FakeBoard()
        session = self.session(board)
        session.verify_identity()
        payload = a_payload()
        record = session.write_sequence(payload)
        self.assertIs(record, session.last_transaction)
        self.assertEqual(record["epoch"], session.epoch)
        self.assertEqual(record["boardid"], "17A6")
        self.assertEqual(record["payload_sha256"],
                         __import__("hashlib").sha256(payload).hexdigest())
        self.assertEqual(len(record["readback_frames"]), axi.TOTAL_FRAMES)


class TheBootMarker(unittest.TestCase):
    """A restart clears the PL, and asking the PL about it is the one question that stalls
    the CPU when the answer is no. `17A6` was seen restarting between two good reads."""

    def board(self, plmark=None):
        board = FakeBoard()
        if plmark is not None:
            board.uboot_env["plmark"] = plmark
        return board

    def test_the_same_boot_passes(self) -> None:
        axi.same_boot(self.board("00000000deadbeef"), "00000000deadbeef")

    def test_a_missing_marker_is_a_restart(self) -> None:
        with self.assertRaises(axi.AxiRefusal) as caught:
            axi.same_boot(self.board(), "00000000deadbeef")
        self.assertIn("restarted", str(caught.exception))
        self.assertIn("would stall the CPU", str(caught.exception))

    def test_a_different_marker_is_a_different_boot(self) -> None:
        with self.assertRaises(axi.AxiRefusal) as caught:
            axi.same_boot(self.board("0000000012345678"), "00000000deadbeef")
        self.assertIn("different boot", str(caught.exception))

    def test_it_asks_before_it_would_have_to_stall(self) -> None:
        """The whole value is that this costs one env read and never touches the window."""
        board = self.board()
        with self.assertRaises(axi.AxiRefusal):
            axi.same_boot(board, "00000000deadbeef")
        self.assertEqual(board.lines, ["printenv plmark"])


class ThePcapHandover(unittest.TestCase):
    """`PCAP_PR` is 1 on this board, so the fabric ICAPE2 is disconnected: without the
    handover every FDRI word would be accepted by the configuration engine and reach
    nothing. The transaction was doing exactly that."""

    def test_the_icap_is_handed_over_and_given_back(self) -> None:
        board = FakeBoard()
        run(board)
        self.assertEqual(len(board.pcap_writes), 2, "one handover, one restore")
        self.assertEqual(board.pcap_writes[0] & guard.PCAP_PR_BIT, 0,
                         "PCAP_PR must be CLEARED for the transaction")
        self.assertEqual(board.pcap_writes[1], 0x4E00E07F,
                         "and the previous value restored exactly")
        self.assertEqual(board.regs[guard.PCAP_PR_ADDR], 0x4E00E07F)

    def test_it_is_given_back_after_a_fault_too(self) -> None:
        """A devcfg left selecting the PL leaves the next PCAP user with a device that
        will not respond, and the recovery for that is a power cycle."""
        board = FakeBoard(fault_at="pass2")
        with self.assertRaises(axi.AxiRefusal):
            run(board)
        self.assertEqual(board.regs[guard.PCAP_PR_ADDR], 0x4E00E07F)
        self.assertEqual(len(board.pcap_writes), 2)

    def test_the_handover_happens_before_begin_txn(self) -> None:
        board = FakeBoard()
        run(board)
        pcap_at = next(i for i, line in enumerate(board.lines)
                       if f"mw 0x{guard.PCAP_PR_ADDR:08x}" in line)
        begin_at = next(i for i, line in enumerate(board.lines)
                        if f"0x{axi.CTRL_BEGIN_TXN:x} 1" in line and "mw.l" in line)
        self.assertLess(pcap_at, begin_at)


class TheMdParser(unittest.TestCase):
    def test_it_reads_a_normal_dump(self) -> None:
        reply = (b"md.l 0x10000000 4\r\n"
                 b"10000000: aabbccdd 00000001 00000002 00000003    ....\r\nZynq> ")
        self.assertEqual(axi.parse_md(reply, 0x10000000, 4),
                         [0xAABBCCDD, 1, 2, 3])

    def test_it_refuses_a_short_dump(self) -> None:
        reply = b"10000000: aabbccdd 00000001    ..\r\nZynq> "
        with self.assertRaises(axi.AxiRefusal):
            axi.parse_md(reply, 0x10000000, 4)

    def test_it_refuses_a_dump_whose_addresses_do_not_follow(self) -> None:
        reply = (b"10000000: 00000000 00000000 00000000 00000000    ....\r\n"
                 b"10000020: 00000000 00000000 00000000 00000000    ....\r\nZynq> ")
        with self.assertRaises(axi.AxiRefusal) as caught:
            axi.parse_md(reply, 0x10000000, 8)
        self.assertIn("out of order", str(caught.exception))

    def test_an_ascii_column_that_looks_like_hex_is_not_read_as_data(self) -> None:
        """`print_buffer` renders unprintables as dots, but a frame of ASCII text would
        put eight plausible hex characters in the right-hand column."""
        reply = (b"10000000: 61626364 61626364 61626364 61626364    abcdabcdabcdabcd\r\n"
                 b"Zynq> ")
        self.assertEqual(axi.parse_md(reply, 0x10000000, 4), [0x61626364] * 4)


if __name__ == "__main__":
    unittest.main()
