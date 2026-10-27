#!/usr/bin/env python3
"""B4 — the FORMAL GATE TOOL (unit 2b-4, the gate-tool half: the owner's ruling of 2026-10-19 "B4 gate tool versus production
execution", section 3). It JUDGES a batch archive of the harness (`b4_sim.py`, mode "gate") against the ten criteria of
docs/b4_architecture.md section 9 with the thresholds of `b4_thresholds.THRESHOLDS`, row by row — method, value, threshold,
status, reason — and writes the judgement as `gate_report.json` + `gate_report.md` in a gate directory under
evidence/b4/gate/, bound to the batch archive by digest.

    b4_gate.py run   --label b4-gate-2 --seeds 200 --deadline-s <s>     # the production run: the batch (b4_sim, mode gate) then the judgement
    b4_gate.py judge <batch_dir>                                         # the judgement of an existing production batch archive (runs nothing)

NOTHING IS AUTHORISED BY THIS FILE. The production run derives the gate's master and pairs (section 9.2, the pinned gate label
of protocol v0.2.0, b4-gate-2; b4-gate-1 is consumed by its records) — that derivation needs its own execution ruling. The CLI
has no fixture path, no allow-dirty, no other S than the planned 200 and no label but the pinned gate label of section 9.2.
PROTOCOL v0.2.0 (the owner's rulings of 2026-10-20), carried unchanged into v0.3.0 (the owner's ruling of 2026-10-27: the task-v0.3
slice-wide stimulus; the panel, both applicabilities and every number unchanged): K9's judged row is (b') — the conditional coverage under SR-driven backgrounds
— with the all-panel (b) reported beside it; the judgement carries the protocol identity's digest (section 9.5) and a batch archive of
another method version, or one without an identity, is refused by name and never judged.

THE DISTINCTIONS THE RULING NAMES (section 3), kept by `judge`:
  - a complete, valid batch whose criterion fails on its data is a FAIL (never retuned, never resampled);
  - a tool / source / replay / control contract break — a batch the harness recorded `invalid` — is `invalid`;
  - unfinished work — a batch recorded `incomplete` — is `incomplete`;
  - an absent B* / N (the budget rule FAILS) leaves every row that depends on B* or N `not_assessable`, and the gate cannot PASS;
  - a PASS needs the formal identity: the pinned gate label, S = 200 as planned, a production (non-fixture) batch archive that the
    archive-wide verifier re-audits clean — a mechanics / synthetic judgement is written with `formal = false` and a standing
    that says NOT A GATE RESULT, and can never be represented as one.

TWO EVIDENCE KINDS. `batch_archive`: the harness's run directory (a production one or a `b4-mech-<n>` fixture one reached
through the Python API only). `synthetic_summary`: a hand-written summary document under a `b4-mech-<n>` label, Python API
only, so that the PASS path and every row's FAIL path can be exercised end to end — the real model does not produce a
PASS on a fixture. Both kinds go through the same `judge`; the verifier (`b4_gate_verify.py`) recomputes the judgement from
the evidence in a fresh process and holds the report to it.

WHAT A FAIL MEANS (ruling section 2): a formal FAIL is a result about this model, public task and panel, operator and
control design, budget grid and declared decision procedure under hypothesis v0.3 — not a proof that FF bits or the content
class are intrinsically indistinguishable. A PASS is never read as evidence about the fabric (section 13).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_gate_stats as gs  # noqa: E402
import b4_k9 as k9  # noqa: E402
import b4_protocol as bp  # noqa: E402
import b4_seeds as bs  # noqa: E402
import b4_sim as sim  # noqa: E402
import b4_sim_schema as sc  # noqa: E402
import b4_stats as st  # noqa: E402
import b4_thresholds as th  # noqa: E402

GATE_REL = "evidence/b4/gate"                                          # the gate namespace: one directory per judgement, <label>_<UTC>
GATE_LABEL_RE = sim.GATE_LABEL_RE
FIXTURE_LABEL_RE = bs.FIXTURE_LABEL_RE
PINNED_GATE_LABEL = th.THRESHOLDS["anchor"]["gate_label"]              # "b4-gate-1": the only production label (another label needs a revision of section 9.2)
S_GATE = th.THRESHOLDS["K6"]["S_gate"]                                 # 200
GATE_SCHEMA = ("b4_gate_report", "1.1.0")
SYNTHETIC_SCHEMA = ("b4_gate_synthetic_summary", "1.0.0")
REPORT_JSON, REPORT_MD, SYNTHETIC_JSON = "gate_report.json", "gate_report.md", "synthetic_summary.json"
EVIDENCE_KINDS = ("batch_archive", "synthetic_summary")
ROW_STATUSES = ("PASS", "FAIL", "not_assessable")
VERDICTS = ("PASS", "FAIL", "invalid", "incomplete")
K_IDS = tuple(f"K{i}" for i in range(1, 11))
GRID = th.GRID
SEMANTICS = k9.SEMANTICS
K10_NOTE = st.summarise([None], th.THRESHOLDS["K10"]["tau"], 1)["note"]          # the driver's own note text, bound by the summary contract
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

STANDING_FORMAL = ("the formal discriminability gate of docs/b4_architecture.md section 9 under the behaviour hypothesis v0.3: every row compares a recorded "
                   "value with its threshold fixed in advance; a PASS is a statement about this model, public task and panel, operator and control design, "
                   "budget grid and declared decision procedure — never evidence about the fabric or the silicon; a FAIL is a result of this protocol "
                   "version, not a proof that FF bits or the content class are indistinguishable in general; no threshold is adjusted in response")
STANDING_NOT_FORMAL = ("NOT A GATE RESULT: the gate's rows applied as written to {kind} evidence under the label {label!r} so that the tool's paths are "
                       "exercised; this judgement can never be represented as a real gate result — the formal result needs the pinned gate label, "
                       "S = 200 as planned and a production batch archive")
SCOPE = ("every result is under the behaviour hypothesis v0.3 and the certificate mapping of the one site; a FAIL is confined to this model, public task / panel, "
         "operator / control design, budget grid and declared decision procedure; nothing here is a statement about silicon, about the carrier, or about the "
         "content class in general; a PASS is never read as evidence about the fabric")


class Refusal(Exception):
    """A refusal before anything is written."""


# ------------------------------------------------------------------ small helpers
def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    return sha_bytes(Path(p).read_bytes())


def _stat_value(enc) -> tuple:
    """An encoded statistic ({'value', 'special'}) as (finite value or None, special or None); anything else -> (None, 'malformed')."""
    if isinstance(enc, dict) and set(enc) == {"value", "special"}:
        return enc["value"], enc["special"]
    return None, "malformed"


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _row(rid: str, criterion: str, method: str, threshold, value, status: str, reason: str) -> dict:
    assert status in ROW_STATUSES
    return {"id": rid, "criterion": criterion, "method": method, "threshold": threshold, "value": value, "status": status, "reason": reason}


def _na(rid: str, criterion: str, method: str, threshold, reason: str, value=None) -> dict:
    return _row(rid, criterion, method, threshold, value, "not_assessable", reason)


# ------------------------------------------------------------------ the summary's own contract (a tampered, malformed or incoherent summary is `invalid`, never judged)
#
# TOTAL on arbitrary decoded JSON (the owner's review of 4cdc0c1, R1 / R2): every shape and exact type is checked before it is indexed or
# used in arithmetic (a bool is never an int, 64.0 is never the budget 64, a non-finite float is never a number); every field K1–K10 read
# is bound to the quantity it represents elsewhere in the summary — the at-B* copies to their per-budget originals, the ratios to the
# means they are made of (through the harness's own `_ratio`), the sign-test p to its counts, Cohen's d to its mean and variance with the
# one valid encoding of +inf, the N scan to its ascending structure and to the claimed N / power, the fractions to their counts and S,
# the budget rule to its inputs. The intentional representations (a null N, a null power below n_min, a +inf d, a null median for a
# semantic with a not-assessable seed) are kept as such; an absent number is a contract finding, never a landscape FAIL.
INT_BOUND = 2 ** 63                                                    # a decoded JSON integer beyond this is out of every numeric contract here (and would overflow float conversion)
S_MAX = 1_000_000                                                      # the planned count's bound in the contract (K6 plans 200; the scan is enumerated to S)
D_REL_TOL = 1e-12                                                      # the relative tolerance (floor 1) of the CONSISTENCY check binding a recorded finite Cohen's d to the value implied by
#   its mean, population variance and S. What it is: on the 140 archived delta records (the S = 32 exploration and the fixture archives) the two
#   routes to d — the production function on the deltas, and mean / sqrt(pvariance · S / (S − 1)) from the recorded statistics — differ by at
#   most 2.2e-16, a rounding discrepancy measured on THOSE records, not a bound on every possible record. What it is not: it is not the K5
#   threshold and not smaller than every difference a criterion can notice — a threshold comparison is discontinuous at its boundary, so near
#   d = 0.5 a summary perturbation within this tolerance passes the consistency check and can change a SYNTHETIC judgement (the owner's review
#   of b49b2ec, section 2; test_b4_gate documents the example). The judgement reads the RECORDED value, the production function's, and no
#   epsilon is added to K5. For a production archive the source authenticity and the exact replay / recomputation of the summary from the raw
#   records are separate requirements of the archive-wide verifier; this check only refuses a summary whose d is not that function's value.


def numeric_findings(obj, path: str = "$") -> list[str]:
    """Total over decoded JSON: every float finite, every int within ±2^63 (a bool is not a number here). Run BEFORE any canonical
    serialisation, comparison or arithmetic, so that a huge integer or an infinite / NaN literal is a named finding, never an exception."""
    f: list[str] = []
    if isinstance(obj, bool):
        return f
    if isinstance(obj, int):
        if not (-INT_BOUND < obj < INT_BOUND):
            f.append(f"{path}: an integer beyond ±2^63 is outside every numeric contract")
    elif isinstance(obj, float):
        if not math.isfinite(obj):
            f.append(f"{path}: {obj!r} is not finite")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            f += numeric_findings(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            f += numeric_findings(v, f"{path}[{i}]")
    return f


def _fin(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return -INT_BOUND < v < INT_BOUND
    return isinstance(v, float) and math.isfinite(v)


def _int(v) -> bool:
    return type(v) is int and -INT_BOUND < v < INT_BOUND


def _same(a, b) -> bool:
    """Exact in value AND in type (2, 2.0 and true differ): the comparison every copy and constant binding uses. Both sides are finite
    (the numeric pre-pass ran) so the canonical serialisation cannot raise."""
    try:
        return sc.canonical(a) == sc.canonical(b)
    except (TypeError, ValueError):
        return False


def _in01(v) -> bool:
    return _fin(v) and 0 <= v <= 1


def _exact(d, want: set, f: list[str], where: str) -> bool:
    if not isinstance(d, dict):
        f.append(f"{where}: not an object"); return False
    if set(d) != want:
        f.append(f"{where}: keys {sorted(set(d) ^ want)} differ from the schema's"); return False
    return True


def _close(a, b, tol: float = 1e-9) -> bool:
    return _fin(a) and _fin(b) and abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def _sign_p(pos: int, neg: int) -> float:
    n = pos + neg
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(pos, n + 1)) / 2 ** n


UNREPRESENTABLE = "unrepresentable"                                    # a derived value no finite float carries: a named finding wherever it arises, never a comparison


def implied_cohen_d(mean, pvariance, S: int):
    """The value the production statistic (`b4_gate_stats.cohen_d`, by copy of host/b2_gate.py: mean / statistics.stdev, the SAMPLE standard
    deviation) takes on a delta list of S values with this mean and POPULATION variance: S < 2 → 0.0; variance 0 → +inf when the mean is
    positive, 0.0 otherwise; else mean / sqrt(pvariance · S / (S − 1)). Returned as the encoded statistic. Numerically safe (the owner's
    review of b49b2ec, section 1): every intermediate — the sample variance, its root, the quotient — is checked finite; an overflow or an
    underflow to zero of the root is {"value": None, "special": "unrepresentable"}, which the caller names and never compares."""
    if S < 2:
        return {"value": 0.0, "special": None}
    if pvariance == 0:
        return {"value": None, "special": "+inf"} if mean > 0 else {"value": 0.0, "special": None}
    sample_var = pvariance * S / (S - 1)
    if not math.isfinite(sample_var) or sample_var <= 0:
        return {"value": None, "special": UNREPRESENTABLE}
    sd = math.sqrt(sample_var)
    if not math.isfinite(sd) or sd == 0:
        return {"value": None, "special": UNREPRESENTABLE}
    d = mean / sd
    if not math.isfinite(d):
        return {"value": None, "special": UNREPRESENTABLE}
    return {"value": d, "special": None}


def _stat_findings(enc, f: list[str], where: str, mean=None, var=None, S=None) -> None:
    """An encoded statistic ({"value", "special"}): special None with a finite value, or special "+inf" with value None — the only two
    encodings the copied cohen_d produces ("-inf" / "nan" / "none" never occur). Bound to its mean, population variance and S when
    given (the owner's review of a8f2da1, P2 1): the special cases exactly (S < 2 → 0.0; variance 0 → +inf when the mean is positive,
    0.0 otherwise) and a finite d to the value implied under the production sample-variance convention within D_REL_TOL — a sign or
    copy agreement alone is not this binding."""
    if not _exact(enc, {"value", "special"}, f, where):
        return
    v, s = enc["value"], enc["special"]
    if s is None:
        if not _fin(v):
            f.append(f"{where}: special null needs a finite value"); return
    elif s == "+inf":
        if v is not None:
            f.append(f"{where}: special +inf carries a null value, not {v!r}"); return
    else:
        f.append(f"{where}: special {s!r} is not an encoding the copied cohen_d produces"); return
    if mean is None or var is None or S is None:
        return
    want = implied_cohen_d(mean, var, S)
    if want["special"] == UNREPRESENTABLE:
        f.append(f"{where}: the d implied by mean {mean!r}, population variance {var!r} and S = {S} is not representable (overflow / underflow): out of the contract's range"); return
    if want["special"] == "+inf":
        if s != "+inf":
            f.append(f"{where}: all deltas equal and positive encode +inf")
        return
    if s is not None:
        f.append(f"{where}: {'S < 2' if S < 2 else 'a positive variance'} gives the finite d {want['value']!r}, not +inf"); return
    w = want["value"]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or abs(v - w) > D_REL_TOL * max(1.0, abs(w)):
        f.append(f"{where}: d {v!r} is not the production statistic of its mean {mean!r}, population variance {var!r} and S = {S} ({w!r}; sample standard deviation)")


def _delta_findings(d, f: list[str], where: str, S: int, expect_mean=None) -> None:
    if not _exact(d, {"n", "mean", "median", "positives", "negatives", "ties", "sign_test_p", "population_variance", "cohen_d"}, f, where):
        return
    if not (_int(d["n"]) and d["n"] == S):
        f.append(f"{where}.n is not S"); return
    if not all(_int(d[k]) and d[k] >= 0 for k in ("positives", "negatives", "ties")) or d["positives"] + d["negatives"] + d["ties"] != S:
        f.append(f"{where}: positives + negatives + ties is not S"); return
    if not (_fin(d["mean"]) and _fin(d["median"]) and _fin(d["population_variance"]) and d["population_variance"] >= 0):
        f.append(f"{where}: mean / median / population_variance are not finite numbers (variance ≥ 0)"); return
    if d["positives"] == 0 and d["negatives"] == 0 and d["ties"] == S and d["mean"] != 0:
        f.append(f"{where}: all pairs tied with a non-zero mean")
    if not (_in01(d["sign_test_p"]) and d["sign_test_p"] == _sign_p(d["positives"], d["negatives"])):
        f.append(f"{where}.sign_test_p is not the one-sided exact p of its counts")
    if d["population_variance"] == 0 and d["median"] != d["mean"]:
        f.append(f"{where}: zero variance with median ≠ mean")
    if expect_mean is not None and not _close(d["mean"], expect_mean):
        f.append(f"{where}.mean {d['mean']!r} is not the difference of the arm means {expect_mean!r}")
    _stat_findings(d["cohen_d"], f, where + ".cohen_d", d["mean"], d["population_variance"], S)


def _scan_findings(rp, f: list[str], where: str, S: int, T) -> None:
    """required_pairs: n_min / n_max; the scan an ascending complete list [[n, rate]] from n_min; with no N every n to S scanned below
    power_min (empty when S < n_min, then the power is null); with N the scan ends at N whose rate reaches power_min and N is at least 8."""
    if not _exact(rp, {"N", "power_at_N_or_last", "scan", "n_min", "n_max"}, f, where):
        return
    n_min, pmin = T["K5"]["n_min"], T["K5"]["power_min"]
    if not (_same(rp["n_min"], n_min) and _same(rp["n_max"], S)):
        f.append(f"{where}: n_min / n_max are not {n_min} / S (exactly, as ints)"); return
    scan = rp["scan"]
    if not (isinstance(scan, list) and all(isinstance(e, list) and len(e) == 2 and _int(e[0]) and _in01(e[1]) for e in scan)):
        f.append(f"{where}.scan is not a list of [n, rate] with rates in [0, 1]"); return
    ns = [e[0] for e in scan]
    if ns != list(range(n_min, n_min + len(ns))):
        f.append(f"{where}.scan is not the complete ascending scan from {n_min}"); return
    N, last = rp["N"], rp["power_at_N_or_last"]
    if N is None:
        if S < n_min:
            if scan or last is not None:
                f.append(f"{where}: S < n_min scans nothing and has no power")
        else:
            if ns != list(range(n_min, S + 1)):
                f.append(f"{where}: no N needs every n from {n_min} to S scanned")
            elif any(e[1] >= pmin for e in scan):
                f.append(f"{where}: no N although a scanned rate reaches {pmin}")
            elif last != scan[-1][1]:
                f.append(f"{where}: power_at_N_or_last is not the last scanned rate")
    else:
        if not (_int(N) and n_min <= N <= S):
            f.append(f"{where}.N {N!r} is not an int in [{n_min}, S]"); return
        if ns != list(range(n_min, N + 1)):
            f.append(f"{where}: the scan does not end at N = {N}")
        elif any(e[1] >= pmin for e in scan[:-1]) or scan[-1][1] < pmin:
            f.append(f"{where}: N is not the first n whose rate reaches {pmin}")
        elif last != scan[-1][1]:
            f.append(f"{where}: power_at_N_or_last is not the rate at N")


def _ratio_findings(r, f: list[str], where: str, num, den) -> None:
    """The ratio record held to the harness's own `_ratio` of its numerator and denominator. Numerically safe: a quotient that overflows
    (finite inputs such as 1e308 / 5e-324 give +inf) is a named finding before any serialisation or comparison."""
    if not (_fin(num) and _fin(den)):
        f.append(f"{where}: its numerator / denominator are not finite numbers"); return
    want = sim._ratio(num, den)
    if want["ratio"] is not None and not math.isfinite(want["ratio"]):
        f.append(f"{where}: the ratio {num!r} / {den!r} is not representable (overflow): out of the contract's range"); return
    if not _exact(r, set(want), f, where):
        return
    if not _same(r, want):
        f.append(f"{where} is not the harness's ratio record of its numerator and denominator")


def summary_contract_findings(s, S) -> list[str]:
    """The structure the judge reads, its exact types and its internal coherence (see the module note above). Total: a finding, never an
    exception, for any decoded JSON. Empty = the summary is well formed and coherent under the frozen method (which says nothing about
    whether its observations are authentic — that is the archive verifier's)."""
    T = th.THRESHOLDS
    f: list[str] = []
    if not (_int(S) and 0 < S <= S_MAX):
        return [f"the batch's count is not a positive int ≤ {S_MAX}"]
    nf = numeric_findings(s, "summary")
    if nf:
        return nf[:20]
    if not _exact(s, {"S", "grid", "per_budget", "eligible_budgets", "candidate_B_star", "at_candidate_B_star", "k9", "k10", "thresholds_for_reference", "standing"}, f, "summary"):
        return f
    if not _same(s["S"], S):
        f.append(f"summary.S {s['S']!r} is not the batch's count {S}")
    if not (isinstance(s["grid"], list) and all(_int(b) for b in s["grid"]) and s["grid"] == list(GRID)):
        f.append("summary.grid is not the fixed grid")
    if sc.canonical(s["thresholds_for_reference"]) != sc.canonical(T):
        f.append("summary.thresholds_for_reference is not the thresholds table")
    if not isinstance(s["standing"], str):
        f.append("summary.standing is not a string")
    pb = s["per_budget"]
    if not (isinstance(pb, dict) and set(pb) == {str(B) for B in GRID}):
        return f + ["summary.per_budget does not carry exactly the grid budgets"]
    elig_expected, both_signs_expected = [], []
    for B in GRID:
        w = f"per_budget[{B}]"
        v = pb[str(B)]
        if not _exact(v, {"budget", "arm_values", "base", "f_end_to_end", "deltas", "k1", "required_pairs", "cost_N_x_3_x_B", "k7_O_prefix_not_unknown"}, f, w):
            continue
        if not _same(v["budget"], B):
            f.append(f"{w}.budget is {v['budget']!r}")
        av = v["arm_values"]
        ok_av = _exact(av, set(sc.ROLES), f, w + ".arm_values")
        if ok_av:
            for role in sc.ROLES:
                a = av[role]
                if not (_exact(a, {"mean", "median", "min", "max"}, f, f"{w}.arm_values.{role}") and all(_fin(a[k]) for k in a) and a["min"] <= a["median"] <= a["max"] and a["min"] <= a["mean"] <= a["max"]):
                    f.append(f"{w}.arm_values.{role}: finite numbers with min ≤ median, mean ≤ max"); ok_av = False
        base = v["base"]
        ok_base = _exact(base, {"mean", "median"}, f, w + ".base") and all(_fin(base[k]) for k in base)
        if not ok_base:
            f.append(f"{w}.base: finite mean / median")
        fe = v["f_end_to_end"]
        ok_fe = _exact(fe, {"mean", "median", "mapping_in_progress"}, f, w + ".f_end_to_end") and _fin(fe["mean"]) and _fin(fe["median"]) and fe["mapping_in_progress"] is (B <= th.PROBES)
        if not ok_fe:
            f.append(f"{w}.f_end_to_end: finite mean / median, mapping_in_progress exactly when B ≤ {th.PROBES}")
        if ok_fe and B <= th.PROBES and ok_base and not (_close(fe["mean"], base["mean"]) and fe["median"] == base["median"]):
            f.append(f"{w}.f_end_to_end: mapping in progress means F's base score")
        dl = v["deltas"]
        names = {"delta1_O_minus_R": ("O", "R"), "delta2_O_minus_endtoend_F": ("O", None), "F_minus_R": ("F", "R"), "X_minus_R": ("X", "R"), "D_minus_R": ("D", "R"), "Omega_minus_R": ("Omega", "R"), "A0_minus_R": ("A0", "R")}
        ok_dl = _exact(dl, set(names), f, w + ".deltas")
        if ok_dl:
            for name, (x, y) in names.items():
                em = None
                if ok_av and ok_fe:
                    em = av[x]["mean"] - (av[y]["mean"] if y else fe["mean"])
                _delta_findings(dl[name], f, f"{w}.deltas.{name}", S, em)
        k1 = v["k1"]
        ok_k1 = _exact(k1, {"omega_best_p95", "median_best_R", "median_base", "eligibility"}, f, w + ".k1") and all(_fin(k1[k]) for k in ("omega_best_p95", "median_best_R", "median_base")) and isinstance(k1["eligibility"], bool)
        if not ok_k1:
            f.append(f"{w}.k1: finite numbers and a bool eligibility")
        else:
            if k1["eligibility"] is not bool(k1["omega_best_p95"] < T["K1"]["omega_best_p95_lt"] and k1["median_best_R"] > k1["median_base"]):
                f.append(f"{w}.k1.eligibility is not the one of its own numbers")
            if ok_av and not (av["Omega"]["min"] <= k1["omega_best_p95"] <= av["Omega"]["max"]):
                f.append(f"{w}.k1.omega_best_p95 lies outside Omega's values")
            if ok_av and not _same(k1["median_best_R"], av["R"]["median"]):
                f.append(f"{w}.k1.median_best_R is not arm R's median")
            if ok_base and not _same(k1["median_base"], base["median"]):
                f.append(f"{w}.k1.median_base is not the base median")
        rp = v["required_pairs"]
        before = len(f)
        _scan_findings(rp, f, w + ".required_pairs", S, T)
        ok_rp = len(f) == before
        cost = v["cost_N_x_3_x_B"]
        if ok_rp:
            if rp["N"] is None:
                if cost is not None:
                    f.append(f"{w}.cost_N_x_3_x_B is not null without N")
            elif not _same(cost, rp["N"] * 3 * B):
                f.append(f"{w}.cost_N_x_3_x_B is not N x 3 x B")
        k7 = v["k7_O_prefix_not_unknown"]
        if not (_exact(k7, {"values", "median"}, f, w + ".k7_O_prefix_not_unknown") and isinstance(k7["values"], list) and len(k7["values"]) == S
                and all(_int(x) and 0 <= x <= th.ADDRESSES for x in k7["values"]) and _same(k7["median"], statistics.median(k7["values"]))):
            f.append(f"{w}.k7_O_prefix_not_unknown: S ints in [0, {th.ADDRESSES}] and their median (exactly, as the production median writes it)")
        if ok_k1 and ok_rp and k1["eligibility"] and rp["N"] is not None:
            elig_expected.append(B)
        if ok_dl and isinstance(dl.get("delta1_O_minus_R"), dict) and _int(dl["delta1_O_minus_R"].get("positives")) and _int(dl["delta1_O_minus_R"].get("negatives")) \
                and dl["delta1_O_minus_R"]["positives"] > 0 and dl["delta1_O_minus_R"]["negatives"] > 0:
            both_signs_expected.append(B)
    if f:
        return f
    if not (isinstance(s["eligible_budgets"], list) and _same(s["eligible_budgets"], elig_expected)):
        f.append(f"eligible_budgets {s['eligible_budgets']!r} are not the budgets with K1 eligibility and an N {elig_expected!r}")
    cb = s["candidate_B_star"]
    if not _exact(cb, {"value", "reason_if_none", "note"}, f, "candidate_B_star"):
        return f
    if cb["note"] != T["B_star"]["no_eligible_budget"]:
        f.append("candidate_B_star.note is not the table's")
    at = s["at_candidate_B_star"]
    if elig_expected:
        want = min(elig_expected, key=lambda B: (pb[str(B)]["cost_N_x_3_x_B"], B))
        if not (_int(cb["value"]) and cb["value"] == want):
            f.append(f"candidate_B_star {cb['value']!r} is not the cheapest eligible budget {want} (ties to the smaller)")
        if cb["reason_if_none"] is not None:
            f.append("candidate_B_star.reason_if_none is not null although B* exists")
        if f:
            return f
        B = cb["value"]
        v, dl = pb[str(B)], pb[str(B)]["deltas"]
        if not _exact(at, {"B_star", "N", "cost_N_x_3_x_B_star", "k2", "k3", "k4", "k5", "k7"}, f, "at_candidate_B_star"):
            return f
        if not (_same(at["B_star"], B) and _same(at["N"], v["required_pairs"]["N"]) and _same(at["cost_N_x_3_x_B_star"], v["cost_N_x_3_x_B"])):
            f.append("at_candidate_B_star's B* / N / cost are not per_budget's")
        k2 = at["k2"]
        if _exact(k2, {"population_variance_delta1", "budgets_with_both_signs", "x_minus_r_bootstrap_nonrejection", "bootstrap"}, f, "at_candidate_B_star.k2"):
            if not _same(k2["population_variance_delta1"], dl["delta1_O_minus_R"]["population_variance"]):
                f.append("k2.population_variance_delta1 is not delta1's population variance at B*")
            if not _same(k2["budgets_with_both_signs"], both_signs_expected):
                f.append(f"k2.budgets_with_both_signs {k2['budgets_with_both_signs']!r} are not the budgets with both signs of delta1 {both_signs_expected!r}")
            if not _in01(k2["x_minus_r_bootstrap_nonrejection"]):
                f.append("k2.x_minus_r_bootstrap_nonrejection is not a rate in [0, 1]")
            bt = k2["bootstrap"]
            if not (_exact(bt, {"N", "experiments", "alpha", "seed"}, f, "k2.bootstrap") and _same(bt, {"N": at["N"], "experiments": T["K2"]["bootstrap_experiments"], "alpha": T["K2"]["alpha"], "seed": T["K2"]["bootstrap_seed"]})):
                f.append("k2.bootstrap is not (N, 1000, 0.05, 7) exactly")
        k3 = at["k3"]
        if _exact(k3, {"D_over_F", "X_over_O", "D_sign_test_p", "X_sign_test_p"}, f, "at_candidate_B_star.k3"):
            _ratio_findings(k3["D_over_F"], f, "k3.D_over_F", dl["D_minus_R"]["mean"], dl["F_minus_R"]["mean"])
            _ratio_findings(k3["X_over_O"], f, "k3.X_over_O", dl["X_minus_R"]["mean"], dl["delta1_O_minus_R"]["mean"])
            if not (_same(k3["D_sign_test_p"], dl["D_minus_R"]["sign_test_p"]) and _same(k3["X_sign_test_p"], dl["X_minus_R"]["sign_test_p"])):
                f.append("k3's sign-test p values are not the controls' at B*")
        k4 = at["k4"]
        if _exact(k4, {"median_best_Omega", "mean_Omega_minus_R", "mean_F_minus_R", "F_over_Omega"}, f, "at_candidate_B_star.k4"):
            if not (_same(k4["median_best_Omega"], v["arm_values"]["Omega"]["median"]) and _same(k4["mean_Omega_minus_R"], dl["Omega_minus_R"]["mean"]) and _same(k4["mean_F_minus_R"], dl["F_minus_R"]["mean"])):
                f.append("k4's medians / means are not the arm values' at B*")
            _ratio_findings(k4["F_over_Omega"], f, "k4.F_over_Omega", dl["F_minus_R"]["mean"], dl["Omega_minus_R"]["mean"])
        k5 = at["k5"]
        if _exact(k5, {"cohen_d_delta1", "N", "cost"}, f, "at_candidate_B_star.k5"):
            if not _same(k5["cohen_d_delta1"], dl["delta1_O_minus_R"]["cohen_d"]):
                f.append("k5.cohen_d_delta1 is not delta1's Cohen's d at B*")
            if not (_same(k5["N"], at["N"]) and _same(k5["cost"], at["cost_N_x_3_x_B_star"])):
                f.append("k5's N / cost are not the budget rule's")
        k7 = at["k7"]
        if _exact(k7, {"median_O_prefix_not_unknown", "values"}, f, "at_candidate_B_star.k7"):
            if not (_same(k7["median_O_prefix_not_unknown"], v["k7_O_prefix_not_unknown"]["median"]) and _same(k7["values"], v["k7_O_prefix_not_unknown"]["values"])):
                f.append("k7 at B* is not per_budget's K7 record")
    else:
        if cb["value"] is not None or not isinstance(cb["reason_if_none"], str) or not cb["reason_if_none"]:
            f.append("no eligible budget: candidate_B_star must be null with its reason")
        if at is not None:
            f.append("no B*: at_candidate_B_star must be null")
    k9s = s["k9"]
    if _exact(k9s, {"judged_estimand", "per_semantic", "per_semantic_all_panel", "seeds_with_all_seven_positive_controls", "fraction_of_S"}, f, "k9"):
        if k9s["judged_estimand"] != k9.JUDGED_ESTIMAND:
            f.append(f"k9.judged_estimand {k9s['judged_estimand']!r} is not this version's {k9.JUDGED_ESTIMAND!r}")
        k9_all = k9s["seeds_with_all_seven_positive_controls"]
        if not (_int(k9_all) and 0 <= k9_all <= S):
            f.append("k9.seeds_with_all_seven_positive_controls is not an int in [0, S]")
        elif not _same(k9s["fraction_of_S"], k9_all / S):
            f.append("k9.fraction_of_S is not seeds_with_all_seven_positive_controls / S")
        for block in ("per_semantic", "per_semantic_all_panel"):
            per = k9s[block]
            if not _exact(per, set(SEMANTICS), f, f"k9.{block}"):
                continue
            for sem in SEMANTICS:
                rec = per[sem]
                w = f"k9.{block}.{sem}"
                if not _exact(rec, {"seeds_with_positive_control", "not_assessable_seeds", "median_coverage_over_all_S", "median_rule", "conditional_on_A8"}, f, w):
                    continue
                if not (_int(rec["seeds_with_positive_control"]) and 0 <= rec["seeds_with_positive_control"] <= S and _int(rec["not_assessable_seeds"]) and 0 <= rec["not_assessable_seeds"] <= S):
                    f.append(f"{w}: counts are ints in [0, S]"); continue
                if _int(k9_all) and rec["seeds_with_positive_control"] < k9_all:
                    f.append(f"{w}: fewer seeds with a positive control than seeds with all seven")
                m = rec["median_coverage_over_all_S"]
                if rec["not_assessable_seeds"] > 0:
                    if m is not None:
                        f.append(f"{w}: a not-assessable seed leaves no median")
                elif not _in01(m):
                    f.append(f"{w}: the median coverage is not a number in [0, 1]")
                if rec["median_rule"] != T["K9"]["median_population"]:
                    f.append(f"{w}.median_rule is not the table's")
                if rec["conditional_on_A8"] is not (sem == "ff_init"):
                    f.append(f"{w}.conditional_on_A8 is not {sem == 'ff_init'}")
        if isinstance(k9s["per_semantic"], dict) and isinstance(k9s["per_semantic_all_panel"], dict):
            for sem in SEMANTICS:
                a, b = k9s["per_semantic"].get(sem), k9s["per_semantic_all_panel"].get(sem)
                if isinstance(a, dict) and isinstance(b, dict) and sem not in k9.SR_SEMANTICS and _same(a.get("not_assessable_seeds"), b.get("not_assessable_seeds")) \
                        and not _same(a.get("median_coverage_over_all_S"), b.get("median_coverage_over_all_S")):
                    f.append(f"k9.{sem}: the judged and the all-panel medians differ on a non-SR semantic (the conditional rule changes ff_srval / sr_kind only)")
    k10s = s["k10"]
    if _exact(k10s, {"tau", "S", "counts", "fraction_interacting_over_S", "note"}, f, "k10"):
        if not (_same(k10s["tau"], T["K10"]["tau"]) and _same(k10s["S"], S)):
            f.append("k10: tau / S are not the table's / the batch's (exactly)")
        if k10s["note"] != K10_NOTE:
            f.append("k10.note is not the driver's")
        c = k10s["counts"]
        if _exact(c, set(st.OUTCOMES), f, "k10.counts"):
            if not all(_int(x) and x >= 0 for x in c.values()) or sum(c.values()) != S:
                f.append("k10.counts: non-negative ints summing to S")
            elif not _same(k10s["fraction_interacting_over_S"], c[st.INTERACTING] / S):
                f.append("k10.fraction_interacting_over_S is not interacting / S")
    return f


def doc_identity_findings(doc) -> list[str]:
    """The report-like document's identity fields the judge reads: status one of the harness's, label a string of the label grammar,
    fixture a bool, count a positive int. Total."""
    f: list[str] = []
    if not isinstance(doc, dict):
        return ["the document is not an object"]
    nf = numeric_findings(doc, "document")
    if nf:
        return nf[:20]
    if doc.get("status") not in sc.STATUSES:
        f.append(f"status {doc.get('status')!r} is not one of {sc.STATUSES}")
    if not (isinstance(doc.get("label"), str) and bs.LABEL_RE.match(doc["label"])):
        f.append("label is not a label")
    if not isinstance(doc.get("fixture"), bool):
        f.append("fixture is not a bool")
    if not (_int(doc.get("count")) and 0 < doc["count"] <= S_MAX):
        f.append(f"count is not a positive int ≤ {S_MAX}")
    return f


# ------------------------------------------------------------------ the judgement (pure)
def formal_reasons(doc: dict, evidence_kind: str) -> list[str]:
    """Why the judgement is NOT the formal gate result; empty = formal. The formal result needs the pinned gate label, S = 200 as
    planned, a production (non-fixture) batch archive that completed. (Whether the archive verifies is the verifier's finding.)"""
    r: list[str] = []
    if evidence_kind != "batch_archive":
        r.append(f"the evidence is {evidence_kind}, not a batch archive")
    if doc.get("fixture") is not False:
        r.append("a fixture batch")
    if doc.get("label") != PINNED_GATE_LABEL:
        r.append(f"the label {doc.get('label')!r} is not the pinned gate label {PINNED_GATE_LABEL!r}")
    if doc.get("count") != S_GATE:
        r.append(f"S = {doc.get('count')!r} is not the planned {S_GATE}")
    if doc.get("status") != "complete":
        r.append(f"the batch is {doc.get('status')!r}, not complete")
    return r


def judge(doc: dict, evidence_kind: str = "batch_archive") -> dict:
    """The ten rows, the budget rule and the verdict from a report-like document {status, label, fixture, count, summary}: the
    harness's sim_report.json (evidence batch_archive) or a synthetic summary document (evidence synthetic_summary). Pure."""
    if evidence_kind not in EVIDENCE_KINDS:
        raise ValueError(f"evidence kind {evidence_kind!r}")
    T = th.THRESHOLDS
    idf = doc_identity_findings(doc)
    g = (lambda k: doc.get(k)) if isinstance(doc, dict) else (lambda k: None)
    status, S, label = g("status"), g("count"), g("label")
    formal_r = formal_reasons(doc if isinstance(doc, dict) else {}, evidence_kind)
    out = {"label": label, "S": S, "fixture": g("fixture"), "batch_status": status, "evidence_kind": evidence_kind,
           "formal": not formal_r, "formal_reasons": formal_r, "contract_findings": []}
    meth = {
        "K1": "percentile(best_Omega(B*), 95) < 64 (B2 linear interpolation, by copy) and median_r(best_R(B*)) > median_r(base_r), two medians compared; eligibility at every grid budget decides B*",
        "K2": "population variance of {delta1_r} at B* > 0; one grid budget with positives and negatives of delta1; the one-sided exact sign test on X - R at B* with size N (H1: P(X - R > 0 | X - R != 0) > 1/2) not rejecting H0 in >= 90 % of 1 000 bootstrap experiments (random.Random(7), alpha 0.05, ties out of n and kept in the population)",
        "K3": "mean(F - R) > 0 and mean(D - R) <= 0.10 mean(F - R); mean(O - R) > 0 and mean(X - R) <= 0.10 mean(O - R); D's and X's one-sided sign tests (H1: P(control - R > 0 | != 0) > 1/2) not significant (p > 0.05); a non-positive denominator is not readable as satisfied",
        "K4": "median_r(best_Omega(B*)) <= 0.90 * 64 = 57.6; mean(Omega - R) > 0 and mean(F - R) >= 0.50 mean(Omega - R)",
        "K5": "paired Cohen's d of {delta1_r} at B* >= 0.5; N(B*) by the complete ascending scan of required_pairs (8 .. S, alpha 0.05, bootstrap power >= 0.90, 1 000 experiments, random.Random(1 + N)); N x 3 x B* <= 4 000 search evaluations",
        "K6": "S = 200 planned (never the number completed) and N >= 8",
        "K7": "(a) zero recomputation mismatches on every arm's own ledger (the completion contract: each audit's recompute findings empty, re-audited by the archive-wide verifier); (b) median_r over seeds of the addresses whose state is not unknown in arm O's B* prefix >= 11 of 21",
        "K8": "the replay of every executed run reports no finding, the recorded q grid recomputes the recorded fitness, X's shadow isomorphism and the source-identity / fixture boundary hold (the completion contract; a break is invalid under 9.1)",
        "K9": ("on the fixed comparison set of 9.3: (a) >= 90 % of all S seeds have, for each of the seven semantics, an applicable pair whose readouts differ (the all-panel record); "
               "(b') JUDGED (protocol v0.2.0, unchanged in v0.3.0): per semantic, the median over all S seeds of the CONDITIONAL coverage fraction >= 0.50 — applicable_conditional = applicable_all_panel AND "
               "sr_mode = driven at both endpoints for ff_srval and sr_kind, the five other semantics as the all-panel rule, the latch / x5FF exclusions kept (a semantic not assessable "
               "for one seed has no median and does not meet (b')); (b) the all-panel coverage of clauses 4-5 is recomputed from the same retained raw grids and reported beside (b') "
               "as a description, not judged"),
        "K10": "tau = 2: interacting seeds (max|I| > 2 over both fixed backgrounds, all 210 pairs) / all S >= 0.50; not-assessable seeds stay in the denominator",
    }
    crit = {"K1": "non-saturation", "K2": "not a definitional lock", "K3": "wrong maps do not profit", "K4": "headroom against the certificate-derived grouping",
            "K5": "effect, power, N", "K6": "no fixed-seed lock", "K7": "the map is a map", "K8": "ledger replay", "K9": "observability", "K10": "real interaction"}
    thr = {"K1": {"omega_best_p95_lt": T["K1"]["omega_best_p95_lt"], "medians": T["K1"]["medians"]},
           "K2": {"population_variance_gt": 0, "x_minus_r_nonrejection_min": T["K2"]["x_minus_r_nonrejection_min"]},
           "K3": {"ratio_max": T["K3"]["ratio_max"], "sign_test_p_gt": T["K3"]["alpha"]},
           "K4": {"omega_median_max": T["K4"]["omega_median_max"], "f_over_omega_min": T["K4"]["f_over_omega_min"]},
           "K5": {"cohen_d_min": T["K5"]["cohen_d_min"], "power_min": T["K5"]["power_min"], "cap_search_evaluations": T["K5"]["cap_search_evaluations"]},
           "K6": {"S_gate": T["K6"]["S_gate"], "N_min": T["K6"]["N_min"]},
           "K7": {"recomputation_mismatches": T["K7"]["recomputation_mismatches"], "o_prefix_median_not_unknown_min": T["K7"]["o_prefix_median_not_unknown_min"]},
           "K8": {"replay": T["K8"]["replay"]},
           "K9": {"seeds_with_all_seven_positive_controls_min": T["K9"]["seeds_with_all_seven_positive_controls_min"], "median_coverage_per_semantic_min": T["K9"]["median_coverage_per_semantic_min"],
                  "judged_estimand": T["K9"]["judged_estimand"], "applicability_judged": T["K9"]["applicability_judged"]},
           "K10": {"tau": T["K10"]["tau"], "interacting_seeds_over_S_min": T["K10"]["interacting_seeds_over_S_min"]}}

    def all_na(reason: str, budget_status: str, budget_reason: str, verdict: str, verdict_reason: str) -> dict:
        out["budget_rule"] = {"B_star": None, "N": None, "cost_N_x_3_x_B_star": None, "eligible_budgets": None, "status": budget_status, "reason": budget_reason,
                              "rule": T["B_star"]["rule"]}
        out["rows"] = [_na(k, crit[k], meth[k], thr[k], reason) for k in K_IDS]
        out["verdict"] = {"status": verdict, "reason": verdict_reason}
        return out

    if idf:
        out["contract_findings"] = idf
        out["formal"], out["formal_reasons"] = False, formal_r + ["the document's identity fields break the contract"]
        return all_na("the document's identity fields break the contract: nothing is judged", "not_assessable", "the document breaks its contract", "invalid",
                      "the document's identity fields break the contract: " + "; ".join(idf[:3]))
    if status in ("invalid", "incomplete"):
        return all_na(f"the batch is {status}: no pooled summary, nothing is judged", "not_assessable", f"the batch is {status}", status,
                      "a tool / source / replay / control contract break is invalid, never a landscape failure" if status == "invalid" else "unfinished work is incomplete, never a result")
    if status != "complete":
        out["contract_findings"] = [f"the batch status {status!r} is not one of complete / invalid / incomplete"]
        return all_na("the evidence does not carry a judgeable batch", "not_assessable", "no judgeable batch", "invalid", "the evidence breaks the report contract")
    cf = summary_contract_findings(doc.get("summary"), S)
    if cf:
        out["contract_findings"] = cf
        return all_na("the summary breaks its contract: nothing is judged", "not_assessable", "the summary breaks its contract", "invalid",
                      "the pooled summary does not satisfy the harness's contract: " + "; ".join(cf[:3]))
    s = doc["summary"]
    pb = s["per_budget"]
    b_star = s["candidate_B_star"]["value"]
    k1_elig = {str(B): pb[str(B)]["k1"]["eligibility"] for B in GRID}
    n_by_b = {str(B): pb[str(B)]["required_pairs"]["N"] for B in GRID}
    rows: list[dict] = []
    if b_star is None:
        out["budget_rule"] = {"B_star": None, "N": None, "cost_N_x_3_x_B_star": None, "eligible_budgets": [], "status": "FAIL",
                              "reason": s["candidate_B_star"]["reason_if_none"] + " — B* and N are not invented; every row that depends on B* or N is not assessable; the gate cannot PASS",
                              "rule": T["B_star"]["rule"], "k1_eligibility_by_budget": k1_elig, "N_by_budget": n_by_b}
        na_reason = "no B*: the budget rule failed (no grid budget has both K1 eligibility and an N)"
        rows.append(_na("K1", crit["K1"], meth["K1"], thr["K1"], na_reason + "; K1's eligibility per budget is in the budget rule's record", {"k1_by_budget": {str(B): pb[str(B)]["k1"] for B in GRID}}))
        for k in ("K2", "K3", "K4", "K5"):
            rows.append(_na(k, crit[k], meth[k], thr[k], na_reason))
        if S != S_GATE:
            rows.append(_row("K6", crit["K6"], meth["K6"], thr["K6"], {"S_planned": S, "N": None}, "FAIL", f"S = {S} is not the planned {S_GATE}; N does not exist"))
        else:
            rows.append(_na("K6", crit["K6"], meth["K6"], thr["K6"], "S = 200 as planned; N does not exist (no B*)", {"S_planned": S, "N": None}))
        rows.append(_na("K7", crit["K7"], meth["K7"], thr["K7"], "(a) holds by the completion contract of a complete batch (every arm audited with no recompute finding); (b) needs B*: " + na_reason,
                        {"a_recomputation_mismatches": 0, "a_basis": "complete batch: every executed run audited clean", "b_median_by_budget": {str(B): pb[str(B)]["k7_O_prefix_not_unknown"]["median"] for B in GRID}}))
        rows.append(_row("K8", crit["K8"], meth["K8"], thr["K8"], {"basis": "complete batch: the replay of every executed run recorded no finding (each arm's audit); re-audited by the archive-wide verifier"}, "PASS",
                         "holds by the completion contract of a complete batch"))
        rows.append(_k9_row(s, crit, meth, thr, T))
        rows.append(_k10_row(s, crit, meth, thr, T))
    else:
        at = s["at_candidate_B_star"]
        N = at["N"]
        v = pb[str(b_star)]
        out["budget_rule"] = {"B_star": b_star, "N": N, "cost_N_x_3_x_B_star": at["cost_N_x_3_x_B_star"], "eligible_budgets": list(s["eligible_budgets"]), "status": "PASS",
                              "reason": f"B* = {b_star} is the cheapest eligible budget (N x 3 x B = {at['cost_N_x_3_x_B_star']}); eligible {s['eligible_budgets']}",
                              "rule": T["B_star"]["rule"], "k1_eligibility_by_budget": k1_elig, "N_by_budget": n_by_b}
        k1 = v["k1"]
        ok = k1["eligibility"]
        rows.append(_row("K1", crit["K1"], meth["K1"], thr["K1"], {"B_star": b_star, "omega_best_p95": k1["omega_best_p95"], "median_best_R": k1["median_best_R"], "median_base": k1["median_base"], "eligibility_by_budget": k1_elig},
                         "PASS" if ok else "FAIL", "at B* the 95th percentile of best_Omega is below 64 and median best_R exceeds median base" if ok else "K1 does not hold at B* (an ineligible B* breaks the budget rule)"))
        k2 = at["k2"]
        var_ok = _num(k2.get("population_variance_delta1")) and k2["population_variance_delta1"] > 0
        signs_ok = isinstance(k2.get("budgets_with_both_signs"), list) and len(k2["budgets_with_both_signs"]) > 0
        nr = k2.get("x_minus_r_bootstrap_nonrejection")
        nr_ok = _num(nr) and nr >= T["K2"]["x_minus_r_nonrejection_min"]
        reasons = [] if var_ok else ["the population variance of delta1 at B* is not > 0"]
        reasons += [] if signs_ok else ["no grid budget has both positive and negative delta1"]
        reasons += [] if nr_ok else [f"X - R non-rejection {nr!r} < 0.90"]
        rows.append(_row("K2", crit["K2"], meth["K2"], thr["K2"], {"population_variance_delta1": k2.get("population_variance_delta1"), "budgets_with_both_signs": k2.get("budgets_with_both_signs"),
                                                                 "x_minus_r_bootstrap_nonrejection": nr, "bootstrap": k2.get("bootstrap")},
                         "PASS" if not reasons else "FAIL", "variance > 0, both signs at a budget, X - R not rejected in >= 90 %" if not reasons else "; ".join(reasons)))
        k3 = at["k3"]
        df, xo = k3["D_over_F"], k3["X_over_O"]
        reasons = []
        if not (df.get("readable") is True and _num(df.get("ratio")) and df["ratio"] <= T["K3"]["ratio_max"]):
            reasons.append("D / F: " + (df.get("note") or f"ratio {df.get('ratio')!r} > 0.10") if not df.get("readable") else f"D / F ratio {df.get('ratio')!r} > 0.10")
        if not (xo.get("readable") is True and _num(xo.get("ratio")) and xo["ratio"] <= T["K3"]["ratio_max"]):
            reasons.append("X / O: " + (xo.get("note") or f"ratio {xo.get('ratio')!r} > 0.10") if not xo.get("readable") else f"X / O ratio {xo.get('ratio')!r} > 0.10")
        for nm in ("D_sign_test_p", "X_sign_test_p"):
            if not (_num(k3.get(nm)) and k3[nm] > T["K3"]["alpha"]):
                reasons.append(f"{nm} {k3.get(nm)!r} is not > 0.05")
        rows.append(_row("K3", crit["K3"], meth["K3"], thr["K3"], {"D_over_F": df, "X_over_O": xo, "D_sign_test_p": k3.get("D_sign_test_p"), "X_sign_test_p": k3.get("X_sign_test_p")},
                         "PASS" if not reasons else "FAIL", "both ratios readable and <= 0.10, neither control significant" if not reasons else "; ".join(reasons)))
        k4 = at["k4"]
        fo = k4["F_over_Omega"]
        reasons = []
        if not (_num(k4.get("median_best_Omega")) and k4["median_best_Omega"] <= T["K4"]["omega_median_max"]):
            reasons.append(f"median best_Omega {k4.get('median_best_Omega')!r} > 57.6")
        if not (fo.get("readable") is True and _num(fo.get("ratio")) and fo["ratio"] >= T["K4"]["f_over_omega_min"]):
            reasons.append("F / Omega: " + (fo.get("note") or "") if not fo.get("readable") else f"F / Omega ratio {fo.get('ratio')!r} < 0.50")
        rows.append(_row("K4", crit["K4"], meth["K4"], thr["K4"], {"median_best_Omega": k4.get("median_best_Omega"), "mean_Omega_minus_R": k4.get("mean_Omega_minus_R"), "mean_F_minus_R": k4.get("mean_F_minus_R"), "F_over_Omega": fo},
                         "PASS" if not reasons else "FAIL", "median Omega within the ceiling margin and F reaches half of Omega's benefit" if not reasons else "; ".join(reasons)))
        k5 = at["k5"]
        dval, dspec = _stat_value(k5.get("cohen_d_delta1"))
        d_ok = dspec == "+inf" or (dspec is None and _num(dval) and dval >= T["K5"]["cohen_d_min"])
        power = v["required_pairs"]["power_at_N_or_last"]
        p_ok = _num(power) and power >= T["K5"]["power_min"]
        cost = at["cost_N_x_3_x_B_star"]
        c_ok = isinstance(cost, int) and cost <= T["K5"]["cap_search_evaluations"]
        reasons = [] if d_ok else [f"Cohen's d {dval!r}{(' (' + dspec + ')') if dspec else ''} < 0.5"]
        reasons += [] if p_ok else [f"bootstrap power at N {power!r} < 0.90"]
        reasons += [] if c_ok else [f"N x 3 x B* = {cost!r} > 4 000"]
        rows.append(_row("K5", crit["K5"], meth["K5"], thr["K5"], {"cohen_d_delta1": k5.get("cohen_d_delta1"), "N": N, "power_at_N": power, "cost_N_x_3_x_B_star": cost, "scan": v["required_pairs"].get("scan")},
                         "PASS" if not reasons else "FAIL", "d >= 0.5, power >= 0.90 at N, cost within the cap" if not reasons else "; ".join(reasons)))
        s_ok, n_ok = S == S_GATE, isinstance(N, int) and N >= T["K6"]["N_min"]
        rows.append(_row("K6", crit["K6"], meth["K6"], thr["K6"], {"S_planned": S, "N": N}, "PASS" if s_ok and n_ok else "FAIL",
                         "S = 200 planned and N >= 8" if s_ok and n_ok else "; ".join(([] if s_ok else [f"S = {S} is not the planned {S_GATE}"]) + ([] if n_ok else [f"N = {N!r} < 8"]))))
        k7 = at["k7"]
        m = k7.get("median_O_prefix_not_unknown")
        b_ok = _num(m) and m >= T["K7"]["o_prefix_median_not_unknown_min"]
        rows.append(_row("K7", crit["K7"], meth["K7"], thr["K7"], {"a_recomputation_mismatches": 0, "a_basis": "complete batch: every executed run audited clean", "b_median_O_prefix_not_unknown_at_B_star": m, "b_values": k7.get("values")},
                         "PASS" if b_ok else "FAIL", "(a) holds by the completion contract; (b) the median of O's not-unknown addresses at B* reaches 11" if b_ok else f"(b) median {m!r} < 11 of 21"))
        rows.append(_row("K8", crit["K8"], meth["K8"], thr["K8"], {"basis": "complete batch: the replay of every executed run recorded no finding (each arm's audit); re-audited by the archive-wide verifier"}, "PASS",
                         "holds by the completion contract of a complete batch"))
        rows.append(_k9_row(s, crit, meth, thr, T))
        rows.append(_k10_row(s, crit, meth, thr, T))
    assert [r["id"] for r in rows] == list(K_IDS)
    out["rows"] = rows
    fails = ([f"budget rule"] if out["budget_rule"]["status"] == "FAIL" else []) + [r["id"] for r in rows if r["status"] == "FAIL"]
    na = [r["id"] for r in rows if r["status"] == "not_assessable"]
    if not fails and not na and out["budget_rule"]["status"] == "PASS":
        out["verdict"] = {"status": "PASS", "reason": "the budget rule and every row PASS on a complete, valid batch" + ("" if not formal_r else " — NOT a gate result (" + "; ".join(formal_r) + ")")}
    else:
        out["verdict"] = {"status": "FAIL", "reason": "a complete, valid batch on which " + ("; ".join(f"{x} FAILS" for x in fails) if fails else "nothing fails") +
                          (f"; not assessable: {', '.join(na)}" if na else "") + " — no threshold is adjusted, no budget or sample repaired"}
    return out


def _k9_row(s, crit, meth, thr, T) -> dict:
    """(a) from the all-panel positive controls; (b') JUDGED from the conditional record; (b) the all-panel record carried beside it, not judged."""
    k = s["k9"]
    frac = k["fraction_of_S"]
    a_ok = _num(frac) and frac >= T["K9"]["seeds_with_all_seven_positive_controls_min"]
    per, per_all = {}, {}
    below, na = [], []
    for sem in SEMANTICS:
        rec = k["per_semantic"][sem]
        m = rec["median_coverage_over_all_S"]
        per[sem] = {"median_coverage_over_all_S": m, "not_assessable_seeds": rec["not_assessable_seeds"], "seeds_with_positive_control": rec.get("seeds_with_positive_control"), "conditional_on_A8": rec.get("conditional_on_A8")}
        ra = k["per_semantic_all_panel"][sem]
        per_all[sem] = {"median_coverage_over_all_S": ra["median_coverage_over_all_S"], "not_assessable_seeds": ra["not_assessable_seeds"]}
        if m is None:
            na.append(f"{sem} ({rec['not_assessable_seeds']} seeds not assessable)")
        elif m < T["K9"]["median_coverage_per_semantic_min"]:
            below.append(f"{sem} {m:.6g}")
    reasons = [] if a_ok else [f"(a) seeds with all seven positive controls {frac!r} < 0.90 of S"]
    reasons += [f"(b') conditional median coverage below 0.50: {', '.join(below)}"] if below else []
    reasons += [f"(b') not assessable: {', '.join(na)}"] if na else []
    return _row("K9", crit["K9"], meth["K9"], thr["K9"],
                {"fraction_of_S_with_all_seven_positive_controls": frac, "seeds_with_all_seven_positive_controls": k.get("seeds_with_all_seven_positive_controls"),
                 "judged_estimand": k.get("judged_estimand"), "per_semantic_conditional_judged": per, "per_semantic_all_panel_descriptive": per_all},
                "PASS" if not reasons else "FAIL", "(a) >= 90 % of seeds and (b') every semantic's conditional median coverage >= 0.50 (the all-panel (b) reported beside it, not judged)" if not reasons else "; ".join(reasons))


def _k10_row(s, crit, meth, thr, T) -> dict:
    k = s["k10"]
    frac = k["fraction_interacting_over_S"]
    ok = _num(frac) and frac >= T["K10"]["interacting_seeds_over_S_min"]
    return _row("K10", crit["K10"], meth["K10"], thr["K10"], {"fraction_interacting_over_S": frac, "counts": k["counts"], "tau": k["tau"]},
                "PASS" if ok else "FAIL", "interacting seeds / S >= 0.50" if ok else f"interacting seeds / S = {frac!r} < 0.50")


# ------------------------------------------------------------------ the synthetic summary (Python API, b4-mech labels only)
SYNTHETIC_KEYS = {"schema", "schema_version", "label", "fixture", "count", "status", "head", "summary", "note", "generated_utc"}


def synthetic_findings(doc) -> list[str]:
    """A synthetic summary document: a b4-mech-<n> label, fixture true, a status of the harness's, the summary under the judge's
    contract when complete, a note that says what it is. It can never carry a production or gate label."""
    f: list[str] = []
    if not isinstance(doc, dict) or set(doc) != SYNTHETIC_KEYS:
        return [f"synthetic summary: keys differ from the schema's"]
    nf = numeric_findings(doc, "synthetic summary")
    if nf:
        return nf[:20]
    if doc["schema"] != SYNTHETIC_SCHEMA[0] or doc["schema_version"] != SYNTHETIC_SCHEMA[1]:
        f.append("schema / schema_version")
    if not (isinstance(doc["label"], str) and FIXTURE_LABEL_RE.match(doc["label"])):
        f.append("label: a synthetic summary carries a b4-mech-<n> label only")
    if doc["fixture"] is not True:
        f.append("fixture must be true")
    if not (isinstance(doc["count"], int) and not isinstance(doc["count"], bool) and doc["count"] > 0):
        f.append("count")
    if doc["status"] not in sc.STATUSES:
        f.append("status")
    if not (doc["head"] is None or (isinstance(doc["head"], str) and HEX40.match(doc["head"]))):
        f.append("head")
    if not (isinstance(doc["note"], str) and "synthetic" in doc["note"].lower()):
        f.append("note must say it is synthetic")
    if doc["status"] == "complete":
        if not isinstance(doc["summary"], dict):
            f.append("a complete synthetic summary carries its summary")
    elif doc["summary"] is not None:
        f.append("a synthetic summary that is not complete carries no summary")
    return f


# ------------------------------------------------------------------ the gate report document and its validator
GATE_KEYS = {"schema", "schema_version", "generated_utc", "head", "clean_tree", "label", "S", "fixture", "evidence_kind", "formal", "formal_reasons", "standing", "scope",
             "batch", "identity", "thresholds", "budget_rule", "rows", "verdict", "contract_findings", "diagnostics", "self_validation", "files"}
BATCH_KEYS = {"kind", "path", "status", "label", "count", "fixture", "head", "generated_utc", "sha256", "seeds_sha256", "manifest_sha256"}


def gate_report_findings(doc) -> list[str]:
    """The typed validator of gate_report.json: keys, vocabularies, the ten rows in order, the verdict's consistency with the rows
    and the budget rule, the formal flag's consistency with its reasons, the thresholds table the module's, the file index."""
    f: list[str] = []
    if not isinstance(doc, dict) or set(doc) != GATE_KEYS:
        return [f"gate report: keys {sorted(set(doc) ^ GATE_KEYS) if isinstance(doc, dict) else 'not an object'} differ from the schema's"]
    nf = numeric_findings(doc, "gate report")
    if nf:
        return nf[:20]
    if doc["schema"] != GATE_SCHEMA[0] or doc["schema_version"] != GATE_SCHEMA[1]:
        f.append("schema / schema_version")
    if not (isinstance(doc["head"], str) and HEX40.match(doc["head"])):
        f.append("head")
    if not isinstance(doc["clean_tree"], bool):
        f.append("clean_tree")
    if not (isinstance(doc["label"], str) and bs.LABEL_RE.match(doc["label"])):
        f.append("label")
    if not (isinstance(doc["S"], int) and not isinstance(doc["S"], bool) and doc["S"] > 0):
        f.append("S")
    if not isinstance(doc["fixture"], bool):
        f.append("fixture")
    elif isinstance(doc["label"], str) and doc["fixture"] is not bool(FIXTURE_LABEL_RE.match(doc["label"])):
        f.append("fixture / label: a fixture judgement carries a b4-mech-<n> label and a production one does not")
    if doc["evidence_kind"] not in EVIDENCE_KINDS:
        f.append("evidence_kind")
    if not isinstance(doc["formal"], bool) or not (isinstance(doc["formal_reasons"], list) and all(isinstance(x, str) for x in doc["formal_reasons"])):
        f.append("formal / formal_reasons")
    elif doc["formal"] is not (doc["formal_reasons"] == []):
        f.append("formal is true exactly when there is no reason against it")
    elif doc["formal"] and (doc["fixture"] or doc["evidence_kind"] != "batch_archive" or doc["label"] != PINNED_GATE_LABEL or doc["S"] != S_GATE):
        f.append("a formal judgement is a production batch archive under the pinned gate label with S = 200")
    if not isinstance(doc["standing"], str) or (doc["formal"] is False and "NOT A GATE RESULT" not in doc["standing"]) or (doc["formal"] is True and "NOT A GATE RESULT" in doc["standing"]):
        f.append("standing: a judgement that is not formal says NOT A GATE RESULT, a formal one does not")
    if doc["scope"] != SCOPE:
        f.append("scope")
    b = doc["batch"]
    if not (isinstance(b, dict) and set(b) == BATCH_KEYS and b["kind"] == doc["evidence_kind"] and isinstance(b["path"], str) and b["path"] and not b["path"].startswith("/")
            and b["status"] in sc.STATUSES and b["label"] == doc["label"] and b["count"] == doc["S"] and b["fixture"] == doc["fixture"]
            and (b["head"] is None or (isinstance(b["head"], str) and HEX40.match(b["head"]))) and isinstance(b["sha256"], str) and HEX64.match(b["sha256"])
            and all(b[k] is None or (isinstance(b[k], str) and HEX64.match(b[k])) for k in ("seeds_sha256", "manifest_sha256"))):
        f.append("batch: the evidence record (kind, a relative path, status, label / count / fixture as the judgement's, digests)")
    ident = doc["identity"]
    if not (isinstance(ident, dict) and set(ident) == {"hypothesis_sha256", "certificate_sha256", "thresholds_source", "gate_label", "protocol_sha256", "architecture_revision"}
            and ident.get("hypothesis_sha256") == hy.HYPOTHESIS_SHA256 and ident.get("certificate_sha256") == bm.CERTIFICATE_SHA256
            and ident.get("thresholds_source") == th.THRESHOLDS["source"] and ident.get("gate_label") == PINNED_GATE_LABEL
            and isinstance(ident.get("protocol_sha256"), str) and HEX64.match(ident["protocol_sha256"]) and isinstance(ident.get("architecture_revision"), str)):
        f.append("identity: the pinned hypothesis / certificate digests, the thresholds' source, the pinned gate label, the protocol digest and the document's revision")
    if sc.canonical(doc["thresholds"]) != sc.canonical(th.THRESHOLDS):
        f.append("thresholds: not the module's table")
    br = doc["budget_rule"]
    if not (isinstance(br, dict) and {"B_star", "N", "cost_N_x_3_x_B_star", "eligible_budgets", "status", "reason", "rule"} <= set(br) and br["status"] in ROW_STATUSES
            and (br["B_star"] is None or br["B_star"] in GRID) and (br["N"] is None or (isinstance(br["N"], int) and br["N"] >= 1)) and br["rule"] == th.THRESHOLDS["B_star"]["rule"]):
        f.append("budget_rule")
    elif (br["status"] == "PASS") is not (br["B_star"] is not None and br["N"] is not None):
        f.append("budget_rule: PASS exactly when B* and N exist")
    rows = doc["rows"]
    if not (isinstance(rows, list) and [r.get("id") if isinstance(r, dict) else None for r in rows] == list(K_IDS)):
        f.append("rows: the ten criteria K1 .. K10 in order")
    else:
        for r in rows:
            if not (set(r) == {"id", "criterion", "method", "threshold", "value", "status", "reason"} and r["status"] in ROW_STATUSES and isinstance(r["reason"], str) and isinstance(r["method"], str) and isinstance(r["criterion"], str)):
                f.append(f"rows.{r.get('id')}: keys / status / texts")
    vd = doc["verdict"]
    if not (isinstance(vd, dict) and set(vd) == {"status", "reason"} and vd["status"] in VERDICTS and isinstance(vd["reason"], str)):
        f.append("verdict")
    elif not f:
        statuses = [r["status"] for r in rows]
        if vd["status"] == "PASS":
            if not (br["status"] == "PASS" and all(x == "PASS" for x in statuses)):
                f.append("verdict PASS with the budget rule or a row not PASS")
            if doc["self_validation"] != {}:
                f.append("verdict PASS with self-validation findings")
        if vd["status"] == "FAIL" and not (br["status"] == "FAIL" or "FAIL" in statuses or "not_assessable" in statuses):
            f.append("verdict FAIL with nothing failed or not assessable")
        if vd["status"] in ("invalid", "incomplete") and doc["batch"]["status"] == "complete" and vd["status"] == "incomplete":
            f.append("verdict incomplete on a complete batch")
        if doc["batch"]["status"] in ("invalid", "incomplete") and vd["status"] != doc["batch"]["status"]:
            f.append("the verdict of a batch that is not complete is that status")
        if doc["self_validation"] != {} and vd["status"] != "invalid":
            f.append("a judgement with self-validation findings is invalid")
    if not (isinstance(doc["contract_findings"], list) and all(isinstance(x, str) for x in doc["contract_findings"])):
        f.append("contract_findings")
    if not isinstance(doc["diagnostics"], dict):
        f.append("diagnostics")
    if not (isinstance(doc["self_validation"], dict) and all(isinstance(v, list) and all(isinstance(x, str) for x in v) for v in doc["self_validation"].values())):
        f.append("self_validation")
    fe = doc["files"]
    if not (isinstance(fe, list) and all(isinstance(e, dict) and set(e) == {"path", "sha256", "size"} and isinstance(e["path"], str) and isinstance(e["sha256"], str) and HEX64.match(e["sha256"]) and isinstance(e["size"], int) for e in fe)):
        f.append("files")
    elif [e["path"] for e in fe] != ([REPORT_MD] if doc["evidence_kind"] == "batch_archive" else [REPORT_MD, SYNTHETIC_JSON]):
        f.append("files: the markdown rendering (and the synthetic summary when that is the evidence), nothing else")
    return f


def _j(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False)


def render_md(doc: dict) -> str:
    """The deterministic markdown rendering of a gate report (everything but `files` and `self_validation` is rendered from the
    document; the verifier re-renders and compares bytes)."""
    L: list[str] = []
    tag = "FORMAL GATE RESULT" if doc["formal"] else "NOT A GATE RESULT"
    L.append(f"# B4 gate judgement — {doc['label']} — **{doc['verdict']['status']}** ({tag})")
    L.append("")
    L.append(f"Generated {doc['generated_utc']} at HEAD `{doc['head']}` (clean tree: {doc['clean_tree']}). Evidence: {doc['evidence_kind']} `{doc['batch']['path']}` "
             f"(status {doc['batch']['status']}, label {doc['batch']['label']}, S = {doc['batch']['count']}, fixture {doc['batch']['fixture']}, sha256 `{doc['batch']['sha256']}`; "
             f"seeds `{doc['batch']['seeds_sha256']}`, manifest `{doc['batch']['manifest_sha256']}`; batch HEAD `{doc['batch']['head']}`).")
    L.append("")
    L.append(f"Hypothesis `{doc['identity']['hypothesis_sha256']}`, certificate `{doc['identity']['certificate_sha256']}`; thresholds: {doc['identity']['thresholds_source']}; "
             f"protocol identity `{doc['identity']['protocol_sha256']}` (architecture {doc['identity']['architecture_revision']}, informational).")
    L.append("")
    L.append(f"**Standing.** {doc['standing']}")
    L.append("")
    L.append(f"**Scope.** {doc['scope']}")
    L.append("")
    if doc["formal_reasons"]:
        L.append("**Why this is not the formal result:** " + "; ".join(doc["formal_reasons"]) + ".")
        L.append("")
    L.append(f"## Verdict: **{doc['verdict']['status']}** — {doc['verdict']['reason']}")
    L.append("")
    br = doc["budget_rule"]
    L.append(f"## The budget rule — **{br['status']}**: B* = {br['B_star']}, N = {br['N']}, N × 3 × B* = {br['cost_N_x_3_x_B_star']}, eligible {br['eligible_budgets']}")
    L.append("")
    L.append(br["reason"])
    L.append("")
    if "k1_eligibility_by_budget" in br:
        L.append("| budget | K1 eligibility | N |")
        L.append("|---|---|---|")
        for B in GRID:
            L.append(f"| {B} | {br['k1_eligibility_by_budget'][str(B)]} | {br['N_by_budget'][str(B)]} |")
        L.append("")
    L.append("## The rows")
    L.append("")
    L.append("| id | criterion | status | reason | value | threshold |")
    L.append("|---|---|---|---|---|---|")
    for r in doc["rows"]:
        val = _j(r["value"]).replace("|", "\\|")
        L.append(f"| {r['id']} | {r['criterion']} | **{r['status']}** | {r['reason'].replace('|', '\\|')} | `{val}` | `{_j(r['threshold']).replace('|', '\\|')}` |")
    L.append("")
    L.append("### Methods (fixed; section 9)")
    L.append("")
    for r in doc["rows"]:
        L.append(f"- **{r['id']}** — {r['method']}")
    L.append("")
    if doc["contract_findings"]:
        L.append("## Contract findings")
        L.append("")
        for x in doc["contract_findings"]:
            L.append(f"- {x}")
        L.append("")
    L.append("## Diagnostics (no threshold)")
    L.append("")
    L.append("```json")
    L.append(json.dumps(doc["diagnostics"], indent=1, sort_keys=True, allow_nan=False, ensure_ascii=False))
    L.append("```")
    L.append("")
    L.append("Self-validation and the file index are in `gate_report.json`; the verifier `b4_gate_verify.py` recomputes this judgement from the evidence and re-renders this file.")
    L.append("")
    return "\n".join(L)


def _diagnostics(doc: dict, evidence_kind: str) -> dict:
    """Values beside the rows that carry no threshold: delta2 at B* and per budget, the per-budget deltas, the deadline record."""
    d: dict = {"deadline": doc.get("deadline"), "standing_of_the_batch": doc.get("standing")}
    s = doc.get("summary")
    if isinstance(s, dict) and isinstance(s.get("per_budget"), dict):
        d["per_budget"] = {}
        for B in GRID:
            v = s["per_budget"].get(str(B))
            if isinstance(v, dict):
                d["per_budget"][str(B)] = {"delta1_O_minus_R": v.get("deltas", {}).get("delta1_O_minus_R"), "delta2_O_minus_endtoend_F": v.get("deltas", {}).get("delta2_O_minus_endtoend_F"),
                                          "F_minus_R": v.get("deltas", {}).get("F_minus_R"), "X_minus_R": v.get("deltas", {}).get("X_minus_R"), "arm_medians": {k: x.get("median") for k, x in (v.get("arm_values") or {}).items()},
                                          "base_median": (v.get("base") or {}).get("median"), "k1": v.get("k1"), "N": (v.get("required_pairs") or {}).get("N"), "power_at_N_or_last": (v.get("required_pairs") or {}).get("power_at_N_or_last")}
        if isinstance(s.get("k9"), dict):
            d["k9_per_semantic_conditional_judged"] = s["k9"].get("per_semantic")
            d["k9_per_semantic_all_panel_descriptive"] = s["k9"].get("per_semantic_all_panel")
        if isinstance(s.get("k10"), dict):
            d["k10"] = s["k10"]
    return d


# ------------------------------------------------------------------ writing a gate directory
def _write_bytes_exclusive(path: Path, data: bytes) -> dict:
    part = path.with_name(path.name + f".{os.getpid()}.part")
    with open(part, "xb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        os.link(part, path)
    finally:
        os.unlink(part)
    return {"path": path.name, "sha256": sha_bytes(data), "size": len(data)}


def gate_namespace_chain(root: Path) -> list[Path]:
    parts = Path(GATE_REL).parts
    return [root.joinpath(*parts[:i + 1]) for i in range(len(parts))]


def gate_dir_preflight(root: Path, label: str, out: Path | None, stamp: str) -> Path:
    """The gate directory: literally <root>/evidence/b4/gate/<label>_…, no symlink in the chain, not existing. Nothing is written."""
    ns = root / GATE_REL
    for anc in gate_namespace_chain(root):
        if anc.is_symlink():
            raise Refusal(f"{anc.relative_to(root)} is a symlink: the gate namespace must be a real directory chain under the root")
        if anc.exists() and not anc.is_dir():
            raise Refusal(f"{anc.relative_to(root)} exists and is not a directory")
    out_p = Path(out) if out is not None else ns / f"{label}_{stamp}"
    out_p = out_p if out_p.is_absolute() else root / out_p
    if Path(os.path.normpath(out_p)) != out_p or out_p.parent != ns:
        raise Refusal(f"the gate directory must lie directly under {GATE_REL}/ of the root, written plainly; got {out_p}")
    if not out_p.name.startswith(label + "_") or "/" in out_p.name:
        raise Refusal(f"the gate directory's name must begin with {label}_")
    if out_p.is_symlink() or out_p.exists():
        raise Refusal(f"the gate directory {out_p} exists (or is a symlink); nothing is overwritten")
    return out_p


def _create_gate_dir(root: Path, out_p: Path) -> None:
    for anc in gate_namespace_chain(root):
        if anc.is_symlink():
            raise Refusal(f"{anc.relative_to(root)} became a symlink")
        anc.mkdir(exist_ok=True)
    out_p.mkdir(exist_ok=False)
    if out_p.is_symlink() or out_p.resolve() != out_p:
        raise Refusal(f"the gate directory {out_p} does not resolve to itself")


def _tree_state(root: Path, own_rel: str | None) -> tuple[str, bool]:
    """(HEAD, clean): clean when the working tree carries nothing — or nothing but the evidence batch's own output, which is
    untracked until the archive is committed (the harness's hold_tree rule)."""
    head = sim.git(root, "rev-parse", "HEAD").strip()
    own = (own_rel.rstrip("/") + "/") if own_rel else None
    for ln in sim.porcelain(root):
        path = ln[3:].strip()
        if own is not None and ln.startswith("??") and (path == own or path.startswith(own)):
            continue
        return head, False
    return head, True


def write_judgement(root: Path, gate_out: Path, evidence_doc: dict, evidence_kind: str, evidence_rel: str, evidence_sha: str, seeds_sha, manifest_sha, synthetic_bytes: bytes | None = None) -> dict:
    """Judge the evidence and write the gate directory: the synthetic summary (when that is the evidence), gate_report.md, then
    gate_report.json binding both. The self-validation — the verifier on the evidence and the judgement, in process, before the
    report is written — is a condition of standing: findings make the verdict `invalid` (the rows stay as computed)."""
    import b4_gate_verify as gv  # imported here: the verifier imports this module
    root = Path(root).resolve()
    head, clean = _tree_state(root, evidence_rel if evidence_kind == "batch_archive" else None)
    protocol = bp.identity()                                          # this tool's method identity (refused by name when the tree is not its inventory)
    j = judge(evidence_doc, evidence_kind)
    doc = {"schema": GATE_SCHEMA[0], "schema_version": GATE_SCHEMA[1], "generated_utc": utc(), "head": head, "clean_tree": clean, "label": j["label"], "S": j["S"], "fixture": j["fixture"],
           "evidence_kind": evidence_kind, "formal": j["formal"], "formal_reasons": j["formal_reasons"],
           "standing": STANDING_FORMAL if j["formal"] else STANDING_NOT_FORMAL.format(kind=evidence_kind, label=j["label"]), "scope": SCOPE,
           "batch": {"kind": evidence_kind, "path": evidence_rel, "status": evidence_doc.get("status"), "label": evidence_doc.get("label"), "count": evidence_doc.get("count"), "fixture": evidence_doc.get("fixture"),
                     "head": evidence_doc.get("head"), "generated_utc": evidence_doc.get("generated_utc"), "sha256": evidence_sha, "seeds_sha256": seeds_sha, "manifest_sha256": manifest_sha},
           "identity": {"hypothesis_sha256": hy.HYPOTHESIS_SHA256, "certificate_sha256": bm.CERTIFICATE_SHA256, "thresholds_source": th.THRESHOLDS["source"], "gate_label": PINNED_GATE_LABEL,
                        "protocol_sha256": bp.protocol_sha256(protocol), "architecture_revision": protocol["architecture_revision"]},
           "thresholds": th.THRESHOLDS, "budget_rule": j["budget_rule"], "rows": j["rows"], "verdict": j["verdict"], "contract_findings": j["contract_findings"],
           "diagnostics": _diagnostics(evidence_doc, evidence_kind), "self_validation": {}, "files": []}
    _create_gate_dir(root, gate_out)
    files: list[dict] = []
    if evidence_kind == "synthetic_summary":
        files.append(_write_bytes_exclusive(gate_out / SYNTHETIC_JSON, synthetic_bytes))
    # the self-validation sees the document as it will be written but for the markdown's entry (rendered after the verdict is final)
    doc["files"] = [{"path": REPORT_MD, "sha256": gv.PLACEHOLDER_SHA, "size": 0}] + files
    try:
        sv_f = gv.verify_gate_dir(gate_out, doc=doc, root=root, deep=True, check_md=False)
    except Exception as exc:  # noqa: BLE001 — the verifier failing is a finding, never a pass
        sv_f = {"verifier": [f"the gate verifier raised {type(exc).__name__}: {exc}"]}
    if sv_f:
        doc["self_validation"] = sv_f
        first = next(iter(sv_f.items()))
        doc["verdict"] = {"status": "invalid", "reason": f"the judgement does not verify against its evidence: {first[0]}: {first[1][0]} ({sum(len(v) for v in sv_f.values())} findings)"}
    md = render_md(doc).encode("utf-8")
    files.insert(0, _write_bytes_exclusive(gate_out / REPORT_MD, md))
    doc["files"] = files
    f = gate_report_findings(doc)
    if f:
        # a report that cannot be validated is itself a failure: say so beside it and return exit 1 (nothing is overwritten)
        (gate_out / "gate_report.ERROR.txt").write_text("gate_report.json does not validate: " + "; ".join(f) + "\n")
        return {"status": "invalid", "exit_code": 1, "gate_out": str(gate_out), "report": doc, "report_error": f}
    sim.write_exclusive(gate_out / REPORT_JSON, doc, None)
    code = {"PASS": 0, "FAIL": 0, "invalid": 1, "incomplete": 3}[doc["verdict"]["status"]]
    return {"status": doc["verdict"]["status"], "exit_code": code, "gate_out": str(gate_out), "report": doc}


def judge_batch(root: Path, batch_dir: Path, gate_out: Path | None = None, stamp: str | None = None) -> dict:
    """The judgement of a harness batch archive (a production one, or a fixture one from the Python API) into a new gate directory."""
    root = Path(root).resolve()
    batch_dir = Path(batch_dir)
    batch_dir = batch_dir if batch_dir.is_absolute() else root / batch_dir
    try:
        rel = str(batch_dir.resolve().relative_to(root))
    except ValueError:
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"the batch directory {batch_dir} is not under the root {root}"}
    if not rel.startswith(sim.SIM_REL + "/") or rel.count("/") != 3:
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"the batch directory must lie directly under {sim.SIM_REL}/ of the root; got {rel}"}
    rp = batch_dir / "sim_report.json"
    if not batch_dir.is_dir():
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"{rel} is not a directory"}
    if not rp.is_file():
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"{rel} carries no sim_report.json (an initialisation failure or an unwritten report is not judged; the harness's record stands)"}
    raw = rp.read_bytes()
    try:
        report = json.loads(raw)
    except ValueError as exc:
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"{rel}/sim_report.json is not JSON: {exc}"}
    pf = archive_identity_findings(batch_dir)                          # FIRST: an archive of another method version (or none) is never judged by this tool
    if pf:
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"{rel}: " + "; ".join(pf[:2])}
    rf = numeric_findings(report, "sim_report") or sc.report_findings(report)
    if rf:
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"{rel}/sim_report.json does not validate: " + "; ".join(rf[:4])}
    label = report["label"]
    if not (GATE_LABEL_RE.match(label) or FIXTURE_LABEL_RE.match(label)):
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"the batch's label {label!r} is neither a gate label nor a mechanics fixture label: an exploration archive is never judged"}
    if not batch_dir.name.startswith(label + "_"):
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"the batch directory {batch_dir.name!r} is not named after its report's label {label!r}"}
    try:
        out_p = gate_dir_preflight(root, label, gate_out, stamp or utc().replace("-", "").replace(":", ""))
    except Refusal as exc:
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": str(exc)}
    seeds_sha = sha_file(batch_dir / "seeds.json") if (batch_dir / "seeds.json").is_file() else None
    manifest_sha = sha_file(batch_dir / "manifest.json") if (batch_dir / "manifest.json").is_file() else None
    try:
        return write_judgement(root, out_p, report, "batch_archive", rel, sha_bytes(raw), seeds_sha, manifest_sha)
    except (Refusal, FileExistsError) as exc:
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": str(exc)}


