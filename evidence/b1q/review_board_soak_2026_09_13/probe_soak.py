"""Offline review: production soak CLI, fake U-Boot and a virtual clock. No port opened."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'host'),str(ROOT/'tests')]
import board_transport_soak as s
from test_board_transport_soak import md_reply
WORDS=[0xA5A5A5A5,0x5A5A5A5A,0xDEADBEEF,0xCAFEF00D]
IDENT={'usb':{'idVendor':'1a86','idProduct':'7523'}}
class Port:
    name='/dev/FAKE'
    def __init__(self,mode):
        self.mode,self.pending,self.now,self.index,self.closed=mode,bytearray(),0.0,-1,0
        self.writes=[];self.partial_sent=False
    def fileno(self): return -1
    def close(self): self.closed+=1
    def write(self,data,timeout=None):
        self.writes.append(data.decode())
        if data==b'\r': self.pending+=b'Zynq> '
        else:
            self.index+=1
            addr=int(data.split()[1],16)
            reply=md_reply(addr,WORDS)
            if self.mode=='ascii_delete' and self.index>=1: reply=reply.replace(b'................',b'...............')
            if self.mode=='extra_hex' and self.index>=1: reply=reply.replace(b'cafef00d',b'cafef00d0')
            if self.mode=='repeated_wrong': reply=reply.replace(b'a5a5a5a5',b'a5a5a5a4')
            if self.mode=='timeout' and self.index>=1: reply=b''
            self.pending+=reply
        return len(data)
    def read(self,timeout):
        self.now+=timeout
        if self.mode=='partial_detach' and self.index==1:
            if self.partial_sent: raise OSError('synthetic detach after partial md output')
            self.partial_sent=True
            b=bytes(self.pending[:20]); del self.pending[:20]; return b
        b=bytes(self.pending); self.pending.clear(); return b

orig_ub=s.UBoot
out={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
     'actual_soak_sha256':hashlib.sha256((ROOT/'host/board_transport_soak.py').read_bytes()).hexdigest(),
     'actual_rig_sha256':hashlib.sha256((ROOT/'host/transport_rig.py').read_bytes()).hexdigest(),'cases':{}}
with tempfile.TemporaryDirectory(prefix='board_soak_review_') as tmp:
 for mode in ['positive','ascii_delete','extra_hex','repeated_wrong','partial_detach','provenance_failure',
              'baseline_export_failure','entry_export_failure','timeout','non_ddr_address']:
    p=Port(mode); d=Path(tmp)/mode; stdout=io.StringIO(); calls=[]; counters=[]
    def opener(*a,**kw): calls.append(a); return p
    def counter(fd): counters.append(fd); return {'available':False,'reason':'fake fd'}
    original_write=s._write_evidence
    def export(path,data):
        if (mode=='baseline_export_failure' and path.name=='baseline.bin') or (mode=='entry_export_failure' and path.name=='entry.json'):
            raise OSError('synthetic '+path.name+' write failure')
        return original_write(path,data)
    argv=['--device','/dev/FAKE','--out',str(d),'--label','offline-review','--words','4','--repetitions','2']
    if mode=='timeout': argv+=['--seconds','0.01']
    if mode=='non_ddr_address': argv+=['--addr','0x40000000']
    with contextlib.ExitStack() as st:
        st.enter_context(patch.object(s,'serial_port',side_effect=opener))
        st.enter_context(patch.object(s,'device_identity',return_value=IDENT))
        st.enter_context(patch.object(s,'_counters',side_effect=counter))
        st.enter_context(patch.object(s.time,'monotonic',side_effect=lambda:p.now))
        st.enter_context(patch.object(s,'UBoot',side_effect=lambda port:orig_ub(port,clock=lambda:p.now)))
        st.enter_context(patch.object(s,'_write_evidence',side_effect=export))
        if mode=='provenance_failure': st.enter_context(patch.object(s,'provenance',side_effect=OSError('synthetic provenance failure')))
        st.enter_context(contextlib.redirect_stdout(stdout))
        try: r={'exit':s.main(argv)}
        except Exception as exc: r={'escaped_exception':f'{type(exc).__name__}: {exc}'}
    r.update(opens=len(calls),writes=p.writes,closed=p.closed,counter_attempts=len(counters),
             fake_elapsed=p.now,files=sorted(x.name for x in d.iterdir()),partial_bytes_observed=20 if p.partial_sent else 0)
    if stdout.getvalue(): r['brief']=json.loads(stdout.getvalue())
    for filename in ['invocation.json','soak.json']:
        if (d/filename).exists():
            x=json.loads((d/filename).read_text())
            r[filename]={k:x.get(k) for k in ['tool_sha256','damaged_reads','damaged_per_100k_bytes','provenance'] if k in x}
    out['cases'][mode]=r
c=out['cases']
assert c['positive']['exit']==0 and c['positive']['brief']['damaged_reads']==0
assert c['ascii_delete']['brief']['damaged_reads']==0
assert c['extra_hex']['brief']['damaged_reads']==0
assert c['repeated_wrong']['brief']['damaged_reads']==0
assert 'escaped_exception' in c['partial_detach'] and 'soak.json' not in c['partial_detach']['files']
assert c['provenance_failure']['opens']==1 and c['provenance_failure']['exit']==0
assert c['baseline_export_failure']['exit']==0 and len(c['baseline_export_failure']['writes'])==4
assert c['entry_export_failure']['brief']['export_complete'] is True
assert c['timeout']['fake_elapsed']>3 and c['timeout']['brief']['terminal']=='board_disruption'
assert 'md.l 0x40000000 0x4\r' in c['non_ddr_address']['writes']
assert c['positive']['soak.json']['tool_sha256']==out['actual_rig_sha256']!=out['actual_soak_sha256']
print(json.dumps(out,indent=2,sort_keys=True))
