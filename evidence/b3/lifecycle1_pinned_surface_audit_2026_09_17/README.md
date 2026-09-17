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
