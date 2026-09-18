"""b3/host/b3_manifest.py — the B3 manifest lifecycle S0 → S3, exercised ON DISK in a temp tree, with
the four authorities it cannot have yet behind Python seams (`b3_manifest.Seams`: the pin verifier, the B2
verify, the B1 chain verify, the re-adjudicator). `None` is always the production path; no test and no
flag turns a check off.

The WORLD (one per process, built once, restored from a snapshot for every test): a temp ROOT holding byte
copies of the seven audited frozen inputs, a fixture B1 manifest, a fixture pin table, a fixture image
with its build evidence, a fixture preregistration, a lifecycle-2 gate FIXTURE shaped to select
B* = 1 000 / N = 8 (the committed prediction's numbers, so the preflight's stop rule passes — a fixture,
never a gate result), and the plan / prediction / B3Q documents written by the plan tool itself. The
manifest is then carried S0 → S1 → S2 → S3 THROUGH THE COMMAND LINE (`b3_manifest.main`), with a modelled
B3Q evidence directory produced by the runner's own session-plan, artifact, verdict and session-record
code over fake ports (no device, no subprocess) and RE-ADJUDICATED by the production
`b3_runner.readjudicator` over the same fake ports. Test readiness, never a qualification.

This unit does not execute S0: nothing here touches manifests/b3_manifest.json, the pin table, the image,
the B3Q documents or the canonical plan of the real tree; the real tree is only READ (the production
refusals, which name what is still absent through injected absences, never a permanent "must not exist").
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host", R / "b3/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import test_b3_runner as rt  # noqa: E402 — binds the instrument host-only; the modelled evidence helpers
import b1_qualification as b1q  # noqa: E402
import b2_manifest as b2man  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b3_gate as b3g  # noqa: E402
import b3_manifest as bman  # noqa: E402
import b3_plan as pl  # noqa: E402
import b3_records as brec  # noqa: E402
import b3_runner as rn  # noqa: E402
import b3_test_fixtures as fx  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402
import l6_schedule as ls  # noqa: E402

BOARD = "17A6"
STUB_RATE = 4000.0                  # a fixture's rate, never a calibration
DISPOSITION = "CH340 single-byte-deletion stop-loss in force; no session-scoped exception (fixture)"
EVIDENCE_REL = "evidence/b3/b3q_fixture_run"
_SAVED: int | None = None
_WORLD = None


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def use_fixture_thresholds() -> None:
    """The gate fixture is written AND validated under 100 bootstrap experiments (the validator's cache key
    includes the thresholds). Idempotent; `restore_thresholds` undoes it."""
    global _SAVED
    if _SAVED is None:
        _SAVED = b3g.THRESHOLDS["H2_bootstrap_experiments"]
    b3g.THRESHOLDS["H2_bootstrap_experiments"] = 100


def restore_thresholds() -> None:
    global _SAVED
    if _SAVED is not None:
        b3g.THRESHOLDS["H2_bootstrap_experiments"] = _SAVED
        _SAVED = None


def setUpModule():
    use_fixture_thresholds()
    world()


def tearDownModule():
    restore_thresholds()


class World:
    """The temp tree, its snapshots per stage, and the seams."""

    STAGES = ("pre", "S0", "S1", "S2", "S3")

    def __init__(self, rate: float = STUB_RATE):
        self.root = Path(tempfile.mkdtemp(prefix="b3life_")).resolve()
        self.snap = Path(tempfile.mkdtemp(prefix="b3life_snap_")).resolve()
        self.rate = rate
        self.calls: list[str] = []
        self.manifest_path = self.root / bman.MANIFEST_REL
        self.evidence = self.root / EVIDENCE_REL
        self._patch = mock.patch.object(rn, "B1_MANIFEST", self.root / bman.B1_MANIFEST_REL)
        self._patch.start()
        try:
            self._build()
        except BaseException:
            self.close()
            raise

    def close(self):
        self._patch.stop()
        shutil.rmtree(self.root, True)
        shutil.rmtree(self.snap, True)

    # -- the tree
    def _put(self, rel: str, data) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            p.write_bytes(data)
        else:
            p.write_text(data if isinstance(data, str) else json.dumps(data, indent=1, sort_keys=True) + "\n")
        return p

    def _snapshot(self, name: str) -> None:
        shutil.copytree(self.root, self.snap / name, symlinks=True)

    def at(self, stage: str) -> "World":
        """The tree exactly as it was at `stage` — the SAME root path (the plan documents carry the gate's
        absolute path), every file restored."""
        shutil.rmtree(self.root)
        shutil.copytree(self.snap / stage, self.root, symlinks=True)
        self.calls.clear()
        return self

    def _build(self) -> None:
        root = self.root
        for rel in bman.FROZEN_INPUTS:
            self._put(rel, (R / rel).read_bytes())
        bit = self._put("builds/b1/b1.bit", b"fixture carrier bitstream")
        cm = self._put("builds/b1/carrier_manifest.json", "{}\n")
        self._put(bman.B1_MANIFEST_REL, {"schema": "b1_manifest", "board": {"boardid": BOARD, "role": "fixture", "part": "xc7z010", "idcode": "0x13722093"},
                                         "carrier": {"bitstream": "builds/b1/b1.bit", "bitstream_sha256": sha(bit), "variant": bman.B3_VARIANT,
                                                     "nonce_seed": "00000000", "carrier_manifest": {"path": "builds/b1/carrier_manifest.json", "sha256": sha(cm)},
                                                     "qualification": {"fixture": True}, "qualified": True},
                                         "protocol": {"wire": "rel-v4"}})
        self._put(bman.PIN_TABLE_REL, {"schema": "fixture pin table", "files": {}})
        self._put(bman.PREREG_REL, "# fixture preregistration\n")
        image = self._put(bman.IMAGE_REL, b"fixture B3 image bytes")
        self._put(bman.BUILD_EVIDENCE_REL, {"schema": "fixture build evidence",
                                            "image": {"path": bman.IMAGE_REL, "sha256": sha(image), "elf_sha256": "e" * 64, "bytes": image.stat().st_size}})
        gate = fx.write_gate_fixture(root / "evidence/b3/gate_2", mutate_rows=fx.rows_selecting_budget_1000)
        g = pl.gate_inputs(gate)
        _master, seeds, _s, _e = pl.session_seeds(g["pairs"], gate)
        map_sha = bmaps.sha256_of(bmaps.load_self_map())
        self.prediction = pl.build_prediction(g["fitness"], g["budget_per_arm"], seeds, map_sha)
        pl.write(root / "evidence/b3", pl.build_plan(None, gate), self.prediction)
        pl.write_qualification(root / "evidence/b3", pl.build_qualification_plan(g["fitness"], map_sha, seeds, gate),
                               pl.build_qualification_prediction(g["fitness"], map_sha, seeds, gate))
        self._snapshot("pre")
        self.cli("init")
        self._snapshot("S0")
        self.cli("freeze", "--prereg-sha256", sha(root / bman.PREREG_REL))
        self._snapshot("S1")
        make_b3q_evidence(self, self.evidence)
        self.cli("qualify", "--evidence-dir", str(self.evidence))
        self._snapshot("S2")
        pl.write(root / "evidence/b3", pl.build_plan(self.rate, gate), self.prediction)         # the S3 plan: the canonical path, regenerated from the calibration
        self.cli("plan", "--plan", str(root / bman.PLAN_REL))
        self._snapshot("S3")

    # -- the seams
    def ports(self, rate: float | None = None, policy: str | None = None) -> rn.Ports:
        calls = self.calls

        def instrument_layer(evidence, log, session_plan, iroot):
            calls.append("instrument_layer")
            r = self.rate if rate is None else rate
            return {"findings": [], "rejected": None, "rate": r, "audit_policy": policy or session_plan["audit_policy"], "rate_report": {"evals_per_hour": r}}
        return rn.Ports(schedule=lambda: ls, instrument_layer=instrument_layer, consts=rt.CONSTS, common_validation=False)

    def seams(self, manifest: dict | None = None, **over) -> bman.Seams:
        calls = self.calls
        if manifest is None:
            try:
                manifest = self.manifest()
            except (OSError, ValueError):
                manifest = {}
        m = manifest

        def b2(root):
            calls.append("b2")
            return dict(bman.B2_REQUIRED)

        def b1(b1_manifest, root):
            calls.append("b1")

        def pins(manifest_, root):
            calls.append("pins")
            return {"verified": "fixture"}

        def again(evidence_dir, manifest_at_run=None):
            calls.append("readjudicate")
            return rn.readjudicator(m, ports=self.ports(), root=self.root)(evidence_dir, manifest_at_run)
        s = bman.Seams(pins=pins, b2=b2, b1=b1, readjudicate=again)
        for k, v in over.items():
            setattr(s, k, v)
        return s

    # -- the manifest on disk, the API and the CLI
    def manifest(self) -> dict:
        return json.loads(self.manifest_path.read_text())

    def write_manifest(self, m: dict) -> None:
        self.manifest_path.write_text(bman.render(m))

    def verify(self, m: dict | None = None, **over) -> dict:
        m = self.manifest() if m is None else m
        return bman.verify(m, root=self.root, seams=self.seams(m, **over))

    def cli(self, *argv: str, expect: int = 0, **over) -> str:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = bman.main(list(argv), root=self.root, seams=self.seams(**over))
        if rc != expect:
            raise AssertionError(f"b3_manifest {' '.join(argv)} exited {rc}, expected {expect}: {err.getvalue()[:3000]}")
        return out.getvalue() + err.getvalue()


def world() -> World:
    """The process's one world, built under the fixture thresholds on first use (this module's and
    test_b3_plan's StageCoverage share it)."""
    global _WORLD
    if _WORLD is None:
        import atexit
        use_fixture_thresholds()
        _WORLD = World()
        atexit.register(_WORLD.close)
    return _WORLD


