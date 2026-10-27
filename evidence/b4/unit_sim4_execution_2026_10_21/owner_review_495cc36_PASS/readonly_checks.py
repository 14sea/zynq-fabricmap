from pathlib import Path
import hashlib, json, subprocess, runpy, sys
R=Path('/home/test/zynq_fabricmap')
sys.path.insert(0,str(R/'b4/host'))
import b4_seeds as bs, b4_sim as sim, b4_ff_model as fm
calls={k:0 for k in ['master_seed','pair_seeds','preflight','run_batch','observe']}
def guard(name):
 def refuse(*args,**kwargs):
  calls[name]+=1
  raise AssertionError('forbidden call during read-only review: '+name)
 return refuse
for name in ['master_seed','pair_seeds']:setattr(bs,name,guard(name))
for name in ['preflight','run_batch']:setattr(sim,name,guard(name))
fm.Fabric.observe=guard('observe')
print('READ_ONLY_INVENTORY_WITH_CALL_GUARDS')
runpy.run_path(str(R/'evidence/b4/unit_sim4_plan_2026_10_21/inventory.py'),run_name='__main__')
print('GUARD_CALLS',json.dumps(calls,sort_keys=True))
assert all(v==0 for v in calls.values())
print('IMPORT_CHECK')
runpy.run_path(str(R/'evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py'),run_name='__main__')
