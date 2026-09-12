"""Independent offline review of test-report parsing and provenance. No repository edits."""
import contextlib,hashlib,importlib.util,io,json,os,shutil,subprocess,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
R=Path('/home/test/zynq_fabricmap')
sys.path[:0]=[str(R/'host'),str(R/'tests')]
import b2_test_report as tr

d=Path(tempfile.mkdtemp(prefix='b2_report_review_'))
OK='....\n----------------------------------------------------------------------\nRan 4 tests in 1.000s\n\nOK\n'
logs={
 'valid_unittest_summary':OK,
 'missing_result':'Ran 1869 tests in 1.000s\n',
 'bare_failed':'Ran 1869 tests in 1.000s\n\nFAILED\n',
 'zero_tests':'Ran 0 tests in 0.000s\n\nOK\n',
 'truncated_count':'Ran 1869\n',
 'malformed_skips':'Ran 1869 tests in 1.000s\n\nOK (skipped=unknown)\n',
 'unparseable':'there is no unittest summary\n',
 'real_failure':'Ran 4 tests in 1.000s\n\nFAILED (failures=1)\n',
}
empty=d/'empty_tests';empty.mkdir()
empty_run=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(empty)],capture_output=True,text=True)
out={'reviewed_head':tr.git('rev-parse','HEAD'),'initial_dirty':tr.git('status','--porcelain'),'logs':{}}
out['actual_empty_discovery']={'returncode':empty_run.returncode,'log':empty_run.stdout+empty_run.stderr}
assert out['initial_dirty']=='','Run this review on the clean reviewed checkout'
for label,text in logs.items():
 lp=d/(label+'.log');lp.write_text(text)
 od=d/label
 cp=subprocess.run([sys.executable,str(R/'host/b2_test_report.py'),'--no-run','--log',str(lp),'--exit-status','1' if label=='real_failure' else '0','--out-dir',str(od)],cwd=R,capture_output=True,text=True)
 files=list(od.glob('test_report_*.json'))
 rep=json.loads(files[0].read_text())
 out['logs'][label]={'cli_rc':cp.returncode,**{k:rep[k] for k in ('clean_tree_proof','ran','result_line','skipped','failures','errors','scope','head_at_run','worktree_dirty')}}

# A valid captured log carries no run revision/dirty state or instrument snapshot.
# The no-run report nevertheless stamps today's clean HEAD and whole-suite scope.
out['imported_log_has_no_provenance']=out['logs']['valid_unittest_summary']
out['io_failures']={}
blocked=d/'regular_file';blocked.write_text('not a directory')
for label,lp,od in [('out_dir_is_a_file',d/'valid_unittest_summary.log',blocked),
                    ('missing_log',d/'not-present.log',d/'missing_log_out')]:
 cp=subprocess.run([sys.executable,str(R/'host/b2_test_report.py'),'--no-run','--log',str(lp),'--exit-status','0','--out-dir',str(od)],cwd=R,capture_output=True,text=True)
 out['io_failures'][label]={'returncode':cp.returncode,'stderr':cp.stderr}

# Exercise the normal CLI ordering with a controlled suite boundary and observable Git reads.
# Only environment history and suite execution are doubled, not report construction/pin checks.
state={'after':False};reads=[]
real_git=tr.git
def watched_git(*args,**kwargs):
 reads.append({'args':list(args),'after_suite':state['after'],'cwd':str(kwargs.get('cwd',R))})
 if kwargs.get('cwd',R)==R and args==('status','--porcelain') and not state['after']:
  return ' M host/b2_records.py'
 return real_git(*args,**kwargs)
def suite(focused=False):
 state['after']=True
 return 0,OK
with patch.object(tr,'git',side_effect=watched_git),patch.object(tr,'run_suite',side_effect=suite),contextlib.redirect_stdout(io.StringIO()):
 rc=tr.main(['--out-dir',str(d/'normal_order')])
rep=json.loads(next((d/'normal_order').glob('test_report_*.json')).read_text())
out['normal_run_order']={'initial_simulated_dirty':True,'git_reads_before_suite':sum(not x['after_suite'] for x in reads),
 'git_reads':reads,'cli_rc':rc,'clean_tree_proof':rep['clean_tree_proof'],'head_at_run':rep['head_at_run']}

# Mutate only the in-memory production predicate. Keep original checkout/table bytes.
source=(R/'host/b2_test_report.py').read_text()
old='rep["worktree_dirty"] is False and rep["skipped"] == 0'
assert source.count(old)==1
mutant=types.ModuleType('b2_test_report');mutant.__file__=str(R/'host/b2_test_report.py')
exec(compile(source.replace(old,'rep["skipped"] == 0'),mutant.__file__,'exec'),mutant.__dict__)
import test_b2_test_report as tests
with patch.object(tests,'tr',mutant):
 stream=io.StringIO()
 result=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
out['predicate_mutation']={'removed_condition':'worktree_dirty is False','tests_run':result.testsRun,
 'failures':len(result.failures),'errors':len(result.errors),'output':stream.getvalue()}

# Check the declared historical artifact digests against actual Git bytes at head_at_run.
arch=json.loads((R/'evidence/b2/tests/test_report_2026-09-12T083954Z.json').read_text())
matches={}
for name,digest in arch['artifacts_sha256'].items():
 cp=subprocess.run(['git','show',arch['head_at_run']+':'+name],cwd=R,capture_output=True)
 matches[name]=(cp.returncode!=0) if digest is None else (cp.returncode==0 and hashlib.sha256(cp.stdout).hexdigest()==digest)
out['archived_report_artifacts_at_declared_head']=matches
out['temporary_artifacts']=str(d)
(d/'review.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
