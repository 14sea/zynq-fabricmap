# B4 exploration — b4-sim-3, S = 32 (2026-10-19): the run record and the owner's corrections

The batch itself is the archive `evidence/b4/sim/b4-sim-3_20261019T121833Z/` (committed unchanged in `5c08536`; nothing in
it is edited by this unit — its file set is bound by the archive verification). This directory holds the run record, the
key points of the owner's review of `5c08536` as relayed by the user (`owner_review_5c08536.md`, a 覆核重點摘錄 — an excerpt of
the review's key points, not the review copied unchanged; corrected on the owner's item 3 of the ruling on `00754d3`), the
owner's ruling on `00754d3` as relayed (`owner_ruling_00754d3.md`), and the corrected summary. Documents only.

## 1. The run

| item | value |
|---|---|
| authorisation | the user confirmed in session that this exploration was authorised by them (2026-10-19; verbatim: 「繼續探索是我授權的」); the owner's ruling of 2026-10-19 section 6 had made the run a separate execution authorisation; the owner's ruling on `00754d3` closes the authorisation question — no further proof is required |
| code tree | HEAD `933545a`, `git status --porcelain` empty |
| command | `python3 -B b4/host/b4_sim.py --label b4-sim-3 --seeds 32 --deadline-s 3600` (one worker; no smoke test before it) |
| pre-flight / report | 2026-10-19T12:18:33Z / 12:22:03Z |
| status / exit | complete / 0 |
| deadline record | 209.702 s of 3600, 52 715 checks, not expired |
| seeds | schema 1.2.0, master 3272749632, 32 pairs; pooled exclusion 2 159 values; the pinned receipt (66 values, sha256 68764bbc…) named and held |
| archive | 643 files, 186 MB |
| sim_report.json / seeds.json / manifest.json | sha256 `a7ab0aaa75a552d01d79ef865acd84d57f7ca2629b4be604e656ba95bc412c89` / `1a0d1e7b91132ed6814a9e369e23f2c55f28886448fa5efd55d722182f50b17d` / `b564bd9cf098b80b2a76ff9dbb4b2a3cd316baffc513a0a6071340c149c1f149` |
| b4_sim_verify.py (deep) | findings {}, clean true (the author's run; the owner's independent deep verify: exit 0, findings {}) |

## 2. The corrected summary — values beside the thresholds, NOT a gate verdict; S = 32 is never the formal S = 200

The owner's review of `5c08536` (its key points, section 0) named three errors in that commit's message and in the session summary. All three are
confirmed against `sim_report.json`; the corrected statements are below, the errors in section 3.

**K1.** eligibility true at all ten grid budgets (median best_R 36 … 42 over base 32; Ω best p95 41.45 … 46.45; reference < 64).

**K5 is on Δ1 = O − R** (`b4_sim.py` line 806 passes `delta1_O_minus_R` to `required_pairs_scan`; architecture section 9
names {Δ1_r}). F − R is a separate descriptive delta and plays no part in N.

| budget | O − R mean | d | sign-test p | F − R mean | d | K5 power over the scan N = 8 … 32 | power at N = 32 |
|---|---|---|---|---|---|---|---|
| 8 | −0.3438 | −0.174 | 0.965 | −0.7812 | −0.267 | 0.000 … 0.001 | 0.000 |
| 16 | −0.6562 | −0.321 | 0.994 | −0.4062 | −0.140 | 0.000 … 0.001 | 0.000 |
| 24 | −0.7812 | −0.310 | 0.975 | −0.3750 | −0.126 | 0.000 … 0.002 | 0.001 |
| 32 | −0.0312 | −0.012 | 0.500 | +0.0625 | +0.020 | 0.016 … 0.064 | 0.046 |
| 48 | +0.0625 | +0.027 | 0.598 | −0.1875 | −0.063 | 0.010 … 0.037 | 0.031 |
| 64 | −0.1875 | −0.083 | 0.798 | −0.1875 | −0.062 | 0.004 … 0.012 | 0.005 |
| 96 | −0.5625 | −0.256 | 0.979 | −0.3750 | −0.144 | 0.000 … 0.003 | 0.000 |
| 128 | −0.4062 | −0.197 | 0.942 | −0.7188 | −0.286 | 0.000 … 0.006 | 0.000 |
| 192 | −0.1250 | −0.064 | 0.598 | −0.2500 | −0.098 | 0.007 … 0.034 | 0.022 |
| 256 | −0.0625 | −0.029 | 0.895 | +0.0625 | +0.025 | 0.001 … 0.007 | 0.003 |

