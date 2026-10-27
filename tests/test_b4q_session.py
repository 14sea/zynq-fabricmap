"""B4Q — the offline end-to-end (host/b4q_e2e.py) in a hermetic root and its fresh-process verification (host/b4q_verify.py):
the valid paths (session open / root / normal P1–P10 / A5 J1–J3 / the A8-style cross / the A2 pairs) verify with empty findings
and the executing side's fitness equals the host's; the negatives are NAMED (an invalid O at P5 with not_realisable and no X,
an invalid O at P1 with arm_auth, no O for a notary refusal / a stopped DMA / an interruption, a refused carrier record for the
unmodelled latch endpoint, the A5 fail data on the persisting fabric); the verifier and the session agree on every scenario;
the A5 / A8 / A2 readings are the contract's. No production registry, seed or board is touched."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b4q_verify as vf  # noqa: E402

_STATE: dict = {}


def setUpModule():
    p = subprocess.run(["bash", str(R / "firmware/b4q/build.sh")], capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(p.stdout + p.stderr)
    root = Path(tempfile.mkdtemp(prefix="b4q_e2e_"))
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_e2e.py"), str(root)], capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        raise AssertionError(p.stdout[-3000:] + p.stderr[-3000:])
    _STATE["root"] = root
    _STATE["summary"] = {s["name"]: s for s in json.loads((root / "e2e_summary.json").read_text())}
    _STATE["verify"] = {}
    for name in _STATE["summary"]:
        q = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(root / name), "--json", str(root / name / "verify.json")], capture_output=True, text=True, timeout=600)
        _STATE["verify"][name] = (q.returncode, json.loads((root / name / "verify.json").read_text()))


class EndToEnd(unittest.TestCase):
    def rep(self, name):
        return _STATE["verify"][name][1]

    def test_every_scenario_verifies_in_agreement_with_the_session(self):
        for name, (rc, rep) in _STATE["verify"].items():
            self.assertTrue(rep["agree"], (name, rep["session"], [(t["dir"], t.get("only_here"), t.get("only_stored")) for t in rep["transactions"] if not t["agrees"]]))
            self.assertEqual(rc, 0, name)
            self.assertEqual([m for m in rep["session"] if m.startswith("A7:")], [], name)          # the bench's declared injected SLVERR (step_in_slverr) is not a finding
            if name != "step_in_slverr":
                self.assertEqual(rep["a7"]["findings"], [], name)
            else:
                self.assertTrue(rep["a7"].get("declared_injections"), name)

    def test_valid_paths_clean(self):
        for name in ("valid", "a5", "a5_persist", "a8_cross"):
            rep = self.rep(name)
            self.assertTrue(rep["clean"], (name, rep["session"], [t["findings"] for t in rep["transactions"]]))
            self.assertEqual(rep["qualification"]["findings"], [], name)
            self.assertIsNone(json.loads((_STATE["root"] / name / "manifest.json").read_text())["halted"], name)
            for t in rep["transactions"]:
                self.assertEqual(t["findings"], [], (name, t["dir"]))
        s = _STATE["summary"]["valid"]
        self.assertEqual([r["x"] for r in s["records"]], ["closed"] * 4)
        self.assertEqual([r["o_status"] for r in s["records"]], ["complete"] * 4)
        self.assertEqual([r["f"] for r in s["records"]], [False, True, True, True])
        for td in sorted((_STATE["root"] / "valid").glob("tx_00[234]")):
            fw = json.loads((td / "firmware_result.json").read_text()); f = json.loads((td / "f.json").read_text())
            self.assertEqual((fw["has_fitness"], fw["fitness"], fw["task_digest"]), (1, f["fitness"], f["task_digest"]), td.name)

    def test_a5_protocol_pass_and_fail_data(self):
        self.assertEqual(_STATE["summary"]["a5"]["a5"], "pass")
        self.assertEqual([r["x"] for r in _STATE["summary"]["a5"]["records"]], ["closed", "closed", "injection_open", "closed", "closed"])
        v = json.loads((_STATE["root"] / "a5/a5_verdict.json").read_text())
        self.assertTrue(v["injection_witness"]["arrived"]); self.assertEqual(v["differing_positions"], [])
        self.assertEqual(_STATE["summary"]["a5_persist"]["a5"], "fail")
        v2 = json.loads((_STATE["root"] / "a5_persist/a5_verdict.json").read_text())
        self.assertTrue(v2["injection_witness"]["arrived"]); self.assertTrue(v2["differing_positions"])
        o3 = json.loads((_STATE["root"] / "a5/tx_004/o.json").read_text())
        self.assertEqual(o3["predecessor"]["kind"], "a5_injection"); self.assertEqual(o3["initial"]["context"], "a5_injection")
        self.assertTrue(o3["init_event"]["parameters"]["pre_init_cleanup"])

    def test_a8_cross_and_a2_rows(self):
        self.assertEqual(_STATE["summary"]["a8_cross"]["a8_AFF"], "both demonstrated")
        self.assertEqual(_STATE["summary"]["a8_cross"]["a8_BFF"], "neither demonstrated")
        cross = json.loads((_STATE["root"] / "a8_cross/a8_cross.json").read_text())
        self.assertEqual(cross["AFF"]["row"], 2); self.assertTrue(all(cross["AFF"]["sr_readings"][c]["reading"] == "restore" for c in ("00", "01", "10", "11")))
        self.assertEqual(_STATE["summary"]["a2_pairs"]["a2"], {"ce_mode": "differs", "storage_kind": "not_assessable"})
        self.assertEqual(self.rep("a8_cross")["qualification"]["a8"][0]["AFF"], {"recomputed": "both demonstrated", "stored": "both demonstrated"})
        self.assertEqual(self.rep("a5_persist")["qualification"]["a5"][0], {"recomputed": "fail", "stored": "fail"})
        rep = self.rep("a2_pairs")
        self.assertTrue(any("bad value" in m for m in rep["transactions"][4]["findings"]))        # the latch endpoint: None cells refused (the emulation's limit)

    def test_negatives_named(self):
        s = _STATE["summary"]
        self.assertEqual((s["not_realisable"]["invalid_phase"], s["not_realisable"]["invalid_code"]), ("P5", "not_realisable"))
        rep = self.rep("not_realisable")
        self.assertIn("O invalid at P5 (not_realisable); no X", rep["transactions"][1]["outcome"])
        self.assertEqual((s["wrong_key"]["o_status"], s["wrong_key"]["o_phase"]), ("invalid", "P1"))
        self.assertIn("arm_auth", self.rep("wrong_key")["transactions"][0]["outcome"])
        for name in ("notary_refuses", "dma_never", "interrupt"):
            self.assertFalse(s[name]["o"], name)
            self.assertTrue(any("no observation sealed" in m for m in s[name]["findings"]), name)
            self.assertIn("no observation sealed", self.rep(name)["transactions"][1]["outcome"])
        self.assertEqual(s["dma_never"]["phase"], "P2"); self.assertIn("D_P_DONE never", s["dma_never"]["reason"])
        self.assertEqual(s["interrupt"]["status"], 5); self.assertEqual(s["interrupt"]["interrupted"]["after_accesses"], 3000)
        self.assertGreater(s["latch_unmodelled"]["unmodelled_reads"], 0)
        self.assertTrue(any("bad value" in m for m in s["latch_unmodelled"]["findings"]))

    def test_r1_fail_closed_before_the_next_operation(self):
        """R1 (the owner's HOLD of 2026-10-27): the forbidden LATER event / DMA / signature is ABSENT, not merely found afterwards"""
        s = _STATE["summary"]; root = _STATE["root"]
        # a refused opening: no root is signed
        st = s["startup_corrupt"]
        self.assertEqual((st["open_status"], st["signatures"]), ("refused", 0)); self.assertIn("no open session", st["root_refused"]); self.assertIsNotNone(st["halted"])
        self.assertEqual(json.loads((root / "startup_corrupt/notary_log.json").read_text()), [])
        # a corrupted pre-event readback: the ARM is the only CTRL write of the transaction (no PRE_SAMPLE, no INIT_REQ), no O, the next transaction refused, no further signature
        pe = s["pre_event_corrupt"]
        self.assertEqual((pe["status"], pe["phase"], pe["ctrl_writes_in_tx"], pe["signed_after"], pe["o"]), (1, "P2", ["0x40"], 0, False)); self.assertIn("halted", pe["next_refused"])
        trace = [json.loads(l) for l in (root / "pre_event_corrupt/trace.jsonl").read_text().splitlines() if l.strip()]
        marks = [i for i, e in enumerate(trace) if e.get("mark") == "transaction_begin"]
        after = trace[marks[1]:]
        self.assertFalse(any(e.get("op") == "wr" and e.get("addr") == 0x2000 and e.get("data") in (0x200, 0x400, 0x800) for e in after))   # no PRE_SAMPLE / INIT_REQ / STEP
        self.assertEqual(len(marks), 2)                                                                                                     # nothing was signed and run after it
        # a corrupted post-event readback: the init event happened, no STEP, no cleanup, no close
        po = s["post_event_corrupt"]
        self.assertEqual((po["status"], po["phase"], po["ctrl_writes_in_tx"], po["signed_after"]), (1, "P4", ["0x40", "0x200", "0x400"], 0))
        # a corrupted restored-base readback: the O sealed complete, no RESTORE_INIT and no CLOSE after it, X absent, nothing further
        br = s["base_readback_corrupt"]
        self.assertEqual((br["status"], br["phase"], br["o_status"], br["x"], br["signed_after"]), (2, "P8", "complete", None, 0))
        self.assertNotIn("0x4000", br["ctrl_writes_in_tx"]); self.assertNotIn("0x2000", br["ctrl_writes_in_tx"])
        # STEP_IN answered SLVERR without a change: no STEP launched on the stale word
        si = s["step_in_slverr"]
        self.assertEqual((si["status"], si["phase"], si["step_launches"], si["o"]), (1, "P5", 0, False)); self.assertIn("SLVERR", si["reason"])
        # the invalid record and the refused latch record halt the session: the next transaction refused, nothing signed
        self.assertIsNotNone(s["not_realisable"]["next_refused"]); self.assertEqual(s["not_realisable"]["signed_after"], 0)
        self.assertIsNotNone(s["latch_unmodelled"]["next_refused"])
        for name in ("startup_corrupt", "pre_event_corrupt", "post_event_corrupt", "base_readback_corrupt", "step_in_slverr"):
            rep = self.rep(name)
            self.assertTrue(rep["agree"], (name, rep["session"], [t.get("only_here") for t in rep["transactions"]]))
            self.assertIsNotNone(json.loads((root / name / "manifest.json").read_text())["halted"], name)

    def test_r2_archive_completeness_and_refusals(self):
        import shutil
        src = _STATE["root"] / "valid"
        # R2a: a dropped final transaction (manifest intact) is refused
        d = _STATE["root"] / "valid_dropped"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(src, d); shutil.rmtree(d / "tx_004")
        rep = vf.verify(d); self.assertIn("declared in the manifest, not present", rep["refused"] or ""); self.assertFalse(rep["agree"])
        # an undeclared extra record directory is refused
        d = _STATE["root"] / "valid_extra"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(src, d); shutil.copytree(d / "tx_004", d / "tx_005")
        rep = vf.verify(d); self.assertIn("not declared", rep["refused"] or "")
        # a record silently removed from the manifest AND its directory: the raw trace suffix is unconsumed
        d = _STATE["root"] / "valid_tail"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(src, d); shutil.rmtree(d / "tx_004")
        m = json.loads((d / "manifest.json").read_text()); m["records"] = m["records"][:3]; (d / "manifest.json").write_text(json.dumps(m))
        rep = vf.verify(d); self.assertIsNone(rep["refused"]); self.assertTrue(any("unindexed suffix" in x or "not covered" in x for x in rep["session"]), rep["session"]); self.assertFalse(rep["agree"])
        # R2c: a malformed manifest is a named refusal with a non-zero exit and no traceback
        d = _STATE["root"] / "valid_malformed"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(src, d); (d / "manifest.json").write_text("[]")
        p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(d)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1); self.assertIn("REFUSED", p.stdout); self.assertNotIn("Traceback", p.stderr)
        for bad in ('{"schema": "b4q_session"}', "not json", '{"schema": "b4q_session", "records": "x"}'):
            (d / "manifest.json").write_text(bad)
            p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(d)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 1, bad); self.assertIn("REFUSED", p.stdout); self.assertNotIn("Traceback", p.stderr)
        shutil.rmtree(d); shutil.copytree(src, d); (d / "trace.jsonl").unlink()
        self.assertIn("missing", vf.verify(d)["refused"])
        # R2b: the staging witness is the retained submitted stream, recomputed; a tampered retained stream is found
        d = _STATE["root"] / "valid_stream"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(src, d)
        lines = (d / "pcap_log.jsonl").read_text().splitlines()
        for i, l in enumerate(lines):
            e = json.loads(l)
            if e.get("pcap") == "stream_submitted":
                h = e["stream_words_hex"]; e["stream_words_hex"] = h[:2400] + ("0" if h[2400] != "0" else "1") + h[2401:]; lines[i] = json.dumps(e); break
        (d / "pcap_log.jsonl").write_text("\n".join(lines) + "\n")
        rep = vf.verify(d)
        self.assertTrue(any("retained submitted stream" in m or "links.staging" in m for m in rep["transactions"][0]["findings"]), rep["transactions"][0]["findings"])
        links = json.loads((src / "tx_002/links.json").read_text()); fw = json.loads((src / "tx_002/firmware_result.json").read_text())
        self.assertEqual(links["staging_readback_sha256"], fw["staged"])                      # the executing side's link-2 digest equals the pre-write witness
        self.assertEqual(links["staging_readback_sha256"], links["fabric_readback_sha256_pre_event"])   # mechanism (b) on the emulation: equal values, two commitments

    def test_r3_qualification_conclusions_recomputed_and_conditioned(self):
        import shutil
        import b4q_qual as ql
        root = _STATE["root"]
        for scenario, f, edit, needle in (("a8_cross", "a8_cross.json", lambda v: v["AFF"].update({"row": 5, "verdict": "neither demonstrated"}), "A8 AFF"),
                                          ("a5_persist", "a5_verdict.json", lambda v: v.update({"verdict": "pass"}), "A5"),
                                          ("a2_pairs", "a2_rows.json", lambda v: v["ce_mode"].update({"verdict": "does_not_differ"}), "A2 ce_mode")):
            d = root / f"{scenario}_altered"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(root / scenario, d)
            v = json.loads((d / f).read_text()); edit(v); (d / f).write_text(json.dumps(v))
            rep = vf.verify(d)
            self.assertTrue(any(needle in m for m in rep["qualification"]["findings"]), (scenario, rep["qualification"]))
            self.assertFalse(rep["agree"], scenario)
        d = root / "a8_cross_undeclared"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(root / "a8_cross", d)
        m = json.loads((d / "manifest.json").read_text()); m["qualification_plan"]["a8"] = []; (d / "manifest.json").write_text(json.dumps(m))
        rep = vf.verify(d); self.assertTrue(any("declared no a8" in x for x in rep["qualification"]["findings"]))
        # A5 without the close witnesses is never a pass; a corner without its closed X is not demonstrated
        A = root / "a5"; rd = lambda n: json.loads((A / n).read_text())
        self.assertEqual(ql.a5_verdict(rd("tx_002/o.json"), rd("tx_003/o.json"), rd("tx_004/o.json"))["verdict"], "not_demonstrated")
        self.assertEqual(ql.a5_verdict(rd("tx_002/o.json"), rd("tx_003/o.json"), rd("tx_004/o.json"), rd("tx_002/x.json"), rd("tx_004/x.json"))["verdict"], "not_demonstrated")   # J2's injection_open missing
        self.assertEqual(ql.a5_verdict(rd("tx_002/o.json"), rd("tx_003/o.json"), rd("tx_004/o.json"), rd("tx_002/x.json"), rd("tx_004/x.json"), rd("tx_003/x.json"))["verdict"], "pass")
        C = root / "a8_cross"; plan = json.loads((C / "manifest.json").read_text())["qualification_plan"]["a8"][0]
        corners = {c: json.loads((C / f"tx_{seq:03d}/o.json").read_text()) for c, seq in plan["corners"].items()}
        closes = {c: json.loads((C / f"tx_{seq:03d}/x.json").read_text()) for c, seq in plan["corners"].items()}
        self.assertEqual(ql.a8_classify(corners, 0, plan["parts"], closes=closes)["row"], 2)
        self.assertEqual(ql.a8_classify(corners, 0, plan["parts"], closes={**closes, "01": None})["row"], 0)
        self.assertEqual(ql.a8_classify(corners, 0, plan["parts"])["row"], 0)
        three = {c: corners[c] for c in ("00", "01", "10")}
        self.assertEqual(ql.a8_classify(three, 0, plan["parts"], closes=closes)["row"], 0)

    def test_tampered_evidence_is_found(self):
        import shutil
        src = _STATE["root"] / "valid"; dst = _STATE["root"] / "valid_tampered"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        o = json.loads((dst / "tx_002/o.json").read_text()); o["steps"][2]["q_after"][0] ^= 1
        (dst / "tx_002/o.json").write_text(json.dumps(o, indent=1, sort_keys=True))
        rep = vf.verify(dst)
        self.assertFalse(rep["clean"]); self.assertTrue(any("stored record is not the one rebuilt" in m for m in rep["transactions"][1]["findings"]))
        shutil.rmtree(dst); shutil.copytree(src, dst)
        f = json.loads((dst / "tx_003/f.json").read_text()); f["fitness"] += 1
        (dst / "tx_003/f.json").write_text(json.dumps(f, indent=1, sort_keys=True))
        rep = vf.verify(dst)
        self.assertTrue(any(m.startswith("F:") for m in rep["transactions"][2]["findings"]))
        shutil.rmtree(dst); shutil.copytree(src, dst)
        lines = (dst / "accesses.jsonl").read_text().splitlines(); lines.append(json.dumps({"op": "wr", "addr": 0x43C02160, "resp": 0}))
        (dst / "accesses.jsonl").write_text("\n".join(lines) + "\n")
        rep = vf.verify(dst)
        self.assertTrue(any("KEY window" in m for m in rep["a7"]["findings"]))


if __name__ == "__main__":
    unittest.main()
