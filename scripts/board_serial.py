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

# A reply can contain a prompt and still be a disaster: if the board reset mid-command it
# reboots and offers a FRESH prompt, which is byte-identical to the one this command should
# have produced. That fooled the instrument twice — once as a "spontaneous restart", once as
# a pass-1 envelope that "returned a prompt" while the board was rebooting inside it. So a
# boot banner is searched for BEFORE any prompt is believed.
BOOT_BANNER_RE = re.compile(
    rb"U-Boot SPL|\r?\nU-Boot \d|Trying to boot from|Model: Ebang|"
    rb"Loading Environment from FAT|No ethernet found")

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


# U-Boot echoes every character it reads, and it echoes with a blocking `putc`. Hand it a
# long line in one burst and its TX FIFO fills, `putc` waits for space, and while it waits
# it is not draining the RX FIFO — so the board loses input characters. Observed on 17A6
# staging a payload with ~350-character lines: the echo stopped mid-token and the prompt
# came back as `ynq> `, missing its first character.
#
# Pacing the write is the fix, not shortening the line: the line length is set by what the
# engine's watchdog allows in one command, and a paced write costs 2 ms per 32 characters.
WRITE_CHUNK = 32
WRITE_GAP_S = 0.002


def write_paced(ser, data):
    """Write in chunks the board can echo without overrunning its own receive FIFO."""
    if len(data) <= WRITE_CHUNK:
        ser.write(data)
        return
    for start in range(0, len(data), WRITE_CHUNK):
        ser.write(data[start:start + WRITE_CHUNK])
        time.sleep(WRITE_GAP_S)


def ub_cmd(ser, line, timeout=1.5):
    """Send one U-Boot command line and return everything up to the prompt."""
    ser.reset_input_buffer()
    write_paced(ser, line.encode("ascii") + b"\r")
    return read_until(ser, PROMPT_RE, timeout)


# Never an empty line. U-Boot treats a bare CR as "repeat the last command", and `md` is
# declared repeatable and resumes from an ALREADY-ADVANCED address, so an empty line after
# an `md` of the carrier reads one word past it. That word is unmapped, the carrier answers
# SLVERR by design, the A9 takes a data abort and U-Boot's abort path resets the board.
# Three "spontaneous restarts" of 2026-08-12 were exactly this. A sync must therefore be a
# NAMED, complete, harmless command whose meaning does not depend on what came before.
SYNC_COMMAND = "echo"          # CONFIG_CMD_ECHO=y on this build; prints a newline, no state


def sync_prompt(ser, timeout=2.0):
    """Land on a known prompt with a named no-op, flushing any partial line on the way.

    Both boards need this: the 4205 leaves a residual ``d`` from the autoboot
    hammer, and the 4203 takes a burst of garbage into its RX at power-on. Junk ahead of the
    command simply makes it an unknown one, which still returns a prompt.
    """
    return ub_cmd(ser, SYNC_COMMAND, timeout)


def md1(ser, addr, timeout=1.5):
    """`md <addr> 1` -> int, or raise if the reply cannot be parsed."""
    out = ub_cmd(ser, f"md 0x{addr:08x} 1", timeout)
    match = MD_RE.search(out)
    if not match:
        raise RuntimeError(f"could not parse md output for 0x{addr:08x}: {out!r}")
    return int(match.group(1), 16)


def mw1(ser, addr, value, timeout=1.5):
    ub_cmd(ser, f"mw 0x{addr:08x} 0x{value:08x} 1", timeout)
