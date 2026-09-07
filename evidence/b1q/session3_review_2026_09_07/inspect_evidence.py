"""Read-only attempt-3 audit; all outputs are separate from original evidence."""
from pathlib import Path
import sys,json,hashlib,collections,copy
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R/'host'))
import claimb_r1p_instrument as inst,b1_pins,b1q_adjudicate as qa,b1_qualification as bq,b1_adjudicate as adj
instrument=inst.bind(require_git=True)
import l5_notary as n,l6_reader as reader,l6_checks as lc,p3_gate as g
from validators import records as vr
D=R/'evidence/b1q/b1q_17A6_2026-09-06-03';O=Path('/tmp/b1q_session3_audit');O.mkdir(exist_ok=True)
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources={p.name:sha(p) for p in sorted(D.iterdir()) if p.is_file()}
m=load(D/'manifest_at_run.json');assert sha(D/'manifest_at_run.json')==sha(R/'manifests/b1_manifest.json')
log=load(D/'run_log.json');audits=load(D/'audits.json');summ=load(D/'summary.json');timeline=load(D/'timeline.json');q=load(D/'qualification.json')
ex=adj.check_exports(D)
res=qa.adjudicate(D,m,load(R/m['qualification_plan']['path']),load(R/m['qualification_plan']['prediction_path']),sha(D/'manifest_at_run.json'),require_git=True)
assert res['outcome'].startswith('HOLD')
stored=load(D/'adjudication.json');assert {k:v for k,v in res.items() if k!='evidence'}=={k:v for k,v in stored.items() if k!='evidence'}
assert bq.make_record(D,m,sha(D/'manifest_at_run.json'),load(R/m['qualification_plan']['path']),res)==q
for f,h in q['files'].items():assert sha(D/f)==h
trial=copy.deepcopy(m);trial['carrier']['qualification']=q
try:bq.verify(trial,require_git=True);raise AssertionError('HOLD must not qualify')
except bq.QualificationRefusal as e:refusal=str(e)
class MemorySerial:
 def __init__(self,data):self.data=data
 @property
 def in_waiting(self):return len(self.data)
 def read(self,n):out,self.data=self.data[:n],self.data[n:];return out
rd=reader.L6LineReader(MemorySerial((D/'console.log').read_bytes()))
lines=rd.poll();frames=[];bad=[]
for line,_,_ in lines:
 if not line.startswith('P3L5 '):continue
 try:
  f=n.parse_line(line);f['decoded']=n.decode_payload(f['payload']) if f['payload']!='-' else None;f['raw']=line;frames.append(f)
 except ValueError as e:
  parts=line.split(' ');bad.append({'type':parts[1],'seq':int(parts[2]),'error':type(e).__name__,'payload':parts[4],'crc':parts[5],'raw':line})
by=lambda kind:[f['decoded'] for f in frames if f['type']==kind]
assert by('REC')==log['loop_records'] and by('AUDIT')==audits['chunks'] and by('IDENT')==[log['app_identity']]
assert not by('TERM') and not by('CLOSE')
assert len(rd.fragments)==len(timeline['fragments'])==1
assert rd.fragments[0]['text']==timeline['fragments'][0]['text']
assert [(f['type'],f['seq']) for f in frames]==[(f['type'],f['seq']) for f in timeline['frames'] if f['dir']=='rx' and f['type'] not in ('CRC_DROP','FRAGMENT')]
assert collections.Counter(x['type'] for x in bad)==timeline['crc_dropped_by_type']
assert all(b['error']=='CrcError' for b in bad)
assert log['session_summary']['written_by']=='collector' and log['session_summary']['epoch_end']==summ['epoch_end']
assert summ['epoch_end']=={'kind':'PROTOCOL','last_seq':3,'reason':'PROTOCOL_CRC_BUDGET: 5 > 4'}
assert set(log['session_summary']['closing'].values())=={'not_reached'}
counts=dict(collections.Counter(x['seq'] for x in audits['chunks']))
assert counts=={1:8,2:8,3:8,4:4}
completed_chunks=[x for x in audits['chunks'] if x['seq']<=3]
audit_count=lc.crash_audit_count({'loop_records':log['loop_records']},completed_chunks,g.load_manifest());assert audit_count[0]==3
# Compare damaged payloads to same-run valid retransmissions or explicit offline candidates.
prev=load(R/'evidence/b1q/b1q_17A6_2026-09-06-02/audits.json')
def subsequence(short,long):
 it=iter(long);return all(any(x==c for x in it) for c in short)
comparisons=[]
for b in bad:
 candidates=[(f['payload'],'same-run CRC-valid frame') for f in frames if f['type']==b['type'] and f['seq']==b['seq']]
 if b['type']=='HB':candidates += [(n.encode_payload({'i':i}),'enumerated protocol heartbeat i='+str(i)) for i in range(16)]
 if b['type']=='AUDIT':candidates += [(n.encode_payload(c),'attempt-2 CRC-valid audit chunk '+str(c['chunk'])) for c in prev['chunks'] if c['seq']==b['seq']]
 hits=[]
 for payload,source in candidates:
  if n.build_line(b['type'],b['seq'],q['binding']['token'],payload).strip().split(' ')[-1]==b['crc']:
   hits.append({'source':source,'expected_payload_chars':len(payload),'received_payload_chars':len(b['payload']),'deletion_only_subsequence':subsequence(b['payload'],payload),'same_payload':payload==b['payload']})
 comparisons.append({'type':b['type'],'seq':b['seq'],'payload_chars':len(b['payload']),'urlsafe_base64_alphabet_only':all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=' for c in b['payload']),'crc_matching_candidates':hits})
boundary_path=R/'evidence/b1q/principal_boundary_2026-09-07-01.json';boundary=load(boundary_path)
first=timeline['frames'][0];go_wall=first['t_wall']-(first['t_mono']-log['timing']['t_go_mono']);vr.boundary_established(boundary,go_wall)
rulings={}
for key,name in [('whole_of_run','b1q_2026-09-06-03.json'),('provisioning','p3_k_b1q_2026-09-06-03.json')]:
 raw,content=bq.read_archived_ruling(D/bq.RULING_FILES[key]);p=R/'rulings'/name
 assert raw==p.read_bytes() and p.with_name(name+'.consumed').is_file()
 bq._bind_ruling(content,qa.RULING_TEXT if key=='whole_of_run' else bq.PROVISION_RULING_TEXT,q['binding'],key=='whole_of_run')
 rulings[key]={'sha256':sha(p),'consumed_marker':p.with_name(name+'.consumed').read_text()}
assert sources=={p.name:sha(p) for p in D.iterdir() if p.is_file()}
out={'source_sha256':sources,'boundary_sha256':sha(boundary_path),'pins':b1_pins.verify(),'instrument':instrument,'outcome':res['outcome'],'record_reproduced':True,'qualification_refusal':refusal,'exports_complete':ex['complete'],'valid_frame_counts':dict(collections.Counter(f['type'] for f in frames)),'raw_records_and_chunks_match':True,'completed_record_audits':audit_count,'audit_chunks_per_seq':counts,'epoch_end':summ['epoch_end'],'crc_drop_comparisons':comparisons,'fragments':timeline['fragments'],'bad_frames':timeline['bad_frames'],'go_to_last_event_s':timeline['frames'][-1]['t_mono']-log['timing']['t_go_mono'],'boundary_age_at_go_s':go_wall-boundary['at'],'rulings':rulings}
(O/'inspection.json').write_text(json.dumps(out,indent=2)+'\n');(O/'readjudication.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('source_sha256','rulings')},indent=2))
