#!/usr/bin/env python3
"""B1 — an end-to-end MODELLED session (host-only; nothing here touches a board): the whole
335-record B1 session driven through the instrument's real host stack and adjudicated by
the real validators.

    b1_modelled_session.py --out <evidence dir> [--fixture truth|permuted|dropout|interact] [--p-fault P]

The board is a twin composed from the instrument's own rel-v4 twins (`l6_session_soak.Board`:
IDENT → per seq SIGNREQ ↔ SIGNOK → 16 indexed heartbeats → the audit pull → REC ↔ RECACK →
TERM, both seq-1 controls armed) with three B1 substitutions: the candidates come from the
reference orchestrator (`b1_carto.session_run`) over a simulated fabric; the records are B1
loop_records 1.2.0 — the carto block, a sign_reply with the ZERO tables, an app_oracle_record
whose hashes are the instrument's gate's over the candidate's real frames, an arm block on
the carrier's nonce chain, a score with the fabric's readout; the audit pull serves the
candidate's REAL staging streams and readback frames (2 814 words) so the instrument's
audit gate recomputes every hash. The host side is the instrument's ConsoleSession /
NotaryRelay (answering with the B1 signer's zero-table signature under a throw-away key) /
Collector / reader / timeline over a modelled channel (fault-free by default, or the soak's
fault classes with --p-fault). The evidence directory then holds run_log.json, audits.json
and timeline.json exactly as the runner writes them, and `b1_adjudicate` runs over it with
the instrument's validators (b1_records with the audit gate) — the same code path as a board
session, minus the silicon.
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
import claimb_r1p_instrument as inst  # noqa: E402

TOOL_VERSION = "b1_modelled_session.py/0.1.0"
ZERO = ["0" * 16] * 6


def bind_instrument(require_git: bool = False):
    inst.bind(inst.DEFAULT_ROOT, require_git=require_git)
    import l5_notary as n  # noqa: E402
    import l6_audit_pull as ap  # noqa: E402
    import l6_checks as lc  # noqa: E402
    import l6_console as lcs  # noqa: E402
    import l6_reader as lrd  # noqa: E402
    import l6_rec as rx  # noqa: E402
    import l6_rel as rel  # noqa: E402
    import l6_schedule as ls  # noqa: E402
    import l6_session_soak as soak  # noqa: E402
    import l6_timing as lt  # noqa: E402
    import l6_transport_soak as tsoak  # noqa: E402
    import p3_gate as g  # noqa: E402
    import p3_genome as gn  # noqa: E402
    import p3_oracle as po  # noqa: E402
    from validators import nonce as nc, signer as sg  # noqa: E402
    return dict(n=n, ap=ap, lc=lc, lcs=lcs, lrd=lrd, rx=rx, rel=rel, ls=ls, soak=soak, lt=lt, tsoak=tsoak, g=g, gn=gn, po=po, nc=nc, sg=sg)


class Candidates:
    """Per seq: genome, frames, the gate verdict (commit, sequence hash), the served words,
    the fabric's readout, the counters, the carto block — from the reference session."""

    def __init__(self, M, plan: dict, manifest: dict, fabric, token: str, key_path: Path):
        self.M = M
        g, gn, po, sg = M["g"], M["gn"], M["po"], M["sg"]
        self.phen = g.load_manifest()
        self.consts = po.load_constants()
        self.holder = sg.KeyHolder(key_path)
        image_lo32 = int(manifest["image"]["sha256"][-8:], 16)
        sim = bm.simulate(plan["master_seed"], plan["budget"], fabric, token=token, universe=manifest["universe"]["sha256"],
                          image_lo32=image_lo32)
        self.sim = sim
        base, roles = g.gc.pinned_frames(self.phen)
        targets = sorted(f for f, role in roles.items() if role == "target")
        self.by_seq: dict[int, dict] = {}
        self.by_genome: dict[str, int] = {}
        for r in sim["records"]:
            frames = gn.frames_from_genome(bc.genome_from_hex(r["genome"]), self.phen)
            streams = g.build_streams(frames, self.phen)
            verdict = g.gate(streams, self.phen)
            assert verdict["writable"], (r["seq"], verdict["findings"])
            words = [w for s in streams for w in s["words"]] + [w for far in targets for w in frames[far]]
            tables = r["tables"]
            self.by_seq[r["seq"]] = {"genome": r["genome"], "commit": verdict["candidate_sha256"],
                                     "sequence_sha256": verdict["sequence_sha256"], "words": words, "tables": tables,
                                     "scores": po.predict_scores(tables, self.consts), "carto": json.loads(r["carto"]),
                                     "is_baseline": r["is_baseline"]}
            self.by_genome[r["genome"]] = r["seq"]

    def sign(self, req: dict) -> dict:
        """The B1 signer, in-process (the ZERO tables), as the relay calls it."""
        sg = self.M["sg"]
        c = self.by_seq[self.by_genome[req["genome"]]]
        payload = sg.sign_arm(self.holder, {"writable": True, "candidate_sha256": c["commit"]},
                              bytes.fromhex(c["commit"]), [0] * 6, int(req["nonce"], 16).to_bytes(8, "little"))
        return {"commit": c["commit"], "expected_tables": ZERO, "tag": payload.tag.hex()}


