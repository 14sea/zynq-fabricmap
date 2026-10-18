# B4 pre-work, unit 2b-4a — the host-only exploration harness (2026-10-18; the owner's ruling of 2026-10-18 on the scope draft, archived here as `owner_ruling_2b4a_full_2026_10_18.md`; the scope draft as `scope_draft_2026_10_18.md`)

**Authorised:** three implementation commits A / B / C, reviewed as one batch (ruling §2 item 8); mechanics tests on the
exposed fixture seeds only (§2 items 4 and 7). **Not authorised and not done:** the S = 32 exploration under `b4-sim-1`,
the formal gate, push / merge, board work. No arm advantage is read, no seed is scanned, no K result is computed.

## Commit A — seeds / controls / snapshot

| deliverable | what it holds | where it is tested |
|---|---|---|
| `b4/host/b4_seeds.py` | the anchor formula (label beside the anchor; `\|` in a label refused); the 38 historical sources of §9.2 read against their digests through **typed field paths**; B2's `EXCLUDED_SEEDS` copied and held to the pinned file's text; `B4_EXPOSED_VALUES`; the `evidence/b4/sim/` registry (every archived `seeds.json`; a run directory without a valid record is refused); one pooled set; `pair_seeds` by copy | `test_b4_seeds.py` (18): the formula by hand on a fake anchor; refusals; the copy equal to B2's original by read-only import; both positions screened; a coinciding draw skipped (a scripted generator); typed refusals (bool, float, missing, empty); every source reads and hashes; the pool's composition; a re-hashed / missing source refused by name; the `FIELDS` table equal to the architecture's §9.2 table (paths, digests, field roots, exposed values); the registry on a hermetic tree (complete / init-failed / damaged / missing / stray) |
| `b4/host/b4_controls.py` | `x_control_seed` / `d_shuffle_seed`; `f_frozen_view` (replay first; the base + 21 probes re-ingested; every record held; the formal source only); `d_view` (the permutation reconstructed and checked; the residual reported; identity kept); `verify_d_view` | `test_b4_controls.py` (10): both formulas by hand; bools / out-of-range refused; the rebuilt view equals the record and can be handed to the frozen arm; O / given-view / other-task / fixture-source / incomplete / tampered results refused by name; D's parent kept; identity shuffle reported, never redrawn; the permutation is `shuffled_view`'s for three seeds |
| `b4/host/b4_snapshot.py` | K7 from the ledger alone (no engine / `RunResult` change): `rebuild` under each arm's rule; `prefix_states` (arm O, exactly `B + 1` records); `recompute_findings` (the whole ledger and the final fields); `arm_states` (reported beside K7 (b), never in its place) | `test_b4_snapshot.py` (10): a HAND q-grid ledger with versions and states derived by hand; a tampered middle record found where it lies; every arm mode rebuilds clean on real runs; O's prefix at 8 / 16 / 24 equals the record's map at that evaluation, the holdout never in a prefix; an F whose search pretends to learn; X with the wrong π or fed the true genome; a moving given view; an injected control failure that does not reproduce |

**A note the record must carry.** While smoke-testing `b4_seeds` before the tests were written, the author printed the
master value of the formal label `b4-sim-1` once (the formula applied to the formal hypothesis digest). No pair was
drawn from it, nothing was derived from it, and it is not recorded anywhere in the tree; the tests use fake anchors
only. It is reported here because the ruling asks that formal values not be generated for testing or value-picking.

**The architecture (v0.1.14):** the owner's P3 (the sign test's H1 in its conditional form, all ties → p = 1) applied; §9.2
names the typed reading and the rule that every archived set joins the pool; the two manifests' `seeds.pairs` fields
listed as seed-bearing; the v0.1.13a note now states that its K9 (b) rule is a decision-policy addition the owner accepted.

(Commits B and C, the full-suite run, the mutants and the IMPORT check are appended below when delivered.)
