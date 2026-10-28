"""Deterministic, local-only transport counterexamples. No serial device is opened."""
import sys,json
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_runner as rn
import b4q_ymodem as ym
out={}
class Port:
    def __init__(self,chunks): self.chunks=list(chunks);self.writes=[]
    def read(self,t): return self.chunks.pop(0) if self.chunks else b''
    def write(self,b): self.writes.append(b)
# Application bytes in the same read as U-Boot's launch announcement must survive the handover.
p=Port([b'## Starting application at 0x02000000 ...\r\n@IDENT already-produced\n'])
u=rn.UBoot(p,[]);u.go(rn.LOAD_ADDR)
out['coalesced_go']={'following_read':p.read(0).decode(),'ident_in_go_reply':'@IDENT' in u.steps[-1]['reply']}
# A correctly coalesced last ACK + prompt must survive YMODEM's private buffer.
class YMPort(Port):
    def __init__(self):super().__init__([bytes([ym.CRC])]);self.eots=0
    def write(self,b):
        super().write(b)
        if b==bytes([ym.EOT]):
            self.eots+=1;self.chunks.append(bytes([ym.NAK]) if self.eots==1 else bytes([ym.ACK,ym.CRC]))
        elif b[0] in (ym.SOH,ym.STX):
            if b[1]==0 and b[3]==0:self.chunks.append(bytes([ym.ACK])+b'## Total Size = 0x1\r\nZynq> ')
            elif b[1]==0:self.chunks.append(bytes([ym.ACK,ym.CRC]))
            else:self.chunks.append(bytes([ym.ACK]))
p=YMPort();ym.send(p,b'x','fixture.bin')
out['coalesced_ymodem_tail']={'ordinary_next_read':p.read(0).decode(),'stranded_private_buffer':p._ym_buf.decode()}
# The md.l parser must check addresses, not just count the values returned.
p=Port([b'md.l 10440000 1\r\ndeadbeef: 12345678    ....\r\nZynq> ']);u=rn.UBoot(p,[])
out['wrong_md_address']={'requested':'10440000','returned':'deadbeef','accepted_words':u.md_l(0x10440000,1)}
p=Port([b'crc32 02000000 1\r\nCRC32 for deadbeef ... deadbeef ==> 12345678\r\nZynq> ']);u=rn.UBoot(p,[])
out['wrong_crc_range']={'accepted_crc':hex(u.crc32(0x02000000,1))}
# Busy junk must not renew a transfer's overall deadline indefinitely. Probe cap is not a product timeout.
class Clock:
    def __init__(self): self.t=0
    def __call__(self):self.t+=1;return self.t
class ProbeCap(Exception):pass
class Flood(Port):
    def __init__(self):super().__init__([]);self.reads=0
    def read(self,t):
        self.reads+=1
        if self.reads>100:raise ProbeCap('local probe cap after 100 reads')
        return bytes([ym.CRC]) if self.reads==1 else b'!'
p=Flood();c=Clock()
with patch.object(ym.time,'time',c):
    try:ym.send(p,b'x','fixture.bin',timeout=5,retries=2);result='returned'
    except Exception as e:result=type(e).__name__+': '+str(e)
out['junk_vs_overall_timeout']={'declared_timeout':5,'clock_elapsed':c.t,'reads':p.reads,'outcome':result}
print(json.dumps(out,indent=2))
