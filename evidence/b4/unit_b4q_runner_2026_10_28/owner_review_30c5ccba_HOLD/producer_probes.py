"""Local-only producer probes: no board endpoint, key provisioning or actual image execution."""
import sys,json,hashlib,errno
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
root=Path(sys.argv[1]).resolve();sys.path[:0]=[str(root),str(root/'host'),str(root/'b4/host')]
import b4q_runner as rn
from tests.test_b4q_runner import FakePort,scripted_uboot
work=root/'build/owner_producer_probes';work.mkdir(parents=True,exist_ok=True)
res={}
pin=hashlib.sha256(rn.IMAGE.read_bytes()).hexdigest()
def admit_only(s):
 s.uboot.get_prompt(break_s=0.01);s._set_phase('prompt');s.admit()
for name,kw,script in [('clock_mismatch',{'fclk0_ctrl_expected':0x00200a00},scripted_uboot(fclk0=0x00100a00)),('reference_role',{'role':'reference'},scripted_uboot())]:
 p=FakePort(script);ctx=rn.ExecutionContext(image_sha256=pin,image_path=str(rn.IMAGE),**kw)
 summ=rn.run('fake',work/name,admit_only,context=ctx,port=p)
 res[name]={'stop':summ['stop'],'phase':summ['phase'],'commands':p.tx_log.decode('ascii','replace'),'admission':summ['admission']}
# Isolate the publication barrier: assume all control-plane checks completed, fail the required pre-go persistence.
s=object.__new__(rn.RunnerSession);s.out=work/'persist';s.out.mkdir(exist_ok=True);s.port=SimpleNamespace(rx_log=bytearray(),tx_log=bytearray());s.phase='pre-go';s.runner={'stops':[],'phase':'pre-go'}
s.context=SimpleNamespace(load_addr=0x02000000);s.control_plane=lambda:None;go=[];s.uboot=SimpleNamespace(go=lambda a:go.append(a));s.proc=None
with patch.object(Path,'write_text',side_effect=OSError(errno.ENOSPC,'injected full filesystem')):
 try:s.start();outcome='returned normally'
 except Exception as e:outcome=type(e).__name__+': '+str(e)
res['pre_go_persist_failure']={'outcome':outcome,'go_calls':go,'phase':s.phase,'stops':s.runner['stops'],'uboot_exists':(s.out/'uboot.json').exists()}
# Port's raw TX commitment records bytes that os.write did not accept.
p=object.__new__(rn.Port);p.closed=False;p.fd=12345;p.tx_log=bytearray();calls=[]
def write(fd,data):
 calls.append(bytes(data))
 if len(calls)==1:return 2
 raise OSError(errno.EIO,'injected tty write error')
with patch.object(rn.select,'select',return_value=([],[12345],[])),patch.object(rn.os,'write',side_effect=write):
 try:p.write(b'go 02000000\r');outcome='returned'
 except Exception as e:outcome=type(e).__name__+': '+str(e)
res['partial_write_tx_commitment']={'outcome':outcome,'accepted_bytes':'go','recorded_tx':p.tx_log.decode(),'os_write_calls':[x.decode() for x in calls]}
# A file changed after a successful admit is re-read for transfer without rechecking its pin.
import zlib
image=work/'image_mutation.bin';image.write_bytes(rn.IMAGE.read_bytes())
class U:
 def __init__(self):self.steps=[{'what':'prompt','model':'Ebang EBAZ4203','dram_mib':512}];self.mem={};self.data=b'';self.go_calls=[]
 def md_l(self,a,n):
  if a==rn.VARIANT_ADDR:return [rn.rm.VARIANT_WORD]
  if a==rn.SLCR_FPGA0_CLK_CTRL:return [0x00200a00]
  return [self.mem.get(a+4*i,0) for i in range(n)]
 def mw_l(self,a,v):self.mem[a]=v
 def loady(self,a,data,name):self.data=data;return {'ymodem':{'blocks':1}}
 def crc32(self,a,n):return zlib.crc32(self.data)&0xffffffff
 def go(self,a):self.go_calls.append(a)
u=U();p=SimpleNamespace(path='fake',real='/dev/pts/fixture',kind='console-pty-surrogate',rx_log=bytearray(),tx_log=bytearray(),buf=bytearray(),fd=-1,closed=False)
ctx=rn.ExecutionContext(image_sha256=pin,image_path=str(image),fclk0_ctrl_expected=0x00200a00)
s=rn.RunnerSession(work/'mutation',p,u,ctx);s._set_phase('prompt');s.admit()
image.write_bytes(b'OWNER TEST ONLY: substituted after admission, never actually executed\n')
s.start()
res['image_changed_after_admission']={'pinned_sha256':pin,'transferred_sha256':hashlib.sha256(u.data).hexdigest(),'transferred_bytes':len(u.data),'go_calls':u.go_calls,'load_equal':s.runner['load_witness']['equal']}
print(json.dumps(res,indent=2))
