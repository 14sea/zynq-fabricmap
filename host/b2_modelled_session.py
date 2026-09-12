#!/usr/bin/env python3
"""B2 — an end-to-end MODELLED session (host-only; nothing here touches a board): a whole B2 or
B2Q session driven through the instrument's real host stack and judged by the real verdict.

    b2_modelled_session.py --out <evidence dir> [--manifest …] [--seed N]

Only the B2Q profile is driven from this entry point: at budget 600 one B2 slice is thousands of
records, which belongs in a one-off demonstration rather than a command-line default.

The board is a twin composed from the instrument's own rel-v4 twins (`l6_session_soak.Board`:
IDENT → per seq SIGNREQ ↔ SIGNOK → indexed heartbeats → the audit pull → REC ↔ RECACK → TERM,
both seq-1 controls armed) with B2's substitutions: the candidates come from the reference
orchestrator (`b2_session.run`) over the fabric model; the records are loop_records 1.3.0 with
the `search` block and the arm; the IDENT is app_identity 1.5.0 with the map digest, the fitness,
the budget and this session's pair slice; the score carries the model's readout and the PL
scorer's additive counts over it; the audit pull serves the candidate's REAL staging streams and
readback frames so the instrument's audit gate recomputes every hash.

The host side is the instrument's ConsoleSession / NotaryRelay (answering with the B1 signer's
zero-table signature under a throw-away key) / Collector / reader / timeline over a modelled
channel, and the evidence is written by the PRODUCTION exporter (`b1_session.export_evidence`) —
the same code path a board session takes — plus the session artifacts the runner archives: the
manifest at run and the two inert ruling archives.

WHAT IT IS NOT. The model stands in for a board: this is not silicon evidence, not a session,
and not a qualification. It exists so the offline verdict and the S1 → B2Q → S2 → S3 lifecycle
can be exercised end to end without a board, which no replay or stored-verdict double can do.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_runner as rn  # noqa: E402
import b2_search as bs  # noqa: E402
import b2_session as bsess  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

TOOL_VERSION = "b2_modelled_session.py/0.1.0"
ZERO = ["0" * 16] * 6
STATUS_BASE = (1 << 2) | (1 << 4) | (1 << 6) | (1 << 8) | (1 << 9) | (1 << 11)
STATUS_TABLES_MATCH = 1 << 10


def status_after(tables: list[int]) -> int:
    return STATUS_BASE | (STATUS_TABLES_MATCH if not any(tables) else 0)


def bind_instrument(require_git: bool = False) -> dict:
    inst.bind(inst.DEFAULT_ROOT, require_git=require_git)
    import l5_notary as n  # noqa: E402
    import l6_console as lcs  # noqa: E402
    import l6_reader as lrd  # noqa: E402
    import l6_rel as rel  # noqa: E402
    import l6_session_soak as soak  # noqa: E402
    import l6_timing as lt  # noqa: E402
    import l6_transport_soak as tsoak  # noqa: E402
    import p3_gate as g  # noqa: E402
    import p3_genome as gn  # noqa: E402
    import p3_oracle as po  # noqa: E402
    from validators import nonce as nc, signer as sg  # noqa: E402
    return dict(n=n, lcs=lcs, lrd=lrd, rel=rel, soak=soak, lt=lt, tsoak=tsoak, g=g, gn=gn, po=po, nc=nc, sg=sg)


class Candidates:
    """Per seq: the genome, its frames, the gate verdict, the served words, the model's readout,
    the PL scorer's counts and the `search` block — from the reference orchestrator."""

    def __init__(self, M: dict, manifest: dict, session_plan: dict, seeds: list, key_path: Path):
        g, gn, po, sg = M["g"], M["gn"], M["po"], M["sg"]
        self.M = M
        self.phen = g.load_manifest()
        self.consts = po.load_constants()
        self.holder = sg.KeyHolder(key_path)
        truth = bm.truth_mapping()
        masks = bl.universe_mask(truth)
        fabric = bs.ModelFabric(truth)
        view = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
        sess = bsess.run(session_plan["master_seed"], session_plan["n"], session_plan["pairs_total"],
                         session_plan["pair_first"], session_plan["pair_count"], fabric, view,
                         truth=truth, masks=masks, pair_seeds=seeds)
        base, roles = g.gc.pinned_frames(self.phen)
        targets = sorted(f for f, role in roles.items() if role == "target")
        self.by_seq: dict[int, dict] = {}
        self.by_genome: dict[str, int] = {}
        for c in sess.candidates:
            frames = gn.frames_from_genome(c.genome, self.phen)
            streams = g.build_streams(frames, self.phen)
            verdict = g.gate(streams, self.phen)
            if not verdict["writable"]:
                raise RuntimeError(f"seq {c.seq}: the gate refuses the reference's genome: {verdict['findings']}")
            words = [w for s in streams for w in s["words"]] + [w for far in targets for w in frames[far]]
            tables = fabric(c.genome)
            self.by_seq[c.seq] = {"genome": bc.genome_to_hex(c.genome), "commit": verdict["candidate_sha256"],
                                  "sequence_sha256": verdict["sequence_sha256"], "words": words, "tables": tables,
                                  "scores": po.predict_scores(tables, self.consts),
                                  "search": json.loads(c.block) if c.block else None,
                                  "arm": c.arm, "is_baseline": c.is_baseline}
            self.by_genome[bc.genome_to_hex(c.genome)] = c.seq
        self.records_total = len(sess.candidates)

    def sign(self, req: dict) -> dict:
        """The B1 signer, in-process, with the ZERO tables the B2 contract signs."""
        sg = self.M["sg"]
        c = self.by_seq[self.by_genome[req["genome"]]]
        payload = sg.sign_arm(self.holder, {"writable": True, "candidate_sha256": c["commit"]},
                              bytes.fromhex(c["commit"]), [0] * 6, int(req["nonce"], 16).to_bytes(8, "little"))
        return {"commit": c["commit"], "expected_tables": ZERO, "tag": payload.tag.hex()}


