"""b4/host/b4_ff_mapping.py — the certificate mapping of SLICE_X2Y25 is read from the certificate and nothing
else: 22 feature names on 21 addresses (CLKINV / NOCLKINV one bit, two readings), every (element, semantic) of
the class exactly once, the addresses in numeric (far, word, bit) order, the certificate's digest pinned; the
project's bit readings are held to the certificate's own specimen pairs, and a certificate that disagrees is
refused by name (every refusal driven on a TEMP COPY with its own digest given explicitly — the fixture boundary;
the real certificate is never touched); the default entry reads only the certificate that hashes to the pinned
CERTIFICATE_SHA256. Address ranges, endpoint existence and the polarity cross-check (the owner's P2 on 2bad829).
No skip: an absent certificate is a failure."""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_ff_mapping as bm  # noqa: E402

CERT = R / bm.CERTIFICATE_REL


class TheMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = bm.site_mapping()

    def test_the_count_is_21_addresses_for_22_feature_names(self):
        m = self.m
        self.assertEqual(len(m.addresses), 21)
        self.assertEqual(sum(len(e.features) for e in m.entries.values()), 22)
        clk = m.entries[m.address_of(None, "clock_mode")]
        self.assertEqual(clk.features, ("CLBLL_L.SLICEL_X0.CLKINV", "CLBLL_L.SLICEL_X0.NOCLKINV"))
        self.assertEqual(clk.bit_one_means, "clock inverted")

    def test_every_element_and_semantic_of_the_class_exactly_once(self):
        m = self.m
        pairs = sorted((str(e.element), e.semantic) for e in m.entries.values())
        want = sorted([(e, "ff_init") for e in bm.ELEMENTS] + [(e, "ff_srval") for e in bm.ELEMENTS] + [("None", s) for s in ("ce_mode", "sr_mode", "sr_kind", "storage_kind", "clock_mode")])
        self.assertEqual(pairs, want)
        for e in bm.ELEMENTS:
            self.assertNotEqual(m.address_of(e, "ff_init"), m.address_of(e, "ff_srval"))

    def test_the_addresses_are_in_numeric_order_and_the_v2_form(self):
        m = self.m
        keys = [bm.address_key(a) for a in m.addresses]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(m.addresses[1], "0x00400a01/51/7")       # /7 before /19: numeric, not lexical
        self.assertEqual(m.addresses[2], "0x00400a01/51/19")
        for a in m.addresses:
            self.assertRegex(a, r"^0x[0-9a-f]{8}/[0-9]+/[0-9]+$")
            self.assertEqual(m.genome_bit(a), m.addresses.index(a))

    def test_the_site_tile_and_certificate_are_pinned(self):
        m = self.m
        self.assertEqual((m.site, m.tile), ("SLICE_X2Y25", "CLBLL_L_X2Y25"))
        self.assertEqual(m.certificate_rel, bm.CERTIFICATE_REL)
        self.assertEqual(m.certificate_sha256, bm.sha256_file(CERT))
        self.assertEqual(m.certificate_sha256, "c69e419f836684872c9edb3754cdb7c76591aaabf69859dab448454c6d78ceef")
        self.assertEqual(json.loads(json.dumps(m.summary()))["addresses"], list(m.addresses))

    def test_the_bit_readings_are_the_plans_z_convention_held_to_the_specimen_pairs(self):
        m = self.m
        self.assertEqual(m.entries[m.address_of("AFF", "ff_init")].feature_specimen, "SLICE_X2Y25_zini_AFF")
        self.assertEqual(m.entries[m.address_of("AFF", "ff_init")].bit_one_means, "INIT = 0")
        self.assertEqual(m.entries[m.address_of("BFF", "ff_srval")].feature_specimen, "SLICE_X2Y25_base")
        self.assertEqual(m.entries[m.address_of("BFF", "ff_srval")].baseline_specimen, "SLICE_X2Y25_zrst_BFF")
        self.assertEqual(m.entries[m.address_of("BFF", "ff_srval")].bit_one_means, "SRVAL = 0")
        self.assertEqual(m.entries[m.address_of(None, "storage_kind")].feature_specimen, "SLICE_X2Y25_latch")
        self.assertEqual(m.entries[m.address_of(None, "sr_kind")].baseline_specimen, "SLICE_X2Y25_async")
        self.assertEqual({e.split for e in m.entries.values()}, {"mine"})

    def test_a_mapping_is_the_same_object_twice(self):
        self.assertEqual(bm.site_mapping().summary(), self.m.summary())