def make_board_class(M):
    """The instrument's session-soak Board with the B1 substitutions."""
    n, rel = M["n"], M["rel"]

    class B1Board(M["soak"].Board):
        def __init__(self, cands: Candidates, token: str, plan: dict, manifest: dict, nonce_seed: int):
            super().__init__(token, plan["budget"], set(plan["audit_seqs"]), controls=True)
            self.cands, self.nc = cands, M["nc"]
            ident = {"schema": "app_identity", "schema_version": "1.4.0", "control_plane": "standalone", "token": token,
                     "protocol": "rel-v4", "master_seed": plan["master_seed"], "schedule_mode": "carto-v1",
                     "operator_data_sha256": manifest["universe"]["sha256"], "carto_version": "carto-v1",
                     "universe_sha256": manifest["universe"]["sha256"], "probe_budget": plan["budget"],
                     "carrier_variant": "0x42310001", "carrier_sha256": manifest["carrier"]["bitstream_sha256"],
                     "rec_retry_control": True, "sign_retry_control": True, "pss_idcode": "0x13722093",
                     "uboot_epoch": 0, "nonce_at_start": f"{nonce_seed:016x}", "findings": [], "app_epoch": 0,
                     "status_at_start": "0x00000900", "fclk0_hz_decoded": 50000000}
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
            self.nonce = self.nc.step(nb)         # the ARM consumes it
            return line

        def _after_sign(self) -> list[str]:
            hb = [rel.hb_line(self.token, self.seq, i) for i in range(rel.HB_PER_RECORD)]
            if self.tx.reply_type == n.T_SIGNOK and self.tx.audit_requested:
                self.phase = "PULL"
                self.pull = rel.ReadyBoard(self.token, self.seq, "streams+readback", self.cands.by_seq[self.seq]["words"], requested=True)
                out = self.pull.start()
                self.stats["ready_sent"] += 1
                return hb + out
            return hb + self._begin_rec(audited=False)

        def _record(self, seq: int, audited: bool) -> dict:
            c = self.cands.by_seq[seq]
            nb, na = self.nonces[seq]
            tag = self.cands.sign({"genome": c["genome"], "nonce": f"{nb:016x}"})["tag"]
            return {"schema": "loop_record", "schema_version": "1.2.0", "seq": seq, "outcome": "SCORED",
                    "verified": "audited" if audited else "replayed-only", "genome": c["genome"], "carto": c["carto"],
                    "evidence": {
                        "sign_reply": {"schema": "sign_reply", "schema_version": "1.0.0", "seq": seq, "commit": c["commit"],
                                       "expected_tables": ZERO, "tag": tag},
                        "app_oracle_record": {"schema": "app_oracle_record", "schema_version": "1.0.0", "seq": seq,
                                              "staged_sha256": c["commit"], "staged_stream_sha256": c["sequence_sha256"],
                                              "readback_sha256": c["commit"], "audit_available": True,
                                              "write": {"envelopes": [{"index": i, "int_sts": "0x50033004"} for i in range(3)]}},
                        "arm": {"nonce_before": f"{nb:016x}", "nonce_after": f"{na:016x}", "status_after": "0x00000f54", "fault_after": 0,
                                "key_loaded_observed": True, "ctrl_readback": "unavailable: CTRL is write-only", "writes_issued": 25,
                                "settle": {"polls": 16, "polls_max": 1000000, "settled": True, "status_first": "0x00000901",
                                           "status_last": "0x00000f54"}},
                        "score": {"hw_candidate_commit": c["commit"], "functional_readout": [f"{t:016x}" for t in c["tables"]],
                                  "scores": c["scores"], "heartbeat": {"before": 100 * seq, "after": 100 * seq + 50}}}}

        def _term(self, kind: str, reason: str) -> list[str]:
            self.phase = "TERM"
            p = {"schema": "session_summary", "schema_version": "1.0.0", "token": self.token,
                 "epoch_end": {"kind": kind, "last_seq": self.seq if kind != "COMPLETED" else self.records_total, "reason": reason},
                 "counts": {"scored": len(self.records), "refused_by_gate": 0},
                 "closing": {"restore": "done", "baseline": "done", "unsigned_control": "done"} if kind == "COMPLETED"
                 else {"restore": "done", "baseline": "not_reached", "unsigned_control": "not_reached"},
                 "audit": {"audited": sum(1 for r in self.records if r["verified"] == "audited"), "total": len(self.records)},
                 "crc_dropped": 0, "drop_budget": 0, "written_by": "app"}
            if kind == "COMPLETED":
                p["closing_control"] = {"fault": 13, "kind": "unsigned", "status": "0x00000982",
                                        "nonce_before": f"{self.nonce:016x}", "nonce_after": f"{self.nc.step(self.nonce):016x}"}
            self.tx = rel.TermBoard(self.token, self.records_total + 1, n.build_line(n.T_TERM, self.records_total + 1, self.token, n.encode_payload(p)))
            self.stats["term_attempts"] += 1
            close = [n.build_line(n.T_CLOSE, self.records_total + 1, self.token, n.encode_payload(p["closing_control"]))] if kind == "COMPLETED" else []
            return close + self.tx.start()

    return B1Board