def make_board_class(M: dict):
    n, rel = M["n"], M["rel"]

    class B2Board(M["soak"].Board):
        def __init__(self, cands: Candidates, token: str, session_plan: dict, manifest: dict, nonce_seed: int):
            super().__init__(token, cands.records_total - 2, set(session_plan["audit_seqs"]), controls=True)
            self.cands, self.nc = cands, M["nc"]
            ident = dict(rn.expected_identity(manifest, session_plan),
                         schema="app_identity", schema_version="1.5.0", control_plane="standalone",
                         token=token, schedule_mode=bs.ENGINE_VERSION, pss_idcode="0x13722093",
                         uboot_epoch=0, nonce_at_start=f"{nonce_seed:016x}", findings=[], app_epoch=0,
                         status_at_start="0x00000900", fclk0_hz_decoded=50000000)
            self.ident_line = n.build_line(n.T_IDENT, 0, token, n.encode_payload(ident))
            self.nonce = nonce_seed
            self.nonces: dict[int, tuple[int, int]] = {}

        def _signreq(self, seq: int) -> str:
            c = self.cands.by_seq[seq]
            nb = self.nonce
            self.nonces[seq] = (nb, self.nc.step(nb))
            line = n.build_line(n.T_SIGNREQ, seq, self.token, n.encode_payload(
                {"seq": seq, "token": self.token, "genome": c["genome"], "nonce": f"{nb:016x}", "app_epoch": 0,
                 "schema": "sign_request", "schema_version": "1.0.0"}))
            self.nonce = self.nc.step(nb)
            return line

        def _after_sign(self) -> list[str]:
            hb = [rel.hb_line(self.token, self.seq, i) for i in range(rel.HB_PER_RECORD)]
            if self.tx.reply_type == n.T_SIGNOK and self.tx.audit_requested:
                self.phase = "PULL"
                self.pull = rel.ReadyBoard(self.token, self.seq, "streams+readback",
                                           self.cands.by_seq[self.seq]["words"], requested=True)
                out = self.pull.start()
                self.stats["ready_sent"] += 1
                return hb + out
            return hb + self._begin_rec(audited=False)

        def _record(self, seq: int, audited: bool) -> dict:
            c = self.cands.by_seq[seq]
            nb, na = self.nonces[seq]
            tag = self.cands.sign({"genome": c["genome"], "nonce": f"{nb:016x}"})["tag"]
            st = status_after(c["tables"])
            rec = {"schema": "loop_record", "schema_version": "1.3.0", "seq": seq, "outcome": "SCORED",
                   "verified": "audited" if audited else "replayed-only", "genome": c["genome"],
                   "evidence": {
                       "sign_reply": {"schema": "sign_reply", "schema_version": "1.0.0", "seq": seq,
                                      "commit": c["commit"], "expected_tables": ZERO, "tag": tag},
                       "app_oracle_record": {"schema": "app_oracle_record", "schema_version": "1.0.0", "seq": seq,
                                             "staged_sha256": c["commit"], "staged_stream_sha256": c["sequence_sha256"],
                                             "readback_sha256": c["commit"], "audit_available": True,
                                             "write": {"envelopes": [{"index": i, "int_sts": "0x50033004"} for i in range(3)]}},
                       "arm": {"nonce_before": f"{nb:016x}", "nonce_after": f"{na:016x}",
                               "status_after": f"{st:#010x}", "fault_after": 0, "key_loaded_observed": True,
                               "ctrl_readback": "unavailable: CTRL is write-only", "writes_issued": 25,
                               "settle": {"polls": 16, "polls_max": 1000000, "settled": True,
                                          "status_first": "0x00000901", "status_last": f"{st:#010x}"}},
                       "score": {"hw_candidate_commit": c["commit"],
                                 "functional_readout": [f"{t:016x}" for t in c["tables"]],
                                 "scores": c["scores"], "heartbeat": {"before": 100 * seq, "after": 100 * seq + 50}}}}
            if c["arm"]:
                rec["arm"] = c["arm"]
            if c["search"]:
                rec["search"] = c["search"]
            return rec

        def _term(self, kind: str, reason: str) -> list[str]:
            self.phase = "TERM"
            p = {"schema": "session_summary", "schema_version": "1.0.0", "token": self.token,
                 "epoch_end": {"kind": kind, "last_seq": self.seq if kind != "COMPLETED" else self.records_total,
                               "reason": reason},
                 "counts": {"scored": len(self.records), "refused_by_gate": 0},
                 "closing": {"restore": "done", "baseline": "done", "unsigned_control": "done"} if kind == "COMPLETED"
                 else {"restore": "done", "baseline": "not_reached", "unsigned_control": "not_reached"},
                 "audit": {"audited": sum(1 for r in self.records if r["verified"] == "audited"),
                           "total": len(self.records)},
                 "crc_dropped": 0, "drop_budget": 0, "written_by": "app"}
            if kind == "COMPLETED":
                p["closing_control"] = {"fault": 13, "kind": "unsigned", "status": "0x00000982",
                                        "nonce_before": f"{self.nonce:016x}",
                                        "nonce_after": f"{self.nc.step(self.nonce):016x}"}
            self.tx = rel.TermBoard(self.token, self.records_total + 1,
                                    n.build_line(n.T_TERM, self.records_total + 1, self.token, n.encode_payload(p)))
            self.stats["term_attempts"] += 1
            close = [n.build_line(n.T_CLOSE, self.records_total + 1, self.token, n.encode_payload(p["closing_control"]))] \
                if kind == "COMPLETED" else []
            return close + self.tx.start()

    return B2Board


