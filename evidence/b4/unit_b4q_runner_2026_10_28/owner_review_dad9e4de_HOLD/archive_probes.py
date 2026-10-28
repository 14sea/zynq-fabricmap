"""Fresh-process verification of copied fixture archives; canonical tracked evidence is untouched."""
import json,sys,shutil,subprocess
from pathlib import Path
root=Path(sys.argv[1]).resolve(); output=Path(sys.argv[2]).resolve()
source=root/'evidence/b4/unit_b4q_runner_2026_10_28/e2e_runner/valid'
work=root/'build/owner_archive_probes';work.mkdir(parents=True,exist_ok=True)
summary={}
def dump(p,x):p.write_text(json.dumps(x,indent=1)+'\n')
for case in ['baseline','missing_boot_evidence','wrong_load_witness','wrong_page_witness','fake_control_plane_stop','board_kind']:
    p=work/case;shutil.copytree(source,p)
    m=json.loads((p/'manifest.json').read_text());u=json.loads((p/'uboot.json').read_text())
    if case=='missing_boot_evidence':
        for n in ['uboot.json','raw/console.bin','raw/console_tx.bin']:(p/n).unlink()
    elif case=='wrong_load_witness':
        for r in [m['transport']['runner'],u]:r['load_witness'].update(host_crc32='11111111',uboot_crc32='22222222',equal=True)
        dump(p/'uboot.json',u)
    elif case=='wrong_page_witness':
        for r in [m['transport']['runner'],u]:r['page_witness']['read_back'][0]='00000000';r['page_witness']['equal']=True
        dump(p/'uboot.json',u)
    elif case=='fake_control_plane_stop':
        m['records']=[];m['transport']['runner']['stops']=[{'why':'claimed before go, contradicted by retained raw bytes'}]
        dump(p/'session_open.json',None)
    elif case=='board_kind':
        m['transport']['kind']='uart-board';m['transport']['runner']['kind']='uart-board';m['emulated']=False
    dump(p/'manifest.json',m)
    target=output/(case+'.json')
    run=subprocess.run([sys.executable,'-B',str(root/'host/b4q_verify.py'),str(p),'--json',str(target)],cwd=root,text=True,capture_output=True)
    (output/(case+'.txt')).write_text(run.stdout+run.stderr)
    report=json.loads(target.read_text());summary[case]={'exit':run.returncode,**{k:report.get(k) for k in ['clean','agree','refused','control_plane_stop','verifier_error']}}
    if case=='fake_control_plane_stop':
        raw=(p/'raw/console.bin').read_bytes();summary[case]['retained_tx_dirs']=len(list(p.glob('tx_*')));summary[case]['raw_has_go']=b'go 02000000' in raw
print(json.dumps(summary,indent=2))
