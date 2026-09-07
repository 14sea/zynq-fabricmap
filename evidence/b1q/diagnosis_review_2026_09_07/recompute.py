"""Recompute descriptive receive/host-send timing; no causal attribution or device access."""
from pathlib import Path
import json,collections,hashlib,statistics,bisect
R=Path(__file__).resolve().parents[3];O=Path('/tmp/b1q_diagnosis_review');O.mkdir(exist_ok=True)
paths={f'b1q_{i}':R/f'evidence/b1q/b1q_17A6_2026-09-06-0{i}' for i in (1,2,3)}
paths['soak']=Path('/home/test/zynq_psoracle/evidence/l6_17A6_2026-09-04-01-S')
report={}
for label,d in paths.items():
 t=json.loads((d/'timeline.json').read_text());s=json.loads((d/'summary.json').read_text());frames=t['frames']
 tx=sorted(f['t_mono'] for f in frames if f['dir']=='tx')
 rx=[f for f in frames if f['dir']=='rx' and f['type'] not in ('CRC_DROP','FRAGMENT')]
 crc=[f for f in frames if f['type']=='CRC_DROP'];control_ids=set()
 # First SIGNREQ and REC CRC events: identify as controls only when the next valid
 # frame of the same type is seq 1, consistent with the armed retry controls.
 for kind in ('SIGNREQ','REC'):
  candidates=[(i,f) for i,f in enumerate(crc) if f.get('frame_type')==kind]
  if candidates:
   i,event=candidates[0];following=next((f for f in rx if f['type']==kind and f['t_mono']>=event['t_mono']),None)
   if following is not None and following['seq']==1:control_ids.add(i)
 noncontrol=[f for i,f in enumerate(crc) if i not in control_ids]
 def after_tx(f):
  j=bisect.bisect_right(tx,f['t_mono'])-1
  return f['t_mono']-tx[j] if j>=0 else None
 bad_dt=[after_tx(f) for f in noncontrol];good_dt=[after_tx(f) for f in rx]
 windows={}
 for width in (.06,.25,.5):
  windows[str(width)]={'noncontrol_crc_within':sum(x is not None and 0<=x<=width for x in bad_dt),'noncontrol_crc_total':len(noncontrol),'valid_rx_within':sum(x is not None and 0<=x<=width for x in good_dt),'valid_rx_total':len(rx)}
 raw=d/'console.log'
 report[label]={'timeline_sha256':hashlib.sha256((d/'timeline.json').read_bytes()).hexdigest(),'input_sha256':{name:hashlib.sha256((d/name).read_bytes()).hexdigest() for name in ('timeline.json','summary.json','console.log')},'summary_crc_dropped':s.get('crc_dropped'),'timeline_crc_dropped':t['crc_dropped'],'crc_events':len(crc),'inferred_seq1_controls':len(control_ids),'noncontrol_crc':len(noncontrol),'fragments':len(t['fragments']),'valid_rx_frames':len(rx),'rx_bytes':raw.stat().st_size if raw.exists() else None,'noncontrol_crc_per_100kB':len(noncontrol)*100000/raw.stat().st_size if raw.exists() else None,'noncontrol_crc_per_valid_rx_pct':100*len(noncontrol)/len(rx),'noncontrol_crc_events':[{'type':f.get('frame_type'),'after_latest_host_tx_s':after_tx(f),'t_mono':f['t_mono']} for f in noncontrol],'fragment_after_latest_host_tx_s':[after_tx(f) for f in t['fragments']],'window_counts':windows,'valid_rx_max_after_tx_s':max(x for x in good_dt if x is not None)}
(O/'recomputed.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:{a:b for a,b in v.items() if a not in ('noncontrol_crc_events','timeline_sha256')} for k,v in report.items()},indent=2))