def make_b3q_evidence(w: World, out: Path, tamper=None, rate: float | None = None) -> dict:
    """A modelled B3Q evidence directory for the S1 manifest on disk, written by the runner's own code
    in the production order: the archived manifest and rulings, the session's five files and their seal,
    the session verdict (`judge_session`) as adjudication.json, then summary.json and runner_session.json."""
    manifest = w.manifest()
    msha = sha(w.manifest_path)
    ports = w.ports(rate)
    qplan, qpred, _pin = rn.pinned_documents(manifest, "qualification_plan", rn.QUAL_SESSION, w.root)
    records = pl.session_records(pl.QUAL_PAIRS, pl.QUAL_BUDGET)
    frames = ls.expected_frames(records - 2, set(range(1, records + 1)), "rel-v4")
    common = {"boardid": BOARD, "granted_by": "the owner (fixture)", "date": "2026-09-18", "session": rn.QUAL_SESSION,
              "prereg_sha256": manifest["prereg"]["sha256"], "image_sha256": manifest["image"]["sha256"], "b3_manifest_sha256": msha}
    ruling = {"ruling": rn.QUAL_RULING_TEXT, **common, "master_seed": qplan["seed_derivation"]["master_seed"], "pair_first": 0, "pair_count": 1,
              "transport_disposition": DISPOSITION, "resend_budget": rn.resend_budget(frames["total"])}
    pk = {"ruling": rn.PROVISION_RULING_TEXT, **common}
    rd = w.root / "rulings_fixture"
    rd.mkdir(exist_ok=True)
    (rd / "b3q.json").write_text(json.dumps(ruling))
    (rd / "pk.json").write_text(json.dumps(pk))
    out.mkdir(parents=True, exist_ok=False)
    rn._prod_write_artifacts(out, w.manifest_path, rd / "b3q.json", rd / "pk.json", msha, (ruling, pk))
    session_plan = rn.qualification_session_plan(manifest, msha, qplan, DISPOSITION, ports)
    cfg = {"plan": session_plan, "manifest": manifest, "context": brec.context_from(qplan, qpred, 0, 1), "profile": rn.QUALIFICATION}
    log = rt.Fixture.run_log(None, cfg, tamper)
    log["app_identity"]["token"] = "fixture-token"

    def judge(evidence_dir):
        return rn.judge_session(evidence_dir, manifest, session_plan, qplan, qpred, inst.DEFAULT_ROOT, ports)
    summary = rt.write_evidence(out, cfg, log, judge)
    summary.update(ruling=ruling, provisioning_ruling_sha256=sha(rd / "pk.json"), token="fixture-token")
    (out / "summary.json").write_text(json.dumps(summary, default=str))
    rn.write_session_record(out, cfg, str(summary["outcome"]), summary, "session", [])
    return summary


# ------------------------------------------------------------------ the tests


class Base(unittest.TestCase):
    def setUp(self):
        self.w = world()

    def refused(self, needle: str, fn, *a, **k) -> str:
        with self.assertRaises(bman.Refusal) as cm:
            fn(*a, **k)
        self.assertIn(needle, str(cm.exception))
        return str(cm.exception)

    def cli_refused(self, needle: str, *argv, **over) -> str:
        """A refused command: exit 2, REFUSED naming the cause, the manifest bytes (or its absence) unchanged,
        no temp file left."""
        before = self.w.manifest_path.read_bytes() if self.w.manifest_path.is_file() else None
        text = self.w.cli(*argv, expect=2, **over)
        self.assertIn("REFUSED:", text)
        self.assertIn(needle, text)
        self.assertNotIn("INTERNAL ERROR", text)
        after = self.w.manifest_path.read_bytes() if self.w.manifest_path.is_file() else None
        self.assertEqual(before, after, "a refused command changed the manifest")
        self.assertEqual([p.name for p in self.w.manifest_path.parent.iterdir() if p.name.endswith(".part")], [])
        return text

    def mutated(self, stage: str, mutate) -> dict:
        m = self.w.at(stage).manifest()
        mutate(m)
        return m


class LegalPath(Base):
    def test_every_stage_verifies_and_reports_itself(self):
        for stage in bman.STAGES:
            with self.subTest(stage=stage):
                w = self.w.at(stage)
                res = w.verify()
                self.assertEqual((res["stage"], res["qualified"], res["refusal"]), (stage, stage >= "S2", None))
                self.assertEqual(res["manifest_sha256"], sha(w.manifest_path), "the file on disk is the canonical rendering a ruling binds to")
                self.assertEqual(w.manifest()["status"], bman.STATUS[stage])
                self.assertEqual(w.calls[:3], ["b2", "b1", "pins"])
                self.assertEqual("readjudicate" in w.calls, stage >= "S2", "the evidence is re-adjudicated at every verify from S2 on")

    def test_each_transition_changed_only_what_it_licenses(self):
        docs = {s: json.loads((self.w.snap / s / bman.MANIFEST_REL).read_text()) for s in bman.STAGES}
        for a, b in zip(bman.STAGES, bman.STAGES[1:]):
            self.assertEqual(bman.check_transition(docs[a], docs[b]), (a, b))
            changed = {d.split(":")[0].split("[")[0] for d in b3g.deep_findings(docs[a], docs[b])}
            licensed = {".".join(p) for p in bman.TRANSITIONS[(a, b)]}
            self.assertTrue(all(any(c == l or c.startswith(l + ".") for l in licensed) for c in changed), (a, b, changed))
        self.assertEqual({json.dumps(docs[s]["qualification_plan"], sort_keys=True) for s in bman.STAGES}.__len__(), 1,
                         "B3Q's pinned experiment never changes after S0")

    def test_s0_pins_the_seven_the_table_the_image_and_b3qs_documents(self):
        m = self.w.at("S0").manifest()
        self.assertEqual(m["frozen_inputs"], bman.FROZEN_INPUTS)
        self.assertEqual(len(bman.FROZEN_INPUTS), 7)
        self.assertIn("schemas/specimen_ledger.schema.json", m["frozen_inputs"])
        self.assertEqual(m["b2_authority"]["required"], {"stage": "S3", "qualified": True, "refusal": None, "manifest_sha256": bman.B2_MANIFEST_SHA256})
        self.assertEqual(m["instrument_pins"], {"path": bman.PIN_TABLE_REL, "sha256": sha(self.w.root / bman.PIN_TABLE_REL)})
        self.assertEqual((m["image"]["sha256"], m["image"]["bytes"], m["image"]["board_ready"]),
                         (sha(self.w.root / bman.IMAGE_REL), (self.w.root / bman.IMAGE_REL).stat().st_size, False))
        self.assertIn(bman.BUILD_EVIDENCE_REL, m["image"]["note"])
        self.assertEqual(m["qualification_plan"]["sha256"], sha(self.w.root / bman.QUAL_PLAN_REL))
        self.assertEqual((m["qualification_plan"]["records"], m["qualification_plan"]["ledger_entries"], m["qualification_plan"]["budget_per_arm"]), (125, 40, 40))
        self.assertEqual(m["prediction"]["sha256"], sha(self.w.root / bman.PREDICTION_REL))
        plan = json.loads((self.w.root / bman.PLAN_REL).read_text())
        self.assertEqual((m["experiment"]["fitness"], m["experiment"]["budget_per_arm"], m["experiment"]["pairs"], m["seeds"]["master_seed"]),
                         (plan["fitness"], plan["budget_per_arm"], plan["pairs"], plan["seed_derivation"]["master_seed"]))
        self.assertEqual(m["instrument"]["psoracle_commit"], plan["seed_derivation"]["commit"])
        self.assertEqual(m["map"]["canonical_json_sha256"], plan["map"]["sha256"])

    def test_the_s2_calibration_is_the_measured_rate_under_the_frozen_margin(self):
        m = self.w.at("S2").manifest()
        cal = m["calibration"]
        self.assertEqual(set(cal), set(bman.CALIBRATION_KEYS))
        self.assertEqual((cal["rate_per_hour"], cal["margin"], cal["rate_for_split"]), (self.w.rate, 0.85, self.w.rate * 0.85))
        self.assertEqual(cal["audit_policy"], "all-self-reporting")
        self.assertEqual(sorted(m["qualification"]["files"]), sorted(b1q.EVIDENCE_FILES + (bman.RUNNER_SESSION,)))
        self.assertEqual(len(m["qualification"]["files"]), 12)
        self.assertEqual(m["qualification"]["qualification_block"]["fitness_values"], 123)
        self.assertEqual((m["qualification"]["qualification_block"]["ledger_entries"], m["qualification"]["qualification_block"]["baselines"]), (40, 2))
        self.assertEqual(m["qualification"]["qualification_block"]["fitness_sequence_sha256"], m["qualification_plan"]["fitness_sequence_sha256"])
        self.assertEqual(m["qualification"]["binding"]["b3_manifest_sha256"], sha(self.w.snap / "S1" / bman.MANIFEST_REL))

    def test_the_s3_pin_is_the_plan_files_own_numbers(self):
        m = self.w.at("S3").manifest()
        plan = json.loads((self.w.root / m["plan"]["path"]).read_text())
        self.assertEqual(plan["session_split"]["status"], "DETERMINED")
        self.assertEqual(plan["session_split"]["rate_for_split"], m["calibration"]["rate_for_split"])
        self.assertEqual((m["plan"]["sessions"], m["plan"]["total_records"]), (len(plan["session_split"]["sessions"]), plan["session_split"]["total_records"]))
        self.assertEqual((m["plan"]["sha256"], m["plan"]["prediction_sha256"]), (sha(self.w.root / m["plan"]["path"]), sha(self.w.root / m["plan"]["prediction_path"])))
        self.assertEqual(m["plan"]["prediction_sha256"], m["prediction"]["sha256"], "the S3 sidecar is the prediction pinned at S0")


