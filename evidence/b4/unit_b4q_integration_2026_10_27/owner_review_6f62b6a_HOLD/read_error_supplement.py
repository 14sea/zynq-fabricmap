from pathlib import Path
import sys,json
C=Path('/tmp/owner_b4q_repair_3ogm8sq4');O=Path('/home/test/zynq_fabricmap/build/wip/owner_review_6f62b6a_2026_10_27')
sys.path[:0]=[str(C/'host'),str(C/'b4/host')]
import b4q_session as ss,b4q_backend as bk,b4q_e2e as ee
s=ss.Session(C/'build/owner_review_probes/devc_read_slverr',label='owner-devc-read');s.start();fired=[]
try:
 s.open();orig=s.backend.rd32
 def read(a):
  v,resp,x=orig(a)
  if not fired and a==bk.DEVCFG_CTRL:
   fired.append(a);s.backend.accesses[-1]=('rd',a,bk.SLVERR);return v,bk.SLVERR,x
  return v,resp,x
 s.backend.rd32=read
 r=s.transaction('root',0,ee.stim([]))
 out={'injections':len(fired),'firmware_status':r['firmware']['status'],'reason':r['firmware']['reason'],'X_status':r['x']['status'] if r['x'] else None,'notary_signatures':len(s.notary.log),'findings':r['findings']}
finally:s.stop()
(O/'read_error_supplement.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