def archive_identity_findings(batch_dir: Path) -> list[str]:
    """The batch archive's protocol identity (its manifest's) against this tool's: empty when it is this method version; a named
    refusal otherwise (missing, malformed, another version). Total."""
    try:
        man = json.loads((Path(batch_dir) / "manifest.json").read_bytes())
    except (OSError, ValueError) as exc:
        return [f"manifest.json unreadable: {type(exc).__name__}: {exc}"]
    pr = man.get("protocol") if isinstance(man, dict) else None
    if not isinstance(pr, dict) or "identity" not in pr:
        return [bp.refusal_for_missing(man if isinstance(man, dict) else {})]
    try:
        mine = bp.identity()
    except bp.IdentityRefusal as exc:
        return [f"this tool's own tree is not its inventory: {exc}"]
    f = bp.compare(pr["identity"], mine)
    if f:
        return f
    if pr.get("protocol_sha256") != bp.protocol_sha256(mine):
        return ["the archive's protocol_sha256 is not the digest of this method version"]
    return []


def judge_synthetic(root: Path, doc: dict, gate_out: Path | None = None) -> dict:
    """Python API only: the judgement of a synthetic summary document (b4-mech label, fixture true, marked synthetic) into a gate
    directory — the PASS path and every row's FAIL path exercised end to end; never a gate result."""
    f = synthetic_findings(doc)
    if f:
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": "the synthetic summary is refused: " + "; ".join(f)}
    root = Path(root).resolve()
    try:
        out_p = gate_dir_preflight(root, doc["label"], gate_out, utc().replace("-", "").replace(":", ""))
    except Refusal as exc:
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": str(exc)}
    raw = sim.json_text(doc)
    try:
        return write_judgement(root, out_p, doc, "synthetic_summary", f"{GATE_REL}/{out_p.name}/{SYNTHETIC_JSON}", sha_bytes(raw), None, None, synthetic_bytes=raw)
    except (Refusal, FileExistsError) as exc:
        return {"status": "refused", "exit_code": 2, "gate_out": None, "reason": str(exc)}


