import json,sys,subprocess,shutil
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(__file__).resolve().parent
sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_wire as w
src=root/'evidence/b4/unit_b4q_image_2026_10_28/e2e/valid';dst=root/'build/owner_exchange_probes';dst.mkdir(exist_ok=True);rows=[]
def pf(e):return w.parse(e['line'])
def rewrite(e,payload):
 f=pf(e);e['line']=w.frame(f['type'],f['seq'],f['token'],payload if isinstance(payload,str) else json.dumps(payload)).rstrip('\n')
for case in ['untouched','all_replies_removed','all_replies_removed_counters','first_reply_removed','last_reply_removed','reply_noted_stale','signreq_only_unanswered']:
 d=dst/case;shutil.copytree(src,d);m=json.loads((d/'manifest.json').read_text());lines=[json.loads(x) for x in (d/'console.jsonl').read_text().splitlines()]
 replies=[i for i,e in enumerate(lines) if e['dir']=='host' and e.get('line') and ' SIGNREPLY ' in e['line'] and not e.get('note')]
 if case.startswith('all_replies_removed'):lines=[e for i,e in enumerate(lines) if i not in replies]
 elif case=='first_reply_removed':lines=[e for i,e in enumerate(lines) if i!=replies[0]]
 elif case=='last_reply_removed':lines=[e for i,e in enumerate(lines) if i!=replies[-1]]
 elif case=='reply_noted_stale':
  lines[replies[0]]['note']='a stale SIGNREPLY: owner coordinated negative';m['transport']['stats']['stale']+=1
 elif case=='signreq_only_unanswered':
  # Leave all raw replies but identify every one as unanswered to the state machine via stale annotations.
  for i in replies:lines[i]['note']='a stale SIGNREPLY: owner coordinated negative'
  m['transport']['stats']['stale']+=len(replies)
 if case=='all_replies_removed_counters':
  m['transport']['stats']['signreply']=0;m['transport']['end']['sign_replies']=0
  for e in lines:
   if e['dir']=='board' and e.get('type')=='END':v=json.loads(pf(e)['payload']);v['sign_replies']=0;rewrite(e,v)
 m['transport']['console_lines']=len(lines)
 (d/'console.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in lines));(d/'manifest.json').write_text(json.dumps(m,indent=1)+'\n')
 j=out/('exchange_'+case+'.json');cmd=[sys.executable,'-B',str(root/'host/b4q_verify.py'),str(d),'--json',str(j)];p=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=50);j.with_suffix('.txt').write_text('COMMAND '+repr(cmd)+'\nEXIT '+str(p.returncode)+'\n'+p.stdout+p.stderr);rep=json.loads(j.read_text());rows.append({'case':case,'exit':p.returncode,'clean':rep['clean'],'agree':rep['agree'],'session':rep.get('session'),'refused':rep.get('refused'),'verifier_error':rep.get('verifier_error')})
(out/'exchange_probes.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
