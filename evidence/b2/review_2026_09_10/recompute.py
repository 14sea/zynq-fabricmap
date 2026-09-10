from pathlib import Path
import json,sys,hashlib,subprocess,copy
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R/'host'))
import b2_gate as g,b2_search as s,b2_plan as p,b3_sim as sim,b2_maps as maps
load=lambda f:json.loads((R/f).read_text())
out={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'b2':{},'b3':{}}
gate=load('evidence/b2/gate/gate_report.json')
seedsets={}
for name,path in [('gate1','evidence/b2/gate/v0.1_2026-09-10/gate_report.json'),('gate3','evidence/b2/gate/gate_report.json'),('b3','evidence/b3/sim/sim_report.json')]:
 r=load(path);seeds=s.pair_seeds(r['seeds']['master_seed'],r['seeds']['count']);seedsets[name]={x for pair in seeds for x in pair}
 assert s.master_seed(r['seeds']['label'],r['head_at_run'])==r['seeds']['master_seed']
 if name!='gate1':
  code=['host/b2_search.py','host/b2_maps.py','host/b2_landscape.py']+(['host/b2_gate.py'] if name=='gate3' else ['host/b3_online.py','host/b3_sim.py'])
  for f in code:assert (R/f).read_bytes()==subprocess.check_output(['git','show',r['head_at_run']+':'+f],cwd=R),f
for fid,stored in gate['results'].items():
 rows=load('evidence/b2/gate/raw_'+fid+'.json')['rows']
 assert [(r['landscape_seed'],r['operator_seed']) for r in rows]==s.pair_seeds(gate['seeds']['master_seed'],200)
 got=g.evaluate(fid,rows)
 assert got=={k:v for k,v in stored.items() if k!='wall_s'},fid
 g._init_worker(fid)
 checked=[]
 for idx in (0,99,199):
  row=rows[idx];assert g._one_seed((idx,row['landscape_seed'],row['operator_seed']))==row,(fid,idx);checked.append(idx)
 out['b2'][fid]={'all_200_rows_statistics_reproduced':True,'all_arms_fresh_full_grid_rows':checked,'b_star':got['b_star'],'pass':got['pass']}
 print('b2 checked',fid,flush=True)
b3=load('evidence/b3/sim/sim_report.json')
for fid,stored in b3['results'].items():
 rows=load('evidence/b3/sim/raw_'+fid+'.json')['rows'];assert sim.summarise(fid,rows)=={k:v for k,v in stored.items() if k!='wall_s'}
 assert [(r['landscape_seed'],r['operator_seed']) for r in rows]==s.pair_seeds(b3['seeds']['master_seed'],200)
 sim._init(fid)
 checked=[]
 for idx in (0,199):
  row=rows[idx];assert sim._one((idx,row['landscape_seed'],row['operator_seed']))==row,(fid,idx);checked.append(idx)
 out['b3'][fid]={'all_200_rows_statistics_reproduced':True,'all_arms_fresh_full_grid_rows':checked,'online_map':stored['online_map']}
 print('b3 checked',fid,flush=True)
seedsets['session']={x for pair in s.pair_seeds(p.master if hasattr(p,'master') else s.master_seed(p.SESSION_LABEL,p.INSTRUMENT_COMMIT),9) for x in pair}
out['session_seed_overlap']={k:sorted(v&seedsets['session']) for k,v in seedsets.items() if k!='session'}
assert not any(out['session_seed_overlap'].values())
old=load('evidence/b2/plan.json');new=json.loads(Path('/tmp/b23_review/rebuilt_plan/plan.json').read_text());assert {k:v for k,v in old.items() if k!='generated_utc'}=={k:v for k,v in new.items() if k!='generated_utc'}
assert (R/'evidence/b2/prediction.json').read_bytes()==Path('/tmp/b23_review/rebuilt_plan/prediction.json').read_bytes()
out['plan_reproduced_except_generation_time']=True;out['prediction_bytes_reproduced']=True
out['map_hashes']={'file_sha256':hashlib.sha256(maps.SELF_MAP.read_bytes()).hexdigest(),'canonical_json_sha256':maps.sha256_of(maps.load_self_map())}
Path('/tmp/b23_review/recomputed.json').write_text(json.dumps(out,indent=2)+'\n')
