# B3 lifecycle 1, unit 1 — pinned-surface audit evidence (2026-09-17)

Document: `docs/b3_lifecycle1_pinned_surface_audit_2026_09_17.md`. Base `73b68d7`, branch `b3-lifecycle-1`.
Host-only; nothing pinned by B1 or B2 was written; every mutation was made in a throwaway detached
worktree under the session scratch directory and removed.

| file | what |
|---|---|
| `verify_baseline.json` | the production S3 verify on `main` at `73b68d7`, tree clean, before anything was written: S3 / true / null / `aec84514…` |
| `inventory_dependency_scan.py` → `inventory.json` | every B3 file at the base: digest, tracked?, in the B2 table?, which B2 globs match, imports of B1/B2 modules, committed reads, git history, simulation provenance; B2 → B3 references by line; the 13 gitignored files the B1 table pins; the two untracked image binaries |
| `probe_pinned_surface.py` → `results.json`, `probe.log` | 20 throwaway-worktree probes (control, 2 fresh-checkout controls with nothing / only the images restored, 3 modify, 3 delete, 2 add-under-glob, 2 on `evidence/b3/sim/`, 7 negative controls); per probe: worktree HEAD, the restored non-tracked inputs by digest, the mutation, the worktree's porcelain status, the verify outcome (stage/qualified/refusal or exception type and text), the `host/b2_pins.py` CLI exit; main-tree state before and after |
| `verify_closing.json` | the same verify on the main tree after the document and this directory were written |

Re-run (from the repository root, on a clean tree at `73b68d7`; ~40 s; needs the working tree's
`firmware/*/bsp/out/` and `vivado/carrier/generated/` gitignored files, which every probe copies in):

    python3 -B evidence/b3/lifecycle1_pinned_surface_audit_2026_09_17/inventory_dependency_scan.py
    python3 -B evidence/b3/lifecycle1_pinned_surface_audit_2026_09_17/probe_pinned_surface.py --scratch <scratch dir>

## v1.1 follow-up (the owner's four P2s on `c648d6e`)

| file | what |
|---|---|
| `glob_and_discovery_probe.py` → `glob_and_discovery.json` | in a throwaway worktree of the base: `Path.glob("b3/**")` lists directories only, `b3/**/*` filtered to regular files reaches depth 1, 2 and 4; `unittest discover -s b3/tests` runs a sentinel test without package files, `-s b3/tests -t .` fails (`Start directory is not importable`) without `__init__.py` files and works with them, B2's `-s tests` discovery never sees `b3/`, and removing the sentinel drops the count to 0 (the removal control) |
| `verify_closing_v1.1.json`, `verify_closing_v1.2.json` | the production S3 verify on the tree after each follow-up was written |

P-F1's archive lives in `evidence/b2/b2_completion_inputs_2026-09-17/` (see its README).
