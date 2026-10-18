#!/usr/bin/env python3
"""B4 — the MACHINE TABLE of the thresholds docs/b4_architecture.md section 9 fixed in advance (unit 2b-3, the owner's rulings
of 2026-10-18), pinned field by field to the document's text by `b4/tests/test_b4_thresholds.py` (the owner's ruling on
unit 2b-4a, section 3.4: the manifest's constants and the architecture's thresholds are held consistent by a static test,
never by eye). The exploration harness lists these values BESIDE its numbers for reference; nothing here is a verdict and
nothing in the harness computes one. A change to a number here is a change to section 9 — a revision with its reason,
authorised separately; this table never follows a run.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from b4_ff_hypothesis import HYPOTHESIS_SHA256  # noqa: E402

ARCHITECTURE_REL = "docs/b4_architecture.md"
ARCHITECTURE_SECTION = "9 (v0.1.15)"

GRID = (8, 16, 24, 32, 48, 64, 96, 128, 192, 256)
B_MAX = 256
LAMBDA = 8
ADDRESSES = 21
PROBES = 21

THRESHOLDS = {
    "source": f"{ARCHITECTURE_REL} section {ARCHITECTURE_SECTION}, fixed before any exploration or gate run",
    "standing": ("engineering research criteria fixed in advance; no number is claimed to be empirically guaranteed, statistically "
                 "calibrated or valid for silicon; listed beside exploration values for reference only — never a gate verdict here"),
    "grid": list(GRID), "B_max": B_MAX, "lambda": LAMBDA, "addresses": ADDRESSES, "probes_per_F_run": PROBES,
    "K1": {"omega_best_p95_lt": 64, "percentile": 95, "medians": "median_r(best_R(B)) > median_r(base_r), two medians compared"},
    "K2": {"population_variance_gt": 0, "x_minus_r_nonrejection_min": 0.90, "bootstrap_experiments": 1000, "alpha": 0.05, "bootstrap_seed": 7,
           "rejection": "p <= 0.05", "ties": "excluded from the sign test's n, kept in the resampled population"},
    "K3": {"ratio_max": 0.10, "alpha": 0.05, "sign_test_h1": "P(control - R > 0 | control - R != 0) > 1/2",
           "denominators": "mean(F - R) > 0 and mean(O - R) > 0 required; a non-positive denominator is not readable as satisfied"},
    "K4": {"omega_median_max": 57.6, "omega_median_rule": "0.90 * 64", "f_over_omega_min": 0.50},
    "K5": {"cohen_d_min": 0.5, "alpha": 0.05, "power_min": 0.90, "bootstrap_experiments": 1000, "bootstrap_seed_rule": "random.Random(1 + N)",
           "n_scan": "every integer from 8 to S, ascending, no bisection", "n_min": 8, "cap_search_evaluations": 4000, "cap_formula": "N x 3 x B*"},
    "K6": {"S_gate": 200, "N_min": 8, "note": "S is the number planned, never the number that completed"},
    "K7": {"recomputation_mismatches": 0, "o_prefix_median_not_unknown_min": 11, "of_addresses": 21, "prefix": "arm O's first B* + 1 ledger records (base + B* search)"},
    "K8": {"replay": "no finding on every executed run; a broken tool contract is invalid under section 9.1"},
    "K9": {"seeds_with_all_seven_positive_controls_min": 0.90, "median_coverage_per_semantic_min": 0.50,
           "median_population": "all S seeds; one not-assessable seed makes the semantic's median not assessable",
           "panel": "section 9.3: 32 mode combinations x INIT/SRVAL all-0 / all-1 = 64 backgrounds", "semantics": 7},
    "K10": {"tau": 2, "interacting": "max|I| > 2 (exactly 2 is nonzero below threshold)", "interacting_seeds_over_S_min": 0.50,
            "pairs_per_background": 210, "backgrounds": 2, "background_salt": 0x4C0A4E55, "background_rule": "0 and Rng((seed ^ salt) & 0xffffffff).uniform(1 << 21), the first call"},
    "B_star": {"rule": "the smallest N(B) x 3 x B among budgets where K1 holds and N(B) exists; ties to the smaller budget",
               "no_eligible_budget": "the budget rule FAILS; B* and N are not invented (exploration: candidate B* / N are null with the reason)"},
    "delta2_F_shift": PROBES,
    "anchor": {"rule": "int.from_bytes(sha256(utf8(label + '|' + anchor))[:4], 'big'), the label passed beside the anchor",
               "hypothesis_sha256": HYPOTHESIS_SHA256, "gate_label": "b4-gate-1", "exploration_label": "b4-sim-1"},
    "controls": {"x_control_seed": "int.from_bytes(sha256('b4-x-control-1|<landscape_seed>|<operator_seed>')[:4], 'big')",
                 "d_shuffle_seed": "int.from_bytes(sha256('b4-d-control-1|<landscape_seed>|<operator_seed>')[:4], 'big')"},
}

# (table path, the text that must appear in the named section-9 row or paragraph) — the per-field pin the static test holds
PINS = (
    ("grid", "K-grid", "`G = {8, 16, 24, 32, 48, 64, 96, 128, 192, 256}`"), ("B_max", "K-grid", "`B_max = 256`"),
    ("K1.omega_best_p95_lt", "K1", "`percentile(best_Ω(B*), 95) < 64`"),
    ("K2.x_minus_r_nonrejection_min", "K2", "**≥ 90 %**"), ("K2.bootstrap_experiments", "K2", "1 000 bootstrap experiments"), ("K2.bootstrap_seed", "K2", "`random.Random(7)`"),
    ("K2.alpha", "K2", "α = 0.05"),
    ("K3.ratio_max", "K3", "≤ 0.10 · mean(F − R)"), ("K3.alpha", "K3", "`p > 0.05`"), ("K3.sign_test_h1", "K3", "P(control − R > 0 | control − R ≠ 0) > ½"),
    ("K4.omega_median_max", "K4", "≤ 0.90 · 64 = 57.6"), ("K4.f_over_omega_min", "K4", "≥ 0.50 · mean(Ω − R)"),
    ("K5.cohen_d_min", "K5", "**≥ 0.5**"), ("K5.power_min", "K5", "bootstrap power **≥ 0.90**"), ("K5.bootstrap_seed_rule", "K5", "`random.Random(1 + N)`"),
    ("K5.n_scan", "K5", "complete ascending scan over every integer from 8 to S"), ("K5.cap_search_evaluations", "K5", "`N × 3 × B* ≤ 4 000`"),
    ("K6.S_gate", "K6", "**S = 200**"), ("K6.N_min", "K6", "**N ≥ 8**"),
    ("K7.recomputation_mismatches", "K7", "**zero recomputation mismatches**"), ("K7.o_prefix_median_not_unknown_min", "K7", "≥ 11` of 21"),
    ("K9.seeds_with_all_seven_positive_controls_min", "K9", "**≥ 90 % of all S seeds**"), ("K9.median_coverage_per_semantic_min", "K9", "**≥ 0.50**"),
    ("K9.median_population", "K9", "if a semantic is not assessable for even one seed, its median is *not assessable*"),
    ("K10.tau", "K10", "τ = **2 fitness score units**"), ("K10.interacting", "K10", "**interacting** when `max|I| > 2`"), ("K10.interacting_seeds_over_S_min", "K10", "**interacting seeds / all S ≥ 0.50**"),
    ("K10.pairs_per_background", "K10", "**all 210 unordered pairs**"), ("K10.background_salt", "K10", "0x4C0A4E55"),
    ("anchor.hypothesis_sha256", "9.2", HYPOTHESIS_SHA256), ("anchor.gate_label", "9.2", "'b4-gate-1|'"), ("anchor.exploration_label", "9.2", "'b4-sim-1'"),
    ("controls.x_control_seed", "8", "sha256('b4-x-control-1|<landscape_seed>|<operator_seed>')"), ("controls.d_shuffle_seed", "8", "sha256('b4-d-control-1|<landscape_seed>|<operator_seed>')"),
    ("delta2_F_shift", "9-intro", "**21 probes, one per address of the slice's configuration-bit universe**"),
)


def lookup(path: str):
    node = THRESHOLDS
    for k in path.split("."):
        node = node[k]
    return node
