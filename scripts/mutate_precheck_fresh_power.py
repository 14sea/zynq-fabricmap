#!/usr/bin/env python3
"""Mutation gate for the fresh-power precheck.

Three mutants, each restoring one thing 1.0.0 actually did wrong:

  * the boot banner was checked on the opening sync only, so a board that restarted partway
    through still passed — every register it had already answered was correct, and nothing
    looked at what came after;
  * a reply without a prompt was parsed anyway, which makes the parsed value a guess;
  * an existing record was overwritten, and a precheck record is evidence.

Each probe drives the module and reads the answer out of the record. Nothing here searches
the source for the mutation: the first mutant would be trivially findable by string and would
still tell you nothing about whether the check runs on every reply.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
SOURCE = REPO / "scripts/precheck_fresh_power.py"

PROMPT = b"\r\nZynq>"
BANNER = b"\r\nU-Boot SPL 2018.01 (Aug 16 2026 - 08:00:00)\r\nZynq> "
GOOD = {
    0xF8007000: b"f8007000: 4e00e07f    ....",
    0xF800700C: b"f800700c: a802000b    ....",
    0xF8007014: b"f8007014: 40000a30    0...",
    0xF8000170: b"f8000170: 00400800    ..@.",
}
PLMARK_ABSENT = b'printenv plmark\r\n## Error: "plmark" not defined'


def scripted(*, reboot_after=None, drop_prompt_at=None):
    """Answers every check correctly, and optionally reboots or truncates at one reply."""
    seen = [0]

    def send(command: str) -> bytes:
        index = seen[0]
        seen[0] += 1
        if command == "echo":
            body = b""
        elif command.startswith("md.l"):
            body = GOOD[int(command.split()[1], 16)]
        else:
            body = PLMARK_ABSENT
        if index == drop_prompt_at:
            return body
        return body + PROMPT + (BANNER if index == reboot_after else b"")

    return send


def load(text: str, name: str):
    path = Path(tempfile.mkdtemp(prefix="precheck-mutant-")) / f"{name}.py"
    path.write_text(text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe_mid_run_reboot(module) -> tuple[bool, str]:
    """Reply 3 is a correct STATUS followed by an SPL banner: the board restarted mid-check."""
    record = module.run_precheck(scripted(reboot_after=3))
    if record["passed"]:
        return True, "a board that rebooted during the precheck passed it"
    return False, "a mid-precheck reboot is refused"


def probe_truncated_reply(module) -> tuple[bool, str]:
    record = module.run_precheck(scripted(drop_prompt_at=2))
    if record["passed"]:
        return True, "a reply with no prompt was parsed and accepted"
    return False, "a truncated reply is refused"


def probe_overwrite(module) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as name:
        out = Path(name) / "precheck.json"
        out.write_text("{}\n", encoding="utf-8")
        try:
            module.refuse_existing(out)
        except module.PrecheckStop:
            return False, "an existing record is refused"
    return True, "an existing precheck record would have been replaced"


PROBES = {
    "check_only_the_first_reply": probe_mid_run_reboot,
    "accept_a_reply_with_no_prompt": probe_truncated_reply,
    "replace_an_existing_record": probe_overwrite,
}

MUTANTS = {
    # MUTATION ANCHOR every_reply: this is 1.0.0's behaviour, restored exactly.
    "check_only_the_first_reply": [(
        "        problems.extend(reply_problems(command, raw))",
        "        if len(record[\"replies\"]) == 1:\n"
        "            problems.extend(reply_problems(command, raw))")],
    "accept_a_reply_with_no_prompt": [(
        "    if not bs.PROMPT_RE.search(raw):\n"
        "        problems.append(f\"{command}: no U-Boot prompt came back — the reply is "
        "truncated\")\n",
        "")],
    # An operator who wanted the old overwriting behaviour would delete the guard loop, not
    # just its body, so that is what this mutant does.
    "replace_an_existing_record": [(
        "    for path in (out, transcript):\n"
        "        if path.exists():\n"
        "            raise PrecheckStop(\n"
        "                f\"{path} already exists; a precheck record is evidence and is never "
        "replaced\")\n",
        "")],
}


def main() -> int:
    original = SOURCE.read_text(encoding="utf-8")
    baseline = load(original, "baseline")
    for name, probe in PROBES.items():
        unsafe, why = probe(baseline)
        if unsafe:
            print(f"the unmutated module already answers yes to {name} ({why}); "
                  "the gate is meaningless")
            return 1

    killed = 0
    for name, edits in MUTANTS.items():
        text = original
        for before, after in edits:
            if text.count(before) != 1:
                print(f"{name}: ANCHOR occurs {text.count(before)} times — repoint it, "
                      "do not loosen the gate")
                return 1
            text = text.replace(before, after)
        unsafe, why = PROBES[name](load(text, name))
        if unsafe:
            print(f"{name}: KILLED — {why}")
            killed += 1
        else:
            print(f"{name}: SURVIVED — {why}")

    print(f"{killed}/{len(MUTANTS)} precheck mutants killed")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
