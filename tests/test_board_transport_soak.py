#!/usr/bin/env python3
"""The U-Boot repeated-read consistency control, proved offline against a fake U-Boot — never a
real port. Every finding of the owner's review of 2026-09-13 has a test here that FAILS on the
reviewed implementation: byte-exact comparison over the whole framed body (an ASCII-column
deletion and a ninth hex digit both read as clean before), the acquisition/finalisation contract
the rig already settled, a deadline that bounds the active command, window and exposure
validation before the port opens, and a provenance that names this tool rather than its helper.

The design's declared blind spot is tested as a blind spot, not as a detection: a corruption
present identically in the reference and every later response is invisible here by construction.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import types
import unittest
import unittest.mock
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import board_transport_soak as soak  # noqa: E402


def md_reply(addr: int, words: list[int]) -> bytes:
    """A U-Boot `md.l` reply body plus the prompt, in `print_buffer`'s exact shape."""
    out = bytearray()
    for i in range(0, len(words), 4):
        row = words[i:i + 4]
        hexpart = "".join(f" {w:08x}" for w in row)
        ascii_part = b"." * (len(row) * 4)
        out += f"{addr + i * 4:08x}:{hexpart}    ".encode() + ascii_part + b"\r\n"
    out += b"Zynq> "
    return bytes(out)


class FakeBoard:
    """A `serial.Serial` double. `mutate(index, reply) -> reply` rewrites the nth md answer
    (index 0 is the reference). Reads advance a virtual clock by the timeout they were given."""

    def __init__(self, addr, words, mutate=None, echo=False, detach_at=None, silent_from=None):
        self.addr, self.words, self.mutate = addr, words, mutate
        self.echo, self.detach_at, self.silent_from = echo, detach_at, silent_from
        self.pending = bytearray()
        self.index = -1
        self.now = 0.0
        self.closed = 0
        self.commands: list[str] = []
        self.detached = False
        self.timeout = self.write_timeout = None

    def write(self, data):
        text = bytes(data)
        if text == b"\r":
            self.pending += b"Zynq> "
            return len(data)
        line = text.decode().rstrip("\r")
        self.commands.append(line)
        self.index += 1
        if self.echo:
            self.pending += line.encode() + b"\r\n"
        if self.silent_from is not None and self.index >= self.silent_from:
            return len(data)
        reply = md_reply(self.addr, self.words)
        if self.mutate is not None:
            reply = self.mutate(self.index, reply)
        self.pending += reply
        return len(data)

    def read(self, n):
        self.now += self.timeout or 0.0
        if self.detach_at is not None and self.index == self.detach_at:
            if self.detached:
                raise OSError("synthetic detach mid-response")
            self.detached = True
            out, self.pending = bytes(self.pending[:20]), self.pending[20:]
            return out
        out, self.pending = bytes(self.pending[:n]), self.pending[n:]
        return out

    def fileno(self):
        return 999999

    def close(self):
        self.closed += 1


