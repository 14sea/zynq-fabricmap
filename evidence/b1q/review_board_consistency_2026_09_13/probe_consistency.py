"""Offline CLI probes; use the submitted fake-board adapter, never a real serial port."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'host')]
from test_board_transport_soak import TheConsistencyControl
import board_transport_soak as s
out={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
     'tool_sha256':s.self_sha256(),'cases':{}}
for name in ['positive','reference_export','sync_export','read_export','leading_newline',
             'injected_command_in_body','reset_with_prompt','partial_detach','exposure_cutoff']:
 t=TheConsistencyControl();t.setUp()
 try:
  kw={};extra=[]
  if name=='reference_export':kw['fault_export']=('reference.bin',)
  if name=='sync_export':kw['fault_export']=('sync.bin',)
  if name=='read_export':kw['fault_export']=('read_0000.bin',)
  if name=='leading_newline':kw['module']=t.module(mutate=lambda i,r: b'\r\n'+r if i==1 else r)
  if name=='injected_command_in_body':
   command=f'md.l {t.ADDR:#010x} {len(t.WORDS):#x}'.encode()
   kw['module']=t.module(mutate=lambda i,r:r.replace(b'................',command+b'................') if i==1 else r)
  if name=='reset_with_prompt':kw['module']=t.module(mutate=lambda i,r:b'\r\nU-Boot 2026.04 (synthetic reset)\r\nZynq> ' if i==1 else r)
  if name=='partial_detach':kw['module']=t.module(detach_at=1)
  if name=='exposure_cutoff':kw['module']=t.module(silent_from=1);extra=['--seconds','0.12']
  code,brief=t.run_cli(*extra,**kw)
  disk=json.loads((t.d/'control.json').read_text())
  r={'exit':code,'brief':brief,'commands':t.boards[0].commands,
     'files':sorted(p.name for p in t.d.iterdir()),
     'disk':{k:disk.get(k) for k in ['reads_done','mismatched_responses','identical_responses',
                'mismatches_per_100_responses','all_observed_responses_differ','terminal','reads']},
     'entry_equals_stdout':json.loads((t.d/'entry.json').read_text())==brief}
  out['cases'][name]=r
 finally:t.doCleanups()
c=out['cases']
assert c['positive']['brief']['identical_responses']==4
for name in ['reference_export','sync_export','read_export']:
 assert c[name]['exit']==0 and len(c[name]['commands'])==5 and c[name]['brief']['export_complete'] is False
for name in ['leading_newline','injected_command_in_body']:
 assert c[name]['brief']['mismatched_responses']==0 and c[name]['brief']['identical_responses']==4
assert c['reset_with_prompt']['exit']==0 and c['reset_with_prompt']['brief']['terminal']=='exposure_repetitions'
for name in ['partial_detach','exposure_cutoff']:
 assert c[name]['brief']['mismatches_per_100_responses']==0.0
 assert c[name]['brief']['all_observed_responses_differ'] is True
 assert c[name]['brief']['identical_responses']==0
print(json.dumps(out,indent=2,sort_keys=True))