class FixedPrefixOrder(Base):
    """1 the seven → 2 B2 → 3 B1 → 4 B3's own: with several things wrong at once, the EARLIEST is the one
    named, and nothing later was even consulted."""

    def test_the_earliest_failure_wins_and_later_authorities_are_not_consulted(self):
        def b2_bad(root):
            self.w.calls.append("b2")
            raise b2man.Refusal("pins: pinned files changed")

        def b1_bad(m1, root):
            self.w.calls.append("b1")
            raise b1q.QualificationRefusal("the chain is broken")

        def pins_bad(m, root):
            self.w.calls.append("pins")
            raise bman.Refusal("instrument pins: not in the table")
        w = self.w.at("S1")
        (w.root / bman.IMAGE_REL).unlink()
        first = next(iter(bman.FROZEN_INPUTS))
        (w.root / first).write_bytes((w.root / first).read_bytes() + b" ")
        self.refused(f"frozen inputs: {first} drifted", w.verify, b2=b2_bad, b1=b1_bad, pins=pins_bad)
        self.assertEqual(w.calls, [])
        (w.root / first).write_bytes((R / first).read_bytes())
        self.refused("B2 lineage: pins: pinned files changed", w.verify, b2=b2_bad, b1=b1_bad, pins=pins_bad)
        self.assertEqual(w.calls, ["b2"])
        w.calls.clear()
        self.refused("B1 lineage: the B1 qualification chain does not verify now: the chain is broken", w.verify, b1=b1_bad, pins=pins_bad)
        self.assertEqual(w.calls, ["b2", "b1"])
        w.calls.clear()
        self.refused("instrument pins: not in the table", w.verify, pins=pins_bad)
        self.assertEqual(w.calls, ["b2", "b1", "pins"])
        w.calls.clear()
        self.refused(f"image: the image binary {bman.IMAGE_REL} is absent", w.verify)

    def test_a_wrong_schema_is_refused_before_anything(self):
        self.refused("not a b3_manifest", self.w.at("S0").verify, {"schema": "b2_manifest"})
        self.assertEqual(self.w.calls, [])


