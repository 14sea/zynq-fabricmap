from pathlib import Path
import json,subprocess,sys,hashlib
D=Path(__file__).resolve().parent;S=json.loads((D/'snapshot.json').read_text());P=Path(S['temporary_root']);R=Path('/home/test/zynq_fabricmap');sys.path.insert(0,str(P/'b4/host'))
import b4_thresholds as th
source=subprocess.check_output(['git','show','e084f07:b4/host/b4_thresholds.py'],cwd=P,text=True)
g={'__file__':str(P/'b4/host/b4_thresholds.py'),'__name__':'owner_old_thresholds'}
exec(compile(source,'<e084f07:b4_thresholds.py>','exec'),g)
old=g['THRESHOLDS'];new=th.THRESHOLDS
same=[k for k in old if k not in ('source','task','gonogo','anchor')]
for k in same:assert json.dumps(old[k],sort_keys=True)==json.dumps(new[k],sort_keys=True),k
for k,v in old['gonogo'].items():assert new['gonogo']['p_max_go' if k=='alpha_go' else k]==v,k
for k,v in old['task'].items():
    if k!='version':assert new['task'][k]==v,k
for k,v in old['anchor'].items():
    if k not in ('exploration_label','consumed_labels'):assert new['anchor'][k]==v,k
protected=['b3','firmware','manifests','scripts','gate_runs','evidence/b1','evidence/b2','evidence/b3','evidence/b4/sim','evidence/b4/gate','evidence/b4/gonogo','host','rtl','vivado','tb','b4/hypothesis','b4/schemas','b4/probes','b4/host/b4_ff_model.py','b4/host/b4_ff_hypothesis.py','b4/host/b4_ff_mapping.py','b4/host/b4_engine.py','b4/host/b4_carto.py','b4/host/b4_k9.py','b4/host/b4_k10.py','b4/host/b4_gate_stats.py','b4/host/b4_stats.py','b4/host/b4_replay.py','b4/host/b4_execution.py']
changes=subprocess.check_output(['git','diff','--name-only','e084f07',S['reviewed_tip'],'--',*protected],cwd=R,text=True);assert not changes,changes
files=json.loads((P/'b4/IMPORT.json').read_text())['files'];bad=[f for f,e in files.items() if hashlib.sha256((P/f).read_bytes()).hexdigest()!=e['sha256']];assert not bad,bad
out={'threshold_blocks_unchanged':same,'gonogo_original_rules_unchanged_with_alpha_go_renamed_to_p_max_go':True,'original_target_rules_unchanged':True,'anchor_formula_hypothesis_gate_label_unchanged':True,'import_entries':len(files),'import_mismatches':bad,'protected_paths':protected,'protected_changes':changes.splitlines(),'method':'compare the historical table from its git blob; source text/revision excluded; no seed derivation or archive statistics read'}
(D/'scope_check.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
