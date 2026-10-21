from pathlib import Path
import subprocess,json,datetime,time
R=Path('/home/test/zynq_fabricmap');D=Path(__file__).resolve().parent
jobs=[('sim_verify',['python3','-B','b4/host/b4_sim_verify.py','evidence/b4/sim/b4-sim-4_20261021T065339Z']),('gonogo_verify',['python3','-B','b4/host/b4_gonogo.py','verify','evidence/b4/gonogo/b4-sim-4_20261021T065857Z'])]
results=[]
for name,cmd in jobs:
 started=datetime.datetime.now(datetime.timezone.utc).isoformat();t=time.monotonic()
 print('START',name,started,flush=True)
 p=subprocess.run(cmd,cwd=R,text=True,capture_output=True)
 elapsed=time.monotonic()-t
 (D/(name+'.txt')).write_text('HEAD '+subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()+'\nCMD '+' '.join(cmd)+'\nSTART_UTC '+started+'\n'+p.stdout+'\nSTDERR\n'+p.stderr+'\nEXIT '+str(p.returncode)+'\nELAPSED_S '+str(elapsed)+'\n')
 results.append({'name':name,'command':cmd,'start_utc':started,'elapsed_s':elapsed,'exit':p.returncode,'result':json.loads(p.stdout)})
 print('END',name,'exit',p.returncode,'elapsed',elapsed,flush=True)
 (D/'verifiers.json').write_text(json.dumps(results,indent=2)+'\n')
 if p.returncode: raise SystemExit(p.returncode)
