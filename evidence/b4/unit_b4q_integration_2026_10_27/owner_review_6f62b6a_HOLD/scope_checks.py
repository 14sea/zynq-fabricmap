from pathlib import Path
import json,subprocess,hashlib
R=Path('/home/test/zynq_fabricmap');C=Path('/tmp/owner_b4q_repair_3ogm8sq4');O=R/'build/wip/owner_review_6f62b6a_2026_10_27'
git=lambda *a:subprocess.check_output(['git','-C',str(R),*a])
protected=['b4/host','b4/schemas','b4/hypothesis','rtl','builds','vivado','tb','sim','b3','firmware/b1','firmware/b2','evidence/b4/sim','evidence/b4/gate','evidence/b4/gonogo','gate_runs','manifests']
diff=git('diff','--name-status','dd8a7b9','HEAD','--',*protected).decode().splitlines()
assert diff==['M\tbuilds/b4/b4_carrier_manifest.json'],diff
before=json.loads(git('show','3723b91:builds/b4/b4_carrier_manifest.json'))
retained=json.loads((R/'evidence/b4/unit_b4q_integration_2026_10_27/manifest_regeneration/b4_carrier_manifest_before_52f2ea56.json').read_bytes());assert before==retained
now=json.loads((R/'builds/b4/b4_carrier_manifest.json').read_bytes())
fresh=json.loads((C/'build/owner_manifest_regenerated.json').read_bytes());assert now==fresh
sha=hashlib.sha256((R/'builds/b4/b4.bit').read_bytes()).hexdigest()
assert sha==now['bitstream_sha256']=='4e406f1280d3cf5cabf43d001278ef3b807a9ce4a7d036445122f5636e3d18a9'
changed=[k for k,v in before['target_column_frames_sha256'].items() if now['target_column_frames_sha256'][k]!=v]
assert len(changed)==22
assert [r['value'] for r in before['addresses']]==[r['value'] for r in now['addresses']]
assert now['natural_build_mismatches']==[]
A=R/'evidence/b4/unit_b4q_integration_2026_10_27/owner_review_3723b91_HOLD';P=R/'build/wip/owner_review_3723b91_2026_10_27';checks=0
for l in (A/'SHA256SUMS').read_text().splitlines():
 h,p=l.split(None,1);p=p.lstrip('* ');assert hashlib.sha256((A/p).read_bytes()).hexdigest()==h
 assert (A/p).read_bytes()==(P/p).read_bytes();checks+=1
assert (A/'SHA256SUMS').read_bytes()==(P/'SHA256SUMS').read_bytes()
assert checks==63
assert git('status','--porcelain','--untracked-files=all')==b''
assert subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=C)==b''
r={'reviewed_tip':git('rev-parse','HEAD').decode().strip(),'protected_diff':diff,'manifest_regenerated_matches_current':True,'retained_before_manifest_equals_history':True,'carrier_bitstream_sha256':sha,'changed_of_36_frame_hashes':len(changed),'address_values_unchanged':21,'natural_build_mismatches':[],'copied_previous_review_payloads_equal':checks,'canonical_and_snapshot_tracked_trees_clean':True}
(O/'scope_checks.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
