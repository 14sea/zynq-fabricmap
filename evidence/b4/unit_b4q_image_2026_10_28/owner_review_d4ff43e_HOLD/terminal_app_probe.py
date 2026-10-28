"""Actual app + actual unchanged transaction core, emulated MMIO after a terminal END."""
import json,os,sys,signal
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(__file__).resolve().parent
sys.path[:0]=[str(root/'host'),str(root/'b4/host')]
import b4q_console_session as cs
rows=[]
for mode in ['baseline','sequence_cut']:
 if mode=='sequence_cut':os.environ['B4Q_OWNER_CUT']='1'
 else:os.environ.pop('B4Q_OWNER_CUT',None)
 s=cs.ConsoleSession(root/'build'/('owner_terminal_'+mode),binary=root/'build/owner_terminal_apphost',label='owner-mechanism-fixture')
 try:
  so=s.open();s._send('TX root 00000000 0');ret=s.serve();first_end=s.ended
  endpos=len(s.backend.trace);endpcap=len(s.backend.pcap_log);drain=None
  if first_end:
   # Continue answering the emulated HAL, observing whether the app actually stopped effects after its END.
   # This is diagnostic draining, not another TX. No new command/signature is supplied.
   signal.alarm(25)
   try:drain=s.serve()
   except Exception as e:drain={'exception':type(e).__name__+': '+str(e)}
   finally:signal.alarm(0)
  after=s.backend.trace[endpos:]
  row={'mode':mode,'opening_findings':so['findings'],'first_return_status':ret.get('status'),'end':first_end,'new_trace_events_after_END':len(after),'write_ops_after_END':sum(e.get('op')=='wr' for e in after),'pcap_entries_after_END':len(s.backend.pcap_log)-endpcap,'drain':drain}
  for name,entries in [('trace',s.backend.trace),('pcap',s.backend.pcap_log),('console',s.console)]:
   (out/(mode+'_'+name+'.jsonl')).write_text(''.join(json.dumps(e)+'\n' for e in entries))
  row['post_end_write_examples']=[e for e in after if e.get('op')=='wr'][:8]
  rows.append(row)
 finally:s.stop()
print(json.dumps(rows,indent=2))
