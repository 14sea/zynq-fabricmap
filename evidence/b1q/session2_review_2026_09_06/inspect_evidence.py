"""Read-only audit of B1Q attempt 2. Writes results only to a separate output directory."""
from pathlib import Path
import collections, copy, hashlib, json, sys, subprocess
R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / 'host'))
import claimb_r1p_instrument as inst
import b1_pins, b1_qualification as bq, b1q_adjudicate as qa, b1_manifest as bm
instrument = inst.bind(require_git=True)
import l5_notary as n, l6_checks as lc, p3_gate as g, b1_records as records
D = R / 'evidence/b1q/b1q_17A6_2026-09-06-02'
O = Path('/tmp/b1q_session2_audit')
O.mkdir(parents=True, exist_ok=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_text())
before = {p.name: sha(p) for p in sorted(D.iterdir()) if p.is_file()}
m = load(R/'manifests/b1_manifest.json'); at = load(D/'manifest_at_run.json')
assert (D/'manifest_at_run.json').read_bytes() == (R/'manifests/b1_manifest.json').read_bytes()
pins = b1_pins.verify(manifest=m)
plan = load(R/m['qualification_plan']['path']); pred = load(R/m['qualification_plan']['prediction_path'])
result = qa.adjudicate(D, at, plan, pred, sha(D/'manifest_at_run.json'), require_git=True)
assert result['outcome'] == 'PASS', result
stored = load(D/'adjudication.json')
assert {k:v for k,v in result.items() if k!='evidence'} == {k:v for k,v in stored.items() if k!='evidence'}
q = load(D/'qualification.json')
assert bq.make_record(D, m, sha(D/'manifest_at_run.json'), plan, result) == q
candidate = copy.deepcopy(m); candidate['carrier']['qualification'] = q; candidate['carrier']['qualified'] = True
verified = bq.verify(candidate, require_git=True)
refreshed = bm.refresh(copy.deepcopy(m), qualification_dir=D)
assert refreshed == candidate
assert m['carrier']['qualification'] is None and m['carrier']['qualified'] is False
frames=[];bad=[]
for idx,line in enumerate((D/'console.log').read_bytes().splitlines(),1):
    if not line.startswith(b'P3L5 '): continue
    try:
        f=n.parse_line(line.decode('ascii')); f['decoded']=n.decode_payload(f['payload']) if f['payload']!='-' else None
        frames.append(f)
    except (ValueError,UnicodeError) as exc:
        bad.append({'line':idx,'type':line.split(b' ')[1].decode('ascii','replace'),'error':type(exc).__name__})
bytype=lambda kind:[f['decoded'] for f in frames if f['type']==kind]
log=load(D/'run_log.json'); aud=load(D/'audits.json'); summary=load(D/'summary.json'); timeline=load(D/'timeline.json')
recs=bytype('REC'); chunks=bytype('AUDIT')
assert recs==log['loop_records'] and chunks==aud['chunks']
assert bytype('IDENT')==[log['app_identity']]
assert bytype('TERM')==[log['session_summary']]
assert bytype('CLOSE')==[log['closing_negative']]
for rec in recs: records.validate(rec)
audit_count=lc.crash_audit_count({'loop_records':recs},chunks,g.load_manifest())
assert audit_count[0]==11
assert [r['seq'] for r in recs]==list(range(1,12))
assert len(chunks)==88 and all(r['outcome']=='SCORED' for r in recs)
assert collections.Counter(x['type'] for x in bad)=={'SIGNREQ':1,'REC':1}
assert all(x['error']=='CrcError' for x in bad)
assert timeline['bad_frames']==0 and timeline['crc_dropped']==2 and not timeline['fragments']
rx=[f for f in timeline['frames'] if f['dir']=='rx' and f['type']!='CRC_DROP']
assert [(f['type'],f['seq']) for f in frames]==[(f['type'],f['seq']) for f in rx]
assert all(f['token']==q['binding']['token'] for f in frames)
term_frame=next(f for f in rx if f['type']=='TERM')
assert any(f['dir']=='tx' and f['type']=='TERMACK' and f['seq']==12 and f['t_mono']>=term_frame['t_mono'] for f in timeline['frames'])
observations=[]
for rec in recs:
    ev=rec['evidence'];arm=ev['arm'];status=int(arm['status_after'],16)
    zeros=not any(int(x,16) for x in ev['score']['functional_readout'])
    assert not any(int(x,16) for x in ev['sign_reply']['expected_tables'])
    baseline=rec['seq'] in (1,11)
    assert bool(status & (1<<10))==baseline and zeros==baseline
    assert status & (1<<2) and not status & (1<<1) and arm['fault_after']==0
    if baseline: assert ev['score']['scores']==[18,22,20,20,20,18]
    observations.append({'seq':rec['seq'],'tables_match':int(bool(status&(1<<10))),'readout_all_zero':zeros,'cfg_valid':1,'fault':0})
