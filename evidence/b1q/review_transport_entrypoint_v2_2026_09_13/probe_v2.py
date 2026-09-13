"""Offline second review: production CLI, fake ports only; no prior evidence modified."""
import contextlib
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
old=ROOT/'evidence/b1q/review_transport_entrypoint_2026_09_13/probe_entrypoint.py'
ns={'__file__':str(old)}
exec(compile(old.read_text().split("results = {'head':",1)[0],str(old),'exec'),ns)
rig, FakePort, invoke=ns['rig'],ns['FakePort'],ns['invoke']
FakePort.close=lambda self: None
result={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'tool_sha256':hashlib.sha256((ROOT/'host/transport_rig.py').read_bytes()).hexdigest()}
with tempfile.TemporaryDirectory(prefix='rig_v2_review_') as tmp:
    base=Path(tmp)
    for name,mode in [('positive','loop'),('silence','silence'),('continuous','continuous'),('detach','detach')]:
        d=base/name; d.mkdir()
        x=invoke(d,FakePort(mode)); x['brief']=json.loads(x.pop('stdout'))
        if (d/'preflight.json').exists():
            pre=json.loads((d/'preflight.json').read_text())
            x['raw_matches_record']=hashlib.sha256((d/'preflight_rx.bin').read_bytes()).hexdigest()==pre['received_sha256']
        result[name]=x
    d=base/'old';d.mkdir();(d/'capture_000.bin').write_bytes(b'old')
    result['old_destination']=invoke(d,FakePort())
    assert (d/'capture_000.bin').read_bytes()==b'old'
    for name in ['provenance_failure','close_failure']:
        d=base/name;d.mkdir();port=FakePort()
        def fail_close(): raise OSError('synthetic close failure')
        if name=='close_failure': port.close=fail_close
        with (patch.object(rig,'provenance',side_effect=OSError('synthetic provenance read failure'))
              if name=='provenance_failure' else contextlib.nullcontext()):
            x=invoke(d,port)
        x['brief']=json.loads(x.pop('stdout'))
        x['invocation_provenance']=json.loads((d/'invocation.json').read_text()).get('provenance')
        disk=json.loads((d/'run.json').read_text())
        x['disk_provenance']=disk.get('provenance')
        x['disk_error']=disk.get('error')
        x['disk_secondary_errors']=disk.get('secondary_errors')
        result[name]=x
assert result['positive']['exit']==0 and result['positive']['raw_matches_record']
assert result['silence']['exit']==3 and result['silence']['counter_calls']==2
assert result['continuous']['exit']==3 and result['continuous']['fake_elapsed']==3.0
assert result['continuous']['brief']['refusal']=='not_quiet'
assert result['detach']['exit']==2 and result['detach']['counter_calls']==2 and result['detach']['raw_matches_record']
assert result['old_destination']['exit']==5 and result['old_destination']['writes']==0
assert result['provenance_failure']['exit']==0 and result['provenance_failure']['writes']==303
assert result['provenance_failure']['invocation_provenance'] is None
assert result['close_failure']['exit']==0 and result['close_failure']['brief']['ports_closed']==['/dev/FAKE']
print(json.dumps(result,indent=2,sort_keys=True))
