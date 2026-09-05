#!/usr/bin/env python3
"""B1 — the host model: a simulated fabric, the ground-truth mapping and its fixtures, and
the session simulator (host-only; nothing here touches a board).

The fabric the cartographer measures is, on the pinned P3 carrier, exactly the readout
the instrument's `p3_oracle.expected_tables` computes from a candidate's frames: setting
the whitelisted address i puts a 1 at INIT[v] of LUT k where the certificate-derived
`local_map.json` places it, and the PL's sweep reads that table back (rule (iii): the
readout equals the expected tables, on every SCORED record of every session so far). So
the truth mapping is `address i -> (k, v)`, one position per address, and the simulated
readout of a genome is the union of its addresses' positions — the additivity the
cartographer's phase C tests.

Fixtures the guards need:
  * `truth`     — the certificate's mapping (the hidden ground truth of B1);
  * `permuted`  — the same 292 positions assigned to the addresses by a seeded
    permutation: a cartographer that still outputs the truth is hard-coded, one that
    follows the fixture is measuring;
  * `dropout`   — the truth with a subset of addresses having NO effect (an unmapped bit):
    the cartographer must say no_effect, not invent a position;
  * `interact`  — the truth plus an injected interaction: one pair of addresses whose
    joint readout differs from the union (a third position lights only when both are
    set), so phase C must record a deviation.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402

LOCAL_MAP = REPO_ROOT / "gate_runs/claimb_round1_carrier_2026_08_13_erratum006/local_map.json"
PHENOTYPE = REPO_ROOT / "gate_runs/claimb_round1_carrier_2026_08_13_erratum006/phenotype_manifest.json"
# LUT index order = sorted map keys, the instrument's convention (l6_operators.operator_data)
HOLDOUT_LUTS = (4, 5)          # CLBLM_L.SLICEM_X0.ALUT / DLUT: the engineering holdout (roadmap §2 B1)


def addresses(local_map: dict | None = None) -> list[tuple[int, int, int]]:
    """The 292 addresses in canonical genome-bit order (ascending far, word, bit) — the
    instrument's p3_genome.addresses order, re-derived here from the map's universe (the
    phenotype manifest pins the map by hash and carries no address list of its own)."""
    lm = local_map or json.loads(LOCAL_MAP.read_text())
    out = []
    for e in lm["universe"]["addresses"]:
        out.append((int(e["far"], 16), int(e["word"]), int(e["bit"])))
    return sorted(out)


def truth_mapping(local_map: dict | None = None, phen: dict | None = None) -> dict:
    """address index -> (lut, init_index), lut keys sorted; plus the key list."""
    lm = local_map or json.loads(LOCAL_MAP.read_text())
    addrs = addresses(lm)
    index_of = {a: i for i, a in enumerate(addrs)}
    keys = sorted(lm["index"]["by_lut"])
    mapping: dict[int, tuple[int, int]] = {}
    for k, key in enumerate(keys):
        for row in lm["index"]["by_lut"][key]:
            far_s, w_s, b_s = row["address_key"].split("/")
            a = (int(far_s, 16), int(w_s), int(b_s))
            mapping[index_of[a]] = (k, int(row["init_index"]))
    if len(mapping) != bc.N:
        raise ValueError(f"{len(mapping)} mapped addresses, expected {bc.N}")
    return {"mapping": mapping, "lut_keys": keys, "addresses": addrs}


class Fabric:
    """readout(genome) -> six 64-bit tables under a mapping (+ optional injected interaction)."""

    def __init__(self, mapping: dict[int, tuple[int, int] | None], interaction: dict | None = None):
        self.mapping = mapping
        self.interaction = interaction    # {"a": i, "b": j, "extra": (lut, init)}
        self.calls = 0

    def __call__(self, genome: int) -> list[int]:
        self.calls += 1
        t = [0] * bc.LUTS
        for i in range(bc.N):
            if genome >> i & 1:
                pos = self.mapping.get(i)
                if pos is not None:
                    t[pos[0]] |= 1 << pos[1]
        ia = self.interaction
        if ia and (genome >> ia["a"] & 1) and (genome >> ia["b"] & 1):
            t[ia["extra"][0]] |= 1 << ia["extra"][1]
        return t


def fixture(kind: str, seed: int = 0, truth: dict | None = None) -> Fabric:
    truth = truth or truth_mapping()
    m = dict(truth["mapping"])
    rng = random.Random(seed)
    if kind == "truth":
        return Fabric(m)
    if kind == "permuted":
        positions = [m[i] for i in range(bc.N)]
        rng.shuffle(positions)
        return Fabric({i: positions[i] for i in range(bc.N)})
    if kind == "dropout":
        drop = set(rng.sample(range(bc.N), 12))
        return Fabric({i: (None if i in drop else m[i]) for i in range(bc.N)})
    if kind == "interact":
        a, b = rng.sample(range(bc.N), 2)
        used = set(m.values())
        extra = next((k, v) for k in range(bc.LUTS) for v in range(64) if (k, v) not in used)
        return Fabric(m, interaction={"a": a, "b": b, "extra": extra})
    raise ValueError(kind)


def simulate(seed: int, budget: int, fab: Fabric, unscored=None) -> dict:
    """One session of the reference cartographer over a fabric; the transcript plus the
    fabric's call count (= probes scored)."""
    r = bc.run(seed, budget, fab, unscored=unscored)
    r["probes_scored"] = fab.calls
    return r


def address_only_baseline(truth: dict) -> dict:
    """The control: what address STRUCTURE alone predicts. An address's frame identifies
    its column and its word/bit its row group, but the LUT within the tile and the INIT
    index are not functions of the address without the DB; the baseline assigns the
    LUT by the address's frame group (the twelve FARs fall into three envelopes of four,
    two LUTs each) and the INIT index by the bit's rank within the frame — the best a
    structure-only guesser can do — and is scored like a map."""
    addrs = truth["addresses"]
    by_far: dict[int, list[int]] = {}
    for i, (far, w, b) in enumerate(addrs):
        by_far.setdefault(far, []).append(i)
    fars = sorted(by_far)
    entries = []
    for i, (far, w, b) in enumerate(addrs):
        env = fars.index(far) // 4          # 0..2
        lut = env * 2 + (1 if w == 52 else 0)
        rank = sorted(by_far[far]).index(i)
        entries.append([i, lut, rank % 64, 1, "decoded", []])
    return {"anomalies": 0, "entries": entries, "pairs": [], "seed": 0, "version": "address-only-baseline"}
