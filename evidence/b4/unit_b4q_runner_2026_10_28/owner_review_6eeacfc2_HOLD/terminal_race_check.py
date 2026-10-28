"""Force both liveness states at acquisition; the terminal-tail account must not depend on process-exit timing."""
import sys,json
from pathlib import Path
root=Path(sys.argv[1]).resolve();sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_console_session as cs
results=[]
for alive in (False,True):
 s=object.__new__(cs.ConsoleSession);s.ps=True;s.log_bytes=bytearray(b'x'*16);s.tail_unobtainable=None
 calls=[]
 def live():calls.append(alive);return alive
 s._transport_alive=live
 r={'status':cs.END_STATUS,'end':{'kind':'PROTOCOL','reason':'the sequence is exhausted','log':64}}
 got=s._acquire(r)
 assert got is r and s.tail_unobtainable['end_log']==64 and s.tail_unobtainable['pulled']==16 and calls==[]
 results.append({'simulated_transport_alive':alive,'liveness_consulted':bool(calls),'tail':s.tail_unobtainable})
print(json.dumps(results,indent=2))
