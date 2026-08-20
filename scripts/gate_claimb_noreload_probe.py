#!/usr/bin/env python3
"""Structural gate for the no-reload diagnostic no-op.

`gate_claimb_board_driver` cannot be reused here: it *requires* `cal.phase_setup`, and this
driver's whole point is that it must never call it. So the rules are stated fresh, and several
of them are the inverse of that gate's. What is being enforced:

* the CLI is exactly `--out`, `--plmark`, `--port`, all literal, with no relaxation word in any
  of them;
* no setup, no loader, no reload path is reachable from this module at all;
* the evidence destination is reserved and the marker's format is judged BEFORE the transport
  is constructed, so those two refusals cost zero board contact; identity and same-boot need an
  open transport by construction, and both still precede the round, so every refusal on this
  path costs zero transactions;
* the entrypoint issues no console action of its own after a refusal — no interrupt, no
  acknowledgement — because those do not appear in the command telemetry;
* the round writes `restore` exactly once through the existing single production write path,
  and names no other payload;
* nothing in the module can reach the scorer, ARM, HOLDOUT, the candidate payload, or a second
  device-write call site;
* the round has no loop and no `except` that resumes: a fault and a pass both stop.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DRIVER = REPO / "scripts/board_claimb_noreload_noop.py"
ROUND_NAME = "run_noreload_noop"

# Naming any of these is disqualifying: they are the reload path, the evaluation path, the
# other rounds, and the second write door.
FORBIDDEN_REFERENCES = (
    "phase_setup", "loadb", "board_uboot_fpga_load", "require_unconfigured",
    ".interrupt(",
    "_score", "score_last_transaction", "arm_scorer", "CTRL_ARM", "CTRL_MODE_HOLDOUT",
    "run_known_answer_round", "run_postfault_capture",
    "run_candidate_on_board", "write_sequence", "execute_transaction",
)


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


def verify_source(driver_source: str) -> list[str]:
    """Return every structural problem; empty is the only accepted verdict."""
    problems: list[str] = []
    try:
        tree = ast.parse(driver_source, filename=str(DRIVER))
        main = _function(tree, "main")
        round_function = _function(tree, ROUND_NAME)
    except (SyntaxError, ValueError) as exc:
        return [f"source cannot be inspected: {exc}"]

    named_forbidden = [name for name in FORBIDDEN_REFERENCES if name in driver_source]
    if named_forbidden:
        problems.append(
            "the no-reload driver names the reload, evaluation or second-write path: "
            + repr(named_forbidden))

    calls = [(node.lineno, _call_name(node), node)
             for node in ast.walk(main) if isinstance(node, ast.Call)]

    def named(name: str) -> list[tuple[int, str, ast.Call]]:
        return [item for item in calls if item[1] == name]

    required_once = (
        "ex.PublishedCarrierAuthority.load",
        "kagate.KnownAnswerAuthority.load",
        "reserve_evidence",
        "require_plmark",
        "ident.SerialTransport",
        "cal.InstrumentedTransport",
        "ident.BoardSession",
        "session.verify_identity",
        "axi.same_boot",
        ROUND_NAME,
        "classify_stop",
    )
    for name in required_once:
        count = len(named(name))
        if count != 1:
            problems.append(f"main must call {name} exactly once, found {count}")

    # Both authorities are fixed in reviewed source, not selected by the caller.
    carrier_load = named("ex.PublishedCarrierAuthority.load")
    if carrier_load:
        args = carrier_load[0][2].args
        fixed = (len(args) == 1 and _is_attr(args[0], "cal", "DEFAULT_RUN"))
        if not fixed or carrier_load[0][2].keywords:
            problems.append("carrier authority must load only cal.DEFAULT_RUN")
    known_load = named("kagate.KnownAnswerAuthority.load")
    if known_load and (known_load[0][2].args or known_load[0][2].keywords):
        problems.append("known-answer authority load must take no caller-selected input")

    instrument = named("cal.InstrumentedTransport")
    if instrument:
        args = instrument[0][2].args
        nested = (len(args) == 2 and isinstance(args[0], ast.Call)
                  and _call_name(args[0]) == "ident.SerialTransport"
                  and len(args[0].args) == 1 and _is_attr(args[0].args[0], "args", "port")
                  and _is_name(args[1], "record"))
        if not nested:
            problems.append(
                "InstrumentedTransport must directly wrap SerialTransport(args.port) and "
                "write into record")

    session_call = named("ident.BoardSession")
    if session_call and not (len(session_call[0][2].args) == 1
                             and _is_name(session_call[0][2].args[0], "transport")):
        problems.append("BoardSession must own the instrumented transport")

    # Ordering is the whole gate: a refusal must be able to cost zero board contact, and the
    # marker must be judged before the tty is even opened.
    marker = named("require_plmark")
    reservation = named("reserve_evidence")
    serial = named("ident.SerialTransport")
    identity = named("session.verify_identity")
    same_boot = named("axi.same_boot")
    round_call = named(ROUND_NAME)
    if marker and serial and marker[0][0] >= serial[0][0]:
        problems.append("require_plmark must precede opening the transport")
    if reservation and serial and reservation[0][0] >= serial[0][0]:
        problems.append(
            "reserve_evidence must precede opening the transport, so a destination that is "
            "taken or unwritable costs no board contact")
    if reservation and marker and reservation[0][0] >= marker[0][0]:
        problems.append(
            "reserve_evidence must precede require_plmark: a marker refusal still writes an "
            "evidence record, and it may only do so into a destination this run claimed")
    if reservation and not (len(reservation[0][2].args) == 1
                            and _is_attr(reservation[0][2].args[0], "args", "out")):
        problems.append("reserve_evidence must claim args.out itself")
    if marker and not (len(marker[0][2].args) == 1
                       and _is_attr(marker[0][2].args[0], "args", "plmark")):
        problems.append("require_plmark must judge args.plmark itself")
    for earlier, later, why in (
            (identity, round_call, "session.verify_identity"),
            (same_boot, round_call, "axi.same_boot")):
        if earlier and later and earlier[0][0] >= later[0][0]:
            problems.append(f"{why} must precede {ROUND_NAME}")
    if identity and same_boot and identity[0][0] >= same_boot[0][0]:
        problems.append("session.verify_identity must precede axi.same_boot")
    if same_boot:
        args = same_boot[0][2].args
        if len(args) != 2 or not _is_name(args[0], "transport") or not _is_name(
                args[1], "expected_plmark"):
            problems.append(
                "axi.same_boot must be given the instrumented transport and the marker "
                "require_plmark returned")
    if round_call:
        args = round_call[0][2].args
        if len(args) != 3 or not all(
                _is_name(node, expected)
                for node, expected in zip(args, ("authority", "known", "session"))):
            problems.append(
                f"{ROUND_NAME} must receive authority, known, and session directly")

    parser_options: list[str] = []
    for _, name, call in calls:
        if name != "parser.add_argument" or not call.args:
            continue
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            parser_options.append(first.value)
        else:
            problems.append("every CLI option must be a literal visible to review")
    if sorted(parser_options) != ["--out", "--plmark", "--port"]:
        problems.append(
            f"the production CLI options are {sorted(parser_options)!r}; only --port, "
            "--plmark and --out are permitted")
    relax = [option for option in parser_options
             if any(word in option.lower()
                    for word in ("force", "skip", "allow", "retry", "continue", "score",
                                 "arm", "holdout", "reload"))]
    if relax:
        problems.append(f"relaxation options are forbidden: {relax}")

    # The round itself: one write, of one literal payload, with no loop and no resume.
    writes = [node for node in ast.walk(round_function)
              if isinstance(node, ast.Call) and _call_name(node) == "known_driver._write"]
    if len(writes) != 1:
        problems.append(
            f"{ROUND_NAME} must call known_driver._write exactly once, found {len(writes)}")
    else:
        first = writes[0].args[0] if writes[0].args else None
        if not (isinstance(first, ast.Constant) and first.value == "restore"):
            problems.append("the single write must name the literal payload 'restore'")
    payload_names = {node.value for node in ast.walk(round_function)
                     if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    if "candidate" in payload_names:
        problems.append(f"{ROUND_NAME} names the candidate payload")
    # Not "the name appears somewhere" — the definition alone satisfies that, and a driver
    # that defines a classifier and then hardcodes a verdict is exactly the defect. It must be
    # CALLED, from main, once, on this run's own record and this run's own cause.
    classifier = named("classify_stop")
    if classifier:
        args = classifier[0][2].args
        if len(args) != 2 or not _is_name(args[0], "record") or not _is_name(args[1], "cause"):
            problems.append(
                "classify_stop must be given this run's own record and the cause it stopped "
                "on, so the reading cannot be a constant")
    if round_call and classifier and classifier[0][0] <= round_call[0][0]:
        problems.append("classify_stop must follow the round it is classifying")

    # Nothing may mint the conditional-negative verdict for itself. Only `classify_stop`,
    # which checks the sticky refusal AND the four status fields, may name it — anywhere else
    # in the module is a path that could call something B1 without testing what B1 means.
    # Checked module-wide, not just in main: the round minting it would be the same defect one
    # level down, and that is exactly what a review of 1.0.1 found.
    try:
        classifier_body = _function(tree, "classify_stop")
    except ValueError as exc:
        problems.append(f"classify_stop must be defined exactly once: {exc}")
        classifier_body = None
    inside = {id(node) for node in ast.walk(classifier_body)} if classifier_body else set()
    stray = []
    for scope in tree.body:
        if isinstance(scope, ast.Assign) and any(
                _is_name(target, "PASS_VERDICT") for target in scope.targets):
            continue                      # the definition itself
        for node in ast.walk(scope):
            if _is_name(node, "PASS_VERDICT") and id(node) not in inside:
                stray.append(getattr(scope, "name", "<module>"))
                break
    if stray:
        problems.append(
            f"PASS_VERDICT is referenced outside classify_stop, in {sorted(set(stray))}; the "
            "B1 reading may only be issued by the function that checks the sticky refusal and "
            "the four status fields")

    loops = [node for node in ast.walk(round_function)
             if isinstance(node, (ast.For, ast.While, ast.AsyncFor))]
    if loops:
        problems.append(f"{ROUND_NAME} contains a loop, so a retry is expressible")
    for handler in [node for node in ast.walk(round_function)
                    if isinstance(node, ast.ExceptHandler)]:
        if not any(isinstance(node, ast.Raise) for node in ast.walk(handler)):
            problems.append(
                f"{ROUND_NAME} has an except arm that does not re-raise, so a fault could be "
                "absorbed and the round continue")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args()
    problems = verify_source(DRIVER.read_text(encoding="utf-8"))
    if problems:
        print("CLAIM-B NO-RELOAD PROBE REFUSED")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("CLAIM-B NO-RELOAD PROBE ACCEPTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
