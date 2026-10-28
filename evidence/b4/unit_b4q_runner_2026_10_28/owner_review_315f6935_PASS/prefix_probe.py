"""Raw reply timing relative to first PL command; disposable archives only."""
import sys,json,hashlib,shutil,subprocess,tempfile,re
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();src=root/'evidence/b4/unit_b4q_runner_2026_10_28/e2e_runner/valid'
work=Path(tempfile.mkdtemp(prefix='owner_prefix_reply_',dir=root/'build'));summary={}
for case in ['positive','late_io_reply','late_role_reply']:
 p=work/case;shutil.copytree(src,p);u=json.loads((p/'uboot.json').read_text());m=json.loads((p/'manifest.json').read_text());rx=(p/'raw/console.bin').read_bytes()
 if case!='positive':
  pat=rb'^f8000108: [^\n]*\n' if case=='late_io_reply' else rb'^role=[^\n]*\n'
  match=re.search(pat,rx,re.M);assert match is not None;line=match[0];rx=rx[:match.start()]+rx[match.end():]
  echo=re.search(rb'md\.l 43c02034 1\r?\n',rx);assert echo is not None
  rx=rx[:echo.end()]+line+rx[echo.end():]
  (p/'raw/console.bin').write_bytes(rx);u['raw'].update(console_bin_sha256=hashlib.sha256(rx).hexdigest(),console_bin_bytes=len(rx));m['transport']['runner']=u
  (p/'uboot.json').write_text(json.dumps(u,indent=1)+'\n');(p/'manifest.json').write_text(json.dumps(m,indent=1)+'\n')
 f=out/(case+'.json');q=subprocess.run([sys.executable,'-B',str(root/'host/b4q_verify.py'),str(p),'--json',str(f)],cwd=root,capture_output=True,text=True);(out/(case+'.txt')).write_text(q.stdout+q.stderr)
 r=json.loads(f.read_text());summary[case]={'exit':q.returncode,**{k:r.get(k) for k in ['clean','agree','refused','session','verifier_error']},'work':str(p)}
print(json.dumps(summary,indent=2))
