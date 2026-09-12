"""Offline review of the real finalizer ordering and the model CLI's output contract."""
import hashlib,json,os,sys,tempfile,subprocess
from pathlib import Path
R=Path('/home/test/zynq_fabricmap')
sys.path[:0]=[str(R/'host'),str(R/'tests')]
import b1_session as prod
import b2_manifest as bm
import b2_modelled_session as ms
import b2_runner as rn
import claimb_r1p_instrument as inst
from test_b2_runner import Fixture
out=Path(tempfile.mkdtemp(prefix='b2_finalize_review_'))
M=ms.bind_instrument(False)
f=Fixture('S1'); mp=f.path(); sha=hashlib.sha256(mp.read_bytes()).hexdigest()
p=rn.qualification_session_plan(f.manifest,sha)
cfg=dict(profile=rn.QUALIFICATION,manifest=f.manifest,plan=p,instrument_root=inst.DEFAULT_ROOT)
key=out/'model_key.bin';key.write_bytes(bytes(range(16)));key.chmod(0o400)
c=ms.Candidates(M,f.manifest,p,rn.qualification_seeds(f.manifest),key)
s=ms.B2Session(M,c,p,f.manifest,'0123456789abcdef0123456789abcdef',identity_check=rn.identity_check_for(cfg))
s.run()
ev=out/'evidence';ev.mkdir()
r=ms.session_artifacts(ev,f.manifest,sha,p)
summary={'tool':'offline-review','token':s.token,'outcome':None,'ruling':r['whole_of_run'][1],
         'provisioning_ruling_sha256':hashlib.sha256(r['provisioning'][0]).hexdigest(),
         'l6':dict(p,audit_seqs=sorted(p['audit_seqs']))}
callback=rn.adjudication_for(cfg)
timing=[]
def judge(d):
    timing.append({'summary_exists_at_callback':(d/'summary.json').exists(),
                   'seal_exists_at_callback':(d/'exports.json').exists()})
    return callback(d)
actual=prod.finalize(ev,summary,p,s.collector,s.cs,s.relay,s.timeline,s.reader,s.t_go,judge)
assert actual['outcome']=='PASS',actual
prod.persist_summary(ev,actual)
m2=bm.qualify(f.manifest,ev,readjudicate=rn.readjudicator(f.manifest))
assert m2['qualified']
cli=subprocess.run([sys.executable,str(R/'host/b2_modelled_session.py'),'--manifest',str(mp),'--out',str(out/'cli')],cwd=R,capture_output=True,text=True)
cli_result=json.loads(cli.stdout)
result={'scope':'MODEL ONLY; real production finalizer, no hardware',
        'production_finalizer_outcome':actual['outcome'],'callback_order':timing,
        'post_finalize_qualify':m2['qualified'],
        'cli':{'returncode':cli.returncode,'epoch_end':cli_result['epoch_end'],
               'crc_dropped':cli_result['crc_dropped'],'outcome_present':'outcome' in cli_result,
               'summary_exists':(out/'cli/summary.json').exists(),
               'adjudication_exists':(out/'cli/adjudication.json').exists()},'temporary_artifacts':str(out)}
(out/'review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
