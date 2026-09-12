"""Independent offline integration review. No hardware access or live authority."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile
from unittest.mock import patch

R = Path('/home/test/zynq_fabricmap')
sys.path[:0] = [str(R / 'host'), str(R / 'tests')]
import b2_manifest as bm
import b2_modelled_session as ms
import b2_plan as bp
import b2_runner as rn
import claimb_r1p_instrument as inst
from test_b2_runner import Fixture

out = Path(tempfile.mkdtemp(prefix='b2_modelled_review_'))
result = {'reviewed_head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=R, text=True).strip(),
          'scope': 'MODEL ONLY; no board, no production qualification or authority',
          'temporary_artifacts': str(out)}
def save():
    (out / 'review.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
def stats(s, v):
    return {k:s[k] for k in ('records','epoch_end','crc_dropped','bad_frames','exports','virtual_s','wall_s')} | {
        'outcome':v['outcome'], 'findings':v['findings'], 'kills':v['kills'],
        'replay':v.get('replay'), 'measured_rate_per_hour':v.get('measured_rate_per_hour')}
ms.bind_instrument(False)
f = Fixture('S1')
mp = f.path()
sha = hashlib.sha256(mp.read_bytes()).hexdigest()
qp = rn.qualification_session_plan(f.manifest, sha)
qcfg = dict(profile=rn.QUALIFICATION,manifest=f.manifest,plan=qp,instrument_root=inst.DEFAULT_ROOT)
qe = out/'b2q'
qs = ms.run_modelled(f.manifest,sha,qp,rn.qualification_seeds(f.manifest),qe)
qv = rn.adjudication_for(qcfg)(qe)
assert qv['outcome'] == 'PASS', qv
ms.finalize(qe,qv,qs['summary'],qs['rulings'])
result['B2Q'] = stats(qs,qv)
m2 = json.loads(bm.render(bm.qualify(f.manifest,qe,readjudicate=rn.readjudicator(f.manifest))))
p = bp.build_plan(m2['calibration']['rate_per_hour'])
pred = bp.build_prediction(p['fitness'],p['budget_per_arm'],[tuple(x) for x in m2['seeds']['pairs']],m2['map']['canonical_json_sha256'])
pp,_ = bp.write(out/'plan',p,pred)
m3 = json.loads(bm.render(bm.pin_plan(m2,pp,readjudicate=rn.readjudicator(m2))))
vp = out/'s3_manifest.json'
vp.write_text(bm.render(m3))
code = 'import json,sys; import b2_manifest as m,b2_runner as r; d=json.load(open(sys.argv[1])); print(json.dumps(m.verify(d,readjudicate=r.readjudicator(d))))'
v = subprocess.run([sys.executable,'-c',code,str(vp)],cwd=R,env=dict(os.environ,PYTHONPATH=str(R/'host')),capture_output=True,text=True)
assert v.returncode == 0, v.stderr
result['fresh_process_verify'] = json.loads(v.stdout)
result['split'] = p['session_split']
save()

# The final slice tests a nonzero offset using the actual calibration and frozen budget.
f.manifest = m3
f.plan_doc = p
split = p['session_split']
print('SPLIT',json.dumps(split),flush=True)
entries = split.get('sessions')
if not isinstance(entries,list):
    entries = next(v for v in split.values() if isinstance(v,list) and v and isinstance(v[0],dict) and 'pair_first' in v[0])
entry = entries[-1]
a = f.args(profile=rn.SEARCH,pair_first=entry['pairs'][0],pair_count=len(entry['pairs']),out=out/'b2')
a.boundary.write_text(json.dumps({'runner_user':pwd.getpwuid(os.getuid()).pw_name,
    'signer_user':a.signer_user,'key_store':str(a.key.parent)}))
from validators import records
which = rn.shutil.which
with patch.object(records,'boundary_established',return_value=None), patch.object(rn.shutil,'which',side_effect=lambda x: '/offline/review/sb' if x=='sb' else which(x)):
    cfg = rn.preflight(a,rn.SEARCH,pins_verify=lambda *_:{'offline_review_double':'b2_pins not implemented'})
result['preflight_doubles'] = ['missing b2_pins hook','boundary_established','sb discovery']
result['B2_invocation'] = {k:cfg['plan'][k] for k in ('session','pair_first','pair_count','pairs_total','n','expected_records','session_timeout_s')}
save()
bs = ms.run_modelled(m3,cfg['manifest_sha256'],cfg['plan'],cfg['seeds'],a.out)
bv = rn.adjudication_for(cfg)(a.out)
ms.finalize(a.out,bv,bs['summary'],bs['rulings'])
result['B2'] = stats(bs,bv)
save()
assert bv['outcome'] == 'PASS', bv
assert not bv.get('primary'), bv.get('primary')
