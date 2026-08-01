"""Shared U-Boot serial plumbing for board runs.

Two boards can host this bitstream, and they do NOT share a prompt string:

  EBAZ4205 (miner NAND board, original vendor U-Boot)  ->  ``zynq-uboot>``
  EBAZ4203 (TF-card board, mainline U-Boot 2026.04-rc5) ->  ``Zynq>``

Both expose the same console symlink ``/dev/ebaz-uart`` (the udev rule matches
any CH340), so the port default is unchanged and only the prompt has to become
board-agnostic.  PROMPT_RE matches either spelling, which keeps every 4205
golden run reproducible while letting the same scripts drive the 4203.

Override the port with ``--port`` where offered, or the AUTOEHW_PORT env var.
"""

import os
import re
import time

PORT = os.environ.get("AUTOEHW_PORT", "/dev/ebaz-uart")
BAUD = int(os.environ.get("AUTOEHW_BAUD", "115200"))

# 4205 vendor U-Boot | 4203 mainline U-Boot
PROMPT_RE = re.compile(rb"(?:zynq-uboot|Zynq)>")

MD_RE = re.compile(rb"^[0-9a-fA-F]{8}:\s+([0-9a-fA-F]{8})", re.MULTILINE)


def read_until(ser, pat, timeout):
    """Read until ``pat`` (compiled regex) matches or ``timeout`` elapses."""
    buf, t0 = b"", time.time()
    while time.time() - t0 < timeout:
        chunk = ser.read(512)
        if chunk:
            buf += chunk
            if pat.search(buf):
                break
    return buf


def ub_cmd(ser, line, timeout=1.5):
    """Send one U-Boot command line and return everything up to the prompt."""
    ser.reset_input_buffer()
    ser.write(line.encode("ascii") + b"\r")
    return read_until(ser, PROMPT_RE, timeout)


def sync_prompt(ser, timeout=2.0):
    """Send a bare CR to flush junk and land on a known prompt.

    Both boards need this: the 4205 leaves a residual ``d`` from the autoboot
    hammer, and the 4203 takes a burst of garbage into its RX at power-on.
    """
    return ub_cmd(ser, "", timeout)


def md1(ser, addr, timeout=1.5):
    """`md <addr> 1` -> int, or raise if the reply cannot be parsed."""
    out = ub_cmd(ser, f"md 0x{addr:08x} 1", timeout)
    match = MD_RE.search(out)
    if not match:
        raise RuntimeError(f"could not parse md output for 0x{addr:08x}: {out!r}")
    return int(match.group(1), 16)


def mw1(ser, addr, value, timeout=1.5):
    ub_cmd(ser, f"mw 0x{addr:08x} 0x{value:08x} 1", timeout)
