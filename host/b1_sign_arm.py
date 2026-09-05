#!/usr/bin/env python3
"""The B1 gate-signer principal — a SUCCESSOR of zynq-psoracle/host/sign_arm.py under the B1
noninterference contract (docs/b1_carrier_contract.md). Runs as a separate OS user (D4).

Reads one JSON request on stdin and answers on stdout. Operations:
  {"op": "sign_genome", genome, nonce}  → the signer derives the canonical frames itself
     (the instrument's p3_genome), runs ITS OWN gate (the instrument's p3_gate — the
     fabricmap candidate rules verbatim: the whitelist, the flush frames, the ECC) and signs
     ONLY a writable candidate: commit ‖ TWELVE ZERO TABLE WORDS ‖ nonce. It computes NO
     expected tables — the semantic oracle's entry points are disarmed in this process before
     any signing — so nothing the host signs attests what the fabric should read. An unwritable genome returns {"refused":
     kinds} with exit 0 (a gate refusal is data).
  {"op": "probe"}                       → key_id and the OS user (the boundary verifier)
  {"op": "provision", "execute", ["ruling"]} → delegated verbatim to the instrument's signer
     module (the write-once key over JTAG; needs a `provisioning P3-K` ruling to execute).
It is the only program that opens K; the runner never imports KeyHolder. Refusals are a
non-zero exit with the reason on stderr. Key words never appear in any answer.

Deployment note (package §6): the D4 sudoers line names the instrument's sign_arm.py path;
running THIS script as the signer user needs the owner to extend that line to this path —
a provisioning step recorded in the package, never done by a runner.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

ZERO_TABLES = [0] * 6
PROVISION_RULING_TEXT = "provisioning P3-K"


def _disarm_semantic_oracle() -> None:
    """The instrument's genome codec imports the semantic oracle module transitively; the
    B1 signer must never USE it. Both entry points are replaced by a refusal in this
    process, so a call — from any path — is a signer refusal, not a silent attestation."""
    import p3_oracle as po

    def refuse(*a, **k):
        raise RuntimeError("the B1 signer must not compute semantic expected tables (docs/b1_carrier_contract.md)")
    po.expected_tables = refuse
    po.predict_scores = refuse


def sign_genome(holder, genome_hex: str, nonce_hex: str) -> dict:
    import p3_gate as g
    import p3_genome as gn
    from validators import signer as sg
    _disarm_semantic_oracle()
    manifest = g.load_manifest()
    frames = gn.frames_from_genome(gn.from_hex(genome_hex), manifest)
    verdict = g.gate(g.build_streams(frames, manifest), manifest)
    if not verdict["writable"]:
        return {"refused": {"finding_kinds": sorted({f["kind"] for f in verdict["findings"]})}}
    payload = sg.sign_arm(holder, verdict, bytes.fromhex(verdict["candidate_sha256"]),
                          ZERO_TABLES, int(nonce_hex, 16).to_bytes(8, "little"))
    return {"commit": verdict["candidate_sha256"], "sequence_sha256": verdict["sequence_sha256"],
            "expected_tables": [f"{t:016x}" for t in ZERO_TABLES], "tag": payload.tag.hex(),
            "words": payload.words(), "key_id": holder.key_id, "contract": "b1-nonsemantic-v1"}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: b1_sign_arm.py <key_path>  (request JSON on stdin)", file=sys.stderr)
        return 2
    req = json.load(sys.stdin)
    try:
        inst.bind(inst.DEFAULT_ROOT, require_git=False)     # the signer user may not run git here
        from validators import signer as sg
        holder = sg.KeyHolder(Path(sys.argv[1]))
        op = req.get("op", "sign")
        if op == "probe":
            json.dump({"key_id": holder.key_id, "user": __import__("getpass").getuser(), "contract": "b1-nonsemantic-v1"}, sys.stdout)
            return 0
        if op == "sign_genome":
            json.dump(sign_genome(holder, req["genome"], req["nonce"]), sys.stdout)
            return 0
        if op == "provision":
            import sign_arm as instrument_signer          # the instrument's provisioning path, verbatim
            execute = bool(req.get("execute"))
            if execute:
                if not req.get("ruling"):
                    raise sg.SignerRefusal(f"provisioning is a board action: no ruling {PROVISION_RULING_TEXT!r} given")
                import board_session as bsn
                import pcap_probe_runner as pr
                try:
                    pr._parse_ruling(Path(req["ruling"]), text=PROVISION_RULING_TEXT)
                except bsn.SessionRefusal as exc:
                    raise sg.SignerRefusal(f"ruling refused: {exc}") from None
                instrument_signer.claim_provision_ruling(Path(req["ruling"]))
            import provision_key_jtag as pk
            res = pk.run(holder._k, execute)
            json.dump({"provision": res, "key_id": holder.key_id}, sys.stdout)
            return 0 if res.get("rc", 0) == 0 else 1
        raise sg.SignerRefusal(f"op {op!r} is not offered by the B1 signer (no host-attested 'sign')")
    except Exception as exc:  # noqa: BLE001 — every refusal is a non-zero exit with the reason
        print(f"signer refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
