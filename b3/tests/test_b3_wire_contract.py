"""The bytes the B3 image will put on the wire, fed to the production validator (B3 lifecycle 2, image stage 3; the
discipline of tests/test_b2_wire.py).

`build/b3_firmware/b3_wire_twin` (`make -C b3/firmware wire-twin`, strictest host warnings, -Werror) links
b3_wire.c — derived from firmware/b2/b2_wire.c — with the units the image links for these bytes: b2_search.c for
the R and F arms (B2's own initializer and renderer), b3_online_view.c + b3_carto.c + b3_record.c for the O arm,
p3_derive.c. The harness plays the fabric (b2_search.ModelFabric over the truth mapping) and the twin emits, for
committed pair 0 (slice 0..1 of the committed plan and prediction), the opening baseline, every search record of
the three arms in the pair's frozen order, the three champions' holdout records and the closing baseline. That
session goes through `b3_records.validate_run_log` WITH the instrument's common validation — no finding — and:

  * every document is compact sorted-key JSON; the identity is app_identity 1.6.0 with the three B3 fields;
  * every record's embedded search block is, byte for byte, the reference block (b2_search.run for R / F,
    b3_online_arm.run_online for O): the wire embeds what it is given and never rebuilds the ledger;
  * the outer arm is the validator's name (random_safe | map_guided | online) and the wire refuses any other;
  * the validator rejects, each with its named finding: an R / F search record with a ledger, an O holdout
    record with a ledger, an O search record without one, a top-level ledger; the identity's three B3 fields
    absent, wrong and of the wrong type; the old identity (1.5.0, B2's actual bytes) and record (1.3.0) versions.

B2 parity (`make wire-parity`): ONE driver compiled against firmware/b2/b2_wire.c and against b3_wire.c, the same
inputs: every public builder's output byte-identical — the framed line, the sign request, the audit (ready,
sparse, raw), the closing control, the heartbeat, AUDITWAIT, the summary, the tally, every loop-record evidence
shape — but the identity (B3 = B2 + the three fields + 1.6.0, as canonical JSON) and the loop record (the version
only).

No skip: a missing compiler, build or instrument is a FAILURE. Builds go to the top-level build/; nothing here
writes under b3/, builds an image or touches a board.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_plan as pl  # noqa: E402
import b3_records as brec  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

FW = R / "b3/firmware"
BUILD = R / "build/b3_firmware"
TWIN = BUILD / "b3_wire_twin"
PARITY = {"b2": BUILD / "b3_wire_parity_b2", "b3": BUILD / "b3_wire_parity_b3"}
PLAN = json.loads((R / "evidence/b3/plan.json").read_text())
PRED = json.loads((R / "evidence/b3/prediction.json").read_text())
CTX = brec.context_from(PLAN, PRED, 0, 1)
TRUTH = bm.truth_mapping()
FABRIC = bs.ModelFabric(TRUTH)
MASKS = bl.universe_mask(TRUTH)
VIEW = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
B3_IDENTITY = {"carto_version": "specimen-carto-v1.1", "arms": "RFO", "b1_map_cost": 333}
_BUILT: dict = {}


def canon(doc) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


def hexw(tables) -> str:
    return " ".join(f"{t:016x}" for t in tables)


def build() -> str:
    if "log" not in _BUILT:
        cc = os.environ.get("CC", "cc")
        if shutil.which(cc) is None:
            raise AssertionError(f"no host C compiler ({cc}): a failure, never a skip")
        p = subprocess.run(["make", "-s", "-C", str(FW), "wire-twin", "wire-parity"], capture_output=True, text=True)
        if p.returncode != 0:
            raise AssertionError(f"the wire twin did not build:\n{p.stdout}{p.stderr}")
        _BUILT["log"] = p.stdout + p.stderr
    return _BUILT["log"]


class Twin:
    def __init__(self):
        build()
        self.p = subprocess.Popen([str(TWIN)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def one(self, line: str) -> str:
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()
        out = self.p.stdout.readline()
        if not out:
            raise AssertionError("the twin closed its output")
        return out.rstrip("\n")

    def close(self):
        try:
            self.p.stdin.write("Q\n")
            self.p.stdin.flush()
        except (BrokenPipeError, ValueError):
            pass
        try:
            self.p.stdin.close()
            rest = self.p.stdout.read()
            self.p.stdout.close()
        finally:
            rc = self.p.wait(timeout=10)
        if rc != 0:
            raise AssertionError(f"the twin exited {rc}: {rest[-300:]!r}")


def session() -> dict:
    """Pair 0's whole session through the wire twin, and the reference blocks, once per process."""
    if "session" in _BUILT:
        return _BUILT["session"]
    pair = PRED["pairs"][0]
    lseed, oseed = pair["landscape_seed"], pair["operator_seed"]
    budget = PRED["budget_per_arm"]
    land = bl.Landscape(PRED["fitness"], lseed, masks=MASKS, truth=TRUTH)
    order = pl.arm_order(0)
    ref = {}
    for a in order:
        if a == "O":
            oo = oa.run_online(land, oseed, budget, FABRIC, keep_ledger=True, pair=0)
            ref[a] = (oo.blocks, oo.champion_block)
        else:
            res = bs.run(brec.ARM_WIRE[a], land, None if a == "R" else VIEW, oseed, budget, FABRIC, log_moves=True, pair=0)
            ref[a] = (res.blocks, res.champion_block)
    twin = Twin()
    raw: list[str] = []
    champs = {}
    try:
        ident = twin.one(f"IDENT {CTX.master_seed} {budget} {CTX.pairs_total} 0 1")
        assert ident.startswith("IDENT "), ident
        seq = 1
        raw.append(twin.one(f"BASE {seq}"))
        for a in order:
            assert twin.one(f"RUN {a} 0 {lseed} {oseed} {budget} {hexw(FABRIC(0))}") == "OK"
            for _ in range(budget):
                prop = twin.one("P")
                assert prop.startswith("PROP "), prop
                seq += 1
                raw.append(twin.one(f"M {seq} {hexw(FABRIC(bc.genome_from_hex(prop[5:])))}"))
            assert twin.one("P") == "DONE"
            champ = twin.one("C")
            assert champ.startswith("CHAMP "), champ
            champs[a] = bc.genome_from_hex(champ[6:])
            # the holdout records come after all three searches (the frozen order); the twin holds one arm at a time,
            # so the champion is evaluated now under the seq its record will have, and the record is placed below
            h_seq = 1 + 3 * budget + order.index(a) + 1
            champs[a] = twin.one(f"H {h_seq} {hexw(FABRIC(champs[a]))}")
        for a in order:
            raw.append(champs[a])
        seq = 1 + 3 * budget + 3 + 1
        raw.append(twin.one(f"BASE {seq}"))
    finally:
        twin.close()
    for line in raw:
        assert line.startswith("REC "), line[:80]
    _BUILT["session"] = {"ident_raw": ident[6:], "raw": [x[4:] for x in raw], "ref": ref, "order": order, "budget": budget}
    return _BUILT["session"]


