#!/usr/bin/env python3
"""Independent read-only check of this checkout's B2 build evidence and named inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / 'host'))
import b2_build_evidence as be
import b1_pins

ev = json.loads((R / 'evidence/b2/build_evidence.json').read_text())
fresh = be.bsp_inputs()  # derives paths from the build configuration, not ev
assert fresh == ev['bsp_inputs']
assert be.verify_findings(ev, R) == []
assert set(ev['sources']) == set(be.APP_SOURCES)
for name, digest in ev['sources'].items():
    assert be.sha(be.FW / name) == digest
    committed = subprocess.check_output(['git', '-C', str(R), 'show', ev['git']['head'] + ':firmware/b2/' + name])
    assert hashlib.sha256(committed).hexdigest() == digest
assert Path(ev['toolchain']['path']).resolve() == be.TC.resolve()
assert ev['toolchain']['gcc_sha256'] == be.sha(be.TC / 'bin/arm-none-eabi-gcc')
for build in ev['reproducibility']['builds']:
    assert build['bin_sha256'] == be.sha(be.OUT / 'b2_app.bin')
    assert build['elf_sha256'] == be.sha(be.OUT / 'b2_app.elf')
assert ev['git']['worktree_dirty'] is False
b1_pins.verify()
print(json.dumps({
    'reviewed_head': subprocess.check_output(['git', '-C', str(R), 'rev-parse', 'HEAD'], text=True).strip(),
    'evidence_source_head': ev['git']['head'], 'image': ev['image'],
    'live_bsp_inputs_equal_evidence': True,
    'all_source_hashes_match_live_and_recorded_commit': True,
    'source_inventory_equals_required_inputs': True,
    'compiler_path_and_hash_match_build_configuration': True,
    'two_bin_and_elf_digests_match_actual_files': True,
    'translation_units': len(fresh['translation_units']), 'headers': len(fresh['headers']),
    'runtime_objects': len(fresh['toolchain_objects']), 'b1_pins_verify': True,
    'b1_manifest_sha256': be.sha(R / 'manifests/b1_manifest.json'),
    'findings': [], 'arm_rebuild_performed': False}, indent=2))
