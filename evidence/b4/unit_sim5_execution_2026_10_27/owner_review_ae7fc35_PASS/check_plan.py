from pathlib import Path
from contextlib import ExitStack, redirect_stdout
from unittest.mock import patch
import hashlib, json, runpy, subprocess, sys
R=Path('/home/test/zynq_fabricmap')
O=R/'build/wip/owner_review_ae7fc35_2026_10_27'
sys.path.insert(0,str(R/'b4/host'))
import b4_seeds as bs, b4_sim as sim, b4_protocol as bp, b4_thresholds as th

def git(*args):
    return subprocess.check_output(['git','-C',str(R),*args],text=True).strip()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
head=git('rev-parse','HEAD')
assert head.startswith('ae7fc35')
assert git('status','--porcelain','--untracked-files=all')==''
assert git('diff','--name-only','e20e12b','HEAD','--','b4/','rtl/','sim/','vivado/','host/','tests/','scripts/','firmware/','manifests/')==''
archive=R/'evidence/b4/unit_task_v03_2026_10_27/owner_review_e20e12b_PASS'
original=R/'build/wip/owner_review_e20e12b_2026_10_27'
checks=[]
for line in (archive/'SHA256SUMS').read_text().splitlines():
    dig,name=line.split(None,1); name=name.lstrip('* ')
    p=archive/name
    assert sha(p)==dig,name
    assert p.read_bytes()==(original/name).read_bytes(),name
    checks.append(name)
assert (archive/'SHA256SUMS').read_bytes()==(original/'SHA256SUMS').read_bytes()
ident=bp.identity(R)
assert bp.protocol_sha256(ident)=='5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f'
assert sha(R/'b4/IMPORT.json')=='9de52e257e2b5c733118b097ffdb5ba69b941726b815bace302a6d1d8eecf02b'
assert th.THRESHOLDS['gonogo']['p_max_go']==.2
assert (th.THRESHOLDS['gonogo']['S'],th.THRESHOLDS['gonogo']['B_go'],th.THRESHOLDS['gonogo']['k9_conditional_medians_min'])==(32,64,.5)
assert bs.EXPLORATION_LABEL=='b4-sim-5'
regs,_=bs.sim_registry(R)
assert sorted((r.dir.rsplit('/',1)[-1],len(r.values)) for r in regs)==[
('b4-gate-1_20261020T102526Z',401),('b4-sim-3_20261019T121833Z',65),('b4-sim-4_20261021T065339Z',65)]
ex=bs.load_exclusion_set(R)
assert (len(ex.values),len(ex.sources))==(2690,38)
assert bs.pinned_receipt_count()==66
assert sorted(p.name for p in (R/'evidence/b4/gonogo').iterdir())==['b4-sim-4_20261021T065857Z']
with ExitStack() as stack:
    guards=[stack.enter_context(patch.object(obj,name,side_effect=AssertionError('not authorised: '+name))) for obj,name in [(bs,'master_seed'),(bs,'pair_seeds'),(sim,'preflight'),(sim,'run_batch')]]
    with (O/'inventory_owner.txt').open('w') as f, redirect_stdout(f):
        runpy.run_path(str(R/'evidence/b4/unit_sim5_plan_2026_10_27/inventory.py'),run_name='__owner_inventory__')
    calls=[g.call_count for g in guards]
assert calls==[0,0,0,0]
with (O/'import_check.txt').open('w') as f,redirect_stdout(f):
    runpy.run_path(str(R/'evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py'),run_name='__owner_import__')
assert 'all equal: True' in (O/'import_check.txt').read_text()
assert 'without an entry: none' in (O/'import_check.txt').read_text()
assert git('status','--porcelain','--untracked-files=all')==''
out={'reviewed_head':head,'archived_review_payload_checksums_and_original_bytes_equal':len(checks),
'archived_SHA256SUMS_equal':True,'b4_and_protected_code_paths_changed':False,
'protocol_sha256':bp.protocol_sha256(ident),'registry_count':len(regs),'pooled_count':len(ex.values),'historical_sources':len(ex.sources),
'receipt_count':66,'production_derivation_and_batch_guard_calls':calls,
'guard_names':['master_seed','pair_seeds','preflight','run_batch'],'working_tree_clean':True}
(O/'independent_checks.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
