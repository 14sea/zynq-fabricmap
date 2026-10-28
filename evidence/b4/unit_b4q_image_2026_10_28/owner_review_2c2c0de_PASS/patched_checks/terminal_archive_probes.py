"""Focused checks of the newly accepted terminal-prefix verifier path."""
import json,sys,shutil,subprocess
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(__file__).resolve().parent;sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_wire as w
src=root/'evidence/b4/unit_b4q_image_2026_10_28/e2e/sequence_cut';base=root/'build/owner_terminal_archive_probes';base.mkdir(exist_ok=True);rows=[]
for case in ['untouched','terminal_low_sequence','terminal_trace_origin','terminal_pcap_origin','terminal_bad_reason_control']:
 d=base/case;shutil.copytree(src,d);m=json.loads((d/'manifest.json').read_text());L=[json.loads(x) for x in (d/'console.jsonl').read_text().splitlines()]
 end=next(e for e in L if e['dir']=='board' and e.get('type')=='END')
 if case=='terminal_low_sequence':
  board=[e for e in L if e['dir']=='board' and e.get('line')]
  for e,seq in [(board[-2],100),(board[-1],101)]:
   f=w.parse(e['line']);e['line']=w.frame(f['type'],seq,f['token'],f['payload']).rstrip('\n');e['seq']=seq
  m['transport']['board_seq_last']=101
 elif case=='terminal_trace_origin':end['i']=0
 elif case=='terminal_pcap_origin':end['pcap_n']=0
 elif case=='terminal_bad_reason_control':
  f=w.parse(end['line']);v=json.loads(f['payload']);v['reason']='not an exhaustion';end['line']=w.frame(f['type'],f['seq'],f['token'],json.dumps(v)).rstrip('\n');m['transport']['end']=v
 (d/'manifest.json').write_text(json.dumps(m,indent=1)+'\n');(d/'console.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in L))
 j=out/('terminal_archive_'+case+'.json');cmd=[sys.executable,'-B',str(root/'host/b4q_verify.py'),str(d),'--json',str(j)];p=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=50);j.with_suffix('.txt').write_text('COMMAND '+repr(cmd)+'\nEXIT '+str(p.returncode)+'\n'+p.stdout+p.stderr);rep=json.loads(j.read_text());rows.append({'case':case,'exit':p.returncode,'clean':rep['clean'],'agree':rep['agree'],'session':rep.get('session'),'refused':rep.get('refused'),'verifier_error':rep.get('verifier_error'),'END_i':end['i'],'END_pcap_n':end.get('pcap_n'),'END_seq':w.parse(end['line'])['seq']})
(out/'terminal_archive_probes.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
