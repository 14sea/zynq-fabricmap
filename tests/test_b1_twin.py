"""The B1 C cartographer against the Python reference — probe by probe, record by record,
map byte for byte, over simulated fabrics (the discipline of the instrument's
test_firmware_twin.py).

The twin (`firmware/b1/build/b1_twin`) is compiled from the SAME b1_carto.c the image links.
It is driven over a pipe: for every proposal it prints the probe, the harness answers with
the fabric's readout (or UNSCORED), and the twin's record blocks and final map must equal
the reference's. Fixtures: the truth mapping, a permuted mapping, a dropout mapping and an
injected interaction; budgets that end in every phase; an unscored probe in each phase.
The RNG is also checked against the instrument's `l6_operators.Rng` when the instrument
is present. Skipped only without a host C compiler — and the skip says so."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402

FW = R / "firmware/b1"
TWIN = FW / "build/b1_twin"
HAVE_CC = shutil.which(os.environ.get("CC", "cc")) is not None


def build_twin() -> None:
    p = subprocess.run(["make", "-s", "twin"], cwd=FW, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stdout + p.stderr)


def drive_twin(seed: int, budget: int, fabric, unscored=None) -> dict:
    """Run the C twin over `fabric`; returns probes, records and the map exactly as printed."""
    p = subprocess.Popen([str(TWIN), "carto"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert p.stdin and p.stdout
    p.stdin.write(f"{seed} {budget}\n"); p.stdin.flush()
    probes, records, final = [], [], None
    while True:
        line = p.stdout.readline()
        if not line:
            break
        parts = line.rstrip("\n").split(" ", 3)
        if parts[0] == "PROBE":
            kind, seq, ghex = int(parts[1]), int(parts[2]), parts[3]
            probes.append({"kind": kind, "seq": seq, "genome": ghex})
            if unscored and unscored(seq):
                p.stdin.write("UNSCORED\n"); p.stdin.flush()
                continue
            t = fabric(bc.genome_from_hex(ghex))
            p.stdin.write(" ".join(f"{x:016x}" for x in t) + "\n"); p.stdin.flush()
        elif parts[0] == "REC":
            records.append({"seq": int(parts[1]), "carto": line.rstrip("\n").split(" ", 2)[2]})
        elif parts[0] == "MAP":
            final = {"map_sha256": parts[1], "map": line.rstrip("\n").split(" ", 2)[2]}
    p.stdin.close()
    rc = p.wait(timeout=60)
    p.stdout.close()
    if rc != 0 or final is None:
        raise RuntimeError(f"twin exited {rc}")
    return {"probes": probes, "records": records, **final}


@unittest.skipUnless(HAVE_CC, "no host C compiler: the twin cannot be built (this is a skip, not a pass)")
class Twin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_twin()
        cls.truth = bm.truth_mapping()

    def compare(self, seed: int, budget: int, fab_c, fab_py, unscored=None):
        c = drive_twin(seed, budget, fab_c, unscored)
        py = bm.simulate(seed, budget, fab_py, unscored)
        # the probe sequence, the records and the map are byte-identical
        self.assertEqual([(p["kind"], p["seq"], p["genome"]) for p in c["probes"]],
                         [(p["kind"], p["seq"], p["genome"]) for p in py["probes"]])
        self.assertEqual([(r["seq"], r["carto"]) for r in c["records"]], [(r["seq"], r["carto"]) for r in py["records"]])
        self.assertEqual(c["map"], py["map"])
        self.assertEqual(c["map_sha256"], py["map_sha256"])
        return c, py

    def test_truth_full_budget(self):
        c, py = self.compare(1234, 400, bm.fixture("truth"), bm.fixture("truth"))
        self.assertEqual(len(c["probes"]), 9 + 292 + 32)
        m = py["carto"]
        self.assertEqual(m.anomalies, 0)
        self.assertTrue(all(e.state == bc.ST_CONFIRMED for e in m.e))
        self.assertTrue(all((e.lut, e.init) == self.truth["mapping"][i] for i, e in enumerate(m.e)))

    def test_budget_ends_in_every_phase(self):
        for budget in (5, 9, 10, 40, 301, 320):
            with self.subTest(budget=budget):
                c, py = self.compare(77, budget, bm.fixture("truth"), bm.fixture("truth"))
                self.assertEqual(len(c["probes"]), budget)

    def test_permuted_dropout_interaction_fixtures(self):
        for kind, seed in (("permuted", 1), ("permuted", 9), ("dropout", 2), ("interact", 3)):
            with self.subTest(fixture=kind, seed=seed):
                self.compare(4321, 400, bm.fixture(kind, seed), bm.fixture(kind, seed))

    def test_unscored_probes_in_every_phase(self):
        drop = {3, 12, 200, 330}                    # seqs the board did not score: one per phase and one late
        def unscored(seq, hit={"n": 0}):
            return seq in drop
        c, py = self.compare(99, 400, bm.fixture("truth"), bm.fixture("truth"), unscored=unscored)
        # the same proposal is re-issued after an unscored attempt: the record seqs stay contiguous
        seqs = [r["seq"] for r in c["records"]]
        self.assertEqual(seqs, list(range(2, 2 + len(seqs))))
        self.assertEqual(py["carto"].anomalies, 0)

    def test_two_seeds_differ_only_in_the_rng_drawn_orders(self):
        a = bm.simulate(1, 400, bm.fixture("truth"))
        b = bm.simulate(2, 400, bm.fixture("truth"))
        self.assertEqual([p["genome"] for p in a["probes"][:9]], [p["genome"] for p in b["probes"][:9]])
        self.assertNotEqual([p["genome"] for p in a["probes"][9:]], [p["genome"] for p in b["probes"][9:]])
        self.assertNotEqual(a["map_sha256"], b["map_sha256"])       # the seed and evidence seqs are in the map

    def test_same_seed_replays_bit_for_bit(self):
        a = bm.simulate(5, 400, bm.fixture("truth"))
        b = bm.simulate(5, 400, bm.fixture("truth"))
        self.assertEqual(a["map"], b["map"])
        self.assertEqual([p["genome"] for p in a["probes"]], [p["genome"] for p in b["probes"]])


class RngTwin(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, "no host C compiler")
    def test_c_rng_equals_the_reference(self):
        build_twin()
        lines = [f"{s} {n}" for s, n in ((1, 292), (1278628687, 6), (0xFFFFFFFF, 2), (0, 51))]
        p = subprocess.run([str(TWIN), "rng"], input="\n".join(lines) + "\n", capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        for line, (s, n) in zip(p.stdout.splitlines(), ((1, 292), (1278628687, 6), (0xFFFFFFFF, 2), (0, 51))):
            r = bc.Rng(s)
            self.assertEqual(line, f"{r.next32():08x} {r.uniform(n)}")

    def test_reference_rng_equals_the_instruments(self):
        try:
            import claimb_r1p_instrument as inst
            inst.bind(inst.DEFAULT_ROOT, require_git=False)
            import l6_operators as lo
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"instrument not bound: {exc}")
        for seed in (1, 2, 1281816666, 0xDEADBEEF):
            a, b = bc.Rng(seed), lo.Rng(seed)
            self.assertEqual([a.next32() for _ in range(50)], [b.next32() for _ in range(50)])
            self.assertEqual(a.sample(list(range(292)), 40), b.sample(list(range(292)), 40))


if __name__ == "__main__":
    unittest.main()
