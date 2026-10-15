# B2 completion inputs — the 15 non-tracked files the B2 S3 verify needs at `73b68d7`

Found by the B3 lifecycle-1 pinned-surface audit (`docs/b3_lifecycle1_pinned_surface_audit_2026_09_17.md`
P-F1): a fresh checkout of the B2 completion commit refuses to verify until 15 gitignored files are
restored from this workstation's working tree — the two image binaries the B1 and B2 manifests pin
(`firmware/b1/bsp/out/b1_app.bin`, `firmware/b2/bsp/out/b2_app.bin`) and the 13 Vivado files the
B1 pin table's glob `vivado/carrier/generated/*` captured (`*.jou`, `*.log`, `clockInfo.txt`).
Until this unit they existed nowhere else. Nothing pinned was changed: this directory is additive,
and every archived file hashes to the digest the frozen tables / manifests already carry.

| file | what |
|---|---|
| `inputs.tar.zst` | the 15 files, relative paths, deterministic ustar (sorted, mtime 0, mode 0644) + zstd -19; 666 808 bytes in, 99 325 bytes out; the producer builds it byte-identically on repeat |
| `archive.json` | `b2_completion_inputs` 1.0.0: base, the expected B2 manifest and pin-table digests, every member's bytes / sha256 / why it is needed / the pin it must equal, the archive's sha256 |
| `make_archive.py` | the producer (reads the working tree; refuses unless HEAD descends from the base, the B2 manifest and table are the completion-state documents, the B1 manifest and B1 table are the ones those two pin by content, and every file hashes to its pin) |
| `restore_verify.py` | the consumer: in a fresh detached checkout of the base, refuse to overwrite, restore exactly the listed members, verify each by size and digest before and after writing, then run the production B2 verify and require S3 / true / null / `aec84514…` / table `82a5f2fb…`; named refusals exit 2, anything unexpected is an INTERNAL ERROR exit 3 |
| `controls.py` → `control_runs/` | the positive run under `env -i PATH=…` in a fresh checkout, and the negative controls (member missing / one byte changed, each with the original manifest and with the outer digest patched; a target already holding the files; a target not at the base); then the producer's controls in a restored checkout: rebuilds the archive byte-identically; refuses a member drifted together with a B1 table re-pinned to it; refuses the B1 image drifted together with a B1 manifest re-pinned to it. `control_runs/summary.json`. (Not `runs/`: `.gitignore:6` ignores that name and the evidence guard refuses ignored evidence.) |

Restore into a fresh checkout (needs `zstd`, and the pinned `zynq-psoracle` checkout for the verify):

    git worktree add --detach /tmp/b2check 73b68d7
    python3 -B evidence/b2/b2_completion_inputs_2026-09-17/restore_verify.py --target /tmp/b2check