class B1Session:
    """The instrument's SessionSoak driver with the B1 board, every seq audited, the B1
    signer behind the relay and the runner's identity check."""

    def __init__(self, M, cands: Candidates, plan: dict, manifest: dict, token: str, seed: int = 1,
                 p_fault: float = 0.0, p_h2b: float = 0.0, identity_check=None):
        n, lcs, lrd, lt, tsoak, soak = M["n"], M["lcs"], M["lrd"], M["lt"], M["tsoak"], M["soak"]
        self.M, self.plan, self.token = M, plan, token
        self.rng = random.Random(seed)
        self.now = 1000.0
        clock = lambda: self.now  # noqa: E731
        self.audit_seqs = set(plan["audit_seqs"])
        self.crc_budget = plan["crc_budget"]
        self.collector = n.Collector(token, heartbeat_s=10, clock=clock)
        self.relay = n.NotaryRelay(token, cands.sign, drop_budget=self.crc_budget, clock=clock)
        self.timeline = lt.Timeline()
        self.channel = tsoak.Channel()
        self.reader = lrd.L6LineReader(self.channel, clock_mono=clock, clock_wall=clock)
        self.to_board: list[tuple[float, str]] = []
        self.faults: list[dict] = []
        self.wire = soak.FaultyWire(self.rng, p_fault, self.faults)
        self.wire_free_at = self.now
        self.board = make_board_class(M)(cands, token, plan, manifest, int(manifest["carrier"]["nonce_seed"], 16))
        self.h2b_dropped = 0
        self.p_h2b = p_h2b
        self.t_go = self.now

        def send(line: str, mtype: str, seq: int) -> None:
            self.timeline.note_sent(mtype, seq, self.now, self.now)
            if self.rng.random() < self.p_h2b:
                self.h2b_dropped += 1
                return
            self.to_board.append((self.now + soak.wire_s(len(line)), line))
            self.to_board.sort(key=lambda x: x[0])
        self.cs = lcs.ConsoleSession(token, self.collector, self.relay, self.timeline, self.audit_seqs, self.crc_budget,
                                     send=send, reader=self.reader, clock=clock, protocol="rel-v4",
                                     identity_check=identity_check or (lambda ident: []), bad_frame_policy=lcs.BAD_FRAME_LEDGER,
                                     bad_frame_budget=plan["bad_frame_budget"])
        self.soak = soak; self.tsoak = tsoak

    def _emit(self, lines):
        for line in lines:
            data = self.wire.apply(line, self.now)
            if not data:
                continue
            t0 = max(self.now, self.wire_free_at)
            for t, piece in self.tsoak._split_pieces(self.rng, data, t0):
                self.channel.schedule(t, piece)
            self.wire_free_at = t0 + self.soak.wire_s(len(data))

    def _host_poll(self):
        self.channel.release(self.now)
        while self.channel.ready:
            for line, tm, tw in self.reader.poll():
                self.cs.on_line(line, tm, tw)
        self.cs.tick()
        self.collector.poll()

    def run(self, max_virtual_s: float = 3600.0) -> None:
        self._emit(self.board.start())
        t_end = self.now + max_virtual_s
        while self.now < t_end:
            if self.board.done and not self.channel.pending and not self.channel.ready and not self.to_board:
                break
            nxt = [t for t in (self.channel.next_time(), self.to_board[0][0] if self.to_board else None) if t is not None]
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

    def write_evidence(self, out_dir: Path, binding: dict) -> None:
        lt = self.M["lt"]
        out_dir.mkdir(parents=True, exist_ok=True)
        seqs = [r["seq"] for r in self.collector.loop_records]
        timing = lt.record_timing(self.timeline.frames, seqs)
        log = {"control_plane": "standalone", "app_identity": self.collector.app_identity,
               "loop_records": self.collector.loop_records, "session_summary": self.collector.session_summary,
               "notary_log": self.relay.notary_log(),
               "timing": {"clocks": lt.CLOCKS, "t_go_mono": self.t_go, "records": {str(s): timing[s] for s in seqs}},
               "l6": {**{k: self.plan[k] for k in ("session", "master_seed", "budget", "audit_seqs", "crc_budget", "session_timeout_s", "flags", "protocol")},
                      "n": self.plan["budget"], "binding": binding}}
        if self.collector.closing_negative is not None:
            log["closing_negative"] = self.collector.closing_negative
        (out_dir / "run_log.json").write_text(json.dumps(log, indent=1))
        (out_dir / "audits.json").write_text(json.dumps({"chunks": self.collector.audits, "pulls": self.cs.pull_ledgers,
                                                          "recs": self.cs.rec_ledgers_json(), **self.cs.rel_ledgers_json()}, indent=1))
        (out_dir / "timeline.json").write_text(json.dumps(self.timeline.to_json(), indent=1))
        (out_dir / "modelled_session.json").write_text(json.dumps({
            "tool": TOOL_VERSION, "epoch_end": self.collector.epoch_end, "records": len(seqs), "virtual_s": self.now - 1000.0,
            "board_stats": self.board.stats, "faults": len(self.faults), "crc_dropped": self.timeline.crc_dropped,
            "bad_frames": self.timeline.bad_frames, "h2b_dropped": self.h2b_dropped}, indent=1))


