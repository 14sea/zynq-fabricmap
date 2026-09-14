"""Read-only native acquisition audit: regenerate traffic, validate captures and deletion shape.
No remote connections or serial devices. Writes only JSON to stdout.
"""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'host'))
import transport_rig as rig
BASE=ROOT/'evidence/b1q/transport_native_orangepi_2026_09_14'
def digest(b): return hashlib.sha256(b).hexdigest()
def definitions(ref):
 src=subprocess.check_output(['git','show',f'{ref}:host/transport_rig.py'],cwd=ROOT,text=True)
 return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(src).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
a,b=definitions('819117c'),definitions('c2f38ab')
core=['Frame','token_for','plan_frames','host_frame','host_schedule','Driver','analyse','Run']
assert all(a[k]==b[k] for k in core)
report={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'scope':'local archived bytes and generator/driver consistency; host topology and wiring remain operator-reported',
        'unchanged_core_between_wsl_and_native_tools':core,'runs':[],'deletions':[]}
for d in sorted(p for p in BASE.iterdir() if p.is_dir()):
 run=json.loads((d/'run.json').read_text());inv=json.loads((d/'invocation.json').read_text());entry=json.loads((d/'entry.json').read_text())
 assert inv['provenance']['tool_sha256']==digest((ROOT/'host/transport_rig.py').read_bytes())
 assert inv['provenance']['framing_sha256']==digest(Path(rig.l5.__file__).read_bytes())
 assert inv['identity_check']['matched'] is True
 pre=json.loads((d/'preflight.json').read_text());pre_raw=(d/'preflight_rx.bin').read_bytes()
 assert pre['matched'] and pre['received_sha256']==digest(pre_raw) and pre['nonce'].encode()==pre_raw
 received_total=accepted_total=delivered_total=echo_total=loss_total=0
 for cap in run['captures']:
  i=cap['repetition'];raw=(d/cap['capture']).read_bytes();events=json.loads((d/cap['events']).read_text())
  assert len(raw)==cap['bytes'] and digest(raw)==cap['sha256']
  assert sum(e['bytes'] for e in events if e['op']=='read')==len(raw)
  frames=rig.plan_frames(run['run_id'],i)
  writes=[e for e in events if e['op']=='write_frame']
  assert [e['index'] for e in writes]==list(range(len(writes)))
  for e,f in zip(writes,frames): assert e['bytes']==len(f.line) and e['kind']==f.kind
  host_events=[e for e in events if e['op']=='write_host']
  schedule=rig.host_schedule(frames) if inv['tx_during_rx'] else []
  assert len(schedule)==len(host_events)
  for e,s in zip(host_events,schedule): assert e['bytes']==len(s['line']) and e['caused_by']==s['caused_by']
  echo=Counter(s['line'] for s in schedule);source=[]
  for line in raw.splitlines(keepends=True):
   if echo[line]:echo[line]-=1;echo_total+=1
   else:source.append(line)
  assert not +echo,'unmatched host echo'
  assert len(source)==len(writes)
  losses=0
  for j,(got,f) in enumerate(zip(source,frames)):
   if got==f.line: delivered_total+=1;continue
   losses+=1;loss_total+=1
   missing=len(f.line)-len(got)
   assert missing>0
   first=next((k for k,(x,y) in enumerate(zip(got,f.line)) if x!=y),len(got))
   assert f.line[:first]+f.line[first+missing:]==got,'not a single contiguous deletion'
   assert j+1<len(source) and source[j+1]==frames[j+1].line
   report['deletions'].append({'run':d.name,'repetition':i,'frame_index':f.index,'kind':f.kind,
                             'expected_bytes':len(f.line),'received_bytes':len(got),'deleted_bytes':missing,
                             'first_difference':first,'deleted_ascii':f.line[first:first+missing].decode(),
                             'next_frame_byte_exact':True})
  rec=run['repetition_results'][i]
  assert losses==rec['confirmed_losses']
  assert rec['frames_accepted']==len(writes) and rec['frames_delivered']==len(writes)-losses
  assert rec['host_echo_lines']==len(host_events)
  received_total+=len(raw);accepted_total+=len(writes)
 assert (received_total,accepted_total,delivered_total,loss_total)==(run['denominator_bytes'],run['frames_accepted'],run['frames_accepted']-run['confirmed_losses'],run['confirmed_losses'])
 assert run['losses']==loss_total and run['loss_metric']['status']=='exact'
 assert run['censored_in_flight']==run['unresolved_at_cutoff']==0
 assert run['export_complete'] and entry['export_complete'] and not entry['entry_export_errors'] and not entry['close_errors']
 for k in ('confirmed_losses','frames_accepted','denominator_bytes','losses'):assert entry[k]==run[k]
 report['runs'].append({'directory':d.name,'captures':len(run['captures']),'accepted':accepted_total,'delivered':delivered_total,
                       'received_bytes':received_total,'confirmed_losses':loss_total,'host_echoes':echo_total,
                       'run_sha256':digest((d/'run.json').read_bytes()),'terminal':run['terminal']['reason']})
assert len(report['deletions'])==5
report['result']='PASS archive consistency'
print(json.dumps(report,indent=2,sort_keys=True))
