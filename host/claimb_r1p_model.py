#!/usr/bin/env python3
"""Claim B round 1′ — the host model of the instrument's fitness, and the preregistered
prediction of the whole run (host-only; nothing here touches a board).

What the pinned instrument measures. The P3 carrier's scorer (`carrier_scorer.v`, imported by
P3 at fabricmap `71666b02`) drives the six evolvable LUTs with the frozen vector order and
counts, per LUT, the vectors whose output equals that LUT's frozen target bit — over the
TRAIN slice (the first `train_count` = 40 vectors) in the mode the pinned image runs (the
image never sets `MODE_HOLDOUT`; the holdout slice of 24 is arithmetic only). A LUT's output
for vector v is INIT[v]. The base INIT is all-zero in P3's carrier (every target frame blank),
and a candidate is the base with `mutation_bits` = 4 INIT positions set. Therefore:

    fitness(candidate) = Σ_LUT #{v in train : INIT[v] == target[v]}
                       = fitness(base) + Σ_{set bits p} δ(p),
    δ(p) = +1 if p in train and target[p] = 1;  −1 if p in train and target[p] = 0;  0 if p in holdout.

The fitness is ADDITIVE over the 292 genome bits: every candidate's score is determined by
which bits it sets, each bit contributing +1, −1 or 0 independently of the others. Both
operators set exactly four bits, so a candidate's gain lies in [−4, +4] for either arm, and
the best of any block of a few hundred candidates is +4 for both arms with overwhelming
probability. Same-LUT locality — the one thing the map-guided operator knows — cannot change
an additive score. The only difference between the arms' score distributions is how they
weight LUTs (random-safe: by mapped-bit count; map-guided: uniformly), an artefact of the
base's agreement pattern that this module computes exactly.

`predict_scores` is P3's own predictor (`zynq-psoracle/host/p3_oracle.py`), the one that
matched all 12 570 S #3 records exactly (`docs/claimb_l6_package.md` §… / this round's
package §2); this module adds the per-bit table, the operator twins' schedule, the block
statistics of the preregistered metrics, and the exact expectations. The prediction is
written to `evidence/claimb_round1prime/model_prediction.json` and its sha256 pinned in the
manifest BEFORE any board contact: the run is then compared against it, candidate by
candidate.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

TOOL_VERSION = "claimb_r1p_model.py/0.1.0"
ARM_A, ARM_B = "random_safe", "map_guided"
BLOCK_PAIRS = 367          # pairs per block (16 blocks × 367 = 5872 pairs of the 5876 planned)
BLOCKS = 16
SIGN_THRESHOLD = 12        # one-sided sign test over 16 blocks: P(X ≥ 12 | p = 1/2) = 0.0384 < 0.05


class ModelError(Exception):
    pass


def _bind(root: Path | None = None, require_git: bool = True):
    inst.bind(root or inst.DEFAULT_ROOT, require_git=require_git)
    import l6_operators as lo  # noqa: E402
    import l6_schedule as ls  # noqa: E402
    import p3_gate as g  # noqa: E402
    import p3_genome as gn  # noqa: E402
    import p3_oracle as po  # noqa: E402
    return lo, ls, g, gn, po


class Model:
    """The pinned constants, the per-bit table and the two operators, from the instrument."""

    def __init__(self, root: Path | None = None, require_git: bool = True):
        lo, ls, g, gn, po = _bind(root, require_git)
        self.lo, self.ls, self.g, self.gn, self.po = lo, ls, g, gn, po
        self.consts = po.load_constants()
        self.phen = g.load_manifest()
        self.data = lo.operator_data(self.phen, lo.load_local_map())
        self.operator_data_sha256 = lo.operator_data_sha256(self.data)
        self.addresses = gn.addresses(self.phen)
        self.base_tables = [l["base_init"] for l in self.consts["luts"]]
        self.base_train = po.predict_scores(self.base_tables, self.consts, False)
        self.base_holdout = po.predict_scores(self.base_tables, self.consts, True)
        self.delta = self._bit_table()

    def _bit_table(self) -> list[dict]:
        order, n = self.consts["order"], self.consts["train_count"]
        train = set(order[:n])
        index_of = {a: i for i, a in enumerate(self.addresses)}
        table: list[dict | None] = [None] * len(self.addresses)
        for l in self.consts["luts"]:
            for idx, addr in l["positions"].items():
                gb = index_of[addr]
                tbit = (l["target"] >> idx) & 1
                base_bit = (l["base_init"] >> idx) & 1
                # setting the bit changes INIT[idx] from base_bit to 1: a gain iff it now
                # agrees with the target where it did not, a loss iff the reverse
                if base_bit == 1:
                    d = 0
                else:
                    d = 1 if tbit == 1 else -1
                table[gb] = {"genome_bit": gb, "lut": l["index"], "init_index": idx,
                             "address": f"{addr[0]:#010x}/{addr[1]}/{addr[2]}", "target_bit": tbit,
                             "d_train": d if idx in train else 0, "d_holdout": 0 if idx in train else d}
        if any(t is None for t in table):
            raise ModelError("a genome bit is mapped to no LUT position")
        return table  # type: ignore[return-value]

    # ---- per candidate ----------------------------------------------------------------
    def tables_of(self, genome: int) -> list[int]:
        return self.po.expected_tables(self.gn.frames_from_genome(genome, self.phen), self.consts)

    def predict(self, genome: int, holdout: bool = False) -> list[int]:
        """P3's own predictor over the candidate's expected truth tables (the exact path)."""
        return self.po.predict_scores(self.tables_of(genome), self.consts, holdout)

    def delta_of(self, genome: int) -> tuple[int, int]:
        dt = dh = 0
        for i in range(len(self.delta)):
            if genome >> i & 1:
                dt += self.delta[i]["d_train"]
                dh += self.delta[i]["d_holdout"]
        return dt, dh

    def bits_of(self, genome: int) -> list[int]:
        return [i for i in range(len(self.delta)) if genome >> i & 1]

    # ---- the schedule and its prediction ---------------------------------------------
    def schedule_rows(self, master_seed: int, n: int) -> list[dict]:
        rows = []
        for r in self.ls.schedule(master_seed, n, self.ls.MODE_ABBA):
            genome = self.lo.OPERATORS[r["arm"]](r["seed"], self.data)
            dt, dh = self.delta_of(genome)
            rows.append({**r, "genome": self.gn.to_hex(genome), "bits": self.bits_of(genome),
                         "d_train": dt, "d_holdout": dh,
                         "fitness_train": sum(self.base_train) + dt, "fitness_holdout": sum(self.base_holdout) + dh})
        return rows

    def exact_expectations(self) -> dict:
        """E[d_train] per candidate under each operator, exactly: random-safe draws 4 of 292
        without replacement (linear: 4 × mean δ); map-guided draws a LUT uniformly then 4
        of its mapped positions without replacement (4 × mean over LUTs of mean δ in LUT)."""
        by_lut: dict[int, list[int]] = {}
        for t in self.delta:
            by_lut.setdefault(t["lut"], []).append(t["d_train"])
        mean_all = statistics.fmean(t["d_train"] for t in self.delta)
        mean_lut = statistics.fmean(statistics.fmean(v) for v in by_lut.values())
        k = self.data["mutation_bits"]
        return {"mutation_bits": k, "random_safe_E_d_train": k * mean_all, "map_guided_E_d_train": k * mean_lut,
                "difference_B_minus_A": k * (mean_lut - mean_all),
                "per_lut_mean_d_train": {str(l): statistics.fmean(v) for l, v in sorted(by_lut.items())},
                "per_lut_bits": {str(l): len(v) for l, v in sorted(by_lut.items())},
                "why": "additive fitness: an operator's expected gain is mutation_bits × the mean per-bit δ under "
                       "its bit-selection law; the arms differ only in how they weight LUTs"}


# ---- the preregistered metrics (shared by the prediction and the adjudicator) --------------

def metrics(rows: list[dict], block_pairs: int = BLOCK_PAIRS, blocks: int = BLOCKS,
            key: str = "d_train") -> dict:
    """`rows`: one per candidate with `pair`, `arm`, and the statistic `key` (a gain over
    the base). Primary: per block of `block_pairs` consecutive pairs, best-of-block per arm,
    difference B − A; the sign count over `blocks` blocks. Secondary: the per-pair paired
    difference B − A, its mean, and the pair-level sign counts. Pairs beyond the blocks are
    in the secondary only."""
    by_pair: dict[int, dict[str, int]] = {}
    for r in rows:
        by_pair.setdefault(int(r["pair"]), {})[r["arm"]] = int(r[key])
    complete = {p: v for p, v in by_pair.items() if ARM_A in v and ARM_B in v}
    pairs = sorted(complete)
    need = block_pairs * blocks
    if len(pairs) < need:
        raise ModelError(f"{len(pairs)} complete pairs < {blocks} blocks × {block_pairs}")
    block_rows = []
    for b in range(blocks):
        ps = pairs[b * block_pairs:(b + 1) * block_pairs]
        best_a = max(complete[p][ARM_A] for p in ps)
        best_b = max(complete[p][ARM_B] for p in ps)
        block_rows.append({"block": b, "pairs": [ps[0], ps[-1]], "best_random_safe": best_a,
                           "best_map_guided": best_b, "difference": best_b - best_a})
    pos = sum(1 for r in block_rows if r["difference"] > 0)
    neg = sum(1 for r in block_rows if r["difference"] < 0)
    ties = blocks - pos - neg
    diffs = [complete[p][ARM_B] - complete[p][ARM_A] for p in pairs]
    return {"statistic": key, "block_pairs": block_pairs, "blocks": blocks, "pairs_complete": len(pairs),
            "pairs_in_blocks": need, "pairs_beyond_blocks": len(pairs) - need,
            "primary": {"rule": f"map-guided better iff ≥ {SIGN_THRESHOLD} of {blocks} blocks have best_B − best_A > 0 "
                                f"(one-sided sign test, ties count against; P(X ≥ {SIGN_THRESHOLD} | p = 1/2) = 0.0384)",
                        "blocks": block_rows, "positive": pos, "negative": neg, "ties": ties,
                        "map_guided_better": pos >= SIGN_THRESHOLD},
            "secondary": {"mean_paired_difference": statistics.fmean(diffs), "pairs": len(diffs),
                          "positive": sum(1 for d in diffs if d > 0), "negative": sum(1 for d in diffs if d < 0),
                          "ties": sum(1 for d in diffs if d == 0),
                          "mean_random_safe": statistics.fmean(complete[p][ARM_A] for p in pairs),
                          "mean_map_guided": statistics.fmean(complete[p][ARM_B] for p in pairs)}}


def histogram(values) -> dict:
    out: dict[str, int] = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: int(kv[0])))


def prediction(model: Model, master_seed: int, n: int, manifest: dict) -> dict:
    rows = model.schedule_rows(master_seed, n)
    m_train = metrics(rows, key="d_train")
    m_hold = metrics(rows, key="d_holdout")
    per_arm = {}
    for arm in (ARM_A, ARM_B):
        v = [r["d_train"] for r in rows if r["arm"] == arm]
        h = [r["d_holdout"] for r in rows if r["arm"] == arm]
        per_arm[arm] = {"candidates": len(v), "mean_d_train": statistics.fmean(v), "hist_d_train": histogram(v),
                        "mean_d_holdout": statistics.fmean(h), "hist_d_holdout": histogram(h),
                        "best_d_train": max(v), "best_d_holdout": max(h)}
    return {"schema": "claimb_r1p_model_prediction", "schema_version": "1.0.0", "tool": TOOL_VERSION,
            "pins": {"psoracle_commit": manifest["instrument"]["psoracle_commit"],
                     "operator_data_sha256": model.operator_data_sha256,
                     "carrier_constants_sha256": manifest["fabricmap_artifacts"]["carrier_constants"]["sha256"],
                     "local_map_sha256": manifest["fabricmap_artifacts"]["local_map"]["sha256"],
                     "image_sha256": manifest["instrument"]["image_sha256"]},
            "master_seed": master_seed, "n": n, "mode": "abba", "mutation_bits": model.data["mutation_bits"],
            "scorer": {"train_count": model.consts["train_count"], "holdout_count": model.consts["holdout_count"],
                       "measured_slice": "train (the pinned image never sets MODE_HOLDOUT; holdout is arithmetic only)"},
            "base_scores": {"train": model.base_train, "holdout": model.base_holdout,
                            "train_sum": sum(model.base_train), "holdout_sum": sum(model.base_holdout)},
            "bit_table": model.delta,
            "bit_table_summary": {f"d_train {dt:+d}, d_holdout {dh:+d}": sum(1 for t in model.delta if (t["d_train"], t["d_holdout"]) == (dt, dh))
                                  for dt, dh in ((1, 0), (-1, 0), (0, 1), (0, -1))},
            "exact_expectations": model.exact_expectations(),
            "per_arm": per_arm,
            "metrics_train": m_train, "metrics_holdout_arithmetic": m_hold,
            "predicted_outcome": {
                "primary_map_guided_better": m_train["primary"]["map_guided_better"],
                "primary_positive_blocks": m_train["primary"]["positive"],
                "primary_ties": m_train["primary"]["ties"],
                "secondary_mean_paired_difference": m_train["secondary"]["mean_paired_difference"],
                "reading": ("falsifier 1 fires by arithmetic: the additive fitness saturates best-of-block at +4 "
                            "for both arms; the secondary's sign is the LUT-weighting artefact, not navigation")},
            "candidates": [{"index": r["index"], "seq": r["seq"], "pair": r["pair"], "seed": r["seed"], "arm": r["arm"],
                            "genome": r["genome"], "bits": r["bits"], "d_train": r["d_train"], "d_holdout": r["d_holdout"],
                            "scores_train": None} for r in rows]}


def fill_scores(model: Model, pred: dict) -> None:
    """The six predicted counters per candidate through P3's exact predictor (slow path:
    frames → tables → counters), and the cross-check that the additive table agrees."""
    for c in pred["candidates"]:
        genome = model.gn.from_hex(c["genome"])
        s = model.predict(genome, False)
        if sum(s) - pred["base_scores"]["train_sum"] != c["d_train"]:
            raise ModelError(f"seq {c['seq']}: the exact predictor and the additive table disagree")
        c["scores_train"] = s


def sha256_text(obj: dict) -> tuple[str, str]:
    text = json.dumps(obj, indent=1, sort_keys=True) + "\n"
    return text, hashlib.sha256(text.encode()).hexdigest()


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, default=inst.MANIFEST)
    ap.add_argument("--plan", type=Path, default=REPO_ROOT / "evidence/claimb_round1prime/plan.json")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "evidence/claimb_round1prime/model_prediction.json")
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args(argv)
    manifest = json.loads(a.manifest.read_text())
    plan = json.loads(a.plan.read_text())
    model = Model(require_git=not a.no_git)
    pred = prediction(model, plan["master_seed"], plan["n"], manifest)
    fill_scores(model, pred)
    pred["plan_sha256"] = hashlib.sha256(a.plan.read_bytes()).hexdigest()
    text, sha = sha256_text(pred)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    po = pred["predicted_outcome"]
    print(f"prediction {a.out} sha256 {sha}\n  N {pred['n']} seed {pred['master_seed']} base train {pred['base_scores']['train_sum']}\n"
          f"  exact E[d_train]: A {pred['exact_expectations']['random_safe_E_d_train']:.6f} B {pred['exact_expectations']['map_guided_E_d_train']:.6f}\n"
          f"  primary: positive blocks {po['primary_positive_blocks']}/{BLOCKS} ties {po['primary_ties']} -> map_guided_better {po['primary_map_guided_better']}\n"
          f"  secondary mean paired difference {po['secondary_mean_paired_difference']:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