class TheConsistencyControl(unittest.TestCase):
    ADDR = soak.WINDOW_BASE
    WORDS = [0xA5A5A5A5, 0x5A5A5A5A, 0xDEADBEEF, 0xCAFEF00D]

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="ctl_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.d, ignore_errors=True))
        self.boards: list[FakeBoard] = []

    def module(self, fail_open=False, **kw):
        boards, addr, words = self.boards, self.ADDR, self.WORDS

        class S:
            def __init__(self, device, baud, **kwargs):
                if fail_open:
                    raise OSError(f"could not open port {device}")
                b = FakeBoard(addr, words, **kw)
                b.timeout, b.write_timeout = kwargs.get("timeout"), kwargs.get("write_timeout")
                boards.append(b)
                self._b = b

            def __getattr__(self, n):
                return getattr(self._b, n)

            def __setattr__(self, n, v):
                # serial_port sets `s.timeout = t` before every read; that MUST reach the board,
                # otherwise the fake advances its clock by a stale timeout and a deadline that
                # does not bound the read still looks bounded.
                if n == "_b":
                    object.__setattr__(self, n, v)
                else:
                    setattr(self._b, n, v)
        return types.SimpleNamespace(Serial=S)

    def run_cli(self, *extra, module=None, out=None, ident=None, fault_export=(), patches=()):
        import contextlib
        import io
        argv = ["--device", "/dev/ebaz-uart", "--label", "t", "--out", str(out or self.d),
                "--addr", hex(self.ADDR), "--words", str(len(self.WORDS)),
                "--repetitions", "4", "--expect-usb", "", *extra]
        ch340 = ident or {"path": "/dev/ebaz-uart", "usb": {"idVendor": "1a86", "idProduct": "7523"}}
        mod = module or self.module()
        original_write = soak._write_evidence

        def export(path, data):
            if path.name in fault_export:
                raise OSError(f"synthetic {path.name} write failure")
            return original_write(path, data)
        buf = io.StringIO()
        boards = self.boards
        with contextlib.ExitStack() as st:
            st.enter_context(unittest.mock.patch.dict(sys.modules, {"serial": mod}))
            st.enter_context(unittest.mock.patch.object(soak, "device_identity", lambda p: dict(ch340)))
            st.enter_context(unittest.mock.patch.object(soak, "_write_evidence", export))
            st.enter_context(unittest.mock.patch.object(
                soak.time, "monotonic", lambda: boards[0].now if boards else 0.0))
            for p in patches:
                st.enter_context(p)
            st.enter_context(contextlib.redirect_stdout(buf))
            code = soak.main(argv)
        return code, json.loads(buf.getvalue().strip().splitlines()[-1])

    # ---------------------------------------------------------------- the clean control

    def test_identical_responses_run_to_completion_and_export_everything(self):
        code, brief = self.run_cli()
        self.assertEqual(code, 0, brief)
        self.assertEqual(brief["terminal"], "exposure_repetitions")
        self.assertEqual((brief["mismatched_responses"], brief["identical_responses"]), (0, 4))
        for name in ("invocation.json", "sync.bin", "reference.bin", "reference.json",
                     "control.json", "entry.json", "read_0000.bin"):
            self.assertTrue((self.d / name).is_file(), name)
        self.assertTrue(brief["export_complete"])
        self.assertEqual(self.boards[0].closed, 1)
        self.assertEqual(brief["ports_closed"], ["/dev/ebaz-uart"])
        self.assertEqual(json.loads((self.d / "entry.json").read_text()), brief)

    def test_the_command_echo_and_prompt_are_the_only_declared_framing_exclusions(self):
        code, brief = self.run_cli(module=self.module(echo=True))
        self.assertEqual(code, 0, brief)
        self.assertEqual(brief["mismatched_responses"], 0)
        ref = json.loads((self.d / "reference.json").read_text())
        self.assertTrue(ref["framing"]["echo_removed"] and ref["framing"]["prompt_removed"])
        body = soak.split_framing(md_reply(self.ADDR, self.WORDS), "md.l")[0]
        self.assertNotIn(b"Zynq>", body)

    # ---------------------------------------------------------------- P2-2, byte-exact comparison

    def test_a_deleted_byte_in_the_ascii_column_is_a_mismatch(self):
        """Reviewed behaviour: the parser matched a prefix and ignored the rest, so deleting a
        byte from the ASCII rendering column reported ZERO damage over the whole run."""
        def mutate(i, reply):
            return reply.replace(b"." * 16, b"." * 15) if i >= 1 else reply
        code, brief = self.run_cli(module=self.module(mutate=mutate))
        self.assertEqual(code, 0, brief)
        self.assertEqual(brief["mismatched_responses"], 3)      # stops at the third
        self.assertEqual(brief["terminal"], "stop_rule_mismatches")
        rec = [r for r in json.loads((self.d / "control.json").read_text())["reads"]
               if r.get("outcome") == "mismatch"][0]
        self.assertEqual(rec["body_delta_bytes"], -1)
        self.assertIsNotNone(rec["first_diff_offset"])

    def test_a_ninth_hex_digit_is_a_mismatch_and_fails_the_grammar(self):
        """Reviewed behaviour: `cafef00d` -> `cafef00d0` still parsed as eight digits and the
        extra byte was ignored."""
        def mutate(i, reply):
            return reply.replace(b"cafef00d", b"cafef00d0") if i >= 1 else reply
        code, brief = self.run_cli(module=self.module(mutate=mutate))
        self.assertEqual(brief["mismatched_responses"], 3, brief)
        rec = [r for r in json.loads((self.d / "control.json").read_text())["reads"]
               if r.get("outcome") == "mismatch"][0]
        self.assertEqual(rec["body_delta_bytes"], 1)
        self.assertFalse(rec["grammar_valid"])                  # not accounted for end to end
        self.assertIsNotNone(rec["grammar_error"])              # here: the word count no longer adds up

    def test_damage_in_every_region_of_the_response_is_caught(self):
        regions = {
            "address_digit": (b"00100000:", b"00100004:"),
            "hex_word": (b"deadbeef", b"deadbeee"),
            "inter_word_space": (b" 5a5a5a5a", b"  5a5a5a5a"),
            "ascii_column": (b"." * 16, b"......x........."),
        }
        for name, (old, new) in regions.items():
            with self.subTest(region=name):
                self.boards.clear()

                def mutate(i, reply, _o=old, _n=new):
                    return reply.replace(_o, _n) if i >= 1 else reply
                code, brief = self.run_cli(module=self.module(mutate=mutate), out=self.d / name)
                self.assertEqual(code, 0, brief)
                self.assertGreaterEqual(brief["mismatched_responses"], 1, f"{name}: {brief}")

    def test_a_multi_line_response_is_compared_over_all_of_its_lines(self):
        self.WORDS = [0x11111111] * 8 + [0x22222222] * 4        # three lines; damage the last
        self.boards.clear()

        def mutate(i, reply):
            return reply.replace(b"22222222", b"22222223") if i >= 1 else reply
        code, brief = self.run_cli("--words", "12", module=self.module(mutate=mutate))
        self.assertGreaterEqual(brief["mismatched_responses"], 1, brief)
        rec = [r for r in json.loads((self.d / "control.json").read_text())["reads"]
               if r.get("outcome") == "mismatch"][0]
        self.assertGreater(rec["first_diff_offset"], 100)       # the damage is in the third line

    def test_an_identical_corruption_in_every_response_is_a_declared_blind_spot(self):
        """Not a detection: the reference is an OBSERVATION, so a corruption present in it and in
        every later response cannot be seen. The tool must SAY so rather than imply cleanliness."""
        def mutate(i, reply):
            return reply.replace(b"a5a5a5a5", b"a5a5a5a4")
        code, brief = self.run_cli(module=self.module(mutate=mutate))
        self.assertEqual(code, 0, brief)
        self.assertEqual(brief["mismatched_responses"], 0)      # invisible, by construction
        ref = json.loads((self.d / "reference.json").read_text())
        self.assertIn("invisible by construction", ref["note"])
        self.assertIn("unknown", brief["cause_of_a_mismatch"])
        result = json.loads((self.d / "control.json").read_text())
        self.assertIn("no bound on B2Q frame loss", result["claims_not_made"])

    # ---------------------------------------------------------------- P2-3, the acquisition contract

    def test_a_provenance_failure_stops_before_the_port_opens(self):
        p = unittest.mock.patch.object(soak, "provenance", side_effect=OSError("synthetic provenance failure"))
        code, brief = self.run_cli(patches=(p,))
        self.assertEqual(code, 2, brief)
        self.assertEqual(brief["stage"], "invocation")
        self.assertIn("synthetic provenance failure", brief["error"])
        self.assertEqual(self.boards, [])                       # no port, no command
        self.assertFalse((self.d / "control.json").exists())
        inv = json.loads((self.d / "invocation.json").read_text())
        self.assertEqual(inv["terminal"]["reason"], "tool_error")
        self.assertTrue(any("provenance" in e for e in inv["construction_errors"]))

    def test_a_detach_mid_response_keeps_the_partial_bytes_and_finalises(self):
        code, brief = self.run_cli(module=self.module(detach_at=1))
        self.assertEqual(code, 2, brief)
        self.assertIn("synthetic detach", brief["detail"])
        self.assertTrue((self.d / "read_0000.bin").is_file())
        self.assertEqual(len((self.d / "read_0000.bin").read_bytes()), 20)   # the partial bytes survive
        result = json.loads((self.d / "control.json").read_text())           # finalisation happened
        self.assertEqual(result["terminal"]["reason"], "tool_error")
        self.assertEqual(result["terminal"]["partial_bytes"], 20)
        for k in ("counters_before", "counters_after"):
            self.assertIn("reason", result[k])                               # both attempted
        self.assertTrue((self.d / "entry.json").is_file())
        self.assertEqual(self.boards[0].closed, 1)

    def test_a_failed_control_export_is_reported_and_does_not_claim_completeness(self):
        code, brief = self.run_cli(fault_export=("control.json",))
        self.assertEqual(code, 0, brief)
        self.assertFalse(brief["export_complete"])
        self.assertTrue(any("control.json" in e for e in brief["entry_export_errors"]))

    def test_a_failed_entry_export_is_recomputed_into_the_printed_result(self):
        """Reviewed behaviour: entry.json failed to write and stdout still said
        `export_complete: true`."""
        code, brief = self.run_cli(fault_export=("entry.json",))
        self.assertEqual(code, 0, brief)
        self.assertIsNone(brief["entry_record"])
        self.assertFalse(brief["export_complete"])
        self.assertTrue(any("entry.json" in e for e in brief["entry_export_errors"]))
        self.assertFalse((self.d / "entry.json").exists())
        self.assertTrue((self.d / "control.json").is_file())    # the acquisition record still landed

    def test_a_device_that_will_not_open_is_exit_4(self):
        code, brief = self.run_cli(module=self.module(fail_open=True))
        self.assertEqual(code, 4, brief)
        self.assertTrue((self.d / "open_error.json").is_file())

    def test_a_nonempty_destination_is_refused_byte_untouched(self):
        (self.d / "control.json").write_bytes(b"old")
        code, brief = self.run_cli()
        self.assertEqual(code, 5, brief)
        self.assertEqual((self.d / "control.json").read_bytes(), b"old")
        self.assertEqual(self.boards, [])
        self.assertIsNone(brief["entry_record"])

    # ---------------------------------------------------------------- P2-4, the deadline

    def test_the_exposure_bounds_the_active_command_not_only_the_gaps(self):
        """Reviewed behaviour: with a tiny `--seconds` a board that stopped answering still burned
        a full ~3 s inside one read, because each command got its own independent budget."""
        code, brief = self.run_cli("--seconds", "0.5", "--command-timeout", "3.0",
                                   module=self.module(silent_from=1))
        self.assertLessEqual(self.boards[0].now, 0.5 + 1e-9, brief)
        self.assertEqual(brief["terminal"], "exposure_seconds")
        self.assertTrue(json.loads((self.d / "control.json").read_text())["terminal"]["cut_short"])

    def test_a_missing_prompt_without_a_banner_is_not_called_a_board_reset(self):
        code, brief = self.run_cli("--seconds", "100", "--command-timeout", "1.0",
                                   module=self.module(silent_from=1))
        self.assertEqual(code, 2, brief)
        self.assertEqual(brief["terminal"], "no_prompt")
        self.assertIn("cause unknown", brief["detail"])

    def test_an_observed_boot_banner_is_a_board_reset(self):
        def mutate(i, reply):
            return b"\r\nU-Boot SPL 2026.04\r\n" if i >= 1 else reply
        code, brief = self.run_cli("--seconds", "100", "--command-timeout", "1.0",
                                   module=self.module(mutate=mutate))
        self.assertEqual(code, 2, brief)
        self.assertEqual(brief["terminal"], "board_reset")

    def test_no_prompt_at_the_sync_refuses_before_any_md_is_issued(self):
        boards, addr, words = self.boards, self.ADDR, self.WORDS

        class S:
            def __init__(self, device, baud, **kwargs):
                b = FakeBoard(addr, words)
                b.timeout = kwargs.get("timeout")
                b.write = lambda data: len(data)                # answers nothing, ever
                boards.append(b)
                self._b = b

            def __getattr__(self, n):
                return getattr(self._b, n)

            def __setattr__(self, n, v):
                object.__setattr__(self, n, v) if n == "_b" else setattr(self._b, n, v)
        code, brief = self.run_cli("--command-timeout", "0.5",
                                   module=types.SimpleNamespace(Serial=S))
        self.assertEqual(code, 3, brief)
        self.assertEqual(brief["refusal"], "no_prompt_at_sync")
        self.assertEqual(self.boards[0].commands, [])           # no md.l was ever sent
        self.assertTrue((self.d / "control.json").is_file())    # the refusal is still recorded

    def test_no_valid_reference_response_refuses_before_the_repeated_reads(self):
        def mutate(i, reply):
            return b"garbage that is not md output\r\nZynq> " if i == 0 else reply
        code, brief = self.run_cli(module=self.module(mutate=mutate))
        self.assertEqual(code, 3, brief)
        self.assertEqual(brief["refusal"], "reference")
        self.assertEqual(len(self.boards[0].commands), 1)       # only the reference attempt

    # ---------------------------------------------------------------- P2-5, the reviewed window

    def test_an_address_outside_the_reviewed_window_is_refused_before_the_port_opens(self):
        """Reviewed behaviour: `--addr 0x40000000` emitted `md.l 0x40000000 0x4` to the board."""
        code, brief = self.run_cli("--addr", "0x40000000")
        self.assertEqual(code, 3, brief)
        self.assertEqual(brief["refusal"], "window")
        self.assertIn("reviewed probe window", brief["refused"])
        self.assertEqual(self.boards, [])                       # never opened, nothing emitted

    def test_the_window_check_covers_alignment_length_and_the_end_address(self):
        cases = {
            "--addr 0x00100002": "aligned",
            "--addr 0x000ffffc": "below",
            "--words 0": "words must be",
            "--words 0x4000": "words must be",
            "--addr 0x001ffff0 --words 0x10": "leaves the reviewed probe window",
        }
        for args, expect in cases.items():
            with self.subTest(args=args):
                self.boards.clear()
                name = args.replace(" ", "_").replace("--", "").replace("0x", "")
                code, brief = self.run_cli(*args.split(), out=self.d / name)
                self.assertEqual(code, 3, brief)
                self.assertIn(expect, brief["refused"])
                self.assertEqual(self.boards, [])
        self.assertIsNone(soak.validate_window(soak.WINDOW_BASE, 4))          # the positive control

    def test_a_nonfinite_or_nonpositive_exposure_is_refused(self):
        for args in ("--seconds 0", "--seconds nan", "--command-timeout -1"):
            with self.subTest(args=args):
                self.boards.clear()
                name = args.replace(" ", "_").replace("--", "")
                code, brief = self.run_cli(*args.split(), out=self.d / name)
                self.assertEqual(code, 3, brief)
                self.assertEqual(brief["refusal"], "exposure")
                self.assertEqual(self.boards, [])

    # ---------------------------------------------------------------- P2-6, provenance and claims

    def test_the_provenance_names_this_tool_and_its_dependency_separately(self):
        """Reviewed behaviour: `tool_sha256` was transport_rig's digest, so edits to this file
        were invisible in the acquisition record."""
        import transport_rig
        mine = hashlib.sha256(Path(soak.__file__).read_bytes()).hexdigest()
        rig = hashlib.sha256(Path(transport_rig.__file__).read_bytes()).hexdigest()
        self.assertNotEqual(mine, rig)
        p = soak.provenance()
        self.assertEqual(p["tool_sha256"], mine)
        self.assertEqual(p["tool"], "host/board_transport_soak.py")
        self.assertEqual(p["dependencies"]["host/transport_rig.py"], rig)
        self.assertIn("response", p["measurement_unit"])         # responses, not expected frames
        code, brief = self.run_cli()
        self.assertEqual(
            json.loads((self.d / "control.json").read_text())["provenance"]["tool_sha256"], mine)

    def test_the_record_states_the_unit_and_refuses_the_b2q_claims(self):
        code, brief = self.run_cli()
        self.assertIn("response", brief["measurement_unit"])
        self.assertIn("unknown", brief["cause_of_a_mismatch"])
        result = json.loads((self.d / "control.json").read_text())
        self.assertIn("not a lost rel-v4 frame", result["claims_not_made"])
        inv = json.loads((self.d / "invocation.json").read_text())
        self.assertIn("mandatory operator check", inv["identity_note"])
        self.assertIn("MANDATORY OPERATOR CHECK", inv["probe_window"]["note"])

    def test_the_stop_rule_is_named_as_a_run_total_and_is_configurable(self):
        def mutate(i, reply):
            return reply.replace(b"deadbeef", b"deadbeee") if i >= 1 else reply
        code, brief = self.run_cli("--stop-after-mismatches", "2", module=self.module(mutate=mutate))
        self.assertEqual(brief["mismatched_responses"], 2)
        self.assertEqual(brief["terminal"], "stop_rule_mismatches")
        self.assertIn("run-total rule", brief["detail"])
        self.assertIn("NOT the rig's", brief["detail"])

    def test_the_adapter_check_is_refused_when_the_identity_is_wrong(self):
        ftdi = {"path": "/dev/ebaz-uart", "usb": {"idVendor": "0403", "idProduct": "6001"}}
        code, brief = self.run_cli("--expect-usb", "1a86:7523", ident=ftdi)
        self.assertEqual(code, 3, brief)
        self.assertEqual(brief["refusal"], "identity")
        self.assertEqual(self.boards, [])

    def test_parse_response_rejects_prefix_matches_and_leftover_bytes(self):
        good = soak.split_framing(md_reply(self.ADDR, self.WORDS), "md.l")[0]
        vals, err = soak.parse_response(good, self.ADDR, 4)
        self.assertIsNone(err)
        self.assertEqual(vals, self.WORDS)
        bad, e = soak.parse_response(good + b"\r\ntrailing junk", self.ADDR, 4)
        self.assertIsNone(bad)
        self.assertIn("grammar", e)
        self.assertIsNone(soak.parse_response(b"", self.ADDR, 4)[0])


if __name__ == "__main__":
    unittest.main()
