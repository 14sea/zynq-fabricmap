"""Synthetic physical-format source selection; no device-origin claim or physical execution."""
import sys,json,subprocess
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_device_fixture as df
src=root/'evidence/b4/unit_b4q_runner_2026_10_28/e2e_runner/valid'
work=root/'build/owner_device_source_probes';work.mkdir(parents=True,exist_ok=True)
summary={}
for case in ['synthetic_device_control','device_without_source']:
 p=work/case;df.make(src,p)
 if case=='device_without_source':
  m=json.loads((p/'manifest.json').read_text());m.pop('source',None);(p/'manifest.json').write_text(json.dumps(m,indent=1)+'\n')
 report=out/(case+'.json');q=subprocess.run([sys.executable,'-B',str(root/'host/b4q_verify.py'),str(p),'--json',str(report)],cwd=root,capture_output=True,text=True)
 (out/(case+'.txt')).write_text(q.stdout+q.stderr)
 r=json.loads(report.read_text());summary[case]={'exit':q.returncode,**{k:r.get(k) for k in ['clean','agree','refused','session','provenance']},'selected_source':r.get('source',{}).get('kind')}
print(json.dumps(summary,indent=2))
