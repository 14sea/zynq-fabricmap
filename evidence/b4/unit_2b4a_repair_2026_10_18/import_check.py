"""Every entry of b4/IMPORT.json against the tree: file digest, base digest, copied-function digests, and that every file under b4/ (but the table) has an entry."""
import json, hashlib, pathlib, sys, inspect, subprocess
R = pathlib.Path('/home/test/zynq_fabricmap'); sys.path.insert(0, str(R / 'b4/host'))
d = json.loads((R / 'b4/IMPORT.json').read_text())
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
bad = []
for rel, e in d['files'].items():
    if not (R / rel).is_file(): bad.append(f"MISSING {rel}"); continue
    if sha(R / rel) != e['sha256']: bad.append(f"DIGEST {rel}")
    if 'base' in e and sha(R / e['base']) != e['base_sha256']: bad.append(f"BASE {rel} <- {e['base']}")
    if 'copied_functions' in e:
        import b4_gate_stats as gs
        for n, s in e['copied_functions'].items():
            if hashlib.sha256(inspect.getsource(getattr(gs, n)).encode()).hexdigest() != s: bad.append(f"FUNC {rel}.{n}")
tracked = subprocess.run(['git', '-C', str(R), 'ls-files', 'b4'], capture_output=True, text=True).stdout.split()
untabled = [t for t in tracked if t != 'b4/IMPORT.json' and t not in d['files'] and '__pycache__' not in t]
print(f"HEAD {subprocess.run(['git','-C',str(R),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()}")
print(f"{len(d['files'])} entries; file digests, base digests and copied-function digests all equal: {not bad}")
for b in bad: print("  ", b)
print(f"tracked files under b4/ without an entry: {untabled or 'none'}")
