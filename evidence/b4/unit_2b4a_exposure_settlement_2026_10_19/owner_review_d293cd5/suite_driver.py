import sys,pathlib,unittest
from unittest import mock
s=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(s/'b4/host'))
import b4_seeds as bs
original=bs.master_seed;blocked=[]
def guard(label,anchor):
 if isinstance(label,str) and (label.startswith('b4-sim-') or label.startswith('b4-gate-')):
  blocked.append(label);raise AssertionError('OWNER: production master derivation forbidden during review')
 return original(label,anchor)
with mock.patch.object(bs,'master_seed',side_effect=guard):
 result=unittest.TextTestRunner(verbosity=2).run(unittest.TestLoader().discover(str(s/'b4/tests'),pattern='test_b4_*.py'))
print('Owner outer guard blocked production derivations:',blocked)
raise SystemExit(not result.wasSuccessful() or bool(blocked))
