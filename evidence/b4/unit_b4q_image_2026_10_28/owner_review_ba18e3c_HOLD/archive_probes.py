"""Fresh-process verification of submitted / regenerated console archives and independent tamper copies."""
import json,sys,shutil,subprocess
from pathlib import Path
root=Path(sys.argv[1]).resolve();review=Path(__file__).resolve().parent
sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_wire as wire
base=root/'evidence/b4/unit_b4q_image_2026_10_28/e2e'
out=root/'build/owner_archive_probes';out.mkdir(exist_ok=True)
rows=[]
def verify(p,kind):
 log=review/('verify_'+kind+'_'+p.name+'.txt');j=log.with_suffix('.json')
 cmd=[sys.executable,'-B',str(root/'host/b4q_verify.py'),str(p),'--json',str(j)]
 v=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=40)
 log.write_text('COMMAND '+repr(cmd)+'\nEXIT '+str(v.returncode)+'\n'+v.stdout+v.stderr)
 d=json.loads(j.read_text()) if j.exists() else {}
 rows.append({'case':kind+'/'+p.name,'exit':v.returncode,'clean':d.get('clean'),'agree':d.get('agree'),'refused':d.get('refused'),'verifier_error':d.get('verifier_error')})
for group,path in [('submitted',base),('regenerated',root/'build/owner_console_e2e')]:
 for p in sorted(path.iterdir()):
  if p.is_dir():verify(p,group)
for name in ['untouched','missing_console','bad_crc','result_changed','ident_changed','end_changed','transport_changed']:
 p=out/name;shutil.copytree(base/'valid',p)
 f=p/'console.jsonl'
 if name=='missing_console':f.unlink()
 elif name in ('bad_crc','result_changed','ident_changed','end_changed'):
  docs=[json.loads(x) for x in f.read_text().splitlines()]
  want={'bad_crc':'IDENT','result_changed':'RESULT','ident_changed':'IDENT','end_changed':'END'}[name]
  for row in docs:
   if row['dir']=='board' and row.get('type')==want:
    line=row['line'];parsed=wire.parse(line)
    if name=='bad_crc':row['line']=line[:-1]+('0' if line[-1]!='0' else '1')
    else:
     payload=json.loads(parsed['payload'])
     if name=='result_changed':payload['fitness']=999
     elif name=='ident_changed':payload['token']='f'*32
     else:payload['transactions']=999
     row['line']=wire.frame(parsed['type'],parsed['seq'],parsed['token'],json.dumps(payload)).rstrip('\n')
    break
  f.write_text(''.join(json.dumps(x)+'\n' for x in docs))
 elif name=='transport_changed':
  m=p/'manifest.json';d=json.loads(m.read_text());d['transport']['ident']['token']='f'*32;d['transport']['page_words'][0]='00000000';d['transport']['end']['transactions']=999;m.write_text(json.dumps(d,indent=1)+'\n')
 verify(p,'tamper')
review.joinpath('archive_probes.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
