"""Local-only checks of newly added admission and verifier paths; no device/image execution."""
import sys,json,hashlib,subprocess,shutil,re
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();sys.path[:0]=[str(root),str(root/'host'),str(root/'b4/host')]
import b4q_runner as rn
import b4q_verify_runner as vr
from tests.test_b4q_runner import FakePort,scripted_uboot
work=root/'build/owner_remaining_final';work.mkdir(parents=True,exist_ok=True)
results={}
pin=hashlib.sha256(rn.IMAGE.read_bytes()).hexdigest()
def admission_only(s):
 s.uboot.get_prompt(break_s=.01);s._set_phase('prompt');s.admit()
for name,kw,script in [
 ('positive',{},scripted_uboot()),
 ('reference_default',{},scripted_uboot(role='reference')),
 ('reference_override',{'allowed_roles':('reference',)},scripted_uboot(role='reference')),
 ('missing_role_override',{'allowed_roles':(None,)},scripted_uboot(role=None)),
 ('pll_powerdown',{},scripted_uboot(io_pll=0x0001E002)),
 ('pll_bypass_qualified',{},scripted_uboot(io_pll=0x0001E008))]:
 port=FakePort(script);ctx=rn.ExecutionContext(image_sha256=pin,image_path=str(rn.IMAGE),expected_boardid='F8B3',**kw)
 s=rn.run('fake',work/name,admission_only,context=ctx,port=port)
 results[name]={'phase':s['phase'],'stop':s['stop'],'identity':(s.get('admission')or{}).get('identity'),'clock':(s.get('admission')or{}).get('clock'),'pl_read_issued':b'md.l 43c' in port.tx_log,'commands':port.tx_log.decode('ascii','replace')}
results['clock_helpers_powerdown']={'runner':rn.fclk0_from_words(0x00200A00,{'io':0x0001E002,'arm':0,'ddr':0}),'verifier':vr.fclk0_from_words(0x00200A00,{'io':0x0001E002,'arm':0,'ddr':0})}
# Coordinated actual-role override in an executed fixture, retaining every raw commitment.
source=root/'evidence/b4/unit_b4q_runner_2026_10_28/e2e_runner/valid'
for name in ['archive_positive','archive_reference_override','archive_pll_powerdown','archive_pll_read_after_pl']:
 p=work/name;shutil.copytree(source,p);m=json.loads((p/'manifest.json').read_text());u=json.loads((p/'uboot.json').read_text());rx=(p/'raw/console.bin').read_bytes();tx=(p/'raw/console_tx.bin').read_bytes()
 if name=='archive_reference_override':
  assert b'role=verify' in rx;edit=rx.index(b'role=verify');rx=rx.replace(b'role=verify',b'role=reference')
  for step in u['uboot_steps']:
   for field in ('rx_at','rx_end'):
    if step.get(field,0)>edit:step[field]+=3
  u['context']['allowed_roles']=['reference'];u['admission']['identity'].update(role='reference',allowed_roles=['reference'],role_ok=True)
  for s in u['uboot_steps']:
   if s.get('what')=='printenv' and s.get('sent')=='printenv role':s['reply']=s.get('reply','').replace('role=verify','role=reference');s['value']='reference'
 elif name=='archive_pll_powerdown':
  old=b'f8000108: 0001e000';assert old in rx;rx=rx.replace(old,b'f8000108: 0001e002')
  u['admission']['clock']['pll_ctrl']['io']='0001e002';u['admission']['clock']['derived']['pll_ctrl']='0001e002'
  for s in u['uboot_steps']:
   if s.get('sent')=='md.l f8000108 1':
    s['reply']=s.get('reply','').replace('0001e000','0001e002');s['words']=['0001e002']
 elif name=='archive_pll_read_after_pl':
  # Keep the FPGA divider read before PL, move the selected PLL read after VARIANT in both streams.
  block=re.search(rb'md\.l f8000108 1\r\n.*?Zynq> ',rx,re.S);assert block
  val=block[0];rx=rx[:block.start()]+rx[block.end():]
  v=re.search(rb'md\.l 43c02034 1\r\n.*?Zynq> ',rx,re.S);assert v;rx=rx[:v.end()]+val+rx[v.end():]
  cmd=b'md.l f8000108 1\r';assert tx.count(cmd)==1;tx=tx.replace(cmd,b'');k=tx.find(b'md.l 43c02034 1\r')+len(b'md.l 43c02034 1\r');tx=tx[:k]+cmd+tx[k:]
  io_step=next(x for x in u['uboot_steps'] if x.get('sent')=='md.l f8000108 1')
  pl_step=next(x for x in u['uboot_steps'] if x.get('sent')=='md.l 43c02034 1')
  for field in ('rx_at','rx_end','tx_at','tx_end','t'):io_step[field],pl_step[field]=pl_step[field],io_step[field]
  u['uboot_steps'].remove(io_step);u['uboot_steps'].insert(u['uboot_steps'].index(pl_step)+1,io_step)
 (p/'raw/console.bin').write_bytes(rx);(p/'raw/console_tx.bin').write_bytes(tx)
 u['raw'].update(console_bin_sha256=hashlib.sha256(rx).hexdigest(),console_bin_bytes=len(rx),console_tx_bin_sha256=hashlib.sha256(tx).hexdigest(),console_tx_bin_bytes=len(tx));m['transport']['runner']=u
 (p/'uboot.json').write_text(json.dumps(u,indent=1)+'\n');(p/'manifest.json').write_text(json.dumps(m,indent=1)+'\n')
 report=out/(name+'.json');r=subprocess.run([sys.executable,'-B',str(root/'host/b4q_verify.py'),str(p),'--json',str(report)],cwd=root,text=True,capture_output=True)
 (out/(name+'.txt')).write_text(r.stdout+r.stderr);d=json.loads(report.read_text());results[name]={'exit':r.returncode,**{k:d.get(k) for k in ['clean','agree','refused','verifier_error','session']}}
print(json.dumps(results,indent=2))
