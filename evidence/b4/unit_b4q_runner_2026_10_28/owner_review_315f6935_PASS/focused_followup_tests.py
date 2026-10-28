"""Focused approved-patch regression using retained fixture archives, not another native 47-case regeneration."""
import sys,unittest
from pathlib import Path
root=Path(sys.argv[1]).resolve();sys.path[:0]=[str(root),str(root/'host'),str(root/'b4/host')]
from tests import test_b4q_runner as t
t._S['runner']=root/'evidence/b4/unit_b4q_runner_2026_10_28/e2e_runner'
t.setUpModule=lambda:None
suite=unittest.defaultTestLoader.loadTestsFromTestCase(t.StateMachineRound3)
r=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if r.wasSuccessful() else 1)
