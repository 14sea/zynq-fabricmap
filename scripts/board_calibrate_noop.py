#!/usr/bin/env python3
"""Erratum 001 step 1: one complete NO-OP transaction, and nothing else.

`docs/claimb_erratum_001_static_routes.md` fixes the order of the first device writes,
because the one assumption that cannot be settled off the board is whether a self-hosted
ICAP path is stable while it rewrites the very static-route bits it is running on. So the
first thing that touches the fabric is a candidate that changes nothing:

  1. a complete NO-OP transaction — all 15 frames equal the pinned base;
  2. required: guard alive, zero faults, readback equal to the base, scorer NOT armed;
  3. only then the pre-selected known-answer mutation;
  4. readback, score, restore base, post-baseline.

**Steps 3 and 4 are not in this file.** It runs step 1, checks step 2, writes the evidence
and stops. A no-op that wedges the device, faults the guard, or reads back different in a
single bit has falsified the assumption the whole carrier rests on: that is a STOP, not a
retry and not a rule loosened to explain it.

What this deliberately does NOT do
----------------------------------
* **it never arms the scorer.** `CTRL_ARM` is not written by any code path in this
  repository, and a test asserts that rather than the docstring.
* **it does not write a `run_log`.** A run log is the record of an ARM of round 1, with a
  budget §6 cannot freeze until a measured calibration exists. Filing the calibration as a
  run of the experiment would be exactly that circularity, in a file format. The evidence
  here is its own document.
* **it changes nothing that survives a power cycle.** No `saveenv`, no flash write. The
  carrier is loaded volatile through `fpga loadb`, and the environment is untouched.

The order of the phases is the order it is, for a reason
--------------------------------------------------------
Setting the clock and loading the carrier need the tty to themselves — `sb` is a separate
process — so they run BEFORE the session opens. Identity is then verified on the session
that performs the write, after every disruptive step is finished, and the payload is proved
byte-for-byte in DRAM inside that same session. A board swapped at any point fails both.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402
import base64  # noqa: E402
import board_carrier_exec as ex  # noqa: E402
import board_serial as bs  # noqa: E402
import board_uboot_axi as axi  # noqa: E402
import gate_board_identity as ident  # noqa: E402
import run_log  # noqa: E402

TOOL_VERSION = "board_calibrate_noop.py/1.0.0"

DEFAULT_RUN = REPO_ROOT / "gate_runs/claimb_round1_carrier_2026_08_13_erratum006"


class CalibrationStop(Exception):
    """A standing stop condition. Nothing in this file catches one to carry on."""


def noop_candidate(manifest: dict, carrier_bit: Path) -> dict[int, list[int]]:
    """The 12 target frames, exactly as they are in the carrier that will be loaded.

    Read from the bitstream and then required to equal the manifest's pinned words. They
    should be the same thing twice — the manifest was built from this bitstream — and if
    they are not, the run has no base and there is nothing to be no-op *against*.
    """
    frames = bf.parse_frames(carrier_bit)["frames"]
    pinned = {int(record["far"], 16): [int(word, 16) for word in record["words"]]
              for record in manifest["frames"]}
    candidate: dict[int, list[int]] = {}
    for record in manifest["frames"]:
        far = int(record["far"], 16)
        if far not in frames:
            raise CalibrationStop(f"FAR {far:#010x} is not in the carrier bitstream")
        if list(frames[far]) != pinned[far]:
            raise CalibrationStop(
                f"FAR {far:#010x} differs between the carrier bitstream and the manifest's "
                "pinned words — the base is not one thing")
        if record["role"] == "target":
            candidate[far] = list(frames[far])
    return candidate



class InstrumentedTransport:
    """Records WHEN the calibration did each thing, and adds nothing to the wire.

    Seven runs of this script have stopped at the same read, but they are not seven repeats:
    one used the pre-shim carrier, which is erratum 002 itself, and of the six on the exact
    pinned carrier only the last ran on the current source. **One clean comparable stall**,
    then, and five historical and partly comparable events. Every account of the gap between
    the load and that read has been reconstructed from outside — from file mtimes, from
    timing the host gate in another process — and one of those was simply wrong: the
    host-only gating was supposed to be some thirty seconds and it measures two.

    So the calibration records its own timeline. **Strictly its own**: this wrapper forwards
    one command in and one command out, and issues nothing of its own. An earlier version
    also read the PS registers before the first carrier command, which would have put extra
    traffic on the wire ahead of the very read under investigation — and the path that
    succeeds also reads PS first, so a pass would not have separated the reading from the
    recording. Timing is free; traffic is not.
    """

    def __init__(self, inner, record: dict):
        self.inner = inner
        self.commands: list[dict] = []
        self.started = time.monotonic()
        self.markers: list[dict] = []
        record["instrumentation"] = {
            "adds_no_commands": "this wrapper forwards 1:1 and issues nothing of its own",
            "commands": self.commands,
            "markers": self.markers,
        }

    def mark(self, name: str) -> None:
        """A host-side instant, so a host-only interval can be read off the timeline."""
        self.markers.append({"marker": name,
                             "at_s": round(time.monotonic() - self.started, 4)})

    def command(self, line: str, timeout: float = 1.5) -> bytes:
        started = time.monotonic()
        entry: dict = {
            "command": line,
            "start_s": round(started - self.started, 4),
            "timeout_s": timeout,
        }
        self.commands.append(entry)
        try:
            reply = self.inner.command(line, timeout)
        except BaseException as raised:              # noqa: BLE001 - recorded, then re-raised
            entry["end_s"] = round(time.monotonic() - self.started, 4)
            entry["elapsed_s"] = round(entry["end_s"] - entry["start_s"], 4)
            entry["exception"] = type(raised).__name__
            raise
        entry["end_s"] = round(time.monotonic() - self.started, 4)
        entry["elapsed_s"] = round(entry["end_s"] - entry["start_s"], 4)
        rebooted = bool(bs.BOOT_BANNER_RE.search(reply))
        entry["rebooted"] = rebooted
        entry["prompt_returned"] = bool(axi.PROMPT_RE.search(reply)) and not rebooted
        # The whole reply, whenever anything is odd. Truncating to a 400-character tail is
        # how a `data abort` message went missing from the one record that needed it.
        entry["raw"] = reply.decode("ascii", "replace")
        if entry["prompt_returned"] and not rebooted:
            entry["raw"] = entry["raw"][-400:]
        else:
            entry["raw_b64"] = base64.b64encode(reply).decode()
        return reply

    def __getattr__(self, name):
        return getattr(self.inner, name)


def phase_setup(port: str, carrier_bit: Path, expected_sha: str) -> dict:
    """Pin FCLK0, then load the published carrier. Both need the tty to themselves."""
    actual = hashlib.sha256(carrier_bit.read_bytes()).hexdigest()
    if actual != expected_sha:
        raise CalibrationStop(
            f"the carrier bitstream on disk is {actual}, the run bundle pins {expected_sha}")

    steps = []
    for argv, what in (
        ([sys.executable, str(REPO_ROOT / "scripts/board_set_fclk50.py"), "--port", port],
         "FCLK0 = 50 MHz"),
        ([sys.executable, str(REPO_ROOT / "scripts/board_uboot_fpga_load.py"),
          "--port", port, "--bit", str(carrier_bit), "--op", "loadb",
          "--require-unconfigured"],
         "fpga loadb of the published carrier, onto an empty PL"),
    ):
        started = time.time()
        done = subprocess.run(argv, capture_output=True, text=True)
        steps.append({
            "step": what,
            "argv": argv[1:],
            "returncode": done.returncode,
            "elapsed_s": round(time.time() - started, 1),
            "stdout_tail": done.stdout[-800:],
            "stderr_tail": done.stderr[-400:],
        })
        if done.returncode != 0:
            raise CalibrationStop(f"{what} failed: {done.stderr.strip() or done.stdout[-300:]}")
    marker = None
    for step in steps:
        found = re.search(r"\[plmark\] ([0-9a-f]+)", step["stdout_tail"])
        if found:
            marker = found.group(1)
    if marker is None:
        raise CalibrationStop(
            "the loader did not report a `plmark`, so a restart between the load and the "
            "write could not be detected — and a restart clears the PL")
    return {"carrier_sha256": actual, "plmark": marker, "steps": steps}


def check_the_no_op(candidate: dict[int, list[int]], manifest: dict,
                    readback: dict[int, list[int]]) -> dict:
    """Erratum 001 step 2, as arithmetic over the bytes that actually came back."""
    pinned = {int(record["far"], 16): [int(word, 16) for word in record["words"]]
              for record in manifest["frames"]}

    if set(readback) != set(pinned):
        raise CalibrationStop(
            f"{len(readback)} FARs read back, the manifest pins {len(pinned)}")

    differing = [far for far in sorted(readback) if readback[far] != pinned[far]]
    if differing:
        detail = []
        for far in differing[:3]:
            bad = [i for i, (a, b) in enumerate(zip(readback[far], pinned[far])) if a != b]
            detail.append(f"{far:#010x}: {len(bad)} word(s), first at index {bad[0]}")
        raise CalibrationStop(
            "STOP — the no-op did not read back identically. "
            f"{len(differing)} of {len(pinned)} frames differ ({'; '.join(detail)}). "
            "This falsifies the assumption the carrier rests on: do not retry, do not "
            "loosen the rule, do not proceed to the known-answer mutation.")

    candidate_hash = run_log.frames_hash(candidate)
    readback_targets = {far: readback[far] for far in candidate}
    return {
        "frames_compared": len(pinned),
        "frames_differing": 0,
        "candidate_sha256": candidate_hash,
        "readback_sha256": run_log.frames_hash(readback_targets),
        "readback_all_frames_sha256": run_log.frames_hash(readback),
        "readback_matches": run_log.frames_hash(readback_targets) == candidate_hash,
    }


def check_the_end_state(transaction: dict) -> list[dict]:
    """The final status and the per-envelope readback telemetry, as stop conditions.

    Split out of `main` so it can be exercised without a board. A check that only ever runs
    against hardware is a check nobody has seen fail.
    """
    final = transaction["status_after"]
    for flag, must_be in (("fault", False), ("configuration_valid", True),
                          ("recovery_required", False), ("scorer_armed", False),
                          ("scorer_busy", False), ("scorer_done", False)):
        if final[flag] is not must_be:
            raise CalibrationStop(
                f"STOP — the final status has {flag}={final[flag]}, required {must_be}")

    # -- the readback telemetry, per envelope (erratum 004).
    #
    # An envelope whose probe never established the read path reports
    # `rb_latency_valid=0`, and whatever it then "verified" was verified against whatever
    # the engine happened to read instead. A run that passed every other check with an
    # invalid latency would be a run whose readback nobody can account for, so this is a
    # stop and not a note. It judges only what the engine REPORTS: the measured value is
    # telemetry and no threshold is applied to it.
    latency = transaction.get("readback_latency")
    if not latency or len(latency) != axi.ENVELOPES:
        raise CalibrationStop(
            f"STOP — the transaction recorded {len(latency or [])} readback-latency "
            f"entries; one per envelope means {axi.ENVELOPES}")
    invalid = [entry for entry in latency if not entry["valid"]]
    if invalid:
        raise CalibrationStop(
            "STOP — the readback probe never named the device on envelope(s) "
            f"{[entry['envelope'] for entry in invalid]}: rb_latency_valid=0, so the read "
            "path was not established for them and no frame they report can be accounted "
            "for")
    return latency


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # Nothing here can relax a requirement: which run, which cable, where to file the
    # evidence. There is no --force, no --skip and no --allow.
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--port", default="/dev/ebaz-uart")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    record: dict = {
        "tool": TOOL_VERSION,
        "what": "erratum 001 step 1 — the complete no-op transaction",
        "run_dir": str(args.run_dir.relative_to(REPO_ROOT))
        if args.run_dir.is_relative_to(REPO_ROOT) else str(args.run_dir),
        "started_at": time.time(),
    }

    try:
        # -- the published authority, before anything is touched.
        authority = ex.PublishedCarrierAuthority.load(args.run_dir)
        manifest = authority.manifest_copy()
        bundle = json.loads((args.run_dir / "carrier_run.json").read_text("utf-8"))
        record["authority"] = {
            "manifest_sha256": authority.manifest_sha256,
            "run_id": bundle.get("run_id"),
        }

        candidate = noop_candidate(manifest, args.run_dir / "carrier.bit")
        payload = ex.SealedPayload(ex.build_sequence_bytes(manifest, candidate))
        record["payload"] = {"bytes": len(payload), "sha256": payload.sha256}

        # -- setup, outside the session: both steps need the tty to themselves.
        record["setup"] = phase_setup(
            args.port, args.run_dir / "carrier.bit",
            bundle["artifacts"]["carrier.bit"]["sha256"])

        # -- the session that verifies the board is the session that writes to it.
        transport = InstrumentedTransport(ident.SerialTransport(args.port), record)
        try:
            session = ident.BoardSession(transport)
            identity = session.verify_identity("content")
            record["identity"] = identity["parsed"]
            # BEFORE anything touches the carrier. A restart since the load clears the PL,
            # and asking the PL about it stalls the CPU.
            axi.same_boot(transport, record["setup"]["plmark"])
            # The host-only gate runs between here and the first carrier command,
            # so this marker and that command's start_s bracket it exactly.
            transport.mark("before run_candidate_on_board")
            result = ex.run_candidate_on_board(payload, authority, session)
        except axi.AxiRefusal:
            # A spinning wait loop still owns the console; a stalled AXI access does not
            # answer this, and that difference is worth having in the record.
            record["interrupt_reply"] = transport.interrupt().decode("ascii", "replace")[-200:]
            raise
        finally:
            transport.close()

        transaction = result["transaction"]
        record["transaction"] = {
            key: value for key, value in transaction.items() if key != "readback_frames"}
        record["check"] = check_the_no_op(candidate, manifest, transaction["readback_frames"])

        record["readback_latency"] = check_the_end_state(transaction)

        record["verdict"] = "NO-OP CALIBRATION PASSED"
    except (CalibrationStop, ex.TransportRefusal, axi.AxiRefusal,
            ident.IdentityError) as stop:
        record["verdict"] = "STOP"
        record["stop_reason"] = f"{type(stop).__name__}: {stop}"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"STOP: {stop}", file=sys.stderr)
        print(f"  evidence: {args.out}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    check = record["check"]
    print("NO-OP CALIBRATION PASSED")
    print(f"  {check['frames_compared']} frames read back, 0 differing")
    print(f"  candidate {check['candidate_sha256'][:16]}… == readback "
          f"{check['readback_sha256'][:16]}…")
    print(f"  configuration_valid=1 recovery_required=0 fault=0 scorer_armed=0")
    print("  readback latency, per envelope: " + ", ".join(
        f"env{entry['envelope']}={entry['words']}w" for entry in record["readback_latency"]))
    print(f"  evidence: {args.out}")
    print("  NEXT is erratum 001 step 3, the pre-selected known-answer mutation — "
          "which this tool does not do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
