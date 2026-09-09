"""Offline mapping audit; originals are read-only, outputs go to /tmp."""
from pathlib import Path
import collections, hashlib, json, subprocess, sys
R=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(R/'host'))
import b1_adjudicate as adj, b1_qualification as q, b1_pins, b1_runner as runner
import claimb_r1p_instrument as inst
instrument=inst.bind(require_git=True)
import l5_notary as n, l6_checks as lc, p3_gate as gate
from validators import records as vr
D=R/'evidence/b1/b1_17A6_2026-09-08-02'
O=Path('/tmp/b1_mapping_review_2026_09_08');O.mkdir(exist_ok=True)
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={p.name:sha(p) for p in sorted(D.iterdir()) if p.is_file()}
boundary_path=R/'evidence/b1/principal_boundary_2026-09-08-02.json'
for p in [*D.iterdir(),boundary_path]:
    if p.is_file(): assert p.read_bytes()==subprocess.check_output(['git','show','31d619e:'+str(p.relative_to(R))])
m=load(R/'manifests/b1_manifest.json');ms=sha(R/'manifests/b1_manifest.json')
assert (R/'manifests/b1_manifest.json').read_bytes()==(D/'manifest_at_run.json').read_bytes()
plan=load(R/m['plan']['path']);pred=load(R/m['prediction']['path'])
pins=b1_pins.verify(manifest=m);qualified=q.verify(m,require_git=True)
res=adj.adjudicate(D,m,plan,pred,ms,require_git=True)
assert res['outcome']=='PASS' and not res['findings'],res.get('findings')
assert {k:v for k,v in res.items() if k not in ('evidence','self_map_v2')}=={k:v for k,v in load(D/'adjudication.json').items() if k!='evidence'}
assert res['self_map_v2']==load(D/'self_map_v2.json')
log=load(D/'run_log.json');aud=load(D/'audits.json');tl=load(D/'timeline.json');su=load(D/'summary.json')
assert su['outcome']=='PASS' and su['findings']==[]
raw=(D/'console.log').read_bytes().splitlines()
ts=(D/'console.ts.log').read_bytes().splitlines()
assert [l.split(b' ',2)[2] for l in ts]==raw
frames=[];bad=[]
for i,line in enumerate(raw):
    if not line.startswith(b'P3L5 '): continue
    try:
        f=n.parse_line(line.decode('ascii'));f['decoded']=n.decode_payload(f['payload']) if f['payload']!='-' else None
        frames.append((i,line,f))
    except n.CrcError:
        parts=line.split(b' ')
        assert len(parts)==6
        bad.append({'line':i+1,'type':parts[1].decode(),'seq':int(parts[2]),'parts':parts})
by=lambda kind:[f['decoded'] for _,_,f in frames if f['type']==kind]
assert by('REC')==log['loop_records'] and by('AUDIT')==aud['chunks']
assert by('IDENT')==[log['app_identity']] and by('TERM')==[log['session_summary']] and by('CLOSE')==[log['closing_negative']]
counts=dict(collections.Counter(f['type'] for _,_,f in frames));assert counts==plan['expected_frames']['by_type']
assert len(frames)==9048 and len(bad)==6
assert [(b['type'],b['seq']) for b in bad]==[('SIGNREQ',1),('REC',1),('REC',85),('AUDIT',147),('SIGNREQ',221),('SIGNREQ',244)]
assert tl['crc_dropped']==6 and tl['bad_frames']==0 and not tl['fragments']
rx=[f for f in tl['frames'] if f['dir']=='rx' and f['type']!='CRC_DROP']
assert [(f['type'],f['seq']) for _,_,f in frames]==[(f['type'],f['seq']) for f in rx]
assert all(f['token']==su['token'] for _,_,f in frames)
for b in bad:
    parts=b.pop('parts');control=b['seq']==1
    matches=[(i,line,f) for i,line,f in frames if i>=b['line'] and f['type']==b['type'] and f['seq']==b['seq'] and
             (line.split(b' ')[:5]==parts[:5] if control else line.split(b' ')[-1]==parts[-1])]
    assert len(matches)==1,(b,len(matches))
    i,good,f=matches[0]
    b.update({'forced_control':control,'valid_retransmission_line':i+1,'valid_payload_sha256':hashlib.sha256(f['payload'].encode()).hexdigest(),'received_byte_deficit':len(good)-len(b' '.join(parts))})
    if not control:
        it=iter(good);assert all(any(c==x for x in it) for c in b' '.join(parts))
        assert b['received_byte_deficit']>0
    if b['type']=='AUDIT': b['retransmitted_chunk_index']=f['decoded']['chunk']
