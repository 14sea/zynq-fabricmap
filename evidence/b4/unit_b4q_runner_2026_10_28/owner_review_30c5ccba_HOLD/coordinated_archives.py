"""Coordinated raw-stream negatives. All files are disposable fixture copies; no device/seed work."""
import json,sys,subprocess,shutil,hashlib,re
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();work=root/'build/owner_coordinated_final';work.mkdir(parents=True,exist_ok=True)
src=root/'evidence/b4/unit_b4q_runner_2026_10_28/e2e_runner/valid'
summary={}
for name in ['baseline','load_at_different_address','crc_false_but_executed','board_256_but_executed','missing_admission','null_context_pin','extra_rx_frame','unknown_stop']:
 p=work/name;shutil.copytree(src,p)
 m=json.loads((p/'manifest.json').read_text());u=json.loads((p/'uboot.json').read_text());rx=(p/'raw/console.bin').read_bytes();tx=(p/'raw/console_tx.bin').read_bytes()
 if name=='load_at_different_address':
  tx=tx.replace(b'loady 02000000\r',b'loady 04000000\r').replace(b'crc32 02000000 ',b'crc32 04000000 ')
  rx=rx.replace(b'loady 02000000\r',b'loady 04000000\r').replace(b'download to 0x02000000',b'download to 0x04000000').replace(b'crc32 02000000 ',b'crc32 04000000 ')
  rx=re.sub(rb'(crc32 for )02000000( \.\.\. )02018013',rb'\g<1>04000000\g<2>04018013',rx)
  for step in u['uboot_steps']:
   if step.get('what') in ('loady','crc32'):
    for key in ('sent','reply'):
     if isinstance(step.get(key),str):step[key]=step[key].replace('02000000','04000000').replace('02018013','04018013')
    if 'range' in step:step['range']=['04000000','04018013']
  u['load_witness']['range']=['04000000','04018013']
 elif name=='crc_false_but_executed':
  pat=rb'(crc32 for [0-9a-f]{8} \.\.\. [0-9a-f]{8} ==> )([0-9a-f]{8})'
  match=re.search(pat,rx);value=('00000000' if match[2]!=b'00000000' else '00000001')
  rx=rx[:match.start(2)]+value.encode()+rx[match.end(2):]
  u['load_witness']['uboot_crc32']=value;u['load_witness']['equal']=False
  for s in u['uboot_steps']:
   if s.get('what')=='crc32':s['crc32']=value;s['reply']=re.sub(r'(==> )[0-9a-f]{8}',lambda x:x[1]+value,s.get('reply',''))
 elif name=='board_256_but_executed':
  old=rx;rx=rx.replace(b'ECC disabled 512 MiB',b'ECC disabled 256 MiB');assert rx!=old
  u['admission']['board'].update(dram_mib=256,dram_ok=False);u['admission']['ok']=False
  for s in u['uboot_steps']:
   if s.get('what')=='prompt':s['dram_mib']=256;s['reply']=s.get('reply','').replace('512 MiB','256 MiB')
 elif name=='missing_admission':u['admission']=None
 elif name=='null_context_pin':u['context']['image_sha256']=None
 elif name=='extra_rx_frame':
  board=next(json.loads(x)['line'] for x in (p/'console.jsonl').read_text().splitlines() if json.loads(x).get('dir')=='board' and json.loads(x).get('line','').startswith('B4Q1 END '))
  k=rx.find(b'B4Q1 IDENT ');assert k>=0
  rx=rx[:k]+board.encode()+b'\n'+rx[k:]
 elif name=='unknown_stop':
  # Start from a legitimate pre-go archive, not the completed session.
  shutil.rmtree(p);shutil.copytree(src.parent/'control_plane_only',p)
  m=json.loads((p/'manifest.json').read_text());u=json.loads((p/'uboot.json').read_text());rx=(p/'raw/console.bin').read_bytes();tx=(p/'raw/console_tx.bin').read_bytes()
  u['phase']='stopped';u['phase_at_stop']='prompt';u['stops']=[{'kind':'TransportStop','why':'OWNER INVENTED STOP WITH NO RAW WITNESS'}]
 (p/'raw/console.bin').write_bytes(rx);(p/'raw/console_tx.bin').write_bytes(tx)
 u['raw'].update(console_bin_sha256=hashlib.sha256(rx).hexdigest(),console_bin_bytes=len(rx),console_tx_bin_sha256=hashlib.sha256(tx).hexdigest(),console_tx_bin_bytes=len(tx))
 m['transport']['runner']=u
 (p/'uboot.json').write_text(json.dumps(u,indent=1)+'\n');(p/'manifest.json').write_text(json.dumps(m,indent=1)+'\n')
 report=out/(name+'.json');q=subprocess.run([sys.executable,'-B',str(root/'host/b4q_verify.py'),str(p),'--json',str(report)],cwd=root,capture_output=True,text=True)
 (out/(name+'.txt')).write_text(q.stdout+q.stderr)
 r=json.loads(report.read_text());summary[name]={'exit':q.returncode,**{k:r.get(k) for k in ['agree','clean','refused','verifier_error','session']},'runner':r.get('runner',{}).get('findings'),'control_plane':r.get('control_plane')}
print(json.dumps(summary,indent=2))
