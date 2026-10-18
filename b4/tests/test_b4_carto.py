"""b4/host/b4_carto.py — the observation cartographer, closed-book and hand-checked: single-bit pairs under one
stimulus give an address its seen effects (cells and presence), a pair without a difference is "no effect seen in this
pair", both kinds make the address context-dependent, no pair leaves it unknown; multi-bit pairs are counted, never
decomposed; the version moves only when a relation changes; the view's groups follow what was SEEN (one per element,
one for multi-element addresses, nothing for unknown / no-effect); the rendered map validates against the v3 draft;
the permuted fabric's relations follow the observations, not the certificate; dropout gives no effect; a hypothesis
swap changes a relation; control X's derangement, permutation and shadow isomorphism; A0, D and Omega's privilege. No skip."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_carto as bc  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_landscape as bl  # noqa: E402

S1, S2 = "a" * 64, "b" * 64


def grid(rows):
    return [list(r) for r in rows]


class HandLedger(unittest.TestCase):
    def test_single_bit_pairs_and_the_states(self):
        c = bc.ObservationCarto(8)
        base = grid([[1] * 8, [1] * 8])
        self.assertFalse(c.ingest(1, 0, S1, base))
        self.assertEqual(c.version, 0)
        g3 = grid([[1] * 8, [1, 1, 0, 1, 1, 1, 1, 1]])                 # bit 3 set: cell (1, 2) differs
        self.assertTrue(c.ingest(2, 1 << 3, S1, g3))
        r3 = c.rel[3]
        self.assertEqual((r3.state, r3.cells, r3.presence, r3.pairs_with_effect, r3.pairs_without_effect, r3.evidence), ("effect_seen", {(1, 2)}, set(), 1, 0, [(1, 2)]))
        self.assertEqual(r3.elements, frozenset({2}))
        self.assertEqual(c.version, 1)
        self.assertTrue(c.ingest(3, 1 << 5, S1, base), "bit 5 changed nothing in this pair: the address moves from unknown to no_effect_seen — a map change")
        self.assertEqual((c.rel[5].state, c.rel[5].pairs_without_effect), ("no_effect_seen", 1))
        self.assertEqual(c.version, 2)
        self.assertFalse(c.ingest(4, 1 << 3, S2, grid([[0] * 8, [0] * 8])), "under another stimulus with no partner: no pair, no change")
        self.assertEqual(c.rel[3].pairs_with_effect, 1, "no pair under S2 yet")
        self.assertEqual(c.version, 2)
        self.assertTrue(c.ingest(5, 0, S2, grid([[0] * 8, [0] * 8])))          # now a pair under S2 with no difference
        self.assertEqual((c.rel[3].state, c.rel[3].pairs_with_effect, c.rel[3].pairs_without_effect, sorted(c.rel[3].contexts)), ("context_dependent", 1, 1, [S1, S2]))
        self.assertEqual(c.rel[0].state, "unknown")
        self.assertEqual(c.version, 3)
        # a two-bit specimen: against seq 1 it is a two-bit pair (counted, not decomposed); against seq 2 (bit 3 set) it differs
        # in bit 5 only (grids equal: another no-effect pair for bit 5); against seq 3 (bit 5 set) in bit 3 only (an effect pair)
        self.assertTrue(c.ingest(6, (1 << 3) | (1 << 5), S1, g3))
        self.assertEqual(c.multi_bit_pairs, 2, "seq 3 (bit 5) against seq 2 (bit 3) was already a two-bit pair; seq 6 against seq 1 is the second")
        self.assertEqual((c.rel[5].pairs_without_effect, c.rel[3].pairs_with_effect), (2, 2))
        self.assertEqual(c.rel[3].cells, {(1, 2)})

    def test_presence_cells_and_the_view(self):
        c = bc.ObservationCarto(4)
        c.ingest(1, 0, S1, grid([[1, 1, 1, 1, 1, 1, 1, 1]]))
        c.ingest(2, 1 << 1, S1, grid([[1, None, 1, None, 1, 1, 1, 1]]))        # bit 1: lanes 1 and 3 lose their readout
        self.assertEqual((c.rel[1].state, c.rel[1].presence, c.rel[1].cells, c.rel[1].elements), ("effect_seen", {(0, 1), (0, 3)}, set(), frozenset({1, 3})))
        c.ingest(3, 1 << 2, S1, grid([[0, 1, 1, 1, 1, 1, 1, 1]]))               # bit 2: element 0
        c.ingest(4, 1 << 0, S1, grid([[0, 1, 1, 1, 1, 1, 1, 1]]))               # bit 0: element 0 too
        v = c.view()
        self.assertEqual(v.groups, ((0, 2), (1,)), "one group per single element (0: bits 0 and 2), one multi-element group (bit 1); bit 3 unknown is in no group")
        self.assertEqual((v.version, v.commitment, v.privileged, v.origin), (c.version, c.commitment(), False, "learned"))
        doc = c.render({"token": "t"}, ("0x00400a00/52/16", "0x00400a01/51/7", "0x00400a01/51/19", "0x00400a01/52/3"))
        self.assertEqual(bc.schema_findings(doc), [])
        self.assertEqual(doc["groups"], [[0, 2], [1]])
        self.assertEqual(doc["semantic_claims"], [])
        self.assertIsNone(doc["host_verdict"])
        self.assertEqual(doc["relations"][3]["state"], "unknown")
        bad = dict(doc); bad["semantic_claims"] = [{"x": 1}]
        self.assertIn("semantic_claims must be empty in v0.1", bc.schema_findings(bad))
        self.assertEqual(bc.ObservationCarto(4).view().groups, (), "an empty map has no groups")
        with self.assertRaises(ValueError):
            c.ingest(9, 1 << 4, S1, grid([[0] * 8]))

    def test_the_commitment_moves_with_the_relations(self):
        a, b = bc.ObservationCarto(3), bc.ObservationCarto(3)
        self.assertEqual(a.commitment(), b.commitment())
        a.ingest(1, 0, S1, grid([[1] * 8])); a.ingest(2, 1, S1, grid([[0] * 8]))
        b.ingest(1, 0, S1, grid([[1] * 8])); b.ingest(2, 1, S1, grid([[0] * 8]))
        self.assertEqual(a.commitment(), b.commitment())
        b.ingest(3, 2, S1, grid([[1] * 8]))
        self.assertNotEqual(a.commitment(), b.commitment())
        self.assertEqual(a.history, [a.commitment()])


class OverTheModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, cls.h = bm.site_mapping(), hy.load()
        cls.task = bl.make_task(5, cls.m.addresses)
        cls.stim = list(cls.task.stimulus)
        cls.ssha = ex.sha256_json(cls.stim)

    def probes(self, fab, bits):
        """The base and single-bit flips through a port, into a fresh cartographer; returns it."""
        port = ex.ObservationPort(fab)
        c = bc.ObservationCarto(21)
        seq = 1
        c.ingest(seq, 0, self.ssha, [s["q_after"] for s in port.observe(ex.genome_to_config(0, port.addresses), self.stim)["steps"]])
        for b in bits:
            seq += 1
            c.ingest(seq, 1 << b, self.ssha, [s["q_after"] for s in port.observe(ex.genome_to_config(1 << b, port.addresses), self.stim)["steps"]])
        return c

    def test_relations_follow_the_observation_not_the_certificate(self):
        m = self.m
        bits = [m.genome_bit(m.address_of("AFF", "ff_init")), m.genome_bit(m.address_of("CFF", "ff_init")), m.genome_bit(m.address_of(None, "ce_mode"))]
        truth = self.probes(fm.fixture("truth", m, self.h), bits)
        self.assertEqual(truth.rel[bits[0]].elements, frozenset({0}), "AFF's INIT bit was seen to move AFF (index 0)")
        self.assertEqual(truth.rel[bits[1]].elements, frozenset({4}), "CFF's INIT bit moves CFF (index 4)")
        perm = fm.fixture("permuted", m, self.h, seed=3)
        permuted = self.probes(perm, bits)
        for b in bits:
            target_bit = m.genome_bit(m.address_of(*perm.effect[m.addresses[b]]))
            self.assertEqual(permuted.rel[b].doc()["affected_elements"], truth.rel[target_bit].doc()["affected_elements"] if truth.rel[target_bit].state == "effect_seen" else self.probes(fm.fixture("truth", m, self.h), [target_bit]).rel[target_bit].doc()["affected_elements"],
                             "on the permuted fabric the address carries the effect of its permuted target, not the certificate's")
        self.assertNotEqual(permuted.relations_doc(), truth.relations_doc())

    def test_dropout_gives_no_effect_and_a_swap_changes_a_relation(self):
        m = self.m
        drop = fm.fixture("dropout", m, self.h, seed=1, drop=5)
        bits = [m.genome_bit(a) for a in drop.dropout]
        c = self.probes(drop, bits)
        for b in bits:
            self.assertEqual(c.rel[b].state, "no_effect_seen", m.addresses[b])
        ce_bit = m.genome_bit(m.address_of(None, "ce_mode"))
        truth = self.probes(fm.fixture("truth", m, self.h), [ce_bit])
        swapped = self.probes(fm.fixture("ce_ungated", m, self.h), [ce_bit])
        self.assertEqual(truth.rel[ce_bit].state, "effect_seen", "with CE driven and the task's ce vectors not all high, the bit was seen")
        self.assertEqual(swapped.rel[ce_bit].state, "no_effect_seen", "under the swap CE never gates: the same bit moves nothing")


class ControlX(unittest.TestCase):
    def test_the_derangement_rule(self):
        p = bc.derangement(5)
        self.assertEqual(sorted(p), list(range(8)))
        self.assertTrue(all(p[i] != i for i in range(8)))
        self.assertEqual(p, bc.derangement(5))
        self.assertNotEqual(p, bc.derangement(6))
        # B3's rule by hand on a tiny n: each attempt from the identity, the generator continuing
        from b4_rng import Rng
        rng = Rng(5)
        while True:
            q = list(range(8))
            for i in range(7, 0, -1):
                j = rng.uniform(i + 1); q[i], q[j] = q[j], q[i]
            if all(q[i] != i for i in range(8)):
                break
        self.assertEqual(p, q)

    def test_permute_and_isomorphism(self):
        perm = bc.derangement(9)
        g = grid([[0, 1, None, 1, 0, 0, 1, None]])
        pg = bc.permute_grid(g, perm)
        for i in range(8):
            self.assertEqual(pg[0][perm[i]], g[0][i])
        x, shadow = bc.ObservationCarto(3), bc.ObservationCarto(3)
        obs = [(1, 0, grid([[1] * 8])), (2, 1, grid([[0, 1, 1, 1, 1, 1, 1, 1]])), (3, 2, grid([[1, 1, None, 1, 1, 1, 1, 1]])), (4, 4, grid([[1] * 8]))]
        for seq, genome, gr in obs:
            x.ingest(seq, genome, S1, bc.permute_grid(gr, perm)); shadow.ingest(seq, genome, S1, gr)
        self.assertEqual(bc.isomorphic(x, shadow, perm), [])
        self.assertEqual(x.rel[0].elements, frozenset({perm[0]}))
        wrong = perm[1:] + perm[:1]
        self.assertTrue(bc.isomorphic(x, shadow, wrong))
        self.assertTrue(bc.isomorphic(x, bc.ObservationCarto(3), perm))

    def test_the_attempts_are_recorded_and_the_last_is_the_derangement(self):
        """Every attempt of B3's rule is kept, the rejected ones included; checked on a seed whose rule needs more
        than one attempt (found by the rule itself, not chosen for its outcome), and against the rule by hand."""
        from b4_rng import Rng
        seed = next(s for s in range(1, 1000) if len(bc.derangement_attempts(s, 21)) >= 2)
        at = bc.derangement_attempts(seed, 21)
        self.assertGreaterEqual(len(at), 2)
        self.assertEqual(at[-1], bc.derangement(seed, 21))
        self.assertTrue(all(sorted(p) == list(range(21)) for p in at))
        self.assertTrue(all(any(p[i] == i for i in range(21)) for p in at[:-1]), "every rejected attempt had a fixed point")
        self.assertTrue(all(at[-1][i] != i for i in range(21)))
        rng, by_hand = Rng(seed), []
        while True:
            q = list(range(21))
            for i in range(20, 0, -1):
                j = rng.uniform(i + 1); q[i], q[j] = q[j], q[i]
            by_hand.append(q)
            if all(q[i] != i for i in range(21)):
                break
        self.assertEqual(at, by_hand, "the attempts are exactly the rule's, in order")

    def test_relabel_genome(self):
        perm = [2, 0, 1]
        self.assertEqual(bc.relabel_genome(0b001, perm), 0b100)
        self.assertEqual(bc.relabel_genome(0b110, perm), 0b011)
        self.assertEqual(bc.relabel_genome(0, perm), 0)
        self.assertEqual(bc.relabel_genome(0b111, perm), 0b111)
        with self.assertRaises(ValueError):
            bc.relabel_genome(0b1000, perm)
        inv = [perm.index(a) for a in range(3)]
        for g in range(8):
            self.assertEqual(bc.relabel_genome(bc.relabel_genome(g, perm), inv), g)

    def ingest_pair(self, n, perm, obs):
        x, shadow = bc.ObservationCarto(n), bc.ObservationCarto(n)
        for seq, genome, gr in obs:
            x.ingest(seq, bc.relabel_genome(genome, perm), S1, gr); shadow.ingest(seq, genome, S1, gr)
        return x, shadow

    def test_x_a_relabels_the_addresses_and_stays_isomorphic_in_full(self):
        n, perm = 3, [1, 2, 0]
        obs = [(1, 0, grid([[1] * 8])), (2, 1, grid([[0, 1, 1, 1, 1, 1, 1, 1]])), (3, 2, grid([[1, 1, None, 1, 1, 1, 1, 1]])), (4, 4, grid([[1] * 8])), (5, 3, grid([[0, 1, None, 1, 1, 1, 1, 1]]))]
        x, shadow = self.ingest_pair(n, perm, obs)
        self.assertEqual(bc.isomorphic_addresses(x, shadow, perm), [])
        self.assertEqual(x.rel[perm[0]].elements, shadow.rel[0].elements, "the effect of address 0 is credited to address perm[0]")
        self.assertEqual((x.rel[perm[0]].evidence, x.rel[perm[0]].contexts), (shadow.rel[0].evidence, shadow.rel[0].contexts))
        self.assertEqual(x.multi_bit_pairs, shadow.multi_bit_pairs)
        self.assertTrue(bc.isomorphic_addresses(x, shadow, [2, 0, 1]), "another permutation is named")
        self.assertTrue(bc.isomorphic_addresses(x, bc.ObservationCarto(n), perm))
        x.rel[perm[1]].evidence.append((9, 9))
        self.assertEqual(len(bc.isomorphic_addresses(x, shadow, perm)), 1, "one evidence reference off: named")
        self.assertEqual(bc.isomorphic_addresses(x, shadow, [0, 1]), ["the permutation is not over the cartographers' addresses"])

    def test_the_two_hand_fixtures_of_the_ruling(self):
        """A partition-CHANGING π and the partition-PRESERVING derangement counterexample (swap within every pair,
        rotate the five-address group): both keep the isomorphism; only the first changes the operator's partition.
        No test requires every π to change the partition."""
        n = 9
        # the true structure: addresses 0,1 affect element 0; 2,3 element 1; 4..8 affect elements 0 and 1 (slice-wide)
        base = grid([[1] * 8])
        def eff(*els):
            row = [1] * 8
            for e in els:
                row[e] = 0
            return grid([row])
        obs = [(1, 0, base)] + [(2 + a, 1 << a, eff(0) if a in (0, 1) else eff(1) if a in (2, 3) else eff(0, 1)) for a in range(n)]
        shadow = bc.ObservationCarto(n)
        for seq, g, gr in obs:
            shadow.ingest(seq, g, S1, gr)
        self.assertEqual([list(g) for g in shadow.view().groups], [[0, 1], [2, 3], [4, 5, 6, 7, 8]])
        changing = [1, 2, 3, 0, 5, 6, 7, 8, 4]           # {0,1} -> {1,2}: not a group any more
        preserving = [1, 0, 3, 2, 5, 6, 7, 8, 4]         # swap within the pairs, rotate the five: no fixed point, the same partition
        for perm in (changing, preserving):
            self.assertTrue(all(perm[i] != i for i in range(n)), "both are derangements")
        xc, sc = self.ingest_pair(n, changing, obs)
        self.assertEqual(bc.isomorphic_addresses(xc, sc, changing), [])
        rc = bc.residual_structure(xc.view(), sc.view())
        self.assertEqual((rc["partition_preserved"], rc["groups_moved"], rc["groups_true"], rc["groups_x"]), (False, 2, 3, 3))
        self.assertEqual(rc["x_groups"], [[1, 2], [3, 0][::-1] if False else [0, 3], [4, 5, 6, 7, 8]])
        xp, sp = self.ingest_pair(n, preserving, obs)
        self.assertEqual(bc.isomorphic_addresses(xp, sp, preserving), [])
        rp = bc.residual_structure(xp.view(), sp.view())
        self.assertEqual((rp["partition_preserved"], rp["groups_moved"]), (True, 0), "a derangement that preserves the partition: reported as such, not an error")
        self.assertEqual(rp["x_groups"], rp["true_groups"])

    def test_a0_d_and_omega(self):
        m = bm.site_mapping()
        a0 = bc.address_only_view(m.addresses)
        self.assertEqual((a0.origin, a0.privileged), ("address_only", False))
        self.assertEqual(sorted(b for g in a0.groups for b in g), list(range(21)))
        self.assertEqual(len(a0.groups), len({a.split("/")[0] for a in m.addresses}))
        omega = bc.oracle_view(m)
        self.assertTrue(omega.privileged)
        self.assertEqual(omega.origin, "oracle")
        self.assertEqual(len(omega.groups), 9, "eight elements and the slice-wide group")
        d = bc.shuffled_view(omega, 2)
        self.assertEqual([len(g) for g in d.groups], [len(g) for g in omega.groups])
        self.assertNotEqual(d.groups, omega.groups)
        self.assertEqual(sorted(b for g in d.groups for b in g), sorted(b for g in omega.groups for b in g))
        self.assertEqual((d.origin, d.privileged, d.provenance, d.base_commitment), ("shuffled", True, ("oracle", "shuffled"), omega.commitment), "a shuffled oracle keeps the oracle's privilege and chain")
        c = bc.ObservationCarto(21)
        learned = c.view()
        self.assertEqual((learned.privileged, learned.provenance), (False, ("learned",)))
        d2 = bc.shuffled_view(bc.address_only_view(m.addresses), 2)
        self.assertEqual((d2.privileged, d2.provenance), (False, ("address_only", "shuffled")))
        self.assertEqual(bc.MapView.from_dict(d.as_dict()), d)


if __name__ == "__main__":
    unittest.main()
