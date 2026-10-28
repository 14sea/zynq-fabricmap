from pathlib import Path
import subprocess,hashlib,json
R=Path('/home/test/zynq_fabricmap');C=Path('/tmp/owner_b4q_round3_ut4zzex4');O=R/'build/wip/owner_review_a41f573_2026_10_27'
g=lambda *a:subprocess.check_output(['git','-C',str(R),*a])
A=R/'evidence/b4/unit_b4q_integration_2026_10_27/owner_review_6f62b6a_HOLD';P=R/'build/wip/owner_review_6f62b6a_2026_10_27'
n=0
for l in (A/'SHA256SUMS').read_text().splitlines():
 h,p=l.split(None,1);p=p.lstrip('* ')
 assert hashlib.sha256((A/p).read_bytes()).hexdigest()==h
 assert (A/p).read_bytes()==(P/p).read_bytes();n+=1
assert n==88 and (A/'SHA256SUMS').read_bytes()==(P/'SHA256SUMS').read_bytes()
protected=['b4/host','b4/schemas','b4/hypothesis','rtl','builds','vivado','tb','sim','b3','firmware/b1','firmware/b2','evidence/b4/sim','evidence/b4/gate','evidence/b4/gonogo','gate_runs','manifests']
diff=g('diff','--name-status','dd8a7b9','HEAD','--',*protected).decode().splitlines();assert diff==['M\tbuilds/b4/b4_carrier_manifest.json']
assert g('diff','--name-only','6f62b6a','HEAD','--',*protected)==b''
bitsha=hashlib.sha256((R/'builds/b4/b4.bit').read_bytes()).hexdigest();mfsha=hashlib.sha256((R/'builds/b4/b4_carrier_manifest.json').read_bytes()).hexdigest()
assert bitsha=='4e406f1280d3cf5cabf43d001278ef3b807a9ce4a7d036445122f5636e3d18a9'
assert mfsha=='6e1cab868f5ef63e1ea99f81a25c9b66e1bba0db294f1e55286e3e6379bc79b0'
files=json.loads((C/'b4/IMPORT.json').read_bytes())['files']
for p,entry in files.items():assert hashlib.sha256((C/p).read_bytes()).hexdigest()==entry['sha256'],p
assert len(files)==59
assert g('status','--porcelain','--untracked-files=all')==b''
assert subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=C)==b''
r={'reviewed_tip':g('rev-parse','HEAD').decode().strip(),'copied_previous_review_payloads_equal':n,'protected_diff_from_base':diff,'protected_diff_from_previous_review':[],'carrier_bitstream_sha256':bitsha,'carrier_manifest_sha256':mfsha,'snapshot_IMPORT_file_hashes_match':59,'canonical_and_snapshot_clean':True}
(O/'scope_checks.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
