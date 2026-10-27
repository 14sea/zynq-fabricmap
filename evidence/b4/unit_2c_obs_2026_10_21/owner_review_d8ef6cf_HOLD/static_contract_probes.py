from pathlib import Path
import json,hashlib,copy,subprocess
R=Path('/home/test/zynq_fabricmap');D=Path(__file__).resolve().parent
P=R/'evidence/b4/unit_protocol_v2_tool_2026_10_20/owner_review_21db2de_PASS/float_return.json'
# Retained malformed-return evidence: inspect only its unchanged model CONFIG/HEADER fields, not its deliberately malformed q cell.
raw=json.loads(P.read_text())['quarantine']['raw'];cfg=raw['config']
old_hash=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
canonical_dict_hash=hashlib.sha256(json.dumps(cfg,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def order(a):
 f,w,b=a.split('/');return int(f,16),int(w),int(b)
vector=[cfg[a] for a in sorted(cfg,key=order)]
canonical_vector_hash=hashlib.sha256(json.dumps(vector,separators=(',',':')).encode()).hexdigest()
assert old_hash==raw['config_sha256'];assert canonical_vector_hash!=old_hash
C1={'source':str(P.relative_to(R)),'note':'legacy config/header only; no new model call','legacy_config_type':type(cfg).__name__,'legacy_config_entries':len(cfg),'legacy_stimulus_sha256_present':'stimulus_sha256' in raw,'legacy_fabric_kind':raw['fabric']['kind'],'recorded_config_sha256':raw['config_sha256'],'legacy_default_json_hash':old_hash,'canonical_dictionary_hash':canonical_dict_hash,'proposed_vector_hash':canonical_vector_hash,'model_would_hit_global_truth_string_deny_list':raw['fabric']['kind']=='truth'}
# Synthetic Boolean-cell records used solely to check the written A5 comparison rule.
# A reset clears the differing initial state perfectly, yet q_before is copied into step 0.
def record(before):
 return {'initial':{'q':[before]*8},'steps':[{'step':0,'kind':'init','prev_event':'none','clock_before':0,'clock_after':0,'edge':None,'ce':0,'sr':0,'d':0,'q_before':[before]*8,'q_after':[0]*8}],'cleanup':{'final_q':[0]*8}}
a,b=record(0),record(1)
def projection(r):return {'steps':r['steps'],'cleanup.final_q':r['cleanup']['final_q']}
assert a['initial']['q']!=b['initial']['q'];assert a['steps'][0]['q_after']==b['steps'][0]['q_after'];assert projection(a)!=projection(b)
C3={'injection_witness_differs':True,'post_init_samples_equal':True,'cleanup_samples_equal':True,'current_A5_projection_equal':False,'difference':'steps[0].q_before is a copy of excluded initial.q; no trace can satisfy both required initial difference and all-step-field equality'}
# Phase constraints as stated by sections 4.2 and 5.1, not an execution of a carrier.
C2={'observation_required_durable_phase':6,'required_field_earliest_phase':{'cleanup':7,'idle_status':10},'own_current_base_restoration_field_named_in_carrier_closed_set':False,'predecessor_describes':'previous transaction, not this transaction','normal_sign_precondition':'prior restoration and idle witnesses','A5_injection_path':'deliberately omits prior P7-P9 and holds nonzero inputs / clock 1'}
# An identical stimulus cannot choose a single D at one shared capture sample opposite to both SRVAL outcomes.
required={str(srval):[d for d in (0,1) if d!=srval] for srval in (0,1)}
intersection=set(required['0'])&set(required['1']);assert not intersection
states=[]
for init_effect in (False,True):
 for srval_effect in (False,True):
  rows=[]
  if init_effect and srval_effect:rows.append('both main effects')
  if srval_effect and not init_effect:rows.append('SRVAL only')
  if init_effect and not srval_effect:rows.append('INIT only')
  if not init_effect and not srval_effect:rows.append('neither')
  if init_effect!=srval_effect:rows.append('last row: a main effect absent where the other is present')
  states.append({'init_effect':init_effect,'srval_effect':srval_effect,'no_cross_tracking':True,'matching_rows':rows})
C4={'required_D_at_evidence_edge_by_SRVAL':required,'common_D_values':sorted(intersection),'outcome_table_overlap':states}
paths=['b4/','b3/','host/','tests/','firmware/','manifests/','gate_runs/','evidence/b3/','evidence/b4/sim/','evidence/b4/gonogo/','evidence/b4/gate/']
p=subprocess.run(['git','diff','--exit-code','e91650b','HEAD','--',*paths],cwd=R,text=True,capture_output=True);assert p.returncode==0
src=R/'build/wip/owner_review_e91650b_2026_10_21';dst=R/'evidence/b4/unit_2c_obs_2026_10_21/owner_review_e91650b_HOLD'
originals=[p for p in src.rglob('*') if p.is_file()];assert all((dst/p.relative_to(src)).read_bytes()==p.read_bytes() for p in originals)
checksums=(dst/'SHA256SUMS').read_text().splitlines()
for line in checksums:
 sha,name=line.split('  ',1);assert hashlib.sha256((dst/name).read_bytes()).hexdigest()==sha
for name in ['owner_authorisation_2026_10_21.txt','AUTHORISATION_SOURCE.txt']:
 assert (src/name).read_bytes()==(R/'evidence/b4/unit_2c_obs_2026_10_21'/name).read_bytes()
scripts_unchanged=subprocess.check_output(['git','diff','--name-only','e91650b','HEAD','--','evidence/b4/unit_2c_obs_2026_10_21/k9_address_record.py','evidence/b4/unit_2c_obs_2026_10_21/k9_address_record.txt','evidence/b4/unit_2c_obs_2026_10_21/positive_control_choice.py','evidence/b4/unit_2c_obs_2026_10_21/positive_control_choice.txt'],cwd=R,text=True)==''
assert scripts_unchanged
out={'C1':C1,'C2':C2,'C3':C3,'C4':C4,'protected_paths_unchanged':paths,'prior_review_copied_byte_identical':True,'prior_review_original_files':len(originals),'prior_checksum_entries':len(checksums),'authorisation_and_source_byte_identical':True,'readonly_scripts_and_outputs_unchanged':scripts_unchanged,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'status':subprocess.check_output(['git','status','--short','--branch'],cwd=R,text=True),'new_model_or_device_observations':False,'new_production_draws':False}
(D/'static_contract_probes.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
