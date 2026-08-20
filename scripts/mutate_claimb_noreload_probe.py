#!/usr/bin/env python3
"""Mutation gate for the no-reload diagnostic no-op.

A gate that passes is not evidence; a gate that refuses the defect it was written for is. Each
mutant below reintroduces exactly one thing the ruling forbids, changes nothing else, and must
be killed — some by the structural gate, some by running the round against a stubbed write path
and watching what it actually does.

The six the ruling named, plus two the design's own history argued for:

  reload             putting the setup phase back
  second_transaction a candidate write after the no-op
  scoring            an evaluation call after the no-op
  skip_same_boot     dropping the boot interlock
  continue_after_pass a pass that runs on instead of stopping
  retry_after_fault   a fault that is swallowed and retried
  write_the_candidate the single write renamed to the candidate payload
  relaxation_flag     a --force option on the CLI

Three more, from the adversarial review of 1.0.0, which found each of them live:

  interrupt_after_fault  an unlogged Ctrl-C on the way out of a refusal
  overwrite_evidence     dropping the destination reservation, so an existing record is lost
  reserve_after_the_tty   reserving only once the board has already been touched
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import board_uboot_axi as axi  # noqa: E402
import gate_claimb_noreload_probe as gate  # noqa: E402

DRIVER = REPO / "scripts/board_claimb_noreload_noop.py"


def load_source(source: str, name: str):
    path = Path(tempfile.mkdtemp(prefix="claimb-noreload-mutant-")) / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def observe(module, *, fault: bool):
    """Run the round against a stubbed write path; report what it did, not what it says.

    Returns (write_payloads, evaluation_calls, steps, raised). A fault is the specified
    `F_READBACK` refusal, which is what the board actually produces here.
    """
    authority = object.__new__(module.ex.PublishedCarrierAuthority)
    known = object.__new__(module.kagate.KnownAnswerAuthority)
    payloads: list[str] = []

    def write(which, *rest):
        payloads.append(which)
        if fault:
            raise axi.AxiRefusal(
                "the engine faulted during pass 2 of envelope 0: fault_code 8 (readback)")
        return {"which": which, "transaction": {"readback_frames": {}}}

    raised = None
    steps: list[str] = []
    with (mock.patch.object(module.known_driver, "_write", side_effect=write),
          mock.patch.object(module.known_driver, "_score",
                            return_value={"scores": []}) as evaluate):
        try:
            record = module.run_noreload_noop(authority, known, object())
        except Exception as stop:
            raised = stop
            record = getattr(stop, "record", {"steps": []})
        steps = [step["step"] for step in record.get("steps", [])]
    return payloads, evaluate.call_count, steps, raised


def behavioural(name: str, source: str, *, fault: bool, expect) -> bool:
    """Kill by observation: the mutant must DO something the baseline does not."""
    try:
        module = load_source(source, name)
        observed = observe(module, fault=fault)
    except Exception as broken:
        print(f"{name}: KILLED — the mutant does not even run: "
              f"{type(broken).__name__}: {broken}")
        return True
    payloads, evaluations, steps, raised = observed
    verdict, why = expect(payloads, evaluations, steps, raised)
    print(f"{name}: {'KILLED' if verdict else 'SURVIVED'} — {why}")
    return verdict


def structural(name: str, source: str) -> bool:
    problems = gate.verify_source(source)
    if problems:
        print(f"{name}: KILLED — {problems[0]}")
        return True
    print(f"{name}: SURVIVED — the structural gate accepted it")
    return False


def main() -> int:
    driver = DRIVER.read_text(encoding="utf-8")
    killed = 0
    mutants = []

    # -- baseline, so a "kill" cannot be an artifact of the harness
    payloads, evaluations, steps, raised = observe(load_source(driver, "baseline"), fault=False)
    baseline_pass_ok = (payloads == ["restore"] and evaluations == 0
                        and steps == ["diagnostic_no_op"] and raised is None)
    payloads, evaluations, steps, raised = observe(load_source(driver, "baseline_f"), fault=True)
    baseline_fault_ok = (payloads == ["restore"] and evaluations == 0
                         and steps == ["diagnostic_no_op"]
                         and isinstance(raised, Exception))
    print(f"baseline: pass_path_ok={baseline_pass_ok} fault_path_ok={baseline_fault_ok}")
    if not (baseline_pass_ok and baseline_fault_ok):
        print("HARNESS ERROR: the unmutated round does not behave as the gate assumes")
        return 1

    write_line = '        entry["result"] = known_driver._write("restore", authority, known, session)\n'
    if driver.count(write_line) != 1:
        print("HARNESS ERROR: the single write line is not unique")
        return 1
    pass_line = '    entry["state"] = "passed"\n    record["verdict"] = PASS_VERDICT\n'
    if driver.count(pass_line) != 1:
        print("HARNESS ERROR: the pass arm is not unique")
        return 1

    # -- 1. a second transaction after the no-op
    mutants.append(("second_transaction", lambda: behavioural(
        "second_transaction",
        driver.replace(pass_line, pass_line.replace(
            '    record["verdict"] = PASS_VERDICT',
            '    known_driver._write("candidate", authority, known, session)\n'
            '    record["verdict"] = PASS_VERDICT')),
        fault=False,
        expect=lambda p, e, s, r: (
            p != ["restore"], f"payloads written: {p}"))))

    # -- 2. an evaluation after the no-op
    mutants.append(("scoring", lambda: behavioural(
        "scoring",
        driver.replace(pass_line, pass_line.replace(
            '    record["verdict"] = PASS_VERDICT',
            '    known_driver._score("restore", "train", known, session)\n'
            '    record["verdict"] = PASS_VERDICT')),
        fault=False,
        expect=lambda p, e, s, r: (e > 0, f"evaluation calls: {e}"))))

    # -- 3. a pass that continues instead of stopping
    mutants.append(("continue_after_pass", lambda: behavioural(
        "continue_after_pass",
        driver.replace(pass_line, pass_line.replace(
            '    record["verdict"] = PASS_VERDICT',
            '    entry2 = {"step": "second_no_op", "state": "started"}\n'
            '    record["steps"].append(entry2)\n'
            '    entry2["result"] = known_driver._write("restore", authority, known, session)\n'
            '    record["verdict"] = PASS_VERDICT')),
        fault=False,
        expect=lambda p, e, s, r: (
            s != ["diagnostic_no_op"], f"steps taken: {s}"))))

    # -- 4. a fault that is swallowed and retried
    retry_before = (
        '        cause = getattr(raised, "cause", None) or raised\n')
    retry_after = (
        '        cause = getattr(raised, "cause", None) or raised\n'
        '        try:\n'
        '            entry["result"] = known_driver._write(\n'
        '                "restore", authority, known, session)\n'
        '            entry["state"] = "passed"\n'
        '            record["verdict"] = PASS_VERDICT\n'
        '            return record\n'
        '        except Exception:\n'
        '            pass\n')
    if driver.count(retry_before) != 1:
        print("retry_after_fault: HARNESS ERROR anchor is not unique")
    else:
        mutants.append(("retry_after_fault", lambda: behavioural(
            "retry_after_fault", driver.replace(retry_before, retry_after), fault=True,
            expect=lambda p, e, s, r: (
                len(p) > 1, f"write attempts after the fault: {len(p)}"))))

    # -- 5. the single write renamed to the candidate payload
    mutants.append(("write_the_candidate", lambda: behavioural(
        "write_the_candidate",
        driver.replace(write_line, write_line.replace('"restore"', '"candidate"')),
        fault=False,
        expect=lambda p, e, s, r: (p != ["restore"], f"payloads written: {p}"))))

    # -- 6. the boot interlock removed  (structural)
    same_boot_line = '        axi.same_boot(transport, expected_plmark)\n'
    if driver.count(same_boot_line) != 1:
        print("skip_same_boot: HARNESS ERROR anchor is not unique")
    else:
        mutants.append(("skip_same_boot",
                        lambda: structural("skip_same_boot",
                                           driver.replace(same_boot_line, ""))))

    # -- 7. the setup phase put back  (structural)
    transport_line = (
        '        transport = cal.InstrumentedTransport(ident.SerialTransport(args.port), record)\n')
    if driver.count(transport_line) != 1:
        print("reload: HARNESS ERROR anchor is not unique")
    else:
        mutants.append(("reload", lambda: structural(
            "reload",
            driver.replace(
                transport_line,
                '        record["setup"] = cal.phase_setup(\n'
                '            args.port, cal.DEFAULT_RUN / "carrier.bit",\n'
                '            bundle["artifacts"]["carrier.bit"]["sha256"])\n'
                + transport_line))))

    # -- 8. a relaxation flag on the CLI  (structural)
    plmark_option = '    parser.add_argument("--plmark", required=True)\n'
    if driver.count(plmark_option) != 1:
        print("relaxation_flag: HARNESS ERROR anchor is not unique")
    else:
        mutants.append(("relaxation_flag", lambda: structural(
            "relaxation_flag",
            driver.replace(plmark_option,
                           plmark_option + '    parser.add_argument("--force")\n'))))

    # -- 9. an unlogged console action after a refusal
    interrupt_anchor = (
        '        record["reading"] = classify_stop(record, cause)\n')
    if driver.count(interrupt_anchor) != 1:
        print("interrupt_after_fault: HARNESS ERROR anchor is not unique")
    else:
        mutants.append(("interrupt_after_fault", lambda: structural(
            "interrupt_after_fault",
            driver.replace(
                interrupt_anchor,
                '        if transport is not None:\n'
                '            transport.interrupt()\n'
                + interrupt_anchor))))

    # -- 10. the destination reservation removed, so an existing record is overwritten
    reserve_anchor = '        partial = reserve_evidence(args.out)\n'
    if driver.count(reserve_anchor) != 1:
        print("overwrite_evidence: HARNESS ERROR anchor is not unique")
    else:
        mutants.append(("overwrite_evidence", lambda: structural(
            "overwrite_evidence",
            driver.replace(reserve_anchor,
                           '        partial = args.out.with_name(args.out.name + ".part")\n'))))

    # -- 11. the reservation moved after the board has been touched. The mutant must stay
    #        SYNTACTICALLY VALID, or the gate would "kill" it for the wrong reason: the whole
    #        pre-flight try/except goes, and the call reappears after the transport exists.
    preflight = (
        "    try:\n"
        "        partial = reserve_evidence(args.out)\n"
        "    except EvidenceReservationStop as stop:\n"
        '        print(f"STOP: {stop}", file=sys.stderr)\n'
        "        return 1\n")
    transport_line_2 = (
        '        transport = cal.InstrumentedTransport(ident.SerialTransport(args.port), record)\n')
    if driver.count(preflight) == 1 and driver.count(transport_line_2) == 1:
        moved = driver.replace(preflight, "")
        moved = moved.replace(transport_line_2, transport_line_2 + reserve_anchor)
        import ast as _ast
        _ast.parse(moved)          # the mutant must be real source, not a syntax error
        mutants.append(("reserve_after_the_tty",
                        lambda: structural("reserve_after_the_tty", moved)))
    else:
        print("reserve_after_the_tty: HARNESS ERROR anchors are not unique")

    for _, run in mutants:
        killed += 1 if run() else 0

    total = len(mutants)
    print(f"{killed}/{total} no-reload probe mutants killed")
    return 0 if killed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