class B2Session:
    """The instrument's soak driver with the B2 board, every seq audited, the B1 signer behind
    the relay and the runner's own identity check."""

    def __init__(self, M: dict, cands: Candidates, session_plan: dict, manifest: dict, token: str,
                 seed: int = 1, identity_check=None):
        n, lcs, lrd, lt, tsoak, soak = M["n"], M["lcs"], M["lrd"], M["lt"], M["tsoak"], M["soak"]
        self.M, self.plan, self.token = M, session_plan, token
        self.rng = random.Random(seed)
        self.now = 1000.0
        clock = lambda: self.now  # noqa: E731
        self.audit_seqs = set(session_plan["audit_seqs"])
        self.crc_budget = session_plan["crc_budget"]
        self.collector = n.Collector(token, heartbeat_s=10, clock=clock)
        self.relay = n.NotaryRelay(token, cands.sign, drop_budget=self.crc_budget, clock=clock)
        self.timeline = lt.Timeline()
        self.channel = tsoak.Channel()
        self.reader = lrd.L6LineReader(self.channel, clock_mono=clock, clock_wall=clock)
        self.to_board: list[tuple[float, str]] = []
        self.faults: list[dict] = []
        self.wire = soak.FaultyWire(self.rng, 0.0, self.faults, scripted=[])
        self.wire_free_at = self.now
        b1_manifest = json.loads(REPO_ROOT.joinpath("manifests/b1_manifest.json").read_text())
        self.board = make_board_class(M)(cands, token, session_plan, manifest,
                                         int(b1_manifest["carrier"]["nonce_seed"], 16))
        self.t_go = self.now

        def send(line: str, mtype: str, seq: int) -> None:
            self.timeline.note_sent(mtype, seq, self.now, self.now)
            self.to_board.append((self.now + soak.wire_s(len(line)), line))
            self.to_board.sort(key=lambda x: x[0])
        self.cs = lcs.ConsoleSession(token, self.collector, self.relay, self.timeline, self.audit_seqs,
                                     self.crc_budget, send=send, reader=self.reader, clock=clock,
                                     protocol=session_plan["protocol"],
                                     identity_check=identity_check or (lambda ident: []),
                                     bad_frame_policy=lcs.BAD_FRAME_LEDGER,
                                     bad_frame_budget=session_plan["bad_frame_budget"])
        self.soak, self.tsoak = soak, tsoak

    def _emit(self, lines):
        for line in lines:
            data = self.wire.apply(line, self.now)
            if not data:
                continue
            t0 = max(self.now, self.wire_free_at)
            for t, piece in self.tsoak._split_pieces(self.rng, data, t0):   # noqa: SLF001
                self.channel.schedule(t, piece)
            self.wire_free_at = t0 + self.soak.wire_s(len(data))

    def _host_poll(self):
        self.channel.release(self.now)
        while self.channel.ready:
            for line, tm, tw in self.reader.poll():
                self.cs.on_line(line, tm, tw)
        self.cs.tick()
        self.collector.poll()

    def run(self, max_virtual_s: float = 86400.0) -> None:
        self._emit(self.board.start())
        t_end = self.now + max_virtual_s
        while self.now < t_end:
            if self.board.done and not self.channel.pending and not self.channel.ready and not self.to_board:
                break
            nxt = [t for t in (self.channel.next_time(), self.to_board[0][0] if self.to_board else None)
                   if t is not None]
            if nxt:
                step = min(min(nxt) - self.now, 0.5)
                self.now += max(step, 0.0)
                self._host_poll()
                while self.to_board and self.to_board[0][0] <= self.now:
                    _, line = self.to_board.pop(0)
                    self._emit(self.board.on_host_line(line))
                self._emit(self.board.tick(max(step, 0.0)))
            else:
                self.now += 0.5
                self._host_poll()
                self._emit(self.board.tick(0.5))
            if self.board.done and self.collector.epoch_end is not None and not self.cs.lingering(self.now):
                break

    def write_evidence(self, out_dir: Path) -> dict:
        """The PRODUCTION exporter over this session's collector / console / relay / timeline /
        reader — the same code path a board session takes."""
        import b1_session
        out_dir.mkdir(parents=True, exist_ok=True)
        plan = dict(self.plan)
        plan["audit_seqs"] = sorted(self.plan["audit_seqs"])
        summary = {"tool": TOOL_VERSION, "outcome": None, "token": self.token, "l6": plan}
        b1_session.export_evidence(out_dir, summary, self.plan, self.collector, self.cs, self.relay,
                                   self.timeline, self.reader, self.t_go)
        summary["crc_dropped"] = self.timeline.crc_dropped
        summary["bad_frames"] = self.timeline.bad_frames
        return summary


