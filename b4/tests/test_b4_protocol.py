"""b4/host/b4_protocol.py — the protocol identity (docs/b4_architecture.md section 9.5; the owner's choice 6 of 2026-10-20): built from
the tree's trusted inventory (every tool file held to the import table's digest; refused by name otherwise), covering the whole
execution / judgement stack; the document's revision carried as provenance and excluded from the digest and from the equality;
the thresholds digest without the table's source text; the comparison naming the differing components; an archive without an
identity refused by name; no self-reference. No production module is run; nothing is written to the repository. No skip."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_protocol as bp  # noqa: E402
import b4_thresholds as th  # noqa: E402

SIM3 = R / "evidence/b4/sim/b4-sim-3_20261019T121833Z/manifest.json"
GATE1 = R / "evidence/b4/sim/b4-gate-1_20261020T102526Z/manifest.json"


class TheIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = bp.identity()

    def test_it_is_deterministic_complete_and_excludes_the_document_revision_from_the_digest(self):
        p = self.p
        self.assertEqual(bp.identity_findings(p), [])
        self.assertEqual(bp.canonical(p), bp.canonical(bp.identity()), "deterministic")
        sha = bp.protocol_sha256(p)
        q = copy.deepcopy(p); q["architecture_revision"] = "v9.9.9"
        self.assertEqual(bp.protocol_sha256(q), sha, "the document's revision is provenance: outside the digest")
        self.assertEqual(bp.compare(q, p), [], "and outside the equality")
        self.assertEqual(p["architecture_revision"], th.ARCHITECTURE_REVISION)
        self.assertEqual(p["thresholds_sha256"], bp.thresholds_sha256())
        self.assertEqual(bp.thresholds_sha256(dict(th.THRESHOLDS, source="another document reference")), bp.thresholds_sha256(), "the table's source text is outside the thresholds digest")
        self.assertNotEqual(bp.thresholds_sha256({**th.THRESHOLDS, "K9": {**th.THRESHOLDS["K9"], "median_coverage_per_semantic_min": 0.4}}), bp.thresholds_sha256(), "a number moves it")
        for key in ("engine", "cartographer", "execution", "snapshot", "replay", "target_setup", "controls", "summary", "judgement", "gonogo", "validators", "archive_verifier", "gate_verifier", "identity"):
            self.assertIn(key, p["stack"], "the whole execution / judgement stack is covered")
        for name in ("b4_sim_manifest", "b4_sim_report", "b4_gate_report", "b4_sim_k9", "b4_sim_task", "b4_gonogo_decision", "b4_protocol_identity"):
            self.assertIn(name, p["schemas"]); self.assertEqual(set(p["schemas"][name]), {"version", "validator", "validator_sha256"})
        self.assertEqual(set(p["statistics"]), {"bootstrap_reject_rate", "cohen_d", "mean", "median", "percentile", "required_pairs", "sign_test_p"})
        self.assertEqual(p["labels"], {"gate": "b4-gate-2", "exploration": "b4-sim-4", "retired": ["b4-sim-1", "b4-sim-2"], "consumed": ["b4-gate-1", "b4-sim-3"]})
        self.assertEqual((p["task"]["version"], p["task"]["salt"], p["k9"]["judged"], p["k10"]["tau"]), ("task-v0.2", 0x54415247, "conditional_sr_driven", 2))
        inv = p["inventory"]
        self.assertTrue(all(rel.startswith("b4/host/") or rel.startswith("b4/schemas/") for rel in inv)); self.assertIn("b4/host/b4_protocol.py", inv)
        self.assertNotIn(sha, json.dumps(p), "no self-reference: the payload never carries its own digest")
        table = json.loads((R / "b4/IMPORT.json").read_bytes())
        for rel, d in inv.items():
            self.assertEqual(table["files"][rel]["sha256"], d, rel)
        self.assertEqual(p["import_table_sha256"], bp._sha(bp.canonical({rel: table["files"][rel] for rel in inv}).encode()), "the table's tool-file entries only")
        other = copy.deepcopy(table); other["files"]["b4/tests/test_b4_protocol.py"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory(prefix="b4ident_t_") as tmp:
            root = Path(tmp)
            for rel in ("b4/host", "b4/schemas"):
                shutil.copytree(R / rel, root / rel)
            (root / "b4/IMPORT.json").write_text(json.dumps(other))
            q = bp.identity(root)
            self.assertEqual(bp.protocol_sha256(q), sha, "a test-only entry change is not a new method version")

    def test_the_comparison_names_the_differing_components(self):
        p = self.p
        q = copy.deepcopy(p); q["k9"]["judged"] = "all_panel"; q["task"]["version"] = "task-v0.1"
        f = bp.compare(q, p)
        self.assertEqual(len(f), 1); self.assertIn("k9: judged", f[0]); self.assertIn("task: version", f[0]); self.assertIn("b4_archive_reverification", f[0])
        q = copy.deepcopy(p); q["inventory"]["b4/host/b4_engine.py"] = "0" * 64; q["stack"]["engine"] = "0" * 64
        f = bp.compare(q, p); self.assertIn("inventory: b4/host/b4_engine.py", f[0]); self.assertIn("stack: engine", f[0])
        q = copy.deepcopy(p); q["thresholds_sha256"] = "0" * 64
        self.assertIn("thresholds_sha256", bp.compare(q, p)[0])
        self.assertTrue(bp.compare("x", p)); self.assertTrue(bp.compare({}, p)); self.assertTrue(bp.compare({k: v for k, v in p.items() if k != "task"}, p))
        q = copy.deepcopy(p); q["labels"]["gate"] = "b4-gate-1"
        self.assertIn("labels: gate", bp.compare(q, p)[0])
        self.assertTrue(any("not a sha256" in x for x in bp.identity_findings(dict(p, thresholds_sha256="x"))))
        self.assertTrue(bp.identity_findings(dict(p, schema_version="0.0.1")))
        self.assertTrue(bp.identity_findings(dict(p, inventory={"a": "b"})))

    def test_a_tree_that_is_not_its_inventory_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix="b4ident_") as tmp:
            root = Path(tmp)
            for rel in ("b4/host", "b4/schemas"):
                shutil.copytree(R / rel, root / rel)
            shutil.copy(R / "b4/IMPORT.json", root / "b4/IMPORT.json")
            self.assertEqual(bp.inventory(root), self.p["inventory"], "a faithful copy is the same inventory")
            f = root / "b4/host/b4_engine.py"
            f.write_bytes(f.read_bytes() + b"\n# changed\n")
            with self.assertRaises(bp.IdentityRefusal) as cm:
                bp.inventory(root)
            self.assertIn("b4_engine.py", str(cm.exception)); self.assertIn("digest differs", str(cm.exception))
            (root / "b4/host/b4_extra.py").write_text("x = 1\n")
            f.write_bytes((R / "b4/host/b4_engine.py").read_bytes())
            with self.assertRaises(bp.IdentityRefusal) as cm:
                bp.inventory(root)
            self.assertIn("absent from the table", str(cm.exception))
            (root / "b4/host/b4_extra.py").unlink()
            (root / "b4/IMPORT.json").write_text("not json")
            with self.assertRaises(bp.IdentityRefusal):
                bp.inventory(root)

    def test_the_committed_archives_written_before_the_identity_are_refused_by_name(self):
        """The committed b4-sim-3 and b4-gate-1 manifests (read-only) carry no protocol identity: the named refusal points to the
        re-verification procedure and names the recorded HEAD; nothing is judged."""
        for path in (SIM3, GATE1):
            before = path.read_bytes()
            man = json.loads(before)
            self.assertNotIn("protocol", man)
            msg = bp.refusal_for_missing(man)
            self.assertIn("no protocol identity", msg); self.assertIn(man["head"], msg); self.assertIn("b4_archive_reverification", msg); self.assertIn("v0.1.16", msg)
            self.assertEqual(path.read_bytes(), before)

    def test_a_documentation_only_revision_moves_nothing_of_the_method_in_fresh_interpreters(self):
        """R1 of the owner's review of 04385ae, on the REAL file / import-table workflow, every step a fresh interpreter: the revision lives
        in b4/architecture_revision.json (not a tool file); changing it and refreshing ITS table entry leaves protocol_sha256 unchanged while
        the identity reports the new revision, and the static pin test is GREEN against the document's new first line; a threshold number
        changed without refreshing the table is refused as "not its inventory"; refreshed, the digest moves (a new method version)."""
        def cli(root):
            p = subprocess.run([sys.executable, "-B", str(root / "b4/host/b4_protocol.py")], capture_output=True, text=True)
            return p.returncode, (json.loads(p.stdout) if p.returncode == 0 else p.stdout + p.stderr)

        def refresh(root, rel):
            t = json.loads((root / "b4/IMPORT.json").read_text()); t["files"][rel]["sha256"] = bp._sha((root / rel).read_bytes()); (root / "b4/IMPORT.json").write_text(json.dumps(t))
        with tempfile.TemporaryDirectory(prefix="b4rev_") as tmp:
            root = Path(tmp)
            shutil.copytree(R / "b4", root / "b4", ignore=shutil.ignore_patterns("__pycache__")); (root / "docs").mkdir(); shutil.copy(R / th.ARCHITECTURE_REL, root / th.ARCHITECTURE_REL)
            code, a = cli(root); self.assertEqual(code, 0, a); self.assertEqual((a["protocol_sha256"], a["architecture_revision"]), (bp.protocol_sha256(self.p), th.ARCHITECTURE_REVISION))
            f = root / th.ARCHITECTURE_REVISION_REL; doc = json.loads(f.read_text()); doc["revision"] = "v0.2.1"; f.write_text(json.dumps(doc, indent=1) + "\n"); refresh(root, th.ARCHITECTURE_REVISION_REL)
            d = root / th.ARCHITECTURE_REL; lines = d.read_text().split("\n"); self.assertIn("(DRAFT v0.2.0,", lines[0]); lines[0] = lines[0].replace("(DRAFT v0.2.0,", "(DRAFT v0.2.1,"); d.write_text("\n".join(lines))
            code, b = cli(root); self.assertEqual(code, 0, b)
            self.assertEqual((b["protocol_sha256"], b["architecture_revision"]), (a["protocol_sha256"], "v0.2.1"), "a documentation-only revision: the method's digest does not move")
            pins = subprocess.run([sys.executable, "-B", "-m", "unittest", "b4.tests.test_b4_thresholds"], cwd=root, capture_output=True, text=True)
            self.assertEqual(pins.returncode, 0, pins.stderr[-3000:]); self.assertIn("OK", pins.stderr); self.assertNotIn("Ran 0 tests", pins.stderr)
            tf = root / "b4/host/b4_thresholds.py"; src = tf.read_text(); self.assertEqual(src.count('"median_coverage_per_semantic_min": 0.50'), 1)
            tf.write_text(src.replace('"median_coverage_per_semantic_min": 0.50', '"median_coverage_per_semantic_min": 0.51'))
            code, c = cli(root); self.assertNotEqual(code, 0); self.assertIn("not its inventory", c)
            refresh(root, "b4/host/b4_thresholds.py")
            code, e = cli(root); self.assertEqual(code, 0, e); self.assertNotEqual(e["protocol_sha256"], a["protocol_sha256"], "a number changed and the table refreshed: a new method version")

    def test_the_cli_prints_the_digest(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = bp.main([])
        out = json.loads(buf.getvalue())
        self.assertEqual((code, out["protocol_sha256"]), (0, bp.protocol_sha256(self.p)))


if __name__ == "__main__":
    unittest.main()
