from pathlib import Path
import sys,subprocess,shutil,json,copy
C=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/owner_b4q_repair_3ogm8sq4')
O=Path(sys.argv[2]) if len(sys.argv)>2 else Path('/home/test/zynq_fabricmap/build/wip/owner_review_6f62b6a_2026_10_27')
O.mkdir(parents=True,exist_ok=True);sys.path[:0]=[str(C/'host'),str(C/'b4/host')]
import b4q_session as ss,b4q_e2e as ee,b4q_backend as bk,b4q_a7 as a7,b4q_qual as ql,b4q_view as vw,b4q_schema as sc,b4_ff_mapping as bm,b4_ff_hypothesis as hy,b4_ff_model as fm
W=C/'build/owner_review_probes';W.mkdir(exist_ok=True);E=C/'evidence/b4/unit_b4q_integration_2026_10_27/e2e';out={}
def fresh(name,scenario,edit):
 d=W/name;shutil.copytree(E/scenario,d,dirs_exist_ok=True);edit(d)
 p=subprocess.run([sys.executable,'-B',str(C/'host/b4q_verify.py'),str(d),'--json',str(d/'owner_verify.json')],capture_output=True,text=True)
 j=json.loads((d/'owner_verify.json').read_bytes()) if (d/'owner_verify.json').exists() else {}
 out[name]={'exit':p.returncode,'clean':j.get('clean'),'agree':j.get('agree'),'refused':j.get('refused'),'session':j.get('session'),'qualification':j.get('qualification'),'traceback':'Traceback' in p.stderr,'stdout':p.stdout,'stderr':p.stderr}
def jread(p):return json.loads(p.read_bytes())
def jwrite(p,j):p.write_text(json.dumps(j,indent=1)+'\n')
def pcgap(d):
 m=jread(d/'manifest.json');r=m['records'][1];r['pcap_range'][0]+=1
 rj=jread(d/r['dir']/'record.json');rj['pcap_range']=r['pcap_range']
 jwrite(d/'manifest.json',m);jwrite(d/r['dir']/'record.json',rj)
def a8label(d):
 m=jread(d/'manifest.json');e=m['qualification_plan']['a8'][0];e['elements']['A5FF']=e['elements'].pop('AFF')
 q=jread(d/'a8_cross.json');q['A5FF']=q.pop('AFF')
 jwrite(d/'manifest.json',m);jwrite(d/'a8_cross.json',q)
def a8bits(d):
 m=jread(d/'manifest.json');e=m['qualification_plan']['a8'][0];e['background_hex']='000000';e['bits']={'ff_init':0,'ff_srval':1};jwrite(d/'manifest.json',m)
def a8samples(d):
 q=jread(d/'a8_cross.json');q['AFF']['init_samples']['00']=1-q['AFF']['init_samples']['00'];q['AFF']['quantities']['init_effect']=False;jwrite(d/'a8_cross.json',q)
def a2label(d):
 m=jread(d/'manifest.json');m['qualification_plan']['a2'][0]['semantic']='ff_init'
 q=jread(d/'a2_rows.json');q['ff_init']=q.pop('ce_mode');jwrite(d/'manifest.json',m);jwrite(d/'a2_rows.json',q)
def drop(d):shutil.rmtree(d/'tx_004')
def a5pass(d):
 q=jread(d/'a5_verdict.json');q['verdict']='pass';jwrite(d/'a5_verdict.json',q)
def a8pass(d):
 q=jread(d/'a8_cross.json');q['AFF']['row']=5;q['AFF']['verdict']='neither demonstrated';jwrite(d/'a8_cross.json',q)
fresh('baseline','valid',lambda d:None)
fresh('old_drop_final_tx','valid',drop)
fresh('old_change_A5_verdict','a5_persist',a5pass)
fresh('old_change_A8_verdict','a8_cross',a8pass)
fresh('pcap_internal_gap','valid',pcgap)
fresh('A8_element_label','a8_cross',a8label)
fresh('A8_background_bits','a8_cross',a8bits)
fresh('A8_partial_conclusion_binding','a8_cross',a8samples)
fresh('A2_semantic_label','a2_pairs',a2label)
for name,rel,val in [('manifest_list','manifest.json',[]),('record_list','tx_001/record.json',[]),('ctx_list','tx_001/ctx.json',[]),('nested_binary_missing','manifest.json',None)]:
 def change(d,rel=rel,val=val):
  if val is None:
   q=jread(d/rel);q['executing_side']={};jwrite(d/rel,q)
  else:jwrite(d/rel,val)
 fresh(name,'valid',change)

# Adversarial read SLVERRs run through the actual firmware and host HAL.
for name,offset in [('nonce_read_slverr',ss.rm.NONCE_LO),('heartbeat_read_slverr',ss.rm.HEARTBEAT)]:
 s=ss.Session(W/name,label='owner-'+name);s.start();fired=[]
 try:
  s.open();orig=s.backend.rd32
  def read(a,orig=orig,offset=offset):
   v,resp,x=orig(a)
   if not fired and a==bk.AXI_BASE+offset:
    fired.append(a);s.backend.accesses[-1]=('rd',a,bk.SLVERR);return v,bk.SLVERR,x
   return v,resp,x
  s.backend.rd32=read
  r=s.transaction('root',0,ee.stim([]))
  ops=[e for e in s.backend.trace if e.get('op')=='wr' and e.get('addr')==ss.rm.CTRL]
  out[name]={'injected':len(fired),'signatures':len(s.notary.log),'firmware_status':r['firmware']['status'],'reason':r['firmware']['reason'],'ctrl_words':[e['data'] for e in ops],'init_req_word':ss.rm.ctrl_word('init_req'),'arm_word':ss.rm.ctrl_word('arm'),'findings':r['findings']}
 finally:s.stop()

# Prior R4/R5 and missing-X boundaries now refuse, without any new production draw.
base={'pcap':'submit','n':0,'kind':'env','src':bk.WR_BUF|1,'dst':bk.PCAP_ENDPOINT,'src_len':bk.fr.STREAM_WORDS,'dst_len':0}
out['A7']={name:a7.check([],[{**base,**change}])['findings'] for name,change in [('valid',{}),('alien_source',{'src':0xdead0001}),('missing_hold_tag',{'src':bk.WR_BUF}),('unaligned_offset',{'src':bk.WR_BUF|3})]}
m=bm.site_mapping();fab=fm.Fabric(m,hy.load());t=fab.observe(fab.config_from_genome(0x18),[fm.init()]);src={k:t[k] for k in ['hypothesis','mapping','fabric']}
out['raw_config']={}
for name,value in [('float',.25),('bool',True),('out_of_range',2)]:
 b=copy.deepcopy(t);b['config'][m.addresses[0]]=value;b['config_sha256']=vw.sha256_default(b['config'])
 try:v=vw.view(b,{'representation':'M-raw','source':src,'addresses':m.addresses});answer='accepted'
 except vw.ViewRefusal as e:answer=str(e)
 out['raw_config'][name]={'schema_findings':sc.validate_named(b,'ff_observation_model_raw_v1'),'adapter':answer}
A=E/'a5';o=lambda n:jread(A/n)
out['A5_missing_X']=ql.a5_verdict(o('tx_002/o.json'),o('tx_003/o.json'),o('tx_004/o.json'))
(O/'probes.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