class Refusals(unittest.TestCase):
    """Each tamper on a temp copy of the certificate is refused by name; the committed file is untouched."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="b4_cert_"))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.doc = json.loads(CERT.read_text())
        self.before = bm.sha256_file(CERT)
        self.addCleanup(lambda: self.assertEqual(bm.sha256_file(CERT), self.before, "the committed certificate changed"))

    def refused(self, needle: str, edit) -> None:
        doc = copy.deepcopy(self.doc)
        edit(doc)
        p = self.d / "certificate.json"
        p.write_text(json.dumps(doc))
        with self.assertRaises(bm.MappingRefusal) as cm:
            bm.site_mapping(path=p, expected_sha256=bm.sha256_file(p))     # the fixture boundary: the copy's own digest, explicitly
        self.assertIn(needle, str(cm.exception))

    def mine(self, doc, token: str, element: str | None = None) -> dict:
        for r in doc["feature_results"]:
            if r["split"] == "mine" and r["feature"].endswith("." + token) and (element is None or r["feature"].split(".")[-2] == element):
                return r
        raise AssertionError(token)

    def test_status_schema_and_class(self):
        self.refused("not 'passed'", lambda d: d.__setitem__("status", "failed"))
        self.refused("schema_version is not 1.6.0", lambda d: d.__setitem__("schema_version", "1.5.0"))
        self.refused("not 'clb_ff_config'", lambda d: d["bit_class"].__setitem__("id", "clb_lut_init"))

    def test_a_reading_that_the_specimen_pair_does_not_support(self):
        self.refused("the feature endpoint is 'SLICE_X2Y25_base', not 'SLICE_X2Y25_zini_AFF'", lambda d: self.mine(d, "ZINI", "AFF").__setitem__("feature_specimen_id", "SLICE_X2Y25_base"))
        self.refused("do not agree with a direct reading (1, 0 -> 1)", lambda d: self.mine(d, "ZRST", "BFF").__setitem__("expected_transition", {"before": 1, "after": 0}))

    def test_the_shared_address_rule(self):
        self.refused("NOCLKINV: expected_value 0 and transition {'before': 1, 'after': 0} do not agree with a direct reading", lambda d: self.mine(d, "NOCLKINV")["predicted_assignments"][0]["segbit"].__setitem__("negated", False))

        def collide(d):   # LATCH moved onto FFSYNC's address: two unrelated features on one bit
            self.mine(d, "LATCH")["predicted_assignments"][0]["address"] = self.mine(d, "FFSYNC")["predicted_assignments"][0]["address"]
        self.refused("share one address; only CLKINV / NOCLKINV may", collide)

    def test_a_missing_or_doubled_feature_and_a_multi_bit_rule(self):
        self.refused("20 addresses / 21 features, not 21 / 22", lambda d: d["feature_results"].remove(self.mine(d, "ZINI", "CFF")))
        self.refused("predicted assignments, not one", lambda d: self.mine(d, "ZINI", "CFF")["predicted_assignments"].append(copy.deepcopy(self.mine(d, "ZINI", "CFF")["predicted_assignments"][0])))
        self.refused("is not a clb_ff_config token", lambda d: self.mine(d, "FFSYNC").__setitem__("feature", "CLBLL_L.SLICEL_X0.WHATEVER"))

    def test_an_unreadable_file(self):
        with self.assertRaises(bm.MappingRefusal):
            bm.site_mapping(path=self.d / "absent.json", expected_sha256="0" * 64)

    def test_the_default_entry_is_pinned_to_the_authorised_digest(self):
        """A copy that is byte-identical still needs its digest given; a copy that differs is refused by the digest
        BEFORE any content check; the default path is held to CERTIFICATE_SHA256; None is never accepted."""
        p = self.d / "copy.json"
        p.write_bytes(CERT.read_bytes())
        self.assertEqual(bm.site_mapping(path=p).addresses, bm.site_mapping().addresses, "a byte-identical copy passes the pinned digest")
        p.write_text(json.dumps(self.doc))                                      # re-serialised: other bytes, same content
        with self.assertRaises(bm.MappingRefusal) as cm:
            bm.site_mapping(path=p)
        self.assertIn("not the expected c69e419f83668487", str(cm.exception))
        with self.assertRaises(bm.MappingRefusal) as cm:
            bm.site_mapping(path=p, expected_sha256=None)
        self.assertIn("explicit 64-hex expected digest", str(cm.exception))
        self.assertEqual(bm.CERTIFICATE_SHA256, bm.sha256_file(CERT))

    def test_address_ranges_endpoints_and_the_polarity_cross_check(self):
        """The owner's three probes on 2bad829, each refused by name."""
        self.refused("word -1 is not in 0..100", lambda d: self.mine(d, "ZINI", "AFF")["predicted_assignments"][0]["address"].__setitem__("word", -1))
        self.refused("bit 32 is not in 0..31", lambda d: self.mine(d, "ZINI", "AFF")["predicted_assignments"][0]["address"].__setitem__("bit", 32))
        self.refused("frame address '0x100000000' is not 32-bit", lambda d: self.mine(d, "ZINI", "AFF")["predicted_assignments"][0]["address"].__setitem__("far", "0x100000000"))
        self.refused("the baseline endpoint 'DOES_NOT_EXIST' is not a specimen of the certificate", lambda d: self.mine(d, "ZINI", "AFF").__setitem__("baseline_specimen_id", "DOES_NOT_EXIST"))
        self.refused("20 addresses / 21 features, not 21 / 22", lambda d: self.mine(d, "ZRST", "AFF").__setitem__("feature_specimen_id", "SLICE_X14Y25_base"))   # a feature endpoint on another site leaves this site a feature short
        self.refused("the baseline endpoint 'SLICE_X14Y25_base' is not on site SLICE_X2Y25", lambda d: self.mine(d, "ZINI", "AFF").__setitem__("baseline_specimen_id", "SLICE_X14Y25_base"))
        self.refused("expected_value 0 and transition {'before': 0, 'after': 1} do not agree with a direct reading (1, 0 -> 1)", lambda d: self.mine(d, "ZINI", "AFF")["predicted_assignments"][0].__setitem__("expected_value", 0))
        self.refused("do not agree with a negated reading (0, 1 -> 0)", lambda d: self.mine(d, "NOCLKINV")["predicted_assignments"][0].__setitem__("expected_value", 1))


if __name__ == "__main__":
    unittest.main()
