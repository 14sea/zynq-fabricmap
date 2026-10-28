"""Local injected write error: retained bytes must survive exception propagation. No device is opened."""
import sys,json
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]).resolve();sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_runner as rn
out=root/'build/owner_retention_probe'
class P:
    def __init__(self,path):
        self.path=path;self.real='/dev/pts/fixture';self.kind='console-pty-surrogate';self.fd=-1;self.rx_log=bytearray(b'ACQUIRED-PREFIX\n');self.tx_log=bytearray();self.closed=False
    def write(self,b):self.tx_log.extend(b);raise OSError('injected tty write EIO')
    def close(self):self.closed=True
class U:
    def __init__(self,p,steps):self.steps=steps;self.p=p
    def get_prompt(self,**kw):self.steps.append({'what':'prompt','ok':True})
ports=[]
def makeport(path):p=P(path);ports.append(p);return p
with patch.object(rn,'Port',makeport),patch.object(rn,'UBoot',U):
    try:rn.run('/tmp/owner-fixture',out,lambda s:s._console_write('TX-FIXTURE\n'));result='returned'
    except Exception as e:result=type(e).__name__+': '+str(e)
print(json.dumps({'outcome':result,'rx_acquired':bytes(ports[0].rx_log).decode(),'raw_prefix_persisted':(out/'raw/console.bin').exists(),'port_closed':ports[0].closed,'files':[str(x.relative_to(out)) for x in out.rglob('*') if x.is_file()]},indent=2))
