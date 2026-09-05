"""The B1 session orchestration — the C orchestrator (`b1_orch.c`, the unit b1_app.c main
drives) against the Python reference `b1_carto.session_run`, whole sessions: opening
baseline, probes, closing baseline, with the binding.

This is the test the first B1 image lacked (owner's review 2026-09-05, blocker 2): the
cartographer was initialised AFTER the opening baseline, so the opening record's
commitment was the zero struct's hash; a unit test of the cartographer cannot see the
order, only a test of the sequence can. Here the C sequence and the Python sequence must
agree record for record — the opening record's block included — and a log built with the
old order must be caught by the adjudicator's replay (the regression)."""
from __future__ import annotations

import json
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
TOKEN = "a13f38b53355fd4c1cac3145244727f8"
UNIVERSE = bm.universe_sha256()
IMAGE_LO32 = 0x12345678


def build_twin() -> None:
    p = subprocess.run(["make", "-s", "twin"], cwd=FW, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stdout + p.stderr)


def drive_session(seed: int, budget: int, fabric, unscored=None, token=TOKEN, universe=UNIVERSE, image_lo32=IMAGE_LO32) -> dict:
    p = subprocess.Popen([str(TWIN), "session"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert p.stdin and p.stdout
    p.stdin.write(f"{seed} {budget} {token} {universe} {image_lo32:x}\n"); p.stdin.flush()
    cands, records, final = [], [], None
    while True:
        line = p.stdout.readline()
        if not line:
            break
        parts = line.rstrip("\n").split(" ", 4)
        if parts[0] == "CAND":
            is_b, kind, seq, ghex = int(parts[1]), int(parts[2]), int(parts[3]), parts[4]
            cands.append({"is_baseline": is_b, "kind": kind, "seq": seq, "genome": ghex})
            if unscored and unscored(seq):
                p.stdin.write("UNSCORED\n"); p.stdin.flush()
                continue
            t = fabric(bc.genome_from_hex(ghex))
            p.stdin.write(" ".join(f"{x:016x}" for x in t) + "\n"); p.stdin.flush()
        elif parts[0] == "REC":
            records.append({"seq": int(parts[1]), "carto": line.rstrip("\n").split(" ", 2)[2]})
        elif parts[0] == "MAP":
            final = {"map_sha256": parts[1], "map": line.rstrip("\n").split(" ", 2)[2]}
    p.stdin.close(); rc = p.wait(timeout=120); p.stdout.close()
    if rc != 0 or final is None:
        raise RuntimeError(f"twin exited {rc}")
    return {"cands": cands, "records": records, **final}


@unittest.skipUnless(HAVE_CC, "no host C compiler")
class Session(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_twin()

    def compare(self, seed, budget, kind="truth", fseed=0, unscored=None):
        c = drive_session(seed, budget, bm.fixture(kind, fseed), unscored)
        py = bm.simulate(seed, budget, bm.fixture(kind, fseed), unscored, token=TOKEN, universe=UNIVERSE, image_lo32=IMAGE_LO32)
        self.assertEqual([(x["seq"], x["carto"]) for x in c["records"]], [(x["seq"], x["carto"]) for x in py["records"]])
        scored = [x for x in c["cands"] if not (unscored and unscored(x["seq"]))]
        self.assertEqual([(x["seq"], x["genome"], x["is_baseline"]) for x in scored],
                         [(x["seq"], x["genome"], int(x["is_baseline"])) for x in py["records"]])
        self.assertEqual(c["map"], py["map"])
        self.assertEqual(c["map_sha256"], py["map_sha256"])
        return c, py

    def test_whole_session_matches_record_for_record(self):
        c, py = self.compare(1123460948, 333)
        self.assertEqual(len(c["records"]), 335)
        first, last = json.loads(c["records"][0]["carto"]), json.loads(c["records"][-1]["carto"])
        self.assertEqual((first["phase"], first["probes_issued"]), ("baseline", 0))
        self.assertEqual((last["phase"], last["probes_issued"]), ("baseline", 333))
        self.assertEqual(last["map_sha256"], c["map_sha256"], "the closing record commits to the final map")

    def test_opening_record_commits_to_the_initialised_bound_state(self):
        """The regression for the init-order defect: the opening block's hash is the hash of a
        freshly initialised, BOUND cartographer — not of a zero struct, and not of an
        unbound one."""
        c, py = self.compare(5, 12)
        first = json.loads(c["records"][0]["carto"])
        fresh = bc.Carto(5, 12); fresh.bind(TOKEN, UNIVERSE, IMAGE_LO32); fresh.render()
        self.assertEqual(first["map_sha256"], fresh.map_sha256)
        zero = bc.Carto(0, 0); zero.render()
        self.assertNotEqual(first["map_sha256"], zero.map_sha256)
        unbound = bc.Carto(5, 12); unbound.render()
        self.assertNotEqual(first["map_sha256"], unbound.map_sha256)

    def test_fixtures_and_budgets(self):
        for kind, fseed, budget in (("permuted", 1, 333), ("dropout", 2, 40), ("interact", 3, 333), ("truth", 0, 9)):
            with self.subTest(fixture=kind, budget=budget):
                self.compare(77, budget, kind, fseed)

    def test_an_unscored_probe_ends_the_session_without_a_closing_baseline(self):
        """As b1_app.c main: a candidate that was not SCORED ends the epoch; the records stop
        there, the map is what was learned before it, and both sides agree."""
        c, py = self.compare(9, 40, unscored=lambda seq: seq == 12)
        seqs = [r["seq"] for r in c["records"]]
        self.assertEqual(seqs, list(range(1, 12)))
        self.assertTrue(py["stopped"])
        self.assertEqual(json.loads(c["records"][-1]["carto"])["phase"], "confirm")   # seq 11 = the first single after the 9 code probes

    def test_binding_changes_the_map_hash_but_not_the_content(self):
        a = bm.simulate(3, 20, bm.fixture("truth"), token="aa" * 16, image_lo32=1)
        b = bm.simulate(3, 20, bm.fixture("truth"), token="bb" * 16, image_lo32=2)
        self.assertEqual(a["content_sha256"], b["content_sha256"])
        self.assertNotEqual(a["map_sha256"], b["map_sha256"])


if __name__ == "__main__":
    unittest.main()
