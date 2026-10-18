"""A contradictory elapsed-time record; no observations or seed derivations."""
import json,sys,shutil
from pathlib import Path
from unittest import mock
D=Path(__file__).resolve().parent;S=Path('/tmp/b4_owner_6c00156_3mc7z1rw');sys.path.insert(0,str(S/'b4/host'))
import b4_sim_verify as sv
import b4_seeds as bs
d=json.loads((D/'probes_results.json').read_bytes());base=Path(d['base']);p=Path(d['temp'])/'contradictory_report_deadline';shutil.copytree(base,p)
doc=json.loads((p/'sim_report.json').read_bytes());doc['deadline'].update(elapsed_s=10000.0,expired=False,first_expired_at_s=None)
(p/'sim_report.json').write_text(json.dumps(doc,sort_keys=True,indent=1)+'\n')
def forbid(*a,**kw):raise AssertionError('OWNER: production derivation forbidden')
with mock.patch.object(bs,'master_seed',side_effect=forbid),mock.patch.object(bs,'pair_seeds',side_effect=forbid):
 result={'path':str(p),'deadline':doc['deadline'],'status':doc['status'],'verify':sv.verify_run_dir(p)}
(D/'deadline_archive_results.json').write_text(json.dumps(result,indent=1)+'\n');print(json.dumps(result,indent=1))