def validator():
    if "br" not in _BUILT:
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import b1_records as br  # noqa: E402  (needs the bound instrument package)
        _BUILT["br"] = br
    return _BUILT["br"]


class TheBuild(unittest.TestCase):
    def test_the_wire_twin_and_the_parity_drivers_build_silently(self):
        self.assertEqual(build(), "")
        for exe in (TWIN, *PARITY.values()):
            self.assertTrue(exe.is_file(), exe)
        mk = (FW / "Makefile").read_text()
        for flag in ("-Werror", "-pedantic", "-Wconversion"):
            self.assertIn(flag, mk)


class TheSessionValidates(unittest.TestCase):
    def test_the_whole_pair_session_passes_the_production_validator_with_the_common_envelope(self):
        s = session()
        validator()
        log = {"app_identity": json.loads(s["ident_raw"]), "loop_records": [json.loads(x) for x in s["raw"]]}
        self.assertEqual(len(log["loop_records"]), 2 + 3 * s["budget"] + 3)
        self.assertEqual(brec.validate_run_log(log, CTX, common=True), [])

    def test_every_document_is_compact_sorted_key_json(self):
        s = session()
        for doc in [s["ident_raw"]] + s["raw"][:50] + s["raw"][-10:] + s["raw"][::97]:
            self.assertEqual(doc, canon(json.loads(doc)))

    def test_the_identity_is_1_6_0_with_the_three_b3_fields(self):
        d = json.loads(session()["ident_raw"])
        self.assertEqual(d["schema"], "app_identity")
        self.assertEqual(d["schema_version"], "1.6.0")
        for k, v in B3_IDENTITY.items():
            self.assertEqual(d[k], v, k)
        self.assertNotIn("probe_budget", d)
        self.assertEqual((d["pair_first"], d["pair_count"], d["pairs_total"]), (0, 1, 8))

    def test_every_embedded_block_is_the_reference_block_byte_for_byte(self):
        """R / F blocks are B2's renderer's, O blocks b3_record_json's — and the wire embeds them as given: the
        raw record contains `"search":` + the reference bytes, the O ledger untouched inside it."""
        s = session()
        recs = s["raw"][1:-1]
        searches, holdouts = recs[:3 * s["budget"]], recs[3 * s["budget"]:]
        n = 0
        for i, a in enumerate(s["order"]):
            blocks, champion_block = s["ref"][a]
            self.assertEqual(len(blocks), s["budget"])
            for k in range(s["budget"]):
                raw = searches[i * s["budget"] + k]
                self.assertIn('"search":' + blocks[k] + ',"seq":', raw, (a, k))
                self.assertEqual(raw.count('"ledger":'), 1 if a == "O" else 0, (a, k))
                self.assertTrue(raw.startswith('{"arm":"' + brec.ARM_WIRE[a] + '",'), (a, k))
                n += 1
            self.assertIn('"search":' + champion_block + ',"seq":', holdouts[i], a)
            self.assertNotIn('"ledger":', holdouts[i], a)
            self.assertTrue(holdouts[i].startswith('{"arm":"' + brec.ARM_WIRE[a] + '",'), a)
        self.assertEqual(n, 3000)
        for base in (s["raw"][0], s["raw"][-1]):
            d = json.loads(base)
            self.assertNotIn("arm", d)
            self.assertNotIn("search", d)
            self.assertEqual(d["schema_version"], "1.4.0")

    def test_the_outer_arm_is_one_of_the_validator_s_names_or_refused(self):
        twin = Twin()
        self.addCleanup(twin.close)
        self.assertEqual(set(brec.ARM_WIRE.values()), {"random_safe", "map_guided", "online"})
        for name in brec.ARM_WIRE.values():
            self.assertNotEqual(twin.one(f"A {name}"), "A 0", name)
        for name in ("frozen-map", "random-safe", "ONLINE", "onlinex", "O", "R", "map_guided "):
            with self.subTest(name=name):
                self.assertEqual(twin.one(f"A {name}"), "A 0", name)
        self.assertEqual(twin.one("A "), "A 0", "an empty name")


