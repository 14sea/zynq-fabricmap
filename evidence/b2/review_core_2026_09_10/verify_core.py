#!/usr/bin/env python3
"""Offline review of B2 stages 1/2a/2b. Host executable only; no board/image build.

Pass --twin for an independently compiled sanitizer-enabled host twin. All candidate
genomes are checked, in addition to the submitted suite's moves, fitness and blocks.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / "host"))
import b2_plan as bp
import b2_search as bs
import claimb_r1p_instrument as inst


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--twin", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("review_twin", R / "tests/test_b2_twin.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.TWIN = args.twin
    original_fabric = mod.FAB
    seeds = bp.session_seeds(9)[1]
    out = {"nominal": [], "perturbed_readout": [], "legacy_validator_scope": {}}

    def check(arm, pair, budget, fabric):
        mod.FAB = fabric
        lseed, oseed = seeds[pair]
        got = mod.drive(arm, lseed, oseed, budget, pair=pair)
        supplied_genomes = []
        class Observed:
            # The reference supports a fabric with incremental observations. Keep a
            # lookup of the injective fixture readouts to identify each parent genome.
            def __init__(self):
                self.genomes = {}
            def __call__(self, genome):
                supplied_genomes.append(genome)
                tables = fabric(genome)
                key = tuple(tables)
                assert key not in self.genomes or self.genomes[key] == genome
                self.genomes[key] = genome
                return tables
            def toggle(self, tables, bits):
                return self(bs.apply_move(self.genomes[tuple(tables)], bits))
        ref = bs.run(bs.ARM_RANDOM_SAFE if arm == 0 else bs.ARM_MAP_GUIDED, got["landscape"],
                     None if arm == 0 else mod.VIEW, oseed, budget, Observed(), log_moves=True, pair=pair)
        assert [v["genome"] for v in got["evals"]] == supplied_genomes[1:]
        assert len(got["evals"]) == budget
        for c, p in zip(got["evals"], ref.moves):
            assert (c["parent_born"], c["bits"], c["kind"], c["fit"]) == (p["parent_born"], p["bits"], p["kind"], p["fit"])
        assert got["blocks"] == ref.blocks
        assert got["champion_block"] == ref.champion_block
        assert got["champion"]["genome"] == ref.champion.genome
        assert got["holdout"] == ref.champion_holdout
        return {"arm": arm, "pair": pair, "budget": budget, "all_candidate_genomes_equal": True,
                "all_blocks_equal": True, "best": ref.champion.fit}

    for pair in range(9):
        for arm in (0, 1):
            out["nominal"].append(check(arm, pair, 600, original_fabric))
    out["deltas"] = [out["nominal"][2*i+1]["best"] - out["nominal"][2*i]["best"] for i in range(9)]
    assert out["deltas"] == json.loads((R / "evidence/b2/prediction.json").read_text())["deltas"]

    changed_observations = [0]
    marker = next((k, v) for k in range(6) for v in range(64)
                  if not (mod.MASKS[k] >> v) & 1 and (k, v) != (0, mod.bl.train_vectors()[0]))
    def perturbed(genome):
        tables = list(original_fabric(genome))
        if genome:
            tables[0] ^= 1 << mod.bl.train_vectors()[0]
            tables[marker[0]] |= 1 << marker[1]  # keeps the fixture readout injective, including base
            changed_observations[0] += 1
        return tables
    for arm in (0, 1):
        for budget in (1, 8, 9, 31, 600):
            out["perturbed_readout"].append(check(arm, 0, budget, perturbed))
    assert changed_observations[0] > 0
    out["perturbed_observation_calls"] = changed_observations[0]

    raw = subprocess.run([str(args.twin), "wire"], capture_output=True, text=True, check=True)
    assert not raw.stderr, raw.stderr
    docs = {tag: json.loads(payload) for tag, payload in (line.split(" ", 1) for line in raw.stdout.splitlines())}
    inst.bind(inst.DEFAULT_ROOT, require_git=False)
    import b1_records as br
    for tag, doc in docs.items():
        br.validate(doc)
        assert json.dumps(doc, sort_keys=True, separators=(",", ":")) == next(
            line.split(" ", 1)[1] for line in raw.stdout.splitlines() if line.startswith(tag + " "))
    rec = copy.deepcopy(docs["REC"])
    rec.pop("search")
    assert "search" not in br.validate(rec)
    identity = copy.deepcopy(docs["IDENT"])
    identity.update(pair_first=99, pair_count=99, budget_per_arm=0, map_sha256="wrong")
    assert "map_sha256" not in br.validate(identity)
    out["legacy_validator_scope"] = {"common_envelope_accepted": True,
        "missing_search_accepted_and_ignored": True,
        "invalid_b2_identity_fields_accepted_and_ignored": True,
        "interpretation": "The legacy validator checks common fields only; B2-specific validation is pending."}
    out["wire_payload_bytes"] = {tag: len(line.split(" ", 1)[1]) for line in raw.stdout.splitlines() for tag in [line.split(" ", 1)[0]]}
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