def session_artifacts(out_dir: Path, manifest: dict, manifest_sha256: str, session_plan: dict) -> dict:
    """The artifacts the runner archives BEFORE the port is opened: the manifest at run and the
    two INERT ruling envelopes. The rulings here are modelled test documents — they authorise
    nothing, and nothing consumes them."""
    import b1_qualification as bq
    import b2_manifest as bman
    b = session_plan["binding"]
    (out_dir / bman.MANIFEST_AT_RUN).write_text(bman.render(manifest))
    texts = {"whole_of_run": rn.QUAL_RULING_TEXT if b["session"] == bman.QUAL_SESSION else rn.RULING_TEXT,
             "provisioning": rn.PROVISION_RULING_TEXT}
    rulings = {}
    for key, name in bq.RULING_FILES.items():
        body = {"ruling": texts[key], "boardid": b["boardid"], "granted_by": "modelled session (no authority)",
                "date": "2026-09-11", "session": b["session"], "prereg_sha256": b["prereg_sha256"],
                "image_sha256": b["image_sha256"], "b2_manifest_sha256": b["b2_manifest_sha256"]}
        if key == "whole_of_run":
            body["master_seed"] = b["master_seed"]
        raw = json.dumps(body).encode()
        rulings[key] = (raw, body)
        (out_dir / name).write_text(json.dumps(bq.archive_envelope(raw)))
    return rulings


