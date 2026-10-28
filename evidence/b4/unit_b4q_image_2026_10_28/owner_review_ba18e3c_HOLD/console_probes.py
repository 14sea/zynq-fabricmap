"""Owner fixture. Exercises actual compiled application; only an emulated backend is used."""
import json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_console_session as cs
import b4q_e2e as ee
import b4q_session as ss
out=root/'build/owner_console_probes';out.mkdir(exist_ok=True)
results={}
s=cs.ConsoleSession(out/'duplicate')
try:
 s.open();s.transaction('root',0,ee.stim([]))
 first=s.transaction('normal',ee.G_BASE,ee.stim(ee.FIX0))
 saved=[x['line'] for x in s.console if x['dir']=='host' and x['line'] and x['line'].startswith('B4Q1 TX ')][-1]+'\n'
 old=s._frame_out
 def replay(kind,payload=''):
  return saved if kind=='TX' else old(kind,payload)
 s._frame_out=replay
 signs=s.stats['signreq'];trace=len(s.backend.trace)
 second=s.transaction('normal',ee.G_BASE,ee.stim(ee.FIX0))
 txlines=[x['line'] for x in s.console if x['dir']=='host' and x['line'] and x['line'].startswith('B4Q1 TX ')]
 results['duplicate']={'exact_replay':txlines[-1]==txlines[-2], 'replayed_sequence':saved.split()[2], 'first_status':first['firmware']['status'], 'second_status':second['firmware']['status'], 'second_x':second['x']['status'] if second['x'] else None, 'new_signreqs':s.stats['signreq']-signs, 'new_trace_events':len(s.backend.trace)-trace,'new_findings':second['findings']}
finally:s.stop()
s.write()
s=cs.ConsoleSession(out/'after_stop',notary_deny={ee.G_CESR})
try:
 s.open();s.transaction('root',0,ee.stim([]))
 failed=s.transaction('normal',ee.G_CESR,ee.stim(ee.FIX1))
 try:s.transaction('normal',ee.G_BASE,ee.stim(ee.FIX0));api_refused=False
 except ss.SessionRefusal:api_refused=True
 signs=s.stats['signreq'];trace=len(s.backend.trace)
 words=[ss.step_word(x) for x in ee.stim(ee.FIX0)[1:]]
 # Deliberately inject at the framing boundary, bypassing the high-level transaction API's latch.
 s._send('TX normal %08x %d '%(ee.G_BASE,len(words))+' '.join('%07x'%w for w in words))
 result=s.serve()
 results['after_stop']={'stopped_status':failed['firmware']['status'],'stopped_reason':failed['firmware']['reason'],'high_level_api_refused':api_refused,'host_halted':s.halted,'raw_next_status':result.get('status'),'raw_next_phase':result.get('phase'),'new_signreqs':s.stats['signreq']-signs,'new_trace_events':len(s.backend.trace)-trace}
finally:s.stop()
s.write()
# Exercise the actual host receive method with complete in-memory console lines.
s=cs.ConsoleSession(out/'host_sequence')
s._fds={'c2h_r':-1}  # never read: complete lines are supplied in the receive buffer
import b4q_wire as wire
s._con_buf=(wire.frame('HB',7,s.token)+wire.frame('HB',7,s.token)+wire.frame('HB',6,s.token)).encode()
errors=[]
for i in range(3):
 try:s._console_line()
 except Exception as e:errors.append(type(e).__name__+': '+str(e))
results['host_sequence']={'injected_board_sequences':[7,7,6],'exceptions':errors,'accepted_heartbeat_count':s.stats['hb']}
print(json.dumps(results,indent=2))
