#!/usr/bin/env python3
"""B4Q — the host SESSION RUNNER of the offline end-to-end observation transaction: it starts the executing-side program
(firmware/b4q, built on the host), answers its every MMIO access from the host backend (host/b4q_backend.py: the carrier
emulation, the DevC / PCAP fake, memory) and its every SIGN from the bench notary (host/b4q_notary.py), and builds the
records — session_open, O, F, X — FROM THE REGISTER TRACE through host/b4carrier_records.py exactly as the bench's records are
built, with the PCAP-side links taken from the backend's PCAP log (the host's view) and the executing side's reported digests
and fitness HELD TO the host's (a difference is a finding, never a repair). Everything is written to an evidence directory
that host/b4q_verify.py re-reads in a fresh process.

EMULATED, LABELLED: every readback digest here is of the backend's frame store, every sample of the hypothesis model; the
session proves the executing side's sequence, arithmetic and record production against the real record / validation path —
not a physical link, not silicon, not A8."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4carrier_records as rec  # noqa: E402
import b4carrier_regmap as rm  # noqa: E402
import b4q_backend as bk  # noqa: E402
import b4q_frames as fr  # noqa: E402
import b4q_notary as nt  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402

BINARY = R / "build/b4q_firmware/b4q_host"
SCHEMA = ("b4q_session", "1.0.0")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def step_word(s: dict) -> int:
    return rm.step_word(s["d"], s["ce"], s["sr"], s["clock"])


def config_list(genome: int) -> list:
    return [(genome >> i) & 1 for i in range(fr.GENOME_BITS)]


class SessionRefusal(ValueError):
    pass


class Session:
    def __init__(self, out_dir: Path, label: str = "B4Q-host", power_on: str = "init", gsr_init_effect: bool = True, binary: Path = BINARY, devc_faults: dict | None = None,
                 provision_key: bytes | None = None, notary_deny: set | None = None, interrupt_after_accesses: int | None = None, interrupt_tx: int | None = None):
        """The negative-path knobs are the ENVIRONMENT's, never the program's: `devc_faults` {(kind, ordinal): mode} on the DevC fake;
        `provision_key` a key other than the notary's (an AUTH fault); `notary_deny` genomes the notary refuses; `interrupt_after_accesses`
        the transport cut after that many accesses of the next transaction (an external interruption)."""
        self.out = Path(out_dir); self.out.mkdir(parents=True, exist_ok=True)
        self.label = label
        self.base, self.wl = fr.load_base(), fr.whitelist()
        self.backend = bk.Backend(self.base, self.wl, power_on=power_on, gsr_init_effect=gsr_init_effect)
        if devc_faults:
            self.backend.devc.faults.update(devc_faults)
        self.notary = nt.Notary(self.base, self.wl)
        self.notary_deny = set(notary_deny or ())
        self.backend.provision_key(provision_key if provision_key is not None else self.notary.key)   # the signer principal provisions the write-once key; the application never touches it
        self.interrupt_after = interrupt_after_accesses
        self.interrupt_tx = interrupt_tx                                    # the transaction number (1 = the root) the interruption is aimed at; None = any
        self.interrupted = None
        self.binary = Path(binary)
        if not self.binary.is_file():
            raise SessionRefusal(f"the executing-side program is not built: {self.binary}")
        self.proc = None
        self._tx_accesses = None
        self.events = []                                                   # EV / MARK lines, in order, with the trace position
        self.records = []                                                  # [{seq, kind, o, f, x, ctx, firmware, findings}]
        self.seq = 0
        self.prev_x = None
        self.session_open = None
        self.open_result = None
        self.instrument = {"variant": f"{rm.VARIANT_WORD:08x}", "carrier_sha256": self.base["bitstream_sha256"], "image_sha256": sha256_file(self.binary)}
        self.loaded_reference = fr.frames_hash(self.base["frames"])      # the loaded image's write-set frames, FAR-ordered (what a startup readback must reproduce)
        self.base_reference = fr.frames_hash(fr.derive_frames(0, self.base["frames"], self.wl))   # the restored study base (signed genome 0): a different commitment
        self.timing = {**rm.decode_timing(self.backend.carrier.timing_word), "pulse": self.backend.carrier.timing["pulse"]}
        self.mapping, self.hyp = bm.site_mapping(), hy.load()

    # ---------------------------------------------------------------- the transport
    def start(self):
        self.proc = subprocess.Popen([str(self.binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def _send(self, line: str):
        self.proc.stdin.write(line + "\n"); self.proc.stdin.flush()

    def serve(self) -> dict:
        """Answer the program's requests until it prints a RESULT line."""
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise SessionRefusal("the executing-side program ended without a RESULT")
            line = line.rstrip("\n")
            if (self.interrupt_after is not None and self._tx_accesses is not None and self._tx_accesses >= self.interrupt_after and line[:2] in ("R ", "W ")
                    and (self.interrupt_tx is None or self.interrupt_tx == self.seq + 1)):
                self.proc.stdin.close()                                     # the external interruption: the transport dies mid-transaction
                self.proc.wait(timeout=10)
                self.interrupted = {"after_accesses": self._tx_accesses, "last_request": line}
                return {"status": 5, "reason": "interrupted: the transport closed mid-transaction", "phase": "?"}
            if self._tx_accesses is not None and line[:2] in ("R ", "W "):
                self._tx_accesses += 1
            if line.startswith("R "):
                data, resp, x = self.backend.rd32(int(line[2:], 16))
                self._send(f"{data:08x} {resp}")
            elif line.startswith("W "):
                a, d = line[2:].split()
                self._send(str(self.backend.wr32(int(a, 16), int(d, 16))))
            elif line.startswith("SIGN "):
                _, g, n = line.split()
                try:
                    if int(g, 16) in self.notary_deny:
                        raise nt.NotaryRefusal("the bench notary refuses this genome (a configured refusal)")
                    s = self.notary.sign(int(g, 16), int(n, 16))
                    self._send("OK " + " ".join(f"{w:08x}" for w in s["words"]))
                except (nt.NotaryRefusal, fr.DeriveRefusal) as e:
                    self.notary.log.append({"genome_hex": g, "nonce": n, "refused": str(e)})
                    self._send(f"REFUSED {e}")
            elif line.startswith("MARK "):
                self.backend.mark(line[5:]); self.events.append({"i": len(self.backend.trace), "line": line})
            elif line.startswith("EV "):
                self.events.append({"i": len(self.backend.trace), "line": line})
            elif line.startswith("RESULT "):
                return json.loads(line[7:])
            else:
                self.events.append({"i": len(self.backend.trace), "line": "?? " + line})

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self._send("QUIT")
            except (BrokenPipeError, ValueError, OSError):
                pass
            self.proc.wait(timeout=10)

    # ---------------------------------------------------------------- the session opening (contract 5.5)
    def open(self) -> dict:
        self._send("OPEN")
        r = self.serve()
        self.open_result = r
        so = rec.session_open(self.instrument, r.get("startup_readback") or "", self.loaded_reference)
        # the host's own view of the startup readback: the PCAP log's last read_frame group (the backend's store, FAR-ordered)
        host_view = [e for e in self.backend.pcap_log if e.get("pcap") == "read_frame"]
        host_hash = host_view[-1]["target_frames_hash"] if host_view else None
        findings = rec.validate_session_open(so)
        if r.get("status") != 0:
            findings.append(f"the executing side refused to open: {r.get('reason')}")
        if host_hash is not None and host_hash != r.get("startup_readback"):
            findings.append("the executing side's startup readback digest is not the host's view of the frames it was given")
        self.session_open = {"record": so, "findings": findings, "executing_side": r, "host_view_target_frames_hash": host_hash}
        return self.session_open

    # ---------------------------------------------------------------- one transaction
    def transaction(self, kind: str, genome: int, stimulus: list, task: dict | None = None) -> dict:
        """kind: normal | root | inject | a5. `stimulus`: the declared steps (the init step first; `set` steps as the model's
        dicts). `task`: {mask, target, weights, digest} — the TRUSTED task the host scores with; given to the executing
        side as well so that its fitness can be held to the host's."""
        if stimulus[0].get("kind") != "init":
            raise SessionRefusal("the declared stimulus begins with the init step")
        steps = [step_word(s) for s in stimulus[1:]]
        cmd = f"TX {kind} {genome:08x} {len(steps)} " + " ".join(f"{w:07x}" for w in steps)
        if task:
            cmd += f" TASK {task['digest']} {len(task['mask'])} " + " ".join(f"{s} {e} {t} {w}" for (s, e), t, w in zip(task["mask"], task["target"], task["weights"]))
        if self.proc is None or self.proc.poll() is not None:
            raise SessionRefusal("the executing-side program is not running (the transport was interrupted): nothing follows without a ruling")
        nonce_before = self.backend.carrier.nonce
        t_begin = len(self.backend.trace)
        pcap_begin = len(self.backend.pcap_log)
        self._tx_accesses = 0
        self._send(cmd)
        r = self.serve()
        self._tx_accesses = None
        if r.get("status") == 5:
            self.backend.mark("transaction_interrupted")
        self.seq += 1
        seq = self.seq
        evs = self.backend.trace[t_begin:]
        txs = rec.transactions(evs)
        tx_events = txs[0] if txs else [e for e in evs if "op" in e]
        pcap = self.backend.pcap_log[pcap_begin:]
        # the host's links: the notary's commit, the PCAP log's digests (the host's view of what the DMAs carried / delivered)
        commit = next((e["commit"] for e in reversed(self.notary.log) if e.get("genome") == genome and "commit" in e), None)
        env_writes = [e for e in pcap if e.get("pcap") == "envelope_written"]
        reads = [e for e in pcap if e.get("pcap") == "read_frame"]
        groups = [reads[i:i + len(fr.TARGET_FARS)] for i in range(0, len(reads), len(fr.TARGET_FARS))]
        group_hash = [g[0]["target_frames_hash"] if len(g) == len(fr.TARGET_FARS) and len({x["target_frames_hash"] for x in g}) == 1 else None for g in groups]
        cand_staged = env_writes[1]["target_frames_hash"] if len(env_writes) >= 2 else None
        base_staged = env_writes[3]["target_frames_hash"] if len(env_writes) >= 4 else None
        links = {"instrument": self.instrument, "nonce": f"{nonce_before:016x}", "config": config_list(genome)}
        for k, v in (("commit", commit), ("staging_readback_sha256", cand_staged), ("fabric_readback_sha256_pre_event", group_hash[0] if len(group_hash) > 0 else None),
                     ("fabric_readback_sha256_post_event", group_hash[1] if len(group_hash) > 1 else None), ("base_readback_sha256", group_hash[2] if len(group_hash) > 2 else None)):
            if v:
                links[k] = v                                                # a value that does not yet exist is never written (contract 4.2)
        pred = {"kind": "session_root", "seq": None, "close_sha256": None} if kind == "root" or self.prev_x is None else \
            {"kind": ("a5_injection" if self.prev_x["status"] == "injection_open" else "closed"), "seq": self.prev_x["seq"], "close_sha256": rec.sha256_json(self.prev_x)}
        findings = []
        o = f = x = None
        try:
            o = rec.observation(tx_events, links, self.timing, seq=seq, session=self.label, predecessor=pred, declared_stimulus=stimulus)
        except rec.RecordRefusal as e:
            findings.append(f"no observation sealed: {e}")
        if o is not None:
            of = rec.validate_observation(o)
            findings += [f"O: {m}" for m in of]
            if not of and o["status"] == "complete" and task and kind != "root":
                f = rec.fitness(o, task)
                if r.get("has_fitness") and r.get("fitness") != f["fitness"]:
                    findings.append(f"F: the executing side's fitness {r.get('fitness')} is not the host's recomputation {f['fitness']} over the full physical grid")
            try:
                x = rec.transaction_close(tx_events, o, seq=seq, links=links)
            except rec.RecordRefusal as e:
                findings.append(f"no transaction close: {e}")
        # the executing side's digests held to the host's view
        for name, mine, theirs in (("commit", commit, r.get("commit")), ("staged", cand_staged, r.get("staged")), ("pre_event", links.get("fabric_readback_sha256_pre_event"), r.get("pre_event")),
                                   ("post_event", links.get("fabric_readback_sha256_post_event"), r.get("post_event")), ("base_readback", links.get("base_readback_sha256"), r.get("base_readback"))):
            if theirs and mine and theirs != mine:
                findings.append(f"link: the executing side's {name} digest is not the host's view")
        ctx = {"instrument": self.instrument, "session": self.label, "stimulus": stimulus, "config": config_list(genome), "task": task, "task_digest": (task or {}).get("digest"),
               "nonce": links["nonce"], "mechanism": "b", "pulse_clocks": self.timing["pulse"], "base_readback_sha256": self.base_reference,
               "loaded_frames_reference_sha256": self.loaded_reference, "predecessor_close_sha256": pred["close_sha256"], "predecessor_seq": pred["seq"]}
        if o is not None and not rec.validate_observation(o):
            findings += [f"bound: {m}" for m in rec.validate_bound(o, ctx, f, x)]
        entry = {"seq": seq, "kind": kind, "genome": genome, "genome_hex": f"{genome:06x}", "o": o, "f": f, "x": x, "ctx": ctx, "links": links, "firmware": r, "interrupted": self.interrupted if r.get("status") == 5 else None,
                 "findings": findings, "trace_range": [t_begin, len(self.backend.trace)], "pcap_range": [pcap_begin, len(self.backend.pcap_log)],
                 "emulation": {"unmodelled_cells": sum(1 for e in tx_events if e.get("op") == "rd" and e.get("x") is not None)}}
        self.records.append(entry)
        if x is not None and x["status"] in ("closed", "injection_open"):
            self.prev_x = x
        elif x is not None:
            self.prev_x = None                                              # a faulted close: nothing follows until a ruling
        return entry

    # ---------------------------------------------------------------- the evidence
    def chain(self) -> list[str]:
        if self.session_open is None:
            return ["no session_open record"]
        return rec.validate_chain(self.session_open["record"], [{"o": e["o"], "x": e["x"], "ctx": e["ctx"], "f": e["f"]} for e in self.records if e["o"] is not None])

    def write(self) -> dict:
        out = self.out
        (out / "trace.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.backend.trace))
        (out / "pcap_log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.backend.pcap_log))
        (out / "accesses.jsonl").write_text("".join(json.dumps({"op": op, "addr": a, "resp": resp}) + "\n" for op, a, resp in self.backend.accesses))
        (out / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.events))
        (out / "notary_log.json").write_text(json.dumps(self.notary.log, indent=1) + "\n")
        (out / "session_open.json").write_text(json.dumps(self.session_open, indent=1) + "\n")
        for e in self.records:
            d = out / f"tx_{e['seq']:03d}"; d.mkdir(exist_ok=True)
            for k in ("o", "f", "x"):
                if e[k] is not None:
                    (d / f"{k}.json").write_text(json.dumps(e[k], indent=1, sort_keys=True) + "\n")
            (d / "ctx.json").write_text(json.dumps(e["ctx"], indent=1, sort_keys=True) + "\n")
            (d / "links.json").write_text(json.dumps(e["links"], indent=1, sort_keys=True) + "\n")
            (d / "firmware_result.json").write_text(json.dumps(e["firmware"], indent=1, sort_keys=True) + "\n")
            (d / "record.json").write_text(json.dumps({k: e[k] for k in ("seq", "kind", "genome", "genome_hex", "findings", "trace_range", "pcap_range", "emulation", "interrupted")}, indent=1) + "\n")
        chain = self.chain()
        manifest = {"schema": SCHEMA[0], "schema_version": SCHEMA[1], "label": self.label, "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "emulated": True, "standing": "an OFFLINE end-to-end transaction on a host emulation of the carrier and the PCAP path: the executing side's sequence, arithmetic and record production against the real record / validation path — not a physical link, not silicon, not A8",
                    "instrument": self.instrument, "executing_side": {"binary": str(self.binary.relative_to(R)), "sha256": self.instrument["image_sha256"], "build": json.loads((self.binary.parent / "build.json").read_text()) if (self.binary.parent / "build.json").is_file() else None},
                    "loaded_frames_reference_sha256": self.loaded_reference, "base_readback_reference_sha256": self.base_reference,
                    "write_set": json.loads((R / "firmware/b4q/b4q_data.json").read_text()), "timing": self.timing,
                    "hypothesis": {"path": self.hyp.path, "sha256": self.hyp.sha256, "version": self.hyp.version}, "mapping": {"site": self.mapping.site, "certificate": self.mapping.certificate_rel, "certificate_sha256": self.mapping.certificate_sha256},
                    "notary": {"key_id": self.notary.key_id, "contract": "zero tables, no attestation (fixture key)"},
                    "backend": {"power_on": "init" if self.backend.carrier.fab.q and None not in self.backend.carrier.fab.q else "x", "nonce_seed": f"{self.backend.carrier.nonce_seed:016x}", "devc_faults": {f"{k[0]}:{k[1]}": str(v) for k, v in self.backend.devc.faults.items()}},
                    "records": [{"seq": e["seq"], "kind": e["kind"], "genome_hex": e["genome_hex"], "o": e["o"] is not None, "f": e["f"] is not None, "x": e["x"]["status"] if e["x"] else None,
                                 "o_status": e["o"]["status"] if e["o"] else None, "executing_side_status": e["firmware"].get("status"), "phase": e["firmware"].get("phase"), "findings": e["findings"]} for e in self.records],
                    "notary_deny": sorted(f"{g:06x}" for g in self.notary_deny), "interrupted": self.interrupted,
                    "chain_findings": chain, "accesses": len(self.backend.accesses), "trace_events": len(self.backend.trace)}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
        return manifest