# ------------------------------------------------------------------ the gate run: the batch, then the judgement
def run_gate(root: Path, label: str, count: int, deadline_s: int, *, out_batch: Path | None = None, out_gate: Path | None = None, clock=time.monotonic, port_factory=None,
             schedule: sim.FixtureSchedule | None = None) -> dict:
    """The batch (b4_sim.run_batch in mode gate) and then its judgement. Production: the pinned gate label and S = 200 only; the
    harness derives the gate's master and pairs (section 9.2) — withheld until ruled. A FixtureSchedule (Python API) runs a
    b4-mech batch and judges it with formal = false."""
    root = Path(root).resolve()
    if schedule is None:
        if label in bs.CONSUMED_LABELS or label in bs.RETIRED_LABELS:
            return {"status": "refused", "exit_code": 2, "out": None, "gate_out": None, "reason": f"the label {label!r} is {'consumed by its archived records' if label in bs.CONSUMED_LABELS else 'retired'} (section 9.2): never derived again; the pinned gate label is {PINNED_GATE_LABEL!r}"}
        if label != PINNED_GATE_LABEL:
            return {"status": "refused", "exit_code": 2, "out": None, "gate_out": None, "reason": f"the production gate label is the pinned {PINNED_GATE_LABEL!r} (section 9.2); {label!r} needs a revision of the thresholds table"}
        if count != S_GATE:
            return {"status": "refused", "exit_code": 2, "out": None, "gate_out": None, "reason": f"the formal gate plans S = {S_GATE} (K6); --seeds {count!r} is not it, and S is never changed to repair a row"}
    stamp = utc().replace("-", "").replace(":", "")
    try:
        gate_dir_preflight(root, label, out_gate, stamp)
    except Refusal as exc:
        return {"status": "refused", "exit_code": 2, "out": None, "gate_out": None, "reason": str(exc)}
    batch_out = Path(out_batch) if out_batch is not None else root / sim.SIM_REL / f"{label}_{stamp}"
    res = sim.run_batch(root, label, count, deadline_s, batch_out, clock=clock, port_factory=port_factory, schedule=schedule, mode="gate")
    if res["status"] in ("refused", "init_failed"):
        return {"status": res["status"], "exit_code": res["exit_code"], "out": res["out"], "gate_out": None, "reason": res.get("reason"), "batch": res}
    gate_out_p = Path(out_gate) if out_gate is not None else root / GATE_REL / f"{label}_{stamp}"
    g = judge_batch(root, Path(res["out"]), gate_out_p, stamp)
    g["out"] = res["out"]
    g["batch"] = {k: v for k, v in res.items() if k in ("status", "exit_code", "out", "reason", "report_error")}
    return g


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="B4 formal gate tool (unit 2b-4). Production only: the pinned gate label, S = 200, a clean tree; no fixture path. "
                                             "Running the production gate needs the owner's separate authorisation.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="the batch under the gate label (b4_sim, mode gate) and then its judgement")
    r.add_argument("--label", required=True, help=f"the pinned gate label {PINNED_GATE_LABEL} only")
    r.add_argument("--seeds", required=True, type=int, help=f"S = {S_GATE} only (K6)")
    r.add_argument("--deadline-s", required=True, type=int, help="the soft monotonic deadline in seconds (no default)")
    r.add_argument("--out-batch", default=None, help=f"the batch directory, directly under {sim.SIM_REL}/; default <label>_<UTC>")
    r.add_argument("--out-gate", default=None, help=f"the gate directory, directly under {GATE_REL}/; default <label>_<UTC>")
    jp = sub.add_parser("judge", help="the judgement of an existing production batch archive (runs nothing)")
    jp.add_argument("batch_dir")
    jp.add_argument("--out-gate", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        res = run_gate(REPO_ROOT, a.label, a.seeds, a.deadline_s, out_batch=Path(a.out_batch) if a.out_batch else None, out_gate=Path(a.out_gate) if a.out_gate else None)
    else:
        rp = Path(a.batch_dir)
        rp = rp if rp.is_absolute() else REPO_ROOT / rp
        # the CLI judges production archives only, on a clean tree; a fixture archive is the Python API's
        try:
            dirty = sim.porcelain(REPO_ROOT)
        except sim.Refusal as exc:
            dirty = [str(exc)]
        if dirty:
            res = {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"the tree is not clean ({len(dirty)} entries); there is no override"}
        elif not rp.name.startswith(PINNED_GATE_LABEL + "_"):
            res = {"status": "refused", "exit_code": 2, "gate_out": None, "reason": f"the CLI judges the production archive {PINNED_GATE_LABEL}_… only; a fixture archive is judged through the Python API with formal = false"}
        else:
            res = judge_batch(REPO_ROOT, rp, Path(a.out_gate) if a.out_gate else None)
    print(json.dumps({k: v for k, v in res.items() if k in ("status", "exit_code", "out", "gate_out", "reason", "report_error")}, indent=1))
    return res["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
