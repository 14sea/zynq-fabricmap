"""Owner's focused coordinated archive negatives. All copies/verification are host-only."""
import json,sys,shutil,subprocess
from pathlib import Path
root=Path(sys.argv[1]).resolve();review=Path(__file__).resolve().parent
sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_wire as wire
base=root/'evidence/b4/unit_b4q_image_2026_10_28/e2e/valid'
out=root/'build/owner_archive_probes';out.mkdir(exist_ok=True)
rows=[]
def verify(p,name):
 j=review/('verify_'+name+'.json');log=j.with_suffix('.txt')
 cmd=[sys.executable,'-B',str(root/'host/b4q_verify.py'),str(p),'--json',str(j)]
 v=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=50)
 log.write_text('COMMAND '+repr(cmd)+'\nEXIT '+str(v.returncode)+'\n'+v.stdout+v.stderr)
 d=json.loads(j.read_text()) if j.exists() else {}
 rows.append({'case':name,'exit':v.returncode,'clean':d.get('clean'),'agree':d.get('agree'),'refused':d.get('refused'),'verifier_error':d.get('verifier_error'),'session':d.get('session')})
def fresh(name):
 p=out/name;shutil.copytree(base,p)
 m=json.loads((p/'manifest.json').read_text());lines=[json.loads(l) for l in (p/'console.jsonl').read_text().splitlines()]
 return p,m,lines
def parsed(row):return wire.parse(row['line'])
def edit(row,payload):
 f=parsed(row);row['line']=wire.frame(f['type'],f['seq'],f['token'],payload if isinstance(payload,str) else json.dumps(payload)).rstrip('\n')
for name in ['untouched','missing_console_control','source_downgrade','tx_genome_changed','tx_all_removed','reply_req_changed','reply_before_request','ident_array','end_array','signreq_array','signreq_bad_req_type','result_invalid_json','end_counter_float','reply_notary_words_changed','ident_nonce_echo_changed']:
 p,m,lines=fresh(name)
 if name=='missing_console_control':(p/'console.jsonl').unlink()
 elif name=='source_downgrade':m.pop('transport');(p/'console.jsonl').unlink()
 elif name=='tx_genome_changed':
  row=next(x for x in lines if x['dir']=='host' and x['line'] and ' TX ' in x['line'] and parsed(x)['payload'].startswith(b'TX normal'))
  fields=parsed(row)['payload'].decode().split(' ');fields[2]='00000001';edit(row,' '.join(fields))
 elif name=='tx_all_removed':
  lines=[x for x in lines if not(x['dir']=='host' and x['line'] and ' TX ' in x['line'])];m['transport']['console_lines']=len(lines)
 elif name=='reply_req_changed':
  row=next(x for x in lines if x['dir']=='host' and x['line'] and ' SIGNREPLY ' in x['line'] and not x.get('note'))
  fields=parsed(row)['payload'].decode().split(' ');fields[1]='999999';edit(row,' '.join(fields))
 elif name=='reply_before_request':
  ri=next(i for i,x in enumerate(lines) if x['dir']=='host' and x['line'] and ' SIGNREPLY ' in x['line']);row=lines.pop(ri)
  qi=next(i for i,x in enumerate(lines) if x['dir']=='board' and x.get('type')=='SIGNREQ');lines.insert(qi,row)
 elif name in ('ident_array','end_array','signreq_array','signreq_bad_req_type','result_invalid_json','end_counter_float','ident_nonce_echo_changed'):
  kind={'ident_array':'IDENT','end_array':'END','signreq_array':'SIGNREQ','signreq_bad_req_type':'SIGNREQ','result_invalid_json':'RESULT','end_counter_float':'END','ident_nonce_echo_changed':'IDENT'}[name]
  row=next(x for x in lines if x['dir']=='board' and x.get('type')==kind)
  if name.endswith('_array'):edit(row,[])
  elif name=='signreq_bad_req_type':
   q=json.loads(parsed(row)['payload']);q['req']={};edit(row,q)
  elif name=='result_invalid_json':edit(row,'{broken')
  elif name=='end_counter_float':
   e=json.loads(parsed(row)['payload']);e['transactions']=float(e['transactions']);edit(row,e);m['transport']['end']=e
  else:
   e=json.loads(parsed(row)['payload']);e['nonce_echo_equal']=0;e['page_nonce_seen']='f'*16;edit(row,e);m['transport']['ident']=e
 elif name=='reply_notary_words_changed':
  row=next(x for x in lines if x['dir']=='host' and x['line'] and ' SIGNREPLY ' in x['line'] and not x.get('note'))
  fields=parsed(row)['payload'].decode().split(' ');fields[2]='00000000' if fields[2]!='00000000' else '00000001';edit(row,' '.join(fields))
  n=p/'notary_log.json';entries=json.loads(n.read_text());entries[0]['words'][0]=int(fields[2],16);n.write_text(json.dumps(entries))
 if name not in ('missing_console_control','source_downgrade'):(p/'console.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in lines))
 (p/'manifest.json').write_text(json.dumps(m,indent=1)+'\n')
 verify(p,name)
review.joinpath('archive_probes.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
