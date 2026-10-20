# Read-only aggregation record for the B4 protocol-revision draft (2026-10-20)

**Standing (the owner's D3 on the v0.1 draft):** the scratchpad scripts went beyond the literal "no programs" of the drafting
authorisation; the owner accepted them as a read-only post-hoc analysis of archived data (no new observation, no seed derivation,
nothing that touches gate-1's verdict) and asked that the scripts, their complete outputs and their sources be kept, not deleted and
not re-run as new experiments. This directory is that record. It is ignored (`build/`), not committed; a later documents commit may
archive it with its source named.

**Source bytes:** `evidence/b4/sim/b4-gate-1_20261020T102526Z/pair_{000..199}/{curves.json,k9.json,k7.json,arm_O.result.json}` as
committed in `5070967` (Git-blob digest comparison 4 005 / 4 005 equal, `evidence/b4/unit_gate1_execution_2026_10_20/blob_digest_check.txt`).
The scripts read JSON only: no `b4_*` module is imported, nothing is replayed, no fitness recomputed, no task or stimulus generated,
`seeds.json` not read.

| file | what |
|---|---|
| `read_curves.py` / `read_curves.out.txt` | per-budget arm − R means and sign counts (Ω, F, O, X, D, A0), per-arm medians, best-of-seven at B = 256, holdout means |
| `read_k9.py` / `read_k9.out.txt` | ff_srval / sr_kind / sr_mode applicable pairs split by the g0 endpoint's sr_mode / sr_kind / storage_kind bits; per-seed fractions; SR-driven-only ff_srval |
| `read_k9_k7_extra.py` / `read_k9_k7_extra.out.txt` | the inline snippet of the session, reproduced verbatim: SR-driven-only per-seed fractions for sr_kind and ff_srval; K7 O not-unknown per budget; O group-move counts |
| `r5_git_readonly_checks.txt` | the git / file reads made for the historical re-verification procedure (section 5 of the v0.2 draft) |

The owner's independent re-aggregation (`build/wip/owner_review_b4_protocol_revision_scope_2026_10_20/readonly_aggregate.json`) agrees
with these outputs on every value it covers (Ω − R per budget, the B = 256 medians and maximum, the holdout means, the tied-low zeros,
7 360 / 12 800, the 103 seeds at exactly 0.5).