Over all budgets the K5 scan's power lies in 0.000 … 0.064; at N = 32 alone in 0.000 … 0.046 (reference ≥ 0.90, d ≥ 0.5).
N is null at every budget; no budget has both K1 eligibility and an N, so the budget rule's candidate B* does not exist on
this S — reported null with its reason, not invented (section 9.1: a complete valid batch with no solution is a result, not
a defect). The owner's review confirms B* = null is consistent with the data.

**K9.** fraction_of_S 1.0; no not-assessable seed. Per-semantic median coverage over all S (reference ≥ 0.50): ce_mode 1.0,
clock_mode 1.0, ff_init 1.0 (conditional on A8), sr_mode 1.0, storage_kind 1.0, **ff_srval 0.427083**, **sr_kind 0.5**.

**K10.** interacting 32 / 32 at τ = 2 (0 nonzero-below-threshold, 0 not assessable; reference ≥ 0.50).

**X − R** mean −1.03 … −0.28 across budgets (descriptive; K2 is the bootstrap non-rejection rule and is not computed here as a verdict).

## 3. The three errors in 5c08536's commit message and the session summary (the owner's review; confirmed)

| # | what 5c08536's message / the summary said | what the data say | how it happened |
|---|---|---|---|
| 1 | "F − R … so N is null" — K5 attributed to F − R | K5 is on Δ1 = O − R (code and section 9); in this S = 32 sample, Δ1 = O − R did not reach bootstrap power 0.90 at any N of the fixed scan N = 8 … 32 (d −0.321 … +0.027 descriptively), which is why N is null; F − R plays no part. No inference that the effect is absent, or that S = 200 would give the same, is drawn | the F − R row was read as the K5 input without checking which delta the scan takes |
| 2 | "K9 … per-semantic median coverage 1.0" | ff_srval 0.427083 and sr_kind 0.5; the other five 1.0 | the per-semantic block was read from an output truncated after ff_init |
| 3 | "K5's N scan 8 … 32 reaches power 0.001 … 0.007 at every budget" | over all budgets 0.000 … 0.064; at N = 32 alone 0.000 … 0.046 | budget 256's scan alone was generalised to every budget |

The commit message of `5c08536` is not rewritten (history kept); this file is the correction of record. The archive is
untouched. The observation reported with `5c08536` stands and is unchanged here: `b4_sim.py`'s STANDING string says
"v0.1.15 section 9" while the report's thresholds block and `b4_thresholds.ARCHITECTURE_SECTION` say v0.1.16.

## 4. The owner's ruling on 00754d3 and this follow-up (2026-10-19)

The owner's review of `00754d3` (`owner_ruling_00754d3.md`, as relayed): the numeric correction PASS; the ten budgets' table
values and the three archive digests checked and equal; the raw output unchanged; B* = null is a valid S = 32 exploration
result, neither a tool defect nor a formal gate verdict; the exploration delivery unit closes after three P3 document
corrections, which this follow-up carries: (1) section 2 and section 3 no longer say "O − R shows no effect" — the
statement is that Δ1 = O − R did not reach bootstrap power 0.90 at any N of the fixed scan 8 … 32 in this S = 32 sample, with
no inference about the effect's existence or about S = 200; (2) the authorisation row records the user's confirmation;
(3) the seven-line owner text is marked a 覆核重點摘錄 and the "copied unchanged" descriptions are corrected (the commit
message of `00754d3` still says "copied unchanged" and "shows no effect"; it is not rewritten, this file is the record).
The existing commits, the 643 raw files and the receipt are kept; no code changed, no test or exploration rerun.

## 5. What this does not claim

Nothing here is a gate result, a statement about silicon, or an authorisation. The formal gate, 2c / 2d, any b4-sim-4,
push / merge and board work remain unauthorised; a batch with no B* does not license another batch (ruling section 6).
