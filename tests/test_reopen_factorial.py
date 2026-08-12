"""The 2x2 reopen experiment, and the two ways it could stop being one.

It could vary something it does not name -- by opening the port itself instead of using the
production path, which is exactly what condition A exists to detect and would therefore be
measuring its own scaffolding. And parameterising `Probe` could change what production does,
which would silently rewrite the thing under investigation.
"""

from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_isolate_carrier as iso  # noqa: E402
import board_probe_reopen_factorial as fac  # noqa: E402

SOURCE = Path(fac.__file__).read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


class ProductionIsUnchanged(unittest.TestCase):
    def test_probe_still_sends_a_cr_by_default(self):
        """Every existing caller passes no flag, so the default IS production behaviour."""
        self.assertIs(inspect.signature(iso.Probe.__init__).parameters["send_cr"].default,
                      True)

    def test_send_cr_is_keyword_only(self):
        """A positional flag could be set by accident from an existing call site."""
        self.assertEqual(inspect.signature(iso.Probe.__init__).parameters["send_cr"].kind,
                         inspect.Parameter.KEYWORD_ONLY)

    def test_only_the_experiment_passes_send_cr_at_a_call_site(self):
        """Defining the parameter is fine anywhere; PASSING it is what changes behaviour."""
        passers = set()
        for path in sorted((REPO_ROOT / "scripts").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and any(
                        kw.arg in {"send_cr", "purge"} for kw in node.keywords):
                    passers.add(path.name)
        self.assertEqual(passers, {"board_probe_reopen_factorial.py"})

    def probe_init_code(self) -> str:
        """The body with the docstring dropped -- prose about a call is not a call."""
        func = ast.parse(inspect.getsource(iso.Probe.__init__).lstrip()).body[0]
        statements = [node for node in func.body
                      if not (isinstance(node, ast.Expr)
                              and isinstance(node.value, ast.Constant)
                              and isinstance(node.value.value, str))]
        return "\n".join(ast.unparse(node) for node in statements)

    def test_the_settle_keeps_the_bytes_AND_still_purges(self):
        """Keeping the bytes is not a substitute for the flush.

        `reset_input_buffer()` is `tcflush(TCIFLUSH)`, issued to the tty layer and the
        USB-serial driver; a read only moves bytes. The buffer ends up empty either way, but
        the driver operation differs and the purge is itself a candidate trigger. So the read
        must come first and the purge must still happen by default.
        """
        code = self.probe_init_code()
        self.assertIn("discarded_on_open", code)
        self.assertIn("reset_input_buffer", code)
        self.assertLess(code.index("discarded_on_open"), code.index("reset_input_buffer"))

    def test_purge_defaults_to_the_historical_behaviour(self):
        self.assertIs(inspect.signature(iso.Probe.__init__).parameters["purge"].default, True)
        self.assertEqual(inspect.signature(iso.Probe.__init__).parameters["purge"].kind,
                         inspect.Parameter.KEYWORD_ONLY)


class ItUsesTheProductionPath(unittest.TestCase):
    def test_it_never_constructs_a_serial_port_of_its_own(self):
        self.assertNotIn("serial.Serial", SOURCE)

    def test_every_reopen_goes_through_probe(self):
        constructed = {ast.unparse(node.func) for node in ast.walk(TREE)
                       if isinstance(node, ast.Call)}
        self.assertIn("iso.Probe", constructed)

    def test_the_baseline_is_the_only_carrier_read(self):
        """A stall costs a power cycle and answers nothing this experiment asks."""
        reads = [node for node in ast.walk(TREE)
                 if isinstance(node, ast.Call) and "read_word" in ast.dump(node.func)]
        self.assertEqual(len(reads), 1)


class TheDesign(unittest.TestCase):
    def test_a_to_d_are_the_two_by_two_without_the_purge(self):
        self.assertEqual([(gap > 0, cr, purge) for _, gap, cr, purge in fac.CONDITIONS[:4]],
                         [(True, False, False), (False, False, False),
                          (True, True, False), (False, True, False)])

    def test_e_is_the_historical_path_and_runs_last(self):
        """Back-to-back, CR, purge — exactly what the three restarts went through."""
        name, gap, cr, purge = fac.CONDITIONS[-1]
        self.assertEqual(name, "E")
        self.assertEqual(gap, 0.0)
        self.assertTrue(cr)
        self.assertTrue(purge)

    def test_f_isolates_the_purge_from_the_cr(self):
        """Without a purge-and-no-CR cell, E could never say which half mattered."""
        name, gap, cr, purge = fac.CONDITIONS[-2]
        self.assertEqual(name, "F")
        self.assertEqual(gap, 0.0)
        self.assertFalse(cr)
        self.assertTrue(purge)

    def test_every_condition_has_a_written_reading(self):
        self.assertEqual(set(fac.INTERPRETATION), {name for name, _, _, _ in fac.CONDITIONS})

    def test_the_order_is_a_b_c_d_f_e(self):
        self.assertEqual([name for name, _, _, _ in fac.CONDITIONS],
                         ["A", "B", "C", "D", "F", "E"])

    def test_the_gap_is_measured_before_the_settle_not_after(self):
        """Probe sleeps 0.4 s inside __init__, so timing after it calls 7 ms "0.407 s"."""
        self.assertIn("gap_close_to_open_s", SOURCE)
        # The baseline `iso.Probe(args.port)` comes earlier in the file, so the trial's
        # reopen has to be named by its keywords rather than by the first match.
        self.assertLess(SOURCE.index("opened_at = time.monotonic()"),
                        SOURCE.index("probe = iso.Probe(args.port, send_cr="))


class UdevWatchParsing(unittest.TestCase):
    def test_the_two_header_lines_are_not_counted_as_events(self):
        self.assertEqual(fac.UdevWatch.HEADER_LINES, 2)

    def test_a_header_only_file_yields_no_events(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
            handle.write("monitor will print the received events for:\n"
                         "UDEV - the event which udev sends out after rule processing\n\n")
            path = Path(handle.name)
        watch = fac.UdevWatch.__new__(fac.UdevWatch)
        watch.path = path
        watch.handle = path.open("a")
        try:
            self.assertEqual(watch.events(), [])
        finally:
            watch.handle.close()
            path.unlink()


if __name__ == "__main__":
    unittest.main()
