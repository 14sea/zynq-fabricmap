from pathlib import Path
import sys,json
root=Path(sys.argv[1]).resolve();sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_console_session as cs,b4q_wire as w
s=cs.ConsoleSession(root/'build/owner_callback_probe',label='owner-fixture');sent=[];s._console_write=lambda line,note='':sent.append(line)
s.halt('owner fixture: stopped');n=len(s.notary.log);t=len(s.backend.trace)
s._answer_sign({'payload':json.dumps({'genome':'00000000','nonce':'0'*16,'req':5}).encode(),'seq':5})
print(json.dumps({'reply_count':len(sent),'reply_payload':w.parse(sent[0],s.token)['payload'].decode(),'new_notary_entries':s.notary.log[n:],'new_trace_events':len(s.backend.trace)-t},indent=2))
