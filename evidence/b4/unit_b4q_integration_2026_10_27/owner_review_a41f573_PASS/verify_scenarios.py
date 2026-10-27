from pathlib import Path
import subprocess,json,sys
C=Path('/tmp/owner_b4q_round3_ut4zzex4');O=Path('/home/test/zynq_fabricmap/build/wip/owner_review_a41f573_2026_10_27')
out=[]
for rootname,root in [('submitted',C/'evidence/b4/unit_b4q_integration_2026_10_27/e2e'),('regenerated',C/'build/owner_e2e')]:
 for d in sorted(p for p in root.iterdir() if p.is_dir()):
  p=subprocess.run([sys.executable,'-B',str(C/'host/b4q_verify.py'),str(d),'--json',str(O/(rootname+'_'+d.name+'.json'))],capture_output=True,text=True)
  (O/(rootname+'_'+d.name+'.txt')).write_text(p.stdout+p.stderr)
  j=json.loads((O/(rootname+'_'+d.name+'.json')).read_bytes()) if (O/(rootname+'_'+d.name+'.json')).exists() else {}
  out.append({'source':rootname,'scenario':d.name,'exit':p.returncode,'clean':j.get('clean'),'agree':j.get('agree')})
(O/'scenario_verifications.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=1))