class TheValidatorRejectsByName(unittest.TestCase):
    """Each malformed document is a C-emitted document with ONE change, and the validator names it."""

    @classmethod
    def setUpClass(cls):
        cls.s = session()
        recs = [json.loads(x) for x in cls.s["raw"]]
        b = cls.s["budget"]
        cls.order = cls.s["order"]
        cls.search = {a: recs[1 + i * b] for i, a in enumerate(cls.order)}            # each arm's first search record
        cls.holdout = {a: recs[1 + 3 * b + i] for i, a in enumerate(cls.order)}
        cls.ident = json.loads(cls.s["ident_raw"])

    def findings(self, rec: dict, arm: str, holdout: bool) -> list[str]:
        return brec.record_findings(rec, CTX, (0, brec.ARM_WIRE[arm], holdout), {})

    def test_the_untouched_records_pass(self):
        for a in self.order:
            self.assertEqual(self.findings(self.search[a], a, False), [], a)

    def test_ledger_placement(self):
        entry = self.search["O"]["search"]["ledger"]
        cases = []
        for a, what in (("R", "a random-safe search record"), ("F", "a frozen-map search record")):
            rec = copy.deepcopy(self.search[a])
            rec["search"]["ledger"] = copy.deepcopy(entry)
            cases.append((rec, a, False, f"a ledger sub-block on {what}"))
        rec = copy.deepcopy(self.holdout["O"])
        rec["search"]["ledger"] = copy.deepcopy(entry)
        cases.append((rec, "O", True, "a ledger sub-block on an O champion's holdout record"))
        rec = copy.deepcopy(self.search["O"])
        del rec["search"]["ledger"]
        cases.append((rec, "O", False, "an O-arm search record must carry its ledger sub-block"))
        rec = copy.deepcopy(self.search["O"])
        rec["ledger"] = rec["search"].pop("ledger")
        cases.append((rec, "O", False, "a top-level `ledger`"))
        for rec, a, h, needle in cases:
            with self.subTest(needle=needle):
                f = self.findings(rec, a, h)
                self.assertTrue(any(needle in x for x in f), (needle, f))

    def test_the_identity_s_three_b3_fields(self):
        self.assertEqual(brec.identity_findings(self.ident, CTX), [])
        for k in B3_IDENTITY:
            with self.subTest(absent=k):
                d = dict(self.ident)
                del d[k]
                self.assertIn(f"identity: the B3 field {k!r} is absent", brec.identity_findings(d, CTX))
        for k, wrong, needle in (("carto_version", "specimen-carto-v1.0", "identity: carto_version 'specimen-carto-v1.0' is not"),
                                 ("arms", "RF", "identity: arms 'RF' is not 'RFO'"),
                                 ("b1_map_cost", 334, "identity: b1_map_cost 334 is not the constant 333")):
            with self.subTest(wrong=k):
                d = dict(self.ident, **{k: wrong})
                self.assertTrue(any(x.startswith(needle) for x in brec.identity_findings(d, CTX)), (k, brec.identity_findings(d, CTX)))
        for k, wrong, what in (("carto_version", 11, "a string"), ("arms", ["R", "F", "O"], "a string"),
                               ("b1_map_cost", "333", "an integer"), ("b1_map_cost", True, "an integer"), ("b1_map_cost", 333.0, "an integer")):
            with self.subTest(type=(k, wrong)):
                d = dict(self.ident, **{k: wrong})
                self.assertIn(f"identity: {k} is not {what}", brec.identity_findings(d, CTX))

    def test_the_old_versions_are_rejected(self):
        d = dict(self.ident, schema_version="1.5.0")
        self.assertIn("identity: schema_version '1.5.0' is not 1.6.0", brec.identity_findings(d, CTX))
        b2_ident = json.loads(parity()["b2"]["IDENT"])            # B2's actual identity bytes
        f = brec.identity_findings(b2_ident, CTX)
        self.assertIn("identity: schema_version '1.5.0' is not 1.6.0", f)
        for k in B3_IDENTITY:
            self.assertIn(f"identity: the B3 field {k!r} is absent", f)
        for a in self.order:
            rec = dict(self.search[a], schema_version="1.3.0")
            self.assertIn(f"record {rec['seq']}: schema_version '1.3.0' is not 1.4.0", self.findings(rec, a, False))


