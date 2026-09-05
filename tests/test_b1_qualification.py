"""The carrier-qualification evidence chain (host/b1_qualification.py, host/b1q_adjudicate.py,
the QUALIFICATION runner profile): a modelled B1Q session (budget 9, eleven records) through
the instrument's real host stack → the B1Q adjudicator with the real validators → the
qualification record → `verify()` re-adjudicates it → the MAPPING adjudicator accepts the
carrier only through that chain. Negatives: a bare flag, a missing record, a tampered
evidence file, a binding to another carrier / image / prereg / seed, a HOLD record, a
code probe whose STATUS says tables_match = 1 or cfg_valid = 0, a baseline with a non-zero
readout or other counters. Nothing here touches a board, a port or the key store."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_adjudicate as adj  # noqa: E402
import b1_modelled_session as ms  # noqa: E402
import b1_qualification as bq  # noqa: E402
import b1q_adjudicate as qadj  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

HAVE = inst.DEFAULT_ROOT.is_dir()
MANIFEST = json.loads((R / "manifests/b1_manifest.json").read_text())
QPLAN = json.loads((R / "evidence/b1q/plan.json").read_text())
QPRED = json.loads((R / "evidence/b1q/prediction.json").read_text())
PLAN = json.loads((R / "evidence/b1/plan.json").read_text())
PRED = json.loads((R / "evidence/b1/prediction.json").read_text())
RULING = {"ruling": qadj.RULING_TEXT, "boardid": "17A6", "granted_by": "test", "date": "2026-09-05-T"}


def msha(m: dict) -> str:
    return hashlib.sha256(json.dumps(m, indent=1, ensure_ascii=False).encode()).hexdigest()


PREREG_DIR = Path(tempfile.mkdtemp())


def freeze_doc(m: dict, text: str = "# fixture preregistration\n") -> Path:
    import os
    doc = PREREG_DIR / f"prereg_{hashlib.sha256(text.encode()).hexdigest()[:8]}.md"
    doc.write_text(text)
    m["prereg"]["path"] = os.path.relpath(doc, R)
    m["prereg"]["sha256"] = hashlib.sha256(doc.read_bytes()).hexdigest(); m["prereg"]["frozen"] = True
    return doc


def frozen() -> dict:
    m = copy.deepcopy(MANIFEST)
    freeze_doc(m)
    m["image"]["board_ready"] = True
    return m


def manifest_text(m: dict) -> str:
    return json.dumps(m, indent=1, ensure_ascii=False) + "\n"


def rulings_for(m: dict, sha: str) -> tuple[dict, dict]:
    common = {"boardid": m["board"]["boardid"], "granted_by": "test", "date": "2026-09-05-T", "session": "B1Q",
              "prereg_sha256": m["prereg"]["sha256"], "image_sha256": m["image"]["sha256"], "b1_manifest_sha256": sha}
    return ({"ruling": qadj.RULING_TEXT, "master_seed": m["qualification_plan"]["master_seed"], **common},
            {"ruling": bq.PROVISION_RULING_TEXT, **common})


def qualify(tmp: Path, m: dict, name: str = "q", text: str | None = None, **kw) -> tuple[dict, Path, dict, str]:
    """Run the modelled B1Q session against manifest `m` (unqualified; `text` = the exact
    manifest bytes the session is bound to, default the canonical rendering), adjudicate,
    write every file the runner writes (manifest_at_run, both rulings, adjudication,
    summary), build the record. Returns (record, evidence dir, result, manifest sha256)."""
    text = text if text is not None else manifest_text(m)
    sha = hashlib.sha256(text.encode()).hexdigest()
    out = tmp / name; out.mkdir(parents=True, exist_ok=True)
    mp = tmp / f"{name}_manifest.json"; mp.write_text(text)
    wr, pr = rulings_for(m, sha)
    rp, pp = tmp / f"{name}_ruling.json", tmp / f"{name}_p3k.json"
    rp.write_text(json.dumps(wr, indent=1) + "\n"); pp.write_text(json.dumps(pr, indent=1) + "\n")
    bq.write_session_artifacts(out, mp, rp, pp, sha, expected_rulings=(wr, pr))
    r = ms.run_modelled(m, QPLAN, out, binding_extra={"b1_manifest_sha256": sha}, **kw)
    res = qadj.adjudicate(out, m, QPLAN, QPRED, sha, require_git=False)
    (out / "adjudication.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    (out / "summary.json").write_text(json.dumps({"outcome": res["outcome"], "token": r["token"], "l6": {"session": "B1Q"},
                                                  "ruling": wr, "provisioning_ruling_sha256": hashlib.sha256(pp.read_bytes()).hexdigest()}) + "\n")
    rec = bq.make_record(out, m, sha, QPLAN, res)
    (out / "qualification.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    return rec, out, res, sha


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class Chain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.m = frozen()
        cls.rec, cls.out, cls.res, cls.sha_q = qualify(cls.tmp, cls.m)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def qualified_manifest(self) -> dict:
        m = copy.deepcopy(self.m); m["carrier"]["qualification"] = copy.deepcopy(self.rec); m["carrier"]["qualified"] = True
        return m


    def test_the_modelled_qualification_session_passes_with_the_silicon_observations(self):
        self.assertEqual(self.res["outcome"], "PASS", self.res["findings"])
        g = self.res["gate_observations"]
        self.assertEqual(g["1"], {"tables_match": 1, "configuration_valid_hw": 1, "readout_all_zero": True})
        self.assertEqual(g["11"]["tables_match"], 1)
        for s in range(2, 11):
            self.assertEqual(g[str(s)], {"tables_match": 0, "configuration_valid_hw": 1, "readout_all_zero": False}, s)
        self.assertEqual(self.res["p3"]["run_log_validation"], {"scored": 11, "audited": 11, "chain_length": 12})
        self.assertEqual(self.res["provisional"]["recall"], 1.0)
        self.assertEqual(self.rec["outcome"], "PASS"); self.assertEqual(self.rec["binding"]["session"], "B1Q")
        log = json.loads((self.out / "run_log.json").read_text())
        self.assertEqual(self.rec["binding"]["token"], log["app_identity"]["token"])
        self.assertEqual(log["l6"]["inputs"], {"plan_sha256": self.m["qualification_plan"]["sha256"],
                                               "prediction_sha256": self.m["qualification_plan"]["prediction_sha256"],
                                               "pins_sha256": self.m["pins"]["sha256"]})
        self.assertEqual(self.rec["rulings"]["whole_of_run"]["content"]["session"], "B1Q")
        self.assertEqual(hashlib.sha256((self.out / "manifest_at_run.json").read_bytes()).hexdigest(), self.sha_q)
        self.assertEqual(self.rec["binding"]["master_seed"], QPLAN["master_seed"])
        self.assertNotEqual(QPLAN["master_seed"], PLAN["master_seed"])
        self.assertIn(QPLAN["master_seed"], MANIFEST["seeds"]["excluded"]["b1_qualification"])
        self.assertIn(PLAN["master_seed"], QPLAN["seed_exclusion"]["excluded_master_seeds"])

    def test_verify_readjudicates_and_the_flag_is_derived(self):
        m = self.qualified_manifest()
        v = bq.verify(m)
        self.assertTrue(v["readjudicated"]); self.assertTrue(bq.qualified(m))
        self.assertFalse(bq.qualified(self.m))                        # no record → not qualified
        bare = copy.deepcopy(self.m); bare["carrier"]["qualified"] = True
        self.assertFalse(bq.qualified(bare))                          # a bare flag is nothing

    def test_every_break_in_the_chain_refuses(self):
        good = self.qualified_manifest()
        def refuses(mut, words):
            m = copy.deepcopy(good); mut(m)
            with self.assertRaises(bq.QualificationRefusal) as cm:
                bq.verify(m)
            self.assertIn(words, str(cm.exception))
        refuses(lambda m: m["carrier"].__setitem__("qualification", None), "no carrier.qualification")
        refuses(lambda m: m["carrier"]["qualification"].__setitem__("outcome", "HOLD: x"), "not PASS")
        refuses(lambda m: m["carrier"].__setitem__("bitstream_sha256", "a" * 64), "carrier_sha256")
        refuses(lambda m: m["image"].__setitem__("sha256", "a" * 64), "image_sha256")
        refuses(lambda m: m["prereg"].__setitem__("sha256", "c" * 64), "frozen pin")
        refuses(lambda m: m["instrument"].__setitem__("psoracle_commit", "0" * 40), "psoracle_commit")
        refuses(lambda m: m["qualification_plan"].__setitem__("master_seed", 5), "seed/budget")
        refuses(lambda m: m["carrier"]["qualification"]["files"].__setitem__("run_log.json", "0" * 64), "does not hash")
        refuses(lambda m: m["carrier"]["qualification"].__setitem__("evidence_dir", "/nonexistent"), "absent")
        # the closure the v2.1 review found open: a record token other than the run log's
        refuses(lambda m: m["carrier"]["qualification"]["binding"].__setitem__("token", "f" * 32), "token")
        # the record's ruling copy must equal the verbatim file
        refuses(lambda m: m["carrier"]["qualification"]["rulings"]["whole_of_run"]["content"].__setitem__("master_seed", 5), "ruling content differs")
        refuses(lambda m: m["carrier"]["qualification"]["rulings"]["provisioning"].__setitem__("bytes_sha256", "0" * 64), "ruling hashes")
        refuses(lambda m: m["carrier"]["qualification"]["rulings"]["provisioning"].__setitem__("envelope_sha256", "0" * 64), "ruling hashes")
        # the record's inputs must be manifest_at_run's pins
        refuses(lambda m: m["carrier"]["qualification"]["inputs"].__setitem__("pins_sha256", "0" * 64), "inputs")
        # the current manifest may differ from manifest_at_run only in the qualification state
        refuses(lambda m: m["universe"].__setitem__("note", "edited after the qualification"), "another manifest")
        refuses(lambda m: m["pins"].__setitem__("sha256", "0" * 64), "another manifest")

    def test_a_tampered_evidence_file_breaks_the_chain(self):
        good = self.qualified_manifest()
        d = self.tmp / "tampered"; shutil.copytree(self.out, d)
        good["carrier"]["qualification"]["evidence_dir"] = str(d)
        bq.verify(good)                                              # the copy stands
        log = json.loads((d / "run_log.json").read_text())
        log["loop_records"][3]["evidence"]["arm"]["status_after"] = "0x00000f54"      # tables_match = 1 on a code probe
        text = json.dumps(log); (d / "run_log.json").write_text(text)
        with self.assertRaises(bq.QualificationRefusal) as cm:
            bq.verify(good)
        self.assertIn("does not hash", str(cm.exception))
        # re-pin the tampered file: the RE-ADJUDICATION catches it
        good["carrier"]["qualification"]["files"]["run_log.json"] = hashlib.sha256(text.encode()).hexdigest()
        with self.assertRaises(bq.QualificationRefusal) as cm:
            bq.verify(good)
        self.assertIn("re-adjudicates", str(cm.exception))

    def test_a_tampered_ruling_or_manifest_copy_or_summary_breaks_the_chain(self):
        good = self.qualified_manifest()
        def reseal(env, mut):
            import base64
            r = json.loads(base64.b64decode(env["content_base64"])); mut(r)
            raw = json.dumps(r).encode()
            env["content_base64"] = base64.b64encode(raw).decode(); env["sha256"] = hashlib.sha256(raw).hexdigest()
        for name, mut, words, after in (
                ("ruling_whole_of_run.json", lambda d: reseal(d, lambda r: r.__setitem__("master_seed", 5)), "does not hash", "summary.ruling"),
                ("manifest_at_run.json", lambda d: d["image"].__setitem__("board_ready", False), "does not hash", "b1_manifest_sha256"),
                ("summary.json", lambda d: d.__setitem__("token", "f" * 32), "does not hash", "summary.json")):
            d = self.tmp / f"tamper_{name}"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(self.out, d)
            m = copy.deepcopy(good); m["carrier"]["qualification"]["evidence_dir"] = str(d)
            bq.verify(m)
            doc = json.loads((d / name).read_text()); mut(doc); text = json.dumps(doc, indent=1) + "\n"
            (d / name).write_text(text)
            with self.assertRaises(bq.QualificationRefusal) as cm:
                bq.verify(m)
            self.assertIn(words, str(cm.exception))
            # re-pinned, the CONTENT check catches it
            m["carrier"]["qualification"]["files"][name] = hashlib.sha256(text.encode()).hexdigest()
            if name == "ruling_whole_of_run.json":
                m["carrier"]["qualification"]["rulings"]["whole_of_run"]["sha256"] = m["carrier"]["qualification"]["files"][name]
                m["carrier"]["qualification"]["rulings"]["whole_of_run"]["content"] = doc
            with self.assertRaises(bq.QualificationRefusal) as cm:
                bq.verify(m)
            self.assertIn(after, str(cm.exception))          # the CONTENT / byte binding, not the file hash

    def test_summary_must_name_the_archived_ruling_and_the_provisioning_digest(self):
        good = self.qualified_manifest()
        for mut, words in ((lambda d: d.pop("ruling"), "summary.ruling"),
                           (lambda d: d["ruling"].__setitem__("master_seed", 5), "summary.ruling"),
                           (lambda d: d.__setitem__("provisioning_ruling_sha256", "0" * 64), "provisioning ruling"),
                           (lambda d: d.pop("provisioning_ruling_sha256"), "provisioning ruling")):
            d = self.tmp / "summary_case"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(self.out, d)
            m = copy.deepcopy(good); m["carrier"]["qualification"]["evidence_dir"] = str(d)
            doc = json.loads((d / "summary.json").read_text()); mut(doc); text = json.dumps(doc) + "\n"
            (d / "summary.json").write_text(text)
            m["carrier"]["qualification"]["files"]["summary.json"] = hashlib.sha256(text.encode()).hexdigest()
            with self.assertRaises(bq.QualificationRefusal) as cm:
                bq.verify(m)
            self.assertIn(words, str(cm.exception))

    def test_the_archived_rulings_are_inert_envelopes_that_no_parser_accepts(self):
        """A verbatim copy would be a second, unconsumed authorisation (owner's review
        2026-09-05): the archive must be refused by every ruling parser — the instrument's
        check_ruling / _parse_ruling (the signer's provisioning path uses the latter) and
        this runner's preflight parse — while verify() reads it fine."""
        import b1_runner as rn
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import board_session as bsn
        import pcap_probe_runner as pr
        for key, name in bq.RULING_FILES.items():
            p = self.out / name
            env = json.loads(p.read_text())
            self.assertEqual(env["schema"], bq.ARCHIVE_SCHEMA)
            for field in ("ruling", "boardid", "granted_by", "date", "session"):
                self.assertNotIn(field, env)
            self.assertFalse(p.with_name(p.name + ".consumed").exists())      # no marker — the envelope needs none
            text = qadj.RULING_TEXT if key == "whole_of_run" else bq.PROVISION_RULING_TEXT
            with self.assertRaises(bsn.SessionRefusal):
                pr.check_ruling(p, text)
            with self.assertRaises(bsn.SessionRefusal):
                pr._parse_ruling(p, text)
            # this runner's preflight parse (the first thing it does with a ruling path)
            import types
            a = types.SimpleNamespace(ruling=p, provision_ruling=p, manifest=self.tmp / "q_manifest.json")
            with self.assertRaises(rn.Refusal) as cm:
                rn.preflight(a, rn.QUALIFICATION if key == "whole_of_run" else rn.MAPPING)
            self.assertIn("lacks", str(cm.exception))
            raw, content = bq.read_archived_ruling(p)
            self.assertEqual(content["ruling"], text)

    def test_an_envelope_re_armed_with_ruling_fields_is_refused_even_when_every_hash_is_updated(self):
        """The owner's counter-example: the decoded ruling fields re-added at the envelope's
        top level (the bytes, their hash and the content unchanged), the evidence and record
        hashes updated to match — a parser then accepts the file as a ruling, so verify()
        must refuse it. Also any other extra key, a missing key, a wrong type."""
        good = self.qualified_manifest()
        import base64
        for key, name in bq.RULING_FILES.items():
            d = self.tmp / f"rearmed_{key}"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(self.out, d)
            m = copy.deepcopy(good); m["carrier"]["qualification"]["evidence_dir"] = str(d)
            bq.verify(m)
            env = json.loads((d / name).read_text())
            decoded = json.loads(base64.b64decode(env["content_base64"]))
            env.update({k: decoded[k] for k in ("ruling", "boardid", "granted_by", "date", "session")})
            text = json.dumps(env, indent=1) + "\n"; (d / name).write_text(text)
            sha = hashlib.sha256(text.encode()).hexdigest()
            m["carrier"]["qualification"]["files"][name] = sha
            m["carrier"]["qualification"]["rulings"][key]["envelope_sha256"] = sha
            # the re-armed file IS a ruling to the instrument's parser — which is why verify must refuse it
            inst.bind(inst.DEFAULT_ROOT, require_git=False)
            import pcap_probe_runner as pr
            self.assertEqual(pr._parse_ruling(d / name, decoded["ruling"])["ruling"], decoded["ruling"])
            with self.assertRaises(bq.QualificationRefusal) as cm:
                bq.verify(m)
            self.assertIn("envelope", str(cm.exception))
            with self.assertRaises(bq.QualificationRefusal):
                bq.read_archived_ruling(d / name)
        # any other extra key, a missing key, a wrong type
        p = self.out / bq.RULING_FILES["whole_of_run"]; base = json.loads(p.read_text())
        for mut in (lambda e: e.__setitem__("extra", 1), lambda e: e.pop("sha256"), lambda e: e.pop("note"),
                    lambda e: e.__setitem__("note", 5), lambda e: e.__setitem__("content_base64", 7)):
            e = copy.deepcopy(base); mut(e)
            q = self.tmp / "env_case.json"; q.write_text(json.dumps(e))
            with self.assertRaises(bq.QualificationRefusal):
                bq.read_archived_ruling(q)
        bq.read_archived_ruling(p)

    def test_a_failed_archive_leaves_no_executable_ruling_behind(self):
        from unittest import mock
        tmp = self.tmp / "partial"; tmp.mkdir(exist_ok=True)
        text = manifest_text(self.m); sha = hashlib.sha256(text.encode()).hexdigest()
        mp = tmp / "m.json"; mp.write_text(text)
        wr, pk = rulings_for(self.m, sha)
        rp, pp = tmp / "r.json", tmp / "p.json"
        rp.write_text(json.dumps(wr)); pp.write_text(json.dumps(pk))
        out = tmp / "out"
        real = bq._write_atomic
        calls = []
        def failing(path, text):
            calls.append(path.name)
            if len(calls) == 2:
                raise OSError("disk full (forced)")
            real(path, text)
        with mock.patch.object(bq, "_write_atomic", failing):
            with self.assertRaises(OSError):
                bq.write_session_artifacts(out, mp, rp, pp, sha, expected_rulings=(wr, pk))
        left = sorted(p.name for p in out.iterdir())
        self.assertEqual(left, [])                                     # nothing partial, nothing executable
        # and in any state of the directory, no file parses as a ruling
        bq.write_session_artifacts(out, mp, rp, pp, sha, expected_rulings=(wr, pk))
        for p in out.iterdir():
            doc = json.loads(p.read_text())
            self.assertFalse(isinstance(doc, dict) and "ruling" in doc and "boardid" in doc, p.name)

    def test_archiving_refuses_a_ruling_that_differs_from_the_parsed_one(self):
        tmp = self.tmp / "archive"; tmp.mkdir(exist_ok=True)
        text = manifest_text(self.m); sha = hashlib.sha256(text.encode()).hexdigest()
        mp = tmp / "m.json"; mp.write_text(text)
        wr, pr = rulings_for(self.m, sha)
        rp, pp = tmp / "r.json", tmp / "p.json"
        rp.write_text(json.dumps(wr)); pp.write_text(json.dumps(pr))
        bq.write_session_artifacts(tmp / "ok", mp, rp, pp, sha, expected_rulings=(wr, pr))
        with self.assertRaises(bq.QualificationRefusal):
            bq.write_session_artifacts(tmp / "bad", mp, rp, pp, sha, expected_rulings=({**wr, "master_seed": 5}, pr))
        with self.assertRaises(bq.QualificationRefusal):
            bq.write_session_artifacts(tmp / "bad2", mp, rp, pp, "0" * 64, expected_rulings=(wr, pr))

    def test_a_preregistration_document_edited_after_the_qualification_breaks_the_chain(self):
        """The owner's pure-model reproduction: after the freeze only the document changes;
        the B1Q adjudicator, the verifier and (through it) the mapping adjudicator refuse."""
        good = self.qualified_manifest()
        doc = R / good["prereg"]["path"]; original = doc.read_bytes()
        try:
            doc.write_text("# fixture preregistration, edited after the freeze\n")
            res = qadj.adjudicate(self.out, good, QPLAN, QPRED, self.sha_q, require_git=False)
            self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("changed after the freeze", res["outcome"])
            with self.assertRaises(bq.QualificationRefusal) as cm:
                bq.verify(good)
            self.assertIn("changed after the freeze", str(cm.exception))
        finally:
            doc.write_bytes(original)
        bq.verify(good)

    def test_a_session_run_before_the_freeze_never_qualifies(self):
        m = copy.deepcopy(self.m); m["image"]["board_ready"] = False
        rec, out, res, sha = qualify(self.tmp, m, "prefreeze")
        self.assertEqual(res["outcome"], "PASS")                   # the session itself is fine
        m["carrier"]["qualification"] = rec
        with self.assertRaises(bq.QualificationRefusal) as cm:
            bq.verify(m)
        self.assertIn("board_ready", str(cm.exception))

    def test_a_b1q_log_carrying_the_mapping_inputs_is_refused(self):
        d = self.tmp / "wrong_inputs"; shutil.copytree(self.out, d)
        log = json.loads((d / "run_log.json").read_text())
        log["l6"]["inputs"] = {"plan_sha256": self.m["plan"]["sha256"], "prediction_sha256": self.m["prediction"]["sha256"],
                               "pins_sha256": self.m["pins"]["sha256"]}
        (d / "run_log.json").write_text(json.dumps(log))
        res = qadj.adjudicate(d, self.m, QPLAN, QPRED, self.sha_q, require_git=False)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("inputs plan_sha256", res["outcome"])

    def test_the_gate_observations_are_required_record_by_record(self):
        log = json.loads((self.out / "run_log.json").read_text())
        def findings(mut):
            l = copy.deepcopy(log); mut(l)
            return qadj.gate_findings(l, QPLAN, QPRED)
        self.assertEqual(findings(lambda l: None), [])
        self.assertTrue(any("tables_match = 1" in f for f in findings(lambda l: l["loop_records"][2]["evidence"]["arm"].__setitem__("status_after", "0x00000f54"))))
        self.assertTrue(any("configuration_valid_hw = 0" in f for f in findings(lambda l: l["loop_records"][2]["evidence"]["arm"].__setitem__("status_after", "0x00000b50"))))
        self.assertTrue(any("fault" in f for f in findings(lambda l: l["loop_records"][2]["evidence"]["arm"].__setitem__("fault_after", 3))))
        self.assertTrue(any("(baseline) readout is not all zero" in f for f in findings(lambda l: l["loop_records"][0]["evidence"]["score"].__setitem__("functional_readout", ["1" + "0" * 15] * 6))))
        self.assertTrue(any("(baseline) tables_match = 0" in f for f in findings(lambda l: l["loop_records"][0]["evidence"]["arm"].__setitem__("status_after", "0x00000b54"))))
        self.assertTrue(any("counters" in f for f in findings(lambda l: l["loop_records"][0]["evidence"]["score"].__setitem__("scores", [0] * 6))))
        self.assertTrue(any("did not answer" in f for f in findings(lambda l: l["loop_records"][4]["evidence"]["score"].__setitem__("functional_readout", ["0" * 16] * 6))))
        self.assertTrue(any("must be SCORED" in f for f in findings(lambda l: l["loop_records"][4].__setitem__("outcome", "REFUSED_BY_PL"))))

    def test_the_b1q_adjudicator_refuses_the_mapping_plan_and_the_wrong_session(self):
        res = qadj.adjudicate(self.out, self.m, PLAN, PRED, self.sha_q, require_git=False)
        self.assertTrue(res["outcome"].startswith("REFUSED"), res["outcome"])
        m = copy.deepcopy(self.m); m["qualification_plan"]["sha256"] = "0" * 64
        res = qadj.adjudicate(self.out, m, QPLAN, QPRED, self.sha_q, require_git=False)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("qualification plan", res["outcome"])

    def test_the_mapping_adjudicator_accepts_the_carrier_only_through_the_chain(self):
        m = self.qualified_manifest(); sha = msha(m)
        out = self.tmp / "mapping"
        r = ms.run_modelled(m, PLAN, out, binding_extra={"b1_manifest_sha256": sha})
        self.assertEqual(r["epoch_end"]["kind"], "COMPLETED")
        res = adj.adjudicate(out, m, PLAN, PRED, sha, require_git=False)
        self.assertEqual(res["outcome"], "PASS", res["findings"])
        bad = copy.deepcopy(m); bad["carrier"]["qualification"]["outcome"] = "HOLD: x"
        res = adj.adjudicate(out, bad, PLAN, PRED, msha(bad), require_git=False)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("qualification", res["outcome"])
        # the derived flag must agree with the evidence (the v2.1 review: qualified False, outcome PASS)
        flag = copy.deepcopy(m); flag["carrier"]["qualified"] = False
        res = adj.adjudicate(out, flag, PLAN, PRED, msha(flag), require_git=False)
        self.assertTrue(res["outcome"].startswith("REFUSED")); self.assertIn("disagrees", res["outcome"])

    def test_a_qualification_that_holds_is_recorded_as_such_and_never_qualifies(self):
        d = self.tmp / "hold"; shutil.copytree(self.out, d)
        log = json.loads((d / "run_log.json").read_text())
        log["loop_records"][2]["evidence"]["arm"]["status_after"] = "0x00000f54"
        log["loop_records"][2]["evidence"]["arm"]["settle"]["status_last"] = "0x00000f54"   # a consistent record, wrong observation
        (d / "run_log.json").write_text(json.dumps(log))
        res = qadj.adjudicate(d, self.m, QPLAN, QPRED, self.sha_q, require_git=False)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"])
        self.assertTrue(any("tables_match = 1" in f for f in res["findings"]))
        (d / "adjudication.json").write_text(json.dumps(res)); (d / "summary.json").write_text("{}")
        rec = bq.make_record(d, self.m, self.sha_q, QPLAN, res)
        self.assertTrue(rec["outcome"].startswith("HOLD"))
        m = copy.deepcopy(self.m); m["carrier"]["qualification"] = rec
        self.assertFalse(bq.qualified(m))


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class Lifecycle(unittest.TestCase):
    """freeze → refresh (board_ready survives; the legacy value migrates) → B1Q → pin the
    record through b1_manifest.refresh(--qualification) → qualified derived, board_ready kept
    → the mapping preflight passes every pin (owner's review 2026-09-05, blocker 1)."""

    def test_freeze_b1q_pin_mapping_preflight(self):
        import os, types
        import b1_manifest as bmf
        import b1_runner as rn
        tmp = Path(tempfile.mkdtemp())
        m = json.loads((R / "manifests/b1_manifest.json").read_text())
        # the committed manifest is a DRAFT; whatever it carries under carrier.qualification is
        # either a real record or nothing after a refresh
        doc = tmp / "prereg.md"; doc.write_text("# fixture preregistration\n")
        m["prereg"]["path"] = os.path.relpath(doc, R); m["prereg"]["sha256"] = hashlib.sha256(doc.read_bytes()).hexdigest()
        m["image"]["board_ready"] = True                                # the owner's freeze
        m["carrier"]["qualification"] = "docs/b1_carrier_qualification.md"   # the v2 legacy value
        m = bmf.refresh(m)
        self.assertTrue(m["image"]["board_ready"]); self.assertIsNone(m["carrier"]["qualification"]); self.assertFalse(m["carrier"]["qualified"])
        m2 = bmf.refresh(copy.deepcopy(m))
        self.assertEqual(m2, m)                                        # a refresh is idempotent on an unchanged tree
        # the B1Q session, bound to THIS manifest's bytes
        text = manifest_text(m)
        rec, out, res, sha = qualify(tmp, m, "b1q", text=text)
        self.assertEqual(res["outcome"], "PASS", res["findings"])
        # the owner pins it: verified, then derived
        m3 = bmf.refresh(copy.deepcopy(m), qualification_dir=out)
        self.assertTrue(m3["carrier"]["qualified"]); self.assertTrue(m3["image"]["board_ready"])
        self.assertEqual(m3["carrier"]["qualification"]["binding"]["b1_manifest_sha256"], sha)
        self.assertEqual(bq._strip_transition(m3), bq._strip_transition(m))
        # a drift of the image would reset board_ready and break the chain
        drifted = copy.deepcopy(m3); drifted["image"]["sha256"] = "a" * 64
        drifted = bmf.refresh(drifted)
        self.assertFalse(drifted["image"]["board_ready"])              # the pinned build evidence names another image
        # the mapping preflight: every pin holds; it stops at the boundary record
        mp = tmp / "manifest.json"; mp.write_text(manifest_text(m3)); msha3 = hashlib.sha256(mp.read_bytes()).hexdigest()
        def ruling(name, **f):
            p = tmp / f"{name}.json"; p.write_text(json.dumps({"boardid": "17A6", "granted_by": "test", "date": "2026-09-05-T", **f})); return p
        common = dict(session="B1", prereg_sha256=m3["prereg"]["sha256"], image_sha256=m3["image"]["sha256"], b1_manifest_sha256=msha3)
        a = types.SimpleNamespace(ruling=ruling("b1", ruling=rn.RULING_TEXT, master_seed=m3["seeds"]["master_seed"], **common),
                                  provision_ruling=ruling("k", ruling=rn.PROVISION_RULING_TEXT, **common),
                                  boundary=inst.DEFAULT_ROOT / "evidence/boundary/principal_boundary_2026-09-04-01.json",
                                  out=tmp / "out", manifest=mp, instrument_root=inst.DEFAULT_ROOT,
                                  image=R / "firmware/b1/bsp/out/b1_app.bin", key=Path("/var/lib/p3signer/keys/K.bin"),
                                  signer_user="p3signer", port="/dev/null")
        if not a.image.is_file() or not a.boundary.is_file():
            self.skipTest("built image or boundary record absent")
        with self.assertRaises(Exception) as cm:
            rn.preflight(a, rn.MAPPING)
        msg = str(cm.exception).lower()
        self.assertNotIsInstance(cm.exception, AssertionError)
        self.assertTrue("boundary" in msg or "old" in msg or "runner_user" in msg, msg)
        # and with the record removed after the freeze, the same preflight refuses at the qualification
        m4 = copy.deepcopy(m3); m4["carrier"]["qualification"] = None; m4["carrier"]["qualified"] = False
        mp.write_text(manifest_text(m4)); msha4 = hashlib.sha256(mp.read_bytes()).hexdigest()
        common["b1_manifest_sha256"] = msha4
        a.ruling = ruling("b1b", ruling=rn.RULING_TEXT, master_seed=m4["seeds"]["master_seed"], **common)
        a.provision_ruling = ruling("kb", ruling=rn.PROVISION_RULING_TEXT, **common)
        with self.assertRaises(rn.Refusal) as cm:
            rn.preflight(a, rn.MAPPING)
        self.assertIn("not qualified", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
