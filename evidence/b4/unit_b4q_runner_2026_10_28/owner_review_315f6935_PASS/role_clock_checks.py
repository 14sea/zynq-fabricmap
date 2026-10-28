"""Independent expected eligibility matrix and local admission controls. No device is opened."""
import sys,json,hashlib,copy
from pathlib import Path
root=Path(sys.argv[1]).resolve();sys.path[:0]=[str(root),str(root/'host'),str(root/'b4/host')]
import b4q_runner as rn
import b4q_zynq_clk as zc
from tests.test_b4q_runner import FakePort,scripted_uboot
base={'fpga0':0x00200A00,'arm':0x0001A000,'ddr':0x00020000,'io':0x0001E000,'status':0x3F,'boot_mode':5}
cases=[('normal',{},True),('reset',{'io':0x1E001},False),('powerdown',{'io':0x1E002},False),('force_bypass',{'io':0x1E010},False),('qualified_bypass',{'io':0x1E008,'boot_mode':0x15},False),('qualified_normal',{'io':0x1E008,'boot_mode':5},True),('strap_ignored_when_not_qualified',{'io':0x1E000,'boot_mode':0x15},True),('unlocked',{'status':0x3B},False),('zero_divisor',{'fpga0':0},False),('unselected_reset',{'arm':0x1A001},True),('arm_selected_unlocked',{'fpga0':0x00200A20,'status':0x3E},False),('ddr_selected_unlocked',{'fpga0':0x00200A30,'status':0x3D},False)]
cases += [('missing_'+k,{k:None},False) for k in zc.WORDS]
res={'eligibility':[],'roles':[],'admission':[]}
for name,changes,expected in cases:
 words={**base,**changes};r=zc.fclk0_eligibility(words);assert r['eligible'] is expected,(name,r)
 res['eligibility'].append({'name':name,'expected':expected,'eligible':r['eligible'],'why':r['why']})
pin=hashlib.sha256(rn.IMAGE.read_bytes()).hexdigest()
for roles in [('reference',),('verify','reference'),(None,),(),('spare',)]:
 try:rn.ExecutionContext(image_sha256=pin,allowed_roles=roles);outcome='accepted'
 except rn.ContextRefusal:outcome='ContextRefusal'
 assert outcome=='ContextRefusal';res['roles'].append({'requested':roles,'outcome':outcome})
work=root/'build/owner_role_clock_checks';work.mkdir(parents=True,exist_ok=True)
def admit(s):s.uboot.get_prompt(break_s=.01);s._set_phase('prompt');s.admit()
for name,script,ctxargs,ok in [('verify',scripted_uboot(),{},True),('sacrificial',scripted_uboot(role='sacrificial'),{'allowed_roles':('sacrificial',)},True),('narrow_verify_refused',scripted_uboot(),{'allowed_roles':('sacrificial',)},False),('powerdown_refused',scripted_uboot(io_pll=0x1E002),{},False)]:
 port=FakePort(script);ctx=rn.ExecutionContext(image_sha256=pin,image_path=str(rn.IMAGE),expected_boardid='F8B3',**ctxargs)
 r=rn.run('fixture',work/name,admit,context=ctx,port=port);assert (r['stop'] is None)==ok
 if not ok:assert b'md.l 43c' not in port.tx_log
 res['admission'].append({'name':name,'stop':r['stop'],'pl_read_issued':b'md.l 43c' in port.tx_log})
print(json.dumps(res,indent=2))