close=log['closing_negative']
assert all(recs[j]['evidence']['arm']['nonce_after']==recs[j+1]['evidence']['arm']['nonce_before'] for j in range(10))
assert recs[-1]['evidence']['arm']['nonce_after']==close['nonce_before']
assert close==log['session_summary']['closing_control'] and close['fault']==13 and close['nonce_after']!=close['nonce_before']
assert log['session_summary']['written_by']=='app' and log['session_summary']['closing']==dict.fromkeys(('restore','baseline','unsigned_control'),'done')
assert log['session_summary']['epoch_end']=={'kind':'COMPLETED','last_seq':11,'reason':'budget'}

# Timestamped console is the same complete stream, with its recorded host timestamps.
ts_lines = (D/'console.ts.log').read_bytes().splitlines()
raw_wire = (D/'console.log').read_bytes().splitlines()
assert [line.split(b' ', 2)[2] for line in ts_lines] == raw_wire
# Independently apply the RTL's 64-bit xorshift after all eleven ARMs and the control.
nonce = int(m['carrier']['nonce_seed'], 16)
mask = (1 << 64) - 1
for arm in [r['evidence']['arm'] for r in recs] + [close]:
    assert int(arm['nonce_before'],16) == nonce
    nonce ^= (nonce << 13) & mask
    nonce ^= nonce >> 7
    nonce ^= (nonce << 17) & mask
    assert int(arm['nonce_after'],16) == nonce

boundary=load(R/'evidence/b1q/principal_boundary_2026-09-06-02.json')
go_wall=rx[0]['t_wall']-(rx[0]['t_mono']-log['timing']['t_go_mono'])
from validators import records as instrument_records
instrument_records.boundary_established(boundary, go_wall)
assert boundary['all_passed'] and all(c['passed'] for c in boundary['checks'])
assert 0 <= go_wall-boundary['at'] < 6*3600
rulings={}
for key,name in [('whole_of_run','b1q_2026-09-06-02.json'),('provisioning','p3_k_b1q_2026-09-06-02.json')]:
    raw,content=bq.read_archived_ruling(D/bq.RULING_FILES[key]);live=R/'rulings'/name
    assert raw==live.read_bytes()
    marker=live.with_name(name+'.consumed');assert marker.is_file()
    rulings[key]={'bytes_sha256':sha(live),'marker':marker.read_text()}
assert before=={p.name:sha(p) for p in sorted(D.iterdir()) if p.is_file()}
out={'reviewed_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_sha256':before,'boundary_sha256':sha(R/'evidence/b1q/principal_boundary_2026-09-06-02.json'),'instrument':instrument,'pins':pins,'adjudication_outcome':result['outcome'],'stored_adjudication_reproduced':True,'qualification_record_reproduced':True,'qualification_verify':verified,'in_memory_refresh_qualified':refreshed['carrier']['qualified'],'disk_manifest_unmodified':True,'valid_received_frames':dict(collections.Counter(f['type'] for f in frames)),'rejected_raw_lines':bad,'raw_matches_exported_records_chunks_ident_close_term':True,'timestamped_raw_stream_matches':True,'nonce_transitions_recomputed':12,'reported_rate_span_s':result['p3']['rate']['session_span_s'],'audit_verification':audit_count,'gate_observations':observations,'closing':close,'epoch_end':log['session_summary']['epoch_end'],'go_to_term_s':term_frame['t_mono']-log['timing']['t_go_mono'],'first_to_last_rec_s':next(f for f in rx if f['type']=='REC' and f['seq']==11)['t_mono']-next(f for f in rx if f['type']=='REC' and f['seq']==1)['t_mono'],'boundary_age_at_go_s':go_wall-boundary['at'],'rulings':rulings,'replay':result['replay'],'provisional':result['provisional']}
(O/'inspection.json').write_text(json.dumps(out,indent=2)+'\n')
(O/'readjudication.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('source_sha256','gate_observations','rulings')},indent=2))
