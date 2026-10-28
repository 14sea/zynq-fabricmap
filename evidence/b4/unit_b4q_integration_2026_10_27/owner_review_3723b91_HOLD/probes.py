from pathlib import Path
import sys,json,shutil,copy,subprocess
C=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/owner_b4q_7w3a_pwh')
O=Path(sys.argv[2]) if len(sys.argv)>2 else Path('/home/test/zynq_fabricmap/build/wip/owner_review_3723b91_2026_10_27')
O.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(C/'host'),str(C/'b4/host')]
import b4q_session as ss,b4q_backend as bk,b4q_e2e as ee,b4q_verify as vv,b4q_a7 as a7,b4q_view as vw,b4q_schema as sc,b4_ff_mapping as bm,b4_ff_hypothesis as hy,b4_ff_model as fm
work=C/'build/owner_probes';work.mkdir(exist_ok=True);out={}

def corruption(phase,ordinal):
 s=ss.Session(work/('corrupt_'+phase),label='owner-'+phase);s.start()
 orig=s.backend.devc.data
 def inject(d):
  before=d['data_done'];orig(d)
  if not before and d['kind']=='frame' and d['ordinal']==ordinal:
   addr=(d['dst']&~3)+4*bk.fr.FRAME_WORDS
   s.backend.mem.wr(addr,s.backend.mem.rd(addr)^1)
 s.backend.devc.data=inject
 try:
  opening=s.open()
  root=s.transaction('root',0,ee.stim([]))
  out[phase]={'open_status':opening['record']['status'],'open_findings':opening['findings'],
   'firmware_status':root['firmware']['status'],'firmware_phase':root['firmware']['phase'],
   'mismatch':root['firmware'].get('pre_event')!=root['firmware'].get('commit') if phase=='pre_event' else None,
   'root_X':root['x']['status'] if root['x'] else None,'root_findings':root['findings'],'notary_signatures':len(s.notary.log)}
  if phase=='pre_event':
   after=s.transaction('normal',ee.G_CESR,ee.stim(ee.FIX1))
   out[phase]['next_transaction_firmware_status']=after['firmware']['status']
   out[phase]['next_transaction_signed']=len(s.notary.log)
 finally:s.stop()
for phase,ordinal in [('startup',1),('pre_event',9),('post_event',17),('base_readback',25)]:corruption(phase,ordinal)

# A returned SLVERR on STEP_IN must not lead to the STEP launch with the old register value.
s=ss.Session(work/'slverr',label='owner-slverr');s.start();orig=s.backend.wr32
try:
 s.open();s.transaction('root',0,ee.stim([]));seen=[]
 def refuse_step(a,v):
  if a==bk.AXI_BASE+ss.rm.STEP_IN:
   seen.append((a,v));s.backend.accesses.append(('wr',a,bk.SLVERR));return bk.SLVERR
  return orig(a,v)
 s.backend.wr32=refuse_step
 r=s.transaction('normal',0,ee.stim(ee.FIX0[:1]))
 out['STEP_IN_SLVERR']={'refused_writes':len(seen),'firmware_status':r['firmware']['status'],'firmware_phase':r['firmware']['phase'],'findings':r['findings']}
finally:s.stop()

# Fresh verifier: extra unindexed suffix and altered qualification conclusions.
E=C/'evidence/b4/unit_b4q_integration_2026_10_27/e2e'
for name,scenario,edit in [('baseline_valid','valid','none'),('dropped_final_tx','valid','drop'),('altered_A8_conclusion','a8_cross','a8'),('altered_A5_conclusion','a5_persist','a5'),('altered_A2_conclusion','a2_pairs','a2')]:
 d=work/name;shutil.copytree(E/scenario,d,dirs_exist_ok=True)
 if edit=='drop':shutil.rmtree(d/'tx_004')
 elif edit=='a8':
  p=d/'a8_cross.json';v=json.loads(p.read_bytes());v['AFF']['row']=5;v['AFF']['verdict']='neither demonstrated';p.write_text(json.dumps(v))
 elif edit=='a5':
  p=d/'a5_verdict.json';v=json.loads(p.read_bytes());v['verdict']='pass';p.write_text(json.dumps(v))
 elif edit=='a2':
  p=d/'a2_rows.json';v=json.loads(p.read_bytes());v['ce_mode']['verdict']='does_not_differ';p.write_text(json.dumps(v))
 p=subprocess.run([sys.executable,'-B',str(C/'host/b4q_verify.py'),str(d),'--json',str(d/'owner_verify.json')],capture_output=True,text=True)
 vr=json.loads((d/'owner_verify.json').read_bytes()) if (d/'owner_verify.json').exists() else None
 out[name]={'exit':p.returncode,'clean':vr.get('clean') if vr else None,'agree':vr.get('agree') if vr else None,'transactions':len(vr['transactions']) if vr else None,'session':vr.get('session') if vr else None,'stdout':p.stdout,'stderr':p.stderr}

# A7 must bind both addresses, the hold tag and lengths, independent of the log's kind label.
base={'pcap':'submit','n':0,'kind':'env','src':bk.WR_BUF|1,'dst':bk.PCAP_ENDPOINT,'src_len':bk.fr.STREAM_WORDS,'dst_len':0}
a7cases={}
for name,change in [('valid',{}),('alien_source',{'src':0xdead0001}),('missing_hold_tag',{'src':bk.WR_BUF}),('unaligned_offset',{'src':bk.WR_BUF|3})]:
 a7cases[name]=a7.check([], [{**base,**change}])['findings']
out['A7_tuple_checks']=a7cases

# Malformed raw config is converted into a legal-looking vector before validating its raw schema.
m=bm.site_mapping();fab=fm.Fabric(m,hy.load());trace=fab.observe(fab.config_from_genome(0x18),[fm.init()])
src={k:trace[k] for k in ['hypothesis','mapping','fabric']};bad=copy.deepcopy(trace);a=m.addresses[0];bad['config'][a]=0.25;bad['config_sha256']=vw.sha256_default(bad['config'])
raw_f=sc.validate_named(bad,'ff_observation_model_raw_v1')
try:
 v=vw.view(bad,{'representation':'M-raw','source':src,'addresses':m.addresses});view_f=sc.validate_named(v,'ff_observation_view_v1')
 out['raw_float_config']={'raw_findings':raw_f,'adapter_accepted':True,'view_findings':view_f,'converted_config_bit':v['config_vector']['value'][0]}
except Exception as e:out['raw_float_config']={'raw_findings':raw_f,'adapter_accepted':False,'exception':str(e)}

# Optional close witnesses cannot justify an A5 pass.
A=E/'a5';rd=lambda n:json.loads((A/n).read_bytes())
import b4q_qual as ql
out['A5_without_close_witnesses']=ql.a5_verdict(rd('tx_002/o.json'),rd('tx_003/o.json'),rd('tx_004/o.json'))
(O/'probes.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
