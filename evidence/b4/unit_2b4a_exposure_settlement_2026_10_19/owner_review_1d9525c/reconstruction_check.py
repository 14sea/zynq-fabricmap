import pathlib,subprocess,importlib.util,sys,tempfile,hashlib,json
R=pathlib.Path('/home/test/zynq_fabricmap');D=pathlib.Path(__file__).resolve().parent
P=R/'evidence/b4/unit_2b4a_exposure_settlement_2026_10_19';receipt=json.loads((P/'exposure_receipt.json').read_bytes());result={}
sha=lambda b:hashlib.sha256(b).hexdigest();canon=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
with tempfile.TemporaryDirectory(prefix='b4_owner_hist_') as t:
 t=pathlib.Path(t)
 for name in ('b4_seeds.py','b4_rng.py'):
  raw=subprocess.check_output(['git','show','edfc93c:b4/host/'+name],cwd=R);(t/name).write_bytes(raw)
  assert sha(raw)==receipt['historical_inputs']['files']['b4/host/'+name]['sha256']
 sys.path.insert(0,str(t));spec=importlib.util.spec_from_file_location('owner_hist_seed',t/'b4_seeds.py');hist=importlib.util.module_from_spec(spec);sys.modules[spec.name]=hist;spec.loader.exec_module(hist)
 ex=hist.load_exclusion_set(R);assert not ex.registry
 result['base_count']=len(ex.values);result['base_pool_sha256']=sha(canon(sorted(ex.values)).encode());assert result['base_pool_sha256']==receipt['historical_inputs']['base_pool_sha256']
 anchor=receipt['historical_inputs']['anchor_hypothesis_sha256'];master={l:hist.master_seed(l,anchor) for l in ('b4-sim-1','b4-sim-2')};pool=set(ex.values);vs=[]
 for k in range(1,8):
  pairs=hist.pair_seeds(master['b4-sim-1'],2,pool);vs.append(('V'+str(k),'b4-sim-1',pairs,len(pool)))
  pool.add(master['b4-sim-1']);pool.update(v for p in pairs for v in p)
 for vid,pool2 in [('V8',set(ex.values)|{master['b4-sim-1']}|{v for p in vs[0][2] for v in p}),('V9',set(ex.values))]:vs.append((vid,'b4-sim-2',hist.pair_seeds(master['b4-sim-2'],2,pool2),len(pool2)))
 byid={v['id']:v for v in receipt['variants']};vals=set();result['variants']={}
 for vid,label,pairs,n in vs:
  v=byid[vid];assert v['master_seed']==master[label] and v['pairs']==[list(p) for p in pairs] and v['exclusion_pooled_total']==n
  controls=[]
  for i,(l,o) in enumerate(pairs):
   controls.append({'pair':i,'x_control_seed':int.from_bytes(hashlib.sha256(f'b4-x-control-1|{l}|{o}'.encode()).digest()[:4],'big'),'d_shuffle_seed':int.from_bytes(hashlib.sha256(f'b4-d-control-1|{l}|{o}'.encode()).digest()[:4],'big')})
  assert v['control_seeds']==controls
  vals.add(master[label]);vals.update(x for pair in pairs for x in pair);vals.update(c[k] for c in controls for k in ('x_control_seed','d_shuffle_seed'))
  result['variants'][vid]='master/pairs/controls/pool count equal'
 assert sorted(vals)==receipt['pooled'];result['receipt_count']=len(vals);result['current_pool_count']=len(set(ex.values)|vals)
 records=list((R/'evidence/b4/unit_2b4a_repair_2026_10_18/exposure').rglob('seeds.json'));checks=[]
 for path in records:
  d=json.loads(path.read_bytes());v=byid['V'+str(len(d['exclusion']['sim_registry'])+1)]
  assert d['master_seed']==v['master_seed'] and d['pairs']==v['pairs'] and d['exclusion']['pooled_total']==v['exclusion_pooled_total']
  assert d['exclusion']['sources']==[s.as_dict() for s in ex.sources] and d['exclusion']['b4_exposed_values']==list(ex.b4_exposed)
  ref=next(x for x in receipt['preserved_records'] if x['path']==str(path.relative_to(R)));assert ref['sha256']==sha(path.read_bytes())
  checks.append({'path':str(path.relative_to(R)),'sha256':sha(path.read_bytes()),'agrees':True})
 result['preserved_records']=checks;result['no_new_label_derived']=True
(D/'reconstruction_check.json').write_text(json.dumps(result,indent=1,sort_keys=True)+'\n');print(json.dumps(result,indent=1,sort_keys=True))
