"""Independent offline CLI acceptance; no real ports and no existing captures touched."""
import contextlib
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
p=ROOT/'evidence/b1q/review_transport_entrypoint_2026_09_13/probe_entrypoint.py'
ns={'__file__':str(p)}
exec(compile(p.read_text().split("results = {'head':",1)[0],str(p),'exec'),ns)
rig,FakePort,invoke=ns['rig'],ns['FakePort'],ns['invoke']
FakePort.close=lambda self: None
result={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'tool_sha256':hashlib.sha256((ROOT/'host/transport_rig.py').read_bytes()).hexdigest(),
        'scope':'offline entry-point acceptance; not a physical transport verdict', 'cases':{}}
with tempfile.TemporaryDirectory(prefix='rig_entry_accept_') as temp:
    base=Path(temp)
    for name,mode in [('positive','loop'),('silence','silence'),('continuous','continuous'),('detach','detach'),
                      ('provenance_failure','loop'),('close_failure','loop'),('entry_export_failure','loop'),
                      ('destination_refusal','loop'),('wrong_expected_usb','loop')]:
        d=base/name;d.mkdir();port=FakePort(mode)
        if name=='destination_refusal': (d/'capture_000.bin').write_bytes(b'old immutable bytes')
        def close_fail(): raise OSError('synthetic close failure')
        if name=='close_failure': port.close=close_fail
        original_write=rig._write_evidence
        def write(path,data):
            if path.name=='entry.json': raise OSError('synthetic entry export failure')
            return original_write(path,data)
        with contextlib.ExitStack() as stack:
            if name=='provenance_failure':
                stack.enter_context(patch.object(rig,'provenance',side_effect=OSError('synthetic provenance failure')))
            if name=='entry_export_failure': stack.enter_context(patch.object(rig,'_write_evidence',side_effect=write))
            if name=='wrong_expected_usb':
                r=invoke(d,port,extra=('--expect-usb','0403:6001'))
            else: r=invoke(d,port)
        brief=json.loads(r.pop('stdout'))
        entry=json.loads((d/'entry.json').read_text()) if (d/'entry.json').exists() else None
        r['brief']=brief
        r['entry_equals_stdout']=entry==brief if entry is not None else None
        if name not in ('destination_refusal','entry_export_failure'): assert entry==brief,name
        if name=='positive': assert r['exit']==0 and r['run']['frames_accepted']==302 and r['run']['losses']==0
        if name=='silence': assert r['exit']==3 and r['writes']==1 and r['counter_calls']==2
        if name=='continuous': assert r['exit']==3 and r['fake_elapsed']==3 and brief['refusal']=='not_quiet'
        if name=='detach':
            pre=json.loads((d/'preflight.json').read_text()); raw=(d/'preflight_rx.bin').read_bytes()
            assert r['exit']==2 and r['counter_calls']==2 and raw==pre['nonce'].encode()
            assert hashlib.sha256(raw).hexdigest()==pre['received_sha256']
        if name=='provenance_failure':
            assert r['exit']==2 and r['writes']==0 and brief['ports_opened']==[] and 'run.json' not in r['files']
            inv=json.loads((d/'invocation.json').read_text())
            assert inv['provenance'] is None and inv['construction_errors']
        if name=='close_failure':
            assert brief['ports_closed']==[] and brief['close_attempted']==['/dev/FAKE'] and brief['close_errors']
            assert r['run']['frames_accepted']==302 and r['run']['losses']==0
        if name=='entry_export_failure':
            assert brief['entry_record'] is None and brief['export_complete'] is False
            assert brief['entry_export_errors'] and r['run']['losses']==0
        if name=='destination_refusal':
            assert r['exit']==5 and r['writes']==0 and brief['ports_opened']==[]
            assert list(d.iterdir())==[d/'capture_000.bin'] and (d/'capture_000.bin').read_bytes()==b'old immutable bytes'
        if name=='wrong_expected_usb': assert r['exit']==3 and r['writes']==0 and brief['ports_opened']==[]
        result['cases'][name]=r
result['acceptance']='PASS'
print(json.dumps(result,indent=2,sort_keys=True))
