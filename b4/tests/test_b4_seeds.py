"""b4/host/b4_seeds.py — the seed anchor, the typed exclusion sources, the archived-set registry, the pooled set and the
`pair_seeds` copy (compared BY IMPORT of the pinned B2 original, read-only). No formal set is derived here: every master
in these tests comes from a FAKE anchor digest or a literal master value; the formal labels' masters are never computed.
The only seed literals are the exposed ones of docs/b4_architecture.md section 9.2 and values that are not seeds (masters). No skip."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_seeds as bs  # noqa: E402
import b2_search as original  # noqa: E402  (the pinned original, read-only, for the comparison only)
import b4_controls as ctl  # noqa: E402

FAKE_ANCHOR = "ab" * 32
FAKE_MASTER = 424242                   # not a seed of any run: a literal master for the derivation tests


RECEIPT_REF = {"path": bs.EXPOSURE_RECEIPT_REL, "sha256": bs.EXPOSURE_RECEIPT_SHA256, "count": 66}   # the pinned receipt, as a record names it


def seeds_doc(label: str, master: int, pairs: list, version: str = "1.2.0", anchor: str = FAKE_ANCHOR) -> dict:
    """A production-form seeds document; 1.2.0 (current) names the exposure receipt, 1.1.0 (archived before the settlement) does not."""
    ex = {"sources": [], "b4_exposed_values": [], "sim_registry": [], "pooled_total": 0}
    if version == "1.2.0":
        ex["exposure_receipt"] = dict(RECEIPT_REF)
    return {"schema": "b4_sim_seeds", "schema_version": version, "label": label, "fixture": False,
            "anchor": {"rule": "sha256(label|anchor)[:4]", "hypothesis_sha256": anchor, "label": label},
            "master_seed": master, "count": len(pairs), "pairs": pairs, "exclusion": ex, "generated_utc": "2026-10-18T00:00:00Z"}


def fixture_doc(label: str, pairs: list) -> dict:
    return {"schema": "b4_sim_seeds", "schema_version": "1.2.0", "label": label, "fixture": True,
            "anchor": {"rule": "mechanics fixture: explicit already-exposed values; no anchor", "hypothesis_sha256": None, "label": label},
            "master_seed": None, "count": len(pairs), "pairs": pairs,
            "exclusion": {"sources": [], "b4_exposed_values": [], "sim_registry": [], "exposure_receipt": dict(RECEIPT_REF), "pooled_total": 0}, "generated_utc": "2026-10-18T00:00:00Z"}


class TheAnchor(unittest.TestCase):
    def test_the_formula_by_hand_and_the_label_beside_the_anchor(self):
        want = int.from_bytes(hashlib.sha256(f"b4-fake-1|{FAKE_ANCHOR}".encode()).digest()[:4], "big")
        self.assertEqual(bs.master_seed("b4-fake-1", FAKE_ANCHOR), want)
        self.assertNotEqual(bs.master_seed("b4-fake-1", FAKE_ANCHOR), bs.master_seed("b4-fake-2", FAKE_ANCHOR), "different labels, different masters")
        self.assertNotEqual(bs.master_seed("b4-fake-1", FAKE_ANCHOR), bs.master_seed("b4-fake-1", "cd" * 32), "a different anchor is a different set")

    def test_a_pre_joined_label_and_a_malformed_anchor_are_refused(self):
        for bad in ("b4-fake-1|" + FAKE_ANCHOR, "B4-Fake", "-b4", "b4-", "b4 sim", ""):
            with self.assertRaises(ValueError, msg=bad):
                bs.master_seed(bad, FAKE_ANCHOR)
        for bad in (FAKE_ANCHOR[:-1], FAKE_ANCHOR.upper(), 12, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                bs.master_seed("b4-fake-1", bad)


class ThePairs(unittest.TestCase):
    def test_the_copy_is_b2_s_pair_seeds(self):
        for master, count, excl in ((FAKE_MASTER, 10, frozenset()), (FAKE_MASTER, 25, {7, 8, 11}), (99999, 3, {3})):
            self.assertEqual(bs.pair_seeds(master, count, excl), original.pair_seeds(master, count, excl), (master, count))

    def test_values_are_32_bit_distinct_and_never_the_excluded_ones(self):
        pairs = bs.pair_seeds(FAKE_MASTER, 40, set())
        flat = [v for p in pairs for v in p]
        self.assertEqual(len(set(flat)), 80, "all values distinct across both positions")
        self.assertTrue(all(0 <= v <= 0xFFFFFFFF for v in flat))
        self.assertTrue(not (set(flat) & set(bs.B2_EXCLUDED_SEEDS)))

    def test_the_pooled_set_screens_both_positions(self):
        base = bs.pair_seeds(FAKE_MASTER, 6, set())
        l0, o0 = base[0]
        for banned in (l0, o0):
            again = bs.pair_seeds(FAKE_MASTER, 6, {banned})
            self.assertNotIn(banned, [v for p in again for v in p], "the banned value appears in neither position")
            self.assertNotEqual(again[0], base[0], "the first draw was skipped")

    def test_a_coinciding_draw_is_skipped(self):
        class Scripted:
            def __init__(self, seed):
                self.vals = [5000, 5000, 9000, 10000]
            def next32(self):
                return self.vals.pop(0)
        with mock.patch.object(bs, "Rng", Scripted):
            self.assertEqual(bs.pair_seeds(FAKE_MASTER, 1, set()), [(9000, 10000)])

    def test_bad_arguments(self):
        with self.assertRaises(ValueError):
            bs.pair_seeds(True, 1, set())
        with self.assertRaises(ValueError):
            bs.pair_seeds(FAKE_MASTER, -1, set())


class TypedExtraction(unittest.TestCase):
    def test_paths_resolve_to_seed_ints_only(self):
        doc = {"seeds": {"master_seed": 7, "pairs": [[1, 2], [3, 4]], "sets": {"a": {"master_seed": 9, "values": 401}, "b": {"master_seed": 10, "values": 5}}},
               "rows": [{"landscape_seed": 11, "operator_seed": 12}]}
        self.assertEqual(bs.extract_ints(doc, "seeds.master_seed", "t"), [7])
        self.assertEqual(bs.extract_ints(doc, "seeds.pairs[][]", "t"), [1, 2, 3, 4])
        self.assertEqual(bs.extract_ints(doc, "seeds.sets.*.master_seed", "t"), [9, 10], "the counts beside them are never read")
        self.assertEqual(bs.extract_ints(doc, "rows[].operator_seed", "t"), [12])

    def test_a_missing_path_a_bool_a_float_an_empty_list_are_refusals(self):
        for doc, path in (({"a": {}}, "a.b"), ({"a": True}, "a"), ({"a": 1.0}, "a"), ({"a": []}, "a[]"), ({"a": {}}, "a.*"),
                          ({"a": -1}, "a"), ({"a": 1 << 32}, "a"), ({"a": "7"}, "a"), ({"a": [1, [2]]}, "a[]")):
            with self.assertRaises(bs.ExclusionSourceRefusal, msg=(doc, path)):
                bs.extract_ints(doc, path, "t")

    def test_the_python_source_must_parse_to_the_kept_copy(self):
        text = "x = 1\nEXCLUDED_SEEDS = frozenset([" + ", ".join(map(str, bs.B2_EXCLUDED_SEEDS)) + "])\n"
        self.assertEqual(bs.parse_python_excluded(text, "t"), list(bs.B2_EXCLUDED_SEEDS))
        with self.assertRaises(bs.ExclusionSourceRefusal):
            bs.parse_python_excluded(text.replace("77", "78"), "t")
        with self.assertRaises(bs.ExclusionSourceRefusal):
            bs.parse_python_excluded("nothing here", "t")


class TheHistoricalSources(unittest.TestCase):
    def test_every_source_reads_hashes_and_yields_seeds(self):
        ex = bs.load_exclusion_set(R)
        self.assertEqual(len(ex.sources), 38)
        self.assertEqual([s.path for s in ex.sources], [f[0] for f in bs.FIELDS])
        for s in ex.sources:
            self.assertGreater(len(s.values), 0, s.path)
            self.assertTrue(all(isinstance(v, int) and not isinstance(v, bool) for v in s.values), s.path)
        by = {s.path: s for s in ex.sources}
        self.assertEqual(by["host/b2_search.py"].values, bs.B2_EXCLUDED_SEEDS)
        self.assertEqual(len(by["evidence/b2/gate/raw_F1.json"].values), 400, "200 pairs, both positions")
        self.assertEqual(len(by["evidence/b3/sim/sim_report.json"].values), 1, "the master only; count and label are not seeds")
        self.assertIn(2041341936, by["evidence/b3/gate_2/gate_report.json"].values, "control_x.seed_x")
        self.assertIn(4260131137, by["evidence/b3/gate_2/gate_report.json"].values, "the b3-gate-2 master")
        self.assertEqual(ex.registry, ())
        self.assertIn("does not exist yet", ex.registry_note)

    def test_the_pool_holds_the_copy_the_exposed_values_and_every_source_value(self):
        ex = bs.load_exclusion_set(R)
        self.assertTrue(set(bs.B2_EXCLUDED_SEEDS) <= ex.values)
        self.assertTrue(set(bs.B4_EXPOSED_VALUES) <= ex.values)
        for s in ex.sources:
            self.assertTrue(set(s.values) <= ex.values, s.path)
        self.assertTrue(set(ex.receipt.values) <= ex.values, "the exposure receipt's values are pooled")
        self.assertEqual(ex.values, set(bs.B2_EXCLUDED_SEEDS) | set(bs.B4_EXPOSED_VALUES) | {v for s in ex.sources for v in s.values} | set(ex.receipt.values))
        self.assertEqual(ex.as_dict()["exposure_receipt"], {"path": bs.EXPOSURE_RECEIPT_REL, "sha256": bs.EXPOSURE_RECEIPT_SHA256, "count": len(ex.receipt.values)})
        in_sources = {v for s in ex.sources for v in s.values}
        for v in (6, 7, 8, 9, 12, 13):
            self.assertNotIn(v, in_sources, f"{v} comes only from B4's exposed values")
            self.assertIn(v, ex.values, f"{v} is pooled")
        self.assertEqual(ex.as_dict()["pooled_total"], len(ex.values))

    def test_a_rehashed_or_missing_source_is_refused_by_name(self):
        rel, paths, sha = bs.FIELDS[3]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / rel).parent.mkdir(parents=True)
            shutil.copy(R / rel, root / rel)
            self.assertEqual(bs.read_source(root, rel, paths, sha).sha256, sha)
            (root / rel).write_bytes((R / rel).read_bytes() + b"\n")
            with self.assertRaises(bs.ExclusionSourceRefusal) as cm:
                bs.read_source(root, rel, paths, sha)
            self.assertIn("hashes to", str(cm.exception))
            (root / rel).unlink()
            with self.assertRaises(bs.ExclusionSourceRefusal) as cm:
                bs.read_source(root, rel, paths, sha)
            self.assertIn("missing", str(cm.exception))

    def test_the_fields_table_is_the_architecture_s_section_9_2_table(self):
        doc = (R / "docs/b4_architecture.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| `([^`]+)` \| (.+?) \| `([0-9a-f]{64})` \|$", doc, re.M)
        table = {(p, s) for p, _, s in rows}
        self.assertEqual(table, {(p, s) for p, _, s in bs.FIELDS}, "every path and digest of FIELDS is in the table and vice versa")
        prose = {p: f for p, f, _ in rows}
        for path, paths, _ in bs.FIELDS:
            for fp in paths:
                head = fp.split(":")[-1].split("[")[0].split(".")[0]
                self.assertIn(head, prose[path], f"{path}: the field {fp}'s root is named in the table's prose")
        i = doc.index("**B4's own exposed values.**")
        para = doc[i:i + 1500]
        for v in sorted(bs.B4_EXPOSED_VALUES):
            self.assertRegex(para, rf"\*\*[^*]*\b{v}\b[^*]*\*\*", f"the exposed value {v} is listed in section 9.2")


class TheRegistry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sim = Path(self.tmp.name) / "sim"

    def write(self, name: str, fname: str, doc) -> Path:
        d = self.sim / name
        d.mkdir(parents=True, exist_ok=True)
        (d / fname).write_text(json.dumps(doc) if not isinstance(doc, (bytes, str)) else doc)
        return d

    def test_no_directory_is_not_a_missing_source(self):
        recs, note = bs.sim_registry(R, str(self.sim))
        self.assertEqual(recs, [])
        self.assertIn("does not exist yet", note)

    def test_every_archived_set_is_read_whatever_its_outcome(self):
        self.write("b4-fake-1_20261018T000000Z", "seeds.json", seeds_doc("b4-fake-1", 1000001, [[2000001, 2000002], [2000003, 2000004]]))
        self.write("b4-fake-1_20261018T000001Z", "seeds.json", seeds_doc("b4-fake-1", 1000002, [[2000005, 2000006]]))
        self.write("b4-fake-1_20261018T000002Z", "INIT_FAILED.json", {"schema": "b4_sim_init_failed", "schema_version": "1.0.0", "label": "b4-fake-1",
                                                                         "seeds_derived": False, "reason": "dirty tree", "generated_utc": "x"})
        recs, note = bs.sim_registry(R, str(self.sim))
        self.assertEqual([r.status for r in recs], ["seeds", "seeds", "init_failed_no_seeds"], "path order")
        self.assertEqual(recs[0].values, (1000001, 2000001, 2000002, 2000003, 2000004), "the master and every planned pair")
        self.assertEqual(recs[1].master_seed, 1000002)
        ex = bs.load_exclusion_set(R, str(self.sim))
        for v in (1000001, 2000001, 2000004, 1000002, 2000005, 2000006):
            self.assertIn(v, ex.values)
        self.assertEqual(len(ex.registry), 3)
        self.assertEqual(ex.as_dict()["sim_registry"][0]["count"], 5)

    def test_a_damaged_or_missing_seed_record_is_refused_never_skipped(self):
        self.write("b4-fake-1_a", "seeds.json", seeds_doc("b4-fake-1", 1000001, [[2000001, 2000002]]))
        self.write("b4-fake-1_b", "seeds.json", "{not json")
        with self.assertRaises(bs.ExclusionSourceRefusal) as cm:
            bs.sim_registry(R, str(self.sim))
        self.assertIn("b4-fake-1_b", str(cm.exception))
        shutil.rmtree(self.sim / "b4-fake-1_b")
        (self.sim / "b4-fake-1_c").mkdir()
        with self.assertRaises(bs.ExclusionSourceRefusal) as cm:
            bs.sim_registry(R, str(self.sim))
        self.assertIn("neither", str(cm.exception))
        shutil.rmtree(self.sim / "b4-fake-1_c")
        bad = seeds_doc("b4-fake-1", 1000003, [[2000007, 2000008]])
        bad["pairs"][0][0] = True
        self.write("b4-fake-1_d", "seeds.json", bad)
        with self.assertRaises(bs.ExclusionSourceRefusal) as cm:
            bs.sim_registry(R, str(self.sim))
        self.assertIn("malformed", str(cm.exception))
        shutil.rmtree(self.sim / "b4-fake-1_d")
        self.write("b4-fake-1_e", "INIT_FAILED.json", {"schema": "b4_sim_init_failed", "schema_version": "1.0.0", "label": "b4-fake-1",
                                                       "seeds_derived": True, "reason": "x", "generated_utc": "x"})
        with self.assertRaises(bs.ExclusionSourceRefusal) as cm:
            bs.sim_registry(R, str(self.sim))
        self.assertIn("says seeds were derived", str(cm.exception))
        shutil.rmtree(self.sim / "b4-fake-1_e")
        (self.sim / "stray.txt").write_text("x")
        with self.assertRaises(bs.ExclusionSourceRefusal):
            bs.sim_registry(R, str(self.sim))

    def test_the_seeds_document_shape(self):
        good = seeds_doc("b4-fake-1", 1000001, [[2000001, 2000002]])
        self.assertEqual(bs.seeds_doc_findings(good), [])
        for mutate in (lambda d: d.pop("count"), lambda d: d.update(count=5), lambda d: d["anchor"].update(label="other"),
                       lambda d: d.update(master_seed=-1), lambda d: d["pairs"].append([1, 1]), lambda d: d["exclusion"].pop("pooled_total"),
                       lambda d: d.update(schema_version="1.0.0"), lambda d: d.pop("fixture"), lambda d: d.update(fixture="no"),
                       lambda d: d.update(fixture=True), lambda d: d.update(label="b4-mech-1"),
                       lambda d: (d.update(label="b4-mech-1"), d["anchor"].update(label="b4-mech-1")),   # a production set under a fixture label: the label rule alone
                       lambda d: d["exclusion"].pop("exposure_receipt"),                                # 1.2.0 names the receipt
                       lambda d: d["exclusion"]["exposure_receipt"].update(sha256="00" * 32),           # exactly the pinned digest
                       lambda d: d["exclusion"]["exposure_receipt"].update(path="elsewhere.json"),
                       lambda d: d["exclusion"]["exposure_receipt"].update(count=66.0),
                       lambda d: d.update(schema_version="1.1.0")):                                      # a 1.1.0 record carries no receipt entry
            d = json.loads(json.dumps(good))
            mutate(d)
            self.assertTrue(bs.seeds_doc_findings(d), mutate)
        legacy = seeds_doc("b4-fake-1", 1000001, [[2000001, 2000002]], version="1.1.0")
        self.assertEqual(bs.seeds_doc_findings(legacy), [], "a 1.1.0 record archived before the settlement is still read")
        self.assertEqual(bs.SEEDS_SCHEMA, ("b4_sim_seeds", "1.2.0"))

    def test_the_fixture_form_of_the_seeds_document(self):
        """A mechanics fixture set: a b4-mech-<n> label, no master, no anchor digest, only already-exposed values (the owner's
        review of 2026-10-18, F1)."""
        good = fixture_doc("b4-mech-1", [[7, 11], [8, 12]])
        self.assertEqual(bs.seeds_doc_findings(good), [])
        self.assertTrue(all(v in bs.FIXTURE_VALUES for p in good["pairs"] for v in p))
        for mutate, why in ((lambda d: d.update(label="b4-sim-1"), "a production label on a fixture set"),
                            (lambda d: (d.update(label="b4-sim-1"), d["anchor"].update(label="b4-sim-1")), "a production label on a fixture set, the anchor's label moved with it: the label rule alone refuses"),
                            (lambda d: d["anchor"].update(label="b4-sim-1"), "the anchor's label differs"),
                            (lambda d: d.update(master_seed=1000001), "a fixture set derives no master"),
                            (lambda d: d["anchor"].update(hypothesis_sha256=FAKE_ANCHOR), "a fixture set has no anchor digest"),
                            (lambda d: d["anchor"].update(rule="sha256(label|anchor)[:4]"), "the rule must name the fixture"),
                            (lambda d: d["pairs"].append([7, 1000001]), "a value that is not already exposed"),
                            (lambda d: d.update(fixture=False), "a production set with a fixture label")):
            d = json.loads(json.dumps(good))
            mutate(d)
            self.assertTrue(bs.seeds_doc_findings(d), why)
        self.assertEqual(bs.FIXTURE_VALUES, frozenset(bs.B2_EXCLUDED_SEEDS) | bs.B4_EXPOSED_VALUES)

    def test_a_fixture_set_in_the_registry_is_read_without_a_master(self):
        self.write("b4-mech-1_x", "seeds.json", fixture_doc("b4-mech-1", [[7, 11], [8, 12]]))
        self.write("b4-fake-1_y", "seeds.json", seeds_doc("b4-fake-1", 1000001, [[2000001, 2000002]]))
        recs, _ = bs.sim_registry(R, str(self.sim))
        self.assertEqual([(r.status, r.master_seed, r.values) for r in recs], [("seeds", 1000001, (1000001, 2000001, 2000002)), ("seeds_fixture", None, (7, 11, 8, 12))])
        ex = bs.load_exclusion_set(R, str(self.sim))
        self.assertEqual(ex.as_dict()["sim_registry"][1], {"dir": f"{self.sim}/b4-mech-1_x", "status": "seeds_fixture", "seeds_sha256": recs[1].seeds_sha256, "master_seed": None, "count": 4})
        self.assertTrue({7, 11, 8, 12, 1000001, 2000001} <= ex.values)


class TheExposureReceipt(unittest.TestCase):
    """The owner's ruling of 2026-10-19: the exposure receipt is pinned, validated, pooled at both positions, and the two
    retired labels are refused on the new-derivation path while their archived records are still read."""

    @classmethod
    def setUpClass(cls):
        cls.rec = bs.read_exposure_receipt(R)
        cls.doc = json.loads((R / bs.EXPOSURE_RECEIPT_REL).read_text())

    def test_the_pinned_receipt_reads_and_is_the_reconstruction_s(self):
        self.assertEqual(bs.receipt_findings(self.doc), [])
        self.assertEqual((self.rec.path, self.rec.sha256), (bs.EXPOSURE_RECEIPT_REL, bs.EXPOSURE_RECEIPT_SHA256))
        self.assertEqual(self.rec.sha256, hashlib.sha256((R / bs.EXPOSURE_RECEIPT_REL).read_bytes()).hexdigest())
        pooled = list(self.rec.values)
        self.assertEqual(pooled, sorted(set(pooled))); self.assertTrue(all(bs.is_seed_int(v) for v in pooled))
        self.assertEqual(self.doc["pooled_sha256"], hashlib.sha256(bs.canonical_ints(pooled).encode()).hexdigest())
        self.assertEqual(bs.pinned_receipt_count(), len(pooled), "the authoritative count is the hash-verified file's pooled length")
        ref = {"path": bs.EXPOSURE_RECEIPT_REL, "sha256": bs.EXPOSURE_RECEIPT_SHA256, "count": len(pooled)}
        self.assertEqual(bs.receipt_reference_findings(ref, "x"), [])
        for n in (0, 1, len(pooled) - 1, len(pooled) + 1):
            f = bs.receipt_reference_findings({**ref, "count": n}, "x")
            self.assertTrue(any("pooled length" in x for x in f), (n, f))
        with mock.patch.object(bs, "EXPOSURE_RECEIPT_SHA256", "00" * 32):
            f = bs.receipt_reference_findings({**ref, "sha256": "00" * 32}, "x")
            self.assertTrue(any("cannot be bound" in x for x in f), f)
        recomputed = set()
        for v in self.doc["variants"]:
            self.assertIn(v["label"], bs.RETIRED_LABELS, "every variant is a RETIRED label")
            recomputed.add(v["master_seed"])
            for i, (l, o) in enumerate(v["pairs"]):
                recomputed.update((l, o))
                c = v["control_seeds"][i]
                self.assertEqual((c["x_control_seed"], c["d_shuffle_seed"]), (ctl.x_control_seed(l, o), ctl.d_shuffle_seed(l, o)), "the control seeds are the formulas' on the drawn pair")
                recomputed.update((c["x_control_seed"], c["d_shuffle_seed"]))
        self.assertEqual(recomputed, set(pooled), "the pooled list is exactly the variants' masters, pairs and control seeds")
        classes = {c for e in self.doc["values"] for c in e["classes"]}
        self.assertEqual(classes, {"observed", "reconstructed_recipe", "conservative_superset"})
        self.assertEqual(sorted(self.doc["envelope"]["observed_variants"]), ["V1", "V2", "V3", "V4", "V5", "V6"])
        self.assertEqual(sorted(self.doc["envelope"]["reconstructed_only_variants"]), ["V7", "V8", "V9"])
        self.assertEqual(len(self.doc["preserved_records"]), 22); self.assertTrue(all(r["agrees_with_recipe"] for r in self.doc["preserved_records"]))
        self.assertIn("NOT a record of execution", self.doc["status"])

    def test_the_receipt_s_values_are_screened_at_both_positions(self):
        ex = bs.load_exclusion_set(R)
        self.assertTrue(set(self.rec.values) <= ex.values)
        drawn = bs.pair_seeds(FAKE_MASTER, 40, ex.values)
        self.assertFalse(set(v for p in drawn for v in p) & set(self.rec.values))
        v0, v1 = self.rec.values[0], self.rec.values[-1]

        class Scripted:                                        # a generator that offers receipt values in each position, then clean values
            def __init__(self, seed):
                self.it = iter([v0, 3000001, 3000002, v1, 3000003, 3000004])

            def next32(self):
                return next(self.it)
        with mock.patch.object(bs, "Rng", Scripted):
            self.assertEqual(bs.pair_seeds(FAKE_MASTER, 1, set(self.rec.values)), [(3000003, 3000004)], "a receipt value in the landscape or the operator position skips the draw")

    def test_a_missing_rehashed_or_malformed_receipt_is_refused_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(bs.ExclusionSourceRefusal) as cm:
                bs.read_exposure_receipt(root)
            self.assertIn("missing", str(cm.exception))
            p = root / bs.EXPOSURE_RECEIPT_REL; p.parent.mkdir(parents=True)
            p.write_bytes((R / bs.EXPOSURE_RECEIPT_REL).read_bytes() + b"\n")
            with self.assertRaises(bs.ExclusionSourceRefusal) as cm:
                bs.read_exposure_receipt(root)
            self.assertIn("hashes to", str(cm.exception))
            p.write_bytes((R / bs.EXPOSURE_RECEIPT_REL).read_bytes())
            self.assertEqual(bs.read_exposure_receipt(root).values, self.rec.values)
        with mock.patch.object(bs, "EXPOSURE_RECEIPT_SHA256", "00" * 32):
            with self.assertRaises(bs.ExclusionSourceRefusal) as cm:
                bs.load_exclusion_set(R)
            self.assertIn("hashes to", str(cm.exception))
        good = self.doc
        self.assertEqual(bs.receipt_findings(good), [])
        for mutate, why in ((lambda d: d["pooled"].reverse(), "unsorted"), (lambda d: d["pooled"].append(d["pooled"][0]), "a duplicate"),
                            (lambda d: d.update(pooled_count=d["pooled_count"] + 1), "the count"), (lambda d: d.update(pooled_sha256="00" * 32), "the digest"),
                            (lambda d: d["variants"][0].update(label="b4-sim-3"), "a variant under a label that is not retired"),
                            (lambda d: d["variants"][0]["pairs"][0].__setitem__(0, 3000009), "a pair value not pooled"),
                            (lambda d: d["variants"][0]["control_seeds"][0].update(x_control_seed=3000009), "a control seed not pooled"),
                            (lambda d: d["values"][0]["classes"].append("guessed"), "an unknown class"),
                            (lambda d: d["values"].pop(), "the value entries are not the pooled list"),
                            (lambda d: d.pop("limits"), "a missing key"), (lambda d: d.update(schema_version="0.9.0"), "the schema"),
                            (lambda d: d["pooled"].__setitem__(0, 1.0), "a float value")):
            d = json.loads(json.dumps(good))
            mutate(d)
            self.assertTrue(bs.receipt_findings(d), why)
        self.assertEqual(bs.receipt_findings([]), ["not an object"])
        self.assertTrue(bs.receipt_findings({**good, "pooled": "x"}))

    def test_retired_labels_are_refused_before_a_master_and_still_read_from_the_registry(self):
        for label in ("b4-sim-1", "b4-sim-2"):
            with self.assertRaises(bs.RetiredLabelRefusal) as cm:
                bs.check_label_not_retired(label)
            self.assertIn("b4-sim-3", str(cm.exception))
        bs.check_label_not_retired("b4-sim-3"); bs.check_label_not_retired(bs.EXPLORATION_LABEL)
        self.assertNotIn(bs.EXPLORATION_LABEL, bs.RETIRED_LABELS); self.assertEqual(bs.RETIRED_LABELS, {"b4-sim-1", "b4-sim-2"})
        v1 = next(v for v in self.doc["variants"] if v["id"] == "V1"); v8 = next(v for v in self.doc["variants"] if v["id"] == "V8")
        anchor = self.doc["historical_inputs"]["anchor_hypothesis_sha256"]
        with tempfile.TemporaryDirectory() as tmp:
            simdir = Path(tmp) / "sim"
            for name, doc in (("b4-sim-1_legacy", seeds_doc("b4-sim-1", v1["master_seed"], v1["pairs"], version="1.1.0", anchor=anchor)),
                              ("b4-sim-2_current", seeds_doc("b4-sim-2", v8["master_seed"], v8["pairs"], anchor=anchor))):
                (simdir / name).mkdir(parents=True); (simdir / name / "seeds.json").write_text(json.dumps(doc))
            with mock.patch.object(bs, "master_seed", side_effect=AssertionError("reading an archive derives nothing")), \
                 mock.patch.object(bs, "pair_seeds", side_effect=AssertionError("reading an archive derives nothing")):
                recs, _ = bs.sim_registry(R, str(simdir))
                self.assertEqual([(r.status, r.master_seed) for r in recs], [("seeds", v1["master_seed"]), ("seeds", v8["master_seed"])], "retired labels' archived records are read")
                ex = bs.load_exclusion_set(R, str(simdir))
            self.assertEqual(len(ex.registry), 2)
            self.assertTrue({v1["master_seed"], v8["master_seed"]} | {x for p in v1["pairs"] + v8["pairs"] for x in p} <= ex.values)


if __name__ == "__main__":
    unittest.main()
