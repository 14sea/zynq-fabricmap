"""An arbitrary local image with a self-consistent transfer is not a pinned image. No actual image is executed."""
import sys,json,zlib,hashlib
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
root=Path(sys.argv[1]).resolve();sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_runner as rn
work=root/'build/owner_admission';work.mkdir(parents=True,exist_ok=True)
image=work/'not_the_pinned_image.bin';image.write_bytes(b'OWNER TEST ONLY: arbitrary non-executable fixture bytes\n')
class U:
    def __init__(self):self.steps=[];self.mem={};self.data=b'';self.go_calls=[]
    def loady(self,a,data,name):self.data=data;return {'ymodem':{'blocks':1}}
    def crc32(self,a,n):return zlib.crc32(self.data)&0xffffffff
    def md_l(self,a,n):return [self.mem.get(a+4*i,0) for i in range(n)]
    def mw_l(self,a,v):self.mem[a]=v
    def go(self,a):self.go_calls.append(a)
u=U();p=SimpleNamespace(path='/tmp/owner-fixture',real='/dev/pts/fixture',kind='console-pty-surrogate',fd=-1)
with patch.object(rn.bk,'Backend',wraps=rn.bk.Backend) as backend:
    s=rn.RunnerSession(work/'output',p,u,image=image);s.start()
    calls=backend.call_count
print(json.dumps({'arbitrary_image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'arbitrary_image_size':image.stat().st_size,'go_calls':u.go_calls,'load_witness':s.runner['load_witness'],'page_equal':s.runner['page_witness']['equal'],'backend_constructions_in_runner_process':calls,'backend_final_value':s.backend},indent=2))
