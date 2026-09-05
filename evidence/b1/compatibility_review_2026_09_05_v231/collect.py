from pathlib import Path
import hashlib,json,re,subprocess,sys
R=Path('/home/test/zynq_fabricmap'); P=Path('/home/test/zynq_psoracle'); D=Path('/tmp/b1_v231_compat')
sys.path.insert(0,str(R/'host'))
import b1_pins,claimb_r1p_instrument as inst,b1_build_evidence as b
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(args): return subprocess.check_output([str(x) for x in args],text=True)
def dump(name,obj): (D/name).write_text(json.dumps(obj,indent=2)+'\n')
pairs={'app':(P/'firmware/p3_app.c',R/'firmware/b1/b1_app.c'),'wire':(P/'firmware/p3_wire.c',R/'firmware/b1/b1_wire.c'),'wire_header':(P/'firmware/p3_wire.h',R/'firmware/b1/b1_wire.h')}
for n in ('arm_gate','axil','core','top'): pairs[n]=(P/f'rtl/p3_{n}.v',R/f'rtl/b1/b1_{n}.v')
for n,(a,z) in pairs.items():
 p=subprocess.run(['git','diff','--no-index',str(a),str(z)],capture_output=True,text=True)
 assert p.returncode in (0,1)
 (D/f'{n}.diff').write_text(p.stdout)
def funcs(s):
 return {m.group(1):m.group(0) for m in re.finditer(r'^(?:static )?[\w *]+?\b(\w+)\([^;{}]*\)\n\{.*?^\}',s,re.M|re.S)}
a=funcs(pairs['app'][0].read_text());z=funcs(pairs['app'][1].read_text())
f={'unchanged':sorted(k for k in a.keys()&z.keys() if a[k]==z[k]),'changed':sorted(k for k in a.keys()&z.keys() if a[k]!=z[k]),'new':sorted(z.keys()-a.keys()),'removed':sorted(a.keys()-z.keys())}
dump('function_diff.json',f);print('Functions', {k:len(v) for k,v in f.items()},f['changed'],f['new'])
old=Path('evidence/b1/compatibility_review_2026_09_05/function_diff.json')
assert set(json.loads(old.read_text())['unchanged'])==set(f['unchanged'])
imports=json.loads((R/'firmware/b1/IMPORT.json').read_text())
for p,v in imports['files'].items():
 assert h(P/p)==v['sha256'],p
 if v.get('copied_to'): assert h(R/v['copied_to'])==v['sha256']
m=json.loads((R/'manifests/b1_manifest.json').read_text());e=json.loads((R/'evidence/b1/build_evidence.json').read_text())
assert h(R/m['image']['path'])==m['image']['sha256']==e['image']['sha256']
assert h(b.OUT/'b1_app.elf')==m['image']['elf_sha256']==e['image']['elf_sha256']
assert h(R/'builds/b1/b1.bit')==m['carrier']['bitstream_sha256']
assert h(R/'evidence/b1/build_evidence.json')==m['image']['build_evidence']['sha256']
for p,v in e['sources'].items(): assert h(b.FW/p)==v,p
for group in ('headers','translation_units'):
 for p,v in e['bsp_inputs'][group].items(): assert h(p)==v,p
for v in e['bsp_inputs']['toolchain_objects'].values(): assert h(v['path'])==v['sha256']
assert e['reproducibility']['builds']==[m['image']['sha256']]*2
r=json.loads((R/'evidence/b1/tests/test_report_2026-09-05T191204Z.json').read_text())
for p,v in r['artifacts_sha256'].items(): assert h(R/p)==v,p
meta={'reviewed_head':run(['git','rev-parse','HEAD']).strip(),'origin_main':run(['git','rev-parse','origin/main']).strip(),'manifest_sha256':h(R/'manifests/b1_manifest.json'),'image':m['image'],'carrier_sha256':h(R/'builds/b1/b1.bit'),'fabricmap_pins':b1_pins.verify(),'instrument':inst.verify(),'worktree_before_artifacts':run(['git','status','--porcelain']),'clean_suite_report':r,'freeze':m['prereg'],'qualification':m['carrier']}
dump('review_metadata.json',meta)
files={str(p.relative_to(R)) if p.is_relative_to(R) else str(p):h(p) for pair in pairs.values() for p in pair}
for p in ('firmware/b1/b1_orch.c','firmware/b1/b1_carto.c','firmware/b1/p3_data.h','firmware/b1/bsp/lscript.ld','vivado/b1/build_b1.tcl','builds/b1/b1_build.json','builds/b1/post_route_util.rpt','builds/b1/isolation.txt','tb/b1/hostapp/hostapp.c','tests/test_b1_hostapp.py','docs/b1_package.md'):files[p]=h(R/p)
dump('review_inputs_sha256.json',files)
cc=b.TC/'bin/arm-none-eabi-gcc'
flags=['-mcpu=cortex-a9','-mfpu=vfpv3','-mfloat-abi=hard','-std=c99','-O2','-g','-Wall','-Wextra','-ffreestanding','-ffunction-sections','-fdata-sections','-fstack-usage',f'-I{b.FW}/bsp/include']+[f'-I{b.SA}/{s}' for s in ('common','arm/common','arm/common/gcc','arm/cortexa9','arm/cortexa9/gcc')]+[f'-I{b.WD}']
dump('stack_compile_flags.json',[str(cc),*flags])
for src in ('b1_app.c','p3_derive.c','b1_carto.c','b1_orch.c','b1_wire.c','p3_rectx.c','p3_pull.c'):
 subprocess.run([str(cc),*flags,'-c',str(b.FW/src),'-o',str(D/(src+'.o'))],check=True)
stack=[]
for p in D.glob('*.su'):
 for line in p.read_text().splitlines():
  name,size,kind=line.split('\t');stack.append([int(size),name,kind])
dump('stack_usage.json',sorted(stack,reverse=True))
elf=b.OUT/'b1_app.elf'
(D/'elf_symbols.txt').write_text(run([b.TC/'bin/arm-none-eabi-nm','-S','--size-sort',elf]))
(D/'elf_layout.txt').write_text(run([b.TC/'bin/arm-none-eabi-nm','-n',elf]))
(D/'elf_size.txt').write_text(run([b.TC/'bin/arm-none-eabi-size',elf]))
print('Stack largest',sorted(stack,reverse=True)[:7]);print('Hashes and pins OK')
