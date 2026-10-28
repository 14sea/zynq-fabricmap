import sys,json,shutil,subprocess
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(__file__).resolve().parent;sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_wire as w
base=root/'build/owner_end_reply_probes';base.mkdir(exist_ok=True);rows=[]
for case in ['untouched','quit_answered_protocol','quit_answered_stop']:
 d=base/case;shutil.copytree(root/'evidence/b4/unit_b4q_image_2026_10_28/e2e/valid',d);m=json.loads((d/'manifest.json').read_text());L=[json.loads(x) for x in (d/'console.jsonl').read_text().splitlines()];e=next(x for x in L if x['dir']=='board' and x.get('type')=='END');f=w.parse(e['line']);v=json.loads(f['payload'])
 if case!='untouched':
  v['kind']='PROTOCOL' if case=='quit_answered_protocol' else 'STOPPED';v['reason']="this side's line sequence is exhausted" if case=='quit_answered_protocol' else 'no host command within the idle bound';e['line']=w.frame(f['type'],f['seq'],f['token'],json.dumps(v)).rstrip('\n');m['transport']['end']=v
 (d/'console.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in L));(d/'manifest.json').write_text(json.dumps(m,indent=1)+'\n');j=out/('end_reply_'+case+'.json');cmd=[sys.executable,'-B',str(root/'host/b4q_verify.py'),str(d),'--json',str(j)];p=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=50);j.with_suffix('.txt').write_text('COMMAND '+repr(cmd)+'\nEXIT '+str(p.returncode)+'\n'+p.stdout+p.stderr);v=json.loads(j.read_text());rows.append({'case':case,'exit':p.returncode,'clean':v['clean'],'agree':v['agree'],'session':v['session'],'END_seq':f['seq'],'last_host_frame':'QUIT'})
(out/'end_reply_probes.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
