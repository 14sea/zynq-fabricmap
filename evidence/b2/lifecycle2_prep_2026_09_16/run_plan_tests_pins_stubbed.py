"""Scratch harness: run tests.test_b2_plan with the LIVE pin-table check stubbed.
On the new-lifecycle branch the edited test is off its pin until the table is regenerated
before the new S0, so the real check refuses every S2/S3 fixture. Diagnostic only."""
import sys, unittest
from pathlib import Path
from unittest import mock
R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / "host")); sys.path.insert(0, str(R / "tests"))
import b2_manifest as bman, b2_pins
with mock.patch.object(b2_pins, "verify", lambda manifest, root=None, b1_root=None, **k: {"stub": True}):
    import test_b2_plan
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_b2_plan)
    r = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if r.wasSuccessful() else 1)
