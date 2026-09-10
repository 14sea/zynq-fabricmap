"""Offline review counterexamples; no production file or original report is changed."""
from pathlib import Path
import copy,json,sys,math,hashlib
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R/'host'))
import b3_online as b3,b2_gate as g,b2_maps as maps,b2_landscape as land,b1_model as bm
out={}
p,q,r,t,u=(0,0),(0,1),(0,2),(0,3),(0,4)
c=b3.SpecimenCarto();c.observe([0],[p]);c.observe([0],[q]);assert c.anomalies==0
out['decoded_contradiction']={'calls':[[[0],[p]],[[0],[q]]],'anomalies':c.anomalies,'decoded':str(c.decoded)}
c=b3.SpecimenCarto();c.observe([0],[p]);c.observe([0,1],[q,r]);assert c.anomalies==0
out['mixed_contradiction']={'calls':[[[0],[p]],[[0,1],[q,r]]],'anomalies':c.anomalies,'candidates':str(c.candidates)}
c=b3.SpecimenCarto();c.observe([0,2],[p,q]);c.observe([1,3],[r,t]);before=copy.deepcopy(c.candidates);c.observe([0,1],[p,u]);assert c.anomalies==1 and c.candidates!=before
out['partial_mutation_on_refusal']={'calls':[[[0,2],[p,q]],[[1,3],[r,t]],[[0,1],[p,u]]],'before':str(before),'after':str(c.candidates),'anomalies':1}
rows=json.loads((R/'evidence/b2/gate/raw_F3.json').read_text())['rows'];ix=g.GRID.index(300)
delta=[r['arms']['B']['at_grid'][ix]-r['arms']['A']['at_grid'][ix] for r in rows]
reported,power=g.required_pairs(delta,.05,.9,1000,1,8,200);smaller=g.bootstrap_reject_rate(delta,89,.05,1000,90)
assert reported==91 and smaller==.906
out['required_pairs']={'fitness':'F3','budget':300,'returned_N':reported,'power_at_89':smaller,'reported_cost':54600,'smaller_passing_cost':53400,'current_F1_selection_not_changed_by_this_counterexample':True}
sm=maps.load_self_map();train=land.train_vectors();known={e['genome_bit'] for e in sm['entries'] if e['relation']['init_index'] in train}
out['control_train_membership']={}
for name,doc in [('B',sm),('D',maps.shuffled_map(sm,0)),('E',maps.lut_shuffled_map(sm,0))]:
 v=maps.MapView(doc,train);selected={i for col in v.columns.values() for i in col}
 out['control_train_membership'][name]={'named_train':len(selected),'actually_train':len(selected&known),'actually_holdout':len(selected-known)}
truth=bm.truth_mapping();l=land.Landscape('F3',123,truth=truth);mod=list(l.target);k,v=truth['mapping'][13];assert v in l.holdout;mod[k]^=1<<v
assert l.train_fitness(l.target)==320 and l.train_fitness(mod)==256
out['F3_holdout_affects_train']={'landscape_seed':123,'genome_bit':13,'position':[k,v],'train_before':320,'train_after':256}
rows=json.loads((R/'evidence/b2/gate/raw_F1.json').read_text())['rows'];i=g.GRID.index(600);d=[r['arms']['B']['at_grid'][i]-r['arms']['A']['at_grid'][i] for r in rows]
pos=sum(x>0 for x in d)/len(d);neg=sum(x<0 for x in d)/len(d);tie=1-pos-neg
out['exact_empirical_sign_test_power']={}
for n in [8,9,10,11,12]:
 power=sum(math.comb(n,k)*(1-tie)**k*tie**(n-k)*sum(math.comb(k,j)*(pos/(pos+neg))**j*(neg/(pos+neg))**(k-j) for j in range(k+1) if sum(math.comb(k,x) for x in range(j,k+1))/2**k<=.05) for k in range(n+1))
 out['exact_empirical_sign_test_power'][n]=power
out['fixed_prediction_primary']={'deltas':[2,5,6,3,4,6,1,-2,5],'p':g.sign_test_p([2,5,6,3,4,6,1,-2,5])[0],'identical_predicted_fitnesses_cannot_change_primary':True}
Path('/tmp/b23_review/findings.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
