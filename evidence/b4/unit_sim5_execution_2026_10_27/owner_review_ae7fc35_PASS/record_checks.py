from pathlib import Path
import hashlib,json
R=Path('/home/test/zynq_fabricmap'); O=R/'build/wip/owner_review_ae7fc35_2026_10_27'
names=['b4-sim-3_20261019T121833Z','b4-gate-1_20261020T102526Z','b4-sim-4_20261021T065339Z']
expected=[(10,12,10,-.21875),(56,95,49,-.49),(7,13,12,-1.71875)]
out=[]
for n,want in zip(names,expected):
 p=R/'evidence/b4/sim'/n/'sim_report.json'; r=json.loads(p.read_bytes()); s=r['summary']; d=s['per_budget']['64']['deltas']['Omega_minus_R']
 assert (d['positives'],d['negatives'],d['ties'],d['mean'])==want
 k9=s['k9']; meds=lambda field:{k:v['median_coverage_over_all_S'] for k,v in k9[field].items()}
 out.append({'archive':n,'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'recorded_count':r['count'],
 'recorded_deadline':r['deadline'],'Omega_minus_R_B64':d,'K9':meds('per_semantic'),
 'K9_all_panel':meds('per_semantic_all_panel') if 'per_semantic_all_panel' in k9 else None,
 'B_star':s['candidate_B_star']})
assert out[0]['K9']['ff_srval']==.4270833333333333
assert out[1]['K9']['sr_mode']==.96875
assert out[2]['K9']['ff_srval']==.8125 and out[2]['K9']['sr_kind']==.875
assert out[2]['K9_all_panel']['ff_srval']==.40625 and out[2]['K9_all_panel']['sr_kind']==.4375
(O/'record_checks.json').write_text(json.dumps(out,indent=2)+'\n')
print('Three existing summaries read; B64 Omega-R counts/means and K9 references match. No replay, new observation, seed read/draw or pooled new test.')
