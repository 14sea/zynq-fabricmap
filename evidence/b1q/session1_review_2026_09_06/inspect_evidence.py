from pathlib import Path
import sys,json,collections,hashlib
R=Path('/home/test/zynq_fabricmap');sys.path.insert(0,str(R/'host'))
import claimb_r1p_instrument as inst
inst.bind(inst.DEFAULT_ROOT)
import l5_notary as n,l6_checks as lc,p3_gate as g,b1_records as records
D=R/'evidence/b1q/b1q_17A6_2026-09-06-01'
frames=[];bad=[]
for idx,line in enumerate((D/'console.log').read_bytes().splitlines(),1):
 if not line.startswith(b'P3L5 '):continue
 try:f=n.parse_line(line.decode('ascii'));f['decoded']=n.decode_payload(f['payload']) if f['payload']!='-' else None;frames.append(f)
 except (ValueError,UnicodeError) as exc:bad.append({'line':idx,'type':line.split(b' ')[1].decode('ascii','replace'),'error':type(exc).__name__})
recs=[f['decoded'] for f in frames if f['type']=='REC'];audits=[f['decoded'] for f in frames if f['type']=='AUDIT'];close=[f['decoded'] for f in frames if f['type']=='CLOSE']
for rec in recs:records.validate(rec)
t=json.loads((D/'timeline.json').read_text())
report={'valid_received_frames':dict(collections.Counter(f['type'] for f in frames)),'rejected_raw_lines':bad,'record_seq_outcomes':[(r['seq'],r['outcome']) for r in recs],'audit_verification':lc.crash_audit_count({'loop_records':recs},audits,g.load_manifest()),'closing_negative':close,'timeline_counts':dict(collections.Counter(f['dir']+':'+f['type'] for f in t['frames'])),'ident_to_last_fragment_s':t['frames'][-1]['t_mono']-t['frames'][0]['t_mono'],'manifest_at_run_sha256':hashlib.sha256((D/'manifest_at_run.json').read_bytes()).hexdigest(),'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(D.iterdir()) if p.is_file()}}
print(json.dumps(report,indent=2));print('First REC:',json.dumps(recs[0])[:2500])
Path('/tmp/b1q_session1_review/inspection.json').write_text(json.dumps(report,indent=2)+'\n')