def run_modelled(manifest: dict, plan: dict, out_dir: Path, fixture: str = "truth", fixture_seed: int = 0,
                 token: str | None = None, p_fault: float = 0.0, p_h2b: float = 0.0, seed: int = 1,
                 binding_extra: dict | None = None, require_git: bool = False) -> dict:
    M = bind_instrument(require_git)
    token = token or hashlib.sha256(f"b1-modelled-{seed}".encode()).hexdigest()[:32]
    d = Path(tempfile.mkdtemp()); key = d / "K.bin"; key.write_bytes(bytes(range(16))); os.chmod(key, 0o400)
    cands = Candidates(M, plan, manifest, bm.fixture(fixture, fixture_seed), token, key)
    import b1_runner
    check = b1_runner.identity_check_for(plan, manifest)
    s = B1Session(M, cands, plan, manifest, token, seed=seed, p_fault=p_fault, p_h2b=p_h2b, identity_check=check)
    t0 = time.monotonic()
    s.run()
    binding = {"image_sha256": manifest["image"]["sha256"], "prereg_sha256": manifest["prereg"]["sha256"], "protocol": "rel-v4",
               "session": "B1", "schedule_mode": "carto-v1", "master_seed": plan["master_seed"],
               "psoracle_commit": manifest["instrument"]["psoracle_commit"], **(binding_extra or {})}
    s.write_evidence(out_dir, binding)
    return {"epoch_end": s.collector.epoch_end, "records": len(s.collector.loop_records), "virtual_s": s.now - 1000.0,
            "wall_s": time.monotonic() - t0, "token": token, "faults": len(s.faults)}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=REPO_ROOT / "manifests/b1_manifest.json")
    ap.add_argument("--plan", type=Path, default=REPO_ROOT / "evidence/b1/plan.json")
    ap.add_argument("--fixture", default="truth")
    ap.add_argument("--p-fault", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    manifest = json.loads(a.manifest.read_text())
    plan = json.loads(a.plan.read_text())
    r = run_modelled(manifest, plan, a.out, fixture=a.fixture, p_fault=a.p_fault, seed=a.seed)
    print(json.dumps(r, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
