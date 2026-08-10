#!/usr/bin/env python3
"""Refuse to write unless this very session proved it is talking to the right board.

`docs/board_roles.md` has said since 2026-08-02 that board identity must be a
machine-checkable fact rather than a memory. This turns that prose into a gate.

Four things are structural here, not stylistic
----------------------------------------------

**1. There is no override.** No `--force`, no `--allow-any-board`, no environment
variable. The required identity is module-level constants, so widening it is a source
edit that shows up in a diff and in review — not a flag someone can add at 2am. A test
asserts the argument parser exposes nothing that could relax a requirement.

**2. Identity and the write share one open session, and one EPOCH.** `BoardSession` owns
the transport. Verifying identity and then re-resolving `/dev/ebaz-uart` for the write
would leave a window in which the symlink moves to another CH340, or the boards are
swapped — and the write would land on a board that never passed. `authorise_write()`
refuses unless *this* object holds a verification, so a caller cannot construct one and
use another.

An authorisation is additionally scoped to an **epoch**. Any transport reopen, timeout,
UART disconnect, prompt-mode change, soft reset, power cycle or recovery calls
`note_disruption()`, which increments the epoch and clears the identity; the next write
must re-verify. Within one stable epoch a run may write many candidates without asking
U-Boot again — an evolution loop cannot afford a `printenv` per candidate — but an
authorisation never survives the event that could have changed which board is on the wire.
That is the stale-authorisation failure in its general form: the first version of this
gate kept an identity across a *failed* re-verification, and only a verify-swap-verify
sequence exposed it.

**3. Silence, duplication and ambiguity are refusals, not defaults.** A missing variable,
two assignments, an unparseable reply and a timeout all refuse. `board_serial.md1` takes
the FIRST regex match, which is fine for a scratch poke and wrong here: an echoed command
or a stale buffer would let a value from an earlier command be read as this one's answer.
`read_register` requires exactly one match.

**4. This gate is not the write authority.** It is the host's half. The board-side fixed
FAR/FDRI guard must independently refuse an out-of-range sequence, because a host that has
been edited, bypassed or simply not run cannot be the only thing standing between a
candidate and the fabric. Two independent refusals, neither trusting the other.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_serial as bs  # noqa: E402
import board_set_fclk50 as fclk  # noqa: E402

TOOL_VERSION = "gate_board_identity.py/1.0.0"

# ---------------------------------------------------------------- frozen requirements
# Constants, deliberately not arguments. Changing what counts as an acceptable board is a
# source edit, reviewable in a diff.
REQUIRED_BOARDID = "17A6"
REQUIRED_ROLE = "verify"
ROLES_FOR_CONTENT_CLASS = frozenset({"verify", "sacrificial"})
ROLES_FOR_ROUTING_CLASS = frozenset({"sacrificial"})

SLCR_PSS_IDCODE = 0xF8000530
# The JTAG/PSS IDCODE of XC7Z010 is 0x13722093. Bits 31:28 are the silicon revision and
# legitimately differ between dies, so they are masked; everything else must match.
IDCODE_MASK = 0x0FFFFFFF
REQUIRED_IDCODE = 0x13722093 & IDCODE_MASK

REQUIRED_FCLK0_MHZ = 50.0
FCLK0_TOLERANCE_MHZ = 0.5

# What this gate can actually interrogate. `printenv` and `md` are U-Boot commands, so a
# verification performed here is a statement about a U-BOOT control plane and nothing
# else. Booting Linux replaces the control plane; the identity does not travel across that
# boundary, and a Linux-side executor (/dev/mem, HWICAP) must establish its own — which
# this module does not implement, so it refuses rather than pretending.
CONTROL_PLANE = "uboot"
KNOWN_CONTROL_PLANES = frozenset({"uboot", "linux"})

PS_CLK_MHZ = 33.333333

ENV_LINE_RE = re.compile(rb"^([A-Za-z_][A-Za-z0-9_]*)=(.*?)\s*$", re.MULTILINE)
MD_LINE_RE = re.compile(rb"^[0-9a-fA-F]{8}:\s+([0-9a-fA-F]{8})", re.MULTILINE)


class IdentityError(Exception):
    """A refusal. Every path out of this module that is not a pass raises this."""


# ------------------------------------------------------------------------- transports


class SerialTransport:
    """Owns one open serial handle for the whole session.

    The port path is resolved once, at open, and recorded. Nothing here re-resolves it:
    that is the window this class exists to close.
    """

    def __init__(self, port: str = bs.PORT, baud: int = bs.BAUD):
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - board-host dependency
            raise IdentityError("pyserial is required for board sessions") from exc
        self.requested_port = port
        self.resolved_port = os.path.realpath(port)
        try:
            stat = os.stat(self.resolved_port)
        except OSError as exc:
            raise IdentityError(f"cannot stat {port}: {exc}") from exc
        self.device_id = f"{os.major(stat.st_rdev)}:{os.minor(stat.st_rdev)}"
        self._serial = serial.Serial(self.resolved_port, baud, timeout=0.1)
        bs.sync_prompt(self._serial)

    def command(self, line: str, timeout: float = 1.5) -> bytes:
        return bs.ub_cmd(self._serial, line, timeout)

    def descriptor(self) -> dict:
        return {
            "requested_port": self.requested_port,
            "resolved_port": self.resolved_port,
            "device_id": self.device_id,
        }

    def close(self) -> None:
        self._serial.close()


# ---------------------------------------------------------------------- strict parsing


def parse_env_value(reply: bytes, name: str) -> str:
    """Exactly one assignment of `name`, or a refusal.

    U-Boot echoes the command line, so a lax parser can read the echo as the answer; and a
    stale buffer can carry a previous variable's value. Both are ambiguity, and ambiguity
    about which board this is must never resolve to a value.
    """
    matches = [
        value.decode("ascii", "replace")
        for key, value in ENV_LINE_RE.findall(reply)
        if key.decode("ascii", "replace") == name
    ]
    if not matches:
        raise IdentityError(
            f"{name} is not set on this board — a board that does not answer with a role "
            "is treated as 'reference', i.e. refused"
        )
    if len(matches) > 1:
        raise IdentityError(
            f"{name} appears {len(matches)} times in one reply ({matches!r}) — ambiguous"
        )
    value = matches[0].strip()
    if not value:
        raise IdentityError(f"{name} is set but empty")
    return value


def read_register(transport, addr: int, timeout: float = 1.5) -> int:
    """`md <addr> 1` with exactly one parsed word, or a refusal."""
    reply = transport.command(f"md 0x{addr:08x} 1", timeout)
    matches = MD_LINE_RE.findall(reply)
    if not matches:
        raise IdentityError(
            f"no readable md output for {addr:#010x} (timeout or unparseable): {reply!r}"
        )
    if len(matches) > 1:
        raise IdentityError(
            f"{len(matches)} md lines for a single-word read of {addr:#010x} — ambiguous"
        )
    return int(matches[0], 16)


# -------------------------------------------------------------------------- the gate


# Events that end an epoch. Named rather than free-form so a run log cannot record a
# disruption the reader has to interpret, and so adding a new one is a source change.
DISRUPTIONS = frozenset(
    {
        "transport_reopen",
        "timeout",
        "uart_disconnect",
        "prompt_mode_change",
        "soft_reset",
        "power_cycle",
        "recovery",
    }
)


class BoardSession:
    """One open transport, one identity, one epoch — and no write without all three."""

    def __init__(self, transport):
        self.transport = transport
        self._identity: dict | None = None
        self.epoch = 0
        self.disruptions: list[dict] = []
        self._prompt_mode: str | None = None

    # -- epoch ------------------------------------------------------------------

    def note_disruption(self, kind: str, detail: str = "") -> int:
        """End the current epoch. Returns the new epoch number.

        Clearing the identity here rather than at the next write is deliberate: the
        window between the event and the next authorisation is exactly where a stale
        authorisation would otherwise be usable.
        """
        if kind not in DISRUPTIONS:
            raise IdentityError(
                f"unknown disruption {kind!r} — it must be one of {sorted(DISRUPTIONS)}, "
                "so a run log never carries an event a reader has to interpret"
            )
        self.epoch += 1
        self._identity = None
        self.disruptions.append(
            {"epoch_ended": self.epoch - 1, "kind": kind, "detail": detail,
             "at": time.time()}
        )
        return self.epoch

    def observe_prompt(self, prompt: str) -> None:
        """A changed prompt means a changed control plane; that ends the epoch.

        `zynq-uboot>` is the 4205's vendor U-Boot and `Zynq>` the 4203's mainline build,
        so a change is either a different board or a different firmware — and a Linux
        shell prompt means U-Boot is gone entirely.
        """
        if self._prompt_mode is None:
            self._prompt_mode = prompt
            return
        if prompt != self._prompt_mode:
            previous, self._prompt_mode = self._prompt_mode, prompt
            self.note_disruption(
                "prompt_mode_change", f"{previous!r} -> {prompt!r}"
            )

    # -- identity ---------------------------------------------------------------

    def verify_identity(self, bit_class_tier: str = "content") -> dict:
        raw: dict[str, str] = {}
        findings: list[str] = []

        def record(cmd: str, reply: bytes) -> bytes:
            raw[cmd] = reply.decode("ascii", "replace")
            return reply

        started = time.time()

        boardid_reply = record("printenv boardid", self.transport.command("printenv boardid"))
        role_reply = record("printenv role", self.transport.command("printenv role"))
        boardid = parse_env_value(boardid_reply, "boardid")
        role = parse_env_value(role_reply, "role")

        if boardid != REQUIRED_BOARDID:
            findings.append(
                f"boardid is {boardid!r}, this run is preregistered for {REQUIRED_BOARDID!r}"
            )
        if role != REQUIRED_ROLE:
            findings.append(f"role is {role!r}, expected {REQUIRED_ROLE!r}")

        allowed = (
            ROLES_FOR_ROUTING_CLASS if bit_class_tier == "routing"
            else ROLES_FOR_CONTENT_CLASS
        )
        if role not in allowed:
            findings.append(
                f"role {role!r} may not host a {bit_class_tier}-class write "
                f"(allowed: {sorted(allowed)})"
            )

        idcode_raw = read_register(self.transport, SLCR_PSS_IDCODE)
        record(f"md {SLCR_PSS_IDCODE:#010x} 1", str(idcode_raw).encode())
        if (idcode_raw & IDCODE_MASK) != REQUIRED_IDCODE:
            findings.append(
                f"PSS_IDCODE {idcode_raw:#010x} (masked {idcode_raw & IDCODE_MASK:#010x}) "
                f"is not XC7Z010 ({REQUIRED_IDCODE:#010x})"
            )

        mhz, pll, div0, div1 = self.read_fclk0()
        if abs(mhz - REQUIRED_FCLK0_MHZ) > FCLK0_TOLERANCE_MHZ:
            findings.append(
                f"FCLK0 is {mhz:.2f} MHz, expected {REQUIRED_FCLK0_MHZ} — decoded from the "
                f"PLLs ({pll:.1f}/{div0}/{div1}), never from a remembered constant"
            )

        identity = {
            "tool": TOOL_VERSION,
            "transport": self.transport.descriptor(),
            "parsed": {
                "boardid": boardid,
                "role": role,
                "pss_idcode": f"{idcode_raw:#010x}",
                "fclk0_mhz": round(mhz, 3),
                "fclk0_pll_mhz": round(pll, 1),
                "fclk0_divisors": [div0, div1],
            },
            "raw_replies": raw,
            "requirements": {
                "boardid": REQUIRED_BOARDID,
                "role": REQUIRED_ROLE,
                "idcode_masked": f"{REQUIRED_IDCODE:#010x}",
                "fclk0_mhz": REQUIRED_FCLK0_MHZ,
                "bit_class_tier": bit_class_tier,
            },
            "elapsed_s": round(time.time() - started, 3),
            "epoch": self.epoch,
            "control_plane": CONTROL_PLANE,
            "findings": findings,
        }

        if findings:
            self._identity = None
            raise IdentityError(
                "board identity refused: " + "; ".join(findings),
            )

        self._identity = identity
        return identity

    def read_fclk0(self) -> tuple[float, float, int, int]:
        pll_by_src = {
            0: fclk.pll_mhz(read_register(self.transport, fclk.IO_PLL_CTRL), PS_CLK_MHZ),
            2: fclk.pll_mhz(read_register(self.transport, fclk.ARM_PLL_CTRL), PS_CLK_MHZ),
            3: fclk.pll_mhz(read_register(self.transport, fclk.DDR_PLL_CTRL), PS_CLK_MHZ),
        }
        ctrl = read_register(self.transport, fclk.FPGA0_CLK_CTRL)
        return fclk.decode_fclk(ctrl, pll_by_src)

    # -- the interlock ----------------------------------------------------------

    @property
    def identity(self) -> dict | None:
        return self._identity

    def authorise_write(self, control_plane: str = CONTROL_PLANE) -> dict:
        """The only door to a device write: this session, this epoch, this control plane.

        `control_plane` is what the *executor* will use. Verifying over U-Boot and then
        writing from Linux is the boundary this argument exists to refuse: `printenv` and
        `md` say nothing about a running kernel, the board may have rebooted into a
        different image, and /dev/mem is a different mechanism with a different guard. A
        Linux-side executor needs a Linux-side verification, which this module does not
        implement.
        """
        if control_plane not in KNOWN_CONTROL_PLANES:
            raise IdentityError(
                f"unknown control plane {control_plane!r}; expected one of "
                f"{sorted(KNOWN_CONTROL_PLANES)}"
            )
        if self._identity is None:
            raise IdentityError(
                "no verified identity on this session — verify_identity() must succeed on "
                "the SAME open session that performs the write, so the port cannot be "
                "re-resolved to another board in between"
            )
        if self._identity.get("epoch") != self.epoch:
            raise IdentityError(
                f"identity was verified in epoch {self._identity.get('epoch')} but the "
                f"session is now in epoch {self.epoch} — re-verify before writing"
            )
        if self._identity.get("control_plane") != control_plane:
            raise IdentityError(
                f"identity was established over the "
                f"{self._identity.get('control_plane')!r} control plane but the write "
                f"would run over {control_plane!r} — booting Linux ends the U-Boot "
                "authorisation, and a Linux-side executor needs its own verification"
            )
        return self._identity


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # Deliberately minimal: --port selects which cable to talk over, and --out where to
    # record. Neither can relax a requirement. There is no flag that makes a wrong board
    # acceptable, and adding one would have to survive review.
    ap.add_argument("--port", default=bs.PORT)
    ap.add_argument("--baud", type=int, default=bs.BAUD)
    ap.add_argument("--tier", choices=["content", "routing"], default="content")
    ap.add_argument("--out", type=Path, help="write the identity record here")
    args = ap.parse_args()

    try:
        transport = SerialTransport(args.port, args.baud)
    except IdentityError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    try:
        session = BoardSession(transport)
        identity = session.verify_identity(args.tier)
    except IdentityError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    finally:
        transport.close()

    if args.out:
        args.out.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    parsed = identity["parsed"]
    print(
        f"BOARD ACCEPTED  boardid={parsed['boardid']} role={parsed['role']} "
        f"idcode={parsed['pss_idcode']} fclk0={parsed['fclk0_mhz']} MHz"
    )
    print(f"  session: {identity['transport']['resolved_port']} ({identity['transport']['device_id']})")
    print("  this gate is the host half; the board-side FAR/FDRI guard refuses independently")
    return 0


if __name__ == "__main__":
    sys.exit(main())