def run_modelled(manifest: dict, manifest_sha256: str, session_plan: dict, seeds: list, out_dir: Path,
                 token: str | None = None, seed: int = 1, require_git: bool = False) -> dict:
    """Drive the session, write the evidence with the production exporter, and archive the session
    artifacts — up to the point a board session reaches when its console loop ends.

    IT DOES NOT JUDGE. The caller owes the verdict and the finalisation, in that order, exactly as
    the runner does: `b2_runner.judge_session(...)` and then `finalize(out_dir, verdict, result
    ["summary"], result["rulings"])`, which writes `adjudication.json` and the final `summary.json`.
    `run_and_finalize` does both for a caller that wants the whole thing."""
    M = bind_instrument(require_git)
    token = token or hashlib.sha256(f"b2-modelled-{session_plan['session']}-{seed}".encode()).hexdigest()[:32]
    d = Path(tempfile.mkdtemp())
    key = d / "K.bin"
    key.write_bytes(bytes(range(16)))
    os.chmod(key, 0o400)
    cands = Candidates(M, manifest, session_plan, seeds, key)
    check = rn.identity_check_for({"manifest": manifest, "plan": session_plan})
    s = B2Session(M, cands, session_plan, manifest, token, seed=seed, identity_check=check)
    t0 = time.monotonic()
    s.run()
    out_dir = Path(out_dir)
    summary = s.write_evidence(out_dir)
    rulings = session_artifacts(out_dir, manifest, manifest_sha256, session_plan)
    return {"session": session_plan["session"], "token": token, "epoch_end": s.collector.epoch_end,
            "records": len(s.collector.loop_records), "virtual_s": s.now - 1000.0,
            "wall_s": time.monotonic() - t0, "crc_dropped": s.timeline.crc_dropped,
            "bad_frames": s.timeline.bad_frames, "exports": summary.get("exports"),
            "board_stats": s.board.stats, "summary": summary, "rulings": rulings, "out": str(out_dir)}


def run_and_finalize(manifest: dict, manifest_sha256: str, session_plan: dict, seeds: list,
                    out_dir: Path, token: str | None = None, seed: int = 1,
                    require_git: bool = False) -> dict:
    """The whole thing: drive, export, archive, JUDGE with the runner's own verdict, finalise."""
    result = run_modelled(manifest, manifest_sha256, session_plan, seeds, out_dir, token=token,
                          seed=seed, require_git=require_git)
    qplan, qpred, qseeds = rn.qualification_documents(manifest)
    verdict = rn.judge_session(out_dir, manifest, session_plan, qplan, qpred, qseeds, inst.DEFAULT_ROOT)
    finalize(out_dir, verdict, result["summary"], result["rulings"])
    result["verdict"] = verdict
    return result


def finalize(out_dir: Path, verdict: dict, summary: dict, rulings: dict) -> None:
    """What the runner's finalisation leaves beside the evidence AFTER the verdict: the
    adjudication and the final summary the lifecycle cross-checks."""
    out_dir = Path(out_dir)
    (out_dir / "adjudication.json").write_text(json.dumps(verdict, indent=1, sort_keys=True) + "\n")
    final = dict(summary)
    final["outcome"] = verdict["outcome"]
    final["ruling"] = rulings["whole_of_run"][1]
    final["provisioning_ruling_sha256"] = hashlib.sha256(rulings["provisioning"][0]).hexdigest()
    (out_dir / "summary.json").write_text(json.dumps(final, indent=1) + "\n")


def main(argv=None) -> int:
    import argparse
    import b2_manifest as bman
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=bman.MANIFEST)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    manifest = json.loads(a.manifest.read_text())
    bind_instrument(False)
    sha = hashlib.sha256(a.manifest.read_bytes()).hexdigest()
    plan = rn.qualification_session_plan(manifest, sha)
    seeds = rn.qualification_seeds(manifest)
    r = run_and_finalize(manifest, sha, plan, seeds, a.out, seed=a.seed)
    print(json.dumps({k: v for k, v in r.items() if k not in ("summary", "rulings")}, indent=1))
    return 0 if r["verdict"]["outcome"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