class FrozenInputs(Base):
    def test_each_of_the_seven_absent_and_one_byte_drifted_on_verify(self):
        for rel in bman.FROZEN_INPUTS:
            for how in ("absent", "drift"):
                with self.subTest(rel=rel, how=how):
                    w = self.w.at("S3")
                    p = w.root / rel
                    if how == "absent":
                        p.unlink()
                        self.refused(f"frozen inputs: {rel} is absent", w.verify)
                    else:
                        data = bytearray(p.read_bytes())
                        data[len(data) // 2] ^= 1
                        p.write_bytes(bytes(data))
                        self.refused(f"frozen inputs: {rel} drifted", w.verify)
                    self.assertEqual(w.calls, [], "nothing after the pre-check ran")

    def test_each_of_the_seven_absent_and_drifted_on_init_writes_no_manifest(self):
        for rel in bman.FROZEN_INPUTS:
            for how in ("absent", "drift"):
                with self.subTest(rel=rel, how=how):
                    w = self.w.at("pre")
                    p = w.root / rel
                    if how == "absent":
                        p.unlink()
                    else:
                        p.write_bytes(p.read_bytes() + b"\n")
                    self.cli_refused(f"frozen inputs: {rel}", "init")
                    self.assertFalse(w.manifest_path.exists())
                    self.assertEqual(w.calls, [])

    def test_the_path_set_and_the_digests_are_fixed(self):
        rel = "schemas/specimen_ledger.schema.json"
        self.refused("the path set is not exactly the seven audited inputs (missing ['schemas/specimen_ledger.schema.json']",
                     self.w.verify, self.mutated("S1", lambda m: m["frozen_inputs"].pop(rel)))
        self.refused("unexpected ['b3/schemas/specimen_ledger.schema.json']",
                     self.w.verify, self.mutated("S1", lambda m: m["frozen_inputs"].__setitem__("b3/schemas/specimen_ledger.schema.json", "0" * 64)))
        self.refused(f"frozen inputs: the manifest pins {rel} at", self.w.verify, self.mutated("S1", lambda m: m["frozen_inputs"].__setitem__(rel, "0" * 64)))
        self.refused("no frozen_inputs block", self.w.verify, self.mutated("S1", lambda m: m.__setitem__("frozen_inputs", None)))
        self.assertEqual(self.w.calls, [])


class B2AndB1Authority(Base):
    def test_each_wrong_field_of_the_b2_verify_is_named(self):
        w = self.w.at("S1")
        for key, bad, shown in (("stage", "S2", "stage = 'S2'"), ("qualified", False, "qualified = False"), ("qualified", 1, "qualified = 1"),
                                ("refusal", "the plan drifted", "refusal = 'the plan drifted'"), ("manifest_sha256", "0" * 64, "manifest_sha256 = 0000000000000000…")):
            with self.subTest(key=key, bad=bad):
                self.refused(f"B2 lineage: the B2 verify gives {shown}, B3 requires", w.verify, b2=lambda root, k=key, v=bad: {**bman.B2_REQUIRED, k: v})
        self.refused("B2 lineage: the B2 verify gives stage = '<absent>'", w.verify, b2=lambda root: {})
        self.refused("B2 lineage: the B2 verify returned NoneType", w.verify, b2=lambda root: None)
        self.refused("b2_authority block is not the frozen requirement", w.verify, self.mutated("S1", lambda m: m["b2_authority"]["required"].__setitem__("stage", "S2")))

    def test_a_declared_refusal_is_renamed_and_anything_else_is_an_internal_error(self):
        w = self.w.at("S1")

        def declared(root):
            raise b2man.Refusal("S3: the pinned plan file is absent or changed")

        def defect(root):
            raise KeyError("carrier")
        self.refused("B2 lineage: S3: the pinned plan file is absent or changed", w.verify, b2=declared)
        with self.assertRaises(KeyError):
            w.verify(b2=defect)
        before = w.manifest_path.read_bytes()
        text = w.cli("verify", expect=3, b2=defect)
        self.assertIn("INTERNAL ERROR: KeyError", text)
        self.assertIn("Traceback", text)
        self.assertNotIn("REFUSED", text)
        text = w.cli("freeze", "--prereg-sha256", "0" * 64, expect=3, b2=defect)
        self.assertIn("INTERNAL ERROR: KeyError", text)
        self.assertEqual(w.manifest_path.read_bytes(), before)

    def test_the_b1_lineage_declared_refusal_and_defect(self):
        w = self.w.at("S1")

        def declared(m1, root):
            raise b1q.QualificationRefusal("evidence file run_log.json changed")

        def defect(m1, root):
            raise AttributeError("'NoneType' object has no attribute 'get'")
        self.refused("B1 lineage: the B1 qualification chain does not verify now: evidence file run_log.json changed", w.verify, b1=declared)
        with self.assertRaises(AttributeError):
            w.verify(b1=defect)
        self.assertIn("INTERNAL ERROR: AttributeError", w.cli("verify", expect=3, b1=defect))
        p = w.root / bman.B1_MANIFEST_REL
        p.write_text(p.read_text() + " ")
        self.refused("B1 lineage: the manifest's carrier_lineage.b1_manifest.sha256", w.verify)
        self.assertNotIn("b1", w.calls, "the chain is not re-verified for a B1 manifest the lineage does not pin")
        p.unlink()
        self.refused(f"B1 lineage: {bman.B1_MANIFEST_REL} is absent", w.verify)
        self.refused("B1 lineage: the manifest's board.boardid", self.w.verify, self.mutated("S1", lambda m: m["board"].__setitem__("boardid", "08EB")))

    def test_none_is_the_production_b2_and_b1_never_a_skip_and_nothing_is_unpacked(self):
        """In the temp tree the B2 manifest is a byte copy but B2's own pinned files are not there: the
        PRODUCTION B2 verify refuses, under the B3 name — and the completion archive stays packed."""
        w = self.w.at("S1")
        listing = sorted(str(p.relative_to(w.root)) for p in w.root.rglob("*"))
        msg = self.refused("B2 lineage: ", w.verify, b2=None)
        self.assertNotIn("b2", w.calls, "the injected B2 seam was not what ran")
        self.assertEqual(sorted(str(p.relative_to(w.root)) for p in w.root.rglob("*")), listing, f"the working tree changed ({msg[:80]})")
        self.refused("B1 lineage: the B1 qualification chain does not verify now", w.verify, b1=None)


class PinsImageAndDocuments(Base):
    def both(self, needle: str, mutate_tree) -> None:
        """The same absence or drift: verify at S1 refuses by name, and init refuses by name and writes nothing."""
        w = self.w.at("S1")
        mutate_tree(w.root)
        self.refused(needle, w.verify)
        w = self.w.at("pre")
        mutate_tree(w.root)
        self.cli_refused(needle, "init")
        self.assertFalse(w.manifest_path.exists())

    @staticmethod
    def edit(rel: str, mutate):
        def go(root: Path):
            doc = json.loads((root / rel).read_text())
            mutate(doc)
            (root / rel).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
        return go

    def test_the_pin_table(self):
        self.both(f"instrument pins: {bman.PIN_TABLE_REL} is absent", lambda root: (root / bman.PIN_TABLE_REL).unlink())
        w = self.w.at("S1")
        (w.root / bman.PIN_TABLE_REL).write_text((w.root / bman.PIN_TABLE_REL).read_text() + " ")
        self.refused("the manifest's instrument_pins is not what the tree gives now: instrument_pins.sha256", w.verify)
        self.assertNotIn("pins", w.calls)

    def test_the_tables_content_goes_through_the_production_verifier_or_is_refused_by_name(self):
        """pins=None is production. b3_pins absent (an INJECTED absence) → the named refusal: a table pinned by
        hash alone is not accepted. A b3_pins that declares PinRefusal → renamed; its defect → propagates."""
        w = self.w.at("S1")
        with mock.patch.dict(sys.modules, {"b3_pins": None}):
            self.refused("instrument pins: b3/host/b3_pins.py does not exist yet", w.verify, pins=None)
            w.at("pre")
            self.cli_refused("instrument pins: b3/host/b3_pins.py does not exist yet", "init", pins=None)
        d = self.w.at("S1").root / "fake_authority"
        d.mkdir()
        (d / "b3_pins.py").write_text("class PinRefusal(Exception):\n    pass\n\n\ndef verify(manifest=None):\n"
                                      "    if manifest.get('lifecycle') == 2:\n        raise PinRefusal('b3/host/new.py is not in the table')\n")
        with mock.patch.object(sys, "path", [str(d)] + sys.path), mock.patch.dict(sys.modules):
            sys.modules.pop("b3_pins", None)
            self.refused("instrument pins: b3/host/new.py is not in the table", w.verify, pins=None)
        (d / "b3_pins.py").write_text("def verify(manifest=None):\n    return manifest['no such key']\n")
        with mock.patch.object(sys, "path", [str(d)] + sys.path), mock.patch.dict(sys.modules):
            sys.modules.pop("b3_pins", None)
            with self.assertRaises(KeyError):
                w.verify(pins=None)
        (d / "b3_pins.py").write_text("import no_such_dependency_b3_lifecycle\n")
        with mock.patch.object(sys, "path", [str(d)] + sys.path), mock.patch.dict(sys.modules):
            sys.modules.pop("b3_pins", None)
            with self.assertRaises(ModuleNotFoundError) as cm:
                w.verify(pins=None)
            self.assertEqual(cm.exception.name, "no_such_dependency_b3_lifecycle")

    def test_the_image_and_its_build_evidence(self):
        self.both(f"image: the build evidence {bman.BUILD_EVIDENCE_REL} is absent", lambda root: (root / bman.BUILD_EVIDENCE_REL).unlink())
        self.both(f"image: the image binary {bman.IMAGE_REL} is absent", lambda root: (root / bman.IMAGE_REL).unlink())
        self.both("image: the image binary hashes to", lambda root: (root / bman.IMAGE_REL).write_bytes(b"fixture B3 image bytez"))
        self.both("bytes, the build evidence says", self.edit(bman.BUILD_EVIDENCE_REL, lambda d: d["image"].__setitem__("bytes", d["image"]["bytes"] + 1)))
        self.both("image: the build evidence's bytes True", self.edit(bman.BUILD_EVIDENCE_REL, lambda d: d["image"].__setitem__("bytes", True)))
        self.both("image: the build evidence's sha256 is not 64 lower-case hex", self.edit(bman.BUILD_EVIDENCE_REL, lambda d: d["image"].__setitem__("sha256", "placeholder")))
        self.both("image: the build evidence names 'firmware/b2/bsp/out/b2_app.bin'",
                  self.edit(bman.BUILD_EVIDENCE_REL, lambda d: d["image"].__setitem__("path", "firmware/b2/bsp/out/b2_app.bin")))
        self.both("carries no image record", self.edit(bman.BUILD_EVIDENCE_REL, lambda d: d.pop("image")))
        w = self.w.at("S1")                                   # evidence still self-consistent, but no longer the pinned bytes
        self.edit(bman.BUILD_EVIDENCE_REL, lambda d: d.__setitem__("rebuilt", True))(w.root)
        self.refused("the manifest's image is not what the tree gives now: image.build_evidence.sha256", w.verify)
        self.refused("the manifest's image is not what the tree gives now: image.sha256", self.w.verify,
                     self.mutated("S1", lambda m: m["image"].__setitem__("sha256", "0" * 64)))

    def test_the_preregistration(self):
        self.both(f"prereg: {bman.PREREG_REL} is absent", lambda root: (root / bman.PREREG_REL).unlink())
        w = self.w.at("S1")
        (w.root / bman.PREREG_REL).write_text("# fixture preregistration.\n")
        self.refused("prereg: the frozen preregistration file changed", w.verify)
        w = self.w.at("S0")
        (w.root / bman.PREREG_REL).write_text("# an edit before the freeze is not a drift\n")
        self.assertEqual(w.verify()["stage"], "S0")

    def test_b3qs_documents(self):
        self.both(f"qualification plan: {bman.QUAL_PLAN_REL} is absent", lambda root: (root / bman.QUAL_PLAN_REL).unlink())
        self.both(f"qualification plan: {bman.QUAL_PREDICTION_REL} is absent", lambda root: (root / bman.QUAL_PREDICTION_REL).unlink())
        self.both("is not the canonical B3Q plan: budget_per_arm: 41, expected 40", self.edit(bman.QUAL_PLAN_REL, lambda d: d.__setitem__("budget_per_arm", 41)))
        self.both("is not the canonical B3Q plan: prediction_sha256", self.edit(bman.QUAL_PLAN_REL, lambda d: d.__setitem__("prediction_sha256", "0" * 64)))
        self.both("is not the canonical B3Q prediction: pairs[0].runs.O.ledger[7].fitness",
                  self.edit(bman.QUAL_PREDICTION_REL, lambda d: d["pairs"][0]["runs"]["O"]["ledger"][7].__setitem__("fitness", 39)))
        w = self.w.at("S1")                                   # canonical content, other bytes: the S0 pin holds
        (w.root / bman.QUAL_PLAN_REL).write_text((w.root / bman.QUAL_PLAN_REL).read_text() + "\n")
        self.refused("the manifest's qualification_plan is not what the tree gives now: qualification_plan.sha256", w.verify)

    def test_the_experiment_the_prediction_and_the_stop_rule(self):
        self.both(f"experiment: the gate report {bman.GATE_REL} is absent", lambda root: (root / bman.GATE_REL).unlink())
        self.both("experiment: the gate: ", self.edit(bman.GATE_REL, lambda d: d["results"]["F1"].__setitem__("b_star", 800)))
        self.both(f"prediction: {bman.PREDICTION_REL} is absent", lambda root: (root / bman.PREDICTION_REL).unlink())
        self.both("is not the canonical prediction: pairs[2].runs.O.ledger[17].fitness",
                  self.edit(bman.PREDICTION_REL, lambda d: d["pairs"][2]["runs"]["O"]["ledger"][17].__setitem__("fitness", 39)))
        with mock.patch.object(pl, "stop_rule_findings", lambda prediction: ["predicted_primary: p = 0.109 > alpha 0.05 — the line stops"]):
            self.both("prediction: the preflight's stop rule no longer passes", lambda root: None)
        for block, key, bad in (("experiment", "budget_per_arm", 600), ("experiment", "pairs", 9), ("experiment", "calibration_margin", 0.9),
                                ("seeds", "master_seed", 1), ("map", "canonical_json_sha256", "0" * 64), ("instrument", "psoracle_commit", "f" * 40),
                                ("audit", "policy", "sampled"), ("universe", "sha256", "0" * 64)):
            with self.subTest(block=block, key=key):
                self.refused(f"the manifest's {block} is not what the tree gives now: {block}.{key}", self.w.verify,
                             self.mutated("S1", lambda m, b=block, k=key, v=bad: m[b].__setitem__(k, v)))
        self.refused("seeds.pairs[3][1]", self.w.verify, self.mutated("S1", lambda m: m["seeds"]["pairs"][3].__setitem__(1, 7)))

    def test_init_requires_the_committed_plan_to_be_the_rate_less_one(self):
        w = self.w.at("pre")
        pl.write(w.root / "evidence/b3", pl.build_plan(STUB_RATE, w.root / bman.GATE_REL), w.prediction)
        self.cli_refused("init: the committed plan is not the canonical rate-less plan: plan session_split.", "init")
        w = self.w.at("pre")
        (w.root / bman.PLAN_REL).unlink()
        self.cli_refused(f"{bman.PLAN_REL} is absent", "init")


class InitNoClobber(Base):
    def test_init_never_overwrites(self):
        for stage in ("S0", "S3"):
            self.w.at(stage)
            self.cli_refused("exists; a manifest is never overwritten (no-clobber)", "init")
            self.assertEqual(self.w.calls, [], "refused before anything was verified")
        w = self.w.at("pre")
        w.manifest_path.symlink_to(w.root / "elsewhere.json")
        text = w.cli("init", expect=2)
        self.assertIn("never overwritten (no-clobber)", text)
        self.assertFalse((w.root / "elsewhere.json").exists(), "nothing was written through the symlink")

    def test_publishing_is_no_clobber_at_the_link_itself(self):
        w = self.w.at("pre")
        target = w.root / "manifests/race.json"
        bman.publish_new(target, "first\n")
        with mock.patch.object(Path, "exists", lambda self_: False), mock.patch.object(Path, "is_symlink", lambda self_: False):
            self.refused("appeared; a manifest is never overwritten", bman.publish_new, target, "second\n")     # the pre-check blinded: os.link still refuses
        self.assertEqual(target.read_text(), "first\n")
        self.assertEqual([p.name for p in target.parent.iterdir() if p.name.endswith(".part")], [])

    def test_a_fresh_init_is_s0_and_byte_stable(self):
        w = self.w.at("pre")
        w.cli("init")
        self.assertEqual(w.manifest_path.read_bytes(), (w.snap / "S0" / bman.MANIFEST_REL).read_bytes())


class StagesAndTransitions(Base):
    def docs(self) -> dict:
        return {s: json.loads((self.w.snap / s / bman.MANIFEST_REL).read_text()) for s in bman.STAGES}

    def test_every_pairing_but_the_three_steps_is_refused(self):
        docs = self.docs()
        legal = set(bman.TRANSITIONS)
        self.assertEqual(legal, {("S0", "S1"), ("S1", "S2"), ("S2", "S3")})
        seen = 0
        for a in bman.STAGES:
            for b in bman.STAGES:
                if (a, b) in legal:
                    continue
                seen += 1
                with self.subTest(pair=(a, b)):
                    self.refused(f"transition: {a} -> {b} is not a lifecycle step", bman.check_transition, docs[a], docs[b])
        self.assertEqual(seen, 13)

    def test_a_field_the_step_does_not_license_is_named(self):
        docs = self.docs()
        cases = (("S0", "S1", lambda m: m["seeds"].__setitem__("master_seed", 1), "seeds.master_seed"),
                 ("S0", "S1", lambda m: m["image"].__setitem__("sha256", "0" * 64), "image.sha256"),
                 ("S0", "S1", lambda m: m["qualification_plan"].__setitem__("sha256", "0" * 64), "qualification_plan.sha256"),
                 ("S0", "S1", lambda m: m["prereg"].__setitem__("path", "docs/other.md"), "prereg.path"),
                 ("S0", "S1", lambda m: m["image"].__setitem__("reviewed", True), "image.reviewed: unexpected"),
                 ("S1", "S2", lambda m: m["board"].__setitem__("boardid", "08EB"), "board.boardid"),
                 ("S1", "S2", lambda m: m["experiment"].__setitem__("budget_per_arm", 600), "experiment.budget_per_arm"),
                 ("S1", "S2", lambda m: m["qualification_plan"]["planning_bound"].__setitem__("rate_per_hour", 1.0), "qualification_plan.planning_bound.rate_per_hour"),
                 ("S2", "S3", lambda m: m["calibration"].__setitem__("rate_per_hour", 9999.0), "calibration.rate_per_hour"),
                 ("S2", "S3", lambda m: m["qualification"].__setitem__("outcome", "HOLD"), "qualification.outcome"),
                 ("S2", "S3", lambda m: m["frozen_inputs"].__setitem__(bman.B2_MANIFEST_REL, "0" * 64), "frozen_inputs"))
        for a, b, mutate, named in cases:
            with self.subTest(step=(a, b), named=named):
                after = copy.deepcopy(docs[b])
                mutate(after)
                self.refused(named, bman.check_transition, docs[a], after)
        after = copy.deepcopy(docs["S1"])
        after["approved_by"] = "someone"
        self.refused("unexpected ['approved_by']", bman.check_transition, docs["S0"], after)

    def test_every_illegal_pairing_of_stage_fields_is_refused_by_verify(self):
        cases = (("S0", lambda m: m["image"].__setitem__("board_ready", True), "S0: a preregistration digest or a board_ready image on an unfrozen manifest"),
                 ("S0", lambda m: m["prereg"].__setitem__("sha256", "0" * 64), "S0: a preregistration digest or a board_ready image"),
                 ("S0", lambda m: m.__setitem__("qualified", True), "S0: a qualification, a qualified flag or a calibration"),
                 ("S0", lambda m: m.__setitem__("plan", {"path": "x"}), "S0: a plan on an unfrozen manifest"),
                 ("S1", lambda m: m["image"].__setitem__("board_ready", False), "S1: frozen without a preregistration digest or without board_ready"),
                 ("S1", lambda m: m["prereg"].__setitem__("sha256", None), "S1: frozen without a preregistration digest"),
                 ("S1", lambda m: m.__setitem__("qualified", True), "S1: qualified / calibration without a qualification record"),
                 ("S1", lambda m: m.__setitem__("calibration", {"rate_per_hour": 4000.0}), "S1: qualified / calibration without a qualification record"),
                 ("S1", lambda m: m.__setitem__("plan", {"path": "x"}), "S1: a plan on a manifest that is not qualified"),
                 ("S2", lambda m: m.__setitem__("qualified", False), "S2: a qualification record without the qualified flag"),
                 ("S2", lambda m: m.__setitem__("calibration", None), "S2: a qualification record without the qualified flag and its calibration"),
                 ("S3", lambda m: m.__setitem__("qualification", None), "S1: qualified / calibration without a qualification record"),
                 ("S3", lambda m: m["prereg"].__setitem__("frozen", False), "S0: a preregistration digest"),
                 ("S1", lambda m: m["prereg"].__setitem__("frozen", "yes"), "carries no boolean frozen"),
                 ("S1", lambda m: m.__setitem__("qualified", 0), "qualified flag is not a boolean"),
                 ("S1", lambda m: m.pop("rulings_binding"), "missing ['rulings_binding']"),
                 ("S1", lambda m: m.__setitem__("schema_version", "9.9.9"), "schema_version '9.9.9'"))
        for stage, mutate, needle in cases:
            with self.subTest(stage=stage, needle=needle):
                self.refused(needle, self.w.verify, self.mutated(stage, mutate))

    def test_a_status_or_a_history_of_another_stage_is_refused(self):
        for stage in bman.STAGES:
            for other in bman.STAGES:
                if other != stage:
                    with self.subTest(stage=stage, status_of=other):
                        self.refused(f"{stage}: the manifest's status is", self.w.verify, self.mutated(stage, lambda m, o=other: m.__setitem__("status", bman.STATUS[o])))
                        self.refused(f"{stage}: the manifest's history is not exactly", self.w.verify,
                                     self.mutated(stage, lambda m, o=other: m.__setitem__("history", [{"transition": t} for t in bman.HISTORY[o]])))
            self.refused(f"{stage}: the manifest's status is", self.w.verify, self.mutated(stage, lambda m: m.__setitem__("status", "READY FOR THE BOARD")))
        self.refused("history: the S1 entry's preregistration digest", self.w.verify, self.mutated("S1", lambda m: m["history"][0].__setitem__("prereg_sha256", "0" * 64)))
        self.refused("history: the S2 entry is not the qualification record's", self.w.verify, self.mutated("S2", lambda m: m["history"][1].__setitem__("rate_per_hour", 1.0)))
        self.refused("history: the S3 entry's plan digest", self.w.verify, self.mutated("S3", lambda m: m["history"][2].__setitem__("plan_sha256", "0" * 64)))

    def test_a_command_from_the_wrong_stage_is_refused_and_keeps_the_bytes(self):
        ev = str(self.w.evidence)
        for stage, argv, needle in (("S1", ("freeze", "--prereg-sha256", "PREREG"), "freeze: the manifest is at S1, this transition starts from S0"),
                                    ("S3", ("freeze", "--prereg-sha256", "PREREG"), "freeze: the manifest is at S3"),
                                    ("S0", ("qualify", "--evidence-dir", ev), "qualify: the manifest is at S0, this transition starts from S1"),
                                    ("S2", ("qualify", "--evidence-dir", ev), "qualify: the manifest is at S2"),
                                    ("S3", ("qualify", "--evidence-dir", ev), "qualify: the manifest is at S3"),
                                    ("S0", ("plan", "--plan", "PLAN"), "plan: the manifest is at S0, this transition starts from S2"),
                                    ("S1", ("plan", "--plan", "PLAN"), "plan: the manifest is at S1"),
                                    ("S3", ("plan", "--plan", "PLAN"), "plan: the manifest is at S3")):
            with self.subTest(stage=stage, command=argv[0]):
                w = self.w.at(stage)
                argv = tuple({"PREREG": sha(w.root / bman.PREREG_REL), "PLAN": str(w.root / bman.PLAN_REL)}.get(x, x) for x in argv)
                self.cli_refused(needle, *argv)

    def test_a_failed_transition_keeps_the_original_bytes(self):
        self.w.at("S0")
        self.cli_refused("freeze: the given preregistration sha256 is not the hash of the preregistration file on disk", "freeze", "--prereg-sha256", "0" * 64)
        self.cli_refused("freeze needs --prereg-sha256", "freeze")
        self.w.at("S1")
        self.cli_refused("qualify needs the B3Q evidence directory", "qualify")
        self.cli_refused("evidence file run_log.json is absent", "qualify", "--evidence-dir", str(self.w.root / "nowhere"))
        self.w.at("S2")
        self.cli_refused("plan needs the plan file", "plan")
        self.w.at("pre")
        self.cli_refused("no B3 manifest at", "verify")
        self.w.manifest_path.write_text("{not json")
        self.cli_refused("the B3 manifest is not readable JSON", "verify")

    def test_the_replace_is_atomic_and_only_over_the_bytes_the_transition_was_computed_from(self):
        w = self.w.at("S1")
        original = w.manifest_path.read_bytes()
        self.refused("changed while the transition was being verified; nothing was written", bman.replace_atomic, w.manifest_path, b"other bytes", "new\n")
        self.assertEqual(w.manifest_path.read_bytes(), original)
        self.assertEqual(self.strays(), [])
        with mock.patch.object(bman, "_rename_exchange", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                bman.replace_atomic(w.manifest_path, original, "new\n")
        self.assertEqual(w.manifest_path.read_bytes(), original)
        self.assertEqual(self.strays(), [])
        bman.replace_atomic(w.manifest_path, original, "new\n")                   # and the positive control: the swap stands
        self.assertEqual(w.manifest_path.read_bytes(), b"new\n")
        self.assertEqual(self.strays(), [])

    def strays(self) -> list[str]:
        return sorted(p.name for p in self.w.manifest_path.parent.iterdir() if ".part" in p.name or ".conflict" in p.name or p.name.endswith(".lock"))

    def racing(self, *intrusions):
        """`_rename_exchange` with a competitor: before the n-th exchange — i.e. AFTER the last comparison the
        function made and before it publishes — `intrusions[n]` writes the manifest."""
        real, calls = bman._rename_exchange, []

        def exchange(a, b):
            if len(calls) < len(intrusions) and intrusions[len(calls)] is not None:
                intrusions[len(calls)](Path(b))
            calls.append(1)
            real(a, b)
        return mock.patch.object(bman, "_rename_exchange", exchange)

    def test_the_replace_is_a_compare_and_swap_a_competitor_after_the_last_comparison_wins(self):
        """The owner's P2 on 8ba72c4: the target changed between the comparison and the publish and was
        overwritten. Now: refused, and the competitor's bytes are the manifest — whether it rewrote the file
        in place or replaced it with another inode."""
        def in_place(p):
            p.write_bytes(b"intruder")

        def new_inode(p):
            other = p.with_name("intruder.tmp")
            other.write_bytes(b"intruder")
            os.replace(other, p)
        for how in (in_place, new_inode):
            with self.subTest(how=how.__name__):
                w = self.w.at("S1")
                original = w.manifest_path.read_bytes()
                with self.racing(how):
                    self.refused("changed after the last comparison and before the publish; the transition was withdrawn and the competitor's bytes are preserved",
                                 bman.replace_atomic, w.manifest_path, original, "new\n")
                self.assertEqual(w.manifest_path.read_bytes(), b"intruder")
                self.assertEqual(self.strays(), [])

    def test_a_second_competitor_between_the_exchanges_loses_nothing_either(self):
        w = self.w.at("S1")
        original = w.manifest_path.read_bytes()
        with self.racing(lambda p: p.write_bytes(b"first"), lambda p: p.write_bytes(b"second")):
            msg = self.refused("changed twice while the transition was being published", bman.replace_atomic, w.manifest_path, original, "new\n")
        self.assertEqual(w.manifest_path.read_bytes(), b"first")
        kept = [p for p in w.manifest_path.parent.iterdir() if ".conflict." in p.name]
        self.assertEqual([p.read_bytes() for p in kept], [b"second"])
        self.assertIn(str(kept[0]), msg)
        self.assertEqual([n for n in self.strays() if ".part" in n], [])

    def test_a_racing_competitor_defeats_the_command_line_transition_too(self):
        w = self.w.at("S0")
        with self.racing(lambda p: p.write_bytes(b"intruder")):
            text = w.cli("freeze", "--prereg-sha256", sha(w.root / bman.PREREG_REL), expect=2)
        self.assertIn("REFUSED:", text)
        self.assertIn("the competitor's bytes are preserved", text)
        self.assertEqual(w.manifest_path.read_bytes(), b"intruder")
        self.assertEqual(self.strays(), [])

    def test_transitions_are_serialised_by_a_lock_that_leaves_no_file(self):
        import fcntl
        w = self.w.at("S1")
        original = w.manifest_path.read_bytes()
        fd = os.open(w.manifest_path.parent, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            self.refused("another b3_manifest transition holds the directory lock; nothing was written", bman.replace_atomic, w.manifest_path, original, "new\n")
        finally:
            os.close(fd)
        self.assertEqual(w.manifest_path.read_bytes(), original)
        self.assertEqual(self.strays(), [])
        (w.root / "gone.json").write_bytes(b"x")
        with self.racing(lambda p: p.unlink()):
            self.refused("vanished while the transition was being verified", bman.replace_atomic, w.root / "gone.json", b"x", "new\n")

    def test_the_candidate_is_verified_before_the_file_is_replaced(self):
        """The write is the LAST act: with the replace spied, a transition whose candidate does not verify
        never reaches it."""
        w = self.w.at("S1")
        make_b3q_evidence(w, w.evidence, rate=1300.0)             # INFEASIBLE under the split rule at the margin
        with mock.patch.object(bman, "replace_atomic") as spy:
            self.cli_refused("calibration: the measured rate 1300.0 /h is INFEASIBLE", "qualify", "--evidence-dir", str(w.evidence))
        spy.assert_not_called()


class Qualification(Base):
    def s2(self) -> World:
        return self.w.at("S2")

    def test_each_of_the_twelve_files_absent_and_drifted(self):
        files = bman.qualification_evidence_files()
        self.assertEqual(len(files), 12)
        self.assertEqual(set(files), set(b1q.EVIDENCE_FILES) | {"runner_session.json"})
        for name in files:
            for how in ("absent", "drift"):
                with self.subTest(file=name, how=how):
                    w = self.s2()
                    p = w.evidence / name
                    if how == "absent":
                        p.unlink()
                        self.refused(f"evidence file {name} is absent", w.verify)
                    else:
                        p.write_bytes(p.read_bytes() + b" ")
                        msg = self.refused("", w.verify)
                        self.assertTrue(any(s in msg for s in ("S2: the record's files is not what the evidence gives", "evidence seal:", name)), msg)
                    self.assertNotIn("readjudicate", w.calls, "evidence that is not the pinned evidence is not re-adjudicated into a pass")

    def test_the_export_seal_is_still_held(self):
        w = self.s2()
        doc = json.loads((w.evidence / "exports.json").read_text())
        doc["complete"] = False
        (w.evidence / "exports.json").write_text(json.dumps(doc))
        self.refused("evidence seal: evidence exports incomplete", w.verify)

    def test_the_record_is_rebuilt_from_the_evidence_not_taken_from_the_manifest(self):
        for key, bad, needle in (("outcome", "HOLD", "the record's outcome"), ("measured_rate_per_hour", 12000.0, "the record's measured_rate_per_hour"),
                                 ("measured_rate_per_hour", 4000, "the record's measured_rate_per_hour"),
                                 ("audit_policy", "sampled", "the record's audit_policy"), ("schema_version", "0.9.0", "not a B3Q image qualification"),
                                 ("session", "B3", "not a B3Q image qualification")):
            with self.subTest(key=key, bad=bad):
                self.refused(needle, self.w.verify, self.mutated("S2", lambda m, k=key, v=bad: m["qualification"].__setitem__(k, v)))
        self.refused("the record's qualification_block", self.w.verify, self.mutated("S2", lambda m: m["qualification"]["qualification_block"].__setitem__("fitness_values", 122)))
        self.refused("the record's binding is not what the evidence gives", self.w.verify,
                     self.mutated("S2", lambda m: m["qualification"]["binding"].__setitem__("image_sha256", "0" * 64)))
        self.refused("file set is not exactly", self.w.verify, self.mutated("S2", lambda m: m["qualification"]["files"].pop("runner_session.json")))
        self.refused("does not carry exactly", self.w.verify, self.mutated("S2", lambda m: m["qualification"].__setitem__("summary", "PASS")))
        self.refused("binding does not carry exactly", self.w.verify, self.mutated("S2", lambda m: m["qualification"]["binding"].pop("qualification_plan_sha256")))
        self.refused("evidence directory evidence/b3/elsewhere is absent", self.w.verify,
                     self.mutated("S2", lambda m: m["qualification"].__setitem__("evidence_dir", "evidence/b3/elsewhere")))

    def test_a_rate_changed_consistently_everywhere_in_the_manifest_is_still_not_the_evidences(self):
        def everywhere(m):
            m["qualification"]["measured_rate_per_hour"] = 12000.0
            m["calibration"].update(rate_per_hour=12000.0, rate_for_split=12000.0 * 0.85, sessions=2, pairs_per_session_max=4)
            m["history"][1]["rate_per_hour"] = 12000.0
        self.refused("S2: the record's measured_rate_per_hour is not what the evidence gives", self.w.verify, self.mutated("S2", everywhere))

    def test_the_calibration_is_recomputed_key_by_key(self):
        for key, bad in (("rate_per_hour", 4001.0), ("margin", 0.9), ("margin", 1), ("rate_for_split", 4000.0), ("audit_policy", "sampled"),
                         ("sessions", 1), ("pairs_per_session_max", 8), ("source", "B2's calibration")):
            with self.subTest(key=key, bad=bad):
                self.refused(f"S2: the calibration is not the one the evidence gives under the frozen margin and split rule: calibration.{key}",
                             self.w.verify, self.mutated("S2", lambda m, k=key, v=bad: m["calibration"].__setitem__(k, v)))
        self.refused("calibration.verified: unexpected", self.w.verify, self.mutated("S2", lambda m: m["calibration"].__setitem__("verified", True)))
        self.refused("calibration.margin: absent", self.w.verify, self.mutated("S2", lambda m: m["calibration"].pop("margin")))

    def test_the_re_adjudication_must_agree_with_the_evidence_on_everything(self):
        w = self.s2()
        good = rn.readjudicator(w.manifest(), ports=w.ports(), root=w.root)(w.evidence, json.loads((w.evidence / bman.MANIFEST_AT_RUN).read_text()))
        self.assertEqual(good["outcome"], "PASS")
        block = dict(good["qualification"])
        for over, needle in (({"outcome": "HOLD: the ledger diverged"}, "re-adjudicates to 'HOLD: the ledger diverged', not PASS"),
                             ({"outcome": "KILL: a fitness value"}, "re-adjudicates to 'KILL: a fitness value'"),
                             ({"measured_rate_per_hour": 3999.0}, "the re-adjudication's measured_rate_per_hour (3999.0) disagrees"),
                             ({"measured_rate_per_hour": 4000}, "the re-adjudication's measured_rate_per_hour (4000) disagrees"),
                             ({"audit_policy": "sampled"}, "the re-adjudication's audit_policy (sampled) disagrees"),
                             ({"audit_policy": None}, "the re-adjudication's audit_policy (None) disagrees"),
                             ({"qualification": {**block, "ledger_entries": 39}}, "the re-adjudication's qualification"),
                             ({"qualification": {**block, "fitness_sequence_sha256": "0" * 64}}, "the re-adjudication's qualification"),
                             ({"qualification": None}, "the re-adjudication's qualification (None) disagrees")):
            with self.subTest(over=over):
                self.refused("S2: " , w.verify, readjudicate=lambda ev, m_run, o=over: {**good, **o})
                self.refused(needle, w.verify, readjudicate=lambda ev, m_run, o=over: {**good, **o})
        self.refused("the re-adjudication returned NoneType", w.verify, readjudicate=lambda ev, m_run: None)
        with self.assertRaises(ZeroDivisionError):
            w.verify(readjudicate=lambda ev, m_run: 1 / 0)

    def test_the_rate_the_instrument_now_measures_must_be_the_pinned_one(self):
        """The three must agree: the evidence's adjudication, the re-adjudication, the calibration."""
        w = self.s2()
        other = rn.readjudicator(w.manifest(), ports=w.ports(rate=3500.0), root=w.root)
        self.refused("runner_session.json's measured_rate_per_hour is 4000.0, this session's is 3500.0", w.verify, readjudicate=other)   # the verdict it recomputes is what the record is held to
        policy = rn.readjudicator(w.manifest(), ports=w.ports(policy="sampled"), root=w.root)
        self.refused("the re-adjudication's audit_policy (sampled) disagrees", w.verify, readjudicate=policy)

    def test_a_forged_pass_over_a_bad_log_is_caught_by_the_re_adjudication(self):
        """adjudication.json, summary.json and runner_session.json copied from a PASSING session over a run log
        whose ledger was tampered: every stored declaration says PASS, the seal is intact — only the
        re-adjudication, from the pinned B3Q plan and prediction, sees it."""
        w = self.w.at("S1")
        good, bad = w.root / "evidence/b3/good", w.root / "evidence/b3/bad"
        make_b3q_evidence(w, good)

        def tamper(log):
            rec = next(r for r in log["loop_records"] if isinstance(r.get("search"), dict) and "ledger" in r["search"])
            rec["search"]["ledger"]["map_version_after"] += 1
        summary = make_b3q_evidence(w, bad, tamper=tamper)
        self.assertNotEqual(summary["outcome"], "PASS")
        self.cli_refused("the stored B3Q adjudication is", "qualify", "--evidence-dir", str(bad))
        for name in ("adjudication.json", "summary.json", "runner_session.json"):
            shutil.copy(good / name, bad / name)
        self.cli_refused("S2: the pinned B3Q evidence re-adjudicates to", "qualify", "--evidence-dir", str(bad))
        self.assertIn("readjudicate", w.calls)
        w.cli("qualify", "--evidence-dir", str(good))
        self.assertEqual(w.verify()["stage"], "S2")

    def test_none_is_the_production_re_adjudicator_never_a_skip(self):
        """No hook: `b3_runner.readjudicator` with the PRODUCTION ports — over modelled evidence the real
        instrument layer cannot pass, so the manifest is refused; what matters is that it RAN."""
        w = self.s2()
        with mock.patch.object(rn, "readjudicator", wraps=rn.readjudicator) as spy:
            self.refused("S2: the pinned B3Q evidence re-adjudicates to", w.verify, readjudicate=None)
        self.assertEqual(spy.call_count, 1)
        self.assertIsNone(spy.call_args.kwargs.get("ports"))
        self.assertEqual(spy.call_args.kwargs.get("root"), w.root)
        self.assertNotIn("readjudicate", w.calls)

    def test_the_final_records_must_close_the_evidence(self):
        def edit(name, mutate):
            w = self.w.at("S1")
            make_b3q_evidence(w, w.evidence)
            doc = json.loads((w.evidence / name).read_text())
            mutate(doc)
            (w.evidence / name).write_text(json.dumps(doc))
            return w
        for name, mutate, needle in (("summary.json", lambda d: d.__setitem__("outcome", "HOLD"), "summary.json's outcome 'HOLD'"),
                                     ("summary.json", lambda d: d.__setitem__("token", "another"), "summary.json's token is not the session's"),
                                     ("summary.json", lambda d: d["ruling"].__setitem__("boardid", "08EB"), "recorded ruling is not the archived whole-of-run ruling"),
                                     ("summary.json", lambda d: d.__setitem__("provisioning_ruling_sha256", "0" * 64), "provisioning_ruling_sha256 is not"),
                                     ("runner_session.json", lambda d: d.__setitem__("pair_first", 0.0), "runner_session.json's pair_first 0.0 is not an integer"),
                                     ("runner_session.json", lambda d: d.__setitem__("pair_count", True), "runner_session.json's pair_count True is not an integer"),
                                     ("runner_session.json", lambda d: d.__setitem__("pair_count", 2), "runner_session.json's pair_count is 2, this session's is 1"),
                                     ("runner_session.json", lambda d: d.__setitem__("master_seed", 123), "runner_session.json's master_seed is 123, this session's is"),
                                     ("runner_session.json", lambda d: d.__setitem__("expected_records", 999), "runner_session.json's expected_records is 999, this session's is 125"),
                                     ("runner_session.json", lambda d: d.__setitem__("expected_records", 125.0), "runner_session.json's expected_records 125.0 is not an integer"),
                                     ("runner_session.json", lambda d: d.__setitem__("reached", "claim"), "runner_session.json's reached is 'claim', this session's is 'session'"),
                                     ("runner_session.json", lambda d: d.__setitem__("tool", "foreign/tool"), "runner_session.json's tool is 'foreign/tool'"),
                                     ("runner_session.json", lambda d: d.__setitem__("profile_stage", "S3"), "runner_session.json's profile_stage is 'S3'"),
                                     ("runner_session.json", lambda d: d.__setitem__("outcome", "HOLD: x"), "runner_session.json's outcome is 'HOLD: x'"),
                                     ("runner_session.json", lambda d: d.__setitem__("measured_rate_per_hour", 4000), "runner_session.json's measured_rate_per_hour is 4000, this session's is 4000.0"),
                                     ("runner_session.json", lambda d: d.__setitem__("note", "extra"), "runner_session.json's keys are not the schema's (missing [], unexpected ['note'])"),
                                     ("runner_session.json", lambda d: d.pop("ruling_pair"), "runner_session.json's keys are not the schema's (missing ['ruling_pair']"),
                                     ("runner_session.json", lambda d: d.__setitem__("ruling_pair", "may be retried"), "runner_session.json's ruling_pair is not the runner's statement"),
                                     ("runner_session.json", lambda d: d.__setitem__("at", "yesterday"), "runner_session.json's at 'yesterday' is not a UTC timestamp"),
                                     ("runner_session.json", lambda d: d.pop("transport"), "runner_session.json carries no transport block"),
                                     ("runner_session.json", lambda d: d["transport"].__setitem__("timeline_error", "OSError"), "runner_session.json's transport keys are not the schema's"),
                                     ("runner_session.json", lambda d: d["transport"].__setitem__("resend_budget", d["transport"]["resend_budget"] + 1), "runner_session.json's transport.resend_budget is"),
                                     ("runner_session.json", lambda d: d["transport"].__setitem__("crc_dropped", None), "runner_session.json's transport.crc_dropped None is not a non-negative integer"),
                                     ("runner_session.json", lambda d: d["transport"].__setitem__("bad_frames", 10 ** 6), "runner_session.json's transport.bad_frames 1000000 exceeds its bad_frame_budget"),
                                     ("runner_session.json", lambda d: d["transport"].__setitem__("crc_budget", d["transport"]["crc_budget"] + 5),
                                      "re-adjudicates to \"HOLD: runner_session.json's transport.crc_budget is"),
                                     ("runner_session.json", lambda d: d["transport"].__setitem__("expected_frames_total", 1),
                                      "re-adjudicates to \"HOLD: runner_session.json's transport.expected_frames_total is 1"),
                                     ("runner_session.json", lambda d: d.__setitem__("cause", "HOLD"), "runner_session.json's cause is 'HOLD'"),
                                     ("runner_session.json", lambda d: d.__setitem__("session", "B3"), "runner_session.json's session is 'B3'"),
                                     ("runner_session.json", lambda d: d.__setitem__("measured_rate_per_hour", 1.0), "runner_session.json's measured_rate_per_hour"),
                                     ("runner_session.json", lambda d: d.__setitem__("finalise_errors", ["transport close: OSError"]), "records finalise errors"),
                                     ("runner_session.json", lambda d: d["transport"].__setitem__("transport_disposition", "another disposition"),
                                      "runner_session.json's transport.transport_disposition is 'another disposition'")):
            with self.subTest(file=name, needle=needle):
                edit(name, mutate)
                text = self.cli_refused(needle, "qualify", "--evidence-dir", str(self.w.evidence))
                # WHICH layer refused: the manifest's own binding (before any re-adjudication), except for the frame / CRC
                # budgets, which need the instrument's schedule and are the re-adjudicator's
                if needle.startswith("re-adjudicates"):
                    self.assertIn("readjudicate", self.w.calls)
                else:
                    self.assertIn("S2: the session's final records do not close this evidence", text)
                    self.assertNotIn("readjudicate", self.w.calls)

    def test_the_owners_probe_every_field_at_once_is_refused_and_nothing_is_pinned(self):
        """8ba72c4 accepted this record and pinned its hash into an S2 qualification."""
        w = self.w.at("S1")
        make_b3q_evidence(w, w.evidence)
        doc = json.loads((w.evidence / "runner_session.json").read_text())
        doc.update(pair_first=0.0, master_seed=123, expected_records=999, reached="claim", tool="foreign/tool")
        (w.evidence / "runner_session.json").write_text(json.dumps(doc))
        before = w.manifest_path.read_bytes()
        text = w.cli("qualify", "--evidence-dir", str(w.evidence), expect=2)
        for needle in ("pair_first 0.0 is not an integer", "master_seed is 123", "expected_records is 999"):
            self.assertIn(needle, text)
        self.assertEqual(w.manifest_path.read_bytes(), before)
        self.assertEqual(w.verify()["stage"], "S1")

    def test_the_adjudication_must_carry_b3qs_own_block(self):
        def edit(mutate):
            w = self.w.at("S1")
            make_b3q_evidence(w, w.evidence)
            doc = json.loads((w.evidence / "adjudication.json").read_text())
            mutate(doc)
            (w.evidence / "adjudication.json").write_text(json.dumps(doc))
        for mutate, needle in ((lambda d: d.pop("qualification"), "adjudication.json lacks qualification"),
                               (lambda d: d["qualification"].pop("baselines"), "the qualification block does not carry exactly"),
                               (lambda d: d["qualification"].__setitem__("fitness_values", 120), "the evidence's qualification block is not the pinned B3Q experiment's"),
                               (lambda d: d["qualification"].__setitem__("fitness_sequence_sha256", "0" * 64), "qualification block is not the pinned B3Q experiment's"),
                               (lambda d: d.__setitem__("scope", "run"), "at scope 'run'"),
                               (lambda d: d.__setitem__("measured_rate_per_hour", float("inf")), "the measured rate is not a finite positive number"),
                               (lambda d: d.__setitem__("measured_rate_per_hour", True), "the measured rate is not a finite positive number")):
            with self.subTest(needle=needle):
                edit(mutate)
                self.cli_refused(needle, "qualify", "--evidence-dir", str(self.w.evidence))

    def test_the_session_must_have_run_under_this_s1_manifest(self):
        w = self.w.at("S1")
        original = w.manifest_path.read_bytes()
        m = w.manifest()
        m["audit"]["note"] = "another manifest, same image"
        w.write_manifest(m)
        make_b3q_evidence(w, w.evidence)
        w.manifest_path.write_bytes(original)
        self.cli_refused("the current manifest differs from manifest_at_run in more than", "qualify", "--evidence-dir", str(w.evidence))
        w = self.w.at("S1")
        make_b3q_evidence(w, w.evidence)
        at_run = json.loads((w.evidence / bman.MANIFEST_AT_RUN).read_text())
        (w.evidence / bman.MANIFEST_AT_RUN).write_text(json.dumps(at_run))                    # the same document, other bytes
        self.cli_refused("is not the manifest file's canonical bytes", "qualify", "--evidence-dir", str(w.evidence))
        (w.evidence / bman.MANIFEST_AT_RUN).write_bytes((w.snap / "S0" / bman.MANIFEST_REL).read_bytes())
        self.cli_refused("manifest_at_run.json is not an S1 b3_manifest: it is at S0", "qualify", "--evidence-dir", str(w.evidence))


class PlanStage(Base):
    def test_the_pinned_plan_and_prediction_bytes(self):
        w = self.w.at("S3")
        p = w.root / bman.PLAN_REL
        doc = json.loads(p.read_text())
        doc["generated_utc"] = "1970-01-01T00:00:00Z"
        p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
        self.refused("S3: the pinned plan file is absent or changed", w.verify)
        w = self.w.at("S3")
        (w.root / bman.PLAN_REL).unlink()
        self.refused("S3: the pinned plan file is absent or changed", w.verify)
        for key, needle in (("sha256", "S3: the pinned plan file is absent or changed"), ("prediction_sha256", "S3: the pinned prediction file is absent or changed")):
            self.refused(needle, self.w.verify, self.mutated("S3", lambda m, k=key: m["plan"].__setitem__(k, "0" * 64)))
        self.refused("S3: the plan pin does not carry exactly", self.w.verify, self.mutated("S3", lambda m: m["plan"].pop("sessions")))

    def test_the_pins_own_summary_one_field_at_a_time(self):
        for key in ("sessions", "total_records"):
            with self.subTest(key=key):
                self.refused("S3: the manifest's plan summary (sessions / total_records) is not the plan's", self.w.verify,
                             self.mutated("S3", lambda m, k=key: m["plan"].__setitem__(k, m["plan"][k] + 1)))

    def test_plan_findings_name_every_drift_including_one_ledger_entry(self):
        w = self.w.at("S2")
        m = w.manifest()
        gate = w.root / bman.GATE_REL
        d = w.root / "evidence/b3/candidate"
        pl.write(d, pl.build_plan(w.rate, gate), w.prediction)
        self.assertEqual(bman.plan_findings(m, d / "plan.json", w.root), [])

        def with_plan(mutate) -> list[str]:
            doc = json.loads((d / "plan.json").read_text())
            mutate(doc)
            (d / "plan.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
            try:
                return bman.plan_findings(m, d / "plan.json", w.root)
            finally:
                pl.write(d, pl.build_plan(w.rate, gate), w.prediction)
        self.assertEqual(with_plan(lambda p: p.__setitem__("generated_utc", "1970-01-01T00:00:00Z")), [], "the one non-operational key")
        self.assertTrue(any(f.startswith("plan session_split.sessions[1].deadline_s") for f in
                            with_plan(lambda p: p["session_split"]["sessions"][1].__setitem__("deadline_s", 1.0))))
        self.assertTrue(any(f.startswith("plan arm_order.per_pair[3]") for f in with_plan(lambda p: p["arm_order"]["per_pair"].__setitem__(3, "RFO"))))
        self.assertIn("the plan's prediction digest is not the sidecar's hash", with_plan(lambda p: p.__setitem__("prediction_sha256", "0" * 64)))
        pred = json.loads((d / "prediction.json").read_text())
        pred["pairs"][5]["runs"]["O"]["ledger"][123]["map_version_after"] += 1
        (d / "prediction.json").write_text(json.dumps(pred, indent=1, sort_keys=True) + "\n")
        findings = bman.plan_findings(m, d / "plan.json", w.root)
        self.assertTrue(any(f.startswith("prediction pairs[5].runs.O.ledger[123].map_version_after:") for f in findings), findings[:5])
        self.assertIn("the plan's prediction sidecar is not the preregistered prediction the manifest pinned at S0", findings)
        (d / "prediction.json").unlink()
        self.assertIn("prediction.json is absent beside the plan", bman.plan_findings(m, d / "plan.json", w.root))
        self.assertEqual(bman.plan_findings(m, d / "absent.json", w.root), [f"plan file {d / 'absent.json'} is absent"])

    def test_the_split_must_be_determined_and_from_this_calibration(self):
        w = self.w.at("S2")
        gate = w.root / bman.GATE_REL
        self.cli_refused("plan session_split.status: 'UNDETERMINED until B3Q measures the all-self-reporting rate', expected 'DETERMINED'", "plan", "--plan", str(w.root / bman.PLAN_REL))      # the committed rate-less plan
        pl.write(w.root / "evidence/b3/other_rate", pl.build_plan(12000.0, gate), w.prediction)
        self.cli_refused("plan: plan session_split", "plan", "--plan", str(w.root / "evidence/b3/other_rate/plan.json"))
        m = w.manifest()
        m["calibration"]["rate_per_hour"] = 1300.0
        self.assertIn("the calibration's split is INFEASIBLE, not DETERMINED", bman.plan_findings(m, w.root / bman.PLAN_REL, w.root))
        m["calibration"]["rate_per_hour"] = float("nan")
        self.assertEqual(bman.plan_findings(m, w.root / bman.PLAN_REL, w.root), ["no calibration with a finite positive rate_per_hour in the manifest: no plan can be derived"])
        m = w.manifest()
        m["calibration"]["rate_for_split"] = 1.0
        pl.write(w.root / "evidence/b3", pl.build_plan(w.rate, gate), w.prediction)
        self.assertIn("the calibration's rate_for_split is not the split rule's", bman.plan_findings(m, w.root / bman.PLAN_REL, w.root))

    def test_a_ledger_entry_drifted_in_the_pinned_sidecar_is_named_at_s3(self):
        w = self.w.at("S3")
        p = w.root / bman.PREDICTION_REL
        pred = json.loads(p.read_text())
        pred["pairs"][7]["runs"]["O"]["ledger"][999]["fitness"] += 1
        p.write_text(json.dumps(pred, indent=1, sort_keys=True) + "\n")
        self.refused("pairs[7].runs.O.ledger[999].fitness", w.verify)


class CommandLine(Base):
    def test_there_is_no_flag_that_skips_anything(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            bman.main(["--help"])
        text = out.getvalue().lower()
        options = sorted({tok.split("=")[0].rstrip(",") for tok in text.split() if tok.startswith("--")})
        self.assertEqual(options, ["--evidence-dir", "--help", "--manifest", "--plan", "--prereg-sha256"])
        for flag in ("--skip-b2", "--allow-missing", "--no-verify", "--force", "--image-evidence"):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
                bman.main(["verify", flag], root=self.w.root, seams=self.w.seams({}))
            self.assertEqual(cm.exception.code, 2)

    def test_the_seams_are_python_only_and_default_to_production(self):
        s = bman.Seams()
        self.assertEqual((s.pins, s.b2, s.b1, s.readjudicate), (None, None, None, None))
        self.assertEqual(sorted(vars(s)), ["b1", "b2", "pins", "readjudicate"])


if __name__ == "__main__":
    unittest.main()
