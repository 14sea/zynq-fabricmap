#!/usr/bin/env python3
"""Structural gate for the single Claim B known-answer board driver.

This gate does not decide whether a payload is scientifically correct; the published
known-answer consumer does that. It decides whether the production CLI retains the board
boundary that makes that judgment meaningful: fixed authorities, the reviewed loader,
same-boot before the round, one instrumented identity session, and no relaxation flags.

The setup function is checked too. Calling a well-named helper is not evidence if that
helper quietly stops requiring an empty PL, so the loader argv must still contain
``--require-unconfigured``. The mutation gate applies exactly those two omissions to
copies of the source and requires this gate to refuse both.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DRIVER = REPO / "scripts/board_claimb_known_answer.py"
SETUP = REPO / "scripts/board_calibrate_noop.py"


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    found = [node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(found) != 1:
        raise ValueError(f"expected one {name}(), found {len(found)}")
    return found[0]


def _call_name(call: ast.Call) -> str:
    parts: list[str] = []
    node = call.func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _is_attr(node: ast.AST, owner: str, attr: str) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == attr
            and _is_name(node.value, owner))


def verify_sources(driver_source: str, setup_source: str) -> list[str]:
    """Return every structural problem; empty is the only accepted verdict."""
    problems: list[str] = []
    try:
        driver_tree = ast.parse(driver_source, filename=str(DRIVER))
        setup_tree = ast.parse(setup_source, filename=str(SETUP))
        main = _function(driver_tree, "main")
        phase_setup = _function(setup_tree, "phase_setup")
    except (SyntaxError, ValueError) as exc:
        return [f"source cannot be inspected: {exc}"]

    calls = [(node.lineno, _call_name(node), node)
             for node in ast.walk(main) if isinstance(node, ast.Call)]

    def named(name: str) -> list[tuple[int, str, ast.Call]]:
        return [item for item in calls if item[1] == name]

    required_once = (
        "ex.PublishedCarrierAuthority.load",
        "kagate.KnownAnswerAuthority.load",
        "cal.phase_setup",
        "ident.SerialTransport",
        "cal.InstrumentedTransport",
        "ident.BoardSession",
        "session.verify_identity",
        "axi.same_boot",
        "run_known_answer_round",
    )
    for name in required_once:
        count = len(named(name))
        if count != 1:
            problems.append(f"main must call {name} exactly once, found {count}")

    # Both authorities are fixed by reviewed source, rather than selected by the caller.
    carrier_load = named("ex.PublishedCarrierAuthority.load")
    if carrier_load:
        args = carrier_load[0][2].args
        fixed = (len(args) == 1 and isinstance(args[0], ast.Attribute)
                 and isinstance(args[0].value, ast.Name)
                 and args[0].value.id == "cal" and args[0].attr == "DEFAULT_RUN")
        if not fixed or carrier_load[0][2].keywords:
            problems.append("carrier authority must load only cal.DEFAULT_RUN")
    known_load = named("kagate.KnownAnswerAuthority.load")
    if known_load and (known_load[0][2].args or known_load[0][2].keywords):
        problems.append("known-answer authority load must take no caller-selected input")

    setup_call = named("cal.phase_setup")
    if setup_call:
        args = setup_call[0][2].args
        carrier = args[1] if len(args) > 1 else None
        fixed_carrier = (isinstance(carrier, ast.BinOp) and isinstance(carrier.op, ast.Div)
                         and _is_attr(carrier.left, "cal", "DEFAULT_RUN")
                         and isinstance(carrier.right, ast.Constant)
                         and carrier.right.value == "carrier.bit")
        if len(args) != 3 or not _is_attr(args[0], "args", "port") or not fixed_carrier:
            problems.append(
                "phase_setup must receive args.port and cal.DEFAULT_RUN / 'carrier.bit'")

    instrument = named("cal.InstrumentedTransport")
    if instrument:
        args = instrument[0][2].args
        nested_serial = (len(args) == 2 and isinstance(args[0], ast.Call)
                         and _call_name(args[0]) == "ident.SerialTransport"
                         and len(args[0].args) == 1
                         and _is_attr(args[0].args[0], "args", "port")
                         and _is_name(args[1], "record"))
        if not nested_serial:
            problems.append(
                "InstrumentedTransport must directly wrap SerialTransport(args.port) "
                "and write into record")

    session_call = named("ident.BoardSession")
    if session_call and not (len(session_call[0][2].args) == 1
                             and _is_name(session_call[0][2].args[0], "transport")):
        problems.append("BoardSession must own the instrumented transport")

    # The boot marker must be judged before the first call that can touch the carrier.
    same_boot = named("axi.same_boot")
    round_call = named("run_known_answer_round")
    if same_boot and round_call and same_boot[0][0] >= round_call[0][0]:
        problems.append("axi.same_boot must precede run_known_answer_round")
    if round_call:
        args = round_call[0][2].args
        if len(args) != 3 or not all(
                _is_name(node, expected)
                for node, expected in zip(args, ("authority", "known", "session"))):
            problems.append(
                "run_known_answer_round must receive authority, known, and session directly")

    parser_options: list[str] = []
    for _, name, call in calls:
        if name != "parser.add_argument" or not call.args:
            continue
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            parser_options.append(first.value)
        else:
            problems.append("every CLI option must be a literal visible to review")
    if sorted(parser_options) != ["--out", "--port"]:
        problems.append(
            f"the production CLI options are {sorted(parser_options)!r}; only --port and "
            "--out are permitted")
    relax = [option for option in parser_options
             if any(word in option.lower() for word in ("force", "skip", "allow"))]
    if relax:
        problems.append(f"relaxation options are forbidden: {relax}")

    setup_constants = [node.value for node in ast.walk(phase_setup)
                       if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    count = setup_constants.count("--require-unconfigured")
    if count != 1:
        problems.append(
            "phase_setup must put --require-unconfigured in the loader argv exactly once, "
            f"found {count}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args()
    problems = verify_sources(
        DRIVER.read_text(encoding="utf-8"), SETUP.read_text(encoding="utf-8"))
    if problems:
        print("CLAIM-B BOARD DRIVER REFUSED")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("CLAIM-B BOARD DRIVER ACCEPTED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