recs=by('REC');chunks=by('AUDIT');close=by('CLOSE')[0];term=by('TERM')[0]
assert len(recs)==335 and len(chunks)==2680 and all(r['outcome']=='SCORED' for r in recs)
audit_count=lc.crash_audit_count({'loop_records':recs},chunks,gate.load_manifest());assert audit_count[0]==335
assert term['audit']=={'audited':335,'total':335}
assert term['written_by']=='app' and term['closing']==dict.fromkeys(('baseline','restore','unsigned_control'),'done')
assert term['epoch_end']=={'kind':'COMPLETED','last_seq':335,'reason':'budget'}
assert close==term['closing_control'] and close['fault']==13
nonce=int(m['carrier']['nonce_seed'],16);mask=(1<<64)-1
for arm in [r['evidence']['arm'] for r in recs]+[close]:
    assert int(arm['nonce_before'],16)==nonce
    nonce^=(nonce<<13)&mask;nonce^=nonce>>7;nonce^=(nonce<<17)&mask
    assert int(arm['nonce_after'],16)==nonce
assert all(not any(int(x,16) for x in r['evidence']['sign_reply']['expected_tables']) for r in recs)
termf=next(f for f in rx if f['type']=='TERM')
assert any(f['dir']=='tx' and f['type']=='TERMACK' and f['seq']==336 and f['t_mono']>=termf['t_mono'] for f in tl['frames'])
go=log['timing']['t_go_mono'];gowall=rx[0]['t_wall']-(rx[0]['t_mono']-go)
boundary=load(boundary_path);vr.boundary_established(boundary,gowall)
assert boundary['all_passed'] and all(c['passed'] for c in boundary['checks'])
rulings={}
for kind,name in [('whole_of_run','b1_2026-09-08-02.json'),('provisioning','p3_k_b1_2026-09-08-02.json')]:
    rb,r=q.read_archived_ruling(D/q.RULING_FILES[kind]);p=R/'rulings'/name
    assert rb==p.read_bytes()
    issued=load(R/'evidence/b1/mapping_pair_review_2026_09_08/inspection.json')
    assert sha(p)==next(x['sha256'] for x in issued['rulings'] if Path(x['path']).name==name)
    assert r['ruling']==(runner.RULING_TEXT if kind=='whole_of_run' else runner.PROVISION_RULING_TEXT)
    marker=p.with_name(p.name+'.consumed');assert marker.exists()
    assert r['boardid']=='17A6' and r['date']=='2026-09-08-02' and r['granted_by']=='14sea'
    runner.bind_ruling(r,r['ruling'],m['prereg']['sha256'],m['image']['sha256'],ms,1123460948 if kind=='whole_of_run' else None,'B1')
    if kind=='whole_of_run': assert su['ruling']==r
    else: assert su['provisioning_ruling_sha256']==sha(p)
    rulings[kind]={'sha256':sha(p),'consumed_marker':marker.read_text()}
assert before=={p.name:sha(p) for p in D.iterdir() if p.is_file()}
report={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'manifest_sha256':ms,'source_sha256':before,'boundary_sha256':sha(boundary_path),'originals_match_commit':True,'pins':pins,'instrument':instrument,'qualification':qualified,'outcome':res['outcome'],'stored_adjudication_reproduced':True,'stored_expanded_map_reproduced':True,'raw_matches_exports':True,'valid_frames':counts,'valid_frame_total':len(frames),'crc_failures':bad,'noncontrol_crc_denominator':{'failures':4,'valid_received':9048,'noncontrol_attempts_including_retries':9052,'fraction':4/9052},'audit_check':audit_count,'nonce_transitions':336,'epoch_end':term['epoch_end'],'closing':close,'go_to_term_monotonic_s':termf['t_mono']-go,'boundary_age_at_go_s':gowall-boundary['at'],'wall_minus_monotonic_change_s':(rx[-1]['t_wall']-rx[-1]['t_mono'])-(rx[0]['t_wall']-rx[0]['t_mono']),'rate':res['p3']['rate'],'replay':res['replay'],'metrics':res['b1_result'],'rulings':rulings,'token':su['token']}
(O/'inspection.json').write_text(json.dumps(report,indent=2)+'\n')
(O/'readjudication.json').write_text(json.dumps({k:v for k,v in res.items() if k!='self_map_v2'},indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('source_sha256','metrics','rulings')},indent=2))
