"""Section 5.3: after the commit, the committed bytes against the files the verifiers read, by Git-blob digest.
git ls-tree -r <commit> for the two directories versus git hash-object of every file on disk under them."""
import subprocess, sys, pathlib, datetime
R = pathlib.Path('/home/test/zynq_fabricmap'); commit = sys.argv[1]
dirs = ['evidence/b4/sim/b4-gate-1_20261020T102526Z', 'evidence/b4/gate/b4-gate-1_20261020T102526Z']
git = lambda *a: subprocess.run(['git', '-C', str(R), *a], capture_output=True, text=True, check=True).stdout
print('UTC', datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'commit', git('rev-parse', commit).strip())
tree = {}
for line in git('ls-tree', '-r', commit, '--', *dirs).splitlines():
    meta, path = line.split('\t', 1); mode, typ, blob = meta.split()
    tree[path] = blob
disk = sorted(str(p.relative_to(R)) for d in dirs for p in (R / d).rglob('*') if p.is_file())
hashed = git('hash-object', '--stdin-paths', input='\n'.join(disk) + '\n') if False else None
out = subprocess.run(['git', '-C', str(R), 'hash-object', '--stdin-paths'], input='\n'.join(disk) + '\n', capture_output=True, text=True, check=True).stdout.split()
ondisk = dict(zip(disk, out))
only_tree = sorted(set(tree) - set(ondisk)); only_disk = sorted(set(ondisk) - set(tree))
diff = sorted(p for p in tree if p in ondisk and tree[p] != ondisk[p])
print(f'committed blobs {len(tree)}; files on disk {len(ondisk)}; equal {sum(1 for p in tree if ondisk.get(p) == tree[p])}')
print(f'only in commit {len(only_tree)}; only on disk {len(only_disk)}; digest differs {len(diff)}')
for p in only_tree[:20]: print('  only in commit', p)
for p in only_disk[:20]: print('  only on disk', p)
for p in diff[:20]: print('  differs', p, tree[p], ondisk[p])
ok = not only_tree and not only_disk and not diff
print('RESULT', 'EQUAL — the committed bytes are the verified files; no second deep-verification round' if ok else 'NOT EQUAL — the verification must be repeated')
sys.exit(0 if ok else 1)