def parity() -> dict:
    if "parity" not in _BUILT:
        build()
        out = {}
        for k, exe in PARITY.items():
            text = subprocess.run([str(exe)], capture_output=True, text=True, check=True).stdout
            lines = {}
            for line in text.splitlines():
                if line:
                    tag, _, rest = line.partition(" ")
                    lines[tag] = rest
            out[k] = lines
        _BUILT["parity"] = out
    return _BUILT["parity"]


class B2Parity(unittest.TestCase):
    CHANGED = ("IDENT",)

    def test_every_public_builder_unaffected_by_b3_is_byte_identical(self):
        p = parity()
        self.assertEqual(sorted(p["b2"]), sorted(p["b3"]))
        expected = {"LINE", "LINE_EMPTY", "LINE_SHORT", "SIGNREQ", "AUDIT_READY", "SPARSE", "AUDIT_SPARSE", "AUDIT",
                    "CLOSING", "HB", "AUDITWAIT", "REC_SCORED", "REC_BASELINE", "REC_REFUSED_PL", "REC_GATE",
                    "REC_AUDIT_STOP", "REC_SIGN_STOP", "REC_SHORT", "TALLY", "SUMMARY", "SUMMARY_STOPPED", "IDENT"}
        self.assertEqual(set(p["b3"]), expected)
        for tag in sorted(expected):
            if tag in self.CHANGED or (tag.startswith("REC_") and p["b2"][tag] != "<0>"):
                continue
            with self.subTest(tag=tag):
                self.assertEqual(p["b3"][tag], p["b2"][tag], tag)
        self.assertEqual(p["b2"]["LINE_SHORT"], "<0>")
        self.assertEqual(p["b2"]["REC_SHORT"], "<0>")
        self.assertEqual(p["b3"]["TALLY"], "6 3")

    def test_the_loop_record_differs_only_by_its_version(self):
        p = parity()
        old, new = '"schema":"loop_record","schema_version":"1.3.0"', '"schema":"loop_record","schema_version":"1.4.0"'
        n = 0
        for tag in p["b2"]:
            if tag.startswith("REC_") and p["b2"][tag] != "<0>":
                with self.subTest(tag=tag):
                    self.assertEqual(p["b2"][tag].count(old), 1)
                    self.assertEqual(p["b3"][tag], p["b2"][tag].replace(old, new), tag)
                    n += 1
        self.assertEqual(n, 6)

    def test_the_identity_differs_only_by_its_version_and_the_three_fields(self):
        p = parity()
        b2, b3 = json.loads(p["b2"]["IDENT"]), json.loads(p["b3"]["IDENT"])
        self.assertEqual(b2["schema_version"], "1.5.0")
        self.assertEqual(set(b3) - set(b2), set(B3_IDENTITY))
        self.assertEqual(set(b2) - set(b3), set())
        want = dict(b2, schema_version="1.6.0", **B3_IDENTITY)
        self.assertEqual(p["b3"]["IDENT"], canon(want), "B3's bytes = B2's with the version and the three fields, canonical")
        self.assertEqual(p["b2"]["IDENT"], canon(b2))


if __name__ == "__main__":
    unittest.main()
